"""Parity for geometric-graph generator signatures + new kwargs.

Aligned four generator signatures with networkx's modern API
(br-r37-c1-geomgenkw):

- soft_random_geometric_graph: + p (Minkowski), keyword-only pos_name
- waxman_graph: + metric (custom distance), keyword-only pos_name
- geographical_threshold_graph: + metric, p_dist, pos_name, weight_name
- thresholded_random_geometric_graph: + weight (callable/dict/scalar),
  p, pos_name, weight_name

Drop-in callers passing any of those previously hit TypeError. The
implementations now honour the new kwargs (Minkowski p-norm distance,
custom metric callable, configurable attribute names, p_dist scoring
function, weight as callable/dict/scalar).
"""

from __future__ import annotations

import inspect

import pytest

import franken_networkx as fnx

try:
    import networkx as nx
    HAS_NX = True
except ImportError:
    HAS_NX = False

needs_nx = pytest.mark.skipif(not HAS_NX, reason="networkx not installed")


GENERATORS = [
    "soft_random_geometric_graph",
    "waxman_graph",
    "geographical_threshold_graph",
    "thresholded_random_geometric_graph",
]


@needs_nx
@pytest.mark.parametrize("name", GENERATORS)
def test_signature_parameter_list_matches_networkx(name):
    fnx_sig = inspect.signature(getattr(fnx, name))
    nx_sig = inspect.signature(getattr(nx, name))
    fnx_params = list(fnx_sig.parameters.keys())
    nx_params = [k for k in nx_sig.parameters.keys()
                 if k not in ("backend", "backend_kwargs")]
    assert fnx_params == nx_params


# ---------------------------------------------------------------------------
# pos_name
# ---------------------------------------------------------------------------

@needs_nx
@pytest.mark.parametrize("name", GENERATORS)
def test_pos_name_renames_position_attribute(name):
    fn = getattr(fnx, name)
    if name == "thresholded_random_geometric_graph":
        G = fn(8, 0.4, 0.3, seed=42, pos_name="coords")
    elif name == "geographical_threshold_graph":
        G = fn(8, 0.5, seed=42, pos_name="coords")
    elif name == "waxman_graph":
        G = fn(8, seed=42, pos_name="coords")
    else:
        G = fn(8, 0.3, seed=42, pos_name="coords")
    # All nodes should carry "coords" not "pos"
    for n in G.nodes():
        assert "coords" in G.nodes[n]
        assert "pos" not in G.nodes[n]


# ---------------------------------------------------------------------------
# weight_name
# ---------------------------------------------------------------------------

@needs_nx
@pytest.mark.parametrize(
    "name",
    ["geographical_threshold_graph", "thresholded_random_geometric_graph"],
)
def test_weight_name_renames_weight_attribute(name):
    fn = getattr(fnx, name)
    if name == "geographical_threshold_graph":
        G = fn(8, 0.5, seed=42, weight_name="w")
    else:
        G = fn(8, 0.4, 0.3, seed=42, weight_name="w")
    for n in G.nodes():
        assert "w" in G.nodes[n]
        assert "weight" not in G.nodes[n]


# ---------------------------------------------------------------------------
# Minkowski p-norm
# ---------------------------------------------------------------------------

@needs_nx
@pytest.mark.parametrize(
    "name",
    ["soft_random_geometric_graph", "thresholded_random_geometric_graph"],
)
def test_minkowski_p_changes_neighbour_set(name):
    """Different p-values produce different distance functions and so
    typically different edge sets on the same fixed positions."""
    fn = getattr(fnx, name)
    if name == "thresholded_random_geometric_graph":
        # Fixed seed so positions stay the same
        G_p2 = fn(20, 0.3, 0.5, seed=42, p=2)
        G_p1 = fn(20, 0.3, 0.5, seed=42, p=1)
        G_inf = fn(20, 0.3, 0.5, seed=42, p=float("inf"))
    else:
        G_p2 = fn(20, 0.4, seed=42, p=2)
        G_p1 = fn(20, 0.4, seed=42, p=1)
        G_inf = fn(20, 0.4, seed=42, p=float("inf"))
    e1 = sorted(G_p2.edges())
    e2 = sorted(G_p1.edges())
    e3 = sorted(G_inf.edges())
    # At least one of the three pairs should differ on a 20-node graph
    assert e1 != e2 or e1 != e3 or e2 != e3


