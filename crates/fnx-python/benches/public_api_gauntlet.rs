#![forbid(unsafe_code)]

use criterion::{BenchmarkId, Criterion, SamplingMode, criterion_group, criterion_main};
use pyo3::types::PyAnyMethods;
use pyo3::{Bound, Py, PyAny, Python};
use std::time::{Duration, Instant};

#[derive(Debug, Eq, PartialEq)]
struct BidirectionalOutput {
    length_bits: u64,
    all_int: bool,
    path: Vec<String>,
}

fn timed_python_call<'py>(callable: &Bound<'py, PyAny>) -> (Duration, Bound<'py, PyAny>) {
    let start = Instant::now();
    let result = callable.call0();
    let elapsed = start.elapsed();
    (
        elapsed,
        result.expect("paired bidirectional-Dijkstra callable failed"),
    )
}

fn extract_bidirectional_output(result: &Bound<'_, PyAny>) -> BidirectionalOutput {
    let (length, all_int, path) = result
        .extract::<(f64, bool, Vec<String>)>()
        .expect("paired bidirectional-Dijkstra result must be (float, bool, list[str])");
    BidirectionalOutput {
        length_bits: length.to_bits(),
        all_int,
        path,
    }
}

fn mean_and_cv_pct(values: &[f64]) -> (f64, f64) {
    assert!(
        values.len() >= 2,
        "paired A/B requires at least two samples"
    );
    let mean = values.iter().sum::<f64>() / values.len() as f64;
    let variance = values
        .iter()
        .map(|value| {
            let delta = value - mean;
            delta * delta
        })
        .sum::<f64>()
        / (values.len() - 1) as f64;
    (mean, 100.0 * variance.sqrt() / mean)
}

fn bench_paired_multigraph_bidirectional(c: &mut Criterion, candidate: Py<PyAny>, orig: Py<PyAny>) {
    let mut samples = Vec::<(f64, f64)>::new();
    let mut candidate_first = true;
    let mut group = c.benchmark_group("multigraph_bidirectional_dijkstra_string_target_ab");
    group.sampling_mode(SamplingMode::Flat);
    group.bench_function("candidate_vs_current_native_orig", |b| {
        b.iter_custom(|iters| {
            Python::attach(|py| {
                let candidate = candidate.bind(py);
                let orig = orig.bind(py);
                let mut candidate_elapsed = Duration::ZERO;
                let mut orig_elapsed = Duration::ZERO;
                for _ in 0..iters {
                    let (candidate_duration, candidate_result, orig_duration, orig_result) =
                        if candidate_first {
                            let (candidate_duration, candidate_result) =
                                timed_python_call(candidate);
                            let (orig_duration, orig_result) = timed_python_call(orig);
                            (
                                candidate_duration,
                                candidate_result,
                                orig_duration,
                                orig_result,
                            )
                        } else {
                            let (orig_duration, orig_result) = timed_python_call(orig);
                            let (candidate_duration, candidate_result) =
                                timed_python_call(candidate);
                            (
                                candidate_duration,
                                candidate_result,
                                orig_duration,
                                orig_result,
                            )
                        };
                    candidate_first = !candidate_first;
                    candidate_elapsed += candidate_duration;
                    orig_elapsed += orig_duration;
                    assert_eq!(
                        extract_bidirectional_output(&candidate_result),
                        extract_bidirectional_output(&orig_result),
                        "paired native ORIG/candidate parity drift"
                    );
                }
                samples.push((
                    candidate_elapsed.as_secs_f64() * 1.0e9 / iters as f64,
                    orig_elapsed.as_secs_f64() * 1.0e9 / iters as f64,
                ));
                candidate_elapsed
            })
        });
    });
    group.finish();

    if samples.len() < 2 {
        return;
    }
    let sample_count = 20_usize.min(samples.len());
    let decision_samples = &samples[samples.len() - sample_count..];
    let candidate_values = decision_samples
        .iter()
        .map(|(candidate_ns, _)| *candidate_ns)
        .collect::<Vec<_>>();
    let orig_values = decision_samples
        .iter()
        .map(|(_, orig_ns)| *orig_ns)
        .collect::<Vec<_>>();
    let (candidate_mean_ns, candidate_cv_pct) = mean_and_cv_pct(&candidate_values);
    let (orig_mean_ns, orig_cv_pct) = mean_and_cv_pct(&orig_values);
    eprintln!(
        "PAIRED_AB samples={sample_count} candidate_mean_ns={candidate_mean_ns:.3} \
         candidate_cv_pct={candidate_cv_pct:.6} orig_mean_ns={orig_mean_ns:.3} \
         orig_cv_pct={orig_cv_pct:.6} speedup_orig_over_candidate={:.6}",
        orig_mean_ns / candidate_mean_ns
    );
}

