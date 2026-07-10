#![forbid(unsafe_code)]

//! Benchmark families for core algorithm categories.
//!
//! Run:   cargo bench -p fnx-algorithms
//! Gate:  check p50/p95/p99 via criterion JSON output in target/criterion/

use std::collections::BTreeMap;

use criterion::{BenchmarkId, Criterion, criterion_group, criterion_main};
use fnx_algorithms::{
    BitparArm, adamic_adar_index, aspl_gate_overhead_cost, average_degree_connectivity,
    average_shortest_path_length, average_shortest_path_length_arm, betweenness_centrality,
    closeness_centrality, closeness_centrality_arm, closeness_reverse_csr_build_cost,
    cn_soundarajan_hopcroft, common_neighbor_centrality, common_neighbors, connected_components,
    degree_centrality, degree_mixing_dict, eigenvector_centrality, harmonic_centrality,
    harmonic_centrality_arm, jaccard_coefficient, max_flow_edmonds_karp, minimum_cut_edmonds_karp,
    minimum_spanning_tree, node_degree_xy, pagerank, preferential_attachment,
    ra_index_soundarajan_hopcroft, resource_allocation_index, shortest_path_unweighted,
    shortest_path_weighted, single_source_dijkstra_path_length,
};
use fnx_classes::{Graph, digraph::DiGraph};
use fnx_runtime::CgseValue;

fn attr(key: &str, val: &str) -> BTreeMap<String, CgseValue> {
    let mut m = BTreeMap::new();
    m.insert(key.to_owned(), val.to_owned().into());
    m
}

// ---------------------------------------------------------------------------
// Graph construction helpers
// ---------------------------------------------------------------------------

fn build_path(n: usize) -> Graph {
    let mut g = Graph::strict();
    for i in 0..n {
        let _ = g.add_node(i.to_string());
    }
    for i in 0..(n.saturating_sub(1)) {
        let _ = g.add_edge(i.to_string(), (i + 1).to_string());
    }
    g
}

fn build_complete(n: usize) -> Graph {
    let mut g = Graph::strict();
    for i in 0..n {
        let _ = g.add_node(i.to_string());
    }
    for i in 0..n {
        for j in (i + 1)..n {
            let _ = g.add_edge(i.to_string(), j.to_string());
        }
    }
    g
}

fn build_grid(rows: usize, cols: usize) -> Graph {
    let mut g = Graph::strict();
    for r in 0..rows {
        for c in 0..cols {
            let _ = g.add_node(format!("{r}_{c}"));
        }
    }
    for r in 0..rows {
        for c in 0..cols {
            if c + 1 < cols {
                let _ = g.add_edge(format!("{r}_{c}"), format!("{r}_{}", c + 1));
            }
            if r + 1 < rows {
                let _ = g.add_edge(format!("{r}_{c}"), format!("{}_{c}", r + 1));
            }
        }
    }
    g
}

/// Deterministic connected low-diameter graph: a random tree (guarantees the whole
/// graph is reachable, which the chunked-parallel eccentricity probe requires)
/// plus `extra` random chords, which collapse the diameter to ~log_deg(n).
///
/// This is the shape real all-pairs centrality workloads have — social, citation
/// and web graphs are low-diameter. The grids benchmarked elsewhere are the
/// high-diameter worst case, kept here as the guard that must NOT regress.
fn build_low_diameter(n: usize, extra: usize) -> Graph {
    let mut g = Graph::strict();
    for i in 0..n {
        let _ = g.add_node(i.to_string());
    }
    let mut x: u64 = 0x2545_F491_4F6C_DD1D;
    let mut next = || {
        x ^= x << 13;
        x ^= x >> 7;
        x ^= x << 17;
        x
    };
    for i in 1..n {
        let parent = (next() as usize) % i;
        let _ = g.add_edge(i.to_string(), parent.to_string());
    }
    for _ in 0..extra {
        let u = (next() as usize) % n;
        let v = (next() as usize) % n;
        if u != v {
            let _ = g.add_edge(u.to_string(), v.to_string());
        }
    }
    g
}

fn build_flow_network(paths: usize, path_len: usize) -> Graph {
    assert!(path_len >= 1, "path_len must be at least 1");
    let mut g = Graph::strict();
    let _ = g.add_node("s");
    let _ = g.add_node("t");
    for p in 0..paths {
        let cap = ((p + 1) * 2).to_string();
        let first = format!("p{p}_0");
        let _ = g.add_node(&first);
        let _ = g.add_edge_with_attrs("s", first, attr("capacity", &cap));
        for i in 1..path_len {
            let prev = format!("p{p}_{}", i - 1);
            let curr = format!("p{p}_{i}");
            let _ = g.add_node(&curr);
            let _ = g.add_edge_with_attrs(prev, curr, attr("capacity", &cap));
        }
        let last = format!("p{p}_{}", path_len - 1);
        let _ = g.add_edge_with_attrs(last, "t", attr("capacity", &cap));
    }
    g
}

