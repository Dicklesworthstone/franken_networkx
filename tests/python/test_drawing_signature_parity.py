"""Parity for ``fnx.draw_networkx*`` introspectable signatures.

Bead br-r37-c1-hz9k5. The drawing wrappers in
``franken_networkx/drawing/nx_pylab.py`` used a generic
``(G, *args, **kwargs)`` shape, so ``inspect.signature(fnx.draw_X)``
returned that catch-all instead of nx's documented per-arg surface
(``draw_networkx_edges`` alone has 18 keyword parameters).

Same root cause and same fix as the approximation namespace
(``br-r37-c1-approxsig``): apply ``functools.wraps(nx_func)`` to each
delegating wrapper so the returned callable carries nx's full
signature, name, and docstring.
"""

from __future__ import annotations

import importlib
import inspect

import pytest

import franken_networkx as fnx

try:
    import networkx as nx
    HAS_NX = True
except ImportError:
    HAS_NX = False

try:
    import matplotlib  # noqa: F401
    HAS_MPL = True
except ImportError:
    HAS_MPL = False

needs_nx = pytest.mark.skipif(not HAS_NX, reason="networkx not installed")
needs_mpl = pytest.mark.skipif(not HAS_MPL, reason="matplotlib not installed")


DRAWING_NAMES = [
    "draw",
    "draw_networkx",
    "draw_networkx_nodes",
    "draw_networkx_edges",
    "draw_networkx_labels",
    "draw_networkx_edge_labels",
]

DRAWING_CHILD_MODULES = [
    ("franken_networkx.drawing.layout", "networkx.drawing.layout"),
    ("franken_networkx.drawing.nx_pylab", "networkx.drawing.nx_pylab"),
]


@needs_nx
@pytest.mark.parametrize(("fnx_name", "nx_name"), DRAWING_CHILD_MODULES)
def test_drawing_child_module_star_exports_match_networkx(fnx_name, nx_name):
    f = importlib.import_module(fnx_name)
    n = importlib.import_module(nx_name)

    assert list(f.__all__) == list(n.__all__)
    missing = [name for name in n.__all__ if not hasattr(f, name)]
    assert not missing


@needs_nx
@pytest.mark.parametrize("name", DRAWING_NAMES)
def test_drawing_signature_matches_networkx(name):
    f = getattr(fnx, name)
    n = getattr(nx, name)

    fnx_params = [k for k in inspect.signature(f).parameters
                  if k not in ("backend", "backend_kwargs")]
    nx_params = [k for k in inspect.signature(n).parameters
                 if k not in ("backend", "backend_kwargs")]
    assert fnx_params == nx_params, (
        f"{name}: fnx={fnx_params} nx={nx_params}"
    )


@needs_nx
@pytest.mark.parametrize("name", DRAWING_NAMES)
def test_drawing_namespace_signature_matches_networkx(name):
    """Same check via the drawing.* namespace, not just top-level."""
    f = getattr(fnx.drawing, name)
    n = getattr(nx, name)

    fnx_params = [k for k in inspect.signature(f).parameters
                  if k not in ("backend", "backend_kwargs")]
    nx_params = [k for k in inspect.signature(n).parameters
                 if k not in ("backend", "backend_kwargs")]
    assert fnx_params == nx_params


@needs_nx
@pytest.mark.parametrize("name", DRAWING_NAMES)
def test_drawing_wrapper_carries_nx_metadata(name):
    """functools.wraps must copy __doc__, __name__, __wrapped__."""
    f = getattr(fnx, name)
    n = getattr(nx, name)
    assert f.__name__ == n.__name__ == name
    # docstring should match
    assert (f.__doc__ or "")[:60] == (n.__doc__ or "")[:60]


@needs_nx
@needs_mpl
def test_draw_networkx_edges_explicit_kwargs_accepted():
    """The new wrapper must still accept the documented kwargs at call
    time. Passes through to nx.draw_networkx_edges."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    G = fnx.path_graph(4)
    pos = fnx.spring_layout(G, seed=0)
    fig, ax = plt.subplots()
    try:
        # arrowsize, edge_color, width are nx's per-arg keywords; if the
        # wrapper still used (G, pos, *args, **kwargs), these would be
        # accepted but inspect.signature wouldn't see them. The new
        # surface should accept them and keep introspection honest.
        fnx.draw_networkx_edges(
            G,
            pos,
            edgelist=list(G.edges()),
            width=1.5,
            edge_color="black",
            ax=ax,
        )
    finally:
        plt.close(fig)


@needs_nx
@needs_mpl
def test_draw_networkx_nodes_kwargs_accepted():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    G = fnx.path_graph(4)
    pos = fnx.spring_layout(G, seed=0)
    fig, ax = plt.subplots()
    try:
        fnx.draw_networkx_nodes(
            G,
            pos,
            nodelist=list(G.nodes()),
            node_size=120,
            node_color="lightblue",
            ax=ax,
        )
    finally:
        plt.close(fig)


# br-r37-c1-ibcok: ``networkx.drawing`` declares no ``__all__``, so its
# star-import surface is its public ``dir()`` — which INCLUDES the five child
# modules. fnx declares an explicit ``__all__``, and it used to omit them while
# adding two names nx does not expose there, so ``import *`` bound a different
# set of names on the two packages.
_DRAWING_CHILD_MODULES = ("layout", "nx_agraph", "nx_latex", "nx_pydot", "nx_pylab")


@pytest.mark.skipif(not HAS_NX, reason="networkx required")
def test_drawing_package_star_export_surface_matches_networkx():
    import networkx.drawing as nx_drawing
    import franken_networkx.drawing as fnx_drawing

    nx_surface = {n for n in dir(nx_drawing) if not n.startswith("_")}
    assert set(fnx_drawing.__all__) == nx_surface

    # The child modules are the specific names that were missing.
    assert set(_DRAWING_CHILD_MODULES) <= set(fnx_drawing.__all__)
    for child in _DRAWING_CHILD_MODULES:
        assert hasattr(fnx_drawing, child), child


def _star_import_names(module):
    """The names ``from <module> import *`` binds: ``__all__`` if present, else
    every public module-level name. This is CPython's rule, spelled out rather
    than run through ``exec``."""
    declared = getattr(module, "__all__", None)
    if declared is None:
        return {n for n in dir(module) if not n.startswith("_")}
    return set(declared)


@pytest.mark.skipif(not HAS_NX, reason="networkx required")
def test_drawing_star_import_binds_the_same_names():
    import networkx.drawing as nx_drawing
    import franken_networkx.drawing as fnx_drawing

    fnx_names = _star_import_names(fnx_drawing)
    assert fnx_names == _star_import_names(nx_drawing)
    # A name in __all__ that does not resolve makes the real star-import raise,
    # so check every exported name actually binds.
    for name in sorted(fnx_names):
        assert hasattr(fnx_drawing, name), name


@pytest.mark.skipif(not HAS_NX, reason="networkx required")
def test_drawing_child_all_surfaces_stay_equal_to_networkx():
    """Negative guard: fixing the parent must not disturb br-r37-c1-knd9z."""
    import networkx.drawing.layout as nx_layout
    import networkx.drawing.nx_pylab as nx_pylab_mod
    import franken_networkx.drawing.layout as fnx_layout
    import franken_networkx.drawing.nx_pylab as fnx_pylab_mod

    assert set(fnx_layout.__all__) == set(nx_layout.__all__)
    assert set(fnx_pylab_mod.__all__) == set(nx_pylab_mod.__all__)
