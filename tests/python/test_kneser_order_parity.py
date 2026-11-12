"""br-r37-c1-jv0h5: kneser_graph node/edge insertion-order parity vs nx.

fnx now replicates nx's construction verbatim: node order is
edge-DISCOVERY order (s in combinations order, t from combinations over
the CPython set difference), with the 2k > n pre-add for graphs that may
have isolated nodes.
"""

import networkx as nx
import pytest

import franken_networkx as fnx


def _canon(g):
    return (
        [repr(n) for n in g],
        [(repr(u), repr(v)) for u, v in g.edges()],
        {repr(x): [repr(y) for y in g[x]] for x in g},
    )


@pytest.mark.parametrize(
    "n,k",
    [(1, 1), (2, 1), (3, 1), (3, 2), (4, 2), (5, 2), (6, 2), (6, 3),
     (7, 3), (8, 3), (8, 4), (9, 4), (5, 4), (4, 3), (2, 2)],
)
def test_full_order_parity(n, k):
    assert _canon(fnx.kneser_graph(n, k)) == _canon(nx.kneser_graph(n, k))


def test_petersen_identity():
    g = fnx.kneser_graph(5, 2)
    assert g.number_of_nodes() == 10 and g.number_of_edges() == 15


@pytest.mark.parametrize("n,k", [(0, 1), (-1, 1), (3, 0), (3, 4)])
def test_error_parity(n, k):
    with pytest.raises(Exception) as nx_err:
        nx.kneser_graph(n, k)
    with pytest.raises(Exception) as fnx_err:
        fnx.kneser_graph(n, k)
    assert type(fnx_err.value).__name__ == type(nx_err.value).__name__
    assert str(fnx_err.value) == str(nx_err.value)
