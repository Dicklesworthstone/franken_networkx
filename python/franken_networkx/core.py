"""FrankenNetworkX core submodule.

Re-exports the upstream ``networkx.algorithms.core`` surface so
existing ``franken_networkx.core.*`` call sites keep working, but
overrides specific functions with fnx-native implementations that return
fnx graph types instead of NetworkX graphs.

Current native overrides:
- ``k_core`` — returns fnx.Graph
- ``k_shell`` — returns fnx.Graph
- ``k_crust`` — returns fnx.Graph
- ``k_corona`` — returns fnx.Graph
- ``onion_layers`` — returns fnx-native layer mapping
"""

from __future__ import annotations

from networkx.algorithms.core import *  # noqa: F401,F403
import networkx.algorithms.core as _nx_core

import franken_networkx as _fnx

__all__ = list(
    getattr(
        _nx_core,
        "__all__",
        (
            "core_number",
            "k_core",
            "k_shell",
            "k_crust",
            "k_corona",
            "k_truss",
            "onion_layers",
        ),
    )
)

# br-r37-c1-b78jl: ``k_core``/``k_shell``/``k_crust``/``k_corona`` used to carry a
# SECOND native-routing implementation here, separate from the one in
# ``franken_networkx/__init__.py``. It had two defects the duplication hid:
# its gate called ``G.number_of_selfloops()`` as a method (no such method exists,
# so every non-empty simple ``Graph`` raised ``AttributeError``), and once that was
# corrected the raw kernels it called dropped graph-level and node attributes that
# ``networkx`` preserves. The top-level implementations are the mature ones -- they
# carry the whole bead history, return fnx graph types, preserve attributes, and are
# what the published k_core incumbent gate actually measures. Route to them, exactly
# as ``onion_layers`` below already does, so there is ONE implementation to keep
# parity-correct instead of two that can silently drift apart.
# br-r37-c1-9hnq3: the k-* four are deliberately NOT routed through the generic
# wrapper below. It forwards `*args, **kwargs`, and docs/coverage.md recorded all
# four as `present` — matching nx's signature — before that routing landed; the
# generic wrapper silently demoted them to `partial`. The regression was
# invisible because the FeatureUniverse extractor could not import networkx, so
# every test that would have caught it errored out first.
#
def core_number(G, *, backend=None, **backend_kwargs):
    """Return the core number for each node in ``G``."""
    return _fnx.core_number(G, backend=backend, **backend_kwargs)


def k_truss(G, k, *, backend=None, **backend_kwargs):
    """Return the maximal k-truss of ``G``."""
    return _fnx.k_truss(G, k, backend=backend, **backend_kwargs)


def k_core(G, k=None, core_number=None, *, backend=None, **backend_kwargs):
    """Return the k-core of G. Routes to ``franken_networkx.k_core``."""
    return _fnx.k_core(
        G, k=k, core_number=core_number, backend=backend, **backend_kwargs
    )


def k_shell(G, k=None, core_number=None, *, backend=None, **backend_kwargs):
    """Return the k-shell of G. Routes to ``franken_networkx.k_shell``."""
    return _fnx.k_shell(
        G, k=k, core_number=core_number, backend=backend, **backend_kwargs
    )


def k_crust(G, k=None, core_number=None, *, backend=None, **backend_kwargs):
    """Return the k-crust of G. Routes to ``franken_networkx.k_crust``."""
    return _fnx.k_crust(
        G, k=k, core_number=core_number, backend=backend, **backend_kwargs
    )


def k_corona(G, k, core_number=None, *, backend=None, **backend_kwargs):
    """Return the k-corona of G. Routes to ``franken_networkx.k_corona``.

    ``k`` is positional-required here, as in networkx — unlike its three
    siblings above, which default it to None.
    """
    return _fnx.k_corona(
        G, k, core_number=core_number, backend=backend, **backend_kwargs
    )


def onion_layers(G, *, backend=None, **backend_kwargs):
    """Return the onion layer decomposition via the fnx-native route."""
    return _fnx.onion_layers(
        G,
        backend=backend,
        **backend_kwargs,
    )
