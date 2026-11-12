"""Conformance guard for the same-type / lift constructor-absorb folds.

cls(other_graph) — building a graph from another graph instance — is the "absorb"
path. cc folded MultiGraph(MultiGraph) and MultiGraph(Graph) to single-pass
with_mirror; CrimsonRiver folds the DiGraph/MultiDiGraph constructors ("new")
toward fully-lazy. Existing tests cover dict-of-list / numpy / from-nx inputs but
NOT fnx-graph absorb, so this locks it vs networkx:

  * same-type absorb (Graph(Graph), DiGraph(DiGraph), MultiGraph(MultiGraph),
    MultiDiGraph(MultiDiGraph)) reproduces nodes/edges/attrs/graph-attrs exactly;
  * simple->multi LIFT (MultiGraph(Graph), MultiDiGraph(DiGraph)) lifts edges to
    key 0 and matches nx;
  * the absorb result is independent of the source (mutating source after).

No mocks: real fnx vs real networkx.
"""

from __future__ import annotations

from collections.abc import Mapping
import random

import pytest
import networkx as nx
import franken_networkx as fnx

# (fnx_target, nx_target, fnx_source, nx_source)
_SAME = [
    (fnx.Graph, nx.Graph, fnx.Graph, nx.Graph),
    (fnx.DiGraph, nx.DiGraph, fnx.DiGraph, nx.DiGraph),
    (fnx.MultiGraph, nx.MultiGraph, fnx.MultiGraph, nx.MultiGraph),
    (fnx.MultiDiGraph, nx.MultiDiGraph, fnx.MultiDiGraph, nx.MultiDiGraph),
]
_LIFT = [
    (fnx.MultiGraph, nx.MultiGraph, fnx.Graph, nx.Graph),
    (fnx.MultiDiGraph, nx.MultiDiGraph, fnx.DiGraph, nx.DiGraph),
]


def _fill(fg, ng, seed):
    r = random.Random(seed)
    n = r.randint(4, 9)
    for node in range(n):
        fg.add_node(node, tag=f"t{node}")
        ng.add_node(node, tag=f"t{node}")
    directed = fg.is_directed()
    for u in range(n):
        for v in range(n):
            if (u < v or (directed and u != v)) and r.random() < 0.4:
                w = r.randint(1, 9)
                fg.add_edge(u, v, weight=w)
                ng.add_edge(u, v, weight=w)
    fg.graph["meta"] = "m"
    ng.graph["meta"] = "m"


def _nattrs(g):
    return {n: dict(d) for n, d in g.nodes(data=True)}


def _eattrs(g):
    if g.is_multigraph():
        return sorted(((u, v), tuple(sorted(d.items())))
                      for u, v, k, d in g.edges(keys=True, data=True))
    return sorted(((u, v), tuple(sorted(d.items()))) for u, v, d in g.edges(data=True))


@pytest.mark.parametrize("ft,nt,fs,ns", _SAME + _LIFT)
@pytest.mark.parametrize("seed", range(12))
def test_absorb_matches_networkx(ft, nt, fs, ns, seed):
    fsrc, nsrc = fs(), ns()
    _fill(fsrc, nsrc, seed)
    fres, nres = ft(fsrc), nt(nsrc)
    assert sorted(fres.nodes()) == sorted(nres.nodes())
    assert _nattrs(fres) == _nattrs(nres)
    assert _eattrs(fres) == _eattrs(nres)
    assert dict(fres.graph) == dict(nres.graph)


@pytest.mark.parametrize("ft,nt,fs,ns", _SAME)
@pytest.mark.parametrize("seed", range(8))
def test_absorb_independent_of_source(ft, nt, fs, ns, seed):
    fsrc, nsrc = fs(), ns()
    _fill(fsrc, nsrc, seed)
    fres = ft(fsrc)
    before_n, before_e = _nattrs(fres), _eattrs(fres)
    for node in list(fsrc.nodes()):
        fsrc.nodes[node]["tag"] = "MUT"
        break
    fsrc.add_node("brand_new")
    assert _nattrs(fres) == before_n
    assert _eattrs(fres) == before_e
    assert "brand_new" not in set(fres.nodes())


