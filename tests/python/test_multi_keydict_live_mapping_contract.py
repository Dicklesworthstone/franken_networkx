"""What networkx's multigraph keydict actually IS, as an executable spec.

br-r37-c1-f3i50. ``G.get_edge_data(u, v)`` on a multigraph returns
``self._adj[u][v]`` in networkx — the graph's own keydict, not a view of it and
not a copy. fnx builds a fresh outer mapping whose VALUES are the live per-edge
attr dicts, so the inner half agrees and the outer half does not.

THE POINT OF THIS FILE is to pin what the eventual fix must satisfy, because the
fix named on the bead — "hand back a live keydict mirror" — is NOT sufficient on
its own, and that is only visible once you check what insertion does to the rest
of the graph:

    d = g.get_edge_data('a', 'b')     # nx: this IS g._adj['a']['b']
    d['newkey'] = {'w': 7}
    g.number_of_edges()               # 2 -> 3
    g.degree('a')                     # 3
    ('a','b','newkey') in g.edges(keys=True)   # True

Insertion into that mapping creates a REAL EDGE. So a fnx fix that merely returns
a live cached mirror would make the key visible in the mapping while
``G.edges``, ``number_of_edges`` and ``degree`` still disagreed — trading today's
"silently dropped" for a NEW internal inconsistency. Reaching parity requires the
returned mapping to WRITE THROUGH to the native store, which is the same write
barrier br-r37-c1-igdzi needs to tell a materialised attr dict from a mutated
one. The two beads share a substrate.

HOW THIS FILE IS WRITTEN. Every expectation is taken from live networkx in the
same test rather than hard-coded, so it cannot rot against a networkx upgrade.
The fnx assertions are split in two:

  * the parts fnx ALREADY satisfies are asserted strictly, so they are locked and
    a regression fails the suite;
  * the parts fnx does not yet satisfy are marked ``xfail(strict=True)``, so they
    document the gap AND flip the suite red the moment someone fixes them — which
    is exactly how br-r37-c1-0k6zl's guard surfaced its own fix this session.
"""

import pytest

import networkx as nx

import franken_networkx as fnx

CLASSES = ["MultiGraph", "MultiDiGraph"]


def _pair(mod, class_name, par=2):
    graph = getattr(mod, class_name)()
    for i in range(par):
        graph.add_edge("a", "b", w=i)
    return graph


# ---------------------------------------------------------------- locked today


@pytest.mark.parametrize("class_name", CLASSES)
def test_inner_attr_mutation_propagates(class_name):
    """The VALUES are live in both libraries. fnx already satisfies this."""
    for mod in (nx, fnx):
        graph = _pair(mod, class_name)
        graph.get_edge_data("a", "b")[0]["w"] = 99
        assert graph["a"]["b"][0]["w"] == 99, mod.__name__
        assert graph.edges["a", "b", 0]["w"] == 99, mod.__name__


@pytest.mark.parametrize("class_name", CLASSES)
def test_keydict_contents_match_networkx(class_name):
    """Key set, ordering and attribute values agree — only liveness differs."""
    got = _pair(fnx, class_name).get_edge_data("a", "b")
    want = _pair(nx, class_name).get_edge_data("a", "b")
    assert list(got.keys()) == list(want.keys())
    assert {k: dict(v) for k, v in got.items()} == {k: dict(v) for k, v in want.items()}


@pytest.mark.parametrize("class_name", CLASSES)
def test_graph_side_mutations_are_visible_on_a_fresh_read(class_name):
    """Whatever the mapping's identity, a NEW read must see graph changes.

    This is the half a caching fix is most likely to break, so it is locked
    strictly: add and remove parallel edges and re-read.
    """
    for mod in (nx, fnx):
        graph = _pair(mod, class_name)
        assert list(graph.get_edge_data("a", "b")) == [0, 1], mod.__name__
        graph.add_edge("a", "b", w=2)
        assert list(graph.get_edge_data("a", "b")) == [0, 1, 2], mod.__name__
        graph.remove_edge("a", "b", 1)
        assert list(graph.get_edge_data("a", "b")) == [0, 2], mod.__name__


@pytest.mark.parametrize("class_name", CLASSES)
def test_insertion_does_not_corrupt_the_graph_either_way(class_name):
    """fnx must stay SELF-consistent even though it diverges from networkx.

    Today fnx drops the insertion entirely. That is a divergence from networkx,
    but it is internally consistent: the mapping, ``G.edges``, ``number_of_edges``
    and ``degree`` all agree that the key does not exist. Any fix must preserve
    that agreement — a mapping that reports a key ``G.edges`` denies would be
    worse than the current behaviour, not better.
    """
    graph = _pair(fnx, class_name)
    mapping = graph.get_edge_data("a", "b")
    mapping["newkey"] = {"w": 7}

    in_mapping = "newkey" in graph.get_edge_data("a", "b")
    in_edges = ("a", "b", "newkey") in list(graph.edges(keys=True))
    counted = graph.number_of_edges() == 3
    assert in_mapping == in_edges == counted, (
        "fnx became internally inconsistent about 'newkey': "
        f"mapping={in_mapping} edges={in_edges} count={counted}. Whatever fnx "
        "decides about keydict insertion, these three must agree."
    )


# ------------------------------------------------------- the documented gap


@pytest.mark.parametrize("class_name", CLASSES)
@pytest.mark.xfail(
    strict=True,
    reason="br-r37-c1-f3i50: fnx builds the outer mapping per call, so it is not "
    "the graph's keydict and repeated reads are distinct objects. networkx "
    "returns self._adj[u][v] itself. Needs the live-mirror substrate "
    "(br-r37-c1-himzq).",
)
def test_repeated_reads_return_the_same_object(class_name):
    graph = _pair(fnx, class_name)
    reference = _pair(nx, class_name)
    assert (reference.get_edge_data("a", "b") is reference.get_edge_data("a", "b")), (
        "networkx is expected to return its own keydict"
    )
    assert graph.get_edge_data("a", "b") is graph.get_edge_data("a", "b")


@pytest.mark.parametrize("class_name", CLASSES)
@pytest.mark.xfail(
    strict=True,
    reason="br-r37-c1-f3i50: insertion into the returned mapping must create a "
    "real edge, as it does in networkx (number_of_edges 2->3, degree 3). That "
    "needs a WRITE-THROUGH mapping, not merely a live mirror — the same write "
    "barrier br-r37-c1-igdzi needs.",
)
def test_keydict_insertion_creates_a_real_edge(class_name):
    # Establish the contract from live networkx, not from a hard-coded number.
    reference = _pair(nx, class_name)
    before = reference.number_of_edges()
    reference.get_edge_data("a", "b")["newkey"] = {"w": 7}
    assert reference.number_of_edges() == before + 1
    assert ("a", "b", "newkey") in list(reference.edges(keys=True))
    assert reference.degree("a") == before + 1

    graph = _pair(fnx, class_name)
    before = graph.number_of_edges()
    graph.get_edge_data("a", "b")["newkey"] = {"w": 7}
    assert graph.number_of_edges() == before + 1
    assert ("a", "b", "newkey") in list(graph.edges(keys=True))
    assert graph.degree("a") == before + 1
