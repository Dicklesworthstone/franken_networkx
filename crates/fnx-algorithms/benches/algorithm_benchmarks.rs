#![forbid(unsafe_code)]

//! Benchmark families for core algorithm categories.
//!
//! Run:   cargo bench -p fnx-algorithms
//! Gate:  check p50/p95/p99 via criterion JSON output in target/criterion/

use std::collections::BTreeMap;

use criterion::{BenchmarkId, Criterion, criterion_group, criterion_main};
use fnx_algorithms::{
    adamic_adar_index, average_shortest_path_length, betweenness_centrality,
    closeness_centrality, cn_soundarajan_hopcroft, common_neighbor_centrality,
    common_neighbors, connected_components, degree_centrality, eigenvector_centrality,
    jaccard_coefficient, max_flow_edmonds_karp, minimum_cut_edmonds_karp,
    minimum_spanning_tree, pagerank, preferential_attachment, ra_index_soundarajan_hopcroft,
    resource_allocation_index, shortest_path_unweighted, shortest_path_weighted,
    single_source_dijkstra_path_length,
};
use fnx_classes::Graph;
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

fn bench_link_prediction_scores(c: &mut Criterion) {
    let mut group = c.benchmark_group("link_prediction_scores");
    for &(left_only, right_only, common, repeats) in
        &[
            (64, 64, 64, 128),
            (32, 512, 32, 128),
            (512, 512, 256, 64),
            (32, 512, 32, 2048),
        ]
    {
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

        let community_graph =
            build_community_common_neighbors_graph(left_only, right_only, common);
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
    bench_degree_centrality,
    bench_closeness_centrality,
    bench_betweenness_centrality,
    bench_eigenvector_centrality,
    bench_pagerank,
    bench_common_neighbors,
    bench_link_prediction_scores,
    bench_max_flow,
    bench_minimum_cut,
    bench_minimum_spanning_tree,
);
criterion_main!(benches);
