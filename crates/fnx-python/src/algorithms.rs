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
    Ok(())
}
