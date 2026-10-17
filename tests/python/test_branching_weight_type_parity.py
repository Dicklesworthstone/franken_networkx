"""Parity for branching/arborescence weight type preservation.

Bead br-r37-c1-xy4xf. fnx.maximum_branching, fnx.minimum_branching,
fnx.maximum_spanning_arborescence, fnx.minimum_spanning_arborescence
on directed graphs returned edge dicts with weight values coerced to
``float``. nx preserves the original weight type (int weights stay
int). Drop-in code that asserts ``isinstance(d['weight'], int)``
broke.

The default weight (``1`` when no edge has the weight attr) was also
affected — fnx returned ``1.0``, nx returned ``1``. Root: Rust
binding coerces to f64.

Fix: after the Rust call, restore each retained edge's attr dict from
the source graph (respecting ``preserve_attrs``) so the original
weight type and other attributes match nx exactly.
"""

from __future__ import annotations

import pytest

import franken_networkx as fnx

try:
    import networkx as nx
    HAS_NX = True
except ImportError:
    HAS_NX = False

needs_nx = pytest.mark.skipif(not HAS_NX, reason="networkx not installed")


# ---------------------------------------------------------------------------
# Int weights stay int
# ---------------------------------------------------------------------------

@needs_nx
@pytest.mark.parametrize("name", [
    "minimum_branching", "maximum_branching",
    "minimum_spanning_arborescence", "maximum_spanning_arborescence",
])
def test_int_weights_preserved_as_int(name):
    DG = fnx.DiGraph([(0, 1, {"weight": 2}), (0, 2, {"weight": 1}), (1, 2, {"weight": 3})])
    DGX = nx.DiGraph([(0, 1, {"weight": 2}), (0, 2, {"weight": 1}), (1, 2, {"weight": 3})])

    f = sorted(getattr(fnx, name)(DG).edges(data=True))
    n = sorted(getattr(nx, name)(DGX).edges(data=True))
    assert f == n
    # Each weight value must be int, not float
    for u, v, d in f:
        if "weight" in d:
            assert isinstance(d["weight"], int), f"{name}: ({u}, {v}) weight is {type(d['weight'])}"


@needs_nx
def test_default_weight_when_attr_missing_is_int():
    """If the source has no weight attr, the default (int 1) propagates."""
    DG = fnx.DiGraph([(0, 1), (1, 2)])
    DGX = nx.DiGraph([(0, 1), (1, 2)])
    f = sorted(fnx.maximum_branching(DG).edges(data=True))
    n = sorted(nx.maximum_branching(DGX).edges(data=True))
    assert f == n
    for u, v, d in f:
        if "weight" in d:
            assert isinstance(d["weight"], int)


# ---------------------------------------------------------------------------
# Float weights stay float
# ---------------------------------------------------------------------------

@needs_nx
def test_float_weights_preserved_as_float():
    DG = fnx.DiGraph([(0, 1, {"weight": 2.5}), (0, 2, {"weight": 1.5})])
    DGX = nx.DiGraph([(0, 1, {"weight": 2.5}), (0, 2, {"weight": 1.5})])
    f = sorted(fnx.maximum_branching(DG).edges(data=True))
    n = sorted(nx.maximum_branching(DGX).edges(data=True))
    assert f == n
    for u, v, d in f:
        assert isinstance(d["weight"], float)


# ---------------------------------------------------------------------------
# preserve_attrs flag
# ---------------------------------------------------------------------------

@needs_nx
def test_preserve_attrs_true_keeps_all_edge_attrs():
    DG = fnx.DiGraph([(0, 1, {"weight": 2, "color": "red"}), (0, 2, {"weight": 1, "color": "blue"})])
    DGX = nx.DiGraph([(0, 1, {"weight": 2, "color": "red"}), (0, 2, {"weight": 1, "color": "blue"})])
    f = sorted(fnx.maximum_branching(DG, preserve_attrs=True).edges(data=True))
    n = sorted(nx.maximum_branching(DGX, preserve_attrs=True).edges(data=True))
    assert f == n


