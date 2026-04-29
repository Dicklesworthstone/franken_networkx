"""Re-export of ``networkx.relabel`` for drop-in import-path compatibility.

br-r37-c1-hnv5y: see ``franken_networkx.utils`` docstring. ``nx.relabel``
hosts ``relabel_nodes`` and ``convert_node_labels_to_integers``.
"""

from networkx.relabel import *  # noqa: F401, F403


def __getattr__(name):
    import networkx.relabel as _src

    try:
        return getattr(_src, name)
    except AttributeError as exc:
        raise AttributeError(
            f"module {__name__!r} has no attribute {name!r}"
        ) from exc


def __dir__():
    import networkx.relabel as _src

    return sorted(set(globals()) | set(dir(_src)))
