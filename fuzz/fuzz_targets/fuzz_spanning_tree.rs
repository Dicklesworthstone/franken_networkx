//! Structure-aware fuzzer for spanning tree algorithms.
//!
//! Tests minimum spanning tree (Kruskal, Prim), maximum spanning tree,
//! and tree validation on valid-but-pathological graph structures.

#![no_main]

mod arbitrary_graph;

use arbitrary::Arbitrary;
use arbitrary_graph::{ArbitraryGraph, ArbitraryWeightedGraph};
use libfuzzer_sys::fuzz_target;

#[derive(Debug, Arbitrary)]
enum SpanningTreeInput {
    /// Minimum spanning tree (Kruskal).
    MstKruskal(ArbitraryWeightedGraph),
    /// Minimum spanning tree (Prim).
    MstPrim(ArbitraryWeightedGraph),
    /// Maximum spanning tree.
    MaxSt(ArbitraryWeightedGraph),
    /// Is tree check.
    IsTree(ArbitraryGraph),
    /// Is forest check.
    IsForest(ArbitraryGraph),
    /// Number of spanning trees.
    NumberSpanningTrees(ArbitraryWeightedGraph),
}

fuzz_target!(|input: SpanningTreeInput| {
    match input {
        SpanningTreeInput::MstKruskal(ag) => {
            let _ = fnx_algorithms::minimum_spanning_tree(&ag.graph, &ag.weight_attr);
        }
        SpanningTreeInput::MstPrim(ag) => {
            let _ = fnx_algorithms::minimum_spanning_tree_prim(&ag.graph, &ag.weight_attr);
        }
        SpanningTreeInput::MaxSt(ag) => {
            let _ = fnx_algorithms::maximum_spanning_tree(&ag.graph, &ag.weight_attr);
        }
        SpanningTreeInput::IsTree(ag) => {
            let _ = fnx_algorithms::is_tree(&ag.graph);
        }
        SpanningTreeInput::IsForest(ag) => {
            let _ = fnx_algorithms::is_forest(&ag.graph);
        }
        SpanningTreeInput::NumberSpanningTrees(ag) => {
            // Only compute for small graphs (determinant is O(n^3))
            if ag.nodes.len() <= 16 {
                let _ = fnx_algorithms::number_of_spanning_trees(&ag.graph, Some(&ag.weight_attr));
            }
        }
    }
});
