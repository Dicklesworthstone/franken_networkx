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

from networkx.algorithms import *  # noqa: F401, F403


_FNX_OVERRIDE_SUBMODULES = {
    "asteroidal",
    "boundary",
    "broadcasting",
    "bipartite",
    "chains",
    "communicability_alg",
    "covering",
    "dominance",
    "dominating",
    "efficiency_measures",
    "hierarchy",
    "isolate",
    "wiener",
    "approximation",
    "minors",
    "operators",
    "clique",
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


_alias_nx_submodules(_importlib.import_module("networkx.algorithms"), __name__)

# Override bipartite submodule to use fnx's native implementation
# which wraps nx functions to return fnx graph types.
# This must happen AFTER the star import since `from networkx.algorithms import *`
# imports `bipartite` into the module namespace directly.
import franken_networkx.bipartite as _fnx_bipartite
_sys.modules[f"{__name__}.bipartite"] = _fnx_bipartite
bipartite = _fnx_bipartite  # Override in module globals

import franken_networkx.approximation as _fnx_approximation
_sys.modules[f"{__name__}.approximation"] = _fnx_approximation
approximation = _fnx_approximation  # Override in module globals

import franken_networkx.minors as _fnx_minors
_sys.modules[f"{__name__}.minors"] = _fnx_minors
minors = _fnx_minors  # Override in module globals

import franken_networkx.operators as _fnx_operators
_sys.modules[f"{__name__}.operators"] = _fnx_operators
operators = _fnx_operators  # Override in module globals

import franken_networkx.clique as _fnx_clique
_sys.modules[f"{__name__}.clique"] = _fnx_clique
clique = _fnx_clique  # Override in module globals

import franken_networkx.summarization as _fnx_summarization
_sys.modules[f"{__name__}.summarization"] = _fnx_summarization
summarization = _fnx_summarization  # Override in module globals

import franken_networkx.moral as _fnx_moral
_sys.modules[f"{__name__}.moral"] = _fnx_moral
moral = _fnx_moral  # Override in module globals

import franken_networkx.tree as _fnx_tree
_sys.modules[f"{__name__}.tree"] = _fnx_tree
tree = _fnx_tree  # Override in module globals

import franken_networkx.flow as _fnx_flow
_sys.modules[f"{__name__}.flow"] = _fnx_flow
flow = _fnx_flow  # Override in module globals

import franken_networkx.traversal as _fnx_traversal
_sys.modules[f"{__name__}.traversal"] = _fnx_traversal
traversal = _fnx_traversal  # Override in module globals

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

_fnx_dominance = _importlib.import_module("franken_networkx.dominance")
_sys.modules[f"{__name__}.dominance"] = _fnx_dominance
dominance = _fnx_dominance  # Override in module globals

_fnx_dominating = _importlib.import_module("franken_networkx.dominating")
_sys.modules[f"{__name__}.dominating"] = _fnx_dominating
dominating = _fnx_dominating  # Override in module globals

_fnx_efficiency_measures = _importlib.import_module(
    "franken_networkx.efficiency_measures"
)
_sys.modules[f"{__name__}.efficiency_measures"] = _fnx_efficiency_measures
efficiency_measures = _fnx_efficiency_measures  # Override in module globals

_fnx_hierarchy = _importlib.import_module("franken_networkx.hierarchy")
_sys.modules[f"{__name__}.hierarchy"] = _fnx_hierarchy
hierarchy = _fnx_hierarchy  # Override in module globals

_fnx_isolate = _importlib.import_module("franken_networkx.isolate")
_sys.modules[f"{__name__}.isolate"] = _fnx_isolate
isolate = _fnx_isolate  # Override in module globals

_fnx_chains = _importlib.import_module("franken_networkx.chains")
_sys.modules[f"{__name__}.chains"] = _fnx_chains
chains = _fnx_chains  # Override in module globals

_fnx_wiener = _importlib.import_module("franken_networkx.wiener")
_sys.modules[f"{__name__}.wiener"] = _fnx_wiener
wiener = _fnx_wiener  # Override in module globals


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
