"""FrankenNetworkX — High-performance NetworkX backend in Rust.

Can be used both as a NetworkX backend::

    import networkx as nx
    nx.betweenness_centrality(G, backend="franken_networkx")

and as a standalone library::

    import franken_networkx as fnx
    G = fnx.Graph()
    G.add_edge("a", "b")
    path = fnx.shortest_path(G, "a", "b")
"""

import importlib.machinery as _machinery
import sys as _sys
import types as _types
from pathlib import Path as _Path

_self_mod = _sys.modules[__name__]
_init_file = __file__
_init_doc = __doc__
_impl_dir = _Path(_init_file).resolve().parent / "_impl"
_impl_mod = _types.ModuleType(f"{__name__}._impl")
_impl_mod.__file__ = str(_impl_dir / "__init__.py")
_impl_mod.__package__ = f"{__name__}._impl"
_impl_mod.__path__ = []
_sys.modules[f"{__name__}._impl"] = _impl_mod
for _part_path in sorted(_impl_dir.glob("s*.py")):
    _sys.modules[f"{__name__}._impl.{_part_path.stem}"] = _self_mod
    _machinery.SourceFileLoader(__name__, str(_part_path)).exec_module(_self_mod)
__file__ = _init_file
__doc__ = _init_doc
# The implementation also imports _sys and _types into this shared namespace.
# Runtime algorithms still use them after the loader has finished.
del _machinery, _Path, _self_mod, _init_file, _init_doc, _impl_dir, _impl_mod, _part_path
