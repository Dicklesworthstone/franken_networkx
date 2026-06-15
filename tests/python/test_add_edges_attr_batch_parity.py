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