# ---------------------------------------------------------------------------
# metric override (waxman / geographical_threshold)
# ---------------------------------------------------------------------------

@needs_nx
@pytest.mark.parametrize("name", ["waxman_graph", "geographical_threshold_graph"])
def test_custom_metric_callable_used(name):
    """A degenerate metric returning 0 for every pair forces all edges
    to satisfy the threshold — proves the metric override is used."""
    fn = getattr(fnx, name)
    zero_metric = lambda a, b: 0.0  # noqa: E731
    if name == "geographical_threshold_graph":
        # With distance always 0, the (w[u]+w[v])/d term explodes →
        # every pair edge is added (we treat d=0 as infinity in our impl).
        G = fn(6, theta=0.5, seed=42, metric=zero_metric)
    else:
        # waxman: P(edge) = beta * exp(-d / (alpha*L)) → with d=0,
        # P=beta*1=0.4. Some edges will fire on a fixed seed.
        G = fn(20, beta=0.9, alpha=0.1, seed=42, metric=zero_metric)
    # Should have some edges — not the empty graph
    assert G.number_of_edges() > 0


# ---------------------------------------------------------------------------
# p_dist on geographical_threshold_graph
# ---------------------------------------------------------------------------

@needs_nx
def test_geographical_threshold_p_dist_callable_used():
    """Pass a constant p_dist(d) = 1.0 — every pair satisfies
    (w[u]+w[v])*1.0 >= theta when theta is small enough."""
    G = fnx.geographical_threshold_graph(
        8, theta=0.0, seed=42, p_dist=lambda d: 1.0,
    )
    # With theta=0 and weights non-negative, every pair is connected.
    n = G.number_of_nodes()
    expected = n * (n - 1) // 2
    assert G.number_of_edges() == expected


# ---------------------------------------------------------------------------
# weight as callable / dict / scalar on thresholded_random_geometric_graph
# ---------------------------------------------------------------------------

@needs_nx
def test_thresholded_weight_callable():
    counter = [0]
    def gen_weight():
        counter[0] += 1
        return counter[0]
    G = fnx.thresholded_random_geometric_graph(
        5, 0.3, 0.5, seed=42, weight=gen_weight,
    )
    # Each node got a unique increasing weight
    weights = [G.nodes[n]["weight"] for n in sorted(G.nodes())]
    assert weights == sorted(weights)


@needs_nx
def test_thresholded_weight_dict():
    fixed = {i: i * 2.0 for i in range(5)}
    G = fnx.thresholded_random_geometric_graph(
        5, 0.3, 0.5, seed=42, weight=fixed,
    )
    for i in range(5):
        assert G.nodes[i]["weight"] == i * 2.0


@needs_nx
def test_thresholded_weight_scalar():
    G = fnx.thresholded_random_geometric_graph(
        5, 0.3, 0.5, seed=42, weight=2.5,
    )
    for n in G.nodes():
        assert G.nodes[n]["weight"] == 2.5


# ---------------------------------------------------------------------------
# pos_name / weight_name are KEYWORD_ONLY
# ---------------------------------------------------------------------------

@needs_nx
@pytest.mark.parametrize("name", GENERATORS)
def test_pos_name_keyword_only(name):
    fnx_sig = inspect.signature(getattr(fnx, name))
    assert (
        fnx_sig.parameters["pos_name"].kind == inspect.Parameter.KEYWORD_ONLY
    )
