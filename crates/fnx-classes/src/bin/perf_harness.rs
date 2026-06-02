#![forbid(unsafe_code)]

//! Minimal release-perf harness for fnx-classes graph construction.
//!
//! Build: cargo build -p fnx-classes --profile release-perf --bin perf_harness

use fnx_classes::Graph;
use fnx_runtime::CompatibilityMode;
use std::collections::hash_map::DefaultHasher;
use std::env;
use std::hash::{Hash, Hasher};
use std::io::Write;
use std::process::{Command, Stdio, exit};
use std::time::Instant;

#[derive(Clone, Copy)]
enum Scenario {
    PathEdges,
    ShaPathEdges,
    ShaPathEdgesOracle,
}

struct Args {
    scenario: Scenario,
    n: usize,
    iters: usize,
    samples: usize,
}

fn make_labels(n: usize) -> Vec<String> {
    (0..n).map(|node| node.to_string()).collect()
}

fn graph_with_nodes(labels: &[String]) -> Graph {
    let mut graph = Graph::new(CompatibilityMode::Strict);
    for label in labels {
        graph.add_node(label.clone());
    }
    graph
}

fn build_current_path_graph(n: usize) -> Graph {
    let labels = make_labels(n);
    let mut graph = graph_with_nodes(&labels);
    let _ = graph.extend_edges_unrecorded(
        labels
            .iter()
            .zip(labels.iter().skip(1))
            .map(|(left, right)| (left.as_str(), right.as_str())),
    );
    graph
}

fn build_oracle_path_graph(n: usize) -> Graph {
    let labels = make_labels(n);
    let mut graph = graph_with_nodes(&labels);
    for (left, right) in labels.iter().zip(labels.iter().skip(1)) {
        graph
            .add_edge(left.clone(), right.clone())
            .expect("path edge should be valid");
    }
    graph
}

fn checksum_graph(graph: &Graph) -> u64 {
    let mut hasher = DefaultHasher::new();
    graph.nodes_ordered().hash(&mut hasher);
    for (left, right, attrs) in graph.edges_ordered_borrowed() {
        left.hash(&mut hasher);
        right.hash(&mut hasher);
        format!("{attrs:?}").hash(&mut hasher);
    }
    hasher.finish()
}

fn canonical_graph_text(graph: &Graph) -> String {
    let mut output = String::new();
    output.push_str("nodes\n");
    for node in graph.nodes_ordered() {
        output.push_str(node);
        output.push('\n');
    }
    output.push_str("edges\n");
    for (left, right, attrs) in graph.edges_ordered_borrowed() {
        output.push_str(left);
        output.push('\t');
        output.push_str(right);
        output.push('\t');
        output.push_str(&format!("{attrs:?}"));
        output.push('\n');
    }
    output
}

fn sha256_text(text: &str) -> String {
    let mut child = Command::new("sha256sum")
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .spawn()
        .expect("sha256sum should start");
    child
        .stdin
        .as_mut()
        .expect("sha256sum stdin should be open")
        .write_all(text.as_bytes())
        .expect("sha256sum stdin should accept graph text");
    let output = child.wait_with_output().expect("sha256sum should finish");
    assert!(output.status.success(), "sha256sum failed");
    String::from_utf8(output.stdout)
        .expect("sha256sum output should be utf8")
        .split_whitespace()
        .next()
        .expect("sha256sum output should contain digest")
        .to_owned()
}

fn run_path_edges(args: &Args) {
    let mut last_nodes = 0usize;
    let mut last_edges = 0usize;
    let mut last_checksum = 0u64;

    for sample in 0..args.samples {
        let started = Instant::now();
        for _ in 0..args.iters {
            let graph = build_current_path_graph(args.n);
            last_nodes = graph.node_count();
            last_edges = graph.edge_count();
            last_checksum = checksum_graph(&graph);
        }
        let elapsed = started.elapsed().as_secs_f64() * 1000.0;
        println!(
            "{{\"scenario\":\"path-edges\",\"sample\":{sample},\"n\":{},\"iters\":{},\"elapsed_ms\":{elapsed:.6},\"nodes\":{last_nodes},\"edges\":{last_edges},\"checksum\":\"{last_checksum:016x}\"}}",
            args.n, args.iters
        );
    }
}

fn print_sha(args: &Args, oracle: bool) {
    let graph = if oracle {
        build_oracle_path_graph(args.n)
    } else {
        build_current_path_graph(args.n)
    };
    let text = canonical_graph_text(&graph);
    println!(
        "{{\"scenario\":\"{}\",\"n\":{},\"nodes\":{},\"edges\":{},\"bytes\":{},\"sha256\":\"{}\"}}",
        if oracle {
            "sha-path-edges-oracle"
        } else {
            "sha-path-edges"
        },
        args.n,
        graph.node_count(),
        graph.edge_count(),
        text.len(),
        sha256_text(&text)
    );
}

fn parse_args() -> Args {
    let mut args = Args {
        scenario: Scenario::PathEdges,
        n: 100_000,
        iters: 3,
        samples: 5,
    };

    for raw in env::args().skip(1) {
        let Some((key, value)) = raw.split_once('=') else {
            continue;
        };
        match key {
            "--scenario" => {
                args.scenario = match value {
                    "path-edges" => Scenario::PathEdges,
                    "sha-path-edges" => Scenario::ShaPathEdges,
                    "sha-path-edges-oracle" => Scenario::ShaPathEdgesOracle,
                    other => {
                        eprintln!("unknown scenario {other}");
                        exit(2);
                    }
                };
            }
            "--n" => args.n = value.parse().expect("--n must be a usize"),
            "--iters" => args.iters = value.parse().expect("--iters must be a usize"),
            "--samples" => args.samples = value.parse().expect("--samples must be a usize"),
            _ => {}
        }
    }
    args
}

fn main() {
    let args = parse_args();
    match args.scenario {
        Scenario::PathEdges => run_path_edges(&args),
        Scenario::ShaPathEdges => print_sha(&args, false),
        Scenario::ShaPathEdgesOracle => print_sha(&args, true),
    }
}
