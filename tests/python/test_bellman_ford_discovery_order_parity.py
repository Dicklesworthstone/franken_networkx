"""Parity for Bellman-Ford shortest-path dict KEY ORDER (SPFA discovery order).

Bead br-r37-c1-e9rea.

networkx implements Bellman-Ford as the SPFA variant and builds its dist/pred
dicts in **first-discovery (first-relaxation) order** during the deque walk —
NOT sorted by distance. A node at distance 3 can therefore precede a node at
distance 2 in the returned dict (e.g. ``{s:0, a:1, b:3, c:2, d:3}``).

fnx previously reconstructed the order in the Python layer with a BFS-from-source
hop-order tie-break (the same path that was right for unweighted BFS but wrong
for Dijkstra/Bellman-Ford), giving ~66% key-order divergence on weighted graphs.

The fix has the Rust SPFA kernel record discovery order and the leaf/all_pairs
functions return order-preserving ``Vec<(node, value)>``; the Python wrappers
now trust that order directly (no distance sort). These tests pin the *key
order* (and values) to nx across directed and undirected graphs, including
negative weights. Graphs are built from an identical edge sequence so
adjacency-insertion order — which drives SPFA discovery — matches.
"""

from __future__ import annotations

import random

import pytest

import franken_networkx as fnx

try:
    import networkx as nx
    HAS_NX = True
except ImportError:
    HAS_NX = False

needs_nx = pytest.mark.skipif(not HAS_NX, reason="networkx not installed")


@needs_nx
def test_witness_not_distance_sorted():
    """A graph whose SPFA discovery order is provably not distance-sorted."""
    edges = [('s', 'a', 1), ('s', 'b', 5), ('a', 'c', 1),
             ('b', 'c', 1), ('a', 'd', 10), ('c', 'd', 1)]
    f, n = fnx.Graph(), nx.Graph()
    for u, v, w in edges:
        f.add_edge(u, v, weight=w)
        n.add_edge(u, v, weight=w)
    fo = list(fnx.single_source_bellman_ford_path_length(f, 's', weight='weight').keys())
    no = list(nx.single_source_bellman_ford_path_length(n, 's', weight='weight').keys())
    assert fo == no
    # confirm it is genuinely not distance-sorted (regression guard)
    d = dict(nx.single_source_bellman_ford_path_length(n, 's', weight='weight'))
    assert [d[k] for k in no] != sorted(d[k] for k in no)


def _build(lib, edges, directed):
    g = lib.DiGraph() if directed else lib.Graph()
    for u, v, w in edges:
        g.add_edge(u, v, weight=w)
    return g


