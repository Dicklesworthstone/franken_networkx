use fnx_conformance::{HarnessConfig, run_smoke};
use fnx_runtime::{StructuredTestLog, TestKind};
use std::fs;
use std::path::PathBuf;
use std::time::{SystemTime, UNIX_EPOCH};

fn unique_report_root() -> PathBuf {
    let nonce = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map_or(0, |dur| dur.as_millis());
    std::env::temp_dir().join(format!("fnx_conformance_smoke_{nonce}"))
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
