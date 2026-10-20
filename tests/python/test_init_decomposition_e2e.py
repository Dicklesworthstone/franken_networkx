"""br-r37-c1-rc0923-epic-docs-truth-structure-8813x.3 — Isomorphic decomposition
of ``python/franken_networkx/__init__.py`` into ``_impl/s*.py`` modules.

Verifies:
1. ``python/franken_networkx/__init__.py`` is a lightweight loader (< 100 lines)
   backed by bounded ``python/franken_networkx/_impl/s*.py`` modules (<= 1,600
   lines each) so static analyzers (``ubs python/franken_networkx/``) complete
   without module timeout.
2. The live package identity manifest (all 843 ``__all__`` exports, ``dir(fnx)``,
   all 94 public submodules, ``__module__``, ``__qualname__``, ``inspect.signature``,
   ``is`` identity with ``networkx``, and class/function/instance pickle
   round-trips) matches the frozen pre-decomposition manifest
   ``artifacts/conformance/init_identity_manifest_v1.json`` byte-for-byte.
3. Negative case: moving a class into an ``_impl`` module without preserving
   ``__module__ == "franken_networkx"`` fails the identity manifest and breaks
   ``pickle.dumps`` of instances.
4. Package ``type(fnx)`` and ``type(fnx.algorithms)`` are plain ``types.ModuleType``
   (no custom ``__getattribute__`` module-class swap), and ``fnx.<attr>`` lookup
   is within ``<= 1.1x`` of ``nx.<attr>`` in-process.
5. E2E parity across public ``fnx`` and ``nx(..., backend="franken_networkx")``
   routes across ``Graph``, ``DiGraph``, ``MultiGraph``, and ``MultiDiGraph``,
   emitting structured JSONL records to ``artifacts/e2e/init_decomposition_e2e.jsonl``.
"""

from __future__ import annotations

import hashlib
import importlib
import inspect
import json
import os
import pickle
import pkgutil
import re
import time
import types
from datetime import datetime, timezone
from pathlib import Path

import networkx as nx
import pytest

import franken_networkx as fnx

REPO_ROOT = Path(__file__).resolve().parents[2]
PKG_DIR = REPO_ROOT / "python" / "franken_networkx"
IMPL_DIR = PKG_DIR / "_impl"
MANIFEST_PATH = REPO_ROOT / "artifacts" / "conformance" / "init_identity_manifest_v1.json"
DEFAULT_E2E_LOG = REPO_ROOT / "artifacts" / "e2e" / "init_decomposition_e2e.jsonl"


def _sig_text(obj) -> str | None:
    try:
        return re.sub(r" at 0x[0-9a-fA-F]+", "", str(inspect.signature(obj)))
    except Exception:  # noqa: BLE001
        return None


def _pickle_roundtrip_ok(obj) -> bool:
    try:
        data = pickle.dumps(obj)
        restored = pickle.loads(data)
        return restored is obj or type(restored) is type(obj)
    except Exception:  # noqa: BLE001
        return False


def _str_attr(obj, attr: str) -> str | None:
    try:
        val = inspect.getattr_static(obj, attr, getattr(obj, attr, None))
    except Exception:  # noqa: BLE001
        val = None
    if not isinstance(val, str):
        val = getattr(obj, attr, None)
    return val if isinstance(val, str) else None


def _describe_symbol(name: str, obj, nx_mod) -> dict:
    nx_obj = getattr(nx_mod, name, None) if nx_mod is not None else None
    obj_type = type(obj)
    return {
        "type": f"{obj_type.__module__}.{obj_type.__qualname__}",
        "module": _str_attr(obj, "__module__"),
        "qualname": _str_attr(obj, "__qualname__") or _str_attr(obj, "__name__"),
        "is_nx_object": bool(nx_obj is not None and obj is nx_obj),
        "signature": _sig_text(obj) if (callable(obj) or inspect.isclass(obj)) else None,
        "pickle_roundtrip": _pickle_roundtrip_ok(obj),
    }


def build_live_identity_manifest() -> dict:
    root_entries = {
        name: _describe_symbol(name, getattr(fnx, name), nx)
        for name in fnx.__all__
    }
    submodules = {}
    for info in sorted(
        pkgutil.walk_packages(fnx.__path__, "franken_networkx."),
        key=lambda item: item.name,
    ):
        rel = info.name.removeprefix("franken_networkx.")
        if any(p.startswith("_") or p == "tests" for p in rel.split(".")):
            continue
        try:
            mod = importlib.import_module(info.name)
        except Exception:  # noqa: BLE001
            continue
        try:
            nx_mod = importlib.import_module("networkx." + rel)
        except Exception:  # noqa: BLE001
            nx_mod = None
        names = getattr(mod, "__all__", None)
        if names is None:
            names = [n for n in dir(mod) if not n.startswith("_")]
        submodules[info.name] = {
            n: _describe_symbol(n, getattr(mod, n), nx_mod)
            for n in sorted(set(names))
            if hasattr(mod, n)
        }

    instance_pickles = {}
    for cls_name in ("Graph", "DiGraph", "MultiGraph", "MultiDiGraph"):
        cls = getattr(fnx, cls_name)
        g = cls()
        g.add_edge("a", "b", weight=2.5)
        g2 = pickle.loads(pickle.dumps(g))
        sub_g = pickle.loads(pickle.dumps(g.subgraph(["a"])))
        instance_pickles[cls_name] = {
            "restored_class": f"{type(g2).__module__}.{type(g2).__qualname__}",
            "edges": sorted((u, v) for u, v in g2.edges()),
            "sub_restored_class": f"{type(sub_g).__module__}.{type(sub_g).__qualname__}",
        }

    return {
        "schema_version": 1,
        "fnx_version": fnx.__version__,
        "nx_version": nx.__version__,
        "all_list": list(fnx.__all__),
        "public_dir": sorted(n for n in dir(fnx) if not n.startswith("_")),
        "root_exports": root_entries,
        "submodules": submodules,
        "instance_pickles": instance_pickles,
    }


