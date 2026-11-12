"""Lock for br-r37-c1-u3vvm — the DIRECTED native relabel kernel.

`_native_relabel_copy` existed on `PyGraph` only, and DiGraph was the worst row
in the family because of it: 0.7668x / 0.5521x / 0.4228x at 0 / 3 / 8 attributes
against Graph's 1.9852x / 0.9758x / 0.7436x with the kernel. The directed mirror
now exists, and everything below is what a kernel that bypasses the Python
rebuild has to keep true.

Two hazards are specific to the DIRECTED kernel and are the reason this file
exists rather than a parametrize added to the undirected one:

* edge mirrors are keyed by ORIENTED endpoints, so unlike the undirected kernel
  there is NO reverse-key fallback. A graph holding both ``(u, v)`` and
  ``(v, u)`` with different attributes would silently swap them if one crept in.
* successor and predecessor ORDER are separately observable, so a kernel that
  rebuilt the adjacency in the wrong order would pass an undirected test.

The rest pins the gates. Each one exists because the Python path implements
something this kernel does not, so a gate that stopped bailing would be a silent
behaviour change, not a speedup.
"""

from __future__ import annotations

import networkx as nx
import pytest

import franken_networkx as fnx


def _shape(graph):
    return (
        list(graph),
        [(u, v, dict(d)) for u, v, d in graph.edges(data=True)],
        {n: dict(d) for n, d in graph.nodes(data=True)},
        dict(graph.graph),
        graph.is_directed(),
        # Successor and predecessor order are separately observable on a
        # DiGraph, and a kernel that rebuilt adjacency in the wrong order would
        # pass an undirected check. Undirected graphs have no succ/pred.
        [(n, list(graph.succ[n]), list(graph.pred[n])) for n in graph]
        if graph.is_directed()
        else [(n, list(graph.adj[n])) for n in graph],
    )


def _both(setup, mapping, cls_name="DiGraph"):
    out = []
    for lib in (nx, fnx):
        graph = getattr(lib, cls_name)()
        setup(graph)
        graph.graph["gattr"] = 1
        try:
            out.append(("value", _shape(lib.relabel_nodes(graph, mapping, copy=True))))
        except Exception as exc:  # noqa: BLE001
            out.append(("raised", type(exc).__name__, str(exc)))
    return out


def test_plain_relabel_matches_networkx():
    def setup(g):
        g.add_edge("a", "b", w=1)
        g.add_edge("b", "c")
        g.add_node("z", k=2)

    nx_out, fnx_out = _both(setup, {"a": "A", "b": "B"})
    assert fnx_out == nx_out


def test_both_directions_keep_their_own_attributes():
    """The oriented-key hazard, stated as a test.

    A reverse-key fallback in the mirror lookup would attach (b, a)'s attrs to
    (a, b). Undirected graphs cannot express this case at all.
    """

    def setup(g):
        g.add_edge("a", "b", w="forward")
        g.add_edge("b", "a", w="backward")

    nx_out, fnx_out = _both(setup, {"a": "A", "b": "B"})
    assert fnx_out == nx_out
    edges = dict(((u, v), d["w"]) for u, v, d in fnx_out[1][1])
    assert edges[("A", "B")] == "forward"
    assert edges[("B", "A")] == "backward"


def test_successor_and_predecessor_order_survive():
    def setup(g):
        for target in ("b", "c", "d"):
            g.add_edge("hub", target)
        for source in ("x", "y"):
            g.add_edge(source, "hub")

    nx_out, fnx_out = _both(setup, {"hub": "HUB"})
    assert fnx_out == nx_out


def test_a_swap_mapping_is_not_a_merge():
    """`{'a': 'b', 'b': 'a'}` is a permutation: every target is distinct."""

    def setup(g):
        g.add_edge("a", "b", w=1)
        g.add_edge("b", "c", w=2)

    nx_out, fnx_out = _both(setup, {"a": "b", "b": "a"})
    assert fnx_out == nx_out


def test_self_loop_survives():
    nx_out, fnx_out = _both(lambda g: g.add_edge("a", "a", w=3), {"a": "A"})
    assert fnx_out == nx_out


@pytest.mark.parametrize(
    "mapping",
    [{}, {"a": "a"}, {"zz": "ZZ"}, {"a": 7}, {"a": (1, 2)}, {"a": 2.5}, {"a": True}],
    ids=["empty", "identity", "absent-key", "int", "tuple", "float", "bool"],
)
def test_exotic_and_no_op_mappings_match(mapping):
    def setup(g):
        g.add_edge("a", "b", w=1)
        g.add_node("c", k=2)

    nx_out, fnx_out = _both(setup, mapping)
    assert fnx_out == nx_out


def test_merging_mapping_still_matches_networkx():
    """Merging must BAIL to the Python path, which implements the semantics."""

    def setup(g):
        g.add_edge("a", "b", w=1)
        g.add_edge("c", "b", w=2)

    nx_out, fnx_out = _both(setup, {"a": "M", "c": "M"})
    assert fnx_out == nx_out


