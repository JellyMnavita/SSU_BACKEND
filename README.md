# SSU_BACKEND

## Configuration Docker

Ce projet est configuré pour fonctionner avec Docker Compose, incluant PostgreSQL, Redis, Django, Celery et Celery Beat.

### Prérequis

- Docker
- Docker Compose

### Configuration

1. Créez un fichier `.env` à la racine du projet avec les variables d'environnement suivantes :

```env
SECRET_KEY=your-secret-key-here
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Database Configuration
DB_NAME=ssu_db
DB_USER=postgres
DB_PASSWORD=postgres
DB_HOST=db
DB_PORT=5432

# Redis Configuration
REDIS_HOST=redis
REDIS_PORT=6379

# Celery Configuration
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0

# Email Configuration
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
SUPPORT_EMAIL=support@example.com

# Frontend URL
FRONTEND_URL=http://localhost:5173

# CORS Configuration
CORS_ALLOWED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

**Note importante** : Dans Docker, utilisez `db` comme `DB_HOST` et `redis` comme `REDIS_HOST` (noms des services Docker).

### Démarrage

Pour démarrer tous les services :

```bash
docker-compose up --build
```

Pour démarrer en arrière-plan :

```bash
docker-compose up -d --build
```

### Services disponibles

- **Web** : Application Django sur `http://localhost:8000`
- **PostgreSQL** : Base de données sur le port `5432`
- **Redis** : Cache et broker Celery sur le port `6379`
- **Celery Worker** : Traitement des tâches asynchrones
- **Celery Beat** : Planificateur de tâches périodiques

### Commandes utiles

Arrêter les services :
```bash
docker-compose down
```

Voir les logs :
```bash
docker-compose logs -f
```

### Exécuter des commandes Django

Toutes les commandes Django doivent être exécutées dans le conteneur `web` :

**Créer un superutilisateur :**
```bash
docker-compose exec web python manage.py createsuperuser
```

**Créer des migrations :**
```bash
docker-compose exec web python manage.py makemigrations
```

**Appliquer les migrations :**
```bash
docker-compose exec web python manage.py migrate
```

**Collecter les fichiers statiques :**
```bash
docker-compose exec web python manage.py collectstatic
```

**Accéder au shell Django :**
```bash
docker-compose exec web python manage.py shell
```

**Voir les logs de l'application :**
```bash
docker-compose logs web
```

**Autres commandes Django :**
Remplacez simplement `python manage.py [commande]` par :
```bash
docker-compose exec web python manage.py [votre-commande]
```

### Accéder à la base de données PostgreSQL

#### Option 1 : Via la ligne de commande (psql)

```bash
docker-compose exec db psql -U postgres -d ssu_db
```

Une fois connecté, vous pouvez exécuter des commandes SQL :
```sql
-- Lister toutes les tables
\dt

-- Voir le contenu d'une table
SELECT * FROM users_user;

-- Quitter
\q
```

#### Option 2 : Via un client graphique (recommandé)

Vous pouvez utiliser des outils comme **pgAdmin**, **DBeaver**, **TablePlus**, ou **DataGrip**.

**Configuration de connexion :**
- **Host** : `localhost` (ou `127.0.0.1`)
- **Port** : `5432`
- **Database** : `ssu_db` (ou la valeur de `DB_NAME` dans votre `.env`)
- **Username** : `postgres` (ou la valeur de `DB_USER` dans votre `.env`)
- **Password** : `postgres` (ou la valeur de `DB_PASSWORD` dans votre `.env`)

**Exemple avec DBeaver (gratuit) :**
1. Téléchargez DBeaver : https://dbeaver.io/
2. Créez une nouvelle connexion PostgreSQL
3. Utilisez les paramètres ci-dessus
4. Testez la connexion et connectez-vous

**Exemple avec pgAdmin :**
1. Téléchargez pgAdmin : https://www.pgadmin.org/
2. Ajoutez un nouveau serveur avec les paramètres ci-dessus

### Volumes persistants

Les données sont stockées dans des volumes Docker :
- `postgres_data` : Données PostgreSQL
- `static_volume` : Fichiers statiques Django
- `media_volume` : Fichiers média uploadés

Pour supprimer tous les volumes (⚠️ supprime les données) :
```bash
docker-compose down -v
```

### Dépannage

#### Erreur "The 'q65' variable is not set"

Cette erreur indique qu'une variable mal formée est présente dans votre fichier `.env`. Pour résoudre :

1. Ouvrez votre fichier `.env`
2. Recherchez toute ligne contenant `q65` ou des caractères étranges
3. Vérifiez que chaque ligne suit le format : `NOM_VARIABLE=valeur`
4. Assurez-vous qu'il n'y a pas d'espaces autour du `=`
5. Vérifiez qu'il n'y a pas de caractères spéciaux non échappés

Exemple de format correct :
```env
DB_NAME=ssu_db
DB_USER=postgres
```

#### Conteneur PostgreSQL "unhealthy"

Si PostgreSQL est marqué comme "unhealthy" :

1. Vérifiez les logs : `docker-compose logs db`
2. Assurez-vous que les variables `DB_USER`, `DB_PASSWORD`, et `DB_NAME` sont définies dans votre `.env`
3. Redémarrez les services : `docker-compose down && docker-compose up --build`

#### Problèmes de connexion réseau entre conteneurs

Assurez-vous que dans votre `.env`, vous utilisez :
- `DB_HOST=db` (pas `localhost` ou `127.0.0.1`)
- `REDIS_HOST=redis` (pas `localhost` ou `127.0.0.1`)