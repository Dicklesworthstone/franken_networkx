"""to_directed / to_undirected conversion views no longer copy the parent.

Bead br-r37-c1-y2b8t.

`nx.to_directed(graph)` / `nx.to_undirected(graph)` (the module functions)
return a live view (``graph.to_directed(as_view=True)``). fnx returns a view
too, but its conversion-view classes mix in the canonical PyO3 Graph/DiGraph
base, whose ``__new__`` eagerly copied the entire parent graph into the view's
Rust storage on every construction (O(|V|+|E|)). That storage is dead weight —
``_ConversionGraphViewBase`` overrides every query method to answer through
``self._graph``. ``__new__`` now builds an empty base, so construction is O(1).
These tests pin structural parity with nx, the view-tracks-parent-mutations
contract, and that construction does not scale with parent size.
"""

from __future__ import annotations

import copy
import gc
import json
import pickle
import random
import sys
import time
import weakref

import franken_networkx as fnx
import pytest

try:
    import networkx as nx
    HAS_NX = True
except ImportError:
    HAS_NX = False

needs_nx = pytest.mark.skipif(not HAS_NX, reason="networkx not installed")


def _edge_key(g, u, v):
    return (u, v) if g.is_directed() else frozenset((u, v))


@needs_nx
@pytest.mark.parametrize("conv", ["to_directed", "to_undirected"])
@pytest.mark.parametrize("directed", [False, True])
@pytest.mark.parametrize("seed", list(range(30)))
def test_structural_parity_with_nx(conv, directed, seed):
    rng = random.Random(seed * 41 + (3 if directed else 1))
    n = rng.randint(0, 30)
    ng = nx.DiGraph() if directed else nx.Graph()
    fg = fnx.DiGraph() if directed else fnx.Graph()
    nodes = list(range(n))
    rng.shuffle(nodes)
    for u in nodes:
        ng.add_node(u)
        fg.add_node(u)
    seen = set()
    for _ in range(rng.randint(0, n * 2)):
        if not nodes:
            break
        a, b = rng.choice(nodes), rng.choice(nodes)
        if a == b:
            continue
        k = (a, b) if directed else tuple(sorted((a, b)))
        if k in seen:
            continue
        seen.add(k)
        ng.add_edge(a, b)
        fg.add_edge(a, b)
    sv = getattr(nx, conv)(ng)
    fv = getattr(fnx, conv)(fg)
    assert fv.is_directed() == sv.is_directed()
    assert fv.is_multigraph() == sv.is_multigraph()
    assert set(fv) == set(sv)
    assert fv.number_of_nodes() == sv.number_of_nodes()
    assert fv.number_of_edges() == sv.number_of_edges()
    assert {_edge_key(sv, u, v) for u, v in fv.edges()} == {
        _edge_key(sv, u, v) for u, v in sv.edges()
    }
    for u in sv:
        assert set(fv.adj[u]) == set(sv.adj[u])


@needs_nx
def test_to_directed_tracks_parent_mutations():
    f = fnx.Graph()
    f.add_edges_from([(0, 1), (1, 2), (2, 3)])
    v = fnx.to_directed(f)
    assert v.is_directed()
    assert v.number_of_edges() == 6
    f.add_edge(3, 0)
    assert v.number_of_edges() == 8
    f.remove_node(2)
    assert set(v) == {0, 1, 3}
    assert v.has_edge(3, 0) and v.has_edge(0, 3)


@needs_nx
def test_to_undirected_of_digraph():
    fd = fnx.DiGraph()
    fd.add_edges_from([(0, 1), (1, 0), (1, 2), (3, 2)])
    nd = nx.DiGraph()
    nd.add_edges_from([(0, 1), (1, 0), (1, 2), (3, 2)])
    fv = fnx.to_undirected(fd)
    sv = nx.to_undirected(nd)
    assert not fv.is_directed()
    assert {frozenset(e) for e in fv.edges()} == {frozenset(e) for e in sv.edges()}
    assert fv.number_of_edges() == sv.number_of_edges()


