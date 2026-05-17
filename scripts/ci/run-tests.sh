#!/usr/bin/env bash
set -euo pipefail

python -m pytest -q
python -m pytest apps/api/tests/test_protocol_contract.py --collect-only -q

