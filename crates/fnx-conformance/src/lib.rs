#![forbid(unsafe_code)]

use fnx_algorithms::{
    AllSimplePathsResult, AverageNeighborDegreeResult, AverageShortestPathLengthResult,
    BipartiteSetsResult, CentralityScore, ComplexityWitness, CoreNumberResult, CycleBasisResult,
    DegreeAssortativityResult, DensityResult, DistanceMeasuresResult, EdgeCentralityScore,
    EdgeCutResult, GlobalEdgeCutResult, GlobalEfficiencyResult, GreedyColorResult, HasPathResult,
    IsBipartiteResult, IsConnectedResult, IsForestResult, IsTreeResult, LocalEfficiencyResult,
    MaximalMatchingResult, MinEdgeCoverResult, MinimumCutResult, MinimumSpanningTreeResult,
    ShortestPathLengthResult, SquareClusteringResult, TrianglesResult, VoterankResult,
    WeightedMatchingResult, WeightedShortestPathsResult, all_simple_paths, articulation_points,
    average_neighbor_degree, average_shortest_path_length, bellman_ford_shortest_paths,
    betweenness_centrality, bipartite_sets, bridges, closeness_centrality, clustering_coefficient,
    connected_components, core_number, cycle_basis, degree_assortativity_coefficient,
    degree_centrality, density, distance_measures, edge_betweenness_centrality,
    edge_connectivity_edmonds_karp, eigenvector_centrality, global_edge_connectivity_edmonds_karp,
    global_efficiency, global_minimum_edge_cut_edmonds_karp, greedy_color, harmonic_centrality,
    has_path, hits_centrality, is_bipartite, is_connected, is_forest, is_tree, k_core, k_corona,
    k_crust, k_shell, katz_centrality, local_efficiency, max_flow_edmonds_karp,
    max_weight_matching, maximal_matching, min_edge_cover, min_weight_matching,
    minimum_cut_edmonds_karp, minimum_spanning_tree, minimum_st_edge_cut_edmonds_karp,
    multi_source_dijkstra, number_connected_components, pagerank, shortest_path_length,
    shortest_path_unweighted, shortest_path_weighted, square_clustering, triangles, voterank,
};
// find_cliques, node_connectivity, minimum_node_cut, global_node_connectivity,
// global_minimum_node_cut used via fnx_algorithms:: prefix
use fnx_classes::{AttrMap, EdgeSnapshot, Graph, GraphSnapshot};
use fnx_convert::{AdjacencyPayload, EdgeListPayload, GraphConverter};
use fnx_dispatch::{BackendRegistry, BackendSpec, DispatchDecision, DispatchRequest};
use fnx_generators::GraphGenerator;
use fnx_readwrite::EdgeListEngine;
use fnx_runtime::{
    CompatibilityMode, DecisionAction, FailureReproData, ForensicsBundleIndex, StructuredTestLog,
    TestKind, TestStatus, canonical_environment_fingerprint, structured_test_log_schema_version,
    unix_time_ms,
};
use fnx_views::GraphView;
use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, BTreeSet};
use std::fs;
use std::io;
use std::path::{Path, PathBuf};
use std::time::Instant;

#[derive(Debug, Clone)]
pub struct HarnessConfig {
    pub oracle_root: PathBuf,
    pub fixture_root: PathBuf,
    pub mode: CompatibilityMode,
    pub report_root: Option<PathBuf>,
    pub fixture_filter: Option<String>,
    pub log_schema_version: String,
}

impl HarnessConfig {
    #[must_use]
    pub fn default_paths() -> Self {
        let repo_root = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../..");
        Self {
            oracle_root: repo_root.join("legacy_networkx_code/networkx"),
            fixture_root: PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("fixtures"),
            mode: CompatibilityMode::Strict,
            report_root: Some(repo_root.join("artifacts/conformance/latest")),
            fixture_filter: None,
            log_schema_version: structured_test_log_schema_version().to_owned(),
        }
    }
}

