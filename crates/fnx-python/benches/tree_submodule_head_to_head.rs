//! Criterion head-to-head for the `franken_networkx.tree` submodule wrappers.
//!
//! This measures the public submodule surface, not just the top-level
//! `franken_networkx.minimum_spanning_tree` functions.

use criterion::{Criterion, criterion_group, criterion_main};
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};
use std::ffi::CString;
use std::path::Path;

fn cstring(source: &str) -> CString {
    CString::new(source).expect("Python snippets must not contain NUL bytes")
}

struct TreeSubmoduleWorkloads {
    fnx_minimum_spanning_tree: Py<PyAny>,
    nx_minimum_spanning_tree: Py<PyAny>,
    fnx_maximum_spanning_tree: Py<PyAny>,
    nx_maximum_spanning_tree: Py<PyAny>,
    fnx_from_nested_tuple: Py<PyAny>,
    nx_from_nested_tuple: Py<PyAny>,
    fnx_from_nested_tuple_sensible: Py<PyAny>,
    nx_from_nested_tuple_sensible: Py<PyAny>,
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
    let target_dir = std::env::var("CARGO_TARGET_DIR")
        .map(std::path::PathBuf::from)
        .unwrap_or_else(|_| repo_root.join("target"));
    locals.set_item(
        "_FNX_TARGET_DIR",
        target_dir.to_str().expect("target dir must be UTF-8"),
    )?;
    py.run(
        cstring(
            r#"
import importlib.util
import operator
import pathlib
import random
import sys
import types

import networkx as nx
import networkx.algorithms.tree as nx_tree


def _preload_fnx_extension():
    target_dir = pathlib.Path(_FNX_TARGET_DIR)
    candidates = [
        target_dir / "release" / "lib_fnx.so",
        target_dir / "release" / "deps" / "lib_fnx.so",
        target_dir / "debug" / "lib_fnx.so",
        target_dir / "debug" / "deps" / "lib_fnx.so",
    ]
    for candidate in candidates:
        if not candidate.exists():
            continue
        spec = importlib.util.spec_from_file_location(
            "franken_networkx._fnx",
            candidate,
        )
        if spec is None or spec.loader is None:
            continue
        module = importlib.util.module_from_spec(spec)
        sys.modules["franken_networkx._fnx"] = module
        spec.loader.exec_module(module)
        return str(candidate)
    raise ImportError(
        f"could not locate bench-built franken_networkx._fnx in {target_dir}"
    )


_FNX_EXTENSION_PATH = _preload_fnx_extension()


class _MissingNumpy(types.ModuleType):
    def __getattr__(self, name):
        raise ImportError(
            "numpy is not available in this RCH bench environment; "
            f"attempted numpy.{name}"
        )


sys.modules.setdefault("numpy", _MissingNumpy("numpy"))

import franken_networkx as fnx
import franken_networkx.tree as fnx_tree

if "legacy_networkx_code/networkx" not in (nx.__file__ or ""):
    raise AssertionError(f"expected vendored NetworkX oracle, got {nx.__file__!r}")


def _build_weighted_sparse_graph(module, node_count, extra_edges, seed):
    rng = random.Random(seed)
    graph = module.Graph()
    graph.graph["name"] = "tree-submodule-head-to-head"
    graph.graph["node_count"] = node_count
    graph.graph["extra_edges"] = extra_edges
    for node in range(node_count):
        graph.add_node(node, label=f"n{node}", bucket=node % 17)

    seen = set()
    edge_index = 0
    for node in range(node_count - 1):
        u, v = node, node + 1
        seen.add((u, v))
        edge_index += 1
        graph.add_edge(
            u,
            v,
            weight=float(edge_index),
            tag=f"chain-{node}",
        )

    while len(seen) < node_count - 1 + extra_edges:
        u = rng.randrange(node_count)
        v = rng.randrange(node_count)
        if u == v:
            continue
        if u > v:
            u, v = v, u
        if (u, v) in seen:
            continue
        seen.add((u, v))
        edge_index += 1
        graph.add_edge(
            u,
            v,
            weight=float(edge_index),
            tag=f"shortcut-{edge_index}",
        )
    return graph


def _tree_signature(tree):
    nodes = tuple(
        (node, tuple(sorted(data.items())))
        for node, data in tree.nodes(data=True)
    )
    edges = tuple(
        sorted(
            (
                min(u, v),
                max(u, v),
                data.get("weight"),
                data.get("tag"),
            )
            for u, v, data in tree.edges(data=True)
        )
    )
    return nodes, edges, tuple(sorted(tree.graph.items()))


def _consume_tree(tree):
    return float(
        tree.size(weight="weight")
        + tree.number_of_nodes() * 0.001
        + tree.number_of_edges() * 0.000001
    )


def _nested_tuple(depth, fanout):
    if depth == 0:
        return ()
    return tuple(_nested_tuple(depth - 1, fanout) for _ in range(fanout))


def _unweighted_tree_signature(tree):
    return tuple(tree.nodes()), tuple(tree.edges())


def _consume_unweighted_tree(tree):
    node_sum = sum(int(node) for node in tree.nodes())
    return float(
        tree.number_of_nodes() * 0.001
        + tree.number_of_edges() * 0.000001
        + node_sum * 0.000000000001
    )


_NODE_COUNT = 900
_EXTRA_EDGES = 2700
_REPEAT = 4
_FROM_NESTED_REPEAT = 8
_NESTED_SEQUENCE = _nested_tuple(6, 3)
_FNX_GRAPH = _build_weighted_sparse_graph(fnx, _NODE_COUNT, _EXTRA_EDGES, 9157)
_NX_GRAPH = _build_weighted_sparse_graph(nx, _NODE_COUNT, _EXTRA_EDGES, 9157)

_FNX_MIN = _tree_signature(
    fnx_tree.minimum_spanning_tree(_FNX_GRAPH, weight="weight")
)
_NX_MIN = _tree_signature(
    nx_tree.minimum_spanning_tree(_NX_GRAPH, weight="weight")
)
if not operator.eq(_FNX_MIN, _NX_MIN):
    raise AssertionError("minimum_spanning_tree submodule parity drift")

_FNX_MAX = _tree_signature(
    fnx_tree.maximum_spanning_tree(_FNX_GRAPH, weight="weight")
)
_NX_MAX = _tree_signature(
    nx_tree.maximum_spanning_tree(_NX_GRAPH, weight="weight")
)
if not operator.eq(_FNX_MAX, _NX_MAX):
    raise AssertionError("maximum_spanning_tree submodule parity drift")

_FNX_NESTED = _unweighted_tree_signature(
    fnx_tree.from_nested_tuple(_NESTED_SEQUENCE)
)
_NX_NESTED = _unweighted_tree_signature(
    nx_tree.from_nested_tuple(_NESTED_SEQUENCE)
)
if not operator.eq(_FNX_NESTED, _NX_NESTED):
    raise AssertionError("from_nested_tuple submodule parity drift")

_FNX_NESTED_SENSIBLE = _unweighted_tree_signature(
    fnx_tree.from_nested_tuple(_NESTED_SEQUENCE, sensible_relabeling=True)
)
_NX_NESTED_SENSIBLE = _unweighted_tree_signature(
    nx_tree.from_nested_tuple(_NESTED_SEQUENCE, sensible_relabeling=True)
)
if not operator.eq(_FNX_NESTED_SENSIBLE, _NX_NESTED_SENSIBLE):
    raise AssertionError("from_nested_tuple sensible submodule parity drift")


def fnx_minimum_spanning_tree():
    total = 0.0
    for _ in range(_REPEAT):
        total += _consume_tree(
            fnx_tree.minimum_spanning_tree(_FNX_GRAPH, weight="weight")
        )
    return total


def nx_minimum_spanning_tree():
    total = 0.0
    for _ in range(_REPEAT):
        total += _consume_tree(
            nx_tree.minimum_spanning_tree(_NX_GRAPH, weight="weight")
        )
    return total


def fnx_maximum_spanning_tree():
    total = 0.0
    for _ in range(_REPEAT):
        total += _consume_tree(
            fnx_tree.maximum_spanning_tree(_FNX_GRAPH, weight="weight")
        )
    return total


def nx_maximum_spanning_tree():
    total = 0.0
    for _ in range(_REPEAT):
        total += _consume_tree(
            nx_tree.maximum_spanning_tree(_NX_GRAPH, weight="weight")
        )
    return total


def fnx_from_nested_tuple():
    total = 0.0
    for _ in range(_FROM_NESTED_REPEAT):
        total += _consume_unweighted_tree(
            fnx_tree.from_nested_tuple(_NESTED_SEQUENCE)
        )
    return total


def nx_from_nested_tuple():
    total = 0.0
    for _ in range(_FROM_NESTED_REPEAT):
        total += _consume_unweighted_tree(
            nx_tree.from_nested_tuple(_NESTED_SEQUENCE)
        )
    return total


def fnx_from_nested_tuple_sensible():
    total = 0.0
    for _ in range(_FROM_NESTED_REPEAT):
        total += _consume_unweighted_tree(
            fnx_tree.from_nested_tuple(_NESTED_SEQUENCE, sensible_relabeling=True)
        )
    return total


def nx_from_nested_tuple_sensible():
    total = 0.0
    for _ in range(_FROM_NESTED_REPEAT):
        total += _consume_unweighted_tree(
            nx_tree.from_nested_tuple(_NESTED_SEQUENCE, sensible_relabeling=True)
        )
    return total
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
        fnx_maximum_spanning_tree: callable("fnx_maximum_spanning_tree")?,
        nx_maximum_spanning_tree: callable("nx_maximum_spanning_tree")?,
        fnx_from_nested_tuple: callable("fnx_from_nested_tuple")?,
        nx_from_nested_tuple: callable("nx_from_nested_tuple")?,
        fnx_from_nested_tuple_sensible: callable("fnx_from_nested_tuple_sensible")?,
        nx_from_nested_tuple_sensible: callable("nx_from_nested_tuple_sensible")?,
    })
}

