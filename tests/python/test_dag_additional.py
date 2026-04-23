"""Tests for additional DAG algorithm bindings.

Tests cover:
- is_aperiodic
- antichains
- immediate_dominators
- dominance_frontiers
"""

import networkx as nx
import pytest
import franken_networkx as fnx


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def chain():
    """a->b->c."""
    g = fnx.DiGraph()
    g.add_edge("a", "b")
    g.add_edge("b", "c")
    return g


@pytest.fixture
def diamond():
    """a->b, a->c, b->d, c->d."""
    g = fnx.DiGraph()
    g.add_edge("a", "b")
    g.add_edge("a", "c")
    g.add_edge("b", "d")
    g.add_edge("c", "d")
    return g


@pytest.fixture
def cycle3():
    """a->b->c->a."""
    g = fnx.DiGraph()
    g.add_edge("a", "b")
    g.add_edge("b", "c")
    g.add_edge("c", "a")
    return g


# ---------------------------------------------------------------------------
# is_aperiodic
# ---------------------------------------------------------------------------

class TestIsAperiodic:
    def test_cycle_periodic(self, cycle3):
        assert fnx.is_aperiodic(cycle3) is False

    def test_with_self_loop(self):
        g = fnx.DiGraph()
        g.add_edge("a", "b")
        g.add_edge("b", "c")
        g.add_edge("c", "a")
        g.add_edge("a", "a")
        assert fnx.is_aperiodic(g) is True

    def test_two_cycle_lengths(self):
        g = fnx.DiGraph()
        g.add_edge("a", "b")
        g.add_edge("b", "a")
        g.add_edge("a", "c")
        g.add_edge("c", "d")
        g.add_edge("d", "a")
        assert fnx.is_aperiodic(g) is True

    def test_raises_on_not_strongly_connected(self, chain):
        with pytest.raises(fnx.NetworkXError, match="Graph is not strongly connected."):
            fnx.is_aperiodic(chain)

    def test_raises_on_undirected(self):
        g = fnx.Graph()
        g.add_edge("a", "b")
        with pytest.raises(
            fnx.NetworkXError,
            match="is_aperiodic not defined for undirected graphs",
        ):
            fnx.is_aperiodic(g)

    @pytest.mark.parametrize(
        ("fnx_cls", "nx_cls", "builder"),
        [
            (fnx.Graph, nx.Graph, lambda graph: None),
            (fnx.MultiGraph, nx.MultiGraph, lambda graph: None),
            (fnx.DiGraph, nx.DiGraph, lambda graph: None),
            (fnx.MultiDiGraph, nx.MultiDiGraph, lambda graph: None),
            (fnx.DiGraph, nx.DiGraph, lambda graph: graph.add_node("a")),
            (fnx.MultiDiGraph, nx.MultiDiGraph, lambda graph: graph.add_node("a")),
            (fnx.DiGraph, nx.DiGraph, lambda graph: graph.add_edge("a", "a")),
            (
                fnx.DiGraph,
                nx.DiGraph,
                lambda graph: graph.add_edges_from([("a", "b"), ("b", "c")]),
            ),
            (
                fnx.DiGraph,
                nx.DiGraph,
                lambda graph: graph.add_edges_from([("a", "b"), ("b", "c"), ("c", "a")]),
            ),
            (
                fnx.DiGraph,
                nx.DiGraph,
                lambda graph: graph.add_edges_from(
                    [("a", "b"), ("b", "c"), ("c", "a"), ("a", "a")]
                ),
            ),
        ],
    )
    def test_matches_networkx_without_fallback(
        self, monkeypatch, fnx_cls, nx_cls, builder
    ):
        graph = fnx_cls()
        expected = nx_cls()
        builder(graph)
        builder(expected)

        try:
            expected_result = nx.is_aperiodic(expected)
        except Exception as exc:
            expected_result = exc

        monkeypatch.setattr(
            nx,
            "is_aperiodic",
            lambda *args, **kwargs: (_ for _ in ()).throw(
                AssertionError("NetworkX is_aperiodic fallback should not be used")
            ),
        )

        if isinstance(expected_result, Exception):
            with pytest.raises(Exception) as fnx_exc:
                fnx.is_aperiodic(graph)
            assert type(fnx_exc.value).__name__ == type(expected_result).__name__
            assert str(fnx_exc.value) == str(expected_result)
        else:
            assert fnx.is_aperiodic(graph) is expected_result


# ---------------------------------------------------------------------------
# antichains
# ---------------------------------------------------------------------------

class TestAntichains:
    def test_chain(self, chain):
        # antichains returns a generator; materialise before counting.
        acs = list(fnx.antichains(chain))
        # Chain a->b->c: antichains are {}, {a}, {b}, {c}
        assert len(acs) == 4
        assert [] in acs

    def test_diamond(self, diamond):
        acs = list(fnx.antichains(diamond))
        # b and c are incomparable
        has_bc = any(
            set(ac) == {"b", "c"} for ac in acs
        )
        assert has_bc

    def test_empty(self):
        g = fnx.DiGraph()
        acs = list(fnx.antichains(g))
        assert acs == [[]]

    def test_raises_on_undirected(self):
        g = fnx.Graph()
        g.add_edge("a", "b")
        # antichains returns a generator; the NetworkXNotImplemented only
        # fires on first next() — materialise via list() to trigger.
        with pytest.raises(fnx.NetworkXNotImplemented):
            list(fnx.antichains(g))


# ---------------------------------------------------------------------------
# immediate_dominators
# ---------------------------------------------------------------------------

class TestImmediateDominators:
    def test_chain(self, chain):
        # Upstream nx.immediate_dominators excludes the start node from
        # the returned dict (franken_networkx-y87ra).
        idom = fnx.immediate_dominators(chain, "a")
        assert "a" not in idom
        assert idom["b"] == "a"
        assert idom["c"] == "b"

    def test_diamond(self, diamond):
        idom = fnx.immediate_dominators(diamond, "a")
        assert "a" not in idom
        assert idom["b"] == "a"
        assert idom["c"] == "a"
        assert idom["d"] == "a"

    def test_matches_networkx(self, chain):
        import networkx as nx
        nxg = nx.DiGraph(); nxg.add_edges_from([("a","b"),("b","c")])
        assert fnx.immediate_dominators(chain, "a") == nx.immediate_dominators(nxg, "a")

    def test_raises_on_undirected(self):
        g = fnx.Graph()
        g.add_edge("a", "b")
        with pytest.raises(fnx.NetworkXNotImplemented):
            fnx.immediate_dominators(g, "a")


# ---------------------------------------------------------------------------
# dominance_frontiers
# ---------------------------------------------------------------------------

class TestDominanceFrontiers:
    def test_chain(self, chain):
        df = fnx.dominance_frontiers(chain, "a")
        # No join points in a chain
        assert all(len(v) == 0 for v in df.values())

    def test_diamond(self, diamond):
        df = fnx.dominance_frontiers(diamond, "a")
        assert "d" in df["b"]
        assert "d" in df["c"]
        assert len(df["a"]) == 0

    def test_raises_on_undirected(self):
        g = fnx.Graph()
        g.add_edge("a", "b")
        with pytest.raises(fnx.NetworkXNotImplemented):
            fnx.dominance_frontiers(g, "a")
