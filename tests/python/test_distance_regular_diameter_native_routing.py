"""Differential parity for ``franken_networkx.distance_regular.diameter``.

This namespace re-exports the general ``diameter`` (via its ``__getattr__``
fallback to networkx). Native routing was deferred here because the module
is imported during package init and its attribute resolution makes
submodule-level routing unreliable (same class as the ``convert``
namespace, 2qsqf). The values still match networkx, which this pins.

br-r37-c1-2qsqf
"""

from __future__ import annotations

import pytest
import networkx as nx
import franken_networkx as fnx
from franken_networkx import distance_regular as fnx_dr


@pytest.mark.parametrize("builder,expected", [
    (lambda lib: lib.cycle_graph(6), 3),
    (lambda lib: lib.path_graph(5), 4),
    (lambda lib: lib.complete_graph(5), 1),
    (lambda lib: lib.petersen_graph(), 2),
    (lambda lib: lib.complete_bipartite_graph(3, 3), 2),
])
def test_diameter_values_match_networkx(builder, expected):
    assert fnx_dr.diameter(builder(fnx)) == expected
    assert fnx_dr.diameter(builder(fnx)) == nx.diameter(builder(nx))
