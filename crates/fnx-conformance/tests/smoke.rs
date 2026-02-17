use fnx_classes::Graph;
use fnx_conformance::{DriftTaxonomyReport, HarnessConfig, MismatchClassification, run_smoke};
use fnx_runtime::{StructuredTestLog, TestKind, TestStatus};
use fnx_views::{CachedSnapshotView, GraphView};
use proptest::prelude::*;
use std::collections::BTreeMap;
use std::fs;
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicU64, Ordering};
use std::time::{SystemTime, UNIX_EPOCH};

static UNIQUE_NONCE: AtomicU64 = AtomicU64::new(0);

fn next_unique_nonce() -> u64 {
    UNIQUE_NONCE.fetch_add(1, Ordering::Relaxed)
}

fn unique_report_root() -> PathBuf {
    let time_nonce = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map_or(0, |dur| dur.as_millis());
    let nonce = next_unique_nonce();
    std::env::temp_dir().join(format!("fnx_conformance_smoke_{time_nonce}_{nonce}"))
}

fn unique_fixture_root() -> PathBuf {
    let time_nonce = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map_or(0, |dur| dur.as_micros());
    let nonce = next_unique_nonce();
    std::env::temp_dir().join(format!("fnx_conformance_fixtures_{time_nonce}_{nonce}"))
}

fn write_fixture(root: &Path, name: &str, body: &str) {
    let path = root.join(name);
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent).expect("fixture directory should be creatable");
    }
    fs::write(path, body).expect("fixture should be writable");
}

fn read_structured_logs(report_root: &Path) -> Vec<StructuredTestLog> {
    let raw = fs::read_to_string(report_root.join("structured_logs.jsonl"))
        .expect("structured logs should exist");
    raw.lines()
        .map(|line| serde_json::from_str::<StructuredTestLog>(line).expect("valid log row"))
        .collect()
}

fn neighbors_for_node(graph: &Graph, node: &str) -> Vec<String> {
    GraphView::new(graph)
        .neighbors(node)
        .map_or_else(Vec::new, |neighbors| {
            neighbors
                .into_iter()
                .map(str::to_owned)
                .collect::<Vec<String>>()
        })
}

#[test]
fn smoke_report_is_stable() {
    let mut cfg = HarnessConfig::default_paths();
    cfg.report_root = None;
    let report = run_smoke(&cfg);
    assert_eq!(report.suite, "smoke");
    assert!(report.fixture_count >= 1);
    assert!(report.oracle_present);
    assert_eq!(report.mismatch_count, 0);
    assert!(report.fixture_reports.iter().all(|fixture| fixture.passed));
}

#[test]
fn smoke_emits_structured_logs_with_replay_metadata() {
    let mut cfg = HarnessConfig::default_paths();
    let report_root = unique_report_root();
    cfg.report_root = Some(report_root.clone());

    let report = run_smoke(&cfg);
    assert_eq!(report.mismatch_count, 0);
    assert_eq!(report.structured_log_count, report.fixture_count);

    let raw = fs::read_to_string(report_root.join("structured_logs.jsonl"))
        .expect("structured log artifact should exist");
    let logs: Vec<StructuredTestLog> = raw
        .lines()
        .map(|line| serde_json::from_str::<StructuredTestLog>(line).expect("valid log line"))
        .collect();
    assert_eq!(logs.len(), report.fixture_count);
    assert!(!logs.is_empty(), "expected at least one structured log");
    let mut observed_packets = std::collections::BTreeSet::new();
    for log in logs {
        observed_packets.insert(log.packet_id.clone());
        log.validate().expect("log should satisfy schema contract");
        assert_eq!(log.test_kind, TestKind::Differential);
        assert_eq!(log.crate_name, "fnx-conformance");
        assert!(log.packet_id.starts_with("FNX-P2C-"));
        assert!(log.run_id.starts_with("conformance-"));
        assert_eq!(log.suite_id, "smoke");
        assert!(log.test_id.starts_with("fixture::"));
        assert!(!log.env_fingerprint.is_empty());
        assert!(!log.replay_command.is_empty());
        assert!(!log.forensic_bundle_id.is_empty());
        assert!(log.e2e_step_traces.is_empty());
        let bundle = log
            .forensics_bundle_index
            .as_ref()
            .expect("forensics bundle index should be present");
        assert_eq!(bundle.bundle_id, log.forensic_bundle_id);
        assert_eq!(bundle.run_id, log.run_id);
        assert_eq!(bundle.test_id, log.test_id);
        assert_eq!(bundle.replay_ref, log.replay_command);
        assert!(!bundle.bundle_hash_id.is_empty());
        assert!(!bundle.artifact_refs.is_empty());
        assert!(log.duration_ms <= 60_000);
    }
    assert!(
        observed_packets.contains("FNX-P2C-008"),
        "runtime config/optional packet coverage should be present in smoke logs"
    );
    assert!(
        observed_packets.contains("FNX-P2C-009"),
        "conformance harness packet coverage should be present in smoke logs"
    );

    let normalization_raw =
        fs::read_to_string(report_root.join("structured_log_emitter_normalization_report.json"))
            .expect("normalization report artifact should exist");
    let normalization: serde_json::Value =
        serde_json::from_str(&normalization_raw).expect("valid normalization report json");
    assert_eq!(
        normalization["valid_log_count"].as_u64(),
        Some(report.fixture_count as u64)
    );
    assert!(
        normalization["normalized_fields"]
            .as_array()
            .is_some_and(|fields| fields.len() >= 10)
    );

    let matrix_raw =
        fs::read_to_string(report_root.join("telemetry_dependent_unblock_matrix_v1.json"))
            .expect("dependent unblock matrix artifact should exist");
    let matrix: serde_json::Value = serde_json::from_str(&matrix_raw).expect("valid matrix json");
    assert_eq!(matrix["source_bead_id"].as_str(), Some("bd-315.5.4"));
    assert!(matrix["rows"].as_array().is_some_and(|rows| {
        rows.iter()
            .any(|row| row["blocked_bead_id"] == "bd-315.5.5")
    }));
}

