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
use std::time::{Duration, Instant};

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
    fnx_cut_overlap_ba: Py<PyAny>,
    nx_cut_overlap_ba: Py<PyAny>,
    fnx_normalized_cut_overlap_ba: Py<PyAny>,
    nx_normalized_cut_overlap_ba: Py<PyAny>,
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

struct MultiDiGraphWeightedDegreeWorkloads {
    fnx_in_degree_weight: Py<PyAny>,
    nx_in_degree_weight: Py<PyAny>,
    fnx_out_degree_weight: Py<PyAny>,
    nx_out_degree_weight: Py<PyAny>,
}

struct MultiGraphBiconnectedWorkloads {
    fnx_is_biconnected: Py<PyAny>,
    nx_is_biconnected: Py<PyAny>,
    fnx_articulation_points: Py<PyAny>,
    nx_articulation_points: Py<PyAny>,
    fnx_biconnected_components: Py<PyAny>,
    nx_biconnected_components: Py<PyAny>,
    fnx_bfs_edges: Py<PyAny>,
    nx_bfs_edges: Py<PyAny>,
    fnx_minimum_spanning_tree: Py<PyAny>,
    nx_minimum_spanning_tree: Py<PyAny>,
}

struct MultiGraphWeightedDegreeWorkloads {
    fnx_degree_nbunch_weight: Py<PyAny>,
    nx_degree_nbunch_weight: Py<PyAny>,
    fnx_size_weight_degree_formula: Py<PyAny>,
    fnx_size_weight: Py<PyAny>,
    nx_size_weight: Py<PyAny>,
}

struct TreeSubmoduleWorkloads {
    fnx_minimum_spanning_tree: Py<PyAny>,
    nx_minimum_spanning_tree: Py<PyAny>,
}

struct LatticeGeneratorWorkloads {
    fnx_triangular: Py<PyAny>,
    nx_triangular: Py<PyAny>,
    fnx_hexagonal: Py<PyAny>,
    nx_hexagonal: Py<PyAny>,
}

struct AdjacencyOuterCacheWorkloads {
    fnx_graph_2000: Py<PyAny>,
    nx_graph_2000: Py<PyAny>,
    fnx_graph_8000: Py<PyAny>,
    nx_graph_8000: Py<PyAny>,
    fnx_digraph_2000: Py<PyAny>,
    nx_digraph_2000: Py<PyAny>,
    fnx_digraph_8000: Py<PyAny>,
    nx_digraph_8000: Py<PyAny>,
}

struct CoreLaggardWorkloads {
    fnx_mdg_in_degree_weight: Py<PyAny>,
    nx_mdg_in_degree_weight: Py<PyAny>,
    fnx_mg_selfloop_keys_weight: Py<PyAny>,
    nx_mg_selfloop_keys_weight: Py<PyAny>,
    fnx_mdg_edges_keys: Py<PyAny>,
    nx_mdg_edges_keys: Py<PyAny>,
    fnx_mdg_in_edges_data: Py<PyAny>,
    nx_mdg_in_edges_data: Py<PyAny>,
    fnx_mdg_out_edges_nbunch_keys_data: Py<PyAny>,
    nx_mdg_out_edges_nbunch_keys_data: Py<PyAny>,
    fnx_mdg_out_edges_nbunch_keys_weight: Py<PyAny>,
    nx_mdg_out_edges_nbunch_keys_weight: Py<PyAny>,
}

struct TspWorkloads {
    fnx_greedy_tsp: Py<PyAny>,
    nx_greedy_tsp: Py<PyAny>,
    fnx_sa_tsp: Py<PyAny>,
    nx_sa_tsp: Py<PyAny>,
    fnx_ta_tsp: Py<PyAny>,
    nx_ta_tsp: Py<PyAny>,
}

struct VoronoiWorkloads {
    fnx_voronoi: Py<PyAny>,
    nx_voronoi: Py<PyAny>,
}

struct ConstructionCopyWorkloads {
    fnx_graph_to_directed_scalar_attrs: Py<PyAny>,
    nx_graph_to_directed_scalar_attrs: Py<PyAny>,
    fnx_graph_iterator_tuples: Py<PyAny>,
    nx_graph_iterator_tuples: Py<PyAny>,
    fnx_graph_iterator_lists_normalized: Py<PyAny>,
    fnx_graph_iterator_lists: Py<PyAny>,
    nx_graph_iterator_lists: Py<PyAny>,
    fnx_digraph_iterator_lists: Py<PyAny>,
    nx_digraph_iterator_lists: Py<PyAny>,
    fnx_multigraph_iterator_lists: Py<PyAny>,
    nx_multigraph_iterator_lists: Py<PyAny>,
    fnx_multidigraph_iterator_lists: Py<PyAny>,
    nx_multidigraph_iterator_lists: Py<PyAny>,
    fnx_multidigraph_iterator_keyed: Py<PyAny>,
    nx_multidigraph_iterator_keyed: Py<PyAny>,
}

struct ClearEdgesWorkloads {
    fnx_multigraph_factory: Py<PyAny>,
    nx_multigraph_factory: Py<PyAny>,
}

struct StickyEdgeDirtyWorkloads {
    fnx_dijkstra_path: Py<PyAny>,
    nx_dijkstra_path: Py<PyAny>,
}

fn prepare_sticky_edge_dirty_workloads(py: Python<'_>) -> PyResult<StickyEdgeDirtyWorkloads> {
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
import glob
import importlib.util
import os
import sys

target_dir = os.environ.get("CARGO_TARGET_DIR")
if target_dir and "franken_networkx._fnx" not in sys.modules:
    candidates = [
        os.path.join(target_dir, "release", "lib_fnx.so"),
        *glob.glob(os.path.join(target_dir, "release", "deps", "lib_fnx*.so")),
    ]
    for path in candidates:
        if os.path.exists(path):
            spec = importlib.util.spec_from_file_location("franken_networkx._fnx", path)
            module = importlib.util.module_from_spec(spec)
            sys.modules["franken_networkx._fnx"] = module
            spec.loader.exec_module(module)
            break

for _name in list(sys.modules):
    if _name == "networkx" or _name.startswith("networkx."):
        del sys.modules[_name]

import networkx as nx
import franken_networkx as fnx

if "legacy_networkx_code" not in getattr(nx, "__file__", ""):
    raise AssertionError(f"expected vendored NetworkX oracle, got {nx.__file__!r}")

def _paired_weighted_ba_graph(node_count, attach_count, seed):
    base = nx.barabasi_albert_graph(node_count, attach_count, seed=seed)
    fnx_graph = fnx.Graph()
    nx_graph = nx.Graph()
    fnx_graph.add_nodes_from(base.nodes())
    nx_graph.add_nodes_from(base.nodes())
    for index, (u, v) in enumerate(base.edges()):
        weight = (u * 13 + v * 17 + index * 19) % 97 + 1
        fnx_graph.add_edge(u, v, weight=weight)
        nx_graph.add_edge(u, v, weight=weight)
    return fnx_graph, nx_graph

sticky_fnx, sticky_nx = _paired_weighted_ba_graph(2000, 3, 9142)
sticky_source = 0
sticky_target = 1900

# Expose live edge-attribute dicts before the timed native reads. In fnx this
# sets the sticky edge-dirty flag; NetworkX keeps the same live dict contract.
assert list(sticky_fnx.edges(data=True)) == list(sticky_nx.edges(data=True))

_fnx_path = fnx.dijkstra_path(sticky_fnx, sticky_source, sticky_target, weight="weight")
_nx_path = nx.dijkstra_path(sticky_nx, sticky_source, sticky_target, weight="weight")
assert _fnx_path == _nx_path

fnx_dijkstra_path = lambda: len(fnx.dijkstra_path(sticky_fnx, sticky_source, sticky_target, weight="weight"))
nx_dijkstra_path = lambda: len(nx.dijkstra_path(sticky_nx, sticky_source, sticky_target, weight="weight"))
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

    Ok(StickyEdgeDirtyWorkloads {
        fnx_dijkstra_path: callable("fnx_dijkstra_path")?,
        nx_dijkstra_path: callable("nx_dijkstra_path")?,
    })
}

fn prepare_clear_edges_workloads(py: Python<'_>) -> PyResult<ClearEdgesWorkloads> {
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
import glob
import importlib.util
import os
import sys

target_dir = os.environ.get("CARGO_TARGET_DIR")
if target_dir and "franken_networkx._fnx" not in sys.modules:
    candidates = [
        os.path.join(target_dir, "release", "lib_fnx.so"),
        *glob.glob(os.path.join(target_dir, "release", "deps", "lib_fnx*.so")),
    ]
    for path in candidates:
        if os.path.exists(path):
            spec = importlib.util.spec_from_file_location("franken_networkx._fnx", path)
            module = importlib.util.module_from_spec(spec)
            sys.modules["franken_networkx._fnx"] = module
            spec.loader.exec_module(module)
            break

for _name in list(sys.modules):
    if _name == "networkx" or _name.startswith("networkx."):
        del sys.modules[_name]

import networkx as nx
import franken_networkx as fnx

if "legacy_networkx_code" not in getattr(nx, "__file__", ""):
    raise AssertionError(f"expected vendored NetworkX oracle, got {nx.__file__!r}")

def _make_multigraph(module):
    graph = module.MultiGraph()
    for node in range(800):
        graph.add_node(node, label=f"n{node}", group=node % 17)
    for i in range(4000):
        u = (i * 37) % 800
        v = (i * 91 + 17) % 800
        if v == u:
            v = (v + 19) % 800
        graph.add_edge(u, v, key=f"k{i}", weight=(i * 13) % 41 - 9, tag=f"e{i % 23}")
    return graph

fnx_probe = _make_multigraph(fnx)
nx_probe = _make_multigraph(nx)
fnx_probe.clear_edges()
nx_probe.clear_edges()
assert fnx_probe.number_of_edges() == nx_probe.number_of_edges() == 0
assert list(fnx_probe.nodes(data=True)) == list(nx_probe.nodes(data=True))

fnx_multigraph_factory = lambda: _make_multigraph(fnx)
nx_multigraph_factory = lambda: _make_multigraph(nx)
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

    Ok(ClearEdgesWorkloads {
        fnx_multigraph_factory: callable("fnx_multigraph_factory")?,
        nx_multigraph_factory: callable("nx_multigraph_factory")?,
    })
}

