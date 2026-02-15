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

fn top_level_yaml_keys(text: &str) -> BTreeSet<String> {
    text.lines()
        .filter_map(|raw| {
            let line = raw.trim_end();
            if line.is_empty() || line.trim_start().starts_with('#') {
                return None;
            }
            if line.starts_with(' ') || line.starts_with('\t') || !line.contains(':') {
                return None;
            }
            Some(line.split(':').next().unwrap_or("").trim().to_owned())
        })
        .filter(|key| !key.is_empty())
        .collect()
}

fn expected_packet_ids() -> BTreeSet<&'static str> {
    BTreeSet::from([
        "FNX-P2C-FOUNDATION",
        "FNX-P2C-001",
        "FNX-P2C-002",
        "FNX-P2C-003",
        "FNX-P2C-004",
        "FNX-P2C-005",
        "FNX-P2C-006",
        "FNX-P2C-007",
        "FNX-P2C-008",
        "FNX-P2C-009",
    ])
}

#[test]
fn topology_and_packet_artifacts_are_complete_and_decode_proof_enforced() {
    let root = repo_root();
    let topology = load_json(&root.join("artifacts/phase2c/packet_topology_v1.json"));
    let contract =
        load_json(&root.join("artifacts/phase2c/schema/v1/artifact_contract_schema_v1.json"));

    let contract_artifacts = contract["artifacts"]
        .as_object()
        .expect("contract artifacts should be an object");
    let required_artifact_keys = contract["required_artifact_keys"]
        .as_array()
        .expect("required_artifact_keys must be array")
        .iter()
        .map(|value| value.as_str().expect("artifact key must be string"))
        .collect::<Vec<_>>();
    assert!(
        required_artifact_keys.contains(&"decode_proof"),
        "decode proof artifact must be required by contract"
    );

    let packets = topology["packets"]
        .as_array()
        .expect("topology packets should be an array");
    let observed_packet_ids = packets
        .iter()
        .map(|packet| {
            packet["packet_id"]
                .as_str()
                .expect("packet_id should be string")
        })
        .collect::<BTreeSet<_>>();
    assert_eq!(
        observed_packet_ids,
        expected_packet_ids(),
        "phase2c topology packet set drifted"
    );

    for packet in packets {
        let packet_id = packet["packet_id"]
            .as_str()
            .expect("packet_id should be string");
        let packet_path = root.join(
            packet["path"]
                .as_str()
                .expect("packet path should be string"),
        );
        assert!(
            packet_path.is_dir(),
            "packet directory missing for {packet_id}: {}",
            packet_path.display()
        );

        let packet_required = packet["required_artifact_keys"]
            .as_array()
            .expect("packet required artifact keys should be array")
            .iter()
            .map(|value| {
                value
                    .as_str()
                    .expect("required artifact key should be string")
            })
            .collect::<Vec<_>>();
        assert_eq!(
            packet_required, required_artifact_keys,
            "packet {packet_id} required artifact keys drifted from contract"
        );

        for artifact_key in &packet_required {
            let spec = contract_artifacts
                .get(*artifact_key)
                .unwrap_or_else(|| panic!("unknown artifact key `{artifact_key}` in contract"));
            let filename = spec["filename"]
                .as_str()
                .expect("artifact filename should be string");
            let kind = spec["kind"]
                .as_str()
                .expect("artifact kind should be string");
            let artifact_path = packet_path.join(filename);
            assert!(
                artifact_path.exists(),
                "packet {packet_id} missing artifact {filename}"
            );

            match kind {
                "markdown_sections" => {
                    let content = fs::read_to_string(&artifact_path)
                        .expect("markdown artifact should be readable");
                    for section in spec["required_sections"]
                        .as_array()
                        .expect("required_sections should be array")
                    {
                        let section_name = section
                            .as_str()
                            .expect("required section name should be string");
                        let marker = format!("## {section_name}");
                        assert!(
                            content.contains(&marker),
                            "packet {packet_id} artifact {filename} missing section `{section_name}`"
                        );
                    }
                }
                "json_keys" => {
                    let payload = load_json(&artifact_path);
                    for key in spec["required_keys"]
                        .as_array()
                        .expect("required_keys should be array")
                    {
                        let key_name = key.as_str().expect("required key should be string");
                        assert!(
                            payload.get(key_name).is_some(),
                            "packet {packet_id} artifact {filename} missing key `{key_name}`"
                        );
                    }
                }
                "yaml_keys" => {
                    let content = fs::read_to_string(&artifact_path)
                        .expect("yaml artifact should be readable");
                    let keys = top_level_yaml_keys(&content);
                    for key in spec["required_keys"]
                        .as_array()
                        .expect("required_keys should be array")
                    {
                        let key_name = key.as_str().expect("required key should be string");
                        assert!(
                            keys.contains(key_name),
                            "packet {packet_id} artifact {filename} missing yaml key `{key_name}`"
                        );
                    }
                }
                other => panic!("unsupported artifact kind in contract: {other}"),
            }
        }
    }
}

