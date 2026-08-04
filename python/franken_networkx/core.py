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

# br-r37-c1-2qsqf: ``from networkx.algorithms.core import *`` above left
# ``core_number`` and ``k_truss`` bound to networkx's implementations, so
# ``fnx.core.core_number`` etc. silently resolved to nx's instead of fnx's
# native versions. Route these via call-time closure wrappers (import-order
# robust).
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
_FNX_NATIVE_CORE_NAMES = (
    "core_number",
    "k_truss",
    "k_core",
    "k_shell",
    "k_crust",
    "k_corona",
)


def _make_fnx_core_router(_fn_name):
    def _routed(*args, **kwargs):
        return getattr(_fnx, _fn_name)(*args, **kwargs)

    _routed.__name__ = _fn_name
    _routed.__qualname__ = _fn_name
    _routed.__doc__ = (
        f"Route to ``franken_networkx.{_fn_name}`` (fnx-native). See "
        f"``networkx.algorithms.core.{_fn_name}`` for semantics."
    )
    return _routed


for _name in _FNX_NATIVE_CORE_NAMES:
    globals()[_name] = _make_fnx_core_router(_name)


def onion_layers(G, *, backend=None, **backend_kwargs):
    """Return the onion layer decomposition via the fnx-native route."""
    return _fnx.onion_layers(
        G,
        backend=backend,
        **backend_kwargs,
    )
