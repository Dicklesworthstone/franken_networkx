//! Fuzzer that exercises `ArbitraryMultiGraph` / `ArbitraryMultiDiGraph`.
//!
//! The primary goal of this target is to drive the new multigraph
//! Arbitrary impls (franken_networkx-njg7f) through code paths that
//! handle keyed parallel edges so any panics in those code paths are
//! caught by libfuzzer. We run a handful of structural reads on the
//! generated graph and, where applicable, pass it through
//! `edges_ordered` / `node_count` / `edge_count` / `neighbors`.

#![no_main]

mod arbitrary_graph;

use arbitrary::Arbitrary;
use arbitrary_graph::{ArbitraryMultiDiGraph, ArbitraryMultiGraph};
use libfuzzer_sys::fuzz_target;
use std::collections::HashSet;

#[derive(Debug, Arbitrary)]
enum MultiGraphInput {
    Undirected(ArbitraryMultiGraph),
    Directed(ArbitraryMultiDiGraph),
}

fuzz_target!(|input: MultiGraphInput| {
    match input {
        MultiGraphInput::Undirected(ag) => {
            let g = &ag.graph;
            let n = g.node_count();
            let m = g.edge_count();
            // node_count / edge_count must equal the cardinality of
            // the corresponding ordered iterators — catches any
            // bookkeeping drift between cached counts and underlying
            // maps.
            assert_eq!(
                g.nodes_ordered().len(),
                n,
                "MultiGraph node_count {} != |nodes_ordered| {}",
                n,
                g.nodes_ordered().len()
            );
            let edges = g.edges_ordered();
            assert_eq!(
                edges.len(),
                m,
                "MultiGraph edge_count {} != |edges_ordered| {}",
                m,
                edges.len()
            );
            // Every edge endpoint must be a real node.
            for edge in &edges {
                assert!(
                    g.has_node(&edge.left),
                    "MultiGraph edge endpoint {} not in node set",
                    edge.left
                );
                assert!(
                    g.has_node(&edge.right),
                    "MultiGraph edge endpoint {} not in node set",
                    edge.right
                );
            }
            // Neighbor relation symmetry on undirected multigraph
            // (sampled to keep fuzzer fast).
            for node in ag.nodes.iter().take(8) {
                if let Some(neighbors) = g.neighbors(node) {
                    let neighbor_set: HashSet<&str> =
                        neighbors.iter().copied().collect();
                    for neighbor in &neighbor_set {
                        if let Some(reverse) = g.neighbors(neighbor) {
                            let reverse_set: HashSet<&str> =
                                reverse.iter().copied().collect();
                            assert!(
                                reverse_set.contains(node.as_str()),
                                "asymmetry: {} in neighbors({}) but not vice versa",
                                neighbor, node
                            );
                        }
                    }
                }
            }
        }
        MultiGraphInput::Directed(ag) => {
            let g = &ag.graph;
            let n = g.node_count();
            let m = g.edge_count();
            assert_eq!(
                g.nodes_ordered().len(),
                n,
                "MultiDiGraph node_count {} != |nodes_ordered| {}",
                n,
                g.nodes_ordered().len()
            );
            let edges = g.edges_ordered();
            assert_eq!(
                edges.len(),
                m,
                "MultiDiGraph edge_count {} != |edges_ordered| {}",
                m,
                edges.len()
            );
            for edge in &edges {
                assert!(
                    g.has_node(&edge.source),
                    "MultiDiGraph edge endpoint {} not in node set",
                    edge.source
                );
                assert!(
                    g.has_node(&edge.target),
                    "MultiDiGraph edge endpoint {} not in node set",
                    edge.target
                );
            }
            for node in &ag.nodes {
                let _ = g.neighbors(node);
            }
        }
    }
});