#[test]
fn packet_001_metamorphic_and_adversarial_fixtures_emit_seeded_taxonomy() {
    let fixture_root = unique_fixture_root();
    write_fixture(
        &fixture_root,
        "graph_core_metamorphic_order_a_strict.json",
        r#"{
  "suite": "graph_core_v1",
  "mode": "strict",
  "fixture_id": "graph_core::metamorphic_attr_merge_order_a",
  "seed": 12001,
  "threat_class": "metamorphic_attr_merge_commutativity",
  "operations": [
    { "op": "add_edge", "left": "a", "right": "b", "attrs": { "weight": "1" } },
    { "op": "add_edge", "left": "a", "right": "b", "attrs": { "color": "red" } },
    { "op": "add_edge", "left": "b", "right": "c" },
    { "op": "shortest_path_query", "source": "a", "target": "c" }
  ],
  "expected": {
    "graph": {
      "nodes": ["a", "b", "c"],
      "edges": [
        { "left": "a", "right": "b", "attrs": { "color": "red", "weight": "1" } },
        { "left": "b", "right": "c", "attrs": {} }
      ]
    },
    "shortest_path_unweighted": ["a", "b", "c"]
  }
}"#,
    );
    write_fixture(
        &fixture_root,
        "graph_core_metamorphic_order_b_strict.json",
        r#"{
  "suite": "graph_core_v1",
  "mode": "strict",
  "fixture_id": "graph_core::metamorphic_attr_merge_order_b",
  "seed": 12001,
  "threat_class": "metamorphic_attr_merge_commutativity",
  "operations": [
    { "op": "add_edge", "left": "a", "right": "b", "attrs": { "color": "red" } },
    { "op": "add_edge", "left": "a", "right": "b", "attrs": { "weight": "1" } },
    { "op": "add_edge", "left": "b", "right": "c" },
    { "op": "shortest_path_query", "source": "a", "target": "c" }
  ],
  "expected": {
    "graph": {
      "nodes": ["a", "b", "c"],
      "edges": [
        { "left": "a", "right": "b", "attrs": { "color": "red", "weight": "1" } },
        { "left": "b", "right": "c", "attrs": {} }
      ]
    },
    "shortest_path_unweighted": ["a", "b", "c"]
  }
}"#,
    );
    write_fixture(
        &fixture_root,
        "graph_core_adversarial_hardened_allowlisted_hardened.json",
        r#"{
  "suite": "graph_core_v1",
  "mode": "hardened",
  "fixture_id": "graph_core::adversarial_unknown_feature_allowlisted",
  "seed": 2101,
  "threat_class": "metadata_ambiguity",
  "hardened_allowlisted_categories": ["graph_mutation"],
  "operations": [
    {
      "op": "add_edge",
      "left": "u",
      "right": "v",
      "attrs": { "__fnx_incompatible_decoder": "v2" }
    }
  ],
  "expected": {
    "graph": {
      "nodes": [],
      "edges": []
    }
  }
}"#,
    );

    let mut cfg = HarnessConfig::default_paths();
    let report_root = unique_report_root();
    cfg.fixture_root = fixture_root;
    cfg.report_root = Some(report_root.clone());

    let report = run_smoke(&cfg);
    assert_eq!(report.fixture_count, 3);
    assert_eq!(report.mismatch_count, 0);
    assert_eq!(report.hardened_allowlisted_count, 1);
    assert!(report.fixture_reports.iter().all(|fixture| fixture.passed));

    let adversarial_fixture = report
        .fixture_reports
        .iter()
        .find(|fixture| fixture.fixture_id == "graph_core::adversarial_unknown_feature_allowlisted")
        .expect("adversarial fixture row should exist");
    assert_eq!(adversarial_fixture.seed, Some(2101));
    assert_eq!(
        adversarial_fixture.threat_class.as_deref(),
        Some("metadata_ambiguity")
    );
    assert_eq!(adversarial_fixture.strict_violation_count, 0);
    assert_eq!(adversarial_fixture.hardened_allowlisted_count, 1);
    assert_eq!(
        adversarial_fixture.reason_code.as_deref(),
        Some("hardened_allowlisted_mismatch")
    );
    assert!(adversarial_fixture.mismatch_taxonomy.iter().any(|row| {
        row.classification == MismatchClassification::HardenedAllowlisted
            && row.category == "graph_mutation"
    }));

    let taxonomy_raw = fs::read_to_string(report_root.join("mismatch_taxonomy_report.json"))
        .expect("drift taxonomy report should exist");
    let taxonomy: DriftTaxonomyReport =
        serde_json::from_str(&taxonomy_raw).expect("drift taxonomy report should parse");
    assert_eq!(taxonomy.strict_violation_count, 0);
    assert_eq!(taxonomy.hardened_allowlisted_count, 1);
    let taxonomy_row = taxonomy
        .fixtures
        .iter()
        .find(|row| row.fixture_id == "graph_core::adversarial_unknown_feature_allowlisted")
        .expect("taxonomy row for adversarial fixture should exist");
    assert_eq!(taxonomy_row.packet_id, "FNX-P2C-001");
    assert_eq!(taxonomy_row.seed, Some(2101));
    assert!(
        taxonomy_row
            .mismatches
            .iter()
            .any(|entry| entry.classification == MismatchClassification::HardenedAllowlisted)
    );

    let logs_raw = fs::read_to_string(report_root.join("structured_logs.jsonl"))
        .expect("structured logs should exist");
    let logs: Vec<StructuredTestLog> = logs_raw
        .lines()
        .map(|line| serde_json::from_str::<StructuredTestLog>(line).expect("valid log row"))
        .collect();
    assert_eq!(logs.len(), 3);
    for log in &logs {
        assert!(
            log.replay_command.starts_with("rch exec --"),
            "replay command should be rch offloaded"
        );
    }
    let adversarial_log = logs
        .iter()
        .find(|log| {
            log.fixture_id.as_deref() == Some("graph_core::adversarial_unknown_feature_allowlisted")
        })
        .expect("adversarial log row should exist");
    assert_eq!(adversarial_log.seed, Some(2101));
    assert_eq!(
        adversarial_log.reason_code.as_deref(),
        Some("hardened_allowlisted_mismatch")
    );
    assert_eq!(adversarial_log.status, fnx_runtime::TestStatus::Passed);
    assert!(
        adversarial_log
            .environment
            .get("threat_class")
            .is_some_and(|value| value == "metadata_ambiguity")
    );

    let adversarial_envelope = report_root
        .join("graph_core_adversarial_hardened_allowlisted_hardened_json.failure_envelope.json");
    assert!(
        adversarial_envelope.exists(),
        "adversarial mismatch should emit replayable envelope"
    );
    let envelope_json: serde_json::Value = serde_json::from_str(
        &fs::read_to_string(&adversarial_envelope).expect("envelope should be readable"),
    )
    .expect("envelope should parse");
    assert_eq!(
        envelope_json["fixture_id"].as_str(),
        Some("graph_core::adversarial_unknown_feature_allowlisted")
    );
    assert_eq!(envelope_json["packet_id"].as_str(), Some("FNX-P2C-001"));
    assert_eq!(envelope_json["seed"].as_u64(), Some(2101));
    assert!(envelope_json["replay_command"].as_str().is_some_and(|cmd| {
        cmd.contains("--fixture graph_core_adversarial_hardened_allowlisted_hardened.json")
    }));
}