@needs_nx
@pytest.mark.parametrize("seed", list(range(25)))
def test_reverse_view_structural_parity(seed):
    # br-r37-c1-q131o: reverse_view had the same parent-copy bug.
    rng = random.Random(seed * 29 + 2)
    n = rng.randint(0, 30)
    ng, fg = nx.DiGraph(), fnx.DiGraph()
    nodes = list(range(n))
    rng.shuffle(nodes)
    for u in nodes:
        ng.add_node(u)
        fg.add_node(u)
    seen = set()
    for _ in range(rng.randint(0, n * 2)):
        if not nodes:
            break
        a, b = rng.choice(nodes), rng.choice(nodes)
        if a == b or (a, b) in seen:
            continue
        seen.add((a, b))
        ng.add_edge(a, b)
        fg.add_edge(a, b)
    sv = nx.reverse_view(ng)
    fv = fnx.reverse_view(fg)
    assert fv.is_directed()
    assert set(fv) == set(sv)
    assert fv.number_of_edges() == sv.number_of_edges()
    assert {(u, v) for u, v in fv.edges()} == {(u, v) for u, v in sv.edges()}
    for u in sv:
        assert set(fv.succ[u]) == set(sv.succ[u])
        assert set(fv.pred[u]) == set(sv.pred[u])


@needs_nx
def test_reverse_view_tracks_parent_and_is_fast():
    f = fnx.DiGraph()
    f.add_edges_from([(0, 1), (1, 2)])
    v = fnx.reverse_view(f)
    assert sorted(v.edges()) == [(1, 0), (2, 1)]
    f.add_edge(2, 0)
    assert sorted(v.edges()) == [(0, 2), (1, 0), (2, 1)]

    big = fnx.DiGraph()
    g = nx.gnm_random_graph(8000, 32000, seed=1, directed=True)
    for u in g.nodes():
        big.add_node(u)
    for u, vv in g.edges():
        big.add_edge(u, vv)
    best = 1e9
    for _ in range(5):
        s = time.perf_counter()
        fnx.reverse_view(big)
        best = min(best, time.perf_counter() - s)
    assert best * 1000 < 5.0, f"reverse_view ctor too slow: {best * 1000:.2f}ms"


@needs_nx
def test_construction_does_not_scale_with_parent_size():
    def make(n):
        g = nx.gnm_random_graph(n, n * 4, seed=1)
        f = fnx.Graph()
        for u in g.nodes():
            f.add_node(u)
        for u, v in g.edges():
            f.add_edge(u, v)
        return f

    def ctor_ms(f):
        best = 1e9
        for _ in range(5):
            s = time.perf_counter()
            fnx.to_directed(f)
            best = min(best, time.perf_counter() - s)
        return best * 1000

    big = ctor_ms(make(8000))
    # The old O(N+E) copy was ~186ms on an 8000-node parent. An empty base
    # makes this ~microseconds. Generous bound that still fails on a regression.
    assert big < 5.0, f"to_directed ctor too slow on 8000-node parent: {big:.2f}ms"


# br-r37-c1-gue3i: a to_directed(as_view=True) view of a Graph / MultiGraph reads
# its degrees from the source's native degree (succ = pred = the source's rows,
# so in = out = the row sum and degree is twice it), summing only the self-loop
# nodes' rows directly - an undirected self-loop counts twice in the source's
# degree but once in the row. Values AND types must be networkx's: int for an
# unweighted or all-int row, float sums in networkx's order.
@pytest.mark.skipif(not HAS_NX, reason="networkx not installed")
@pytest.mark.parametrize("cls", ["Graph", "MultiGraph"])
@pytest.mark.parametrize("seed", range(12))
def test_to_directed_view_degrees_are_networkxs(cls, seed):
    rng = random.Random(seed)
    n = rng.choice([5, 20, 60])
    edges = [(rng.randrange(n), rng.randrange(n)) for _ in range(3 * n)]
    if seed % 3 == 0:
        edges = [(u, v) for u, v in edges if u != v]
    views = []
    for lib in (fnx, nx):
        G = getattr(lib, cls)()
        G.add_nodes_from(range(n))
        weights = random.Random(seed + 1000)
        for u, v in edges:
            w = weights.choice([1, 2, 0.1, 0.2, 0.7, 3.3, None])
            G.add_edge(u, v, **({} if w is None else {"weight": w}))
        views.append((G, G.to_directed(as_view=True)))
    (fg, fv), (ng, nv) = views

    def reads(view):
        out = []
        for attr in ("degree", "in_degree", "out_degree"):
            for weight in (None, "weight", "absent"):
                dv = getattr(view, attr)
                out.append([(k, d, type(d)) for k, d in dv(weight=weight)])
                out.append([(dv(k, weight=weight), type(dv(k, weight=weight))) for k in range(min(n, 6))])
                out.append(list(dv(list(range(0, n, 2)) + [0, 0], weight=weight)))
            out.append([getattr(view, attr)[k] for k in range(min(n, 6))])
        return out

    assert reads(fv) == reads(nv)
    # live: the view reads the source at each call
    fg.add_edge(0, 0, weight=4.5)
    ng.add_edge(0, 0, weight=4.5)
    fg.add_edge(1, 2)
    ng.add_edge(1, 2)
    assert reads(fv) == reads(nv)


