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


_FNX_OVERRIDE_SUBMODULES = {"bipartite", "approximation", "minors", "operators", "clique", "summarization", "moral"}


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
