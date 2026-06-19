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

struct AssortativityWorkloads {
    fnx_degree_mixing: Py<PyAny>,
    fnx_raw_degree_mixing: Py<PyAny>,
    nx_degree_mixing: Py<PyAny>,
    fnx_node_degree_xy: Py<PyAny>,
    fnx_raw_node_degree_xy: Py<PyAny>,
    nx_node_degree_xy: Py<PyAny>,
    fnx_node_degree_xy_directed: Py<PyAny>,
    fnx_raw_node_degree_xy_directed: Py<PyAny>,
    nx_node_degree_xy_directed: Py<PyAny>,
    fnx_average_degree_connectivity: Py<PyAny>,
    fnx_raw_average_degree_connectivity: Py<PyAny>,
    nx_average_degree_connectivity: Py<PyAny>,
}

struct LinkPredictionWorkloads {
    fnx_common_neighbor_centrality: Py<PyAny>,
    nx_common_neighbor_centrality: Py<PyAny>,
}

struct MultiDiGraphConnectivityWorkloads {
    fnx_strongly_connected_components: Py<PyAny>,
    nx_strongly_connected_components: Py<PyAny>,
    fnx_descendants: Py<PyAny>,
    nx_descendants: Py<PyAny>,
}

fn prepare_cut_metric_workloads(py: Python<'_>) -> PyResult<CutMetricWorkloads> {
    let manifest_dir = Path::new(env!("CARGO_MANIFEST_DIR"));
    let repo_root = manifest_dir
        .parent()
        .and_then(Path::parent)
        .expect("fnx-python crate must live under crates/");
    let python_dir = repo_root.join("python");
    let legacy_dir = repo_root.join("legacy_networkx_code").join("networkx");

    let sys = py.import("sys")?;
    let path = sys.getattr("path")?;
    let path = path.cast::<PyList>()?;
    path.insert(0, repo_root.to_str().expect("repo path must be UTF-8"))?;
    path.insert(0, python_dir.to_str().expect("repo path must be UTF-8"))?;
    path.insert(0, legacy_dir.to_str().expect("repo path must be UTF-8"))?;

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
        let callable = locals.get_item(name)?.ok_or_else(|| {
            pyo3::exceptions::PyKeyError::new_err(format!("missing Python callable {name}"))
        })?;
        Ok(callable.unbind())
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

fn prepare_assortativity_workloads(py: Python<'_>) -> PyResult<AssortativityWorkloads> {
    let manifest_dir = Path::new(env!("CARGO_MANIFEST_DIR"));
    let repo_root = manifest_dir
        .parent()
        .and_then(Path::parent)
        .expect("fnx-python crate must live under crates/");
    let python_dir = repo_root.join("python");
    let legacy_dir = repo_root.join("legacy_networkx_code").join("networkx");

    let sys = py.import("sys")?;
    let path = sys.getattr("path")?;
    let path = path.cast::<PyList>()?;
    path.insert(0, repo_root.to_str().expect("repo path must be UTF-8"))?;
    path.insert(0, python_dir.to_str().expect("repo path must be UTF-8"))?;
    path.insert(0, legacy_dir.to_str().expect("repo path must be UTF-8"))?;

    let locals = PyDict::new(py);
    py.run(
        cstring(
            r#"
import networkx as nx
import franken_networkx as fnx
import franken_networkx._fnx as raw

def _paired_graph_from_edges(nodes, edges, directed=False):
    graph_type = nx.DiGraph if directed else nx.Graph
    fnx_type = fnx.DiGraph if directed else fnx.Graph
    g_nx = graph_type()
    g_fnx = fnx_type()
    g_nx.add_nodes_from(nodes)
    g_fnx.add_nodes_from(nodes)
    g_nx.add_edges_from(edges)
    g_fnx.add_edges_from(edges)
    return g_fnx, g_nx

def _degree_mixing_hubs(hubs, spokes_per_hub):
    nodes = []
    edges = []
    for hub in range(hubs):
        hub_node = f"h{hub}"
        nodes.append(hub_node)
        if hub > 0:
            edges.append((f"h{hub - 1}", hub_node))
        for spoke in range(spokes_per_hub):
            spoke_node = f"h{hub}_s{spoke}"
            nodes.append(spoke_node)
            edges.append((hub_node, spoke_node))
    return _paired_graph_from_edges(nodes, edges)

def _average_degree_connectivity_mix(hubs, spokes_per_hub, isolates):
    fnx_g, nx_g = _degree_mixing_hubs(hubs, spokes_per_hub)
    for hub in range(min(hubs, 32)):
        hub_node = f"h{hub}"
        fnx_g.add_edge(hub_node, hub_node)
        nx_g.add_edge(hub_node, hub_node)
    isolate_nodes = [f"iso{i}" for i in range(isolates)]
    fnx_g.add_nodes_from(isolate_nodes)
    nx_g.add_nodes_from(isolate_nodes)
    return fnx_g, nx_g

def _directed_degree_xy_fan(layers, fanout):
    nodes = []
    edges = []
    for layer in range(layers):
        source = f"s{layer}"
        sink = f"t{layer}"
        nodes.extend([source, sink])
        for spoke in range(fanout):
            mid = f"m{layer}_{spoke}"
            nodes.append(mid)
            edges.append((source, mid))
            edges.append((mid, sink))
        if layer > 0:
            edges.append((f"t{layer - 1}", source))
    return _paired_graph_from_edges(nodes, edges, directed=True)

dm_fnx, dm_nx = _degree_mixing_hubs(512, 32)
adc_fnx, adc_nx = _average_degree_connectivity_mix(512, 32, 256)
xy_fnx, xy_nx = _degree_mixing_hubs(512, 32)
xy_dir_fnx, xy_dir_nx = _directed_degree_xy_fan(512, 32)

def _raw_mixing_to_nested(flat):
    result = {}
    for (left, right), count in flat.items():
        inner = result.setdefault(left, {})
        inner[right] = count
    return result

fnx_degree_mixing = lambda: fnx.degree_mixing_dict(dm_fnx)
fnx_raw_degree_mixing = lambda: _raw_mixing_to_nested(raw.degree_mixing_dict_rust(dm_fnx))
nx_degree_mixing = lambda: nx.degree_mixing_dict(dm_nx)
fnx_node_degree_xy = lambda: list(fnx.node_degree_xy(xy_fnx))
fnx_raw_node_degree_xy = lambda: list(raw.node_degree_xy_rust(xy_fnx))
nx_node_degree_xy = lambda: list(nx.node_degree_xy(xy_nx))
fnx_node_degree_xy_directed = lambda: list(fnx.node_degree_xy(xy_dir_fnx, x="out", y="in"))
fnx_raw_node_degree_xy_directed = lambda: list(raw.node_degree_xy_rust(xy_dir_fnx, x="out", y="in"))
nx_node_degree_xy_directed = lambda: list(nx.node_degree_xy(xy_dir_nx, x="out", y="in"))
fnx_average_degree_connectivity = lambda: fnx.average_degree_connectivity(adc_fnx)
fnx_raw_average_degree_connectivity = lambda: raw.average_degree_connectivity(adc_fnx)
nx_average_degree_connectivity = lambda: nx.average_degree_connectivity(adc_nx)

assert fnx_degree_mixing() == nx_degree_mixing()
assert fnx_raw_degree_mixing() == nx_degree_mixing()
assert fnx_node_degree_xy() == nx_node_degree_xy()
assert fnx_node_degree_xy_directed() == nx_node_degree_xy_directed()
assert fnx_average_degree_connectivity() == nx_average_degree_connectivity()
assert fnx_raw_average_degree_connectivity() == nx_average_degree_connectivity()
"#,
        )
        .as_c_str(),
        Some(&locals),
        Some(&locals),
    )?;

    let callable = |name: &str| -> PyResult<Py<PyAny>> {
        let callable = locals.get_item(name)?.ok_or_else(|| {
            pyo3::exceptions::PyKeyError::new_err(format!("missing Python callable {name}"))
        })?;
        Ok(callable.unbind())
    };

    Ok(AssortativityWorkloads {
        fnx_degree_mixing: callable("fnx_degree_mixing")?,
        fnx_raw_degree_mixing: callable("fnx_raw_degree_mixing")?,
        nx_degree_mixing: callable("nx_degree_mixing")?,
        fnx_node_degree_xy: callable("fnx_node_degree_xy")?,
        fnx_raw_node_degree_xy: callable("fnx_raw_node_degree_xy")?,
        nx_node_degree_xy: callable("nx_node_degree_xy")?,
        fnx_node_degree_xy_directed: callable("fnx_node_degree_xy_directed")?,
        fnx_raw_node_degree_xy_directed: callable("fnx_raw_node_degree_xy_directed")?,
        nx_node_degree_xy_directed: callable("nx_node_degree_xy_directed")?,
        fnx_average_degree_connectivity: callable("fnx_average_degree_connectivity")?,
        fnx_raw_average_degree_connectivity: callable("fnx_raw_average_degree_connectivity")?,
        nx_average_degree_connectivity: callable("nx_average_degree_connectivity")?,
    })
}

fn prepare_link_prediction_workloads(py: Python<'_>) -> PyResult<LinkPredictionWorkloads> {
    let manifest_dir = Path::new(env!("CARGO_MANIFEST_DIR"));
    let repo_root = manifest_dir
        .parent()
        .and_then(Path::parent)
        .expect("fnx-python crate must live under crates/");
    let python_dir = repo_root.join("python");
    let legacy_dir = repo_root.join("legacy_networkx_code").join("networkx");

    let sys = py.import("sys")?;
    let path = sys.getattr("path")?;
    let path = path.cast::<PyList>()?;
    path.insert(0, repo_root.to_str().expect("repo path must be UTF-8"))?;
    path.insert(0, python_dir.to_str().expect("repo path must be UTF-8"))?;
    path.insert(0, legacy_dir.to_str().expect("repo path must be UTF-8"))?;

    let locals = PyDict::new(py);
    py.run(
        cstring(
            r#"
import math
import random
import sys

for _name in list(sys.modules):
    if _name == "networkx" or _name.startswith("networkx."):
        del sys.modules[_name]

import networkx as nx
import franken_networkx as fnx

if "legacy_networkx_code" not in getattr(nx, "__file__", ""):
    raise AssertionError(f"expected vendored NetworkX oracle, got {nx.__file__!r}")

def _sparse_edges(node_count, probability, seed):
    rng = random.Random(seed)
    for u in range(node_count):
        for v in range(u + 1, node_count):
            if rng.random() < probability:
                yield (u, v)

def _paired_sparse_graph(node_count, probability, seed):
    edges = list(_sparse_edges(node_count, probability, seed))
    fnx_graph = fnx.Graph()
    nx_graph = nx.Graph()
    fnx_graph.add_nodes_from(range(node_count))
    nx_graph.add_nodes_from(range(node_count))
    fnx_graph.add_edges_from(edges)
    nx_graph.add_edges_from(edges)
    return fnx_graph, nx_graph

def _sample_non_edges(nx_graph, count, seed):
    nodes = list(nx_graph)
    pairs = []
    for left_pos, u in enumerate(nodes):
        for v in nodes[left_pos + 1:]:
            if not nx_graph.has_edge(u, v):
                pairs.append((u, v))
    rng = random.Random(seed)
    rng.shuffle(pairs)
    return pairs[:count]

def _consume_scores(scores):
    total = 0.0
    count = 0
    for u, v, score in scores:
        count += 1
        total += (count * 0.000001) + (int(u) * 0.0000001) + (int(v) * 0.00000001) + float(score)
    return total

ccpa_fnx_graph, ccpa_nx_graph = _paired_sparse_graph(600, 0.03, 9140)
ccpa_ebunch = _sample_non_edges(ccpa_nx_graph, 2000, 914001)

_fnx_ccpa = list(fnx.common_neighbor_centrality(ccpa_fnx_graph, ccpa_ebunch, alpha=0.8))
_nx_ccpa = list(nx.common_neighbor_centrality(ccpa_nx_graph, ccpa_ebunch, alpha=0.8))
assert len(_fnx_ccpa) == len(_nx_ccpa)
for (fu, fv, fs), (nu, nv, ns) in zip(_fnx_ccpa, _nx_ccpa):
    assert (fu, fv) == (nu, nv)
    assert math.isclose(fs, ns, rel_tol=0.0, abs_tol=1e-12)

fnx_common_neighbor_centrality = lambda: _consume_scores(
    fnx.common_neighbor_centrality(ccpa_fnx_graph, ccpa_ebunch, alpha=0.8)
)
nx_common_neighbor_centrality = lambda: _consume_scores(
    nx.common_neighbor_centrality(ccpa_nx_graph, ccpa_ebunch, alpha=0.8)
)
"#,
        )
        .as_c_str(),
        Some(&locals),
        Some(&locals),
    )?;

    let callable = |name: &str| -> PyResult<Py<PyAny>> {
        let callable = locals.get_item(name)?.ok_or_else(|| {
            pyo3::exceptions::PyKeyError::new_err(format!("missing Python callable {name}"))
        })?;
        Ok(callable.unbind())
    };

    Ok(LinkPredictionWorkloads {
        fnx_common_neighbor_centrality: callable("fnx_common_neighbor_centrality")?,
        nx_common_neighbor_centrality: callable("nx_common_neighbor_centrality")?,
    })
}

fn prepare_multidigraph_connectivity_workloads(
    py: Python<'_>,
) -> PyResult<MultiDiGraphConnectivityWorkloads> {
    let manifest_dir = Path::new(env!("CARGO_MANIFEST_DIR"));
    let repo_root = manifest_dir
        .parent()
        .and_then(Path::parent)
        .expect("fnx-python crate must live under crates/");
    let python_dir = repo_root.join("python");
    let legacy_dir = repo_root.join("legacy_networkx_code").join("networkx");

    let sys = py.import("sys")?;
    let path = sys.getattr("path")?;
    let path = path.cast::<PyList>()?;
    path.insert(0, repo_root.to_str().expect("repo path must be UTF-8"))?;
    path.insert(0, python_dir.to_str().expect("repo path must be UTF-8"))?;
    path.insert(0, legacy_dir.to_str().expect("repo path must be UTF-8"))?;

    let locals = PyDict::new(py);
    py.run(
        cstring(
            r#"
import sys

for _name in list(sys.modules):
    if _name == "networkx" or _name.startswith("networkx."):
        del sys.modules[_name]

import networkx as nx
import franken_networkx as fnx

if "legacy_networkx_code" not in getattr(nx, "__file__", ""):
    raise AssertionError(f"expected vendored NetworkX oracle, got {nx.__file__!r}")

def _paired_multidigraph_scc_workload(node_count, block_size):
    fnx_graph = fnx.MultiDiGraph()
    nx_graph = nx.MultiDiGraph()
    nodes = list(range(node_count))
    fnx_graph.add_nodes_from(nodes)
    nx_graph.add_nodes_from(nodes)
    for block_start in range(0, node_count, block_size):
        block = nodes[block_start:block_start + block_size]
        if not block:
            continue
        for offset, u in enumerate(block):
            v = block[(offset + 1) % len(block)]
            fnx_graph.add_edge(u, v)
            fnx_graph.add_edge(u, v)
            nx_graph.add_edge(u, v)
            nx_graph.add_edge(u, v)
            if offset % 3 == 0:
                fnx_graph.add_edge(u, u)
                nx_graph.add_edge(u, u)
        next_block = block_start + block_size
        if next_block < node_count:
            fnx_graph.add_edge(block[-1], next_block)
            fnx_graph.add_edge(block[-1], next_block)
            nx_graph.add_edge(block[-1], next_block)
            nx_graph.add_edge(block[-1], next_block)
    return fnx_graph, nx_graph

def _component_checksum(components):
    total = 0
    for idx, component in enumerate(components):
        subtotal = 0
        for node in component:
            subtotal += int(node) + 1
        total += (idx + 1) * subtotal + len(component) * 17
    return total

def _node_set_checksum(nodes):
    total = 0
    for idx, node in enumerate(sorted(nodes)):
        total += (idx + 1) * (int(node) + 1)
    return total + len(nodes) * 17

mdg_fnx, mdg_nx = _paired_multidigraph_scc_workload(1800, 6)
_fnx_scc = list(fnx.strongly_connected_components(mdg_fnx))
_nx_scc = list(nx.strongly_connected_components(mdg_nx))
assert [set(c) for c in _fnx_scc] == [set(c) for c in _nx_scc]
assert _component_checksum(_fnx_scc) == _component_checksum(_nx_scc)
assert fnx.descendants(mdg_fnx, 0) == nx.descendants(mdg_nx, 0)

fnx_strongly_connected_components = lambda: _component_checksum(
    fnx.strongly_connected_components(mdg_fnx)
)
nx_strongly_connected_components = lambda: _component_checksum(
    nx.strongly_connected_components(mdg_nx)
)
fnx_descendants = lambda: _node_set_checksum(fnx.descendants(mdg_fnx, 0))
nx_descendants = lambda: _node_set_checksum(nx.descendants(mdg_nx, 0))
"#,
        )
        .as_c_str(),
        Some(&locals),
        Some(&locals),
    )?;

    let callable = |name: &str| -> PyResult<Py<PyAny>> {
        let callable = locals.get_item(name)?.ok_or_else(|| {
            pyo3::exceptions::PyKeyError::new_err(format!("missing Python callable {name}"))
        })?;
        Ok(callable.unbind())
    };

    Ok(MultiDiGraphConnectivityWorkloads {
        fnx_strongly_connected_components: callable("fnx_strongly_connected_components")?,
        nx_strongly_connected_components: callable("nx_strongly_connected_components")?,
        fnx_descendants: callable("fnx_descendants")?,
        nx_descendants: callable("nx_descendants")?,
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

fn assortativity_head_to_head(c: &mut Criterion) {
    Python::initialize();
    let workloads = Python::attach(prepare_assortativity_workloads)
        .expect("failed to prepare assortativity Python workloads");
    let mut group = c.benchmark_group("networkx_head_to_head_assortativity");
    group.sample_size(20);

    bench_python_callable(
        &mut group,
        "fnx_degree_mixing_dict_h512_s32",
        &workloads.fnx_degree_mixing,
    );
    bench_python_callable(
        &mut group,
        "nx_degree_mixing_dict_h512_s32",
        &workloads.nx_degree_mixing,
    );
    bench_python_callable(
        &mut group,
        "fnx_node_degree_xy_h512_s32",
        &workloads.fnx_node_degree_xy,
    );
    bench_python_callable(
        &mut group,
        "nx_node_degree_xy_h512_s32",
        &workloads.nx_node_degree_xy,
    );
    bench_python_callable(
        &mut group,
        "fnx_node_degree_xy_directed_l512_f32",
        &workloads.fnx_node_degree_xy_directed,
    );
    bench_python_callable(
        &mut group,
        "nx_node_degree_xy_directed_l512_f32",
        &workloads.nx_node_degree_xy_directed,
    );
    bench_python_callable(
        &mut group,
        "fnx_average_degree_connectivity_h512_s32_i256",
        &workloads.fnx_average_degree_connectivity,
    );
    bench_python_callable(
        &mut group,
        "nx_average_degree_connectivity_h512_s32_i256",
        &workloads.nx_average_degree_connectivity,
    );

    group.finish();
}

fn assortativity_raw_head_to_head(c: &mut Criterion) {
    Python::initialize();
    let workloads = Python::attach(prepare_assortativity_workloads)
        .expect("failed to prepare raw assortativity Python workloads");
    let mut group = c.benchmark_group("networkx_head_to_head_assortativity_raw");
    group.sample_size(20);

    bench_python_callable(
        &mut group,
        "fnx_raw_degree_mixing_dict_h512_s32",
        &workloads.fnx_raw_degree_mixing,
    );
    bench_python_callable(
        &mut group,
        "nx_degree_mixing_dict_h512_s32",
        &workloads.nx_degree_mixing,
    );
    bench_python_callable(
        &mut group,
        "fnx_raw_node_degree_xy_h512_s32",
        &workloads.fnx_raw_node_degree_xy,
    );
    bench_python_callable(
        &mut group,
        "nx_node_degree_xy_h512_s32",
        &workloads.nx_node_degree_xy,
    );
    bench_python_callable(
        &mut group,
        "fnx_raw_node_degree_xy_directed_l512_f32",
        &workloads.fnx_raw_node_degree_xy_directed,
    );
    bench_python_callable(
        &mut group,
        "nx_node_degree_xy_directed_l512_f32",
        &workloads.nx_node_degree_xy_directed,
    );
    bench_python_callable(
        &mut group,
        "fnx_raw_average_degree_connectivity_h512_s32_i256",
        &workloads.fnx_raw_average_degree_connectivity,
    );
    bench_python_callable(
        &mut group,
        "nx_average_degree_connectivity_h512_s32_i256",
        &workloads.nx_average_degree_connectivity,
    );

    group.finish();
}

fn link_prediction_head_to_head(c: &mut Criterion) {
    Python::initialize();
    let workloads = Python::attach(prepare_link_prediction_workloads)
        .expect("failed to prepare link-prediction Python workloads");
    let mut group = c.benchmark_group("networkx_head_to_head_link_prediction");
    group.sample_size(20);

    bench_python_callable(
        &mut group,
        "fnx_common_neighbor_centrality_g600_p003_e2000",
        &workloads.fnx_common_neighbor_centrality,
    );
    bench_python_callable(
        &mut group,
        "nx_common_neighbor_centrality_g600_p003_e2000",
        &workloads.nx_common_neighbor_centrality,
    );

    group.finish();
}

fn multidigraph_connectivity_head_to_head(c: &mut Criterion) {
    Python::initialize();
    let workloads = Python::attach(prepare_multidigraph_connectivity_workloads)
        .expect("failed to prepare MultiDiGraph connectivity Python workloads");
    let mut group = c.benchmark_group("networkx_head_to_head_multidigraph_connectivity");
    group.sample_size(20);

    bench_python_callable(
        &mut group,
        "fnx_strongly_connected_components_mdg1800_b6",
        &workloads.fnx_strongly_connected_components,
    );
    bench_python_callable(
        &mut group,
        "nx_strongly_connected_components_mdg1800_b6",
        &workloads.nx_strongly_connected_components,
    );
    bench_python_callable(
        &mut group,
        "fnx_descendants_mdg1800_b6_source0",
        &workloads.fnx_descendants,
    );
    bench_python_callable(
        &mut group,
        "nx_descendants_mdg1800_b6_source0",
        &workloads.nx_descendants,
    );

    group.finish();
}

criterion_group!(
    benches,
    cut_metric_head_to_head,
    assortativity_head_to_head,
    assortativity_raw_head_to_head,
    link_prediction_head_to_head,
    multidigraph_connectivity_head_to_head
);
criterion_main!(benches);
