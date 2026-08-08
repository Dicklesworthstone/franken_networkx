"""Planarity: Kuratowski closed forms + Euler's formula on the embedding.

check_planarity returns a combinatorial embedding for a planar graph. A valid
embedding of a CONNECTED planar graph satisfies Euler's formula V - E + F = 2,
where F is the number of faces (counted by traversing each face once via
mark_half_edges). This embedding-validity invariant, plus the Kuratowski closed
forms (K5 / K_{3,3} non-planar, K4 planar) and boolean parity with networkx,
pins the planarity machinery.

No mocks: real fnx and real networkx.
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx


def _count_faces(emb):
    """Number of faces: traverse each face once, marking its half-edges."""
    visited = set()
    faces = 0
    for v in emb:
        for w in emb[v]:
            if (v, w) in visited:
                continue
            emb.traverse_face(v, w, mark_half_edges=visited)
            faces += 1
    return faces


def _undirected_edges(g):
    return {frozenset((u, v)) for u, v in g.edges()}


def _smooth(h):
    """Suppress degree-2 vertices, recovering the graph a subdivision came from.

    A Kuratowski subgraph is a *subdivision* of K5 or K_{3,3}, so its branch
    vertices are only visible once the paths between them are contracted back to
    single edges. Kept as a MultiGraph so a contraction that creates a parallel
    edge stays visible instead of silently collapsing.
    """
    m = nx.MultiGraph()
    m.add_nodes_from(h.nodes())
    m.add_edges_from(h.edges())
    changed = True
    while changed:
        changed = False
        for v in list(m.nodes()):
            if m.degree(v) != 2:
                continue
            ends = [x for x in m.neighbors(v) for _ in range(m.number_of_edges(v, x))]
            if len(ends) != 2 or v in ends:      # self-loop at v: not a subdivision path
                continue
            m.remove_node(v)
            m.add_edge(ends[0], ends[1])
            changed = True
            break
    return m


def _is_kuratowski(smoothed):
    """True iff the smoothed graph is K5 or K_{3,3}."""
    simple = nx.Graph(smoothed)
    if simple.number_of_edges() != smoothed.number_of_edges():
        return False                              # parallel edges: not a clean subdivision
    return (nx.is_isomorphic(simple, nx.complete_graph(5))
            or nx.is_isomorphic(simple, nx.complete_bipartite_graph(3, 3)))


def _mixed_graph(seed):
    """Dense enough that BOTH planarity verdicts occur across the seed range."""
    r = random.Random(seed)
    n = r.randint(5, 11)
    edges = [(u, v) for u in range(n) for v in range(u + 1, n) if r.random() < 0.5]
    g = fnx.Graph(); g.add_nodes_from(range(n)); g.add_edges_from(edges)
    return g


def test_kuratowski_closed_forms():
    assert fnx.check_planarity(fnx.complete_graph(4))[0] is True
    assert fnx.check_planarity(fnx.complete_graph(5))[0] is False
    assert fnx.check_planarity(fnx.complete_bipartite_graph(3, 3))[0] is False
    assert fnx.check_planarity(fnx.complete_bipartite_graph(2, 4))[0] is True
    assert fnx.check_planarity(fnx.petersen_graph())[0] is False


@pytest.mark.parametrize("seed", range(40))
def test_planarity_boolean_parity(seed):
    r = random.Random(seed)
    n = r.randint(4, 9)
    edges = [(u, v) for u in range(n) for v in range(u + 1, n) if r.random() < 0.3]
    fg = fnx.Graph(); fg.add_nodes_from(range(n)); fg.add_edges_from(edges)
    ng = nx.Graph(); ng.add_nodes_from(range(n)); ng.add_edges_from(edges)
    assert fnx.check_planarity(fg)[0] == nx.check_planarity(ng)[0]


@pytest.mark.parametrize("seed", range(40))
def test_embedding_satisfies_euler_formula(seed):
    r = random.Random(seed)
    n = r.randint(4, 9)
    edges = [(u, v) for u in range(n) for v in range(u + 1, n) if r.random() < 0.3]
    fg = fnx.Graph(); fg.add_nodes_from(range(n)); fg.add_edges_from(edges)
    is_planar, emb = fnx.check_planarity(fg)
    if not (is_planar and fnx.is_connected(fg) and fg.number_of_edges() > 0):
        pytest.skip("not connected planar with edges")
    v, e = fg.number_of_nodes(), fg.number_of_edges()
    f = _count_faces(emb)
    # Euler's formula for a connected planar embedding.
    assert v - e + f == 2


@pytest.mark.parametrize("seed", range(40))
def test_euler_holds_without_requiring_connectivity(seed):
    """The connected-only test above skips 19 of its 40 seeds; this one skips none.

    Face traversal gives every component its own outer face, so summing Euler
    over the components that carry edges gives V - E + F = 2 * C_edged. Isolated
    vertices own no half-edges and so contribute no face — they are excluded
    from V rather than being allowed to break the identity.
    """
    r = random.Random(seed)
    n = r.randint(4, 9)
    edges = [(u, v) for u in range(n) for v in range(u + 1, n) if r.random() < 0.3]
    fg = fnx.Graph(); fg.add_nodes_from(range(n)); fg.add_edges_from(edges)
    is_planar, emb = fnx.check_planarity(fg)
    assert is_planar, "this sparse family is planar for every seed in range(40)"
    if fg.number_of_edges() == 0:
        pytest.skip("no edges, no faces to traverse")

    components = [c for c in fnx.connected_components(fg) if len(c) > 1]
    v = sum(len(c) for c in components)
    assert v - fg.number_of_edges() + _count_faces(emb) == 2 * len(components)


@pytest.mark.parametrize("seed", range(40))
def test_embedding_is_an_embedding_of_THIS_graph(seed):
    """Euler's formula alone would also hold for an embedding of a different graph."""
    r = random.Random(seed)
    n = r.randint(4, 9)
    edges = [(u, v) for u in range(n) for v in range(u + 1, n) if r.random() < 0.3]
    fg = fnx.Graph(); fg.add_nodes_from(range(n)); fg.add_edges_from(edges)
    is_planar, emb = fnx.check_planarity(fg)
    assert is_planar

    assert set(emb.nodes()) == set(fg.nodes())
    # The embedding is directed (half-edges); as undirected pairs it must be G.
    assert _undirected_edges(emb) == _undirected_edges(fg)
    emb.check_structure()          # raises if the rotation system is inconsistent


