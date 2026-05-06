"""Pickle / deepcopy parity locks for the public view classes.

br-r37-c1-viewpkl: ``AtlasView`` / ``AdjacencyView`` /
``MultiAdjacencyView`` stored a ``_atlas_getter`` lambda closure that
captured a graph descriptor reference. Pickle cannot serialize lambdas
or local functions, so ``pickle.dumps(M.adj[0])`` and
``pickle.dumps(M.adj)`` raised ``AttributeError: Can't get local
object 'MultiAdjacencyView.__getitem__.<locals>.<lambda>'``.

nx's matching views snapshot to a plain dict (live-tracking is lost,
since the graph descriptor can't survive pickling anyway) but
preserve the wrapping view TYPE on the restored side. Match that
contract exactly so users serializing graphs through caching layers
(joblib, dask, multiprocessing) don't crash on adjacency-view access.

Companion to br-r37-c1-cip5m which fixed the same defect class on
``_LiveMultiEdgeDataView``.
"""

from __future__ import annotations

import copy
import pickle

import franken_networkx as fnx
import networkx as nx
import pytest


GRAPH_BUILDERS = [
    ("Graph", lambda m: m.Graph([(0, 1, {"w": 1}), (1, 2, {"w": 2})])),
    ("DiGraph", lambda m: m.DiGraph([(0, 1, {"w": 1}), (1, 2, {"w": 2})])),
    ("MultiGraph", lambda m: m.MultiGraph(
        [(0, 1, {"w": 1}), (0, 1, {"w": 2}), (1, 2, {"w": 3})])),
    ("MultiDiGraph", lambda m: m.MultiDiGraph(
        [(0, 1, {"w": 1}), (0, 1, {"w": 2}), (1, 2, {"w": 3})])),
]


@pytest.mark.parametrize("name,builder", GRAPH_BUILDERS, ids=[b[0] for b in GRAPH_BUILDERS])
def test_adj_view_pickle_roundtrips(name, builder):
    """``G.adj`` (AdjacencyView or MultiAdjacencyView) must round-trip
    pickle. Snapshot semantics (no live-tracking after restore) match
    nx; the view type is preserved across the roundtrip."""
    G = builder(fnx)
    G_n = builder(nx)
    restored = pickle.loads(pickle.dumps(G.adj))
    restored_n = pickle.loads(pickle.dumps(G_n.adj))
    assert type(restored).__name__ == type(restored_n).__name__
    # Compare via nested dict equality.
    def _flat(view):
        return {u: dict(view[u]) for u in view}
    assert _flat(restored) == _flat(restored_n)


@pytest.mark.parametrize("name,builder", GRAPH_BUILDERS, ids=[b[0] for b in GRAPH_BUILDERS])
def test_adj_node_view_pickle_roundtrips(name, builder):
    """``G.adj[node]`` (AtlasView for simple graphs, AdjacencyView for
    multigraphs) must round-trip pickle."""
    G = builder(fnx)
    G_n = builder(nx)
    av_f = G.adj[0]
    av_n = G_n.adj[0]
    restored = pickle.loads(pickle.dumps(av_f))
    restored_n = pickle.loads(pickle.dumps(av_n))
    assert type(restored).__name__ == type(restored_n).__name__
    assert dict(restored) == dict(restored_n) or {
        k: dict(v) for k, v in dict(restored).items()
    } == {k: dict(v) for k, v in dict(restored_n).items()}


@pytest.mark.parametrize("name,builder", GRAPH_BUILDERS, ids=[b[0] for b in GRAPH_BUILDERS])
def test_adj_view_deepcopy_roundtrips(name, builder):
    """``copy.deepcopy`` uses the same protocol surface as pickle; lock
    parity here so a future change to ``__reduce__`` doesn't break
    deepcopy on adjacency views."""
    G = builder(fnx)
    av = G.adj[0]
    deepc = copy.deepcopy(av)
    assert type(deepc).__name__ == type(av).__name__
    assert dict(deepc) == dict(av) or {
        k: dict(v) for k, v in dict(deepc).items()
    } == {k: dict(v) for k, v in dict(av).items()}


