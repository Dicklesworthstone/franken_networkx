"""br-r37-c1-256q5: regression tests for delegation ledger.

Companion to ``scripts/delegation_ledger.py``. Locks in the runtime
probe outcomes for the families fixed by sjf4t (br-r37-c1-sjf4t) and
0x9pd (br-r37-c1-0x9pd) — if any of those wrappers regresses to nx
fallback on a previously-native shape, this test fails.
"""

from __future__ import annotations

import json
import importlib.util
import hashlib
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT = REPO_ROOT / "scripts" / "delegation_ledger.py"


@pytest.fixture(scope="module")
def analyzer():
    spec = importlib.util.spec_from_file_location("fnx_delegation_analyzer", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    "source,expected",
    [
        ("import networkx as _nx\ndef public(G):\n return _nx.algorithms.foo(G)", "nx-fallback"),
        ("from networkx.algorithms import foo as renamed\ndef public(G):\n return renamed(G)", "nx-fallback"),
        ("import networkx as oracle\ndef public(G):\n return getattr(oracle, 'foo')(G)", "nx-fallback"),
        ("import networkx as oracle\nselected = oracle.algorithms.foo\ndef public(G):\n return selected(G)", "nx-fallback"),
        ("import networkx as oracle\ndef public(G):\n selected = oracle.algorithms.foo\n return selected(G)", "nx-fallback"),
        ("import networkx as oracle\ndef public(G):\n return bridge(G)\ndef bridge(G):\n return _zzz_inproc(G)\ndef _zzz_inproc(G):\n return oracle.algorithms.foo(G)", "nx-fallback"),
        ("def public(G):\n return _zzz_inproc(G)\ndef _zzz_inproc(G):\n return sum(G)", "py-wrapper"),
        ("def public(G):\n return _call_networkx_pure_port(G)\ndef _call_networkx_pure_port(G):\n return sum(G)", "py-wrapper"),
        ("import networkx as oracle\ndef public(G):\n return first(G)\ndef first(G):\n return second(G)\ndef second(G):\n if G: return first([])\n return oracle.algorithms.foo(G)", "nx-fallback"),
        ("from franken_networkx._fnx import foo as kernel\nimport networkx as oracle\ndef public(G):\n if G: return kernel(G)\n return oracle.algorithms.foo(G)", "mixed-route"),
        ("import networkx as oracle\ndef public(G):\n def unused():\n  return oracle.algorithms.foo(G)\n return sum(G)", "py-wrapper"),
        ("import networkx as oracle\ndef public(G):\n def used():\n  return oracle.algorithms.foo(G)\n return used()", "nx-fallback"),
        ("def public(G):\n import networkx as oracle\n def used():\n  return oracle.algorithms.foo(G)\n return used()", "nx-fallback"),
        ("import networkx as oracle\ndef public(G):\n oracle = sum\n return oracle(G)", "py-wrapper"),
        ("import networkx as oracle\ndef public(oracle):\n return oracle.foo()", "py-wrapper"),
        ("import networkx as oracle\ndef public(G):\n def first():\n  selected = oracle.algorithms.foo\n  def second():\n   return selected(G)\n  return second()\n return first()", "nx-fallback"),
        ("import networkx as oracle\ndef public(G):\n return runner(oracle.algorithms.foo, G)\ndef runner(function, G):\n return function(G)", "nx-fallback"),
        ("from franken_networkx._fnx import foo as kernel\ndef public(G):\n return runner(kernel, G)\ndef runner(function, G):\n return function(G)", "rust-native"),
    ],
)
def test_reachability_follows_calls_not_helper_spelling(analyzer, source, expected):
    info = analyzer._analyze_source(source, ["public"])
    assert set(info) == {"public"}, "private graph nodes are not public ledger rows"
    assert analyzer._classify_static(info["public"]) == expected


@pytest.mark.parametrize("delegates", [True, False])
def test_existing_static_entrypoint_has_no_spelling_blind_spot(
    analyzer, tmp_path, monkeypatch, delegates
):
    helper = "oracle.algorithms.foo(G)" if delegates else "sum(G)"
    source = tmp_path / "__init__.py"
    source.write_text(
        "import networkx as oracle\ndef public(G):\n return bridge(G)\n"
        f"def bridge(G):\n return {helper}\n", encoding="utf-8"
    )
    monkeypatch.setattr(analyzer, "INIT_PATH", source)
    monkeypatch.setattr(analyzer.fnx, "__all__", ["public"])
    info = analyzer._gather_static(include_backend=False)
    assert set(info) == {"public"}
    assert analyzer._classify_static(info["public"]) == (
        "nx-fallback" if delegates else "py-wrapper"
    )


