"""Parity for ``join_trees`` signature + behaviour.

The previous fnx ``join_trees(T1, T2, root1, root2)`` is incompatible
with networkx's modern public signature
``join_trees(rooted_trees, *, label_attribute=None, first_label=0)``.
nx accepts a list of (tree, root) pairs and joins them under a new
synthetic root, relabelling all nodes to consecutive integers starting
at ``first_label + 1``. Drop-in callers writing for nx hit ``TypeError``
on the previous fnx surface.

Aligned: ``join_trees`` now matches nx's signature and produces the
same edge set when called with the same inputs.
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


@needs_nx
def test_signature_matches_networkx():
    fnx_sig = inspect.signature(fnx.join_trees)
    nx_sig = inspect.signature(nx.join_trees)
    fnx_params = list(fnx_sig.parameters.keys())
    nx_params = [k for k in nx_sig.parameters.keys()
                 if k not in ("backend", "backend_kwargs")]
    assert fnx_params == nx_params

    for name in ("label_attribute", "first_label"):
        assert (
            fnx_sig.parameters[name].kind == inspect.Parameter.KEYWORD_ONLY
        ), f"{name} should be KEYWORD_ONLY"


@needs_nx
def test_join_two_balanced_trees_is_balanced_tree_of_height_plus_one():
    """nx docstring example: joining two balanced binary trees of
    height h gives a balanced binary tree of height h+1."""
    h = 4
    left = fnx.balanced_tree(2, h)
    right = fnx.balanced_tree(2, h)
    joined = fnx.join_trees([(left, 0), (right, 0)])
    expected = nx.balanced_tree(2, h + 1)
    assert nx.is_isomorphic(joined, expected)


@needs_nx
def test_edges_match_networkx_exactly():
    """Same inputs produce the same edge set since the relabel is
    deterministic."""
    left_f = fnx.balanced_tree(2, 3)
    right_f = fnx.balanced_tree(2, 3)
    left_n = nx.balanced_tree(2, 3)
    right_n = nx.balanced_tree(2, 3)

    joined_f = fnx.join_trees([(left_f, 0), (right_f, 0)])
    joined_n = nx.join_trees([(left_n, 0), (right_n, 0)])
    assert sorted(joined_f.edges()) == sorted(joined_n.edges())


@needs_nx
def test_label_attribute_preserves_original_labels():
    fnx_in = fnx.path_graph(3)
    nx_in = nx.path_graph(3)
    joined_f = fnx.join_trees([(fnx_in, 0)], label_attribute="orig")
    joined_n = nx.join_trees([(nx_in, 0)], label_attribute="orig")
    fnx_attrs = {n: dict(joined_f.nodes[n]) for n in joined_f.nodes()}
    nx_attrs = {n: dict(joined_n.nodes[n]) for n in joined_n.nodes()}
    assert fnx_attrs == nx_attrs


@needs_nx
def test_first_label_offsets_node_ids():
    joined_f = fnx.join_trees(
        [(fnx.path_graph(3), 0), (fnx.path_graph(2), 0)], first_label=10
    )
    joined_n = nx.join_trees(
        [(nx.path_graph(3), 0), (nx.path_graph(2), 0)], first_label=10
    )
    assert sorted(joined_f.nodes()) == sorted(joined_n.nodes())
    # Root label is first_label
    assert 10 in joined_f.nodes()


@needs_nx
def test_empty_rooted_trees_returns_single_node_graph():
    joined_f = fnx.join_trees([])
    joined_n = nx.join_trees([])
    assert joined_f.number_of_nodes() == joined_n.number_of_nodes() == 1


@needs_nx
def test_old_two_arg_call_form_no_longer_accepted():
    """The previous fnx API ``join_trees(T1, T2, root1=0, root2=0)`` is
    now rejected in favour of nx's list-of-pairs form."""
    T = fnx.path_graph(3)
    with pytest.raises((TypeError, AttributeError)):
        # Passing a second graph as positional #2 — nx interprets it
        # as ``label_attribute`` (kwarg-only) so this raises.
        fnx.join_trees(T, T)
