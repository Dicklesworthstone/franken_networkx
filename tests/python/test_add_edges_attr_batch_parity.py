"""br-r37-c1-pr8q6: attributed add_edges_from batch-path parity vs networkx.

The (u, v, dict) bulk path commits through ONE
``extend_edges_with_attrs_unrecorded`` call instead of per-edge
``add_edge``. These tests pin: insert-or-merge semantics, node/edge/adj
order, no source-dict aliasing, error/partial-prefix fallbacks, and
weighted-kernel exactness after a batched build.
"""

import random

import networkx as nx
import pytest

import franken_networkx as fnx


def _canon(g):
    return (
        [(n, dict(a)) for n, a in g.nodes(data=True)],
        [(u, v, dict(d)) for u, v, d in g.edges(data=True)],
        {n: list(g[n]) for n in g},
    )


def _canon_multidigraph(g):
    return (
        [(n, dict(a)) for n, a in g.nodes(data=True)],
        [(u, v, k, dict(d)) for u, v, k, d in g.edges(keys=True, data=True)],
        {n: list(g.successors(n)) for n in g},
        {n: list(g.predecessors(n)) for n in g},
    )


def _canon_multigraph(g):
    return (
        [(n, dict(a)) for n, a in g.nodes(data=True)],
        [(u, v, k, dict(d)) for u, v, k, d in g.edges(keys=True, data=True)],
        {n: list(g.adj[n]) for n in g},
    )


def _both(build):
    return _canon(build(nx)), _canon(build(fnx))


def test_random_attr_batches_match_nx():
    rnd = random.Random(20260605)
    for trial in range(30):
        n_edges = rnd.choice([0, 7, 8, 9, 30, 300])
        edges = []
        for _ in range(n_edges):
            u, v = rnd.randrange(50), rnd.randrange(50)
            r = rnd.random()
            if r < 0.3:
                edges.append((u, v))
            elif r < 0.6:
                edges.append((u, v, {"weight": rnd.random()}))
            else:
                edges.append(
                    (u, v, {"w": rnd.randrange(9), "c": "x", "b": bool(rnd.randrange(2))})
                )
        if edges:
            edges.append(edges[0])  # duplicate
        def build(mod, edges=edges):
            g = mod.Graph()
            g.add_edges_from(edges)
            return g
        a, b = _both(build)
        assert a == b, f"trial {trial}"


def test_merge_into_preexisting_edge():
    def build(mod):
        g = mod.Graph()
        g.add_edge(1, 2, weight=1, keep="x")
        g.add_edges_from(
            [(1, 2, {"weight": 7}), (2, 3, {"w": 1})] + [(i, i + 1) for i in range(3, 14)]
        )
        return g
    a, b = _both(build)
    assert a == b
    g = fnx.Graph()
    g.add_edge(1, 2, weight=1, keep="x")
    g.add_edges_from([(1, 2, {"weight": 7})] + [(i, i + 1) for i in range(3, 14)])
    assert g[1][2] == {"weight": 7, "keep": "x"}


def test_intra_batch_duplicate_merges_in_order():
    def build(mod):
        g = mod.Graph()
        g.add_edges_from(
            [(0, 1, {"a": 1})] + [(i, i + 1) for i in range(2, 12)] + [(1, 0, {"a": 2, "b": 3})]
        )
        return g
    a, b = _both(build)
    assert a == b
    g = build(fnx)
    assert g[0][1] == {"a": 2, "b": 3}  # last write wins


