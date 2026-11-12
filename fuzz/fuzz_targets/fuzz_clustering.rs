//! Structure-aware fuzzer for clustering algorithms.
//!
//! Tests clustering coefficient, triangles, transitivity, and
//! related metrics on valid-but-pathological graph structures.

#![no_main]

mod arbitrary_graph;

use arbitrary::Arbitrary;
use arbitrary_graph::{ArbitraryDiGraph, ArbitraryGraph};
use fnx_classes::Graph;
use libfuzzer_sys::fuzz_target;
use std::collections::HashSet;

/// Check that a slice of node-keyed items covers exactly the graph's
/// node set (no duplicates, no extras, no missing nodes). The closure
/// extracts the node name from each item.
fn assert_node_set_covers_graph<T>(items: &[T], graph: &Graph, key: impl Fn(&T) -> &str, label: &str) {
    let expected: HashSet<&str> =
        graph.nodes_ordered().into_iter().collect();
    let mut seen: HashSet<&str> = HashSet::new();
    for item in items {
        let k = key(item);
        assert!(
            graph.has_node(k),
            "{}: node {} not in graph",
            label,
            k
        );
        assert!(
            seen.insert(k),
            "{}: duplicate node {} in result",
            label,
            k
        );
    }
    assert_eq!(
        seen, expected,
        "{}: result keys diverged from graph node set",
        label
    );
}

#[derive(Debug, Arbitrary)]
enum ClusteringInput {
    /// Clustering coefficient on undirected graph.
    ClusteringUndirected(ArbitraryGraph),
    /// Clustering coefficient on directed graph.
    ClusteringDirected(ArbitraryDiGraph),
    /// Triangles count.
    Triangles(ArbitraryGraph),
    /// Square clustering.
    SquareClustering(ArbitraryGraph),
    /// Core number (k-core decomposition).
    CoreNumber(ArbitraryGraph),
    /// K-core subgraph.
    KCore(ArbitraryGraph),
    /// K-truss subgraph.
    KTruss(ArbitraryGraph),
    /// Onion layers decomposition.
    OnionLayers(ArbitraryGraph),
    /// Is bipartite check.
    IsBipartite(ArbitraryGraph),
    /// Bipartite sets.
    BipartiteSets(ArbitraryGraph),
    /// Greedy graph coloring.
    GreedyColor(ArbitraryGraph),
}

/// A clustering input with an embedded k parameter for k-core/k-truss.
#[derive(Debug, Arbitrary)]
struct ClusteringInputWithK {
    input: ClusteringInput,
    k_value: u8,
}

