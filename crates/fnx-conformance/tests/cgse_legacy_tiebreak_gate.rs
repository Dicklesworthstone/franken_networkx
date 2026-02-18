use fnx_conformance::{DriftTaxonomyReport, HarnessConfig, run_smoke};
use fnx_runtime::{
    CGSE_POLICY_SPEC_PATH, CGSE_POLICY_SPEC_SCHEMA_PATH, CgsePolicyEngine, CgsePolicyRule,
    CompatibilityMode, DecisionAction, StructuredTestLog, TestKind, TestStatus,
    cgse_policy_schema_version,
};
use serde_json::Value;
use std::collections::{BTreeMap, BTreeSet};
use std::fs;
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicU64, Ordering};
use std::time::{SystemTime, UNIX_EPOCH};

static UNIQUE_NONCE: AtomicU64 = AtomicU64::new(0);

fn next_unique_nonce() -> u64 {
    UNIQUE_NONCE.fetch_add(1, Ordering::Relaxed)
}

fn unique_report_root() -> PathBuf {
    let time_nonce = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map_or(0, |dur| dur.as_millis());
    let nonce = next_unique_nonce();
    std::env::temp_dir().join(format!("fnx_conformance_cgse_gate_{time_nonce}_{nonce}"))
}

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
fn cgse_legacy_tiebreak_ledger_is_complete_and_source_anchored() {
    let root = repo_root();
    let artifact =
        load_json(&root.join("artifacts/cgse/v1/cgse_legacy_tiebreak_ordering_ledger_v1.json"));
    let schema = load_json(
        &root.join("artifacts/cgse/schema/v1/cgse_legacy_tiebreak_ordering_ledger_schema_v1.json"),
    );

    for key in required_string_array(&schema, "required_top_level_keys") {
        assert!(
            artifact.get(key).is_some(),
            "artifact missing top-level key `{key}`"
        );
    }

    let required_families = required_string_array(&schema, "required_operation_families")
        .into_iter()
        .collect::<BTreeSet<_>>();

    let rule_families = artifact["rule_families"]
        .as_array()
        .expect("rule_families should be array")
        .iter()
        .map(|value| {
            value
                .as_str()
                .expect("rule_families entries should be string")
        })
        .collect::<BTreeSet<_>>();
    assert_eq!(
        rule_families, required_families,
        "rule_families must match schema operation family set"
    );

    let required_rule_keys = required_string_array(&schema, "required_rule_keys");
    let required_anchor_keys = required_string_array(&schema, "required_anchor_keys");
    let required_ambiguity_keys = required_string_array(&schema, "required_ambiguity_keys");
    let required_channels = required_string_array(&schema, "required_test_hook_channels");
    let required_hook_keys = required_string_array(&schema, "required_test_hook_keys");

    let rules = artifact["rules"].as_array().expect("rules should be array");
    assert!(
        rules.len() >= required_families.len(),
        "rules should include at least one row per required family"
    );

    let mut observed_families = BTreeSet::new();
    let mut seen_rule_ids = BTreeSet::new();
    let mut ambiguity_count = 0usize;

    for rule in rules {
        let rule_id = rule["rule_id"].as_str().expect("rule_id should be string");
        assert!(
            seen_rule_ids.insert(rule_id),
            "duplicate rule_id detected: {rule_id}"
        );

        for key in &required_rule_keys {
            assert!(
                rule.get(*key).is_some(),
                "rule {rule_id} missing key `{key}`"
            );
        }

        let family = rule["operation_family"]
            .as_str()
            .expect("operation_family should be string");
        observed_families.insert(family);
        assert!(
            required_families.contains(family),
            "rule {rule_id} has unsupported family {family}"
        );

        let anchors = rule["source_anchors"]
            .as_array()
            .expect("source_anchors should be array");
        assert!(
            !anchors.is_empty(),
            "rule {rule_id} must define at least one source anchor"
        );
        for (idx, anchor) in anchors.iter().enumerate() {
            for key in &required_anchor_keys {
                assert!(
                    anchor.get(*key).is_some(),
                    "rule {rule_id} source_anchor[{idx}] missing `{key}`"
                );
            }
            let path = anchor["path"]
                .as_str()
                .expect("source anchor path should be string");
            assert_path(path, &format!("rule {rule_id} source_anchor[{idx}]"), &root);
            let symbols = anchor["symbols"]
                .as_array()
                .expect("source anchor symbols should be array");
            assert!(
                !symbols.is_empty(),
                "rule {rule_id} source_anchor[{idx}] symbols must be non-empty"
            );
        }

        let ambiguities = rule["ambiguity_tags"]
            .as_array()
            .expect("ambiguity_tags should be array");
        ambiguity_count += ambiguities.len();
        for (idx, ambiguity) in ambiguities.iter().enumerate() {
            for key in &required_ambiguity_keys {
                assert!(
                    ambiguity.get(*key).is_some(),
                    "rule {rule_id} ambiguity_tags[{idx}] missing `{key}`"
                );
            }
            let options = ambiguity["policy_options"]
                .as_array()
                .expect("policy_options should be array");
            assert!(
                options.len() >= 2,
                "rule {rule_id} ambiguity_tags[{idx}] must include at least two policy options"
            );
        }

        let hooks = rule["test_hooks"]
            .as_object()
            .expect("test_hooks should be object");
        for channel in &required_channels {
            let rows = hooks[*channel]
                .as_array()
                .unwrap_or_else(|| panic!("rule {rule_id} channel {channel} should be array"));
            assert!(
                !rows.is_empty(),
                "rule {rule_id} channel {channel} must be non-empty"
            );
            for (idx, row) in rows.iter().enumerate() {
                for key in &required_hook_keys {
                    assert!(
                        row.get(*key).is_some(),
                        "rule {rule_id} channel {channel}[{idx}] missing `{key}`"
                    );
                }
                let path = row["path"].as_str().expect("hook path should be string");
                assert_path(
                    path,
                    &format!("rule {rule_id} channel {channel}[{idx}]"),
                    &root,
                );
            }
        }
    }

    assert_eq!(
        observed_families, required_families,
        "rules must cover all required operation families"
    );
    assert!(
        ambiguity_count > 0,
        "ledger should register at least one ambiguity tag"
    );

    let ambiguity_register = artifact["ambiguity_register"]
        .as_array()
        .expect("ambiguity_register should be array");
    assert!(
        !ambiguity_register.is_empty(),
        "ambiguity_register should be non-empty"
    );
    for (idx, row) in ambiguity_register.iter().enumerate() {
        let rule_id = row["rule_id"]
            .as_str()
            .unwrap_or_else(|| panic!("ambiguity_register[{idx}].rule_id should be string"));
        assert!(
            seen_rule_ids.contains(rule_id),
            "ambiguity_register[{idx}] references unknown rule_id {rule_id}"
        );
        let family = row["operation_family"].as_str().unwrap_or_else(|| {
            panic!("ambiguity_register[{idx}].operation_family should be string")
        });
        assert!(
            required_families.contains(family),
            "ambiguity_register[{idx}] uses unsupported family {family}"
        );
    }

    let profile_required = required_string_array(&schema, "required_profile_artifact_keys");
    let profile = artifact["profile_first_artifacts"]
        .as_object()
        .expect("profile_first_artifacts should be object");
    for key in profile_required {
        let path = profile[key]
            .as_str()
            .unwrap_or_else(|| panic!("profile_first_artifacts.{key} should be string"));
        assert_path(path, &format!("profile_first_artifacts.{key}"), &root);
    }

    for (idx, path) in artifact["isomorphism_proof_artifacts"]
        .as_array()
        .expect("isomorphism_proof_artifacts should be array")
        .iter()
        .enumerate()
    {
        let path = path
            .as_str()
            .unwrap_or_else(|| panic!("isomorphism_proof_artifacts[{idx}] should be string"));
        assert_path(path, &format!("isomorphism_proof_artifacts[{idx}]"), &root);
    }

    for (idx, path) in artifact["structured_logging_evidence"]
        .as_array()
        .expect("structured_logging_evidence should be array")
        .iter()
        .enumerate()
    {
        let path = path
            .as_str()
            .unwrap_or_else(|| panic!("structured_logging_evidence[{idx}] should be string"));
        assert_path(path, &format!("structured_logging_evidence[{idx}]"), &root);
    }

    let ev_score = artifact["alien_uplift_contract_card"]["ev_score"]
        .as_f64()
        .expect("alien_uplift_contract_card.ev_score should be numeric");
    assert!(ev_score >= 2.0, "ev_score must be >= 2.0");
}

