"""Observable-output lock for the batched ``karate_club_graph`` builder.

Bead br-r37-c1-p4qjj. The builder used to walk Zachary's 34x34 interaction
matrix cell by cell, calling ``G.add_edge(row, col, weight=entry)`` once per
nonzero cell (155 PyO3 crossings) and then writing ``G.nodes[v]['club']`` node
by node (34 more). That measured 0.3762x against live NetworkX. It now parses
the matrix once into a memoised stream and replays it through a single batched
``add_edges_from``, with the ``club`` attribute folded into the single
``add_nodes_from``.

The batch rewrite is only legitimate if it is observationally identical, and
"identical" here is sharper than it looks, because **Zachary's matrix is not
symmetric**:

  * seven pairs disagree across the diagonal — (0,12), (2,32), (8,32), (8,33),
    (22,33), (23,29), (29,32) — so the duplicate lower-triangle entry is what
    decides the final weight under last-write-wins; and
  * M[22][33] is 0 while M[33][22] is 3, so that edge exists *only* because row
    33 emits it, and it therefore lands late in insertion order.

So an "obvious" upper-triangle optimisation would drop one edge and mis-weight
seven others. These tests are written to fail loudly if anyone tries it, and to
fail if the batch path's duplicate-merge semantics ever diverge from sequential
``add_edge``.
"""

from __future__ import annotations

import networkx as nx
import pytest

import franken_networkx as fnx


def _reference_karate():
    """Zachary's graph built the pre-batch way: one ``add_edge`` per cell.

    Spelled out here rather than imported so the lock survives the batch
    implementation being edited — this is the oracle the batch must reproduce.
    """
    club1 = frozenset({0, 1, 2, 3, 4, 5, 6, 7, 8, 10, 11, 12, 13, 16, 17, 19, 21})
    graph = fnx.Graph()
    graph.add_nodes_from(range(34))
    for row, line in enumerate(fnx._KARATE_CLUB_MATRIX.split("\n")):
        thisrow = [int(b) for b in line.split()]
        for col, entry in enumerate(thisrow):
            if entry >= 1:
                graph.add_edge(row, col, weight=entry)
    for node in graph:
        graph.nodes[node]["club"] = "Mr. Hi" if node in club1 else "Officer"
    graph.graph["name"] = "Zachary's Karate Club"
    return graph


def _matrix():
    return [
        [int(b) for b in line.split()]
        for line in fnx._KARATE_CLUB_MATRIX.split("\n")
    ]


def test_matrix_is_asymmetric_so_both_triangles_are_load_bearing():
    """Guard the premise the builder's correctness rests on."""
    matrix = _matrix()
    assert len(matrix) == 34
    assert {len(row) for row in matrix} == {34}

    disagreeing = {
        (i, j)
        for i in range(34)
        for j in range(i + 1, 34)
        if matrix[i][j] != matrix[j][i]
    }
    assert disagreeing == {(0, 12), (2, 32), (8, 32), (8, 33), (22, 33), (23, 29), (29, 32)}

    # The edge that exists only below the diagonal. If a future rewrite walks
    # the upper triangle alone, this pair vanishes from the graph entirely.
    assert matrix[22][33] == 0
    assert matrix[33][22] == 3

    # No cell on the diagonal, so the builder never has to reason about
    # self-loops.
    assert all(matrix[i][i] == 0 for i in range(34))


def test_edge_stream_is_the_full_row_major_traversal():
    stream = fnx._karate_club_edge_stream()
    matrix = _matrix()
    expected = tuple(
        (row, col, matrix[row][col])
        for row in range(34)
        for col in range(34)
        if matrix[row][col] >= 1
    )
    assert stream == expected
    assert len(stream) == 155  # both triangles, not the 78 distinct edges


def test_edge_stream_memo_is_stable_across_calls():
    assert fnx._karate_club_edge_stream() is fnx._karate_club_edge_stream()


