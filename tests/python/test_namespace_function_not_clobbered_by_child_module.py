"""Guard: namespace FUNCTIONS aren't clobbered by same-named child modules.

When the algorithms package aliases a submodule's child modules into the fnx
submodule (``_alias_nx_child_modules``), a child MODULE whose name matches a
FUNCTION the submodule exposes can overwrite the function (``setattr(parent,
name, module)``), making ``fnx.<sub>.<fn>`` an un-callable module. This bit
``fnx.isomorphism.tree_isomorphism`` (br-r37-c1-nhbni). These names are the
ones at risk (networkx exposes a function AND ships a same-named child
module); they must stay callable functions, not modules.

br-r37-c1-nhbni
"""

from __future__ import annotations

import inspect

import pytest
import networkx as nx
import franken_networkx as fnx
from franken_networkx import isomorphism as fnx_isomorphism
from franken_networkx import centrality as fnx_centrality


@pytest.mark.parametrize("module,name", [
    (fnx_isomorphism, "tree_isomorphism"),
    (fnx_centrality, "dispersion"),
])
def test_namespace_function_stays_callable(module, name):
    obj = getattr(module, name)
    assert callable(obj), f"{name} should be a function"
    assert not inspect.ismodule(obj), f"{name} was clobbered by a child module"


def test_tree_isomorphism_works_and_matches_networkx():
    # Two isomorphic 3-node paths.
    t1 = fnx.Graph([(0, 1), (1, 2)])
    t2 = fnx.Graph([("a", "b"), ("b", "c")])
    result = fnx_isomorphism.tree_isomorphism(t1, t2)
    nresult = nx.isomorphism.tree_isomorphism(
        nx.Graph([(0, 1), (1, 2)]), nx.Graph([("a", "b"), ("b", "c")])
    )
    # Both return a (possibly empty) list of node-pair mappings; non-empty here.
    assert bool(result) == bool(nresult)


def test_dispersion_works_and_matches_networkx():
    g = fnx.Graph([(0, 1), (1, 2), (2, 0), (2, 3), (3, 4), (4, 2)])
    ng = nx.Graph(list(g.edges()))
    assert fnx_centrality.dispersion(g, 0, 2) == pytest.approx(
        nx.dispersion(ng, 0, 2)
    )
