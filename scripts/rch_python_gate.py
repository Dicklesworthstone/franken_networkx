#!/usr/bin/env python3
"""Test current Python sources against a separately RCH-built native extension.

This script never compiles. Run it through `rch exec --job` on the worker that
produced --library. The isolated environment and logs are retained at --scratch.
Dependencies must have binary distributions; no installer may compile them.
The coverage ledger requires the pinned NetworkX 3.6.1 oracle; use
--networkx-version to run an additional compatibility probe explicitly.
"""

import argparse
import configparser
import hashlib
import json
import os
from pathlib import Path
import resource
import shutil
import subprocess
import tomllib
import urllib.request

USER_AGENT = "OpenAI File Downloader, XaiImageApiFetch/1.0"


def fetch(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": USER_AGENT}), timeout=60) as response:
        return response.read()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--library", type=Path, required=True)
    parser.add_argument("--scratch", type=Path, required=True)
    parser.add_argument("--networkx-version", default="3.6.1")
    args = parser.parse_args()
    library = args.library.resolve(strict=True)
    scratch = args.scratch.resolve()
    root = Path(__file__).resolve().parents[1]
    uv = shutil.which("uv")
    if not uv:
        raise SystemExit("uv is required on the RCH test worker")
    if scratch.exists():
        raise SystemExit(f"use a fresh scratch path; existing files are retained: {scratch}")
    scratch.mkdir(parents=True)
    subprocess.run([uv, "venv", "--no-python-downloads", "--python", "python3", str(scratch / "venv")], check=True)
    python = scratch / "venv/bin/python"
    # Bootstrap pip from its official wheel without running a source build,
    # and set the workspace-required User-Agent for all dependency requests.
    metadata = json.loads(fetch("https://pypi.org/pypi/pip/json"))
    wheel = next(row for row in metadata["urls"] if row["filename"].endswith("-py3-none-any.whl"))
    data = fetch(wheel["url"])
    if hashlib.sha256(data).hexdigest() != wheel["digests"]["sha256"]:
        raise SystemExit("pip bootstrap wheel failed the official PyPI checksum")
    bootstrap_wheel = scratch / wheel["filename"]
    bootstrap_wheel.write_bytes(data)
    bootstrap_env = os.environ.copy()
    bootstrap_env["PYTHONPATH"] = str(bootstrap_wheel)
    bootstrap_env["PIP_CACHE_DIR"] = str(scratch / "pip-cache")
    bootstrap = ("import sys; from pip._internal.network import session; "
                 f"session.user_agent = lambda: {USER_AGENT!r}; "
                 "from pip._internal.cli.main import main; sys.exit(main(sys.argv[1:]))")
    subprocess.run([str(python), "-c", bootstrap, "install", "--only-binary=:all:",
                    "pip", "pytest", "pytest-benchmark", "hypothesis",
                    f"networkx=={args.networkx_version}", "numpy", "scipy", "pandas"],
                   env=bootstrap_env, check=True)
    shutil.copytree(root / "python", scratch / "python")
    shutil.copyfile(library, scratch / "python/franken_networkx/_fnx.abi3.so")
    # Source qualification needs the actual declared backend entry points.
    # Materialize only runtime metadata from pyproject, without invoking a
    # package builder. Published-wheel installation is a separate release E2E.
    project = tomllib.loads((root / "pyproject.toml").read_text())["project"]
    version = tomllib.loads((root / "Cargo.toml").read_text())["workspace"]["package"]["version"]
    dist_info = scratch / "python" / f"franken_networkx-{version}.dist-info"
    dist_info.mkdir()
    (dist_info / "METADATA").write_text(
        f"Metadata-Version: 2.3\nName: {project['name']}\nVersion: {version}\n"
    )
    entry_points = configparser.ConfigParser()
    entry_points.optionxform = str
    entry_points.read_dict(project["entry-points"])
    with (dist_info / "entry_points.txt").open("w") as handle:
        entry_points.write(handle)
    print(f"native_library_sha256={hashlib.sha256(library.read_bytes()).hexdigest()}", flush=True)
    env = os.environ.copy()
    env["PYTHONPATH"] = str(scratch / "python")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["NETWORKX_AUTOMATIC_BACKENDS"] = ""
    env["FNX_TEST_MAX_RSS_MB"] = "4096"
    subprocess.run([str(python), "-c", "import networkx, franken_networkx; "
                    "from pathlib import Path; import hashlib; "
                    f"expected = Path({str(scratch / 'python/franken_networkx/_fnx.abi3.so')!r}).resolve(); "
                    "actual = Path(franken_networkx._fnx.__file__).resolve(); assert actual == expected; "
                    f"assert hashlib.sha256(actual.read_bytes()).hexdigest() == {hashlib.sha256(library.read_bytes()).hexdigest()!r}; "
                    "print('networkx=' + networkx.__version__); print('extension=' + str(actual))"],
                   cwd=scratch, env=env, check=True)
    tests = ["test_attr_store_and_gml_parity_regressions.py", "test_instance_dict_memory_leak.py",
             "test_error_messages.py", "test_thread_safety.py", "test_coverage_gaps.py",
             "test_delegation_ledger.py", "test_raw_vs_public_audit.py",
             "test_upstream_divergence_ledger.py", "test_api_ergonomics_audit.py",
             "test_unused_raw_exposures.py", "test_verify_docs.py"]
    if (root / "tests/python/test_set_result_iteration_order_parity.py").is_file():
        tests.append("test_set_result_iteration_order_parity.py")
    def protect_test_process():
        resource.setrlimit(resource.RLIMIT_AS, (16 * 1024**3, 16 * 1024**3))

    subprocess.run([str(python), "-m", "pytest", "-q", "--durations=10",
                    f"--junitxml={scratch / 'pytest.xml'}", *[str(root / "tests/python" / test) for test in tests]],
                   cwd=scratch, env=env, check=True, timeout=600,
                   preexec_fn=protect_test_process)
    subprocess.run([str(python), str(root / "scripts/verify_docs.py")], cwd=root, env=env, check=True)
    print("Python and documentation qualification complete; fuzz compilation/replay is a separate RCH gate.", flush=True)


if __name__ == "__main__":
    main()
