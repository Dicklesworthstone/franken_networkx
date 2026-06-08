//! Python bindings for graph I/O functions.
//!
//! Each read function accepts a file path (str or os.PathLike) or file-like object.
//! Each write function accepts a Graph or DiGraph and a file path or file-like object.
//! Internally delegates to `fnx_readwrite::EdgeListEngine` where the native
//! engine format matches the public NetworkX surface.

use crate::algorithms::{GraphRef, extract_graph};
use crate::digraph::PyDiGraph;
use crate::{
    DictOfDictsCache, PyGraph, PyObject, PythonAllowThreadsExt, cgse_value_to_py,
    node_key_to_string, py_dict_to_attr_map,
};
use fnx_classes::Graph as RustGraph;
use fnx_classes::digraph::DiGraph as RustDiGraph;
use fnx_readwrite::{DiReadWriteReport, EdgeListEngine, ReadWriteError, ReadWriteReport};
use fnx_runtime::CompatibilityMode;
use pyo3::exceptions::PyRuntimeError;
use pyo3::prelude::*;
use pyo3::types::PyBytes;
use pyo3::types::PyDict;
use pyo3::types::PyList;
use pyo3::types::PyString;
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
        lazy_int_node_stop: 0,
        node_py_attrs,
        edge_py_attrs,
        adj_py_keys: HashMap::new(), // br-r37-c1-z6uka
        dict_of_dicts_cache: None,
        adj_row_py: HashMap::new(),
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
        succ_py_keys: HashMap::new(), // br-r37-c1-z6uka
        pred_py_keys: HashMap::new(), // br-r37-c1-z6uka
        succ_row_py: HashMap::new(),
        pred_row_py: HashMap::new(),
        graph_attrs: py_graph_attrs.unbind(),
        nodes_seq: 0,
        edges_seq: 0,
        edges_dirty: AtomicBool::new(false),
    })
}

