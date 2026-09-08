"""Algorithm functions — re-exports from ``networkx.algorithms``.

br-r37-c1-j54tp: see ``franken_networkx.generators`` docstring for the
parity-gap context. nx.algorithms exposes ~537 names (114 of them
nested submodules like ``approximation``, ``assortativity``, ``astar``);
they're all reachable via this submodule path.

Top-level functions (``franken_networkx.foo``) remain backed by the
fnx-native Rust ports / Python wrappers; this module is the nx-mirror
path for code that imports through ``franken_networkx.algorithms.X``.

br-r37-c1-algsubmod: register every nx.algorithms submodule (and
subpackage) in ``sys.modules`` so drop-in callers using the
import-from-submodule form ``from franken_networkx.algorithms.flow
import maximum_flow`` resolve to the same module as nx.  Without this,
attribute access (``fnx.algorithms.flow``) worked but the import path
raised ``ModuleNotFoundError``.
"""

import sys as _sys
import importlib as _importlib
import inspect as _inspect
import pkgutil as _pkgutil

import networkx.algorithms as _nx_algorithms
from networkx.algorithms import *  # noqa: F401, F403

__all__ = list(
    getattr(_nx_algorithms, "__all__", ())
    or [name for name in dir(_nx_algorithms) if not name.startswith("_")]
)

# br-r37-c1-8wp6u: networkx.algorithms has no __all__, so the above falls to
# dir(_nx_algorithms) — but that is captured before networkx lazily loads some
# submodules (e.g. ``threshold``), leaving them out of __all__ and diverging
# from nx's exports. Add every algorithms submodule explicitly so __all__ is
# complete regardless of lazy-import timing.
for _info in _pkgutil.iter_modules(_nx_algorithms.__path__):
    if (
        not _info.name.startswith("_")
        and _info.name != "tests"
        and _info.name not in __all__
    ):
        __all__.append(_info.name)


_FNX_OVERRIDE_SUBMODULES = {
    "asteroidal",
    "boundary",
    "broadcasting",
    "bipartite",
    "chains",
    "communicability_alg",
    "community",
    "connectivity",
    "covering",
    "cuts",
    "isomorphism",
    "cycles",
    "dominance",
    "d_separation",
    "distance_regular",
    "dominating",
    "efficiency_measures",
    "graph_hashing",
    "graphical",
    "hierarchy",
    "isolate",
    "link_prediction",
    "lowest_common_ancestors",
    "matching",
    "mis",
    "non_randomness",
    "perfect_graph",
    "polynomials",
    "reciprocity",
    "richclub",
    "similarity",
    "simple_paths",
    "smetric",
    "structuralholes",
    "voronoi",
    "vitality",
    "walks",
    "wiener",
    "approximation",
    "minors",
    "operators",
    "clique",
    "cluster",
    "summarization",
    "moral",
    "tree",
    "flow",
    "traversal",
    "euler",
    "sparsifiers",
    "triads",
    "threshold",
    "dag",
    "chordal",
    "core",
    "hybrid",
    "tournament",
    "smallworld",
    "regular",
    "swap",
    "planarity",
    "components",
    "bridges",
    "centrality",
    "distance_measures",
    "link_analysis",
    "assortativity",
}


def _alias_nx_submodules(nx_pkg, fnx_prefix):
    """Recursively alias nx submodules into ``sys.modules`` under fnx_prefix.

    Skips ``tests`` packages (pytest-fixture-bound) and private modules
    starting with ``_`` so we don't expose nx's internal test helpers as
    fnx public API.

    Also skips submodules listed in _FNX_OVERRIDE_SUBMODULES which have
    native fnx implementations that should take precedence.
    """
    if not hasattr(nx_pkg, "__path__"):
        return
    for info in _pkgutil.iter_modules(nx_pkg.__path__):
        name = info.name
        if name == "tests" or name.startswith("_"):
            continue
        if name in _FNX_OVERRIDE_SUBMODULES:
            continue
        nx_dotted = f"{nx_pkg.__name__}.{name}"
        fnx_dotted = f"{fnx_prefix}.{name}"
        if fnx_dotted in _sys.modules:
            continue
        try:
            sub = _importlib.import_module(nx_dotted)
        except Exception:
            continue
        _sys.modules[fnx_dotted] = sub
        if info.ispkg:
            _alias_nx_submodules(sub, fnx_dotted)


def _alias_nx_child_modules(nx_dotted, fnx_dotted):
    """Alias child modules under an overridden fnx algorithm module."""
    try:
        nx_pkg = _importlib.import_module(nx_dotted)
    except Exception:
        return
    if not hasattr(nx_pkg, "__path__"):
        return
    for info in _pkgutil.iter_modules(nx_pkg.__path__):
        name = info.name
        if name == "tests" or name.startswith("_"):
            continue
        nx_child = f"{nx_dotted}.{name}"
        fnx_child = f"{fnx_dotted}.{name}"
        if fnx_child in _sys.modules:
            continue
        sub = None
        try:
            sub = _importlib.import_module(nx_child)
        except Exception as exc:
            sub = exc
        if isinstance(sub, Exception):
            continue
        _sys.modules[fnx_child] = sub
        parent = _sys.modules.get(fnx_dotted)
        if parent is not None:
            # br-r37-c1-dispclob: do NOT overwrite an existing FUNCTION/class
            # attribute with a same-named child MODULE. e.g. fnx.centrality has a
            # ``dispersion`` centrality FUNCTION and a ``dispersion.py`` child
            # module; clobbering the function breaks ``fnx.centrality.dispersion(
            # ...)`` (-> "module not callable"). Same class as the isomorphism.
            # tree_isomorphism clobber (nhbni). The child module stays importable
            # via ``sys.modules[fnx_child]`` / its dotted path; we just don't let
            # it shadow the public function attribute.
            from types import ModuleType as _ModuleType
            existing = getattr(parent, name, None)
            if existing is None or isinstance(existing, _ModuleType):
                setattr(parent, name, sub)
        if info.ispkg:
            _alias_nx_child_modules(nx_child, fnx_child)


_alias_nx_submodules(_importlib.import_module("networkx.algorithms"), __name__)

_nx_connectivity_cuts = _importlib.import_module(
    "networkx.algorithms.connectivity.cuts"
)
_sys.modules[f"{__name__}.connectivity.cuts"] = _nx_connectivity_cuts
_connectivity_parent = _sys.modules.get(f"{__name__}.connectivity")
if _connectivity_parent is not None:
    _connectivity_parent.cuts = _nx_connectivity_cuts

# Override bipartite submodule to use fnx's native implementation
# which wraps nx functions to return fnx graph types.
# This must happen AFTER the star import since `from networkx.algorithms import *`
# imports `bipartite` into the module namespace directly.
import franken_networkx.bipartite as _fnx_bipartite
_sys.modules[f"{__name__}.bipartite"] = _fnx_bipartite
bipartite = _fnx_bipartite  # Override in module globals
_alias_nx_child_modules(
    "networkx.algorithms.bipartite", f"{__name__}.bipartite"
)


def complete_bipartite_graph(
    n1, n2, create_using=None, *, backend=None, **backend_kwargs
):
    return _fnx_bipartite.complete_bipartite_graph(
        n1, n2, create_using=create_using, backend=backend, **backend_kwargs
    )


def is_bipartite(G, *, backend=None, **backend_kwargs):
    return _fnx_bipartite.is_bipartite(G, backend=backend, **backend_kwargs)


def projected_graph(
    B, nodes, multigraph=False, *, backend=None, **backend_kwargs
):
    return _fnx_bipartite.projected_graph(
        B, nodes, multigraph=multigraph, backend=backend, **backend_kwargs
    )


_fnx_approximation = _importlib.import_module("franken_networkx.approximation")
_sys.modules[f"{__name__}.approximation"] = _fnx_approximation
approximation = _fnx_approximation  # Override in module globals

# br-r37-c1-nc-native (cc): override node_classification with the fnx-native
# version — fnx's native to_scipy_sparse_array builds the adjacency matrix in Rust
# instead of nx iterating the fnx graph via PyO3 — byte-identical (deterministic
# linear solve) and 1.27-1.77x faster than nx, growing with n. Same override
# pattern as bipartite/approximation above; must run AFTER the alias loop (which
# registered nx's leaf module) to win in sys.modules + module globals. The alias
# loop already cached nx's module under our dotted name, so pop it first or
# ``import_module`` returns that cached nx module instead of loading our file.
_sys.modules.pop(f"{__name__}.node_classification", None)
_fnx_node_classification = _importlib.import_module(
    "franken_networkx.algorithms.node_classification"
)
_sys.modules[f"{__name__}.node_classification"] = _fnx_node_classification
node_classification = _fnx_node_classification  # Override in module globals
_alias_nx_child_modules(
    "networkx.algorithms.approximation", f"{__name__}.approximation"
)

import franken_networkx.minors as _fnx_minors
_sys.modules[f"{__name__}.minors"] = _fnx_minors
minors = _fnx_minors  # Override in module globals
_alias_nx_child_modules(
    "networkx.algorithms.minors", f"{__name__}.minors"
)

import franken_networkx.operators as _fnx_operators
_sys.modules[f"{__name__}.operators"] = _fnx_operators
operators = _fnx_operators  # Override in module globals
_alias_nx_child_modules(
    "networkx.algorithms.operators", f"{__name__}.operators"
)


def cartesian_product(G, H, *, backend=None, **backend_kwargs):
    return _fnx_operators.cartesian_product(
        G, H, backend=backend, **backend_kwargs
    )


def corona_product(G, H, *, backend=None, **backend_kwargs):
    return _fnx_operators.corona_product(
        G, H, backend=backend, **backend_kwargs
    )


def lexicographic_product(G, H, *, backend=None, **backend_kwargs):
    return _fnx_operators.lexicographic_product(
        G, H, backend=backend, **backend_kwargs
    )


def modular_product(G, H, *, backend=None, **backend_kwargs):
    return _fnx_operators.modular_product(
        G, H, backend=backend, **backend_kwargs
    )


def power(G, k, *, backend=None, **backend_kwargs):
    return _fnx_operators.power(G, k, backend=backend, **backend_kwargs)


def rooted_product(G, H, root, *, backend=None, **backend_kwargs):
    return _fnx_operators.rooted_product(
        G, H, root, backend=backend, **backend_kwargs
    )


def strong_product(G, H, *, backend=None, **backend_kwargs):
    return _fnx_operators.strong_product(
        G, H, backend=backend, **backend_kwargs
    )


def tensor_product(G, H, *, backend=None, **backend_kwargs):
    return _fnx_operators.tensor_product(
        G, H, backend=backend, **backend_kwargs
    )


def compose(G, H, *, backend=None, **backend_kwargs):
    return _fnx_operators.compose(G, H, backend=backend, **backend_kwargs)


def difference(G, H, *, backend=None, **backend_kwargs):
    return _fnx_operators.difference(G, H, backend=backend, **backend_kwargs)


def disjoint_union(G, H, *, backend=None, **backend_kwargs):
    return _fnx_operators.disjoint_union(
        G, H, backend=backend, **backend_kwargs
    )


def full_join(G, H, rename=(None, None), *, backend=None, **backend_kwargs):
    return _fnx_operators.full_join(
        G, H, rename=rename, backend=backend, **backend_kwargs
    )


def intersection(G, H, *, backend=None, **backend_kwargs):
    return _fnx_operators.intersection(
        G, H, backend=backend, **backend_kwargs
    )


def symmetric_difference(G, H, *, backend=None, **backend_kwargs):
    return _fnx_operators.symmetric_difference(
        G, H, backend=backend, **backend_kwargs
    )


def union(G, H, rename=(), *, backend=None, **backend_kwargs):
    return _fnx_operators.union(
        G, H, rename=rename, backend=backend, **backend_kwargs
    )


def compose_all(graphs, *, backend=None, **backend_kwargs):
    return _fnx_operators.compose_all(
        graphs, backend=backend, **backend_kwargs
    )


def disjoint_union_all(graphs, *, backend=None, **backend_kwargs):
    return _fnx_operators.disjoint_union_all(
        graphs, backend=backend, **backend_kwargs
    )


def intersection_all(graphs, *, backend=None, **backend_kwargs):
    return _fnx_operators.intersection_all(
        graphs, backend=backend, **backend_kwargs
    )


def union_all(graphs, rename=(), *, backend=None, **backend_kwargs):
    return _fnx_operators.union_all(
        graphs, rename=rename, backend=backend, **backend_kwargs
    )


def complement(G, *, backend=None, **backend_kwargs):
    return _fnx_operators.complement(G, backend=backend, **backend_kwargs)


def reverse(G, copy=True, *, backend=None, **backend_kwargs):
    return _fnx_operators.reverse(
        G, copy=copy, backend=backend, **backend_kwargs
    )

import franken_networkx.clique as _fnx_clique
_sys.modules[f"{__name__}.clique"] = _fnx_clique
clique = _fnx_clique  # Override in module globals


def enumerate_all_cliques(G, *, backend=None, **backend_kwargs):
    return _fnx_clique.enumerate_all_cliques(
        G, backend=backend, **backend_kwargs
    )


def find_cliques(G, nodes=None, *, backend=None, **backend_kwargs):
    return _fnx_clique.find_cliques(
        G, nodes=nodes, backend=backend, **backend_kwargs
    )


def find_cliques_recursive(G, nodes=None, *, backend=None, **backend_kwargs):
    return _fnx_clique.find_cliques_recursive(
        G, nodes=nodes, backend=backend, **backend_kwargs
    )


def make_clique_bipartite(
    G, fpos=None, create_using=None, name=None, *, backend=None, **backend_kwargs
):
    return _fnx_clique.make_clique_bipartite(
        G,
        fpos=fpos,
        create_using=create_using,
        name=name,
        backend=backend,
        **backend_kwargs,
    )


def max_weight_clique(G, weight="weight", *, backend=None, **backend_kwargs):
    return _fnx_clique.max_weight_clique(
        G, weight=weight, backend=backend, **backend_kwargs
    )


def node_clique_number(
    G, nodes=None, cliques=None, separate_nodes=False, *, backend=None, **backend_kwargs
):
    return _fnx_clique.node_clique_number(
        G,
        nodes=nodes,
        cliques=cliques,
        separate_nodes=separate_nodes,
        backend=backend,
        **backend_kwargs,
    )


def number_of_cliques(G, nodes=None, cliques=None):
    return _fnx_clique.number_of_cliques(G, nodes=nodes, cliques=cliques)

# br-r37-c1-nhbni: community/connectivity/isomorphism have native fnx submodules
# (fnx.community / fnx.connectivity / fnx.isomorphism) but were missing from the
# override set, so fnx.algorithms.<one> resolved to nx's. Map them to the fnx
# submodules like the 60+ others above.
from networkx.utils.heaps import BinaryHeap as _BinaryHeap

import franken_networkx.connectivity as _fnx_connectivity
_sys.modules[f"{__name__}.connectivity"] = _fnx_connectivity
connectivity = _fnx_connectivity  # Override in module globals
_alias_nx_child_modules(
    "networkx.algorithms.connectivity", f"{__name__}.connectivity"
)


def all_pairs_node_connectivity(
    G, nbunch=None, flow_func=None, *, backend=None, **backend_kwargs
):
    return _fnx_connectivity.all_pairs_node_connectivity(
        G, nbunch=nbunch, flow_func=flow_func, backend=backend, **backend_kwargs
    )


