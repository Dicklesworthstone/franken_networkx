use fnx_algorithms::{faster_could_be_isomorphic, is_isomorphic};
use fnx_classes::Graph;
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

#[derive(Debug)]
struct RegressionFixtureTopology {
    fixture_id: String,
    fixture_name: String,
    provenance_bead_ids: Vec<String>,
    graph: Graph,
}

fn load_regression_fixture_topology(
    regressions_root: &Path,
    fixture_path: &Path,
    bead_id: &str,
) -> RegressionFixtureTopology {
    let fixture = load_json(fixture_path);
    let fixture_id = fixture["fixture_id"]
        .as_str()
        .expect("fixture_id should be a string")
        .to_owned();
    let fixture_name = fixture_path
        .strip_prefix(regressions_root)
        .expect("fixture should be under regressions root")
        .to_string_lossy()
        .to_string();

    let mut provenance_bead_ids = fixture["provenance_bead_ids"]
        .as_array()
        .expect("regression fixture should declare provenance_bead_ids")
        .iter()
        .map(|entry| {
            entry
                .as_str()
                .expect("provenance_bead_ids entries should be strings")
                .to_owned()
        })
        .collect::<Vec<_>>();
    assert!(
        !provenance_bead_ids.is_empty(),
        "regression fixture {fixture_id} should list at least one provenance bead id"
    );
    let mut sorted_bead_ids = provenance_bead_ids.clone();
    sorted_bead_ids.sort();
    sorted_bead_ids.dedup();
    assert_eq!(
        provenance_bead_ids, sorted_bead_ids,
        "regression fixture {fixture_id} should keep provenance_bead_ids sorted and duplicate-free"
    );
    assert!(
        provenance_bead_ids.iter().any(|id| id == bead_id),
        "regression fixture {fixture_id} should retain its directory bead id {bead_id} in provenance_bead_ids"
    );

    let mut graph = Graph::strict();
    for node in fixture["expected"]["graph"]["nodes"]
        .as_array()
        .expect("expected.graph.nodes should be an array")
    {
        graph.add_node(
            node.as_str()
                .expect("expected.graph.nodes entries should be strings")
                .to_owned(),
        );
    }
    for edge in fixture["expected"]["graph"]["edges"]
        .as_array()
        .expect("expected.graph.edges should be an array")
    {
        let left = edge["left"]
            .as_str()
            .expect("expected.graph.edges[].left should be a string")
            .to_owned();
        let right = edge["right"]
            .as_str()
            .expect("expected.graph.edges[].right should be a string")
            .to_owned();
        graph
            .add_edge(left.clone(), right.clone())
            .unwrap_or_else(|err| {
                panic!("failed to add expected regression edge ({left}, {right}): {err}")
            });
    }

    RegressionFixtureTopology {
        fixture_id,
        fixture_name,
        provenance_bead_ids: std::mem::take(&mut provenance_bead_ids),
        graph,
    }
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
    let mut regression_topologies = Vec::new();
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
            regression_topologies.push(load_regression_fixture_topology(
                &regressions_root,
                &fixture_path,
                bead_id,
            ));
        }
    }

    for left_idx in 0..regression_topologies.len() {
        for right_idx in (left_idx + 1)..regression_topologies.len() {
            let left = &regression_topologies[left_idx];
            let right = &regression_topologies[right_idx];
            if !faster_could_be_isomorphic(&left.graph, &right.graph) {
                continue;
            }
            assert!(
                !is_isomorphic(&left.graph, &right.graph),
                "historical regression fixtures {} [{}] ({:?}) and {} [{}] ({:?}) are isomorphic duplicates; merge them into one canonical fixture and attach all provenance bead ids to that fixture",
                left.fixture_name,
                left.fixture_id,
                left.provenance_bead_ids,
                right.fixture_name,
                right.fixture_id,
                right.provenance_bead_ids
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
