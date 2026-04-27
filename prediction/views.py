import os
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
from .serializers import DangerPredictionSerializer
from django.core.cache import cache


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
