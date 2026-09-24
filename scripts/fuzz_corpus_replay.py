#!/usr/bin/env python3
"""Replay every fuzz target's committed corpus, then fuzz briefly (hhj5p.1 item 5).

The fuzz crate's targets are libFuzzer binaries. They are built on an rch
worker with the coverage instrumentation cargo-fuzz uses (sancov, no
sanitizer: the workspace forbids unsafe code), and rch retrieves them into
fuzz/target. Each target then runs here over its committed corpus and its
committed crash / timeout / oom reproducers under fuzz/artifacts/<target>/:

* ``--budget-seconds 0`` (the default) runs every input once (-runs=0);
* ``--budget-seconds N`` runs every input, then mutates for N seconds.

A panic, an input slower than --input-timeout, or one using more than
--rss-limit-mb fails the target. libFuzzer writes the failing input under
--artifacts-out (the DSR run directory when DSR runs this, else a fresh
temporary directory), never into the source tree: a file appearing in the
tree mid-run makes DSR discard the whole run as a moving source. The report
names the file; committing it under fuzz/artifacts/<target>/ makes every
later run replay it. Inputs found while mutating go to a temporary directory,
never into the committed corpus. The CPU-seconds each target used are
reported.

    scripts/fuzz_corpus_replay.py                       # build remotely, replay all
    scripts/fuzz_corpus_replay.py --budget-seconds 5    # replay, then 5 s of fuzzing each
    scripts/fuzz_corpus_replay.py --no-build --target fuzz_dag
"""

from __future__ import annotations

import argparse
import json
import os
import re
import resource
import subprocess  # nosec B404 - runs the repo's own fuzz binaries and rch
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FUZZ = ROOT / "fuzz"
TRIPLE = "x86_64-unknown-linux-gnu"
RCH_RETRYABLE = 103  # "remote required; refusing local fallback (no admissible workers ...) — retryable"
BIN_RE = re.compile(r'^\[\[bin\]\]\s*\nname\s*=\s*"([^"]+)"', re.MULTILINE)
# cargo-fuzz's instrumentation with its sanitizer set to none. Passing
# --target keeps these flags off build scripts and proc macros.
RUSTFLAGS = [
    "-Cpasses=sancov-module",
    "-Cllvm-args=-sanitizer-coverage-level=4",
    "-Cllvm-args=-sanitizer-coverage-inline-8bit-counters",
    "-Cllvm-args=-sanitizer-coverage-pc-table",
    "-Cllvm-args=-sanitizer-coverage-trace-compares",
    "--cfg", "fuzzing",
]


def fuzz_targets(fuzz_dir: Path = FUZZ) -> list[str]:
    """Binary names declared in fuzz/Cargo.toml that have a committed corpus."""
    names = BIN_RE.findall((fuzz_dir / "Cargo.toml").read_text(encoding="utf-8"))
    return [name for name in names if (fuzz_dir / "corpus" / name).is_dir()]


def binary_path(fuzz_dir: Path, name: str) -> Path:
    return fuzz_dir / "target" / TRIPLE / "release" / name


def build_command(jobs: int, fuzz_dir: Path = FUZZ) -> tuple[list[str], dict[str, str]]:
    """The rch build of every fuzz target, and its environment.

    RCH_QUEUE_WHEN_BUSY makes rch wait for a worker slot instead of refusing
    when every worker is busy, as the DSR config's cargo checks do.
    """
    env = dict(os.environ, CARGO_TARGET_DIR=str(fuzz_dir / "target"), RCH_QUEUE_WHEN_BUSY="1")
    command = [
        "rch", "exec", "--", "cargo", "build", "--release", "-j", str(jobs),
        "--manifest-path", str(fuzz_dir / "Cargo.toml"), "--bins", "--target", TRIPLE,
        "--config", "build.rustflags=" + json.dumps(RUSTFLAGS, separators=(",", ":")),
    ]
    return command, env


def build(jobs: int, fuzz_dir: Path = FUZZ, attempts: int = 20, wait_seconds: int = 60) -> None:
    """Build every fuzz target on an rch worker.

    rch exits RCH_RETRYABLE when no worker is admissible at all (critical
    pressure, too few slots), which RCH_QUEUE_WHEN_BUSY does not cover. That
    refusal is retried a bounded number of times, each one announced; any
    other failure, or the last refusal, fails the build.
    """
    command, env = build_command(jobs, fuzz_dir)
    for attempt in range(1, attempts + 1):
        proc = subprocess.run(command, cwd=fuzz_dir.parent, env=env, timeout=5400, check=False)  # nosec B603 B607
        if proc.returncode == 0:
            return
        if proc.returncode != RCH_RETRYABLE or attempt == attempts:
            raise SystemExit(f"fuzz build failed (exit {proc.returncode}, attempt {attempt} of {attempts})")
        print(f"rch admitted no worker (exit {RCH_RETRYABLE}); attempt {attempt} of {attempts}, "
              f"retrying in {wait_seconds}s", flush=True)
        time.sleep(wait_seconds)


