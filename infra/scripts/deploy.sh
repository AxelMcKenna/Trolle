#!/usr/bin/env bash
set -euo pipefail

COMPOSE_FILE="infra/docker-compose.prod.yml"

# Ensure we're in the repo root
cd "$(git rev-parse --show-toplevel)"

echo "==> Pulling latest images..."
docker compose -f "$COMPOSE_FILE" pull

echo "==> Running database migrations..."
docker compose -f "$COMPOSE_FILE" run --rm api poetry run alembic upgrade head

echo "==> Starting services..."
docker compose -f "$COMPOSE_FILE" up -d --remove-orphans

echo "==> Waiting for API health check..."
for i in $(seq 1 30); do
    if docker compose -f "$COMPOSE_FILE" exec -T api curl -sf http://localhost:8000/health > /dev/null 2>&1; then
        echo "==> API is healthy!"
        docker compose -f "$COMPOSE_FILE" ps
        exit 0
    fi
    sleep 2
done

echo "==> ERROR: API did not become healthy within 60 seconds"
docker compose -f "$COMPOSE_FILE" logs --tail=50 api
exit 1
