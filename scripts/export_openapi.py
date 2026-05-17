"""Export and verify the AgentNet OpenAPI contract.

The script intentionally imports the FastAPI app directly instead of calling a
running server, so the exported contract is deterministic and CI-friendly.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
API_ROOT = REPO_ROOT / "apps" / "api"
DEFAULT_JSON_PATH = REPO_ROOT / "packages" / "protocol" / "openapi" / "agentnet.openapi.json"
DEFAULT_YAML_PATH = REPO_ROOT / "packages" / "protocol" / "openapi" / "agentnet.openapi.yaml"


def _load_openapi_schema() -> dict[str, Any]:
    sys.path.insert(0, str(API_ROOT))
    from app.main import app

    schema = app.openapi()
    schema.setdefault("info", {})
    schema["info"].setdefault("description", "AgentNet Agent Relay Platform REST and WebSocket API.")
    schema["info"].setdefault("version", "0.1.0")
    schema.setdefault("servers", [{"url": "http://localhost:8000", "description": "Local development"}])
    return schema


def _render_json(schema: dict[str, Any]) -> str:
    return json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _render_yaml(schema: dict[str, Any]) -> str:
    try:
        import yaml
    except ImportError as exc:
        raise SystemExit(
            "PyYAML is required for YAML export. Install with: "
            "python -m pip install -e apps/api[test]"
        ) from exc

    return yaml.safe_dump(schema, allow_unicode=True, sort_keys=False)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _check(path: Path, expected: str) -> bool:
    if not path.exists():
        print(f"Missing OpenAPI artifact: {path.relative_to(REPO_ROOT)}", file=sys.stderr)
        return False
    actual = path.read_text(encoding="utf-8")
    if actual != expected:
        print(f"OpenAPI artifact is out of date: {path.relative_to(REPO_ROOT)}", file=sys.stderr)
        return False
    return True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export AgentNet OpenAPI artifacts.")
    parser.add_argument(
        "--yaml",
        action="store_true",
        help="Export YAML instead of JSON. With --check, check only the YAML artifact.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check generated content against committed artifacts. Without --yaml, checks JSON and YAML.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional output path for non-check export.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    schema = _load_openapi_schema()
    json_content = _render_json(schema)

    if args.check:
        if args.output is not None:
            expected = _render_yaml(schema) if args.yaml else json_content
            return 0 if _check(args.output, expected) else 1
        checks: list[bool]
        if args.yaml:
            checks = [_check(DEFAULT_YAML_PATH, _render_yaml(schema))]
        else:
            checks = [
                _check(DEFAULT_JSON_PATH, json_content),
                _check(DEFAULT_YAML_PATH, _render_yaml(schema)),
            ]
        return 0 if all(checks) else 1

    if args.yaml:
        output_path = args.output or DEFAULT_YAML_PATH
        _write(output_path, _render_yaml(schema))
    else:
        output_path = args.output or DEFAULT_JSON_PATH
        _write(output_path, json_content)

    print(f"Wrote {output_path.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