#[test]
fn cgse_policy_runtime_surface_matches_generated_policy_rows() {
    let root = repo_root();
    assert_path(CGSE_POLICY_SPEC_PATH, "runtime policy spec path", &root);
    assert_path(
        CGSE_POLICY_SPEC_SCHEMA_PATH,
        "runtime policy spec schema path",
        &root,
    );

    let policy = load_json(&root.join(CGSE_POLICY_SPEC_PATH));
    let schema_version = policy["schema_version"]
        .as_str()
        .expect("schema_version should be string");
    assert_eq!(schema_version, cgse_policy_schema_version());

    let rows = policy["policy_rows"]
        .as_array()
        .expect("policy_rows should be array");
    assert_eq!(rows.len(), CgsePolicyRule::ALL.len());

    for (idx, row) in rows.iter().enumerate() {
        let rule_id = row["rule_id"]
            .as_str()
            .unwrap_or_else(|| panic!("policy_rows[{idx}].rule_id should be string"));
        let mapped = CgsePolicyRule::from_rule_id(rule_id)
            .unwrap_or_else(|| panic!("policy_rows[{idx}] uses unknown runtime rule_id {rule_id}"));
        assert_eq!(mapped.as_rule_id(), rule_id);
    }

    let engine = CgsePolicyEngine::new(CompatibilityMode::Hardened);
    let allowlisted = engine.evaluate_at(CgsePolicyRule::R01, Some("CGSE-AMB-001"), 0.2, false, 7);
    assert_eq!(allowlisted.policy_spec_path, CGSE_POLICY_SPEC_PATH);
    assert_eq!(allowlisted.decision.action, DecisionAction::FullValidate);
    assert!(allowlisted.allowlisted_ambiguity);

    let blocked = engine.evaluate_at(CgsePolicyRule::R01, Some("CGSE-AMB-999"), 0.01, false, 8);
    assert_eq!(blocked.decision.action, DecisionAction::FailClosed);
    assert!(!blocked.allowlisted_ambiguity);
}

