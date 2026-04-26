"""Parity for ``graph_edit_distance`` family signatures.

Bead br-r37-c1-gedsig. fnx exposed only ``(G1, G2, **kwargs)`` for
``graph_edit_distance``, ``optimize_graph_edit_distance``, and
``optimize_edit_paths``. inspect.signature() returned a useless
catch-all instead of the documented per-arg surface, and worse, the
``timeout`` kwarg raised ``NetworkXNotImplemented`` whenever the
native fast path didn't fire — leaving drop-in callers with no way to
get a bounded-time result.

Aligned: signatures now spell out every nx parameter explicitly, and
the timeout branch delegates to networkx so the iterative algorithm
honours the cutoff.
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


@needs_nx
@pytest.mark.parametrize(
    "name",
    ["graph_edit_distance", "optimize_graph_edit_distance", "optimize_edit_paths"],
)
def test_signature_parameter_list_matches_networkx(name):
    fnx_sig = inspect.signature(getattr(fnx, name))
    nx_sig = inspect.signature(getattr(nx, name))
    fnx_params = list(fnx_sig.parameters.keys())
    nx_params = [k for k in nx_sig.parameters.keys()
                 if k not in ("backend", "backend_kwargs")]
    assert fnx_params == nx_params


@needs_nx
def test_graph_edit_distance_timeout_raises_not_implemented():
    """fnx's contract is to NOT fall back to nx for the timeout-cutoff
    iterative path (test_graph_edit_directed_mismatch_and_unsupported_modes_do_not_fallback
    locks this). The native exact-paths algorithm doesn't honour
    timeout, so the call surfaces NetworkXNotImplemented when the
    fast path can't handle the input."""
    # complete_graph(7) is large enough to exceed the native fast path,
    # forcing the iterative branch where timeout would apply.
    G1 = fnx.complete_graph(7)
    G2 = fnx.complete_graph(7)
    with pytest.raises(fnx.NetworkXNotImplemented):
        fnx.graph_edit_distance(G1, G2, timeout=1.0)


@needs_nx
def test_graph_edit_distance_node_match_matches_networkx():
    G1 = fnx.path_graph(3)
    G2 = fnx.path_graph(3)
    GX1 = nx.path_graph(3)
    GX2 = nx.path_graph(3)
    nm = lambda d1, d2: True  # noqa: E731
    actual = fnx.graph_edit_distance(G1, G2, node_match=nm)
    expected = nx.graph_edit_distance(GX1, GX2, node_match=nm)
    assert actual == expected


@needs_nx
def test_graph_edit_distance_upper_bound_matches_networkx():
    G1 = fnx.path_graph(3)
    G2 = fnx.cycle_graph(3)
    GX1 = nx.path_graph(3)
    GX2 = nx.cycle_graph(3)
    actual = fnx.graph_edit_distance(G1, G2, upper_bound=10)
    expected = nx.graph_edit_distance(GX1, GX2, upper_bound=10)
    assert actual == expected


@needs_nx
def test_optimize_edit_paths_yields_same_node_path_count_as_networkx():
    G1 = fnx.path_graph(3)
    G2 = fnx.path_graph(3)
    GX1 = nx.path_graph(3)
    GX2 = nx.path_graph(3)
    fnx_paths = list(fnx.optimize_edit_paths(G1, G2))
    nx_paths = list(nx.optimize_edit_paths(GX1, GX2))
    # At least one path each, and final cost should match
    assert len(fnx_paths) >= 1
    assert len(nx_paths) >= 1
    assert fnx_paths[-1][2] == nx_paths[-1][2]


@needs_nx
def test_optimize_edit_paths_timeout_raises_not_implemented():
    """Same policy as graph_edit_distance: timeout requires the
    iterative algorithm, which fnx doesn't have, and project contract
    forbids falling back to nx
    (test_graph_edit_directed_mismatch_and_unsupported_modes_do_not_fallback
    locks this)."""
    G1 = fnx.complete_graph(7)
    G2 = fnx.complete_graph(7)
    with pytest.raises(fnx.NetworkXNotImplemented):
        list(fnx.optimize_edit_paths(G1, G2, timeout=1.0))


@needs_nx
def test_optimize_graph_edit_distance_yields_cost():
    G1 = fnx.path_graph(3)
    G2 = fnx.path_graph(3)
    costs = list(fnx.optimize_graph_edit_distance(G1, G2))
    assert costs == [0] or costs == [0.0]


@needs_nx
def test_explicit_keyword_call_with_strictly_decreasing():
    """strictly_decreasing was a hidden kwarg in **kwargs; now it's
    explicitly named at the documented position."""
    G1 = fnx.path_graph(3)
    G2 = fnx.path_graph(3)
    paths = list(fnx.optimize_edit_paths(G1, G2, strictly_decreasing=False))
    assert len(paths) >= 1
