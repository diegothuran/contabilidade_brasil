FROM node:22-alpine AS web
WORKDIR /src
COPY apps/web/ ./
ARG VITE_OIDC_AUTHORITY
ARG VITE_OIDC_CLIENT_ID
ARG VITE_OIDC_LOGOUT_URL=
ENV VITE_OIDC_AUTHORITY=$VITE_OIDC_AUTHORITY \
    VITE_OIDC_CLIENT_ID=$VITE_OIDC_CLIENT_ID \
    VITE_OIDC_USE_ID_TOKEN=1 \
    VITE_OIDC_LOGOUT_URL=$VITE_OIDC_LOGOUT_URL \
    VITE_API_URL=
RUN npm install && npm run build

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_HOME=/app \
    SCHEMAS_DIR=/schemas \
    STATIC_DIR=/app/static \
    OUTBOX_IN_PROCESS=1

WORKDIR /app

RUN useradd --create-home --uid 10001 contabil

COPY apps/api /app
COPY schemas /schemas
COPY configs /configs
COPY --from=web /src/dist /app/static

RUN pip install --no-cache-dir ".[dev]" \
    && chown -R contabil:contabil /app

USER contabil

CMD ["sh", "-c", "uvicorn contabil.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
