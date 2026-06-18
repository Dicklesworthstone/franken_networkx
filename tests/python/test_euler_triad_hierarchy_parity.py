"""Phase B certification: Eulerian circuits/paths (edge-traversal ORDER
is a parity contract), triadic_census, flow_hierarchy, reciprocity,
regularity, dispersion. Zero divergences.
"""
import random

import networkx as nx

import franken_networkx as fnx


def _expect(condition, message):
    if not condition:
        raise AssertionError(message)


def _eul(mod):
    g = mod.Graph()
    for u, v in [(0, 1), (1, 2), (2, 0), (2, 3), (3, 4), (4, 2)]:
        g.add_edge(u, v)
    return g


def _semi(mod):
    g = mod.Graph()
    for u, v in [(0, 1), (1, 2), (2, 3), (3, 0), (0, 2)]:
        g.add_edge(u, v)
    return g


def test_eulerian_circuit_and_path_order():
    ef, en = _eul(fnx), _eul(nx)
    assert fnx.is_eulerian(ef) == nx.is_eulerian(en) is True
    assert [(repr(u), repr(v)) for u, v in fnx.eulerian_circuit(ef, source=0)] == [
        (repr(u), repr(v)) for u, v in nx.eulerian_circuit(en, source=0)
    ]
    sf, sn = _semi(fnx), _semi(nx)
    assert fnx.has_eulerian_path(sf) == nx.has_eulerian_path(sn) is True
    assert [(repr(u), repr(v)) for u, v in fnx.eulerian_path(sf)] == [
        (repr(u), repr(v)) for u, v in nx.eulerian_path(sn)
    ]


def test_euler_module_eulerize_returns_fnx_multigraph_with_edge_parity():
    from franken_networkx import euler as fnx_euler
    from networkx.algorithms import euler as nx_euler

    fnx_graph = fnx.path_graph(4)
    nx_graph = nx.path_graph(4)

    actual = fnx_euler.eulerize(fnx_graph)
    expected = nx_euler.eulerize(nx_graph)

    actual_edges = sorted(tuple(sorted(edge)) for edge in actual.edges())
    expected_edges = sorted(tuple(sorted(edge)) for edge in expected.edges())

    _expect(
        isinstance(actual, fnx.MultiGraph),
        "franken_networkx.euler.eulerize must return fnx.MultiGraph",
    )
    _expect(
        actual_edges == expected_edges,
        "franken_networkx.euler.eulerize edge multiset must match networkx",
    )


def _mkd():
    R = random.Random(71)
    de = [(u, v) for u, v in ((R.randrange(10), R.randrange(10)) for _ in range(35)) if u != v]
    return fnx.DiGraph(de), nx.DiGraph(de)


def test_triadic_census_flow_hierarchy_reciprocity():
    df, dn = _mkd()
    assert dict(fnx.triadic_census(df)) == dict(nx.triadic_census(dn))
    assert round(nx.flow_hierarchy(df), 9) == round(nx.flow_hierarchy(dn), 9)
    assert round(fnx.reciprocity(df), 9) == round(nx.reciprocity(dn), 9)


def test_regularity_and_dispersion():
    R = random.Random(73)
    ue = [(u, v) for u, v in ((R.randrange(10), R.randrange(10)) for _ in range(30)) if u != v]
    gf, gn = fnx.Graph(ue), nx.Graph(ue)
    assert nx.is_regular(gf) == nx.is_regular(gn)
    assert nx.is_regular(fnx.complete_graph(4)) == nx.is_regular(nx.complete_graph(4)) is True
    df = nx.dispersion(gf, 0)
    dn = nx.dispersion(gn, 0)
    assert {repr(k): round(v, 6) for k, v in df.items()} == {repr(k): round(v, 6) for k, v in dn.items()}
