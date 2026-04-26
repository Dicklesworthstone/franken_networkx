"""Parity for ``geometric_soft_configuration_graph``.

Bead br-r37-c1-gsc-stub. The fnx stub had signature
``(beta=1, n=100, dim=2, pos=None, seed=None)`` and silently routed to
``random_geometric_graph(n, 0.3)`` — a completely different model. nx's
S^1 / hyperbolic H^2 soft configuration model has signature
``(*, beta, n=None, gamma=None, mean_degree=None, kappas=None, seed=None)``.

Aligned: signature now matches nx; implementation delegates to nx so
the documented hyperbolic geometric model is actually run.
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


@needs_nx
def test_signature_matches_networkx():
    fnx_sig = inspect.signature(fnx.geometric_soft_configuration_graph)
    nx_sig = inspect.signature(nx.geometric_soft_configuration_graph)
    fnx_params = list(fnx_sig.parameters.keys())
    nx_params = [k for k in nx_sig.parameters.keys()
                 if k not in ("backend", "backend_kwargs")]
    assert fnx_params == nx_params

    # All parameters keyword-only (matching nx)
    for name in fnx_params:
        assert (
            fnx_sig.parameters[name].kind == inspect.Parameter.KEYWORD_ONLY
        ), f"{name} should be KEYWORD_ONLY"


@needs_nx
def test_beta_is_required():
    """beta has no default — must be specified."""
    sig = inspect.signature(fnx.geometric_soft_configuration_graph)
    assert sig.parameters["beta"].default is inspect.Parameter.empty
    with pytest.raises(TypeError):
        fnx.geometric_soft_configuration_graph(n=10, gamma=2.5, mean_degree=4)


@needs_nx
def test_returns_fnx_graph_instance():
    G = fnx.geometric_soft_configuration_graph(
        beta=1.5, n=20, gamma=2.5, mean_degree=4, seed=42,
    )
    assert isinstance(G, fnx.Graph)
    assert not G.is_directed()
    assert not G.is_multigraph()


@needs_nx
def test_node_count_matches_networkx_for_same_seed():
    G = fnx.geometric_soft_configuration_graph(
        beta=1.5, n=30, gamma=2.5, mean_degree=4, seed=42,
    )
    GX = nx.geometric_soft_configuration_graph(
        beta=1.5, n=30, gamma=2.5, mean_degree=4, seed=42,
    )
    assert G.number_of_nodes() == GX.number_of_nodes() == 30


@needs_nx
def test_edge_count_matches_networkx_for_same_seed():
    """Seeded random number generation should produce identical
    structure between fnx (which delegates) and nx."""
    G = fnx.geometric_soft_configuration_graph(
        beta=2.0, n=25, gamma=2.5, mean_degree=5, seed=7,
    )
    GX = nx.geometric_soft_configuration_graph(
        beta=2.0, n=25, gamma=2.5, mean_degree=5, seed=7,
    )
    assert G.number_of_edges() == GX.number_of_edges()


@needs_nx
def test_different_seeds_produce_different_edge_sets():
    """Sanity check that the seed is actually used."""
    G1 = fnx.geometric_soft_configuration_graph(
        beta=1.5, n=30, gamma=2.5, mean_degree=4, seed=1,
    )
    G2 = fnx.geometric_soft_configuration_graph(
        beta=1.5, n=30, gamma=2.5, mean_degree=4, seed=2,
    )
    assert sorted(G1.edges()) != sorted(G2.edges())


@needs_nx
def test_kappas_argument_drives_hidden_degrees():
    """When kappas is provided, n is taken from len(kappas)."""
    kappas = {i: float(i + 1) for i in range(15)}
    G = fnx.geometric_soft_configuration_graph(
        beta=1.5, kappas=kappas, seed=42,
    )
    assert G.number_of_nodes() == 15


@needs_nx
def test_old_positional_call_form_rejected():
    """All parameters are keyword-only now — positional must raise."""
    with pytest.raises(TypeError):
        fnx.geometric_soft_configuration_graph(1.5)  # was beta=1 default
