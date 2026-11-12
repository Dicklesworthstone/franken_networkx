#![forbid(unsafe_code)]

//! Profiling-only harness for fnx-readwrite text serialization.
//!
//! Builds a deterministic graph once, outside the timed region, then runs the
//! selected readwrite operation for repeated samples. Each sample prints a JSON
//! line with timing plus a stable output checksum for before/after proof.
//!
//! Build: cargo build -p fnx-readwrite --profile release-perf --bin perf_harness
//! Run:   SCENARIO=write-edgelist N=10000 DEG=8 ITERS=5 SAMPLES=5 ./target/release-perf/perf_harness
//!
//! Scenarios:
//!   write-edgelist       — timed serialization through EdgeListEngine
//!   dump-edgelist        — print current EdgeListEngine output
//!   dump-owned-edgelist  — print the pre-borrowed owned-snapshot/join oracle
//!   sha-edgelist         — print SHA-256 for current EdgeListEngine output
//!   sha-owned-edgelist   — print SHA-256 for the owned-snapshot/join oracle

use std::hint::black_box;
use std::io::Write;
use std::process::{Command, Stdio};
use std::time::Instant;

use fnx_classes::Graph;
use fnx_readwrite::EdgeListEngine;

#[derive(Debug)]
struct HarnessArgs {
    scenario: String,
    n: usize,
    deg: usize,
    iters: usize,
    samples: usize,
    seed: u64,
}

impl Default for HarnessArgs {
    fn default() -> Self {
        Self {
            scenario: "write-edgelist".to_owned(),
            n: 10_000,
            deg: 8,
            iters: 5,
            samples: 5,
            seed: 0x2545_F491_4F6C_DD1D,
        }
    }
}

struct SplitMix64(u64);

impl SplitMix64 {
    fn next_u64(&mut self) -> u64 {
        self.0 = self.0.wrapping_add(0x9E37_79B9_7F4A_7C15);
        let mut z = self.0;
        z = (z ^ (z >> 30)).wrapping_mul(0xBF58_476D_1CE4_E5B9);
        z = (z ^ (z >> 27)).wrapping_mul(0x94D0_49BB_1331_11EB);
        z ^ (z >> 31)
    }

    fn below(&mut self, bound: usize) -> usize {
        (self.next_u64() % (bound as u64)) as usize
    }
}

fn main() {
    let args = parse_args();
    let graph = build_sparse_graph(args.n, args.deg, args.seed);

    match args.scenario.as_str() {
        "write-edgelist" => run_write_edgelist(&args, &graph),
        "dump-edgelist" => run_dump_edgelist(&graph),
        "dump-owned-edgelist" => run_dump_owned_edgelist(&graph),
        "sha-edgelist" => run_sha_edgelist(&args.scenario, current_edgelist_output(&graph)),
        "sha-owned-edgelist" => run_sha_edgelist(&args.scenario, owned_edgelist_output(&graph)),
        other => {
            eprintln!(
                "unknown scenario `{other}`; supported scenarios: write-edgelist, dump-edgelist, dump-owned-edgelist, sha-edgelist, sha-owned-edgelist"
            );
            std::process::exit(2);
        }
    }
}

fn run_write_edgelist(args: &HarnessArgs, graph: &Graph) {
    for sample in 0..args.samples {
        let mut checksum = 0_u64;
        let mut bytes = 0_usize;
        let start = Instant::now();
        for _ in 0..args.iters {
            let mut engine = EdgeListEngine::strict();
            let output = engine
                .write_edgelist(graph)
                .expect("write_edgelist should succeed");
            checksum ^= checksum_bytes(output.as_bytes());
            bytes = bytes.saturating_add(output.len());
            black_box(output);
        }
        let elapsed = start.elapsed();
        println!(
            "{{\"scenario\":\"{}\",\"sample\":{},\"nodes\":{},\"edges\":{},\"iters\":{},\"elapsed_ms\":{:.6},\"bytes\":{},\"checksum\":\"{:016x}\"}}",
            args.scenario,
            sample,
            graph.node_count(),
            graph.edge_count(),
            args.iters,
            elapsed.as_secs_f64() * 1000.0,
            bytes,
            checksum
        );
    }
}

