use fnx_conformance::{HarnessConfig, run_smoke};
use serde_json::Value;
use std::fs;
use std::path::{Path, PathBuf};

fn repo_root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../..")
}

fn load_json(path: &Path) -> Value {
    let raw = fs::read_to_string(path)
        .unwrap_or_else(|err| panic!("failed to read {}: {err}", path.display()));
    serde_json::from_str(&raw)
        .unwrap_or_else(|err| panic!("failed to parse {}: {err}", path.display()))
}

#[test]
fn historical_regression_corpus_has_provenance_and_passes_smoke() {
    let regressions_root = repo_root().join("crates/fnx-conformance/fixtures/regressions");
    assert!(
        regressions_root.is_dir(),
        "regression corpus root should exist at {}",
        regressions_root.display()
    );

    let mut regression_dirs = fs::read_dir(&regressions_root)
        .expect("regressions root should be readable")
        .filter_map(Result::ok)
        .map(|entry| entry.path())
        .filter(|path| path.is_dir())
        .collect::<Vec<_>>();
    regression_dirs.sort();
    assert!(
        !regression_dirs.is_empty(),
        "regression corpus should contain at least one provenance-linked bead directory"
    );

    let mut expected_fixture_names = Vec::new();
    for dir in &regression_dirs {
        let bead_id = dir
            .file_name()
            .and_then(|name| name.to_str())
            .expect("regression directory should have utf-8 name");
        assert!(
            bead_id.starts_with("franken_networkx-"),
            "regression directory {bead_id} should be named after its originating bead"
        );

        let provenance_path = dir.join("provenance.json");
        assert!(
            provenance_path.exists(),
            "regression directory {bead_id} should contain provenance.json"
        );
        let provenance = load_json(&provenance_path);
        assert_eq!(
            provenance["originating_bead_id"].as_str(),
            Some(bead_id),
            "provenance originating_bead_id should match directory name"
        );
        assert!(
            provenance["title"]
                .as_str()
                .is_some_and(|value| !value.trim().is_empty()),
            "provenance title should be present for {bead_id}"
        );
        assert!(
            provenance["close_reason"]
                .as_str()
                .is_some_and(|value| !value.trim().is_empty()),
            "provenance close_reason should be present for {bead_id}"
        );

        let fixture_list = provenance["fixtures"]
            .as_array()
            .expect("provenance fixtures should be an array");
        assert!(
            !fixture_list.is_empty(),
            "provenance fixtures should list at least one regression fixture for {bead_id}"
        );

        for fixture_entry in fixture_list {
            let fixture_name = fixture_entry
                .as_str()
                .expect("fixture list entries should be strings");
            let fixture_path = dir.join(fixture_name);
            assert!(
                fixture_path.exists(),
                "listed regression fixture should exist: {}",
                fixture_path.display()
            );

            let fixture = load_json(&fixture_path);
            let fixture_id = fixture["fixture_id"]
                .as_str()
                .expect("fixture_id should be a string");
            assert!(
                fixture_id.contains(bead_id),
                "fixture_id {fixture_id} should retain bead provenance {bead_id}"
            );

            expected_fixture_names.push(
                fixture_path
                    .strip_prefix(&regressions_root)
                    .expect("fixture should be under regressions root")
                    .to_string_lossy()
                    .to_string(),
            );
        }
    }

    let mut cfg = HarnessConfig::default_paths();
    cfg.fixture_root = regressions_root.clone();
    cfg.report_root = None;

    let report = run_smoke(&cfg);
    if report.mismatch_count > 0 {
        for fixture in &report.fixture_reports {
            if !fixture.mismatches.is_empty() {
                println!(
                    "Fixture {} failed with {} mismatches: {:#?}",
                    fixture.fixture_id,
                    fixture.mismatches.len(),
                    fixture.mismatches
                );
            }
        }
    }
    assert_eq!(
        report.mismatch_count, 0,
        "historical regression corpus should replay without mismatches"
    );
    assert_eq!(
        report.fixture_count,
        expected_fixture_names.len(),
        "run_smoke should execute every provenance-listed regression fixture"
    );

    let mut observed_fixture_names = report
        .fixture_reports
        .iter()
        .map(|fixture| fixture.fixture_name.clone())
        .collect::<Vec<_>>();
    observed_fixture_names.sort();
    expected_fixture_names.sort();

    assert_eq!(
        observed_fixture_names, expected_fixture_names,
        "smoke runner should cover the entire historical regression corpus"
    );
    assert!(
        report.fixture_reports.iter().all(|fixture| fixture.passed),
        "all historical regression fixtures should pass in the smoke harness"
    );
}