fn prepare_construction_copy_workloads(py: Python<'_>) -> PyResult<ConstructionCopyWorkloads> {
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
import glob
import importlib.util
import os
import sys

target_dir = os.environ.get("CARGO_TARGET_DIR")
if target_dir and "franken_networkx._fnx" not in sys.modules:
    candidates = [
        os.path.join(target_dir, "release", "lib_fnx.so"),
        *glob.glob(os.path.join(target_dir, "release", "deps", "lib_fnx*.so")),
    ]
    for path in candidates:
        if os.path.exists(path):
            spec = importlib.util.spec_from_file_location("franken_networkx._fnx", path)
            module = importlib.util.module_from_spec(spec)
            sys.modules["franken_networkx._fnx"] = module
            spec.loader.exec_module(module)
            break

for _name in list(sys.modules):
    if _name == "networkx" or _name.startswith("networkx."):
        del sys.modules[_name]

import networkx as nx
import franken_networkx as fnx

if "legacy_networkx_code" not in getattr(nx, "__file__", ""):
    raise AssertionError(f"expected vendored NetworkX oracle, got {nx.__file__!r}")

def _paired_scalar_attr_graph(node_count):
    fnx_graph = fnx.Graph()
    nx_graph = nx.Graph()
    for node in range(node_count):
        attrs = {
            "i": node,
            "f": node / 17.0,
            "s": f"n{node}",
            "b": (node & 1) == 0,
            "nested": {"bucket": node % 31},
        }
        fnx_graph.add_node(node, **attrs)
        nx_graph.add_node(node, **attrs)
    for u in range(node_count):
        for step in range(1, 9):
            v = (u * 37 + step * 19) % node_count
            if v == u:
                v = (v + step + 1) % node_count
            attrs = {
                "weight": (u * 11 + v * 7 + step) % 97,
                "cost": (u + v + step) / 13.0,
                "tag": f"e{step}",
                "flag": ((u + v + step) & 1) == 0,
                "meta": {"step": step},
            }
            fnx_graph.add_edge(u, v, **attrs)
            nx_graph.add_edge(u, v, **attrs)
    return fnx_graph, nx_graph

def _node_payload(graph):
    return [(node, dict(attrs)) for node, attrs in graph.nodes(data=True)]

def _edge_payload(graph):
    return [(u, v, dict(attrs)) for u, v, attrs in graph.edges(data=True)]

def _assert_to_directed_contract(fnx_graph, nx_graph):
    fnx_directed = fnx_graph.to_directed()
    nx_directed = nx_graph.to_directed()
    assert _node_payload(fnx_directed) == _node_payload(nx_directed)
    assert _edge_payload(fnx_directed) == _edge_payload(nx_directed)

    fnx_directed.nodes[0]["i"] = -1
    assert fnx_graph.nodes[0]["i"] == 0
    fnx_directed[0][19]["weight"] = -1
    assert fnx_graph[0][19]["weight"] != -1

    object_fnx = fnx.Graph()
    object_nx = nx.Graph()
    payload = ["mutable"]
    object_fnx.add_edge("a", "b", payload=payload)
    object_nx.add_edge("a", "b", payload=list(payload))
    object_directed = object_fnx.to_directed()
    assert _edge_payload(object_directed) == _edge_payload(object_nx.to_directed())
    assert object_directed["a"]["b"]["payload"] == payload
    assert object_directed["a"]["b"]["payload"] is not object_fnx["a"]["b"]["payload"]
    object_directed["a"]["b"]["payload"].append("child")
    assert object_fnx["a"]["b"]["payload"] == payload

scalar_fnx, scalar_nx = _paired_scalar_attr_graph(2000)
_assert_to_directed_contract(scalar_fnx, scalar_nx)

fnx_graph_to_directed_scalar_attrs = lambda: scalar_fnx.to_directed()
nx_graph_to_directed_scalar_attrs = lambda: scalar_nx.to_directed()

iterator_edge_count = 20_000
tuple_edges = tuple((i, i + 1) for i in range(iterator_edge_count))
list_edges = tuple([i, i + 1] for i in range(iterator_edge_count))

fnx_graph_iterator_tuples = lambda: fnx.Graph(iter(tuple_edges))
nx_graph_iterator_tuples = lambda: nx.Graph(iter(tuple_edges))
# Frozen behavior-isomorphic baseline for the pre-fix implementation, which
# cannot absorb list rows from a true iterator directly.
fnx_graph_iterator_lists_normalized = lambda: fnx.Graph(
    tuple(row) for row in list_edges
)
fnx_graph_iterator_lists = lambda: fnx.Graph(iter(list_edges))
nx_graph_iterator_lists = lambda: nx.Graph(iter(list_edges))
fnx_digraph_iterator_lists = lambda: fnx.DiGraph(iter(list_edges))
nx_digraph_iterator_lists = lambda: nx.DiGraph(iter(list_edges))
fnx_multigraph_iterator_lists = lambda: fnx.MultiGraph(iter(list_edges))
nx_multigraph_iterator_lists = lambda: nx.MultiGraph(iter(list_edges))
fnx_multidigraph_iterator_lists = lambda: fnx.MultiDiGraph(iter(list_edges))
nx_multidigraph_iterator_lists = lambda: nx.MultiDiGraph(iter(list_edges))

keyed_edges = tuple((i, i + 1, f"k{i}") for i in range(iterator_edge_count))
fnx_multidigraph_iterator_keyed = lambda: fnx.MultiDiGraph(iter(keyed_edges))
nx_multidigraph_iterator_keyed = lambda: nx.MultiDiGraph(iter(keyed_edges))
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

    Ok(ConstructionCopyWorkloads {
        fnx_graph_to_directed_scalar_attrs: callable("fnx_graph_to_directed_scalar_attrs")?,
        nx_graph_to_directed_scalar_attrs: callable("nx_graph_to_directed_scalar_attrs")?,
        fnx_graph_iterator_tuples: callable("fnx_graph_iterator_tuples")?,
        nx_graph_iterator_tuples: callable("nx_graph_iterator_tuples")?,
        fnx_graph_iterator_lists_normalized: callable("fnx_graph_iterator_lists_normalized")?,
        fnx_graph_iterator_lists: callable("fnx_graph_iterator_lists")?,
        nx_graph_iterator_lists: callable("nx_graph_iterator_lists")?,
        fnx_digraph_iterator_lists: callable("fnx_digraph_iterator_lists")?,
        nx_digraph_iterator_lists: callable("nx_digraph_iterator_lists")?,
        fnx_multigraph_iterator_lists: callable("fnx_multigraph_iterator_lists")?,
        nx_multigraph_iterator_lists: callable("nx_multigraph_iterator_lists")?,
        fnx_multidigraph_iterator_lists: callable("fnx_multidigraph_iterator_lists")?,
        nx_multidigraph_iterator_lists: callable("nx_multidigraph_iterator_lists")?,
        fnx_multidigraph_iterator_keyed: callable("fnx_multidigraph_iterator_keyed")?,
        nx_multidigraph_iterator_keyed: callable("nx_multidigraph_iterator_keyed")?,
    })
}

