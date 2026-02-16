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

fn required_string_array(schema: &Value, key: &str) -> Vec<String> {
    schema[key]
        .as_array()
        .unwrap_or_else(|| panic!("schema.{key} should be array"))
        .iter()
        .map(|value| {
            value
                .as_str()
                .unwrap_or_else(|| panic!("schema.{key} entries should be strings"))
                .to_owned()
        })
        .collect()
}

fn collect_string_set(values: &Value, ctx: &str) -> BTreeSet<String> {
    values
        .as_array()
        .unwrap_or_else(|| panic!("{ctx} should be array"))
        .iter()
        .map(|value| {
            value
                .as_str()
                .unwrap_or_else(|| panic!("{ctx} entries should be strings"))
                .to_owned()
        })
        .collect()
}

fn assert_path_exists(root: &Path, rel: &str, ctx: &str) {
    assert!(!rel.trim().is_empty(), "{ctx} should be non-empty path");
    let path = root.join(rel);
    assert!(path.exists(), "{ctx} missing path `{}`", path.display());
}

#[test]
fn ci_gate_topology_contract_is_complete_and_fail_closed() {
    let root = repo_root();
    let schema =
        load_json(&root.join("artifacts/conformance/schema/v1/ci_gate_topology_schema_v1.json"));
    let artifact = load_json(&root.join("artifacts/conformance/v1/ci_gate_topology_v1.json"));

    for key in required_string_array(&schema, "required_top_level_keys") {
        assert!(
            artifact.get(&key).is_some(),
            "ci gate topology artifact missing top-level key `{key}`"
        );
    }
    assert_eq!(
        artifact["source_bead_id"].as_str(),
        Some("bd-315.10.1"),
        "ci gate topology artifact must track bead ownership"
    );

    let required_gate_ids = required_string_array(&schema, "required_gate_ids");
    let gate_order = artifact["gate_order"]
        .as_array()
        .expect("artifact.gate_order should be array")
        .iter()
        .map(|value| {
            value
                .as_str()
                .expect("artifact.gate_order entries should be strings")
                .to_owned()
        })
        .collect::<Vec<_>>();
    assert_eq!(
        gate_order, required_gate_ids,
        "gate order drifted from schema lock"
    );

    let short_circuit = artifact["short_circuit"]
        .as_object()
        .expect("artifact.short_circuit should be object");
    for key in required_string_array(&schema, "required_short_circuit_keys") {
        assert!(
            short_circuit.contains_key(&key),
            "artifact.short_circuit missing `{key}`"
        );
    }
    assert_eq!(
        short_circuit["enabled"].as_bool(),
        Some(true),
        "short_circuit.enabled must be true"
    );
    assert_eq!(
        short_circuit["stop_after_first_failure"].as_bool(),
        Some(true),
        "short_circuit.stop_after_first_failure must be true"
    );
    let short_circuit_policy = short_circuit["policy_id"]
        .as_str()
        .expect("short_circuit.policy_id should be string")
        .to_owned();

    let allowed_policy_domains = required_string_array(&schema, "allowed_policy_domains")
        .into_iter()
        .collect::<BTreeSet<_>>();
    let required_policy_keys = required_string_array(&schema, "required_policy_keys");
    let policies = artifact["policies"]
        .as_array()
        .expect("artifact.policies should be array");
    assert!(
        !policies.is_empty(),
        "artifact.policies should be non-empty"
    );

    let mut policy_ids = BTreeSet::new();
    for (idx, policy) in policies.iter().enumerate() {
        let object = policy
            .as_object()
            .unwrap_or_else(|| panic!("artifact.policies[{idx}] should be object"));
        for key in &required_policy_keys {
            assert!(
                object.contains_key(key),
                "artifact.policies[{idx}] missing `{key}`"
            );
        }
        let policy_id = object["policy_id"]
            .as_str()
            .expect("policy_id should be string");
        assert!(
            policy_ids.insert(policy_id.to_owned()),
            "duplicate policy_id `{policy_id}`"
        );
        let domain = object["domain"]
            .as_str()
            .expect("policy domain should be string");
        assert!(
            allowed_policy_domains.contains(domain),
            "artifact.policies[{idx}].domain `{domain}` not allowed by schema"
        );
        assert_eq!(
            object["deterministic"].as_bool(),
            Some(true),
            "artifact.policies[{idx}] must be deterministic"
        );
    }
    assert!(
        policy_ids.contains(&short_circuit_policy),
        "short-circuit policy `{short_circuit_policy}` missing from policy registry"
    );

    let required_drift_keys = required_string_array(&schema, "required_drift_rule_keys");
    let required_drift_ids = required_string_array(&schema, "required_drift_rule_ids")
        .into_iter()
        .collect::<BTreeSet<_>>();
    let drift_rules = artifact["drift_rules"]
        .as_array()
        .expect("artifact.drift_rules should be array");
    assert!(
        !drift_rules.is_empty(),
        "artifact.drift_rules should be non-empty"
    );

    let mut observed_drift_ids = BTreeSet::new();
    for (idx, rule) in drift_rules.iter().enumerate() {
        let object = rule
            .as_object()
            .unwrap_or_else(|| panic!("artifact.drift_rules[{idx}] should be object"));
        for key in &required_drift_keys {
            assert!(
                object.contains_key(key),
                "artifact.drift_rules[{idx}] missing `{key}`"
            );
        }
        let rule_id = object["rule_id"]
            .as_str()
            .expect("drift rule_id should be string");
        assert!(
            observed_drift_ids.insert(rule_id.to_owned()),
            "duplicate drift rule_id `{rule_id}`"
        );
        let policy_id = object["policy_id"]
            .as_str()
            .expect("drift policy_id should be string");
        assert!(
            policy_ids.contains(policy_id),
            "drift rule `{rule_id}` references unknown policy `{policy_id}`"
        );
    }
    assert_eq!(
        observed_drift_ids, required_drift_ids,
        "drift-rule registry drifted from schema lock"
    );

    let required_gate_keys = required_string_array(&schema, "required_gate_keys");
    let required_input_keys = required_string_array(&schema, "required_input_contract_keys");
    let required_output_keys = required_string_array(&schema, "required_output_artifact_keys");
    let gates = artifact["gates"]
        .as_array()
        .expect("artifact.gates should be array");
    assert_eq!(
        gates.len(),
        gate_order.len(),
        "artifact.gates length should match gate_order"
    );

    let mut observed_gate_ids = BTreeSet::new();
    let mut input_ids_by_gate: BTreeMap<String, BTreeSet<String>> = BTreeMap::new();
    let mut output_ids_by_gate: BTreeMap<String, BTreeSet<String>> = BTreeMap::new();

    for (idx, gate) in gates.iter().enumerate() {
        let object = gate
            .as_object()
            .unwrap_or_else(|| panic!("artifact.gates[{idx}] should be object"));
        for key in &required_gate_keys {
            assert!(
                object.contains_key(key),
                "artifact.gates[{idx}] missing `{key}`"
            );
        }

        let gate_id = object["gate_id"]
            .as_str()
            .expect("gate_id should be string")
            .to_owned();
        assert_eq!(
            gate_id, gate_order[idx],
            "gate list order should match gate_order"
        );
        assert!(
            observed_gate_ids.insert(gate_id.clone()),
            "duplicate gate_id `{gate_id}`"
        );
        assert_eq!(
            object["blocking"].as_bool(),
            Some(true),
            "{gate_id} must be blocking"
        );
        assert_eq!(
            object["short_circuit_on_fail"].as_bool(),
            Some(true),
            "{gate_id} must short-circuit on failure"
        );
        assert_eq!(
            object["owner_bead_id"].as_str(),
            Some("bd-315.10.1"),
            "{gate_id} owner_bead_id must remain pinned"
        );

        let expected_dependencies = if idx == 0 {
            Vec::new()
        } else {
            vec![gate_order[idx - 1].clone()]
        };
        let dependencies = object["depends_on"]
            .as_array()
            .expect("depends_on should be array")
            .iter()
            .map(|value| {
                value
                    .as_str()
                    .expect("depends_on entries should be strings")
            })
            .map(str::to_owned)
            .collect::<Vec<_>>();
        assert_eq!(
            dependencies, expected_dependencies,
            "{gate_id} dependency order drifted"
        );

        let fail_closed_policy_ids = collect_string_set(
            &object["fail_closed_policy_ids"],
            &format!("{gate_id}.fail_closed_policy_ids"),
        );
        assert!(
            !fail_closed_policy_ids.is_empty(),
            "{gate_id}.fail_closed_policy_ids should be non-empty"
        );
        for policy_id in &fail_closed_policy_ids {
            assert!(
                policy_ids.contains(policy_id),
                "{gate_id} references unknown fail_closed policy `{policy_id}`"
            );
        }

        let drift_rule_ids = collect_string_set(
            &object["drift_rule_ids"],
            &format!("{gate_id}.drift_rule_ids"),
        );
        assert!(
            !drift_rule_ids.is_empty(),
            "{gate_id}.drift_rule_ids should be non-empty"
        );
        for rule_id in &drift_rule_ids {
            assert!(
                observed_drift_ids.contains(rule_id),
                "{gate_id} references unknown drift rule `{rule_id}`"
            );
        }

        for command_key in ["primary_commands", "replay_commands"] {
            let commands = object[command_key]
                .as_array()
                .unwrap_or_else(|| panic!("{gate_id}.{command_key} should be array"));
            assert!(
                !commands.is_empty(),
                "{gate_id}.{command_key} should be non-empty"
            );
            for (cmd_idx, command) in commands.iter().enumerate() {
                let command = command.as_str().unwrap_or_else(|| {
                    panic!("{gate_id}.{command_key}[{cmd_idx}] should be string")
                });
                assert!(
                    !command.trim().is_empty(),
                    "{gate_id}.{command_key}[{cmd_idx}] should be non-empty"
                );
                if command.contains("cargo ") {
                    assert!(
                        command.contains("rch exec --"),
                        "{gate_id}.{command_key}[{cmd_idx}] cargo command must be offloaded via rch"
                    );
                }
            }
        }

        let input_contracts = object["input_contracts"]
            .as_array()
            .expect("input_contracts should be array");
        assert!(
            !input_contracts.is_empty(),
            "{gate_id}.input_contracts should be non-empty"
        );
        let mut input_ids = BTreeSet::new();
        for (input_idx, input) in input_contracts.iter().enumerate() {
            let input_object = input.as_object().unwrap_or_else(|| {
                panic!("{gate_id}.input_contracts[{input_idx}] should be object")
            });
            for key in &required_input_keys {
                assert!(
                    input_object.contains_key(key),
                    "{gate_id}.input_contracts[{input_idx}] missing `{key}`"
                );
            }
            let input_id = input_object["contract_id"]
                .as_str()
                .expect("contract_id should be string");
            assert!(
                input_ids.insert(input_id.to_owned()),
                "{gate_id} duplicate input contract `{input_id}`"
            );

            let required_paths = input_object["required_paths"]
                .as_array()
                .expect("required_paths should be array");
            assert!(
                !required_paths.is_empty(),
                "{gate_id}.input_contracts[{input_idx}].required_paths should be non-empty"
            );
            for (path_idx, value) in required_paths.iter().enumerate() {
                let rel = value.as_str().unwrap_or_else(|| {
                    panic!("{gate_id}.input_contracts[{input_idx}].required_paths[{path_idx}] should be string")
                });
                assert_path_exists(
                    root.as_path(),
                    rel,
                    &format!("{gate_id}.input_contracts[{input_idx}].required_paths[{path_idx}]"),
                );
            }
        }
        input_ids_by_gate.insert(gate_id.clone(), input_ids);

        let output_artifacts = object["output_artifacts"]
            .as_array()
            .expect("output_artifacts should be array");
        assert!(
            !output_artifacts.is_empty(),
            "{gate_id}.output_artifacts should be non-empty"
        );
        let mut output_ids = BTreeSet::new();
        for (output_idx, output) in output_artifacts.iter().enumerate() {
            let output_object = output.as_object().unwrap_or_else(|| {
                panic!("{gate_id}.output_artifacts[{output_idx}] should be object")
            });
            for key in &required_output_keys {
                assert!(
                    output_object.contains_key(key),
                    "{gate_id}.output_artifacts[{output_idx}] missing `{key}`"
                );
            }
            let output_id = output_object["artifact_id"]
                .as_str()
                .expect("artifact_id should be string");
            assert!(
                output_ids.insert(output_id.to_owned()),
                "{gate_id} duplicate output artifact `{output_id}`"
            );
            let path = output_object["path"].as_str().unwrap_or_else(|| {
                panic!("{gate_id}.output_artifacts[{output_idx}].path should be string")
            });
            assert_path_exists(
                root.as_path(),
                path,
                &format!("{gate_id}.output_artifacts[{output_idx}].path"),
            );
        }
        output_ids_by_gate.insert(gate_id, output_ids);
    }

    let expected_gate_ids = gate_order.into_iter().collect::<BTreeSet<_>>();
    assert_eq!(
        observed_gate_ids, expected_gate_ids,
        "observed gate coverage drifted from locked gate set"
    );

    let required_io_keys = required_string_array(&schema, "required_io_matrix_keys");
    let io_matrix = artifact["io_contract_matrix"]
        .as_array()
        .expect("artifact.io_contract_matrix should be array");
    assert_eq!(
        io_matrix.len(),
        observed_gate_ids.len(),
        "io_contract_matrix should have one row per gate"
    );

    let mut io_gate_ids = BTreeSet::new();
    for (idx, row) in io_matrix.iter().enumerate() {
        let object = row
            .as_object()
            .unwrap_or_else(|| panic!("io_contract_matrix[{idx}] should be object"));
        for key in &required_io_keys {
            assert!(
                object.contains_key(key),
                "io_contract_matrix[{idx}] missing `{key}`"
            );
        }

        let gate_id = object["gate_id"]
            .as_str()
            .expect("io gate_id should be string")
            .to_owned();
        assert!(
            io_gate_ids.insert(gate_id.clone()),
            "duplicate io row for `{gate_id}`"
        );
        assert_eq!(
            object["owner_bead_id"].as_str(),
            Some("bd-315.10.1"),
            "io row owner_bead_id must remain pinned"
        );

        let envelope_policy = object["failure_envelope_policy_id"]
            .as_str()
            .expect("failure_envelope_policy_id should be string");
        assert!(
            policy_ids.contains(envelope_policy),
            "io row `{gate_id}` references unknown envelope policy `{envelope_policy}`"
        );

        let expected_input_ids = input_ids_by_gate
            .get(&gate_id)
            .unwrap_or_else(|| panic!("io row `{gate_id}` references unknown gate"));
        let expected_output_ids = output_ids_by_gate
            .get(&gate_id)
            .unwrap_or_else(|| panic!("io row `{gate_id}` references unknown gate"));
        let input_ids = collect_string_set(
            &object["input_contract_ids"],
            &format!("io_contract_matrix[{idx}].input_contract_ids"),
        );
        let output_ids = collect_string_set(
            &object["output_artifact_ids"],
            &format!("io_contract_matrix[{idx}].output_artifact_ids"),
        );
        assert_eq!(
            input_ids, *expected_input_ids,
            "io row `{gate_id}` input contract IDs drifted from gate declaration"
        );
        assert_eq!(
            output_ids, *expected_output_ids,
            "io row `{gate_id}` output artifact IDs drifted from gate declaration"
        );
    }

    assert_eq!(
        io_gate_ids, observed_gate_ids,
        "io matrix gate coverage drifted from gate registry"
    );
}
