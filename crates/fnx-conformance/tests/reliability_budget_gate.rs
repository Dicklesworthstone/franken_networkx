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

fn required_string_array(schema: &Value, key: &str) -> Vec<String> {
    schema[key]
        .as_array()
        .unwrap_or_else(|| panic!("schema.{key} should be array"))
        .iter()
        .map(|value| {
            value
                .as_str()
                .unwrap_or_else(|| panic!("schema.{key} should contain string entries"))
                .to_owned()
        })
        .collect()
}

#[test]
fn reliability_budget_artifacts_are_complete_and_gate_passes() {
    let root = repo_root();
    let schema = load_json(
        &root.join("artifacts/conformance/schema/v1/reliability_budget_gate_schema_v1.json"),
    );
    let spec = load_json(&root.join("artifacts/conformance/v1/reliability_budget_gate_v1.json"));
    let report =
        load_json(&root.join("artifacts/conformance/latest/reliability_budget_report_v1.json"));
    let quarantine = load_json(&root.join("artifacts/conformance/latest/flake_quarantine_v1.json"));

    for key in required_string_array(&schema, "required_top_level_keys") {
        assert!(
            spec.get(&key).is_some(),
            "reliability spec missing top-level key `{key}`"
        );
    }

    let required_budget_ids = required_string_array(&schema, "required_budget_ids")
        .into_iter()
        .collect::<BTreeSet<_>>();
    let allowed_status_values = required_string_array(&schema, "allowed_status_values")
        .into_iter()
        .collect::<BTreeSet<_>>();
    let required_report_top_level_keys =
        required_string_array(&schema, "required_report_top_level_keys");
    let required_report_budget_keys = required_string_array(&schema, "required_report_budget_keys");
    let required_stage_result_keys = required_string_array(&schema, "required_stage_result_keys");
    let required_stage_ids = required_string_array(&schema, "required_stage_ids")
        .into_iter()
        .collect::<BTreeSet<_>>();
    let required_failure_replay_metadata_keys =
        required_string_array(&schema, "required_failure_replay_metadata_keys");
    let required_quarantine_top_level_keys =
        required_string_array(&schema, "required_quarantine_top_level_keys");
    let required_quarantine_test_keys =
        required_string_array(&schema, "required_quarantine_test_keys");

    let required_budget_keys = required_string_array(&schema, "required_budget_keys");
    let spec_budgets = spec["budget_definitions"]
        .as_array()
        .expect("spec.budget_definitions should be array");
    let mut observed_spec_budget_ids = BTreeSet::new();
    for (idx, budget) in spec_budgets.iter().enumerate() {
        for key in &required_budget_keys {
            assert!(
                budget.get(key).is_some(),
                "spec.budget_definitions[{idx}] missing key `{key}`"
            );
        }
        let budget_id = budget["budget_id"]
            .as_str()
            .expect("spec budget_id should be string");
        assert!(
            observed_spec_budget_ids.insert(budget_id.to_owned()),
            "duplicate spec budget_id `{budget_id}`"
        );
    }
    assert_eq!(
        observed_spec_budget_ids, required_budget_ids,
        "spec budget coverage drifted"
    );

    assert_eq!(
        report["source_bead_id"].as_str(),
        Some("bd-315.23"),
        "reliability report must point to bd-315.23"
    );
    for key in &required_report_top_level_keys {
        assert!(
            report.get(key).is_some(),
            "reliability report missing top-level key `{key}`"
        );
    }
    let report_run_id = report["run_id"]
        .as_str()
        .expect("report.run_id should be string")
        .to_owned();
    assert!(
        !report_run_id.trim().is_empty(),
        "report.run_id should be non-empty"
    );
    let report_seed = report["deterministic_seed"]
        .as_str()
        .expect("report.deterministic_seed should be string");
    assert!(
        report_seed.len() >= 16,
        "report.deterministic_seed should be hash-like"
    );
    let report_status = report["status"]
        .as_str()
        .expect("report.status should be string");
    assert!(
        allowed_status_values.contains(report_status),
        "report.status `{report_status}` outside schema status set"
    );

    let report_budgets = report["budgets"]
        .as_array()
        .expect("report.budgets should be array");
    assert!(
        !report_budgets.is_empty(),
        "report.budgets must be non-empty"
    );

    let mut observed_report_budget_ids = BTreeSet::new();
    let mut status_by_budget: Vec<(String, String)> = Vec::new();
    let mut non_pass_stage_ids_by_budget: std::collections::BTreeMap<String, Vec<String>> =
        std::collections::BTreeMap::new();

    for (idx, budget) in report_budgets.iter().enumerate() {
        for key in &required_report_budget_keys {
            assert!(
                budget.get(key).is_some(),
                "report.budgets[{idx}] missing key `{key}`"
            );
        }

        let budget_id = budget["budget_id"]
            .as_str()
            .expect("report budget_id should be string")
            .to_owned();
        let budget_run_id = budget["run_id"]
            .as_str()
            .expect("report budget run_id should be string");
        assert_eq!(
            budget_run_id, report_run_id,
            "report.budgets[{idx}].run_id must match report.run_id"
        );

        let status = budget["status"]
            .as_str()
            .expect("report status should be string")
            .to_owned();
        assert!(
            allowed_status_values.contains(status.as_str()),
            "report.budgets[{idx}].status `{status}` outside schema status set"
        );
        assert!(
            observed_report_budget_ids.insert(budget_id.clone()),
            "duplicate report budget_id `{budget_id}`"
        );
        assert_eq!(
            budget["owner_bead_id"].as_str(),
            Some("bd-315.23"),
            "report.budgets[{idx}].owner_bead_id must be bd-315.23"
        );

        let gate_command = budget["gate_command"]
            .as_str()
            .expect("report gate_command should be string");
        assert!(
            gate_command.contains("rch exec --"),
            "report.budgets[{idx}].gate_command must use rch"
        );

        let artifact_paths = budget["artifact_paths"]
            .as_array()
            .expect("report artifact_paths should be array");
        assert!(
            !artifact_paths.is_empty(),
            "report.budgets[{idx}].artifact_paths must be non-empty"
        );
        for (path_idx, path_value) in artifact_paths.iter().enumerate() {
            let path = path_value
                .as_str()
                .expect("report artifact path should be string");
            assert!(
                root.join(path).exists(),
                "report.budgets[{idx}].artifact_paths[{path_idx}] missing path `{path}`"
            );
        }

        let observed = budget["observed"]
            .as_object()
            .expect("report observed should be object");
        for key in [
            "unit_line_pct_proxy",
            "branch_pct_proxy",
            "property_count",
            "e2e_replay_pass_ratio",
            "flake_rate_pct_7d",
            "runtime_guardrail_pass",
            "missing_evidence_count",
        ] {
            assert!(
                observed.get(key).is_some(),
                "report.budgets[{idx}].observed missing `{key}`"
            );
        }

        let thresholds = budget["thresholds"]
            .as_object()
            .expect("report thresholds should be object");
        for key in [
            "unit_line_pct_floor",
            "branch_pct_floor",
            "property_floor",
            "e2e_replay_pass_floor",
            "flake_ceiling_pct_7d",
            "runtime_guardrail",
        ] {
            assert!(
                thresholds.get(key).is_some(),
                "report.budgets[{idx}].thresholds missing `{key}`"
            );
        }

        let stage_results = budget["stage_results"]
            .as_array()
            .expect("report stage_results should be array");
        assert!(
            !stage_results.is_empty(),
            "report.budgets[{idx}].stage_results must be non-empty"
        );
        let mut observed_stage_ids = BTreeSet::new();
        let mut non_pass_stage_ids = Vec::new();
        for (stage_idx, stage) in stage_results.iter().enumerate() {
            for key in &required_stage_result_keys {
                assert!(
                    stage.get(key).is_some(),
                    "report.budgets[{idx}].stage_results[{stage_idx}] missing key `{key}`"
                );
            }
            let stage_id = stage["stage_id"]
                .as_str()
                .expect("stage_id should be string")
                .to_owned();
            assert!(
                observed_stage_ids.insert(stage_id.clone()),
                "report.budgets[{idx}] duplicate stage_id `{stage_id}`"
            );
            let stage_status = stage["status"]
                .as_str()
                .expect("stage status should be string")
                .to_owned();
            assert!(
                allowed_status_values.contains(stage_status.as_str()),
                "report.budgets[{idx}].stage_results[{stage_idx}].status `{stage_status}` outside allowed set"
            );
            if stage_status != "pass" {
                non_pass_stage_ids.push(stage_id.clone());
            }
            let stage_run_id = stage["run_id"]
                .as_str()
                .expect("stage run_id should be string");
            assert!(
                stage_run_id.starts_with(&format!("{report_run_id}::{budget_id}::")),
                "report.budgets[{idx}].stage_results[{stage_idx}].run_id not namespaced by report/budget run_id"
            );
            let stage_replay_command = stage["replay_command"]
                .as_str()
                .expect("stage replay_command should be string");
            if stage_replay_command.contains("cargo ") {
                assert!(
                    stage_replay_command.contains("rch exec --"),
                    "report.budgets[{idx}].stage_results[{stage_idx}] cargo replay must use rch"
                );
            }
            assert!(
                stage["observed_value"].is_object(),
                "report.budgets[{idx}].stage_results[{stage_idx}].observed_value should be object"
            );
            assert!(
                stage["threshold_value"].is_object(),
                "report.budgets[{idx}].stage_results[{stage_idx}].threshold_value should be object"
            );
            let stage_artifact_refs = stage["artifact_refs"]
                .as_array()
                .expect("stage artifact_refs should be array");
            assert!(
                !stage_artifact_refs.is_empty(),
                "report.budgets[{idx}].stage_results[{stage_idx}].artifact_refs must be non-empty"
            );
            for (art_idx, art_value) in stage_artifact_refs.iter().enumerate() {
                let path = art_value
                    .as_str()
                    .expect("stage artifact ref should be string");
                assert!(
                    root.join(path).exists(),
                    "report.budgets[{idx}].stage_results[{stage_idx}].artifact_refs[{art_idx}] missing `{path}`"
                );
            }
        }
        assert_eq!(
            observed_stage_ids, required_stage_ids,
            "report.budgets[{idx}] stage ID coverage drifted"
        );
        non_pass_stage_ids_by_budget.insert(budget_id.clone(), non_pass_stage_ids.clone());

        if status == "pass" {
            let failing_test_groups = budget["failing_test_groups"]
                .as_array()
                .expect("report failing_test_groups should be array");
            assert!(
                failing_test_groups.is_empty(),
                "pass budget `{budget_id}` cannot have failing_test_groups"
            );
            let missing_evidence = budget["missing_evidence_paths"]
                .as_array()
                .expect("report missing_evidence_paths should be array");
            assert!(
                missing_evidence.is_empty(),
                "pass budget `{budget_id}` cannot have missing_evidence_paths"
            );
            assert_eq!(
                observed["runtime_guardrail_pass"].as_bool(),
                Some(true),
                "pass budget `{budget_id}` must have runtime_guardrail_pass=true"
            );
            assert_eq!(
                observed["missing_evidence_count"].as_u64(),
                Some(0),
                "pass budget `{budget_id}` must have missing_evidence_count=0"
            );
            assert!(
                non_pass_stage_ids.is_empty(),
                "pass budget `{budget_id}` cannot have non-pass stage results"
            );
        } else {
            assert!(
                !non_pass_stage_ids.is_empty(),
                "non-pass budget `{budget_id}` must have at least one non-pass stage result"
            );
        }

        status_by_budget.push((budget_id, status));
    }

    assert_eq!(
        observed_report_budget_ids, required_budget_ids,
        "report budget coverage drifted"
    );

    let required_failure_fields =
        required_string_array(&schema, "required_failure_envelope_fields");
    let failure_envelopes = report["failure_envelopes"]
        .as_array()
        .expect("report.failure_envelopes should be array");
    let mut envelope_budget_ids = BTreeSet::new();
    for (idx, envelope) in failure_envelopes.iter().enumerate() {
        for key in &required_failure_fields {
            assert!(
                envelope.get(key).is_some(),
                "report.failure_envelopes[{idx}] missing key `{key}`"
            );
        }
        let budget_id = envelope["budget_id"]
            .as_str()
            .expect("failure envelope budget_id should be string");
        assert_eq!(
            envelope["run_id"].as_str(),
            Some(report_run_id.as_str()),
            "failure envelope run_id must match report.run_id"
        );
        let status = envelope["status"]
            .as_str()
            .expect("failure envelope status should be string");
        assert!(
            matches!(status, "warn" | "fail"),
            "failure envelope status must be warn|fail; got `{status}`"
        );
        let replay_metadata = envelope["replay_metadata"]
            .as_object()
            .expect("failure envelope replay_metadata should be object");
        for key in &required_failure_replay_metadata_keys {
            assert!(
                replay_metadata.contains_key(key),
                "failure envelope replay_metadata missing key `{key}`"
            );
        }
        assert_eq!(
            replay_metadata["run_id"].as_str(),
            Some(report_run_id.as_str()),
            "failure envelope replay_metadata.run_id must match report.run_id"
        );
        assert_eq!(
            replay_metadata["deterministic_seed"].as_str(),
            Some(report_seed),
            "failure envelope replay_metadata.deterministic_seed must match report.deterministic_seed"
        );
        let replay_gate_command = replay_metadata["gate_command"]
            .as_str()
            .expect("failure envelope replay_metadata.gate_command should be string");
        assert!(
            replay_gate_command.contains("rch exec --"),
            "failure envelope replay_metadata.gate_command must use rch"
        );
        let failing_stage_ids = replay_metadata["failing_stage_ids"]
            .as_array()
            .expect("failure envelope replay_metadata.failing_stage_ids should be array")
            .iter()
            .map(|value| {
                value
                    .as_str()
                    .expect("failure envelope replay_metadata.failing_stage_ids entries should be strings")
                    .to_owned()
            })
            .collect::<Vec<_>>();
        let failed_stage_count = replay_metadata["failed_stage_count"]
            .as_u64()
            .expect("failure envelope replay_metadata.failed_stage_count should be integer")
            as usize;
        assert_eq!(
            failed_stage_count,
            failing_stage_ids.len(),
            "failure envelope replay_metadata.failed_stage_count must match failing_stage_ids length"
        );
        let budget_non_pass_stages = non_pass_stage_ids_by_budget
            .get(budget_id)
            .cloned()
            .unwrap_or_default();
        let failing_stage_ids_set = failing_stage_ids.into_iter().collect::<BTreeSet<_>>();
        let budget_non_pass_stages_set =
            budget_non_pass_stages.into_iter().collect::<BTreeSet<_>>();
        assert_eq!(
            failing_stage_ids_set, budget_non_pass_stages_set,
            "failure envelope replay metadata stage failures must match budget stage_results"
        );
        envelope_budget_ids.insert(budget_id.to_owned());
        assert_eq!(
            envelope["owner_bead_id"].as_str(),
            Some("bd-315.23"),
            "failure envelope owner_bead_id must be bd-315.23"
        );
    }

    for (budget_id, status) in status_by_budget {
        if status == "pass" {
            assert!(
                !envelope_budget_ids.contains(&budget_id),
                "pass budget `{budget_id}` must not appear in failure_envelopes"
            );
        } else {
            assert!(
                envelope_budget_ids.contains(&budget_id),
                "non-pass budget `{budget_id}` must appear in failure_envelopes"
            );
        }
    }

    let derived_status = if report_budgets
        .iter()
        .any(|budget| budget["status"].as_str() == Some("fail"))
    {
        "fail"
    } else if report_budgets
        .iter()
        .any(|budget| budget["status"].as_str() == Some("warn"))
    {
        "warn"
    } else {
        "pass"
    };
    assert_eq!(
        report_status, derived_status,
        "report.status must match derived aggregate budget status"
    );

    for key in &required_quarantine_top_level_keys {
        assert!(
            quarantine.get(key).is_some(),
            "quarantine artifact missing top-level key `{key}`"
        );
    }
    assert_eq!(
        quarantine["source_bead_id"].as_str(),
        Some("bd-315.23"),
        "quarantine artifact must point to bd-315.23"
    );
    assert_eq!(
        quarantine["run_id"].as_str(),
        Some(report_run_id.as_str()),
        "quarantine.run_id must match report.run_id"
    );
    let quarantine_status = quarantine["status"]
        .as_str()
        .expect("quarantine.status should be string");
    assert!(
        matches!(quarantine_status, "active" | "clear"),
        "quarantine.status must be active|clear"
    );

    let flake_summary = report["flake_summary"]
        .as_object()
        .expect("report.flake_summary should be object");
    let quarantined_test_count = flake_summary["quarantined_test_count"]
        .as_u64()
        .expect("report.flake_summary.quarantined_test_count should be integer")
        as usize;

    let quarantined_tests = quarantine["quarantined_tests"]
        .as_array()
        .expect("quarantine.quarantined_tests should be array");
    assert_eq!(
        quarantined_test_count,
        quarantined_tests.len(),
        "quarantined test count drifted between report and quarantine artifact"
    );

    if quarantine_status == "clear" {
        assert!(
            quarantined_tests.is_empty(),
            "quarantine.status=clear requires zero quarantined tests"
        );
    } else {
        assert!(
            !quarantined_tests.is_empty(),
            "quarantine.status=active requires quarantined tests"
        );
    }

    for (idx, test) in quarantined_tests.iter().enumerate() {
        for key in &required_quarantine_test_keys {
            assert!(
                test.get(key).is_some(),
                "quarantine.quarantined_tests[{idx}] missing key `{key}`"
            );
        }
        assert_eq!(
            test["status"].as_str(),
            Some("quarantined"),
            "quarantine.quarantined_tests[{idx}].status must be `quarantined`"
        );
        assert_eq!(
            test["owner_bead_id"].as_str(),
            Some("bd-315.23"),
            "quarantine.quarantined_tests[{idx}].owner_bead_id must be bd-315.23"
        );
        assert_eq!(
            test["run_id"].as_str(),
            Some(report_run_id.as_str()),
            "quarantine.quarantined_tests[{idx}].run_id must match report.run_id"
        );
        let replay_command = test["replay_command"]
            .as_str()
            .expect("quarantine replay_command should be string");
        assert!(
            replay_command.contains("rch exec -- cargo"),
            "quarantine.quarantined_tests[{idx}].replay_command must use rch"
        );
    }
}
