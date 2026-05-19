import os
from datetime import datetime
from functools import lru_cache
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
import pandas as pd
import numpy as np
import joblib
import geopandas as gpd
from shapely.geometry import Point
from sklearn.neighbors import BallTree
from .serializers import DangerPredictionSerializer, SafeRouteRequestSerializer
from django.core.cache import cache


RISK_LABELS = {0: "faible", 1: "modere", 2: "eleve"}


def _prediction_assets_paths():
    base_dir = os.path.join(settings.BASE_DIR, "prediction")
    return (
        os.path.join(base_dir, "data", "data_reports.csv"),
        os.path.join(base_dir, "model", "best_model.pkl"),
        os.path.join(base_dir, "model", "scaler.pkl"),
    )


@lru_cache(maxsize=1)
def _load_prediction_assets():
    csv_path, model_path, scaler_path = _prediction_assets_paths()
    df = pd.read_csv(csv_path)
    df["degree_report"] = df["degree_report"].map(
        {"faible": 0, "modéré": 1, "élevé": 2}
    )
    df["degree_report"] = df["degree_report"].fillna(0)
    coords_rad = np.radians(df[["latitude_report", "longitude_report"]].to_numpy())
    tree = BallTree(coords_rad, metric="haversine")
    model = joblib.load(model_path)
    scaler = joblib.load(scaler_path)
    return df, tree, model, scaler


def _sample_route_geometry(geometry, max_points=36):
    if not geometry:
        return []
    if len(geometry) <= max_points:
        sampled = geometry
    else:
        indexes = np.linspace(0, len(geometry) - 1, num=max_points, dtype=int)
        sampled = [geometry[index] for index in indexes]

    normalized = []
    for point in sampled:
        if len(point) < 2:
            continue
        lon, lat = point[0], point[1]
        normalized.append((float(lat), float(lon)))

    last_lon, last_lat = geometry[-1][0], geometry[-1][1]
    last_point = (float(last_lat), float(last_lon))
    if not normalized or normalized[-1] != last_point:
        normalized.append(last_point)
    return normalized


def _predict_risk_for_point(lat, lon, hour, day_of_week, df, tree, model, scaler):
    point_rad = np.radians([[lat, lon]])
    radius_rad = 0.5 / 6371.0
    indices = tree.query_radius(point_rad, r=radius_rad)[0]

    density = int(len(indices))
    mean_degree_danger = (
        float(df.iloc[indices]["degree_report"].mean()) if density > 0 else 0.0
    )

    input_data = np.array(
        [[lat, lon, hour, day_of_week, density, mean_degree_danger]],
        dtype=float,
    )
    input_scaled = scaler.transform(input_data)
    probas = model.predict_proba(input_scaled)[0]
    prediction = int(np.argmax(probas))
    confidence = float(np.max(probas))
    density_factor = min(density / 8.0, 1.0)
    danger_factor = min(mean_degree_danger / 2.0, 1.0)
    risk_score = min(
        1.0,
        (float(probas[1]) * 0.45)
        + (float(probas[2]) * 0.95)
        + (density_factor * 0.15)
        + (danger_factor * 0.15),
    )

    return {
        "latitude": float(lat),
        "longitude": float(lon),
        "prediction": prediction,
        "label": RISK_LABELS[prediction],
        "confidence": confidence,
        "density": density,
        "mean_degree_danger": mean_degree_danger,
        "risk_score": risk_score,
    }


def _route_risk_level(avg_risk_score, high_risk_points, sampled_points):
    high_risk_ratio = high_risk_points / max(sampled_points, 1)
    if avg_risk_score >= 0.65 or high_risk_ratio >= 0.35:
        return "high"
    if avg_risk_score >= 0.35 or high_risk_ratio >= 0.15:
        return "medium"
    return "low"


