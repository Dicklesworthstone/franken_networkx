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
//!   ALGO  — betweenness | pagerank | closeness | harmonic | aspl | components |
//!           dijkstra_ssp | spanning_tree_ab | path_graph_ab |
//!           edge_disjoint_paths_ab (default betweenness)
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

use std::collections::BTreeMap;
#[cfg(feature = "profile-pprof")]
use std::collections::HashSet;

use fnx_algorithms::{
    SpanningTreeCountArm, average_shortest_path_length, betweenness_centrality,
    closeness_centrality, connected_components, edge_disjoint_paths, harmonic_centrality,
    is_connected, is_path_graph, number_of_spanning_trees_arm, pagerank, shortest_path_unweighted,
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

    if algo == "spanning_tree_ab" {
        run_spanning_tree_ab(n, iters);
        return;
    }
    if algo == "path_graph_ab" {
        run_path_graph_ab(n, iters);
        return;
    }
    if algo == "edge_disjoint_paths_ab" {
        run_edge_disjoint_paths_ab(n, iters);
        return;
    }

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

/// Same-binary, paired-interleaved A/B for br-r37-c1-jhxvq. Graph construction,
/// parity, and warm-up are outside the measured region; each timing contains only
/// complete spanning-tree count calls.
fn run_spanning_tree_ab(node_count: usize, iterations: usize) {
    assert!(node_count >= 12, "spanning_tree_ab needs at least 12 nodes");
    let iterations = iterations.max(1);
    let name = |index: usize| format!("spanning_tree_node_{index:04}_with_long_name");
    let payload = "attribute-payload-that-is-intentionally-long-enough-to-make-cloning-visible";
    let mut graph = Graph::strict();
    for index in 0..node_count {
        let _ = graph.add_node(name(index));
    }
    for left in 0..node_count {
        for step in 1..=5usize {
            let right = (left + step) % node_count;
            let attrs: fnx_classes::AttrMap = (0..8usize)
                .map(|index| (format!("payload-{index}"), payload.to_owned().into()))
                .collect::<BTreeMap<_, _>>();
            let _ = graph.add_edge_with_attrs(name(left), name(right), attrs);
        }
    }

    let baseline = number_of_spanning_trees_arm(&graph, None, SpanningTreeCountArm::Contracted);
    let candidate = number_of_spanning_trees_arm(&graph, None, SpanningTreeCountArm::Direct);
    assert_eq!(
        candidate.to_bits(),
        baseline.to_bits(),
        "direct and contracted spanning-tree counts must be bit-identical"
    );

    let time = |arm: SpanningTreeCountArm| -> f64 {
        let started = Instant::now();
        for _ in 0..iterations {
            black_box(number_of_spanning_trees_arm(black_box(&graph), None, arm));
        }
        started.elapsed().as_nanos() as f64
    };
    for _ in 0..3 {
        black_box(time(SpanningTreeCountArm::Contracted));
        black_box(time(SpanningTreeCountArm::Direct));
    }

    let rounds = 21usize;
    let paired = |null_control: bool| -> (Vec<f64>, Vec<f64>, Vec<f64>) {
        let mut ratios = Vec::with_capacity(rounds);
        let mut baseline_times = Vec::with_capacity(rounds);
        let mut candidate_times = Vec::with_capacity(rounds);
        let baseline_arm = if null_control {
            SpanningTreeCountArm::Direct
        } else {
            SpanningTreeCountArm::Contracted
        };
        for round in 0..rounds {
            let (baseline_time, candidate_time) = if round.is_multiple_of(2) {
                (time(baseline_arm), time(SpanningTreeCountArm::Direct))
            } else {
                let candidate_time = time(SpanningTreeCountArm::Direct);
                (time(baseline_arm), candidate_time)
            };
            ratios.push(baseline_time / candidate_time);
            baseline_times.push(baseline_time);
            candidate_times.push(candidate_time);
        }
        (ratios, baseline_times, candidate_times)
    };
    let median = |values: &[f64]| {
        let mut sorted = values.to_vec();
        sorted.sort_by(|left, right| left.partial_cmp(right).expect("finite timing"));
        sorted[sorted.len() / 2]
    };
    let report = |label: &str, ratios: &[f64], baseline_times: &[f64], candidate_times: &[f64]| {
        let wins = ratios.iter().filter(|&&ratio| ratio > 1.0).count();
        let mut sorted = ratios.to_vec();
        sorted.sort_by(|left, right| left.partial_cmp(right).expect("finite ratio"));
        println!(
            "NST_DIRECT_AB {label}: median={:.4}x win_rate={wins}/{rounds} p5_p95=[{:.4},{:.4}] baseline_median_ns={:.0} candidate_median_ns={:.0}",
            median(ratios),
            sorted[rounds * 5 / 100],
            sorted[rounds * 95 / 100],
            median(baseline_times) / iterations as f64,
            median(candidate_times) / iterations as f64,
        );
    };

    println!(
        "NST_DIRECT_AB full-function n={node_count} edges={} attrs_per_edge=8 rounds={rounds} iterations={iterations} (>1 = direct faster)",
        graph.edge_count()
    );
    let (ratios, baseline_times, candidate_times) = paired(false);
    report(
        "DIRECT_vs_contracted",
        &ratios,
        &baseline_times,
        &candidate_times,
    );
    let (null_ratios, null_left, null_right) = paired(true);
    report(
        "NULL_direct_vs_direct",
        &null_ratios,
        &null_left,
        &null_right,
    );
}

/// Same-binary, paired-interleaved A/B for br-r37-c1-tz5st. Graph construction,
/// parity controls, and warm-up are outside the measured region; each timing
/// contains only complete `is_path_graph` calls.
fn run_path_graph_ab(node_count: usize, iterations: usize) {
    assert!(node_count >= 3, "path_graph_ab needs at least 3 nodes");
    let iterations = iterations.max(1);
    let name = |index: usize| format!("path_graph_node_{index:06}_with_a_long_stable_label");
    let mut graph = Graph::strict();
    for index in 0..node_count {
        let _ = graph.add_node(name(index));
    }
    for index in 0..node_count - 1 {
        let _ = graph.add_edge(name(index), name(index + 1));
    }

    let baseline = is_path_graph_name_keyed(&graph);
    let candidate = is_path_graph(&graph);
    assert_eq!(
        candidate, baseline,
        "index and name-keyed path checks differ"
    );
    assert!(
        candidate,
        "benchmark graph must exercise the full-success path"
    );

    let empty = Graph::strict();
    let mut singleton = Graph::strict();
    let _ = singleton.add_node("singleton");
    let mut self_loop = Graph::strict();
    let _ = self_loop.add_edge("loop", "loop");
    let mut cycle = Graph::strict();
    let _ = cycle.add_edge("a", "b");
    let _ = cycle.add_edge("b", "c");
    let _ = cycle.add_edge("c", "a");
    for control in [&empty, &singleton, &self_loop, &cycle] {
        assert_eq!(
            is_path_graph(control),
            is_path_graph_name_keyed(control),
            "index and name-keyed path checks differ on a parity control"
        );
    }

    let time = |candidate_arm: bool| -> f64 {
        let started = Instant::now();
        for _ in 0..iterations {
            let value = if candidate_arm {
                is_path_graph(black_box(&graph))
            } else {
                is_path_graph_name_keyed(black_box(&graph))
            };
            black_box(value);
        }
        started.elapsed().as_nanos() as f64
    };
    for _ in 0..3 {
        black_box(time(false));
        black_box(time(true));
    }

    let rounds = 21usize;
    let paired = |null_control: bool| -> (Vec<f64>, Vec<f64>, Vec<f64>) {
        let mut ratios = Vec::with_capacity(rounds);
        let mut baseline_times = Vec::with_capacity(rounds);
        let mut candidate_times = Vec::with_capacity(rounds);
        for round in 0..rounds {
            let baseline_arm = null_control;
            let (baseline_time, candidate_time) = if round.is_multiple_of(2) {
                (time(baseline_arm), time(true))
            } else {
                let candidate_time = time(true);
                (time(baseline_arm), candidate_time)
            };
            ratios.push(baseline_time / candidate_time);
            baseline_times.push(baseline_time);
            candidate_times.push(candidate_time);
        }
        (ratios, baseline_times, candidate_times)
    };
    let median = |values: &[f64]| {
        let mut sorted = values.to_vec();
        sorted.sort_by(|left, right| left.partial_cmp(right).expect("finite timing"));
        sorted[sorted.len() / 2]
    };
    let report = |label: &str, ratios: &[f64], baseline_times: &[f64], candidate_times: &[f64]| {
        let wins = ratios.iter().filter(|&&ratio| ratio > 1.0).count();
        let mut sorted = ratios.to_vec();
        sorted.sort_by(|left, right| left.partial_cmp(right).expect("finite ratio"));
        println!(
            "PATH_GRAPH_INDEX_AB {label}: median={:.4}x win_rate={wins}/{rounds} p5_p95=[{:.4},{:.4}] baseline_median_ns={:.0} candidate_median_ns={:.0}",
            median(ratios),
            sorted[rounds * 5 / 100],
            sorted[rounds * 95 / 100],
            median(baseline_times) / iterations as f64,
            median(candidate_times) / iterations as f64,
        );
    };

    println!(
        "PATH_GRAPH_INDEX_AB full-function n={node_count} edges={} rounds={rounds} iterations={iterations} (>1 = index faster)",
        graph.edge_count()
    );
    let (ratios, baseline_times, candidate_times) = paired(false);
    report(
        "INDEX_vs_name_keyed",
        &ratios,
        &baseline_times,
        &candidate_times,
    );
    let (null_ratios, null_left, null_right) = paired(true);
    report("NULL_index_vs_index", &null_ratios, &null_left, &null_right);
}

/// Exact pre-br-r37-c1-tz5st production kernel, retained only in the profiling
/// harness as the paired baseline.
fn is_path_graph_name_keyed(graph: &Graph) -> bool {
    let nodes = graph.nodes_ordered();
    let n = nodes.len();
    if n == 0 {
        return false;
    }
    if nodes.iter().any(|&node| graph.has_edge(node, node)) {
        return false;
    }
    if n == 1 {
        return true;
    }
    let mut degree_one_count = 0usize;
    for &node in &nodes {
        match graph.degree(node) {
            0 => return false,
            1 => degree_one_count += 1,
            2 => {}
            _ => return false,
        }
    }
    degree_one_count == 2 && is_connected(graph).is_connected
}

/// Same-binary, paired-interleaved A/B for br-r37-c1-lqir7. The measured
/// graph has one tiny queried component plus an attribute-heavy background
/// component, exposing the mandatory whole-graph residual setup without
/// timing graph construction. Both arms execute the complete public kernel.
fn run_edge_disjoint_paths_ab(node_count: usize, iterations: usize) {
    assert!(
        node_count >= 8,
        "edge_disjoint_paths_ab needs at least 8 nodes"
    );
    let iterations = iterations.max(1);
    let name = |index: usize| format!("flow_node_{index:06}_with_a_long_stable_label");
    let payload = "attribute-payload-that-is-intentionally-long-enough-to-make-cloning-visible";
    let attrs: fnx_classes::AttrMap = (0..8usize)
        .map(|index| (format!("payload-{index}"), payload.to_owned().into()))
        .collect::<BTreeMap<_, _>>();
    let mut graph = Graph::strict();
    for index in 0..node_count {
        let _ = graph.add_node(name(index));
    }
    let _ = graph.add_edge_with_attrs(name(0), name(1), attrs.clone());
    for index in 2..node_count - 1 {
        let _ = graph.add_edge_with_attrs(name(index), name(index + 1), attrs.clone());
    }
    let source = name(0);
    let target = name(1);

    let baseline = edge_disjoint_paths_snapshot_baseline(&graph, &source, &target);
    let candidate = edge_disjoint_paths(&graph, &source, &target);
    assert_eq!(
        candidate, baseline,
        "ordered-index and snapshot flow paths differ"
    );
    assert_eq!(
        candidate,
        vec![vec![source.clone(), target.clone()]],
        "benchmark query must have one direct path"
    );

    let mut path = Graph::strict();
    let _ = path.add_edge("p0", "p1");
    let _ = path.add_edge("p1", "p2");
    let mut disconnected = Graph::strict();
    let _ = disconnected.add_node("left");
    let _ = disconnected.add_node("right");
    for (control, left, right) in [
        (&path, "p0", "p2"),
        (&path, "p0", "p0"),
        (&disconnected, "left", "right"),
    ] {
        assert_eq!(
            edge_disjoint_paths(control, left, right),
            edge_disjoint_paths_snapshot_baseline(control, left, right),
            "ordered-index and snapshot paths differ on a parity control"
        );
    }

    let time = |candidate_arm: bool| -> f64 {
        let started = Instant::now();
        for _ in 0..iterations {
            let paths = if candidate_arm {
                edge_disjoint_paths(black_box(&graph), black_box(&source), black_box(&target))
            } else {
                edge_disjoint_paths_snapshot_baseline(
                    black_box(&graph),
                    black_box(&source),
                    black_box(&target),
                )
            };
            black_box(paths);
        }
        started.elapsed().as_nanos() as f64
    };
    for _ in 0..3 {
        black_box(time(false));
        black_box(time(true));
    }

    let rounds = 21usize;
    let paired = |null_control: bool| -> (Vec<f64>, Vec<f64>, Vec<f64>) {
        let mut ratios = Vec::with_capacity(rounds);
        let mut baseline_times = Vec::with_capacity(rounds);
        let mut candidate_times = Vec::with_capacity(rounds);
        for round in 0..rounds {
            let baseline_arm = null_control;
            let (baseline_time, candidate_time) = if round.is_multiple_of(2) {
                (time(baseline_arm), time(true))
            } else {
                let candidate_time = time(true);
                (time(baseline_arm), candidate_time)
            };
            ratios.push(baseline_time / candidate_time);
            baseline_times.push(baseline_time);
            candidate_times.push(candidate_time);
        }
        (ratios, baseline_times, candidate_times)
    };
    let median = |values: &[f64]| {
        let mut sorted = values.to_vec();
        sorted.sort_by(|left, right| left.partial_cmp(right).expect("finite timing"));
        sorted[sorted.len() / 2]
    };
    let report = |label: &str, ratios: &[f64], baseline_times: &[f64], candidate_times: &[f64]| {
        let wins = ratios.iter().filter(|&&ratio| ratio > 1.0).count();
        let mut sorted = ratios.to_vec();
        sorted.sort_by(|left, right| left.partial_cmp(right).expect("finite ratio"));
        println!(
            "EDGE_DISJOINT_INDEX_AB {label}: median={:.4}x win_rate={wins}/{rounds} p5_p95=[{:.4},{:.4}] baseline_median_ns={:.0} candidate_median_ns={:.0}",
            median(ratios),
            sorted[rounds * 5 / 100],
            sorted[rounds * 95 / 100],
            median(baseline_times) / iterations as f64,
            median(candidate_times) / iterations as f64,
        );
    };

    println!(
        "EDGE_DISJOINT_INDEX_AB full-function n={node_count} edges={} attrs_per_edge=8 rounds={rounds} iterations={iterations} (>1 = ordered indices faster)",
        graph.edge_count()
    );
    let (ratios, baseline_times, candidate_times) = paired(false);
    report(
        "INDEX_vs_snapshots",
        &ratios,
        &baseline_times,
        &candidate_times,
    );
    let (null_ratios, null_left, null_right) = paired(true);
    report(
        "NULL_index_vs_index",
        &null_ratios,
        &null_left,
        &null_right,
    );
}

/// Exact pre-br-r37-c1-lqir7 production kernel, retained only in the profiling
/// harness as the paired baseline.
fn edge_disjoint_paths_snapshot_baseline(
    graph: &Graph,
    source: &str,
    target: &str,
) -> Vec<Vec<String>> {
    if source == target || !graph.has_node(source) || !graph.has_node(target) {
        return Vec::new();
    }

    let nodes = graph.nodes_ordered();
    let n = nodes.len();
    let idx: std::collections::HashMap<&str, usize> =
        nodes.iter().enumerate().map(|(i, n)| (*n, i)).collect();
    let s = match idx.get(source) {
        Some(&i) => i,
        None => return Vec::new(),
    };
    let t = match idx.get(target) {
        Some(&i) => i,
        None => return Vec::new(),
    };

    let mut cap = std::collections::HashMap::new();
    let mut initial_cap = std::collections::HashMap::new();
    let mut adj = vec![std::collections::HashSet::new(); n];
    for edge in graph.edges_ordered() {
        let i = idx[edge.left.as_str()];
        let j = idx[edge.right.as_str()];
        if i != j {
            cap.insert((i, j), 1);
            cap.insert((j, i), 1);
            initial_cap.insert((i, j), 1);
            initial_cap.insert((j, i), 1);
            adj[i].insert(j);
            adj[j].insert(i);
        }
    }

    loop {
        let mut parent = vec![None::<usize>; n];
        let mut visited = vec![false; n];
        visited[s] = true;
        let mut queue = std::collections::VecDeque::new();
        queue.push_back(s);
        while let Some(v) = queue.pop_front() {
            if v == t {
                break;
            }
            for &j in &adj[v] {
                if !visited[j] && *cap.get(&(v, j)).unwrap_or(&0) > 0 {
                    visited[j] = true;
                    parent[j] = Some(v);
                    queue.push_back(j);
                }
            }
        }
        if !visited[t] {
            break;
        }
        let mut v = t;
        while let Some(p) = parent[v] {
            *cap.get_mut(&(p, v)).expect("path edge has capacity") -= 1;
            *cap.get_mut(&(v, p)).expect("reverse edge has capacity") += 1;
            v = p;
        }
    }

    let mut flow_adj = vec![Vec::new(); n];
    for (&(i, j), &c) in &initial_cap {
        if c == 1 && *cap.get(&(i, j)).unwrap_or(&0) == 0 {
            flow_adj[i].push(j);
        }
    }

    let mut paths = Vec::new();
    loop {
        let mut parent = vec![None::<usize>; n];
        let mut visited = vec![false; n];
        visited[s] = true;
        let mut queue = std::collections::VecDeque::new();
        queue.push_back(s);
        while let Some(v) = queue.pop_front() {
            if v == t {
                break;
            }
            for &j in &flow_adj[v] {
                if !visited[j] {
                    visited[j] = true;
                    parent[j] = Some(v);
                    queue.push_back(j);
                }
            }
        }
        if !visited[t] {
            break;
        }
        let mut path = Vec::new();
        let mut v = t;
        while let Some(p) = parent[v] {
            path.push(nodes[v].to_owned());
            if let Some(position) = flow_adj[p].iter().position(|&x| x == v) {
                flow_adj[p].remove(position);
            }
            v = p;
        }
        path.push(nodes[s].to_owned());
        path.reverse();
        paths.push(path);
    }
    paths
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
        "aspl" => {
            let score = average_shortest_path_length(g).average_shortest_path_length;
            vec![("average_shortest_path_length".to_owned(), score)]
        }
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
        "aspl" => average_shortest_path_length(g).average_shortest_path_length,
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
        "graph_build" => {
            // br-r37-c1-d58s8 P2 scoping: replicate the storage workload of
            // _native_compose / the operator family — rebuild the graph from
            // its own parts via the bulk unrecorded path. PPROF the interior
            // to split EdgeKey String allocs vs IndexMap hashing vs adjacency
            // IndexSet inserts BEFORE designing the NodeId side-table.
            let names = g.nodes_ordered();
            let mut out = Graph::strict();
            let _ = out.extend_nodes_with_attrs_unrecorded(
                names
                    .iter()
                    .map(|n2| ((*n2).to_owned(), fnx_classes::AttrMap::new())),
            );
            let mut batch: Vec<(String, String, fnx_classes::AttrMap)> = Vec::new();
            for (u, name_u) in names.iter().enumerate() {
                if let Some(row) = g.neighbors_indices(u) {
                    for &v in row {
                        if u <= v {
                            batch.push((
                                (*name_u).to_owned(),
                                names[v].to_owned(),
                                fnx_classes::AttrMap::new(),
                            ));
                        }
                    }
                }
            }
            let inserted = out.extend_edges_with_attrs_unrecorded(batch);
            inserted as f64
        }
        "dijkstra_ssp" => {
            // Single-source unweighted shortest path to the far node.
            let r = shortest_path_unweighted(g, "0", &(n - 1).to_string());
            r.path.map(|p| p.len() as f64).unwrap_or(0.0)
        }
        other => {
            eprintln!(
                "unknown ALGO={other}; valid: betweenness|pagerank|closeness|harmonic|aspl|components|dijkstra_ssp"
            );
            std::process::exit(2);
        }
    }
}