fn init_python() {
    static START: std::sync::Once = std::sync::Once::new();
    START.call_once(Python::initialize);
}

fn bench_py_callable(c: &mut Criterion, workload: &str, engine: &str, callable: Py<PyAny>) {
    c.bench_with_input(
        BenchmarkId::new(workload, engine),
        &callable,
        |b, callable| {
            b.iter(|| {
                Python::attach(|py| {
                    callable
                        .bind(py)
                        .call0()
                        .and_then(|value| value.extract::<f64>())
                        .expect("Python benchmark callable should return float")
                })
            });
        },
    );
}

fn bench_public_api_gauntlet(c: &mut Criterion) {
    init_python();
    Python::attach(|py| {
        // br-gauntletfix (cc): the sys.path setup used os.getcwd(), which is only the
        // repo root when `cargo bench` is launched there — under `rch exec` (remote
        // worker) the CWD differs, so `import networkx.exception` / the helper import
        // failed and the bench panicked. Inject the repo root from CARGO_MANIFEST_DIR
        // (compile-time, absolute) like networkx_head_to_head does, so the bench runs
        // identically locally and on remote workers.
        let repo_root = std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
            .parent()
            .and_then(std::path::Path::parent)
            .expect("fnx-python crate must live under crates/")
            .to_str()
            .expect("repo path must be UTF-8");
        let preload_src = format!(
            "import glob, hashlib, importlib.util, os, sys
cwd = {repo_root:?}
for rel_path in (
    'crates/fnx-python/benches',
    'python',
    'legacy_networkx_code/networkx',
    'legacy_networkx_code',
):
    path = os.path.join(cwd, rel_path)
    if path not in sys.path:
        sys.path.insert(0, path)
import networkx.exception
available_cpus = sorted(os.sched_getaffinity(0))
if available_cpus:
    bench_cpu = available_cpus[-1]
    os.sched_setaffinity(0, set((bench_cpu,)))
    print(f'fnx bench cpu: {{bench_cpu}}', file=sys.stderr)
target_dir = os.environ.get('CARGO_TARGET_DIR') or os.path.join(cwd, 'target')
if target_dir:
    perf_candidates = sorted(
        [path for path in [
            os.path.join(target_dir, 'release-perf', 'lib_fnx.so'),
            *glob.glob(os.path.join(target_dir, 'release-perf', 'deps', 'lib_fnx*.so')),
        ] if os.path.exists(path)],
        key=os.path.getmtime,
        reverse=True,
    )
    release_candidates = sorted(
        [path for path in [
            os.path.join(target_dir, 'release', 'lib_fnx.so'),
            *glob.glob(os.path.join(target_dir, 'release', 'deps', 'lib_fnx*.so')),
        ] if os.path.exists(path)],
        key=os.path.getmtime,
        reverse=True,
    )
    candidates = [
        *perf_candidates,
        *release_candidates,
    ]
    loaded_path = None
    for path in candidates:
        if os.path.exists(path):
            spec = importlib.util.spec_from_file_location('franken_networkx._fnx', path)
            module = importlib.util.module_from_spec(spec)
            sys.modules['franken_networkx._fnx'] = module
            spec.loader.exec_module(module)
            loaded_path = path
            break
    if loaded_path is None:
        raise RuntimeError(f'no freshly built fnx extension under {{target_dir}}')
    with open(loaded_path, 'rb') as extension_file:
        extension_sha = hashlib.sha256(extension_file.read()).hexdigest()
    print(f'fnx bench extension: {{loaded_path}} sha256={{extension_sha}}', file=sys.stderr)"
        );
        py.run(
            std::ffi::CString::new(preload_src)
                .expect("preload source contains no interior nul")
                .as_c_str(),
            None,
            None,
        )
        .expect("failed to preload freshly built fnx extension");
        let helper = py
            .import("public_api_gauntlet")
            .expect("set PYTHONPATH=crates/fnx-python/benches:python:legacy_networkx_code");
        if let (Ok(candidate), Ok(orig)) = (
            helper.getattr("candidate_multigraph_bidirectional_native_once"),
            helper.getattr("orig_multigraph_bidirectional_native_once"),
        ) {
            bench_paired_multigraph_bidirectional(c, candidate.unbind(), orig.unbind());
        }
        for (workload, engine, callable_name) in [
            (
                "from_graph6_bytes_sparse_700",
                "fnx",
                "fnx_from_graph6_bytes_sparse_700",
            ),
            (
                "from_graph6_bytes_sparse_700",
                "networkx",
                "networkx_from_graph6_bytes_sparse_700",
            ),
            (
                "write_gml_int_edge_attrs",
                "fnx",
                "fnx_write_gml_int_edge_attrs",
            ),
            (
                "write_gml_int_edge_attrs",
                "networkx",
                "networkx_write_gml_int_edge_attrs",
            ),
            (
                "create_empty_copy_node_attrs_10k",
                "fnx",
                "fnx_create_empty_copy_node_attrs_10k",
            ),
            (
                "create_empty_copy_node_attrs_10k",
                "networkx",
                "networkx_create_empty_copy_node_attrs_10k",
            ),
            (
                "tournament_is_reachable_bitset_220",
                "fnx",
                "fnx_tournament_is_reachable_bitset_220",
            ),
            (
                "tournament_is_reachable_bitset_220",
                "networkx",
                "networkx_tournament_is_reachable_bitset_220",
            ),
            (
                "summarization_dedensify_copy_dense_hubs",
                "fnx",
                "fnx_summarization_dedensify_copy_dense_hubs",
            ),
            (
                "summarization_dedensify_copy_dense_hubs",
                "networkx",
                "networkx_summarization_dedensify_copy_dense_hubs",
            ),
            (
                "edge_boundary_target_sparse",
                "fnx",
                "fnx_edge_boundary_target_sparse",
            ),
            (
                "edge_boundary_target_sparse",
                "networkx",
                "networkx_edge_boundary_target_sparse",
            ),
            (
                "flow_hierarchy_weighted_cyclic_dag",
                "fnx",
                "fnx_flow_hierarchy_weighted_cyclic_dag",
            ),
            (
                "flow_hierarchy_weighted_cyclic_dag",
                "networkx",
                "networkx_flow_hierarchy_weighted_cyclic_dag",
            ),
            (
                "within_inter_cluster_explicit_community",
                "fnx",
                "fnx_within_inter_cluster_explicit_community",
            ),
            (
                "within_inter_cluster_explicit_community",
                "networkx",
                "networkx_within_inter_cluster_explicit_community",
            ),
            (
                "non_edges_sparse_undirected",
                "fnx",
                "fnx_non_edges_sparse_undirected",
            ),
            (
                "non_edges_sparse_undirected",
                "networkx",
                "networkx_non_edges_sparse_undirected",
            ),
            (
                "fast_gnp_create_using_graph",
                "fnx",
                "fnx_fast_gnp_create_using_graph",
            ),
            (
                "fast_gnp_create_using_graph",
                "networkx",
                "networkx_fast_gnp_create_using_graph",
            ),
            (
                "fast_gnp_create_using_digraph",
                "fnx",
                "fnx_fast_gnp_create_using_digraph",
            ),
            (
                "fast_gnp_create_using_digraph",
                "networkx",
                "networkx_fast_gnp_create_using_digraph",
            ),
            (
                "ubizp_multigraph_single_source_shortest_path",
                "fnx",
                "fnx_ubizp_multigraph_single_source_shortest_path",
            ),
            (
                "ubizp_multigraph_single_source_shortest_path",
                "networkx",
                "networkx_ubizp_multigraph_single_source_shortest_path",
            ),
            (
                "multidigraph_single_target_shortest_path_length",
                "fnx",
                "fnx_multidigraph_single_target_shortest_path_length",
            ),
            (
                "multidigraph_single_target_shortest_path_length",
                "networkx",
                "networkx_multidigraph_single_target_shortest_path_length",
            ),
            (
                "digraph_weighted_target_shortest_path_length",
                "fnx",
                "fnx_digraph_weighted_target_shortest_path_length",
            ),
            (
                "digraph_weighted_target_shortest_path_length",
                "networkx",
                "networkx_digraph_weighted_target_shortest_path_length",
            ),
            (
                "string_graph_single_source_shortest_path",
                "fnx",
                "fnx_string_graph_single_source_shortest_path",
            ),
            (
                "string_graph_single_source_shortest_path",
                "networkx",
                "networkx_string_graph_single_source_shortest_path",
            ),
            (
                "multidigraph_single_source_shortest_path",
                "fnx",
                "fnx_multidigraph_single_source_shortest_path",
            ),
            (
                "multidigraph_single_source_shortest_path",
                "networkx",
                "networkx_multidigraph_single_source_shortest_path",
            ),
            (
                "multidigraph_bfs_edges",
                "fnx",
                "fnx_multidigraph_bfs_edges",
            ),
            (
                "multidigraph_bfs_edges",
                "networkx",
                "networkx_multidigraph_bfs_edges",
            ),
            (
                "multidigraph_strongly_connected_components",
                "fnx",
                "fnx_multidigraph_strongly_connected_components",
            ),
            (
                "multidigraph_strongly_connected_components",
                "networkx",
                "networkx_multidigraph_strongly_connected_components",
            ),
            (
                "directed_pagerank_large",
                "fnx",
                "fnx_directed_pagerank_large",
            ),
            (
                "directed_pagerank_large",
                "networkx",
                "networkx_directed_pagerank_large",
            ),
            (
                "multidigraph_dijkstra_path_length_target_early_exit",
                "fnx",
                "fnx_multidigraph_dijkstra_path_length_target_early_exit",
            ),
            (
                "multidigraph_dijkstra_path_length_target_early_exit",
                "networkx",
                "networkx_multidigraph_dijkstra_path_length_target_early_exit",
            ),
            (
                "multidigraph_dijkstra_path_target_early_exit",
                "fnx",
                "fnx_multidigraph_dijkstra_path_target_early_exit",
            ),
            (
                "multidigraph_dijkstra_path_target_early_exit",
                "networkx",
                "networkx_multidigraph_dijkstra_path_target_early_exit",
            ),
            (
                "multigraph_dijkstra_path_string_target",
                "fnx",
                "fnx_multigraph_dijkstra_path_string_target",
            ),
            (
                "multigraph_dijkstra_path_string_target",
                "networkx",
                "networkx_multigraph_dijkstra_path_string_target",
            ),
            (
                "multigraph_shortest_path_string_target",
                "fnx",
                "fnx_multigraph_shortest_path_string_target",
            ),
            (
                "multigraph_shortest_path_string_target",
                "orig",
                "orig_multigraph_shortest_path_string_target",
            ),
            (
                "multigraph_shortest_path_string_target",
                "networkx",
                "networkx_multigraph_shortest_path_string_target",
            ),
            (
                "multigraph_bidirectional_dijkstra_string_target",
                "fnx",
                "fnx_multigraph_bidirectional_dijkstra_string_target",
            ),
            (
                "multigraph_bidirectional_dijkstra_string_target",
                "orig",
                "orig_multigraph_bidirectional_dijkstra_string_target",
            ),
            (
                "multigraph_bidirectional_dijkstra_string_target",
                "networkx",
                "networkx_multigraph_bidirectional_dijkstra_string_target",
            ),
            (
                "multidigraph_single_source_dijkstra_path_length",
                "fnx",
                "fnx_multidigraph_single_source_dijkstra_path_length",
            ),
            (
                "multidigraph_single_source_dijkstra_path_length",
                "networkx",
                "networkx_multidigraph_single_source_dijkstra_path_length",
            ),
            (
                "raw_adamic_adar_repeated_overlap",
                "fnx",
                "fnx_raw_adamic_adar_repeated_overlap",
            ),
            (
                "raw_adamic_adar_repeated_overlap",
                "networkx",
                "networkx_adamic_adar_repeated_overlap",
            ),
            (
                "raw_resource_allocation_repeated_overlap",
                "fnx",
                "fnx_raw_resource_allocation_repeated_overlap",
            ),
            (
                "raw_resource_allocation_repeated_overlap",
                "networkx",
                "networkx_resource_allocation_repeated_overlap",
            ),
            (
                "raw_preferential_attachment_repeated_overlap",
                "fnx",
                "fnx_raw_preferential_attachment_repeated_overlap",
            ),
            (
                "raw_preferential_attachment_repeated_overlap",
                "networkx",
                "networkx_preferential_attachment_repeated_overlap",
            ),
            (
                "raw_cn_soundarajan_hopcroft_repeated_overlap",
                "fnx",
                "fnx_raw_cn_soundarajan_hopcroft_repeated_overlap",
            ),
            (
                "raw_cn_soundarajan_hopcroft_repeated_overlap",
                "networkx",
                "networkx_cn_soundarajan_hopcroft_repeated_overlap",
            ),
            (
                "raw_ra_index_soundarajan_hopcroft_repeated_overlap",
                "fnx",
                "fnx_raw_ra_index_soundarajan_hopcroft_repeated_overlap",
            ),
            (
                "raw_ra_index_soundarajan_hopcroft_repeated_overlap",
                "networkx",
                "networkx_ra_index_soundarajan_hopcroft_repeated_overlap",
            ),
            ("is_path_len50", "fnx", "fnx_is_path_len50"),
            ("is_path_len50", "networkx", "networkx_is_path_len50"),
            (
                "graph_get_edge_attributes_weight_4k",
                "fnx",
                "fnx_graph_get_edge_attributes_weight_4k",
            ),
            (
                "graph_get_edge_attributes_weight_4k",
                "networkx",
                "networkx_graph_get_edge_attributes_weight_4k",
            ),
            (
                "digraph_get_edge_attributes_weight_4k",
                "fnx",
                "fnx_digraph_get_edge_attributes_weight_4k",
            ),
            (
                "digraph_get_edge_attributes_weight_4k",
                "networkx",
                "networkx_digraph_get_edge_attributes_weight_4k",
            ),
            (
                "graph_duplicate_attr_add_edges_from",
                "fnx",
                "fnx_graph_duplicate_attr_add_edges_from",
            ),
            (
                "graph_duplicate_attr_add_edges_from",
                "networkx",
                "networkx_graph_duplicate_attr_add_edges_from",
            ),
            (
                "digraph_duplicate_attr_add_edges_from",
                "fnx",
                "fnx_digraph_duplicate_attr_add_edges_from",
            ),
            (
                "digraph_duplicate_attr_add_edges_from",
                "networkx",
                "networkx_digraph_duplicate_attr_add_edges_from",
            ),
            (
                "digraph_to_undirected_attr_heavy",
                "fnx",
                "fnx_digraph_to_undirected_attr_heavy",
            ),
            (
                "digraph_to_undirected_attr_heavy",
                "networkx",
                "networkx_digraph_to_undirected_attr_heavy",
            ),
            (
                "multidigraph_to_scipy_sparse_array_csr_int_weights",
                "fnx",
                "fnx_multidigraph_to_scipy_sparse_array_csr_int_weights",
            ),
            (
                "multidigraph_to_scipy_sparse_array_csr_int_weights",
                "networkx",
                "networkx_multidigraph_to_scipy_sparse_array_csr_int_weights",
            ),
        ] {
            let callable = helper
                .getattr(callable_name)
                .expect("benchmark helper should expose callable")
                .unbind();
            bench_py_callable(c, workload, engine, callable);
        }
    });
}

criterion_group!(benches, bench_public_api_gauntlet);
criterion_main!(benches);