@pytest.mark.parametrize("name,builder", GRAPH_BUILDERS, ids=[b[0] for b in GRAPH_BUILDERS])
def test_adj_view_pickle_loses_live_tracking_like_nx(name, builder):
    """Restored views are snapshots — mutating the original graph after
    pickle does NOT propagate to the restored view. nx behaves the same
    way; the live graph descriptor reference can't survive pickling."""
    G = builder(fnx)
    av = G.adj[0]
    restored = pickle.loads(pickle.dumps(av))
    initial_keys = set(restored)
    if G.is_multigraph():
        G.add_edge(0, 1, key="newkey", w=99)
    else:
        G.add_edge(0, 99, w=99)
    # Restored view's keys should NOT include the new edge target.
    assert set(restored) == initial_keys


def test_adj_view_repickle_roundtrips():
    """A restored view must itself be re-picklable. Originally the
    fix could regress here if the reconstructor produced a view that
    again held an unpicklable closure."""
    M = fnx.MultiGraph([(0, 1, {"w": 1}), (0, 1, {"w": 2})])
    av = M.adj[0]
    once = pickle.loads(pickle.dumps(av))
    twice = pickle.loads(pickle.dumps(once))
    assert dict(twice) == dict(once)


# ---------------------------------------------------------------------------
# Subgraph view pickle parity (br-r37-c1-fgv-pkl)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name,builder", GRAPH_BUILDERS, ids=[b[0] for b in GRAPH_BUILDERS])
def test_subgraph_view_isinstance_matches_graph_class(name, builder):
    """Filtered subgraph views must remain public graph-class instances."""
    G = builder(fnx)
    sg = G.subgraph([0, 1, 2])
    assert isinstance(sg, getattr(fnx, name))


@pytest.mark.parametrize("name,builder", GRAPH_BUILDERS, ids=[b[0] for b in GRAPH_BUILDERS])
def test_subgraph_view_pickle_roundtrips(name, builder):
    """``G.subgraph(nbunch)`` returns a `_FilteredGraphView` whose
    `__class__` is a synthetic subclass of `_FilteredGraphView` named
    'Graph'/'DiGraph'/etc. — same `__qualname__` as the public class
    but a DIFFERENT class object, so pickle's qualname-lookup found
    the canonical class and crashed with `PicklingError("not the same
    object as franken_networkx.Graph")`. The fix snapshots the view
    as a real (non-view) graph copy at pickle time."""
    G = builder(fnx)
    sg = G.subgraph([0, 1, 2])
    restored = pickle.loads(pickle.dumps(sg))
    # After pickle, the restored object is the canonical class.
    canonical = getattr(fnx, name)
    assert isinstance(restored, canonical)
    assert type(restored) is canonical
    # Node / edge content matches.
    assert sorted(restored.nodes()) == sorted(sg.nodes())
    if G.is_multigraph():
        assert sorted(restored.edges(keys=True)) == sorted(sg.edges(keys=True))
    else:
        assert sorted(restored.edges()) == sorted(sg.edges())


@pytest.mark.parametrize("name,builder", GRAPH_BUILDERS, ids=[b[0] for b in GRAPH_BUILDERS])
def test_subgraph_view_deepcopy_roundtrips(name, builder):
    """copy.deepcopy uses the same protocol surface as pickle."""
    G = builder(fnx)
    sg = G.subgraph([0, 1, 2])
    deepc = copy.deepcopy(sg)
    canonical = getattr(fnx, name)
    assert isinstance(deepc, canonical)
    assert sorted(deepc.nodes()) == sorted(sg.nodes())


def test_subgraph_view_repickle_roundtrips():
    """A restored subgraph copy must re-pickle (it's a canonical
    Graph/DiGraph at that point, so this is a smoke test that the
    reconstructor doesn't accidentally produce something
    pickle-incompatible)."""
    G = fnx.path_graph(5)
    sg = G.subgraph([0, 1, 2])
    once = pickle.loads(pickle.dumps(sg))
    twice = pickle.loads(pickle.dumps(once))
    assert sorted(twice.nodes()) == [0, 1, 2]
    assert isinstance(twice, fnx.Graph)


