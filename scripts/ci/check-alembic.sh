#!/usr/bin/env bash
set -euo pipefail

pushd apps/api >/dev/null
alembic upgrade head
alembic current
popd >/dev/null

