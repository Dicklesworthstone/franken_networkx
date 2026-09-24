"""to_numpy_array hands edge values to numpy exactly as networkx does.

br-r37-c1-rc0923-epic-silent-wrong-answers-nro4w.6. The native COO builders
return float64 and substituted the unit default for any weight that is not a
real number, whatever dtype the caller asked for: a complex weight came out as
1+0j, a big int lost precision under dtype=object, structured dtypes read
(1, 1), and a non-numeric weight gave 1.0 where networkx raises (or, for None,
gives nan). networkx builds the array with numpy advanced-index assignment of
the attribute values, so numpy decides every conversion and error.
"""

from __future__ import annotations

import networkx as nx
import numpy as np
import pytest

import franken_networkx as fnx

CLASSES = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]
WEIGHTS = {
    "int": 3,
    "float": 2.5,
    "bool": True,
    "complex": 1 + 2j,
    "big_int": 922337203685477580102,
    "none": None,
    "numeric_str": "3.5",
    "str": "abc",
    "list": [1, 2],
    "nan": float("nan"),
}
DTYPES = {"default": None, "float": float, "int": int, "complex": complex, "object": object}


def _outcome(module, cls, weight_value, dtype, weight="weight"):
    G = getattr(module, cls)()
    G.add_edge(0, 1, weight=weight_value)
    G.add_edge(1, 2)  # no weight attribute: networkx's default is 1.0
    G.add_node(3)
    try:
        A = module.to_numpy_array(G, dtype=dtype, weight=weight)
    except Exception as exc:  # compared by type only; numpy owns the message
        return ("raised", type(exc).__name__)
    return ("ok", str(A.dtype), repr(A.tolist()))


@pytest.mark.filterwarnings("ignore")
@pytest.mark.parametrize("cls", CLASSES)
@pytest.mark.parametrize("dtype", sorted(DTYPES))
@pytest.mark.parametrize("value", sorted(WEIGHTS))
def test_weight_value_and_dtype_parity(cls, dtype, value):
    want = _outcome(nx, cls, WEIGHTS[value], DTYPES[dtype])
    got = _outcome(fnx, cls, WEIGHTS[value], DTYPES[dtype])
    assert got == want


@pytest.mark.parametrize("cls", ["Graph", "DiGraph"])
def test_structured_dtype_reads_each_field_like_networkx(cls):
    dtype = np.dtype([("weight", int), ("cost", float)])
    graphs = []
    for module in (nx, fnx):
        G = getattr(module, cls)()
        G.add_edge(0, 1, weight=10)
        G.add_edge(1, 2, cost=5)
        G.add_edge(2, 3, weight=3, cost=-4.0)
        graphs.append(module.to_numpy_array(G, dtype=dtype, weight=None))
    want, got = graphs
    assert got.dtype == want.dtype
    for field in dtype.names:
        np.testing.assert_array_equal(got[field], want[field])


@pytest.mark.parametrize("cls", CLASSES)
def test_structured_dtype_errors_match_networkx(cls):
    dtype = np.dtype([("weight", int), ("cost", int)])
    for weight in ("weight", None):
        outcomes = []
        for module in (nx, fnx):
            G = getattr(module, cls)()
            G.add_edge(0, 1, weight=1, cost=2)
            try:
                A = module.to_numpy_array(G, dtype=dtype, weight=weight)
                outcomes.append(("ok", repr(A.tolist())))
            except Exception as exc:
                outcomes.append(("raised", type(exc).__name__, str(exc)))
        assert outcomes[1] == outcomes[0], (cls, weight)


def test_edgeless_structured_request_returns_the_filled_array_like_networkx():
    dtype = np.dtype([("weight", int), ("cost", int)])
    for module in (nx, fnx):
        G = module.Graph()
        G.add_nodes_from([0, 1])
        A = module.to_numpy_array(G, dtype=dtype, weight="weight")  # no error: no edges
        assert A.shape == (2, 2)


def test_float_weights_still_take_the_native_path(monkeypatch):
    """The fail-closed change must not push the common case off the fast path."""
    import franken_networkx as package

    calls = []
    real = package._native_adjacency_arrays

    def counting(*args, **kwargs):
        calls.append(1)
        return real(*args, **kwargs)

    monkeypatch.setattr(package, "_native_adjacency_arrays", counting)
    G = fnx.Graph()
    G.add_weighted_edges_from([(0, 1, 2.0), (1, 2, 3.5)])
    A = fnx.to_numpy_array(G)
    assert calls and A[0, 1] == 2.0
