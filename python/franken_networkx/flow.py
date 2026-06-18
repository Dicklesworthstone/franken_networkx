"""FrankenNetworkX flow submodule.

Re-exports the upstream ``networkx.algorithms.flow`` surface so
existing ``franken_networkx.flow.*`` call sites keep working, but
overrides specific functions with fnx-native implementations that return
fnx graph types instead of NetworkX graphs.

Current native overrides:
- high-level max-flow/min-cut/min-cost helpers route to fnx top-level natives
- ``gomory_hu_tree`` — returns fnx.Graph
"""

from __future__ import annotations

from networkx.algorithms.flow import *  # noqa: F401,F403
import networkx.algorithms.flow as _nx_flow

import franken_networkx as _fnx

__all__ = list(
    getattr(_nx_flow, "__all__", ())
    or [name for name in dir(_nx_flow) if not name.startswith("_")]
)

# br-r37-c1-ojs7g: ``from networkx.algorithms.flow import *`` above left the
# high-level flow helpers bound to NetworkX implementations even though fnx has
# native top-level versions with local parity/perf fixes. Route the root flow
# namespace through fnx; deeper child modules such as
# ``franken_networkx.algorithms.flow.maxflow`` remain NetworkX aliases.
_FNX_NATIVE_FLOW_NAMES = (
    "capacity_scaling",
    "cost_of_flow",
    "gomory_hu_tree",
    "max_flow_min_cost",
    "maximum_flow",
    "maximum_flow_value",
    "min_cost_flow",
    "min_cost_flow_cost",
    "minimum_cut",
    "minimum_cut_value",
    "network_simplex",
)


def _make_fnx_flow_router(_fn_name):
    def _routed(*args, **kwargs):
        return getattr(_fnx, _fn_name)(*args, **kwargs)

    _routed.__name__ = _fn_name
    _routed.__qualname__ = _fn_name
    _routed.__doc__ = (
        f"Route to ``franken_networkx.{_fn_name}`` (fnx-native). See "
        f"``networkx.algorithms.flow.{_fn_name}`` for semantics."
    )
    return _routed


for _name in _FNX_NATIVE_FLOW_NAMES:
    globals()[_name] = _make_fnx_flow_router(_name)
