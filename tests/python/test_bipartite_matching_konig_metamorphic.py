"""Oracle-free / metamorphic tests for bipartite matching + vertex cover.

These cross-check independent algorithms against each other and against the
theorems that define them — finding correctness bugs that differential-only
testing can miss:

- **König's theorem**: in a bipartite graph, the size of a maximum matching
  equals the size of a minimum vertex cover.
- **Definitional invariant**: the complement of a vertex cover is an
  independent set (no edge has both endpoints outside the cover).
- **Differential parity**: matching size matches networkx.

No mocks: real fnx + real networkx on randomly generated bipartite graphs.

br-r37-c1-a93hl
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx
from franken_networkx.algorithms import bipartite as fbp
from networkx.algorithms import bipartite as nbp


def _random_bipartite(seed):
    r = random.Random(seed)
    n1 = r.randint(2, 7)
    n2 = r.randint(2, 7)
    top = list(range(n1))
    bot = list(range(n1, n1 + n2))
    edges = [(u, v) for u in top for v in bot if r.random() < 0.4]
    g = fnx.Graph()
    g.add_nodes_from(top)
    g.add_nodes_from(bot)
    g.add_edges_from(edges)
    return g, top, bot, edges


@pytest.mark.parametrize("seed", range(60))
def test_konig_matching_equals_vertex_cover(seed):
    g, top, bot, edges = _random_bipartite(seed)
    if not edges:
        pytest.skip("empty graph")
    matching = fbp.hopcroft_karp_matching(g, top_nodes=top)
    matching_size = len(matching) // 2
    cover = fbp.to_vertex_cover(g, matching, top_nodes=top)
    # König: |max matching| == |min vertex cover|.
    assert matching_size == len(cover)


@pytest.mark.parametrize("seed", range(60))
def test_vertex_cover_complement_is_independent(seed):
    g, top, bot, edges = _random_bipartite(seed)
    if not edges:
        pytest.skip("empty graph")
    matching = fbp.hopcroft_karp_matching(g, top_nodes=top)
    cover = fbp.to_vertex_cover(g, matching, top_nodes=top)
    complement = set(g.nodes()) - set(cover)
    # The complement of a vertex cover must be an independent set.
    for u, v in edges:
        assert not (u in complement and v in complement), (
            f"edge ({u},{v}) uncovered: cover is not valid"
        )


@pytest.mark.parametrize("seed", range(60))
def test_matching_size_matches_networkx(seed):
    g, top, bot, edges = _random_bipartite(seed)
    if not edges:
        pytest.skip("empty graph")
    ng = nx.Graph()
    ng.add_nodes_from(top)
    ng.add_nodes_from(bot)
    ng.add_edges_from(edges)
    fnx_size = len(fbp.hopcroft_karp_matching(g, top_nodes=top)) // 2
    nx_size = len(nbp.hopcroft_karp_matching(ng, top_nodes=top)) // 2
    assert fnx_size == nx_size


def test_konig_on_complete_bipartite_closed_form():
    # K_{m,n}: maximum matching is min(m, n); so is the min vertex cover.
    for m, n in [(3, 5), (4, 4), (2, 7), (6, 3)]:
        g = fnx.complete_bipartite_graph(m, n)
        top = list(range(m))
        matching = fbp.hopcroft_karp_matching(g, top_nodes=top)
        assert len(matching) // 2 == min(m, n)
        cover = fbp.to_vertex_cover(g, matching, top_nodes=top)
        assert len(cover) == min(m, n)


def _maximum_matching_size(top, adjacency):
    """Kuhn's augmenting-path algorithm — an oracle that does not call fnx.

    König ties the matching to the cover, but a matching and a cover that were
    BOTH wrong by the same amount would still satisfy it. This computes the
    maximum independently. (Cross-checked against exhaustive search over all
    edge subsets on the smaller draws: they agree.)
    """
    partner = {}

    def augment(u, seen):
        for v in adjacency.get(u, ()):
            if v in seen:
                continue
            seen.add(v)
            if v not in partner or augment(partner[v], seen):
                partner[v] = u
                return True
        return False

    return sum(1 for u in top if augment(u, set()))


@pytest.mark.parametrize("seed", range(60))
def test_returned_matching_is_actually_a_matching(seed):
    """The suite validates the COVER thoroughly and never the matching itself."""
    g, top, bot, edges = _random_bipartite(seed)
    matching = fbp.hopcroft_karp_matching(g, top_nodes=top)

    # Symmetric: the dict reports both directions of each pair.
    for u, v in matching.items():
        assert matching.get(v) == u
        # A matched pair has to be an edge of the graph.
        assert g.has_edge(u, v)
    # No node is matched to two different partners.
    assert len(set(matching.values())) == len(matching)
    assert set(matching) <= set(g.nodes())


@pytest.mark.parametrize("seed", range(60))
def test_matching_is_maximum_not_merely_maximal(seed):
    """König holds for a wrong matching paired with an equally wrong cover."""
    g, top, bot, edges = _random_bipartite(seed)
    adjacency = {u: list(g.neighbors(u)) for u in top}
    assert len(fbp.hopcroft_karp_matching(g, top_nodes=top)) // 2 == _maximum_matching_size(
        top, adjacency
    )
