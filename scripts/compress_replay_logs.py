#!/usr/bin/env python3
"""Compress structured replay logs with count-min sketch + reservoir sampling."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from datetime import datetime, timezone
from pathlib import Path


def event_key(row: dict) -> str:
    if isinstance(row.get("event"), str):
        return row["event"]
    if isinstance(row.get("event"), dict):
        event = row["event"]
        for field in ("event", "name", "operation", "kind", "id"):
            value = event.get(field)
            if value is not None:
                return str(value)
    for field in ("event", "event_name", "operation", "kind", "id"):
        value = row.get(field)
        if value is not None:
            return str(value)
    return "unknown"


def hash_index(key: str, seed: int, width: int) -> int:
    payload = f"{seed}:{key}".encode("utf-8")
    digest = hashlib.blake2b(payload, digest_size=8).digest()
    return int.from_bytes(digest, "little") % width


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        default="artifacts/conformance/latest/structured_logs.jsonl",
    )
    parser.add_argument(
        "--output",
        default="artifacts/conformance/latest/structured_logs_compressed_v1.json",
    )
    parser.add_argument("--reservoir-size", type=int, default=200)
    parser.add_argument("--sketch-width", type=int, default=2048)
    parser.add_argument("--sketch-depth", type=int, default=4)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        raise SystemExit(f"missing input log: {input_path}")

    width = max(1, int(args.sketch_width))
    depth = max(1, int(args.sketch_depth))
    reservoir_size = max(1, int(args.reservoir_size))

    sketch = [[0] * width for _ in range(depth)]
    rng = random.Random(args.seed)
    reservoir: list[dict] = []

    total_events = 0
    with input_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            total_events += 1
            key = event_key(row)
            for i in range(depth):
                idx = hash_index(key, args.seed + i, width)
                sketch[i][idx] += 1

            if len(reservoir) < reservoir_size:
                reservoir.append(row)
            else:
                j = rng.randint(1, total_events)
                if j <= reservoir_size:
                    reservoir[j - 1] = row

    payload = {
        "schema_version": "1.0.0",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "input_path": str(input_path),
        "event_count": total_events,
        "sketch": {
            "width": width,
            "depth": depth,
            "seed": args.seed,
            "table": sketch,
        },
        "reservoir": {
            "size": reservoir_size,
            "sample": reservoir,
        },
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"compressed_replay_log:{output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
