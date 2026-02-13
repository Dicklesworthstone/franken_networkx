#![forbid(unsafe_code)]

use fnx_algorithms::{
    CentralityScore, ComplexityWitness, closeness_centrality, connected_components,
    degree_centrality, number_connected_components, shortest_path_unweighted,
};
use fnx_classes::{AttrMap, EdgeSnapshot, Graph, GraphSnapshot};
use fnx_convert::{AdjacencyPayload, EdgeListPayload, GraphConverter};
use fnx_dispatch::{BackendRegistry, BackendSpec, DispatchDecision, DispatchRequest};
use fnx_generators::GraphGenerator;
use fnx_readwrite::EdgeListEngine;
use fnx_runtime::{
    CompatibilityMode, DecisionAction, FailureReproData, StructuredTestLog, TestKind, TestStatus,
    unix_time_ms,
};
use fnx_views::GraphView;
use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, BTreeSet};
use std::fs;
use std::io;
use std::path::{Path, PathBuf};

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
            log_schema_version: "1.0.0".to_owned(),
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

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct FixtureReport {
    pub fixture_name: String,
    pub suite: String,
    pub mode: CompatibilityMode,
    pub passed: bool,
    pub mismatches: Vec<Mismatch>,
    pub witness: Option<ComplexityWitness>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct HarnessReport {
    pub suite: &'static str,
    pub oracle_present: bool,
    pub fixture_count: usize,
    pub strict_mode: bool,
    pub mismatch_count: usize,
    pub structured_log_count: usize,
    pub structured_log_path: Option<String>,
    pub fixture_reports: Vec<FixtureReport>,
}

#[derive(Debug, Deserialize)]
struct ConformanceFixture {
    suite: String,
    #[serde(default)]
    mode: Option<ModeValue>,
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
    DegreeCentralityQuery,
    ClosenessCentralityQuery,
    ConnectedComponentsQuery,
    NumberConnectedComponentsQuery,
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
    degree_centrality: Option<Vec<ExpectedCentralityScore>>,
    #[serde(default)]
    closeness_centrality: Option<Vec<ExpectedCentralityScore>>,
    #[serde(default)]
    connected_components: Option<Vec<Vec<String>>>,
    #[serde(default)]
    number_connected_components: Option<usize>,
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
    dispatch_decision: Option<DispatchDecision>,
    serialized_edgelist: Option<String>,
    serialized_json_graph: Option<String>,
    view_neighbors_result: Option<Vec<String>>,
    degree_centrality_result: Option<Vec<CentralityScore>>,
    closeness_centrality_result: Option<Vec<CentralityScore>>,
    connected_components_result: Option<Vec<Vec<String>>>,
    number_connected_components_result: Option<usize>,
    warnings: Vec<String>,
    witness: Option<ComplexityWitness>,
}

#[must_use]
pub fn run_smoke(config: &HarnessConfig) -> HarnessReport {
    let mut fixture_reports = Vec::new();

    for path in fixture_paths_recursive(&config.fixture_root) {
        if let Some(filter) = config.fixture_filter.as_deref() {
            let fixture_name = fixture_name_for_path(&path);
            if fixture_name != filter && !fixture_name.ends_with(filter) {
                continue;
            }
        }
        fixture_reports.push(run_fixture(path, config.strict_mode));
    }

    let mismatch_count = fixture_reports
        .iter()
        .map(|report| report.mismatches.len())
        .sum();

    let report = HarnessReport {
        suite: "smoke",
        oracle_present: config.oracle_root.exists(),
        fixture_count: fixture_reports.len(),
        strict_mode: config.strict_mode,
        mismatch_count,
        structured_log_count: fixture_reports.len(),
        structured_log_path: config
            .report_root
            .as_ref()
            .map(|root| root.join("structured_logs.jsonl").display().to_string()),
        fixture_reports,
    };

    if let Some(report_root) = &config.report_root {
        let _ = write_artifacts(report_root, &report, &config.log_schema_version);
    }

    report
}

fn write_artifacts(
    report_root: &Path,
    report: &HarnessReport,
    log_schema_version: &str,
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
        structured_logs.push(build_structured_log(
            report,
            fixture,
            &smoke_path,
            &fixture_path,
            log_schema_version,
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

    Ok(())
}

fn build_structured_log(
    report: &HarnessReport,
    fixture: &FixtureReport,
    smoke_report_path: &Path,
    fixture_report_path: &Path,
    log_schema_version: &str,
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
    let hash_id = stable_hash_hex(&format!(
        "{}|{}|{}|{}|{}",
        fixture.fixture_name,
        fixture.suite,
        mode_flag,
        fixture.passed,
        fixture.mismatches.len()
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

    StructuredTestLog {
        schema_version: log_schema_version.to_owned(),
        ts_unix_ms: unix_time_ms(),
        crate_name: "fnx-conformance".to_owned(),
        packet_id,
        test_name: format!("fixture::{}", fixture.fixture_name),
        test_kind: TestKind::Differential,
        mode: fixture.mode,
        fixture_id: Some(fixture.fixture_name.clone()),
        seed: None,
        environment,
        artifact_refs: vec![
            smoke_report_path.display().to_string(),
            fixture_report_path.display().to_string(),
        ],
        hash_id: hash_id.clone(),
        status,
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
                reproduction_command: reproduction_command_for_fixture(
                    &fixture.fixture_name,
                    fixture.mode,
                ),
                expected_behavior: "Fixture should match expected outputs with zero mismatches"
                    .to_owned(),
                observed_behavior: format!("{} mismatches reported", fixture.mismatches.len()),
                seed: None,
                fixture_id: Some(fixture.fixture_name.clone()),
                artifact_hash_id: Some(hash_id),
            })
        },
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
        "CARGO_TARGET_DIR=target-codex cargo run -q -p fnx-conformance --bin run_smoke -- --fixture {fixture_name} --mode {mode_flag}"
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

fn fixture_name_for_path(path: &Path) -> String {
    path.strip_prefix(PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("fixtures"))
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
        if p.file_name().and_then(|name| name.to_str()) == Some("smoke_case.json") {
            continue;
        }
        out.push(p);
    }
}

fn run_fixture(path: PathBuf, default_strict_mode: bool) -> FixtureReport {
    let fixture_name = fixture_name_for_path(&path);

    let data = match fs::read_to_string(&path) {
        Ok(value) => value,
        Err(err) => {
            return FixtureReport {
                fixture_name,
                suite: "read_error".to_owned(),
                mode: if default_strict_mode {
                    CompatibilityMode::Strict
                } else {
                    CompatibilityMode::Hardened
                },
                passed: false,
                mismatches: vec![Mismatch {
                    category: "fixture_io".to_owned(),
                    message: format!("failed to read fixture: {err}"),
                }],
                witness: None,
            };
        }
    };

    let fixture = match serde_json::from_str::<ConformanceFixture>(&data) {
        Ok(value) => value,
        Err(err) => {
            return FixtureReport {
                fixture_name,
                suite: "parse_error".to_owned(),
                mode: if default_strict_mode {
                    CompatibilityMode::Strict
                } else {
                    CompatibilityMode::Hardened
                },
                passed: false,
                mismatches: vec![Mismatch {
                    category: "fixture_schema".to_owned(),
                    message: format!("failed to parse fixture: {err}"),
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

    let mut context = ExecutionContext {
        graph: Graph::new(mode),
        dispatch_registry: default_dispatch_registry(mode),
        shortest_path_result: None,
        dispatch_decision: None,
        serialized_edgelist: None,
        serialized_json_graph: None,
        view_neighbors_result: None,
        degree_centrality_result: None,
        closeness_centrality_result: None,
        connected_components_result: None,
        number_connected_components_result: None,
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

    FixtureReport {
        fixture_name,
        suite: fixture.suite,
        mode,
        passed: mismatches.is_empty(),
        mismatches,
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
            "convert_edge_list",
            "convert_adjacency",
            "read_edgelist",
            "write_edgelist",
            "read_json_graph",
            "write_json_graph",
            "connected_components",
            "number_connected_components",
            "degree_centrality",
            "closeness_centrality",
            "generate_path_graph",
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
        supported_features: set(["shortest_path"]),
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
