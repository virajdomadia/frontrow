"""Dump the OpenAPI document to `api/openapi.json` — the committed contract (05 §2).

    uv run python -m app.openapi

`web/src/lib/api-types.ts` is generated from it by `pnpm gen:api` (in web/), which runs this
first. Committed, not CI-gated (lean rules).
"""

import json
import sys
from pathlib import Path
from typing import Any

from app.main import create_app

OPENAPI_PATH = Path(__file__).resolve().parents[1] / "openapi.json"


def build_document() -> dict[str, Any]:
    return create_app().openapi()


def render_document() -> str:
    return json.dumps(build_document(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def write_document(path: Path = OPENAPI_PATH) -> Path:
    path.write_text(render_document(), encoding="utf-8", newline="\n")
    return path


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else OPENAPI_PATH
    print(f"wrote {write_document(target)}")
