#!/usr/bin/env bash
set -euo pipefail

python -m compileall \
  adapters/openclaw/agentnet_openclaw \
  packages/python-sdk/agentnet \
  packages/cli/agentnet_cli \
  apps/api/app

