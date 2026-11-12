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

#[test]
fn doc_pass03_state_mapping_has_required_components_and_invariants() {
    let root = repo_root();
    let artifact =
        load_json(&root.join("artifacts/docs/v1/doc_pass03_data_model_state_invariant_v1.json"));
    let schema = load_json(
        &root.join("artifacts/docs/schema/v1/doc_pass03_data_model_state_invariant_schema_v1.json"),
    );

    let required_top_keys = schema["required_top_level_keys"]
        .as_array()
        .expect("required_top_level_keys should be array");
    for key in required_top_keys {
        let key_name = key.as_str().expect("schema key should be string");
        assert!(
            artifact.get(key_name).is_some(),
            "artifact missing top-level key `{key_name}`"
        );
    }

    let components = artifact["components"]
        .as_array()
        .expect("components should be array");
    assert!(
        components.len() >= 5,
        "expected at least five core components in DOC-PASS-03 mapping"
    );

    let component_ids = components
        .iter()
        .map(|row| {
            row["component_id"]
                .as_str()
                .expect("component_id should be string")
        })
        .collect::<BTreeSet<_>>();
    let expected = BTreeSet::from([
        "graph_store",
        "view_cache",
        "dispatch_registry",
        "conversion_readwrite",
        "algo_conformance",
    ]);
    assert_eq!(component_ids, expected, "DOC-PASS-03 component set drifted");

    for component in components {
        let cid = component["component_id"]
            .as_str()
            .expect("component_id should be string");

        let transitions = component["state_transitions"]
            .as_array()
            .expect("state_transitions should be array");
        assert!(
            !transitions.is_empty(),
            "component {cid} must define at least one transition"
        );
        for transition in transitions {
            for key in [
                "from_state",
                "to_state",
                "trigger",
                "action",
                "failure_behavior",
            ] {
                assert!(
                    transition.get(key).is_some(),
                    "component {cid} transition missing key `{key}`"
                );
            }
            let guards = transition["guards"]
                .as_array()
                .expect("transition guards should be array");
            assert!(
                !guards.is_empty(),
                "component {cid} transition guards must be non-empty"
            );
        }

        let invariants = component["invariants"]
            .as_array()
            .expect("invariants should be array");
        assert!(
            !invariants.is_empty(),
            "component {cid} must define at least one invariant"
        );
        for invariant in invariants {
            for key in [
                "invariant_id",
                "statement",
                "strict_mode_response",
                "hardened_mode_response",
            ] {
                assert!(
                    invariant.get(key).is_some(),
                    "component {cid} invariant missing key `{key}`"
                );
            }
            let test_hooks = invariant["test_hooks"]
                .as_array()
                .expect("invariant test_hooks should be array");
            assert!(
                !test_hooks.is_empty(),
                "component {cid} invariant test_hooks must be non-empty"
            );
        }

        let hooks = component["verification_hooks"]
            .as_object()
            .expect("verification_hooks should be object");
        for key in ["unit", "property", "differential", "e2e"] {
            let values = hooks[key]
                .as_array()
                .expect("verification hook values should be array");
            assert!(
                !values.is_empty(),
                "component {cid} verification hook `{key}` should be non-empty"
            );
        }
    }

    let ev_score = artifact["alien_uplift_contract_card"]["ev_score"]
        .as_f64()
        .expect("ev_score should be numeric");
    assert!(ev_score >= 2.0, "ev_score must be >= 2.0");
}
