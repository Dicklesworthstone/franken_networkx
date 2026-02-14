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
