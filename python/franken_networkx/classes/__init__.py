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
from networkx.classes.filters import no_filter as _no_filter

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


def nodes(G):
    """Return the native graph's node view."""
    import franken_networkx as _fnx

    return _fnx.nodes(G)


def edges(G, nbunch=None):
    """Return the native graph's edge view, optionally restricted to nbunch."""
    import franken_networkx as _fnx

    return _fnx.edges(G, nbunch)


def degree(G, nbunch=None, weight=None):
    """Return the native graph's degree view."""
    import franken_networkx as _fnx

    return _fnx.degree(G, nbunch, weight)


def add_cycle(G_to_add_to, nodes_for_cycle, **attr):
    """Add a cycle through the native functional API."""
    import franken_networkx as _fnx

    return _fnx.add_cycle(G_to_add_to, nodes_for_cycle, **attr)


def add_path(G_to_add_to, nodes_for_path, **attr):
    """Add a path through the native functional API."""
    import franken_networkx as _fnx

    return _fnx.add_path(G_to_add_to, nodes_for_path, **attr)


def density(G):
    """Return graph density through the native functional API."""
    import franken_networkx as _fnx

    return _fnx.density(G)


def edge_subgraph(G, edges):
    """Return an edge-induced native subgraph."""
    import franken_networkx as _fnx

    return _fnx.edge_subgraph(G, edges)


def is_directed(G):
    """Return whether a native graph is directed."""
    import franken_networkx as _fnx

    return _fnx.is_directed(G)


def neighbors(G, n):
    """Return the native graph's neighbor iterator."""
    import franken_networkx as _fnx

    return _fnx.neighbors(G, n)


def number_of_edges(G):
    """Return the native graph's edge count."""
    import franken_networkx as _fnx

    return _fnx.number_of_edges(G)


def number_of_nodes(G):
    """Return the native graph's node count."""
    import franken_networkx as _fnx

    return _fnx.number_of_nodes(G)


def subgraph(G, nbunch):
    """Return a native induced subgraph."""
    import franken_networkx as _fnx

    return _fnx.subgraph(G, nbunch)


def to_directed(graph):
    """Convert a native graph to a directed graph."""
    import franken_networkx as _fnx

    return _fnx.to_directed(graph)


def to_undirected(graph):
    """Convert a native graph to an undirected graph."""
    import franken_networkx as _fnx

    return _fnx.to_undirected(graph)


def induced_subgraph(G, nbunch):
    """Return a native induced live subgraph."""
    import franken_networkx as _fnx

    return _fnx.induced_subgraph(G, nbunch)


def subgraph_view(G, *, filter_node=_no_filter, filter_edge=_no_filter):
    """Return a filtered native live view."""
    import franken_networkx as _fnx

    return _fnx.subgraph_view(G, filter_node=filter_node, filter_edge=filter_edge)


def restricted_view(G, nodes, edges):
    """Return a native view excluding selected nodes and edges."""
    import franken_networkx as _fnx

    return _fnx.restricted_view(G, nodes, edges)


def reverse_view(G):
    """Return a native directed reverse view."""
    import franken_networkx as _fnx

    return _fnx.reverse_view(G)


def add_star(G_to_add_to, nodes_for_star, **attr):
    """Add a star through the native functional API."""
    import franken_networkx as _fnx

    return _fnx.add_star(G_to_add_to, nodes_for_star, **attr)


def all_neighbors(graph, node):
    """Return all native neighbors of a node."""
    import franken_networkx as _fnx

    return _fnx.all_neighbors(graph, node)


def common_neighbors(G, u, v):
    """Return native common neighbors of two nodes."""
    import franken_networkx as _fnx

    return _fnx.common_neighbors(G, u, v)


def degree_histogram(G):
    """Return the native graph's degree histogram."""
    import franken_networkx as _fnx

    return _fnx.degree_histogram(G)


def is_path(G, path):
    """Return whether path is valid in the native graph."""
    import franken_networkx as _fnx

    return _fnx.is_path(G, path)


def nodes_with_selfloops(G):
    """Return native nodes that have a self-loop."""
    import franken_networkx as _fnx

    return _fnx.nodes_with_selfloops(G)


def non_edges(graph):
    """Return missing native graph edges."""
    import franken_networkx as _fnx

    return _fnx.non_edges(graph)