@pytest.mark.parametrize("seed", range(40))
def test_planarity_parity_covers_both_verdicts(seed):
    """The sparse family is planar for all 40 seeds, so it only ever compared True."""
    fg = _mixed_graph(seed)
    ng = nx.Graph(); ng.add_nodes_from(fg.nodes()); ng.add_edges_from(fg.edges())
    assert fnx.check_planarity(fg)[0] == nx.check_planarity(ng)[0]


def test_mixed_family_actually_contains_both_verdicts():
    """Guards the test above: if this family drifts to all-planar, it goes vacuous."""
    verdicts = [fnx.check_planarity(_mixed_graph(s))[0] for s in range(40)]
    assert verdicts.count(True) >= 5 and verdicts.count(False) >= 5


@pytest.mark.parametrize(
    "name", ["k5", "k33", "petersen", "k6", "k5_subdivided"],
)
def test_kuratowski_counterexample_is_a_k5_or_k33_subdivision(name):
    """A non-planar verdict must come with a witness, and the witness must be real."""
    graphs = {
        "k5": fnx.complete_graph(5),
        "k33": fnx.complete_bipartite_graph(3, 3),
        "petersen": fnx.petersen_graph(),
        "k6": fnx.complete_graph(6),
        # K5 with one edge subdivided: still non-planar, and the witness must
        # smooth back through the subdivision vertex.
        "k5_subdivided": None,
    }
    if name == "k5_subdivided":
        g = fnx.complete_graph(5)
        g.remove_edge(0, 1); g.add_edge(0, "mid"); g.add_edge("mid", 1)
    else:
        g = graphs[name]

    is_planar, counterexample = fnx.check_planarity(g, counterexample=True)
    assert is_planar is False
    # The witness is a subgraph of the input...
    assert set(counterexample.nodes()) <= set(g.nodes())
    assert _undirected_edges(counterexample) <= _undirected_edges(g)
    # ...it is itself non-planar...
    assert fnx.check_planarity(counterexample)[0] is False
    # ...and it is genuinely a K5 or K_{3,3} subdivision, not just some subgraph.
    assert _is_kuratowski(_smooth(counterexample))


@pytest.mark.parametrize("seed", range(40))
def test_random_counterexamples_are_kuratowski_subdivisions(seed):
    g = _mixed_graph(seed)
    is_planar, counterexample = fnx.check_planarity(g, counterexample=True)
    if is_planar:
        pytest.skip("planar draw: no counterexample to validate")
    assert _undirected_edges(counterexample) <= _undirected_edges(g)
    assert _is_kuratowski(_smooth(counterexample))
