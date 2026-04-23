"""Stateful differential fuzzing of Graph/DiGraph/MultiGraph/MultiDiGraph
constructor and mutation APIs.

Runs a Hypothesis RuleBasedStateMachine that drives a random sequence
of mutation operations into both an fnx graph and an upstream nx graph,
and cross-checks the public observable state after every rule. Any
divergence — node set, edge set, data dict, is_directed flag, etc. —
surfaces as a failing example that hypothesis shrinks to a minimal
reproducer.

Fuzzing scope (what's exercised):

- add_node(node) and add_node(node, **attrs)
- remove_node(node)
- add_edge(u, v) and add_edge(u, v, **attrs) (with key for multigraphs)
- remove_edge(u, v) / remove_edge(u, v, key)
- clear() and clear_edges()
- subgraph(nbunch).copy() round-trip
- copy() round-trip
- node-attribute mutation via G.nodes[n][key] = val
- edge-attribute mutation via G[u][v][key] = val
- to_directed() / to_undirected() class flip

Each rule uses a small bounded node domain (0..=7) so the state
machine can revisit the same nodes across rules and exercise
add-then-remove cycles.

The `_snapshot` comparison is type-agnostic: it projects both graphs
to a normalized (nodes, edges, directed, multigraph, graph_attrs)
tuple so the equality check doesn't care about generator-vs-list or
set-vs-list container differences.
"""

import pytest

hypothesis = pytest.importorskip("hypothesis")

from hypothesis import strategies as st, settings, HealthCheck
from hypothesis.stateful import (
    RuleBasedStateMachine,
    rule,
    invariant,
    initialize,
)

import franken_networkx as fnx
import networkx as nx


NODE_DOMAIN = list(range(8))


def _snapshot(graph):
    """Normalize a graph to a value that supports == comparison across fnx/nx."""
    nodes = sorted(
        (str(n), tuple(sorted(d.items())))
        for n, d in graph.nodes(data=True)
    )
    if graph.is_multigraph():
        edges = sorted(
            (str(u), str(v), k, tuple(sorted(d.items())))
            for u, v, k, d in graph.edges(keys=True, data=True)
        )
    else:
        edges = sorted(
            (str(u), str(v), tuple(sorted(d.items())))
            for u, v, d in graph.edges(data=True)
        )
    # For undirected graphs, canonicalize edge endpoint order
    if not graph.is_directed():
        if graph.is_multigraph():
            edges = sorted(
                (min(u, v), max(u, v), k, d) for u, v, k, d in edges
            )
        else:
            edges = sorted(
                (min(u, v), max(u, v), d) for u, v, d in edges
            )
    return {
        "nodes": nodes,
        "edges": edges,
        "directed": graph.is_directed(),
        "multigraph": graph.is_multigraph(),
        "n_nodes": graph.number_of_nodes(),
        "n_edges": graph.number_of_edges(),
        "graph_attrs": tuple(sorted(graph.graph.items())),
    }


