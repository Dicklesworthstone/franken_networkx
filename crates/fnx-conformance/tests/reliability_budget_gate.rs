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

    for (idx, budget) in report_budgets.iter().enumerate() {
        for key in [
            "budget_id",
            "packet_family",
            "status",
            "failing_test_groups",
            "missing_evidence_paths",
            "observed",
            "thresholds",
            "gate_command",
            "artifact_paths",
            "owner_bead_id",
        ] {
            assert!(
                budget.get(key).is_some(),
                "report.budgets[{idx}] missing key `{key}`"
            );
        }

        let budget_id = budget["budget_id"]
            .as_str()
            .expect("report budget_id should be string")
            .to_owned();
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
        let status = envelope["status"]
            .as_str()
            .expect("failure envelope status should be string");
        assert!(
            matches!(status, "warn" | "fail"),
            "failure envelope status must be warn|fail; got `{status}`"
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

    assert_eq!(
        quarantine["source_bead_id"].as_str(),
        Some("bd-315.23"),
        "quarantine artifact must point to bd-315.23"
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
        for key in [
            "test_id",
            "flake_events",
            "observation_count",
            "status",
            "owner_bead_id",
            "replay_command",
            "artifact_refs",
        ] {
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
        let replay_command = test["replay_command"]
            .as_str()
            .expect("quarantine replay_command should be string");
        assert!(
            replay_command.contains("rch exec -- cargo"),
            "quarantine.quarantined_tests[{idx}].replay_command must use rch"
        );
    }
}
