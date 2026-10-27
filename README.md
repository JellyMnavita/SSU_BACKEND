# SSU Bokengi — service backend

Service Django/DRF de **SSU Bokengi**, une plateforme de signalement et d’alerte de sécurité urbaine à Kinshasa. Les citoyens déposent un incident (texte, photo, position). Le backend qualifie ce signalement, puis estime un **degré de danger** (faible, modéré, élevé) sur une grille géographique.

Ce dépôt contient l’API, la fusion des modèles, le pipeline scikit-learn (`prediction_shared/`), le lexique NLP (`nlp_shared/`) et les métriques de la dernière expérience enregistrée. Les poids, les exports de signalements et les secrets ne sont pas versionnés.

## Ce que fait le système

1. Un signalement arrive avec une description, éventuellement une image, et des coordonnées.
2. Deux microservices spécialisés sont interrogés : un classifieur de texte (NLP) et un détecteur visuel.
3. Une **fusion pondérée** transforme ces sorties en un score de risque entre 0 et 1, puis en un degré F / M / E, et en une recommandation de modération : valider, rejeter ou laisser en revue humaine.
4. Les signalements validés alimentent un **classifieur géospatial** (scikit-learn). Il sert une carte de danger et des itinéraires.

Les services NLP et vision tournent à part et sont appelés en HTTP (`ai_gateway/`). L’entraînement tabulaire est dans `prediction_shared/training.py`, lancé par `prediction/training.py`. Le lexique et les filtres de texte sont dans `nlp_shared/`.

## Installation

Prérequis : Python 3.12, PostgreSQL, Redis.

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python manage.py migrate
python manage.py runserver
```

Sous Docker, le build part du dossier parent (il recopie ces deux paquets, déjà présents ici) :

```bash
docker compose up --build
```

L’API écoute sur `http://localhost:8000`. Les variables sont documentées dans `.env.example`. Ne commitez jamais un `.env` réel.

Entraîner le modèle de danger après un export des signalements validés :

```bash
python manage.py export_reports_csv
python manage.py train_prediction_model
```

Les artefacts écrits localement sont `prediction/model/best_model.pkl`, `prediction/model/scaler.pkl` et les JSON de `prediction/models/`.

## Apprentissage : prédire le degré de danger

### Question

À partir de signalements déjà validés, prédire le degré de danger d’un lieu à Kinshasa à un moment donné. Trois classes : `faible`, `modere`, `eleve`.

Le jeu est petit (quelques centaines de lignes) et déséquilibré. Le critère de sélection n’est donc pas l’accuracy, qui favorise la classe majoritaire, mais le **F1 macro** : la moyenne non pondérée des F1 par classe.

### Données et découpage

Les lignes viennent des signalements au statut validé, avec coordonnées dans l’emprise de Kinshasa. Un nettoyage retire les coordonnées invalides, les points hors bbox, les degrés illisibles et les doublons.

Le découpage est stratifié par classe, graine 42 :

| Jeu | Rôle | Contenu |
|-----|------|---------|
| train | ajuster les modèles | signalements réels restants + **tous** les exemples synthétiques |
| val | choisir les hyperparamètres via la validation croisée interne au train, puis réintégrer au fit final | réels seulement |
| test | estimation tenue à l’écart | réels seulement |
| gold | second jeu réel, jamais utilisé pour choisir le modèle | réels seulement |

Les exemples synthétiques (`source_report=synthetic`) n’entrent ni dans val, ni dans test, ni dans gold. Sinon un modèle pourrait paraître bon en reconnaissant des points générés par nos propres règles.

Proportions sur les réels : environ 15 % gold, puis 15 % validation, puis 15 % test sur le reste. Le fit final est fait sur **train + val**. Le test et le gold ne servent qu’au rapport.

### Variables

Le degré des voisins n’est pas une entrée. C’est la cible : l’utiliser (par exemple une moyenne des degrés dans un rayon) ferait fuiter l’étiquette.

Pour chaque point, un `BallTree` en distance haversine (rayon terrestre 6 371 km) calcule :

