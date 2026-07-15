#![forbid(unsafe_code)]

//! Minimal release harness for fnx-classes hot primitives.
//!
//! Build: cargo build -p fnx-classes --profile release --bin perf_harness

use fnx_classes::Graph;
use fnx_classes::digraph::DiGraph;
use fnx_runtime::CompatibilityMode;
use std::collections::hash_map::DefaultHasher;
use std::env;
use std::hash::{Hash, Hasher};
use std::hint::black_box;
use std::io::Write;
use std::process::{Command, Stdio, exit};
use std::time::Instant;

#[derive(Clone, Copy)]
enum Scenario {
    PathEdges,
    ShaPathEdges,
    ShaPathEdgesOracle,
    DiGraphDegreeLookupAb,
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

fn build_degree_graph(n: usize) -> (DiGraph, Vec<String>) {
    assert!(n >= 3, "degree A/B requires at least three nodes");
    let labels = (0..n)
        .map(|node| format!("node-{node:08}-degree-probe"))
        .collect::<Vec<_>>();
    let mut graph = DiGraph::strict();
    for label in &labels {
        graph.add_node(label.clone());
    }
    for node in 0..n {
        graph
            .add_edge(labels[node].clone(), labels[(node + 1) % n].clone())
            .expect("cycle edge should be valid");
        if node % 17 == 0 {
            graph
                .add_edge(labels[node].clone(), labels[(node + 13) % n].clone())
                .expect("chord edge should be valid");
        }
    }
    graph
        .add_edge(labels[n / 2].clone(), labels[n / 2].clone())
        .expect("self-loop should be valid");
    (graph, labels)
}

fn time_degree_route(
    graph: &DiGraph,
    labels: &[String],
    iters: usize,
    frozen_two_lookup: bool,
) -> (f64, usize) {
    let started = Instant::now();
    let mut checksum = 0usize;
    for _ in 0..iters {
        for label in labels {
            let node = black_box(label.as_str());
            let degree = if frozen_two_lookup {
                graph.in_degree(node) + graph.out_degree(node)
            } else {
                graph.degree(node)
            };
            checksum = checksum.wrapping_add(black_box(degree));
        }
    }
    (started.elapsed().as_secs_f64() * 1_000_000.0, checksum)
}

fn median(values: &mut [f64]) -> f64 {
    values.sort_by(f64::total_cmp);
    values[values.len() / 2]
}

fn run_digraph_degree_lookup_ab(args: &Args) {
    let (graph, labels) = build_degree_graph(args.n);
    for label in &labels {
        assert_eq!(
            graph.degree(label),
            graph.in_degree(label) + graph.out_degree(label)
        );
    }
    assert_eq!(graph.degree("missing-node"), 0);
    assert_eq!(
        graph.in_degree("missing-node") + graph.out_degree("missing-node"),
        0
    );

    let mut speedups = Vec::with_capacity(args.samples);
    let mut null_ratios = Vec::with_capacity(args.samples);
    let mut candidate_wins = 0usize;
    let mut checksum = None;

    for sample in 0..args.samples {
        let ((candidate_us, candidate_sum), (reference_us, reference_sum)) = if sample % 2 == 0 {
            (
                time_degree_route(&graph, &labels, args.iters, false),
                time_degree_route(&graph, &labels, args.iters, true),
            )
        } else {
            let reference = time_degree_route(&graph, &labels, args.iters, true);
            let candidate = time_degree_route(&graph, &labels, args.iters, false);
            (candidate, reference)
        };
        let (null_a_us, null_a_sum) = time_degree_route(&graph, &labels, args.iters, false);
        let (null_b_us, null_b_sum) = time_degree_route(&graph, &labels, args.iters, false);
        assert_eq!(candidate_sum, reference_sum);
        assert_eq!(candidate_sum, null_a_sum);
        assert_eq!(candidate_sum, null_b_sum);
        checksum = Some(candidate_sum);
        candidate_wins += usize::from(candidate_us < reference_us);
        speedups.push(reference_us / candidate_us);
        null_ratios.push(null_a_us / null_b_us);
        println!(
            "{{\"scenario\":\"digraph-degree-lookup-ab\",\"sample\":{sample},\"n\":{},\"iters\":{},\"candidate_us\":{candidate_us:.3},\"reference_us\":{reference_us:.3},\"speedup\":{:.6},\"null_ratio\":{:.6},\"checksum\":{candidate_sum}}}",
            args.n,
            args.iters,
            reference_us / candidate_us,
            null_a_us / null_b_us
        );
    }

    println!(
        "{{\"scenario\":\"digraph-degree-lookup-summary\",\"samples\":{},\"candidate_wins\":{candidate_wins},\"median_speedup\":{:.6},\"median_null_ratio\":{:.6},\"checksum\":{}}}",
        args.samples,
        median(&mut speedups),
        median(&mut null_ratios),
        checksum.expect("at least one sample is required")
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
                    "digraph-degree-lookup-ab" => Scenario::DiGraphDegreeLookupAb,
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
        Scenario::DiGraphDegreeLookupAb => run_digraph_degree_lookup_ab(&args),
    }
}
