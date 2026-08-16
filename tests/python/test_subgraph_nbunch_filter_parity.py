"""Parity lock for br-r37-c1-yioox — the induced-node filter.

``G.subgraph(nbunch)`` builds a set of induced nodes. The large-nbunch branch
now builds the candidate set once and intersects with the graph's node set,
instead of a per-node loop that hashed every node three times (an explicit
hash() for the error contract, again for the membership test, again for the
add).

Two properties make the rewrite safe, and both are asserted because both are
easy to lose:

* the result is a SET, so nbunch ORDER cannot matter — but the induced
  subgraph's node and edge ITERATION order must still match networkx, which is
  what actually reaches callers;
* the unhashable-element error must survive. It cannot ride on the membership
  test: fnx's ``n in G`` answers False for an unhashable argument, exactly as
  networkx's does, so nothing would raise. ``set()`` raises the same TypeError
  and the offending element is located on that path.

There are TWO branches — a large nbunch intersects, a small one keeps the
per-node loop — so every case below is run across sizes that straddle the
threshold (nbunch*4 >= len(G)).
"""

from __future__ import annotations

import networkx as nx
import pytest

import franken_networkx as fnx

CLASSES = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]
N = 40


def _build(lib, cls_name):
    graph = getattr(lib, cls_name)()
    for i in range(N):
        graph.add_edge(f"n{i}", f"n{(i * 7 + 3) % N}", weight=float(i % 5))
    graph.add_node("iso")
    return graph


def _pair(cls_name):
    return _build(nx, cls_name), _build(fnx, cls_name)


def _shape(sub):
    return (
        list(sub.nodes),
        list(sub.edges),
        list(sub.nodes(data=True)),
        list(sub.edges(data=True)),
        len(sub),
        sub.number_of_edges(),
    )


# Sizes deliberately straddle the large/small branch boundary (4*k >= len(G)).
@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize("size", [0, 1, 2, 9, 10, 11, 20, N], ids=lambda s: f"nbunch{s}")
def test_induced_subgraph_matches_networkx_across_both_branches(cls_name, size):
    gnx, gfx = _pair(cls_name)
    nbunch = [f"n{i}" for i in range(size)]
    assert _shape(gfx.subgraph(nbunch)) == _shape(gnx.subgraph(nbunch))


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize("size", [2, 20], ids=["small", "large"])
def test_reversing_the_nbunch_tracks_networkx(cls_name, size):
    """Reversing the nbunch changes the CONTENT not at all — and changes the
    node ITERATION order in exactly the way networkx's does.

    Worth stating precisely, because I first asserted the stronger claim and it
    is false of BOTH libraries: the induced node set is set-backed, so its
    iteration order depends on insertion order, and reversing the nbunch does
    reorder it. networkx behaves identically. What must hold is that fnx
    matches networkx FOR EACH ordering — which is also the assertion that
    catches a filter rewrite changing insertion order, since a set built by
    intersection does not iterate like one built by repeated adds.
    """
    gnx, gfx = _pair(cls_name)
    forward = [f"n{i}" for i in range(size)]
    backward = list(reversed(forward))
    assert _shape(gfx.subgraph(forward)) == _shape(gnx.subgraph(forward))
    assert _shape(gfx.subgraph(backward)) == _shape(gnx.subgraph(backward))
    # Content is order-independent even where iteration order is not.
    assert sorted(gfx.subgraph(backward).nodes) == sorted(gfx.subgraph(forward).nodes)
    assert sorted(map(str, gfx.subgraph(backward).edges)) == sorted(
        map(str, gfx.subgraph(forward).edges)
    )


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize("size", [2, 20], ids=["small", "large"])
def test_duplicates_and_absent_nodes_match_networkx(cls_name, size):
    gnx, gfx = _pair(cls_name)
    nbunch = [f"n{i}" for i in range(size)]
    for variant in (nbunch + nbunch, nbunch + ["ghost"], ["ghost"], nbunch + ["iso"]):
        assert _shape(gfx.subgraph(variant)) == _shape(gnx.subgraph(variant)), variant


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize("size", [2, 20], ids=["small", "large"])
def test_unhashable_element_raises_networkxs_error_on_both_branches(cls_name, size):
    """The error the explicit hash() used to produce, on BOTH branches.

    Membership cannot carry this check — `n in G` answers False for an
    unhashable argument in both libraries — so losing it would silently drop
    the bad element instead of raising.
    """
    gnx, gfx = _pair(cls_name)
    nbunch = [f"n{i}" for i in range(size)] + [["un", "hashable"]]
    outcomes = []
    for graph in (gnx, gfx):
        try:
            graph.subgraph(nbunch)
            outcomes.append(("no-raise", None))
        except Exception as exc:  # noqa: BLE001
            outcomes.append((type(exc).__name__, str(exc)))
    assert outcomes[1] == outcomes[0]
    assert outcomes[0][0] == "NetworkXError"


@pytest.mark.parametrize("cls_name", CLASSES)
def test_non_sequence_nbunch_forms_match_networkx(cls_name):
    """A single node, a generator and a set all still work."""
    gnx, gfx = _pair(cls_name)
    for make in (
        lambda: "n1",
        lambda: (f"n{i}" for i in range(20)),
        lambda: {f"n{i}" for i in range(20)},
        lambda: tuple(f"n{i}" for i in range(20)),
    ):
        assert _shape(gfx.subgraph(make())) == _shape(gnx.subgraph(make()))


@pytest.mark.parametrize("cls_name", CLASSES)
def test_subgraph_view_stays_live(cls_name):
    """The filter is built once; the view over it must still track the parent."""
    gnx, gfx = _pair(cls_name)
    nbunch = [f"n{i}" for i in range(20)]
    sub_nx, sub_fx = gnx.subgraph(nbunch), gfx.subgraph(nbunch)
    for graph in (gnx, gfx):
        graph.add_edge("n0", "n1", weight=99.0)
        graph.remove_edge("n2", "n17")
    assert _shape(sub_fx) == _shape(sub_nx)
