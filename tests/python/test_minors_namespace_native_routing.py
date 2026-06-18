"""``franken_networkx.minors.equivalence_classes`` routes to the fnx native.

``from networkx.algorithms.minors import *`` left ``equivalence_classes``
bound to networkx's implementation instead of fnx's native version.

br-r37-c1-2qsqf
"""

from __future__ import annotations

import networkx as nx
import franken_networkx as fnx
from franken_networkx import minors as fnx_minors


def test_equivalence_classes_is_not_networkx_version():
    assert fnx_minors.equivalence_classes is not nx.equivalence_classes


def test_equivalence_classes_values_match_networkx():
    def same_parity(a, b):
        return (a % 2) == (b % 2)

    fnx_result = sorted(map(sorted, fnx_minors.equivalence_classes(range(8), same_parity)))
    nx_result = sorted(map(sorted, nx.equivalence_classes(range(8), same_parity)))
    assert fnx_result == nx_result

    def same_mod3(a, b):
        return (a % 3) == (b % 3)

    assert sorted(map(sorted, fnx_minors.equivalence_classes(range(9), same_mod3))) == (
        sorted(map(sorted, nx.equivalence_classes(range(9), same_mod3)))
    )