def _build_route_justifications(
    avg_risk_score,
    max_risk_score,
    high_risk_points,
    moderate_risk_points,
    sampled_points,
    average_density,
):
    justifications = []
    if high_risk_points == 0:
        justifications.append(
            "Aucun segment fortement risque n'a ete detecte sur les points echantillonnes."
        )
    else:
        justifications.append(
            f"{high_risk_points} point(s) echantillonnes presentent un risque eleve."
        )

    if avg_risk_score < 0.35:
        justifications.append(
            "Le trajet reste majoritairement dans des zones a faible exposition."
        )
    elif avg_risk_score < 0.65:
        justifications.append(
            "Le trajet traverse quelques zones de vigilance, mais limite l'exposition globale."
        )
    else:
        justifications.append(
            "Le trajet reste expose a plusieurs zones sensibles et doit etre evite si possible."
        )

    if moderate_risk_points:
        justifications.append(
            f"{moderate_risk_points} point(s) supplementaires montrent une vigilance moderee."
        )

    if average_density < 1:
        justifications.append(
            "La densite moyenne de signalements proches reste faible sur le parcours."
        )
    else:
        justifications.append(
            "Le score integre la densite locale de signalements historiques et recents."
        )

    if max_risk_score >= 0.8 and sampled_points > 0:
        justifications.append(
            "Un pic de risque ponctuel subsiste; surveillez l'environnement autour de cette portion."
        )

    return justifications[:4]


def _score_route(route, hour, day_of_week, route_index):
    df, tree, model, scaler = _load_prediction_assets()
    sampled_points = _sample_route_geometry(route["geometry"])
    if len(sampled_points) < 2:
        raise ValueError("La geometrie d'une route candidate est invalide.")

    point_scores = [
        _predict_risk_for_point(
            lat=lat,
            lon=lon,
            hour=hour,
            day_of_week=day_of_week,
            df=df,
            tree=tree,
            model=model,
            scaler=scaler,
        )
        for lat, lon in sampled_points
    ]

    route_risk_scores = [point["risk_score"] for point in point_scores]
    avg_risk_score = float(np.mean(route_risk_scores))
    max_risk_score = float(np.max(route_risk_scores))
    sampled_count = len(point_scores)
    high_risk_points = sum(
        1 for point in point_scores if point["prediction"] == 2 or point["risk_score"] >= 0.7
    )
    moderate_risk_points = sum(
        1
        for point in point_scores
        if point["prediction"] == 1 or 0.4 <= point["risk_score"] < 0.7
    )
    average_density = float(np.mean([point["density"] for point in point_scores]))
    average_model_confidence = float(
        np.mean([point["confidence"] for point in point_scores])
    )

    distance_penalty = min(float(route["distance_m"]) / 15000.0, 1.0) * 0.18
    duration_penalty = min(float(route["duration_s"]) / 3600.0, 1.0) * 0.07
    high_risk_penalty = (high_risk_points / max(sampled_count, 1)) * 0.25
    optimization_cost = min(
        1.0,
        (avg_risk_score * 0.55)
        + (max_risk_score * 0.2)
        + high_risk_penalty
        + distance_penalty
        + duration_penalty,
    )
    safety_score = max(0.0, 1.0 - optimization_cost)
    risk_level = _route_risk_level(avg_risk_score, high_risk_points, sampled_count)

    return {
        "route_id": route.get("id") or f"route_{route_index}",
        "distance_m": float(route["distance_m"]),
        "duration_s": float(route["duration_s"]),
        "geometry": route["geometry"],
        "safety_score": round(safety_score, 4),
        "optimization_cost": round(float(optimization_cost), 4),
        "avg_risk_score": round(avg_risk_score, 4),
        "max_risk_score": round(max_risk_score, 4),
        "risk_level": risk_level,
        "high_risk_points": int(high_risk_points),
        "moderate_risk_points": int(moderate_risk_points),
        "sampled_points": int(sampled_count),
        "average_density": round(average_density, 2),
        "average_model_confidence": round(average_model_confidence, 4),
        "justifications": _build_route_justifications(
            avg_risk_score=avg_risk_score,
            max_risk_score=max_risk_score,
            high_risk_points=high_risk_points,
            moderate_risk_points=moderate_risk_points,
            sampled_points=sampled_count,
            average_density=average_density,
        ),
    }


