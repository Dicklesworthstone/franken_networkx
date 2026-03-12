//! Python bindings for FrankenNetworkX algorithms.
//!
//! Each function follows the NetworkX API signature, accepts a `Graph` or `DiGraph`,
//! delegates to the Rust implementation in `fnx_algorithms`, and returns
//! Python-native types (lists, dicts, floats, bools).

use crate::digraph::PyDiGraph;
use crate::{NetworkXError, NetworkXNoPath, NodeNotFound, PyGraph, node_key_to_string};
use pyo3::prelude::*;
use pyo3::types::PyDict;
use std::collections::HashMap;

// ---------------------------------------------------------------------------
// GraphRef — unified graph access for algorithms accepting both Graph & DiGraph
// ---------------------------------------------------------------------------

/// Unified graph reference for algorithm bindings that accept both Graph and DiGraph.
///
/// For undirected graphs, borrows the inner `Graph` directly.
/// For directed graphs, converts to undirected once and stores the result.
pub(crate) enum GraphRef<'py> {
    Undirected(PyRef<'py, PyGraph>),
    Directed {
        dg: PyRef<'py, PyDiGraph>,
        undirected: Box<fnx_classes::Graph>,
    },
}

impl<'py> GraphRef<'py> {
    /// Get a reference to the undirected graph (for algorithm dispatch).
    pub(crate) fn undirected(&self) -> &fnx_classes::Graph {
        match self {
            GraphRef::Undirected(pg) => &pg.inner,
            GraphRef::Directed { undirected, .. } => undirected,
        }
    }

    /// Convert a canonical node key to Python object.
    fn py_node_key(&self, py: Python<'_>, canonical: &str) -> PyObject {
        match self {
            GraphRef::Undirected(pg) => pg.py_node_key(py, canonical),
            GraphRef::Directed { dg, .. } => dg.py_node_key(py, canonical),
        }
    }

    /// Check if a node exists.
    fn has_node(&self, canonical: &str) -> bool {
        match self {
            GraphRef::Undirected(pg) => pg.inner.has_node(canonical),
            GraphRef::Directed { dg, .. } => dg.inner.has_node(canonical),
        }
    }

    /// Is this a directed graph?
    fn is_directed(&self) -> bool {
        matches!(self, GraphRef::Directed { .. })
    }

    /// Get the original graph's node key map.
    fn node_key_map(&self) -> &HashMap<String, PyObject> {
        match self {
            GraphRef::Undirected(pg) => &pg.node_key_map,
            GraphRef::Directed { dg, .. } => &dg.node_key_map,
        }
    }

    /// Look up edge attributes from the original graph for an undirected edge.
    /// For DiGraph, tries both directions.
    fn edge_attrs_for_undirected(&self, left: &str, right: &str) -> Option<&Py<PyDict>> {
        match self {
            GraphRef::Undirected(pg) => {
                let ek = PyGraph::edge_key(left, right);
                pg.edge_py_attrs.get(&ek)
            }
            GraphRef::Directed { dg, .. } => {
                let ek1 = (left.to_owned(), right.to_owned());
                if let Some(attrs) = dg.edge_py_attrs.get(&ek1) {
                    return Some(attrs);
                }
                let ek2 = (right.to_owned(), left.to_owned());
                dg.edge_py_attrs.get(&ek2)
            }
        }
    }
}

/// Extract either a `PyGraph` or `PyDiGraph` from a Python argument.
pub(crate) fn extract_graph<'py>(g: &'py Bound<'py, PyAny>) -> PyResult<GraphRef<'py>> {
    if let Ok(pg) = g.extract::<PyRef<'py, PyGraph>>() {
        Ok(GraphRef::Undirected(pg))
    } else if let Ok(dg) = g.extract::<PyRef<'py, PyDiGraph>>() {
        let undirected = dg.inner.to_undirected();
        Ok(GraphRef::Directed {
            dg,
            undirected: Box::new(undirected),
        })
    } else {
        Err(pyo3::exceptions::PyTypeError::new_err(
            "expected Graph or DiGraph",
        ))
    }
}

/// Require undirected graph — raise `NetworkXNotImplemented` on DiGraph.
fn require_undirected(gr: &GraphRef<'_>, _algo_name: &str) -> PyResult<()> {
    if gr.is_directed() {
        return Err(crate::NetworkXNotImplemented::new_err(
            "not implemented for directed type",
        ));
    }
    Ok(())
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

fn validate_node(gr: &GraphRef<'_>, canonical: &str, py_key: &Bound<'_, PyAny>) -> PyResult<()> {
    if !gr.has_node(canonical) {
        return Err(NodeNotFound::new_err(format!(
            "Node {} is not in G",
            py_key.repr()?
        )));
    }
    Ok(())
}

fn validate_node_str(gr: &GraphRef<'_>, canonical: &str) -> PyResult<()> {
    if !gr.has_node(canonical) {
        return Err(NodeNotFound::new_err(format!(
            "Node '{}' is not in G",
            canonical
        )));
    }
    Ok(())
}

fn compute_single_shortest_path(
    inner: &fnx_classes::Graph,
    source: &str,
    target: &str,
    weight: Option<&str>,
    method: &str,
) -> PyResult<Option<Vec<String>>> {
    match weight {
        None => {
            let result = fnx_algorithms::shortest_path_unweighted(inner, source, target);
            Ok(result.path)
        }
        Some(w) => match method {
            "dijkstra" => {
                let result = fnx_algorithms::shortest_path_weighted(inner, source, target, w);
                Ok(result.path)
            }
            "bellman-ford" => {
                let result = fnx_algorithms::bellman_ford_shortest_paths(inner, source, w);
                if result.negative_cycle_detected {
                    return Err(crate::NetworkXUnbounded::new_err(
                        "Negative cost cycle detected.",
                    ));
                }
                let pred_map: std::collections::HashMap<&str, Option<&str>> = result
                    .predecessors
                    .iter()
                    .map(|e| (e.node.as_str(), e.predecessor.as_deref()))
                    .collect();

                if !pred_map.contains_key(target) {
                    return Ok(None);
                }

                let mut path = vec![target.to_owned()];
                let mut current = target;
                while current != source {
                    match pred_map.get(current) {
                        Some(Some(prev)) => {
                            path.push((*prev).to_owned());
                            current = prev;
                        }
                        _ => return Ok(None),
                    }
                }
                path.reverse();
                Ok(Some(path))
            }
            other => Err(NetworkXError::new_err(format!(
                "Unknown method: '{}'. Supported: 'dijkstra', 'bellman-ford'.",
                other
            ))),
        },
    }
}

/// Helper to convert CentralityScore vec to Python dict.
fn centrality_to_dict(
    py: Python<'_>,
    gr: &GraphRef<'_>,
    scores: &[fnx_algorithms::CentralityScore],
) -> PyResult<Py<PyDict>> {
    let dict = PyDict::new(py);
    for s in scores {
        dict.set_item(gr.py_node_key(py, &s.node), s.score)?;
    }
    Ok(dict.unbind())
}

// ---------------------------------------------------------------------------
// shortest_path
// ---------------------------------------------------------------------------

/// Compute shortest paths in the graph.
///
/// Parameters
/// ----------
/// G : Graph or DiGraph
///     The input graph.
/// source : node, optional
///     Starting node for the path.
/// target : node, optional
///     Ending node for the path.
/// weight : str, optional
///     Edge attribute to use as weight. If None, all edges have weight 1.
/// method : str, optional
///     Algorithm: ``'dijkstra'`` (default) or ``'bellman-ford'``.
///
/// Returns
/// -------
/// path : list
///     List of nodes in the shortest path from source to target.
///
/// Raises
/// ------
/// NodeNotFound
///     If source or target is not in the graph.
/// NetworkXNoPath
///     If no path exists between source and target.
#[pyfunction]
#[pyo3(signature = (g, source=None, target=None, weight=None, method="dijkstra"))]
pub fn shortest_path(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    source: Option<&Bound<'_, PyAny>>,
    target: Option<&Bound<'_, PyAny>>,
    weight: Option<&str>,
    method: &str,
) -> PyResult<PyObject> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    log::info!(target: "franken_networkx", "shortest_path: nodes={} edges={}", inner.node_count(), inner.edge_count());
    match (source, target) {
        (Some(src), Some(tgt)) => {
            let s = node_key_to_string(py, src)?;
            let t = node_key_to_string(py, tgt)?;
            validate_node(&gr, &s, src)?;
            validate_node(&gr, &t, tgt)?;

            let path = compute_single_shortest_path(inner, &s, &t, weight, method)?;
            match path {
                Some(p) => {
                    let py_path: Vec<PyObject> = p.iter().map(|n| gr.py_node_key(py, n)).collect();
                    Ok(py_path.into_pyobject(py)?.into_any().unbind())
                }
                None => Err(NetworkXNoPath::new_err(format!(
                    "No path between {} and {}.",
                    s, t
                ))),
            }
        }
        (Some(src), None) => {
            let s = node_key_to_string(py, src)?;
            validate_node(&gr, &s, src)?;
            let result = PyDict::new(py);
            for node in inner.nodes_ordered() {
                if let Some(p) = compute_single_shortest_path(inner, &s, node, weight, method)? {
                    let py_path: Vec<PyObject> = p.iter().map(|n| gr.py_node_key(py, n)).collect();
                    result.set_item(gr.py_node_key(py, node), py_path)?;
                }
            }
            Ok(result.into_any().unbind())
        }
        (None, Some(tgt)) => {
            let t = node_key_to_string(py, tgt)?;
            validate_node(&gr, &t, tgt)?;
            let result = PyDict::new(py);
            for node in inner.nodes_ordered() {
                if let Some(p) = compute_single_shortest_path(inner, node, &t, weight, method)? {
                    let py_path: Vec<PyObject> = p.iter().map(|n| gr.py_node_key(py, n)).collect();
                    result.set_item(gr.py_node_key(py, node), py_path)?;
                }
            }
            Ok(result.into_any().unbind())
        }
        (None, None) => {
            let result = PyDict::new(py);
            for src_node in inner.nodes_ordered() {
                let inner_dict = PyDict::new(py);
                for tgt_node in inner.nodes_ordered() {
                    if let Some(p) =
                        compute_single_shortest_path(inner, src_node, tgt_node, weight, method)?
                    {
                        let py_path: Vec<PyObject> =
                            p.iter().map(|n| gr.py_node_key(py, n)).collect();
                        inner_dict.set_item(gr.py_node_key(py, tgt_node), py_path)?;
                    }
                }
                result.set_item(gr.py_node_key(py, src_node), inner_dict)?;
            }
            Ok(result.into_any().unbind())
        }
    }
}

// ---------------------------------------------------------------------------
// shortest_path_length
// ---------------------------------------------------------------------------

#[pyfunction]
#[pyo3(signature = (g, source, target, weight=None))]
pub fn shortest_path_length(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    source: &Bound<'_, PyAny>,
    target: &Bound<'_, PyAny>,
    weight: Option<&str>,
) -> PyResult<PyObject> {
    let gr = extract_graph(g)?;
    let s = node_key_to_string(py, source)?;
    let t = node_key_to_string(py, target)?;
    validate_node(&gr, &s, source)?;
    validate_node(&gr, &t, target)?;
    let inner = gr.undirected();

    if let Some(_w) = weight {
        let result = fnx_algorithms::shortest_path_weighted(inner, &s, &t, _w);
        match result.path {
            Some(path) => {
                let mut total: f64 = 0.0;
                for i in 0..path.len() - 1 {
                    let attrs = inner.edge_attrs(&path[i], &path[i + 1]);
                    let w = attrs
                        .and_then(|a| a.get(_w))
                        .and_then(|v| v.parse::<f64>().ok())
                        .unwrap_or(1.0);
                    total += w;
                }
                Ok(total.into_pyobject(py)?.into_any().unbind())
            }
            None => Err(NetworkXNoPath::new_err(format!(
                "No path between {} and {}.",
                s, t
            ))),
        }
    } else {
        let result = fnx_algorithms::shortest_path_length(inner, &s, &t);
        match result.length {
            Some(len) => Ok(len.into_pyobject(py)?.into_any().unbind()),
            None => Err(NetworkXNoPath::new_err(format!(
                "No path between {} and {}.",
                s, t
            ))),
        }
    }
}

// ---------------------------------------------------------------------------
// has_path
// ---------------------------------------------------------------------------

#[pyfunction]
pub fn has_path(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    source: &Bound<'_, PyAny>,
    target: &Bound<'_, PyAny>,
) -> PyResult<bool> {
    let gr = extract_graph(g)?;
    let s = node_key_to_string(py, source)?;
    let t = node_key_to_string(py, target)?;
    validate_node(&gr, &s, source)?;
    validate_node(&gr, &t, target)?;
    let result = fnx_algorithms::has_path(gr.undirected(), &s, &t);
    Ok(result.has_path)
}

// ---------------------------------------------------------------------------
// average_shortest_path_length
// ---------------------------------------------------------------------------

#[pyfunction]
#[pyo3(signature = (g, weight=None))]
pub fn average_shortest_path_length(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    weight: Option<&str>,
) -> PyResult<f64> {
    if weight.is_some() {
        return Err(crate::NetworkXNotImplemented::new_err(
            "weighted average_shortest_path_length not yet supported",
        ));
    }
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    let (connected, avg) = py.allow_threads(|| {
        let conn = fnx_algorithms::is_connected(inner);
        let result = fnx_algorithms::average_shortest_path_length(inner);
        (conn.is_connected, result.average_shortest_path_length)
    });
    if !connected {
        return Err(NetworkXError::new_err("Graph is not connected."));
    }
    Ok(avg)
}

// ---------------------------------------------------------------------------
// dijkstra_path
// ---------------------------------------------------------------------------

#[pyfunction]
#[pyo3(signature = (g, source, target, weight="weight"))]
pub fn dijkstra_path(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    source: &Bound<'_, PyAny>,
    target: &Bound<'_, PyAny>,
    weight: &str,
) -> PyResult<Vec<PyObject>> {
    let gr = extract_graph(g)?;
    let s = node_key_to_string(py, source)?;
    let t = node_key_to_string(py, target)?;
    validate_node(&gr, &s, source)?;
    validate_node(&gr, &t, target)?;

    let result = fnx_algorithms::shortest_path_weighted(gr.undirected(), &s, &t, weight);
    match result.path {
        Some(p) => Ok(p.iter().map(|n| gr.py_node_key(py, n)).collect()),
        None => Err(NetworkXNoPath::new_err(format!(
            "No path between {} and {}.",
            s, t
        ))),
    }
}

// ---------------------------------------------------------------------------
// bellman_ford_path
// ---------------------------------------------------------------------------

#[pyfunction]
#[pyo3(signature = (g, source, target, weight="weight"))]
pub fn bellman_ford_path(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    source: &Bound<'_, PyAny>,
    target: &Bound<'_, PyAny>,
    weight: &str,
) -> PyResult<Vec<PyObject>> {
    let gr = extract_graph(g)?;
    let s = node_key_to_string(py, source)?;
    let t = node_key_to_string(py, target)?;
    validate_node(&gr, &s, source)?;
    validate_node(&gr, &t, target)?;

    let result = fnx_algorithms::bellman_ford_shortest_paths(gr.undirected(), &s, weight);
    if result.negative_cycle_detected {
        return Err(crate::NetworkXUnbounded::new_err(
            "Negative cost cycle detected.",
        ));
    }

    let pred_map: std::collections::HashMap<&str, Option<&str>> = result
        .predecessors
        .iter()
        .map(|e| (e.node.as_str(), e.predecessor.as_deref()))
        .collect();

    if !pred_map.contains_key(t.as_str()) {
        return Err(NetworkXNoPath::new_err(format!(
            "No path between {} and {}.",
            s, t
        )));
    }

    let mut path = vec![t.clone()];
    let mut current = t.as_str();
    while current != s {
        match pred_map.get(current) {
            Some(Some(prev)) => {
                path.push((*prev).to_owned());
                current = prev;
            }
            _ => {
                return Err(NetworkXNoPath::new_err(format!(
                    "No path between {} and {}.",
                    s, t
                )));
            }
        }
    }
    path.reverse();
    Ok(path.iter().map(|n| gr.py_node_key(py, n)).collect())
}

