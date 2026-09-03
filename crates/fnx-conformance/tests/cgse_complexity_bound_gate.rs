//! CGSE complexity-bound gate (reality-check bead rc-cgse-bound-ci-job-slls9).
//!
//! For each of the 12 V1 reference algorithms this gate asserts, at the Rust
//! level where every reference kernel is instrumented (`cgse_begin` sites in
//! `fnx-algorithms`):
//!
//! 1. **Emission** — running the algorithm under `collect_witnesses` yields
//!    at least one `ComplexityWitness` (a kernel that stops emitting breaks
//!    the witness contract silently otherwise).
//! 2. **Registry agreement** — the witness's `dominant_term` and `policy`
//!    match the pinned `v1_policy_registry()` entry for that algorithm.
//! 3. **Recognized term** — `analytic_upper_bound` returns `Some` for the
//!    witness's dominant term (a typo'd term silently disables all bound
//!    checks; this makes that failure loud).
//! 4. **Bound** — `assert_complexity_within_bounds` accepts the observed
//!    operation count (the actual complexity-regression tripwire; the helper
//!    allows the documented 2x constant-factor headroom).
//! 5. **Determinism** — two runs on identical fresh graphs produce identical
//!    `decision_path_blake3` hashes (ordering drift = different hash).
//! 6. **Negative case** — an artificially inflated `observed_count` must be
//!    rejected by `verify_complexity_bound` and must panic inside
//!    `assert_complexity_within_bounds`, proving the gate can fail.

use fnx_algorithms::{
    bellman_ford_shortest_paths, bfs_edges, connected_components, dfs_edges, eulerian_circuit,
    max_weight_matching, min_weight_matching, minimum_spanning_tree, minimum_spanning_tree_prim,
    multi_source_dijkstra, number_strongly_connected_components, topological_sort,
};
use fnx_cgse::{
    AlgorithmFamilyPolicy, ComplexityWitness, ReferenceAlgorithm, TieBreakPolicy,
    analytic_upper_bound, assert_complexity_within_bounds, collect_witnesses, v1_policy_registry,
    verify_complexity_bound,
};
use fnx_classes::digraph::DiGraph;
use fnx_classes::{AttrMap, Graph};
use fnx_runtime::CompatibilityMode;

const N: usize = 12;

/// Connected 2-regular ring: every node has even degree (eulerian) and the
/// graph is simple, connected, and unweighted.
fn ring() -> Graph {
    let mut g = Graph::new(CompatibilityMode::Strict);
    for i in 0..N {
        let _ = g.add_node(i.to_string());
    }
    for i in 0..N {
        g.add_edge(i.to_string(), ((i + 1) % N).to_string())
            .expect("ring edge insert");
    }
    g
}

/// Same ring with `weight` attributes on every edge (for the weighted
/// kernels: Dijkstra, Bellman-Ford, matching, MST).
fn weighted_ring() -> Graph {
    let mut g = ring();
    let edges: Vec<(String, String)> = (0..N)
        .map(|i| (i.to_string(), ((i + 1) % N).to_string()))
        .collect();
    for (u, v) in edges {
        let mut attrs = AttrMap::new();
        attrs.insert("weight".to_owned(), fnx_runtime::CgseValue::Float(1.0));
        g.add_edge_with_attrs(u, v, attrs)
            .expect("weighted ring edge insert");
    }
    g
}

/// Forward-only DAG: path 0→1→…→11 plus forward chords 0→5 and 2→9.
fn dag() -> DiGraph {
    let mut d = DiGraph::new(CompatibilityMode::Strict);
    for i in 0..N {
        let _ = d.add_node(i.to_string());
    }
    for i in 0..N - 1 {
        d.add_edge(i.to_string(), (i + 1).to_string())
            .expect("dag edge insert");
    }
    d.add_edge("0", "5").expect("dag chord insert");
    d.add_edge("2", "9").expect("dag chord insert");
    d
}

fn registry_entry(algorithm: &str) -> AlgorithmFamilyPolicy {
    v1_policy_registry()
        .into_iter()
        .find(|entry| entry.algorithm == algorithm)
        .unwrap_or_else(|| panic!("v1 policy registry missing entry for `{algorithm}`"))
}

fn assert_witness_contract(entry: &AlgorithmFamilyPolicy, witness: &ComplexityWitness) {
    assert!(
        analytic_upper_bound(&witness.dominant_term, witness.n, witness.m).is_some(),
        "{}: witness dominant term `{}` is not a recognized complexity class — \
         an unrecognized term silently disables every bound check",
        entry.algorithm,
        witness.dominant_term
    );
    assert_eq!(
        witness.dominant_term, entry.dominant_complexity,
        "{}: witness dominant term drifted from the pinned registry entry",
        entry.algorithm
    );
    assert_eq!(
        &witness.policy, &entry.policy,
        "{}: witness tie-break policy drifted from the pinned registry entry",
        entry.algorithm
    );
    assert_complexity_within_bounds(witness);
}

