"""br-r37-c1-vbe1o: number_of_edges DERIVES from degree, it does not count.

networkx's ``number_of_edges()`` is ``int(self.size())`` and ``size()`` is
``sum(d for _, d in self.degree()) // 2``. The answer therefore comes from the
DEGREE view, which reads assigned private storage. fnx counted
``len(self.edges)`` instead.

On the undirected classes both spellings agree, which is why this was invisible
there. On the DIRECTED classes they do not: total degree needs both ``_succ[n]``
and ``_pred[n]``, so a node carried only by an assigned ``_succ``/``_adj`` has no
``_pred`` row and networkx propagates the KeyError. fnx returned a plausible
number instead — the worse failure, because a raise is noticed and a wrong count
is not.

One spot accounted for 15 sweep cases: ``number_of_edges``, ``size`` and
``nx.density`` all derive from it.

THE TWIN TRAP, pinned in this file's history: there are two same-named
definitions. The factory `_number_of_edges_with_endpoints` is NOT the live path
for a graph carrying private storage — the instance-level wrapper is. Editing the
factory changed nothing, and only the sweep count failing to move revealed it.
"""

import networkx as nx
import pytest

import franken_networkx as fnx

ADJ = {"a": {"b": {}}, "b": {"a": {}}, "ZZ": {"b": {}}}
SUCC = {"a": {"b": {}}, "b": {}, "ZZ": {"b": {}}}
ALL = ["Graph", "MultiGraph", "DiGraph", "MultiDiGraph"]
DIRECTED = ["DiGraph", "MultiDiGraph"]


def build(mod, cls, attr, mapping):
    g = getattr(mod, cls)()
    g.add_edge("a", "b")
    setattr(g, attr, dict(mapping))
    return g


def out(call):
    try:
        return ("ok", call())
    except Exception as exc:  # noqa: BLE001
        return (type(exc).__name__,)


@pytest.mark.parametrize("cls", ALL)
def test_number_of_edges_matches_networkx_under_assigned_adj(cls):
    expected = out(lambda: build(nx, cls, "_adj", ADJ).number_of_edges())
    got = out(lambda: build(fnx, cls, "_adj", ADJ).number_of_edges())
    assert got == expected


@pytest.mark.parametrize("cls", ALL)
def test_size_matches_networkx_under_assigned_adj(cls):
    expected = out(lambda: build(nx, cls, "_adj", ADJ).size())
    got = out(lambda: build(fnx, cls, "_adj", ADJ).size())
    assert got == expected


@pytest.mark.parametrize("cls", DIRECTED)
def test_directed_counting_RAISES_like_networkx(cls):
    """The interesting half: nx raises, and a plausible number is worse.

    Total degree on a directed graph needs `_pred[n]` as well as `_succ[n]`, so a
    node reachable only through an assigned `_succ` has no predecessor row and
    networkx propagates the KeyError. Returning a number instead is silent.
    """
    for attr, mapping in (("_adj", ADJ), ("_succ", SUCC)):
        expected = out(lambda: build(nx, cls, attr, mapping).number_of_edges())
        got = out(lambda: build(fnx, cls, attr, mapping).number_of_edges())
        assert expected[0] == "KeyError", "nx contract moved; update this file"
        assert got == expected, f"{cls} {attr}"


@pytest.mark.parametrize("cls", ALL)
def test_density_follows_the_same_derivation(cls):
    """density is a cascade of the above and must not be fixed separately."""
    expected = out(lambda: round(nx.density(build(nx, cls, "_adj", ADJ)), 9))
    got = out(lambda: round(nx.density(build(fnx, cls, "_adj", ADJ)), 9))
    assert got == expected


@pytest.mark.parametrize("cls", ALL)
def test_ordinary_graphs_keep_the_native_counter(cls):
    """Negative control: no assignment, so the native count path is untouched."""
    gnx = getattr(nx, cls)()
    gfx = getattr(fnx, cls)()
    for g in (gnx, gfx):
        g.add_edge("a", "b")
        g.add_edge("b", "c")
        g.add_edge("a", "c")
        g.add_node("iso")
    assert gfx.number_of_edges() == gnx.number_of_edges()
    assert gfx.size() == gnx.size()
    assert gfx.number_of_edges("a", "b") == gnx.number_of_edges("a", "b")
    assert round(nx.density(gfx), 9) == round(nx.density(gnx), 9)


@pytest.mark.parametrize("cls", ALL)
def test_self_loops_still_count_correctly(cls):
    """The //2 halving is only exact if degree counts a self-loop twice."""
    gnx = getattr(nx, cls)()
    gfx = getattr(fnx, cls)()
    for g in (gnx, gfx):
        g.add_edge("a", "a")
        g.add_edge("a", "b")
    assert gfx.number_of_edges() == gnx.number_of_edges()
    assert gfx.size() == gnx.size()
