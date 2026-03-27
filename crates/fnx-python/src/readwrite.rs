//! Python bindings for graph I/O functions.
//!
//! Each read function accepts a file path (str or os.PathLike) or file-like object.
//! Each write function accepts a Graph or DiGraph and a file path or file-like object.
//! Internally delegates to `fnx_readwrite::EdgeListEngine`.

use crate::algorithms::{GraphRef, extract_graph};
use crate::digraph::{PyDiGraph, PyMultiDiGraph};
use crate::{PyGraph, PyMultiGraph, py_dict_to_attr_map};
use fnx_readwrite::{DiReadWriteReport, EdgeListEngine, ReadWriteReport};
use pyo3::prelude::*;
use pyo3::types::PyBytes;
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
        match write_method.call1((content,)) {
            Ok(_) => return Ok(()),
            Err(err) if err.is_instance_of::<pyo3::exceptions::PyTypeError>(py) => {
                let bytes = PyBytes::new(py, content.as_bytes());
                write_method.call1((bytes,))?;
                return Ok(());
            }
            Err(err) => return Err(err),
        }
    }
    // Otherwise treat as path
    let pathlib = py.import("pathlib")?;
    let path_cls = pathlib.getattr("Path")?;
    let path = path_cls.call1((dest,))?;
    path.call_method1("write_text", (content, "utf-8"))?;
    Ok(())
}

/// Convert a `ReadWriteReport` into a `PyGraph`.
fn report_to_pygraph(py: Python<'_>, report: ReadWriteReport) -> PyResult<PyGraph> {
    let graph_attrs = report.graph_attrs;
    let g = report.graph;
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
                d.set_item(k, crate::cgse_value_to_py(py, v))?;
            }
        }
        node_py_attrs.insert(node_id.to_owned(), d.unbind());
    }

    let mut edge_py_attrs = HashMap::new();
    for es in g.edges_ordered() {
        let key = PyGraph::edge_key(&es.left, &es.right);
        let d = PyDict::new(py);
        if let Some(attrs) = g.edge_attrs(&es.left, &es.right) {
            for (k, v) in attrs {
                d.set_item(k, crate::cgse_value_to_py(py, v))?;
            }
        }
        edge_py_attrs.insert(key, d.unbind());
    }

    let py_graph_attrs = PyDict::new(py);
    for (k, v) in &graph_attrs {
        py_graph_attrs.set_item(k, crate::cgse_value_to_py(py, v))?;
    }

    Ok(PyGraph {
        inner: g,
        node_key_map,
        node_py_attrs,
        edge_py_attrs,
        graph_attrs: py_graph_attrs.unbind(),
    })
}

/// Convert a `DiReadWriteReport` into a `PyDiGraph`.
fn di_report_to_pydigraph(py: Python<'_>, report: DiReadWriteReport) -> PyResult<PyDiGraph> {
    let graph_attrs = report.graph_attrs;
    let g = report.graph;
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
                d.set_item(k, crate::cgse_value_to_py(py, v))?;
            }
        }
        node_py_attrs.insert(node_id.to_owned(), d.unbind());
    }

    let mut edge_py_attrs = HashMap::new();
    for es in g.edges_ordered() {
        let key = PyDiGraph::edge_key(&es.left, &es.right);
        let d = PyDict::new(py);
        if let Some(attrs) = g.edge_attrs(&es.left, &es.right) {
            for (k, v) in attrs {
                d.set_item(k, crate::cgse_value_to_py(py, v))?;
            }
        }
        edge_py_attrs.insert(key, d.unbind());
    }

    let py_graph_attrs = PyDict::new(py);
    for (k, v) in &graph_attrs {
        py_graph_attrs.set_item(k, crate::cgse_value_to_py(py, v))?;
    }

    Ok(PyDiGraph {
        inner: g,
        node_key_map,
        node_py_attrs,
        edge_py_attrs,
        graph_attrs: py_graph_attrs.unbind(),
    })
}

fn rw_error_to_py(e: fnx_readwrite::ReadWriteError) -> PyErr {
    pyo3::exceptions::PyIOError::new_err(format!("{e}"))
}

fn graph_ref_attrs(gr: &GraphRef<'_>, py: Python<'_>) -> PyResult<fnx_classes::AttrMap> {
    let py_attrs = match gr {
        GraphRef::Undirected(pg) => pg.graph_attrs.bind(py),
        GraphRef::Directed { dg, .. } => dg.graph_attrs.bind(py),
        GraphRef::MultiUndirected { mg, .. } => mg.graph_attrs.bind(py),
        GraphRef::MultiDirected { mdg, .. } => mdg.graph_attrs.bind(py),
    };
    py_dict_to_attr_map(py_attrs)
}

