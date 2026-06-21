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

_fnx_approximation = _importlib.import_module("franken_networkx.approximation")
_sys.modules[f"{__name__}.approximation"] = _fnx_approximation
approximation = _fnx_approximation  # Override in module globals
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

import franken_networkx.clique as _fnx_clique
_sys.modules[f"{__name__}.clique"] = _fnx_clique
clique = _fnx_clique  # Override in module globals

# br-r37-c1-nhbni: community/connectivity/isomorphism have native fnx submodules
# (fnx.community / fnx.connectivity / fnx.isomorphism) but were missing from the
# override set, so fnx.algorithms.<one> resolved to nx's. Map them to the fnx
# submodules like the 60+ others above.
import franken_networkx.connectivity as _fnx_connectivity
_sys.modules[f"{__name__}.connectivity"] = _fnx_connectivity
connectivity = _fnx_connectivity  # Override in module globals
_alias_nx_child_modules(
    "networkx.algorithms.connectivity", f"{__name__}.connectivity"
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

_fnx_cluster = _importlib.import_module("franken_networkx.cluster")
_sys.modules[f"{__name__}.cluster"] = _fnx_cluster
cluster = _fnx_cluster  # Override in module globals

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

# br-r37-c1-muhsi: route nx.algorithms.distance_measures through fnx-native
# top-level (harmonic_diameter ran nx pure-Python on fnx views — 7.6x slower;
# the rest are 14-16x faster than genuine nx).
import franken_networkx.distance_measures as _fnx_distance_measures
_sys.modules[f"{__name__}.distance_measures"] = _fnx_distance_measures
distance_measures = _fnx_distance_measures  # Override in module globals
_alias_nx_child_modules(
    "networkx.algorithms.distance_measures", f"{__name__}.distance_measures"
)

# br-r37-c1-muhsi: route nx.algorithms.link_analysis through fnx-native
# top-level (google_matrix ~1.4x; pagerank/hits already dispatch, neutral).
import franken_networkx.link_analysis as _fnx_link_analysis
_sys.modules[f"{__name__}.link_analysis"] = _fnx_link_analysis
link_analysis = _fnx_link_analysis  # Override in module globals
_alias_nx_child_modules(
    "networkx.algorithms.link_analysis", f"{__name__}.link_analysis"
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

import franken_networkx.summarization as _fnx_summarization
_sys.modules[f"{__name__}.summarization"] = _fnx_summarization
summarization = _fnx_summarization  # Override in module globals

import franken_networkx.moral as _fnx_moral
_sys.modules[f"{__name__}.moral"] = _fnx_moral
moral = _fnx_moral  # Override in module globals

import franken_networkx.tree as _fnx_tree
_sys.modules[f"{__name__}.tree"] = _fnx_tree
tree = _fnx_tree  # Override in module globals
_alias_nx_child_modules(
    "networkx.algorithms.tree", f"{__name__}.tree"
)

import franken_networkx.flow as _fnx_flow
_sys.modules[f"{__name__}.flow"] = _fnx_flow
flow = _fnx_flow  # Override in module globals
_alias_nx_child_modules(
    "networkx.algorithms.flow", f"{__name__}.flow"
)

import franken_networkx.traversal as _fnx_traversal
_sys.modules[f"{__name__}.traversal"] = _fnx_traversal
traversal = _fnx_traversal  # Override in module globals
_alias_nx_child_modules(
    "networkx.algorithms.traversal", f"{__name__}.traversal"
)

import franken_networkx.euler as _fnx_euler
_sys.modules[f"{__name__}.euler"] = _fnx_euler
euler = _fnx_euler  # Override in module globals

import franken_networkx.sparsifiers as _fnx_sparsifiers
_sys.modules[f"{__name__}.sparsifiers"] = _fnx_sparsifiers
sparsifiers = _fnx_sparsifiers  # Override in module globals

import franken_networkx.triads as _fnx_triads
_sys.modules[f"{__name__}.triads"] = _fnx_triads
triads = _fnx_triads  # Override in module globals

import franken_networkx.threshold as _fnx_threshold
_sys.modules[f"{__name__}.threshold"] = _fnx_threshold
threshold = _fnx_threshold  # Override in module globals

import franken_networkx.dag as _fnx_dag
_sys.modules[f"{__name__}.dag"] = _fnx_dag
dag = _fnx_dag  # Override in module globals

import franken_networkx.chordal as _fnx_chordal
_sys.modules[f"{__name__}.chordal"] = _fnx_chordal
chordal = _fnx_chordal  # Override in module globals

import franken_networkx.core as _fnx_core
_sys.modules[f"{__name__}.core"] = _fnx_core
core = _fnx_core  # Override in module globals

import franken_networkx.hybrid as _fnx_hybrid
_sys.modules[f"{__name__}.hybrid"] = _fnx_hybrid
hybrid = _fnx_hybrid  # Override in module globals

import franken_networkx.tournament as _fnx_tournament
_sys.modules[f"{__name__}.tournament"] = _fnx_tournament
tournament = _fnx_tournament  # Override in module globals

import franken_networkx.smallworld as _fnx_smallworld
_sys.modules[f"{__name__}.smallworld"] = _fnx_smallworld
smallworld = _fnx_smallworld  # Override in module globals

import franken_networkx.regular as _fnx_regular
_sys.modules[f"{__name__}.regular"] = _fnx_regular
regular = _fnx_regular  # Override in module globals

import franken_networkx.swap as _fnx_swap
_sys.modules[f"{__name__}.swap"] = _fnx_swap
swap = _fnx_swap  # Override in module globals

import franken_networkx.planarity as _fnx_planarity
_sys.modules[f"{__name__}.planarity"] = _fnx_planarity
planarity = _fnx_planarity  # Override in module globals

import franken_networkx.components as _fnx_components
_sys.modules[f"{__name__}.components"] = _fnx_components
components = _fnx_components  # Override in module globals
_alias_nx_child_modules(
    "networkx.algorithms.components", f"{__name__}.components"
)

_fnx_bridges = _importlib.import_module("franken_networkx.bridges")
_sys.modules[f"{__name__}.bridges"] = _fnx_bridges
bridges = _fnx_bridges  # Override in module globals

_fnx_asteroidal = _importlib.import_module("franken_networkx.asteroidal")
_sys.modules[f"{__name__}.asteroidal"] = _fnx_asteroidal
asteroidal = _fnx_asteroidal  # Override in module globals

_fnx_boundary = _importlib.import_module("franken_networkx.boundary")
_sys.modules[f"{__name__}.boundary"] = _fnx_boundary
boundary = _fnx_boundary  # Override in module globals

_fnx_broadcasting = _importlib.import_module("franken_networkx.broadcasting")
_sys.modules[f"{__name__}.broadcasting"] = _fnx_broadcasting
broadcasting = _fnx_broadcasting  # Override in module globals

_fnx_communicability_alg = _importlib.import_module(
    "franken_networkx.communicability_alg"
)
_sys.modules[f"{__name__}.communicability_alg"] = _fnx_communicability_alg
communicability_alg = _fnx_communicability_alg  # Override in module globals

_fnx_covering = _importlib.import_module("franken_networkx.covering")
_sys.modules[f"{__name__}.covering"] = _fnx_covering
covering = _fnx_covering  # Override in module globals

_fnx_cuts = _importlib.import_module("franken_networkx.cuts")
_sys.modules[f"{__name__}.cuts"] = _fnx_cuts
cuts = _fnx_cuts  # Override in module globals

_fnx_cycles = _importlib.import_module("franken_networkx.cycles")
_sys.modules[f"{__name__}.cycles"] = _fnx_cycles
cycles = _fnx_cycles  # Override in module globals

_fnx_dominance = _importlib.import_module("franken_networkx.dominance")
_sys.modules[f"{__name__}.dominance"] = _fnx_dominance
dominance = _fnx_dominance  # Override in module globals

_fnx_d_separation = _importlib.import_module("franken_networkx.d_separation")
_sys.modules[f"{__name__}.d_separation"] = _fnx_d_separation
d_separation = _fnx_d_separation  # Override in module globals

_fnx_distance_regular = _importlib.import_module("franken_networkx.distance_regular")
_sys.modules[f"{__name__}.distance_regular"] = _fnx_distance_regular
distance_regular = _fnx_distance_regular  # Override in module globals

_fnx_dominating = _importlib.import_module("franken_networkx.dominating")
_sys.modules[f"{__name__}.dominating"] = _fnx_dominating
dominating = _fnx_dominating  # Override in module globals

_fnx_efficiency_measures = _importlib.import_module(
    "franken_networkx.efficiency_measures"
)
_sys.modules[f"{__name__}.efficiency_measures"] = _fnx_efficiency_measures
efficiency_measures = _fnx_efficiency_measures  # Override in module globals

_fnx_graph_hashing = _importlib.import_module("franken_networkx.graph_hashing")
_sys.modules[f"{__name__}.graph_hashing"] = _fnx_graph_hashing
graph_hashing = _fnx_graph_hashing  # Override in module globals

_fnx_graphical = _importlib.import_module("franken_networkx.graphical")
_sys.modules[f"{__name__}.graphical"] = _fnx_graphical
graphical = _fnx_graphical  # Override in module globals

_fnx_hierarchy = _importlib.import_module("franken_networkx.hierarchy")
_sys.modules[f"{__name__}.hierarchy"] = _fnx_hierarchy
hierarchy = _fnx_hierarchy  # Override in module globals

_fnx_isolate = _importlib.import_module("franken_networkx.isolate")
_sys.modules[f"{__name__}.isolate"] = _fnx_isolate
isolate = _fnx_isolate  # Override in module globals

_fnx_link_prediction = _importlib.import_module("franken_networkx.link_prediction")
_sys.modules[f"{__name__}.link_prediction"] = _fnx_link_prediction
link_prediction = _fnx_link_prediction  # Override in module globals

_fnx_lowest_common_ancestors = _importlib.import_module(
    "franken_networkx.lowest_common_ancestors"
)
_sys.modules[f"{__name__}.lowest_common_ancestors"] = _fnx_lowest_common_ancestors
lowest_common_ancestors = _fnx_lowest_common_ancestors  # Override in module globals

_fnx_matching = _importlib.import_module("franken_networkx.matching")
_sys.modules[f"{__name__}.matching"] = _fnx_matching
matching = _fnx_matching  # Override in module globals

_fnx_mis = _importlib.import_module("franken_networkx.mis")
_sys.modules[f"{__name__}.mis"] = _fnx_mis
mis = _fnx_mis  # Override in module globals

_fnx_non_randomness = _importlib.import_module("franken_networkx._non_randomness")
_sys.modules[f"{__name__}.non_randomness"] = _fnx_non_randomness
non_randomness = _fnx_non_randomness.non_randomness  # Match nx: function attr

_fnx_perfect_graph = _importlib.import_module("franken_networkx.perfect_graph")
_sys.modules[f"{__name__}.perfect_graph"] = _fnx_perfect_graph
perfect_graph = _fnx_perfect_graph  # Override in module globals

_fnx_polynomials = _importlib.import_module("franken_networkx.polynomials")
_sys.modules[f"{__name__}.polynomials"] = _fnx_polynomials
polynomials = _fnx_polynomials  # Override in module globals

_fnx_reciprocity = _importlib.import_module("franken_networkx.reciprocity")
_sys.modules[f"{__name__}.reciprocity"] = _fnx_reciprocity
reciprocity = _fnx_reciprocity.reciprocity  # Match nx: function attr

_fnx_richclub = _importlib.import_module("franken_networkx.richclub")
_sys.modules[f"{__name__}.richclub"] = _fnx_richclub
richclub = _fnx_richclub  # Override in module globals

_fnx_similarity = _importlib.import_module("franken_networkx.similarity")
_sys.modules[f"{__name__}.similarity"] = _fnx_similarity
similarity = _fnx_similarity  # Override in module globals

_fnx_simple_paths = _importlib.import_module("franken_networkx.simple_paths")
_sys.modules[f"{__name__}.simple_paths"] = _fnx_simple_paths
simple_paths = _fnx_simple_paths  # Override in module globals

_fnx_smetric = _importlib.import_module("franken_networkx.smetric")
_sys.modules[f"{__name__}.smetric"] = _fnx_smetric
smetric = _fnx_smetric  # Override in module globals

_fnx_structuralholes = _importlib.import_module("franken_networkx.structuralholes")
_sys.modules[f"{__name__}.structuralholes"] = _fnx_structuralholes
structuralholes = _fnx_structuralholes  # Override in module globals

_fnx_voronoi = _importlib.import_module("franken_networkx.voronoi")
_sys.modules[f"{__name__}.voronoi"] = _fnx_voronoi
voronoi = _fnx_voronoi  # Override in module globals

_fnx_vitality = _importlib.import_module("franken_networkx.vitality")
_sys.modules[f"{__name__}.vitality"] = _fnx_vitality
vitality = _fnx_vitality  # Override in module globals

_fnx_walks = _importlib.import_module("franken_networkx.walks")
_sys.modules[f"{__name__}.walks"] = _fnx_walks
walks = _fnx_walks  # Override in module globals

_fnx_chains = _importlib.import_module("franken_networkx.chains")
_sys.modules[f"{__name__}.chains"] = _fnx_chains
chains = _fnx_chains  # Override in module globals

_fnx_wiener = _importlib.import_module("franken_networkx.wiener")
_sys.modules[f"{__name__}.wiener"] = _fnx_wiener
wiener = _fnx_wiener  # Override in module globals


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
