"""Multigraph ``write_edgelist`` must not convert the whole graph to networkx.

br-r37-c1-ton6l, the multigraph half of br-r37-c1-04z53.9187. That lever
removed the ``_to_nx(G)`` whole-graph conversion from ``write_edgelist`` for
SIMPLE graphs - 570.136ms to 30.158ms on a real n=10k export, where
serialisation had been 52% of the summed wall clock - and left
``not G.is_multigraph()`` on the outer gate. So every multigraph export still
paid a full conversion to produce output networkx writes from a plain loop:

    for line in generate_edgelist(G, delimiter, data):
        path.write((line + "\\n").encode(encoding))

That loop is class-agnostic in networkx, and fnx's ``generate_edgelist`` is
byte-identical to networkx's for the multigraph classes, so the conversion buys
nothing.

WHAT THIS FILE PINS. The claim is a BYTE claim, so the tests are byte
comparisons - of written output, not of line lists:

  * both bool ``data`` spellings, all four classes, as a file object AND as a
    path, since ``open_file`` handles those through different branches;
  * parallel edges and self-loops, which are the whole reason multigraphs were
    excluded, and which the simple-graph fixtures could not exercise;
  * non-string node labels, where ``str()`` placement in the loop matters;
  * NON-DEFAULT kwargs still delegate: a non-space delimiter, a non-utf-8
    encoding, and a non-bool ``data`` list must go through networkx and keep
    matching, because the fast path is only entitled to the default surface.

THE NATIVE RUST WRITER STAYS SIMPLE-GRAPH-ONLY and that is asserted here rather
than assumed: it has no parallel-edge key handling, and this change deliberately
does not ask it to grow one. A future edit that widens its gate to multigraphs
should fail this file.

NO TIMING CLAIM IS MADE HERE. The conversion removal was measured for the simple
classes by br-r37-c1-04z53.9187; the multigraph figure has not been measured
(committed under a build freeze). These tests establish only that the cheaper
route produces networkx's exact bytes.
"""

from __future__ import annotations

import io
import os
import tempfile

import networkx as nx
import pytest

import franken_networkx as fnx

CLASSES = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]
MULTI = ["MultiGraph", "MultiDiGraph"]


def _build(lib, cls):
    g = getattr(lib, cls)()
    g.add_edge("a", "b", weight=1.5, color="red")
    g.add_edge("a", "b", weight=2)  # parallel edge on the multis
    g.add_edge("b", "c")  # no attrs
    g.add_edge("c", "c", weight=3)  # self-loop
    g.add_edge("c", "c", weight=4)  # parallel self-loop on the multis
    g.add_edge("d", "a", k=None)
    g.add_edge(1, 2, weight=7)  # non-string labels
    g.add_node("isolated")
    return g


def _write_bytes(lib, graph, data, **kwargs):
    buf = io.BytesIO()
    lib.write_edgelist(graph, buf, data=data, **kwargs)
    return buf.getvalue()


def _write_path_bytes(lib, graph, data, **kwargs):
    with tempfile.TemporaryDirectory() as td:
        target = os.path.join(td, "edges.txt")
        lib.write_edgelist(graph, target, data=data, **kwargs)
        with open(target, "rb") as handle:
            return handle.read()


@pytest.mark.parametrize("cls", CLASSES)
@pytest.mark.parametrize("data", [True, False], ids=["data_true", "data_false"])
def test_file_object_bytes_match_networkx(cls, data):
    assert _write_bytes(fnx, _build(fnx, cls), data) == _write_bytes(
        nx, _build(nx, cls), data
    )


@pytest.mark.parametrize("cls", CLASSES)
@pytest.mark.parametrize("data", [True, False], ids=["data_true", "data_false"])
def test_path_bytes_match_networkx(cls, data):
    """``open_file`` takes a different branch for a filename than a handle."""
    assert _write_path_bytes(fnx, _build(fnx, cls), data) == _write_path_bytes(
        nx, _build(nx, cls), data
    )


