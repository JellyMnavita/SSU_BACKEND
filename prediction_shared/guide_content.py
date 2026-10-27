"""Contenu du guide — calcul trajets sécurisés et secteurs Kinshasa."""

from __future__ import annotations

from datetime import datetime
from typing import Any

GUIDE_TITLE = "Guide SSU Bokengi — Trajets sécurisés et secteurs de risque"

GUIDE_SUBTITLE = (
    "Documentation du calcul des itinéraires, des pourcentages par secteur "
    "et de la carte de prédiction géospatiale"
)


def build_guide_document() -> dict[str, Any]:
    return {
        "title": GUIDE_TITLE,
        "subtitle": GUIDE_SUBTITLE,
        "generated_at": datetime.now().strftime("%d/%m/%Y à %H:%M"),
        "version": "1.0 — prediction-service + prediction_shared",
        "sections": _sections(),
        "tables": _tables(),
        "architecture": _architecture_steps(),
        "formulas": _formulas(),
        "limits": _limits(),
    }


def _sections() -> list[dict[str, str]]:
    return [
        {
            "id": "1",
            "title": "Vue d'ensemble",
            "body": (
                "L'application SSU Bokengi propose deux visualisations complémentaires : "
                "une <b>carte de chaleur</b> (grille 48×48) alimentée par le microservice "
                "<i>prediction-service</i>, et des <b>secteurs</b> (8×8) affichant des "
                "pourcentages faible / modéré / élevé. Le mode <b>trajet sécurisé</b> "
                "interroge Mapbox pour obtenir plusieurs candidats (marche / vélo), puis "
                "les classe selon un score de sécurité combinant modèle ML et signalements "
                "validés terrain (statut V)."
            ),
        },
        {
            "id": "2",
            "title": "Données sources",
            "body": (
                "Tous les calculs s'appuient sur <b>data_reports.csv</b> : export des "
                "signalements validés (latitude, longitude, degré F/M/E, description, date). "
                "Le modèle ML (Gradient Boosting ou meilleur candidat en CV) est entraîné "
                "sur ce fichier. À l'inférence, six features sont utilisées : latitude, "
                "longitude, heure, jour de la semaine, densité locale (500 m) et degré "
                "moyen des voisins (BallTree haversine)."
            ),
        },
        {
            "id": "3",
            "title": "Grille 48×48 et score de risque par cellule",
            "body": (
                "Kinshasa est découpée en une grille régulière de 48×48 points (~2 304 cellules). "
                "Pour chaque cellule, le service calcule la densité de signalements dans un "
                "rayon de <b>500 m</b> et le degré moyen observé chez les voisins. "
                "Le modèle produit trois probabilités (faible, modéré, élevé). "
                "Le <b>risk_score</b> composite (0–1) combine probabilités modéré/élevé "
                "et contexte local :<br/>"
                "<i>risk_score = min(1, proba_modéré×0,45 + proba_élevé×0,95 "
                "+ facteur_densité×0,15 + facteur_danger×0,15)</i><br/>"
                "Seules les cellules avec signal significatif sont affichées comme points "
                "cliquables (filtre anti-saturation verte)."
            ),
        },
        {
            "id": "4",
            "title": "Secteurs 8×8 — découpage et pourcentages",
            "body": (
                "La ville est aussi découpée en <b>64 secteurs</b> (8 lignes × 8 colonnes) "
                "sur la bbox OSM de Kinshasa. Pour chaque secteur, deux jeux de statistiques "
                "sont calculés :<br/><br/>"
                "<b>A) Statistiques terrain (prioritaires)</b> — si au moins un signalement "
                "validé se trouve dans le secteur, les pourcentages affichés "
                "(pct_faible, pct_modere, pct_eleve) reflètent la répartition <b>réelle</b> "
                "des degrés F/M/E des signalements.<br/><br/>"
                "<b>B) Statistiques grille ML (secours)</b> — s'il n'y a aucun signalement "
                "validé dans le secteur, les pourcentages proviennent de la répartition "
                "des prédictions ML sur les cellules 48×48 du secteur.<br/><br/>"
                "Le <b>niveau dominant</b> (risk_level : faible / modere / eleve) est dérivé "
                "des pourcentages retenus et du score moyen, avec seuils : élevé si "
                "pct_élevé ≥ 25 % ou score ≥ 0,65 ; modéré si pct_modéré ≥ 30 %, "
                "pct_élevé ≥ 10 % ou score ≥ 0,40."
            ),
        },
        {
            "id": "5",
            "title": "Trajet sécurisé — pipeline",
            "body": (
                "<b>Étape 1 — Candidats Mapbox</b> : le frontend appelle l'API Directions "
                "(profils walking et cycling, alternatives=true) entre origine et destination. "
                "Jusqu'à 10 routes candidates sont conservées (dédoublonnage géométrique).<br/><br/>"
                "<b>Étape 2 — Échantillonnage du tracé</b> : chaque route est découpée en "
                "jusqu'à <b>48 points</b> régulièrement espacés le long de la polyligne, "
                "plus l'arrivée exacte. Les signalements validés situés à <b>≤ 120 m</b> "
                "du tracé sont ajoutés comme points de contrôle supplémentaires (pour ne pas "
                "« rater » un passage sur un signalement).<br/><br/>"
                "<b>Étape 3 — Score ML par point</b> : pour chaque point échantillon, "
                "prediction-service calcule densité, danger voisin et prédiction ML "
                "(predict_point).<br/><br/>"
                "<b>Étape 4 — Hazard terrain</b> : indépendamment du ML, un score "
                "<b>report_hazard</b> (0–1) mesure la proximité des signalements validés "
                "réels (voir tableau distances).<br/><br/>"
                "<b>Étape 5 — Agrégation route</b> : moyenne et maximum des risques ML et "
                "terrain, comptage des segments à haut risque, puis calcul du "
                "<b>optimization_cost</b> (plus bas = plus sûr). La route recommandée est "
                "celle au coût minimal."
            ),
        },
        {
            "id": "6",
            "title": "Formule de classement des itinéraires",
            "body": (
                "Pour chaque route candidate :<br/>"
                "<i>risk_effectif(point) = max(risk_ML, report_hazard)</i> si hazard ≥ 0,45 ; "
                "sinon <i>risk_ML</i> si densité ≥ 1 ; sinon <i>risk_ML × 0,35</i>.<br/>"
                "<i>combined_avg = max(moyenne(risk_effectif), moyenne(report_hazard) × 0,75)</i><br/>"
                "<i>combined_max = max(max(risk_effectif), max(report_hazard))</i><br/>"
                "<i>high_risk_penalty = (points_haut_risque / N) × 0,22</i><br/>"
                "<i>report_penalty = min(0,48 ; max(max_hazard×0,28 ; avg_hazard×0,16))</i> "
                "— renforcée si passage à ≤ 120 m d'un signalement validé.<br/>"
                "<i>optimization_cost = min(1 ; combined_avg×0,36 + combined_max×0,22 "
                "+ high_risk_penalty×0,85 + report_penalty + pénalité_distance + pénalité_durée)</i><br/>"
                "<i>safety_score = 1 − optimization_cost</i> (affiché en % côté frontend).<br/><br/>"
                "Pénalités distance et durée : <i>min(distance/15000, 1)×0,12</i> et "
                "<i>min(durée/3600, 1)×0,05</i>.<br/>"
                "Niveau textuel : <b>low</b> / <b>medium</b> / <b>high</b> selon le score "
                "combiné et la proportion de points à haut risque."
            ),
        },
        {
            "id": "7",
            "title": "Carte admin — toggle « Grille ville » et secteurs",
            "body": (
                "Dans la carte admin (<i>MapPage</i>), le panneau « Outils » propose deux couches "
                "distinctes liées à la prédiction IA :<br/><br/>"
                "<b>Grille ville</b> — active la heatmap 48×48 (couches Mapbox "
                "<i>predictions-heat-grid</i> + cercles cliquables). Chaque cellule affiche "
                "la prédiction ML et le <i>risk_score</i> composite. Les points faibles ne "
                "s'affichent que s'ils sont documentés par au moins 2 signalements à proximité.<br/><br/>"
                "<b>Secteurs</b> — active la couche <i>risk-sectors-fill</i> (64 polygones 8×8). "
                "Au clic, le popup montre les pourcentages F/M/E : priorité aux signalements "
                "validés terrain ; sinon pourcentages issus de la grille ML "
                "(champs <i>grid_pct_*</i>).<br/><br/>"
                "Les deux couches consomment le même appel API <b>GET /grid/layers</b> ; "
                "seule la visibilité côté carte change."
            ),
        },
        {
            "id": "8",
            "title": "Carte de chaleur — couleurs",
            "body": (
                "Trois couches heatmap Mapbox superposées, filtrées par classe prédite :<br/>"
                "• <b>Vert / bleu</b> — prédiction faible (danger=0)<br/>"
                "• <b>Orange / ambre</b> — prédiction modérée (danger=1)<br/>"
                "• <b>Rouge</b> — prédiction élevée (danger=2)<br/><br/>"
                "Les poids heatmap sont calibrés pour que modéré et élevé ne produisent "
                "pas la même teinte. Les cercles cliquables reprennent le code couleur "
                "vert / jaune / rouge selon la classe."
            ),
        },
        {
            "id": "9",
            "title": "API et déploiement",
            "body": (
                "• <b>GET /grid/layers</b> — grille, heatmap, secteurs (prediction-service)<br/>"
                "• <b>POST /routes/score</b> — scoring des candidats Mapbox<br/>"
                "• <b>POST /predict</b> — prédiction ponctuelle<br/>"
                "• Django (web) délègue l'inférence au microservice ; seule l'agrégation "
                "par commune reste côté backend (requête PostgreSQL).<br/>"
                "Volumes Docker partagés : <i>ssu_backend/prediction/data</i> et "
                "<i>ssu_backend/prediction/model</i>."
            ),
        },
    ]


