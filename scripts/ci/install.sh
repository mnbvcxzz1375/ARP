#!/usr/bin/env bash
set -euo pipefail

python -m pip install --upgrade pip
python -m pip install -e "apps/api[test]"
python -m pip install -e "packages/python-sdk"
python -m pip install -e "packages/cli"
python -m pip install -e "adapters/base"
python -m pip install -e "adapters/openclaw"

