#!/usr/bin/env python3
"""Validate Markdown links and execute runnable documentation examples."""

from __future__ import annotations

import argparse
import os
import re
import subprocess  # nosec B404 - this script intentionally executes repo-owned examples
import sys
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
MARKDOWN_SOURCES = [ROOT / "README.md"]
EXAMPLE_DIR = ROOT / "examples"
DOCS_DIR = ROOT / "docs"
DOCS_EXEC_TIMEOUT_SECONDS = 60
PYTHON_FENCE_RE = re.compile(r"```([^\n`]*)\n(.*?)```", re.DOTALL)
LINK_RE = re.compile(r'!?\[[^\]]*\]\(([^)\s]+(?:\s+"[^"]*")?)\)')
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)


def repo_python_env() -> dict[str, str]:
    env = os.environ.copy()
    paths = [str(ROOT / "python"), str(ROOT)]
    existing = env.get("PYTHONPATH")
    if existing:
        paths.append(existing)
    env["PYTHONPATH"] = os.pathsep.join(paths)
    return env


def github_anchor(title: str) -> str:
    anchor = title.strip().lower()
    anchor = re.sub(r"[^\w\s-]", "", anchor)
    anchor = re.sub(r"\s+", "-", anchor)
    anchor = re.sub(r"-{2,}", "-", anchor)
    return anchor.strip("-")


def markdown_sources() -> list[Path]:
    docs = sorted(DOCS_DIR.glob("*.md")) if DOCS_DIR.exists() else []
    return MARKDOWN_SOURCES + docs


def example_sources() -> list[Path]:
    return sorted(EXAMPLE_DIR.glob("*.py")) if EXAMPLE_DIR.exists() else []


def local_anchors(path: Path) -> set[str]:
    anchors = set()
    text = path.read_text(encoding="utf-8")
    for match in HEADING_RE.finditer(text):
        anchors.add(github_anchor(match.group(2)))
    return anchors


def validate_links(path: Path) -> list[str]:
    errors: list[str] = []
    text = path.read_text(encoding="utf-8")
    anchors = local_anchors(path)
    for raw_target in LINK_RE.findall(text):
        target = raw_target.split()[0].strip("<>")
        if target.startswith("mailto:"):
            if "@" not in target:
                errors.append(f"{path}: invalid mailto link {target}")
            continue
        if target.startswith(("http://", "https://")):
            parsed = urlparse(target)
            if not parsed.scheme or not parsed.netloc:
                errors.append(f"{path}: malformed external URL {target}")
            continue

        if "#" in target:
            rel_target, anchor = target.split("#", 1)
        else:
            rel_target, anchor = target, ""

        if rel_target:
            resolved = (path.parent / rel_target).resolve()
            if not resolved.exists():
                errors.append(f"{path}: missing relative link target {target}")
                continue
            target_anchors = local_anchors(resolved) if resolved.suffix.lower() == ".md" else set()
        else:
            resolved = path
            target_anchors = anchors

        if anchor and anchor not in target_anchors:
            errors.append(f"{path}: missing anchor #{anchor} in {resolved}")
    return errors