def average_node_connectivity(
    G, flow_func=None, *, backend=None, **backend_kwargs
):
    return _fnx_connectivity.average_node_connectivity(
        G, flow_func=flow_func, backend=backend, **backend_kwargs
    )


def edge_connectivity(
    G, s=None, t=None, flow_func=None, cutoff=None, *, backend=None, **backend_kwargs
):
    return _fnx_connectivity.edge_connectivity(
        G,
        s=s,
        t=t,
        flow_func=flow_func,
        cutoff=cutoff,
        backend=backend,
        **backend_kwargs,
    )


def node_connectivity(
    G, s=None, t=None, flow_func=None, *, backend=None, **backend_kwargs
):
    return _fnx_connectivity.node_connectivity(
        G, s=s, t=t, flow_func=flow_func, backend=backend, **backend_kwargs
    )


def edge_disjoint_paths(
    G,
    s,
    t,
    flow_func=None,
    cutoff=None,
    auxiliary=None,
    residual=None,
    *,
    backend=None,
    **backend_kwargs,
):
    return _fnx_connectivity.edge_disjoint_paths(
        G,
        s,
        t,
        flow_func=flow_func,
        cutoff=cutoff,
        auxiliary=auxiliary,
        residual=residual,
        backend=backend,
        **backend_kwargs,
    )


def node_disjoint_paths(
    G,
    s,
    t,
    flow_func=None,
    cutoff=None,
    auxiliary=None,
    residual=None,
    *,
    backend=None,
    **backend_kwargs,
):
    return _fnx_connectivity.node_disjoint_paths(
        G,
        s,
        t,
        flow_func=flow_func,
        cutoff=cutoff,
        auxiliary=auxiliary,
        residual=residual,
        backend=backend,
        **backend_kwargs,
    )


def is_k_edge_connected(G, k, *, backend=None, **backend_kwargs):
    return _fnx_connectivity.is_k_edge_connected(
        G, k, backend=backend, **backend_kwargs
    )


def k_edge_augmentation(
    G, k, avail=None, weight=None, partial=False, *, backend=None, **backend_kwargs
):
    return _fnx_connectivity.k_edge_augmentation(
        G,
        k,
        avail=avail,
        weight=weight,
        partial=partial,
        backend=backend,
        **backend_kwargs,
    )


def k_edge_components(G, k, *, backend=None, **backend_kwargs):
    return _fnx_connectivity.k_edge_components(
        G, k, backend=backend, **backend_kwargs
    )


def k_edge_subgraphs(G, k, *, backend=None, **backend_kwargs):
    return _fnx_connectivity.k_edge_subgraphs(
        G, k, backend=backend, **backend_kwargs
    )


def minimum_edge_cut(
    G, s=None, t=None, flow_func=None, *, backend=None, **backend_kwargs
):
    return _fnx_connectivity.minimum_edge_cut(
        G, s=s, t=t, flow_func=flow_func, backend=backend, **backend_kwargs
    )


def minimum_node_cut(
    G, s=None, t=None, flow_func=None, *, backend=None, **backend_kwargs
):
    return _fnx_connectivity.minimum_node_cut(
        G, s=s, t=t, flow_func=flow_func, backend=backend, **backend_kwargs
    )


def all_node_cuts(
    G, k=None, flow_func=None, *, backend=None, **backend_kwargs
):
    return _fnx_connectivity.all_node_cuts(
        G, k=k, flow_func=flow_func, backend=backend, **backend_kwargs
    )


def k_components(G, flow_func=None, *, backend=None, **backend_kwargs):
    return _fnx_connectivity.k_components(
        G, flow_func=flow_func, backend=backend, **backend_kwargs
    )


def stoer_wagner(
    G, weight="weight", heap=_BinaryHeap, *, backend=None, **backend_kwargs
):
    return _fnx_connectivity.stoer_wagner(
        G, weight=weight, heap=heap, backend=backend, **backend_kwargs
    )


import franken_networkx.community as _fnx_community
_sys.modules[f"{__name__}.community"] = _fnx_community
community = _fnx_community  # Override in module globals
_alias_nx_child_modules(
    "networkx.algorithms.community", f"{__name__}.community"
)

import franken_networkx.isomorphism as _fnx_isomorphism
_sys.modules[f"{__name__}.isomorphism"] = _fnx_isomorphism
isomorphism = _fnx_isomorphism  # Override in module globals
_alias_nx_child_modules(
    "networkx.algorithms.isomorphism", f"{__name__}.isomorphism"
)

# The flattened spellings are common public entry points.  Keep their exact
# NetworkX signatures while resolving the implementation at call time from the
# native leaf module, rather than retaining the generic ``*args, **kwargs``
# router installed below.
_FNX_FLATTENED_ISOMORPHISM_NAMES = (
    "is_isomorphic",
    "could_be_isomorphic",
    "fast_could_be_isomorphic",
    "faster_could_be_isomorphic",
    "vf2pp_is_isomorphic",
    "vf2pp_isomorphism",
    "vf2pp_all_isomorphisms",
)


def _make_flattened_isomorphism_router(_name):
    def _routed(*args, **kwargs):
        return getattr(_fnx_isomorphism, _name)(*args, **kwargs)

    _routed.__name__ = _name
    _routed.__qualname__ = _name
    _routed.__signature__ = _inspect.signature(getattr(_nx_algorithms, _name))
    return _routed


for _name in _FNX_FLATTENED_ISOMORPHISM_NAMES:
    globals()[_name] = _make_flattened_isomorphism_router(_name)

_fnx_cluster = _importlib.import_module("franken_networkx.cluster")
_sys.modules[f"{__name__}.cluster"] = _fnx_cluster
cluster = _fnx_cluster  # Override in module globals

# Preserve the public signatures of the flattened clustering helpers while
# delegating at call time to the native leaf module, including its backend
# dispatch validation.
_FNX_FLATTENED_CLUSTER_NAMES = (
    "triangles",
    "all_triangles",
    "average_clustering",
    "clustering",
    "transitivity",
    "square_clustering",
    "generalized_degree",
)


def _make_flattened_cluster_router(_name):
    def _routed(*args, **kwargs):
        return getattr(_fnx_cluster, _name)(*args, **kwargs)

    _routed.__name__ = _name
    _routed.__qualname__ = _name
    _routed.__signature__ = _inspect.signature(getattr(_nx_algorithms, _name))
    return _routed


for _name in _FNX_FLATTENED_CLUSTER_NAMES:
    globals()[_name] = _make_flattened_cluster_router(_name)

# br-r37-c1-1s6cb: route nx.algorithms.centrality through the fnx-native
# top-level implementations (nx aliased it verbatim, so fnx.algorithms.
# centrality.betweenness_centrality ran nx's pure-Python Brandes on fnx
# views — 33x slower than fnx.betweenness_centrality).
import franken_networkx.centrality as _fnx_centrality
_sys.modules[f"{__name__}.centrality"] = _fnx_centrality
centrality = _fnx_centrality  # Override in module globals
_alias_nx_child_modules(
    "networkx.algorithms.centrality", f"{__name__}.centrality"
)


# Preserve the public signatures of the flattened centrality helpers while
# delegating at call time to the native leaf module, including its backend
# dispatch validation.


def approximate_current_flow_betweenness_centrality(
    G,
    normalized=True,
    weight=None,
    dtype=float,
    solver='full',
    epsilon=0.5,
    kmax=10000,
    seed=None,
    *,
    sample_weight=1,
    backend=None,
    **backend_kwargs,
):
    return _fnx_centrality.approximate_current_flow_betweenness_centrality(
        G=G,
        normalized=normalized,
        weight=weight,
        dtype=dtype,
        solver=solver,
        epsilon=epsilon,
        kmax=kmax,
        seed=seed,
        sample_weight=sample_weight,
        backend=backend,
        **backend_kwargs,
    )


def betweenness_centrality(
    G,
    k=None,
    normalized=True,
    weight=None,
    endpoints=False,
    seed=None,
    *,
    backend=None,
    **backend_kwargs,
):
    return _fnx_centrality.betweenness_centrality(
        G=G,
        k=k,
        normalized=normalized,
        weight=weight,
        endpoints=endpoints,
        seed=seed,
        backend=backend,
        **backend_kwargs,
    )


def betweenness_centrality_subset(
    G,
    sources,
    targets,
    normalized=False,
    weight=None,
    *,
    backend=None,
    **backend_kwargs,
):
    return _fnx_centrality.betweenness_centrality_subset(
        G=G,
        sources=sources,
        targets=targets,
        normalized=normalized,
        weight=weight,
        backend=backend,
        **backend_kwargs,
    )


def closeness_centrality(
    G,
    u=None,
    distance=None,
    wf_improved=True,
    *,
    backend=None,
    **backend_kwargs,
):
    return _fnx_centrality.closeness_centrality(
        G=G,
        u=u,
        distance=distance,
        wf_improved=wf_improved,
        backend=backend,
        **backend_kwargs,
    )


def communicability_betweenness_centrality(G, *, backend=None, **backend_kwargs):
    return _fnx_centrality.communicability_betweenness_centrality(
        G=G,
        backend=backend,
        **backend_kwargs,
    )


def current_flow_betweenness_centrality(
    G,
    normalized=True,
    weight=None,
    dtype=float,
    solver='full',
    *,
    backend=None,
    **backend_kwargs,
):
    return _fnx_centrality.current_flow_betweenness_centrality(
        G=G,
        normalized=normalized,
        weight=weight,
        dtype=dtype,
        solver=solver,
        backend=backend,
        **backend_kwargs,
    )


def current_flow_betweenness_centrality_subset(
    G,
    sources,
    targets,
    normalized=True,
    weight=None,
    dtype=float,
    solver='lu',
    *,
    backend=None,
    **backend_kwargs,
):
    return _fnx_centrality.current_flow_betweenness_centrality_subset(
        G=G,
        sources=sources,
        targets=targets,
        normalized=normalized,
        weight=weight,
        dtype=dtype,
        solver=solver,
        backend=backend,
        **backend_kwargs,
    )


def current_flow_closeness_centrality(
    G,
    weight=None,
    dtype=float,
    solver='lu',
    *,
    backend=None,
    **backend_kwargs,
):
    return _fnx_centrality.current_flow_closeness_centrality(
        G=G,
        weight=weight,
        dtype=dtype,
        solver=solver,
        backend=backend,
        **backend_kwargs,
    )


def degree_centrality(G, *, backend=None, **backend_kwargs):
    return _fnx_centrality.degree_centrality(
        G=G,
        backend=backend,
        **backend_kwargs,
    )


def dispersion(
    G,
    u=None,
    v=None,
    normalized=True,
    alpha=1.0,
    b=0.0,
    c=0.0,
    *,
    backend=None,
    **backend_kwargs,
):
    return _fnx_centrality.dispersion(
        G=G,
        u=u,
        v=v,
        normalized=normalized,
        alpha=alpha,
        b=b,
        c=c,
        backend=backend,
        **backend_kwargs,
    )


def edge_betweenness_centrality(
    G,
    k=None,
    normalized=True,
    weight=None,
    seed=None,
    *,
    backend=None,
    **backend_kwargs,
):
    return _fnx_centrality.edge_betweenness_centrality(
        G=G,
        k=k,
        normalized=normalized,
        weight=weight,
        seed=seed,
        backend=backend,
        **backend_kwargs,
    )


def edge_betweenness_centrality_subset(
    G,
    sources,
    targets,
    normalized=False,
    weight=None,
    *,
    backend=None,
    **backend_kwargs,
):
    return _fnx_centrality.edge_betweenness_centrality_subset(
        G=G,
        sources=sources,
        targets=targets,
        normalized=normalized,
        weight=weight,
        backend=backend,
        **backend_kwargs,
    )


def edge_current_flow_betweenness_centrality(
    G,
    normalized=True,
    weight=None,
    dtype=float,
    solver='full',
    *,
    backend=None,
    **backend_kwargs,
):
    return _fnx_centrality.edge_current_flow_betweenness_centrality(
        G=G,
        normalized=normalized,
        weight=weight,
        dtype=dtype,
        solver=solver,
        backend=backend,
        **backend_kwargs,
    )


def edge_current_flow_betweenness_centrality_subset(
    G,
    sources,
    targets,
    normalized=True,
    weight=None,
    dtype=float,
    solver='lu',
    *,
    backend=None,
    **backend_kwargs,
):
    return _fnx_centrality.edge_current_flow_betweenness_centrality_subset(
        G=G,
        sources=sources,
        targets=targets,
        normalized=normalized,
        weight=weight,
        dtype=dtype,
        solver=solver,
        backend=backend,
        **backend_kwargs,
    )


def edge_load_centrality(
    G,
    cutoff=False,
    *,
    backend=None,
    **backend_kwargs,
):
    return _fnx_centrality.edge_load_centrality(
        G=G,
        cutoff=cutoff,
        backend=backend,
        **backend_kwargs,
    )


def eigenvector_centrality(
    G,
    max_iter=100,
    tol=1e-06,
    nstart=None,
    weight=None,
    *,
    backend=None,
    **backend_kwargs,
):
    return _fnx_centrality.eigenvector_centrality(
        G=G,
        max_iter=max_iter,
        tol=tol,
        nstart=nstart,
        weight=weight,
        backend=backend,
        **backend_kwargs,
    )


def eigenvector_centrality_numpy(
    G,
    weight=None,
    max_iter=50,
    tol=0,
    *,
    backend=None,
    **backend_kwargs,
):
    return _fnx_centrality.eigenvector_centrality_numpy(
        G=G,
        weight=weight,
        max_iter=max_iter,
        tol=tol,
        backend=backend,
        **backend_kwargs,
    )


def estrada_index(G, *, backend=None, **backend_kwargs):
    return _fnx_centrality.estrada_index(
        G=G,
        backend=backend,
        **backend_kwargs,
    )


def global_reaching_centrality(
    G,
    weight=None,
    normalized=True,
    *,
    backend=None,
    **backend_kwargs,
):
    return _fnx_centrality.global_reaching_centrality(
        G=G,
        weight=weight,
        normalized=normalized,
        backend=backend,
        **backend_kwargs,
    )


def group_betweenness_centrality(
    G,
    C,
    normalized=True,
    weight=None,
    endpoints=False,
    *,
    backend=None,
    **backend_kwargs,
):
    return _fnx_centrality.group_betweenness_centrality(
        G=G,
        C=C,
        normalized=normalized,
        weight=weight,
        endpoints=endpoints,
        backend=backend,
        **backend_kwargs,
    )


def group_closeness_centrality(
    G,
    S,
    weight=None,
    *,
    backend=None,
    **backend_kwargs,
):
    return _fnx_centrality.group_closeness_centrality(
        G=G,
        S=S,
        weight=weight,
        backend=backend,
        **backend_kwargs,
    )


def group_degree_centrality(
    G,
    S,
    *,
    backend=None,
    **backend_kwargs,
):
    return _fnx_centrality.group_degree_centrality(
        G=G,
        S=S,
        backend=backend,
        **backend_kwargs,
    )


def group_in_degree_centrality(
    G,
    S,
    *,
    backend=None,
    **backend_kwargs,
):
    return _fnx_centrality.group_in_degree_centrality(
        G=G,
        S=S,
        backend=backend,
        **backend_kwargs,
    )


def group_out_degree_centrality(
    G,
    S,
    *,
    backend=None,
    **backend_kwargs,
):
    return _fnx_centrality.group_out_degree_centrality(
        G=G,
        S=S,
        backend=backend,
        **backend_kwargs,
    )


