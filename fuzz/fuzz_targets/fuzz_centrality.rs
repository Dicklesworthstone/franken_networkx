//! Structure-aware fuzzer for centrality algorithms.
//!
//! Tests pagerank, betweenness, closeness, degree, and eigenvector centrality
//! on valid-but-pathological graph structures.

#![no_main]

mod arbitrary_graph;

use arbitrary::Arbitrary;
use arbitrary_graph::{ArbitraryDiGraph, ArbitraryGraph};
use fnx_algorithms::CentralityScore;
use fnx_classes::Graph;
use fnx_classes::digraph::DiGraph;
use libfuzzer_sys::fuzz_target;
use std::collections::HashSet;

const PAGERANK_SUM_EPS: f64 = 1.0e-3;

/// Assert that a centrality score Vec covers exactly the graph's node set
/// (no duplicates, no extras, no missing nodes) and that every value is
/// finite. This is the minimum invariant any node-keyed centrality must
/// satisfy regardless of input graph structure.
fn assert_score_set_covers_graph(scores: &[CentralityScore], graph: &Graph) {
    let expected: HashSet<&str> =
        graph.nodes_ordered().into_iter().collect();
    let actual: HashSet<&str> =
        scores.iter().map(|s| s.node.as_str()).collect();
    assert_eq!(
        actual.len(),
        scores.len(),
        "centrality result has duplicate node entries"
    );
    assert_eq!(
        actual, expected,
        "centrality result keys diverged from graph node set"
    );
    for s in scores {
        assert!(
            s.score.is_finite(),
            "centrality score must be finite: node={} score={}",
            s.node,
            s.score
        );
    }
}