// ---------------------------------------------------------------------------
// multi_source_dijkstra
// ---------------------------------------------------------------------------

#[pyfunction]
#[pyo3(signature = (g, sources, weight="weight"))]
pub fn multi_source_dijkstra(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    sources: &Bound<'_, PyAny>,
    weight: &str,
) -> PyResult<(PyObject, PyObject)> {
    let gr = extract_graph(g)?;
    let iter = pyo3::types::PyIterator::from_object(sources)?;
    let mut source_strs = Vec::new();
    for item in iter {
        let item = item?;
        let s = node_key_to_string(py, &item)?;
        validate_node_str(&gr, &s)?;
        source_strs.push(s);
    }
    let source_refs: Vec<&str> = source_strs.iter().map(String::as_str).collect();

    let result = fnx_algorithms::multi_source_dijkstra(gr.undirected(), &source_refs, weight);

    let dist_dict = PyDict::new(py);
    for entry in &result.distances {
        dist_dict.set_item(gr.py_node_key(py, &entry.node), entry.distance)?;
    }

    let pred_map: std::collections::HashMap<&str, Option<&str>> = result
        .predecessors
        .iter()
        .map(|e| (e.node.as_str(), e.predecessor.as_deref()))
        .collect();

    let paths_dict = PyDict::new(py);
    for entry in &result.distances {
        let mut path = vec![entry.node.clone()];
        let mut current = entry.node.as_str();
        while let Some(Some(prev)) = pred_map.get(current) {
            path.push((*prev).to_owned());
            current = prev;
        }
        path.reverse();
        let py_path: Vec<PyObject> = path.iter().map(|n| gr.py_node_key(py, n)).collect();
        paths_dict.set_item(gr.py_node_key(py, &entry.node), py_path)?;
    }

    Ok((
        dist_dict.into_any().unbind(),
        paths_dict.into_any().unbind(),
    ))
}

// ===========================================================================
// Connectivity algorithms
// ===========================================================================

/// Return True if the graph is connected, False otherwise.
///
/// Parameters
/// ----------
/// G : Graph
///     An undirected graph.
///
/// Returns
/// -------
/// connected : bool
///     True if the graph is connected.
///
/// Raises
/// ------
/// NetworkXNotImplemented
///     If the graph is directed.
#[pyfunction]
pub fn is_connected(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<bool> {
    let gr = extract_graph(g)?;
    require_undirected(&gr, "is_connected")?;
    let inner = gr.undirected();
    log::info!(target: "franken_networkx", "is_connected: nodes={} edges={}", inner.node_count(), inner.edge_count());
    Ok(py.allow_threads(|| fnx_algorithms::is_connected(inner).is_connected))
}

/// Return the density of the graph.
#[pyfunction]
pub fn density(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<f64> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    Ok(py.allow_threads(|| fnx_algorithms::density(inner).density))
}

/// Generate connected components.
///
/// Parameters
/// ----------
/// G : Graph
///     An undirected graph.
///
/// Returns
/// -------
/// comp : list of lists
///     A list of lists, one per connected component, each containing
///     the nodes in the component.
///
/// Raises
/// ------
/// NetworkXNotImplemented
///     If the graph is directed.
#[pyfunction]
pub fn connected_components(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<Vec<PyObject>> {
    let gr = extract_graph(g)?;
    require_undirected(&gr, "connected_components")?;
    let inner = gr.undirected();
    log::info!(target: "franken_networkx", "connected_components: nodes={} edges={}", inner.node_count(), inner.edge_count());
    let result = py.allow_threads(|| fnx_algorithms::connected_components(inner));
    result
        .components
        .iter()
        .map(|comp| {
            let py_set: Vec<PyObject> = comp.iter().map(|n| gr.py_node_key(py, n)).collect();
            py_set.into_pyobject(py).map(|obj| obj.into_any().unbind())
        })
        .collect()
}

/// Return the number of connected components.
/// Raises ``NetworkXNotImplemented`` on DiGraph.
#[pyfunction]
pub fn number_connected_components(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<usize> {
    let gr = extract_graph(g)?;
    require_undirected(&gr, "number_connected_components")?;
    let inner = gr.undirected();
    Ok(py.allow_threads(|| fnx_algorithms::number_connected_components(inner).count))
}

/// Return the node connectivity of the graph.
#[pyfunction]
pub fn node_connectivity(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<usize> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    Ok(py.allow_threads(|| fnx_algorithms::global_node_connectivity(inner).value))
}

/// Return a minimum node cut of the graph.
#[pyfunction]
pub fn minimum_node_cut(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<Vec<PyObject>> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    let result = py.allow_threads(|| fnx_algorithms::global_minimum_node_cut(inner));
    Ok(result
        .cut_nodes
        .iter()
        .map(|n| gr.py_node_key(py, n))
        .collect())
}

/// Return the edge connectivity of the graph.
#[pyfunction]
#[pyo3(signature = (g, capacity="capacity"))]
pub fn edge_connectivity(py: Python<'_>, g: &Bound<'_, PyAny>, capacity: &str) -> PyResult<f64> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    let cap = capacity.to_owned();
    Ok(py.allow_threads(move || {
        fnx_algorithms::global_edge_connectivity_edmonds_karp(inner, &cap).value
    }))
}

/// Return articulation points (cut vertices) of the graph.
/// Raises ``NetworkXNotImplemented`` on DiGraph.
#[pyfunction]
pub fn articulation_points(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<Vec<PyObject>> {
    let gr = extract_graph(g)?;
    require_undirected(&gr, "articulation_points")?;
    let inner = gr.undirected();
    let result = py.allow_threads(|| fnx_algorithms::articulation_points(inner));
    Ok(result.nodes.iter().map(|n| gr.py_node_key(py, n)).collect())
}

/// Return bridges (cut edges) of the graph.
/// Raises ``NetworkXNotImplemented`` on DiGraph.
#[pyfunction]
pub fn bridges(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<Vec<(PyObject, PyObject)>> {
    let gr = extract_graph(g)?;
    require_undirected(&gr, "bridges")?;
    let inner = gr.undirected();
    let result = py.allow_threads(|| fnx_algorithms::bridges(inner));
    Ok(result
        .edges
        .iter()
        .map(|(u, v)| (gr.py_node_key(py, u), gr.py_node_key(py, v)))
        .collect())
}

// ===========================================================================
// Centrality algorithms
// ===========================================================================

/// Return the degree centrality for all nodes.
#[pyfunction]
pub fn degree_centrality(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<Py<PyDict>> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    let result = py.allow_threads(|| fnx_algorithms::degree_centrality(inner));
    centrality_to_dict(py, &gr, &result.scores)
}

/// Return the closeness centrality for all nodes.
#[pyfunction]
pub fn closeness_centrality(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<Py<PyDict>> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    let result = py.allow_threads(|| fnx_algorithms::closeness_centrality(inner));
    centrality_to_dict(py, &gr, &result.scores)
}

/// Return the harmonic centrality for all nodes.
#[pyfunction]
pub fn harmonic_centrality(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<Py<PyDict>> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    let result = py.allow_threads(|| fnx_algorithms::harmonic_centrality(inner));
    centrality_to_dict(py, &gr, &result.scores)
}

/// Return the Katz centrality for all nodes.
#[pyfunction]
pub fn katz_centrality(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<Py<PyDict>> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    let result = py.allow_threads(|| fnx_algorithms::katz_centrality(inner));
    centrality_to_dict(py, &gr, &result.scores)
}

/// Compute the shortest-path betweenness centrality for nodes.
///
/// Parameters
/// ----------
/// G : Graph or DiGraph
///     The input graph.
///
/// Returns
/// -------
/// nodes : dict
///     Dictionary of nodes with betweenness centrality as the value.
#[pyfunction]
pub fn betweenness_centrality(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<Py<PyDict>> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    log::info!(target: "franken_networkx", "betweenness_centrality: nodes={} edges={}", inner.node_count(), inner.edge_count());
    let result = py.allow_threads(|| fnx_algorithms::betweenness_centrality(inner));
    centrality_to_dict(py, &gr, &result.scores)
}

/// Return the edge betweenness centrality for all edges.
#[pyfunction]
pub fn edge_betweenness_centrality(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<Py<PyDict>> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    let result = py.allow_threads(|| fnx_algorithms::edge_betweenness_centrality(inner));
    let dict = PyDict::new(py);
    for s in &result.scores {
        let key = pyo3::types::PyTuple::new(
            py,
            &[gr.py_node_key(py, &s.left), gr.py_node_key(py, &s.right)],
        )?;
        dict.set_item(key, s.score)?;
    }
    Ok(dict.unbind())
}

/// Return the eigenvector centrality for all nodes.
#[pyfunction]
pub fn eigenvector_centrality(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<Py<PyDict>> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    let result = py.allow_threads(|| fnx_algorithms::eigenvector_centrality(inner));
    centrality_to_dict(py, &gr, &result.scores)
}

/// Compute the PageRank of each node.
///
/// Parameters
/// ----------
/// G : Graph or DiGraph
///     The input graph. Undirected graphs are treated as directed
///     with edges in both directions.
///
/// Returns
/// -------
/// pagerank : dict
///     Dictionary of nodes with PageRank as value.
#[pyfunction]
pub fn pagerank(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<Py<PyDict>> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    log::info!(target: "franken_networkx", "pagerank: nodes={} edges={}", inner.node_count(), inner.edge_count());
    let result = py.allow_threads(|| fnx_algorithms::pagerank(inner));
    centrality_to_dict(py, &gr, &result.scores)
}

/// Return HITS hubs and authorities scores.
#[pyfunction]
pub fn hits(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<(Py<PyDict>, Py<PyDict>)> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    let result = py.allow_threads(|| fnx_algorithms::hits_centrality(inner));
    let hubs = centrality_to_dict(py, &gr, &result.hubs)?;
    let auths = centrality_to_dict(py, &gr, &result.authorities)?;
    Ok((hubs, auths))
}

/// Return the average neighbor degree for each node.
#[pyfunction]
pub fn average_neighbor_degree(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<Py<PyDict>> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    let result = py.allow_threads(|| fnx_algorithms::average_neighbor_degree(inner));
    let dict = PyDict::new(py);
    for s in &result.scores {
        dict.set_item(gr.py_node_key(py, &s.node), s.avg_neighbor_degree)?;
    }
    Ok(dict.unbind())
}

/// Return the degree assortativity coefficient.
#[pyfunction]
pub fn degree_assortativity_coefficient(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<f64> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    Ok(py.allow_threads(|| fnx_algorithms::degree_assortativity_coefficient(inner).coefficient))
}

/// Return a list of nodes in decreasing voterank order.
#[pyfunction]
pub fn voterank(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<Vec<PyObject>> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    let result = py.allow_threads(|| fnx_algorithms::voterank(inner));
    Ok(result
        .ranked
        .iter()
        .map(|n| gr.py_node_key(py, n))
        .collect())
}

// ===========================================================================
// Clustering algorithms
// ===========================================================================

/// Compute the clustering coefficient for nodes.
///
/// Parameters
/// ----------
/// G : Graph or DiGraph
///     The input graph.
///
/// Returns
/// -------
/// clust : dict
///     Dictionary of nodes with clustering coefficient as the value.
#[pyfunction]
pub fn clustering(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<Py<PyDict>> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    let result = py.allow_threads(|| fnx_algorithms::clustering_coefficient(inner));
    centrality_to_dict(py, &gr, &result.scores)
}

/// Return the average clustering coefficient.
#[pyfunction]
pub fn average_clustering(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<f64> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    Ok(py.allow_threads(|| fnx_algorithms::clustering_coefficient(inner).average_clustering))
}

/// Return the transitivity (global clustering coefficient).
#[pyfunction]
pub fn transitivity(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<f64> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    Ok(py.allow_threads(|| fnx_algorithms::clustering_coefficient(inner).transitivity))
}

/// Return the number of triangles for each node.
#[pyfunction]
pub fn triangles(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<Py<PyDict>> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    let result = py.allow_threads(|| fnx_algorithms::triangles(inner));
    let dict = PyDict::new(py);
    for t in &result.triangles {
        dict.set_item(gr.py_node_key(py, &t.node), t.count)?;
    }
    Ok(dict.unbind())
}

/// Return the square clustering coefficient for each node.
#[pyfunction]
pub fn square_clustering(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<Py<PyDict>> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    let result = py.allow_threads(|| fnx_algorithms::square_clustering(inner));
    centrality_to_dict(py, &gr, &result.scores)
}

/// Return all maximal cliques as a list of lists.
#[pyfunction]
pub fn find_cliques(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<Vec<Vec<PyObject>>> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    let result = py.allow_threads(|| fnx_algorithms::find_cliques(inner));
    Ok(result
        .cliques
        .iter()
        .map(|clique| clique.iter().map(|n| gr.py_node_key(py, n)).collect())
        .collect())
}

/// Return the size of the largest maximal clique.
#[pyfunction]
pub fn graph_clique_number(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<usize> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    Ok(py.allow_threads(|| fnx_algorithms::graph_clique_number(inner).clique_number))
}

// ===========================================================================
// Matching algorithms
// ===========================================================================

/// Return a maximal matching as a set of edge tuples.
#[pyfunction]
pub fn maximal_matching(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
) -> PyResult<Vec<(PyObject, PyObject)>> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    let result = py.allow_threads(|| fnx_algorithms::maximal_matching(inner));
    Ok(result
        .matching
        .iter()
        .map(|(u, v)| (gr.py_node_key(py, u), gr.py_node_key(py, v)))
        .collect())
}

/// Return a max-weight matching as a set of edge tuples.
#[pyfunction]
#[pyo3(signature = (g, weight="weight"))]
pub fn max_weight_matching(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    weight: &str,
) -> PyResult<Vec<(PyObject, PyObject)>> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    let w = weight.to_owned();
    let result = py.allow_threads(move || fnx_algorithms::min_weight_matching(inner, &w));
    Ok(result
        .matching
        .iter()
        .map(|(u, v)| (gr.py_node_key(py, u), gr.py_node_key(py, v)))
        .collect())
}

/// Return a min-weight matching as a set of edge tuples.
#[pyfunction]
#[pyo3(signature = (g, weight="weight"))]
pub fn min_weight_matching(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    weight: &str,
) -> PyResult<Vec<(PyObject, PyObject)>> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    let w = weight.to_owned();
    let result = py.allow_threads(move || fnx_algorithms::min_weight_matching(inner, &w));
    Ok(result
        .matching
        .iter()
        .map(|(u, v)| (gr.py_node_key(py, u), gr.py_node_key(py, v)))
        .collect())
}

/// Return a minimum edge cover as a set of edge tuples.
#[pyfunction]
pub fn min_edge_cover(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<Vec<(PyObject, PyObject)>> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    let result = py.allow_threads(|| fnx_algorithms::min_edge_cover(inner));
    match result {
        Some(r) => Ok(r
            .edges
            .iter()
            .map(|(u, v)| (gr.py_node_key(py, u), gr.py_node_key(py, v)))
            .collect()),
        None => Err(NetworkXError::new_err(
            "Graph has a node with no edge incident on it, so no edge cover exists.",
        )),
    }
}

// ===========================================================================
// Flow algorithms
// ===========================================================================

/// Return the maximum flow value between source and sink.
#[pyfunction]
#[pyo3(signature = (g, source, sink, capacity="capacity"))]
pub fn maximum_flow_value(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    source: &Bound<'_, PyAny>,
    sink: &Bound<'_, PyAny>,
    capacity: &str,
) -> PyResult<f64> {
    let gr = extract_graph(g)?;
    let s = node_key_to_string(py, source)?;
    let t = node_key_to_string(py, sink)?;
    let inner = gr.undirected();
    let cap = capacity.to_owned();
    Ok(py.allow_threads(move || fnx_algorithms::max_flow_edmonds_karp(inner, &s, &t, &cap).value))
}

/// Return the minimum cut value between source and sink.
#[pyfunction]
#[pyo3(signature = (g, source, sink, capacity="capacity"))]
pub fn minimum_cut_value(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    source: &Bound<'_, PyAny>,
    sink: &Bound<'_, PyAny>,
    capacity: &str,
) -> PyResult<f64> {
    let gr = extract_graph(g)?;
    let s = node_key_to_string(py, source)?;
    let t = node_key_to_string(py, sink)?;
    let inner = gr.undirected();
    let cap = capacity.to_owned();
    Ok(py
        .allow_threads(move || fnx_algorithms::minimum_cut_edmonds_karp(inner, &s, &t, &cap).value))
}

// ===========================================================================
// Distance measures
// ===========================================================================

/// Return the eccentricity of each node as a dict.
#[pyfunction]
pub fn eccentricity(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<Py<PyDict>> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    let result = py.allow_threads(|| fnx_algorithms::distance_measures(inner));
    let dict = PyDict::new(py);
    for e in &result.eccentricity {
        dict.set_item(gr.py_node_key(py, &e.node), e.value)?;
    }
    Ok(dict.unbind())
}

/// Return the diameter of the graph.
#[pyfunction]
pub fn diameter(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<usize> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    let (connected, result) = py.allow_threads(|| {
        let c = fnx_algorithms::is_connected(inner);
        let r = fnx_algorithms::distance_measures(inner);
        (c.is_connected, r)
    });
    if !connected {
        return Err(NetworkXError::new_err(
            "Found infinite path length because the graph is not connected",
        ));
    }
    Ok(result.diameter)
}

/// Return the radius of the graph.
#[pyfunction]
pub fn radius(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<usize> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    let (connected, result) = py.allow_threads(|| {
        let c = fnx_algorithms::is_connected(inner);
        let r = fnx_algorithms::distance_measures(inner);
        (c.is_connected, r)
    });
    if !connected {
        return Err(NetworkXError::new_err(
            "Found infinite path length because the graph is not connected",
        ));
    }
    Ok(result.radius)
}

/// Return the center of the graph.
#[pyfunction]
pub fn center(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<Vec<PyObject>> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    let (connected, result) = py.allow_threads(|| {
        let c = fnx_algorithms::is_connected(inner);
        let r = fnx_algorithms::distance_measures(inner);
        (c.is_connected, r)
    });
    if !connected {
        return Err(NetworkXError::new_err(
            "Found infinite path length because the graph is not connected",
        ));
    }
    Ok(result
        .center
        .iter()
        .map(|n| gr.py_node_key(py, n))
        .collect())
}

/// Return the periphery of the graph.
#[pyfunction]
pub fn periphery(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<Vec<PyObject>> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    let (connected, result) = py.allow_threads(|| {
        let c = fnx_algorithms::is_connected(inner);
        let r = fnx_algorithms::distance_measures(inner);
        (c.is_connected, r)
    });
    if !connected {
        return Err(NetworkXError::new_err(
            "Found infinite path length because the graph is not connected",
        ));
    }
    Ok(result
        .periphery
        .iter()
        .map(|n| gr.py_node_key(py, n))
        .collect())
}

// ===========================================================================
// Tree, forest, bipartite, coloring, core algorithms
// ===========================================================================

/// Return True if the graph is a tree.
#[pyfunction]
pub fn is_tree(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<bool> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    Ok(py.allow_threads(|| fnx_algorithms::is_tree(inner).is_tree))
}

/// Return True if the graph is a forest.
#[pyfunction]
pub fn is_forest(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<bool> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    Ok(py.allow_threads(|| fnx_algorithms::is_forest(inner).is_forest))
}

/// Return True if the graph is bipartite.
#[pyfunction]
pub fn is_bipartite(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<bool> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    Ok(py.allow_threads(|| fnx_algorithms::is_bipartite(inner).is_bipartite))
}

/// Return the two bipartite node sets.
#[pyfunction]
pub fn bipartite_sets(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
) -> PyResult<(Vec<PyObject>, Vec<PyObject>)> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    let result = py.allow_threads(|| fnx_algorithms::bipartite_sets(inner));
    if !result.is_bipartite {
        return Err(NetworkXError::new_err("Graph is not bipartite."));
    }
    let a: Vec<PyObject> = result.set_a.iter().map(|n| gr.py_node_key(py, n)).collect();
    let b: Vec<PyObject> = result.set_b.iter().map(|n| gr.py_node_key(py, n)).collect();
    Ok((a, b))
}

