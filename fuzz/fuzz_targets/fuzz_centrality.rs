//! Structure-aware fuzzer for centrality algorithms.
//!
//! Tests pagerank, betweenness, closeness, degree, and eigenvector centrality
//! on valid-but-pathological graph structures.

#![no_main]

mod arbitrary_graph;

use arbitrary::Arbitrary;
use arbitrary_graph::{ArbitraryDiGraph, ArbitraryGraph};
use libfuzzer_sys::fuzz_target;

#[derive(Debug, Arbitrary)]
enum CentralityInput {
    /// PageRank on undirected graph.
    PageRankUndirected(ArbitraryGraph),
    /// PageRank on directed graph.
    PageRankDirected(ArbitraryDiGraph),
    /// Betweenness centrality on undirected graph.
    BetweennessUndirected(ArbitraryGraph),
    /// Betweenness centrality on directed graph.
    BetweennessDirected(ArbitraryDiGraph),
    /// Closeness centrality on undirected graph.
    ClosenessUndirected(ArbitraryGraph),
    /// Closeness centrality on directed graph.
    ClosenessDirected(ArbitraryDiGraph),
    /// Degree centrality on undirected graph.
    DegreeUndirected(ArbitraryGraph),
    /// Degree centrality on directed graph.
    DegreeDirected(ArbitraryDiGraph),
    /// Eigenvector centrality on undirected graph.
    EigenvectorUndirected(ArbitraryGraph),
    /// Eigenvector centrality on directed graph.
    EigenvectorDirected(ArbitraryDiGraph),
    /// Katz centrality on undirected graph.
    KatzUndirected(ArbitraryGraph),
    /// Katz centrality on directed graph.
    KatzDirected(ArbitraryDiGraph),
    /// HITS centrality on undirected graph.
    HitsUndirected(ArbitraryGraph),
    /// HITS centrality on directed graph.
    HitsDirected(ArbitraryDiGraph),
    /// Harmonic centrality on undirected graph.
    HarmonicUndirected(ArbitraryGraph),
    /// Harmonic centrality on directed graph.
    HarmonicDirected(ArbitraryDiGraph),
}

fuzz_target!(|input: CentralityInput| {
    match input {
        CentralityInput::PageRankUndirected(ag) => {
            let _ = fnx_algorithms::pagerank(&ag.graph);
        }
        CentralityInput::PageRankDirected(ag) => {
            let _ = fnx_algorithms::pagerank_directed(&ag.graph);
        }
        CentralityInput::BetweennessUndirected(ag) => {
            let _ = fnx_algorithms::betweenness_centrality(&ag.graph);
        }
        CentralityInput::BetweennessDirected(ag) => {
            let _ = fnx_algorithms::betweenness_centrality_directed(&ag.graph);
        }
        CentralityInput::ClosenessUndirected(ag) => {
            let _ = fnx_algorithms::closeness_centrality(&ag.graph);
        }
        CentralityInput::ClosenessDirected(ag) => {
            let _ = fnx_algorithms::closeness_centrality_directed(&ag.graph);
        }
        CentralityInput::DegreeUndirected(ag) => {
            let _ = fnx_algorithms::degree_centrality(&ag.graph);
        }
        CentralityInput::DegreeDirected(ag) => {
            let _ = fnx_algorithms::degree_centrality_directed(&ag.graph);
        }
        CentralityInput::EigenvectorUndirected(ag) => {
            let _ = fnx_algorithms::eigenvector_centrality(&ag.graph);
        }
        CentralityInput::EigenvectorDirected(ag) => {
            let _ = fnx_algorithms::eigenvector_centrality_directed(&ag.graph);
        }
        CentralityInput::KatzUndirected(ag) => {
            let _ = fnx_algorithms::katz_centrality(&ag.graph);
        }
        CentralityInput::KatzDirected(ag) => {
            let _ = fnx_algorithms::katz_centrality_directed(&ag.graph);
        }
        CentralityInput::HitsUndirected(ag) => {
            let _ = fnx_algorithms::hits_centrality(&ag.graph);
        }
        CentralityInput::HitsDirected(ag) => {
            let _ = fnx_algorithms::hits_centrality_directed(&ag.graph);
        }
        CentralityInput::HarmonicUndirected(ag) => {
            let _ = fnx_algorithms::harmonic_centrality(&ag.graph);
        }
        CentralityInput::HarmonicDirected(ag) => {
            let _ = fnx_algorithms::harmonic_centrality_directed(&ag.graph);
        }
    }
});
