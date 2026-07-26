#!/usr/bin/env python3
"""Export the FastAPI OpenAPI schema to docs/openapi.yaml (+ .json).

The schema is built from the app object in-memory — no running server or DB
connection is needed (SQLAlchemy engines are lazy). Run in the dev env so the
production config validation in config.py is skipped:

    cd apps/api
    ENVIRONMENT=development .venv/bin/python scripts/export_openapi.py

Regenerate whenever routes/schemas change; commit docs/openapi.yaml as the
published API contract. The live, always-current schema is also at /openapi.json
(and Swagger UI at /docs).
"""
import json
import os
import sys
from pathlib import Path

# apps/api must be importable, and dev env avoids prod-config fail-fast.
API_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(API_DIR))
os.environ.setdefault("ENVIRONMENT", "development")

import yaml  # noqa: E402


def main() -> int:
    from main import app  # imported after env is set

    schema = app.openapi()

    # Repo root = apps/api/../.. ; write the contract under docs/.
    docs_dir = API_DIR.parent.parent / "docs"
    docs_dir.mkdir(exist_ok=True)

    yaml_path = docs_dir / "openapi.yaml"
    json_path = docs_dir / "openapi.json"

    yaml_path.write_text(
        yaml.safe_dump(schema, sort_keys=False, allow_unicode=True, width=100),
        encoding="utf-8",
    )
    json_path.write_text(json.dumps(schema, indent=2), encoding="utf-8")

    paths = len(schema.get("paths", {}))
    title = schema.get("info", {}).get("title", "?")
    version = schema.get("info", {}).get("version", "?")
    print(f"✅ {title} v{version} — {paths} paths")
    print(f"   → {yaml_path}")
    print(f"   → {json_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