@needs_nx
def test_preserve_attrs_false_drops_non_weight_attrs():
    """preserve_attrs=False (default) keeps only the weight attr."""
    DG = fnx.DiGraph([(0, 1, {"weight": 2, "color": "red"}), (0, 2, {"weight": 1, "color": "blue"})])
    DGX = nx.DiGraph([(0, 1, {"weight": 2, "color": "red"}), (0, 2, {"weight": 1, "color": "blue"})])
    f = sorted(fnx.maximum_branching(DG, preserve_attrs=False).edges(data=True))
    n = sorted(nx.maximum_branching(DGX, preserve_attrs=False).edges(data=True))
    assert f == n
    for u, v, d in f:
        assert "color" not in d
        assert "weight" in d


# ---------------------------------------------------------------------------
# Custom attr name
# ---------------------------------------------------------------------------

@needs_nx
def test_custom_attr_name():
    DG = fnx.DiGraph([(0, 1, {"cost": 2}), (0, 2, {"cost": 1})])
    DGX = nx.DiGraph([(0, 1, {"cost": 2}), (0, 2, {"cost": 1})])
    f = sorted(fnx.maximum_branching(DG, attr="cost").edges(data=True))
    n = sorted(nx.maximum_branching(DGX, attr="cost").edges(data=True))
    assert f == n
    for u, v, d in f:
        assert isinstance(d["cost"], int)


# nro4w.7: networkx rewrites the INPUT's weights in place and back (minimal
# branching's C - (C - w), maximum_spanning_arborescence's shift, minimum
# branching's negation), so both the result's weights and the input's after
# the call carry that round trip (e.g. 0.1 -> 0.09999999999999964), and edges
# without the attribute gain it. The native kernels also chose a different
# arborescence or edge order in ~20% of random cases. fnx now runs networkx's
# wrappers over its maximum_branching, which already matched networkx exactly.
_ROUND_TRIP_FUNCTIONS = [
    "maximum_branching",
    "minimum_branching",
    "maximum_spanning_arborescence",
    "minimum_spanning_arborescence",
]


def _call(module, name, G):
    fn = getattr(module, name)
    try:
        H = fn(G)
    except Exception as exc:
        return type(exc).__name__, str(exc)
    return type(H).__name__, list(H.nodes), list(H.edges(data=True))


@pytest.mark.skipif(not HAS_NX, reason="networkx not installed")
@pytest.mark.parametrize("cls_name", ["DiGraph", "MultiDiGraph", "Graph"])
@pytest.mark.parametrize("name", _ROUND_TRIP_FUNCTIONS)
def test_result_and_input_after_the_call_match_networkx(name, cls_name):
    import random

    rng = random.Random(f"{name}-{cls_name}")
    for _ in range(80):
        n = rng.randint(1, 8)
        edges = [
            (rng.randrange(n), rng.randrange(n),
             {"weight": rng.choice([1, 2, 3, 0.5, 0.1, 7.3, -2])} if rng.random() < 0.85 else {})
            for _ in range(rng.randint(0, 20))
        ]
        edges = [e for e in edges if e[0] != e[1]]
        outcomes = []
        for module in (nx, fnx):
            G = getattr(module, cls_name)()
            G.add_nodes_from(range(n))
            G.add_edges_from(edges)
            outcomes.append((_call(module, name, G), list(G.edges(data=True))))
        assert outcomes[1] == outcomes[0], (edges,)


@pytest.mark.skipif(not HAS_NX, reason="networkx not installed")
def test_minimum_spanning_arborescence_weight_round_trip_example():
    # networkx's test_edge_augmentation::test_weight_key reached this through
    # minimum_spanning_arborescence; the drift is networkx's, reproduced.
    edges = [(0, 1, {"weight": 0.1}), (0, 2, {"weight": 0.7}), (1, 2, {"weight": 0.2})]
    G = fnx.DiGraph(edges)
    H = nx.DiGraph(edges)
    A = fnx.minimum_spanning_arborescence(G)
    B = nx.minimum_spanning_arborescence(H)
    assert list(A.edges(data=True)) == list(B.edges(data=True))
    assert list(G.edges(data=True)) == list(H.edges(data=True))
    assert list(G.edges(data=True)) != edges  # networkx's own drift, kept


