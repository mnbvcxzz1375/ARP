"""Root conftest for monorepo-wide pytest collection.

Adds each sub-project's source root to sys.path so that tests can import
their local packages (e.g. `from app.main import app`) regardless of
which directory pytest was invoked from.
"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent

_SUBPROJECT_ROOTS = [
    _ROOT / "apps" / "api",
    _ROOT / "packages" / "python-sdk",
    _ROOT / "packages" / "cli",
    _ROOT / "adapters" / "base",
    _ROOT / "adapters" / "openclaw",
]

for p in _SUBPROJECT_ROOTS:
    sp = str(p)
    if sp not in sys.path:
        sys.path.insert(0, sp)