/// Return a greedy graph coloring as a dict mapping node -> color.
#[pyfunction]
pub fn greedy_color(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<Py<PyDict>> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    let result = py.allow_threads(|| fnx_algorithms::greedy_color(inner));
    let dict = PyDict::new(py);
    for nc in &result.coloring {
        dict.set_item(gr.py_node_key(py, &nc.node), nc.color)?;
    }
    Ok(dict.unbind())
}

/// Return the core number for each node.
#[pyfunction]
pub fn core_number(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<Py<PyDict>> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    let result = py.allow_threads(|| fnx_algorithms::core_number(inner));
    let dict = PyDict::new(py);
    for nc in &result.core_numbers {
        dict.set_item(gr.py_node_key(py, &nc.node), nc.core)?;
    }
    Ok(dict.unbind())
}

/// Return a minimum spanning tree or forest on an undirected graph.
///
/// Parameters
/// ----------
/// G : Graph or DiGraph
///     The input graph.
/// weight : str, optional
///     Edge data key to use as weight (default ``'weight'``).
#[pyfunction]
#[pyo3(signature = (g, weight="weight"))]
pub fn minimum_spanning_tree(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    weight: &str,
) -> PyResult<PyGraph> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    let w = weight.to_owned();
    let result = py.allow_threads(move || fnx_algorithms::minimum_spanning_tree(inner, &w));
    let mut new_graph = PyGraph::new_empty(py)?;

    // Add all nodes from original graph
    for node in inner.nodes_ordered() {
        new_graph.inner.add_node(node.to_owned());
        if let Some(py_key) = gr.node_key_map().get(node) {
            new_graph
                .node_key_map
                .insert(node.to_owned(), py_key.clone_ref(py));
        }
    }
    // Add MST edges
    for edge in &result.edges {
        let _ = new_graph
            .inner
            .add_edge(edge.left.clone(), edge.right.clone());
        let ek = PyGraph::edge_key(&edge.left, &edge.right);
        if let Some(attrs) = gr.edge_attrs_for_undirected(&edge.left, &edge.right) {
            new_graph
                .edge_py_attrs
                .insert(ek, attrs.bind(py).copy()?.unbind());
        }
    }
    Ok(new_graph)
}

/// Return a maximum spanning tree using Kruskal's algorithm.
#[pyfunction]
#[pyo3(signature = (g, weight="weight"))]
pub fn maximum_spanning_tree(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    weight: &str,
) -> PyResult<PyGraph> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    let w = weight.to_owned();
    let result = py.allow_threads(move || fnx_algorithms::maximum_spanning_tree(inner, &w));
    let mut new_graph = PyGraph::new_empty(py)?;

    for node in inner.nodes_ordered() {
        new_graph.inner.add_node(node.to_owned());
        if let Some(py_key) = gr.node_key_map().get(node) {
            new_graph
                .node_key_map
                .insert(node.to_owned(), py_key.clone_ref(py));
        }
    }
    for edge in &result.edges {
        let _ = new_graph
            .inner
            .add_edge(edge.left.clone(), edge.right.clone());
        let ek = PyGraph::edge_key(&edge.left, &edge.right);
        if let Some(attrs) = gr.edge_attrs_for_undirected(&edge.left, &edge.right) {
            new_graph
                .edge_py_attrs
                .insert(ek, attrs.bind(py).copy()?.unbind());
        }
    }
    Ok(new_graph)
}

// ===========================================================================
// Euler algorithms
// ===========================================================================

/// Return True if the graph is Eulerian.
#[pyfunction]
pub fn is_eulerian(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<bool> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    Ok(py.allow_threads(|| fnx_algorithms::is_eulerian(inner).is_eulerian))
}

/// Return True if the graph has an Eulerian path.
#[pyfunction]
pub fn has_eulerian_path(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<bool> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    Ok(py.allow_threads(|| fnx_algorithms::has_eulerian_path(inner).has_eulerian_path))
}

/// Return True if the graph is semi-Eulerian.
#[pyfunction]
pub fn is_semieulerian(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<bool> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    Ok(py.allow_threads(|| fnx_algorithms::is_semieulerian(inner).is_semieulerian))
}

/// Return an Eulerian circuit as a list of edge tuples.
#[pyfunction]
#[pyo3(signature = (g, source=None))]
pub fn eulerian_circuit(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    source: Option<&Bound<'_, PyAny>>,
) -> PyResult<Vec<(PyObject, PyObject)>> {
    let gr = extract_graph(g)?;
    let src = source.map(|s| node_key_to_string(py, s)).transpose()?;
    let inner = gr.undirected();
    let result = py.allow_threads(|| fnx_algorithms::eulerian_circuit(inner, src.as_deref()));
    match result {
        Some(r) => Ok(r
            .edges
            .iter()
            .map(|(u, v)| (gr.py_node_key(py, u), gr.py_node_key(py, v)))
            .collect()),
        None => Err(NetworkXError::new_err("G is not Eulerian.")),
    }
}

/// Return an Eulerian path as a list of edge tuples.
#[pyfunction]
#[pyo3(signature = (g, source=None))]
pub fn eulerian_path(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    source: Option<&Bound<'_, PyAny>>,
) -> PyResult<Vec<(PyObject, PyObject)>> {
    let gr = extract_graph(g)?;
    let src = source.map(|s| node_key_to_string(py, s)).transpose()?;
    let inner = gr.undirected();
    let result = py.allow_threads(|| fnx_algorithms::eulerian_path(inner, src.as_deref()));
    match result {
        Some(r) => Ok(r
            .edges
            .iter()
            .map(|(u, v)| (gr.py_node_key(py, u), gr.py_node_key(py, v)))
            .collect()),
        None => Err(NetworkXError::new_err("G has no Eulerian path.")),
    }
}

// ===========================================================================
// Path and cycle algorithms
// ===========================================================================

/// Return all simple paths between source and target.
#[pyfunction]
#[pyo3(signature = (g, source, target, cutoff=None))]
pub fn all_simple_paths(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    source: &Bound<'_, PyAny>,
    target: &Bound<'_, PyAny>,
    cutoff: Option<usize>,
) -> PyResult<Vec<Vec<PyObject>>> {
    let gr = extract_graph(g)?;
    let s = node_key_to_string(py, source)?;
    let t = node_key_to_string(py, target)?;
    let inner = gr.undirected();
    let result = py.allow_threads(|| fnx_algorithms::all_simple_paths(inner, &s, &t, cutoff));
    Ok(result
        .paths
        .iter()
        .map(|path| path.iter().map(|n| gr.py_node_key(py, n)).collect())
        .collect())
}

/// Return a list of cycles forming a basis for the cycle space.
/// Raises ``NetworkXNotImplemented`` on DiGraph.
#[pyfunction]
#[pyo3(signature = (g, root=None))]
pub fn cycle_basis(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    root: Option<&Bound<'_, PyAny>>,
) -> PyResult<Vec<Vec<PyObject>>> {
    let gr = extract_graph(g)?;
    require_undirected(&gr, "cycle_basis")?;
    let r = root.map(|r| node_key_to_string(py, r)).transpose()?;
    let inner = gr.undirected();
    let result = py.allow_threads(|| fnx_algorithms::cycle_basis(inner, r.as_deref()));
    Ok(result
        .cycles
        .iter()
        .map(|cycle| cycle.iter().map(|n| gr.py_node_key(py, n)).collect())
        .collect())
}

// ===========================================================================
// Graph efficiency measures
// ===========================================================================

/// Return the global efficiency of the graph.
#[pyfunction]
pub fn global_efficiency(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<f64> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    Ok(py.allow_threads(|| fnx_algorithms::global_efficiency(inner).efficiency))
}

/// Return the local efficiency of the graph.
#[pyfunction]
pub fn local_efficiency(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<f64> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    Ok(py.allow_threads(|| fnx_algorithms::local_efficiency(inner).efficiency))
}

// ===========================================================================
// BFS Traversal
// ===========================================================================

/// Iterate over edges in a breadth-first search starting at source.
#[pyfunction]
#[pyo3(signature = (g, source, reverse=false, depth_limit=None, sort_neighbors=None))]
pub fn bfs_edges(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    source: &Bound<'_, PyAny>,
    reverse: bool,
    depth_limit: Option<usize>,
    sort_neighbors: Option<&Bound<'_, PyAny>>,
) -> PyResult<Vec<(PyObject, PyObject)>> {
    let _ = (reverse, sort_neighbors); // accepted for API compat, not used
    let gr = extract_graph(g)?;
    let source_key = node_key_to_string(py, source)?;
    if !gr.has_node(&source_key) {
        return Err(NodeNotFound::new_err(format!(
            "The node {} is not in the graph.",
            source.repr()?
        )));
    }

    let edges = if gr.is_directed() {
        if let GraphRef::Directed { dg, .. } = &gr {
            fnx_algorithms::bfs_edges_directed(&dg.inner, &source_key, depth_limit)
        } else {
            unreachable!()
        }
    } else {
        let inner = gr.undirected();
        py.allow_threads(|| fnx_algorithms::bfs_edges(inner, &source_key, depth_limit))
    };

    Ok(edges
        .into_iter()
        .map(|(u, v)| (gr.py_node_key(py, &u), gr.py_node_key(py, &v)))
        .collect())
}

/// Return an oriented tree constructed from a breadth-first search from source.
#[pyfunction]
#[pyo3(signature = (g, source, reverse=false, depth_limit=None, sort_neighbors=None))]
pub fn bfs_tree(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    source: &Bound<'_, PyAny>,
    reverse: bool,
    depth_limit: Option<usize>,
    sort_neighbors: Option<&Bound<'_, PyAny>>,
) -> PyResult<crate::digraph::PyDiGraph> {
    let _ = (reverse, sort_neighbors);
    let gr = extract_graph(g)?;
    let source_key = node_key_to_string(py, source)?;
    if !gr.has_node(&source_key) {
        return Err(NodeNotFound::new_err(format!(
            "The node {} is not in the graph.",
            source.repr()?
        )));
    }

    let edges = if gr.is_directed() {
        if let GraphRef::Directed { dg, .. } = &gr {
            fnx_algorithms::bfs_edges_directed(&dg.inner, &source_key, depth_limit)
        } else {
            unreachable!()
        }
    } else {
        let inner = gr.undirected();
        py.allow_threads(|| fnx_algorithms::bfs_edges(inner, &source_key, depth_limit))
    };

    let mut tree = crate::digraph::PyDiGraph::new_empty(py)?;
    let source_py = source.clone().unbind();
    let source_s = source_key.clone();
    tree.inner.add_node(&source_s);
    tree.node_key_map.insert(source_s.clone(), source_py);
    tree.node_py_attrs
        .insert(source_s, pyo3::types::PyDict::new(py).unbind());

    for (u, v) in &edges {
        if !tree.inner.has_node(v) {
            tree.inner.add_node(v);
            tree.node_key_map
                .insert(v.clone(), gr.py_node_key(py, v));
            tree.node_py_attrs
                .insert(v.clone(), pyo3::types::PyDict::new(py).unbind());
        }
        let _ = tree.inner.add_edge(u, v);
        tree.edge_py_attrs
            .insert((u.clone(), v.clone()), pyo3::types::PyDict::new(py).unbind());
    }

    Ok(tree)
}