fn build_weighted_grid(rows: usize, cols: usize) -> Graph {
    let mut g = Graph::strict();
    for r in 0..rows {
        for c in 0..cols {
            let _ = g.add_node(format!("{r}_{c}"));
        }
    }
    for r in 0..rows {
        for c in 0..cols {
            // Deterministic pseudo-weight so the relaxation order is non-trivial.
            if c + 1 < cols {
                let w = (((r * 7 + c * 13) % 17 + 1) as f64 * 0.5).to_string();
                let _ = g.add_edge_with_attrs(
                    format!("{r}_{c}"),
                    format!("{r}_{}", c + 1),
                    attr("weight", &w),
                );
            }
            if r + 1 < rows {
                let w = (((r * 11 + c * 5) % 19 + 1) as f64 * 0.5).to_string();
                let _ = g.add_edge_with_attrs(
                    format!("{r}_{c}"),
                    format!("{}_{c}", r + 1),
                    attr("weight", &w),
                );
            }
        }
    }
    g
}

fn build_common_neighbors_graph(left_only: usize, right_only: usize, common: usize) -> Graph {
    let mut g = Graph::strict();
    let _ = g.add_node("u");
    let _ = g.add_node("v");
    for i in 0..common {
        let node = format!("c{i}");
        let _ = g.add_edge("u", node.clone());
        let _ = g.add_edge("v", node);
    }
    for i in 0..left_only {
        let _ = g.add_edge("u", format!("l{i}"));
    }
    for i in 0..right_only {
        let _ = g.add_edge("v", format!("r{i}"));
    }
    g
}

fn build_community_common_neighbors_graph(
    left_only: usize,
    right_only: usize,
    common: usize,
) -> Graph {
    let mut g = Graph::strict();
    let _ = g.add_node_with_attrs("u", attr("community", "core"));
    let _ = g.add_node_with_attrs("v", attr("community", "core"));
    for i in 0..common {
        let node = format!("c{i}");
        let community = if i % 2 == 0 { "core" } else { "outer" };
        let _ = g.add_node_with_attrs(node.clone(), attr("community", community));
        let _ = g.add_edge("u", node.clone());
        let _ = g.add_edge("v", node);
    }
    for i in 0..left_only {
        let node = format!("l{i}");
        let _ = g.add_node_with_attrs(node.clone(), attr("community", "left"));
        let _ = g.add_edge("u", node);
    }
    for i in 0..right_only {
        let node = format!("r{i}");
        let _ = g.add_node_with_attrs(node.clone(), attr("community", "right"));
        let _ = g.add_edge("v", node);
    }
    g
}

fn build_link_prediction_pairs(repeats: usize) -> Vec<(String, String)> {
    (0..repeats)
        .map(|_| ("u".to_owned(), "v".to_owned()))
        .collect()
}

fn build_link_prediction_shared_source_pairs(
    repeats: usize,
    target_count: usize,
) -> Vec<(String, String)> {
    let target_count = target_count.max(1);
    (0..repeats)
        .map(|i| {
            let target = if i % target_count == 0 {
                "v".to_owned()
            } else {
                format!("r{}", i % target_count)
            };
            ("u".to_owned(), target)
        })
        .collect()
}

fn build_degree_mixing_hubs(hubs: usize, spokes_per_hub: usize) -> Graph {
    let mut g = Graph::strict();
    for hub in 0..hubs {
        let hub_node = format!("h{hub}");
        let _ = g.add_node(hub_node.clone());
        if hub > 0 {
            let _ = g.add_edge(format!("h{}", hub - 1), hub_node.clone());
        }
        for spoke in 0..spokes_per_hub {
            let spoke_node = format!("h{hub}_s{spoke}");
            let _ = g.add_edge(hub_node.clone(), spoke_node);
        }
    }
    g
}

fn build_average_degree_connectivity_mix(
    hubs: usize,
    spokes_per_hub: usize,
    isolates: usize,
) -> Graph {
    let mut g = build_degree_mixing_hubs(hubs, spokes_per_hub);
    for hub in 0..hubs.min(32) {
        let hub_node = format!("h{hub}");
        let _ = g.add_edge(hub_node.clone(), hub_node);
    }
    for isolate in 0..isolates {
        let _ = g.add_node(format!("iso{isolate}"));
    }
    g
}

