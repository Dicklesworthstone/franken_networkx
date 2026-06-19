//! Python-facing Criterion benches against upstream NetworkX.
//!
//! These benches exercise the public `franken_networkx` Python wrappers, not just
//! raw Rust helpers. The Python setup builds identical NetworkX/FNX graphs once;
//! Criterion times only repeated algorithm calls.

use criterion::{Criterion, criterion_group, criterion_main};
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};
use std::ffi::CString;
use std::path::Path;
use std::time::Instant;

fn cstring(source: &str) -> CString {
    CString::new(source).expect("Python snippets must not contain NUL bytes")
}

struct CutMetricWorkloads {
    fnx_edge_ba: Py<PyAny>,
    nx_edge_ba: Py<PyAny>,
    fnx_edge_ws: Py<PyAny>,
    nx_edge_ws: Py<PyAny>,
    fnx_node_ba: Py<PyAny>,
    nx_node_ba: Py<PyAny>,
    fnx_node_ws: Py<PyAny>,
    nx_node_ws: Py<PyAny>,
}

fn prepare_cut_metric_workloads(py: Python<'_>) -> PyResult<CutMetricWorkloads> {
    let manifest_dir = Path::new(env!("CARGO_MANIFEST_DIR"));
    let repo_root = manifest_dir
        .parent()
        .and_then(Path::parent)
        .expect("fnx-python crate must live under crates/");
    let python_dir = repo_root.join("python");

    let sys = py.import("sys")?;
    let path = sys.getattr("path")?;
    let path = path.cast::<PyList>()?;
    path.insert(0, python_dir.to_str().expect("repo path must be UTF-8"))?;
    path.insert(0, repo_root.to_str().expect("repo path must be UTF-8"))?;

    let locals = PyDict::new(py);
    py.run(
        cstring(
            r#"
import networkx as nx
import franken_networkx as fnx

def _paired_graphs(kind, n, m_or_k, p=0.0, seed=1):
    if kind == "ba":
        base = nx.barabasi_albert_graph(n, m_or_k, seed=seed)
    elif kind == "ws":
        base = nx.watts_strogatz_graph(n, m_or_k, p, seed=seed)
    else:
        raise AssertionError(kind)
    nodes = list(base.nodes())
    edges = list(base.edges())
    g_nx = nx.Graph()
    g_nx.add_nodes_from(nodes)
    g_nx.add_edges_from(edges)
    g_fnx = fnx.Graph()
    g_fnx.add_nodes_from(nodes)
    g_fnx.add_edges_from(edges)
    return g_fnx, g_nx

ba_fnx, ba_nx = _paired_graphs("ba", 2500, 3, seed=11)
ws_fnx, ws_nx = _paired_graphs("ws", 2500, 8, p=0.05, seed=17)

ba_cut = list(range(0, 1250))
ws_cut = list(range(0, 2500, 4))

fnx_edge_ba = lambda: fnx.edge_expansion(ba_fnx, ba_cut)
nx_edge_ba = lambda: nx.edge_expansion(ba_nx, ba_cut)
fnx_edge_ws = lambda: fnx.edge_expansion(ws_fnx, ws_cut)
nx_edge_ws = lambda: nx.edge_expansion(ws_nx, ws_cut)
fnx_node_ba = lambda: fnx.node_expansion(ba_fnx, ba_cut)
nx_node_ba = lambda: nx.node_expansion(ba_nx, ba_cut)
fnx_node_ws = lambda: fnx.node_expansion(ws_fnx, ws_cut)
nx_node_ws = lambda: nx.node_expansion(ws_nx, ws_cut)

assert fnx_edge_ba() == nx_edge_ba()
assert fnx_edge_ws() == nx_edge_ws()
assert fnx_node_ba() == nx_node_ba()
assert fnx_node_ws() == nx_node_ws()
"#,
        )
        .as_c_str(),
        Some(&locals),
        Some(&locals),
    )?;

    let callable = |name: &str| -> PyResult<Py<PyAny>> {
        Ok(locals
            .get_item(name)?
            .unwrap_or_else(|| panic!("missing Python callable {name}"))
            .unbind())
    };

    Ok(CutMetricWorkloads {
        fnx_edge_ba: callable("fnx_edge_ba")?,
        nx_edge_ba: callable("nx_edge_ba")?,
        fnx_edge_ws: callable("fnx_edge_ws")?,
        nx_edge_ws: callable("nx_edge_ws")?,
        fnx_node_ba: callable("fnx_node_ba")?,
        nx_node_ba: callable("nx_node_ba")?,
        fnx_node_ws: callable("fnx_node_ws")?,
        nx_node_ws: callable("nx_node_ws")?,
    })
}

fn bench_python_callable(
    group: &mut criterion::BenchmarkGroup<'_, criterion::measurement::WallTime>,
    name: &str,
    callable: &Py<PyAny>,
) {
    group.bench_function(name, |b| {
        b.iter_custom(|iters| {
            Python::attach(|py| {
                let callable = callable.bind(py);
                let start = Instant::now();
                for _ in 0..iters {
                    callable.call0().expect("Python benchmark callable failed");
                }
                start.elapsed()
            })
        });
    });
}

fn cut_metric_head_to_head(c: &mut Criterion) {
    Python::initialize();
    let workloads =
        Python::attach(prepare_cut_metric_workloads).expect("failed to prepare Python workloads");
    let mut group = c.benchmark_group("networkx_head_to_head_cut_metrics");
    group.sample_size(20);

    bench_python_callable(
        &mut group,
        "fnx_edge_expansion_ba2500_s1250",
        &workloads.fnx_edge_ba,
    );
    bench_python_callable(
        &mut group,
        "nx_edge_expansion_ba2500_s1250",
        &workloads.nx_edge_ba,
    );
    bench_python_callable(
        &mut group,
        "fnx_edge_expansion_ws2500_s625",
        &workloads.fnx_edge_ws,
    );
    bench_python_callable(
        &mut group,
        "nx_edge_expansion_ws2500_s625",
        &workloads.nx_edge_ws,
    );
    bench_python_callable(
        &mut group,
        "fnx_node_expansion_ba2500_s1250",
        &workloads.fnx_node_ba,
    );
    bench_python_callable(
        &mut group,
        "nx_node_expansion_ba2500_s1250",
        &workloads.nx_node_ba,
    );
    bench_python_callable(
        &mut group,
        "fnx_node_expansion_ws2500_s625",
        &workloads.fnx_node_ws,
    );
    bench_python_callable(
        &mut group,
        "nx_node_expansion_ws2500_s625",
        &workloads.nx_node_ws,
    );

    group.finish();
}

criterion_group!(benches, cut_metric_head_to_head);
criterion_main!(benches);
