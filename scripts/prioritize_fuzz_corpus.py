#!/usr/bin/env python3
"""Rank fuzz corpus entries by information-theoretic entropy."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


def shannon_entropy(data: bytes) -> float:
    if not data:
        return 0.0
    counts = [0] * 256
    for byte in data:
        counts[byte] += 1
    total = len(data)
    entropy = 0.0
    for count in counts:
        if count == 0:
            continue
        p = count / total
        entropy -= p * math.log2(p)
    return entropy


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", default="fuzz/corpus")
    parser.add_argument("--output", default="artifacts/fuzz/prioritized_corpus_v1.json")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    corpus_dir = Path(args.corpus)
    if not corpus_dir.exists():
        raise SystemExit(f"missing corpus directory: {corpus_dir}")

    entries = []
    for path in sorted(corpus_dir.rglob("*")):
        if not path.is_file():
            continue
        data = path.read_bytes()
        entries.append(
            {
                "path": str(path),
                "size_bytes": len(data),
                "entropy_bits": round(shannon_entropy(data), 6),
            }
        )

    entries.sort(key=lambda row: (row["entropy_bits"], row["size_bytes"]), reverse=True)
    if args.limit and args.limit > 0:
        entries = entries[: args.limit]

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "1.0.0",
        "corpus_root": str(corpus_dir),
        "entry_count": len(entries),
        "entries": entries,
    }
    output_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"fuzz_prioritization_report:{output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
