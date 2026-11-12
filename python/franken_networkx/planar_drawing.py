"""FrankenNetworkX planar_drawing algorithm submodule.

Mirrors ``networkx.algorithms.planar_drawing`` but routes functions that
networkx re-exports at top level or in algorithms to FrankenNetworkX's
optimized implementations.
"""

from __future__ import annotations

import importlib as _importlib

_nx_planar_drawing = _importlib.import_module("networkx.algorithms.planar_drawing")

import franken_networkx as _fnx

combinatorial_embedding_to_pos = _fnx.combinatorial_embedding_to_pos
set_position = _fnx._embedding_set_position
get_canonical_ordering = _fnx._embedding_canonical_ordering
triangulate_face = _fnx._embedding_triangulate_face
triangulate_embedding = _fnx._embedding_triangulate
make_bi_connected = _fnx._embedding_make_bi_connected

for _fn_name, _fn_obj in (
    ("set_position", set_position),
    ("get_canonical_ordering", get_canonical_ordering),
    ("triangulate_face", triangulate_face),
    ("triangulate_embedding", triangulate_embedding),
    ("make_bi_connected", make_bi_connected),
):
    _fn_obj.__name__ = _fn_name
    _fn_obj.__qualname__ = _fn_name
    _nx_fn = getattr(_nx_planar_drawing, _fn_name, None)
    if _nx_fn is not None:
        _fn_obj.__doc__ = _nx_fn.__doc__

__all__ = list(
    getattr(_nx_planar_drawing, "__all__", ("combinatorial_embedding_to_pos",))
)


def __getattr__(name):
    try:
        return getattr(_nx_planar_drawing, name)
    except AttributeError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc


def __dir__():
    public_globals = {name for name in globals() if not name.startswith("_")}
    public_upstream = {
        name for name in dir(_nx_planar_drawing) if not name.startswith("_")
    }
    return sorted(public_globals | public_upstream)