/// br-r37-c1-dgctor: native DiGraph(Graph) copy-constructor body.
///
/// Fills `dg` (a FRESH, empty PyDiGraph — the Python gate enforces
/// emptiness and exact types) with the bidirected shallow copy of `g`,
/// replicating nx's `from_dict_of_dicts(G.adj) + graph.update +
/// add_nodes_from(G.nodes(data=True))` contract exactly:
/// - node order = source node order; edge insertion = adjacency-row walk
///   (u-major, each row in source adj order) — each undirected edge
///   yields BOTH directions naturally since adjacency is symmetric, in
///   nx's exact succ/pred row order (the Python expand loop this replaces
///   emitted u->v,v->u pairs adjacent, which DIVERGED from nx's row
///   order);
/// - copy depth = shallow: fresh per-node / per-edge / graph dicts whose
///   VALUES are shared with the source (probed vs nx);
/// - attrs are derived from the live PyDict MIRRORS (not src.inner,
///   which can lag post-creation mutations until sync);
/// - inner built in Strict mode via the bulk unrecorded paths (one
///   summary ledger record each).
///
/// Returns false (caller falls back to the Python loop) if either object
/// isn't the exact native type or any attr dict carries an
/// "__fnx_incompatible" key (FailClosed contract lives in
/// add_edge_with_attrs). No mutation of `dg` happens before any bail.
#[pyfunction]
fn digraph_absorb_graph_bidirected(
    py: Python<'_>,
    dg: &Bound<'_, PyAny>,
    g: &Bound<'_, PyAny>,
) -> PyResult<bool> {
    let Ok(src) = g.extract::<PyRef<'_, PyGraph>>() else {
        return Ok(false);
    };
    if !src.adj_py_keys.is_empty() {
        // br-r37-c1-z6uka: mixed-display row objects need the per-edge
        // Python path (which records per-row succ/pred objects).
        return Ok(false);
    }

    let gdict = PyDict::new(py);
    gdict.update(src.graph_attrs.bind(py).as_mapping())?;

    let nodes: Vec<String> = src
        .inner
        .nodes_ordered()
        .into_iter()
        .map(str::to_owned)
        .collect();
    let mut node_key_map: HashMap<String, PyObject> = HashMap::with_capacity(nodes.len());
    let mut node_py_attrs: HashMap<String, Py<PyDict>> = HashMap::with_capacity(nodes.len());
    let mut nodes_bulk: Vec<(String, fnx_classes::AttrMap)> = Vec::with_capacity(nodes.len());
    for nid in &nodes {
        node_key_map.insert(nid.clone(), src.py_node_key(py, nid));
        let mirror = PyDict::new(py);
        let mut amap = fnx_classes::AttrMap::new();
        if let Some(d) = src.node_py_attrs.get(nid) {
            let b = d.bind(py);
            if !b.is_empty() {
                mirror.update(b.as_mapping())?;
                amap = py_dict_to_attr_map(b)?;
                if amap.keys().any(|k| k.starts_with("__fnx_incompatible")) {
                    return Ok(false);
                }
            }
        }
        node_py_attrs.insert(nid.clone(), mirror.unbind());
        nodes_bulk.push((nid.clone(), amap));
    }

    let mut edge_py_attrs: HashMap<(String, String), Py<PyDict>> = HashMap::new();
    let mut edges_bulk: Vec<(String, String, fnx_classes::AttrMap)> = Vec::new();
    for u in &nodes {
        let Some(nbrs) = src.inner.neighbors(u) else {
            continue;
        };
        for v in nbrs {
            let mirror = PyDict::new(py);
            let mut amap = fnx_classes::AttrMap::new();
            if let Some(d) = src.edge_py_attrs.get(&PyGraph::edge_key(u, v)) {
                let b = d.bind(py);
                if !b.is_empty() {
                    mirror.update(b.as_mapping())?;
                    amap = py_dict_to_attr_map(b)?;
                    if amap.keys().any(|k| k.starts_with("__fnx_incompatible")) {
                        return Ok(false);
                    }
                }
            }
            edge_py_attrs.insert(PyDiGraph::edge_key(u, v), mirror.unbind());
            edges_bulk.push((u.clone(), (*v).to_owned(), amap));
        }
    }

    // br-r37-c1-ymeml: carry the SOURCE's compatibility mode (the pre-kernel
    // path preserved it via __new__ absorb + clear's with_runtime_policy;
    // the kernel originally hard-coded Strict, silently downgrading
    // DiGraph(hardened_graph)).
    let mut inner = RustDiGraph::new(src.inner.mode());
    let _ = inner.extend_nodes_with_attrs_unrecorded(nodes_bulk);
    let _ = inner.extend_edges_with_attrs_unrecorded(edges_bulk);

    let Ok(mut dst) = dg.extract::<PyRefMut<'_, PyDiGraph>>() else {
        return Ok(false);
    };
    dst.inner = inner;
    dst.node_key_map = node_key_map;
    dst.node_py_attrs = node_py_attrs;
    dst.edge_py_attrs = edge_py_attrs;
    dst.graph_attrs = gdict.unbind();
    dst.bump_nodes_seq();
    dst.bump_edges_seq();
    Ok(true)
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

