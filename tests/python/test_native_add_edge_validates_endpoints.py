"""Every native ``add_edge`` kernel rejects None and unhashable endpoints.

br-r37-c1-aeshim. Found while sizing a performance lever, and worth fixing on
correctness grounds alone.

Of the four native kernels, only ``PyMultiGraph::add_edge`` validated its
endpoints. The other three went straight to ``node_key_to_string``. Measured
against networkx by exception TYPE, exception ARGS and the resulting node list,
they diverged in 10 of 10 cases - and the unhashable cases did something worse
than raise the wrong error: the kernel STORED the list or dict as a node and the
graph became permanently unreadable, with ``G.nodes()`` raising
``TypeError: unhashable type`` from a call site unrelated to the add.

WHY IT WAS INVISIBLE. The Python ``add_edge`` shim validates first, so no public
call could reach the defect. It was reachable only by calling the kernel
directly - which the shim itself does, and which any future fast path would do.
A test that exercises only the public API cannot see this class of bug, so this
file drives the KERNELS directly, through the module-level ``_*_ADD_EDGE_RAW``
handles the shim captured.

The comparison includes the resulting NODE LIST, not just the exception: the
corruption's signature is that the raise looks right while the graph is left
holding an unhashable node.
"""

from __future__ import annotations

import networkx as nx
import pytest

import franken_networkx as fnx

RAW = {
    "Graph": fnx._GRAPH_ADD_EDGE_RAW,
    "DiGraph": fnx._DIGRAPH_ADD_EDGE_RAW,
    "MultiGraph": fnx._MULTIGRAPH_ADD_EDGE_RAW,
    "MultiDiGraph": fnx._MULTIDIGRAPH_ADD_EDGE_RAW,
}

BAD_ENDPOINTS = [
    (None, "b"),
    ("a", None),
    (None, None),
    (["x"], "b"),
    ("a", ["x"]),
    ({1: 2}, "b"),
    ("a", {1: 2}),
    ({"s"}, "b"),
]


def _nodes(graph):
    """Node list, or the failure - an unreadable graph IS the symptom."""
    try:
        return sorted(repr(n) for n in graph.nodes())
    except Exception as exc:  # noqa: BLE001
        return f"UNREADABLE:{type(exc).__name__}"


def _outcome(graph, call):
    try:
        call()
        return ("ok", None), _nodes(graph)
    except Exception as exc:  # noqa: BLE001 - the raise is the subject
        return (type(exc).__name__, exc.args), _nodes(graph)


@pytest.mark.parametrize("cls", sorted(RAW), ids=sorted(RAW))
@pytest.mark.parametrize("u,v", BAD_ENDPOINTS, ids=repr)
def test_kernel_matches_networkx_on_bad_endpoints(cls, u, v):
    """Drives the KERNEL directly; the public shim would mask this."""
    got = getattr(fnx, cls)()
    want = getattr(nx, cls)()
    assert _outcome(got, lambda: RAW[cls](got, u, v)) == _outcome(
        want, lambda: want.add_edge(u, v)
    )


@pytest.mark.parametrize("cls", sorted(RAW), ids=sorted(RAW))
def test_kernel_leaves_the_graph_readable_after_a_bad_add(cls):
    """The corruption signature: a plausible raise, an unusable graph."""
    got = getattr(fnx, cls)()
    got_add = RAW[cls]
    got_add(got, "keep", "alsokeep")
    for u, v in BAD_ENDPOINTS:
        with pytest.raises((ValueError, TypeError)):
            got_add(got, u, v)
        assert _nodes(got) != "UNREADABLE:TypeError", (
            f"{cls} kernel stored an unhashable endpoint from {u!r}/{v!r}"
        )
    assert "'keep'" in _nodes(got)


@pytest.mark.parametrize("cls", sorted(RAW), ids=sorted(RAW))
def test_partial_state_ordering_matches_networkx(cls):
    """nx creates u BEFORE examining v, so a bad v must leave u behind."""
    got, want = getattr(fnx, cls)(), getattr(nx, cls)()
    with pytest.raises(ValueError):
        RAW[cls](got, "u-survives", None)
    with pytest.raises(ValueError):
        want.add_edge("u-survives", None)
    assert _nodes(got) == _nodes(want)


@pytest.mark.parametrize("cls", sorted(RAW), ids=sorted(RAW))
def test_good_endpoints_still_work(cls):
    """The guard must not reject anything networkx accepts."""
    got, want = getattr(fnx, cls)(), getattr(nx, cls)()
    for u, v in (("a", "b"), (1, 2), ((1, 2), (3, 4)), (0, False), ("s", "s")):
        RAW[cls](got, u, v)
        want.add_edge(u, v)
    assert _nodes(got) == _nodes(want)
    assert got.number_of_edges() == want.number_of_edges()
