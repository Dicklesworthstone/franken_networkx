#!/usr/bin/env python3
"""Archive perf baseline event runs into a history JSONL ledger."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def iter_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rows.append(json.loads(line))
    return rows


def event_fingerprint(payload: dict) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--events",
        default="artifacts/perf/phase2c/perf_baseline_matrix_events_v1.jsonl",
    )
    parser.add_argument(
        "--matrix",
        default="artifacts/perf/phase2c/perf_baseline_matrix_v1.json",
    )
    parser.add_argument(
        "--history",
        default="artifacts/perf/history/perf_baseline_run_history_v1.jsonl",
    )
    args = parser.parse_args()

    events_path = Path(args.events)
    matrix_path = Path(args.matrix)
    history_path = Path(args.history)

    if not events_path.exists():
        raise SystemExit(f"missing events file: {events_path}")
    if not matrix_path.exists():
        raise SystemExit(f"missing matrix file: {matrix_path}")

    matrix = load_json(matrix_path)
    events = iter_jsonl(events_path)

    history_path.parent.mkdir(parents=True, exist_ok=True)
    existing = iter_jsonl(history_path)
    seen = {row.get("event_fingerprint") for row in existing if row.get("event_fingerprint")}

    appended = 0
    now = datetime.now(timezone.utc).isoformat()
    with history_path.open("a", encoding="utf-8") as handle:
        for event in events:
            payload = {
                "archived_at_utc": now,
                "source_events_path": str(events_path),
                "matrix_id": matrix.get("matrix_id"),
                "environment_fingerprint": matrix.get("environment_fingerprint"),
                "event": event,
            }
            fingerprint = event_fingerprint(payload)
            if fingerprint in seen:
                continue
            payload["event_fingerprint"] = fingerprint
            handle.write(json.dumps(payload) + "\n")
            seen.add(fingerprint)
            appended += 1

    total = len(seen)
    print(f"perf_history:{history_path}")
    print(f"perf_history_appended:{appended}")
    print(f"perf_history_total:{total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