def test_graph_fresh_exact_int_attr_batch_matches_nx_order_and_copies():
    first = {"w": 0, "label": "first"}
    duplicate = {"w": 91, "extra": "last"}
    batch = (
        [(10, 2, first), (2, 2, {"self": True}), (2, 3, {"w": 1})]
        + [(i, i + 1, {"w": i, "tag": f"e{i}"}) for i in range(3, 12)]
        + [(2, 10, duplicate)]
    )

    gf = fnx.Graph()
    gn = nx.Graph()
    gf.add_edges_from(batch)
    gn.add_edges_from(batch)

    assert _canon(gf) == _canon(gn)
    assert gf.get_edge_data(10, 2) == {"w": 91, "label": "first", "extra": "last"}
    assert list(gf.adj[10]) == list(gn.adj[10])
    assert list(gf.adj[2]) == list(gn.adj[2])

    first["w"] = 999
    duplicate["extra"] = "mutated"
    assert gf.get_edge_data(10, 2) == {"w": 91, "label": "first", "extra": "last"}

    assert _canon(fnx.Graph(batch)) == _canon(nx.Graph(batch))


def test_graph_exact_int_attr_probe_falls_back_for_bool_nodes():
    batch = (
        [(True, 2, {"w": "bool"}), (1, 3, {"w": "int"})]
        + [(i, i + 10, {"w": i}) for i in range(2, 10)]
    )

    def build(mod):
        g = mod.Graph()
        g.add_edges_from(batch)
        return g

    a, b = _both(build)
    assert a == b


def test_source_dict_not_aliased():
    g = fnx.Graph()
    shared = {"w": 1}
    g.add_edges_from([(i, i + 1, shared) for i in range(15)])
    shared["w"] = 999
    assert all(g[i][i + 1]["w"] == 1 for i in range(15))
    g[0][1]["extra"] = 5
    assert "extra" not in g[1][2]


def test_global_attr_kwargs_still_merge():
    def build(mod):
        g = mod.Graph()
        g.add_edges_from([(i, i + 1, {"a": i}) for i in range(20)], weight=5)
        return g
    a, b = _both(build)
    assert a == b


@pytest.mark.parametrize(
    "tail",
    [
        [(1, 2, 3, 4)],  # bad arity
        [(2, None)],  # None endpoint
        [([1, 2], 3)],  # unhashable endpoint
        [(1, 2, 1.5)],  # br-r37-c1-a4zlp: non-dict third — nx keeps BOTH endpoint nodes
        [(1, 2, "ab")],  # br-r37-c1-a4zlp: bad iterable third (ValueError shape)
    ],
)
def test_partial_prefix_on_error_matches_nx(tail):
    def build(mod):
        g = mod.Graph()
        try:
            g.add_edges_from([(0, 1, {"w": 1})] * 10 + tail)
        except Exception:
            pass
        return g
    a, b = _both(build)
    assert a == b


def test_weighted_kernels_exact_after_batch():
    batch = [(i, (i * 7) % 40, {"weight": (i % 9) + 0.5}) for i in range(200)]
    gf, gn = fnx.Graph(), nx.Graph()
    gf.add_edges_from(batch)
    gn.add_edges_from(batch)
    assert dict(fnx.single_source_dijkstra_path_length(gf, 0)) == dict(
        nx.single_source_dijkstra_path_length(gn, 0)
    )
    assert sorted(d for _, d in gf.degree(weight="weight")) == sorted(
        d for _, d in gn.degree(weight="weight")
    )


def test_small_batches_below_gate_still_match():
    for k in (1, 2, 7):  # below ATTR_EDGE_BATCH_MIN
        def build(mod, k=k):
            g = mod.Graph()
            g.add_edges_from([(i, i + 1, {"w": i}) for i in range(k)])
            return g
        a, b = _both(build)
        assert a == b


def test_graph_fresh_exact_int_attr_batch_matches_nx_order_and_copies():
    first = {"w": 0, "label": "first"}
    duplicate = {"w": 91, "extra": "last"}
    batch = (
        [(0, 1, first), (2, 2, {"self": True}), (1, 2, {"w": 1})]
        + [(i, i + 1, {"w": i, "tag": f"e{i}"}) for i in range(3, 12)]
        + [(1, 0, duplicate)]
    )

    gf = fnx.Graph()
    gn = nx.Graph()
    gf.add_edges_from(batch)
    gn.add_edges_from(batch)

    assert _canon(gf) == _canon(gn)
    assert gf.get_edge_data(0, 1) == {"w": 91, "label": "first", "extra": "last"}
    assert list(gf[0]) == [1]
    assert list(gf[2]) == [2, 1]

    first["w"] = 999
    duplicate["extra"] = "mutated"
    assert gf.get_edge_data(0, 1) == {"w": 91, "label": "first", "extra": "last"}