fn build_directed_degree_xy_fan(layers: usize, fanout: usize) -> DiGraph {
    let mut dg = DiGraph::strict();
    for layer in 0..layers {
        let source = format!("s{layer}");
        let sink = format!("t{layer}");
        for spoke in 0..fanout {
            let mid = format!("m{layer}_{spoke}");
            let _ = dg.add_edge(source.clone(), mid.clone());
            let _ = dg.add_edge(mid, sink.clone());
        }
        if layer > 0 {
            let _ = dg.add_edge(format!("t{}", layer - 1), source);
        }
    }
    dg
}

fn bench_single_source_dijkstra(c: &mut Criterion) {
    let mut group = c.benchmark_group("single_source_dijkstra");
    for &side in &[20usize, 45, 64] {
        let g = build_weighted_grid(side, side);
        let label = side * side;
        group.bench_with_input(BenchmarkId::new("grid", label), &side, |b, _| {
            b.iter(|| single_source_dijkstra_path_length(&g, "0_0", "weight"));
        });
    }
    group.finish();
}

fn build_weighted_complete(n: usize) -> Graph {
    let mut g = Graph::strict();
    for i in 0..n {
        let _ = g.add_node(i.to_string());
    }
    for i in 0..n {
        for j in (i + 1)..n {
            let w = ((i + j + 1) as f64 * 0.5).to_string();
            let _ = g.add_edge_with_attrs(i.to_string(), j.to_string(), attr("weight", &w));
        }
    }
    g
}

// ---------------------------------------------------------------------------
// Benchmark: Shortest Path (unweighted)
// ---------------------------------------------------------------------------

fn bench_shortest_path_unweighted(c: &mut Criterion) {
    let mut group = c.benchmark_group("shortest_path_unweighted");
    for &n in &[50, 100, 500] {
        let g = build_path(n);
        group.bench_with_input(BenchmarkId::new("path", n), &n, |b, _| {
            b.iter(|| shortest_path_unweighted(&g, "0", &(n - 1).to_string()));
        });
    }
    for &n in &[20, 50, 100] {
        let g = build_complete(n);
        group.bench_with_input(BenchmarkId::new("complete", n), &n, |b, _| {
            b.iter(|| shortest_path_unweighted(&g, "0", &(n - 1).to_string()));
        });
    }
    group.finish();
}

// ---------------------------------------------------------------------------
// Benchmark: Shortest Path (weighted / Dijkstra)
// ---------------------------------------------------------------------------

fn bench_shortest_path_weighted(c: &mut Criterion) {
    let mut group = c.benchmark_group("shortest_path_weighted");
    for &n in &[20, 50, 100] {
        let g = build_weighted_complete(n);
        group.bench_with_input(BenchmarkId::new("complete", n), &n, |b, _| {
            b.iter(|| shortest_path_weighted(&g, "0", &(n - 1).to_string(), "weight"));
        });
    }
    group.finish();
}

// ---------------------------------------------------------------------------
// Benchmark: Connected Components
// ---------------------------------------------------------------------------

fn bench_connected_components(c: &mut Criterion) {
    let mut group = c.benchmark_group("connected_components");
    for &n in &[100, 500, 1000] {
        let g = build_path(n);
        group.bench_with_input(BenchmarkId::new("path", n), &n, |b, _| {
            b.iter(|| connected_components(&g));
        });
    }
    for &(r, co) in &[(10, 10), (20, 20), (30, 30)] {
        let g = build_grid(r, co);
        let label = r * co;
        group.bench_with_input(BenchmarkId::new("grid", label), &label, |b, _| {
            b.iter(|| connected_components(&g));
        });
    }
    group.finish();
}

fn bench_average_shortest_path_length(c: &mut Criterion) {
    let mut group = c.benchmark_group("average_shortest_path_length");
    for &(r, co) in &[(20, 20), (30, 30), (40, 40)] {
        let g = build_grid(r, co);
        let label = r * co;
        group.bench_with_input(BenchmarkId::new("grid", label), &label, |b, _| {
            b.iter(|| average_shortest_path_length(&g));
        });
    }
    group.finish();
}

// ---------------------------------------------------------------------------
// Benchmark: Centrality
// ---------------------------------------------------------------------------

fn bench_degree_centrality(c: &mut Criterion) {
    let mut group = c.benchmark_group("degree_centrality");
    for &n in &[50, 100, 500] {
        let g = build_path(n);
        group.bench_with_input(BenchmarkId::new("path", n), &n, |b, _| {
            b.iter(|| degree_centrality(&g));
        });
    }
    group.finish();
}

