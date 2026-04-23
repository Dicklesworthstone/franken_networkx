//! Structure-aware fuzzer for matching algorithms.
//!
//! Tests maximal matching, max weight matching, and matching validation
//! on valid-but-pathological graph structures.

#![no_main]

mod arbitrary_graph;

use arbitrary::Arbitrary;
use arbitrary_graph::{ArbitraryGraph, ArbitraryWeightedGraph};
use libfuzzer_sys::fuzz_target;

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
            let _ = fnx_algorithms::maximal_matching(&ag.graph);
        }
        MatchingInput::MaxWeightMatching(ag) => {
            // Signature: (graph, maxcardinality, weight_attr)
            let _ = fnx_algorithms::max_weight_matching(&ag.graph, true, &ag.weight_attr);
        }
        MatchingInput::MinWeightMatching(ag) => {
            let _ = fnx_algorithms::min_weight_matching(&ag.graph, &ag.weight_attr);
        }
        MatchingInput::ValidateMatching(ag) => {
            // First compute a matching, then validate it
            let result = fnx_algorithms::maximal_matching(&ag.graph);
            let matching: Vec<(String, String)> = result
                .matching
                .iter()
                .map(|(a, b)| (a.clone(), b.clone()))
                .collect();
            let _ = fnx_algorithms::is_matching(&ag.graph, &matching);
            let _ = fnx_algorithms::is_maximal_matching(&ag.graph, &matching);
            let _ = fnx_algorithms::is_perfect_matching(&ag.graph, &matching);
        }
    }
});
