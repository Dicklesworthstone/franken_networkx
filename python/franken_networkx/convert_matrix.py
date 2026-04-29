"""Re-export of ``networkx.convert_matrix`` for drop-in import-path compatibility.

br-r37-c1-hnv5y: see ``franken_networkx.utils`` docstring.
``nx.convert_matrix`` hosts numpy / scipy.sparse / pandas adjacency
builders (``to_numpy_array``, ``from_numpy_array``,
``to_scipy_sparse_array``, ``from_pandas_edgelist``, etc.).
"""

from networkx.convert_matrix import *  # noqa: F401, F403


def __getattr__(name):
    import networkx.convert_matrix as _src

    try:
        return getattr(_src, name)
    except AttributeError as exc:
        raise AttributeError(
            f"module {__name__!r} has no attribute {name!r}"
        ) from exc


def __dir__():
    import networkx.convert_matrix as _src

    return sorted(set(globals()) | set(dir(_src)))
