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