- `density_500m` : nombre de signalements dans un rayon de 500 m, comptage seul ;
- `nearest_neighbor_km` : distance au signalement le plus proche.

S’y ajoutent latitude, longitude, heure et jour. L’ingénierie est appliquée **après** le split, séparément sur chaque jeu :

- encodage cyclique de l’heure et du jour (`sin` / `cos`), pour que 23 h et 0 h restent voisines ;
- indicateurs nuit (22 h–5 h), week-end, soirée (18 h–22 h) ;
- `log(1 + densité)`, densité au carré, distance au centre de Kinshasa, proximité `1 / (1 + km)`.

Cela fait 17 variables. Elles sont standardisées (`StandardScaler` ajusté sur le jeu d’apprentissage seulement). Les corrélations feature–cible publiées dans le rapport sont calculées sur le train uniquement.

### Modèles comparés

Six candidats scikit-learn, graine 42, validation croisée stratifiée (au plus 5 plis, plafonnée par la classe la plus rare) :

| Modèle | Idée | Déséquilibre |
|--------|------|----------------|
| GradientBoosting | arbres séquentiels, `max_depth` faible | `sample_weight` par classe au fit final |
| HistGradientBoosting | même principe, histogrammes | recherche d’hyperparamètres |
| RandomForest | bagging | `class_weight="balanced"` |
| ExtraTrees | seuils aléatoires, moins de variance | `class_weight="balanced"` |
| LogisticRegression | baseline linéaire | `class_weight="balanced"` |
| SVM (RBF) | frontière non linéaire | `class_weight="balanced"`, `probability=True` |

`RandomizedSearchCV` (8 tirages au plus, score `f1_macro`) règle la profondeur, le learning rate, `C`, `gamma`, etc. Le gagnant est le meilleur F1 macro moyen en validation croisée. En cas d’égalité à 1e-6 près, l’accuracy puis l’ordre de déclaration départagent. Le modèle retenu est réentraîné sur train+val et sérialisé avec son scaler (`joblib`).

Gradient boosting est un bon candidat sur ce type de table (interactions lieu × heure × densité, peu de lignes, bruit de saisie), mais il n’est pas imposé : il ne reste que s’il gagne le F1 macro.

### Dernière expérience enregistrée

Fichier `prediction/models/training_summary.json`, entraînement du **4 octobre 2026**. 311 lignes conservées sur 312. Répartition : 150 faible, 84 modéré, 77 élevé. Découpage : train 191, val 40, test 33, gold 47. Ajustement final sur 231 lignes.

La classe « faible » représente 150/311 ≈ **48 %** des lignes. Un classifieur qui prédit toujours « faible » a donc une accuracy d’environ **0,48**, et un F1 macro d’environ **0,22** (F1 nul sur modéré et élevé). L’accuracy seule ne dit pas si le modèle voit les trois degrés. C’est pour cela que la sélection se fait sur le **F1 macro**, choisi avant de regarder les scores.

Validation croisée 5-fold sur le train :

| Modèle | Accuracy | F1 macro |
|--------|----------|----------|
| GradientBoosting (retenu) | 0,482 ± 0,050 | **0,438 ± 0,049** |
| RandomForest | 0,498 ± 0,077 | 0,433 ± 0,085 |
| HistGradientBoosting | 0,487 ± 0,057 | 0,428 ± 0,065 |
| SVM | 0,393 ± 0,057 | 0,387 ± 0,061 |
| LogisticRegression | 0,367 ± 0,058 | 0,370 ± 0,059 |

Les cinq modèles se tiennent. L’accuracy du boosting est au niveau de la baseline majoritaire : il ne « gagne » pas sur ce chiffre. Son F1 macro (0,44) vaut environ le double de cette baseline (0,22), avec un écart-type plus serré que la forêt. C’est le critère annoncé, donc c’est lui qui est retenu.

Lecture externe, même exécution :

