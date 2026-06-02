#![forbid(unsafe_code)]

//! Profiling-only harness (measurement, not optimization).
//!
//! Builds a deterministic graph once (excluded from timing) and runs a chosen
//! algorithm `ITERS` times inside a timed region, printing one JSON line of
//! timing to stdout. Designed for clean `perf`/`samply` attribution and for
//! `hyperfine`/loop-based wall-clock baselines.
//!
//! Build:  cargo build -p fnx-algorithms --profile release-perf --bin perf_harness
//! Run:    ALGO=betweenness N=1500 DEG=8 ITERS=1 ./target/release-perf/perf_harness
//!
//! Env vars:
//!   ALGO  — betweenness | pagerank | closeness | harmonic | components | dijkstra_ssp (default betweenness)
//!   N     — node count (default 1500)
//!   DEG   — average degree for the sparse random graph (default 8)
//!   ITERS — timed repetitions of the algorithm (default 1)
//!   SEED  — LCG seed for graph generation (default 0x2545F4914F6CDD1D)
//!   PPROF — enable pprof when built with --features profile-pprof
//!
//! CLI equivalents are also accepted so rch cargo-run invocations can pass
//! settings through with `-- --pprof --algo=betweenness --n=1500`.

use std::hint::black_box;
use std::time::Instant;

#[cfg(feature = "profile-pprof")]
use std::collections::{BTreeMap, HashSet};

use fnx_algorithms::{
    betweenness_centrality, closeness_centrality, connected_components, harmonic_centrality,
    pagerank, shortest_path_unweighted,
};
use fnx_classes::Graph;

#[derive(Default)]
struct HarnessArgs {
    algo: Option<String>,
    n: Option<usize>,
    deg: Option<usize>,
    iters: Option<usize>,
    seed: Option<u64>,
    pprof: bool,
    pprof_freq: Option<i32>,
    pprof_top: Option<usize>,
}

