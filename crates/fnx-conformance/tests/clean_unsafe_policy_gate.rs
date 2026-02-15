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

#[test]
fn clean_unsafe_policy_defaults_are_fail_closed() {
    let root = repo_root();
    let artifact =
        load_json(&root.join("artifacts/clean/v1/clean_unsafe_exception_registry_v1.json"));
    let schema = load_json(
        &root.join("artifacts/clean/schema/v1/clean_unsafe_exception_registry_schema_v1.json"),
    );

    for key in required_string_array(&schema, "required_top_level_keys") {
        assert!(
            artifact.get(key).is_some(),
            "artifact missing top-level key `{key}`"
        );
    }

    let policy_defaults = artifact["policy_defaults"]
        .as_object()
        .expect("policy_defaults should be object");
    for key in required_string_array(&schema, "required_policy_default_keys") {
        assert!(
            policy_defaults.get(key).is_some(),
            "policy_defaults missing `{key}`"
        );
    }
    let unknown_behavior = policy_defaults["unknown_unsafe_behavior"]
        .as_str()
        .expect("unknown_unsafe_behavior should be string");
    assert_eq!(
        unknown_behavior, "fail_closed",
        "unknown unsafe behavior must be fail_closed"
    );

    let coverage = artifact["coverage_snapshot"]
        .as_object()
        .expect("coverage_snapshot should be object");
    for key in required_string_array(&schema, "required_coverage_snapshot_keys") {
        assert!(
            coverage.get(key).is_some(),
            "coverage_snapshot missing `{key}`"
        );
    }

    let workspace_crates = coverage["workspace_crates"]
        .as_array()
        .expect("workspace_crates should be array");
    assert!(
        !workspace_crates.is_empty(),
        "workspace_crates should be non-empty"
    );
    for (idx, path_text) in workspace_crates.iter().enumerate() {
        let crate_path = path_text
            .as_str()
            .unwrap_or_else(|| panic!("workspace_crates[{idx}] should be string"));
        assert_path(
            crate_path,
            &format!("coverage_snapshot.workspace_crates[{idx}]"),
            &root,
        );
        let lib_path = root.join(crate_path).join("src/lib.rs");
        let lib_raw = fs::read_to_string(&lib_path)
            .unwrap_or_else(|err| panic!("failed to read {}: {err}", lib_path.display()));
        assert!(
            lib_raw.contains("#![forbid(unsafe_code)]"),
            "{} must include #![forbid(unsafe_code)]",
            lib_path.display()
        );
    }

    let forbid_missing = coverage["forbid_unsafe_missing"]
        .as_array()
        .expect("forbid_unsafe_missing should be array");
    assert!(
        forbid_missing.is_empty(),
        "forbid_unsafe_missing must be empty for policy readiness"
    );

    let unsafe_findings = coverage["unsafe_findings"]
        .as_array()
        .expect("unsafe_findings should be array");

    let exceptions = artifact["exception_registry"]
        .as_array()
        .expect("exception_registry should be array");
    let required_exception_keys = required_string_array(&schema, "required_exception_entry_keys");
    let allowed_status = required_string_array(&schema, "allowed_exception_status")
        .into_iter()
        .collect::<BTreeSet<_>>();

    let mut approved_exception_paths: BTreeMap<String, usize> = BTreeMap::new();
    for (idx, exception) in exceptions.iter().enumerate() {
        for key in &required_exception_keys {
            assert!(
                exception.get(*key).is_some(),
                "exception_registry[{idx}] missing `{key}`"
            );
        }

        let path = exception["path"]
            .as_str()
            .expect("exception path should be string");
        assert_path(path, &format!("exception_registry[{idx}].path"), &root);

        let status = exception["status"]
            .as_str()
            .expect("exception status should be string");
        assert!(
            allowed_status.contains(status),
            "exception_registry[{idx}] status `{status}` outside allowed set"
        );

        let review_every_days = exception["review_every_days"]
            .as_i64()
            .expect("review_every_days should be integer");
        assert!(
            review_every_days >= 1,
            "exception_registry[{idx}] review_every_days should be >= 1"
        );

        let owner = exception["owner"].as_str().expect("owner should be string");
        assert!(
            !owner.trim().is_empty(),
            "exception_registry[{idx}] owner should be non-empty"
        );

        let mitigation = exception["mitigation_plan"]
            .as_str()
            .expect("mitigation_plan should be string");
        assert!(
            !mitigation.trim().is_empty(),
            "exception_registry[{idx}] mitigation_plan should be non-empty"
        );

        let threat_note = exception["threat_note"]
            .as_str()
            .expect("threat_note should be string");
        assert!(
            !threat_note.trim().is_empty(),
            "exception_registry[{idx}] threat_note should be non-empty"
        );

        let expires_at = exception["expires_at_utc"]
            .as_str()
            .expect("expires_at_utc should be string");
        assert!(
            !expires_at.trim().is_empty(),
            "exception_registry[{idx}] expires_at_utc should be non-empty"
        );

        let tests = exception["tests"]
            .as_array()
            .expect("tests should be array");
        if status == "approved" {
            assert!(
                !tests.is_empty(),
                "approved exception_registry[{idx}] must include tests"
            );
            *approved_exception_paths
                .entry(path.to_string())
                .or_insert(0usize) += 1;
        }

        for (test_idx, test_path) in tests.iter().enumerate() {
            let test_path = test_path.as_str().unwrap_or_else(|| {
                panic!("exception_registry[{idx}].tests[{test_idx}] should be string")
            });
            assert_path(
                test_path,
                &format!("exception_registry[{idx}].tests[{test_idx}]"),
                &root,
            );
        }
    }

    if !unsafe_findings.is_empty() {
        for (idx, finding) in unsafe_findings.iter().enumerate() {
            let path = finding["path"]
                .as_str()
                .unwrap_or_else(|| panic!("unsafe_findings[{idx}].path should be string"));
            assert_path(path, &format!("unsafe_findings[{idx}].path"), &root);
            let line = finding["line"]
                .as_i64()
                .unwrap_or_else(|| panic!("unsafe_findings[{idx}].line should be integer"));
            assert!(line >= 1, "unsafe_findings[{idx}].line should be >= 1");
            assert!(
                approved_exception_paths.contains_key(path),
                "unsafe finding at {path} is missing approved exception mapping"
            );
        }
    }

    let fail_closed_controls = artifact["fail_closed_controls"]
        .as_array()
        .expect("fail_closed_controls should be array");
    assert!(
        !fail_closed_controls.is_empty(),
        "fail_closed_controls should be non-empty"
    );
    let required_fail_closed_keys =
        required_string_array(&schema, "required_fail_closed_control_keys");
    for (idx, control) in fail_closed_controls.iter().enumerate() {
        for key in &required_fail_closed_keys {
            assert!(
                control.get(*key).is_some(),
                "fail_closed_controls[{idx}] missing `{key}`"
            );
        }
    }

    let audit = artifact["audit_enforcement"]
        .as_object()
        .expect("audit_enforcement should be object");
    for key in required_string_array(&schema, "required_audit_enforcement_keys") {
        let text = audit[key]
            .as_str()
            .unwrap_or_else(|| panic!("audit_enforcement.{key} should be string"));
        assert!(
            !text.trim().is_empty(),
            "audit_enforcement.{key} should be non-empty"
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
        "max_unmapped_unsafe_findings",
        "max_expired_approved_exceptions",
        "max_missing_forbid_crates",
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
            "trigger_thresholds[{idx}] threshold must be >= 1"
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
