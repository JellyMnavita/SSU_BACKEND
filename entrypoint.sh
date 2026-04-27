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

echo "Collecte des fichiers statiques..."
python manage.py collectstatic --noinput || true

echo "Démarrage de l'application..."
exec "$@"
