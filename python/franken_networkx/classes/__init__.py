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
