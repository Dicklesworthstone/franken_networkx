//! Structure-aware fuzzer for matching algorithms.
//!
//! Tests maximal matching, max weight matching, and matching validation
//! on valid-but-pathological graph structures.

#![no_main]

mod arbitrary_graph;

use arbitrary::Arbitrary;
use arbitrary_graph::{ArbitraryGraph, ArbitraryWeightedGraph};
use fnx_classes::Graph;
use libfuzzer_sys::fuzz_target;
use std::collections::HashSet;

/// Validate the structural matching contract: every reported edge is
/// an actual edge of G, and no node appears twice (a matching is a set
/// of edges with no shared endpoints).
fn assert_valid_matching(graph: &Graph, matching: &[(String, String)], label: &str) {
    let mut endpoints: HashSet<&str> = HashSet::new();
    for (u, v) in matching {
        assert!(
            graph.has_edge(u, v),
            "{}: edge ({}, {}) not in graph",
            label, u, v
        );
        assert!(
            u != v,
            "{}: matching contains self-loop on node {}",
            label, u
        );
        assert!(
            endpoints.insert(u.as_str()),
            "{}: node {} appears twice in matching",
            label, u
        );
        assert!(
            endpoints.insert(v.as_str()),
            "{}: node {} appears twice in matching",
            label, v
        );
    }
}

#[derive(Debug, Arbitrary)]
#[allow(clippy::enum_variant_names)]
enum MatchingInput {
    /// Maximal matching on unweighted graph.
    MaximalMatching(ArbitraryGraph),
    /// Maximum weight matching.
    MaxWeightMatching(ArbitraryWeightedGraph),
    /// Minimum weight matching.
    MinWeightMatching(ArbitraryWeightedGraph),
    /// Validate a random matching.
    ValidateMatching(ArbitraryGraph),
}

fuzz_target!(|input: MatchingInput| {
    match input {
        MatchingInput::MaximalMatching(ag) => {
            let result = fnx_algorithms::maximal_matching(&ag.graph);
            assert_valid_matching(&ag.graph, &result.matching, "maximal_matching");
            // Sanity-check round-trip: the result must satisfy is_matching
            // and is_maximal_matching by definition.
            assert!(
                fnx_algorithms::is_matching(&ag.graph, &result.matching),
                "maximal_matching output failed is_matching check"
            );
            assert!(
                fnx_algorithms::is_maximal_matching(&ag.graph, &result.matching),
                "maximal_matching output failed is_maximal_matching check"
            );
        }
        MatchingInput::MaxWeightMatching(ag) => {
            // Signature: (graph, maxcardinality, weight_attr)
            let result = fnx_algorithms::max_weight_matching(&ag.graph, true, &ag.weight_attr);
            assert_valid_matching(&ag.graph, &result.matching, "max_weight_matching");
            // total_weight must be finite (NaN/inf would be a bug).
            assert!(
                result.total_weight.is_finite(),
                "max_weight_matching total_weight {} is not finite",
                result.total_weight
            );
        }
        MatchingInput::MinWeightMatching(ag) => {
            let result = fnx_algorithms::min_weight_matching(&ag.graph, &ag.weight_attr);
            assert_valid_matching(&ag.graph, &result.matching, "min_weight_matching");
            assert!(
                result.total_weight.is_finite(),
                "min_weight_matching total_weight {} is not finite",
                result.total_weight
            );
        }
        MatchingInput::ValidateMatching(ag) => {
            // First compute a matching, then validate it.
            let result = fnx_algorithms::maximal_matching(&ag.graph);
            let matching: Vec<(String, String)> = result
                .matching
                .iter()
                .map(|(a, b)| (a.clone(), b.clone()))
                .collect();
            // Cross-check: the maximal_matching output must be a valid
            // matching according to the predicate.
            assert!(
                fnx_algorithms::is_matching(&ag.graph, &matching),
                "is_matching disagrees with maximal_matching constructor"
            );
            assert!(
                fnx_algorithms::is_maximal_matching(&ag.graph, &matching),
                "is_maximal_matching disagrees with maximal_matching constructor"
            );
            // Perfect matching iff every node is covered (2 * |M| == n).
            let perfect = fnx_algorithms::is_perfect_matching(&ag.graph, &matching);
            let expected_perfect = 2 * matching.len() == ag.graph.node_count();
            assert_eq!(
                perfect, expected_perfect,
                "is_perfect_matching ({}) disagrees with 2*|M|==n ({})",
                perfect, expected_perfect
            );
        }
    }
});
