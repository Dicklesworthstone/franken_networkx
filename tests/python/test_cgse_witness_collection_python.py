"""``franken_networkx._fnx.cgse.collect_witnesses`` drains CGSE witnesses from Python.

Before this binding the witness ledger was reachable only from Rust integration
tests; the README promised a reproducibility receipt per execution that Python
could not observe. ``collect_witnesses(func)`` runs ``func()`` with the
thread-local ledger armed and returns ``(result, [ComplexityWitness, ...])``.

Only kernels that call ``cgse_begin`` emit. From the public Python surface that
is currently: connected components, BFS/DFS edges and trees, Kruskal MST,
Bellman-Ford and the DFS-based strongly-connected count. Public routes for the
other reference algorithms (topological sort, Prim, matching, Dijkstra, Euler)
reach sibling kernels that are not instrumented yet and yield an empty list;
the planted negative below pins that an un-instrumented call reports nothing
rather than a fabricated witness.
"""

import pytest

import franken_networkx as fnx
from franken_networkx._fnx import cgse


def _graph():
    G = fnx.Graph()
    G.add_edges_from([(0, 1), (1, 2), (2, 3), (3, 0), (4, 5)])
    G.add_edge(1, 3, weight=2.5)
    G.add_edge(0, 2, weight=0.5)
    return G


def test_result_passes_through_unchanged():
    G = _graph()
    result, witnesses = cgse.collect_witnesses(lambda: list(fnx.bfs_edges(G, 0)))
    assert result == list(fnx.bfs_edges(G, 0))
    assert len(witnesses) == 1


@pytest.mark.parametrize(
    ("call", "policy_id", "dominant_term"),
    [
        (lambda G: list(fnx.connected_components(G)), "lex_min", "n_plus_m"),
        (lambda G: fnx.number_connected_components(G), "lex_min", "n_plus_m"),
        (lambda G: list(fnx.bfs_edges(G, 0)), "insertion_order", "n_plus_m"),
        (lambda G: list(fnx.dfs_edges(G, 0)), "insertion_order", "n_plus_m"),
        (lambda G: fnx.minimum_spanning_tree(G), "weight_then_lex", "m_log_m"),
    ],
)
def test_reference_kernels_emit_one_witness_with_the_registered_policy(
    call, policy_id, dominant_term
):
    G = _graph()
    _, witnesses = cgse.collect_witnesses(lambda: call(G))
    assert len(witnesses) == 1, witnesses
    w = witnesses[0]
    assert isinstance(w, cgse.ComplexityWitness)
    assert (w.n, w.m) == (G.number_of_nodes(), G.number_of_edges())
    assert w.policy.id() == policy_id
    assert w.dominant_term == dominant_term
    assert w.observed_count > 0
    assert len(w.decision_path_hash) == 64  # blake3 hex
    assert int(w.decision_path_hash, 16) != 0


def test_witnesses_are_reproducible_and_input_sensitive():
    G = _graph()
    _, first = cgse.collect_witnesses(lambda: list(fnx.connected_components(G)))
    _, second = cgse.collect_witnesses(lambda: list(fnx.connected_components(G)))
    assert [w.decision_path_hash for w in first] == [w.decision_path_hash for w in second]

    H = _graph()
    H.add_edge(5, 6)
    _, other = cgse.collect_witnesses(lambda: list(fnx.connected_components(H)))
    assert other[0].n == first[0].n + 1
    assert other[0].decision_path_hash != first[0].decision_path_hash


def test_several_calls_inside_one_scope_are_all_collected_in_order():
    G = _graph()

    def workload():
        list(fnx.bfs_edges(G, 0))
        fnx.minimum_spanning_tree(G)
        list(fnx.connected_components(G))
        return "done"

    result, witnesses = cgse.collect_witnesses(workload)
    assert result == "done"
    assert [w.policy.id() for w in witnesses] == [
        "insertion_order",
        "weight_then_lex",
        "lex_min",
    ]


def test_uninstrumented_kernels_emit_nothing():
    """Planted negative: a non-reference algorithm must not fabricate a witness."""
    G = _graph()
    result, witnesses = cgse.collect_witnesses(lambda: fnx.degree_centrality(G))
    assert result == fnx.degree_centrality(G)
    assert witnesses == []


def test_witnesses_outside_a_scope_are_not_carried_into_the_next_one():
    G = _graph()
    list(fnx.bfs_edges(G, 0))  # outside any scope: not recorded
    _, witnesses = cgse.collect_witnesses(lambda: None)
    assert witnesses == []


def test_exceptions_propagate_unchanged():
    def boom():
        raise ValueError("boom")

    with pytest.raises(ValueError, match="boom"):
        cgse.collect_witnesses(boom)
