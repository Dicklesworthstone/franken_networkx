"""Iteration order of the sets networkx functions return (br-r37-c1-n4j4k).

A set iterates in slot order, and wherever hashes collide the slots depend on
how the set was built - its insertion order, and whether its table was sized up
front (set(dict)) or grown one add at a time. networkx builds each of these sets
in a defined order: descendants / ancestors add bfs_edges' children as they are
discovered; node_connected_component and weakly_connected_components are
_plain_bfs's seen set; kosaraju adds each node as its DFS marks it;
biconnected_components is set(chain.from_iterable(edges)); descendants_at_distance
is set(bfs layer); attracting_components yields strongly_connected_components'
own sets; node_boundary and non_neighbors are set expressions. fnx built the same
members in other orders (a Rust HashSet, a DFS, a sorted component), so list()
of the result differed for up to half the cases below while every set compared
equal. Labels scaled x1024 collide in any table under 1024 slots.

No mocks: real fnx against real networkx, both graphs from one edge stream.
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx


def _edges(scale, seed):
    r = random.Random(seed)
    edges, off = [], 0
    for size in (50, 30, 20):
        for a, b in nx.barabasi_albert_graph(size, 2, seed=seed + size).edges():
            edges.append((scale * (a + off), scale * (b + off)))
        off += size
    edges += [(scale * r.randrange(120), scale * r.randrange(120)) for _ in range(10)]
    edges = [(b, a) if r.random() < 0.5 else (a, b) for a, b in edges]
    r.shuffle(edges)
    nodes = [scale * x for x in r.sample(range(130), 130)]
    return edges, nodes, r


def _twins(cls_name, scale, seed):
    edges, nodes, r = _edges(scale, seed)
    if cls_name.startswith("Multi"):
        edges = edges + edges[::5]
    fg, ng = getattr(fnx, cls_name)(), getattr(nx, cls_name)()
    for g in (fg, ng):
        g.add_nodes_from(nodes)
        g.add_edges_from(edges)
    return fg, ng, r


def _ordered(result):
    """list() all the way down: the order a caller iterating the result sees."""
    if isinstance(result, (set, frozenset, list, tuple)) or hasattr(result, "__next__"):
        return [_ordered(x) for x in result]
    return result


UNDIRECTED = {
    "node_connected_component": lambda m, G, s: m.node_connected_component(G, s),
    "descendants": lambda m, G, s: m.descendants(G, s),
    "ancestors": lambda m, G, s: m.ancestors(G, s),
    "descendants_at_distance": lambda m, G, s: m.descendants_at_distance(G, s, 2),
    "biconnected_components": lambda m, G, s: m.biconnected_components(G),
    "node_boundary": lambda m, G, s: m.node_boundary(G, list(G)[:15]),
    "node_boundary_nbunch2": lambda m, G, s: m.node_boundary(G, list(G)[:15], list(G)[10:90]),
    "non_neighbors": lambda m, G, s: m.non_neighbors(G, s),
}
DIRECTED = {
    "descendants": lambda m, G, s: m.descendants(G, s),
    "ancestors": lambda m, G, s: m.ancestors(G, s),
    "descendants_at_distance": lambda m, G, s: m.descendants_at_distance(G, s, 2),
    "weakly_connected_components": lambda m, G, s: m.weakly_connected_components(G),
    "kosaraju_strongly_connected_components": lambda m, G, s: m.kosaraju_strongly_connected_components(G),
    "attracting_components": lambda m, G, s: m.attracting_components(G),
    "non_neighbors": lambda m, G, s: m.non_neighbors(G, s),
}
CASES = [(cls, name, fn) for cls in ("Graph", "MultiGraph") for name, fn in UNDIRECTED.items()] + [
    (cls, name, fn) for cls in ("DiGraph", "MultiDiGraph") for name, fn in DIRECTED.items()
]


@pytest.mark.parametrize("seed", range(3))
@pytest.mark.parametrize("scale", [1, 37, 1024])
@pytest.mark.parametrize("cls, name, fn", CASES, ids=[f"{c}-{n}" for c, n, _ in CASES])
def test_set_results_iterate_in_networkx_order(cls, name, fn, scale, seed):
    fg, ng, r = _twins(cls, scale, seed)
    nodes = list(ng)
    for source in [r.choice(nodes) for _ in range(4)]:
        want = _ordered(fn(nx, ng, source))
        got = _ordered(fn(fnx, fg, source))
        assert got == want, (cls, name, scale, seed, source)


@pytest.mark.parametrize(
    "make",
    [
        lambda m, g: g.subgraph(list(g)[::2] + list(g)[1:40:2]),
        lambda m, g: g.copy(as_view=True),
        lambda m, g: m.restricted_view(g, list(g)[:5], []),
        lambda m, g: m.DiGraph(g.edges()).to_undirected(as_view=True),
    ],
    ids=["subgraph", "copy_view", "restricted_view", "undirected_view_of_digraph"],
)
def test_non_neighbors_order_on_views(make):
    fg, ng, r = _twins("Graph", 1024, 5)
    fv, nv = make(fnx, fg), make(nx, ng)
    for node in list(nv)[:40]:
        assert list(fnx.non_neighbors(fv, node)) == list(nx.non_neighbors(nv, node)), node


@pytest.mark.parametrize("cls", ["Graph", "DiGraph"])
def test_non_neighbors_follows_node_changes(cls):
    # The node dict it reads is cached per nodes_seq: a node added or removed
    # after a call must show in the next one, in networkx's order.
    fg, ng, r = _twins(cls, 1024, 6)
    assert list(fnx.non_neighbors(fg, 0)) == list(nx.non_neighbors(ng, 0))
    for step in range(6):
        for g in (fg, ng):
            if step % 2:
                g.remove_node(1024 * (step + 3))
            else:
                g.add_edge(1024 * (500 + step), 0)
        assert list(fnx.non_neighbors(fg, 0)) == list(nx.non_neighbors(ng, 0)), step


def test_non_neighbors_errors_match_networkx():
    fg, ng, r = _twins("Graph", 1, 7)
    for node in (10_000, [1]):
        with pytest.raises(Exception) as want:
            nx.non_neighbors(ng, node)
        with pytest.raises(type(want.value)) as got:
            fnx.non_neighbors(fg, node)
        assert got.value.args == want.value.args


@pytest.mark.parametrize(
    "nbunch1",
    [lambda: [10_000, 0, 1], lambda: iter([0, 1, 2]), lambda: {0: 1, 5: 2}.keys(), lambda: ()],
    ids=["with_absent_node", "iterator", "dict_keys", "empty"],
)
def test_node_boundary_takes_what_networkx_takes(nbunch1):
    # nodes not in G are skipped, and any iterable is walked once, in order.
    fg, ng, r = _twins("Graph", 1024, 7)
    assert list(fnx.node_boundary(fg, nbunch1())) == list(nx.node_boundary(ng, nbunch1()))


# br-r37-c1-ygt3z: community sets. k_clique_communities yields
# frozenset.union(*component) of the percolation graph's BFS set, and
# louvain_communities the sets networkx's moves left behind; fnx built the
# same members another way (a union-find over sorted (k-1)-subsets, sorted
# native lists), so their order differed for most graphs below.


def _dense_twins(scale, seed):
    r = random.Random(seed)
    edges = [(scale * u, scale * v) for u, v in nx.gnp_random_graph(60, 0.25, seed=seed).edges()]
    r.shuffle(edges)
    return fnx.Graph(edges), nx.Graph(edges)


@pytest.mark.parametrize("seed", range(3))
@pytest.mark.parametrize("scale", [1, 37, 1024])
@pytest.mark.parametrize("k", [2, 3, 4])
def test_k_clique_communities_iterate_in_networkx_order(k, scale, seed):
    for fg, ng in (_twins("Graph", scale, seed)[:2], _dense_twins(scale, seed)):
        want = _ordered(nx.community.k_clique_communities(ng, k))
        assert _ordered(fnx.community.k_clique_communities(fg, k)) == want, (k, scale, seed)


def test_k_clique_communities_takes_what_networkx_takes():
    # Unorderable labels (the subsets it replaced were sorted), given cliques
    # with a repeat, and k < 2 raised at the first next(), as networkx does.
    edges = [("a", 1), (1, "b"), ("b", "a"), ("b", 2.5), (2.5, "a")]
    fg, ng = fnx.Graph(edges), nx.Graph(edges)
    assert _ordered(fnx.community.k_clique_communities(fg, 3)) == _ordered(
        nx.community.k_clique_communities(ng, 3)
    )
    cliques = [[1, 2, 3], [2, 3, 4], [1, 2, 3], [7, 8]]
    assert _ordered(fnx.community.k_clique_communities(fg, 2, cliques=cliques)) == _ordered(
        nx.community.k_clique_communities(ng, 2, cliques=cliques)
    )
    communities = fnx.community.k_clique_communities(fg, 1)
    with pytest.raises(nx.NetworkXError, match="k=1, k must be greater than 1."):
        next(communities)


def test_k_clique_communities_is_not_combinatorial_in_clique_size():
    # One 28-clique, k=14: networkx tests one clique; the (k-1)-subset
    # union-find walked C(28, 13) = 37 million subsets (16 s here).
    import time

    start = time.perf_counter()
    got = list(fnx.community.k_clique_communities(fnx.complete_graph(28), 14))
    assert time.perf_counter() - start < 2.0
    assert got == list(nx.community.k_clique_communities(nx.complete_graph(28), 14))


def _weighted_twins(cls_name, scale, seed):
    fg, ng, r = _twins(cls_name, scale, seed)
    weights = {}
    for g in (ng, fg):
        for u, v, d in g.edges(data=True):
            d["weight"] = weights.setdefault((u, v), r.randint(1, 5))
    return fg, ng


@pytest.mark.parametrize("seed", range(3))
@pytest.mark.parametrize("scale", [1, 37, 1024])
@pytest.mark.parametrize("cls", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
def test_louvain_communities_iterate_in_networkx_order(cls, scale, seed):
    fg, ng, r = _twins(cls, scale, seed)
    for kwargs in ({"seed": seed}, {"seed": seed, "max_level": 1}, {"seed": seed, "resolution": 0.5}):
        want = _ordered(nx.community.louvain_communities(ng, **kwargs))
        assert _ordered(fnx.community.louvain_communities(fg, **kwargs)) == want, kwargs


@pytest.mark.parametrize("cls", ["Graph", "DiGraph"])
def test_louvain_weighted_and_every_level_iterate_in_networkx_order(cls):
    fg, ng = _weighted_twins(cls, 1024, 4)
    assert _ordered(fnx.community.louvain_communities(fg, seed=9)) == _ordered(
        nx.community.louvain_communities(ng, seed=9)
    )
    assert _ordered(fnx.community.louvain_partitions(fg, seed=9)) == _ordered(
        nx.community.louvain_partitions(ng, seed=9)
    )


def test_louvain_edgeless_graph_yields_networkx_singletons():
    fg, ng = fnx.Graph(), nx.Graph()
    for g in (fg, ng):
        g.add_nodes_from([1024 * i for i in (5, 0, 9, 3)])
    assert _ordered(fnx.community.louvain_communities(fg, seed=1)) == _ordered(
        nx.community.louvain_communities(ng, seed=1)
    )
    assert _ordered(fnx.community.louvain_partitions(fg, seed=1)) == _ordered(
        nx.community.louvain_partitions(ng, seed=1)
    )
