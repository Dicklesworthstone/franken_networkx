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

#[test]
fn asupersync_capability_matrix_contract_is_complete_and_fail_closed() {
    let root = repo_root();
    let artifact =
        load_json(&root.join("artifacts/asupersync/v1/asupersync_capability_matrix_v1.json"));
    let schema = load_json(
        &root.join("artifacts/asupersync/schema/v1/asupersync_capability_matrix_schema_v1.json"),
    );

    for key in required_string_array(&schema, "required_top_level_keys") {
        assert!(
            artifact.get(key).is_some(),
            "artifact missing top-level key `{key}`"
        );
    }

    let summary = artifact["capability_summary"]
        .as_object()
        .expect("capability_summary should be object");
    for key in required_string_array(&schema, "required_summary_keys") {
        assert!(
            summary.get(key).is_some(),
            "capability_summary missing key `{key}`"
        );
    }

    let boundaries = artifact["integration_boundaries"]
        .as_object()
        .expect("integration_boundaries should be object");
    for key in required_string_array(&schema, "required_boundary_keys") {
        assert!(
            boundaries.get(key).is_some(),
            "integration_boundaries missing key `{key}`"
        );
    }
    let owning_crate = boundaries["owning_crate"]
        .as_str()
        .expect("integration_boundaries.owning_crate should be string");
    assert_eq!(
        owning_crate, "fnx-runtime",
        "owning crate should be fnx-runtime"
    );
    let feature_gate = boundaries["feature_gate"]
        .as_str()
        .expect("integration_boundaries.feature_gate should be string");
    assert_eq!(
        feature_gate, "asupersync-integration",
        "feature gate should be asupersync-integration"
    );

    let runtime_cargo = fs::read_to_string(root.join("crates/fnx-runtime/Cargo.toml"))
        .expect("expected readable crates/fnx-runtime/Cargo.toml");
    assert!(
        runtime_cargo.contains("asupersync-integration"),
        "fnx-runtime Cargo.toml should expose asupersync-integration feature"
    );
    assert!(
        runtime_cargo.contains("asupersync = { version = \"0.2.0\""),
        "fnx-runtime Cargo.toml should pin asupersync 0.2.0 dependency"
    );

    let required_forbidden = required_string_array(&schema, "required_forbidden_algorithm_crates")
        .into_iter()
        .collect::<BTreeSet<_>>();
    let top_forbidden = boundaries["forbidden_algorithm_crates"]
        .as_array()
        .expect("integration_boundaries.forbidden_algorithm_crates should be array")
        .iter()
        .map(|value| {
            value
                .as_str()
                .expect("forbidden_algorithm_crates entry should be string")
        })
        .collect::<BTreeSet<_>>();
    assert_eq!(
        top_forbidden, required_forbidden,
        "forbidden algorithm crate set drifted from schema"
    );

    let required_classes = required_string_array(&schema, "required_artifact_classes")
        .into_iter()
        .collect::<BTreeSet<_>>();
    let required_layers = required_string_array(&schema, "required_test_layers")
        .into_iter()
        .collect::<BTreeSet<_>>();
    let required_telemetry_fields = required_string_array(&schema, "required_telemetry_fields")
        .into_iter()
        .collect::<BTreeSet<_>>();
    let required_fail_closed_reason_codes =
        required_string_array(&schema, "required_fail_closed_reason_codes")
            .into_iter()
            .collect::<BTreeSet<_>>();

    let matrix = artifact["capability_matrix"]
        .as_array()
        .expect("capability_matrix should be array");
    assert_eq!(
        matrix.len(),
        required_classes.len(),
        "capability_matrix should include one row per required artifact class"
    );

    let required_row_keys = required_string_array(&schema, "required_capability_row_keys");
    let required_mode_keys = required_string_array(&schema, "required_mode_behavior_keys");
    let required_fail_closed_keys =
        required_string_array(&schema, "required_fail_closed_contract_keys");
    let required_integration_boundary_keys =
        required_string_array(&schema, "required_integration_boundary_keys");
    let required_test_binding_keys = required_string_array(&schema, "required_test_binding_keys");

    let mut seen_operation_ids = BTreeSet::new();
    let mut seen_classes = BTreeSet::new();
    let mut seen_test_layers = BTreeSet::new();
    let mut seen_test_ids = BTreeSet::new();

    for (idx, row) in matrix.iter().enumerate() {
        for key in &required_row_keys {
            assert!(
                row.get(*key).is_some(),
                "capability_matrix[{idx}] missing key `{key}`"
            );
        }

        let operation_id = row["operation_id"]
            .as_str()
            .expect("operation_id should be string");
        assert!(
            seen_operation_ids.insert(operation_id),
            "duplicate operation_id detected: {operation_id}"
        );

        let artifact_class = row["artifact_class"]
            .as_str()
            .expect("artifact_class should be string");
        assert!(
            required_classes.contains(artifact_class),
            "unsupported artifact_class in row {operation_id}: {artifact_class}"
        );
        seen_classes.insert(artifact_class);

        let primitives = row["asupersync_primitives"]
            .as_array()
            .expect("asupersync_primitives should be array");
        assert!(
            !primitives.is_empty(),
            "asupersync_primitives should be non-empty for {operation_id}"
        );
        for primitive in primitives {
            let primitive = primitive
                .as_str()
                .expect("asupersync primitive should be string");
            assert!(
                primitive.starts_with("asupersync::"),
                "primitive should use asupersync namespace: {primitive}"
            );
        }

        for (expected_mode, key) in [
            ("strict", "strict_mode_behavior"),
            ("hardened", "hardened_mode_behavior"),
        ] {
            let mode_behavior = row[key]
                .as_object()
                .unwrap_or_else(|| panic!("{key} should be object for {operation_id}"));
            for required_key in &required_mode_keys {
                assert!(
                    mode_behavior.get(*required_key).is_some(),
                    "{operation_id}.{key} missing `{required_key}`"
                );
            }
            assert_eq!(
                mode_behavior["mode"]
                    .as_str()
                    .expect("mode should be string"),
                expected_mode,
                "{operation_id}.{key}.mode mismatch"
            );
            assert_eq!(
                mode_behavior["unsupported_capability_policy"]
                    .as_str()
                    .expect("unsupported_capability_policy should be string"),
                "fail_closed",
                "{operation_id}.{key} must fail-closed on unsupported capabilities"
            );
            assert!(
                !mode_behavior["fallback_behavior"]
                    .as_str()
                    .expect("fallback_behavior should be string")
                    .trim()
                    .is_empty(),
                "{operation_id}.{key}.fallback_behavior should be non-empty"
            );
        }

        let fail_closed = row["fail_closed_contract"]
            .as_object()
            .expect("fail_closed_contract should be object");
        for key in &required_fail_closed_keys {
            assert!(
                fail_closed.get(*key).is_some(),
                "{operation_id}.fail_closed_contract missing `{key}`"
            );
        }
        assert_eq!(
            fail_closed["default_action"]
                .as_str()
                .expect("default_action should be string"),
            "abort_sync",
            "{operation_id}.fail_closed_contract.default_action should be abort_sync"
        );
        let reason_codes = fail_closed["reason_codes"]
            .as_array()
            .expect("reason_codes should be array")
            .iter()
            .map(|value| value.as_str().expect("reason code should be string"))
            .collect::<BTreeSet<_>>();
        assert!(
            required_fail_closed_reason_codes.is_subset(&reason_codes),
            "{operation_id}.fail_closed_contract.reason_codes missing required reasons"
        );

        let row_boundary = row["integration_boundary"]
            .as_object()
            .expect("integration_boundary should be object");
        for key in &required_integration_boundary_keys {
            assert!(
                row_boundary.get(*key).is_some(),
                "{operation_id}.integration_boundary missing `{key}`"
            );
        }
        assert_eq!(
            row_boundary["owning_crate"]
                .as_str()
                .expect("row owning_crate should be string"),
            owning_crate,
            "{operation_id}.integration_boundary.owning_crate mismatch"
        );
        let row_forbidden = row_boundary["forbidden_crates"]
            .as_array()
            .expect("integration_boundary.forbidden_crates should be array")
            .iter()
            .map(|value| {
                value
                    .as_str()
                    .expect("integration_boundary forbidden crate should be string")
            })
            .collect::<BTreeSet<_>>();
        assert!(
            required_forbidden.is_subset(&row_forbidden),
            "{operation_id}.integration_boundary.forbidden_crates missing required algorithm crate exclusions"
        );

        let test_bindings = row["test_bindings"]
            .as_array()
            .expect("test_bindings should be array");
        assert!(
            !test_bindings.is_empty(),
            "{operation_id}.test_bindings should be non-empty"
        );
        for (test_idx, test_binding) in test_bindings.iter().enumerate() {
            for key in &required_test_binding_keys {
                assert!(
                    test_binding.get(*key).is_some(),
                    "{operation_id}.test_bindings[{test_idx}] missing `{key}`"
                );
            }
            let test_id = test_binding["test_id"]
                .as_str()
                .expect("test_id should be string");
            assert!(
                seen_test_ids.insert(test_id),
                "duplicate test_id detected: {test_id}"
            );
            let layer = test_binding["layer"]
                .as_str()
                .expect("layer should be string");
            assert!(
                required_layers.contains(layer),
                "unexpected test layer in {operation_id}: {layer}"
            );
            seen_test_layers.insert(layer);
            let artifact_path = test_binding["artifact_path"]
                .as_str()
                .expect("artifact_path should be string");
            assert_path(
                artifact_path,
                &format!("{operation_id}.test_bindings[{test_idx}].artifact_path"),
                &root,
            );
            let replay_command = test_binding["replay_command"]
                .as_str()
                .expect("replay_command should be string");
            assert!(
                replay_command.contains("rch exec --"),
                "{operation_id}.test_bindings[{test_idx}] replay_command should use rch offload"
            );
        }

        let telemetry_fields = row["telemetry_fields"]
            .as_array()
            .expect("telemetry_fields should be array")
            .iter()
            .map(|value| value.as_str().expect("telemetry field should be string"))
            .collect::<BTreeSet<_>>();
        assert!(
            required_telemetry_fields.is_subset(&telemetry_fields),
            "{operation_id}.telemetry_fields missing required fields"
        );
    }

    assert_eq!(
        seen_classes, required_classes,
        "capability_matrix must cover required artifact classes exactly"
    );
    assert_eq!(
        seen_test_layers, required_layers,
        "capability_matrix test bindings must cover unit/differential/e2e layers"
    );

    assert_eq!(
        summary["operation_count"]
            .as_u64()
            .expect("operation_count should be numeric"),
        matrix.len() as u64
    );
    assert_eq!(
        summary["artifact_class_count"]
            .as_u64()
            .expect("artifact_class_count should be numeric"),
        required_classes.len() as u64
    );
    assert!(
        summary["strict_fail_closed_default"]
            .as_bool()
            .expect("strict_fail_closed_default should be bool"),
        "strict_fail_closed_default should be true"
    );
    assert!(
        summary["hardened_fail_closed_default"]
            .as_bool()
            .expect("hardened_fail_closed_default should be bool"),
        "hardened_fail_closed_default should be true"
    );

    let decision_contract = artifact["decision_theoretic_runtime_contract"]
        .as_object()
        .expect("decision_theoretic_runtime_contract should be object");
    for key in required_string_array(&schema, "required_decision_contract_keys") {
        assert!(
            decision_contract.get(key).is_some(),
            "decision_theoretic_runtime_contract missing `{key}`"
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
        assert!(
            loss_budget[key].as_f64().is_some(),
            "loss_budget.{key} should be numeric"
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
    assert!(
        safe_mode_fallback["budgeted_recovery_window_ms"]
            .as_u64()
            .is_some(),
        "safe_mode_fallback.budgeted_recovery_window_ms should be non-negative integer"
    );

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

    let ev_score = artifact["alien_uplift_contract_card"]["ev_score"]
        .as_f64()
        .expect("alien_uplift_contract_card.ev_score should be numeric");
    assert!(ev_score >= 2.0, "ev_score should be >= 2.0");
}