fn prepare_core_laggard_workloads(py: Python<'_>) -> PyResult<CoreLaggardWorkloads> {
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
import glob
import importlib.util
import os
import sys

target_dir = os.environ.get("CARGO_TARGET_DIR")
if target_dir and "franken_networkx._fnx" not in sys.modules:
    candidates = [
        os.path.join(target_dir, "release", "lib_fnx.so"),
        *glob.glob(os.path.join(target_dir, "release", "deps", "lib_fnx*.so")),
    ]
    for path in candidates:
        if os.path.exists(path):
            spec = importlib.util.spec_from_file_location("franken_networkx._fnx", path)
            module = importlib.util.module_from_spec(spec)
            sys.modules["franken_networkx._fnx"] = module
            spec.loader.exec_module(module)
            break

for _name in list(sys.modules):
    if _name == "networkx" or _name.startswith("networkx."):
        del sys.modules[_name]

import networkx as nx
import franken_networkx as fnx

if "legacy_networkx_code" not in getattr(nx, "__file__", ""):
    raise AssertionError(f"expected vendored NetworkX oracle, got {nx.__file__!r}")

def _paired_multidigraph(node_count):
    fnx_graph = fnx.MultiDiGraph()
    nx_graph = nx.MultiDiGraph()
    fnx_graph.add_nodes_from(range(node_count))
    nx_graph.add_nodes_from(range(node_count))
    for u in range(node_count):
        for step in range(1, 7):
            v = (u * 41 + step * 17) % node_count
            if v == u:
                v = (v + step + 3) % node_count
            for parallel in range(3):
                attrs = {}
                if (u + v + step + parallel) % 11 != 0:
                    attrs["weight"] = (u * 7 + v * 13 + step * 5 + parallel) % 29 - 8
                fnx_graph.add_edge(u, v, **attrs)
                nx_graph.add_edge(u, v, **attrs)
    for u in range(0, node_count, 23):
        for parallel in range(2):
            attrs = {"weight": (u * 19 + parallel) % 37 - 11}
            fnx_graph.add_edge(u, u, **attrs)
            nx_graph.add_edge(u, u, **attrs)
    return fnx_graph, nx_graph

def _paired_multigraph_selfloops(node_count):
    fnx_graph = fnx.MultiGraph()
    nx_graph = nx.MultiGraph()
    fnx_graph.add_nodes_from(range(node_count))
    nx_graph.add_nodes_from(range(node_count))
    for u in range(node_count):
        v = (u * 31 + 7) % node_count
        if v == u:
            v = (v + 1) % node_count
        weight = (u * 5 + v) % 17
        fnx_graph.add_edge(u, v, weight=weight)
        nx_graph.add_edge(u, v, weight=weight)
        if u % 3 == 0:
            for parallel in range(3):
                weight = (u * 11 + parallel * 3) % 41 - 9
                fnx_graph.add_edge(u, u, weight=weight)
                nx_graph.add_edge(u, u, weight=weight)
    return fnx_graph, nx_graph

def _paired_multidigraph_custom_keys(node_count):
    fnx_graph = fnx.MultiDiGraph()
    nx_graph = nx.MultiDiGraph()
    fnx_graph.add_nodes_from(range(node_count))
    nx_graph.add_nodes_from(range(node_count))
    for u in range(node_count):
        for step in range(1, 7):
            v = (u * 43 + step * 19) % node_count
            if v == u:
                v = (v + step + 5) % node_count
            for parallel in range(3):
                key = f"k-{u}-{step}-{parallel}"
                attrs = {"weight": (u * 11 + v * 13 + step * 17 + parallel) % 31 - 7}
                fnx_graph.add_edge(u, v, key=key, **attrs)
                nx_graph.add_edge(u, v, key=key, **attrs)
    return fnx_graph, nx_graph

mdg_fnx, mdg_nx = _paired_multidigraph(700)
mg_self_fnx, mg_self_nx = _paired_multigraph_selfloops(2500)
mdg_custom_fnx, mdg_custom_nx = _paired_multidigraph_custom_keys(700)
mdg_custom_nbunch = [((i * 7) % 700) for i in range(480)]
mdg_custom_nbunch.extend([701, 702, 3, 3, 99])

def _mdg_in_degree_weight(graph):
    return sum(degree for _, degree in graph.in_degree(weight="weight"))

def _mg_selfloop_keys_weight(graph, module):
    return sum(value for _, _, _, value in module.selfloop_edges(graph, keys=True, data="weight"))

def _mdg_edges_keys(graph):
    return sum(key for _, _, key in graph.edges(keys=True))

def _mdg_in_edges_data(graph):
    return sum(
        key + value
        for _, _, key, value in graph.in_edges(keys=True, data="weight", default=0)
    )

def _mdg_out_edges_nbunch_keys_data(graph):
    return sum(
        data.get("weight", 0) + len(str(key))
        for _, _, key, data in graph.out_edges(
            mdg_custom_nbunch,
            keys=True,
            data=True,
        )
    )

def _mdg_out_edges_nbunch_keys_weight(graph):
    return sum(
        weight + len(str(key))
        for _, _, key, weight in graph.out_edges(
            mdg_custom_nbunch,
            keys=True,
            data="weight",
            default=0,
        )
    )

assert _mdg_in_degree_weight(mdg_fnx) == _mdg_in_degree_weight(mdg_nx)
assert _mg_selfloop_keys_weight(mg_self_fnx, fnx) == _mg_selfloop_keys_weight(mg_self_nx, nx)
assert _mdg_edges_keys(mdg_fnx) == _mdg_edges_keys(mdg_nx)
assert list(mdg_fnx.in_edges(keys=True, data="weight", default=0)) == list(
    mdg_nx.in_edges(keys=True, data="weight", default=0)
)
assert _mdg_in_edges_data(mdg_fnx) == _mdg_in_edges_data(mdg_nx)
assert list(mdg_custom_fnx.out_edges(mdg_custom_nbunch, keys=True, data=True)) == list(
    mdg_custom_nx.out_edges(mdg_custom_nbunch, keys=True, data=True)
)
assert _mdg_out_edges_nbunch_keys_data(mdg_custom_fnx) == _mdg_out_edges_nbunch_keys_data(
    mdg_custom_nx
)
assert list(mdg_custom_fnx.out_edges(mdg_custom_nbunch, keys=True, data="weight", default=0)) == list(
    mdg_custom_nx.out_edges(mdg_custom_nbunch, keys=True, data="weight", default=0)
)
assert _mdg_out_edges_nbunch_keys_weight(mdg_custom_fnx) == _mdg_out_edges_nbunch_keys_weight(
    mdg_custom_nx
)

fnx_mdg_in_degree_weight = lambda: _mdg_in_degree_weight(mdg_fnx)
nx_mdg_in_degree_weight = lambda: _mdg_in_degree_weight(mdg_nx)
fnx_mg_selfloop_keys_weight = lambda: _mg_selfloop_keys_weight(mg_self_fnx, fnx)
nx_mg_selfloop_keys_weight = lambda: _mg_selfloop_keys_weight(mg_self_nx, nx)
fnx_mdg_edges_keys = lambda: _mdg_edges_keys(mdg_fnx)
nx_mdg_edges_keys = lambda: _mdg_edges_keys(mdg_nx)
fnx_mdg_in_edges_data = lambda: _mdg_in_edges_data(mdg_fnx)
nx_mdg_in_edges_data = lambda: _mdg_in_edges_data(mdg_nx)
fnx_mdg_out_edges_nbunch_keys_data = lambda: _mdg_out_edges_nbunch_keys_data(mdg_custom_fnx)
nx_mdg_out_edges_nbunch_keys_data = lambda: _mdg_out_edges_nbunch_keys_data(mdg_custom_nx)
fnx_mdg_out_edges_nbunch_keys_weight = lambda: _mdg_out_edges_nbunch_keys_weight(mdg_custom_fnx)
nx_mdg_out_edges_nbunch_keys_weight = lambda: _mdg_out_edges_nbunch_keys_weight(mdg_custom_nx)
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

    Ok(CoreLaggardWorkloads {
        fnx_mdg_in_degree_weight: callable("fnx_mdg_in_degree_weight")?,
        nx_mdg_in_degree_weight: callable("nx_mdg_in_degree_weight")?,
        fnx_mg_selfloop_keys_weight: callable("fnx_mg_selfloop_keys_weight")?,
        nx_mg_selfloop_keys_weight: callable("nx_mg_selfloop_keys_weight")?,
        fnx_mdg_edges_keys: callable("fnx_mdg_edges_keys")?,
        nx_mdg_edges_keys: callable("nx_mdg_edges_keys")?,
        fnx_mdg_in_edges_data: callable("fnx_mdg_in_edges_data")?,
        nx_mdg_in_edges_data: callable("nx_mdg_in_edges_data")?,
        fnx_mdg_out_edges_nbunch_keys_data: callable("fnx_mdg_out_edges_nbunch_keys_data")?,
        nx_mdg_out_edges_nbunch_keys_data: callable("nx_mdg_out_edges_nbunch_keys_data")?,
        fnx_mdg_out_edges_nbunch_keys_weight: callable("fnx_mdg_out_edges_nbunch_keys_weight")?,
        nx_mdg_out_edges_nbunch_keys_weight: callable("nx_mdg_out_edges_nbunch_keys_weight")?,
    })
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
ba_overlap_s = list(range(0, 1250))
ba_overlap_t = list(range(625, 1875))

fnx_edge_ba = lambda: fnx.edge_expansion(ba_fnx, ba_cut)
nx_edge_ba = lambda: nx.edge_expansion(ba_nx, ba_cut)
fnx_edge_ws = lambda: fnx.edge_expansion(ws_fnx, ws_cut)
nx_edge_ws = lambda: nx.edge_expansion(ws_nx, ws_cut)
fnx_node_ba = lambda: fnx.node_expansion(ba_fnx, ba_cut)
nx_node_ba = lambda: nx.node_expansion(ba_nx, ba_cut)
fnx_node_ws = lambda: fnx.node_expansion(ws_fnx, ws_cut)
nx_node_ws = lambda: nx.node_expansion(ws_nx, ws_cut)
fnx_cut_overlap_ba = lambda: fnx.cut_size(ba_fnx, ba_overlap_s, ba_overlap_t)
nx_cut_overlap_ba = lambda: nx.cut_size(ba_nx, ba_overlap_s, ba_overlap_t)
fnx_normalized_cut_overlap_ba = lambda: fnx.normalized_cut_size(ba_fnx, ba_overlap_s, ba_overlap_t)
nx_normalized_cut_overlap_ba = lambda: nx.normalized_cut_size(ba_nx, ba_overlap_s, ba_overlap_t)

assert fnx_edge_ba() == nx_edge_ba()
assert fnx_edge_ws() == nx_edge_ws()
assert fnx_node_ba() == nx_node_ba()
assert fnx_node_ws() == nx_node_ws()
assert fnx_cut_overlap_ba() == nx_cut_overlap_ba()
assert abs(fnx_normalized_cut_overlap_ba() - nx_normalized_cut_overlap_ba()) < 1e-12
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
        fnx_cut_overlap_ba: callable("fnx_cut_overlap_ba")?,
        nx_cut_overlap_ba: callable("nx_cut_overlap_ba")?,
        fnx_normalized_cut_overlap_ba: callable("fnx_normalized_cut_overlap_ba")?,
        nx_normalized_cut_overlap_ba: callable("nx_normalized_cut_overlap_ba")?,
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

fn prepare_multidigraph_weighted_degree_workloads(
    py: Python<'_>,
) -> PyResult<MultiDiGraphWeightedDegreeWorkloads> {
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

def _paired_weighted_mdg(node_count):
    fnx_graph = fnx.MultiDiGraph()
    nx_graph = nx.MultiDiGraph()
    fnx_graph.add_nodes_from(range(node_count))
    nx_graph.add_nodes_from(range(node_count))
    for source in range(node_count):
        for step in range(1, 5):
            target = (source * 37 + step * 17) % node_count
            for parallel in range(2):
                weight = (source * 19 + target * 23 + step * 29 + parallel * 31) % 101 - 37
                fnx_graph.add_edge(source, target, weight=weight)
                nx_graph.add_edge(source, target, weight=weight)
    return fnx_graph, nx_graph

mdg_degree_fnx, mdg_degree_nx = _paired_weighted_mdg(1800)

assert list(mdg_degree_fnx.in_degree(weight="weight")) == list(
    mdg_degree_nx.in_degree(weight="weight")
)
assert list(mdg_degree_fnx.out_degree(weight="weight")) == list(
    mdg_degree_nx.out_degree(weight="weight")
)

fnx_in_degree_weight = lambda: sum(deg for _, deg in mdg_degree_fnx.in_degree(weight="weight"))
nx_in_degree_weight = lambda: sum(deg for _, deg in mdg_degree_nx.in_degree(weight="weight"))
fnx_out_degree_weight = lambda: sum(deg for _, deg in mdg_degree_fnx.out_degree(weight="weight"))
nx_out_degree_weight = lambda: sum(deg for _, deg in mdg_degree_nx.out_degree(weight="weight"))
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

    Ok(MultiDiGraphWeightedDegreeWorkloads {
        fnx_in_degree_weight: callable("fnx_in_degree_weight")?,
        nx_in_degree_weight: callable("nx_in_degree_weight")?,
        fnx_out_degree_weight: callable("fnx_out_degree_weight")?,
        nx_out_degree_weight: callable("nx_out_degree_weight")?,
    })
}

fn prepare_multigraph_biconnected_workloads(
    py: Python<'_>,
) -> PyResult<MultiGraphBiconnectedWorkloads> {
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
import random
import sys

for _name in list(sys.modules):
    if _name == "networkx" or _name.startswith("networkx."):
        del sys.modules[_name]

import networkx as nx
import franken_networkx as fnx

if "legacy_networkx_code" not in getattr(nx, "__file__", ""):
    raise AssertionError(f"expected vendored NetworkX oracle, got {nx.__file__!r}")

def _paired_multigraph_biconnected_workload(node_count, extra_edges, parallel_edges, seed):
    rng = random.Random(seed)
    edges = []
    for i in range(node_count):
        edges.append((i, (i + 1) % node_count, {"weight": float((i * 17) % 101) + 0.25}))
    for k in range(extra_edges):
        u = rng.randrange(node_count)
        v = rng.randrange(node_count - 1)
        if v >= u:
            v += 1
        edges.append((u, v, {"weight": float((u * 31 + v * 17 + k) % 257) + 0.5}))
    for k in range(parallel_edges):
        u, v, _ = edges[rng.randrange(len(edges))]
        edges.append((u, v, {"weight": float((u * 13 + v * 19 + k) % 113) + 0.125}))

    fnx_graph = fnx.MultiGraph()
    nx_graph = nx.MultiGraph()
    fnx_graph.add_nodes_from(range(node_count))
    nx_graph.add_nodes_from(range(node_count))
    fnx_graph.add_edges_from(edges)
    nx_graph.add_edges_from(edges)
    return fnx_graph, nx_graph

mg_fnx, mg_nx = _paired_multigraph_biconnected_workload(1000, 3000, 1000, 20260620)
assert fnx.is_biconnected(mg_fnx) == nx.is_biconnected(mg_nx)
assert list(fnx.articulation_points(mg_fnx)) == list(nx.articulation_points(mg_nx))
assert [set(c) for c in fnx.biconnected_components(mg_fnx)] == [set(c) for c in nx.biconnected_components(mg_nx)]
assert list(fnx.bfs_edges(mg_fnx, 0)) == list(nx.bfs_edges(mg_nx, 0))

def _mst_signature(tree):
    return [
        (u, v, k, data.get("weight"))
        for u, v, k, data in tree.edges(keys=True, data=True)
    ]

fnx_mst_sig = _mst_signature(fnx.minimum_spanning_tree(mg_fnx, weight="weight"))
nx_mst_sig = _mst_signature(nx.minimum_spanning_tree(mg_nx, weight="weight"))
if not all(pair[0].__eq__(pair[1]) for pair in zip(fnx_mst_sig, nx_mst_sig, strict=True)):
    raise AssertionError((fnx_mst_sig, nx_mst_sig))

def _component_checksum(components):
    total = 0
    for idx, component in enumerate(components):
        subtotal = 0
        for node in component:
            subtotal += int(node) + 1
        total += (idx + 1) * subtotal + len(component) * 17
    return total

fnx_is_biconnected = lambda: fnx.is_biconnected(mg_fnx)
nx_is_biconnected = lambda: nx.is_biconnected(mg_nx)
fnx_articulation_points = lambda: len(list(fnx.articulation_points(mg_fnx)))
nx_articulation_points = lambda: len(list(nx.articulation_points(mg_nx)))
fnx_biconnected_components = lambda: _component_checksum(fnx.biconnected_components(mg_fnx))
nx_biconnected_components = lambda: _component_checksum(nx.biconnected_components(mg_nx))
fnx_bfs_edges = lambda: len(list(fnx.bfs_edges(mg_fnx, 0)))
nx_bfs_edges = lambda: len(list(nx.bfs_edges(mg_nx, 0)))
fnx_minimum_spanning_tree = lambda: fnx.minimum_spanning_tree(mg_fnx, weight="weight")
nx_minimum_spanning_tree = lambda: nx.minimum_spanning_tree(mg_nx, weight="weight")
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

    Ok(MultiGraphBiconnectedWorkloads {
        fnx_is_biconnected: callable("fnx_is_biconnected")?,
        nx_is_biconnected: callable("nx_is_biconnected")?,
        fnx_articulation_points: callable("fnx_articulation_points")?,
        nx_articulation_points: callable("nx_articulation_points")?,
        fnx_biconnected_components: callable("fnx_biconnected_components")?,
        nx_biconnected_components: callable("nx_biconnected_components")?,
        fnx_bfs_edges: callable("fnx_bfs_edges")?,
        nx_bfs_edges: callable("nx_bfs_edges")?,
        fnx_minimum_spanning_tree: callable("fnx_minimum_spanning_tree")?,
        nx_minimum_spanning_tree: callable("nx_minimum_spanning_tree")?,
    })
}

fn prepare_multigraph_weighted_degree_workloads(
    py: Python<'_>,
) -> PyResult<MultiGraphWeightedDegreeWorkloads> {
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

def _paired_multigraph_weighted_degree_workload(node_count):
    fnx_graph = fnx.MultiGraph()
    nx_graph = nx.MultiGraph()
    fnx_graph.add_nodes_from(range(node_count))
    nx_graph.add_nodes_from(range(node_count))

    for u in range(node_count):
        for step in range(1, 5):
            v = (u * 37 + step * 11) % node_count
            if v == u:
                v = (v + step + 1) % node_count
            for parallel in range(2):
                attrs = {}
                if (u + step + parallel) % 7 != 0:
                    attrs["weight"] = (u * 13 + v * 17 + parallel * 19 + step) % 23 - 5
                fnx_graph.add_edge(u, v, **attrs)
                nx_graph.add_edge(u, v, **attrs)

    for u in range(0, node_count, 17):
        attrs = {"weight": (u * 29) % 31 - 9}
        fnx_graph.add_edge(u, u, **attrs)
        nx_graph.add_edge(u, u, **attrs)

    return fnx_graph, nx_graph

mg_degree_fnx, mg_degree_nx = _paired_multigraph_weighted_degree_workload(400)
mg_degree_nbunch = [((i * 7) % 400) for i in range(280)]
mg_degree_nbunch.extend([401, 402, 3, 3, 99])

fnx_degree_pairs = list(fnx.degree(mg_degree_fnx, mg_degree_nbunch, weight="weight"))
nx_degree_pairs = list(nx.degree(mg_degree_nx, mg_degree_nbunch, weight="weight"))
assert fnx_degree_pairs == nx_degree_pairs

fnx_degree_nbunch_weight = lambda: sum(
    degree for _, degree in fnx.degree(mg_degree_fnx, mg_degree_nbunch, weight="weight")
)
nx_degree_nbunch_weight = lambda: sum(
    degree for _, degree in nx.degree(mg_degree_nx, mg_degree_nbunch, weight="weight")
)

assert mg_degree_fnx.size(weight="weight") == mg_degree_nx.size(weight="weight")
fnx_size_weight_degree_formula = lambda: sum(
    degree for _, degree in mg_degree_fnx.degree(weight="weight")
) / 2
fnx_size_weight = lambda: mg_degree_fnx.size(weight="weight")
nx_size_weight = lambda: mg_degree_nx.size(weight="weight")
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

    Ok(MultiGraphWeightedDegreeWorkloads {
        fnx_degree_nbunch_weight: callable("fnx_degree_nbunch_weight")?,
        nx_degree_nbunch_weight: callable("nx_degree_nbunch_weight")?,
        fnx_size_weight_degree_formula: callable("fnx_size_weight_degree_formula")?,
        fnx_size_weight: callable("fnx_size_weight")?,
        nx_size_weight: callable("nx_size_weight")?,
    })
}

fn prepare_tree_submodule_workloads(py: Python<'_>) -> PyResult<TreeSubmoduleWorkloads> {
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
import random
import sys

for _name in list(sys.modules):
    if _name == "networkx" or _name.startswith("networkx."):
        del sys.modules[_name]

import networkx as nx
import networkx.algorithms.tree as nx_tree
import franken_networkx as fnx
import franken_networkx.tree as fnx_tree

if "legacy_networkx_code" not in getattr(nx, "__file__", ""):
    raise AssertionError(f"expected vendored NetworkX oracle, got {nx.__file__!r}")

def _paired_weighted_graph(node_count, extra_edges, seed):
    rng = random.Random(seed)
    edges = []
    for i in range(node_count - 1):
        edges.append((i, i + 1, {"weight": float((i * 17) % 101) + 0.25}))
    for k in range(extra_edges):
        u = rng.randrange(node_count)
        v = rng.randrange(node_count - 1)
        if v >= u:
            v += 1
        edges.append((u, v, {"weight": float((u * 31 + v * 17 + k) % 257) + 0.5}))

    fnx_graph = fnx.Graph()
    nx_graph = nx.Graph()
    fnx_graph.add_nodes_from(range(node_count))
    nx_graph.add_nodes_from(range(node_count))
    fnx_graph.add_edges_from(edges)
    nx_graph.add_edges_from(edges)
    return fnx_graph, nx_graph

def _mst_signature(tree):
    return [(u, v, data.get("weight")) for u, v, data in tree.edges(data=True)]

tree_fnx, tree_nx = _paired_weighted_graph(1000, 4000, 20260621)
fnx_mst_sig = _mst_signature(fnx_tree.minimum_spanning_tree(tree_fnx, weight="weight"))
nx_mst_sig = _mst_signature(nx_tree.minimum_spanning_tree(tree_nx, weight="weight"))
if not all(pair[0].__eq__(pair[1]) for pair in zip(fnx_mst_sig, nx_mst_sig, strict=True)):
    raise AssertionError((fnx_mst_sig, nx_mst_sig))

fnx_minimum_spanning_tree = lambda: fnx_tree.minimum_spanning_tree(tree_fnx, weight="weight")
nx_minimum_spanning_tree = lambda: nx_tree.minimum_spanning_tree(tree_nx, weight="weight")
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

    Ok(TreeSubmoduleWorkloads {
        fnx_minimum_spanning_tree: callable("fnx_minimum_spanning_tree")?,
        nx_minimum_spanning_tree: callable("nx_minimum_spanning_tree")?,
    })
}

fn prepare_lattice_generator_workloads(py: Python<'_>) -> PyResult<LatticeGeneratorWorkloads> {
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
import hashlib
import json
import networkx as nx
import franken_networkx as fnx
from franken_networkx.backend import _fnx_to_nx

def _canon(g):
    payload = {
        "nodes": [repr(n) for n in g.nodes()],
        "edges": [(repr(u), repr(v)) for u, v in g.edges()],
        "pos": sorted((repr(k), repr(v)) for k, v in nx.get_node_attributes(g, "pos").items()),
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

def _fnx_triangular():
    return fnx.triangular_lattice_graph(60, 60)

def _nx_triangular():
    return nx.triangular_lattice_graph(60, 60)

def _fnx_hexagonal():
    return fnx.hexagonal_lattice_graph(60, 60)

def _nx_hexagonal():
    return nx.hexagonal_lattice_graph(60, 60)

assert _canon(_fnx_to_nx(_fnx_triangular())) == _canon(_nx_triangular())
assert _canon(_fnx_to_nx(_fnx_hexagonal())) == _canon(_nx_hexagonal())

fnx_triangular = _fnx_triangular
nx_triangular = _nx_triangular
fnx_hexagonal = _fnx_hexagonal
nx_hexagonal = _nx_hexagonal
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

    Ok(LatticeGeneratorWorkloads {
        fnx_triangular: callable("fnx_triangular")?,
        nx_triangular: callable("nx_triangular")?,
        fnx_hexagonal: callable("fnx_hexagonal")?,
        nx_hexagonal: callable("nx_hexagonal")?,
    })
}

fn prepare_adjacency_outer_cache_workloads(
    py: Python<'_>,
) -> PyResult<AdjacencyOuterCacheWorkloads> {
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
import glob
import importlib.util
import os
import sys

target_dir = os.environ.get("CARGO_TARGET_DIR")
if target_dir and "franken_networkx._fnx" not in sys.modules:
    candidates = [
        os.path.join(target_dir, "release", "lib_fnx.so"),
        *glob.glob(os.path.join(target_dir, "release", "deps", "lib_fnx*.so")),
    ]
    for path in candidates:
        if os.path.exists(path):
            spec = importlib.util.spec_from_file_location("franken_networkx._fnx", path)
            module = importlib.util.module_from_spec(spec)
            sys.modules["franken_networkx._fnx"] = module
            spec.loader.exec_module(module)
            break

import networkx as nx
import franken_networkx as fnx

def _paired_graphs(n, directed=False):
    base = nx.barabasi_albert_graph(n, 4, seed=9144 + n)
    edges = list(base.edges())
    if directed:
        nx_g = nx.DiGraph()
        fnx_g = fnx.DiGraph()
        directed_edges = [
            (u, v) if ((u + v) & 1) == 0 else (v, u)
            for u, v in edges
        ]
        nx_g.add_nodes_from(base.nodes())
        fnx_g.add_nodes_from(base.nodes())
        nx_g.add_edges_from(directed_edges)
        fnx_g.add_edges_from(directed_edges)
    else:
        nx_g = nx.Graph()
        fnx_g = fnx.Graph()
        nx_g.add_nodes_from(base.nodes())
        fnx_g.add_nodes_from(base.nodes())
        nx_g.add_edges_from(edges)
        fnx_g.add_edges_from(edges)
    return fnx_g, nx_g

def _snapshot(graph):
    return {
        node: tuple(neighbors.keys())
        for node, neighbors in dict(graph.adjacency()).items()
    }

def _assert_adjacency_contract(fnx_g, nx_g):
    assert _snapshot(fnx_g) == _snapshot(nx_g)
    probe = next(iter(fnx_g))
    first = dict(fnx_g.adjacency())
    second = dict(fnx_g.adjacency())
    assert first[probe] is second[probe]

g2000_fnx, g2000_nx = _paired_graphs(2000, directed=False)
g8000_fnx, g8000_nx = _paired_graphs(8000, directed=False)
dg2000_fnx, dg2000_nx = _paired_graphs(2000, directed=True)
dg8000_fnx, dg8000_nx = _paired_graphs(8000, directed=True)

for _fnx_g, _nx_g in (
    (g2000_fnx, g2000_nx),
    (g8000_fnx, g8000_nx),
    (dg2000_fnx, dg2000_nx),
    (dg8000_fnx, dg8000_nx),
):
    _assert_adjacency_contract(_fnx_g, _nx_g)

fnx_graph_2000 = lambda: dict(g2000_fnx.adjacency())
nx_graph_2000 = lambda: dict(g2000_nx.adjacency())
fnx_graph_8000 = lambda: dict(g8000_fnx.adjacency())
nx_graph_8000 = lambda: dict(g8000_nx.adjacency())
fnx_digraph_2000 = lambda: dict(dg2000_fnx.adjacency())
nx_digraph_2000 = lambda: dict(dg2000_nx.adjacency())
fnx_digraph_8000 = lambda: dict(dg8000_fnx.adjacency())
nx_digraph_8000 = lambda: dict(dg8000_nx.adjacency())
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

    Ok(AdjacencyOuterCacheWorkloads {
        fnx_graph_2000: callable("fnx_graph_2000")?,
        nx_graph_2000: callable("nx_graph_2000")?,
        fnx_graph_8000: callable("fnx_graph_8000")?,
        nx_graph_8000: callable("nx_graph_8000")?,
        fnx_digraph_2000: callable("fnx_digraph_2000")?,
        nx_digraph_2000: callable("nx_digraph_2000")?,
        fnx_digraph_8000: callable("fnx_digraph_8000")?,
        nx_digraph_8000: callable("nx_digraph_8000")?,
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

fn bench_python_clear_edges_factory(
    group: &mut criterion::BenchmarkGroup<'_, criterion::measurement::WallTime>,
    name: &str,
    factory: &Py<PyAny>,
) {
    group.bench_function(name, |b| {
        b.iter_custom(|iters| {
            Python::attach(|py| {
                let factory = factory.bind(py);
                let mut elapsed = Duration::ZERO;
                for _ in 0..iters {
                    let graph = factory.call0().expect("Python graph factory failed");
                    let start = Instant::now();
                    graph
                        .call_method0("clear_edges")
                        .expect("clear_edges benchmark call failed");
                    elapsed += start.elapsed();
                    let edge_count = graph
                        .call_method0("number_of_edges")
                        .expect("number_of_edges check failed")
                        .extract::<usize>()
                        .expect("number_of_edges should return usize");
                    assert_eq!(edge_count, 0);
                }
                elapsed
            })
        });
    });
}

fn clear_edges_head_to_head(c: &mut Criterion) {
    Python::initialize();
    let workloads = Python::attach(prepare_clear_edges_workloads)
        .expect("failed to prepare clear_edges Python workloads");
    let mut group = c.benchmark_group("networkx_head_to_head_clear_edges");
    group.sample_size(20);

    bench_python_clear_edges_factory(
        &mut group,
        "fnx_multigraph_clear_edges_n800_e4000",
        &workloads.fnx_multigraph_factory,
    );
    bench_python_clear_edges_factory(
        &mut group,
        "nx_multigraph_clear_edges_n800_e4000",
        &workloads.nx_multigraph_factory,
    );

    group.finish();
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
    bench_python_callable(
        &mut group,
        "fnx_cut_size_overlap_ba2500_s1250_t1250",
        &workloads.fnx_cut_overlap_ba,
    );
    bench_python_callable(
        &mut group,
        "nx_cut_size_overlap_ba2500_s1250_t1250",
        &workloads.nx_cut_overlap_ba,
    );
    bench_python_callable(
        &mut group,
        "fnx_normalized_cut_size_overlap_ba2500_s1250_t1250",
        &workloads.fnx_normalized_cut_overlap_ba,
    );
    bench_python_callable(
        &mut group,
        "nx_normalized_cut_size_overlap_ba2500_s1250_t1250",
        &workloads.nx_normalized_cut_overlap_ba,
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

fn multidigraph_weighted_degree_head_to_head(c: &mut Criterion) {
    Python::initialize();
    let workloads = Python::attach(prepare_multidigraph_weighted_degree_workloads)
        .expect("failed to prepare MultiDiGraph weighted degree Python workloads");
    let mut group = c.benchmark_group("networkx_head_to_head_multidigraph_weighted_degree");
    group.sample_size(20);

    bench_python_callable(
        &mut group,
        "fnx_in_degree_weight_mdg1800_e14400",
        &workloads.fnx_in_degree_weight,
    );
    bench_python_callable(
        &mut group,
        "nx_in_degree_weight_mdg1800_e14400",
        &workloads.nx_in_degree_weight,
    );
    bench_python_callable(
        &mut group,
        "fnx_out_degree_weight_mdg1800_e14400",
        &workloads.fnx_out_degree_weight,
    );
    bench_python_callable(
        &mut group,
        "nx_out_degree_weight_mdg1800_e14400",
        &workloads.nx_out_degree_weight,
    );

    group.finish();
}

fn multigraph_biconnected_head_to_head(c: &mut Criterion) {
    Python::initialize();
    let workloads = Python::attach(prepare_multigraph_biconnected_workloads)
        .expect("failed to prepare MultiGraph biconnected Python workloads");
    let mut group = c.benchmark_group("networkx_head_to_head_multigraph_biconnected");
    group.sample_size(20);

    bench_python_callable(
        &mut group,
        "fnx_is_biconnected_mg1000_e5000",
        &workloads.fnx_is_biconnected,
    );
    bench_python_callable(
        &mut group,
        "nx_is_biconnected_mg1000_e5000",
        &workloads.nx_is_biconnected,
    );
    bench_python_callable(
        &mut group,
        "fnx_articulation_points_mg1000_e5000",
        &workloads.fnx_articulation_points,
    );
    bench_python_callable(
        &mut group,
        "nx_articulation_points_mg1000_e5000",
        &workloads.nx_articulation_points,
    );
    bench_python_callable(
        &mut group,
        "fnx_biconnected_components_mg1000_e5000",
        &workloads.fnx_biconnected_components,
    );
    bench_python_callable(
        &mut group,
        "nx_biconnected_components_mg1000_e5000",
        &workloads.nx_biconnected_components,
    );
    bench_python_callable(
        &mut group,
        "fnx_bfs_edges_mg1000_e5000",
        &workloads.fnx_bfs_edges,
    );
    bench_python_callable(
        &mut group,
        "nx_bfs_edges_mg1000_e5000",
        &workloads.nx_bfs_edges,
    );
    bench_python_callable(
        &mut group,
        "fnx_minimum_spanning_tree_mg1000_e5000",
        &workloads.fnx_minimum_spanning_tree,
    );
    bench_python_callable(
        &mut group,
        "nx_minimum_spanning_tree_mg1000_e5000",
        &workloads.nx_minimum_spanning_tree,
    );

    group.finish();
}

fn multigraph_weighted_degree_head_to_head(c: &mut Criterion) {
    Python::initialize();
    let workloads = Python::attach(prepare_multigraph_weighted_degree_workloads)
        .expect("failed to prepare MultiGraph weighted degree Python workloads");
    let mut group = c.benchmark_group("networkx_head_to_head_multigraph_weighted_degree");
    group.sample_size(20);

    bench_python_callable(
        &mut group,
        "fnx_degree_nbunch_weight_mg400_e3224",
        &workloads.fnx_degree_nbunch_weight,
    );
    bench_python_callable(
        &mut group,
        "nx_degree_nbunch_weight_mg400_e3224",
        &workloads.nx_degree_nbunch_weight,
    );
    bench_python_callable(
        &mut group,
        "fnx_size_weight_degree_formula_mg400_e3224",
        &workloads.fnx_size_weight_degree_formula,
    );
    bench_python_callable(
        &mut group,
        "fnx_size_weight_mg400_e3224",
        &workloads.fnx_size_weight,
    );
    bench_python_callable(
        &mut group,
        "nx_size_weight_mg400_e3224",
        &workloads.nx_size_weight,
    );

    group.finish();
}

fn tree_submodule_head_to_head(c: &mut Criterion) {
    Python::initialize();
    let workloads = Python::attach(prepare_tree_submodule_workloads)
        .expect("failed to prepare tree submodule Python workloads");
    let mut group = c.benchmark_group("networkx_head_to_head_tree_submodule");
    group.sample_size(10);

    bench_python_callable(
        &mut group,
        "fnx_tree_minimum_spanning_tree_g1000_e4999",
        &workloads.fnx_minimum_spanning_tree,
    );
    bench_python_callable(
        &mut group,
        "nx_tree_minimum_spanning_tree_g1000_e4999",
        &workloads.nx_minimum_spanning_tree,
    );

    group.finish();
}

fn lattice_generators_head_to_head(c: &mut Criterion) {
    Python::initialize();
    let workloads = Python::attach(prepare_lattice_generator_workloads)
        .expect("failed to prepare lattice generator Python workloads");
    let mut group = c.benchmark_group("networkx_head_to_head_lattice_generators");
    group.sample_size(20);

    bench_python_callable(
        &mut group,
        "fnx_triangular_lattice_graph_60_60",
        &workloads.fnx_triangular,
    );
    bench_python_callable(
        &mut group,
        "nx_triangular_lattice_graph_60_60",
        &workloads.nx_triangular,
    );
    bench_python_callable(
        &mut group,
        "fnx_hexagonal_lattice_graph_60_60",
        &workloads.fnx_hexagonal,
    );
    bench_python_callable(
        &mut group,
        "nx_hexagonal_lattice_graph_60_60",
        &workloads.nx_hexagonal,
    );

    group.finish();
}

fn adjacency_outer_cache_head_to_head(c: &mut Criterion) {
    Python::initialize();
    let workloads = Python::attach(prepare_adjacency_outer_cache_workloads)
        .expect("failed to prepare adjacency outer-cache Python workloads");
    let mut group = c.benchmark_group("networkx_head_to_head_adjacency_outer_cache");
    group.sample_size(20);

    bench_python_callable(
        &mut group,
        "fnx_graph_dict_adjacency_n2000",
        &workloads.fnx_graph_2000,
    );
    bench_python_callable(
        &mut group,
        "nx_graph_dict_adjacency_n2000",
        &workloads.nx_graph_2000,
    );
    bench_python_callable(
        &mut group,
        "fnx_graph_dict_adjacency_n8000",
        &workloads.fnx_graph_8000,
    );
    bench_python_callable(
        &mut group,
        "nx_graph_dict_adjacency_n8000",
        &workloads.nx_graph_8000,
    );
    bench_python_callable(
        &mut group,
        "fnx_digraph_dict_adjacency_n2000",
        &workloads.fnx_digraph_2000,
    );
    bench_python_callable(
        &mut group,
        "nx_digraph_dict_adjacency_n2000",
        &workloads.nx_digraph_2000,
    );
    bench_python_callable(
        &mut group,
        "fnx_digraph_dict_adjacency_n8000",
        &workloads.fnx_digraph_8000,
    );
    bench_python_callable(
        &mut group,
        "nx_digraph_dict_adjacency_n8000",
        &workloads.nx_digraph_8000,
    );

    group.finish();
}

fn core_laggard_head_to_head(c: &mut Criterion) {
    Python::initialize();
    let workloads = Python::attach(prepare_core_laggard_workloads)
        .expect("failed to prepare core laggard Python workloads");
    let mut group = c.benchmark_group("networkx_head_to_head_core_laggards");
    group.sample_size(20);

    bench_python_callable(
        &mut group,
        "fnx_mdg_in_degree_weight_n700_e12662",
        &workloads.fnx_mdg_in_degree_weight,
    );
    bench_python_callable(
        &mut group,
        "nx_mdg_in_degree_weight_n700_e12662",
        &workloads.nx_mdg_in_degree_weight,
    );
    bench_python_callable(
        &mut group,
        "fnx_mg_selfloop_keys_weight_n2500_loops2502",
        &workloads.fnx_mg_selfloop_keys_weight,
    );
    bench_python_callable(
        &mut group,
        "nx_mg_selfloop_keys_weight_n2500_loops2502",
        &workloads.nx_mg_selfloop_keys_weight,
    );
    bench_python_callable(
        &mut group,
        "fnx_mdg_edges_keys_n700_e12662",
        &workloads.fnx_mdg_edges_keys,
    );
    bench_python_callable(
        &mut group,
        "nx_mdg_edges_keys_n700_e12662",
        &workloads.nx_mdg_edges_keys,
    );
    bench_python_callable(
        &mut group,
        "fnx_mdg_in_edges_data_n700_e12662",
        &workloads.fnx_mdg_in_edges_data,
    );
    bench_python_callable(
        &mut group,
        "nx_mdg_in_edges_data_n700_e12662",
        &workloads.nx_mdg_in_edges_data,
    );
    bench_python_callable(
        &mut group,
        "fnx_mdg_out_edges_nbunch_keys_data_n700_e12600",
        &workloads.fnx_mdg_out_edges_nbunch_keys_data,
    );
    bench_python_callable(
        &mut group,
        "nx_mdg_out_edges_nbunch_keys_data_n700_e12600",
        &workloads.nx_mdg_out_edges_nbunch_keys_data,
    );
    bench_python_callable(
        &mut group,
        "fnx_mdg_out_edges_nbunch_keys_weight_n700_e12600",
        &workloads.fnx_mdg_out_edges_nbunch_keys_weight,
    );
    bench_python_callable(
        &mut group,
        "nx_mdg_out_edges_nbunch_keys_weight_n700_e12600",
        &workloads.nx_mdg_out_edges_nbunch_keys_weight,
    );

    group.finish();
}

fn construction_copy_head_to_head(c: &mut Criterion) {
    Python::initialize();
    let workloads = Python::attach(prepare_construction_copy_workloads)
        .expect("failed to prepare construction/copy Python workloads");
    let mut group = c.benchmark_group("networkx_head_to_head_construction_copy");
    group.sample_size(20);

    bench_python_callable(
        &mut group,
        "fnx_graph_to_directed_scalar_attrs_n2000",
        &workloads.fnx_graph_to_directed_scalar_attrs,
    );
    bench_python_callable(
        &mut group,
        "nx_graph_to_directed_scalar_attrs_n2000",
        &workloads.nx_graph_to_directed_scalar_attrs,
    );
    bench_python_callable(
        &mut group,
        "fnx_graph_iterator_tuples_e20000",
        &workloads.fnx_graph_iterator_tuples,
    );
    bench_python_callable(
        &mut group,
        "nx_graph_iterator_tuples_e20000",
        &workloads.nx_graph_iterator_tuples,
    );
    bench_python_callable(
        &mut group,
        "fnx_graph_iterator_lists_normalized_e20000",
        &workloads.fnx_graph_iterator_lists_normalized,
    );
    bench_python_callable(
        &mut group,
        "fnx_graph_iterator_lists_e20000",
        &workloads.fnx_graph_iterator_lists,
    );
    bench_python_callable(
        &mut group,
        "nx_graph_iterator_lists_e20000",
        &workloads.nx_graph_iterator_lists,
    );
    bench_python_callable(
        &mut group,
        "fnx_digraph_iterator_lists_e20000",
        &workloads.fnx_digraph_iterator_lists,
    );
    bench_python_callable(
        &mut group,
        "nx_digraph_iterator_lists_e20000",
        &workloads.nx_digraph_iterator_lists,
    );
    bench_python_callable(
        &mut group,
        "fnx_multigraph_iterator_lists_e20000",
        &workloads.fnx_multigraph_iterator_lists,
    );
    bench_python_callable(
        &mut group,
        "nx_multigraph_iterator_lists_e20000",
        &workloads.nx_multigraph_iterator_lists,
    );
    bench_python_callable(
        &mut group,
        "fnx_multidigraph_iterator_lists_e20000",
        &workloads.fnx_multidigraph_iterator_lists,
    );
    bench_python_callable(
        &mut group,
        "nx_multidigraph_iterator_lists_e20000",
        &workloads.nx_multidigraph_iterator_lists,
    );
    bench_python_callable(
        &mut group,
        "fnx_multidigraph_iterator_keyed_e20000",
        &workloads.fnx_multidigraph_iterator_keyed,
    );
    bench_python_callable(
        &mut group,
        "nx_multidigraph_iterator_keyed_e20000",
        &workloads.nx_multidigraph_iterator_keyed,
    );

    group.finish();
}

fn sticky_edge_dirty_head_to_head(c: &mut Criterion) {
    Python::initialize();
    let workloads = Python::attach(prepare_sticky_edge_dirty_workloads)
        .expect("failed to prepare sticky edge-dirty Python workloads");
    let mut group = c.benchmark_group("networkx_head_to_head_sticky_edge_dirty");
    group.sample_size(20);

    bench_python_callable(
        &mut group,
        "fnx_dijkstra_path_ba2000_weighted_after_edges_data",
        &workloads.fnx_dijkstra_path,
    );
    bench_python_callable(
        &mut group,
        "nx_dijkstra_path_ba2000_weighted_after_edges_data",
        &workloads.nx_dijkstra_path,
    );

    group.finish();
}

fn prepare_tsp_workloads(py: Python<'_>) -> PyResult<TspWorkloads> {
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

def _complete_weighted(n):
    fg = fnx.complete_graph(n)
    ng = nx.complete_graph(n)
    for u, v in list(ng.edges()):
        # Tie-free, real-valued weights: fixing one endpoint, w varies
        # monotonically with the other (u*u + v*v + u*v is strictly
        # increasing in each argument), so every nearest-neighbour step has a
        # unique minimum and the native fast path engages (and is byte-exact).
        w = float(u * u + v * v + u * v + 1)
        fg.edges[u, v]["weight"] = w
        ng.edges[u, v]["weight"] = w
    return fg, ng

tsp_fnx, tsp_nx = _complete_weighted(250)

fnx_greedy_tsp = lambda: fnx.approximation.greedy_tsp(tsp_fnx, source=0)
nx_greedy_tsp = lambda: nx.approximation.greedy_tsp(tsp_nx, source=0)

# Correctness gate baked into the bench: the native tour must equal nx's.
assert fnx_greedy_tsp() == nx_greedy_tsp(), "greedy_tsp tour diverged from NetworkX"

# simulated_annealing / threshold_accepting TSP: integer weights (so the
# vectorised numpy cycle cost equals nx's left-to-right Python sum exactly) on
# a complete graph, run at nx's default config (N_inner=100).
def _complete_int_weighted(n):
    fg = fnx.complete_graph(n)
    ng = nx.complete_graph(n)
    for u, v in list(ng.edges()):
        w = (u * 7 + v * 3) % 50 + 1
        fg.edges[u, v]["weight"] = w
        ng.edges[u, v]["weight"] = w
    return fg, ng

anneal_fnx, anneal_nx = _complete_int_weighted(200)
anneal_init = list(range(200)) + [0]

fnx_sa_tsp = lambda: fnx.approximation.simulated_annealing_tsp(anneal_fnx, anneal_init, source=0, seed=7)
nx_sa_tsp = lambda: nx.approximation.simulated_annealing_tsp(anneal_nx, anneal_init, source=0, seed=7)
fnx_ta_tsp = lambda: fnx.approximation.threshold_accepting_tsp(anneal_fnx, anneal_init, source=0, seed=7)
nx_ta_tsp = lambda: nx.approximation.threshold_accepting_tsp(anneal_nx, anneal_init, source=0, seed=7)

assert fnx_sa_tsp() == nx_sa_tsp(), "simulated_annealing_tsp tour diverged from NetworkX"
assert fnx_ta_tsp() == nx_ta_tsp(), "threshold_accepting_tsp tour diverged from NetworkX"
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

    Ok(TspWorkloads {
        fnx_greedy_tsp: callable("fnx_greedy_tsp")?,
        nx_greedy_tsp: callable("nx_greedy_tsp")?,
        fnx_sa_tsp: callable("fnx_sa_tsp")?,
        nx_sa_tsp: callable("nx_sa_tsp")?,
        fnx_ta_tsp: callable("fnx_ta_tsp")?,
        nx_ta_tsp: callable("nx_ta_tsp")?,
    })
}

fn tsp_head_to_head(c: &mut Criterion) {
    Python::initialize();
    let workloads =
        Python::attach(prepare_tsp_workloads).expect("failed to prepare TSP Python workloads");
    let mut group = c.benchmark_group("networkx_head_to_head_tsp");
    group.sample_size(20);

    bench_python_callable(
        &mut group,
        "fnx_greedy_tsp_complete_n250",
        &workloads.fnx_greedy_tsp,
    );
    bench_python_callable(
        &mut group,
        "nx_greedy_tsp_complete_n250",
        &workloads.nx_greedy_tsp,
    );
    bench_python_callable(
        &mut group,
        "fnx_simulated_annealing_tsp_complete_n200",
        &workloads.fnx_sa_tsp,
    );
    bench_python_callable(
        &mut group,
        "nx_simulated_annealing_tsp_complete_n200",
        &workloads.nx_sa_tsp,
    );
    bench_python_callable(
        &mut group,
        "fnx_threshold_accepting_tsp_complete_n200",
        &workloads.fnx_ta_tsp,
    );
    bench_python_callable(
        &mut group,
        "nx_threshold_accepting_tsp_complete_n200",
        &workloads.nx_ta_tsp,
    );

    group.finish();
}

fn prepare_voronoi_workloads(py: Python<'_>) -> PyResult<VoronoiWorkloads> {
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

# Weighted undirected graph: voronoi_cells used to delegate the whole call to nx
# (the stale _mst_has_weight_edge_attr gate -> O(V+E) conversion). The native
# multi_source_nearest_source binding now serves it byte-exact (cells compare
# order-insensitively, so the kernel tie-break is irrelevant).
G = nx.connected_watts_strogatz_graph(400, 6, 0.3, seed=3)
fg = fnx.Graph()
fg.add_nodes_from(G.nodes())
for u, v in G.edges():
    G[u][v]["weight"] = (u * 7 + v * 3) % 9 + 1
fg.add_edges_from((u, v, d) for u, v, d in G.edges(data=True))
centers = set(range(0, 400, 80))

fnx_voronoi = lambda: fnx.voronoi_cells(fg, centers)
nx_voronoi = lambda: nx.voronoi_cells(G, centers)

# Correctness gate baked into the bench: cells (order-insensitive) match nx.
assert fnx_voronoi() == nx_voronoi(), "voronoi_cells diverged from NetworkX"
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

    Ok(VoronoiWorkloads {
        fnx_voronoi: callable("fnx_voronoi")?,
        nx_voronoi: callable("nx_voronoi")?,
    })
}

fn voronoi_head_to_head(c: &mut Criterion) {
    Python::initialize();
    let workloads = Python::attach(prepare_voronoi_workloads)
        .expect("failed to prepare voronoi Python workloads");
    let mut group = c.benchmark_group("networkx_head_to_head_voronoi");
    group.sample_size(20);

    bench_python_callable(
        &mut group,
        "fnx_voronoi_cells_weighted_n400",
        &workloads.fnx_voronoi,
    );
    bench_python_callable(
        &mut group,
        "nx_voronoi_cells_weighted_n400",
        &workloads.nx_voronoi,
    );

    group.finish();
}

struct KCoreWorkloads {
    fnx_kcore: Py<PyAny>,
    nx_kcore: Py<PyAny>,
}

fn prepare_kcore_workloads(py: Python<'_>) -> PyResult<KCoreWorkloads> {
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
import glob
import importlib.util
import os
import sys

target_dir = os.environ.get("CARGO_TARGET_DIR")
if target_dir and "franken_networkx._fnx" not in sys.modules:
    candidates = [
        os.path.join(target_dir, "release", "lib_fnx.so"),
        *glob.glob(os.path.join(target_dir, "release", "deps", "lib_fnx*.so")),
    ]
    for path in candidates:
        if os.path.exists(path):
            spec = importlib.util.spec_from_file_location("franken_networkx._fnx", path)
            module = importlib.util.module_from_spec(spec)
            sys.modules["franken_networkx._fnx"] = module
            spec.loader.exec_module(module)
            break

for _name in list(sys.modules):
    if _name == "networkx" or _name.startswith("networkx."):
        del sys.modules[_name]

import networkx as nx
import franken_networkx as fnx
import franken_networkx._fnx as _raw

if "legacy_networkx_code" not in getattr(nx, "__file__", ""):
    raise AssertionError(f"expected vendored NetworkX oracle, got {nx.__file__!r}")

def _paired_attr_graph(n, m, seed):
    base = nx.barabasi_albert_graph(n, m, seed=seed)
    gf = fnx.Graph()
    gn = nx.Graph()
    for i in base.nodes():
        gf.add_node(i, color=(i % 5), tag="v")
        gn.add_node(i, color=(i % 5), tag="v")
    for j, (u, v) in enumerate(base.edges()):
        w = (u * 7 + v * 11 + j) % 13
        gf.add_edge(u, v, weight=w)
        gn.add_edge(u, v, weight=w)
    return gf, gn

gf, gn = _paired_attr_graph(4000, 4, 7)

def _canon_edges(G):
    return sorted(tuple(sorted((u, v))) for u, v in G.edges())

def _edge_attr_map(G):
    return {tuple(sorted((u, v))): dict(d) for u, v, d in G.edges(data=True)}

def _assert_parity(k):
    rf = fnx.k_core(gf, k)
    rn = nx.k_core(gn, k)
    assert list(rf.nodes()) == list(rn.nodes()), f"k_core node order mismatch k={k}"
    assert _canon_edges(rf) == _canon_edges(rn), f"k_core edge set mismatch k={k}"
    assert dict(rf.nodes(data=True)) == dict(rn.nodes(data=True)), f"k_core node attrs mismatch k={k}"
    assert _edge_attr_map(rf) == _edge_attr_map(rn), f"k_core edge attrs mismatch k={k}"

for _k in (None, 2, 3, 5):
    _assert_parity(_k)

# Confirm fnx.k_core actually routes to the NATIVE kernel (not the nx fallback):
# its result must equal the direct native binding for the same input.
assert list(fnx.k_core(gf, 3).nodes()) == list(_raw.k_core_rust(gf, 3).nodes())

fnx_kcore = lambda: fnx.k_core(gf, 3).number_of_nodes()
nx_kcore = lambda: nx.k_core(gn, 3).number_of_nodes()
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

    Ok(KCoreWorkloads {
        fnx_kcore: callable("fnx_kcore")?,
        nx_kcore: callable("nx_kcore")?,
    })
}

fn kcore_head_to_head(c: &mut Criterion) {
    Python::initialize();
    let workloads =
        Python::attach(prepare_kcore_workloads).expect("failed to prepare k_core Python workloads");
    let mut group = c.benchmark_group("networkx_head_to_head_kcore");
    group.sample_size(20);
    bench_python_callable(&mut group, "fnx_k_core_ba4000_k3", &workloads.fnx_kcore);
    bench_python_callable(&mut group, "nx_k_core_ba4000_k3", &workloads.nx_kcore);
    group.finish();
}

struct KCoreFamilyWorkloads {
    fnx_kshell: Py<PyAny>,
    nx_kshell: Py<PyAny>,
    fnx_kcrust: Py<PyAny>,
    nx_kcrust: Py<PyAny>,
    fnx_kcorona: Py<PyAny>,
    nx_kcorona: Py<PyAny>,
}

fn prepare_kcore_family_workloads(py: Python<'_>) -> PyResult<KCoreFamilyWorkloads> {
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
import glob
import importlib.util
import os
import sys

target_dir = os.environ.get("CARGO_TARGET_DIR")
if target_dir and "franken_networkx._fnx" not in sys.modules:
    candidates = [
        os.path.join(target_dir, "release", "lib_fnx.so"),
        *glob.glob(os.path.join(target_dir, "release", "deps", "lib_fnx*.so")),
    ]
    for path in candidates:
        if os.path.exists(path):
            spec = importlib.util.spec_from_file_location("franken_networkx._fnx", path)
            module = importlib.util.module_from_spec(spec)
            sys.modules["franken_networkx._fnx"] = module
            spec.loader.exec_module(module)
            break

for _name in list(sys.modules):
    if _name == "networkx" or _name.startswith("networkx."):
        del sys.modules[_name]

import networkx as nx
import franken_networkx as fnx

if "legacy_networkx_code" not in getattr(nx, "__file__", ""):
    raise AssertionError(f"expected vendored NetworkX oracle, got {nx.__file__!r}")

def _paired_attr_graph(n, m, seed):
    base = nx.barabasi_albert_graph(n, m, seed=seed)
    gf = fnx.Graph()
    gn = nx.Graph()
    for i in base.nodes():
        gf.add_node(i, color=(i % 5), tag="v")
        gn.add_node(i, color=(i % 5), tag="v")
    for j, (u, v) in enumerate(base.edges()):
        w = (u * 7 + v * 11 + j) % 13
        gf.add_edge(u, v, weight=w)
        gn.add_edge(u, v, weight=w)
    return gf, gn

gf, gn = _paired_attr_graph(4000, 4, 7)

def _canon_edges(G):
    return sorted(tuple(sorted((u, v))) for u, v in G.edges())

def _edge_attr_map(G):
    return {tuple(sorted((u, v))): dict(d) for u, v, d in G.edges(data=True)}

def _assert_pair(rf, rn, label):
    assert list(rf.nodes()) == list(rn.nodes()), f"{label}: node order mismatch"
    assert _canon_edges(rf) == _canon_edges(rn), f"{label}: edge set mismatch"
    assert dict(rf.nodes(data=True)) == dict(rn.nodes(data=True)), f"{label}: node attrs mismatch"
    assert _edge_attr_map(rf) == _edge_attr_map(rn), f"{label}: edge attrs mismatch"

for _k in (None, 2, 3, 4, 5):
    _assert_pair(fnx.k_shell(gf, _k), nx.k_shell(gn, _k), f"k_shell k={_k}")
for _k in (None, 1, 2, 3, 4):
    _assert_pair(fnx.k_crust(gf, _k), nx.k_crust(gn, _k), f"k_crust k={_k}")
for _k in (1, 2, 3, 4):
    _assert_pair(fnx.k_corona(gf, _k), nx.k_corona(gn, _k), f"k_corona k={_k}")

# Edge-case parity: the native route must DELEGATE (not silently compute) where nx raises, so the
# same exception surfaces. Empty graph with k=None -> nx max([]) ValueError; any self loop ->
# nx.core_number NetworkXNotImplemented.
def _both_raise(fn_f, fn_n, gf_, gn_, *a):
    try:
        fn_n(gn_, *a)
        raised_n = False
    except Exception:
        raised_n = True
    try:
        fn_f(gf_, *a)
        raised_f = False
    except Exception:
        raised_f = True
    assert raised_n and raised_f, f"raise parity mismatch: nx={raised_n} fnx={raised_f}"

ef, en = fnx.Graph(), nx.Graph()
_both_raise(fnx.k_shell, nx.k_shell, ef, en)
_both_raise(fnx.k_crust, nx.k_crust, ef, en)

sf, sn = fnx.Graph(), nx.Graph()
for _g in (sf, sn):
    _g.add_edge(0, 0)
    _g.add_edge(0, 1)
    _g.add_edge(1, 2)
_both_raise(fnx.k_shell, nx.k_shell, sf, sn)
_both_raise(fnx.k_crust, nx.k_crust, sf, sn)
_both_raise(fnx.k_core, nx.k_core, sf, sn)
_both_raise(fnx.k_corona, nx.k_corona, sf, sn, 2)

fnx_kshell = lambda: fnx.k_shell(gf, 3).number_of_nodes()
nx_kshell = lambda: nx.k_shell(gn, 3).number_of_nodes()
fnx_kcrust = lambda: fnx.k_crust(gf, 2).number_of_nodes()
nx_kcrust = lambda: nx.k_crust(gn, 2).number_of_nodes()
fnx_kcorona = lambda: fnx.k_corona(gf, 2).number_of_nodes()
nx_kcorona = lambda: nx.k_corona(gn, 2).number_of_nodes()
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

    Ok(KCoreFamilyWorkloads {
        fnx_kshell: callable("fnx_kshell")?,
        nx_kshell: callable("nx_kshell")?,
        fnx_kcrust: callable("fnx_kcrust")?,
        nx_kcrust: callable("nx_kcrust")?,
        fnx_kcorona: callable("fnx_kcorona")?,
        nx_kcorona: callable("nx_kcorona")?,
    })
}

fn kcore_family_head_to_head(c: &mut Criterion) {
    Python::initialize();
    let workloads = Python::attach(prepare_kcore_family_workloads)
        .expect("failed to prepare k_core-family Python workloads");
    let mut group = c.benchmark_group("networkx_head_to_head_kcore_family");
    group.sample_size(15);
    bench_python_callable(&mut group, "fnx_k_shell_ba4000_k3", &workloads.fnx_kshell);
    bench_python_callable(&mut group, "nx_k_shell_ba4000_k3", &workloads.nx_kshell);
    bench_python_callable(&mut group, "fnx_k_crust_ba4000_k2", &workloads.fnx_kcrust);
    bench_python_callable(&mut group, "nx_k_crust_ba4000_k2", &workloads.nx_kcrust);
    bench_python_callable(&mut group, "fnx_k_corona_ba4000_k2", &workloads.fnx_kcorona);
    bench_python_callable(&mut group, "nx_k_corona_ba4000_k2", &workloads.nx_kcorona);
    group.finish();
}

struct IndegBindingWorkloads {
    old_binding: Py<PyAny>,
    new_binding: Py<PyAny>,
    old_total: Py<PyAny>,
    new_total: Py<PyAny>,
    old_core: Py<PyAny>,
    new_core: Py<PyAny>,
}

fn prepare_indeg_binding_workloads(py: Python<'_>) -> PyResult<IndegBindingWorkloads> {
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
import glob
import importlib.util
import os
import sys

target_dir = os.environ.get("CARGO_TARGET_DIR")
if target_dir and "franken_networkx._fnx" not in sys.modules:
    candidates = [
        os.path.join(target_dir, "release", "lib_fnx.so"),
        *glob.glob(os.path.join(target_dir, "release", "deps", "lib_fnx*.so")),
    ]
    for path in candidates:
        if os.path.exists(path):
            spec = importlib.util.spec_from_file_location("franken_networkx._fnx", path)
            module = importlib.util.module_from_spec(spec)
            sys.modules["franken_networkx._fnx"] = module
            spec.loader.exec_module(module)
            break

for _name in list(sys.modules):
    if _name == "networkx" or _name.startswith("networkx."):
        del sys.modules[_name]

import networkx as nx
import franken_networkx as fnx
import franken_networkx._fnx as _raw

# Directed graph, ~20k nodes so the O(V) dict build (not the O(V+E) degree scan) is timed.
_base = nx.scale_free_graph(20000, seed=11)
gd = fnx.DiGraph()
gd.add_nodes_from(range(20000))
for _u, _v in _base.edges():
    gd.add_edge(_u, _v)

# Confirm the live inline `in_degree_centrality` is BYTE-IDENTICAL to the preserved OLD
# kernel+centrality_to_dict baseline: same {node: score} mapping AND same key insertion order.
_old = _raw.in_degree_centrality_kernel_ab(gd)
_new = _raw.in_degree_centrality(gd)
assert list(_old.items()) == list(_new.items()), "in_degree_centrality inline parity (order+values)"

# br-r37-c1-tdcbind: directed TOTAL degree_centrality — same throwaway-String lever, multiplication
# formula. Assert the routed inline degree_centrality == the preserved kernel baseline byte-for-byte.
_old_t = _raw.degree_centrality_directed_kernel_ab(gd)
_new_t = _raw.degree_centrality(gd)
assert list(_old_t.items()) == list(_new_t.items()), "degree_centrality (total) inline parity (order+values)"

# br-r37-c1-corenumsl: core_number self-loop guard. Undirected simple Graph, NO self-loops (the
# common case where the old per-node neighbors() Vec-alloc scan iterates all V nodes). Assert the
# new alloc-free number_of_selfloops() guard gives the byte-identical {node: core} result.
_ba = nx.barabasi_albert_graph(20000, 8, seed=13)
gu = fnx.Graph()
gu.add_nodes_from(range(20000))
for _u, _v in _ba.edges():
    gu.add_edge(_u, _v)
_old_c = _raw.core_number_selfloopscan_ab(gu)
_new_c = _raw.core_number(gu)
assert list(_old_c.items()) == list(_new_c.items()), "core_number self-loop-guard parity (order+values)"

old_binding = lambda: _raw.in_degree_centrality_kernel_ab(gd)
new_binding = lambda: _raw.in_degree_centrality(gd)
old_total = lambda: _raw.degree_centrality_directed_kernel_ab(gd)
new_total = lambda: _raw.degree_centrality(gd)
old_core = lambda: _raw.core_number_selfloopscan_ab(gu)
new_core = lambda: _raw.core_number(gu)
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

    Ok(IndegBindingWorkloads {
        old_binding: callable("old_binding")?,
        new_binding: callable("new_binding")?,
        old_total: callable("old_total")?,
        new_total: callable("new_total")?,
        old_core: callable("old_core")?,
        new_core: callable("new_core")?,
    })
}

// br-r37-c1-idcbind: with-GIL binding-layer A/B. Both arms build the SAME {node: score} PyDict for
// the same 20k-node DiGraph; the only difference is the old arm materializes an n-element
// Vec<CentralityScore> (throwaway node.to_owned() Strings) in the kernel, while the new inline arm
// walks indices → get_node_name → py_node_key directly. Measures whether removing the String churn
// clears the shared PyDict-build floor (py_node_key + set_item per node, common to both arms).
fn indeg_binding_head_to_head(c: &mut Criterion) {
    Python::initialize();
    let workloads = Python::attach(prepare_indeg_binding_workloads)
        .expect("failed to prepare in_degree_centrality binding A/B workloads");
    let mut group = c.benchmark_group("networkx_head_to_head_indeg_binding");
    group.sample_size(30);
    bench_python_callable(
        &mut group,
        "old_centrality_to_dict_20k",
        &workloads.old_binding,
    );
    bench_python_callable(&mut group, "new_inline_20k", &workloads.new_binding);
    bench_python_callable(
        &mut group,
        "old_total_centrality_to_dict_20k",
        &workloads.old_total,
    );
    bench_python_callable(&mut group, "new_total_inline_20k", &workloads.new_total);
    bench_python_callable(&mut group, "old_core_selfloopscan_20k", &workloads.old_core);
    bench_python_callable(&mut group, "new_core_numselfloops_20k", &workloads.new_core);
    group.finish();
}

criterion_group!(
    benches,
    kcore_head_to_head,
    kcore_family_head_to_head,
    indeg_binding_head_to_head,
    voronoi_head_to_head,
    tsp_head_to_head,
    construction_copy_head_to_head,
    sticky_edge_dirty_head_to_head,
    clear_edges_head_to_head,
    core_laggard_head_to_head,
    cut_metric_head_to_head,
    assortativity_head_to_head,
    assortativity_raw_head_to_head,
    link_prediction_head_to_head,
    multidigraph_connectivity_head_to_head,
    multigraph_biconnected_head_to_head,
    multigraph_weighted_degree_head_to_head,
    tree_submodule_head_to_head,
    lattice_generators_head_to_head,
    adjacency_outer_cache_head_to_head,
    multidigraph_weighted_degree_head_to_head
);
criterion_main!(benches);
