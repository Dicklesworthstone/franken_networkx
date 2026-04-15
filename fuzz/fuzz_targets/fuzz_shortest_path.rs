//! Structure-aware fuzzer for shortest path algorithms.
//!
//! Tests dijkstra, bellman-ford, and unweighted shortest paths on
//! valid-but-pathological graph structures.

#![no_main]

mod arbitrary_graph;

use arbitrary::Arbitrary;
use arbitrary_graph::{
    ArbitraryDiGraph, ArbitraryGraph, ArbitraryWeightedDiGraph, ArbitraryWeightedGraph,
};
use libfuzzer_sys::fuzz_target;

#[derive(Debug, Arbitrary)]
enum ShortestPathInput {
    /// Unweighted shortest path on undirected graph.
    UnweightedUndirected(ArbitraryGraph),
    /// Unweighted shortest path on directed graph.
    UnweightedDirected(ArbitraryDiGraph),
    /// Weighted (Dijkstra) shortest path on undirected graph.
    WeightedUndirected(ArbitraryWeightedGraph),
    /// Weighted (Dijkstra) shortest path on directed graph.
    WeightedDirected(ArbitraryWeightedDiGraph),
    /// Single-source shortest path (all destinations).
    SingleSource(ArbitraryGraph),
    /// Multi-source dijkstra.
    MultiSource(ArbitraryWeightedGraph),
}

fuzz_target!(|input: ShortestPathInput| {
    match input {
        ShortestPathInput::UnweightedUndirected(ag) => {
            if ag.nodes.len() >= 2 {
                // Use first and last nodes as source/target
                let src = &ag.nodes[0];
                let dst = &ag.nodes[ag.nodes.len() - 1];
                let _ = fnx_algorithms::shortest_path_unweighted(&ag.graph, src, dst);
            }
        }
        ShortestPathInput::UnweightedDirected(ag) => {
            if ag.nodes.len() >= 2 {
                let src = &ag.nodes[0];
                let dst = &ag.nodes[ag.nodes.len() - 1];
                let _ = fnx_algorithms::shortest_path_unweighted_directed(&ag.graph, src, dst);
            }
        }
        ShortestPathInput::WeightedUndirected(ag) => {
            if ag.nodes.len() >= 2 {
                let src = &ag.nodes[0];
                let dst = &ag.nodes[ag.nodes.len() - 1];
                let _ = fnx_algorithms::shortest_path_weighted(
                    &ag.graph,
                    src,
                    dst,
                    &ag.weight_attr,
                );
            }
        }
        ShortestPathInput::WeightedDirected(ag) => {
            if ag.nodes.len() >= 2 {
                let src = &ag.nodes[0];
                let dst = &ag.nodes[ag.nodes.len() - 1];
                let _ = fnx_algorithms::shortest_path_weighted_directed(
                    &ag.graph,
                    src,
                    dst,
                    &ag.weight_attr,
                );
            }
        }
        ShortestPathInput::SingleSource(ag) => {
            if !ag.nodes.is_empty() {
                let src = &ag.nodes[0];
                let _ = fnx_algorithms::single_source_shortest_path(&ag.graph, src, None);
            }
        }
        ShortestPathInput::MultiSource(ag) => {
            if !ag.nodes.is_empty() {
                // Use first 1-3 nodes as sources
                let num_sources = 3.min(ag.nodes.len());
                let sources: Vec<&str> = ag.nodes.iter().take(num_sources).map(|s| s.as_str()).collect();
                let _ = fnx_algorithms::multi_source_dijkstra(&ag.graph, &sources, &ag.weight_attr);
            }
        }
    }
});
