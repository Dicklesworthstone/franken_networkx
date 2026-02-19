#![forbid(unsafe_code)]

use fnx_classes::Graph;
use serde::{Deserialize, Serialize};
use std::cmp::Ordering;
use std::collections::{HashMap, HashSet, VecDeque};

pub const CGSE_WITNESS_ARTIFACT_SCHEMA_VERSION_V1: &str = "1.0.0";
pub const CGSE_WITNESS_POLICY_SPEC_PATH: &str =
    "artifacts/cgse/v1/cgse_deterministic_policy_spec_v1.json";
pub const CGSE_WITNESS_LEDGER_PATH: &str =
    "artifacts/cgse/v1/cgse_legacy_tiebreak_ordering_ledger_v1.json";

#[must_use]
pub fn cgse_witness_schema_version() -> &'static str {
    CGSE_WITNESS_ARTIFACT_SCHEMA_VERSION_V1
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ComplexityWitness {
    pub algorithm: String,
    pub complexity_claim: String,
    pub nodes_touched: usize,
    pub edges_scanned: usize,
    pub queue_peak: usize,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct CgseWitnessArtifact {
    pub schema_version: String,
    pub algorithm_family: String,
    pub operation: String,
    pub algorithm: String,
    pub complexity_claim: String,
    pub nodes_touched: usize,
    pub edges_scanned: usize,
    pub queue_peak: usize,
    pub artifact_refs: Vec<String>,
    pub witness_hash_id: String,
}

impl ComplexityWitness {
    #[must_use]
    pub fn to_cgse_witness_artifact(
        &self,
        algorithm_family: &str,
        operation: &str,
        artifact_refs: &[&str],
    ) -> CgseWitnessArtifact {
        let mut canonical_refs = vec![
            CGSE_WITNESS_POLICY_SPEC_PATH.to_owned(),
            CGSE_WITNESS_LEDGER_PATH.to_owned(),
        ];
        canonical_refs.extend(
            artifact_refs
                .iter()
                .copied()
                .map(str::trim)
                .filter(|item| !item.is_empty())
                .map(str::to_owned),
        );
        canonical_refs.sort_unstable();
        canonical_refs.dedup();

        let hash_material = format!(
            "schema:{}|family:{}|op:{}|alg:{}|claim:{}|nodes:{}|edges:{}|q:{}|refs:{}",
            cgse_witness_schema_version(),
            algorithm_family.trim(),
            operation.trim(),
            self.algorithm,
            self.complexity_claim,
            self.nodes_touched,
            self.edges_scanned,
            self.queue_peak,
            canonical_refs.join("|")
        );

        CgseWitnessArtifact {
            schema_version: cgse_witness_schema_version().to_owned(),
            algorithm_family: algorithm_family.trim().to_owned(),
            operation: operation.trim().to_owned(),
            algorithm: self.algorithm.clone(),
            complexity_claim: self.complexity_claim.clone(),
            nodes_touched: self.nodes_touched,
            edges_scanned: self.edges_scanned,
            queue_peak: self.queue_peak,
            artifact_refs: canonical_refs,
            witness_hash_id: format!("cgse-witness:{}", stable_hash_hex(hash_material.as_bytes())),
        }
    }
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

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct BetweennessCentralityResult {
    pub scores: Vec<CentralityScore>,
    pub witness: ComplexityWitness,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct MaximalMatchingResult {
    pub matching: Vec<(String, String)>,
    pub witness: ComplexityWitness,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct WeightedMatchingResult {
    pub matching: Vec<(String, String)>,
    pub total_weight: f64,
    pub witness: ComplexityWitness,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct MaxFlowResult {
    pub value: f64,
    pub witness: ComplexityWitness,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct MinimumCutResult {
    pub value: f64,
    pub source_partition: Vec<String>,
    pub sink_partition: Vec<String>,
    pub witness: ComplexityWitness,
}

#[derive(Debug, Clone)]
struct FlowComputation {
    value: f64,
    residual: HashMap<String, HashMap<String, f64>>,
    witness: ComplexityWitness,
}

type MatchingNodeSet = HashSet<String>;
type MatchingEdgeSet = HashSet<(String, String)>;

#[derive(Debug, Clone)]
struct WeightedEdgeCandidate {
    left: String,
    right: String,
    weight: f64,
    iteration_index: usize,
    degree_sum: usize,
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
pub fn shortest_path_weighted(
    graph: &Graph,
    source: &str,
    target: &str,
    weight_attr: &str,
) -> ShortestPathResult {
    if !graph.has_node(source) || !graph.has_node(target) {
        return ShortestPathResult {
            path: None,
            witness: ComplexityWitness {
                algorithm: "dijkstra_shortest_path".to_owned(),
                complexity_claim: "O(|V|^2 + |E|)".to_owned(),
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
                algorithm: "dijkstra_shortest_path".to_owned(),
                complexity_claim: "O(|V|^2 + |E|)".to_owned(),
                nodes_touched: 1,
                edges_scanned: 0,
                queue_peak: 1,
            },
        };
    }

    let nodes = graph.nodes_ordered();
    let mut settled: HashSet<&str> = HashSet::new();
    let mut predecessor: HashMap<&str, &str> = HashMap::new();
    let mut distance: HashMap<&str, f64> = HashMap::new();
    distance.insert(source, 0.0);

    let mut nodes_touched = 1usize;
    let mut edges_scanned = 0usize;
    let mut queue_peak = 1usize;

    loop {
        let mut current: Option<(&str, f64)> = None;
        for &node in &nodes {
            if settled.contains(node) {
                continue;
            }
            let Some(&candidate_distance) = distance.get(node) else {
                continue;
            };
            match current {
                None => current = Some((node, candidate_distance)),
                Some((_, best_distance)) if candidate_distance < best_distance => {
                    current = Some((node, candidate_distance));
                }
                _ => {}
            }
        }

        let Some((current_node, current_distance)) = current else {
            break;
        };

        settled.insert(current_node);
        if current_node == target {
            break;
        }

        let Some(neighbors) = graph.neighbors_iter(current_node) else {
            continue;
        };
        for neighbor in neighbors {
            edges_scanned += 1;
            if settled.contains(neighbor) {
                continue;
            }
            let edge_weight = edge_weight_or_default(graph, current_node, neighbor, weight_attr);
            let candidate_distance = current_distance + edge_weight;
            let should_update = match distance.get(neighbor) {
                Some(existing_distance) => candidate_distance < *existing_distance,
                None => true,
            };
            if should_update {
                if distance.insert(neighbor, candidate_distance).is_none() {
                    nodes_touched += 1;
                }
                predecessor.insert(neighbor, current_node);
            }
        }

        queue_peak = queue_peak.max(distance.len().saturating_sub(settled.len()));
    }

    let path = if distance.contains_key(target) {
        let rebuilt_path = rebuild_path(&predecessor, source, target);
        if rebuilt_path.first().map(String::as_str) == Some(source)
            && rebuilt_path.last().map(String::as_str) == Some(target)
        {
            Some(rebuilt_path)
        } else {
            None
        }
    } else {
        None
    };

    ShortestPathResult {
        path,
        witness: ComplexityWitness {
            algorithm: "dijkstra_shortest_path".to_owned(),
            complexity_claim: "O(|V|^2 + |E|)".to_owned(),
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

#[must_use]
pub fn betweenness_centrality(graph: &Graph) -> BetweennessCentralityResult {
    let nodes = graph.nodes_ordered();
    let n = nodes.len();
    if n == 0 {
        return BetweennessCentralityResult {
            scores: Vec::new(),
            witness: ComplexityWitness {
                algorithm: "brandes_betweenness_centrality".to_owned(),
                complexity_claim: "O(|V| * |E|)".to_owned(),
                nodes_touched: 0,
                edges_scanned: 0,
                queue_peak: 0,
            },
        };
    }

    let mut centrality = HashMap::<&str, f64>::new();
    for node in &nodes {
        centrality.insert(*node, 0.0);
    }

    let mut nodes_touched = 0usize;
    let mut edges_scanned = 0usize;
    let mut queue_peak = 0usize;

    for source in &nodes {
        let mut stack = Vec::<&str>::with_capacity(n);
        let mut predecessors = HashMap::<&str, Vec<&str>>::new();
        let mut sigma = HashMap::<&str, f64>::new();
        let mut distance = HashMap::<&str, i64>::new();
        for node in &nodes {
            predecessors.insert(*node, Vec::new());
            sigma.insert(*node, 0.0);
            distance.insert(*node, -1);
        }
        sigma.insert(*source, 1.0);
        distance.insert(*source, 0);

        let mut queue = VecDeque::<&str>::new();
        queue.push_back(source);
        queue_peak = queue_peak.max(queue.len());

        while let Some(v) = queue.pop_front() {
            stack.push(v);
            let dist_v = *distance.get(v).unwrap_or(&-1);
            let Some(neighbors) = graph.neighbors_iter(v) else {
                continue;
            };
            for w in neighbors {
                edges_scanned += 1;
                if *distance.get(w).unwrap_or(&-1) < 0 {
                    distance.insert(w, dist_v + 1);
                    queue.push_back(w);
                    queue_peak = queue_peak.max(queue.len());
                }
                if *distance.get(w).unwrap_or(&-1) == dist_v + 1 {
                    let sigma_v = *sigma.get(v).unwrap_or(&0.0);
                    *sigma.entry(w).or_insert(0.0) += sigma_v;
                    predecessors.entry(w).or_default().push(v);
                }
            }
        }
        nodes_touched += stack.len();

        let mut dependency = HashMap::<&str, f64>::new();
        for node in &nodes {
            dependency.insert(*node, 0.0);
        }

        while let Some(w) = stack.pop() {
            let sigma_w = *sigma.get(w).unwrap_or(&0.0);
            let delta_w = *dependency.get(w).unwrap_or(&0.0);
            if sigma_w > 0.0 {
                for v in predecessors.get(w).map(Vec::as_slice).unwrap_or(&[]) {
                    let sigma_v = *sigma.get(v).unwrap_or(&0.0);
                    let contribution = (sigma_v / sigma_w) * (1.0 + delta_w);
                    *dependency.entry(v).or_insert(0.0) += contribution;
                }
            }
            if w != *source {
                *centrality.entry(w).or_insert(0.0) += delta_w;
            }
        }
    }

    let scale = if n > 2 {
        1.0 / (((n - 1) * (n - 2)) as f64)
    } else {
        0.0
    };
    let scores = nodes
        .iter()
        .map(|node| CentralityScore {
            node: (*node).to_owned(),
            score: centrality.get(node).copied().unwrap_or(0.0) * scale,
        })
        .collect::<Vec<CentralityScore>>();

    BetweennessCentralityResult {
        scores,
        witness: ComplexityWitness {
            algorithm: "brandes_betweenness_centrality".to_owned(),
            complexity_claim: "O(|V| * |E|)".to_owned(),
            nodes_touched,
            edges_scanned,
            queue_peak,
        },
    }
}

#[must_use]
pub fn maximal_matching(graph: &Graph) -> MaximalMatchingResult {
    let mut matched_nodes = HashSet::<String>::new();
    let mut matching = Vec::<(String, String)>::new();
    let edges = undirected_edges_in_iteration_order(graph);
    for (left, right) in &edges {
        if left == right || matched_nodes.contains(left) || matched_nodes.contains(right) {
            continue;
        }
        matched_nodes.insert(left.clone());
        matched_nodes.insert(right.clone());
        matching.push((left.clone(), right.clone()));
    }

    MaximalMatchingResult {
        matching,
        witness: ComplexityWitness {
            algorithm: "greedy_maximal_matching".to_owned(),
            complexity_claim: "O(|E|)".to_owned(),
            nodes_touched: graph.node_count(),
            edges_scanned: edges.len(),
            queue_peak: 0,
        },
    }
}

#[must_use]
pub fn is_matching(graph: &Graph, matching: &[(String, String)]) -> bool {
    matching_state(graph, matching).is_some()
}

#[must_use]
pub fn is_maximal_matching(graph: &Graph, matching: &[(String, String)]) -> bool {
    let Some((matched_nodes, matched_edges)) = matching_state(graph, matching) else {
        return false;
    };

    for (left, right) in undirected_edges_in_iteration_order(graph) {
        if left == right {
            continue;
        }
        let canonical = canonical_undirected_edge(&left, &right);
        if matched_edges.contains(&canonical) {
            continue;
        }
        if !matched_nodes.contains(&left) && !matched_nodes.contains(&right) {
            return false;
        }
    }

    true
}

#[must_use]
pub fn is_perfect_matching(graph: &Graph, matching: &[(String, String)]) -> bool {
    let Some((matched_nodes, _)) = matching_state(graph, matching) else {
        return false;
    };
    matched_nodes.len() == graph.node_count()
}

#[must_use]
pub fn max_weight_matching(
    graph: &Graph,
    maxcardinality: bool,
    weight_attr: &str,
) -> WeightedMatchingResult {
    let candidates = weighted_edge_candidates(graph, weight_attr);
    if candidates.is_empty() {
        return WeightedMatchingResult {
            matching: Vec::new(),
            total_weight: 0.0,
            witness: ComplexityWitness {
                algorithm: if maxcardinality {
                    "greedy_max_weight_matching_maxcardinality".to_owned()
                } else {
                    "greedy_max_weight_matching".to_owned()
                },
                complexity_claim: "O(|E| log |E|)".to_owned(),
                nodes_touched: graph.node_count(),
                edges_scanned: 0,
                queue_peak: 0,
            },
        };
    }

    let weighted_order = sorted_candidates_by_weight(candidates.clone());
    let weighted_matching = greedy_matching_from_candidates(&weighted_order);

    let (matching, total_weight, passes) = if maxcardinality {
        let cardinality_order = sorted_candidates_by_cardinality_aware_weight(candidates);
        let cardinality_matching = greedy_matching_from_candidates(&cardinality_order);
        let (selected_matching, selected_weight) =
            choose_preferred_matching(weighted_matching, cardinality_matching, true);
        (selected_matching, selected_weight, 2usize)
    } else {
        (weighted_matching.0, weighted_matching.1, 1usize)
    };

    WeightedMatchingResult {
        matching,
        total_weight,
        witness: ComplexityWitness {
            algorithm: if maxcardinality {
                "greedy_max_weight_matching_maxcardinality".to_owned()
            } else {
                "greedy_max_weight_matching".to_owned()
            },
            complexity_claim: "O(|E| log |E|)".to_owned(),
            nodes_touched: graph.node_count(),
            edges_scanned: weighted_order.len() * passes,
            queue_peak: 0,
        },
    }
}

#[must_use]
pub fn min_weight_matching(graph: &Graph, weight_attr: &str) -> WeightedMatchingResult {
    let candidates = weighted_edge_candidates(graph, weight_attr);
    if candidates.is_empty() {
        return WeightedMatchingResult {
            matching: Vec::new(),
            total_weight: 0.0,
            witness: ComplexityWitness {
                algorithm: "greedy_min_weight_matching".to_owned(),
                complexity_claim: "O(|E| log |E|)".to_owned(),
                nodes_touched: graph.node_count(),
                edges_scanned: 0,
                queue_peak: 0,
            },
        };
    }

    let max_weight = candidates
        .iter()
        .fold(f64::NEG_INFINITY, |acc, edge| acc.max(edge.weight));
    let transformed_candidates = candidates
        .into_iter()
        .map(|edge| WeightedEdgeCandidate {
            weight: (max_weight + 1.0) - edge.weight,
            ..edge
        })
        .collect::<Vec<WeightedEdgeCandidate>>();

    let weighted_order = sorted_candidates_by_weight(transformed_candidates.clone());
    let weighted_matching = greedy_matching_from_candidates(&weighted_order);
    let cardinality_order =
        sorted_candidates_by_cardinality_aware_weight(transformed_candidates.clone());
    let cardinality_matching = greedy_matching_from_candidates(&cardinality_order);
    let (matching, _) = choose_preferred_matching(weighted_matching, cardinality_matching, true);
    let total_weight = matching
        .iter()
        .map(|(left, right)| matching_edge_weight_or_default(graph, left, right, weight_attr))
        .sum();

    WeightedMatchingResult {
        matching,
        total_weight,
        witness: ComplexityWitness {
            algorithm: "greedy_min_weight_matching".to_owned(),
            complexity_claim: "O(|E| log |E|)".to_owned(),
            nodes_touched: graph.node_count(),
            edges_scanned: transformed_candidates.len() * 2,
            queue_peak: 0,
        },
    }
}

#[must_use]
pub fn max_flow_edmonds_karp(
    graph: &Graph,
    source: &str,
    sink: &str,
    capacity_attr: &str,
) -> MaxFlowResult {
    let computation = compute_max_flow_residual(graph, source, sink, capacity_attr);
    MaxFlowResult {
        value: computation.value,
        witness: computation.witness,
    }
}

#[must_use]
pub fn minimum_cut_edmonds_karp(
    graph: &Graph,
    source: &str,
    sink: &str,
    capacity_attr: &str,
) -> MinimumCutResult {
    if !graph.has_node(source) || !graph.has_node(sink) {
        return MinimumCutResult {
            value: 0.0,
            source_partition: Vec::new(),
            sink_partition: Vec::new(),
            witness: ComplexityWitness {
                algorithm: "edmonds_karp_minimum_cut".to_owned(),
                complexity_claim: "O(|V| * |E|^2)".to_owned(),
                nodes_touched: 0,
                edges_scanned: 0,
                queue_peak: 0,
            },
        };
    }

    if source == sink {
        let mut source_partition = Vec::new();
        let mut sink_partition = Vec::new();
        for node in graph.nodes_ordered().into_iter().map(str::to_owned) {
            if node == source {
                source_partition.push(node);
            } else {
                sink_partition.push(node);
            }
        }
        return MinimumCutResult {
            value: 0.0,
            source_partition,
            sink_partition,
            witness: ComplexityWitness {
                algorithm: "edmonds_karp_minimum_cut".to_owned(),
                complexity_claim: "O(|V| * |E|^2)".to_owned(),
                nodes_touched: 1,
                edges_scanned: 0,
                queue_peak: 1,
            },
        };
    }

    let computation = compute_max_flow_residual(graph, source, sink, capacity_attr);
    let ordered_nodes = graph
        .nodes_ordered()
        .into_iter()
        .map(str::to_owned)
        .collect::<Vec<String>>();
    let mut visited = HashSet::<String>::new();
    let mut queue = VecDeque::<String>::new();
    queue.push_back(source.to_owned());
    visited.insert(source.to_owned());
    let mut cut_nodes_touched = 1_usize;
    let mut cut_edges_scanned = 0_usize;
    let mut cut_queue_peak = 1_usize;

    while let Some(current) = queue.pop_front() {
        for candidate in &ordered_nodes {
            if visited.contains(candidate) {
                continue;
            }
            cut_edges_scanned += 1;
            let residual_capacity = computation
                .residual
                .get(&current)
                .and_then(|caps| caps.get(candidate))
                .copied()
                .unwrap_or(0.0);
            if residual_capacity <= 0.0 {
                continue;
            }
            visited.insert(candidate.clone());
            queue.push_back(candidate.clone());
            cut_nodes_touched += 1;
            cut_queue_peak = cut_queue_peak.max(queue.len());
        }
    }

    let mut source_partition = Vec::new();
    let mut sink_partition = Vec::new();
    for node in ordered_nodes {
        if visited.contains(&node) {
            source_partition.push(node);
        } else {
            sink_partition.push(node);
        }
    }

    MinimumCutResult {
        value: computation.value,
        source_partition,
        sink_partition,
        witness: ComplexityWitness {
            algorithm: "edmonds_karp_minimum_cut".to_owned(),
            complexity_claim: "O(|V| * |E|^2)".to_owned(),
            nodes_touched: computation.witness.nodes_touched + cut_nodes_touched,
            edges_scanned: computation.witness.edges_scanned + cut_edges_scanned,
            queue_peak: computation.witness.queue_peak.max(cut_queue_peak),
        },
    }
}

fn compute_max_flow_residual(
    graph: &Graph,
    source: &str,
    sink: &str,
    capacity_attr: &str,
) -> FlowComputation {
    if !graph.has_node(source) || !graph.has_node(sink) {
        return FlowComputation {
            value: 0.0,
            residual: HashMap::new(),
            witness: ComplexityWitness {
                algorithm: "edmonds_karp_max_flow".to_owned(),
                complexity_claim: "O(|V| * |E|^2)".to_owned(),
                nodes_touched: 0,
                edges_scanned: 0,
                queue_peak: 0,
            },
        };
    }

    if source == sink {
        return FlowComputation {
            value: 0.0,
            residual: HashMap::new(),
            witness: ComplexityWitness {
                algorithm: "edmonds_karp_max_flow".to_owned(),
                complexity_claim: "O(|V| * |E|^2)".to_owned(),
                nodes_touched: 1,
                edges_scanned: 0,
                queue_peak: 1,
            },
        };
    }

    let ordered_nodes = graph.nodes_ordered();
    let mut residual: HashMap<String, HashMap<String, f64>> = HashMap::new();
    for node in &ordered_nodes {
        let node_key = (*node).to_owned();
        residual.entry(node_key.clone()).or_default();
        let Some(neighbors) = graph.neighbors_iter(node) else {
            continue;
        };
        for neighbor in neighbors {
            let capacity = edge_capacity_or_default(graph, node, neighbor, capacity_attr);
            residual
                .entry(node_key.clone())
                .or_default()
                .entry(neighbor.to_owned())
                .or_insert(capacity);
            residual.entry(neighbor.to_owned()).or_default();
        }
    }

    let mut total_flow = 0.0_f64;
    let mut nodes_touched = 0_usize;
    let mut edges_scanned = 0_usize;
    let mut queue_peak = 0_usize;

    loop {
        let mut predecessor: HashMap<String, String> = HashMap::new();
        let mut visited: HashSet<String> = HashSet::new();
        let mut queue: VecDeque<String> = VecDeque::new();
        let source_owned = source.to_owned();
        queue.push_back(source_owned.clone());
        visited.insert(source_owned);
        nodes_touched += 1;
        queue_peak = queue_peak.max(queue.len());

        let mut reached_sink = false;
        while let Some(current) = queue.pop_front() {
            let Some(neighbors) = graph.neighbors_iter(&current) else {
                continue;
            };
            for neighbor in neighbors {
                edges_scanned += 1;
                if visited.contains(neighbor) {
                    continue;
                }
                let residual_capacity = residual
                    .get(&current)
                    .and_then(|caps| caps.get(neighbor))
                    .copied()
                    .unwrap_or(0.0);
                if residual_capacity <= 0.0 {
                    continue;
                }
                predecessor.insert(neighbor.to_owned(), current.clone());
                visited.insert(neighbor.to_owned());
                nodes_touched += 1;
                if neighbor == sink {
                    reached_sink = true;
                    break;
                }
                queue.push_back(neighbor.to_owned());
                queue_peak = queue_peak.max(queue.len());
            }
            if reached_sink {
                break;
            }
        }

        if !reached_sink {
            break;
        }

        let mut bottleneck = f64::INFINITY;
        let mut cursor = sink.to_owned();
        while cursor != source {
            let Some(prev) = predecessor.get(&cursor) else {
                bottleneck = 0.0;
                break;
            };
            let available = residual
                .get(prev)
                .and_then(|caps| caps.get(&cursor))
                .copied()
                .unwrap_or(0.0);
            bottleneck = bottleneck.min(available);
            cursor = prev.clone();
        }

        if bottleneck <= 0.0 || !bottleneck.is_finite() {
            break;
        }

        let mut cursor = sink.to_owned();
        while cursor != source {
            let Some(prev) = predecessor.get(&cursor).cloned() else {
                break;
            };
            let forward = residual
                .entry(prev.clone())
                .or_default()
                .entry(cursor.clone())
                .or_insert(0.0);
            *forward = (*forward - bottleneck).max(0.0);
            let reverse = residual
                .entry(cursor.clone())
                .or_default()
                .entry(prev.clone())
                .or_insert(0.0);
            *reverse += bottleneck;
            cursor = prev;
        }

        total_flow += bottleneck;
    }

    FlowComputation {
        value: total_flow,
        residual,
        witness: ComplexityWitness {
            algorithm: "edmonds_karp_max_flow".to_owned(),
            complexity_claim: "O(|V| * |E|^2)".to_owned(),
            nodes_touched,
            edges_scanned,
            queue_peak,
        },
    }
}

fn matching_state(
    graph: &Graph,
    matching: &[(String, String)],
) -> Option<(MatchingNodeSet, MatchingEdgeSet)> {
    let mut matched_nodes = MatchingNodeSet::new();
    let mut matched_edges = MatchingEdgeSet::new();

    for (left, right) in matching {
        if left == right
            || !graph.has_node(left)
            || !graph.has_node(right)
            || !graph.has_edge(left, right)
            || !matched_nodes.insert(left.clone())
            || !matched_nodes.insert(right.clone())
        {
            return None;
        }
        matched_edges.insert(canonical_undirected_edge(left, right));
    }

    Some((matched_nodes, matched_edges))
}

fn canonical_undirected_edge(left: &str, right: &str) -> (String, String) {
    if left <= right {
        (left.to_owned(), right.to_owned())
    } else {
        (right.to_owned(), left.to_owned())
    }
}

fn undirected_edges_in_iteration_order(graph: &Graph) -> Vec<(String, String)> {
    let mut seen_nodes = HashSet::<&str>::new();
    let mut edges = Vec::<(String, String)>::new();
    for left in graph.nodes_ordered() {
        let Some(neighbors) = graph.neighbors_iter(left) else {
            seen_nodes.insert(left);
            continue;
        };
        for right in neighbors {
            if seen_nodes.contains(right) {
                continue;
            }
            edges.push((left.to_owned(), right.to_owned()));
        }
        seen_nodes.insert(left);
    }
    edges
}

fn weighted_edge_candidates(graph: &Graph, weight_attr: &str) -> Vec<WeightedEdgeCandidate> {
    undirected_edges_in_iteration_order(graph)
        .into_iter()
        .enumerate()
        .map(|(iteration_index, (left, right))| WeightedEdgeCandidate {
            weight: matching_edge_weight_or_default(graph, &left, &right, weight_attr),
            degree_sum: graph.neighbor_count(&left) + graph.neighbor_count(&right),
            left,
            right,
            iteration_index,
        })
        .collect()
}

fn sorted_candidates_by_weight(
    mut candidates: Vec<WeightedEdgeCandidate>,
) -> Vec<WeightedEdgeCandidate> {
    candidates.sort_by(|left, right| {
        right
            .weight
            .partial_cmp(&left.weight)
            .unwrap_or(Ordering::Equal)
            .then_with(|| left.iteration_index.cmp(&right.iteration_index))
    });
    candidates
}

fn sorted_candidates_by_cardinality_aware_weight(
    mut candidates: Vec<WeightedEdgeCandidate>,
) -> Vec<WeightedEdgeCandidate> {
    candidates.sort_by(|left, right| {
        left.degree_sum
            .cmp(&right.degree_sum)
            .then_with(|| {
                right
                    .weight
                    .partial_cmp(&left.weight)
                    .unwrap_or(Ordering::Equal)
            })
            .then_with(|| left.iteration_index.cmp(&right.iteration_index))
    });
    candidates
}

fn greedy_matching_from_candidates(
    candidates: &[WeightedEdgeCandidate],
) -> (Vec<(String, String)>, f64) {
    let mut matched_nodes = MatchingNodeSet::new();
    let mut matching = Vec::<(String, String)>::new();
    let mut total_weight = 0.0_f64;

    for edge in candidates {
        if edge.left == edge.right
            || matched_nodes.contains(&edge.left)
            || matched_nodes.contains(&edge.right)
        {
            continue;
        }
        matched_nodes.insert(edge.left.clone());
        matched_nodes.insert(edge.right.clone());
        matching.push((edge.left.clone(), edge.right.clone()));
        total_weight += edge.weight;
    }

    (matching, total_weight)
}

fn choose_preferred_matching(
    weighted: (Vec<(String, String)>, f64),
    alternative: (Vec<(String, String)>, f64),
    prefer_cardinality: bool,
) -> (Vec<(String, String)>, f64) {
    let (weighted_matching, weighted_weight) = weighted;
    let (alternative_matching, alternative_weight) = alternative;

    if prefer_cardinality {
        match alternative_matching.len().cmp(&weighted_matching.len()) {
            Ordering::Greater => return (alternative_matching, alternative_weight),
            Ordering::Less => return (weighted_matching, weighted_weight),
            Ordering::Equal => {}
        }
    }

    match alternative_weight
        .partial_cmp(&weighted_weight)
        .unwrap_or(Ordering::Equal)
    {
        Ordering::Greater => return (alternative_matching, alternative_weight),
        Ordering::Less => return (weighted_matching, weighted_weight),
        Ordering::Equal => {}
    }

    let weighted_key = canonical_matching_key(&weighted_matching);
    let alternative_key = canonical_matching_key(&alternative_matching);
    if alternative_key < weighted_key {
        (alternative_matching, alternative_weight)
    } else {
        (weighted_matching, weighted_weight)
    }
}

fn canonical_matching_key(matching: &[(String, String)]) -> Vec<(String, String)> {
    let mut key = matching
        .iter()
        .map(|(left, right)| canonical_undirected_edge(left, right))
        .collect::<Vec<(String, String)>>();
    key.sort_unstable();
    key
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

fn edge_weight_or_default(graph: &Graph, left: &str, right: &str, weight_attr: &str) -> f64 {
    graph
        .edge_attrs(left, right)
        .and_then(|attrs| attrs.get(weight_attr))
        .and_then(|raw| raw.parse::<f64>().ok())
        .filter(|value| value.is_finite() && *value >= 0.0)
        .unwrap_or(1.0)
}

fn matching_edge_weight_or_default(
    graph: &Graph,
    left: &str,
    right: &str,
    weight_attr: &str,
) -> f64 {
    graph
        .edge_attrs(left, right)
        .and_then(|attrs| attrs.get(weight_attr))
        .and_then(|raw| raw.parse::<f64>().ok())
        .filter(|value| value.is_finite())
        .unwrap_or(1.0)
}

fn edge_capacity_or_default(graph: &Graph, left: &str, right: &str, capacity_attr: &str) -> f64 {
    graph
        .edge_attrs(left, right)
        .and_then(|attrs| attrs.get(capacity_attr))
        .and_then(|raw| raw.parse::<f64>().ok())
        .filter(|value| value.is_finite() && *value >= 0.0)
        .unwrap_or(1.0)
}

fn stable_hash_hex(input: &[u8]) -> String {
    let mut hash = 0xcbf29ce484222325_u64;
    for byte in input {
        hash ^= u64::from(*byte);
        hash = hash.wrapping_mul(0x00000100000001b3_u64);
    }
    format!("{hash:016x}")
}

#[cfg(test)]
mod tests {
    use super::{
        CGSE_WITNESS_LEDGER_PATH, CGSE_WITNESS_POLICY_SPEC_PATH, CentralityScore,
        ComplexityWitness, betweenness_centrality, cgse_witness_schema_version,
        closeness_centrality, connected_components, degree_centrality, is_matching,
        is_maximal_matching, is_perfect_matching, max_flow_edmonds_karp, max_weight_matching,
        maximal_matching, min_weight_matching, minimum_cut_edmonds_karp,
        number_connected_components, shortest_path_unweighted, shortest_path_weighted,
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

    fn assert_matching_is_valid_and_maximal(graph: &Graph, matching: &[(String, String)]) {
        let mut matched_nodes = std::collections::HashSet::<String>::new();
        let mut matched_edges = BTreeSet::<(String, String)>::new();

        for (left, right) in matching {
            assert_ne!(left, right, "self-loops are not valid matching edges");
            assert!(
                graph.has_edge(left, right),
                "matching edge ({left}, {right}) must exist in graph"
            );
            assert!(
                matched_nodes.insert(left.clone()),
                "node {left} appears in multiple matching edges"
            );
            assert!(
                matched_nodes.insert(right.clone()),
                "node {right} appears in multiple matching edges"
            );
            let canonical = if left <= right {
                (left.clone(), right.clone())
            } else {
                (right.clone(), left.clone())
            };
            matched_edges.insert(canonical);
        }

        for left in graph.nodes_ordered() {
            let Some(neighbors) = graph.neighbors_iter(left) else {
                continue;
            };
            for right in neighbors {
                if left >= right {
                    continue;
                }
                if matched_edges.contains(&(left.to_owned(), right.to_owned())) {
                    continue;
                }
                assert!(
                    matched_nodes.contains(left) || matched_nodes.contains(right),
                    "found augmentable edge ({left}, {right}), matching is not maximal"
                );
            }
        }
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
    fn shortest_path_tie_break_tracks_first_seen_neighbor_order() {
        let mut insertion_a = Graph::strict();
        insertion_a
            .add_edge("a", "b")
            .expect("edge add should succeed");
        insertion_a
            .add_edge("a", "c")
            .expect("edge add should succeed");
        insertion_a
            .add_edge("b", "d")
            .expect("edge add should succeed");
        insertion_a
            .add_edge("c", "d")
            .expect("edge add should succeed");

        let mut insertion_b = Graph::strict();
        insertion_b
            .add_edge("c", "d")
            .expect("edge add should succeed");
        insertion_b
            .add_edge("a", "c")
            .expect("edge add should succeed");
        insertion_b
            .add_edge("b", "d")
            .expect("edge add should succeed");
        insertion_b
            .add_edge("a", "b")
            .expect("edge add should succeed");

        let left = shortest_path_unweighted(&insertion_a, "a", "d");
        let left_replay = shortest_path_unweighted(&insertion_a, "a", "d");
        let right = shortest_path_unweighted(&insertion_b, "a", "d");
        let right_replay = shortest_path_unweighted(&insertion_b, "a", "d");
        assert_eq!(
            left.path,
            Some(vec!["a", "b", "d"].into_iter().map(str::to_owned).collect())
        );
        assert_eq!(
            right.path,
            Some(vec!["a", "c", "d"].into_iter().map(str::to_owned).collect())
        );
        assert_eq!(left.path, left_replay.path);
        assert_eq!(left.witness, left_replay.witness);
        assert_eq!(right.path, right_replay.path);
        assert_eq!(right.witness, right_replay.witness);
    }

    #[test]
    fn weighted_shortest_path_prefers_lower_total_weight() {
        let mut graph = Graph::strict();
        graph
            .add_edge_with_attrs("a", "b", [("weight".to_owned(), "5".to_owned())].into())
            .expect("edge add should succeed");
        graph
            .add_edge_with_attrs("a", "c", [("weight".to_owned(), "1".to_owned())].into())
            .expect("edge add should succeed");
        graph
            .add_edge_with_attrs("c", "b", [("weight".to_owned(), "1".to_owned())].into())
            .expect("edge add should succeed");
        graph
            .add_edge_with_attrs("b", "d", [("weight".to_owned(), "1".to_owned())].into())
            .expect("edge add should succeed");
        graph
            .add_edge_with_attrs("c", "d", [("weight".to_owned(), "10".to_owned())].into())
            .expect("edge add should succeed");

        let result = shortest_path_weighted(&graph, "a", "d", "weight");
        assert_eq!(
            result.path,
            Some(
                vec!["a", "c", "b", "d"]
                    .into_iter()
                    .map(str::to_owned)
                    .collect()
            )
        );
        assert_eq!(result.witness.algorithm, "dijkstra_shortest_path");
    }

    #[test]
    fn weighted_shortest_path_tie_break_tracks_node_insertion_order() {
        let mut insertion_a = Graph::strict();
        insertion_a
            .add_edge_with_attrs("a", "b", [("weight".to_owned(), "1".to_owned())].into())
            .expect("edge add should succeed");
        insertion_a
            .add_edge_with_attrs("a", "c", [("weight".to_owned(), "1".to_owned())].into())
            .expect("edge add should succeed");
        insertion_a
            .add_edge_with_attrs("b", "d", [("weight".to_owned(), "1".to_owned())].into())
            .expect("edge add should succeed");
        insertion_a
            .add_edge_with_attrs("c", "d", [("weight".to_owned(), "1".to_owned())].into())
            .expect("edge add should succeed");

        let mut insertion_b = Graph::strict();
        insertion_b
            .add_edge_with_attrs("a", "c", [("weight".to_owned(), "1".to_owned())].into())
            .expect("edge add should succeed");
        insertion_b
            .add_edge_with_attrs("a", "b", [("weight".to_owned(), "1".to_owned())].into())
            .expect("edge add should succeed");
        insertion_b
            .add_edge_with_attrs("c", "d", [("weight".to_owned(), "1".to_owned())].into())
            .expect("edge add should succeed");
        insertion_b
            .add_edge_with_attrs("b", "d", [("weight".to_owned(), "1".to_owned())].into())
            .expect("edge add should succeed");

        let left = shortest_path_weighted(&insertion_a, "a", "d", "weight");
        let left_replay = shortest_path_weighted(&insertion_a, "a", "d", "weight");
        let right = shortest_path_weighted(&insertion_b, "a", "d", "weight");
        let right_replay = shortest_path_weighted(&insertion_b, "a", "d", "weight");
        assert_eq!(
            left.path,
            Some(vec!["a", "b", "d"].into_iter().map(str::to_owned).collect())
        );
        assert_eq!(
            right.path,
            Some(vec!["a", "c", "d"].into_iter().map(str::to_owned).collect())
        );
        assert_eq!(left.path, left_replay.path);
        assert_eq!(left.witness, left_replay.witness);
        assert_eq!(right.path, right_replay.path);
        assert_eq!(right.witness, right_replay.witness);
    }

    #[test]
    fn max_flow_edmonds_karp_matches_expected_value() {
        let mut graph = Graph::strict();
        graph
            .add_edge_with_attrs("s", "a", [("capacity".to_owned(), "3".to_owned())].into())
            .expect("edge add should succeed");
        graph
            .add_edge_with_attrs("s", "b", [("capacity".to_owned(), "2".to_owned())].into())
            .expect("edge add should succeed");
        graph
            .add_edge_with_attrs("a", "b", [("capacity".to_owned(), "1".to_owned())].into())
            .expect("edge add should succeed");
        graph
            .add_edge_with_attrs("a", "t", [("capacity".to_owned(), "2".to_owned())].into())
            .expect("edge add should succeed");
        graph
            .add_edge_with_attrs("b", "t", [("capacity".to_owned(), "3".to_owned())].into())
            .expect("edge add should succeed");

        let result = max_flow_edmonds_karp(&graph, "s", "t", "capacity");
        assert!((result.value - 5.0).abs() <= 1e-12);
        assert_eq!(result.witness.algorithm, "edmonds_karp_max_flow");
    }

    #[test]
    fn max_flow_edmonds_karp_is_replay_stable() {
        let mut graph = Graph::strict();
        graph
            .add_edge_with_attrs("s", "a", [("capacity".to_owned(), "4".to_owned())].into())
            .expect("edge add should succeed");
        graph
            .add_edge_with_attrs("s", "b", [("capacity".to_owned(), "2".to_owned())].into())
            .expect("edge add should succeed");
        graph
            .add_edge_with_attrs("a", "b", [("capacity".to_owned(), "1".to_owned())].into())
            .expect("edge add should succeed");
        graph
            .add_edge_with_attrs("a", "t", [("capacity".to_owned(), "2".to_owned())].into())
            .expect("edge add should succeed");
        graph
            .add_edge_with_attrs("b", "t", [("capacity".to_owned(), "3".to_owned())].into())
            .expect("edge add should succeed");

        let left = max_flow_edmonds_karp(&graph, "s", "t", "capacity");
        let right = max_flow_edmonds_karp(&graph, "s", "t", "capacity");
        assert!((left.value - right.value).abs() <= 1e-12);
        assert_eq!(left.witness, right.witness);
    }

    #[test]
    fn max_flow_edmonds_karp_returns_zero_for_missing_nodes() {
        let mut graph = Graph::strict();
        let _ = graph.add_node("only");
        let result = max_flow_edmonds_karp(&graph, "missing", "only", "capacity");
        assert!((result.value - 0.0).abs() <= 1e-12);
    }

    #[test]
    fn minimum_cut_edmonds_karp_matches_expected_partition() {
        let mut graph = Graph::strict();
        graph
            .add_edge_with_attrs("s", "a", [("capacity".to_owned(), "3".to_owned())].into())
            .expect("edge add should succeed");
        graph
            .add_edge_with_attrs("s", "b", [("capacity".to_owned(), "2".to_owned())].into())
            .expect("edge add should succeed");
        graph
            .add_edge_with_attrs("a", "b", [("capacity".to_owned(), "1".to_owned())].into())
            .expect("edge add should succeed");
        graph
            .add_edge_with_attrs("a", "t", [("capacity".to_owned(), "2".to_owned())].into())
            .expect("edge add should succeed");
        graph
            .add_edge_with_attrs("b", "t", [("capacity".to_owned(), "3".to_owned())].into())
            .expect("edge add should succeed");

        let result = minimum_cut_edmonds_karp(&graph, "s", "t", "capacity");
        assert!((result.value - 5.0).abs() <= 1e-12);
        assert_eq!(result.source_partition, vec!["s".to_owned()]);
        assert_eq!(
            result.sink_partition,
            vec!["a".to_owned(), "b".to_owned(), "t".to_owned()]
        );
        assert_eq!(result.witness.algorithm, "edmonds_karp_minimum_cut");
    }

    #[test]
    fn minimum_cut_edmonds_karp_is_replay_stable() {
        let mut graph = Graph::strict();
        graph
            .add_edge_with_attrs("s", "a", [("capacity".to_owned(), "4".to_owned())].into())
            .expect("edge add should succeed");
        graph
            .add_edge_with_attrs("s", "b", [("capacity".to_owned(), "2".to_owned())].into())
            .expect("edge add should succeed");
        graph
            .add_edge_with_attrs("a", "b", [("capacity".to_owned(), "1".to_owned())].into())
            .expect("edge add should succeed");
        graph
            .add_edge_with_attrs("a", "t", [("capacity".to_owned(), "2".to_owned())].into())
            .expect("edge add should succeed");
        graph
            .add_edge_with_attrs("b", "t", [("capacity".to_owned(), "3".to_owned())].into())
            .expect("edge add should succeed");

        let left = minimum_cut_edmonds_karp(&graph, "s", "t", "capacity");
        let right = minimum_cut_edmonds_karp(&graph, "s", "t", "capacity");
        assert_eq!(left, right);
    }

    #[test]
    fn minimum_cut_edmonds_karp_returns_empty_partitions_for_missing_nodes() {
        let mut graph = Graph::strict();
        let _ = graph.add_node("only");
        let result = minimum_cut_edmonds_karp(&graph, "missing", "only", "capacity");
        assert!((result.value - 0.0).abs() <= 1e-12);
        assert!(result.source_partition.is_empty());
        assert!(result.sink_partition.is_empty());
    }

    #[test]
    fn maximal_matching_matches_greedy_contract() {
        let mut graph = Graph::strict();
        graph.add_edge("1", "2").expect("edge add should succeed");
        graph.add_edge("1", "3").expect("edge add should succeed");
        graph.add_edge("2", "3").expect("edge add should succeed");
        graph.add_edge("2", "4").expect("edge add should succeed");
        graph.add_edge("3", "5").expect("edge add should succeed");
        graph.add_edge("4", "5").expect("edge add should succeed");

        let result = maximal_matching(&graph);
        assert_eq!(
            result.matching,
            vec![
                ("1".to_owned(), "2".to_owned()),
                ("3".to_owned(), "5".to_owned())
            ]
        );
        assert_eq!(result.witness.algorithm, "greedy_maximal_matching");
        assert_eq!(result.witness.complexity_claim, "O(|E|)");
        assert_eq!(result.witness.nodes_touched, 5);
        assert_eq!(result.witness.edges_scanned, 6);
        assert_eq!(result.witness.queue_peak, 0);
        assert_matching_is_valid_and_maximal(&graph, &result.matching);
    }

    #[test]
    fn maximal_matching_skips_self_loops() {
        let mut graph = Graph::strict();
        graph
            .add_edge("a", "a")
            .expect("self-loop add should succeed");
        graph.add_edge("a", "b").expect("edge add should succeed");
        graph.add_edge("b", "c").expect("edge add should succeed");

        let result = maximal_matching(&graph);
        assert_eq!(result.matching, vec![("a".to_owned(), "b".to_owned())]);
        assert_matching_is_valid_and_maximal(&graph, &result.matching);
    }

    #[test]
    fn maximal_matching_tie_break_tracks_edge_iteration_order() {
        let mut insertion_a = Graph::strict();
        insertion_a
            .add_edge("a", "b")
            .expect("edge add should succeed");
        insertion_a
            .add_edge("b", "c")
            .expect("edge add should succeed");
        insertion_a
            .add_edge("c", "d")
            .expect("edge add should succeed");
        insertion_a
            .add_edge("d", "a")
            .expect("edge add should succeed");

        let mut insertion_b = Graph::strict();
        insertion_b
            .add_edge("a", "d")
            .expect("edge add should succeed");
        insertion_b
            .add_edge("d", "c")
            .expect("edge add should succeed");
        insertion_b
            .add_edge("c", "b")
            .expect("edge add should succeed");
        insertion_b
            .add_edge("b", "a")
            .expect("edge add should succeed");

        let left = maximal_matching(&insertion_a);
        let left_replay = maximal_matching(&insertion_a);
        let right = maximal_matching(&insertion_b);
        let right_replay = maximal_matching(&insertion_b);

        assert_eq!(
            left.matching,
            vec![
                ("a".to_owned(), "b".to_owned()),
                ("c".to_owned(), "d".to_owned())
            ]
        );
        assert_eq!(
            right.matching,
            vec![
                ("a".to_owned(), "d".to_owned()),
                ("c".to_owned(), "b".to_owned())
            ]
        );
        assert_eq!(left, left_replay);
        assert_eq!(right, right_replay);
        assert_matching_is_valid_and_maximal(&insertion_a, &left.matching);
        assert_matching_is_valid_and_maximal(&insertion_b, &right.matching);
    }

    #[test]
    fn maximal_matching_empty_graph_is_empty() {
        let graph = Graph::strict();
        let result = maximal_matching(&graph);
        assert!(result.matching.is_empty());
        assert_eq!(result.witness.nodes_touched, 0);
        assert_eq!(result.witness.edges_scanned, 0);
    }

    #[test]
    fn is_matching_accepts_valid_matching() {
        let mut graph = Graph::strict();
        graph.add_edge("a", "b").expect("edge add should succeed");
        graph.add_edge("b", "c").expect("edge add should succeed");
        graph.add_edge("c", "d").expect("edge add should succeed");
        graph.add_edge("d", "a").expect("edge add should succeed");

        let matching = vec![
            ("a".to_owned(), "b".to_owned()),
            ("c".to_owned(), "d".to_owned()),
        ];
        assert!(is_matching(&graph, &matching));
    }

    #[test]
    fn is_matching_rejects_invalid_matching() {
        let mut graph = Graph::strict();
        graph.add_edge("a", "b").expect("edge add should succeed");
        graph.add_edge("a", "c").expect("edge add should succeed");

        let shared_endpoint = vec![
            ("a".to_owned(), "b".to_owned()),
            ("a".to_owned(), "c".to_owned()),
        ];
        assert!(!is_matching(&graph, &shared_endpoint));

        let missing_node = vec![("a".to_owned(), "z".to_owned())];
        assert!(!is_matching(&graph, &missing_node));

        let self_loop = vec![("a".to_owned(), "a".to_owned())];
        assert!(!is_matching(&graph, &self_loop));
    }

    #[test]
    fn is_maximal_matching_detects_augmentable_edge() {
        let mut graph = Graph::strict();
        graph.add_edge("a", "b").expect("edge add should succeed");
        graph.add_edge("b", "c").expect("edge add should succeed");
        graph.add_edge("c", "d").expect("edge add should succeed");

        let non_maximal = vec![("a".to_owned(), "b".to_owned())];
        assert!(!is_maximal_matching(&graph, &non_maximal));

        let maximal = vec![
            ("a".to_owned(), "b".to_owned()),
            ("c".to_owned(), "d".to_owned()),
        ];
        assert!(is_maximal_matching(&graph, &maximal));
    }

    #[test]
    fn is_perfect_matching_requires_all_nodes_covered() {
        let mut graph = Graph::strict();
        graph.add_edge("a", "b").expect("edge add should succeed");
        graph.add_edge("b", "c").expect("edge add should succeed");
        graph.add_edge("c", "d").expect("edge add should succeed");
        graph.add_edge("d", "a").expect("edge add should succeed");

        let perfect = vec![
            ("a".to_owned(), "b".to_owned()),
            ("c".to_owned(), "d".to_owned()),
        ];
        assert!(is_perfect_matching(&graph, &perfect));

        let non_perfect = vec![("a".to_owned(), "b".to_owned())];
        assert!(!is_perfect_matching(&graph, &non_perfect));
    }

    #[test]
    fn is_perfect_matching_empty_graph_is_true() {
        let graph = Graph::strict();
        let matching = Vec::<(String, String)>::new();
        assert!(is_perfect_matching(&graph, &matching));
    }

    #[test]
    fn max_weight_matching_prefers_higher_total_weight() {
        let mut graph = Graph::strict();
        graph
            .add_edge_with_attrs("1", "2", [("weight".to_owned(), "6".to_owned())].into())
            .expect("edge add should succeed");
        graph
            .add_edge_with_attrs("1", "3", [("weight".to_owned(), "2".to_owned())].into())
            .expect("edge add should succeed");
        graph
            .add_edge_with_attrs("2", "3", [("weight".to_owned(), "1".to_owned())].into())
            .expect("edge add should succeed");
        graph
            .add_edge_with_attrs("2", "4", [("weight".to_owned(), "7".to_owned())].into())
            .expect("edge add should succeed");
        graph
            .add_edge_with_attrs("3", "5", [("weight".to_owned(), "9".to_owned())].into())
            .expect("edge add should succeed");
        graph
            .add_edge_with_attrs("4", "5", [("weight".to_owned(), "3".to_owned())].into())
            .expect("edge add should succeed");

        let result = max_weight_matching(&graph, false, "weight");
        assert_eq!(
            result.matching,
            vec![
                ("3".to_owned(), "5".to_owned()),
                ("2".to_owned(), "4".to_owned())
            ]
        );
        assert!((result.total_weight - 16.0).abs() <= 1e-12);
        assert_eq!(result.witness.algorithm, "greedy_max_weight_matching");
        assert_matching_is_valid_and_maximal(&graph, &result.matching);
    }

    #[test]
    fn max_weight_matching_maxcardinality_prefers_larger_matching() {
        let mut graph = Graph::strict();
        graph
            .add_edge_with_attrs("a", "b", [("weight".to_owned(), "100".to_owned())].into())
            .expect("edge add should succeed");
        graph
            .add_edge_with_attrs("a", "c", [("weight".to_owned(), "60".to_owned())].into())
            .expect("edge add should succeed");
        graph
            .add_edge_with_attrs("b", "d", [("weight".to_owned(), "60".to_owned())].into())
            .expect("edge add should succeed");

        let default_result = max_weight_matching(&graph, false, "weight");
        assert_eq!(
            default_result.matching,
            vec![("a".to_owned(), "b".to_owned())]
        );
        assert!((default_result.total_weight - 100.0).abs() <= 1e-12);

        let maxcard_result = max_weight_matching(&graph, true, "weight");
        assert_eq!(
            maxcard_result.matching,
            vec![
                ("a".to_owned(), "c".to_owned()),
                ("b".to_owned(), "d".to_owned())
            ]
        );
        assert!((maxcard_result.total_weight - 120.0).abs() <= 1e-12);
        assert_eq!(
            maxcard_result.witness.algorithm,
            "greedy_max_weight_matching_maxcardinality"
        );
        assert_matching_is_valid_and_maximal(&graph, &maxcard_result.matching);
    }

    #[test]
    fn min_weight_matching_uses_weight_inversion_contract() {
        let mut graph = Graph::strict();
        graph
            .add_edge_with_attrs("a", "b", [("weight".to_owned(), "10".to_owned())].into())
            .expect("edge add should succeed");
        graph
            .add_edge_with_attrs("a", "c", [("weight".to_owned(), "1".to_owned())].into())
            .expect("edge add should succeed");
        graph
            .add_edge_with_attrs("b", "d", [("weight".to_owned(), "1".to_owned())].into())
            .expect("edge add should succeed");
        graph
            .add_edge_with_attrs("c", "d", [("weight".to_owned(), "10".to_owned())].into())
            .expect("edge add should succeed");

        let result = min_weight_matching(&graph, "weight");
        assert_eq!(
            result.matching,
            vec![
                ("a".to_owned(), "c".to_owned()),
                ("b".to_owned(), "d".to_owned())
            ]
        );
        assert!((result.total_weight - 2.0).abs() <= 1e-12);
        assert_eq!(result.witness.algorithm, "greedy_min_weight_matching");
        assert_matching_is_valid_and_maximal(&graph, &result.matching);
    }

    #[test]
    fn min_weight_matching_defaults_missing_weight_to_one() {
        let mut graph = Graph::strict();
        graph.add_edge("a", "b").expect("edge add should succeed");
        graph
            .add_edge_with_attrs("a", "c", [("weight".to_owned(), "3".to_owned())].into())
            .expect("edge add should succeed");
        graph
            .add_edge_with_attrs("b", "c", [("weight".to_owned(), "2".to_owned())].into())
            .expect("edge add should succeed");

        let result = min_weight_matching(&graph, "weight");
        assert_eq!(result.matching, vec![("a".to_owned(), "b".to_owned())]);
        assert!((result.total_weight - 1.0).abs() <= 1e-12);
    }

    #[test]
    fn weighted_matching_empty_graph_is_empty() {
        let graph = Graph::strict();
        let max_result = max_weight_matching(&graph, false, "weight");
        let min_result = min_weight_matching(&graph, "weight");

        assert!(max_result.matching.is_empty());
        assert!((max_result.total_weight - 0.0).abs() <= 1e-12);
        assert_eq!(max_result.witness.nodes_touched, 0);

        assert!(min_result.matching.is_empty());
        assert!((min_result.total_weight - 0.0).abs() <= 1e-12);
        assert_eq!(min_result.witness.nodes_touched, 0);
    }

    #[test]
    fn returns_none_when_nodes_are_missing() {
        let graph = Graph::strict();
        let result = shortest_path_unweighted(&graph, "a", "b");
        assert_eq!(result.path, None);
    }

    #[test]
    fn cgse_witness_artifact_skeleton_is_stable_and_deterministic() {
        let witness = ComplexityWitness {
            algorithm: "bfs_shortest_path".to_owned(),
            complexity_claim: "O(|V| + |E|)".to_owned(),
            nodes_touched: 7,
            edges_scanned: 12,
            queue_peak: 3,
        };
        let left = witness.to_cgse_witness_artifact(
            "shortest_path_algorithms",
            "shortest_path_unweighted",
            &[
                "artifacts/cgse/latest/cgse_deterministic_policy_spec_validation_v1.json",
                CGSE_WITNESS_POLICY_SPEC_PATH,
            ],
        );
        let right = witness.to_cgse_witness_artifact(
            "shortest_path_algorithms",
            "shortest_path_unweighted",
            &[
                CGSE_WITNESS_POLICY_SPEC_PATH,
                "artifacts/cgse/latest/cgse_deterministic_policy_spec_validation_v1.json",
            ],
        );
        assert_eq!(cgse_witness_schema_version(), "1.0.0");
        assert_eq!(left, right);
        assert_eq!(left.schema_version, "1.0.0");
        assert_eq!(left.algorithm_family, "shortest_path_algorithms");
        assert_eq!(left.operation, "shortest_path_unweighted");
        assert!(
            left.artifact_refs
                .contains(&CGSE_WITNESS_POLICY_SPEC_PATH.to_owned()),
            "witness must include policy spec path"
        );
        assert!(
            left.artifact_refs
                .contains(&CGSE_WITNESS_LEDGER_PATH.to_owned()),
            "witness must include legacy tiebreak ledger path"
        );
        assert!(left.witness_hash_id.starts_with("cgse-witness:"));
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
    fn centrality_and_component_outputs_are_deterministic_under_insertion_order_noise() {
        let mut forward = Graph::strict();
        for (left, right) in [("n0", "n1"), ("n1", "n2"), ("n2", "n3"), ("n0", "n3")] {
            forward
                .add_edge(left, right)
                .expect("edge add should succeed");
        }
        let _ = forward.add_node("noise_a");
        let _ = forward.add_node("noise_b");

        let mut reverse = Graph::strict();
        for (left, right) in [("n0", "n3"), ("n2", "n3"), ("n1", "n2"), ("n0", "n1")] {
            reverse
                .add_edge(left, right)
                .expect("edge add should succeed");
        }
        let _ = reverse.add_node("noise_b");
        let _ = reverse.add_node("noise_a");

        let forward_components = connected_components(&forward);
        let forward_components_replay = connected_components(&forward);
        let reverse_components = connected_components(&reverse);
        let reverse_components_replay = connected_components(&reverse);
        assert_eq!(
            forward_components.components,
            forward_components_replay.components
        );
        assert_eq!(
            reverse_components.components,
            reverse_components_replay.components
        );

        let normalize_components = |components: Vec<Vec<String>>| {
            let mut normalized = components
                .into_iter()
                .map(|mut component| {
                    component.sort();
                    component
                })
                .collect::<Vec<Vec<String>>>();
            normalized.sort();
            normalized
        };
        assert_eq!(
            normalize_components(forward_components.components),
            normalize_components(reverse_components.components)
        );

        let forward_count = number_connected_components(&forward);
        let reverse_count = number_connected_components(&reverse);
        assert_eq!(forward_count.count, reverse_count.count);

        let forward_degree = degree_centrality(&forward);
        let forward_degree_replay = degree_centrality(&forward);
        let reverse_degree = degree_centrality(&reverse);
        let reverse_degree_replay = degree_centrality(&reverse);
        assert_eq!(forward_degree.scores, forward_degree_replay.scores);
        assert_eq!(reverse_degree.scores, reverse_degree_replay.scores);

        let as_score_map = |scores: Vec<CentralityScore>| -> BTreeMap<String, f64> {
            scores
                .into_iter()
                .map(|entry| (entry.node, entry.score))
                .collect::<BTreeMap<String, f64>>()
        };
        assert_eq!(
            as_score_map(forward_degree.scores),
            as_score_map(reverse_degree.scores)
        );

        let forward_closeness = closeness_centrality(&forward);
        let forward_closeness_replay = closeness_centrality(&forward);
        let reverse_closeness = closeness_centrality(&reverse);
        let reverse_closeness_replay = closeness_centrality(&reverse);
        assert_eq!(forward_closeness.scores, forward_closeness_replay.scores);
        assert_eq!(reverse_closeness.scores, reverse_closeness_replay.scores);
        assert_eq!(
            as_score_map(forward_closeness.scores),
            as_score_map(reverse_closeness.scores)
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
    fn betweenness_centrality_path_graph_matches_expected_values() {
        let mut graph = Graph::strict();
        graph.add_edge("a", "b").expect("edge add should succeed");
        graph.add_edge("b", "c").expect("edge add should succeed");
        graph.add_edge("c", "d").expect("edge add should succeed");

        let result = betweenness_centrality(&graph);
        let expected = [
            ("a", 0.0_f64),
            ("b", 2.0 / 3.0),
            ("c", 2.0 / 3.0),
            ("d", 0.0_f64),
        ];
        for (actual, (exp_node, exp_score)) in result.scores.iter().zip(expected) {
            assert_eq!(actual.node, exp_node);
            assert!((actual.score - exp_score).abs() <= 1e-12);
        }
        assert_eq!(result.witness.algorithm, "brandes_betweenness_centrality");
        assert_eq!(result.witness.complexity_claim, "O(|V| * |E|)");
    }

    #[test]
    fn betweenness_centrality_star_graph_center_is_one() {
        let mut graph = Graph::strict();
        graph.add_edge("c", "l1").expect("edge add should succeed");
        graph.add_edge("c", "l2").expect("edge add should succeed");
        graph.add_edge("c", "l3").expect("edge add should succeed");
        graph.add_edge("c", "l4").expect("edge add should succeed");

        let result = betweenness_centrality(&graph);
        let mut center_seen = false;
        for score in result.scores {
            if score.node == "c" {
                center_seen = true;
                assert!((score.score - 1.0).abs() <= 1e-12);
            } else {
                assert!(score.node.starts_with('l'));
                assert!((score.score - 0.0).abs() <= 1e-12);
            }
        }
        assert!(center_seen);
    }

    #[test]
    fn betweenness_centrality_cycle_graph_distributes_evenly() {
        let mut graph = Graph::strict();
        graph.add_edge("a", "b").expect("edge add should succeed");
        graph.add_edge("b", "c").expect("edge add should succeed");
        graph.add_edge("c", "d").expect("edge add should succeed");
        graph.add_edge("d", "a").expect("edge add should succeed");

        let result = betweenness_centrality(&graph);
        for score in result.scores {
            assert!((score.score - (1.0 / 6.0)).abs() <= 1e-12);
        }
    }

    #[test]
    fn betweenness_centrality_is_replay_stable_under_insertion_order_noise() {
        let mut forward = Graph::strict();
        for (left, right) in [("n0", "n1"), ("n1", "n2"), ("n2", "n3"), ("n0", "n3")] {
            forward
                .add_edge(left, right)
                .expect("edge add should succeed");
        }
        let _ = forward.add_node("noise_a");

        let mut reverse = Graph::strict();
        for (left, right) in [("n0", "n3"), ("n2", "n3"), ("n1", "n2"), ("n0", "n1")] {
            reverse
                .add_edge(left, right)
                .expect("edge add should succeed");
        }
        let _ = reverse.add_node("noise_a");

        let forward_once = betweenness_centrality(&forward);
        let forward_twice = betweenness_centrality(&forward);
        let reverse_once = betweenness_centrality(&reverse);
        let reverse_twice = betweenness_centrality(&reverse);

        assert_eq!(forward_once, forward_twice);
        assert_eq!(reverse_once, reverse_twice);

        let as_score_map = |scores: Vec<CentralityScore>| -> BTreeMap<String, f64> {
            scores
                .into_iter()
                .map(|entry| (entry.node, entry.score))
                .collect::<BTreeMap<String, f64>>()
        };
        let forward_map = as_score_map(forward_once.scores);
        let reverse_map = as_score_map(reverse_once.scores);
        assert_eq!(
            forward_map.keys().collect::<Vec<&String>>(),
            reverse_map.keys().collect::<Vec<&String>>()
        );
        for key in forward_map.keys() {
            let left = *forward_map.get(key).unwrap_or(&0.0);
            let right = *reverse_map.get(key).unwrap_or(&0.0);
            assert!(
                (left - right).abs() <= 1e-12,
                "score mismatch for node {key}"
            );
        }
    }

    #[test]
    fn betweenness_centrality_empty_and_small_graphs_are_zero_or_empty() {
        let empty = Graph::strict();
        let empty_result = betweenness_centrality(&empty);
        assert!(empty_result.scores.is_empty());

        let mut singleton = Graph::strict();
        let _ = singleton.add_node("solo");
        let singleton_result = betweenness_centrality(&singleton);
        assert_eq!(singleton_result.scores.len(), 1);
        assert_eq!(singleton_result.scores[0].node, "solo");
        assert!((singleton_result.scores[0].score - 0.0).abs() <= 1e-12);

        let mut pair = Graph::strict();
        pair.add_edge("a", "b").expect("edge add should succeed");
        let pair_result = betweenness_centrality(&pair);
        for score in pair_result.scores {
            assert!((score.score - 0.0).abs() <= 1e-12);
        }
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
        environment.insert("policy_row_id".to_owned(), "CGSE-POL-R08".to_owned());

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
            environment.insert("policy_row_id".to_owned(), "CGSE-POL-R08".to_owned());

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

        #[test]
        fn property_packet_005_insertion_permutation_and_noise_are_replay_stable(
            edges in prop::collection::vec((0_u8..8, 0_u8..8), 1..40),
            noise_nodes in prop::collection::vec(0_u8..8, 0..12)
        ) {
            let mut forward = Graph::strict();
            for (left, right) in &edges {
                let left_node = format!("n{left}");
                let right_node = format!("n{right}");
                let _ = forward.add_node(&left_node);
                let _ = forward.add_node(&right_node);
                forward
                    .add_edge(&left_node, &right_node)
                    .expect("forward edge insertion should succeed");
            }

            let mut reverse = Graph::strict();
            for (left, right) in edges.iter().rev() {
                let left_node = format!("n{left}");
                let right_node = format!("n{right}");
                let _ = reverse.add_node(&left_node);
                let _ = reverse.add_node(&right_node);
                reverse
                    .add_edge(&left_node, &right_node)
                    .expect("reverse edge insertion should succeed");
            }

            for noise in &noise_nodes {
                let node = format!("z{noise}");
                let _ = forward.add_node(&node);
                let _ = reverse.add_node(&node);
            }

            let forward_nodes = forward
                .nodes_ordered()
                .into_iter()
                .map(str::to_owned)
                .collect::<Vec<String>>();
            let reverse_nodes = reverse
                .nodes_ordered()
                .into_iter()
                .map(str::to_owned)
                .collect::<Vec<String>>();
            let mut forward_node_set = forward_nodes.clone();
            forward_node_set.sort();
            let mut reverse_node_set = reverse_nodes.clone();
            reverse_node_set.sort();
            prop_assert_eq!(
                &forward_node_set, &reverse_node_set,
                "P2C005-INV-2 node membership must remain stable under insertion perturbation"
            );
            prop_assume!(!forward_nodes.is_empty());

            let source = forward_node_set.first().expect("source exists").clone();
            let target = forward_node_set.last().expect("target exists").clone();

            let forward_path = shortest_path_unweighted(&forward, &source, &target);
            let forward_path_replay = shortest_path_unweighted(&forward, &source, &target);
            let reverse_path = shortest_path_unweighted(&reverse, &source, &target);
            let reverse_path_replay = shortest_path_unweighted(&reverse, &source, &target);
            prop_assert_eq!(
                &forward_path.path, &forward_path_replay.path,
                "P2C005-INV-2 shortest-path output must be replay-stable for forward insertion"
            );
            prop_assert_eq!(
                &forward_path.witness, &forward_path_replay.witness,
                "P2C005-INV-2 shortest-path witness must be replay-stable for forward insertion"
            );
            prop_assert_eq!(
                &reverse_path.path, &reverse_path_replay.path,
                "P2C005-INV-2 shortest-path output must be replay-stable for reverse insertion"
            );
            prop_assert_eq!(
                &reverse_path.witness, &reverse_path_replay.witness,
                "P2C005-INV-2 shortest-path witness must be replay-stable for reverse insertion"
            );
            prop_assert_eq!(
                forward_path.path.as_ref().map(Vec::len),
                reverse_path.path.as_ref().map(Vec::len),
                "P2C005-INV-2 shortest-path hop count should remain stable across insertion perturbation"
            );

            let forward_components = connected_components(&forward);
            let forward_components_replay = connected_components(&forward);
            let reverse_components = connected_components(&reverse);
            let reverse_components_replay = connected_components(&reverse);
            prop_assert_eq!(
                &forward_components.components, &forward_components_replay.components,
                "P2C005-INV-2 components must be replay-stable for forward insertion"
            );
            prop_assert_eq!(
                &reverse_components.components, &reverse_components_replay.components,
                "P2C005-INV-2 components must be replay-stable for reverse insertion"
            );
            let normalize_components = |components: &[Vec<String>]| {
                let mut normalized = components
                    .iter()
                    .map(|component| {
                        let mut component = component.clone();
                        component.sort();
                        component
                    })
                    .collect::<Vec<Vec<String>>>();
                normalized.sort();
                normalized
            };
            prop_assert_eq!(
                normalize_components(&forward_components.components),
                normalize_components(&reverse_components.components),
                "P2C005-INV-2 component membership must remain stable under insertion perturbation"
            );

            let forward_count = number_connected_components(&forward);
            let reverse_count = number_connected_components(&reverse);
            prop_assert_eq!(
                forward_count.count, reverse_count.count,
                "P2C005-INV-2 component counts must remain stable"
            );

            let forward_degree = degree_centrality(&forward);
            let forward_degree_replay = degree_centrality(&forward);
            let reverse_degree = degree_centrality(&reverse);
            let reverse_degree_replay = degree_centrality(&reverse);
            prop_assert_eq!(
                &forward_degree.scores, &forward_degree_replay.scores,
                "P2C005-INV-2 degree-centrality must be replay-stable for forward insertion"
            );
            prop_assert_eq!(
                &reverse_degree.scores, &reverse_degree_replay.scores,
                "P2C005-INV-2 degree-centrality must be replay-stable for reverse insertion"
            );
            let as_score_map = |scores: &[CentralityScore]| -> BTreeMap<String, f64> {
                scores
                    .iter()
                    .map(|entry| (entry.node.clone(), entry.score))
                    .collect::<BTreeMap<String, f64>>()
            };
            prop_assert_eq!(
                as_score_map(&forward_degree.scores),
                as_score_map(&reverse_degree.scores),
                "P2C005-INV-2 degree-centrality scores must remain stable by node"
            );

            let forward_closeness = closeness_centrality(&forward);
            let forward_closeness_replay = closeness_centrality(&forward);
            let reverse_closeness = closeness_centrality(&reverse);
            let reverse_closeness_replay = closeness_centrality(&reverse);
            prop_assert_eq!(
                &forward_closeness.scores, &forward_closeness_replay.scores,
                "P2C005-INV-2 closeness-centrality must be replay-stable for forward insertion"
            );
            prop_assert_eq!(
                &reverse_closeness.scores, &reverse_closeness_replay.scores,
                "P2C005-INV-2 closeness-centrality must be replay-stable for reverse insertion"
            );
            prop_assert_eq!(
                as_score_map(&forward_closeness.scores),
                as_score_map(&reverse_closeness.scores),
                "P2C005-INV-2 closeness-centrality scores must remain stable by node"
            );

            let deterministic_seed = edges.iter().fold(7305_u64, |acc, (left_edge, right_edge)| {
                acc.wrapping_mul(131)
                    .wrapping_add((*left_edge as u64) << 8)
                    .wrapping_add(*right_edge as u64)
            }).wrapping_add(
                noise_nodes
                    .iter()
                    .fold(0_u64, |acc, noise| acc.wrapping_mul(17).wrapping_add(*noise as u64))
            );

            let mut environment = BTreeMap::new();
            environment.insert("os".to_owned(), std::env::consts::OS.to_owned());
            environment.insert("arch".to_owned(), std::env::consts::ARCH.to_owned());
            environment.insert("graph_fingerprint".to_owned(), graph_fingerprint(&forward));
            environment.insert("tie_break_policy".to_owned(), "lexical_neighbor_order".to_owned());
            environment.insert("invariant_id".to_owned(), "P2C005-INV-2".to_owned());
            environment.insert("policy_row_id".to_owned(), "CGSE-POL-R08".to_owned());
            environment.insert(
                "perturbation_model".to_owned(),
                "reverse_insertion_plus_noise_nodes".to_owned(),
            );

            let replay_command =
                "rch exec -- cargo test -p fnx-algorithms property_packet_005_insertion_permutation_and_noise_are_replay_stable -- --nocapture";
            let log = StructuredTestLog {
                schema_version: structured_test_log_schema_version().to_owned(),
                run_id: "algorithms-p2c005-property-perturbation".to_owned(),
                ts_unix_ms: 3,
                crate_name: "fnx-algorithms".to_owned(),
                suite_id: "property".to_owned(),
                packet_id: "FNX-P2C-005".to_owned(),
                test_name: "property_packet_005_insertion_permutation_and_noise_are_replay_stable".to_owned(),
                test_id: "property::fnx-p2c-005::invariants".to_owned(),
                test_kind: TestKind::Property,
                mode: CompatibilityMode::Hardened,
                fixture_id: Some("algorithms::property::permutation_noise_matrix".to_owned()),
                seed: Some(deterministic_seed),
                env_fingerprint: canonical_environment_fingerprint(&environment),
                environment,
                duration_ms: 15,
                replay_command: replay_command.to_owned(),
                artifact_refs: vec![
                    "artifacts/conformance/latest/structured_log_emitter_normalization_report.json"
                        .to_owned(),
                ],
                forensic_bundle_id: "forensics::algorithms::property::permutation_noise".to_owned(),
                hash_id: "sha256:algorithms-p2c005-property-permutation".to_owned(),
                status: TestStatus::Passed,
                reason_code: None,
                failure_repro: None,
                e2e_step_traces: Vec::new(),
                forensics_bundle_index: Some(packet_005_forensics_bundle(
                    "algorithms-p2c005-property-perturbation",
                    "property::fnx-p2c-005::invariants",
                    replay_command,
                    "forensics::algorithms::property::permutation_noise",
                    vec![
                        "artifacts/conformance/latest/structured_log_emitter_normalization_report.json"
                            .to_owned(),
                    ],
                )),
            };
            prop_assert!(
                log.validate().is_ok(),
                "packet-005 perturbation telemetry log should satisfy strict schema"
            );
        }
    }
}
