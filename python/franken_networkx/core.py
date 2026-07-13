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
from franken_networkx.readwrite import _from_nx_graph

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
# native versions. ``k_core`` already overrides below; route these via call-time
# closure wrappers (import-order robust).
_FNX_NATIVE_CORE_NAMES = ("core_number", "k_truss")


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


def _k_core_family_native_ok(G, k, core_number):
    """Whether the k-core family can route to native Rust with byte-exact nx parity.

    The native kernels emit nodes in G-insertion order and re-attach node/edge attributes, so
    the induced subgraph matches ``G.subgraph(nodes)``. Route ONLY when the result and the
    error behaviour match ``networkx``:

    - simple undirected fnx ``Graph`` (the nx wrappers go through ``core_number``, which is
      undefined for multigraphs; directed inputs take a different degree definition);
    - no precomputed ``core_number`` (a user map bypasses the native decomposition);
    - at least one node (``nx.core_number`` -> ``max([])`` raises ``ValueError`` when ``k is
      None`` on an empty graph — delegate so that raise is preserved);
    - no self loops (``nx.core_number`` raises ``NetworkXNotImplemented`` on self loops);
    - ``k`` is ``None`` or a non-negative ``int`` (the usize binding cannot represent a negative
      or float ``k`` that networkx would still accept).
    """
    return (
        core_number is None
        and type(G) is _fnx.Graph
        and G.number_of_nodes() > 0
        and G.number_of_selfloops() == 0
        and (k is None or (isinstance(k, int) and k >= 0))
    )


def k_core(G, k=None, core_number=None, *, backend=None, **backend_kwargs):
    """Return the k-core of G.

    Wraps ``networkx.algorithms.core.k_core`` and converts
    the result to an fnx graph type for drop-in compatibility.
    """
    _fnx._validate_backend_dispatch_keywords("k_core", backend, backend_kwargs)
    # br-r37-c1-kcorenative: route the plain simple-``Graph`` case to the native Rust k-core (nx
    # runs a pure-Python core decomposition + subgraph copy). See ``_k_core_family_native_ok``.
    if _k_core_family_native_ok(G, k, core_number):
        from franken_networkx._fnx import k_core_rust as _raw_k_core

        return _raw_k_core(G, k)
    nx_result = _nx_core.k_core(G, k=k, core_number=core_number)
    return _from_nx_graph(nx_result)


def k_shell(G, k=None, core_number=None, *, backend=None, **backend_kwargs):
    """Return the k-shell of G.

    Wraps ``networkx.algorithms.core.k_shell`` and converts
    the result to an fnx graph type for drop-in compatibility.
    """
    _fnx._validate_backend_dispatch_keywords("k_shell", backend, backend_kwargs)
    # br-r37-c1-kshellnative: native route for the simple-``Graph`` case (see the k_core note).
    if _k_core_family_native_ok(G, k, core_number):
        from franken_networkx._fnx import k_shell_rust as _raw_k_shell

        return _raw_k_shell(G, k)
    nx_result = _nx_core.k_shell(G, k=k, core_number=core_number)
    return _from_nx_graph(nx_result)


def k_crust(G, k=None, core_number=None, *, backend=None, **backend_kwargs):
    """Return the k-crust of G.

    Wraps ``networkx.algorithms.core.k_crust`` and converts
    the result to an fnx graph type for drop-in compatibility.
    """
    _fnx._validate_backend_dispatch_keywords("k_crust", backend, backend_kwargs)
    # br-r37-c1-kcrustnative: native route for the simple-``Graph`` case (see the k_core note).
    if _k_core_family_native_ok(G, k, core_number):
        from franken_networkx._fnx import k_crust_rust as _raw_k_crust

        return _raw_k_crust(G, k)
    nx_result = _nx_core.k_crust(G, k=k, core_number=core_number)
    return _from_nx_graph(nx_result)


def k_corona(G, k, core_number=None, *, backend=None, **backend_kwargs):
    """Return the k-corona of G.

    Wraps ``networkx.algorithms.core.k_corona`` and converts
    the result to an fnx graph type for drop-in compatibility.
    """
    _fnx._validate_backend_dispatch_keywords("k_corona", backend, backend_kwargs)
    # br-r37-c1-kcoronanative: native route for the simple-``Graph`` case (see the k_core note).
    # ``k`` is required here, so the guard's ``k is None`` branch is never taken.
    if _k_core_family_native_ok(G, k, core_number):
        from franken_networkx._fnx import k_corona_rust as _raw_k_corona

        return _raw_k_corona(G, k)
    nx_result = _nx_core.k_corona(G, k, core_number=core_number)
    return _from_nx_graph(nx_result)


def onion_layers(G, *, backend=None, **backend_kwargs):
    """Return the onion layer decomposition via the fnx-native route."""
    return _fnx.onion_layers(
        G,
        backend=backend,
        **backend_kwargs,
    )