// ---------------------------------------------------------------------------
// Edge list
// ---------------------------------------------------------------------------

#[pyfunction]
#[pyo3(signature = (path,))]
fn read_edgelist(py: Python<'_>, path: &Bound<'_, PyAny>) -> PyResult<PyGraph> {
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
    let gr = extract_graph(g)?;
    let mut engine = EdgeListEngine::hardened();
    let content = match &gr {
        GraphRef::Undirected(pg) => {
            let inner = &pg.inner;
            py.allow_threads(|| engine.write_edgelist(inner))
                .map_err(rw_error_to_py)?
        }
        GraphRef::Directed { dg, .. } => {
            let inner = &dg.inner;
            py.allow_threads(|| engine.write_digraph_edgelist(inner))
                .map_err(rw_error_to_py)?
        }
        _ => {
            if gr.is_directed() {
                let inner = gr.digraph().ok_or_else(|| {
                    pyo3::exceptions::PyTypeError::new_err(
                        "expected directed graph backend for directed graph value",
                    )
                })?;
                py.allow_threads(|| engine.write_digraph_edgelist(inner))
                    .map_err(rw_error_to_py)?
            } else {
                let inner = gr.undirected();
                py.allow_threads(|| engine.write_edgelist(inner))
                    .map_err(rw_error_to_py)?
            }
        }
    };
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
    let mut engine = EdgeListEngine::hardened();
    let content = match &gr {
        GraphRef::Undirected(pg) => {
            let inner = &pg.inner;
            py.allow_threads(|| engine.write_adjlist(inner))
                .map_err(rw_error_to_py)?
        }
        GraphRef::Directed { dg, .. } => {
            let inner = &dg.inner;
            py.allow_threads(|| engine.write_digraph_adjlist(inner))
                .map_err(rw_error_to_py)?
        }
        _ => {
            if gr.is_directed() {
                let inner = gr.digraph().ok_or_else(|| {
                    pyo3::exceptions::PyTypeError::new_err(
                        "expected directed graph backend for directed graph value",
                    )
                })?;
                py.allow_threads(|| engine.write_digraph_adjlist(inner))
                    .map_err(rw_error_to_py)?
            } else {
                let inner = gr.undirected();
                py.allow_threads(|| engine.write_adjlist(inner))
                    .map_err(rw_error_to_py)?
            }
        }
    };
    write_output(py, path, &content)
}

// ---------------------------------------------------------------------------
// JSON graph (node_link format)
// ---------------------------------------------------------------------------

