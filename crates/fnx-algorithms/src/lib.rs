#![forbid(unsafe_code)]

use fnx_classes::Graph;
use mwmatching::{Matching as BlossomMatching, SENTINEL as BLOSSOM_SENTINEL};
use serde::{Deserialize, Serialize};
use std::collections::{HashMap, HashSet, VecDeque};

pub const CGSE_WITNESS_ARTIFACT_SCHEMA_VERSION_V1: &str = "1.0.0";
pub const CGSE_WITNESS_POLICY_SPEC_PATH: &str =
    "artifacts/cgse/v1/cgse_deterministic_policy_spec_v1.json";
pub const CGSE_WITNESS_LEDGER_PATH: &str =
    "artifacts/cgse/v1/cgse_legacy_tiebreak_ordering_ledger_v1.json";
const PAGERANK_DEFAULT_ALPHA: f64 = 0.85;
const PAGERANK_DEFAULT_MAX_ITERATIONS: usize = 100;
const PAGERANK_DEFAULT_TOLERANCE: f64 = 1.0e-6;
const KATZ_DEFAULT_ALPHA: f64 = 0.1;
const KATZ_DEFAULT_BETA: f64 = 1.0;
const KATZ_DEFAULT_MAX_ITERATIONS: usize = 1000;
const KATZ_DEFAULT_TOLERANCE: f64 = 1.0e-6;
const HITS_DEFAULT_MAX_ITERATIONS: usize = 100;
const HITS_DEFAULT_TOLERANCE: f64 = 1.0e-8;
const DISTANCE_COMPARISON_EPSILON: f64 = 1.0e-12;

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

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct WeightedDistanceEntry {
    pub node: String,
    pub distance: f64,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct WeightedPredecessorEntry {
    pub node: String,
    pub predecessor: Option<String>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct WeightedShortestPathsResult {
    pub distances: Vec<WeightedDistanceEntry>,
    pub predecessors: Vec<WeightedPredecessorEntry>,
    pub negative_cycle_detected: bool,
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
pub struct HarmonicCentralityResult {
    pub scores: Vec<CentralityScore>,
    pub witness: ComplexityWitness,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct KatzCentralityResult {
    pub scores: Vec<CentralityScore>,
    pub witness: ComplexityWitness,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct HitsCentralityResult {
    pub hubs: Vec<CentralityScore>,
    pub authorities: Vec<CentralityScore>,
    pub witness: ComplexityWitness,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct PageRankResult {
    pub scores: Vec<CentralityScore>,
    pub witness: ComplexityWitness,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct EigenvectorCentralityResult {
    pub scores: Vec<CentralityScore>,
    pub witness: ComplexityWitness,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct BetweennessCentralityResult {
    pub scores: Vec<CentralityScore>,
    pub witness: ComplexityWitness,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct EdgeCentralityScore {
    pub left: String,
    pub right: String,
    pub score: f64,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct EdgeBetweennessCentralityResult {
    pub scores: Vec<EdgeCentralityScore>,
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

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct EdgeCutResult {
    pub value: f64,
    pub cut_edges: Vec<(String, String)>,
    pub source_partition: Vec<String>,
    pub sink_partition: Vec<String>,
    pub witness: ComplexityWitness,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct EdgeConnectivityResult {
    pub value: f64,
    pub witness: ComplexityWitness,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct GlobalEdgeCutResult {
    pub value: f64,
    pub source: String,
    pub sink: String,
    pub cut_edges: Vec<(String, String)>,
    pub source_partition: Vec<String>,
    pub sink_partition: Vec<String>,
    pub witness: ComplexityWitness,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct ArticulationPointsResult {
    pub nodes: Vec<String>,
    pub witness: ComplexityWitness,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct BridgesResult {
    pub edges: Vec<(String, String)>,
    pub witness: ComplexityWitness,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct ClusteringCoefficientResult {
    pub scores: Vec<CentralityScore>,
    pub average_clustering: f64,
    pub transitivity: f64,
    pub witness: ComplexityWitness,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct EccentricityEntry {
    pub node: String,
    pub value: usize,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct DistanceMeasuresResult {
    pub eccentricity: Vec<EccentricityEntry>,
    pub diameter: usize,
    pub radius: usize,
    pub center: Vec<String>,
    pub periphery: Vec<String>,
    pub witness: ComplexityWitness,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct AverageShortestPathLengthResult {
    pub average_shortest_path_length: f64,
    pub witness: ComplexityWitness,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct IsConnectedResult {
    pub is_connected: bool,
    pub witness: ComplexityWitness,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct DensityResult {
    pub density: f64,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct HasPathResult {
    pub has_path: bool,
    pub witness: ComplexityWitness,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ShortestPathLengthResult {
    pub length: Option<usize>,
    pub witness: ComplexityWitness,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct MstEdge {
    pub left: String,
    pub right: String,
    pub weight: f64,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct MinimumSpanningTreeResult {
    pub edges: Vec<MstEdge>,
    pub total_weight: f64,
    pub witness: ComplexityWitness,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct TrianglesResult {
    pub triangles: Vec<NodeTriangleCount>,
    pub witness: ComplexityWitness,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct NodeTriangleCount {
    pub node: String,
    pub count: usize,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct SquareClusteringResult {
    pub scores: Vec<CentralityScore>,
    pub witness: ComplexityWitness,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct IsTreeResult {
    pub is_tree: bool,
    pub witness: ComplexityWitness,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct IsForestResult {
    pub is_forest: bool,
    pub witness: ComplexityWitness,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct IsBipartiteResult {
    pub is_bipartite: bool,
    pub witness: ComplexityWitness,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct BipartiteSetsResult {
    pub is_bipartite: bool,
    pub set_a: Vec<String>,
    pub set_b: Vec<String>,
    pub witness: ComplexityWitness,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct NodeColor {
    pub node: String,
    pub color: usize,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct GreedyColorResult {
    pub coloring: Vec<NodeColor>,
    pub num_colors: usize,
    pub witness: ComplexityWitness,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct NodeCoreNumber {
    pub node: String,
    pub core: usize,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct CoreNumberResult {
    pub core_numbers: Vec<NodeCoreNumber>,
    pub witness: ComplexityWitness,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct NodeAvgNeighborDegree {
    pub node: String,
    pub avg_neighbor_degree: f64,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct AverageNeighborDegreeResult {
    pub scores: Vec<NodeAvgNeighborDegree>,
    pub witness: ComplexityWitness,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct DegreeAssortativityResult {
    pub coefficient: f64,
    pub witness: ComplexityWitness,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct VoterankResult {
    pub ranked: Vec<String>,
    pub witness: ComplexityWitness,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct FindCliquesResult {
    /// Each inner Vec is a maximal clique (sorted node names), outer Vec sorted lexicographically.
    pub cliques: Vec<Vec<String>>,
    pub witness: ComplexityWitness,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct GraphCliqueNumberResult {
    /// Size of the largest maximal clique.
    pub clique_number: usize,
    pub witness: ComplexityWitness,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct NodeConnectivityResult {
    pub value: usize,
    pub witness: ComplexityWitness,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct MinimumNodeCutResult {
    pub cut_nodes: Vec<String>,
    pub witness: ComplexityWitness,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct CycleBasisResult {
    /// Each inner Vec is a cycle (list of node names forming the cycle).
    pub cycles: Vec<Vec<String>>,
    pub witness: ComplexityWitness,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct GlobalEfficiencyResult {
    pub efficiency: f64,
    pub witness: ComplexityWitness,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct LocalEfficiencyResult {
    pub efficiency: f64,
    pub witness: ComplexityWitness,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct MinEdgeCoverResult {
    /// Edges forming the minimum edge cover, each as (left, right) sorted.
    pub edges: Vec<(String, String)>,
    pub witness: ComplexityWitness,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct AllSimplePathsResult {
    /// Each inner Vec is a simple path (list of node names from source to target).
    pub paths: Vec<Vec<String>>,
    pub witness: ComplexityWitness,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct IsEulerianResult {
    pub is_eulerian: bool,
    pub witness: ComplexityWitness,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct HasEulerianPathResult {
    pub has_eulerian_path: bool,
    pub witness: ComplexityWitness,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct IsSemiEulerianResult {
    pub is_semieulerian: bool,
    pub witness: ComplexityWitness,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct EulerianCircuitResult {
    /// Edges of the Eulerian circuit in traversal order, each as (from, to).
    pub edges: Vec<(String, String)>,
    pub witness: ComplexityWitness,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct EulerianPathResult {
    /// Edges of the Eulerian path in traversal order, each as (from, to).
    pub edges: Vec<(String, String)>,
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
                Some(existing_distance) => {
                    candidate_distance + DISTANCE_COMPARISON_EPSILON < *existing_distance
                }
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
pub fn multi_source_dijkstra(
    graph: &Graph,
    sources: &[&str],
    weight_attr: &str,
) -> WeightedShortestPathsResult {
    let ordered_nodes = graph.nodes_ordered();
    let mut settled = HashSet::<String>::new();
    let mut distances = HashMap::<String, f64>::new();
    let mut predecessors = HashMap::<String, Option<String>>::new();
    let mut seen_sources = HashSet::<&str>::new();

    let mut nodes_touched = 0usize;
    let mut edges_scanned = 0usize;
    let mut queue_peak = 0usize;

    for source in sources {
        if !graph.has_node(source) || !seen_sources.insert(source) {
            continue;
        }
        distances.insert((*source).to_owned(), 0.0);
        predecessors.insert((*source).to_owned(), None);
        nodes_touched += 1;
    }

    queue_peak = queue_peak.max(distances.len());

    loop {
        let mut current: Option<(&str, f64)> = None;
        for &node in &ordered_nodes {
            if settled.contains(node) {
                continue;
            }
            let Some(&candidate_distance) = distances.get(node) else {
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
        settled.insert(current_node.to_owned());

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
            let should_update = match distances.get(neighbor) {
                Some(existing_distance) => {
                    candidate_distance + DISTANCE_COMPARISON_EPSILON < *existing_distance
                }
                None => true,
            };
            if should_update {
                if distances
                    .insert(neighbor.to_owned(), candidate_distance)
                    .is_none()
                {
                    nodes_touched += 1;
                }
                predecessors.insert(neighbor.to_owned(), Some(current_node.to_owned()));
            }
        }

        queue_peak = queue_peak.max(distances.len().saturating_sub(settled.len()));
    }

    weighted_paths_result(
        &ordered_nodes,
        distances,
        predecessors,
        false,
        ComplexityWitness {
            algorithm: "multi_source_dijkstra".to_owned(),
            complexity_claim: "O(|V|^2 + |E|)".to_owned(),
            nodes_touched,
            edges_scanned,
            queue_peak,
        },
    )
}

#[must_use]
pub fn bellman_ford_shortest_paths(
    graph: &Graph,
    source: &str,
    weight_attr: &str,
) -> WeightedShortestPathsResult {
    if !graph.has_node(source) {
        return WeightedShortestPathsResult {
            distances: Vec::new(),
            predecessors: Vec::new(),
            negative_cycle_detected: false,
            witness: ComplexityWitness {
                algorithm: "bellman_ford_shortest_paths".to_owned(),
                complexity_claim: "O(|V| * |E|)".to_owned(),
                nodes_touched: 0,
                edges_scanned: 0,
                queue_peak: 0,
            },
        };
    }

    let ordered_nodes = graph.nodes_ordered();
    let ordered_edges = undirected_edges_in_iteration_order(graph);
    let mut distances = HashMap::<String, f64>::new();
    let mut predecessors = HashMap::<String, Option<String>>::new();

    distances.insert(source.to_owned(), 0.0);
    predecessors.insert(source.to_owned(), None);

    let mut nodes_touched = 1usize;
    let mut edges_scanned = 0usize;
    let mut queue_peak = 1usize;

    for _ in 0..ordered_nodes.len().saturating_sub(1) {
        let mut changed = false;
        for (left, right) in &ordered_edges {
            let edge_weight = signed_edge_weight_or_default(graph, left, right, weight_attr);
            edges_scanned += 2;
            if relax_weighted_edge(
                left,
                right,
                edge_weight,
                &mut distances,
                &mut predecessors,
                &mut nodes_touched,
            ) {
                changed = true;
            }
            if relax_weighted_edge(
                right,
                left,
                edge_weight,
                &mut distances,
                &mut predecessors,
                &mut nodes_touched,
            ) {
                changed = true;
            }
        }
        queue_peak = queue_peak.max(distances.len());
        if !changed {
            break;
        }
    }

    let mut negative_cycle_detected = false;
    for (left, right) in &ordered_edges {
        let edge_weight = signed_edge_weight_or_default(graph, left, right, weight_attr);
        if can_relax_weighted_edge(left, right, edge_weight, &distances)
            || can_relax_weighted_edge(right, left, edge_weight, &distances)
        {
            negative_cycle_detected = true;
            break;
        }
    }

    weighted_paths_result(
        &ordered_nodes,
        distances,
        predecessors,
        negative_cycle_detected,
        ComplexityWitness {
            algorithm: "bellman_ford_shortest_paths".to_owned(),
            complexity_claim: "O(|V| * |E|)".to_owned(),
            nodes_touched,
            edges_scanned,
            queue_peak,
        },
    )
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
pub fn harmonic_centrality(graph: &Graph) -> HarmonicCentralityResult {
    let nodes = graph.nodes_ordered();
    let n = nodes.len();
    if n == 0 {
        return HarmonicCentralityResult {
            scores: Vec::new(),
            witness: ComplexityWitness {
                algorithm: "harmonic_centrality".to_owned(),
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

        nodes_touched += distance.len();
        // Accumulate in canonical distance order so floating-point roundoff is replay-stable
        // even when node insertion order differs.
        let mut reachable_distances = distance
            .iter()
            .filter_map(|(target, shortest_path_distance)| {
                if *target == *source || *shortest_path_distance == 0 {
                    None
                } else {
                    Some(*shortest_path_distance)
                }
            })
            .collect::<Vec<usize>>();
        reachable_distances.sort_unstable();
        let harmonic = reachable_distances
            .into_iter()
            .fold(0.0_f64, |sum, shortest_path_distance| {
                sum + 1.0 / (shortest_path_distance as f64)
            });
        scores.push(CentralityScore {
            node: (*source).to_owned(),
            score: harmonic,
        });
    }

    HarmonicCentralityResult {
        scores,
        witness: ComplexityWitness {
            algorithm: "harmonic_centrality".to_owned(),
            complexity_claim: "O(|V| * (|V| + |E|))".to_owned(),
            nodes_touched,
            edges_scanned,
            queue_peak,
        },
    }
}

#[must_use]
pub fn katz_centrality(graph: &Graph) -> KatzCentralityResult {
    let nodes = graph.nodes_ordered();
    let n = nodes.len();
    if n == 0 {
        return KatzCentralityResult {
            scores: Vec::new(),
            witness: ComplexityWitness {
                algorithm: "katz_centrality_power_iteration".to_owned(),
                complexity_claim: "O(k * (|V| + |E|))".to_owned(),
                nodes_touched: 0,
                edges_scanned: 0,
                queue_peak: 0,
            },
        };
    }
    if n == 1 {
        return KatzCentralityResult {
            scores: vec![CentralityScore {
                node: nodes[0].to_owned(),
                score: 1.0,
            }],
            witness: ComplexityWitness {
                algorithm: "katz_centrality_power_iteration".to_owned(),
                complexity_claim: "O(k * (|V| + |E|))".to_owned(),
                nodes_touched: 1,
                edges_scanned: 0,
                queue_peak: 0,
            },
        };
    }

    let mut canonical_nodes = nodes.clone();
    canonical_nodes.sort_unstable();
    let index_by_node = canonical_nodes
        .iter()
        .enumerate()
        .map(|(idx, node)| (*node, idx))
        .collect::<HashMap<&str, usize>>();

    let mut scores = vec![0.0_f64; n];
    let mut next_scores = vec![0.0_f64; n];
    let mut iterations = 0usize;
    let mut edges_scanned = 0usize;
    let tolerance = n as f64 * KATZ_DEFAULT_TOLERANCE;

    for _ in 0..KATZ_DEFAULT_MAX_ITERATIONS {
        iterations += 1;
        next_scores.fill(0.0);

        // Deterministic power iteration in canonical node/neighbor order.
        for (source_idx, source) in canonical_nodes.iter().enumerate() {
            let source_score = scores[source_idx];
            let mut neighbors = graph
                .neighbors_iter(source)
                .map(|iter| iter.collect::<Vec<&str>>())
                .unwrap_or_default();
            neighbors.sort_unstable();
            edges_scanned += neighbors.len();

            for neighbor in neighbors {
                let Some(&target_idx) = index_by_node.get(neighbor) else {
                    continue;
                };
                next_scores[target_idx] += source_score;
            }
        }

        for value in &mut next_scores {
            *value = (KATZ_DEFAULT_ALPHA * *value) + KATZ_DEFAULT_BETA;
        }

        let delta = next_scores
            .iter()
            .zip(scores.iter())
            .map(|(left, right)| (left - right).abs())
            .sum::<f64>();
        scores.copy_from_slice(&next_scores);
        if delta < tolerance {
            break;
        }
    }

    let norm = scores.iter().map(|value| value * value).sum::<f64>().sqrt();
    let normalizer = if norm > 0.0 { norm } else { 1.0 };
    for value in &mut scores {
        *value /= normalizer;
    }

    let ordered_scores = nodes
        .iter()
        .map(|node| CentralityScore {
            node: (*node).to_owned(),
            score: scores[*index_by_node
                .get(*node)
                .expect("graph output node must exist in canonical katz index")],
        })
        .collect::<Vec<CentralityScore>>();

    KatzCentralityResult {
        scores: ordered_scores,
        witness: ComplexityWitness {
            algorithm: "katz_centrality_power_iteration".to_owned(),
            complexity_claim: "O(k * (|V| + |E|))".to_owned(),
            nodes_touched: n.saturating_mul(iterations),
            edges_scanned,
            queue_peak: 0,
        },
    }
}

#[must_use]
pub fn hits_centrality(graph: &Graph) -> HitsCentralityResult {
    let nodes = graph.nodes_ordered();
    let n = nodes.len();
    if n == 0 {
        return HitsCentralityResult {
            hubs: Vec::new(),
            authorities: Vec::new(),
            witness: ComplexityWitness {
                algorithm: "hits_centrality_power_iteration".to_owned(),
                complexity_claim: "O(k * (|V| + |E|))".to_owned(),
                nodes_touched: 0,
                edges_scanned: 0,
                queue_peak: 0,
            },
        };
    }
    if n == 1 {
        return HitsCentralityResult {
            hubs: vec![CentralityScore {
                node: nodes[0].to_owned(),
                score: 1.0,
            }],
            authorities: vec![CentralityScore {
                node: nodes[0].to_owned(),
                score: 1.0,
            }],
            witness: ComplexityWitness {
                algorithm: "hits_centrality_power_iteration".to_owned(),
                complexity_claim: "O(k * (|V| + |E|))".to_owned(),
                nodes_touched: 1,
                edges_scanned: 0,
                queue_peak: 0,
            },
        };
    }

    let mut canonical_nodes = nodes.clone();
    canonical_nodes.sort_unstable();
    let index_by_node = canonical_nodes
        .iter()
        .enumerate()
        .map(|(idx, node)| (*node, idx))
        .collect::<HashMap<&str, usize>>();

    let n_f64 = n as f64;
    let mut hubs = vec![1.0 / n_f64; n];
    let mut authorities = vec![0.0_f64; n];
    let mut next_hubs = vec![0.0_f64; n];
    let mut iterations = 0usize;
    let mut edges_scanned = 0usize;

    for _ in 0..HITS_DEFAULT_MAX_ITERATIONS {
        iterations += 1;
        authorities.fill(0.0);
        next_hubs.fill(0.0);

        for (source_idx, source) in canonical_nodes.iter().enumerate() {
            let source_hub = hubs[source_idx];
            let mut neighbors = graph
                .neighbors_iter(source)
                .map(|iter| iter.collect::<Vec<&str>>())
                .unwrap_or_default();
            neighbors.sort_unstable();
            edges_scanned += neighbors.len();
            for neighbor in neighbors {
                let Some(&target_idx) = index_by_node.get(neighbor) else {
                    continue;
                };
                authorities[target_idx] += source_hub;
            }
        }

        for value in &mut authorities {
            if value.is_nan() || !value.is_finite() {
                *value = 0.0;
            }
        }
        let authority_sum_iter = authorities.iter().copied().sum::<f64>();
        if authority_sum_iter > 0.0 {
            for value in &mut authorities {
                *value /= authority_sum_iter;
            }
        }

        for (source_idx, source) in canonical_nodes.iter().enumerate() {
            let mut neighbors = graph
                .neighbors_iter(source)
                .map(|iter| iter.collect::<Vec<&str>>())
                .unwrap_or_default();
            neighbors.sort_unstable();
            edges_scanned += neighbors.len();
            let score = neighbors.into_iter().fold(0.0_f64, |acc, neighbor| {
                let Some(&target_idx) = index_by_node.get(neighbor) else {
                    return acc;
                };
                acc + authorities[target_idx]
            });
            next_hubs[source_idx] = if score.is_finite() { score } else { 0.0 };
        }

        let hub_sum_iter = next_hubs.iter().copied().sum::<f64>();
        if hub_sum_iter > 0.0 {
            for value in &mut next_hubs {
                *value /= hub_sum_iter;
            }
        }

        let delta = next_hubs
            .iter()
            .zip(hubs.iter())
            .map(|(left, right)| (left - right).abs())
            .sum::<f64>();
        hubs.copy_from_slice(&next_hubs);
        if delta < HITS_DEFAULT_TOLERANCE {
            break;
        }
    }

    let hub_sum = hubs.iter().sum::<f64>();
    if hub_sum > 0.0 {
        for value in &mut hubs {
            *value /= hub_sum;
        }
    } else {
        for value in &mut hubs {
            *value = 1.0 / n_f64;
        }
    }
    let authority_sum = authorities.iter().sum::<f64>();
    if authority_sum > 0.0 {
        for value in &mut authorities {
            *value /= authority_sum;
        }
    } else {
        for value in &mut authorities {
            *value = 1.0 / n_f64;
        }
    }

    let ordered_hubs = nodes
        .iter()
        .map(|node| CentralityScore {
            node: (*node).to_owned(),
            score: hubs[*index_by_node
                .get(*node)
                .expect("graph output node must exist in canonical hits-hub index")],
        })
        .collect::<Vec<CentralityScore>>();
    let ordered_authorities = nodes
        .iter()
        .map(|node| CentralityScore {
            node: (*node).to_owned(),
            score: authorities[*index_by_node
                .get(*node)
                .expect("graph output node must exist in canonical hits-authority index")],
        })
        .collect::<Vec<CentralityScore>>();

    HitsCentralityResult {
        hubs: ordered_hubs,
        authorities: ordered_authorities,
        witness: ComplexityWitness {
            algorithm: "hits_centrality_power_iteration".to_owned(),
            complexity_claim: "O(k * (|V| + |E|))".to_owned(),
            nodes_touched: n.saturating_mul(iterations).saturating_mul(2),
            edges_scanned,
            queue_peak: 0,
        },
    }
}

#[must_use]
pub fn pagerank(graph: &Graph) -> PageRankResult {
    let nodes = graph.nodes_ordered();
    let n = nodes.len();
    if n == 0 {
        return PageRankResult {
            scores: Vec::new(),
            witness: ComplexityWitness {
                algorithm: "pagerank_power_iteration".to_owned(),
                complexity_claim: "O(k * (|V| + |E|))".to_owned(),
                nodes_touched: 0,
                edges_scanned: 0,
                queue_peak: 0,
            },
        };
    }
    if n == 1 {
        return PageRankResult {
            scores: vec![CentralityScore {
                node: nodes[0].to_owned(),
                score: 1.0,
            }],
            witness: ComplexityWitness {
                algorithm: "pagerank_power_iteration".to_owned(),
                complexity_claim: "O(k * (|V| + |E|))".to_owned(),
                nodes_touched: 1,
                edges_scanned: 0,
                queue_peak: 0,
            },
        };
    }

    // Canonical compute order removes insertion-order drift while preserving output order.
    let mut canonical_nodes = nodes.clone();
    canonical_nodes.sort_unstable();
    let index_by_node = canonical_nodes
        .iter()
        .enumerate()
        .map(|(idx, node)| (*node, idx))
        .collect::<HashMap<&str, usize>>();
    let out_degree = canonical_nodes
        .iter()
        .map(|node| graph.neighbor_count(node))
        .collect::<Vec<usize>>();

    let n_f64 = n as f64;
    let base = (1.0 - PAGERANK_DEFAULT_ALPHA) / n_f64;
    let mut ranks = vec![1.0 / n_f64; n];
    let mut next_ranks = vec![0.0_f64; n];
    let mut iterations = 0usize;
    let mut edges_scanned = 0usize;

    for _ in 0..PAGERANK_DEFAULT_MAX_ITERATIONS {
        iterations += 1;
        let dangling_mass = ranks
            .iter()
            .enumerate()
            .filter_map(|(idx, value)| (out_degree[idx] == 0).then_some(*value))
            .sum::<f64>();
        let dangling_term = PAGERANK_DEFAULT_ALPHA * dangling_mass / n_f64;

        for (v_idx, v) in canonical_nodes.iter().enumerate() {
            let mut neighbors = graph
                .neighbors_iter(v)
                .map(|iter| iter.collect::<Vec<&str>>())
                .unwrap_or_default();
            neighbors.sort_unstable();
            edges_scanned += neighbors.len();

            let inbound = neighbors.into_iter().fold(0.0_f64, |acc, neighbor| {
                let Some(&u_idx) = index_by_node.get(neighbor) else {
                    return acc;
                };
                let degree = out_degree[u_idx];
                if degree == 0 {
                    acc
                } else {
                    acc + (ranks[u_idx] / degree as f64)
                }
            });

            next_ranks[v_idx] = base + dangling_term + (PAGERANK_DEFAULT_ALPHA * inbound);
        }

        let total_mass = next_ranks.iter().sum::<f64>();
        if total_mass > 0.0 {
            for value in &mut next_ranks {
                *value /= total_mass;
            }
        }

        let delta = next_ranks
            .iter()
            .zip(ranks.iter())
            .map(|(left, right)| (left - right).abs())
            .sum::<f64>();
        ranks.copy_from_slice(&next_ranks);
        if delta < n_f64 * PAGERANK_DEFAULT_TOLERANCE {
            break;
        }
    }

    let scores = nodes
        .iter()
        .map(|node| CentralityScore {
            node: (*node).to_owned(),
            score: ranks[*index_by_node
                .get(*node)
                .expect("graph output node must exist in canonical pagerank index")],
        })
        .collect::<Vec<CentralityScore>>();

    PageRankResult {
        scores,
        witness: ComplexityWitness {
            algorithm: "pagerank_power_iteration".to_owned(),
            complexity_claim: "O(k * (|V| + |E|))".to_owned(),
            nodes_touched: n.saturating_mul(iterations),
            edges_scanned,
            queue_peak: 0,
        },
    }
}

#[must_use]
pub fn eigenvector_centrality(graph: &Graph) -> EigenvectorCentralityResult {
    let nodes = graph.nodes_ordered();
    let n = nodes.len();
    if n == 0 {
        return EigenvectorCentralityResult {
            scores: Vec::new(),
            witness: ComplexityWitness {
                algorithm: "eigenvector_centrality_power_iteration".to_owned(),
                complexity_claim: "O(k * (|V| + |E|))".to_owned(),
                nodes_touched: 0,
                edges_scanned: 0,
                queue_peak: 0,
            },
        };
    }
    if n == 1 {
        return EigenvectorCentralityResult {
            scores: vec![CentralityScore {
                node: nodes[0].to_owned(),
                score: 1.0,
            }],
            witness: ComplexityWitness {
                algorithm: "eigenvector_centrality_power_iteration".to_owned(),
                complexity_claim: "O(k * (|V| + |E|))".to_owned(),
                nodes_touched: 1,
                edges_scanned: 0,
                queue_peak: 0,
            },
        };
    }

    let mut canonical_nodes = nodes.clone();
    canonical_nodes.sort_unstable();
    let index_by_node = canonical_nodes
        .iter()
        .enumerate()
        .map(|(idx, node)| (*node, idx))
        .collect::<HashMap<&str, usize>>();

    let mut scores = vec![1.0_f64 / n as f64; n];
    let mut next_scores = vec![0.0_f64; n];
    let mut iterations = 0usize;
    let mut edges_scanned = 0usize;

    for _ in 0..PAGERANK_DEFAULT_MAX_ITERATIONS {
        iterations += 1;
        next_scores.copy_from_slice(&scores);

        for (source_idx, source) in canonical_nodes.iter().enumerate() {
            let source_score = scores[source_idx];
            let mut neighbors = graph
                .neighbors_iter(source)
                .map(|iter| iter.collect::<Vec<&str>>())
                .unwrap_or_default();
            neighbors.sort_unstable();
            edges_scanned += neighbors.len();
            for neighbor in neighbors {
                let Some(&target_idx) = index_by_node.get(neighbor) else {
                    continue;
                };
                next_scores[target_idx] += source_score;
            }
        }

        let norm = next_scores
            .iter()
            .map(|value| value * value)
            .sum::<f64>()
            .sqrt();
        let normalizer = if norm > 0.0 { norm } else { 1.0 };
        for value in &mut next_scores {
            *value /= normalizer;
        }

        let delta = next_scores
            .iter()
            .zip(scores.iter())
            .map(|(left, right)| (left - right).abs())
            .sum::<f64>();
        scores.copy_from_slice(&next_scores);
        if delta < n as f64 * PAGERANK_DEFAULT_TOLERANCE {
            break;
        }
    }

    let ordered_scores = nodes
        .iter()
        .map(|node| CentralityScore {
            node: (*node).to_owned(),
            score: scores[*index_by_node
                .get(*node)
                .expect("graph output node must exist in canonical eigenvector index")],
        })
        .collect::<Vec<CentralityScore>>();

    EigenvectorCentralityResult {
        scores: ordered_scores,
        witness: ComplexityWitness {
            algorithm: "eigenvector_centrality_power_iteration".to_owned(),
            complexity_claim: "O(k * (|V| + |E|))".to_owned(),
            nodes_touched: n.saturating_mul(iterations),
            edges_scanned,
            queue_peak: 0,
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
pub fn edge_betweenness_centrality(graph: &Graph) -> EdgeBetweennessCentralityResult {
    let nodes = graph.nodes_ordered();
    let n = nodes.len();
    if n == 0 {
        return EdgeBetweennessCentralityResult {
            scores: Vec::new(),
            witness: ComplexityWitness {
                algorithm: "brandes_edge_betweenness_centrality".to_owned(),
                complexity_claim: "O(|V| * |E|)".to_owned(),
                nodes_touched: 0,
                edges_scanned: 0,
                queue_peak: 0,
            },
        };
    }

    let canonical_edge_key = |left: &str, right: &str| -> (String, String) {
        if left <= right {
            (left.to_owned(), right.to_owned())
        } else {
            (right.to_owned(), left.to_owned())
        }
    };

    let mut edge_scores = HashMap::<(String, String), f64>::new();
    for node in &nodes {
        let Some(neighbors) = graph.neighbors_iter(node) else {
            continue;
        };
        for neighbor in neighbors {
            edge_scores
                .entry(canonical_edge_key(node, neighbor))
                .or_insert(0.0);
        }
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
                    let key = canonical_edge_key(v, w);
                    *edge_scores.entry(key).or_insert(0.0) += contribution;
                    *dependency.entry(v).or_insert(0.0) += contribution;
                }
            }
        }
    }

    let scale = if n > 1 {
        1.0 / ((n * (n - 1)) as f64)
    } else {
        0.0
    };
    let mut scores = edge_scores
        .into_iter()
        .map(|((left, right), score)| EdgeCentralityScore {
            left,
            right,
            score: score * scale,
        })
        .collect::<Vec<EdgeCentralityScore>>();
    scores.sort_unstable_by(|left, right| {
        left.left
            .cmp(&right.left)
            .then_with(|| left.right.cmp(&right.right))
    });

    EdgeBetweennessCentralityResult {
        scores,
        witness: ComplexityWitness {
            algorithm: "brandes_edge_betweenness_centrality".to_owned(),
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
                    "blossom_max_weight_matching_maxcardinality".to_owned()
                } else {
                    "blossom_max_weight_matching".to_owned()
                },
                complexity_claim: "O(|V|^3)".to_owned(),
                nodes_touched: graph.node_count(),
                edges_scanned: 0,
                queue_peak: 0,
            },
        };
    }

    let (matching, total_weight, edges_scanned) =
        blossom_weight_matching(&candidates, maxcardinality);

    WeightedMatchingResult {
        matching,
        total_weight,
        witness: ComplexityWitness {
            algorithm: if maxcardinality {
                "blossom_max_weight_matching_maxcardinality".to_owned()
            } else {
                "blossom_max_weight_matching".to_owned()
            },
            complexity_claim: "O(|V|^3)".to_owned(),
            nodes_touched: graph.node_count(),
            edges_scanned,
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
                algorithm: "blossom_min_weight_matching".to_owned(),
                complexity_claim: "O(|V|^3)".to_owned(),
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
        .iter()
        .map(|edge| WeightedEdgeCandidate {
            weight: (max_weight + 1.0) - edge.weight,
            left: edge.left.clone(),
            right: edge.right.clone(),
        })
        .collect::<Vec<WeightedEdgeCandidate>>();

    let (matching, _, edges_scanned) = blossom_weight_matching(&transformed_candidates, true);
    let total_weight = matching
        .iter()
        .map(|(left, right)| matching_edge_weight_or_default(graph, left, right, weight_attr))
        .sum();

    WeightedMatchingResult {
        matching,
        total_weight,
        witness: ComplexityWitness {
            algorithm: "blossom_min_weight_matching".to_owned(),
            complexity_claim: "O(|V|^3)".to_owned(),
            nodes_touched: graph.node_count(),
            edges_scanned,
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
        let mut candidates = computation
            .residual
            .get(&current)
            .map(|caps| caps.keys().map(|s| s.as_str()).collect::<Vec<&str>>())
            .unwrap_or_default();
        candidates.sort_unstable();

        for candidate in candidates {
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
            visited.insert(candidate.to_owned());
            queue.push_back(candidate.to_owned());
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

#[must_use]
pub fn minimum_st_edge_cut_edmonds_karp(
    graph: &Graph,
    source: &str,
    sink: &str,
    capacity_attr: &str,
) -> EdgeCutResult {
    let cut = minimum_cut_edmonds_karp(graph, source, sink, capacity_attr);
    let source_partition = cut.source_partition;
    let sink_partition = cut.sink_partition;

    let source_set = source_partition
        .iter()
        .cloned()
        .collect::<HashSet<String>>();
    let sink_set = sink_partition.iter().cloned().collect::<HashSet<String>>();

    let mut cut_edges = Vec::<(String, String)>::new();
    let mut cut_edges_scanned = 0usize;
    for (left, right) in undirected_edges_in_iteration_order(graph) {
        cut_edges_scanned += 1;
        let left_in_source = source_set.contains(&left);
        let right_in_source = source_set.contains(&right);
        let left_in_sink = sink_set.contains(&left);
        let right_in_sink = sink_set.contains(&right);
        let crosses_partition =
            (left_in_source && right_in_sink) || (right_in_source && left_in_sink);
        if !crosses_partition {
            continue;
        }
        let (canonical_left, canonical_right) = canonical_undirected_edge(&left, &right);
        cut_edges.push((canonical_left, canonical_right));
    }
    cut_edges.sort_unstable();
    cut_edges.dedup();

    EdgeCutResult {
        value: cut.value,
        cut_edges,
        source_partition,
        sink_partition,
        witness: ComplexityWitness {
            algorithm: "edmonds_karp_minimum_st_edge_cut".to_owned(),
            complexity_claim: "O(|V| * |E|^2)".to_owned(),
            nodes_touched: cut.witness.nodes_touched,
            edges_scanned: cut.witness.edges_scanned + cut_edges_scanned,
            queue_peak: cut.witness.queue_peak,
        },
    }
}

#[must_use]
pub fn edge_connectivity_edmonds_karp(
    graph: &Graph,
    source: &str,
    sink: &str,
    capacity_attr: &str,
) -> EdgeConnectivityResult {
    let cut = minimum_cut_edmonds_karp(graph, source, sink, capacity_attr);
    EdgeConnectivityResult {
        value: cut.value,
        witness: ComplexityWitness {
            algorithm: "edmonds_karp_edge_connectivity".to_owned(),
            complexity_claim: "O(|V| * |E|^2)".to_owned(),
            nodes_touched: cut.witness.nodes_touched,
            edges_scanned: cut.witness.edges_scanned,
            queue_peak: cut.witness.queue_peak,
        },
    }
}

#[must_use]
pub fn global_edge_connectivity_edmonds_karp(
    graph: &Graph,
    capacity_attr: &str,
) -> EdgeConnectivityResult {
    let mut nodes = graph.nodes_ordered();
    nodes.sort_unstable();
    if nodes.len() < 2 {
        return EdgeConnectivityResult {
            value: 0.0,
            witness: ComplexityWitness {
                algorithm: "edmonds_karp_global_edge_connectivity".to_owned(),
                complexity_claim: "O(|V|^3 * |E|^2)".to_owned(),
                nodes_touched: graph.node_count(),
                edges_scanned: 0,
                queue_peak: 0,
            },
        };
    }

    let mut best_value = f64::INFINITY;
    let mut nodes_touched = 0usize;
    let mut edges_scanned = 0usize;
    let mut queue_peak = 0usize;

    'pairs: for (left_index, left) in nodes.iter().enumerate() {
        for right in nodes.iter().skip(left_index + 1) {
            let cut = minimum_cut_edmonds_karp(graph, left, right, capacity_attr);
            best_value = best_value.min(cut.value);
            nodes_touched += cut.witness.nodes_touched;
            edges_scanned += cut.witness.edges_scanned;
            queue_peak = queue_peak.max(cut.witness.queue_peak);
            if best_value <= 0.0 {
                break 'pairs;
            }
        }
    }

    EdgeConnectivityResult {
        value: if best_value.is_finite() {
            best_value
        } else {
            0.0
        },
        witness: ComplexityWitness {
            algorithm: "edmonds_karp_global_edge_connectivity".to_owned(),
            complexity_claim: "O(|V|^3 * |E|^2)".to_owned(),
            nodes_touched,
            edges_scanned,
            queue_peak,
        },
    }
}

#[must_use]
pub fn global_minimum_edge_cut_edmonds_karp(
    graph: &Graph,
    capacity_attr: &str,
) -> GlobalEdgeCutResult {
    let mut nodes = graph.nodes_ordered();
    nodes.sort_unstable();
    if nodes.len() < 2 {
        return GlobalEdgeCutResult {
            value: 0.0,
            source: String::new(),
            sink: String::new(),
            cut_edges: Vec::new(),
            source_partition: Vec::new(),
            sink_partition: Vec::new(),
            witness: ComplexityWitness {
                algorithm: "edmonds_karp_global_minimum_edge_cut".to_owned(),
                complexity_claim: "O(|V|^3 * |E|^2)".to_owned(),
                nodes_touched: graph.node_count(),
                edges_scanned: 0,
                queue_peak: 0,
            },
        };
    }

    let mut best_pair = None::<(String, String)>;
    let mut best_cut = None::<EdgeCutResult>;
    let mut nodes_touched = 0usize;
    let mut edges_scanned = 0usize;
    let mut queue_peak = 0usize;

    'pairs: for (left_index, left) in nodes.iter().enumerate() {
        for right in nodes.iter().skip(left_index + 1) {
            let cut = minimum_st_edge_cut_edmonds_karp(graph, left, right, capacity_attr);
            nodes_touched += cut.witness.nodes_touched;
            edges_scanned += cut.witness.edges_scanned;
            queue_peak = queue_peak.max(cut.witness.queue_peak);

            let candidate_pair = ((*left).to_owned(), (*right).to_owned());
            let should_replace = match (&best_pair, &best_cut) {
                (None, None) => true,
                (Some(current_pair), Some(current_cut)) => {
                    if cut.value + 1e-12 < current_cut.value {
                        true
                    } else {
                        (cut.value - current_cut.value).abs() <= 1e-12
                            && candidate_pair < *current_pair
                    }
                }
                _ => true,
            };

            if should_replace {
                best_pair = Some(candidate_pair);
                best_cut = Some(cut);
            }

            if let Some(current_cut) = &best_cut
                && current_cut.value <= 0.0
            {
                break 'pairs;
            }
        }
    }

    let (source, sink) = best_pair.unwrap_or_else(|| (String::new(), String::new()));
    let cut = best_cut.unwrap_or(EdgeCutResult {
        value: 0.0,
        cut_edges: Vec::new(),
        source_partition: Vec::new(),
        sink_partition: Vec::new(),
        witness: ComplexityWitness {
            algorithm: "edmonds_karp_minimum_st_edge_cut".to_owned(),
            complexity_claim: "O(|V| * |E|^2)".to_owned(),
            nodes_touched: 0,
            edges_scanned: 0,
            queue_peak: 0,
        },
    });

    GlobalEdgeCutResult {
        value: cut.value,
        source,
        sink,
        cut_edges: cut.cut_edges,
        source_partition: cut.source_partition,
        sink_partition: cut.sink_partition,
        witness: ComplexityWitness {
            algorithm: "edmonds_karp_global_minimum_edge_cut".to_owned(),
            complexity_claim: "O(|V|^3 * |E|^2)".to_owned(),
            nodes_touched,
            edges_scanned,
            queue_peak,
        },
    }
}

#[must_use]
pub fn articulation_points(graph: &Graph) -> ArticulationPointsResult {
    let analysis = dfs_connectivity_analysis(graph);
    ArticulationPointsResult {
        nodes: analysis.articulation_points,
        witness: ComplexityWitness {
            algorithm: "tarjan_articulation_points".to_owned(),
            complexity_claim: "O(|V| + |E|)".to_owned(),
            nodes_touched: analysis.nodes_touched,
            edges_scanned: analysis.edges_scanned,
            queue_peak: 0,
        },
    }
}

#[must_use]
pub fn bridges(graph: &Graph) -> BridgesResult {
    let analysis = dfs_connectivity_analysis(graph);
    BridgesResult {
        edges: analysis.bridges,
        witness: ComplexityWitness {
            algorithm: "tarjan_bridges".to_owned(),
            complexity_claim: "O(|V| + |E|)".to_owned(),
            nodes_touched: analysis.nodes_touched,
            edges_scanned: analysis.edges_scanned,
            queue_peak: 0,
        },
    }
}

#[derive(Debug, Default)]
struct DfsConnectivityAnalysis {
    articulation_points: Vec<String>,
    bridges: Vec<(String, String)>,
    nodes_touched: usize,
    edges_scanned: usize,
}

fn dfs_connectivity_analysis(graph: &Graph) -> DfsConnectivityAnalysis {
    let mut analysis = DfsConnectivityAnalysis::default();
    let mut ordered_nodes = graph.nodes_ordered();
    ordered_nodes.sort_unstable();

    let mut discovery = HashMap::<String, usize>::new();
    let mut low = HashMap::<String, usize>::new();
    let mut parent = HashMap::<String, Option<String>>::new();
    let mut is_articulation = HashSet::<String>::new();
    let mut bridges = HashSet::<(String, String)>::new();
    let mut time = 0usize;

    for node in &ordered_nodes {
        if discovery.contains_key(*node) {
            continue;
        }
        parent.insert((*node).to_owned(), None);
        dfs_connectivity_visit(
            graph,
            node,
            &mut time,
            &mut discovery,
            &mut low,
            &mut parent,
            &mut is_articulation,
            &mut bridges,
            &mut analysis.nodes_touched,
            &mut analysis.edges_scanned,
        );
    }

    let mut articulation_points = is_articulation.into_iter().collect::<Vec<String>>();
    articulation_points.sort_unstable();
    let mut bridge_edges = bridges.into_iter().collect::<Vec<(String, String)>>();
    bridge_edges.sort_unstable();

    analysis.articulation_points = articulation_points;
    analysis.bridges = bridge_edges;
    analysis
}

struct DfsFrame {
    node: String,
    neighbors: Vec<String>,
    neighbor_idx: usize,
    child_count: usize,
}

#[allow(clippy::too_many_arguments)]
fn dfs_connectivity_visit(
    graph: &Graph,
    root: &str,
    time: &mut usize,
    discovery: &mut HashMap<String, usize>,
    low: &mut HashMap<String, usize>,
    parent: &mut HashMap<String, Option<String>>,
    is_articulation: &mut HashSet<String>,
    bridges: &mut HashSet<(String, String)>,
    nodes_touched: &mut usize,
    edges_scanned: &mut usize,
) {
    *nodes_touched += 1;
    *time += 1;
    discovery.insert(root.to_owned(), *time);
    low.insert(root.to_owned(), *time);

    let mut root_neighbors = graph
        .neighbors_iter(root)
        .map(|iter| iter.map(str::to_owned).collect::<Vec<String>>())
        .unwrap_or_default();
    root_neighbors.sort_unstable();

    let mut stack = vec![DfsFrame {
        node: root.to_owned(),
        neighbors: root_neighbors,
        neighbor_idx: 0,
        child_count: 0,
    }];

    while let Some(frame) = stack.last_mut() {
        if frame.neighbor_idx < frame.neighbors.len() {
            let neighbor = frame.neighbors[frame.neighbor_idx].clone();
            frame.neighbor_idx += 1;
            *edges_scanned += 1;

            if !discovery.contains_key(&neighbor) {
                frame.child_count += 1;
                parent.insert(neighbor.clone(), Some(frame.node.clone()));

                *nodes_touched += 1;
                *time += 1;
                discovery.insert(neighbor.clone(), *time);
                low.insert(neighbor.clone(), *time);

                let mut child_neighbors = graph
                    .neighbors_iter(&neighbor)
                    .map(|iter| iter.map(str::to_owned).collect::<Vec<String>>())
                    .unwrap_or_default();
                child_neighbors.sort_unstable();

                stack.push(DfsFrame {
                    node: neighbor,
                    neighbors: child_neighbors,
                    neighbor_idx: 0,
                    child_count: 0,
                });
            } else {
                let current_parent = parent.get(&frame.node).cloned().flatten();
                if current_parent.as_deref() != Some(neighbor.as_str()) {
                    let disc_neighbor = *discovery.get(&neighbor).unwrap_or(&usize::MAX);
                    let low_current = *low.get(&frame.node).unwrap_or(&usize::MAX);
                    low.insert(frame.node.clone(), low_current.min(disc_neighbor));
                }
            }
        } else {
            let finished = stack.pop().unwrap();

            if let Some(parent_frame) = stack.last() {
                let low_finished = *low.get(&finished.node).unwrap_or(&usize::MAX);
                let low_parent = *low.get(&parent_frame.node).unwrap_or(&usize::MAX);
                low.insert(parent_frame.node.clone(), low_parent.min(low_finished));

                let parent_of_parent = parent.get(&parent_frame.node).cloned().flatten();
                if parent_of_parent.is_none() && parent_frame.child_count > 1 {
                    is_articulation.insert(parent_frame.node.clone());
                }
                if parent_of_parent.is_some() {
                    let disc_parent = *discovery.get(&parent_frame.node).unwrap_or(&usize::MAX);
                    if low_finished >= disc_parent {
                        is_articulation.insert(parent_frame.node.clone());
                    }
                }
                let disc_parent = *discovery.get(&parent_frame.node).unwrap_or(&usize::MAX);
                if low_finished > disc_parent {
                    bridges.insert(canonical_undirected_edge(
                        &parent_frame.node,
                        &finished.node,
                    ));
                }
            } else if finished.child_count > 1 {
                is_articulation.insert(finished.node);
            }
        }
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
            let mut neighbors = residual
                .get(&current)
                .map(|caps| caps.keys().map(|s| s.as_str()).collect::<Vec<&str>>())
                .unwrap_or_default();
            neighbors.sort_unstable();

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

fn weighted_paths_result(
    ordered_nodes: &[&str],
    distances: HashMap<String, f64>,
    predecessors: HashMap<String, Option<String>>,
    negative_cycle_detected: bool,
    witness: ComplexityWitness,
) -> WeightedShortestPathsResult {
    let distance_entries = ordered_nodes
        .iter()
        .filter_map(|node| {
            distances.get(*node).map(|distance| WeightedDistanceEntry {
                node: (*node).to_owned(),
                distance: *distance,
            })
        })
        .collect::<Vec<WeightedDistanceEntry>>();
    let predecessor_entries = ordered_nodes
        .iter()
        .filter(|node| distances.contains_key(**node))
        .map(|node| WeightedPredecessorEntry {
            node: (*node).to_owned(),
            predecessor: predecessors.get(*node).cloned().flatten(),
        })
        .collect::<Vec<WeightedPredecessorEntry>>();

    WeightedShortestPathsResult {
        distances: distance_entries,
        predecessors: predecessor_entries,
        negative_cycle_detected,
        witness,
    }
}

fn relax_weighted_edge(
    from: &str,
    to: &str,
    weight: f64,
    distances: &mut HashMap<String, f64>,
    predecessors: &mut HashMap<String, Option<String>>,
    nodes_touched: &mut usize,
) -> bool {
    let Some(base_distance) = distances.get(from).copied() else {
        return false;
    };

    let candidate_distance = base_distance + weight;
    let should_update = match distances.get(to) {
        Some(existing_distance) => {
            candidate_distance + DISTANCE_COMPARISON_EPSILON < *existing_distance
        }
        None => true,
    };
    if !should_update {
        return false;
    }

    if distances
        .insert(to.to_owned(), candidate_distance)
        .is_none()
    {
        *nodes_touched += 1;
    }
    predecessors.insert(to.to_owned(), Some(from.to_owned()));
    true
}

fn can_relax_weighted_edge(
    from: &str,
    to: &str,
    weight: f64,
    distances: &HashMap<String, f64>,
) -> bool {
    let Some(base_distance) = distances.get(from).copied() else {
        return false;
    };
    let candidate_distance = base_distance + weight;
    match distances.get(to) {
        Some(existing_distance) => {
            candidate_distance + DISTANCE_COMPARISON_EPSILON < *existing_distance
        }
        None => true,
    }
}

fn weighted_edge_candidates(graph: &Graph, weight_attr: &str) -> Vec<WeightedEdgeCandidate> {
    let mut candidates = undirected_edges_in_iteration_order(graph)
        .into_iter()
        .map(|(left, right)| {
            let (canonical_left, canonical_right) = canonical_undirected_edge(&left, &right);
            WeightedEdgeCandidate {
                weight: matching_edge_weight_or_default(
                    graph,
                    &canonical_left,
                    &canonical_right,
                    weight_attr,
                ),
                left: canonical_left,
                right: canonical_right,
            }
        })
        .collect::<Vec<WeightedEdgeCandidate>>();
    candidates.sort_unstable_by(|left, right| {
        left.left
            .cmp(&right.left)
            .then_with(|| left.right.cmp(&right.right))
    });
    candidates
}

fn blossom_weight_matching(
    candidates: &[WeightedEdgeCandidate],
    maxcardinality: bool,
) -> (Vec<(String, String)>, f64, usize) {
    if candidates.is_empty() {
        return (Vec::new(), 0.0, 0);
    }

    let mut node_names = candidates
        .iter()
        .flat_map(|edge| [&edge.left, &edge.right])
        .cloned()
        .collect::<Vec<String>>();
    node_names.sort_unstable();
    node_names.dedup();

    let mut node_to_index = HashMap::<String, usize>::new();
    for (index, node) in node_names.iter().enumerate() {
        node_to_index.insert(node.clone(), index);
    }

    let mut edge_weights = HashMap::<(usize, usize), f64>::new();
    let scale = blossom_integer_weight_scale(candidates);
    let mut blossom_edges = candidates
        .iter()
        .filter_map(|edge| {
            let left_index = *node_to_index.get(&edge.left)?;
            let right_index = *node_to_index.get(&edge.right)?;
            if left_index == right_index {
                return None;
            }
            let (u, v) = if left_index < right_index {
                (left_index, right_index)
            } else {
                (right_index, left_index)
            };
            edge_weights.insert((u, v), edge.weight);
            Some((u, v, blossom_quantized_weight(edge.weight, scale)))
        })
        .collect::<Vec<(usize, usize, i32)>>();
    blossom_edges.sort_unstable_by(|left, right| {
        left.0
            .cmp(&right.0)
            .then_with(|| left.1.cmp(&right.1))
            .then_with(|| left.2.cmp(&right.2))
    });

    let mut solver = BlossomMatching::new(blossom_edges);
    if maxcardinality {
        solver.max_cardinality();
    }
    let mates = solver.solve();

    let mut matching = Vec::<(String, String)>::new();
    let mut total_weight = 0.0_f64;
    for (left_index, right_index) in mates.iter().enumerate() {
        if *right_index == BLOSSOM_SENTINEL || left_index >= *right_index {
            continue;
        }
        let (u, v) = if left_index < *right_index {
            (left_index, *right_index)
        } else {
            (*right_index, left_index)
        };
        let Some(left_node) = node_names.get(u) else {
            continue;
        };
        let Some(right_node) = node_names.get(v) else {
            continue;
        };
        matching.push((left_node.clone(), right_node.clone()));
        total_weight += edge_weights.get(&(u, v)).copied().unwrap_or(1.0);
    }
    matching.sort_unstable();

    (matching, total_weight, candidates.len())
}

fn blossom_integer_weight_scale(candidates: &[WeightedEdgeCandidate]) -> f64 {
    let max_abs_weight = candidates
        .iter()
        .map(|edge| edge.weight.abs())
        .fold(0.0_f64, f64::max);
    if !max_abs_weight.is_finite() || max_abs_weight <= 0.0 {
        return 1.0;
    }

    let preferred_scale = 1_000_000.0_f64;
    let bounded_scale = (f64::from(i32::MAX) / max_abs_weight).floor().max(1.0);
    preferred_scale.min(bounded_scale)
}

fn blossom_quantized_weight(weight: f64, scale: f64) -> i32 {
    let scaled = (weight * scale).round();
    if !scaled.is_finite() {
        return 0;
    }
    let bounded = scaled.clamp(f64::from(i32::MIN), f64::from(i32::MAX));
    bounded as i32
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

fn signed_edge_weight_or_default(graph: &Graph, left: &str, right: &str, weight_attr: &str) -> f64 {
    graph
        .edge_attrs(left, right)
        .and_then(|attrs| attrs.get(weight_attr))
        .and_then(|raw| raw.parse::<f64>().ok())
        .filter(|value| value.is_finite())
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

#[must_use]
pub fn clustering_coefficient(graph: &Graph) -> ClusteringCoefficientResult {
    let nodes = graph.nodes_ordered();
    let n = nodes.len();
    if n == 0 {
        return ClusteringCoefficientResult {
            scores: Vec::new(),
            average_clustering: 0.0,
            transitivity: 0.0,
            witness: ComplexityWitness {
                algorithm: "clustering_coefficient".to_owned(),
                complexity_claim: "O(|V| * d_max^2)".to_owned(),
                nodes_touched: 0,
                edges_scanned: 0,
                queue_peak: 0,
            },
        };
    }

    let mut scores = Vec::with_capacity(n);
    let mut nodes_touched = 0usize;
    let mut edges_scanned = 0usize;
    let mut total_triangles = 0usize;
    let mut total_triples = 0usize;

    for node in &nodes {
        nodes_touched += 1;
        let neighbors = graph.neighbors(node).unwrap_or_default();
        let degree = neighbors.len();

        if degree < 2 {
            scores.push(CentralityScore {
                node: (*node).to_owned(),
                score: 0.0,
            });
            total_triples += degree * degree.saturating_sub(1);
            continue;
        }

        let mut triangles = 0usize;
        for (i, u) in neighbors.iter().enumerate() {
            for v in &neighbors[i + 1..] {
                edges_scanned += 1;
                if graph.has_edge(u, v) {
                    triangles += 1;
                }
            }
        }

        let possible_pairs = degree * (degree - 1) / 2;
        let coefficient = (triangles as f64) / (possible_pairs as f64);
        scores.push(CentralityScore {
            node: (*node).to_owned(),
            score: coefficient,
        });

        total_triangles += triangles;
        total_triples += degree * (degree - 1);
    }

    let average_clustering = if n == 0 {
        0.0
    } else {
        scores.iter().map(|s| s.score).sum::<f64>() / (n as f64)
    };

    let transitivity = if total_triples == 0 {
        0.0
    } else {
        (2.0 * total_triangles as f64) / (total_triples as f64)
    };

    ClusteringCoefficientResult {
        scores,
        average_clustering,
        transitivity,
        witness: ComplexityWitness {
            algorithm: "clustering_coefficient".to_owned(),
            complexity_claim: "O(|V| * d_max^2)".to_owned(),
            nodes_touched,
            edges_scanned,
            queue_peak: 0,
        },
    }
}

#[must_use]
pub fn distance_measures(graph: &Graph) -> DistanceMeasuresResult {
    let nodes = graph.nodes_ordered();
    let n = nodes.len();
    if n == 0 {
        return DistanceMeasuresResult {
            eccentricity: Vec::new(),
            diameter: 0,
            radius: 0,
            center: Vec::new(),
            periphery: Vec::new(),
            witness: ComplexityWitness {
                algorithm: "bfs_distance_measures".to_owned(),
                complexity_claim: "O(|V| * (|V| + |E|))".to_owned(),
                nodes_touched: 0,
                edges_scanned: 0,
                queue_peak: 0,
            },
        };
    }

    let mut eccentricities = Vec::with_capacity(n);
    let mut total_nodes_touched = 0usize;
    let mut total_edges_scanned = 0usize;
    let mut max_queue_peak = 0usize;

    for source in &nodes {
        let mut dist: HashMap<&str, usize> = HashMap::new();
        let mut queue = VecDeque::new();
        dist.insert(source, 0);
        queue.push_back(*source);
        let mut local_nodes = 0usize;
        let mut local_edges = 0usize;
        let mut local_peak = 0usize;

        while let Some(current) = queue.pop_front() {
            local_nodes += 1;
            let current_dist = dist[current];
            if let Some(neighbors) = graph.neighbors_iter(current) {
                for neighbor in neighbors {
                    local_edges += 1;
                    if !dist.contains_key(neighbor) {
                        dist.insert(neighbor, current_dist + 1);
                        queue.push_back(neighbor);
                    }
                }
            }
            if queue.len() > local_peak {
                local_peak = queue.len();
            }
        }

        let ecc = dist.values().copied().max().unwrap_or(0);
        eccentricities.push(EccentricityEntry {
            node: (*source).to_owned(),
            value: ecc,
        });

        total_nodes_touched += local_nodes;
        total_edges_scanned += local_edges;
        if local_peak > max_queue_peak {
            max_queue_peak = local_peak;
        }
    }

    let diameter = eccentricities.iter().map(|e| e.value).max().unwrap_or(0);
    let radius = eccentricities.iter().map(|e| e.value).min().unwrap_or(0);

    let mut center: Vec<String> = eccentricities
        .iter()
        .filter(|e| e.value == radius)
        .map(|e| e.node.clone())
        .collect();
    center.sort_unstable();

    let mut periphery: Vec<String> = eccentricities
        .iter()
        .filter(|e| e.value == diameter)
        .map(|e| e.node.clone())
        .collect();
    periphery.sort_unstable();

    DistanceMeasuresResult {
        eccentricity: eccentricities,
        diameter,
        radius,
        center,
        periphery,
        witness: ComplexityWitness {
            algorithm: "bfs_distance_measures".to_owned(),
            complexity_claim: "O(|V| * (|V| + |E|))".to_owned(),
            nodes_touched: total_nodes_touched,
            edges_scanned: total_edges_scanned,
            queue_peak: max_queue_peak,
        },
    }
}

/// Computes the average shortest path length of an undirected graph.
///
/// Returns `sum(d(u,v)) / (n*(n-1))` for all pairs `u != v` where `d(u,v)` is
/// the shortest-path distance between `u` and `v`.  The graph must be connected;
/// if it is empty or has a single node, the result is 0.0.
#[must_use]
pub fn average_shortest_path_length(graph: &Graph) -> AverageShortestPathLengthResult {
    let nodes = graph.nodes_ordered();
    let n = nodes.len();
    if n <= 1 {
        return AverageShortestPathLengthResult {
            average_shortest_path_length: 0.0,
            witness: ComplexityWitness {
                algorithm: "bfs_average_shortest_path_length".to_owned(),
                complexity_claim: "O(|V| * (|V| + |E|))".to_owned(),
                nodes_touched: 0,
                edges_scanned: 0,
                queue_peak: 0,
            },
        };
    }

    let mut total_distance = 0usize;
    let mut total_nodes_touched = 0usize;
    let mut total_edges_scanned = 0usize;
    let mut max_queue_peak = 0usize;

    for source in &nodes {
        let mut dist: HashMap<&str, usize> = HashMap::new();
        let mut queue = VecDeque::new();
        dist.insert(source, 0);
        queue.push_back(*source);
        let mut local_nodes = 0usize;
        let mut local_edges = 0usize;
        let mut local_peak = 0usize;

        while let Some(current) = queue.pop_front() {
            local_nodes += 1;
            let current_dist = dist[current];
            if let Some(neighbors) = graph.neighbors_iter(current) {
                for neighbor in neighbors {
                    local_edges += 1;
                    if !dist.contains_key(neighbor) {
                        dist.insert(neighbor, current_dist + 1);
                        queue.push_back(neighbor);
                    }
                }
            }
            if queue.len() > local_peak {
                local_peak = queue.len();
            }
        }

        total_distance += dist.values().sum::<usize>();
        total_nodes_touched += local_nodes;
        total_edges_scanned += local_edges;
        if local_peak > max_queue_peak {
            max_queue_peak = local_peak;
        }
    }

    let denominator = n * (n - 1);
    let avg = total_distance as f64 / denominator as f64;

    AverageShortestPathLengthResult {
        average_shortest_path_length: avg,
        witness: ComplexityWitness {
            algorithm: "bfs_average_shortest_path_length".to_owned(),
            complexity_claim: "O(|V| * (|V| + |E|))".to_owned(),
            nodes_touched: total_nodes_touched,
            edges_scanned: total_edges_scanned,
            queue_peak: max_queue_peak,
        },
    }
}

/// Returns whether the graph is connected (all nodes reachable from each other).
///
/// An empty graph returns `false` (consistent with NetworkX raising
/// `NetworkXPointlessConcept`).  A single-node graph returns `true`.
#[must_use]
pub fn is_connected(graph: &Graph) -> IsConnectedResult {
    let nodes = graph.nodes_ordered();
    let n = nodes.len();
    if n == 0 {
        return IsConnectedResult {
            is_connected: false,
            witness: ComplexityWitness {
                algorithm: "bfs_is_connected".to_owned(),
                complexity_claim: "O(|V| + |E|)".to_owned(),
                nodes_touched: 0,
                edges_scanned: 0,
                queue_peak: 0,
            },
        };
    }

    let mut visited = HashSet::new();
    let mut queue = VecDeque::new();
    let mut edges_scanned = 0usize;
    let mut queue_peak = 0usize;

    visited.insert(nodes[0]);
    queue.push_back(nodes[0]);

    while let Some(current) = queue.pop_front() {
        if let Some(neighbors) = graph.neighbors_iter(current) {
            for neighbor in neighbors {
                edges_scanned += 1;
                if visited.insert(neighbor) {
                    queue.push_back(neighbor);
                }
            }
        }
        if queue.len() > queue_peak {
            queue_peak = queue.len();
        }
    }

    IsConnectedResult {
        is_connected: visited.len() == n,
        witness: ComplexityWitness {
            algorithm: "bfs_is_connected".to_owned(),
            complexity_claim: "O(|V| + |E|)".to_owned(),
            nodes_touched: visited.len(),
            edges_scanned,
            queue_peak,
        },
    }
}

/// Computes the density of an undirected graph: `2 * |E| / (|V| * (|V| - 1))`.
///
/// Returns 0.0 for graphs with fewer than 2 nodes.
#[must_use]
pub fn density(graph: &Graph) -> DensityResult {
    let n = graph.nodes_ordered().len();
    if n < 2 {
        return DensityResult { density: 0.0 };
    }
    let e = graph.edge_count();
    let d = (2.0 * e as f64) / (n * (n - 1)) as f64;
    DensityResult { density: d }
}

/// Returns whether there is a path between `source` and `target` in the graph.
///
/// Uses BFS from `source`.  Returns `false` if either node is missing from the graph.
#[must_use]
pub fn has_path(graph: &Graph, source: &str, target: &str) -> HasPathResult {
    if source == target && graph.has_node(source) {
        return HasPathResult {
            has_path: true,
            witness: ComplexityWitness {
                algorithm: "bfs_has_path".to_owned(),
                complexity_claim: "O(|V| + |E|)".to_owned(),
                nodes_touched: 1,
                edges_scanned: 0,
                queue_peak: 0,
            },
        };
    }
    if !graph.has_node(source) || !graph.has_node(target) {
        return HasPathResult {
            has_path: false,
            witness: ComplexityWitness {
                algorithm: "bfs_has_path".to_owned(),
                complexity_claim: "O(|V| + |E|)".to_owned(),
                nodes_touched: 0,
                edges_scanned: 0,
                queue_peak: 0,
            },
        };
    }

    let mut visited = HashSet::new();
    let mut queue = VecDeque::new();
    let mut edges_scanned = 0usize;
    let mut queue_peak = 0usize;

    visited.insert(source);
    queue.push_back(source);

    while let Some(current) = queue.pop_front() {
        if current == target {
            return HasPathResult {
                has_path: true,
                witness: ComplexityWitness {
                    algorithm: "bfs_has_path".to_owned(),
                    complexity_claim: "O(|V| + |E|)".to_owned(),
                    nodes_touched: visited.len(),
                    edges_scanned,
                    queue_peak,
                },
            };
        }
        if let Some(neighbors) = graph.neighbors_iter(current) {
            for neighbor in neighbors {
                edges_scanned += 1;
                if visited.insert(neighbor) {
                    queue.push_back(neighbor);
                }
            }
        }
        if queue.len() > queue_peak {
            queue_peak = queue.len();
        }
    }

    HasPathResult {
        has_path: false,
        witness: ComplexityWitness {
            algorithm: "bfs_has_path".to_owned(),
            complexity_claim: "O(|V| + |E|)".to_owned(),
            nodes_touched: visited.len(),
            edges_scanned,
            queue_peak,
        },
    }
}

/// Returns the length of the shortest path between `source` and `target`.
///
/// Uses BFS.  Returns `None` if there is no path or if either node is missing.
#[must_use]
pub fn shortest_path_length(graph: &Graph, source: &str, target: &str) -> ShortestPathLengthResult {
    if source == target && graph.has_node(source) {
        return ShortestPathLengthResult {
            length: Some(0),
            witness: ComplexityWitness {
                algorithm: "bfs_shortest_path_length".to_owned(),
                complexity_claim: "O(|V| + |E|)".to_owned(),
                nodes_touched: 1,
                edges_scanned: 0,
                queue_peak: 0,
            },
        };
    }
    if !graph.has_node(source) || !graph.has_node(target) {
        return ShortestPathLengthResult {
            length: None,
            witness: ComplexityWitness {
                algorithm: "bfs_shortest_path_length".to_owned(),
                complexity_claim: "O(|V| + |E|)".to_owned(),
                nodes_touched: 0,
                edges_scanned: 0,
                queue_peak: 0,
            },
        };
    }

    let mut dist: HashMap<&str, usize> = HashMap::new();
    let mut queue = VecDeque::new();
    let mut edges_scanned = 0usize;
    let mut queue_peak = 0usize;

    dist.insert(source, 0);
    queue.push_back(source);

    while let Some(current) = queue.pop_front() {
        let current_dist = dist[current];
        if current == target {
            return ShortestPathLengthResult {
                length: Some(current_dist),
                witness: ComplexityWitness {
                    algorithm: "bfs_shortest_path_length".to_owned(),
                    complexity_claim: "O(|V| + |E|)".to_owned(),
                    nodes_touched: dist.len(),
                    edges_scanned,
                    queue_peak,
                },
            };
        }
        if let Some(neighbors) = graph.neighbors_iter(current) {
            for neighbor in neighbors {
                edges_scanned += 1;
                if !dist.contains_key(neighbor) {
                    dist.insert(neighbor, current_dist + 1);
                    queue.push_back(neighbor);
                }
            }
        }
        if queue.len() > queue_peak {
            queue_peak = queue.len();
        }
    }

    ShortestPathLengthResult {
        length: None,
        witness: ComplexityWitness {
            algorithm: "bfs_shortest_path_length".to_owned(),
            complexity_claim: "O(|V| + |E|)".to_owned(),
            nodes_touched: dist.len(),
            edges_scanned,
            queue_peak,
        },
    }
}

/// Computes the minimum spanning tree using Kruskal's algorithm.
///
/// Reads edge weights from the attribute `weight_attr` (parsed as `f64`).
/// Missing or unparseable weights default to `1.0`.
/// Returns edges in deterministic sorted order `(min(u,v), max(u,v))`.
#[must_use]
pub fn minimum_spanning_tree(graph: &Graph, weight_attr: &str) -> MinimumSpanningTreeResult {
    let nodes = graph.nodes_ordered();
    let n = nodes.len();
    if n == 0 {
        return MinimumSpanningTreeResult {
            edges: Vec::new(),
            total_weight: 0.0,
            witness: ComplexityWitness {
                algorithm: "kruskal_mst".to_owned(),
                complexity_claim: "O(|E| log |E|)".to_owned(),
                nodes_touched: 0,
                edges_scanned: 0,
                queue_peak: 0,
            },
        };
    }

    // Collect all edges with weights
    let mut edge_list: Vec<(f64, &str, &str)> = Vec::new();
    let mut seen = HashSet::new();
    for node in &nodes {
        if let Some(neighbors) = graph.neighbors_iter(node) {
            for neighbor in neighbors {
                let (left, right) = if *node <= neighbor {
                    (*node, neighbor)
                } else {
                    (neighbor, *node)
                };
                if seen.insert((left, right)) {
                    let weight = matching_edge_weight_or_default(graph, left, right, weight_attr);
                    edge_list.push((weight, left, right));
                }
            }
        }
    }

    let edges_scanned = edge_list.len();

    // Sort by weight, then deterministic tie-break by (left, right)
    edge_list.sort_by(|a, b| {
        a.0.partial_cmp(&b.0)
            .unwrap_or(std::cmp::Ordering::Equal)
            .then_with(|| a.1.cmp(b.1))
            .then_with(|| a.2.cmp(b.2))
    });

    // Union-Find
    let mut parent: HashMap<&str, &str> = HashMap::new();
    let mut rank: HashMap<&str, usize> = HashMap::new();
    for node in &nodes {
        parent.insert(node, node);
        rank.insert(node, 0);
    }

    fn find<'a>(parent: &mut HashMap<&'a str, &'a str>, x: &'a str) -> &'a str {
        let mut root = x;
        while parent[root] != root {
            root = parent[root];
        }
        // Path compression
        let mut current = x;
        while current != root {
            let next = parent[current];
            parent.insert(current, root);
            current = next;
        }
        root
    }

    let mut mst_edges = Vec::new();
    let mut total_weight = 0.0;
    let mut nodes_touched = 0usize;

    for (weight, left, right) in &edge_list {
        let root_a = find(&mut parent, left);
        let root_b = find(&mut parent, right);
        if root_a != root_b {
            // Union by rank
            let rank_a = rank[root_a];
            let rank_b = rank[root_b];
            if rank_a < rank_b {
                parent.insert(root_a, root_b);
            } else if rank_a > rank_b {
                parent.insert(root_b, root_a);
            } else {
                parent.insert(root_b, root_a);
                rank.insert(root_a, rank_a + 1);
            }
            mst_edges.push(MstEdge {
                left: left.to_string(),
                right: right.to_string(),
                weight: *weight,
            });
            total_weight += weight;
            nodes_touched += 2;
            if mst_edges.len() == n - 1 {
                break;
            }
        }
    }

    MinimumSpanningTreeResult {
        edges: mst_edges,
        total_weight,
        witness: ComplexityWitness {
            algorithm: "kruskal_mst".to_owned(),
            complexity_claim: "O(|E| log |E|)".to_owned(),
            nodes_touched: nodes_touched.min(n),
            edges_scanned,
            queue_peak: 0,
        },
    }
}

/// Counts the number of triangles each node participates in.
///
/// A triangle is a 3-clique. Each triangle is counted once per participating node.
/// Returns nodes in deterministic canonical order.
#[must_use]
pub fn triangles(graph: &Graph) -> TrianglesResult {
    let nodes = graph.nodes_ordered();
    let n = nodes.len();
    if n == 0 {
        return TrianglesResult {
            triangles: Vec::new(),
            witness: ComplexityWitness {
                algorithm: "triangle_count".to_owned(),
                complexity_claim: "O(|V| * deg^2)".to_owned(),
                nodes_touched: 0,
                edges_scanned: 0,
                queue_peak: 0,
            },
        };
    }

    let neighbor_sets: HashMap<&str, HashSet<&str>> = nodes
        .iter()
        .map(|&node| {
            let set = graph
                .neighbors_iter(node)
                .map(|iter| iter.collect::<HashSet<&str>>())
                .unwrap_or_default();
            (node, set)
        })
        .collect();

    let mut tri_count: HashMap<&str, usize> = nodes.iter().map(|&n| (n, 0)).collect();
    let mut edges_scanned = 0usize;

    for &u in &nodes {
        if let Some(neighbors) = graph.neighbors_iter(u) {
            for v in neighbors {
                if u < v {
                    edges_scanned += 1;
                    let nbrs_v = &neighbor_sets[v];
                    for &w in &neighbor_sets[u] {
                        if v < w && nbrs_v.contains(w) {
                            *tri_count.entry(u).or_default() += 1;
                            *tri_count.entry(v).or_default() += 1;
                            *tri_count.entry(w).or_default() += 1;
                        }
                    }
                }
            }
        }
    }

    let mut result: Vec<NodeTriangleCount> = nodes
        .iter()
        .map(|&node| NodeTriangleCount {
            node: node.to_owned(),
            count: tri_count[node],
        })
        .collect();
    result.sort_by(|a, b| a.node.cmp(&b.node));

    TrianglesResult {
        triangles: result,
        witness: ComplexityWitness {
            algorithm: "triangle_count".to_owned(),
            complexity_claim: "O(|V| * deg^2)".to_owned(),
            nodes_touched: n,
            edges_scanned,
            queue_peak: 0,
        },
    }
}

/// Computes the square clustering coefficient for each node.
///
/// The square clustering of a node `v` is the fraction of possible squares
/// that actually exist through `v`, following the definition from NetworkX:
/// `C_4(v) = Σ q_v(u,w) / Σ [a_v(u,w) + q_v(u,w)]`
/// where q_v(u,w) counts common neighbors of u and w excluding v,
/// and a_v(u,w) accounts for the potential connections.
#[must_use]
pub fn square_clustering(graph: &Graph) -> SquareClusteringResult {
    let nodes = graph.nodes_ordered();
    let n = nodes.len();
    if n == 0 {
        return SquareClusteringResult {
            scores: Vec::new(),
            witness: ComplexityWitness {
                algorithm: "square_clustering".to_owned(),
                complexity_claim: "O(|V| * deg^3)".to_owned(),
                nodes_touched: 0,
                edges_scanned: 0,
                queue_peak: 0,
            },
        };
    }

    let neighbor_sets: HashMap<&str, HashSet<&str>> = nodes
        .iter()
        .map(|&node| {
            let set = graph
                .neighbors_iter(node)
                .map(|iter| iter.collect::<HashSet<&str>>())
                .unwrap_or_default();
            (node, set)
        })
        .collect();

    let mut edges_scanned = 0usize;
    let mut scores = Vec::with_capacity(n);

    for &v in &nodes {
        let nbrs_v = &neighbor_sets[v];
        let deg = nbrs_v.len();
        if deg < 2 {
            scores.push(CentralityScore {
                node: v.to_owned(),
                score: 0.0,
            });
            continue;
        }

        let nbrs_sorted: Vec<&str> = {
            let mut ns: Vec<&str> = nbrs_v.iter().copied().collect();
            ns.sort_unstable();
            ns
        };

        let mut numerator = 0usize;
        let mut denominator = 0usize;

        for (i, &u) in nbrs_sorted.iter().enumerate() {
            let nbrs_u = &neighbor_sets[u];
            for &w in &nbrs_sorted[i + 1..] {
                edges_scanned += 1;
                let nbrs_w = &neighbor_sets[w];
                // q_v(u,w): common neighbors of u and w, excluding v
                let q: usize = nbrs_u
                    .iter()
                    .filter(|&&x| x != v && nbrs_w.contains(x))
                    .count();
                // theta_uw: 1 if u and w are connected
                let theta_uw: usize = if nbrs_u.contains(w) { 1 } else { 0 };
                // a_v(u,w) = (deg(u) - 1 - q - theta_uw) + (deg(w) - 1 - q - theta_uw)
                let a = (nbrs_u.len().saturating_sub(1 + q + theta_uw))
                    + (nbrs_w.len().saturating_sub(1 + q + theta_uw));
                numerator += q;
                denominator += a + q;
            }
        }

        let score = if denominator == 0 {
            0.0
        } else {
            numerator as f64 / denominator as f64
        };

        scores.push(CentralityScore {
            node: v.to_owned(),
            score,
        });
    }

    scores.sort_by(|a, b| a.node.cmp(&b.node));

    SquareClusteringResult {
        scores,
        witness: ComplexityWitness {
            algorithm: "square_clustering".to_owned(),
            complexity_claim: "O(|V| * deg^3)".to_owned(),
            nodes_touched: n,
            edges_scanned,
            queue_peak: 0,
        },
    }
}

/// Checks whether the graph is a tree (connected acyclic graph).
///
/// A tree has exactly `|V| - 1` edges and is connected.
#[must_use]
pub fn is_tree(graph: &Graph) -> IsTreeResult {
    let n = graph.node_count();
    let m = graph.edge_count();

    // Single node is a tree; empty graph (0 nodes) is not (matches NetworkX)
    if n <= 1 {
        return IsTreeResult {
            is_tree: n == 1,
            witness: ComplexityWitness {
                algorithm: "is_tree".to_owned(),
                complexity_claim: "O(|V| + |E|)".to_owned(),
                nodes_touched: n,
                edges_scanned: 0,
                queue_peak: 0,
            },
        };
    }

    // Quick check: a tree must have exactly n-1 edges
    if m != n - 1 {
        return IsTreeResult {
            is_tree: false,
            witness: ComplexityWitness {
                algorithm: "is_tree".to_owned(),
                complexity_claim: "O(|V| + |E|)".to_owned(),
                nodes_touched: 0,
                edges_scanned: 0,
                queue_peak: 0,
            },
        };
    }

    // Check connectivity via BFS
    let conn = is_connected(graph);
    IsTreeResult {
        is_tree: conn.is_connected,
        witness: ComplexityWitness {
            algorithm: "is_tree".to_owned(),
            complexity_claim: "O(|V| + |E|)".to_owned(),
            nodes_touched: conn.witness.nodes_touched,
            edges_scanned: conn.witness.edges_scanned,
            queue_peak: conn.witness.queue_peak,
        },
    }
}

/// Checks whether the graph is a forest (acyclic graph, possibly disconnected).
///
/// A forest has exactly `|V| - C` edges, where `C` is the number of connected components.
#[must_use]
pub fn is_forest(graph: &Graph) -> IsForestResult {
    let n = graph.node_count();
    let m = graph.edge_count();

    if n == 0 {
        return IsForestResult {
            is_forest: true,
            witness: ComplexityWitness {
                algorithm: "is_forest".to_owned(),
                complexity_claim: "O(|V| + |E|)".to_owned(),
                nodes_touched: 0,
                edges_scanned: 0,
                queue_peak: 0,
            },
        };
    }

    // A forest with C components has exactly n - C edges
    let comp = number_connected_components(graph);
    let expected_edges = n - comp.count;
    IsForestResult {
        is_forest: m == expected_edges,
        witness: ComplexityWitness {
            algorithm: "is_forest".to_owned(),
            complexity_claim: "O(|V| + |E|)".to_owned(),
            nodes_touched: comp.witness.nodes_touched,
            edges_scanned: comp.witness.edges_scanned,
            queue_peak: comp.witness.queue_peak,
        },
    }
}

/// Greedy graph coloring in canonical (sorted) node order.
///
/// Assigns each node the smallest integer color not used by any neighbor,
/// processing nodes in lexicographic order for determinism.
#[must_use]
pub fn greedy_color(graph: &Graph) -> GreedyColorResult {
    let nodes = graph.nodes_ordered();
    let n = nodes.len();
    let mut color_map: HashMap<&str, usize> = HashMap::new();
    let mut max_color = 0usize;
    let mut edges_scanned = 0usize;

    // Process nodes in sorted (canonical) order
    let mut sorted_nodes = nodes.clone();
    sorted_nodes.sort_unstable();

    for &node in &sorted_nodes {
        let mut neighbor_colors = HashSet::new();
        if let Some(neighbors) = graph.neighbors_iter(node) {
            for neighbor in neighbors {
                edges_scanned += 1;
                if let Some(&c) = color_map.get(neighbor) {
                    neighbor_colors.insert(c);
                }
            }
        }
        let mut color = 0;
        while neighbor_colors.contains(&color) {
            color += 1;
        }
        color_map.insert(node, color);
        if color > max_color {
            max_color = color;
        }
    }

    let coloring: Vec<NodeColor> = sorted_nodes
        .iter()
        .map(|&node| NodeColor {
            node: node.to_owned(),
            color: color_map[node],
        })
        .collect();

    let num_colors = if n == 0 { 0 } else { max_color + 1 };

    GreedyColorResult {
        coloring,
        num_colors,
        witness: ComplexityWitness {
            algorithm: "greedy_color".to_owned(),
            complexity_claim: "O(|V| * deg)".to_owned(),
            nodes_touched: n,
            edges_scanned,
            queue_peak: 0,
        },
    }
}

/// Checks whether the graph is bipartite.
///
/// Uses BFS 2-coloring. Returns true if the graph can be divided into two
/// disjoint sets where every edge connects a node from one set to the other.
#[must_use]
pub fn is_bipartite(graph: &Graph) -> IsBipartiteResult {
    let result = bipartite_sets(graph);
    IsBipartiteResult {
        is_bipartite: result.is_bipartite,
        witness: result.witness,
    }
}

/// Computes the two sets of a bipartite graph via BFS 2-coloring.
///
/// If the graph is not bipartite, returns `is_bipartite: false` with empty sets.
/// Sets are returned in sorted order for determinism.
#[must_use]
pub fn bipartite_sets(graph: &Graph) -> BipartiteSetsResult {
    let nodes = graph.nodes_ordered();
    let n = nodes.len();

    if n == 0 {
        return BipartiteSetsResult {
            is_bipartite: true,
            set_a: Vec::new(),
            set_b: Vec::new(),
            witness: ComplexityWitness {
                algorithm: "bipartite_bfs".to_owned(),
                complexity_claim: "O(|V| + |E|)".to_owned(),
                nodes_touched: 0,
                edges_scanned: 0,
                queue_peak: 0,
            },
        };
    }

    let mut color: HashMap<&str, u8> = HashMap::new();
    let mut queue = VecDeque::new();
    let mut edges_scanned = 0usize;
    let mut queue_peak = 0usize;

    // Process all connected components
    let mut sorted_nodes = nodes.clone();
    sorted_nodes.sort_unstable();

    for &start in &sorted_nodes {
        if color.contains_key(start) {
            continue;
        }
        color.insert(start, 0);
        queue.push_back(start);
        if queue.len() > queue_peak {
            queue_peak = queue.len();
        }

        while let Some(current) = queue.pop_front() {
            let current_color = color[current];
            if let Some(neighbors) = graph.neighbors_iter(current) {
                for neighbor in neighbors {
                    edges_scanned += 1;
                    match color.get(neighbor) {
                        Some(&c) if c == current_color => {
                            // Odd cycle found - not bipartite
                            return BipartiteSetsResult {
                                is_bipartite: false,
                                set_a: Vec::new(),
                                set_b: Vec::new(),
                                witness: ComplexityWitness {
                                    algorithm: "bipartite_bfs".to_owned(),
                                    complexity_claim: "O(|V| + |E|)".to_owned(),
                                    nodes_touched: color.len(),
                                    edges_scanned,
                                    queue_peak,
                                },
                            };
                        }
                        Some(_) => {} // Already colored correctly
                        None => {
                            color.insert(neighbor, 1 - current_color);
                            queue.push_back(neighbor);
                            if queue.len() > queue_peak {
                                queue_peak = queue.len();
                            }
                        }
                    }
                }
            }
        }
    }

    let mut set_a: Vec<String> = Vec::new();
    let mut set_b: Vec<String> = Vec::new();
    for (&node, &c) in &color {
        if c == 0 {
            set_a.push(node.to_owned());
        } else {
            set_b.push(node.to_owned());
        }
    }
    set_a.sort();
    set_b.sort();

    BipartiteSetsResult {
        is_bipartite: true,
        set_a,
        set_b,
        witness: ComplexityWitness {
            algorithm: "bipartite_bfs".to_owned(),
            complexity_claim: "O(|V| + |E|)".to_owned(),
            nodes_touched: color.len(),
            edges_scanned,
            queue_peak,
        },
    }
}

/// Computes the core number for every node using the iterative peeling algorithm.
///
/// The core number of a node v is the largest value k such that v belongs to the
/// k-core (the maximal subgraph where every node has degree >= k).
#[must_use]
pub fn core_number(graph: &Graph) -> CoreNumberResult {
    let nodes = graph.nodes_ordered();
    let n = nodes.len();
    if n == 0 {
        return CoreNumberResult {
            core_numbers: Vec::new(),
            witness: ComplexityWitness {
                algorithm: "core_number".to_owned(),
                complexity_claim: "O(|V| + |E|)".to_owned(),
                nodes_touched: 0,
                edges_scanned: 0,
                queue_peak: 0,
            },
        };
    }

    // Compute initial degrees
    let mut degree: HashMap<&str, usize> = HashMap::new();
    for &node in &nodes {
        let deg = graph
            .neighbors_iter(node)
            .map(|iter| iter.count())
            .unwrap_or(0);
        degree.insert(node, deg);
    }

    // Sort nodes by degree (ascending), with lexicographic tie-break
    let mut sorted: Vec<&str> = nodes.clone();
    sorted.sort_by(|a, b| degree[a].cmp(&degree[b]).then_with(|| a.cmp(b)));

    // Build position map for bin-sort update
    let mut pos: HashMap<&str, usize> = HashMap::new();
    for (i, &node) in sorted.iter().enumerate() {
        pos.insert(node, i);
    }

    // Bin boundaries
    let max_deg = sorted.iter().map(|n| degree[n]).max().unwrap_or(0);
    let mut bin_start: Vec<usize> = vec![0; max_deg + 1];
    for &node in &sorted {
        bin_start[degree[node]] += 1;
    }
    let mut cumsum = 0;
    for start in &mut bin_start {
        let count = *start;
        *start = cumsum;
        cumsum += count;
    }

    let mut core: HashMap<&str, usize> = HashMap::new();
    let mut edges_scanned = 0usize;

    // Peeling: process nodes in order of current degree
    for i in 0..n {
        let v = sorted[i];
        core.insert(v, degree[v]);
        if let Some(neighbors) = graph.neighbors_iter(v) {
            for u in neighbors {
                edges_scanned += 1;
                if degree[u] > degree[v] {
                    // Move u earlier in sorted order (decrease its effective degree)
                    let du = degree[u];
                    let pu = pos[u];
                    let pw = bin_start[du];
                    let w = sorted[pw];
                    if u != w {
                        // Swap positions of u and w
                        sorted[pu] = w;
                        sorted[pw] = u;
                        pos.insert(u, pw);
                        pos.insert(w, pu);
                    }
                    bin_start[du] += 1;
                    degree.insert(u, du - 1);
                }
            }
        }
    }

    let mut result: Vec<NodeCoreNumber> = core
        .into_iter()
        .map(|(node, c)| NodeCoreNumber {
            node: node.to_owned(),
            core: c,
        })
        .collect();
    result.sort_by(|a, b| a.node.cmp(&b.node));

    CoreNumberResult {
        core_numbers: result,
        witness: ComplexityWitness {
            algorithm: "core_number".to_owned(),
            complexity_claim: "O(|V| + |E|)".to_owned(),
            nodes_touched: n,
            edges_scanned,
            queue_peak: 0,
        },
    }
}

/// Computes the average neighbor degree for each node.
///
/// For node v with neighbors N(v), the average neighbor degree is:
/// `mean(deg(u) for u in N(v))`, or 0.0 if deg(v) == 0.
#[must_use]
pub fn average_neighbor_degree(graph: &Graph) -> AverageNeighborDegreeResult {
    let nodes = graph.nodes_ordered();
    let n = nodes.len();
    if n == 0 {
        return AverageNeighborDegreeResult {
            scores: Vec::new(),
            witness: ComplexityWitness {
                algorithm: "average_neighbor_degree".to_owned(),
                complexity_claim: "O(|V| * deg)".to_owned(),
                nodes_touched: 0,
                edges_scanned: 0,
                queue_peak: 0,
            },
        };
    }

    // Precompute degrees
    let degrees: HashMap<&str, usize> = nodes
        .iter()
        .map(|&node| {
            let deg = graph
                .neighbors_iter(node)
                .map(|iter| iter.count())
                .unwrap_or(0);
            (node, deg)
        })
        .collect();

    let mut edges_scanned = 0usize;
    let mut scores: Vec<NodeAvgNeighborDegree> = Vec::with_capacity(n);

    for &node in &nodes {
        let deg = degrees[node];
        if deg == 0 {
            scores.push(NodeAvgNeighborDegree {
                node: node.to_owned(),
                avg_neighbor_degree: 0.0,
            });
            continue;
        }
        let mut sum_deg = 0usize;
        if let Some(neighbors) = graph.neighbors_iter(node) {
            for neighbor in neighbors {
                edges_scanned += 1;
                sum_deg += degrees[neighbor];
            }
        }
        scores.push(NodeAvgNeighborDegree {
            node: node.to_owned(),
            avg_neighbor_degree: sum_deg as f64 / deg as f64,
        });
    }

    scores.sort_by(|a, b| a.node.cmp(&b.node));

    AverageNeighborDegreeResult {
        scores,
        witness: ComplexityWitness {
            algorithm: "average_neighbor_degree".to_owned(),
            complexity_claim: "O(|V| * deg)".to_owned(),
            nodes_touched: n,
            edges_scanned,
            queue_peak: 0,
        },
    }
}

/// Computes the degree assortativity coefficient of the graph.
///
/// This is the Pearson correlation coefficient of degrees across edges.
/// Returns 0.0 for graphs with fewer than 2 edges or zero variance in degree.
#[must_use]
pub fn degree_assortativity_coefficient(graph: &Graph) -> DegreeAssortativityResult {
    let nodes = graph.nodes_ordered();
    let n = nodes.len();

    // Collect degree pairs for each edge — both directions per undirected edge
    // (matches NetworkX's mixing-matrix approach for undirected graphs)
    let mut degree_pairs: Vec<(f64, f64)> = Vec::new();
    let mut seen = HashSet::new();
    let mut edges_scanned = 0usize;

    // Precompute degrees
    let degrees: HashMap<&str, usize> = nodes
        .iter()
        .map(|&node| {
            let deg = graph
                .neighbors_iter(node)
                .map(|iter| iter.count())
                .unwrap_or(0);
            (node, deg)
        })
        .collect();

    for &node in &nodes {
        if let Some(neighbors) = graph.neighbors_iter(node) {
            let deg_u = degrees[node];
            for neighbor in neighbors {
                let (left, right) = if node <= neighbor {
                    (node, neighbor)
                } else {
                    (neighbor, node)
                };
                if seen.insert((left, right)) {
                    edges_scanned += 1;
                    let deg_v = degrees[neighbor];
                    // Both directions for undirected edge
                    degree_pairs.push((deg_u as f64, deg_v as f64));
                    degree_pairs.push((deg_v as f64, deg_u as f64));
                }
            }
        }
    }

    let m = degree_pairs.len();
    if m < 2 {
        return DegreeAssortativityResult {
            coefficient: 0.0,
            witness: ComplexityWitness {
                algorithm: "degree_assortativity".to_owned(),
                complexity_claim: "O(|E|)".to_owned(),
                nodes_touched: n,
                edges_scanned,
                queue_peak: 0,
            },
        };
    }

    // Pearson correlation of (deg_u, deg_v) across edges
    let mf = m as f64;
    let sum_x: f64 = degree_pairs.iter().map(|(x, _)| x).sum();
    let sum_y: f64 = degree_pairs.iter().map(|(_, y)| y).sum();
    let sum_xy: f64 = degree_pairs.iter().map(|(x, y)| x * y).sum();
    let sum_x2: f64 = degree_pairs.iter().map(|(x, _)| x * x).sum();
    let sum_y2: f64 = degree_pairs.iter().map(|(_, y)| y * y).sum();

    let numerator = mf * sum_xy - sum_x * sum_y;
    let denom_x = (mf * sum_x2 - sum_x * sum_x).sqrt();
    let denom_y = (mf * sum_y2 - sum_y * sum_y).sqrt();
    let denominator = denom_x * denom_y;

    let coefficient = if denominator.abs() < 1e-15 {
        0.0
    } else {
        numerator / denominator
    };

    DegreeAssortativityResult {
        coefficient,
        witness: ComplexityWitness {
            algorithm: "degree_assortativity".to_owned(),
            complexity_claim: "O(|E|)".to_owned(),
            nodes_touched: n,
            edges_scanned,
            queue_peak: 0,
        },
    }
}

/// Computes VoteRank centrality — iterative voting to find influential spreaders.
///
/// Each round: every node votes for its best unranked neighbor (vote power
/// initially 1.0). The node with the highest total vote is selected and its
/// neighbors' vote powers are reduced by `1/avg_degree`. Repeats until no
/// more nodes receive votes.
#[must_use]
pub fn voterank(graph: &Graph) -> VoterankResult {
    let nodes = graph.nodes_ordered();
    let n = nodes.len();
    if n == 0 {
        return VoterankResult {
            ranked: Vec::new(),
            witness: ComplexityWitness {
                algorithm: "voterank".to_owned(),
                complexity_claim: "O(|V|^2)".to_owned(),
                nodes_touched: 0,
                edges_scanned: 0,
                queue_peak: 0,
            },
        };
    }

    let edge_count = graph.edge_count();
    let avg_degree = if n > 0 {
        (2.0 * edge_count as f64) / n as f64
    } else {
        0.0
    };
    let decay = if avg_degree > 0.0 {
        1.0 / avg_degree
    } else {
        0.0
    };

    let mut vote_power: HashMap<&str, f64> = nodes.iter().map(|&v| (v, 1.0)).collect();
    let mut ranked: Vec<String> = Vec::new();
    let mut selected: HashSet<&str> = HashSet::new();
    let mut edges_scanned = 0usize;

    loop {
        // Accumulate votes
        let mut scores: HashMap<&str, f64> = HashMap::new();
        for &node in &nodes {
            if selected.contains(node) {
                continue;
            }
            if let Some(neighbors) = graph.neighbors_iter(node) {
                for neighbor in neighbors {
                    edges_scanned += 1;
                    if !selected.contains(neighbor) {
                        *scores.entry(neighbor).or_insert(0.0) += vote_power[node];
                    }
                }
            }
        }

        if scores.is_empty() {
            break;
        }

        // Find node with max score; deterministic tie-break by node name (ascending)
        let mut candidates: Vec<(&str, f64)> = scores.into_iter().collect();
        candidates.sort_by(|a, b| {
            b.1.partial_cmp(&a.1)
                .unwrap_or(std::cmp::Ordering::Equal)
                .then_with(|| a.0.cmp(b.0))
        });
        let best = candidates.first().copied();

        let Some((winner, max_score)) = best else {
            break;
        };
        if max_score <= 0.0 {
            break;
        }

        ranked.push(winner.to_owned());
        selected.insert(winner);

        // Reduce vote power of winner's neighbors
        vote_power.insert(winner, 0.0);
        if let Some(neighbors) = graph.neighbors_iter(winner) {
            for neighbor in neighbors {
                if !selected.contains(neighbor) {
                    let current = vote_power[neighbor];
                    let new_power = (current - decay).max(0.0);
                    vote_power.insert(neighbor, new_power);
                }
            }
        }
    }

    VoterankResult {
        ranked,
        witness: ComplexityWitness {
            algorithm: "voterank".to_owned(),
            complexity_claim: "O(|V|^2)".to_owned(),
            nodes_touched: n,
            edges_scanned,
            queue_peak: 0,
        },
    }
}

/// Enumerate all maximal cliques using the Bron-Kerbosch algorithm with pivoting.
///
/// Each clique is returned as a sorted `Vec<String>`. The outer vector is sorted
/// lexicographically so output is deterministic regardless of internal iteration order.
///
/// Matches `networkx.algorithms.clique.find_cliques`:
/// - Empty graph → empty vec
/// - Isolated node → singleton clique `[node]`
pub fn find_cliques(graph: &Graph) -> FindCliquesResult {
    let nodes = graph.nodes_ordered();
    let n = nodes.len();
    let mut edges_scanned: usize = 0;

    if n == 0 {
        return FindCliquesResult {
            cliques: vec![],
            witness: ComplexityWitness {
                algorithm: "find_cliques_bron_kerbosch".to_owned(),
                complexity_claim: "O(3^(n/3))".to_owned(),
                nodes_touched: 0,
                edges_scanned: 0,
                queue_peak: 0,
            },
        };
    }

    // Build adjacency sets for fast neighbor lookup
    let node_to_idx: HashMap<&str, usize> =
        nodes.iter().enumerate().map(|(i, n)| (*n, i)).collect();
    let mut adj: Vec<HashSet<usize>> = vec![HashSet::new(); n];
    for i in 0..n {
        if let Some(nbrs) = graph.neighbors_iter(nodes[i]) {
            for nb in nbrs {
                if let Some(&j) = node_to_idx.get(nb) {
                    adj[i].insert(j);
                    edges_scanned += 1;
                }
            }
        }
    }

    let mut cliques: Vec<Vec<String>> = Vec::new();

    // Iterative Bron-Kerbosch with pivoting
    // Stack frame: (P, R, X)
    let p_init: HashSet<usize> = (0..n).collect();
    let r_init: HashSet<usize> = HashSet::new();
    let x_init: HashSet<usize> = HashSet::new();

    let mut stack: Vec<(HashSet<usize>, HashSet<usize>, HashSet<usize>)> =
        vec![(p_init, r_init, x_init)];
    let mut peak_stack: usize = 1;

    while let Some((p, r, x)) = stack.pop() {
        if p.is_empty() && x.is_empty() {
            // R is a maximal clique
            let mut clique: Vec<String> = r.iter().map(|&i| nodes[i].to_owned()).collect();
            clique.sort();
            cliques.push(clique);
            continue;
        }
        if p.is_empty() {
            continue;
        }

        // Choose pivot: node in P ∪ X that maximizes |P ∩ N(pivot)|
        let pivot = p
            .union(&x)
            .max_by_key(|&&v| p.intersection(&adj[v]).count())
            .copied()
            .unwrap(); // safe: P is non-empty

        // Candidates: P \ N(pivot)
        let candidates: Vec<usize> = p.difference(&adj[pivot]).copied().collect();

        let mut p_mut = p;
        let mut x_mut = x;

        for v in candidates {
            let mut r_new = r.clone();
            r_new.insert(v);
            let p_new: HashSet<usize> = p_mut.intersection(&adj[v]).copied().collect();
            let x_new: HashSet<usize> = x_mut.intersection(&adj[v]).copied().collect();
            stack.push((p_new, r_new, x_new));
            if stack.len() > peak_stack {
                peak_stack = stack.len();
            }
            p_mut.remove(&v);
            x_mut.insert(v);
        }
    }

    cliques.sort();

    FindCliquesResult {
        cliques,
        witness: ComplexityWitness {
            algorithm: "find_cliques_bron_kerbosch".to_owned(),
            complexity_claim: "O(3^(n/3))".to_owned(),
            nodes_touched: n,
            edges_scanned,
            queue_peak: peak_stack,
        },
    }
}

/// Return the size of the largest maximal clique (the graph's clique number).
///
/// Matches `networkx.algorithms.clique.graph_clique_number`.
/// Empty graph → 0.
pub fn graph_clique_number(graph: &Graph) -> GraphCliqueNumberResult {
    let result = find_cliques(graph);
    let clique_number = result.cliques.iter().map(|c| c.len()).max().unwrap_or(0);
    GraphCliqueNumberResult {
        clique_number,
        witness: result.witness,
    }
}

/// Edmonds-Karp max-flow on a HashMap-based auxiliary directed graph.
/// Returns (flow_value, residual).
fn aux_max_flow(
    residual: &mut HashMap<String, HashMap<String, f64>>,
    source: &str,
    sink: &str,
    stats: &mut (usize, usize, usize),
) -> f64 {
    let mut total_flow = 0.0_f64;
    loop {
        let mut predecessor: HashMap<String, String> = HashMap::new();
        let mut visited: HashSet<String> = HashSet::new();
        let mut queue: VecDeque<String> = VecDeque::new();
        queue.push_back(source.to_owned());
        visited.insert(source.to_owned());
        stats.0 += 1;
        stats.2 = stats.2.max(queue.len());
        let mut reached_sink = false;
        while let Some(current) = queue.pop_front() {
            let mut neighbors: Vec<String> = residual
                .get(&current)
                .map(|caps| caps.keys().cloned().collect())
                .unwrap_or_default();
            neighbors.sort_unstable();
            for neighbor in neighbors {
                stats.1 += 1;
                if visited.contains(&neighbor) {
                    continue;
                }
                let cap = residual
                    .get(&current)
                    .and_then(|caps| caps.get(&neighbor))
                    .copied()
                    .unwrap_or(0.0);
                if cap <= 0.0 {
                    continue;
                }
                predecessor.insert(neighbor.clone(), current.clone());
                visited.insert(neighbor.clone());
                stats.0 += 1;
                if neighbor == sink {
                    reached_sink = true;
                    break;
                }
                queue.push_back(neighbor);
                stats.2 = stats.2.max(queue.len());
            }
            if reached_sink {
                break;
            }
        }
        if !reached_sink {
            break;
        }
        // trace bottleneck
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
        // update residual
        let mut cursor = sink.to_owned();
        while cursor != source {
            let prev = predecessor.get(&cursor).unwrap().clone();
            *residual
                .entry(prev.clone())
                .or_default()
                .entry(cursor.clone())
                .or_insert(0.0) -= bottleneck;
            *residual
                .entry(cursor.clone())
                .or_default()
                .entry(prev.clone())
                .or_insert(0.0) += bottleneck;
            cursor = prev;
        }
        total_flow += bottleneck;
    }
    total_flow
}

/// Build auxiliary directed graph for node connectivity:
/// Each node v → v_in, v_out with capacity 1.0.
/// Each original edge (u,v) → u_out→v_in and v_out→u_in with large capacity.
fn build_node_split_auxiliary(graph: &Graph) -> HashMap<String, HashMap<String, f64>> {
    let nodes = graph.nodes_ordered();
    let large_cap = (nodes.len() + 1) as f64;
    let mut residual: HashMap<String, HashMap<String, f64>> = HashMap::new();

    for node in &nodes {
        let n_in = format!("{node}_in");
        let n_out = format!("{node}_out");
        residual.entry(n_in.clone()).or_default();
        residual.entry(n_out.clone()).or_default();
        // internal edge: n_in → n_out with capacity 1
        residual
            .entry(n_in.clone())
            .or_default()
            .insert(n_out.clone(), 1.0);
        // reverse for residual
        residual
            .entry(n_out.clone())
            .or_default()
            .entry(n_in.clone())
            .or_insert(0.0);
    }

    for node in &nodes {
        let n_out = format!("{node}_out");
        if let Some(nbrs) = graph.neighbors_iter(node) {
            for nb in nbrs {
                // Skip self-loops — NetworkX ignores them in connectivity
                if nb == *node {
                    continue;
                }
                let nb_in = format!("{nb}_in");
                // u_out → v_in with large capacity
                residual
                    .entry(n_out.clone())
                    .or_default()
                    .insert(nb_in.clone(), large_cap);
                // reverse for residual
                residual
                    .entry(nb_in.clone())
                    .or_default()
                    .entry(n_out.clone())
                    .or_insert(0.0);
            }
        }
    }

    residual
}

/// Compute node connectivity between two specific nodes s and t.
///
/// Uses node-splitting + Edmonds-Karp max-flow on auxiliary graph.
/// Matches `networkx.algorithms.connectivity.node_connectivity(G, s, t)`.
pub fn node_connectivity(graph: &Graph, source: &str, sink: &str) -> NodeConnectivityResult {
    let nodes = graph.nodes_ordered();
    let n = nodes.len();

    if !graph.has_node(source) || !graph.has_node(sink) || source == sink {
        return NodeConnectivityResult {
            value: 0,
            witness: ComplexityWitness {
                algorithm: "node_connectivity".to_owned(),
                complexity_claim: "O(|V| * |E|^2)".to_owned(),
                nodes_touched: 0,
                edges_scanned: 0,
                queue_peak: 0,
            },
        };
    }

    let mut residual = build_node_split_auxiliary(graph);
    let s_out = format!("{source}_out");
    let t_in = format!("{sink}_in");

    let mut stats = (0_usize, 0_usize, 0_usize);
    let flow = aux_max_flow(&mut residual, &s_out, &t_in, &mut stats);

    NodeConnectivityResult {
        value: flow as usize,
        witness: ComplexityWitness {
            algorithm: "node_connectivity".to_owned(),
            complexity_claim: "O(|V| * |E|^2)".to_owned(),
            nodes_touched: n,
            edges_scanned: stats.1,
            queue_peak: stats.2,
        },
    }
}

/// Compute global node connectivity: minimum s-t node connectivity over all pairs.
///
/// Algorithm 11 from Esfahanian: pick min-degree node v, start with K = deg(v),
/// check non-neighbors of v, then non-adjacent pairs of neighbors of v.
/// Matches `networkx.algorithms.connectivity.node_connectivity(G)`.
pub fn global_node_connectivity(graph: &Graph) -> NodeConnectivityResult {
    let nodes = graph.nodes_ordered();
    let n = nodes.len();

    if n <= 1 {
        return NodeConnectivityResult {
            value: 0,
            witness: ComplexityWitness {
                algorithm: "global_node_connectivity".to_owned(),
                complexity_claim: "O(|V|^2 * |V| * |E|^2)".to_owned(),
                nodes_touched: n,
                edges_scanned: 0,
                queue_peak: 0,
            },
        };
    }

    // Check connectivity first
    if !is_connected(graph).is_connected {
        return NodeConnectivityResult {
            value: 0,
            witness: ComplexityWitness {
                algorithm: "global_node_connectivity".to_owned(),
                complexity_claim: "O(|V|^2 * |V| * |E|^2)".to_owned(),
                nodes_touched: n,
                edges_scanned: 0,
                queue_peak: 0,
            },
        };
    }

    let mut total_edges_scanned = 0_usize;
    let mut max_queue_peak = 0_usize;

    // Pick node with minimum degree
    let v = nodes
        .iter()
        .min_by_key(|node| graph.neighbors_iter(node).map(|it| it.count()).unwrap_or(0))
        .unwrap();

    let v_neighbors: HashSet<&str> = graph
        .neighbors_iter(v)
        .map(|it| it.collect())
        .unwrap_or_default();

    // K starts at min degree
    let mut k = v_neighbors.len();

    // Check non-neighbors of v
    for w in &nodes {
        if *w == *v || v_neighbors.contains(*w) {
            continue;
        }
        let result = node_connectivity(graph, v, w);
        total_edges_scanned += result.witness.edges_scanned;
        max_queue_peak = max_queue_peak.max(result.witness.queue_peak);
        if result.value < k {
            k = result.value;
        }
    }

    // Check non-adjacent pairs of neighbors of v (sorted for deterministic witness values)
    let mut v_nbr_vec: Vec<&str> = v_neighbors.iter().copied().collect();
    v_nbr_vec.sort_unstable();
    for i in 0..v_nbr_vec.len() {
        for j in (i + 1)..v_nbr_vec.len() {
            let x = v_nbr_vec[i];
            let y = v_nbr_vec[j];
            // Skip if x and y are adjacent
            let x_neighbors: HashSet<&str> = graph
                .neighbors_iter(x)
                .map(|it| it.collect())
                .unwrap_or_default();
            if x_neighbors.contains(y) {
                continue;
            }
            let result = node_connectivity(graph, x, y);
            total_edges_scanned += result.witness.edges_scanned;
            max_queue_peak = max_queue_peak.max(result.witness.queue_peak);
            if result.value < k {
                k = result.value;
            }
        }
    }

    NodeConnectivityResult {
        value: k,
        witness: ComplexityWitness {
            algorithm: "global_node_connectivity".to_owned(),
            complexity_claim: "O(|V|^2 * |V| * |E|^2)".to_owned(),
            nodes_touched: n,
            edges_scanned: total_edges_scanned,
            queue_peak: max_queue_peak,
        },
    }
}

/// Compute minimum s-t node cut: the smallest set of nodes whose removal disconnects s from t.
///
/// Uses node-splitting + Edmonds-Karp, then BFS on residual to find min-cut nodes.
/// Matches `networkx.algorithms.connectivity.minimum_node_cut(G, s, t)`.
pub fn minimum_node_cut(graph: &Graph, source: &str, sink: &str) -> MinimumNodeCutResult {
    let nodes = graph.nodes_ordered();
    let n = nodes.len();

    if !graph.has_node(source) || !graph.has_node(sink) || source == sink {
        return MinimumNodeCutResult {
            cut_nodes: vec![],
            witness: ComplexityWitness {
                algorithm: "minimum_node_cut".to_owned(),
                complexity_claim: "O(|V| * |E|^2)".to_owned(),
                nodes_touched: 0,
                edges_scanned: 0,
                queue_peak: 0,
            },
        };
    }

    let mut residual = build_node_split_auxiliary(graph);
    let s_out = format!("{source}_out");
    let t_in = format!("{sink}_in");

    let mut stats = (0_usize, 0_usize, 0_usize);
    let _flow = aux_max_flow(&mut residual, &s_out, &t_in, &mut stats);

    // BFS from s_out on residual to find reachable set
    let mut visited = HashSet::<String>::new();
    let mut queue = VecDeque::<String>::new();
    queue.push_back(s_out.clone());
    visited.insert(s_out);

    while let Some(current) = queue.pop_front() {
        let neighbors: Vec<String> = residual
            .get(&current)
            .map(|caps| caps.keys().cloned().collect())
            .unwrap_or_default();
        for nb in neighbors {
            if visited.contains(&nb) {
                continue;
            }
            let cap = residual
                .get(&current)
                .and_then(|caps| caps.get(&nb))
                .copied()
                .unwrap_or(0.0);
            if cap > 0.0 {
                visited.insert(nb.clone());
                queue.push_back(nb);
            }
        }
    }

    // Cut nodes are those where v_in is reachable but v_out is not (saturated internal edge)
    // Exclude source and sink from the cut set
    let mut cut_nodes: Vec<String> = Vec::new();
    for node in &nodes {
        if *node == source || *node == sink {
            continue;
        }
        let n_in = format!("{node}_in");
        let n_out = format!("{node}_out");
        if visited.contains(&n_in) && !visited.contains(&n_out) {
            cut_nodes.push((*node).to_owned());
        }
    }
    cut_nodes.sort();

    MinimumNodeCutResult {
        cut_nodes,
        witness: ComplexityWitness {
            algorithm: "minimum_node_cut".to_owned(),
            complexity_claim: "O(|V| * |E|^2)".to_owned(),
            nodes_touched: n,
            edges_scanned: stats.1,
            queue_peak: stats.2,
        },
    }
}

/// Compute global minimum node cut: the smallest set of nodes whose removal disconnects the graph.
///
/// Algorithm 11 from Esfahanian: pick min-degree node v, start with cut = neighbors(v),
/// check non-neighbors of v, then non-adjacent pairs of neighbors of v.
/// Matches `networkx.algorithms.connectivity.minimum_node_cut(G)`.
pub fn global_minimum_node_cut(graph: &Graph) -> MinimumNodeCutResult {
    let nodes = graph.nodes_ordered();
    let n = nodes.len();

    if n <= 1 {
        return MinimumNodeCutResult {
            cut_nodes: vec![],
            witness: ComplexityWitness {
                algorithm: "global_minimum_node_cut".to_owned(),
                complexity_claim: "O(|V|^2 * |V| * |E|^2)".to_owned(),
                nodes_touched: n,
                edges_scanned: 0,
                queue_peak: 0,
            },
        };
    }

    // Disconnected graph: NetworkX raises error; we return empty cut
    if !is_connected(graph).is_connected {
        return MinimumNodeCutResult {
            cut_nodes: vec![],
            witness: ComplexityWitness {
                algorithm: "global_minimum_node_cut".to_owned(),
                complexity_claim: "O(|V|^2 * |V| * |E|^2)".to_owned(),
                nodes_touched: n,
                edges_scanned: 0,
                queue_peak: 0,
            },
        };
    }

    let mut total_edges_scanned = 0_usize;
    let mut max_queue_peak = 0_usize;

    // Pick node with minimum degree
    let v = nodes
        .iter()
        .min_by_key(|node| graph.neighbors_iter(node).map(|it| it.count()).unwrap_or(0))
        .unwrap();

    let v_neighbors: HashSet<&str> = graph
        .neighbors_iter(v)
        .map(|it| it.collect())
        .unwrap_or_default();

    // Initial min_cut = all neighbors of v
    let mut min_cut: Vec<String> = v_neighbors.iter().map(|s| (*s).to_owned()).collect();
    min_cut.sort();

    // Check non-neighbors of v
    for w in &nodes {
        if *w == *v || v_neighbors.contains(*w) {
            continue;
        }
        let result = minimum_node_cut(graph, v, w);
        total_edges_scanned += result.witness.edges_scanned;
        max_queue_peak = max_queue_peak.max(result.witness.queue_peak);
        if result.cut_nodes.len() < min_cut.len() {
            min_cut = result.cut_nodes;
        }
    }

    // Check non-adjacent pairs of neighbors of v (sorted for determinism)
    let mut v_nbr_vec: Vec<&str> = v_neighbors.iter().copied().collect();
    v_nbr_vec.sort_unstable();
    for i in 0..v_nbr_vec.len() {
        for j in (i + 1)..v_nbr_vec.len() {
            let x = v_nbr_vec[i];
            let y = v_nbr_vec[j];
            let x_neighbors: HashSet<&str> = graph
                .neighbors_iter(x)
                .map(|it| it.collect())
                .unwrap_or_default();
            if x_neighbors.contains(y) {
                continue;
            }
            let result = minimum_node_cut(graph, x, y);
            total_edges_scanned += result.witness.edges_scanned;
            max_queue_peak = max_queue_peak.max(result.witness.queue_peak);
            if result.cut_nodes.len() < min_cut.len() {
                min_cut = result.cut_nodes;
            }
        }
    }

    min_cut.sort();

    MinimumNodeCutResult {
        cut_nodes: min_cut,
        witness: ComplexityWitness {
            algorithm: "global_minimum_node_cut".to_owned(),
            complexity_claim: "O(|V|^2 * |V| * |E|^2)".to_owned(),
            nodes_touched: n,
            edges_scanned: total_edges_scanned,
            queue_peak: max_queue_peak,
        },
    }
}

// ---------------------------------------------------------------------------
// cycle_basis — Paton's algorithm for fundamental cycle basis
// ---------------------------------------------------------------------------

/// Compute a cycle basis for an undirected graph using Paton's algorithm.
///
/// A cycle basis is a minimal set of cycles such that any cycle in the graph
/// can be expressed as a symmetric difference (XOR) of cycles from the basis.
/// Each cycle is returned as a list of node names.
#[must_use]
pub fn cycle_basis(graph: &Graph, root: Option<&str>) -> CycleBasisResult {
    let all_nodes = graph.nodes_ordered();
    let n = all_nodes.len();
    if n == 0 {
        return CycleBasisResult {
            cycles: Vec::new(),
            witness: ComplexityWitness {
                algorithm: "cycle_basis".to_owned(),
                complexity_claim: "O(|V| + |E|)".to_owned(),
                nodes_touched: 0,
                edges_scanned: 0,
                queue_peak: 0,
            },
        };
    }

    let mut gnodes: HashSet<&str> = all_nodes.iter().copied().collect();
    let mut cycles: Vec<Vec<String>> = Vec::new();
    let mut nodes_touched = 0usize;
    let mut edges_scanned = 0usize;
    let mut stack_peak = 0usize;

    let mut current_root: Option<&str> = root;

    while !gnodes.is_empty() {
        // Pick root: use provided root first time, then smallest remaining node
        let r = if let Some(r) = current_root.take() {
            gnodes.remove(r);
            r
        } else {
            // Pick lexicographically smallest remaining node for determinism
            let mut remaining: Vec<&str> = gnodes.iter().copied().collect();
            remaining.sort_unstable();
            let r = remaining[0];
            gnodes.remove(r);
            r
        };

        let mut stack: Vec<&str> = vec![r];
        let mut pred: HashMap<&str, &str> = HashMap::new();
        pred.insert(r, r);
        let mut used: HashMap<&str, HashSet<&str>> = HashMap::new();
        used.insert(r, HashSet::new());

        while let Some(z) = stack.pop() {
            nodes_touched += 1;
            stack_peak = stack_peak.max(stack.len() + 1);
            let z_used = used[z].clone();

            // Get sorted neighbors for deterministic traversal
            let mut nbrs: Vec<&str> = graph
                .neighbors_iter(z)
                .map(|iter| iter.collect())
                .unwrap_or_default();
            nbrs.sort_unstable();

            for nbr in nbrs {
                edges_scanned += 1;
                if !used.contains_key(nbr) {
                    // New node — extend spanning tree
                    pred.insert(nbr, z);
                    stack.push(nbr);
                    let mut nbr_used = HashSet::new();
                    nbr_used.insert(z);
                    used.insert(nbr, nbr_used);
                } else if nbr == z {
                    // Self loop — single-node cycle
                    cycles.push(vec![z.to_owned()]);
                } else if !z_used.contains(nbr) {
                    // Found a cycle — trace back through predecessors
                    let pn = used[nbr].clone();
                    let mut cycle: Vec<&str> = vec![nbr, z];
                    let mut p = pred[z];
                    while !pn.contains(p) {
                        cycle.push(p);
                        p = pred[p];
                    }
                    cycle.push(p);
                    cycles.push(cycle.iter().map(|s| (*s).to_owned()).collect());
                    used.get_mut(nbr).unwrap().insert(z);
                }
            }
        }

        // Remove all visited nodes from gnodes
        for &node in pred.keys() {
            gnodes.remove(node);
        }
    }

    // Sort cycles for deterministic output: sort each cycle internally, then sort outer list
    for cycle in &mut cycles {
        // Rotate so smallest element is first, matching NetworkX convention
        if let Some(min_pos) = cycle
            .iter()
            .enumerate()
            .min_by(|a, b| a.1.cmp(b.1))
            .map(|(i, _)| i)
        {
            cycle.rotate_left(min_pos);
        }
    }
    cycles.sort();

    CycleBasisResult {
        cycles,
        witness: ComplexityWitness {
            algorithm: "cycle_basis".to_owned(),
            complexity_claim: "O(|V| + |E|)".to_owned(),
            nodes_touched,
            edges_scanned,
            queue_peak: stack_peak,
        },
    }
}

// ---------------------------------------------------------------------------
// all_simple_paths — DFS enumeration of simple paths
// ---------------------------------------------------------------------------

/// Enumerate all simple (loopless) paths from source to target.
///
/// An optional `cutoff` limits the maximum path length (number of edges).
/// Without a cutoff, this can be exponential in the number of paths.
#[must_use]
pub fn all_simple_paths(
    graph: &Graph,
    source: &str,
    target: &str,
    cutoff: Option<usize>,
) -> AllSimplePathsResult {
    let nodes = graph.nodes_ordered();
    let n = nodes.len();

    if !nodes.contains(&source) || !nodes.contains(&target) {
        return AllSimplePathsResult {
            paths: Vec::new(),
            witness: ComplexityWitness {
                algorithm: "all_simple_paths".to_owned(),
                complexity_claim: "O(|V|! / (|V|-k)!)".to_owned(),
                nodes_touched: 0,
                edges_scanned: 0,
                queue_peak: 0,
            },
        };
    }

    let max_depth = cutoff.unwrap_or(n.saturating_sub(1));
    let mut paths: Vec<Vec<String>> = Vec::new();
    let mut nodes_touched = 0usize;
    let mut edges_scanned = 0usize;
    let mut stack_peak = 0usize;

    // DFS with explicit stack: (node, visited_set, current_path, neighbor_index)
    // Using iterative DFS for stack safety
    let mut visited: HashSet<&str> = HashSet::new();
    visited.insert(source);

    // Stack element: (node, sorted_neighbors, neighbor_index)
    let mut nbr_cache: HashMap<&str, Vec<&str>> = HashMap::new();
    for &node in &nodes {
        let mut nbrs: Vec<&str> = graph
            .neighbors_iter(node)
            .map(|iter| iter.collect())
            .unwrap_or_default();
        nbrs.sort_unstable();
        nbr_cache.insert(node, nbrs);
    }

    let mut stack: Vec<(&str, usize)> = vec![(source, 0)];
    let mut path: Vec<&str> = vec![source];

    while !stack.is_empty() {
        stack_peak = stack_peak.max(stack.len());
        let (node, idx) = *stack.last().unwrap();
        let nbrs = &nbr_cache[node];

        if idx < nbrs.len() {
            let next = nbrs[idx];
            stack.last_mut().unwrap().1 += 1;
            edges_scanned += 1;

            if next == target {
                nodes_touched += 1;
                let mut found_path: Vec<String> = path.iter().map(|s| (*s).to_owned()).collect();
                found_path.push(target.to_owned());
                paths.push(found_path);
            } else if !visited.contains(next) && path.len() < max_depth {
                nodes_touched += 1;
                visited.insert(next);
                path.push(next);
                stack.push((next, 0));
            }
        } else {
            // Backtrack
            stack.pop();
            if let Some(removed) = path.pop() {
                visited.remove(removed);
            }
        }
    }

    // Sort paths for deterministic output
    paths.sort();

    AllSimplePathsResult {
        paths,
        witness: ComplexityWitness {
            algorithm: "all_simple_paths".to_owned(),
            complexity_claim: "O(|V|! / (|V|-k)!)".to_owned(),
            nodes_touched,
            edges_scanned,
            queue_peak: stack_peak,
        },
    }
}

// ---------------------------------------------------------------------------
// global_efficiency / local_efficiency — Latora & Marchiori (2001)
// ---------------------------------------------------------------------------

/// Compute the average global efficiency of the graph.
///
/// The efficiency of a pair of nodes is 1 / shortest_path_distance.
/// Global efficiency is the average over all ordered pairs (u, v), u != v.
/// Edge weights are ignored (unweighted shortest paths).
#[must_use]
pub fn global_efficiency(graph: &Graph) -> GlobalEfficiencyResult {
    let nodes = graph.nodes_ordered();
    let n = nodes.len();
    if n < 2 {
        return GlobalEfficiencyResult {
            efficiency: 0.0,
            witness: ComplexityWitness {
                algorithm: "global_efficiency".to_owned(),
                complexity_claim: "O(|V| * (|V| + |E|))".to_owned(),
                nodes_touched: n,
                edges_scanned: 0,
                queue_peak: 0,
            },
        };
    }

    let denom = n * (n - 1);
    let mut total_eff = 0.0f64;
    let mut total_edges_scanned = 0usize;
    let mut max_queue_peak = 0usize;

    // BFS from each node to compute all shortest path distances
    for &source in &nodes {
        let mut dist: HashMap<&str, usize> = HashMap::new();
        dist.insert(source, 0);
        let mut queue: VecDeque<&str> = VecDeque::new();
        queue.push_back(source);

        while let Some(current) = queue.pop_front() {
            let d = dist[current];
            let mut nbrs: Vec<&str> = graph
                .neighbors_iter(current)
                .map(|iter| iter.collect())
                .unwrap_or_default();
            nbrs.sort_unstable();

            for nbr in nbrs {
                total_edges_scanned += 1;
                if !dist.contains_key(nbr) {
                    dist.insert(nbr, d + 1);
                    queue.push_back(nbr);
                    max_queue_peak = max_queue_peak.max(queue.len());
                }
            }
        }

        // Sum inverse distances for this source
        for (&target, &d) in &dist {
            if target != source && d > 0 {
                total_eff += 1.0 / d as f64;
            }
        }
    }

    let efficiency = total_eff / denom as f64;

    GlobalEfficiencyResult {
        efficiency,
        witness: ComplexityWitness {
            algorithm: "global_efficiency".to_owned(),
            complexity_claim: "O(|V| * (|V| + |E|))".to_owned(),
            nodes_touched: n,
            edges_scanned: total_edges_scanned,
            queue_peak: max_queue_peak,
        },
    }
}

/// Compute the average local efficiency of the graph.
///
/// Local efficiency of a node v is the global efficiency of the subgraph
/// induced by v's neighbors (not including v itself).
/// Average local efficiency is the mean over all nodes.
#[must_use]
pub fn local_efficiency(graph: &Graph) -> LocalEfficiencyResult {
    let nodes = graph.nodes_ordered();
    let n = nodes.len();
    if n == 0 {
        return LocalEfficiencyResult {
            efficiency: 0.0,
            witness: ComplexityWitness {
                algorithm: "local_efficiency".to_owned(),
                complexity_claim: "O(|V| * d_max * (d_max + |E_sub|))".to_owned(),
                nodes_touched: 0,
                edges_scanned: 0,
                queue_peak: 0,
            },
        };
    }

    let mut total_eff = 0.0f64;
    let mut total_edges_scanned = 0usize;
    let mut max_queue_peak = 0usize;

    for &v in &nodes {
        // Get neighbors of v
        let nbrs: HashSet<&str> = graph
            .neighbors_iter(v)
            .map(|iter| iter.collect())
            .unwrap_or_default();

        let nbr_count = nbrs.len();
        if nbr_count < 2 {
            // Subgraph with 0 or 1 nodes has efficiency 0
            continue;
        }

        let denom = nbr_count * (nbr_count - 1);
        let mut sub_eff = 0.0f64;

        // BFS from each neighbor within the induced subgraph
        for &source in &nbrs {
            let mut dist: HashMap<&str, usize> = HashMap::new();
            dist.insert(source, 0);
            let mut queue: VecDeque<&str> = VecDeque::new();
            queue.push_back(source);

            while let Some(current) = queue.pop_front() {
                let d = dist[current];
                let mut cur_nbrs: Vec<&str> = graph
                    .neighbors_iter(current)
                    .map(|iter| iter.collect())
                    .unwrap_or_default();
                cur_nbrs.sort_unstable();

                for nbr in cur_nbrs {
                    total_edges_scanned += 1;
                    // Only traverse within the induced subgraph of v's neighbors
                    if nbrs.contains(nbr) && !dist.contains_key(nbr) {
                        dist.insert(nbr, d + 1);
                        queue.push_back(nbr);
                        max_queue_peak = max_queue_peak.max(queue.len());
                    }
                }
            }

            for (&target, &d) in &dist {
                if target != source && d > 0 {
                    sub_eff += 1.0 / d as f64;
                }
            }
        }

        total_eff += sub_eff / denom as f64;
    }

    let efficiency = total_eff / n as f64;

    LocalEfficiencyResult {
        efficiency,
        witness: ComplexityWitness {
            algorithm: "local_efficiency".to_owned(),
            complexity_claim: "O(|V| * d_max * (d_max + |E_sub|))".to_owned(),
            nodes_touched: n,
            edges_scanned: total_edges_scanned,
            queue_peak: max_queue_peak,
        },
    }
}

// ---------------------------------------------------------------------------
// min_edge_cover — minimum cardinality edge cover via maximum matching
// ---------------------------------------------------------------------------

/// Compute a minimum edge cover of the graph.
///
/// An edge cover is a set of edges such that every node is incident to at least one edge.
/// Returns `None` if the graph has isolated nodes (no edge cover exists).
/// Uses maximum matching + greedy extension.
#[must_use]
pub fn min_edge_cover(graph: &Graph) -> Option<MinEdgeCoverResult> {
    let nodes = graph.nodes_ordered();
    let n = nodes.len();
    if n == 0 {
        return Some(MinEdgeCoverResult {
            edges: Vec::new(),
            witness: ComplexityWitness {
                algorithm: "min_edge_cover".to_owned(),
                complexity_claim: "O(|V|^3)".to_owned(),
                nodes_touched: 0,
                edges_scanned: 0,
                queue_peak: 0,
            },
        });
    }

    // Check for isolated nodes
    for &node in &nodes {
        let deg = graph
            .neighbors_iter(node)
            .map(|iter| iter.count())
            .unwrap_or(0);
        if deg == 0 {
            return None; // No edge cover exists
        }
    }

    // Get maximum matching using blossom algorithm (maxcardinality=true)
    let matching = max_weight_matching(graph, true, "weight");
    let mut cover: HashSet<(String, String)> = HashSet::new();
    let mut covered_nodes: HashSet<String> = HashSet::new();

    for (left, right) in &matching.matching {
        let (l, r): (String, String) = if left <= right {
            (left.clone(), right.clone())
        } else {
            (right.clone(), left.clone())
        };
        covered_nodes.insert(l.clone());
        covered_nodes.insert(r.clone());
        cover.insert((l, r));
    }

    // Greedily cover remaining uncovered nodes
    for &node in &nodes {
        if covered_nodes.contains(node) {
            continue;
        }
        // Pick the lexicographically smallest neighbor for determinism
        let mut nbrs: Vec<&str> = graph
            .neighbors_iter(node)
            .map(|iter| iter.collect())
            .unwrap_or_default();
        nbrs.sort_unstable();
        if let Some(&nbr) = nbrs.first() {
            let (l, r) = if node <= nbr {
                (node.to_owned(), nbr.to_owned())
            } else {
                (nbr.to_owned(), node.to_owned())
            };
            covered_nodes.insert(node.to_owned());
            cover.insert((l, r));
        }
    }

    let mut edges: Vec<(String, String)> = cover.into_iter().collect();
    edges.sort();

    let edges_scanned = matching.witness.edges_scanned;
    let queue_peak = matching.witness.queue_peak;

    Some(MinEdgeCoverResult {
        edges,
        witness: ComplexityWitness {
            algorithm: "min_edge_cover".to_owned(),
            complexity_claim: "O(|V|^3)".to_owned(),
            nodes_touched: n,
            edges_scanned,
            queue_peak,
        },
    })
}

/// Checks whether an undirected graph has an Eulerian circuit.
///
/// An Eulerian circuit exists iff the graph is connected (ignoring isolated nodes)
/// and every node has even degree.
#[must_use]
pub fn is_eulerian(graph: &Graph) -> IsEulerianResult {
    let nodes = graph.nodes_ordered();
    let n = nodes.len();
    let mut edges_scanned = 0usize;

    if n == 0 {
        return IsEulerianResult {
            is_eulerian: true,
            witness: ComplexityWitness {
                algorithm: "is_eulerian".to_owned(),
                complexity_claim: "O(|V| + |E|)".to_owned(),
                nodes_touched: 0,
                edges_scanned: 0,
                queue_peak: 0,
            },
        };
    }

    // Check all nodes have even degree
    for &node in &nodes {
        let deg = graph
            .neighbors_iter(node)
            .map(|iter| {
                let nbrs: Vec<_> = iter.collect();
                edges_scanned += nbrs.len();
                nbrs.len()
            })
            .unwrap_or(0);
        if !deg.is_multiple_of(2) {
            return IsEulerianResult {
                is_eulerian: false,
                witness: ComplexityWitness {
                    algorithm: "is_eulerian".to_owned(),
                    complexity_claim: "O(|V| + |E|)".to_owned(),
                    nodes_touched: n,
                    edges_scanned,
                    queue_peak: 0,
                },
            };
        }
    }

    // Check connectivity among non-isolated nodes
    let non_isolated: Vec<&str> = nodes
        .iter()
        .filter(|&&node| {
            graph
                .neighbors_iter(node)
                .map(|iter| iter.count())
                .unwrap_or(0)
                > 0
        })
        .copied()
        .collect();

    if non_isolated.is_empty() {
        // All nodes isolated => vacuously Eulerian (no edges)
        return IsEulerianResult {
            is_eulerian: true,
            witness: ComplexityWitness {
                algorithm: "is_eulerian".to_owned(),
                complexity_claim: "O(|V| + |E|)".to_owned(),
                nodes_touched: n,
                edges_scanned,
                queue_peak: 0,
            },
        };
    }

    // BFS from first non-isolated node
    let mut visited = HashSet::new();
    let mut queue = VecDeque::new();
    let mut queue_peak = 0usize;
    visited.insert(non_isolated[0]);
    queue.push_back(non_isolated[0]);

    while let Some(current) = queue.pop_front() {
        if let Some(neighbors) = graph.neighbors_iter(current) {
            for neighbor in neighbors {
                edges_scanned += 1;
                if visited.insert(neighbor) {
                    queue.push_back(neighbor);
                }
            }
        }
        if queue.len() > queue_peak {
            queue_peak = queue.len();
        }
    }

    let connected = non_isolated.iter().all(|n| visited.contains(n));

    IsEulerianResult {
        is_eulerian: connected,
        witness: ComplexityWitness {
            algorithm: "is_eulerian".to_owned(),
            complexity_claim: "O(|V| + |E|)".to_owned(),
            nodes_touched: visited.len(),
            edges_scanned,
            queue_peak,
        },
    }
}

/// Checks whether an undirected graph has an Eulerian path.
///
/// An Eulerian path exists iff the graph is connected (ignoring isolated nodes)
/// and has exactly 0 or 2 nodes of odd degree. (0 odd-degree nodes means an
/// Eulerian circuit exists, which is a special case of Eulerian path.)
#[must_use]
pub fn has_eulerian_path(graph: &Graph) -> HasEulerianPathResult {
    let nodes = graph.nodes_ordered();
    let n = nodes.len();
    let mut edges_scanned = 0usize;

    if n == 0 {
        return HasEulerianPathResult {
            has_eulerian_path: true,
            witness: ComplexityWitness {
                algorithm: "has_eulerian_path".to_owned(),
                complexity_claim: "O(|V| + |E|)".to_owned(),
                nodes_touched: 0,
                edges_scanned: 0,
                queue_peak: 0,
            },
        };
    }

    // Count odd-degree nodes
    let mut odd_degree_count = 0usize;
    for &node in &nodes {
        let deg = graph
            .neighbors_iter(node)
            .map(|iter| {
                let nbrs: Vec<_> = iter.collect();
                edges_scanned += nbrs.len();
                nbrs.len()
            })
            .unwrap_or(0);
        if !deg.is_multiple_of(2) {
            odd_degree_count += 1;
        }
    }

    if odd_degree_count != 0 && odd_degree_count != 2 {
        return HasEulerianPathResult {
            has_eulerian_path: false,
            witness: ComplexityWitness {
                algorithm: "has_eulerian_path".to_owned(),
                complexity_claim: "O(|V| + |E|)".to_owned(),
                nodes_touched: n,
                edges_scanned,
                queue_peak: 0,
            },
        };
    }

    // Check connectivity among non-isolated nodes
    let non_isolated: Vec<&str> = nodes
        .iter()
        .filter(|&&node| {
            graph
                .neighbors_iter(node)
                .map(|iter| iter.count())
                .unwrap_or(0)
                > 0
        })
        .copied()
        .collect();

    if non_isolated.is_empty() {
        return HasEulerianPathResult {
            has_eulerian_path: true,
            witness: ComplexityWitness {
                algorithm: "has_eulerian_path".to_owned(),
                complexity_claim: "O(|V| + |E|)".to_owned(),
                nodes_touched: n,
                edges_scanned,
                queue_peak: 0,
            },
        };
    }

    let mut visited = HashSet::new();
    let mut queue = VecDeque::new();
    let mut queue_peak = 0usize;
    visited.insert(non_isolated[0]);
    queue.push_back(non_isolated[0]);

    while let Some(current) = queue.pop_front() {
        if let Some(neighbors) = graph.neighbors_iter(current) {
            for neighbor in neighbors {
                edges_scanned += 1;
                if visited.insert(neighbor) {
                    queue.push_back(neighbor);
                }
            }
        }
        if queue.len() > queue_peak {
            queue_peak = queue.len();
        }
    }

    let connected = non_isolated.iter().all(|n| visited.contains(n));

    HasEulerianPathResult {
        has_eulerian_path: connected,
        witness: ComplexityWitness {
            algorithm: "has_eulerian_path".to_owned(),
            complexity_claim: "O(|V| + |E|)".to_owned(),
            nodes_touched: visited.len(),
            edges_scanned,
            queue_peak,
        },
    }
}

/// Checks whether an undirected graph is semi-Eulerian.
///
/// A graph is semi-Eulerian iff it has an Eulerian path but NOT an Eulerian circuit
/// (i.e., exactly 2 nodes of odd degree).
#[must_use]
pub fn is_semieulerian(graph: &Graph) -> IsSemiEulerianResult {
    let has_path = has_eulerian_path(graph);
    let is_circuit = is_eulerian(graph);

    IsSemiEulerianResult {
        is_semieulerian: has_path.has_eulerian_path && !is_circuit.is_eulerian,
        witness: ComplexityWitness {
            algorithm: "is_semieulerian".to_owned(),
            complexity_claim: "O(|V| + |E|)".to_owned(),
            nodes_touched: has_path.witness.nodes_touched,
            edges_scanned: has_path.witness.edges_scanned + is_circuit.witness.edges_scanned,
            queue_peak: has_path
                .witness
                .queue_peak
                .max(is_circuit.witness.queue_peak),
        },
    }
}

/// Finds an Eulerian circuit in the graph using Hierholzer's algorithm.
///
/// Returns `None` if no Eulerian circuit exists.
/// The `source` parameter optionally specifies the starting node; if `None`,
/// the lexicographically smallest non-isolated node is used.
/// Neighbor traversal is in sorted order for determinism.
#[must_use]
pub fn eulerian_circuit(graph: &Graph, source: Option<&str>) -> Option<EulerianCircuitResult> {
    let check = is_eulerian(graph);
    if !check.is_eulerian {
        return None;
    }

    // No edges → empty circuit
    if graph.edge_count() == 0 {
        return Some(EulerianCircuitResult {
            edges: Vec::new(),
            witness: ComplexityWitness {
                algorithm: "hierholzer_circuit".to_owned(),
                complexity_claim: "O(|V| + |E|)".to_owned(),
                nodes_touched: check.witness.nodes_touched,
                edges_scanned: check.witness.edges_scanned,
                queue_peak: check.witness.queue_peak,
            },
        });
    }

    let start = if let Some(s) = source {
        s.to_owned()
    } else {
        // Pick lexicographically smallest non-isolated node
        let nodes = graph.nodes_ordered();
        let mut sorted = nodes.clone();
        sorted.sort_unstable();
        sorted
            .into_iter()
            .find(|&n| {
                graph
                    .neighbors_iter(n)
                    .map(|iter| iter.count())
                    .unwrap_or(0)
                    > 0
            })
            .unwrap_or(nodes[0])
            .to_owned()
    };

    let edges = hierholzer_traverse(graph, &start);
    let edges_scanned = check.witness.edges_scanned + edges.len();

    Some(EulerianCircuitResult {
        edges,
        witness: ComplexityWitness {
            algorithm: "hierholzer_circuit".to_owned(),
            complexity_claim: "O(|V| + |E|)".to_owned(),
            nodes_touched: graph.node_count(),
            edges_scanned,
            queue_peak: check.witness.queue_peak,
        },
    })
}

/// Finds an Eulerian path in the graph using Hierholzer's algorithm.
///
/// Returns `None` if no Eulerian path exists.
/// The `source` parameter optionally specifies the starting node; if `None`,
/// one of the odd-degree nodes is used (lexicographically smallest), or if
/// all degrees are even, the smallest non-isolated node.
#[must_use]
pub fn eulerian_path(graph: &Graph, source: Option<&str>) -> Option<EulerianPathResult> {
    let check = has_eulerian_path(graph);
    if !check.has_eulerian_path {
        return None;
    }

    if graph.edge_count() == 0 {
        return Some(EulerianPathResult {
            edges: Vec::new(),
            witness: ComplexityWitness {
                algorithm: "hierholzer_path".to_owned(),
                complexity_claim: "O(|V| + |E|)".to_owned(),
                nodes_touched: check.witness.nodes_touched,
                edges_scanned: check.witness.edges_scanned,
                queue_peak: check.witness.queue_peak,
            },
        });
    }

    let start = if let Some(s) = source {
        s.to_owned()
    } else {
        // Find odd-degree nodes, pick lexicographically smallest
        let nodes = graph.nodes_ordered();
        let mut sorted = nodes.clone();
        sorted.sort_unstable();

        let odd_node = sorted.iter().find(|&&n| {
            let deg = graph
                .neighbors_iter(n)
                .map(|iter| iter.count())
                .unwrap_or(0);
            !deg.is_multiple_of(2)
        });

        if let Some(&n) = odd_node {
            n.to_owned()
        } else {
            // All even degrees → circuit case, pick smallest non-isolated
            sorted
                .into_iter()
                .find(|&n| {
                    graph
                        .neighbors_iter(n)
                        .map(|iter| iter.count())
                        .unwrap_or(0)
                        > 0
                })
                .unwrap_or(nodes[0])
                .to_owned()
        }
    };

    let edges = hierholzer_traverse(graph, &start);
    let edges_scanned = check.witness.edges_scanned + edges.len();

    Some(EulerianPathResult {
        edges,
        witness: ComplexityWitness {
            algorithm: "hierholzer_path".to_owned(),
            complexity_claim: "O(|V| + |E|)".to_owned(),
            nodes_touched: graph.node_count(),
            edges_scanned,
            queue_peak: check.witness.queue_peak,
        },
    })
}

/// Hierholzer's algorithm for finding an Euler trail starting from `start`.
///
/// Builds an adjacency structure with edge-usage tracking and walks deterministically
/// by visiting neighbors in sorted order.
fn hierholzer_traverse(graph: &Graph, start: &str) -> Vec<(String, String)> {
    // Build adjacency list with mutable edge tracking.
    // For undirected graphs, each edge appears twice (once in each direction).
    // We use a shared "used" flag via indices into a used-edges vector.
    let nodes = graph.nodes_ordered();
    let mut sorted_nodes: Vec<&str> = nodes.clone();
    sorted_nodes.sort_unstable();

    let node_index: HashMap<&str, usize> = sorted_nodes
        .iter()
        .enumerate()
        .map(|(i, &n)| (n, i))
        .collect();

    // Count edges first to allocate edge_used vector
    let mut edge_id = 0usize;
    // adj[node_idx] = Vec<(neighbor_idx, edge_id)> sorted by neighbor name
    let mut adj: Vec<Vec<(usize, usize)>> = vec![Vec::new(); sorted_nodes.len()];

    // Build edges deterministically: iterate in sorted node order
    let mut seen_edges: HashSet<(usize, usize)> = HashSet::new();
    for (i, &node) in sorted_nodes.iter().enumerate() {
        if let Some(neighbors) = graph.neighbors_iter(node) {
            let mut nbrs: Vec<&str> = neighbors.collect();
            nbrs.sort_unstable();
            for &nbr in &nbrs {
                let j = node_index[nbr];
                let key = if i <= j { (i, j) } else { (j, i) };
                if seen_edges.insert(key) {
                    adj[i].push((j, edge_id));
                    adj[j].push((i, edge_id));
                    edge_id += 1;
                }
            }
        }
    }

    // Sort adjacency lists by neighbor index (already effectively sorted by name)
    for list in &mut adj {
        list.sort_unstable_by_key(|&(nbr, _)| nbr);
    }

    let total_edges = edge_id;
    let mut edge_used = vec![false; total_edges];

    // Track current position in each adjacency list for efficiency
    let mut adj_pos: Vec<usize> = vec![0; sorted_nodes.len()];

    let start_idx = node_index[start];
    let mut stack = vec![start_idx];
    let mut trail: Vec<usize> = Vec::new();

    while let Some(&current) = stack.last() {
        // Find next unused edge from current node
        let mut found = false;
        while adj_pos[current] < adj[current].len() {
            let (nbr, eid) = adj[current][adj_pos[current]];
            adj_pos[current] += 1;
            if !edge_used[eid] {
                edge_used[eid] = true;
                stack.push(nbr);
                found = true;
                break;
            }
        }
        if !found {
            stack.pop();
            trail.push(current);
        }
    }

    // Convert node indices back to edge pairs
    trail.reverse();
    let mut edges = Vec::with_capacity(total_edges);
    for window in trail.windows(2) {
        edges.push((
            sorted_nodes[window[0]].to_owned(),
            sorted_nodes[window[1]].to_owned(),
        ));
    }

    edges
}

#[cfg(test)]
mod tests {
    use super::{
        CGSE_WITNESS_LEDGER_PATH, CGSE_WITNESS_POLICY_SPEC_PATH, CentralityScore,
        ComplexityWitness, all_simple_paths, articulation_points, bellman_ford_shortest_paths,
        betweenness_centrality, bridges, cgse_witness_schema_version, closeness_centrality,
        clustering_coefficient, connected_components, cycle_basis, degree_centrality,
        edge_betweenness_centrality, edge_connectivity_edmonds_karp, eigenvector_centrality,
        eulerian_circuit, eulerian_path, global_edge_connectivity_edmonds_karp, global_efficiency,
        global_minimum_edge_cut_edmonds_karp, harmonic_centrality, has_eulerian_path,
        hits_centrality, is_eulerian, is_matching, is_maximal_matching, is_perfect_matching,
        is_semieulerian, katz_centrality, local_efficiency, max_flow_edmonds_karp,
        max_weight_matching, maximal_matching, min_edge_cover, min_weight_matching,
        minimum_cut_edmonds_karp, minimum_st_edge_cut_edmonds_karp, multi_source_dijkstra,
        number_connected_components, pagerank, shortest_path_unweighted, shortest_path_weighted,
    };
    use fnx_classes::Graph;
    use fnx_runtime::{
        CompatibilityMode, ForensicsBundleIndex, StructuredTestLog, TestKind, TestStatus,
        canonical_environment_fingerprint, structured_test_log_schema_version,
    };
    use proptest::prelude::*;
    use std::collections::{BTreeMap, BTreeSet, HashSet};

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
    fn multi_source_dijkstra_returns_expected_distances_and_predecessors() {
        let mut graph = Graph::strict();
        graph
            .add_edge_with_attrs("a", "b", [("weight".to_owned(), "1".to_owned())].into())
            .expect("edge add should succeed");
        graph
            .add_edge_with_attrs("b", "d", [("weight".to_owned(), "2".to_owned())].into())
            .expect("edge add should succeed");
        graph
            .add_edge_with_attrs("c", "d", [("weight".to_owned(), "1".to_owned())].into())
            .expect("edge add should succeed");
        graph
            .add_edge_with_attrs("d", "e", [("weight".to_owned(), "1".to_owned())].into())
            .expect("edge add should succeed");

        let result = multi_source_dijkstra(&graph, &["a", "c"], "weight");
        let distance_map = result
            .distances
            .iter()
            .map(|entry| (entry.node.as_str(), entry.distance))
            .collect::<BTreeMap<&str, f64>>();
        assert!((distance_map.get("a").copied().unwrap_or_default() - 0.0).abs() <= 1e-12);
        assert!((distance_map.get("b").copied().unwrap_or_default() - 1.0).abs() <= 1e-12);
        assert!((distance_map.get("c").copied().unwrap_or_default() - 0.0).abs() <= 1e-12);
        assert!((distance_map.get("d").copied().unwrap_or_default() - 1.0).abs() <= 1e-12);
        assert!((distance_map.get("e").copied().unwrap_or_default() - 2.0).abs() <= 1e-12);

        let predecessor_map = result
            .predecessors
            .iter()
            .map(|entry| (entry.node.as_str(), entry.predecessor.clone()))
            .collect::<BTreeMap<&str, Option<String>>>();
        assert_eq!(predecessor_map.get("a"), Some(&None));
        assert_eq!(predecessor_map.get("c"), Some(&None));
        assert_eq!(predecessor_map.get("b"), Some(&Some("a".to_owned())));
        assert_eq!(predecessor_map.get("d"), Some(&Some("c".to_owned())));
        assert_eq!(predecessor_map.get("e"), Some(&Some("d".to_owned())));
        assert!(!result.negative_cycle_detected);
        assert_eq!(result.witness.algorithm, "multi_source_dijkstra");
    }

    #[test]
    fn multi_source_dijkstra_is_replay_stable() {
        let mut graph = Graph::strict();
        for (left, right) in [("a", "b"), ("b", "c"), ("c", "d"), ("a", "d")] {
            graph
                .add_edge_with_attrs(left, right, [("weight".to_owned(), "1".to_owned())].into())
                .expect("edge add should succeed");
        }

        let first = multi_source_dijkstra(&graph, &["a", "c"], "weight");
        let second = multi_source_dijkstra(&graph, &["a", "c"], "weight");
        assert_eq!(first, second);
    }

    #[test]
    fn multi_source_dijkstra_ignores_missing_sources() {
        let mut graph = Graph::strict();
        graph
            .add_edge_with_attrs("a", "b", [("weight".to_owned(), "3".to_owned())].into())
            .expect("edge add should succeed");

        let result = multi_source_dijkstra(&graph, &["missing", "a"], "weight");
        assert_eq!(result.distances.len(), 2);
        assert_eq!(result.predecessors.len(), 2);
        assert!(!result.negative_cycle_detected);
    }

    #[test]
    fn bellman_ford_shortest_paths_positive_weights_match_expected() {
        let mut graph = Graph::strict();
        graph
            .add_edge_with_attrs("a", "b", [("weight".to_owned(), "2".to_owned())].into())
            .expect("edge add should succeed");
        graph
            .add_edge_with_attrs("b", "c", [("weight".to_owned(), "1".to_owned())].into())
            .expect("edge add should succeed");
        graph
            .add_edge_with_attrs("a", "c", [("weight".to_owned(), "10".to_owned())].into())
            .expect("edge add should succeed");

        let result = bellman_ford_shortest_paths(&graph, "a", "weight");
        let distance_map = result
            .distances
            .iter()
            .map(|entry| (entry.node.as_str(), entry.distance))
            .collect::<BTreeMap<&str, f64>>();
        assert!((distance_map.get("a").copied().unwrap_or_default() - 0.0).abs() <= 1e-12);
        assert!((distance_map.get("b").copied().unwrap_or_default() - 2.0).abs() <= 1e-12);
        assert!((distance_map.get("c").copied().unwrap_or_default() - 3.0).abs() <= 1e-12);
        assert!(!result.negative_cycle_detected);
        assert_eq!(result.witness.algorithm, "bellman_ford_shortest_paths");
    }

    #[test]
    fn bellman_ford_shortest_paths_detects_negative_cycle() {
        let mut graph = Graph::strict();
        graph
            .add_edge_with_attrs("a", "b", [("weight".to_owned(), "-1".to_owned())].into())
            .expect("edge add should succeed");
        graph
            .add_edge_with_attrs("b", "c", [("weight".to_owned(), "2".to_owned())].into())
            .expect("edge add should succeed");

        let result = bellman_ford_shortest_paths(&graph, "a", "weight");
        assert!(result.negative_cycle_detected);
    }

    #[test]
    fn bellman_ford_shortest_paths_returns_empty_for_missing_source() {
        let mut graph = Graph::strict();
        let _ = graph.add_node("only");

        let result = bellman_ford_shortest_paths(&graph, "missing", "weight");
        assert!(result.distances.is_empty());
        assert!(result.predecessors.is_empty());
        assert!(!result.negative_cycle_detected);
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
    fn minimum_st_edge_cut_edmonds_karp_matches_expected_edges() {
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

        let result = minimum_st_edge_cut_edmonds_karp(&graph, "s", "t", "capacity");
        assert!((result.value - 5.0).abs() <= 1e-12);
        assert_eq!(
            result.cut_edges,
            vec![
                ("a".to_owned(), "s".to_owned()),
                ("b".to_owned(), "s".to_owned())
            ]
        );
        assert_eq!(result.source_partition, vec!["s".to_owned()]);
        assert_eq!(
            result.sink_partition,
            vec!["a".to_owned(), "b".to_owned(), "t".to_owned()]
        );
        assert_eq!(result.witness.algorithm, "edmonds_karp_minimum_st_edge_cut");
    }

    #[test]
    fn minimum_st_edge_cut_edmonds_karp_is_replay_stable() {
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

        let left = minimum_st_edge_cut_edmonds_karp(&graph, "s", "t", "capacity");
        let right = minimum_st_edge_cut_edmonds_karp(&graph, "s", "t", "capacity");
        assert_eq!(left, right);
    }

    #[test]
    fn edge_connectivity_edmonds_karp_matches_minimum_cut_value() {
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

        let cut = minimum_cut_edmonds_karp(&graph, "s", "t", "capacity");
        let connectivity = edge_connectivity_edmonds_karp(&graph, "s", "t", "capacity");
        assert!((connectivity.value - cut.value).abs() <= 1e-12);
        assert_eq!(
            connectivity.witness.algorithm,
            "edmonds_karp_edge_connectivity"
        );
    }

    #[test]
    fn edge_connectivity_edmonds_karp_returns_zero_for_missing_nodes() {
        let mut graph = Graph::strict();
        let _ = graph.add_node("only");
        let result = edge_connectivity_edmonds_karp(&graph, "missing", "only", "capacity");
        assert!((result.value - 0.0).abs() <= 1e-12);
    }

    #[test]
    fn global_edge_connectivity_edmonds_karp_detects_path_bottleneck() {
        let mut graph = Graph::strict();
        graph.add_edge("a", "b").expect("edge add should succeed");
        graph.add_edge("b", "c").expect("edge add should succeed");
        graph.add_edge("c", "d").expect("edge add should succeed");

        let result = global_edge_connectivity_edmonds_karp(&graph, "capacity");
        assert!((result.value - 1.0).abs() <= 1e-12);
        assert_eq!(
            result.witness.algorithm,
            "edmonds_karp_global_edge_connectivity"
        );
    }

    #[test]
    fn global_edge_connectivity_edmonds_karp_detects_triangle_redundancy() {
        let mut graph = Graph::strict();
        graph.add_edge("a", "b").expect("edge add should succeed");
        graph.add_edge("b", "c").expect("edge add should succeed");
        graph.add_edge("c", "a").expect("edge add should succeed");

        let result = global_edge_connectivity_edmonds_karp(&graph, "capacity");
        assert!((result.value - 2.0).abs() <= 1e-12);
    }

    #[test]
    fn global_edge_connectivity_edmonds_karp_disconnected_graph_is_zero() {
        let mut graph = Graph::strict();
        graph.add_edge("a", "b").expect("edge add should succeed");
        graph.add_edge("c", "d").expect("edge add should succeed");

        let result = global_edge_connectivity_edmonds_karp(&graph, "capacity");
        assert!((result.value - 0.0).abs() <= 1e-12);
    }

    #[test]
    fn global_minimum_edge_cut_edmonds_karp_path_graph_returns_first_min_pair() {
        let mut graph = Graph::strict();
        graph.add_edge("a", "b").expect("edge add should succeed");
        graph.add_edge("b", "c").expect("edge add should succeed");
        graph.add_edge("c", "d").expect("edge add should succeed");

        let result = global_minimum_edge_cut_edmonds_karp(&graph, "capacity");
        assert!((result.value - 1.0).abs() <= 1e-12);
        assert_eq!(result.source, "a");
        assert_eq!(result.sink, "b");
        assert_eq!(result.cut_edges, vec![("a".to_owned(), "b".to_owned())]);
        assert_eq!(
            result.witness.algorithm,
            "edmonds_karp_global_minimum_edge_cut"
        );
    }

    #[test]
    fn global_minimum_edge_cut_edmonds_karp_triangle_is_two() {
        let mut graph = Graph::strict();
        graph.add_edge("a", "b").expect("edge add should succeed");
        graph.add_edge("b", "c").expect("edge add should succeed");
        graph.add_edge("c", "a").expect("edge add should succeed");

        let result = global_minimum_edge_cut_edmonds_karp(&graph, "capacity");
        assert!((result.value - 2.0).abs() <= 1e-12);
        assert_eq!(result.source, "a");
        assert_eq!(result.sink, "b");
        assert_eq!(
            result.cut_edges,
            vec![
                ("a".to_owned(), "b".to_owned()),
                ("a".to_owned(), "c".to_owned())
            ]
        );
    }

    #[test]
    fn global_minimum_edge_cut_edmonds_karp_disconnected_graph_is_zero() {
        let mut graph = Graph::strict();
        graph.add_edge("a", "b").expect("edge add should succeed");
        graph.add_edge("c", "d").expect("edge add should succeed");

        let result = global_minimum_edge_cut_edmonds_karp(&graph, "capacity");
        assert!((result.value - 0.0).abs() <= 1e-12);
        assert_eq!(result.source, "a");
        assert_eq!(result.sink, "c");
        assert!(result.cut_edges.is_empty());
    }

    #[test]
    fn global_minimum_edge_cut_edmonds_karp_is_replay_stable() {
        let mut graph = Graph::strict();
        graph.add_edge("a", "b").expect("edge add should succeed");
        graph.add_edge("a", "c").expect("edge add should succeed");
        graph.add_edge("b", "d").expect("edge add should succeed");
        graph.add_edge("c", "d").expect("edge add should succeed");
        graph.add_edge("d", "e").expect("edge add should succeed");

        let left = global_minimum_edge_cut_edmonds_karp(&graph, "capacity");
        let right = global_minimum_edge_cut_edmonds_karp(&graph, "capacity");
        assert_eq!(left, right);
    }

    #[test]
    fn articulation_points_path_graph_matches_expected() {
        let mut graph = Graph::strict();
        graph.add_edge("a", "b").expect("edge add should succeed");
        graph.add_edge("b", "c").expect("edge add should succeed");
        graph.add_edge("c", "d").expect("edge add should succeed");

        let result = articulation_points(&graph);
        assert_eq!(result.nodes, vec!["b".to_owned(), "c".to_owned()]);
        assert_eq!(result.witness.algorithm, "tarjan_articulation_points");
    }

    #[test]
    fn articulation_points_cycle_graph_is_empty() {
        let mut graph = Graph::strict();
        graph.add_edge("a", "b").expect("edge add should succeed");
        graph.add_edge("b", "c").expect("edge add should succeed");
        graph.add_edge("c", "d").expect("edge add should succeed");
        graph.add_edge("d", "a").expect("edge add should succeed");

        let result = articulation_points(&graph);
        assert!(result.nodes.is_empty());
    }

    #[test]
    fn articulation_points_is_replay_stable_under_insertion_order_noise() {
        let mut forward = Graph::strict();
        for (left, right) in [("a", "b"), ("b", "c"), ("c", "d"), ("d", "e"), ("c", "f")] {
            forward
                .add_edge(left, right)
                .expect("forward edge insertion should succeed");
        }

        let mut reverse = Graph::strict();
        for (left, right) in [("c", "f"), ("d", "e"), ("c", "d"), ("b", "c"), ("a", "b")] {
            reverse
                .add_edge(left, right)
                .expect("reverse edge insertion should succeed");
        }

        let left = articulation_points(&forward);
        let right = articulation_points(&reverse);
        assert_eq!(left.nodes, right.nodes);
    }

    #[test]
    fn bridges_path_graph_matches_expected() {
        let mut graph = Graph::strict();
        graph.add_edge("a", "b").expect("edge add should succeed");
        graph.add_edge("b", "c").expect("edge add should succeed");
        graph.add_edge("c", "d").expect("edge add should succeed");

        let result = bridges(&graph);
        assert_eq!(
            result.edges,
            vec![
                ("a".to_owned(), "b".to_owned()),
                ("b".to_owned(), "c".to_owned()),
                ("c".to_owned(), "d".to_owned())
            ]
        );
        assert_eq!(result.witness.algorithm, "tarjan_bridges");
    }

    #[test]
    fn bridges_cycle_graph_is_empty() {
        let mut graph = Graph::strict();
        graph.add_edge("a", "b").expect("edge add should succeed");
        graph.add_edge("b", "c").expect("edge add should succeed");
        graph.add_edge("c", "d").expect("edge add should succeed");
        graph.add_edge("d", "a").expect("edge add should succeed");

        let result = bridges(&graph);
        assert!(result.edges.is_empty());
    }

    #[test]
    fn bridges_is_replay_stable_under_insertion_order_noise() {
        let mut forward = Graph::strict();
        for (left, right) in [("a", "b"), ("b", "c"), ("c", "d"), ("d", "e"), ("c", "f")] {
            forward
                .add_edge(left, right)
                .expect("forward edge insertion should succeed");
        }

        let mut reverse = Graph::strict();
        for (left, right) in [("c", "f"), ("d", "e"), ("c", "d"), ("b", "c"), ("a", "b")] {
            reverse
                .add_edge(left, right)
                .expect("reverse edge insertion should succeed");
        }

        let left = bridges(&forward);
        let right = bridges(&reverse);
        assert_eq!(left.edges, right.edges);
    }

    #[test]
    fn articulation_points_empty_graph_is_empty() {
        let graph = Graph::strict();
        let result = articulation_points(&graph);
        assert!(result.nodes.is_empty());
        assert_eq!(result.witness.algorithm, "tarjan_articulation_points");
        assert_eq!(result.witness.nodes_touched, 0);
        assert_eq!(result.witness.edges_scanned, 0);
    }

    #[test]
    fn bridges_empty_graph_is_empty() {
        let graph = Graph::strict();
        let result = bridges(&graph);
        assert!(result.edges.is_empty());
        assert_eq!(result.witness.algorithm, "tarjan_bridges");
    }

    #[test]
    fn articulation_points_single_node_is_empty() {
        let mut graph = Graph::strict();
        let _ = graph.add_node("lonely");
        let result = articulation_points(&graph);
        assert!(result.nodes.is_empty());
    }

    #[test]
    fn bridges_single_node_is_empty() {
        let mut graph = Graph::strict();
        let _ = graph.add_node("lonely");
        let result = bridges(&graph);
        assert!(result.edges.is_empty());
    }

    #[test]
    fn articulation_points_single_edge_is_empty() {
        let mut graph = Graph::strict();
        graph.add_edge("a", "b").expect("edge add should succeed");
        let result = articulation_points(&graph);
        assert!(result.nodes.is_empty());
    }

    #[test]
    fn bridges_single_edge_is_bridge() {
        let mut graph = Graph::strict();
        graph.add_edge("a", "b").expect("edge add should succeed");
        let result = bridges(&graph);
        assert_eq!(result.edges, vec![("a".to_owned(), "b".to_owned())]);
    }

    #[test]
    fn articulation_points_complete_k4_is_empty() {
        let mut graph = Graph::strict();
        for (left, right) in [
            ("a", "b"),
            ("a", "c"),
            ("a", "d"),
            ("b", "c"),
            ("b", "d"),
            ("c", "d"),
        ] {
            graph
                .add_edge(left, right)
                .expect("edge add should succeed");
        }
        let result = articulation_points(&graph);
        assert!(result.nodes.is_empty());
    }

    #[test]
    fn bridges_complete_k4_is_empty() {
        let mut graph = Graph::strict();
        for (left, right) in [
            ("a", "b"),
            ("a", "c"),
            ("a", "d"),
            ("b", "c"),
            ("b", "d"),
            ("c", "d"),
        ] {
            graph
                .add_edge(left, right)
                .expect("edge add should succeed");
        }
        let result = bridges(&graph);
        assert!(result.edges.is_empty());
    }

    #[test]
    fn articulation_points_star_graph_has_center() {
        let mut graph = Graph::strict();
        for leaf in ["a", "b", "c", "d"] {
            graph
                .add_edge("center", leaf)
                .expect("edge add should succeed");
        }
        let result = articulation_points(&graph);
        assert_eq!(result.nodes, vec!["center".to_owned()]);
    }

    #[test]
    fn bridges_star_graph_all_edges_are_bridges() {
        let mut graph = Graph::strict();
        for leaf in ["a", "b", "c", "d"] {
            graph
                .add_edge("center", leaf)
                .expect("edge add should succeed");
        }
        let result = bridges(&graph);
        assert_eq!(
            result.edges,
            vec![
                ("a".to_owned(), "center".to_owned()),
                ("b".to_owned(), "center".to_owned()),
                ("c".to_owned(), "center".to_owned()),
                ("center".to_owned(), "d".to_owned()),
            ]
        );
    }

    #[test]
    fn articulation_points_two_triangles_with_bridge() {
        let mut graph = Graph::strict();
        graph.add_edge("a", "b").expect("edge add should succeed");
        graph.add_edge("b", "c").expect("edge add should succeed");
        graph.add_edge("c", "a").expect("edge add should succeed");
        graph.add_edge("c", "d").expect("edge add should succeed");
        graph.add_edge("d", "e").expect("edge add should succeed");
        graph.add_edge("e", "f").expect("edge add should succeed");
        graph.add_edge("f", "d").expect("edge add should succeed");
        let result = articulation_points(&graph);
        assert_eq!(result.nodes, vec!["c".to_owned(), "d".to_owned()]);
    }

    #[test]
    fn bridges_two_triangles_with_bridge() {
        let mut graph = Graph::strict();
        graph.add_edge("a", "b").expect("edge add should succeed");
        graph.add_edge("b", "c").expect("edge add should succeed");
        graph.add_edge("c", "a").expect("edge add should succeed");
        graph.add_edge("c", "d").expect("edge add should succeed");
        graph.add_edge("d", "e").expect("edge add should succeed");
        graph.add_edge("e", "f").expect("edge add should succeed");
        graph.add_edge("f", "d").expect("edge add should succeed");
        let result = bridges(&graph);
        assert_eq!(result.edges, vec![("c".to_owned(), "d".to_owned())]);
    }

    #[test]
    fn articulation_points_disconnected_graph() {
        let mut graph = Graph::strict();
        graph.add_edge("a", "b").expect("edge add should succeed");
        graph.add_edge("b", "c").expect("edge add should succeed");
        graph.add_edge("d", "e").expect("edge add should succeed");
        graph.add_edge("e", "f").expect("edge add should succeed");
        let result = articulation_points(&graph);
        assert_eq!(result.nodes, vec!["b".to_owned(), "e".to_owned()]);
    }

    #[test]
    fn bridges_disconnected_graph() {
        let mut graph = Graph::strict();
        graph.add_edge("a", "b").expect("edge add should succeed");
        graph.add_edge("b", "c").expect("edge add should succeed");
        graph.add_edge("d", "e").expect("edge add should succeed");
        graph.add_edge("e", "f").expect("edge add should succeed");
        let result = bridges(&graph);
        assert_eq!(
            result.edges,
            vec![
                ("a".to_owned(), "b".to_owned()),
                ("b".to_owned(), "c".to_owned()),
                ("d".to_owned(), "e".to_owned()),
                ("e".to_owned(), "f".to_owned()),
            ]
        );
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
                ("2".to_owned(), "4".to_owned()),
                ("3".to_owned(), "5".to_owned())
            ]
        );
        assert!((result.total_weight - 16.0).abs() <= 1e-12);
        assert_eq!(result.witness.algorithm, "blossom_max_weight_matching");
        assert_matching_is_valid_and_maximal(&graph, &result.matching);
    }

    #[test]
    fn max_weight_matching_beats_greedy_local_choice() {
        let mut graph = Graph::strict();
        graph
            .add_edge_with_attrs("a", "b", [("weight".to_owned(), "10".to_owned())].into())
            .expect("edge add should succeed");
        graph
            .add_edge_with_attrs("a", "c", [("weight".to_owned(), "9".to_owned())].into())
            .expect("edge add should succeed");
        graph
            .add_edge_with_attrs("b", "d", [("weight".to_owned(), "9".to_owned())].into())
            .expect("edge add should succeed");
        graph
            .add_edge_with_attrs("c", "d", [("weight".to_owned(), "1".to_owned())].into())
            .expect("edge add should succeed");

        let result = max_weight_matching(&graph, false, "weight");
        assert_eq!(
            result.matching,
            vec![
                ("a".to_owned(), "c".to_owned()),
                ("b".to_owned(), "d".to_owned())
            ]
        );
        assert!((result.total_weight - 18.0).abs() <= 1e-12);
        assert_matching_is_valid_and_maximal(&graph, &result.matching);
    }

    #[test]
    fn weighted_matching_replay_stable_under_insertion_order_noise() {
        let mut forward = Graph::strict();
        for (left, right, weight) in [
            ("a", "b", "8"),
            ("a", "c", "9"),
            ("b", "d", "9"),
            ("c", "d", "8"),
            ("c", "e", "7"),
            ("d", "f", "7"),
        ] {
            forward
                .add_edge_with_attrs(
                    left,
                    right,
                    [("weight".to_owned(), weight.to_owned())].into(),
                )
                .expect("edge add should succeed");
        }
        let _ = forward.add_node("noise");

        let mut reverse = Graph::strict();
        for (left, right, weight) in [
            ("d", "f", "7"),
            ("c", "e", "7"),
            ("c", "d", "8"),
            ("b", "d", "9"),
            ("a", "c", "9"),
            ("a", "b", "8"),
        ] {
            reverse
                .add_edge_with_attrs(
                    left,
                    right,
                    [("weight".to_owned(), weight.to_owned())].into(),
                )
                .expect("edge add should succeed");
        }
        let _ = reverse.add_node("noise");

        let forward_default = max_weight_matching(&forward, false, "weight");
        let reverse_default = max_weight_matching(&reverse, false, "weight");
        assert_eq!(forward_default.matching, reverse_default.matching);
        assert!((forward_default.total_weight - reverse_default.total_weight).abs() <= 1e-12);

        let forward_cardinality = max_weight_matching(&forward, true, "weight");
        let reverse_cardinality = max_weight_matching(&reverse, true, "weight");
        assert_eq!(forward_cardinality.matching, reverse_cardinality.matching);
        assert!(
            (forward_cardinality.total_weight - reverse_cardinality.total_weight).abs() <= 1e-12
        );

        let forward_min = min_weight_matching(&forward, "weight");
        let reverse_min = min_weight_matching(&reverse, "weight");
        assert_eq!(forward_min.matching, reverse_min.matching);
        assert!((forward_min.total_weight - reverse_min.total_weight).abs() <= 1e-12);
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
            .add_edge_with_attrs("b", "d", [("weight".to_owned(), "39".to_owned())].into())
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
        assert!((maxcard_result.total_weight - 99.0).abs() <= 1e-12);
        assert_eq!(
            maxcard_result.witness.algorithm,
            "blossom_max_weight_matching_maxcardinality"
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
        assert_eq!(result.witness.algorithm, "blossom_min_weight_matching");
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

        let forward_harmonic = harmonic_centrality(&forward);
        let forward_harmonic_replay = harmonic_centrality(&forward);
        let reverse_harmonic = harmonic_centrality(&reverse);
        let reverse_harmonic_replay = harmonic_centrality(&reverse);
        assert_eq!(forward_harmonic.scores, forward_harmonic_replay.scores);
        assert_eq!(reverse_harmonic.scores, reverse_harmonic_replay.scores);
        assert_eq!(
            as_score_map(forward_harmonic.scores),
            as_score_map(reverse_harmonic.scores)
        );

        let forward_edge_betweenness = edge_betweenness_centrality(&forward);
        let forward_edge_betweenness_replay = edge_betweenness_centrality(&forward);
        let reverse_edge_betweenness = edge_betweenness_centrality(&reverse);
        let reverse_edge_betweenness_replay = edge_betweenness_centrality(&reverse);
        assert_eq!(
            forward_edge_betweenness.scores,
            forward_edge_betweenness_replay.scores
        );
        assert_eq!(
            reverse_edge_betweenness.scores,
            reverse_edge_betweenness_replay.scores
        );
        let as_edge_score_map =
            |scores: Vec<super::EdgeCentralityScore>| -> BTreeMap<(String, String), f64> {
                scores
                    .into_iter()
                    .map(|entry| ((entry.left, entry.right), entry.score))
                    .collect::<BTreeMap<(String, String), f64>>()
            };
        let forward_edge_map = as_edge_score_map(forward_edge_betweenness.scores);
        let reverse_edge_map = as_edge_score_map(reverse_edge_betweenness.scores);
        assert_eq!(
            forward_edge_map.keys().collect::<Vec<&(String, String)>>(),
            reverse_edge_map.keys().collect::<Vec<&(String, String)>>()
        );
        for key in forward_edge_map.keys() {
            let left = *forward_edge_map.get(key).unwrap_or(&0.0);
            let right = *reverse_edge_map.get(key).unwrap_or(&0.0);
            assert!((left - right).abs() <= 1e-12);
        }

        let forward_pagerank = pagerank(&forward);
        let forward_pagerank_replay = pagerank(&forward);
        let reverse_pagerank = pagerank(&reverse);
        let reverse_pagerank_replay = pagerank(&reverse);
        assert_eq!(forward_pagerank.scores, forward_pagerank_replay.scores);
        assert_eq!(reverse_pagerank.scores, reverse_pagerank_replay.scores);
        assert_eq!(
            as_score_map(forward_pagerank.scores),
            as_score_map(reverse_pagerank.scores)
        );

        let forward_eigenvector = eigenvector_centrality(&forward);
        let forward_eigenvector_replay = eigenvector_centrality(&forward);
        let reverse_eigenvector = eigenvector_centrality(&reverse);
        let reverse_eigenvector_replay = eigenvector_centrality(&reverse);
        assert_eq!(
            forward_eigenvector.scores,
            forward_eigenvector_replay.scores
        );
        assert_eq!(
            reverse_eigenvector.scores,
            reverse_eigenvector_replay.scores
        );
        assert_eq!(
            as_score_map(forward_eigenvector.scores),
            as_score_map(reverse_eigenvector.scores)
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
    fn harmonic_centrality_matches_expected_values_and_order() {
        let mut graph = Graph::strict();
        graph.add_edge("a", "b").expect("edge add should succeed");
        graph.add_edge("a", "c").expect("edge add should succeed");
        graph.add_edge("b", "d").expect("edge add should succeed");

        let result = harmonic_centrality(&graph);
        let expected = [
            ("a".to_owned(), 2.5_f64),
            ("b".to_owned(), 2.5_f64),
            ("c".to_owned(), 11.0_f64 / 6.0_f64),
            ("d".to_owned(), 11.0_f64 / 6.0_f64),
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
    fn harmonic_centrality_disconnected_graph_matches_networkx_behavior() {
        let mut graph = Graph::strict();
        graph.add_edge("a", "b").expect("edge add should succeed");
        let _ = graph.add_node("c");

        let result = harmonic_centrality(&graph);
        let expected = [("a", 1.0_f64), ("b", 1.0_f64), ("c", 0.0_f64)];
        for (actual, (exp_node, exp_score)) in result.scores.iter().zip(expected) {
            assert_eq!(actual.node, exp_node);
            assert!((actual.score - exp_score).abs() <= 1e-12);
        }
    }

    #[test]
    fn harmonic_centrality_singleton_and_empty_are_zero_or_empty() {
        let empty = Graph::strict();
        let empty_result = harmonic_centrality(&empty);
        assert!(empty_result.scores.is_empty());

        let mut singleton = Graph::strict();
        let _ = singleton.add_node("solo");
        let single_result = harmonic_centrality(&singleton);
        assert_eq!(single_result.scores.len(), 1);
        assert_eq!(single_result.scores[0].node, "solo");
        assert!((single_result.scores[0].score - 0.0).abs() <= 1e-12);
    }

    #[test]
    fn katz_centrality_cycle_graph_is_uniform() {
        let mut graph = Graph::strict();
        graph.add_edge("a", "b").expect("edge add should succeed");
        graph.add_edge("b", "c").expect("edge add should succeed");
        graph.add_edge("c", "d").expect("edge add should succeed");
        graph.add_edge("d", "a").expect("edge add should succeed");

        let result = katz_centrality(&graph);
        assert_eq!(result.scores.len(), 4);
        for score in result.scores {
            assert!((score.score - 0.5_f64).abs() <= 1e-12);
        }
        assert_eq!(result.witness.algorithm, "katz_centrality_power_iteration");
        assert_eq!(result.witness.complexity_claim, "O(k * (|V| + |E|))");
    }

    #[test]
    fn katz_centrality_star_graph_center_dominates_leaves() {
        let mut graph = Graph::strict();
        graph.add_edge("c", "l1").expect("edge add should succeed");
        graph.add_edge("c", "l2").expect("edge add should succeed");
        graph.add_edge("c", "l3").expect("edge add should succeed");
        graph.add_edge("c", "l4").expect("edge add should succeed");

        let result = katz_centrality(&graph);
        let center = result
            .scores
            .iter()
            .find(|entry| entry.node == "c")
            .expect("center node must exist")
            .score;
        let leaves = result
            .scores
            .iter()
            .filter(|entry| entry.node.starts_with('l'))
            .map(|entry| entry.score)
            .collect::<Vec<f64>>();
        assert_eq!(leaves.len(), 4);
        for leaf in &leaves {
            assert!(center > *leaf);
        }
        for pair in leaves.windows(2) {
            assert!((pair[0] - pair[1]).abs() <= 1e-12);
        }
    }

    #[test]
    fn katz_centrality_empty_and_singleton_are_empty_or_one() {
        let empty = Graph::strict();
        let empty_result = katz_centrality(&empty);
        assert!(empty_result.scores.is_empty());

        let mut singleton = Graph::strict();
        let _ = singleton.add_node("solo");
        let single_result = katz_centrality(&singleton);
        assert_eq!(single_result.scores.len(), 1);
        assert_eq!(single_result.scores[0].node, "solo");
        assert!((single_result.scores[0].score - 1.0).abs() <= 1e-12);
    }

    #[test]
    fn hits_centrality_cycle_graph_is_uniform() {
        let mut graph = Graph::strict();
        graph.add_edge("a", "b").expect("edge add should succeed");
        graph.add_edge("b", "c").expect("edge add should succeed");
        graph.add_edge("c", "d").expect("edge add should succeed");
        graph.add_edge("d", "a").expect("edge add should succeed");

        let result = hits_centrality(&graph);
        assert_eq!(result.hubs.len(), 4);
        assert_eq!(result.authorities.len(), 4);
        for score in result.hubs {
            assert!((score.score - 0.25_f64).abs() <= 1e-12);
        }
        for score in result.authorities {
            assert!((score.score - 0.25_f64).abs() <= 1e-12);
        }
        assert_eq!(result.witness.algorithm, "hits_centrality_power_iteration");
        assert_eq!(result.witness.complexity_claim, "O(k * (|V| + |E|))");
    }

    #[test]
    fn hits_centrality_path_graph_matches_expected_symmetry() {
        let mut graph = Graph::strict();
        graph.add_edge("a", "b").expect("edge add should succeed");
        graph.add_edge("b", "c").expect("edge add should succeed");
        graph.add_edge("c", "d").expect("edge add should succeed");

        let result = hits_centrality(&graph);
        assert_eq!(result.hubs.len(), 4);
        assert_eq!(result.authorities.len(), 4);

        let hubs = result
            .hubs
            .iter()
            .map(|entry| (entry.node.as_str(), entry.score))
            .collect::<BTreeMap<&str, f64>>();
        let authorities = result
            .authorities
            .iter()
            .map(|entry| (entry.node.as_str(), entry.score))
            .collect::<BTreeMap<&str, f64>>();
        assert!(
            (hubs.get("a").copied().unwrap_or_default()
                - hubs.get("d").copied().unwrap_or_default())
            .abs()
                <= 1e-12
        );
        assert!(
            (hubs.get("b").copied().unwrap_or_default()
                - hubs.get("c").copied().unwrap_or_default())
            .abs()
                <= 1e-12
        );
        assert!(
            hubs.get("b").copied().unwrap_or_default() > hubs.get("a").copied().unwrap_or_default()
        );
        assert!(
            (authorities.get("a").copied().unwrap_or_default()
                - authorities.get("d").copied().unwrap_or_default())
            .abs()
                <= 1e-12
        );
        assert!(
            (authorities.get("b").copied().unwrap_or_default()
                - authorities.get("c").copied().unwrap_or_default())
            .abs()
                <= 1e-12
        );
        assert!(
            authorities.get("b").copied().unwrap_or_default()
                > authorities.get("a").copied().unwrap_or_default()
        );
    }

    #[test]
    fn hits_centrality_path_graph_matches_legacy_networkx_oracle_values() {
        let mut graph = Graph::strict();
        graph.add_edge("a", "b").expect("edge add should succeed");
        graph.add_edge("b", "c").expect("edge add should succeed");
        graph.add_edge("c", "d").expect("edge add should succeed");

        let result = hits_centrality(&graph);

        let expected_hubs = [
            ("a", 0.190_983_005_664_778_4_f64),
            ("b", 0.309_016_994_335_221_6_f64),
            ("c", 0.309_016_994_335_221_6_f64),
            ("d", 0.190_983_005_664_778_4_f64),
        ];
        for (actual, (node, score)) in result.hubs.iter().zip(expected_hubs) {
            assert_eq!(actual.node, node);
            assert!((actual.score - score).abs() <= 1e-9);
        }

        let expected_authorities = [
            ("a", 0.190_983_005_521_049_f64),
            ("b", 0.309_016_994_478_951_f64),
            ("c", 0.309_016_994_478_951_f64),
            ("d", 0.190_983_005_521_049_f64),
        ];
        for (actual, (node, score)) in result.authorities.iter().zip(expected_authorities) {
            assert_eq!(actual.node, node);
            assert!((actual.score - score).abs() <= 1e-9);
        }
    }

    #[test]
    fn hits_centrality_disconnected_graph_matches_expected_behavior() {
        let mut graph = Graph::strict();
        graph.add_edge("a", "b").expect("edge add should succeed");
        let _ = graph.add_node("c");

        let result = hits_centrality(&graph);
        let hubs = result
            .hubs
            .iter()
            .map(|entry| (entry.node.as_str(), entry.score))
            .collect::<BTreeMap<&str, f64>>();
        let authorities = result
            .authorities
            .iter()
            .map(|entry| (entry.node.as_str(), entry.score))
            .collect::<BTreeMap<&str, f64>>();
        assert!((hubs.get("a").copied().unwrap_or_default() - 0.5).abs() <= 1e-12);
        assert!((hubs.get("b").copied().unwrap_or_default() - 0.5).abs() <= 1e-12);
        assert!((hubs.get("c").copied().unwrap_or_default() - 0.0).abs() <= 1e-12);
        assert!((authorities.get("a").copied().unwrap_or_default() - 0.5).abs() <= 1e-12);
        assert!((authorities.get("b").copied().unwrap_or_default() - 0.5).abs() <= 1e-12);
        assert!((authorities.get("c").copied().unwrap_or_default() - 0.0).abs() <= 1e-12);
    }

    #[test]
    fn hits_centrality_empty_and_singleton_are_empty_or_one() {
        let empty = Graph::strict();
        let empty_result = hits_centrality(&empty);
        assert!(empty_result.hubs.is_empty());
        assert!(empty_result.authorities.is_empty());

        let mut singleton = Graph::strict();
        let _ = singleton.add_node("solo");
        let result = hits_centrality(&singleton);
        assert_eq!(result.hubs.len(), 1);
        assert_eq!(result.authorities.len(), 1);
        assert_eq!(result.hubs[0].node, "solo");
        assert_eq!(result.authorities[0].node, "solo");
        assert!((result.hubs[0].score - 1.0).abs() <= 1e-12);
        assert!((result.authorities[0].score - 1.0).abs() <= 1e-12);
    }

    #[test]
    fn pagerank_cycle_graph_is_uniform() {
        let mut graph = Graph::strict();
        graph.add_edge("a", "b").expect("edge add should succeed");
        graph.add_edge("b", "c").expect("edge add should succeed");
        graph.add_edge("c", "d").expect("edge add should succeed");
        graph.add_edge("d", "a").expect("edge add should succeed");

        let result = pagerank(&graph);
        assert_eq!(result.scores.len(), 4);
        for score in result.scores {
            assert!((score.score - 0.25_f64).abs() <= 1e-12);
        }
        assert_eq!(result.witness.algorithm, "pagerank_power_iteration");
        assert_eq!(result.witness.complexity_claim, "O(k * (|V| + |E|))");
    }

    #[test]
    fn pagerank_star_graph_center_dominates_leaves() {
        let mut graph = Graph::strict();
        graph.add_edge("c", "l1").expect("edge add should succeed");
        graph.add_edge("c", "l2").expect("edge add should succeed");
        graph.add_edge("c", "l3").expect("edge add should succeed");
        graph.add_edge("c", "l4").expect("edge add should succeed");

        let result = pagerank(&graph);
        let center = result
            .scores
            .iter()
            .find(|entry| entry.node == "c")
            .expect("center node must exist")
            .score;
        let leaves = result
            .scores
            .iter()
            .filter(|entry| entry.node.starts_with('l'))
            .map(|entry| entry.score)
            .collect::<Vec<f64>>();
        assert_eq!(leaves.len(), 4);
        for leaf in &leaves {
            assert!(center > *leaf);
        }
        for pair in leaves.windows(2) {
            assert!((pair[0] - pair[1]).abs() <= 1e-12);
        }
    }

    #[test]
    fn pagerank_path_graph_matches_legacy_networkx_oracle_values() {
        let mut graph = Graph::strict();
        graph.add_edge("a", "b").expect("edge add should succeed");
        graph.add_edge("b", "c").expect("edge add should succeed");
        graph.add_edge("c", "d").expect("edge add should succeed");

        let result = pagerank(&graph);
        let expected = [
            ("a", 0.175_438_397_722_515_35_f64),
            ("b", 0.324_561_602_277_484_65_f64),
            ("c", 0.324_561_602_277_484_65_f64),
            ("d", 0.175_438_397_722_515_35_f64),
        ];
        for (actual, (node, score)) in result.scores.iter().zip(expected) {
            assert_eq!(actual.node, node);
            assert!((actual.score - score).abs() <= 1e-9);
        }
    }

    #[test]
    fn pagerank_empty_and_singleton_are_empty_or_one() {
        let empty = Graph::strict();
        let empty_result = pagerank(&empty);
        assert!(empty_result.scores.is_empty());

        let mut singleton = Graph::strict();
        let _ = singleton.add_node("solo");
        let singleton_result = pagerank(&singleton);
        assert_eq!(singleton_result.scores.len(), 1);
        assert_eq!(singleton_result.scores[0].node, "solo");
        assert!((singleton_result.scores[0].score - 1.0).abs() <= 1e-12);
    }

    #[test]
    fn eigenvector_centrality_cycle_graph_is_uniform() {
        let mut graph = Graph::strict();
        graph.add_edge("a", "b").expect("edge add should succeed");
        graph.add_edge("b", "c").expect("edge add should succeed");
        graph.add_edge("c", "d").expect("edge add should succeed");
        graph.add_edge("d", "a").expect("edge add should succeed");

        let result = eigenvector_centrality(&graph);
        assert_eq!(result.scores.len(), 4);
        for score in result.scores {
            assert!((score.score - 0.5_f64).abs() <= 1e-12);
        }
        assert_eq!(
            result.witness.algorithm,
            "eigenvector_centrality_power_iteration"
        );
        assert_eq!(result.witness.complexity_claim, "O(k * (|V| + |E|))");
    }

    #[test]
    fn eigenvector_centrality_star_graph_center_dominates_leaves() {
        let mut graph = Graph::strict();
        graph.add_edge("c", "l1").expect("edge add should succeed");
        graph.add_edge("c", "l2").expect("edge add should succeed");
        graph.add_edge("c", "l3").expect("edge add should succeed");
        graph.add_edge("c", "l4").expect("edge add should succeed");

        let result = eigenvector_centrality(&graph);
        let center = result
            .scores
            .iter()
            .find(|entry| entry.node == "c")
            .expect("center node must exist")
            .score;
        let leaves = result
            .scores
            .iter()
            .filter(|entry| entry.node.starts_with('l'))
            .map(|entry| entry.score)
            .collect::<Vec<f64>>();
        assert_eq!(leaves.len(), 4);
        for leaf in &leaves {
            assert!(center > *leaf);
        }
        for pair in leaves.windows(2) {
            assert!((pair[0] - pair[1]).abs() <= 1e-12);
        }
    }

    #[test]
    fn eigenvector_centrality_path_graph_matches_legacy_networkx_oracle_values() {
        let mut graph = Graph::strict();
        graph.add_edge("a", "b").expect("edge add should succeed");
        graph.add_edge("b", "c").expect("edge add should succeed");
        graph.add_edge("c", "d").expect("edge add should succeed");

        let result = eigenvector_centrality(&graph);
        let expected = [
            ("a", 0.371_748_234_271_200_85_f64),
            ("b", 0.601_500_831_517_500_3_f64),
            ("c", 0.601_500_831_517_500_4_f64),
            ("d", 0.371_748_234_271_200_8_f64),
        ];
        for (actual, (node, score)) in result.scores.iter().zip(expected) {
            assert_eq!(actual.node, node);
            assert!((actual.score - score).abs() <= 1e-9);
        }
    }

    #[test]
    fn eigenvector_centrality_empty_and_singleton_are_empty_or_one() {
        let empty = Graph::strict();
        let empty_result = eigenvector_centrality(&empty);
        assert!(empty_result.scores.is_empty());

        let mut singleton = Graph::strict();
        let _ = singleton.add_node("solo");
        let single_result = eigenvector_centrality(&singleton);
        assert_eq!(single_result.scores.len(), 1);
        assert_eq!(single_result.scores[0].node, "solo");
        assert!((single_result.scores[0].score - 1.0).abs() <= 1e-12);
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
    fn edge_betweenness_centrality_path_graph_matches_expected_values() {
        let mut graph = Graph::strict();
        graph.add_edge("a", "b").expect("edge add should succeed");
        graph.add_edge("b", "c").expect("edge add should succeed");
        graph.add_edge("c", "d").expect("edge add should succeed");

        let result = edge_betweenness_centrality(&graph);
        let as_edge_map = result
            .scores
            .iter()
            .map(|entry| ((entry.left.as_str(), entry.right.as_str()), entry.score))
            .collect::<BTreeMap<(&str, &str), f64>>();
        assert!((as_edge_map.get(&("a", "b")).copied().unwrap_or_default() - 0.5).abs() <= 1e-12);
        assert!(
            (as_edge_map.get(&("b", "c")).copied().unwrap_or_default() - (2.0 / 3.0)).abs()
                <= 1e-12
        );
        assert!((as_edge_map.get(&("c", "d")).copied().unwrap_or_default() - 0.5).abs() <= 1e-12);
        assert_eq!(
            result.witness.algorithm,
            "brandes_edge_betweenness_centrality"
        );
        assert_eq!(result.witness.complexity_claim, "O(|V| * |E|)");
    }

    #[test]
    fn edge_betweenness_centrality_cycle_graph_is_uniform() {
        let mut graph = Graph::strict();
        graph.add_edge("a", "b").expect("edge add should succeed");
        graph.add_edge("b", "c").expect("edge add should succeed");
        graph.add_edge("c", "d").expect("edge add should succeed");
        graph.add_edge("d", "a").expect("edge add should succeed");

        let result = edge_betweenness_centrality(&graph);
        for score in result.scores {
            assert!((score.score - (1.0 / 3.0)).abs() <= 1e-12);
        }
    }

    #[test]
    fn edge_betweenness_centrality_is_replay_stable_under_insertion_order_noise() {
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

        let forward_once = edge_betweenness_centrality(&forward);
        let forward_twice = edge_betweenness_centrality(&forward);
        let reverse_once = edge_betweenness_centrality(&reverse);
        let reverse_twice = edge_betweenness_centrality(&reverse);

        assert_eq!(forward_once, forward_twice);
        assert_eq!(reverse_once, reverse_twice);

        let as_edge_map =
            |edges: Vec<super::EdgeCentralityScore>| -> BTreeMap<(String, String), f64> {
                edges
                    .into_iter()
                    .map(|entry| ((entry.left, entry.right), entry.score))
                    .collect::<BTreeMap<(String, String), f64>>()
            };
        let forward_map = as_edge_map(forward_once.scores);
        let reverse_map = as_edge_map(reverse_once.scores);
        assert_eq!(
            forward_map.keys().collect::<Vec<&(String, String)>>(),
            reverse_map.keys().collect::<Vec<&(String, String)>>()
        );
        for key in forward_map.keys() {
            let left = *forward_map.get(key).unwrap_or(&0.0);
            let right = *reverse_map.get(key).unwrap_or(&0.0);
            assert!(
                (left - right).abs() <= 1e-12,
                "score mismatch for edge {:?}",
                key
            );
        }
    }

    #[test]
    fn edge_betweenness_centrality_empty_and_singleton_are_empty() {
        let empty = Graph::strict();
        let empty_result = edge_betweenness_centrality(&empty);
        assert!(empty_result.scores.is_empty());

        let mut singleton = Graph::strict();
        let _ = singleton.add_node("solo");
        let single_result = edge_betweenness_centrality(&singleton);
        assert!(single_result.scores.is_empty());
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

        let weighted_sources = multi_source_dijkstra(&graph, &["a", "d"], "weight");
        let bellman_ford = bellman_ford_shortest_paths(&graph, "a", "weight");
        assert!(!weighted_sources.distances.is_empty());
        assert!(!weighted_sources.predecessors.is_empty());
        assert!(!weighted_sources.negative_cycle_detected);
        assert!(!bellman_ford.distances.is_empty());
        assert!(!bellman_ford.predecessors.is_empty());
        assert!(!bellman_ford.negative_cycle_detected);
        assert_eq!(weighted_sources.witness.algorithm, "multi_source_dijkstra");
        assert_eq!(
            bellman_ford.witness.algorithm,
            "bellman_ford_shortest_paths"
        );

        let components = connected_components(&graph);
        assert_eq!(components.components.len(), 1);
        assert_eq!(
            number_connected_components(&graph).count,
            components.components.len()
        );

        let degree = degree_centrality(&graph);
        let closeness = closeness_centrality(&graph);
        let harmonic = harmonic_centrality(&graph);
        let katz = katz_centrality(&graph);
        let hits = hits_centrality(&graph);
        let edge_betweenness = edge_betweenness_centrality(&graph);
        let pagerank_result = pagerank(&graph);
        let eigenvector_result = eigenvector_centrality(&graph);
        let st_edge_cut = minimum_st_edge_cut_edmonds_karp(&graph, "a", "e", "capacity");
        let pair_edge_connectivity = edge_connectivity_edmonds_karp(&graph, "a", "e", "capacity");
        let global_edge_connectivity = global_edge_connectivity_edmonds_karp(&graph, "capacity");
        let global_min_edge_cut = global_minimum_edge_cut_edmonds_karp(&graph, "capacity");
        let articulation = articulation_points(&graph);
        let bridge_result = bridges(&graph);
        assert_eq!(degree.scores.len(), 5);
        assert_eq!(closeness.scores.len(), 5);
        assert_eq!(harmonic.scores.len(), 5);
        assert_eq!(katz.scores.len(), 5);
        assert_eq!(hits.hubs.len(), 5);
        assert_eq!(hits.authorities.len(), 5);
        assert_eq!(edge_betweenness.scores.len(), 5);
        assert_eq!(pagerank_result.scores.len(), 5);
        assert_eq!(eigenvector_result.scores.len(), 5);
        assert!((st_edge_cut.value - 1.0).abs() <= 1e-12);
        assert_eq!(
            st_edge_cut.cut_edges,
            vec![("d".to_owned(), "e".to_owned())]
        );
        assert!((pair_edge_connectivity.value - 1.0).abs() <= 1e-12);
        assert!((global_edge_connectivity.value - 1.0).abs() <= 1e-12);
        assert!(global_edge_connectivity.value <= pair_edge_connectivity.value);
        assert!((global_min_edge_cut.value - 1.0).abs() <= 1e-12);
        assert_eq!(global_min_edge_cut.source, "a");
        assert_eq!(global_min_edge_cut.sink, "e");
        assert_eq!(
            global_min_edge_cut.cut_edges,
            vec![("d".to_owned(), "e".to_owned())]
        );
        assert_eq!(articulation.nodes, vec!["d".to_owned()]);
        assert_eq!(bridge_result.edges, vec![("d".to_owned(), "e".to_owned())]);
        assert!(
            degree.scores.iter().all(|entry| entry.score >= 0.0),
            "degree centrality must remain non-negative"
        );
        assert!(
            closeness.scores.iter().all(|entry| entry.score >= 0.0),
            "closeness centrality must remain non-negative"
        );
        assert!(
            harmonic.scores.iter().all(|entry| entry.score >= 0.0),
            "harmonic centrality must remain non-negative"
        );
        assert!(
            katz.scores.iter().all(|entry| entry.score >= 0.0),
            "katz centrality must remain non-negative"
        );
        assert!(
            hits.hubs.iter().all(|entry| entry.score >= 0.0),
            "hits hubs must remain non-negative"
        );
        assert!(
            hits.authorities.iter().all(|entry| entry.score >= 0.0),
            "hits authorities must remain non-negative"
        );
        assert!(
            edge_betweenness
                .scores
                .iter()
                .all(|entry| entry.score >= 0.0),
            "edge betweenness centrality must remain non-negative"
        );
        assert!(
            pagerank_result
                .scores
                .iter()
                .all(|entry| entry.score >= 0.0),
            "pagerank must remain non-negative"
        );
        assert!(
            eigenvector_result
                .scores
                .iter()
                .all(|entry| entry.score >= 0.0),
            "eigenvector centrality must remain non-negative"
        );
        let pagerank_mass = pagerank_result
            .scores
            .iter()
            .map(|entry| entry.score)
            .sum::<f64>();
        let hits_hub_mass = hits.hubs.iter().map(|entry| entry.score).sum::<f64>();
        let hits_authority_mass = hits
            .authorities
            .iter()
            .map(|entry| entry.score)
            .sum::<f64>();
        assert!(
            (pagerank_mass - 1.0).abs() <= 1e-12,
            "pagerank distribution must sum to one"
        );
        assert!(
            (hits_hub_mass - 1.0).abs() <= 1e-12,
            "hits hub distribution must sum to one"
        );
        assert!(
            (hits_authority_mass - 1.0).abs() <= 1e-12,
            "hits authority distribution must sum to one"
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

            let multi_source_left = multi_source_dijkstra(&graph, &[&source], "weight");
            let multi_source_right = multi_source_dijkstra(&graph, &[&source], "weight");
            prop_assert_eq!(
                &multi_source_left, &multi_source_right,
                "P2C005-INV-1 multi-source dijkstra replay must be deterministic"
            );
            let multi_source_nodes = multi_source_left
                .distances
                .iter()
                .map(|entry| entry.node.clone())
                .collect::<Vec<String>>();
            let expected_multi_source_nodes = graph
                .nodes_ordered()
                .into_iter()
                .filter(|node| multi_source_nodes.iter().any(|candidate| candidate == node))
                .map(str::to_owned)
                .collect::<Vec<String>>();
            prop_assert_eq!(
                multi_source_nodes, expected_multi_source_nodes,
                "P2C005-DC-3 multi-source dijkstra order must match graph node order for reached nodes"
            );

            let bellman_left = bellman_ford_shortest_paths(&graph, &source, "weight");
            let bellman_right = bellman_ford_shortest_paths(&graph, &source, "weight");
            prop_assert_eq!(
                &bellman_left, &bellman_right,
                "P2C005-INV-1 bellman-ford replay must be deterministic"
            );
            let bellman_nodes = bellman_left
                .distances
                .iter()
                .map(|entry| entry.node.clone())
                .collect::<Vec<String>>();
            let expected_bellman_nodes = graph
                .nodes_ordered()
                .into_iter()
                .filter(|node| bellman_nodes.iter().any(|candidate| candidate == node))
                .map(str::to_owned)
                .collect::<Vec<String>>();
            prop_assert_eq!(
                bellman_nodes, expected_bellman_nodes,
                "P2C005-DC-3 bellman-ford order must match graph node order for reached nodes"
            );
            prop_assert!(
                !bellman_left.negative_cycle_detected,
                "P2C005-INV-1 generated unweighted graph should not trigger bellman-ford negative cycle"
            );

            let components = connected_components(&graph);
            let count = number_connected_components(&graph);
            prop_assert_eq!(
                components.components.len(), count.count,
                "P2C005-INV-3 connected component count must match partition cardinality"
            );

            let degree = degree_centrality(&graph);
            let closeness = closeness_centrality(&graph);
            let harmonic = harmonic_centrality(&graph);
            let katz = katz_centrality(&graph);
            let hits = hits_centrality(&graph);
            let edge_betweenness = edge_betweenness_centrality(&graph);
            let pagerank_result = pagerank(&graph);
            let eigenvector_result = eigenvector_centrality(&graph);
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
            let harmonic_order = harmonic
                .scores
                .iter()
                .map(|entry| entry.node.as_str())
                .collect::<Vec<&str>>();
            let katz_order = katz
                .scores
                .iter()
                .map(|entry| entry.node.as_str())
                .collect::<Vec<&str>>();
            let hits_hub_order = hits
                .hubs
                .iter()
                .map(|entry| entry.node.as_str())
                .collect::<Vec<&str>>();
            let hits_authority_order = hits
                .authorities
                .iter()
                .map(|entry| entry.node.as_str())
                .collect::<Vec<&str>>();
            let edge_betweenness_order = edge_betweenness
                .scores
                .iter()
                .map(|entry| (entry.left.clone(), entry.right.clone()))
                .collect::<Vec<(String, String)>>();
            let pagerank_order = pagerank_result
                .scores
                .iter()
                .map(|entry| entry.node.as_str())
                .collect::<Vec<&str>>();
            let eigenvector_order = eigenvector_result
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
                closeness_order, ordered_refs.clone(),
                "P2C005-DC-3 closeness centrality order must match graph node order"
            );
            prop_assert_eq!(
                harmonic_order, ordered_refs,
                "P2C005-DC-3 harmonic centrality order must match graph node order"
            );
            prop_assert_eq!(
                katz_order, graph.nodes_ordered(),
                "P2C005-DC-3 katz centrality order must match graph node order"
            );
            prop_assert_eq!(
                hits_hub_order, graph.nodes_ordered(),
                "P2C005-DC-3 hits hub order must match graph node order"
            );
            prop_assert_eq!(
                hits_authority_order, graph.nodes_ordered(),
                "P2C005-DC-3 hits authority order must match graph node order"
            );
            let canonical_edges = canonical_edge_pairs(&graph);
            prop_assert_eq!(
                edge_betweenness_order, canonical_edges,
                "P2C005-DC-3 edge betweenness order must match canonical edge order"
            );
            prop_assert_eq!(
                pagerank_order, graph.nodes_ordered(),
                "P2C005-DC-3 pagerank order must match graph node order"
            );
            prop_assert_eq!(
                eigenvector_order, graph.nodes_ordered(),
                "P2C005-DC-3 eigenvector centrality order must match graph node order"
            );

            let pair_connectivity_left =
                edge_connectivity_edmonds_karp(&graph, &source, &target, "capacity");
            let pair_connectivity_right =
                edge_connectivity_edmonds_karp(&graph, &source, &target, "capacity");
            prop_assert!(
                (pair_connectivity_left.value - pair_connectivity_right.value).abs() <= 1e-12,
                "P2C005-INV-1 pair edge connectivity must be replay-stable"
            );
            prop_assert_eq!(
                &pair_connectivity_left.witness, &pair_connectivity_right.witness,
                "P2C005-INV-1 pair edge connectivity witness must be replay-stable"
            );

            let global_connectivity_left =
                global_edge_connectivity_edmonds_karp(&graph, "capacity");
            let global_connectivity_right =
                global_edge_connectivity_edmonds_karp(&graph, "capacity");
            prop_assert!(
                (global_connectivity_left.value - global_connectivity_right.value).abs() <= 1e-12,
                "P2C005-INV-1 global edge connectivity must be replay-stable"
            );
            prop_assert_eq!(
                &global_connectivity_left.witness, &global_connectivity_right.witness,
                "P2C005-INV-1 global edge connectivity witness must be replay-stable"
            );
            prop_assert!(
                global_connectivity_left.value <= pair_connectivity_left.value + 1e-12,
                "P2C005-INV-1 global edge connectivity should not exceed pair connectivity"
            );

            let st_edge_cut_left = minimum_st_edge_cut_edmonds_karp(&graph, &source, &target, "capacity");
            let st_edge_cut_right = minimum_st_edge_cut_edmonds_karp(&graph, &source, &target, "capacity");
            prop_assert_eq!(
                &st_edge_cut_left.cut_edges, &st_edge_cut_right.cut_edges,
                "P2C005-INV-1 minimum s-t edge cut edges must be replay-stable"
            );
            prop_assert!(
                (st_edge_cut_left.value - st_edge_cut_right.value).abs() <= 1e-12,
                "P2C005-INV-1 minimum s-t edge cut value must be replay-stable"
            );
            let mut sorted_cut_edges = st_edge_cut_left.cut_edges.clone();
            sorted_cut_edges.sort();
            prop_assert_eq!(
                &st_edge_cut_left.cut_edges, &sorted_cut_edges,
                "P2C005-INV-1 minimum s-t edge cut edge order must be canonical"
            );

            let global_min_edge_cut_left = global_minimum_edge_cut_edmonds_karp(&graph, "capacity");
            let global_min_edge_cut_right = global_minimum_edge_cut_edmonds_karp(&graph, "capacity");
            prop_assert_eq!(
                &global_min_edge_cut_left, &global_min_edge_cut_right,
                "P2C005-INV-1 global minimum edge cut must be replay-stable"
            );
            prop_assert!(
                global_min_edge_cut_left.value <= st_edge_cut_left.value + 1e-12,
                "P2C005-INV-1 global minimum edge cut should not exceed selected s-t cut"
            );

            let articulation_left = articulation_points(&graph);
            let articulation_right = articulation_points(&graph);
            prop_assert_eq!(
                &articulation_left.nodes, &articulation_right.nodes,
                "P2C005-INV-1 articulation points must be replay-stable"
            );
            let mut sorted_articulation = articulation_left.nodes.clone();
            sorted_articulation.sort();
            prop_assert_eq!(
                &articulation_left.nodes, &sorted_articulation,
                "P2C005-INV-1 articulation point order must be canonical"
            );

            let bridges_left = bridges(&graph);
            let bridges_right = bridges(&graph);
            prop_assert_eq!(
                &bridges_left.edges, &bridges_right.edges,
                "P2C005-INV-1 bridges must be replay-stable"
            );
            let mut sorted_bridges = bridges_left.edges.clone();
            sorted_bridges.sort();
            prop_assert_eq!(
                &bridges_left.edges, &sorted_bridges,
                "P2C005-INV-1 bridge edge order must be canonical"
            );
            let canonical_edge_set = canonical_edge_pairs(&graph)
                .into_iter()
                .collect::<BTreeSet<(String, String)>>();
            for edge in &bridges_left.edges {
                prop_assert!(
                    canonical_edge_set.contains(edge),
                    "P2C005-INV-1 every bridge must exist in canonical graph edge set"
                );
            }

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

            let forward_multi_source = multi_source_dijkstra(&forward, &[&source], "weight");
            let forward_multi_source_replay = multi_source_dijkstra(&forward, &[&source], "weight");
            let reverse_multi_source = multi_source_dijkstra(&reverse, &[&source], "weight");
            let reverse_multi_source_replay = multi_source_dijkstra(&reverse, &[&source], "weight");
            prop_assert_eq!(
                &forward_multi_source, &forward_multi_source_replay,
                "P2C005-INV-2 multi-source dijkstra must be replay-stable for forward insertion"
            );
            prop_assert_eq!(
                &reverse_multi_source, &reverse_multi_source_replay,
                "P2C005-INV-2 multi-source dijkstra must be replay-stable for reverse insertion"
            );
            let as_distance_map = |distances: &[super::WeightedDistanceEntry]| -> BTreeMap<String, f64> {
                distances
                    .iter()
                    .map(|entry| (entry.node.clone(), entry.distance))
                    .collect::<BTreeMap<String, f64>>()
            };
            prop_assert_eq!(
                as_distance_map(&forward_multi_source.distances),
                as_distance_map(&reverse_multi_source.distances),
                "P2C005-INV-2 multi-source dijkstra distances must remain stable by node"
            );

            let forward_bellman_ford = bellman_ford_shortest_paths(&forward, &source, "weight");
            let forward_bellman_ford_replay = bellman_ford_shortest_paths(&forward, &source, "weight");
            let reverse_bellman_ford = bellman_ford_shortest_paths(&reverse, &source, "weight");
            let reverse_bellman_ford_replay = bellman_ford_shortest_paths(&reverse, &source, "weight");
            prop_assert_eq!(
                &forward_bellman_ford, &forward_bellman_ford_replay,
                "P2C005-INV-2 bellman-ford must be replay-stable for forward insertion"
            );
            prop_assert_eq!(
                &reverse_bellman_ford, &reverse_bellman_ford_replay,
                "P2C005-INV-2 bellman-ford must be replay-stable for reverse insertion"
            );
            prop_assert_eq!(
                as_distance_map(&forward_bellman_ford.distances),
                as_distance_map(&reverse_bellman_ford.distances),
                "P2C005-INV-2 bellman-ford distances must remain stable by node"
            );
            prop_assert!(
                !forward_bellman_ford.negative_cycle_detected && !reverse_bellman_ford.negative_cycle_detected,
                "P2C005-INV-2 generated unweighted graph should not trigger bellman-ford negative cycle"
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

            let forward_harmonic = harmonic_centrality(&forward);
            let forward_harmonic_replay = harmonic_centrality(&forward);
            let reverse_harmonic = harmonic_centrality(&reverse);
            let reverse_harmonic_replay = harmonic_centrality(&reverse);
            prop_assert_eq!(
                &forward_harmonic.scores, &forward_harmonic_replay.scores,
                "P2C005-INV-2 harmonic-centrality must be replay-stable for forward insertion"
            );
            prop_assert_eq!(
                &reverse_harmonic.scores, &reverse_harmonic_replay.scores,
                "P2C005-INV-2 harmonic-centrality must be replay-stable for reverse insertion"
            );
            prop_assert_eq!(
                as_score_map(&forward_harmonic.scores),
                as_score_map(&reverse_harmonic.scores),
                "P2C005-INV-2 harmonic-centrality scores must remain stable by node"
            );

            let forward_katz = katz_centrality(&forward);
            let forward_katz_replay = katz_centrality(&forward);
            let reverse_katz = katz_centrality(&reverse);
            let reverse_katz_replay = katz_centrality(&reverse);
            prop_assert_eq!(
                &forward_katz.scores, &forward_katz_replay.scores,
                "P2C005-INV-2 katz centrality must be replay-stable for forward insertion"
            );
            prop_assert_eq!(
                &reverse_katz.scores, &reverse_katz_replay.scores,
                "P2C005-INV-2 katz centrality must be replay-stable for reverse insertion"
            );
            prop_assert_eq!(
                as_score_map(&forward_katz.scores),
                as_score_map(&reverse_katz.scores),
                "P2C005-INV-2 katz centrality scores must remain stable by node"
            );

            let forward_hits = hits_centrality(&forward);
            let forward_hits_replay = hits_centrality(&forward);
            let reverse_hits = hits_centrality(&reverse);
            let reverse_hits_replay = hits_centrality(&reverse);
            prop_assert_eq!(
                &forward_hits.hubs, &forward_hits_replay.hubs,
                "P2C005-INV-2 hits hubs must be replay-stable for forward insertion"
            );
            prop_assert_eq!(
                &reverse_hits.hubs, &reverse_hits_replay.hubs,
                "P2C005-INV-2 hits hubs must be replay-stable for reverse insertion"
            );
            prop_assert_eq!(
                as_score_map(&forward_hits.hubs),
                as_score_map(&reverse_hits.hubs),
                "P2C005-INV-2 hits hub scores must remain stable by node"
            );
            prop_assert_eq!(
                &forward_hits.authorities, &forward_hits_replay.authorities,
                "P2C005-INV-2 hits authorities must be replay-stable for forward insertion"
            );
            prop_assert_eq!(
                &reverse_hits.authorities, &reverse_hits_replay.authorities,
                "P2C005-INV-2 hits authorities must be replay-stable for reverse insertion"
            );
            prop_assert_eq!(
                as_score_map(&forward_hits.authorities),
                as_score_map(&reverse_hits.authorities),
                "P2C005-INV-2 hits authority scores must remain stable by node"
            );

            let forward_edge_betweenness = edge_betweenness_centrality(&forward);
            let forward_edge_betweenness_replay = edge_betweenness_centrality(&forward);
            let reverse_edge_betweenness = edge_betweenness_centrality(&reverse);
            let reverse_edge_betweenness_replay = edge_betweenness_centrality(&reverse);
            prop_assert_eq!(
                &forward_edge_betweenness.scores, &forward_edge_betweenness_replay.scores,
                "P2C005-INV-2 edge betweenness must be replay-stable for forward insertion"
            );
            prop_assert_eq!(
                &reverse_edge_betweenness.scores, &reverse_edge_betweenness_replay.scores,
                "P2C005-INV-2 edge betweenness must be replay-stable for reverse insertion"
            );
            let as_edge_score_map =
                |scores: &[super::EdgeCentralityScore]| -> BTreeMap<(String, String), f64> {
                    scores
                        .iter()
                        .map(|entry| ((entry.left.clone(), entry.right.clone()), entry.score))
                        .collect::<BTreeMap<(String, String), f64>>()
                };
            let forward_edge_map = as_edge_score_map(&forward_edge_betweenness.scores);
            let reverse_edge_map = as_edge_score_map(&reverse_edge_betweenness.scores);
            prop_assert_eq!(
                forward_edge_map.keys().collect::<Vec<&(String, String)>>(),
                reverse_edge_map.keys().collect::<Vec<&(String, String)>>(),
                "P2C005-INV-2 edge betweenness edge set must remain stable"
            );
            for key in forward_edge_map.keys() {
                let left = *forward_edge_map.get(key).unwrap_or(&0.0);
                let right = *reverse_edge_map.get(key).unwrap_or(&0.0);
                prop_assert!(
                    (left - right).abs() <= 1e-12,
                    "P2C005-INV-2 edge betweenness scores must remain stable by edge"
                );
            }

            let forward_pagerank = pagerank(&forward);
            let forward_pagerank_replay = pagerank(&forward);
            let reverse_pagerank = pagerank(&reverse);
            let reverse_pagerank_replay = pagerank(&reverse);
            prop_assert_eq!(
                &forward_pagerank.scores, &forward_pagerank_replay.scores,
                "P2C005-INV-2 pagerank must be replay-stable for forward insertion"
            );
            prop_assert_eq!(
                &reverse_pagerank.scores, &reverse_pagerank_replay.scores,
                "P2C005-INV-2 pagerank must be replay-stable for reverse insertion"
            );
            prop_assert_eq!(
                as_score_map(&forward_pagerank.scores),
                as_score_map(&reverse_pagerank.scores),
                "P2C005-INV-2 pagerank scores must remain stable by node"
            );

            let forward_eigenvector = eigenvector_centrality(&forward);
            let forward_eigenvector_replay = eigenvector_centrality(&forward);
            let reverse_eigenvector = eigenvector_centrality(&reverse);
            let reverse_eigenvector_replay = eigenvector_centrality(&reverse);
            prop_assert_eq!(
                &forward_eigenvector.scores, &forward_eigenvector_replay.scores,
                "P2C005-INV-2 eigenvector centrality must be replay-stable for forward insertion"
            );
            prop_assert_eq!(
                &reverse_eigenvector.scores, &reverse_eigenvector_replay.scores,
                "P2C005-INV-2 eigenvector centrality must be replay-stable for reverse insertion"
            );
            prop_assert_eq!(
                as_score_map(&forward_eigenvector.scores),
                as_score_map(&reverse_eigenvector.scores),
                "P2C005-INV-2 eigenvector centrality scores must remain stable by node"
            );

            let forward_pair_connectivity =
                edge_connectivity_edmonds_karp(&forward, &source, &target, "capacity");
            let forward_pair_connectivity_replay =
                edge_connectivity_edmonds_karp(&forward, &source, &target, "capacity");
            let reverse_pair_connectivity =
                edge_connectivity_edmonds_karp(&reverse, &source, &target, "capacity");
            let reverse_pair_connectivity_replay =
                edge_connectivity_edmonds_karp(&reverse, &source, &target, "capacity");
            prop_assert!(
                (forward_pair_connectivity.value - forward_pair_connectivity_replay.value).abs()
                    <= 1e-12,
                "P2C005-INV-2 pair edge connectivity must be replay-stable for forward insertion"
            );
            prop_assert!(
                (reverse_pair_connectivity.value - reverse_pair_connectivity_replay.value).abs()
                    <= 1e-12,
                "P2C005-INV-2 pair edge connectivity must be replay-stable for reverse insertion"
            );
            prop_assert!(
                (forward_pair_connectivity.value - reverse_pair_connectivity.value).abs() <= 1e-12,
                "P2C005-INV-2 pair edge connectivity values must remain stable across insertion perturbation"
            );

            let forward_global_connectivity =
                global_edge_connectivity_edmonds_karp(&forward, "capacity");
            let forward_global_connectivity_replay =
                global_edge_connectivity_edmonds_karp(&forward, "capacity");
            let reverse_global_connectivity =
                global_edge_connectivity_edmonds_karp(&reverse, "capacity");
            let reverse_global_connectivity_replay =
                global_edge_connectivity_edmonds_karp(&reverse, "capacity");
            prop_assert!(
                (forward_global_connectivity.value - forward_global_connectivity_replay.value).abs()
                    <= 1e-12,
                "P2C005-INV-2 global edge connectivity must be replay-stable for forward insertion"
            );
            prop_assert!(
                (reverse_global_connectivity.value - reverse_global_connectivity_replay.value).abs()
                    <= 1e-12,
                "P2C005-INV-2 global edge connectivity must be replay-stable for reverse insertion"
            );
            prop_assert!(
                (forward_global_connectivity.value - reverse_global_connectivity.value).abs()
                    <= 1e-12,
                "P2C005-INV-2 global edge connectivity values must remain stable across insertion perturbation"
            );

            let forward_st_cut =
                minimum_st_edge_cut_edmonds_karp(&forward, &source, &target, "capacity");
            let forward_st_cut_replay =
                minimum_st_edge_cut_edmonds_karp(&forward, &source, &target, "capacity");
            let reverse_st_cut =
                minimum_st_edge_cut_edmonds_karp(&reverse, &source, &target, "capacity");
            let reverse_st_cut_replay =
                minimum_st_edge_cut_edmonds_karp(&reverse, &source, &target, "capacity");
            prop_assert_eq!(
                &forward_st_cut.cut_edges, &forward_st_cut_replay.cut_edges,
                "P2C005-INV-2 minimum s-t edge cut must be replay-stable for forward insertion"
            );
            prop_assert_eq!(
                &reverse_st_cut.cut_edges, &reverse_st_cut_replay.cut_edges,
                "P2C005-INV-2 minimum s-t edge cut must be replay-stable for reverse insertion"
            );
            prop_assert_eq!(
                &forward_st_cut.cut_edges, &reverse_st_cut.cut_edges,
                "P2C005-INV-2 minimum s-t edge cut edge sets must remain stable across insertion perturbation"
            );
            prop_assert!(
                (forward_st_cut.value - reverse_st_cut.value).abs() <= 1e-12,
                "P2C005-INV-2 minimum s-t edge cut values must remain stable across insertion perturbation"
            );

            let forward_global_min_cut = global_minimum_edge_cut_edmonds_karp(&forward, "capacity");
            let forward_global_min_cut_replay =
                global_minimum_edge_cut_edmonds_karp(&forward, "capacity");
            let reverse_global_min_cut = global_minimum_edge_cut_edmonds_karp(&reverse, "capacity");
            let reverse_global_min_cut_replay =
                global_minimum_edge_cut_edmonds_karp(&reverse, "capacity");
            prop_assert_eq!(
                &forward_global_min_cut, &forward_global_min_cut_replay,
                "P2C005-INV-2 global minimum edge cut must be replay-stable for forward insertion"
            );
            prop_assert_eq!(
                &reverse_global_min_cut, &reverse_global_min_cut_replay,
                "P2C005-INV-2 global minimum edge cut must be replay-stable for reverse insertion"
            );
            prop_assert!(
                (forward_global_min_cut.value - reverse_global_min_cut.value).abs() <= 1e-12,
                "P2C005-INV-2 global minimum edge cut value must remain stable across insertion perturbation"
            );
            prop_assert_eq!(
                &forward_global_min_cut.cut_edges, &reverse_global_min_cut.cut_edges,
                "P2C005-INV-2 global minimum edge cut edge set must remain stable across insertion perturbation"
            );
            prop_assert_eq!(
                forward_global_min_cut.source, reverse_global_min_cut.source,
                "P2C005-INV-2 global minimum edge cut source choice must remain stable across insertion perturbation"
            );
            prop_assert_eq!(
                forward_global_min_cut.sink, reverse_global_min_cut.sink,
                "P2C005-INV-2 global minimum edge cut sink choice must remain stable across insertion perturbation"
            );

            let forward_articulation = articulation_points(&forward);
            let forward_articulation_replay = articulation_points(&forward);
            let reverse_articulation = articulation_points(&reverse);
            let reverse_articulation_replay = articulation_points(&reverse);
            prop_assert_eq!(
                &forward_articulation.nodes, &forward_articulation_replay.nodes,
                "P2C005-INV-2 articulation points must be replay-stable for forward insertion"
            );
            prop_assert_eq!(
                &reverse_articulation.nodes, &reverse_articulation_replay.nodes,
                "P2C005-INV-2 articulation points must be replay-stable for reverse insertion"
            );
            prop_assert_eq!(
                &forward_articulation.nodes, &reverse_articulation.nodes,
                "P2C005-INV-2 articulation points must remain stable across insertion perturbation"
            );

            let forward_bridges = bridges(&forward);
            let forward_bridges_replay = bridges(&forward);
            let reverse_bridges = bridges(&reverse);
            let reverse_bridges_replay = bridges(&reverse);
            prop_assert_eq!(
                &forward_bridges.edges, &forward_bridges_replay.edges,
                "P2C005-INV-2 bridges must be replay-stable for forward insertion"
            );
            prop_assert_eq!(
                &reverse_bridges.edges, &reverse_bridges_replay.edges,
                "P2C005-INV-2 bridges must be replay-stable for reverse insertion"
            );
            prop_assert_eq!(
                &forward_bridges.edges, &reverse_bridges.edges,
                "P2C005-INV-2 bridges must remain stable across insertion perturbation"
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

    proptest! {
        #[test]
        fn clustering_coefficient_scores_are_between_zero_and_one(
            edge_count in 1usize..=8,
            seed in any::<u64>(),
        ) {
            use std::collections::hash_map::DefaultHasher;
            use std::hash::{Hash, Hasher};
            let mut graph = Graph::strict();
            let node_pool = ["a", "b", "c", "d", "e", "f", "g", "h"];
            let mut hasher = DefaultHasher::new();
            seed.hash(&mut hasher);
            let mut state = hasher.finish();
            for _ in 0..edge_count {
                let left_idx = (state % (node_pool.len() as u64)) as usize;
                state = state.wrapping_mul(6364136223846793005).wrapping_add(1442695040888963407);
                let right_idx = (state % (node_pool.len() as u64)) as usize;
                state = state.wrapping_mul(6364136223846793005).wrapping_add(1442695040888963407);
                if left_idx != right_idx {
                    let _ = graph.add_edge(node_pool[left_idx], node_pool[right_idx]);
                }
            }
            let result = clustering_coefficient(&graph);
            for score in &result.scores {
                prop_assert!(score.score >= 0.0 && score.score <= 1.0,
                    "clustering coefficient must be in [0, 1], got {} for node {}",
                    score.score, score.node);
            }
            prop_assert!(result.average_clustering >= 0.0 && result.average_clustering <= 1.0);
            prop_assert!(result.transitivity >= 0.0 && result.transitivity <= 1.0);
        }
    }

    // -----------------------------------------------------------------------
    // cycle_basis tests
    // -----------------------------------------------------------------------

    #[test]
    fn cycle_basis_empty_graph_has_no_cycles() {
        let graph = Graph::strict();
        let result = cycle_basis(&graph, None);
        assert!(result.cycles.is_empty());
    }

    #[test]
    fn cycle_basis_tree_has_no_cycles() {
        let mut graph = Graph::strict();
        graph.add_edge("a", "b").expect("edge add");
        graph.add_edge("b", "c").expect("edge add");
        graph.add_edge("c", "d").expect("edge add");
        let result = cycle_basis(&graph, None);
        assert!(result.cycles.is_empty());
    }

    #[test]
    fn cycle_basis_single_triangle() {
        let mut graph = Graph::strict();
        graph.add_edge("a", "b").expect("edge add");
        graph.add_edge("b", "c").expect("edge add");
        graph.add_edge("a", "c").expect("edge add");
        let result = cycle_basis(&graph, None);
        assert_eq!(
            result.cycles.len(),
            1,
            "triangle should have exactly one cycle in basis"
        );
    }

    #[test]
    fn cycle_basis_two_connected_triangles() {
        let mut graph = Graph::strict();
        graph.add_edge("a", "b").expect("edge add");
        graph.add_edge("b", "c").expect("edge add");
        graph.add_edge("a", "c").expect("edge add");
        graph.add_edge("c", "d").expect("edge add");
        graph.add_edge("d", "e").expect("edge add");
        graph.add_edge("c", "e").expect("edge add");
        let result = cycle_basis(&graph, None);
        assert_eq!(
            result.cycles.len(),
            2,
            "two triangles sharing vertex should have 2 cycles"
        );
    }

    #[test]
    fn cycle_basis_square_graph() {
        let mut graph = Graph::strict();
        graph.add_edge("a", "b").expect("edge add");
        graph.add_edge("b", "c").expect("edge add");
        graph.add_edge("c", "d").expect("edge add");
        graph.add_edge("d", "a").expect("edge add");
        let result = cycle_basis(&graph, None);
        assert_eq!(
            result.cycles.len(),
            1,
            "4-cycle should have exactly one cycle in basis"
        );
        assert_eq!(result.cycles[0].len(), 4);
    }

    #[test]
    fn cycle_basis_disconnected_components() {
        let mut graph = Graph::strict();
        graph.add_edge("a", "b").expect("edge add");
        graph.add_edge("b", "c").expect("edge add");
        graph.add_edge("a", "c").expect("edge add");
        graph.add_edge("x", "y").expect("edge add");
        graph.add_edge("y", "z").expect("edge add");
        graph.add_edge("x", "z").expect("edge add");
        let result = cycle_basis(&graph, None);
        assert_eq!(
            result.cycles.len(),
            2,
            "two disconnected triangles should have 2 cycles"
        );
    }

    // -----------------------------------------------------------------------
    // all_simple_paths tests
    // -----------------------------------------------------------------------

    #[test]
    fn all_simple_paths_missing_nodes_returns_empty() {
        let graph = Graph::strict();
        let result = all_simple_paths(&graph, "a", "b", None);
        assert!(result.paths.is_empty());
    }

    #[test]
    fn all_simple_paths_direct_edge() {
        let mut graph = Graph::strict();
        graph.add_edge("a", "b").expect("edge add");
        let result = all_simple_paths(&graph, "a", "b", None);
        assert_eq!(result.paths.len(), 1);
        assert_eq!(result.paths[0], vec!["a", "b"]);
    }

    #[test]
    fn all_simple_paths_triangle() {
        let mut graph = Graph::strict();
        graph.add_edge("a", "b").expect("edge add");
        graph.add_edge("b", "c").expect("edge add");
        graph.add_edge("a", "c").expect("edge add");
        let result = all_simple_paths(&graph, "a", "c", None);
        assert_eq!(
            result.paths.len(),
            2,
            "triangle should have 2 paths from a to c"
        );
        assert!(result.paths.contains(&vec!["a".to_owned(), "c".to_owned()]));
        assert!(
            result
                .paths
                .contains(&vec!["a".to_owned(), "b".to_owned(), "c".to_owned()])
        );
    }

    #[test]
    fn all_simple_paths_with_cutoff() {
        let mut graph = Graph::strict();
        graph.add_edge("a", "b").expect("edge add");
        graph.add_edge("b", "c").expect("edge add");
        graph.add_edge("a", "c").expect("edge add");
        let result = all_simple_paths(&graph, "a", "c", Some(1));
        assert_eq!(
            result.paths.len(),
            1,
            "cutoff=1 should only find direct path"
        );
        assert_eq!(result.paths[0], vec!["a", "c"]);
    }

    #[test]
    fn all_simple_paths_no_path() {
        let mut graph = Graph::strict();
        graph.add_edge("a", "b").expect("edge add");
        graph.add_node("c");
        let result = all_simple_paths(&graph, "a", "c", None);
        assert!(result.paths.is_empty());
    }

    // -----------------------------------------------------------------------
    // global_efficiency tests
    // -----------------------------------------------------------------------

    #[test]
    fn global_efficiency_empty_graph_is_zero() {
        let graph = Graph::strict();
        let result = global_efficiency(&graph);
        assert!((result.efficiency - 0.0).abs() < 1e-12);
    }

    #[test]
    fn global_efficiency_single_node_is_zero() {
        let mut graph = Graph::strict();
        graph.add_node("a");
        let result = global_efficiency(&graph);
        assert!((result.efficiency - 0.0).abs() < 1e-12);
    }

    #[test]
    fn global_efficiency_complete_k3() {
        let mut graph = Graph::strict();
        graph.add_edge("a", "b").expect("edge add");
        graph.add_edge("b", "c").expect("edge add");
        graph.add_edge("a", "c").expect("edge add");
        let result = global_efficiency(&graph);
        assert!(
            (result.efficiency - 1.0).abs() < 1e-12,
            "K3 should have global efficiency 1.0, got {}",
            result.efficiency
        );
    }

    #[test]
    fn global_efficiency_path_graph_p3() {
        let mut graph = Graph::strict();
        graph.add_edge("a", "b").expect("edge add");
        graph.add_edge("b", "c").expect("edge add");
        let result = global_efficiency(&graph);
        let expected = 5.0 / 6.0;
        assert!(
            (result.efficiency - expected).abs() < 1e-12,
            "P3 global efficiency should be {expected}, got {}",
            result.efficiency
        );
    }

    #[test]
    fn global_efficiency_disconnected_graph() {
        let mut graph = Graph::strict();
        graph.add_edge("a", "b").expect("edge add");
        graph.add_node("c");
        let result = global_efficiency(&graph);
        let expected = 1.0 / 3.0;
        assert!(
            (result.efficiency - expected).abs() < 1e-12,
            "disconnected graph global efficiency should be {expected}, got {}",
            result.efficiency
        );
    }

    // -----------------------------------------------------------------------
    // local_efficiency tests
    // -----------------------------------------------------------------------

    #[test]
    fn local_efficiency_empty_graph_is_zero() {
        let graph = Graph::strict();
        let result = local_efficiency(&graph);
        assert!((result.efficiency - 0.0).abs() < 1e-12);
    }

    #[test]
    fn local_efficiency_complete_k4() {
        let mut graph = Graph::strict();
        graph.add_edge("a", "b").expect("edge add");
        graph.add_edge("a", "c").expect("edge add");
        graph.add_edge("a", "d").expect("edge add");
        graph.add_edge("b", "c").expect("edge add");
        graph.add_edge("b", "d").expect("edge add");
        graph.add_edge("c", "d").expect("edge add");
        let result = local_efficiency(&graph);
        assert!(
            (result.efficiency - 1.0).abs() < 1e-12,
            "K4 should have local efficiency 1.0, got {}",
            result.efficiency
        );
    }

    // -----------------------------------------------------------------------
    // min_edge_cover tests
    // -----------------------------------------------------------------------

    #[test]
    fn min_edge_cover_empty_graph() {
        let graph = Graph::strict();
        let result = min_edge_cover(&graph);
        assert!(result.is_some());
        assert!(result.unwrap().edges.is_empty());
    }

    #[test]
    fn min_edge_cover_isolated_node_returns_none() {
        let mut graph = Graph::strict();
        graph.add_node("a");
        let result = min_edge_cover(&graph);
        assert!(result.is_none(), "isolated node means no edge cover exists");
    }

    #[test]
    fn min_edge_cover_single_edge() {
        let mut graph = Graph::strict();
        graph.add_edge("a", "b").expect("edge add");
        let result = min_edge_cover(&graph);
        assert!(result.is_some());
        let cover = result.unwrap();
        assert_eq!(cover.edges.len(), 1);
        assert_eq!(cover.edges[0], ("a".to_owned(), "b".to_owned()));
    }

    #[test]
    fn min_edge_cover_triangle() {
        let mut graph = Graph::strict();
        graph.add_edge("a", "b").expect("edge add");
        graph.add_edge("b", "c").expect("edge add");
        graph.add_edge("a", "c").expect("edge add");
        let result = min_edge_cover(&graph);
        assert!(result.is_some());
        let cover = result.unwrap();
        assert_eq!(cover.edges.len(), 2);
        let mut covered: HashSet<&str> = HashSet::new();
        for (l, r) in &cover.edges {
            covered.insert(l.as_str());
            covered.insert(r.as_str());
        }
        assert!(covered.contains("a"));
        assert!(covered.contains("b"));
        assert!(covered.contains("c"));
    }

    #[test]
    fn min_edge_cover_path_graph() {
        let mut graph = Graph::strict();
        graph.add_edge("a", "b").expect("edge add");
        graph.add_edge("b", "c").expect("edge add");
        graph.add_edge("c", "d").expect("edge add");
        let result = min_edge_cover(&graph);
        assert!(result.is_some());
        let cover = result.unwrap();
        assert_eq!(cover.edges.len(), 2);
    }

    // ── Euler algorithm tests ──

    #[test]
    fn is_eulerian_empty_graph() {
        let graph = Graph::strict();
        let result = is_eulerian(&graph);
        assert!(result.is_eulerian);
    }

    #[test]
    fn is_eulerian_single_node() {
        let mut graph = Graph::strict();
        graph.add_node("a");
        let result = is_eulerian(&graph);
        assert!(result.is_eulerian); // No edges, vacuously true
    }

    #[test]
    fn is_eulerian_triangle() {
        // Triangle: all degree 2 (even) → Eulerian circuit exists
        let mut graph = Graph::strict();
        graph.add_edge("a", "b").expect("edge add");
        graph.add_edge("b", "c").expect("edge add");
        graph.add_edge("a", "c").expect("edge add");
        let result = is_eulerian(&graph);
        assert!(result.is_eulerian);
    }

    #[test]
    fn is_eulerian_path_graph_not_eulerian() {
        // Path a-b-c: degrees 1,2,1 → not Eulerian
        let mut graph = Graph::strict();
        graph.add_edge("a", "b").expect("edge add");
        graph.add_edge("b", "c").expect("edge add");
        let result = is_eulerian(&graph);
        assert!(!result.is_eulerian);
    }

    #[test]
    fn is_eulerian_square_with_diagonals() {
        // K4 minus one edge: a-b, b-c, c-d, d-a, a-c
        // Degrees: a=3, b=2, c=3, d=2 → odd degrees exist, not Eulerian
        let mut graph = Graph::strict();
        graph.add_edge("a", "b").expect("edge add");
        graph.add_edge("b", "c").expect("edge add");
        graph.add_edge("c", "d").expect("edge add");
        graph.add_edge("d", "a").expect("edge add");
        graph.add_edge("a", "c").expect("edge add");
        let result = is_eulerian(&graph);
        assert!(!result.is_eulerian);
    }

    #[test]
    fn is_eulerian_rectangle() {
        // Square: a-b-c-d-a → all degree 2 → Eulerian
        let mut graph = Graph::strict();
        graph.add_edge("a", "b").expect("edge add");
        graph.add_edge("b", "c").expect("edge add");
        graph.add_edge("c", "d").expect("edge add");
        graph.add_edge("d", "a").expect("edge add");
        let result = is_eulerian(&graph);
        assert!(result.is_eulerian);
    }

    #[test]
    fn is_eulerian_disconnected() {
        // Two separate triangles: all even degrees but not connected → not Eulerian
        let mut graph = Graph::strict();
        graph.add_edge("a", "b").expect("edge add");
        graph.add_edge("b", "c").expect("edge add");
        graph.add_edge("a", "c").expect("edge add");
        graph.add_edge("x", "y").expect("edge add");
        graph.add_edge("y", "z").expect("edge add");
        graph.add_edge("x", "z").expect("edge add");
        let result = is_eulerian(&graph);
        assert!(!result.is_eulerian);
    }

    #[test]
    fn has_eulerian_path_triangle() {
        // Triangle: all even degrees → Eulerian circuit → also has Eulerian path
        let mut graph = Graph::strict();
        graph.add_edge("a", "b").expect("edge add");
        graph.add_edge("b", "c").expect("edge add");
        graph.add_edge("a", "c").expect("edge add");
        let result = has_eulerian_path(&graph);
        assert!(result.has_eulerian_path);
    }

    #[test]
    fn has_eulerian_path_simple_path() {
        // Path a-b-c: degrees 1,2,1 → exactly 2 odd → has Eulerian path
        let mut graph = Graph::strict();
        graph.add_edge("a", "b").expect("edge add");
        graph.add_edge("b", "c").expect("edge add");
        let result = has_eulerian_path(&graph);
        assert!(result.has_eulerian_path);
    }

    #[test]
    fn has_eulerian_path_k4() {
        // K4: all degree 3 (odd) → 4 odd-degree nodes → no Eulerian path
        let mut graph = Graph::strict();
        graph.add_edge("a", "b").expect("edge add");
        graph.add_edge("a", "c").expect("edge add");
        graph.add_edge("a", "d").expect("edge add");
        graph.add_edge("b", "c").expect("edge add");
        graph.add_edge("b", "d").expect("edge add");
        graph.add_edge("c", "d").expect("edge add");
        let result = has_eulerian_path(&graph);
        assert!(!result.has_eulerian_path);
    }

    #[test]
    fn is_semieulerian_path_graph() {
        // Path a-b-c: has Eulerian path but not circuit → semi-Eulerian
        let mut graph = Graph::strict();
        graph.add_edge("a", "b").expect("edge add");
        graph.add_edge("b", "c").expect("edge add");
        let result = is_semieulerian(&graph);
        assert!(result.is_semieulerian);
    }

    #[test]
    fn is_semieulerian_triangle() {
        // Triangle: has Eulerian circuit → NOT semi-Eulerian
        let mut graph = Graph::strict();
        graph.add_edge("a", "b").expect("edge add");
        graph.add_edge("b", "c").expect("edge add");
        graph.add_edge("a", "c").expect("edge add");
        let result = is_semieulerian(&graph);
        assert!(!result.is_semieulerian);
    }

    #[test]
    fn eulerian_circuit_triangle() {
        let mut graph = Graph::strict();
        graph.add_edge("a", "b").expect("edge add");
        graph.add_edge("b", "c").expect("edge add");
        graph.add_edge("a", "c").expect("edge add");
        let result = eulerian_circuit(&graph, None);
        assert!(result.is_some());
        let circuit = result.unwrap();
        assert_eq!(circuit.edges.len(), 3);
        // Circuit should start and end at same node
        assert_eq!(circuit.edges[0].0, circuit.edges[2].1);
        // Every edge is used exactly once
        let mut edge_set: HashSet<(String, String)> = HashSet::new();
        for (u, v) in &circuit.edges {
            let key = if u <= v {
                (u.clone(), v.clone())
            } else {
                (v.clone(), u.clone())
            };
            assert!(edge_set.insert(key), "duplicate edge in circuit");
        }
        assert_eq!(edge_set.len(), 3);
    }

    #[test]
    fn eulerian_circuit_rectangle() {
        let mut graph = Graph::strict();
        graph.add_edge("a", "b").expect("edge add");
        graph.add_edge("b", "c").expect("edge add");
        graph.add_edge("c", "d").expect("edge add");
        graph.add_edge("d", "a").expect("edge add");
        let result = eulerian_circuit(&graph, None);
        assert!(result.is_some());
        let circuit = result.unwrap();
        assert_eq!(circuit.edges.len(), 4);
        assert_eq!(circuit.edges[0].0, circuit.edges[3].1);
    }

    #[test]
    fn eulerian_circuit_not_eulerian() {
        // Path graph: no Eulerian circuit
        let mut graph = Graph::strict();
        graph.add_edge("a", "b").expect("edge add");
        graph.add_edge("b", "c").expect("edge add");
        let result = eulerian_circuit(&graph, None);
        assert!(result.is_none());
    }

    #[test]
    fn eulerian_circuit_with_source() {
        let mut graph = Graph::strict();
        graph.add_edge("a", "b").expect("edge add");
        graph.add_edge("b", "c").expect("edge add");
        graph.add_edge("a", "c").expect("edge add");
        let result = eulerian_circuit(&graph, Some("c"));
        assert!(result.is_some());
        let circuit = result.unwrap();
        assert_eq!(circuit.edges[0].0, "c");
        assert_eq!(circuit.edges[2].1, "c");
    }

    #[test]
    fn eulerian_circuit_empty_graph() {
        let graph = Graph::strict();
        let result = eulerian_circuit(&graph, None);
        assert!(result.is_some());
        assert!(result.unwrap().edges.is_empty());
    }

    #[test]
    fn eulerian_path_simple() {
        // Path a-b-c: exactly 2 odd-degree nodes → Eulerian path exists
        let mut graph = Graph::strict();
        graph.add_edge("a", "b").expect("edge add");
        graph.add_edge("b", "c").expect("edge add");
        let result = eulerian_path(&graph, None);
        assert!(result.is_some());
        let path = result.unwrap();
        assert_eq!(path.edges.len(), 2);
        // Path should start at "a" (smallest odd-degree node)
        assert_eq!(path.edges[0].0, "a");
        // Each edge is consecutive
        assert_eq!(path.edges[0].1, path.edges[1].0);
    }

    #[test]
    fn eulerian_path_house_graph() {
        // House graph: square + triangle on top
        // a-b, b-c, c-d, d-a, c-e, d-e
        // Degrees: a=2, b=2, c=3, d=3, e=2 → 2 odd nodes (c,d)
        let mut graph = Graph::strict();
        graph.add_edge("a", "b").expect("edge add");
        graph.add_edge("b", "c").expect("edge add");
        graph.add_edge("c", "d").expect("edge add");
        graph.add_edge("d", "a").expect("edge add");
        graph.add_edge("c", "e").expect("edge add");
        graph.add_edge("d", "e").expect("edge add");
        let result = eulerian_path(&graph, None);
        assert!(result.is_some());
        let path = result.unwrap();
        assert_eq!(path.edges.len(), 6);
        // Should start at "c" (smallest odd-degree node)
        assert_eq!(path.edges[0].0, "c");
        // Every edge used exactly once
        let mut edge_set: HashSet<(String, String)> = HashSet::new();
        for (u, v) in &path.edges {
            let key = if u <= v {
                (u.clone(), v.clone())
            } else {
                (v.clone(), u.clone())
            };
            assert!(edge_set.insert(key), "duplicate edge in path");
        }
        assert_eq!(edge_set.len(), 6);
    }

    #[test]
    fn eulerian_path_no_path() {
        // K4: 4 odd-degree nodes → no Eulerian path
        let mut graph = Graph::strict();
        graph.add_edge("a", "b").expect("edge add");
        graph.add_edge("a", "c").expect("edge add");
        graph.add_edge("a", "d").expect("edge add");
        graph.add_edge("b", "c").expect("edge add");
        graph.add_edge("b", "d").expect("edge add");
        graph.add_edge("c", "d").expect("edge add");
        let result = eulerian_path(&graph, None);
        assert!(result.is_none());
    }

    #[test]
    fn eulerian_path_with_source() {
        let mut graph = Graph::strict();
        graph.add_edge("a", "b").expect("edge add");
        graph.add_edge("b", "c").expect("edge add");
        let result = eulerian_path(&graph, Some("c"));
        assert!(result.is_some());
        let path = result.unwrap();
        assert_eq!(path.edges[0].0, "c");
    }

    #[test]
    fn eulerian_path_circuit_case() {
        // Triangle: all even → eulerian_path still works (returns circuit as path)
        let mut graph = Graph::strict();
        graph.add_edge("a", "b").expect("edge add");
        graph.add_edge("b", "c").expect("edge add");
        graph.add_edge("a", "c").expect("edge add");
        let result = eulerian_path(&graph, None);
        assert!(result.is_some());
        let path = result.unwrap();
        assert_eq!(path.edges.len(), 3);
    }

    #[test]
    fn eulerian_circuit_butterfly() {
        // Butterfly / bowtie: two triangles sharing a vertex
        // a-b, b-c, a-c, c-d, c-e, d-e
        // Degrees: a=2, b=2, c=4, d=2, e=2 → all even → Eulerian
        let mut graph = Graph::strict();
        graph.add_edge("a", "b").expect("edge add");
        graph.add_edge("a", "c").expect("edge add");
        graph.add_edge("b", "c").expect("edge add");
        graph.add_edge("c", "d").expect("edge add");
        graph.add_edge("c", "e").expect("edge add");
        graph.add_edge("d", "e").expect("edge add");
        let result = eulerian_circuit(&graph, None);
        assert!(result.is_some());
        let circuit = result.unwrap();
        assert_eq!(circuit.edges.len(), 6);
        assert_eq!(circuit.edges[0].0, circuit.edges[5].1);
        // Verify all edges used exactly once
        let mut edge_set: HashSet<(String, String)> = HashSet::new();
        for (u, v) in &circuit.edges {
            let key = if u <= v {
                (u.clone(), v.clone())
            } else {
                (v.clone(), u.clone())
            };
            assert!(edge_set.insert(key), "duplicate edge in circuit");
        }
        assert_eq!(edge_set.len(), 6);
    }

    #[test]
    fn is_eulerian_with_isolated_node() {
        // Triangle + isolated node: isolated nodes are ignored for connectivity
        let mut graph = Graph::strict();
        graph.add_edge("a", "b").expect("edge add");
        graph.add_edge("b", "c").expect("edge add");
        graph.add_edge("a", "c").expect("edge add");
        graph.add_node("z");
        let result = is_eulerian(&graph);
        assert!(result.is_eulerian);
    }
}
