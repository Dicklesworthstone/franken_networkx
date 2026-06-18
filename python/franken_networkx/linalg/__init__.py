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

# br-r37-c1-f8j44: ``from networkx.linalg import *`` above binds networkx's
# matrix/spectral builders into this namespace, so ``franken_networkx.linalg.
# adjacency_matrix`` silently resolved to nx's implementation instead of fnx's
# native one (values match, but fnx's native path is the intended one). Route
# the names fnx provides natively to the top-level fnx version — the same fix
# p55u8 applied to ``convert_matrix``. Guarded by hasattr so a partially
# initialized package (circular import) just leaves the nx version in place.
_FNX_NATIVE_LINALG_NAMES = (
    "adjacency_matrix",
    "adjacency_spectrum",
    "algebraic_connectivity",
    "attr_matrix",
    "attr_sparse_matrix",
    "bethe_hessian_matrix",
    "bethe_hessian_spectrum",
    "directed_combinatorial_laplacian_matrix",
    "directed_laplacian_matrix",
    "directed_modularity_matrix",
    "fiedler_vector",
    "incidence_matrix",
    "laplacian_matrix",
    "laplacian_spectrum",
    "modularity_matrix",
    "modularity_spectrum",
    "normalized_laplacian_matrix",
    "normalized_laplacian_spectrum",
    "spectral_bisection",
    "spectral_ordering",
)


def _install_fnx_native_linalg_aliases():
    import franken_networkx as _fnx

    for _name in _FNX_NATIVE_LINALG_NAMES:
        if hasattr(_fnx, _name):
            globals()[_name] = getattr(_fnx, _name)


_install_fnx_native_linalg_aliases()


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
