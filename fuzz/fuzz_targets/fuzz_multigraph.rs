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

#[derive(Debug, Arbitrary)]
enum MultiGraphInput {
    Undirected(ArbitraryMultiGraph),
    Directed(ArbitraryMultiDiGraph),
}

fuzz_target!(|input: MultiGraphInput| {
    match input {
        MultiGraphInput::Undirected(ag) => {
            let g = &ag.graph;
            let _ = g.node_count();
            let _ = g.edge_count();
            // Snapshot-style reads — exercise the keyed-edge path.
            let _ = g.edges_ordered();
            for node in &ag.nodes {
                let _ = g.neighbors(node);
            }
        }
        MultiGraphInput::Directed(ag) => {
            let g = &ag.graph;
            let _ = g.node_count();
            let _ = g.edge_count();
            let _ = g.edges_ordered();
            for node in &ag.nodes {
                let _ = g.neighbors(node);
            }
        }
    }
});
