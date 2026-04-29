"""Algorithm functions — re-exports from ``networkx.algorithms``.

br-r37-c1-j54tp: see ``franken_networkx.generators`` docstring for the
parity-gap context. nx.algorithms exposes ~537 names (114 of them
nested submodules like ``approximation``, ``assortativity``, ``astar``);
they're all reachable via this submodule path.

Top-level functions (``franken_networkx.foo``) remain backed by the
fnx-native Rust ports / Python wrappers; this module is the nx-mirror
path for code that imports through ``franken_networkx.algorithms.X``.
"""

from networkx.algorithms import *  # noqa: F401, F403


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
