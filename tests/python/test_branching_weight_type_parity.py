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
