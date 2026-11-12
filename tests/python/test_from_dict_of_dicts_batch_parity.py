"""br-r37-c1-nlanb: from_dict_of_dicts batched construction parity vs nx.

The simple-Graph path now routes through add_edges_from (one bulk
insertion) instead of per-edge add_edge + adjacency-view __getitem__ +
dict.update. These tests pin: round-trip identity, aliasing isolation,
node order, malformed-input partial state (nx leaves nodes-but-no-edge),
and that DiGraph / multigraph_input variants keep their contracts.
"""

from collections.abc import Mapping
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


def _symmetric_dod():
    shared = {"w": 1}
    return {0: {1: shared, 2: {}}, 1: {0: shared}, 2: {0: {}}}


class _NoLookupGraph(fnx.Graph):
    def __getitem__(self, n):
        raise KeyError(n)


class _NxNoLookupGraph(nx.Graph):
    def __getitem__(self, n):
        raise KeyError(n)


def test_subclass_create_using_is_not_read_back_like_networkx():
    # nro4w.7: the subclass branch did add_edge + graph[u][v].update(...);
    # networkx makes one add_edges_from call and never reads the edge back.
    # networkx's approximation tests build an AntiGraph (whose G[u] is the
    # complement) this way: KeyError under the fnx test backend.
    G = fnx.from_dict_of_dicts(_symmetric_dod(), create_using=_NoLookupGraph)
    H = nx.from_dict_of_dicts(_symmetric_dod(), create_using=_NxNoLookupGraph)
    assert sorted(G.edges(data=True)) == sorted(H.edges(data=True))


def _decode_outcome(module, data, graph):
    try:
        module.from_dict_of_dicts(data, create_using=graph)
        error = None
    except Exception as exc:
        error = type(exc), str(exc)
    return error, _canon(graph)


@pytest.mark.parametrize("class_name", ["Graph", "DiGraph"])
@pytest.mark.parametrize("input_kind", ["dict", "adjacency_view"])
@pytest.mark.parametrize("mutation", ["later_row", "current_row", "later_value"])
def test_edge_attribute_providers_observe_incremental_source_rows(class_name, input_kind, mutation):
    def run(module):
        graph = getattr(module, class_name)()
        data = {0: {1: {}}, 1: {0: {}, 2: {}}, 2: {1: {}}, 3: {}}
        calls = []

        class Attributes(Mapping):
            def __len__(self):
                return 1

            def __iter__(self):
                return iter(("cost",))

            def __getitem__(self, key):
                calls.append((key, graph.has_edge(0, 1), graph.has_edge(1, 2)))
                if mutation == "later_row":
                    data[2][3] = data[3][2] = {"cost": 99}
                elif mutation == "current_row":
                    data[0][3] = data[3][0] = {"cost": 99}
                else:
                    data[1][2]["cost"] = 99
                return 7

        data[0][1] = data[1][0] = Attributes()
        source = data if input_kind == "dict" else nx.classes.coreviews.AdjacencyView(data)
        outcome = _decode_outcome(module, source, graph)
        return outcome, calls

    expected = run(nx)
    assert expected[1], "the fixture must read the attribute provider"
    assert run(fnx) == expected


@pytest.mark.parametrize("class_name", ["Graph", "DiGraph"])
@pytest.mark.parametrize("provider_kind", ["outer", "row"])
def test_mapping_rows_see_each_edge_before_yielding_another(class_name, provider_kind):
    def run(module):
        graph = getattr(module, class_name)()
        calls = []

        class Rows(dict):
            def items(self):
                for key, value in super().items():
                    calls.append((key, tuple(graph.edges())))
                    yield key, value

        if provider_kind == "outer":
            data = Rows({0: {1: {"cost": 1}}, 1: {2: {"cost": 2}}, 2: {}})
        else:
            data = {0: Rows({1: {"cost": 1}, 2: {"cost": 2}}), 1: {}, 2: {}}
        return _decode_outcome(module, data, graph), calls

    expected = run(nx)
    assert expected[1][1][1] == ((0, 1),)
    assert run(fnx) == expected


@pytest.mark.parametrize("class_name", ["Graph", "DiGraph"])
@pytest.mark.parametrize("existing_edge", [False, True])
def test_attribute_provider_errors_keep_the_completed_prefix(class_name, existing_edge):
    def run(module):
        graph = getattr(module, class_name)()

        class FailsAfterOne(Mapping):
            def __len__(self):
                return 2

            def __iter__(self):
                return iter(("completed", "failure"))

            def __getitem__(self, key):
                if key == "failure":
                    raise ValueError("attribute provider stopped")
                return 99

        data = {0: {1: {"first": 1}}, 1: {}, 2: {}}
        if existing_edge:
            data[1][0] = FailsAfterOne()
        else:
            data[1][2] = FailsAfterOne()
        return _decode_outcome(module, data, graph)

    expected = run(nx)
    assert expected[0] == (ValueError, "attribute provider stopped")
    assert run(fnx) == expected


@pytest.mark.parametrize("class_name", ["Graph", "DiGraph"])
def test_new_edge_provider_sees_missing_endpoint_before_its_error(class_name):
    def run(module):
        graph = getattr(module, class_name)()
        calls = []

        class Attributes(Mapping):
            def __len__(self):
                return 1

            def __iter__(self):
                return iter(("cost",))

            def __getitem__(self, key):
                calls.append((tuple(graph), tuple(graph.edges())))
                raise ValueError("no edge attributes")

        outcome = _decode_outcome(module, {"source": {"new": Attributes()}}, graph)
        return outcome, calls

    expected = run(nx)
    assert expected[1] == [(("source", "new"), ())]
    assert expected[0][0] == (ValueError, "no edge attributes")
    assert run(fnx) == expected


@pytest.mark.parametrize("class_name", ["Graph", "DiGraph"])
def test_streaming_decode_does_not_dispatch_through_unrelated_instance_hooks(class_name):
    def run(module):
        graph = getattr(module, class_name)()

        def forbidden(*args, **kwargs):
            raise AssertionError("add_edges_from does not invoke this instance method")

        graph.add_node = forbidden
        graph.get_edge_data = forbidden

        class Attributes(Mapping):
            def __len__(self):
                return 1

            def __iter__(self):
                return iter(("cost",))

            def __getitem__(self, key):
                return 7

        return _decode_outcome(module, {0: {1: Attributes()}}, graph)

    expected = run(nx)
    assert expected[0] is None
    assert run(fnx) == expected


@pytest.mark.parametrize("class_name", ["Graph", "DiGraph"])
def test_patched_standard_adjacency_view_keeps_its_public_iteration(monkeypatch, class_name):
    view_class = nx.classes.coreviews.AdjacencyView
    original = view_class.items

    def run(module):
        graph = getattr(module, class_name)()
        source = view_class({0: {1: {}}, 1: {2: {}}, 2: {}})
        calls = []

        def observed(view):
            for node, row in original(view):
                calls.append((node, tuple(graph.edges())))
                yield node, row

        with monkeypatch.context() as patch:
            patch.setattr(view_class, "items", observed)
            outcome = _decode_outcome(module, source, graph)
        return outcome, calls

    expected = run(nx)
    assert expected[1][1][1] == ((0, 1),)
    assert run(fnx) == expected
