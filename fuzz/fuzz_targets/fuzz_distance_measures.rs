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
            let _ = fnx_algorithms::wiener_index(&ag.graph);
        }
        DistanceInput::WienerIndexDirected(ag) => {
            let _ = fnx_algorithms::wiener_index_directed(&ag.graph);
        }
        DistanceInput::HarmonicDiameter(ag) => {
            let _ = fnx_algorithms::harmonic_diameter(&ag.graph);
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
            let _ = fnx_algorithms::is_chordal(&ag.graph);
        }
        DistanceInput::ChordalGraphTreewidth(ag) => {
            // Graceful error when input is non-chordal — must not panic.
            let _ = fnx_algorithms::chordal_graph_treewidth(&ag.graph);
        }
        DistanceInput::IsTree(ag) => {
            let _ = fnx_algorithms::is_tree(&ag.graph);
        }
        DistanceInput::IsForest(ag) => {
            let _ = fnx_algorithms::is_forest(&ag.graph);
        }
        DistanceInput::CoreNumber(ag) => {
            let _ = fnx_algorithms::core_number(&ag.graph);
        }
        DistanceInput::KCore(ag, k) => {
            // Bound k to a reasonable range so the fuzzer doesn't only
            // hit the empty-result branch.
            let k_val = (k as usize) % 8;
            let _ = fnx_algorithms::k_core(&ag.graph, Some(k_val));
        }
        DistanceInput::KTruss(ag, k) => {
            let k_val = (k as usize) % 6;
            let _ = fnx_algorithms::k_truss(&ag.graph, k_val);
        }
        DistanceInput::OnionLayers(ag) => {
            let _ = fnx_algorithms::onion_layers(&ag.graph);
        }
    }
});
