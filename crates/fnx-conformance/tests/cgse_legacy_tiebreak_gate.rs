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