impl Default for HarnessConfig {
    fn default() -> Self {
        Self::default_paths()
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Mismatch {
    pub category: String,
    pub message: String,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum MismatchClassification {
    StrictViolation,
    HardenedAllowlisted,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct TaxonomyMismatch {
    pub category: String,
    pub message: String,
    pub classification: MismatchClassification,
    pub allowlisted_in_hardened: bool,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct FixtureReport {
    pub fixture_id: String,
    pub fixture_name: String,
    pub suite: String,
    pub mode: CompatibilityMode,
    pub seed: Option<u64>,
    pub threat_class: Option<String>,
    pub replay_command: String,
    pub passed: bool,
    pub reason_code: Option<String>,
    pub fixture_source_hash: String,
    pub duration_ms: u128,
    pub strict_violation_count: usize,
    pub hardened_allowlisted_count: usize,
    pub mismatches: Vec<Mismatch>,
    pub mismatch_taxonomy: Vec<TaxonomyMismatch>,
    pub witness: Option<ComplexityWitness>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct HarnessReport {
    pub suite: &'static str,
    pub oracle_present: bool,
    pub fixture_count: usize,
    pub mode: CompatibilityMode,
    pub mismatch_count: usize,
    pub hardened_allowlisted_count: usize,
    pub structured_log_count: usize,
    pub structured_log_path: Option<String>,
    pub fixture_reports: Vec<FixtureReport>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct DriftTaxonomyFixtureRow {
    pub fixture_id: String,
    pub fixture_name: String,
    pub packet_id: String,
    pub mode: CompatibilityMode,
    pub seed: Option<u64>,
    pub threat_class: Option<String>,
    pub replay_command: String,
    pub strict_violation_count: usize,
    pub hardened_allowlisted_count: usize,
    pub mismatches: Vec<TaxonomyMismatch>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct DriftTaxonomyReport {
    pub schema_version: String,
    pub generated_at_unix_ms: u128,
    pub run_id: String,
    pub strict_violation_count: usize,
    pub hardened_allowlisted_count: usize,
    pub fixtures: Vec<DriftTaxonomyFixtureRow>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct FailureArtifactEnvelope {
    pub schema_version: String,
    pub generated_at_unix_ms: u128,
    pub fixture_id: String,
    pub fixture_name: String,
    pub packet_id: String,
    pub mode: CompatibilityMode,
    pub seed: Option<u64>,
    pub threat_class: Option<String>,
    pub replay_command: String,
    pub strict_violation_count: usize,
    pub hardened_allowlisted_count: usize,
    pub reason_code: Option<String>,
    pub mismatches: Vec<TaxonomyMismatch>,
    pub artifact_refs: Vec<String>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct EmitterNormalizationReport {
    pub schema_version: String,
    pub generated_at_unix_ms: u128,
    pub crate_name: String,
    pub run_id: String,
    pub suite: String,
    pub fixture_count: usize,
    pub valid_log_count: usize,
    pub normalized_fields: Vec<String>,
    pub findings: Vec<String>,
    pub output_artifacts: Vec<String>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct DependentUnblockRow {
    pub blocked_bead_id: String,
    pub required_artifacts: Vec<String>,
    pub required_fields: Vec<String>,
    pub evidence_paths: Vec<String>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct DependentUnblockMatrix {
    pub schema_version: String,
    pub generated_at_unix_ms: u128,
    pub source_bead_id: String,
    pub run_id: String,
    pub rows: Vec<DependentUnblockRow>,
}

#[derive(Debug, Deserialize)]
struct ConformanceFixture {
    suite: String,
    #[serde(default)]
    mode: Option<ModeValue>,
    #[serde(default)]
    fixture_id: Option<String>,
    #[serde(default)]
    seed: Option<u64>,
    #[serde(default)]
    threat_class: Option<String>,
    #[serde(default)]
    hardened_allowlisted_categories: Vec<String>,
    #[serde(default)]
    replay_command: Option<String>,
    operations: Vec<Operation>,
    expected: ExpectedState,
}

#[derive(Debug, Clone, Copy, Deserialize)]
#[serde(rename_all = "snake_case")]
enum ModeValue {
    Strict,
    Hardened,
}

impl ModeValue {
    fn as_mode(self) -> CompatibilityMode {
        match self {
            Self::Strict => CompatibilityMode::Strict,
            Self::Hardened => CompatibilityMode::Hardened,
        }
    }
}

fn default_weight_attr() -> String {
    "weight".to_owned()
}

fn default_capacity_attr() -> String {
    "capacity".to_owned()
}

#[derive(Debug, Deserialize)]
#[serde(tag = "op", rename_all = "snake_case")]
enum Operation {
    AddNode {
        node: String,
        #[serde(default)]
        attrs: AttrMap,
    },
    AddEdge {
        left: String,
        right: String,
        #[serde(default)]
        attrs: AttrMap,
    },
    RemoveNode {
        node: String,
    },
    RemoveEdge {
        left: String,
        right: String,
    },
    ShortestPathQuery {
        source: String,
        target: String,
    },
    WeightedShortestPathQuery {
        source: String,
        target: String,
        #[serde(default = "default_weight_attr")]
        weight_attr: String,
    },
    MaxFlowQuery {
        source: String,
        target: String,
        #[serde(default = "default_capacity_attr")]
        capacity_attr: String,
    },
    MinimumCutQuery {
        source: String,
        target: String,
        #[serde(default = "default_capacity_attr")]
        capacity_attr: String,
    },
    MinimumStEdgeCutQuery {
        source: String,
        target: String,
        #[serde(default = "default_capacity_attr")]
        capacity_attr: String,
    },
    EdgeConnectivityQuery {
        source: String,
        target: String,
        #[serde(default = "default_capacity_attr")]
        capacity_attr: String,
    },
    GlobalEdgeConnectivityQuery {
        #[serde(default = "default_capacity_attr")]
        capacity_attr: String,
    },
    GlobalMinimumEdgeCutQuery {
        #[serde(default = "default_capacity_attr")]
        capacity_attr: String,
    },
    BetweennessCentralityQuery,
    EdgeBetweennessCentralityQuery,
    DegreeCentralityQuery,
    ClosenessCentralityQuery,
    HarmonicCentralityQuery,
    KatzCentralityQuery,
    HitsCentralityQuery,
    PagerankQuery,
    EigenvectorCentralityQuery,
    ClusteringCoefficientQuery,
    DistanceMeasuresQuery,
    AverageShortestPathLengthQuery,
    IsConnectedQuery,
    DensityQuery,
    HasPathQuery {
        source: String,
        target: String,
    },
    ShortestPathLengthQuery {
        source: String,
        target: String,
    },
    ConnectedComponentsQuery,
    NumberConnectedComponentsQuery,
    ArticulationPointsQuery,
    BridgesQuery,
    BellmanFordQuery {
        source: String,
        #[serde(default = "default_weight_attr")]
        weight_attr: String,
    },
    MultiSourceDijkstraQuery {
        sources: Vec<String>,
        #[serde(default = "default_weight_attr")]
        weight_attr: String,
    },
    MaximalMatchingQuery,
    MaxWeightMatchingQuery {
        #[serde(default)]
        maxcardinality: bool,
        #[serde(default = "default_weight_attr")]
        weight_attr: String,
    },
    MinWeightMatchingQuery {
        #[serde(default = "default_weight_attr")]
        weight_attr: String,
    },
    MinimumSpanningTreeQuery {
        #[serde(default = "default_weight_attr")]
        weight_attr: String,
    },
    TrianglesQuery,
    SquareClusteringQuery,
    IsTreeQuery,
    IsForestQuery,
    GreedyColorQuery,
    IsBipartiteQuery,
    BipartiteSetsQuery,
    CoreNumberQuery,
    KCoreQuery {
        k: Option<usize>,
    },
    KShellQuery {
        k: Option<usize>,
    },
    KCrustQuery {
        k: Option<usize>,
    },
    KCoronaQuery {
        k: usize,
    },
    AverageNeighborDegreeQuery,
    DegreeAssortativityQuery,
    VoterankQuery,
    FindCliquesQuery,
    NodeConnectivityQuery {
        source: String,
        target: String,
    },
    MinimumNodeCutQuery {
        source: String,
        target: String,
    },
    GlobalNodeConnectivityQuery,
    GlobalMinimumNodeCutQuery,
    CycleBasisQuery,
    AllSimplePathsQuery {
        source: String,
        target: String,
    },
    GlobalEfficiencyQuery,
    LocalEfficiencyQuery,
    MinEdgeCoverQuery,
    IsEulerianQuery,
    HasEulerianPathQuery,
    IsSemieulerianQuery,
    EulerianCircuitQuery {
        #[serde(default)]
        source: Option<String>,
    },
    EulerianPathQuery {
        #[serde(default)]
        source: Option<String>,
    },
    ClosenessVitalityQuery,
    LouvainCommunitiesQuery {
        #[serde(default = "default_weight_attr")]
        weight_attr: String,
        #[serde(default)]
        resolution: Option<f64>,
        #[serde(default)]
        seed: Option<u64>,
    },
    ModularityQuery {
        communities: Vec<Vec<String>>,
        #[serde(default = "default_weight_attr")]
        weight_attr: String,
    },
    LabelPropagationCommunitiesQuery,
    GreedyModularityCommunitiesQuery {
        #[serde(default = "default_weight_attr")]
        weight_attr: String,
    },
    // Traversal algorithms
    DFSEdgesQuery {
        source: String,
        #[serde(default)]
        depth_limit: Option<usize>,
    },
    DFSPreorderNodesQuery {
        source: String,
        #[serde(default)]
        depth_limit: Option<usize>,
    },
    DFSPostorderNodesQuery {
        source: String,
        #[serde(default)]
        depth_limit: Option<usize>,
    },
    BFSEdgesQuery {
        source: String,
        #[serde(default)]
        depth_limit: Option<usize>,
    },
    BFSLayersQuery {
        source: String,
    },
    TopologicalSortQuery,
    // Link prediction algorithms
    JaccardCoefficientQuery {
        ebunch: Vec<(String, String)>,
    },
    AdamicAdarIndexQuery {
        ebunch: Vec<(String, String)>,
    },
    PreferentialAttachmentQuery {
        ebunch: Vec<(String, String)>,
    },
    ResourceAllocationIndexQuery {
        ebunch: Vec<(String, String)>,
    },
    // Isomorphism algorithms
    IsIsomorphicQuery {
        nodes2: Vec<String>,
        edges2: Vec<(String, String)>,
    },
    CouldBeIsomorphicQuery {
        nodes2: Vec<String>,
        edges2: Vec<(String, String)>,
    },
    FasterCouldBeIsomorphicQuery {
        nodes2: Vec<String>,
        edges2: Vec<(String, String)>,
    },
    // Graph metrics
    WienerIndexQuery,
    GirthQuery,
    DegreeAssortativityCoefficientQuery,
    SMetricQuery,
    RichClubCoefficientQuery,
    DispatchResolve {
        operation: String,
        #[serde(default)]
        requested_backend: Option<String>,
        #[serde(default)]
        required_features: Vec<String>,
        #[serde(default)]
        risk_probability: f64,
        #[serde(default)]
        unknown_incompatible_feature: bool,
    },
    ConvertEdgeList {
        payload: EdgeListPayload,
    },
    ConvertAdjacency {
        payload: AdjacencyPayload,
    },
    ReadEdgelist {
        input: String,
    },
    WriteEdgelist,
    ReadAdjlist {
        input: String,
    },
    WriteAdjlist,
    ReadJsonGraph {
        input: String,
    },
    WriteJsonGraph,
    ReadGraphml {
        input: String,
    },
    WriteGraphml,
    ViewNeighborsQuery {
        node: String,
    },
    GeneratePathGraph {
        n: usize,
    },
    GenerateStarGraph {
        n: usize,
    },
    GenerateCycleGraph {
        n: usize,
    },
    GenerateCompleteGraph {
        n: usize,
    },
    GenerateEmptyGraph {
        n: usize,
    },
    GenerateGnpRandomGraph {
        n: usize,
        p: f64,
        seed: u64,
    },
}

#[derive(Debug, Deserialize)]
struct ExpectedState {
    #[serde(default)]
    graph: Option<GraphSnapshotExpectation>,
    #[serde(default)]
    shortest_path_unweighted: Option<Vec<String>>,
    #[serde(default)]
    shortest_path_weighted: Option<Vec<String>>,
    #[serde(default)]
    max_flow_value: Option<f64>,
    #[serde(default)]
    minimum_cut: Option<ExpectedMinimumCut>,
    #[serde(default)]
    minimum_st_edge_cut: Option<ExpectedEdgeCut>,
    #[serde(default)]
    edge_connectivity_value: Option<f64>,
    #[serde(default)]
    global_edge_connectivity_value: Option<f64>,
    #[serde(default)]
    global_minimum_edge_cut: Option<ExpectedGlobalEdgeCut>,
    #[serde(default)]
    betweenness_centrality: Option<Vec<ExpectedCentralityScore>>,
    #[serde(default)]
    edge_betweenness_centrality: Option<Vec<ExpectedEdgeCentralityScore>>,
    #[serde(default)]
    degree_centrality: Option<Vec<ExpectedCentralityScore>>,
    #[serde(default)]
    closeness_centrality: Option<Vec<ExpectedCentralityScore>>,
    #[serde(default)]
    harmonic_centrality: Option<Vec<ExpectedCentralityScore>>,
    #[serde(default)]
    katz_centrality: Option<Vec<ExpectedCentralityScore>>,
    #[serde(default)]
    hits_hubs: Option<Vec<ExpectedCentralityScore>>,
    #[serde(default)]
    hits_authorities: Option<Vec<ExpectedCentralityScore>>,
    #[serde(default)]
    pagerank: Option<Vec<ExpectedCentralityScore>>,
    #[serde(default)]
    eigenvector_centrality: Option<Vec<ExpectedCentralityScore>>,
    #[serde(default)]
    clustering_coefficient: Option<Vec<ExpectedCentralityScore>>,
    #[serde(default)]
    average_clustering: Option<f64>,
    #[serde(default)]
    transitivity: Option<f64>,
    #[serde(default)]
    eccentricity: Option<Vec<ExpectedEccentricityEntry>>,
    #[serde(default)]
    diameter: Option<usize>,
    #[serde(default)]
    radius: Option<usize>,
    #[serde(default)]
    center: Option<Vec<String>>,
    #[serde(default)]
    periphery: Option<Vec<String>>,
    #[serde(default)]
    average_shortest_path_length: Option<f64>,
    #[serde(default)]
    is_connected: Option<bool>,
    #[serde(default)]
    density: Option<f64>,
    #[serde(default)]
    has_path: Option<bool>,
    #[serde(default)]
    shortest_path_length: Option<usize>,
    #[serde(default)]
    connected_components: Option<Vec<Vec<String>>>,
    #[serde(default)]
    number_connected_components: Option<usize>,
    #[serde(default)]
    articulation_points: Option<Vec<String>>,
    #[serde(default)]
    bridges: Option<Vec<(String, String)>>,
    #[serde(default)]
    bellman_ford_distances: Option<Vec<ExpectedWeightedDistance>>,
    #[serde(default)]
    bellman_ford_predecessors: Option<Vec<ExpectedWeightedPredecessor>>,
    #[serde(default)]
    bellman_ford_negative_cycle: Option<bool>,
    #[serde(default)]
    multi_source_dijkstra_distances: Option<Vec<ExpectedWeightedDistance>>,
    #[serde(default)]
    multi_source_dijkstra_predecessors: Option<Vec<ExpectedWeightedPredecessor>>,
    #[serde(default)]
    maximal_matching: Option<Vec<(String, String)>>,
    #[serde(default)]
    max_weight_matching: Option<ExpectedWeightedMatching>,
    #[serde(default)]
    min_weight_matching: Option<ExpectedWeightedMatching>,
    #[serde(default)]
    minimum_spanning_tree: Option<ExpectedMst>,
    #[serde(default)]
    triangles: Option<Vec<ExpectedTriangleCount>>,
    #[serde(default)]
    square_clustering: Option<Vec<ExpectedCentralityScore>>,
    #[serde(default)]
    is_tree: Option<bool>,
    #[serde(default)]
    is_forest: Option<bool>,
    #[serde(default)]
    greedy_coloring: Option<Vec<ExpectedNodeColor>>,
    #[serde(default)]
    num_colors: Option<usize>,
    #[serde(default)]
    is_bipartite: Option<bool>,
    #[serde(default)]
    bipartite_sets: Option<ExpectedBipartiteSets>,
    #[serde(default)]
    core_numbers: Option<Vec<ExpectedCoreNumber>>,
    #[serde(default)]
    k_core_nodes: Option<Vec<String>>,
    #[serde(default)]
    k_shell_nodes: Option<Vec<String>>,
    #[serde(default)]
    k_crust_nodes: Option<Vec<String>>,
    #[serde(default)]
    k_corona_nodes: Option<Vec<String>>,
    #[serde(default)]
    average_neighbor_degree: Option<Vec<ExpectedAvgNeighborDegree>>,
    #[serde(default)]
    degree_assortativity: Option<f64>,
    #[serde(default)]
    voterank: Option<Vec<String>>,
    #[serde(default)]
    cliques: Option<Vec<Vec<String>>>,
    #[serde(default)]
    clique_number: Option<usize>,
    #[serde(default)]
    node_connectivity: Option<usize>,
    #[serde(default)]
    minimum_node_cut: Option<Vec<String>>,
    #[serde(default)]
    global_node_connectivity: Option<usize>,
    #[serde(default)]
    global_minimum_node_cut: Option<Vec<String>>,
    #[serde(default)]
    cycle_basis: Option<Vec<Vec<String>>>,
    #[serde(default)]
    all_simple_paths: Option<Vec<Vec<String>>>,
    #[serde(default)]
    global_efficiency: Option<f64>,
    #[serde(default)]
    local_efficiency: Option<f64>,
    #[serde(default)]
    min_edge_cover: Option<Vec<ExpectedEdgePair>>,
    #[serde(default)]
    is_eulerian: Option<bool>,
    #[serde(default)]
    has_eulerian_path: Option<bool>,
    #[serde(default)]
    is_semieulerian: Option<bool>,
    #[serde(default)]
    closeness_vitality: Option<Vec<ExpectedClosenessVitality>>,
    #[serde(default)]
    eulerian_circuit: Option<Vec<ExpectedEdgePair>>,
    #[serde(default)]
    eulerian_circuit_edge_count: Option<usize>,
    #[serde(default)]
    eulerian_path: Option<Vec<ExpectedEdgePair>>,
    #[serde(default)]
    eulerian_path_edge_count: Option<usize>,
    #[serde(default)]
    dispatch: Option<ExpectedDispatch>,
    #[serde(default)]
    serialized_edgelist: Option<String>,
    #[serde(default)]
    serialized_adjlist: Option<String>,
    #[serde(default)]
    serialized_json_graph: Option<String>,
    #[serde(default)]
    serialized_graphml: Option<String>,
    #[serde(default)]
    view_neighbors: Option<Vec<String>>,
    #[serde(default)]
    warnings_contains: Vec<String>,
    #[serde(default)]
    louvain_communities_count: Option<usize>,
    #[serde(default)]
    #[allow(dead_code)] // Reserved for exact community membership comparison
    louvain_communities: Option<Vec<Vec<String>>>,
    #[serde(default)]
    modularity: Option<f64>,
    #[serde(default)]
    label_propagation_communities_count: Option<usize>,
    #[serde(default)]
    #[allow(dead_code)] // Reserved for exact community membership comparison
    label_propagation_communities: Option<Vec<Vec<String>>>,
    #[serde(default)]
    greedy_modularity_communities_count: Option<usize>,
    #[serde(default)]
    #[allow(dead_code)] // Reserved for exact community membership comparison
    greedy_modularity_communities: Option<Vec<Vec<String>>>,
    // Traversal expected results
    #[serde(default)]
    dfs_edges: Option<Vec<ExpectedEdgePair>>,
    #[serde(default)]
    dfs_preorder_nodes: Option<Vec<String>>,
    #[serde(default)]
    dfs_postorder_nodes: Option<Vec<String>>,
    #[serde(default)]
    bfs_edges: Option<Vec<ExpectedEdgePair>>,
    #[serde(default)]
    bfs_layers: Option<Vec<Vec<String>>>,
    #[serde(default)]
    topological_sort: Option<Vec<String>>,
    // Link prediction expected results
    #[serde(default)]
    jaccard_coefficient: Option<Vec<ExpectedLinkPredictionScore>>,
    #[serde(default)]
    adamic_adar_index: Option<Vec<ExpectedLinkPredictionScore>>,
    #[serde(default)]
    preferential_attachment: Option<Vec<ExpectedLinkPredictionScore>>,
    #[serde(default)]
    resource_allocation_index: Option<Vec<ExpectedLinkPredictionScore>>,
    // Isomorphism expected results
    #[serde(default)]
    is_isomorphic: Option<bool>,
    #[serde(default)]
    could_be_isomorphic: Option<bool>,
    #[serde(default)]
    faster_could_be_isomorphic: Option<bool>,
    // Graph metrics expected results
    #[serde(default)]
    wiener_index: Option<f64>,
    #[serde(default)]
    girth: Option<Option<usize>>,
    #[serde(default)]
    degree_assortativity_coefficient: Option<f64>,
    #[serde(default)]
    s_metric: Option<f64>,
    #[serde(default)]
    rich_club_coefficient: Option<Vec<ExpectedRichClubEntry>>,
}

#[derive(Debug, Deserialize, Clone)]
struct ExpectedLinkPredictionScore {
    u: String,
    v: String,
    score: f64,
}

#[derive(Debug, Deserialize, Clone)]
struct ExpectedRichClubEntry {
    k: usize,
    phi: f64,
}

#[derive(Debug, Deserialize)]
struct GraphSnapshotExpectation {
    nodes: Vec<String>,
    edges: Vec<EdgeSnapshot>,
}

#[derive(Debug, Deserialize)]
struct ExpectedDispatch {
    selected_backend: Option<String>,
    action: DecisionAction,
}

#[derive(Debug, Deserialize)]
struct ExpectedMinimumCut {
    value: f64,
    source_partition: Vec<String>,
    sink_partition: Vec<String>,
}

#[derive(Debug, Deserialize)]
struct ExpectedEdgeCut {
    value: f64,
    cut_edges: Vec<(String, String)>,
    source_partition: Vec<String>,
    sink_partition: Vec<String>,
}

#[derive(Debug, Deserialize)]
struct ExpectedGlobalEdgeCut {
    value: f64,
    source: String,
    sink: String,
    cut_edges: Vec<(String, String)>,
    source_partition: Vec<String>,
    sink_partition: Vec<String>,
}

#[derive(Debug, Clone, Deserialize)]
struct ExpectedCentralityScore {
    node: String,
    score: f64,
}

#[derive(Debug, Clone, Deserialize)]
struct ExpectedEdgeCentralityScore {
    left: String,
    right: String,
    score: f64,
}

#[derive(Debug, Clone, Deserialize)]
struct ExpectedEccentricityEntry {
    node: String,
    value: usize,
}

#[derive(Debug, Clone, Deserialize)]
struct ExpectedWeightedDistance {
    node: String,
    distance: f64,
}

#[derive(Debug, Clone, Deserialize)]
struct ExpectedWeightedPredecessor {
    node: String,
    predecessor: Option<String>,
}

#[derive(Debug, Clone, Deserialize)]
struct ExpectedWeightedMatching {
    matching: Vec<(String, String)>,
    total_weight: f64,
}

#[derive(Debug, Clone, Deserialize)]
struct ExpectedBipartiteSets {
    set_a: Vec<String>,
    set_b: Vec<String>,
}

#[derive(Debug, Clone, Deserialize)]
struct ExpectedNodeColor {
    node: String,
    color: usize,
}

#[derive(Debug, Clone, Deserialize)]
struct ExpectedTriangleCount {
    node: String,
    count: usize,
}

#[derive(Debug, Clone, Deserialize)]
struct ExpectedMstEdge {
    left: String,
    right: String,
    weight: f64,
}

#[derive(Debug, Clone, Deserialize)]
struct ExpectedMst {
    edges: Vec<ExpectedMstEdge>,
    total_weight: f64,
}

#[derive(Debug, Clone, Deserialize)]
struct ExpectedCoreNumber {
    node: String,
    core: usize,
}

#[derive(Debug, Clone, Deserialize)]
struct ExpectedAvgNeighborDegree {
    node: String,
    avg_neighbor_degree: f64,
}

#[derive(Debug, Clone, Deserialize)]
struct ExpectedEdgePair {
    #[serde(alias = "from")]
    left: String,
    #[serde(alias = "to")]
    right: String,
}

#[derive(Debug, Clone, Deserialize)]
struct ExpectedClosenessVitality {
    node: String,
    vitality: f64,
}

#[derive(Debug)]
struct ExecutionContext {
    graph: Graph,
    dispatch_registry: BackendRegistry,
    shortest_path_result: Option<Vec<String>>,
    shortest_path_weighted_result: Option<Vec<String>>,
    max_flow_result: Option<f64>,
    minimum_cut_result: Option<MinimumCutResult>,
    minimum_st_edge_cut_result: Option<EdgeCutResult>,
    edge_connectivity_result: Option<f64>,
    global_edge_connectivity_result: Option<f64>,
    global_minimum_edge_cut_result: Option<GlobalEdgeCutResult>,
    dispatch_decision: Option<DispatchDecision>,
    serialized_edgelist: Option<String>,
    serialized_adjlist: Option<String>,
    serialized_json_graph: Option<String>,
    serialized_graphml: Option<String>,
    view_neighbors_result: Option<Vec<String>>,
    betweenness_centrality_result: Option<Vec<CentralityScore>>,
    edge_betweenness_centrality_result: Option<Vec<EdgeCentralityScore>>,
    degree_centrality_result: Option<Vec<CentralityScore>>,
    closeness_centrality_result: Option<Vec<CentralityScore>>,
    harmonic_centrality_result: Option<Vec<CentralityScore>>,
    katz_centrality_result: Option<Vec<CentralityScore>>,
    hits_hubs_result: Option<Vec<CentralityScore>>,
    hits_authorities_result: Option<Vec<CentralityScore>>,
    pagerank_result: Option<Vec<CentralityScore>>,
    eigenvector_centrality_result: Option<Vec<CentralityScore>>,
    clustering_coefficient_result: Option<Vec<CentralityScore>>,
    average_clustering_result: Option<f64>,
    transitivity_result: Option<f64>,
    distance_measures_result: Option<DistanceMeasuresResult>,
    average_shortest_path_length_result: Option<AverageShortestPathLengthResult>,
    is_connected_result: Option<IsConnectedResult>,
    density_result: Option<DensityResult>,
    has_path_result: Option<HasPathResult>,
    shortest_path_length_result: Option<ShortestPathLengthResult>,
    connected_components_result: Option<Vec<Vec<String>>>,
    number_connected_components_result: Option<usize>,
    articulation_points_result: Option<Vec<String>>,
    bridges_result: Option<Vec<(String, String)>>,
    bellman_ford_result: Option<WeightedShortestPathsResult>,
    multi_source_dijkstra_result: Option<WeightedShortestPathsResult>,
    maximal_matching_result: Option<MaximalMatchingResult>,
    max_weight_matching_result: Option<WeightedMatchingResult>,
    min_weight_matching_result: Option<WeightedMatchingResult>,
    minimum_spanning_tree_result: Option<MinimumSpanningTreeResult>,
    triangles_result: Option<TrianglesResult>,
    square_clustering_result: Option<SquareClusteringResult>,
    is_tree_result: Option<IsTreeResult>,
    is_forest_result: Option<IsForestResult>,
    greedy_color_result: Option<GreedyColorResult>,
    is_bipartite_result: Option<IsBipartiteResult>,
    bipartite_sets_result: Option<BipartiteSetsResult>,
    core_number_result: Option<CoreNumberResult>,
    k_core_result: Option<fnx_algorithms::KCoreResult>,
    k_shell_result: Option<fnx_algorithms::KCoreResult>,
    k_crust_result: Option<fnx_algorithms::KCoreResult>,
    k_corona_result: Option<fnx_algorithms::KCoreResult>,
    avg_neighbor_degree_result: Option<AverageNeighborDegreeResult>,
    degree_assortativity_result: Option<DegreeAssortativityResult>,
    voterank_result: Option<VoterankResult>,
    find_cliques_result: Option<fnx_algorithms::FindCliquesResult>,
    node_connectivity_result: Option<fnx_algorithms::NodeConnectivityResult>,
    minimum_node_cut_result: Option<fnx_algorithms::MinimumNodeCutResult>,
    global_node_connectivity_result: Option<fnx_algorithms::NodeConnectivityResult>,
    global_minimum_node_cut_result: Option<fnx_algorithms::MinimumNodeCutResult>,
    cycle_basis_result: Option<CycleBasisResult>,
    all_simple_paths_result: Option<AllSimplePathsResult>,
    global_efficiency_result: Option<GlobalEfficiencyResult>,
    local_efficiency_result: Option<LocalEfficiencyResult>,
    min_edge_cover_result: Option<MinEdgeCoverResult>,
    is_eulerian_result: Option<fnx_algorithms::IsEulerianResult>,
    has_eulerian_path_result: Option<fnx_algorithms::HasEulerianPathResult>,
    is_semieulerian_result: Option<fnx_algorithms::IsSemiEulerianResult>,
    closeness_vitality_result: Option<fnx_algorithms::ClosenessVitalityResult>,
    eulerian_circuit_result: Option<fnx_algorithms::EulerianCircuitResult>,
    eulerian_path_result: Option<fnx_algorithms::EulerianPathResult>,
    louvain_communities_result: Option<Vec<Vec<String>>>,
    modularity_result: Option<f64>,
    label_propagation_communities_result: Option<Vec<Vec<String>>>,
    greedy_modularity_communities_result: Option<Vec<Vec<String>>>,
    // Traversal results
    dfs_edges_result: Option<Vec<(String, String)>>,
    dfs_preorder_nodes_result: Option<Vec<String>>,
    dfs_postorder_nodes_result: Option<Vec<String>>,
    bfs_edges_result: Option<Vec<(String, String)>>,
    bfs_layers_result: Option<Vec<Vec<String>>>,
    topological_sort_result: Option<Vec<String>>,
    // Link prediction results
    jaccard_coefficient_result: Option<Vec<(String, String, f64)>>,
    adamic_adar_index_result: Option<Vec<(String, String, f64)>>,
    preferential_attachment_result: Option<Vec<(String, String, f64)>>,
    resource_allocation_index_result: Option<Vec<(String, String, f64)>>,
    // Isomorphism results
    is_isomorphic_result: Option<bool>,
    could_be_isomorphic_result: Option<bool>,
    faster_could_be_isomorphic_result: Option<bool>,
    // Graph metrics results
    wiener_index_result: Option<f64>,
    girth_result: Option<Option<usize>>,
    degree_assortativity_coefficient_result: Option<f64>,
    s_metric_result: Option<f64>,
    rich_club_coefficient_result: Option<std::collections::HashMap<usize, f64>>,
    warnings: Vec<String>,
    witness: Option<ComplexityWitness>,
}

fn build_helper_graph_from_source(
    source: &Graph,
    nodes: &[String],
    edges: &[(String, String)],
) -> Graph {
    let runtime_policy = source.runtime_policy().clone();
    let mut graph = Graph::with_runtime_policy(runtime_policy.clone());
    for node in nodes {
        graph.add_node(node);
    }
    for (left, right) in edges {
        let _ = graph.add_edge(left, right);
    }
    graph.set_runtime_policy(runtime_policy);
    graph
}

#[must_use]
pub fn run_smoke(config: &HarnessConfig) -> HarnessReport {
    let mut fixture_reports = Vec::new();
    let run_id = format!(
        "conformance-{}-{}",
        unix_time_ms(),
        if config.mode == CompatibilityMode::Strict {
            "strict"
        } else {
            "hardened"
        }
    );

    for path in fixture_paths_recursive(&config.fixture_root) {
        if let Some(filter) = config.fixture_filter.as_deref() {
            let fixture_name = fixture_name_for_path(&path, &config.fixture_root);
            if fixture_name != filter && !fixture_name.ends_with(filter) {
                continue;
            }
        }
        fixture_reports.push(run_fixture(path, config.mode, &config.fixture_root));
    }

    let mismatch_count = fixture_reports
        .iter()
        .map(|report| report.strict_violation_count)
        .sum();
    let hardened_allowlisted_count = fixture_reports
        .iter()
        .map(|report| report.hardened_allowlisted_count)
        .sum();

    let report = HarnessReport {
        suite: "smoke",
        oracle_present: config.oracle_root.exists(),
        fixture_count: fixture_reports.len(),
        mode: config.mode,
        mismatch_count,
        hardened_allowlisted_count,
        structured_log_count: fixture_reports.len(),
        structured_log_path: config
            .report_root
            .as_ref()
            .map(|root| root.join("structured_logs.jsonl").display().to_string()),
        fixture_reports,
    };

    if let Some(report_root) = &config.report_root {
        let _ = write_artifacts(report_root, &report, &config.log_schema_version, &run_id);
    }

    report
}

fn write_artifacts(
    report_root: &Path,
    report: &HarnessReport,
    log_schema_version: &str,
    run_id: &str,
) -> Result<(), io::Error> {
    fs::create_dir_all(report_root)?;
    let smoke_path = report_root.join("smoke_report.json");
    fs::write(
        &smoke_path,
        serde_json::to_string_pretty(report).unwrap_or_else(|_| "{}".to_owned()),
    )?;

    let mut structured_logs = Vec::with_capacity(report.fixture_reports.len());
    for fixture in &report.fixture_reports {
        let sanitized = fixture.fixture_name.replace(['/', '\\', '.'], "_");
        let fixture_path = report_root.join(format!("{sanitized}.report.json"));
        fs::write(
            &fixture_path,
            serde_json::to_string_pretty(fixture).unwrap_or_else(|_| "{}".to_owned()),
        )?;
        let failure_envelope_path =
            if fixture.strict_violation_count > 0 || fixture.hardened_allowlisted_count > 0 {
                Some(report_root.join(format!("{sanitized}.failure_envelope.json")))
            } else {
                None
            };
        if let Some(envelope_path) = &failure_envelope_path {
            let envelope = build_failure_envelope(
                fixture,
                packet_id_for_fixture(&fixture.suite, &fixture.fixture_name),
                vec![
                    smoke_path.display().to_string(),
                    fixture_path.display().to_string(),
                ],
            );
            fs::write(
                envelope_path,
                serde_json::to_string_pretty(&envelope).map_err(io::Error::other)?,
            )?;
        }
        structured_logs.push(build_structured_log(
            report,
            fixture,
            &smoke_path,
            &fixture_path,
            log_schema_version,
            run_id,
            failure_envelope_path.as_deref(),
        ));
    }

    let mut jsonl = String::new();
    for log in &structured_logs {
        log.validate().map_err(io::Error::other)?;
        let line = serde_json::to_string(log).map_err(io::Error::other)?;
        jsonl.push_str(&line);
        jsonl.push('\n');
    }
    fs::write(report_root.join("structured_logs.jsonl"), jsonl)?;
    fs::write(
        report_root.join("structured_logs.json"),
        serde_json::to_string_pretty(&structured_logs).map_err(io::Error::other)?,
    )?;
    let normalization_report =
        build_emitter_normalization_report(report_root, report, &structured_logs, run_id);
    fs::write(
        report_root.join("structured_log_emitter_normalization_report.json"),
        serde_json::to_string_pretty(&normalization_report).map_err(io::Error::other)?,
    )?;
    let unblock_matrix = build_dependent_unblock_matrix(report_root, run_id);
    fs::write(
        report_root.join("telemetry_dependent_unblock_matrix_v1.json"),
        serde_json::to_string_pretty(&unblock_matrix).map_err(io::Error::other)?,
    )?;
    let drift_taxonomy_report = build_drift_taxonomy_report(report, run_id);
    fs::write(
        report_root.join("mismatch_taxonomy_report.json"),
        serde_json::to_string_pretty(&drift_taxonomy_report).map_err(io::Error::other)?,
    )?;

    Ok(())
}

fn build_emitter_normalization_report(
    report_root: &Path,
    report: &HarnessReport,
    structured_logs: &[StructuredTestLog],
    run_id: &str,
) -> EmitterNormalizationReport {
    let normalized_fields = vec![
        "schema_version",
        "run_id",
        "suite_id",
        "test_id",
        "test_kind",
        "mode",
        "environment",
        "env_fingerprint",
        "duration_ms",
        "replay_command",
        "artifact_refs",
        "forensic_bundle_id",
        "forensics_bundle_index",
        "hash_id",
        "status",
        "reason_code",
        "failure_repro",
        "e2e_step_traces",
    ]
    .into_iter()
    .map(str::to_owned)
    .collect::<Vec<String>>();
    let valid_log_count = structured_logs
        .iter()
        .filter(|log| log.validate().is_ok())
        .count();
    let findings = if valid_log_count == structured_logs.len() {
        vec!["all logs satisfy canonical emitter contract".to_owned()]
    } else {
        vec!["one or more logs failed canonical emitter contract".to_owned()]
    };
    let output_artifacts = vec![
        report_root.join("smoke_report.json").display().to_string(),
        report_root
            .join("structured_logs.jsonl")
            .display()
            .to_string(),
        report_root
            .join("structured_logs.json")
            .display()
            .to_string(),
        report_root
            .join("structured_log_emitter_normalization_report.json")
            .display()
            .to_string(),
        report_root
            .join("telemetry_dependent_unblock_matrix_v1.json")
            .display()
            .to_string(),
        report_root
            .join("mismatch_taxonomy_report.json")
            .display()
            .to_string(),
    ];

    EmitterNormalizationReport {
        schema_version: "1.0.0".to_owned(),
        generated_at_unix_ms: unix_time_ms(),
        crate_name: "fnx-conformance".to_owned(),
        run_id: run_id.to_owned(),
        suite: report.suite.to_owned(),
        fixture_count: report.fixture_count,
        valid_log_count,
        normalized_fields,
        findings,
        output_artifacts,
    }
}

fn build_dependent_unblock_matrix(report_root: &Path, run_id: &str) -> DependentUnblockMatrix {
    let schema_artifact =
        "artifacts/conformance/schema/v1/structured_test_log_schema_v1.json".to_owned();
    let e2e_schema_artifact =
        "artifacts/conformance/schema/v1/e2e_step_trace_schema_v1.json".to_owned();
    let bundle_schema_artifact =
        "artifacts/conformance/schema/v1/forensics_bundle_index_schema_v1.json".to_owned();
    let normalization_report = report_root
        .join("structured_log_emitter_normalization_report.json")
        .display()
        .to_string();
    let log_jsonl = report_root
        .join("structured_logs.jsonl")
        .display()
        .to_string();
    let log_json = report_root
        .join("structured_logs.json")
        .display()
        .to_string();
    let smoke_report = report_root.join("smoke_report.json").display().to_string();
    let matrix_rows = vec![
        DependentUnblockRow {
            blocked_bead_id: "bd-315.5.5".to_owned(),
            required_artifacts: vec![
                log_jsonl.clone(),
                "artifacts/conformance/latest/structured_logs.raptorq.json".to_owned(),
                "artifacts/conformance/latest/structured_logs.recovered.json".to_owned(),
            ],
            required_fields: vec![
                "forensic_bundle_id".to_owned(),
                "forensics_bundle_index.bundle_hash_id".to_owned(),
                "forensics_bundle_index.artifact_refs".to_owned(),
            ],
            evidence_paths: vec![normalization_report.clone(), schema_artifact.clone()],
        },
        DependentUnblockRow {
            blocked_bead_id: "bd-315.21".to_owned(),
            required_artifacts: vec![log_json.clone(), smoke_report.clone()],
            required_fields: vec![
                "test_id".to_owned(),
                "fixture_id".to_owned(),
                "seed".to_owned(),
                "env_fingerprint".to_owned(),
                "replay_command".to_owned(),
                "reason_code".to_owned(),
            ],
            evidence_paths: vec![normalization_report.clone(), schema_artifact.clone()],
        },
        DependentUnblockRow {
            blocked_bead_id: "bd-315.6.1".to_owned(),
            required_artifacts: vec![log_jsonl.clone(), smoke_report.clone()],
            required_fields: vec![
                "mode".to_owned(),
                "forensic_bundle_id".to_owned(),
                "forensics_bundle_index.replay_ref".to_owned(),
            ],
            evidence_paths: vec![normalization_report.clone(), bundle_schema_artifact.clone()],
        },
        DependentUnblockRow {
            blocked_bead_id: "bd-315.7.1".to_owned(),
            required_artifacts: vec![log_jsonl.clone()],
            required_fields: vec![
                "e2e_step_traces".to_owned(),
                "forensics_bundle_index.bundle_id".to_owned(),
            ],
            evidence_paths: vec![normalization_report.clone(), e2e_schema_artifact.clone()],
        },
        DependentUnblockRow {
            blocked_bead_id: "bd-315.8.1".to_owned(),
            required_artifacts: vec![log_jsonl, smoke_report],
            required_fields: vec![
                "schema_version".to_owned(),
                "packet_id".to_owned(),
                "hash_id".to_owned(),
            ],
            evidence_paths: vec![normalization_report, schema_artifact],
        },
    ];

    DependentUnblockMatrix {
        schema_version: "1.0.0".to_owned(),
        generated_at_unix_ms: unix_time_ms(),
        source_bead_id: "bd-315.5.4".to_owned(),
        run_id: run_id.to_owned(),
        rows: matrix_rows,
    }
}

fn classify_mismatch_taxonomy(
    mode: CompatibilityMode,
    mismatches: &[Mismatch],
    hardened_allowlisted_categories: &BTreeSet<String>,
) -> Vec<TaxonomyMismatch> {
    mismatches
        .iter()
        .map(|mismatch| {
            let allowlisted_in_hardened =
                hardened_allowlisted_categories.contains(&mismatch.category.to_ascii_lowercase());
            let classification = if mode == CompatibilityMode::Hardened && allowlisted_in_hardened {
                MismatchClassification::HardenedAllowlisted
            } else {
                MismatchClassification::StrictViolation
            };
            TaxonomyMismatch {
                category: mismatch.category.clone(),
                message: mismatch.message.clone(),
                classification,
                allowlisted_in_hardened,
            }
        })
        .collect()
}

fn build_drift_taxonomy_report(report: &HarnessReport, run_id: &str) -> DriftTaxonomyReport {
    let fixtures = report
        .fixture_reports
        .iter()
        .map(|fixture| DriftTaxonomyFixtureRow {
            fixture_id: fixture.fixture_id.clone(),
            fixture_name: fixture.fixture_name.clone(),
            packet_id: packet_id_for_fixture(&fixture.suite, &fixture.fixture_name),
            mode: fixture.mode,
            seed: fixture.seed,
            threat_class: fixture.threat_class.clone(),
            replay_command: fixture.replay_command.clone(),
            strict_violation_count: fixture.strict_violation_count,
            hardened_allowlisted_count: fixture.hardened_allowlisted_count,
            mismatches: fixture.mismatch_taxonomy.clone(),
        })
        .collect();
    DriftTaxonomyReport {
        schema_version: "1.0.0".to_owned(),
        generated_at_unix_ms: unix_time_ms(),
        run_id: run_id.to_owned(),
        strict_violation_count: report.mismatch_count,
        hardened_allowlisted_count: report.hardened_allowlisted_count,
        fixtures,
    }
}

fn build_failure_envelope(
    fixture: &FixtureReport,
    packet_id: String,
    artifact_refs: Vec<String>,
) -> FailureArtifactEnvelope {
    FailureArtifactEnvelope {
        schema_version: "1.0.0".to_owned(),
        generated_at_unix_ms: unix_time_ms(),
        fixture_id: fixture.fixture_id.clone(),
        fixture_name: fixture.fixture_name.clone(),
        packet_id,
        mode: fixture.mode,
        seed: fixture.seed,
        threat_class: fixture.threat_class.clone(),
        replay_command: fixture.replay_command.clone(),
        strict_violation_count: fixture.strict_violation_count,
        hardened_allowlisted_count: fixture.hardened_allowlisted_count,
        reason_code: fixture.reason_code.clone(),
        mismatches: fixture.mismatch_taxonomy.clone(),
        artifact_refs,
    }
}

fn build_structured_log(
    report: &HarnessReport,
    fixture: &FixtureReport,
    smoke_report_path: &Path,
    fixture_report_path: &Path,
    log_schema_version: &str,
    run_id: &str,
    failure_envelope_path: Option<&Path>,
) -> StructuredTestLog {
    let mode_flag = match fixture.mode {
        CompatibilityMode::Strict => "strict",
        CompatibilityMode::Hardened => "hardened",
    };
    let packet_id = packet_id_for_fixture(&fixture.suite, &fixture.fixture_name);
    let status = if fixture.passed {
        TestStatus::Passed
    } else {
        TestStatus::Failed
    };
    let test_id = format!("fixture::{}", fixture.fixture_id);
    let replay_command = fixture.replay_command.clone();
    let sanitized_test_id = fixture.fixture_id.replace(['/', '\\'], "::");
    let forensic_bundle_id = format!("forensics::{packet_id}::{sanitized_test_id}");
    let hash_id = stable_hash_hex(&format!(
        "{}|{}|{}|{}|{}|{}|{}|{}|{}",
        fixture.fixture_id,
        fixture.fixture_name,
        fixture.suite,
        mode_flag,
        fixture.passed,
        fixture.mismatches.len(),
        fixture.fixture_source_hash,
        fixture.strict_violation_count,
        fixture.hardened_allowlisted_count,
    ));

    let mut environment = BTreeMap::new();
    environment.insert("os".to_owned(), std::env::consts::OS.to_owned());
    environment.insert("arch".to_owned(), std::env::consts::ARCH.to_owned());
    environment.insert("suite".to_owned(), report.suite.to_owned());
    environment.insert(
        "oracle_present".to_owned(),
        report.oracle_present.to_string(),
    );
    environment.insert(
        "strict_mode_default".to_owned(),
        (report.mode == CompatibilityMode::Strict).to_string(),
    );
    environment.insert("run_id".to_owned(), run_id.to_owned());
    environment.insert("fixture_id".to_owned(), fixture.fixture_id.clone());
    environment.insert(
        "strict_violation_count".to_owned(),
        fixture.strict_violation_count.to_string(),
    );
    environment.insert(
        "hardened_allowlisted_count".to_owned(),
        fixture.hardened_allowlisted_count.to_string(),
    );
    if let Some(threat_class) = &fixture.threat_class {
        environment.insert("threat_class".to_owned(), threat_class.clone());
    }
    let env_fingerprint = canonical_environment_fingerprint(&environment);
    let mut artifact_refs = vec![
        smoke_report_path.display().to_string(),
        fixture_report_path.display().to_string(),
    ];
    if let Some(path) = failure_envelope_path {
        artifact_refs.push(path.display().to_string());
    }
    let bundle_hash_id = stable_hash_hex(&format!(
        "{}|{}|{}",
        forensic_bundle_id,
        hash_id,
        artifact_refs.join("|")
    ));
    let forensics_bundle_index = ForensicsBundleIndex {
        bundle_id: forensic_bundle_id.clone(),
        run_id: run_id.to_owned(),
        test_id: test_id.clone(),
        bundle_hash_id,
        captured_unix_ms: unix_time_ms(),
        replay_ref: replay_command.clone(),
        artifact_refs: artifact_refs.clone(),
        raptorq_sidecar_refs: vec![],
        decode_proof_refs: vec![],
    };

    StructuredTestLog {
        schema_version: log_schema_version.to_owned(),
        run_id: run_id.to_owned(),
        ts_unix_ms: unix_time_ms(),
        crate_name: "fnx-conformance".to_owned(),
        suite_id: report.suite.to_owned(),
        packet_id,
        test_name: test_id.clone(),
        test_id,
        test_kind: TestKind::Differential,
        mode: fixture.mode,
        fixture_id: Some(fixture.fixture_id.clone()),
        seed: fixture.seed,
        environment,
        env_fingerprint,
        duration_ms: fixture.duration_ms,
        replay_command: replay_command.clone(),
        artifact_refs,
        forensic_bundle_id: forensic_bundle_id.clone(),
        hash_id: hash_id.clone(),
        status,
        reason_code: fixture.reason_code.clone(),
        failure_repro: if fixture.passed {
            None
        } else {
            Some(FailureReproData {
                failure_message: fixture
                    .mismatches
                    .iter()
                    .map(|mismatch| format!("{}: {}", mismatch.category, mismatch.message))
                    .collect::<Vec<String>>()
                    .join(" | "),
                reproduction_command: replay_command,
                expected_behavior: "Fixture should match expected outputs with zero mismatches"
                    .to_owned(),
                observed_behavior: format!("{} mismatches reported", fixture.mismatches.len()),
                seed: fixture.seed,
                fixture_id: Some(fixture.fixture_id.clone()),
                artifact_hash_id: Some(hash_id),
                forensics_link: Some(failure_envelope_path.map_or_else(
                    || fixture_report_path.display().to_string(),
                    |path| path.display().to_string(),
                )),
            })
        },
        e2e_step_traces: Vec::new(),
        forensics_bundle_index: Some(forensics_bundle_index),
    }
}

fn packet_id_for_fixture(suite: &str, fixture_name: &str) -> String {
    let key = format!(
        "{} {}",
        suite.to_ascii_lowercase(),
        fixture_name.to_ascii_lowercase()
    );
    if key.contains("graph_core") {
        "FNX-P2C-001".to_owned()
    } else if key.contains("view") {
        "FNX-P2C-002".to_owned()
    } else if key.contains("dispatch") {
        "FNX-P2C-003".to_owned()
    } else if key.contains("convert") {
        "FNX-P2C-004".to_owned()
    } else if key.contains("shortest_path")
        || key.contains("centrality")
        || key.contains("component")
        || key.contains("flow")
    {
        "FNX-P2C-005".to_owned()
    } else if key.contains("readwrite") || key.contains("edgelist") || key.contains("json_graph") {
        "FNX-P2C-006".to_owned()
    } else if key.contains("generator")
        || key.contains("generate_")
        || key.contains("path_graph")
        || key.contains("cycle_graph")
        || key.contains("complete_graph")
        || key.contains("empty_graph")
    {
        "FNX-P2C-007".to_owned()
    } else if key.contains("runtime_config") || key.contains("optional") {
        "FNX-P2C-008".to_owned()
    } else if key.contains("conformance") || key.contains("harness") {
        "FNX-P2C-009".to_owned()
    } else {
        "FNX-P2C-FOUNDATION".to_owned()
    }
}

fn reproduction_command_for_fixture(fixture_name: &str, mode: CompatibilityMode) -> String {
    let mode_flag = match mode {
        CompatibilityMode::Strict => "strict",
        CompatibilityMode::Hardened => "hardened",
    };
    format!(
        "rch exec -- CARGO_TARGET_DIR=target-codex cargo run -q -p fnx-conformance --bin run_smoke -- --fixture {fixture_name} --mode {mode_flag}"
    )
}

fn stable_hash_hex(input: &str) -> String {
    let mut hash = 0xcbf29ce484222325_u64;
    for byte in input.as_bytes() {
        hash ^= u64::from(*byte);
        hash = hash.wrapping_mul(0x00000100000001B3_u64);
    }
    format!("{hash:016x}")
}

fn fixture_name_for_path(path: &Path, fixture_root: &Path) -> String {
    path.strip_prefix(fixture_root)
        .unwrap_or(path)
        .to_string_lossy()
        .to_string()
}

fn fixture_paths_recursive(root: &Path) -> Vec<PathBuf> {
    let mut out = Vec::new();
    collect_fixture_paths(root, &mut out);
    out.sort_unstable();
    out
}

fn collect_fixture_paths(path: &Path, out: &mut Vec<PathBuf>) {
    let Ok(entries) = fs::read_dir(path) else {
        return;
    };

    for entry in entries.filter_map(Result::ok) {
        let p = entry.path();
        if p.is_dir() {
            collect_fixture_paths(&p, out);
            continue;
        }
        if p.extension().and_then(|ext| ext.to_str()) != Some("json") {
            continue;
        }
        let Some(file_name) = p.file_name().and_then(|name| name.to_str()) else {
            continue;
        };
        if file_name == "smoke_case.json" {
            continue;
        }
        if !(file_name.contains("_strict") || file_name.contains("_hardened")) {
            continue;
        }
        out.push(p);
    }
}

fn run_fixture(
    path: PathBuf,
    default_mode: CompatibilityMode,
    fixture_root: &Path,
) -> FixtureReport {
    let fixture_start = Instant::now();
    let fixture_name = fixture_name_for_path(&path, fixture_root);
    let fallback_source_hash = stable_hash_hex(&fixture_name);

    let data = match fs::read_to_string(&path) {
        Ok(value) => value,
        Err(err) => {
            let mode = default_mode;
            let replay_command = reproduction_command_for_fixture(&fixture_name, mode);
            let mismatch = Mismatch {
                category: "fixture_io".to_owned(),
                message: format!("failed to read fixture: {err}"),
            };
            return FixtureReport {
                fixture_id: fixture_name.clone(),
                fixture_name,
                suite: "read_error".to_owned(),
                mode,
                seed: None,
                threat_class: None,
                replay_command,
                passed: false,
                reason_code: Some("read_error".to_owned()),
                fixture_source_hash: fallback_source_hash,
                duration_ms: fixture_start.elapsed().as_millis(),
                strict_violation_count: 1,
                hardened_allowlisted_count: 0,
                mismatches: vec![mismatch.clone()],
                mismatch_taxonomy: vec![TaxonomyMismatch {
                    category: mismatch.category,
                    message: mismatch.message,
                    classification: MismatchClassification::StrictViolation,
                    allowlisted_in_hardened: false,
                }],
                witness: None,
            };
        }
    };
    let fixture_source_hash = stable_hash_hex(&data);

    let fixture = match serde_json::from_str::<ConformanceFixture>(&data) {
        Ok(value) => value,
        Err(err) => {
            let mode = default_mode;
            let replay_command = reproduction_command_for_fixture(&fixture_name, mode);
            let mismatch = Mismatch {
                category: "fixture_schema".to_owned(),
                message: format!("failed to parse fixture: {err}"),
            };
            return FixtureReport {
                fixture_id: fixture_name.clone(),
                fixture_name,
                suite: "parse_error".to_owned(),
                mode,
                seed: None,
                threat_class: None,
                replay_command,
                passed: false,
                reason_code: Some("parse_error".to_owned()),
                fixture_source_hash,
                duration_ms: fixture_start.elapsed().as_millis(),
                strict_violation_count: 1,
                hardened_allowlisted_count: 0,
                mismatches: vec![mismatch.clone()],
                mismatch_taxonomy: vec![TaxonomyMismatch {
                    category: mismatch.category,
                    message: mismatch.message,
                    classification: MismatchClassification::StrictViolation,
                    allowlisted_in_hardened: false,
                }],
                witness: None,
            };
        }
    };

    let mode = fixture.mode.map_or(default_mode, ModeValue::as_mode);
    let fixture_id = fixture
        .fixture_id
        .clone()
        .unwrap_or_else(|| fixture_name.clone());
    let seed = fixture.seed;
    let threat_class = fixture.threat_class.clone();
    let replay_command = fixture
        .replay_command
        .clone()
        .unwrap_or_else(|| reproduction_command_for_fixture(&fixture_name, mode));
    let hardened_allowlisted_categories = fixture
        .hardened_allowlisted_categories
        .iter()
        .map(|category| category.to_ascii_lowercase())
        .collect::<BTreeSet<String>>();

    let mut context = ExecutionContext {
        graph: Graph::new(mode),
        dispatch_registry: default_dispatch_registry(mode),
        shortest_path_result: None,
        shortest_path_weighted_result: None,
        max_flow_result: None,
        minimum_cut_result: None,
        minimum_st_edge_cut_result: None,
        edge_connectivity_result: None,
        global_edge_connectivity_result: None,
        global_minimum_edge_cut_result: None,
        dispatch_decision: None,
        serialized_edgelist: None,
        serialized_adjlist: None,
        serialized_json_graph: None,
        serialized_graphml: None,
        view_neighbors_result: None,
        betweenness_centrality_result: None,
        edge_betweenness_centrality_result: None,
        degree_centrality_result: None,
        closeness_centrality_result: None,
        harmonic_centrality_result: None,
        katz_centrality_result: None,
        hits_hubs_result: None,
        hits_authorities_result: None,
        pagerank_result: None,
        eigenvector_centrality_result: None,
        clustering_coefficient_result: None,
        average_clustering_result: None,
        transitivity_result: None,
        distance_measures_result: None,
        average_shortest_path_length_result: None,
        is_connected_result: None,
        density_result: None,
        has_path_result: None,
        shortest_path_length_result: None,
        connected_components_result: None,
        number_connected_components_result: None,
        articulation_points_result: None,
        bridges_result: None,
        bellman_ford_result: None,
        multi_source_dijkstra_result: None,
        maximal_matching_result: None,
        max_weight_matching_result: None,
        min_weight_matching_result: None,
        minimum_spanning_tree_result: None,
        triangles_result: None,
        square_clustering_result: None,
        is_tree_result: None,
        is_forest_result: None,
        greedy_color_result: None,
        is_bipartite_result: None,
        bipartite_sets_result: None,
        core_number_result: None,
        k_core_result: None,
        k_shell_result: None,
        k_crust_result: None,
        k_corona_result: None,
        avg_neighbor_degree_result: None,
        degree_assortativity_result: None,
        voterank_result: None,
        find_cliques_result: None,
        node_connectivity_result: None,
        minimum_node_cut_result: None,
        global_node_connectivity_result: None,
        global_minimum_node_cut_result: None,
        cycle_basis_result: None,
        all_simple_paths_result: None,
        global_efficiency_result: None,
        local_efficiency_result: None,
        min_edge_cover_result: None,
        is_eulerian_result: None,
        has_eulerian_path_result: None,
        is_semieulerian_result: None,
        closeness_vitality_result: None,
        eulerian_circuit_result: None,
        eulerian_path_result: None,
        louvain_communities_result: None,
        modularity_result: None,
        label_propagation_communities_result: None,
        greedy_modularity_communities_result: None,
        dfs_edges_result: None,
        dfs_preorder_nodes_result: None,
        dfs_postorder_nodes_result: None,
        bfs_edges_result: None,
        bfs_layers_result: None,
        topological_sort_result: None,
        jaccard_coefficient_result: None,
        adamic_adar_index_result: None,
        preferential_attachment_result: None,
        resource_allocation_index_result: None,
        is_isomorphic_result: None,
        could_be_isomorphic_result: None,
        faster_could_be_isomorphic_result: None,
        wiener_index_result: None,
        girth_result: None,
        degree_assortativity_coefficient_result: None,
        s_metric_result: None,
        rich_club_coefficient_result: None,
        warnings: Vec::new(),
        witness: None,
    };
    let mut mismatches = Vec::new();

    for operation in fixture.operations {
        match operation {
            Operation::AddNode { node, attrs } => {
                let _ = context.graph.add_node_with_attrs(node, attrs);
            }
            Operation::AddEdge { left, right, attrs } => {
                if let Err(err) = context.graph.add_edge_with_attrs(left, right, attrs) {
                    mismatches.push(Mismatch {
                        category: "graph_mutation".to_owned(),
                        message: format!("add_edge failed: {err}"),
                    });
                }
            }
            Operation::RemoveNode { node } => {
                let _ = context.graph.remove_node(&node);
            }
            Operation::RemoveEdge { left, right } => {
                let _ = context.graph.remove_edge(&left, &right);
            }
            Operation::ShortestPathQuery { source, target } => {
                let result = shortest_path_unweighted(&context.graph, &source, &target);
                context.shortest_path_result = result.path;
                context.witness = Some(result.witness);
            }
            Operation::WeightedShortestPathQuery {
                source,
                target,
                weight_attr,
            } => {
                let result = shortest_path_weighted(&context.graph, &source, &target, &weight_attr);
                context.shortest_path_weighted_result = result.path;
                context.witness = Some(result.witness);
            }
            Operation::MaxFlowQuery {
                source,
                target,
                capacity_attr,
            } => {
                let result =
                    max_flow_edmonds_karp(&context.graph, &source, &target, &capacity_attr)
                        .expect("flow algorithm should succeed");
                context.max_flow_result = Some(result.value);
                context.witness = Some(result.witness);
            }
            Operation::MinimumCutQuery {
                source,
                target,
                capacity_attr,
            } => {
                let result =
                    minimum_cut_edmonds_karp(&context.graph, &source, &target, &capacity_attr)
                        .expect("flow algorithm should succeed");
                context.minimum_cut_result = Some(result.clone());
                context.witness = Some(result.witness);
            }
            Operation::MinimumStEdgeCutQuery {
                source,
                target,
                capacity_attr,
            } => {
                let result = minimum_st_edge_cut_edmonds_karp(
                    &context.graph,
                    &source,
                    &target,
                    &capacity_attr,
                )
                .expect("flow algorithm should succeed");
                context.minimum_st_edge_cut_result = Some(result.clone());
                context.witness = Some(result.witness);
            }
            Operation::EdgeConnectivityQuery {
                source,
                target,
                capacity_attr,
            } => {
                let result = edge_connectivity_edmonds_karp(
                    &context.graph,
                    &source,
                    &target,
                    &capacity_attr,
                )
                .expect("flow algorithm should succeed");
                context.edge_connectivity_result = Some(result.value);
                context.witness = Some(result.witness);
            }
            Operation::GlobalEdgeConnectivityQuery { capacity_attr } => {
                let result = global_edge_connectivity_edmonds_karp(&context.graph, &capacity_attr);
                context.global_edge_connectivity_result = Some(result.value);
                context.witness = Some(result.witness);
            }
            Operation::GlobalMinimumEdgeCutQuery { capacity_attr } => {
                let result = global_minimum_edge_cut_edmonds_karp(&context.graph, &capacity_attr);
                context.global_minimum_edge_cut_result = Some(result.clone());
                context.witness = Some(result.witness);
            }
            Operation::BetweennessCentralityQuery => {
                let result = betweenness_centrality(&context.graph);
                context.betweenness_centrality_result = Some(result.scores);
                context.witness = Some(result.witness);
            }
            Operation::EdgeBetweennessCentralityQuery => {
                let result = edge_betweenness_centrality(&context.graph);
                context.edge_betweenness_centrality_result = Some(result.scores);
                context.witness = Some(result.witness);
            }
            Operation::DegreeCentralityQuery => {
                let result = degree_centrality(&context.graph);
                context.degree_centrality_result = Some(result.scores);
                context.witness = Some(result.witness);
            }
            Operation::ClosenessCentralityQuery => {
                let result = closeness_centrality(&context.graph);
                context.closeness_centrality_result = Some(result.scores);
                context.witness = Some(result.witness);
            }
            Operation::HarmonicCentralityQuery => {
                let result = harmonic_centrality(&context.graph);
                context.harmonic_centrality_result = Some(result.scores);
                context.witness = Some(result.witness);
            }
            Operation::KatzCentralityQuery => {
                let result = katz_centrality(&context.graph);
                context.katz_centrality_result = Some(result.scores);
                context.witness = Some(result.witness);
            }
            Operation::HitsCentralityQuery => {
                let result = hits_centrality(&context.graph);
                context.hits_hubs_result = Some(result.hubs);
                context.hits_authorities_result = Some(result.authorities);
                context.witness = Some(result.witness);
            }
            Operation::PagerankQuery => {
                let result = pagerank(&context.graph);
                context.pagerank_result = Some(result.scores);
                context.witness = Some(result.witness);
            }
            Operation::EigenvectorCentralityQuery => {
                let result = eigenvector_centrality(&context.graph);
                context.eigenvector_centrality_result = Some(result.scores);
                context.witness = Some(result.witness);
            }
            Operation::ClusteringCoefficientQuery => {
                let result = clustering_coefficient(&context.graph);
                context.clustering_coefficient_result = Some(result.scores);
                context.average_clustering_result = Some(result.average_clustering);
                context.transitivity_result = Some(result.transitivity);
                context.witness = Some(result.witness);
            }
            Operation::DistanceMeasuresQuery => {
                let result = distance_measures(&context.graph);
                context.witness = Some(result.witness.clone());
                context.distance_measures_result = Some(result);
            }
            Operation::AverageShortestPathLengthQuery => {
                let result = average_shortest_path_length(&context.graph);
                context.witness = Some(result.witness.clone());
                context.average_shortest_path_length_result = Some(result);
            }
            Operation::IsConnectedQuery => {
                let result = is_connected(&context.graph);
                context.witness = Some(result.witness.clone());
                context.is_connected_result = Some(result);
            }
            Operation::DensityQuery => {
                let result = density(&context.graph);
                context.density_result = Some(result);
            }
            Operation::HasPathQuery { source, target } => {
                let result = has_path(&context.graph, &source, &target);
                context.witness = Some(result.witness.clone());
                context.has_path_result = Some(result);
            }
            Operation::ShortestPathLengthQuery { source, target } => {
                let result = shortest_path_length(&context.graph, &source, &target);
                context.witness = Some(result.witness.clone());
                context.shortest_path_length_result = Some(result);
            }
            Operation::ConnectedComponentsQuery => {
                let result = connected_components(&context.graph);
                context.connected_components_result = Some(result.components);
                context.witness = Some(result.witness);
            }
            Operation::NumberConnectedComponentsQuery => {
                let result = number_connected_components(&context.graph);
                context.number_connected_components_result = Some(result.count);
                context.witness = Some(result.witness);
            }
            Operation::ArticulationPointsQuery => {
                let result = articulation_points(&context.graph);
                context.articulation_points_result = Some(result.nodes);
                context.witness = Some(result.witness);
            }
            Operation::BridgesQuery => {
                let result = bridges(&context.graph);
                context.bridges_result = Some(result.edges);
                context.witness = Some(result.witness);
            }
            Operation::BellmanFordQuery {
                source,
                weight_attr,
            } => {
                let result = bellman_ford_shortest_paths(&context.graph, &source, &weight_attr);
                context.bellman_ford_result = Some(result.clone());
                context.witness = Some(result.witness);
            }
            Operation::MultiSourceDijkstraQuery {
                sources,
                weight_attr,
            } => {
                let source_refs: Vec<&str> = sources.iter().map(String::as_str).collect();
                let result = multi_source_dijkstra(&context.graph, &source_refs, &weight_attr);
                context.multi_source_dijkstra_result = Some(result.clone());
                context.witness = Some(result.witness);
            }
            Operation::MaximalMatchingQuery => {
                let result = maximal_matching(&context.graph);
                context.maximal_matching_result = Some(result.clone());
                context.witness = Some(result.witness);
            }
            Operation::MaxWeightMatchingQuery {
                maxcardinality,
                weight_attr,
            } => {
                let result = max_weight_matching(&context.graph, maxcardinality, &weight_attr);
                context.max_weight_matching_result = Some(result.clone());
                context.witness = Some(result.witness);
            }
            Operation::MinWeightMatchingQuery { weight_attr } => {
                let result = min_weight_matching(&context.graph, &weight_attr);
                context.min_weight_matching_result = Some(result.clone());
                context.witness = Some(result.witness);
            }
            Operation::MinimumSpanningTreeQuery { weight_attr } => {
                let result = minimum_spanning_tree(&context.graph, &weight_attr);
                context.minimum_spanning_tree_result = Some(result.clone());
                context.witness = Some(result.witness);
            }
            Operation::TrianglesQuery => {
                let result = triangles(&context.graph);
                context.triangles_result = Some(result.clone());
                context.witness = Some(result.witness);
            }
            Operation::SquareClusteringQuery => {
                let result = square_clustering(&context.graph);
                context.square_clustering_result = Some(result.clone());
                context.witness = Some(result.witness);
            }
            Operation::IsTreeQuery => {
                let result = is_tree(&context.graph);
                context.is_tree_result = Some(result.clone());
                context.witness = Some(result.witness);
            }
            Operation::IsForestQuery => {
                let result = is_forest(&context.graph);
                context.is_forest_result = Some(result.clone());
                context.witness = Some(result.witness);
            }
            Operation::GreedyColorQuery => {
                let result = greedy_color(&context.graph);
                context.greedy_color_result = Some(result.clone());
                context.witness = Some(result.witness);
            }
            Operation::IsBipartiteQuery => {
                let result = is_bipartite(&context.graph);
                context.is_bipartite_result = Some(result.clone());
                context.witness = Some(result.witness);
            }
            Operation::BipartiteSetsQuery => {
                let result = bipartite_sets(&context.graph);
                context.bipartite_sets_result = Some(result.clone());
                context.witness = Some(result.witness);
            }
            Operation::CoreNumberQuery => {
                let result = core_number(&context.graph);
                context.core_number_result = Some(result.clone());
                context.witness = Some(result.witness);
            }
            Operation::KCoreQuery { k } => {
                let result = k_core(&context.graph, k);
                context.k_core_result = Some(result.clone());
                context.witness = Some(result.witness);
            }
            Operation::KShellQuery { k } => {
                let result = k_shell(&context.graph, k);
                context.k_shell_result = Some(result.clone());
                context.witness = Some(result.witness);
            }
            Operation::KCrustQuery { k } => {
                let result = k_crust(&context.graph, k);
                context.k_crust_result = Some(result.clone());
                context.witness = Some(result.witness);
            }
            Operation::KCoronaQuery { k } => {
                let result = k_corona(&context.graph, k);
                context.k_corona_result = Some(result.clone());
                context.witness = Some(result.witness);
            }
            Operation::AverageNeighborDegreeQuery => {
                let result = average_neighbor_degree(&context.graph);
                context.avg_neighbor_degree_result = Some(result.clone());
                context.witness = Some(result.witness);
            }
            Operation::DegreeAssortativityQuery => {
                let result = degree_assortativity_coefficient(&context.graph);
                context.degree_assortativity_result = Some(result.clone());
                context.witness = Some(result.witness);
            }
            Operation::VoterankQuery => {
                let result = voterank(&context.graph, None);
                context.voterank_result = Some(result.clone());
                context.witness = Some(result.witness);
            }
            Operation::FindCliquesQuery => {
                let result = fnx_algorithms::find_cliques(&context.graph);
                context.find_cliques_result = Some(result.clone());
                context.witness = Some(result.witness);
            }
            Operation::NodeConnectivityQuery { source, target } => {
                let result = fnx_algorithms::node_connectivity(&context.graph, &source, &target);
                context.node_connectivity_result = Some(result.clone());
                context.witness = Some(result.witness);
            }
            Operation::MinimumNodeCutQuery { source, target } => {
                let result = fnx_algorithms::minimum_node_cut(&context.graph, &source, &target);
                context.minimum_node_cut_result = Some(result.clone());
                context.witness = Some(result.witness);
            }
            Operation::GlobalNodeConnectivityQuery => {
                let result = fnx_algorithms::global_node_connectivity(&context.graph);
                context.global_node_connectivity_result = Some(result.clone());
                context.witness = Some(result.witness);
            }
            Operation::GlobalMinimumNodeCutQuery => {
                let result = fnx_algorithms::global_minimum_node_cut(&context.graph);
                context.global_minimum_node_cut_result = Some(result.clone());
                context.witness = Some(result.witness);
            }
            Operation::CycleBasisQuery => {
                let result = cycle_basis(&context.graph, None);
                context.cycle_basis_result = Some(result.clone());
                context.witness = Some(result.witness);
            }
            Operation::AllSimplePathsQuery { source, target } => {
                let result = all_simple_paths(&context.graph, &source, &target, None);
                context.all_simple_paths_result = Some(result.clone());
                context.witness = Some(result.witness);
            }
            Operation::GlobalEfficiencyQuery => {
                let result = global_efficiency(&context.graph);
                context.global_efficiency_result = Some(result.clone());
                context.witness = Some(result.witness);
            }
            Operation::LocalEfficiencyQuery => {
                let result = local_efficiency(&context.graph);
                context.local_efficiency_result = Some(result.clone());
                context.witness = Some(result.witness);
            }
            Operation::MinEdgeCoverQuery => {
                let result = min_edge_cover(&context.graph);
                context.min_edge_cover_result = result.clone();
                if let Some(ref r) = result {
                    context.witness = Some(r.witness.clone());
                }
            }
            Operation::IsEulerianQuery => {
                let result = fnx_algorithms::is_eulerian(&context.graph);
                context.is_eulerian_result = Some(result.clone());
                context.witness = Some(result.witness);
            }
            Operation::HasEulerianPathQuery => {
                let result = fnx_algorithms::has_eulerian_path(&context.graph);
                context.has_eulerian_path_result = Some(result.clone());
                context.witness = Some(result.witness);
            }
            Operation::IsSemieulerianQuery => {
                let result = fnx_algorithms::is_semieulerian(&context.graph);
                context.is_semieulerian_result = Some(result.clone());
                context.witness = Some(result.witness);
            }
            Operation::ClosenessVitalityQuery => {
                let result = fnx_algorithms::closeness_vitality(&context.graph);
                context.closeness_vitality_result = Some(result.clone());
                context.witness = Some(result.witness);
            }
            Operation::EulerianCircuitQuery { source } => {
                let result = fnx_algorithms::eulerian_circuit(&context.graph, source.as_deref());
                context.eulerian_circuit_result = result.clone();
                if let Some(ref r) = result {
                    context.witness = Some(r.witness.clone());
                }
            }
            Operation::EulerianPathQuery { source } => {
                let result = fnx_algorithms::eulerian_path(&context.graph, source.as_deref());
                context.eulerian_path_result = result.clone();
                if let Some(ref r) = result {
                    context.witness = Some(r.witness.clone());
                }
            }
            Operation::LouvainCommunitiesQuery {
                weight_attr,
                resolution,
                seed,
            } => {
                let result = fnx_algorithms::louvain_communities(
                    &context.graph,
                    resolution.unwrap_or(1.0),
                    &weight_attr,
                    1.0e-7,
                    None,
                    seed,
                );
                context.louvain_communities_result = Some(result);
            }
            Operation::ModularityQuery {
                communities,
                weight_attr,
            } => {
                let result =
                    fnx_algorithms::modularity(&context.graph, &communities, 1.0, &weight_attr);
                context.modularity_result = Some(result);
            }
            Operation::LabelPropagationCommunitiesQuery => {
                let result = fnx_algorithms::label_propagation_communities(&context.graph);
                context.label_propagation_communities_result = Some(result);
            }
            Operation::GreedyModularityCommunitiesQuery { weight_attr } => {
                let result = fnx_algorithms::greedy_modularity_communities(
                    &context.graph,
                    1.0,
                    &weight_attr,
                );
                context.greedy_modularity_communities_result = Some(result);
            }
            // Traversal operations
            Operation::DFSEdgesQuery {
                source,
                depth_limit,
            } => {
                let result = fnx_algorithms::dfs_edges(&context.graph, &source, depth_limit);
                context.dfs_edges_result = Some(result);
            }
            Operation::DFSPreorderNodesQuery {
                source,
                depth_limit,
            } => {
                let result =
                    fnx_algorithms::dfs_preorder_nodes(&context.graph, &source, depth_limit);
                context.dfs_preorder_nodes_result = Some(result);
            }
            Operation::DFSPostorderNodesQuery {
                source,
                depth_limit,
            } => {
                let result =
                    fnx_algorithms::dfs_postorder_nodes(&context.graph, &source, depth_limit);
                context.dfs_postorder_nodes_result = Some(result);
            }
            Operation::BFSEdgesQuery {
                source,
                depth_limit,
            } => {
                let result = fnx_algorithms::bfs_edges(&context.graph, &source, depth_limit);
                context.bfs_edges_result = Some(result);
            }
            Operation::BFSLayersQuery { source } => {
                let result = fnx_algorithms::bfs_layers(&context.graph, &source);
                context.bfs_layers_result = Some(result);
            }
            Operation::TopologicalSortQuery => {
                // Topological sort requires a DiGraph - convert from undirected for testing
                // In practice, this should only be called on DAGs represented as digraphs
                context.topological_sort_result = None; // Placeholder - requires DiGraph
            }
            // Link prediction operations
            Operation::JaccardCoefficientQuery { ebunch } => {
                let result = fnx_algorithms::jaccard_coefficient(&context.graph, &ebunch);
                context.jaccard_coefficient_result = Some(result);
            }
            Operation::AdamicAdarIndexQuery { ebunch } => {
                let result = fnx_algorithms::adamic_adar_index(&context.graph, &ebunch);
                context.adamic_adar_index_result = Some(result);
            }
            Operation::PreferentialAttachmentQuery { ebunch } => {
                let result = fnx_algorithms::preferential_attachment(&context.graph, &ebunch);
                context.preferential_attachment_result = Some(result);
            }
            Operation::ResourceAllocationIndexQuery { ebunch } => {
                let result = fnx_algorithms::resource_allocation_index(&context.graph, &ebunch);
                context.resource_allocation_index_result = Some(result);
            }
            // Isomorphism operations
            Operation::IsIsomorphicQuery { nodes2, edges2 } => {
                let graph2 = build_helper_graph_from_source(&context.graph, &nodes2, &edges2);
                let result = fnx_algorithms::is_isomorphic(&context.graph, &graph2);
                context.is_isomorphic_result = Some(result);
            }
            Operation::CouldBeIsomorphicQuery { nodes2, edges2 } => {
                let graph2 = build_helper_graph_from_source(&context.graph, &nodes2, &edges2);
                let result = fnx_algorithms::could_be_isomorphic(&context.graph, &graph2);
                context.could_be_isomorphic_result = Some(result);
            }
            Operation::FasterCouldBeIsomorphicQuery { nodes2, edges2 } => {
                let graph2 = build_helper_graph_from_source(&context.graph, &nodes2, &edges2);
                let result = fnx_algorithms::faster_could_be_isomorphic(&context.graph, &graph2);
                context.faster_could_be_isomorphic_result = Some(result);
            }
            // Graph metrics operations
            Operation::WienerIndexQuery => {
                let result = fnx_algorithms::wiener_index(&context.graph);
                context.wiener_index_result = Some(result);
            }
            Operation::GirthQuery => {
                let result = fnx_algorithms::girth(&context.graph);
                context.girth_result = Some(result);
            }
            Operation::DegreeAssortativityCoefficientQuery => {
                let result = fnx_algorithms::degree_assortativity_coefficient(&context.graph);
                context.degree_assortativity_coefficient_result = Some(result.coefficient);
            }
            Operation::SMetricQuery => {
                let result = fnx_algorithms::s_metric(&context.graph);
                context.s_metric_result = Some(result);
            }
            Operation::RichClubCoefficientQuery => {
                let result = fnx_algorithms::rich_club_coefficient(&context.graph);
                context.rich_club_coefficient_result = Some(result);
            }
            Operation::DispatchResolve {
                operation,
                requested_backend,
                required_features,
                risk_probability,
                unknown_incompatible_feature,
            } => {
                let decision = context.dispatch_registry.resolve(&DispatchRequest {
                    operation,
                    requested_backend,
                    required_features: required_features.into_iter().collect(),
                    risk_probability,
                    unknown_incompatible_feature,
                });
                match decision {
                    Ok(value) => context.dispatch_decision = Some(value),
                    Err(err) => mismatches.push(Mismatch {
                        category: "dispatch".to_owned(),
                        message: format!("dispatch failed: {err}"),
                    }),
                }
            }
            Operation::ConvertEdgeList { payload } => {
                let mut converter = GraphConverter::new(mode);
                match converter.from_edge_list(&payload) {
                    Ok(report) => {
                        context.warnings.extend(report.warnings);
                        context.graph = report.graph;
                    }
                    Err(err) => mismatches.push(Mismatch {
                        category: "convert".to_owned(),
                        message: format!("edge-list conversion failed: {err}"),
                    }),
                }
            }
            Operation::ConvertAdjacency { payload } => {
                let mut converter = GraphConverter::new(mode);
                match converter.from_adjacency(&payload) {
                    Ok(report) => {
                        context.warnings.extend(report.warnings);
                        context.graph = report.graph;
                    }
                    Err(err) => mismatches.push(Mismatch {
                        category: "convert".to_owned(),
                        message: format!("adjacency conversion failed: {err}"),
                    }),
                }
            }
            Operation::ReadEdgelist { input } => {
                let mut engine = EdgeListEngine::new(mode);
                match engine.read_edgelist(&input) {
                    Ok(report) => {
                        context.warnings.extend(report.warnings);
                        context.graph = report.graph;
                    }
                    Err(err) => mismatches.push(Mismatch {
                        category: "readwrite".to_owned(),
                        message: format!("read_edgelist failed: {err}"),
                    }),
                }
            }
            Operation::WriteEdgelist => {
                let mut engine = EdgeListEngine::new(mode);
                match engine.write_edgelist(&context.graph) {
                    Ok(text) => context.serialized_edgelist = Some(text),
                    Err(err) => mismatches.push(Mismatch {
                        category: "readwrite".to_owned(),
                        message: format!("write_edgelist failed: {err}"),
                    }),
                }
            }
            Operation::ReadAdjlist { input } => {
                let mut engine = EdgeListEngine::new(mode);
                match engine.read_adjlist(&input) {
                    Ok(report) => {
                        context.warnings.extend(report.warnings);
                        context.graph = report.graph;
                    }
                    Err(err) => mismatches.push(Mismatch {
                        category: "readwrite".to_owned(),
                        message: format!("read_adjlist failed: {err}"),
                    }),
                }
            }
            Operation::WriteAdjlist => {
                let mut engine = EdgeListEngine::new(mode);
                match engine.write_adjlist(&context.graph) {
                    Ok(text) => context.serialized_adjlist = Some(text),
                    Err(err) => mismatches.push(Mismatch {
                        category: "readwrite".to_owned(),
                        message: format!("write_adjlist failed: {err}"),
                    }),
                }
            }
            Operation::ReadJsonGraph { input } => {
                let mut engine = EdgeListEngine::new(mode);
                match engine.read_json_graph(&input) {
                    Ok(report) => {
                        context.warnings.extend(report.warnings);
                        context.graph = report.graph;
                    }
                    Err(err) => mismatches.push(Mismatch {
                        category: "readwrite".to_owned(),
                        message: format!("read_json_graph failed: {err}"),
                    }),
                }
            }
            Operation::WriteJsonGraph => {
                let mut engine = EdgeListEngine::new(mode);
                match engine.write_json_graph(&context.graph) {
                    Ok(text) => context.serialized_json_graph = Some(text),
                    Err(err) => mismatches.push(Mismatch {
                        category: "readwrite".to_owned(),
                        message: format!("write_json_graph failed: {err}"),
                    }),
                }
            }
            Operation::ReadGraphml { input } => {
                let mut engine = EdgeListEngine::new(mode);
                match engine.read_graphml(&input) {
                    Ok(report) => {
                        context.warnings.extend(report.warnings);
                        context.graph = report.graph;
                    }
                    Err(err) => mismatches.push(Mismatch {
                        category: "readwrite".to_owned(),
                        message: format!("read_graphml failed: {err}"),
                    }),
                }
            }
            Operation::WriteGraphml => {
                let mut engine = EdgeListEngine::new(mode);
                match engine.write_graphml(&context.graph) {
                    Ok(text) => context.serialized_graphml = Some(text),
                    Err(err) => mismatches.push(Mismatch {
                        category: "readwrite".to_owned(),
                        message: format!("write_graphml failed: {err}"),
                    }),
                }
            }
            Operation::ViewNeighborsQuery { node } => {
                let view = GraphView::new(&context.graph);
                context.view_neighbors_result = view.neighbors(&node).map(|neighbors| {
                    neighbors
                        .into_iter()
                        .map(str::to_owned)
                        .collect::<Vec<String>>()
                });
            }
            Operation::GeneratePathGraph { n } => {
                let mut generator = GraphGenerator::new(mode);
                match generator.path_graph(n) {
                    Ok(report) => {
                        context.warnings.extend(report.warnings);
                        context.graph = report.graph;
                    }
                    Err(err) => mismatches.push(Mismatch {
                        category: "generators".to_owned(),
                        message: format!("path_graph generation failed: {err}"),
                    }),
                }
            }
            Operation::GenerateStarGraph { n } => {
                let mut generator = GraphGenerator::new(mode);
                match generator.star_graph(n) {
                    Ok(report) => {
                        context.warnings.extend(report.warnings);
                        context.graph = report.graph;
                    }
                    Err(err) => mismatches.push(Mismatch {
                        category: "generators".to_owned(),
                        message: format!("star_graph generation failed: {err}"),
                    }),
                }
            }
            Operation::GenerateCycleGraph { n } => {
                let mut generator = GraphGenerator::new(mode);
                match generator.cycle_graph(n) {
                    Ok(report) => {
                        context.warnings.extend(report.warnings);
                        context.graph = report.graph;
                    }
                    Err(err) => mismatches.push(Mismatch {
                        category: "generators".to_owned(),
                        message: format!("cycle_graph generation failed: {err}"),
                    }),
                }
            }
            Operation::GenerateCompleteGraph { n } => {
                let mut generator = GraphGenerator::new(mode);
                match generator.complete_graph(n) {
                    Ok(report) => {
                        context.warnings.extend(report.warnings);
                        context.graph = report.graph;
                    }
                    Err(err) => mismatches.push(Mismatch {
                        category: "generators".to_owned(),
                        message: format!("complete_graph generation failed: {err}"),
                    }),
                }
            }
            Operation::GenerateEmptyGraph { n } => {
                let mut generator = GraphGenerator::new(mode);
                match generator.empty_graph(n) {
                    Ok(report) => {
                        context.warnings.extend(report.warnings);
                        context.graph = report.graph;
                    }
                    Err(err) => mismatches.push(Mismatch {
                        category: "generators".to_owned(),
                        message: format!("empty_graph generation failed: {err}"),
                    }),
                }
            }
            Operation::GenerateGnpRandomGraph { n, p, seed } => {
                let mut generator = GraphGenerator::new(mode);
                match generator.gnp_random_graph(n, p, seed) {
                    Ok(report) => {
                        context.warnings.extend(report.warnings);
                        context.graph = report.graph;
                    }
                    Err(err) => mismatches.push(Mismatch {
                        category: "generators".to_owned(),
                        message: format!("gnp_random_graph generation failed: {err}"),
                    }),
                }
            }
        }
    }

    if let Some(expected_graph) = &fixture.expected.graph {
        compare_nodes(&context.graph.snapshot(), expected_graph, &mut mismatches);
        compare_edges(&context.graph.snapshot(), expected_graph, &mut mismatches);
    }

    if let Some(expected_path) = fixture.expected.shortest_path_unweighted
        && context.shortest_path_result != Some(expected_path.clone())
    {
        mismatches.push(Mismatch {
            category: "algorithm".to_owned(),
            message: format!(
                "shortest_path_unweighted mismatch: expected {:?}, got {:?}",
                expected_path, context.shortest_path_result
            ),
        });
    }

    if let Some(expected_path) = fixture.expected.shortest_path_weighted
        && context.shortest_path_weighted_result != Some(expected_path.clone())
    {
        mismatches.push(Mismatch {
            category: "algorithm".to_owned(),
            message: format!(
                "shortest_path_weighted mismatch: expected {:?}, got {:?}",
                expected_path, context.shortest_path_weighted_result
            ),
        });
    }

    if let Some(expected_flow) = fixture.expected.max_flow_value {
        match context.max_flow_result {
            Some(actual_flow) if (actual_flow - expected_flow).abs() <= 1e-12 => {}
            Some(actual_flow) => mismatches.push(Mismatch {
                category: "algorithm_flow".to_owned(),
                message: format!(
                    "max_flow mismatch: expected {}, got {}",
                    expected_flow, actual_flow
                ),
            }),
            None => mismatches.push(Mismatch {
                category: "algorithm_flow".to_owned(),
                message: "expected max_flow result but none produced".to_owned(),
            }),
        }
    }

    if let Some(expected_cut) = fixture.expected.minimum_cut {
        match context.minimum_cut_result.as_ref() {
            Some(actual_cut) => {
                if (actual_cut.value - expected_cut.value).abs() > 1e-12 {
                    mismatches.push(Mismatch {
                        category: "algorithm_flow".to_owned(),
                        message: format!(
                            "minimum_cut value mismatch: expected {}, got {}",
                            expected_cut.value, actual_cut.value
                        ),
                    });
                }
                if actual_cut.source_partition != expected_cut.source_partition {
                    mismatches.push(Mismatch {
                        category: "algorithm_flow".to_owned(),
                        message: format!(
                            "minimum_cut source partition mismatch: expected {:?}, got {:?}",
                            expected_cut.source_partition, actual_cut.source_partition
                        ),
                    });
                }
                if actual_cut.sink_partition != expected_cut.sink_partition {
                    mismatches.push(Mismatch {
                        category: "algorithm_flow".to_owned(),
                        message: format!(
                            "minimum_cut sink partition mismatch: expected {:?}, got {:?}",
                            expected_cut.sink_partition, actual_cut.sink_partition
                        ),
                    });
                }
            }
            None => mismatches.push(Mismatch {
                category: "algorithm_flow".to_owned(),
                message: "expected minimum_cut result but none produced".to_owned(),
            }),
        }
    }

    if let Some(expected_cut) = fixture.expected.minimum_st_edge_cut {
        match context.minimum_st_edge_cut_result.as_ref() {
            Some(actual_cut) => {
                if (actual_cut.value - expected_cut.value).abs() > 1e-12 {
                    mismatches.push(Mismatch {
                        category: "algorithm_flow".to_owned(),
                        message: format!(
                            "minimum_st_edge_cut value mismatch: expected {}, got {}",
                            expected_cut.value, actual_cut.value
                        ),
                    });
                }
                if actual_cut.cut_edges != expected_cut.cut_edges {
                    mismatches.push(Mismatch {
                        category: "algorithm_flow".to_owned(),
                        message: format!(
                            "minimum_st_edge_cut edges mismatch: expected {:?}, got {:?}",
                            expected_cut.cut_edges, actual_cut.cut_edges
                        ),
                    });
                }
                if actual_cut.source_partition != expected_cut.source_partition {
                    mismatches.push(Mismatch {
                        category: "algorithm_flow".to_owned(),
                        message: format!(
                            "minimum_st_edge_cut source partition mismatch: expected {:?}, got {:?}",
                            expected_cut.source_partition, actual_cut.source_partition
                        ),
                    });
                }
                if actual_cut.sink_partition != expected_cut.sink_partition {
                    mismatches.push(Mismatch {
                        category: "algorithm_flow".to_owned(),
                        message: format!(
                            "minimum_st_edge_cut sink partition mismatch: expected {:?}, got {:?}",
                            expected_cut.sink_partition, actual_cut.sink_partition
                        ),
                    });
                }
            }
            None => mismatches.push(Mismatch {
                category: "algorithm_flow".to_owned(),
                message: "expected minimum_st_edge_cut result but none produced".to_owned(),
            }),
        }
    }

    if let Some(expected_value) = fixture.expected.edge_connectivity_value {
        match context.edge_connectivity_result {
            Some(actual_value) if (actual_value - expected_value).abs() <= 1e-12 => {}
            Some(actual_value) => mismatches.push(Mismatch {
                category: "algorithm_flow".to_owned(),
                message: format!(
                    "edge_connectivity mismatch: expected {}, got {}",
                    expected_value, actual_value
                ),
            }),
            None => mismatches.push(Mismatch {
                category: "algorithm_flow".to_owned(),
                message: "expected edge_connectivity result but none produced".to_owned(),
            }),
        }
    }

    if let Some(expected_value) = fixture.expected.global_edge_connectivity_value {
        match context.global_edge_connectivity_result {
            Some(actual_value) if (actual_value - expected_value).abs() <= 1e-12 => {}
            Some(actual_value) => mismatches.push(Mismatch {
                category: "algorithm_flow".to_owned(),
                message: format!(
                    "global_edge_connectivity mismatch: expected {}, got {}",
                    expected_value, actual_value
                ),
            }),
            None => mismatches.push(Mismatch {
                category: "algorithm_flow".to_owned(),
                message: "expected global_edge_connectivity result but none produced".to_owned(),
            }),
        }
    }

    if let Some(expected_cut) = fixture.expected.global_minimum_edge_cut {
        match context.global_minimum_edge_cut_result.as_ref() {
            Some(actual_cut) => {
                if (actual_cut.value - expected_cut.value).abs() > 1e-12 {
                    mismatches.push(Mismatch {
                        category: "algorithm_flow".to_owned(),
                        message: format!(
                            "global_minimum_edge_cut value mismatch: expected {}, got {}",
                            expected_cut.value, actual_cut.value
                        ),
                    });
                }
                if actual_cut.source != expected_cut.source {
                    mismatches.push(Mismatch {
                        category: "algorithm_flow".to_owned(),
                        message: format!(
                            "global_minimum_edge_cut source mismatch: expected {:?}, got {:?}",
                            expected_cut.source, actual_cut.source
                        ),
                    });
                }
                if actual_cut.sink != expected_cut.sink {
                    mismatches.push(Mismatch {
                        category: "algorithm_flow".to_owned(),
                        message: format!(
                            "global_minimum_edge_cut sink mismatch: expected {:?}, got {:?}",
                            expected_cut.sink, actual_cut.sink
                        ),
                    });
                }
                if actual_cut.cut_edges != expected_cut.cut_edges {
                    mismatches.push(Mismatch {
                        category: "algorithm_flow".to_owned(),
                        message: format!(
                            "global_minimum_edge_cut edges mismatch: expected {:?}, got {:?}",
                            expected_cut.cut_edges, actual_cut.cut_edges
                        ),
                    });
                }
                if actual_cut.source_partition != expected_cut.source_partition {
                    mismatches.push(Mismatch {
                        category: "algorithm_flow".to_owned(),
                        message: format!(
                            "global_minimum_edge_cut source partition mismatch: expected {:?}, got {:?}",
                            expected_cut.source_partition, actual_cut.source_partition
                        ),
                    });
                }
                if actual_cut.sink_partition != expected_cut.sink_partition {
                    mismatches.push(Mismatch {
                        category: "algorithm_flow".to_owned(),
                        message: format!(
                            "global_minimum_edge_cut sink partition mismatch: expected {:?}, got {:?}",
                            expected_cut.sink_partition, actual_cut.sink_partition
                        ),
                    });
                }
            }
            None => mismatches.push(Mismatch {
                category: "algorithm_flow".to_owned(),
                message: "expected global_minimum_edge_cut result but none produced".to_owned(),
            }),
        }
    }

    if let Some(expected_scores) = fixture.expected.betweenness_centrality {
        match context.betweenness_centrality_result.as_ref() {
            Some(actual_scores) => {
                compare_centrality_scores(
                    "betweenness_centrality",
                    actual_scores,
                    &expected_scores,
                    &mut mismatches,
                );
            }
            None => mismatches.push(Mismatch {
                category: "algorithm_centrality".to_owned(),
                message: "expected betweenness_centrality result but none produced".to_owned(),
            }),
        }
    }

    if let Some(expected_scores) = fixture.expected.edge_betweenness_centrality {
        match context.edge_betweenness_centrality_result.as_ref() {
            Some(actual_scores) => {
                compare_edge_centrality_scores(
                    "edge_betweenness_centrality",
                    actual_scores,
                    &expected_scores,
                    &mut mismatches,
                );
            }
            None => mismatches.push(Mismatch {
                category: "algorithm_centrality".to_owned(),
                message: "expected edge_betweenness_centrality result but none produced".to_owned(),
            }),
        }
    }

    if let Some(expected_scores) = fixture.expected.degree_centrality {
        match context.degree_centrality_result.as_ref() {
            Some(actual_scores) => {
                compare_degree_centrality(actual_scores, &expected_scores, &mut mismatches);
            }
            None => mismatches.push(Mismatch {
                category: "algorithm_centrality".to_owned(),
                message: "expected degree_centrality result but none produced".to_owned(),
            }),
        }
    }

    if let Some(expected_scores) = fixture.expected.closeness_centrality {
        match context.closeness_centrality_result.as_ref() {
            Some(actual_scores) => {
                compare_centrality_scores(
                    "closeness_centrality",
                    actual_scores,
                    &expected_scores,
                    &mut mismatches,
                );
            }
            None => mismatches.push(Mismatch {
                category: "algorithm_centrality".to_owned(),
                message: "expected closeness_centrality result but none produced".to_owned(),
            }),
        }
    }

    if let Some(expected_scores) = fixture.expected.harmonic_centrality {
        match context.harmonic_centrality_result.as_ref() {
            Some(actual_scores) => {
                compare_centrality_scores(
                    "harmonic_centrality",
                    actual_scores,
                    &expected_scores,
                    &mut mismatches,
                );
            }
            None => mismatches.push(Mismatch {
                category: "algorithm_centrality".to_owned(),
                message: "expected harmonic_centrality result but none produced".to_owned(),
            }),
        }
    }

    if let Some(expected_scores) = fixture.expected.katz_centrality {
        match context.katz_centrality_result.as_ref() {
            Some(actual_scores) => {
                compare_centrality_scores(
                    "katz_centrality",
                    actual_scores,
                    &expected_scores,
                    &mut mismatches,
                );
            }
            None => mismatches.push(Mismatch {
                category: "algorithm_centrality".to_owned(),
                message: "expected katz_centrality result but none produced".to_owned(),
            }),
        }
    }

    if let Some(expected_scores) = fixture.expected.hits_hubs {
        match context.hits_hubs_result.as_ref() {
            Some(actual_scores) => {
                compare_centrality_scores(
                    "hits_hubs",
                    actual_scores,
                    &expected_scores,
                    &mut mismatches,
                );
            }
            None => mismatches.push(Mismatch {
                category: "algorithm_centrality".to_owned(),
                message: "expected hits_hubs result but none produced".to_owned(),
            }),
        }
    }

    if let Some(expected_scores) = fixture.expected.hits_authorities {
        match context.hits_authorities_result.as_ref() {
            Some(actual_scores) => {
                compare_centrality_scores(
                    "hits_authorities",
                    actual_scores,
                    &expected_scores,
                    &mut mismatches,
                );
            }
            None => mismatches.push(Mismatch {
                category: "algorithm_centrality".to_owned(),
                message: "expected hits_authorities result but none produced".to_owned(),
            }),
        }
    }

    if let Some(expected_scores) = fixture.expected.pagerank {
        match context.pagerank_result.as_ref() {
            Some(actual_scores) => {
                compare_centrality_scores(
                    "pagerank",
                    actual_scores,
                    &expected_scores,
                    &mut mismatches,
                );
            }
            None => mismatches.push(Mismatch {
                category: "algorithm_centrality".to_owned(),
                message: "expected pagerank result but none produced".to_owned(),
            }),
        }
    }

    if let Some(expected_scores) = fixture.expected.eigenvector_centrality {
        match context.eigenvector_centrality_result.as_ref() {
            Some(actual_scores) => {
                compare_centrality_scores(
                    "eigenvector_centrality",
                    actual_scores,
                    &expected_scores,
                    &mut mismatches,
                );
            }
            None => mismatches.push(Mismatch {
                category: "algorithm_centrality".to_owned(),
                message: "expected eigenvector_centrality result but none produced".to_owned(),
            }),
        }
    }

    if let Some(expected_scores) = fixture.expected.clustering_coefficient {
        match context.clustering_coefficient_result.as_ref() {
            Some(actual_scores) => {
                compare_centrality_scores(
                    "clustering_coefficient",
                    actual_scores,
                    &expected_scores,
                    &mut mismatches,
                );
            }
            None => mismatches.push(Mismatch {
                category: "algorithm_centrality".to_owned(),
                message: "expected clustering_coefficient result but none produced".to_owned(),
            }),
        }
    }

    if let Some(expected_avg) = fixture.expected.average_clustering {
        match context.average_clustering_result {
            Some(actual_avg) => {
                if (actual_avg - expected_avg).abs() > 1e-12 {
                    mismatches.push(Mismatch {
                        category: "algorithm_centrality".to_owned(),
                        message: format!(
                            "average_clustering mismatch: expected {expected_avg}, got {actual_avg}"
                        ),
                    });
                }
            }
            None => mismatches.push(Mismatch {
                category: "algorithm_centrality".to_owned(),
                message: "expected average_clustering result but none produced".to_owned(),
            }),
        }
    }

    if let Some(expected_trans) = fixture.expected.transitivity {
        match context.transitivity_result {
            Some(actual_trans) => {
                if (actual_trans - expected_trans).abs() > 1e-12 {
                    mismatches.push(Mismatch {
                        category: "algorithm_centrality".to_owned(),
                        message: format!(
                            "transitivity mismatch: expected {expected_trans}, got {actual_trans}"
                        ),
                    });
                }
            }
            None => mismatches.push(Mismatch {
                category: "algorithm_centrality".to_owned(),
                message: "expected transitivity result but none produced".to_owned(),
            }),
        }
    }

    if let Some(expected_ecc) = fixture.expected.eccentricity.as_ref() {
        match context.distance_measures_result.as_ref() {
            Some(actual) => {
                let actual_map: std::collections::BTreeMap<&str, usize> = actual
                    .eccentricity
                    .iter()
                    .map(|e| (e.node.as_str(), e.value))
                    .collect();
                let expected_map: std::collections::BTreeMap<&str, usize> = expected_ecc
                    .iter()
                    .map(|e| (e.node.as_str(), e.value))
                    .collect();
                if actual_map != expected_map {
                    mismatches.push(Mismatch {
                        category: "algorithm_distance".to_owned(),
                        message: format!(
                            "eccentricity mismatch: expected {expected_map:?}, got {actual_map:?}"
                        ),
                    });
                }
            }
            None => mismatches.push(Mismatch {
                category: "algorithm_distance".to_owned(),
                message: "expected eccentricity result but none produced".to_owned(),
            }),
        }
    }

    if let Some(expected_diam) = fixture.expected.diameter {
        match context.distance_measures_result.as_ref() {
            Some(actual) => {
                if actual.diameter != expected_diam {
                    mismatches.push(Mismatch {
                        category: "algorithm_distance".to_owned(),
                        message: format!(
                            "diameter mismatch: expected {expected_diam}, got {}",
                            actual.diameter
                        ),
                    });
                }
            }
            None => mismatches.push(Mismatch {
                category: "algorithm_distance".to_owned(),
                message: "expected diameter result but none produced".to_owned(),
            }),
        }
    }

    if let Some(expected_rad) = fixture.expected.radius {
        match context.distance_measures_result.as_ref() {
            Some(actual) => {
                if actual.radius != expected_rad {
                    mismatches.push(Mismatch {
                        category: "algorithm_distance".to_owned(),
                        message: format!(
                            "radius mismatch: expected {expected_rad}, got {}",
                            actual.radius
                        ),
                    });
                }
            }
            None => mismatches.push(Mismatch {
                category: "algorithm_distance".to_owned(),
                message: "expected radius result but none produced".to_owned(),
            }),
        }
    }

    if let Some(expected_center) = fixture.expected.center.as_ref() {
        match context.distance_measures_result.as_ref() {
            Some(actual) => {
                let mut actual_sorted = actual.center.clone();
                actual_sorted.sort();
                let mut expected_sorted = expected_center.clone();
                expected_sorted.sort();
                if actual_sorted != expected_sorted {
                    mismatches.push(Mismatch {
                        category: "algorithm_distance".to_owned(),
                        message: format!(
                            "center mismatch: expected {expected_sorted:?}, got {actual_sorted:?}"
                        ),
                    });
                }
            }
            None => mismatches.push(Mismatch {
                category: "algorithm_distance".to_owned(),
                message: "expected center result but none produced".to_owned(),
            }),
        }
    }

    if let Some(expected_periphery) = fixture.expected.periphery.as_ref() {
        match context.distance_measures_result.as_ref() {
            Some(actual) => {
                let mut actual_sorted = actual.periphery.clone();
                actual_sorted.sort();
                let mut expected_sorted = expected_periphery.clone();
                expected_sorted.sort();
                if actual_sorted != expected_sorted {
                    mismatches.push(Mismatch {
                        category: "algorithm_distance".to_owned(),
                        message: format!(
                            "periphery mismatch: expected {expected_sorted:?}, got {actual_sorted:?}"
                        ),
                    });
                }
            }
            None => mismatches.push(Mismatch {
                category: "algorithm_distance".to_owned(),
                message: "expected periphery result but none produced".to_owned(),
            }),
        }
    }

    if let Some(expected_avg) = fixture.expected.average_shortest_path_length {
        match context.average_shortest_path_length_result.as_ref() {
            Some(actual) => {
                if (actual.average_shortest_path_length - expected_avg).abs() > 1e-12 {
                    mismatches.push(Mismatch {
                        category: "algorithm_distance".to_owned(),
                        message: format!(
                            "average_shortest_path_length mismatch: expected {expected_avg}, got {}",
                            actual.average_shortest_path_length
                        ),
                    });
                }
            }
            None => mismatches.push(Mismatch {
                category: "algorithm_distance".to_owned(),
                message: "expected average_shortest_path_length result but none produced"
                    .to_owned(),
            }),
        }
    }

    if let Some(expected_conn) = fixture.expected.is_connected {
        match context.is_connected_result.as_ref() {
            Some(actual) => {
                if actual.is_connected != expected_conn {
                    mismatches.push(Mismatch {
                        category: "algorithm_components".to_owned(),
                        message: format!(
                            "is_connected mismatch: expected {expected_conn}, got {}",
                            actual.is_connected
                        ),
                    });
                }
            }
            None => mismatches.push(Mismatch {
                category: "algorithm_components".to_owned(),
                message: "expected is_connected result but none produced".to_owned(),
            }),
        }
    }

    if let Some(expected_dens) = fixture.expected.density {
        match context.density_result.as_ref() {
            Some(actual) => {
                if (actual.density - expected_dens).abs() > 1e-12 {
                    mismatches.push(Mismatch {
                        category: "algorithm_components".to_owned(),
                        message: format!(
                            "density mismatch: expected {expected_dens}, got {}",
                            actual.density
                        ),
                    });
                }
            }
            None => mismatches.push(Mismatch {
                category: "algorithm_components".to_owned(),
                message: "expected density result but none produced".to_owned(),
            }),
        }
    }

    if let Some(expected_hp) = fixture.expected.has_path {
        match context.has_path_result.as_ref() {
            Some(actual) => {
                if actual.has_path != expected_hp {
                    mismatches.push(Mismatch {
                        category: "algorithm".to_owned(),
                        message: format!(
                            "has_path mismatch: expected {expected_hp}, got {}",
                            actual.has_path
                        ),
                    });
                }
            }
            None => mismatches.push(Mismatch {
                category: "algorithm".to_owned(),
                message: "expected has_path result but none produced".to_owned(),
            }),
        }
    }

    if let Some(expected_spl) = fixture.expected.shortest_path_length {
        match context.shortest_path_length_result.as_ref() {
            Some(actual) => {
                if actual.length != Some(expected_spl) {
                    mismatches.push(Mismatch {
                        category: "algorithm".to_owned(),
                        message: format!(
                            "shortest_path_length mismatch: expected Some({expected_spl}), got {:?}",
                            actual.length
                        ),
                    });
                }
            }
            None => mismatches.push(Mismatch {
                category: "algorithm".to_owned(),
                message: "expected shortest_path_length result but none produced".to_owned(),
            }),
        }
    }

    if let Some(expected_components) = fixture.expected.connected_components
        && context.connected_components_result != Some(expected_components.clone())
    {
        mismatches.push(Mismatch {
            category: "algorithm_components".to_owned(),
            message: format!(
                "connected_components mismatch: expected {:?}, got {:?}",
                expected_components, context.connected_components_result
            ),
        });
    }

    if let Some(expected_count) = fixture.expected.number_connected_components
        && context.number_connected_components_result != Some(expected_count)
    {
        mismatches.push(Mismatch {
            category: "algorithm_components".to_owned(),
            message: format!(
                "number_connected_components mismatch: expected {:?}, got {:?}",
                expected_count, context.number_connected_components_result
            ),
        });
    }

    if let Some(expected_nodes) = fixture.expected.articulation_points {
        match context.articulation_points_result.as_ref() {
            Some(actual_nodes) => {
                if actual_nodes != &expected_nodes {
                    mismatches.push(Mismatch {
                        category: "algorithm_structure".to_owned(),
                        message: format!(
                            "articulation_points mismatch: expected {expected_nodes:?}, got {actual_nodes:?}"
                        ),
                    });
                }
            }
            None => mismatches.push(Mismatch {
                category: "algorithm_structure".to_owned(),
                message: "expected articulation_points result but none produced".to_owned(),
            }),
        }
    }

    if let Some(expected_edges) = fixture.expected.bridges {
        match context.bridges_result.as_ref() {
            Some(actual_edges) => {
                if actual_edges != &expected_edges {
                    mismatches.push(Mismatch {
                        category: "algorithm_structure".to_owned(),
                        message: format!(
                            "bridges mismatch: expected {expected_edges:?}, got {actual_edges:?}"
                        ),
                    });
                }
            }
            None => mismatches.push(Mismatch {
                category: "algorithm_structure".to_owned(),
                message: "expected bridges result but none produced".to_owned(),
            }),
        }
    }

    if let Some(expected_distances) = fixture.expected.bellman_ford_distances {
        match context.bellman_ford_result.as_ref() {
            Some(actual) => {
                let actual_dists: Vec<(&str, f64)> = actual
                    .distances
                    .iter()
                    .map(|d| (d.node.as_str(), d.distance))
                    .collect();
                let expected_dists: Vec<(&str, f64)> = expected_distances
                    .iter()
                    .map(|d| (d.node.as_str(), d.distance))
                    .collect();
                for (exp_node, exp_dist) in &expected_dists {
                    let found = actual_dists.iter().find(|(n, _)| n == exp_node);
                    match found {
                        Some((_, actual_dist)) => {
                            if (actual_dist - exp_dist).abs() > 1e-9 {
                                mismatches.push(Mismatch {
                                    category: "algorithm_bellman_ford".to_owned(),
                                    message: format!(
                                        "bellman_ford distance mismatch for {exp_node}: expected {exp_dist}, got {actual_dist}"
                                    ),
                                });
                            }
                        }
                        None => {
                            mismatches.push(Mismatch {
                                category: "algorithm_bellman_ford".to_owned(),
                                message: format!(
                                    "bellman_ford missing distance for node {exp_node}"
                                ),
                            });
                        }
                    }
                }
            }
            None => mismatches.push(Mismatch {
                category: "algorithm_bellman_ford".to_owned(),
                message: "expected bellman_ford result but none produced".to_owned(),
            }),
        }
    }

    if let Some(expected_preds) = fixture.expected.bellman_ford_predecessors {
        match context.bellman_ford_result.as_ref() {
            Some(actual) => {
                for exp in &expected_preds {
                    let found = actual.predecessors.iter().find(|p| p.node == exp.node);
                    match found {
                        Some(actual_pred) => {
                            if actual_pred.predecessor != exp.predecessor {
                                mismatches.push(Mismatch {
                                    category: "algorithm_bellman_ford".to_owned(),
                                    message: format!(
                                        "bellman_ford predecessor mismatch for {}: expected {:?}, got {:?}",
                                        exp.node, exp.predecessor, actual_pred.predecessor
                                    ),
                                });
                            }
                        }
                        None => {
                            mismatches.push(Mismatch {
                                category: "algorithm_bellman_ford".to_owned(),
                                message: format!(
                                    "bellman_ford missing predecessor for node {}",
                                    exp.node
                                ),
                            });
                        }
                    }
                }
            }
            None => mismatches.push(Mismatch {
                category: "algorithm_bellman_ford".to_owned(),
                message: "expected bellman_ford predecessors but none produced".to_owned(),
            }),
        }
    }

    if let Some(expected_neg_cycle) = fixture.expected.bellman_ford_negative_cycle {
        match context.bellman_ford_result.as_ref() {
            Some(actual) => {
                if actual.negative_cycle_detected != expected_neg_cycle {
                    mismatches.push(Mismatch {
                        category: "algorithm_bellman_ford".to_owned(),
                        message: format!(
                            "bellman_ford negative_cycle mismatch: expected {expected_neg_cycle}, got {}",
                            actual.negative_cycle_detected
                        ),
                    });
                }
            }
            None => mismatches.push(Mismatch {
                category: "algorithm_bellman_ford".to_owned(),
                message: "expected bellman_ford negative_cycle but none produced".to_owned(),
            }),
        }
    }

    if let Some(expected_distances) = fixture.expected.multi_source_dijkstra_distances {
        match context.multi_source_dijkstra_result.as_ref() {
            Some(actual) => {
                for exp in &expected_distances {
                    let found = actual.distances.iter().find(|d| d.node == exp.node);
                    match found {
                        Some(actual_dist) => {
                            if (actual_dist.distance - exp.distance).abs() > 1e-9 {
                                mismatches.push(Mismatch {
                                    category: "algorithm_multi_source_dijkstra".to_owned(),
                                    message: format!(
                                        "multi_source_dijkstra distance mismatch for {}: expected {}, got {}",
                                        exp.node, exp.distance, actual_dist.distance
                                    ),
                                });
                            }
                        }
                        None => {
                            mismatches.push(Mismatch {
                                category: "algorithm_multi_source_dijkstra".to_owned(),
                                message: format!(
                                    "multi_source_dijkstra missing distance for node {}",
                                    exp.node
                                ),
                            });
                        }
                    }
                }
            }
            None => mismatches.push(Mismatch {
                category: "algorithm_multi_source_dijkstra".to_owned(),
                message: "expected multi_source_dijkstra distances but none produced".to_owned(),
            }),
        }
    }

    if let Some(expected_preds) = fixture.expected.multi_source_dijkstra_predecessors {
        match context.multi_source_dijkstra_result.as_ref() {
            Some(actual) => {
                for exp in &expected_preds {
                    let found = actual.predecessors.iter().find(|p| p.node == exp.node);
                    match found {
                        Some(actual_pred) => {
                            if actual_pred.predecessor != exp.predecessor {
                                mismatches.push(Mismatch {
                                    category: "algorithm_multi_source_dijkstra".to_owned(),
                                    message: format!(
                                        "multi_source_dijkstra predecessor mismatch for {}: expected {:?}, got {:?}",
                                        exp.node, exp.predecessor, actual_pred.predecessor
                                    ),
                                });
                            }
                        }
                        None => {
                            mismatches.push(Mismatch {
                                category: "algorithm_multi_source_dijkstra".to_owned(),
                                message: format!(
                                    "multi_source_dijkstra missing predecessor for node {}",
                                    exp.node
                                ),
                            });
                        }
                    }
                }
            }
            None => mismatches.push(Mismatch {
                category: "algorithm_multi_source_dijkstra".to_owned(),
                message: "expected multi_source_dijkstra predecessors but none produced".to_owned(),
            }),
        }
    }

    if let Some(expected_matching) = fixture.expected.maximal_matching {
        match context.maximal_matching_result.as_ref() {
            Some(actual) => {
                let mut actual_sorted = actual.matching.clone();
                actual_sorted.sort();
                let mut expected_sorted = expected_matching.clone();
                expected_sorted.sort();
                if actual_sorted != expected_sorted {
                    mismatches.push(Mismatch {
                        category: "algorithm_matching".to_owned(),
                        message: format!(
                            "maximal_matching mismatch: expected {expected_sorted:?}, got {actual_sorted:?}"
                        ),
                    });
                }
            }
            None => mismatches.push(Mismatch {
                category: "algorithm_matching".to_owned(),
                message: "expected maximal_matching result but none produced".to_owned(),
            }),
        }
    }

    if let Some(expected_wm) = fixture.expected.max_weight_matching {
        match context.max_weight_matching_result.as_ref() {
            Some(actual) => {
                let mut actual_sorted = actual.matching.clone();
                actual_sorted.sort();
                let mut expected_sorted = expected_wm.matching.clone();
                expected_sorted.sort();
                if actual_sorted != expected_sorted {
                    mismatches.push(Mismatch {
                        category: "algorithm_matching".to_owned(),
                        message: format!(
                            "max_weight_matching edges mismatch: expected {expected_sorted:?}, got {actual_sorted:?}"
                        ),
                    });
                }
                if (actual.total_weight - expected_wm.total_weight).abs() > 1e-9 {
                    mismatches.push(Mismatch {
                        category: "algorithm_matching".to_owned(),
                        message: format!(
                            "max_weight_matching total_weight mismatch: expected {}, got {}",
                            expected_wm.total_weight, actual.total_weight
                        ),
                    });
                }
            }
            None => mismatches.push(Mismatch {
                category: "algorithm_matching".to_owned(),
                message: "expected max_weight_matching result but none produced".to_owned(),
            }),
        }
    }

    if let Some(expected_wm) = fixture.expected.min_weight_matching {
        match context.min_weight_matching_result.as_ref() {
            Some(actual) => {
                let mut actual_sorted = actual.matching.clone();
                actual_sorted.sort();
                let mut expected_sorted = expected_wm.matching.clone();
                expected_sorted.sort();
                if actual_sorted != expected_sorted {
                    mismatches.push(Mismatch {
                        category: "algorithm_matching".to_owned(),
                        message: format!(
                            "min_weight_matching edges mismatch: expected {expected_sorted:?}, got {actual_sorted:?}"
                        ),
                    });
                }
                if (actual.total_weight - expected_wm.total_weight).abs() > 1e-9 {
                    mismatches.push(Mismatch {
                        category: "algorithm_matching".to_owned(),
                        message: format!(
                            "min_weight_matching total_weight mismatch: expected {}, got {}",
                            expected_wm.total_weight, actual.total_weight
                        ),
                    });
                }
            }
            None => mismatches.push(Mismatch {
                category: "algorithm_matching".to_owned(),
                message: "expected min_weight_matching result but none produced".to_owned(),
            }),
        }
    }

    if let Some(expected_mst) = fixture.expected.minimum_spanning_tree {
        match context.minimum_spanning_tree_result.as_ref() {
            Some(actual) => {
                let mut actual_edges: Vec<(String, String, f64)> = actual
                    .edges
                    .iter()
                    .map(|e| (e.left.clone(), e.right.clone(), e.weight))
                    .collect();
                actual_edges.sort_by(|a, b| a.0.cmp(&b.0).then_with(|| a.1.cmp(&b.1)));
                let mut expected_edges: Vec<(String, String, f64)> = expected_mst
                    .edges
                    .iter()
                    .map(|e| (e.left.clone(), e.right.clone(), e.weight))
                    .collect();
                expected_edges.sort_by(|a, b| a.0.cmp(&b.0).then_with(|| a.1.cmp(&b.1)));
                if actual_edges.len() != expected_edges.len() {
                    mismatches.push(Mismatch {
                        category: "algorithm_mst".to_owned(),
                        message: format!(
                            "minimum_spanning_tree edge count mismatch: expected {}, got {}",
                            expected_edges.len(),
                            actual_edges.len()
                        ),
                    });
                } else {
                    for (i, (a, e)) in actual_edges.iter().zip(expected_edges.iter()).enumerate() {
                        if a.0 != e.0 || a.1 != e.1 || (a.2 - e.2).abs() > 1e-9 {
                            mismatches.push(Mismatch {
                                category: "algorithm_mst".to_owned(),
                                message: format!(
                                    "minimum_spanning_tree edge {i} mismatch: expected ({}, {}, {}), got ({}, {}, {})",
                                    e.0, e.1, e.2, a.0, a.1, a.2
                                ),
                            });
                        }
                    }
                }
                if (actual.total_weight - expected_mst.total_weight).abs() > 1e-9 {
                    mismatches.push(Mismatch {
                        category: "algorithm_mst".to_owned(),
                        message: format!(
                            "minimum_spanning_tree total_weight mismatch: expected {}, got {}",
                            expected_mst.total_weight, actual.total_weight
                        ),
                    });
                }
            }
            None => mismatches.push(Mismatch {
                category: "algorithm_mst".to_owned(),
                message: "expected minimum_spanning_tree result but none produced".to_owned(),
            }),
        }
    }

    if let Some(expected_tri) = &fixture.expected.triangles {
        match context.triangles_result.as_ref() {
            Some(actual) => {
                let actual_map: BTreeMap<&str, usize> = actual
                    .triangles
                    .iter()
                    .map(|t| (t.node.as_str(), t.count))
                    .collect();
                let expected_map: BTreeMap<&str, usize> = expected_tri
                    .iter()
                    .map(|t| (t.node.as_str(), t.count))
                    .collect();
                if actual_map != expected_map {
                    mismatches.push(Mismatch {
                        category: "algorithm_triangles".to_owned(),
                        message: format!(
                            "triangles mismatch: expected {expected_map:?}, got {actual_map:?}"
                        ),
                    });
                }
            }
            None => mismatches.push(Mismatch {
                category: "algorithm_triangles".to_owned(),
                message: "expected triangles result but none produced".to_owned(),
            }),
        }
    }

    if let Some(expected_sq) = &fixture.expected.square_clustering {
        match context.square_clustering_result.as_ref() {
            Some(actual) => {
                let actual_map: BTreeMap<&str, &f64> = actual
                    .scores
                    .iter()
                    .map(|s| (s.node.as_str(), &s.score))
                    .collect();
                if actual.scores.len() != expected_sq.len() {
                    mismatches.push(Mismatch {
                        category: "algorithm_square_clustering".to_owned(),
                        message: format!(
                            "square_clustering node count mismatch: expected {}, got {}",
                            expected_sq.len(),
                            actual.scores.len()
                        ),
                    });
                }
                for exp in expected_sq {
                    match actual_map.get(exp.node.as_str()) {
                        Some(&&actual_score) => {
                            if (actual_score - exp.score).abs() > 1e-9 {
                                mismatches.push(Mismatch {
                                    category: "algorithm_square_clustering".to_owned(),
                                    message: format!(
                                        "square_clustering score mismatch for {}: expected {}, got {}",
                                        exp.node, exp.score, actual_score
                                    ),
                                });
                            }
                        }
                        None => mismatches.push(Mismatch {
                            category: "algorithm_square_clustering".to_owned(),
                            message: format!("square_clustering missing node {}", exp.node),
                        }),
                    }
                }
            }
            None => mismatches.push(Mismatch {
                category: "algorithm_square_clustering".to_owned(),
                message: "expected square_clustering result but none produced".to_owned(),
            }),
        }
    }

    if let Some(expected_is_tree) = fixture.expected.is_tree {
        match context.is_tree_result.as_ref() {
            Some(actual) => {
                if actual.is_tree != expected_is_tree {
                    mismatches.push(Mismatch {
                        category: "algorithm_structure".to_owned(),
                        message: format!(
                            "is_tree mismatch: expected {expected_is_tree}, got {}",
                            actual.is_tree
                        ),
                    });
                }
            }
            None => mismatches.push(Mismatch {
                category: "algorithm_structure".to_owned(),
                message: "expected is_tree result but none produced".to_owned(),
            }),
        }
    }

    if let Some(expected_is_forest) = fixture.expected.is_forest {
        match context.is_forest_result.as_ref() {
            Some(actual) => {
                if actual.is_forest != expected_is_forest {
                    mismatches.push(Mismatch {
                        category: "algorithm_structure".to_owned(),
                        message: format!(
                            "is_forest mismatch: expected {expected_is_forest}, got {}",
                            actual.is_forest
                        ),
                    });
                }
            }
            None => mismatches.push(Mismatch {
                category: "algorithm_structure".to_owned(),
                message: "expected is_forest result but none produced".to_owned(),
            }),
        }
    }

    if let Some(expected_coloring) = &fixture.expected.greedy_coloring {
        match context.greedy_color_result.as_ref() {
            Some(actual) => {
                let actual_map: BTreeMap<&str, usize> = actual
                    .coloring
                    .iter()
                    .map(|c| (c.node.as_str(), c.color))
                    .collect();
                let expected_map: BTreeMap<&str, usize> = expected_coloring
                    .iter()
                    .map(|c| (c.node.as_str(), c.color))
                    .collect();
                if actual_map != expected_map {
                    mismatches.push(Mismatch {
                        category: "algorithm_coloring".to_owned(),
                        message: format!(
                            "greedy_coloring mismatch: expected {expected_map:?}, got {actual_map:?}"
                        ),
                    });
                }
                if let Some(expected_nc) = fixture.expected.num_colors
                    && actual.num_colors != expected_nc
                {
                    mismatches.push(Mismatch {
                        category: "algorithm_coloring".to_owned(),
                        message: format!(
                            "num_colors mismatch: expected {expected_nc}, got {}",
                            actual.num_colors
                        ),
                    });
                }
            }
            None => mismatches.push(Mismatch {
                category: "algorithm_coloring".to_owned(),
                message: "expected greedy_coloring result but none produced".to_owned(),
            }),
        }
    }

    if let Some(expected_bip) = fixture.expected.is_bipartite {
        match context.is_bipartite_result.as_ref() {
            Some(actual) => {
                if actual.is_bipartite != expected_bip {
                    mismatches.push(Mismatch {
                        category: "algorithm_structure".to_owned(),
                        message: format!(
                            "is_bipartite mismatch: expected {expected_bip}, got {}",
                            actual.is_bipartite
                        ),
                    });
                }
            }
            None => mismatches.push(Mismatch {
                category: "algorithm_structure".to_owned(),
                message: "expected is_bipartite result but none produced".to_owned(),
            }),
        }
    }

    if let Some(expected_sets) = &fixture.expected.bipartite_sets {
        match context.bipartite_sets_result.as_ref() {
            Some(actual) => {
                if !actual.is_bipartite {
                    mismatches.push(Mismatch {
                        category: "algorithm_structure".to_owned(),
                        message: "bipartite_sets: graph reported as not bipartite".to_owned(),
                    });
                } else {
                    let mut actual_a = actual.set_a.clone();
                    let mut actual_b = actual.set_b.clone();
                    actual_a.sort();
                    actual_b.sort();
                    let mut expected_a = expected_sets.set_a.clone();
                    let mut expected_b = expected_sets.set_b.clone();
                    expected_a.sort();
                    expected_b.sort();
                    // Sets could be swapped (set_a <-> set_b), so check both orderings
                    let match_direct = actual_a == expected_a && actual_b == expected_b;
                    let match_swapped = actual_a == expected_b && actual_b == expected_a;
                    if !match_direct && !match_swapped {
                        mismatches.push(Mismatch {
                            category: "algorithm_structure".to_owned(),
                            message: format!(
                                "bipartite_sets mismatch: expected ({expected_a:?}, {expected_b:?}), got ({actual_a:?}, {actual_b:?})"
                            ),
                        });
                    }
                }
            }
            None => mismatches.push(Mismatch {
                category: "algorithm_structure".to_owned(),
                message: "expected bipartite_sets result but none produced".to_owned(),
            }),
        }
    }

    if let Some(expected_cores) = &fixture.expected.core_numbers {
        match context.core_number_result.as_ref() {
            Some(actual) => {
                let actual_map: BTreeMap<&str, usize> = actual
                    .core_numbers
                    .iter()
                    .map(|c| (c.node.as_str(), c.core))
                    .collect();
                let expected_map: BTreeMap<&str, usize> = expected_cores
                    .iter()
                    .map(|c| (c.node.as_str(), c.core))
                    .collect();
                if actual_map != expected_map {
                    mismatches.push(Mismatch {
                        category: "algorithm_core_number".to_owned(),
                        message: format!(
                            "core_number mismatch: expected {expected_map:?}, got {actual_map:?}"
                        ),
                    });
                }
            }
            None => mismatches.push(Mismatch {
                category: "algorithm_core_number".to_owned(),
                message: "expected core_number result but none produced".to_owned(),
            }),
        }
    }

    if let Some(expected_nodes) = &fixture.expected.k_core_nodes {
        match context.k_core_result.as_ref() {
            Some(actual) => {
                let mut actual_nodes: Vec<&str> = actual.nodes.iter().map(|s| s.as_str()).collect();
                actual_nodes.sort();
                let mut expected_sorted: Vec<&str> =
                    expected_nodes.iter().map(|s| s.as_str()).collect();
                expected_sorted.sort();
                if actual_nodes != expected_sorted {
                    mismatches.push(Mismatch {
                        category: "algorithm_k_core".to_owned(),
                        message: format!(
                            "k_core nodes mismatch: expected {expected_sorted:?}, got {actual_nodes:?}"
                        ),
                    });
                }
            }
            None => mismatches.push(Mismatch {
                category: "algorithm_k_core".to_owned(),
                message: "expected k_core result but none produced".to_owned(),
            }),
        }
    }

    if let Some(expected_nodes) = &fixture.expected.k_shell_nodes {
        match context.k_shell_result.as_ref() {
            Some(actual) => {
                let mut actual_nodes: Vec<&str> = actual.nodes.iter().map(|s| s.as_str()).collect();
                actual_nodes.sort();
                let mut expected_sorted: Vec<&str> =
                    expected_nodes.iter().map(|s| s.as_str()).collect();
                expected_sorted.sort();
                if actual_nodes != expected_sorted {
                    mismatches.push(Mismatch {
                        category: "algorithm_k_shell".to_owned(),
                        message: format!(
                            "k_shell nodes mismatch: expected {expected_sorted:?}, got {actual_nodes:?}"
                        ),
                    });
                }
            }
            None => mismatches.push(Mismatch {
                category: "algorithm_k_shell".to_owned(),
                message: "expected k_shell result but none produced".to_owned(),
            }),
        }
    }

    if let Some(expected_nodes) = &fixture.expected.k_crust_nodes {
        match context.k_crust_result.as_ref() {
            Some(actual) => {
                let mut actual_nodes: Vec<&str> = actual.nodes.iter().map(|s| s.as_str()).collect();
                actual_nodes.sort();
                let mut expected_sorted: Vec<&str> =
                    expected_nodes.iter().map(|s| s.as_str()).collect();
                expected_sorted.sort();
                if actual_nodes != expected_sorted {
                    mismatches.push(Mismatch {
                        category: "algorithm_k_crust".to_owned(),
                        message: format!(
                            "k_crust nodes mismatch: expected {expected_sorted:?}, got {actual_nodes:?}"
                        ),
                    });
                }
            }
            None => mismatches.push(Mismatch {
                category: "algorithm_k_crust".to_owned(),
                message: "expected k_crust result but none produced".to_owned(),
            }),
        }
    }

    if let Some(expected_nodes) = &fixture.expected.k_corona_nodes {
        match context.k_corona_result.as_ref() {
            Some(actual) => {
                let mut actual_nodes: Vec<&str> = actual.nodes.iter().map(|s| s.as_str()).collect();
                actual_nodes.sort();
                let mut expected_sorted: Vec<&str> =
                    expected_nodes.iter().map(|s| s.as_str()).collect();
                expected_sorted.sort();
                if actual_nodes != expected_sorted {
                    mismatches.push(Mismatch {
                        category: "algorithm_k_corona".to_owned(),
                        message: format!(
                            "k_corona nodes mismatch: expected {expected_sorted:?}, got {actual_nodes:?}"
                        ),
                    });
                }
            }
            None => mismatches.push(Mismatch {
                category: "algorithm_k_corona".to_owned(),
                message: "expected k_corona result but none produced".to_owned(),
            }),
        }
    }

    if let Some(expected_and) = &fixture.expected.average_neighbor_degree {
        match context.avg_neighbor_degree_result.as_ref() {
            Some(actual) => {
                let actual_map: BTreeMap<&str, f64> = actual
                    .scores
                    .iter()
                    .map(|s| (s.node.as_str(), s.avg_neighbor_degree))
                    .collect();
                for exp in expected_and {
                    match actual_map.get(exp.node.as_str()) {
                        Some(&actual_score) => {
                            if (actual_score - exp.avg_neighbor_degree).abs() > 1e-9 {
                                mismatches.push(Mismatch {
                                    category: "algorithm_avg_neighbor_degree".to_owned(),
                                    message: format!(
                                        "average_neighbor_degree mismatch for {}: expected {}, got {}",
                                        exp.node, exp.avg_neighbor_degree, actual_score
                                    ),
                                });
                            }
                        }
                        None => mismatches.push(Mismatch {
                            category: "algorithm_avg_neighbor_degree".to_owned(),
                            message: format!("average_neighbor_degree missing node {}", exp.node),
                        }),
                    }
                }
                if actual.scores.len() != expected_and.len() {
                    mismatches.push(Mismatch {
                        category: "algorithm_avg_neighbor_degree".to_owned(),
                        message: format!(
                            "average_neighbor_degree node count mismatch: expected {}, got {}",
                            expected_and.len(),
                            actual.scores.len()
                        ),
                    });
                }
            }
            None => mismatches.push(Mismatch {
                category: "algorithm_avg_neighbor_degree".to_owned(),
                message: "expected average_neighbor_degree result but none produced".to_owned(),
            }),
        }
    }

    if let Some(expected_r) = fixture.expected.degree_assortativity {
        match context.degree_assortativity_result.as_ref() {
            Some(actual) => {
                if (actual.coefficient - expected_r).abs() > 1e-9 {
                    mismatches.push(Mismatch {
                        category: "algorithm_assortativity".to_owned(),
                        message: format!(
                            "degree_assortativity mismatch: expected {expected_r}, got {}",
                            actual.coefficient
                        ),
                    });
                }
            }
            None => mismatches.push(Mismatch {
                category: "algorithm_assortativity".to_owned(),
                message: "expected degree_assortativity result but none produced".to_owned(),
            }),
        }
    }

    if let Some(expected_vr) = &fixture.expected.voterank {
        match context.voterank_result.as_ref() {
            Some(actual) => {
                if actual.ranked != *expected_vr {
                    mismatches.push(Mismatch {
                        category: "algorithm_voterank".to_owned(),
                        message: format!(
                            "voterank mismatch: expected {expected_vr:?}, got {:?}",
                            actual.ranked
                        ),
                    });
                }
            }
            None => mismatches.push(Mismatch {
                category: "algorithm_voterank".to_owned(),
                message: "expected voterank result but none produced".to_owned(),
            }),
        }
    }

    if let Some(expected_cliques) = &fixture.expected.cliques {
        match context.find_cliques_result.as_ref() {
            Some(actual) => {
                if actual.cliques != *expected_cliques {
                    mismatches.push(Mismatch {
                        category: "algorithm_cliques".to_owned(),
                        message: format!(
                            "cliques mismatch: expected {expected_cliques:?}, got {:?}",
                            actual.cliques
                        ),
                    });
                }
            }
            None => mismatches.push(Mismatch {
                category: "algorithm_cliques".to_owned(),
                message: "expected find_cliques result but none produced".to_owned(),
            }),
        }
    }

    if let Some(expected_cn) = fixture.expected.clique_number {
        match context.find_cliques_result.as_ref() {
            Some(actual) => {
                let actual_cn = actual.cliques.iter().map(|c| c.len()).max().unwrap_or(0);
                if actual_cn != expected_cn {
                    mismatches.push(Mismatch {
                        category: "algorithm_cliques".to_owned(),
                        message: format!(
                            "clique_number mismatch: expected {expected_cn}, got {actual_cn}"
                        ),
                    });
                }
            }
            None => mismatches.push(Mismatch {
                category: "algorithm_cliques".to_owned(),
                message: "expected clique_number result but none produced".to_owned(),
            }),
        }
    }

    if let Some(expected_nc) = fixture.expected.node_connectivity {
        match context.node_connectivity_result.as_ref() {
            Some(actual) => {
                if actual.value != expected_nc {
                    mismatches.push(Mismatch {
                        category: "algorithm_connectivity".to_owned(),
                        message: format!(
                            "node_connectivity mismatch: expected {expected_nc}, got {}",
                            actual.value
                        ),
                    });
                }
            }
            None => mismatches.push(Mismatch {
                category: "algorithm_connectivity".to_owned(),
                message: "expected node_connectivity result but none produced".to_owned(),
            }),
        }
    }

    if let Some(expected_mnc) = &fixture.expected.minimum_node_cut {
        match context.minimum_node_cut_result.as_ref() {
            Some(actual) => {
                let mut actual_sorted = actual.cut_nodes.clone();
                actual_sorted.sort();
                let mut expected_sorted = expected_mnc.clone();
                expected_sorted.sort();
                if actual_sorted != expected_sorted {
                    mismatches.push(Mismatch {
                        category: "algorithm_connectivity".to_owned(),
                        message: format!(
                            "minimum_node_cut mismatch: expected {expected_sorted:?}, got {actual_sorted:?}"
                        ),
                    });
                }
            }
            None => mismatches.push(Mismatch {
                category: "algorithm_connectivity".to_owned(),
                message: "expected minimum_node_cut result but none produced".to_owned(),
            }),
        }
    }

    if let Some(expected_gnc) = fixture.expected.global_node_connectivity {
        match context.global_node_connectivity_result.as_ref() {
            Some(actual) => {
                if actual.value != expected_gnc {
                    mismatches.push(Mismatch {
                        category: "algorithm_connectivity".to_owned(),
                        message: format!(
                            "global_node_connectivity mismatch: expected {expected_gnc}, got {}",
                            actual.value
                        ),
                    });
                }
            }
            None => mismatches.push(Mismatch {
                category: "algorithm_connectivity".to_owned(),
                message: "expected global_node_connectivity result but none produced".to_owned(),
            }),
        }
    }

    if let Some(expected_gmnc) = &fixture.expected.global_minimum_node_cut {
        match context.global_minimum_node_cut_result.as_ref() {
            Some(actual) => {
                let mut actual_sorted = actual.cut_nodes.clone();
                actual_sorted.sort();
                let mut expected_sorted = expected_gmnc.clone();
                expected_sorted.sort();
                if actual_sorted != expected_sorted {
                    mismatches.push(Mismatch {
                        category: "algorithm_connectivity".to_owned(),
                        message: format!(
                            "global_minimum_node_cut mismatch: expected {expected_sorted:?}, got {actual_sorted:?}"
                        ),
                    });
                }
            }
            None => mismatches.push(Mismatch {
                category: "algorithm_connectivity".to_owned(),
                message: "expected global_minimum_node_cut result but none produced".to_owned(),
            }),
        }
    }

    if let Some(expected_cycles) = &fixture.expected.cycle_basis {
        match context.cycle_basis_result.as_ref() {
            Some(actual) => {
                let mut actual_sorted: Vec<Vec<String>> = actual
                    .cycles
                    .iter()
                    .map(|c| {
                        let mut sorted = c.clone();
                        sorted.sort();
                        sorted
                    })
                    .collect();
                actual_sorted.sort();
                let mut expected_sorted: Vec<Vec<String>> = expected_cycles
                    .iter()
                    .map(|c| {
                        let mut sorted = c.clone();
                        sorted.sort();
                        sorted
                    })
                    .collect();
                expected_sorted.sort();
                if actual_sorted != expected_sorted {
                    mismatches.push(Mismatch {
                        category: "algorithm".to_owned(),
                        message: format!(
                            "cycle_basis mismatch: expected {expected_sorted:?}, got {actual_sorted:?}"
                        ),
                    });
                }
            }
            None => mismatches.push(Mismatch {
                category: "algorithm".to_owned(),
                message: "expected cycle_basis result but none produced".to_owned(),
            }),
        }
    }

    if let Some(expected_paths) = &fixture.expected.all_simple_paths {
        match context.all_simple_paths_result.as_ref() {
            Some(actual) => {
                let mut actual_sorted = actual.paths.clone();
                actual_sorted.sort();
                let mut expected_sorted = expected_paths.clone();
                expected_sorted.sort();
                if actual_sorted != expected_sorted {
                    mismatches.push(Mismatch {
                        category: "algorithm".to_owned(),
                        message: format!(
                            "all_simple_paths mismatch: expected {expected_sorted:?}, got {actual_sorted:?}"
                        ),
                    });
                }
            }
            None => mismatches.push(Mismatch {
                category: "algorithm".to_owned(),
                message: "expected all_simple_paths result but none produced".to_owned(),
            }),
        }
    }

    if let Some(expected_ge) = fixture.expected.global_efficiency {
        match context.global_efficiency_result.as_ref() {
            Some(actual) if (actual.efficiency - expected_ge).abs() <= 1e-6 => {}
            Some(actual) => mismatches.push(Mismatch {
                category: "algorithm".to_owned(),
                message: format!(
                    "global_efficiency mismatch: expected {expected_ge}, got {}",
                    actual.efficiency
                ),
            }),
            None => mismatches.push(Mismatch {
                category: "algorithm".to_owned(),
                message: "expected global_efficiency result but none produced".to_owned(),
            }),
        }
    }

    if let Some(expected_le) = fixture.expected.local_efficiency {
        match context.local_efficiency_result.as_ref() {
            Some(actual) if (actual.efficiency - expected_le).abs() <= 1e-6 => {}
            Some(actual) => mismatches.push(Mismatch {
                category: "algorithm".to_owned(),
                message: format!(
                    "local_efficiency mismatch: expected {expected_le}, got {}",
                    actual.efficiency
                ),
            }),
            None => mismatches.push(Mismatch {
                category: "algorithm".to_owned(),
                message: "expected local_efficiency result but none produced".to_owned(),
            }),
        }
    }

    if let Some(expected_cover) = &fixture.expected.min_edge_cover {
        match context.min_edge_cover_result.as_ref() {
            Some(actual) => {
                let mut actual_edges: Vec<(String, String)> = actual
                    .edges
                    .iter()
                    .map(|(l, r)| {
                        if l <= r {
                            (l.clone(), r.clone())
                        } else {
                            (r.clone(), l.clone())
                        }
                    })
                    .collect();
                actual_edges.sort();
                let mut expected_edges: Vec<(String, String)> = expected_cover
                    .iter()
                    .map(|e| {
                        if e.left <= e.right {
                            (e.left.clone(), e.right.clone())
                        } else {
                            (e.right.clone(), e.left.clone())
                        }
                    })
                    .collect();
                expected_edges.sort();
                if actual_edges != expected_edges {
                    mismatches.push(Mismatch {
                        category: "algorithm".to_owned(),
                        message: format!(
                            "min_edge_cover mismatch: expected {expected_edges:?}, got {actual_edges:?}"
                        ),
                    });
                }
            }
            None => mismatches.push(Mismatch {
                category: "algorithm".to_owned(),
                message: "expected min_edge_cover result but none produced".to_owned(),
            }),
        }
    }

    if let Some(expected_is_eul) = fixture.expected.is_eulerian {
        match context.is_eulerian_result.as_ref() {
            Some(actual) => {
                if actual.is_eulerian != expected_is_eul {
                    mismatches.push(Mismatch {
                        category: "algorithm_euler".to_owned(),
                        message: format!(
                            "is_eulerian mismatch: expected {expected_is_eul}, got {}",
                            actual.is_eulerian
                        ),
                    });
                }
            }
            None => mismatches.push(Mismatch {
                category: "algorithm_euler".to_owned(),
                message: "expected is_eulerian result but none produced".to_owned(),
            }),
        }
    }

    if let Some(expected_has_path) = fixture.expected.has_eulerian_path {
        match context.has_eulerian_path_result.as_ref() {
            Some(actual) => {
                if actual.has_eulerian_path != expected_has_path {
                    mismatches.push(Mismatch {
                        category: "algorithm_euler".to_owned(),
                        message: format!(
                            "has_eulerian_path mismatch: expected {expected_has_path}, got {}",
                            actual.has_eulerian_path
                        ),
                    });
                }
            }
            None => mismatches.push(Mismatch {
                category: "algorithm_euler".to_owned(),
                message: "expected has_eulerian_path result but none produced".to_owned(),
            }),
        }
    }

    if let Some(expected_is_semi) = fixture.expected.is_semieulerian {
        match context.is_semieulerian_result.as_ref() {
            Some(actual) => {
                if actual.is_semieulerian != expected_is_semi {
                    mismatches.push(Mismatch {
                        category: "algorithm_euler".to_owned(),
                        message: format!(
                            "is_semieulerian mismatch: expected {expected_is_semi}, got {}",
                            actual.is_semieulerian
                        ),
                    });
                }
            }
            None => mismatches.push(Mismatch {
                category: "algorithm_euler".to_owned(),
                message: "expected is_semieulerian result but none produced".to_owned(),
            }),
        }
    }

    if let Some(ref expected_vitality) = fixture.expected.closeness_vitality {
        match context.closeness_vitality_result.as_ref() {
            Some(actual) => {
                for ev in expected_vitality {
                    match actual.vitality.get(&ev.node) {
                        Some(&actual_val) => {
                            // Handle infinity comparisons
                            if ev.vitality.is_infinite() && actual_val.is_infinite() {
                                if ev.vitality.is_sign_positive() != actual_val.is_sign_positive() {
                                    mismatches.push(Mismatch {
                                        category: "algorithm_vitality".to_owned(),
                                        message: format!(
                                            "closeness_vitality sign mismatch for node {}: expected {}, got {}",
                                            ev.node, ev.vitality, actual_val
                                        ),
                                    });
                                }
                            } else if (ev.vitality - actual_val).abs() > 1e-6 {
                                mismatches.push(Mismatch {
                                    category: "algorithm_vitality".to_owned(),
                                    message: format!(
                                        "closeness_vitality mismatch for node {}: expected {}, got {}",
                                        ev.node, ev.vitality, actual_val
                                    ),
                                });
                            }
                        }
                        None => mismatches.push(Mismatch {
                            category: "algorithm_vitality".to_owned(),
                            message: format!(
                                "closeness_vitality missing result for node {}",
                                ev.node
                            ),
                        }),
                    }
                }
            }
            None => mismatches.push(Mismatch {
                category: "algorithm_vitality".to_owned(),
                message: "expected closeness_vitality result but none produced".to_owned(),
            }),
        }
    }

    if let Some(expected_count) = fixture.expected.eulerian_circuit_edge_count {
        match context.eulerian_circuit_result.as_ref() {
            Some(actual) => {
                if actual.edges.len() != expected_count {
                    mismatches.push(Mismatch {
                        category: "algorithm_euler".to_owned(),
                        message: format!(
                            "eulerian_circuit edge count mismatch: expected {expected_count}, got {}",
                            actual.edges.len()
                        ),
                    });
                }
                // Validate structural correctness: consecutive edges share endpoints
                for window in actual.edges.windows(2) {
                    if window[0].1 != window[1].0 {
                        mismatches.push(Mismatch {
                            category: "algorithm_euler".to_owned(),
                            message: format!(
                                "eulerian_circuit not consecutive: edge ({},{}) not followed by ({},{})",
                                window[0].0, window[0].1, window[1].0, window[1].1
                            ),
                        });
                        break;
                    }
                }
                // Validate circuit: starts and ends at same node
                if let (Some(first), Some(last)) = (actual.edges.first(), actual.edges.last())
                    && first.0 != last.1
                {
                    mismatches.push(Mismatch {
                        category: "algorithm_euler".to_owned(),
                        message: "eulerian_circuit does not form a cycle".to_owned(),
                    });
                }
            }
            None => mismatches.push(Mismatch {
                category: "algorithm_euler".to_owned(),
                message: "expected eulerian_circuit result but none produced".to_owned(),
            }),
        }
    }

    if let Some(ref expected_edges) = fixture.expected.eulerian_circuit {
        match context.eulerian_circuit_result.as_ref() {
            Some(actual) => {
                let expected_tuples: Vec<(String, String)> = expected_edges
                    .iter()
                    .map(|edge| (edge.left.clone(), edge.right.clone()))
                    .collect();
                if actual.edges != expected_tuples {
                    mismatches.push(Mismatch {
                        category: "algorithm_euler".to_owned(),
                        message: format!(
                            "eulerian_circuit mismatch: expected {:?}, got {:?}",
                            expected_tuples, actual.edges
                        ),
                    });
                }
            }
            None => mismatches.push(Mismatch {
                category: "algorithm_euler".to_owned(),
                message: "expected eulerian_circuit result but none produced".to_owned(),
            }),
        }
    }

    if let Some(expected_count) = fixture.expected.eulerian_path_edge_count {
        match context.eulerian_path_result.as_ref() {
            Some(actual) => {
                if actual.edges.len() != expected_count {
                    mismatches.push(Mismatch {
                        category: "algorithm_euler".to_owned(),
                        message: format!(
                            "eulerian_path edge count mismatch: expected {expected_count}, got {}",
                            actual.edges.len()
                        ),
                    });
                }
                // Validate structural correctness: consecutive edges share endpoints
                for window in actual.edges.windows(2) {
                    if window[0].1 != window[1].0 {
                        mismatches.push(Mismatch {
                            category: "algorithm_euler".to_owned(),
                            message: format!(
                                "eulerian_path not consecutive: edge ({},{}) not followed by ({},{})",
                                window[0].0, window[0].1, window[1].0, window[1].1
                            ),
                        });
                        break;
                    }
                }
            }
            None => mismatches.push(Mismatch {
                category: "algorithm_euler".to_owned(),
                message: "expected eulerian_path result but none produced".to_owned(),
            }),
        }
    }

    if let Some(ref expected_edges) = fixture.expected.eulerian_path {
        match context.eulerian_path_result.as_ref() {
            Some(actual) => {
                let expected_tuples: Vec<(String, String)> = expected_edges
                    .iter()
                    .map(|edge| (edge.left.clone(), edge.right.clone()))
                    .collect();
                if actual.edges != expected_tuples {
                    mismatches.push(Mismatch {
                        category: "algorithm_euler".to_owned(),
                        message: format!(
                            "eulerian_path mismatch: expected {:?}, got {:?}",
                            expected_tuples, actual.edges
                        ),
                    });
                }
            }
            None => mismatches.push(Mismatch {
                category: "algorithm_euler".to_owned(),
                message: "expected eulerian_path result but none produced".to_owned(),
            }),
        }
    }

    // Community detection comparisons
    if let Some(expected_count) = fixture.expected.louvain_communities_count {
        match context.louvain_communities_result.as_ref() {
            Some(actual) => {
                if actual.len() != expected_count {
                    mismatches.push(Mismatch {
                        category: "algorithm_community".to_owned(),
                        message: format!(
                            "louvain_communities count mismatch: expected {expected_count}, got {}",
                            actual.len()
                        ),
                    });
                }
            }
            None => mismatches.push(Mismatch {
                category: "algorithm_community".to_owned(),
                message: "expected louvain_communities result but none produced".to_owned(),
            }),
        }
    }

    if let Some(ref expected_modularity) = fixture.expected.modularity {
        match context.modularity_result {
            Some(actual) => {
                let diff = (actual - expected_modularity).abs();
                if diff > 1e-6 {
                    mismatches.push(Mismatch {
                        category: "algorithm_community".to_owned(),
                        message: format!(
                            "modularity mismatch: expected {expected_modularity}, got {actual}"
                        ),
                    });
                }
            }
            None => mismatches.push(Mismatch {
                category: "algorithm_community".to_owned(),
                message: "expected modularity result but none produced".to_owned(),
            }),
        }
    }

    if let Some(expected_count) = fixture.expected.label_propagation_communities_count {
        match context.label_propagation_communities_result.as_ref() {
            Some(actual) => {
                if actual.len() != expected_count {
                    mismatches.push(Mismatch {
                        category: "algorithm_community".to_owned(),
                        message: format!(
                            "label_propagation_communities count mismatch: expected {expected_count}, got {}",
                            actual.len()
                        ),
                    });
                }
            }
            None => mismatches.push(Mismatch {
                category: "algorithm_community".to_owned(),
                message: "expected label_propagation_communities result but none produced"
                    .to_owned(),
            }),
        }
    }

    if let Some(expected_count) = fixture.expected.greedy_modularity_communities_count {
        match context.greedy_modularity_communities_result.as_ref() {
            Some(actual) => {
                if actual.len() != expected_count {
                    mismatches.push(Mismatch {
                        category: "algorithm_community".to_owned(),
                        message: format!(
                            "greedy_modularity_communities count mismatch: expected {expected_count}, got {}",
                            actual.len()
                        ),
                    });
                }
            }
            None => mismatches.push(Mismatch {
                category: "algorithm_community".to_owned(),
                message: "expected greedy_modularity_communities result but none produced"
                    .to_owned(),
            }),
        }
    }

    // Traversal comparisons
    if let Some(ref expected_edges) = fixture.expected.dfs_edges {
        match context.dfs_edges_result.as_ref() {
            Some(actual) => {
                let expected_tuples: Vec<(String, String)> = expected_edges
                    .iter()
                    .map(|e| (e.left.clone(), e.right.clone()))
                    .collect();
                if *actual != expected_tuples {
                    mismatches.push(Mismatch {
                        category: "algorithm_traversal".to_owned(),
                        message: format!(
                            "dfs_edges mismatch: expected {:?}, got {:?}",
                            expected_tuples, actual
                        ),
                    });
                }
            }
            None => mismatches.push(Mismatch {
                category: "algorithm_traversal".to_owned(),
                message: "expected dfs_edges result but none produced".to_owned(),
            }),
        }
    }

    if let Some(ref expected_nodes) = fixture.expected.dfs_preorder_nodes {
        match context.dfs_preorder_nodes_result.as_ref() {
            Some(actual) => {
                if *actual != *expected_nodes {
                    mismatches.push(Mismatch {
                        category: "algorithm_traversal".to_owned(),
                        message: format!(
                            "dfs_preorder_nodes mismatch: expected {:?}, got {:?}",
                            expected_nodes, actual
                        ),
                    });
                }
            }
            None => mismatches.push(Mismatch {
                category: "algorithm_traversal".to_owned(),
                message: "expected dfs_preorder_nodes result but none produced".to_owned(),
            }),
        }
    }

    if let Some(ref expected_nodes) = fixture.expected.dfs_postorder_nodes {
        match context.dfs_postorder_nodes_result.as_ref() {
            Some(actual) => {
                if *actual != *expected_nodes {
                    mismatches.push(Mismatch {
                        category: "algorithm_traversal".to_owned(),
                        message: format!(
                            "dfs_postorder_nodes mismatch: expected {:?}, got {:?}",
                            expected_nodes, actual
                        ),
                    });
                }
            }
            None => mismatches.push(Mismatch {
                category: "algorithm_traversal".to_owned(),
                message: "expected dfs_postorder_nodes result but none produced".to_owned(),
            }),
        }
    }

    if let Some(ref expected_edges) = fixture.expected.bfs_edges {
        match context.bfs_edges_result.as_ref() {
            Some(actual) => {
                let expected_tuples: Vec<(String, String)> = expected_edges
                    .iter()
                    .map(|e| (e.left.clone(), e.right.clone()))
                    .collect();
                if *actual != expected_tuples {
                    mismatches.push(Mismatch {
                        category: "algorithm_traversal".to_owned(),
                        message: format!(
                            "bfs_edges mismatch: expected {:?}, got {:?}",
                            expected_tuples, actual
                        ),
                    });
                }
            }
            None => mismatches.push(Mismatch {
                category: "algorithm_traversal".to_owned(),
                message: "expected bfs_edges result but none produced".to_owned(),
            }),
        }
    }

    if let Some(ref expected_layers) = fixture.expected.bfs_layers {
        match context.bfs_layers_result.as_ref() {
            Some(actual) => {
                if *actual != *expected_layers {
                    mismatches.push(Mismatch {
                        category: "algorithm_traversal".to_owned(),
                        message: format!(
                            "bfs_layers mismatch: expected {:?}, got {:?}",
                            expected_layers, actual
                        ),
                    });
                }
            }
            None => mismatches.push(Mismatch {
                category: "algorithm_traversal".to_owned(),
                message: "expected bfs_layers result but none produced".to_owned(),
            }),
        }
    }

    if let Some(ref expected_order) = fixture.expected.topological_sort {
        match context.topological_sort_result.as_ref() {
            Some(actual) => {
                if *actual != *expected_order {
                    mismatches.push(Mismatch {
                        category: "algorithm_traversal".to_owned(),
                        message: format!(
                            "topological_sort mismatch: expected {:?}, got {:?}",
                            expected_order, actual
                        ),
                    });
                }
            }
            None => mismatches.push(Mismatch {
                category: "algorithm_traversal".to_owned(),
                message: "expected topological_sort result but none produced".to_owned(),
            }),
        }
    }

    // Link prediction comparisons
    if let Some(ref expected_scores) = fixture.expected.jaccard_coefficient {
        match context.jaccard_coefficient_result.as_ref() {
            Some(actual) => {
                for (i, expected) in expected_scores.iter().enumerate() {
                    if i >= actual.len() {
                        mismatches.push(Mismatch {
                            category: "algorithm_link_prediction".to_owned(),
                            message: format!(
                                "jaccard_coefficient: expected {} results, got {}",
                                expected_scores.len(),
                                actual.len()
                            ),
                        });
                        break;
                    }
                    let (u, v, score) = &actual[i];
                    if *u != expected.u || *v != expected.v {
                        mismatches.push(Mismatch {
                            category: "algorithm_link_prediction".to_owned(),
                            message: format!(
                                "jaccard_coefficient[{}]: expected pair ({}, {}), got ({}, {})",
                                i, expected.u, expected.v, u, v
                            ),
                        });
                    } else if (*score - expected.score).abs() > 1e-9 {
                        mismatches.push(Mismatch {
                            category: "algorithm_link_prediction".to_owned(),
                            message: format!(
                                "jaccard_coefficient[{}] ({}, {}): expected {}, got {}",
                                i, u, v, expected.score, score
                            ),
                        });
                    }
                }
            }
            None => mismatches.push(Mismatch {
                category: "algorithm_link_prediction".to_owned(),
                message: "expected jaccard_coefficient result but none produced".to_owned(),
            }),
        }
    }

    if let Some(ref expected_scores) = fixture.expected.adamic_adar_index {
        match context.adamic_adar_index_result.as_ref() {
            Some(actual) => {
                for (i, expected) in expected_scores.iter().enumerate() {
                    if i >= actual.len() {
                        mismatches.push(Mismatch {
                            category: "algorithm_link_prediction".to_owned(),
                            message: format!(
                                "adamic_adar_index: expected {} results, got {}",
                                expected_scores.len(),
                                actual.len()
                            ),
                        });
                        break;
                    }
                    let (u, v, score) = &actual[i];
                    if *u != expected.u || *v != expected.v {
                        mismatches.push(Mismatch {
                            category: "algorithm_link_prediction".to_owned(),
                            message: format!(
                                "adamic_adar_index[{}]: expected pair ({}, {}), got ({}, {})",
                                i, expected.u, expected.v, u, v
                            ),
                        });
                    } else if (*score - expected.score).abs() > 1e-9 {
                        mismatches.push(Mismatch {
                            category: "algorithm_link_prediction".to_owned(),
                            message: format!(
                                "adamic_adar_index[{}] ({}, {}): expected {}, got {}",
                                i, u, v, expected.score, score
                            ),
                        });
                    }
                }
            }
            None => mismatches.push(Mismatch {
                category: "algorithm_link_prediction".to_owned(),
                message: "expected adamic_adar_index result but none produced".to_owned(),
            }),
        }
    }

    if let Some(ref expected_scores) = fixture.expected.preferential_attachment {
        match context.preferential_attachment_result.as_ref() {
            Some(actual) => {
                for (i, expected) in expected_scores.iter().enumerate() {
                    if i >= actual.len() {
                        mismatches.push(Mismatch {
                            category: "algorithm_link_prediction".to_owned(),
                            message: format!(
                                "preferential_attachment: expected {} results, got {}",
                                expected_scores.len(),
                                actual.len()
                            ),
                        });
                        break;
                    }
                    let (u, v, score) = &actual[i];
                    if *u != expected.u || *v != expected.v {
                        mismatches.push(Mismatch {
                            category: "algorithm_link_prediction".to_owned(),
                            message: format!(
                                "preferential_attachment[{}]: expected pair ({}, {}), got ({}, {})",
                                i, expected.u, expected.v, u, v
                            ),
                        });
                    } else if (*score - expected.score).abs() > 1e-9 {
                        mismatches.push(Mismatch {
                            category: "algorithm_link_prediction".to_owned(),
                            message: format!(
                                "preferential_attachment[{}] ({}, {}): expected {}, got {}",
                                i, u, v, expected.score, score
                            ),
                        });
                    }
                }
            }
            None => mismatches.push(Mismatch {
                category: "algorithm_link_prediction".to_owned(),
                message: "expected preferential_attachment result but none produced".to_owned(),
            }),
        }
    }

    if let Some(ref expected_scores) = fixture.expected.resource_allocation_index {
        match context.resource_allocation_index_result.as_ref() {
            Some(actual) => {
                for (i, expected) in expected_scores.iter().enumerate() {
                    if i >= actual.len() {
                        mismatches.push(Mismatch {
                            category: "algorithm_link_prediction".to_owned(),
                            message: format!(
                                "resource_allocation_index: expected {} results, got {}",
                                expected_scores.len(),
                                actual.len()
                            ),
                        });
                        break;
                    }
                    let (u, v, score) = &actual[i];
                    if *u != expected.u || *v != expected.v {
                        mismatches.push(Mismatch {
                            category: "algorithm_link_prediction".to_owned(),
                            message: format!(
                                "resource_allocation_index[{}]: expected pair ({}, {}), got ({}, {})",
                                i, expected.u, expected.v, u, v
                            ),
                        });
                    } else if (*score - expected.score).abs() > 1e-9 {
                        mismatches.push(Mismatch {
                            category: "algorithm_link_prediction".to_owned(),
                            message: format!(
                                "resource_allocation_index[{}] ({}, {}): expected {}, got {}",
                                i, u, v, expected.score, score
                            ),
                        });
                    }
                }
            }
            None => mismatches.push(Mismatch {
                category: "algorithm_link_prediction".to_owned(),
                message: "expected resource_allocation_index result but none produced".to_owned(),
            }),
        }
    }

    // Isomorphism comparisons
    if let Some(expected) = fixture.expected.is_isomorphic {
        match context.is_isomorphic_result {
            Some(actual) => {
                if actual != expected {
                    mismatches.push(Mismatch {
                        category: "algorithm_isomorphism".to_owned(),
                        message: format!("is_isomorphic: expected {}, got {}", expected, actual),
                    });
                }
            }
            None => mismatches.push(Mismatch {
                category: "algorithm_isomorphism".to_owned(),
                message: "expected is_isomorphic result but none produced".to_owned(),
            }),
        }
    }

    if let Some(expected) = fixture.expected.could_be_isomorphic {
        match context.could_be_isomorphic_result {
            Some(actual) => {
                if actual != expected {
                    mismatches.push(Mismatch {
                        category: "algorithm_isomorphism".to_owned(),
                        message: format!(
                            "could_be_isomorphic: expected {}, got {}",
                            expected, actual
                        ),
                    });
                }
            }
            None => mismatches.push(Mismatch {
                category: "algorithm_isomorphism".to_owned(),
                message: "expected could_be_isomorphic result but none produced".to_owned(),
            }),
        }
    }

    if let Some(expected) = fixture.expected.faster_could_be_isomorphic {
        match context.faster_could_be_isomorphic_result {
            Some(actual) => {
                if actual != expected {
                    mismatches.push(Mismatch {
                        category: "algorithm_isomorphism".to_owned(),
                        message: format!(
                            "faster_could_be_isomorphic: expected {}, got {}",
                            expected, actual
                        ),
                    });
                }
            }
            None => mismatches.push(Mismatch {
                category: "algorithm_isomorphism".to_owned(),
                message: "expected faster_could_be_isomorphic result but none produced".to_owned(),
            }),
        }
    }

    // Graph metrics comparisons
    if let Some(expected) = fixture.expected.wiener_index {
        match context.wiener_index_result {
            Some(actual) => {
                let differs = actual.is_infinite() != expected.is_infinite()
                    || (!actual.is_infinite() && (actual - expected).abs() > 1e-9);
                if differs {
                    mismatches.push(Mismatch {
                        category: "algorithm_metrics".to_owned(),
                        message: format!("wiener_index: expected {}, got {}", expected, actual),
                    });
                }
            }
            None => mismatches.push(Mismatch {
                category: "algorithm_metrics".to_owned(),
                message: "expected wiener_index result but none produced".to_owned(),
            }),
        }
    }

    if let Some(expected) = fixture.expected.girth {
        match context.girth_result {
            Some(actual) => {
                if actual != expected {
                    mismatches.push(Mismatch {
                        category: "algorithm_metrics".to_owned(),
                        message: format!("girth: expected {:?}, got {:?}", expected, actual),
                    });
                }
            }
            None => mismatches.push(Mismatch {
                category: "algorithm_metrics".to_owned(),
                message: "expected girth result but none produced".to_owned(),
            }),
        }
    }

    if let Some(expected) = fixture.expected.degree_assortativity_coefficient {
        match context.degree_assortativity_coefficient_result {
            Some(actual) => {
                if (actual - expected).abs() > 1e-9 {
                    mismatches.push(Mismatch {
                        category: "algorithm_metrics".to_owned(),
                        message: format!(
                            "degree_assortativity_coefficient: expected {}, got {}",
                            expected, actual
                        ),
                    });
                }
            }
            None => mismatches.push(Mismatch {
                category: "algorithm_metrics".to_owned(),
                message: "expected degree_assortativity_coefficient result but none produced"
                    .to_owned(),
            }),
        }
    }

    if let Some(expected) = fixture.expected.s_metric {
        match context.s_metric_result {
            Some(actual) => {
                if (actual - expected).abs() > 1e-9 {
                    mismatches.push(Mismatch {
                        category: "algorithm_metrics".to_owned(),
                        message: format!("s_metric: expected {}, got {}", expected, actual),
                    });
                }
            }
            None => mismatches.push(Mismatch {
                category: "algorithm_metrics".to_owned(),
                message: "expected s_metric result but none produced".to_owned(),
            }),
        }
    }

    if let Some(ref expected_entries) = fixture.expected.rich_club_coefficient {
        match context.rich_club_coefficient_result.as_ref() {
            Some(actual) => {
                for entry in expected_entries {
                    match actual.get(&entry.k) {
                        Some(&actual_phi) => {
                            if (actual_phi - entry.phi).abs() > 1e-9 {
                                mismatches.push(Mismatch {
                                    category: "algorithm_metrics".to_owned(),
                                    message: format!(
                                        "rich_club_coefficient[k={}]: expected {}, got {}",
                                        entry.k, entry.phi, actual_phi
                                    ),
                                });
                            }
                        }
                        None => {
                            mismatches.push(Mismatch {
                                category: "algorithm_metrics".to_owned(),
                                message: format!(
                                    "rich_club_coefficient: missing entry for k={}",
                                    entry.k
                                ),
                            });
                        }
                    }
                }
            }
            None => mismatches.push(Mismatch {
                category: "algorithm_metrics".to_owned(),
                message: "expected rich_club_coefficient result but none produced".to_owned(),
            }),
        }
    }

    if let Some(expected_dispatch) = fixture.expected.dispatch {
        match context.dispatch_decision {
            Some(actual) => {
                if actual.selected_backend != expected_dispatch.selected_backend {
                    mismatches.push(Mismatch {
                        category: "dispatch".to_owned(),
                        message: format!(
                            "selected backend mismatch: expected {:?}, got {:?}",
                            expected_dispatch.selected_backend, actual.selected_backend
                        ),
                    });
                }
                if actual.action != expected_dispatch.action {
                    mismatches.push(Mismatch {
                        category: "dispatch".to_owned(),
                        message: format!(
                            "dispatch action mismatch: expected {:?}, got {:?}",
                            expected_dispatch.action, actual.action
                        ),
                    });
                }
            }
            None => mismatches.push(Mismatch {
                category: "dispatch".to_owned(),
                message: "expected dispatch decision but none produced".to_owned(),
            }),
        }
    }

    if let Some(expected_text) = fixture.expected.serialized_edgelist
        && context.serialized_edgelist.as_deref() != Some(expected_text.as_str())
    {
        mismatches.push(Mismatch {
            category: "readwrite".to_owned(),
            message: format!(
                "serialized edgelist mismatch: expected {:?}, got {:?}",
                expected_text, context.serialized_edgelist
            ),
        });
    }

    if let Some(expected_text) = fixture.expected.serialized_adjlist
        && context.serialized_adjlist.as_deref() != Some(expected_text.as_str())
    {
        mismatches.push(Mismatch {
            category: "readwrite".to_owned(),
            message: format!(
                "serialized adjlist mismatch: expected {:?}, got {:?}",
                expected_text, context.serialized_adjlist
            ),
        });
    }

    if let Some(expected_text) = fixture.expected.serialized_json_graph
        && context.serialized_json_graph.as_deref() != Some(expected_text.as_str())
    {
        mismatches.push(Mismatch {
            category: "readwrite".to_owned(),
            message: format!(
                "serialized json graph mismatch: expected {:?}, got {:?}",
                expected_text, context.serialized_json_graph
            ),
        });
    }

    if let Some(expected_text) = fixture.expected.serialized_graphml
        && context.serialized_graphml.as_deref() != Some(expected_text.as_str())
    {
        mismatches.push(Mismatch {
            category: "readwrite".to_owned(),
            message: format!(
                "serialized graphml mismatch: expected {:?}, got {:?}",
                expected_text, context.serialized_graphml
            ),
        });
    }

    if let Some(expected_neighbors) = fixture.expected.view_neighbors
        && context.view_neighbors_result != Some(expected_neighbors.clone())
    {
        mismatches.push(Mismatch {
            category: "views".to_owned(),
            message: format!(
                "view neighbors mismatch: expected {:?}, got {:?}",
                expected_neighbors, context.view_neighbors_result
            ),
        });
    }

    for expected_warning in fixture.expected.warnings_contains {
        if !context
            .warnings
            .iter()
            .any(|warning| warning.contains(&expected_warning))
        {
            mismatches.push(Mismatch {
                category: "warnings".to_owned(),
                message: format!("expected warning fragment not found: `{expected_warning}`"),
            });
        }
    }

    let mismatch_taxonomy =
        classify_mismatch_taxonomy(mode, &mismatches, &hardened_allowlisted_categories);
    let strict_violation_count = mismatch_taxonomy
        .iter()
        .filter(|row| row.classification == MismatchClassification::StrictViolation)
        .count();
    let hardened_allowlisted_count = mismatch_taxonomy
        .iter()
        .filter(|row| row.classification == MismatchClassification::HardenedAllowlisted)
        .count();
    let passed = strict_violation_count == 0;
    let reason_code = if strict_violation_count > 0 {
        Some("mismatch".to_owned())
    } else if hardened_allowlisted_count > 0 {
        Some("hardened_allowlisted_mismatch".to_owned())
    } else {
        None
    };

    FixtureReport {
        fixture_id,
        fixture_name,
        suite: fixture.suite,
        mode,
        seed,
        threat_class,
        replay_command,
        passed,
        reason_code,
        fixture_source_hash,
        duration_ms: fixture_start.elapsed().as_millis(),
        strict_violation_count,
        hardened_allowlisted_count,
        mismatches,
        mismatch_taxonomy,
        witness: context.witness,
    }
}

fn compare_nodes(
    snapshot: &GraphSnapshot,
    expected: &GraphSnapshotExpectation,
    mismatches: &mut Vec<Mismatch>,
) {
    if snapshot.nodes != expected.nodes {
        mismatches.push(Mismatch {
            category: "graph_nodes".to_owned(),
            message: format!(
                "node ordering mismatch: expected {:?}, got {:?}",
                expected.nodes, snapshot.nodes
            ),
        });
    }
}

fn compare_edges(
    snapshot: &GraphSnapshot,
    expected: &GraphSnapshotExpectation,
    mismatches: &mut Vec<Mismatch>,
) {
    if snapshot.edges != expected.edges {
        mismatches.push(Mismatch {
            category: "graph_edges".to_owned(),
            message: format!(
                "edge snapshot mismatch: expected {:?}, got {:?}",
                expected.edges, snapshot.edges
            ),
        });
    }
}

fn default_dispatch_registry(mode: CompatibilityMode) -> BackendRegistry {
    let mut registry = BackendRegistry::new(mode);
    registry.register_backend(BackendSpec {
        name: "native".to_owned(),
        priority: 100,
        supported_features: set([
            "shortest_path",
            "shortest_path_weighted",
            "max_flow",
            "minimum_cut",
            "minimum_st_edge_cut",
            "edge_connectivity",
            "global_edge_connectivity",
            "global_minimum_edge_cut",
            "convert_edge_list",
            "convert_adjacency",
            "read_edgelist",
            "write_edgelist",
            "read_adjlist",
            "write_adjlist",
            "read_json_graph",
            "write_json_graph",
            "read_graphml",
            "write_graphml",
            "connected_components",
            "number_connected_components",
            "betweenness_centrality",
            "edge_betweenness_centrality",
            "degree_centrality",
            "closeness_centrality",
            "harmonic_centrality",
            "katz_centrality",
            "hits_centrality",
            "pagerank",
            "eigenvector_centrality",
            "clustering_coefficient",
            "distance_measures",
            "average_shortest_path_length",
            "is_connected",
            "density",
            "has_path",
            "shortest_path_length",
            "generate_path_graph",
            "generate_star_graph",
            "generate_cycle_graph",
            "generate_complete_graph",
            "generate_empty_graph",
            "generate_gnp_random_graph",
            "bellman_ford",
            "multi_source_dijkstra",
            "maximal_matching",
            "max_weight_matching",
            "min_weight_matching",
            "minimum_spanning_tree",
            "triangles",
            "square_clustering",
            "is_tree",
            "is_forest",
            "greedy_color",
            "is_bipartite",
            "bipartite_sets",
            "core_number",
            "average_neighbor_degree",
            "degree_assortativity",
            "voterank",
            "find_cliques",
            "node_connectivity",
            "minimum_node_cut",
            "global_node_connectivity",
            "global_minimum_node_cut",
            "cycle_basis",
            "all_simple_paths",
            "global_efficiency",
            "local_efficiency",
            "min_edge_cover",
            "is_eulerian",
            "has_eulerian_path",
            "is_semieulerian",
            "eulerian_circuit",
            "eulerian_path",
        ]),
        allow_in_strict: true,
        allow_in_hardened: true,
    });
    registry.register_backend(BackendSpec {
        name: "compat_probe".to_owned(),
        priority: 50,
        supported_features: set(["shortest_path", "shortest_path_weighted"]),
        allow_in_strict: true,
        allow_in_hardened: true,
    });
    registry
}

fn set<const N: usize>(values: [&str; N]) -> BTreeSet<String> {
    values.into_iter().map(str::to_owned).collect()
}

fn compare_degree_centrality(
    actual: &[CentralityScore],
    expected: &[ExpectedCentralityScore],
    mismatches: &mut Vec<Mismatch>,
) {
    compare_centrality_scores("degree_centrality", actual, expected, mismatches);
}

fn centrality_score_tolerance(label: &str) -> f64 {
    match label {
        "hits_hubs" | "hits_authorities" => 1e-9,
        _ => 1e-12,
    }
}

fn compare_centrality_scores(
    label: &str,
    actual: &[CentralityScore],
    expected: &[ExpectedCentralityScore],
    mismatches: &mut Vec<Mismatch>,
) {
    let tolerance = centrality_score_tolerance(label);

    if actual.len() != expected.len() {
        mismatches.push(Mismatch {
            category: "algorithm_centrality".to_owned(),
            message: format!(
                "{label} length mismatch: expected {}, got {}",
                expected.len(),
                actual.len()
            ),
        });
        return;
    }

    for (idx, (actual_score, expected_score)) in actual.iter().zip(expected.iter()).enumerate() {
        if actual_score.node != expected_score.node {
            mismatches.push(Mismatch {
                category: "algorithm_centrality".to_owned(),
                message: format!(
                    "{label} node mismatch at index {idx}: expected {:?}, got {:?}",
                    expected_score.node, actual_score.node
                ),
            });
        }
        if (actual_score.score - expected_score.score).abs() > tolerance {
            mismatches.push(Mismatch {
                category: "algorithm_centrality".to_owned(),
                message: format!(
                    "{label} score mismatch for node {}: expected {}, got {}",
                    expected_score.node, expected_score.score, actual_score.score
                ),
            });
        }
    }
}

fn compare_edge_centrality_scores(
    label: &str,
    actual: &[EdgeCentralityScore],
    expected: &[ExpectedEdgeCentralityScore],
    mismatches: &mut Vec<Mismatch>,
) {
    if actual.len() != expected.len() {
        mismatches.push(Mismatch {
            category: "algorithm_centrality".to_owned(),
            message: format!(
                "{label} length mismatch: expected {}, got {}",
                expected.len(),
                actual.len()
            ),
        });
        return;
    }

    for (idx, (actual_score, expected_score)) in actual.iter().zip(expected.iter()).enumerate() {
        if actual_score.left != expected_score.left || actual_score.right != expected_score.right {
            mismatches.push(Mismatch {
                category: "algorithm_centrality".to_owned(),
                message: format!(
                    "{label} edge mismatch at index {idx}: expected ({}, {}), got ({}, {})",
                    expected_score.left,
                    expected_score.right,
                    actual_score.left,
                    actual_score.right
                ),
            });
        }
        if (actual_score.score - expected_score.score).abs() > 1e-12 {
            mismatches.push(Mismatch {
                category: "algorithm_centrality".to_owned(),
                message: format!(
                    "{label} score mismatch for edge ({}, {}): expected {}, got {}",
                    expected_score.left,
                    expected_score.right,
                    expected_score.score,
                    actual_score.score
                ),
            });
        }
    }
}

// ---------------------------------------------------------------------------
// Python parity cross-walk — B9
// ---------------------------------------------------------------------------

/// A Python parity test record emitted by pytest (conftest.py ParityRecordEmitter).
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct PythonParityRecord {
    pub fixture_id: String,
    pub fixture_name: String,
    #[serde(default = "default_python_parity_suite")]
    pub suite: String,
    #[serde(default = "default_strict_mode")]
    pub mode: String,
    pub seed: Option<u64>,
    pub threat_class: Option<String>,
    #[serde(default)]
    pub replay_command: String,
    #[serde(default = "default_passed")]
    pub passed: bool,
    pub reason_code: Option<String>,
    #[serde(default)]
    pub fixture_source_hash: String,
    #[serde(default)]
    pub duration_ms: u64,
    #[serde(default)]
    pub strict_violation_count: usize,
    #[serde(default)]
    pub hardened_allowlisted_count: usize,
    #[serde(default)]
    pub mismatches: Vec<Mismatch>,
    #[serde(default)]
    pub mismatch_taxonomy: Vec<TaxonomyMismatch>,
    pub witness: Option<ComplexityWitness>,
    #[serde(default)]
    pub python_module: String,
    #[serde(default)]
    pub python_markers: Vec<String>,
    #[serde(default = "default_schema_version")]
    pub schema_version: String,
}

fn default_python_parity_suite() -> String {
    "python_parity".to_owned()
}

fn default_strict_mode() -> String {
    "strict".to_owned()
}

fn default_passed() -> bool {
    true
}

fn default_schema_version() -> String {
    "python_parity_v1".to_owned()
}

impl PythonParityRecord {
    /// Convert to a FixtureReport for unified reporting.
    pub fn to_fixture_report(&self) -> FixtureReport {
        let mode = match self.mode.as_str() {
            "hardened" => CompatibilityMode::Hardened,
            _ => CompatibilityMode::Strict,
        };
        FixtureReport {
            fixture_id: self.fixture_id.clone(),
            fixture_name: self.fixture_name.clone(),
            suite: self.suite.clone(),
            mode,
            seed: self.seed,
            threat_class: self.threat_class.clone(),
            replay_command: self.replay_command.clone(),
            passed: self.passed,
            reason_code: self.reason_code.clone(),
            fixture_source_hash: self.fixture_source_hash.clone(),
            duration_ms: u128::from(self.duration_ms),
            strict_violation_count: self.strict_violation_count,
            hardened_allowlisted_count: self.hardened_allowlisted_count,
            mismatches: self.mismatches.clone(),
            mismatch_taxonomy: self.mismatch_taxonomy.clone(),
            witness: self.witness.clone(),
        }
    }
}

/// Cross-walk report combining Rust conformance results with Python parity records.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct CrossWalkReport {
    pub schema_version: String,
    pub generated_at_unix_ms: u128,
    pub rust_fixture_count: usize,
    pub python_parity_count: usize,
    pub rust_mismatch_count: usize,
    pub python_mismatch_count: usize,
    pub combined_fixture_ids: Vec<String>,
    pub rust_only_fixture_ids: Vec<String>,
    pub python_only_fixture_ids: Vec<String>,
    pub unified_reports: Vec<FixtureReport>,
}

impl CrossWalkReport {
    pub const SCHEMA_VERSION: &'static str = "crosswalk_v1";
}

/// Load Python parity records from a JSONL file.
pub fn load_python_parity_records(path: &Path) -> io::Result<Vec<PythonParityRecord>> {
    let content = fs::read_to_string(path)?;
    let mut records = Vec::new();
    for line in content.lines() {
        if line.trim().is_empty() {
            continue;
        }
        match serde_json::from_str::<PythonParityRecord>(line) {
            Ok(record) => records.push(record),
            Err(e) => {
                eprintln!("Warning: failed to parse parity record: {e}");
            }
        }
    }
    Ok(records)
}

/// Build a cross-walk report from Rust fixture reports and Python parity records.
pub fn build_crosswalk_report(
    rust_reports: &[FixtureReport],
    python_records: &[PythonParityRecord],
) -> CrossWalkReport {
    let rust_ids: BTreeSet<_> = rust_reports.iter().map(|r| r.fixture_id.clone()).collect();
    let python_ids: BTreeSet<_> = python_records
        .iter()
        .map(|r| r.fixture_id.clone())
        .collect();

    let combined: BTreeSet<_> = rust_ids.intersection(&python_ids).cloned().collect();
    let rust_only: Vec<_> = rust_ids.difference(&python_ids).cloned().collect();
    let python_only: Vec<_> = python_ids.difference(&rust_ids).cloned().collect();

    let mut unified: Vec<FixtureReport> = rust_reports.to_vec();
    for py_record in python_records {
        if !rust_ids.contains(&py_record.fixture_id) {
            unified.push(py_record.to_fixture_report());
        }
    }
    unified.sort_by(|a, b| a.fixture_id.cmp(&b.fixture_id));

    let rust_mismatch_count = rust_reports.iter().filter(|r| !r.passed).count();
    let python_mismatch_count = python_records.iter().filter(|r| !r.passed).count();

    CrossWalkReport {
        schema_version: CrossWalkReport::SCHEMA_VERSION.to_owned(),
        generated_at_unix_ms: unix_time_ms(),
        rust_fixture_count: rust_reports.len(),
        python_parity_count: python_records.len(),
        rust_mismatch_count,
        python_mismatch_count,
        combined_fixture_ids: combined.into_iter().collect(),
        rust_only_fixture_ids: rust_only,
        python_only_fixture_ids: python_only,
        unified_reports: unified,
    }
}

/// Run cross-walk: load Python parity records and merge with Rust harness results.
pub fn run_crosswalk(
    rust_report: &HarnessReport,
    python_parity_path: &Path,
) -> io::Result<CrossWalkReport> {
    let python_records = load_python_parity_records(python_parity_path)?;
    Ok(build_crosswalk_report(
        &rust_report.fixture_reports,
        &python_records,
    ))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn smoke_harness_reports_zero_drift_for_bootstrap_fixtures() {
        let mut cfg = HarnessConfig::default_paths();
        cfg.report_root = None;
        let report = run_smoke(&cfg);
        assert!(report.oracle_present, "oracle repo should be present");
        assert!(report.fixture_count >= 1, "expected at least one fixture");
        if report.mismatch_count > 0 {
            for log in &report.fixture_reports {
                if !log.mismatches.is_empty() {
                    println!(
                        "Fixture {} failed with {} errors: {:#?}",
                        log.fixture_id,
                        log.mismatches.len(),
                        log.mismatches
                    );
                }
            }
        }
        assert_eq!(report.mismatch_count, 0, "fixtures should be drift-free");
        assert_eq!(report.structured_log_count, report.fixture_count);
    }

    #[test]
    fn test_python_parity_record_deserialize() {
        let json = r#"{
            "fixture_id": "py-abcd1234",
            "fixture_name": "test_example",
            "suite": "python_parity",
            "mode": "strict",
            "passed": true,
            "duration_ms": 42
        }"#;
        let record: PythonParityRecord = serde_json::from_str(json).unwrap();
        assert_eq!(record.fixture_id, "py-abcd1234");
        assert_eq!(record.fixture_name, "test_example");
        assert!(record.passed);
        assert_eq!(record.duration_ms, 42);
    }

    #[test]
    fn test_python_parity_to_fixture_report() {
        let record = PythonParityRecord {
            fixture_id: "py-test123".to_owned(),
            fixture_name: "test_algo_parity".to_owned(),
            suite: "python_parity".to_owned(),
            mode: "hardened".to_owned(),
            seed: Some(42),
            threat_class: None,
            replay_command: "pytest test_algo.py -k test_algo_parity".to_owned(),
            passed: false,
            reason_code: Some("assertion_failure".to_owned()),
            fixture_source_hash: "abc123".to_owned(),
            duration_ms: 100,
            strict_violation_count: 1,
            hardened_allowlisted_count: 0,
            mismatches: vec![Mismatch {
                category: "algorithm".to_owned(),
                message: "value mismatch".to_owned(),
            }],
            mismatch_taxonomy: vec![],
            witness: None,
            python_module: "test_algo".to_owned(),
            python_markers: vec!["parity".to_owned()],
            schema_version: "python_parity_v1".to_owned(),
        };

        let report = record.to_fixture_report();
        assert_eq!(report.fixture_id, "py-test123");
        assert_eq!(report.mode, CompatibilityMode::Hardened);
        assert!(!report.passed);
        assert_eq!(report.mismatches.len(), 1);
    }

    #[test]
    fn test_build_crosswalk_report_merges_sources() {
        let rust_reports = vec![FixtureReport {
            fixture_id: "rust-001".to_owned(),
            fixture_name: "rust_fixture_1".to_owned(),
            suite: "rust_conformance".to_owned(),
            mode: CompatibilityMode::Strict,
            seed: None,
            threat_class: None,
            replay_command: String::new(),
            passed: true,
            reason_code: None,
            fixture_source_hash: String::new(),
            duration_ms: 10,
            strict_violation_count: 0,
            hardened_allowlisted_count: 0,
            mismatches: vec![],
            mismatch_taxonomy: vec![],
            witness: None,
        }];

        let python_records = vec![PythonParityRecord {
            fixture_id: "py-001".to_owned(),
            fixture_name: "python_fixture_1".to_owned(),
            suite: "python_parity".to_owned(),
            mode: "strict".to_owned(),
            seed: None,
            threat_class: None,
            replay_command: String::new(),
            passed: true,
            reason_code: None,
            fixture_source_hash: String::new(),
            duration_ms: 20,
            strict_violation_count: 0,
            hardened_allowlisted_count: 0,
            mismatches: vec![],
            mismatch_taxonomy: vec![],
            witness: None,
            python_module: String::new(),
            python_markers: vec![],
            schema_version: "python_parity_v1".to_owned(),
        }];

        let crosswalk = build_crosswalk_report(&rust_reports, &python_records);
        assert_eq!(crosswalk.rust_fixture_count, 1);
        assert_eq!(crosswalk.python_parity_count, 1);
        assert_eq!(crosswalk.unified_reports.len(), 2);
        assert!(crosswalk.combined_fixture_ids.is_empty()); // no overlap
        assert_eq!(crosswalk.rust_only_fixture_ids, vec!["rust-001"]);
        assert_eq!(crosswalk.python_only_fixture_ids, vec!["py-001"]);
    }

    #[test]
    fn helper_graph_builder_preserves_source_runtime_policy() {
        let mut source = Graph::hardened();
        source
            .add_edge("a".to_owned(), "b".to_owned())
            .expect("source edge add should succeed");
        let expected_policy = source.runtime_policy().clone();

        let helper = build_helper_graph_from_source(
            &source,
            &["x".to_owned(), "y".to_owned()],
            &[("x".to_owned(), "y".to_owned())],
        );

        assert_eq!(helper.runtime_policy(), &expected_policy);
        assert_eq!(helper.nodes_ordered(), vec!["x", "y"]);
        assert!(helper.has_edge("x", "y"));
    }
}
