//! Structure-aware fuzzer for strongly-connected-components and
//! path-generation algorithms.
//!
//! Drives the algorithms whose conformance harnesses landed recently:
//!
//! - SCC family: ``strongly_connected_components`` (Tarjan),
//!   ``kosaraju_strongly_connected_components``, ``condensation``,
//!   ``attracting_components``.
//! - Biconnected family: ``biconnected_components``,
//!   ``biconnected_component_edges``, ``articulation_points``,
//!   ``bridges``.
//! - Path family: ``all_simple_paths``, ``all_simple_paths_directed``,
//!   ``shortest_simple_paths``.
//!
//! In addition to the no-panic invariant, asserts these cheap runtime
//! contracts:
//!
//! - On a directed graph, ``strongly_connected_components`` and
//!   ``kosaraju_strongly_connected_components`` enumerate the same
//!   set of components (yield order may differ).
//! - The ``condensation`` has exactly one node per SCC.
//! - Every attracting component is itself an SCC (subset relation).
//! - A bridge edge belongs to a 2-node biconnected component (its
//!   endpoints form an articulation pair on the bridge).
//! - ``shortest_simple_paths`` yields paths in non-decreasing length.

#![no_main]

mod arbitrary_graph;

use arbitrary::Arbitrary;
use arbitrary_graph::{ArbitraryDiGraph, ArbitraryGraph};
use libfuzzer_sys::fuzz_target;
use std::collections::HashSet;

#[derive(Debug, Arbitrary)]
enum SccPathInput {
    /// Tarjan vs Kosaraju partition equivalence on directed input.
    SccPartitionEquivalence(ArbitraryDiGraph),
    /// condensation: |V| equals number of SCCs.
    Condensation(ArbitraryDiGraph),
    /// attracting_components ⊆ SCCs.
    AttractingComponents(ArbitraryDiGraph),
    /// biconnected_components on undirected.
    BiconnectedComponents(ArbitraryGraph),
    /// biconnected_component_edges on undirected.
    BiconnectedComponentEdges(ArbitraryGraph),
    /// articulation_points + bridges + every-bridge-is-2-node-bcc invariant.
    ArticulationAndBridges(ArbitraryGraph),
    /// all_simple_paths undirected with bounded cutoff.
    AllSimplePathsUndirected(ArbitraryGraph, u8),
    /// all_simple_paths directed.
    AllSimplePathsDirected(ArbitraryDiGraph, u8),
    /// shortest_simple_paths length-monotonicity invariant.
    ShortestSimplePaths(ArbitraryGraph),
}

fn ssc_partition_equivalence(g: &fnx_classes::digraph::DiGraph) {
    let tarjan = fnx_algorithms::strongly_connected_components(g);
    let kosaraju = fnx_algorithms::kosaraju_strongly_connected_components(g);
    let tarjan_set: HashSet<Vec<String>> = tarjan
        .iter()
        .map(|c| {
            let mut s = c.clone();
            s.sort();
            s
        })
        .collect();
    let kosaraju_set: HashSet<Vec<String>> = kosaraju
        .iter()
        .map(|c| {
            let mut s = c.clone();
            s.sort();
            s
        })
        .collect();
    assert_eq!(
        tarjan_set, kosaraju_set,
        "Tarjan and Kosaraju partitioned into different SCCs"
    );
}

fn condensation_node_count_invariant(g: &fnx_classes::digraph::DiGraph) {
    let sccs = fnx_algorithms::strongly_connected_components(g);
    let (cond, _mapping) = fnx_algorithms::condensation(g);
    assert_eq!(
        cond.node_count(),
        sccs.len(),
        "condensation node count != number of SCCs"
    );
}

fn attracting_components_subset(g: &fnx_classes::digraph::DiGraph) {
    let sccs: HashSet<Vec<String>> = fnx_algorithms::strongly_connected_components(g)
        .into_iter()
        .map(|mut c| {
            c.sort();
            c
        })
        .collect();
    let attracting: Vec<Vec<String>> = fnx_algorithms::attracting_components(g);
    for ac in attracting {
        let mut sorted = ac.clone();
        sorted.sort();
        assert!(
            sccs.contains(&sorted),
            "attracting component {sorted:?} not in SCC set"
        );
    }
}

fn articulation_and_bridges_invariant(g: &fnx_classes::Graph) {
    let bridges = fnx_algorithms::bridges(g);
    let bccs = fnx_algorithms::biconnected_component_edges(g);
    // Every bridge edge must belong to some biconnected component
    // that contains exactly one edge (the bridge itself).
    let bcc_edge_sets: Vec<HashSet<(String, String)>> = bccs
        .iter()
        .map(|bcc| {
            bcc.iter()
                .map(|(u, v)| {
                    let (a, b) = if u <= v {
                        (u.clone(), v.clone())
                    } else {
                        (v.clone(), u.clone())
                    };
                    (a, b)
                })
                .collect()
        })
        .collect();
    for bridge in &bridges.edges {
        let (u, v) = (&bridge.0, &bridge.1);
        let (a, b) = if u <= v {
            (u.clone(), v.clone())
        } else {
            (v.clone(), u.clone())
        };
        let canonical = (a, b);
        let in_singleton_bcc = bcc_edge_sets
            .iter()
            .any(|s| s.len() == 1 && s.contains(&canonical));
        assert!(
            in_singleton_bcc,
            "bridge {canonical:?} not in any singleton BCC"
        );
    }
}