#[test]
fn essence_ledger_is_machine_auditable_and_cross_linked() {
    let root = repo_root();
    let ledger = load_json(&root.join("artifacts/phase2c/essence_extraction_ledger_v1.json"));
    let schema = load_json(
        &root.join("artifacts/phase2c/schema/v1/essence_extraction_ledger_schema_v1.json"),
    );
    let security_contract = load_json(
        &root.join("artifacts/phase2c/schema/v1/security_compatibility_contract_schema_v1.json"),
    );

    let packets = ledger["packets"]
        .as_array()
        .expect("ledger packets should be an array");
    let observed_packet_ids = packets
        .iter()
        .map(|entry| {
            entry["packet_id"]
                .as_str()
                .expect("ledger packet_id should be string")
        })
        .collect::<BTreeSet<_>>();
    assert_eq!(
        observed_packet_ids,
        expected_packet_ids(),
        "essence ledger packet coverage drifted"
    );

    let schema_packet_keys = schema["required_packet_keys"]
        .as_array()
        .expect("required_packet_keys should be array");
    for entry in packets {
        let packet_id = entry["packet_id"]
            .as_str()
            .expect("packet_id should be string");
        for key in schema_packet_keys {
            let key_name = key.as_str().expect("schema packet key should be string");
            assert!(
                entry.get(key_name).is_some(),
                "ledger packet {packet_id} missing required key `{key_name}`"
            );
        }

        let invariants = entry["invariants"]
            .as_array()
            .expect("invariants should be array");
        assert!(
            !invariants.is_empty(),
            "ledger packet {packet_id} should define at least one invariant"
        );
        for invariant in invariants {
            let hooks = invariant["verification_hooks"]
                .as_object()
                .expect("verification_hooks should be object");
            for hook_key in ["unit", "property", "differential", "adversarial", "e2e"] {
                let hook_values = hooks[hook_key]
                    .as_array()
                    .expect("verification hook should be array");
                assert!(
                    !hook_values.is_empty(),
                    "ledger packet {packet_id} invariant hook `{hook_key}` should be non-empty"
                );
            }
        }

        let ev_score = entry["alien_uplift_contract_card"]["ev_score"]
            .as_f64()
            .expect("ev_score should be numeric");
        assert!(
            ev_score >= 2.0,
            "ledger packet {packet_id} ev_score must be >= 2.0"
        );

        let raptorq_artifacts = entry["raptorq_artifacts"]
            .as_object()
            .expect("raptorq_artifacts should be object");
        for (key, path) in raptorq_artifacts {
            let path_value = path
                .as_str()
                .expect("raptorq artifact path should be string");
            let full_path = root.join(path_value);
            assert!(
                full_path.exists(),
                "ledger packet {packet_id} missing artifact path for {key}: {}",
                full_path.display()
            );
        }

        for path_key in ["baseline", "hotspot", "delta"] {
            let rel = entry["profile_first_artifacts"][path_key]
                .as_str()
                .expect("profile_first_artifacts path should be string");
            assert!(
                root.join(rel).exists(),
                "ledger packet {packet_id} missing profile artifact `{path_key}`: {rel}"
            );
        }

        for field in ["isomorphism_proof_artifacts", "structured_logging_evidence"] {
            let refs = entry[field]
                .as_array()
                .expect("path ref field should be array");
            assert!(
                !refs.is_empty(),
                "ledger packet {packet_id} field `{field}` should be non-empty"
            );
            for path in refs {
                let rel = path.as_str().expect("path ref should be string");
                assert!(
                    root.join(rel).exists(),
                    "ledger packet {packet_id} field `{field}` references missing path {rel}"
                );
            }
        }
    }

    let required_security_packets = security_contract["required_packet_ids"]
        .as_array()
        .expect("required_packet_ids should be an array")
        .iter()
        .map(|value| value.as_str().expect("packet id should be string"))
        .collect::<BTreeSet<_>>();
    for packet_id in required_security_packets {
        assert!(
            observed_packet_ids.contains(packet_id),
            "security contract packet {packet_id} missing in essence ledger"
        );
    }
}

