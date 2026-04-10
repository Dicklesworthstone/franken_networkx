//! CGSE Adversarial Tie-Break Corpus Tests
//!
//! This module validates that all 12 CGSE reference algorithms produce
//! deterministic witness hashes when processing graphs with tie-break scenarios.
//! Each test case forces the algorithm to make ordering decisions, and we verify
//! that the decision path hash is stable across multiple runs.

use fnx_algorithms::{
    bellman_ford_shortest_paths, bfs_edges, connected_components, dfs_edges, eulerian_circuit,
    max_weight_matching, min_weight_matching, minimum_spanning_tree, minimum_spanning_tree_prim,
    multi_source_dijkstra, strongly_connected_components, topological_sort,
};
use fnx_cgse::{ComplexityWitness, ReferenceAlgorithm, TieBreakPolicy, collect_witnesses};
use fnx_classes::digraph::DiGraph;
use fnx_classes::{AttrMap, Graph};
use fnx_runtime::CgseValue;
use serde::Deserialize;
use std::collections::{BTreeMap, HashMap};
use std::fs;
use std::path::PathBuf;

#[allow(dead_code)]
#[derive(Debug, Deserialize)]
struct AdversarialCorpus {
    schema_version: String,
    test_cases: Vec<TestCase>,
    determinism_invariants: Vec<DeterminismInvariant>,
}

#[allow(dead_code)]
#[derive(Debug, Deserialize)]
struct TestCase {
    case_id: String,
    algorithm: String,
    policy: String,
    description: String,
    graph: GraphSpec,
    #[serde(default)]
    query: HashMap<String, String>,
    expected_witness_property: String,
    adversarial_property: String,
}

#[allow(dead_code)]
#[derive(Debug, Deserialize)]
struct GraphSpec {
    directed: bool,
    nodes: Vec<String>,
    edges: Vec<EdgeSpec>,
}

#[derive(Debug, Deserialize)]
struct EdgeSpec {
    u: String,
    v: String,
    #[serde(default)]
    weight: Option<f64>,
}

#[allow(dead_code)]
#[derive(Debug, Deserialize)]
struct DeterminismInvariant {
    invariant_id: String,
    description: String,
    verification: String,
}

fn corpus_path() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("fixtures/cgse_adversarial_tiebreak_corpus_v1.json")
}

fn load_corpus() -> AdversarialCorpus {
    let content = fs::read_to_string(corpus_path()).expect("adversarial corpus file should exist");
    serde_json::from_str(&content).expect("corpus should parse as valid JSON")
}

fn build_undirected_graph(spec: &GraphSpec) -> Graph {
    let mut g = Graph::strict();
    for node in &spec.nodes {
        g.add_node(node);
    }
    for edge in &spec.edges {
        if let Some(w) = edge.weight {
            let mut attrs: AttrMap = BTreeMap::new();
            attrs.insert("weight".to_string(), CgseValue::Float(w));
            let _ = g.add_edge_with_attrs(&edge.u, &edge.v, attrs);
        } else {
            let _ = g.add_edge(&edge.u, &edge.v);
        }
    }
    g
}

fn build_directed_graph(spec: &GraphSpec) -> DiGraph {
    let mut g = DiGraph::strict();
    for node in &spec.nodes {
        g.add_node(node);
    }
    for edge in &spec.edges {
        if let Some(w) = edge.weight {
            let mut attrs: AttrMap = BTreeMap::new();
            attrs.insert("weight".to_string(), CgseValue::Float(w));
            let _ = g.add_edge_with_attrs(&edge.u, &edge.v, attrs);
        } else {
            let _ = g.add_edge(&edge.u, &edge.v);
        }
    }
    g
}

