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

#[test]
fn doc_pass02_symbol_api_census_is_complete_and_contract_aligned() {
    let root = repo_root();
    let artifact = load_json(&root.join("artifacts/docs/v1/doc_pass02_symbol_api_census_v1.json"));
    let schema = load_json(
        &root.join("artifacts/docs/schema/v1/doc_pass02_symbol_api_census_schema_v1.json"),
    );

    for key in required_string_array(&schema, "required_top_level_keys") {
        assert!(
            artifact.get(key).is_some(),
            "artifact missing top-level key `{key}`"
        );
    }

    let expected_crates = BTreeSet::from([
        "fnx-algorithms",
        "fnx-classes",
        "fnx-conformance",
        "fnx-convert",
        "fnx-dispatch",
        "fnx-durability",
        "fnx-generators",
        "fnx-readwrite",
        "fnx-runtime",
        "fnx-views",
    ])
    .into_iter()
    .map(str::to_owned)
    .collect::<BTreeSet<_>>();

    let summary = artifact["census_summary"]
        .as_object()
        .expect("census_summary should be object");
    for key in required_string_array(&schema, "required_summary_keys") {
        assert!(
            summary.contains_key(key),
            "census_summary missing key `{key}`"
        );
    }

    let families = artifact["subsystem_families"]
        .as_array()
        .expect("subsystem_families should be array");
    assert!(
        !families.is_empty(),
        "subsystem_families should be non-empty"
    );
    for family in families {
        for key in required_string_array(&schema, "required_family_keys") {
            assert!(
                family.get(key).is_some(),
                "subsystem_families row missing key `{key}`"
            );
        }
        let crates = family["crates"]
            .as_array()
            .expect("subsystem family crates should be array");
        assert!(
            !crates.is_empty(),
            "subsystem family should map to at least one crate"
        );
    }

    let symbol_rows = artifact["symbol_inventory"]
        .as_array()
        .expect("symbol_inventory should be array");
    assert!(
        !symbol_rows.is_empty(),
        "symbol_inventory must be non-empty"
    );

    let mut symbol_ids = BTreeSet::new();
    let mut observed_crates = BTreeSet::new();
    let mut observed_high = BTreeSet::new();
    let mut public_count = 0_u64;
    let mut internal_count = 0_u64;

    for row in symbol_rows {
        for key in required_string_array(&schema, "required_symbol_keys") {
            assert!(row.get(key).is_some(), "symbol row missing key `{key}`");
        }

        let symbol_id = row["symbol_id"]
            .as_str()
            .expect("symbol_id should be string");
        assert!(
            symbol_ids.insert(symbol_id.to_owned()),
            "duplicate symbol_id `{symbol_id}`"
        );

        let crate_name = row["crate_name"]
            .as_str()
            .expect("crate_name should be string");
        observed_crates.insert(crate_name.to_owned());
        assert!(
            expected_crates.contains(crate_name),
            "symbol row has unknown crate `{crate_name}`"
        );

        let module_path = row["module_path"]
            .as_str()
            .expect("module_path should be string");
        assert_path_exists(root.as_path(), module_path, "symbol_inventory.module_path");

        let line = row["line"]
            .as_u64()
            .expect("line should be unsigned integer");
        assert!(line >= 1, "line should be >= 1");

        let visibility = row["visibility"]
            .as_str()
            .expect("visibility should be string");
        let api_surface = row["api_surface"]
            .as_str()
            .expect("api_surface should be string");
        match visibility {
            "public" => {
                public_count += 1;
                assert_eq!(
                    api_surface, "public_contract",
                    "public symbols must map to public_contract api_surface"
                );
            }
            "internal" => {
                internal_count += 1;
                assert_eq!(
                    api_surface, "internal_impl",
                    "internal symbols must map to internal_impl api_surface"
                );
            }
            _ => panic!("visibility must be public/internal, got {visibility}"),
        }

        let risk = row["regression_risk"]
            .as_str()
            .expect("regression_risk should be string");
        assert!(
            matches!(risk, "high" | "medium" | "low"),
            "invalid regression_risk {risk}"
        );
        if risk == "high" {
            observed_high.insert(symbol_id.to_owned());
        }

        let bindings = row["test_bindings"]
            .as_array()
            .expect("test_bindings should be array");
        assert!(!bindings.is_empty(), "test_bindings should be non-empty");

        let replay = row["replay_command"]
            .as_str()
            .expect("replay_command should be string");
        assert!(
            replay.contains("rch exec --"),
            "replay_command should use rch offload"
        );
    }

    assert_eq!(
        observed_crates, expected_crates,
        "workspace crate coverage drift"
    );

    let high_rows = artifact["high_regression_symbols"]
        .as_array()
        .expect("high_regression_symbols should be array");
    assert!(
        !high_rows.is_empty(),
        "high_regression_symbols should be non-empty"
    );
    let high_symbol_ids = high_rows
        .iter()
        .map(|row| {
            row["symbol_id"]
                .as_str()
                .expect("high_regression_symbols.symbol_id should be string")
                .to_owned()
        })
        .collect::<BTreeSet<_>>();
    assert_eq!(
        high_symbol_ids, observed_high,
        "high_regression_symbols must match computed high-risk symbol set"
    );

    let risk_notes = artifact["risk_notes"]
        .as_array()
        .expect("risk_notes should be array");
    assert!(!risk_notes.is_empty(), "risk_notes should be non-empty");
    assert_eq!(
        risk_notes.len(),
        high_symbol_ids.len(),
        "risk_notes count should match high_regression_symbols count"
    );
    let mut note_ids = BTreeSet::new();
    for note in risk_notes {
        for key in required_string_array(&schema, "required_risk_note_keys") {
            assert!(note.get(key).is_some(), "risk note missing key `{key}`");
        }
        let note_id = note["note_id"].as_str().expect("note_id should be string");
        assert!(
            note_ids.insert(note_id.to_owned()),
            "duplicate risk note_id `{note_id}`"
        );
        let symbol_id = note["symbol_id"]
            .as_str()
            .expect("symbol_id should be string");
        assert!(
            high_symbol_ids.contains(symbol_id),
            "risk note references unknown high-risk symbol `{symbol_id}`"
        );
    }

    assert_eq!(
        summary["workspace_crate_count"]
            .as_u64()
            .expect("workspace_crate_count should be u64"),
        expected_crates.len() as u64,
        "workspace_crate_count mismatch"
    );
    assert_eq!(
        summary["symbol_count_total"]
            .as_u64()
            .expect("symbol_count_total should be u64"),
        symbol_rows.len() as u64,
        "symbol_count_total mismatch"
    );
    assert_eq!(
        summary["public_symbol_count"]
            .as_u64()
            .expect("public_symbol_count should be u64"),
        public_count,
        "public_symbol_count mismatch"
    );
    assert_eq!(
        summary["internal_symbol_count"]
            .as_u64()
            .expect("internal_symbol_count should be u64"),
        internal_count,
        "internal_symbol_count mismatch"
    );
    assert_eq!(
        summary["high_regression_count"]
            .as_u64()
            .expect("high_regression_count should be u64"),
        high_symbol_ids.len() as u64,
        "high_regression_count mismatch"
    );

    let alien = artifact["alien_uplift_contract_card"]
        .as_object()
        .expect("alien_uplift_contract_card should be object");
    let ev_score = alien["ev_score"]
        .as_f64()
        .expect("ev_score should be numeric");
    assert!(ev_score >= 2.0, "ev_score must be >= 2.0");
    let baseline_comparator = alien["baseline_comparator"]
        .as_str()
        .expect("baseline_comparator should be string");
    assert!(
        !baseline_comparator.trim().is_empty(),
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

    let decision_contract = artifact["decision_theoretic_runtime_contract"]
        .as_object()
        .expect("decision_theoretic_runtime_contract should be object");
    for key in required_string_array(&schema, "required_decision_contract_keys") {
        assert!(
            decision_contract.contains_key(key),
            "decision_theoretic_runtime_contract missing key `{key}`"
        );
    }
    let thresholds = decision_contract["safe_mode_fallback"]["trigger_thresholds"]
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

    let logs = artifact["structured_logging_evidence"]
        .as_array()
        .expect("structured_logging_evidence should be array");
    assert!(
        !logs.is_empty(),
        "structured_logging_evidence should be non-empty"
    );
    for (idx, entry) in logs.iter().enumerate() {
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
