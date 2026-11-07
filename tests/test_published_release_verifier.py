"""Offline release configuration and published-artifact refusal tests."""

import importlib.util
import json
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "published_release_verifier",
    ROOT / "scripts/verify_published_release.py",
)
verifier = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verifier)


class DsrQualityInventoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Parse with DSR's own required YAML tool. A missing parser is an
        # incomplete qualification, not a reason to silently skip this gate.
        yq = shutil.which("yq")
        if yq is None:
            raise RuntimeError("DSR quality inventory tests require Mike Farah yq on PATH")
        cls.registry = json.loads(subprocess.check_output(
            [yq, "-o=json", ".tools.franken_networkx", str(ROOT / ".dsr/repos.yaml")],
            text=True, timeout=30,
        ))
        cls.recipe = json.loads(subprocess.check_output(
            [yq, "-o=json", ".", str(ROOT / ".dsr/repos.d/franken_networkx.yaml")],
            text=True, timeout=30,
        ))

    def test_quality_registry_and_build_recipe_run_the_same_checks(self):
        self.assertEqual(
            self.registry["checks"], self.recipe["checks"],
            "dsr quality reads repos.yaml; repos.d must not silently define stronger gates",
        )
        self.assertEqual(self.registry.get("required_checks", []),
                         self.recipe.get("required_checks", []))
        for key in ("repo", "local_path", "language", "targets"):
            with self.subTest(key=key):
                self.assertEqual(self.registry[key], self.recipe[key])

    def test_quality_inventory_retains_full_native_and_python_qualification(self):
        checks = self.registry["checks"]
        for command in (
            "cargo fmt --all -- --check",
            "RCH_REQUIRE_REMOTE=1 CARGO_BUILD_JOBS=2 rch exec -- cargo check --locked -j 2 --workspace --all-targets",
            "RCH_REQUIRE_REMOTE=1 CARGO_BUILD_JOBS=2 rch exec -- cargo clippy --locked -j 2 --workspace --all-targets -- -D warnings",
            "RCH_REQUIRE_REMOTE=1 CARGO_BUILD_JOBS=2 rch exec -- cargo test --locked -j 2 --workspace --exclude fnx-python --no-fail-fast",
            ".venv/bin/python scripts/fuzz_corpus_replay.py --budget-seconds 10",
            ".venv/bin/python scripts/verify_docs.py",
            ".venv/bin/python scripts/run_upstream_networkx_suite.py",
            ".venv/bin/python scripts/run_python_parity_suite.py --workers 4",
        ):
            with self.subTest(command=command):
                self.assertIn(command, checks)

    def test_guarded_smoke_includes_overflow_and_release_inventory_regressions(self):
        smoke = [command.split() for command in self.registry["checks"]
                 if command.startswith("./scripts/run_pytest_guarded.sh ")]
        self.assertEqual(len(smoke), 1)
        for module in (
            "tests/python/test_instance_dict_memory_leak.py",
            "tests/python/test_error_messages.py",
            "tests/python/test_thread_safety.py",
            "tests/python/test_coverage_gaps.py",
            "tests/python/test_delegation_ledger.py",
            "tests/python/test_raw_vs_public_audit.py",
            "tests/python/test_upstream_divergence_ledger.py",
            "tests/python/test_api_ergonomics_audit.py",
            "tests/python/test_unused_raw_exposures.py",
            "tests/python/test_dijkstra_exact_weight_domain.py",
            "tests/test_published_release_verifier.py",
        ):
            with self.subTest(module=module):
                self.assertIn(module, smoke[0])


class PublishedReleaseVerifierTests(unittest.TestCase):
    def test_manifest_rejects_duplicate_empty_and_path_rows(self):
        digest = "a" * 64
        for value in ("", f"{digest} wheel.whl\n{digest} wheel.whl", f"{digest} ../wheel.whl",
                      f"{digest} /wheel.whl", f"{digest} ..", f"{digest[:-1]} wheel.whl"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                verifier.parse_manifest(value)

    def test_manifest_accepts_binary_marker_and_normalizes_digest(self):
        self.assertEqual(verifier.parse_manifest("A" * 64 + "  *wheel.whl\n"), {"wheel.whl": "a" * 64})

    def test_registry_requires_exact_signed_non_yanked_wheels(self):
        version = "0.2.3"
        manifest = {name: "a" * 64 for name in verifier.wheel_names(version)}
        rows = [{"filename": name, "packagetype": "bdist_wheel", "yanked": False,
                 "digests": {"sha256": digest}} for name, digest in manifest.items()]
        metadata = {"info": {"version": version}, "urls": rows}
        self.assertEqual(verifier.validate_registry(metadata, version, manifest), rows)
        for mutation in ("digest", "yanked", "duplicate", "missing", "version", "sdist"):
            changed = {"info": dict(metadata["info"]), "urls": [dict(row, digests=dict(row["digests"])) for row in rows]}
            if mutation == "digest":
                changed["urls"][0]["digests"]["sha256"] = "b" * 64
            elif mutation == "yanked":
                changed["urls"][0]["yanked"] = True
            elif mutation == "duplicate":
                changed["urls"][0] = changed["urls"][1]
            elif mutation == "missing":
                changed["urls"] = changed["urls"][:-1]
            elif mutation == "version":
                changed["info"]["version"] = "0.2.2"
            else:
                changed["urls"][0]["packagetype"] = "sdist"
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                verifier.validate_registry(changed, version, manifest)

    def test_download_boundary_refuses_credentials_non_https_and_other_hosts(self):
        for url in ("http://pypi.org/pypi/pip/json", "https://pypi.org.evil.test/file",
                    "https://user:pass@pypi.org/file", "https://pypi.org:444/file", "file:///etc/passwd"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                verifier.check_url(url)
        verifier.check_url("https://files.pythonhosted.org/packages/wheel.whl")


if __name__ == "__main__":
    unittest.main()