@pytest.mark.parametrize(
    "rows",
    [
        [(1, 2, "")] * 8,
        [(1, 2, f"key-{index}") for index in range(8)] + [(1, 2, "")],
        [(1, 2, "", {"explicit": True})] * 8,
    ],
)
def test_multidigraph_true_iterator_empty_string_key_or_edge_data_matches_networkx(rows):
    """NetworkX consumes an empty string in a 3-tuple as edge data.

    This uses a genuine one-shot iterator so the typed constructor staging is
    exercised, including the case where it must abandon an already-staged
    explicit-key prefix. A 4-tuple instead keeps the empty string as an
    explicit key, matching NetworkX's arity-sensitive interpretation.
    """
    fnx_graph = fnx.MultiDiGraph(edge for edge in rows)
    nx_graph = nx.MultiDiGraph(edge for edge in rows)

    assert list(fnx_graph.edges(keys=True, data=True)) == list(
        nx_graph.edges(keys=True, data=True)
    )


_CONSTRUCTOR_KINDS = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]


def _constructor_public_state(graph):
    def rows(mapping):
        return [
            (node, [(neighbor, list(data)) for neighbor, data in row.items()])
            for node, row in mapping.items()
        ]

    edges = graph.edges(keys=True, data=True) if graph.is_multigraph() else graph.edges(data=True)
    return (
        [(node, list(attrs.items())) for node, attrs in graph.nodes(data=True)],
        [(*edge[:-1], list(edge[-1].items())) for edge in edges],
        rows(graph.adj),
        rows(graph.pred) if graph.is_directed() else None,
        list(graph.graph.items()),
    )


def _constructor_logical_input(library, kind, input_kind):
    logical = getattr(nx, kind)()
    payload = ["shared"]
    logical.add_nodes_from(
        (node, {"z": node, ("node", 1): payload, "a": 1})
        for node in ("isolated", ("middle", 1), "source", "sink")
    )
    for index, (u, v) in enumerate([
        ("source", "sink"), (("middle", 1), "source"),
        ("sink", ("middle", 1)), (("middle", 1), ("middle", 1)),
    ]):
        logical.add_edges_from([(u, v, {"z": index, ("edge", 1): payload, "a": 2})])
    if logical.is_directed():
        logical.add_edge("sink", "source", reciprocal=True)
    if logical.is_multigraph():
        logical.add_edges_from([
            ("source", "sink", ("parallel", 2), {"extra": payload}),
        ])
    logical.graph.update({"z": 1, ("graph", 1): payload, "a": 2})
    if input_kind == "networkx":
        return logical, payload
    if input_kind == "networkx_view":
        return nx.subgraph_view(logical), payload

    graph = getattr(library, kind)()
    graph.graph.update(logical.graph)
    if input_kind == "assigned":
        graph.add_edge("stale", "native", stale=True)
        graph._node = logical._node
        graph._adj = logical._adj
        if logical.is_directed():
            graph._pred = logical._pred
    else:
        graph.add_nodes_from(logical.nodes(data=True))
        if input_kind == "assigned_adjacency":
            graph.add_edge("source", "sink", stale=True)
            graph._adj = logical._adj
        else:
            graph.add_edges_from(
                logical.edges(keys=True, data=True) if logical.is_multigraph()
                else logical.edges(data=True)
            )
            if input_kind == "assigned_node":
                graph._node = dict(reversed(list(logical._node.items())))
    return graph, payload


@pytest.mark.parametrize("source_kind", _CONSTRUCTOR_KINDS)
@pytest.mark.parametrize("target_kind", _CONSTRUCTOR_KINDS)
@pytest.mark.parametrize(
    "input_kind", ["native", "assigned", "assigned_node", "assigned_adjacency", "networkx", "networkx_view"],
)
def test_constructor_uses_logical_rows_and_shallow_attributes(source_kind, target_kind, input_kind):
    source, payload = _constructor_logical_input(fnx, source_kind, input_kind)
    expected_source, _ = _constructor_logical_input(nx, source_kind, input_kind)
    before = _constructor_public_state(source)
    expected_before = _constructor_public_state(expected_source)
    result = getattr(fnx, target_kind)(source, z="override", extra="constructor")
    expected = getattr(nx, target_kind)(expected_source, z="override", extra="constructor")

    assert _constructor_public_state(result) == _constructor_public_state(expected)
    assert result.graph[("graph", 1)] is payload
    assert result.nodes["source"][("node", 1)] is payload
    edge = result["source"]["sink"]
    if result.is_multigraph():
        edge = edge[0]
    assert edge[("edge", 1)] is payload
    result.graph["only_target"] = True
    result.nodes["source"]["only_target"] = True
    edge["only_target"] = True
    assert _constructor_public_state(source) == before
    assert _constructor_public_state(expected_source) == expected_before
    if input_kind != "networkx_view":
        source.add_node("only_source")
    assert "only_source" not in result


