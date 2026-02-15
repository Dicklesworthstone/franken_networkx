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

fn fixture_inventory(root: &Path) -> BTreeSet<String> {
    let fixture_root = root.join("crates/fnx-conformance/fixtures");
    let mut stack = vec![fixture_root.clone()];
    let mut out = BTreeSet::new();
    while let Some(dir) = stack.pop() {
        let entries = fs::read_dir(&dir)
            .unwrap_or_else(|err| panic!("expected readable directory {}: {err}", dir.display()));
        for entry in entries {
            let entry = entry.unwrap_or_else(|err| panic!("invalid dir entry: {err}"));
            let path = entry.path();
            if path.is_dir() {
                stack.push(path);
                continue;
            }
            if path.extension().and_then(|ext| ext.to_str()) != Some("json") {
                continue;
            }
            if path.file_name().and_then(|name| name.to_str()) == Some("smoke_case.json") {
                continue;
            }
            let rel = path
                .strip_prefix(&fixture_root)
                .unwrap_or_else(|err| panic!("failed to strip fixture prefix: {err}"))
                .to_string_lossy()
                .replace('\\', "/");
            out.insert(rel);
        }
    }
    out
}

fn assert_path(path: &str, ctx: &str, root: &Path) {
    assert!(
        !path.trim().is_empty(),
        "{ctx} path should be non-empty string"
    );
    let full = root.join(path);
    assert!(full.exists(), "{ctx} path missing: {}", full.display());
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

struct PathValidationContext<'a> {
    required_path_keys: &'a [&'a str],
    required_step_keys: &'a [&'a str],
    required_assertion_keys: &'a [&'a str],
    failure_classes: &'a BTreeSet<&'a str>,
    fixture_inventory: &'a BTreeSet<String>,
}

