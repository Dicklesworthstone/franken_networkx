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


# br-r37-c1-oe93x: the read paths (`has_node`, `n in G`, `has_edge`) build the
# canonical key in a 128-byte STACK buffer instead of allocating a String, and
# fall back to the owned path when it does not fit. The canonical form is
# "str:{len}:{s}" with `len` in BYTES, so these probes pin the two ways the
# borrowed writer can diverge from the owned one: a length near the buffer edge
# (truncate/overflow) and a multi-byte key (byte length vs character count).
_STACK_BUF = 128

# "str:" + decimal length + ":" is 5-8 bytes of prefix, so keys in this range
# straddle the stack/heap boundary from both sides.
_BOUNDARY_KEYS = [
    "b" * n for n in range(_STACK_BUF - 12, _STACK_BUF + 3)
]

_MULTIBYTE_KEYS = [
    "ünïcödé",  # 2-byte code points: 7 chars, 11 bytes
    "日本語のノード",  # 3-byte code points: 7 chars, 21 bytes
    "emoji-🎯-key",  # a 4-byte code point
    "é" * 60,  # 60 chars, 120 bytes — fits by chars, NOT by bytes
]


def test_borrowed_read_path_finds_every_key_the_write_path_stored():
    """Round-trip every key kind through add_node -> has_node / `in`."""
    keys = _BOUNDARY_KEYS + _MULTIBYTE_KEYS + ["", "a", "str:5:weird", "x" * 4096]
    Gx = nx.Graph()
    Gf = fnx.Graph()
    for graph in (Gx, Gf):
        graph.add_nodes_from(keys)

    assert Gf.number_of_nodes() == Gx.number_of_nodes() == len(set(keys))
    for key in keys:
        # A borrowed canonical built from the character count instead of the
        # byte length misses on every multi-byte key: this is the negative case.
        assert Gf.has_node(key) is Gx.has_node(key) is True, key
        assert (key in Gf) == (key in Gx) is True, key
        assert Gf.has_node(key + "!") is Gx.has_node(key + "!") is False, key


def test_borrowed_read_path_keeps_prefix_keys_distinct():
    """A truncated canonical would alias a key with its own prefix."""
    long_key = "z" * (_STACK_BUF + 40)
    prefix = long_key[:_STACK_BUF]
    Gx = nx.Graph()
    Gf = fnx.Graph()
    for graph in (Gx, Gf):
        graph.add_node(long_key)

    assert Gf.has_node(long_key) is Gx.has_node(long_key) is True
    assert Gf.has_node(prefix) is Gx.has_node(prefix) is False
    assert (prefix in Gf) == (prefix in Gx) is False


def test_borrowed_read_path_has_edge_parity_across_classes():
    pairs = [
        (_BOUNDARY_KEYS[0], _BOUNDARY_KEYS[-1]),
        ("ünïcödé", "日本語のノード"),
        ("é" * 60, "emoji-🎯-key"),
        ("a", "x" * 4096),
    ]
    for nx_cls, fnx_cls in (
        (nx.Graph, fnx.Graph),
        (nx.DiGraph, fnx.DiGraph),
        (nx.MultiGraph, fnx.MultiGraph),
        (nx.MultiDiGraph, fnx.MultiDiGraph),
    ):
        Gx, Gf = nx_cls(), fnx_cls()
        for graph in (Gx, Gf):
            graph.add_edges_from(pairs)

        for u, v in pairs:
            assert Gf.has_edge(u, v) is Gx.has_edge(u, v) is True, (fnx_cls, u, v)
            # reversed: True only for the undirected classes
            assert Gf.has_edge(v, u) is Gx.has_edge(v, u), (fnx_cls, v, u)
            assert Gf.has_edge(u, v + "!") is Gx.has_edge(u, v + "!") is False


# br-r37-c1-dr1h9: Python ints are arbitrary precision. Keys wider than i64 used
# to round through `extract::<f64>()` and then saturate onto `i64::MAX`, so every
# key in that window shared one canonical and distinct nodes silently MERGED.
_WIDE_INT_KEYS = [
    2**63 - 1,  # i64::MAX — the key the saturated ones aliased onto
    2**63,
    2**63 + 1,
    2**63 + 7,
    2**63 + 8,
    2**64,
    2**64 + 1,
    10**30,
    -(2**63),  # i64::MIN
    -(2**63) - 1,
    -(2**64),
]


def test_wide_int_node_keys_do_not_merge():
    Gx = nx.Graph()
    Gf = fnx.Graph()
    for graph in (Gx, Gf):
        graph.add_nodes_from(_WIDE_INT_KEYS)

    assert Gf.number_of_nodes() == Gx.number_of_nodes() == len(_WIDE_INT_KEYS)
    assert sorted(Gf.nodes()) == sorted(Gx.nodes())
    for key in _WIDE_INT_KEYS:
        assert Gf.has_node(key) is Gx.has_node(key) is True, key
        assert (key in Gf) == (key in Gx) is True, key


def test_wide_int_edge_endpoints_survive_every_add_path():
    big = 2**63 + 7
    # add_edge, a sub-threshold add_edges_from (below the native batch minimum),
    # and add_nodes_from all route through the same canonicalization.
    for build in (
        lambda G: G.add_edge(big, big + 1),
        lambda G: G.add_edges_from([(big, big + 1)]),
        lambda G: (G.add_nodes_from([big, big + 1]), G.add_edge(big, big + 1)),
    ):
        Gx, Gf = nx.Graph(), fnx.Graph()
        for graph in (Gx, Gf):
            build(graph)
        assert sorted(Gf.nodes()) == sorted(Gx.nodes()) == [big, big + 1]
        assert Gf.number_of_edges() == Gx.number_of_edges() == 1
        assert Gf.degree(big) == Gx.degree(big) == 1


def test_wide_int_multigraph_edge_keys_do_not_merge():
    big = 2**63 + 7
    for nx_cls, fnx_cls in ((nx.MultiGraph, fnx.MultiGraph), (nx.MultiDiGraph, fnx.MultiDiGraph)):
        Gx, Gf = nx_cls(), fnx_cls()
        for graph in (Gx, Gf):
            graph.add_edge("a", "b", key=big)
            graph.add_edge("a", "b", key=big + 1)
        assert sorted(Gf["a"]["b"]) == sorted(Gx["a"]["b"]) == [big, big + 1]
        assert Gf.number_of_edges() == Gx.number_of_edges() == 2
        assert Gf.has_edge("a", "b", key=big) is Gx.has_edge("a", "b", key=big) is True


def test_wide_int_fix_preserves_hash_equal_collapse():
    """The negative case: routing every int through repr breaks bool/int/float.

    ``repr(True)`` is ``"True"``, not ``"1"``, so a fix that canonicalized ints
    by repr unconditionally would split ``1`` / ``1.0`` / ``True`` into three
    nodes where Python's dict semantics (and nx) give one.
    """
    Gx, Gf = nx.Graph(), fnx.Graph()
    for graph in (Gx, Gf):
        graph.add_nodes_from([1, 1.0, True, 0, False, 0.0, -1, -1.0])

    assert Gf.number_of_nodes() == Gx.number_of_nodes() == 3
    assert sorted(Gf.nodes(), key=repr) == sorted(Gx.nodes(), key=repr)


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