def test_static_entrypoint_follows_private_module_without_export_padding(
    analyzer, tmp_path, monkeypatch
):
    from types import ModuleType

    source = tmp_path / "__init__.py"
    source.write_text(
        "from ._hidden import bridge\ndef public(G):\n return bridge(G)\n",
        encoding="utf-8",
    )
    private_source = tmp_path / "_hidden.py"
    private_source.write_text(
        "import networkx as oracle\ndef bridge(G):\n return oracle.algorithms.foo(G)\n",
        encoding="utf-8",
    )
    private_module = ModuleType("franken_networkx._hidden")
    private_module.__file__ = str(private_source)
    original_import = analyzer.importlib.import_module

    def import_source(name):
        if name == private_module.__name__:
            return private_module
        return original_import(name)

    monkeypatch.setattr(analyzer, "INIT_PATH", source)
    monkeypatch.setattr(analyzer.fnx, "__all__", ["public"])
    monkeypatch.setattr(analyzer.importlib, "import_module", import_source)
    info = analyzer._gather_static(include_backend=False)
    assert set(info) == {"public"}
    assert analyzer._classify_static(info["public"]) == "nx-fallback"
    assert "franken_networkx._hidden.bridge" in info["public"].reachable_helpers


def test_observer_detects_direct_networkx_algorithm(analyzer):
    import networkx as nx

    graph = nx.path_graph(5)

    def innocently_renamed():
        return nx.shortest_path(graph, 0, 4, backend="networkx")

    probe = analyzer._observe_callable(innocently_renamed)
    assert probe.error is None
    assert probe.networkx_frames > 0
    assert probe.networkx_algorithm_frames > 0
    assert probe.classification == "nx-fallback"


def test_observer_does_not_confuse_pure_inproc_with_delegation(analyzer):
    def _zzz_inproc():
        return sum(range(5))

    probe = analyzer._observe_callable(_zzz_inproc)
    assert probe.error is None
    assert probe.networkx_frames == 0
    assert probe.classification == "py-wrapper-only"


def test_observer_consumes_lazy_algorithm_results(analyzer):
    import networkx as nx

    graph = nx.path_graph(5)

    def lazy_route():
        yield from nx.all_pairs_shortest_path_length(graph, backend="networkx")

    probe = analyzer._observe_callable(lazy_route)
    assert probe.error is None
    assert probe.networkx_algorithm_frames > 0
    assert probe.classification == "nx-fallback"


def test_relative_package_alias_reachability(analyzer):
    sources = {
        "franken_networkx": "from .nested import public",
        "franken_networkx.nested": "from .helpers import bridge\ndef public(G):\n return bridge(G)",
        "franken_networkx.nested.helpers": "import networkx as oracle\ndef bridge(G):\n return oracle.algorithms.foo(G)",
    }
    graph = analyzer._CallGraph(sources, packages={"franken_networkx", "franken_networkx.nested"})
    info = graph.analyze({"nested.public": {"franken_networkx.nested.public"}})
    assert analyzer._classify_static(info["nested.public"]) == "nx-fallback"


def test_observer_releases_monitoring_id_after_error(analyzer):
    before = [sys.monitoring.get_tool(i) for i in range(6)]
    calls = 0

    def fail_after_warm():
        nonlocal calls
        calls += 1
        if calls == 2:
            raise ValueError("observed failure")

    probe = analyzer._observe_callable(fail_after_warm)
    assert probe.classification == "error"
    assert probe.error == "ValueError: observed failure"
    assert [sys.monitoring.get_tool(i) for i in range(6)] == before


def test_metadata_does_not_turn_local_code_into_networkx_identity(analyzer):
    def local_port():
        return sum(range(5))

    local_port.__module__ = "networkx.algorithms.shortest_paths"
    assert not analyzer._object_targets(local_port)


def test_partial_default_generation_preserves_authoritative_docs(analyzer):
    paths = [REPO_ROOT / "docs" / ("delegation_ledger." + suffix) for suffix in ("json", "md")]
    before = [path.read_bytes() for path in paths]
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--quiet"], capture_output=True, text=True, timeout=120
    )
    assert result.returncode == 2, result.stderr
    assert "refusing to replace authoritative docs" in result.stderr
    assert [path.read_bytes() for path in paths] == before


def test_observer_sees_native_reexport_without_raw_alias(analyzer):
    probe = analyzer._observe_callable(analyzer.fnx._fnx.path_graph, 5)
    assert probe.error is None
    assert probe.raw_called
    assert probe.networkx_algorithm_frames == 0
    assert probe.classification == "rust-native"


def test_census_requires_the_registered_backend_callable(analyzer):
    public = analyzer.RuntimeProbe(name="astar_path_length", shape_id="public-call")
    census = analyzer._census_coverage([public])
    assert "astar_path_length" not in census["observed"]
    assert "astar_path_length" in census["missing"]
    registered = analyzer.RuntimeProbe(
        name="backend.BackendInterface.astar_path_length", shape_id="registry-call"
    )
    census = analyzer._census_coverage([public, registered])
    assert census["observed"] == ["astar_path_length"]
    registered.error = "invalid fixture"
    assert not analyzer._census_coverage([registered])["observed"]


