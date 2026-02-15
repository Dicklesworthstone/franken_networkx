use fnx_runtime::{
    CompatibilityMode, E2eStepStatus, E2eStepTrace, FailureReproData, ForensicsBundleIndex,
    FtuiTelemetryAdapter, StructuredTestLog, TestKind, TestStatus,
    canonical_environment_fingerprint, ftui_telemetry_canonical_fields,
    structured_test_log_schema_version,
};
use serde_json::Value;
use std::collections::{BTreeMap, BTreeSet};
use std::fs;
use std::path::{Path, PathBuf};

fn repo_root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../..")
}

fn load_json(path: &Path) -> Value {
    let raw = fs::read_to_string(path)
        .unwrap_or_else(|err| panic!("expected readable json at {}: {err}", path.display()));
    serde_json::from_str(&raw)
        .unwrap_or_else(|err| panic!("expected valid json at {}: {err}", path.display()))
}

fn required_string_array<'a>(schema: &'a Value, key: &str) -> Vec<&'a str> {
    schema[key]
        .as_array()
        .unwrap_or_else(|| panic!("schema key `{key}` should be array"))
        .iter()
        .map(|value| {
            value
                .as_str()
                .unwrap_or_else(|| panic!("schema key `{key}` entry should be string"))
        })
        .collect()
}

fn assert_path(path: &str, ctx: &str, root: &Path) {
    assert!(
        !path.trim().is_empty(),
        "{ctx} should be non-empty path string"
    );
    let full = root.join(path);
    assert!(full.exists(), "{ctx} path missing: {}", full.display());
}

fn base_env() -> BTreeMap<String, String> {
    let mut env = BTreeMap::new();
    env.insert("arch".to_owned(), "x86_64".to_owned());
    env.insert("os".to_owned(), "linux".to_owned());
    env.insert("ci".to_owned(), "true".to_owned());
    env
}

fn base_bundle(
    run_id: &str,
    test_id: &str,
    bundle_id: &str,
    artifact_refs: Vec<String>,
) -> ForensicsBundleIndex {
    ForensicsBundleIndex {
        bundle_id: bundle_id.to_owned(),
        run_id: run_id.to_owned(),
        test_id: test_id.to_owned(),
        bundle_hash_id: format!("bundle-hash::{bundle_id}"),
        captured_unix_ms: 10,
        replay_ref: "rch exec -- cargo test -p fnx-conformance -- --nocapture".to_owned(),
        artifact_refs,
        raptorq_sidecar_refs: Vec::new(),
        decode_proof_refs: Vec::new(),
    }
}

fn base_log(
    run_id: &str,
    test_id: &str,
    suite_id: &str,
    ts_unix_ms: u128,
    status: TestStatus,
    reason_code: Option<&str>,
) -> StructuredTestLog {
    let env = base_env();
    let bundle_id = format!("forensics::{suite_id}::{test_id}");
    let replay = "rch exec -- cargo test -p fnx-conformance -- --nocapture";
    let failure_repro = match status {
        TestStatus::Failed => Some(FailureReproData {
            failure_message: "telemetry-adapter failure".to_owned(),
            reproduction_command: replay.to_owned(),
            expected_behavior: "completed".to_owned(),
            observed_behavior: "failed_closed".to_owned(),
            seed: Some(19),
            fixture_id: Some("fixture-telemetry-001".to_owned()),
            artifact_hash_id: Some(format!("sha256:{run_id}:{test_id}")),
            forensics_link: Some("artifacts/conformance/latest/structured_logs.jsonl".to_owned()),
        }),
        TestStatus::Passed | TestStatus::Skipped => None,
    };

    StructuredTestLog {
        schema_version: structured_test_log_schema_version().to_owned(),
        run_id: run_id.to_owned(),
        ts_unix_ms,
        crate_name: "fnx-conformance".to_owned(),
        suite_id: suite_id.to_owned(),
        packet_id: "FNX-P2C-FTUI".to_owned(),
        test_name: format!("test::{test_id}"),
        test_id: test_id.to_owned(),
        test_kind: TestKind::E2e,
        mode: CompatibilityMode::Strict,
        fixture_id: Some("fixture-telemetry-001".to_owned()),
        seed: Some(19),
        environment: env.clone(),
        env_fingerprint: canonical_environment_fingerprint(&env),
        duration_ms: 35,
        replay_command: replay.to_owned(),
        artifact_refs: vec![
            "artifacts/e2e/latest/e2e_scenario_matrix_steps_v1.jsonl".to_owned(),
            "artifacts/conformance/latest/structured_logs.jsonl".to_owned(),
        ],
        forensic_bundle_id: bundle_id.clone(),
        hash_id: format!("sha256:{run_id}:{test_id}"),
        status,
        reason_code: reason_code.map(ToOwned::to_owned),
        failure_repro,
        e2e_step_traces: vec![E2eStepTrace {
            run_id: run_id.to_owned(),
            test_id: test_id.to_owned(),
            step_id: format!("step::{test_id}"),
            step_label: "telemetry-step".to_owned(),
            phase: "execute".to_owned(),
            status: match status {
                TestStatus::Passed => E2eStepStatus::Passed,
                TestStatus::Failed => E2eStepStatus::Failed,
                TestStatus::Skipped => E2eStepStatus::Skipped,
            },
            start_unix_ms: ts_unix_ms,
            end_unix_ms: ts_unix_ms + 35,
            duration_ms: 35,
            replay_command: replay.to_owned(),
            forensic_bundle_id: bundle_id.clone(),
            artifact_refs: vec![
                "artifacts/e2e/latest/e2e_scenario_matrix_steps_v1.jsonl".to_owned(),
            ],
            hash_id: format!("step-hash::{run_id}:{test_id}"),
            reason_code: reason_code.map(ToOwned::to_owned),
        }],
        forensics_bundle_index: Some(base_bundle(
            run_id,
            test_id,
            &bundle_id,
            vec![
                "artifacts/e2e/latest/e2e_scenario_matrix_steps_v1.jsonl".to_owned(),
                "artifacts/conformance/latest/structured_logs.jsonl".to_owned(),
            ],
        )),
    }
}

