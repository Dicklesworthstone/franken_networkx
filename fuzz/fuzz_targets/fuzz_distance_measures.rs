//! Structure-aware fuzzer for distance-measure, chordal, tree, and
//! core-decomposition algorithms.
//!
//! Covers ``distance_measures`` (which packs eccentricity/diameter/
//! radius/center/periphery into one BFS sweep), ``wiener_index``,
//! ``wiener_index_directed``, ``harmonic_diameter``, ``barycenter``,
//! plus the chordal/tree/core families: ``is_chordal``,
//! ``chordal_graph_treewidth``, ``is_tree``, ``is_forest``,
//! ``core_number``, ``k_core``, ``k_truss``, ``onion_layers``.
//!
//! Asserts a few cheap invariants so divergence between the eccentricity
//! vector and the summary fields can't slip past unnoticed:
//!
//! - On connected graphs, ``diameter == max(eccentricity)`` and
//!   ``radius == min(eccentricity)``.
//! - ``center`` ⊆ argmin(eccentricity), ``periphery`` ⊆
//!   argmax(eccentricity).
//! - ``barycenter`` is a non-empty subset of nodes when the input is
//!   connected.

#![no_main]

mod arbitrary_graph;

use arbitrary::Arbitrary;
use arbitrary_graph::{ArbitraryDiGraph, ArbitraryGraph};
use libfuzzer_sys::fuzz_target;

#[derive(Debug, Arbitrary)]
enum DistanceInput {
    /// Combined BFS sweep — eccentricity + diameter + radius + center
    /// + periphery, with the per-node-distance invariants above.
    DistanceMeasures(ArbitraryGraph),
    /// Wiener index (sum of all-pairs shortest path distances) on
    /// undirected graphs.
    WienerIndex(ArbitraryGraph),
    /// Wiener index on directed graphs — must not panic on graphs
    /// with unreachable nodes.
    WienerIndexDirected(ArbitraryDiGraph),
    /// Harmonic diameter (1 / mean of 1/d_uv).
    HarmonicDiameter(ArbitraryGraph),
    /// Barycenter — argmin of the sum-of-distances objective.
    Barycenter(ArbitraryGraph),
    /// is_chordal (chordal-graph predicate via MCS).
    IsChordal(ArbitraryGraph),
    /// Treewidth of a chordal graph (errors gracefully if non-chordal).
    ChordalGraphTreewidth(ArbitraryGraph),
    /// is_tree predicate.
    IsTree(ArbitraryGraph),
    /// is_forest predicate.
    IsForest(ArbitraryGraph),
    /// Core decomposition.
    CoreNumber(ArbitraryGraph),
    /// k-core subgraph extraction.
    KCore(ArbitraryGraph, u8),
    /// k-truss subgraph extraction.
    KTruss(ArbitraryGraph, u8),
    /// Onion layers decomposition.
    OnionLayers(ArbitraryGraph),
}

fn check_distance_measures_invariants(
    graph: &fnx_classes::Graph,
) {
    let result = fnx_algorithms::distance_measures(graph);
    let connected = fnx_algorithms::is_connected(graph).is_connected;
    let n = graph.node_count();

    // Eccentricity vector must list one value per node (when connected
    // and non-empty); on disconnected graphs the impl may report
    // partial info, but it must not panic and the structure must
    // remain coherent.
    if connected && n > 0 {
        assert_eq!(
            result.eccentricity.len(),
            n,
            "eccentricity must report one value per node on connected graph"
        );

        // diameter == max(eccentricity)
        let max_ecc = result.eccentricity.iter().map(|e| e.value).max().unwrap();
        assert_eq!(
            result.diameter, max_ecc,
            "diameter must equal max(eccentricity)"
        );

        // radius == min(eccentricity)
        let min_ecc = result.eccentricity.iter().map(|e| e.value).min().unwrap();
        assert_eq!(
            result.radius, min_ecc,
            "radius must equal min(eccentricity)"
        );

        // center ⊆ argmin(eccentricity)
        let argmin: std::collections::HashSet<&str> = result
            .eccentricity
            .iter()
            .filter(|e| e.value == min_ecc)
            .map(|e| e.node.as_str())
            .collect();
        for node in &result.center {
            assert!(
                argmin.contains(node.as_str()),
                "center node {node:?} not in argmin(eccentricity)"
            );
        }

        // periphery ⊆ argmax(eccentricity)
        let argmax: std::collections::HashSet<&str> = result
            .eccentricity
            .iter()
            .filter(|e| e.value == max_ecc)
            .map(|e| e.node.as_str())
            .collect();
        for node in &result.periphery {
            assert!(
                argmax.contains(node.as_str()),
                "periphery node {node:?} not in argmax(eccentricity)"
            );
        }
    }
}

