#!/bin/bash
set -e

echo "Attente de la base de donnees PostgreSQL..."

python <<'EOF'
import os
import socket
import sys
from time import sleep

import psycopg2

db_max_retries = 30
db_retry_count = 0

while db_retry_count < db_max_retries:
    try:
        conn = psycopg2.connect(
            dbname=os.getenv("DB_NAME", "ssu_db"),
            user=os.getenv("DB_USER", "postgres"),
            password=os.getenv("DB_PASSWORD", "postgres"),
            host=os.getenv("DB_HOST", "db"),
            port=os.getenv("DB_PORT", "5432"),
        )
        conn.close()
        print("PostgreSQL est pret!")
        break
    except psycopg2.OperationalError as exc:
        db_retry_count += 1
        if db_retry_count >= db_max_retries:
            print(
                f"Erreur: PostgreSQL n'est pas disponible apres {db_max_retries} tentatives"
            )
            print(f"Derniere erreur: {exc}")
            sys.exit(1)
        print(f"Tentative PostgreSQL {db_retry_count}/{db_max_retries}...")
        sleep(2)

web_host = os.getenv("WEB_HOST", "web")
web_port = int(os.getenv("WEB_PORT", "8000"))
web_max_retries = 60
web_retry_count = 0

print(f"Attente de l'application Django sur {web_host}:{web_port}...")

while web_retry_count < web_max_retries:
    try:
        with socket.create_connection((web_host, web_port), timeout=5):
            print("Application Django disponible!")
            sys.exit(0)
    except OSError as exc:
        web_retry_count += 1
        if web_retry_count >= web_max_retries:
            print(
                f"Erreur: l'application Django n'est pas disponible apres {web_max_retries} tentatives"
            )
            print(f"Derniere erreur: {exc}")
            sys.exit(1)
        print(f"Tentative Django {web_retry_count}/{web_max_retries}...")
        sleep(2)
EOF

echo "Demarrage du service worker..."
exec "$@"