def harmonic_centrality(
    G,
    nbunch=None,
    distance=None,
    sources=None,
    *,
    backend=None,
    **backend_kwargs,
):
    return _fnx_centrality.harmonic_centrality(
        G=G,
        nbunch=nbunch,
        distance=distance,
        sources=sources,
        backend=backend,
        **backend_kwargs,
    )


def in_degree_centrality(G, *, backend=None, **backend_kwargs):
    return _fnx_centrality.in_degree_centrality(
        G=G,
        backend=backend,
        **backend_kwargs,
    )


def incremental_closeness_centrality(
    G,
    edge,
    prev_cc=None,
    insertion=True,
    wf_improved=True,
    *,
    backend=None,
    **backend_kwargs,
):
    return _fnx_centrality.incremental_closeness_centrality(
        G=G,
        edge=edge,
        prev_cc=prev_cc,
        insertion=insertion,
        wf_improved=wf_improved,
        backend=backend,
        **backend_kwargs,
    )


def information_centrality(
    G,
    weight=None,
    dtype=float,
    solver='lu',
    *,
    backend=None,
    **backend_kwargs,
):
    return _fnx_centrality.information_centrality(
        G=G,
        weight=weight,
        dtype=dtype,
        solver=solver,
        backend=backend,
        **backend_kwargs,
    )


def katz_centrality(
    G,
    alpha=0.1,
    beta=1.0,
    max_iter=1000,
    tol=1e-06,
    nstart=None,
    normalized=True,
    weight=None,
    *,
    backend=None,
    **backend_kwargs,
):
    return _fnx_centrality.katz_centrality(
        G=G,
        alpha=alpha,
        beta=beta,
        max_iter=max_iter,
        tol=tol,
        nstart=nstart,
        normalized=normalized,
        weight=weight,
        backend=backend,
        **backend_kwargs,
    )


def katz_centrality_numpy(
    G,
    alpha=0.1,
    beta=1.0,
    normalized=True,
    weight=None,
    *,
    backend=None,
    **backend_kwargs,
):
    return _fnx_centrality.katz_centrality_numpy(
        G=G,
        alpha=alpha,
        beta=beta,
        normalized=normalized,
        weight=weight,
        backend=backend,
        **backend_kwargs,
    )


def laplacian_centrality(
    G,
    normalized=True,
    nodelist=None,
    weight='weight',
    walk_type=None,
    alpha=0.95,
    *,
    backend=None,
    **backend_kwargs,
):
    return _fnx_centrality.laplacian_centrality(
        G=G,
        normalized=normalized,
        nodelist=nodelist,
        weight=weight,
        walk_type=walk_type,
        alpha=alpha,
        backend=backend,
        **backend_kwargs,
    )


def load_centrality(
    G,
    v=None,
    cutoff=None,
    normalized=True,
    weight=None,
    *,
    backend=None,
    **backend_kwargs,
):
    return _fnx_centrality.load_centrality(
        G=G,
        v=v,
        cutoff=cutoff,
        normalized=normalized,
        weight=weight,
        backend=backend,
        **backend_kwargs,
    )


def local_reaching_centrality(
    G,
    v,
    paths=None,
    weight=None,
    normalized=True,
    *,
    backend=None,
    **backend_kwargs,
):
    return _fnx_centrality.local_reaching_centrality(
        G=G,
        v=v,
        paths=paths,
        weight=weight,
        normalized=normalized,
        backend=backend,
        **backend_kwargs,
    )


def out_degree_centrality(G, *, backend=None, **backend_kwargs):
    return _fnx_centrality.out_degree_centrality(
        G=G,
        backend=backend,
        **backend_kwargs,
    )


def percolation_centrality(
    G,
    attribute='percolation',
    states=None,
    weight=None,
    *,
    backend=None,
    **backend_kwargs,
):
    return _fnx_centrality.percolation_centrality(
        G=G,
        attribute=attribute,
        states=states,
        weight=weight,
        backend=backend,
        **backend_kwargs,
    )


def prominent_group(
    G,
    k,
    weight=None,
    C=None,
    endpoints=False,
    normalized=True,
    greedy=False,
    *,
    backend=None,
    **backend_kwargs,
):
    return _fnx_centrality.prominent_group(
        G=G,
        k=k,
        weight=weight,
        C=C,
        endpoints=endpoints,
        normalized=normalized,
        greedy=greedy,
        backend=backend,
        **backend_kwargs,
    )


def second_order_centrality(
    G,
    weight='weight',
    *,
    backend=None,
    **backend_kwargs,
):
    return _fnx_centrality.second_order_centrality(
        G=G,
        weight=weight,
        backend=backend,
        **backend_kwargs,
    )


def subgraph_centrality(
    G,
    *,
    normalized=False,
    backend=None,
    **backend_kwargs,
):
    return _fnx_centrality.subgraph_centrality(
        G=G,
        normalized=normalized,
        backend=backend,
        **backend_kwargs,
    )


def subgraph_centrality_exp(
    G,
    *,
    normalized=False,
    backend=None,
    **backend_kwargs,
):
    return _fnx_centrality.subgraph_centrality_exp(
        G=G,
        normalized=normalized,
        backend=backend,
        **backend_kwargs,
    )


def trophic_differences(
    G,
    weight='weight',
    *,
    backend=None,
    **backend_kwargs,
):
    return _fnx_centrality.trophic_differences(
        G=G,
        weight=weight,
        backend=backend,
        **backend_kwargs,
    )


def trophic_incoherence_parameter(
    G,
    weight='weight',
    cannibalism=False,
    *,
    backend=None,
    **backend_kwargs,
):
    return _fnx_centrality.trophic_incoherence_parameter(
        G=G,
        weight=weight,
        cannibalism=cannibalism,
        backend=backend,
        **backend_kwargs,
    )


def trophic_levels(
    G,
    weight='weight',
    *,
    backend=None,
    **backend_kwargs,
):
    return _fnx_centrality.trophic_levels(
        G=G,
        weight=weight,
        backend=backend,
        **backend_kwargs,
    )


def voterank(
    G,
    number_of_nodes=None,
    *,
    backend=None,
    **backend_kwargs,
):
    return _fnx_centrality.voterank(
        G=G,
        number_of_nodes=number_of_nodes,
        backend=backend,
        **backend_kwargs,
    )

# br-r37-c1-muhsi: route nx.algorithms.distance_measures through fnx-native
# top-level (harmonic_diameter ran nx pure-Python on fnx views — 7.6x slower;
# the rest are 14-16x faster than genuine nx).
import franken_networkx.distance_measures as _fnx_distance_measures
_sys.modules[f"{__name__}.distance_measures"] = _fnx_distance_measures
distance_measures = _fnx_distance_measures  # Override in module globals
_alias_nx_child_modules(
    "networkx.algorithms.distance_measures", f"{__name__}.distance_measures"
)


def barycenter(G, weight=None, attr=None, sp=None, *, backend=None, **backend_kwargs):
    return _fnx_distance_measures.barycenter(
        G, weight=weight, attr=attr, sp=sp, backend=backend, **backend_kwargs
    )


def center(G, e=None, usebounds=False, weight=None, *, backend=None, **backend_kwargs):
    return _fnx_distance_measures.center(
        G, e=e, usebounds=usebounds, weight=weight, backend=backend, **backend_kwargs
    )


def diameter(G, e=None, usebounds=False, weight=None, *, backend=None, **backend_kwargs):
    return _fnx_distance_measures.diameter(
        G, e=e, usebounds=usebounds, weight=weight, backend=backend, **backend_kwargs
    )


def eccentricity(G, v=None, sp=None, weight=None, *, backend=None, **backend_kwargs):
    return _fnx_distance_measures.eccentricity(
        G, v=v, sp=sp, weight=weight, backend=backend, **backend_kwargs
    )


def effective_graph_resistance(
    G, weight=None, invert_weight=True, *, backend=None, **backend_kwargs
):
    return _fnx_distance_measures.effective_graph_resistance(
        G, weight=weight, invert_weight=invert_weight, backend=backend, **backend_kwargs
    )


def harmonic_diameter(G, sp=None, *, weight=None, backend=None, **backend_kwargs):
    return _fnx_distance_measures.harmonic_diameter(
        G, sp=sp, weight=weight, backend=backend, **backend_kwargs
    )


def kemeny_constant(G, *, weight=None, backend=None, **backend_kwargs):
    return _fnx_distance_measures.kemeny_constant(
        G, weight=weight, backend=backend, **backend_kwargs
    )


def periphery(G, e=None, usebounds=False, weight=None, *, backend=None, **backend_kwargs):
    return _fnx_distance_measures.periphery(
        G, e=e, usebounds=usebounds, weight=weight, backend=backend, **backend_kwargs
    )


def radius(G, e=None, usebounds=False, weight=None, *, backend=None, **backend_kwargs):
    return _fnx_distance_measures.radius(
        G, e=e, usebounds=usebounds, weight=weight, backend=backend, **backend_kwargs
    )


def resistance_distance(
    G, nodeA=None, nodeB=None, weight=None, invert_weight=True, *, backend=None, **backend_kwargs
):
    return _fnx_distance_measures.resistance_distance(
        G,
        nodeA=nodeA,
        nodeB=nodeB,
        weight=weight,
        invert_weight=invert_weight,
        backend=backend,
        **backend_kwargs,
    )

# br-r37-c1-muhsi: route nx.algorithms.link_analysis through fnx-native
# top-level (google_matrix ~1.4x; pagerank/hits already dispatch, neutral).
import franken_networkx.link_analysis as _fnx_link_analysis
_sys.modules[f"{__name__}.link_analysis"] = _fnx_link_analysis
link_analysis = _fnx_link_analysis  # Override in module globals
_alias_nx_child_modules(
    "networkx.algorithms.link_analysis", f"{__name__}.link_analysis"
)


def google_matrix(
    G,
    alpha=0.85,
    personalization=None,
    nodelist=None,
    weight="weight",
    dangling=None,
    *,
    backend=None,
    **backend_kwargs,
):
    return _fnx_link_analysis.google_matrix(
        G,
        alpha=alpha,
        personalization=personalization,
        nodelist=nodelist,
        weight=weight,
        dangling=dangling,
        backend=backend,
        **backend_kwargs,
    )


def pagerank(
    G,
    alpha=0.85,
    personalization=None,
    max_iter=100,
    tol=1e-06,
    nstart=None,
    weight="weight",
    dangling=None,
    *,
    backend=None,
    **backend_kwargs,
):
    return _fnx_link_analysis.pagerank(
        G,
        alpha=alpha,
        personalization=personalization,
        max_iter=max_iter,
        tol=tol,
        nstart=nstart,
        weight=weight,
        dangling=dangling,
        backend=backend,
        **backend_kwargs,
    )


def hits(
    G,
    max_iter=100,
    tol=1e-08,
    nstart=None,
    normalized=True,
    *,
    backend=None,
    **backend_kwargs,
):
    return _fnx_link_analysis.hits(
        G,
        max_iter=max_iter,
        tol=tol,
        nstart=nstart,
        normalized=normalized,
        backend=backend,
        **backend_kwargs,
    )


# br-r37-c1-asrt: route nx.algorithms.assortativity through fnx-native top-level
# (degree_pearson 5.8x, attribute/degree mixing matrices 4-7x — these did not
# dispatch to the fnx backend, so the submodule ran nx pure-Python on fnx views).
import franken_networkx.assortativity as _fnx_assortativity
_sys.modules[f"{__name__}.assortativity"] = _fnx_assortativity
assortativity = _fnx_assortativity  # Override in module globals
_alias_nx_child_modules(
    "networkx.algorithms.assortativity", f"{__name__}.assortativity"
)

# These common flattened spellings are native routes, but the generic
# flattened-name installer below would otherwise replace them with a
# ``*args, **kwargs`` wrapper. Keep the upstream signatures while resolving the
# leaf implementation when called so that backend validation stays in the
# assortativity module.
_FNX_FLATTENED_ASSORTATIVITY_NAMES = (
    "attribute_assortativity_coefficient",
    "attribute_mixing_dict",
    "attribute_mixing_matrix",
    "average_degree_connectivity",
    "average_neighbor_degree",
    "degree_assortativity_coefficient",
    "degree_mixing_dict",
    "degree_mixing_matrix",
    "degree_pearson_correlation_coefficient",
    "mixing_dict",
    "node_attribute_xy",
    "node_degree_xy",
    "numeric_assortativity_coefficient",
)


def _make_flattened_assortativity_router(_name):
    def _routed(*args, **kwargs):
        return getattr(_fnx_assortativity, _name)(*args, **kwargs)

    _routed.__name__ = _name
    _routed.__qualname__ = _name
    _routed.__signature__ = _inspect.signature(getattr(_nx_algorithms, _name))
    return _routed


for _name in _FNX_FLATTENED_ASSORTATIVITY_NAMES:
    globals()[_name] = _make_flattened_assortativity_router(_name)

import franken_networkx.summarization as _fnx_summarization
_sys.modules[f"{__name__}.summarization"] = _fnx_summarization
summarization = _fnx_summarization  # Override in module globals


def dedensify(G, threshold, prefix=None, copy=True, *, backend=None, **backend_kwargs):
    return _fnx_summarization.dedensify(
        G,
        threshold,
        prefix=prefix,
        copy=copy,
        backend=backend,
        **backend_kwargs,
    )


def snap_aggregation(
    G,
    node_attributes,
    edge_attributes=(),
    prefix="Supernode-",
    supernode_attribute="group",
    superedge_attribute="types",
    *,
    backend=None,
    **backend_kwargs,
):
    return _fnx_summarization.snap_aggregation(
        G,
        node_attributes,
        edge_attributes=edge_attributes,
        prefix=prefix,
        supernode_attribute=supernode_attribute,
        superedge_attribute=superedge_attribute,
        backend=backend,
        **backend_kwargs,
    )

import franken_networkx.moral as _fnx_moral
_sys.modules[f"{__name__}.moral"] = _fnx_moral
moral = _fnx_moral  # Override in module globals


def moral_graph(G, *, backend=None, **backend_kwargs):
    return _fnx_moral.moral_graph(G, backend=backend, **backend_kwargs)

import franken_networkx.tree as _fnx_tree
_sys.modules[f"{__name__}.tree"] = _fnx_tree
tree = _fnx_tree  # Override in module globals
_alias_nx_child_modules(
    "networkx.algorithms.tree", f"{__name__}.tree"
)


def maximum_spanning_edges(
    G,
    algorithm="kruskal",
    weight="weight",
    keys=True,
    data=True,
    ignore_nan=False,
    *,
    backend=None,
    **backend_kwargs,
):
    return _fnx_tree.maximum_spanning_edges(
        G,
        algorithm=algorithm,
        weight=weight,
        keys=keys,
        data=data,
        ignore_nan=ignore_nan,
        backend=backend,
        **backend_kwargs,
    )


def maximum_spanning_tree(
    G,
    weight="weight",
    algorithm="kruskal",
    ignore_nan=False,
    *,
    backend=None,
    **backend_kwargs,
):
    return _fnx_tree.maximum_spanning_tree(
        G,
        weight=weight,
        algorithm=algorithm,
        ignore_nan=ignore_nan,
        backend=backend,
        **backend_kwargs,
    )


