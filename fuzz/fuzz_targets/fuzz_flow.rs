//! Structure-aware fuzzer for flow algorithms.
//!
//! Tests max flow, min cut, and edge connectivity on valid-but-pathological
//! flow network structures.

#![no_main]

mod arbitrary_graph;

use arbitrary::Arbitrary;
use arbitrary_graph::{ArbitraryFlowNetwork, ArbitraryFlowNetworkUndirected};
use libfuzzer_sys::fuzz_target;
use std::collections::HashSet;

const FLOW_EPS: f64 = 1.0e-6;

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
            let result = fnx_algorithms::max_flow_edmonds_karp_directed(
                &net.graph,
                &net.source,
                &net.sink,
                &net.capacity_attr,
            );
            if let Ok(flow) = result {
                // value must be finite, non-negative, and ≤ sum of
                // capacities incident to the source.
                assert!(
                    flow.value.is_finite() && flow.value >= -FLOW_EPS,
                    "max_flow value {} not finite/non-negative",
                    flow.value
                );
                // Cross-check with minimum_cut_edmonds_karp_directed —
                // by max-flow/min-cut theorem they must match.
                if let Ok(cut) = fnx_algorithms::minimum_cut_edmonds_karp_directed(
                    &net.graph,
                    &net.source,
                    &net.sink,
                    &net.capacity_attr,
                ) {
                    assert!(
                        (flow.value - cut.value).abs() < FLOW_EPS,
                        "max-flow {} != min-cut {} (max-flow/min-cut theorem)",
                        flow.value, cut.value
                    );
                }
                // Per-edge sanity: source / target are in G; flow value
                // is finite.
                for fe in &flow.flows {
                    assert!(
                        net.graph.has_edge(&fe.source, &fe.target),
                        "max_flow emitted flow on non-edge {} -> {}",
                        fe.source, fe.target
                    );
                    assert!(
                        fe.flow.is_finite(),
                        "max_flow per-edge flow {} -> {} is not finite ({})",
                        fe.source, fe.target, fe.flow
                    );
                }
            }
        }
        FlowInput::MinCutDirected(net) => {
            let result = fnx_algorithms::minimum_cut_edmonds_karp_directed(
                &net.graph,
                &net.source,
                &net.sink,
                &net.capacity_attr,
            );
            if let Ok(cut) = result {
                assert!(
                    cut.value.is_finite() && cut.value >= -FLOW_EPS,
                    "min_cut value {} not finite/non-negative",
                    cut.value
                );
                // Source partition contains the source; sink partition
                // contains the sink; the two are disjoint.
                let src_set: HashSet<&str> =
                    cut.source_partition.iter().map(|s| s.as_str()).collect();
                let sink_set: HashSet<&str> =
                    cut.sink_partition.iter().map(|s| s.as_str()).collect();
                assert!(
                    src_set.contains(net.source.as_str()),
                    "source {} not in source_partition",
                    net.source
                );
                assert!(
                    sink_set.contains(net.sink.as_str()),
                    "sink {} not in sink_partition",
                    net.sink
                );
                assert!(
                    src_set.is_disjoint(&sink_set),
                    "source and sink partitions overlap"
                );
            }
        }
        FlowInput::MinStEdgeCut(net) => {
            let result = fnx_algorithms::minimum_st_edge_cut_edmonds_karp(
                &net.graph,
                &net.source,
                &net.sink,
                &net.capacity_attr,
            );
            if let Ok(cut) = result {
                assert!(
                    cut.value.is_finite() && cut.value >= -FLOW_EPS,
                    "min_st_edge_cut value {} not finite/non-negative",
                    cut.value
                );
                // Every cut edge is an actual edge of G.
                for (u, v) in &cut.cut_edges {
                    assert!(
                        net.graph.has_edge(u, v),
                        "min_st_edge_cut emitted edge ({}, {}) not in graph",
                        u, v
                    );
                }
            }
        }
        FlowInput::MaxFlowUndirected(net) => {
            let result = fnx_algorithms::max_flow_edmonds_karp(
                &net.graph,
                &net.source,
                &net.sink,
                &net.capacity_attr,
            );
            if let Ok(flow) = result {
                assert!(
                    flow.value.is_finite() && flow.value >= -FLOW_EPS,
                    "max_flow_undirected value {} not finite/non-negative",
                    flow.value
                );
                for fe in &flow.flows {
                    assert!(
                        net.graph.has_edge(&fe.source, &fe.target),
                        "max_flow_undirected emitted flow on non-edge {} -> {}",
                        fe.source, fe.target
                    );
                    assert!(
                        fe.flow.is_finite(),
                        "max_flow_undirected per-edge flow {} -> {} is not finite ({})",
                        fe.source, fe.target, fe.flow
                    );
                }
            }
        }
    }
});