fn bench_python_callable(
    group: &mut criterion::BenchmarkGroup<'_, criterion::measurement::WallTime>,
    name: &str,
    callable: &Py<PyAny>,
) {
    group.bench_function(name, |b| {
        b.iter(|| {
            Python::attach(|py| {
                callable
                    .bind(py)
                    .call0()
                    .and_then(|value| value.extract::<f64>())
                    .expect("Python benchmark callable should return float")
            })
        });
    });
}

fn tree_submodule_head_to_head(c: &mut Criterion) {
    Python::initialize();
    let workloads = Python::attach(prepare_tree_submodule_workloads)
        .expect("failed to prepare tree submodule workloads");
    let mut group = c.benchmark_group("tree_submodule_spanning_tree");
    group.sample_size(10);

    bench_python_callable(
        &mut group,
        "fnx_minimum_spanning_tree_n900_e3599",
        &workloads.fnx_minimum_spanning_tree,
    );
    bench_python_callable(
        &mut group,
        "nx_minimum_spanning_tree_n900_e3599",
        &workloads.nx_minimum_spanning_tree,
    );
    bench_python_callable(
        &mut group,
        "fnx_maximum_spanning_tree_n900_e3599",
        &workloads.fnx_maximum_spanning_tree,
    );
    bench_python_callable(
        &mut group,
        "nx_maximum_spanning_tree_n900_e3599",
        &workloads.nx_maximum_spanning_tree,
    );

    group.finish();

    let mut group = c.benchmark_group("tree_submodule_from_nested_tuple");
    group.sample_size(10);

    bench_python_callable(
        &mut group,
        "fnx_from_nested_tuple_depth6_fanout3_repeat8",
        &workloads.fnx_from_nested_tuple,
    );
    bench_python_callable(
        &mut group,
        "nx_from_nested_tuple_depth6_fanout3_repeat8",
        &workloads.nx_from_nested_tuple,
    );
    bench_python_callable(
        &mut group,
        "fnx_from_nested_tuple_sensible_depth6_fanout3_repeat8",
        &workloads.fnx_from_nested_tuple_sensible,
    );
    bench_python_callable(
        &mut group,
        "nx_from_nested_tuple_sensible_depth6_fanout3_repeat8",
        &workloads.nx_from_nested_tuple_sensible,
    );

    group.finish();
}

criterion_group!(benches, tree_submodule_head_to_head);
criterion_main!(benches);