def minimum_spanning_edges(
    G,
    algorithm="kruskal",
    weight="weight",
    keys=True,
    data=True,
    ignore_nan=False,
    *,
    backend=None,
    **backend_kwargs,
):
    return _fnx_tree.minimum_spanning_edges(
        G,
        algorithm=algorithm,
        weight=weight,
        keys=keys,
        data=data,
        ignore_nan=ignore_nan,
        backend=backend,
        **backend_kwargs,
    )


def minimum_spanning_tree(
    G,
    weight="weight",
    algorithm="kruskal",
    ignore_nan=False,
    *,
    backend=None,
    **backend_kwargs,
):
    return _fnx_tree.minimum_spanning_tree(
        G,
        weight=weight,
        algorithm=algorithm,
        ignore_nan=ignore_nan,
        backend=backend,
        **backend_kwargs,
    )


def number_of_spanning_trees(
    G, *, root=None, weight=None, backend=None, **backend_kwargs
):
    return _fnx_tree.number_of_spanning_trees(
        G, root=root, weight=weight, backend=backend, **backend_kwargs
    )


def partition_spanning_tree(
    G,
    minimum=True,
    weight="weight",
    partition="partition",
    ignore_nan=False,
    *,
    backend=None,
    **backend_kwargs,
):
    return _fnx_tree.partition_spanning_tree(
        G,
        minimum=minimum,
        weight=weight,
        partition=partition,
        ignore_nan=ignore_nan,
        backend=backend,
        **backend_kwargs,
    )


def random_spanning_tree(
    G, weight=None, *, multiplicative=True, seed=None, backend=None, **backend_kwargs
):
    return _fnx_tree.random_spanning_tree(
        G,
        weight=weight,
        multiplicative=multiplicative,
        seed=seed,
        backend=backend,
        **backend_kwargs,
    )


def from_nested_tuple(
    sequence, sensible_relabeling=False, *, backend=None, **backend_kwargs
):
    return _fnx_tree.from_nested_tuple(
        sequence,
        sensible_relabeling=sensible_relabeling,
        backend=backend,
        **backend_kwargs,
    )


def from_prufer_sequence(sequence, *, backend=None, **backend_kwargs):
    return _fnx_tree.from_prufer_sequence(
        sequence, backend=backend, **backend_kwargs
    )


def to_nested_tuple(
    T, root, canonical_form=False, *, backend=None, **backend_kwargs
):
    return _fnx_tree.to_nested_tuple(
        T, root, canonical_form=canonical_form, backend=backend, **backend_kwargs
    )


def to_prufer_sequence(T, *, backend=None, **backend_kwargs):
    return _fnx_tree.to_prufer_sequence(T, backend=backend, **backend_kwargs)


def is_arborescence(G, *, backend=None, **backend_kwargs):
    return _fnx_tree.is_arborescence(G, backend=backend, **backend_kwargs)


def is_branching(G, *, backend=None, **backend_kwargs):
    return _fnx_tree.is_branching(G, backend=backend, **backend_kwargs)


def is_forest(G, *, backend=None, **backend_kwargs):
    return _fnx_tree.is_forest(G, backend=backend, **backend_kwargs)


def is_tree(G, *, backend=None, **backend_kwargs):
    return _fnx_tree.is_tree(G, backend=backend, **backend_kwargs)


def maximum_branching(
    G,
    attr="weight",
    default=1,
    preserve_attrs=False,
    partition=None,
    *,
    backend=None,
    **backend_kwargs,
):
    return _fnx_tree.maximum_branching(
        G,
        attr=attr,
        default=default,
        preserve_attrs=preserve_attrs,
        partition=partition,
        backend=backend,
        **backend_kwargs,
    )


def maximum_spanning_arborescence(
    G,
    attr="weight",
    default=1,
    preserve_attrs=False,
    partition=None,
    *,
    backend=None,
    **backend_kwargs,
):
    return _fnx_tree.maximum_spanning_arborescence(
        G,
        attr=attr,
        default=default,
        preserve_attrs=preserve_attrs,
        partition=partition,
        backend=backend,
        **backend_kwargs,
    )


def minimum_branching(
    G,
    attr="weight",
    default=1,
    preserve_attrs=False,
    partition=None,
    *,
    backend=None,
    **backend_kwargs,
):
    return _fnx_tree.minimum_branching(
        G,
        attr=attr,
        default=default,
        preserve_attrs=preserve_attrs,
        partition=partition,
        backend=backend,
        **backend_kwargs,
    )


def minimum_spanning_arborescence(
    G,
    attr="weight",
    default=1,
    preserve_attrs=False,
    partition=None,
    *,
    backend=None,
    **backend_kwargs,
):
    return _fnx_tree.minimum_spanning_arborescence(
        G,
        attr=attr,
        default=default,
        preserve_attrs=preserve_attrs,
        partition=partition,
        backend=backend,
        **backend_kwargs,
    )


def join_trees(
    rooted_trees,
    *,
    label_attribute=None,
    first_label=0,
    backend=None,
    **backend_kwargs,
):
    return _fnx_tree.join_trees(
        rooted_trees,
        label_attribute=label_attribute,
        first_label=first_label,
        backend=backend,
        **backend_kwargs,
    )


def junction_tree(G, *, backend=None, **backend_kwargs):
    return _fnx_tree.junction_tree(G, backend=backend, **backend_kwargs)


import franken_networkx.flow as _fnx_flow
_sys.modules[f"{__name__}.flow"] = _fnx_flow
flow = _fnx_flow  # Override in module globals
_alias_nx_child_modules(
    "networkx.algorithms.flow", f"{__name__}.flow"
)


def cost_of_flow(G, flowDict, weight="weight", *, backend=None, **backend_kwargs):
    return _fnx_flow.cost_of_flow(
        G, flowDict, weight=weight, backend=backend, **backend_kwargs
    )


def max_flow_min_cost(
    G, s, t, capacity="capacity", weight="weight", *, backend=None, **backend_kwargs
):
    return _fnx_flow.max_flow_min_cost(
        G, s, t, capacity=capacity, weight=weight, backend=backend, **backend_kwargs
    )


def min_cost_flow(
    G, demand="demand", capacity="capacity", weight="weight", *, backend=None, **backend_kwargs
):
    return _fnx_flow.min_cost_flow(
        G, demand=demand, capacity=capacity, weight=weight, backend=backend, **backend_kwargs
    )


def min_cost_flow_cost(
    G, demand="demand", capacity="capacity", weight="weight", *, backend=None, **backend_kwargs
):
    return _fnx_flow.min_cost_flow_cost(
        G, demand=demand, capacity=capacity, weight=weight, backend=backend, **backend_kwargs
    )


def maximum_flow(
    flowG, _s, _t, capacity="capacity", flow_func=None, *, backend=None, **kwargs
):
    return _fnx_flow.maximum_flow(
        flowG, _s, _t, capacity=capacity, flow_func=flow_func, backend=backend, **kwargs
    )


def maximum_flow_value(
    flowG, _s, _t, capacity="capacity", flow_func=None, *, backend=None, **kwargs
):
    return _fnx_flow.maximum_flow_value(
        flowG, _s, _t, capacity=capacity, flow_func=flow_func, backend=backend, **kwargs
    )


def minimum_cut(
    flowG, _s, _t, capacity="capacity", flow_func=None, *, backend=None, **kwargs
):
    return _fnx_flow.minimum_cut(
        flowG, _s, _t, capacity=capacity, flow_func=flow_func, backend=backend, **kwargs
    )


def minimum_cut_value(
    flowG, _s, _t, capacity="capacity", flow_func=None, *, backend=None, **kwargs
):
    return _fnx_flow.minimum_cut_value(
        flowG, _s, _t, capacity=capacity, flow_func=flow_func, backend=backend, **kwargs
    )


from networkx.utils.heaps import BinaryHeap as _BinaryHeap


def capacity_scaling(
    G,
    demand="demand",
    capacity="capacity",
    weight="weight",
    heap=_BinaryHeap,
    *,
    backend=None,
    **backend_kwargs,
):
    return _fnx_flow.capacity_scaling(
        G,
        demand=demand,
        capacity=capacity,
        weight=weight,
        heap=heap,
        backend=backend,
        **backend_kwargs,
    )


def gomory_hu_tree(
    G, capacity="capacity", flow_func=None, *, backend=None, **backend_kwargs
):
    return _fnx_flow.gomory_hu_tree(
        G, capacity=capacity, flow_func=flow_func, backend=backend, **backend_kwargs
    )


def network_simplex(
    G, demand="demand", capacity="capacity", weight="weight", *, backend=None, **backend_kwargs
):
    return _fnx_flow.network_simplex(
        G, demand=demand, capacity=capacity, weight=weight, backend=backend, **backend_kwargs
    )


import franken_networkx.traversal as _fnx_traversal
_sys.modules[f"{__name__}.traversal"] = _fnx_traversal
traversal = _fnx_traversal  # Override in module globals
_alias_nx_child_modules(
    "networkx.algorithms.traversal", f"{__name__}.traversal"
)


def bfs_beam_edges(
    G, source, value, width=None, *, backend=None, **backend_kwargs
):
    return _fnx_traversal.bfs_beam_edges(
        G, source, value, width=width, backend=backend, **backend_kwargs
    )


def bfs_labeled_edges(G, sources, *, backend=None, **backend_kwargs):
    return _fnx_traversal.bfs_labeled_edges(
        G, sources, backend=backend, **backend_kwargs
    )


def generic_bfs_edges(
    G, source, neighbors=None, depth_limit=None, *, backend=None, **backend_kwargs
):
    return _fnx_traversal.generic_bfs_edges(
        G,
        source,
        neighbors=neighbors,
        depth_limit=depth_limit,
        backend=backend,
        **backend_kwargs,
    )


import franken_networkx.euler as _fnx_euler
_sys.modules[f"{__name__}.euler"] = _fnx_euler
euler = _fnx_euler  # Override in module globals


def eulerian_circuit(
    G, source=None, keys=False, *, backend=None, **backend_kwargs
):
    return _fnx_euler.eulerian_circuit(
        G, source=source, keys=keys, backend=backend, **backend_kwargs
    )


def eulerian_path(G, source=None, keys=False, *, backend=None, **backend_kwargs):
    return _fnx_euler.eulerian_path(
        G, source=source, keys=keys, backend=backend, **backend_kwargs
    )


def eulerize(G, *, backend=None, **backend_kwargs):
    return _fnx_euler.eulerize(G, backend=backend, **backend_kwargs)


def has_eulerian_path(G, source=None, *, backend=None, **backend_kwargs):
    return _fnx_euler.has_eulerian_path(
        G, source=source, backend=backend, **backend_kwargs
    )


def is_eulerian(G, *, backend=None, **backend_kwargs):
    return _fnx_euler.is_eulerian(G, backend=backend, **backend_kwargs)


def is_semieulerian(G, *, backend=None, **backend_kwargs):
    return _fnx_euler.is_semieulerian(G, backend=backend, **backend_kwargs)

import franken_networkx.sparsifiers as _fnx_sparsifiers
_sys.modules[f"{__name__}.sparsifiers"] = _fnx_sparsifiers
sparsifiers = _fnx_sparsifiers  # Override in module globals


def spanner(G, stretch, weight=None, seed=None, *, backend=None, **backend_kwargs):
    return _fnx_sparsifiers.spanner(
        G, stretch, weight=weight, seed=seed, backend=backend, **backend_kwargs
    )

import franken_networkx.triads as _fnx_triads
_sys.modules[f"{__name__}.triads"] = _fnx_triads
triads = _fnx_triads  # Override in module globals


def all_triads(G, *, backend=None, **backend_kwargs):
    return _fnx_triads.all_triads(G, backend=backend, **backend_kwargs)


def is_triad(G, *, backend=None, **backend_kwargs):
    return _fnx_triads.is_triad(G, backend=backend, **backend_kwargs)

import franken_networkx.threshold as _fnx_threshold
_sys.modules[f"{__name__}.threshold"] = _fnx_threshold
threshold = _fnx_threshold  # Override in module globals

import franken_networkx.dag as _fnx_dag
_sys.modules[f"{__name__}.dag"] = _fnx_dag
dag = _fnx_dag  # Override in module globals

import franken_networkx.chordal as _fnx_chordal
_sys.modules[f"{__name__}.chordal"] = _fnx_chordal
chordal = _fnx_chordal  # Override in module globals


def complete_to_chordal_graph(G, *, backend=None, **backend_kwargs):
    return _fnx_chordal.complete_to_chordal_graph(
        G, backend=backend, **backend_kwargs
    )


def find_induced_nodes(
    G, s, t, treewidth_bound=9223372036854775807, *, backend=None, **backend_kwargs
):
    return _fnx_chordal.find_induced_nodes(
        G, s, t, treewidth_bound=treewidth_bound, backend=backend, **backend_kwargs
    )


def is_chordal(G, *, backend=None, **backend_kwargs):
    return _fnx_chordal.is_chordal(G, backend=backend, **backend_kwargs)

import franken_networkx.core as _fnx_core
_sys.modules[f"{__name__}.core"] = _fnx_core
core = _fnx_core  # Override in module globals


def k_core(G, k=None, core_number=None, *, backend=None, **backend_kwargs):
    return _fnx_core.k_core(
        G, k=k, core_number=core_number, backend=backend, **backend_kwargs
    )


def k_corona(G, k, core_number=None, *, backend=None, **backend_kwargs):
    return _fnx_core.k_corona(
        G, k, core_number=core_number, backend=backend, **backend_kwargs
    )


def k_crust(G, k=None, core_number=None, *, backend=None, **backend_kwargs):
    return _fnx_core.k_crust(
        G, k=k, core_number=core_number, backend=backend, **backend_kwargs
    )


def k_shell(G, k=None, core_number=None, *, backend=None, **backend_kwargs):
    return _fnx_core.k_shell(
        G, k=k, core_number=core_number, backend=backend, **backend_kwargs
    )


def k_truss(G, k, *, backend=None, **backend_kwargs):
    return _fnx_core.k_truss(G, k, backend=backend, **backend_kwargs)


def onion_layers(G, *, backend=None, **backend_kwargs):
    return _fnx_core.onion_layers(G, backend=backend, **backend_kwargs)

import franken_networkx.hybrid as _fnx_hybrid
_sys.modules[f"{__name__}.hybrid"] = _fnx_hybrid
hybrid = _fnx_hybrid  # Override in module globals


def is_kl_connected(G, k, l, low_memory=False, *, backend=None, **backend_kwargs):
    return _fnx_hybrid.is_kl_connected(
        G, k, l, low_memory=low_memory, backend=backend, **backend_kwargs
    )


def kl_connected_subgraph(
    G, k, l, low_memory=False, same_as_graph=False, *, backend=None, **backend_kwargs
):
    return _fnx_hybrid.kl_connected_subgraph(
        G,
        k,
        l,
        low_memory=low_memory,
        same_as_graph=same_as_graph,
        backend=backend,
        **backend_kwargs,
    )

import franken_networkx.tournament as _fnx_tournament
_sys.modules[f"{__name__}.tournament"] = _fnx_tournament
tournament = _fnx_tournament  # Override in module globals


def is_tournament(G, *, backend=None, **backend_kwargs):
    return _fnx_tournament.is_tournament(G, backend=backend, **backend_kwargs)

import franken_networkx.smallworld as _fnx_smallworld
_sys.modules[f"{__name__}.smallworld"] = _fnx_smallworld
smallworld = _fnx_smallworld  # Override in module globals