@pytest.fixture(scope="module")
def ledger_output(tmp_path_factory):
    out_dir = tmp_path_factory.mktemp("delegation_ledger")
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--quiet", "--output-dir", str(out_dir)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 2, f"expected explicitly INCOMPLETE census, stderr: {result.stderr}"
    js = out_dir / "delegation_ledger.json"
    md = out_dir / "delegation_ledger.md"
    assert js.exists()
    assert md.exists()
    ledger = json.loads(js.read_text(encoding="utf-8"))
    assert ledger["status"] == "INCOMPLETE"
    assert ledger["unimplemented_checks"], "observed fixtures cannot certify always/never routing"
    return ledger


def _runtime_by_key(ledger):
    return {
        (probe["name"], probe["shape"]): probe
        for probe in ledger["runtime"]
    }


@pytest.mark.parametrize(
    "name,shape",
    [
        ("single_source_dijkstra_path_length", "path-5-unweighted"),
        ("single_source_dijkstra_path_length", "path-5-weighted-kwargs"),
        ("single_source_dijkstra_path_length", "path-5-weighted-postmut"),
        ("single_source_bellman_ford_path_length", "path-5-unweighted"),
        ("single_source_bellman_ford_path_length", "path-5-weighted-kwargs"),
        ("single_source_bellman_ford_path_length", "path-5-weighted-postmut"),
        ("astar_path_length", "path-5-unweighted"),
        ("astar_path_length", "path-5-weighted-kwargs"),
        ("astar_path_length", "path-5-weighted-postmut"),
        ("shortest_path_length", "path-5-weighted-kwargs"),
        ("shortest_path_length", "path-5-weighted-postmut"),
    ],
)
def test_no_nx_fallback_on_sjf4t_protected_shapes(ledger_output, name, shape):
    """The sjf4t (br-r37-c1-sjf4t) and 0x9pd (br-r37-c1-0x9pd) fixes
    sync edge attrs to Rust before native algorithm calls. Verify
    that the Rust path is taken for all shapes the fixes cover —
    if any of these regresses to nx fallback, the perf gain is gone.
    """
    runtime = _runtime_by_key(ledger_output)
    probe = runtime.get((name, shape))
    assert probe is not None, f"no probe for {(name, shape)}"
    assert probe["error"] is None, f"probe error: {probe['error']}"
    assert probe["classification"] == "rust-native", (
        f"{name}/{shape} regressed to {probe['classification']}: "
        f"raw={probe['raw_called']}, parity={probe['parity_called_with_target']}"
    )


def test_static_classification_summary_shape(ledger_output):
    """Smoke: static section is well-formed and returns sensible counts."""
    static = ledger_output["static"]
    assert isinstance(static, list)
    assert len(static) >= 1000, f"only {len(static)} static entries"
    classifications = {entry["classification"] for entry in static}
    expected = {"rust-reexport", "rust-native", "mixed-route", "nx-fallback", "py-wrapper"}
    assert classifications & expected == expected, (
        f"missing classifications: {expected - classifications}"
    )


def test_public_scope_and_runtime_static_cross_check(ledger_output):
    import franken_networkx as fnx
    from franken_networkx.backend import _SUPPORTED_ALGORITHMS

    static = {entry["name"]: entry for entry in ledger_output["static"]}
    top_level = {name for name in fnx.__all__ if callable(getattr(fnx, name))}
    assert {name for name in static if "." not in name} == top_level
    assert not any(name.startswith("_") for name in static)
    assert "approximation.min_weighted_vertex_cover" in static
    assert "community.louvain_communities" in static
    for probe in ledger_output["runtime"]:
        assert probe["error"] is None
        if probe["networkx_algorithm_frames"]:
            assert static[probe["name"]]["calls_parity_helper"]
    census = ledger_output["census"]
    assert set(census["required"]) == set(_SUPPORTED_ALGORITHMS)
    backend_prefix = "backend.BackendInterface."
    registry_observations = {
        probe["name"].removeprefix(backend_prefix)
        for probe in ledger_output["runtime"]
        if probe["error"] is None and probe["name"].startswith(backend_prefix)
    }
    assert set(census["observed"]) == registry_observations
    assert set(census["observed"]) | set(census["missing"]) == set(census["required"])
    assert not (set(census["observed"]) & set(census["missing"]))
    attempts = ledger_output["census_attempts"]
    assert {row["name"] for row in attempts} == set(_SUPPORTED_ALGORITHMS)
    assert all(row["name"] in census["observed"] for row in attempts if row["status"] == "observed")
    assert any(row["status"] == "needs-explicit-fixture" for row in attempts)
    assert ledger_output["provenance"]["loaded_shim_sha256"] == ledger_output["provenance"]["checkout_shim_sha256"]
    package_sources = ledger_output["provenance"]["package_sources"]
    assert package_sources
    assert all(row["loaded_sha256"] == row["checkout_sha256"] for row in package_sources)