/// Return an iterator of predecessors in breadth-first search from source.
#[pyfunction]
#[pyo3(signature = (g, source, depth_limit=None, sort_neighbors=None))]
pub fn bfs_predecessors(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    source: &Bound<'_, PyAny>,
    depth_limit: Option<usize>,
    sort_neighbors: Option<&Bound<'_, PyAny>>,
) -> PyResult<Vec<(PyObject, PyObject)>> {
    let _ = sort_neighbors;
    let gr = extract_graph(g)?;
    let source_key = node_key_to_string(py, source)?;
    if !gr.has_node(&source_key) {
        return Err(NodeNotFound::new_err(format!(
            "The node {} is not in the graph.",
            source.repr()?
        )));
    }

    let preds = if gr.is_directed() {
        if let GraphRef::Directed { dg, .. } = &gr {
            fnx_algorithms::bfs_predecessors_directed(&dg.inner, &source_key, depth_limit)
        } else {
            unreachable!()
        }
    } else {
        let inner = gr.undirected();
        py.allow_threads(|| fnx_algorithms::bfs_predecessors(inner, &source_key, depth_limit))
    };

    Ok(preds
        .into_iter()
        .map(|(child, parent)| (gr.py_node_key(py, &child), gr.py_node_key(py, &parent)))
        .collect())
}

/// Return an iterator of successors in breadth-first search from source.
#[pyfunction]
#[pyo3(signature = (g, source, depth_limit=None, sort_neighbors=None))]
pub fn bfs_successors(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    source: &Bound<'_, PyAny>,
    depth_limit: Option<usize>,
    sort_neighbors: Option<&Bound<'_, PyAny>>,
) -> PyResult<Vec<(PyObject, Vec<PyObject>)>> {
    let _ = sort_neighbors;
    let gr = extract_graph(g)?;
    let source_key = node_key_to_string(py, source)?;
    if !gr.has_node(&source_key) {
        return Err(NodeNotFound::new_err(format!(
            "The node {} is not in the graph.",
            source.repr()?
        )));
    }

    let succs = if gr.is_directed() {
        if let GraphRef::Directed { dg, .. } = &gr {
            fnx_algorithms::bfs_successors_directed(&dg.inner, &source_key, depth_limit)
        } else {
            unreachable!()
        }
    } else {
        let inner = gr.undirected();
        py.allow_threads(|| fnx_algorithms::bfs_successors(inner, &source_key, depth_limit))
    };

    Ok(succs
        .into_iter()
        .map(|(parent, children)| {
            let py_parent = gr.py_node_key(py, &parent);
            let py_children: Vec<PyObject> = children.iter().map(|c| gr.py_node_key(py, c)).collect();
            (py_parent, py_children)
        })
        .collect())
}

/// Return an iterator of all the layers in breadth-first search from sources.
#[pyfunction]
#[pyo3(signature = (g, sources))]
pub fn bfs_layers(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    sources: &Bound<'_, PyAny>,
) -> PyResult<Vec<Vec<PyObject>>> {
    let gr = extract_graph(g)?;
    // sources can be a single node or iterable of nodes
    let source_key = node_key_to_string(py, sources)?;
    if gr.has_node(&source_key) {
        // Single source
        let layers = if gr.is_directed() {
            if let GraphRef::Directed { dg, .. } = &gr {
                fnx_algorithms::bfs_layers_directed(&dg.inner, &source_key)
            } else {
                unreachable!()
            }
        } else {
            let inner = gr.undirected();
            py.allow_threads(|| fnx_algorithms::bfs_layers(inner, &source_key))
        };
        return Ok(layers
            .into_iter()
            .map(|layer| layer.iter().map(|n| gr.py_node_key(py, n)).collect())
            .collect());
    }

    // If it's iterable, try extracting nodes from it
    // For now we support single source only (most common usage)
    Err(NodeNotFound::new_err(format!(
        "The node {} is not in the graph.",
        sources.repr()?
    )))
}

/// Return all nodes at a fixed distance from source in G.
#[pyfunction]
pub fn descendants_at_distance(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    source: &Bound<'_, PyAny>,
    distance: usize,
) -> PyResult<pyo3::Py<pyo3::types::PyFrozenSet>> {
    let gr = extract_graph(g)?;
    let source_key = node_key_to_string(py, source)?;
    if !gr.has_node(&source_key) {
        return Err(NodeNotFound::new_err(format!(
            "The node {} is not in the graph.",
            source.repr()?
        )));
    }

    let nodes = if gr.is_directed() {
        if let GraphRef::Directed { dg, .. } = &gr {
            fnx_algorithms::descendants_at_distance_directed(&dg.inner, &source_key, distance)
        } else {
            unreachable!()
        }
    } else {
        let inner = gr.undirected();
        py.allow_threads(|| fnx_algorithms::descendants_at_distance(inner, &source_key, distance))
    };

    let py_nodes: Vec<PyObject> = nodes.iter().map(|n| gr.py_node_key(py, n)).collect();
    pyo3::types::PyFrozenSet::new(py, &py_nodes).map(|s| s.unbind())
}

// ===========================================================================
// DFS Traversal
// ===========================================================================

/// Iterate over edges in a depth-first search starting at source.
#[pyfunction]
#[pyo3(signature = (g, source=None, depth_limit=None, sort_neighbors=None))]
pub fn dfs_edges(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    source: Option<&Bound<'_, PyAny>>,
    depth_limit: Option<usize>,
    sort_neighbors: Option<&Bound<'_, PyAny>>,
) -> PyResult<Vec<(PyObject, PyObject)>> {
    let _ = sort_neighbors;
    let gr = extract_graph(g)?;

    let source_key = match source {
        Some(s) => {
            let k = node_key_to_string(py, s)?;
            if !gr.has_node(&k) {
                return Err(NodeNotFound::new_err(format!(
                    "The node {} is not in the graph.",
                    s.repr()?
                )));
            }
            k
        }
        None => {
            // Use first node as source (NetworkX iterates all components)
            let nodes = gr.undirected().nodes_ordered();
            if nodes.is_empty() {
                return Ok(Vec::new());
            }
            nodes[0].to_owned()
        }
    };

    let edges = if gr.is_directed() {
        if let GraphRef::Directed { dg, .. } = &gr {
            fnx_algorithms::dfs_edges_directed(&dg.inner, &source_key, depth_limit)
        } else {
            unreachable!()
        }
    } else {
        let inner = gr.undirected();
        py.allow_threads(|| fnx_algorithms::dfs_edges(inner, &source_key, depth_limit))
    };

    Ok(edges
        .into_iter()
        .map(|(u, v)| (gr.py_node_key(py, &u), gr.py_node_key(py, &v)))
        .collect())
}

/// Return an oriented tree constructed from a depth-first search from source.
#[pyfunction]
#[pyo3(signature = (g, source=None, depth_limit=None, sort_neighbors=None))]
pub fn dfs_tree(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    source: Option<&Bound<'_, PyAny>>,
    depth_limit: Option<usize>,
    sort_neighbors: Option<&Bound<'_, PyAny>>,
) -> PyResult<crate::digraph::PyDiGraph> {
    let _ = sort_neighbors;
    let edge_list = dfs_edges(py, g, source, depth_limit, None)?;

    let gr = extract_graph(g)?;
    let mut tree = crate::digraph::PyDiGraph::new_empty(py)?;

    if let Some(s) = source {
        let sk = node_key_to_string(py, s)?;
        tree.inner.add_node(&sk);
        tree.node_key_map.insert(sk.clone(), s.clone().unbind());
        tree.node_py_attrs
            .insert(sk, pyo3::types::PyDict::new(py).unbind());
    } else {
        for node in gr.undirected().nodes_ordered() {
            tree.inner.add_node(node);
            tree.node_key_map
                .insert(node.to_owned(), gr.py_node_key(py, node));
            tree.node_py_attrs
                .insert(node.to_owned(), pyo3::types::PyDict::new(py).unbind());
        }
    }

    for (u_py, v_py) in &edge_list {
        let u_key = node_key_to_string(py, u_py.bind(py))?;
        let v_key = node_key_to_string(py, v_py.bind(py))?;
        if !tree.inner.has_node(&v_key) {
            tree.inner.add_node(&v_key);
            tree.node_key_map.insert(v_key.clone(), v_py.clone_ref(py));
            tree.node_py_attrs
                .insert(v_key.clone(), pyo3::types::PyDict::new(py).unbind());
        }
        let _ = tree.inner.add_edge(&u_key, &v_key);
        tree.edge_py_attrs
            .insert((u_key, v_key), pyo3::types::PyDict::new(py).unbind());
    }

    Ok(tree)
}

/// Return dict of predecessors in depth-first search from source.
#[pyfunction]
#[pyo3(signature = (g, source=None, depth_limit=None, sort_neighbors=None))]
pub fn dfs_predecessors(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    source: Option<&Bound<'_, PyAny>>,
    depth_limit: Option<usize>,
    sort_neighbors: Option<&Bound<'_, PyAny>>,
) -> PyResult<Py<PyDict>> {
    let _ = sort_neighbors;
    let gr = extract_graph(g)?;

    let source_key = match source {
        Some(s) => {
            let k = node_key_to_string(py, s)?;
            if !gr.has_node(&k) {
                return Err(NodeNotFound::new_err(format!(
                    "The node {} is not in the graph.",
                    s.repr()?
                )));
            }
            k
        }
        None => {
            let nodes = gr.undirected().nodes_ordered();
            if nodes.is_empty() {
                return Ok(PyDict::new(py).unbind());
            }
            nodes[0].to_owned()
        }
    };

    let preds = if gr.is_directed() {
        if let GraphRef::Directed { dg, .. } = &gr {
            fnx_algorithms::dfs_predecessors_directed(&dg.inner, &source_key, depth_limit)
        } else {
            unreachable!()
        }
    } else {
        let inner = gr.undirected();
        py.allow_threads(|| fnx_algorithms::dfs_predecessors(inner, &source_key, depth_limit))
    };

    let dict = PyDict::new(py);
    for (child, parent) in &preds {
        dict.set_item(gr.py_node_key(py, child), gr.py_node_key(py, parent))?;
    }
    Ok(dict.unbind())
}

/// Return dict of successors in depth-first search from source.
#[pyfunction]
#[pyo3(signature = (g, source=None, depth_limit=None, sort_neighbors=None))]
pub fn dfs_successors(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    source: Option<&Bound<'_, PyAny>>,
    depth_limit: Option<usize>,
    sort_neighbors: Option<&Bound<'_, PyAny>>,
) -> PyResult<Py<PyDict>> {
    let _ = sort_neighbors;
    let gr = extract_graph(g)?;

    let source_key = match source {
        Some(s) => {
            let k = node_key_to_string(py, s)?;
            if !gr.has_node(&k) {
                return Err(NodeNotFound::new_err(format!(
                    "The node {} is not in the graph.",
                    s.repr()?
                )));
            }
            k
        }
        None => {
            let nodes = gr.undirected().nodes_ordered();
            if nodes.is_empty() {
                return Ok(PyDict::new(py).unbind());
            }
            nodes[0].to_owned()
        }
    };

    let succs = if gr.is_directed() {
        if let GraphRef::Directed { dg, .. } = &gr {
            fnx_algorithms::dfs_successors_directed(&dg.inner, &source_key, depth_limit)
        } else {
            unreachable!()
        }
    } else {
        let inner = gr.undirected();
        py.allow_threads(|| fnx_algorithms::dfs_successors(inner, &source_key, depth_limit))
    };

    let dict = PyDict::new(py);
    for (parent, children) in &succs {
        let py_children: Vec<PyObject> = children.iter().map(|c| gr.py_node_key(py, c)).collect();
        dict.set_item(gr.py_node_key(py, parent), py_children)?;
    }
    Ok(dict.unbind())
}

/// Generate nodes in a depth-first-search pre-ordering starting at source.
#[pyfunction]
#[pyo3(signature = (g, source=None, depth_limit=None, sort_neighbors=None))]
pub fn dfs_preorder_nodes(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    source: Option<&Bound<'_, PyAny>>,
    depth_limit: Option<usize>,
    sort_neighbors: Option<&Bound<'_, PyAny>>,
) -> PyResult<Vec<PyObject>> {
    let _ = sort_neighbors;
    let gr = extract_graph(g)?;

    let source_key = match source {
        Some(s) => {
            let k = node_key_to_string(py, s)?;
            if !gr.has_node(&k) {
                return Err(NodeNotFound::new_err(format!(
                    "The node {} is not in the graph.",
                    s.repr()?
                )));
            }
            k
        }
        None => {
            let nodes = gr.undirected().nodes_ordered();
            if nodes.is_empty() {
                return Ok(Vec::new());
            }
            nodes[0].to_owned()
        }
    };

    let nodes = if gr.is_directed() {
        if let GraphRef::Directed { dg, .. } = &gr {
            fnx_algorithms::dfs_preorder_nodes_directed(&dg.inner, &source_key, depth_limit)
        } else {
            unreachable!()
        }
    } else {
        let inner = gr.undirected();
        py.allow_threads(|| fnx_algorithms::dfs_preorder_nodes(inner, &source_key, depth_limit))
    };

    Ok(nodes.iter().map(|n| gr.py_node_key(py, n)).collect())
}

/// Generate nodes in a depth-first-search post-ordering starting at source.
#[pyfunction]
#[pyo3(signature = (g, source=None, depth_limit=None, sort_neighbors=None))]
pub fn dfs_postorder_nodes(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    source: Option<&Bound<'_, PyAny>>,
    depth_limit: Option<usize>,
    sort_neighbors: Option<&Bound<'_, PyAny>>,
) -> PyResult<Vec<PyObject>> {
    let _ = sort_neighbors;
    let gr = extract_graph(g)?;

    let source_key = match source {
        Some(s) => {
            let k = node_key_to_string(py, s)?;
            if !gr.has_node(&k) {
                return Err(NodeNotFound::new_err(format!(
                    "The node {} is not in the graph.",
                    s.repr()?
                )));
            }
            k
        }
        None => {
            let nodes = gr.undirected().nodes_ordered();
            if nodes.is_empty() {
                return Ok(Vec::new());
            }
            nodes[0].to_owned()
        }
    };

    let nodes = if gr.is_directed() {
        if let GraphRef::Directed { dg, .. } = &gr {
            fnx_algorithms::dfs_postorder_nodes_directed(&dg.inner, &source_key, depth_limit)
        } else {
            unreachable!()
        }
    } else {
        let inner = gr.undirected();
        py.allow_threads(|| fnx_algorithms::dfs_postorder_nodes(inner, &source_key, depth_limit))
    };

    Ok(nodes.iter().map(|n| gr.py_node_key(py, n)).collect())
}

// ===========================================================================
// DAG Algorithms
// ===========================================================================

/// Return a topological sort of the nodes in a directed graph.
///
/// Raises ``NetworkXError`` if the graph is undirected.
/// Raises ``HasACycle`` if the graph contains a cycle.
#[pyfunction]
pub fn topological_sort(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
) -> PyResult<Vec<PyObject>> {
    let gr = extract_graph(g)?;
    if !gr.is_directed() {
        return Err(NetworkXError::new_err(
            "Topological sort not defined on undirected graphs.",
        ));
    }
    if let GraphRef::Directed { dg, .. } = &gr {
        match fnx_algorithms::topological_sort(&dg.inner) {
            Some(result) => Ok(result
                .order
                .iter()
                .map(|n| gr.py_node_key(py, n))
                .collect()),
            None => Err(crate::HasACycle::new_err(
                "Graph contains a cycle, topological sort is not possible.",
            )),
        }
    } else {
        unreachable!()
    }
}

/// Return a list of generations in topological order.
///
/// Each generation is a list of nodes with the same topological depth.
/// Matches `networkx.topological_generations`.
#[pyfunction]
pub fn topological_generations(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
) -> PyResult<Vec<Vec<PyObject>>> {
    let gr = extract_graph(g)?;
    if !gr.is_directed() {
        return Err(NetworkXError::new_err(
            "Topological generations not defined on undirected graphs.",
        ));
    }
    if let GraphRef::Directed { dg, .. } = &gr {
        match fnx_algorithms::topological_generations(&dg.inner) {
            Some(result) => {
                let gens: Vec<Vec<PyObject>> = result
                    .generations
                    .iter()
                    .map(|g| g.iter().map(|n| gr.py_node_key(py, n)).collect())
                    .collect();
                Ok(gens)
            }
            None => Err(crate::HasACycle::new_err(
                "Graph contains a cycle, topological generations is not possible.",
            )),
        }
    } else {
        unreachable!()
    }
}

