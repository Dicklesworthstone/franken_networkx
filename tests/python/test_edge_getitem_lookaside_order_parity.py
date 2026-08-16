"""Lock for br-r37-c1-y2ww1 — `G.edges[u, v]` lookaside ordering.

`EdgeView.__getitem__` now consults the endpoint lookaside before probing the
graph for ``u``, because a lookaside hit is existence proof. That is a pure
reordering of two checks, but it moves a HASH across a KeyError boundary, which
is the part that can silently break:

networkx evaluates ``self._adjdict[u][v]``. It hashes ``u``; if ``u`` is absent
it raises KeyError *without ever hashing* ``v``. So an unhashable ``v`` on a
graph that is missing ``u`` must be a **KeyError**, not a TypeError — while an
unhashable ``v`` on a graph that HAS ``u`` must be a TypeError. Canonicalization
reads characters and does not hash, so nothing enforces this except the explicit
ordering the fix has to preserve.

Both sides of that boundary are asserted here, along with the rest of the
subscript's error surface, all against the live networkx in the environment.
"""

from __future__ import annotations

import networkx as nx
import pytest

import franken_networkx as fnx

CLASSES = ["Graph", "DiGraph"]

# br-r37-c1-60627: two pre-existing divergences live on the DIRECTED view, which
# this bead's lever did not touch — a slice raises a bare TypeError instead of
# networkx's NetworkXError, and an absent `u` hashes `v` before short-circuiting.
# xfail-STRICT so fixing that bead turns these green loudly.
_DIRECTED_XFAIL = {"unhashable-v-absent-u", "slice"}


class _Unhashable(str):
    __hash__ = None


def _pair(cls_name):
    made = []
    for lib in (nx, fnx):
        graph = getattr(lib, cls_name)()
        graph.add_edge("a", "b", w=1)
        graph.add_edge("b", "c", w=2)
        graph.add_node("iso")
        made.append(graph)
    return made


def _outcome(fn, graph):
    try:
        result = fn(graph)
    except Exception as exc:  # noqa: BLE001 - the exception IS the contract
        return ("raised", type(exc).__name__)
    return ("value", dict(result))


PROBES = {
    "present": lambda g: g.edges["a", "b"],
    "present-reversed": lambda g: g.edges["b", "a"],
    "absent-v": lambda g: g.edges["a", "zz"],
    "absent-u": lambda g: g.edges["zz", "b"],
    "both-absent": lambda g: g.edges["zz", "yy"],
    "isolated-u": lambda g: g.edges["iso", "b"],
    "isolated-v": lambda g: g.edges["a", "iso"],
    "unhashable-u": lambda g: g.edges[_Unhashable("a"), "b"],
    "unhashable-v": lambda g: g.edges["a", _Unhashable("b")],
    "unhashable-v-absent-u": lambda g: g.edges["zz", _Unhashable("b")],
    "unhashable-both": lambda g: g.edges[_Unhashable("a"), _Unhashable("b")],
    "one-element": lambda g: g.edges[("a",)],
    "three-element": lambda g: g.edges["a", "b", "c"],
    "slice": lambda g: g.edges[1:2],
}


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize("probe_name", list(PROBES))
def test_edge_subscript_matches_networkx(cls_name, probe_name, request):
    if cls_name == "DiGraph" and probe_name in _DIRECTED_XFAIL:
        request.node.add_marker(
            pytest.mark.xfail(strict=True, reason="br-r37-c1-60627")
        )
    gnx, gfx = _pair(cls_name)
    probe = PROBES[probe_name]
    assert _outcome(probe, gfx) == _outcome(probe, gnx)


@pytest.mark.parametrize(
    "cls_name",
    [
        "Graph",
        pytest.param(
            "DiGraph",
            marks=pytest.mark.xfail(
                strict=True,
                reason="br-r37-c1-60627: the directed view hashes v before "
                "establishing u's presence",
            ),
        ),
    ],
)
def test_unhashable_v_boundary_is_ordered_like_networkx(cls_name):
    """The exact hazard: the same unhashable `v`, on both sides of `u`.

    Present `u` must hash `v` and raise TypeError; absent `u` must short-circuit
    to KeyError before `v` is ever hashed.
    """
    gnx, gfx = _pair(cls_name)
    for graph, label in ((gnx, "nx"), (gfx, "fnx")):
        with pytest.raises(TypeError):
            graph.edges["a", _Unhashable("b")]
        with pytest.raises(KeyError):
            graph.edges["zz", _Unhashable("b")]


@pytest.mark.parametrize("cls_name", CLASSES)
def test_repeat_read_is_the_same_live_dict(cls_name):
    """The lookaside must hand back the live attr dict, not a copy."""
    gnx, gfx = _pair(cls_name)
    for graph in (gnx, gfx):
        first = graph.edges["a", "b"]
        assert graph.edges["a", "b"] is first
        first["injected"] = 7
        assert graph.edges["a", "b"]["injected"] == 7
        assert graph["a"]["b"]["injected"] == 7
    assert dict(gfx.edges["a", "b"]) == dict(gnx.edges["a", "b"])


@pytest.mark.parametrize("cls_name", CLASSES)
def test_lookaside_cannot_survive_edge_removal(cls_name):
    """A hit is only existence proof while the lookaside is invalidated."""
    gnx, gfx = _pair(cls_name)
    for graph in (gnx, gfx):
        graph.edges["a", "b"]  # populate
        graph.remove_edge("a", "b")
    assert _outcome(lambda g: g.edges["a", "b"], gfx) == _outcome(
        lambda g: g.edges["a", "b"], gnx
    )
    for graph in (gnx, gfx):
        graph.add_edge("a", "b", w=99)
    assert dict(gfx.edges["a", "b"]) == dict(gnx.edges["a", "b"])


@pytest.mark.parametrize("cls_name", CLASSES)
def test_lookaside_cannot_survive_node_removal(cls_name):
    gnx, gfx = _pair(cls_name)
    for graph in (gnx, gfx):
        graph.edges["a", "b"]
        graph.remove_node("a")
    assert _outcome(lambda g: g.edges["a", "b"], gfx) == _outcome(
        lambda g: g.edges["a", "b"], gnx
    )