fn run_dump_edgelist(graph: &Graph) {
    print!("{}", current_edgelist_output(graph));
}

fn run_dump_owned_edgelist(graph: &Graph) {
    print!("{}", owned_edgelist_output(graph));
}

fn run_sha_edgelist(scenario: &str, output: String) {
    let sha256 = sha256sum(output.as_bytes());
    println!(
        "{{\"scenario\":\"{scenario}\",\"bytes\":{},\"sha256\":\"{sha256}\"}}",
        output.len()
    );
}

fn current_edgelist_output(graph: &Graph) -> String {
    let mut engine = EdgeListEngine::strict();
    engine
        .write_edgelist(graph)
        .expect("write_edgelist should succeed")
}

fn owned_edgelist_output(graph: &Graph) -> String {
    graph
        .edges_ordered()
        .into_iter()
        .map(|edge| format!("{} {} -", edge.left, edge.right))
        .collect::<Vec<_>>()
        .join("\n")
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

fn build_sparse_graph(n: usize, avg_deg: usize, seed: u64) -> Graph {
    let mut graph = Graph::strict();
    for node in 0..n {
        graph.add_node(node_name(node));
    }

    for node in 0..n.saturating_sub(1) {
        graph
            .add_edge(node_name(node), node_name(node + 1))
            .expect("path edge add should succeed");
    }

    let target_edges = n.saturating_mul(avg_deg) / 2;
    let mut rng = SplitMix64(seed);
    let mut guard = 0_usize;
    let guard_cap = target_edges.saturating_mul(16).max(16);
    while graph.edge_count() < target_edges && guard < guard_cap {
        guard += 1;
        let left = rng.below(n);
        let right = rng.below(n);
        if left == right {
            continue;
        }
        graph
            .add_edge(node_name(left), node_name(right))
            .expect("random edge add should succeed");
    }

    graph
}

fn node_name(node: usize) -> String {
    format!("n{node:05}")
}

fn checksum_bytes(bytes: &[u8]) -> u64 {
    let mut hash = 0xcbf2_9ce4_8422_2325_u64;
    for byte in bytes {
        hash ^= u64::from(*byte);
        hash = hash.wrapping_mul(0x0000_0100_0000_01b3);
    }
    hash
}

fn parse_args() -> HarnessArgs {
    let mut args = HarnessArgs {
        scenario: std::env::var("SCENARIO").unwrap_or_else(|_| "write-edgelist".to_owned()),
        n: env_parse("N").unwrap_or(10_000),
        deg: env_parse("DEG").unwrap_or(8),
        iters: env_parse("ITERS").unwrap_or(5),
        samples: env_parse("SAMPLES").unwrap_or(5),
        seed: env_parse("SEED").unwrap_or(0x2545_F491_4F6C_DD1D),
    };

    for arg in std::env::args().skip(1) {
        if let Some(value) = arg.strip_prefix("--scenario=") {
            args.scenario = value.to_owned();
        } else if let Some(value) = arg.strip_prefix("--n=") {
            args.n = value.parse().expect("--n must be a usize");
        } else if let Some(value) = arg.strip_prefix("--deg=") {
            args.deg = value.parse().expect("--deg must be a usize");
        } else if let Some(value) = arg.strip_prefix("--iters=") {
            args.iters = value.parse().expect("--iters must be a usize");
        } else if let Some(value) = arg.strip_prefix("--samples=") {
            args.samples = value.parse().expect("--samples must be a usize");
        } else if let Some(value) = arg.strip_prefix("--seed=") {
            args.seed = value.parse().expect("--seed must be a u64");
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
