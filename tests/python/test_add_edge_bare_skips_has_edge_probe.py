"""Bare ``G.add_edge(u, v)`` must not pay a ``has_edge`` probe.

br-r37-c1-aenoattr. The simple-graph ``add_edge`` shim called
``self.has_edge(u, v)`` on EVERY call. That probe exists only to drive the
attribute MERGE branch, so with no attributes its result was used to choose
between a no-op and a no-op - while canonicalising BOTH endpoints, which at
2000-character node keys is the same O(key length) work ``raw_add_edge`` is about
to do again.

MEASURED, arms alternated three times each (pure-Python packages, no build),
under 14 concurrent peer build processes at 888 percent CPU:

    OLD  6844.0us  6598.1us  6787.5us    median 6787.5us
    NEW  6251.0us  6083.8us  6056.1us    median 6083.8us

1.116x on bare add_edge, complete separation - the worst NEW run beats the best
OLD one. The with-attributes path is untouched and measured unchanged.

WHY THIS IS SAFE, and it was verified before the probe was removed rather than
argued: re-adding an existing edge with NO attributes leaves the datadict
untouched, adds no edge, and returns None - in BOTH libraries. So calling
``raw_add_edge`` unconditionally is exactly what networkx does. That equivalence
is what this file pins; if it ever stops holding, the probe has to come back.

THE MULTIGRAPH CLASSES ARE THE CONTROL. Their shim never had this probe, because
there a repeat add legitimately creates a NEW parallel edge. They are tested here
so that a future "simplification" that unifies the two shims cannot quietly give
multigraphs the simple-graph behaviour.

The ordering of the shim's guards also matters and is pinned: the None and
unhashable-endpoint checks run BEFORE the early return, so error behaviour is
identical for bare and attributed calls.
"""

from __future__ import annotations

import networkx as nx
import pytest

import franken_networkx as fnx

SIMPLE = ["Graph", "DiGraph"]
MULTI = ["MultiGraph", "MultiDiGraph"]
ALL = SIMPLE + MULTI


def _edge_state(graph, u="a", v="b"):
    if graph.is_multigraph():
        data = sorted(
            (k, tuple(sorted(d.items()))) for k, d in graph.get_edge_data(u, v).items()
        )
    else:
        data = tuple(sorted(graph.get_edge_data(u, v).items()))
    return graph.number_of_edges(), graph.number_of_nodes(), data


@pytest.mark.parametrize("cls", ALL)
def test_bare_readd_matches_networkx(cls):
    """THE equivalence the removal rests on."""
    got, want = getattr(fnx, cls)(), getattr(nx, cls)()
    returns = []
    for g in (got, want):
        g.add_edge("a", "b", weight=7, color="red")
        returns.append(g.add_edge("a", "b"))
    # Simple graphs return None; the MULTI classes return the new key, in
    # networkx too. Compare the two libraries rather than assuming either.
    assert returns[0] == returns[1]
    if cls in SIMPLE:
        assert returns[0] is None
    assert _edge_state(got) == _edge_state(want)


@pytest.mark.parametrize("cls", ALL)
def test_repeated_bare_adds_match_networkx(cls):
    """Many repeats: multigraphs must keep growing, simple graphs must not."""
    got, want = getattr(fnx, cls)(), getattr(nx, cls)()
    for g in (got, want):
        g.add_edge("a", "b", weight=1)
        for _ in range(5):
            g.add_edge("a", "b")
    assert _edge_state(got) == _edge_state(want)
    if cls in SIMPLE:
        assert got.number_of_edges() == 1
    else:
        assert got.number_of_edges() == 6, "multigraph repeat add must add an edge"


@pytest.mark.parametrize("cls", ALL)
def test_attribute_merge_path_is_unchanged(cls):
    """The branch the probe actually exists for."""
    got, want = getattr(fnx, cls)(), getattr(nx, cls)()
    for g in (got, want):
        g.add_edge("a", "b", weight=1, keep="yes")
        g.add_edge("a", "b", weight=2)
        g.add_edge("a", "b", extra=3)
    assert _edge_state(got) == _edge_state(want)


@pytest.mark.parametrize("cls", ALL)
def test_bare_add_of_a_new_edge_matches_networkx(cls):
    got, want = getattr(fnx, cls)(), getattr(nx, cls)()
    for g in (got, want):
        g.add_edge("a", "b")
        g.add_edge("b", "c")
        g.add_edge("c", "c")  # self-loop
    assert sorted(map(str, got.nodes())) == sorted(map(str, want.nodes()))
    assert got.number_of_edges() == want.number_of_edges()


@pytest.mark.parametrize("cls", ALL)
@pytest.mark.parametrize("bare", [True, False], ids=["bare", "with_attrs"])
def test_guard_ordering_is_identical_for_bare_and_attributed(cls, bare):
    """The None/unhashable guards must run BEFORE the early return.

    Compared by exception TYPE and ARGS, and by the side effect networkx has of
    creating the first endpoint before raising on the second.
    """
    kw = {} if bare else {"weight": 1}

    def run(lib):
        g = getattr(lib, cls)()
        out = []
        for u, v in ((None, "b"), ("a", None), (["bad"], "b"), ("a", ["bad"])):
            try:
                g.add_edge(u, v, **kw)
                out.append(("ok", None))
            except Exception as exc:  # noqa: BLE001 - comparing the raise itself
                out.append((type(exc).__name__, exc.args))
        return out, sorted(map(str, g.nodes()))

    assert run(fnx) == run(nx)


@pytest.mark.parametrize("cls", SIMPLE)
def test_bare_readd_does_not_disturb_a_long_key_graph(cls):
    """The shape the lever targets: 2000-character keys, endpoints present."""
    key_len = 2000
    got, want = getattr(fnx, cls)(), getattr(nx, cls)()
    u, v = "u".ljust(key_len, "x"), "v".ljust(key_len, "y")
    for g in (got, want):
        g.add_edge(u, v, weight=5)
        g.add_edge(u, v)
        g.add_edge(v, u)
    assert _edge_state(got, u, v) == _edge_state(want, u, v)