/// br-r37-c1-770mm: single-pass native fast path for `read_adjlist` with
/// default kwargs (comments="#", delimiter=None, nodetype=None,
/// encoding="utf-8", create_using=None/Graph). Parses the adjacency-list
/// text directly into the FINAL `PyGraph` — no intermediate engine graph,
/// no nx round-trip, no per-edge `_from_nx_graph` rebuild (the tax that
/// made the delegated path ~7.3x slower than nx).
///
/// Parity contract (mirrors `nx.parse_adjlist` line-for-line):
/// - per-line comment strip at the first `#`, then `continue` only when the
///   strip left an empty string (nx checks `len(line)` BEFORE `.strip()`,
///   and an uncommented line always retains its `\n`, so a blank or
///   whitespace-only line reaches `vlist.pop(0)` and raises IndexError in
///   nx — we return `None` so the wrapper's delegated path raises the
///   byte-identical error);
/// - whitespace tokenization == `str.split(None)` (Rust `split_whitespace`
///   matches: runs of Unicode whitespace, incl. `\t` and `\r`);
/// - node insertion order = source first, then targets in line order;
///   duplicate edges keep the first insertion (empty attrs either way);
/// - `CompatibilityMode::Strict` to match the graph the delegated path
///   builds via the default `fnx.Graph()` constructor (the older
///   `read_adjlist` engine kernel above is Hardened-mode and double-builds,
///   which is why it is NOT the fast path).
///
/// Returns `None` (caller falls back to the nx-delegated path) for missing
/// or non-UTF-8 files so nx defines those error surfaces exactly.
/// Canonicalize an adjlist token, registering the node (order, Python key,
/// attr dict) on first appearance. Returns the canonical id; repeated
/// appearances cost one hash lookup + one String clone.
fn canon_token<'a>(
    py: Python<'_>,
    token: &'a str,
    cache: &mut HashMap<&'a str, String>,
    nodes_order: &mut Vec<String>,
    node_key_map: &mut HashMap<String, PyObject>,
    node_py_attrs: &mut HashMap<String, Py<PyDict>>,
) -> String {
    if let Some(c) = cache.get(token) {
        return c.clone();
    }
    let c = format!("str:{}:{token}", token.len());
    cache.insert(token, c.clone());
    nodes_order.push(c.clone());
    node_key_map.insert(c.clone(), PyString::new(py, token).into_any().unbind());
    node_py_attrs.insert(c.clone(), PyDict::new(py).unbind());
    c
}

#[pyfunction]
#[pyo3(signature = (path,))]
fn read_adjlist_simple(py: Python<'_>, path: &str) -> PyResult<Option<PyGraph>> {
    let Ok(content) = std::fs::read_to_string(path) else {
        return Ok(None);
    };

    let mut inner = RustGraph::new(CompatibilityMode::Strict);
    let mut node_key_map: HashMap<String, PyObject> = HashMap::new();
    let mut node_py_attrs: HashMap<String, Py<PyDict>> = HashMap::new();
    let edge_py_attrs: HashMap<(String, String), Py<PyDict>> = HashMap::new();
    let mut nodes_order: Vec<String> = Vec::new();
    let mut edges: Vec<(String, String)> = Vec::new();
    let mut canon_cache: HashMap<&str, String> = HashMap::new();

    let mut lines: Vec<&str> = content.split('\n').collect();
    if content.ends_with('\n') {
        // `split` yields a synthetic trailing "" that file iteration never
        // produces; a *real* interior blank line stays in `lines` and bails
        // below (nx raises IndexError on it).
        lines.pop();
    }

    for raw in lines {
        let (line, had_comment) = match raw.find('#') {
            Some(p) => (&raw[..p], true),
            None => (raw, false),
        };
        if had_comment && line.is_empty() {
            // nx: comment at column 0 strips to "" -> `continue`. Without a
            // comment the nx line keeps its trailing newline so it is never
            // empty — that case falls through to the bail-out below.
            continue;
        }
        let mut tokens = line.split_whitespace();
        let Some(u) = tokens.next() else {
            // Blank/whitespace-only line: nx raises
            // IndexError("pop from empty list") — delegate for exactness.
            return Ok(None);
        };
        // Canonical node id for a str key is "str:{byte_len}:{s}" — must
        // match `node_key_to_string` exactly or adjacency lookups KeyError.
        // Nodes are registered on first appearance (order preserved); edges
        // are batched and inserted via the unrecorded bulk paths below,
        // which skip the per-element `record_decision` ledger push
        // (timestamp syscall + several String allocs each) that dominates
        // per-edge construction. `canon` caches token -> canonical so each
        // repeated token costs one hash lookup, not a fresh format!.
        let cu = canon_token(
            py,
            u,
            &mut canon_cache,
            &mut nodes_order,
            &mut node_key_map,
            &mut node_py_attrs,
        );
        for v in tokens {
            let cv = canon_token(
                py,
                v,
                &mut canon_cache,
                &mut nodes_order,
                &mut node_key_map,
                &mut node_py_attrs,
            );
            // Adjlist carries no edge attributes; keep the mirror sparse and
            // let `materialize_edge_py_attrs` create the live dict only when
            // Python asks for edge data or mutates an edge.
            edges.push((cu.clone(), cv));
        }
    }

    let _ = inner.extend_nodes_unrecorded(nodes_order);
    let _ = inner.extend_edges_unrecorded(edges);

    Ok(Some(PyGraph {
        inner,
        node_key_map,
        lazy_int_node_stop: 0,
        node_py_attrs,
        edge_py_attrs,
        adj_py_keys: HashMap::new(), // br-r37-c1-z6uka
        dict_of_dicts_cache: None,
        adj_row_py: HashMap::new(),
        graph_attrs: PyDict::new(py).unbind(),
        nodes_seq: 0,
        edges_seq: 0,
        edges_dirty: AtomicBool::new(false),
    }))
}

