# Migrations base de données — SSU Backend

Guide pour appliquer les migrations **PostgreSQL** (Django) du backend, y compris les nouveautés **anti-enlèvement** (app `safety`, champs étendus sur `Report`).

---

## Migrations récentes (sécurité personnelle)

| App | Fichier | Contenu |
|-----|---------|---------|
| `reports` | `0009_report_safety_fields.py` | `incident_type`, véhicule, direction, plaque, témoin, anonymat, sources O/Q/W (+ U/C/S/A existants), photo nullable |
| `safety` | `0001_initial.py` | `TrustedContact`, `TrackingSession`, `TrackingPoint`, `Trip`, `CheckIn` |

**Ordre d’application** : `reports` (0009) **puis** `safety` (0001).

---

## Option A — Docker (recommandé)

Les migrations sont **lancées automatiquement** au démarrage du conteneur `web` (`entrypoint.sh` → `python manage.py migrate --noinput`).

### Premier lancement ou après `git pull`

```bash
# À la racine du monorepo « Ssu Bokengi »
cd "Ssu Bokengi"

docker compose up --build -d
```

### Appliquer manuellement (sans redémarrer tout)

```bash
docker compose exec web python manage.py migrate
```

### Appliquer une app précise

```bash
docker compose exec web python manage.py migrate reports
docker compose exec web python manage.py migrate safety
```

### Vérifier l’état des migrations

```bash
# Liste des migrations appliquées / en attente
docker compose exec web python manage.py showmigrations

# Uniquement reports et safety
docker compose exec web python manage.py showmigrations reports safety
```

Résultat attendu (extrait) :

```
reports
 ...
 [X] 0009_report_safety_fields
safety
 [X] 0001_initial
```

### Voir le SQL sans l’exécuter (debug)

```bash
docker compose exec web python manage.py sqlmigrate reports 0009
docker compose exec web python manage.py sqlmigrate safety 0001
```

---

## Option B — Environnement local (venv)

### Prérequis

1. PostgreSQL accessible (local ou Docker avec port `5432` exposé).
2. Fichier `ssu_backend/.env` configuré :

```env
DB_NAME=ssu_db
DB_USER=postgres
DB_PASSWORD=postgres
DB_HOST=127.0.0.1
DB_PORT=5432
```

3. Environnement virtuel activé et dépendances installées :

```powershell
cd ssu_backend
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Appliquer toutes les migrations

```powershell
python manage.py migrate
```

### Appliquer par app

```powershell
python manage.py migrate reports
python manage.py migrate safety
```

### Vérification

```powershell
python manage.py showmigrations reports safety
python manage.py check
```

---

## Créer de nouvelles migrations (développeurs)

Après modification d’un `models.py` :

```bash
# Docker
docker compose exec web python manage.py makemigrations reports safety

# Local
python manage.py makemigrations reports safety
```

Puis appliquer :

```bash
docker compose exec web python manage.py migrate
# ou
python manage.py migrate
```

---

## Dépannage

### `ModuleNotFoundError: No module named 'httpx'`

```powershell
pip install httpx
# ou
docker compose exec web pip install httpx
```

### `django.db.utils.ProgrammingError: relation already exists`

La table existe mais la migration n’est pas marquée comme appliquée. À utiliser **avec prudence** :

```bash
docker compose exec web python manage.py migrate reports 0009 --fake
docker compose exec web python manage.py migrate safety 0001 --fake
```

### Reset complet de la base (dev uniquement)

```bash
docker compose down -v
docker compose up --build -d
```

Cela supprime le volume PostgreSQL et recrée la base depuis zéro (migrations + seeders si `AUTO_SEED=1`).

### Contrainte `valid_source_combination` en échec

Les signalements SOS / Quick / Witness exigent un **utilisateur connecté** (`user_id` non null). Lors des imports manuels ou seeders, respecter les sources :

| Code | Signification | Règle |
|------|---------------|-------|
| `U` | User (compte connecté) | `user` requis |
| `C` | Citizen (anonyme web) | `citizen` requis |
| `S` | System (scraping / auto) | pas de `user` ni `citizen` |
| `A` | Admin | pas de `user` ni `citizen` |
| `O`, `Q`, `W` | SOS / Quick / Witness (mobile) | `user` requis |

---

## Référence — codes `source` du modèle `Report`

| Code | Libellé | Origine | Règle DB |
|------|---------|---------|----------|
| **U** | User | Utilisateur connecté (web ou mobile, formulaire classique) | `user` requis |
| **C** | Citizen | Citoyen anonyme (formulaire web sans compte) | `citizen` requis |
| **S** | System | Signalements **automatiques** (scraping actualités, ingestion IA) | pas de `user` ni `citizen` |
| **A** | Admin | Création manuelle par un administrateur | pas de `user` ni `citizen` |
| **O** | SOS | Bouton SOS mobile Bokengi | `user` requis |
| **Q** | Quick | Double appui volume (mobile) | `user` requis |
| **W** | Witness | Signalement témoin (mobile) | `user` requis |

**S** est le code historique des signalements générés par le pipeline **actualités / scraping** (`source=S` dans les seeders et Celery). Il ne correspond pas à une action utilisateur sur mobile.

---

## App mobile Bokengi (SQLite)

L’app Flutter **n’utilise pas** `manage.py migrate`. La base locale `bokengi.db` est migrée **automatiquement** au lancement (version schéma **v3** dans `DatabaseHelper`).

| Version | Contenu |
|---------|---------|
| v2 | Photo de profil |
| v3 | Champs report anti-enlèvement + tables `trusted_contacts`, `tracking_*`, `trips`, `check_ins` |

Pour forcer une réinstallation propre en dev : désinstaller l’app ou supprimer les données de l’application sur l’appareil/émulateur.

La **synchronisation** vers PostgreSQL se fera via `POST /api/safety/sync/batch/` une fois le client mobile branché au backend.

---

## Liens utiles

- [README.md](./README.md) — configuration Docker générale
- [../DOCKER.md](../DOCKER.md) — orchestration complète du monorepo
- [SEEDERS.md](./SEEDERS.md) — données initiales après migration
