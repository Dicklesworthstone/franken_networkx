#![forbid(unsafe_code)]

use fnx_algorithms::{
    CentralityScore, ComplexityWitness, MinimumCutResult, articulation_points,
    betweenness_centrality, bridges, closeness_centrality, connected_components, degree_centrality,
    eigenvector_centrality, harmonic_centrality, hits_centrality, katz_centrality,
    max_flow_edmonds_karp, minimum_cut_edmonds_karp, number_connected_components, pagerank,
    shortest_path_unweighted, shortest_path_weighted,
};
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
    pub strict_mode: bool,
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
            strict_mode: true,
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
    pub strict_mode: bool,
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
    BetweennessCentralityQuery,
    DegreeCentralityQuery,
    ClosenessCentralityQuery,
    HarmonicCentralityQuery,
    KatzCentralityQuery,
    HitsCentralityQuery,
    PagerankQuery,
    EigenvectorCentralityQuery,
    ConnectedComponentsQuery,
    NumberConnectedComponentsQuery,
    ArticulationPointsQuery,
    BridgesQuery,
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
    ReadJsonGraph {
        input: String,
    },
    WriteJsonGraph,
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
    betweenness_centrality: Option<Vec<ExpectedCentralityScore>>,
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
    connected_components: Option<Vec<Vec<String>>>,
    #[serde(default)]
    number_connected_components: Option<usize>,
    #[serde(default)]
    articulation_points: Option<Vec<String>>,
    #[serde(default)]
    bridges: Option<Vec<(String, String)>>,
    #[serde(default)]
    dispatch: Option<ExpectedDispatch>,
    #[serde(default)]
    serialized_edgelist: Option<String>,
    #[serde(default)]
    serialized_json_graph: Option<String>,
    #[serde(default)]
    view_neighbors: Option<Vec<String>>,
    #[serde(default)]
    warnings_contains: Vec<String>,
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

#[derive(Debug, Clone, Deserialize)]
struct ExpectedCentralityScore {
    node: String,
    score: f64,
}

#[derive(Debug)]
struct ExecutionContext {
    graph: Graph,
    dispatch_registry: BackendRegistry,
    shortest_path_result: Option<Vec<String>>,
    shortest_path_weighted_result: Option<Vec<String>>,
    max_flow_result: Option<f64>,
    minimum_cut_result: Option<MinimumCutResult>,
    dispatch_decision: Option<DispatchDecision>,
    serialized_edgelist: Option<String>,
    serialized_json_graph: Option<String>,
    view_neighbors_result: Option<Vec<String>>,
    betweenness_centrality_result: Option<Vec<CentralityScore>>,
    degree_centrality_result: Option<Vec<CentralityScore>>,
    closeness_centrality_result: Option<Vec<CentralityScore>>,
    harmonic_centrality_result: Option<Vec<CentralityScore>>,
    katz_centrality_result: Option<Vec<CentralityScore>>,
    hits_hubs_result: Option<Vec<CentralityScore>>,
    hits_authorities_result: Option<Vec<CentralityScore>>,
    pagerank_result: Option<Vec<CentralityScore>>,
    eigenvector_centrality_result: Option<Vec<CentralityScore>>,
    connected_components_result: Option<Vec<Vec<String>>>,
    number_connected_components_result: Option<usize>,
    articulation_points_result: Option<Vec<String>>,
    bridges_result: Option<Vec<(String, String)>>,
    warnings: Vec<String>,
    witness: Option<ComplexityWitness>,
}

#[must_use]
pub fn run_smoke(config: &HarnessConfig) -> HarnessReport {
    let mut fixture_reports = Vec::new();
    let run_id = format!(
        "conformance-{}-{}",
        unix_time_ms(),
        if config.strict_mode {
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
        fixture_reports.push(run_fixture(path, config.strict_mode, &config.fixture_root));
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
        strict_mode: config.strict_mode,
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
        report.strict_mode.to_string(),
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

fn run_fixture(path: PathBuf, default_strict_mode: bool, fixture_root: &Path) -> FixtureReport {
    let fixture_start = Instant::now();
    let fixture_name = fixture_name_for_path(&path, fixture_root);
    let fallback_source_hash = stable_hash_hex(&fixture_name);

    let data = match fs::read_to_string(&path) {
        Ok(value) => value,
        Err(err) => {
            let mode = if default_strict_mode {
                CompatibilityMode::Strict
            } else {
                CompatibilityMode::Hardened
            };
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
            let mode = if default_strict_mode {
                CompatibilityMode::Strict
            } else {
                CompatibilityMode::Hardened
            };
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

    let mode = fixture.mode.map_or_else(
        || {
            if default_strict_mode {
                CompatibilityMode::Strict
            } else {
                CompatibilityMode::Hardened
            }
        },
        ModeValue::as_mode,
    );
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
        dispatch_decision: None,
        serialized_edgelist: None,
        serialized_json_graph: None,
        view_neighbors_result: None,
        betweenness_centrality_result: None,
        degree_centrality_result: None,
        closeness_centrality_result: None,
        harmonic_centrality_result: None,
        katz_centrality_result: None,
        hits_hubs_result: None,
        hits_authorities_result: None,
        pagerank_result: None,
        eigenvector_centrality_result: None,
        connected_components_result: None,
        number_connected_components_result: None,
        articulation_points_result: None,
        bridges_result: None,
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
                    max_flow_edmonds_karp(&context.graph, &source, &target, &capacity_attr);
                context.max_flow_result = Some(result.value);
                context.witness = Some(result.witness);
            }
            Operation::MinimumCutQuery {
                source,
                target,
                capacity_attr,
            } => {
                let result =
                    minimum_cut_edmonds_karp(&context.graph, &source, &target, &capacity_attr);
                context.minimum_cut_result = Some(result.clone());
                context.witness = Some(result.witness);
            }
            Operation::BetweennessCentralityQuery => {
                let result = betweenness_centrality(&context.graph);
                context.betweenness_centrality_result = Some(result.scores);
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
            "convert_edge_list",
            "convert_adjacency",
            "read_edgelist",
            "write_edgelist",
            "read_json_graph",
            "write_json_graph",
            "connected_components",
            "number_connected_components",
            "betweenness_centrality",
            "degree_centrality",
            "closeness_centrality",
            "harmonic_centrality",
            "katz_centrality",
            "hits_centrality",
            "pagerank",
            "eigenvector_centrality",
            "generate_path_graph",
            "generate_star_graph",
            "generate_cycle_graph",
            "generate_complete_graph",
            "generate_empty_graph",
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

fn compare_centrality_scores(
    label: &str,
    actual: &[CentralityScore],
    expected: &[ExpectedCentralityScore],
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
        if actual_score.node != expected_score.node {
            mismatches.push(Mismatch {
                category: "algorithm_centrality".to_owned(),
                message: format!(
                    "{label} node mismatch at index {idx}: expected {:?}, got {:?}",
                    expected_score.node, actual_score.node
                ),
            });
        }
        if (actual_score.score - expected_score.score).abs() > 1e-12 {
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

#[cfg(test)]
mod tests {
    use super::{HarnessConfig, run_smoke};

    #[test]
    fn smoke_harness_reports_zero_drift_for_bootstrap_fixtures() {
        let mut cfg = HarnessConfig::default_paths();
        cfg.report_root = None;
        let report = run_smoke(&cfg);
        assert!(report.oracle_present, "oracle repo should be present");
        assert!(report.fixture_count >= 1, "expected at least one fixture");
        assert_eq!(report.mismatch_count, 0, "fixtures should be drift-free");
        assert_eq!(report.structured_log_count, report.fixture_count);
    }
}