def test_none_target_raises_like_networkx():
    """The kernel bails so add_nodes_from keeps raising its own wording.

    ``read_gexf(relabel=True)`` depends on that ValueError when a node carries
    no label, so swallowing it here would be a real regression.
    """
    nx_out, fnx_out = _both(lambda g: g.add_edge("a", "b"), {"a": None})
    assert fnx_out == nx_out
    assert fnx_out[0] == "raised"


def test_node_attribute_written_through_the_mirror_is_carried():
    """Node-attr writes are not tracked by edges_dirty; the mirror is truth."""

    def setup(g):
        g.add_node("a", w=1)
        g.add_edge("a", "b")
        g.nodes["a"]["w"] = 99
        g.nodes["a"]["fresh"] = "yes"

    nx_out, fnx_out = _both(setup, {"a": "A"})
    assert fnx_out == nx_out
    assert fnx_out[1][2]["A"] == {"w": 99, "fresh": "yes"}


def test_edge_attribute_written_through_the_mirror_is_carried():
    def setup(g):
        g.add_edge("a", "b", w=1)
        g["a"]["b"]["w"] = 99
        g["a"]["b"]["fresh"] = "yes"

    nx_out, fnx_out = _both(setup, {"a": "A", "b": "B"})
    assert fnx_out == nx_out


def test_the_result_is_independent_of_the_source():
    """A kernel that shared attr dicts would alias the source."""
    gfx = fnx.DiGraph()
    gfx.add_edge("a", "b", w=1)
    gfx.add_node("a", k=1)
    out = fnx.relabel_nodes(gfx, {"a": "A", "b": "B"}, copy=True)
    out.nodes["A"]["k"] = 999
    out["A"]["B"]["w"] = 999
    out.graph["gattr"] = 999
    assert gfx.nodes["a"]["k"] == 1
    assert gfx["a"]["b"]["w"] == 1
    assert "gattr" not in gfx.graph


def test_graph_level_attributes_are_carried():
    gfx, gnx = fnx.DiGraph(), nx.DiGraph()
    for g in (gfx, gnx):
        g.add_edge("a", "b")
        g.graph["name"] = "n"
        g.graph["nested"] = {"k": 1}
    ofx = fnx.relabel_nodes(gfx, {"a": "A"}, copy=True)
    onx = nx.relabel_nodes(gnx, {"a": "A"}, copy=True)
    assert dict(ofx.graph) == dict(onx.graph)


@pytest.mark.parametrize(
    ("fnx_cls", "nx_cls"),
    [
        (fnx.Graph, nx.Graph),
        (fnx.DiGraph, nx.DiGraph),
        (fnx.MultiGraph, nx.MultiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_relabel_copy_preserves_real_graph_subclasses(fnx_cls, nx_cls):
    """NetworkX constructs a copy with ``G.__class__()``, not its base class."""

    class FnxSub(fnx_cls):
        def marker(self):
            return "preserved"

    class NxSub(nx_cls):
        pass

    actual = FnxSub()
    expected_input = NxSub()
    for graph in (actual, expected_input):
        graph.add_edge("a", "b", w=1)
        graph.add_node("c", k=2)
        graph.graph["kind"] = "subclass"

    out = fnx.relabel_nodes(actual, {"a": "A"}, copy=True)
    expected = nx.relabel_nodes(expected_input, {"a": "A"}, copy=True)

    assert type(out) is FnxSub
    assert type(expected) is NxSub
    assert out.marker() == "preserved"
    assert _shape(out) == _shape(expected)


@pytest.mark.parametrize(
    ("fnx_cls", "nx_cls"),
    [
        (fnx.Graph, nx.Graph),
        (fnx.DiGraph, nx.DiGraph),
        (fnx.MultiGraph, nx.MultiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_relabel_copy_still_materializes_filtered_views(fnx_cls, nx_cls):
    """The view's synthetic class needs a backing graph and cannot be called."""

    actual_parent = fnx_cls()
    expected_parent = nx_cls()
    for graph in (actual_parent, expected_parent):
        graph.add_edge("a", "b", w=1)
        graph.add_edge("b", "outside")

    actual_view = actual_parent.subgraph(["a", "b"])
    expected_view = expected_parent.subgraph(["a", "b"])
    assert type(actual_view) is not fnx_cls

    out = fnx.relabel_nodes(actual_view, {"a": "A"}, copy=True)
    expected = nx.relabel_nodes(expected_view, {"a": "A"}, copy=True)

    assert type(out) is fnx_cls
    assert type(expected) is nx_cls
    assert _shape(out) == _shape(expected)


def test_undirected_kernel_is_unaffected():
    """The undirected twin is the control for this change."""

    def setup(g):
        g.add_edge("a", "b", w=1)
        g.add_edge("b", "c")

    nx_out, fnx_out = _both(setup, {"a": "A"}, cls_name="Graph")
    assert fnx_out == nx_out