fn assert_score_set_covers_digraph(scores: &[CentralityScore], digraph: &DiGraph) {
    let expected: HashSet<&str> =
        digraph.nodes_ordered().into_iter().collect();
    let actual: HashSet<&str> =
        scores.iter().map(|s| s.node.as_str()).collect();
    assert_eq!(
        actual.len(),
        scores.len(),
        "centrality result has duplicate node entries"
    );
    assert_eq!(
        actual, expected,
        "centrality result keys diverged from digraph node set"
    );
    for s in scores {
        assert!(
            s.score.is_finite(),
            "centrality score must be finite: node={} score={}",
            s.node,
            s.score
        );
    }
}

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
            if ag.graph.node_count() == 0 {
                return;
            }
            let result = fnx_algorithms::pagerank(&ag.graph);
            assert_score_set_covers_graph(&result.scores, &ag.graph);
            // PageRank is a probability distribution: scores sum to 1.0
            // (within tolerance) when the algorithm converges.
            let total: f64 = result.scores.iter().map(|s| s.score).sum();
            assert!(
                (total - 1.0).abs() < PAGERANK_SUM_EPS,
                "pagerank sum {} drifted from 1.0",
                total
            );
            for s in &result.scores {
                assert!(s.score >= -PAGERANK_SUM_EPS, "pagerank score went negative: {}", s.score);
            }
        }
        CentralityInput::PageRankDirected(ag) => {
            if ag.graph.node_count() == 0 {
                return;
            }
            let result = fnx_algorithms::pagerank_directed(&ag.graph);
            assert_score_set_covers_digraph(&result.scores, &ag.graph);
            let total: f64 = result.scores.iter().map(|s| s.score).sum();
            assert!(
                (total - 1.0).abs() < PAGERANK_SUM_EPS,
                "directed pagerank sum {} drifted from 1.0",
                total
            );
            for s in &result.scores {
                assert!(s.score >= -PAGERANK_SUM_EPS, "directed pagerank score went negative: {}", s.score);
            }
        }
        CentralityInput::BetweennessUndirected(ag) => {
            if ag.graph.node_count() == 0 {
                return;
            }
            let result = fnx_algorithms::betweenness_centrality(&ag.graph);
            assert_score_set_covers_graph(&result.scores, &ag.graph);
            for s in &result.scores {
                assert!(s.score >= -1.0e-9, "betweenness went negative: {}", s.score);
            }
        }
        CentralityInput::BetweennessDirected(ag) => {
            if ag.graph.node_count() == 0 {
                return;
            }
            let result = fnx_algorithms::betweenness_centrality_directed(&ag.graph);
            assert_score_set_covers_digraph(&result.scores, &ag.graph);
            for s in &result.scores {
                assert!(s.score >= -1.0e-9, "directed betweenness went negative: {}", s.score);
            }
        }
        CentralityInput::ClosenessUndirected(ag) => {
            if ag.graph.node_count() == 0 {
                return;
            }
            let result = fnx_algorithms::closeness_centrality(&ag.graph);
            assert_score_set_covers_graph(&result.scores, &ag.graph);
            for s in &result.scores {
                assert!(s.score >= 0.0 && s.score <= 1.0 + 1.0e-9,
                    "closeness out of [0,1]: node={} score={}", s.node, s.score);
            }
        }
        CentralityInput::ClosenessDirected(ag) => {
            if ag.graph.node_count() == 0 {
                return;
            }
            let result = fnx_algorithms::closeness_centrality_directed(&ag.graph);
            assert_score_set_covers_digraph(&result.scores, &ag.graph);
            for s in &result.scores {
                assert!(s.score >= 0.0 && s.score <= 1.0 + 1.0e-9,
                    "directed closeness out of [0,1]: node={} score={}", s.node, s.score);
            }
        }
        CentralityInput::DegreeUndirected(ag) => {
            if ag.graph.node_count() == 0 {
                return;
            }
            let result = fnx_algorithms::degree_centrality(&ag.graph);
            assert_score_set_covers_graph(&result.scores, &ag.graph);
            for s in &result.scores {
                assert!(s.score >= 0.0 && s.score <= 1.0 + 1.0e-9,
                    "degree centrality out of [0,1]: node={} score={}", s.node, s.score);
            }
        }
        CentralityInput::DegreeDirected(ag) => {
            if ag.graph.node_count() == 0 {
                return;
            }
            let result = fnx_algorithms::degree_centrality_directed(&ag.graph);
            assert_score_set_covers_digraph(&result.scores, &ag.graph);
            for s in &result.scores {
                assert!(s.score >= 0.0 && s.score <= 1.0 + 1.0e-9,
                    "directed degree centrality out of [0,1]: node={} score={}", s.node, s.score);
            }
        }
        CentralityInput::EigenvectorUndirected(ag) => {
            if ag.graph.node_count() == 0 {
                return;
            }
            let _ = fnx_algorithms::eigenvector_centrality(&ag.graph);
        }
        CentralityInput::EigenvectorDirected(ag) => {
            if ag.graph.node_count() == 0 {
                return;
            }
            let _ = fnx_algorithms::eigenvector_centrality_directed(&ag.graph);
        }
        CentralityInput::KatzUndirected(ag) => {
            if ag.graph.node_count() == 0 {
                return;
            }
            let _ = fnx_algorithms::katz_centrality(&ag.graph);
        }
        CentralityInput::KatzDirected(ag) => {
            if ag.graph.node_count() == 0 {
                return;
            }
            let _ = fnx_algorithms::katz_centrality_directed(&ag.graph);
        }
        CentralityInput::HitsUndirected(ag) => {
            if ag.graph.node_count() == 0 {
                return;
            }
            let _ = fnx_algorithms::hits_centrality(&ag.graph);
        }
        CentralityInput::HitsDirected(ag) => {
            if ag.graph.node_count() == 0 {
                return;
            }
            let _ = fnx_algorithms::hits_centrality_directed(&ag.graph);
        }
        CentralityInput::HarmonicUndirected(ag) => {
            if ag.graph.node_count() == 0 {
                return;
            }
            let result = fnx_algorithms::harmonic_centrality(&ag.graph);
            assert_score_set_covers_graph(&result.scores, &ag.graph);
            for s in &result.scores {
                assert!(s.score >= 0.0,
                    "harmonic centrality went negative: node={} score={}", s.node, s.score);
            }
        }
        CentralityInput::HarmonicDirected(ag) => {
            if ag.graph.node_count() == 0 {
                return;
            }
            let result = fnx_algorithms::harmonic_centrality_directed(&ag.graph);
            assert_score_set_covers_digraph(&result.scores, &ag.graph);
            for s in &result.scores {
                assert!(s.score >= 0.0,
                    "directed harmonic centrality went negative: node={} score={}", s.node, s.score);
            }
        }
    }
});
