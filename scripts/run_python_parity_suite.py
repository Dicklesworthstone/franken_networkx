#!/usr/bin/env python3
"""Run the whole tests/python suite as guarded shards and fail on any red test.

Nothing ran the full suite before 2026-09-24; its first complete run found four
red tests, one of them red for eight days (hhj5p.2 / hhj5p.4). This is that run
as a gate (hhj5p.1): every test file, split into shards of explicit file lists
(never a bare sweep, AGENTS.md), each shard through scripts/run_pytest_guarded.sh
(address-space, RSS and wall-time limits), several shards at a time.

    scripts/run_python_parity_suite.py                    # 4 workers, ~25 min on an idle host
    scripts/run_python_parity_suite.py --workers 2 --files-per-shard 60
    scripts/run_python_parity_suite.py --json-out /path/summary.json

It refuses to start with less free disk than --min-free-gb: a shared /data that
fills mid-run makes every shard fail on ENOSPC and, for a detached run, every log
write fail too. Exit status is non-zero when any shard fails, errors or times out.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess  # nosec B404 - runs the repo's own guarded pytest wrapper
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUARDED = ROOT / "scripts" / "run_pytest_guarded.sh"
SUMMARY_RE = re.compile(r"(\d+) (passed|failed|errors?|skipped|xfailed|xpassed)")


def shard(files: list[str], per_shard: int) -> list[list[str]]:
    return [files[i : i + per_shard] for i in range(0, len(files), per_shard)]


def parse_summary(text: str) -> dict[str, int]:
    """Counts from pytest's final summary line ('3 failed, 10 passed in 1s')."""
    lines = [line for line in text.splitlines() if " in " in line and SUMMARY_RE.search(line)]
    counts = {"passed": 0, "failed": 0, "errors": 0, "skipped": 0, "xfailed": 0, "xpassed": 0}
    if not lines:
        return counts
    for number, word in SUMMARY_RE.findall(lines[-1]):
        counts["errors" if word.startswith("error") else word] += int(number)
    return counts


def run_shard(index: int, files: list[str], log_dir: Path, timeout: int) -> dict:
    log = log_dir / f"shard_{index:02d}.log"
    env = dict(os.environ, FNX_TEST_TIMEOUT_SECS=str(timeout))
    start = time.monotonic()
    with log.open("w", encoding="utf-8") as out:
        proc = subprocess.run(  # nosec B603
            [str(GUARDED), "-q", "-p", "no:cacheprovider", "--tb=line", "-rfE", *files],
            cwd=ROOT, env=env, stdout=out, stderr=subprocess.STDOUT, timeout=timeout + 300,
        )
    text = log.read_text(encoding="utf-8", errors="replace")
    counts = parse_summary(text)
    red = [line.split(" ", 1)[1] for line in text.splitlines() if line.startswith(("FAILED ", "ERROR "))]
    return {
        "shard": index,
        "files": len(files),
        "returncode": proc.returncode,
        "seconds": round(time.monotonic() - start, 1),
        "log": str(log),
        "red": red,
        **counts,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--files-per-shard", type=int, default=40)
    parser.add_argument("--shard-timeout", type=int, default=1800, help="seconds per shard")
    parser.add_argument("--min-free-gb", type=int, default=20)
    parser.add_argument("--test-dir", type=Path, default=ROOT / "tests" / "python",
                        help="directory whose test_*.py files are run (default: tests/python)")
    parser.add_argument("--log-dir", type=Path, help="default: a fresh directory under the system temp dir")
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args(argv)

    free_gb = shutil.disk_usage(ROOT).free // 1024**3
    if free_gb < args.min_free_gb:
        print(f"refusing to start: {free_gb} GB free on the repo's filesystem (< {args.min_free_gb})")
        return 2

    test_dir = args.test_dir.resolve()
    files = sorted(
        str(p.relative_to(ROOT)) if ROOT in p.parents else str(p)
        for p in test_dir.glob("test_*.py")
    )
    if not files:
        print(f"no test_*.py files under {test_dir}")
        return 2
    shards = shard(files, args.files_per_shard)
    log_dir = args.log_dir or Path(tempfile.mkdtemp(prefix="fnx-python-parity-suite-"))
    log_dir.mkdir(parents=True, exist_ok=True)
    print(f"{len(files)} test files in {len(shards)} shards, {args.workers} workers, logs in {log_dir}", flush=True)

    start = time.monotonic()
    results = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(run_shard, i, s, log_dir, args.shard_timeout) for i, s in enumerate(shards)]
        for future in futures:
            result = future.result()
            results.append(result)
            status = "ok " if result["returncode"] == 0 else "RED"
            print(
                f"{status} shard {result['shard']:02d}: {result['passed']} passed, {result['failed']} failed, "
                f"{result['errors']} errors, {result['skipped']} skipped ({result['seconds']} s)",
                flush=True,
            )
            for line in result["red"]:
                print(f"    {line}", flush=True)

    totals = {key: sum(r[key] for r in results) for key in ("passed", "failed", "errors", "skipped", "xfailed", "xpassed")}
    bad = [r["shard"] for r in results if r["returncode"] != 0]
    wall = round(time.monotonic() - start, 1)
    print(
        f"TOTAL {len(files)} files: {totals['passed']} passed, {totals['failed']} failed, {totals['errors']} errors, "
        f"{totals['skipped']} skipped, {totals['xfailed']} xfailed in {wall} s; non-zero shards: {bad or 'none'}"
    )
    if args.json_out:
        args.json_out.write_text(
            json.dumps({"files": len(files), "wall_seconds": wall, "totals": totals, "shards": results}, indent=2) + "\n"
        )
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
