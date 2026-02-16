use fnx_runtime::{
    AsupersyncAdapterMachine, AsupersyncAdapterState, AsupersyncTransferIntent, CompatibilityMode,
};
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

fn assert_metric_block(metric: &Value, ctx: &str, required_keys: &[&str]) {
    let block = metric
        .as_object()
        .unwrap_or_else(|| panic!("{ctx} should be object"));
    for key in required_keys {
        assert!(
            block.get(*key).is_some(),
            "{ctx} missing required key `{key}`"
        );
    }

    let samples = block["samples"]
        .as_array()
        .unwrap_or_else(|| panic!("{ctx}.samples should be array"));
    assert!(!samples.is_empty(), "{ctx}.samples should be non-empty");
    for (idx, sample) in samples.iter().enumerate() {
        assert!(
            sample.as_f64().is_some() || sample.as_i64().is_some() || sample.as_u64().is_some(),
            "{ctx}.samples[{idx}] should be numeric"
        );
    }

    let p50 = block["p50"]
        .as_f64()
        .unwrap_or_else(|| panic!("{ctx}.p50 should be numeric"));
    let p95 = block["p95"]
        .as_f64()
        .unwrap_or_else(|| panic!("{ctx}.p95 should be numeric"));
    let p99 = block["p99"]
        .as_f64()
        .unwrap_or_else(|| panic!("{ctx}.p99 should be numeric"));
    let _mean = block["mean"]
        .as_f64()
        .unwrap_or_else(|| panic!("{ctx}.mean should be numeric"));

    assert!(p95 >= p50, "{ctx}.p95 should be >= p50");
    assert!(p99 >= p95, "{ctx}.p99 should be >= p95");
}

fn base_intent() -> AsupersyncTransferIntent {
    AsupersyncTransferIntent {
        transfer_id: "tx-asup-perf-gate-001".to_owned(),
        artifact_id: "artifacts/e2e/latest/e2e_scenario_matrix_report_v1.json".to_owned(),
        artifact_class: "conformance_fixture_bundle".to_owned(),
        mode: CompatibilityMode::Strict,
        deterministic_seed: 123,
        expected_checksum: "sha256:expected-perf-gate".to_owned(),
        max_attempts: 3,
    }
}

