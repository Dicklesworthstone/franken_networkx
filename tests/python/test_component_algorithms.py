"""Tests for component algorithm bindings.

Tests cover:
- node_connected_component
- is_biconnected
- biconnected_components
- biconnected_component_edges
- is_semiconnected
- kosaraju_strongly_connected_components
- attracting_components
- number_attracting_components
- is_attracting_component
"""

import pytest
import franken_networkx as fnx


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def triangle():
    """Triangle graph: a-b-c-a."""
    g = fnx.Graph()
    g.add_edge("a", "b")
    g.add_edge("b", "c")
    g.add_edge("c", "a")
    return g


@pytest.fixture
def path4():
    """Path graph: a-b-c-d."""
    g = fnx.Graph()
    g.add_edge("a", "b")
    g.add_edge("b", "c")
    g.add_edge("c", "d")
    return g


@pytest.fixture
def disconnected():
    """Two disconnected components."""
    g = fnx.Graph()
    g.add_edge("a", "b")
    g.add_node("c")
    return g


@pytest.fixture
def directed_cycle():
    """Directed cycle: a->b->c->a."""
    g = fnx.DiGraph()
    g.add_edge("a", "b")
    g.add_edge("b", "c")
    g.add_edge("c", "a")
    return g


@pytest.fixture
def directed_chain():
    """Directed chain: a->b->c."""
    g = fnx.DiGraph()
    g.add_edge("a", "b")
    g.add_edge("b", "c")
    return g


# ---------------------------------------------------------------------------
# node_connected_component
# ---------------------------------------------------------------------------

class TestNodeConnectedComponent:
    def test_triangle(self, triangle):
        comp = fnx.node_connected_component(triangle, "a")
        assert sorted(comp) == ["a", "b", "c"]

    def test_disconnected(self, disconnected):
        comp_a = fnx.node_connected_component(disconnected, "a")
        assert sorted(comp_a) == ["a", "b"]
        comp_c = fnx.node_connected_component(disconnected, "c")
        assert comp_c == ["c"]

    def test_single_node(self):
        g = fnx.Graph()
        g.add_node("x")
        assert fnx.node_connected_component(g, "x") == ["x"]


# ---------------------------------------------------------------------------
# is_biconnected
# ---------------------------------------------------------------------------

class TestIsBiconnected:
    def test_triangle(self, triangle):
        assert fnx.is_biconnected(triangle) is True

    def test_path(self, path4):
        # Path has articulation points
        assert fnx.is_biconnected(path4) is False

    def test_single_node(self):
        g = fnx.Graph()
        g.add_node("a")
        assert fnx.is_biconnected(g) is False

    def test_disconnected(self, disconnected):
        assert fnx.is_biconnected(disconnected) is False


# ---------------------------------------------------------------------------
# biconnected_components
# ---------------------------------------------------------------------------

class TestBiconnectedComponents:
    def test_triangle(self, triangle):
        comps = [sorted(c) for c in fnx.biconnected_components(triangle)]
        assert len(comps) == 1
        assert comps[0] == ["a", "b", "c"]

    def test_bridge_graph(self):
        """Two triangles connected by a bridge."""
        g = fnx.Graph()
        g.add_edge("a", "b")
        g.add_edge("b", "c")
        g.add_edge("c", "a")
        g.add_edge("c", "d")
        g.add_edge("d", "e")
        g.add_edge("e", "f")
        g.add_edge("f", "d")
        comps = list(fnx.biconnected_components(g))
        assert len(comps) == 3  # two triangles + bridge

    def test_empty(self):
        g = fnx.Graph()
        assert list(fnx.biconnected_components(g)) == []


# ---------------------------------------------------------------------------
# biconnected_component_edges
# ---------------------------------------------------------------------------

class TestBiconnectedComponentEdges:
    def test_triangle(self, triangle):
        comps = fnx.biconnected_component_edges(triangle)
        assert len(comps) == 1
        assert len(comps[0]) == 3  # 3 edges in triangle

    def test_path(self):
        """a-b-c: two bridge components, each with 1 edge."""
        g = fnx.Graph()
        g.add_edge("a", "b")
        g.add_edge("b", "c")
        comps = fnx.biconnected_component_edges(g)
        assert len(comps) == 2
        for comp in comps:
            assert len(comp) == 1


# ---------------------------------------------------------------------------
# is_semiconnected
# ---------------------------------------------------------------------------

class TestIsSemiconnected:
    def test_chain(self, directed_chain):
        assert fnx.is_semiconnected(directed_chain) is True

    def test_cycle(self, directed_cycle):
        assert fnx.is_semiconnected(directed_cycle) is True

    def test_fork(self):
        """a->b, a->c: NOT semiconnected."""
        g = fnx.DiGraph()
        g.add_edge("a", "b")
        g.add_edge("a", "c")
        assert fnx.is_semiconnected(g) is False

    def test_raises_on_undirected(self, triangle):
        with pytest.raises(fnx.NetworkXNotImplemented):
            fnx.is_semiconnected(triangle)


# ---------------------------------------------------------------------------
# kosaraju_strongly_connected_components
# ---------------------------------------------------------------------------