fn bench_closeness_centrality(c: &mut Criterion) {
    let mut group = c.benchmark_group("closeness_centrality");
    for &n in &[20, 50, 100] {
        let g = build_complete(n);
        group.bench_with_input(BenchmarkId::new("complete", n), &n, |b, _| {
            b.iter(|| closeness_centrality(&g));
        });
    }
    group.finish();
}

/// SUBSTRATE RULE v2: criterion group members run SEQUENTIALLY, so registering ORIG
/// and CAND side by side does NOT cancel worker/thermal drift — their samples come
/// from different wall-clock windows. The decision number must come from arms
/// interleaved INSIDE one loop, so each ratio is formed from an adjacent pair that
/// saw the same machine state. This routine does that and prints the per-pair ratio
/// distribution; the criterion rows below are kept only for absolute magnitudes.
///
/// Arm order alternates per round to cancel first/second ordering bias. Inputs and
/// results both pass through `black_box`, and both arms' scores are compared
/// bit-for-bit once up front — a DCE'd arm cannot produce a matching checksum, which
/// is the execution proof the ledger-integrity rule requires.
fn paired_interleaved_ab(
    label: &str,
    g: &Graph,
    cand_name: &str,
    cand: BitparArm,
    rounds: usize,
    // `run` must consume its result through black_box; `score_bits` supplies the
    // one-time bit-exactness proof. Passing them in lets closeness and harmonic
    // share this sampler without duplicating the statistics.
    run_arm: &dyn Fn(&Graph, BitparArm) -> usize,
    score_bits: &dyn Fn(&Graph, BitparArm) -> Vec<u64>,
) {
    use std::hint::black_box;
    use std::time::Instant;

    let run = |arm: BitparArm| -> usize { run_arm(black_box(g), black_box(arm)) };
    for _ in 0..3 {
        black_box(run(BitparArm::PerSource));
        black_box(run(cand));
    }

    // Execution + byte-exactness proof: both arms really compute, and agree. A
    // dead-code-eliminated arm cannot produce matching bits.
    let a = score_bits(g, BitparArm::PerSource);
    let b = score_bits(g, cand);
    assert_eq!(a.len(), b.len(), "{label}/{cand_name}: score count");
    let mut checksum = 0u64;
    for (i, (x, y)) in a.iter().zip(b.iter()).enumerate() {
        assert_eq!(x, y, "{label}/{cand_name}: arms diverge at score {i}");
        // Order-sensitive fold: a plain XOR cancels on symmetric graphs (a grid's
        // closeness values each occur an even number of times) and would print 0.
        checksum = checksum.rotate_left(7) ^ x.wrapping_mul(0x9E37_79B9_7F4A_7C15);
    }

    let (mut orig, mut cand_t, mut ratios) = (Vec::new(), Vec::new(), Vec::new());
    for r in 0..rounds {
        let (to, tc) = if r % 2 == 0 {
            let t = Instant::now();
            black_box(run(BitparArm::PerSource));
            let to = t.elapsed();
            let t = Instant::now();
            black_box(run(cand));
            (to, t.elapsed())
        } else {
            let t = Instant::now();
            black_box(run(cand));
            let tc = t.elapsed();
            let t = Instant::now();
            black_box(run(BitparArm::PerSource));
            (t.elapsed(), tc)
        };
        orig.push(to.as_secs_f64() * 1e3);
        cand_t.push(tc.as_secs_f64() * 1e3);
        ratios.push(to.as_secs_f64() / tc.as_secs_f64());
    }

    let median = |v: &[f64]| {
        let mut s = v.to_vec();
        s.sort_by(|a, b| a.partial_cmp(b).unwrap());
        s[s.len() / 2]
    };
    // The decision statistic is the MEDIAN paired ratio, so the quantity that must
    // clear the cv gate is the sampling error OF THAT MEDIAN — not the spread of
    // individual pairs, which on a shared worker mostly reflects other tenants.
    // Bootstrap it. `win_rate` is the distribution-free companion: the fraction of
    // adjacent pairs the candidate won, which drift cannot fake.
    let point = median(&ratios);
    let mut x: u64 = 0x9E37_79B9_7F4A_7C15;
    let mut rng = || {
        x ^= x << 13;
        x ^= x >> 7;
        x ^= x << 17;
        x
    };
    let resamples = 4000usize;
    let mut meds = Vec::with_capacity(resamples);
    for _ in 0..resamples {
        let s: Vec<f64> = (0..ratios.len())
            .map(|_| ratios[(rng() as usize) % ratios.len()])
            .collect();
        meds.push(median(&s));
    }
    meds.sort_by(|a, b| a.partial_cmp(b).unwrap());
    let ci_lo = meds[(resamples as f64 * 0.025) as usize];
    let ci_hi = meds[(resamples as f64 * 0.975) as usize];
    let bmean: f64 = meds.iter().sum::<f64>() / resamples as f64;
    let bvar: f64 = meds.iter().map(|m| (m - bmean).powi(2)).sum::<f64>() / resamples as f64;
    let median_cv = bvar.sqrt() / point * 100.0;
    let wins = ratios.iter().filter(|&&r| r > 1.0).count();
    let (lo, hi) = ratios
        .iter()
        .fold((f64::MAX, f64::MIN), |(l, h), &r| (l.min(r), h.max(r)));

    println!(
        "PAIRED {label} per_source vs {cand_name}: orig_med={:.3}ms cand_med={:.3}ms \
         ratio_med={:.3}x ci95=[{:.3},{:.3}] median_cv={:.2}% win_rate={}/{} \
         ratio_min={:.3}x ratio_max={:.3}x checksum={:#018x}",
        median(&orig),
        median(&cand_t),
        point,
        ci_lo,
        ci_hi,
        median_cv,
        wins,
        rounds,
        lo,
        hi,
        checksum
    );
}

