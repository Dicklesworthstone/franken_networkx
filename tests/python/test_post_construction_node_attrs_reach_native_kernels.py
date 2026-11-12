"""A node attribute written AFTER construction must reach the native kernels.

br-r37-c1-303zo. A graph carries two node-attribute stores: ``node_py_attrs``,
written by the Python paths, and the typed Rust store that native kernels read.
The bead recorded that attributes attached after construction landed only in the
former, so a kernel reading the typed store missed them - and missed them
SILENTLY, because kernels default on a miss (the weighted vertex-cover kernel
used ``.unwrap_or(1.0)``, turning every node into cost 1 and violating its own
2-approximation guarantee by 25x).

WHAT THIS FILE IS. The gap does not reproduce today: checked across the node-attr
consumer surface, the serializers, the graph operators, and finally by calling a
native kernel DIRECTLY with no shim and no sync in between, all three
construction paths agree. So this is the audit the bead asked for, kept as an
executable guard rather than as a note - the bead's own warning is that the gap
"will bite any future native kernel", and a future kernel that reads the typed
store without a sync is exactly what these assertions catch.

THE THREE PATHS ARE THE WHOLE POINT. They are indistinguishable from Python -
``nodes(data=True)`` shows the same values for all three - so any test that builds
its fixture one way cannot see this class of defect at all:

    A: add_node(v, k=w) BEFORE the edges   -> always reached the typed store
    B: edges first, then G.nodes[v][k] = w -> the failing path
    C: edges first, then set_node_attributes -> the failing path

``_native_disjoint_union`` is the load-bearing case: the shim calls it with no
sync, and it reads ``inner.node_attrs`` directly, so it observes the typed store
rather than the Python mirror.
"""

from __future__ import annotations

import networkx as nx
import pytest

import franken_networkx as fnx

EDGES = [("a", "b"), ("b", "c"), ("c", "d"), ("a", "d")]
NUMERIC = {"a": 1.0, "b": 5.0, "c": 2.0, "d": 9.0}
CATEGORICAL = {"a": "x", "b": "y", "c": "x", "d": "y"}
PATHS = ["ctor", "nodes-subscript", "set_node_attributes"]


def _build(mod, path, attr, values, prefix=""):
    graph = mod.Graph()
    nodes = {prefix + k: v for k, v in values.items()}
    edges = [(prefix + u, prefix + v) for u, v in EDGES]
    if path == "ctor":
        for node, value in nodes.items():
            graph.add_node(node, **{attr: value})
        graph.add_edges_from(edges)
    elif path == "nodes-subscript":
        graph.add_edges_from(edges)
        for node, value in nodes.items():
            graph.nodes[node][attr] = value
    else:
        graph.add_edges_from(edges)
        mod.set_node_attributes(graph, nodes, attr)
    return graph


def _node_attrs(graph, attr="val"):
    return sorted((str(n), d.get(attr)) for n, d in graph.nodes(data=True))


@pytest.mark.parametrize("path", PATHS)
def test_the_typed_store_itself_sees_the_write(path):
    """The sharpest form: a native kernel, called directly, with no sync.

    `_native_disjoint_union` reads `inner.node_attrs` and the shim invokes it
    without syncing, so a value arriving here proves the typed store - not the
    Python mirror - carries the attribute. A regression shows up as `None`.
    """
    left = _build(fnx, path, "val", NUMERIC)
    right = _build(fnx, path, "val", NUMERIC, prefix="z")

    fused = left._native_disjoint_union(right)
    values = [d.get("val") for _, d in fused.nodes(data=True)]

    assert None not in values, (
        f"{path}: the typed store lost a node attribute - a native kernel would "
        "silently default it (br-r37-c1-303zo)"
    )
    assert sorted(values) == sorted(list(NUMERIC.values()) * 2)


@pytest.mark.parametrize("path", PATHS)
def test_python_readback_cannot_tell_the_paths_apart(path):
    """Why the defect was silent: Python shows the same thing either way.

    This is the control that makes the assertions above meaningful. If this ever
    fails, the fixture is broken rather than the store.
    """
    fx = _build(fnx, path, "val", NUMERIC)
    ref = _build(nx, path, "val", NUMERIC)

    assert _node_attrs(fx) == _node_attrs(ref) == sorted(NUMERIC.items())


@pytest.mark.parametrize("path", PATHS)
@pytest.mark.parametrize(
    "name",
    [
        "disjoint_union",
        "union",
        "compose",
        "copy",
        "to_directed",
        "subgraph",
    ],
)
def test_graph_operators_carry_the_attribute(path, name):
    """The operators are where a stale typed store shows as DROPPED attributes."""
    fx_left = _build(fnx, path, "val", NUMERIC)
    fx_right = _build(fnx, path, "val", NUMERIC, prefix="z")
    ref_left = _build(nx, path, "val", NUMERIC)
    ref_right = _build(nx, path, "val", NUMERIC, prefix="z")

    def apply(mod, left, right):
        if name in ("disjoint_union", "union", "compose"):
            return _node_attrs(getattr(mod, name)(left, right))
        if name == "copy":
            return _node_attrs(left.copy())
        if name == "to_directed":
            return _node_attrs(left.to_directed())
        return _node_attrs(left.subgraph(sorted(left)[:2]))

    assert apply(fnx, fx_left, fx_right) == apply(nx, ref_left, ref_right)


@pytest.mark.parametrize("path", PATHS)
def test_weighted_approximation_uses_the_attribute(path):
    """The original symptom's family: a kernel that defaults on a miss.

    `min_weighted_vertex_cover` returned the UNWEIGHTED cover when the weights
    did not reach the typed store. The witness weights are lopsided so an
    all-ones fallback picks a visibly different set.
    """
    fx = _build(fnx, path, "val", NUMERIC)
    ref = _build(nx, path, "val", NUMERIC)

    assert sorted(fnx.approximation.min_weighted_vertex_cover(fx, "val")) == sorted(
        nx.approximation.min_weighted_vertex_cover(ref, "val")
    )


@pytest.mark.parametrize("path", PATHS)
def test_attribute_mixing_uses_the_attribute(path):
    """A categorical consumer, so the guard is not only about numeric weights."""
    fx = _build(fnx, path, "cat", CATEGORICAL)
    ref = _build(nx, path, "cat", CATEGORICAL)

    assert fnx.attribute_assortativity_coefficient(
        fx, "cat"
    ) == nx.attribute_assortativity_coefficient(ref, "cat")
    assert sorted(fnx.node_attribute_xy(fx, "cat")) == sorted(
        nx.node_attribute_xy(ref, "cat")
    )


@pytest.mark.parametrize("path", PATHS)
def test_serializers_emit_the_attribute(path):
    """A stale typed store shows here as an attribute missing from the output."""
    fx = _build(fnx, path, "val", NUMERIC)
    ref = _build(nx, path, "val", NUMERIC)

    fx_nodes = sorted(
        (d.get("id"), d.get("val"))
        for d in fnx.node_link_data(fx, edges="edges")["nodes"]
    )
    ref_nodes = sorted(
        (d.get("id"), d.get("val"))
        for d in nx.node_link_data(ref, edges="edges")["nodes"]
    )
    assert fx_nodes == ref_nodes

    fx_gml = sorted(line.strip() for line in fnx.generate_gml(fx) if "val" in line)
    ref_gml = sorted(line.strip() for line in nx.generate_gml(ref) if "val" in line)
    assert fx_gml == ref_gml