def test_init_py_is_decomposed_into_bounded_impl_modules() -> None:
    """Negative gate on the pre-fix 76,854-line monolith: __init__.py must be
    < 100 lines and every _impl/s*.py module must be <= 1,600 lines."""
    init_lines = len((PKG_DIR / "__init__.py").read_text(encoding="utf-8").splitlines())
    assert init_lines < 100, (
        f"python/franken_networkx/__init__.py has {init_lines} lines (expected < 100)"
    )
    parts = sorted(IMPL_DIR.glob("s*.py"))
    assert len(parts) >= 40, f"expected >= 40 _impl modules, found {len(parts)}"
    for part in parts:
        line_count = len(part.read_text(encoding="utf-8").splitlines())
        assert 1 <= line_count <= 1600, (
            f"{part.name} has {line_count} lines (expected <= 1600 for ubs taint_py budget)"
        )


def test_identity_manifest_matches_frozen_baseline() -> None:
    """Every public export, submodule member, signature, __module__, and pickle
    round-trip must match the pre-decomposition manifest."""
    expected_bytes = MANIFEST_PATH.read_bytes()
    expected = json.loads(expected_bytes.decode("utf-8"))
    actual_raw = build_live_identity_manifest()
    actual_bytes = (json.dumps(actual_raw, indent=2, sort_keys=True) + "\n").encode("utf-8")
    actual = json.loads(actual_bytes.decode("utf-8"))
    assert actual["all_list"] == expected["all_list"]
    assert actual["public_dir"] == expected["public_dir"]
    assert actual["instance_pickles"] == expected["instance_pickles"]
    assert actual["root_exports"] == expected["root_exports"]
    assert actual["submodules"] == expected["submodules"]
    assert hashlib.sha256(actual_bytes).hexdigest() == hashlib.sha256(expected_bytes).hexdigest()


def test_negative_unpreserved_module_path_breaks_manifest_and_pickling() -> None:
    """Negative case required by 8813x.3: if a class moved to an _impl module
    without preserving ``__module__ == 'franken_networkx'``, instance pickling
    and manifest verification fail."""
    UnpreservedClass = type(
        "SpanningTreeIterator",
        (),
        {"__module__": "franken_networkx._impl._unregistered_part"},
    )
    desc = _describe_symbol("SpanningTreeIterator", UnpreservedClass, nx)
    expected = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))["root_exports"][
        "SpanningTreeIterator"
    ]
    assert desc["module"] != expected["module"]
    assert desc["pickle_roundtrip"] is False
    instance = UnpreservedClass()
    with pytest.raises((pickle.PicklingError, ModuleNotFoundError, AttributeError)):
        pickle.loads(pickle.dumps(instance))


def test_no_module_class_swap_and_attribute_lookup_parity() -> None:
    """type(fnx) and type(fnx.algorithms) must be plain ModuleType and
    attribute lookup on fnx must be <= 1.1x nx in-process."""
    assert type(fnx) is types.ModuleType
    assert type(fnx.algorithms) is types.ModuleType
    assert callable(fnx.bridges)
    assert callable(fnx.reciprocity)
    assert callable(fnx.algorithms.bridges)
    assert callable(fnx.algorithms.reciprocity)

    # Warm lookup caches
    for _ in range(1000):
        _ = fnx.shortest_path
        _ = nx.shortest_path

    iters = 200_000
    best_ratio = float("inf")
    for _ in range(5):
        t0 = time.perf_counter_ns()
        for _ in range(iters):
            _ = fnx.shortest_path
            _ = fnx.Graph
            _ = fnx.bridges
            _ = fnx.reciprocity
        fnx_ns = time.perf_counter_ns() - t0

        t1 = time.perf_counter_ns()
        for _ in range(iters):
            _ = nx.shortest_path
            _ = nx.Graph
            _ = nx.bridges
            _ = nx.reciprocity
        nx_ns = max(1, time.perf_counter_ns() - t1)
        best_ratio = min(best_ratio, fnx_ns / nx_ns)

    assert best_ratio <= 1.10, (
        f"fnx.<attr> lookup ratio vs nx.<attr> was {best_ratio:.3f}x (expected <= 1.10x)"
    )


