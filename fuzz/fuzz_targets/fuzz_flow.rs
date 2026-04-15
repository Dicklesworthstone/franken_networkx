//! Structure-aware fuzzer for flow algorithms.
//!
//! Tests max flow, min cut, and edge connectivity on valid-but-pathological
//! flow network structures.

#![no_main]

mod arbitrary_graph;

use arbitrary::Arbitrary;
use arbitrary_graph::{ArbitraryFlowNetwork, ArbitraryFlowNetworkUndirected};
use libfuzzer_sys::fuzz_target;

#[derive(Debug, Arbitrary)]
enum FlowInput {
    /// Max flow using Edmonds-Karp (directed).
    MaxFlowDirected(ArbitraryFlowNetwork),
    /// Min cut using Edmonds-Karp (directed).
    MinCutDirected(ArbitraryFlowNetwork),
    /// Minimum ST edge cut (undirected).
    MinStEdgeCut(ArbitraryFlowNetworkUndirected),
    /// Max flow using Edmonds-Karp (undirected).
    MaxFlowUndirected(ArbitraryFlowNetworkUndirected),
}

fuzz_target!(|input: FlowInput| {
    match input {
        FlowInput::MaxFlowDirected(net) => {
            let _ = fnx_algorithms::max_flow_edmonds_karp_directed(
                &net.graph,
                &net.source,
                &net.sink,
                &net.capacity_attr,
            );
        }
        FlowInput::MinCutDirected(net) => {
            let _ = fnx_algorithms::minimum_cut_edmonds_karp_directed(
                &net.graph,
                &net.source,
                &net.sink,
                &net.capacity_attr,
            );
        }
        FlowInput::MinStEdgeCut(net) => {
            let _ = fnx_algorithms::minimum_st_edge_cut_edmonds_karp(
                &net.graph,
                &net.source,
                &net.sink,
                &net.capacity_attr,
            );
        }
        FlowInput::MaxFlowUndirected(net) => {
            let _ = fnx_algorithms::max_flow_edmonds_karp(
                &net.graph,
                &net.source,
                &net.sink,
                &net.capacity_attr,
            );
        }
    }
});
