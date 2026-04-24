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
