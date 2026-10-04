#!/usr/bin/env python3
"""Verify published DSR wheels without building, installing or removing files.

Recovered from the release-wave consumer harness. Publication checks and the
optional installed-consumer smoke are separate proof boundaries. Every fetched
artifact is retained in a new, caller-selected evidence directory.
"""

import argparse
import hashlib
import hmac
import importlib.metadata
import json
import os
import re
import subprocess
import sys
import urllib.parse
import urllib.request
from pathlib import Path

UA = "OpenAI File Downloader, XaiImageApiFetch/1.0"
REPOSITORY = "Dicklesworthstone/franken_networkx"
PLATFORMS = (
    "macosx_10_12_x86_64", "macosx_11_0_arm64",
    "manylinux_2_17_aarch64.manylinux2014_aarch64",
    "manylinux_2_17_x86_64.manylinux2014_x86_64",
    "musllinux_1_2_x86_64", "win_amd64",
)
HOSTS = {
    "api.github.com", "github.com", "release-assets.githubusercontent.com",
    "objects.githubusercontent.com", "pypi.org", "files.pythonhosted.org",
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def wheel_names(version):
    return {f"franken_networkx-{version}-cp310-abi3-{tag}.whl" for tag in PLATFORMS}


def payload_names(version):
    archives = {
        f"franken-networkx-{version}-{tag}.tar.gz"
        for tag in ("darwin-amd64", "darwin-arm64", "linux-amd64", "linux-arm64")
    }
    return archives | wheel_names(version) | {
        f"franken-networkx-{version}-windows-amd64.zip",
        f"franken_networkx-{version}.tar.gz",
    }


def parse_manifest(text):
    result = {}
    for line in text.splitlines():
        match = re.fullmatch(r"([0-9a-fA-F]{64})[ \t]+\*?([A-Za-z0-9_.-]+)", line)
        require(match is not None, "malformed signed checksum row")
        name = match[2]
        require(name not in result and name not in {".", ".."}, "duplicate or unsafe checksum name")
        result[name] = match[1].lower()
    require(result, "empty signed manifest")
    return result


def validate_registry(metadata, version, manifest):
    rows = metadata["urls"]
    require(metadata["info"]["version"] == version, "PyPI version differs")
    names = [row["filename"] for row in rows]
    require(len(names) == len(set(names)) == len(PLATFORMS)
            and set(names) == wheel_names(version), "PyPI six-wheel contract differs")
    for row in rows:
        require(row["packagetype"] == "bdist_wheel" and not row["yanked"], "yanked or non-wheel publication")
        expected = manifest.get(row["filename"])
        actual = row["digests"]["sha256"]
        require(isinstance(actual, str) and re.fullmatch(r"[0-9a-f]{64}", actual)
                and expected is not None and hmac.compare_digest(expected, actual),
                "PyPI digest differs from signed DSR manifest")
    return rows


def check_url(url):
    parsed = urllib.parse.urlsplit(url)
    require(parsed.scheme == "https" and parsed.hostname in HOSTS
            and parsed.port in (None, 443) and not parsed.username and not parsed.password,
            "unexpected public download URL")


class PublicRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, newurl):
        check_url(newurl)
        return super().redirect_request(request, response, code, message, headers, newurl)


def fetch(url):
    check_url(url)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), PublicRedirect())
    request = urllib.request.Request(url, headers={"User-Agent": UA})
    with opener.open(request, timeout=60) as response:
        check_url(response.url)
        data = response.read(128 * 1024 * 1024 + 1)
    require(len(data) <= 128 * 1024 * 1024, "download exceeds 128 MiB limit")
    return data


def save(path, data):
    with path.open("xb") as output:
        output.write(data)