class TestKosarajuSCC:
    def test_cycle(self, directed_cycle):
        sccs = fnx.kosaraju_strongly_connected_components(directed_cycle)
        assert len(sccs) == 1
        assert sorted(sccs[0]) == ["a", "b", "c"]

    def test_chain(self, directed_chain):
        sccs = fnx.kosaraju_strongly_connected_components(directed_chain)
        assert len(sccs) == 3  # all singletons

    def test_matches_tarjan(self, directed_cycle):
        """Kosaraju and Tarjan should give the same result."""
        tarjan = list(fnx.strongly_connected_components(directed_cycle))
        kosaraju = fnx.kosaraju_strongly_connected_components(directed_cycle)
        tarjan_sorted = sorted([sorted(c) for c in tarjan])
        kosaraju_sorted = sorted([sorted(c) for c in kosaraju])
        assert tarjan_sorted == kosaraju_sorted

    def test_raises_on_undirected(self, triangle):
        with pytest.raises(fnx.NetworkXNotImplemented):
            fnx.kosaraju_strongly_connected_components(triangle)


# ---------------------------------------------------------------------------
# attracting_components
# ---------------------------------------------------------------------------

class TestAttractingComponents:
    def test_cycle(self, directed_cycle):
        # attracting_components returns a generator — materialise to
        # a list of sets to allow indexing / length checks.
        att = [set(c) for c in fnx.attracting_components(directed_cycle)]
        assert len(att) == 1
        assert att[0] == {"a", "b", "c"}

    def test_chain(self, directed_chain):
        att = [set(c) for c in fnx.attracting_components(directed_chain)]
        assert len(att) == 1
        assert att[0] == {"c"}  # only sink node

    def test_two_sinks(self):
        g = fnx.DiGraph()
        g.add_edge("a", "b")
        g.add_edge("a", "c")
        att = [set(c) for c in fnx.attracting_components(g)]
        assert len(att) == 2

    def test_raises_on_undirected(self, triangle):
        # NetworkXNotImplemented fires on first next() of the generator.
        with pytest.raises(fnx.NetworkXNotImplemented):
            list(fnx.attracting_components(triangle))


# ---------------------------------------------------------------------------
# number_attracting_components
# ---------------------------------------------------------------------------

class TestNumberAttractingComponents:
    def test_cycle(self, directed_cycle):
        assert fnx.number_attracting_components(directed_cycle) == 1

    def test_two_sinks(self):
        g = fnx.DiGraph()
        g.add_edge("a", "b")
        g.add_edge("a", "c")
        assert fnx.number_attracting_components(g) == 2


# ---------------------------------------------------------------------------
# is_attracting_component
# ---------------------------------------------------------------------------

class TestIsAttractingComponent:
    """Upstream nx.is_attracting_component(G) takes *only* the graph and
    returns True iff G consists of a single attracting component that
    spans all nodes (one sink SCC in the condensation, with no other
    SCCs). fnx matches this contract — these tests cross-check it.
    """

    def test_yes(self):
        # Directed cycle a->b->c->a: whole graph is one attracting SCC.
        g = fnx.DiGraph()
        g.add_edge("a", "b")
        g.add_edge("b", "c")
        g.add_edge("c", "a")
        assert fnx.is_attracting_component(g) is True

    def test_no_outgoing(self):
        # {a,b} strongly connected, {a,c} is not — condensation has
        # two sinks ({b,a}? wait a<->b, a->c so sink is {c}), so the
        # attracting component is {c} not the whole graph → False.
        g = fnx.DiGraph()
        g.add_edge("a", "b")
        g.add_edge("b", "a")
        g.add_edge("a", "c")
        assert fnx.is_attracting_component(g) is False

    def test_not_strongly_connected(self):
        # a->b has attracting component {b}, not the full graph.
        g = fnx.DiGraph()
        g.add_edge("a", "b")
        assert fnx.is_attracting_component(g) is False

    def test_raises_on_undirected(self, triangle):
        with pytest.raises(fnx.NetworkXNotImplemented):
            fnx.is_attracting_component(triangle)


# ---------------------------------------------------------------------------
# Cross-algorithm consistency
# ---------------------------------------------------------------------------

class TestCrossAlgorithmConsistency:
    def test_attracting_subset_of_scc(self, directed_cycle):
        """Every attracting component should be an SCC."""
        sccs = fnx.strongly_connected_components(directed_cycle)
        atts = fnx.attracting_components(directed_cycle)
        scc_sets = [frozenset(c) for c in sccs]
        for att in atts:
            assert frozenset(att) in scc_sets

    def test_kosaraju_vs_tarjan_complex(self):
        """Complex graph: Kosaraju and Tarjan produce same SCCs."""
        g = fnx.DiGraph()
        g.add_edge("a", "b")
        g.add_edge("b", "c")
        g.add_edge("c", "a")
        g.add_edge("c", "d")
        g.add_edge("d", "e")
        g.add_edge("e", "d")
        tarjan = fnx.strongly_connected_components(g)
        kosaraju = fnx.kosaraju_strongly_connected_components(g)
        assert sorted([sorted(c) for c in tarjan]) == sorted([sorted(c) for c in kosaraju])
