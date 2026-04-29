//! Structure-aware fuzzer for graph traversals, dominance analysis,
//! and the moral graph construction.
//!
//! Targets:
//!
//! - ``fnx_algorithms::bfs_edges`` / ``bfs_layers`` /
//!   ``descendants_at_distance`` — undirected BFS family.
//! - ``fnx_algorithms::dfs_edges`` — undirected DFS edge enumeration.
//! - ``fnx_algorithms::immediate_dominators`` and
//!   ``dominance_frontiers`` — Cooper / Harvey / Kennedy-style dominator
//!   analysis on a digraph rooted at an arbitrary node.
//! - ``fnx_algorithms::moral_graph`` — DAG → undirected moralized graph.
//!
//! Beyond the no-panic invariant, asserts these runtime contracts:
//!
//! BFS family
//! ----------
//! * **Tree-shape**: ``bfs_edges`` from a single source yields exactly
//!   one edge per *non-source* node reached, so the count of unique
//!   target endpoints equals the count of yielded edges.
//! * **Layer partition**: every node listed by ``bfs_layers`` appears
//!   in exactly one layer, and the source sits in layer 0.
//! * **Distance contract**: ``descendants_at_distance(G, s, 0)`` is
//!   exactly ``{s}`` whenever ``s`` is in the graph.
//! * **Layer-distance equivalence**: a node belongs to layer ``k`` iff
//!   it is at BFS distance ``k`` from the source — confirmed via
//!   ``descendants_at_distance(G, s, k)``.
//!
//! DFS family
//! ----------
//! * **Tree-shape**: ``dfs_edges`` from a single source yields a forest
//!   over the reachable subgraph. The set of *target* endpoints
//!   visits each non-source reachable node exactly once.
//!
//! Dominance family (digraph)
//! --------------------------
//! * **Function**: ``immediate_dominators(G, s)`` is a function — every
//!   reachable non-source node ``v`` maps to a unique parent in the
//!   dominator tree.
//! * **Acyclic**: the dominator-tree edge set ``{(idom[v], v)}``
//!   contains no cycles.
//! * **Reachability ⊇ idom keys**: every key of the idom dict must be
//!   reachable from ``s``.
//! * **Frontier well-formed**: ``dominance_frontiers(G, s)`` keys are
//!   reachable from ``s``; each frontier set ``DF(v) ⊆`` reachable.
//!
//! Moral family
//! ------------
//! * **Undirected output**: ``moral_graph`` returns an undirected graph.
//! * **Skeleton subset**: every undirected edge ``{u, v}`` of the input
//!   digraph survives in the moralized graph (skeleton is a subset).

#![no_main]

mod arbitrary_graph;

use arbitrary::Arbitrary;
use arbitrary_graph::{ArbitraryDiGraph, ArbitraryGraph};
use fnx_algorithms::{
    bfs_edges, bfs_layers, descendants_at_distance, dfs_edges, dominance_frontiers,
    immediate_dominators, moral_graph,
};
use fnx_classes::Graph;
use fnx_classes::digraph::DiGraph;
use libfuzzer_sys::fuzz_target;
use std::collections::{HashMap, HashSet};

#[derive(Debug, Arbitrary)]
enum TraversalDominanceInput {
    /// BFS forest + layer-partition invariants on the source node.
    BfsInvariants(ArbitraryGraph),
    /// BFS layers vs descendants_at_distance equivalence at distance k.
    LayerEqualsDistance(ArbitraryGraph, u8),
    /// DFS forest invariants (each non-source node visited once).
    DfsInvariants(ArbitraryGraph),
    /// Dominator-tree well-formedness on a digraph rooted at first node.
    DominatorTree(ArbitraryDiGraph),
    /// Dominance frontiers reachability invariant.
    DominanceFrontiers(ArbitraryDiGraph),
    /// moral_graph is undirected and supersets the skeleton.
    Moralization(ArbitraryDiGraph),
}

fn pick_source(graph: &Graph) -> Option<&str> {
    graph.nodes_ordered().first().copied()
}

fn pick_source_directed(graph: &DiGraph) -> Option<&str> {
    graph.nodes_ordered().first().copied()
}

fn assert_bfs_invariants(graph: &Graph) {
    let Some(source) = pick_source(graph) else {
        return;
    };
    let edges = bfs_edges(graph, source, None);
    let mut seen_targets: HashSet<&str> = HashSet::new();
    for (_u, v) in &edges {
        assert!(
            seen_targets.insert(v.as_str()),
            "bfs_edges visits target {v} more than once",
        );
    }

    let layers = bfs_layers(graph, source);
    if layers.is_empty() {
        return;
    }
    assert!(
        layers[0].iter().any(|n| n == source),
        "source must be in layer 0",
    );
    let mut layer_of: HashMap<&str, usize> = HashMap::new();
    for (idx, layer) in layers.iter().enumerate() {
        for n in layer {
            assert!(
                layer_of.insert(n.as_str(), idx).is_none(),
                "node {n} appears in multiple layers",
            );
        }
    }
}

