"""Graph classes — re-exports from ``networkx.classes``.

br-r37-c1-j54tp: see ``franken_networkx.generators`` docstring for the
parity-gap context. Same pattern: previously empty submodule that
broke ``import franken_networkx.classes as c; c.add_cycle(...)`` even
though ``franken_networkx.add_cycle`` worked.

Note: this re-exports nx's *Graph classes — the actual fnx Graph /
DiGraph / MultiGraph / MultiDiGraph used by user code remain the
fnx-native classes exposed at the top level of ``franken_networkx``.
``franken_networkx.classes`` is the *nx-mirror* path used by code that
explicitly imports through it for compatibility with nx-style
introspection.
"""

import networkx.classes as _nx_classes
from networkx.classes import *  # noqa: F401, F403

__all__ = list(
    getattr(_nx_classes, "__all__", ())
    or [name for name in dir(_nx_classes) if not name.startswith("_")]
)

# br-r37-c1-2qsqf: ``from networkx.classes import *`` above left the core graph
# TYPES (Graph/DiGraph/MultiGraph/MultiDiGraph) and ~42 helper functions bound to
# networkx's objects, so ``from franken_networkx.classes import Graph`` returned
# nx.Graph (a serious drop-in bug — that path should give fnx's native graph) and
# ``fnx.classes.degree`` etc. resolved to nx's helpers. Route to the fnx
# top-level objects: TYPES via direct hasattr-guarded alias (closures would break
# instantiation / isinstance); FUNCTIONS via call-time closure wrappers
# (import-order robust). Verified no internal module imports the graph types from
# ``.classes``, so this is safe.
_FNX_NATIVE_CLASS_TYPES = ("Graph", "DiGraph", "MultiGraph", "MultiDiGraph")
_FNX_NATIVE_CLASS_FUNCS = (
    "add_cycle", "add_path", "add_star", "all_neighbors", "common_neighbors",
    "create_empty_copy", "degree", "degree_histogram", "density", "describe",
    "edge_subgraph", "edges", "freeze", "get_edge_attributes",
    "get_node_attributes", "induced_subgraph", "is_directed", "is_empty",
    "is_frozen", "is_negatively_weighted", "is_path", "is_weighted", "neighbors",
    "nodes", "nodes_with_selfloops", "non_edges", "non_neighbors",
    "number_of_edges", "number_of_nodes", "number_of_selfloops", "path_weight",
    "remove_edge_attributes", "remove_node_attributes", "restricted_view",
    "reverse_view", "selfloop_edges", "set_edge_attributes", "set_node_attributes",
    "subgraph", "subgraph_view", "to_directed", "to_undirected",
)


def _make_fnx_classes_router(_fn_name):
    def _routed(*args, **kwargs):
        import franken_networkx as _fnx

        return getattr(_fnx, _fn_name)(*args, **kwargs)

    _routed.__name__ = _fn_name
    _routed.__qualname__ = _fn_name
    _routed.__doc__ = (
        f"Route to ``franken_networkx.{_fn_name}`` (fnx-native). See "
        f"``networkx.classes.{_fn_name}`` for semantics."
    )
    return _routed


for _name in _FNX_NATIVE_CLASS_FUNCS:
    globals()[_name] = _make_fnx_classes_router(_name)


def _install_fnx_native_class_types():
    import franken_networkx as _fnx

    for _name in _FNX_NATIVE_CLASS_TYPES:
        if hasattr(_fnx, _name):
            globals()[_name] = getattr(_fnx, _name)


_install_fnx_native_class_types()


def _install_classes_child_aliases():
    import importlib
    import pkgutil
    import sys
    import networkx.classes as _src

    for info in pkgutil.iter_modules(_src.__path__):
        name = info.name
        if name == "tests" or name.startswith("_"):
            continue
        alias = f"{__name__}.{name}"
        if alias in sys.modules:
            continue
        module = importlib.import_module(f"networkx.classes.{name}")
        sys.modules[alias] = module
        globals()[name] = module


def __getattr__(name):
    import networkx.classes as _src

    try:
        return getattr(_src, name)
    except AttributeError as exc:
        raise AttributeError(
            f"module {__name__!r} has no attribute {name!r}"
        ) from exc


def __dir__():
    import networkx.classes as _src

    return sorted(set(globals()) | set(dir(_src)))


_install_classes_child_aliases()
