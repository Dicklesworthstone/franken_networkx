//! Structure-aware fuzzer for connectivity algorithms.
//!
//! Tests connected components, articulation points, bridges, and
//! node/edge connectivity on valid-but-pathological graph structures.

#![no_main]

mod arbitrary_graph;

use arbitrary::Arbitrary;
use arbitrary_graph::{ArbitraryDiGraph, ArbitraryGraph, ArbitraryWeightedGraph};
use libfuzzer_sys::fuzz_target;

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
            let _ = fnx_algorithms::connected_components(&ag.graph);
        }
        ConnectivityInput::NumberConnectedComponents(ag) => {
            let _ = fnx_algorithms::number_connected_components(&ag.graph);
        }
        ConnectivityInput::IsConnected(ag) => {
            let _ = fnx_algorithms::is_connected(&ag.graph);
        }
        ConnectivityInput::ArticulationPoints(ag) => {
            let _ = fnx_algorithms::articulation_points(&ag.graph);
        }
        ConnectivityInput::Bridges(ag) => {
            let _ = fnx_algorithms::bridges(&ag.graph);
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