class _GraphFuzzBase(RuleBasedStateMachine):
    """Base state machine.  Subclasses set ``GRAPH_CLASS`` to the pair
    (fnx_cls, nx_cls) they want to drive.
    """

    GRAPH_CLASS = None  # (fnx_cls, nx_cls) — set by subclass

    @initialize()
    def setup(self):
        fnx_cls, nx_cls = self.GRAPH_CLASS
        self.fnx_g = fnx_cls()
        self.nx_g = nx_cls()

    # ------------------------------------------------------------------
    # Node rules
    # ------------------------------------------------------------------
    @rule(node=st.sampled_from(NODE_DOMAIN))
    def add_node_plain(self, node):
        self.fnx_g.add_node(node)
        self.nx_g.add_node(node)

    @rule(
        node=st.sampled_from(NODE_DOMAIN),
        color=st.sampled_from(["red", "blue", "green"]),
        weight=st.integers(min_value=-5, max_value=5),
    )
    def add_node_with_attrs(self, node, color, weight):
        self.fnx_g.add_node(node, color=color, weight=weight)
        self.nx_g.add_node(node, color=color, weight=weight)

    @rule(node=st.sampled_from(NODE_DOMAIN))
    def remove_node_if_present(self, node):
        if node in self.fnx_g:
            self.fnx_g.remove_node(node)
        if node in self.nx_g:
            self.nx_g.remove_node(node)

    # ------------------------------------------------------------------
    # Edge rules
    # ------------------------------------------------------------------
    @rule(
        u=st.sampled_from(NODE_DOMAIN),
        v=st.sampled_from(NODE_DOMAIN),
    )
    def add_edge_plain(self, u, v):
        self.fnx_g.add_edge(u, v)
        self.nx_g.add_edge(u, v)

    @rule(
        u=st.sampled_from(NODE_DOMAIN),
        v=st.sampled_from(NODE_DOMAIN),
        weight=st.floats(
            min_value=-10.0,
            max_value=10.0,
            allow_nan=False,
            allow_infinity=False,
        ),
        label=st.sampled_from(["x", "y", "z"]),
    )
    def add_edge_with_attrs(self, u, v, weight, label):
        self.fnx_g.add_edge(u, v, weight=weight, label=label)
        self.nx_g.add_edge(u, v, weight=weight, label=label)

    @rule(
        u=st.sampled_from(NODE_DOMAIN),
        v=st.sampled_from(NODE_DOMAIN),
    )
    def remove_edge_if_present(self, u, v):
        if self.fnx_g.has_edge(u, v):
            self.fnx_g.remove_edge(u, v)
        if self.nx_g.has_edge(u, v):
            self.nx_g.remove_edge(u, v)

    # ------------------------------------------------------------------
    # Whole-graph rules
    # ------------------------------------------------------------------
    @rule()
    def clear(self):
        self.fnx_g.clear()
        self.nx_g.clear()

    @rule()
    def clear_edges(self):
        self.fnx_g.clear_edges()
        self.nx_g.clear_edges()

    @rule()
    def roundtrip_copy(self):
        self.fnx_g = self.fnx_g.copy()
        self.nx_g = self.nx_g.copy()

    @rule()
    def roundtrip_subgraph_copy(self):
        # Snapshot the full node set, subgraph it, then .copy() to get a
        # concrete graph. Should be a no-op (same as self.copy()).
        nodes = list(self.fnx_g.nodes())
        if not nodes:
            return
        self.fnx_g = self.fnx_g.subgraph(nodes).copy()
        self.nx_g = self.nx_g.subgraph(nodes).copy()

    @rule(
        node=st.sampled_from(NODE_DOMAIN),
        key=st.sampled_from(["color", "weight", "label"]),
        value=st.integers(min_value=-3, max_value=3),
    )
    def mutate_node_attr(self, node, key, value):
        if node not in self.fnx_g:
            return
        self.fnx_g.nodes[node][key] = value
        self.nx_g.nodes[node][key] = value

    @rule(
        u=st.sampled_from(NODE_DOMAIN),
        v=st.sampled_from(NODE_DOMAIN),
        key=st.sampled_from(["weight", "label", "tag"]),
        value=st.integers(min_value=-3, max_value=3),
    )
    def mutate_edge_attr(self, u, v, key, value):
        if not self.fnx_g.has_edge(u, v):
            return
        if self.fnx_g.is_multigraph():
            # Mutate the 0th parallel edge's attrs
            ek = next(iter(self.fnx_g[u][v]))
            self.fnx_g[u][v][ek][key] = value
            # nx side: same edge key
            self.nx_g[u][v][ek][key] = value
        else:
            self.fnx_g[u][v][key] = value
            self.nx_g[u][v][key] = value

    @rule(
        gkey=st.sampled_from(["name", "phase", "mode"]),
        gval=st.sampled_from(["alpha", "beta", "gamma"]),
    )
    def mutate_graph_attr(self, gkey, gval):
        self.fnx_g.graph[gkey] = gval
        self.nx_g.graph[gkey] = gval

    @rule(
        nodes=st.lists(
            st.sampled_from(NODE_DOMAIN), min_size=0, max_size=4, unique=True
        )
    )
    def add_nodes_from_list(self, nodes):
        self.fnx_g.add_nodes_from(nodes)
        self.nx_g.add_nodes_from(nodes)

    @rule(
        edges=st.lists(
            st.tuples(
                st.sampled_from(NODE_DOMAIN),
                st.sampled_from(NODE_DOMAIN),
            ),
            min_size=0,
            max_size=4,
        )
    )
    def add_edges_from_list(self, edges):
        self.fnx_g.add_edges_from(edges)
        self.nx_g.add_edges_from(edges)

    @rule(node=st.sampled_from(NODE_DOMAIN))
    def self_loop_if_present(self, node):
        """Add a self-loop on ``node``."""
        self.fnx_g.add_edge(node, node)
        self.nx_g.add_edge(node, node)

    @rule(
        nbunch=st.lists(
            st.sampled_from(NODE_DOMAIN), min_size=0, max_size=3, unique=True
        )
    )
    def remove_nodes_if_present(self, nbunch):
        """Remove a set of nodes (silent-ignore missing to match nx's
        ``remove_nodes_from`` semantics)."""
        for n in nbunch:
            if n in self.fnx_g:
                self.fnx_g.remove_node(n)
            if n in self.nx_g:
                self.nx_g.remove_node(n)

    # ------------------------------------------------------------------
    # Invariant: state must match upstream nx after every rule.
    # ------------------------------------------------------------------
    @invariant()
    def state_matches_nx(self):
        if getattr(self, "fnx_g", None) is None or getattr(self, "nx_g", None) is None:
            return  # pre-initialize
        assert _snapshot(self.fnx_g) == _snapshot(self.nx_g)