fn validate_path(
    journey_id: &str,
    path_name: &str,
    expected_mode: &str,
    row: &Value,
    ctx: &PathValidationContext<'_>,
) -> BTreeSet<String> {
    for key in ctx.required_path_keys {
        assert!(
            row.get(*key).is_some(),
            "{journey_id}.{path_name} missing key `{key}`"
        );
    }
    assert_eq!(
        row["mode"]
            .as_str()
            .unwrap_or_else(|| panic!("{journey_id}.{path_name}.mode should be string")),
        expected_mode,
        "{journey_id}.{path_name}.mode mismatch"
    );
    let mode_strategy = row["mode_strategy"].as_str().unwrap_or_else(|| {
        panic!("{journey_id}.{path_name}.mode_strategy should be non-empty string")
    });
    assert!(
        mode_strategy == "native_fixture" || mode_strategy == "mode_override_fixture",
        "{journey_id}.{path_name}.mode_strategy unsupported value {mode_strategy}"
    );
    let fixture_id = row["fixture_id"]
        .as_str()
        .unwrap_or_else(|| panic!("{journey_id}.{path_name}.fixture_id should be string"));
    assert!(
        ctx.fixture_inventory.contains(fixture_id),
        "{journey_id}.{path_name}.fixture_id references unknown fixture {fixture_id}"
    );
    assert!(
        row["deterministic_seed"].as_u64().is_some(),
        "{journey_id}.{path_name}.deterministic_seed should be non-negative integer"
    );

    let fixture_ids = row["fixture_ids"]
        .as_array()
        .unwrap_or_else(|| panic!("{journey_id}.{path_name}.fixture_ids should be array"));
    assert!(
        !fixture_ids.is_empty(),
        "{journey_id}.{path_name}.fixture_ids should not be empty"
    );
    let mut covered = BTreeSet::new();
    let mut includes_primary = false;
    for fixture in fixture_ids {
        let fixture_ref = fixture.as_str().unwrap_or_else(|| {
            panic!("{journey_id}.{path_name}.fixture_ids entries should be string")
        });
        if fixture_ref == fixture_id {
            includes_primary = true;
        }
        assert!(
            ctx.fixture_inventory.contains(fixture_ref),
            "{journey_id}.{path_name} references unknown fixture {fixture_ref}"
        );
        covered.insert(fixture_ref.to_owned());
    }
    assert!(
        includes_primary,
        "{journey_id}.{path_name}.fixture_ids must include fixture_id"
    );

    let replay_command = row["replay_command"].as_str().unwrap_or_else(|| {
        panic!("{journey_id}.{path_name}.replay_command should be non-empty string")
    });
    assert!(
        replay_command.contains(&format!("--fixture {fixture_id}")),
        "{journey_id}.{path_name}.replay_command missing fixture switch"
    );
    assert!(
        replay_command.contains(&format!("--mode {expected_mode}")),
        "{journey_id}.{path_name}.replay_command missing mode switch"
    );

    let steps = row["step_contract"]
        .as_array()
        .unwrap_or_else(|| panic!("{journey_id}.{path_name}.step_contract should be array"));
    assert!(
        !steps.is_empty(),
        "{journey_id}.{path_name}.step_contract should not be empty"
    );
    let mut step_ids = BTreeSet::new();
    for step in steps {
        for key in ctx.required_step_keys {
            assert!(
                step.get(*key).is_some(),
                "{journey_id}.{path_name}.step missing key `{key}`"
            );
        }
        let step_id = step["step_id"]
            .as_str()
            .unwrap_or_else(|| panic!("{journey_id}.{path_name}.step_id should be string"));
        assert!(
            step_ids.insert(step_id),
            "{journey_id}.{path_name}.step_id values must be unique"
        );
        let expected_outputs = step["expected_outputs"].as_array().unwrap_or_else(|| {
            panic!("{journey_id}.{path_name}.step.expected_outputs should be array")
        });
        assert!(
            !expected_outputs.is_empty(),
            "{journey_id}.{path_name}.step.expected_outputs must be non-empty"
        );
        for expected_ref in expected_outputs {
            let expected_ref = expected_ref.as_str().unwrap_or_else(|| {
                panic!("{journey_id}.{path_name}.expected_outputs entries should be string")
            });
            assert!(
                expected_ref.starts_with("expected."),
                "{journey_id}.{path_name}.expected_outputs entries should start with expected."
            );
        }
        let step_failure_classes = step["failure_classes"].as_array().unwrap_or_else(|| {
            panic!("{journey_id}.{path_name}.step.failure_classes should be array")
        });
        assert!(
            !step_failure_classes.is_empty(),
            "{journey_id}.{path_name}.step.failure_classes must be non-empty"
        );
        for failure_class in step_failure_classes {
            let failure_class = failure_class.as_str().unwrap_or_else(|| {
                panic!("{journey_id}.{path_name}.step.failure_classes entries should be string")
            });
            assert!(
                ctx.failure_classes.contains(failure_class),
                "{journey_id}.{path_name}.step has unknown failure class {failure_class}"
            );
        }
    }

    let assertions = row["oracle_assertions"]
        .as_array()
        .unwrap_or_else(|| panic!("{journey_id}.{path_name}.oracle_assertions should be array"));
    assert!(
        !assertions.is_empty(),
        "{journey_id}.{path_name}.oracle_assertions should not be empty"
    );
    for assertion in assertions {
        for key in ctx.required_assertion_keys {
            assert!(
                assertion.get(*key).is_some(),
                "{journey_id}.{path_name}.oracle_assertion missing key `{key}`"
            );
        }
        let expected_ref = assertion["expected_ref"].as_str().unwrap_or_else(|| {
            panic!("{journey_id}.{path_name}.oracle_assertion.expected_ref should be string")
        });
        assert!(
            expected_ref.starts_with("expected."),
            "{journey_id}.{path_name}.oracle_assertion.expected_ref should start with expected."
        );
        let failure_class = assertion["failure_class"].as_str().unwrap_or_else(|| {
            panic!("{journey_id}.{path_name}.oracle_assertion.failure_class should be string")
        });
        assert!(
            ctx.failure_classes.contains(failure_class),
            "{journey_id}.{path_name}.oracle_assertion has unknown failure class {failure_class}"
        );
    }

    let path_failure_classes = row["failure_classes"]
        .as_array()
        .unwrap_or_else(|| panic!("{journey_id}.{path_name}.failure_classes should be array"));
    assert!(
        !path_failure_classes.is_empty(),
        "{journey_id}.{path_name}.failure_classes should not be empty"
    );
    for failure_class in path_failure_classes {
        let failure_class = failure_class.as_str().unwrap_or_else(|| {
            panic!("{journey_id}.{path_name}.failure_classes entries should be string")
        });
        assert!(
            ctx.failure_classes.contains(failure_class),
            "{journey_id}.{path_name}.failure_classes has unknown class {failure_class}"
        );
    }
    covered
}