fn run_algorithm_and_get_witnesses(case: &TestCase) -> Vec<ComplexityWitness> {
    let (_, witnesses) = collect_witnesses(|| match case.algorithm.as_str() {
        "dijkstra" => {
            let g = build_undirected_graph(&case.graph);
            let source = case.query.get("source").map(|s| s.as_str()).unwrap_or("a");
            let _ = multi_source_dijkstra(&g, &[source], "weight");
        }
        "bellman_ford" => {
            let g = build_undirected_graph(&case.graph);
            let source = case.query.get("source").map(|s| s.as_str()).unwrap_or("s");
            let _ = bellman_ford_shortest_paths(&g, source, "weight");
        }
        "bfs" => {
            let g = build_undirected_graph(&case.graph);
            let source = case
                .query
                .get("source")
                .map(|s| s.as_str())
                .unwrap_or("root");
            let _ = bfs_edges(&g, source, None);
        }
        "dfs" => {
            let g = build_undirected_graph(&case.graph);
            let source = case
                .query
                .get("source")
                .map(|s| s.as_str())
                .unwrap_or("root");
            let _ = dfs_edges(&g, source, None);
        }
        "connected_components" => {
            let g = build_undirected_graph(&case.graph);
            let _ = connected_components(&g);
        }
        "strongly_connected_components" => {
            let g = build_directed_graph(&case.graph);
            let _ = strongly_connected_components(&g);
        }
        "kruskal" => {
            let g = build_undirected_graph(&case.graph);
            let _ = minimum_spanning_tree(&g, "weight");
        }
        "prim" => {
            let g = build_undirected_graph(&case.graph);
            let _ = minimum_spanning_tree_prim(&g, "weight");
        }
        "max_weight_matching" => {
            let g = build_undirected_graph(&case.graph);
            let _ = max_weight_matching(&g, true, "weight");
        }
        "min_weight_matching" => {
            let g = build_undirected_graph(&case.graph);
            let _ = min_weight_matching(&g, "weight");
        }
        "eulerian_circuit" => {
            let g = build_undirected_graph(&case.graph);
            let _ = eulerian_circuit(&g, None);
        }
        "topological_sort" => {
            let g = build_directed_graph(&case.graph);
            let _ = topological_sort(&g);
        }
        other => panic!("Unknown algorithm in corpus: {}", other),
    });
    witnesses
}

#[test]
fn cgse_adversarial_corpus_loads_successfully() {
    let corpus = load_corpus();
    assert_eq!(corpus.schema_version, "1.0.0");
    assert!(
        !corpus.test_cases.is_empty(),
        "corpus should have test cases"
    );
    assert!(
        corpus.test_cases.len() >= 12,
        "corpus should cover all 12 reference algorithms"
    );
}

#[test]
fn cgse_adversarial_corpus_covers_all_reference_algorithms() {
    let corpus = load_corpus();
    let mut covered: std::collections::HashSet<&str> = std::collections::HashSet::new();
    for case in &corpus.test_cases {
        covered.insert(&case.algorithm);
    }

    let expected = [
        "dijkstra",
        "bellman_ford",
        "bfs",
        "dfs",
        "connected_components",
        "strongly_connected_components",
        "kruskal",
        "prim",
        "max_weight_matching",
        "min_weight_matching",
        "eulerian_circuit",
        "topological_sort",
    ];

    for alg in expected {
        assert!(
            covered.contains(alg),
            "corpus should include test case for algorithm: {}",
            alg
        );
    }
}

#[test]
fn cgse_adversarial_witness_determinism_dijkstra() {
    let corpus = load_corpus();
    for case in corpus
        .test_cases
        .iter()
        .filter(|c| c.algorithm == "dijkstra")
    {
        verify_witness_determinism(case, 10);
    }
}

#[test]
fn cgse_adversarial_witness_determinism_bellman_ford() {
    let corpus = load_corpus();
    for case in corpus
        .test_cases
        .iter()
        .filter(|c| c.algorithm == "bellman_ford")
    {
        verify_witness_determinism(case, 10);
    }
}

#[test]
fn cgse_adversarial_witness_determinism_bfs() {
    let corpus = load_corpus();
    for case in corpus.test_cases.iter().filter(|c| c.algorithm == "bfs") {
        verify_witness_determinism(case, 10);
    }
}

#[test]
fn cgse_adversarial_witness_determinism_dfs() {
    let corpus = load_corpus();
    for case in corpus.test_cases.iter().filter(|c| c.algorithm == "dfs") {
        verify_witness_determinism(case, 10);
    }
}

#[test]
fn cgse_adversarial_witness_determinism_connected_components() {
    let corpus = load_corpus();
    for case in corpus
        .test_cases
        .iter()
        .filter(|c| c.algorithm == "connected_components")
    {
        verify_witness_determinism(case, 10);
    }
}

