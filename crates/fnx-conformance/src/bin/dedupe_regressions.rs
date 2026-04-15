//! Graph-isomorphism-aware regression deduplication (G4).
//!
//! Scans the regression corpus for duplicate fixtures where the underlying
//! graphs are isomorphic, even if node labels differ.
//!
//! Usage:
//!   cargo run -p fnx-conformance --bin dedupe_regressions [OPTIONS]
//!
//! Options:
//!   --check      Report duplicates without modifying (exit 1 if found)
//!   --verbose    Show detailed isomorphism matches

use fnx_algorithms::is_isomorphic;
use fnx_classes::Graph;
use fnx_runtime::CompatibilityMode;
use serde::Deserialize;
use std::collections::HashMap;
use std::fs;
use std::path::{Path, PathBuf};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args: Vec<String> = std::env::args().collect();
    let check_only = args.iter().any(|a| a == "--check");
    let verbose = args.iter().any(|a| a == "--verbose");

    let fixtures_dir = Path::new("crates/fnx-conformance/fixtures/regressions");
    if !fixtures_dir.exists() {
        eprintln!("Regression fixtures directory not found: {fixtures_dir:?}");
        return Ok(());
    }

    let fixtures = load_all_fixtures(fixtures_dir)?;
    eprintln!("Loaded {} regression fixtures", fixtures.len());

    let duplicates = find_isomorphic_duplicates(&fixtures, verbose);

    if duplicates.is_empty() {
        eprintln!("No isomorphic duplicates found");
        return Ok(());
    }

    eprintln!("\nFound {} duplicate groups:", duplicates.len());
    for (canonical, dupes) in &duplicates {
        eprintln!("  Canonical: {}", canonical.display());
        for dupe in dupes {
            eprintln!("    Duplicate: {}", dupe.display());
        }
    }

    if check_only {
        std::process::exit(1);
    }

    Ok(())
}

#[derive(Debug, Deserialize)]
#[allow(dead_code)]
struct RegressionFixture {
    #[serde(default)]
    suite: String,
    #[serde(default)]
    fixture_id: String,
    #[serde(default)]
    expected: Option<ExpectedGraph>,
    #[serde(default)]
    operations: Vec<Operation>,
}

#[derive(Debug, Deserialize)]
struct ExpectedGraph {
    #[serde(default)]
    graph: Option<GraphDef>,
}

#[derive(Debug, Deserialize)]
struct GraphDef {
    #[serde(default)]
    nodes: Vec<String>,
    #[serde(default)]
    edges: Vec<EdgeDef>,
}

#[derive(Debug, Deserialize)]
struct EdgeDef {
    left: String,
    right: String,
}

#[derive(Debug, Deserialize)]
#[serde(tag = "op")]
#[allow(dead_code)]
enum Operation {
    #[serde(rename = "add_node")]
    AddNode { node: String },
    #[serde(rename = "add_edge")]
    AddEdge { left: String, right: String },
    #[serde(other)]
    Other,
}

struct LoadedFixture {
    path: PathBuf,
    graph: Graph,
    node_count: usize,
    edge_count: usize,
}

fn load_all_fixtures(dir: &Path) -> Result<Vec<LoadedFixture>, Box<dyn std::error::Error>> {
    let mut fixtures = Vec::new();

    for entry in fs::read_dir(dir)? {
        let entry = entry?;
        let path = entry.path();

        if path.is_dir() {
            // Recurse into subdirectories
            fixtures.extend(load_all_fixtures(&path)?);
        } else if path.extension().is_some_and(|e| e == "json")
            && path.file_name().is_none_or(|n| n != "provenance.json")
            && let Some(fixture) = load_fixture(&path)?
        {
            fixtures.push(fixture);
        }
    }

    Ok(fixtures)
}

fn load_fixture(path: &Path) -> Result<Option<LoadedFixture>, Box<dyn std::error::Error>> {
    let content = fs::read_to_string(path)?;
    let fixture: RegressionFixture = serde_json::from_str(&content)?;

    let graph = build_graph_from_fixture(&fixture);
    let node_count = graph.node_count();
    let edge_count = graph.edge_count();

    // Skip empty graphs
    if node_count == 0 {
        return Ok(None);
    }

    Ok(Some(LoadedFixture {
        path: path.to_path_buf(),
        graph,
        node_count,
        edge_count,
    }))
}

fn build_graph_from_fixture(fixture: &RegressionFixture) -> Graph {
    let mut graph = Graph::new(CompatibilityMode::Strict);

    // Try to build from expected.graph first
    if let Some(expected) = &fixture.expected
        && let Some(graph_def) = &expected.graph
    {
        for node in &graph_def.nodes {
            graph.add_node(node.clone());
        }
        for edge in &graph_def.edges {
            let _ = graph.add_edge(edge.left.clone(), edge.right.clone());
        }
        return graph;
    }

    // Fall back to operations
    for op in &fixture.operations {
        match op {
            Operation::AddNode { node } => {
                graph.add_node(node.clone());
            }
            Operation::AddEdge { left, right } => {
                let _ = graph.add_edge(left.clone(), right.clone());
            }
            Operation::Other => {}
        }
    }

    graph
}

fn find_isomorphic_duplicates(
    fixtures: &[LoadedFixture],
    verbose: bool,
) -> HashMap<PathBuf, Vec<PathBuf>> {
    let mut duplicates: HashMap<PathBuf, Vec<PathBuf>> = HashMap::new();
    let mut canonical_indices: Vec<usize> = Vec::new();

    for (i, fixture) in fixtures.iter().enumerate() {
        let mut found_match = false;

        for &canonical_idx in &canonical_indices {
            let canonical = &fixtures[canonical_idx];

            // Quick reject: different sizes can't be isomorphic
            if fixture.node_count != canonical.node_count
                || fixture.edge_count != canonical.edge_count
            {
                continue;
            }

            // Full isomorphism check
            if is_isomorphic(&fixture.graph, &canonical.graph) {
                if verbose {
                    eprintln!(
                        "Isomorphic match: {} ~ {}",
                        fixture.path.display(),
                        canonical.path.display()
                    );
                }

                duplicates
                    .entry(canonical.path.clone())
                    .or_default()
                    .push(fixture.path.clone());
                found_match = true;
                break;
            }
        }

        if !found_match {
            canonical_indices.push(i);
        }
    }

    // Filter to only groups with actual duplicates
    duplicates.retain(|_, v| !v.is_empty());
    duplicates
}
