FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_HOME=/app \
    SCHEMAS_DIR=/schemas \
    OUTBOX_IN_PROCESS=1

WORKDIR /app

# O release do Heroku só executa o comando de migração se a imagem tiver curl.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --uid 10001 contabil

COPY apps/api /app
COPY schemas /schemas
COPY configs /configs

RUN pip install --no-cache-dir ".[dev]" \
    && sed -i 's/\r$//' /app/bin/migrate.sh \
    && chmod +x /app/bin/migrate.sh \
    && chown -R contabil:contabil /app

USER contabil

CMD ["sh", "-c", "uvicorn contabil.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