#[test]
fn ftui_telemetry_adapter_contract_is_complete_and_fail_closed() {
    let root = repo_root();
    let artifact = load_json(&root.join("artifacts/ftui/v1/ftui_telemetry_adapter_v1.json"));
    let schema =
        load_json(&root.join("artifacts/ftui/schema/v1/ftui_telemetry_adapter_schema_v1.json"));

    for key in required_string_array(&schema, "required_top_level_keys") {
        assert!(
            artifact.get(key).is_some(),
            "artifact missing top-level key `{key}`"
        );
    }

    let adapter_interface = artifact["adapter_interface"]
        .as_object()
        .expect("adapter_interface should be object");
    for key in required_string_array(&schema, "required_adapter_interface_keys") {
        assert!(
            adapter_interface.get(key).is_some(),
            "adapter_interface missing key `{key}`"
        );
    }
    assert_eq!(
        adapter_interface["owning_crate"]
            .as_str()
            .expect("owning_crate should be string"),
        "fnx-runtime"
    );
    let module_path = adapter_interface["module_path"]
        .as_str()
        .expect("module_path should be string");
    assert_path(module_path, "adapter_interface.module_path", &root);
    let runtime_source =
        fs::read_to_string(root.join(module_path)).expect("runtime source path should be readable");
    for symbol in [
        "FtuiTelemetryAdapter",
        "FtuiArtifactIndex",
        "ftui_telemetry_canonical_fields",
        "build_artifact_index",
        "TelemetryArtifactIndexAdapter",
    ] {
        assert!(
            runtime_source.contains(symbol),
            "runtime source missing required symbol `{symbol}`"
        );
    }

    let ingestion = artifact["ingestion_contract"]
        .as_object()
        .expect("ingestion_contract should be object");
    for key in required_string_array(&schema, "required_ingestion_contract_keys") {
        assert!(
            ingestion.get(key).is_some(),
            "ingestion_contract missing key `{key}`"
        );
    }
    assert_eq!(
        ingestion["unknown_field_policy"]
            .as_str()
            .expect("unknown_field_policy should be string"),
        "fail_closed"
    );
    assert_eq!(
        ingestion["incompatible_payload_policy"]
            .as_str()
            .expect("incompatible_payload_policy should be string"),
        "fail_closed_with_diagnostics"
    );
    let required_fields = required_string_array(&schema, "required_fields")
        .into_iter()
        .collect::<BTreeSet<_>>();
    let observed_fields = ingestion["required_fields"]
        .as_array()
        .expect("ingestion.required_fields should be array")
        .iter()
        .map(|value| value.as_str().expect("required field should be string"))
        .collect::<BTreeSet<_>>();
    assert_eq!(
        observed_fields, required_fields,
        "required fields drifted from schema"
    );

    let runtime_fields = ftui_telemetry_canonical_fields()
        .iter()
        .copied()
        .collect::<BTreeSet<_>>();
    assert_eq!(
        runtime_fields, required_fields,
        "runtime canonical field set drifted"
    );

    let index_contract = artifact["artifact_index_contract"]
        .as_object()
        .expect("artifact_index_contract should be object");
    for key in required_string_array(&schema, "required_artifact_index_keys") {
        assert!(
            index_contract.get(key).is_some(),
            "artifact_index_contract missing key `{key}`"
        );
    }
    let required_row_keys = required_string_array(&schema, "required_row_keys")
        .into_iter()
        .collect::<BTreeSet<_>>();
    let observed_row_keys = index_contract["row_keys"]
        .as_array()
        .expect("artifact_index_contract.row_keys should be array")
        .iter()
        .map(|value| value.as_str().expect("row_key should be string"))
        .collect::<BTreeSet<_>>();
    assert_eq!(
        observed_row_keys, required_row_keys,
        "row keys drifted from schema"
    );

    let failure_modes = artifact["failure_modes"]
        .as_array()
        .expect("failure_modes should be array");
    assert!(
        !failure_modes.is_empty(),
        "failure_modes should be non-empty"
    );
    let required_failure_mode_keys = required_string_array(&schema, "required_failure_mode_keys");
    let required_failure_codes = required_string_array(&schema, "required_failure_codes")
        .into_iter()
        .collect::<BTreeSet<_>>();
    let mut observed_failure_codes = BTreeSet::new();
    for (idx, mode) in failure_modes.iter().enumerate() {
        for key in &required_failure_mode_keys {
            assert!(
                mode.get(*key).is_some(),
                "failure_modes[{idx}] missing key `{key}`"
            );
        }
        let reason_code = mode["reason_code"]
            .as_str()
            .expect("failure_modes.reason_code should be string");
        observed_failure_codes.insert(reason_code);
        assert_eq!(
            mode["action"]
                .as_str()
                .expect("failure_modes.action should be string"),
            "fail_closed",
            "failure mode `{reason_code}` should fail closed"
        );
    }
    assert!(
        required_failure_codes.is_subset(&observed_failure_codes),
        "failure_modes missing required reason codes"
    );

    let test_bindings = artifact["test_bindings"]
        .as_array()
        .expect("test_bindings should be array");
    assert!(
        !test_bindings.is_empty(),
        "test_bindings should be non-empty"
    );
    let required_test_binding_keys = required_string_array(&schema, "required_test_binding_keys");
    let required_layers = required_string_array(&schema, "required_test_layers")
        .into_iter()
        .collect::<BTreeSet<_>>();
    let mut observed_layers = BTreeSet::new();
    let mut observed_test_ids = BTreeSet::new();
    for (idx, binding) in test_bindings.iter().enumerate() {
        for key in &required_test_binding_keys {
            assert!(
                binding.get(*key).is_some(),
                "test_bindings[{idx}] missing key `{key}`"
            );
        }
        let test_id = binding["test_id"]
            .as_str()
            .expect("test_id should be string");
        assert!(
            observed_test_ids.insert(test_id),
            "duplicate test_id `{test_id}` in test_bindings"
        );
        let layer = binding["layer"].as_str().expect("layer should be string");
        assert!(
            required_layers.contains(layer),
            "unexpected layer `{layer}`"
        );
        observed_layers.insert(layer);
        assert_path(
            binding["artifact_path"]
                .as_str()
                .expect("artifact_path should be string"),
            &format!("test_bindings[{idx}].artifact_path"),
            &root,
        );
        assert!(
            binding["replay_command"]
                .as_str()
                .expect("replay_command should be string")
                .contains("rch exec --"),
            "test_bindings[{idx}] replay_command should use rch"
        );
    }
    assert_eq!(
        observed_layers, required_layers,
        "test binding layers should cover unit/differential/e2e"
    );

    let decision_contract = artifact["decision_theoretic_runtime_contract"]
        .as_object()
        .expect("decision_theoretic_runtime_contract should be object");
    for key in required_string_array(&schema, "required_decision_contract_keys") {
        assert!(
            decision_contract.get(key).is_some(),
            "decision_theoretic_runtime_contract missing key `{key}`"
        );
    }
    let loss_budget = decision_contract["loss_budget"]
        .as_object()
        .expect("loss_budget should be object");
    for key in required_string_array(&schema, "required_loss_budget_keys") {
        assert!(
            loss_budget.get(key).is_some(),
            "loss_budget missing key `{key}`"
        );
    }
    let safe_mode_fallback = decision_contract["safe_mode_fallback"]
        .as_object()
        .expect("safe_mode_fallback should be object");
    for key in required_string_array(&schema, "required_safe_mode_fallback_keys") {
        assert!(
            safe_mode_fallback.get(key).is_some(),
            "safe_mode_fallback missing key `{key}`"
        );
    }

    let profile = artifact["profile_first_artifacts"]
        .as_object()
        .expect("profile_first_artifacts should be object");
    for key in required_string_array(&schema, "required_profile_artifact_keys") {
        assert_path(
            profile[key]
                .as_str()
                .expect("profile artifact path should be string"),
            &format!("profile_first_artifacts.{key}"),
            &root,
        );
    }

    let isomorphism = artifact["isomorphism_proof_artifacts"]
        .as_array()
        .expect("isomorphism_proof_artifacts should be array");
    assert!(
        !isomorphism.is_empty(),
        "isomorphism_proof_artifacts should be non-empty"
    );
    for (idx, path_text) in isomorphism.iter().enumerate() {
        assert_path(
            path_text
                .as_str()
                .unwrap_or_else(|| panic!("isomorphism_proof_artifacts[{idx}] should be string")),
            &format!("isomorphism_proof_artifacts[{idx}]"),
            &root,
        );
    }
    let logging = artifact["structured_logging_evidence"]
        .as_array()
        .expect("structured_logging_evidence should be array");
    assert!(
        !logging.is_empty(),
        "structured_logging_evidence should be non-empty"
    );
    for (idx, path_text) in logging.iter().enumerate() {
        assert_path(
            path_text
                .as_str()
                .unwrap_or_else(|| panic!("structured_logging_evidence[{idx}] should be string")),
            &format!("structured_logging_evidence[{idx}]"),
            &root,
        );
    }

    let adapter = FtuiTelemetryAdapter::strict_default();
    let mut unknown_row = BTreeMap::new();
    for field in ftui_telemetry_canonical_fields() {
        unknown_row.insert((*field).to_owned(), "x".to_owned());
    }
    unknown_row.insert("unknown_field".to_owned(), "boom".to_owned());
    let unknown_err = adapter
        .ingest_row(&unknown_row)
        .expect_err("unknown fields should fail closed");
    assert!(unknown_err.contains("unknown telemetry field"));
    assert!(unknown_err.contains("allowed fields"));

    let log_a = base_log(
        "run-2",
        "tests::b",
        "suite-b",
        2_000,
        TestStatus::Passed,
        None,
    );
    let log_b = base_log(
        "run-1",
        "tests::a",
        "suite-a",
        1_000,
        TestStatus::Passed,
        None,
    );
    let log_c = base_log(
        "run-3",
        "tests::c",
        "suite-c",
        2_000,
        TestStatus::Failed,
        Some("integrity_precheck_failed"),
    );

    let index_one = adapter
        .build_artifact_index(&[log_a.clone(), log_b.clone(), log_c.clone()])
        .expect("artifact index build should succeed");
    let index_two = adapter
        .build_artifact_index(&[log_c.clone(), log_b.clone(), log_a.clone()])
        .expect("artifact index build should succeed");
    assert_eq!(
        index_one, index_two,
        "artifact index ordering should be deterministic across repeated runs"
    );
    assert_eq!(index_one.entries.len(), 3);
    assert_eq!(index_one.entries[0].run_id, "run-1");
    assert_eq!(index_one.entries[1].run_id, "run-2");
    assert_eq!(index_one.entries[2].run_id, "run-3");

    let event_one = adapter
        .from_structured_log(&log_a)
        .expect("from_structured_log should succeed");
    let event_two = adapter
        .from_structured_log(&log_a)
        .expect("from_structured_log should be deterministic");
    assert_eq!(event_one.correlation_id, event_two.correlation_id);

    let mut incompatible = log_b;
    incompatible.forensics_bundle_index = None;
    let incompatible_err = adapter
        .from_structured_log(&incompatible)
        .expect_err("missing forensics_bundle_index should fail closed");
    assert!(incompatible_err.contains("forensics_bundle_index"));
}
