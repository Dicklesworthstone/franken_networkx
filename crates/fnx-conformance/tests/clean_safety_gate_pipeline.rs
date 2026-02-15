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
fn clean_safety_gate_pipeline_is_reproducible_and_artifact_indexed() {
    let root = repo_root();
    let artifact = load_json(&root.join("artifacts/clean/v1/clean_safety_gate_pipeline_v1.json"));
    let schema = load_json(
        &root.join("artifacts/clean/schema/v1/clean_safety_gate_pipeline_schema_v1.json"),
    );

    for key in required_string_array(&schema, "required_top_level_keys") {
        assert!(
            artifact.get(key).is_some(),
            "artifact missing top-level key `{key}`"
        );
    }

    let gate_matrix = artifact["gate_matrix"]
        .as_array()
        .expect("gate_matrix should be array");
    assert!(!gate_matrix.is_empty(), "gate_matrix should be non-empty");

    let required_gate_row_keys = required_string_array(&schema, "required_gate_row_keys");
    let required_repro_keys = required_string_array(&schema, "required_reproducibility_keys");
    let allowed_gate_types = required_string_array(&schema, "allowed_gate_types")
        .into_iter()
        .collect::<BTreeSet<_>>();

    let mut gate_ids = BTreeSet::new();
    let mut observed_gate_types = BTreeSet::new();

    for (idx, gate) in gate_matrix.iter().enumerate() {
        for key in &required_gate_row_keys {
            assert!(
                gate.get(*key).is_some(),
                "gate_matrix[{idx}] missing `{key}`"
            );
        }

        let gate_id = gate["gate_id"].as_str().expect("gate_id should be string");
        assert!(
            gate_ids.insert(gate_id),
            "duplicate gate_id detected: {gate_id}"
        );

        let gate_type = gate["gate_type"]
            .as_str()
            .expect("gate_type should be string");
        observed_gate_types.insert(gate_type);
        assert!(
            allowed_gate_types.contains(gate_type),
            "gate_type `{gate_type}` outside allowed set"
        );

        assert!(
            !gate["command"]
                .as_str()
                .expect("command should be string")
                .trim()
                .is_empty(),
            "gate_matrix[{idx}].command should be non-empty"
        );
        assert!(
            !gate["owner"]
                .as_str()
                .expect("owner should be string")
                .trim()
                .is_empty(),
            "gate_matrix[{idx}].owner should be non-empty"
        );

        let output_artifact = gate["output_artifact"]
            .as_str()
            .expect("output_artifact should be string");
        assert_path(
            output_artifact,
            &format!("gate_matrix[{idx}].output_artifact"),
            &root,
        );

        let reproducibility = gate["reproducibility"]
            .as_object()
            .expect("reproducibility should be object");
        for key in &required_repro_keys {
            let value = reproducibility[*key]
                .as_str()
                .unwrap_or_else(|| panic!("reproducibility.{key} should be string"));
            assert!(
                !value.trim().is_empty(),
                "gate_matrix[{idx}].reproducibility.{key} should be non-empty"
            );
        }
    }

    assert!(
        observed_gate_types.contains("static"),
        "gate_matrix should include at least one static gate"
    );
    assert!(
        observed_gate_types.contains("dynamic"),
        "gate_matrix should include at least one dynamic gate"
    );

    let high_risk = artifact["high_risk_coverage"]
        .as_array()
        .expect("high_risk_coverage should be array");
    assert!(
        !high_risk.is_empty(),
        "high_risk_coverage should be non-empty"
    );

    let required_high_risk_keys = required_string_array(&schema, "required_high_risk_entry_keys");
    let required_coverage_modes = required_string_array(&schema, "required_coverage_modes")
        .into_iter()
        .collect::<BTreeSet<_>>();

    let mut high_risk_target_ids = BTreeSet::new();
    let mut high_risk_buckets = BTreeSet::new();

    for (idx, row) in high_risk.iter().enumerate() {
        for key in &required_high_risk_keys {
            assert!(
                row.get(*key).is_some(),
                "high_risk_coverage[{idx}] missing `{key}`"
            );
        }

        let target_id = row["target_id"]
            .as_str()
            .expect("target_id should be string");
        assert!(
            high_risk_target_ids.insert(target_id),
            "duplicate high_risk target_id detected: {target_id}"
        );

        let modes = row["coverage_modes"]
            .as_array()
            .expect("coverage_modes should be array")
            .iter()
            .map(|value| {
                value
                    .as_str()
                    .expect("coverage_modes entries should be string")
            })
            .collect::<BTreeSet<_>>();
        assert_eq!(
            modes, required_coverage_modes,
            "high_risk_coverage[{idx}] must include full required coverage mode set"
        );

        let entrypoint = row["entrypoint_path"]
            .as_str()
            .expect("entrypoint_path should be string");
        assert_path(
            entrypoint,
            &format!("high_risk_coverage[{idx}].entrypoint_path"),
            &root,
        );

        let fixtures = row["fixtures"]
            .as_array()
            .expect("fixtures should be array");
        assert!(
            !fixtures.is_empty(),
            "high_risk_coverage[{idx}].fixtures should be non-empty"
        );
        for (fixture_idx, fixture) in fixtures.iter().enumerate() {
            let fixture = fixture.as_str().unwrap_or_else(|| {
                panic!("high_risk_coverage[{idx}].fixtures[{fixture_idx}] should be string")
            });
            assert_path(
                fixture,
                &format!("high_risk_coverage[{idx}].fixtures[{fixture_idx}]"),
                &root,
            );
        }

        let bucket = row["triage_bucket"]
            .as_str()
            .expect("triage_bucket should be string");
        high_risk_buckets.insert(bucket);
    }

    let execution_workflows = artifact["execution_workflows"]
        .as_object()
        .expect("execution_workflows should be object");
    for key in required_string_array(&schema, "required_execution_workflow_keys") {
        assert!(
            execution_workflows.get(key).is_some(),
            "execution_workflows missing `{key}`"
        );
    }
    assert!(
        !execution_workflows["local_commands"]
            .as_array()
            .expect("local_commands should be array")
            .is_empty(),
        "execution_workflows.local_commands should be non-empty"
    );
    assert!(
        !execution_workflows["ci_commands"]
            .as_array()
            .expect("ci_commands should be array")
            .is_empty(),
        "execution_workflows.ci_commands should be non-empty"
    );
    assert!(
        !execution_workflows["determinism_notes"]
            .as_str()
            .expect("determinism_notes should be string")
            .trim()
            .is_empty(),
        "execution_workflows.determinism_notes should be non-empty"
    );

    let compliance_scenarios = artifact["compliance_test_scenarios"]
        .as_array()
        .expect("compliance_test_scenarios should be array");
    assert!(
        !compliance_scenarios.is_empty(),
        "compliance_test_scenarios should be non-empty"
    );
    let required_scenario_keys =
        required_string_array(&schema, "required_compliance_scenario_keys");
    let required_triage_metadata_keys =
        required_string_array(&schema, "required_triage_metadata_keys");
    let allowed_scenario_levels = required_string_array(&schema, "allowed_scenario_levels")
        .into_iter()
        .map(str::to_owned)
        .collect::<BTreeSet<_>>();
    let required_scenario_levels = required_string_array(&schema, "required_scenario_levels")
        .into_iter()
        .map(str::to_owned)
        .collect::<BTreeSet<_>>();
    let required_control_coverage = required_string_array(&schema, "required_control_coverage")
        .into_iter()
        .map(str::to_owned)
        .collect::<BTreeSet<_>>();

    let mut scenario_ids = BTreeSet::new();
    let mut observed_levels = BTreeSet::new();
    let mut observed_controls = BTreeSet::new();

    for (idx, scenario) in compliance_scenarios.iter().enumerate() {
        for key in &required_scenario_keys {
            assert!(
                scenario.get(*key).is_some(),
                "compliance_test_scenarios[{idx}] missing `{key}`"
            );
        }

        let scenario_id = scenario["scenario_id"]
            .as_str()
            .expect("scenario_id should be string");
        assert!(
            scenario_ids.insert(scenario_id.to_string()),
            "duplicate compliance scenario_id detected: {scenario_id}"
        );

        let level = scenario["level"].as_str().expect("level should be string");
        assert!(
            allowed_scenario_levels.contains(level),
            "compliance scenario `{scenario_id}` level `{level}` outside allowed set"
        );
        observed_levels.insert(level.to_string());

        let command = scenario["command"]
            .as_str()
            .expect("command should be string");
        assert!(
            !command.trim().is_empty(),
            "compliance scenario `{scenario_id}` command should be non-empty"
        );

        let replay_command = scenario["replay_command"]
            .as_str()
            .expect("replay_command should be string");
        assert!(
            !replay_command.trim().is_empty(),
            "compliance scenario `{scenario_id}` replay_command should be non-empty"
        );
        assert!(
            replay_command.contains("rch exec --"),
            "compliance scenario `{scenario_id}` replay_command should use rch offload"
        );

        let controls = scenario["controls_validated"]
            .as_array()
            .expect("controls_validated should be array");
        assert!(
            !controls.is_empty(),
            "compliance scenario `{scenario_id}` controls_validated should be non-empty"
        );
        for (control_idx, control) in controls.iter().enumerate() {
            let control = control.as_str().unwrap_or_else(|| {
                panic!(
                    "controls_validated[{control_idx}] for scenario {scenario_id} should be string"
                )
            });
            observed_controls.insert(control.to_string());
        }

        let evidence_paths = scenario["evidence_paths"]
            .as_array()
            .expect("evidence_paths should be array");
        assert!(
            !evidence_paths.is_empty(),
            "compliance scenario `{scenario_id}` evidence_paths should be non-empty"
        );
        for (path_idx, path) in evidence_paths.iter().enumerate() {
            let path = path.as_str().unwrap_or_else(|| {
                panic!("compliance scenario `{scenario_id}` evidence_paths[{path_idx}] should be string")
            });
            assert_path(
                path,
                &format!("compliance_test_scenarios[{idx}].evidence_paths[{path_idx}]"),
                &root,
            );
        }

        let audit_log_path = scenario["audit_log_path"]
            .as_str()
            .expect("audit_log_path should be string");
        assert_path(
            audit_log_path,
            &format!("compliance_test_scenarios[{idx}].audit_log_path"),
            &root,
        );

        assert!(
            scenario["deterministic_seed"].as_u64().is_some(),
            "compliance scenario `{scenario_id}` deterministic_seed should be non-negative integer"
        );

        let triage_metadata = scenario["triage_metadata"]
            .as_object()
            .expect("triage_metadata should be object");
        for key in &required_triage_metadata_keys {
            let value = triage_metadata[*key]
                .as_str()
                .unwrap_or_else(|| panic!("triage_metadata.{key} should be string"));
            assert!(
                !value.trim().is_empty(),
                "compliance scenario `{scenario_id}` triage_metadata.{key} should be non-empty"
            );
        }
        assert_eq!(
            triage_metadata["replay_ref"]
                .as_str()
                .expect("triage_metadata.replay_ref should be string"),
            replay_command,
            "compliance scenario `{scenario_id}` triage replay_ref must match replay_command"
        );
    }

    assert_eq!(
        observed_levels, required_scenario_levels,
        "compliance_test_scenarios should cover required levels"
    );
    assert!(
        required_control_coverage.is_subset(&observed_controls),
        "compliance_test_scenarios controls_validated must cover required control set"
    );

    let audit_contract = artifact["audit_logging_contract"]
        .as_object()
        .expect("audit_logging_contract should be object");
    for key in required_string_array(&schema, "required_audit_log_contract_keys") {
        assert!(
            audit_contract.get(key).is_some(),
            "audit_logging_contract missing `{key}`"
        );
    }

    let audit_path = audit_contract["path"]
        .as_str()
        .expect("audit_logging_contract.path should be string");
    assert_path(audit_path, "audit_logging_contract.path", &root);

    let required_audit_fields = required_string_array(&schema, "required_audit_log_fields")
        .into_iter()
        .map(str::to_owned)
        .collect::<BTreeSet<_>>();
    let audit_contract_fields = audit_contract["required_fields"]
        .as_array()
        .expect("audit_logging_contract.required_fields should be array")
        .iter()
        .map(|value| {
            value
                .as_str()
                .expect("audit_logging_contract.required_fields entries should be string")
                .to_string()
        })
        .collect::<BTreeSet<_>>();
    assert_eq!(
        audit_contract_fields, required_audit_fields,
        "audit_logging_contract.required_fields should match schema.required_audit_log_fields"
    );

    let allowed_audit_modes = required_string_array(&schema, "allowed_audit_modes")
        .into_iter()
        .collect::<BTreeSet<_>>();
    let allowed_audit_outcomes = required_string_array(&schema, "allowed_audit_outcomes")
        .into_iter()
        .collect::<BTreeSet<_>>();

    let replay_key = audit_contract["replay_key"]
        .as_str()
        .expect("audit_logging_contract.replay_key should be string");
    let triage_key = audit_contract["triage_key"]
        .as_str()
        .expect("audit_logging_contract.triage_key should be string");

    let audit_log = load_json(&root.join(audit_path));
    let audit_records = audit_log["records"]
        .as_array()
        .expect("audit log records should be array");
    assert!(
        !audit_records.is_empty(),
        "audit log records should be non-empty"
    );

    for (idx, record) in audit_records.iter().enumerate() {
        for field in &required_audit_fields {
            assert!(
                record.get(field).is_some(),
                "audit record [{idx}] missing `{field}`"
            );
        }

        let claim_id = record["claim_id"]
            .as_str()
            .expect("claim_id should be string");
        assert!(
            !claim_id.trim().is_empty(),
            "audit record [{idx}] claim_id should be non-empty"
        );

        let source_anchor = record["source_anchor"]
            .as_object()
            .expect("source_anchor should be object");
        let source_path = source_anchor["path"]
            .as_str()
            .expect("source_anchor.path should be string");
        assert_path(
            source_path,
            &format!("audit record [{idx}] source_anchor.path"),
            &root,
        );

        let implementation_ref = record["implementation_ref"]
            .as_object()
            .expect("implementation_ref should be object");
        let implementation_path = implementation_ref["path"]
            .as_str()
            .expect("implementation_ref.path should be string");
        assert_path(
            implementation_path,
            &format!("audit record [{idx}] implementation_ref.path"),
            &root,
        );

        let reviewer_id = record["reviewer_id"]
            .as_str()
            .expect("reviewer_id should be string");
        assert!(
            !reviewer_id.trim().is_empty(),
            "audit record [{idx}] reviewer_id should be non-empty"
        );

        let mode = record["mode"].as_str().expect("mode should be string");
        assert!(
            allowed_audit_modes.contains(mode),
            "audit record [{idx}] mode `{mode}` outside allowed set"
        );

        let outcome = record["outcome"]
            .as_str()
            .expect("outcome should be string");
        assert!(
            allowed_audit_outcomes.contains(outcome),
            "audit record [{idx}] outcome `{outcome}` outside allowed set"
        );

        let replay_command = record[replay_key]
            .as_str()
            .unwrap_or_else(|| panic!("audit record [{idx}] {replay_key} should be string"));
        assert!(
            !replay_command.trim().is_empty(),
            "audit record [{idx}] replay command should be non-empty"
        );
        assert!(
            replay_command.contains("rch exec --"),
            "audit record [{idx}] replay command should use rch offload"
        );

        let triage = record[triage_key]
            .as_object()
            .unwrap_or_else(|| panic!("audit record [{idx}] {triage_key} should be object"));
        for key in &required_triage_metadata_keys {
            let value = triage[*key].as_str().unwrap_or_else(|| {
                panic!("audit record [{idx}] triage_metadata.{key} should be string")
            });
            assert!(
                !value.trim().is_empty(),
                "audit record [{idx}] triage_metadata.{key} should be non-empty"
            );
        }

        let scenario_id = record["scenario_id"]
            .as_str()
            .expect("scenario_id should be string");
        assert!(
            scenario_ids.contains(scenario_id),
            "audit record [{idx}] scenario_id `{scenario_id}` not found in compliance scenario matrix"
        );
    }

    let artifact_index = artifact["artifact_index"]
        .as_array()
        .expect("artifact_index should be array");
    assert!(
        !artifact_index.is_empty(),
        "artifact_index should be non-empty"
    );
    let required_index_keys = required_string_array(&schema, "required_artifact_index_keys");

    let mut artifact_index_ids = BTreeSet::new();
    for (idx, row) in artifact_index.iter().enumerate() {
        for key in &required_index_keys {
            assert!(
                row.get(*key).is_some(),
                "artifact_index[{idx}] missing `{key}`"
            );
        }

        let artifact_id = row["artifact_id"]
            .as_str()
            .expect("artifact_id should be string");
        assert!(
            artifact_index_ids.insert(artifact_id),
            "duplicate artifact_index artifact_id detected: {artifact_id}"
        );

        let path = row["path"].as_str().expect("path should be string");
        assert_path(path, &format!("artifact_index[{idx}].path"), &root);

        let producer_gate = row["producer_gate_id"]
            .as_str()
            .expect("producer_gate_id should be string");
        assert!(
            gate_ids.contains(producer_gate),
            "artifact_index[{idx}] references unknown gate_id `{producer_gate}`"
        );
    }

    let triage_taxonomy = artifact["triage_taxonomy"]
        .as_array()
        .expect("triage_taxonomy should be array");
    assert!(
        !triage_taxonomy.is_empty(),
        "triage_taxonomy should be non-empty"
    );
    let required_triage_keys = required_string_array(&schema, "required_triage_bucket_keys");
    let required_triage_buckets = required_string_array(&schema, "required_triage_buckets")
        .into_iter()
        .collect::<BTreeSet<_>>();

    let mut observed_triage_buckets = BTreeSet::new();
    for (idx, row) in triage_taxonomy.iter().enumerate() {
        for key in &required_triage_keys {
            assert!(
                row.get(*key).is_some(),
                "triage_taxonomy[{idx}] missing `{key}`"
            );
        }

        let bucket_id = row["bucket_id"]
            .as_str()
            .expect("bucket_id should be string");
        observed_triage_buckets.insert(bucket_id);

        let sla = row["response_sla_hours"]
            .as_i64()
            .expect("response_sla_hours should be integer");
        assert!(
            sla >= 1,
            "triage_taxonomy[{idx}] response_sla_hours must be >= 1"
        );
    }

    assert_eq!(
        observed_triage_buckets, required_triage_buckets,
        "triage_taxonomy must match required triage bucket set"
    );

    for bucket in &high_risk_buckets {
        assert!(
            observed_triage_buckets.contains(bucket),
            "high_risk_coverage references undefined triage bucket `{bucket}`"
        );
    }

    let alien = artifact["alien_uplift_contract_card"]
        .as_object()
        .expect("alien_uplift_contract_card should be object");
    for key in required_string_array(&schema, "required_alien_contract_card_keys") {
        assert!(
            alien.get(key).is_some(),
            "alien_uplift_contract_card missing `{key}`"
        );
    }
    let ev_score = alien["ev_score"]
        .as_f64()
        .expect("ev_score should be numeric");
    assert!(ev_score >= 2.0, "ev_score must be >= 2.0");

    let profile = artifact["profile_first_artifacts"]
        .as_object()
        .expect("profile_first_artifacts should be object");
    for key in required_string_array(&schema, "required_profile_artifact_keys") {
        let path = profile[key]
            .as_str()
            .unwrap_or_else(|| panic!("profile_first_artifacts.{key} should be string"));
        assert_path(path, &format!("profile_first_artifacts.{key}"), &root);
    }

    let optimization = artifact["optimization_lever_policy"]
        .as_object()
        .expect("optimization_lever_policy should be object");
    for key in required_string_array(&schema, "required_optimization_policy_keys") {
        assert!(
            optimization.get(key).is_some(),
            "optimization_lever_policy missing `{key}`"
        );
    }
    let optimization_evidence = optimization["evidence_path"]
        .as_str()
        .expect("optimization_lever_policy.evidence_path should be string");
    assert_path(
        optimization_evidence,
        "optimization_lever_policy.evidence_path",
        &root,
    );
    let max_levers = optimization["max_levers_per_change"]
        .as_i64()
        .expect("max_levers_per_change should be integer");
    assert_eq!(max_levers, 1, "max_levers_per_change must equal 1");

    let parity = artifact["drop_in_parity_contract"]
        .as_object()
        .expect("drop_in_parity_contract should be object");
    for key in required_string_array(&schema, "required_drop_in_parity_keys") {
        assert!(
            parity.get(key).is_some(),
            "drop_in_parity_contract missing `{key}`"
        );
    }
    let overlap_target = parity["legacy_feature_overlap_target"]
        .as_str()
        .expect("legacy_feature_overlap_target should be string");
    assert_eq!(overlap_target, "100%", "overlap target must be 100%");
    assert!(
        parity["intentional_capability_gaps"]
            .as_array()
            .expect("intentional_capability_gaps should be array")
            .is_empty(),
        "intentional_capability_gaps must be empty"
    );

    let runtime = artifact["decision_theoretic_runtime_contract"]
        .as_object()
        .expect("decision_theoretic_runtime_contract should be object");
    for key in required_string_array(&schema, "required_runtime_contract_keys") {
        assert!(
            runtime.get(key).is_some(),
            "decision_theoretic_runtime_contract missing `{key}`"
        );
    }
    assert!(
        !runtime["states"]
            .as_array()
            .expect("runtime.states should be array")
            .is_empty(),
        "runtime.states should be non-empty"
    );
    assert!(
        !runtime["actions"]
            .as_array()
            .expect("runtime.actions should be array")
            .is_empty(),
        "runtime.actions should be non-empty"
    );

    let safe_mode_budget = runtime["safe_mode_budget"]
        .as_object()
        .expect("safe_mode_budget should be object");
    for key in [
        "max_failed_required_gates",
        "max_unmapped_high_risk_targets",
        "max_missing_artifact_links",
    ] {
        let value = safe_mode_budget[key]
            .as_i64()
            .unwrap_or_else(|| panic!("safe_mode_budget.{key} should be integer"));
        assert!(value >= 0, "safe_mode_budget.{key} should be >= 0");
    }

    let trigger_thresholds = runtime["trigger_thresholds"]
        .as_array()
        .expect("trigger_thresholds should be array");
    assert!(
        !trigger_thresholds.is_empty(),
        "trigger_thresholds should be non-empty"
    );
    let required_trigger_keys = required_string_array(&schema, "required_runtime_trigger_keys");
    for (idx, trigger) in trigger_thresholds.iter().enumerate() {
        for key in &required_trigger_keys {
            assert!(
                trigger.get(*key).is_some(),
                "trigger_thresholds[{idx}] missing `{key}`"
            );
        }
        let threshold = trigger["threshold"]
            .as_i64()
            .expect("trigger threshold should be integer");
        assert!(
            threshold >= 1,
            "trigger_thresholds[{idx}].threshold must be >= 1"
        );
    }

    for (idx, path_text) in artifact["isomorphism_proof_artifacts"]
        .as_array()
        .expect("isomorphism_proof_artifacts should be array")
        .iter()
        .enumerate()
    {
        let path = path_text
            .as_str()
            .unwrap_or_else(|| panic!("isomorphism_proof_artifacts[{idx}] should be string"));
        assert_path(path, &format!("isomorphism_proof_artifacts[{idx}]"), &root);
    }

    let logging_paths = artifact["structured_logging_evidence"]
        .as_array()
        .expect("structured_logging_evidence should be array");
    assert!(
        logging_paths.len() >= 3,
        "structured_logging_evidence should include log + replay + forensics evidence"
    );
    for (idx, path_text) in logging_paths.iter().enumerate() {
        let path = path_text
            .as_str()
            .unwrap_or_else(|| panic!("structured_logging_evidence[{idx}] should be string"));
        assert_path(path, &format!("structured_logging_evidence[{idx}]"), &root);
    }
}