def _tables() -> list[dict[str, Any]]:
    return [
        {
            "title": "Distances hazard terrain (report_proximity_hazard)",
            "headers": ["Distance au signalement", "Effet sur hazard_score"],
            "rows": [
                ["≤ 50 m (sur le point)", "0,92 – 1,00 (selon degré F/M/E)"],
                ["≤ 120 m", "0,72 – 0,90"],
                ["≤ 350 m", "0,45 – 0,70"],
                ["≤ 500 m (zone BallTree)", "Décroissance linéaire jusqu'à ~0,25–0,60"],
                ["> 500 m", "0 (hors voisinage)"],
            ],
        },
        {
            "title": "Pénalités dans optimization_cost (trajet)",
            "headers": ["Composante", "Formule / seuil"],
            "rows": [
                ["Risque moyen combiné", "combined_avg × 0,36"],
                ["Pic de risque", "combined_max × 0,22"],
                ["Segments haut risque", "(high_risk_points / N) × 0,22 × 0,85"],
                ["Signalements proches", "report_penalty (max 0,48 ; +0,03/crossing si ≤120 m)"],
                ["Distance", "min(distance/15000, 1) × 0,12"],
                ["Durée", "min(duration/3600, 1) × 0,05"],
            ],
        },
        {
            "title": "Secteur — champs renvoyés à l'API",
            "headers": ["Champ", "Description"],
            "rows": [
                ["pct_faible / modere / eleve", "Pourcentages affichés (terrain ou ML)"],
                ["grid_pct_*", "Pourcentages ML bruts (toujours calculés)"],
                ["observed_report_count", "Nombre de signalements validés dans le secteur"],
                ["avg_risk_score", "Score moyen des cellules grille dans le secteur"],
                ["avg_density", "Densité moyenne signalements / 500 m"],
                ["risk_level", "faible | modere | eleve"],
            ],
        },
    ]


