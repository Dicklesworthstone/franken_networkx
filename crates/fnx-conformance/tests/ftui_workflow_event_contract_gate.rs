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
            observed_journey_ids.insert(journey_id),
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