/// br-r37-c1-x0jz8 A/B. BOTH arms live in this ONE group so a single
/// `rch exec -- cargo bench` invocation measures them on the SAME worker: rch has
/// no worker-pinning flag and its within-run ratio is not worker-invariant, so an
/// ORIG/CAND comparison split across two invocations is meaningless
/// (br-r37-c1-839yx). `per_source` is the pre-lever behaviour; `chunked_bitpar`
/// forces the candidate past its gate; `auto` is what callers actually get.
fn bench_closeness_centrality_parallel(c: &mut Criterion) {
    let run = |g: &Graph, arm: BitparArm| -> usize {
        std::hint::black_box(closeness_centrality_arm(g, arm).scores.len())
    };
    let bits = |g: &Graph, arm: BitparArm| -> Vec<u64> {
        closeness_centrality_arm(g, arm)
            .scores
            .iter()
            .map(|s| s.score.to_bits())
            .collect()
    };
    for (label, g) in [
        ("closeness/lowdiam_2000", build_low_diameter(2000, 8000)),
        ("closeness/grid_1600", build_grid(40, 40)),
    ] {
        paired_interleaved_ab(label, &g, "auto", BitparArm::Auto, 61, &run, &bits);
        paired_interleaved_ab(
            label,
            &g,
            "chunked_bitpar",
            BitparArm::ChunkedBitpar,
            61,
            &run,
            &bits,
        );
    }

    let mut group = c.benchmark_group("closeness_centrality_parallel");
    // n >= CENTRALITY_PARALLEL_THRESHOLD on both, so the per-source arm is the
    // rayon fan-out this lever is trying to beat.
    let workloads = [
        ("lowdiam_2000", build_low_diameter(2000, 8000)),
        ("grid_1600", build_grid(40, 40)), // GUARD: high diameter, must not regress
    ];
    let arms = [
        ("per_source", BitparArm::PerSource),
        ("chunked_bitpar", BitparArm::ChunkedBitpar),
        ("auto", BitparArm::Auto),
    ];
    for (workload, g) in &workloads {
        for (arm_name, arm) in arms {
            group.bench_with_input(BenchmarkId::new(arm_name, workload), &arm, |b, &arm| {
                b.iter(|| closeness_centrality_arm(g, arm))
            });
        }
        // Stage cost, MEASURED not inferred: every bit-parallel arm pays this
        // reverse-CSR build before it traverses anything, so a REJECT that blames
        // it has to be able to point at a number.
        group.bench_with_input(
            BenchmarkId::new("csr_build_only", workload),
            workload,
            |b, _| b.iter(|| closeness_reverse_csr_build_cost(g)),
        );
    }
    group.finish();
}

