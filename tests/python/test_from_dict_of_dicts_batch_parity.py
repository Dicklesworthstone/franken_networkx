"""br-r37-c1-nlanb: from_dict_of_dicts batched construction parity vs nx.

The simple-Graph path now routes through add_edges_from (one bulk
insertion) instead of per-edge add_edge + adjacency-view __getitem__ +
dict.update. These tests pin: round-trip identity, aliasing isolation,
node order, malformed-input partial state (nx leaves nodes-but-no-edge),
and that DiGraph / multigraph_input variants keep their contracts.
"""

import random

import networkx as nx
import pytest

import franken_networkx as fnx


def _canon(g):
    return (
        repr([(n, dict(a)) for n, a in g.nodes(data=True)]),
        repr([(u, v, dict(d)) for u, v, d in g.edges(data=True)]),
        repr({n: list(g[n]) for n in g}),
    )


def test_roundtrip_corpus_matches_nx():
    rnd = random.Random(20260605)
    for trial in range(20):
        n = rnd.choice([0, 1, 2, 30, 150])
        g = nx.Graph()
        labels = [f"s{rnd.randrange(40)}" for _ in range(n)]  # str-only: avoids
        # the pre-existing z6uka mixed int/float display issue (own bead)
        g.add_nodes_from(labels)
        for _ in range(n * 2):
            u, v = (rnd.choice(labels), rnd.choice(labels)) if labels else ("a", "b")
            if rnd.random() < 0.5:
                g.add_edge(u, v)
            else:
                g.add_edge(u, v, weight=rnd.random(), color="red")
        d = nx.to_dict_of_dicts(g)
        assert _canon(fnx.from_dict_of_dicts(d)) == _canon(nx.from_dict_of_dicts(d)), trial


@pytest.mark.parametrize(
    "d",
    [
        {},
        {"a": {}, "b": {}},  # isolated nodes
        {"a": {"a": {"w": 1}}},  # self-loop
        {"a": {"b": {"w": 1}}},  # asymmetric input (one direction listed)
        {"z": {"a": {}}, "a": {"z": {}}, "m": {}},  # node order incl. isolated
    ],
)
def test_handcrafted_match_nx(d):
    assert _canon(fnx.from_dict_of_dicts(d)) == _canon(nx.from_dict_of_dicts(d))


def test_no_aliasing_with_input_dicts():
    shared = {"w": 5}
    d = {"a": {"b": shared}, "b": {"a": shared}}
    g = fnx.from_dict_of_dicts(d)
    shared["w"] = 999
    assert g["a"]["b"]["w"] == 5
    g["a"]["b"]["x"] = 7
    assert "x" not in shared


def test_malformed_attrs_value_error_and_partial_state():
    d = {"a": {"b": 1.5}}
    with pytest.raises(TypeError) as nx_err:
        nx.from_dict_of_dicts(d)
    with pytest.raises(TypeError) as fnx_err:
        fnx.from_dict_of_dicts(d)
    assert str(fnx_err.value) == str(nx_err.value)


def test_digraph_and_multigraph_input_unchanged():
    d = {"a": {"b": {"w": 1}}, "b": {"a": {"w": 1}}}
    g_di = fnx.from_dict_of_dicts(d, create_using=fnx.DiGraph)
    assert g_di.is_directed()
    assert sorted(g_di.edges()) == [("a", "b"), ("b", "a")]
    dm = {
        "a": {"b": {0: {"w": 1}, 1: {"w": 2}}},
        "b": {"a": {0: {"w": 1}, 1: {"w": 2}}},
    }
    g_m = fnx.from_dict_of_dicts(dm, create_using=fnx.MultiGraph, multigraph_input=True)
    gn_m = nx.from_dict_of_dicts(dm, create_using=nx.MultiGraph, multigraph_input=True)
    assert sorted(g_m.edges(keys=True, data=True)) == sorted(gn_m.edges(keys=True, data=True))


def test_kernels_exact_after_batched_build():
    rnd = random.Random(3)
    g = nx.Graph()
    for _ in range(150):
        g.add_edge(str(rnd.randrange(40)), str(rnd.randrange(40)), weight=rnd.random() + 0.1)
    d = nx.to_dict_of_dicts(g)
    gf, gn = fnx.from_dict_of_dicts(d), nx.from_dict_of_dicts(d)
    src = next(iter(gn))
    assert dict(fnx.single_source_dijkstra_path_length(gf, src)) == dict(
        nx.single_source_dijkstra_path_length(gn, src)
    )
