"""Parity + perf guard for complete_to_chordal_graph (MCS-M).

br-ctcg-localadj: the MCS-M minimal-fill-in inner test used
``has_path(H.subgraph(lower_nodes + [z, y]).copy(), y, z)``. The ``.copy()``
paid the full graph-construction tax O(|V|^2) times, making this ~77x slower
than networkx (49.8s vs 0.64s on watts_strogatz(200, 6)). It now snapshots G's
adjacency into plain sets once and runs the reachability test locally; the
chordal completion H and elimination ordering alpha are byte-identical to nx.
"""

import importlib
import time

import networkx as nx
import pytest

import franken_networkx as fnx


def _mk(n, k, p, seed):
    Gx = nx.connected_watts_strogatz_graph(n, k, p, seed=seed)
    Gf = fnx.Graph()
    Gf.add_nodes_from(Gx.nodes())
    Gf.add_edges_from(Gx.edges())
    return Gx, Gf


def _canon(H, alpha):
    return (
        sorted(tuple(sorted(e)) for e in H.edges()),
        {repr(k): v for k, v in alpha.items()},
    )


@pytest.mark.parametrize(
    ("graph_factory", "expected_factory"),
    [
        (fnx.DiGraph, nx.DiGraph),
        (fnx.MultiGraph, nx.MultiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_not_implemented_guard_order_matches_networkx(
    graph_factory, expected_factory
):
    graph = graph_factory([(0, 1), (1, 2)])
    expected_graph = expected_factory([(0, 1), (1, 2)])

    with pytest.raises(nx.NetworkXNotImplemented) as fnx_exc:
        fnx.complete_to_chordal_graph(graph)
    with pytest.raises(nx.NetworkXNotImplemented) as nx_exc:
        nx.complete_to_chordal_graph(expected_graph)

    assert str(fnx_exc.value) == str(nx_exc.value)


@pytest.mark.parametrize(
    ("graph_factory", "expected_factory"),
    [
        (fnx.DiGraph, nx.DiGraph),
        (fnx.MultiGraph, nx.MultiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_chordal_module_guard_order_matches_networkx(
    graph_factory, expected_factory
):
    module = importlib.import_module("franken_networkx.chordal")
    graph = graph_factory([(0, 1), (1, 2)])
    expected_graph = expected_factory([(0, 1), (1, 2)])

    with pytest.raises(nx.NetworkXNotImplemented) as fnx_exc:
        module.complete_to_chordal_graph(graph)
    with pytest.raises(nx.NetworkXNotImplemented) as nx_exc:
        nx.complete_to_chordal_graph(expected_graph)

    assert str(fnx_exc.value) == str(nx_exc.value)


def test_parity_random_graphs():
    for n, k, p, seed in [
        (30, 4, 0.3, 1),
        (50, 6, 0.3, 2),
        (60, 4, 0.5, 3),
        (40, 6, 0.2, 4),
        (80, 6, 0.3, 5),
    ]:
        Gx, Gf = _mk(n, k, p, seed)
        Hx, ax = nx.complete_to_chordal_graph(Gx)
        Hf, af = fnx.complete_to_chordal_graph(Gf)
        assert _canon(Hx, ax) == _canon(Hf, af), (n, k, p, seed)
        assert nx.is_chordal(Hf)


def test_already_chordal_input_is_identity():
    # A tree is chordal: H == G and alpha maps every node to 0.
    builder = getattr(nx, "random_labeled_tree", None) or nx.random_tree
    T = builder(40, seed=7)
    Tf = fnx.Graph()
    Tf.add_nodes_from(T.nodes())
    Tf.add_edges_from(T.edges())
    Hf, af = fnx.complete_to_chordal_graph(Tf)
    assert sorted(tuple(sorted(e)) for e in Hf.edges()) == sorted(
        tuple(sorted(e)) for e in T.edges()
    )
    assert set(af.values()) == {0}


def test_complete_graph_is_already_chordal():
    Kx = nx.complete_graph(8)
    Kf = fnx.complete_graph(8)
    Hx, ax = nx.complete_to_chordal_graph(Kx)
    Hf, af = fnx.complete_to_chordal_graph(Kf)
    assert _canon(Hx, ax) == _canon(Hf, af)


def test_perf_no_quadratic_copy_blowup():
    # Regression guard: the old subgraph-copy path took ~50s here; the local
    # adjacency version is well under a second. Use a generous ceiling to stay
    # robust under host noise while still catching a return of the O(|V|^2)
    # construction-tax blowup.
    Gx, Gf = _mk(200, 6, 0.3, 3)
    t = time.perf_counter()
    fnx.complete_to_chordal_graph(Gf)
    elapsed = time.perf_counter() - t
    assert elapsed < 10.0, f"complete_to_chordal_graph too slow: {elapsed:.1f}s"