fn shortest_simple_paths_monotonic(g: &fnx_classes::Graph) {
    let nodes = g.nodes_ordered();
    if nodes.len() < 2 {
        return;
    }
    let src = nodes[0];
    let tgt = nodes[nodes.len() - 1];
    let paths = fnx_algorithms::shortest_simple_paths(g, src, tgt, None);
    let mut prev_len = 0;
    for p in &paths {
        assert!(
            p.len() >= prev_len,
            "shortest_simple_paths violates non-decreasing length \
             (prev={prev_len}, this={})",
            p.len()
        );
        prev_len = p.len();
    }
}

fuzz_target!(|input: SccPathInput| {
    match input {
        SccPathInput::SccPartitionEquivalence(ag) => {
            ssc_partition_equivalence(&ag.graph);
        }
        SccPathInput::Condensation(ag) => {
            condensation_node_count_invariant(&ag.graph);
        }
        SccPathInput::AttractingComponents(ag) => {
            attracting_components_subset(&ag.graph);
        }
        SccPathInput::BiconnectedComponents(ag) => {
            let bccs = fnx_algorithms::biconnected_components(&ag.graph);
            // Each BCC is non-empty and every node within is in G.
            for bcc in &bccs {
                assert!(
                    !bcc.is_empty(),
                    "biconnected_components emitted empty BCC"
                );
                for n in bcc {
                    assert!(
                        ag.graph.has_node(n),
                        "biconnected_components contains foreign node {}",
                        n
                    );
                }
            }
        }
        SccPathInput::BiconnectedComponentEdges(ag) => {
            let bccs = fnx_algorithms::biconnected_component_edges(&ag.graph);
            // Each BCC's edges are real edges of G.
            for bcc in &bccs {
                for (u, v) in bcc {
                    assert!(
                        ag.graph.has_edge(u, v),
                        "biconnected_component_edges emitted non-edge ({}, {})",
                        u, v
                    );
                }
            }
        }
        SccPathInput::ArticulationAndBridges(ag) => {
            let aps = fnx_algorithms::articulation_points(&ag.graph);
            // Every articulation point is a node of G with no duplicates.
            let mut seen: HashSet<&str> = HashSet::new();
            for n in &aps.nodes {
                assert!(
                    ag.graph.has_node(n),
                    "articulation_points contains foreign node {}",
                    n
                );
                assert!(
                    seen.insert(n.as_str()),
                    "articulation_points emitted duplicate node {}",
                    n
                );
            }
            articulation_and_bridges_invariant(&ag.graph);
        }
        SccPathInput::AllSimplePathsUndirected(ag, k) => {
            let nodes = ag.graph.nodes_ordered();
            if nodes.len() >= 2 {
                let src = nodes[0];
                let tgt = nodes[nodes.len() - 1];
                let cutoff = (k as usize) % 6;
                let result = fnx_algorithms::all_simple_paths(
                    &ag.graph,
                    src,
                    tgt,
                    Some(cutoff),
                );
                // Every yielded path is a valid simple path source→target.
                for path in &result.paths {
                    if path.is_empty() {
                        continue;
                    }
                    assert_eq!(path.first().map(|s| s.as_str()), Some(src),
                        "all_simple_paths path doesn't start at source");
                    assert_eq!(path.last().map(|s| s.as_str()), Some(tgt),
                        "all_simple_paths path doesn't end at target");
                    let mut seen: HashSet<&str> = HashSet::new();
                    for n in path {
                        assert!(
                            seen.insert(n.as_str()),
                            "all_simple_paths emitted non-simple path (repeats {})",
                            n
                        );
                    }
                    for w in path.windows(2) {
                        assert!(
                            ag.graph.has_edge(&w[0], &w[1]),
                            "all_simple_paths emitted non-edge ({}, {})",
                            w[0], w[1]
                        );
                    }
                }
            }
        }
        SccPathInput::AllSimplePathsDirected(ag, k) => {
            let nodes = ag.graph.nodes_ordered();
            if nodes.len() >= 2 {
                let src = nodes[0];
                let tgt = nodes[nodes.len() - 1];
                let cutoff = (k as usize) % 6;
                let result = fnx_algorithms::all_simple_paths_directed(
                    &ag.graph,
                    src,
                    tgt,
                    Some(cutoff),
                );
                for path in &result.paths {
                    if path.is_empty() {
                        continue;
                    }
                    assert_eq!(path.first().map(|s| s.as_str()), Some(src),
                        "all_simple_paths_directed path doesn't start at source");
                    assert_eq!(path.last().map(|s| s.as_str()), Some(tgt),
                        "all_simple_paths_directed path doesn't end at target");
                    let mut seen: HashSet<&str> = HashSet::new();
                    for n in path {
                        assert!(
                            seen.insert(n.as_str()),
                            "all_simple_paths_directed emitted non-simple path (repeats {})",
                            n
                        );
                    }
                    for w in path.windows(2) {
                        assert!(
                            ag.graph.has_edge(&w[0], &w[1]),
                            "all_simple_paths_directed emitted non-edge {} -> {}",
                            w[0], w[1]
                        );
                    }
                }
            }
        }
        SccPathInput::ShortestSimplePaths(ag) => {
            shortest_simple_paths_monotonic(&ag.graph);
        }
    }
});