/// br-r37-c1-bger9: aspl on the same chunked-parallel driver. aspl returns a single
/// f64, so `score_bits` yields a one-element vector — the bit-exactness assert still
/// runs, and it is meaningful because `AsplAgg::merge` must be order-free for rayon's
/// reduction tree to reproduce the sequential aggregate exactly.
fn bench_aspl_parallel(c: &mut Criterion) {
    let run = |g: &Graph, arm: BitparArm| -> usize {
        std::hint::black_box(
            average_shortest_path_length_arm(g, arm)
                .average_shortest_path_length
                .to_bits() as usize,
        )
    };
    let bits = |g: &Graph, arm: BitparArm| -> Vec<u64> {
        vec![
            average_shortest_path_length_arm(g, arm)
                .average_shortest_path_length
                .to_bits(),
        ]
    };
    let workloads = [
        ("aspl/lowdiam_2000", build_low_diameter(2000, 8000)),
        ("aspl/grid_1600", build_grid(40, 40)), // GUARD: gate must decline
    ];
    for (label, g) in &workloads {
        paired_interleaved_ab(label, g, "auto", BitparArm::Auto, 121, &run, &bits);
        paired_interleaved_ab(
            label,
            g,
            "chunked_bitpar",
            BitparArm::ChunkedBitpar,
            121,
            &run,
            &bits,
        );
    }

    let mut group = c.benchmark_group("aspl_parallel");
    for (label, g) in &workloads {
        for (arm_name, arm) in [
            ("per_source", BitparArm::PerSource),
            ("chunked_bitpar", BitparArm::ChunkedBitpar),
            ("auto", BitparArm::Auto),
        ] {
            group.bench_with_input(BenchmarkId::new(arm_name, label), &arm, |b, &arm| {
                b.iter(|| average_shortest_path_length_arm(g, arm))
            });
        }
        // The gate's ENTIRE added cost on a declined graph: CSR build + probe, and
        // nothing else. Measured, so the guard regression is attributed rather than
        // explained by subtracting noisy arms.
        // The declined path's ENTIRE added cost, measured both ways. `unbounded` is
        // what run 3 shipped in the tree; `bounded` stops the walk once the gate's
        // answer is determined.
        group.bench_with_input(
            BenchmarkId::new("gate_probe_unbounded", label),
            label,
            |b, _| b.iter(|| aspl_gate_overhead_cost(g, false)),
        );
        group.bench_with_input(
            BenchmarkId::new("gate_probe_bounded", label),
            label,
            |b, _| b.iter(|| aspl_gate_overhead_cost(g, true)),
        );
    }
    group.finish();
}

/// br-r37-c1-qdcdq: harmonic on the same chunked-parallel driver, measured with the
/// same interleaved paired sampler. Harmonic accumulates f64, so the bit-exactness
/// assertion inside the sampler is doing real work here — chunking must repartition
/// SOURCES only, never the addition order within a source.
fn bench_harmonic_centrality_parallel(c: &mut Criterion) {
    let run = |g: &Graph, arm: BitparArm| -> usize {
        std::hint::black_box(harmonic_centrality_arm(g, arm).scores.len())
    };
    let bits = |g: &Graph, arm: BitparArm| -> Vec<u64> {
        harmonic_centrality_arm(g, arm)
            .scores
            .iter()
            .map(|s| s.score.to_bits())
            .collect()
    };
    let workloads = [
        ("harmonic/lowdiam_2000", build_low_diameter(2000, 8000)),
        ("harmonic/grid_1600", build_grid(40, 40)), // GUARD: gate must decline
    ];
    // 121 rounds, not 61: harmonic's per-source arm pays an f64 division per popped
    // node, so its grid rows are noisier than closeness's and 61 rounds left the
    // GUARD row's bootstrapped median at cv 6.00% — above the keep-gate. The extra
    // rounds tighten the estimator, they do not change what is measured.
    for (label, g) in &workloads {
        paired_interleaved_ab(label, g, "auto", BitparArm::Auto, 121, &run, &bits);
        paired_interleaved_ab(
            label,
            g,
            "chunked_bitpar",
            BitparArm::ChunkedBitpar,
            121,
            &run,
            &bits,
        );
    }

    let mut group = c.benchmark_group("harmonic_centrality_parallel");
    for (label, g) in &workloads {
        for (arm_name, arm) in [
            ("per_source", BitparArm::PerSource),
            ("chunked_bitpar", BitparArm::ChunkedBitpar),
            ("auto", BitparArm::Auto),
        ] {
            group.bench_with_input(BenchmarkId::new(arm_name, label), &arm, |b, &arm| {
                b.iter(|| harmonic_centrality_arm(g, arm))
            });
        }
    }
    group.finish();
}

fn bench_harmonic_centrality(c: &mut Criterion) {
    let mut group = c.benchmark_group("harmonic_centrality");
    // `complete` mirrors the closeness sizes (diameter 1). The grids are the
    // high-diameter counterpoint, where an all-pairs BFS reduction has many more
    // levels and far less to gain per traversal.
    for &n in &[20, 50, 100] {
        let g = build_complete(n);
        group.bench_with_input(BenchmarkId::new("complete", n), &n, |b, _| {
            b.iter(|| harmonic_centrality(&g));
        });
    }
    for &(r, co) in &[(10, 10), (20, 20)] {
        let g = build_grid(r, co);
        let label = r * co;
        group.bench_with_input(BenchmarkId::new("grid", label), &label, |b, _| {
            b.iter(|| harmonic_centrality(&g));
        });
    }
    group.finish();
}

