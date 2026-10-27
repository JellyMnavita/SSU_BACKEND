# Prédiction de danger

Le récit complet (découpage, variables, comparaison de modèles, chiffres et limites) est dans le [README](../README.md) à la racine.

`prediction/training.py` appelle `prediction_shared/training.py` (dans ce dépôt) : nettoyage, splits stratifiés, features après le split, validation croisée, choix par F1 macro, fit final, écriture de `model/best_model.pkl` et `model/scaler.pkl`.

Les exports CSV, les splits et les poids ne sont pas versionnés. Commandes :

```bash
python manage.py export_reports_csv
python manage.py train_prediction_model
```

Les paquets `prediction_shared/` et `nlp_shared/` sont dans ce dépôt. L’image Docker est construite depuis le dossier parent, qui contient les mêmes dossiers.
