"""Parity for MultiGraph construction from 3-level dict-of-dicts input.

Regression for br-r37-c1-13tp1: ``MultiGraph`` built from a *symmetric*
3-level dict-of-dicts (``{u: {v: attrs}, ...}`` with both ``u->v`` and
``v->u`` present) double-counted every edge (auto keys 0 and 1) instead
of folding the symmetric adjacency into a single ``(u, v, 0)`` edge the
way ``nx.from_dict_of_dicts`` does for undirected multigraphs.

These tests pin fnx to nx across the matrix of shapes that share the
``_decode_dict_of_dicts_into`` code path so the dedup fix cannot silently
regress the directed / 4-level / simple-graph / dict-of-list branches.
"""

import networkx as nx

import franken_networkx as fnx


def _edge_multiset(g):
    if g.is_multigraph():
        return sorted(
            (u, v, k, tuple(sorted(d.items())))
            for u, v, k, d in g.edges(keys=True, data=True)
        )
    return sorted(
        (u, v, tuple(sorted(d.items()))) for u, v, d in g.edges(data=True)
    )


def _assert_parity(dod, nx_cls, fnx_cls, *, multigraph_input=None):
    if multigraph_input is None:
        gx = nx_cls(dod)
        gf = fnx_cls(dod)
    else:
        gx = nx.from_dict_of_dicts(
            dod, create_using=nx_cls(), multigraph_input=multigraph_input
        )
        gf = fnx.from_dict_of_dicts(
            dod, create_using=fnx_cls(), multigraph_input=multigraph_input
        )
    assert gf.number_of_edges() == gx.number_of_edges()
    assert sorted(gf.nodes()) == sorted(gx.nodes())
    assert _edge_multiset(gf) == _edge_multiset(gx)


def test_symmetric_three_level_undirected_multigraph_dedup():
    # The original defect: symmetric 3-level dict produced two edges.
    dod = {1: {2: {"weight": 5}}, 2: {1: {"weight": 5}}, 3: {}}
    _assert_parity(dod, nx.MultiGraph, fnx.MultiGraph)


def test_symmetric_three_level_dense_undirected_multigraph():
    import random

    rnd = random.Random(42)
    n = 40
    dod = {i: {} for i in range(n)}
    for i in range(n):
        for j in range(i + 1, n):
            if rnd.random() < 0.3:
                w = rnd.randint(1, 100)
                dod[i][j] = {"weight": w}
                dod[j][i] = {"weight": w}
    _assert_parity(dod, nx.MultiGraph, fnx.MultiGraph)


def test_asymmetric_three_level_undirected_multigraph():
    dod = {1: {2: {"weight": 5}}, 2: {}, 3: {1: {"a": 1}}}
    _assert_parity(dod, nx.MultiGraph, fnx.MultiGraph)


def test_self_loop_three_level_undirected_multigraph():
    dod = {1: {1: {"weight": 9}, 2: {"weight": 3}}, 2: {1: {"weight": 3}}}
    _assert_parity(dod, nx.MultiGraph, fnx.MultiGraph)


def test_directed_multigraph_three_level_no_dedup():
    # Directed multigraphs keep both directions (no dedup).
    dod = {1: {2: {"weight": 5}}, 2: {1: {"weight": 6}}}
    _assert_parity(dod, nx.MultiDiGraph, fnx.MultiDiGraph)


def test_four_level_multigraph_input_autodetect():
    dod = {
        1: {2: {0: {"weight": 5}, 1: {"weight": 7}}},
        2: {1: {0: {"weight": 5}, 1: {"weight": 7}}},
    }
    _assert_parity(dod, nx.MultiGraph, fnx.MultiGraph)


def test_four_level_multigraph_input_explicit():
    dod = {1: {2: {0: {"weight": 5}}}, 2: {1: {0: {"weight": 5}}}}
    _assert_parity(dod, nx.MultiGraph, fnx.MultiGraph, multigraph_input=True)


def test_three_level_multigraph_input_explicit_false():
    dod = {1: {2: {"weight": 5}}, 2: {1: {"weight": 5}}}
    _assert_parity(dod, nx.MultiGraph, fnx.MultiGraph, multigraph_input=False)


def test_simple_graph_symmetric_three_level():
    dod = {1: {2: {"weight": 5}}, 2: {1: {"weight": 5}}}
    _assert_parity(dod, nx.Graph, fnx.Graph)


def test_empty_inner_undirected_multigraph():
    dod = {1: {2: {}}, 2: {1: {}}}
    _assert_parity(dod, nx.MultiGraph, fnx.MultiGraph)


def test_dict_of_list_undirected_multigraph_still_dedups():
    dod = {1: [2, 3], 2: [1, 3], 3: [1, 2]}
    _assert_parity(dod, nx.MultiGraph, fnx.MultiGraph)