/// Return the longest path in a DAG.
///
/// Matches `networkx.dag_longest_path(G)`.
#[pyfunction]
pub fn dag_longest_path(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
) -> PyResult<Vec<PyObject>> {
    let gr = extract_graph(g)?;
    if !gr.is_directed() {
        return Err(NetworkXError::new_err(
            "dag_longest_path not defined on undirected graphs.",
        ));
    }
    if let GraphRef::Directed { dg, .. } = &gr {
        match fnx_algorithms::dag_longest_path(&dg.inner) {
            Some(path) => Ok(path.iter().map(|n| gr.py_node_key(py, n)).collect()),
            None => Err(crate::HasACycle::new_err(
                "Graph contains a cycle.",
            )),
        }
    } else {
        unreachable!()
    }
}

/// Return the length of the longest path in a DAG.
///
/// Matches `networkx.dag_longest_path_length(G)`.
#[pyfunction]
pub fn dag_longest_path_length(
    _py: Python<'_>,
    g: &Bound<'_, PyAny>,
) -> PyResult<usize> {
    let gr = extract_graph(g)?;
    if !gr.is_directed() {
        return Err(NetworkXError::new_err(
            "dag_longest_path_length not defined on undirected graphs.",
        ));
    }
    if let GraphRef::Directed { dg, .. } = &gr {
        match fnx_algorithms::dag_longest_path_length(&dg.inner) {
            Some(length) => Ok(length),
            None => Err(crate::HasACycle::new_err(
                "Graph contains a cycle.",
            )),
        }
    } else {
        unreachable!()
    }
}

/// Return a topological ordering, breaking ties lexicographically.
///
/// Matches `networkx.lexicographic_topological_sort(G)`.
#[pyfunction]
pub fn lexicographic_topological_sort(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
) -> PyResult<Vec<PyObject>> {
    let gr = extract_graph(g)?;
    if !gr.is_directed() {
        return Err(NetworkXError::new_err(
            "Lexicographic topological sort not defined on undirected graphs.",
        ));
    }
    if let GraphRef::Directed { dg, .. } = &gr {
        match fnx_algorithms::lexicographic_topological_sort(&dg.inner) {
            Some(order) => Ok(order.iter().map(|n| gr.py_node_key(py, n)).collect()),
            None => Err(crate::HasACycle::new_err(
                "Graph contains a cycle, topological sort is not possible.",
            )),
        }
    } else {
        unreachable!()
    }
}

/// Return True if the directed graph G is a directed acyclic graph (DAG).
#[pyfunction]
pub fn is_directed_acyclic_graph(
    _py: Python<'_>,
    g: &Bound<'_, PyAny>,
) -> PyResult<bool> {
    let gr = extract_graph(g)?;
    if !gr.is_directed() {
        return Ok(false);
    }
    if let GraphRef::Directed { dg, .. } = &gr {
        Ok(fnx_algorithms::is_directed_acyclic_graph(&dg.inner))
    } else {
        unreachable!()
    }
}

/// Return all ancestors of node in the directed graph.
#[pyfunction]
pub fn ancestors(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    source: &Bound<'_, PyAny>,
) -> PyResult<pyo3::Py<pyo3::types::PyFrozenSet>> {
    let gr = extract_graph(g)?;
    if !gr.is_directed() {
        return Err(NetworkXError::new_err(
            "ancestors() is not defined for undirected graphs.",
        ));
    }
    let source_key = node_key_to_string(py, source)?;
    if !gr.has_node(&source_key) {
        return Err(NodeNotFound::new_err(format!(
            "The node {} is not in the graph.",
            source.repr()?
        )));
    }

    if let GraphRef::Directed { dg, .. } = &gr {
        let result = fnx_algorithms::ancestors(&dg.inner, &source_key);
        let py_nodes: Vec<PyObject> = result.iter().map(|n| gr.py_node_key(py, n)).collect();
        pyo3::types::PyFrozenSet::new(py, &py_nodes).map(|s| s.unbind())
    } else {
        unreachable!()
    }
}

/// Return all descendants of node in the directed graph.
#[pyfunction]
pub fn descendants(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    source: &Bound<'_, PyAny>,
) -> PyResult<pyo3::Py<pyo3::types::PyFrozenSet>> {
    let gr = extract_graph(g)?;
    if !gr.is_directed() {
        return Err(NetworkXError::new_err(
            "descendants() is not defined for undirected graphs.",
        ));
    }
    let source_key = node_key_to_string(py, source)?;
    if !gr.has_node(&source_key) {
        return Err(NodeNotFound::new_err(format!(
            "The node {} is not in the graph.",
            source.repr()?
        )));
    }

    if let GraphRef::Directed { dg, .. } = &gr {
        let result = fnx_algorithms::descendants(&dg.inner, &source_key);
        let py_nodes: Vec<PyObject> = result.iter().map(|n| gr.py_node_key(py, n)).collect();
        pyo3::types::PyFrozenSet::new(py, &py_nodes).map(|s| s.unbind())
    } else {
        unreachable!()
    }
}

// ===========================================================================
// All shortest paths
// ===========================================================================

/// Return all shortest paths between source and target.
///
/// Matches `networkx.all_shortest_paths(G, source, target, weight=None, method='dijkstra')`.
#[pyfunction]
#[pyo3(signature = (g, source, target, weight=None, method=None))]
pub fn all_shortest_paths(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    source: &Bound<'_, PyAny>,
    target: &Bound<'_, PyAny>,
    weight: Option<&str>,
    method: Option<&str>,
) -> PyResult<Vec<Vec<PyObject>>> {
    let _ = method; // method selection not yet differentiated (both use same impl)
    let gr = extract_graph(g)?;
    let source_key = node_key_to_string(py, source)?;
    let target_key = node_key_to_string(py, target)?;

    if !gr.has_node(&source_key) {
        return Err(NodeNotFound::new_err(format!(
            "Source node {} is not in G",
            source.repr()?
        )));
    }
    if !gr.has_node(&target_key) {
        return Err(NodeNotFound::new_err(format!(
            "Target node {} is not in G",
            target.repr()?
        )));
    }

    let paths = if gr.is_directed() {
        if weight.is_some() {
            return Err(pyo3::exceptions::PyNotImplementedError::new_err(
                "weighted all_shortest_paths is not yet supported for DiGraph",
            ));
        }
        if let GraphRef::Directed { dg, .. } = &gr {
            fnx_algorithms::all_shortest_paths_directed(&dg.inner, &source_key, &target_key)
        } else {
            unreachable!()
        }
    } else {
        let inner = gr.undirected();
        match weight {
            Some(w) => {
                py.allow_threads(|| {
                    fnx_algorithms::all_shortest_paths_weighted(inner, &source_key, &target_key, w)
                })
            }
            None => {
                py.allow_threads(|| {
                    fnx_algorithms::all_shortest_paths(inner, &source_key, &target_key)
                })
            }
        }
    };

    if paths.is_empty() {
        return Err(NetworkXNoPath::new_err(format!(
            "No path between {} and {}.",
            source.repr()?,
            target.repr()?
        )));
    }

    Ok(paths
        .iter()
        .map(|path| path.iter().map(|n| gr.py_node_key(py, n)).collect())
        .collect())
}

// ===========================================================================
// Complement
// ===========================================================================

/// Return the graph complement of G.
///
/// The complement contains the same nodes but has edges where G does not.
/// Matches `networkx.complement(G)`.
#[pyfunction]
pub fn complement(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<PyObject> {
    if let Ok(pg) = g.extract::<PyRef<'_, PyGraph>>() {
        let result = fnx_algorithms::complement(&pg.inner);

        let mut py_graph = PyGraph::new_empty(py)?;
        // Add nodes
        for node in result.nodes_ordered() {
            let py_key = pg.py_node_key(py, node);
            py_graph.node_key_map.insert(node.to_owned(), py_key);
            py_graph.node_py_attrs.insert(
                node.to_owned(),
                pyo3::types::PyDict::new(py).unbind(),
            );
            py_graph.inner.add_node(node);
        }
        // Add edges from the complement result
        for edge in result.edges_ordered() {
            let _ = py_graph.inner.add_edge(&edge.left, &edge.right);
            let ek = PyGraph::edge_key(&edge.left, &edge.right);
            py_graph
                .edge_py_attrs
                .insert(ek, pyo3::types::PyDict::new(py).unbind());
        }

        Ok(py_graph.into_pyobject(py)?.into_any().unbind())
    } else if let Ok(dg) = g.extract::<PyRef<'_, PyDiGraph>>() {
        let result = fnx_algorithms::complement_directed(&dg.inner);

        let mut py_dg = PyDiGraph::new_empty(py)?;
        for node in result.nodes_ordered() {
            let py_key = dg.py_node_key(py, node);
            py_dg.node_key_map.insert(node.to_owned(), py_key);
            py_dg.node_py_attrs.insert(
                node.to_owned(),
                pyo3::types::PyDict::new(py).unbind(),
            );
            py_dg.inner.add_node(node);
        }
        for edge in result.edges_ordered() {
            let _ = py_dg.inner.add_edge(&edge.left, &edge.right);
            py_dg.edge_py_attrs.insert(
                (edge.left, edge.right),
                pyo3::types::PyDict::new(py).unbind(),
            );
        }

        Ok(py_dg.into_pyobject(py)?.into_any().unbind())
    } else {
        Err(pyo3::exceptions::PyTypeError::new_err(
            "expected Graph or DiGraph",
        ))
    }
}

// ===========================================================================
// Average Degree Connectivity
// ===========================================================================

/// Compute the average degree connectivity of a graph.
///
/// Matches `networkx.average_degree_connectivity(G)`.
#[pyfunction]
pub fn average_degree_connectivity(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
) -> PyResult<PyObject> {
    let gr = extract_graph(g)?;
    require_undirected(&gr, "average_degree_connectivity")?;
    let inner = gr.undirected();
    let result = py.allow_threads(|| fnx_algorithms::average_degree_connectivity(inner));
    let dict = pyo3::types::PyDict::new(py);
    for (k, v) in &result {
        dict.set_item(*k, *v)?;
    }
    Ok(dict.into_any().unbind())
}

// ===========================================================================
// Rich-Club Coefficient
// ===========================================================================

/// Compute the rich-club coefficient for the graph.
///
/// Matches `networkx.rich_club_coefficient(G, normalized=False)`.
#[pyfunction]
pub fn rich_club_coefficient(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
) -> PyResult<PyObject> {
    let gr = extract_graph(g)?;
    require_undirected(&gr, "rich_club_coefficient")?;
    let inner = gr.undirected();
    let result = py.allow_threads(|| fnx_algorithms::rich_club_coefficient(inner));
    let dict = pyo3::types::PyDict::new(py);
    for (k, v) in &result {
        dict.set_item(*k, *v)?;
    }
    Ok(dict.into_any().unbind())
}

// ===========================================================================
// s-metric
// ===========================================================================

/// Compute the s-metric of a graph.
///
/// Matches `networkx.s_metric(G, normalized=False)`.
#[pyfunction]
pub fn s_metric(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
) -> PyResult<f64> {
    let gr = extract_graph(g)?;
    require_undirected(&gr, "s_metric")?;
    let inner = gr.undirected();
    Ok(py.allow_threads(|| fnx_algorithms::s_metric(inner)))
}

// ===========================================================================
// All-pairs shortest paths
// ===========================================================================

/// Return all shortest paths between all pairs of nodes.
#[pyfunction]
#[pyo3(signature = (g, cutoff=None))]
pub fn all_pairs_shortest_path(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    cutoff: Option<usize>,
) -> PyResult<PyObject> {
    let gr = extract_graph(g)?;
    require_undirected(&gr, "all_pairs_shortest_path")?;
    let inner = gr.undirected();
    let result = py.allow_threads(|| fnx_algorithms::all_pairs_shortest_path(inner, cutoff));
    let outer_dict = pyo3::types::PyDict::new(py);
    for (source, targets) in &result {
        let inner_dict = pyo3::types::PyDict::new(py);
        for (target, path) in targets {
            let py_path: Vec<PyObject> = path.iter().map(|n| gr.py_node_key(py, n)).collect();
            inner_dict.set_item(gr.py_node_key(py, target), py_path)?;
        }
        outer_dict.set_item(gr.py_node_key(py, source), inner_dict)?;
    }
    Ok(outer_dict.into_any().unbind())
}

/// Return shortest path lengths between all pairs of nodes.
#[pyfunction]
#[pyo3(signature = (g, cutoff=None))]
pub fn all_pairs_shortest_path_length(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    cutoff: Option<usize>,
) -> PyResult<PyObject> {
    let gr = extract_graph(g)?;
    require_undirected(&gr, "all_pairs_shortest_path_length")?;
    let inner = gr.undirected();
    let result = py.allow_threads(|| fnx_algorithms::all_pairs_shortest_path_length(inner, cutoff));
    let outer_dict = pyo3::types::PyDict::new(py);
    for (source, targets) in &result {
        let inner_dict = pyo3::types::PyDict::new(py);
        for (target, length) in targets {
            inner_dict.set_item(gr.py_node_key(py, target), *length)?;
        }
        outer_dict.set_item(gr.py_node_key(py, source), inner_dict)?;
    }
    Ok(outer_dict.into_any().unbind())
}

// ===========================================================================
// Graph Predicates & Utilities
// ===========================================================================

/// Return whether the graph has no edges.
#[pyfunction]
pub fn is_empty(
    _py: Python<'_>,
    g: &Bound<'_, PyAny>,
) -> PyResult<bool> {
    let gr = extract_graph(g)?;
    match &gr {
        GraphRef::Undirected(pg) => Ok(fnx_algorithms::is_empty(&pg.inner)),
        GraphRef::Directed { dg, .. } => Ok(fnx_algorithms::is_empty_directed(&dg.inner)),
    }
}

/// Return the non-neighbors of a node.
#[pyfunction]
pub fn non_neighbors(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    v: &Bound<'_, PyAny>,
) -> PyResult<Vec<PyObject>> {
    let gr = extract_graph(g)?;
    require_undirected(&gr, "non_neighbors")?;
    let inner = gr.undirected();
    let node_key = node_key_to_string(py, v)?;
    let result = fnx_algorithms::non_neighbors(inner, &node_key);
    Ok(result.iter().map(|n| gr.py_node_key(py, n)).collect())
}

/// Return the number of maximal cliques containing each node.
#[pyfunction]
pub fn number_of_cliques(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
) -> PyResult<PyObject> {
    let gr = extract_graph(g)?;
    require_undirected(&gr, "number_of_cliques")?;
    let inner = gr.undirected();
    let result = py.allow_threads(|| fnx_algorithms::number_of_cliques(inner));
    let dict = pyo3::types::PyDict::new(py);
    for (node, count) in &result {
        dict.set_item(gr.py_node_key(py, node), *count)?;
    }
    Ok(dict.into_any().unbind())
}

// ===========================================================================
// Single-source shortest paths
// ===========================================================================

/// Return all shortest paths from source (unweighted BFS).
#[pyfunction]
#[pyo3(signature = (g, source, cutoff=None))]
pub fn single_source_shortest_path(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    source: &Bound<'_, PyAny>,
    cutoff: Option<usize>,
) -> PyResult<PyObject> {
    let gr = extract_graph(g)?;
    require_undirected(&gr, "single_source_shortest_path")?;
    let inner = gr.undirected();
    let source_key = node_key_to_string(py, source)?;
    let result = fnx_algorithms::single_source_shortest_path(inner, &source_key, cutoff);
    let dict = pyo3::types::PyDict::new(py);
    for (node, path) in &result {
        let py_path: Vec<PyObject> = path.iter().map(|n| gr.py_node_key(py, n)).collect();
        dict.set_item(gr.py_node_key(py, node), py_path)?;
    }
    Ok(dict.into_any().unbind())
}