def lattice_reference(
    G, niter=5, D=None, connectivity=True, seed=None, *, backend=None, **backend_kwargs
):
    return _fnx_smallworld.lattice_reference(
        G,
        niter=niter,
        D=D,
        connectivity=connectivity,
        seed=seed,
        backend=backend,
        **backend_kwargs,
    )


def omega(G, niter=5, nrand=10, seed=None, *, backend=None, **backend_kwargs):
    return _fnx_smallworld.omega(
        G, niter=niter, nrand=nrand, seed=seed, backend=backend, **backend_kwargs
    )


def random_reference(
    G, niter=1, connectivity=True, seed=None, *, backend=None, **backend_kwargs
):
    return _fnx_smallworld.random_reference(
        G,
        niter=niter,
        connectivity=connectivity,
        seed=seed,
        backend=backend,
        **backend_kwargs,
    )


def sigma(G, niter=100, nrand=10, seed=None, *, backend=None, **backend_kwargs):
    return _fnx_smallworld.sigma(
        G, niter=niter, nrand=nrand, seed=seed, backend=backend, **backend_kwargs
    )

import franken_networkx.regular as _fnx_regular
_sys.modules[f"{__name__}.regular"] = _fnx_regular
regular = _fnx_regular  # Override in module globals


def is_k_regular(G, k, *, backend=None, **backend_kwargs):
    return _fnx_regular.is_k_regular(G, k, backend=backend, **backend_kwargs)


def is_regular(G, *, backend=None, **backend_kwargs):
    return _fnx_regular.is_regular(G, backend=backend, **backend_kwargs)


def k_factor(G, k, matching_weight="weight", *, backend=None, **backend_kwargs):
    return _fnx_regular.k_factor(
        G, k, matching_weight=matching_weight, backend=backend, **backend_kwargs
    )

import franken_networkx.swap as _fnx_swap
_sys.modules[f"{__name__}.swap"] = _fnx_swap
swap = _fnx_swap  # Override in module globals


def connected_double_edge_swap(
    G, nswap=1, _window_threshold=3, seed=None, *, backend=None, **backend_kwargs
):
    return _fnx_swap.connected_double_edge_swap(
        G,
        nswap=nswap,
        _window_threshold=_window_threshold,
        seed=seed,
        backend=backend,
        **backend_kwargs,
    )


def directed_edge_swap(
    G, *, nswap=1, max_tries=100, seed=None, backend=None, **backend_kwargs
):
    return _fnx_swap.directed_edge_swap(
        G,
        nswap=nswap,
        max_tries=max_tries,
        seed=seed,
        backend=backend,
        **backend_kwargs,
    )


def double_edge_swap(
    G, nswap=1, max_tries=100, seed=None, *, backend=None, **backend_kwargs
):
    return _fnx_swap.double_edge_swap(
        G,
        nswap=nswap,
        max_tries=max_tries,
        seed=seed,
        backend=backend,
        **backend_kwargs,
    )

import franken_networkx.planarity as _fnx_planarity
_sys.modules[f"{__name__}.planarity"] = _fnx_planarity
planarity = _fnx_planarity  # Override in module globals


def check_planarity(G, counterexample=False, *, backend=None, **backend_kwargs):
    return _fnx_planarity.check_planarity(
        G, counterexample=counterexample, backend=backend, **backend_kwargs
    )


def is_planar(G, *, backend=None, **backend_kwargs):
    return _fnx_planarity.is_planar(G, backend=backend, **backend_kwargs)

import franken_networkx.components as _fnx_components
_sys.modules[f"{__name__}.components"] = _fnx_components
components = _fnx_components  # Override in module globals
_alias_nx_child_modules(
    "networkx.algorithms.components", f"{__name__}.components"
)


def condensation(G, scc=None, *, backend=None, **backend_kwargs):
    return _fnx_components.condensation(
        G, scc=scc, backend=backend, **backend_kwargs
    )


def is_strongly_connected(G, *, backend=None, **backend_kwargs):
    return _fnx_components.is_strongly_connected(
        G, backend=backend, **backend_kwargs
    )


def kosaraju_strongly_connected_components(
    G, source=None, *, backend=None, **backend_kwargs
):
    return _fnx_components.kosaraju_strongly_connected_components(
        G, source=source, backend=backend, **backend_kwargs
    )


def number_strongly_connected_components(G, *, backend=None, **backend_kwargs):
    return _fnx_components.number_strongly_connected_components(
        G, backend=backend, **backend_kwargs
    )


def strongly_connected_components(G, *, backend=None, **backend_kwargs):
    return _fnx_components.strongly_connected_components(
        G, backend=backend, **backend_kwargs
    )


def articulation_points(G, *, backend=None, **backend_kwargs):
    return _fnx_components.articulation_points(
        G, backend=backend, **backend_kwargs
    )


def biconnected_component_edges(G, *, backend=None, **backend_kwargs):
    return _fnx_components.biconnected_component_edges(
        G, backend=backend, **backend_kwargs
    )


def biconnected_components(G, *, backend=None, **backend_kwargs):
    return _fnx_components.biconnected_components(
        G, backend=backend, **backend_kwargs
    )


def is_biconnected(G, *, backend=None, **backend_kwargs):
    return _fnx_components.is_biconnected(
        G, backend=backend, **backend_kwargs
    )


def connected_components(G, *, backend=None, **backend_kwargs):
    return _fnx_components.connected_components(
        G, backend=backend, **backend_kwargs
    )


def is_connected(G, *, backend=None, **backend_kwargs):
    return _fnx_components.is_connected(
        G, backend=backend, **backend_kwargs
    )


def node_connected_component(G, n, *, backend=None, **backend_kwargs):
    return _fnx_components.node_connected_component(
        G, n, backend=backend, **backend_kwargs
    )


def number_connected_components(G, *, backend=None, **backend_kwargs):
    return _fnx_components.number_connected_components(
        G, backend=backend, **backend_kwargs
    )


def attracting_components(G, *, backend=None, **backend_kwargs):
    return _fnx_components.attracting_components(
        G, backend=backend, **backend_kwargs
    )


def is_attracting_component(G, *, backend=None, **backend_kwargs):
    return _fnx_components.is_attracting_component(
        G, backend=backend, **backend_kwargs
    )


def number_attracting_components(G, *, backend=None, **backend_kwargs):
    return _fnx_components.number_attracting_components(
        G, backend=backend, **backend_kwargs
    )


def is_weakly_connected(G, *, backend=None, **backend_kwargs):
    return _fnx_components.is_weakly_connected(
        G, backend=backend, **backend_kwargs
    )


def number_weakly_connected_components(G, *, backend=None, **backend_kwargs):
    return _fnx_components.number_weakly_connected_components(
        G, backend=backend, **backend_kwargs
    )


def weakly_connected_components(G, *, backend=None, **backend_kwargs):
    return _fnx_components.weakly_connected_components(
        G, backend=backend, **backend_kwargs
    )


def is_semiconnected(G, *, backend=None, **backend_kwargs):
    return _fnx_components.is_semiconnected(
        G, backend=backend, **backend_kwargs
    )

_fnx_bridges = _importlib.import_module("franken_networkx.bridges")
_sys.modules[f"{__name__}.bridges"] = _fnx_bridges
bridges = _fnx_bridges  # Override in module globals


# ``bridges`` itself is a callable module, but these two flattened helpers are
# functions. Spell their public call contracts out so the generic native-router
# pass below does not demote them to ``*args, **kwargs``.
def has_bridges(G, root=None, *, backend=None, **backend_kwargs):
    return _fnx_bridges.has_bridges(
        G, root=root, backend=backend, **backend_kwargs
    )


def local_bridges(G, with_span=True, weight=None, *, backend=None, **backend_kwargs):
    return _fnx_bridges.local_bridges(
        G,
        with_span=with_span,
        weight=weight,
        backend=backend,
        **backend_kwargs,
    )


_fnx_asteroidal = _importlib.import_module("franken_networkx.asteroidal")
_sys.modules[f"{__name__}.asteroidal"] = _fnx_asteroidal
asteroidal = _fnx_asteroidal  # Override in module globals


def is_at_free(G, *, backend=None, **backend_kwargs):
    return _fnx_asteroidal.is_at_free(G, backend=backend, **backend_kwargs)


def find_asteroidal_triple(G, *, backend=None, **backend_kwargs):
    return _fnx_asteroidal.find_asteroidal_triple(
        G, backend=backend, **backend_kwargs
    )


_fnx_boundary = _importlib.import_module("franken_networkx.boundary")
_sys.modules[f"{__name__}.boundary"] = _fnx_boundary
boundary = _fnx_boundary  # Override in module globals


# Preserve the public contracts of the flattened boundary helpers while routing
# to the live fnx leaf module, instead of the generic native-router below.
def edge_boundary(
    G,
    nbunch1,
    nbunch2=None,
    data=False,
    keys=False,
    default=None,
    *,
    backend=None,
    **backend_kwargs,
):
    return _fnx_boundary.edge_boundary(
        G,
        nbunch1,
        nbunch2=nbunch2,
        data=data,
        keys=keys,
        default=default,
        backend=backend,
        **backend_kwargs,
    )


def node_boundary(G, nbunch1, nbunch2=None, *, backend=None, **backend_kwargs):
    return _fnx_boundary.node_boundary(
        G, nbunch1, nbunch2=nbunch2, backend=backend, **backend_kwargs
    )


_fnx_broadcasting = _importlib.import_module("franken_networkx.broadcasting")
_sys.modules[f"{__name__}.broadcasting"] = _fnx_broadcasting
broadcasting = _fnx_broadcasting  # Override in module globals


# Keep flattened broadcasting helpers on their exact public contracts while
# resolving the implementation through the fnx leaf module.
def tree_broadcast_center(G, *, backend=None, **backend_kwargs):
    return _fnx_broadcasting.tree_broadcast_center(
        G, backend=backend, **backend_kwargs
    )


def tree_broadcast_time(G, node=None, *, backend=None, **backend_kwargs):
    return _fnx_broadcasting.tree_broadcast_time(
        G, node=node, backend=backend, **backend_kwargs
    )


_fnx_communicability_alg = _importlib.import_module(
    "franken_networkx.communicability_alg"
)
_sys.modules[f"{__name__}.communicability_alg"] = _fnx_communicability_alg
communicability_alg = _fnx_communicability_alg  # Override in module globals


def communicability(G, *, backend=None, **backend_kwargs):
    return _fnx_communicability_alg.communicability(
        G, backend=backend, **backend_kwargs
    )


def communicability_exp(G, *, backend=None, **backend_kwargs):
    return _fnx_communicability_alg.communicability_exp(
        G, backend=backend, **backend_kwargs
    )


_fnx_covering = _importlib.import_module("franken_networkx.covering")
_sys.modules[f"{__name__}.covering"] = _fnx_covering
covering = _fnx_covering  # Override in module globals


def is_edge_cover(G, cover, *, backend=None, **backend_kwargs):
    return _fnx_covering.is_edge_cover(G, cover, backend=backend, **backend_kwargs)


def min_edge_cover(G, matching_algorithm=None, *, backend=None, **backend_kwargs):
    return _fnx_covering.min_edge_cover(
        G, matching_algorithm=matching_algorithm, backend=backend, **backend_kwargs
    )

_fnx_cuts = _importlib.import_module("franken_networkx.cuts")
_sys.modules[f"{__name__}.cuts"] = _fnx_cuts
cuts = _fnx_cuts  # Override in module globals

_FNX_FLATTENED_CUT_NAMES = (
    "boundary_expansion",
    "conductance",
    "cut_size",
    "edge_expansion",
    "mixing_expansion",
    "node_expansion",
    "normalized_cut_size",
    "volume",
)


def _make_flattened_cuts_router(_name):
    def _routed(*args, **kwargs):
        return getattr(_fnx_cuts, _name)(*args, **kwargs)

    _routed.__name__ = _name
    _routed.__qualname__ = _name
    _routed.__signature__ = _inspect.signature(getattr(_nx_algorithms, _name))
    return _routed


for _name in _FNX_FLATTENED_CUT_NAMES:
    globals()[_name] = _make_flattened_cuts_router(_name)

_FNX_FLATTENED_WEIGHTED_SHORTEST_PATH_NAMES = (
    "all_pairs_bellman_ford_path",
    "all_pairs_bellman_ford_path_length",
    "all_pairs_dijkstra",
    "all_pairs_dijkstra_path",
    "all_pairs_dijkstra_path_length",
    "bellman_ford_path",
    "bellman_ford_path_length",
    "bellman_ford_predecessor_and_distance",
    "bidirectional_dijkstra",
    "dijkstra_path",
    "dijkstra_path_length",
    "dijkstra_predecessor_and_distance",
    "find_negative_cycle",
    "goldberg_radzik",
    "johnson",
    "multi_source_dijkstra",
    "multi_source_dijkstra_path",
    "multi_source_dijkstra_path_length",
    "negative_edge_cycle",
    "single_source_bellman_ford",
    "single_source_bellman_ford_path",
    "single_source_bellman_ford_path_length",
    "single_source_dijkstra",
    "single_source_dijkstra_path",
    "single_source_dijkstra_path_length",
)


def _make_flattened_weighted_shortest_path_router(_name):
    def _routed(*args, **kwargs):
        import franken_networkx as _fnx_call

        return getattr(_fnx_call, _name)(*args, **kwargs)

    _routed.__name__ = _name
    _routed.__qualname__ = _name
    _routed.__signature__ = _inspect.signature(getattr(_nx_algorithms, _name))
    return _routed


for _name in _FNX_FLATTENED_WEIGHTED_SHORTEST_PATH_NAMES:
    globals()[_name] = _make_flattened_weighted_shortest_path_router(_name)


def all_pairs_shortest_path(G, cutoff=None, *, backend=None, **backend_kwargs):
    import franken_networkx as _fnx_call

    return _fnx_call.all_pairs_shortest_path(
        G, cutoff=cutoff, backend=backend, **backend_kwargs
    )


def all_pairs_shortest_path_length(
    G, cutoff=None, *, backend=None, **backend_kwargs
):
    import franken_networkx as _fnx_call

    return _fnx_call.all_pairs_shortest_path_length(
        G, cutoff=cutoff, backend=backend, **backend_kwargs
    )


def bidirectional_shortest_path(
    G, source, target, *, backend=None, **backend_kwargs
):
    import franken_networkx as _fnx_call

    return _fnx_call.bidirectional_shortest_path(
        G, source, target, backend=backend, **backend_kwargs
    )


def predecessor(
    G,
    source,
    target=None,
    cutoff=None,
    return_seen=None,
    *,
    backend=None,
    **backend_kwargs,
):
    import franken_networkx as _fnx_call

    return _fnx_call.predecessor(
        G,
        source,
        target=target,
        cutoff=cutoff,
        return_seen=return_seen,
        backend=backend,
        **backend_kwargs,
    )


def single_source_shortest_path(
    G, source, cutoff=None, *, backend=None, **backend_kwargs
):
    import franken_networkx as _fnx_call

    return _fnx_call.single_source_shortest_path(
        G, source, cutoff=cutoff, backend=backend, **backend_kwargs
    )


def single_source_shortest_path_length(
    G, source, cutoff=None, *, backend=None, **backend_kwargs
):
    import franken_networkx as _fnx_call

    return _fnx_call.single_source_shortest_path_length(
        G, source, cutoff=cutoff, backend=backend, **backend_kwargs
    )


def single_target_shortest_path(
    G, target, cutoff=None, *, backend=None, **backend_kwargs
):
    import franken_networkx as _fnx_call

    return _fnx_call.single_target_shortest_path(
        G, target, cutoff=cutoff, backend=backend, **backend_kwargs
    )


