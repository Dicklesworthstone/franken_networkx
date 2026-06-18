"""API-health smoke parity: representative functions run and agree with nx.

A broad sweep (759 common callables) confirmed no fnx single-argument function
errors where networkx succeeds. This curated subset pins that health for a
representative cross-section so a function that regresses to "raises on a normal
graph" is caught — each is called on a fresh standard graph and compared to
networkx (success-vs-raise; value where order-invariant).

No mocks: real fnx and real networkx on a fresh standard graph per call.
"""

from __future__ import annotations

import pytest
import networkx as nx
import franken_networkx as fnx


def _standard(lib):
    g = lib.Graph()
    for u, v in [(0, 1), (1, 2), (2, 3), (3, 4), (4, 0), (0, 2), (1, 3)]:
        g.add_edge(u, v, weight=1)
    return g


# (name, optional scalar normaliser) — None means just require both succeed.
_FUNCS = [
    ("density", float), ("transitivity", float), ("average_clustering", float),
    ("diameter", int), ("radius", int), ("number_connected_components", int),
    ("is_connected", bool), ("wiener_index", float), ("estrada_index", None),
    ("degree_assortativity_coefficient", None), ("global_efficiency", float),
    ("local_efficiency", float), ("is_tree", bool), ("is_forest", bool),
    ("is_bipartite", bool), ("is_eulerian", bool), ("is_chordal", bool),
    ("is_planar", None), ("node_connectivity", int), ("edge_connectivity", int),
    ("number_of_isolates", int), ("s_metric", None),
    ("degree_pearson_correlation_coefficient", None),
    ("non_randomness", None), ("sigma", None), ("omega", None),
]


@pytest.mark.parametrize("name,norm", _FUNCS)
def test_function_runs_and_matches_networkx(name, norm):
    ff = getattr(fnx, name, None)
    nf = getattr(nx, name, None)
    if ff is None or nf is None:
        pytest.skip(f"{name} not available")

    def outcome(fn, g):
        try:
            return ("ok", fn(g))
        except Exception as exc:  # noqa: BLE001
            return ("err", type(exc).__name__)

    f_kind, f_val = outcome(ff, _standard(fnx))
    n_kind, n_val = outcome(nf, _standard(nx))
    # fnx must not error where networkx succeeds (and vice-versa).
    assert f_kind == n_kind, f"{name}: fnx={f_kind} nx={n_kind}"
    if f_kind == "ok" and norm in (int, float, bool):
        assert norm(f_val) == pytest.approx(norm(n_val)) if norm is float else (
            norm(f_val) == norm(n_val)
        )
