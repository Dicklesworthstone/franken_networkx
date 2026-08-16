"""Regression lock (br-r37-c1-15wjz) — relabel must refuse a None node.

``None`` is not a valid networkx node, and nx raises
``ValueError("None cannot be a node")`` wherever one would be created. fnx
agrees on every route into a graph, on all four classes, and this file passes
on HEAD. It is a LOCK, not a fix — but it locks something that genuinely broke
in a built artifact earlier today, which is why it is worth its runtime.

WHAT HAPPENED, because it is the reason this file exists. While
br-r37-c1-u3vvm's native ``_native_relabel_copy`` kernel was in flight, the
shared checkout's compiled extension (ELF sha256 a85d2a98d4793df8) contained a
version of it that skipped the None check. The kernel is reached only by a
``Graph`` whose nodes carry attributes, so the failure was invisible on the
other three classes and on an unattributed Graph::

    g = Graph(); g.add_node('n0', label=None)
    relabel_nodes(g, {'n0': None}, copy=True)

    networkx  -> ValueError('None cannot be a node')
    that .so  -> no error, and the graph's node key was literally None

It surfaced as a red
``test_gexf.py::test_read_gexf_preserves_missing_node_label_as_none``: a GEXF
node may legitimately omit its label, fnx's parser represents that as
``{'label': None}``, and ``read_gexf(relabel=True)`` maps the node id onto that
None. The kernel landed fixed (4733d15d3, ELF 39879819545fc91e) and nothing is
broken on HEAD now.

Run against the earlier extension this file fails 6 of its cases, so it would
have caught that rewrite before it was built. A silent None node key is worse
than an exception — every later operation misbehaves instead of failing where
the mistake was made — and the guard lives in a native kernel that is likely to
be rewritten again for performance.

The trigger condition is asserted precisely: nx raises when a node that IS in
the graph maps to None, NOT merely when None appears in the mapping. Mapping an
absent key to None is accepted by both libraries.
"""

from __future__ import annotations

from io import BytesIO

import networkx as nx
import pytest

import franken_networkx as fnx

CLASSES = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]
ATTR_VARIANTS = {
    "no-attrs": {},
    "attrs-none-value": {"label": None},
    "attrs-str-value": {"label": "x"},
    "several-attrs": {"label": "x", "weight": 2, "colour": "red"},
}


def _outcome(fn):
    try:
        return ("ok", fn())
    except Exception as exc:  # noqa: BLE001 - the exception IS the contract
        return (type(exc).__name__, str(exc))


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize("attr_name", list(ATTR_VARIANTS))
@pytest.mark.parametrize("copy", [True, False], ids=["copy", "inplace"])
def test_relabel_to_none_raises_like_networkx(cls_name, attr_name, copy):
    attrs = ATTR_VARIANTS[attr_name]
    outcomes = []
    for lib in (nx, fnx):
        graph = getattr(lib, cls_name)()
        graph.add_node("n0", **attrs)
        graph.add_edge("n0", "n1")
        outcomes.append(
            _outcome(lambda g=graph, l=lib: sorted(map(str, l.relabel_nodes(g, {"n0": None}, copy=copy).nodes)))
        )
    assert outcomes[1] == outcomes[0]
    assert outcomes[0] == ("ValueError", "None cannot be a node")


@pytest.mark.parametrize("cls_name", CLASSES)
def test_mapping_an_absent_key_to_none_is_accepted(cls_name):
    """nx's rule is about nodes IN the graph, not about the mapping's values."""
    outcomes = []
    for lib in (nx, fnx):
        graph = getattr(lib, cls_name)()
        graph.add_node("n0", label="L")
        outcomes.append(
            _outcome(lambda g=graph, l=lib: sorted(map(str, l.relabel_nodes(g, {"ghost": None}, copy=True).nodes)))
        )
    assert outcomes[1] == outcomes[0]
    assert outcomes[0] == ("ok", ["n0"])


@pytest.mark.parametrize("cls_name", CLASSES)
def test_none_alongside_a_valid_rename_still_raises(cls_name):
    outcomes = []
    for lib in (nx, fnx):
        graph = getattr(lib, cls_name)()
        graph.add_node("n0", label="L")
        graph.add_node("n1", label="L2")
        outcomes.append(
            _outcome(
                lambda g=graph, l=lib: sorted(
                    map(str, l.relabel_nodes(g, {"n0": "a", "n1": None}, copy=True).nodes)
                )
            )
        )
    assert outcomes[1] == outcomes[0]
    assert outcomes[0] == ("ValueError", "None cannot be a node")


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize("attr_name", list(ATTR_VARIANTS))
def test_ordinary_relabel_is_unaffected_and_keeps_attributes(cls_name, attr_name):
    """The guard must not disturb the fast path it protects.

    The attributed Graph case is the one that reaches the native kernel, so
    this is also the regression check that the kernel is still being used
    correctly rather than bypassed.
    """
    attrs = ATTR_VARIANTS[attr_name]
    results = []
    for lib in (nx, fnx):
        graph = getattr(lib, cls_name)()
        graph.add_node("n0", **attrs)
        graph.add_edge("n0", "n1", weight=3)
        relabeled = lib.relabel_nodes(graph, {"n0": "renamed"}, copy=True)
        results.append(
            (
                sorted(map(str, relabeled.nodes)),
                sorted((str(n), sorted(d.items())) for n, d in relabeled.nodes(data=True)),
                sorted(map(str, relabeled.edges(data=True))),
            )
        )
    assert results[1] == results[0]


def test_read_gexf_relabel_rejects_a_missing_label():
    """The concrete failure this bug produced, asserted end to end.

    A GEXF node may omit its label; the parser represents that as
    ``{'label': None}``, and relabel=True would map the id onto None.
    """
    payload = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<gexf xmlns="http://www.gexf.net/1.2draft" version="1.2">\n'
        '  <graph mode="static" defaultedgetype="undirected">\n'
        '    <nodes><node id="n0"/></nodes>\n'
        "    <edges/>\n"
        "  </graph>\n"
        "</gexf>"
    ).encode("utf-8")

    expected = nx.read_gexf(BytesIO(payload))
    actual = fnx.read_gexf(BytesIO(payload))
    assert list(actual.nodes(data=True)) == list(expected.nodes(data=True))

    for lib in (nx, fnx):
        with pytest.raises(ValueError, match="None cannot be a node"):
            lib.read_gexf(BytesIO(payload), relabel=True)


def test_no_graph_can_end_up_holding_a_none_node():
    """Belt and braces: the invariant itself, on every route in.

    Asserted on fnx directly rather than differentially — a graph containing
    None is wrong regardless of what networkx does about it.
    """
    for cls_name in CLASSES:
        graph = getattr(fnx, cls_name)()
        graph.add_node("n0", label=None)
        for attempt in (
            lambda g=graph: g.add_node(None),
            lambda g=graph: g.add_edge(None, "x"),
            lambda g=graph: fnx.relabel_nodes(g, {"n0": None}, copy=True),
            lambda g=graph: fnx.relabel_nodes(g, {"n0": None}, copy=False),
        ):
            with pytest.raises(ValueError, match="None cannot be a node"):
                attempt()
        assert None not in list(graph.nodes)