def test_graph_exact_int_batch_probe_falls_back_for_bool_nodes():
    batch = (
        [(True, 2, {"w": "bool"}), (1, 3, {"w": "int"})]
        + [(i, i + 10, {"w": i}) for i in range(2, 10)]
    )

    def build(mod):
        g = mod.Graph()
        g.add_edges_from(batch)
        return g

    a, b = _both(build)
    assert a == b


def test_digraph_attr_batch_preserves_direction_and_mirrors():
    batch = (
        [(i, i + 1, {"w": i, "label": f"f{i}"}) for i in range(12)]
        + [(1, 0, {"w": 99, "rev": True}), (0, 1, {"extra": "last"})]
    )

    def build(mod):
        g = mod.DiGraph()
        g.add_edges_from(batch)
        return g

    a, b = _both(build)
    assert a == b

    g = build(fnx)
    assert g.get_edge_data(0, 1) == {"w": 0, "label": "f0", "extra": "last"}
    assert g.get_edge_data(1, 0) == {"w": 99, "rev": True}
    assert list(g.successors(0)) == [1]
    assert list(g.predecessors(0)) == [1]

    ctor = fnx.DiGraph(batch)
    assert _canon(ctor) == _canon(nx.DiGraph(batch))


def test_digraph_fresh_exact_int_attr_batch_matches_nx_order_and_copies():
    first = {"w": 0, "label": "first"}
    duplicate = {"w": 91, "extra": "last"}
    batch = (
        [(0, 1, first), (1, 2, {"w": 1}), (2, 2, {"self": True})]
        + [(i, i + 1, {"w": i, "tag": f"e{i}"}) for i in range(3, 12)]
        + [(0, 1, duplicate)]
    )

    gf = fnx.DiGraph()
    gn = nx.DiGraph()
    gf.add_edges_from(batch)
    gn.add_edges_from(batch)

    assert _canon(gf) == _canon(gn)
    assert gf.get_edge_data(0, 1) == {"w": 91, "label": "first", "extra": "last"}
    assert list(gf.successors(0)) == [1]
    assert list(gf.predecessors(1)) == [0]

    first["w"] = 999
    duplicate["extra"] = "mutated"
    assert gf.get_edge_data(0, 1) == {"w": 91, "label": "first", "extra": "last"}


def test_digraph_lazy_attr_mirrors_materialize_from_all_views():
    batch = (
        [(0, 1, {"weight": 1.5, "label": "first"}), (1, 2, {"weight": 2.5})]
        + [(i, i + 1, {"weight": float(i), "tag": f"e{i}"}) for i in range(2, 12)]
    )
    gf = fnx.DiGraph()
    gn = nx.DiGraph()
    gf.add_edges_from(batch)
    gn.add_edges_from(batch)

    assert list(gf.edges(data=True)) == list(gn.edges(data=True))
    assert list(gf.edges(data="weight", default=None)) == list(
        gn.edges(data="weight", default=None)
    )
    assert list(gf.succ[0].items()) == list(gn.succ[0].items())
    assert gf.succ[0].copy() == gn.succ[0].copy()

    edge_dict = gf[0][1]
    edge_view_dict = next(data for u, v, data in gf.edges(data=True) if (u, v) == (0, 1))
    assert edge_view_dict is edge_dict
    edge_view_dict["weight"] = 7.5
    edge_view_dict["extra"] = "live"
    assert gf[0][1] == {"weight": 7.5, "label": "first", "extra": "live"}

    gn[0][1]["weight"] = 7.5
    gn[0][1]["extra"] = "live"
    assert dict(fnx.single_source_dijkstra_path_length(gf, 0)) == dict(
        nx.single_source_dijkstra_path_length(gn, 0)
    )


