//! Planar-embedding oracle gate (reality-check bead
//! rc-planar-embedding-kernel-07rh8, milestone 1).
//!
//! For every graph in `tests/fixtures/planarity_embedding_oracle.json`:
//!
//! 1. The fnx verdict (`planar_embedding_data` returning Some/None) must
//!    match nx's `check_planarity` verdict recorded in the fixture.
//! 2. For planar graphs, the per-node clockwise neighbour orders produced by
//!    the native Boyer-Myrvold embedding assembly must equal nx's
//!    `PlanarEmbedding.get_data()` byte for byte.
//!
//! The fixture records the exact node/edge INSERTION order — the nx embedding
//! depends on it through the `G.copy()` adjacency walk — and the test builds
//! the fnx graph in that same order.
//!
//! STATUS (2026-09-04): milestone-1 parity LANDED — the LrState differential
//! harness (lr_state_matches_nx_lrplanarity_state in fnx-algorithms) proved
//! testing-half state parity, and the full rotation-order comparison runs
//! unignored below (the earlier octahedron anchor divergence was a cw-branch
//! anchor bookkeeping bug, fixed by moving the pre-append dict-last on
//! rotation).

use fnx_algorithms::planar_embedding_data;
use fnx_classes::Graph;
use fnx_runtime::CompatibilityMode;
use serde_json::Value;
use std::fs;
use std::path::PathBuf;

fn repo_root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../..")
}

fn fixture() -> Value {
    let raw =
        fs::read_to_string(repo_root().join("tests/fixtures/planarity_embedding_oracle.json"))
            .expect("planarity embedding oracle fixture should be readable");
    serde_json::from_str(&raw).expect("oracle fixture should be valid JSON")
}

fn build_graph(entry: &Value) -> Graph {
    let mut g = Graph::new(CompatibilityMode::Strict);
    for node in entry["nodes"].as_array().expect("nodes array") {
        let _ = g.add_node(node.as_str().expect("string node label"));
    }
    for edge in entry["edges"].as_array().expect("edges array") {
        let u = edge[0].as_str().expect("edge endpoint");
        let v = edge[1].as_str().expect("edge endpoint");
        g.add_edge(u, v).expect("edge insert");
    }
    g
}

#[test]
fn planar_verdicts_match_networkx_oracle() {
    let fixture = fixture();
    let graphs = fixture["graphs"]
        .as_object()
        .expect("fixture should carry a graphs object");
    let mut planar = 0usize;
    let mut nonplanar = 0usize;
    for (name, entry) in graphs {
        let expect_planar = entry["is_planar"].as_bool().expect("is_planar recorded");
        let graph = build_graph(entry);
        let data = planar_embedding_data(&graph);
        if expect_planar {
            assert!(
                data.is_some(),
                "{name}: fixture records planar but fnx produced no embedding"
            );
            planar += 1;
        } else {
            assert!(
                data.is_none(),
                "{name}: fixture records non-planar but fnx produced an embedding"
            );
            nonplanar += 1;
        }
    }
    assert!(
        planar > 0 && nonplanar > 0,
        "oracle corpus degenerated: {planar} planar / {nonplanar} non-planar"
    );
}

/// Milestone-1 parity comparison — ignored until the LrState state-parity
/// prerequisite lands (see module docs). The negative-case test above keeps
/// the verdict side exercised in the meantime.
#[test]
fn planar_embedding_matches_networkx_oracle() {
    let fixture = fixture();
    let graphs = fixture["graphs"]
        .as_object()
        .expect("fixture should carry a graphs object");
    let mut planar_checked = 0usize;
    for (name, entry) in graphs {
        if !entry["is_planar"].as_bool().expect("is_planar recorded") {
            continue;
        }
        planar_checked += 1;
        let graph = build_graph(entry);
        let data = planar_embedding_data(&graph).unwrap_or_else(|| {
            panic!("{name}: fixture records planar but fnx produced no embedding")
        });
        let embedding_data = entry["embedding_data"]
            .as_object()
            .unwrap_or_else(|| panic!("{name}: planar fixture should carry embedding_data"));
        assert_eq!(
            data.order.len(),
            embedding_data.len(),
            "{name}: embedding covers a different node set than nx"
        );
        for (node, order) in &data.order {
            let expected = embedding_data
                .get(node.as_str())
                .unwrap_or_else(|| panic!("{name}: nx embedding missing node {node}"))
                .as_array()
                .expect("embedding_data entry should be an array");
            let expected: Vec<&str> = expected
                .iter()
                .map(|x| x.as_str().expect("string neighbour"))
                .collect();
            let got: Vec<&str> = order.iter().map(String::as_str).collect();
            assert_eq!(
                got, expected,
                "{name}: clockwise order at {node} diverges from nx"
            );
        }
    }
    assert!(
        planar_checked >= 5,
        "planar corpus degenerated: {planar_checked}"
    );
}

/// Negative case: the oracle fixture must actually be able to fail the gate.
/// If the planar/non-planar split collapses (e.g. the fixture generator
/// regresses to all-planar), a silently wrong verdict side would pass.
#[test]
fn oracle_corpus_covers_both_verdicts() {
    let fixture = fixture();
    let mut planar = 0usize;
    let mut nonplanar = 0usize;
    for entry in fixture["graphs"].as_object().expect("graphs").values() {
        if entry["is_planar"].as_bool().unwrap() {
            planar += 1;
        } else {
            nonplanar += 1;
        }
    }
    assert!(planar > 0, "oracle corpus lost its planar fixtures");
    assert!(nonplanar > 0, "oracle corpus lost its non-planar fixtures");
}
