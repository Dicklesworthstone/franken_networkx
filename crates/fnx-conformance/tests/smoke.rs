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
    for log in logs {
        log.validate().expect("log should satisfy schema contract");
        assert_eq!(log.test_kind, TestKind::Differential);
        assert_eq!(log.crate_name, "fnx-conformance");
        assert!(log.packet_id.starts_with("FNX-P2C-"));
    }
}