def test_digraph_exact_int_batch_probe_falls_back_for_bool_nodes():
    batch = (
        [(True, 2, {"w": "bool"}), (1, 3, {"w": "int"})]
        + [(i, i + 10, {"w": i}) for i in range(2, 10)]
    )

    def build(mod):
        g = mod.DiGraph()
        g.add_edges_from(batch)
        return g

    a, b = _both(build)
    assert a == b


def test_multigraph_fresh_exact_int_attr_batch_matches_nx_order_keys_and_copies():
    first = {"w": 0, "label": "first"}
    duplicate = {"w": 91, "extra": "second-key"}
    third = {"w": 92, "tail": "third-key"}
    batch = (
        [(10, 2, first), (2, 3, {"w": 1}), (2, 10, duplicate), (10, 10, {"self": True})]
        + [(i, i + 1, {"w": i, "tag": f"e{i}"}) for i in range(3, 11)]
        + [(10, 2, third)]
    )

    gf = fnx.MultiGraph()
    gn = nx.MultiGraph()
    gf.add_edges_from(batch)
    gn.add_edges_from(batch)

    assert _canon_multigraph(gf) == _canon_multigraph(gn)
    assert gf.get_edge_data(10, 2) == {
        0: {"w": 0, "label": "first"},
        1: {"w": 91, "extra": "second-key"},
        2: {"w": 92, "tail": "third-key"},
    }
    assert list(gf.adj[10]) == list(gn.adj[10])
    assert list(gf.adj[2]) == list(gn.adj[2])

    first["w"] = 999
    duplicate["extra"] = "mutated"
    third["tail"] = "mutated"
    assert gf.get_edge_data(10, 2) == {
        0: {"w": 0, "label": "first"},
        1: {"w": 91, "extra": "second-key"},
        2: {"w": 92, "tail": "third-key"},
    }


def test_multigraph_exact_int_attr_probe_falls_back_for_bool_nodes():
    batch = (
        [(True, 2, {"w": "bool"}), (1, 3, {"w": "int"})]
        + [(i, i + 10, {"w": i}) for i in range(2, 10)]
    )

    def build(mod):
        g = mod.MultiGraph()
        g.add_edges_from(batch)
        return g

    assert _canon_multigraph(build(fnx)) == _canon_multigraph(build(nx))


def test_multidigraph_fresh_exact_int_attr_batch_matches_nx_order_keys_and_copies():
    first = {"w": 0, "label": "first"}
    duplicate = {"w": 91, "extra": "second-key"}
    third = {"w": 92, "tail": "third-key"}
    batch = (
        [(0, 1, first), (1, 2, {"w": 1}), (0, 1, duplicate), (1, 0, {"rev": True})]
        + [(i, i + 1, {"w": i, "tag": f"e{i}"}) for i in range(3, 11)]
        + [(2, 2, {"self": True}), (0, 1, third)]
    )

    gf = fnx.MultiDiGraph()
    gn = nx.MultiDiGraph()
    gf.add_edges_from(batch)
    gn.add_edges_from(batch)

    assert _canon_multidigraph(gf) == _canon_multidigraph(gn)
    assert gf.get_edge_data(0, 1) == {
        0: {"w": 0, "label": "first"},
        1: {"w": 91, "extra": "second-key"},
        2: {"w": 92, "tail": "third-key"},
    }
    assert list(gf.successors(0)) == [1]
    assert list(gf.predecessors(1)) == [0]

    first["w"] = 999
    duplicate["extra"] = "mutated"
    third["tail"] = "mutated"
    assert gf.get_edge_data(0, 1) == {
        0: {"w": 0, "label": "first"},
        1: {"w": 91, "extra": "second-key"},
        2: {"w": 92, "tail": "third-key"},
    }


