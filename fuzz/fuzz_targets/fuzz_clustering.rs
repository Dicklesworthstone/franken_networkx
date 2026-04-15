//! Structure-aware fuzzer for clustering algorithms.
//!
//! Tests clustering coefficient, triangles, transitivity, and
//! related metrics on valid-but-pathological graph structures.

#![no_main]

mod arbitrary_graph;

use arbitrary::Arbitrary;
use arbitrary_graph::{ArbitraryDiGraph, ArbitraryGraph};
use libfuzzer_sys::fuzz_target;

#[derive(Debug, Arbitrary)]
enum ClusteringInput {
    /// Clustering coefficient on undirected graph.
    ClusteringUndirected(ArbitraryGraph),
    /// Clustering coefficient on directed graph.
    ClusteringDirected(ArbitraryDiGraph),
    /// Triangles count.
    Triangles(ArbitraryGraph),
    /// Square clustering.
    SquareClustering(ArbitraryGraph),
    /// Core number (k-core decomposition).
    CoreNumber(ArbitraryGraph),
    /// K-core subgraph.
    KCore(ArbitraryGraph),
    /// K-truss subgraph.
    KTruss(ArbitraryGraph),
    /// Onion layers decomposition.
    OnionLayers(ArbitraryGraph),
    /// Is bipartite check.
    IsBipartite(ArbitraryGraph),
    /// Bipartite sets.
    BipartiteSets(ArbitraryGraph),
    /// Greedy graph coloring.
    GreedyColor(ArbitraryGraph),
}

/// A clustering input with an embedded k parameter for k-core/k-truss.
#[derive(Debug, Arbitrary)]
struct ClusteringInputWithK {
    input: ClusteringInput,
    k_value: u8,
}

fuzz_target!(|input_with_k: ClusteringInputWithK| {
    let k = (input_with_k.k_value % 10) as usize;

    match input_with_k.input {
        ClusteringInput::ClusteringUndirected(ag) => {
            let _ = fnx_algorithms::clustering_coefficient(&ag.graph);
        }
        ClusteringInput::ClusteringDirected(ag) => {
            let _ = fnx_algorithms::clustering_coefficient_directed(&ag.graph);
        }
        ClusteringInput::Triangles(ag) => {
            let _ = fnx_algorithms::triangles(&ag.graph);
        }
        ClusteringInput::SquareClustering(ag) => {
            let _ = fnx_algorithms::square_clustering(&ag.graph);
        }
        ClusteringInput::CoreNumber(ag) => {
            let _ = fnx_algorithms::core_number(&ag.graph);
        }
        ClusteringInput::KCore(ag) => {
            let _ = fnx_algorithms::k_core(&ag.graph, Some(k));
        }
        ClusteringInput::KTruss(ag) => {
            // k-truss requires k >= 2
            let k_truss = k.max(2);
            let _ = fnx_algorithms::k_truss(&ag.graph, k_truss);
        }
        ClusteringInput::OnionLayers(ag) => {
            let _ = fnx_algorithms::onion_layers(&ag.graph);
        }
        ClusteringInput::IsBipartite(ag) => {
            let _ = fnx_algorithms::is_bipartite(&ag.graph);
        }
        ClusteringInput::BipartiteSets(ag) => {
            let _ = fnx_algorithms::bipartite_sets(&ag.graph);
        }
        ClusteringInput::GreedyColor(ag) => {
            let _ = fnx_algorithms::greedy_color(&ag.graph);
        }
    }
});