_FILTERED_VIEW_MUTATORS_FOR_TEST = [
    ("add_node", lambda sg: sg.add_node(99)),
    ("add_nodes_from", lambda sg: sg.add_nodes_from([99, 100])),
    ("remove_node", lambda sg: sg.remove_node(0)),
    ("remove_nodes_from", lambda sg: sg.remove_nodes_from([0])),
    ("add_edge", lambda sg: sg.add_edge(99, 100)),
    ("add_edges_from", lambda sg: sg.add_edges_from([(99, 100)])),
    ("add_weighted_edges_from",
     lambda sg: sg.add_weighted_edges_from([(99, 100, 5)])),
    ("remove_edge", lambda sg: sg.remove_edge(0, 1)),
    ("remove_edges_from", lambda sg: sg.remove_edges_from([(0, 1)])),
    ("clear", lambda sg: sg.clear()),
    ("clear_edges", lambda sg: sg.clear_edges()),
    ("update", lambda sg: sg.update(edges=[(99, 100)])),
]


@pytest.mark.parametrize("name,builder", GRAPH_BUILDERS, ids=[b[0] for b in GRAPH_BUILDERS])
@pytest.mark.parametrize(
    "op_name,op",
    _FILTERED_VIEW_MUTATORS_FOR_TEST,
    ids=[op[0] for op in _FILTERED_VIEW_MUTATORS_FOR_TEST],
)
def test_subgraph_view_is_frozen(name, builder, op_name, op):
    """br-r37-c1-fgvfrz: peer commit 9b9f47f2 (br-r37-c1-rcd0e) added
    Graph/DiGraph/MultiGraph/MultiDiGraph as a SECOND base class for
    the synthetic _FILTERED_GRAPH_VIEW_TYPES so isinstance passes —
    but moved the canonical class's mutation methods into the
    synthetic MRO BEFORE _FilteredGraphView's __getattr__ ever gets
    consulted. Mutation became a silent no-op (Graph.add_node hits
    unset Rust state on the synthetic instance), violating nx's
    documented frozen-graph contract.

    Lock that all 12 nx-defined mutators raise NetworkXError("Frozen
    graph can't be modified") on subgraph views across all 4 graph
    classes."""
    G = builder(fnx)
    sg = G.subgraph([0, 1, 2])
    with pytest.raises(nx.NetworkXError, match="Frozen graph"):
        op(sg)


# ---------------------------------------------------------------------------
# Reverse view frozen-mutator parity (br-r37-c1-rvfrz)
# ---------------------------------------------------------------------------


_REVERSE_VIEW_BUILDERS = [
    ("DiGraph",
     lambda: fnx.DiGraph([(0, 1), (1, 2), (2, 0)]).reverse(copy=False)),
    ("MultiDiGraph",
     lambda: fnx.MultiDiGraph(
         [(0, 1), (0, 1), (1, 2)]).reverse(copy=False)),
]


@pytest.mark.parametrize("name,view_builder", _REVERSE_VIEW_BUILDERS,
                         ids=[b[0] for b in _REVERSE_VIEW_BUILDERS])
@pytest.mark.parametrize(
    "op_name,op",
    _FILTERED_VIEW_MUTATORS_FOR_TEST,
    ids=[op[0] for op in _FILTERED_VIEW_MUTATORS_FOR_TEST],
)
def test_reverse_view_is_frozen(name, view_builder, op_name, op):
    """br-r37-c1-rvfrz: same MRO mutability hole as br-r37-c1-fgvfrz,
    on a different view class. `_ReverseDirectedView` and
    `_ReverseMultiDirectedView` inherit from
    (`_ReverseDirectedViewBase`, DiGraph) / (..., MultiDiGraph) —
    canonical class mutators reachable in MRO before
    `_ReverseDirectedViewBase.__getattr__` ever fires. Mutating a
    reversed view became a silent no-op instead of raising
    NetworkXError("Frozen graph can't be modified").

    Lock all 12 nx-defined mutators on both reverse view classes."""
    rv = view_builder()
    with pytest.raises(nx.NetworkXError, match="Frozen graph"):
        op(rv)


# ---------------------------------------------------------------------------
# Conversion view pickle parity (br-r37-c1-cgv-pkl)
# ---------------------------------------------------------------------------


_CONVERSION_VIEW_BUILDERS = [
    ("Graph_to_directed", lambda: fnx.path_graph(5).to_directed(as_view=True),
     "DiGraph"),
    ("DiGraph_to_undirected",
     lambda: fnx.DiGraph([(0, 1), (1, 2)]).to_undirected(as_view=True),
     "Graph"),
    ("MultiGraph_to_directed",
     lambda: fnx.MultiGraph(
         [(0, 1), (0, 1), (1, 2)]).to_directed(as_view=True),
     "MultiDiGraph"),
    ("MultiDiGraph_to_undirected",
     lambda: fnx.MultiDiGraph(
         [(0, 1), (0, 1), (1, 2)]).to_undirected(as_view=True),
     "MultiGraph"),
]