def python_blocks(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    blocks = []
    for info, body in PYTHON_FENCE_RE.findall(text):
        tag = info.strip().split()
        if not tag:
            continue
        if tag[0] not in {"python", "py"}:
            continue
        if "skip-verify" in tag:
            continue
        blocks.append(body)
    return blocks


def run_markdown(path: Path, python_bin: str) -> list[str]:
    errors = validate_links(path)
    blocks = python_blocks(path)
    if not blocks:
        return errors

    source_lines = []
    for index, block in enumerate(blocks, start=1):
        source_lines.append(f"# {path.name} block {index}")
        source_lines.append(block.rstrip())
        source_lines.append("")

    env = repo_python_env()
    try:
        subprocess.run(
            [python_bin, "-c", "\n".join(source_lines)],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=DOCS_EXEC_TIMEOUT_SECONDS,
            check=True,
        )  # nosec B603 - the executed code comes from repository-owned documentation
    except subprocess.TimeoutExpired:
        errors.append(
            f"{path}: markdown execution timed out after {DOCS_EXEC_TIMEOUT_SECONDS}s"
        )
    except subprocess.CalledProcessError as exc:  # pragma: no cover - exercised in CI on failure
        errors.append(
            "\n".join(
                [
                    f"{path}: markdown execution failed",
                    exc.stdout.strip(),
                    exc.stderr.strip(),
                ]
            ).strip()
        )
    return errors


def run_example(path: Path, python_bin: str) -> list[str]:
    env = repo_python_env()
    try:
        subprocess.run(
            [python_bin, str(path)],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=DOCS_EXEC_TIMEOUT_SECONDS,
            check=True,
        )  # nosec B603 - the executed code comes from repository-owned example scripts
    except subprocess.TimeoutExpired:
        return [f"{path}: example timed out after {DOCS_EXEC_TIMEOUT_SECONDS}s"]
    except subprocess.CalledProcessError as exc:
        return [
            "\n".join(
                [
                    f"{path}: example exited with {exc.returncode}",
                    exc.stdout.strip(),
                    exc.stderr.strip(),
                ]
            ).strip()
        ]
    else:
        return []


def validate_generated_docs(python_bin: str) -> list[str]:
    env = repo_python_env()
    try:
        subprocess.run(
            [python_bin, str(ROOT / "scripts" / "generate_coverage_matrix.py"), "--check"],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=DOCS_EXEC_TIMEOUT_SECONDS,
            check=True,
        )  # nosec B603 - the executed generator is repository-owned
    except subprocess.TimeoutExpired:
        return [
            f"generated docs validation timed out after {DOCS_EXEC_TIMEOUT_SECONDS}s"
        ]
    except subprocess.CalledProcessError as exc:
        return [
            "\n".join(
                [
                    "generated docs validation failed",
                    exc.stdout.strip(),
                    exc.stderr.strip(),
                ]
            ).strip()
        ]
    else:
        return []


RELEASE_MENTION_RES = (
    re.compile(r"franken-networkx\s*=\s*\"==([0-9][^\"]*)\""),
    re.compile(r"franken-networkx==([0-9][0-9A-Za-z.+-]*)"),
    re.compile(r"PyPI's current release is `?([0-9][0-9A-Za-z.+-]*[0-9A-Za-z])`?"),
    re.compile(r"PyPI \(release ([0-9][0-9A-Za-z.+-]*[0-9A-Za-z])\)"),
)


def published_pypi_release() -> str:
    """The latest version actually on PyPI, recorded at release time in
    ``[tool.franken_networkx] pypi_release`` (pyproject's own ``version`` is
    the NEXT release, not a published one)."""
    import tomllib

    with (ROOT / "pyproject.toml").open("rb") as fh:
        return tomllib.load(fh)["tool"]["franken_networkx"]["pypi_release"]


def validate_release_mentions(text: str, published: str) -> list[str]:
    """Every install pin and "current PyPI release" statement must name the
    published release. br-r37-c1-rc0923-epic-docs-truth-structure-8813x.1: the
    README pinned ``==0.2.0`` (never on PyPI, so the documented install
    failed) while also calling ``v0.2.2`` published and ``0.2.1`` current."""
    failures = []
    for pattern in RELEASE_MENTION_RES:
        for match in pattern.finditer(text):
            if match.group(1) != published:
                line = text.count("\n", 0, match.start()) + 1
                failures.append(
                    f"README.md:{line}: names release {match.group(1)!r} but the "
                    f"published PyPI release is {published!r} "
                    "([tool.franken_networkx] pypi_release in pyproject.toml)"
                )
    return failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--python-bin", default=sys.executable)
    args = parser.parse_args()

    failures: list[str] = []
    failures.extend(validate_generated_docs(args.python_bin))
    failures.extend(
        validate_release_mentions(
            (ROOT / "README.md").read_text(encoding="utf-8"), published_pypi_release()
        )
    )

    for path in markdown_sources():
        failures.extend(run_markdown(path, args.python_bin))

    for path in example_sources():
        failures.extend(run_example(path, args.python_bin))

    if failures:
        for failure in failures:
            print(failure, file=sys.stderr)
        return 1

    print(
        f"verified_markdown={len(markdown_sources())} verified_examples={len(example_sources())}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
