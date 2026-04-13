use fnx_runtime::StructuredTestLog;
use std::fs;
use std::path::PathBuf;

fn fixture_path(name: &str) -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("tests")
        .join("fixtures")
        .join(name)
}

fn parse_fixture(name: &str) -> StructuredTestLog {
    let raw = fs::read_to_string(fixture_path(name)).expect("fixture should be readable");
    serde_json::from_str::<StructuredTestLog>(&raw).expect("fixture should deserialize")
}

#[test]
fn rejects_unsupported_schema_version_fixture() {
    let log = parse_fixture("structured_log_unsupported_schema_version.json");
    let err = log
        .validate()
        .expect_err("unsupported schema should fail closed");
    assert!(err.contains("unsupported schema_version"));
}

#[test]
fn rejects_missing_replay_command_fixture() {
    let log = parse_fixture("structured_log_missing_replay_command.json");
    let err = log
        .validate()
        .expect_err("missing replay command should fail closed");
    assert!(err.contains("replay_command must be non-empty"));
}

#[test]
fn rejects_failed_fixture_without_artifact_hash_id() {
    let log = parse_fixture("structured_log_failed_missing_artifact_hash.json");
    let err = log
        .validate()
        .expect_err("failed fixture without artifact hash should fail closed");
    assert!(err.contains("artifact_hash_id"));
}

#[test]
fn rejects_fixture_missing_replay_critical_field_at_deserialize_time() {
    let raw = fs::read_to_string(fixture_path("structured_log_missing_env_fingerprint.json"))
        .expect("fixture should be readable");
    let err = serde_json::from_str::<StructuredTestLog>(&raw)
        .expect_err("missing env_fingerprint should be rejected");
    assert!(err.to_string().contains("env_fingerprint"));
}

#[test]
fn rejects_missing_forensics_bundle_index() {
    let log = parse_fixture("structured_log_missing_bundle_index.json");
    let err = log
        .validate()
        .expect_err("missing forensics bundle index should fail closed");
    assert!(err.contains("forensics_bundle_index is required"));
}

#[test]
fn rejects_bundle_id_mismatch() {
    let log = parse_fixture("structured_log_bundle_id_mismatch.json");
    let err = log
        .validate()
        .expect_err("bundle_id mismatch should fail closed");
    assert!(err.contains("bundle_id must match forensic_bundle_id"));
}

#[test]
fn rejects_packet_003_missing_required_env_key() {
    let log = parse_fixture("structured_log_missing_env_key_packet003.json");
    let err = log
        .validate()
        .expect_err("packet-003 missing env key should fail closed");
    assert!(err.contains("packet-003 unit contract telemetry missing required environment key"));
}

#[test]
fn rejects_bundle_replay_ref_mismatch() {
    let log = parse_fixture("structured_log_bundle_replay_ref_mismatch.json");
    let err = log
        .validate()
        .expect_err("bundle replay_ref mismatch should fail closed");
    assert!(err.contains("forensics_bundle_index.replay_ref must match replay_command"));
}

#[test]
fn rejects_bundle_run_id_mismatch() {
    let log = parse_fixture("structured_log_bundle_run_id_mismatch.json");
    let err = log
        .validate()
        .expect_err("bundle run_id mismatch should fail closed");
    assert!(err.contains("forensics_bundle_index.run_id must match run_id"));
}

#[test]
fn rejects_empty_artifact_refs() {
    let log = parse_fixture("structured_log_empty_artifact_refs.json");
    let err = log
        .validate()
        .expect_err("empty artifact refs should fail closed");
    assert!(err.contains("artifact_refs must include at least one artifact path/ref"));
}

#[test]
fn rejects_e2e_missing_step_traces() {
    let log = parse_fixture("structured_log_e2e_missing_steps.json");
    let err = log
        .validate()
        .expect_err("e2e logs without step traces should fail closed");
    assert!(err.contains("e2e_step_traces are required when test_kind=e2e"));
}
