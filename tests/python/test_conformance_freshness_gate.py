"""Regression tests for the conformance freshness gate."""

from __future__ import annotations

import os
from pathlib import Path

from scripts.verify_conformance_freshness import check_fixture_report_freshness


def _touch(path: Path, mtime: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{}", encoding="utf-8")
    os.utime(path, (mtime, mtime))


def test_fixture_freshness_ignores_python_bytecode(tmp_path: Path) -> None:
    artifacts = tmp_path / "artifacts"
    source_root = tmp_path / "python" / "franken_networkx"
    _touch(artifacts / "case.report.json", 2_000)
    _touch(source_root / "__init__.py", 1_000)
    _touch(source_root / "__pycache__" / "__init__.cpython-313.pyc", 3_000)

    ok, errors = check_fixture_report_freshness(artifacts, [source_root])

    assert ok, errors


def test_fixture_freshness_still_rejects_newer_sources(tmp_path: Path) -> None:
    artifacts = tmp_path / "artifacts"
    source_root = tmp_path / "python" / "franken_networkx"
    _touch(artifacts / "case.report.json", 1_000)
    _touch(source_root / "__init__.py", 3_000)
    _touch(source_root / "__pycache__" / "__init__.cpython-313.pyc", 4_000)

    ok, errors = check_fixture_report_freshness(artifacts, [source_root])

    assert not ok
    assert "__init__.py" in errors[0]
    assert "__pycache__" not in errors[0]
