"""Re-export of ``networkx.convert`` for drop-in import-path compatibility.

br-r37-c1-hnv5y: see ``franken_networkx.utils`` docstring. ``nx.convert``
hosts ``to_dict_of_dicts``, ``from_dict_of_dicts``, ``to_dict_of_lists``,
``from_dict_of_lists``, ``to_edgelist``, ``from_edgelist``, etc.
"""

import networkx.convert as _nx_convert
from networkx.convert import *  # noqa: F401, F403

__all__ = list(
    getattr(_nx_convert, "__all__", ())
    or [name for name in dir(_nx_convert) if not name.startswith("_")]
)


def to_dict_of_dicts(G, nodelist=None, edge_data=None):
    """Return adjacency representation of graph as a dictionary of dictionaries.

    br-r37-c1-c2d-route: the ``from networkx.convert import *`` re-export left
    ``to_dict_of_dicts`` as nx's pure-Python version, which on an fnx graph
    walks ``G.adjacency()`` / ``G[u][v]`` views — ~14.8x slower than the native
    ``franken_networkx.to_dict_of_dicts`` (2.07ms vs 0.14ms at n=1000), which is
    byte-exact with nx (incl. ``nodelist`` / ``edge_data`` args and directed
    graphs). Route to it.
    """
    import franken_networkx as _fnx

    return _fnx.to_dict_of_dicts(G, nodelist=nodelist, edge_data=edge_data)


def to_dict_of_lists(G, nodelist=None):
    """Return adjacency representation of graph as a dictionary of lists.

    Keep the standalone ``franken_networkx.convert`` route on the same native
    implementation as ``franken_networkx.to_dict_of_lists`` rather than the
    NetworkX star-imported function.
    """
    import franken_networkx as _fnx

    return _fnx.to_dict_of_lists(G, nodelist=nodelist)


# br-r37-c1-2qsqf: the `from networkx.convert import *` above also left these
# five bound to nx's pure-Python versions while `franken_networkx.<name>` is a
# different, native object — so `from franken_networkx.convert import
# from_edgelist` silently handed back nx's implementation. Same bug class the
# two wrappers above already fix for `to_dict_of_dicts` / `to_dict_of_lists`,
# and the same routing the bead prescribes.
#
# Forwarded with `*args, **kwargs` rather than restated signatures on purpose:
# these take `create_using` / `multigraph_input` / `nodelist` and a restated
# signature is one upstream keyword away from silently diverging. The top-level
# functions own the contract; this module only decides WHICH object you get.
_FNX_NATIVE_CONVERT_NAMES = (
    "from_dict_of_dicts",
    "from_dict_of_lists",
    "from_edgelist",
    "to_edgelist",
    "to_networkx_graph",
)


def _make_fnx_convert_router(_fn_name):
    def _routed(*args, **kwargs):
        import franken_networkx as _fnx

        return getattr(_fnx, _fn_name)(*args, **kwargs)

    _routed.__name__ = _fn_name
    _routed.__qualname__ = _fn_name
    _routed.__doc__ = (
        f"Route to ``franken_networkx.{_fn_name}`` (fnx-native). See "
        f"``networkx.convert.{_fn_name}`` for semantics."
    )
    return _routed


for _name in _FNX_NATIVE_CONVERT_NAMES:
    globals()[_name] = _make_fnx_convert_router(_name)


def __getattr__(name):
    import networkx.convert as _src

    try:
        return getattr(_src, name)
    except AttributeError as exc:
        raise AttributeError(
            f"module {__name__!r} has no attribute {name!r}"
        ) from exc


def __dir__():
    import networkx.convert as _src

    return sorted(set(globals()) | set(dir(_src)))
