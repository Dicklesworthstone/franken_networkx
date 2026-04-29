"""Re-export of ``networkx.convert`` for drop-in import-path compatibility.

br-r37-c1-hnv5y: see ``franken_networkx.utils`` docstring. ``nx.convert``
hosts ``to_dict_of_dicts``, ``from_dict_of_dicts``, ``to_dict_of_lists``,
``from_dict_of_lists``, ``to_edgelist``, ``from_edgelist``, etc.
"""

from networkx.convert import *  # noqa: F401, F403


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