class DangerPredictionProximityAPIView(APIView):
    def get(self, request):
        try:
            # Paramètres facultatifs
            hour = int(request.GET.get('hour', 14))
            day_of_week = int(request.GET.get('day_of_week', 2))

            # --- Ajout du cache ---
            cache_key = f"prediction_grid:{hour}:{day_of_week}"
            cached_result = cache.get(cache_key)
            if cached_result:
                return Response(cached_result)
            # --- Fin ajout du cache ---

            # Chemins
            csv_path = os.path.join(settings.BASE_DIR, "prediction", "data", "data_reports.csv")
            model_path = os.path.join(settings.BASE_DIR, "prediction", "model", "best_model.pkl")
            scaler_path = os.path.join(settings.BASE_DIR, "prediction", "model", "scaler.pkl")

            # Chargement des signalements
            df = pd.read_csv(csv_path)
            df['degree_report'] = df['degree_report'].map({"faible": 0, "modéré": 1, "élevé": 2})

            # GeoDataFrame
            gdf = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df.longitude_report, df.latitude_report), crs="EPSG:4326")

            #  Créer un buffer de 1km autour des points signalés
            buffer_zone = gdf.unary_union.buffer(0.01)  # 0.01 ≈ 1 km

            # Générer une grille dans les limites du buffer
            bounds = buffer_zone.bounds
            lats = np.linspace(bounds[1], bounds[3], 80)
            lons = np.linspace(bounds[0], bounds[2], 80)
            grid = [(lat, lon) for lat in lats for lon in lons]
            grid_df = pd.DataFrame(grid, columns=['latitude_report', 'longitude_report'])
            grid_df['hour'] = hour
            grid_df['day_of_week'] = day_of_week

            #  Garder seulement les points dans le buffer
            grid_df['geometry'] = grid_df.apply(lambda row: Point(row['longitude_report'], row['latitude_report']), axis=1)
            grid_gdf = gpd.GeoDataFrame(grid_df, geometry='geometry', crs="EPSG:4326")
            grid_gdf = grid_gdf[grid_gdf.geometry.within(buffer_zone)]

            # Calcul densité et danger moyen
            tree = BallTree(np.radians(df[['latitude_report', 'longitude_report']]), metric='haversine')
            coords_rad = np.radians(grid_gdf[['latitude_report', 'longitude_report']])
            radius_rad = 0.5 / 6371.0
            indices = tree.query_radius(coords_rad, r=radius_rad)
            grid_gdf['density'] = [len(i) for i in indices]
            mean_danger = []
            for i in indices:
                if len(i) > 0:
                    val = df.iloc[i]['degree_report'].mean()
                    mean_danger.append(val if not pd.isna(val) else 0)
                else:
                    mean_danger.append(0)

            grid_gdf['mean_degree_danger'] = mean_danger
            grid_gdf = grid_gdf.fillna(0)


            # ⚙️ Charger modèle et scaler
            model = joblib.load(model_path)
            scaler = joblib.load(scaler_path)

            features = ['latitude_report', 'longitude_report', 'hour', 'day_of_week', 'density', 'mean_degree_danger']
            X = scaler.transform(grid_gdf[features])

            probas = model.predict_proba(X)
            preds = np.argmax(probas, axis=1)
            confidence = np.max(probas, axis=1)

            grid_gdf['prediction'] = preds
            grid_gdf['confidence'] = confidence
            grid_gdf['proba_0'] = probas[:, 0]
            grid_gdf['proba_1'] = probas[:, 1]
            grid_gdf['proba_2'] = probas[:, 2]

            # Filtrage optionnel (on garde tout ici)
            result = grid_gdf[['latitude_report', 'longitude_report', 'prediction', 'confidence', 'proba_0', 'proba_1', 'proba_2']]
            data = result.to_dict(orient='records')

            # --- Mise en cache du résultat ---
            cache.set(cache_key, data, timeout=60*10)  # 10 minutes
            # --- Fin mise en cache ---

            return Response(data)

        except Exception as e:
            print(e)
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class DangerPredictSingleAPIView(APIView):
    def get(self, request):
        try:
            lat = float(request.GET.get("latitude"))
            lon = float(request.GET.get("longitude"))
            hour = int(request.GET.get("hour"))
            day_of_week = int(request.GET.get("day_of_week"))

            # --- Ajout du cache ---
            cache_key = f"prediction:{lat}:{lon}:{hour}:{day_of_week}"
            cached_result = cache.get(cache_key)
            if cached_result:
                return Response(cached_result)
            # --- Fin ajout du cache ---

            # 2. Charger les signalements
            csv_path = os.path.join(
                settings.BASE_DIR, "prediction", "data", "data_reports.csv"
            )
            df = pd.read_csv(csv_path)
            df["degree_report"] = df["degree_report"].map(
                {"faible": 0, "modéré": 1, "élevé": 2}
            )

            # 3. Construire BallTree pour densité & danger moyen
            coords = np.radians(df[["latitude_report", "longitude_report"]])
            tree = BallTree(coords, metric="haversine")
            point_rad = np.radians([[lat, lon]])
            radius_rad = 0.5 / 6371.0
            indices = tree.query_radius(point_rad, r=radius_rad)[0]

            density = len(indices)
            mean_degree_danger = (
                df.iloc[indices]["degree_report"].mean() if len(indices) > 0 else 0
            )

            # 4. Charger modèle et scaler
            model_path = os.path.join(
                settings.BASE_DIR, "prediction", "model", "best_model.pkl"
            )
            scaler_path = os.path.join(
                settings.BASE_DIR, "prediction", "model", "scaler.pkl"
            )
            model = joblib.load(model_path)
            scaler = joblib.load(scaler_path)

            # 5. Préparer les features pour prédiction
            input_data = np.array(
                [[lat, lon, hour, day_of_week, density, mean_degree_danger]]
            )
            input_scaled = scaler.transform(input_data)

            # 6. Prédire

            probas = model.predict_proba(input_scaled)[0]
            confidence = float(np.max(probas))
            prediction = int(np.argmax(probas))

            reverse_map = {0: "faible", 1: "modéré", 2: "élevé"}

            result = {
                "latitude": lat,
                "longitude": lon,
                "hour": hour,
                "day_of_week": day_of_week,
                "density": density,
                "mean_degree_danger": mean_degree_danger,
                "prediction": prediction,
                "label": reverse_map[prediction],
                "confidence": confidence,
                "probabilities": {
                    "faible": float(probas[0]),
                    "modéré": float(probas[1]),
                    "élevé": float(probas[2]),
                },
            }

            # --- Mise en cache du résultat ---
            cache.set(cache_key, result, timeout=60*10)  # 10 minutes
            # --- Fin mise en cache ---

            return Response(result)

        except Exception as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )



