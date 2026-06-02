"""Regression: current_flow_closeness_centrality / information_centrality must
return Python ``float`` dict values, not ``np.float64``.

The implementation builds the result from a numpy array
(``1.0 / centrality_arr[i]``), which yields ``np.float64``. networkx returns
Python ``float``. While ``np.float64`` subclasses ``float`` (so isinstance
checks pass), ``type(v) is float`` fails and ``repr`` differs
(``np.float64(...)``), breaking strict type/representation parity.
current_flow_betweenness_centrality already coerced to float; this aligns the
closeness variant. (br-r37-c1-cfctype)
"""

import networkx as nx
import franken_networkx as fnx

import pytest


def _graph(mod, weighted=False):
    g = mod.Graph()
    edges = [(0, 1, 1.0), (1, 2, 2.0), (2, 3, 1.0), (3, 0, 2.0), (0, 2, 1.0), (2, 4, 3.0)]
    for u, v, w in edges:
        if weighted:
            g.add_edge(u, v, weight=w)
        else:
            g.add_edge(u, v)
    return g


@pytest.mark.parametrize("name", ["current_flow_closeness_centrality", "information_centrality"])
@pytest.mark.parametrize("weighted", [False, True])
def test_returns_python_float_matching_networkx(name, weighted):
    nx_fn, fnx_fn = getattr(nx, name), getattr(fnx, name)
    kwargs = {"weight": "weight"} if weighted else {}
    rn = nx_fn(_graph(nx, weighted), **kwargs)
    rf = fnx_fn(_graph(fnx, weighted), **kwargs)
    assert set(rn) == set(rf)
    for k in rn:
        # exact Python float type, matching nx (not np.float64)
        assert type(rf[k]) is type(rn[k]) is float, f"node {k}: {type(rf[k]).__name__}"
        assert abs(rf[k] - rn[k]) <= 1e-9


def test_result_is_json_serializable_with_native_float():
    import json
    r = fnx.current_flow_closeness_centrality(_graph(fnx))
    # all values are plain float -> standard json (no numpy) round-trips
    assert all(type(v) is float for v in r.values())
    assert json.loads(json.dumps(r))
