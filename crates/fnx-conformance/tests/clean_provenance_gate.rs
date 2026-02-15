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
fn clean_provenance_ledger_is_lineage_complete_and_separated() {
    let root = repo_root();
    let artifact = load_json(&root.join("artifacts/clean/v1/clean_provenance_ledger_v1.json"));
    let schema =
        load_json(&root.join("artifacts/clean/schema/v1/clean_provenance_ledger_schema_v1.json"));

    for key in required_string_array(&schema, "required_top_level_keys") {
        assert!(
            artifact.get(key).is_some(),
            "artifact missing top-level key `{key}`"
        );
    }

    let workflow = artifact["separation_workflow"]
        .as_object()
        .expect("separation_workflow should be object");
    for key in required_string_array(&schema, "required_workflow_keys") {
        assert!(
            workflow.get(key).is_some(),
            "separation_workflow missing key `{key}`"
        );
    }

    let stages = workflow["separation_stages"]
        .as_array()
        .expect("separation_stages should be array");
    assert!(!stages.is_empty(), "separation_stages should be non-empty");
    let required_stage_keys = required_string_array(&schema, "required_stage_keys");
    for (idx, stage) in stages.iter().enumerate() {
        for key in &required_stage_keys {
            assert!(
                stage.get(*key).is_some(),
                "separation_stages[{idx}] missing `{key}`"
            );
        }
        assert!(
            !stage["owner_role"]
                .as_str()
                .expect("owner_role should be string")
                .trim()
                .is_empty(),
            "separation_stages[{idx}].owner_role should be non-empty"
        );
    }

    let handoff_controls = workflow["handoff_controls"]
        .as_array()
        .expect("handoff_controls should be array");
    assert!(
        !handoff_controls.is_empty(),
        "handoff_controls should be non-empty"
    );
    let required_handoff_control_keys =
        required_string_array(&schema, "required_handoff_control_keys");
    for (idx, control) in handoff_controls.iter().enumerate() {
        for key in &required_handoff_control_keys {
            assert!(
                control.get(*key).is_some(),
                "handoff_controls[{idx}] missing `{key}`"
            );
        }
    }

    let required_families = required_string_array(&schema, "allowed_lineage_families")
        .into_iter()
        .collect::<BTreeSet<_>>();

    let required_record_keys = required_string_array(&schema, "required_record_keys");
    let required_anchor_keys = required_string_array(&schema, "required_anchor_keys");
    let required_impl_keys = required_string_array(&schema, "required_implementation_ref_keys");
    let required_handoff_keys = required_string_array(&schema, "required_handoff_boundary_keys");
    let required_signoff_keys = required_string_array(&schema, "required_signoff_keys");

    let records = artifact["provenance_records"]
        .as_array()
        .expect("provenance_records should be array");
    assert!(
        records.len() >= required_families.len(),
        "provenance_records should include at least one row per required family"
    );

    let mut seen_record_ids = BTreeSet::new();
    let mut seen_packet_ids = BTreeSet::new();
    let mut observed_families = BTreeSet::new();
    let mut ambiguity_refs_by_record = BTreeMap::<String, BTreeSet<String>>::new();

    let confidence_range = schema["confidence_range"]
        .as_object()
        .expect("confidence_range should be object");
    let min_confidence = confidence_range["min"]
        .as_f64()
        .expect("confidence_range.min should be numeric");
    let max_confidence = confidence_range["max"]
        .as_f64()
        .expect("confidence_range.max should be numeric");

    let allowed_signoff_status = required_string_array(&schema, "allowed_signoff_status")
        .into_iter()
        .collect::<BTreeSet<_>>();

    for (idx, record) in records.iter().enumerate() {
        let record_id = record["record_id"]
            .as_str()
            .expect("record_id should be string");
        assert!(
            seen_record_ids.insert(record_id.to_string()),
            "duplicate record_id detected: {record_id}"
        );
        for key in &required_record_keys {
            assert!(
                record.get(*key).is_some(),
                "record {record_id} missing key `{key}`"
            );
        }

        let packet_id = record["packet_id"]
            .as_str()
            .expect("packet_id should be string");
        assert!(
            seen_packet_ids.insert(packet_id.to_string()),
            "duplicate packet_id detected: {packet_id}"
        );

        let family = record["lineage_family"]
            .as_str()
            .expect("lineage_family should be string");
        observed_families.insert(family);
        assert!(
            required_families.contains(family),
            "record {record_id} has unsupported lineage family {family}"
        );

        let anchor = record["legacy_source_anchor"]
            .as_object()
            .expect("legacy_source_anchor should be object");
        for key in &required_anchor_keys {
            assert!(
                anchor.get(*key).is_some(),
                "record {record_id} legacy_source_anchor missing `{key}`"
            );
        }
        let anchor_path = anchor["path"]
            .as_str()
            .expect("anchor path should be string");
        assert_path(anchor_path, &format!("record {record_id} anchor"), &root);
        let anchor_symbols = anchor["symbols"]
            .as_array()
            .expect("anchor symbols should be array");
        assert!(
            !anchor_symbols.is_empty(),
            "record {record_id} anchor symbols must be non-empty"
        );

        let impl_refs = record["implementation_artifact_refs"]
            .as_array()
            .expect("implementation_artifact_refs should be array");
        assert!(
            !impl_refs.is_empty(),
            "record {record_id} implementation_artifact_refs should be non-empty"
        );
        for (impl_idx, impl_ref) in impl_refs.iter().enumerate() {
            for key in &required_impl_keys {
                assert!(
                    impl_ref.get(*key).is_some(),
                    "record {record_id} implementation_artifact_refs[{impl_idx}] missing `{key}`"
                );
            }
            let path = impl_ref["path"]
                .as_str()
                .expect("impl ref path should be string");
            assert_path(
                path,
                &format!("record {record_id} implementation_artifact_refs[{impl_idx}]"),
                &root,
            );
        }

        let conformance_refs = record["conformance_evidence_refs"]
            .as_array()
            .expect("conformance_evidence_refs should be array");
        assert!(
            !conformance_refs.is_empty(),
            "record {record_id} conformance_evidence_refs should be non-empty"
        );
        for (conf_idx, path_text) in conformance_refs.iter().enumerate() {
            let path = path_text.as_str().unwrap_or_else(|| {
                panic!("record {record_id} conformance_evidence_refs[{conf_idx}] should be string")
            });
            assert_path(
                path,
                &format!("record {record_id} conformance_evidence_refs[{conf_idx}]"),
                &root,
            );
        }

        let boundary = record["handoff_boundary"]
            .as_object()
            .expect("handoff_boundary should be object");
        for key in &required_handoff_keys {
            assert!(
                boundary.get(*key).is_some(),
                "record {record_id} handoff_boundary missing `{key}`"
            );
        }
        let extractor = boundary["extractor_role"]
            .as_str()
            .expect("extractor_role should be string");
        let implementer = boundary["implementer_role"]
            .as_str()
            .expect("implementer_role should be string");
        assert!(
            extractor != implementer,
            "record {record_id} should keep extractor/implementer roles separate"
        );
        let handoff_path = boundary["handoff_artifact"]
            .as_str()
            .expect("handoff_artifact should be string");
        assert_path(
            handoff_path,
            &format!("record {record_id} handoff_boundary"),
            &root,
        );

        let signoff = record["reviewer_signoff"]
            .as_object()
            .expect("reviewer_signoff should be object");
        for key in &required_signoff_keys {
            assert!(
                signoff.get(*key).is_some(),
                "record {record_id} reviewer_signoff missing `{key}`"
            );
        }
        let status = signoff["status"]
            .as_str()
            .expect("reviewer_signoff.status should be string");
        assert!(
            allowed_signoff_status.contains(status),
            "record {record_id} reviewer_signoff.status `{status}` not in allowed set"
        );

        let confidence = record["confidence_rating"]
            .as_f64()
            .expect("confidence_rating should be numeric");
        assert!(
            confidence >= min_confidence && confidence <= max_confidence,
            "record {record_id} confidence {confidence} outside [{min_confidence}, {max_confidence}]"
        );

        if record["lineage_prev_record_id"].is_null() {
            assert_eq!(
                idx, 0,
                "only first record should have null lineage_prev_record_id"
            );
        } else {
            let prev = record["lineage_prev_record_id"]
                .as_str()
                .expect("lineage_prev_record_id should be string or null");
            assert!(
                seen_record_ids.contains(prev),
                "record {record_id} lineage_prev_record_id `{prev}` should reference earlier row"
            );
        }

        let mut ambiguity_refs = BTreeSet::new();
        for (amb_idx, ref_id) in record["ambiguity_ref_ids"]
            .as_array()
            .expect("ambiguity_ref_ids should be array")
            .iter()
            .enumerate()
        {
            let ref_id = ref_id.as_str().unwrap_or_else(|| {
                panic!("record {record_id} ambiguity_ref_ids[{amb_idx}] should be string")
            });
            ambiguity_refs.insert(ref_id.to_string());
        }
        ambiguity_refs_by_record.insert(record_id.to_string(), ambiguity_refs);
    }

    assert_eq!(
        observed_families, required_families,
        "provenance_records must cover all required lineage families"
    );

    let required_ambiguity_keys =
        required_string_array(&schema, "required_ambiguity_decision_keys");
    let decisions = artifact["ambiguity_decisions"]
        .as_array()
        .expect("ambiguity_decisions should be array");
    assert!(
        !decisions.is_empty(),
        "ambiguity_decisions should be non-empty"
    );

    let mut seen_decision_ids = BTreeSet::new();
    let mut decision_ids_by_record = BTreeMap::<String, BTreeSet<String>>::new();

    for (idx, decision) in decisions.iter().enumerate() {
        for key in &required_ambiguity_keys {
            assert!(
                decision.get(*key).is_some(),
                "ambiguity_decisions[{idx}] missing `{key}`"
            );
        }
        let decision_id = decision["decision_id"]
            .as_str()
            .expect("ambiguity decision_id should be string");
        assert!(
            seen_decision_ids.insert(decision_id.to_string()),
            "duplicate ambiguity decision_id detected: {decision_id}"
        );

        let record_id = decision["record_id"]
            .as_str()
            .expect("ambiguity record_id should be string");
        assert!(
            seen_record_ids.contains(record_id),
            "ambiguity decision {decision_id} points at unknown record {record_id}"
        );
        decision_ids_by_record
            .entry(record_id.to_string())
            .or_default()
            .insert(decision_id.to_string());

        let confidence = decision["confidence_rating"]
            .as_f64()
            .expect("ambiguity confidence should be numeric");
        assert!(
            confidence >= min_confidence && confidence <= max_confidence,
            "ambiguity decision {decision_id} confidence {confidence} outside [{min_confidence}, {max_confidence}]"
        );
    }

    for (record_id, refs) in &ambiguity_refs_by_record {
        for ref_id in refs {
            assert!(
                seen_decision_ids.contains(ref_id),
                "record {record_id} references unknown ambiguity decision {ref_id}"
            );
        }
    }

    for (record_id, decision_ids) in &decision_ids_by_record {
        let refs = ambiguity_refs_by_record
            .get(record_id)
            .cloned()
            .unwrap_or_default();
        for decision_id in decision_ids {
            assert!(
                refs.contains(decision_id),
                "decision {decision_id} for record {record_id} missing from ambiguity_ref_ids"
            );
        }
    }

    let required_audit_keys = required_string_array(&schema, "required_audit_query_keys");
    let required_audit_fields = required_string_array(&schema, "required_audit_fields")
        .into_iter()
        .collect::<BTreeSet<_>>();
    let queries = artifact["audit_query_index"]
        .as_array()
        .expect("audit_query_index should be array");
    assert!(!queries.is_empty(), "audit_query_index should be non-empty");

    let mut seen_query_ids = BTreeSet::new();
    for (idx, query) in queries.iter().enumerate() {
        for key in &required_audit_keys {
            assert!(
                query.get(*key).is_some(),
                "audit_query_index[{idx}] missing `{key}`"
            );
        }

        let query_id = query["query_id"]
            .as_str()
            .expect("query_id should be string");
        assert!(
            seen_query_ids.insert(query_id),
            "duplicate query_id detected: {query_id}"
        );

        let record_path = query["record_path"]
            .as_array()
            .expect("record_path should be array");
        assert!(
            !record_path.is_empty(),
            "query {query_id} record_path should be non-empty"
        );
        for (rid_idx, record_id) in record_path.iter().enumerate() {
            let record_id = record_id.as_str().unwrap_or_else(|| {
                panic!("query {query_id} record_path[{rid_idx}] should be string")
            });
            assert!(
                seen_record_ids.contains(record_id),
                "query {query_id} references unknown record_id {record_id}"
            );
        }

        let fields = query["expected_end_to_end_fields"]
            .as_array()
            .expect("expected_end_to_end_fields should be array")
            .iter()
            .map(|value| {
                value
                    .as_str()
                    .expect("expected_end_to_end_fields entries should be string")
            })
            .collect::<BTreeSet<_>>();
        assert_eq!(
            fields, required_audit_fields,
            "query {query_id} expected_end_to_end_fields should match schema.required_audit_fields"
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
        .expect("alien_uplift_contract_card.ev_score should be numeric");
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
        .expect("optimization_lever_policy.max_levers_per_change should be integer");
    assert_eq!(
        max_levers, 1,
        "optimization_lever_policy.max_levers_per_change must equal 1"
    );

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
        .expect("drop_in_parity_contract.legacy_feature_overlap_target should be string");
    assert_eq!(
        overlap_target, "100%",
        "legacy_feature_overlap_target must be 100%"
    );
    let capability_gaps = parity["intentional_capability_gaps"]
        .as_array()
        .expect("drop_in_parity_contract.intentional_capability_gaps should be array");
    assert!(
        capability_gaps.is_empty(),
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
            .expect("runtime states should be array")
            .is_empty(),
        "runtime states should be non-empty"
    );
    assert!(
        !runtime["actions"]
            .as_array()
            .expect("runtime actions should be array")
            .is_empty(),
        "runtime actions should be non-empty"
    );

    let safe_mode_budget = runtime["safe_mode_budget"]
        .as_object()
        .expect("safe_mode_budget should be object");
    for key in [
        "max_blocked_promotions_per_run",
        "max_unsigned_records_before_halt",
        "max_unresolved_ambiguities_before_halt",
    ] {
        let value = safe_mode_budget[key]
            .as_i64()
            .unwrap_or_else(|| panic!("safe_mode_budget.{key} should be integer"));
        assert!(value >= 0, "safe_mode_budget.{key} should be >= 0");
    }

    let required_trigger_keys = required_string_array(&schema, "required_runtime_trigger_keys");
    let trigger_thresholds = runtime["trigger_thresholds"]
        .as_array()
        .expect("trigger_thresholds should be array");
    assert!(
        !trigger_thresholds.is_empty(),
        "trigger_thresholds should be non-empty"
    );
    let mut trigger_ids = BTreeSet::new();
    for (idx, trigger) in trigger_thresholds.iter().enumerate() {
        for key in &required_trigger_keys {
            assert!(
                trigger.get(*key).is_some(),
                "trigger_thresholds[{idx}] missing `{key}`"
            );
        }
        let trigger_id = trigger["trigger_id"]
            .as_str()
            .expect("trigger_id should be string");
        assert!(
            trigger_ids.insert(trigger_id),
            "duplicate trigger_id detected: {trigger_id}"
        );
        let threshold = trigger["threshold"]
            .as_i64()
            .expect("trigger threshold should be integer");
        assert!(
            threshold >= 1,
            "trigger_thresholds[{idx}].threshold should be >= 1"
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

    let logging = artifact["structured_logging_evidence"]
        .as_array()
        .expect("structured_logging_evidence should be array");
    assert!(
        logging.len() >= 3,
        "structured_logging_evidence should include deterministic replay + forensics artifacts"
    );
    for (idx, path_text) in logging.iter().enumerate() {
        let path = path_text
            .as_str()
            .unwrap_or_else(|| panic!("structured_logging_evidence[{idx}] should be string"));
        assert_path(path, &format!("structured_logging_evidence[{idx}]"), &root);
    }
}
