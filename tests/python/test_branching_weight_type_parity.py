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
