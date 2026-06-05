"""Node-key canonicalization parity across key types.

br-ctaxkey: `node_key_to_string` now detects string keys with a cheap
`downcast::<PyString>()` (no PyErr built for non-strings) instead of
`extract::<String>()`. The produced canonical key must stay byte-identical, so
node identity, hash-equal collapsing (1 / 1.0 / True, 0 / False), distinctness
of int vs str, large ints, negatives, floats, and tuple keys all match nx.
"""

import networkx as nx

import franken_networkx as fnx


def _probe(lib):
    G = lib.Graph()
    # hash-equal keys collapse to one node (Python dict semantics)
    G.add_node(1)
    G.add_node(1.0)
    G.add_node(True)
    G.add_node(0)
    G.add_node(False)
    # distinct / exotic keys
    G.add_node("1")
    G.add_node(10**30)
    G.add_node(-5)
    G.add_node(3.5)
    G.add_node((1, 2))
    G.add_edge("a", "b", w=1)
    G.add_edge(1, 2)
    G.add_edge(True, 5)
    return {
        "n_nodes": G.number_of_nodes(),
        "nodes": sorted(repr(n) for n in G.nodes()),
        "1_in": 1 in G,
        "1.0_in": 1.0 in G,
        "True_in": True in G,
        "str1_in": "1" in G,
        "0_eq_False": (0 in G) and (False in G),
        "edges": sorted((repr(u), repr(v)) for u, v in G.edges()),
        "neighbors_1": sorted(repr(x) for x in G[1]),
        "huge_in": 10**30 in G,
        "tuple_in": (1, 2) in G,
    }


def test_node_key_type_parity():
    assert _probe(fnx) == _probe(nx)


def test_int_float_bool_collapse_to_one_node():
    Gf = fnx.Graph()
    Gf.add_nodes_from([1, 1.0, True])
    assert Gf.number_of_nodes() == 1
    assert 1 in Gf and 1.0 in Gf and True in Gf


def test_int_and_str_are_distinct():
    Gf = fnx.Graph()
    Gf.add_node(5)
    Gf.add_node("5")
    assert Gf.number_of_nodes() == 2


def test_string_subclass_key():
    class S(str):
        pass

    Gx = nx.Graph()
    Gf = fnx.Graph()
    Gx.add_node(S("hi"))
    Gx.add_node("hi")
    Gf.add_node(S("hi"))
    Gf.add_node("hi")
    # str subclass with equal value collapses with the plain str (one node)
    assert Gf.number_of_nodes() == Gx.number_of_nodes() == 1
    assert "hi" in Gf


def test_membership_lookup_parity_large_graph():
    edges = [(i, i + 1) for i in range(500)]
    Gx = nx.Graph(edges)
    Gf = fnx.Graph(edges)
    for k in [0, 250, 499, 500, "0", 1.0, True, -1, 10**40]:
        assert (k in Gx) == (k in Gf), k


def test_range_fast_path_preserves_display_key_parity():
    Gx = nx.Graph()
    Gf = fnx.Graph()
    Gx.add_nodes_from(range(20))
    Gf.add_nodes_from(range(20))

    # Re-adding hash-equal numeric keys must preserve the first object that
    # entered the node dict: the int from range(...), not float/bool aliases.
    for graph in (Gx, Gf):
        graph.add_node(0.0)
        graph.add_node(True)
        graph.nodes[3]["color"] = "red"
        graph.add_node(3.0, weight=7)

    assert list(Gf.nodes()) == list(Gx.nodes())
    assert list(Gf.nodes(data=True)) == list(Gx.nodes(data=True))

    Hx = nx.Graph()
    Hf = fnx.Graph()
    Hx.add_nodes_from(range(5))
    Hf.add_nodes_from(range(5))
    Hx.remove_node(0)
    Hf.remove_node(0)
    Hx.add_node(0.0)
    Hf.add_node(0.0)
    assert list(Hf.nodes()) == list(Hx.nodes())


def test_range_fast_path_materializes_int_keys_for_native_algorithms():
    Gx = nx.Graph()
    Gf = fnx.Graph()
    for graph in (Gx, Gf):
        graph.add_nodes_from(range(12))
        graph.add_edges_from((i, i + 1) for i in range(11))

    assert list(Gf.nodes()) == list(Gx.nodes())
    assert [type(node) for node in Gf.nodes()] == [type(node) for node in Gx.nodes()]
    assert list(Gf.neighbors(0)) == list(Gx.neighbors(0))
    assert list(Gf[0]) == list(Gx[0])
    assert fnx.triangles(Gf, 0) == nx.triangles(Gx, 0)
    assert fnx.triangles(Gf) == nx.triangles(Gx)
    assert fnx.clustering(Gf, 0) == nx.clustering(Gx, 0)
    assert dict(fnx.all_pairs_shortest_path_length(Gf)) == dict(
        nx.all_pairs_shortest_path_length(Gx)
    )