def single_target_shortest_path_length(
    G, target, cutoff=None, *, backend=None, **backend_kwargs
):
    import franken_networkx as _fnx_call

    return _fnx_call.single_target_shortest_path_length(
        G, target, cutoff=cutoff, backend=backend, **backend_kwargs
    )


def all_pairs_all_shortest_paths(
    G, weight=None, method="dijkstra", *, backend=None, **backend_kwargs
):
    import franken_networkx as _fnx_call

    return _fnx_call.all_pairs_all_shortest_paths(
        G, weight=weight, method=method, backend=backend, **backend_kwargs
    )


def all_shortest_paths(
    G,
    source,
    target,
    weight=None,
    method="dijkstra",
    *,
    backend=None,
    **backend_kwargs,
):
    import franken_networkx as _fnx_call

    return _fnx_call.all_shortest_paths(
        G,
        source,
        target,
        weight=weight,
        method=method,
        backend=backend,
        **backend_kwargs,
    )


def average_shortest_path_length(
    G, weight=None, method=None, *, backend=None, **backend_kwargs
):
    import franken_networkx as _fnx_call

    return _fnx_call.average_shortest_path_length(
        G, weight=weight, method=method, backend=backend, **backend_kwargs
    )


def has_path(G, source, target, *, backend=None, **backend_kwargs):
    import franken_networkx as _fnx_call

    return _fnx_call.has_path(
        G, source, target, backend=backend, **backend_kwargs
    )


def shortest_path(
    G,
    source=None,
    target=None,
    weight=None,
    method="dijkstra",
    *,
    backend=None,
    **backend_kwargs,
):
    import franken_networkx as _fnx_call

    return _fnx_call.shortest_path(
        G,
        source=source,
        target=target,
        weight=weight,
        method=method,
        backend=backend,
        **backend_kwargs,
    )


def shortest_path_length(
    G,
    source=None,
    target=None,
    weight=None,
    method="dijkstra",
    *,
    backend=None,
    **backend_kwargs,
):
    import franken_networkx as _fnx_call

    return _fnx_call.shortest_path_length(
        G,
        source=source,
        target=target,
        weight=weight,
        method=method,
        backend=backend,
        **backend_kwargs,
    )


def single_source_all_shortest_paths(
    G, source, weight=None, method="dijkstra", *, backend=None, **backend_kwargs
):
    import franken_networkx as _fnx_call

    return _fnx_call.single_source_all_shortest_paths(
        G, source, weight=weight, method=method, backend=backend, **backend_kwargs
    )


def floyd_warshall(G, weight="weight", *, backend=None, **backend_kwargs):
    import franken_networkx as _fnx_call

    return _fnx_call.floyd_warshall(
        G, weight=weight, backend=backend, **backend_kwargs
    )


def floyd_warshall_numpy(
    G, nodelist=None, weight="weight", *, backend=None, **backend_kwargs
):
    import franken_networkx as _fnx_call

    return _fnx_call.floyd_warshall_numpy(
        G,
        nodelist=nodelist,
        weight=weight,
        backend=backend,
        **backend_kwargs,
    )


def floyd_warshall_predecessor_and_distance(
    G, weight="weight", *, backend=None, **backend_kwargs
):
    import franken_networkx as _fnx_call

    return _fnx_call.floyd_warshall_predecessor_and_distance(
        G, weight=weight, backend=backend, **backend_kwargs
    )


def reconstruct_path(
    source, target, predecessors, *, backend=None, **backend_kwargs
):
    import franken_networkx as _fnx_call

    return _fnx_call.reconstruct_path(
        source,
        target,
        predecessors,
        backend=backend,
        **backend_kwargs,
    )


def astar_path(
    G,
    source,
    target,
    heuristic=None,
    weight="weight",
    *,
    cutoff=None,
    backend=None,
    **backend_kwargs,
):
    import franken_networkx as _fnx_call

    return _fnx_call.astar_path(
        G,
        source,
        target,
        heuristic=heuristic,
        weight=weight,
        cutoff=cutoff,
        backend=backend,
        **backend_kwargs,
    )


def astar_path_length(
    G,
    source,
    target,
    heuristic=None,
    weight="weight",
    *,
    cutoff=None,
    backend=None,
    **backend_kwargs,
):
    import franken_networkx as _fnx_call

    return _fnx_call.astar_path_length(
        G,
        source,
        target,
        heuristic=heuristic,
        weight=weight,
        cutoff=cutoff,
        backend=backend,
        **backend_kwargs,
    )


_FNX_FLATTENED_DAG_NAMES = (
    "all_topological_sorts",
    "ancestors",
    "antichains",
    "dag_longest_path",
    "dag_longest_path_length",
    "dag_to_branching",
    "descendants",
    "is_aperiodic",
    "is_directed_acyclic_graph",
    "lexicographical_topological_sort",
    "topological_generations",
    "topological_sort",
    "transitive_closure",
    "transitive_closure_dag",
    "transitive_reduction",
)


def _make_flattened_dag_router(_name):
    def _routed(*args, **kwargs):
        import franken_networkx as _fnx_call

        return getattr(_fnx_call, _name)(*args, **kwargs)

    _routed.__name__ = _name
    _routed.__qualname__ = _name
    _routed.__signature__ = _inspect.signature(getattr(_nx_algorithms, _name))
    return _routed


for _name in _FNX_FLATTENED_DAG_NAMES:
    globals()[_name] = _make_flattened_dag_router(_name)

_fnx_cycles = _importlib.import_module("franken_networkx.cycles")
_sys.modules[f"{__name__}.cycles"] = _fnx_cycles
cycles = _fnx_cycles  # Override in module globals


def chordless_cycles(G, length_bound=None, *, backend=None, **backend_kwargs):
    return _fnx_cycles.chordless_cycles(
        G, length_bound=length_bound, backend=backend, **backend_kwargs
    )


def cycle_basis(G, root=None, *, backend=None, **backend_kwargs):
    return _fnx_cycles.cycle_basis(G, root=root, backend=backend, **backend_kwargs)


def find_cycle(G, source=None, orientation=None, *, backend=None, **backend_kwargs):
    return _fnx_cycles.find_cycle(
        G, source=source, orientation=orientation, backend=backend, **backend_kwargs
    )


def girth(G, *, backend=None, **backend_kwargs):
    return _fnx_cycles.girth(G, backend=backend, **backend_kwargs)


def minimum_cycle_basis(G, weight=None, *, backend=None, **backend_kwargs):
    return _fnx_cycles.minimum_cycle_basis(
        G, weight=weight, backend=backend, **backend_kwargs
    )


def recursive_simple_cycles(G, *, backend=None, **backend_kwargs):
    return _fnx_cycles.recursive_simple_cycles(G, backend=backend, **backend_kwargs)


def simple_cycles(G, length_bound=None, *, backend=None, **backend_kwargs):
    return _fnx_cycles.simple_cycles(
        G, length_bound=length_bound, backend=backend, **backend_kwargs
    )

_fnx_dominance = _importlib.import_module("franken_networkx.dominance")
_sys.modules[f"{__name__}.dominance"] = _fnx_dominance
dominance = _fnx_dominance  # Override in module globals


def dominance_frontiers(G, start, *, backend=None, **backend_kwargs):
    return _fnx_dominance.dominance_frontiers(
        G, start, backend=backend, **backend_kwargs
    )


def immediate_dominators(G, start, *, backend=None, **backend_kwargs):
    return _fnx_dominance.immediate_dominators(
        G, start, backend=backend, **backend_kwargs
    )

_fnx_d_separation = _importlib.import_module("franken_networkx.d_separation")
_sys.modules[f"{__name__}.d_separation"] = _fnx_d_separation
d_separation = _fnx_d_separation  # Override in module globals


def find_minimal_d_separator(
    G, x, y, *, included=None, restricted=None, backend=None, **backend_kwargs
):
    return _fnx_d_separation.find_minimal_d_separator(
        G,
        x,
        y,
        included=included,
        restricted=restricted,
        backend=backend,
        **backend_kwargs,
    )


def is_d_separator(G, x, y, z, *, backend=None, **backend_kwargs):
    return _fnx_d_separation.is_d_separator(
        G, x, y, z, backend=backend, **backend_kwargs
    )


def is_minimal_d_separator(
    G, x, y, z, *, included=None, restricted=None, backend=None, **backend_kwargs
):
    return _fnx_d_separation.is_minimal_d_separator(
        G,
        x,
        y,
        z,
        included=included,
        restricted=restricted,
        backend=backend,
        **backend_kwargs,
    )


_fnx_distance_regular = _importlib.import_module("franken_networkx.distance_regular")
_sys.modules[f"{__name__}.distance_regular"] = _fnx_distance_regular
distance_regular = _fnx_distance_regular  # Override in module globals


def global_parameters(b, c):
    return _fnx_distance_regular.global_parameters(b, c)


def intersection_array(G, *, backend=None, **backend_kwargs):
    return _fnx_distance_regular.intersection_array(
        G, backend=backend, **backend_kwargs
    )


def is_distance_regular(G, *, backend=None, **backend_kwargs):
    return _fnx_distance_regular.is_distance_regular(
        G, backend=backend, **backend_kwargs
    )


def is_strongly_regular(G, *, backend=None, **backend_kwargs):
    return _fnx_distance_regular.is_strongly_regular(
        G, backend=backend, **backend_kwargs
    )


_fnx_dominating = _importlib.import_module("franken_networkx.dominating")
_sys.modules[f"{__name__}.dominating"] = _fnx_dominating
dominating = _fnx_dominating  # Override in module globals


def connected_dominating_set(G, *, backend=None, **backend_kwargs):
    return _fnx_dominating.connected_dominating_set(
        G, backend=backend, **backend_kwargs
    )


def dominating_set(G, start_with=None, *, backend=None, **backend_kwargs):
    return _fnx_dominating.dominating_set(
        G, start_with=start_with, backend=backend, **backend_kwargs
    )


def is_connected_dominating_set(G, nbunch, *, backend=None, **backend_kwargs):
    return _fnx_dominating.is_connected_dominating_set(
        G, nbunch, backend=backend, **backend_kwargs
    )


def is_dominating_set(G, nbunch, *, backend=None, **backend_kwargs):
    return _fnx_dominating.is_dominating_set(
        G, nbunch, backend=backend, **backend_kwargs
    )

_fnx_efficiency_measures = _importlib.import_module(
    "franken_networkx.efficiency_measures"
)
_sys.modules[f"{__name__}.efficiency_measures"] = _fnx_efficiency_measures
efficiency_measures = _fnx_efficiency_measures  # Override in module globals


# Keep the flattened ``algorithms`` spellings as explicit delegates rather than
# letting the generic native-router pass replace them with ``*args, **kwargs``.
# These three paths are commonly imported directly from ``networkx.algorithms``;
# their leaf module owns backend validation and the native implementation.
def efficiency(G, u, v, *, backend=None, **backend_kwargs):
    return _fnx_efficiency_measures.efficiency(
        G, u, v, backend=backend, **backend_kwargs
    )


def local_efficiency(G, *, backend=None, **backend_kwargs):
    return _fnx_efficiency_measures.local_efficiency(
        G, backend=backend, **backend_kwargs
    )


def global_efficiency(G, *, backend=None, **backend_kwargs):
    return _fnx_efficiency_measures.global_efficiency(
        G, backend=backend, **backend_kwargs
    )


_fnx_graph_hashing = _importlib.import_module("franken_networkx.graph_hashing")
_sys.modules[f"{__name__}.graph_hashing"] = _fnx_graph_hashing
graph_hashing = _fnx_graph_hashing  # Override in module globals


def weisfeiler_lehman_graph_hash(
    G,
    edge_attr=None,
    node_attr=None,
    iterations=3,
    digest_size=16,
    *,
    backend=None,
    **backend_kwargs,
):
    return _fnx_graph_hashing.weisfeiler_lehman_graph_hash(
        G,
        edge_attr=edge_attr,
        node_attr=node_attr,
        iterations=iterations,
        digest_size=digest_size,
        backend=backend,
        **backend_kwargs,
    )


def weisfeiler_lehman_subgraph_hashes(
    G,
    edge_attr=None,
    node_attr=None,
    iterations=3,
    digest_size=16,
    include_initial_labels=False,
    *,
    backend=None,
    **backend_kwargs,
):
    return _fnx_graph_hashing.weisfeiler_lehman_subgraph_hashes(
        G,
        edge_attr=edge_attr,
        node_attr=node_attr,
        iterations=iterations,
        digest_size=digest_size,
        include_initial_labels=include_initial_labels,
        backend=backend,
        **backend_kwargs,
    )

_fnx_graphical = _importlib.import_module("franken_networkx.graphical")
_sys.modules[f"{__name__}.graphical"] = _fnx_graphical
graphical = _fnx_graphical  # Override in module globals


# The flattened spellings are public entry points in their own right.  Keep
# their contracts at this boundary while leaving validation and the native
# implementation with the graphical leaf module.
def is_graphical(sequence, method="eg", *, backend=None, **backend_kwargs):
    return _fnx_graphical.is_graphical(
        sequence, method=method, backend=backend, **backend_kwargs
    )


def is_digraphical(in_sequence, out_sequence, *, backend=None, **backend_kwargs):
    return _fnx_graphical.is_digraphical(
        in_sequence, out_sequence, backend=backend, **backend_kwargs
    )


def is_multigraphical(sequence, *, backend=None, **backend_kwargs):
    return _fnx_graphical.is_multigraphical(
        sequence, backend=backend, **backend_kwargs
    )


def is_pseudographical(sequence, *, backend=None, **backend_kwargs):
    return _fnx_graphical.is_pseudographical(
        sequence, backend=backend, **backend_kwargs
    )


def is_valid_degree_sequence_erdos_gallai(
    deg_sequence, *, backend=None, **backend_kwargs
):
    return _fnx_graphical.is_valid_degree_sequence_erdos_gallai(
        deg_sequence, backend=backend, **backend_kwargs
    )


def is_valid_degree_sequence_havel_hakimi(
    deg_sequence, *, backend=None, **backend_kwargs
):
    return _fnx_graphical.is_valid_degree_sequence_havel_hakimi(
        deg_sequence, backend=backend, **backend_kwargs
    )

_fnx_hierarchy = _importlib.import_module("franken_networkx.hierarchy")
_sys.modules[f"{__name__}.hierarchy"] = _fnx_hierarchy
hierarchy = _fnx_hierarchy  # Override in module globals


def flow_hierarchy(G, weight=None, *, backend=None, **backend_kwargs):
    return _fnx_hierarchy.flow_hierarchy(
        G, weight=weight, backend=backend, **backend_kwargs
    )

_fnx_isolate = _importlib.import_module("franken_networkx.isolate")
_sys.modules[f"{__name__}.isolate"] = _fnx_isolate
isolate = _fnx_isolate  # Override in module globals


# ``isolates`` is already an explicit flattened delegate; spell out its two
# sibling entry points as well so introspection and keyword validation happen
# at the public algorithms namespace.
def is_isolate(G, n, *, backend=None, **backend_kwargs):
    return _fnx_isolate.is_isolate(G, n, backend=backend, **backend_kwargs)


def number_of_isolates(G, *, backend=None, **backend_kwargs):
    return _fnx_isolate.number_of_isolates(G, backend=backend, **backend_kwargs)