#[test]
fn cgse_differential_strict_fixture_matrix_is_parity_clean_and_triage_ready() {
    let mut cfg = HarnessConfig::default_paths();
    let report_root = unique_report_root();
    cfg.report_root = Some(report_root.clone());

    let report = run_smoke(&cfg);
    assert!(
        report.oracle_present,
        "legacy oracle must be available for differential parity checks"
    );

    let expected_fixture_ids = BTreeSet::from([
        "generated/view_neighbors_strict.json".to_owned(),
        "generated/dispatch_route_strict.json".to_owned(),
        "generated/convert_edge_list_strict.json".to_owned(),
        "generated/centrality_degree_strict.json".to_owned(),
        "generated/readwrite_roundtrip_strict.json".to_owned(),
        "generated/generators_path_strict.json".to_owned(),
        "generated/runtime_config_optional_strict.json".to_owned(),
    ]);

    for fixture_id in &expected_fixture_ids {
        let row = report
            .fixture_reports
            .iter()
            .find(|fixture| &fixture.fixture_id == fixture_id)
            .unwrap_or_else(|| panic!("expected fixture row {fixture_id} in smoke report"));
        assert_eq!(row.mode, CompatibilityMode::Strict);
        assert!(row.passed, "fixture {fixture_id} should pass strict parity");
        assert_eq!(
            row.strict_violation_count, 0,
            "fixture {fixture_id} should have zero strict violations"
        );
        assert_eq!(
            row.hardened_allowlisted_count, 0,
            "strict fixture {fixture_id} should not record hardened allowlisted rows"
        );
        assert!(
            row.mismatch_taxonomy.is_empty(),
            "fixture {fixture_id} should emit empty drift taxonomy rows"
        );
        assert!(
            row.replay_command.starts_with("rch exec --"),
            "fixture {fixture_id} replay command should stay rch-offloaded"
        );
    }

    let taxonomy_raw = fs::read_to_string(report_root.join("mismatch_taxonomy_report.json"))
        .expect("mismatch taxonomy report should exist");
    let taxonomy: DriftTaxonomyReport =
        serde_json::from_str(&taxonomy_raw).expect("taxonomy report should parse");
    for fixture_id in &expected_fixture_ids {
        let row = taxonomy
            .fixtures
            .iter()
            .find(|fixture| &fixture.fixture_id == fixture_id)
            .unwrap_or_else(|| panic!("expected taxonomy row for fixture {fixture_id}"));
        assert_eq!(row.mode, CompatibilityMode::Strict);
        assert_eq!(row.strict_violation_count, 0);
        assert_eq!(row.hardened_allowlisted_count, 0);
        assert!(
            row.mismatches.is_empty(),
            "taxonomy row for {fixture_id} should be mismatch-free"
        );
        assert!(
            row.replay_command.starts_with("rch exec --"),
            "taxonomy replay command for {fixture_id} should stay rch-offloaded"
        );
    }

    let logs_raw = fs::read_to_string(report_root.join("structured_logs.jsonl"))
        .expect("structured logs should exist");
    let logs = logs_raw
        .lines()
        .map(|line| serde_json::from_str::<StructuredTestLog>(line).expect("valid structured log"))
        .collect::<Vec<StructuredTestLog>>();
    for fixture_id in &expected_fixture_ids {
        let log = logs
            .iter()
            .find(|row| row.fixture_id.as_deref() == Some(fixture_id.as_str()))
            .unwrap_or_else(|| panic!("expected structured log row for fixture {fixture_id}"));
        log.validate()
            .expect("strict differential structured log should satisfy schema");
        assert_eq!(log.mode, CompatibilityMode::Strict);
        assert_eq!(log.test_kind, TestKind::Differential);
        assert_eq!(log.status, TestStatus::Passed);
        assert!(log.reason_code.is_none());
        assert!(
            log.replay_command.starts_with("rch exec --"),
            "structured log replay command should stay rch-offloaded"
        );
    }
}