/// br-r37-c1-2vmel: single-pass native fast path for `read_edgelist` /
/// `read_weighted_edgelist` with default kwargs (comments="#",
/// delimiter=None, nodetype=None, encoding="utf-8",
/// create_using=None/Graph). The delegated path paid nx parse +
/// per-edge `_from_nx_graph` rebuild (no-data files 5.39x, weighted
/// 2.81x vs nx). Same recipe as `read_adjlist_simple` above; edges are
/// committed through the bulk unrecorded paths.
///
/// `mode` (validated by the Python wrappers):
/// - "data_true":  every line must have EXACTLY 2 tokens (extra tokens
///   need ast.literal_eval and nx raises a specific TypeError) — bail;
/// - "data_false": first 2 tokens, extras ignored;
/// - "weight_float": 2 tokens = edge with no attrs (nx leaves `{}` when
///   the weight column is missing), 3 tokens = weight parsed as float,
///   anything else bails (nx raises IndexError on length mismatch).
///
/// Line semantics mirror `nx.parse_edgelist`: comment strip at the
/// first `#`, whitespace tokenization (== `str.split(None)`), and
/// `len(s) < 2 -> continue` — blank, whitespace-only, and single-token
/// lines are silently skipped (verified against nx; unlike
/// parse_adjlist, which raises IndexError on those).
///
/// Float parity: Rust `f64::from_str` and CPython `float()` agree on
/// all sign/decimal/exponent/inf/infinity/nan spellings (both
/// correctly-rounded IEEE-754); Python additionally allows `_`
/// separators, so any token containing `_` bails to the delegated
/// path. Returns None (caller falls back to nx) for missing or
/// non-UTF-8 files so nx defines those error surfaces exactly.
#[pyfunction]
#[pyo3(signature = (path, mode))]
fn read_edgelist_simple(py: Python<'_>, path: &str, mode: &str) -> PyResult<Option<PyGraph>> {
    let Ok(content) = std::fs::read_to_string(path) else {
        return Ok(None);
    };

    let mut node_key_map: HashMap<String, PyObject> = HashMap::new();
    let mut node_py_attrs: HashMap<String, Py<PyDict>> = HashMap::new();
    let mut edge_py_attrs: HashMap<(String, String), Py<PyDict>> = HashMap::new();
    let mut nodes_order: Vec<String> = Vec::new();
    let mut edges: Vec<(String, String, fnx_classes::AttrMap)> = Vec::new();
    let mut canon_cache: HashMap<&str, String> = HashMap::new();

    for raw in content.split('\n') {
        let line = match raw.find('#') {
            Some(p) => &raw[..p],
            None => raw,
        };
        let mut tokens = line.split_whitespace();
        let (Some(u), Some(v)) = (tokens.next(), tokens.next()) else {
            // nx parse_edgelist: `if len(s) < 2: continue` — blank,
            // whitespace-only, and single-token lines are skipped.
            continue;
        };
        let extra = tokens.next();
        let mut attrs = fnx_classes::AttrMap::new();
        match mode {
            "data_true" => {
                if extra.is_some() {
                    // nx: TypeError("Failed to convert edge data ...").
                    return Ok(None);
                }
            }
            "data_false" => {
                // extras ignored entirely
            }
            "weight_float" => {
                if let Some(w) = extra {
                    if tokens.next().is_some() {
                        // nx: IndexError on data/data_keys length mismatch.
                        return Ok(None);
                    }
                    if w.contains('_') {
                        // Python float() accepts underscore separators;
                        // Rust does not — delegate.
                        return Ok(None);
                    }
                    let Ok(parsed) = w.parse::<f64>() else {
                        // nx raises TypeError on float() failure.
                        return Ok(None);
                    };
                    attrs.insert("weight".to_owned(), fnx_runtime::CgseValue::Float(parsed));
                }
                // 2 tokens: nx leaves the edge with empty attrs.
            }
            _ => return Ok(None),
        }

        let cu = canon_token(
            py,
            u,
            &mut canon_cache,
            &mut nodes_order,
            &mut node_key_map,
            &mut node_py_attrs,
        );
        let cv = canon_token(
            py,
            v,
            &mut canon_cache,
            &mut nodes_order,
            &mut node_key_map,
            &mut node_py_attrs,
        );
        let mirror = edge_py_attrs
            .entry(PyGraph::edge_key(&cu, &cv))
            .or_insert_with(|| PyDict::new(py).unbind());
        // weighted: duplicate edges overwrite, matching nx's per-line
        // datadict.update on the live edge dict.
        if let Some((k, fnx_runtime::CgseValue::Float(f))) = attrs.iter().next() {
            mirror.bind(py).set_item(k, *f)?;
        }
        edges.push((cu, cv, attrs));
    }

    let mut inner = RustGraph::new(CompatibilityMode::Strict);
    let _ = inner.extend_nodes_unrecorded(nodes_order);
    let _ = inner.extend_edges_with_attrs_unrecorded(edges);

    Ok(Some(PyGraph {
        inner,
        node_key_map,
        lazy_int_node_stop: 0,
        node_py_attrs,
        edge_py_attrs,
        adj_py_keys: HashMap::new(), // br-r37-c1-z6uka
        dict_of_dicts_cache: None,
        adj_row_py: HashMap::new(),
        graph_attrs: PyDict::new(py).unbind(),
        nodes_seq: 0,
        edges_seq: 0,
        edges_dirty: AtomicBool::new(false),
    }))
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
    if let Ok(mut pg) = g.extract::<PyRefMut<'_, PyGraph>>() {
        return to_dict_of_dicts_graph_cached(py, &mut pg).map(Some);
    }

    let gr = extract_graph(g)?;
    let outer = PyDict::new(py);
    match &gr {
        GraphRef::Undirected(pg) => {
            for u in pg.inner.nodes_ordered() {
                let inner_dict = PyDict::new(py);
                if let Some(neighbors) = pg.inner.neighbors_iter(u) {
                    for v in neighbors {
                        let ek = PyGraph::edge_key(u, v);
                        match pg.edge_py_attrs.get(&ek) {
                            Some(edge_dict) => {
                                inner_dict.set_item(pg.py_node_key(py, v), edge_dict.bind(py))?;
                            }
                            None => {
                                let edge_dict = PyDict::new(py);
                                inner_dict.set_item(pg.py_node_key(py, v), edge_dict)?;
                            }
                        }
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
                        match dg.edge_py_attrs.get(&ek) {
                            Some(edge_dict) => {
                                inner_dict.set_item(dg.py_node_key(py, v), edge_dict.bind(py))?;
                            }
                            None => {
                                let edge_dict = PyDict::new(py);
                                inner_dict.set_item(dg.py_node_key(py, v), edge_dict)?;
                            }
                        }
                    }
                }
                outer.set_item(dg.py_node_key(py, u), inner_dict)?;
            }
        }
        GraphRef::MultiUndirected { .. } | GraphRef::MultiDirected { .. } => return Ok(None),
    }
    Ok(Some(outer.unbind()))
}