/// Deterministic SplitMix64-style PRNG — no external rng, fully reproducible.
struct Lcg(u64);
impl Lcg {
    fn next_u64(&mut self) -> u64 {
        // SplitMix64
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

/// Connected sparse random graph: a spanning path (guarantees connectivity)
/// plus extra random edges to reach the requested average degree.
fn build_sparse(n: usize, avg_deg: usize, seed: u64) -> Graph {
    let mut g = Graph::strict();
    for i in 0..n {
        let _ = g.add_node(i.to_string());
    }
    // Spanning path so the graph is connected (matters for closeness/betweenness).
    for i in 0..n.saturating_sub(1) {
        let _ = g.add_edge(i.to_string(), (i + 1).to_string());
    }
    let target_edges = n.saturating_mul(avg_deg) / 2;
    let mut rng = Lcg(seed);
    let mut added = n.saturating_sub(1);
    let mut guard = 0usize;
    let guard_cap = target_edges.saturating_mul(8).max(16);
    while added < target_edges && guard < guard_cap {
        guard += 1;
        let u = rng.below(n);
        let v = rng.below(n);
        if u == v {
            continue;
        }
        // add_edge is idempotent on an existing edge in strict mode; only count
        // genuinely new edges toward the target.
        let before = g.edge_count();
        let _ = g.add_edge(u.to_string(), v.to_string());
        if g.edge_count() > before {
            added += 1;
        }
    }
    g
}

fn main() {
    let args = parse_args();
    let algo = args
        .algo
        .or_else(|| std::env::var("ALGO").ok())
        .unwrap_or_else(|| "betweenness".to_string());
    let n = args
        .n
        .or_else(|| std::env::var("N").ok().and_then(|v| v.parse().ok()))
        .unwrap_or(1500);
    let deg = args
        .deg
        .or_else(|| std::env::var("DEG").ok().and_then(|v| v.parse().ok()))
        .unwrap_or(8);
    let iters = args
        .iters
        .or_else(|| std::env::var("ITERS").ok().and_then(|v| v.parse().ok()))
        .unwrap_or(1);
    let seed = args
        .seed
        .or_else(|| std::env::var("SEED").ok().and_then(|v| v.parse().ok()))
        .unwrap_or(0x2545_F491_4F6C_DD1D);
    let pprof_freq = args.pprof_freq.or_else(|| {
        std::env::var("PPROF_FREQ")
            .ok()
            .and_then(|value| value.parse().ok())
    });
    let pprof_top = args.pprof_top.or_else(|| {
        std::env::var("PPROF_TOP")
            .ok()
            .and_then(|value| value.parse().ok())
    });
    let pprof_enabled = args.pprof || std::env::var_os("PPROF").is_some();

    let g = build_sparse(n, deg, seed);
    let m = g.edge_count();

    // Golden-output mode for isomorphism proofs: print full-precision per-node
    // scores in node order so the result can be sha256'd before/after an
    // optimization. `DUMP=1 ALGO=betweenness N=... | sha256sum`.
    if std::env::var_os("DUMP").is_some() {
        dump_golden(&algo, &g);
        return;
    }

    // Warm one untimed run (page-ins, branch predictor) without polluting the metric.
    run_once(&algo, &g, n);

    let pprof_guard = start_pprof_guard(pprof_enabled, pprof_freq);

    let start = Instant::now();
    let mut checksum = 0.0_f64;
    for _ in 0..iters {
        checksum += run_once(&algo, &g, n);
    }
    let total = start.elapsed();
    let per_iter_ms = (total.as_secs_f64() * 1e3) / (iters.max(1) as f64);

    // black_box the checksum so the algorithm output can't be optimized away.
    black_box(checksum);

    println!(
        "{{\"algo\":\"{algo}\",\"n\":{n},\"m\":{m},\"avg_deg\":{deg},\"iters\":{iters},\"total_ms\":{:.4},\"per_iter_ms\":{per_iter_ms:.4},\"checksum\":{checksum:.6}}}",
        total.as_secs_f64() * 1e3
    );

    print_pprof_report(pprof_guard, pprof_top);
}

fn parse_args() -> HarnessArgs {
    let mut parsed = HarnessArgs::default();
    for arg in std::env::args().skip(1) {
        if arg == "--pprof" {
            parsed.pprof = true;
        } else if let Some(value) = arg.strip_prefix("--algo=") {
            parsed.algo = Some(value.to_owned());
        } else if let Some(value) = arg.strip_prefix("--n=") {
            parsed.n = value.parse().ok();
        } else if let Some(value) = arg.strip_prefix("--deg=") {
            parsed.deg = value.parse().ok();
        } else if let Some(value) = arg.strip_prefix("--iters=") {
            parsed.iters = value.parse().ok();
        } else if let Some(value) = arg.strip_prefix("--seed=") {
            parsed.seed = value.parse().ok();
        } else if let Some(value) = arg.strip_prefix("--pprof-freq=") {
            parsed.pprof_freq = value.parse().ok();
        } else if let Some(value) = arg.strip_prefix("--pprof-top=") {
            parsed.pprof_top = value.parse().ok();
        } else {
            eprintln!("unknown argument {arg}");
            std::process::exit(2);
        }
    }
    parsed
}

#[cfg(feature = "profile-pprof")]
fn start_pprof_guard(
    enabled: bool,
    frequency: Option<i32>,
) -> Option<pprof::ProfilerGuard<'static>> {
    if !enabled {
        return None;
    }

    let sample_frequency = match frequency {
        Some(value) => value,
        None => 997,
    };
    match pprof::ProfilerGuardBuilder::default()
        .frequency(sample_frequency)
        .blocklist(&["libc", "libgcc", "pthread", "vdso"])
        .build()
    {
        Ok(guard) => Some(guard),
        Err(error) => {
            eprintln!("failed to start pprof profiler: {error}");
            std::process::exit(2);
        }
    }
}

#[cfg(not(feature = "profile-pprof"))]
fn start_pprof_guard(enabled: bool, _frequency: Option<i32>) -> Option<()> {
    if enabled {
        eprintln!("pprof requires building perf_harness with --features profile-pprof");
        std::process::exit(2);
    }
    None
}

#[cfg(feature = "profile-pprof")]
fn print_pprof_report(guard: Option<pprof::ProfilerGuard<'static>>, limit: Option<usize>) {
    let Some(guard) = guard else {
        return;
    };

    let report = match guard.report().build() {
        Ok(report) => report,
        Err(error) => {
            eprintln!("failed to build pprof report: {error}");
            std::process::exit(2);
        }
    };
    let mut samples_by_symbol = BTreeMap::<String, isize>::new();

    for (frames, count) in &report.data {
        let mut stack_seen = HashSet::<String>::new();
        for frame in &frames.frames {
            for symbol in frame {
                let name = symbol.name();
                if is_profile_noise(&name) || !stack_seen.insert(name.clone()) {
                    continue;
                }
                *samples_by_symbol.entry(name).or_insert(0) += *count;
            }
        }
    }

    let mut rows: Vec<_> = samples_by_symbol.into_iter().collect();
    rows.sort_by(|left, right| right.1.cmp(&left.1).then_with(|| left.0.cmp(&right.0)));

    println!("pprof_top_inclusive:");
    for (rank, (symbol, samples)) in rows.into_iter().take(limit.unwrap_or(12)).enumerate() {
        println!("{}\t{}\t{}", rank + 1, samples, symbol);
    }
}

#[cfg(not(feature = "profile-pprof"))]
fn print_pprof_report(_guard: Option<()>, _limit: Option<usize>) {}

#[cfg(feature = "profile-pprof")]
fn is_profile_noise(symbol: &str) -> bool {
    symbol.contains("pprof::")
        || symbol.contains("backtrace::")
        || symbol.contains("perf_signal_handler")
        || symbol.contains("std::rt::")
        || symbol.contains("core::ops::function::")
        || symbol.contains("__libc_start")
        || symbol == "Unknown"
}

/// Print full-precision per-node scores in node order for golden/isomorphism
/// proofs. Bit-exact `{:.17e}` so any FP drift changes the sha256.
fn dump_golden(algo: &str, g: &Graph) {
    let scores: Vec<(String, f64)> = match algo {
        "betweenness" => betweenness_centrality(g)
            .scores
            .into_iter()
            .map(|s| (s.node, s.score))
            .collect(),
        "closeness" => closeness_centrality(g)
            .scores
            .into_iter()
            .map(|s| (s.node, s.score))
            .collect(),
        "harmonic" => harmonic_centrality(g)
            .scores
            .into_iter()
            .map(|s| (s.node, s.score))
            .collect(),
        "pagerank" => pagerank(g)
            .scores
            .into_iter()
            .map(|s| (s.node, s.score))
            .collect(),
        other => {
            eprintln!("DUMP unsupported for ALGO={other}");
            std::process::exit(2);
        }
    };
    for (node, score) in scores {
        println!("{node}\t{score:.17e}");
    }
}

/// Run one repetition of the chosen algorithm, returning a checksum derived from
/// the result to defeat dead-code elimination.
fn run_once(algo: &str, g: &Graph, n: usize) -> f64 {
    match algo {
        "betweenness" => {
            let r = betweenness_centrality(g);
            r.scores.iter().map(|s| s.score).sum()
        }
        "pagerank" => {
            let r = pagerank(g);
            r.scores.iter().map(|s| s.score).sum()
        }
        "closeness" => {
            let r = closeness_centrality(g);
            r.scores.iter().map(|s| s.score).sum()
        }
        "harmonic" => {
            let r = harmonic_centrality(g);
            r.scores.iter().map(|s| s.score).sum()
        }
        "components" => connected_components(g).components.len() as f64,
        "lookup_sweep" => {
            // Non-distorting microbench: replicate exactly the string-keyed
            // adjacency operations the Brandes inner loop performs once per
            // edge per source — `neighbors_iter(name)` + `get_node_index(name)`
            // — over the whole edge set ONCE. Comparing this against the full
            // betweenness time (which performs n such sweeps) quantifies the
            // share attributable to string→index resolution.
            let mut acc = 0usize;
            let names = g.nodes_ordered();
            for name in &names {
                if let Some(neighbors) = g.neighbors_iter(name) {
                    for w_name in neighbors {
                        acc = acc.wrapping_add(g.get_node_index(w_name).unwrap_or(0));
                    }
                }
            }
            acc as f64
        }
        "dijkstra_ssp" => {
            // Single-source unweighted shortest path to the far node.
            let r = shortest_path_unweighted(g, "0", &(n - 1).to_string());
            r.path.map(|p| p.len() as f64).unwrap_or(0.0)
        }
        other => {
            eprintln!(
                "unknown ALGO={other}; valid: betweenness|pagerank|closeness|harmonic|components|dijkstra_ssp"
            );
            std::process::exit(2);
        }
    }
}
