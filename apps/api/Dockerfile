FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_HOME=/app \
    SCHEMAS_DIR=/schemas

WORKDIR /app

RUN useradd --create-home --uid 10001 contabil

COPY apps/api /app
COPY schemas /schemas
COPY configs /configs

RUN pip install --no-cache-dir ".[dev]" \
    && chown -R contabil:contabil /app

USER contabil

EXPOSE 8000

CMD ["uvicorn", "contabil.main:app", "--host", "0.0.0.0", "--port", "8000"]