#[test]
fn packet_002_contract_rows_emit_replay_complete_structured_logs() {
    let fixture_root = unique_fixture_root();
    write_fixture(
        &fixture_root,
        "view_neighbors_projection_nominal_strict.json",
        r#"{
  "suite": "views_v1",
  "mode": "strict",
  "fixture_id": "views::projection_nominal",
  "seed": 5201,
  "threat_class": "state_corruption",
  "operations": [
    { "op": "add_edge", "left": "a", "right": "b" },
    { "op": "add_edge", "left": "a", "right": "c" },
    { "op": "view_neighbors_query", "node": "a" }
  ],
  "expected": {
    "graph": {
      "nodes": ["a", "b", "c"],
      "edges": [
        { "left": "a", "right": "b", "attrs": {} },
        { "left": "a", "right": "c", "attrs": {} }
      ]
    },
    "view_neighbors": ["b", "c"]
  }
}"#,
    );
    write_fixture(
        &fixture_root,
        "view_neighbors_projection_after_mutation_strict.json",
        r#"{
  "suite": "views_v1",
  "mode": "strict",
  "fixture_id": "views::projection_after_mutation",
  "seed": 5202,
  "threat_class": "state_corruption",
  "operations": [
    { "op": "add_edge", "left": "a", "right": "b" },
    { "op": "add_edge", "left": "a", "right": "c" },
    { "op": "remove_edge", "left": "a", "right": "c" },
    { "op": "view_neighbors_query", "node": "a" }
  ],
  "expected": {
    "graph": {
      "nodes": ["a", "b", "c"],
      "edges": [
        { "left": "a", "right": "b", "attrs": {} }
      ]
    },
    "view_neighbors": ["b"]
  }
}"#,
    );
    write_fixture(
        &fixture_root,
        "view_neighbors_unknown_metadata_fail_closed_strict.json",
        r#"{
  "suite": "views_v1",
  "mode": "strict",
  "fixture_id": "views::unknown_metadata_fail_closed",
  "seed": 5203,
  "threat_class": "metadata_ambiguity",
  "operations": [
    {
      "op": "add_edge",
      "left": "u",
      "right": "v",
      "attrs": { "__fnx_incompatible_decoder": "v2" }
    },
    { "op": "view_neighbors_query", "node": "u" }
  ],
  "expected": {
    "graph": {
      "nodes": [],
      "edges": []
    }
  }
}"#,
    );
    write_fixture(
        &fixture_root,
        "view_neighbors_unknown_metadata_allowlisted_hardened.json",
        r#"{
  "suite": "views_v1",
  "mode": "hardened",
  "fixture_id": "views::unknown_metadata_allowlisted",
  "seed": 5203,
  "threat_class": "metadata_ambiguity",
  "hardened_allowlisted_categories": ["graph_mutation"],
  "operations": [
    {
      "op": "add_edge",
      "left": "u",
      "right": "v",
      "attrs": { "__fnx_incompatible_decoder": "v2" }
    },
    { "op": "view_neighbors_query", "node": "u" }
  ],
  "expected": {
    "graph": {
      "nodes": [],
      "edges": []
    }
  }
}"#,
    );

    let mut cfg = HarnessConfig::default_paths();
    let first_report_root = unique_report_root();
    cfg.fixture_root = fixture_root;
    cfg.report_root = Some(first_report_root.clone());

    let first_report = run_smoke(&cfg);
    assert_eq!(first_report.fixture_count, 4);
    assert_eq!(first_report.mismatch_count, 1);
    assert_eq!(first_report.hardened_allowlisted_count, 1);

    let strict_failure_fixture = first_report
        .fixture_reports
        .iter()
        .find(|fixture| fixture.fixture_id == "views::unknown_metadata_fail_closed")
        .expect("strict fail-closed fixture should exist");
    assert!(!strict_failure_fixture.passed);
    assert_eq!(
        strict_failure_fixture.reason_code.as_deref(),
        Some("mismatch")
    );
    assert_eq!(strict_failure_fixture.seed, Some(5203));
    assert_eq!(
        strict_failure_fixture.threat_class.as_deref(),
        Some("metadata_ambiguity")
    );
    assert_eq!(strict_failure_fixture.strict_violation_count, 1);
    assert_eq!(strict_failure_fixture.hardened_allowlisted_count, 0);

    let hardened_allowlisted_fixture = first_report
        .fixture_reports
        .iter()
        .find(|fixture| fixture.fixture_id == "views::unknown_metadata_allowlisted")
        .expect("hardened allowlisted fixture should exist");
    assert!(hardened_allowlisted_fixture.passed);
    assert_eq!(
        hardened_allowlisted_fixture.reason_code.as_deref(),
        Some("hardened_allowlisted_mismatch")
    );
    assert_eq!(hardened_allowlisted_fixture.seed, Some(5203));
    assert_eq!(
        hardened_allowlisted_fixture.threat_class.as_deref(),
        Some("metadata_ambiguity")
    );
    assert_eq!(hardened_allowlisted_fixture.strict_violation_count, 0);
    assert_eq!(hardened_allowlisted_fixture.hardened_allowlisted_count, 1);

    let first_logs = read_structured_logs(&first_report_root);
    assert_eq!(first_logs.len(), 4);
    for log in &first_logs {
        log.validate()
            .expect("packet-002 structured log should satisfy schema");
        assert_eq!(log.packet_id, "FNX-P2C-002");
        assert_eq!(log.test_kind, TestKind::Differential);
        assert_eq!(log.crate_name, "fnx-conformance");
        assert_eq!(log.suite_id, "smoke");
        assert!(log.test_id.starts_with("fixture::views::"));
        assert!(log.replay_command.starts_with("rch exec --"));
        assert!(log.fixture_id.is_some());
        assert!(log.seed.is_some());
        assert!(!log.env_fingerprint.is_empty());
        assert!(log.environment.contains_key("fixture_id"));
        assert!(log.environment.contains_key("threat_class"));
        assert!(!log.forensic_bundle_id.is_empty());
        assert!(!log.hash_id.is_empty());
        let bundle = log
            .forensics_bundle_index
            .as_ref()
            .expect("forensics bundle index should be present");
        assert_eq!(bundle.bundle_id, log.forensic_bundle_id);
        assert_eq!(bundle.replay_ref, log.replay_command);
        assert!(!bundle.bundle_hash_id.is_empty());
        assert!(!bundle.artifact_refs.is_empty());
    }

    let strict_failure_log = first_logs
        .iter()
        .find(|log| log.fixture_id.as_deref() == Some("views::unknown_metadata_fail_closed"))
        .expect("strict fail-closed log should exist");
    assert_eq!(strict_failure_log.status, TestStatus::Failed);
    assert_eq!(strict_failure_log.reason_code.as_deref(), Some("mismatch"));
    assert!(strict_failure_log.failure_repro.is_some());
    assert_eq!(strict_failure_log.seed, Some(5203));
    assert_eq!(
        strict_failure_log
            .environment
            .get("threat_class")
            .map(String::as_str),
        Some("metadata_ambiguity")
    );

    let hardened_allowlisted_log = first_logs
        .iter()
        .find(|log| log.fixture_id.as_deref() == Some("views::unknown_metadata_allowlisted"))
        .expect("hardened allowlisted log should exist");
    assert_eq!(hardened_allowlisted_log.status, TestStatus::Passed);
    assert_eq!(
        hardened_allowlisted_log.reason_code.as_deref(),
        Some("hardened_allowlisted_mismatch")
    );
    assert!(hardened_allowlisted_log.failure_repro.is_none());

    let failure_envelope = first_report_root
        .join("view_neighbors_unknown_metadata_fail_closed_strict_json.failure_envelope.json");
    assert!(
        failure_envelope.exists(),
        "strict fail-closed fixture should emit failure envelope"
    );
    let failure_envelope_payload: serde_json::Value =
        serde_json::from_str(&fs::read_to_string(&failure_envelope).expect("envelope readable"))
            .expect("envelope parseable");
    assert_eq!(
        failure_envelope_payload["fixture_id"].as_str(),
        Some("views::unknown_metadata_fail_closed")
    );
    assert_eq!(
        failure_envelope_payload["packet_id"].as_str(),
        Some("FNX-P2C-002")
    );
    assert_eq!(failure_envelope_payload["seed"].as_u64(), Some(5203));
    assert_eq!(
        failure_envelope_payload["reason_code"].as_str(),
        Some("mismatch")
    );

    let second_report_root = unique_report_root();
    cfg.report_root = Some(second_report_root.clone());
    let second_report = run_smoke(&cfg);
    assert_eq!(second_report.fixture_count, first_report.fixture_count);
    assert_eq!(second_report.mismatch_count, first_report.mismatch_count);
    assert_eq!(
        second_report.hardened_allowlisted_count,
        first_report.hardened_allowlisted_count
    );

    let second_logs = read_structured_logs(&second_report_root);
    let first_hashes_by_fixture = first_logs
        .iter()
        .map(|log| {
            (
                log.fixture_id
                    .clone()
                    .expect("fixture id should always be populated"),
                log.hash_id.clone(),
            )
        })
        .collect::<BTreeMap<String, String>>();
    let second_hashes_by_fixture = second_logs
        .iter()
        .map(|log| {
            (
                log.fixture_id
                    .clone()
                    .expect("fixture id should always be populated"),
                log.hash_id.clone(),
            )
        })
        .collect::<BTreeMap<String, String>>();
    assert_eq!(
        first_hashes_by_fixture, second_hashes_by_fixture,
        "deterministic replay hash drifted for packet-002 fixtures"
    );
}

