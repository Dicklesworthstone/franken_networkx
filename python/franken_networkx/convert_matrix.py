"""Re-export of ``networkx.convert_matrix`` for drop-in import-path compatibility.

br-r37-c1-hnv5y: see ``franken_networkx.utils`` docstring.
``nx.convert_matrix`` hosts numpy / scipy.sparse / pandas adjacency
builders (``to_numpy_array``, ``from_numpy_array``,
``to_scipy_sparse_array``, ``from_pandas_edgelist``, etc.).
"""

import franken_networkx as _fnx
import networkx.convert_matrix as _nx_convert_matrix
from networkx.convert_matrix import *  # noqa: F401, F403

__all__ = list(
    getattr(_nx_convert_matrix, "__all__", ())
    or [name for name in dir(_nx_convert_matrix) if not name.startswith("_")]
)

_FNX_NATIVE_CONVERT_MATRIX_NAMES = (
    "from_numpy_array",
    "from_pandas_adjacency",
    "from_pandas_edgelist",
    "from_scipy_sparse_array",
    "to_numpy_array",
    "to_pandas_adjacency",
    "to_pandas_edgelist",
    "to_scipy_sparse_array",
)

for _name in _FNX_NATIVE_CONVERT_MATRIX_NAMES:
    if hasattr(_fnx, _name):
        globals()[_name] = getattr(_fnx, _name)


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
