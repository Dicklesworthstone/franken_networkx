//! Python bindings for graph I/O functions.
//!
//! Each read function accepts a file path (str or os.PathLike) or file-like object.
//! Each write function accepts a Graph and a file path or file-like object.
//! Internally delegates to `fnx_readwrite::EdgeListEngine` which operates on strings.

use crate::PyGraph;
use crate::algorithms::extract_graph;
use fnx_readwrite::EdgeListEngine;
use pyo3::prelude::*;
use pyo3::types::PyDict;
use std::collections::HashMap;

/// Read the file content from a path-like or file-like Python object.
fn read_input(py: Python<'_>, source: &Bound<'_, PyAny>) -> PyResult<String> {
    // Try file-like first (has .read())
    if let Ok(read_method) = source.getattr("read") {
        let content = read_method.call0()?;
        if let Ok(s) = content.extract::<String>() {
            return Ok(s);
        }
        if let Ok(b) = content.extract::<Vec<u8>>() {
            return String::from_utf8(b).map_err(|e| {
                pyo3::exceptions::PyUnicodeDecodeError::new_err(format!(
                    "cannot decode file content: {e}"
                ))
            });
        }
        return Err(pyo3::exceptions::PyTypeError::new_err(
            "file-like .read() must return str or bytes",
        ));
    }
    // Otherwise treat as path
    let pathlib = py.import("pathlib")?;
    let path_cls = pathlib.getattr("Path")?;
    let path = path_cls.call1((source,))?;
    let text = path.call_method1("read_text", ("utf-8",))?;
    text.extract::<String>()
}

/// Write string content to a path-like or file-like Python object.
fn write_output(py: Python<'_>, dest: &Bound<'_, PyAny>, content: &str) -> PyResult<()> {
    // Try file-like first (has .write())
    if let Ok(write_method) = dest.getattr("write") {
        write_method.call1((content,))?;
        return Ok(());
    }
    // Otherwise treat as path
    let pathlib = py.import("pathlib")?;
    let path_cls = pathlib.getattr("Path")?;
    let path = path_cls.call1((dest,))?;
    path.call_method1("write_text", (content, "utf-8"))?;
    Ok(())
}

/// Convert a `ReadWriteReport` into a `PyGraph`.
///
/// Builds Python-side maps (node_key_map, node_py_attrs, edge_py_attrs)
/// from the Rust Graph's string-keyed data.
fn report_to_pygraph(py: Python<'_>, report: fnx_readwrite::ReadWriteReport) -> PyResult<PyGraph> {
    let g = report.graph;

    // Build node_key_map: canonical string -> Python str object
    let mut node_key_map = HashMap::new();
    let mut node_py_attrs = HashMap::new();
    for node_id in g.nodes_ordered() {
        node_key_map.insert(
            node_id.to_owned(),
            node_id.into_pyobject(py)?.into_any().unbind(),
        );
        let d = PyDict::new(py);
        if let Some(attrs) = g.node_attrs(node_id) {
            for (k, v) in attrs {
                d.set_item(k, v)?;
            }
        }
        node_py_attrs.insert(node_id.to_owned(), d.unbind());
    }

    // Build edge_py_attrs from edges
    let mut edge_py_attrs = HashMap::new();
    for es in g.edges_ordered() {
        let key = PyGraph::edge_key(&es.left, &es.right);
        let d = PyDict::new(py);
        if let Some(attrs) = g.edge_attrs(&es.left, &es.right) {
            for (k, v) in attrs {
                d.set_item(k, v)?;
            }
        }
        edge_py_attrs.insert(key, d.unbind());
    }

    Ok(PyGraph {
        inner: g,
        node_key_map,
        node_py_attrs,
        edge_py_attrs,
        graph_attrs: PyDict::new(py).unbind(),
    })
}

fn rw_error_to_py(e: fnx_readwrite::ReadWriteError) -> PyErr {
    pyo3::exceptions::PyIOError::new_err(format!("{e}"))
}

// ---------------------------------------------------------------------------
// Edge list
// ---------------------------------------------------------------------------

#[pyfunction]
#[pyo3(signature = (path,))]
fn read_edgelist(py: Python<'_>, path: &Bound<'_, PyAny>) -> PyResult<PyGraph> {
    log::info!(target: "franken_networkx", "read_edgelist");
    let input = read_input(py, path)?;
    let mut engine = EdgeListEngine::hardened();
    let report = py
        .allow_threads(|| engine.read_edgelist(&input))
        .map_err(rw_error_to_py)?;
    report_to_pygraph(py, report)
}