def consumer_smoke(version):
    """Run only in the explicitly supplied interpreter's installed prefix."""
    import franken_networkx as fnx
    import franken_networkx._fnx as native
    import networkx as nx
    import numpy as np
    import scipy.sparse as sp

    prefix = Path(sys.prefix).resolve()
    for module in (fnx, native):
        require(prefix in Path(module.__file__).resolve().parents, "consumer imported outside interpreter prefix")
    require(importlib.metadata.version("franken-networkx") == version, "installed consumer version differs")
    graph = fnx.Graph()
    graph.add_weighted_edges_from([(0, 1, 2), (1, 2, 3), (0, 2, 9)])
    require(fnx.shortest_path_length(graph, 0, 2, weight="weight") == 5, "weighted shortest path failed")
    require(sorted(fnx.minimum_spanning_tree(graph, weight="weight").edges()) == [(0, 1), (1, 2)], "spanning tree failed")
    wide = 2 ** 63
    matrix = np.array([[0, wide], [wide, 0]], dtype=np.uint64)
    for constructor, value in (
        (fnx.from_numpy_array, matrix),
        (fnx.from_scipy_sparse_array, sp.coo_array(matrix)),
        (fnx.from_scipy_sparse_array, sp.csr_array(matrix)),
    ):
        for graph_type in (fnx.Graph, fnx.DiGraph):
            weight = constructor(value, create_using=graph_type)[0][1]["weight"]
            require(int(weight) == wide and not isinstance(weight, str), "uint64 conversion lost numeric identity")
    entries = importlib.metadata.entry_points(group="networkx.backends")
    require(next(row for row in entries if row.name == "franken_networkx").load() is not None, "backend entry point failed")
    info = next(row for row in importlib.metadata.entry_points(group="networkx.backend_info")
                if row.name == "franken_networkx").load()()
    require(isinstance(info, dict), "backend information entry point failed")
    require(nx.shortest_path(nx.path_graph(4), 0, 3, backend="franken_networkx") == [0, 1, 2, 3], "NetworkX dispatch failed")
    return {"version": version, "native": str(native.__file__), "networkx": nx.__version__}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True)
    parser.add_argument("--source-commit", required=True, help="expected 40-character published source commit")
    parser.add_argument("--evidence-dir", type=Path, required=True, help="new directory; all downloads are retained")
    parser.add_argument("--public-key", type=Path, default=Path(__file__).resolve().parents[1] / "minisign.pub")
    parser.add_argument("--python", type=Path, help="optional already-installed consumer interpreter; nothing is installed")
    options = parser.parse_args()
    require(re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", options.version), "version must be numeric major.minor.patch")
    require(re.fullmatch(r"[0-9a-f]{40}", options.source_commit), "expected source must be a full commit ID")
    evidence = options.evidence_dir.resolve()
    evidence.mkdir(mode=0o700, parents=True)
    receipt = {"version": options.version, "expected_source_commit": options.source_commit,
               "status": "FAIL", "consumer": "not_run", "upgrade": "not_run"}
    try:
        tag = "v" + options.version
        refs = subprocess.check_output([
            "git", "-c", "http.userAgent=" + UA, "ls-remote",
            "https://github.com/" + REPOSITORY + ".git", "refs/tags/" + tag, "refs/tags/" + tag + "^{}",
        ], text=True, timeout=60)
        tag_rows = dict((name, sha) for sha, name in (line.split() for line in refs.splitlines()))
        require(tag_rows.get("refs/tags/" + tag + "^{}", tag_rows.get("refs/tags/" + tag)) == options.source_commit,
                "public tag differs from expected source")
        raw = fetch("https://api.github.com/repos/" + REPOSITORY + "/releases/tags/" + tag)
        save(evidence / "release.json", raw)
        release = json.loads(raw)
        require(not release["draft"] and not release["prerelease"] and release["published_at"]
                and release["tag_name"] == tag, "release is not a published stable tag")
        names = [row["name"] for row in release["assets"]]
        payloads = payload_names(options.version)
        expected = {name + suffix for name in payloads for suffix in ("", ".sha256", ".minisig")}
        expected |= {"SHA256SUMS", "SHA256SUMS.minisig"}
        require(len(names) == len(set(names)) and set(names) == expected, "DSR asset inventory differs")
        assets = {row["name"]: row for row in release["assets"]}
        for name in ("SHA256SUMS", "SHA256SUMS.minisig"):
            save(evidence / name, fetch(assets[name]["browser_download_url"]))
        key = options.public_key.read_bytes()
        save(evidence / "minisign.pub", key)
        subprocess.run(["minisign", "-V", "-p", str(evidence / "minisign.pub"),
                        "-m", str(evidence / "SHA256SUMS"), "-x", str(evidence / "SHA256SUMS.minisig")],
                       check=True, timeout=60)
        manifest = parse_manifest((evidence / "SHA256SUMS").read_text())
        require(set(manifest) == payloads, "signed twelve-payload inventory differs")
        raw = fetch("https://pypi.org/pypi/franken-networkx/" + options.version + "/json")
        save(evidence / "pypi.json", raw)
        rows = validate_registry(json.loads(raw), options.version, manifest)
        wheels = []
        for row in rows:
            data = fetch(row["url"])
            digest = hashlib.sha256(data).hexdigest()
            require(hmac.compare_digest(digest, manifest[row["filename"]])
                    and len(data) == row["size"], "actual PyPI wheel bytes differ")
            save(evidence / row["filename"], data)
            wheels.append({"filename": row["filename"], "sha256": digest, "bytes": len(data)})
        if options.python:
            env = {name: value for name, value in os.environ.items()
                   if not name.startswith(("PYTHON", "FNX_", "NETWORKX_"))}
            script = "import runpy; m=runpy.run_path(" + repr(str(Path(__file__).resolve())) + "); import json; print(json.dumps(m['consumer_smoke'](" + repr(options.version) + ")))"
            # Keep a virtual environment's executable symlink: resolving it
            # would invoke the base interpreter and lose the installed prefix.
            result = subprocess.check_output([str(options.python.absolute()), "-I", "-B", "-c", script],
                                             cwd=evidence, env=env, text=True, timeout=60)
            receipt["consumer"] = json.loads(result)
        receipt.update(status="published_wheel_bytes_verified", release=release["html_url"],
                       source_commit=options.source_commit, public_key_sha256=hashlib.sha256(key).hexdigest(),
                       wheels=wheels, scope="six PyPI wheel byte hashes plus DSR signed publication; no build/install/upgrade")
    except Exception as error:
        receipt["error"] = str(error)
        raise
    finally:
        save(evidence / "receipt.json", (json.dumps(receipt, indent=2) + "\n").encode())
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