/// Runs `emit` twice on fresh graphs; asserts both runs emit witnesses that
/// satisfy the full contract, and that the decision-path hashes agree.
fn gate<F>(algorithm: &str, emit: F)
where
    F: Fn() -> Vec<ComplexityWitness>,
{
    let entry = registry_entry(algorithm);

    let first = emit();
    assert!(
        !first.is_empty(),
        "{algorithm}: no ComplexityWitness emitted — the reference kernel's \
         cgse instrumentation is disconnected on this route"
    );
    for witness in &first {
        assert_witness_contract(&entry, witness);
    }

    let second = emit();
    assert!(
        !second.is_empty(),
        "{algorithm}: second run emitted nothing"
    );
    let hashes_match = first
        .iter()
        .zip(second.iter())
        .all(|(a, b)| a.decision_path_blake3 == b.decision_path_blake3);
    assert!(
        hashes_match,
        "{algorithm}: decision_path_blake3 differs across two identical runs — \
         non-determinism leak in tie-break ordering"
    );
}

#[test]
fn all_twelve_reference_algorithms_emit_witnesses_within_bounds() {
    gate("dijkstra", || {
        let (_result, witnesses) =
            collect_witnesses(|| multi_source_dijkstra(&weighted_ring(), &["0"], "weight"));
        witnesses
    });

    gate("bellman_ford", || {
        let (_result, witnesses) =
            collect_witnesses(|| bellman_ford_shortest_paths(&weighted_ring(), "0", "weight"));
        witnesses
    });

    gate("bfs", || {
        let (_, witnesses) = collect_witnesses(|| bfs_edges(&ring(), "0", None));
        witnesses
    });

    gate("dfs", || {
        let (_, witnesses) = collect_witnesses(|| dfs_edges(&ring(), "0", None));
        witnesses
    });

    gate("max_weight_matching", || {
        let (_, witnesses) =
            collect_witnesses(|| max_weight_matching(&weighted_ring(), false, "weight"));
        witnesses
    });

    gate("min_weight_matching", || {
        let (_, witnesses) = collect_witnesses(|| min_weight_matching(&weighted_ring(), "weight"));
        witnesses
    });

    gate("connected_components", || {
        let (_, witnesses) = collect_witnesses(|| connected_components(&ring()));
        witnesses
    });

    gate("strongly_connected_components", || {
        let (_, witnesses) = collect_witnesses(|| number_strongly_connected_components(&dag()));
        witnesses
    });

    gate("kruskal", || {
        let (_, witnesses) =
            collect_witnesses(|| minimum_spanning_tree(&weighted_ring(), "weight"));
        witnesses
    });

    gate("prim", || {
        let (_, witnesses) =
            collect_witnesses(|| minimum_spanning_tree_prim(&weighted_ring(), "weight"));
        witnesses
    });

    gate("eulerian_circuit", || {
        let (_, witnesses) = collect_witnesses(|| eulerian_circuit(&ring(), Some("0")));
        witnesses
    });

    gate("topological_sort", || {
        let (_, witnesses) = collect_witnesses(|| topological_sort(&dag()));
        witnesses
    });
}

/// The registry must stay exactly the V1 dozen — a registry entry without a
/// gated kernel, or a gated kernel without a registry entry, is contract
/// drift.
#[test]
fn registry_pins_exactly_the_v1_dozen() {
    let registry = v1_policy_registry();
    assert_eq!(registry.len(), ReferenceAlgorithm::ALL.len());
    for known in ReferenceAlgorithm::ALL {
        // Registry keys are snake_case; Debug gives CamelCase compound words.
        let name = match known {
            ReferenceAlgorithm::BellmanFord => "bellman_ford".to_owned(),
            ReferenceAlgorithm::MaxWeightMatching => "max_weight_matching".to_owned(),
            ReferenceAlgorithm::MinWeightMatching => "min_weight_matching".to_owned(),
            ReferenceAlgorithm::ConnectedComponents => "connected_components".to_owned(),
            ReferenceAlgorithm::StronglyConnectedComponents => {
                "strongly_connected_components".to_owned()
            }
            ReferenceAlgorithm::EulerianCircuit => "eulerian_circuit".to_owned(),
            ReferenceAlgorithm::TopologicalSort => "topological_sort".to_owned(),
            other => format!("{other:?}").to_lowercase(),
        };
        assert!(
            registry.iter().any(|entry| entry.algorithm == name),
            "registry missing reference algorithm `{name}`"
        );
    }
}

/// Negative case: an inflated operation count must be REJECTED. Without this
/// check a bound helper that silently accepts everything would pass the gate
/// above while protecting nothing.
#[test]
fn inflated_observed_count_is_rejected() {
    let entry = registry_entry("bfs");
    let (_result, witnesses) = collect_witnesses(|| bfs_edges(&ring(), "0", None));
    let mut witness = witnesses
        .first()
        .expect("bfs should emit a witness for the positive case")
        .clone();
    witness.observed_count = u64::MAX / 2;

    let verdict = verify_complexity_bound(&witness)
        .expect("recognized dominant term must produce a bound verdict");
    assert!(
        !verdict.within_bounds,
        "inflated observed_count {} passed the bound check (upper {}) — \
         the complexity gate is a no-op",
        verdict.observed_count, verdict.upper_bound
    );

    let panicked = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| {
        assert_complexity_within_bounds(&witness);
    }))
    .is_err();
    assert!(
        panicked,
        "assert_complexity_within_bounds must panic on a bound violation"
    );

    // Silence the unused warning path for the policy field access used above.
    let _policy_guard: Option<&TieBreakPolicy> = None;
    let _ = &entry;
}
