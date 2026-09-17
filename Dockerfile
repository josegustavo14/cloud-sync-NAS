FROM node:22-bookworm-slim AS web
WORKDIR /web
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM rclone/rclone:1.70.3 AS rclone
FROM python:3.12-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 1000 cloudsync && useradd --uid 1000 --gid 1000 --create-home cloudsync
WORKDIR /app
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY --from=rclone /usr/local/bin/rclone /usr/local/bin/rclone
COPY backend/app ./app
COPY --from=web /web/dist ./web
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PCS_ROOT=/DATA/CloudSync PCS_SOURCE_ROOT=/sources
RUN mkdir -p /DATA/CloudSync /sources && chown cloudsync:cloudsync /DATA/CloudSync
USER cloudsync
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health',timeout=4)"
CMD ["python", "-m", "app.entrypoint"]