@pytest.mark.parametrize(
    "case_id,cls_name,route",
    [
        ("ba_shortest_path_graph_public", "Graph", "public"),
        ("ba_shortest_path_graph_backend", "Graph", "backend"),
        ("gnp_dijkstra_digraph_public", "DiGraph", "public"),
        ("gnp_dijkstra_digraph_backend", "DiGraph", "backend"),
        ("multigraph_components_public", "MultiGraph", "public"),
        ("multigraph_components_backend", "MultiGraph", "backend"),
        ("multidigraph_pagerank_public", "MultiDiGraph", "public"),
        ("multidigraph_pagerank_backend", "MultiDiGraph", "backend"),
    ],
)
def test_init_decomposition_e2e_routes_and_jsonl_log(
    case_id: str, cls_name: str, route: str
) -> None:
    """E2E check across public fnx and nx backend dispatch on realistic graphs,
    emitting structured JSONL telemetry."""
    base = nx.barabasi_albert_graph(60, 3, seed=42)
    edges = []
    for u, v in base.edges():
        w = float(((u * 13 + v * 7) % 19) + 1) / 4.0
        edges.append((u, v, {"weight": w}))
    # Add disconnected component and self-loop
    edges.append((60, 61, {"weight": 1.25}))
    edges.append((0, 0, {"weight": 0.5}))

    nx_cls = getattr(nx, cls_name)
    fnx_cls = getattr(fnx, cls_name)
    g_nx = nx_cls()
    g_nx.add_nodes_from(range(63))
    for u, v, d in edges:
        g_nx.add_edge(u, v, **d)
        if cls_name in ("MultiGraph", "MultiDiGraph") and (u + v) % 11 == 0:
            g_nx.add_edge(u, v, weight=d["weight"] + 0.75)

    g_fnx = fnx_cls()
    g_fnx.add_nodes_from(range(63))
    for u, v, d in edges:
        g_fnx.add_edge(u, v, **d)
        if cls_name in ("MultiGraph", "MultiDiGraph") and (u + v) % 11 == 0:
            g_fnx.add_edge(u, v, weight=d["weight"] + 0.75)

    input_payload = json.dumps(
        {"case_id": case_id, "cls_name": cls_name, "route": route, "n": 63, "m": g_nx.number_of_edges()},
        sort_keys=True,
    ).encode("utf-8")

    started = time.perf_counter()
    with nx.config(backend_priority={}):
        if "shortest_path" in case_id:
            expected = nx.shortest_path_length(g_nx, source=0, weight="weight", backend="networkx")
            if route == "public":
                actual = fnx.shortest_path_length(g_fnx, source=0, weight="weight")
            else:
                actual = nx.shortest_path_length(
                    g_nx, source=0, weight="weight", backend="franken_networkx"
                )
        elif "dijkstra" in case_id:
            expected = nx.single_source_dijkstra_path_length(
                g_nx, source=0, weight="weight", backend="networkx"
            )
            if route == "public":
                actual = fnx.single_source_dijkstra_path_length(g_fnx, source=0, weight="weight")
            else:
                actual = nx.single_source_dijkstra_path_length(
                    g_nx, source=0, weight="weight", backend="franken_networkx"
                )
        elif "components" in case_id:
            expected = sorted(sorted(c) for c in nx.connected_components(g_nx, backend="networkx"))
            if route == "public":
                actual = sorted(sorted(c) for c in fnx.connected_components(g_fnx))
            else:
                actual = sorted(
                    sorted(c)
                    for c in nx.connected_components(g_nx, backend="franken_networkx")
                )
        else:
            exp_pr = nx.pagerank(g_nx, weight="weight", backend="networkx")
            if route == "public":
                act_pr = fnx.pagerank(g_fnx, weight="weight")
            else:
                act_pr = nx.pagerank(g_nx, weight="weight", backend="franken_networkx")
            expected = {k: round(v, 8) for k, v in sorted(exp_pr.items())}
            actual = {k: round(v, 8) for k, v in sorted(act_pr.items())}

    duration_ms = (time.perf_counter() - started) * 1000.0
    passed = actual == expected
    so_path = Path(fnx._fnx.__file__).resolve()
    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "case_id": case_id,
        "input_sha256": hashlib.sha256(input_payload).hexdigest(),
        "fnx_version": fnx.__version__,
        "nx_version": nx.__version__,
        "so_sha256": hashlib.sha256(so_path.read_bytes()).hexdigest(),
        "graph_class": cls_name,
        "construction_path": "fnx-direct" if route == "public" else "nx-backend-dispatch",
        "expected": expected,
        "actual": actual,
        "pass": passed,
        "duration_ms": round(duration_ms, 4),
    }
    if not passed:
        record["reproducer"] = f"pytest tests/python/test_init_decomposition_e2e.py -k {case_id}"

    log_path = Path(os.environ.get("FNX_INIT_DECOMP_E2E_LOG", str(DEFAULT_E2E_LOG)))
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, sort_keys=True) + "\n")

    assert passed, f"Mismatch on {case_id}: expected={expected}, actual={actual}"