@pytest.mark.parametrize("target_kind", _CONSTRUCTOR_KINDS)
@pytest.mark.parametrize("case", ["missing_node", "node_attributes", "graph_attributes"])
def test_constructor_public_mapping_failures_keep_networkx_error_cause(target_kind, case):
    def run(library):
        source = nx.Graph()
        source.add_edge("source", "sink")
        events = []

        class Broken(dict):
            def keys(self):
                events.append("keys")
                raise ValueError("attribute provider failed")

            def __iter__(self):
                return super().__iter__()

        if case == "missing_node":
            source._node["missing"] = {}
        elif case == "node_attributes":
            source._node["source"] = Broken(value=1)
        else:
            source.graph = Broken(value=1)
        try:
            getattr(library, target_kind)(source)
        except Exception as exc:
            cause = exc.__cause__
            return type(exc), exc.args, type(cause), cause.args, events
        raise AssertionError("constructor did not report the invalid source")

    assert run(fnx) == run(nx)


@pytest.mark.parametrize("target_kind", _CONSTRUCTOR_KINDS)
@pytest.mark.parametrize("assigned", [False, True])
def test_constructor_observes_edge_attribute_callbacks_before_later_rows(target_kind, assigned):
    def run(library):
        logical = nx.Graph()
        logical.add_nodes_from(range(4))
        logical.add_edges_from([(0, 1), (1, 2)])
        events = []

        class Attributes(Mapping):
            def __len__(self):
                return 1

            def __iter__(self):
                return iter(("cost",))

            def __getitem__(self, key):
                events.append(key)
                logical.add_edge(2, 3, cost=99)
                return 7

        attrs = Attributes()
        logical._adj[0][1] = logical._adj[1][0] = attrs
        source = logical
        if assigned:
            source = library.Graph()
            source.add_edge("stale", "native")
            source._node = logical._node
            source._adj = logical._adj
        result = getattr(library, target_kind)(source)
        assert result.has_edge(2, 3)
        return _constructor_public_state(result), events

    assert run(fnx) == run(nx)


@pytest.mark.parametrize("case", ["scalar", "tuple_key", "nested", "wide_integer", "subclass"])
def test_multigraph_constructor_absorbs_only_lossless_edge_attributes(case, monkeypatch):
    class Scalar(int):
        pass

    attributes = {
        "scalar": {"weight": 3, "name": "route", "active": True, "capacity": 1.5},
        "tuple_key": {("attribute", 1): 3},
        "nested": {"payload": {"items": [1, 2]}},
        "wide_integer": {"weight": 2**100},
        "subclass": {"weight": Scalar(3)},
    }[case]
    source = fnx.Graph()
    source.add_edges_from([("source", "sink", attributes)])
    expected_source = nx.Graph()
    expected_source.add_edges_from([("source", "sink", attributes)])
    expected = nx.MultiGraph(expected_source)
    calls = []
    native = fnx._fnx.multigraph_absorb_graph

    def recorded(*args):
        calls.append(args)
        return native(*args)

    monkeypatch.setattr(fnx._fnx, "multigraph_absorb_graph", recorded)
    result = fnx.MultiGraph(source)
    assert _constructor_public_state(result) == _constructor_public_state(expected)
    assert len(calls) == (1 if case == "scalar" else 0)
    if case != "scalar":
        for key, value in source["source"]["sink"].items():
            assert result["source"]["sink"][0][key] is value


@pytest.mark.parametrize("kind", ["Graph", "DiGraph"])
def test_max_flow_min_cost_copies_the_logical_source_graph(kind):
    source = getattr(nx, kind)()
    source.add_edge("source", "sink", capacity=3, weight=2)
    graph = getattr(fnx, kind)()
    graph.add_edge("stale", "native", capacity=1, weight=99)
    graph._node = source._node
    graph._adj = source._adj
    if source.is_directed():
        graph._pred = source._pred
    expected = nx.max_flow_min_cost(source, "source", "sink")
    assert fnx.max_flow_min_cost(graph, "source", "sink") == expected