@pytest.mark.parametrize("cls", MULTI)
def test_parallel_edges_and_self_loops_all_appear(cls):
    """The reason multigraphs were excluded; assert against nx, then count."""
    got = _write_bytes(fnx, _build(fnx, cls), True)
    assert got == _write_bytes(nx, _build(nx, cls), True)
    lines = got.decode().splitlines()
    assert sum(1 for ln in lines if ln.startswith("a b")) == 2, lines
    assert sum(1 for ln in lines if ln.startswith("c c")) == 2, lines


@pytest.mark.parametrize("cls", CLASSES)
@pytest.mark.parametrize(
    "kwargs",
    [{"delimiter": "\t"}, {"encoding": "latin-1"}, {"comments": "%"}],
    ids=["tab_delimiter", "latin1", "comment_char"],
)
@pytest.mark.parametrize("data", [True, False], ids=["data_true", "data_false"])
def test_non_default_kwargs_still_match(cls, kwargs, data):
    """Off the default surface the fast path must not fire; bytes still match."""
    assert _write_bytes(fnx, _build(fnx, cls), data, **kwargs) == _write_bytes(
        nx, _build(nx, cls), data, **kwargs
    )


@pytest.mark.parametrize("cls", CLASSES)
@pytest.mark.parametrize(
    "data", [["weight"], ["weight", "color"], []], ids=["one_key", "two_keys", "no_keys"]
)
def test_key_list_data_still_matches(cls, data):
    """Non-bool ``data`` delegates; pinned so the delegation stays correct."""
    assert _write_bytes(fnx, _build(fnx, cls), data) == _write_bytes(
        nx, _build(nx, cls), data
    )


@pytest.mark.parametrize("cls", MULTI)
def test_the_native_writer_is_not_used_for_multigraphs(cls):
    """Pins the deliberate scope limit, so a future widening fails here.

    The Rust writer has no parallel-edge key handling. If it is ever reached for
    a multigraph, either it grew that handling (and this test should be updated
    deliberately) or the output is about to be wrong.

    THE FIXTURE MATTERS. The native writer only fires for INT-labelled graphs
    carrying at most one attribute per edge - a string-labelled graph bails it
    for unrelated reasons, so asserting "not called" on one would pass no matter
    what this gate said. This uses the exact shape that WOULD reach it if the
    class check were dropped, which is what makes the assertion mean something.
    """
    graph = getattr(fnx, cls)()
    graph.add_edge(1, 2, weight=1)
    graph.add_edge(1, 2, weight=2)
    calls = []
    original = fnx._rust_write_edgelist

    def spy(*args, **kwargs):
        calls.append(args)
        return original(*args, **kwargs)

    fnx._rust_write_edgelist = spy
    try:
        _write_bytes(fnx, graph, True)
        _write_bytes(fnx, graph, False)
    finally:
        fnx._rust_write_edgelist = original
    assert calls == [], f"native writer reached for {cls}"


def test_the_native_writer_is_still_used_for_simple_graphs():
    """The control: the simple-graph fast path must not have been disturbed.

    Same int-labelled, single-attribute shape as the multigraph test above, so
    the pair differs ONLY in graph class - which is the thing under test.
    """
    graph = fnx.Graph()
    graph.add_edge(1, 2, weight=1)
    calls = []
    original = fnx._rust_write_edgelist

    def spy(*args, **kwargs):
        calls.append(args)
        return original(*args, **kwargs)

    fnx._rust_write_edgelist = spy
    try:
        _write_bytes(fnx, graph, True)
    finally:
        fnx._rust_write_edgelist = original
    assert calls, "simple-graph native writer path was lost"


@pytest.mark.parametrize("cls", CLASSES)
def test_empty_and_isolated_only_graphs(cls):
    for graph_f, graph_x in (
        (getattr(fnx, cls)(), getattr(nx, cls)()),
        (getattr(fnx, cls)(), getattr(nx, cls)()),
    ):
        graph_f.add_node("only")
        graph_x.add_node("only")
        for data in (True, False):
            assert _write_bytes(fnx, graph_f, data) == _write_bytes(nx, graph_x, data)
