"""Float-tolerance contract for accumulative centralities at the Python API.

NetworkX accumulates these centralities by summing many floating-point terms in
a specific traversal order (e.g. ``harmonic_centrality`` does
``centrality[u] += 1 / d`` iterating sources in node order; Brandes betweenness
sums dependency contributions in BFS-stack order). franken_networkx's Rust
kernels are numerically equivalent but accumulate in their own order, so the
results agree with networkx only up to floating-point round-off (~1e-15 here),
NOT bit-for-bit. This is by design and matches the project's conformance
contract, which compares centrality scores with a 1e-12 absolute tolerance
(1e-9 for HITS) — see ``centrality_score_tolerance`` in fnx-conformance.

``degree_centrality`` is the exception: its single reciprocal-multiply was
made bit-exact (it does ``s = 1/(n-1); d*s`` like nx), so it is asserted
exactly here as a guard against that fix regressing. So is unweighted Brandes
betweenness, node and edge (br-r37-c1-79ceg): its per-source accumulation
already follows networkx's order, and once its dependency term used
networkx's association - ``sigma[v] * ((1 + delta[w]) / sigma[w])``, not
``(sigma[v] / sigma[w]) * (1 + delta[w])`` - every value came out identical.

This test documents the policy (so an exact-float probe doesn't re-file ~1e-16
"bugs") and guards the tolerance bound at the public Python boundary — distinct
from the Rust-fixture conformance harness. A regression that pushed a kernel
past 1e-12 would trip it.
"""

import networkx as nx
import franken_networkx as fnx

import pytest

_TOL = 1e-12


def _build(mod, weighted=False):
    g = mod.Graph()
    edges = []
    for i in range(20):
        edges.append((i, (i + 1) % 20))
        edges.append((i, (i + 3) % 20))
        if i % 2 == 0:
            edges.append((i, (i + 7) % 20))
    for j, (u, v) in enumerate(edges):
        if u == v:
            continue
        if weighted:
            g.add_edge(u, v, weight=1.0 + ((j * 7) % 11) / 3.0)
        else:
            g.add_edge(u, v)
    return g


_UNWEIGHTED = [
    ("betweenness", lambda m, g: m.betweenness_centrality(g)),
    ("betweenness_unnormalized", lambda m, g: m.betweenness_centrality(g, normalized=False)),
    ("harmonic", lambda m, g: m.harmonic_centrality(g)),
    ("closeness", lambda m, g: m.closeness_centrality(g)),
    ("closeness_wf_false", lambda m, g: m.closeness_centrality(g, wf_improved=False)),
    ("load", lambda m, g: m.load_centrality(g)),
    ("eigenvector", lambda m, g: m.eigenvector_centrality(g, max_iter=3000, tol=1e-12)),
]

_WEIGHTED = [
    ("betweenness_w", lambda m, g: m.betweenness_centrality(g, weight="weight")),
    ("closeness_distance", lambda m, g: m.closeness_centrality(g, distance="weight")),
]


def _assert_close(label, dn, df):
    assert set(dn) == set(df), f"{label}: key set differs"
    worst = max((abs(dn[k] - df[k]) for k in dn), default=0.0)
    assert worst <= _TOL, f"{label}: max abs diff {worst:.3e} exceeds tolerance {_TOL:.0e}"


@pytest.mark.parametrize("label,fn", _UNWEIGHTED, ids=[c[0] for c in _UNWEIGHTED])
def test_unweighted_centrality_within_tolerance(label, fn):
    _assert_close(label, fn(nx, _build(nx)), fn(fnx, _build(fnx)))


@pytest.mark.parametrize("label,fn", _WEIGHTED, ids=[c[0] for c in _WEIGHTED])
def test_weighted_centrality_within_tolerance(label, fn):
    _assert_close(label, fn(nx, _build(nx, weighted=True)), fn(fnx, _build(fnx, weighted=True)))


def test_edge_betweenness_within_tolerance():
    gn, gf = _build(nx), _build(fnx)
    dn = {tuple(sorted(k)): v for k, v in nx.edge_betweenness_centrality(gn).items()}
    df = {tuple(sorted(k)): v for k, v in fnx.edge_betweenness_centrality(gf).items()}
    _assert_close("edge_betweenness", dn, df)


