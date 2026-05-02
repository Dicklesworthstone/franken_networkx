"""Metamorphic tests for max-flow / min-cut algebraic invariants.

Twelfth metamorphic-equivalence module pairing with the eleven already
in place. Asserts the textbook flow-network identities — every result
that should hold on any flow network, regardless of the specific
algorithm used.

Flow / cut duality and structural invariants:

1. **Max-flow / min-cut theorem**: ``max_flow == min_cut`` on the
   same source/sink pair. The most fundamental flow invariant.
2. **Source out-capacity bound**: ``max_flow ≤ Σ capacity(s, *)``.
   The flow can't exceed what the source can push out.
3. **Sink in-capacity bound**: ``max_flow ≤ Σ capacity(*, t)``.
   Symmetric bound for the sink side.
4. **Flow non-negativity**: every per-edge flow value in the
   max-flow decomposition is finite and non-negative.
5. **Per-edge capacity respect**: every per-edge flow value f(u, v)
   satisfies ``0 ≤ f(u, v) ≤ capacity(u, v)``.
6. **Flow conservation at non-source/sink nodes**: net flow in ==
   net flow out.

Pairs with the fuzz_flow target (1d23f49d) — the fuzzer drives the
same identities on arbitrary flow networks; this module pins them at
deterministic fixtures so any regression is immediately visible.
"""

from __future__ import annotations

from collections import defaultdict

import pytest

import franken_networkx as fnx


FLOW_FIXTURES = [
    # (name, builder, source, sink)
    (
        "two_path",
        lambda: _build_two_path(),
        "s",
        "t",
    ),
    (
        "diamond_flow",
        lambda: _build_diamond(),
        "s",
        "t",
    ),
    (
        "linear_chain_4",
        lambda: _build_linear_chain(),
        "s",
        "t",
    ),
    (
        "k4_directed_flow",
        lambda: _build_k4_directed(),
        "s",
        "t",
    ),
]


def _build_two_path():
    g = fnx.DiGraph()
    g.add_edge("s", "a", capacity=10)
    g.add_edge("s", "b", capacity=5)
    g.add_edge("a", "t", capacity=8)
    g.add_edge("b", "t", capacity=10)
    g.add_edge("a", "b", capacity=2)
    return g


def _build_diamond():
    g = fnx.DiGraph()
    g.add_edge("s", "a", capacity=20)
    g.add_edge("s", "b", capacity=15)
    g.add_edge("a", "c", capacity=10)
    g.add_edge("b", "c", capacity=10)
    g.add_edge("c", "t", capacity=25)
    g.add_edge("a", "t", capacity=5)
    return g


def _build_linear_chain():
    g = fnx.DiGraph()
    g.add_edge("s", "a", capacity=4)
    g.add_edge("a", "b", capacity=3)
    g.add_edge("b", "c", capacity=5)
    g.add_edge("c", "t", capacity=6)
    return g


def _build_k4_directed():
    g = fnx.DiGraph()
    nodes = ["s", "a", "b", "t"]
    caps = {("s", "a"): 7, ("s", "b"): 9, ("a", "b"): 3,
            ("a", "t"): 5, ("b", "t"): 8, ("b", "a"): 2}
    for (u, v), c in caps.items():
        g.add_edge(u, v, capacity=c)
    return g


# -----------------------------------------------------------------------------
# Max-flow / min-cut theorem
# -----------------------------------------------------------------------------


@pytest.mark.parametrize(("name", "builder", "source", "sink"), FLOW_FIXTURES)
def test_max_flow_equals_min_cut(name, builder, source, sink):
    g = builder()
    flow_value, _ = fnx.maximum_flow(g, source, sink)
    cut_value, _ = fnx.minimum_cut(g, source, sink)
    assert flow_value == cut_value, (
        f"{name}: max-flow {flow_value} != min-cut {cut_value} "
        f"(violates max-flow / min-cut theorem)"
    )


# -----------------------------------------------------------------------------
# Source / sink capacity bounds
# -----------------------------------------------------------------------------


@pytest.mark.parametrize(("name", "builder", "source", "sink"), FLOW_FIXTURES)
def test_max_flow_bounded_by_source_out_capacity(name, builder, source, sink):
    g = builder()
    flow_value, _ = fnx.maximum_flow(g, source, sink)
    out_cap = sum(
        attrs.get("capacity", float("inf"))
        for u, v, attrs in g.edges(data=True)
        if u == source
    )
    assert flow_value <= out_cap, (
        f"{name}: max_flow {flow_value} > source out-capacity {out_cap}"
    )


@pytest.mark.parametrize(("name", "builder", "source", "sink"), FLOW_FIXTURES)
def test_max_flow_bounded_by_sink_in_capacity(name, builder, source, sink):
    g = builder()
    flow_value, _ = fnx.maximum_flow(g, source, sink)
    in_cap = sum(
        attrs.get("capacity", float("inf"))
        for u, v, attrs in g.edges(data=True)
        if v == sink
    )
    assert flow_value <= in_cap, (
        f"{name}: max_flow {flow_value} > sink in-capacity {in_cap}"
    )


# -----------------------------------------------------------------------------
# Per-edge flow respects capacity
# -----------------------------------------------------------------------------


@pytest.mark.parametrize(("name", "builder", "source", "sink"), FLOW_FIXTURES)
def test_per_edge_flow_within_capacity(name, builder, source, sink):
    g = builder()
    _, flow_dict = fnx.maximum_flow(g, source, sink)
    for u in flow_dict:
        for v, f_uv in flow_dict[u].items():
            cap = g[u][v].get("capacity", float("inf"))
            assert 0 <= f_uv <= cap + 1e-9, (
                f"{name}: per-edge flow f({u},{v})={f_uv} outside "
                f"[0, capacity={cap}]"
            )


# -----------------------------------------------------------------------------
# Flow conservation at intermediate nodes
# -----------------------------------------------------------------------------


@pytest.mark.parametrize(("name", "builder", "source", "sink"), FLOW_FIXTURES)
def test_flow_conservation_at_intermediate_nodes(name, builder, source, sink):
    g = builder()
    _, flow_dict = fnx.maximum_flow(g, source, sink)
    in_flow = defaultdict(float)
    out_flow = defaultdict(float)
    for u in flow_dict:
        for v, f_uv in flow_dict[u].items():
            out_flow[u] += f_uv
            in_flow[v] += f_uv
    for v in g.nodes():
        if v == source or v == sink:
            continue
        assert abs(in_flow[v] - out_flow[v]) < 1e-9, (
            f"{name}: flow conservation violated at {v} — "
            f"in_flow={in_flow[v]}, out_flow={out_flow[v]}"
        )


# -----------------------------------------------------------------------------
# Min-cut value non-negative
# -----------------------------------------------------------------------------


@pytest.mark.parametrize(("name", "builder", "source", "sink"), FLOW_FIXTURES)
def test_min_cut_non_negative(name, builder, source, sink):
    g = builder()
    cut_value, _ = fnx.minimum_cut(g, source, sink)
    assert cut_value >= 0, (
        f"{name}: min-cut value {cut_value} is negative"
    )