#[test]
fn adversarial_manifest_is_complete_and_gate_linked() {
    let root = repo_root();
    let contract = load_json(
        &root.join("artifacts/phase2c/schema/v1/security_compatibility_contract_schema_v1.json"),
    );
    let matrix = load_json(
        &root.join("artifacts/phase2c/security/v1/security_compatibility_threat_matrix_v1.json"),
    );
    let manifest =
        load_json(&root.join("artifacts/phase2c/security/v1/adversarial_corpus_manifest_v1.json"));

    for key in contract["required_adversarial_manifest_keys"]
        .as_array()
        .expect("required_adversarial_manifest_keys must be array")
    {
        let key_name = key
            .as_str()
            .expect("required manifest key should be string");
        assert!(
            manifest.get(key_name).is_some(),
            "adversarial manifest missing key `{key_name}`"
        );
    }

    let seed_policy = manifest["seed_policy"]
        .as_object()
        .expect("manifest seed_policy must be an object");
    for key in contract["adversarial_manifest_seed_policy_required_keys"]
        .as_array()
        .expect("adversarial_manifest_seed_policy_required_keys must be array")
    {
        let key_name = key
            .as_str()
            .expect("seed policy required key should be string");
        assert!(
            seed_policy.contains_key(key_name),
            "adversarial manifest seed_policy missing key `{key_name}`"
        );
    }
    assert!(
        seed_policy
            .get("deterministic")
            .and_then(Value::as_bool)
            .expect("seed_policy.deterministic must be bool"),
        "seed_policy.deterministic must be true for reproducible replay"
    );

    let mut matrix_gate_by_pair: BTreeMap<(String, String), String> = BTreeMap::new();
    let mut matrix_classes = BTreeSet::new();
    for packet_row in matrix["packet_families"]
        .as_array()
        .expect("matrix packet_families should be array")
    {
        let packet_id = packet_row["packet_id"]
            .as_str()
            .expect("matrix packet_id should be string")
            .to_owned();
        for threat_row in packet_row["threats"]
            .as_array()
            .expect("matrix threats should be array")
        {
            let threat_class = threat_row["threat_class"]
                .as_str()
                .expect("matrix threat_class should be string")
                .to_owned();
            let drift_gate = threat_row["drift_gate"]
                .as_str()
                .expect("matrix drift_gate should be string")
                .to_owned();
            matrix_classes.insert(threat_class.clone());
            matrix_gate_by_pair.insert((packet_id.clone(), threat_class), drift_gate);
        }
    }

    let entry_required_keys = contract["adversarial_manifest_entry_required_keys"]
        .as_array()
        .expect("adversarial_manifest_entry_required_keys must be array");
    let mapping_required_keys = contract["adversarial_manifest_mapping_required_keys"]
        .as_array()
        .expect("adversarial_manifest_mapping_required_keys must be array");

    let mut manifest_classes = BTreeSet::new();
    let mut manifest_pairs = BTreeSet::new();
    for threat_row in manifest["threat_taxonomy"]
        .as_array()
        .expect("manifest threat_taxonomy should be array")
    {
        for key in entry_required_keys {
            let key_name = key.as_str().expect("entry required key should be string");
            assert!(
                threat_row.get(key_name).is_some(),
                "manifest threat row missing key `{key_name}`"
            );
        }

        let threat_class = threat_row["threat_class"]
            .as_str()
            .expect("manifest threat_class should be string")
            .to_owned();
        manifest_classes.insert(threat_class.clone());
        assert!(
            matrix_classes.contains(&threat_class),
            "manifest threat_class `{threat_class}` not present in security matrix"
        );

        let local_seed_policy = threat_row["seed_policy"]
            .as_object()
            .expect("manifest threat row seed_policy should be object");
        assert!(
            local_seed_policy
                .get("class_seed")
                .and_then(Value::as_u64)
                .is_some(),
            "manifest threat `{threat_class}` seed_policy.class_seed must be u64"
        );

        let mappings = threat_row["packet_gate_mappings"]
            .as_array()
            .expect("manifest packet_gate_mappings should be array");
        assert!(
            !mappings.is_empty(),
            "manifest threat `{threat_class}` must map to at least one packet gate"
        );
        for mapping in mappings {
            for key in mapping_required_keys {
                let key_name = key.as_str().expect("mapping required key should be string");
                assert!(
                    mapping.get(key_name).is_some(),
                    "manifest threat `{threat_class}` mapping missing key `{key_name}`"
                );
            }

            let packet_id = mapping["packet_id"]
                .as_str()
                .expect("mapping packet_id should be string")
                .to_owned();
            let gate = mapping["validation_gate"]
                .as_str()
                .expect("mapping validation_gate should be string")
                .to_owned();
            assert!(
                mapping["seed"].as_u64().is_some(),
                "manifest threat `{threat_class}` mapping `{packet_id}` seed must be u64"
            );

            let pair = (packet_id.clone(), threat_class.clone());
            manifest_pairs.insert(pair.clone());
            let expected_gate = matrix_gate_by_pair.get(&pair).unwrap_or_else(|| {
                panic!("manifest pair {:?} is not present in security matrix", pair)
            });
            assert_eq!(
                gate, *expected_gate,
                "manifest gate drift for packet `{packet_id}` and threat `{threat_class}`"
            );
        }
    }

    assert_eq!(
        manifest_classes, matrix_classes,
        "manifest threat class set drifted from security matrix"
    );

    let matrix_pairs: BTreeSet<(String, String)> = matrix_gate_by_pair.keys().cloned().collect();
    assert_eq!(
        manifest_pairs, matrix_pairs,
        "manifest packet/threat mapping set drifted from security matrix"
    );

    let required_high_risk = contract["required_high_risk_threat_classes"]
        .as_array()
        .expect("required_high_risk_threat_classes should be array")
        .iter()
        .map(|value| {
            value
                .as_str()
                .expect("required high-risk threat class should be string")
                .to_owned()
        })
        .collect::<BTreeSet<_>>();
    let manifest_high_risk = manifest["high_risk_classes"]
        .as_array()
        .expect("manifest high_risk_classes should be array")
        .iter()
        .map(|value| {
            value
                .as_str()
                .expect("manifest high-risk threat class should be string")
                .to_owned()
        })
        .collect::<BTreeSet<_>>();
    assert!(
        required_high_risk.is_subset(&manifest_high_risk),
        "manifest missing required high-risk classes"
    );
    assert!(
        required_high_risk.is_subset(&manifest_classes),
        "manifest high-risk classes must all have taxonomy entries"
    );
}