| Jeu | Accuracy | F1 macro | Lecture |
|-----|----------|----------|---------|
| gold (n = 47) | 0,404 | 0,385 | au-dessus du F1 majoritaire (~0,22), accuracy proche de la baseline |
| test (n = 33) | 0,242 | 0,148 | un seul découpage, sous la baseline |

Le jeu **gold** est la lecture retenue : réels uniquement, jamais utilisés pour choisir le modèle, F1 macro 0,38. Le test de 33 lignes tombe sous la baseline. On le publie pour ne pas montrer seulement le meilleur découpage. Avec cette taille, un split ne suffit pas à estimer une performance de terrain. Le chiffre de travail reste le F1 macro de validation (0,44 ± 0,05) et sa confirmation partielle sur le gold (0,38).

Cet instantané utilisait encore `mean_neighbor_degree`. Cette variable a été retirée ensuite : elle réinjecte la cible. Les chiffres ci-dessus décrivent cette exécution. Le code actuel (`prediction_shared/features.py`) ne s’en sert plus. Le modèle sert une carte indicative, pas un score de risque calibré pour une décision automatique.

## Fusion NLP et vision

Fichier `ai_gateway/services/fusion.py`. Chaque modalité produit un risque = gravité du label × confiance du service.

Gravités texte : kidnapping 1,0, violence 0,95, agression 0,70, vol 0,55, vandalisme 0,50, autre 0,10. Gravités image : arme 1,0, incendie 0,95, accident 0,60, foule 0,50, véhicule suspect 0,45, autre 0,08. Une détection visuelle sous 0,20 de confiance est ignorée.

Le score fusionné est une moyenne pondérée : **0,62 NLP + 0,38 vision**. Si une modalité manque, son poids sort du dénominateur. Deux signaux au-dessus de 0,35 relèvent le score (× 1,12, plafond 0,98). Seuils de degré : élevé ≥ 0,65, modéré ≥ 0,35, sinon faible. Le degré recommandé ne descend pas en dessous du degré de la modalité la plus alarmée.

La modération (`moderation_from_fusion`) reste prudente :

- alerte SOS : validation système, hors de ce score ;
- texte trop pauvre, services en échec, ou score intermédiaire : revue humaine ;
- actualité scrapée sans marqueur d’incident local, ou contenu anodin : rejet ;
- score très bas et degré faible : rejet, sauf si le réglage désactive l’auto-rejet des signalements citoyens ;
- score haut et degré élevé, avec un signal crédible : validation.

Les seuils sont des choix de produit, pas des probabilités calibrées. Un lexique (règles) peut court-circuiter le modèle neuronal quand la formulation est explicite ; sa confiance n’est pas pénalisée.

## Fichiers à lire

| Fichier | Rôle |
|---------|------|
| `ai_gateway/services/fusion.py` | score, degré, décision valider / rejeter / attendre |
| `ai_gateway/services/report_enrichment.py` | appels NLP et vision, filtres d’actualité |
| `prediction_shared/training.py` | comparaison des 6 modèles, validation croisée, fit final |
| `prediction_shared/features.py` | variables géospatiales, sans le degré des voisins |
| `prediction_shared/dataset.py` | nettoyage et découpage train / val / test / gold |
| `nlp_shared/filters.py` | rejets anodins et actualités hors incident |
| `prediction/training.py` | point d’entrée Django du pipeline |
| `prediction/models/training_summary.json` | métriques de l’exécution du 4 octobre 2026 |
| `prediction/models/cv_results.json` | comparaison des modèles |

Dépendances d’apprentissage : `requirements.txt` (Django 5.1, djangorestframework, scikit-learn 1.5, pandas, numpy, geopandas).

## Ce qui est hors du dépôt

Ignorés volontairement (voir `.gitignore`) : `.env`, médias uploadés, `staticfiles/`, caches Python, exports CSV, jeux train/val/test, poids `.pkl`, et le GeoJSON volumineux `rdc_kin.json`. Ces fichiers se régénèrent en local ou restent sur la machine de développement. Le modèle `.env.example` liste les clés sans valeurs.
