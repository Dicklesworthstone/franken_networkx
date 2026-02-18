#![forbid(unsafe_code)]

use fnx_classes::Graph;
use serde::{Deserialize, Serialize};
use std::collections::{HashMap, HashSet, VecDeque};

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ComplexityWitness {
    pub algorithm: String,
    pub complexity_claim: String,
    pub nodes_touched: usize,
    pub edges_scanned: usize,
    pub queue_peak: usize,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ShortestPathResult {
    pub path: Option<Vec<String>>,
    pub witness: ComplexityWitness,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ComponentsResult {
    pub components: Vec<Vec<String>>,
    pub witness: ComplexityWitness,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct NumberConnectedComponentsResult {
    pub count: usize,
    pub witness: ComplexityWitness,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct CentralityScore {
    pub node: String,
    pub score: f64,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct DegreeCentralityResult {
    pub scores: Vec<CentralityScore>,
    pub witness: ComplexityWitness,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct ClosenessCentralityResult {
    pub scores: Vec<CentralityScore>,
    pub witness: ComplexityWitness,
}

#[must_use]
pub fn shortest_path_unweighted(graph: &Graph, source: &str, target: &str) -> ShortestPathResult {
    if !graph.has_node(source) || !graph.has_node(target) {
        return ShortestPathResult {
            path: None,
            witness: ComplexityWitness {
                algorithm: "bfs_shortest_path".to_owned(),
                complexity_claim: "O(|V| + |E|)".to_owned(),
                nodes_touched: 0,
                edges_scanned: 0,
                queue_peak: 0,
            },
        };
    }

    if source == target {
        return ShortestPathResult {
            path: Some(vec![source.to_owned()]),
            witness: ComplexityWitness {
                algorithm: "bfs_shortest_path".to_owned(),
                complexity_claim: "O(|V| + |E|)".to_owned(),
                nodes_touched: 1,
                edges_scanned: 0,
                queue_peak: 1,
            },
        };
    }

    let mut visited: HashSet<&str> = HashSet::new();
    let mut predecessor: HashMap<&str, &str> = HashMap::new();
    let mut queue: VecDeque<&str> = VecDeque::new();

    visited.insert(source);
    queue.push_back(source);

    let mut nodes_touched = 1;
    let mut edges_scanned = 0;
    let mut queue_peak = 1;

    while let Some(current) = queue.pop_front() {
        let Some(neighbors) = graph.neighbors_iter(current) else {
            continue;
        };

        for neighbor in neighbors {
            edges_scanned += 1;
            if !visited.insert(neighbor) {
                continue;
            }
            predecessor.insert(neighbor, current);
            queue.push_back(neighbor);
            nodes_touched += 1;
            queue_peak = queue_peak.max(queue.len());

            if neighbor == target {
                let path = rebuild_path(&predecessor, source, target);
                return ShortestPathResult {
                    path: Some(path),
                    witness: ComplexityWitness {
                        algorithm: "bfs_shortest_path".to_owned(),
                        complexity_claim: "O(|V| + |E|)".to_owned(),
                        nodes_touched,
                        edges_scanned,
                        queue_peak,
                    },
                };
            }
        }
    }

    ShortestPathResult {
        path: None,
        witness: ComplexityWitness {
            algorithm: "bfs_shortest_path".to_owned(),
            complexity_claim: "O(|V| + |E|)".to_owned(),
            nodes_touched,
            edges_scanned,
            queue_peak,
        },
    }
}

#[must_use]
pub fn connected_components(graph: &Graph) -> ComponentsResult {
    let mut visited: HashSet<&str> = HashSet::new();
    let mut components = Vec::new();
    let mut nodes_touched = 0usize;
    let mut edges_scanned = 0usize;
    let mut queue_peak = 0usize;

    for node in graph.nodes_ordered() {
        if visited.contains(node) {
            continue;
        }

        let mut queue: VecDeque<&str> = VecDeque::new();
        let mut component = Vec::new();
        queue.push_back(node);
        visited.insert(node);
        component.push(node);
        nodes_touched += 1;
        queue_peak = queue_peak.max(queue.len());

        while let Some(current) = queue.pop_front() {
            let Some(neighbors) = graph.neighbors_iter(current) else {
                continue;
            };

            for neighbor in neighbors {
                edges_scanned += 1;
                if visited.insert(neighbor) {
                    queue.push_back(neighbor);
                    component.push(neighbor);
                    nodes_touched += 1;
                    queue_peak = queue_peak.max(queue.len());
                }
            }
        }

        component.sort_unstable();
        components.push(component.into_iter().map(str::to_owned).collect());
    }

    ComponentsResult {
        components,
        witness: ComplexityWitness {
            algorithm: "bfs_connected_components".to_owned(),
            complexity_claim: "O(|V| + |E|)".to_owned(),
            nodes_touched,
            edges_scanned,
            queue_peak,
        },
    }
}

#[must_use]
pub fn number_connected_components(graph: &Graph) -> NumberConnectedComponentsResult {
    let components = connected_components(graph);
    NumberConnectedComponentsResult {
        count: components.components.len(),
        witness: ComplexityWitness {
            algorithm: "bfs_number_connected_components".to_owned(),
            complexity_claim: components.witness.complexity_claim,
            nodes_touched: components.witness.nodes_touched,
            edges_scanned: components.witness.edges_scanned,
            queue_peak: components.witness.queue_peak,
        },
    }
}

#[must_use]
pub fn degree_centrality(graph: &Graph) -> DegreeCentralityResult {
    let nodes = graph.nodes_ordered();
    let n = nodes.len();
    if n == 0 {
        return DegreeCentralityResult {
            scores: Vec::new(),
            witness: ComplexityWitness {
                algorithm: "degree_centrality".to_owned(),
                complexity_claim: "O(|V| + |E|)".to_owned(),
                nodes_touched: 0,
                edges_scanned: 0,
                queue_peak: 0,
            },
        };
    }

    let denominator = if n <= 1 { 1.0 } else { (n - 1) as f64 };
    let mut edges_scanned = 0usize;
    let mut scores = Vec::with_capacity(n);
    for node in nodes {
        let neighbor_count = graph.neighbor_count(node);
        // A self-loop contributes 2 to degree in simple NetworkX Graph semantics.
        let self_loop_extra = usize::from(graph.has_edge(node, node));
        let degree = neighbor_count + self_loop_extra;
        edges_scanned += degree;
        let score = if n == 1 && degree == 0 {
            1.0
        } else {
            (degree as f64) / denominator
        };
        scores.push(CentralityScore {
            node: node.to_owned(),
            score,
        });
    }

    DegreeCentralityResult {
        scores,
        witness: ComplexityWitness {
            algorithm: "degree_centrality".to_owned(),
            complexity_claim: "O(|V| + |E|)".to_owned(),
            nodes_touched: n,
            edges_scanned,
            queue_peak: 0,
        },
    }
}

#[must_use]
pub fn closeness_centrality(graph: &Graph) -> ClosenessCentralityResult {
    let nodes = graph.nodes_ordered();
    let n = nodes.len();
    if n == 0 {
        return ClosenessCentralityResult {
            scores: Vec::new(),
            witness: ComplexityWitness {
                algorithm: "closeness_centrality".to_owned(),
                complexity_claim: "O(|V| * (|V| + |E|))".to_owned(),
                nodes_touched: 0,
                edges_scanned: 0,
                queue_peak: 0,
            },
        };
    }

    let mut scores = Vec::with_capacity(n);
    let mut nodes_touched = 0usize;
    let mut edges_scanned = 0usize;
    let mut queue_peak = 0usize;

    for source in &nodes {
        let mut queue: VecDeque<&str> = VecDeque::new();
        let mut distance: HashMap<&str, usize> = HashMap::new();
        queue.push_back(*source);
        distance.insert(*source, 0usize);
        queue_peak = queue_peak.max(queue.len());

        while let Some(current) = queue.pop_front() {
            let Some(neighbors) = graph.neighbors_iter(current) else {
                continue;
            };
            let current_distance = *distance.get(&current).unwrap_or(&0usize);
            for neighbor in neighbors {
                edges_scanned += 1;
                if distance.contains_key(neighbor) {
                    continue;
                }
                distance.insert(neighbor, current_distance + 1);
                queue.push_back(neighbor);
                queue_peak = queue_peak.max(queue.len());
            }
        }

        let reachable = distance.len();
        nodes_touched += reachable;
        let total_distance: usize = distance.values().sum();
        let score = if reachable <= 1 || total_distance == 0 {
            0.0
        } else {
            let reachable_minus_one = (reachable - 1) as f64;
            let mut closeness = reachable_minus_one / (total_distance as f64);
            if n > 1 {
                closeness *= reachable_minus_one / ((n - 1) as f64);
            }
            closeness
        };
        scores.push(CentralityScore {
            node: (*source).to_owned(),
            score,
        });
    }

    ClosenessCentralityResult {
        scores,
        witness: ComplexityWitness {
            algorithm: "closeness_centrality".to_owned(),
            complexity_claim: "O(|V| * (|V| + |E|))".to_owned(),
            nodes_touched,
            edges_scanned,
            queue_peak,
        },
    }
}

fn rebuild_path(predecessor: &HashMap<&str, &str>, source: &str, target: &str) -> Vec<String> {
    let mut path = vec![target.to_owned()];
    let mut cursor = target;

    while cursor != source {
        let Some(prev) = predecessor.get(cursor) else {
            break;
        };
        path.push((*prev).to_owned());
        cursor = prev;
    }

    path.reverse();
    path
}

#[cfg(test)]
mod tests {
    use super::{
        closeness_centrality, connected_components, degree_centrality, number_connected_components,
        shortest_path_unweighted,
    };
    use fnx_classes::Graph;
    use fnx_runtime::{
        CompatibilityMode, ForensicsBundleIndex, StructuredTestLog, TestKind, TestStatus,
        canonical_environment_fingerprint, structured_test_log_schema_version,
    };
    use proptest::prelude::*;
    use std::collections::{BTreeMap, BTreeSet};

    fn packet_005_forensics_bundle(
        run_id: &str,
        test_id: &str,
        replay_ref: &str,
        bundle_id: &str,
        artifact_refs: Vec<String>,
    ) -> ForensicsBundleIndex {
        ForensicsBundleIndex {
            bundle_id: bundle_id.to_owned(),
            run_id: run_id.to_owned(),
            test_id: test_id.to_owned(),
            bundle_hash_id: "bundle-hash-p2c005".to_owned(),
            captured_unix_ms: 1,
            replay_ref: replay_ref.to_owned(),
            artifact_refs,
            raptorq_sidecar_refs: Vec::new(),
            decode_proof_refs: Vec::new(),
        }
    }

    fn canonical_edge_pairs(graph: &Graph) -> Vec<(String, String)> {
        let mut edges = BTreeSet::new();
        for node in graph.nodes_ordered() {
            let Some(neighbors) = graph.neighbors_iter(node) else {
                continue;
            };
            for neighbor in neighbors {
                let (left, right) = if node <= neighbor {
                    (node.to_owned(), neighbor.to_owned())
                } else {
                    (neighbor.to_owned(), node.to_owned())
                };
                edges.insert((left, right));
            }
        }
        edges.into_iter().collect()
    }

    fn graph_fingerprint(graph: &Graph) -> String {
        let nodes = graph
            .nodes_ordered()
            .into_iter()
            .map(str::to_owned)
            .collect::<Vec<String>>();
        let edge_signature = canonical_edge_pairs(graph)
            .into_iter()
            .map(|(left, right)| format!("{left}>{right}"))
            .collect::<Vec<String>>()
            .join("|");
        format!(
            "nodes:{};edges:{};sig:{edge_signature}",
            nodes.join(","),
            canonical_edge_pairs(graph).len()
        )
    }

    #[test]
    fn bfs_shortest_path_uses_deterministic_neighbor_order() {
        let mut graph = Graph::strict();
        graph.add_edge("a", "b").expect("edge add should succeed");
        graph.add_edge("a", "c").expect("edge add should succeed");
        graph.add_edge("b", "d").expect("edge add should succeed");
        graph.add_edge("c", "d").expect("edge add should succeed");

        let result = shortest_path_unweighted(&graph, "a", "d");
        assert_eq!(
            result.path,
            Some(vec!["a", "b", "d"].into_iter().map(str::to_owned).collect())
        );
        assert_eq!(result.witness.algorithm, "bfs_shortest_path");
        assert_eq!(result.witness.complexity_claim, "O(|V| + |E|)");
    }

    #[test]
    fn returns_none_when_nodes_are_missing() {
        let graph = Graph::strict();
        let result = shortest_path_unweighted(&graph, "a", "b");
        assert_eq!(result.path, None);
    }

    #[test]
    fn connected_components_are_deterministic_and_partitioned() {
        let mut graph = Graph::strict();
        graph.add_edge("a", "b").expect("edge add should succeed");
        graph.add_edge("d", "e").expect("edge add should succeed");
        graph.add_edge("c", "d").expect("edge add should succeed");

        let result = connected_components(&graph);
        assert_eq!(
            result.components,
            vec![
                vec!["a".to_owned(), "b".to_owned()],
                vec!["c".to_owned(), "d".to_owned(), "e".to_owned()]
            ]
        );
        assert_eq!(result.witness.algorithm, "bfs_connected_components");
    }

    #[test]
    fn connected_components_include_isolated_nodes() {
        let mut graph = Graph::strict();
        let _ = graph.add_node("solo");
        graph.add_edge("x", "y").expect("edge add should succeed");

        let result = connected_components(&graph);
        assert_eq!(
            result.components,
            vec![
                vec!["solo".to_owned()],
                vec!["x".to_owned(), "y".to_owned()]
            ]
        );
    }

    #[test]
    fn empty_graph_has_zero_components() {
        let graph = Graph::strict();
        let components = connected_components(&graph);
        assert!(components.components.is_empty());
        assert_eq!(components.witness.nodes_touched, 0);
        let count = number_connected_components(&graph);
        assert_eq!(count.count, 0);
    }

    #[test]
    fn number_connected_components_matches_components_len() {
        let mut graph = Graph::strict();
        graph.add_edge("a", "b").expect("edge add should succeed");
        graph.add_edge("c", "d").expect("edge add should succeed");
        let _ = graph.add_node("e");

        let components = connected_components(&graph);
        let count = number_connected_components(&graph);
        assert_eq!(components.components.len(), count.count);
        assert_eq!(count.witness.algorithm, "bfs_number_connected_components");
    }

    #[test]
    fn degree_centrality_matches_expected_values_and_order() {
        let mut graph = Graph::strict();
        graph.add_edge("a", "b").expect("edge add should succeed");
        graph.add_edge("a", "c").expect("edge add should succeed");
        graph.add_edge("b", "d").expect("edge add should succeed");

        let result = degree_centrality(&graph);
        let expected = [
            ("a".to_owned(), 2.0 / 3.0),
            ("b".to_owned(), 2.0 / 3.0),
            ("c".to_owned(), 1.0 / 3.0),
            ("d".to_owned(), 1.0 / 3.0),
        ];
        let got = result
            .scores
            .iter()
            .map(|entry| (entry.node.clone(), entry.score))
            .collect::<Vec<(String, f64)>>();
        assert_eq!(got.len(), expected.len());
        for (idx, ((g_node, g_score), (e_node, e_score))) in
            got.iter().zip(expected.iter()).enumerate()
        {
            assert_eq!(g_node, e_node, "node order mismatch at index {idx}");
            assert!(
                (g_score - e_score).abs() <= 1e-12,
                "score mismatch for node {g_node}: expected {e_score}, got {g_score}"
            );
        }
    }

    #[test]
    fn degree_centrality_empty_graph_is_empty() {
        let graph = Graph::strict();
        let result = degree_centrality(&graph);
        assert!(result.scores.is_empty());
    }

    #[test]
    fn degree_centrality_singleton_is_one() {
        let mut graph = Graph::strict();
        let _ = graph.add_node("solo");
        let result = degree_centrality(&graph);
        assert_eq!(result.scores.len(), 1);
        assert_eq!(result.scores[0].node, "solo");
        assert!((result.scores[0].score - 1.0).abs() <= 1e-12);
    }

    #[test]
    fn closeness_centrality_matches_expected_values_and_order() {
        let mut graph = Graph::strict();
        graph.add_edge("a", "b").expect("edge add should succeed");
        graph.add_edge("a", "c").expect("edge add should succeed");
        graph.add_edge("b", "d").expect("edge add should succeed");

        let result = closeness_centrality(&graph);
        let expected = [
            ("a".to_owned(), 0.75),
            ("b".to_owned(), 0.75),
            ("c".to_owned(), 0.5),
            ("d".to_owned(), 0.5),
        ];
        for (idx, (actual, (exp_node, exp_score))) in result.scores.iter().zip(expected).enumerate()
        {
            assert_eq!(actual.node, exp_node, "node order mismatch at index {idx}");
            assert!(
                (actual.score - exp_score).abs() <= 1e-12,
                "score mismatch for node {}: expected {}, got {}",
                actual.node,
                exp_score,
                actual.score
            );
        }
    }

    #[test]
    fn closeness_centrality_disconnected_graph_matches_networkx_behavior() {
        let mut graph = Graph::strict();
        graph.add_edge("a", "b").expect("edge add should succeed");
        let _ = graph.add_node("c");
        let result = closeness_centrality(&graph);
        let expected = [("a", 0.5), ("b", 0.5), ("c", 0.0)];
        for (actual, (exp_node, exp_score)) in result.scores.iter().zip(expected) {
            assert_eq!(actual.node, exp_node);
            assert!((actual.score - exp_score).abs() <= 1e-12);
        }
    }

    #[test]
    fn closeness_centrality_singleton_and_empty_are_zero_or_empty() {
        let empty = Graph::strict();
        let empty_result = closeness_centrality(&empty);
        assert!(empty_result.scores.is_empty());

        let mut singleton = Graph::strict();
        let _ = singleton.add_node("solo");
        let single_result = closeness_centrality(&singleton);
        assert_eq!(single_result.scores.len(), 1);
        assert_eq!(single_result.scores[0].node, "solo");
        assert!((single_result.scores[0].score - 0.0).abs() <= 1e-12);
    }

    #[test]
    fn unit_packet_005_contract_asserted() {
        let mut graph = Graph::strict();
        graph.add_edge("a", "b").expect("edge add should succeed");
        graph.add_edge("a", "c").expect("edge add should succeed");
        graph.add_edge("b", "d").expect("edge add should succeed");
        graph.add_edge("c", "d").expect("edge add should succeed");
        graph.add_edge("d", "e").expect("edge add should succeed");

        let path_result = shortest_path_unweighted(&graph, "a", "e");
        assert_eq!(
            path_result.path,
            Some(
                vec!["a", "b", "d", "e"]
                    .into_iter()
                    .map(str::to_owned)
                    .collect()
            )
        );
        assert_eq!(path_result.witness.algorithm, "bfs_shortest_path");
        assert_eq!(path_result.witness.complexity_claim, "O(|V| + |E|)");

        let components = connected_components(&graph);
        assert_eq!(components.components.len(), 1);
        assert_eq!(
            number_connected_components(&graph).count,
            components.components.len()
        );

        let degree = degree_centrality(&graph);
        let closeness = closeness_centrality(&graph);
        assert_eq!(degree.scores.len(), 5);
        assert_eq!(closeness.scores.len(), 5);
        assert!(
            degree.scores.iter().all(|entry| entry.score >= 0.0),
            "degree centrality must remain non-negative"
        );
        assert!(
            closeness.scores.iter().all(|entry| entry.score >= 0.0),
            "closeness centrality must remain non-negative"
        );

        let mut environment = BTreeMap::new();
        environment.insert("os".to_owned(), std::env::consts::OS.to_owned());
        environment.insert("arch".to_owned(), std::env::consts::ARCH.to_owned());
        environment.insert(
            "algorithm_family".to_owned(),
            "shortest_path_first_wave".to_owned(),
        );
        environment.insert("source_target_pair".to_owned(), "a->e".to_owned());
        environment.insert("strict_mode".to_owned(), "true".to_owned());

        let replay_command = "rch exec -- cargo test -p fnx-algorithms unit_packet_005_contract_asserted -- --nocapture";
        let log = StructuredTestLog {
            schema_version: structured_test_log_schema_version().to_owned(),
            run_id: "algorithms-p2c005-unit".to_owned(),
            ts_unix_ms: 1,
            crate_name: "fnx-algorithms".to_owned(),
            suite_id: "unit".to_owned(),
            packet_id: "FNX-P2C-005".to_owned(),
            test_name: "unit_packet_005_contract_asserted".to_owned(),
            test_id: "unit::fnx-p2c-005::contract".to_owned(),
            test_kind: TestKind::Unit,
            mode: CompatibilityMode::Strict,
            fixture_id: Some("algorithms::contract::shortest_path_wave".to_owned()),
            seed: Some(7105),
            env_fingerprint: canonical_environment_fingerprint(&environment),
            environment,
            duration_ms: 7,
            replay_command: replay_command.to_owned(),
            artifact_refs: vec!["artifacts/conformance/latest/structured_logs.jsonl".to_owned()],
            forensic_bundle_id: "forensics::algorithms::unit::contract".to_owned(),
            hash_id: "sha256:algorithms-p2c005-unit".to_owned(),
            status: TestStatus::Passed,
            reason_code: None,
            failure_repro: None,
            e2e_step_traces: Vec::new(),
            forensics_bundle_index: Some(packet_005_forensics_bundle(
                "algorithms-p2c005-unit",
                "unit::fnx-p2c-005::contract",
                replay_command,
                "forensics::algorithms::unit::contract",
                vec!["artifacts/conformance/latest/structured_logs.jsonl".to_owned()],
            )),
        };
        log.validate()
            .expect("unit packet-005 telemetry log should satisfy strict schema");
    }

    proptest! {
        #[test]
        fn property_packet_005_invariants(edges in prop::collection::vec((0_u8..8, 0_u8..8), 1..40)) {
            let mut graph = Graph::strict();
            for (left, right) in &edges {
                let left_node = format!("n{left}");
                let right_node = format!("n{right}");
                let _ = graph.add_node(&left_node);
                let _ = graph.add_node(&right_node);
                graph
                    .add_edge(&left_node, &right_node)
                    .expect("generated edge insertion should succeed");
            }

            let ordered_nodes = graph
                .nodes_ordered()
                .into_iter()
                .map(str::to_owned)
                .collect::<Vec<String>>();
            prop_assume!(!ordered_nodes.is_empty());
            let source = ordered_nodes.first().expect("source node exists").clone();
            let target = ordered_nodes.last().expect("target node exists").clone();

            let left = shortest_path_unweighted(&graph, &source, &target);
            let right = shortest_path_unweighted(&graph, &source, &target);
            prop_assert_eq!(
                &left.path, &right.path,
                "P2C005-INV-1 shortest-path replay must be deterministic"
            );
            prop_assert_eq!(
                &left.witness, &right.witness,
                "P2C005-INV-1 complexity witness replay must be deterministic"
            );

            let components = connected_components(&graph);
            let count = number_connected_components(&graph);
            prop_assert_eq!(
                components.components.len(), count.count,
                "P2C005-INV-3 connected component count must match partition cardinality"
            );

            let degree = degree_centrality(&graph);
            let closeness = closeness_centrality(&graph);
            let degree_order = degree
                .scores
                .iter()
                .map(|entry| entry.node.as_str())
                .collect::<Vec<&str>>();
            let closeness_order = closeness
                .scores
                .iter()
                .map(|entry| entry.node.as_str())
                .collect::<Vec<&str>>();
            let ordered_refs = graph.nodes_ordered();
            prop_assert_eq!(
                degree_order, ordered_refs.clone(),
                "P2C005-DC-3 degree centrality order must match graph node order"
            );
            prop_assert_eq!(
                closeness_order, ordered_refs,
                "P2C005-DC-3 closeness centrality order must match graph node order"
            );

            if let Some(path) = &left.path {
                prop_assert!(
                    !path.is_empty(),
                    "P2C005-INV-1 emitted path must be non-empty when present"
                );
                prop_assert_eq!(
                    path.first().expect("path has first node"),
                    &source,
                    "P2C005-INV-1 path must start at source"
                );
                prop_assert_eq!(
                    path.last().expect("path has last node"),
                    &target,
                    "P2C005-INV-1 path must end at target"
                );
            }

            let deterministic_seed = edges.iter().fold(7205_u64, |acc, (left_edge, right_edge)| {
                acc.wrapping_mul(131)
                    .wrapping_add((*left_edge as u64) << 8)
                    .wrapping_add(*right_edge as u64)
            });
            let mut environment = BTreeMap::new();
            environment.insert("os".to_owned(), std::env::consts::OS.to_owned());
            environment.insert("arch".to_owned(), std::env::consts::ARCH.to_owned());
            environment.insert("graph_fingerprint".to_owned(), graph_fingerprint(&graph));
            environment.insert("tie_break_policy".to_owned(), "lexical_neighbor_order".to_owned());
            environment.insert("invariant_id".to_owned(), "P2C005-INV-1".to_owned());

            let replay_command =
                "rch exec -- cargo test -p fnx-algorithms property_packet_005_invariants -- --nocapture";
            let log = StructuredTestLog {
                schema_version: structured_test_log_schema_version().to_owned(),
                run_id: "algorithms-p2c005-property".to_owned(),
                ts_unix_ms: 2,
                crate_name: "fnx-algorithms".to_owned(),
                suite_id: "property".to_owned(),
                packet_id: "FNX-P2C-005".to_owned(),
                test_name: "property_packet_005_invariants".to_owned(),
                test_id: "property::fnx-p2c-005::invariants".to_owned(),
                test_kind: TestKind::Property,
                mode: CompatibilityMode::Hardened,
                fixture_id: Some("algorithms::property::path_and_centrality_matrix".to_owned()),
                seed: Some(deterministic_seed),
                env_fingerprint: canonical_environment_fingerprint(&environment),
                environment,
                duration_ms: 12,
                replay_command: replay_command.to_owned(),
                artifact_refs: vec![
                    "artifacts/conformance/latest/structured_log_emitter_normalization_report.json"
                        .to_owned(),
                ],
                forensic_bundle_id: "forensics::algorithms::property::invariants".to_owned(),
                hash_id: "sha256:algorithms-p2c005-property".to_owned(),
                status: TestStatus::Passed,
                reason_code: None,
                failure_repro: None,
                e2e_step_traces: Vec::new(),
                forensics_bundle_index: Some(packet_005_forensics_bundle(
                    "algorithms-p2c005-property",
                    "property::fnx-p2c-005::invariants",
                    replay_command,
                    "forensics::algorithms::property::invariants",
                    vec![
                        "artifacts/conformance/latest/structured_log_emitter_normalization_report.json"
                            .to_owned(),
                    ],
                )),
            };
            prop_assert!(
                log.validate().is_ok(),
                "packet-005 property telemetry log should satisfy strict schema"
            );
        }
    }
}
