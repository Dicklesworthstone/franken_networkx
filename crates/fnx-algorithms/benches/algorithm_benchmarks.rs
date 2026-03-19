#![forbid(unsafe_code)]

//! Benchmark families for core algorithm categories.
//!
//! Run:   cargo bench -p fnx-algorithms
//! Gate:  check p50/p95/p99 via criterion JSON output in target/criterion/

use std::collections::BTreeMap;

use criterion::{BenchmarkId, Criterion, criterion_group, criterion_main};
use fnx_algorithms::{
    betweenness_centrality, closeness_centrality, connected_components, degree_centrality,
    eigenvector_centrality, max_flow_edmonds_karp, minimum_cut_edmonds_karp, minimum_spanning_tree,
    pagerank, shortest_path_unweighted, shortest_path_weighted,
};
use fnx_classes::Graph;

fn attr(key: &str, val: &str) -> BTreeMap<String, String> {
    let mut m = BTreeMap::new();
    m.insert(key.to_owned(), val.to_owned());
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
                b.iter(|| max_flow_edmonds_karp(&g, "s", "t", "capacity"));
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
                b.iter(|| minimum_cut_edmonds_karp(&g, "s", "t", "capacity"));
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
    bench_connected_components,
    bench_degree_centrality,
    bench_closeness_centrality,
    bench_betweenness_centrality,
    bench_eigenvector_centrality,
    bench_pagerank,
    bench_max_flow,
    bench_minimum_cut,
    bench_minimum_spanning_tree,
);
criterion_main!(benches);
