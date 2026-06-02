#![forbid(unsafe_code)]

//! Profiling-only harness for fnx-generators.
//!
//! Builds generator outputs inside the timed region and emits JSON lines with
//! timing plus a stable graph checksum. SHA scenarios compare current output
//! against a local oracle for byte-stable behavior proof.
//!
//! Build: cargo build -p fnx-generators --profile release-perf --bin perf_harness
//! Run:   SCENARIO=path-graph N=100000 ITERS=3 SAMPLES=5 ./target/release-perf/perf_harness

use std::hint::black_box;
use std::io::Write;
use std::process::{Command, Stdio};
use std::time::Instant;

use fnx_classes::Graph;
use fnx_generators::GraphGenerator;

#[derive(Debug)]
struct HarnessArgs {
    scenario: String,
    n: usize,
    iters: usize,
    samples: usize,
}

fn main() {
    let args = parse_args();
    match args.scenario.as_str() {
        "path-graph" => run_path_graph(&args),
        "sha-path-graph" => run_sha_graph(&args.scenario, current_path_graph(args.n)),
        "sha-path-graph-oracle" => run_sha_graph(&args.scenario, oracle_path_graph(args.n)),
        other => {
            eprintln!(
                "unknown scenario `{other}`; supported scenarios: path-graph, sha-path-graph, sha-path-graph-oracle"
            );
            std::process::exit(2);
        }
    }
}

fn run_path_graph(args: &HarnessArgs) {
    for sample in 0..args.samples {
        let mut checksum = 0_u64;
        let mut nodes = 0_usize;
        let mut edges = 0_usize;
        let start = Instant::now();
        for _ in 0..args.iters {
            let graph = current_path_graph(args.n);
            nodes = graph.node_count();
            edges = graph.edge_count();
            checksum ^= checksum_bytes(canonical_graph_text(&graph).as_bytes());
            black_box(graph);
        }
        let elapsed = start.elapsed();
        println!(
            "{{\"scenario\":\"{}\",\"sample\":{},\"nodes\":{},\"edges\":{},\"iters\":{},\"elapsed_ms\":{:.6},\"checksum\":\"{:016x}\"}}",
            args.scenario,
            sample,
            nodes,
            edges,
            args.iters,
            elapsed.as_secs_f64() * 1000.0,
            checksum
        );
    }
}

fn run_sha_graph(scenario: &str, graph: Graph) {
    let text = canonical_graph_text(&graph);
    let sha256 = sha256sum(text.as_bytes());
    println!(
        "{{\"scenario\":\"{scenario}\",\"nodes\":{},\"edges\":{},\"bytes\":{},\"sha256\":\"{sha256}\"}}",
        graph.node_count(),
        graph.edge_count(),
        text.len()
    );
}

fn current_path_graph(n: usize) -> Graph {
    let mut generator = GraphGenerator::strict();
    generator
        .path_graph(n)
        .expect("path_graph should succeed")
        .graph
}

fn oracle_path_graph(n: usize) -> Graph {
    let mut graph = Graph::strict();
    let mut node_labels = Vec::with_capacity(n);
    for i in 0..n {
        let node_label = i.to_string();
        graph.add_node(node_label.clone());
        node_labels.push(node_label);
    }
    for i in 0..n.saturating_sub(1) {
        graph
            .add_edge(node_labels[i].clone(), node_labels[i + 1].clone())
            .expect("oracle path edge should succeed");
    }
    graph
}

fn canonical_graph_text(graph: &Graph) -> String {
    let mut output = String::new();
    output.push_str("nodes ");
    output.push_str(&graph.node_count().to_string());
    output.push('\n');
    for node in graph.nodes_ordered() {
        output.push_str("n ");
        output.push_str(node);
        output.push('\n');
    }
    output.push_str("edges ");
    output.push_str(&graph.edge_count().to_string());
    output.push('\n');
    for edge in graph.edges_ordered() {
        output.push_str("e ");
        output.push_str(&edge.left);
        output.push(' ');
        output.push_str(&edge.right);
        output.push('\n');
    }
    output
}

fn checksum_bytes(bytes: &[u8]) -> u64 {
    let mut hash = 0xcbf2_9ce4_8422_2325_u64;
    for byte in bytes {
        hash ^= u64::from(*byte);
        hash = hash.wrapping_mul(0x0000_0100_0000_01b3);
    }
    hash
}

fn sha256sum(bytes: &[u8]) -> String {
    let mut child = Command::new("sha256sum")
        .arg("-")
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .spawn()
        .expect("sha256sum should be available");

    child
        .stdin
        .as_mut()
        .expect("sha256sum stdin should be piped")
        .write_all(bytes)
        .expect("sha256sum stdin write should succeed");

    let output = child.wait_with_output().expect("sha256sum should finish");
    assert!(
        output.status.success(),
        "sha256sum should exit successfully"
    );
    let stdout = String::from_utf8(output.stdout).expect("sha256sum stdout should be UTF-8");
    stdout
        .split_whitespace()
        .next()
        .expect("sha256sum should print a digest")
        .to_owned()
}

fn parse_args() -> HarnessArgs {
    let mut args = HarnessArgs {
        scenario: std::env::var("SCENARIO").unwrap_or_else(|_| "path-graph".to_owned()),
        n: env_parse("N").unwrap_or(100_000),
        iters: env_parse("ITERS").unwrap_or(3),
        samples: env_parse("SAMPLES").unwrap_or(5),
    };

    for arg in std::env::args().skip(1) {
        if let Some(value) = arg.strip_prefix("--scenario=") {
            args.scenario = value.to_owned();
        } else if let Some(value) = arg.strip_prefix("--n=") {
            args.n = value.parse().expect("--n must be a usize");
        } else if let Some(value) = arg.strip_prefix("--iters=") {
            args.iters = value.parse().expect("--iters must be a usize");
        } else if let Some(value) = arg.strip_prefix("--samples=") {
            args.samples = value.parse().expect("--samples must be a usize");
        }
    }

    args
}

fn env_parse<T>(name: &str) -> Option<T>
where
    T: std::str::FromStr,
{
    std::env::var(name)
        .ok()
        .and_then(|value| value.parse().ok())
}
