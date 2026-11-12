"""FrankenNetworkX shortest_paths submodule.

Mirrors ``networkx.algorithms.shortest_paths`` but routes every function that
networkx re-exports at top level to FrankenNetworkX's optimized top-level
implementation.

br-r37-c1-sproute: previously ``franken_networkx.algorithms.shortest_paths``
and ``fnx.shortest_paths`` were aliased directly to networkx's module.
Calls like ``fnx.algorithms.shortest_paths.shortest_path`` ran nx's pure-Python
implementation over fnx graph views (~8x slower than native fnx.shortest_path).
Binding every name networkx aliases to top level to the ``franken_networkx``
top-level implementation ensures drop-in performance and semantic parity
(fnx.algorithms.shortest_paths.X is fnx.X, exactly as nx.algorithms.shortest_paths.X is nx.X).
"""

from __future__ import annotations

import importlib as _importlib
import sys as _sys
import types as _types

import networkx as _nx
import networkx.algorithms.shortest_paths as _nxsp
from networkx.algorithms.shortest_paths import *  # noqa: F401,F403

import franken_networkx as _fnx

__all__ = getattr(
    _nxsp, "__all__", [n for n in dir(_nxsp) if not n.startswith("_")]
)


def _route_module_to_fnx(mod, nx_source):
    """Rebind top-level-aliased nx names in `mod` to fnx's optimized implementations."""
    routed = []
    for name in dir(nx_source):
        if name.startswith("_"):
            continue
        nval = getattr(nx_source, name)
        if not callable(nval):
            continue
        if getattr(_nx, name, None) is not nval:
            continue
        fval = getattr(_fnx, name, None)
        if fval is not None and fval is not nval:
            if isinstance(mod, dict):
                mod[name] = fval
            else:
                setattr(mod, name, fval)
            routed.append(name)
    return routed


def _route_to_fnx_toplevel():
    """Rebind top-level-aliased nx names to fnx's optimized implementations."""
    routed = _route_module_to_fnx(globals(), _nxsp)
    _install_child_modules()
    return routed


def _install_child_modules():
    """Proxy child modules (generic, unweighted, weighted, dense, astar) so their
    functions also route to fnx top-level implementations."""
    for child_name in ("generic", "unweighted", "weighted", "dense", "astar"):
        try:
            nx_child = _importlib.import_module(f"networkx.algorithms.shortest_paths.{child_name}")
        except Exception:
            continue

        alias_sp = f"{__name__}.{child_name}"
        alias_alg = f"franken_networkx.algorithms.shortest_paths.{child_name}"

        proxy = _types.ModuleType(alias_sp, nx_child.__doc__)
        proxy.__dict__.update(nx_child.__dict__)
        proxy.__name__ = alias_sp
        proxy.__package__ = __name__

        _route_module_to_fnx(proxy, nx_child)

        globals()[child_name] = proxy
        _sys.modules[alias_sp] = proxy
        _sys.modules[alias_alg] = proxy


_routed_names = _route_to_fnx_toplevel()
_install_child_modules()
