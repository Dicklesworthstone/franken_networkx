"""Re-export of ``networkx.relabel`` for drop-in import-path compatibility.

br-r37-c1-hnv5y: see ``franken_networkx.utils`` docstring. ``nx.relabel``
hosts ``relabel_nodes`` and ``convert_node_labels_to_integers``.
"""

import networkx.relabel as _nx_relabel
from networkx.relabel import *  # noqa: F401, F403

__all__ = list(
    getattr(_nx_relabel, "__all__", ())
    or [name for name in dir(_nx_relabel) if not name.startswith("_")]
)


def relabel_nodes(G, mapping, copy=True, *, backend=None, **backend_kwargs):
    """Relabel graph nodes via the fnx-native top-level implementation."""
    import franken_networkx as _fnx

    return _fnx.relabel_nodes(
        G,
        mapping,
        copy=copy,
        backend=backend,
        **backend_kwargs,
    )


def convert_node_labels_to_integers(
    G,
    first_label=0,
    ordering="default",
    label_attribute=None,
    *,
    backend=None,
    **backend_kwargs,
):
    """Relabel graph nodes to consecutive integers via the fnx-native route."""
    import franken_networkx as _fnx

    return _fnx.convert_node_labels_to_integers(
        G,
        first_label=first_label,
        ordering=ordering,
        label_attribute=label_attribute,
        backend=backend,
        **backend_kwargs,
    )


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