fn bench_betweenness_centrality(c: &mut Criterion) {
    let mut group = c.benchmark_group("betweenness_centrality");
    for &n in &[20, 50, 100] {
        let g = build_complete(n);
        group.bench_with_input(BenchmarkId::new("complete", n), &n, |b, _| {
            b.iter(|| betweenness_centrality(&g));
        });
    }
    group.finish();
}

fn bench_eigenvector_centrality(c: &mut Criterion) {
    let mut group = c.benchmark_group("eigenvector_centrality");
    for &n in &[20, 50, 100] {
        let g = build_complete(n);
        group.bench_with_input(BenchmarkId::new("complete", n), &n, |b, _| {
            b.iter(|| eigenvector_centrality(&g));
        });
    }
    group.finish();
}

fn bench_pagerank(c: &mut Criterion) {
    let mut group = c.benchmark_group("pagerank");
    for &n in &[50, 100, 500] {
        let g = build_path(n);
        group.bench_with_input(BenchmarkId::new("path", n), &n, |b, _| {
            b.iter(|| pagerank(&g));
        });
    }
    for &n in &[20, 50, 100] {
        let g = build_complete(n);
        group.bench_with_input(BenchmarkId::new("complete", n), &n, |b, _| {
            b.iter(|| pagerank(&g));
        });
    }
    group.finish();
}

fn bench_common_neighbors(c: &mut Criterion) {
    let mut group = c.benchmark_group("common_neighbors");
    for &(left_only, right_only, common) in &[(64, 64, 64), (32, 512, 32), (512, 512, 256)] {
        let g = build_common_neighbors_graph(left_only, right_only, common);
        let label = format!("l{left_only}_r{right_only}_c{common}");
        group.bench_with_input(BenchmarkId::new("overlap_rows", &label), &label, |b, _| {
            b.iter(|| common_neighbors(&g, "u", "v"));
        });
    }
    group.finish();
}

fn bench_degree_mixing_dict(c: &mut Criterion) {
    let mut group = c.benchmark_group("degree_mixing_dict");
    for &(hubs, spokes) in &[(64usize, 32usize), (256, 16), (512, 32)] {
        let g = build_degree_mixing_hubs(hubs, spokes);
        let label = format!("h{hubs}_s{spokes}");
        group.bench_with_input(BenchmarkId::new("hub_spokes", &label), &label, |b, _| {
            b.iter(|| degree_mixing_dict(&g));
        });
    }
    group.finish();
}

fn bench_average_degree_connectivity(c: &mut Criterion) {
    let mut group = c.benchmark_group("average_degree_connectivity");
    for &(hubs, spokes, isolates) in &[(64usize, 32usize, 64usize), (256, 16, 128), (512, 32, 256)]
    {
        let g = build_average_degree_connectivity_mix(hubs, spokes, isolates);
        let label = format!("h{hubs}_s{spokes}_i{isolates}");
        group.bench_with_input(
            BenchmarkId::new("hub_spokes_isolates", &label),
            &label,
            |b, _| {
                b.iter(|| average_degree_connectivity(&g));
            },
        );
    }
    group.finish();
}

fn bench_node_degree_xy(c: &mut Criterion) {
    let mut group = c.benchmark_group("node_degree_xy");
    for &(hubs, spokes) in &[(64usize, 32usize), (256, 16), (512, 32)] {
        let g = build_degree_mixing_hubs(hubs, spokes);
        let label = format!("h{hubs}_s{spokes}");
        group.bench_with_input(
            BenchmarkId::new("undirected_hub_spokes", &label),
            &label,
            |b, _| {
                b.iter(|| node_degree_xy(&g));
            },
        );
    }
    for &(layers, fanout) in &[(64usize, 32usize), (256, 16), (512, 32)] {
        let dg = build_directed_degree_xy_fan(layers, fanout);
        let label = format!("l{layers}_f{fanout}");
        group.bench_with_input(BenchmarkId::new("directed_fan", &label), &label, |b, _| {
            b.iter(|| fnx_algorithms::node_degree_xy_directed(&dg, "out", "in"));
        });
    }
    group.finish();
}

