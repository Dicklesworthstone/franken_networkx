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
        .unwrap_or_else(|| panic!("{key} should be array"))
        .iter()
        .map(|value| {
            value
                .as_str()
                .unwrap_or_else(|| panic!("{key} entries should be strings"))
        })
        .collect()
}

fn assert_path_exists(root: &Path, rel: &str, ctx: &str) {
    assert!(
        !rel.trim().is_empty(),
        "{ctx} should be non-empty path string"
    );
    let path = root.join(rel);
    assert!(path.exists(), "{ctx} should exist: {}", path.display());
}

fn assert_anchor(root: &Path, schema: &Value, anchor: &Value, ctx: &str) {
    let object = anchor
        .as_object()
        .unwrap_or_else(|| panic!("{ctx} should be object"));
    for key in required_string_array(schema, "required_anchor_keys") {
        assert!(
            object.contains_key(key),
            "{ctx} missing required key `{key}`"
        );
    }

    let crate_name = object
        .get("crate_name")
        .and_then(Value::as_str)
        .unwrap_or_else(|| panic!("{ctx}.crate_name should be string"));
    assert!(
        !crate_name.trim().is_empty(),
        "{ctx}.crate_name should be non-empty"
    );

    let symbol = object
        .get("symbol")
        .and_then(Value::as_str)
        .unwrap_or_else(|| panic!("{ctx}.symbol should be string"));
    assert!(
        !symbol.trim().is_empty(),
        "{ctx}.symbol should be non-empty"
    );

    let file_path = object
        .get("file_path")
        .and_then(Value::as_str)
        .unwrap_or_else(|| panic!("{ctx}.file_path should be string"));
    assert_path_exists(root, file_path, &format!("{ctx}.file_path"));

    let line_start = object
        .get("line_start")
        .and_then(Value::as_u64)
        .unwrap_or_else(|| panic!("{ctx}.line_start should be u64"));
    assert!(line_start >= 1, "{ctx}.line_start should be >= 1");
}

