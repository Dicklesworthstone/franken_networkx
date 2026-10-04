"""Offline refusal tests for the published-artifact verifier (no native build)."""

import importlib.util
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "published_release_verifier",
    Path(__file__).resolve().parents[1] / "scripts/verify_published_release.py",
)
verifier = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verifier)


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
