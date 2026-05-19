#!/bin/bash
set -e

echo "Attente de la base de données PostgreSQL..."

# Attendre que PostgreSQL soit prêt
python << EOF
import sys
import psycopg2
import os
from time import sleep

max_retries = 30
retry_count = 0

while retry_count < max_retries:
    try:
        conn = psycopg2.connect(
            dbname=os.getenv('DB_NAME', 'ssu_db'),
            user=os.getenv('DB_USER', 'postgres'),
            password=os.getenv('DB_PASSWORD', 'postgres'),
            host=os.getenv('DB_HOST', 'db'),
            port=os.getenv('DB_PORT', '5432')
        )
        conn.close()
        print('PostgreSQL est prêt!')
        sys.exit(0)
    except psycopg2.OperationalError as e:
        retry_count += 1
        if retry_count >= max_retries:
            print(f'Erreur: PostgreSQL n\'est pas disponible après {max_retries} tentatives')
            print(f'Dernière erreur: {e}')
            sys.exit(1)
        print(f'Tentative {retry_count}/{max_retries}...')
        sleep(2)
EOF

echo "Exécution des migrations..."
python manage.py migrate --noinput

# Seeders au démarrage du conteneur (pas au build : la DB n'existe pas encore).
# AUTO_SEED=0 pour désactiver (ex. prod avec données déjà injectées).
if [ "${AUTO_SEED:-1}" = "1" ]; then
    echo "Exécution des seeders (AUTO_SEED=1)..."
    python manage.py seed_users
    python manage.py seed_quartiers
    # seed_signalements duplique les lignes CSV à chaque run : uniquement si base vide (source=S).
    SIG_COUNT="$(python -c "
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ssu_backend.settings')
django.setup()
from reports.models import Report
print(Report.objects.filter(source='S').count())
" | tr -d '[:space:]')"
    if [ "${SIG_COUNT:-999}" -eq 0 ]; then
        echo "Import des signalements (aucun source=S en base)..."
        python manage.py seed_signalements
    else
        echo "seed_signalements ignoré (${SIG_COUNT} signalement(s) source=S déjà en base)."
    fi
else
    echo "AUTO_SEED=0 : seeders non exécutés."
fi

echo "Collecte des fichiers statiques..."
python manage.py collectstatic --noinput || true

echo "Démarrage de l'application..."
exec "$@"
