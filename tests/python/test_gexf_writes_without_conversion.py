"""GEXF serialisation must not rebuild the whole graph first.

br-r37-c1-ymuxk. All four GEXF helpers called ``_multigraph_to_nx(G)`` or
``_simple_to_nx(G)`` before delegating, rebuilding an entire networkx graph to
produce output nx's ``GEXFWriter`` derives from iteration alone - it touches only
``nodes(data=True)``, ``edges(data=True[, keys])``, ``graph``, ``is_directed()``
and ``is_multigraph()``, all of which an fnx graph exposes nx-compatibly.

GML (br-r37-c1-gmldirect) and GraphML (br-r37-c1-grphmldirect) already carry
exactly this lever. GEXF was the sibling that never got it - found by censusing
every remaining ``_to_nx`` call site in the package after the same
partially-applied-fix shape paid twice earlier the same day (the weighted-degree
float family, and multigraph ``write_edgelist``).

WHAT THIS FILE PINS:

  * BYTES, not structure. GEXF is XML with attribute order, indentation and a
    namespace that vary by version, so the tests compare exact output across
    four classes x three versions (1.2draft, 1.1draft, 1.3) x prettyprint on and
    off, for ``generate_gexf`` and for ``write_gexf`` to both a file object and
    a path - ``open_file`` handles those through different branches, and the
    direct path has to re-apply that decorator itself.
  * THAT THE CONVERSION IS ACTUALLY SKIPPED. A byte test alone cannot tell the
    fast path from the slow one, since both produce identical output - that is
    the whole premise. So the conversion helpers are spied on: they must NOT be
    called for a concrete graph.
  * THAT VIEWS STILL CONVERT. A subgraph view reports as ``Graph`` while its
    filtering lives in Python wrappers, so it must keep round-tripping through
    the rebuild. The same spy asserts the conversion IS called there, which is
    what stops the type gate from being quietly widened later.

NO TIMING CLAIM. Committed under a build freeze with benchmarks banned; the
sibling levers measured 1.9x (GraphML) and 4.9x (GML) for the same removal.
"""

from __future__ import annotations

import io
import os
import tempfile

import networkx as nx
import pytest

import franken_networkx as fnx
from franken_networkx import readwrite as _rw

CLASSES = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]
VERSIONS = ["1.2draft", "1.1draft", "1.3"]


def _build(lib, cls):
    g = getattr(lib, cls)()
    g.add_edge("a", "b", weight=1.5, color="red")
    g.add_edge("a", "b", weight=2)  # parallel on the multis
    g.add_edge("b", "c")  # no attrs
    g.add_edge("c", "c", weight=3)  # self-loop
    g.add_node("iso", label="x", size=2)
    g.graph["name"] = "demo"
    return g


@pytest.mark.parametrize("cls", CLASSES)
@pytest.mark.parametrize("version", VERSIONS)
@pytest.mark.parametrize("prettyprint", [True, False], ids=["pretty", "compact"])
def test_generate_matches_networkx(cls, version, prettyprint):
    assert list(
        fnx.generate_gexf(_build(fnx, cls), prettyprint=prettyprint, version=version)
    ) == list(
        nx.generate_gexf(_build(nx, cls), prettyprint=prettyprint, version=version)
    )


@pytest.mark.parametrize("cls", CLASSES)
@pytest.mark.parametrize("version", VERSIONS)
def test_write_to_file_object_matches_networkx(cls, version):
    got, want = io.BytesIO(), io.BytesIO()
    fnx.write_gexf(_build(fnx, cls), got, version=version)
    nx.write_gexf(_build(nx, cls), want, version=version)
    assert got.getvalue() == want.getvalue()


@pytest.mark.parametrize("cls", CLASSES)
@pytest.mark.parametrize("version", VERSIONS)
def test_write_to_path_matches_networkx(cls, version):
    """``open_file`` takes a different branch for a filename than a handle."""
    with tempfile.TemporaryDirectory() as td:
        got_path = os.path.join(td, "got.gexf")
        want_path = os.path.join(td, "want.gexf")
        fnx.write_gexf(_build(fnx, cls), got_path, version=version)
        nx.write_gexf(_build(nx, cls), want_path, version=version)
        with open(got_path, "rb") as a, open(want_path, "rb") as b:
            assert a.read() == b.read()


class _ConversionSpy:
    """Count calls to the two rebuild helpers without changing behaviour."""

    def __init__(self):
        self.calls = []
        self._originals = {}

    def __enter__(self):
        for name in ("_simple_to_nx", "_multigraph_to_nx"):
            original = getattr(_rw, name)
            self._originals[name] = original

            def make(nm, orig):
                def spy(graph):
                    self.calls.append(nm)
                    return orig(graph)

                return spy

            setattr(_rw, name, make(name, original))
        return self

    def __exit__(self, *exc):
        for name, original in self._originals.items():
            setattr(_rw, name, original)
        return False


@pytest.mark.parametrize("cls", CLASSES)
def test_a_concrete_graph_skips_the_rebuild(cls):
    """THE LEVER. Byte tests cannot see this - both routes emit the same bytes."""
    graph = _build(fnx, cls)
    with _ConversionSpy() as spy:
        list(fnx.generate_gexf(graph))
        fnx.write_gexf(graph, io.BytesIO())
    assert spy.calls == [], f"{cls}: still rebuilding the graph ({spy.calls})"


def test_a_view_still_converts():
    """The control, and the reason the type gate is exact rather than duck-typed.

    A subgraph view reports as Graph but its filtering lives in Python wrappers,
    so handing it straight to nx's writer would serialise the wrong graph. If
    this ever stops converting, the gate has been widened and the output for
    views is about to be wrong.
    """
    view = _build(fnx, "Graph").subgraph(["a", "b"])
    with _ConversionSpy() as spy:
        list(fnx.generate_gexf(view))
    assert spy.calls, "a filtered view must still round-trip through the rebuild"


def test_a_view_serialises_the_filtered_graph():
    """And the conversion must produce the VIEW's contents, not the parent's."""
    parent = _build(fnx, "Graph")
    view = parent.subgraph(["a", "b"])
    text = "\n".join(fnx.generate_gexf(view))
    assert 'label="a"' in text and 'label="b"' in text
    assert 'label="c"' not in text, "the parent's nodes leaked into the view output"
    assert 'label="iso"' not in text


@pytest.mark.parametrize("cls", CLASSES)
def test_empty_and_isolated_only_graphs(cls):
    for build in (lambda lib: getattr(lib, cls)(),):
        got, want = build(fnx), build(nx)
        assert list(fnx.generate_gexf(got)) == list(nx.generate_gexf(want))
        got.add_node("only")
        want.add_node("only")
        assert list(fnx.generate_gexf(got)) == list(nx.generate_gexf(want))