#[test]
fn packet_002_differential_metamorphic_and_adversarial_taxonomy_is_deterministic() {
    let fixture_root = unique_fixture_root();
    write_fixture(
        &fixture_root,
        "view_neighbors_metamorphic_duplicate_edge_a_strict.json",
        r#"{
  "suite": "views_v1",
  "mode": "strict",
  "fixture_id": "views::metamorphic_duplicate_edge_a",
  "seed": 6201,
  "threat_class": "metamorphic_duplicate_edge_idempotence",
  "operations": [
    { "op": "add_edge", "left": "a", "right": "b" },
    { "op": "view_neighbors_query", "node": "a" }
  ],
  "expected": {
    "graph": {
      "nodes": ["a", "b"],
      "edges": [
        { "left": "a", "right": "b", "attrs": {} }
      ]
    },
    "view_neighbors": ["b"]
  }
}"#,
    );
    write_fixture(
        &fixture_root,
        "view_neighbors_metamorphic_duplicate_edge_b_strict.json",
        r#"{
  "suite": "views_v1",
  "mode": "strict",
  "fixture_id": "views::metamorphic_duplicate_edge_b",
  "seed": 6201,
  "threat_class": "metamorphic_duplicate_edge_idempotence",
  "operations": [
    { "op": "add_edge", "left": "a", "right": "b" },
    { "op": "add_edge", "left": "a", "right": "b" },
    { "op": "view_neighbors_query", "node": "a" }
  ],
  "expected": {
    "graph": {
      "nodes": ["a", "b"],
      "edges": [
        { "left": "a", "right": "b", "attrs": {} }
      ]
    },
    "view_neighbors": ["b"]
  }
}"#,
    );
    write_fixture(
        &fixture_root,
        "view_neighbors_adversarial_parser_abuse_strict.json",
        r#"{
  "suite": "views_v1",
  "mode": "strict",
  "fixture_id": "views::adversarial_parser_abuse",
  "seed": 1102,
  "threat_class": "parser_abuse",
  "operations": [
    {
      "op": "add_edge",
      "left": "p",
      "right": "q",
      "attrs": { "__fnx_incompatible_decoder": "v2" }
    }
  ],
  "expected": {
    "graph": {
      "nodes": [],
      "edges": []
    }
  }
}"#,
    );
    write_fixture(
        &fixture_root,
        "view_neighbors_adversarial_metadata_strict.json",
        r#"{
  "suite": "views_v1",
  "mode": "strict",
  "fixture_id": "views::adversarial_metadata_ambiguity_strict",
  "seed": 2102,
  "threat_class": "metadata_ambiguity",
  "operations": [
    {
      "op": "add_edge",
      "left": "m",
      "right": "n",
      "attrs": { "__fnx_incompatible_decoder": "v2" }
    }
  ],
  "expected": {
    "graph": {
      "nodes": [],
      "edges": []
    }
  }
}"#,
    );
    write_fixture(
        &fixture_root,
        "view_neighbors_adversarial_metadata_hardened.json",
        r#"{
  "suite": "views_v1",
  "mode": "hardened",
  "fixture_id": "views::adversarial_metadata_ambiguity_hardened",
  "seed": 2102,
  "threat_class": "metadata_ambiguity",
  "hardened_allowlisted_categories": ["graph_mutation"],
  "operations": [
    {
      "op": "add_edge",
      "left": "m",
      "right": "n",
      "attrs": { "__fnx_incompatible_decoder": "v2" }
    }
  ],
  "expected": {
    "graph": {
      "nodes": [],
      "edges": []
    }
  }
}"#,
    );
    write_fixture(
        &fixture_root,
        "view_neighbors_adversarial_version_skew_strict.json",
        r#"{
  "suite": "views_v1",
  "mode": "strict",
  "fixture_id": "views::adversarial_version_skew",
  "seed": 3102,
  "threat_class": "version_skew",
  "operations": [
    {
      "op": "add_edge",
      "left": "v1",
      "right": "v2",
      "attrs": { "__fnx_incompatible_decoder": "v2" }
    }
  ],
  "expected": {
    "graph": {
      "nodes": [],
      "edges": []
    }
  }
}"#,
    );
    write_fixture(
        &fixture_root,
        "view_neighbors_adversarial_resource_exhaustion_strict.json",
        r#"{
  "suite": "views_v1",
  "mode": "strict",
  "fixture_id": "views::adversarial_resource_exhaustion",
  "seed": 4102,
  "threat_class": "resource_exhaustion",
  "operations": [
    {
      "op": "add_edge",
      "left": "r1",
      "right": "r2",
      "attrs": { "__fnx_incompatible_decoder": "v2" }
    }
  ],
  "expected": {
    "graph": {
      "nodes": [],
      "edges": []
    }
  }
}"#,
    );
    write_fixture(
        &fixture_root,
        "view_neighbors_adversarial_state_corruption_strict.json",
        r#"{
  "suite": "views_v1",
  "mode": "strict",
  "fixture_id": "views::adversarial_state_corruption",
  "seed": 5102,
  "threat_class": "state_corruption",
  "operations": [
    {
      "op": "add_edge",
      "left": "s1",
      "right": "s2",
      "attrs": { "__fnx_incompatible_decoder": "v2" }
    }
  ],
  "expected": {
    "graph": {
      "nodes": [],
      "edges": []
    }
  }
}"#,
    );

    let mut cfg = HarnessConfig::default_paths();
    let report_root = unique_report_root();
    cfg.fixture_root = fixture_root;
    cfg.report_root = Some(report_root.clone());

    let report = run_smoke(&cfg);
    assert!(
        report.oracle_present,
        "legacy oracle root should be present"
    );
    assert_eq!(report.fixture_count, 8);
    assert_eq!(report.mismatch_count, 5);
    assert_eq!(report.hardened_allowlisted_count, 1);

    let metamorphic_a = report
        .fixture_reports
        .iter()
        .find(|fixture| fixture.fixture_id == "views::metamorphic_duplicate_edge_a")
        .expect("metamorphic fixture A should exist");
    let metamorphic_b = report
        .fixture_reports
        .iter()
        .find(|fixture| fixture.fixture_id == "views::metamorphic_duplicate_edge_b")
        .expect("metamorphic fixture B should exist");
    assert!(metamorphic_a.passed);
    assert!(metamorphic_b.passed);
    assert_eq!(metamorphic_a.seed, Some(6201));
    assert_eq!(metamorphic_b.seed, Some(6201));
    assert_eq!(
        metamorphic_a.threat_class.as_deref(),
        Some("metamorphic_duplicate_edge_idempotence")
    );
    assert_eq!(
        metamorphic_b.threat_class.as_deref(),
        Some("metamorphic_duplicate_edge_idempotence")
    );
    assert_eq!(metamorphic_a.strict_violation_count, 0);
    assert_eq!(metamorphic_b.strict_violation_count, 0);
    assert_eq!(metamorphic_a.hardened_allowlisted_count, 0);
    assert_eq!(metamorphic_b.hardened_allowlisted_count, 0);

    let hardened_metadata = report
        .fixture_reports
        .iter()
        .find(|fixture| fixture.fixture_id == "views::adversarial_metadata_ambiguity_hardened")
        .expect("hardened metadata fixture should exist");
    assert!(hardened_metadata.passed);
    assert_eq!(
        hardened_metadata.reason_code.as_deref(),
        Some("hardened_allowlisted_mismatch")
    );
    assert_eq!(hardened_metadata.seed, Some(2102));
    assert_eq!(
        hardened_metadata.threat_class.as_deref(),
        Some("metadata_ambiguity")
    );
    assert_eq!(hardened_metadata.strict_violation_count, 0);
    assert_eq!(hardened_metadata.hardened_allowlisted_count, 1);
    assert!(
        hardened_metadata
            .mismatch_taxonomy
            .iter()
            .all(|entry| { entry.classification == MismatchClassification::HardenedAllowlisted })
    );

    let strict_adversarial_fixture_ids = [
        "views::adversarial_parser_abuse",
        "views::adversarial_metadata_ambiguity_strict",
        "views::adversarial_version_skew",
        "views::adversarial_resource_exhaustion",
        "views::adversarial_state_corruption",
    ];
    for fixture_id in strict_adversarial_fixture_ids {
        let fixture = report
            .fixture_reports
            .iter()
            .find(|row| row.fixture_id == fixture_id)
            .expect("strict adversarial fixture should exist");
        assert!(!fixture.passed);
        assert_eq!(fixture.reason_code.as_deref(), Some("mismatch"));
        assert_eq!(fixture.strict_violation_count, 1);
        assert_eq!(fixture.hardened_allowlisted_count, 0);
        assert!(
            fixture
                .mismatch_taxonomy
                .iter()
                .all(|entry| entry.classification == MismatchClassification::StrictViolation)
        );
    }

    let expected_seed_and_threat = BTreeMap::from([
        (
            "views::adversarial_parser_abuse".to_owned(),
            (Some(1102_u64), Some("parser_abuse")),
        ),
        (
            "views::adversarial_metadata_ambiguity_strict".to_owned(),
            (Some(2102_u64), Some("metadata_ambiguity")),
        ),
        (
            "views::adversarial_metadata_ambiguity_hardened".to_owned(),
            (Some(2102_u64), Some("metadata_ambiguity")),
        ),
        (
            "views::adversarial_version_skew".to_owned(),
            (Some(3102_u64), Some("version_skew")),
        ),
        (
            "views::adversarial_resource_exhaustion".to_owned(),
            (Some(4102_u64), Some("resource_exhaustion")),
        ),
        (
            "views::adversarial_state_corruption".to_owned(),
            (Some(5102_u64), Some("state_corruption")),
        ),
    ]);
    for fixture in &report.fixture_reports {
        if let Some((expected_seed, expected_threat)) =
            expected_seed_and_threat.get(&fixture.fixture_id)
        {
            assert_eq!(&fixture.seed, expected_seed);
            assert_eq!(fixture.threat_class.as_deref(), *expected_threat);
        }
    }

    let taxonomy_raw = fs::read_to_string(report_root.join("mismatch_taxonomy_report.json"))
        .expect("drift taxonomy report should exist");
    let taxonomy: DriftTaxonomyReport =
        serde_json::from_str(&taxonomy_raw).expect("drift taxonomy report should parse");
    assert_eq!(taxonomy.strict_violation_count, 5);
    assert_eq!(taxonomy.hardened_allowlisted_count, 1);
    assert_eq!(taxonomy.fixtures.len(), 8);
    assert!(
        taxonomy
            .fixtures
            .iter()
            .all(|fixture| fixture.packet_id == "FNX-P2C-002")
    );
    let hardened_taxonomy_row = taxonomy
        .fixtures
        .iter()
        .find(|row| row.fixture_id == "views::adversarial_metadata_ambiguity_hardened")
        .expect("hardened taxonomy row should exist");
    assert!(
        hardened_taxonomy_row
            .mismatches
            .iter()
            .all(|entry| entry.classification == MismatchClassification::HardenedAllowlisted)
    );

    let logs = read_structured_logs(&report_root);
    assert_eq!(logs.len(), 8);
    assert!(logs.iter().all(|log| log.packet_id == "FNX-P2C-002"));
    assert!(
        logs.iter()
            .all(|log| log.test_kind == TestKind::Differential)
    );
    assert!(
        logs.iter()
            .all(|log| log.replay_command.starts_with("rch exec --"))
    );
    for log in &logs {
        log.validate()
            .expect("differential structured log should satisfy schema");
        assert!(log.fixture_id.is_some());
        assert!(log.seed.is_some());
        assert!(!log.env_fingerprint.is_empty());
    }

    let strict_failed_logs = logs
        .iter()
        .filter(|log| {
            strict_adversarial_fixture_ids.contains(&log.fixture_id.as_deref().unwrap_or_default())
        })
        .collect::<Vec<&StructuredTestLog>>();
    assert_eq!(strict_failed_logs.len(), 5);
    assert!(
        strict_failed_logs
            .iter()
            .all(|log| log.status == TestStatus::Failed)
    );
    assert!(
        strict_failed_logs
            .iter()
            .all(|log| log.failure_repro.is_some())
    );
    assert!(
        strict_failed_logs
            .iter()
            .all(|log| log.reason_code.as_deref() == Some("mismatch"))
    );

    let hardened_log = logs
        .iter()
        .find(|log| {
            log.fixture_id.as_deref() == Some("views::adversarial_metadata_ambiguity_hardened")
        })
        .expect("hardened adversarial log should exist");
    assert_eq!(hardened_log.status, TestStatus::Passed);
    assert_eq!(
        hardened_log.reason_code.as_deref(),
        Some("hardened_allowlisted_mismatch")
    );
    assert!(hardened_log.failure_repro.is_none());
    assert_eq!(hardened_log.seed, Some(2102));
    assert_eq!(
        hardened_log
            .environment
            .get("threat_class")
            .map(String::as_str),
        Some("metadata_ambiguity")
    );

    let failure_envelopes = fs::read_dir(&report_root)
        .expect("report root should be readable")
        .filter_map(Result::ok)
        .map(|entry| entry.path())
        .filter(|path| {
            path.file_name()
                .and_then(|name| name.to_str())
                .is_some_and(|name| name.ends_with(".failure_envelope.json"))
        })
        .collect::<Vec<PathBuf>>();
    assert_eq!(
        failure_envelopes.len(),
        6,
        "5 strict failures + 1 hardened allowlisted failure envelope expected"
    );
    for envelope_path in &failure_envelopes {
        let payload: serde_json::Value =
            serde_json::from_str(&fs::read_to_string(envelope_path).expect("envelope readable"))
                .expect("envelope parseable");
        assert_eq!(payload["packet_id"].as_str(), Some("FNX-P2C-002"));
        assert!(
            payload["replay_command"]
                .as_str()
                .is_some_and(|cmd| { cmd.starts_with("rch exec --") })
        );
    }
}