#[test]
fn adversarial_seed_ledger_is_deterministic_and_replayable() {
    let root = repo_root();
    let manifest =
        load_json(&root.join("artifacts/phase2c/security/v1/adversarial_corpus_manifest_v1.json"));
    let ledger =
        load_json(&root.join("artifacts/phase2c/security/v1/adversarial_seed_ledger_v1.json"));

    assert_eq!(
        ledger["schema_version"]
            .as_str()
            .expect("seed ledger schema_version should be string"),
        "1.0.0"
    );
    assert_eq!(
        ledger["ledger_id"]
            .as_str()
            .expect("seed ledger ledger_id should be string"),
        "adversarial-seed-ledger-v1"
    );
    assert_eq!(
        ledger["deterministic_seed_strategy"]
            .as_str()
            .expect("seed ledger deterministic_seed_strategy should be string"),
        "class_seed_plus_packet_offset"
    );

    let manifest_pairs = manifest["threat_taxonomy"]
        .as_array()
        .expect("manifest threat_taxonomy should be array")
        .iter()
        .flat_map(|threat_row| {
            let threat_class = threat_row["threat_class"]
                .as_str()
                .expect("manifest threat_class should be string")
                .to_owned();
            threat_row["packet_gate_mappings"]
                .as_array()
                .expect("manifest packet_gate_mappings should be array")
                .iter()
                .map(move |mapping| {
                    (
                        mapping["packet_id"]
                            .as_str()
                            .expect("manifest packet_id should be string")
                            .to_owned(),
                        threat_class.clone(),
                        mapping["validation_gate"]
                            .as_str()
                            .expect("manifest validation_gate should be string")
                            .to_owned(),
                        mapping["seed"]
                            .as_u64()
                            .expect("manifest mapping seed should be u64"),
                    )
                })
        })
        .collect::<BTreeSet<_>>();

    let entries = ledger["entries"]
        .as_array()
        .expect("seed ledger entries should be an array");
    assert_eq!(
        ledger["entry_count"]
            .as_u64()
            .expect("seed ledger entry_count should be u64") as usize,
        entries.len(),
        "seed ledger entry_count mismatch"
    );

    let mut ledger_pairs = BTreeSet::new();
    for entry in entries {
        for key in [
            "packet_id",
            "threat_class",
            "validation_gate",
            "generator_variant",
            "seed",
            "expected_failure_mode",
            "failure_classification",
            "fixture_hash_id",
            "replay_command",
            "shrink_metadata",
        ] {
            assert!(
                entry.get(key).is_some(),
                "seed ledger entry missing key `{key}`"
            );
        }

        let packet_id = entry["packet_id"]
            .as_str()
            .expect("seed ledger packet_id should be string")
            .to_owned();
        let threat_class = entry["threat_class"]
            .as_str()
            .expect("seed ledger threat_class should be string")
            .to_owned();
        let validation_gate = entry["validation_gate"]
            .as_str()
            .expect("seed ledger validation_gate should be string")
            .to_owned();
        let seed = entry["seed"]
            .as_u64()
            .expect("seed ledger seed should be u64");
        let fixture_hash_id = entry["fixture_hash_id"]
            .as_str()
            .expect("seed ledger fixture_hash_id should be string");
        let replay_command = entry["replay_command"]
            .as_str()
            .expect("seed ledger replay_command should be string");
        let classification = entry["failure_classification"]
            .as_str()
            .expect("seed ledger failure_classification should be string");

        assert!(
            !fixture_hash_id.is_empty(),
            "seed ledger fixture_hash_id must be non-empty"
        );
        assert!(
            replay_command.contains("--threat-class") && replay_command.contains("--packet-id"),
            "seed ledger replay_command must include deterministic replay selectors"
        );
        assert!(
            [
                "security",
                "compatibility",
                "determinism",
                "performance_tail",
                "memory_state_corruption"
            ]
            .contains(&classification),
            "seed ledger failure_classification `{classification}` is unsupported"
        );
        let shrink_metadata = entry["shrink_metadata"]
            .as_object()
            .expect("seed ledger shrink_metadata should be object");
        assert_eq!(
            shrink_metadata
                .get("strategy")
                .and_then(Value::as_str)
                .expect("seed ledger shrink_metadata.strategy should be string"),
            "delta_debug_fixed_seed"
        );
        assert!(
            shrink_metadata
                .get("minimized_counterexample_id")
                .and_then(Value::as_str)
                .expect("seed ledger shrink_metadata.minimized_counterexample_id should be string")
                .starts_with("min-"),
            "seed ledger shrink_metadata.minimized_counterexample_id should have `min-` prefix"
        );
        assert_eq!(
            shrink_metadata
                .get("shrink_steps")
                .and_then(Value::as_u64)
                .expect("seed ledger shrink_metadata.shrink_steps should be u64"),
            0
        );

        ledger_pairs.insert((packet_id, threat_class, validation_gate, seed));
    }

    assert_eq!(
        ledger_pairs, manifest_pairs,
        "seed ledger packet/threat/gate/seed coverage drifted from manifest"
    );

    let report =
        load_json(&root.join("artifacts/phase2c/latest/adversarial_seed_harness_report_v1.json"));
    assert_eq!(
        report["status"]
            .as_str()
            .expect("seed harness report status should be string"),
        "pass"
    );
    assert!(
        report["deterministic_replay_ready"]
            .as_bool()
            .expect("seed harness report deterministic_replay_ready should be bool"),
        "seed harness report must declare deterministic replay readiness"
    );

    let events_path =
        root.join("artifacts/phase2c/latest/adversarial_seed_harness_events_v1.jsonl");
    let events_raw =
        fs::read_to_string(&events_path).expect("seed harness events jsonl should be readable");
    let event_rows = events_raw
        .lines()
        .filter(|line| !line.trim().is_empty())
        .map(|line| {
            serde_json::from_str::<Value>(line)
                .expect("seed harness event row should be valid json")
        })
        .collect::<Vec<_>>();
    assert_eq!(
        event_rows.len(),
        report["event_count"]
            .as_u64()
            .expect("seed harness report event_count should be u64") as usize,
        "seed harness report event_count mismatch"
    );
    for event in event_rows {
        assert_eq!(
            event["status"]
                .as_str()
                .expect("seed harness event status should be string"),
            "replay_ready"
        );
        assert!(
            event["fixture_hash_id"]
                .as_str()
                .expect("seed harness event fixture_hash_id should be string")
                .len()
                >= 8,
            "seed harness event fixture_hash_id should look like a stable hash"
        );
    }
}
