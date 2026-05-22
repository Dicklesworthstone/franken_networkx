"""Parity for ``random_labeled_rooted_forest`` + ``tutte_polynomial`` signatures.

Bead br-r37-c1-rrf-tut. Two stale signatures:

- ``random_labeled_rooted_forest(n, q=None, seed=None)`` — fnx had a
  stray ``q`` arg leaked from the related ``random_unlabeled_rooted_forest``;
  nx is ``(n, *, seed=None)``. Drop-in code calling
  ``rrf(5, seed=42)`` worked, but ``rrf(5, None, 42)`` worked on fnx
  and rejected on nx.
- ``tutte_polynomial(G)`` — fnx previously accepted ``x``/``y`` numeric
  evaluation kwargs; nx rejects them. fnx now mirrors nx's dispatch
  signature and unexpected-keyword behavior.
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
    # br-r37-c1-rrfsig-update: cycle 178 added the canonical
    # ``*, backend=None, **backend_kwargs`` dispatch surface to fnx
    # wrappers so ``nx.random_labeled_rooted_forest(n, backend=
    # 'networkx')`` works on fnx.  Compare core user-facing params
    # after stripping the dispatch-surface kwargs — fnx and nx must
    # agree on both core and dispatch params.
    def _strip_dispatch(params):
        return [k for k in params if k not in ("backend", "backend_kwargs")]

    fnx_core = _strip_dispatch(fnx_sig.parameters)
    nx_core = _strip_dispatch(nx_sig.parameters)
    assert fnx_core == nx_core == ["n", "seed"]
    # seed is keyword-only on both
    assert (
        fnx_sig.parameters["seed"].kind == inspect.Parameter.KEYWORD_ONLY
    )
    # Also assert the full signature including dispatch surface matches nx
    assert str(fnx_sig) == str(nx_sig)


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
def test_tutte_polynomial_signature_matches_networkx():
    fnx_sig = inspect.signature(fnx.tutte_polynomial)
    nx_sig = inspect.signature(nx.tutte_polynomial)

    assert str(fnx_sig) == str(nx_sig)


@needs_nx
def test_tutte_polynomial_rejects_positional_x_y():
    """tutte_polynomial(G, 1, 1) must raise — nx rejects, fnx now too."""
    G = fnx.path_graph(3)
    with pytest.raises(TypeError):
        fnx.tutte_polynomial(G, 1)
    with pytest.raises(TypeError):
        fnx.tutte_polynomial(G, 1, 1)


@needs_nx
def test_tutte_polynomial_rejects_x_y_kwargs_like_networkx():
    G = fnx.path_graph(3)
    with pytest.raises(TypeError, match="unexpected keyword argument 'x'"):
        fnx.tutte_polynomial(G, x=2, y=3)
