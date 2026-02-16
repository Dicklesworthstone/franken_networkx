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

#[test]
fn e2e_script_pack_artifacts_are_complete_and_deterministic() {
    let root = repo_root();
    let schema = load_json(&root.join("artifacts/e2e/schema/v1/e2e_script_pack_schema_v1.json"));
    let report =
        load_json(&root.join("artifacts/e2e/latest/e2e_script_pack_determinism_report_v1.json"));
    let events = load_jsonl(&root.join("artifacts/e2e/latest/e2e_script_pack_events_v1.jsonl"));
    let replay_report =
        load_json(&root.join("artifacts/e2e/latest/e2e_script_pack_replay_report_v1.json"));

    let required_report_keys = schema["required_report_keys"]
        .as_array()
        .expect("required_report_keys should be array")
        .iter()
        .map(|value| value.as_str().expect("report key should be string"))
        .collect::<Vec<_>>();
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

    let required_scenarios = schema["required_scenarios"]
        .as_array()
        .expect("required_scenarios should be array")
        .iter()
        .map(|value| {
            value
                .as_str()
                .expect("required scenario should be string")
                .to_owned()
        })
        .collect::<BTreeSet<_>>();
    let required_pass_labels = schema["required_pass_labels"]
        .as_array()
        .expect("required_pass_labels should be array")
        .iter()
        .map(|value| {
            value
                .as_str()
                .expect("required pass label should be string")
                .to_owned()
        })
        .collect::<BTreeSet<_>>();

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

        let bundle_id = event["bundle_id"]
            .as_str()
            .expect("bundle_id should be string");
        let fingerprint = event["stable_fingerprint"]
            .as_str()
            .expect("stable_fingerprint should be string");
        bundle_ids_by_scenario
            .entry(scenario.to_owned())
            .or_default()
            .insert(bundle_id.to_owned());
        fingerprints_by_scenario
            .entry(scenario.to_owned())
            .or_default()
            .insert(fingerprint.to_owned());

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
        let forensics = manifest["forensics_links"]
            .as_object()
            .expect("forensics_links should be object");
        for key in schema["required_forensics_keys"]
            .as_array()
            .expect("required_forensics_keys should be array")
            .iter()
            .map(|value| value.as_str().expect("forensics key should be string"))
        {
            assert!(
                forensics.get(key).is_some(),
                "forensics_links missing key `{key}`"
            );
            let value = forensics
                .get(key)
                .and_then(Value::as_str)
                .unwrap_or_default()
                .trim()
                .to_owned();
            assert!(
                !value.is_empty(),
                "forensics_links field `{key}` should be non-empty string"
            );
        }
        assert_eq!(
            forensics
                .get("forensics_bundle_replay_ref")
                .and_then(Value::as_str),
            Some(replay_command),
            "forensics replay reference should match replay_command"
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
    }

    for scenario in &required_scenarios {
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