#[pyfunction]
#[pyo3(signature = (g,))]
fn node_link_data(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<PyObject> {
    let gr = extract_graph(g)?;
    let mut engine = EdgeListEngine::hardened();
    let json_str = match &gr {
        GraphRef::Undirected(pg) => {
            let inner = &pg.inner;
            py.allow_threads(|| engine.write_json_graph(inner))
                .map_err(rw_error_to_py)?
        }
        GraphRef::Directed { dg, .. } => {
            let inner = &dg.inner;
            py.allow_threads(|| engine.write_digraph_json_graph(inner))
                .map_err(rw_error_to_py)?
        }
        _ => {
            if gr.is_directed() {
                let inner = gr.digraph().ok_or_else(|| {
                    pyo3::exceptions::PyTypeError::new_err(
                        "expected directed graph backend for directed graph value",
                    )
                })?;
                py.allow_threads(|| engine.write_digraph_json_graph(inner))
                    .map_err(rw_error_to_py)?
            } else {
                let inner = gr.undirected();
                py.allow_threads(|| engine.write_json_graph(inner))
                    .map_err(rw_error_to_py)?
            }
        }
    };
    let json_mod = py.import("json")?;
    let result = json_mod.call_method1("loads", (json_str,))?;
    Ok(result.unbind())
}

#[pyfunction]
#[pyo3(signature = (data,))]
fn node_link_graph(py: Python<'_>, data: &Bound<'_, PyAny>) -> PyResult<PyObject> {
    let json_mod = py.import("json")?;
    let json_str: String = json_mod.call_method1("dumps", (data,))?.extract()?;
    let mut engine = EdgeListEngine::hardened();

    let report = engine.read_json_graph(&json_str).map_err(rw_error_to_py)?;
    Ok(report_to_pygraph(py, report)?
        .into_pyobject(py)?
        .into_any()
        .unbind())
}

// ---------------------------------------------------------------------------
// GraphML
// ---------------------------------------------------------------------------

#[pyfunction]
#[pyo3(signature = (path,))]
fn read_graphml(py: Python<'_>, path: &Bound<'_, PyAny>) -> PyResult<PyObject> {
    let input = read_input(py, path)?;
    let mut engine = EdgeListEngine::hardened();

    // Check if input says it's directed.
    if input.contains("edgedefault=\"directed\"") {
        let report = py
            .allow_threads(|| engine.read_digraph_graphml(&input))
            .map_err(rw_error_to_py)?;
        Ok(di_report_to_pydigraph(py, report)?
            .into_pyobject(py)?
            .into_any()
            .unbind())
    } else {
        let report = py
            .allow_threads(|| engine.read_graphml(&input))
            .map_err(rw_error_to_py)?;
        Ok(report_to_pygraph(py, report)?
            .into_pyobject(py)?
            .into_any()
            .unbind())
    }
}

#[pyfunction]
#[pyo3(signature = (g, path))]
fn write_graphml(py: Python<'_>, g: &Bound<'_, PyAny>, path: &Bound<'_, PyAny>) -> PyResult<()> {
    let gr = extract_graph(g)?;
    let graph_attrs = graph_ref_attrs(&gr, py)?;
    let mut engine = EdgeListEngine::hardened();
    let content = match &gr {
        GraphRef::Undirected(pg) => {
            let inner = &pg.inner;
            py.allow_threads(|| engine.write_graphml_with_graph_attrs(inner, &graph_attrs))
                .map_err(rw_error_to_py)?
        }
        GraphRef::Directed { dg, .. } => {
            let inner = &dg.inner;
            py.allow_threads(|| engine.write_digraph_graphml_with_graph_attrs(inner, &graph_attrs))
                .map_err(rw_error_to_py)?
        }
        _ => {
            if gr.is_directed() {
                let inner = gr.digraph().ok_or_else(|| {
                    pyo3::exceptions::PyTypeError::new_err(
                        "expected directed graph backend for directed graph value",
                    )
                })?;
                py.allow_threads(|| engine.write_digraph_graphml_with_graph_attrs(inner, &graph_attrs))
                    .map_err(rw_error_to_py)?
            } else {
                let inner = gr.undirected();
                py.allow_threads(|| engine.write_graphml_with_graph_attrs(inner, &graph_attrs))
                    .map_err(rw_error_to_py)?
            }
        }
    };
    write_output(py, path, &content)
}

// ---------------------------------------------------------------------------
// GML
// ---------------------------------------------------------------------------

#[pyfunction]
#[pyo3(signature = (path,))]
fn read_gml(py: Python<'_>, path: &Bound<'_, PyAny>) -> PyResult<PyObject> {
    let input = read_input(py, path)?;
    let mut engine = EdgeListEngine::hardened();

    // Auto-detect directed from content
    if input.contains("directed 1") {
        let report = py
            .allow_threads(|| engine.read_digraph_gml(&input))
            .map_err(rw_error_to_py)?;
        Ok(di_report_to_pydigraph(py, report)?
            .into_pyobject(py)?
            .into_any()
            .unbind())
    } else {
        let report = py
            .allow_threads(|| engine.read_gml(&input))
            .map_err(rw_error_to_py)?;
        Ok(report_to_pygraph(py, report)?
            .into_pyobject(py)?
            .into_any()
            .unbind())
    }
}

#[pyfunction]
#[pyo3(signature = (g, path))]
fn write_gml(py: Python<'_>, g: &Bound<'_, PyAny>, path: &Bound<'_, PyAny>) -> PyResult<()> {
    let gr = extract_graph(g)?;
    let graph_attrs = graph_ref_attrs(&gr, py)?;
    let mut engine = EdgeListEngine::hardened();
    let content = match &gr {
        GraphRef::Undirected(pg) => {
            let inner = &pg.inner;
            py.allow_threads(|| engine.write_gml_with_graph_attrs(inner, &graph_attrs))
                .map_err(rw_error_to_py)?
        }
        GraphRef::Directed { dg, .. } => {
            let inner = &dg.inner;
            py.allow_threads(|| engine.write_digraph_gml_with_graph_attrs(inner, &graph_attrs))
                .map_err(rw_error_to_py)?
        }
        _ => {
            if gr.is_directed() {
                let inner = gr.digraph().ok_or_else(|| {
                    pyo3::exceptions::PyTypeError::new_err("expected directed graph")
                })?;
                py.allow_threads(|| engine.write_digraph_gml_with_graph_attrs(inner, &graph_attrs))
                    .map_err(rw_error_to_py)?
            } else {
                let inner = gr.undirected();
                py.allow_threads(|| engine.write_gml_with_graph_attrs(inner, &graph_attrs))
                    .map_err(rw_error_to_py)?
            }
        }
    };
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
    m.add_function(wrap_pyfunction!(read_gml, m)?)?;
    m.add_function(wrap_pyfunction!(write_gml, m)?)?;
    Ok(())
}
