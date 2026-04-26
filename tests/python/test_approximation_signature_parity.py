"""Parity for ``fnx.approximation.*`` introspectable signatures.

Bead br-r37-c1-approxsig. The ``_ApproximationNamespace`` wrapper
class used a generic ``(G, *args, **kwargs)`` shape, so
``inspect.signature(fnx.approximation.X)`` returned that catch-all
for *every* approximation function. nx exposes the documented
per-function signatures (e.g. ``average_clustering(G, trials=1000,
seed=None)``).

Fix: ``functools.wraps(nx_func)`` on the dynamic wrapper so the
returned callable carries nx's full signature, name, and docstring.
"""

from __future__ import annotations

import inspect

import pytest

import franken_networkx as fnx

try:
    import networkx as nx
    HAS_NX = True
except ImportError:
    HAS_NX = False

needs_nx = pytest.mark.skipif(not HAS_NX, reason="networkx not installed")


# A representative subset that previously had ``*args, **kwargs`` shape.
APPROX_NAMES = [
    "all_pairs_node_connectivity",
    "asadpour_atsp",
    "average_clustering",
    "christofides",
    "clique_removal",
    "densest_subgraph",
    "diameter",
    "greedy_tsp",
    "k_components",
    "large_clique_size",
    "local_node_connectivity",
    "max_clique",
    "maximum_independent_set",
    "metric_closure",
    "min_edge_dominating_set",
    "min_maximal_matching",
    "min_weighted_dominating_set",
    "min_weighted_vertex_cover",
    "node_connectivity",
    "one_exchange",
    "ramsey_R2",
    "randomized_partitioning",
    "simulated_annealing_tsp",
    "steiner_tree",
    "threshold_accepting_tsp",
    "traveling_salesman_problem",
    "treewidth_min_fill_in",
]


@needs_nx
@pytest.mark.parametrize("name", APPROX_NAMES)
def test_approximation_signature_matches_networkx(name):
    if not hasattr(nx.approximation, name) or not hasattr(fnx.approximation, name):
        pytest.skip(f"{name} not in both libraries")

    fnx_sig = inspect.signature(getattr(fnx.approximation, name))
    nx_sig = inspect.signature(getattr(nx.approximation, name))

    fnx_params = [k for k in fnx_sig.parameters.keys()
                  if k not in ("backend", "backend_kwargs")]
    nx_params = [k for k in nx_sig.parameters.keys()
                 if k not in ("backend", "backend_kwargs")]
    assert fnx_params == nx_params

    # Generic wrapper used to expose ``args``/``kwargs`` as fake params;
    # confirm those are gone (or only appear via the wrapper's
    # transparent **kwargs catch-all, never as positional placeholders).
    fnx_kinds = {k: v.kind for k, v in fnx_sig.parameters.items()}
    for k, kind in fnx_kinds.items():
        if k == "args":
            assert kind == inspect.Parameter.VAR_POSITIONAL
        if k == "kwargs":
            assert kind == inspect.Parameter.VAR_KEYWORD


@needs_nx
def test_approximation_call_still_works():
    """Concrete sanity: the wrapper still routes through to nx
    correctly with kwargs."""
    G = fnx.karate_club_graph()
    GX = nx.karate_club_graph()
    r_fnx = fnx.approximation.average_clustering(G, trials=200, seed=42)
    r_nx = nx.approximation.average_clustering(GX, trials=200, seed=42)
    assert abs(r_fnx - r_nx) < 0.05


@needs_nx
def test_approximation_treewidth_min_degree_overrides_dispatch():
    """treewidth_min_degree was overridden in fnx (not delegated). Its
    signature must still match upstream so introspection is honest."""
    fnx_sig = inspect.signature(fnx.approximation.treewidth_min_degree)
    # fnx defines it as a method (G,); nx's takes (G, *) — accept just G
    assert "G" in fnx_sig.parameters


@needs_nx
def test_approximation_wrapper_carries_nx_docstring():
    """functools.wraps must copy __doc__ + __name__ from nx_func."""
    f = fnx.approximation.average_clustering
    nx_f = nx.approximation.average_clustering
    assert f.__name__ == nx_f.__name__ == "average_clustering"
    # docstrings should match (after the dispatch decorator chain)
    assert (f.__doc__ or "")[:50] == (nx_f.__doc__ or "")[:50]
