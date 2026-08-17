"""`G.in_edges` and `G.out_edges` are not Mappings in fnx, but are in networkx.

FOUND BY A SYSTEMATIC PROTOCOL SWEEP, which was written because br-r37-c1-p1dbu
(`G.edges(keys=True)` silently losing `.items()`) was found by accident. That
defect class — a view whose class NAME matches while a protocol is missing — is
invisible to every name-based parity check, so it has to be looked for on
purpose. This is the same class, functional rather than cosmetic, and larger.

networkx's `OutEdgeView` / `InEdgeView` are Mappings: `G.out_edges[u, v]` returns
the edge attribute dict, and `.get()` / `.items()` / `.keys()` / `.values()` all
work. fnx's same-named views expose none of it:

    DiGraph        nx                      fnx
    out_edges[u,v]     {'w': 1.0}              TypeError (not subscriptable)
    in_edges[u,v]      {'w': 1.0}              TypeError (not subscriptable)
    out_edges.get(...) {'w': 1.0}              AttributeError
    out_edges.items()  2 pairs                 AttributeError

    MultiDiGraph
    out_edges[u,v,0]   {'w': 1.0}              TypeError (not subscriptable)
    out_edges[u,v]     ValueError              TypeError

Twelve of twelve probes diverge across the two directed classes, and the last row
shows the divergence persists even where BOTH fail: networkx raises ValueError
for a 2-tuple on a multigraph view, fnx raises TypeError because the view is not
subscriptable at all.

THE WORKING SIBLING IS THE CONTROL. `G.edges[u, v]` DOES work on fnx's DiGraph
and returns the same dict networkx does, which is what makes this a missing
sibling rather than an unimplemented feature: the surface exists one name over.
That sibling is pinned as a passing test below so a fix cannot regress it.

NOT ATTEMPTED HERE. Wiring the Mapping surface onto these views needs a build to
verify, and the host is under a build halt (5-minute loadavg ~190). The
divergence is recorded strictly so it cannot rot.
"""

from __future__ import annotations

import networkx as nx
import pytest

import franken_networkx as fnx

DIRECTED = ["DiGraph", "MultiDiGraph"]

XFAIL = pytest.mark.xfail(
    strict=True,
    reason="br-r37-c1-dfivn: fnx's InEdgeView / OutEdgeView are not Mappings — "
    "no __getitem__, get, items, keys or values — while networkx's are. Found by "
    "a systematic protocol sweep; same defect class as br-r37-c1-p1dbu. Needs a "
    "build to fix and verify, which the build halt currently forbids.",
)


def _pair(cls_name):
    gnx, gfx = getattr(nx, cls_name)(), getattr(fnx, cls_name)()
    for graph in (gnx, gfx):
        graph.add_edge("a", "b", w=1.0)
        graph.add_edge("b", "c", w=2.0)
    return gnx, gfx


def _outcome(fn):
    try:
        return ("val", repr(fn()))
    except Exception as exc:  # noqa: BLE001
        return ("exc", type(exc).__name__)


# ------------------------------------------------------------------ divergences


@pytest.mark.parametrize("cls_name", [pytest.param(c, marks=XFAIL) for c in DIRECTED])
@pytest.mark.parametrize("view", ["in_edges", "out_edges"])
def test_directed_edge_view_is_subscriptable_like_networkx(cls_name, view):
    gnx, gfx = _pair(cls_name)
    key = ("a", "b", 0) if cls_name.startswith("Multi") else ("a", "b")
    want = _outcome(lambda: getattr(gnx, view)[key])
    got = _outcome(lambda: getattr(gfx, view)[key])
    assert got == want, f"{cls_name}.{view}[{key}]: nx={want} fnx={got}"


@pytest.mark.parametrize("cls_name", [pytest.param(c, marks=XFAIL) for c in DIRECTED])
@pytest.mark.parametrize("attr", ["get", "items", "keys", "values"])
@pytest.mark.parametrize("view", ["in_edges", "out_edges"])
def test_directed_edge_view_keeps_the_mapping_surface(cls_name, attr, view):
    gnx, gfx = _pair(cls_name)
    assert hasattr(getattr(gnx, view), attr), "networkx oracle changed"
    assert hasattr(getattr(gfx, view), attr), f"{cls_name}.{view} lost .{attr}"


@pytest.mark.parametrize("cls_name", [pytest.param(c, marks=XFAIL) for c in DIRECTED])
@pytest.mark.parametrize("view", ["in_edges", "out_edges"])
def test_directed_edge_view_wrong_arity_raises_the_same_exception(cls_name, view):
    """Even where BOTH fail the exception diverges: networkx raises ValueError
    for a bad-arity key, fnx raises TypeError because the view is not
    subscriptable at all. Pinned so a fix produces nx's exception, not merely
    some exception."""
    gnx, gfx = _pair(cls_name)
    key = ("a", "b") if cls_name.startswith("Multi") else ("a", "b", 0)
    want = _outcome(lambda: getattr(gnx, view)[key])
    got = _outcome(lambda: getattr(gfx, view)[key])
    assert got == want, f"{cls_name}.{view}[{key}]: nx={want} fnx={got}"


# --------------------------------------------------- the sibling that already works


@pytest.mark.parametrize("cls_name", DIRECTED)
def test_the_plain_edges_view_sibling_is_subscriptable(cls_name):
    """THE CONTROL. `G.edges[u, v]` already works and returns what networkx
    returns — which is why the in/out views are a missing sibling rather than an
    unimplemented feature, and why a fix has a working model to copy."""
    gnx, gfx = _pair(cls_name)
    key = ("a", "b", 0) if cls_name.startswith("Multi") else ("a", "b")
    assert dict(gfx.edges[key]) == dict(gnx.edges[key])


@pytest.mark.parametrize("cls_name", DIRECTED)
@pytest.mark.parametrize("view", ["in_edges", "out_edges"])
def test_the_parts_of_these_views_that_do_agree(cls_name, view):
    """Bounds any fix: iteration contents and order, length, and containment all
    agree today and must survive gaining the Mapping surface."""
    gnx, gfx = _pair(cls_name)
    vnx, vfx = getattr(gnx, view), getattr(gfx, view)
    assert list(vfx) == list(vnx)
    assert len(vfx) == len(vnx)
    for edge in list(vnx):
        assert (edge in vfx) == (edge in vnx), edge
    assert type(vfx).__name__ == type(vnx).__name__


@pytest.mark.parametrize("cls_name", DIRECTED)
@pytest.mark.parametrize("view", ["in_edges", "out_edges"])
def test_call_forms_of_these_views_agree(cls_name, view):
    """The callable surface is separate from the Mapping surface and is fine."""
    gnx, gfx = _pair(cls_name)
    for call in (
        lambda v: v(data=True),
        lambda v: v(data="w"),
        lambda v: v(["a", "b"]),
    ):
        want = sorted(map(str, call(getattr(gnx, view))))
        got = sorted(map(str, call(getattr(gfx, view))))
        assert got == want
