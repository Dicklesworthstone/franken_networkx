"""Eager/lazy validation parity for path & traversal generators.

The "generator function defers eager validation" bug class produced 21 fixes
(see test_generator_eager_not_implemented_parity.py). This net guards the
remaining generator family — the (source[, target]) path/traversal generators —
where validation is split between EAGER (missing source/target -> NodeNotFound
on the call) and LAZY (no-path -> NetworkXNoPath / empty on iteration). Each
case asserts fnx surfaces the same outcome at the same point (call vs iterate)
as networkx, so a future eager/lazy regression in these functions trips.
"""

import inspect

import networkx as nx
import franken_networkx as fnx

import pytest


def _outcome(call):
    """('RAISE:T','-') if the call raises, else ('ok', iterate-outcome)."""
    try:
        g = call()
    except Exception as exc:  # noqa: BLE001
        return ("RAISE:" + type(exc).__name__, "-")
    if not (inspect.isgenerator(g) or hasattr(g, "__next__")):
        return ("VALUE", type(g).__name__)
    try:
        list(g)
        return ("ok", "ok")
    except Exception as exc:  # noqa: BLE001
        return ("ok", "RAISE:" + type(exc).__name__)


def _UG():
    return (nx.Graph([(0, 1), (1, 2), (2, 3), (3, 0), (0, 2)]),
            fnx.Graph([(0, 1), (1, 2), (2, 3), (3, 0), (0, 2)]))


def _DISC():
    return nx.Graph([(0, 1), (2, 3)]), fnx.Graph([(0, 1), (2, 3)])


_PATH_GENS = ["all_simple_paths", "all_shortest_paths", "shortest_simple_paths", "all_simple_edge_paths"]


@pytest.mark.parametrize("name", _PATH_GENS)
@pytest.mark.parametrize("scenario", ["missing_src", "missing_tgt", "no_path", "self"])
def test_path_generator_validation_matches_networkx(name, scenario):
    if not (hasattr(nx, name) and hasattr(fnx, name)):
        pytest.skip(f"{name} unavailable")
    if scenario in ("missing_src", "missing_tgt", "self"):
        gn, gf = _UG()
        args = {"missing_src": (99, 0), "missing_tgt": (0, 99), "self": (0, 0)}[scenario]
    else:  # no_path
        gn, gf = _DISC()
        args = (0, 3)
    n = _outcome(lambda: getattr(nx, name)(gn, *args))
    f = _outcome(lambda: getattr(fnx, name)(gf, *args))
    assert n == f, f"{name}/{scenario}: nx={n} fnx={f}"


_TRAVERSAL = ["bfs_edges", "dfs_edges", "edge_bfs", "edge_dfs", "generic_bfs_edges",
              "dfs_preorder_nodes", "dfs_postorder_nodes"]


@pytest.mark.parametrize("name", _TRAVERSAL)
def test_traversal_missing_source_matches_networkx(name):
    if not (hasattr(nx, name) and hasattr(fnx, name)):
        pytest.skip(f"{name} unavailable")
    gn, gf = _UG()
    n = _outcome(lambda: getattr(nx, name)(gn, 99))
    f = _outcome(lambda: getattr(fnx, name)(gf, 99))
    assert n == f, f"{name}: nx={n} fnx={f}"


def test_bfs_layers_missing_source_matches_networkx():
    gn, gf = _UG()
    assert _outcome(lambda: nx.bfs_layers(gn, [99])) == _outcome(lambda: fnx.bfs_layers(gf, [99]))


def test_descendants_at_distance_missing_matches_networkx():
    dn, df = nx.DiGraph([(0, 1)]), fnx.DiGraph([(0, 1)])
    assert _outcome(lambda: nx.descendants_at_distance(dn, 99, 1)) == _outcome(
        lambda: fnx.descendants_at_distance(df, 99, 1)
    )
