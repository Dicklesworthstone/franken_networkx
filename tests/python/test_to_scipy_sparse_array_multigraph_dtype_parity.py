"""to_scipy_sparse_array must preserve networkx's dtype on multigraphs.

br-r37-c1-p80x1. Found by a systematic f(G) divergence sweep of the public surface
(445 functions x 4 classes x 3 seeds). networkx returns float64 whenever the weight
attribute holds a FLOAT, even when that float is integral-valued; fnx's multigraph fast
path returns int64 in exactly that case.

    class          weights            fnx        nx
    MultiGraph     2.0, 3.0           int64      float64      <- diverges
    MultiDiGraph   2.0, 3.0           int64      float64      <- diverges
    MultiGraph     2, 3               agree
    MultiGraph     2.5, 0.25          agree (float64)
    MultiGraph     no weight attr     agree
    Graph/DiGraph  every case         agree

The VALUES are equal - this is not a truncation bug, and non-integral weights are handled
correctly - but the dtype is wrong, which matters for drop-in code that inspects `.dtype`,
feeds the array to a scipy routine with a dtype expectation, or relies on float semantics
downstream (later division, NaN propagation).

CAUSE, from python/franken_networkx/__init__.py: the multigraph fast path reads
`data_is_int` from the native CSR kernel and picks
`_np.int64 if data_is_int else _np.float64`. The kernel decides that from the summed
VALUES being integral, whereas networkx decides from the source weight's TYPE. Repairing it
properly means changing what the kernel reports, which is a Rust change; a Python-side
repair would need an O(|E|) scan of the weights and would cost the fast path its reason to
exist.

MARKED xfail(strict=True) DELIBERATELY: the tree stays green, and the day the kernel is
fixed this test fails as XPASS and forces the marker off, rather than silently passing and
leaving a stale xfail behind.
"""

import networkx as nx
import pytest

import franken_networkx as fnx


def _build(module, cls, weights):
    graph = getattr(module, cls)()
    if weights is None:
        graph.add_edge(0, 1)
        graph.add_edge(1, 2)
    else:
        graph.add_edge(0, 1, weight=weights[0])
        graph.add_edge(1, 2, weight=weights[1])
    return graph


@pytest.mark.parametrize("cls", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize(
    ("label", "weights"),
    [("int", (2, 3)), ("float_fractional", (2.5, 0.25)), ("absent", None)],
)
def test_dtype_matches_networkx(cls, label, weights):
    """The cases that already agree - a guard against regressing them while fixing the one below."""
    got = fnx.to_scipy_sparse_array(_build(fnx, cls, weights))
    expected = nx.to_scipy_sparse_array(_build(nx, cls, weights))
    assert got.dtype == expected.dtype, f"{cls}/{label}"
    assert (got.toarray() == expected.toarray()).all(), f"{cls}/{label}"


@pytest.mark.parametrize("cls", ["MultiGraph", "MultiDiGraph"])
@pytest.mark.xfail(
    strict=True,
    reason="br-r37-c1-p80x1: the multigraph CSR kernel reports data_is_int from the summed "
    "VALUES, so integral-valued FLOAT weights yield int64 where networkx yields float64. "
    "Fixing it means changing what the kernel reports (Rust); a Python-side repair would "
    "need an O(|E|) weight scan and would cost the fast path its purpose.",
)
def test_integral_float_weights_keep_float_dtype(cls):
    got = fnx.to_scipy_sparse_array(_build(fnx, cls, (2.0, 3.0)))
    expected = nx.to_scipy_sparse_array(_build(nx, cls, (2.0, 3.0)))
    # Values already agree; it is the dtype that diverges.
    assert (got.toarray() == expected.toarray()).all()
    assert got.dtype == expected.dtype
