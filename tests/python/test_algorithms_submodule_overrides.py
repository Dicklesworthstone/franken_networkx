"""``fnx.algorithms.{community,connectivity,isomorphism}`` are fnx submodules.

These three submodules have native fnx implementations
(``fnx.community`` / ``fnx.connectivity`` / ``fnx.isomorphism``) but were
missing from the algorithms-package override set, so
``fnx.algorithms.connectivity`` resolved to networkx's. They now map to the
fnx submodules like the other 60+ overrides — so the doubly-nested
``from fnx.algorithms.connectivity import node_connectivity`` path is native
too (and carries the cqlms/ebd8d local-connectivity fixes).

br-r37-c1-nhbni
"""

from __future__ import annotations

import networkx as nx
import franken_networkx as fnx
import franken_networkx.algorithms as fnx_algorithms


def test_overridden_submodules_are_fnx():
    for name in ("community", "connectivity", "isomorphism"):
        assert getattr(fnx_algorithms, name) is getattr(fnx, name)
        assert getattr(fnx_algorithms, name) is not getattr(nx.algorithms, name)


def test_doubly_nested_connectivity_is_native_with_cqlms_fix():
    from franken_networkx.algorithms.connectivity import node_connectivity

    assert node_connectivity is not nx.node_connectivity
    # The cqlms fix flows through: adjacent local connectivity in K5 is 4.
    assert node_connectivity(fnx.complete_graph(5), 0, 4) == 4
    assert node_connectivity(fnx.complete_graph(5)) == nx.node_connectivity(
        nx.complete_graph(5)
    )


def test_doubly_nested_isomorphism_is_native():
    import franken_networkx.algorithms.isomorphism as fnx_iso

    assert fnx_iso is fnx.isomorphism
    # is_isomorphic resolves and works through the nested path.
    g = fnx.complete_graph(4)
    h = fnx.complete_graph(4)
    assert fnx.is_isomorphic(g, h)
