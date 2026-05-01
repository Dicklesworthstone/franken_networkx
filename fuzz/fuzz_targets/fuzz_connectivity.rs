//! Structure-aware fuzzer for connectivity algorithms.
//!
//! Tests connected components, articulation points, bridges, and
//! node/edge connectivity on valid-but-pathological graph structures.

#![no_main]

mod arbitrary_graph;

use arbitrary::Arbitrary;
use arbitrary_graph::{ArbitraryDiGraph, ArbitraryGraph, ArbitraryWeightedGraph};
use fnx_classes::Graph;
use libfuzzer_sys::fuzz_target;
use std::collections::HashSet;

/// Verify the connected_components partition: components are non-empty,
/// pairwise disjoint, and their union equals the graph's node set.
fn assert_components_partition(components: &[Vec<String>], graph: &Graph) {
    let expected: HashSet<&str> =
        graph.nodes_ordered().into_iter().collect();
    let mut seen: HashSet<&str> = HashSet::new();
    for comp in components {
        assert!(!comp.is_empty(), "connected component must be non-empty");
        for node in comp {
            assert!(
                graph.has_node(node),
                "component contains node {} not present in graph",
                node
            );
            let inserted = seen.insert(node.as_str());
            assert!(
                inserted,
                "node {} appears in multiple connected components",
                node
            );
        }
    }
    assert_eq!(
        seen, expected,
        "components partition does not cover the graph's node set"
    );
}

#[derive(Debug, Arbitrary)]
enum ConnectivityInput {
    /// Connected components on undirected graph.
    ConnectedComponents(ArbitraryGraph),
    /// Number of connected components.
    NumberConnectedComponents(ArbitraryGraph),
    /// Is connected check.
    IsConnected(ArbitraryGraph),
    /// Articulation points (cut vertices).
    ArticulationPoints(ArbitraryGraph),
    /// Bridges (cut edges).
    Bridges(ArbitraryGraph),
    /// Has path between two nodes.
    HasPath(ArbitraryGraph),
    /// Has path in directed graph.
    HasPathDirected(ArbitraryDiGraph),
    /// Node connectivity between two nodes.
    NodeConnectivity(ArbitraryGraph),
    /// Edge connectivity with capacity.
    EdgeConnectivity(ArbitraryWeightedGraph),
    /// Global node connectivity.
    GlobalNodeConnectivity(ArbitraryGraph),
    /// Global edge connectivity with capacity.
    GlobalEdgeConnectivity(ArbitraryWeightedGraph),
}

fuzz_target!(|input: ConnectivityInput| {
    match input {
        ConnectivityInput::ConnectedComponents(ag) => {
            let result = fnx_algorithms::connected_components(&ag.graph);
            assert_components_partition(&result.components, &ag.graph);
            // Cross-check: number_connected_components must agree.
            let count = fnx_algorithms::number_connected_components(&ag.graph).count;
            assert_eq!(
                count,
                result.components.len(),
                "number_connected_components ({}) disagrees with connected_components.len() ({})",
                count,
                result.components.len()
            );
        }
        ConnectivityInput::NumberConnectedComponents(ag) => {
            let result = fnx_algorithms::number_connected_components(&ag.graph);
            // count must be in [0, n].
            assert!(
                result.count <= ag.graph.node_count(),
                "ncc {} exceeds node count {}",
                result.count,
                ag.graph.node_count()
            );
            // Empty graph → 0 components; non-empty → at least 1.
            if ag.graph.node_count() == 0 {
                assert_eq!(result.count, 0);
            } else {
                assert!(result.count >= 1);
            }
        }
        ConnectivityInput::IsConnected(ag) => {
            // is_connected on the empty graph raises in the Python wrapper
            // but the Rust binding may return either way; just ensure no
            // panic and the result is consistent with number_connected_components.
            if ag.graph.node_count() == 0 {
                return;
            }
            let connected = fnx_algorithms::is_connected(&ag.graph).is_connected;
            let count = fnx_algorithms::number_connected_components(&ag.graph).count;
            assert_eq!(
                connected,
                count == 1,
                "is_connected ({}) disagrees with ncc==1 ({})",
                connected,
                count == 1
            );
        }
        ConnectivityInput::ArticulationPoints(ag) => {
            let result = fnx_algorithms::articulation_points(&ag.graph);
            // No duplicates, every node in the graph.
            let mut seen: HashSet<&str> = HashSet::new();
            for node in &result.nodes {
                assert!(
                    ag.graph.has_node(node),
                    "articulation point {} not in graph",
                    node
                );
                assert!(
                    seen.insert(node.as_str()),
                    "articulation point {} appears twice in result",
                    node
                );
            }
        }
        ConnectivityInput::Bridges(ag) => {
            let result = fnx_algorithms::bridges(&ag.graph);
            for (u, v) in &result.edges {
                assert!(
                    ag.graph.has_edge(u, v),
                    "bridge ({},{}) not in graph",
                    u, v
                );
            }
        }
        ConnectivityInput::HasPath(ag) => {
            if ag.nodes.len() >= 2 {
                let src = &ag.nodes[0];
                let dst = &ag.nodes[ag.nodes.len() - 1];
                let _ = fnx_algorithms::has_path(&ag.graph, src, dst);
            }
        }
        ConnectivityInput::HasPathDirected(ag) => {
            if ag.nodes.len() >= 2 {
                let src = &ag.nodes[0];
                let dst = &ag.nodes[ag.nodes.len() - 1];
                let _ = fnx_algorithms::has_path_directed(&ag.graph, src, dst);
            }
        }
        ConnectivityInput::NodeConnectivity(ag) => {
            if ag.nodes.len() >= 2 {
                let src = &ag.nodes[0];
                let dst = &ag.nodes[ag.nodes.len() - 1];
                let _ = fnx_algorithms::node_connectivity(&ag.graph, src, dst);
            }
        }
        ConnectivityInput::EdgeConnectivity(ag) => {
            if ag.nodes.len() >= 2 {
                let src = &ag.nodes[0];
                let dst = &ag.nodes[ag.nodes.len() - 1];
                let _ = fnx_algorithms::edge_connectivity_edmonds_karp(
                    &ag.graph, src, dst, &ag.weight_attr,
                );
            }
        }
        ConnectivityInput::GlobalNodeConnectivity(ag) => {
            let _ = fnx_algorithms::global_node_connectivity(&ag.graph);
        }
        ConnectivityInput::GlobalEdgeConnectivity(ag) => {
            let _ = fnx_algorithms::global_edge_connectivity_edmonds_karp(&ag.graph, &ag.weight_attr);
        }
    }
});