@pytest.mark.skipif(not HAS_NX, reason="networkx not installed")
def test_sfq4w4_native_default_routes_e2e_jsonl():
    """br-r37-c1-rc0923-epic-perf-where-we-lose-sfq4w.4: verify 0 networkx
    frames and exact parity on maximum_branching, minimum_branching,
    maximum_spanning_arborescence, minimum_spanning_arborescence, and
    k_components (including non-closed-form Moody-White graphs), and emit
    artifacts/conformance/latest/always_networkx_native_routes_e2e.jsonl.
    """
    import hashlib
    import json
    import random
    import sys
    import time
    from pathlib import Path

    so_sha256 = hashlib.sha256(
        Path(fnx._fnx.__file__).read_bytes()
    ).hexdigest()
    records = []

    def run_with_frame_census(fn):
        nx_frames = []

        def prof(frame, event, _arg):
            if event == "call" and "/networkx/" in frame.f_code.co_filename:
                nx_frames.append(frame.f_code.co_name)

        t0 = time.perf_counter()
        sys.setprofile(prof)
        try:
            res = fn()
        finally:
            sys.setprofile(None)
        dt_ms = (time.perf_counter() - t0) * 1000.0
        return res, nx_frames, dt_ms

    for fn_name in (
        "maximum_branching",
        "minimum_branching",
        "maximum_spanning_arborescence",
        "minimum_spanning_arborescence",
    ):
        for cls_name in ("DiGraph", "MultiDiGraph"):
            rng = random.Random(42)
            n = 15
            edges = [(i, (i + 1) % n, {"weight": 1 + (i * 3) % 11}) for i in range(n)]
            for _ in range(30):
                u, v = rng.randrange(n), rng.randrange(n)
                if u != v:
                    edges.append((u, v, {"weight": rng.choice([1, 2, 5, 9, -1])}))
            fg = getattr(fnx, cls_name)()
            ng = getattr(nx, cls_name)()
            fg.add_nodes_from(range(n))
            ng.add_nodes_from(range(n))
            fg.add_edges_from(edges)
            ng.add_edges_from(edges)
            res_fnx, nx_frames, dt_ms = run_with_frame_census(
                lambda: getattr(fnx, fn_name)(fg)
            )
            res_nx = getattr(nx, fn_name)(ng)
            assert nx_frames == [], (fn_name, cls_name, nx_frames)
            assert list(res_fnx.edges(data=True)) == list(res_nx.edges(data=True))
            records.append(
                {
                    "ts": "2026-10-17T00:00:00Z",
                    "case_id": f"{fn_name}_{cls_name}",
                    "input_sha256": hashlib.sha256(repr(edges).encode()).hexdigest(),
                    "fnx_version": fnx.__version__,
                    "nx_version": nx.__version__,
                    "so_sha256": so_sha256,
                    "graph_class": cls_name,
                    "construction_path": "add_edges_from",
                    "expected": len(res_nx.edges()),
                    "actual": len(res_fnx.edges()),
                    "nx_frames": len(nx_frames),
                    "pass": True,
                    "duration_ms": round(dt_ms, 4),
                }
            )

    # Non-closed-form Moody-White graphs for k_components
    for seed in (3, 7, 12):
        rng = random.Random(seed)
        n = 11
        edges = [(u, v) for u in range(n) for v in range(u + 1, n) if rng.random() < 0.45]
        fg = fnx.Graph()
        ng = nx.Graph()
        fg.add_nodes_from(range(n))
        ng.add_nodes_from(range(n))
        fg.add_edges_from(edges)
        ng.add_edges_from(edges)
        res_fnx, nx_frames, dt_ms = run_with_frame_census(lambda: fnx.k_components(fg))
        res_nx = nx.k_components(ng)
        assert nx_frames == [], (seed, nx_frames)
        assert res_fnx == res_nx
        records.append(
            {
                "ts": "2026-10-17T00:00:00Z",
                "case_id": f"k_components_Graph_seed_{seed}",
                "input_sha256": hashlib.sha256(repr(edges).encode()).hexdigest(),
                "fnx_version": fnx.__version__,
                "nx_version": nx.__version__,
                "so_sha256": so_sha256,
                "graph_class": "Graph",
                "construction_path": "add_edges_from",
                "expected": sorted(res_nx.keys()),
                "actual": sorted(res_fnx.keys()),
                "nx_frames": len(nx_frames),
                "pass": True,
                "duration_ms": round(dt_ms, 4),
            }
        )

    out_path = (
        Path(__file__).resolve().parents[2]
        / "artifacts"
        / "conformance"
        / "latest"
        / "always_networkx_native_routes_e2e.jsonl"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        "\n".join(json.dumps(r, sort_keys=True) for r in records) + "\n",
        encoding="utf-8",
    )