fn to_dict_of_dicts_graph_cached(py: Python<'_>, pg: &mut PyGraph) -> PyResult<Py<PyDict>> {
    let cache_matches = pg
        .dict_of_dicts_cache
        .as_ref()
        .is_some_and(|cache| cache.nodes_seq == pg.nodes_seq && cache.edges_seq == pg.edges_seq);
    if !cache_matches {
        rebuild_dict_of_dicts_cache(py, pg)?;
    }
    let Some(cache) = pg.dict_of_dicts_cache.as_ref() else {
        return Err(PyRuntimeError::new_err(
            "dict_of_dicts cache missing after rebuild",
        ));
    };
    copy_dict_of_dicts_cache(py, cache)
}

fn rebuild_dict_of_dicts_cache(py: Python<'_>, pg: &mut PyGraph) -> PyResult<()> {
    let nodes: Vec<String> = pg
        .inner
        .nodes_ordered()
        .into_iter()
        .map(ToOwned::to_owned)
        .collect();
    let py_node_keys: Vec<PyObject> = nodes.iter().map(|node| pg.py_node_key(py, node)).collect();
    let mut rows = Vec::with_capacity(nodes.len());

    for (u_idx, u) in nodes.iter().enumerate() {
        let row = PyDict::new(py);
        let neighbors = pg
            .inner
            .neighbors_indices(u_idx)
            .map_or_else(Vec::new, <[usize]>::to_vec);
        for v_idx in neighbors {
            let Some(v) = nodes.get(v_idx) else {
                continue;
            };
            let Some(v_key) = py_node_keys.get(v_idx) else {
                continue;
            };
            let edge_key = PyGraph::edge_key(u, v);
            let edge_dict = pg
                .edge_py_attrs
                .entry(edge_key)
                .or_insert_with(|| PyDict::new(py).unbind());
            row.set_item(v_key.bind(py), edge_dict.bind(py))?;
        }
        if let Some(u_key) = py_node_keys.get(u_idx) {
            rows.push((u_key.clone_ref(py), row.unbind()));
        }
    }

    pg.dict_of_dicts_cache = Some(DictOfDictsCache {
        nodes_seq: pg.nodes_seq,
        edges_seq: pg.edges_seq,
        rows,
    });
    Ok(())
}

