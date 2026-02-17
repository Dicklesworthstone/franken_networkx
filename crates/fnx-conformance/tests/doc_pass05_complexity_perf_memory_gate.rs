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
fn doc_pass05_complexity_perf_memory_is_complete_and_cross_linked() {
    let root = repo_root();
    let artifact =
        load_json(&root.join("artifacts/docs/v1/doc_pass05_complexity_perf_memory_v1.json"));
    let schema = load_json(
        &root.join("artifacts/docs/schema/v1/doc_pass05_complexity_perf_memory_schema_v1.json"),
    );

    for key in required_string_array(&schema, "required_top_level_keys") {
        assert!(
            artifact.get(key).is_some(),
            "artifact missing top-level key `{key}`"
        );
    }

    let summary = artifact["characterization_summary"]
        .as_object()
        .expect("characterization_summary should be object");
    for key in required_string_array(&schema, "required_summary_keys") {
        assert!(
            summary.contains_key(key),
            "characterization_summary missing key `{key}`"
        );
    }

    let families = artifact["operation_families"]
        .as_array()
        .expect("operation_families should be array");
    assert!(
        families.len() >= 6,
        "operation_families should include at least six core families"
    );

    let expected_families = BTreeSet::from([
        "algorithmic_core".to_owned(),
        "conformance_execution".to_owned(),
        "conversion_and_io".to_owned(),
        "dispatch_runtime_policy".to_owned(),
        "generator_workloads".to_owned(),
        "graph_storage_semantics".to_owned(),
    ]);

    let mut family_ids = BTreeSet::new();
    let mut operation_ids = BTreeSet::new();
    let mut op_to_risk_refs: BTreeMap<String, BTreeSet<String>> = BTreeMap::new();
    let mut high_risk_operation_count = 0_u64;

    for (family_idx, family) in families.iter().enumerate() {
        for key in required_string_array(&schema, "required_family_keys") {
            assert!(
                family.get(key).is_some(),
                "operation_families[{family_idx}] missing key `{key}`"
            );
        }
        let family_id = family["family_id"]
            .as_str()
            .expect("family_id should be string");
        family_ids.insert(family_id.to_owned());

        let legacy_paths = family["legacy_scope_paths"]
            .as_array()
            .expect("legacy_scope_paths should be array");
        assert!(
            !legacy_paths.is_empty(),
            "{family_id}.legacy_scope_paths should be non-empty"
        );

        let crates = family["rust_crates"]
            .as_array()
            .expect("rust_crates should be array");
        assert!(
            !crates.is_empty(),
            "{family_id}.rust_crates should be non-empty"
        );

        let operations = family["operations"]
            .as_array()
            .expect("operations should be array");
        assert!(
            !operations.is_empty(),
            "{family_id}.operations should be non-empty"
        );

        for (op_idx, operation) in operations.iter().enumerate() {
            for key in required_string_array(&schema, "required_operation_keys") {
                assert!(
                    operation.get(key).is_some(),
                    "{family_id}.operations[{op_idx}] missing key `{key}`"
                );
            }

            let operation_id = operation["operation_id"]
                .as_str()
                .expect("operation_id should be string");
            assert!(
                operation_ids.insert(operation_id.to_owned()),
                "duplicate operation_id `{operation_id}`"
            );

            let complexity_time = operation["complexity_time"]
                .as_str()
                .expect("complexity_time should be string");
            assert!(
                complexity_time.starts_with("O("),
                "{operation_id}.complexity_time should start with O("
            );
            let complexity_space = operation["complexity_space"]
                .as_str()
                .expect("complexity_space should be string");
            assert!(
                complexity_space.starts_with("O("),
                "{operation_id}.complexity_space should start with O("
            );

            assert_anchor(
                root.as_path(),
                &schema,
                &operation["code_anchor"],
                &format!("{operation_id}.code_anchor"),
            );

            let signals = operation["hotspot_signals"]
                .as_array()
                .expect("hotspot_signals should be array");
            assert!(
                !signals.is_empty(),
                "{operation_id}.hotspot_signals should be non-empty"
            );
            for (signal_idx, signal) in signals.iter().enumerate() {
                let rel = signal.as_str().unwrap_or_else(|| {
                    panic!("{operation_id}.hotspot_signals[{signal_idx}] should be string")
                });
                assert_path_exists(
                    root.as_path(),
                    rel,
                    &format!("{operation_id}.hotspot_signals[{signal_idx}]"),
                );
            }

            let parity_constraints = operation["parity_constraints"]
                .as_array()
                .expect("parity_constraints should be array");
            assert!(
                !parity_constraints.is_empty(),
                "{operation_id}.parity_constraints should be non-empty"
            );

            let hooks = operation["validation_hooks"]
                .as_object()
                .expect("validation_hooks should be object");
            for hook_key in required_string_array(&schema, "required_validation_hook_keys") {
                let hook_values = hooks[hook_key].as_array().unwrap_or_else(|| {
                    panic!("{operation_id}.validation_hooks.{hook_key} should be array")
                });
                assert!(
                    !hook_values.is_empty(),
                    "{operation_id}.validation_hooks.{hook_key} should be non-empty"
                );
            }

            let replay = operation["replay_command"]
                .as_str()
                .expect("replay_command should be string");
            assert!(
                replay.contains("rch exec --"),
                "{operation_id}.replay_command should use rch offload"
            );

            let risk_tier = operation["risk_tier"]
                .as_str()
                .expect("risk_tier should be string");
            assert!(
                ["low", "medium", "high"].contains(&risk_tier),
                "{operation_id}.risk_tier should be low|medium|high"
            );
            if risk_tier == "high" {
                high_risk_operation_count += 1;
            }

            let risk_refs = operation["optimization_risk_note_ids"]
                .as_array()
                .expect("optimization_risk_note_ids should be array");
            assert!(
                !risk_refs.is_empty(),
                "{operation_id}.optimization_risk_note_ids should be non-empty"
            );
            let mut risk_set = BTreeSet::new();
            for risk_ref in risk_refs {
                let risk_id = risk_ref
                    .as_str()
                    .expect("optimization_risk_note_ids entries should be strings");
                risk_set.insert(risk_id.to_owned());
            }
            op_to_risk_refs.insert(operation_id.to_owned(), risk_set);
        }
    }

    assert_eq!(
        family_ids, expected_families,
        "family_id set drift detected"
    );

    let hotspot_hypotheses = artifact["hotspot_hypotheses"]
        .as_array()
        .expect("hotspot_hypotheses should be array");
    assert!(
        !hotspot_hypotheses.is_empty(),
        "hotspot_hypotheses should be non-empty"
    );

    let mut hypothesis_ids = BTreeSet::new();
    for (idx, hypothesis) in hotspot_hypotheses.iter().enumerate() {
        for key in required_string_array(&schema, "required_hotspot_keys") {
            assert!(
                hypothesis.get(key).is_some(),
                "hotspot_hypotheses[{idx}] missing key `{key}`"
            );
        }
        let hypothesis_id = hypothesis["hypothesis_id"]
            .as_str()
            .expect("hypothesis_id should be string");
        assert!(
            hypothesis_ids.insert(hypothesis_id.to_owned()),
            "duplicate hypothesis_id `{hypothesis_id}`"
        );
        let operation_id = hypothesis["operation_id"]
            .as_str()
            .expect("operation_id should be string");
        assert!(
            operation_ids.contains(operation_id),
            "unknown hotspot operation_id `{operation_id}`"
        );
        let evidence_refs = hypothesis["evidence_refs"]
            .as_array()
            .expect("evidence_refs should be array");
        assert!(
            !evidence_refs.is_empty(),
            "{hypothesis_id}.evidence_refs should be non-empty"
        );
        for (evidence_idx, evidence) in evidence_refs.iter().enumerate() {
            let rel = evidence.as_str().unwrap_or_else(|| {
                panic!("{hypothesis_id}.evidence_refs[{evidence_idx}] should be string")
            });
            assert_path_exists(
                root.as_path(),
                rel,
                &format!("{hypothesis_id}.evidence_refs[{evidence_idx}]"),
            );
        }
    }

    let risk_notes = artifact["optimization_risk_notes"]
        .as_array()
        .expect("optimization_risk_notes should be array");
    assert!(
        !risk_notes.is_empty(),
        "optimization_risk_notes should be non-empty"
    );
    let mut risk_note_ids = BTreeSet::new();
    let mut risk_note_owner: BTreeMap<String, String> = BTreeMap::new();

    for (idx, risk_note) in risk_notes.iter().enumerate() {
        for key in required_string_array(&schema, "required_risk_note_keys") {
            assert!(
                risk_note.get(key).is_some(),
                "optimization_risk_notes[{idx}] missing key `{key}`"
            );
        }
        let risk_note_id = risk_note["risk_note_id"]
            .as_str()
            .expect("risk_note_id should be string");
        assert!(
            risk_note_ids.insert(risk_note_id.to_owned()),
            "duplicate risk_note_id `{risk_note_id}`"
        );
        let operation_id = risk_note["operation_id"]
            .as_str()
            .expect("risk note operation_id should be string");
        assert!(
            operation_ids.contains(operation_id),
            "risk note references unknown operation `{operation_id}`"
        );
        risk_note_owner.insert(risk_note_id.to_owned(), operation_id.to_owned());

        let allowed = risk_note["allowed_optimization_levers"]
            .as_array()
            .expect("allowed_optimization_levers should be array");
        assert!(
            !allowed.is_empty(),
            "{risk_note_id}.allowed_optimization_levers should be non-empty"
        );
        let forbidden = risk_note["forbidden_changes"]
            .as_array()
            .expect("forbidden_changes should be array");
        assert!(
            !forbidden.is_empty(),
            "{risk_note_id}.forbidden_changes should be non-empty"
        );
        let verification = risk_note["verification_requirements"]
            .as_array()
            .expect("verification_requirements should be array");
        assert!(
            !verification.is_empty(),
            "{risk_note_id}.verification_requirements should be non-empty"
        );
    }

    for (operation_id, risk_refs) in op_to_risk_refs {
        for risk_ref in risk_refs {
            assert!(
                risk_note_ids.contains(&risk_ref),
                "{operation_id} references missing risk note {risk_ref}"
            );
            let owner = risk_note_owner
                .get(&risk_ref)
                .unwrap_or_else(|| panic!("missing owner for risk note {risk_ref}"));
            assert_eq!(
                owner, &operation_id,
                "{operation_id} references risk note {risk_ref} owned by {owner}"
            );
        }
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
        let linked_ops = row["linked_operation_ids"]
            .as_array()
            .expect("linked_operation_ids should be array");
        assert!(
            !linked_ops.is_empty(),
            "verification_bead_crosswalk[{idx}].linked_operation_ids should be non-empty"
        );
        for operation in linked_ops {
            let operation_id = operation
                .as_str()
                .expect("linked operation ids should be strings");
            assert!(
                operation_ids.contains(operation_id),
                "crosswalk references unknown operation `{operation_id}`"
            );
        }
    }

    assert_eq!(
        summary["family_count"]
            .as_u64()
            .expect("family_count should be u64"),
        family_ids.len() as u64,
        "family_count mismatch"
    );
    assert_eq!(
        summary["operation_count"]
            .as_u64()
            .expect("operation_count should be u64"),
        operation_ids.len() as u64,
        "operation_count mismatch"
    );
    assert_eq!(
        summary["high_risk_operation_count"]
            .as_u64()
            .expect("high_risk_operation_count should be u64"),
        high_risk_operation_count,
        "high_risk_operation_count mismatch"
    );
    assert_eq!(
        summary["hotspot_hypothesis_count"]
            .as_u64()
            .expect("hotspot_hypothesis_count should be u64"),
        hotspot_hypotheses.len() as u64,
        "hotspot_hypothesis_count mismatch"
    );
    assert_eq!(
        summary["optimization_risk_note_count"]
            .as_u64()
            .expect("optimization_risk_note_count should be u64"),
        risk_note_ids.len() as u64,
        "optimization_risk_note_count mismatch"
    );

    let alien = artifact["alien_uplift_contract_card"]
        .as_object()
        .expect("alien_uplift_contract_card should be object");
    let ev_score = alien["ev_score"]
        .as_f64()
        .expect("ev_score should be numeric");
    assert!(ev_score >= 2.0, "ev_score must be >= 2.0");

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