def non_neighbors(graph, node):
    """Return native non-neighbors of a node."""
    import franken_networkx as _fnx

    return _fnx.non_neighbors(graph, node)


def path_weight(G, path, weight):
    """Return the native graph's total path weight."""
    import franken_networkx as _fnx

    return _fnx.path_weight(G, path, weight)


def selfloop_edges(G, data=False, keys=False, default=None):
    """Return native graph self-loop edges."""
    import franken_networkx as _fnx

    return _fnx.selfloop_edges(G, data=data, keys=keys, default=default)


def create_empty_copy(G, with_data=True):
    """Create an empty native graph preserving the requested data."""
    import franken_networkx as _fnx

    return _fnx.create_empty_copy(G, with_data)


def freeze(G):
    """Freeze a native graph against mutation."""
    import franken_networkx as _fnx

    return _fnx.freeze(G)


def is_frozen(G):
    """Return whether a native graph is frozen."""
    import franken_networkx as _fnx

    return _fnx.is_frozen(G)


def get_node_attributes(G, name, default=None, *, backend=None, **backend_kwargs):
    """Return node attributes through the native functional API."""
    import franken_networkx as _fnx

    _fnx._validate_backend_dispatch_keywords(
        "get_node_attributes", backend, backend_kwargs
    )
    return _fnx.get_node_attributes(G, name, default)


def get_edge_attributes(G, name, default=None, *, backend=None, **backend_kwargs):
    """Return edge attributes through the native functional API."""
    import franken_networkx as _fnx

    _fnx._validate_backend_dispatch_keywords(
        "get_edge_attributes", backend, backend_kwargs
    )
    return _fnx.get_edge_attributes(G, name, default)


def set_node_attributes(G, values, name=None, *, backend=None, **backend_kwargs):
    """Set node attributes through the native functional API."""
    import franken_networkx as _fnx

    _fnx._validate_backend_dispatch_keywords(
        "set_node_attributes", backend, backend_kwargs
    )
    return _fnx.set_node_attributes(G, values, name)


def set_edge_attributes(G, values, name=None, *, backend=None, **backend_kwargs):
    """Set edge attributes through the native functional API."""
    import franken_networkx as _fnx

    _fnx._validate_backend_dispatch_keywords(
        "set_edge_attributes", backend, backend_kwargs
    )
    return _fnx.set_edge_attributes(G, values, name)


def number_of_selfloops(G, *, backend=None, **backend_kwargs):
    """Return the number of native self-loop edges."""
    import franken_networkx as _fnx

    _fnx._validate_backend_dispatch_keywords(
        "number_of_selfloops", backend, backend_kwargs
    )
    return _fnx.number_of_selfloops(G)


def is_weighted(G, edge=None, weight="weight", *, backend=None, **backend_kwargs):
    """Return whether native graph edges carry the requested weight."""
    import franken_networkx as _fnx

    _fnx._validate_backend_dispatch_keywords("is_weighted", backend, backend_kwargs)
    return _fnx.is_weighted(G, edge, weight)


def is_negatively_weighted(
    G, edge=None, weight="weight", *, backend=None, **backend_kwargs
):
    """Return whether native graph edges carry a negative requested weight."""
    import franken_networkx as _fnx

    _fnx._validate_backend_dispatch_keywords(
        "is_negatively_weighted", backend, backend_kwargs
    )
    return _fnx.is_negatively_weighted(G, edge, weight)


def describe(G, describe_hook=None):
    """Print a native graph description."""
    import franken_networkx as _fnx

    return _fnx.describe(G, describe_hook)


def is_empty(G, *, backend=None, **backend_kwargs):
    """Return whether the native graph has no edges."""
    import franken_networkx as _fnx

    return _fnx.is_empty(G, backend=backend, **backend_kwargs)


def remove_node_attributes(G, *attr_names, nbunch=None, backend=None, **backend_kwargs):
    """Remove selected native node attributes."""
    import franken_networkx as _fnx

    return _fnx.remove_node_attributes(
        G, *attr_names, nbunch=nbunch, backend=backend, **backend_kwargs
    )


def remove_edge_attributes(G, *attr_names, ebunch=None, backend=None, **backend_kwargs):
    """Remove selected native edge attributes."""
    import franken_networkx as _fnx

    return _fnx.remove_edge_attributes(
        G, *attr_names, ebunch=ebunch, backend=backend, **backend_kwargs
    )


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