#[pyfunction]
#[pyo3(signature = (g, path))]
fn write_edgelist(py: Python<'_>, g: &Bound<'_, PyAny>, path: &Bound<'_, PyAny>) -> PyResult<()> {
    log::info!(target: "franken_networkx", "write_edgelist");
    let gr = extract_graph(g)?;
    let graph = gr.undirected();
    let mut engine = EdgeListEngine::hardened();
    let content = py
        .allow_threads(|| engine.write_edgelist(graph))
        .map_err(rw_error_to_py)?;
    write_output(py, path, &content)
}

// ---------------------------------------------------------------------------
// Adjacency list
// ---------------------------------------------------------------------------

#[pyfunction]
#[pyo3(signature = (path,))]
fn read_adjlist(py: Python<'_>, path: &Bound<'_, PyAny>) -> PyResult<PyGraph> {
    let input = read_input(py, path)?;
    let mut engine = EdgeListEngine::hardened();
    let report = py
        .allow_threads(|| engine.read_adjlist(&input))
        .map_err(rw_error_to_py)?;
    report_to_pygraph(py, report)
}

#[pyfunction]
#[pyo3(signature = (g, path))]
fn write_adjlist(py: Python<'_>, g: &Bound<'_, PyAny>, path: &Bound<'_, PyAny>) -> PyResult<()> {
    let gr = extract_graph(g)?;
    let graph = gr.undirected();
    let mut engine = EdgeListEngine::hardened();
    let content = py
        .allow_threads(|| engine.write_adjlist(graph))
        .map_err(rw_error_to_py)?;
    write_output(py, path, &content)
}

// ---------------------------------------------------------------------------
// JSON graph (node_link format)
// ---------------------------------------------------------------------------

#[pyfunction]
#[pyo3(signature = (g,))]
fn node_link_data(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<PyObject> {
    let gr = extract_graph(g)?;
    let graph = gr.undirected();
    let mut engine = EdgeListEngine::hardened();
    let json_str = py
        .allow_threads(|| engine.write_json_graph(graph))
        .map_err(rw_error_to_py)?;
    let json_mod = py.import("json")?;
    let result = json_mod.call_method1("loads", (json_str,))?;
    Ok(result.unbind())
}

#[pyfunction]
#[pyo3(signature = (data,))]
fn node_link_graph(py: Python<'_>, data: &Bound<'_, PyAny>) -> PyResult<PyGraph> {
    let json_mod = py.import("json")?;
    let json_str: String = json_mod.call_method1("dumps", (data,))?.extract()?;
    let mut engine = EdgeListEngine::hardened();
    let report = py
        .allow_threads(|| engine.read_json_graph(&json_str))
        .map_err(rw_error_to_py)?;
    report_to_pygraph(py, report)
}

// ---------------------------------------------------------------------------
// GraphML
// ---------------------------------------------------------------------------

#[pyfunction]
#[pyo3(signature = (path,))]
fn read_graphml(py: Python<'_>, path: &Bound<'_, PyAny>) -> PyResult<PyGraph> {
    let input = read_input(py, path)?;
    let mut engine = EdgeListEngine::hardened();
    let report = py
        .allow_threads(|| engine.read_graphml(&input))
        .map_err(rw_error_to_py)?;
    report_to_pygraph(py, report)
}

#[pyfunction]
#[pyo3(signature = (g, path))]
fn write_graphml(py: Python<'_>, g: &Bound<'_, PyAny>, path: &Bound<'_, PyAny>) -> PyResult<()> {
    let gr = extract_graph(g)?;
    let graph = gr.undirected();
    let mut engine = EdgeListEngine::hardened();
    let content = py
        .allow_threads(|| engine.write_graphml(graph))
        .map_err(rw_error_to_py)?;
    write_output(py, path, &content)
}

// ---------------------------------------------------------------------------
// Registration
// ---------------------------------------------------------------------------

pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(read_edgelist, m)?)?;
    m.add_function(wrap_pyfunction!(write_edgelist, m)?)?;
    m.add_function(wrap_pyfunction!(read_adjlist, m)?)?;
    m.add_function(wrap_pyfunction!(write_adjlist, m)?)?;
    m.add_function(wrap_pyfunction!(node_link_data, m)?)?;
    m.add_function(wrap_pyfunction!(node_link_graph, m)?)?;
    m.add_function(wrap_pyfunction!(read_graphml, m)?)?;
    m.add_function(wrap_pyfunction!(write_graphml, m)?)?;
    Ok(())
}
