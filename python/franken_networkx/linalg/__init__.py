"""Re-export of ``networkx.linalg`` for drop-in import-path compatibility.

br-r37-c1-hnv5y: see ``franken_networkx.utils`` docstring for the
parity-gap context. ``nx.linalg`` exposes adjacency / Laplacian /
modularity / algebraic-connectivity matrix builders that drop-in code
expects to be importable through the ``franken_networkx.linalg`` path.
"""

import networkx.linalg as _nx_linalg
from networkx.linalg import *  # noqa: F401, F403

__all__ = list(
    getattr(_nx_linalg, "__all__", ())
    or [name for name in dir(_nx_linalg) if not name.startswith("_")]
)


def _install_linalg_child_aliases():
    import importlib
    import pkgutil
    import sys
    import networkx.linalg as _src

    for info in pkgutil.iter_modules(_src.__path__):
        name = info.name
        if name == "tests" or name.startswith("_"):
            continue
        alias = f"{__name__}.{name}"
        if alias in sys.modules:
            continue
        module = importlib.import_module(f"networkx.linalg.{name}")
        sys.modules[alias] = module
        globals()[name] = module


def __getattr__(name):
    import networkx.linalg as _src

    try:
        return getattr(_src, name)
    except AttributeError as exc:
        raise AttributeError(
            f"module {__name__!r} has no attribute {name!r}"
        ) from exc


def __dir__():
    import networkx.linalg as _src

    return sorted(set(globals()) | set(dir(_src)))


_install_linalg_child_aliases()
