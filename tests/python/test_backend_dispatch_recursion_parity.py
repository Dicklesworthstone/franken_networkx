"""Regression coverage for backend-dispatch re-entry (br-parityrec).

When a user sets ``nx.config.backend_priority = ["franken_networkx"]``
to transparently accelerate nx calls, and then calls an algorithm that
fnx implements via the _call_networkx_for_parity fallback (because fnx
can't honour some argument, e.g. ``flow_func=``), the fallback must
bypass the backend dispatcher — otherwise ``getattr(nx, name)(...)``
re-enters the dispatcher and bounces right back into fnx, producing an
infinite RecursionError before the user ever sees a result.

Fix: _call_networkx_for_parity and _call_networkx_submodule_for_parity
both call nx with ``backend="networkx"`` to force the pure-Python nx
path.
"""

from __future__ import annotations

import warnings

import networkx as nx
import pytest


@pytest.fixture(autouse=True)
def _clear_backend_priority():
    prior_algos = list(nx.config.backend_priority.algos)
    yield
    nx.config.backend_priority.algos = prior_algos


def test_maximum_flow_value_with_flow_func_does_not_recurse():
    """flow_func triggers the parity fallback; recursion used to blow up."""
    nx.config.backend_priority.algos = ["franken_networkx"]

    G = nx.DiGraph()
    G.add_edge("s", "a", capacity=3)
    G.add_edge("s", "t", capacity=2)
    G.add_edge("a", "t", capacity=2)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        val = nx.maximum_flow_value(
            G,
            "s",
            "t",
            flow_func=nx.algorithms.flow.shortest_augmenting_path,
        )
    assert val == 4


def test_maximum_flow_default_still_uses_backend():
    """Regression-check that the dispatch-bypass patch did not break the
    ordinary dispatch path that reaches fnx's native implementation."""
    nx.config.backend_priority.algos = ["franken_networkx"]

    G = nx.DiGraph()
    G.add_edge("s", "a", capacity=3)
    G.add_edge("s", "t", capacity=2)
    G.add_edge("a", "t", capacity=2)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        val = nx.maximum_flow_value(G, "s", "t")
    assert val == 4


def test_average_shortest_path_length_with_method_does_not_recurse():
    """method=... is rejected by can_run for aspl; parity path must not
    re-enter the backend."""
    nx.config.backend_priority.algos = ["franken_networkx"]
    G = nx.path_graph(5)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        val = nx.average_shortest_path_length(G, method="dijkstra")
    assert val == pytest.approx(2.0)


def test_maximum_flow_with_flow_func_does_not_recurse():
    nx.config.backend_priority.algos = ["franken_networkx"]
    G = nx.DiGraph()
    G.add_edge("s", "a", capacity=3)
    G.add_edge("s", "t", capacity=2)
    G.add_edge("a", "t", capacity=2)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        val, flow_dict = nx.maximum_flow(
            G, "s", "t", flow_func=nx.algorithms.flow.shortest_augmenting_path
        )
    assert val == 4
    assert flow_dict["s"]["a"] == 2
    assert flow_dict["s"]["t"] == 2


def test_minimum_cut_with_flow_func_does_not_recurse():
    nx.config.backend_priority.algos = ["franken_networkx"]
    G = nx.DiGraph()
    G.add_edge("s", "a", capacity=3)
    G.add_edge("s", "t", capacity=2)
    G.add_edge("a", "t", capacity=2)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        cut_val, partition = nx.minimum_cut(
            G, "s", "t", flow_func=nx.algorithms.flow.shortest_augmenting_path
        )
    assert cut_val == 4
    assert "s" in partition[0]
    assert "t" in partition[1]


def test_minimum_cut_value_with_flow_func_does_not_recurse():
    nx.config.backend_priority.algos = ["franken_networkx"]
    G = nx.DiGraph()
    G.add_edge("s", "a", capacity=3)
    G.add_edge("s", "t", capacity=2)
    G.add_edge("a", "t", capacity=2)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        cut_val = nx.minimum_cut_value(
            G, "s", "t", flow_func=nx.algorithms.flow.shortest_augmenting_path
        )
    assert cut_val == 4


def test_k_components_does_not_recurse():
    nx.config.backend_priority.algos = ["franken_networkx"]
    G = nx.cycle_graph(4)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        kc = nx.algorithms.connectivity.kcomponents.k_components(G)
    assert 2 in kc


def test_random_reference_does_not_recurse():
    nx.config.backend_priority.algos = ["franken_networkx"]
    G = nx.cycle_graph(4)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        rr = nx.algorithms.smallworld.random_reference(G, niter=1, seed=42)
    assert len(rr) == 4


def test_check_planarity_does_not_recurse():
    nx.config.backend_priority.algos = ["franken_networkx"]
    G = nx.cycle_graph(4)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        is_planar, _ = nx.check_planarity(G)
    assert is_planar is True


def test_junction_tree_does_not_recurse():
    nx.config.backend_priority.algos = ["franken_networkx"]
    G = nx.cycle_graph(4)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        jt = nx.junction_tree(G)
    assert len(jt) > 0


def test_random_kernel_graph_does_not_recurse():
    nx.config.backend_priority.algos = ["franken_networkx"]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        rkg = nx.random_kernel_graph(
            10,
            lambda u, w, z: z - w,
            lambda u, w, r: r + w,
            seed=42,
        )
    assert len(rkg) == 10


def test_read_edgelist_and_adjlist_do_not_recurse():
    import io
    nx.config.backend_priority.algos = ["franken_networkx"]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        f = io.BytesIO(b"1 2\n2 3\n")
        g = nx.read_edgelist(f)
        assert len(g) == 3
        f2 = io.BytesIO(b"1 2 3\n")
        g2 = nx.read_adjlist(f2)
        assert len(g2) == 3


def test_tutte_polynomial_does_not_recurse():
    pytest.importorskip("sympy")
    nx.config.backend_priority.algos = ["franken_networkx"]
    G = nx.cycle_graph(4)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        tp = nx.algorithms.polynomials.tutte_polynomial(G)
    assert tp is not None