@pytest.mark.parametrize(
    "name,view_builder,canonical_name", _CONVERSION_VIEW_BUILDERS,
    ids=[b[0] for b in _CONVERSION_VIEW_BUILDERS],
)
def test_conversion_view_pickle_roundtrips(name, view_builder, canonical_name):
    """br-r37-c1-cgv-pkl: same defect class as br-r37-c1-{neb6c, fgv-pkl}.
    `_DIRECTED_CONVERSION_VIEW_TYPES` and
    `_UNDIRECTED_CONVERSION_VIEW_TYPES` create synthetic classes
    named "DiGraph"/"MultiDiGraph"/"Graph"/"MultiGraph" that share
    `__qualname__` and `__module__` with the canonical classes but
    are distinct class objects. Pickle's qualname-based class lookup
    finds the canonical class, sees `lookup is not type(self)`, and
    crashes with PicklingError.

    Snapshot the conversion view as a real (canonical-class) graph
    copy at pickle time."""
    view = view_builder()
    restored = pickle.loads(pickle.dumps(view))
    canonical = getattr(fnx, canonical_name)
    assert isinstance(restored, canonical)
    assert type(restored) is canonical
    # Edges and nodes preserved.
    assert sorted(restored.nodes()) == sorted(view.nodes())
    if view.is_multigraph():
        assert sorted(restored.edges(keys=True)) == sorted(view.edges(keys=True))
    else:
        assert sorted(restored.edges()) == sorted(view.edges())


@pytest.mark.parametrize(
    "name,view_builder,canonical_name", _CONVERSION_VIEW_BUILDERS,
    ids=[b[0] for b in _CONVERSION_VIEW_BUILDERS],
)
def test_conversion_view_deepcopy_roundtrips(name, view_builder, canonical_name):
    """copy.deepcopy uses the same protocol surface as pickle."""
    view = view_builder()
    deepc = copy.deepcopy(view)
    canonical = getattr(fnx, canonical_name)
    assert isinstance(deepc, canonical)
    assert sorted(deepc.nodes()) == sorted(view.nodes())


def test_conversion_view_pickle_matches_nx():
    """Edge-content parity check on the simple-graph conversion case
    where nx's pickle also succeeds."""
    G = fnx.path_graph(5)
    G_n = nx.path_graph(5)
    f_restored = pickle.loads(pickle.dumps(G.to_directed(as_view=True)))
    n_restored = pickle.loads(pickle.dumps(G_n.to_directed(as_view=True)))
    assert sorted(f_restored.nodes()) == sorted(n_restored.nodes())
    assert sorted(f_restored.edges()) == sorted(n_restored.edges())


def test_subgraph_view_loses_live_filtering_after_pickle():
    """The live subgraph view tracks filter changes against its parent
    graph. After pickle, the restored object is independent (matches
    nx) — mutations to the parent are NOT reflected."""
    G = fnx.path_graph(5)
    sg = G.subgraph([0, 1, 2])
    restored = pickle.loads(pickle.dumps(sg))
    G.add_edge(0, 99)  # parent mutated; sg sees the new node still filtered out
    assert sorted(restored.nodes()) == [0, 1, 2]
    assert 99 not in restored.nodes()


def test_subgraph_view_pickle_matches_nx_undirected():
    """The fnx-vs-nx parity check on undirected graphs (where nx's
    subgraph_view DOES pickle successfully). nx's directed
    `subgraph_view` pickle is broken upstream by a closure-over-lambda
    in `reverse_edge`; we don't lock parity for the directed case
    because nx's behavior there is itself a known limitation."""
    G = fnx.path_graph(5)
    G_n = nx.path_graph(5)
    f_restored = pickle.loads(pickle.dumps(G.subgraph([0, 1, 2])))
    n_restored = pickle.loads(pickle.dumps(G_n.subgraph([0, 1, 2])))
    assert sorted(f_restored.nodes()) == sorted(n_restored.nodes())
    assert sorted(f_restored.edges()) == sorted(n_restored.edges())
