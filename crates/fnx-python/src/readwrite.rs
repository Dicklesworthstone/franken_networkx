//! Python bindings for graph I/O functions.
//!
//! Each read function accepts a file path (str or os.PathLike) or file-like object.
//! Each write function accepts a Graph or DiGraph and a file path or file-like object.
//! Internally delegates to `fnx_readwrite::EdgeListEngine` where the native
//! engine format matches the public NetworkX surface.

use crate::algorithms::{GraphRef, extract_graph};
use crate::digraph::PyDiGraph;
use crate::{
    PyGraph, PyObject, PythonAllowThreadsExt, cgse_value_to_py, node_key_to_string,
    py_dict_to_attr_map,
};
use fnx_classes::Graph as RustGraph;
use fnx_classes::digraph::DiGraph as RustDiGraph;
use fnx_readwrite::{DiReadWriteReport, EdgeListEngine, ReadWriteError, ReadWriteReport};
use pyo3::exceptions::PyRuntimeError;
use pyo3::prelude::*;
use pyo3::types::PyBytes;
use pyo3::types::PyDict;
use pyo3::types::PyList;
use serde_json::Value as JsonValue;
use std::collections::HashMap;
use std::sync::atomic::AtomicBool;

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

/// Write UTF-8 content to a binary-oriented Python destination.
fn write_output_bytes(py: Python<'_>, dest: &Bound<'_, PyAny>, content: &str) -> PyResult<()> {
    let bytes = PyBytes::new(py, content.as_bytes());
    if let Ok(write_method) = dest.getattr("write") {
        match write_method.call1((bytes,)) {
            Ok(_) => return Ok(()),
            Err(err) if err.is_instance_of::<pyo3::exceptions::PyTypeError>(py) => {
                write_method.call1((content,))?;
                return Ok(());
            }
            Err(err) => return Err(err),
        }
    }
    let pathlib = py.import("pathlib")?;
    let path_cls = pathlib.getattr("Path")?;
    let path = path_cls.call1((dest,))?;
    path.call_method1("write_bytes", (bytes,))?;
    Ok(())
}

/// Convert a `ReadWriteReport` into a `PyGraph`.
fn report_to_pygraph(py: Python<'_>, report: ReadWriteReport) -> PyResult<PyGraph> {
    let graph_attrs = report.graph_attrs;
    let g = report.graph;
    let mut inner = RustGraph::new(g.mode());
    let mut raw_to_canonical = HashMap::new();
    let mut node_key_map = HashMap::new();
    let mut node_py_attrs = HashMap::new();
    for node_id in g.nodes_ordered() {
        let py_key = node_id.to_owned().into_pyobject(py)?.into_any().unbind();
        let canonical = node_key_to_string(py, py_key.bind(py))?;
        raw_to_canonical.insert(node_id.to_owned(), canonical.clone());
        node_key_map.insert(canonical.clone(), py_key);
        let d = PyDict::new(py);
        let attrs = g.node_attrs(node_id).cloned().unwrap_or_default();
        for (k, v) in &attrs {
            d.set_item(k, crate::cgse_value_to_py(py, v)?)?;
        }
        inner.add_node_with_attrs(canonical.clone(), attrs);
        node_py_attrs.insert(canonical, d.unbind());
    }

    let mut edge_py_attrs = HashMap::new();
    for es in g.edges_ordered() {
        let left = raw_to_canonical
            .get(&es.left)
            .cloned()
            .unwrap_or_else(|| es.left.clone());
        let right = raw_to_canonical
            .get(&es.right)
            .cloned()
            .unwrap_or_else(|| es.right.clone());
        inner
            .add_edge_with_attrs(left.clone(), right.clone(), es.attrs.clone())
            .map_err(|err| PyRuntimeError::new_err(format!("failed to import edge: {err}")))?;
        let key = PyGraph::edge_key(&left, &right);
        let d = PyDict::new(py);
        for (k, v) in &es.attrs {
            d.set_item(k, crate::cgse_value_to_py(py, v)?)?;
        }
        edge_py_attrs.insert(key, d.unbind());
    }

    let py_graph_attrs = PyDict::new(py);
    for (k, v) in &graph_attrs {
        py_graph_attrs.set_item(k, crate::cgse_value_to_py(py, v)?)?;
    }

    Ok(PyGraph {
        inner,
        node_key_map,
        node_py_attrs,
        edge_py_attrs,
        graph_attrs: py_graph_attrs.unbind(),
        nodes_seq: 0,
        edges_seq: 0,
        edges_dirty: AtomicBool::new(false),
    })
}