@pytest.mark.parametrize(
    "name,args,kwargs,directed",
    [
        ("single_source_dijkstra_path_length", (0,), {}, False),
        ("single_source_bellman_ford_path_length", (0,), {}, False),
        ("astar_path_length", (0, 3), {}, False),
        ("shortest_path_length", (0, 3), {"weight": "weight"}, False),
        ("floyd_warshall", (), {}, False),
        ("simple_cycles", (), {}, True),
        ("community.louvain_communities", (), {"seed": 7}, False),
    ],
)
@pytest.mark.parametrize("route", ["public", "backend"])
def test_public_route_e2e_against_live_networkx(
    analyzer, ledger_output, tmp_path, name, args, kwargs, directed, route
):
    import franken_networkx as fnx
    import networkx as nx

    edges = [(i, (i + 1) % 6, {"weight": i + 0.5}) for i in range(6)]
    input_bytes = json.dumps(
        {"directed": directed, "edges": edges, "args": args, "kwargs": kwargs}, sort_keys=True
    ).encode()
    graph_package = fnx if route == "public" else nx
    actual_graph = (graph_package.DiGraph if directed else graph_package.Graph)(edges)
    expected_graph = (nx.DiGraph if directed else nx.Graph)(edges)
    actual_function, expected_function = fnx, nx
    for part in name.split("."):
        actual_function = getattr(actual_function, part)
        expected_function = getattr(expected_function, part)
    actual_kwargs = kwargs
    if route == "backend":
        actual_function = expected_function
        actual_kwargs = {**kwargs, "backend": "franken_networkx"}

    def normalize(value):
        if isinstance(value, dict):
            return {key: normalize(item) for key, item in value.items()}
        if isinstance(value, (set, frozenset)):
            return sorted(value)
        if isinstance(value, (list, tuple)) or hasattr(value, "__next__"):
            return [normalize(item) for item in value]
        return value

    started = time.perf_counter()
    with nx.config(backend_priority={}):
        expected = normalize(expected_function(expected_graph, *args, **kwargs, backend="networkx"))
        actual = normalize(actual_function(actual_graph, *args, **actual_kwargs))
        probe = analyzer._observe_callable(actual_function, actual_graph, *args, **actual_kwargs)
    static = {row["name"]: row for row in ledger_output["static"]}
    assert probe.error is None
    if probe.networkx_algorithm_frames:
        assert static[name]["calls_parity_helper"]
    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "case_id": route + ":" + name,
        "input_sha256": hashlib.sha256(input_bytes).hexdigest(),
        "fnx_version": fnx.__version__,
        "nx_version": nx.__version__,
        "so_sha256": hashlib.sha256(Path(fnx._fnx.__file__).read_bytes()).hexdigest(),
        "graph_class": type(actual_graph).__name__,
        "construction_path": "edge-stream-constructor" if route == "public" else "networkx-edge-stream/backend-conversion",
        "expected": expected,
        "actual": actual,
        "pass": actual == expected,
        "duration_ms": (time.perf_counter() - started) * 1000,
        "networkx_frames": probe.networkx_frames,
        "networkx_algorithm_frames": probe.networkx_algorithm_frames,
    }
    if actual != expected:
        record["reproducer"] = f"{route}:{name}, edges={edges!r}, args={args!r}, kwargs={actual_kwargs!r}"
    log_path = Path(os.environ.get("FNX_DELEGATION_E2E_LOG", str(tmp_path / "routes.jsonl")))
    with log_path.open("a", encoding="utf-8") as log:
        log.write(json.dumps(record, sort_keys=True) + "\n")
    assert actual == expected


def test_verify_docs_rejects_planted_readme_numeric_drift():
    spec = importlib.util.spec_from_file_location(
        "fnx_verify_docs", REPO_ROOT / "scripts" / "verify_docs.py"
    )
    verify_docs = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = verify_docs
    spec.loader.exec_module(verify_docs)

    assert verify_docs.verify_doc_truth_invariants() == []

    real_readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    drifted = real_readme.replace("843 `franken_networkx.__all__`", "839 `franken_networkx.__all__`")
    drifted = drifted.replace("315 algorithms in `backend.py`", "313 algorithms in `backend.py`")
    failures = verify_docs.verify_doc_truth_invariants(readme_text=drifted)
    assert any("claims 839 __all__ exports" in f for f in failures), failures
    assert any("claims 313 backend algorithms" in f for f in failures), failures

