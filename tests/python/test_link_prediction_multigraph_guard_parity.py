"""Parity for link-prediction soundarajan_hopcroft / within_inter_cluster
on multigraph and directed inputs.

Bead br-r37-c1-fa5tf. Three link-prediction functions raised
``NetworkXAlgorithmError('No community information available for
Node 1')`` on multigraph input — masking the real issue. nx is
decorated with ``@not_implemented_for('directed', 'multigraph')``
and raises ``NetworkXNotImplemented`` first, before any community-
attribute lookup.

This is a follow-up to br-r37-c1-tqimg which scoped these out
because the existing fnx wrappers fell through to a per-node
community check before any type guard.

Affected functions:
- ``cn_soundarajan_hopcroft``
- ``ra_index_soundarajan_hopcroft``
- ``within_inter_cluster``
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


LP_FNS = [
    "cn_soundarajan_hopcroft",
    "ra_index_soundarajan_hopcroft",
    "within_inter_cluster",
]


# ---------------------------------------------------------------------------
# Eager raise on multigraph / directed inputs
# ---------------------------------------------------------------------------

@needs_nx
@pytest.mark.parametrize("fn_name", LP_FNS)
@pytest.mark.parametrize("cls_name", ["MultiGraph", "MultiDiGraph"])
def test_multigraph_raises_eagerly(fn_name, cls_name):
    """Type check fires on call (not on iteration). nx's argmap
    decorator runs synchronously, so calling ``fn(G)`` on a
    MultiGraph raises immediately, before any iteration."""
    G = getattr(fnx, cls_name)([(1, 2), (2, 3)])
    GX = getattr(nx, cls_name)([(1, 2), (2, 3)])
    with pytest.raises(
        fnx.NetworkXNotImplemented,
        match=r"not implemented for multigraph type",
    ):
        # The call itself must raise — don't iterate.
        getattr(fnx, fn_name)(G)
    with pytest.raises(
        nx.NetworkXNotImplemented,
        match=r"not implemented for multigraph type",
    ):
        getattr(nx, fn_name)(GX)


@needs_nx
@pytest.mark.parametrize("fn_name", LP_FNS)
def test_digraph_raises_directed(fn_name):
    G = fnx.DiGraph([(1, 2), (2, 3)])
    GX = nx.DiGraph([(1, 2), (2, 3)])
    with pytest.raises(
        fnx.NetworkXNotImplemented,
        match=r"not implemented for directed type",
    ):
        getattr(fnx, fn_name)(G)
    with pytest.raises(
        nx.NetworkXNotImplemented,
        match=r"not implemented for directed type",
    ):
        getattr(nx, fn_name)(GX)


# ---------------------------------------------------------------------------
# Cross-class catching
# ---------------------------------------------------------------------------

@needs_nx
def test_multigraph_caught_by_nx_class():
    """Drop-in: a fnx-raised NetworkXNotImplemented must be
    catchable via ``except nx.NetworkXNotImplemented``."""
    G = fnx.MultiGraph([(1, 2)])
    try:
        fnx.cn_soundarajan_hopcroft(G)
    except nx.NetworkXNotImplemented:
        return
    pytest.fail(
        "fnx.cn_soundarajan_hopcroft should raise NetworkXNotImplemented "
        "on MultiGraph"
    )


# ---------------------------------------------------------------------------
# Regression: simple Graph behavior unchanged
# ---------------------------------------------------------------------------

@needs_nx
def test_simple_graph_unchanged():
    """The community-attribute-aware path must continue to work for
    simple Graph inputs with community attrs set."""
    G = fnx.Graph([(1, 2), (2, 3), (3, 4)])
    GX = nx.Graph([(1, 2), (2, 3), (3, 4)])
    for n in (1, 2):
        G.nodes[n]["community"] = 0
        GX.nodes[n]["community"] = 0
    for n in (3, 4):
        G.nodes[n]["community"] = 1
        GX.nodes[n]["community"] = 1

    # cn_soundarajan_hopcroft: same output as nx
    f = sorted(
        [(u, v, round(s, 4)) for u, v, s in fnx.cn_soundarajan_hopcroft(G, [(1, 3)])]
    )
    n = sorted(
        [(u, v, round(s, 4)) for u, v, s in nx.cn_soundarajan_hopcroft(GX, [(1, 3)])]
    )
    assert f == n

    # within_inter_cluster: same output
    f = sorted(
        [(u, v, round(s, 4)) for u, v, s in fnx.within_inter_cluster(G, [(1, 3)])]
    )
    n = sorted(
        [(u, v, round(s, 4)) for u, v, s in nx.within_inter_cluster(GX, [(1, 3)])]
    )
    assert f == n


@needs_nx
def test_within_inter_cluster_negative_delta_raises_algorithm_error():
    """``delta <= 0`` raises ``NetworkXAlgorithmError`` (not
    ``NetworkXError``) — matching nx exactly. Pre-fix fnx raised the
    plain ``NetworkXError`` parent class. Drop-in code that catches
    ``NetworkXAlgorithmError`` would not trigger on the parent."""
    G = fnx.Graph([(1, 2)])
    GX = nx.Graph([(1, 2)])
    with pytest.raises(
        fnx.NetworkXAlgorithmError, match=r"Delta must be greater than zero"
    ):
        fnx.within_inter_cluster(G, delta=0)
    with pytest.raises(
        nx.NetworkXAlgorithmError, match=r"Delta must be greater than zero"
    ):
        nx.within_inter_cluster(GX, delta=0)


@needs_nx
def test_multigraph_short_circuits_before_negative_delta_check():
    """Drop-in: when both delta <= 0 AND multigraph, the multigraph
    guard must fire FIRST (matching nx's argmap-decorator order)."""
    G = fnx.MultiGraph([(1, 2)])
    GX = nx.MultiGraph([(1, 2)])
    with pytest.raises(fnx.NetworkXNotImplemented, match=r"multigraph"):
        fnx.within_inter_cluster(G, delta=-1)
    with pytest.raises(nx.NetworkXNotImplemented, match=r"multigraph"):
        nx.within_inter_cluster(GX, delta=-1)
