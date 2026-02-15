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
fn performance_baseline_matrix_is_reproducible_and_complete() {
    let root = repo_root();
    let matrix = load_json(&root.join("artifacts/perf/phase2c/perf_baseline_matrix_v1.json"));

    for key in [
        "schema_version",
        "matrix_id",
        "measurement_protocol",
        "environment",
        "environment_fingerprint",
        "events_path",
        "scenario_count",
        "scenarios",
        "summary",
    ] {
        assert!(
            matrix.get(key).is_some(),
            "baseline matrix missing key `{key}`"
        );
    }

    let protocol = matrix["measurement_protocol"]
        .as_object()
        .expect("measurement_protocol should be object");
    let runs = protocol["runs"]
        .as_u64()
        .expect("measurement_protocol.runs should be u64");
    let warmup_runs = protocol["warmup_runs"]
        .as_u64()
        .expect("measurement_protocol.warmup_runs should be u64");
    assert!(runs >= 3, "measurement protocol runs should be >= 3");
    assert!(
        protocol["fixed_seed_policy"]
            .as_str()
            .expect("fixed_seed_policy should be string")
            .contains("seed"),
        "measurement protocol must document deterministic seed policy"
    );
    assert!(
        warmup_runs >= 1,
        "measurement protocol warmup_runs should be at least 1"
    );

    let scenarios = matrix["scenarios"]
        .as_array()
        .expect("scenarios should be array");
    assert_eq!(
        scenarios.len(),
        matrix["scenario_count"]
            .as_u64()
            .expect("scenario_count should be u64") as usize,
        "scenario_count should match scenario rows"
    );
    assert!(
        !scenarios.is_empty(),
        "scenarios should include representative topology matrix rows"
    );

    let mut topologies = BTreeSet::new();
    let mut size_buckets = BTreeSet::new();
    let mut density_classes = BTreeSet::new();
    let mut measurement_event_expectations = BTreeMap::new();
    for scenario in scenarios {
        for key in [
            "scenario_id",
            "topology",
            "size_bucket",
            "density_class",
            "seed",
            "command",
            "node_count",
            "edge_count_estimate",
            "density_estimate",
            "sample_count",
            "time_ms",
            "max_rss_kb",
        ] {
            assert!(
                scenario.get(key).is_some(),
                "scenario row missing key `{key}`"
            );
        }

        let topology = scenario["topology"]
            .as_str()
            .expect("scenario topology should be string");
        let size_bucket = scenario["size_bucket"]
            .as_str()
            .expect("scenario size_bucket should be string");
        let density_class = scenario["density_class"]
            .as_str()
            .expect("scenario density_class should be string");
        let command = scenario["command"]
            .as_str()
            .expect("scenario command should be string");
        let node_count = scenario["node_count"]
            .as_u64()
            .expect("scenario node_count should be u64");
        let sample_count = scenario["sample_count"]
            .as_u64()
            .expect("scenario sample_count should be u64") as usize;
        let density_estimate = scenario["density_estimate"]
            .as_f64()
            .expect("scenario density_estimate should be f64");
        assert!(
            command.contains("--topology") && command.contains("--seed"),
            "scenario command must carry deterministic topology/seed selectors"
        );
        assert!(node_count >= 2, "scenario node_count should be >= 2");
        assert_eq!(
            sample_count, runs as usize,
            "scenario sample_count should match measurement protocol runs"
        );
        assert!(
            (0.0..=1.0).contains(&density_estimate),
            "scenario density_estimate should be in [0.0, 1.0]"
        );

        let time_ms = scenario["time_ms"]
            .as_object()
            .expect("scenario time_ms should be object");
        let max_rss_kb = scenario["max_rss_kb"]
            .as_object()
            .expect("scenario max_rss_kb should be object");
        for key in ["mean", "p50", "p95", "p99", "min", "max"] {
            let time_value = time_ms[key]
                .as_f64()
                .unwrap_or_else(|| panic!("scenario time_ms.{key} should be f64"));
            let mem_value = max_rss_kb[key]
                .as_f64()
                .unwrap_or_else(|| panic!("scenario max_rss_kb.{key} should be f64"));
            assert!(
                time_value >= 0.0,
                "scenario time_ms.{key} must be non-negative"
            );
            assert!(
                mem_value >= 0.0,
                "scenario max_rss_kb.{key} must be non-negative"
            );
        }
        assert!(
            time_ms["p99"].as_f64().expect("time_ms.p99 should be f64")
                >= time_ms["p95"].as_f64().expect("time_ms.p95 should be f64")
                && time_ms["p95"].as_f64().expect("time_ms.p95 should be f64")
                    >= time_ms["p50"].as_f64().expect("time_ms.p50 should be f64"),
            "scenario runtime percentile ordering must be monotonic (p50 <= p95 <= p99)"
        );
        assert!(
            max_rss_kb["p99"]
                .as_f64()
                .expect("max_rss_kb.p99 should be f64")
                >= max_rss_kb["p95"]
                    .as_f64()
                    .expect("max_rss_kb.p95 should be f64")
                && max_rss_kb["p95"]
                    .as_f64()
                    .expect("max_rss_kb.p95 should be f64")
                    >= max_rss_kb["p50"]
                        .as_f64()
                        .expect("max_rss_kb.p50 should be f64"),
            "scenario memory percentile ordering must be monotonic (p50 <= p95 <= p99)"
        );

        topologies.insert(topology.to_owned());
        size_buckets.insert(size_bucket.to_owned());
        density_classes.insert(density_class.to_owned());
        measurement_event_expectations.insert(
            scenario["scenario_id"]
                .as_str()
                .expect("scenario_id should be string")
                .to_owned(),
            sample_count,
        );
    }

    assert_eq!(
        topologies,
        BTreeSet::from([
            "complete".to_owned(),
            "erdos_renyi".to_owned(),
            "grid".to_owned(),
            "line".to_owned(),
            "star".to_owned(),
        ]),
        "topology matrix coverage drifted"
    );
    assert!(
        size_buckets.contains("small")
            && size_buckets.contains("medium")
            && size_buckets.contains("large"),
        "size bucket coverage should include small/medium/large"
    );
    assert!(
        density_classes.len() >= 3,
        "density classes should include multiple representative classes"
    );

    let summary = matrix["summary"]
        .as_object()
        .expect("summary should be object");
    let summary_topologies = summary["topology_classes"]
        .as_array()
        .expect("summary.topology_classes should be array")
        .iter()
        .map(|entry| entry.as_str().expect("summary topology should be string"))
        .collect::<BTreeSet<_>>();
    assert_eq!(
        summary_topologies,
        BTreeSet::from(["complete", "erdos_renyi", "grid", "line", "star"]),
        "summary topology_classes drifted from scenario rows"
    );
    assert!(
        summary["max_p95_ms"]
            .as_f64()
            .expect("summary.max_p95_ms should be f64")
            >= 0.0
            && summary["max_memory_p95_kb"]
                .as_f64()
                .expect("summary.max_memory_p95_kb should be f64")
                >= 0.0,
        "summary performance/memory tails should be non-negative"
    );

    let environment = matrix["environment"]
        .as_object()
        .expect("environment should be object");
    for key in [
        "hostname",
        "os",
        "cpu_model",
        "python_version",
        "cargo_version",
        "rustc_version",
        "git_commit",
    ] {
        assert!(
            environment[key]
                .as_str()
                .unwrap_or_else(|| panic!("environment.{key} should be string"))
                .trim()
                .len()
                >= 4,
            "environment field `{key}` should be non-empty"
        );
    }
    let env_fingerprint = matrix["environment_fingerprint"]
        .as_str()
        .expect("environment_fingerprint should be string");
    assert!(
        env_fingerprint.len() >= 16,
        "environment_fingerprint should look like a stable hash"
    );

    let events_path = root.join(
        matrix["events_path"]
            .as_str()
            .expect("events_path should be string"),
    );
    assert!(
        events_path.exists(),
        "baseline matrix events_path should exist: {}",
        events_path.display()
    );
    let events_raw =
        fs::read_to_string(&events_path).expect("baseline matrix events jsonl should be readable");
    let event_rows = events_raw
        .lines()
        .filter(|line| !line.trim().is_empty())
        .map(|line| serde_json::from_str::<Value>(line).expect("event row should be valid json"))
        .collect::<Vec<_>>();
    assert_eq!(
        event_rows.len(),
        scenarios.len() * (runs as usize + warmup_runs as usize),
        "events row count should match scenarios * (warmup + measured runs)"
    );

    let mut observed_measurement_counts = BTreeMap::new();
    for event in event_rows {
        for key in [
            "phase",
            "scenario_id",
            "topology",
            "run_index",
            "seed",
            "node_count",
            "edge_count_estimate",
            "replay_command",
            "elapsed_ms",
            "max_rss_kb",
        ] {
            assert!(event.get(key).is_some(), "event row missing key `{key}`");
        }
        let phase = event["phase"]
            .as_str()
            .expect("event phase should be string");
        let scenario_id = event["scenario_id"]
            .as_str()
            .expect("event scenario_id should be string");
        let replay_command = event["replay_command"]
            .as_str()
            .expect("event replay_command should be string");
        assert!(
            replay_command.contains("--topology") && replay_command.contains("--seed"),
            "event replay_command should include deterministic topology/seed selectors"
        );
        assert!(
            event["elapsed_ms"]
                .as_f64()
                .expect("event elapsed_ms should be f64")
                >= 0.0
                && event["max_rss_kb"]
                    .as_u64()
                    .expect("event max_rss_kb should be u64")
                    >= 1,
            "event timing/memory fields should be non-negative"
        );

        match phase {
            "warmup" => {}
            "measurement" => {
                *observed_measurement_counts
                    .entry(scenario_id.to_owned())
                    .or_insert(0usize) += 1;
            }
            other => panic!("unsupported event phase `{other}`"),
        }
    }
    assert_eq!(
        observed_measurement_counts, measurement_event_expectations,
        "event measurement coverage should match scenario sample counts"
    );

    let hotspot_backlog =
        load_json(&root.join("artifacts/perf/phase2c/hotspot_one_lever_backlog_v1.json"));
    for key in [
        "schema_version",
        "backlog_id",
        "source_matrix_path",
        "source_events_path",
        "optimization_protocol",
        "hotspot_profiles",
        "optimization_backlog",
    ] {
        assert!(
            hotspot_backlog.get(key).is_some(),
            "hotspot backlog missing key `{key}`"
        );
    }
    assert_eq!(
        hotspot_backlog["source_matrix_path"]
            .as_str()
            .expect("source_matrix_path should be string"),
        "artifacts/perf/phase2c/perf_baseline_matrix_v1.json"
    );
    assert_eq!(
        hotspot_backlog["source_events_path"]
            .as_str()
            .expect("source_events_path should be string"),
        "artifacts/perf/phase2c/perf_baseline_matrix_events_v1.jsonl"
    );

    let optimization_protocol = hotspot_backlog["optimization_protocol"]
        .as_object()
        .expect("optimization_protocol should be object");
    assert!(
        optimization_protocol["one_lever_per_change"]
            .as_bool()
            .expect("one_lever_per_change should be bool"),
        "optimization protocol must enforce one-lever-per-change"
    );
    assert!(
        optimization_protocol["minimum_ev_score"]
            .as_f64()
            .expect("minimum_ev_score should be f64")
            >= 2.0,
        "optimization protocol minimum EV should be >= 2.0"
    );

    let hotspot_profiles = hotspot_backlog["hotspot_profiles"]
        .as_array()
        .expect("hotspot_profiles should be array");
    assert!(
        !hotspot_profiles.is_empty(),
        "hotspot_profiles should contain ranked bottlenecks"
    );
    let backlog_entries = hotspot_backlog["optimization_backlog"]
        .as_array()
        .expect("optimization_backlog should be array");
    assert_eq!(
        backlog_entries.len(),
        hotspot_profiles.len(),
        "optimization_backlog should mirror hotspot profile coverage"
    );

    let mut previous_ev = f64::INFINITY;
    for entry in backlog_entries {
        for key in [
            "entry_id",
            "rank",
            "target_scenario_id",
            "expected_value_score",
            "single_lever",
            "lever_count",
            "baseline_comparator",
            "fallback_trigger",
            "rollback_path",
            "decision_contract",
            "isomorphism_proof_refs",
            "risk_note_refs",
            "linked_packet_optimization_beads",
        ] {
            assert!(
                entry.get(key).is_some(),
                "optimization_backlog entry missing key `{key}`"
            );
        }
        assert_eq!(
            entry["lever_count"]
                .as_u64()
                .expect("lever_count should be u64"),
            1,
            "optimization backlog entry must be single-lever"
        );
        assert!(
            entry["single_lever"]
                .as_str()
                .expect("single_lever should be string")
                .trim()
                .len()
                >= 12,
            "single_lever should contain concrete lever details"
        );
        assert!(
            entry["fallback_trigger"]
                .as_str()
                .expect("fallback_trigger should be string")
                .contains("5%"),
            "fallback_trigger should include explicit regression threshold"
        );
        assert!(
            entry["rollback_path"]
                .as_str()
                .expect("rollback_path should be string")
                .contains("git revert"),
            "rollback_path should specify concrete rollback command"
        );
        let ev = entry["expected_value_score"]
            .as_f64()
            .expect("expected_value_score should be f64");
        assert!(
            ev >= 2.0,
            "optimization backlog entry expected_value_score should be >= 2.0"
        );
        assert!(
            ev <= previous_ev,
            "optimization backlog should be sorted by descending EV score"
        );
        previous_ev = ev;

        let baseline_ref = entry["baseline_comparator"]
            .as_str()
            .expect("baseline_comparator should be string");
        assert!(
            root.join(baseline_ref).exists(),
            "baseline comparator reference should exist: {baseline_ref}"
        );
        for proof_ref in entry["isomorphism_proof_refs"]
            .as_array()
            .expect("isomorphism_proof_refs should be array")
        {
            let path = proof_ref
                .as_str()
                .expect("isomorphism proof ref should be string");
            assert!(
                root.join(path).exists(),
                "isomorphism proof ref should exist: {path}"
            );
        }
        for risk_ref in entry["risk_note_refs"]
            .as_array()
            .expect("risk_note_refs should be array")
        {
            let path = risk_ref.as_str().expect("risk note ref should be string");
            assert!(
                root.join(path).exists(),
                "risk note ref should exist: {path}"
            );
        }
        assert!(
            !entry["linked_packet_optimization_beads"]
                .as_array()
                .expect("linked_packet_optimization_beads should be array")
                .is_empty(),
            "linked packet optimization beads should be non-empty"
        );
    }

    let playbook_path = root.join("artifacts/perf/phase2c/optimization_playbook_v1.md");
    let playbook =
        fs::read_to_string(&playbook_path).expect("optimization playbook should be readable");
    for section in [
        "## One-Lever Rule",
        "## Behavior-Isomorphism Obligations",
        "## Divergence Policy",
    ] {
        assert!(
            playbook.contains(section),
            "optimization playbook missing section `{section}`"
        );
    }

    let golden_signatures =
        load_json(&root.join("artifacts/perf/phase2c/isomorphism_golden_signatures_v1.json"));
    let divergence_allowlist =
        load_json(&root.join("artifacts/perf/phase2c/isomorphism_divergence_allowlist_v1.json"));
    let harness_report =
        load_json(&root.join("artifacts/perf/phase2c/isomorphism_harness_report_v1.json"));
    assert_eq!(
        harness_report["status"]
            .as_str()
            .expect("isomorphism harness report status should be string"),
        "pass",
        "isomorphism harness must pass under default fail-closed policy"
    );
    assert!(
        harness_report["divergence_policy"]["blocking_default"]
            .as_bool()
            .expect("divergence_policy.blocking_default should be bool"),
        "divergence policy should be fail-closed by default"
    );
    assert_eq!(
        harness_report["scenario_count"]
            .as_u64()
            .expect("isomorphism harness scenario_count should be u64") as usize,
        scenarios.len(),
        "isomorphism harness coverage should match baseline matrix scenario count"
    );
    let golden_map = golden_signatures["signatures"]
        .as_object()
        .expect("isomorphism golden signatures map should be object");
    assert_eq!(
        golden_map.len(),
        scenarios.len(),
        "isomorphism golden signatures should cover every baseline scenario"
    );
    assert!(
        divergence_allowlist["approved_divergences"]
            .as_array()
            .expect("approved_divergences should be array")
            .is_empty(),
        "allowlist should remain empty when no approved divergence exists"
    );

    let regression_report =
        load_json(&root.join("artifacts/perf/phase2c/perf_regression_gate_report_v1.json"));
    for key in [
        "schema_version",
        "report_id",
        "baseline_path",
        "candidate_path",
        "hotspot_backlog_path",
        "policy",
        "scenario_deltas",
        "regressions",
        "summary",
        "status",
    ] {
        assert!(
            regression_report.get(key).is_some(),
            "regression report missing key `{key}`"
        );
    }
    assert!(
        regression_report["policy"]["critical_fail_closed"]
            .as_bool()
            .expect("policy.critical_fail_closed should be bool"),
        "regression policy must be fail-closed for critical paths"
    );
    assert_eq!(
        regression_report["summary"]["scenario_count"]
            .as_u64()
            .expect("summary.scenario_count should be u64") as usize,
        scenarios.len(),
        "regression report scenario coverage should match matrix scenarios"
    );
    assert_eq!(
        regression_report["status"]
            .as_str()
            .expect("regression report status should be string"),
        "pass",
        "regression report should pass for current candidate matrix"
    );
    for delta in regression_report["scenario_deltas"]
        .as_array()
        .expect("scenario_deltas should be array")
    {
        for key in [
            "scenario_id",
            "critical_path",
            "baseline_comparator",
            "hotspot_ref",
            "delta_pct",
            "threshold_pct",
            "regressed",
        ] {
            assert!(
                delta.get(key).is_some(),
                "scenario_deltas row missing key `{key}`"
            );
        }
        let baseline_ref = delta["baseline_comparator"]
            .as_str()
            .expect("baseline_comparator should be string");
        let hotspot_ref = delta["hotspot_ref"]
            .as_str()
            .expect("hotspot_ref should be string");
        assert!(
            root.join(baseline_ref).exists(),
            "scenario delta baseline comparator should exist: {baseline_ref}"
        );
        assert!(
            root.join(hotspot_ref).exists(),
            "scenario delta hotspot ref should exist: {hotspot_ref}"
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

#[test]
fn adversarial_crash_triage_and_promotion_pipeline_is_machine_auditable() {
    let root = repo_root();
    let seed_ledger =
        load_json(&root.join("artifacts/phase2c/security/v1/adversarial_seed_ledger_v1.json"));
    let triage_report =
        load_json(&root.join("artifacts/phase2c/latest/adversarial_crash_triage_report_v1.json"));
    let promotion_queue = load_json(
        &root.join("artifacts/phase2c/latest/adversarial_regression_promotion_queue_v1.json"),
    );
    let fixture_bundle =
        load_json(&root.join(
            "crates/fnx-conformance/fixtures/generated/adversarial_regression_bundle_v1.json",
        ));

    assert_eq!(
        triage_report["status"]
            .as_str()
            .expect("triage report status should be string"),
        "pass"
    );
    let routing_policy_counts = triage_report["routing_policy_counts"]
        .as_object()
        .expect("triage report routing_policy_counts should be object");
    for policy in ["bug", "known_risk_allowlist", "compatibility_exception"] {
        assert!(
            routing_policy_counts.contains_key(policy),
            "triage report routing_policy_counts missing `{policy}`"
        );
    }

    let seed_entries = seed_ledger["entries"]
        .as_array()
        .expect("seed ledger entries should be array");
    let seed_entry_count = seed_ledger["entry_count"]
        .as_u64()
        .expect("seed ledger entry_count should be u64") as usize;
    assert_eq!(
        seed_entry_count,
        seed_entries.len(),
        "seed ledger entry_count mismatch"
    );

    let triage_events_path =
        root.join("artifacts/phase2c/latest/adversarial_crash_triage_events_v1.jsonl");
    let triage_events_raw =
        fs::read_to_string(&triage_events_path).expect("triage events jsonl should be readable");
    let triage_events = triage_events_raw
        .lines()
        .filter(|line| !line.trim().is_empty())
        .map(|line| serde_json::from_str::<Value>(line).expect("triage event row should be json"))
        .collect::<Vec<_>>();
    let triage_count = triage_report["triage_count"]
        .as_u64()
        .expect("triage report triage_count should be u64") as usize;
    assert_eq!(
        triage_count, seed_entry_count,
        "triage count must match seed count"
    );
    assert_eq!(
        triage_events.len(),
        triage_count,
        "triage events row count must match triage report"
    );

    let seed_fixture_hashes = seed_entries
        .iter()
        .map(|entry| {
            entry["fixture_hash_id"]
                .as_str()
                .expect("seed entry fixture_hash_id should be string")
                .to_owned()
        })
        .collect::<BTreeSet<_>>();

    let mut triage_ids = BTreeSet::new();
    let mut fixture_ids = BTreeSet::new();
    for triage_event in &triage_events {
        for key in [
            "triage_id",
            "packet_id",
            "owner_bead_id",
            "threat_class",
            "severity_tag",
            "failure_classification",
            "fixture_hash_id",
            "seed",
            "validation_gate",
            "generator_variant",
            "stack_signature",
            "environment_fingerprint",
            "environment",
            "routing_policy",
            "triage_status",
            "routing_tags",
            "minimal_reproducer",
            "replay_command",
            "conformance_gate_ids",
            "forensics_refs",
            "regression_fixture_id",
            "promotion_action",
        ] {
            assert!(
                triage_event.get(key).is_some(),
                "triage event missing key `{key}`"
            );
        }
        let triage_id = triage_event["triage_id"]
            .as_str()
            .expect("triage_event triage_id should be string")
            .to_owned();
        let severity = triage_event["severity_tag"]
            .as_str()
            .expect("triage_event severity_tag should be string");
        let owner_bead = triage_event["owner_bead_id"]
            .as_str()
            .expect("triage_event owner_bead_id should be string");
        let fixture_hash_id = triage_event["fixture_hash_id"]
            .as_str()
            .expect("triage_event fixture_hash_id should be string");
        let stack_signature = triage_event["stack_signature"]
            .as_str()
            .expect("triage_event stack_signature should be string");
        let env_fingerprint = triage_event["environment_fingerprint"]
            .as_str()
            .expect("triage_event environment_fingerprint should be string");
        let routing_policy = triage_event["routing_policy"]
            .as_str()
            .expect("triage_event routing_policy should be string");
        let replay_command = triage_event["replay_command"]
            .as_str()
            .expect("triage_event replay_command should be string");
        let regression_fixture_id = triage_event["regression_fixture_id"]
            .as_str()
            .expect("triage_event regression_fixture_id should be string")
            .to_owned();

        assert!(
            ["critical", "high", "medium", "low"].contains(&severity),
            "unsupported severity_tag `{severity}`"
        );
        assert!(
            owner_bead.starts_with("bd-315."),
            "triage_event owner_bead_id should route to packet owner bead"
        );
        assert_eq!(
            triage_event["triage_status"]
                .as_str()
                .expect("triage_event triage_status should be string"),
            "confirmed_regression_candidate"
        );
        assert!(
            seed_fixture_hashes.contains(fixture_hash_id),
            "triage_event fixture_hash_id must exist in seed ledger"
        );
        assert!(
            replay_command.contains("run_adversarial_seed_harness.py"),
            "triage_event replay_command should support single-command replay"
        );
        assert!(
            stack_signature.len() >= 8,
            "triage_event stack_signature should look like a stable hash"
        );
        assert!(
            env_fingerprint.len() >= 8,
            "triage_event environment_fingerprint should be non-empty hash"
        );
        assert!(
            ["bug", "known_risk_allowlist", "compatibility_exception"].contains(&routing_policy),
            "triage_event routing_policy `{routing_policy}` is unsupported"
        );
        let minimal_reproducer = triage_event["minimal_reproducer"]
            .as_object()
            .expect("triage_event minimal_reproducer should be object");
        assert_eq!(
            minimal_reproducer
                .get("command")
                .and_then(Value::as_str)
                .expect("triage_event minimal_reproducer.command should be string"),
            replay_command,
            "triage_event minimal_reproducer.command should match replay_command"
        );
        assert!(
            minimal_reproducer
                .get("seed")
                .and_then(Value::as_u64)
                .is_some(),
            "triage_event minimal_reproducer.seed should be u64"
        );
        assert!(
            triage_event["conformance_gate_ids"]
                .as_array()
                .expect("triage_event conformance_gate_ids should be array")
                .iter()
                .any(|gate| gate.as_str() == Some("phase2c_packet_readiness_gate")),
            "triage_event conformance gate linkage missing phase2c gate id"
        );
        for ref_path in triage_event["forensics_refs"]
            .as_array()
            .expect("triage_event forensics_refs should be array")
        {
            let rel = ref_path
                .as_str()
                .expect("triage_event forensics ref should be string");
            assert!(
                root.join(rel).exists(),
                "triage_event forensics ref path missing: {rel}"
            );
        }

        let routing_tags = triage_event["routing_tags"]
            .as_array()
            .expect("triage_event routing_tags should be array");
        assert!(
            !routing_tags.is_empty(),
            "triage_event routing_tags should be non-empty"
        );
        triage_ids.insert(triage_id);
        fixture_ids.insert(regression_fixture_id);
    }

    let promotion_entries = promotion_queue["entries"]
        .as_array()
        .expect("promotion queue entries should be array");
    assert_eq!(
        promotion_queue["entry_count"]
            .as_u64()
            .expect("promotion queue entry_count should be u64") as usize,
        promotion_entries.len(),
        "promotion queue entry_count mismatch"
    );
    assert_eq!(
        promotion_entries.len(),
        triage_count,
        "promotion queue must include each triage row"
    );
    for promotion_entry in promotion_entries {
        assert_eq!(
            promotion_entry["promotion_status"]
                .as_str()
                .expect("promotion entry promotion_status should be string"),
            "promoted"
        );
        assert!(
            ["bug", "known_risk_allowlist", "compatibility_exception"].contains(
                &promotion_entry["routing_policy"]
                    .as_str()
                    .expect("promotion entry routing_policy should be string")
            ),
            "promotion entry routing_policy should be supported"
        );
        assert!(
            triage_ids.contains(
                promotion_entry["source_triage_id"]
                    .as_str()
                    .expect("promotion entry source_triage_id should be string")
            ),
            "promotion entry must reference triage event source"
        );
        assert_eq!(
            promotion_entry["target_fixture_bundle_path"]
                .as_str()
                .expect("promotion entry target fixture bundle path should be string"),
            "crates/fnx-conformance/fixtures/generated/adversarial_regression_bundle_v1.json"
        );
    }

    let fixtures = fixture_bundle["fixtures"]
        .as_array()
        .expect("fixture bundle fixtures should be array");
    assert_eq!(
        fixture_bundle["fixture_count"]
            .as_u64()
            .expect("fixture bundle fixture_count should be u64") as usize,
        fixtures.len(),
        "fixture bundle fixture_count mismatch"
    );
    assert_eq!(
        fixtures.len(),
        triage_count,
        "fixture bundle must include one fixture per triage event"
    );
    for fixture in fixtures {
        assert!(
            fixture_ids.contains(
                fixture["fixture_id"]
                    .as_str()
                    .expect("fixture bundle fixture_id should be string")
            ),
            "fixture bundle fixture_id must be sourced from triage"
        );
        assert!(
            fixture["owner_bead_id"]
                .as_str()
                .expect("fixture bundle owner_bead_id should be string")
                .starts_with("bd-315."),
            "fixture bundle entries must link to packet owner beads"
        );
        assert!(
            ["bug", "known_risk_allowlist", "compatibility_exception"].contains(
                &fixture["routing_policy"]
                    .as_str()
                    .expect("fixture bundle routing_policy should be string")
            ),
            "fixture bundle routing_policy should be supported"
        );
        assert!(
            fixture["replay_command"]
                .as_str()
                .expect("fixture bundle replay_command should be string")
                .contains("run_adversarial_seed_harness.py"),
            "fixture bundle replay command must be deterministic and directly runnable"
        );
        assert!(
            fixture["conformance_gate_ids"]
                .as_array()
                .expect("fixture bundle conformance_gate_ids should be array")
                .iter()
                .any(|gate| gate.as_str() == Some("phase2c_packet_readiness_gate")),
            "fixture bundle entries must link to conformance gate ids"
        );
    }
}
