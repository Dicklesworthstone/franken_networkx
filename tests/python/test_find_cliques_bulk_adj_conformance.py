"""Conformance harness for `_fnx.find_cliques_adjacency_sets` — the bulk
adjacency-sets builder wired into `franken_networkx.find_cliques`
(br-r37-c1-tvf43, peer commit 9fd0d7c3).

REVIEW MODE Tick 14 audit (br-r37-c1-zz30b) found that the previous
parity claims for this binding had been silently going through the
Python-comprehension fallback because the venv `.so` predated the
binding's registration. This harness closes that hole by:

1. Asserting the binding is actually loaded (catches stale `.so` AND
   missing registration in `crates/fnx-python/src/algorithms.rs::register`).
2. Locking iteration-order parity between the Rust binding and the
   Python comprehension `{v for v in _GRAPH_NEIGHBORS(G, u) if v != u}`
   that the wrapper falls back to. Both produce a Python `set`, but
   `find_cliques` does `max(subgraph, key=lambda n: len(candidates &
   adjacency[n]))` — set iteration order does not matter for `&` /
   `len`, BUT it DOES matter for how nx tie-breaks via `subgraph.pop()`
   in deeper recursion. So a future "optimization" that swaps the
   `PySet::new` for a `frozenset(sorted(...))` would silently change
   the clique enumeration order.
3. Locking adjacency-set CONTENT equality (every node maps to the same
   neighbor set in both paths).
4. Locking output equality between the Rust-fast-path and the
   Python-fallback `find_cliques(G)` results — by toggling the binding
   reference at runtime via monkeypatch.
"""

from __future__ import annotations

import pytest

import franken_networkx as fnx
import networkx as nx


pytest.importorskip("franken_networkx._fnx")


def _binding_or_skip():
    try:
        from franken_networkx._fnx import find_cliques_adjacency_sets
    except ImportError as exc:  # pragma: no cover — caught by next assert
        pytest.fail(
            "find_cliques_adjacency_sets is missing from the loaded "
            "_fnx.abi3.so — likely a stale build. Rebuild fnx-python "
            f"and reinstall the wheel ({exc!s})."
        )
    return find_cliques_adjacency_sets


FIXTURES = [
    ("karate", fnx.karate_club_graph, nx.karate_club_graph),
    ("florentine", fnx.florentine_families_graph, nx.florentine_families_graph),
    ("davis", fnx.davis_southern_women_graph, nx.davis_southern_women_graph),
    ("petersen", fnx.petersen_graph, nx.petersen_graph),
    ("K10", lambda: fnx.complete_graph(10), lambda: nx.complete_graph(10)),
    ("path7", lambda: fnx.path_graph(7), lambda: nx.path_graph(7)),
    ("cycle8", lambda: fnx.cycle_graph(8), lambda: nx.cycle_graph(8)),
    ("K33", lambda: fnx.complete_bipartite_graph(3, 3),
     lambda: nx.complete_bipartite_graph(3, 3)),
]


def test_binding_is_registered():
    """The Rust binding must be importable from the loaded .so.

    Catches: stale .so, missing m.add_function(...) registration in
    crates/fnx-python/src/algorithms.rs::register, accidental rename.
    """
    binding = _binding_or_skip()
    assert callable(binding)
    G = fnx.path_graph(3)
    out = binding(G)
    assert isinstance(out, dict)
    assert set(out.keys()) == {0, 1, 2}
    assert all(isinstance(v, set) for v in out.values())


@pytest.mark.parametrize("name,fnx_factory,_nx_factory", FIXTURES, ids=[f[0] for f in FIXTURES])
def test_bulk_adj_matches_python_comprehension(name, fnx_factory, _nx_factory):
    """Locks parity vs the wrapper-bypass fallback path.

    The wrapper at __init__.py:7311 picks `_raw_find_cliques_adjacency_sets(G)`
    when present and falls back to `{u: {v for v in _raw(G,u) if v != u} for u in G}`
    otherwise. Both must produce IDENTICAL adjacency dicts (same key
    order, same neighbor sets) so swapping between paths cannot drift
    the clique enumeration order.
    """
    binding = _binding_or_skip()
    from franken_networkx import _GRAPH_NEIGHBORS

    G = fnx_factory()
    rust_adj = binding(G)
    py_adj = {u: {v for v in _GRAPH_NEIGHBORS(G, u) if v != u} for u in G}

    assert list(rust_adj.keys()) == list(py_adj.keys()), (
        f"{name}: dict insertion order diverged between Rust binding "
        f"and Python comprehension — find_cliques traversal will be "
        f"non-deterministic across paths."
    )
    for k in rust_adj:
        assert rust_adj[k] == py_adj[k], (
            f"{name}: neighbor set for {k!r} differs: "
            f"rust={rust_adj[k]!r} vs py={py_adj[k]!r}"
        )