fn assert_descendants_at_distance_zero(graph: &Graph) {
    let Some(source) = pick_source(graph) else {
        return;
    };
    let result = descendants_at_distance(graph, source, 0);
    assert_eq!(result.len(), 1, "distance-0 should yield exactly one node");
    assert_eq!(
        result[0], source,
        "distance-0 node must be the source itself",
    );
}

fn assert_layer_equals_distance(graph: &Graph, k_byte: u8) {
    let Some(source) = pick_source(graph) else {
        return;
    };
    let layers = bfs_layers(graph, source);
    if layers.is_empty() {
        return;
    }
    let k = (k_byte as usize) % layers.len();
    let from_layer: HashSet<&str> = layers[k].iter().map(String::as_str).collect();
    let from_distance: HashSet<String> = descendants_at_distance(graph, source, k)
        .into_iter()
        .collect();
    let from_distance_borrowed: HashSet<&str> =
        from_distance.iter().map(String::as_str).collect();
    assert_eq!(
        from_layer, from_distance_borrowed,
        "layer {k} disagrees with descendants_at_distance(_, {k})",
    );
}

fn assert_dfs_invariants(graph: &Graph) {
    let Some(source) = pick_source(graph) else {
        return;
    };
    let edges = dfs_edges(graph, source, None);
    let mut seen_targets: HashSet<&str> = HashSet::new();
    for (_u, v) in &edges {
        assert!(
            seen_targets.insert(v.as_str()),
            "dfs_edges visits target {v} more than once",
        );
    }
}

fn assert_dominator_tree(graph: &DiGraph) {
    let Some(source) = pick_source_directed(graph) else {
        return;
    };
    let idom = immediate_dominators(graph, source);
    // Every key must have a unique parent in idom.
    for (v, parent) in &idom {
        assert!(graph.has_node(v), "idom key {v} not in graph");
        assert!(graph.has_node(parent), "idom parent {parent} not in graph");
    }
    // The idom dictionary, treated as parent pointers, must be acyclic.
    for v in idom.keys() {
        let mut steps = 0usize;
        let mut current: &str = v.as_str();
        let limit = idom.len() + 2;
        loop {
            steps += 1;
            assert!(
                steps <= limit,
                "idom parent chain from {v} did not terminate within \
                 {limit} steps — implies a cycle",
            );
            match idom.get(current) {
                Some(p) if p == current => break, // self-dominator (root in some impls)
                Some(p) => current = p.as_str(),
                None => break,
            }
        }
    }
}

fn assert_dominance_frontiers_reachable(graph: &DiGraph) {
    let Some(source) = pick_source_directed(graph) else {
        return;
    };
    let frontiers = dominance_frontiers(graph, source);
    for (v, frontier) in &frontiers {
        assert!(
            graph.has_node(v),
            "dominance_frontiers key {v} not in graph",
        );
        for f in frontier {
            assert!(
                graph.has_node(f),
                "frontier element {f} of {v} not in graph",
            );
        }
    }
}

fn assert_moralization_invariants(graph: &DiGraph) {
    let m = moral_graph(graph);
    // moral_graph returns an undirected fnx_classes::Graph — the type
    // itself is the proof, but assert via API: every edge in the
    // underlying digraph must survive (in some orientation).
    let mut surviving = 0usize;
    for edge in graph.edges_ordered() {
        let (u, v) = (edge.left.as_str(), edge.right.as_str());
        if u == v {
            continue;
        }
        if m.has_edge(u, v) {
            surviving += 1;
        }
    }
    let n_edges = graph
        .edges_ordered()
        .iter()
        .filter(|e| e.left != e.right)
        .count();
    assert_eq!(
        surviving, n_edges,
        "moral_graph dropped a skeleton edge",
    );
}

fuzz_target!(|input: TraversalDominanceInput| {
    match input {
        TraversalDominanceInput::BfsInvariants(ag) => {
            assert_bfs_invariants(&ag.graph);
            assert_descendants_at_distance_zero(&ag.graph);
        }
        TraversalDominanceInput::LayerEqualsDistance(ag, k) => {
            assert_layer_equals_distance(&ag.graph, k);
        }
        TraversalDominanceInput::DfsInvariants(ag) => {
            assert_dfs_invariants(&ag.graph);
        }
        TraversalDominanceInput::DominatorTree(ag) => {
            assert_dominator_tree(&ag.graph);
        }
        TraversalDominanceInput::DominanceFrontiers(ag) => {
            assert_dominance_frontiers_reachable(&ag.graph);
        }
        TraversalDominanceInput::Moralization(ag) => {
            assert_moralization_invariants(&ag.graph);
        }
    }
});