fuzz_target!(|input: DistanceInput| {
    match input {
        DistanceInput::DistanceMeasures(ag) => {
            check_distance_measures_invariants(&ag.graph);
        }
        DistanceInput::WienerIndex(ag) => {
            let value = fnx_algorithms::wiener_index(&ag.graph);
            // Wiener index = sum of all-pairs shortest path distances.
            // Non-negative; may be +∞ as a sentinel for "disconnected"
            // but never NaN.
            assert!(!value.is_nan(), "wiener_index returned NaN");
            assert!(
                value >= 0.0 || !value.is_finite(),
                "wiener_index returned negative finite value {}",
                value
            );
        }
        DistanceInput::WienerIndexDirected(ag) => {
            let value = fnx_algorithms::wiener_index_directed(&ag.graph);
            assert!(!value.is_nan(), "wiener_index_directed returned NaN");
            assert!(
                value >= 0.0 || !value.is_finite(),
                "wiener_index_directed returned negative finite value {}",
                value
            );
        }
        DistanceInput::HarmonicDiameter(ag) => {
            let value = fnx_algorithms::harmonic_diameter(&ag.graph);
            // Harmonic diameter = 1 / mean(1/d_uv). Non-negative; may
            // be ±∞ on disconnected/empty inputs but never NaN.
            assert!(!value.is_nan(), "harmonic_diameter returned NaN");
            assert!(
                value >= 0.0 || !value.is_finite(),
                "harmonic_diameter returned negative finite value {}",
                value
            );
        }
        DistanceInput::Barycenter(ag) => {
            let connected = fnx_algorithms::is_connected(&ag.graph).is_connected;
            let result = fnx_algorithms::barycenter(&ag.graph);
            if connected && ag.graph.node_count() > 0 {
                assert!(
                    !result.is_empty(),
                    "barycenter of a non-empty connected graph must be non-empty"
                );
            }
        }
        DistanceInput::IsChordal(ag) => {
            // Cross-check: every tree is chordal (a tree has no cycles
            // at all, so trivially every cycle of length ≥ 4 has a
            // chord).
            let chordal = fnx_algorithms::is_chordal(&ag.graph);
            let tree = fnx_algorithms::is_tree(&ag.graph);
            if tree.is_tree {
                assert!(
                    chordal,
                    "is_tree=true implies is_chordal=true (failed cross-check)"
                );
            }
        }
        DistanceInput::ChordalGraphTreewidth(ag) => {
            // Treewidth is bounded by max(0, n-1).
            if let Ok(tw) = fnx_algorithms::chordal_graph_treewidth(&ag.graph) {
                let upper = ag.graph.node_count().saturating_sub(1);
                assert!(
                    tw <= upper,
                    "chordal_graph_treewidth {} exceeds n-1 = {}",
                    tw,
                    upper
                );
            }
        }
        DistanceInput::IsTree(ag) => {
            // Tree → forest. n-1 edges if non-empty.
            let result = fnx_algorithms::is_tree(&ag.graph);
            if result.is_tree && ag.graph.node_count() > 0 {
                assert_eq!(
                    ag.graph.edge_count(),
                    ag.graph.node_count() - 1,
                    "is_tree=true but |E|={} != |V|-1={}",
                    ag.graph.edge_count(),
                    ag.graph.node_count() - 1
                );
                assert!(
                    fnx_algorithms::is_forest(&ag.graph).is_forest,
                    "is_tree=true but is_forest=false"
                );
            }
        }
        DistanceInput::IsForest(ag) => {
            let result = fnx_algorithms::is_forest(&ag.graph);
            if result.is_forest && ag.graph.node_count() > 0 {
                // A forest is acyclic, so |E| < |V|.
                assert!(
                    ag.graph.edge_count() < ag.graph.node_count(),
                    "is_forest=true but |E|={} >= |V|={}",
                    ag.graph.edge_count(),
                    ag.graph.node_count()
                );
            }
        }
        DistanceInput::CoreNumber(ag) => {
            let result = fnx_algorithms::core_number(&ag.graph);
            // Coverage + bound check.
            assert_eq!(
                result.core_numbers.len(),
                ag.graph.node_count(),
                "core_number reports {} entries but graph has {} nodes",
                result.core_numbers.len(),
                ag.graph.node_count()
            );
            let upper = ag.graph.node_count().saturating_sub(1);
            for c in &result.core_numbers {
                assert!(
                    ag.graph.has_node(&c.node),
                    "core_number reports foreign node {}",
                    c.node
                );
                assert!(
                    c.core <= upper,
                    "core number {} for node {} exceeds n-1 = {}",
                    c.core,
                    c.node,
                    upper
                );
            }
        }
        DistanceInput::KCore(ag, k) => {
            let k_val = (k as usize) % 8;
            let kcore = fnx_algorithms::k_core(&ag.graph, Some(k_val));
            // Subgraph relationship: every node in the k-core is in G.
            for n in &kcore.nodes {
                assert!(
                    ag.graph.has_node(n),
                    "k_core node {} not in original graph",
                    n
                );
            }
            for (u, v) in &kcore.edges {
                assert!(
                    ag.graph.has_edge(u, v),
                    "k_core edge ({}, {}) not in original graph",
                    u,
                    v
                );
            }
        }
        DistanceInput::KTruss(ag, k) => {
            let k_val = (k as usize) % 6;
            let ktruss = fnx_algorithms::k_truss(&ag.graph, k_val);
            for n in &ktruss.nodes {
                assert!(
                    ag.graph.has_node(n),
                    "k_truss node {} not in original graph",
                    n
                );
            }
            for (u, v) in &ktruss.edges {
                assert!(
                    ag.graph.has_edge(u, v),
                    "k_truss edge ({}, {}) not in original graph",
                    u,
                    v
                );
            }
        }
        DistanceInput::OnionLayers(ag) => {
            let result = fnx_algorithms::onion_layers(&ag.graph);
            // Onion layers report one entry per node.
            assert_eq!(
                result.layers.len(),
                ag.graph.node_count(),
                "onion_layers reports {} entries but graph has {} nodes",
                result.layers.len(),
                ag.graph.node_count()
            );
            for entry in &result.layers {
                assert!(
                    ag.graph.has_node(&entry.node),
                    "onion_layers reports foreign node {}",
                    entry.node
                );
            }
        }
    }
});