def test_multidigraph_keyed_data_view_preserves_live_attrs_for_mirrored_and_plain_edges():
    attr_batch = [(0, 1, {"weight": 1.5}), (0, 1, {"weight": 2.5, "label": "parallel"})]
    gf = fnx.MultiDiGraph()
    gn = nx.MultiDiGraph()
    gf.add_edges_from(attr_batch)
    gn.add_edges_from(attr_batch)

    assert list(gf.edges(keys=True, data=True)) == list(gn.edges(keys=True, data=True))
    edge_dict = next(
        data for u, v, key, data in gf.edges(keys=True, data=True) if (u, v, key) == (0, 1, 0)
    )
    edge_dict["weight"] = 7.5
    gn[0][1][0]["weight"] = 7.5
    assert gf[0][1][0] is edge_dict
    assert dict(gf.out_degree(weight="weight")) == dict(gn.out_degree(weight="weight"))

    plain = fnx.MultiDiGraph()
    plain.add_edge(1, 2)
    _u, _v, _key, attrs = list(plain.edges(keys=True, data=True))[0]
    attrs["weight"] = 3.0
    assert plain[1][2][0]["weight"] == 3.0
    assert list(plain.edges(keys=True, data="weight", default=None)) == [(1, 2, 0, 3.0)]


def test_multidigraph_exact_int_weight_float_batch_matches_nx_and_copies():
    attrs = [{"weight": float(i) + 0.25} for i in range(16)]
    batch = [(i % 5, (i * 7 + 1) % 9, attrs[i]) for i in range(16)]

    gf = fnx.MultiDiGraph()
    gn = nx.MultiDiGraph()
    gf.add_edges_from(batch)
    gn.add_edges_from(batch)

    assert _canon_multidigraph(gf) == _canon_multidigraph(gn)
    attrs[0]["weight"] = 999.0
    assert gf.get_edge_data(0, 1)[0] == {"weight": 0.25}
    assert _canon_multidigraph(gf) == _canon_multidigraph(gn)


def test_multidigraph_exact_int_batch_probe_falls_back_for_bool_nodes():
    batch = (
        [(True, 2, {"w": "bool"}), (1, 3, {"w": "int"})]
        + [(i, i + 10, {"w": i}) for i in range(2, 10)]
    )

    def build(mod):
        g = mod.MultiDiGraph()
        g.add_edges_from(batch)
        return g

    gf = build(fnx)
    gn = build(nx)
    assert _canon_multidigraph(gf) == _canon_multidigraph(gn)


def test_digraph_batch_probe_falls_back_for_list_edges():
    batch = [[i, i + 1, {"w": i}] for i in range(12)]

    def build(mod):
        g = mod.DiGraph()
        g.add_edges_from(batch)
        return g

    a, b = _both(build)
    assert a == b


def test_digraph_batch_probe_preserves_partial_error_prefix():
    tail_cases = [
        [(1, 2, 3, 4)],
        [(2, None)],
        [([1, 2], 3)],
    ]

    for tail in tail_cases:
        def build(mod, tail=tail):
            g = mod.DiGraph()
            try:
                g.add_edges_from([(0, 1, {"w": 1})] * 10 + tail)
            except Exception:
                pass
            return g

        a, b = _both(build)
        assert a == b


# Plain exact-int pairs onto a FRESH DiGraph are collected by index. Node,
# successor, predecessor and edge order must be networkx's, a repeated pair adds
# nothing, and every shape outside exact ints goes to the general path with
# networkx's outcome.

def _canon_digraph_plain(g):
    return (
        [repr(n) for n in g.nodes],
        [(repr(u), repr(v)) for u, v in g.edges],
        {repr(n): [repr(m) for m in g.succ[n]] for n in g},
        {repr(n): [repr(m) for m in g.pred[n]] for n in g},
        [(repr(n), dict(d)) for n, d in g.nodes(data=True)],
    )