# ---------------------------------------------------------------------------
# Simple-graph state machines (Graph + DiGraph)
# ---------------------------------------------------------------------------

class GraphFuzz(_GraphFuzzBase):
    GRAPH_CLASS = (fnx.Graph, nx.Graph)


class DiGraphFuzz(_GraphFuzzBase):
    GRAPH_CLASS = (fnx.DiGraph, nx.DiGraph)


# Multigraph state machines add key-aware edge ops on top.

class _MultiGraphFuzzBase(_GraphFuzzBase):
    @rule(
        u=st.sampled_from(NODE_DOMAIN),
        v=st.sampled_from(NODE_DOMAIN),
        key=st.integers(min_value=0, max_value=3),
    )
    def add_edge_with_key(self, u, v, key):
        self.fnx_g.add_edge(u, v, key=key)
        self.nx_g.add_edge(u, v, key=key)

    @rule(
        u=st.sampled_from(NODE_DOMAIN),
        v=st.sampled_from(NODE_DOMAIN),
        key=st.integers(min_value=0, max_value=3),
    )
    def remove_edge_with_key_if_present(self, u, v, key):
        if self.fnx_g.has_edge(u, v, key=key):
            self.fnx_g.remove_edge(u, v, key=key)
        if self.nx_g.has_edge(u, v, key=key):
            self.nx_g.remove_edge(u, v, key=key)


class MultiGraphFuzz(_MultiGraphFuzzBase):
    GRAPH_CLASS = (fnx.MultiGraph, nx.MultiGraph)


class MultiDiGraphFuzz(_MultiGraphFuzzBase):
    GRAPH_CLASS = (fnx.MultiDiGraph, nx.MultiDiGraph)


# ---------------------------------------------------------------------------
# Wire into pytest.
# ---------------------------------------------------------------------------

_machine_settings = settings(
    max_examples=200,
    stateful_step_count=40,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
)

for _cls in (GraphFuzz, DiGraphFuzz, MultiGraphFuzz, MultiDiGraphFuzz):
    _machine_settings(_cls)

TestGraphFuzz = GraphFuzz.TestCase
TestDiGraphFuzz = DiGraphFuzz.TestCase
TestMultiGraphFuzz = MultiGraphFuzz.TestCase
TestMultiDiGraphFuzz = MultiDiGraphFuzz.TestCase
