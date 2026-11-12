"""Parity for unhashable-node rejection in add_node / add_edge / add_*_from.

Bead br-r37-c1-m0io3. fnx silently accepted unhashable types
(list, set, dict) as graph nodes, while nx raises ``TypeError:
unhashable type: '<type>'``.

Repro:
    >>> fnx.Graph().add_node([1, 2])    # silently succeeded
    >>> nx.Graph().add_node([1, 2])
    TypeError: unhashable type: 'list'

Drop-in code that catches TypeError when constructing a graph from
external/serialized data wouldn't trigger on fnx; the bad input got
silently absorbed and broke downstream operations later.

The fix calls ``hash(node)`` in the Python add_node / add_edge /
add_edges_from wrappers (raising the nx-shaped TypeError) before
delegating to the Rust binding.
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


UNHASHABLE = [
    pytest.param([1, 2], id="list"),
    pytest.param({1, 2}, id="set"),
    pytest.param({"a": 1}, id="dict"),
]


# ---------------------------------------------------------------------------
# add_node
# ---------------------------------------------------------------------------

@needs_nx
@pytest.mark.parametrize("val", UNHASHABLE)
def test_add_node_unhashable_raises_typeerror(val):
    G = fnx.Graph()
    GX = nx.Graph()
    with pytest.raises(TypeError, match=r"unhashable type"):
        G.add_node(val)
    with pytest.raises(TypeError, match=r"unhashable type"):
        GX.add_node(val)


@needs_nx
@pytest.mark.parametrize("cls_name", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
def test_add_node_unhashable_message_matches_nx(cls_name):
    """Message wording check — must say ``unhashable type: 'list'``."""
    G = getattr(fnx, cls_name)()
    GX = getattr(nx, cls_name)()
    try:
        G.add_node([1, 2])
    except TypeError as e:
        f_msg = str(e)
    try:
        GX.add_node([1, 2])
    except TypeError as e:
        n_msg = str(e)
    assert f_msg == n_msg


# ---------------------------------------------------------------------------
# add_edge
# ---------------------------------------------------------------------------

@needs_nx
@pytest.mark.parametrize("val", UNHASHABLE)
@pytest.mark.parametrize("cls_name", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
def test_add_edge_unhashable_endpoint_raises(val, cls_name):
    G = getattr(fnx, cls_name)()
    GX = getattr(nx, cls_name)()
    with pytest.raises(TypeError, match=r"unhashable type"):
        G.add_edge(val, 99)
    with pytest.raises(TypeError, match=r"unhashable type"):
        GX.add_edge(val, 99)


@needs_nx
@pytest.mark.parametrize("val", UNHASHABLE)
def test_add_edge_unhashable_both_endpoints_raises(val):
    G = fnx.Graph()
    GX = nx.Graph()
    with pytest.raises(TypeError, match=r"unhashable type"):
        G.add_edge(val, val)
    with pytest.raises(TypeError, match=r"unhashable type"):
        GX.add_edge(val, val)


# ---------------------------------------------------------------------------
# add_edges_from
# ---------------------------------------------------------------------------

@needs_nx
@pytest.mark.parametrize("val", UNHASHABLE)
def test_add_edges_from_unhashable_endpoint_raises(val):
    G = fnx.Graph()
    GX = nx.Graph()
    with pytest.raises(TypeError, match=r"unhashable type"):
        G.add_edges_from([(val, 3)])
    with pytest.raises(TypeError, match=r"unhashable type"):
        GX.add_edges_from([(val, 3)])


# ---------------------------------------------------------------------------
# Hashable types still work (regression)
# ---------------------------------------------------------------------------

@needs_nx
@pytest.mark.parametrize(
    "val",
    [1, "x", (1, 2), frozenset([1, 2]), 1.5, None_alt := (None,)[0:0]],
)
def test_hashable_types_still_work(val):
    """Hashable node values must continue to work — covers int, str,
    tuple, frozenset, float, and the empty-tuple corner case."""
    if val == ():
        pytest.skip("empty tuple corner — not a meaningful node")
    G = fnx.Graph()
    GX = nx.Graph()
    G.add_node(val)
    GX.add_node(val)
    assert val in G
    assert val in GX


@needs_nx
def test_add_edge_with_hashable_endpoints_unchanged():
    G = fnx.Graph()
    GX = nx.Graph()
    G.add_edge((1, 2), (3, 4))     # tuples are hashable
    GX.add_edge((1, 2), (3, 4))
    assert sorted(G.edges()) == sorted(GX.edges())


@needs_nx
def test_add_edges_from_with_hashable_endpoints_unchanged():
    edges = [(1, 2), ((3, 4), (5, 6)), ("a", "b")]
    G = fnx.Graph()
    GX = nx.Graph()
    G.add_edges_from(edges)
    GX.add_edges_from(edges)
    assert sorted(G.nodes(), key=str) == sorted(GX.nodes(), key=str)


# ---------------------------------------------------------------------------
# None still raises ValueError (pre-existing br-nonenode parity)
# ---------------------------------------------------------------------------

@needs_nx
def test_none_node_still_raises_value_error():
    """The None guard (br-nonenode) is unchanged: ValueError, not
    TypeError."""
    G = fnx.Graph()
    GX = nx.Graph()
    with pytest.raises(ValueError, match=r"None cannot be a node"):
        G.add_node(None)
    with pytest.raises(ValueError, match=r"None cannot be a node"):
        GX.add_node(None)