@pytest.mark.parametrize("how", ["add_edges_from", "constructor", "tuple"])
@pytest.mark.parametrize("seed", range(10))
def test_digraph_plain_int_batch_matches_networkx(seed, how):
    rng = random.Random(seed)
    # Small id range: repeated pairs, reversed pairs and self-loops occur.
    edges = [(rng.randrange(20), rng.randrange(20)) for _ in range(rng.randrange(8, 160))]

    def build(mod):
        if how == "constructor":
            return mod.DiGraph(edges)
        g = mod.DiGraph()
        g.add_edges_from(tuple(edges) if how == "tuple" else edges)
        return g

    fnx_graph = build(fnx)
    nx_graph = build(nx)
    assert _canon_digraph_plain(fnx_graph) == _canon_digraph_plain(nx_graph)
    # The batch-built graph keeps working as a graph: a later edit and a read.
    for g in (fnx_graph, nx_graph):
        g.add_edge(0, 99, weight=3)
        g.remove_edge(*edges[0]) if g.has_edge(*edges[0]) else None
    assert _canon_digraph_plain(fnx_graph) == _canon_digraph_plain(nx_graph)
    assert sorted(fnx_graph.in_degree()) == sorted(nx_graph.in_degree())


_PLAIN_BATCH_DECLINES = {
    "bool_node": [(True, 1)] + [(i, i + 1) for i in range(10)],
    "big_int": [(2**70, 1)] + [(i, i + 1) for i in range(10)],
    "str_node": [("a", 1)] + [(i, i + 1) for i in range(10)],
    "float_node": [(1.0, 2)] + [(i, i + 1) for i in range(10)],
    "attr_pair": [(0, 1, {"w": 1})] + [(i, i + 1) for i in range(10)],
    "long_tuple": [(i, i + 1) for i in range(10)] + [(0, 1, 2, 3)],
    "none_node": [(i, i + 1) for i in range(10)] + [(None, 1)],
}


@pytest.mark.parametrize("shape", sorted(_PLAIN_BATCH_DECLINES))
def test_digraph_plain_batch_other_shapes_match_networkx(shape):
    edges = _PLAIN_BATCH_DECLINES[shape]

    def outcome(mod):
        g = mod.DiGraph()
        try:
            g.add_edges_from(edges)
        except Exception as exc:  # noqa: BLE001 - the error IS the parity subject
            return type(exc).__name__, str(exc), _canon_digraph_plain(g)
        return _canon_digraph_plain(g)

    assert outcome(fnx) == outcome(nx)


def _canon_full(g):
    state = [
        [(repr(n), type(n).__name__) for n in g.nodes],
        repr(list(g.edges(data=True))),
        {repr(n): [repr(m) for m in g.adj[n]] for n in g},
    ]
    if g.is_directed():
        state.append({repr(n): [repr(m) for m in g.pred[n]] for n in g})
    return state


# br-r37-c1-ey5n2: plain pairs appended to a graph that already has nodes and
# edges - the Graph batch without the Python pass over existing edges, and the
# DiGraph exact-int append collector.
_APPEND_EXTRA_NODES = {
    "ints only": [],
    "a float node": [3.0],
    "str nodes": ["5", "x"],
    "bool nodes": [True, False],
}


@pytest.mark.parametrize("cls", ["Graph", "DiGraph"])
@pytest.mark.parametrize("extra", sorted(_APPEND_EXTRA_NODES))
@pytest.mark.parametrize("seed", range(6))
def test_plain_pairs_appended_to_a_populated_graph_match_networkx(cls, extra, seed):
    rng = random.Random(seed)
    n = rng.randint(4, 30)
    base = [
        (rng.randrange(n), rng.randrange(n), {"w": rng.randint(1, 9)} if rng.random() < 0.5 else {})
        for _ in range(rng.randint(1, 3 * n))
    ]
    removed = [rng.randrange(n) for _ in range(2)] if seed % 2 else []
    bunch = [
        (rng.randrange(n + 12) + (10**6 if rng.random() < 0.1 else 0), rng.randrange(n + 12))
        for _ in range(rng.randint(8, 5 * n))
    ] + [(u, v) for u, v, _ in base[:4]] + [(v, u) for u, v, _ in base[:2]]

    def outcome(lib):
        g = getattr(lib, cls)()
        g.add_edges_from(base)
        g.add_nodes_from(_APPEND_EXTRA_NODES[extra])
        for node in removed:
            if node in g:
                g.remove_node(node)
        g.add_edges_from(bunch if seed % 3 else tuple(bunch))
        before_edit = _canon_full(g)
        g.add_edge(0, 999)
        g.remove_edge(0, 999)
        return before_edit, _canon_full(g)

    assert outcome(fnx) == outcome(nx)