def test_degree_centrality_is_bit_exact():
    # degree_centrality was deliberately made bit-exact (s = 1/(n-1); d*s).
    gn, gf = _build(nx), _build(fnx)
    assert fnx.degree_centrality(gf) == nx.degree_centrality(gn)


def _brandes_graphs():
    # BA800 takes the rayon-chunked source arm (>= 500 nodes); the others the
    # sequential one.
    yield "karate", nx.karate_club_graph()
    yield "BA400", nx.barabasi_albert_graph(400, 3, seed=2)
    yield "WS200", nx.connected_watts_strogatz_graph(200, 6, 0.3, seed=1)
    yield "gnp300 directed", nx.gnp_random_graph(300, 0.03, seed=5, directed=True)
    yield "BA800", nx.barabasi_albert_graph(800, 3, seed=9)


def _twins(g):
    """``g`` rebuilt from its edge stream in networkx and in fnx. Both copies
    get the same adjacency rows - the rebuild can reorder an undirected row
    against ``g``'s own - so both libraries traverse in the same order."""
    twins = []
    for lib in (nx, fnx):
        twin = lib.DiGraph() if g.is_directed() else lib.Graph()
        twin.add_nodes_from(g)
        twin.add_edges_from(g.edges())
        twins.append(twin)
    return twins


@pytest.mark.parametrize(
    "kwargs",
    [{}, {"normalized": False}, {"endpoints": True}, {"k": 20, "seed": 3}],
    ids=["default", "unnormalized", "endpoints", "k-sampled"],
)
def test_unweighted_betweenness_is_bit_exact(kwargs):
    for name, g in _brandes_graphs():
        nx_twin, fnx_twin = _twins(g)
        expected = nx.betweenness_centrality(nx_twin, **kwargs)
        actual = fnx.betweenness_centrality(fnx_twin, **kwargs)
        differ = [n for n in expected if actual[n] != expected[n]]
        assert not differ, (name, len(differ), differ[:3])


def test_unweighted_edge_betweenness_is_bit_exact():
    for name, g in _brandes_graphs():
        nx_twin, fnx_twin = _twins(g)
        expected = nx.edge_betweenness_centrality(nx_twin)
        actual = fnx.edge_betweenness_centrality(fnx_twin)
        assert set(actual) == set(expected), name
        differ = [e for e in expected if actual[e] != expected[e]]
        assert not differ, (name, len(differ), differ[:3])


@pytest.mark.parametrize("normalized", [True, False], ids=["normalized", "unnormalized"])
def test_unweighted_load_centrality_is_bit_exact(normalized):
    """br-r37-c1-f0uiy: networkx walks a source's reached nodes as
    sorted((length, vert)) from the end - ties at one distance in node-VALUE
    order - and the kernel takes that order as ranks."""
    for name, g in _brandes_graphs():
        nx_twin, fnx_twin = _twins(g)
        expected = nx.load_centrality(nx_twin, normalized=normalized)
        actual = fnx.load_centrality(fnx_twin, normalized=normalized)
        differ = [n for n in expected if actual[n] != expected[n]]
        assert not differ, (name, len(differ), differ[:3])


def _load_outcome(call):
    try:
        value = call()
    except Exception as exc:  # noqa: BLE001 - the exception IS the parity subject
        return (type(exc).__name__, str(exc))
    return ("ok", repr(value), type(value).__name__)


@pytest.mark.parametrize("cls", ["Graph", "DiGraph", "MultiGraph"])
@pytest.mark.parametrize("weight", [None, "weight"])
@pytest.mark.parametrize("normalized", [True, False], ids=["normalized", "unnormalized"])
def test_single_node_load_centrality_is_networkx_to_the_last_bit(cls, weight, normalized):
    """br-r37-c1-96x14: v= answers from the whole-graph kernel. networkx's
    single-node path sums v's per-source load in node order and scales it as
    its whole-graph path does that node, so the value must be identical - and
    a v that is not a node (networkx: 0.0) or is unhashable (TypeError) must
    keep networkx's answer too."""
    import random

    for seed in range(6):
        rng = random.Random(seed)
        n = rng.choice([1, 2, 3, 9, 40, 90])
        edges = [
            (rng.randrange(n), rng.randrange(n), rng.choice([1, 2, 0.5, 1.5, 3]))
            for _ in range(rng.randint(0, 3 * n))
        ]
        twins = []
        for lib in (fnx, nx):
            graph = getattr(lib, cls)()
            graph.add_nodes_from(range(n))
            graph.add_weighted_edges_from(edges)
            twins.append(graph)
        for v in [*range(min(n, 5)), n + 5, "absent", [1]]:
            got = _load_outcome(
                lambda: fnx.load_centrality(twins[0], v=v, weight=weight, normalized=normalized)
            )
            want = _load_outcome(
                lambda: nx.load_centrality(twins[1], v=v, weight=weight, normalized=normalized)
            )
            assert got == want, (seed, n, v)