def test_matches_the_per_cell_reference_builder_exactly():
    built = fnx.karate_club_graph()
    reference = _reference_karate()

    assert list(built.nodes) == list(reference.nodes)
    assert list(built.edges) == list(reference.edges)
    assert [built.edges[e]["weight"] for e in built.edges] == [
        reference.edges[e]["weight"] for e in reference.edges
    ]
    assert [built.nodes[n]["club"] for n in built.nodes] == [
        reference.nodes[n]["club"] for n in reference.nodes
    ]
    assert built.graph == reference.graph

    # Adjacency row order, not just the edge list: drop-in code iterates these.
    assert {n: list(built.adj[n]) for n in built} == {
        n: list(reference.adj[n]) for n in reference
    }


def test_matches_live_networkx():
    built = fnx.karate_club_graph()
    oracle = nx.karate_club_graph()

    assert list(built.nodes) == list(oracle.nodes)
    assert list(built.edges) == list(oracle.edges)
    assert built.number_of_nodes() == 34
    assert built.number_of_edges() == 78
    assert [built.edges[e]["weight"] for e in built.edges] == [
        oracle.edges[e]["weight"] for e in oracle.edges
    ]
    assert [built.nodes[n]["club"] for n in built.nodes] == [
        oracle.nodes[n]["club"] for n in oracle.nodes
    ]
    assert {n: list(built.adj[n]) for n in built} == {
        n: list(oracle.adj[n]) for n in oracle
    }


@pytest.mark.parametrize(
    ("pair", "expected_weight"),
    # For every asymmetric pair the LOWER-triangle cell wins, because row j
    # runs after row i and overwrites. A batch path whose duplicate merge kept
    # the first write instead of the last would flip all seven.
    [
        ((0, 12), 1),
        ((2, 32), 2),
        ((8, 32), 3),
        ((8, 33), 4),
        ((22, 33), 3),
        ((23, 29), 3),
        ((29, 32), 4),
    ],
)
def test_asymmetric_pairs_keep_last_write_wins_weight(pair, expected_weight):
    built = fnx.karate_club_graph()
    oracle = nx.karate_club_graph()
    assert built.edges[pair]["weight"] == expected_weight
    assert oracle.edges[pair]["weight"] == expected_weight


def test_lower_triangle_only_edge_is_present_and_ordered_late():
    """(22, 33) exists solely because row 33 emits it."""
    built = fnx.karate_club_graph()
    assert built.has_edge(22, 33)

    edges = list(built.edges)
    assert (22, 33) in edges
    # It is the very last edge 22 acquires, since every other 22-incident edge
    # was inserted by an earlier row.
    assert list(built.adj[22])[-1] == 33


def test_repeated_calls_do_not_share_mutable_attribute_state():
    """The memoised stream must not leak attr dicts between graphs."""
    first = fnx.karate_club_graph()
    second = fnx.karate_club_graph()
    assert first is not second

    first.nodes[0]["club"] = "MUTATED"
    first.edges[0, 1]["weight"] = 9999
    first.graph["name"] = "MUTATED"

    third = fnx.karate_club_graph()
    for other in (second, third):
        assert other.nodes[0]["club"] == "Mr. Hi"
        assert other.edges[0, 1]["weight"] == 4
        assert other.graph["name"] == "Zachary's Karate Club"


def test_club_partition_matches_the_paper():
    built = fnx.karate_club_graph()
    mr_hi = {n for n in built if built.nodes[n]["club"] == "Mr. Hi"}
    assert mr_hi == {0, 1, 2, 3, 4, 5, 6, 7, 8, 10, 11, 12, 13, 16, 17, 19, 21}
    assert {built.nodes[n]["club"] for n in built} == {"Mr. Hi", "Officer"}
    # Documented spot checks from nx's own docstring.
    assert built.nodes[5]["club"] == "Mr. Hi"
    assert built.nodes[9]["club"] == "Officer"


def test_graph_is_undirected_simple_and_unfrozen():
    built = fnx.karate_club_graph()
    assert isinstance(built, fnx.Graph)
    assert not built.is_directed()
    assert not built.is_multigraph()
    assert nx.number_of_selfloops(built) == 0
    built.add_edge(0, 33)  # a freshly returned generator graph stays mutable
    assert built.has_edge(0, 33)
