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
fn doc_pass01_module_cartography_covers_workspace_and_layers() {
    let root = repo_root();
    let artifact = load_json(&root.join("artifacts/docs/v1/doc_pass01_module_cartography_v1.json"));
    let schema = load_json(
        &root.join("artifacts/docs/schema/v1/doc_pass01_module_cartography_schema_v1.json"),
    );

    let required_top_keys = schema["required_top_level_keys"]
        .as_array()
        .expect("required_top_level_keys should be an array");
    for key in required_top_keys {
        let key_name = key.as_str().expect("schema key should be string");
        assert!(
            artifact.get(key_name).is_some(),
            "artifact missing top-level key `{key_name}`"
        );
    }

    let modules = artifact["module_cartography"]
        .as_array()
        .expect("module_cartography should be an array");
    assert!(
        !modules.is_empty(),
        "module_cartography should contain workspace crates"
    );

    let module_names = modules
        .iter()
        .map(|module| {
            module["crate_name"]
                .as_str()
                .expect("crate_name should be string")
        })
        .collect::<BTreeSet<_>>();
    let expected = BTreeSet::from([
        "fnx-algorithms",
        "fnx-classes",
        "fnx-conformance",
        "fnx-convert",
        "fnx-dispatch",
        "fnx-durability",
        "fnx-generators",
        "fnx-readwrite",
        "fnx-runtime",
        "fnx-views",
    ]);
    assert_eq!(module_names, expected, "workspace crate coverage drifted");

    let required_module_keys = schema["required_module_keys"]
        .as_array()
        .expect("required_module_keys should be array")
        .iter()
        .map(|value| value.as_str().expect("module key should be string"))
        .collect::<Vec<_>>();
    let required_hook_keys = schema["required_verification_hook_keys"]
        .as_array()
        .expect("required_verification_hook_keys should be array")
        .iter()
        .map(|value| value.as_str().expect("hook key should be string"))
        .collect::<Vec<_>>();
    let required_policy_keys = schema["required_policy_keys"]
        .as_array()
        .expect("required_policy_keys should be array")
        .iter()
        .map(|value| value.as_str().expect("policy key should be string"))
        .collect::<Vec<_>>();

    for module in modules {
        for key in &required_module_keys {
            assert!(
                module.get(*key).is_some(),
                "module {:?} missing key `{key}`",
                module["crate_name"]
            );
        }
        let crate_name = module["crate_name"]
            .as_str()
            .expect("crate_name should be string");

        let manifest_path = root.join(
            module["manifest_path"]
                .as_str()
                .expect("manifest_path should be string"),
        );
        assert!(
            manifest_path.exists(),
            "{crate_name} manifest path missing: {}",
            manifest_path.display()
        );
        let source_root = root.join(
            module["source_root"]
                .as_str()
                .expect("source_root should be string"),
        );
        assert!(
            source_root.exists(),
            "{crate_name} source root missing: {}",
            source_root.display()
        );

        let deps = module["depends_on"]
            .as_array()
            .expect("depends_on should be array");
        for dep in deps {
            let dep_name = dep.as_str().expect("depends_on entry should be string");
            assert!(
                module_names.contains(dep_name),
                "{crate_name} depends on unknown workspace crate {dep_name}"
            );
        }

        let hooks = module["verification_hooks"]
            .as_object()
            .expect("verification_hooks should be object");
        for key in &required_hook_keys {
            let values = hooks[*key]
                .as_array()
                .expect("verification hook values should be array");
            assert!(
                !values.is_empty(),
                "{crate_name} verification hook `{key}` should be non-empty"
            );
        }

        let policy = module["strict_hardened_policy"]
            .as_object()
            .expect("strict_hardened_policy should be object");
        for key in &required_policy_keys {
            let value = policy[*key]
                .as_str()
                .expect("strict_hardened_policy values should be string");
            assert!(
                !value.trim().is_empty(),
                "{crate_name} strict_hardened_policy `{key}` must be non-empty"
            );
        }

        let hidden_refs = module["known_hidden_couplings"]
            .as_array()
            .expect("known_hidden_couplings should be array");
        assert!(
            !hidden_refs.is_empty(),
            "{crate_name} should reference at least one hidden coupling"
        );
    }

    let edges = artifact["cross_module_dependency_map"]
        .as_array()
        .expect("cross_module_dependency_map should be array");
    assert!(
        !edges.is_empty(),
        "dependency edge inventory must be non-empty"
    );
    for edge in edges {
        let from_crate = edge["from_crate"]
            .as_str()
            .expect("edge from_crate should be string");
        let to_crate = edge["to_crate"]
            .as_str()
            .expect("edge to_crate should be string");
        assert!(
            module_names.contains(from_crate),
            "edge references unknown from_crate {from_crate}"
        );
        assert!(
            module_names.contains(to_crate),
            "edge references unknown to_crate {to_crate}"
        );
    }

    let violations = artifact["layering_violations"]
        .as_array()
        .expect("layering_violations should be array");
    assert!(
        violations.is_empty(),
        "expected zero layering violations, got {violations:?}"
    );

    let hidden_hotspots = artifact["hidden_coupling_hotspots"]
        .as_array()
        .expect("hidden_coupling_hotspots should be array");
    assert!(
        hidden_hotspots.len() >= 3,
        "hidden_coupling_hotspots must include at least three entries"
    );
    assert!(
        hidden_hotspots
            .iter()
            .any(|row| row["risk_level"] == "high")
    );

    let ev_score = artifact["alien_uplift_contract_card"]["ev_score"]
        .as_f64()
        .expect("ev_score should be numeric");
    assert!(ev_score >= 2.0, "ev_score must be >= 2.0");
}