/// Convert a `DiReadWriteReport` into a `PyDiGraph`.
fn di_report_to_pydigraph(py: Python<'_>, report: DiReadWriteReport) -> PyResult<PyDiGraph> {
    let graph_attrs = report.graph_attrs;
    let g = report.graph;
    let mut inner = RustDiGraph::new(g.mode());
    let mut raw_to_canonical = HashMap::new();
    let mut node_key_map = HashMap::new();
    let mut node_py_attrs = HashMap::new();
    for node_id in g.nodes_ordered() {
        let py_key = node_id.to_owned().into_pyobject(py)?.into_any().unbind();
        let canonical = node_key_to_string(py, py_key.bind(py))?;
        raw_to_canonical.insert(node_id.to_owned(), canonical.clone());
        node_key_map.insert(canonical.clone(), py_key);
        let d = PyDict::new(py);
        let attrs = g.node_attrs(node_id).cloned().unwrap_or_default();
        for (k, v) in &attrs {
            d.set_item(k, crate::cgse_value_to_py(py, v)?)?;
        }
        inner.add_node_with_attrs(canonical.clone(), attrs);
        node_py_attrs.insert(canonical, d.unbind());
    }

    let mut edge_py_attrs = HashMap::new();
    for es in g.edges_ordered() {
        let left = raw_to_canonical
            .get(&es.left)
            .cloned()
            .unwrap_or_else(|| es.left.clone());
        let right = raw_to_canonical
            .get(&es.right)
            .cloned()
            .unwrap_or_else(|| es.right.clone());
        inner
            .add_edge_with_attrs(left.clone(), right.clone(), es.attrs.clone())
            .map_err(|err| PyRuntimeError::new_err(format!("failed to import edge: {err}")))?;
        let key = PyDiGraph::edge_key(&left, &right);
        let d = PyDict::new(py);
        for (k, v) in &es.attrs {
            d.set_item(k, crate::cgse_value_to_py(py, v)?)?;
        }
        edge_py_attrs.insert(key, d.unbind());
    }

    let py_graph_attrs = PyDict::new(py);
    for (k, v) in &graph_attrs {
        py_graph_attrs.set_item(k, crate::cgse_value_to_py(py, v)?)?;
    }

    Ok(PyDiGraph {
        inner,
        node_key_map,
        node_py_attrs,
        edge_py_attrs,
        graph_attrs: py_graph_attrs.unbind(),
        nodes_seq: 0,
        edges_seq: 0,
        edges_dirty: AtomicBool::new(false),
    })
}

fn rw_error_to_py(e: fnx_readwrite::ReadWriteError) -> PyErr {
    pyo3::exceptions::PyIOError::new_err(format!("{e}"))
}

#[derive(Debug)]
pub enum RawNodeLinkReport {
    Undirected(ReadWriteReport),
    Directed(DiReadWriteReport),
}

