"""br-r37-c1-ewtd1 + ft8c0: ctor edge-list contract parity.

ewtd1: nx iterates str/bytes edge-list ITEMS as 2/3-char specs
       (['ab','cd'] -> edges (a,b),(c,d); [b'xy'] -> (120,121)).
ft8c0: a NON-multigraph 3-tuple's third element is the data dict; a
       non-dict third makes the input invalid (nx datadict.update
       raises). For multigraphs the third element is the edge KEY.
"""

import networkx as nx
import pytest

import franken_networkx as fnx


def _run(mod, cls, data):
    try:
        g = getattr(mod, cls)(data)
        keys = g.is_multigraph()
        edges = g.edges(keys=True) if keys else g.edges()
        return (
            "OK",
            sorted((repr(u), repr(v)) for u, v, *_ in edges),
            sorted(map(repr, g.nodes())),
        )
    except Exception as e:  # noqa: BLE001
        return ("ERR", type(e).__name__)


CASES = [
    ("Graph", ["ab", "cd"]),
    ("Graph", [b"xy"]),
    ("Graph", ["abc"]),
    ("Graph", ["ab", "cde"]),
    ("Graph", [(1, 2, 3)]),
    ("Graph", [(1, 2, "x")]),
    ("Graph", [(1, 2, {"w": 1})]),
    ("Graph", [(0, 1), (1, 2)]),
    ("Graph", [[0, 1], [1, 2]]),
    ("DiGraph", ["ab"]),
    ("DiGraph", [(1, 2, 3)]),
    ("MultiGraph", [(1, 2, 3)]),
    ("MultiGraph", [(1, 2, "k")]),
    ("MultiGraph", ["ab"]),
    ("MultiGraph", [(1, 2, 3, {"w": 1})]),
    ("MultiGraph", [(1, 2, 3, 4)]),
    ("MultiDiGraph", ["ab", "cd"]),
]


@pytest.mark.parametrize("cls,data", CASES)
def test_ctor_edge_list_contract_matches_nx(cls, data):
    assert _run(fnx, cls, data) == _run(nx, cls, data), (cls, data)
