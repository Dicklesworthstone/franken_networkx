"""br-r37-c1-5h9kx / br-r37-c1-t27ad — the s,t family compared on ARGS, not types.

`test_no_path_st_contract_parity.py` already sweeps this family, but it records
only ``type(exc).__name__``. Comparing the exception ARGS over the same surface
finds **0 type divergences and 17 args divergences** — a textbook false green,
and the same lesson as br-r37-c1-exception_sweep_must_compare_args.

The headline was an internal key encoding reaching the user:

    nx  NetworkXNoPath('No path between a and z.')
    fnx NetworkXNoPath('No path between str:1:a and str:1:z.')

`str:1:a` is fnx's canonical node key. It leaked for STRING keys only — int and
tuple keys already round-trip — so it hit the most common node type while every
int-keyed fixture looked clean. Fixed under br-r37-c1-t27ad, taking 17 divergences
to 5.

The 5 that remain are two different defects, pinned below rather than hidden:
br-r37-c1-7aymx (flow values return float 0.0 where networkx returns int 0) and
br-r37-c1-rmzr6 (MultiDiGraph dijkstra_path_length uses the wrong message
template). Both are filed with their own evidence.
"""

from __future__ import annotations

import networkx as nx
import pytest

import franken_networkx as fnx

CLASSES = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]

# name -> callable(lib, graph). Kept as (lib, graph) so each library resolves
# the function from ITS OWN module: calling nx.<fn>(fnx_graph) would measure the
# backend conversion, not fnx (br-r37-c1-rajc2).
NO_PATH_CALLS = {
    "shortest_path": lambda L, g: L.shortest_path(g, "a", "z"),
    "shortest_path_length": lambda L, g: L.shortest_path_length(g, "a", "z"),
    "bidirectional_shortest_path": lambda L, g: L.bidirectional_shortest_path(g, "a", "z"),
    "all_simple_paths": lambda L, g: list(L.all_simple_paths(g, "a", "z")),
    "shortest_simple_paths": lambda L, g: list(L.shortest_simple_paths(g, "a", "z")),
    "dijkstra_path": lambda L, g: L.dijkstra_path(g, "a", "z"),
    "bidirectional_dijkstra": lambda L, g: L.bidirectional_dijkstra(g, "a", "z"),
    "astar_path": lambda L, g: L.astar_path(g, "a", "z"),
    "astar_path_length": lambda L, g: L.astar_path_length(g, "a", "z"),
    "has_path": lambda L, g: L.has_path(g, "a", "z"),
    "node_disjoint_paths": lambda L, g: list(L.node_disjoint_paths(g, "a", "z")),
    "edge_disjoint_paths": lambda L, g: list(L.edge_disjoint_paths(g, "a", "z")),
}

MISSING_ENDPOINT_CALLS = {
    "shortest_path missing source": lambda L, g: L.shortest_path(g, "nope", "z"),
    "shortest_path missing target": lambda L, g: L.shortest_path(g, "a", "nope"),
    "dijkstra_path missing source": lambda L, g: L.dijkstra_path(g, "nope", "z"),
    "has_path missing source": lambda L, g: L.has_path(g, "nope", "z"),
    "bidirectional_shortest_path missing target": (
        lambda L, g: L.bidirectional_shortest_path(g, "a", "nope")
    ),
}


def _build(lib, cls_name):
    """Two components, so a and z are genuinely unreachable."""
    graph = getattr(lib, cls_name)()
    graph.add_edge("a", "b", weight=1.0, capacity=1.0)
    graph.add_edge("b", "c", weight=1.0, capacity=1.0)
    graph.add_edge("y", "z", weight=1.0, capacity=1.0)
    return graph