def test_load_centrality_ties_follow_node_values_not_insertion():
    """str nodes inserted out of lexicographic order, tuple nodes, and a
    MultiGraph (whose load is its simple projection's)."""
    base = nx.barabasi_albert_graph(150, 3, seed=11)
    names = {n: f"v{(n * 37) % 150:03d}" for n in base}
    str_graph = nx.relabel_nodes(base, names)
    grid = nx.grid_2d_graph(9, 11)
    for name, g in (("str nodes", str_graph), ("grid tuples", grid)):
        nx_twin, fnx_twin = _twins(g)
        expected = nx.load_centrality(nx_twin)
        actual = fnx.load_centrality(fnx_twin)
        assert not [n for n in expected if actual[n] != expected[n]], name
        # cutoff= runs the Python port, which sorts the same pairs; v= reads
        # the kernel's value for the node (br-r37-c1-96x14).
        expected = nx.load_centrality(nx_twin, cutoff=4)
        actual = fnx.load_centrality(fnx_twin, cutoff=4)
        assert not [n for n in expected if actual[n] != expected[n]], (name, "cutoff")
        node = list(g)[7]
        assert fnx.load_centrality(fnx_twin, v=node) == nx.load_centrality(nx_twin, v=node), name

    multi_edges = list(base.edges()) + [(u, v) for u, v in base.edges() if (u + v) % 4 == 0]
    nx_multi, fnx_multi = nx.MultiGraph(), fnx.MultiGraph()
    for g in (nx_multi, fnx_multi):
        g.add_nodes_from(base)
        g.add_edges_from(multi_edges)
    expected = nx.load_centrality(nx_multi)
    actual = fnx.load_centrality(fnx_multi)
    assert not [n for n in expected if actual[n] != expected[n]]


def test_load_centrality_unsortable_tie_raises_as_networkx_does():
    """networkx compares the node objects of a distance tie: an int and a
    str at one distance raise TypeError there, so fnx must not answer."""
    edges = [("hub", 0), ("hub", "a"), (0, "z"), ("a", "z")]
    nx_graph, fnx_graph = nx.Graph(edges), fnx.Graph(edges)
    with pytest.raises(TypeError) as expected:
        nx.load_centrality(nx_graph)
    with pytest.raises(TypeError) as actual:
        fnx.load_centrality(fnx_graph)
    assert str(actual.value) == str(expected.value)


@pytest.mark.parametrize("wf_improved", [True, False], ids=["wf", "no-wf"])
def test_closeness_centrality_wf_improved_is_native_and_bit_exact(wf_improved):
    """br-r37-c1-mub4s: wf_improved=False only skips networkx's per-node
    Wasserman-Faust multiply; it runs the native kernel like the default.
    The disconnected graph is where the flag changes the values."""
    disconnected = nx.disjoint_union(nx.barabasi_albert_graph(60, 2, seed=3), nx.path_graph(9))
    graphs = list(_brandes_graphs()) + [("disconnected", disconnected)]
    for name, g in graphs:
        nx_twin, fnx_twin = _twins(g)
        expected = nx.closeness_centrality(nx_twin, wf_improved=wf_improved)
        actual = fnx.closeness_centrality(fnx_twin, wf_improved=wf_improved)
        assert list(actual) == list(expected), name
        assert not [n for n in expected if actual[n] != expected[n]], name
    nx_multi, fnx_multi = nx.MultiGraph(), fnx.MultiGraph()
    for multi in (nx_multi, fnx_multi):
        multi.add_nodes_from(disconnected)
        multi.add_edges_from(list(disconnected.edges()) * 2)
    assert fnx.closeness_centrality(fnx_multi, wf_improved=wf_improved) == nx.closeness_centrality(
        nx_multi, wf_improved=wf_improved
    )