@needs_nx
@pytest.mark.parametrize("directed", [False, True])
@pytest.mark.parametrize("seed", list(range(40)))
def test_random_single_source_key_order(directed, seed):
    rng = random.Random(seed * 23 + (6 if directed else 1))
    n = rng.randint(3, 10)
    nodes = list(range(n))
    rng.shuffle(nodes)
    fg = fnx.DiGraph() if directed else fnx.Graph()
    ng = nx.DiGraph() if directed else nx.Graph()
    for u in nodes:
        fg.add_node(u)
        ng.add_node(u)
    seen = set()
    target = rng.randint(0, n * (n - 1) // (1 if directed else 2))
    tries = 0
    while ng.number_of_edges() < target and tries < target * 5 + 10:
        tries += 1
        u, v = rng.sample(nodes, 2)
        key = (u, v) if directed else tuple(sorted((u, v)))
        if key in seen:
            continue
        seen.add(key)
        w = float(rng.choice([1, 1, 2, 2, 3]))
        fg.add_edge(u, v, weight=w)
        ng.add_edge(u, v, weight=w)
    for s in nodes:
        fp = fnx.single_source_bellman_ford_path(fg, s, weight="weight")
        npp = nx.single_source_bellman_ford_path(ng, s, weight="weight")
        assert list(fp.keys()) == list(npp.keys()), f"path d={directed} seed={seed} s={s}"
        assert dict(fp) == dict(npp)
        fl = fnx.single_source_bellman_ford_path_length(fg, s, weight="weight")
        nl = nx.single_source_bellman_ford_path_length(ng, s, weight="weight")
        assert list(fl.keys()) == list(nl.keys())
        assert dict(fl) == dict(nl)
        fd2, fp2 = fnx.single_source_bellman_ford(fg, s, weight="weight")
        nd2, np2 = nx.single_source_bellman_ford(ng, s, weight="weight")
        assert list(fd2.keys()) == list(nd2.keys())
        assert list(fp2.keys()) == list(np2.keys())


@needs_nx
@pytest.mark.parametrize("directed", [False, True])
@pytest.mark.parametrize("seed", list(range(25)))
def test_random_all_pairs_key_order(directed, seed):
    rng = random.Random(seed * 19 + (8 if directed else 3))
    n = rng.randint(3, 9)
    nodes = list(range(n))
    rng.shuffle(nodes)
    fg = fnx.DiGraph() if directed else fnx.Graph()
    ng = nx.DiGraph() if directed else nx.Graph()
    for u in nodes:
        fg.add_node(u)
        ng.add_node(u)
    seen = set()
    target = rng.randint(0, n * 2)
    tries = 0
    while ng.number_of_edges() < target and tries < target * 5 + 10:
        tries += 1
        u, v = rng.sample(nodes, 2)
        key = (u, v) if directed else tuple(sorted((u, v)))
        if key in seen:
            continue
        seen.add(key)
        w = float(rng.choice([1, 1, 2, 3]))
        fg.add_edge(u, v, weight=w)
        ng.add_edge(u, v, weight=w)
    fap = dict(fnx.all_pairs_bellman_ford_path(fg, weight="weight"))
    nap = dict(nx.all_pairs_bellman_ford_path(ng, weight="weight"))
    assert list(fap.keys()) == list(nap.keys())
    for s in nap:
        assert list(fap[s].keys()) == list(nap[s].keys()), f"path d={directed} seed={seed} s={s}"
        assert dict(fap[s]) == dict(nap[s])
    fal = dict(fnx.all_pairs_bellman_ford_path_length(fg, weight="weight"))
    nal = dict(nx.all_pairs_bellman_ford_path_length(ng, weight="weight"))
    assert list(fal.keys()) == list(nal.keys())
    for s in nal:
        assert list(fal[s].keys()) == list(nal[s].keys()), f"len d={directed} seed={seed} s={s}"


@needs_nx
@pytest.mark.parametrize("seed", list(range(20)))
def test_negative_weights_key_order(seed):
    rng = random.Random(seed * 7 + 100)
    n = rng.randint(3, 8)
    directed = bool(seed % 2)
    nodes = list(range(n))
    rng.shuffle(nodes)
    fg = fnx.DiGraph() if directed else fnx.Graph()
    ng = nx.DiGraph() if directed else nx.Graph()
    for u in nodes:
        fg.add_node(u)
        ng.add_node(u)
    seen = set()
    target = rng.randint(0, n * 2)
    tries = 0
    while ng.number_of_edges() < target and tries < target * 5 + 10:
        tries += 1
        u, v = rng.sample(nodes, 2)
        key = (u, v) if directed else tuple(sorted((u, v)))
        if key in seen:
            continue
        seen.add(key)
        w = float(rng.choice([-2, -1, 1, 1, 2, 3]))
        fg.add_edge(u, v, weight=w)
        ng.add_edge(u, v, weight=w)
    for s in nodes:
        try:
            nl = nx.single_source_bellman_ford_path_length(ng, s, weight="weight")
            n_neg = False
        except nx.NetworkXUnbounded:
            n_neg = True
        try:
            fl = fnx.single_source_bellman_ford_path_length(fg, s, weight="weight")
            f_neg = False
        except Exception as e:  # noqa: BLE001
            f_neg = "Unbounded" in type(e).__name__
        assert n_neg == f_neg, f"cycle-detect mismatch seed={seed} s={s}"
        if n_neg:
            continue
        assert list(fl.keys()) == list(nl.keys())
        assert dict(fl) == dict(nl)


# br-r37-c1-qnj0n: the SPFA reads each node's row when it first pops the node
# and keeps state only for what it reaches (it built a weighted CSR of every
# edge first: 9 ms of kernel against networkx's 17 us beside a 32k-node
# component, plus an uncached 17 ms type scan per call). Twins below carry a
# REMOVED node, so node storage is non-dense and rows must be read by position,
# and negative weights that improve already-seen nodes, so a path must follow
# the predecessor of the LAST strict improvement.
_IMPROVING_EDGES = [
    ("gone", "s", 1), ("s", "a", 4), ("s", "b", 1), ("b", "a", -2), ("a", "c", 1),
    ("b", "c", 3), ("c", "d", -1), ("s", "d", 5), ("d", "e", 2), ("b", "e", 4),
    ("e", "f", 1), ("a", "f", 3), ("far", "s", 2),
]


def _improving_twins(directed):
    graphs = []
    for lib in (fnx, nx):
        g = lib.DiGraph() if directed else lib.Graph()
        for u, v, w in _IMPROVING_EDGES:
            g.add_edge(u, v, weight=w)
        g.remove_node("gone")
        graphs.append(g)
    return graphs


@needs_nx
def test_improved_nodes_follow_the_last_improvement_like_networkx():
    fg, ng = _improving_twins(directed=True)
    dist, paths = fnx.single_source_bellman_ford(fg, "s")
    nx_dist, nx_paths = nx.single_source_bellman_ford(ng, "s")
    assert list(dist.items()) == list(nx_dist.items())
    assert list(paths.items()) == list(nx_paths.items())
    assert fnx.bellman_ford_path(fg, "s", "f") == nx.bellman_ford_path(ng, "s", "f")
    assert list(fnx.single_source_bellman_ford_path_length(fg, "s").items()) == list(
        nx.single_source_bellman_ford_path_length(ng, "s").items()
    )
    # "a" is first reached at 4 from s and improved to -1 through b.
    assert nx_paths["a"] == ["s", "b", "a"]


@needs_nx
def test_undirected_negative_edge_is_a_negative_cycle_like_networkx():
    fg, ng = _improving_twins(directed=False)
    for call in (
        lambda m, g: m.single_source_bellman_ford(g, "s"),
        lambda m, g: m.single_source_bellman_ford_path_length(g, "s"),
        lambda m, g: m.bellman_ford_path(g, "s", "f"),
    ):
        with pytest.raises(nx.NetworkXUnbounded) as nx_error:
            call(nx, ng)
        with pytest.raises(fnx.NetworkXUnbounded) as fnx_error:
            call(fnx, fg)
        assert fnx_error.value.args == nx_error.value.args


def _small_component_beside_a_ring(lib, ring):
    graph = lib.DiGraph()
    graph.add_edges_from((i, i + 1, {"weight": (i % 3) - 1 + 2 * (i % 2)}) for i in range(9))
    graph.add_edges_from(
        (100 + i, 100 + (i + 1) % ring, {"weight": 1}) for i in range(ring)
    )
    return graph


def _best_of(fn, reps=30, rounds=7):
    import time

    fn()
    best = None
    for _ in range(rounds):
        start = time.perf_counter()
        for _ in range(reps):
            fn()
        elapsed = (time.perf_counter() - start) / reps
        best = elapsed if best is None else min(best, elapsed)
    return best


_BF_PARENTS = {
    (lib.__name__, ring): _small_component_beside_a_ring(lib, ring)
    for lib in (fnx, nx)
    for ring in (200, 12800)
} if HAS_NX else {}


@needs_nx
@pytest.mark.parametrize(
    "call",
    [
        lambda m, g: m.single_source_bellman_ford_path_length(g, 0),
        lambda m, g: m.single_source_bellman_ford(g, 0),
        lambda m, g: m.bellman_ford_path(g, 0, 5),
    ],
    ids=["path_length", "single_source", "path"],
)
def test_bounded_bellman_ford_cost_does_not_grow_with_the_parent(call):
    """A walk inside a 10-node component beside a disconnected ring of 200 vs
    12800 nodes. networkx is flat; fnx's growth is judged against networkx's in
    the same process at the same moment, which calibrates the bound under load.
    The whole-graph weight CSR and the uncached type scan grew ~60x here."""
    growth = {}
    for lib in (fnx, nx):
        small = _BF_PARENTS[(lib.__name__, 200)]
        large = _BF_PARENTS[(lib.__name__, 12800)]
        growth[lib.__name__] = _best_of(lambda: call(lib, large)) / _best_of(
            lambda: call(lib, small)
        )
    assert growth["franken_networkx"] < 2.5 * max(growth["networkx"], 1.0), growth


@pytest.mark.parametrize("cls", ["Graph", "DiGraph"])
@pytest.mark.parametrize("weights", ["float", "int", "mixed"])
def test_all_pairs_bellman_ford_source_distance_is_the_int_zero(cls, weights):
    """networkx seeds dist = {source: 0}, so a source's own distance is the int 0
    whatever the weights; the native all-pairs path returned the kernel's 0.0 for
    float weights. == cannot see it (0 == 0.0), so compare the types too."""
    value = {"float": lambda i: float(i % 3) + 0.5, "int": lambda i: i % 3 + 1,
             "mixed": lambda i: float(i) + 0.5 if i % 2 else i + 1}[weights]
    edges = [(i, (i + 1) % 8, value(i)) for i in range(8)] + [(0, 4, value(9))]
    rows = {}
    for name, lib in (("nx", nx), ("fnx", fnx)):
        graph = getattr(lib, cls)()
        graph.add_weighted_edges_from(edges)
        rows[name] = [
            (source, [(target, type(d).__name__, d) for target, d in lengths.items()])
            for source, lengths in lib.all_pairs_bellman_ford_path_length(graph)
        ]
    assert rows["fnx"] == rows["nx"]