def replay(name: str, *, artifacts_out: Path, fuzz_dir: Path = FUZZ, budget_seconds: int = 0,
           input_timeout: int = 60, rss_limit_mb: int = 4096) -> dict:
    """Run target ``name`` over its corpus and reproducers, then fuzz for ``budget_seconds``.

    A failing input is written under ``artifacts_out / name``, outside the tree.
    """
    binary = binary_path(fuzz_dir, name)
    if not binary.exists():
        return {"target": name, "ok": False, "summary": f"missing binary {binary}", "log": "", "cpu_seconds": 0.0}
    committed = fuzz_dir / "artifacts" / name
    inputs = [fuzz_dir / "corpus" / name]
    if committed.is_dir():
        inputs.append(committed)
    written = artifacts_out / name
    written.mkdir(parents=True, exist_ok=True)
    mode = [f"-max_total_time={budget_seconds}"] if budget_seconds > 0 else ["-runs=0"]
    limits = [f"-timeout={input_timeout}", f"-rss_limit_mb={rss_limit_mb}", f"-artifact_prefix={written}/"]
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    start = time.monotonic()
    with tempfile.TemporaryDirectory(prefix=f"{name}-new-") as found:
        # libFuzzer writes new inputs into the FIRST directory it is given.
        dirs = [found, *map(str, inputs)] if budget_seconds > 0 else list(map(str, inputs))
        try:
            proc = subprocess.run(  # nosec B603
                [str(binary), *dirs, *mode, *limits], cwd=fuzz_dir, capture_output=True, text=True,
                errors="replace", timeout=budget_seconds + input_timeout + 1800, check=False,
            )
        except subprocess.TimeoutExpired:
            return {"target": name, "ok": False, "summary": "no verdict before the wall-clock limit",
                    "log": "", "cpu_seconds": 0.0}
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    cpu = round((after.ru_utime + after.ru_stime) - (before.ru_utime + before.ru_stime), 2)
    log = (proc.stdout + proc.stderr).strip()
    done = [line for line in log.splitlines() if line.startswith("Done ")]
    ok = proc.returncode == 0 and bool(done)
    summary = done[-1] if ok else f"exit {proc.returncode}"
    tail = "\n".join(log.splitlines()[-25:])
    reproducers = sorted(str(p) for p in written.iterdir())
    if reproducers:
        tail += "\nreproducer(s), copy into " + str(committed) + "/ to replay on every run:\n" + "\n".join(reproducers)
    return {
        "target": name,
        "ok": ok,
        "summary": f"{summary} ({time.monotonic() - start:.1f}s wall, {cpu} cpu-s)",
        "log": "" if ok else tail,
        "cpu_seconds": cpu,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--no-build", action="store_true", help="use the binaries already in fuzz/target")
    parser.add_argument("--jobs", type=int, default=2)
    parser.add_argument("--target", action="append", default=[], help="only these targets")
    parser.add_argument("--fuzz-dir", type=Path, default=FUZZ)
    parser.add_argument("--budget-seconds", type=int, default=0, help="seconds of fuzzing per target after the replay")
    parser.add_argument("--input-timeout", type=int, default=60, help="seconds allowed per input")
    parser.add_argument("--rss-limit-mb", type=int, default=4096)
    parser.add_argument("--artifacts-out", type=Path,
                        help="where failing inputs go (default: $DSR_QUALITY_RUN_DIR/fuzz-artifacts, "
                             "else a fresh temporary directory)")
    args = parser.parse_args(argv)

    targets = args.target or fuzz_targets(args.fuzz_dir)
    if not targets:
        print("no fuzz targets with a committed corpus")
        return 2
    artifacts_out = args.artifacts_out
    if artifacts_out is None:
        run_dir = os.environ.get("DSR_QUALITY_RUN_DIR")
        artifacts_out = (Path(run_dir) / "fuzz-artifacts" if run_dir
                         else Path(tempfile.mkdtemp(prefix="fnx-fuzz-artifacts-")))
    if not args.no_build:
        build(args.jobs, args.fuzz_dir)

    failed = []
    cpu_total = 0.0
    for name in targets:
        result = replay(name, artifacts_out=artifacts_out, fuzz_dir=args.fuzz_dir,
                        budget_seconds=args.budget_seconds, input_timeout=args.input_timeout,
                        rss_limit_mb=args.rss_limit_mb)
        cpu_total += result["cpu_seconds"]
        print(f"{'ok  ' if result['ok'] else 'FAIL'} {name}: {result['summary']}", flush=True)
        if not result["ok"]:
            failed.append(name)
            print("    " + result["log"].replace("\n", "\n    "), flush=True)
    print(f"TOTAL {len(targets)} targets, {len(failed)} failed: {failed or 'none'}; "
          f"{cpu_total:.1f} cpu-seconds, budget {args.budget_seconds}s per target")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
