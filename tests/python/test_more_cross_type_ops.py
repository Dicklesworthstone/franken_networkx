"""br-r37-c1-9rd4z: regression — fnx.power, fnx.vf2pp_is_isomorphic,
fnx.vf2pp_isomorphism, fnx.vf2pp_all_isomorphisms must accept nx graph
args via boundary coercion.

Continues the cross-type sweep from br-r37-c1-i2uub (union) and
br-r37-c1-jwdzp (difference / iso family / GED).
"""

from __future__ import annotations

import pytest

import franken_networkx as fnx

try:
    import networkx as nx

    HAS_NX = True
except ImportError:
    HAS_NX = False


needs_nx = pytest.mark.skipif(not HAS_NX, reason="networkx not installed")


@needs_nx
def test_power_accepts_nx_graph():
    ng = nx.path_graph(3)
    result = fnx.power(ng, 2)
    assert sorted(result.edges()) == [(0, 1), (0, 2), (1, 2)]


@needs_nx
def test_vf2pp_is_isomorphic_accepts_nx_graph():
    ng = nx.path_graph(3)
    fg = fnx.path_graph(3)
    assert fnx.vf2pp_is_isomorphic(ng, fg) is True
    assert fnx.vf2pp_is_isomorphic(fg, ng) is True
    assert fnx.vf2pp_is_isomorphic(ng, ng) is True


@needs_nx
def test_vf2pp_isomorphism_accepts_nx_graph():
    ng = nx.path_graph(3)
    fg = fnx.path_graph(3)
    mapping = fnx.vf2pp_isomorphism(ng, fg)
    assert isinstance(mapping, dict)
    assert len(mapping) == 3


@needs_nx
def test_vf2pp_all_isomorphisms_accepts_nx_graph():
    ng = nx.path_graph(3)
    fg = fnx.path_graph(3)
    mappings = list(fnx.vf2pp_all_isomorphisms(ng, fg))
    # path_3 has 2 isomorphisms (identity and reversal)
    assert len(mappings) == 2


@needs_nx
def test_power_directed_unsupported_still_raises():
    """Negative-path: power on directed graph still raises (the coercion
    must not mask the algorithm precondition)."""
    ng = nx.DiGraph([(0, 1), (1, 2)])
    with pytest.raises(fnx.NetworkXNotImplemented):
        fnx.power(ng, 2)


@needs_nx
def test_power_no_regression_fnx_input():
    """Same-type call still works."""
    fg = fnx.path_graph(3)
    result = fnx.power(fg, 2)
    assert sorted(result.edges()) == [(0, 1), (0, 2), (1, 2)]