/// Return shortest path lengths from source (unweighted BFS).
#[pyfunction]
#[pyo3(signature = (g, source, cutoff=None))]
pub fn single_source_shortest_path_length(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    source: &Bound<'_, PyAny>,
    cutoff: Option<usize>,
) -> PyResult<PyObject> {
    let gr = extract_graph(g)?;
    require_undirected(&gr, "single_source_shortest_path_length")?;
    let inner = gr.undirected();
    let source_key = node_key_to_string(py, source)?;
    let result = fnx_algorithms::single_source_shortest_path_length(inner, &source_key, cutoff);
    let dict = pyo3::types::PyDict::new(py);
    for (node, length) in &result {
        dict.set_item(gr.py_node_key(py, node), *length)?;
    }
    Ok(dict.into_any().unbind())
}

// ===========================================================================
// Dominating Set
// ===========================================================================

/// Return a greedy dominating set.
#[pyfunction]
pub fn dominating_set(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
) -> PyResult<Vec<PyObject>> {
    let gr = extract_graph(g)?;
    require_undirected(&gr, "dominating_set")?;
    let inner = gr.undirected();
    let result = py.allow_threads(|| fnx_algorithms::dominating_set(inner));
    Ok(result.iter().map(|n| gr.py_node_key(py, n)).collect())
}

/// Return whether the given nodes form a dominating set.
#[pyfunction]
pub fn is_dominating_set(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    nbunch: &Bound<'_, PyAny>,
) -> PyResult<bool> {
    let gr = extract_graph(g)?;
    require_undirected(&gr, "is_dominating_set")?;
    let inner = gr.undirected();
    let nodes: Vec<String> = nbunch
        .try_iter()?
        .map(|item| node_key_to_string(py, &item?))
        .collect::<PyResult<Vec<_>>>()?;
    let refs: Vec<&str> = nodes.iter().map(String::as_str).collect();
    Ok(fnx_algorithms::is_dominating_set(inner, &refs))
}

// ===========================================================================
// Strongly Connected Components
// ===========================================================================

/// Return the strongly connected components of a directed graph.
#[pyfunction]
pub fn strongly_connected_components(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
) -> PyResult<Vec<PyObject>> {
    let gr = extract_graph(g)?;
    if !gr.is_directed() {
        return Err(crate::NetworkXNotImplemented::new_err(
            "strongly_connected_components is not defined for undirected graphs. Use connected_components instead.",
        ));
    }
    if let GraphRef::Directed { dg, .. } = &gr {
        let result = fnx_algorithms::strongly_connected_components(&dg.inner);
        result
            .iter()
            .map(|comp| {
                let py_set: Vec<PyObject> = comp.iter().map(|n| gr.py_node_key(py, n)).collect();
                py_set.into_pyobject(py).map(|obj| obj.into_any().unbind())
            })
            .collect()
    } else {
        unreachable!()
    }
}

/// Return the number of strongly connected components.
#[pyfunction]
pub fn number_strongly_connected_components(
    _py: Python<'_>,
    g: &Bound<'_, PyAny>,
) -> PyResult<usize> {
    let gr = extract_graph(g)?;
    if !gr.is_directed() {
        return Err(crate::NetworkXNotImplemented::new_err(
            "number_strongly_connected_components is not defined for undirected graphs.",
        ));
    }
    if let GraphRef::Directed { dg, .. } = &gr {
        Ok(fnx_algorithms::number_strongly_connected_components(&dg.inner))
    } else {
        unreachable!()
    }
}

/// Return whether the directed graph is strongly connected.
#[pyfunction]
pub fn is_strongly_connected(
    _py: Python<'_>,
    g: &Bound<'_, PyAny>,
) -> PyResult<bool> {
    let gr = extract_graph(g)?;
    if !gr.is_directed() {
        return Err(crate::NetworkXNotImplemented::new_err(
            "is_strongly_connected is not defined for undirected graphs. Use is_connected instead.",
        ));
    }
    if let GraphRef::Directed { dg, .. } = &gr {
        Ok(fnx_algorithms::is_strongly_connected(&dg.inner))
    } else {
        unreachable!()
    }
}

/// Condense a directed graph by contracting each SCC into a single node.
///
/// Returns a tuple (condensation_graph, mapping) where mapping is a dict
/// from original nodes to SCC indices.
#[pyfunction]
pub fn condensation(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
) -> PyResult<(PyObject, PyObject)> {
    let gr = extract_graph(g)?;
    if !gr.is_directed() {
        return Err(crate::NetworkXNotImplemented::new_err(
            "condensation is not defined for undirected graphs.",
        ));
    }
    if let GraphRef::Directed { dg, .. } = &gr {
        let (cond_graph, node_mapping) = fnx_algorithms::condensation(&dg.inner);
        // Build the condensation DiGraph
        let mut py_dg = PyDiGraph::new_empty(py)?;
        for node in cond_graph.nodes_ordered() {
            py_dg.node_key_map.insert(
                node.to_owned(),
                node.parse::<i64>().unwrap().into_pyobject(py)?.into_any().unbind(),
            );
            py_dg.node_py_attrs.insert(
                node.to_owned(),
                pyo3::types::PyDict::new(py).unbind(),
            );
            py_dg.inner.add_node(node);
        }
        for edge in cond_graph.edges_ordered() {
            let _ = py_dg.inner.add_edge(&edge.left, &edge.right);
            py_dg.edge_py_attrs.insert(
                (edge.left, edge.right),
                pyo3::types::PyDict::new(py).unbind(),
            );
        }
        let py_cond = py_dg.into_pyobject(py)?.into_any().unbind();
        // Build the mapping dict
        let mapping = pyo3::types::PyDict::new(py);
        for (node, scc_idx) in &node_mapping {
            mapping.set_item(dg.py_node_key(py, node), *scc_idx)?;
        }
        Ok((py_cond, mapping.into_any().unbind()))
    } else {
        unreachable!()
    }
}

// ===========================================================================
// Weakly Connected Components
// ===========================================================================

/// Return the weakly connected components of a directed graph.
#[pyfunction]
pub fn weakly_connected_components(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
) -> PyResult<Vec<PyObject>> {
    let gr = extract_graph(g)?;
    if !gr.is_directed() {
        return Err(crate::NetworkXNotImplemented::new_err(
            "weakly_connected_components is not defined for undirected graphs. Use connected_components instead.",
        ));
    }
    if let GraphRef::Directed { dg, .. } = &gr {
        let result = fnx_algorithms::weakly_connected_components(&dg.inner);
        result
            .iter()
            .map(|comp| {
                let py_set: Vec<PyObject> = comp.iter().map(|n| gr.py_node_key(py, n)).collect();
                py_set.into_pyobject(py).map(|obj| obj.into_any().unbind())
            })
            .collect()
    } else {
        unreachable!()
    }
}

/// Return the number of weakly connected components.
#[pyfunction]
pub fn number_weakly_connected_components(
    _py: Python<'_>,
    g: &Bound<'_, PyAny>,
) -> PyResult<usize> {
    let gr = extract_graph(g)?;
    if !gr.is_directed() {
        return Err(crate::NetworkXNotImplemented::new_err(
            "number_weakly_connected_components is not defined for undirected graphs.",
        ));
    }
    if let GraphRef::Directed { dg, .. } = &gr {
        Ok(fnx_algorithms::number_weakly_connected_components(&dg.inner))
    } else {
        unreachable!()
    }
}

/// Return whether the directed graph is weakly connected.
#[pyfunction]
pub fn is_weakly_connected(
    _py: Python<'_>,
    g: &Bound<'_, PyAny>,
) -> PyResult<bool> {
    let gr = extract_graph(g)?;
    if !gr.is_directed() {
        return Err(crate::NetworkXNotImplemented::new_err(
            "is_weakly_connected is not defined for undirected graphs. Use is_connected instead.",
        ));
    }
    if let GraphRef::Directed { dg, .. } = &gr {
        Ok(fnx_algorithms::is_weakly_connected(&dg.inner))
    } else {
        unreachable!()
    }
}

// ===========================================================================
// Transitive Closure / Reduction
// ===========================================================================

/// Return the transitive closure of a directed graph.
#[pyfunction]
pub fn transitive_closure(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
) -> PyResult<PyObject> {
    let gr = extract_graph(g)?;
    if !gr.is_directed() {
        return Err(crate::NetworkXNotImplemented::new_err(
            "transitive_closure is not defined for undirected graphs.",
        ));
    }
    if let GraphRef::Directed { dg, .. } = &gr {
        let result = fnx_algorithms::transitive_closure(&dg.inner);
        let mut py_dg = PyDiGraph::new_empty(py)?;
        for node in result.nodes_ordered() {
            let py_key = dg.py_node_key(py, node);
            py_dg.node_key_map.insert(node.to_owned(), py_key);
            py_dg.node_py_attrs.insert(
                node.to_owned(),
                pyo3::types::PyDict::new(py).unbind(),
            );
            py_dg.inner.add_node(node);
        }
        for edge in result.edges_ordered() {
            let _ = py_dg.inner.add_edge(&edge.left, &edge.right);
            py_dg.edge_py_attrs.insert(
                (edge.left, edge.right),
                pyo3::types::PyDict::new(py).unbind(),
            );
        }
        Ok(py_dg.into_pyobject(py)?.into_any().unbind())
    } else {
        unreachable!()
    }
}

/// Return the transitive reduction of a directed acyclic graph.
#[pyfunction]
pub fn transitive_reduction(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
) -> PyResult<PyObject> {
    let gr = extract_graph(g)?;
    if !gr.is_directed() {
        return Err(crate::NetworkXNotImplemented::new_err(
            "transitive_reduction is not defined for undirected graphs.",
        ));
    }
    if let GraphRef::Directed { dg, .. } = &gr {
        match fnx_algorithms::transitive_reduction(&dg.inner) {
            Some(result) => {
                let mut py_dg = PyDiGraph::new_empty(py)?;
                for node in result.nodes_ordered() {
                    let py_key = dg.py_node_key(py, node);
                    py_dg.node_key_map.insert(node.to_owned(), py_key);
                    py_dg.node_py_attrs.insert(
                        node.to_owned(),
                        pyo3::types::PyDict::new(py).unbind(),
                    );
                    py_dg.inner.add_node(node);
                }
                for edge in result.edges_ordered() {
                    let _ = py_dg.inner.add_edge(&edge.left, &edge.right);
                    py_dg.edge_py_attrs.insert(
                        (edge.left, edge.right),
                        pyo3::types::PyDict::new(py).unbind(),
                    );
                }
                Ok(py_dg.into_pyobject(py)?.into_any().unbind())
            }
            None => Err(NetworkXError::new_err(
                "transitive_reduction is not uniquely defined for graphs with cycles.",
            )),
        }
    } else {
        unreachable!()
    }
}

// ===========================================================================
// Reciprocity
// ===========================================================================

/// Compute the overall reciprocity of a directed graph.
///
/// Matches `networkx.overall_reciprocity(G)`.
#[pyfunction]
pub fn overall_reciprocity(
    _py: Python<'_>,
    g: &Bound<'_, PyAny>,
) -> PyResult<f64> {
    let gr = extract_graph(g)?;
    if !gr.is_directed() {
        return Err(NetworkXError::new_err(
            "overall_reciprocity not defined on undirected graphs.",
        ));
    }
    if let GraphRef::Directed { dg, .. } = &gr {
        Ok(fnx_algorithms::overall_reciprocity(&dg.inner))
    } else {
        unreachable!()
    }
}

/// Compute the reciprocity for nodes in a directed graph.
///
/// If nodes is None, computes for all nodes.
/// Matches `networkx.reciprocity(G, nodes)`.
#[pyfunction]
#[pyo3(signature = (g, nodes=None))]
pub fn reciprocity(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    nodes: Option<&Bound<'_, PyAny>>,
) -> PyResult<PyObject> {
    let gr = extract_graph(g)?;
    if !gr.is_directed() {
        return Err(NetworkXError::new_err(
            "reciprocity not defined on undirected graphs.",
        ));
    }
    if let GraphRef::Directed { dg, .. } = &gr {
        let node_list: Vec<String> = if let Some(ns) = nodes {
            // Check if it's a single node (not iterable list)
            if let Ok(s) = node_key_to_string(py, ns) && dg.inner.has_node(&s) {
                // Single node: return a float directly
                let node_refs: Vec<&str> = vec![s.as_str()];
                let result = fnx_algorithms::reciprocity(&dg.inner, &node_refs);
                let val = result.get(&s).copied().unwrap_or(0.0);
                return Ok(val.into_pyobject(py).unwrap().into_any().unbind());
            }
            // Try as iterable
            ns.try_iter()?
                .map(|item| node_key_to_string(py, &item?))
                .collect::<PyResult<Vec<_>>>()?
        } else {
            dg.inner.nodes_ordered().into_iter().map(|s| s.to_owned()).collect()
        };

        let node_refs: Vec<&str> = node_list.iter().map(String::as_str).collect();
        let result = fnx_algorithms::reciprocity(&dg.inner, &node_refs);

        let dict = pyo3::types::PyDict::new(py);
        for (k, v) in &result {
            let py_key = gr.py_node_key(py, k);
            dict.set_item(py_key, v)?;
        }
        Ok(dict.into_any().unbind())
    } else {
        unreachable!()
    }
}

// ===========================================================================
// Wiener Index
// ===========================================================================

/// Compute the Wiener index of a connected graph.
///
/// Matches `networkx.wiener_index(G)`.
#[pyfunction]
pub fn wiener_index(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
) -> PyResult<f64> {
    let gr = extract_graph(g)?;
    require_undirected(&gr, "wiener_index")?;
    let inner = gr.undirected();
    match py.allow_threads(|| fnx_algorithms::wiener_index(inner)) {
        Some(w) => Ok(w),
        None => Err(NetworkXError::new_err(
            "Graph is not connected.",
        )),
    }
}

// ===========================================================================
// Link Prediction
// ===========================================================================

/// Return the common neighbors of u and v in the graph.
///
/// Matches `networkx.common_neighbors(G, u, v)`.
#[pyfunction]
pub fn common_neighbors(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    u: &Bound<'_, PyAny>,
    v: &Bound<'_, PyAny>,
) -> PyResult<Vec<PyObject>> {
    let gr = extract_graph(g)?;
    require_undirected(&gr, "common_neighbors")?;
    let u_key = node_key_to_string(py, u)?;
    let v_key = node_key_to_string(py, v)?;
    validate_node(&gr, &u_key, u)?;
    validate_node(&gr, &v_key, v)?;
    let inner = gr.undirected();
    let result = py.allow_threads(|| fnx_algorithms::common_neighbors(inner, &u_key, &v_key));
    Ok(result.iter().map(|n| gr.py_node_key(py, n)).collect())
}

/// Helper to extract node pairs (ebunch) from Python.
/// If ebunch is None, returns all non-edges.
fn extract_ebunch(
    py: Python<'_>,
    gr: &GraphRef<'_>,
    ebunch: Option<&Bound<'_, PyAny>>,
) -> PyResult<Vec<(String, String)>> {
    if let Some(eb) = ebunch {
        let pairs: Vec<(String, String)> = eb
            .try_iter()?
            .map(|item| {
                let item = item?;
                let pair: &Bound<'_, PyAny> = &item;
                let iter_result: PyResult<Vec<_>> = pair.try_iter()?.collect();
                let items = iter_result?;
                if items.len() != 2 {
                    return Err(pyo3::exceptions::PyValueError::new_err(
                        "ebunch must contain 2-tuples",
                    ));
                }
                let u_key = node_key_to_string(py, &items[0])?;
                let v_key = node_key_to_string(py, &items[1])?;
                Ok((u_key, v_key))
            })
            .collect::<PyResult<Vec<_>>>()?;
        Ok(pairs)
    } else {
        // Default: all non-edges
        let inner = gr.undirected();
        let nodes = inner.nodes_ordered();
        let mut pairs = Vec::new();
        for (i, u) in nodes.iter().enumerate() {
            for v in &nodes[i + 1..] {
                if !inner.has_edge(u, v) {
                    pairs.push((u.to_string(), v.to_string()));
                }
            }
        }
        Ok(pairs)
    }
}

