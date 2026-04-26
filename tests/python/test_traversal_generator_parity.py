"""Parity for traversal/path/clique iterator return types.

Bead br-r37-c1-682kr. Eight functions returned ``list`` or
``list_iterator`` (eager Rust materialisation or eager Python list-build)
while nx returns true generators (lazy):

- all_simple_paths, shortest_simple_paths
- enumerate_all_cliques, find_cliques, find_cliques_recursive
- bfs_edges, dfs_edges
- lexicographical_topological_sort

Drop-in code doing ``isinstance(result, types.GeneratorType)`` failed;
short-circuit patterns like ``next(all_simple_paths(huge_graph, ...))``
materialise the entire result on fnx vs. one path on nx — could be
unbounded.

Fix converts each function to a generator (``yield``/``yield from``),
matching nx's lazy evaluation contract.
"""

from __future__ import annotations

import types

import pytest

import franken_networkx as fnx

try:
    import networkx as nx
    HAS_NX = True
except ImportError:
    HAS_NX = False

needs_nx = pytest.mark.skipif(not HAS_NX, reason="networkx not installed")


# ---------------------------------------------------------------------------
# Each entry: function name, factory taking the library that builds the call.
# ---------------------------------------------------------------------------
PROBES = [
    ("all_simple_paths",
     lambda lib: lib.all_simple_paths(lib.path_graph(5), 0, 4)),
    ("shortest_simple_paths",
     lambda lib: lib.shortest_simple_paths(lib.path_graph(5), 0, 4)),
    ("enumerate_all_cliques",
     lambda lib: lib.enumerate_all_cliques(lib.complete_graph(3))),
    ("find_cliques",
     lambda lib: lib.find_cliques(lib.complete_graph(3))),
    ("find_cliques_recursive",
     lambda lib: lib.find_cliques_recursive(lib.complete_graph(3))),
    ("bfs_edges",
     lambda lib: lib.bfs_edges(lib.path_graph(5), 0)),
    ("dfs_edges",
     lambda lib: lib.dfs_edges(lib.path_graph(5), 0)),
    ("lexicographical_topological_sort",
     lambda lib: lib.lexicographical_topological_sort(
         lib.DiGraph([(0, 1), (1, 2)]))),
]


@needs_nx
@pytest.mark.parametrize(
    "name,factory", PROBES,
    ids=[entry[0] for entry in PROBES],
)
def test_returns_generator_like_networkx(name, factory):
    f_result = factory(fnx)
    assert isinstance(f_result, types.GeneratorType), (
        f"fnx.{name} returned {type(f_result).__name__}, expected generator"
    )


@needs_nx
@pytest.mark.parametrize(
    "name,factory", PROBES,
    ids=[entry[0] for entry in PROBES],
)
def test_values_match_networkx(name, factory):
    f_result = list(factory(fnx))
    n_result = list(factory(nx))
    # Some return iterators of lists/tuples in different orders. Compare
    # multiset.
    f_canon = sorted([tuple(p) if isinstance(p, list) else p for p in f_result])
    n_canon = sorted([tuple(p) if isinstance(p, list) else p for p in n_result])
    assert f_canon == n_canon, (
        f"{name}: fnx={f_canon[:3]}... nx={n_canon[:3]}..."
    )


@needs_nx
def test_all_simple_paths_lazy_short_circuit():
    """next() on the generator returns one path immediately."""
    G = fnx.complete_graph(6)
    paths = fnx.all_simple_paths(G, 0, 5)
    first = next(paths)
    assert isinstance(first, list)
    assert first[0] == 0 and first[-1] == 5


@needs_nx
def test_dfs_edges_error_raised_on_iteration_not_call():
    """nx raises NetworkXError when the generator is iterated, not when
    called — fnx now matches this lazy behaviour."""
    G = fnx.path_graph(3)
    # The call should not raise; iteration should.
    gen = fnx.dfs_edges(G, source=99)
    assert isinstance(gen, types.GeneratorType)
    with pytest.raises(fnx.NetworkXError):
        next(gen)


@needs_nx
def test_bfs_edges_error_raised_on_iteration_not_call():
    G = fnx.path_graph(3)
    gen = fnx.bfs_edges(G, source=99)
    assert isinstance(gen, types.GeneratorType)
    with pytest.raises(fnx.NetworkXError):
        next(gen)


@needs_nx
def test_all_simple_paths_source_equals_target_yields_single():
    """When source==target, a single [source] path should yield."""
    G = fnx.path_graph(5)
    paths = fnx.all_simple_paths(G, 2, 2)
    assert isinstance(paths, types.GeneratorType)
    result = list(paths)
    assert result == [[2]]


@needs_nx
def test_find_cliques_with_explicit_nodes_yields_lazily():
    """find_cliques with non-None nodes also yields rather than returning
    a list."""
    G = fnx.complete_graph(5)
    gen = fnx.find_cliques(G, nodes=[0, 1])
    assert isinstance(gen, types.GeneratorType)
    cliques = list(gen)
    assert len(cliques) >= 1


@needs_nx
def test_lexicographical_topological_sort_yields_lazily():
    G = fnx.DiGraph()
    G.add_edges_from([(0, 1), (1, 2), (2, 3)])
    gen = fnx.lexicographical_topological_sort(G)
    assert isinstance(gen, types.GeneratorType)
    first = next(gen)
    assert first == 0


@needs_nx
def test_shortest_simple_paths_yields_lazily():
    G = fnx.complete_graph(5)
    gen = fnx.shortest_simple_paths(G, 0, 4)
    assert isinstance(gen, types.GeneratorType)
    first_path = next(gen)
    assert first_path[0] == 0 and first_path[-1] == 4