fn bench_link_prediction_scores(c: &mut Criterion) {
    let mut group = c.benchmark_group("link_prediction_scores");
    for &(left_only, right_only, common, repeats) in &[
        (64, 64, 64, 128),
        (32, 512, 32, 128),
        (512, 512, 256, 64),
        (32, 512, 32, 2048),
    ] {
        let g = build_common_neighbors_graph(left_only, right_only, common);
        let pairs = build_link_prediction_pairs(repeats);
        let label = format!("l{left_only}_r{right_only}_c{common}_p{repeats}");
        group.bench_with_input(BenchmarkId::new("jaccard", &label), &label, |b, _| {
            b.iter(|| jaccard_coefficient(&g, &pairs));
        });
        group.bench_with_input(BenchmarkId::new("adamic_adar", &label), &label, |b, _| {
            b.iter(|| adamic_adar_index(&g, &pairs));
        });
        group.bench_with_input(
            BenchmarkId::new("resource_allocation", &label),
            &label,
            |b, _| {
                b.iter(|| resource_allocation_index(&g, &pairs));
            },
        );
        group.bench_with_input(
            BenchmarkId::new("common_neighbor_centrality", &label),
            &label,
            |b, _| {
                b.iter(|| common_neighbor_centrality(&g, &pairs, 0.8));
            },
        );
        let shared_source_pairs =
            build_link_prediction_shared_source_pairs(repeats, right_only.min(64));
        group.bench_with_input(
            BenchmarkId::new("common_neighbor_centrality_shared_source", &label),
            &label,
            |b, _| {
                b.iter(|| common_neighbor_centrality(&g, &shared_source_pairs, 0.8));
            },
        );
        group.bench_with_input(
            BenchmarkId::new("preferential_attachment", &label),
            &label,
            |b, _| {
                b.iter(|| preferential_attachment(&g, &pairs));
            },
        );

        let community_graph = build_community_common_neighbors_graph(left_only, right_only, common);
        group.bench_with_input(
            BenchmarkId::new("cn_soundarajan_hopcroft", &label),
            &label,
            |b, _| {
                b.iter(|| cn_soundarajan_hopcroft(&community_graph, &pairs, "community"));
            },
        );
        group.bench_with_input(
            BenchmarkId::new("ra_index_soundarajan_hopcroft", &label),
            &label,
            |b, _| {
                b.iter(|| ra_index_soundarajan_hopcroft(&community_graph, &pairs, "community"));
            },
        );
    }
    group.finish();
}

// ---------------------------------------------------------------------------
// Benchmark: Flow
// ---------------------------------------------------------------------------

fn bench_max_flow(c: &mut Criterion) {
    let mut group = c.benchmark_group("max_flow");
    for &(paths, len) in &[(3, 5), (5, 5), (5, 10), (10, 5)] {
        let g = build_flow_network(paths, len);
        let label = format!("{paths}x{len}");
        group.bench_with_input(
            BenchmarkId::new("parallel_paths", &label),
            &label,
            |b, _| {
                b.iter(|| {
                    max_flow_edmonds_karp(&g, "s", "t", "capacity")
                        .expect("flow algorithm should succeed")
                });
            },
        );
    }
    group.finish();
}

fn bench_minimum_cut(c: &mut Criterion) {
    let mut group = c.benchmark_group("minimum_cut");
    for &(paths, len) in &[(3, 5), (5, 5), (5, 10)] {
        let g = build_flow_network(paths, len);
        let label = format!("{paths}x{len}");
        group.bench_with_input(
            BenchmarkId::new("parallel_paths", &label),
            &label,
            |b, _| {
                b.iter(|| {
                    minimum_cut_edmonds_karp(&g, "s", "t", "capacity")
                        .expect("flow algorithm should succeed")
                });
            },
        );
    }
    group.finish();
}

// ---------------------------------------------------------------------------
// Benchmark: Minimum Spanning Tree
// ---------------------------------------------------------------------------

fn bench_minimum_spanning_tree(c: &mut Criterion) {
    let mut group = c.benchmark_group("minimum_spanning_tree");
    for &n in &[20, 50, 100] {
        let g = build_weighted_complete(n);
        group.bench_with_input(BenchmarkId::new("complete", n), &n, |b, _| {
            b.iter(|| minimum_spanning_tree(&g, "weight"));
        });
    }
    group.finish();
}

// ---------------------------------------------------------------------------
// Entry point
// ---------------------------------------------------------------------------

criterion_group!(
    benches,
    bench_shortest_path_unweighted,
    bench_shortest_path_weighted,
    bench_single_source_dijkstra,
    bench_connected_components,
    bench_average_shortest_path_length,
    bench_aspl_parallel,
    bench_degree_centrality,
    bench_closeness_centrality,
    bench_closeness_centrality_parallel,
    bench_harmonic_centrality,
    bench_harmonic_centrality_parallel,
    bench_betweenness_centrality,
    bench_eigenvector_centrality,
    bench_pagerank,
    bench_common_neighbors,
    bench_degree_mixing_dict,
    bench_average_degree_connectivity,
    bench_node_degree_xy,
    bench_link_prediction_scores,
    bench_max_flow,
    bench_minimum_cut,
    bench_minimum_spanning_tree,
);
criterion_main!(benches);