_fnx_link_prediction = _importlib.import_module("franken_networkx.link_prediction")
_sys.modules[f"{__name__}.link_prediction"] = _fnx_link_prediction
link_prediction = _fnx_link_prediction  # Override in module globals

_FNX_FLATTENED_LINK_PREDICTION_NAMES = (
    "resource_allocation_index",
    "jaccard_coefficient",
    "adamic_adar_index",
    "preferential_attachment",
    "cn_soundarajan_hopcroft",
    "ra_index_soundarajan_hopcroft",
    "within_inter_cluster",
    "common_neighbor_centrality",
)


def _make_flattened_link_prediction_router(_name):
    def _routed(*args, **kwargs):
        return getattr(_fnx_link_prediction, _name)(*args, **kwargs)

    _routed.__name__ = _name
    _routed.__qualname__ = _name
    _routed.__signature__ = _inspect.signature(getattr(_nx_algorithms, _name))
    return _routed


for _name in _FNX_FLATTENED_LINK_PREDICTION_NAMES:
    globals()[_name] = _make_flattened_link_prediction_router(_name)

_fnx_lowest_common_ancestors = _importlib.import_module(
    "franken_networkx.lowest_common_ancestors"
)
_sys.modules[f"{__name__}.lowest_common_ancestors"] = _fnx_lowest_common_ancestors
lowest_common_ancestors = _fnx_lowest_common_ancestors  # Override in module globals


def all_pairs_lowest_common_ancestor(
    G, pairs=None, *, backend=None, **backend_kwargs
):
    return _fnx_lowest_common_ancestors.all_pairs_lowest_common_ancestor(
        G, pairs=pairs, backend=backend, **backend_kwargs
    )


def lowest_common_ancestor(
    G, node1, node2, default=None, *, backend=None, **backend_kwargs
):
    return _fnx_lowest_common_ancestors.lowest_common_ancestor(
        G, node1, node2, default=default, backend=backend, **backend_kwargs
    )


def tree_all_pairs_lowest_common_ancestor(
    G, root=None, pairs=None, *, backend=None, **backend_kwargs
):
    return _fnx_lowest_common_ancestors.tree_all_pairs_lowest_common_ancestor(
        G, root=root, pairs=pairs, backend=backend, **backend_kwargs
    )


_fnx_matching = _importlib.import_module("franken_networkx.matching")
_sys.modules[f"{__name__}.matching"] = _fnx_matching
matching = _fnx_matching  # Override in module globals


def is_matching(G, matching, *, backend=None, **backend_kwargs):
    return _fnx_matching.is_matching(
        G, matching, backend=backend, **backend_kwargs
    )


def is_maximal_matching(G, matching, *, backend=None, **backend_kwargs):
    return _fnx_matching.is_maximal_matching(
        G, matching, backend=backend, **backend_kwargs
    )


def is_perfect_matching(G, matching, *, backend=None, **backend_kwargs):
    return _fnx_matching.is_perfect_matching(
        G, matching, backend=backend, **backend_kwargs
    )


def max_weight_matching(
    G, maxcardinality=False, weight="weight", *, backend=None, **backend_kwargs
):
    return _fnx_matching.max_weight_matching(
        G,
        maxcardinality=maxcardinality,
        weight=weight,
        backend=backend,
        **backend_kwargs,
    )


def maximal_matching(G, *, backend=None, **backend_kwargs):
    return _fnx_matching.maximal_matching(G, backend=backend, **backend_kwargs)


def min_weight_matching(
    G, weight="weight", *, backend=None, **backend_kwargs
):
    return _fnx_matching.min_weight_matching(
        G, weight=weight, backend=backend, **backend_kwargs
    )

_fnx_mis = _importlib.import_module("franken_networkx.mis")
_sys.modules[f"{__name__}.mis"] = _fnx_mis
mis = _fnx_mis  # Override in module globals


def maximal_independent_set(
    G, nodes=None, seed=None, *, backend=None, **backend_kwargs
):
    return _fnx_mis.maximal_independent_set(
        G, nodes=nodes, seed=seed, backend=backend, **backend_kwargs
    )

_fnx_non_randomness = _importlib.import_module("franken_networkx._non_randomness")
_sys.modules[f"{__name__}.non_randomness"] = _fnx_non_randomness
non_randomness = _fnx_non_randomness.non_randomness  # Match nx: function attr

_fnx_perfect_graph = _importlib.import_module("franken_networkx.perfect_graph")
_sys.modules[f"{__name__}.perfect_graph"] = _fnx_perfect_graph
perfect_graph = _fnx_perfect_graph  # Override in module globals


def is_perfect_graph(G, *, backend=None, **backend_kwargs):
    return _fnx_perfect_graph.is_perfect_graph(
        G, backend=backend, **backend_kwargs
    )

_fnx_polynomials = _importlib.import_module("franken_networkx.polynomials")
_sys.modules[f"{__name__}.polynomials"] = _fnx_polynomials
polynomials = _fnx_polynomials  # Override in module globals


def chromatic_polynomial(G, *, backend=None, **backend_kwargs):
    return _fnx_polynomials.chromatic_polynomial(
        G, backend=backend, **backend_kwargs
    )


def tutte_polynomial(G, *, backend=None, **backend_kwargs):
    return _fnx_polynomials.tutte_polynomial(
        G, backend=backend, **backend_kwargs
    )


_fnx_reciprocity = _importlib.import_module("franken_networkx.reciprocity")
_sys.modules[f"{__name__}.reciprocity"] = _fnx_reciprocity


def reciprocity(G, nodes=None, *, backend=None, **backend_kwargs):
    return _fnx_reciprocity.reciprocity(
        G, nodes=nodes, backend=backend, **backend_kwargs
    )


def overall_reciprocity(G, *, backend=None, **backend_kwargs):
    return _fnx_reciprocity.overall_reciprocity(
        G, backend=backend, **backend_kwargs
    )

_fnx_richclub = _importlib.import_module("franken_networkx.richclub")
_sys.modules[f"{__name__}.richclub"] = _fnx_richclub
richclub = _fnx_richclub  # Override in module globals


def rich_club_coefficient(
    G, normalized=True, Q=100, seed=None, *, backend=None, **backend_kwargs
):
    return _fnx_richclub.rich_club_coefficient(
        G,
        normalized=normalized,
        Q=Q,
        seed=seed,
        backend=backend,
        **backend_kwargs,
    )


_fnx_similarity = _importlib.import_module("franken_networkx.similarity")
_sys.modules[f"{__name__}.similarity"] = _fnx_similarity
similarity = _fnx_similarity  # Override in module globals


def generate_random_paths(
    G,
    sample_size,
    path_length=5,
    index_map=None,
    weight="weight",
    seed=None,
    *,
    source=None,
    backend=None,
    **backend_kwargs,
):
    return _fnx_similarity.generate_random_paths(
        G,
        sample_size,
        path_length=path_length,
        index_map=index_map,
        weight=weight,
        seed=seed,
        source=source,
        backend=backend,
        **backend_kwargs,
    )


def graph_edit_distance(
    G1,
    G2,
    node_match=None,
    edge_match=None,
    node_subst_cost=None,
    node_del_cost=None,
    node_ins_cost=None,
    edge_subst_cost=None,
    edge_del_cost=None,
    edge_ins_cost=None,
    roots=None,
    upper_bound=None,
    timeout=None,
    *,
    backend=None,
    **backend_kwargs,
):
    return _fnx_similarity.graph_edit_distance(
        G1,
        G2,
        node_match=node_match,
        edge_match=edge_match,
        node_subst_cost=node_subst_cost,
        node_del_cost=node_del_cost,
        node_ins_cost=node_ins_cost,
        edge_subst_cost=edge_subst_cost,
        edge_del_cost=edge_del_cost,
        edge_ins_cost=edge_ins_cost,
        roots=roots,
        upper_bound=upper_bound,
        timeout=timeout,
        backend=backend,
        **backend_kwargs,
    )


def optimal_edit_paths(
    G1,
    G2,
    node_match=None,
    edge_match=None,
    node_subst_cost=None,
    node_del_cost=None,
    node_ins_cost=None,
    edge_subst_cost=None,
    edge_del_cost=None,
    edge_ins_cost=None,
    upper_bound=None,
    *,
    backend=None,
    **backend_kwargs,
):
    return _fnx_similarity.optimal_edit_paths(
        G1,
        G2,
        node_match=node_match,
        edge_match=edge_match,
        node_subst_cost=node_subst_cost,
        node_del_cost=node_del_cost,
        node_ins_cost=node_ins_cost,
        edge_subst_cost=edge_subst_cost,
        edge_del_cost=edge_del_cost,
        edge_ins_cost=edge_ins_cost,
        upper_bound=upper_bound,
        backend=backend,
        **backend_kwargs,
    )


def optimize_edit_paths(
    G1,
    G2,
    node_match=None,
    edge_match=None,
    node_subst_cost=None,
    node_del_cost=None,
    node_ins_cost=None,
    edge_subst_cost=None,
    edge_del_cost=None,
    edge_ins_cost=None,
    upper_bound=None,
    strictly_decreasing=True,
    roots=None,
    timeout=None,
    *,
    backend=None,
    **backend_kwargs,
):
    return _fnx_similarity.optimize_edit_paths(
        G1,
        G2,
        node_match=node_match,
        edge_match=edge_match,
        node_subst_cost=node_subst_cost,
        node_del_cost=node_del_cost,
        node_ins_cost=node_ins_cost,
        edge_subst_cost=edge_subst_cost,
        edge_del_cost=edge_del_cost,
        edge_ins_cost=edge_ins_cost,
        upper_bound=upper_bound,
        strictly_decreasing=strictly_decreasing,
        roots=roots,
        timeout=timeout,
        backend=backend,
        **backend_kwargs,
    )


def optimize_graph_edit_distance(
    G1,
    G2,
    node_match=None,
    edge_match=None,
    node_subst_cost=None,
    node_del_cost=None,
    node_ins_cost=None,
    edge_subst_cost=None,
    edge_del_cost=None,
    edge_ins_cost=None,
    upper_bound=None,
    *,
    backend=None,
    **backend_kwargs,
):
    return _fnx_similarity.optimize_graph_edit_distance(
        G1,
        G2,
        node_match=node_match,
        edge_match=edge_match,
        node_subst_cost=node_subst_cost,
        node_del_cost=node_del_cost,
        node_ins_cost=node_ins_cost,
        edge_subst_cost=edge_subst_cost,
        edge_del_cost=edge_del_cost,
        edge_ins_cost=edge_ins_cost,
        upper_bound=upper_bound,
        backend=backend,
        **backend_kwargs,
    )


def panther_similarity(
    G,
    source,
    k=5,
    path_length=5,
    c=0.5,
    delta=0.1,
    eps=None,
    weight="weight",
    seed=None,
    *,
    backend=None,
    **backend_kwargs,
):
    return _fnx_similarity.panther_similarity(
        G,
        source,
        k=k,
        path_length=path_length,
        c=c,
        delta=delta,
        eps=eps,
        weight=weight,
        seed=seed,
        backend=backend,
        **backend_kwargs,
    )


def panther_vector_similarity(
    G,
    source,
    *,
    D=10,
    k=5,
    path_length=5,
    c=0.5,
    delta=0.1,
    eps=None,
    weight="weight",
    seed=None,
    backend=None,
    **backend_kwargs,
):
    return _fnx_similarity.panther_vector_similarity(
        G,
        source,
        D=D,
        k=k,
        path_length=path_length,
        c=c,
        delta=delta,
        eps=eps,
        weight=weight,
        seed=seed,
        backend=backend,
        **backend_kwargs,
    )


def simrank_similarity(
    G,
    source=None,
    target=None,
    importance_factor=0.9,
    max_iterations=1000,
    tolerance=0.0001,
    *,
    backend=None,
    **backend_kwargs,
):
    return _fnx_similarity.simrank_similarity(
        G,
        source=source,
        target=target,
        importance_factor=importance_factor,
        max_iterations=max_iterations,
        tolerance=tolerance,
        backend=backend,
        **backend_kwargs,
    )

_fnx_simple_paths = _importlib.import_module("franken_networkx.simple_paths")
_sys.modules[f"{__name__}.simple_paths"] = _fnx_simple_paths
simple_paths = _fnx_simple_paths  # Override in module globals


def all_simple_edge_paths(
    G, source, target, cutoff=None, *, backend=None, **backend_kwargs
):
    return _fnx_simple_paths.all_simple_edge_paths(
        G, source, target, cutoff=cutoff, backend=backend, **backend_kwargs
    )


def all_simple_paths(
    G, source, target, cutoff=None, *, backend=None, **backend_kwargs
):
    return _fnx_simple_paths.all_simple_paths(
        G, source, target, cutoff=cutoff, backend=backend, **backend_kwargs
    )


def is_simple_path(G, nodes, *, backend=None, **backend_kwargs):
    return _fnx_simple_paths.is_simple_path(
        G, nodes, backend=backend, **backend_kwargs
    )


def shortest_simple_paths(
    G, source, target, weight=None, *, backend=None, **backend_kwargs
):
    return _fnx_simple_paths.shortest_simple_paths(
        G, source, target, weight=weight, backend=backend, **backend_kwargs
    )

_fnx_smetric = _importlib.import_module("franken_networkx.smetric")
_sys.modules[f"{__name__}.smetric"] = _fnx_smetric
smetric = _fnx_smetric  # Override in module globals


def s_metric(G, *, backend=None, **backend_kwargs):
    return _fnx_smetric.s_metric(G, backend=backend, **backend_kwargs)


_fnx_structuralholes = _importlib.import_module("franken_networkx.structuralholes")
_sys.modules[f"{__name__}.structuralholes"] = _fnx_structuralholes
structuralholes = _fnx_structuralholes  # Override in module globals


def constraint(G, nodes=None, weight=None, *, backend=None, **backend_kwargs):
    return _fnx_structuralholes.constraint(
        G, nodes=nodes, weight=weight, backend=backend, **backend_kwargs
    )


def local_constraint(G, u, v, weight=None, *, backend=None, **backend_kwargs):
    return _fnx_structuralholes.local_constraint(
        G, u, v, weight=weight, backend=backend, **backend_kwargs
    )


def effective_size(G, nodes=None, weight=None, *, backend=None, **backend_kwargs):
    return _fnx_structuralholes.effective_size(
        G, nodes=nodes, weight=weight, backend=backend, **backend_kwargs
    )


_fnx_voronoi = _importlib.import_module("franken_networkx.voronoi")
_sys.modules[f"{__name__}.voronoi"] = _fnx_voronoi
voronoi = _fnx_voronoi  # Override in module globals


def voronoi_cells(
    G, center_nodes, weight="weight", *, backend=None, **backend_kwargs
):
    return _fnx_voronoi.voronoi_cells(
        G, center_nodes, weight=weight, backend=backend, **backend_kwargs
    )


_fnx_vitality = _importlib.import_module("franken_networkx.vitality")
_sys.modules[f"{__name__}.vitality"] = _fnx_vitality
vitality = _fnx_vitality  # Override in module globals


def closeness_vitality(
    G,
    node=None,
    weight=None,
    wiener_index=None,
    *,
    backend=None,
    **backend_kwargs,
):
    return _fnx_vitality.closeness_vitality(
        G,
        node=node,
        weight=weight,
        wiener_index=wiener_index,
        backend=backend,
        **backend_kwargs,
    )


