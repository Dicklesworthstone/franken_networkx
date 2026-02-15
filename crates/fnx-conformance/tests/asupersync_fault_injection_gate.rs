use fnx_runtime::{
    AsupersyncAdapterMachine, AsupersyncAdapterReasonCode, AsupersyncAdapterState,
    AsupersyncTransferIntent, CompatibilityMode,
};
use serde_json::Value;
use std::collections::BTreeSet;
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

fn base_intent() -> AsupersyncTransferIntent {
    AsupersyncTransferIntent {
        transfer_id: "tx-fault-gate-001".to_owned(),
        artifact_id: "artifacts/e2e/latest/e2e_scenario_matrix_report_v1.json".to_owned(),
        artifact_class: "conformance_fixture_bundle".to_owned(),
        mode: CompatibilityMode::Strict,
        deterministic_seed: 23,
        expected_checksum: "sha256:expected-fault-gate".to_owned(),
        max_attempts: 3,
    }
}

#[test]
fn asupersync_fault_injection_contract_is_complete_and_fail_closed() {
    let root = repo_root();
    let artifact =
        load_json(&root.join("artifacts/asupersync/v1/asupersync_fault_injection_suite_v1.json"));
    let schema = load_json(
        &root.join("artifacts/asupersync/schema/v1/asupersync_fault_injection_schema_v1.json"),
    );

    for key in required_string_array(&schema, "required_top_level_keys") {
        assert!(
            artifact.get(key).is_some(),
            "artifact missing top-level key `{key}`"
        );
    }

    let summary = artifact["suite_summary"]
        .as_object()
        .expect("suite_summary should be object");
    for key in required_string_array(&schema, "required_suite_summary_keys") {
        assert!(
            summary.get(key).is_some(),
            "suite_summary missing key `{key}`"
        );
    }
    let fault_classes = artifact["fault_classes"]
        .as_array()
        .expect("fault_classes should be array");
    assert!(
        !fault_classes.is_empty(),
        "fault_classes should be non-empty"
    );
    assert_eq!(
        usize::try_from(
            summary["fault_class_count"]
                .as_u64()
                .expect("fault_class_count should be u64"),
        )
        .expect("fault_class_count should fit usize"),
        fault_classes.len(),
        "suite_summary.fault_class_count should match fault class rows"
    );

    let required_fault_types = required_string_array(&schema, "required_fault_types")
        .into_iter()
        .collect::<BTreeSet<_>>();
    let required_reason_codes = required_string_array(&schema, "required_reason_codes")
        .into_iter()
        .collect::<BTreeSet<_>>();
    let required_log_fields = required_string_array(&schema, "required_log_fields")
        .into_iter()
        .collect::<BTreeSet<_>>();

    let required_fault_keys = required_string_array(&schema, "required_fault_class_keys");
    let mut observed_fault_ids = BTreeSet::new();
    let mut observed_fault_types = BTreeSet::new();
    let mut observed_reason_codes = BTreeSet::new();
    for (idx, row) in fault_classes.iter().enumerate() {
        for key in &required_fault_keys {
            assert!(
                row.get(*key).is_some(),
                "fault_classes[{idx}] missing key `{key}`"
            );
        }
        let fault_id = row["fault_id"].as_str().expect("fault_id should be string");
        assert!(
            observed_fault_ids.insert(fault_id),
            "duplicate fault_id `{fault_id}`"
        );
        let fault_type = row["fault_type"]
            .as_str()
            .expect("fault_type should be string");
        assert!(
            required_fault_types.contains(fault_type),
            "unsupported fault_type `{fault_type}`"
        );
        observed_fault_types.insert(fault_type);
        let expected_reason = row["expected_reason_code"]
            .as_str()
            .expect("expected_reason_code should be string");
        assert!(
            required_reason_codes.contains(expected_reason),
            "unsupported expected_reason_code `{expected_reason}`"
        );
        observed_reason_codes.insert(expected_reason);
        assert_eq!(
            row["expected_terminal_state"]
                .as_str()
                .expect("expected_terminal_state should be string"),
            "failed_closed"
        );
        let invariant_checks = row["invariant_checks"]
            .as_array()
            .expect("invariant_checks should be array");
        assert!(
            !invariant_checks.is_empty(),
            "fault_classes[{idx}].invariant_checks should be non-empty"
        );
        let row_log_fields = row["log_fields"]
            .as_array()
            .expect("log_fields should be array")
            .iter()
            .map(|value| value.as_str().expect("log field should be string"))
            .collect::<BTreeSet<_>>();
        assert!(
            required_log_fields.is_subset(&row_log_fields),
            "fault_classes[{idx}].log_fields missing required fields"
        );
    }
    assert_eq!(
        observed_fault_types, required_fault_types,
        "fault type set drifted from schema"
    );
    assert!(
        required_reason_codes.is_subset(&observed_reason_codes),
        "fault reason code coverage is incomplete"
    );

    let log_contract = artifact["structured_log_contract"]
        .as_object()
        .expect("structured_log_contract should be object");
    for key in required_string_array(&schema, "required_log_contract_keys") {
        assert!(
            log_contract.get(key).is_some(),
            "structured_log_contract missing key `{key}`"
        );
    }
    let observed_required_fields = log_contract["required_fields"]
        .as_array()
        .expect("required_fields should be array")
        .iter()
        .map(|value| value.as_str().expect("required field should be string"))
        .collect::<BTreeSet<_>>();
    assert_eq!(
        observed_required_fields, required_log_fields,
        "structured_log_contract.required_fields drifted from schema"
    );
    assert!(
        log_contract["fail_closed_policy"]
            .as_str()
            .expect("fail_closed_policy should be string")
            .contains("fail closed"),
        "structured_log_contract.fail_closed_policy should explicitly describe fail-closed policy"
    );

    let repro_commands = artifact["repro_commands"]
        .as_array()
        .expect("repro_commands should be array");
    assert!(
        !repro_commands.is_empty(),
        "repro_commands should be non-empty"
    );
    let required_repro_keys = required_string_array(&schema, "required_repro_command_keys");
    let mut repro_fault_ids = BTreeSet::new();
    for (idx, row) in repro_commands.iter().enumerate() {
        for key in &required_repro_keys {
            assert!(
                row.get(*key).is_some(),
                "repro_commands[{idx}] missing key `{key}`"
            );
        }
        let fault_id = row["fault_id"].as_str().expect("fault_id should be string");
        assert!(
            observed_fault_ids.contains(fault_id),
            "repro_commands[{idx}] references unknown fault_id `{fault_id}`"
        );
        assert!(
            repro_fault_ids.insert(fault_id),
            "duplicate repro command for fault_id `{fault_id}`"
        );
        assert!(
            row["replay_command"]
                .as_str()
                .expect("replay_command should be string")
                .contains("rch exec --"),
            "repro_commands[{idx}] replay_command should use rch"
        );
        assert!(
            !row["expected_outcome"]
                .as_str()
                .expect("expected_outcome should be string")
                .trim()
                .is_empty(),
            "repro_commands[{idx}] expected_outcome should be non-empty"
        );
    }
    assert_eq!(
        repro_fault_ids, observed_fault_ids,
        "repro command coverage should include every fault_id"
    );

    let test_bindings = artifact["test_bindings"]
        .as_array()
        .expect("test_bindings should be array");
    assert!(
        !test_bindings.is_empty(),
        "test_bindings should be non-empty"
    );
    let required_test_binding_keys = required_string_array(&schema, "required_test_binding_keys");
    let required_test_layers = required_string_array(&schema, "required_test_layers")
        .into_iter()
        .collect::<BTreeSet<_>>();
    let mut observed_layers = BTreeSet::new();
    let mut observed_test_ids = BTreeSet::new();
    for (idx, row) in test_bindings.iter().enumerate() {
        for key in &required_test_binding_keys {
            assert!(
                row.get(*key).is_some(),
                "test_bindings[{idx}] missing key `{key}`"
            );
        }
        let test_id = row["test_id"].as_str().expect("test_id should be string");
        assert!(
            observed_test_ids.insert(test_id),
            "duplicate test_id `{test_id}` in test_bindings"
        );
        let layer = row["layer"].as_str().expect("layer should be string");
        assert!(
            required_test_layers.contains(layer),
            "unsupported test layer `{layer}`"
        );
        observed_layers.insert(layer);
        assert_path(
            row["artifact_path"]
                .as_str()
                .expect("artifact_path should be string"),
            &format!("test_bindings[{idx}].artifact_path"),
            &root,
        );
        assert!(
            row["replay_command"]
                .as_str()
                .expect("replay_command should be string")
                .contains("rch exec --"),
            "test_bindings[{idx}] replay_command should use rch"
        );
    }
    assert_eq!(
        observed_layers, required_test_layers,
        "test binding layers should cover unit/property/differential/e2e"
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

    let runtime_source = fs::read_to_string(root.join("crates/fnx-runtime/src/lib.rs"))
        .expect("expected readable runtime source");
    for symbol in [
        "asupersync_adapter_retry_budget_exhaustion_fault_injection_is_fail_closed",
        "asupersync_adapter_partial_write_cursor_regression_is_fail_closed",
        "asupersync_adapter_stale_metadata_seed_mismatch_rejects_resume",
        "asupersync_adapter_property_same_fault_sequence_has_identical_transitions",
    ] {
        assert!(
            runtime_source.contains(symbol),
            "runtime source missing ASUP-C coverage symbol `{symbol}`"
        );
    }

    let mut interruption_intent = base_intent();
    interruption_intent.max_attempts = 2;
    let mut interruption_machine =
        AsupersyncAdapterMachine::start(interruption_intent).expect("start should succeed");
    interruption_machine
        .mark_capability_check(true)
        .expect("capability should pass");
    interruption_machine
        .record_transport_interruption()
        .expect("first retry should succeed");
    interruption_machine
        .record_transport_interruption()
        .expect("second retry should succeed");
    let retry_err = interruption_machine
        .record_transport_interruption()
        .expect_err("third retry should fail closed");
    assert!(retry_err.contains("RetryExhausted"));
    assert_eq!(
        interruption_machine.state(),
        AsupersyncAdapterState::FailedClosed
    );
    assert_eq!(
        interruption_machine
            .transitions()
            .last()
            .expect("retry transition should be present")
            .reason_code,
        Some(AsupersyncAdapterReasonCode::RetryExhausted)
    );

    let mut partial_write_machine =
        AsupersyncAdapterMachine::start(base_intent()).expect("start should succeed");
    partial_write_machine
        .mark_capability_check(true)
        .expect("capability should pass");
    partial_write_machine
        .record_chunk_commit(20)
        .expect("initial chunk should succeed");
    let partial_err = partial_write_machine
        .record_chunk_commit(10)
        .expect_err("cursor regression should fail closed");
    assert!(partial_err.contains("ConflictDetected"));
    assert_eq!(
        partial_write_machine.state(),
        AsupersyncAdapterState::FailedClosed
    );

    let checkpoint = AsupersyncAdapterMachine::start(base_intent())
        .expect("start should succeed")
        .checkpoint();
    let mut stale_intent = base_intent();
    stale_intent.deterministic_seed = 999;
    let stale_err = AsupersyncAdapterMachine::resume_from_checkpoint(stale_intent, checkpoint)
        .expect_err("stale metadata should reject resume");
    assert!(stale_err.contains("deterministic_seed"));

    let deterministic_run = |seed: u64| {
        let mut intent = base_intent();
        intent.deterministic_seed = seed;
        let mut machine = AsupersyncAdapterMachine::start(intent).expect("start should succeed");
        machine
            .mark_capability_check(true)
            .expect("capability should pass");
        machine
            .record_chunk_commit(88)
            .expect("chunk commit should succeed");
        machine
            .record_transport_interruption()
            .expect("interruption should succeed");
        machine
            .apply_resume_cursor(88)
            .expect("resume cursor should succeed");
        machine
            .start_checksum_verification()
            .expect("checksum phase should start");
        machine
            .finish_checksum_verification("sha256:expected-fault-gate")
            .expect("checksum should complete");
        machine
    };

    let first = deterministic_run(77);
    let second = deterministic_run(77);
    assert_eq!(
        first.transitions(),
        second.transitions(),
        "same deterministic seed + fault sequence should produce identical transitions"
    );
    assert_eq!(first.state(), AsupersyncAdapterState::Completed);
}
