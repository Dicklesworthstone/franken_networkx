"""Parity for ``random_labeled_rooted_forest`` + ``tutte_polynomial`` signatures.

Bead br-r37-c1-rrf-tut. Two stale signatures:

- ``random_labeled_rooted_forest(n, q=None, seed=None)`` — fnx had a
  stray ``q`` arg leaked from the related ``random_unlabeled_rooted_forest``;
  nx is ``(n, *, seed=None)``. Drop-in code calling
  ``rrf(5, seed=42)`` worked, but ``rrf(5, None, 42)`` worked on fnx
  and rejected on nx.
- ``tutte_polynomial(G, x=None, y=None)`` — fnx accepted ``x``/``y``
  positionally as a numeric-evaluation extension; nx is ``(G,)`` with
  no other positional arguments. Calling ``tutte_polynomial(G, 1, 1)``
  on nx raised TypeError. fnx now requires ``x``/``y`` keyword-only.
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


# ---------------------------------------------------------------------------
# random_labeled_rooted_forest
# ---------------------------------------------------------------------------

@needs_nx
def test_rrf_signature_matches_networkx():
    fnx_sig = inspect.signature(fnx.random_labeled_rooted_forest)
    nx_sig = inspect.signature(nx.random_labeled_rooted_forest)
    fnx_params = list(fnx_sig.parameters.keys())
    nx_params = [k for k in nx_sig.parameters.keys()
                 if k not in ("backend", "backend_kwargs")]
    assert fnx_params == nx_params == ["n", "seed"]
    # seed is keyword-only on both
    assert (
        fnx_sig.parameters["seed"].kind == inspect.Parameter.KEYWORD_ONLY
    )


@needs_nx
def test_rrf_rejects_old_positional_q_argument():
    """Old fnx signature was (n, q=None, seed=None). Calling with a
    third positional argument must now raise."""
    with pytest.raises(TypeError):
        fnx.random_labeled_rooted_forest(5, None, 42)


@needs_nx
def test_rrf_default_call_returns_graph_with_n_nodes():
    G = fnx.random_labeled_rooted_forest(5, seed=42)
    assert G.number_of_nodes() == 5


# ---------------------------------------------------------------------------
# tutte_polynomial
# ---------------------------------------------------------------------------

@needs_nx
def test_tutte_polynomial_x_y_keyword_only():
    """fnx's x, y numeric-evaluation extension must be keyword-only —
    nx accepts only G positionally."""
    fnx_sig = inspect.signature(fnx.tutte_polynomial)
    for name in ("x", "y"):
        assert (
            fnx_sig.parameters[name].kind == inspect.Parameter.KEYWORD_ONLY
        ), f"{name} should be KEYWORD_ONLY"


@needs_nx
def test_tutte_polynomial_rejects_positional_x_y():
    """tutte_polynomial(G, 1, 1) must raise — nx rejects, fnx now too."""
    G = fnx.path_graph(3)
    with pytest.raises(TypeError):
        fnx.tutte_polynomial(G, 1)
    with pytest.raises(TypeError):
        fnx.tutte_polynomial(G, 1, 1)


@needs_nx
def test_tutte_polynomial_kwargs_x_y_evaluation():
    """fnx's numeric-evaluation extension still works with kwargs.
    For the path graph P3 (a tree), the Tutte polynomial T(x, y) = x^2,
    so T(2, 3) = 4."""
    G = fnx.path_graph(3)
    val = fnx.tutte_polynomial(G, x=2, y=3)
    assert val == 4
