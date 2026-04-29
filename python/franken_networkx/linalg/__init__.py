"""Re-export of ``networkx.linalg`` for drop-in import-path compatibility.

br-r37-c1-hnv5y: see ``franken_networkx.utils`` docstring for the
parity-gap context. ``nx.linalg`` exposes adjacency / Laplacian /
modularity / algebraic-connectivity matrix builders that drop-in code
expects to be importable through the ``franken_networkx.linalg`` path.
"""

from networkx.linalg import *  # noqa: F401, F403


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
