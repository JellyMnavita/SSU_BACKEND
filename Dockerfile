# syntax=docker/dockerfile:1.7
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
ENV PIP_DEFAULT_TIMEOUT=300
ENV PIP_RETRIES=10

WORKDIR /app

# Dépendances système : PostgreSQL client + compilation psycopg2 / wheels géo
RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client \
    libpq-dev \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

COPY ssu_backend/requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip setuptools wheel \
    && pip install -r requirements.txt

COPY nlp_shared /app/nlp_shared
COPY prediction_shared /app/prediction_shared
COPY ssu_backend /app

COPY ssu_backend/entrypoint.sh /entrypoint.sh
COPY ssu_backend/worker-entrypoint.sh /worker-entrypoint.sh
RUN chmod +x /entrypoint.sh /worker-entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
CMD ["gunicorn", "ssu_backend.wsgi:application", "--bind", "0.0.0.0:8000"]
