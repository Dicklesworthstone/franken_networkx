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