# br-r37-c1-gue3i: a to_undirected(as_view=True) view of a DiGraph /
# MultiDiGraph reads a node's degree off the source's rows: networkx's degree
# over the UnionAtlas set(succ) | set(pred) (a pair both ways counts once, its
# multiedge keys as the union of both key sets), float weights summed by one
# sum() in the union's order plus the self-loop's - the view's per-neighbour
# walk summed differently (58.900000000000006 where networkx answers 58.9).
@pytest.mark.skipif(not HAS_NX, reason="networkx not installed")
@pytest.mark.parametrize("cls", ["DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("seed", range(12))
def test_to_undirected_view_degrees_are_networkxs(cls, seed):
    rng = random.Random(seed)
    n = rng.choice([5, 20, 60])
    edges = [(rng.randrange(n), rng.randrange(n)) for _ in range(4 * n)]
    edges += [(v, u) for u, v in edges[: n]]  # reciprocal pairs
    if seed % 3 == 0:
        edges = [(u, v) for u, v in edges if u != v]
    views = []
    for lib in (fnx, nx):
        G = getattr(lib, cls)()
        G.add_nodes_from(range(n))
        weights = random.Random(seed + 1000)
        for u, v in edges:
            w = weights.choice([1, 2, 0.1, 0.2, 0.7, 3.3, None])
            G.add_edge(u, v, **({} if w is None else {"weight": w}))
        views.append((G, G.to_undirected(as_view=True)))
    (fg, fv), (ng, nv) = views

    def reads(view):
        out = []
        for weight in (None, "weight", "absent"):
            dv = view.degree
            out.append([(k, d, type(d)) for k, d in dv(weight=weight)])
            out.append([(dv(k, weight=weight), type(dv(k, weight=weight))) for k in range(n)])
            out.append(list(dv(list(range(0, n, 2)) + [0, 0], weight=weight)))
        out.append([view.degree[k] for k in range(n)])
        return out

    assert reads(fv) == reads(nv)
    # live: the view reads the source at each call
    for G in (fg, ng):
        G.add_edge(0, 0, weight=4.5)
        G.add_edge(1, 2, weight=0.1)
        G.add_edge(2, 1, weight=0.2)
    assert reads(fv) == reads(nv)


@pytest.mark.parametrize("cls", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("mixed", [False, True])
@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("mutated", [False, True])
@pytest.mark.parametrize("mode", ["strict", "hardened"])
def test_conversion_view_interpreter_cancellation_exact(cls, mixed, reverse, mutated, mode):
    values = [0.0, 1e16, 1, -1e16] if mixed else [1e16, 1.0, -1e16]
    with fnx.compatibility_mode(mode):
        views = []
        for lib in (fnx, nx):
            graph = getattr(lib, cls)()
            graph.add_nodes_from(["hub", *range(len(values)), "isolated"])
            items = list(enumerate(values))
            if reverse:
                items.reverse()
            for i, value in items:
                graph.add_edge("hub", i, weight=value)
            graph.add_edge("hub", "hub", weight=0.25)
            view = (graph.to_undirected(as_view=True) if graph.is_directed()
                    else graph.to_directed(as_view=True))
            if mutated:
                attrs = graph["hub"][0]
                if graph.is_multigraph():
                    attrs = attrs[0]
                attrs["weight"] = 0.2
            views.append(view)
        def exact(view):
            def number(value):
                return (type(value).__name__, value.hex() if isinstance(value, float) else repr(value))
            result = []
            names = ("degree", "in_degree", "out_degree") if view.is_directed() else ("degree",)
            for name in names:
                degree = getattr(view, name)
                result.append([(node, number(value)) for node, value in degree(weight="weight")])
                result.append(number(degree("hub", weight="weight")))
                result.append([(node, number(value)) for node, value in
                               degree(["hub", "isolated", "hub"], weight="weight")])
            result.append(number(view.size(weight="weight")))
            return result
        got, want = exact(views[0]), exact(views[1])
        trace = {
            "python": sys.version, "oracle": nx.__version__, "cls": cls, "mixed": mixed,
            "reverse": reverse, "mutated": mutated, "mode": mode, "nodes": list(views[1]),
            "edges": [(u, v, type(data["weight"]).__name__, repr(data["weight"]))
                      for u, v, data in views[1].edges(data=True)], "got": got, "want": want,
        }
        print(json.dumps(trace), flush=True)
        assert got == want, trace


_DEGREE_ACCESSOR_CASES = [
    (cls, conversion, name)
    for cls in ("Graph", "DiGraph", "MultiGraph", "MultiDiGraph")
    for conversion in ("to_directed", "to_undirected")
    for name in (("degree", "in_degree", "out_degree")
                 if conversion == "to_directed" else ("degree",))
]


@needs_nx
@pytest.mark.parametrize("cls,conversion,name", _DEGREE_ACCESSOR_CASES)
def test_conversion_degree_accessor_cache_and_assignment(cls, conversion, name):
    for lib in (nx, fnx):
        graph = getattr(lib, cls)()
        graph.add_edge("a", "b", weight=2)
        view = getattr(graph, conversion)(as_view=True)
        assert name not in vars(view)
        # NetworkX permits assignment even before the cached getter runs.
        replacement = object()
        setattr(view, name, replacement)
        assert getattr(view, name) is replacement
        delattr(view, name)
        held = getattr(view, name)
        assert getattr(view, name) is held
        assert vars(view)[name] is held
        assert held() is held
        setattr(view, name, replacement)
        assert getattr(view, name) is replacement
        delattr(view, name)
        rebuilt = getattr(view, name)
        assert rebuilt is not held
        assert list(rebuilt) == list(held)


@needs_nx
@pytest.mark.parametrize("cls,conversion,name", _DEGREE_ACCESSOR_CASES)
@pytest.mark.parametrize("nested", [False, True])
def test_cached_conversion_degree_wrappers_remain_live(cls, conversion, name, nested):
    pairs = []
    for lib in (nx, fnx):
        graph = getattr(lib, cls)()
        graph.add_nodes_from(["a", "b", "isolated"])
        graph.add_edge("a", "b", weight=2)
        graph.add_edge("a", "a", weight=0.25)
        source = graph
        if nested:
            source = graph.to_directed(as_view=True).to_undirected(as_view=True)
        view = getattr(source, conversion)(as_view=True)
        held = getattr(view, name)
        weighted = held(weight="weight")
        restricted = held(["a", "isolated", "a"], weight="weight")
        pairs.append((graph, view, held, weighted, restricted))

    def reads(pair):
        _, view, held, weighted, restricted = pair
        assert getattr(view, name) is held
        return (
            [(node, value, type(value)) for node, value in held],
            [(node, value, type(value)) for node, value in weighted],
            [(node, value, type(value)) for node, value in restricted],
            (weighted["a"], type(weighted["a"])) if "a" in view else None,
        )

    assert reads(pairs[0]) == reads(pairs[1])
    for graph, *_ in pairs:
        graph.add_edge("isolated", "a", weight=3.5)
        graph.add_edge("b", "b", weight=4)
        attrs = graph["a"]["b"]
        if graph.is_multigraph():
            attrs = attrs[0]
        attrs["weight"] = 0.125
    assert reads(pairs[0]) == reads(pairs[1])
    for graph, *_ in pairs:
        graph.remove_edge("a", "b")
        graph.remove_node("b")
        graph.add_edge("new", "a", weight=6)
    assert reads(pairs[0]) == reads(pairs[1])
    for graph, view, held, weighted, restricted in pairs:
        graph.clear()
        assert getattr(view, name) is held
        assert list(held) == list(weighted) == []
        # A restricted wrapper retains its nbunch, just as NetworkX does.
        for operation in (lambda: weighted["a"], lambda: list(restricted)):
            with pytest.raises(KeyError) as error:
                operation()
            assert error.value.args == ("a",)


@needs_nx
@pytest.mark.parametrize("cls,conversion,name", _DEGREE_ACCESSOR_CASES)
@pytest.mark.parametrize("warm", [False, True])
@pytest.mark.parametrize("nested", [False, True])
def test_cached_conversion_degree_cycles_are_collected(cls, conversion, name, warm, nested):
    def make_refs(lib):
        graph = getattr(lib, cls)()
        graph.add_edge("a", "b")
        source = graph
        if nested:
            source = graph.to_directed(as_view=True).to_undirected(as_view=True)
        view = getattr(source, conversion)(as_view=True)
        if warm:
            held = getattr(view, name)
            assert held is getattr(view, name)
        return weakref.ref(graph), weakref.ref(view)

    for lib in (nx, fnx):
        refs = make_refs(lib)
        gc.collect()
        assert all(ref() is None for ref in refs)


@pytest.mark.parametrize("cls", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("conversion", ["to_directed", "to_undirected"])
def test_partial_conversion_view_is_collected_after_constructor_error(cls, conversion):
    graph = getattr(fnx, cls)()
    graph.add_edge("a", "b")
    base = type(getattr(graph, conversion)(as_view=True))
    failed_refs = []

    class InterruptedView(base):
        @staticmethod
        def _adj_view_type(view):
            failed_refs.append(weakref.ref(view))
            raise ValueError("injected adjacency allocation failure")

    # Nodes/edges already retain the view when adjacency construction fails.
    with pytest.raises(ValueError, match="injected adjacency allocation failure"):
        InterruptedView(graph)
    assert len(failed_refs) == 1
    gc.collect()
    assert failed_refs[0]() is None


@needs_nx
@pytest.mark.parametrize("cls,conversion,name", _DEGREE_ACCESSOR_CASES)
def test_held_conversion_degree_keeps_its_source_alive(cls, conversion, name):
    def make(lib):
        graph = getattr(lib, cls)()
        graph.add_edge("a", "b", weight=2)
        view = getattr(graph, conversion)(as_view=True)
        held = getattr(view, name)(weight="weight")
        return held, (weakref.ref(graph), weakref.ref(view))

    reads = []
    for lib in (nx, fnx):
        held, refs = make(lib)
        gc.collect()
        assert all(ref() is not None for ref in refs)
        before = list(held)
        refs[0]().add_edge("new", "a", weight=3.5)
        reads.append((before, list(held)))
        del held
        gc.collect()
        assert all(ref() is None for ref in refs)
    assert reads[0] == reads[1]


@needs_nx
@pytest.mark.parametrize("cls", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("conversion", ["to_directed", "to_undirected"])
@pytest.mark.parametrize("method", ["copy", "deepcopy", "pickle"])
def test_conversion_degree_cache_does_not_alias_snapshot(cls, conversion, method):
    snapshots = []
    for lib in (nx, fnx):
        graph = getattr(lib, cls)()
        graph.add_edge("a", "b", weight=2)
        graph.add_edge("a", "a", weight=0.25)
        view = getattr(graph, conversion)(as_view=True)
        names = ("degree", "in_degree", "out_degree") if view.is_directed() else ("degree",)
        held = [getattr(view, name) for name in names]
        if method == "copy":
            snapshot = view.copy()
        elif method == "deepcopy":
            snapshot = copy.deepcopy(view)
        else:
            snapshot = pickle.loads(pickle.dumps(view))
        snapshot_degrees = [getattr(snapshot, name) for name in names]
        assert all(cloned is not original for cloned, original in zip(snapshot_degrees, held))
        before = [list(degree(weight="weight")) for degree in snapshot_degrees]
        graph.add_edge("a", "new", weight=3.5)
        assert "new" in view and "new" not in snapshot
        assert [list(degree(weight="weight")) for degree in snapshot_degrees] == before
        snapshots.append(before)
    assert snapshots[0] == snapshots[1]