#[test]
fn packet_003_differential_metamorphic_and_adversarial_taxonomy_is_deterministic() {
    let fixture_root = unique_fixture_root();
    write_fixture(
        &fixture_root,
        "dispatch_metamorphic_route_implicit_strict.json",
        r#"{
  "suite": "dispatch_v1",
  "mode": "strict",
  "fixture_id": "dispatch::metamorphic_route_implicit",
  "seed": 6303,
  "threat_class": "metamorphic_route_idempotence",
  "operations": [
    {
      "op": "dispatch_resolve",
      "operation": "shortest_path",
      "required_features": ["shortest_path"],
      "risk_probability": 0.2,
      "unknown_incompatible_feature": false
    }
  ],
  "expected": {
    "dispatch": {
      "selected_backend": "native",
      "action": "full_validate"
    }
  }
}"#,
    );
    write_fixture(
        &fixture_root,
        "dispatch_metamorphic_route_explicit_native_strict.json",
        r#"{
  "suite": "dispatch_v1",
  "mode": "strict",
  "fixture_id": "dispatch::metamorphic_route_explicit_native",
  "seed": 6303,
  "threat_class": "metamorphic_route_idempotence",
  "operations": [
    {
      "op": "dispatch_resolve",
      "operation": "shortest_path",
      "requested_backend": "native",
      "required_features": ["shortest_path"],
      "risk_probability": 0.2,
      "unknown_incompatible_feature": false
    }
  ],
  "expected": {
    "dispatch": {
      "selected_backend": "native",
      "action": "full_validate"
    }
  }
}"#,
    );
    write_fixture(
        &fixture_root,
        "dispatch_adversarial_parser_abuse_strict.json",
        r#"{
  "suite": "dispatch_v1",
  "mode": "strict",
  "fixture_id": "dispatch::adversarial_parser_abuse",
  "seed": 1103,
  "threat_class": "parser_abuse",
  "operations": [
    {
      "op": "dispatch_resolve",
      "operation": "shortest_path",
      "required_features": ["shortest_path"],
      "risk_probability": 0.2,
      "unknown_incompatible_feature": true
    }
  ],
  "expected": {}
}"#,
    );
    write_fixture(
        &fixture_root,
        "dispatch_adversarial_backend_route_ambiguity_strict.json",
        r#"{
  "suite": "dispatch_v1",
  "mode": "strict",
  "fixture_id": "dispatch::adversarial_backend_route_ambiguity",
  "seed": 6103,
  "threat_class": "backend_route_ambiguity",
  "operations": [
    {
      "op": "dispatch_resolve",
      "operation": "shortest_path",
      "requested_backend": "ghost-backend",
      "required_features": ["shortest_path"],
      "risk_probability": 0.2,
      "unknown_incompatible_feature": false
    }
  ],
  "expected": {}
}"#,
    );
    write_fixture(
        &fixture_root,
        "dispatch_adversarial_version_skew_strict.json",
        r#"{
  "suite": "dispatch_v1",
  "mode": "strict",
  "fixture_id": "dispatch::adversarial_version_skew",
  "seed": 3103,
  "threat_class": "version_skew",
  "operations": [
    {
      "op": "dispatch_resolve",
      "operation": "shortest_path",
      "required_features": ["shortest_path", "version_skew_marker"],
      "risk_probability": 0.2,
      "unknown_incompatible_feature": false
    }
  ],
  "expected": {}
}"#,
    );
    write_fixture(
        &fixture_root,
        "dispatch_adversarial_resource_exhaustion_strict.json",
        r#"{
  "suite": "dispatch_v1",
  "mode": "strict",
  "fixture_id": "dispatch::adversarial_resource_exhaustion",
  "seed": 4103,
  "threat_class": "resource_exhaustion",
  "operations": [
    {
      "op": "dispatch_resolve",
      "operation": "shortest_path",
      "required_features": ["shortest_path"],
      "risk_probability": 0.95,
      "unknown_incompatible_feature": false
    }
  ],
  "expected": {}
}"#,
    );
    write_fixture(
        &fixture_root,
        "dispatch_adversarial_state_corruption_strict.json",
        r#"{
  "suite": "dispatch_v1",
  "mode": "strict",
  "fixture_id": "dispatch::adversarial_state_corruption",
  "seed": 5103,
  "threat_class": "state_corruption",
  "operations": [
    {
      "op": "dispatch_resolve",
      "operation": "shortest_path",
      "required_features": ["cache_state_break_marker"],
      "risk_probability": 0.2,
      "unknown_incompatible_feature": false
    }
  ],
  "expected": {}
}"#,
    );
    write_fixture(
        &fixture_root,
        "dispatch_adversarial_metadata_ambiguity_hardened.json",
        r#"{
  "suite": "dispatch_v1",
  "mode": "hardened",
  "fixture_id": "dispatch::adversarial_metadata_ambiguity_hardened",
  "seed": 2203,
  "threat_class": "metadata_ambiguity",
  "hardened_allowlisted_categories": ["dispatch"],
  "operations": [
    {
      "op": "dispatch_resolve",
      "operation": "shortest_path",
      "requested_backend": "ghost-backend",
      "required_features": ["shortest_path"],
      "risk_probability": 0.2,
      "unknown_incompatible_feature": false
    }
  ],
  "expected": {}
}"#,
    );

    let mut cfg = HarnessConfig::default_paths();
    let report_root = unique_report_root();
    cfg.fixture_root = fixture_root;
    cfg.report_root = Some(report_root.clone());

    let report = run_smoke(&cfg);
    assert!(
        report.oracle_present,
        "legacy oracle root should be present"
    );
    assert_eq!(report.fixture_count, 8);
    assert_eq!(report.mismatch_count, 5);
    assert_eq!(report.hardened_allowlisted_count, 1);

    let metamorphic_implicit = report
        .fixture_reports
        .iter()
        .find(|fixture| fixture.fixture_id == "dispatch::metamorphic_route_implicit")
        .expect("metamorphic implicit fixture should exist");
    let metamorphic_explicit = report
        .fixture_reports
        .iter()
        .find(|fixture| fixture.fixture_id == "dispatch::metamorphic_route_explicit_native")
        .expect("metamorphic explicit fixture should exist");
    assert!(metamorphic_implicit.passed);
    assert!(metamorphic_explicit.passed);
    assert_eq!(metamorphic_implicit.seed, Some(6303));
    assert_eq!(metamorphic_explicit.seed, Some(6303));
    assert_eq!(
        metamorphic_implicit.threat_class.as_deref(),
        Some("metamorphic_route_idempotence")
    );
    assert_eq!(
        metamorphic_explicit.threat_class.as_deref(),
        Some("metamorphic_route_idempotence")
    );
    assert_eq!(metamorphic_implicit.strict_violation_count, 0);
    assert_eq!(metamorphic_explicit.strict_violation_count, 0);
    assert_eq!(metamorphic_implicit.hardened_allowlisted_count, 0);
    assert_eq!(metamorphic_explicit.hardened_allowlisted_count, 0);

    let hardened_metadata = report
        .fixture_reports
        .iter()
        .find(|fixture| fixture.fixture_id == "dispatch::adversarial_metadata_ambiguity_hardened")
        .expect("hardened metadata fixture should exist");
    assert!(hardened_metadata.passed);
    assert_eq!(
        hardened_metadata.reason_code.as_deref(),
        Some("hardened_allowlisted_mismatch")
    );
    assert_eq!(hardened_metadata.seed, Some(2203));
    assert_eq!(
        hardened_metadata.threat_class.as_deref(),
        Some("metadata_ambiguity")
    );
    assert_eq!(hardened_metadata.strict_violation_count, 0);
    assert_eq!(hardened_metadata.hardened_allowlisted_count, 1);
    assert!(
        hardened_metadata
            .mismatch_taxonomy
            .iter()
            .all(|entry| entry.classification == MismatchClassification::HardenedAllowlisted)
    );

    let strict_adversarial_fixture_ids = [
        "dispatch::adversarial_parser_abuse",
        "dispatch::adversarial_backend_route_ambiguity",
        "dispatch::adversarial_version_skew",
        "dispatch::adversarial_resource_exhaustion",
        "dispatch::adversarial_state_corruption",
    ];
    for fixture_id in strict_adversarial_fixture_ids {
        let fixture = report
            .fixture_reports
            .iter()
            .find(|row| row.fixture_id == fixture_id)
            .expect("strict adversarial fixture should exist");
        assert!(!fixture.passed);
        assert_eq!(fixture.reason_code.as_deref(), Some("mismatch"));
        assert_eq!(fixture.strict_violation_count, 1);
        assert_eq!(fixture.hardened_allowlisted_count, 0);
        assert!(
            fixture
                .mismatch_taxonomy
                .iter()
                .all(|entry| entry.classification == MismatchClassification::StrictViolation)
        );
    }

    let expected_seed_and_threat = BTreeMap::from([
        (
            "dispatch::adversarial_parser_abuse".to_owned(),
            (Some(1103_u64), Some("parser_abuse")),
        ),
        (
            "dispatch::adversarial_backend_route_ambiguity".to_owned(),
            (Some(6103_u64), Some("backend_route_ambiguity")),
        ),
        (
            "dispatch::adversarial_metadata_ambiguity_hardened".to_owned(),
            (Some(2203_u64), Some("metadata_ambiguity")),
        ),
        (
            "dispatch::adversarial_version_skew".to_owned(),
            (Some(3103_u64), Some("version_skew")),
        ),
        (
            "dispatch::adversarial_resource_exhaustion".to_owned(),
            (Some(4103_u64), Some("resource_exhaustion")),
        ),
        (
            "dispatch::adversarial_state_corruption".to_owned(),
            (Some(5103_u64), Some("state_corruption")),
        ),
    ]);
    for fixture in &report.fixture_reports {
        if let Some((expected_seed, expected_threat)) =
            expected_seed_and_threat.get(&fixture.fixture_id)
        {
            assert_eq!(&fixture.seed, expected_seed);
            assert_eq!(fixture.threat_class.as_deref(), *expected_threat);
        }
    }

    let taxonomy_raw = fs::read_to_string(report_root.join("mismatch_taxonomy_report.json"))
        .expect("drift taxonomy report should exist");
    let taxonomy: DriftTaxonomyReport =
        serde_json::from_str(&taxonomy_raw).expect("drift taxonomy report should parse");
    assert_eq!(taxonomy.strict_violation_count, 5);
    assert_eq!(taxonomy.hardened_allowlisted_count, 1);
    assert_eq!(taxonomy.fixtures.len(), 8);
    assert!(
        taxonomy
            .fixtures
            .iter()
            .all(|fixture| fixture.packet_id == "FNX-P2C-003")
    );
    let hardened_taxonomy_row = taxonomy
        .fixtures
        .iter()
        .find(|row| row.fixture_id == "dispatch::adversarial_metadata_ambiguity_hardened")
        .expect("hardened taxonomy row should exist");
    assert!(
        hardened_taxonomy_row
            .mismatches
            .iter()
            .all(|entry| entry.classification == MismatchClassification::HardenedAllowlisted)
    );

    let logs = read_structured_logs(&report_root);
    assert_eq!(logs.len(), 8);
    assert!(logs.iter().all(|log| log.packet_id == "FNX-P2C-003"));
    assert!(
        logs.iter()
            .all(|log| log.test_kind == TestKind::Differential)
    );
    assert!(
        logs.iter()
            .all(|log| log.replay_command.starts_with("rch exec --"))
    );
    for log in &logs {
        log.validate()
            .expect("differential structured log should satisfy schema");
        assert!(log.fixture_id.is_some());
        assert!(log.seed.is_some());
        assert!(!log.env_fingerprint.is_empty());
        assert!(log.environment.contains_key("fixture_id"));
    }

    let strict_failed_logs = logs
        .iter()
        .filter(|log| {
            strict_adversarial_fixture_ids.contains(&log.fixture_id.as_deref().unwrap_or_default())
        })
        .collect::<Vec<&StructuredTestLog>>();
    assert_eq!(strict_failed_logs.len(), 5);
    assert!(
        strict_failed_logs
            .iter()
            .all(|log| log.status == TestStatus::Failed)
    );
    assert!(
        strict_failed_logs
            .iter()
            .all(|log| log.failure_repro.is_some())
    );
    assert!(
        strict_failed_logs
            .iter()
            .all(|log| log.reason_code.as_deref() == Some("mismatch"))
    );

    let hardened_log = logs
        .iter()
        .find(|log| {
            log.fixture_id.as_deref() == Some("dispatch::adversarial_metadata_ambiguity_hardened")
        })
        .expect("hardened adversarial log should exist");
    assert_eq!(hardened_log.status, TestStatus::Passed);
    assert_eq!(
        hardened_log.reason_code.as_deref(),
        Some("hardened_allowlisted_mismatch")
    );
    assert!(hardened_log.failure_repro.is_none());
    assert_eq!(hardened_log.seed, Some(2203));
    assert_eq!(
        hardened_log
            .environment
            .get("threat_class")
            .map(String::as_str),
        Some("metadata_ambiguity")
    );

    let failure_envelopes = fs::read_dir(&report_root)
        .expect("report root should be readable")
        .filter_map(Result::ok)
        .map(|entry| entry.path())
        .filter(|path| {
            path.file_name()
                .and_then(|name| name.to_str())
                .is_some_and(|name| name.ends_with(".failure_envelope.json"))
        })
        .collect::<Vec<PathBuf>>();
    assert_eq!(
        failure_envelopes.len(),
        6,
        "5 strict failures + 1 hardened allowlisted failure envelope expected"
    );
    for envelope_path in &failure_envelopes {
        let payload: serde_json::Value =
            serde_json::from_str(&fs::read_to_string(envelope_path).expect("envelope readable"))
                .expect("envelope parseable");
        assert_eq!(payload["packet_id"].as_str(), Some("FNX-P2C-003"));
        assert!(
            payload["replay_command"]
                .as_str()
                .is_some_and(|cmd| { cmd.starts_with("rch exec --") })
        );
    }
}