#[test]
fn e2e_scenario_matrix_oracle_contract_is_complete_and_replay_ready() {
    let root = repo_root();
    let artifact =
        load_json(&root.join("artifacts/e2e/v1/e2e_scenario_matrix_oracle_contract_v1.json"));
    let schema = load_json(
        &root.join("artifacts/e2e/schema/v1/e2e_scenario_matrix_oracle_contract_schema_v1.json"),
    );

    let required_top_keys = required_string_array(&schema, "required_top_level_keys");
    for key in required_top_keys {
        assert!(
            artifact.get(key).is_some(),
            "artifact missing top-level key `{key}`"
        );
    }

    let required_failure_classes = required_string_array(&schema, "required_failure_classes")
        .into_iter()
        .collect::<BTreeSet<_>>();
    let taxonomy = artifact["failure_class_taxonomy"]
        .as_array()
        .expect("failure_class_taxonomy should be array");
    let observed_failure_classes = taxonomy
        .iter()
        .map(|entry| {
            entry["failure_class"]
                .as_str()
                .expect("failure class should be string")
        })
        .collect::<BTreeSet<_>>();
    assert_eq!(
        observed_failure_classes, required_failure_classes,
        "failure class taxonomy drifted from schema contract"
    );

    let required_journey_keys = required_string_array(&schema, "required_journey_keys");
    let required_path_keys = required_string_array(&schema, "required_path_keys");
    let required_step_keys = required_string_array(&schema, "required_step_keys");
    let required_assertion_keys = required_string_array(&schema, "required_oracle_assertion_keys");

    let journeys = artifact["journeys"]
        .as_array()
        .expect("journeys should be non-empty array");
    assert!(!journeys.is_empty(), "journeys should not be empty");
    let mut journey_ids = BTreeSet::new();
    for journey in journeys {
        let journey_id = journey["journey_id"]
            .as_str()
            .expect("journey_id should be string");
        assert!(
            journey_ids.insert(journey_id.to_owned()),
            "journey_id values should be unique"
        );
        for key in &required_journey_keys {
            assert!(
                journey.get(*key).is_some(),
                "{journey_id} missing journey key `{key}`"
            );
        }
        assert!(
            journey["packet_id"]
                .as_str()
                .expect("packet_id should be string")
                .starts_with("FNX-P2C-"),
            "{journey_id}.packet_id should start with FNX-P2C-"
        );
    }

    let fixture_inventory = fixture_inventory(&root);
    let validation_ctx = PathValidationContext {
        required_path_keys: &required_path_keys,
        required_step_keys: &required_step_keys,
        required_assertion_keys: &required_assertion_keys,
        failure_classes: &required_failure_classes,
        fixture_inventory: &fixture_inventory,
    };
    let mut covered_from_paths = BTreeSet::new();
    for journey in journeys {
        let journey_id = journey["journey_id"]
            .as_str()
            .expect("journey_id should be string");
        covered_from_paths.extend(validate_path(
            journey_id,
            "strict_path",
            "strict",
            &journey["strict_path"],
            &validation_ctx,
        ));
        covered_from_paths.extend(validate_path(
            journey_id,
            "hardened_path",
            "hardened",
            &journey["hardened_path"],
            &validation_ctx,
        ));
    }

    let coverage = artifact["coverage_manifest"]
        .as_object()
        .expect("coverage_manifest should be object");
    for key in required_string_array(&schema, "required_coverage_keys") {
        assert!(
            coverage.get(key).is_some(),
            "coverage_manifest missing key `{key}`"
        );
    }
    let manifest_inventory = coverage["fixture_inventory"]
        .as_array()
        .expect("coverage_manifest.fixture_inventory should be array")
        .iter()
        .map(|value| {
            value
                .as_str()
                .expect("coverage fixture inventory entry should be string")
                .to_owned()
        })
        .collect::<BTreeSet<_>>();
    assert_eq!(
        manifest_inventory, fixture_inventory,
        "coverage fixture inventory should match fixture files"
    );
    let manifest_covered = coverage["covered_fixture_ids"]
        .as_array()
        .expect("coverage_manifest.covered_fixture_ids should be array")
        .iter()
        .map(|value| {
            value
                .as_str()
                .expect("covered fixture id should be string")
                .to_owned()
        })
        .collect::<BTreeSet<_>>();
    assert_eq!(
        manifest_covered, covered_from_paths,
        "coverage covered_fixture_ids should match strict/hardened path coverage"
    );
    let manifest_uncovered = coverage["uncovered_fixture_ids"]
        .as_array()
        .expect("coverage_manifest.uncovered_fixture_ids should be array");
    assert!(
        manifest_uncovered.is_empty(),
        "coverage_manifest.uncovered_fixture_ids should be empty"
    );

    let required_workflow_categories =
        required_string_array(&schema, "required_workflow_categories")
            .into_iter()
            .map(str::to_owned)
            .collect::<BTreeSet<_>>();
    let user_workflow_corpus = artifact["user_workflow_corpus"]
        .as_object()
        .expect("user_workflow_corpus should be object");
    for key in required_string_array(&schema, "required_user_workflow_corpus_keys") {
        assert!(
            user_workflow_corpus.get(key).is_some(),
            "user_workflow_corpus missing key `{key}`"
        );
    }
    let golden_journey_ids = user_workflow_corpus["golden_journey_ids"]
        .as_array()
        .expect("user_workflow_corpus.golden_journey_ids should be array")
        .iter()
        .map(|value| {
            value
                .as_str()
                .expect("golden_journey_ids entry should be string")
                .to_owned()
        })
        .collect::<BTreeSet<_>>();
    assert_eq!(
        golden_journey_ids, journey_ids,
        "user_workflow_corpus.golden_journey_ids should exactly match journey IDs"
    );
    let workflow_required_categories = user_workflow_corpus["required_categories"]
        .as_array()
        .expect("user_workflow_corpus.required_categories should be array")
        .iter()
        .map(|value| {
            value
                .as_str()
                .expect("required_categories entry should be string")
                .to_owned()
        })
        .collect::<BTreeSet<_>>();
    assert_eq!(
        workflow_required_categories, required_workflow_categories,
        "user_workflow_corpus.required_categories drifted from schema"
    );
    let scenario_log_report_path = user_workflow_corpus["scenario_log_report"]
        .as_str()
        .expect("user_workflow_corpus.scenario_log_report should be string");
    assert_path(
        scenario_log_report_path,
        "user_workflow_corpus.scenario_log_report",
        &root,
    );

    let journey_coverage_hooks = artifact["journey_coverage_hooks"]
        .as_array()
        .expect("journey_coverage_hooks should be array");
    assert_eq!(
        journey_coverage_hooks.len(),
        journeys.len(),
        "journey_coverage_hooks should have one entry per journey"
    );
    let required_journey_coverage_hook_keys =
        required_string_array(&schema, "required_journey_coverage_hook_keys");
    let required_hook_entry_keys = required_string_array(&schema, "required_hook_entry_keys");

    let mut mapped_hook_journey_ids = BTreeSet::new();
    let mut mapped_hook_scenario_ids = BTreeSet::new();
    let mut observed_hook_categories = BTreeSet::new();
    let mut observed_hook_report_refs = BTreeSet::new();

    for (hook_idx, hook) in journey_coverage_hooks.iter().enumerate() {
        for key in &required_journey_coverage_hook_keys {
            assert!(
                hook.get(*key).is_some(),
                "journey_coverage_hooks[{hook_idx}] missing key `{key}`"
            );
        }
        let journey_id = hook["journey_id"]
            .as_str()
            .expect("journey_coverage_hooks[].journey_id should be string");
        assert!(
            journey_ids.contains(journey_id),
            "journey_coverage_hooks[{hook_idx}] references unknown journey_id {journey_id}"
        );
        assert!(
            mapped_hook_journey_ids.insert(journey_id.to_owned()),
            "duplicate journey_id in journey_coverage_hooks: {journey_id}"
        );

        let scenario_id = hook["scenario_id"]
            .as_str()
            .expect("journey_coverage_hooks[].scenario_id should be string");
        assert!(
            !scenario_id.trim().is_empty(),
            "journey_coverage_hooks[{hook_idx}].scenario_id should be non-empty"
        );
        assert!(
            scenario_id.starts_with("WF-"),
            "journey_coverage_hooks[{hook_idx}].scenario_id should start with WF-"
        );
        assert!(
            scenario_id
                .chars()
                .all(|c| c.is_ascii_uppercase() || c.is_ascii_digit() || c == '-'),
            "journey_coverage_hooks[{hook_idx}].scenario_id should be stable ASCII token format"
        );
        assert!(
            mapped_hook_scenario_ids.insert(scenario_id.to_owned()),
            "duplicate scenario_id in journey_coverage_hooks: {scenario_id}"
        );

        let category = hook["category"]
            .as_str()
            .expect("journey_coverage_hooks[].category should be string");
        assert!(
            required_workflow_categories.contains(category),
            "journey_coverage_hooks[{hook_idx}] category `{category}` outside required set"
        );
        observed_hook_categories.insert(category.to_owned());

        for hook_set_key in ["unit_hooks", "differential_hooks", "e2e_hooks"] {
            let hook_set = hook[hook_set_key].as_array().unwrap_or_else(|| {
                panic!("journey_coverage_hooks[{hook_idx}].{hook_set_key} should be array")
            });
            assert!(
                !hook_set.is_empty(),
                "journey_coverage_hooks[{hook_idx}].{hook_set_key} should be non-empty"
            );
            for (entry_idx, entry) in hook_set.iter().enumerate() {
                for key in &required_hook_entry_keys {
                    assert!(
                        entry.get(*key).is_some(),
                        "journey_coverage_hooks[{hook_idx}].{hook_set_key}[{entry_idx}] missing key `{key}`"
                    );
                }
                let hook_id = entry["hook_id"]
                    .as_str()
                    .expect("hook entry hook_id should be string");
                assert!(
                    !hook_id.trim().is_empty(),
                    "journey_coverage_hooks[{hook_idx}].{hook_set_key}[{entry_idx}].hook_id should be non-empty"
                );
                let command = entry["command"]
                    .as_str()
                    .expect("hook entry command should be string");
                assert!(
                    !command.trim().is_empty(),
                    "journey_coverage_hooks[{hook_idx}].{hook_set_key}[{entry_idx}].command should be non-empty"
                );
                assert!(
                    command.contains("rch exec --"),
                    "journey_coverage_hooks[{hook_idx}].{hook_set_key}[{entry_idx}] command should use rch offload"
                );
                let artifact_ref = entry["artifact_ref"]
                    .as_str()
                    .expect("hook entry artifact_ref should be string");
                assert_path(
                    artifact_ref,
                    &format!(
                        "journey_coverage_hooks[{hook_idx}].{hook_set_key}[{entry_idx}].artifact_ref"
                    ),
                    &root,
                );
            }
        }

        let report_refs = hook["report_refs"]
            .as_array()
            .expect("journey_coverage_hooks[].report_refs should be array");
        assert!(
            !report_refs.is_empty(),
            "journey_coverage_hooks[{hook_idx}].report_refs should be non-empty"
        );
        for (report_idx, report_ref) in report_refs.iter().enumerate() {
            let report_ref = report_ref.as_str().unwrap_or_else(|| {
                panic!(
                    "journey_coverage_hooks[{hook_idx}].report_refs[{report_idx}] should be string"
                )
            });
            assert_path(
                report_ref,
                &format!("journey_coverage_hooks[{hook_idx}].report_refs[{report_idx}]"),
                &root,
            );
            observed_hook_report_refs.insert(report_ref.to_owned());
        }
    }
    assert_eq!(
        mapped_hook_journey_ids, journey_ids,
        "journey_coverage_hooks journey coverage must be complete"
    );
    assert_eq!(
        observed_hook_categories, required_workflow_categories,
        "journey_coverage_hooks categories must cover required workflow categories"
    );
    assert!(
        observed_hook_report_refs.contains(scenario_log_report_path),
        "scenario_log_report should be referenced by journey_coverage_hooks.report_refs"
    );

    let scenario_log_report = load_json(&root.join(scenario_log_report_path));
    let scenario_log_report_obj = scenario_log_report
        .as_object()
        .expect("scenario_log_report should be object");
    for key in [
        "schema_version",
        "report_id",
        "generated_at_utc",
        "source_matrix_contract",
        "source_matrix_report",
        "source_steps_log",
        "scenario_records",
    ] {
        assert!(
            scenario_log_report_obj.get(key).is_some(),
            "scenario_log_report missing key `{key}`"
        );
    }
    let source_matrix_contract = scenario_log_report["source_matrix_contract"]
        .as_str()
        .expect("scenario_log_report.source_matrix_contract should be string");
    assert_path(
        source_matrix_contract,
        "scenario_log_report.source_matrix_contract",
        &root,
    );
    let source_matrix_report = scenario_log_report["source_matrix_report"]
        .as_str()
        .expect("scenario_log_report.source_matrix_report should be string");
    assert_path(
        source_matrix_report,
        "scenario_log_report.source_matrix_report",
        &root,
    );
    let source_steps_log = scenario_log_report["source_steps_log"]
        .as_str()
        .expect("scenario_log_report.source_steps_log should be string");
    assert_path(
        source_steps_log,
        "scenario_log_report.source_steps_log",
        &root,
    );

    let matrix_report = load_json(&root.join(source_matrix_report));
    let matrix_report_scenario_ids = matrix_report["scenario_ids"]
        .as_array()
        .expect("matrix report scenario_ids should be array")
        .iter()
        .map(|value| {
            value
                .as_str()
                .expect("matrix report scenario_id entry should be string")
                .to_owned()
        })
        .collect::<BTreeSet<_>>();
    assert_eq!(
        matrix_report_scenario_ids, mapped_hook_scenario_ids,
        "matrix report scenario_ids should match journey_coverage_hooks scenario IDs"
    );
    assert_eq!(
        matrix_report["scenario_report_path"]
            .as_str()
            .expect("matrix report scenario_report_path should be string"),
        scenario_log_report_path,
        "matrix report should point to scenario log report"
    );
    assert_path(
        matrix_report["steps_log_path"]
            .as_str()
            .expect("matrix report steps_log_path should be string"),
        "matrix report steps_log_path",
        &root,
    );

    let scenario_records = scenario_log_report["scenario_records"]
        .as_array()
        .expect("scenario_log_report.scenario_records should be array");
    assert_eq!(
        scenario_records.len(),
        mapped_hook_scenario_ids.len(),
        "scenario_log_report should contain one record per scenario"
    );
    let mut scenario_report_ids = BTreeSet::new();
    for (record_idx, record) in scenario_records.iter().enumerate() {
        for key in ["scenario_id", "journey_id", "category", "report_refs"] {
            assert!(
                record.get(key).is_some(),
                "scenario_records[{record_idx}] missing key `{key}`"
            );
        }
        let scenario_id = record["scenario_id"]
            .as_str()
            .expect("scenario_records[].scenario_id should be string");
        assert!(
            mapped_hook_scenario_ids.contains(scenario_id),
            "scenario_records[{record_idx}] unknown scenario_id {scenario_id}"
        );
        assert!(
            scenario_report_ids.insert(scenario_id.to_owned()),
            "scenario_records duplicate scenario_id {scenario_id}"
        );
        let journey_id = record["journey_id"]
            .as_str()
            .expect("scenario_records[].journey_id should be string");
        assert!(
            journey_ids.contains(journey_id),
            "scenario_records[{record_idx}] unknown journey_id {journey_id}"
        );
        let category = record["category"]
            .as_str()
            .expect("scenario_records[].category should be string");
        assert!(
            required_workflow_categories.contains(category),
            "scenario_records[{record_idx}] category `{category}` outside required set"
        );
        let report_refs = record["report_refs"]
            .as_array()
            .expect("scenario_records[].report_refs should be array");
        assert!(
            !report_refs.is_empty(),
            "scenario_records[{record_idx}].report_refs should be non-empty"
        );
        for (ref_idx, report_ref) in report_refs.iter().enumerate() {
            let report_ref = report_ref.as_str().unwrap_or_else(|| {
                panic!("scenario_records[{record_idx}].report_refs[{ref_idx}] should be string")
            });
            assert_path(
                report_ref,
                &format!("scenario_records[{record_idx}].report_refs[{ref_idx}]"),
                &root,
            );
        }
    }
    assert_eq!(
        scenario_report_ids, mapped_hook_scenario_ids,
        "scenario_log_report scenario records should cover all scenario IDs"
    );

    assert_eq!(
        artifact["journey_summary"]["journey_count"]
            .as_u64()
            .expect("journey_count should be numeric"),
        journeys.len() as u64
    );
    assert_eq!(
        artifact["journey_summary"]["fixture_inventory_count"]
            .as_u64()
            .expect("fixture_inventory_count should be numeric"),
        fixture_inventory.len() as u64
    );

    let replay_contract = artifact["replay_metadata_contract"]
        .as_object()
        .expect("replay_metadata_contract should be object");
    for key in required_string_array(&schema, "required_replay_contract_keys") {
        assert!(
            replay_contract.get(key).is_some(),
            "replay metadata contract missing key `{key}`"
        );
    }
    let schema_refs = replay_contract["schema_refs"]
        .as_array()
        .expect("replay_metadata_contract.schema_refs should be array");
    for required_ref in required_string_array(&schema, "required_replay_schema_refs") {
        assert!(
            schema_refs
                .iter()
                .any(|value| value.as_str() == Some(required_ref)),
            "replay metadata contract missing schema ref {required_ref}"
        );
    }
    for schema_ref in schema_refs {
        assert_path(
            schema_ref.as_str().expect("schema_ref should be string"),
            "replay schema ref",
            &root,
        );
    }

    let profile = artifact["profile_first_artifacts"]
        .as_object()
        .expect("profile_first_artifacts should be object");
    for key in required_string_array(&schema, "required_profile_artifact_keys") {
        assert_path(
            profile[key]
                .as_str()
                .expect("profile artifact path should be string"),
            &format!("profile_first_artifacts.{key}"),
            &root,
        );
    }

    let ev_score = artifact["alien_uplift_contract_card"]["ev_score"]
        .as_f64()
        .expect("ev_score should be numeric");
    assert!(ev_score >= 2.0, "ev_score should be >= 2.0");
}
