"""Parity coverage for cycle_basis on multigraph inputs.

Bead franken_networkx-ebmj: cycle_basis must raise
NetworkXNotImplemented on MultiGraph / MultiDiGraph inputs, matching
upstream NetworkX, instead of silently returning an empty list.
"""

import networkx as nx
import pytest

import franken_networkx as fnx


@pytest.mark.parametrize(
    ("fnx_ctor", "nx_ctor"),
    [
        (fnx.MultiGraph, nx.MultiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_cycle_basis_multigraph_raises_networkx_not_implemented(fnx_ctor, nx_ctor):
    fg = fnx_ctor()
    fg.add_edge(0, 1)
    fg.add_edge(1, 2)
    ng = nx_ctor()
    ng.add_edge(0, 1)
    ng.add_edge(1, 2)

    err_types = []
    for cls_name in ("NetworkXNotImplemented", "NetworkXError"):
        for mod in (fnx, nx):
            cls = getattr(mod, cls_name, None)
            if cls is not None:
                err_types.append(cls)
    err_tuple = tuple(err_types)

    with pytest.raises(err_tuple, match="multigraph"):
        fnx.cycle_basis(fg)
    with pytest.raises(err_tuple, match="multigraph"):
        nx.cycle_basis(ng)


def test_cycle_basis_simple_graph_still_works():
    """br-r37-c1-j5swc: cycle node ordering now matches nx's
    DFS-discovery order through the chord-completion path, not
    canonical/sorted order. The previous hardcoded [[0,1,2,3]]
    assertion described the old canonical-output contract — assert
    on the cycle's *node set* and basis cardinality so this stays
    robust to nx's algorithm-specific ordering."""
    g = fnx.cycle_graph(4)
    basis = fnx.cycle_basis(g)
    assert len(basis) == 1
    assert set(basis[0]) == {0, 1, 2, 3}
    # root kwarg still routes through.
    rooted = fnx.cycle_basis(g, 0)
    assert len(rooted) == 1
    assert set(rooted[0]) == {0, 1, 2, 3}
