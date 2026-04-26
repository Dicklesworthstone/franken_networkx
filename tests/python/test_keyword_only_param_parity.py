"""Parity for parameter KIND (KEYWORD_ONLY vs POSITIONAL_OR_KEYWORD).

Bead br-r37-c1-cirha. fnx exposed many params as POSITIONAL_OR_KEYWORD
that nx declares as KEYWORD_ONLY (after a ``*`` in the signature).
Forward-compat issue: code using positional form on fnx breaks when
ported to nx. Fix inserted ``*`` before the documented keyword-only
params in each Python wrapper, plus a Python wrapper around the Rust
binding for ``number_of_spanning_trees``.
"""

from __future__ import annotations

import inspect

import pytest

import franken_networkx as fnx

try:
    import networkx as nx
    HAS_NX = True
except ImportError:
    HAS_NX = False

needs_nx = pytest.mark.skipif(not HAS_NX, reason="networkx not installed")


# Each entry: function name, list of params expected to be KEYWORD_ONLY.
KEYWORD_ONLY_EXPECTATIONS = [
    # dfs_* family
    ("dfs_edges", ["sort_neighbors"]),
    ("dfs_tree", ["sort_neighbors"]),
    ("dfs_predecessors", ["sort_neighbors"]),
    ("dfs_successors", ["sort_neighbors"]),
    ("dfs_preorder_nodes", ["sort_neighbors"]),
    ("dfs_postorder_nodes", ["sort_neighbors"]),
    # random tree/forest generators
    ("random_spanning_tree", ["multiplicative", "seed"]),
    ("random_labeled_tree", ["seed"]),
    ("random_labeled_rooted_tree", ["seed"]),
    ("random_unlabeled_tree", ["number_of_trees", "seed"]),
    ("random_unlabeled_rooted_tree", ["number_of_trees", "seed"]),
    ("random_unlabeled_rooted_forest", ["q", "number_of_forests", "seed"]),
    # graph generators with create_using moved to keyword-only
    ("connected_watts_strogatz_graph", ["create_using"]),
    ("dense_gnm_random_graph", ["create_using"]),
    ("duplication_divergence_graph", ["create_using"]),
    ("gnm_random_graph", ["create_using"]),
    ("random_lobster_graph", ["create_using"]),
    ("random_powerlaw_tree", ["create_using"]),
    ("generalized_petersen_graph", ["create_using"]),
    # other functions
    ("directed_edge_swap", ["nswap", "max_tries", "seed"]),
    ("from_numpy_array", ["nodelist"]),
    ("harmonic_diameter", ["weight"]),
    ("identified_nodes", ["store_contraction_as"]),
    ("number_of_spanning_trees", ["root", "weight"]),
    ("subgraph_view", ["filter_node", "filter_edge"]),
]


@needs_nx
@pytest.mark.parametrize(
    "name,kw_only", KEYWORD_ONLY_EXPECTATIONS,
    ids=[entry[0] for entry in KEYWORD_ONLY_EXPECTATIONS],
)
def test_param_kind_matches_networkx(name, kw_only):
    f = getattr(fnx, name)
    n = getattr(nx, name)
    fp = inspect.signature(f).parameters
    np_ = inspect.signature(n).parameters

    for p in kw_only:
        assert p in fp, f"fnx.{name} is missing param {p}"
        assert p in np_, f"nx.{name} is missing param {p}"
        assert fp[p].kind == inspect.Parameter.KEYWORD_ONLY, (
            f"fnx.{name}.{p} should be KEYWORD_ONLY, got {fp[p].kind.name}"
        )
        assert np_[p].kind == inspect.Parameter.KEYWORD_ONLY, (
            f"nx.{name}.{p} should be KEYWORD_ONLY, got {np_[p].kind.name}"
        )


@needs_nx
def test_directed_edge_swap_rejects_positional_nswap():
    G = fnx.DiGraph()
    G.add_edges_from([(0, 1), (1, 2), (2, 3), (3, 0)])
    # nx rejects: directed_edge_swap(G, 1) — 'nswap' is keyword-only.
    with pytest.raises(TypeError):
        fnx.directed_edge_swap(G, 1)


@needs_nx
def test_subgraph_view_rejects_positional_filter():
    G = fnx.path_graph(4)
    # nx rejects: subgraph_view(G, callable) — 'filter_node' is keyword-only.
    with pytest.raises(TypeError):
        fnx.subgraph_view(G, lambda n: True)


@needs_nx
def test_dfs_edges_kwarg_form_works():
    """The kwarg form (which is the only valid one now) still works."""
    G = fnx.path_graph(5)
    edges = list(fnx.dfs_edges(G, source=0, sort_neighbors=sorted))
    assert edges == [(0, 1), (1, 2), (2, 3), (3, 4)]


@needs_nx
def test_random_spanning_tree_kwarg_form():
    G = fnx.complete_graph(5)
    T = fnx.random_spanning_tree(G, weight=None, seed=42)
    assert T.number_of_nodes() == 5
    assert T.number_of_edges() == 4


@needs_nx
def test_number_of_spanning_trees_kwarg_form():
    G = fnx.complete_graph(4)
    # K4 has 4^(4-2) = 16 spanning trees by Cayley's formula.
    n_fnx = fnx.number_of_spanning_trees(G)
    n_nx = nx.number_of_spanning_trees(nx.complete_graph(4))
    assert abs(n_fnx - n_nx) < 1e-9


@needs_nx
def test_subgraph_view_filter_node_kwarg_works():
    G = fnx.path_graph(5)
    H = fnx.subgraph_view(G, filter_node=lambda n: n != 2)
    assert 2 not in H.nodes()
    assert sorted(H.nodes()) == [0, 1, 3, 4]