proptest! {
    #[test]
    fn property_packet_002_projection_matches_first_seen_neighbors(
        edges in prop::collection::vec((0_u8..8, 0_u8..8), 1..40)
    ) {
        let anchor = "n0";
        let mut graph = Graph::strict();
        for (left, right) in &edges {
            graph
                .add_edge(format!("n{left}"), format!("n{right}"))
                .expect("generated edge inserts should succeed");
        }

        let actual = neighbors_for_node(&graph, anchor);
        let mut expected = Vec::new();
        for (left, right) in edges {
            let left_name = format!("n{left}");
            let right_name = format!("n{right}");
            if left_name == anchor && !expected.contains(&right_name) {
                expected.push(right_name.clone());
            }
            if right_name == anchor && !expected.contains(&left_name) {
                expected.push(left_name);
            }
        }

        prop_assert_eq!(
            actual,
            expected,
            "projection order drifted; proptest should shrink to minimal edge counterexample"
        );
    }

    #[test]
    fn property_packet_002_missing_node_is_none(
        edges in prop::collection::vec((0_u8..8, 0_u8..8), 0..40)
    ) {
        let mut graph = Graph::strict();
        for (left, right) in edges {
            graph
                .add_edge(format!("n{left}"), format!("n{right}"))
                .expect("generated edge inserts should succeed");
        }

        prop_assert!(
            GraphView::new(&graph).neighbors("__missing_node__").is_none(),
            "missing nodes must not materialize synthetic neighbor lists"
        );
    }

    #[test]
    fn property_packet_002_graph_view_snapshot_matches_graph_snapshot(
        edges in prop::collection::vec((0_u8..8, 0_u8..8), 0..40)
    ) {
        let mut graph = Graph::strict();
        for (left, right) in edges {
            graph
                .add_edge(format!("n{left}"), format!("n{right}"))
                .expect("generated edge inserts should succeed");
        }

        let view_snapshot = GraphView::new(&graph).snapshot();
        prop_assert_eq!(
            view_snapshot,
            graph.snapshot(),
            "view snapshot drift indicates projection/state desynchronization"
        );
    }

    #[test]
    fn property_packet_002_cached_snapshot_detects_revision_changes(
        edges in prop::collection::vec((0_u8..8, 0_u8..8), 0..40)
    ) {
        let mut graph = Graph::strict();
        for (left, right) in edges {
            graph
                .add_edge(format!("n{left}"), format!("n{right}"))
                .expect("generated edge inserts should succeed");
        }
        let mut cached = CachedSnapshotView::new(&graph);
        let old_revision = cached.cached_revision();

        graph
            .add_edge("__mutation_left__", "__mutation_right__")
            .expect("mutation edge should insert");
        prop_assert!(
            cached.is_stale(&graph),
            "cached snapshot should detect monotonic revision mismatch"
        );
        prop_assert!(
            cached.refresh_if_stale(&graph),
            "refresh_if_stale should perform exactly one refresh when stale"
        );
        prop_assert!(
            cached.cached_revision() > old_revision,
            "cache revision should advance after refresh"
        );
        prop_assert!(!cached.is_stale(&graph), "cache should be fresh after refresh");
        prop_assert_eq!(
            cached.snapshot(),
            &graph.snapshot(),
            "refreshed cache snapshot should match graph snapshot exactly"
        );
    }

    #[test]
    fn property_packet_002_cached_snapshot_refresh_is_idempotent_when_fresh(
        edges in prop::collection::vec((0_u8..8, 0_u8..8), 0..40)
    ) {
        let mut graph = Graph::strict();
        for (left, right) in edges {
            graph
                .add_edge(format!("n{left}"), format!("n{right}"))
                .expect("generated edge inserts should succeed");
        }
        let mut cached = CachedSnapshotView::new(&graph);
        let baseline = cached.snapshot().clone();

        prop_assert!(
            !cached.refresh_if_stale(&graph),
            "refresh_if_stale should be a no-op when revision is unchanged"
        );
        prop_assert_eq!(
            cached.snapshot(),
            &baseline,
            "no-op refresh should preserve cached snapshot byte-for-byte"
        );
    }
}