#[derive(Debug)]
pub enum RawNodeLinkError {
    InvalidFlagType(&'static str),
    MultigraphUnsupported,
    ReadWrite(ReadWriteError),
}

impl From<ReadWriteError> for RawNodeLinkError {
    fn from(value: ReadWriteError) -> Self {
        Self::ReadWrite(value)
    }
}

fn raw_node_link_flag(
    object: &serde_json::Map<String, JsonValue>,
    key: &'static str,
) -> Result<Option<bool>, RawNodeLinkError> {
    match object.get(key) {
        None => Ok(None),
        Some(JsonValue::Bool(value)) => Ok(Some(*value)),
        Some(_) => Err(RawNodeLinkError::InvalidFlagType(key)),
    }
}

pub fn parse_raw_node_link_json(input: &str) -> Result<RawNodeLinkReport, RawNodeLinkError> {
    let parsed = match serde_json::from_str::<JsonValue>(input) {
        Ok(value) => value,
        Err(_) => {
            let mut engine = EdgeListEngine::hardened();
            return engine
                .read_json_graph(input)
                .map(RawNodeLinkReport::Undirected)
                .map_err(RawNodeLinkError::from);
        }
    };

    let Some(object) = parsed.as_object() else {
        let mut engine = EdgeListEngine::hardened();
        return engine
            .read_json_graph(input)
            .map(RawNodeLinkReport::Undirected)
            .map_err(RawNodeLinkError::from);
    };

    if raw_node_link_flag(object, "multigraph")? == Some(true) {
        return Err(RawNodeLinkError::MultigraphUnsupported);
    }

    let directed = raw_node_link_flag(object, "directed")?.unwrap_or(false);
    let mut engine = EdgeListEngine::hardened();
    if directed {
        engine
            .read_digraph_json_graph(input)
            .map(RawNodeLinkReport::Directed)
            .map_err(RawNodeLinkError::from)
    } else {
        engine
            .read_json_graph(input)
            .map(RawNodeLinkReport::Undirected)
            .map_err(RawNodeLinkError::from)
    }
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

fn reject_multigraph_write(gr: &GraphRef<'_>, operation: &str) -> PyResult<()> {
    match gr {
        GraphRef::MultiUndirected { .. } | GraphRef::MultiDirected { .. } => {
            Err(pyo3::exceptions::PyTypeError::new_err(format!(
                "{operation} does not support MultiGraph or MultiDiGraph without losing parallel edges"
            )))
        }
        _ => Ok(()),
    }
}

fn edge_attr_dict_repr(py: Python<'_>, attrs: &fnx_classes::AttrMap) -> PyResult<String> {
    if attrs.is_empty() {
        return Ok("{}".to_owned());
    }

    let dict = PyDict::new(py);
    for (key, value) in attrs {
        dict.set_item(key, cgse_value_to_py(py, value)?)?;
    }
    dict.repr()?.extract()
}

fn graph_networkx_edgelist(py: Python<'_>, graph: &fnx_classes::Graph) -> PyResult<String> {
    let mut content = String::new();
    for (left, right, attrs) in graph.edges_ordered_borrowed() {
        content.push_str(left);
        content.push(' ');
        content.push_str(right);
        content.push(' ');
        content.push_str(&edge_attr_dict_repr(py, attrs)?);
        content.push('\n');
    }
    Ok(content)
}

fn digraph_networkx_edgelist(
    py: Python<'_>,
    graph: &fnx_classes::digraph::DiGraph,
) -> PyResult<String> {
    let mut content = String::new();
    for (source, target, attrs) in graph.edges_ordered_borrowed() {
        content.push_str(source);
        content.push(' ');
        content.push_str(target);
        content.push(' ');
        content.push_str(&edge_attr_dict_repr(py, attrs)?);
        content.push('\n');
    }
    Ok(content)
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
    reject_multigraph_write(&gr, "write_edgelist")?;
    let content = match &gr {
        GraphRef::Undirected(pg) => graph_networkx_edgelist(py, &pg.inner)?,
        GraphRef::Directed { dg, .. } => digraph_networkx_edgelist(py, &dg.inner)?,
        _ => {
            if gr.is_directed() {
                let inner = gr.digraph().ok_or_else(|| {
                    pyo3::exceptions::PyTypeError::new_err(
                        "expected directed graph backend for directed graph value",
                    )
                })?;
                digraph_networkx_edgelist(py, inner)?
            } else {
                let inner = gr.undirected();
                graph_networkx_edgelist(py, inner)?
            }
        }
    };
    write_output_bytes(py, path, &content)
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
#[pyo3(signature = (g, path, comments="#", delimiter=" ", encoding="utf-8"))]
fn write_adjlist(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    path: &Bound<'_, PyAny>,
    comments: &str,
    delimiter: &str,
    encoding: &str,
) -> PyResult<()> {
    if comments != "#" || delimiter != " " || encoding != "utf-8" {
        return Err(crate::NetworkXNotImplemented::new_err(
            "franken_networkx currently only supports default parameters for write_adjlist",
        ));
    }
    let gr = extract_graph(g)?;
    reject_multigraph_write(&gr, "write_adjlist")?;
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
    reject_multigraph_write(&gr, "node_link_data")?;
    let graph_attrs = graph_ref_attrs(&gr, py)?;
    let mut engine = EdgeListEngine::hardened();
    let json_str = match &gr {
        GraphRef::Undirected(pg) => {
            let inner = &pg.inner;
            py.allow_threads(|| engine.write_json_graph_with_graph_attrs(inner, &graph_attrs))
                .map_err(rw_error_to_py)?
        }
        GraphRef::Directed { dg, .. } => {
            let inner = &dg.inner;
            py.allow_threads(|| {
                engine.write_digraph_json_graph_with_graph_attrs(inner, &graph_attrs)
            })
            .map_err(rw_error_to_py)?
        }
        _ => {
            if gr.is_directed() {
                let inner = gr.digraph().ok_or_else(|| {
                    pyo3::exceptions::PyTypeError::new_err(
                        "expected directed graph backend for directed graph value",
                    )
                })?;
                py.allow_threads(|| {
                    engine.write_digraph_json_graph_with_graph_attrs(inner, &graph_attrs)
                })
                .map_err(rw_error_to_py)?
            } else {
                let inner = gr.undirected();
                py.allow_threads(|| engine.write_json_graph_with_graph_attrs(inner, &graph_attrs))
                    .map_err(rw_error_to_py)?
            }
        }
    };
    let json_mod = py.import("json")?;
    let result = json_mod.call_method1("loads", (json_str,))?;
    Ok(result.unbind())
}

#[pyfunction]
#[pyo3(signature = (data, directed=false, multigraph=true, attrs=None, source="source", target="target", name="id", key="key", link="links"))]
#[allow(unused_variables)]
fn node_link_graph(
    py: Python<'_>,
    data: &Bound<'_, PyAny>,
    directed: bool,
    multigraph: bool,
    attrs: Option<Bound<'_, PyAny>>,
    source: &str,
    target: &str,
    name: &str,
    key: &str,
    link: &str,
) -> PyResult<PyObject> {
    if attrs.is_some()
        || source != "source"
        || target != "target"
        || name != "id"
        || key != "key"
        || link != "links"
    {
        return Err(crate::NetworkXNotImplemented::new_err(
            "franken_networkx currently only supports default parameters for node_link_graph",
        ));
    }
    let json_mod = py.import("json")?;
    let json_str: String = json_mod.call_method1("dumps", (data,))?.extract()?;
    match parse_raw_node_link_json(&json_str) {
        Ok(RawNodeLinkReport::Directed(report)) => Ok(di_report_to_pydigraph(py, report)?
            .into_pyobject(py)?
            .into_any()
            .unbind()),
        Ok(RawNodeLinkReport::Undirected(report)) => Ok(report_to_pygraph(py, report)?
            .into_pyobject(py)?
            .into_any()
            .unbind()),
        Err(RawNodeLinkError::InvalidFlagType(key)) => Err(pyo3::exceptions::PyTypeError::new_err(
            format!("node_link_graph expected `{key}` to be a bool when present"),
        )),
        Err(RawNodeLinkError::MultigraphUnsupported) => {
            Err(pyo3::exceptions::PyTypeError::new_err(
                "node_link_graph does not support multigraph payloads without losing parallel edges",
            ))
        }
        Err(RawNodeLinkError::ReadWrite(err)) => Err(rw_error_to_py(err)),
    }
}

// ---------------------------------------------------------------------------
// GraphML
// ---------------------------------------------------------------------------

#[pyfunction]
#[pyo3(signature = (path,))]
fn read_graphml(py: Python<'_>, path: &Bound<'_, PyAny>) -> PyResult<PyObject> {
    let input = read_input(py, path)?;
    let mut engine = EdgeListEngine::hardened();

    if py
        .allow_threads(|| engine.graphml_declares_directed(&input))
        .map_err(rw_error_to_py)?
    {
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
    reject_multigraph_write(&gr, "write_graphml")?;
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
                py.allow_threads(|| {
                    engine.write_digraph_graphml_with_graph_attrs(inner, &graph_attrs)
                })
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
// GEXF
// ---------------------------------------------------------------------------

#[pyfunction]
#[pyo3(signature = (path,))]
fn read_gexf(py: Python<'_>, path: &Bound<'_, PyAny>) -> PyResult<PyObject> {
    let input = read_input(py, path)?;
    let mut engine = EdgeListEngine::hardened();

    if py
        .allow_threads(|| engine.gexf_declares_directed(&input))
        .map_err(rw_error_to_py)?
    {
        let report = py
            .allow_threads(|| engine.read_digraph_gexf(&input))
            .map_err(rw_error_to_py)?;
        Ok(di_report_to_pydigraph(py, report)?
            .into_pyobject(py)?
            .into_any()
            .unbind())
    } else {
        let report = py
            .allow_threads(|| engine.read_gexf(&input))
            .map_err(rw_error_to_py)?;
        Ok(report_to_pygraph(py, report)?
            .into_pyobject(py)?
            .into_any()
            .unbind())
    }
}

fn write_gexf_content(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<String> {
    let gr = extract_graph(g)?;
    reject_multigraph_write(&gr, "write_gexf")?;
    let graph_attrs = graph_ref_attrs(&gr, py)?;
    let mut engine = EdgeListEngine::hardened();
    match &gr {
        GraphRef::Undirected(pg) => {
            let inner = &pg.inner;
            py.allow_threads(|| engine.write_gexf_with_graph_attrs(inner, &graph_attrs))
                .map_err(rw_error_to_py)
        }
        GraphRef::Directed { dg, .. } => {
            let inner = &dg.inner;
            py.allow_threads(|| engine.write_digraph_gexf_with_graph_attrs(inner, &graph_attrs))
                .map_err(rw_error_to_py)
        }
        _ => {
            if gr.is_directed() {
                let inner = gr.digraph().ok_or_else(|| {
                    pyo3::exceptions::PyTypeError::new_err("expected directed graph")
                })?;
                py.allow_threads(|| engine.write_digraph_gexf_with_graph_attrs(inner, &graph_attrs))
                    .map_err(rw_error_to_py)
            } else {
                let inner = gr.undirected();
                py.allow_threads(|| engine.write_gexf_with_graph_attrs(inner, &graph_attrs))
                    .map_err(rw_error_to_py)
            }
        }
    }
}

#[pyfunction]
#[pyo3(signature = (g, path))]
fn write_gexf(py: Python<'_>, g: &Bound<'_, PyAny>, path: &Bound<'_, PyAny>) -> PyResult<()> {
    let content = write_gexf_content(py, g)?;
    write_output(py, path, &content)
}

#[pyfunction]
#[pyo3(signature = (g,))]
fn write_gexf_string_rust(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<String> {
    write_gexf_content(py, g)
}

// ---------------------------------------------------------------------------
// GML
// ---------------------------------------------------------------------------

#[pyfunction]
#[pyo3(signature = (path, label="label", destringizer=None))]
fn read_gml(
    py: Python<'_>,
    path: &Bound<'_, PyAny>,
    label: Option<&str>,
    destringizer: Option<Bound<'_, PyAny>>,
) -> PyResult<PyObject> {
    if label != Some("label") || destringizer.is_some() {
        return Err(crate::NetworkXNotImplemented::new_err(
            "franken_networkx currently only supports default parameters for read_gml",
        ));
    }
    let input = read_input(py, path)?;
    // br-readgml-strict: nx raises NetworkXError on duplicate node ids,
    // unclosed brackets, and stray ']' tokens. Hardened mode silently
    // recovers from those, which diverges from nx parity for drop-in
    // users. Use strict mode at the Python boundary so the contract
    // matches nx; the underlying hardened-mode behavior remains
    // available to direct Rust callers.
    let mut engine = EdgeListEngine::strict();

    if py
        .allow_threads(|| engine.gml_declares_directed(&input))
        .map_err(rw_error_to_py)?
    {
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
    reject_multigraph_write(&gr, "write_gml")?;
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
    write_output_bytes(py, path, &content)
}

// ---------------------------------------------------------------------------
// Registration
// ---------------------------------------------------------------------------

/// br-r37-c1-yl59j/br-r37-c1-nocb2: native fast path for `to_dict_of_dicts`
/// on simple `Graph` and `DiGraph`. Builds `{u: {v: edge_attr_dict}}` reusing
/// the LIVE edge attribute dict objects (the same `Py<PyDict>` references
/// returned by `G[u][v]`) in adjacency order, bypassing the slow per-access
/// AdjacencyView Python machinery.
///
/// Returns `None` for multigraph inputs so the Python wrapper falls back to its
/// general implementation; the wrapper also gates on exact graph type so
/// filtered SubgraphViews / subclasses never reach here.
#[pyfunction]
pub fn to_dict_of_dicts_undirected(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
) -> PyResult<Option<Py<PyDict>>> {
    let gr = extract_graph(g)?;
    let outer = PyDict::new(py);
    match &gr {
        GraphRef::Undirected(pg) => {
            for u in pg.inner.nodes_ordered() {
                let inner_dict = PyDict::new(py);
                if let Some(neighbors) = pg.inner.neighbors_iter(u) {
                    for v in neighbors {
                        let ek = PyGraph::edge_key(u, v);
                        let edge_dict = pg
                            .edge_py_attrs
                            .get(&ek)
                            .map_or_else(|| PyDict::new(py).unbind(), |d| d.clone_ref(py));
                        inner_dict.set_item(pg.py_node_key(py, v), edge_dict.bind(py))?;
                    }
                }
                outer.set_item(pg.py_node_key(py, u), inner_dict)?;
            }
        }
        GraphRef::Directed { dg, .. } => {
            for u in dg.inner.nodes_ordered() {
                let inner_dict = PyDict::new(py);
                if let Some(neighbors) = dg.inner.successors_iter(u) {
                    for v in neighbors {
                        let ek = PyDiGraph::edge_key(u, v);
                        let edge_dict = dg
                            .edge_py_attrs
                            .get(&ek)
                            .map_or_else(|| PyDict::new(py).unbind(), |d| d.clone_ref(py));
                        inner_dict.set_item(dg.py_node_key(py, v), edge_dict.bind(py))?;
                    }
                }
                outer.set_item(dg.py_node_key(py, u), inner_dict)?;
            }
        }
        GraphRef::MultiUndirected { .. } | GraphRef::MultiDirected { .. } => return Ok(None),
    }
    Ok(Some(outer.unbind()))
}

/// br-r37-c1-6o3wi/br-r37-c1-nocb2: native fast path for `to_dict_of_lists`
/// on simple `Graph` and `DiGraph` with no nodelist. Builds `{u: [v, ...]}`
/// with each neighbor list in adjacency/successor order, bypassing the slow
/// per-node `G.neighbors(n)` wrapper iteration. Returns `None` for multigraph
/// inputs; the Python wrapper also gates on exact type so subclasses / filtered
/// SubgraphViews fall back.
#[pyfunction]
pub fn to_dict_of_lists_undirected(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
) -> PyResult<Option<Py<PyDict>>> {
    let gr = extract_graph(g)?;
    let outer = PyDict::new(py);
    match &gr {
        GraphRef::Undirected(pg) => {
            for u in pg.inner.nodes_ordered() {
                let neighbors = PyList::empty(py);
                if let Some(nbrs) = pg.inner.neighbors_iter(u) {
                    for v in nbrs {
                        neighbors.append(pg.py_node_key(py, v))?;
                    }
                }
                outer.set_item(pg.py_node_key(py, u), neighbors)?;
            }
        }
        GraphRef::Directed { dg, .. } => {
            for u in dg.inner.nodes_ordered() {
                let neighbors = PyList::empty(py);
                if let Some(nbrs) = dg.inner.successors_iter(u) {
                    for v in nbrs {
                        neighbors.append(dg.py_node_key(py, v))?;
                    }
                }
                outer.set_item(dg.py_node_key(py, u), neighbors)?;
            }
        }
        GraphRef::MultiUndirected { .. } | GraphRef::MultiDirected { .. } => return Ok(None),
    }
    Ok(Some(outer.unbind()))
}

/// br-r37-c1-gl3nq: native fast path for `to_edgelist` on exact simple
/// `Graph` and `DiGraph` with no nodelist. It preserves the existing fnx
/// materialized list-like return behavior while avoiding Python adjacency
/// wrapper traversal for every edge.
#[pyfunction]
pub fn to_edgelist_simple(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<Option<Py<PyList>>> {
    let gr = extract_graph(g)?;
    let result = PyList::empty(py);
    match &gr {
        GraphRef::Undirected(pg) => {
            for edge in pg.inner.edges_ordered() {
                let u = edge.left.as_str();
                let v = edge.right.as_str();
                let ek = PyGraph::edge_key(u, v);
                let attrs = pg
                    .edge_py_attrs
                    .get(&ek)
                    .map_or_else(|| PyDict::new(py).unbind(), |d| d.clone_ref(py));
                result.append((pg.py_node_key(py, u), pg.py_node_key(py, v), attrs))?;
            }
        }
        GraphRef::Directed { dg, .. } => {
            for edge in dg.inner.edges_ordered() {
                let u = edge.left.as_str();
                let v = edge.right.as_str();
                let ek = PyDiGraph::edge_key(u, v);
                let attrs = dg
                    .edge_py_attrs
                    .get(&ek)
                    .map_or_else(|| PyDict::new(py).unbind(), |d| d.clone_ref(py));
                result.append((dg.py_node_key(py, u), dg.py_node_key(py, v), attrs))?;
            }
        }
        GraphRef::MultiUndirected { .. } | GraphRef::MultiDirected { .. } => return Ok(None),
    }
    Ok(Some(result.unbind()))
}

/// br-r37-c1-fwdense: cache-friendly in-place min-plus Floyd-Warshall over a
/// flat row-major distance matrix (`dist` is `n*n`, `dist[u*n+v]`).
///
/// Bit-identical to the standard k-outer FW and to numpy's broadcast variant
/// (`for k: A = minimum(A, A[k,:] + A[:,k])`): for each pivot `k` we snapshot
/// row `k` — invariant during the k-iteration because `dist[k][k]==0` (so the
/// self-updates to row k and column k are no-ops) — then apply
/// `dist[u][v] = min(dist[u][v], dist[u][k] + row_k[v])` over contiguous rows.
/// The snapshot removes the read/write alias between the pivot row and the row
/// being updated, so the inner `v`-loop is a fused min-add over a contiguous
/// slice that auto-vectorizes, and it never allocates the `n` temporary `n*n`
/// arrays numpy's broadcast FW materializes (the dominant cost there). Rows with
/// `dist[u][k] == +inf` are skipped (inf + x is never smaller than the current
/// entry), which is also exact.
fn floyd_warshall_dense_inplace(dist: &mut [f64], n: usize) {
    debug_assert_eq!(dist.len(), n * n);
    let mut row_k = vec![0.0f64; n];
    for k in 0..n {
        row_k.copy_from_slice(&dist[k * n..(k + 1) * n]);
        for u in 0..n {
            let duk = dist[u * n + k];
            if duk == f64::INFINITY {
                continue;
            }
            let row_u = &mut dist[u * n..(u + 1) * n];
            for v in 0..n {
                let cand = duk + row_k[v];
                if cand < row_u[v] {
                    row_u[v] = cand;
                }
            }
        }
    }
}

/// Read an edge's numeric weight from its live Python attr dict, defaulting to
/// 1.0 when the key is absent (matches nx `to_numpy_array`'s `data.get(weight,
/// 1)`); a present-but-non-numeric value raises (as nx would when assembling the
/// float matrix).
fn fw_edge_weight(
    py: Python<'_>,
    attrs: Option<&Py<PyDict>>,
    weight: &str,
) -> PyResult<f64> {
    match attrs {
        Some(d) => match d.bind(py).get_item(weight)? {
            Some(val) => val.extract::<f64>(),
            None => Ok(1.0),
        },
        None => Ok(1.0),
    }
}

/// br-r37-c1-fwdense: native `floyd_warshall_numpy` core for simple Graph /
/// DiGraph with the default nodelist. Builds the dense distance matrix
/// (non-edges = +inf, diagonal = 0, edge weight or default 1.0, min over any
/// parallel edges) in node-insertion order, then runs the in-place SIMD FW.
/// Returns `(n, flat row-major)` which Python reshapes to `(n, n)`. Returns
/// `None` for multigraph inputs so the Python wrapper falls back. Self-loops are
/// dropped (nx forces the diagonal to 0). Bit-identical to nx (see
/// `floyd_warshall_dense_inplace` + nx's `to_numpy_array(nonedge=inf)` +
/// `fill_diagonal(0)`).
#[pyfunction]
pub fn floyd_warshall_dense(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    weight: &str,
) -> PyResult<Option<(usize, Vec<f64>)>> {
    let gr = extract_graph(g)?;
    match &gr {
        GraphRef::Undirected(pg) => {
            let nodes = pg.inner.nodes_ordered();
            let n = nodes.len();
            let mut idx: HashMap<&str, usize> = HashMap::with_capacity(n);
            for (i, &nd) in nodes.iter().enumerate() {
                idx.insert(nd, i);
            }
            let mut dist = vec![f64::INFINITY; n * n];
            for i in 0..n {
                dist[i * n + i] = 0.0;
            }
            for u in pg.inner.nodes_ordered() {
                let iu = idx[u];
                if let Some(nbrs) = pg.inner.neighbors_iter(u) {
                    for v in nbrs {
                        let iv = idx[v];
                        if iu == iv {
                            continue;
                        }
                        let ek = PyGraph::edge_key(u, v);
                        let w = fw_edge_weight(py, pg.edge_py_attrs.get(&ek), weight)?;
                        let cell = &mut dist[iu * n + iv];
                        if w < *cell {
                            *cell = w;
                        }
                    }
                }
            }
            floyd_warshall_dense_inplace(&mut dist, n);
            Ok(Some((n, dist)))
        }
        GraphRef::Directed { dg, .. } => {
            let nodes = dg.inner.nodes_ordered();
            let n = nodes.len();
            let mut idx: HashMap<&str, usize> = HashMap::with_capacity(n);
            for (i, &nd) in nodes.iter().enumerate() {
                idx.insert(nd, i);
            }
            let mut dist = vec![f64::INFINITY; n * n];
            for i in 0..n {
                dist[i * n + i] = 0.0;
            }
            for u in dg.inner.nodes_ordered() {
                let iu = idx[u];
                if let Some(nbrs) = dg.inner.successors_iter(u) {
                    for v in nbrs {
                        let iv = idx[v];
                        if iu == iv {
                            continue;
                        }
                        let ek = PyDiGraph::edge_key(u, v);
                        let w = fw_edge_weight(py, dg.edge_py_attrs.get(&ek), weight)?;
                        let cell = &mut dist[iu * n + iv];
                        if w < *cell {
                            *cell = w;
                        }
                    }
                }
            }
            floyd_warshall_dense_inplace(&mut dist, n);
            Ok(Some((n, dist)))
        }
        GraphRef::MultiUndirected { .. } | GraphRef::MultiDirected { .. } => Ok(None),
    }
}

pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(floyd_warshall_dense, m)?)?;
    m.add_function(wrap_pyfunction!(to_dict_of_dicts_undirected, m)?)?;
    m.add_function(wrap_pyfunction!(to_dict_of_lists_undirected, m)?)?;
    m.add_function(wrap_pyfunction!(to_edgelist_simple, m)?)?;
    m.add_function(wrap_pyfunction!(read_edgelist, m)?)?;
    m.add_function(wrap_pyfunction!(write_edgelist, m)?)?;
    m.add_function(wrap_pyfunction!(read_adjlist, m)?)?;
    m.add_function(wrap_pyfunction!(write_adjlist, m)?)?;
    m.add_function(wrap_pyfunction!(node_link_data, m)?)?;
    m.add_function(wrap_pyfunction!(node_link_graph, m)?)?;
    m.add_function(wrap_pyfunction!(read_graphml, m)?)?;
    m.add_function(wrap_pyfunction!(write_graphml, m)?)?;
    m.add_function(wrap_pyfunction!(read_gexf, m)?)?;
    m.add_function(wrap_pyfunction!(write_gexf, m)?)?;
    m.add_function(wrap_pyfunction!(write_gexf_string_rust, m)?)?;
    m.add_function(wrap_pyfunction!(read_gml, m)?)?;
    m.add_function(wrap_pyfunction!(write_gml, m)?)?;
    Ok(())
}
