#!/usr/bin/env python3
"""Run networkx's own test suite with franken_networkx as the test backend, and
hold the result to a ratchet.

networkx ships a supported way to run its suite against a third-party backend
(NETWORKX_TEST_BACKEND). Every other parity test in this repo was written by fnx
agents; this one was not, which is the point. On 2026-09-24 it found eleven
divergences the repo's own tests had missed (br-r37-c1-rc0923-epic-silent-
wrong-answers-nro4w.7).

The ratchet (artifacts/upstream_suite/ratchet_v1.json) names every test that
may fail, each with a reason, plus the minimum pass count of a full run. A run
fails when a test outside that set fails, or when a full run passes fewer tests
than the floor. --update may only move the ratchet forward: drop allowed
failures that now pass and raise the floor. It refuses to admit a new failure;
that is a hand edit with a reason, visible in review.

The suite runs from a scratch directory (the repo's conftest must not load)
under an address-space limit, with networkx's default warning filters: running
it with -W ignore makes networkx's own test_pajek.py::test_ignored_attribute
fail on plain networkx too.

    scripts/run_upstream_networkx_suite.py            # full run, check (~7 min)
    scripts/run_upstream_networkx_suite.py --update   # full run, move the ratchet forward
    scripts/run_upstream_networkx_suite.py --target networkx.algorithms.tests.test_covering
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import resource
import subprocess  # nosec B404 - runs pytest on the repo's own interpreter
import sys
import tempfile
import time
import xml.etree.ElementTree as ET  # nosec B405 - parses the junit file this script asked pytest to write
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RATCHET = ROOT / "artifacts" / "upstream_suite" / "ratchet_v1.json"
SCHEMA = "fnx-upstream-networkx-ratchet/v1"
ADDRESS_SPACE_LIMIT = 16 * 1024**3
SELF_REPORT = r"""
import hashlib, json, sys
import networkx, franken_networkx, franken_networkx._fnx as ext
with open(ext.__file__, "rb") as fh:
    digest = hashlib.sha256(fh.read()).hexdigest()