#[test]
fn cgse_policy_rows_cover_differential_hooks_and_adversarial_fail_closed_matrix() {
    let root = repo_root();
    let ledger =
        load_json(&root.join("artifacts/cgse/v1/cgse_legacy_tiebreak_ordering_ledger_v1.json"));
    let policy = load_json(&root.join(CGSE_POLICY_SPEC_PATH));

    let mut differential_hooks_by_rule = BTreeMap::<String, BTreeSet<String>>::new();
    for (idx, row) in ledger["rules"]
        .as_array()
        .expect("ledger rules should be array")
        .iter()
        .enumerate()
    {
        let rule_id = row["rule_id"]
            .as_str()
            .unwrap_or_else(|| panic!("ledger rules[{idx}].rule_id should be string"));
        let hooks = row["test_hooks"]["differential"]
            .as_array()
            .unwrap_or_else(|| {
                panic!("ledger rules[{idx}].test_hooks.differential should be array")
            })
            .iter()
            .map(|entry| {
                entry["hook_id"]
                    .as_str()
                    .unwrap_or_else(|| {
                        panic!(
                            "ledger rules[{idx}].test_hooks.differential hook_id should be string"
                        )
                    })
                    .to_owned()
            })
            .collect::<BTreeSet<String>>();
        assert!(
            !hooks.is_empty(),
            "rule {rule_id} must define differential hooks"
        );
        differential_hooks_by_rule.insert(rule_id.to_owned(), hooks);
    }

    let strict_engine = CgsePolicyEngine::new(CompatibilityMode::Strict);
    let hardened_engine = CgsePolicyEngine::new(CompatibilityMode::Hardened);
    for (idx, row) in policy["policy_rows"]
        .as_array()
        .expect("policy_rows should be array")
        .iter()
        .enumerate()
    {
        let rule_id = row["rule_id"]
            .as_str()
            .unwrap_or_else(|| panic!("policy_rows[{idx}].rule_id should be string"));
        let policy_id = row["policy_id"]
            .as_str()
            .unwrap_or_else(|| panic!("policy_rows[{idx}].policy_id should be string"));
        let runtime_rule = CgsePolicyRule::from_rule_id(rule_id)
            .unwrap_or_else(|| panic!("policy_rows[{idx}] unknown runtime rule id {rule_id}"));
        assert_eq!(policy_id, runtime_rule.policy_id());

        let policy_diff_hooks = row["verification_hooks"]["differential"]
            .as_array()
            .unwrap_or_else(|| {
                panic!("policy_rows[{idx}].verification_hooks.differential should be array")
            })
            .iter()
            .map(|entry| {
                entry
                    .as_str()
                    .unwrap_or_else(|| {
                        panic!(
                            "policy_rows[{idx}].verification_hooks.differential entries must be string"
                        )
                    })
                    .to_owned()
            })
            .collect::<BTreeSet<String>>();
        let ledger_hooks = differential_hooks_by_rule
            .get(rule_id)
            .unwrap_or_else(|| panic!("missing ledger differential hook mapping for {rule_id}"));
        assert_eq!(
            policy_diff_hooks, *ledger_hooks,
            "policy and ledger differential hooks must match for {rule_id}"
        );

        let policy_allowlist = row["hardened_allowlist"]
            .as_array()
            .unwrap_or_else(|| panic!("policy_rows[{idx}].hardened_allowlist should be array"))
            .iter()
            .map(|entry| {
                entry
                    .as_str()
                    .unwrap_or_else(|| {
                        panic!("policy_rows[{idx}].hardened_allowlist entry should be string")
                    })
                    .to_owned()
            })
            .collect::<BTreeSet<String>>();
        let runtime_allowlist = runtime_rule
            .hardened_allowlist()
            .iter()
            .map(|entry| (*entry).to_owned())
            .collect::<BTreeSet<String>>();
        assert_eq!(
            policy_allowlist, runtime_allowlist,
            "policy and runtime allowlist must match for {rule_id}"
        );

        let sample_allowlisted_tag = runtime_rule
            .hardened_allowlist()
            .first()
            .copied()
            .expect("runtime allowlist must be non-empty");
        let metamorphic_a =
            strict_engine.evaluate_at(runtime_rule, Some(sample_allowlisted_tag), 0.33, false, 11);
        let metamorphic_b =
            strict_engine.evaluate_at(runtime_rule, Some(sample_allowlisted_tag), 0.33, false, 22);
        assert_eq!(metamorphic_a.decision.action, metamorphic_b.decision.action);
        assert_eq!(
            metamorphic_a.allowlisted_ambiguity,
            metamorphic_b.allowlisted_ambiguity
        );
        assert_eq!(metamorphic_a.policy_id, metamorphic_b.policy_id);

        let adversarial_ambiguity =
            hardened_engine.evaluate_at(runtime_rule, Some("CGSE-AMB-999"), 0.02, false, 33);
        assert_eq!(
            adversarial_ambiguity.decision.action,
            DecisionAction::FailClosed
        );
        assert!(!adversarial_ambiguity.allowlisted_ambiguity);
        let adversarial_unknown_feature =
            strict_engine.evaluate_at(runtime_rule, Some(sample_allowlisted_tag), 0.01, true, 44);
        assert_eq!(
            adversarial_unknown_feature.decision.action,
            DecisionAction::FailClosed
        );
    }
}
