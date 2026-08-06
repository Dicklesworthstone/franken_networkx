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
# Signatures are restated verbatim from networkx rather than forwarded through
# `*args, **kwargs`. A generic router is tempting and was tried first, but the
# coverage matrix classifies an entry point whose signature reads
# `(*args, **kwargs)` as PARTIAL coverage of the nx surface, not present — and it
# is right to: `help()`, `inspect.signature`, IDE completion and keyword-only
# enforcement all degrade. `to_dict_of_dicts` / `to_dict_of_lists` above already
# spell theirs out; these match.


def from_dict_of_dicts(
    d, create_using=None, multigraph_input=False, *, backend=None, **backend_kwargs
):
    """Return a graph from a dictionary of dictionaries."""
    import franken_networkx as _fnx

    return _fnx.from_dict_of_dicts(
        d,
        create_using=create_using,
        multigraph_input=multigraph_input,
        backend=backend,
        **backend_kwargs,
    )


def from_dict_of_lists(d, create_using=None, *, backend=None, **backend_kwargs):
    """Return a graph from a dictionary of lists."""
    import franken_networkx as _fnx

    return _fnx.from_dict_of_lists(
        d, create_using=create_using, backend=backend, **backend_kwargs
    )


def from_edgelist(edgelist, create_using=None, *, backend=None, **backend_kwargs):
    """Return a graph from a list of edges."""
    import franken_networkx as _fnx

    return _fnx.from_edgelist(
        edgelist, create_using=create_using, backend=backend, **backend_kwargs
    )


def to_edgelist(G, nodelist=None, *, backend=None, **backend_kwargs):
    """Return a list of edges in the graph."""
    import franken_networkx as _fnx

    return _fnx.to_edgelist(G, nodelist=nodelist, backend=backend, **backend_kwargs)


def to_networkx_graph(data, create_using=None, multigraph_input=False):
    """Make a graph from a known data structure.

    No ``backend`` keyword: networkx's own ``to_networkx_graph`` does not take
    one, and adding it here would diverge from the surface being mirrored.
    """
    import franken_networkx as _fnx

    return _fnx.to_networkx_graph(
        data, create_using=create_using, multigraph_input=multigraph_input
    )


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