#[test]
fn asupersync_performance_characterization_contract_is_complete_and_safe() {
    let root = repo_root();
    let artifact = load_json(
        &root.join("artifacts/asupersync/v1/asupersync_performance_characterization_v1.json"),
    );
    let schema = load_json(&root.join(
        "artifacts/asupersync/schema/v1/asupersync_performance_characterization_schema_v1.json",
    ));

    for key in required_string_array(&schema, "required_top_level_keys") {
        assert!(
            artifact.get(key).is_some(),
            "artifact missing top-level key `{key}`"
        );
    }

    let corpus = artifact["measurement_corpus"]
        .as_object()
        .expect("measurement_corpus should be object");
    for key in required_string_array(&schema, "required_measurement_corpus_keys") {
        assert!(
            corpus.get(key).is_some(),
            "measurement_corpus missing key `{key}`"
        );
    }
    assert!(
        corpus["command"]
            .as_str()
            .expect("measurement_corpus.command should be string")
            .contains("rch exec --"),
        "measurement_corpus.command should use rch"
    );
    let run_count = usize::try_from(
        corpus["runs"]
            .as_u64()
            .expect("measurement_corpus.runs should be u64"),
    )
    .expect("measurement_corpus.runs should fit usize");
    assert!(run_count >= 5, "measurement_corpus.runs should be >= 5");

    let lever = artifact["optimization_lever"]
        .as_object()
        .expect("optimization_lever should be object");
    for key in required_string_array(&schema, "required_optimization_lever_keys") {
        assert!(
            lever.get(key).is_some(),
            "optimization_lever missing key `{key}`"
        );
    }
    let code_paths = lever["code_paths"]
        .as_array()
        .expect("optimization_lever.code_paths should be array");
    assert!(
        !code_paths.is_empty(),
        "optimization_lever.code_paths should be non-empty"
    );
    for (idx, path_value) in code_paths.iter().enumerate() {
        let path_text = path_value
            .as_str()
            .unwrap_or_else(|| panic!("optimization_lever.code_paths[{idx}] should be string"));
        assert_path(
            path_text,
            &format!("optimization_lever.code_paths[{idx}]"),
            &root,
        );
    }

    let required_metrics = required_string_array(&schema, "required_metrics_keys");
    let required_metric_block_keys = required_string_array(&schema, "required_metric_block_keys");

    for (scope, metrics_obj) in [
        (
            "baseline_metrics",
            artifact["baseline_metrics"]
                .as_object()
                .expect("baseline_metrics should be object"),
        ),
        (
            "candidate_metrics",
            artifact["candidate_metrics"]
                .as_object()
                .expect("candidate_metrics should be object"),
        ),
    ] {
        for metric_key in &required_metrics {
            assert!(
                metrics_obj.get(*metric_key).is_some(),
                "{scope} missing metric `{metric_key}`"
            );
            assert_metric_block(
                &metrics_obj[*metric_key],
                &format!("{scope}.{metric_key}"),
                &required_metric_block_keys,
            );
        }

        let elapsed_samples = metrics_obj["elapsed_s"]["samples"]
            .as_array()
            .expect("elapsed_s.samples should be array");
        assert_eq!(
            elapsed_samples.len(),
            run_count,
            "{scope}.elapsed_s.samples length should match measurement_corpus.runs"
        );
    }

    let stable = artifact["stable_window_metrics"]
        .as_object()
        .expect("stable_window_metrics should be object");
    for key in required_string_array(&schema, "required_stable_window_metric_keys") {
        assert!(
            stable.get(key).is_some(),
            "stable_window_metrics missing key `{key}`"
        );
        let scope_metrics = stable[key]
            .as_object()
            .unwrap_or_else(|| panic!("stable_window_metrics.{key} should be object"));
        for metric_key in &required_metrics {
            assert!(
                scope_metrics.get(*metric_key).is_some(),
                "stable_window_metrics.{key} missing metric `{metric_key}`"
            );
            assert_metric_block(
                &scope_metrics[*metric_key],
                &format!("stable_window_metrics.{key}.{metric_key}"),
                &required_metric_block_keys,
            );
        }
    }

    let delta = artifact["delta_summary"]
        .as_object()
        .expect("delta_summary should be object");
    for key in required_string_array(&schema, "required_delta_summary_keys") {
        assert!(
            delta.get(key).is_some(),
            "delta_summary missing key `{key}`"
        );
        assert!(
            delta[key].as_f64().is_some(),
            "delta_summary.{key} should be numeric"
        );
    }

    let gate = artifact["tail_regression_gate"]
        .as_object()
        .expect("tail_regression_gate should be object");
    for key in required_string_array(&schema, "required_tail_regression_gate_keys") {
        assert!(
            gate.get(key).is_some(),
            "tail_regression_gate missing key `{key}`"
        );
    }
    assert_eq!(
        gate["status"]
            .as_str()
            .expect("tail_regression_gate.status should be string"),
        "pass",
        "tail_regression_gate.status should be pass"
    );
    assert!(
        !gate["blocked"]
            .as_bool()
            .expect("tail_regression_gate.blocked should be bool"),
        "tail_regression_gate.blocked should be false"
    );

    let latency_threshold = gate["latency_tail_pct_threshold"]
        .as_f64()
        .expect("latency_tail_pct_threshold should be numeric");
    let memory_threshold = gate["memory_tail_pct_threshold"]
        .as_f64()
        .expect("memory_tail_pct_threshold should be numeric");

    for key in ["elapsed_p95_pct", "elapsed_p99_pct"] {
        let value = delta[key]
            .as_f64()
            .unwrap_or_else(|| panic!("delta_summary.{key} should be numeric"));
        assert!(
            value <= latency_threshold,
            "delta_summary.{key} should not exceed latency threshold"
        );
    }
    for key in ["max_rss_p95_pct", "max_rss_p99_pct"] {
        let value = delta[key]
            .as_f64()
            .unwrap_or_else(|| panic!("delta_summary.{key} should be numeric"));
        assert!(
            value <= memory_threshold,
            "delta_summary.{key} should not exceed memory threshold"
        );
    }

    let test_bindings = artifact["test_bindings"]
        .as_array()
        .expect("test_bindings should be array");
    assert!(
        !test_bindings.is_empty(),
        "test_bindings should be non-empty"
    );
    let required_test_binding_keys = required_string_array(&schema, "required_test_binding_keys");
    let required_layers = required_string_array(&schema, "required_test_layers")
        .into_iter()
        .collect::<BTreeSet<_>>();
    let mut observed_layers = BTreeSet::new();
    let mut observed_test_ids = BTreeSet::new();

    for (idx, row) in test_bindings.iter().enumerate() {
        for key in &required_test_binding_keys {
            assert!(
                row.get(*key).is_some(),
                "test_bindings[{idx}] missing key `{key}`"
            );
        }
        let test_id = row["test_id"].as_str().expect("test_id should be string");
        assert!(
            observed_test_ids.insert(test_id),
            "duplicate test_id `{test_id}`"
        );

        let layer = row["layer"].as_str().expect("layer should be string");
        assert!(
            required_layers.contains(layer),
            "unsupported layer `{layer}`"
        );
        observed_layers.insert(layer);

        let artifact_path = row["artifact_path"]
            .as_str()
            .expect("artifact_path should be string");
        assert_path(
            artifact_path,
            &format!("test_bindings[{idx}].artifact_path"),
            &root,
        );

        let replay = row["replay_command"]
            .as_str()
            .expect("replay_command should be string");
        if layer == "e2e" {
            assert!(
                replay.contains("run_phase2c_readiness_e2e.sh"),
                "e2e replay command should run readiness script"
            );
        } else {
            assert!(
                replay.contains("rch exec --"),
                "unit/differential replay commands should use rch"
            );
        }
    }
    assert_eq!(
        observed_layers, required_layers,
        "test_bindings should cover unit/differential/e2e layers"
    );

    let decision = artifact["decision_theoretic_runtime_contract"]
        .as_object()
        .expect("decision_theoretic_runtime_contract should be object");
    for key in required_string_array(&schema, "required_decision_contract_keys") {
        assert!(
            decision.get(key).is_some(),
            "decision_theoretic_runtime_contract missing key `{key}`"
        );
    }

    let loss_budget = decision["loss_budget"]
        .as_object()
        .expect("loss_budget should be object");
    for key in required_string_array(&schema, "required_loss_budget_keys") {
        assert!(
            loss_budget.get(key).is_some(),
            "loss_budget missing key `{key}`"
        );
        assert!(
            loss_budget[key].as_f64().is_some(),
            "loss_budget.{key} should be numeric"
        );
    }

    let safe_mode = decision["safe_mode_fallback"]
        .as_object()
        .expect("safe_mode_fallback should be object");
    for key in required_string_array(&schema, "required_safe_mode_fallback_keys") {
        assert!(
            safe_mode.get(key).is_some(),
            "safe_mode_fallback missing key `{key}`"
        );
    }

    let profile = artifact["profile_first_artifacts"]
        .as_object()
        .expect("profile_first_artifacts should be object");
    for key in required_string_array(&schema, "required_profile_artifact_keys") {
        assert_path(
            profile[key]
                .as_str()
                .expect("profile path should be string"),
            &format!("profile_first_artifacts.{key}"),
            &root,
        );
    }

    let isomorphism = artifact["isomorphism_proof_artifacts"]
        .as_array()
        .expect("isomorphism_proof_artifacts should be array");
    assert!(
        !isomorphism.is_empty(),
        "isomorphism_proof_artifacts should be non-empty"
    );
    for (idx, path_value) in isomorphism.iter().enumerate() {
        assert_path(
            path_value
                .as_str()
                .unwrap_or_else(|| panic!("isomorphism_proof_artifacts[{idx}] should be string")),
            &format!("isomorphism_proof_artifacts[{idx}]"),
            &root,
        );
    }

    let logging = artifact["structured_logging_evidence"]
        .as_array()
        .expect("structured_logging_evidence should be array");
    assert!(
        !logging.is_empty(),
        "structured_logging_evidence should be non-empty"
    );
    for (idx, path_value) in logging.iter().enumerate() {
        assert_path(
            path_value
                .as_str()
                .unwrap_or_else(|| panic!("structured_logging_evidence[{idx}] should be string")),
            &format!("structured_logging_evidence[{idx}]"),
            &root,
        );
    }

    let ev_score = artifact["alien_uplift_contract_card"]["ev_score"]
        .as_f64()
        .expect("alien_uplift_contract_card.ev_score should be numeric");
    assert!(ev_score >= 2.0, "ev_score should be >= 2.0");

    let runtime_source = fs::read_to_string(root.join("crates/fnx-runtime/src/lib.rs"))
        .expect("expected readable runtime source");
    for required_symbol in [
        "transition_capacity(max_attempts: u8)",
        "Vec::with_capacity(transition_capacity)",
    ] {
        assert!(
            runtime_source.contains(required_symbol),
            "runtime source missing required optimization symbol `{required_symbol}`"
        );
    }

    let deterministic_run = || {
        let mut machine =
            AsupersyncAdapterMachine::start(base_intent()).expect("start should pass");
        machine
            .mark_capability_check(true)
            .expect("capability check should pass");
        machine
            .record_chunk_commit(64)
            .expect("chunk commit should pass");
        machine
            .record_transport_interruption()
            .expect("interruption should pass");
        machine
            .apply_resume_cursor(64)
            .expect("resume cursor should pass");
        machine
            .start_checksum_verification()
            .expect("checksum phase should start");
        machine
            .finish_checksum_verification("sha256:expected-perf-gate")
            .expect("checksum should pass");
        machine
    };

    let first = deterministic_run();
    let second = deterministic_run();
    assert_eq!(
        first.transitions(),
        second.transitions(),
        "optimization lever must not change deterministic transition outputs"
    );
    assert_eq!(first.state(), AsupersyncAdapterState::Completed);
}
