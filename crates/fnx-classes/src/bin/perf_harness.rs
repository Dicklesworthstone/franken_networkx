#![forbid(unsafe_code)]

//! Minimal release harness for fnx-classes hot primitives.
//!
//! Build: cargo build -p fnx-classes --profile release --bin perf_harness

use fnx_classes::digraph::DiGraph;
use fnx_classes::{AttrMap, Graph};
use fnx_runtime::{CgseValue, CompatibilityMode};
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
    IsWeightedEdgeScanAb,
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

fn weighted_attrs() -> AttrMap {
    let mut attrs = AttrMap::new();
    attrs.insert("weight".to_owned(), CgseValue::from(1_i64));
    attrs
}

fn build_weighted_scan_graph(n: usize) -> Graph {
    assert!(n > 16, "weighted scan A/B requires more than 16 nodes");
    let labels = (0..n)
        .map(|node| format!("node-{node:08}-weighted-predicate"))
        .collect::<Vec<_>>();
    let mut graph = graph_with_nodes(&labels);
    let mut edges = Vec::with_capacity(n * 8 + 1);
    for node in 0..n {
        for offset in 1..=8 {
            edges.push((
                labels[node].clone(),
                labels[(node + offset) % n].clone(),
                weighted_attrs(),
            ));
        }
    }
    edges.push((
        labels[n / 2].clone(),
        labels[n / 2].clone(),
        weighted_attrs(),
    ));
    let inserted = graph.extend_edges_with_attrs_unrecorded(edges);
    assert_eq!(inserted, n * 8 + 1);
    graph
}

fn is_weighted_frozen_adjacency(graph: &Graph, weight_attr: &str) -> bool {
    let nodes = graph.nodes_ordered();
    let mut has_edges = false;
    for &left in &nodes {
        if let Some(neighbors) = graph.neighbors_iter(left) {
            for right in neighbors {
                has_edges = true;
                if graph
                    .edge_attrs(left, right)
                    .and_then(|attrs| attrs.get(weight_attr))
                    .is_none()
                {
                    return false;
                }
            }
        }
    }
    has_edges
}

fn is_weighted_direct_storage(graph: &Graph, weight_attr: &str) -> bool {
    let mut has_edges = false;
    for (_, _, attrs) in graph.edges_storage_order_index_iter() {
        has_edges = true;
        if !attrs.contains_key(weight_attr) {
            return false;
        }
    }
    has_edges
}

fn time_is_weighted_route(graph: &Graph, iters: usize, frozen_adjacency: bool) -> (f64, usize) {
    let started = Instant::now();
    let mut checksum = 0usize;
    for _ in 0..iters {
        let weighted = if frozen_adjacency {
            is_weighted_frozen_adjacency(graph, black_box("weight"))
        } else {
            is_weighted_direct_storage(graph, black_box("weight"))
        };
        checksum = checksum.wrapping_add(usize::from(black_box(weighted)));
    }
    (started.elapsed().as_secs_f64() * 1_000_000.0, checksum)
}

fn run_is_weighted_edge_scan_ab(args: &Args) {
    let graph = build_weighted_scan_graph(args.n);
    assert!(is_weighted_frozen_adjacency(&graph, "weight"));
    assert!(is_weighted_direct_storage(&graph, "weight"));
    assert!(!is_weighted_frozen_adjacency(&graph, "missing"));
    assert!(!is_weighted_direct_storage(&graph, "missing"));
    let empty = Graph::strict();
    assert_eq!(
        is_weighted_frozen_adjacency(&empty, "weight"),
        is_weighted_direct_storage(&empty, "weight")
    );

    let mut speedups = Vec::with_capacity(args.samples);
    let mut null_ratios = Vec::with_capacity(args.samples);
    let mut candidate_wins = 0usize;
    let mut checksum = None;

    for sample in 0..args.samples {
        let ((candidate_us, candidate_sum), (reference_us, reference_sum)) = if sample % 2 == 0 {
            (
                time_is_weighted_route(&graph, args.iters, false),
                time_is_weighted_route(&graph, args.iters, true),
            )
        } else {
            let reference = time_is_weighted_route(&graph, args.iters, true);
            let candidate = time_is_weighted_route(&graph, args.iters, false);
            (candidate, reference)
        };
        let (null_a_us, null_a_sum) = time_is_weighted_route(&graph, args.iters, false);
        let (null_b_us, null_b_sum) = time_is_weighted_route(&graph, args.iters, false);
        assert_eq!(candidate_sum, reference_sum);
        assert_eq!(candidate_sum, null_a_sum);
        assert_eq!(candidate_sum, null_b_sum);
        checksum = Some(candidate_sum);
        candidate_wins += usize::from(candidate_us < reference_us);
        speedups.push(reference_us / candidate_us);
        null_ratios.push(null_a_us / null_b_us);
        println!(
            "{{\"scenario\":\"is-weighted-edge-scan-ab\",\"sample\":{sample},\"n\":{},\"m\":{},\"iters\":{},\"candidate_us\":{candidate_us:.3},\"reference_us\":{reference_us:.3},\"speedup\":{:.6},\"null_ratio\":{:.6},\"checksum\":{candidate_sum}}}",
            args.n,
            graph.edge_count(),
            args.iters,
            reference_us / candidate_us,
            null_a_us / null_b_us
        );
    }

    println!(
        "{{\"scenario\":\"is-weighted-edge-scan-summary\",\"samples\":{},\"candidate_wins\":{candidate_wins},\"median_speedup\":{:.6},\"median_null_ratio\":{:.6},\"checksum\":{}}}",
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
                    "is-weighted-edge-scan-ab" => Scenario::IsWeightedEdgeScanAb,
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
        Scenario::IsWeightedEdgeScanAb => run_is_weighted_edge_scan_ab(&args),
    }
}