def _architecture_steps() -> list[str]:
    return [
        "Export signalements V → data_reports.csv (Celery / manage.py)",
        "Entraînement ML → best_model.pkl + scaler.pkl (prediction_shared)",
        "prediction-service charge CSV + modèle (volume Docker partagé)",
        "Frontend carte → GET /api/danger-predictions/ → proxy Django → GET /grid/layers",
        "Trajet sécurisé → Mapbox Directions → POST /api/safe-routes/score/ → POST /routes/score",
    ]


def _formulas() -> list[dict[str, str]]:
    return [
        {
            "name": "Features ML (6)",
            "expr": "lat, lon, hour, day_of_week, density_500m, nearest_neighbor_km (+ engenierie sans degré)",
        },
        {
            "name": "risk_score cellule",
            "expr": "min(1, P(modéré)×0,45 + P(élevé)×0,95 + min(density/8,1)×0,25)",
        },
        {
            "name": "optimization_cost trajet",
            "expr": "min(1, combined_avg×0,36 + combined_max×0,22 + high_risk_penalty×0,85 + report_penalty + dist_pen + dur_pen)",
        },
        {
            "name": "niveau secteur (risk_level)",
            "expr": "élevé si pct_E≥25% ou avg_risk≥0,65 ; modéré si pct_M≥30% ou pct_E≥10% ou avg_risk≥0,40",
        },
        {
            "name": "safety_score trajet",
            "expr": "1 − optimization_cost",
        },
    ]


def _limits() -> list[str]:
    return [
        "Mapbox ne reçoit pas de zones d'évitement : le contournement repose uniquement "
        "sur le classement des alternatives déjà proposées par Directions.",
        "Un trajet unique imposé par la topographie peut rester risqué si toutes les "
        "alternatives passent près de signalements.",
        "Les pourcentages secteur « terrain » ne reflètent que les signalements validés (V), "
        "pas les signalements en attente.",
        "La grille ML peut sous-estimer un point isolé si le modèle généralise « faible » "
        "— d'où la priorité aux stats terrain dans les secteurs peuplés de signalements.",
        "Performance : grille 48×48 ≈ 2 300 inférences ; timeout API recommandé 90 s.",
    ]