@pytest.mark.parametrize("name,fnx_factory,nx_factory", FIXTURES, ids=[f[0] for f in FIXTURES])
def test_find_cliques_output_matches_nx(name, fnx_factory, nx_factory):
    """End-to-end: the bulk-adj fast path produces nx-equal cliques."""
    _binding_or_skip()
    G = fnx_factory()
    G_n = nx_factory()
    fnx_cliques = sorted(sorted(c, key=str) for c in fnx.find_cliques(G))
    nx_cliques = sorted(sorted(c, key=str) for c in nx.find_cliques(G_n))
    assert fnx_cliques == nx_cliques


@pytest.mark.parametrize("name,fnx_factory,_nx_factory", FIXTURES, ids=[f[0] for f in FIXTURES])
def test_find_cliques_fast_path_matches_fallback(monkeypatch, name, fnx_factory, _nx_factory):
    """Set-equal comparison of fnx.find_cliques output across both paths.

    Toggles `_raw_find_cliques_adjacency_sets` to None (forcing the
    Python comprehension fallback) and asserts the fast path produces
    the same multiset of cliques. The order of cliques can drift
    because `max(subgraph, key=...)` is a tie-break over a Python set,
    but the SET of cliques (sorted) must match exactly.
    """
    _binding_or_skip()

    G = fnx_factory()
    fast_cliques = sorted(sorted(c, key=str) for c in fnx.find_cliques(G))

    monkeypatch.setattr(fnx, "_raw_find_cliques_adjacency_sets", None)
    G2 = fnx_factory()
    fallback_cliques = sorted(sorted(c, key=str) for c in fnx.find_cliques(G2))

    assert fast_cliques == fallback_cliques, (
        f"{name}: bulk-adj Rust path and Python-comprehension fallback "
        f"emit different clique sets — silent ordering drift."
    )


def test_bulk_adj_drops_self_loops():
    """`find_cliques` requires self-loops EXCLUDED from the adjacency
    sets (they otherwise corrupt pivot selection: `len(candidates &
    adjacency[v])` would include v itself for any v with a self-loop)."""
    binding = _binding_or_skip()
    G = fnx.Graph()
    G.add_edges_from([(1, 2), (2, 3), (3, 1)])
    G.add_edge(1, 1)  # self-loop on 1
    G.add_edge(2, 2)  # self-loop on 2
    adj = binding(G)
    assert 1 not in adj[1], "self-loop on 1 leaked into adj[1]"
    assert 2 not in adj[2], "self-loop on 2 leaked into adj[2]"


def test_bulk_adj_isolated_nodes_get_empty_set():
    """Isolated nodes are present as keys with an empty neighbor set
    — find_cliques relies on every node ∈ G appearing in the dict."""
    binding = _binding_or_skip()
    G = fnx.Graph()
    G.add_nodes_from([10, 20, 30])
    G.add_edge(10, 20)
    adj = binding(G)
    assert set(adj.keys()) == {10, 20, 30}
    assert adj[30] == set()
    assert adj[10] == {20}
    assert adj[20] == {10}


def test_bulk_adj_rejects_directed():
    """Bulk-adj is only meaningful for undirected `Graph` (clique
    enumeration is undirected). Directed input must raise
    NetworkXNotImplemented, not return a wrong-shaped dict."""
    binding = _binding_or_skip()
    DG = fnx.DiGraph()
    DG.add_edges_from([(1, 2), (2, 3)])
    with pytest.raises(nx.NetworkXNotImplemented):
        binding(DG)