class SafeRouteScoreAPIView(APIView):
    def post(self, request):
        serializer = SafeRouteRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        payload = serializer.validated_data
        now = datetime.now()
        hour = payload.get("hour", now.hour)
        day_of_week = payload.get("day_of_week", now.weekday())

        try:
            scored_routes = [
                _score_route(route, hour, day_of_week, index)
                for index, route in enumerate(payload["routes"], start=1)
            ]
        except FileNotFoundError as exc:
            return Response(
                {
                    "error": "Les artefacts de prediction sont introuvables.",
                    "detail": str(exc),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        except ValueError as exc:
            return Response(
                {"error": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as exc:
            return Response(
                {"error": str(exc)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        ranked_routes = sorted(scored_routes, key=lambda route: route["optimization_cost"])
        shortest_route = min(scored_routes, key=lambda route: route["distance_m"])

        return Response(
            {
                "origin": payload["origin"],
                "destination": payload["destination"],
                "recommended_route": ranked_routes[0],
                "alternatives": ranked_routes[1:],
                "routes_evaluated": len(ranked_routes),
                "comparison": {
                    "shortest_route_id": shortest_route["route_id"],
                    "recommended_is_shortest": ranked_routes[0]["route_id"] == shortest_route["route_id"],
                },
            }
        )