/// Compute the Jaccard coefficient for all node pairs in ebunch.
///
/// Matches `networkx.jaccard_coefficient(G, ebunch)`.
#[pyfunction]
#[pyo3(signature = (g, ebunch=None))]
pub fn jaccard_coefficient(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    ebunch: Option<&Bound<'_, PyAny>>,
) -> PyResult<Vec<(PyObject, PyObject, f64)>> {
    let gr = extract_graph(g)?;
    require_undirected(&gr, "jaccard_coefficient")?;
    let pairs = extract_ebunch(py, &gr, ebunch)?;
    let inner = gr.undirected();
    let result = py.allow_threads(|| fnx_algorithms::jaccard_coefficient(inner, &pairs));
    Ok(result
        .into_iter()
        .map(|(u, v, s)| (gr.py_node_key(py, &u), gr.py_node_key(py, &v), s))
        .collect())
}

/// Compute the Adamic-Adar index for all node pairs in ebunch.
///
/// Matches `networkx.adamic_adar_index(G, ebunch)`.
#[pyfunction]
#[pyo3(signature = (g, ebunch=None))]
pub fn adamic_adar_index(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    ebunch: Option<&Bound<'_, PyAny>>,
) -> PyResult<Vec<(PyObject, PyObject, f64)>> {
    let gr = extract_graph(g)?;
    require_undirected(&gr, "adamic_adar_index")?;
    let pairs = extract_ebunch(py, &gr, ebunch)?;
    let inner = gr.undirected();
    let result = py.allow_threads(|| fnx_algorithms::adamic_adar_index(inner, &pairs));
    Ok(result
        .into_iter()
        .map(|(u, v, s)| (gr.py_node_key(py, &u), gr.py_node_key(py, &v), s))
        .collect())
}

/// Compute the preferential attachment score for all node pairs in ebunch.
///
/// Matches `networkx.preferential_attachment(G, ebunch)`.
#[pyfunction]
#[pyo3(signature = (g, ebunch=None))]
pub fn preferential_attachment(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    ebunch: Option<&Bound<'_, PyAny>>,
) -> PyResult<Vec<(PyObject, PyObject, f64)>> {
    let gr = extract_graph(g)?;
    require_undirected(&gr, "preferential_attachment")?;
    let pairs = extract_ebunch(py, &gr, ebunch)?;
    let inner = gr.undirected();
    let result = py.allow_threads(|| fnx_algorithms::preferential_attachment(inner, &pairs));
    Ok(result
        .into_iter()
        .map(|(u, v, s)| (gr.py_node_key(py, &u), gr.py_node_key(py, &v), s))
        .collect())
}

/// Compute the resource allocation index for all node pairs in ebunch.
///
/// Matches `networkx.resource_allocation_index(G, ebunch)`.
#[pyfunction]
#[pyo3(signature = (g, ebunch=None))]
pub fn resource_allocation_index(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    ebunch: Option<&Bound<'_, PyAny>>,
) -> PyResult<Vec<(PyObject, PyObject, f64)>> {
    let gr = extract_graph(g)?;
    require_undirected(&gr, "resource_allocation_index")?;
    let pairs = extract_ebunch(py, &gr, ebunch)?;
    let inner = gr.undirected();
    let result = py.allow_threads(|| fnx_algorithms::resource_allocation_index(inner, &pairs));
    Ok(result
        .into_iter()
        .map(|(u, v, s)| (gr.py_node_key(py, &u), gr.py_node_key(py, &v), s))
        .collect())
}

// ===========================================================================
// Graph Operators
// ===========================================================================

fn rust_graph_to_py(py: Python<'_>, result: &fnx_classes::Graph, source_gr: &GraphRef<'_>) -> PyResult<PyObject> {
    let mut py_graph = PyGraph::new_empty(py)?;
    for node in result.nodes_ordered() {
        let py_key = source_gr.py_node_key(py, node);
        py_graph.node_key_map.insert(node.to_owned(), py_key);
        py_graph.node_py_attrs.insert(
            node.to_owned(),
            pyo3::types::PyDict::new(py).unbind(),
        );
        py_graph.inner.add_node(node);
    }
    for edge in result.edges_ordered() {
        let _ = py_graph.inner.add_edge(&edge.left, &edge.right);
        let ek = PyGraph::edge_key(&edge.left, &edge.right);
        py_graph
            .edge_py_attrs
            .insert(ek, pyo3::types::PyDict::new(py).unbind());
    }
    Ok(py_graph.into_pyobject(py)?.into_any().unbind())
}

#[pyfunction]
#[pyo3(signature = (g, h))]
fn union(py: Python<'_>, g: &Bound<'_, PyAny>, h: &Bound<'_, PyAny>) -> PyResult<PyObject> {
    let gr1 = extract_graph(g)?;
    let gr2 = extract_graph(h)?;
    let inner1 = gr1.undirected();
    let inner2 = gr2.undirected();
    let result = py.allow_threads(|| fnx_algorithms::graph_union(inner1, inner2));
    rust_graph_to_py(py, &result, &gr1)
}

#[pyfunction]
#[pyo3(signature = (g, h))]
fn intersection(py: Python<'_>, g: &Bound<'_, PyAny>, h: &Bound<'_, PyAny>) -> PyResult<PyObject> {
    let gr1 = extract_graph(g)?;
    let gr2 = extract_graph(h)?;
    let inner1 = gr1.undirected();
    let inner2 = gr2.undirected();
    let result = py.allow_threads(|| fnx_algorithms::graph_intersection(inner1, inner2));
    rust_graph_to_py(py, &result, &gr1)
}

#[pyfunction]
#[pyo3(signature = (g, h))]
fn compose(py: Python<'_>, g: &Bound<'_, PyAny>, h: &Bound<'_, PyAny>) -> PyResult<PyObject> {
    let gr1 = extract_graph(g)?;
    let gr2 = extract_graph(h)?;
    let inner1 = gr1.undirected();
    let inner2 = gr2.undirected();
    let result = py.allow_threads(|| fnx_algorithms::graph_compose(inner1, inner2));
    rust_graph_to_py(py, &result, &gr1)
}

#[pyfunction]
#[pyo3(signature = (g, h))]
fn difference(py: Python<'_>, g: &Bound<'_, PyAny>, h: &Bound<'_, PyAny>) -> PyResult<PyObject> {
    let gr1 = extract_graph(g)?;
    let gr2 = extract_graph(h)?;
    let inner1 = gr1.undirected();
    let inner2 = gr2.undirected();
    let result = py.allow_threads(|| fnx_algorithms::graph_difference(inner1, inner2));
    rust_graph_to_py(py, &result, &gr1)
}

#[pyfunction]
#[pyo3(signature = (g, h))]
fn symmetric_difference(py: Python<'_>, g: &Bound<'_, PyAny>, h: &Bound<'_, PyAny>) -> PyResult<PyObject> {
    let gr1 = extract_graph(g)?;
    let gr2 = extract_graph(h)?;
    let inner1 = gr1.undirected();
    let inner2 = gr2.undirected();
    let result = py.allow_threads(|| fnx_algorithms::graph_symmetric_difference(inner1, inner2));
    rust_graph_to_py(py, &result, &gr1)
}

#[pyfunction]
#[pyo3(signature = (g,))]
fn degree_histogram(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<Vec<usize>> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    Ok(py.allow_threads(|| fnx_algorithms::degree_histogram(inner)))
}

// ===========================================================================
// Community Detection
// ===========================================================================

#[pyfunction]
#[pyo3(signature = (g, resolution=1.0, weight="weight", seed=None))]
fn louvain_communities(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    resolution: f64,
    weight: &str,
    seed: Option<u64>,
) -> PyResult<Vec<Vec<PyObject>>> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    let result = py.allow_threads(|| {
        fnx_algorithms::louvain_communities(inner, resolution, weight, seed)
    });
    Ok(result
        .into_iter()
        .map(|comm| comm.into_iter().map(|n| gr.py_node_key(py, &n)).collect())
        .collect())
}

#[pyfunction]
#[pyo3(signature = (g, communities, resolution=1.0, weight="weight"))]
fn modularity(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    communities: Vec<Vec<String>>,
    resolution: f64,
    weight: &str,
) -> PyResult<f64> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    Ok(py.allow_threads(|| {
        fnx_algorithms::modularity(inner, &communities, resolution, weight)
    }))
}

#[pyfunction]
#[pyo3(signature = (g,))]
fn label_propagation_communities(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
) -> PyResult<Vec<Vec<PyObject>>> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    let result = py.allow_threads(|| fnx_algorithms::label_propagation_communities(inner));
    Ok(result
        .into_iter()
        .map(|comm| comm.into_iter().map(|n| gr.py_node_key(py, &n)).collect())
        .collect())
}

#[pyfunction]
#[pyo3(signature = (g, resolution=1.0, weight="weight"))]
fn greedy_modularity_communities(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    resolution: f64,
    weight: &str,
) -> PyResult<Vec<Vec<PyObject>>> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    let result = py.allow_threads(|| {
        fnx_algorithms::greedy_modularity_communities(inner, resolution, weight)
    });
    Ok(result
        .into_iter()
        .map(|comm| comm.into_iter().map(|n| gr.py_node_key(py, &n)).collect())
        .collect())
}

// ===========================================================================
// A* shortest path
// ===========================================================================

/// A* shortest path from source to target.
///
/// ``heuristic`` is an optional Python callable ``heuristic(u, v) -> float``
/// where *v* is the target node.  When omitted, A* degenerates to Dijkstra.
#[pyfunction]
#[pyo3(signature = (g, source, target, heuristic=None, weight="weight"))]
fn astar_path(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    source: &Bound<'_, PyAny>,
    target: &Bound<'_, PyAny>,
    heuristic: Option<&Bound<'_, PyAny>>,
    weight: &str,
) -> PyResult<Vec<PyObject>> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    let src_key = node_key_to_string(py, source)?;
    let tgt_key = node_key_to_string(py, target)?;
    validate_node(&gr, &src_key, source)?;
    validate_node(&gr, &tgt_key, target)?;

    let result = if let Some(callable) = heuristic {
        // With heuristic: build a closure that calls back into Python.
        // The closure converts internal string keys back to Python objects
        // and invokes the user-supplied heuristic(u, target).
        let tgt_obj = target.clone().unbind();
        let callable_obj = callable.clone().unbind();
        let h = |node_str: &str| -> f64 {
            let node_py = gr.py_node_key(py, node_str);
            let tgt_bound = tgt_obj.bind(py);
            callable_obj
                .bind(py)
                .call1((node_py, tgt_bound))
                .and_then(|r| r.extract::<f64>())
                .unwrap_or(0.0)
        };
        fnx_algorithms::astar_path(inner, &src_key, &tgt_key, weight, Some(&h))
    } else {
        // Without heuristic: can release the GIL.
        py.allow_threads(|| {
            fnx_algorithms::astar_path(inner, &src_key, &tgt_key, weight, None)
        })
    };

    match result {
        Some(path) => Ok(path.iter().map(|n| gr.py_node_key(py, n)).collect()),
        None => Err(pyo3::exceptions::PyValueError::new_err(
            format!("No path between {} and {}.", src_key, tgt_key),
        )),
    }
}

/// A* shortest path length from source to target.
#[pyfunction]
#[pyo3(signature = (g, source, target, heuristic=None, weight="weight"))]
fn astar_path_length(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    source: &Bound<'_, PyAny>,
    target: &Bound<'_, PyAny>,
    heuristic: Option<&Bound<'_, PyAny>>,
    weight: &str,
) -> PyResult<f64> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    let src_key = node_key_to_string(py, source)?;
    let tgt_key = node_key_to_string(py, target)?;
    validate_node(&gr, &src_key, source)?;
    validate_node(&gr, &tgt_key, target)?;

    let result = if let Some(callable) = heuristic {
        let tgt_obj = target.clone().unbind();
        let callable_obj = callable.clone().unbind();
        let h = |node_str: &str| -> f64 {
            let node_py = gr.py_node_key(py, node_str);
            let tgt_bound = tgt_obj.bind(py);
            callable_obj
                .bind(py)
                .call1((node_py, tgt_bound))
                .and_then(|r| r.extract::<f64>())
                .unwrap_or(0.0)
        };
        fnx_algorithms::astar_path_length(inner, &src_key, &tgt_key, weight, Some(&h))
    } else {
        py.allow_threads(|| {
            fnx_algorithms::astar_path_length(inner, &src_key, &tgt_key, weight, None)
        })
    };

    match result {
        Some(length) => Ok(length),
        None => Err(pyo3::exceptions::PyValueError::new_err(
            format!("No path between {} and {}.", src_key, tgt_key),
        )),
    }
}

/// Yen's K-shortest simple paths from source to target.
#[pyfunction]
#[pyo3(signature = (g, source, target, weight=None))]
fn shortest_simple_paths(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    source: &Bound<'_, PyAny>,
    target: &Bound<'_, PyAny>,
    weight: Option<&str>,
) -> PyResult<Vec<Vec<PyObject>>> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    let src_key = node_key_to_string(py, source)?;
    let tgt_key = node_key_to_string(py, target)?;
    validate_node(&gr, &src_key, source)?;
    validate_node(&gr, &tgt_key, target)?;
    let result = py.allow_threads(|| {
        fnx_algorithms::shortest_simple_paths(inner, &src_key, &tgt_key, weight)
    });
    Ok(result
        .iter()
        .map(|path| path.iter().map(|n| gr.py_node_key(py, n)).collect())
        .collect())
}

// ===========================================================================
// Graph isomorphism
// ===========================================================================

/// Check if two graphs are isomorphic (VF2 algorithm).
#[pyfunction]
#[pyo3(signature = (g1, g2))]
fn is_isomorphic(py: Python<'_>, g1: &Bound<'_, PyAny>, g2: &Bound<'_, PyAny>) -> PyResult<bool> {
    let gr1 = extract_graph(g1)?;
    let gr2 = extract_graph(g2)?;
    let inner1 = gr1.undirected();
    let inner2 = gr2.undirected();
    Ok(py.allow_threads(|| fnx_algorithms::is_isomorphic(inner1, inner2)))
}

/// Check if two graphs could be isomorphic (degree sequence heuristic).
#[pyfunction]
#[pyo3(signature = (g1, g2))]
fn could_be_isomorphic(py: Python<'_>, g1: &Bound<'_, PyAny>, g2: &Bound<'_, PyAny>) -> PyResult<bool> {
    let gr1 = extract_graph(g1)?;
    let gr2 = extract_graph(g2)?;
    let inner1 = gr1.undirected();
    let inner2 = gr2.undirected();
    Ok(py.allow_threads(|| fnx_algorithms::could_be_isomorphic(inner1, inner2)))
}

/// Fast check if two graphs could be isomorphic (node/edge count + degree sequence).
#[pyfunction]
#[pyo3(signature = (g1, g2))]
fn fast_could_be_isomorphic(py: Python<'_>, g1: &Bound<'_, PyAny>, g2: &Bound<'_, PyAny>) -> PyResult<bool> {
    let gr1 = extract_graph(g1)?;
    let gr2 = extract_graph(g2)?;
    let inner1 = gr1.undirected();
    let inner2 = gr2.undirected();
    Ok(py.allow_threads(|| fnx_algorithms::fast_could_be_isomorphic(inner1, inner2)))
}

// ===========================================================================
// Approximation algorithms
// ===========================================================================