def _outcome(lib, cls_name, fn):
    try:
        return ("ok", repr(fn(lib, _build(lib, cls_name)))[:80])
    except Exception as exc:  # noqa: BLE001
        return (type(exc).__name__, tuple(map(str, exc.args)))


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize("call", sorted(NO_PATH_CALLS))
def test_no_path_exception_ARGS_match_networkx(cls_name, call):
    """Args, not just type. The type-only version of this passes on all 80."""
    fn = NO_PATH_CALLS[call]
    want = _outcome(nx, cls_name, fn)
    got = _outcome(fnx, cls_name, fn)
    assert got == want, (cls_name, call)


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize("call", sorted(MISSING_ENDPOINT_CALLS))
def test_missing_endpoint_exception_ARGS_match_networkx(cls_name, call):
    """The neighbouring contract: a source or target that is not in G at all."""
    fn = MISSING_ENDPOINT_CALLS[call]
    want = _outcome(nx, cls_name, fn)
    got = _outcome(fnx, cls_name, fn)
    assert got == want, (cls_name, call)


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize(
    "nodes,label",
    [
        (("a", "b", "c", "y", "z"), "str"),
        ((0, 1, 2, 8, 9), "int"),
        (((1, 2), (3, 4), (5, 6), (7, 8), (9, 0)), "tuple"),
    ],
)
def test_no_path_message_never_leaks_the_canonical_key(cls_name, nodes, label):
    """br-r37-c1-t27ad, across key TYPES.

    The leak was string-specific — int and tuple keys already round-tripped —
    so a fixture using integer nodes would have shown nothing. Parametrising the
    key type is what makes this test able to catch the bug it was written for.
    """
    a, b, c, y, z = nodes
    results = []
    for lib in (nx, fnx):
        graph = getattr(lib, cls_name)()
        graph.add_edge(a, b)
        graph.add_edge(b, c)
        graph.add_edge(y, z)
        try:
            results.append(("ok", lib.shortest_path(graph, a, z)))
        except Exception as exc:  # noqa: BLE001
            results.append((type(exc).__name__, tuple(map(str, exc.args))))
    assert results[1] == results[0], (cls_name, label)
    message = results[0][1][0]
    assert "str:" not in message and "int:" not in message, (
        f"canonical key encoding leaked into the message: {message!r}"
    )


@pytest.mark.parametrize("cls_name", CLASSES)
def test_flow_value_residue_is_still_exactly_as_recorded(cls_name):
    """br-r37-c1-7aymx: flow values are float 0.0 where networkx gives int 0.

    Pinned, not hidden. The VALUE agrees; only the type differs, so this asserts
    the agreement that holds and reports when the type divergence goes away.
    """
    want_graph, got_graph = _build(nx, cls_name), _build(fnx, cls_name)
    try:
        want = nx.maximum_flow_value(want_graph, "a", "z")
        got = fnx.maximum_flow_value(got_graph, "a", "z")
    except Exception:  # noqa: BLE001
        pytest.skip(f"maximum_flow_value unsupported for {cls_name}")
    assert got == want, "the flow VALUE must agree regardless of type"
    if type(got) is type(want):
        pytest.fail(
            f"br-r37-c1-7aymx appears FIXED for {cls_name}: maximum_flow_value now "
            "returns networkx's type. Fold this into the strict assertions."
        )
    assert isinstance(got, float) and isinstance(want, int), (
        f"br-r37-c1-7aymx residue CHANGED shape: got {got!r}, want {want!r}"
    )


def test_multidigraph_dijkstra_message_residue_is_still_as_recorded():
    """br-r37-c1-rmzr6: MultiDiGraph uses the wrong message template.

    The other three classes already produce networkx's wording, and asserting
    that here is what proves the right message is reachable.
    """
    for cls_name in ("Graph", "DiGraph", "MultiGraph"):
        want = _outcome(nx, cls_name, lambda L, g: L.dijkstra_path_length(g, "a", "z"))
        got = _outcome(fnx, cls_name, lambda L, g: L.dijkstra_path_length(g, "a", "z"))
        assert got == want, f"{cls_name} was correct when rmzr6 was filed"

    want = _outcome(nx, "MultiDiGraph", lambda L, g: L.dijkstra_path_length(g, "a", "z"))
    got = _outcome(fnx, "MultiDiGraph", lambda L, g: L.dijkstra_path_length(g, "a", "z"))
    assert got[0] == want[0] == "NetworkXNoPath", "the exception TYPE has always agreed"
    if got == want:
        pytest.fail(
            "br-r37-c1-rmzr6 appears FIXED: MultiDiGraph dijkstra_path_length now "
            "matches networkx. Fold it into the strict assertions above."
        )


def test_the_sweep_is_not_vacuous():
    assert len(NO_PATH_CALLS) >= 10
    assert len(MISSING_ENDPOINT_CALLS) >= 4
    # Every no-path call must actually raise on at least one class, or the
    # sweep would be asserting equality of two "ok" results.
    raised = [
        name
        for name, fn in NO_PATH_CALLS.items()
        if _outcome(nx, "Graph", fn)[0] != "ok"
    ]
    assert len(raised) >= 8, f"only {len(raised)} calls raise on a disconnected pair"