fuzz_target!(|input_with_k: ClusteringInputWithK| {
    let k = (input_with_k.k_value % 10) as usize;

    match input_with_k.input {
        ClusteringInput::ClusteringUndirected(ag) => {
            if ag.graph.node_count() == 0 {
                return;
            }
            let result = fnx_algorithms::clustering_coefficient(&ag.graph);
            assert_node_set_covers_graph(
                &result.scores,
                &ag.graph,
                |s| s.node.as_str(),
                "clustering_coefficient",
            );
            // Each per-node clustering coefficient is in [0, 1].
            for s in &result.scores {
                assert!(
                    s.score >= -1.0e-9 && s.score <= 1.0 + 1.0e-9,
                    "clustering coefficient out of [0,1]: node={} score={}",
                    s.node, s.score
                );
            }
            // Aggregates within [0, 1] when defined.
            assert!(
                (result.average_clustering >= -1.0e-9 && result.average_clustering <= 1.0 + 1.0e-9)
                    || !result.average_clustering.is_finite(),
                "average_clustering out of [0,1]: {}",
                result.average_clustering
            );
            assert!(
                (result.transitivity >= -1.0e-9 && result.transitivity <= 1.0 + 1.0e-9)
                    || !result.transitivity.is_finite(),
                "transitivity out of [0,1]: {}",
                result.transitivity
            );
        }
        ClusteringInput::ClusteringDirected(ag) => {
            let _ = fnx_algorithms::clustering_coefficient_directed(&ag.graph);
        }
        ClusteringInput::Triangles(ag) => {
            if ag.graph.node_count() == 0 {
                return;
            }
            let result = fnx_algorithms::triangles(&ag.graph);
            assert_node_set_covers_graph(
                &result.triangles,
                &ag.graph,
                |t| t.node.as_str(),
                "triangles",
            );
            // The sum of per-node triangle counts is always 3 * (number
            // of triangles in G), so the sum is divisible by 3.
            let sum: usize = result.triangles.iter().map(|t| t.count).sum();
            assert_eq!(
                sum % 3, 0,
                "sum of per-node triangle counts ({}) not divisible by 3",
                sum
            );
        }
        ClusteringInput::SquareClustering(ag) => {
            if ag.graph.node_count() == 0 {
                return;
            }
            let result = fnx_algorithms::square_clustering(&ag.graph);
            assert_node_set_covers_graph(
                &result.scores,
                &ag.graph,
                |s| s.node.as_str(),
                "square_clustering",
            );
            for s in &result.scores {
                assert!(
                    s.score >= -1.0e-9 && s.score <= 1.0 + 1.0e-9,
                    "square clustering out of [0,1]: node={} score={}",
                    s.node, s.score
                );
            }
        }
        ClusteringInput::CoreNumber(ag) => {
            if ag.graph.node_count() == 0 {
                return;
            }
            let result = fnx_algorithms::core_number(&ag.graph);
            assert_node_set_covers_graph(
                &result.core_numbers,
                &ag.graph,
                |c| c.node.as_str(),
                "core_number",
            );
            // Core number is always ≤ degree in the graph; we don't have
            // direct degree access but it's also ≤ node_count - 1.
            let upper = ag.graph.node_count().saturating_sub(1);
            for c in &result.core_numbers {
                assert!(
                    c.core <= upper,
                    "core number {} for node {} exceeds n-1 = {}",
                    c.core, c.node, upper
                );
            }
        }
        ClusteringInput::KCore(ag) => {
            let _ = fnx_algorithms::k_core(&ag.graph, Some(k));
        }
        ClusteringInput::KTruss(ag) => {
            // k-truss requires k >= 2
            let k_truss = k.max(2);
            let _ = fnx_algorithms::k_truss(&ag.graph, k_truss);
        }
        ClusteringInput::OnionLayers(ag) => {
            let _ = fnx_algorithms::onion_layers(&ag.graph);
        }
        ClusteringInput::IsBipartite(ag) => {
            let _ = fnx_algorithms::is_bipartite(&ag.graph);
        }
        ClusteringInput::BipartiteSets(ag) => {
            if ag.graph.node_count() == 0 {
                return;
            }
            let result = fnx_algorithms::bipartite_sets(&ag.graph);
            if result.is_bipartite {
                // set_a and set_b are disjoint and cover the (component
                // containing the BFS root); both must be subsets of G's
                // node set.
                let mut seen: HashSet<&str> = HashSet::new();
                for n in &result.set_a {
                    assert!(ag.graph.has_node(n), "bipartite set_a contains foreign node {}", n);
                    assert!(seen.insert(n.as_str()), "node {} appears twice in bipartite sets", n);
                }
                for n in &result.set_b {
                    assert!(ag.graph.has_node(n), "bipartite set_b contains foreign node {}", n);
                    assert!(seen.insert(n.as_str()), "node {} appears in both bipartite sets", n);
                }
            }
        }
        ClusteringInput::GreedyColor(ag) => {
            if ag.graph.node_count() == 0 {
                return;
            }
            let result = fnx_algorithms::greedy_color(&ag.graph);
            assert_node_set_covers_graph(
                &result.coloring,
                &ag.graph,
                |c| c.node.as_str(),
                "greedy_color",
            );
            // num_colors must equal the number of distinct colors used.
            let distinct: HashSet<usize> =
                result.coloring.iter().map(|c| c.color).collect();
            assert_eq!(
                distinct.len(),
                result.num_colors,
                "greedy_color num_colors ({}) disagrees with distinct colors used ({})",
                result.num_colors,
                distinct.len()
            );
            // Every assigned color must be in [0, num_colors).
            for c in &result.coloring {
                assert!(
                    c.color < result.num_colors,
                    "node {} assigned color {} >= num_colors {}",
                    c.node, c.color, result.num_colors
                );
            }
            // Adjacent nodes must receive distinct colors (the actual
            // greedy-coloring contract).
            let color_of: std::collections::HashMap<&str, usize> = result
                .coloring
                .iter()
                .map(|c| (c.node.as_str(), c.color))
                .collect();
            for edge in ag.graph.edges_ordered() {
                if edge.left == edge.right {
                    continue; // self-loops are normally rejected, but skip if present
                }
                let cu = color_of[edge.left.as_str()];
                let cv = color_of[edge.right.as_str()];
                assert_ne!(
                    cu, cv,
                    "greedy_color assigned the same color {} to adjacent nodes {} and {}",
                    cu, edge.left, edge.right
                );
            }
        }
    }
});
