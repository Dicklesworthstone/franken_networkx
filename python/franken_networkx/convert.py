"""Re-export of ``networkx.convert`` for drop-in import-path compatibility.

br-r37-c1-hnv5y: see ``franken_networkx.utils`` docstring. ``nx.convert``
hosts ``to_dict_of_dicts``, ``from_dict_of_dicts``, ``to_dict_of_lists``,
``from_dict_of_lists``, ``to_edgelist``, ``from_edgelist``, etc.
"""

from networkx.convert import *  # noqa: F401, F403


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