/// 2-approximation for minimum weighted vertex cover.
#[pyfunction]
#[pyo3(signature = (g, weight=None))]
fn min_weighted_vertex_cover(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    weight: Option<&str>,
) -> PyResult<PyObject> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    let attr = weight.unwrap_or("weight");
    let result = py.allow_threads(|| fnx_algorithms::min_weighted_vertex_cover(inner, attr));
    let dict = pyo3::types::PyDict::new(py);
    for (node, w) in &result {
        dict.set_item(gr.py_node_key(py, node), w)?;
    }
    // NetworkX returns a set of nodes (ignoring weights), so return just a set.
    let pyset = pyo3::types::PySet::new(py, result.keys().map(|n| gr.py_node_key(py, n)).collect::<Vec<_>>())?;
    Ok(pyset.into_any().unbind())
}

/// Greedy approximation for maximum independent set.
#[pyfunction]
#[pyo3(signature = (g,))]
fn maximum_independent_set(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<PyObject> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    let result = py.allow_threads(|| fnx_algorithms::maximum_independent_set(inner));
    let pyset = pyo3::types::PySet::new(py, result.iter().map(|n| gr.py_node_key(py, n)).collect::<Vec<_>>())?;
    Ok(pyset.into_any().unbind())
}

/// Greedy approximation for maximum clique.
#[pyfunction]
#[pyo3(signature = (g,))]
fn max_clique(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<PyObject> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    let result = py.allow_threads(|| fnx_algorithms::max_clique_approx(inner));
    let pyset = pyo3::types::PySet::new(py, result.iter().map(|n| gr.py_node_key(py, n)).collect::<Vec<_>>())?;
    Ok(pyset.into_any().unbind())
}

/// Ramsey-based clique removal approximation.
///
/// Returns (independent_set, list_of_cliques).
#[pyfunction]
#[pyo3(signature = (g,))]
fn clique_removal(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<(PyObject, Vec<PyObject>)> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    let (iset, cliques) = py.allow_threads(|| fnx_algorithms::clique_removal(inner));
    let py_iset = pyo3::types::PySet::new(
        py,
        iset.iter().map(|n| gr.py_node_key(py, n)).collect::<Vec<_>>(),
    )?;
    let py_cliques: Vec<PyObject> = cliques
        .iter()
        .map(|clique| {
            pyo3::types::PySet::new(
                py,
                clique.iter().map(|n| gr.py_node_key(py, n)).collect::<Vec<_>>(),
            )
            .map(|s| s.into_any().unbind())
        })
        .collect::<PyResult<Vec<_>>>()?;
    Ok((py_iset.into_any().unbind(), py_cliques))
}

/// Return the size of the largest clique in the graph (approximate).
#[pyfunction]
#[pyo3(signature = (g,))]
fn large_clique_size(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<usize> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    let result = py.allow_threads(|| fnx_algorithms::max_clique_approx(inner));
    Ok(result.len())
}

/// Fastest isomorphism pre-check (order + size only).
#[pyfunction]
#[pyo3(signature = (g1, g2))]
fn faster_could_be_isomorphic(py: Python<'_>, g1: &Bound<'_, PyAny>, g2: &Bound<'_, PyAny>) -> PyResult<bool> {
    let gr1 = extract_graph(g1)?;
    let gr2 = extract_graph(g2)?;
    let inner1 = gr1.undirected();
    let inner2 = gr2.undirected();
    Ok(py.allow_threads(|| fnx_algorithms::faster_could_be_isomorphic(inner1, inner2)))
}

/// Check if a graph is planar (can be drawn without edge crossings).
#[pyfunction]
#[pyo3(signature = (g,))]
fn is_planar(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<bool> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    Ok(py.allow_threads(|| fnx_algorithms::is_planar(inner)))
}

/// Find the barycenter of a connected graph.
///
/// The barycenter is the set of nodes minimizing the sum of shortest
/// path distances to all other nodes.
#[pyfunction]
#[pyo3(signature = (g,))]
fn barycenter(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<Vec<PyObject>> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    let result = py.allow_threads(|| fnx_algorithms::barycenter(inner));
    Ok(result.iter().map(|n| gr.py_node_key(py, n)).collect())
}

// ===========================================================================
// Registration
// ===========================================================================

/// Register all algorithm functions into the Python module.
pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    // Shortest path
    m.add_function(wrap_pyfunction!(shortest_path, m)?)?;
    m.add_function(wrap_pyfunction!(shortest_path_length, m)?)?;
    m.add_function(wrap_pyfunction!(has_path, m)?)?;
    m.add_function(wrap_pyfunction!(average_shortest_path_length, m)?)?;
    m.add_function(wrap_pyfunction!(dijkstra_path, m)?)?;
    m.add_function(wrap_pyfunction!(bellman_ford_path, m)?)?;
    m.add_function(wrap_pyfunction!(multi_source_dijkstra, m)?)?;
    // Connectivity
    m.add_function(wrap_pyfunction!(is_connected, m)?)?;
    m.add_function(wrap_pyfunction!(connected_components, m)?)?;
    m.add_function(wrap_pyfunction!(number_connected_components, m)?)?;
    m.add_function(wrap_pyfunction!(node_connectivity, m)?)?;
    m.add_function(wrap_pyfunction!(minimum_node_cut, m)?)?;
    m.add_function(wrap_pyfunction!(edge_connectivity, m)?)?;
    m.add_function(wrap_pyfunction!(articulation_points, m)?)?;
    m.add_function(wrap_pyfunction!(bridges, m)?)?;
    // Centrality
    m.add_function(wrap_pyfunction!(degree_centrality, m)?)?;
    m.add_function(wrap_pyfunction!(closeness_centrality, m)?)?;
    m.add_function(wrap_pyfunction!(harmonic_centrality, m)?)?;
    m.add_function(wrap_pyfunction!(katz_centrality, m)?)?;
    m.add_function(wrap_pyfunction!(betweenness_centrality, m)?)?;
    m.add_function(wrap_pyfunction!(edge_betweenness_centrality, m)?)?;
    m.add_function(wrap_pyfunction!(eigenvector_centrality, m)?)?;
    m.add_function(wrap_pyfunction!(pagerank, m)?)?;
    m.add_function(wrap_pyfunction!(hits, m)?)?;
    m.add_function(wrap_pyfunction!(average_neighbor_degree, m)?)?;
    m.add_function(wrap_pyfunction!(degree_assortativity_coefficient, m)?)?;
    m.add_function(wrap_pyfunction!(voterank, m)?)?;
    // Clustering
    m.add_function(wrap_pyfunction!(clustering, m)?)?;
    m.add_function(wrap_pyfunction!(average_clustering, m)?)?;
    m.add_function(wrap_pyfunction!(transitivity, m)?)?;
    m.add_function(wrap_pyfunction!(triangles, m)?)?;
    m.add_function(wrap_pyfunction!(square_clustering, m)?)?;
    m.add_function(wrap_pyfunction!(find_cliques, m)?)?;
    m.add_function(wrap_pyfunction!(graph_clique_number, m)?)?;
    // Matching
    m.add_function(wrap_pyfunction!(maximal_matching, m)?)?;
    m.add_function(wrap_pyfunction!(max_weight_matching, m)?)?;
    m.add_function(wrap_pyfunction!(min_weight_matching, m)?)?;
    m.add_function(wrap_pyfunction!(min_edge_cover, m)?)?;
    // Flow
    m.add_function(wrap_pyfunction!(maximum_flow_value, m)?)?;
    m.add_function(wrap_pyfunction!(minimum_cut_value, m)?)?;
    // Distance measures
    m.add_function(wrap_pyfunction!(density, m)?)?;
    m.add_function(wrap_pyfunction!(eccentricity, m)?)?;
    m.add_function(wrap_pyfunction!(diameter, m)?)?;
    m.add_function(wrap_pyfunction!(radius, m)?)?;
    m.add_function(wrap_pyfunction!(center, m)?)?;
    m.add_function(wrap_pyfunction!(periphery, m)?)?;
    // Tree/forest/bipartite/coloring/core
    m.add_function(wrap_pyfunction!(is_tree, m)?)?;
    m.add_function(wrap_pyfunction!(is_forest, m)?)?;
    m.add_function(wrap_pyfunction!(is_bipartite, m)?)?;
    m.add_function(wrap_pyfunction!(bipartite_sets, m)?)?;
    m.add_function(wrap_pyfunction!(greedy_color, m)?)?;
    m.add_function(wrap_pyfunction!(core_number, m)?)?;
    m.add_function(wrap_pyfunction!(minimum_spanning_tree, m)?)?;
    // Euler
    m.add_function(wrap_pyfunction!(is_eulerian, m)?)?;
    m.add_function(wrap_pyfunction!(has_eulerian_path, m)?)?;
    m.add_function(wrap_pyfunction!(is_semieulerian, m)?)?;
    m.add_function(wrap_pyfunction!(eulerian_circuit, m)?)?;
    m.add_function(wrap_pyfunction!(eulerian_path, m)?)?;
    // Paths and cycles
    m.add_function(wrap_pyfunction!(all_simple_paths, m)?)?;
    m.add_function(wrap_pyfunction!(cycle_basis, m)?)?;
    // Efficiency
    m.add_function(wrap_pyfunction!(global_efficiency, m)?)?;
    m.add_function(wrap_pyfunction!(local_efficiency, m)?)?;
    // BFS traversal
    m.add_function(wrap_pyfunction!(bfs_edges, m)?)?;
    m.add_function(wrap_pyfunction!(bfs_tree, m)?)?;
    m.add_function(wrap_pyfunction!(bfs_predecessors, m)?)?;
    m.add_function(wrap_pyfunction!(bfs_successors, m)?)?;
    m.add_function(wrap_pyfunction!(bfs_layers, m)?)?;
    m.add_function(wrap_pyfunction!(descendants_at_distance, m)?)?;
    // DFS traversal
    m.add_function(wrap_pyfunction!(dfs_edges, m)?)?;
    m.add_function(wrap_pyfunction!(dfs_tree, m)?)?;
    m.add_function(wrap_pyfunction!(dfs_predecessors, m)?)?;
    m.add_function(wrap_pyfunction!(dfs_successors, m)?)?;
    m.add_function(wrap_pyfunction!(dfs_preorder_nodes, m)?)?;
    m.add_function(wrap_pyfunction!(dfs_postorder_nodes, m)?)?;
    // DAG algorithms
    m.add_function(wrap_pyfunction!(topological_sort, m)?)?;
    m.add_function(wrap_pyfunction!(topological_generations, m)?)?;
    m.add_function(wrap_pyfunction!(dag_longest_path, m)?)?;
    m.add_function(wrap_pyfunction!(dag_longest_path_length, m)?)?;
    m.add_function(wrap_pyfunction!(lexicographic_topological_sort, m)?)?;
    m.add_function(wrap_pyfunction!(is_directed_acyclic_graph, m)?)?;
    m.add_function(wrap_pyfunction!(ancestors, m)?)?;
    m.add_function(wrap_pyfunction!(descendants, m)?)?;
    // All shortest paths
    m.add_function(wrap_pyfunction!(all_shortest_paths, m)?)?;
    // Complement
    m.add_function(wrap_pyfunction!(complement, m)?)?;
    // Reciprocity
    m.add_function(wrap_pyfunction!(overall_reciprocity, m)?)?;
    m.add_function(wrap_pyfunction!(reciprocity, m)?)?;
    // Wiener index
    m.add_function(wrap_pyfunction!(wiener_index, m)?)?;
    // Link prediction
    m.add_function(wrap_pyfunction!(common_neighbors, m)?)?;
    m.add_function(wrap_pyfunction!(jaccard_coefficient, m)?)?;
    m.add_function(wrap_pyfunction!(adamic_adar_index, m)?)?;
    m.add_function(wrap_pyfunction!(preferential_attachment, m)?)?;
    m.add_function(wrap_pyfunction!(resource_allocation_index, m)?)?;
    // Graph metrics
    m.add_function(wrap_pyfunction!(average_degree_connectivity, m)?)?;
    m.add_function(wrap_pyfunction!(rich_club_coefficient, m)?)?;
    m.add_function(wrap_pyfunction!(s_metric, m)?)?;
    // Spanning trees
    m.add_function(wrap_pyfunction!(maximum_spanning_tree, m)?)?;
    // Strongly connected components
    m.add_function(wrap_pyfunction!(strongly_connected_components, m)?)?;
    m.add_function(wrap_pyfunction!(number_strongly_connected_components, m)?)?;
    m.add_function(wrap_pyfunction!(is_strongly_connected, m)?)?;
    m.add_function(wrap_pyfunction!(condensation, m)?)?;
    // Weakly connected components
    m.add_function(wrap_pyfunction!(weakly_connected_components, m)?)?;
    m.add_function(wrap_pyfunction!(number_weakly_connected_components, m)?)?;
    m.add_function(wrap_pyfunction!(is_weakly_connected, m)?)?;
    // Transitive closure/reduction
    m.add_function(wrap_pyfunction!(transitive_closure, m)?)?;
    m.add_function(wrap_pyfunction!(transitive_reduction, m)?)?;
    // All-pairs shortest paths
    m.add_function(wrap_pyfunction!(all_pairs_shortest_path, m)?)?;
    m.add_function(wrap_pyfunction!(all_pairs_shortest_path_length, m)?)?;
    // Graph predicates & utilities
    m.add_function(wrap_pyfunction!(is_empty, m)?)?;
    m.add_function(wrap_pyfunction!(non_neighbors, m)?)?;
    m.add_function(wrap_pyfunction!(number_of_cliques, m)?)?;
    // Single-source shortest paths
    m.add_function(wrap_pyfunction!(single_source_shortest_path, m)?)?;
    m.add_function(wrap_pyfunction!(single_source_shortest_path_length, m)?)?;
    // Dominating set
    m.add_function(wrap_pyfunction!(dominating_set, m)?)?;
    m.add_function(wrap_pyfunction!(is_dominating_set, m)?)?;
    // Community detection
    m.add_function(wrap_pyfunction!(louvain_communities, m)?)?;
    m.add_function(wrap_pyfunction!(modularity, m)?)?;
    m.add_function(wrap_pyfunction!(label_propagation_communities, m)?)?;
    m.add_function(wrap_pyfunction!(greedy_modularity_communities, m)?)?;
    // Graph operators
    m.add_function(wrap_pyfunction!(union, m)?)?;
    m.add_function(wrap_pyfunction!(intersection, m)?)?;
    m.add_function(wrap_pyfunction!(compose, m)?)?;
    m.add_function(wrap_pyfunction!(difference, m)?)?;
    m.add_function(wrap_pyfunction!(symmetric_difference, m)?)?;
    m.add_function(wrap_pyfunction!(degree_histogram, m)?)?;
    // A* shortest path
    m.add_function(wrap_pyfunction!(astar_path, m)?)?;
    m.add_function(wrap_pyfunction!(astar_path_length, m)?)?;
    m.add_function(wrap_pyfunction!(shortest_simple_paths, m)?)?;
    // Graph isomorphism
    m.add_function(wrap_pyfunction!(is_isomorphic, m)?)?;
    m.add_function(wrap_pyfunction!(could_be_isomorphic, m)?)?;
    m.add_function(wrap_pyfunction!(fast_could_be_isomorphic, m)?)?;
    m.add_function(wrap_pyfunction!(faster_could_be_isomorphic, m)?)?;
    // Planarity
    m.add_function(wrap_pyfunction!(is_planar, m)?)?;
    // Barycenter
    m.add_function(wrap_pyfunction!(barycenter, m)?)?;
    // Approximation algorithms
    m.add_function(wrap_pyfunction!(min_weighted_vertex_cover, m)?)?;
    m.add_function(wrap_pyfunction!(maximum_independent_set, m)?)?;
    m.add_function(wrap_pyfunction!(max_clique, m)?)?;
    m.add_function(wrap_pyfunction!(clique_removal, m)?)?;
    m.add_function(wrap_pyfunction!(large_clique_size, m)?)?;
    Ok(())
}