#[test]
fn cgse_adversarial_witness_determinism_strongly_connected() {
    let corpus = load_corpus();
    for case in corpus
        .test_cases
        .iter()
        .filter(|c| c.algorithm == "strongly_connected_components")
    {
        verify_witness_determinism(case, 10);
    }
}

#[test]
fn cgse_adversarial_witness_determinism_kruskal() {
    let corpus = load_corpus();
    for case in corpus
        .test_cases
        .iter()
        .filter(|c| c.algorithm == "kruskal")
    {
        verify_witness_determinism(case, 10);
    }
}

#[test]
fn cgse_adversarial_witness_determinism_prim() {
    let corpus = load_corpus();
    for case in corpus.test_cases.iter().filter(|c| c.algorithm == "prim") {
        verify_witness_determinism(case, 10);
    }
}

#[test]
fn cgse_adversarial_witness_determinism_max_weight_matching() {
    let corpus = load_corpus();
    for case in corpus
        .test_cases
        .iter()
        .filter(|c| c.algorithm == "max_weight_matching")
    {
        verify_witness_determinism(case, 10);
    }
}

#[test]
fn cgse_adversarial_witness_determinism_min_weight_matching() {
    let corpus = load_corpus();
    for case in corpus
        .test_cases
        .iter()
        .filter(|c| c.algorithm == "min_weight_matching")
    {
        verify_witness_determinism(case, 10);
    }
}

#[test]
fn cgse_adversarial_witness_determinism_eulerian() {
    let corpus = load_corpus();
    for case in corpus
        .test_cases
        .iter()
        .filter(|c| c.algorithm == "eulerian_circuit")
    {
        verify_witness_determinism(case, 10);
    }
}

#[test]
fn cgse_adversarial_witness_determinism_topological() {
    let corpus = load_corpus();
    for case in corpus
        .test_cases
        .iter()
        .filter(|c| c.algorithm == "topological_sort")
    {
        verify_witness_determinism(case, 10);
    }
}

fn verify_witness_determinism(case: &TestCase, iterations: usize) {
    let mut hashes: Vec<[u8; 32]> = Vec::with_capacity(iterations);

    for _ in 0..iterations {
        let witnesses = run_algorithm_and_get_witnesses(case);
        if !witnesses.is_empty() {
            hashes.push(witnesses[0].decision_path_blake3);
        }
    }

    if hashes.len() > 1 {
        let first_hash = &hashes[0];
        for (i, hash) in hashes.iter().enumerate().skip(1) {
            assert_eq!(
                hash, first_hash,
                "Case '{}': witness hash at iteration {} differs from iteration 0. \
                 Algorithm '{}' is non-deterministic on adversarial input.",
                case.case_id, i, case.algorithm
            );
        }
    }
}

#[test]
fn cgse_adversarial_all_cases_emit_witnesses_when_collection_enabled() {
    let corpus = load_corpus();
    for case in &corpus.test_cases {
        let witnesses = run_algorithm_and_get_witnesses(case);
        assert!(
            !witnesses.is_empty(),
            "Case '{}' (algorithm '{}') should emit at least one witness when collection is enabled",
            case.case_id,
            case.algorithm
        );
    }
}

#[test]
fn cgse_adversarial_policy_matches_algorithm() {
    let corpus = load_corpus();
    for case in &corpus.test_cases {
        let ref_alg = ReferenceAlgorithm::from_algorithm_id(&case.algorithm)
            .unwrap_or_else(|| panic!("Unknown algorithm: {}", case.algorithm));

        let expected_policy = match case.policy.as_str() {
            "weight_then_lex" => TieBreakPolicy::WeightThenLex,
            "insertion_order" => TieBreakPolicy::InsertionOrder,
            "lex_min" => TieBreakPolicy::LexMin,
            other => panic!("Unknown policy in corpus: {}", other),
        };

        assert_eq!(
            ref_alg.policy(),
            expected_policy,
            "Case '{}': algorithm '{}' should have policy '{}'",
            case.case_id,
            case.algorithm,
            case.policy
        );
    }
}