@pytest.mark.parametrize("cls", ["Graph", "DiGraph"])
def test_re_added_pairs_keep_their_edge_attributes(cls):
    """Without attrs, networkx's add_edge of an existing edge changes nothing:
    the edge keeps its dict, its data and its place in the row."""
    base = [(i, (i + 1) % 12, {"w": i, "tag": f"e{i}"}) for i in range(12)]
    bunch = [(i, (i + 1) % 12) for i in range(12)] + [((i + 1) % 12, i) for i in range(12)]

    def outcome(lib):
        g = getattr(lib, cls)(base)
        # Held through get_edge_data, not g[3][4]: reading a row leaves a live
        # row mirror, and a graph with one declines the native batches.
        held = g.get_edge_data(3, 4)
        g.add_edges_from(bunch)
        return _canon_full(g), held is g.get_edge_data(3, 4)

    assert outcome(fnx) == outcome(nx)


@pytest.mark.parametrize("cls", ["Graph", "DiGraph"])
@pytest.mark.parametrize("seed", range(8))
def test_rows_read_before_an_append_show_its_edges(cls, seed):
    """br-r37-c1-dnqsr: a row read (dict(G[u]), G.pred[v], neighbors) leaves a
    live row mirror; the batch now runs anyway and must write the new edges
    into every live row, in networkx's order, with each cell the edge's own
    dict."""
    rng = random.Random(seed)
    n = rng.randint(4, 25)
    base = [(rng.randrange(n), rng.randrange(n)) for _ in range(rng.randint(1, 3 * n))]
    readers = rng.sample(range(n), min(n, 3))
    bunch = [(rng.randrange(n + 6), rng.randrange(n + 6)) for _ in range(rng.randint(8, 4 * n))]
    bunch += [(r, n + 1) for r in readers] + [(n + 2, r) for r in readers] + [(readers[0], readers[0])]
    bunch += [(v, u) for u, v in base[:3]]

    def outcome(lib):
        g = getattr(lib, cls)(base)
        g.add_nodes_from(range(n))
        held = []
        for r in readers:
            held.append(g[r])
            dict(g[r])
            if g.is_directed():
                held.append(g.pred[r])
                dict(g.pred[r])
            list(g.neighbors(r))
        g.add_edges_from(bunch)
        rows = [list(row.items()) for row in held]
        own = all(row[x] is g.get_edge_data(r, x) for r, row in zip(readers, held[:: 2 if g.is_directed() else 1]) for x in row)
        return _canon_full(g), repr(rows), [list(g.neighbors(r)) for r in readers], own

    assert outcome(fnx) == outcome(nx)


@pytest.mark.parametrize("seed", range(8))
def test_transitive_closure_dag_matches_networkx(seed):
    """Its closure edges are appended to a copy in one add_edges_from, after a
    successor snapshot that must not leave row mirrors behind."""
    rng = random.Random(seed)
    n = rng.randint(2, 80)
    edges = [
        (u, v, {"w": rng.random()})
        for u in range(n)
        for v in rng.sample(range(u + 1, n + 1), min(rng.randint(0, 4), n - u))
    ]
    got = fnx.transitive_closure_dag(fnx.DiGraph(edges))
    want = nx.transitive_closure_dag(nx.DiGraph(edges))
    assert _canon_full(got) == _canon_full(want)
