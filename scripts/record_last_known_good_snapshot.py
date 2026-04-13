#!/usr/bin/env python3
"""Record last-known-good snapshot metadata after CI gates succeed."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path


def main() -> int:
    output_dir = Path("artifacts/last_known_good")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "last_known_good_snapshot_v1.json"

    payload = {
        "schema_version": "1.0.0",
        "snapshot_id": f"lkg-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "git": {
            "sha": os.environ.get("GITHUB_SHA"),
            "ref": os.environ.get("GITHUB_REF"),
            "run_id": os.environ.get("GITHUB_RUN_ID"),
            "run_number": os.environ.get("GITHUB_RUN_NUMBER"),
        },
        "artifacts": {
            "conformance": "artifacts/conformance/latest",
            "performance": "artifacts/perf/latest",
        },
        "gates": [
            "g1-format",
            "g2-clippy",
            "g3-rust-tests",
            "g4-python-tests",
            "g4b-e2e",
            "g4c-docs",
            "g4d-examples",
            "g5-conformance",
            "g6-performance",
            "g7-ubs",
            "g7b-fuzz-smoke",
            "g8-raptorq",
        ],
    }

    output_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"last_known_good_snapshot:{output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
