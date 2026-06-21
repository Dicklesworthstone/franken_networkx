"""br-r37-c1-0epvo: regression — ``fnx.algorithms.tree.X`` for the
four arborescence/branching functions that nx 3.3+ flags as
mutation-preserving must not raise ``NotImplementedError`` from the nx
dispatcher.

Background: nx 3.3 introduced strict dispatch for any function that
mutates its input — if the input has ``__networkx_backend__`` set, nx
will *only* call that backend's implementation; it refuses to
auto-convert to a different backend (because the conversion would lose
the mutation context the caller expects to observe). Without the
``__networkx_backend__ = "franken_networkx"`` class attribute on
fnx.Graph/DiGraph/MultiGraph/MultiDiGraph, the dispatcher returned an
empty ``set()`` for ``graph_backend_names`` and raised::

    RuntimeError: ``X`` was called with inputs from multiple
    backends: set().

Once the class attribute is in place, the dispatcher routes the
function through ``franken_networkx.backend.BackendInterface``, which
must register every such function (otherwise the dispatcher raises
``NotImplementedError`` instead).
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


def _weighted_digraph(cls):
    g = cls()
    g.add_edge(0, 1, weight=5)
    g.add_edge(1, 2, weight=3)
    g.add_edge(2, 0, weight=2)
    g.add_edge(0, 2, weight=4)
    return g


@pytest.mark.parametrize(
    "fname",
    [
        "minimum_branching",
        "maximum_spanning_arborescence",
        "minimum_spanning_arborescence",
        "minimal_branching",
    ],
)
def test_tree_submodule_via_fnx_namespace(fname):
    """``fnx.algorithms.tree.X(fnx_graph)`` returns a graph (no
    dispatcher error). Locks in the backend-attribute fix plus the
    ``minimal_branching`` registration."""
    fg = _weighted_digraph(fnx.DiGraph)
    result = getattr(fnx.algorithms.tree, fname)(fg)
    # Should be a graph-like result with edges + nodes attrs.
    assert hasattr(result, "edges")
    assert hasattr(result, "nodes")


@needs_nx
@pytest.mark.parametrize(
    "fname",
    [
        "minimum_branching",
        "maximum_spanning_arborescence",
        "minimum_spanning_arborescence",
        "minimal_branching",
    ],
)
def test_tree_submodule_via_nx_namespace_with_fnx_graph(fname):
    """``nx.algorithms.tree.X(fnx_graph)`` does not raise. Verifies the
    nx dispatcher recognises the fnx graph as belonging to the
    ``franken_networkx`` backend."""
    fg = _weighted_digraph(fnx.DiGraph)
    result = getattr(nx.algorithms.tree, fname)(fg)
    assert hasattr(result, "edges")


@needs_nx
def test_graph_classes_have_networkx_backend_attr():
    """All four fnx graph classes must declare themselves as belonging
    to the ``franken_networkx`` backend for nx 3.3+ dispatch."""
    for cls in (fnx.Graph, fnx.DiGraph, fnx.MultiGraph, fnx.MultiDiGraph):
        assert getattr(cls, "__networkx_backend__", None) == "franken_networkx", (
            f"{cls.__name__} missing __networkx_backend__ class attribute"
        )


@needs_nx
def test_backend_registers_all_four_tree_functions():
    """The backend registry must include every function name the
    dispatcher will route from ``nx.algorithms.tree``; otherwise
    NetworkXNotImplemented is raised for fnx graphs."""
    from franken_networkx.backend import _SUPPORTED_ALGORITHMS

    for fname in (
        "minimum_branching",
        "maximum_spanning_arborescence",
        "minimum_spanning_arborescence",
        "minimal_branching",
    ):
        assert fname in _SUPPORTED_ALGORITHMS, (
            f"{fname} not registered in backend._SUPPORTED_ALGORITHMS"
        )


@needs_nx
@pytest.mark.parametrize(
    "sequence",
    [
        (),
        ((),),
        (((),), ()),
        (((), ()), ((), ())),
        ((((),), ()),),
    ],
)
@pytest.mark.parametrize("sensible_relabeling", [False, True])
def test_tree_submodule_from_nested_tuple_native_order_parity(
    monkeypatch, sequence, sensible_relabeling
):
    """Submodule override should match nx order without fnx<-nx conversion."""
    import franken_networkx.tree as tree_mod

    def _conversion_forbidden(*args, **kwargs):
        raise AssertionError("from_nested_tuple should build fnx.Graph directly")

    monkeypatch.setattr(tree_mod, "_from_nx_graph", _conversion_forbidden)

    result = tree_mod.from_nested_tuple(
        sequence, sensible_relabeling=sensible_relabeling
    )
    expected = nx.from_nested_tuple(
        sequence, sensible_relabeling=sensible_relabeling
    )

    assert isinstance(result, fnx.Graph)
    assert list(result.nodes()) == list(expected.nodes())
    assert list(result.edges()) == list(expected.edges())


@needs_nx
def test_minimum_branching_parity_with_nx():
    """Beyond the dispatcher contract, the result for a simple
    weighted DiGraph should match nx's own value-wise output."""
    ng = _weighted_digraph(nx.DiGraph)
    fg = _weighted_digraph(fnx.DiGraph)
    rn = nx.algorithms.tree.minimum_branching(ng)
    rf = fnx.algorithms.tree.minimum_branching(fg)
    # Sum of weights should match.
    sum_n = sum(d.get("weight", 0) for _, _, d in rn.edges(data=True))
    sum_f = sum(d.get("weight", 0) for _, _, d in rf.edges(data=True))
    assert sum_n == sum_f