_fnx_walks = _importlib.import_module("franken_networkx.walks")
_sys.modules[f"{__name__}.walks"] = _fnx_walks
walks = _fnx_walks  # Override in module globals


def number_of_walks(G, walk_length, *, backend=None, **backend_kwargs):
    return _fnx_walks.number_of_walks(
        G, walk_length, backend=backend, **backend_kwargs
    )


_fnx_chains = _importlib.import_module("franken_networkx.chains")
_sys.modules[f"{__name__}.chains"] = _fnx_chains
chains = _fnx_chains  # Override in module globals


def chain_decomposition(G, root=None, *, backend=None, **backend_kwargs):
    return _fnx_chains.chain_decomposition(
        G, root=root, backend=backend, **backend_kwargs
    )


_fnx_wiener = _importlib.import_module("franken_networkx.wiener")
_sys.modules[f"{__name__}.wiener"] = _fnx_wiener
wiener = _fnx_wiener  # Override in module globals


# Preserve the four flattened distance-index contracts rather than letting the
# generic native router obscure their optional weight and backend parameters.
def wiener_index(G, weight=None, *, backend=None, **backend_kwargs):
    return _fnx_wiener.wiener_index(
        G, weight=weight, backend=backend, **backend_kwargs
    )


def schultz_index(G, weight=None, *, backend=None, **backend_kwargs):
    return _fnx_wiener.schultz_index(
        G, weight=weight, backend=backend, **backend_kwargs
    )


def gutman_index(G, weight=None, *, backend=None, **backend_kwargs):
    return _fnx_wiener.gutman_index(
        G, weight=weight, backend=backend, **backend_kwargs
    )


def hyper_wiener_index(G, weight=None, *, backend=None, **backend_kwargs):
    return _fnx_wiener.hyper_wiener_index(
        G, weight=weight, backend=backend, **backend_kwargs
    )


# br-r37-c1-nhbni: ``from networkx.algorithms import *`` flattens networkx's
# functions into this namespace, so ``from franken_networkx.algorithms import X``
# resolved to nx's implementation wherever fnx has a native top-level ``fnx.X``.
# The submodule overrides above fix ``fnx.algorithms.<submodule>.X``; this routes
# the FLATTENED ``X`` names too. Computed dynamically (fnx is fully initialized by
# the time this subpackage is imported, verified reachable in a fresh process) so
# it auto-tracks fnx's native surface. Only names currently bound to nx's object
# are replaced. Functions use call-time closures (import-order robust); classes /
# exceptions use direct alias (a closure would break isinstance / ``except``).
def _install_fnx_native_algorithm_aliases():
    import inspect as _inspect
    import franken_networkx as _fnx_pkg
    import networkx as _nx_top

    def _make_router(_fn_name):
        def _routed(*args, **kwargs):
            import franken_networkx as _fnx_call

            return getattr(_fnx_call, _fn_name)(*args, **kwargs)

        _routed.__name__ = _fn_name
        _routed.__qualname__ = _fn_name
        _routed.__doc__ = (
            f"Route to ``franken_networkx.{_fn_name}`` (fnx-native). See "
            f"``networkx.algorithms.{_fn_name}`` for semantics."
        )
        return _routed

    for _name in list(__all__):
        if _name.startswith("_"):
            continue
        _fnx_obj = getattr(_fnx_pkg, _name, None)
        _nx_obj = getattr(_nx_top, _name, None)
        _current = globals().get(_name)
        # Replace only where the current binding IS networkx's and fnx has a
        # different native version.
        if _fnx_obj is None or _nx_obj is None:
            continue
        if _current is not _nx_obj or _fnx_obj is _nx_obj:
            continue
        if _inspect.isclass(_fnx_obj):
            globals()[_name] = _fnx_obj
        elif callable(_fnx_obj):
            globals()[_name] = _make_router(_name)


_install_fnx_native_algorithm_aliases()


# br-r37-c1-9hnq3: the installer above gives every routed function the signature
# `(*args, **kwargs)`, which the coverage matrix scores as PARTIAL coverage of
# the nx surface rather than present. Most routed names are already accounted for
# at that grade in the pinned numbers; `make_max_clique_graph` had regressed away
# from `present` on both this path and `franken_networkx.clique`, so it is spelled
# out. Attaching `__wrapped__` inside `_make_router` would fix the whole family at
# once and is probably right, but it would reclassify hundreds of paths and needs
# its own regenerated baseline — filed separately, not smuggled in here.
def make_max_clique_graph(G, create_using=None, *, backend=None, **backend_kwargs):
    """Return the maximal clique graph of the given graph.

    Routes to ``franken_networkx.make_max_clique_graph`` (fnx-native) with nx's
    signature spelled out. See ``networkx.algorithms.clique.make_max_clique_graph``
    for semantics.
    """
    import franken_networkx as _fnx_call

    return _fnx_call.make_max_clique_graph(
        G, create_using=create_using, backend=backend, **backend_kwargs
    )


# br-r37-c1-ozpfa: these colouring functions are native top-level routes, but
# the generic flattened-name installer above erases their public signatures.
# Keep the namespace spelling on the same dispatch path, including backend
# selection and rejection, with the exact NetworkX call contracts.
def equitable_color(G, num_colors, *, backend=None, **backend_kwargs):
    import franken_networkx as _fnx_call

    return _fnx_call.equitable_color(
        G, num_colors, backend=backend, **backend_kwargs
    )


def greedy_color(
    G, strategy="largest_first", interchange=False, *, backend=None, **backend_kwargs
):
    import franken_networkx as _fnx_call

    return _fnx_call.greedy_color(
        G,
        strategy=strategy,
        interchange=interchange,
        backend=backend,
        **backend_kwargs,
    )


def contracted_edge(
    G,
    edge,
    self_loops=True,
    copy=True,
    *,
    store_contraction_as="contraction",
    backend=None,
    **backend_kwargs,
):
    import franken_networkx as _fnx_call

    return _fnx_call.contracted_edge(
        G,
        edge,
        self_loops=self_loops,
        copy=copy,
        store_contraction_as=store_contraction_as,
        backend=backend,
        **backend_kwargs,
    )


def contracted_nodes(
    G,
    u,
    v,
    self_loops=True,
    copy=True,
    *,
    store_contraction_as="contraction",
    backend=None,
    **backend_kwargs,
):
    import franken_networkx as _fnx_call

    return _fnx_call.contracted_nodes(
        G,
        u,
        v,
        self_loops=self_loops,
        copy=copy,
        store_contraction_as=store_contraction_as,
        backend=backend,
        **backend_kwargs,
    )


def equivalence_classes(iterable, relation):
    import franken_networkx as _fnx_call

    return _fnx_call.equivalence_classes(iterable, relation)


def identified_nodes(
    G,
    u,
    v,
    self_loops=True,
    copy=True,
    *,
    store_contraction_as="contraction",
    backend=None,
    **backend_kwargs,
):
    import franken_networkx as _fnx_call

    return _fnx_call.identified_nodes(
        G,
        u,
        v,
        self_loops=self_loops,
        copy=copy,
        store_contraction_as=store_contraction_as,
        backend=backend,
        **backend_kwargs,
    )


def quotient_graph(
    G,
    partition,
    edge_relation=None,
    node_data=None,
    edge_data=None,
    weight="weight",
    relabel=False,
    create_using=None,
    *,
    backend=None,
    **backend_kwargs,
):
    import franken_networkx as _fnx_call

    return _fnx_call.quotient_graph(
        G,
        partition,
        edge_relation=edge_relation,
        node_data=node_data,
        edge_data=edge_data,
        weight=weight,
        relabel=relabel,
        create_using=create_using,
        backend=backend,
        **backend_kwargs,
    )


def isolates(G, *, backend=None, **backend_kwargs):
    import franken_networkx as _fnx_call

    _fnx_call._validate_backend_dispatch_keywords("isolates", backend, backend_kwargs)
    return _fnx_call.isolates(G)


def triad_type(G, *, backend=None, **backend_kwargs):
    import franken_networkx as _fnx_call

    return _fnx_call.triad_type(G, backend=backend, **backend_kwargs)


def triadic_census(G, nodelist=None, *, backend=None, **backend_kwargs):
    import franken_networkx as _fnx_call

    return _fnx_call.triadic_census(
        G, nodelist=nodelist, backend=backend, **backend_kwargs
    )


def triads_by_type(G, *, backend=None, **backend_kwargs):
    import franken_networkx as _fnx_call

    return _fnx_call.triads_by_type(G, backend=backend, **backend_kwargs)


def core_number(G, *, backend=None, **backend_kwargs):
    import franken_networkx as _fnx_call

    return _fnx_call.core_number(G, backend=backend, **backend_kwargs)


def chordal_graph_cliques(G, *, backend=None, **backend_kwargs):
    import franken_networkx as _fnx_call

    return _fnx_call.chordal_graph_cliques(G, backend=backend, **backend_kwargs)


def chordal_graph_treewidth(G, *, backend=None, **backend_kwargs):
    import franken_networkx as _fnx_call

    return _fnx_call.chordal_graph_treewidth(G, backend=backend, **backend_kwargs)


def bfs_edges(
    G,
    source,
    reverse=False,
    depth_limit=None,
    sort_neighbors=None,
    *,
    backend=None,
    **backend_kwargs,
):
    import franken_networkx as _fnx_call

    return _fnx_call.bfs_edges(
        G,
        source,
        reverse=reverse,
        depth_limit=depth_limit,
        sort_neighbors=sort_neighbors,
        backend=backend,
        **backend_kwargs,
    )


def bfs_predecessors(
    G,
    source,
    depth_limit=None,
    sort_neighbors=None,
    *,
    backend=None,
    **backend_kwargs,
):
    import franken_networkx as _fnx_call

    return _fnx_call.bfs_predecessors(
        G,
        source,
        depth_limit=depth_limit,
        sort_neighbors=sort_neighbors,
        backend=backend,
        **backend_kwargs,
    )


def bfs_successors(
    G,
    source,
    depth_limit=None,
    sort_neighbors=None,
    *,
    backend=None,
    **backend_kwargs,
):
    import franken_networkx as _fnx_call

    return _fnx_call.bfs_successors(
        G,
        source,
        depth_limit=depth_limit,
        sort_neighbors=sort_neighbors,
        backend=backend,
        **backend_kwargs,
    )


def bfs_tree(
    G,
    source,
    reverse=False,
    depth_limit=None,
    sort_neighbors=None,
    *,
    backend=None,
    **backend_kwargs,
):
    import franken_networkx as _fnx_call

    return _fnx_call.bfs_tree(
        G,
        source,
        reverse=reverse,
        depth_limit=depth_limit,
        sort_neighbors=sort_neighbors,
        backend=backend,
        **backend_kwargs,
    )


def dfs_edges(
    G,
    source=None,
    depth_limit=None,
    *,
    sort_neighbors=None,
    backend=None,
    **backend_kwargs,
):
    import franken_networkx as _fnx_call

    return _fnx_call.dfs_edges(
        G,
        source=source,
        depth_limit=depth_limit,
        sort_neighbors=sort_neighbors,
        backend=backend,
        **backend_kwargs,
    )


def dfs_predecessors(
    G,
    source=None,
    depth_limit=None,
    *,
    sort_neighbors=None,
    backend=None,
    **backend_kwargs,
):
    import franken_networkx as _fnx_call

    return _fnx_call.dfs_predecessors(
        G,
        source=source,
        depth_limit=depth_limit,
        sort_neighbors=sort_neighbors,
        backend=backend,
        **backend_kwargs,
    )


def dfs_successors(
    G,
    source=None,
    depth_limit=None,
    *,
    sort_neighbors=None,
    backend=None,
    **backend_kwargs,
):
    import franken_networkx as _fnx_call

    return _fnx_call.dfs_successors(
        G,
        source=source,
        depth_limit=depth_limit,
        sort_neighbors=sort_neighbors,
        backend=backend,
        **backend_kwargs,
    )


def dfs_tree(
    G,
    source=None,
    depth_limit=None,
    *,
    sort_neighbors=None,
    backend=None,
    **backend_kwargs,
):
    import franken_networkx as _fnx_call

    return _fnx_call.dfs_tree(
        G,
        source=source,
        depth_limit=depth_limit,
        sort_neighbors=sort_neighbors,
        backend=backend,
        **backend_kwargs,
    )


def edge_bfs(G, source=None, orientation=None, *, backend=None, **backend_kwargs):
    import franken_networkx as _fnx_call

    return _fnx_call.edge_bfs(
        G,
        source=source,
        orientation=orientation,
        backend=backend,
        **backend_kwargs,
    )


def edge_dfs(G, source=None, orientation=None, *, backend=None, **backend_kwargs):
    import franken_networkx as _fnx_call

    return _fnx_call.edge_dfs(
        G,
        source=source,
        orientation=orientation,
        backend=backend,
        **backend_kwargs,
    )


def dfs_preorder_nodes(
    G,
    source=None,
    depth_limit=None,
    *,
    sort_neighbors=None,
    backend=None,
    **backend_kwargs,
):
    import franken_networkx as _fnx_call

    return _fnx_call.dfs_preorder_nodes(
        G,
        source=source,
        depth_limit=depth_limit,
        sort_neighbors=sort_neighbors,
        backend=backend,
        **backend_kwargs,
    )


def dfs_postorder_nodes(
    G,
    source=None,
    depth_limit=None,
    *,
    sort_neighbors=None,
    backend=None,
    **backend_kwargs,
):
    import franken_networkx as _fnx_call

    return _fnx_call.dfs_postorder_nodes(
        G,
        source=source,
        depth_limit=depth_limit,
        sort_neighbors=sort_neighbors,
        backend=backend,
        **backend_kwargs,
    )


def dfs_labeled_edges(
    G,
    source=None,
    depth_limit=None,
    *,
    sort_neighbors=None,
    backend=None,
    **backend_kwargs,
):
    import franken_networkx as _fnx_call

    return _fnx_call.dfs_labeled_edges(
        G,
        source=source,
        depth_limit=depth_limit,
        sort_neighbors=sort_neighbors,
        backend=backend,
        **backend_kwargs,
    )


def bfs_layers(G, sources, *, backend=None, **backend_kwargs):
    import franken_networkx as _fnx_call

    return _fnx_call.bfs_layers(
        G,
        sources,
        backend=backend,
        **backend_kwargs,
    )


def descendants_at_distance(
    G, source, distance, *, backend=None, **backend_kwargs
):
    import franken_networkx as _fnx_call

    return _fnx_call.descendants_at_distance(
        G,
        source,
        distance,
        backend=backend,
        **backend_kwargs,
    )


def cd_index(
    G,
    node,
    time_delta,
    *,
    time="time",
    weight=None,
    backend=None,
    **backend_kwargs,
):
    import franken_networkx as _fnx_call

    return _fnx_call.cd_index(
        G,
        node,
        time_delta,
        time=time,
        weight=weight,
        backend=backend,
        **backend_kwargs,
    )


def combinatorial_embedding_to_pos(embedding, fully_triangulate=False):
    import franken_networkx as _fnx_call

    return _fnx_call.combinatorial_embedding_to_pos(
        embedding, fully_triangulate=fully_triangulate
    )


def __getattr__(name):
    import networkx.algorithms as _src

    try:
        return getattr(_src, name)
    except AttributeError as exc:
        raise AttributeError(
            f"module {__name__!r} has no attribute {name!r}"
        ) from exc


def __dir__():
    import networkx.algorithms as _src

    return sorted(set(globals()) | set(dir(_src)))
