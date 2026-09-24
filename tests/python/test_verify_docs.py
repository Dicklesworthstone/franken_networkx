"""Regression tests for documentation example validation."""

from __future__ import annotations

import os
from pathlib import Path
from runpy import run_path
import sys


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_verify_docs_script():
    script_path = _repo_root() / "scripts" / "verify_docs.py"
    return run_path(str(script_path))


def test_docs_verifier_prefers_checkout_python_package(tmp_path: Path) -> None:
    verify_docs = _load_verify_docs_script()
    env = verify_docs["repo_python_env"]()
    pythonpath = env["PYTHONPATH"].split(os.pathsep)
    expected_prefix = [
        str(_repo_root() / "python"),
        str(_repo_root()),
    ]
    if pythonpath[:2] != expected_prefix:
        raise AssertionError(f"unexpected PYTHONPATH prefix: {pythonpath[:2]!r}")

    doc = tmp_path / "stale_api.md"
    doc.write_text(
        "\n".join(
            [
                "```python",
                "import franken_networkx as fnx",
                "getattr(fnx, 'bipartite_sets')",
                "```",
            ]
        ),
        encoding="utf-8",
    )
    failures = verify_docs["run_markdown"](doc, sys.executable)
    failure_text = "\n".join(failures)

    if "has no attribute 'bipartite_sets'" not in failure_text:
        raise AssertionError(f"expected checkout import failure, got: {failure_text}")


def test_docs_verifier_times_out_markdown_blocks(tmp_path: Path) -> None:
    verify_docs = _load_verify_docs_script()
    verify_docs["run_markdown"].__globals__["DOCS_EXEC_TIMEOUT_SECONDS"] = 0.1

    doc = tmp_path / "sleeping.md"
    doc.write_text(
        "\n".join(
            [
                "```python",
                "import time",
                "time.sleep(30)",
                "```",
            ]
        ),
        encoding="utf-8",
    )
    failures = verify_docs["run_markdown"](doc, sys.executable)
    failure_text = "\n".join(failures)

    if "markdown execution timed out after 0.1s" not in failure_text:
        raise AssertionError(f"expected timeout failure, got: {failure_text}")


def _run_documented_block(
    verify_docs: dict[str, object], doc: Path, marker: str, tmp_path: Path
) -> list[str]:
    blocks = verify_docs["python_blocks"](doc)
    block = next(block for block in blocks if marker in block)
    isolated = tmp_path / f"{doc.stem}-{marker}.md"
    isolated.write_text(f"```python\n{block}```\n", encoding="utf-8")
    return verify_docs["run_markdown"](isolated, sys.executable)


def test_public_social_network_examples_use_the_community_namespace(tmp_path: Path) -> None:
    verify_docs = _load_verify_docs_script()
    root = _repo_root()

    readme_failures = _run_documented_block(
        verify_docs, root / "README.md", "WeightThenInsertionOrder", tmp_path
    )
    if readme_failures:
        raise AssertionError(f"README tie-break example failed: {readme_failures!r}")

    graphml_failures = _run_documented_block(
        verify_docs, root / "README.md", "TemporaryDirectory", tmp_path
    )
    if graphml_failures:
        raise AssertionError(f"README GraphML round-trip example failed: {graphml_failures!r}")

    quickstart_failures = _run_documented_block(
        verify_docs, root / "docs" / "quickstart.md", "community.girvan_newman", tmp_path
    )
    if quickstart_failures:
        raise AssertionError(f"quickstart social-network example failed: {quickstart_failures!r}")

    example_failures = verify_docs["run_example"](
        root / "examples" / "social_network.py", sys.executable
    )
    if example_failures:
        raise AssertionError(f"social network example failed: {example_failures!r}")


def test_negative_evidence_dimension_probes_are_not_relative_links() -> None:
    verify_docs = _load_verify_docs_script()
    path = _repo_root() / "docs" / "NEGATIVE_EVIDENCE_cc.md"
    failures = verify_docs["validate_links"](path)
    unexpected = [failure for failure in failures if "missing relative link target" in failure]
    if unexpected:
        raise AssertionError(f"dimension probes must not be parsed as links: {unexpected!r}")


def test_release_mentions_must_name_the_published_release() -> None:
    """br-r37-c1-rc0923-epic-docs-truth-structure-8813x.1: the README pinned a
    version that was never on PyPI; every pin/"current release" line is now
    checked against the recorded published release."""
    verify_docs = _load_verify_docs_script()
    check = verify_docs["validate_release_mentions"]
    good = 'franken-networkx = "==0.2.1"\nPyPI\'s current release is `0.2.1`\n'
    assert check(good, "0.2.1") == []
    stale = 'franken-networkx = "==0.2.0"\npip install franken-networkx==0.2.2\n'
    failures = check(stale, "0.2.1")
    assert len(failures) == 2 and "0.2.0" in failures[0] and "0.2.2" in failures[1]


def test_readme_release_mentions_match_the_recorded_pypi_release() -> None:
    verify_docs = _load_verify_docs_script()
    readme = (_repo_root() / "README.md").read_text(encoding="utf-8")
    published = verify_docs["published_pypi_release"]()
    assert verify_docs["validate_release_mentions"](readme, published) == []
    # the README must actually state the release, so the check is not vacuous
    assert f"PyPI's current release is `{published}`" in readme