fn copy_dict_of_dicts_cache(py: Python<'_>, cache: &DictOfDictsCache) -> PyResult<Py<PyDict>> {
    let outer = PyDict::new(py);
    for (node_key, row) in &cache.rows {
        outer.set_item(node_key.bind(py), row.bind(py).copy()?)?;
    }
    Ok(outer.unbind())
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

/// Native fast path for `adjacency_data` (json_graph) on simple `Graph` and
/// `DiGraph`. Returns the `(nodes, adjacency)` pair that the Python wrapper
/// assembles into the full payload:
///   - `nodes`      = `[{**node_attrs, id_: node}, ...]`     (node insertion order)
///   - `adjacency`  = `[[{**edge_attrs, id_: nbr}, ...], ...]` (adjacency order)
///
/// Each emitted dict is a COPY of the live `node_py_attrs` / `edge_py_attrs`
/// dict with the `id_` field inserted last, exactly mirroring nx's
/// `{**attrs, id_: n}` spread (so a pre-existing `id_` key is overwritten in
/// place and the graph's stored attr dicts are never mutated). This bypasses
/// the per-access AdjacencyView Python machinery that made the pure-Python
/// wrapper ~14x slower than nx.
///
/// Returns `None` for multigraph inputs so the wrapper falls back to its
/// general implementation; the wrapper also gates on exact graph type so
/// filtered SubgraphViews / subclasses never reach here.
#[pyfunction]
pub fn adjacency_data_simple(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    id_: &str,
) -> PyResult<Option<(Py<PyList>, Py<PyList>)>> {
    let gr = extract_graph(g)?;
    let nodes = PyList::empty(py);
    let adjacency = PyList::empty(py);
    match &gr {
        GraphRef::Undirected(pg) => {
            for u in pg.inner.nodes_ordered() {
                let node_dict = match pg.node_py_attrs.get(u) {
                    Some(d) => d.bind(py).copy()?,
                    None => PyDict::new(py),
                };
                node_dict.set_item(id_, pg.py_node_key(py, u))?;
                nodes.append(node_dict)?;

                let nbr_list = PyList::empty(py);
                if let Some(neighbors) = pg.inner.neighbors_iter(u) {
                    for v in neighbors {
                        let ek = PyGraph::edge_key(u, v);
                        let edge_dict = match pg.edge_py_attrs.get(&ek) {
                            Some(d) => d.bind(py).copy()?,
                            None => PyDict::new(py),
                        };
                        edge_dict.set_item(id_, pg.py_node_key(py, v))?;
                        nbr_list.append(edge_dict)?;
                    }
                }
                adjacency.append(nbr_list)?;
            }
        }
        GraphRef::Directed { dg, .. } => {
            for u in dg.inner.nodes_ordered() {
                let node_dict = match dg.node_py_attrs.get(u) {
                    Some(d) => d.bind(py).copy()?,
                    None => PyDict::new(py),
                };
                node_dict.set_item(id_, dg.py_node_key(py, u))?;
                nodes.append(node_dict)?;

                let nbr_list = PyList::empty(py);
                if let Some(neighbors) = dg.inner.successors_iter(u) {
                    for v in neighbors {
                        let ek = PyDiGraph::edge_key(u, v);
                        let edge_dict = match dg.edge_py_attrs.get(&ek) {
                            Some(d) => d.bind(py).copy()?,
                            None => PyDict::new(py),
                        };
                        edge_dict.set_item(id_, dg.py_node_key(py, v))?;
                        nbr_list.append(edge_dict)?;
                    }
                }
                adjacency.append(nbr_list)?;
            }
        }
        GraphRef::MultiUndirected { .. } | GraphRef::MultiDirected { .. } => return Ok(None),
    }
    Ok(Some((nodes.unbind(), adjacency.unbind())))
}

/// Native fast path for `node_link_data` (json_graph) on simple `Graph` and
/// `DiGraph`. Returns the `(nodes, edges)` pair the Python wrapper places
/// under the caller's `nodes`/`edges` key names:
///   - `nodes` = `[{**node_attrs, name: node}, ...]`            (node insertion order)
///   - `edges` = `[{**edge_attrs, source: u, target: v}, ...]`  (G.edges() order)
///
/// Mirrors nx's `{**attrs, name: n}` / `{**attrs, source: u, target: v}`
/// spreads: each dict is a COPY of the live attr dict with the id/endpoint
/// fields appended last (so pre-existing same-named keys are overwritten in
/// place and the stored attr dicts are never mutated). Edge iteration uses
/// `edges_ordered()` — the same source `to_edgelist_simple` uses — so the
/// emitted edge order matches nx's `G.edges()` dedup order.
///
/// Returns `None` for multigraph inputs (the wrapper falls back); the wrapper
/// also gates on exact graph type so filtered SubgraphViews / subclasses never
/// reach here.
#[pyfunction]
#[pyo3(signature = (g, name, source, target))]
pub fn node_link_data_simple(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    name: &str,
    source: &str,
    target: &str,
) -> PyResult<Option<(Py<PyList>, Py<PyList>)>> {
    let gr = extract_graph(g)?;
    let nodes = PyList::empty(py);
    let edges = PyList::empty(py);
    match &gr {
        GraphRef::Undirected(pg) => {
            for u in pg.inner.nodes_ordered() {
                let node_dict = match pg.node_py_attrs.get(u) {
                    Some(d) => d.bind(py).copy()?,
                    None => PyDict::new(py),
                };
                node_dict.set_item(name, pg.py_node_key(py, u))?;
                nodes.append(node_dict)?;
            }
            // Match nx `G.edges()` undirected order: for u in node order,
            // emit (u, v) for each neighbor v whose own adjacency has not yet
            // been processed (seen-set of finished source nodes). This avoids
            // `edges_ordered()`, which eagerly clones every edge's AttrMap.
            let mut seen: std::collections::HashSet<String> = std::collections::HashSet::new();
            for u in pg.inner.nodes_ordered() {
                if let Some(neighbors) = pg.inner.neighbors_iter(u) {
                    for v in neighbors {
                        if seen.contains(v) {
                            continue;
                        }
                        let ek = PyGraph::edge_key(u, v);
                        let edge_dict = match pg.edge_py_attrs.get(&ek) {
                            Some(d) => d.bind(py).copy()?,
                            None => PyDict::new(py),
                        };
                        edge_dict.set_item(source, pg.py_node_key(py, u))?;
                        edge_dict.set_item(target, pg.py_node_key(py, v))?;
                        edges.append(edge_dict)?;
                    }
                }
                seen.insert(u.to_owned());
            }
        }
        GraphRef::Directed { dg, .. } => {
            for u in dg.inner.nodes_ordered() {
                let node_dict = match dg.node_py_attrs.get(u) {
                    Some(d) => d.bind(py).copy()?,
                    None => PyDict::new(py),
                };
                node_dict.set_item(name, dg.py_node_key(py, u))?;
                nodes.append(node_dict)?;
            }
            // Directed `G.edges()` order: out-edges in node order (no dedup).
            for u in dg.inner.nodes_ordered() {
                if let Some(neighbors) = dg.inner.successors_iter(u) {
                    for v in neighbors {
                        let ek = PyDiGraph::edge_key(u, v);
                        let edge_dict = match dg.edge_py_attrs.get(&ek) {
                            Some(d) => d.bind(py).copy()?,
                            None => PyDict::new(py),
                        };
                        edge_dict.set_item(source, dg.py_node_key(py, u))?;
                        edge_dict.set_item(target, dg.py_node_key(py, v))?;
                        edges.append(edge_dict)?;
                    }
                }
            }
        }
        GraphRef::MultiUndirected { .. } | GraphRef::MultiDirected { .. } => return Ok(None),
    }
    Ok(Some((nodes.unbind(), edges.unbind())))
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
fn fw_edge_weight(py: Python<'_>, attrs: Option<&Py<PyDict>>, weight: &str) -> PyResult<f64> {
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
    m.add_function(wrap_pyfunction!(adjacency_data_simple, m)?)?;
    m.add_function(wrap_pyfunction!(node_link_data_simple, m)?)?;
    m.add_function(wrap_pyfunction!(to_edgelist_simple, m)?)?;
    m.add_function(wrap_pyfunction!(read_edgelist, m)?)?;
    m.add_function(wrap_pyfunction!(write_edgelist, m)?)?;
    m.add_function(wrap_pyfunction!(read_adjlist, m)?)?;
    m.add_function(wrap_pyfunction!(read_adjlist_simple, m)?)?;
    m.add_function(wrap_pyfunction!(read_edgelist_simple, m)?)?;
    m.add_function(wrap_pyfunction!(digraph_absorb_graph_bidirected, m)?)?;
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
