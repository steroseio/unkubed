#!/usr/bin/env bash
set -euo pipefail

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is required to start Postgres."
  exit 1
fi

echo "Starting Postgres via Docker Compose..."
docker compose up postgres -d
