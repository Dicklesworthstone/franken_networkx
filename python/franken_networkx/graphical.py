"""FrankenNetworkX graphical degree-sequence algorithm submodule."""

from __future__ import annotations

import importlib as _importlib

_nx_graphical = _importlib.import_module("networkx.algorithms.graphical")

import franken_networkx as _fnx

__all__ = list(
    getattr(
        _nx_graphical,
        "__all__",
        (
            "is_graphical",
            "is_multigraphical",
            "is_pseudographical",
            "is_digraphical",
            "is_valid_degree_sequence_erdos_gallai",
            "is_valid_degree_sequence_havel_hakimi",
        ),
    )
)


def is_graphical(sequence, method="eg", *, backend=None, **backend_kwargs):
    """Return True if sequence can be realized by a simple graph."""
    _fnx._validate_backend_dispatch_keywords("is_graphical", backend, backend_kwargs)
    return _fnx.is_graphical(sequence, method=method)


def is_multigraphical(sequence, *, backend=None, **backend_kwargs):
    """Return True if sequence can be realized by a multigraph."""
    _fnx._validate_backend_dispatch_keywords(
        "is_multigraphical", backend, backend_kwargs
    )
    return _fnx.is_multigraphical(sequence)


def is_pseudographical(sequence, *, backend=None, **backend_kwargs):
    """Return True if sequence can be realized by a pseudograph."""
    _fnx._validate_backend_dispatch_keywords(
        "is_pseudographical", backend, backend_kwargs
    )
    return _fnx.is_pseudographical(sequence)


def is_digraphical(in_sequence, out_sequence, *, backend=None, **backend_kwargs):
    """Return True if in/out sequences can be realized by a digraph."""
    _fnx._validate_backend_dispatch_keywords("is_digraphical", backend, backend_kwargs)
    return _fnx.is_digraphical(in_sequence, out_sequence)


def is_valid_degree_sequence_erdos_gallai(
    deg_sequence, *, backend=None, **backend_kwargs
):
    """Return True if sequence is graphical by Erdős-Gallai."""
    _fnx._validate_backend_dispatch_keywords(
        "is_valid_degree_sequence_erdos_gallai", backend, backend_kwargs
    )
    return _fnx.is_valid_degree_sequence_erdos_gallai(deg_sequence)


def is_valid_degree_sequence_havel_hakimi(
    deg_sequence, *, backend=None, **backend_kwargs
):
    """Return True if sequence is graphical by Havel-Hakimi."""
    _fnx._validate_backend_dispatch_keywords(
        "is_valid_degree_sequence_havel_hakimi", backend, backend_kwargs
    )
    return _fnx.is_valid_degree_sequence_havel_hakimi(deg_sequence)


def __getattr__(name):
    try:
        return getattr(_nx_graphical, name)
    except AttributeError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc


def __dir__():
    public_globals = {name for name in globals() if not name.startswith("_")}
    public_upstream = {name for name in dir(_nx_graphical) if not name.startswith("_")}
    return sorted(public_globals | public_upstream)
