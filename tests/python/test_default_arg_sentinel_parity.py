"""Parity for default-arg sentinels (br-r37-c1-rygbm).

Several fnx wrappers had ``None`` defaults where networkx uses concrete
sentinel values. ``inspect.signature`` introspection diverged, and in
the trophic case the wrong default silently dropped edge weights.

Aligned in commit (this PR):

- ``stoer_wagner(G, weight, heap=BinaryHeap)`` — was heap=None
- ``capacity_scaling(G, ..., heap=BinaryHeap)`` — was heap=None
- ``adjacency_data(G, attrs={'id': 'id', 'key': 'key'})`` — was None
- ``adjacency_graph(data, ..., attrs={'id': 'id', 'key': 'key'})``
- ``trophic_levels(G, weight='weight')`` — was None
- ``trophic_differences(G, weight='weight')`` — was None
- ``trophic_incoherence_parameter(G, weight='weight', cannibalism=False)``
"""

from __future__ import annotations

import inspect

import pytest

import franken_networkx as fnx

try:
    import networkx as nx
    HAS_NX = True
except ImportError:
    HAS_NX = False

needs_nx = pytest.mark.skipif(not HAS_NX, reason="networkx not installed")


def _signature_defaults(fn):
    """Map of parameter name → default value (skipping empty + backend kwargs)."""
    sig = inspect.signature(fn)
    return {
        name: param.default
        for name, param in sig.parameters.items()
        if param.default is not inspect.Parameter.empty
        and name not in ("backend", "backend_kwargs")
    }


@needs_nx
@pytest.mark.parametrize(
    "name",
    [
        "stoer_wagner",
        "capacity_scaling",
        "adjacency_data",
        "adjacency_graph",
        "trophic_levels",
        "trophic_differences",
        "trophic_incoherence_parameter",
    ],
)
def test_default_arg_sentinels_match_networkx(name):
    fnx_defaults = _signature_defaults(getattr(fnx, name))
    nx_defaults = _signature_defaults(getattr(nx, name))
    for key, expected in nx_defaults.items():
        assert key in fnx_defaults, f"{name}: missing param {key}"
        assert (
            repr(fnx_defaults[key]) == repr(expected)
        ), f"{name}.{key}: fnx={fnx_defaults[key]!r} nx={expected!r}"


@needs_nx
def test_trophic_levels_uses_weighted_default_when_attribute_present():
    """nx defaults trophic_levels to weight='weight'. Build a DAG with
    asymmetric weights and confirm fnx now picks them up by default,
    instead of silently passing weight=None."""
    G = fnx.DiGraph()
    GX = nx.DiGraph()
    for g in (G, GX):
        g.add_edge("a", "b", weight=2.0)
        g.add_edge("a", "c", weight=1.0)
        g.add_edge("b", "d", weight=3.0)
        g.add_edge("c", "d", weight=1.0)

    fnx_levels = fnx.trophic_levels(G)
    nx_levels = nx.trophic_levels(GX)
    for k in nx_levels:
        assert abs(fnx_levels[k] - nx_levels[k]) < 1e-9


@needs_nx
def test_adjacency_data_default_attrs_match_networkx():
    """Without an explicit attrs dict, fnx must produce the same output
    as nx — the default sentinel ``{'id': 'id', 'key': 'key'}`` controls
    the field names in the JSON payload."""
    G = fnx.karate_club_graph()
    GX = nx.karate_club_graph()
    actual = fnx.adjacency_data(G)
    expected = nx.adjacency_data(GX)
    assert sorted(actual.keys()) == sorted(expected.keys())
    # both should expose 'id' on each node, not whatever None resolved to
    assert all("id" in n for n in actual["nodes"])
    assert len(actual["nodes"]) == len(expected["nodes"])
    assert len(actual["adjacency"]) == len(expected["adjacency"])


@needs_nx
def test_adjacency_data_round_trip_with_default_attrs():
    G = fnx.karate_club_graph()
    data = fnx.adjacency_data(G)
    # Roundtrip — must preserve edges
    rebuilt = fnx.adjacency_graph(data)
    assert rebuilt.number_of_nodes() == G.number_of_nodes()
    assert rebuilt.number_of_edges() == G.number_of_edges()


@needs_nx
def test_stoer_wagner_default_heap_is_binary_heap_class():
    """The default heap argument must be a class (not None) so users
    introspecting the signature see what nx exposes."""
    sig = inspect.signature(fnx.stoer_wagner)
    heap_default = sig.parameters["heap"].default
    assert heap_default is not None
    assert isinstance(heap_default, type)
    # Should be the same class nx exports
    nx_default = inspect.signature(nx.stoer_wagner).parameters["heap"].default
    assert heap_default is nx_default


@needs_nx
def test_stoer_wagner_explicit_none_heap_still_works():
    """Backwards compat: callers used to pass ``heap=None``. The fnx
    impl ignores the heap arg, so None should still be accepted."""
    G = fnx.cycle_graph(5)
    cut_value, partition = fnx.stoer_wagner(G, heap=None)
    assert cut_value == 2  # min cut of C5 is 2