#[test]
fn doc_pass04_execution_paths_cover_branches_fallbacks_and_verification() {
    let root = repo_root();
    let artifact =
        load_json(&root.join("artifacts/docs/v1/doc_pass04_execution_path_tracing_v1.json"));
    let schema = load_json(
        &root.join("artifacts/docs/schema/v1/doc_pass04_execution_path_tracing_schema_v1.json"),
    );

    for key in required_string_array(&schema, "required_top_level_keys") {
        assert!(
            artifact.get(key).is_some(),
            "artifact missing top-level key `{key}`"
        );
    }

    let summary = artifact["execution_summary"]
        .as_object()
        .expect("execution_summary should be object");
    for key in required_string_array(&schema, "required_summary_keys") {
        assert!(
            summary.contains_key(key),
            "execution_summary missing key `{key}`"
        );
    }

    let execution_paths = artifact["execution_paths"]
        .as_array()
        .expect("execution_paths should be array");
    assert!(
        execution_paths.len() >= 7,
        "execution_paths should include at least seven core workflows"
    );

    let mut path_ids = BTreeSet::new();
    let mut branch_ids_by_path: BTreeMap<String, BTreeSet<String>> = BTreeMap::new();
    let mut branch_count = 0_u64;
    let mut fallback_count = 0_u64;
    let mut crate_names = BTreeSet::new();
    let mut bead_ids = BTreeSet::new();

    for path_row in execution_paths {
        for key in required_string_array(&schema, "required_execution_path_keys") {
            assert!(
                path_row.get(key).is_some(),
                "execution path row missing key `{key}`"
            );
        }
        let path_id = path_row["path_id"]
            .as_str()
            .expect("execution path path_id should be string");
        assert!(
            path_ids.insert(path_id.to_owned()),
            "duplicate execution path_id `{path_id}`"
        );

        let entrypoints = path_row["entrypoints"]
            .as_array()
            .expect("entrypoints should be array");
        assert!(
            !entrypoints.is_empty(),
            "{path_id} entrypoints should be non-empty"
        );
        for (entry_idx, anchor) in entrypoints.iter().enumerate() {
            assert_anchor(
                root.as_path(),
                &schema,
                anchor,
                &format!("{path_id}.entrypoints[{entry_idx}]"),
            );
            let crate_name = anchor["crate_name"]
                .as_str()
                .expect("entrypoint crate_name should be string");
            crate_names.insert(crate_name.to_owned());
        }

        let steps = path_row["primary_steps"]
            .as_array()
            .expect("primary_steps should be array");
        assert!(
            !steps.is_empty(),
            "{path_id} primary_steps should be non-empty"
        );
        for (step_idx, step) in steps.iter().enumerate() {
            for key in required_string_array(&schema, "required_step_keys") {
                assert!(
                    step.get(key).is_some(),
                    "{path_id}.primary_steps[{step_idx}] missing key `{key}`"
                );
            }
            assert_anchor(
                root.as_path(),
                &schema,
                &step["code_anchor"],
                &format!("{path_id}.primary_steps[{step_idx}].code_anchor"),
            );
            let output_artifacts = step["output_artifacts"]
                .as_array()
                .expect("output_artifacts should be array");
            assert!(
                !output_artifacts.is_empty(),
                "{path_id}.primary_steps[{step_idx}] output_artifacts should be non-empty"
            );
            for (art_idx, path) in output_artifacts.iter().enumerate() {
                let rel = path.as_str().unwrap_or_else(|| {
                    panic!("{path_id}.primary_steps[{step_idx}].output_artifacts[{art_idx}] should be string")
                });
                assert_path_exists(
                    root.as_path(),
                    rel,
                    &format!("{path_id}.primary_steps[{step_idx}].output_artifacts[{art_idx}]"),
                );
            }
        }

        let branches = path_row["branch_paths"]
            .as_array()
            .expect("branch_paths should be array");
        assert!(
            !branches.is_empty(),
            "{path_id} branch_paths should be non-empty"
        );
        let mut branch_ids = BTreeSet::new();
        for (branch_idx, branch) in branches.iter().enumerate() {
            for key in required_string_array(&schema, "required_branch_keys") {
                assert!(
                    branch.get(key).is_some(),
                    "{path_id}.branch_paths[{branch_idx}] missing key `{key}`"
                );
            }
            let branch_id = branch["branch_id"]
                .as_str()
                .expect("branch_id should be string");
            assert!(
                branch_ids.insert(branch_id.to_owned()),
                "{path_id} duplicate branch_id `{branch_id}`"
            );
            assert_anchor(
                root.as_path(),
                &schema,
                &branch["code_anchor"],
                &format!("{path_id}.branch_paths[{branch_idx}].code_anchor"),
            );
            let forensics_links = branch["forensics_links"]
                .as_array()
                .expect("forensics_links should be array");
            assert!(
                !forensics_links.is_empty(),
                "{path_id}.branch_paths[{branch_idx}] forensics_links should be non-empty"
            );
            for (idx, entry) in forensics_links.iter().enumerate() {
                let rel = entry.as_str().unwrap_or_else(|| {
                    panic!("{path_id}.branch_paths[{branch_idx}].forensics_links[{idx}] should be string")
                });
                assert_path_exists(
                    root.as_path(),
                    rel,
                    &format!("{path_id}.branch_paths[{branch_idx}].forensics_links[{idx}]"),
                );
            }
        }
        branch_count += branch_ids.len() as u64;
        branch_ids_by_path.insert(path_id.to_owned(), branch_ids.clone());

        let fallbacks = path_row["fallback_paths"]
            .as_array()
            .expect("fallback_paths should be array");
        assert!(
            !fallbacks.is_empty(),
            "{path_id} fallback_paths should be non-empty"
        );
        for (fallback_idx, fallback) in fallbacks.iter().enumerate() {
            for key in required_string_array(&schema, "required_fallback_keys") {
                assert!(
                    fallback.get(key).is_some(),
                    "{path_id}.fallback_paths[{fallback_idx}] missing key `{key}`"
                );
            }
            let branch_id = fallback["branch_id"]
                .as_str()
                .expect("fallback branch_id should be string");
            assert!(
                branch_ids.contains(branch_id),
                "{path_id}.fallback_paths[{fallback_idx}] references unknown branch_id `{branch_id}`"
            );
            let evidence_refs = fallback["evidence_refs"]
                .as_array()
                .expect("evidence_refs should be array");
            assert!(
                !evidence_refs.is_empty(),
                "{path_id}.fallback_paths[{fallback_idx}] evidence_refs should be non-empty"
            );
            for (idx, entry) in evidence_refs.iter().enumerate() {
                let rel = entry.as_str().unwrap_or_else(|| {
                    panic!("{path_id}.fallback_paths[{fallback_idx}].evidence_refs[{idx}] should be string")
                });
                assert_path_exists(
                    root.as_path(),
                    rel,
                    &format!("{path_id}.fallback_paths[{fallback_idx}].evidence_refs[{idx}]"),
                );
            }
        }
        fallback_count += fallbacks.len() as u64;

        let verification = path_row["verification_links"]
            .as_object()
            .expect("verification_links should be object");
        for key in required_string_array(&schema, "required_verification_keys") {
            let values = verification[key]
                .as_array()
                .unwrap_or_else(|| panic!("{path_id}.verification_links.{key} should be array"));
            assert!(
                !values.is_empty(),
                "{path_id}.verification_links.{key} should be non-empty"
            );
        }

        let linked_beads = path_row["linked_bead_ids"]
            .as_array()
            .expect("linked_bead_ids should be array");
        assert!(
            !linked_beads.is_empty(),
            "{path_id} linked_bead_ids should be non-empty"
        );
        for bead in linked_beads {
            bead_ids.insert(
                bead.as_str()
                    .expect("linked_bead_ids entries should be strings")
                    .to_owned(),
            );
        }

        let replay_command = path_row["replay_command"]
            .as_str()
            .expect("replay_command should be string");
        assert!(
            replay_command.contains("rch exec --"),
            "{path_id}.replay_command should use rch offload"
        );

        let structured_refs = path_row["structured_log_refs"]
            .as_array()
            .expect("structured_log_refs should be array");
        assert!(
            !structured_refs.is_empty(),
            "{path_id}.structured_log_refs should be non-empty"
        );
        for (idx, entry) in structured_refs.iter().enumerate() {
            let rel = entry
                .as_str()
                .unwrap_or_else(|| panic!("{path_id}.structured_log_refs[{idx}] should be string"));
            assert_path_exists(
                root.as_path(),
                rel,
                &format!("{path_id}.structured_log_refs[{idx}]"),
            );
        }
    }

    let branch_catalog = artifact["branch_catalog"]
        .as_array()
        .expect("branch_catalog should be array");
    assert!(
        !branch_catalog.is_empty(),
        "branch_catalog should be non-empty"
    );
    for (idx, row) in branch_catalog.iter().enumerate() {
        for key in required_string_array(&schema, "required_branch_catalog_keys") {
            assert!(
                row.get(key).is_some(),
                "branch_catalog[{idx}] missing key `{key}`"
            );
        }
        let path_id = row["path_id"]
            .as_str()
            .expect("branch_catalog path_id should be string");
        let branch_id = row["branch_id"]
            .as_str()
            .expect("branch_catalog branch_id should be string");
        assert!(
            path_ids.contains(path_id),
            "branch_catalog[{idx}] unknown path_id `{path_id}`"
        );
        assert!(
            branch_ids_by_path
                .get(path_id)
                .is_some_and(|set| set.contains(branch_id)),
            "branch_catalog[{idx}] unknown branch `{branch_id}` for path `{path_id}`"
        );
        assert_anchor(
            root.as_path(),
            &schema,
            &row["code_anchor"],
            &format!("branch_catalog[{idx}].code_anchor"),
        );
    }

    let fallback_index = artifact["fallback_index"]
        .as_array()
        .expect("fallback_index should be array");
    assert!(
        !fallback_index.is_empty(),
        "fallback_index should be non-empty"
    );
    for (idx, row) in fallback_index.iter().enumerate() {
        for key in required_string_array(&schema, "required_fallback_index_keys") {
            assert!(
                row.get(key).is_some(),
                "fallback_index[{idx}] missing key `{key}`"
            );
        }
        let path_id = row["path_id"]
            .as_str()
            .expect("fallback_index path_id should be string");
        let branch_id = row["branch_id"]
            .as_str()
            .expect("fallback_index branch_id should be string");
        assert!(
            path_ids.contains(path_id),
            "fallback_index[{idx}] unknown path_id `{path_id}`"
        );
        assert!(
            branch_ids_by_path
                .get(path_id)
                .is_some_and(|set| set.contains(branch_id)),
            "fallback_index[{idx}] unknown branch `{branch_id}` for path `{path_id}`"
        );
    }

    let crosswalk = artifact["verification_bead_crosswalk"]
        .as_array()
        .expect("verification_bead_crosswalk should be array");
    assert!(
        !crosswalk.is_empty(),
        "verification_bead_crosswalk should be non-empty"
    );
    for (idx, row) in crosswalk.iter().enumerate() {
        for key in required_string_array(&schema, "required_crosswalk_keys") {
            assert!(
                row.get(key).is_some(),
                "verification_bead_crosswalk[{idx}] missing key `{key}`"
            );
        }
        let path_refs = row["path_ids"]
            .as_array()
            .expect("crosswalk.path_ids should be array");
        assert!(
            !path_refs.is_empty(),
            "verification_bead_crosswalk[{idx}].path_ids should be non-empty"
        );
        for path_ref in path_refs {
            let path_id = path_ref
                .as_str()
                .expect("crosswalk path ref should be string");
            assert!(
                path_ids.contains(path_id),
                "verification_bead_crosswalk[{idx}] unknown path_id `{path_id}`"
            );
        }
    }

    assert_eq!(
        summary["workflow_count"]
            .as_u64()
            .expect("workflow_count should be u64"),
        path_ids.len() as u64,
        "workflow_count mismatch"
    );
    assert_eq!(
        summary["branch_count"]
            .as_u64()
            .expect("branch_count should be u64"),
        branch_count,
        "branch_count mismatch"
    );
    assert_eq!(
        summary["fallback_count"]
            .as_u64()
            .expect("fallback_count should be u64"),
        fallback_count,
        "fallback_count mismatch"
    );
    assert_eq!(
        summary["workspace_crate_count"]
            .as_u64()
            .expect("workspace_crate_count should be u64"),
        crate_names.len() as u64,
        "workspace_crate_count mismatch"
    );
    assert_eq!(
        summary["verification_bead_count"]
            .as_u64()
            .expect("verification_bead_count should be u64"),
        bead_ids.len() as u64,
        "verification_bead_count mismatch"
    );

    let alien = artifact["alien_uplift_contract_card"]
        .as_object()
        .expect("alien_uplift_contract_card should be object");
    let ev_score = alien["ev_score"]
        .as_f64()
        .expect("ev_score should be numeric");
    assert!(ev_score >= 2.0, "ev_score must be >= 2.0");
    let baseline = alien["baseline_comparator"]
        .as_str()
        .expect("baseline_comparator should be string");
    assert!(
        !baseline.trim().is_empty(),
        "baseline_comparator should be non-empty"
    );

    let profile = artifact["profile_first_artifacts"]
        .as_object()
        .expect("profile_first_artifacts should be object");
    for key in ["baseline", "hotspot", "delta"] {
        let rel = profile[key]
            .as_str()
            .unwrap_or_else(|| panic!("profile_first_artifacts.{key} should be string"));
        assert_path_exists(
            root.as_path(),
            rel,
            &format!("profile_first_artifacts.{key}"),
        );
    }

    let optimization = artifact["optimization_lever_policy"]
        .as_object()
        .expect("optimization_lever_policy should be object");
    assert_eq!(
        optimization["rule"]
            .as_str()
            .expect("optimization_lever_policy.rule should be string"),
        "exactly_one_optimization_lever_per_change",
        "optimization_lever_policy.rule mismatch"
    );
    let optimization_evidence = optimization["evidence_path"]
        .as_str()
        .expect("optimization_lever_policy.evidence_path should be string");
    assert_path_exists(
        root.as_path(),
        optimization_evidence,
        "optimization_lever_policy.evidence_path",
    );

    let decision = artifact["decision_theoretic_runtime_contract"]
        .as_object()
        .expect("decision_theoretic_runtime_contract should be object");
    for key in required_string_array(&schema, "required_decision_contract_keys") {
        assert!(
            decision.contains_key(key),
            "decision_theoretic_runtime_contract missing key `{key}`"
        );
    }
    let thresholds = decision["safe_mode_fallback"]["trigger_thresholds"]
        .as_object()
        .expect("safe_mode_fallback.trigger_thresholds should be object");
    assert!(
        !thresholds.is_empty(),
        "safe_mode_fallback.trigger_thresholds should be non-empty"
    );

    let isomorphism = artifact["isomorphism_proof_artifacts"]
        .as_array()
        .expect("isomorphism_proof_artifacts should be array");
    assert!(
        !isomorphism.is_empty(),
        "isomorphism_proof_artifacts should be non-empty"
    );
    for (idx, entry) in isomorphism.iter().enumerate() {
        let rel = entry
            .as_str()
            .unwrap_or_else(|| panic!("isomorphism_proof_artifacts[{idx}] should be string"));
        assert_path_exists(
            root.as_path(),
            rel,
            &format!("isomorphism_proof_artifacts[{idx}]"),
        );
    }

    let logging = artifact["structured_logging_evidence"]
        .as_array()
        .expect("structured_logging_evidence should be array");
    assert!(
        !logging.is_empty(),
        "structured_logging_evidence should be non-empty"
    );
    for (idx, entry) in logging.iter().enumerate() {
        let rel = entry
            .as_str()
            .unwrap_or_else(|| panic!("structured_logging_evidence[{idx}] should be string"));
        assert_path_exists(
            root.as_path(),
            rel,
            &format!("structured_logging_evidence[{idx}]"),
        );
    }
}
