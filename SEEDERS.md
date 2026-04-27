# Documentation des Seeders — SSU Backend

## Vue d'ensemble

Les seeders sont des commandes Django (`manage.py`) qui permettent de pré-remplir la base de données avec des données initiales ou de test. Ils sont tous **idempotents** : les relancer plusieurs fois ne crée pas de doublons.

---

## 1. `seed_users` — Utilisateurs par type

**Fichier :** `users/management/commands/seed_users.py`

### Description
Crée un utilisateur de base pour chacun des 4 types du système, et s'assure que les `TypeUser` existent en base.

### Utilisation

```bash
# Créer les utilisateurs (ignore ceux qui existent déjà)
python manage.py seed_users

# Supprimer les utilisateurs seed puis les recréer
python manage.py seed_users --clear
```

### Utilisateurs créés

| Type | Username | Email | Mot de passe | is_staff |
|---|---|---|---|---|
| ADMIN | admin_ssu | admin@ssu.cd | Admin@ssu2025 | ✅ |
| GOV | gov_ssu | gouvernement@ssu.cd | Gov@ssu2025 | ❌ |
| COMPANY | company_ssu | entreprise@ssu.cd | Company@ssu2025 | ❌ |
| USER | user_ssu | utilisateur@ssu.cd | User@ssu2025 | ❌ |

### Comportement
- Crée les `TypeUser` (ADMIN, GOV, COMPANY, USER) s'ils n'existent pas
- Ignore silencieusement un utilisateur si son `username` existe déjà
- Tous les utilisateurs créés ont `is_verified=True` et `agreementTermsUse_user=True`
- `--clear` supprime uniquement les 4 usernames seed, pas les autres utilisateurs

### Options

| Option | Description |
|---|---|
| `--clear` | Supprime les utilisateurs seed avant de les recréer |

---

## 2. `seed_signalements` — Signalements depuis CSV

**Fichier :** `reports/management/commands/seed_signalements.py`

### Description
Importe les signalements réels depuis le fichier `prediction/data/data_reports.csv` dans la table `Report`. Chaque signalement importé a `source="S"` (System) pour le distinguer des vrais signalements.

### Utilisation

```bash
# Import depuis le chemin par défaut
python manage.py seed_signalements

# Supprimer les imports précédents puis réimporter
python manage.py seed_signalements --clear

# Spécifier un fichier CSV différent
python manage.py seed_signalements --csv /chemin/vers/fichier.csv
```

### Format CSV attendu

Le fichier CSV doit contenir au minimum les colonnes suivantes (les noms alternatifs sont aussi acceptés) :

| Colonne | Alias accepté | Obligatoire | Description |
|---|---|---|---|
| `latitude_report` | `latitude` | ✅ | Latitude du signalement |
| `longitude_report` | `longitude` | ✅ | Longitude du signalement |
| `degree` | `degree_report` | ❌ | Niveau de danger (voir tableau ci-dessous) |
| `description` | `description_report` | ❌ | Description du signalement |
| `location` | `adresse` | ❌ | Adresse lisible |
| `status` | — | ❌ | Statut du signalement |
| `quartier` | — | ❌ | Nom du quartier (doit exister en base) |

### Correspondances des valeurs

**Degree (niveau de danger) :**

| Valeur CSV | Valeur BDD | Libellé |
|---|---|---|
| `0` ou `F` ou `Faible` | `F` | Faible |
| `1` ou `M` ou `Moyen` | `M` | Moyen |
| `2` ou `E` ou `Elevé` | `E` | Elevé |

**Status :**

| Valeur CSV | Valeur BDD | Libellé |
|---|---|---|
| `P` ou `Pending` | `P` | En attente |
| `V` ou `Validated` | `V` | Validé |
| `R` ou `Rejected` | `R` | Rejeté |

### Comportement
- Les lignes avec coordonnées invalides ou `(0, 0)` sont ignorées
- Une image PNG factice 1×1 est assignée (le champ `picture` est obligatoire)
- Le quartier est résolu par nom (insensible à la casse) ; si non trouvé, il reste `null`
- `source="S"` est assigné à tous les signalements importés
- `--clear` supprime uniquement les signalements `source="S"`, pas les vrais signalements

### Options

| Option | Description |
|---|---|
| `--clear` | Supprime tous les signalements `source=S` avant d'importer |
| `--csv <chemin>` | Chemin vers le fichier CSV (défaut : `prediction/data/data_reports.csv`) |

---

## 3. `seed_quartiers` — Quartiers par commune

**Fichier :** `locations/management/commands/seed_quartiers.py`

### Description
Crée un quartier par défaut pour chaque commune qui n'en possède pas encore. Utile pour initialiser les communes vides après le seed des communes.

### Utilisation

```bash
# Créer un quartier "Non spécifié" pour chaque commune sans quartiers
python manage.py seed_quartiers

# Utiliser un nom personnalisé
python manage.py seed_quartiers --name "Centre"

# Forcer la création même si la commune a déjà des quartiers
python manage.py seed_quartiers --force
```

### Comportement
- Ignore les communes qui ont déjà au moins un quartier (sauf avec `--force`)
- Idempotent : ne crée pas de doublon `(commune, nom)`
- `limites_gps` est initialisé à `"[]"` (tableau vide)

### Options

| Option | Description |
|---|---|
| `--name <nom>` | Nom du quartier créé (défaut : `"Non spécifié"`) |
| `--force` | Crée le quartier même si la commune a déjà des quartiers |

---

## Ordre d'exécution recommandé

Pour initialiser une base de données vide, lancer les seeders dans cet ordre :

```bash
# 1. Types d'utilisateurs + utilisateurs de base
python manage.py seed_users

# 2. Quartiers par défaut pour les communes existantes
python manage.py seed_quartiers

# 3. Signalements depuis le CSV
python manage.py seed_signalements
```

Ou tout réinitialiser d'un coup :

```bash
python manage.py seed_users --clear
python manage.py seed_quartiers --force
python manage.py seed_signalements --clear
```

---

## Notes importantes

- Les seeders utilisent `@transaction.atomic` : en cas d'erreur, aucune donnée partielle n'est enregistrée
- Ne jamais utiliser `--clear` en production sur `seed_signalements` sans sauvegarde préalable
- Les mots de passe des utilisateurs seed doivent être changés avant tout déploiement en production
