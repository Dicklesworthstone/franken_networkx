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

fn load_jsonl(path: &Path) -> Vec<Value> {
    let raw = fs::read_to_string(path)
        .unwrap_or_else(|err| panic!("expected readable jsonl at {}: {err}", path.display()));
    raw.lines()
        .filter(|line| !line.trim().is_empty())
        .map(|line| {
            serde_json::from_str::<Value>(line).unwrap_or_else(|err| {
                panic!("expected valid json line at {}: {err}", path.display())
            })
        })
        .collect()
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

fn assert_path_exists(root: &Path, path: &str, ctx: &str) {
    assert!(
        !path.trim().is_empty(),
        "{ctx} should be non-empty path string"
    );
    let full = root.join(path);
    assert!(full.exists(), "{ctx} should exist: {}", full.display());
}

fn assert_forensics_links(schema: &Value, links: &Value, ctx: &str) {
    let object = links
        .as_object()
        .unwrap_or_else(|| panic!("{ctx} should be object"));
    for key in required_string_array(schema, "required_forensics_keys") {
        let value = object
            .get(key)
            .and_then(Value::as_str)
            .unwrap_or_else(|| panic!("{ctx}.{key} should be non-empty string"));
        assert!(
            !value.trim().is_empty(),
            "{ctx}.{key} should be non-empty string"
        );
    }
}

fn assert_gate_step_id(value: &Value, required_prefix: &str, ctx: &str) -> String {
    let gate_step_id = value
        .as_str()
        .unwrap_or_else(|| panic!("{ctx} should be non-empty string"));
    assert!(
        !gate_step_id.trim().is_empty(),
        "{ctx} should be non-empty string"
    );
    assert!(
        gate_step_id.starts_with(required_prefix),
        "{ctx} should start with `{required_prefix}`"
    );
    gate_step_id.to_owned()
}

fn fnv1a64(text: &str) -> String {
    let mut value: u64 = 0xCBF29CE484222325;
    for byte in text.as_bytes() {
        value ^= u64::from(*byte);
        value = value.wrapping_mul(0x100000001B3);
    }
    format!("{value:016x}")
}

fn expected_retention_policy_digest(policy_id: &str, min_retention_days: u64, storage_root: &str) -> String {
    let mut normalized = BTreeMap::<&str, Value>::new();
    normalized.insert("min_retention_days", Value::from(min_retention_days));
    normalized.insert("policy_id", Value::from(policy_id));
    normalized.insert("storage_root", Value::from(storage_root));
    let canonical = serde_json::to_string(&normalized)
        .expect("retention policy digest canonical serialization should succeed");
    format!("fnv1a64:{}", fnv1a64(&canonical))
}

fn assert_retention_policy(root: &Path, schema: &Value, policy: &Value, ctx: &str) {
    let object = policy
        .as_object()
        .unwrap_or_else(|| panic!("{ctx} should be object"));
    for key in required_string_array(schema, "required_retention_policy_keys") {
        assert!(
            object.contains_key(key),
            "{ctx} missing required key `{key}`"
        );
    }
    let policy_id = object
        .get("policy_id")
        .and_then(Value::as_str)
        .unwrap_or_else(|| panic!("{ctx}.policy_id should be non-empty string"));
    assert!(
        !policy_id.trim().is_empty(),
        "{ctx}.policy_id should be non-empty string"
    );
    let min_retention_days = object
        .get("min_retention_days")
        .and_then(Value::as_u64)
        .unwrap_or_else(|| panic!("{ctx}.min_retention_days should be integer >= 1"));
    assert!(
        min_retention_days >= 1,
        "{ctx}.min_retention_days should be >= 1"
    );
    let storage_root = object
        .get("storage_root")
        .and_then(Value::as_str)
        .unwrap_or_else(|| panic!("{ctx}.storage_root should be string"));
    assert_path_exists(root, storage_root, &format!("{ctx}.storage_root"));
    let policy_digest = object
        .get("policy_digest")
        .and_then(Value::as_str)
        .unwrap_or_else(|| panic!("{ctx}.policy_digest should be non-empty string"));
    assert!(
        !policy_digest.trim().is_empty(),
        "{ctx}.policy_digest should be non-empty string"
    );
    let expected_policy_digest =
        expected_retention_policy_digest(policy_id, min_retention_days, storage_root);
    assert_eq!(
        policy_digest, expected_policy_digest,
        "{ctx}.policy_digest should match deterministic digest over policy fields"
    );
}

fn assert_evidence_refs(root: &Path, schema: &Value, refs: &Value, ctx: &str) {
    let object = refs
        .as_object()
        .unwrap_or_else(|| panic!("{ctx} should be object"));
    for key in required_string_array(schema, "required_evidence_ref_keys") {
        assert!(
            object.contains_key(key),
            "{ctx} missing required key `{key}`"
        );
    }
    for path_key in [
        "parity_report",
        "parity_report_raptorq",
        "parity_report_decode_proof",
        "contract_table",
        "risk_note",
        "legacy_anchor_map",
    ] {
        let rel = object
            .get(path_key)
            .and_then(Value::as_str)
            .unwrap_or_else(|| panic!("{ctx}.{path_key} should be string"));
        assert_path_exists(root, rel, &format!("{ctx}.{path_key}"));
    }

    let profile = object["profile_first_artifacts"]
        .as_object()
        .unwrap_or_else(|| panic!("{ctx}.profile_first_artifacts should be object"));
    for profile_key in ["baseline", "hotspot", "delta"] {
        let rel = profile
            .get(profile_key)
            .and_then(Value::as_str)
            .unwrap_or_else(|| {
                panic!("{ctx}.profile_first_artifacts.{profile_key} should be string")
            });
        assert_path_exists(
            root,
            rel,
            &format!("{ctx}.profile_first_artifacts.{profile_key}"),
        );
    }

    let optimization = object["optimization_lever_policy"]
        .as_object()
        .unwrap_or_else(|| panic!("{ctx}.optimization_lever_policy should be object"));
    assert_eq!(
        optimization
            .get("rule")
            .and_then(Value::as_str)
            .unwrap_or_default(),
        "exactly_one_optimization_lever_per_change",
        "{ctx}.optimization_lever_policy.rule should match one-lever policy"
    );
    let optimization_evidence = optimization
        .get("evidence_path")
        .and_then(Value::as_str)
        .unwrap_or_else(|| {
            panic!("{ctx}.optimization_lever_policy.evidence_path should be string")
        });
    assert_path_exists(
        root,
        optimization_evidence,
        &format!("{ctx}.optimization_lever_policy.evidence_path"),
    );

    let isomorphism = object["isomorphism_proof_artifacts"]
        .as_array()
        .unwrap_or_else(|| panic!("{ctx}.isomorphism_proof_artifacts should be array"));
    assert!(
        !isomorphism.is_empty(),
        "{ctx}.isomorphism_proof_artifacts should be non-empty"
    );
    for (idx, proof) in isomorphism.iter().enumerate() {
        let rel = proof
            .as_str()
            .unwrap_or_else(|| panic!("{ctx}.isomorphism_proof_artifacts[{idx}] should be string"));
        assert_path_exists(
            root,
            rel,
            &format!("{ctx}.isomorphism_proof_artifacts[{idx}]"),
        );
    }

    let durability_refs = object["durability_evidence"]
        .as_array()
        .unwrap_or_else(|| panic!("{ctx}.durability_evidence should be array"));
    assert!(
        !durability_refs.is_empty(),
        "{ctx}.durability_evidence should be non-empty"
    );
    for (idx, entry) in durability_refs.iter().enumerate() {
        let rel = entry
            .as_str()
            .unwrap_or_else(|| panic!("{ctx}.durability_evidence[{idx}] should be string"));
        assert_path_exists(root, rel, &format!("{ctx}.durability_evidence[{idx}]"));
    }

    let baseline_comparator = object["baseline_comparator"]
        .as_str()
        .unwrap_or_else(|| panic!("{ctx}.baseline_comparator should be string"));
    assert!(
        !baseline_comparator.trim().is_empty(),
        "{ctx}.baseline_comparator should be non-empty"
    );
}

#[test]
fn e2e_script_pack_artifacts_are_complete_and_deterministic() {
    let root = repo_root();
    let schema = load_json(&root.join("artifacts/e2e/schema/v1/e2e_script_pack_schema_v1.json"));
    let report =
        load_json(&root.join("artifacts/e2e/latest/e2e_script_pack_determinism_report_v1.json"));
    let events = load_jsonl(&root.join("artifacts/e2e/latest/e2e_script_pack_events_v1.jsonl"));
    let replay_report =
        load_json(&root.join("artifacts/e2e/latest/e2e_script_pack_replay_report_v1.json"));
    let bundle_index =
        load_json(&root.join("artifacts/e2e/latest/e2e_script_pack_bundle_index_v1.json"));

    let required_report_keys = required_string_array(&schema, "required_report_keys");
    for key in required_report_keys {
        assert!(
            report.get(key).is_some(),
            "determinism report missing required key `{key}`"
        );
    }
    assert_eq!(
        report["status"]
            .as_str()
            .expect("report status should be string"),
        "pass"
    );
    let profile_first = report["profile_first_artifacts"]
        .as_object()
        .expect("report.profile_first_artifacts should be object");
    for key in ["baseline", "hotspot", "delta"] {
        let rel = profile_first
            .get(key)
            .and_then(Value::as_str)
            .unwrap_or_else(|| panic!("report.profile_first_artifacts.{key} should be string"));
        assert_path_exists(
            root.as_path(),
            rel,
            &format!("report.profile_first_artifacts.{key}"),
        );
    }
    let optimization_policy = report["optimization_lever_policy"]
        .as_object()
        .expect("report.optimization_lever_policy should be object");
    assert_eq!(
        optimization_policy
            .get("rule")
            .and_then(Value::as_str)
            .unwrap_or_default(),
        "exactly_one_optimization_lever_per_change",
        "report.optimization_lever_policy.rule should enforce one-lever policy"
    );
    let optimization_evidence = optimization_policy
        .get("evidence_path")
        .and_then(Value::as_str)
        .expect("report.optimization_lever_policy.evidence_path should be string");
    assert_path_exists(
        root.as_path(),
        optimization_evidence,
        "report.optimization_lever_policy.evidence_path",
    );
    let alien_uplift = report["alien_uplift_contract_card"]
        .as_object()
        .expect("report.alien_uplift_contract_card should be object");
    let ev_score = alien_uplift
        .get("ev_score")
        .and_then(Value::as_f64)
        .expect("report.alien_uplift_contract_card.ev_score should be f64");
    assert!(
        ev_score >= 2.0,
        "report.alien_uplift_contract_card.ev_score should be >= 2.0"
    );
    let baseline_comparator = alien_uplift
        .get("baseline_comparator")
        .and_then(Value::as_str)
        .expect("report.alien_uplift_contract_card.baseline_comparator should be string");
    assert!(
        !baseline_comparator.trim().is_empty(),
        "report.alien_uplift_contract_card.baseline_comparator should be non-empty"
    );
    let decision_contract = report["decision_theoretic_runtime_contract"]
        .as_object()
        .expect("report.decision_theoretic_runtime_contract should be object");
    for key in [
        "states",
        "actions",
        "loss_model",
        "loss_budget",
        "safe_mode_fallback",
    ] {
        assert!(
            decision_contract.contains_key(key),
            "report.decision_theoretic_runtime_contract missing key `{key}`"
        );
    }
    assert!(
        decision_contract["safe_mode_fallback"]["trigger_thresholds"]
            .as_object()
            .map(|rows| !rows.is_empty())
            .unwrap_or(false),
        "report.decision_theoretic_runtime_contract.safe_mode_fallback.trigger_thresholds should be non-empty object"
    );
    let report_isomorphism = report["isomorphism_proof_artifacts"]
        .as_array()
        .expect("report.isomorphism_proof_artifacts should be array");
    assert!(
        !report_isomorphism.is_empty(),
        "report.isomorphism_proof_artifacts should be non-empty"
    );
    for (idx, entry) in report_isomorphism.iter().enumerate() {
        let rel = entry.as_str().unwrap_or_else(|| {
            panic!("report.isomorphism_proof_artifacts[{idx}] should be string")
        });
        assert_path_exists(
            root.as_path(),
            rel,
            &format!("report.isomorphism_proof_artifacts[{idx}]"),
        );
    }
    let report_logs = report["structured_logging_evidence"]
        .as_array()
        .expect("report.structured_logging_evidence should be array");
    assert!(
        !report_logs.is_empty(),
        "report.structured_logging_evidence should be non-empty"
    );
    for (idx, entry) in report_logs.iter().enumerate() {
        let rel = entry.as_str().unwrap_or_else(|| {
            panic!("report.structured_logging_evidence[{idx}] should be string")
        });
        assert_path_exists(
            root.as_path(),
            rel,
            &format!("report.structured_logging_evidence[{idx}]"),
        );
    }
    assert_eq!(
        replay_report["status"]
            .as_str()
            .expect("replay report status should be string"),
        "passed"
    );
    assert!(
        replay_report["forensics_match"]
            .as_bool()
            .expect("replay report forensics_match should be bool")
    );
    assert_eq!(
        replay_report["diagnostics"]
            .as_array()
            .expect("replay report diagnostics should be array")
            .len(),
        0,
        "replay diagnostics should be empty on pass"
    );
    let replay_failure_envelope = replay_report["failure_envelope_path"]
        .as_str()
        .expect("replay report failure_envelope_path should be string");
    assert_path_exists(
        root.as_path(),
        replay_failure_envelope,
        "replay report failure_envelope_path",
    );
    assert_evidence_refs(
        root.as_path(),
        &schema,
        &replay_report["evidence_refs"],
        "replay_report.evidence_refs",
    );
    let gate_report_path = root.join("artifacts/e2e/latest/e2e_script_pack_gate_report_v1.json");
    if gate_report_path.exists() {
        let gate_report = load_json(&gate_report_path);
        if let Some(bundle_index_path) = gate_report["bundle_index_path"].as_str() {
            assert_eq!(
                root.join(bundle_index_path),
                root.join("artifacts/e2e/latest/e2e_script_pack_bundle_index_v1.json")
            );
        }
    }
    for key in required_string_array(&schema, "required_bundle_index_keys") {
        assert!(
            bundle_index.get(key).is_some(),
            "bundle index missing required key `{key}`"
        );
    }
    let bundle_rows = bundle_index["rows"]
        .as_array()
        .expect("bundle index rows should be array");

    let required_scenarios = required_string_array(&schema, "required_scenarios")
        .iter()
        .map(|value| (*value).to_owned())
        .collect::<BTreeSet<_>>();
    let required_packet_ids = required_string_array(&schema, "required_packet_ids")
        .iter()
        .map(|value| (*value).to_owned())
        .collect::<BTreeSet<_>>();
    let required_pass_labels = required_string_array(&schema, "required_pass_labels")
        .iter()
        .map(|value| (*value).to_owned())
        .collect::<BTreeSet<_>>();
    let required_gate_step_prefix = schema["required_gate_step_prefix"]
        .as_str()
        .expect("required_gate_step_prefix should be string");

    let report_required_scenarios = report["required_scenarios"]
        .as_array()
        .expect("report.required_scenarios should be array")
        .iter()
        .map(|value| {
            value
                .as_str()
                .expect("report required scenario should be string")
                .to_owned()
        })
        .collect::<BTreeSet<_>>();
    assert_eq!(report_required_scenarios, required_scenarios);
    let report_required_packet_ids = report["required_packet_ids"]
        .as_array()
        .expect("report.required_packet_ids should be array")
        .iter()
        .map(|value| {
            value
                .as_str()
                .expect("report required packet id should be string")
                .to_owned()
        })
        .collect::<BTreeSet<_>>();
    assert_eq!(report_required_packet_ids, required_packet_ids);
    assert_gate_step_id(
        &report["gate_step_id"],
        required_gate_step_prefix,
        "report.gate_step_id",
    );
    let report_forensics_index_path = report["forensics_index_path"]
        .as_str()
        .expect("report.forensics_index_path should be string");
    assert_path_exists(
        root.as_path(),
        report_forensics_index_path,
        "report.forensics_index_path",
    );
    assert_retention_policy(
        root.as_path(),
        &schema,
        &report["retention_policy"],
        "report.retention_policy",
    );
    let packet_coverage = report["packet_coverage"]
        .as_object()
        .expect("report.packet_coverage should be object");
    let coverage_required_packet_ids = packet_coverage
        .get("required_packet_ids")
        .and_then(Value::as_array)
        .expect("report.packet_coverage.required_packet_ids should be array")
        .iter()
        .map(|value| {
            value
                .as_str()
                .expect("report.packet_coverage.required_packet_ids entries should be string")
                .to_owned()
        })
        .collect::<BTreeSet<_>>();
    assert_eq!(coverage_required_packet_ids, required_packet_ids);
    let coverage_observed_packet_ids = packet_coverage
        .get("observed_packet_ids")
        .and_then(Value::as_array)
        .expect("report.packet_coverage.observed_packet_ids should be array")
        .iter()
        .map(|value| {
            value
                .as_str()
                .expect("report.packet_coverage.observed_packet_ids entries should be string")
                .to_owned()
        })
        .collect::<BTreeSet<_>>();
    assert_eq!(coverage_observed_packet_ids, required_packet_ids);
    assert!(
        packet_coverage
            .get("missing_packet_ids")
            .and_then(Value::as_array)
            .expect("report.packet_coverage.missing_packet_ids should be array")
            .is_empty(),
        "report.packet_coverage.missing_packet_ids should be empty"
    );
    assert_eq!(
        packet_coverage.get("coverage_ok").and_then(Value::as_bool),
        Some(true),
        "report.packet_coverage.coverage_ok should be true"
    );

    let report_pass_labels = report["pass_labels"]
        .as_array()
        .expect("report.pass_labels should be array")
        .iter()
        .map(|value| {
            value
                .as_str()
                .expect("report pass label should be string")
                .to_owned()
        })
        .collect::<BTreeSet<_>>();
    assert_eq!(report_pass_labels, required_pass_labels);
    let bundle_gate_step_id = assert_gate_step_id(
        &bundle_index["gate_step_id"],
        required_gate_step_prefix,
        "bundle_index.gate_step_id",
    );
    assert_eq!(
        bundle_index["scenario_count"].as_u64(),
        Some(required_scenarios.len() as u64),
        "bundle index scenario_count should match required_scenarios"
    );
    let bundle_forensics_index_path = bundle_index["forensics_index_path"]
        .as_str()
        .expect("bundle_index.forensics_index_path should be string");
    assert_path_exists(
        root.as_path(),
        bundle_forensics_index_path,
        "bundle_index.forensics_index_path",
    );
    assert_eq!(
        bundle_forensics_index_path, "artifacts/e2e/latest/e2e_script_pack_bundle_index_v1.json",
        "bundle_index.forensics_index_path should point at canonical bundle index artifact"
    );
    assert_eq!(
        bundle_forensics_index_path, report_forensics_index_path,
        "bundle_index.forensics_index_path should match determinism report"
    );
    assert_retention_policy(
        root.as_path(),
        &schema,
        &bundle_index["retention_policy"],
        "bundle_index.retention_policy",
    );
    let failure_index = bundle_index["failure_index"]
        .as_array()
        .expect("bundle index failure_index should be array");
    assert_eq!(
        bundle_index["failure_count"].as_u64(),
        Some(failure_index.len() as u64),
        "bundle index failure_count should equal failure_index length"
    );
    let bundle_profile = bundle_index["profile_first_artifacts"]
        .as_object()
        .expect("bundle_index.profile_first_artifacts should be object");
    for key in ["baseline", "hotspot", "delta"] {
        let rel = bundle_profile
            .get(key)
            .and_then(Value::as_str)
            .unwrap_or_else(|| {
                panic!("bundle_index.profile_first_artifacts.{key} should be string")
            });
        assert_path_exists(
            root.as_path(),
            rel,
            &format!("bundle_index.profile_first_artifacts.{key}"),
        );
    }
    let bundle_optimization = bundle_index["optimization_lever_policy"]
        .as_object()
        .expect("bundle_index.optimization_lever_policy should be object");
    assert_eq!(
        bundle_optimization
            .get("rule")
            .and_then(Value::as_str)
            .unwrap_or_default(),
        "exactly_one_optimization_lever_per_change",
        "bundle_index.optimization_lever_policy.rule should enforce one-lever policy"
    );
    let bundle_optimization_evidence = bundle_optimization
        .get("evidence_path")
        .and_then(Value::as_str)
        .expect("bundle_index.optimization_lever_policy.evidence_path should be string");
    assert_path_exists(
        root.as_path(),
        bundle_optimization_evidence,
        "bundle_index.optimization_lever_policy.evidence_path",
    );
    let bundle_alien = bundle_index["alien_uplift_contract_card"]
        .as_object()
        .expect("bundle_index.alien_uplift_contract_card should be object");
    assert!(
        bundle_alien["ev_score"]
            .as_f64()
            .expect("bundle_index.alien_uplift_contract_card.ev_score should be f64")
            >= 2.0,
        "bundle_index.alien_uplift_contract_card.ev_score should be >= 2.0"
    );
    for key in required_string_array(&schema, "required_bundle_index_failure_keys") {
        for (idx, failure_row) in failure_index.iter().enumerate() {
            assert!(
                failure_row.get(key).is_some(),
                "bundle_index.failure_index[{idx}] missing required key `{key}`"
            );
        }
    }
    let bundle_decision = bundle_index["decision_theoretic_runtime_contract"]
        .as_object()
        .expect("bundle_index.decision_theoretic_runtime_contract should be object");
    for key in [
        "states",
        "actions",
        "loss_model",
        "loss_budget",
        "safe_mode_fallback",
    ] {
        assert!(
            bundle_decision.get(key).is_some(),
            "bundle_index.decision_theoretic_runtime_contract missing key `{key}`"
        );
    }
    let bundle_isomorphism = bundle_index["isomorphism_proof_artifacts"]
        .as_array()
        .expect("bundle_index.isomorphism_proof_artifacts should be array");
    assert!(
        !bundle_isomorphism.is_empty(),
        "bundle_index.isomorphism_proof_artifacts should be non-empty"
    );
    for (idx, proof_ref) in bundle_isomorphism.iter().enumerate() {
        let rel = proof_ref.as_str().unwrap_or_else(|| {
            panic!("bundle_index.isomorphism_proof_artifacts[{idx}] should be string")
        });
        assert_path_exists(
            root.as_path(),
            rel,
            &format!("bundle_index.isomorphism_proof_artifacts[{idx}]"),
        );
    }
    let bundle_logs = bundle_index["structured_logging_evidence"]
        .as_array()
        .expect("bundle_index.structured_logging_evidence should be array");
    assert!(
        !bundle_logs.is_empty(),
        "bundle_index.structured_logging_evidence should be non-empty"
    );
    for (idx, log_ref) in bundle_logs.iter().enumerate() {
        let rel = log_ref.as_str().unwrap_or_else(|| {
            panic!("bundle_index.structured_logging_evidence[{idx}] should be string")
        });
        assert_path_exists(
            root.as_path(),
            rel,
            &format!("bundle_index.structured_logging_evidence[{idx}]"),
        );
    }

    let required_event_keys = schema["required_event_keys"]
        .as_array()
        .expect("required_event_keys should be array")
        .iter()
        .map(|value| value.as_str().expect("event key should be string"))
        .collect::<Vec<_>>();
    assert!(
        !events.is_empty(),
        "events jsonl should contain at least one event row"
    );

    let mut seen_pairs = BTreeSet::new();
    let mut seen_packet_ids = BTreeSet::new();
    let mut bundle_ids_by_scenario: std::collections::BTreeMap<String, BTreeSet<String>> =
        std::collections::BTreeMap::new();
    let mut fingerprints_by_scenario: std::collections::BTreeMap<String, BTreeSet<String>> =
        std::collections::BTreeMap::new();

    for event in &events {
        for key in &required_event_keys {
            assert!(
                event.get(*key).is_some(),
                "event row missing required key `{key}`"
            );
        }
        assert_eq!(
            event["status"]
                .as_str()
                .expect("event status should be string"),
            "passed"
        );
        let start = event["start_unix_ms"]
            .as_u64()
            .expect("event start_unix_ms should be integer");
        let end = event["end_unix_ms"]
            .as_u64()
            .expect("event end_unix_ms should be integer");
        let duration = event["duration_ms"]
            .as_u64()
            .expect("event duration_ms should be integer");
        assert!(start <= end, "event start_unix_ms should be <= end_unix_ms");
        assert_eq!(
            duration,
            end - start,
            "event duration_ms should equal end-start"
        );

        let scenario = event["scenario_id"]
            .as_str()
            .expect("scenario_id should be string");
        let packet_id = event["packet_id"]
            .as_str()
            .expect("packet_id should be string");
        let pass_label = event["pass_label"]
            .as_str()
            .expect("pass_label should be string");
        assert!(
            required_scenarios.contains(scenario),
            "unexpected scenario_id {scenario}"
        );
        assert!(
            required_pass_labels.contains(pass_label),
            "unexpected pass_label {pass_label}"
        );
        assert!(
            seen_pairs.insert((scenario.to_owned(), pass_label.to_owned())),
            "duplicate event for scenario/pass pair ({scenario}, {pass_label})"
        );
        seen_packet_ids.insert(packet_id.to_owned());

        let bundle_id = event["bundle_id"]
            .as_str()
            .expect("bundle_id should be string");
        let fingerprint = event["stable_fingerprint"]
            .as_str()
            .expect("stable_fingerprint should be string");
        let event_replay_command = event["replay_command"]
            .as_str()
            .expect("event replay_command should be string");
        assert!(
            !event_replay_command.trim().is_empty(),
            "event replay_command should be non-empty"
        );
        assert!(
            event_replay_command.starts_with("rch exec --"),
            "event replay_command should use rch offload"
        );
        let event_gate_step_id = assert_gate_step_id(
            &event["gate_step_id"],
            required_gate_step_prefix,
            &format!("event[{scenario}/{pass_label}].gate_step_id"),
        );
        assert_eq!(
            event_gate_step_id, bundle_gate_step_id,
            "event gate_step_id should match bundle_index gate_step_id"
        );
        let event_forensics_index_path = event["forensics_index_path"]
            .as_str()
            .expect("event forensics_index_path should be string");
        assert_eq!(
            event_forensics_index_path, bundle_forensics_index_path,
            "event forensics_index_path should match bundle index path"
        );
        assert_path_exists(
            root.as_path(),
            event_forensics_index_path,
            &format!("event[{scenario}/{pass_label}].forensics_index_path"),
        );
        assert_retention_policy(
            root.as_path(),
            &schema,
            &event["retention_policy"],
            &format!("event[{scenario}/{pass_label}].retention_policy"),
        );
        assert_forensics_links(
            &schema,
            &event["forensics_links"],
            &format!("event[{scenario}/{pass_label}].forensics_links"),
        );
        assert_evidence_refs(
            root.as_path(),
            &schema,
            &event["evidence_refs"],
            &format!("event[{scenario}/{pass_label}].evidence_refs"),
        );
        let event_policy_digest = event["retention_policy"]["policy_digest"]
            .as_str()
            .expect("event retention_policy.policy_digest should be string");
        let deterministic_replay = event["deterministic_replay_metadata"]
            .as_object()
            .expect("event deterministic_replay_metadata should be object");
        for key in required_string_array(&schema, "required_deterministic_replay_metadata_keys") {
            assert!(
                deterministic_replay.get(key).is_some(),
                "event deterministic_replay_metadata missing key `{key}`"
            );
        }
        assert_eq!(
            deterministic_replay.get("run_id").and_then(Value::as_str),
            event.get("run_id").and_then(Value::as_str)
        );
        assert_eq!(
            deterministic_replay
                .get("deterministic_seed")
                .and_then(Value::as_u64),
            event.get("deterministic_seed").and_then(Value::as_u64)
        );
        assert_eq!(
            deterministic_replay
                .get("bundle_id")
                .and_then(Value::as_str),
            Some(bundle_id)
        );
        assert_eq!(
            deterministic_replay
                .get("stable_fingerprint")
                .and_then(Value::as_str),
            Some(fingerprint)
        );
        assert_eq!(
            deterministic_replay
                .get("replay_command")
                .and_then(Value::as_str),
            Some(event_replay_command)
        );
        assert_eq!(
            deterministic_replay.get("scenario_id").and_then(Value::as_str),
            Some(scenario),
            "deterministic_replay_metadata.scenario_id should match event"
        );
        assert_eq!(
            deterministic_replay.get("packet_id").and_then(Value::as_str),
            Some(packet_id),
            "deterministic_replay_metadata.packet_id should match event"
        );
        assert_eq!(
            deterministic_replay.get("fixture_id").and_then(Value::as_str),
            event.get("fixture_id").and_then(Value::as_str),
            "deterministic_replay_metadata.fixture_id should match event"
        );
        assert_eq!(
            deterministic_replay.get("mode").and_then(Value::as_str),
            event.get("mode").and_then(Value::as_str),
            "deterministic_replay_metadata.mode should match event"
        );
        assert_eq!(
            deterministic_replay.get("reason_code"),
            event.get("reason_code"),
            "deterministic_replay_metadata.reason_code should match event"
        );
        assert_eq!(
            deterministic_replay
                .get("policy_digest")
                .and_then(Value::as_str),
            Some(event_policy_digest),
            "deterministic_replay_metadata.policy_digest should match retention policy digest"
        );
        assert_eq!(
            deterministic_replay.get("packet_evidence_refs"),
            event.get("evidence_refs"),
            "deterministic_replay_metadata.packet_evidence_refs should match event evidence_refs"
        );
        bundle_ids_by_scenario
            .entry(scenario.to_owned())
            .or_default()
            .insert(bundle_id.to_owned());
        fingerprints_by_scenario
            .entry(scenario.to_owned())
            .or_default()
            .insert(fingerprint.to_owned());

        let failure_envelope_rel = event["failure_envelope_path"]
            .as_str()
            .expect("event failure_envelope_path should be string");
        assert_path_exists(
            root.as_path(),
            failure_envelope_rel,
            &format!("event[{scenario}/{pass_label}].failure_envelope_path"),
        );
        let failure_envelope = load_json(&root.join(failure_envelope_rel));
        for key in required_string_array(&schema, "required_failure_envelope_keys") {
            assert!(
                failure_envelope.get(key).is_some(),
                "failure envelope missing required key `{key}`"
            );
        }
        assert_eq!(
            failure_envelope["scenario_id"].as_str(),
            Some(scenario),
            "failure envelope scenario_id should match event"
        );
        assert_eq!(
            failure_envelope["pass_label"].as_str(),
            Some(pass_label),
            "failure envelope pass_label should match event"
        );
        assert_eq!(
            failure_envelope["packet_id"].as_str(),
            Some(packet_id),
            "failure envelope packet_id should match event"
        );
        let envelope_gate_step_id = assert_gate_step_id(
            &failure_envelope["gate_step_id"],
            required_gate_step_prefix,
            &format!("failure_envelope[{scenario}/{pass_label}].gate_step_id"),
        );
        assert_eq!(
            envelope_gate_step_id, event_gate_step_id,
            "failure envelope gate_step_id should match event"
        );
        assert_eq!(
            failure_envelope["bundle_id"].as_str(),
            Some(bundle_id),
            "failure envelope bundle_id should match event"
        );
        assert_eq!(
            failure_envelope["stable_fingerprint"].as_str(),
            Some(fingerprint),
            "failure envelope stable_fingerprint should match event"
        );
        assert_eq!(
            failure_envelope["replay_command"].as_str(),
            Some(event_replay_command),
            "failure envelope replay_command should match event replay_command"
        );
        assert_eq!(
            failure_envelope["policy_digest"].as_str(),
            Some(event_policy_digest),
            "failure envelope policy_digest should match event retention policy digest"
        );
        assert_eq!(
            failure_envelope["deterministic_replay_metadata"],
            event["deterministic_replay_metadata"],
            "failure envelope deterministic_replay_metadata should match event"
        );
        let envelope_status = failure_envelope["status"]
            .as_str()
            .expect("failure envelope status should be string");
        assert!(
            matches!(envelope_status, "passed" | "failed"),
            "failure envelope status should be passed or failed"
        );
        if envelope_status == "passed" {
            assert!(
                failure_envelope["reason_code"].is_null(),
                "failure envelope reason_code should be null on pass"
            );
        } else {
            assert!(
                failure_envelope["reason_code"]
                    .as_str()
                    .map(|value| !value.trim().is_empty())
                    .unwrap_or(false),
                "failure envelope reason_code should be non-empty on failure"
            );
        }
        assert_forensics_links(
            &schema,
            &failure_envelope["forensics_links"],
            &format!("failure_envelope[{scenario}/{pass_label}].forensics_links"),
        );
        let failure_forensics_index_path = failure_envelope["forensics_index_path"]
            .as_str()
            .expect("failure envelope forensics_index_path should be string");
        assert_eq!(
            failure_forensics_index_path, event_forensics_index_path,
            "failure envelope forensics_index_path should match event"
        );
        assert_path_exists(
            root.as_path(),
            failure_forensics_index_path,
            &format!("failure_envelope[{scenario}/{pass_label}].forensics_index_path"),
        );
        let replay_bundle_manifest_path = failure_envelope["replay_bundle_manifest_path"]
            .as_str()
            .expect("failure envelope replay_bundle_manifest_path should be string");
        assert_path_exists(
            root.as_path(),
            replay_bundle_manifest_path,
            &format!("failure_envelope[{scenario}/{pass_label}].replay_bundle_manifest_path"),
        );
        assert_eq!(
            replay_bundle_manifest_path,
            event["bundle_manifest_path"]
                .as_str()
                .expect("event bundle_manifest_path should be string"),
            "failure envelope replay_bundle_manifest_path should match event bundle_manifest_path"
        );
        assert_retention_policy(
            root.as_path(),
            &schema,
            &failure_envelope["retention_policy"],
            &format!("failure_envelope[{scenario}/{pass_label}].retention_policy"),
        );
        assert_eq!(
            failure_envelope["retention_policy"], event["retention_policy"],
            "failure envelope retention_policy should match event"
        );
        assert_evidence_refs(
            root.as_path(),
            &schema,
            &failure_envelope["evidence_refs"],
            &format!("failure_envelope[{scenario}/{pass_label}].evidence_refs"),
        );

        let manifest_rel = event["bundle_manifest_path"]
            .as_str()
            .expect("bundle_manifest_path should be string");
        let manifest_path = root.join(manifest_rel);
        assert!(
            manifest_path.exists(),
            "bundle manifest path missing: {}",
            manifest_path.display()
        );
        let manifest = load_json(&manifest_path);
        let required_manifest_keys = schema["required_bundle_manifest_keys"]
            .as_array()
            .expect("required_bundle_manifest_keys should be array")
            .iter()
            .map(|value| value.as_str().expect("manifest key should be string"))
            .collect::<Vec<_>>();
        for key in required_manifest_keys {
            assert!(
                manifest.get(key).is_some(),
                "bundle manifest missing required key `{key}`"
            );
        }
        assert_eq!(manifest["bundle_id"].as_str(), Some(bundle_id));
        assert_eq!(manifest["stable_fingerprint"].as_str(), Some(fingerprint));
        let manifest_gate_step_id = assert_gate_step_id(
            &manifest["gate_step_id"],
            required_gate_step_prefix,
            &format!("manifest[{scenario}/{pass_label}].gate_step_id"),
        );
        assert_eq!(
            manifest_gate_step_id, event_gate_step_id,
            "manifest gate_step_id should match event"
        );
        let replay_command = manifest["replay_command"]
            .as_str()
            .expect("replay_command should be string");
        assert!(
            !replay_command.trim().is_empty(),
            "replay_command should be non-empty"
        );
        let execution = manifest["execution_metadata"]
            .as_object()
            .expect("execution_metadata should be object");
        for key in schema["required_execution_metadata_keys"]
            .as_array()
            .expect("required_execution_metadata_keys should be array")
            .iter()
            .map(|value| value.as_str().expect("execution key should be string"))
        {
            assert!(
                execution.get(key).is_some(),
                "execution_metadata missing key `{key}`"
            );
        }
        assert_forensics_links(
            &schema,
            &manifest["forensics_links"],
            &format!("manifest[{scenario}/{pass_label}].forensics_links"),
        );
        assert_eq!(
            manifest["forensics_links"]
                .as_object()
                .expect("manifest forensics links should be object")
                .get("forensics_bundle_replay_ref")
                .and_then(Value::as_str),
            Some(replay_command),
            "forensics replay reference should match replay_command"
        );
        assert_eq!(
            replay_command, event_replay_command,
            "manifest replay_command should match event replay_command"
        );
        let manifest_forensics_index_path = manifest["forensics_index_path"]
            .as_str()
            .expect("manifest forensics_index_path should be string");
        assert_eq!(
            manifest_forensics_index_path, event_forensics_index_path,
            "manifest forensics_index_path should match event"
        );
        assert_path_exists(
            root.as_path(),
            manifest_forensics_index_path,
            &format!("manifest[{scenario}/{pass_label}].forensics_index_path"),
        );
        assert_retention_policy(
            root.as_path(),
            &schema,
            &manifest["retention_policy"],
            &format!("manifest[{scenario}/{pass_label}].retention_policy"),
        );
        assert_eq!(
            manifest["retention_policy"], event["retention_policy"],
            "manifest retention_policy should match event"
        );
        assert_eq!(
            execution.get("gate_step_id").and_then(Value::as_str),
            Some(event_gate_step_id.as_str()),
            "execution_metadata.gate_step_id should match event gate_step_id"
        );
        let manifest_failure_envelope = manifest["failure_envelope_path"]
            .as_str()
            .expect("manifest failure_envelope_path should be string");
        assert_eq!(
            manifest_failure_envelope, failure_envelope_rel,
            "manifest failure_envelope_path should match event failure_envelope_path"
        );
        assert_evidence_refs(
            root.as_path(),
            &schema,
            &manifest["evidence_refs"],
            &format!("manifest[{scenario}/{pass_label}].evidence_refs"),
        );

        let artifact_refs = manifest["artifact_refs"]
            .as_array()
            .expect("artifact_refs should be array");
        assert!(
            !artifact_refs.is_empty(),
            "artifact_refs should not be empty"
        );
        for artifact_ref in artifact_refs {
            let rel = artifact_ref
                .as_str()
                .expect("artifact_ref entries should be strings");
            let full = root.join(rel);
            assert!(
                full.exists(),
                "artifact reference missing: {}",
                full.display()
            );
        }

        if scenario == "adversarial_soak" {
            assert_eq!(
                event["soak_profile"].as_str(),
                Some("long_tail_stability"),
                "adversarial_soak should set soak_profile"
            );
            assert_eq!(
                event["soak_threat_class"].as_str(),
                Some("algorithmic_denial"),
                "adversarial_soak should set soak_threat_class"
            );
            let soak_cycle_count = event["soak_cycle_count"]
                .as_u64()
                .expect("soak_cycle_count should be integer");
            let soak_realized_cycle_count = event["soak_realized_cycle_count"]
                .as_u64()
                .expect("soak_realized_cycle_count should be integer");
            assert!(
                soak_cycle_count >= 1,
                "soak_cycle_count should be >= 1 for adversarial_soak"
            );
            assert_eq!(
                soak_realized_cycle_count, soak_cycle_count,
                "adversarial_soak should execute all configured cycles"
            );
            let checkpoint_interval = event["soak_checkpoint_interval_ms"]
                .as_u64()
                .expect("soak_checkpoint_interval_ms should be integer");
            assert!(
                checkpoint_interval >= 1,
                "soak_checkpoint_interval_ms should be >= 1"
            );

            let checkpoint_rel = event["soak_checkpoint_artifact_path"]
                .as_str()
                .expect("soak_checkpoint_artifact_path should be string");
            let checkpoint_path = root.join(checkpoint_rel);
            assert!(
                checkpoint_path.exists(),
                "soak checkpoint artifact missing: {}",
                checkpoint_path.display()
            );
            let checkpoint = load_json(&checkpoint_path);
            assert_eq!(
                checkpoint["status"].as_str(),
                Some("passed"),
                "soak checkpoint report should pass"
            );
            assert_eq!(
                checkpoint["target_cycle_count"].as_u64(),
                Some(soak_cycle_count),
                "checkpoint target_cycle_count should match event"
            );
            assert_eq!(
                checkpoint["realized_cycle_count"].as_u64(),
                Some(soak_realized_cycle_count),
                "checkpoint realized_cycle_count should match event"
            );
            let deterministic_checkpoints = checkpoint["deterministic_checkpoints"]
                .as_array()
                .expect("deterministic_checkpoints should be array");
            assert_eq!(
                deterministic_checkpoints.len(),
                soak_cycle_count as usize,
                "deterministic checkpoint count should match cycle count"
            );
            let health_samples = checkpoint["health_samples"]
                .as_array()
                .expect("health_samples should be array");
            assert_eq!(
                health_samples.len(),
                soak_cycle_count as usize,
                "health sample count should match cycle count"
            );

            let triage_rel = event["soak_triage_summary_path"]
                .as_str()
                .expect("soak_triage_summary_path should be string");
            let triage_path = root.join(triage_rel);
            assert!(
                triage_path.exists(),
                "soak triage summary missing: {}",
                triage_path.display()
            );
            let triage = load_json(&triage_path);
            assert_eq!(
                triage["status"].as_str(),
                Some("passed"),
                "soak triage summary should pass"
            );
            assert_eq!(
                triage["decode_ready_replay_bundle"].as_bool(),
                Some(true),
                "soak triage summary should confirm decode-ready replay bundle"
            );
            assert_eq!(
                triage["replay_manifest_path"].as_str(),
                Some(manifest_rel),
                "soak triage summary should point to current manifest"
            );

            let soak_telemetry = manifest["soak_telemetry"]
                .as_object()
                .expect("adversarial_soak manifest should include soak_telemetry");
            assert_eq!(
                soak_telemetry.get("soak_profile").and_then(Value::as_str),
                Some("long_tail_stability")
            );
            assert_eq!(
                soak_telemetry
                    .get("soak_threat_class")
                    .and_then(Value::as_str),
                Some("algorithmic_denial")
            );
            assert_eq!(
                soak_telemetry
                    .get("target_cycle_count")
                    .and_then(Value::as_u64),
                Some(soak_cycle_count)
            );
            assert_eq!(
                soak_telemetry
                    .get("realized_cycle_count")
                    .and_then(Value::as_u64),
                Some(soak_realized_cycle_count)
            );
            assert_eq!(
                soak_telemetry
                    .get("checkpoint_artifact_path")
                    .and_then(Value::as_str),
                Some(checkpoint_rel)
            );
            assert_eq!(
                soak_telemetry
                    .get("triage_summary_path")
                    .and_then(Value::as_str),
                Some(triage_rel)
            );
        }
    }

    assert_eq!(
        seen_packet_ids, required_packet_ids,
        "event packet coverage should match required packet ids"
    );

    for scenario in &required_scenarios {
        let bundle_row = bundle_rows
            .iter()
            .find(|row| row["scenario_id"].as_str() == Some(scenario.as_str()))
            .unwrap_or_else(|| panic!("missing bundle index row for scenario {scenario}"));
        for key in required_string_array(&schema, "required_bundle_index_row_keys") {
            assert!(
                bundle_row.get(key).is_some(),
                "bundle index row missing required key `{key}`"
            );
        }
        let bundle_row_gate_step_id = assert_gate_step_id(
            &bundle_row["gate_step_id"],
            required_gate_step_prefix,
            &format!("bundle_index.rows[{scenario}].gate_step_id"),
        );
        assert_eq!(
            bundle_row_gate_step_id, bundle_gate_step_id,
            "bundle row gate_step_id should match bundle index gate_step_id"
        );
        let bundle_row_forensics_index_path = bundle_row["forensics_index_path"]
            .as_str()
            .expect("bundle index row forensics_index_path should be string");
        assert_eq!(
            bundle_row_forensics_index_path, bundle_forensics_index_path,
            "bundle row forensics_index_path should match bundle index"
        );
        assert_path_exists(
            root.as_path(),
            bundle_row_forensics_index_path,
            &format!("bundle_index.rows[{scenario}].forensics_index_path"),
        );
        assert_retention_policy(
            root.as_path(),
            &schema,
            &bundle_row["retention_policy"],
            &format!("bundle_index.rows[{scenario}].retention_policy"),
        );
        let manifests = bundle_row["manifests"]
            .as_object()
            .expect("bundle index manifests should be object");
        let failure_envelopes = bundle_row["failure_envelopes"]
            .as_object()
            .expect("bundle index failure_envelopes should be object");
        for pass_label in &required_pass_labels {
            assert!(
                manifests.get(pass_label).is_some(),
                "bundle index missing manifest entry for scenario/pass ({scenario}, {pass_label})"
            );
            assert!(
                failure_envelopes.get(pass_label).is_some(),
                "bundle index missing failure envelope entry for scenario/pass ({scenario}, {pass_label})"
            );
            let manifest_rel = manifests
                .get(pass_label)
                .and_then(Value::as_str)
                .unwrap_or_else(|| {
                    panic!("bundle index manifest for ({scenario}, {pass_label}) should be string")
                });
            assert_path_exists(
                root.as_path(),
                manifest_rel,
                &format!("bundle_index.rows[{scenario}].manifests[{pass_label}]"),
            );
            let failure_envelope_rel = failure_envelopes
                .get(pass_label)
                .and_then(Value::as_str)
                .unwrap_or_else(|| {
                    panic!(
                        "bundle index failure_envelopes for ({scenario}, {pass_label}) should be string"
                    )
                });
            assert_path_exists(
                root.as_path(),
                failure_envelope_rel,
                &format!("bundle_index.rows[{scenario}].failure_envelopes[{pass_label}]"),
            );
            let event_row = events
                .iter()
                .find(|row| {
                    row["scenario_id"].as_str() == Some(scenario.as_str())
                        && row["pass_label"].as_str() == Some(pass_label.as_str())
                })
                .unwrap_or_else(|| {
                    panic!(
                        "missing event row for ({scenario}, {pass_label}) during bundle index check"
                    )
                });
            assert_eq!(
                event_row["bundle_manifest_path"].as_str(),
                Some(manifest_rel),
                "bundle index manifest entry should match event bundle_manifest_path"
            );
            assert_eq!(
                event_row["failure_envelope_path"].as_str(),
                Some(failure_envelope_rel),
                "bundle index failure envelope entry should match event failure_envelope_path"
            );
            assert_eq!(
                event_row["gate_step_id"].as_str(),
                Some(bundle_row_gate_step_id.as_str()),
                "bundle row gate_step_id should match event gate_step_id"
            );
            assert_eq!(
                event_row["retention_policy"], bundle_row["retention_policy"],
                "bundle row retention_policy should match event retention_policy"
            );
        }
        assert_evidence_refs(
            root.as_path(),
            &schema,
            &bundle_row["parity_perf_raptorq_evidence"],
            &format!("bundle_index.rows[{scenario}].parity_perf_raptorq_evidence"),
        );
        for pass_label in &required_pass_labels {
            assert!(
                seen_pairs.contains(&(scenario.clone(), pass_label.clone())),
                "missing scenario/pass event pair ({scenario}, {pass_label})"
            );
        }
        assert_eq!(
            bundle_ids_by_scenario.get(scenario).map(BTreeSet::len),
            Some(1),
            "bundle_id should be stable across passes for scenario {scenario}"
        );
        assert_eq!(
            fingerprints_by_scenario.get(scenario).map(BTreeSet::len),
            Some(1),
            "stable_fingerprint should be stable across passes for scenario {scenario}"
        );
    }

    for (idx, failure_row) in failure_index.iter().enumerate() {
        for key in required_string_array(&schema, "required_bundle_index_failure_keys") {
            assert!(
                failure_row.get(key).is_some(),
                "bundle_index.failure_index[{idx}] missing required key `{key}`"
            );
        }
        let replay_command = failure_row["replay_command"]
            .as_str()
            .expect("bundle_index.failure_index replay_command should be string");
        assert!(
            !replay_command.trim().is_empty(),
            "bundle_index.failure_index replay_command should be non-empty"
        );
        let failure_gate_step_id = assert_gate_step_id(
            &failure_row["gate_step_id"],
            required_gate_step_prefix,
            &format!("bundle_index.failure_index[{idx}].gate_step_id"),
        );
        assert_eq!(
            failure_gate_step_id, bundle_gate_step_id,
            "failure_index gate_step_id should match bundle index gate_step_id"
        );
        let failure_forensics_index_path = failure_row["forensics_index_path"]
            .as_str()
            .expect("bundle_index.failure_index forensics_index_path should be string");
        assert_eq!(
            failure_forensics_index_path, bundle_forensics_index_path,
            "failure_index forensics_index_path should match bundle index path"
        );
        assert_path_exists(
            root.as_path(),
            failure_forensics_index_path,
            &format!("bundle_index.failure_index[{idx}].forensics_index_path"),
        );
        let replay_bundle_manifest_path = failure_row["replay_bundle_manifest_path"]
            .as_str()
            .expect("bundle_index.failure_index replay_bundle_manifest_path should be string");
        assert_path_exists(
            root.as_path(),
            replay_bundle_manifest_path,
            &format!("bundle_index.failure_index[{idx}].replay_bundle_manifest_path"),
        );
        assert_retention_policy(
            root.as_path(),
            &schema,
            &failure_row["retention_policy"],
            &format!("bundle_index.failure_index[{idx}].retention_policy"),
        );
        let failure_envelope_rel = failure_row["failure_envelope_path"]
            .as_str()
            .expect("bundle_index.failure_index failure_envelope_path should be string");
        assert_path_exists(
            root.as_path(),
            failure_envelope_rel,
            &format!("bundle_index.failure_index[{idx}].failure_envelope_path"),
        );
        let failure_envelope = load_json(&root.join(failure_envelope_rel));
        assert_eq!(
            failure_envelope["status"].as_str(),
            Some("failed"),
            "bundle_index.failure_index should only include failed envelopes"
        );
        assert_forensics_links(
            &schema,
            &failure_row["forensics_links"],
            &format!("bundle_index.failure_index[{idx}].forensics_links"),
        );
        let scenario = failure_row["scenario_id"]
            .as_str()
            .expect("bundle_index.failure_index scenario_id should be string");
        let pass_label = failure_row["pass_label"]
            .as_str()
            .expect("bundle_index.failure_index pass_label should be string");
        let matching_event = events
            .iter()
            .find(|row| {
                row["scenario_id"].as_str() == Some(scenario)
                    && row["pass_label"].as_str() == Some(pass_label)
            })
            .unwrap_or_else(|| {
                panic!("missing matching event row for bundle_index.failure_index[{idx}]")
            });
        assert_eq!(
            matching_event["bundle_manifest_path"].as_str(),
            Some(replay_bundle_manifest_path),
            "failure_index replay_bundle_manifest_path should match event bundle_manifest_path"
        );
        assert_eq!(
            matching_event["retention_policy"], failure_row["retention_policy"],
            "failure_index retention_policy should match event retention_policy"
        );
        assert_evidence_refs(
            root.as_path(),
            &schema,
            &failure_row["parity_perf_raptorq_evidence"],
            &format!("bundle_index.failure_index[{idx}].parity_perf_raptorq_evidence"),
        );
    }

    let checks = report["scenario_checks"]
        .as_array()
        .expect("scenario_checks should be array");
    assert_eq!(checks.len(), required_scenarios.len());
    for row in checks {
        assert_eq!(row["bundle_id_match"].as_bool(), Some(true));
        assert_eq!(row["stable_fingerprint_match"].as_bool(), Some(true));
        assert_eq!(row["status_ok"].as_bool(), Some(true));
    }
}
