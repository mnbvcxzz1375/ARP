#!/usr/bin/env bash
# Validate both compose contexts from the repository root:
#   1. dev  : infra/docker-compose.yml + infra/docker-compose.dev.yml
#   2. prod : infra/docker-compose.prod.yml
# `docker compose config` resolves build contexts relative to the compose file,
# so both invocations work from the repo root. When infra/.env.production
# exists, the prod context is validated with it so interpolation is checked
# against real values (an empty-string fallback makes postgres init fail).
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/../.."

docker compose -f infra/docker-compose.yml -f infra/docker-compose.dev.yml config -q

if [[ -f infra/.env.production ]]; then
  docker compose --env-file infra/.env.production -f infra/docker-compose.prod.yml config -q
else
  echo "check-compose: infra/.env.production not found — prod context validated without env interpolation" >&2
  docker compose -f infra/docker-compose.prod.yml config -q
fi