print(json.dumps({
    "networkx_version": networkx.__version__,
    "networkx_dir": networkx.__path__[0],
    "python": sys.version.split()[0],
    "fnx_package": franken_networkx.__file__,
    "fnx_extension": ext.__file__,
    "fnx_extension_sha256": digest,
}))
"""


@dataclass
class RunResult:
    passed: int = 0
    skipped: int = 0
    failed: set[str] = field(default_factory=set)
    errors: set[str] = field(default_factory=set)
    ran: set[str] = field(default_factory=set)

    @property
    def not_passing(self) -> set[str]:
        return self.failed | self.errors


@dataclass
class Verdict:
    new_failures: list[str]
    now_passing: list[str]
    pass_floor_breach: tuple[int, int] | None

    @property
    def ok(self) -> bool:
        return not self.new_failures and self.pass_floor_breach is None


def parse_junit(path: Path) -> RunResult:
    """Count one junit testcase per test: failure and error are exclusive
    outcomes, skipped cases are counted, the rest passed."""
    result = RunResult()
    for case in ET.parse(path).getroot().iter("testcase"):  # nosec B314
        test_id = f"{case.get('classname', '')}::{case.get('name', '')}"
        result.ran.add(test_id)
        if case.find("failure") is not None:
            result.failed.add(test_id)
        elif case.find("error") is not None:
            result.errors.add(test_id)
        elif case.find("skipped") is not None:
            result.skipped += 1
        else:
            result.passed += 1
    return result


def compare(ratchet: dict, result: RunResult, *, full_run: bool) -> Verdict:
    allowed = set(ratchet["allowed_failures"])
    new_failures = sorted(result.not_passing - allowed)
    # A subset run only says something about the tests it ran.
    now_passing = sorted((allowed & result.ran) - result.not_passing)
    breach = None
    if full_run and result.passed < ratchet["min_passed"]:
        breach = (result.passed, ratchet["min_passed"])
    return Verdict(new_failures, now_passing, breach)


def advance(ratchet: dict, result: RunResult, report: dict) -> dict:
    """The only direction --update may move: fewer allowed failures, a higher
    floor. Raises when the run has a failure the ratchet does not allow."""
    verdict = compare(ratchet, result, full_run=True)
    if verdict.new_failures:
        raise ValueError(
            "refusing to admit new failures into the ratchet (add them by hand, "
            "each with a reason): " + ", ".join(verdict.new_failures)
        )
    advanced = dict(ratchet)
    advanced["allowed_failures"] = {
        test_id: reason
        for test_id, reason in ratchet["allowed_failures"].items()
        if test_id in result.not_passing
    }
    advanced["min_passed"] = max(ratchet["min_passed"], result.passed)
    advanced["last_run"] = report
    return advanced


def self_report(python: str, env: dict[str, str]) -> dict:
    out = subprocess.run(  # nosec B603
        [python, "-c", SELF_REPORT], capture_output=True, text=True, env=env, check=True,
        cwd=tempfile.gettempdir(), timeout=300,
    )
    try:
        return json.loads(out.stdout)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"self-report printed no JSON ({exc}): {out.stdout[-500:]!r}") from exc


def load_ratchet(path: Path) -> dict:
    try:
        ratchet = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"{path}: {exc}") from exc
    if ratchet.get("schema") != SCHEMA:
        raise SystemExit(f"{path}: unexpected schema {ratchet.get('schema')!r}")
    return ratchet


def refuse_stale_or_foreign_extension(report: dict) -> None:
    extension = Path(report["fnx_extension"]).resolve()
    if ROOT not in extension.parents:
        raise SystemExit(f"franken_networkx imports {extension}, not this checkout's build")
    newest = max(
        (p.stat().st_mtime for p in (ROOT / "crates").glob("*/src/**/*.rs")), default=0.0
    )
    if extension.stat().st_mtime + 1.0 < newest:
        raise SystemExit(f"{extension} is older than the Rust sources: rebuild before measuring")


def run_suite(
    python: str, networkx_dir: str, targets: list[str], timeout: int, env: dict[str, str]
) -> tuple[RunResult, float]:
    with tempfile.TemporaryDirectory(prefix="fnx-upstream-suite-") as scratch:
        junit = Path(scratch) / "junit.xml"
        # An empty ini keeps any stray config out; rooting at networkx's parent
        # keeps the module path in every test id (outside the rootdir, pytest
        # reports '::TestX::test_y' with no file).
        ini = Path(scratch) / "pytest.ini"
        ini.write_text("[pytest]\n")
        command = [
            python, "-m", "pytest", "-c", str(ini), "--rootdir", str(Path(networkx_dir).parent),
            "--pyargs", *targets,
            "-q", "-p", "no:cacheprovider", "--tb=no", f"--junitxml={junit}",
        ]

        def limit_address_space() -> None:
            resource.setrlimit(resource.RLIMIT_AS, (ADDRESS_SPACE_LIMIT, ADDRESS_SPACE_LIMIT))

        start = time.monotonic()
        proc = subprocess.run(  # nosec B603
            command, cwd=scratch, env=env, timeout=timeout, preexec_fn=limit_address_space,
            capture_output=True, text=True,
        )
        seconds = time.monotonic() - start
        if not junit.exists():
            sys.stderr.write(proc.stdout[-4000:] + proc.stderr[-4000:])
            raise SystemExit(f"pytest wrote no junit report (exit {proc.returncode})")
        return parse_junit(junit), seconds


def per_file_counts(test_ids: set[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for test_id in test_ids:
        module = test_id.split("::", 1)[0]
        parts = module.split(".")
        name = next((".".join(parts[: i + 1]) for i, p in enumerate(parts) if p.startswith("test_")), module)
        counts[name] = counts.get(name, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--ratchet", type=Path, default=DEFAULT_RATCHET)
    parser.add_argument("--update", action="store_true", help="move the ratchet forward after a full run")
    parser.add_argument("--target", action="append", default=[], help="networkx test module(s); default: all")
    parser.add_argument("--timeout", type=int, default=2400)
    parser.add_argument("--json-out", type=Path, help="write this run's result here")
    args = parser.parse_args(argv)

    full_run = not args.target
    if args.update and not full_run:
        parser.error("--update needs a full run (no --target)")

    env = dict(os.environ)
    env["NETWORKX_TEST_BACKEND"] = "franken_networkx"
    env["NETWORKX_FALLBACK_TO_NX"] = "True"
    python = sys.executable
    report = self_report(python, env)
    refuse_stale_or_foreign_extension(report)

    ratchet = load_ratchet(args.ratchet)
    if ratchet["networkx_version"] != report["networkx_version"]:
        raise SystemExit(
            f"ratchet is for networkx {ratchet['networkx_version']}, installed is "
            f"{report['networkx_version']}: test ids and counts are not comparable"
        )

    result, seconds = run_suite(
        python, report["networkx_dir"], args.target or ["networkx"], args.timeout, env
    )
    git_sha = subprocess.run(  # nosec B603 B607
        ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=False,
        timeout=60,
    ).stdout.strip()
    run = {
        **report,
        "fnx_git_sha": git_sha,
        "targets": args.target or ["networkx"],
        "passed": result.passed,
        "failed": len(result.failed),
        "errors": len(result.errors),
        "skipped": result.skipped,
        "seconds": round(seconds, 1),
        "not_passing_by_file": per_file_counts(result.not_passing),
    }
    if args.json_out:
        args.json_out.write_text(json.dumps({**run, "not_passing": sorted(result.not_passing)}, indent=2) + "\n")

    verdict = compare(ratchet, result, full_run=full_run)
    print(
        f"networkx {report['networkx_version']} suite, fnx backend ({report['fnx_extension_sha256'][:12]}): "
        f"{result.passed} passed, {len(result.failed)} failed, {len(result.errors)} errors, "
        f"{result.skipped} skipped in {seconds:.0f} s"
    )
    for test_id in verdict.new_failures:
        print(f"NEW FAILURE (not in the ratchet): {test_id}")
    if verdict.pass_floor_breach:
        got, floor = verdict.pass_floor_breach
        print(f"PASS COUNT BELOW THE RATCHET: {got} < {floor}")
    for test_id in verdict.now_passing:
        print(f"now passing, drop from the ratchet with --update: {test_id}")

    if args.update:
        advanced = advance(ratchet, result, run)
        args.ratchet.write_text(json.dumps(advanced, indent=2, ensure_ascii=False) + "\n")
        print(f"ratchet advanced: {len(advanced['allowed_failures'])} allowed failures, floor {advanced['min_passed']}")
    return 0 if verdict.ok else 1


if __name__ == "__main__":
    sys.exit(main())
