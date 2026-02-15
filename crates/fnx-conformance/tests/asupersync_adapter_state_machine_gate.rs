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
        transfer_id: "tx-gate-001".to_owned(),
        artifact_id: "artifacts/e2e/latest/e2e_scenario_matrix_report_v1.json".to_owned(),
        artifact_class: "conformance_fixture_bundle".to_owned(),
        mode: CompatibilityMode::Strict,
        deterministic_seed: 41,
        expected_checksum: "sha256:expected-gate".to_owned(),
        max_attempts: 3,
    }
}

#[test]
fn asupersync_adapter_state_machine_contract_is_complete_and_deterministic() {
    let root = repo_root();
    let artifact =
        load_json(&root.join("artifacts/asupersync/v1/asupersync_adapter_state_machine_v1.json"));
    let schema = load_json(
        &root
            .join("artifacts/asupersync/schema/v1/asupersync_adapter_state_machine_schema_v1.json"),
    );

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
    for required_symbol in [
        "AsupersyncAdapterMachine",
        "resume_from_checkpoint",
        "record_conflict",
        "finish_checksum_verification",
        "ArtifactSyncAdapter",
    ] {
        assert!(
            runtime_source.contains(required_symbol),
            "runtime source missing required symbol `{required_symbol}`"
        );
    }

    let required_states = required_string_array(&schema, "required_states")
        .into_iter()
        .collect::<BTreeSet<_>>();
    let required_terminal_states = required_string_array(&schema, "required_terminal_states")
        .into_iter()
        .collect::<BTreeSet<_>>();
    let required_events = required_string_array(&schema, "required_events")
        .into_iter()
        .collect::<BTreeSet<_>>();
    let required_reason_codes = required_string_array(&schema, "required_reason_codes")
        .into_iter()
        .collect::<BTreeSet<_>>();

    let state_machine = artifact["state_machine"]
        .as_object()
        .expect("state_machine should be object");
    for key in required_string_array(&schema, "required_state_machine_keys") {
        assert!(
            state_machine.get(key).is_some(),
            "state_machine missing key `{key}`"
        );
    }

    let observed_states = state_machine["states"]
        .as_array()
        .expect("state_machine.states should be array")
        .iter()
        .map(|value| value.as_str().expect("state entry should be string"))
        .collect::<BTreeSet<_>>();
    assert_eq!(
        observed_states, required_states,
        "state_machine.states drifted from schema"
    );
    let observed_terminal_states = state_machine["terminal_states"]
        .as_array()
        .expect("state_machine.terminal_states should be array")
        .iter()
        .map(|value| {
            value
                .as_str()
                .expect("terminal state entry should be string")
        })
        .collect::<BTreeSet<_>>();
    assert_eq!(
        observed_terminal_states, required_terminal_states,
        "state_machine.terminal_states drifted from schema"
    );
    let observed_events = state_machine["events"]
        .as_array()
        .expect("state_machine.events should be array")
        .iter()
        .map(|value| value.as_str().expect("event entry should be string"))
        .collect::<BTreeSet<_>>();
    assert_eq!(
        observed_events, required_events,
        "state_machine.events drifted from schema"
    );
    let observed_reason_codes = state_machine["reason_codes"]
        .as_array()
        .expect("state_machine.reason_codes should be array")
        .iter()
        .map(|value| value.as_str().expect("reason code entry should be string"))
        .collect::<BTreeSet<_>>();
    assert_eq!(
        observed_reason_codes, required_reason_codes,
        "state_machine.reason_codes drifted from schema"
    );

    let transition_rows = state_machine["transition_table"]
        .as_array()
        .expect("state_machine.transition_table should be array");
    assert!(
        !transition_rows.is_empty(),
        "state_machine.transition_table should be non-empty"
    );
    let required_transition_keys = required_string_array(&schema, "required_transition_row_keys");
    for (idx, row) in transition_rows.iter().enumerate() {
        for key in &required_transition_keys {
            assert!(
                row.get(*key).is_some(),
                "transition_table[{idx}] missing key `{key}`"
            );
        }
        let from_state = row["from_state"]
            .as_str()
            .expect("from_state should be string");
        let to_state = row["to_state"].as_str().expect("to_state should be string");
        let event = row["event"].as_str().expect("event should be string");
        assert!(
            required_states.contains(from_state),
            "transition row {idx} has unknown from_state `{from_state}`"
        );
        assert!(
            required_states.contains(to_state),
            "transition row {idx} has unknown to_state `{to_state}`"
        );
        assert!(
            required_events.contains(event),
            "transition row {idx} has unknown event `{event}`"
        );

        let reason_code = row["reason_code"].as_str();
        if to_state == "failed_closed" {
            let reason_code = reason_code.unwrap_or_else(|| {
                panic!("transition row {idx} to failed_closed needs reason_code")
            });
            assert!(
                required_reason_codes.contains(reason_code),
                "transition row {idx} has unknown reason_code `{reason_code}`"
            );
        }
    }

    let conflict_policy = artifact["conflict_policy"]
        .as_object()
        .expect("conflict_policy should be object");
    for key in required_string_array(&schema, "required_conflict_policy_keys") {
        assert!(
            conflict_policy.get(key).is_some(),
            "conflict_policy missing key `{key}`"
        );
    }
    assert_eq!(
        conflict_policy["default_action"]
            .as_str()
            .expect("conflict_policy.default_action should be string"),
        "fail_closed"
    );

    let checksum_policy = artifact["checksum_policy"]
        .as_object()
        .expect("checksum_policy should be object");
    for key in required_string_array(&schema, "required_checksum_policy_keys") {
        assert!(
            checksum_policy.get(key).is_some(),
            "checksum_policy missing key `{key}`"
        );
    }
    assert_eq!(
        checksum_policy["failure_reason_code"]
            .as_str()
            .expect("checksum_policy.failure_reason_code should be string"),
        "integrity_precheck_failed"
    );

    let checkpoint_contract = artifact["recovery_checkpoint_contract"]
        .as_object()
        .expect("recovery_checkpoint_contract should be object");
    for key in required_string_array(&schema, "required_recovery_checkpoint_keys") {
        assert!(
            checkpoint_contract.get(key).is_some(),
            "recovery_checkpoint_contract missing key `{key}`"
        );
    }
    let checkpoint_fields = checkpoint_contract["checkpoint_fields"]
        .as_array()
        .expect("checkpoint_fields should be array")
        .iter()
        .map(|value| value.as_str().expect("checkpoint field should be string"))
        .collect::<BTreeSet<_>>();
    for required_field in [
        "transfer_id",
        "deterministic_seed",
        "attempt",
        "committed_cursor",
    ] {
        assert!(
            checkpoint_fields.contains(required_field),
            "checkpoint_fields missing `{required_field}`"
        );
    }

    let required_layers = required_string_array(&schema, "required_test_layers")
        .into_iter()
        .collect::<BTreeSet<_>>();
    let test_bindings = artifact["test_bindings"]
        .as_array()
        .expect("test_bindings should be array");
    assert!(
        !test_bindings.is_empty(),
        "test_bindings should be non-empty"
    );
    let required_test_binding_keys = required_string_array(&schema, "required_test_binding_keys");
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
            "duplicate test_id `{test_id}`"
        );
        let layer = binding["layer"].as_str().expect("layer should be string");
        assert!(
            required_layers.contains(layer),
            "unexpected test layer `{layer}`"
        );
        observed_layers.insert(layer);
        assert_path(
            binding["artifact_path"]
                .as_str()
                .expect("artifact_path should be string"),
            &format!("test_bindings[{idx}].artifact_path"),
            &root,
        );
        let replay_command = binding["replay_command"]
            .as_str()
            .expect("replay_command should be string");
        assert!(
            replay_command.contains("rch exec --"),
            "test_bindings[{idx}] replay_command must use rch offload"
        );
    }
    assert_eq!(
        observed_layers, required_layers,
        "test_bindings should cover unit/differential/e2e layers"
    );

    let required_telemetry_fields = required_string_array(&schema, "required_telemetry_fields")
        .into_iter()
        .collect::<BTreeSet<_>>();
    let observed_telemetry_fields = artifact["telemetry_fields"]
        .as_array()
        .expect("telemetry_fields should be array")
        .iter()
        .map(|value| value.as_str().expect("telemetry field should be string"))
        .collect::<BTreeSet<_>>();
    assert!(
        required_telemetry_fields.is_subset(&observed_telemetry_fields),
        "telemetry_fields missing required entries"
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
            "loss_budget missing `{key}`"
        );
    }
    let safe_mode_fallback = decision_contract["safe_mode_fallback"]
        .as_object()
        .expect("safe_mode_fallback should be object");
    for key in required_string_array(&schema, "required_safe_mode_fallback_keys") {
        assert!(
            safe_mode_fallback.get(key).is_some(),
            "safe_mode_fallback missing `{key}`"
        );
    }

    let profile_artifacts = artifact["profile_first_artifacts"]
        .as_object()
        .expect("profile_first_artifacts should be object");
    for key in required_string_array(&schema, "required_profile_artifact_keys") {
        assert_path(
            profile_artifacts[key]
                .as_str()
                .expect("profile artifact path should be string"),
            &format!("profile_first_artifacts.{key}"),
            &root,
        );
    }

    let isomorphism_artifacts = artifact["isomorphism_proof_artifacts"]
        .as_array()
        .expect("isomorphism_proof_artifacts should be array");
    assert!(
        !isomorphism_artifacts.is_empty(),
        "isomorphism_proof_artifacts should be non-empty"
    );
    for (idx, path_text) in isomorphism_artifacts.iter().enumerate() {
        assert_path(
            path_text
                .as_str()
                .unwrap_or_else(|| panic!("isomorphism_proof_artifacts[{idx}] should be string")),
            &format!("isomorphism_proof_artifacts[{idx}]"),
            &root,
        );
    }

    let structured_logging_evidence = artifact["structured_logging_evidence"]
        .as_array()
        .expect("structured_logging_evidence should be array");
    assert!(
        !structured_logging_evidence.is_empty(),
        "structured_logging_evidence should be non-empty"
    );
    for (idx, path_text) in structured_logging_evidence.iter().enumerate() {
        assert_path(
            path_text
                .as_str()
                .unwrap_or_else(|| panic!("structured_logging_evidence[{idx}] should be string")),
            &format!("structured_logging_evidence[{idx}]"),
            &root,
        );
    }

    let mut machine = AsupersyncAdapterMachine::start(base_intent()).expect("start should pass");
    machine
        .mark_capability_check(true)
        .expect("capability acceptance should pass");
    machine
        .record_chunk_commit(64)
        .expect("chunk commit should pass");
    machine
        .record_transport_interruption()
        .expect("transport interruption should consume one retry");
    let checkpoint = machine.checkpoint();
    let mut resumed = AsupersyncAdapterMachine::resume_from_checkpoint(base_intent(), checkpoint)
        .expect("resume_from_checkpoint should pass");
    resumed
        .apply_resume_cursor(64)
        .expect("resume cursor should pass");
    resumed
        .start_checksum_verification()
        .expect("checksum phase should start");
    resumed
        .finish_checksum_verification("sha256:expected-gate")
        .expect("checksum should validate");
    assert_eq!(resumed.state(), AsupersyncAdapterState::Completed);
    assert!(resumed.validate_transition_log().is_ok());

    let mut mismatch_machine =
        AsupersyncAdapterMachine::start(base_intent()).expect("start should pass");
    mismatch_machine
        .mark_capability_check(true)
        .expect("capability acceptance should pass");
    mismatch_machine
        .start_checksum_verification()
        .expect("checksum phase should start");
    let err = mismatch_machine
        .finish_checksum_verification("sha256:not-expected")
        .expect_err("checksum mismatch should fail closed");
    assert!(err.contains("IntegrityPrecheckFailed"));
    assert_eq!(
        mismatch_machine.state(),
        AsupersyncAdapterState::FailedClosed
    );
    assert_eq!(
        mismatch_machine
            .transitions()
            .last()
            .expect("transition log should have mismatch transition")
            .reason_code,
        Some(AsupersyncAdapterReasonCode::IntegrityPrecheckFailed)
    );
}
