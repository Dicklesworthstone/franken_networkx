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
            serde_json::from_str(line).unwrap_or_else(|err| {
                panic!("expected valid jsonl row at {}: {err}", path.display())
            })
        })
        .collect()
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
fn ftui_workflow_event_contract_is_complete_and_deterministic() {
    let root = repo_root();
    let artifact = load_json(&root.join("artifacts/ftui/v1/ftui_workflow_event_contract_v1.json"));
    let schema = load_json(
        &root.join("artifacts/ftui/schema/v1/ftui_workflow_event_contract_schema_v1.json"),
    );

    for key in required_string_array(&schema, "required_top_level_keys") {
        assert!(
            artifact.get(key).is_some(),
            "artifact missing top-level key `{key}`"
        );
    }

    let required_states = required_string_array(&schema, "required_states")
        .into_iter()
        .collect::<BTreeSet<_>>();
    let required_terminal_states = required_string_array(&schema, "required_terminal_states")
        .into_iter()
        .collect::<BTreeSet<_>>();
    let required_event_ids = required_string_array(&schema, "required_event_ids")
        .into_iter()
        .collect::<BTreeSet<_>>();
    let required_journey_kinds = required_string_array(&schema, "required_journey_kinds")
        .into_iter()
        .collect::<BTreeSet<_>>();
    let required_telemetry_fields = required_string_array(&schema, "required_telemetry_fields")
        .into_iter()
        .collect::<BTreeSet<_>>();

    let workflow_map = artifact["workflow_map"]
        .as_object()
        .expect("workflow_map should be object");
    for key in required_string_array(&schema, "required_workflow_map_keys") {
        assert!(
            workflow_map.get(key).is_some(),
            "workflow_map missing key `{key}`"
        );
    }
    let journeys = workflow_map["journeys"]
        .as_array()
        .expect("workflow_map.journeys should be array");
    assert!(
        !journeys.is_empty(),
        "workflow_map.journeys should be non-empty"
    );

    let required_journey_keys = required_string_array(&schema, "required_journey_keys");
    let required_step_keys = required_string_array(&schema, "required_step_keys");
    let mut observed_journey_kinds = BTreeSet::new();
    let mut observed_journey_ids = BTreeSet::new();
    let mut observed_step_ids = BTreeSet::new();
    let mut events_seen_in_steps = BTreeSet::new();

    for (journey_idx, journey) in journeys.iter().enumerate() {
        for key in &required_journey_keys {
            assert!(
                journey.get(*key).is_some(),
                "workflow_map.journeys[{journey_idx}] missing key `{key}`"
            );
        }
        let journey_id = journey["journey_id"]
            .as_str()
            .expect("journey_id should be string");
        assert!(
            observed_journey_ids.insert(journey_id.to_owned()),
            "duplicate journey_id `{journey_id}`"
        );
        let kind = journey["kind"]
            .as_str()
            .expect("journey.kind should be string");
        assert!(
            required_journey_kinds.contains(kind),
            "workflow_map.journeys[{journey_idx}] has unsupported kind `{kind}`"
        );
        observed_journey_kinds.insert(kind);

        let steps = journey["steps"]
            .as_array()
            .expect("journey.steps should be array");
        assert!(
            !steps.is_empty(),
            "journey `{journey_id}` should have steps"
        );
        for (step_idx, step) in steps.iter().enumerate() {
            for key in &required_step_keys {
                assert!(
                    step.get(*key).is_some(),
                    "journey `{journey_id}` step {step_idx} missing key `{key}`"
                );
            }
            let step_id = step["step_id"]
                .as_str()
                .expect("step.step_id should be string");
            assert!(
                observed_step_ids.insert(step_id),
                "duplicate step_id `{step_id}`"
            );
            let event_id = step["event_id"]
                .as_str()
                .expect("step.event_id should be string");
            assert!(
                required_event_ids.contains(event_id),
                "step `{step_id}` references unknown event_id `{event_id}`"
            );
            events_seen_in_steps.insert(event_id);

            let expected_state = step["expected_state"]
                .as_str()
                .expect("step.expected_state should be string");
            assert!(
                required_states.contains(expected_state),
                "step `{step_id}` has unknown expected_state `{expected_state}`"
            );
            assert_path(
                step["artifact_ref"]
                    .as_str()
                    .expect("step.artifact_ref should be string"),
                &format!("workflow_map.journeys[{journey_idx}].steps[{step_idx}].artifact_ref"),
                &root,
            );
            assert!(
                !step["test_id"]
                    .as_str()
                    .expect("step.test_id should be string")
                    .trim()
                    .is_empty(),
                "step `{step_id}` test_id should be non-empty"
            );
        }

        let outcome_contract = journey["outcome_contract"]
            .as_object()
            .expect("journey.outcome_contract should be object");
        let terminal_state = outcome_contract["terminal_state"]
            .as_str()
            .expect("outcome_contract.terminal_state should be string");
        assert!(
            required_terminal_states.contains(terminal_state),
            "journey `{journey_id}` terminal_state should be terminal"
        );
    }

    assert_eq!(
        observed_journey_kinds, required_journey_kinds,
        "journey kinds drifted from schema"
    );

    let event_contract = artifact["event_contract"]
        .as_object()
        .expect("event_contract should be object");
    for key in required_string_array(&schema, "required_event_contract_keys") {
        assert!(
            event_contract.get(key).is_some(),
            "event_contract missing key `{key}`"
        );
    }
    let invariant_checks = event_contract["invariant_checks"]
        .as_array()
        .expect("event_contract.invariant_checks should be array");
    assert!(
        !invariant_checks.is_empty(),
        "event_contract.invariant_checks should be non-empty"
    );

    let required_event_keys = required_string_array(&schema, "required_event_keys");
    let events = event_contract["events"]
        .as_array()
        .expect("event_contract.events should be array");
    assert!(
        !events.is_empty(),
        "event_contract.events should be non-empty"
    );

    let mut observed_event_ids = BTreeSet::new();
    let mut event_indices = BTreeSet::new();
    let mut event_state_map = BTreeMap::<String, (String, String)>::new();
    for (idx, event) in events.iter().enumerate() {
        for key in &required_event_keys {
            assert!(
                event.get(*key).is_some(),
                "event_contract.events[{idx}] missing key `{key}`"
            );
        }
        let event_id = event["event_id"]
            .as_str()
            .expect("event_id should be string");
        assert!(
            required_event_ids.contains(event_id),
            "unknown event_id `{event_id}` in event_contract"
        );
        assert!(
            observed_event_ids.insert(event_id.to_owned()),
            "duplicate event_id `{event_id}`"
        );
        let from_state = event["from_state"]
            .as_str()
            .expect("from_state should be string");
        let to_state = event["to_state"]
            .as_str()
            .expect("to_state should be string");
        assert!(
            required_states.contains(from_state),
            "event `{event_id}` has unknown from_state `{from_state}`"
        );
        assert!(
            required_states.contains(to_state),
            "event `{event_id}` has unknown to_state `{to_state}`"
        );
        let index = event["deterministic_index"]
            .as_u64()
            .expect("deterministic_index should be u64");
        assert!(
            index > 0,
            "deterministic_index must be > 0 for `{event_id}`"
        );
        assert!(
            event_indices.insert(index),
            "duplicate deterministic_index `{index}` in event_contract"
        );
        assert!(
            event["payload_contract"].is_object(),
            "event `{event_id}` payload_contract should be object"
        );
        assert!(
            !event["policy_on_invalid_input"]
                .as_str()
                .expect("policy_on_invalid_input should be string")
                .trim()
                .is_empty(),
            "event `{event_id}` policy_on_invalid_input should be non-empty"
        );
        assert!(
            !event["telemetry_event_name"]
                .as_str()
                .expect("telemetry_event_name should be string")
                .trim()
                .is_empty(),
            "event `{event_id}` telemetry_event_name should be non-empty"
        );
        event_state_map.insert(
            event_id.to_owned(),
            (from_state.to_owned(), to_state.to_owned()),
        );
    }
    assert_eq!(
        observed_event_ids,
        required_event_ids
            .iter()
            .map(|value| (*value).to_owned())
            .collect(),
        "event id set drifted from schema"
    );

    let expected_indices = (1_u64..=u64::try_from(required_event_ids.len()).expect("len fits"))
        .collect::<BTreeSet<_>>();
    assert_eq!(
        event_indices, expected_indices,
        "event deterministic_index values should be contiguous"
    );

    let state_machine = artifact["state_machine"]
        .as_object()
        .expect("state_machine should be object");
    for key in required_string_array(&schema, "required_state_machine_keys") {
        assert!(
            state_machine.get(key).is_some(),
            "state_machine missing key `{key}`"
        );
    }
    let observed_states = state_machine["states"]
        .as_array()
        .expect("state_machine.states should be array")
        .iter()
        .map(|value| value.as_str().expect("state should be string"))
        .collect::<BTreeSet<_>>();
    assert_eq!(
        observed_states, required_states,
        "state_machine.states drifted from schema"
    );
    let observed_terminal_states = state_machine["terminal_states"]
        .as_array()
        .expect("state_machine.terminal_states should be array")
        .iter()
        .map(|value| value.as_str().expect("terminal state should be string"))
        .collect::<BTreeSet<_>>();
    assert_eq!(
        observed_terminal_states, required_terminal_states,
        "state_machine.terminal_states drifted from schema"
    );
    let initial_state = state_machine["initial_state"]
        .as_str()
        .expect("state_machine.initial_state should be string");
    assert_eq!(initial_state, "idle", "initial state should be idle");

    let required_transition_keys = required_string_array(&schema, "required_transition_keys");
    let transitions = state_machine["transitions"]
        .as_array()
        .expect("state_machine.transitions should be array");
    assert_eq!(
        transitions.len(),
        required_event_ids.len(),
        "state_machine.transitions should cover each required event exactly once"
    );

    let mut transition_indices = BTreeSet::new();
    let mut transition_pairs = BTreeSet::new();
    let mut transition_events = BTreeSet::new();
    for (idx, transition) in transitions.iter().enumerate() {
        for key in &required_transition_keys {
            assert!(
                transition.get(*key).is_some(),
                "state_machine.transitions[{idx}] missing key `{key}`"
            );
        }
        let from_state = transition["from_state"]
            .as_str()
            .expect("transition.from_state should be string");
        let event_id = transition["event_id"]
            .as_str()
            .expect("transition.event_id should be string");
        let to_state = transition["to_state"]
            .as_str()
            .expect("transition.to_state should be string");
        assert!(
            required_states.contains(from_state),
            "transition[{idx}] unknown from_state `{from_state}`"
        );
        assert!(
            required_states.contains(to_state),
            "transition[{idx}] unknown to_state `{to_state}`"
        );
        assert!(
            required_event_ids.contains(event_id),
            "transition[{idx}] unknown event_id `{event_id}`"
        );
        assert!(
            transition_pairs.insert((from_state.to_owned(), event_id.to_owned())),
            "transition[{idx}] duplicates (from_state,event_id) pair"
        );
        transition_events.insert(event_id.to_owned());

        let index = transition["deterministic_index"]
            .as_u64()
            .expect("transition.deterministic_index should be u64");
        assert!(
            transition_indices.insert(index),
            "duplicate transition deterministic_index `{index}`"
        );

        let (event_from, event_to) = event_state_map
            .get(event_id)
            .unwrap_or_else(|| panic!("event `{event_id}` missing from event_contract"));
        assert_eq!(
            event_from, from_state,
            "transition[{idx}] from_state does not match event_contract for `{event_id}`"
        );
        assert_eq!(
            event_to, to_state,
            "transition[{idx}] to_state does not match event_contract for `{event_id}`"
        );

        if to_state == "failed_closed" {
            let reason = transition["reason_code"].as_str().unwrap_or_else(|| {
                panic!("transition[{idx}] to failed_closed requires reason_code")
            });
            assert!(
                !reason.trim().is_empty(),
                "transition[{idx}] reason_code should be non-empty for failed_closed"
            );
        }
    }
    assert_eq!(
        transition_events, observed_event_ids,
        "transition event coverage should match event_contract.events"
    );
    let expected_transition_indices = (1_u64
        ..=u64::try_from(required_event_ids.len()).expect("len fits"))
        .collect::<BTreeSet<_>>();
    assert_eq!(
        transition_indices, expected_transition_indices,
        "transition deterministic_index values should be contiguous"
    );

    let traceability = artifact["traceability_map"]
        .as_array()
        .expect("traceability_map should be array");
    assert!(
        !traceability.is_empty(),
        "traceability_map should be non-empty"
    );
    let required_traceability_keys = required_string_array(&schema, "required_traceability_keys");
    let mut traceability_events = BTreeSet::new();
    for (idx, row) in traceability.iter().enumerate() {
        for key in &required_traceability_keys {
            assert!(
                row.get(*key).is_some(),
                "traceability_map[{idx}] missing key `{key}`"
            );
        }
        let event_id = row["ui_event_id"]
            .as_str()
            .expect("traceability_map.ui_event_id should be string");
        assert!(
            required_event_ids.contains(event_id),
            "traceability_map[{idx}] unknown event_id `{event_id}`"
        );
        assert!(
            traceability_events.insert(event_id.to_owned()),
            "traceability_map has duplicate ui_event_id `{event_id}`"
        );
        let artifact_ids = row["artifact_ids"]
            .as_array()
            .expect("traceability_map.artifact_ids should be array");
        assert!(
            !artifact_ids.is_empty(),
            "traceability_map[{idx}] artifact_ids should be non-empty"
        );
        for (artifact_idx, artifact_path) in artifact_ids.iter().enumerate() {
            assert_path(
                artifact_path
                    .as_str()
                    .unwrap_or_else(|| panic!("artifact_ids[{artifact_idx}] should be string")),
                &format!("traceability_map[{idx}].artifact_ids[{artifact_idx}]"),
                &root,
            );
        }
        let test_ids = row["test_ids"]
            .as_array()
            .expect("traceability_map.test_ids should be array");
        assert!(
            !test_ids.is_empty(),
            "traceability_map[{idx}] test_ids should be non-empty"
        );
        for test_id in test_ids {
            assert!(
                !test_id
                    .as_str()
                    .expect("test_id should be string")
                    .trim()
                    .is_empty(),
                "traceability_map[{idx}] test_id should be non-empty"
            );
        }
        let telemetry_fields = row["telemetry_fields"]
            .as_array()
            .expect("traceability_map.telemetry_fields should be array")
            .iter()
            .map(|value| value.as_str().expect("telemetry field should be string"))
            .collect::<BTreeSet<_>>();
        assert!(
            required_telemetry_fields.is_subset(&telemetry_fields),
            "traceability_map[{idx}] telemetry_fields missing required entries"
        );
    }
    assert_eq!(
        traceability_events, observed_event_ids,
        "traceability_map must cover all event ids"
    );

    let accessibility = artifact["accessibility_constraints"]
        .as_object()
        .expect("accessibility_constraints should be object");
    for key in required_string_array(&schema, "required_accessibility_keys") {
        assert!(
            accessibility.get(key).is_some(),
            "accessibility_constraints missing key `{key}`"
        );
    }
    let keyboard = accessibility["keyboard_navigation"]
        .as_object()
        .expect("keyboard_navigation should be object");
    assert!(
        keyboard["tab_order_deterministic"]
            .as_bool()
            .expect("tab_order_deterministic should be bool"),
        "keyboard_navigation.tab_order_deterministic should be true"
    );
    let shortcuts = keyboard["required_shortcuts"]
        .as_array()
        .expect("keyboard_navigation.required_shortcuts should be array");
    assert!(
        !shortcuts.is_empty(),
        "keyboard_navigation.required_shortcuts should be non-empty"
    );
    let screen_reader = accessibility["screen_reader"]
        .as_object()
        .expect("screen_reader should be object");
    assert!(
        screen_reader["aria_labels_required"]
            .as_bool()
            .expect("aria_labels_required should be bool"),
        "screen_reader.aria_labels_required should be true"
    );
    assert!(
        screen_reader["announce_state_transitions"]
            .as_bool()
            .expect("announce_state_transitions should be bool"),
        "screen_reader.announce_state_transitions should be true"
    );
    let color_contrast = accessibility["color_contrast"]
        .as_object()
        .expect("color_contrast should be object");
    let min_ratio = color_contrast["minimum_ratio_wcag_aa"]
        .as_f64()
        .expect("minimum_ratio_wcag_aa should be f64");
    assert!(min_ratio >= 4.5, "minimum_ratio_wcag_aa should be >= 4.5");
    let ergonomics = accessibility["ergonomics"]
        .as_object()
        .expect("ergonomics should be object");
    let max_actions = ergonomics["max_primary_actions_per_screen"]
        .as_u64()
        .expect("max_primary_actions_per_screen should be u64");
    assert!(
        (1..=7).contains(&max_actions),
        "max_primary_actions_per_screen should be between 1 and 7"
    );

    let decision_contract = artifact["decision_theoretic_runtime_contract"]
        .as_object()
        .expect("decision_theoretic_runtime_contract should be object");
    for key in required_string_array(&schema, "required_decision_contract_keys") {
        assert!(
            decision_contract.get(key).is_some(),
            "decision_theoretic_runtime_contract missing key `{key}`"
        );
    }
    let loss_budget = decision_contract["loss_budget"]
        .as_object()
        .expect("loss_budget should be object");
    for key in required_string_array(&schema, "required_loss_budget_keys") {
        assert!(
            loss_budget.get(key).is_some(),
            "loss_budget missing key `{key}`"
        );
    }
    let safe_mode_fallback = decision_contract["safe_mode_fallback"]
        .as_object()
        .expect("safe_mode_fallback should be object");
    for key in required_string_array(&schema, "required_safe_mode_fallback_keys") {
        assert!(
            safe_mode_fallback.get(key).is_some(),
            "safe_mode_fallback missing key `{key}`"
        );
    }

    let profile_artifacts = artifact["profile_first_artifacts"]
        .as_object()
        .expect("profile_first_artifacts should be object");
    for key in required_string_array(&schema, "required_profile_artifact_keys") {
        assert_path(
            profile_artifacts[key]
                .as_str()
                .expect("profile artifact path should be string"),
            &format!("profile_first_artifacts.{key}"),
            &root,
        );
    }

    let isomorphism_artifacts = artifact["isomorphism_proof_artifacts"]
        .as_array()
        .expect("isomorphism_proof_artifacts should be array");
    assert!(
        !isomorphism_artifacts.is_empty(),
        "isomorphism_proof_artifacts should be non-empty"
    );
    for (idx, path_text) in isomorphism_artifacts.iter().enumerate() {
        assert_path(
            path_text
                .as_str()
                .unwrap_or_else(|| panic!("isomorphism_proof_artifacts[{idx}] should be string")),
            &format!("isomorphism_proof_artifacts[{idx}]"),
            &root,
        );
    }

    let structured_logging_evidence = artifact["structured_logging_evidence"]
        .as_array()
        .expect("structured_logging_evidence should be array");
    assert!(
        !structured_logging_evidence.is_empty(),
        "structured_logging_evidence should be non-empty"
    );
    for (idx, path_text) in structured_logging_evidence.iter().enumerate() {
        assert_path(
            path_text
                .as_str()
                .unwrap_or_else(|| panic!("structured_logging_evidence[{idx}] should be string")),
            &format!("structured_logging_evidence[{idx}]"),
            &root,
        );
    }

    let journey_script_pack = artifact["journey_script_pack"]
        .as_object()
        .expect("journey_script_pack should be object");
    for key in required_string_array(&schema, "required_journey_script_pack_keys") {
        assert!(
            journey_script_pack.get(key).is_some(),
            "journey_script_pack missing key `{key}`"
        );
    }

    let pack_artifact_path = journey_script_pack["artifact_path"]
        .as_str()
        .expect("journey_script_pack.artifact_path should be string");
    let pack_schema_path = journey_script_pack["schema_path"]
        .as_str()
        .expect("journey_script_pack.schema_path should be string");
    let pack_script_path = journey_script_pack["script_path"]
        .as_str()
        .expect("journey_script_pack.script_path should be string");
    let regression_harness_command = journey_script_pack["regression_harness_command"]
        .as_str()
        .expect("journey_script_pack.regression_harness_command should be string");
    assert_path(
        pack_artifact_path,
        "journey_script_pack.artifact_path",
        &root,
    );
    assert_path(pack_schema_path, "journey_script_pack.schema_path", &root);
    assert_path(pack_script_path, "journey_script_pack.script_path", &root);
    assert!(
        regression_harness_command.contains("--non-interactive"),
        "journey script pack harness command should be non-interactive"
    );
    assert!(
        regression_harness_command.contains("--journey-id all"),
        "journey script pack harness command should replay all journeys"
    );

    let pack_artifact = load_json(&root.join(pack_artifact_path));
    let pack_schema = load_json(&root.join(pack_schema_path));
    for key in required_string_array(&pack_schema, "required_top_level_keys") {
        assert!(
            pack_artifact.get(key).is_some(),
            "ftui journey script pack artifact missing key `{key}`"
        );
    }
    assert!(
        pack_artifact["non_interactive"]
            .as_bool()
            .expect("ftui journey script pack non_interactive should be bool"),
        "ftui journey script pack should require non_interactive execution"
    );

    let pack_script_source = fs::read_to_string(root.join(pack_script_path))
        .expect("expected readable scripts/run_ftui_e2e_journey_pack.sh");
    assert!(
        pack_script_source.contains("--non-interactive"),
        "ftui journey script should enforce --non-interactive mode"
    );

    let required_pack_journey_keys = required_string_array(&pack_schema, "required_journey_keys");
    let required_path_kinds = required_string_array(&pack_schema, "required_path_kinds")
        .into_iter()
        .collect::<BTreeSet<_>>();
    let required_correctness_checks =
        required_string_array(&pack_schema, "required_correctness_checks")
            .into_iter()
            .collect::<BTreeSet<_>>();
    let pack_journeys = pack_artifact["journeys"]
        .as_array()
        .expect("ftui journey script pack journeys should be array");
    assert!(
        !pack_journeys.is_empty(),
        "ftui journey script pack journeys should be non-empty"
    );
    let mut observed_pack_path_kinds = BTreeSet::new();
    let mut observed_pack_journey_ids = BTreeSet::new();
    for (idx, journey) in pack_journeys.iter().enumerate() {
        for key in &required_pack_journey_keys {
            assert!(
                journey.get(*key).is_some(),
                "ftui journey script pack journeys[{idx}] missing key `{key}`"
            );
        }
        let journey_id = journey["journey_id"]
            .as_str()
            .expect("ftui journey script pack journey_id should be string");
        assert!(
            observed_journey_ids.contains(journey_id),
            "ftui journey script pack journey `{journey_id}` must exist in workflow_map.journeys"
        );
        assert!(
            observed_pack_journey_ids.insert(journey_id.to_owned()),
            "duplicate ftui journey script pack journey `{journey_id}`"
        );
        let path_kind = journey["path_kind"]
            .as_str()
            .expect("ftui journey script pack path_kind should be string");
        assert!(
            required_path_kinds.contains(path_kind),
            "unsupported ftui journey script pack path_kind `{path_kind}`"
        );
        observed_pack_path_kinds.insert(path_kind);

        let replay_command = journey["replay_command"]
            .as_str()
            .expect("ftui journey script pack replay_command should be string");
        assert!(
            replay_command.contains("--non-interactive"),
            "ftui journey script replay command must be non-interactive"
        );
        assert!(
            replay_command.contains(&format!("--journey-id {journey_id}")),
            "ftui journey script replay command should target journey `{journey_id}`"
        );
        assert_path(
            journey["transcript_path"]
                .as_str()
                .expect("ftui journey script pack transcript_path should be string"),
            &format!("ftui journey script pack journeys[{idx}].transcript_path"),
            &root,
        );

        let diagnosis_budget_ms = journey["diagnosis_budget_ms"]
            .as_u64()
            .expect("ftui journey script pack diagnosis_budget_ms should be u64");
        assert!(
            diagnosis_budget_ms > 0,
            "ftui journey script pack diagnosis_budget_ms should be > 0"
        );

        let reason_codes = journey["reason_codes"]
            .as_array()
            .expect("ftui journey script pack reason_codes should be array");
        assert!(
            !reason_codes.is_empty(),
            "ftui journey script pack reason_codes should be non-empty"
        );
        for reason_code in reason_codes {
            assert!(
                !reason_code
                    .as_str()
                    .expect("ftui journey script pack reason_code should be string")
                    .trim()
                    .is_empty(),
                "ftui journey script pack reason_code should be non-empty"
            );
        }

        let correctness_checks = journey["correctness_checks"]
            .as_array()
            .expect("ftui journey script pack correctness_checks should be array")
            .iter()
            .map(|value| {
                value
                    .as_str()
                    .expect("ftui journey script pack correctness check should be string")
            })
            .collect::<BTreeSet<_>>();
        assert!(
            required_correctness_checks.is_subset(&correctness_checks),
            "ftui journey script pack correctness checks should cover required checks"
        );

        let success_criteria = journey["success_criteria"]
            .as_array()
            .expect("ftui journey script pack success_criteria should be array");
        assert!(
            !success_criteria.is_empty(),
            "ftui journey script pack success_criteria should be non-empty"
        );
        for criterion in success_criteria {
            assert!(
                !criterion
                    .as_str()
                    .expect("ftui journey script pack success criterion should be string")
                    .trim()
                    .is_empty(),
                "ftui journey script pack success criterion should be non-empty"
            );
        }
    }
    assert_eq!(
        observed_pack_path_kinds, required_path_kinds,
        "ftui journey script pack should include all required path kinds"
    );
    assert_eq!(
        observed_pack_journey_ids, observed_journey_ids,
        "ftui journey script pack should cover all workflow journeys"
    );

    let transcript_paths = pack_artifact["transcript_paths"]
        .as_object()
        .expect("ftui journey script pack transcript_paths should be object");
    for key in required_string_array(&pack_schema, "required_transcript_paths") {
        assert!(
            transcript_paths.get(key).is_some(),
            "ftui journey script pack transcript_paths missing key `{key}`"
        );
        assert_path(
            transcript_paths[key]
                .as_str()
                .expect("ftui journey script pack transcript path should be string"),
            &format!("ftui journey script pack transcript_paths.{key}"),
            &root,
        );
    }

    let events_path = transcript_paths["events"]
        .as_str()
        .expect("ftui journey script pack transcript_paths.events should be string");
    assert_eq!(
        events_path,
        journey_script_pack["events_path"]
            .as_str()
            .expect("journey_script_pack.events_path should be string"),
        "workflow contract journey_script_pack.events_path should match pack transcript_paths.events"
    );
    let report_path = pack_artifact["triage_report_path"]
        .as_str()
        .expect("ftui journey script pack triage_report_path should be string");
    assert_eq!(
        report_path,
        journey_script_pack["report_path"]
            .as_str()
            .expect("journey_script_pack.report_path should be string"),
        "workflow contract journey_script_pack.report_path should match pack triage_report_path"
    );
    assert_path(
        report_path,
        "ftui journey script pack triage_report_path",
        &root,
    );

    let transcript_rows = load_jsonl(&root.join(events_path));
    assert!(
        !transcript_rows.is_empty(),
        "ftui journey script pack events transcript should be non-empty"
    );
    let required_transcript_event_keys =
        required_string_array(&pack_schema, "required_transcript_event_keys");
    let mut last_ts_unix_ms = 0_u64;
    for (idx, row) in transcript_rows.iter().enumerate() {
        for key in &required_transcript_event_keys {
            assert!(
                row.get(*key).is_some(),
                "ftui journey transcript row [{idx}] missing key `{key}`"
            );
        }
        let ts_unix_ms = row["ts_unix_ms"]
            .as_u64()
            .expect("ftui journey transcript ts_unix_ms should be u64");
        assert!(
            ts_unix_ms >= last_ts_unix_ms,
            "ftui journey transcript rows should be monotonically timestamped"
        );
        last_ts_unix_ms = ts_unix_ms;

        let row_journey_id = row["journey_id"]
            .as_str()
            .expect("ftui journey transcript journey_id should be string");
        assert!(
            observed_pack_journey_ids.contains(row_journey_id),
            "ftui journey transcript row [{idx}] journey_id `{row_journey_id}` unknown"
        );
        let row_path_kind = row["path_kind"]
            .as_str()
            .expect("ftui journey transcript path_kind should be string");
        assert!(
            required_path_kinds.contains(row_path_kind),
            "ftui journey transcript row [{idx}] path_kind `{row_path_kind}` unknown"
        );
        assert!(
            row["replay_command"]
                .as_str()
                .expect("ftui journey transcript replay_command should be string")
                .contains("--non-interactive"),
            "ftui journey transcript replay_command should be non-interactive"
        );
        assert_path(
            row["artifact_ref"]
                .as_str()
                .expect("ftui journey transcript artifact_ref should be string"),
            &format!("ftui journey transcript rows[{idx}].artifact_ref"),
            &root,
        );
    }

    let golden_rows = load_jsonl(
        &root.join(
            transcript_paths["golden"]
                .as_str()
                .expect("ftui journey transcript_paths.golden should be string"),
        ),
    );
    assert!(
        !golden_rows.is_empty(),
        "ftui journey golden transcript should be non-empty"
    );
    assert!(
        golden_rows.iter().all(|row| {
            row["path_kind"]
                .as_str()
                .expect("golden transcript path_kind should be string")
                == "golden"
        }),
        "ftui journey golden transcript should only include golden path rows"
    );
    assert!(
        golden_rows.iter().any(|row| {
            row["event_id"]
                .as_str()
                .expect("golden transcript event_id should be string")
                == "FTUI-EVT-005"
        }),
        "ftui journey golden transcript should include completion event FTUI-EVT-005"
    );

    let failure_rows = load_jsonl(
        &root.join(
            transcript_paths["failure"]
                .as_str()
                .expect("ftui journey transcript_paths.failure should be string"),
        ),
    );
    assert!(
        !failure_rows.is_empty(),
        "ftui journey failure transcript should be non-empty"
    );
    assert!(
        failure_rows.iter().all(|row| {
            row["path_kind"]
                .as_str()
                .expect("failure transcript path_kind should be string")
                == "failure"
        }),
        "ftui journey failure transcript should only include failure path rows"
    );
    assert!(
        failure_rows.iter().any(|row| {
            row["event_id"]
                .as_str()
                .expect("failure transcript event_id should be string")
                == "FTUI-EVT-007"
        }),
        "ftui journey failure transcript should include checksum mismatch FTUI-EVT-007"
    );

    let pack_report = load_json(&root.join(report_path));
    for key in required_string_array(&pack_schema, "required_report_keys") {
        assert!(
            pack_report.get(key).is_some(),
            "ftui journey report missing key `{key}`"
        );
    }
    assert!(
        pack_report["non_interactive"]
            .as_bool()
            .expect("ftui journey report non_interactive should be bool"),
        "ftui journey report should declare non_interactive=true"
    );
    assert_eq!(
        pack_report["status"]
            .as_str()
            .expect("ftui journey report status should be string"),
        "pass",
        "ftui journey report status should be pass"
    );
    assert_eq!(
        pack_report["events_path"]
            .as_str()
            .expect("ftui journey report events_path should be string"),
        events_path,
        "ftui journey report events_path should align with transcript_paths.events"
    );
    let report_results = pack_report["journey_results"]
        .as_array()
        .expect("ftui journey report journey_results should be array");
    assert_eq!(
        report_results.len(),
        pack_journeys.len(),
        "ftui journey report should include result row per journey"
    );
    for (idx, result) in report_results.iter().enumerate() {
        assert!(
            result["within_budget"]
                .as_bool()
                .expect("ftui journey report within_budget should be bool"),
            "ftui journey report journey_results[{idx}] should stay within diagnosis budget"
        );
        assert!(
            result["minimal_reproducer"]["command"]
                .as_str()
                .expect("ftui journey report minimal_reproducer.command should be string")
                .contains("--non-interactive"),
            "ftui journey report minimal_reproducer.command should be non-interactive"
        );
        assert!(
            result["minimal_reproducer"]["non_interactive"]
                .as_bool()
                .expect("ftui journey report minimal_reproducer.non_interactive should be bool"),
            "ftui journey report minimal_reproducer.non_interactive should be true"
        );
    }

    let final_evidence_pack = artifact["final_evidence_pack"]
        .as_object()
        .expect("final_evidence_pack should be object");
    for key in required_string_array(&schema, "required_final_evidence_pack_keys") {
        assert!(
            final_evidence_pack.get(key).is_some(),
            "final_evidence_pack missing key `{key}`"
        );
    }
    let final_pack_artifact_path = final_evidence_pack["artifact_path"]
        .as_str()
        .expect("final_evidence_pack.artifact_path should be string");
    let final_pack_schema_path = final_evidence_pack["schema_path"]
        .as_str()
        .expect("final_evidence_pack.schema_path should be string");
    let final_pack_review_command = final_evidence_pack["review_command"]
        .as_str()
        .expect("final_evidence_pack.review_command should be string");
    let final_pack_signoff_gate = final_evidence_pack["signoff_gate"]
        .as_str()
        .expect("final_evidence_pack.signoff_gate should be string");
    assert_path(
        final_pack_artifact_path,
        "final_evidence_pack.artifact_path",
        &root,
    );
    assert_path(
        final_pack_schema_path,
        "final_evidence_pack.schema_path",
        &root,
    );
    assert!(
        final_pack_review_command.contains("ftui_workflow_event_contract_gate"),
        "final_evidence_pack.review_command should reference ftui_workflow_event_contract_gate"
    );
    assert!(
        !final_pack_signoff_gate.trim().is_empty(),
        "final_evidence_pack.signoff_gate should be non-empty"
    );

    let final_pack_artifact = load_json(&root.join(final_pack_artifact_path));
    let final_pack_schema = load_json(&root.join(final_pack_schema_path));
    for key in required_string_array(&final_pack_schema, "required_top_level_keys") {
        assert!(
            final_pack_artifact.get(key).is_some(),
            "ftui final evidence pack missing key `{key}`"
        );
    }

    let evidence_inventory = final_pack_artifact["evidence_inventory"]
        .as_object()
        .expect("ftui final evidence pack evidence_inventory should be object");
    for key in required_string_array(&final_pack_schema, "required_evidence_inventory_keys") {
        assert!(
            evidence_inventory.get(key).is_some(),
            "ftui final evidence pack evidence_inventory missing key `{key}`"
        );
    }

    let contract_artifacts = evidence_inventory["contract_artifacts"]
        .as_array()
        .expect("ftui final evidence pack contract_artifacts should be array");
    assert!(
        !contract_artifacts.is_empty(),
        "ftui final evidence pack contract_artifacts should be non-empty"
    );
    for (idx, path_text) in contract_artifacts.iter().enumerate() {
        assert_path(
            path_text.as_str().unwrap_or_else(|| {
                panic!("ftui final evidence pack contract_artifacts[{idx}] should be string")
            }),
            &format!("ftui final evidence pack contract_artifacts[{idx}]"),
            &root,
        );
    }
    assert!(
        contract_artifacts.iter().any(|entry| {
            entry.as_str() == Some("artifacts/ftui/v1/ftui_workflow_event_contract_v1.json")
        }),
        "ftui final evidence pack contract_artifacts should include workflow contract artifact"
    );
    assert!(
        contract_artifacts
            .iter()
            .any(|entry| entry.as_str() == Some(pack_artifact_path)),
        "ftui final evidence pack contract_artifacts should include journey script pack artifact"
    );

    let implementation_artifacts = evidence_inventory["implementation_artifacts"]
        .as_array()
        .expect("ftui final evidence pack implementation_artifacts should be array");
    assert!(
        !implementation_artifacts.is_empty(),
        "ftui final evidence pack implementation_artifacts should be non-empty"
    );
    for (idx, path_text) in implementation_artifacts.iter().enumerate() {
        assert_path(
            path_text.as_str().unwrap_or_else(|| {
                panic!("ftui final evidence pack implementation_artifacts[{idx}] should be string")
            }),
            &format!("ftui final evidence pack implementation_artifacts[{idx}]"),
            &root,
        );
    }

    let artifact_bundle_paths = evidence_inventory["artifact_bundle_paths"]
        .as_array()
        .expect("ftui final evidence pack artifact_bundle_paths should be array");
    assert!(
        !artifact_bundle_paths.is_empty(),
        "ftui final evidence pack artifact_bundle_paths should be non-empty"
    );
    for (idx, path_text) in artifact_bundle_paths.iter().enumerate() {
        assert_path(
            path_text.as_str().unwrap_or_else(|| {
                panic!("ftui final evidence pack artifact_bundle_paths[{idx}] should be string")
            }),
            &format!("ftui final evidence pack artifact_bundle_paths[{idx}]"),
            &root,
        );
    }
    assert!(
        artifact_bundle_paths
            .iter()
            .any(|entry| entry.as_str() == Some(events_path)),
        "ftui final evidence pack artifact_bundle_paths should include journey events transcript"
    );
    assert!(
        artifact_bundle_paths
            .iter()
            .any(|entry| entry.as_str() == Some(report_path)),
        "ftui final evidence pack artifact_bundle_paths should include journey report"
    );

    let test_artifacts = evidence_inventory["test_artifacts"]
        .as_object()
        .expect("ftui final evidence pack test_artifacts should be object");
    let required_test_entry_keys =
        required_string_array(&final_pack_schema, "required_test_entry_keys");
    for category in required_string_array(&final_pack_schema, "required_test_artifact_keys") {
        let entries = test_artifacts[category].as_array().unwrap_or_else(|| {
            panic!("ftui final evidence pack test_artifacts.{category} should be array")
        });
        assert!(
            !entries.is_empty(),
            "ftui final evidence pack test_artifacts.{category} should be non-empty"
        );
        for (entry_idx, entry) in entries.iter().enumerate() {
            for key in &required_test_entry_keys {
                assert!(
                    entry.get(*key).is_some(),
                    "ftui final evidence pack test_artifacts.{category}[{entry_idx}] missing key `{key}`"
                );
            }
            let evidence_path = entry["evidence_path"].as_str().unwrap_or_else(|| {
                panic!("ftui final evidence pack test_artifacts.{category}[{entry_idx}].evidence_path should be string")
            });
            assert_path(
                evidence_path,
                &format!(
                    "ftui final evidence pack test_artifacts.{category}[{entry_idx}].evidence_path"
                ),
                &root,
            );
            let replay_command = entry["replay_command"].as_str().unwrap_or_else(|| {
                panic!("ftui final evidence pack test_artifacts.{category}[{entry_idx}].replay_command should be string")
            });
            assert!(
                !replay_command.trim().is_empty(),
                "ftui final evidence pack test_artifacts.{category}[{entry_idx}] replay_command should be non-empty"
            );
            if category == "e2e" {
                assert!(
                    replay_command.contains("--non-interactive"),
                    "ftui final evidence pack e2e replay commands must be non-interactive"
                );
            }
        }
    }

    let perf_impact_notes = final_pack_artifact["perf_impact_notes"]
        .as_object()
        .expect("ftui final evidence pack perf_impact_notes should be object");
    for key in required_string_array(&final_pack_schema, "required_perf_impact_keys") {
        assert!(
            perf_impact_notes.get(key).is_some(),
            "ftui final evidence pack perf_impact_notes missing key `{key}`"
        );
    }
    let baseline_artifact_paths = perf_impact_notes["baseline_artifact_paths"]
        .as_array()
        .expect("ftui final evidence pack baseline_artifact_paths should be array");
    assert!(
        !baseline_artifact_paths.is_empty(),
        "ftui final evidence pack baseline_artifact_paths should be non-empty"
    );
    for (idx, path_text) in baseline_artifact_paths.iter().enumerate() {
        assert_path(
            path_text.as_str().unwrap_or_else(|| {
                panic!("ftui final evidence pack baseline_artifact_paths[{idx}] should be string")
            }),
            &format!("ftui final evidence pack baseline_artifact_paths[{idx}]"),
            &root,
        );
    }
    assert!(
        !perf_impact_notes["runtime_delta_summary"]
            .as_str()
            .expect("ftui final evidence pack runtime_delta_summary should be string")
            .trim()
            .is_empty(),
        "ftui final evidence pack runtime_delta_summary should be non-empty"
    );
    assert!(
        !perf_impact_notes["memory_delta_summary"]
            .as_str()
            .expect("ftui final evidence pack memory_delta_summary should be string")
            .trim()
            .is_empty(),
        "ftui final evidence pack memory_delta_summary should be non-empty"
    );
    assert!(
        !perf_impact_notes["regression_policy"]
            .as_str()
            .expect("ftui final evidence pack regression_policy should be string")
            .trim()
            .is_empty(),
        "ftui final evidence pack regression_policy should be non-empty"
    );

    assert!(
        !final_pack_artifact["ux_risk_gap_note"]
            .as_str()
            .expect("ftui final evidence pack ux_risk_gap_note should be string")
            .trim()
            .is_empty(),
        "ftui final evidence pack ux_risk_gap_note should be non-empty"
    );

    let residual_risks = final_pack_artifact["residual_ux_risk_register"]
        .as_array()
        .expect("ftui final evidence pack residual_ux_risk_register should be array");
    assert!(
        !residual_risks.is_empty(),
        "ftui final evidence pack residual_ux_risk_register should be non-empty"
    );
    let required_risk_keys = required_string_array(&final_pack_schema, "required_risk_keys");
    let allowed_risk_severity = required_string_array(&final_pack_schema, "allowed_risk_severity")
        .into_iter()
        .collect::<BTreeSet<_>>();
    let allowed_risk_status = required_string_array(&final_pack_schema, "allowed_risk_status")
        .into_iter()
        .collect::<BTreeSet<_>>();
    let mut last_priority_rank = 0_u64;
    let mut observed_risk_ids = BTreeSet::new();
    for (idx, risk) in residual_risks.iter().enumerate() {
        for key in &required_risk_keys {
            assert!(
                risk.get(*key).is_some(),
                "ftui final evidence pack residual_ux_risk_register[{idx}] missing key `{key}`"
            );
        }
        let risk_id = risk["risk_id"]
            .as_str()
            .expect("ftui final evidence pack risk_id should be string");
        assert!(
            observed_risk_ids.insert(risk_id.to_owned()),
            "duplicate ftui final evidence pack risk_id `{risk_id}`"
        );
        let severity = risk["severity"]
            .as_str()
            .expect("ftui final evidence pack risk severity should be string");
        assert!(
            allowed_risk_severity.contains(severity),
            "unsupported ftui final evidence pack risk severity `{severity}`"
        );
        let status = risk["status"]
            .as_str()
            .expect("ftui final evidence pack risk status should be string");
        assert!(
            allowed_risk_status.contains(status),
            "unsupported ftui final evidence pack risk status `{status}`"
        );
        let priority_rank = risk["priority_rank"]
            .as_u64()
            .expect("ftui final evidence pack priority_rank should be u64");
        assert!(
            priority_rank > last_priority_rank,
            "ftui final evidence pack priority_rank should be strictly increasing"
        );
        last_priority_rank = priority_rank;
        assert!(
            !risk["symptom"]
                .as_str()
                .expect("ftui final evidence pack symptom should be string")
                .trim()
                .is_empty(),
            "ftui final evidence pack risk symptom should be non-empty"
        );
        assert!(
            !risk["mitigation"]
                .as_str()
                .expect("ftui final evidence pack mitigation should be string")
                .trim()
                .is_empty(),
            "ftui final evidence pack risk mitigation should be non-empty"
        );
        let affected_journey_ids = risk["affected_journey_ids"]
            .as_array()
            .expect("ftui final evidence pack affected_journey_ids should be array");
        assert!(
            !affected_journey_ids.is_empty(),
            "ftui final evidence pack affected_journey_ids should be non-empty"
        );
        for journey_id in affected_journey_ids {
            let journey_id = journey_id
                .as_str()
                .expect("ftui final evidence pack affected journey id should be string");
            assert!(
                observed_journey_ids.contains(journey_id),
                "ftui final evidence pack affected_journey_id `{journey_id}` must exist in workflow_map.journeys"
            );
        }
        let verification_artifacts = risk["verification_artifacts"]
            .as_array()
            .expect("ftui final evidence pack verification_artifacts should be array");
        assert!(
            !verification_artifacts.is_empty(),
            "ftui final evidence pack verification_artifacts should be non-empty"
        );
        for (artifact_idx, path_text) in verification_artifacts.iter().enumerate() {
            assert_path(
                path_text.as_str().unwrap_or_else(|| {
                    panic!("ftui final evidence pack verification_artifacts[{artifact_idx}] should be string")
                }),
                &format!("ftui final evidence pack residual_ux_risk_register[{idx}].verification_artifacts[{artifact_idx}]"),
                &root,
            );
        }
    }

    let audit_checklist = final_pack_artifact["audit_checklist"]
        .as_array()
        .expect("ftui final evidence pack audit_checklist should be array");
    let required_audit_checklist_keys =
        required_string_array(&final_pack_schema, "required_audit_checklist_keys");
    let required_audit_requirements =
        required_string_array(&final_pack_schema, "required_audit_requirements")
            .into_iter()
            .collect::<BTreeSet<_>>();
    let mut observed_audit_requirements = BTreeSet::new();
    for (idx, row) in audit_checklist.iter().enumerate() {
        for key in &required_audit_checklist_keys {
            assert!(
                row.get(*key).is_some(),
                "ftui final evidence pack audit_checklist[{idx}] missing key `{key}`"
            );
        }
        let requirement = row["requirement"]
            .as_str()
            .expect("ftui final evidence pack audit requirement should be string");
        assert!(
            required_audit_requirements.contains(requirement),
            "unsupported ftui final evidence pack audit requirement `{requirement}`"
        );
        assert!(
            observed_audit_requirements.insert(requirement.to_owned()),
            "duplicate ftui final evidence pack audit requirement `{requirement}`"
        );
        assert_eq!(
            row["status"]
                .as_str()
                .expect("ftui final evidence pack audit status should be string"),
            "pass",
            "ftui final evidence pack audit status must be pass"
        );
        let evidence_refs = row["evidence_refs"]
            .as_array()
            .expect("ftui final evidence pack audit evidence_refs should be array");
        assert!(
            !evidence_refs.is_empty(),
            "ftui final evidence pack audit evidence_refs should be non-empty"
        );
        for (ref_idx, path_text) in evidence_refs.iter().enumerate() {
            assert_path(
                path_text.as_str().unwrap_or_else(|| {
                    panic!(
                        "ftui final evidence pack audit evidence_refs[{ref_idx}] should be string"
                    )
                }),
                &format!(
                    "ftui final evidence pack audit_checklist[{idx}].evidence_refs[{ref_idx}]"
                ),
                &root,
            );
        }
    }
    assert_eq!(
        observed_audit_requirements,
        required_audit_requirements
            .iter()
            .map(|value| (*value).to_owned())
            .collect(),
        "ftui final evidence pack audit checklist should cover every required audit requirement"
    );

    let reviewer_validation_package = final_pack_artifact["reviewer_validation_package"]
        .as_object()
        .expect("ftui final evidence pack reviewer_validation_package should be object");
    for key in required_string_array(&final_pack_schema, "required_reviewer_package_keys") {
        assert!(
            reviewer_validation_package.get(key).is_some(),
            "ftui final evidence pack reviewer_validation_package missing key `{key}`"
        );
    }
    assert!(
        reviewer_validation_package["signoff_ready"]
            .as_bool()
            .expect("ftui final evidence pack signoff_ready should be bool"),
        "ftui final evidence pack signoff_ready should be true"
    );
    let review_scope = reviewer_validation_package["review_scope"]
        .as_array()
        .expect("ftui final evidence pack review_scope should be array");
    assert!(
        !review_scope.is_empty(),
        "ftui final evidence pack review_scope should be non-empty"
    );
    let independent_replay_command = reviewer_validation_package["independent_replay_command"]
        .as_str()
        .expect("ftui final evidence pack independent_replay_command should be string");
    assert!(
        independent_replay_command.contains("--non-interactive"),
        "ftui final evidence pack independent_replay_command should be non-interactive"
    );
    assert_eq!(
        independent_replay_command, regression_harness_command,
        "ftui final evidence pack independent_replay_command should align with journey script harness command"
    );
    let independent_review_steps = reviewer_validation_package["independent_review_steps"]
        .as_array()
        .expect("ftui final evidence pack independent_review_steps should be array");
    assert!(
        independent_review_steps.len() >= 3,
        "ftui final evidence pack independent_review_steps should provide at least three steps"
    );
    for (idx, step) in independent_review_steps.iter().enumerate() {
        assert!(
            !step
                .as_str()
                .unwrap_or_else(|| {
                    panic!(
                        "ftui final evidence pack independent_review_steps[{idx}] should be string"
                    )
                })
                .trim()
                .is_empty(),
            "ftui final evidence pack independent_review_steps[{idx}] should be non-empty"
        );
    }
    let traceability_proof_refs = reviewer_validation_package["traceability_proof_refs"]
        .as_array()
        .expect("ftui final evidence pack traceability_proof_refs should be array");
    assert!(
        !traceability_proof_refs.is_empty(),
        "ftui final evidence pack traceability_proof_refs should be non-empty"
    );
    for (idx, path_text) in traceability_proof_refs.iter().enumerate() {
        assert_path(
            path_text.as_str().unwrap_or_else(|| {
                panic!("ftui final evidence pack traceability_proof_refs[{idx}] should be string")
            }),
            &format!("ftui final evidence pack traceability_proof_refs[{idx}]"),
            &root,
        );
    }
    assert!(
        traceability_proof_refs.iter().any(|entry| {
            entry.as_str() == Some("artifacts/ftui/v1/ftui_workflow_event_contract_v1.json")
        }),
        "ftui final evidence pack traceability_proof_refs should include workflow contract artifact"
    );
    assert!(
        traceability_proof_refs
            .iter()
            .any(|entry| entry.as_str() == Some(final_pack_artifact_path)),
        "ftui final evidence pack traceability_proof_refs should include final evidence pack artifact"
    );

    let runtime_source = fs::read_to_string(root.join("crates/fnx-runtime/src/lib.rs"))
        .expect("expected readable crates/fnx-runtime/src/lib.rs");
    assert!(
        runtime_source.contains("pub mod ftui_bridge"),
        "fnx-runtime should expose ftui_bridge module"
    );
    assert!(
        runtime_source.contains("ftui-integration-enabled"),
        "fnx-runtime ftui bridge marker should be present"
    );

    let runtime_cargo = fs::read_to_string(root.join("crates/fnx-runtime/Cargo.toml"))
        .expect("expected readable crates/fnx-runtime/Cargo.toml");
    assert!(
        runtime_cargo.contains("ftui-integration"),
        "fnx-runtime Cargo.toml should expose ftui-integration feature"
    );
    assert!(
        runtime_cargo.contains("ftui = { path = \"/dp/frankentui/crates/ftui\""),
        "fnx-runtime Cargo.toml should pin local ftui dependency path"
    );

    assert!(
        events_seen_in_steps.contains("FTUI-EVT-005"),
        "golden path should include completion event FTUI-EVT-005"
    );
    assert!(
        events_seen_in_steps.contains("FTUI-EVT-007"),
        "failure path should include checksum mismatch event FTUI-EVT-007"
    );
}
