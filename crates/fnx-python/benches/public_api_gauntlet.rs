#![forbid(unsafe_code)]

use criterion::{BenchmarkId, Criterion, criterion_group, criterion_main};
use pyo3::types::PyAnyMethods;
use pyo3::{Py, PyAny, Python};

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
            "import glob, importlib.util, os, sys
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
target_dir = os.environ.get('CARGO_TARGET_DIR')
if target_dir:
    candidates = [
        os.path.join(target_dir, 'release', 'lib_fnx.so'),
        *glob.glob(os.path.join(target_dir, 'release', 'deps', 'lib_fnx*.so')),
    ]
    for path in candidates:
        if os.path.exists(path):
            spec = importlib.util.spec_from_file_location('franken_networkx._fnx', path)
            module = importlib.util.module_from_spec(spec)
            sys.modules['franken_networkx._fnx'] = module
            spec.loader.exec_module(module)
            break"
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
        for (workload, engine, callable_name) in [
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
