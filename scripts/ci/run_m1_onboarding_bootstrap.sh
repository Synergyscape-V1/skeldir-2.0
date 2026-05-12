#!/usr/bin/env bash
set -euo pipefail

if [ ! -f .env.local ]; then
  cp .env.local.example .env.local
fi

docker compose --env-file .env.local -f docker-compose.local.yml config >/tmp/skeldir-m1-compose-config.yml

make dev
make migrate
make api
make worker
make health
make smoke
