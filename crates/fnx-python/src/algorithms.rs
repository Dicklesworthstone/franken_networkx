//! Python bindings for FrankenNetworkX algorithms.
//!
//! Each function follows the NetworkX API signature, accepts a `PyGraph`,
//! delegates to the Rust implementation in `fnx_algorithms`, and returns
//! Python-native types (lists, dicts, floats, bools).

use crate::{NetworkXError, NetworkXNoPath, NodeNotFound, PyGraph, node_key_to_string};
use pyo3::prelude::*;
use pyo3::types::PyDict;

// ---------------------------------------------------------------------------
// shortest_path
// ---------------------------------------------------------------------------

/// Return the shortest path between source and target.
///
/// Parameters
/// ----------
/// G : Graph
///     The graph to search.
/// source : node, optional
///     Starting node. If None and target is None, return dict of dicts.
/// target : node, optional
///     Ending node.
/// weight : str or None, optional
///     Edge attribute to use as weight. None means unweighted (BFS).
/// method : str, optional
///     Algorithm: 'dijkstra' (default) or 'bellman-ford'.
///
/// Returns
/// -------
/// list or dict
///     If source and target are given: a list of nodes.
///     If only source: dict mapping target -> path.
///     If neither: dict mapping source -> dict mapping target -> path.
#[pyfunction]
#[pyo3(signature = (g, source=None, target=None, weight=None, method="dijkstra"))]
pub fn shortest_path(
    py: Python<'_>,
    g: &PyGraph,
    source: Option<&Bound<'_, PyAny>>,
    target: Option<&Bound<'_, PyAny>>,
    weight: Option<&str>,
    method: &str,
) -> PyResult<PyObject> {
    match (source, target) {
        (Some(src), Some(tgt)) => {
            let s = node_key_to_string(py, src)?;
            let t = node_key_to_string(py, tgt)?;
            validate_node_exists(g, &s, src)?;
            validate_node_exists(g, &t, tgt)?;

            let path = compute_single_shortest_path(g, &s, &t, weight, method)?;
            match path {
                Some(p) => {
                    let py_path: Vec<PyObject> =
                        p.iter().map(|n| g.py_node_key(py, n)).collect();
                    Ok(py_path.into_pyobject(py)?.into_any().unbind())
                }
                None => Err(NetworkXNoPath::new_err(format!(
                    "No path between {} and {}.",
                    s, t
                ))),
            }
        }
        (Some(src), None) => {
            // Single source → dict {target: path}
            let s = node_key_to_string(py, src)?;
            validate_node_exists(g, &s, src)?;
            let result = PyDict::new(py);
            for node in g.inner.nodes_ordered() {
                if let Some(p) = compute_single_shortest_path(g, &s, node, weight, method)? {
                    let py_path: Vec<PyObject> =
                        p.iter().map(|n| g.py_node_key(py, n)).collect();
                    result.set_item(g.py_node_key(py, node), py_path)?;
                }
            }
            Ok(result.into_any().unbind())
        }
        (None, Some(tgt)) => {
            // Single target → dict {source: path}
            let t = node_key_to_string(py, tgt)?;
            validate_node_exists(g, &t, tgt)?;
            let result = PyDict::new(py);
            for node in g.inner.nodes_ordered() {
                if let Some(p) = compute_single_shortest_path(g, node, &t, weight, method)? {
                    let py_path: Vec<PyObject> =
                        p.iter().map(|n| g.py_node_key(py, n)).collect();
                    result.set_item(g.py_node_key(py, node), py_path)?;
                }
            }
            Ok(result.into_any().unbind())
        }
        (None, None) => {
            // All pairs → dict {source: {target: path}}
            let result = PyDict::new(py);
            for src_node in g.inner.nodes_ordered() {
                let inner = PyDict::new(py);
                for tgt_node in g.inner.nodes_ordered() {
                    if let Some(p) =
                        compute_single_shortest_path(g, src_node, tgt_node, weight, method)?
                    {
                        let py_path: Vec<PyObject> =
                            p.iter().map(|n| g.py_node_key(py, n)).collect();
                        inner.set_item(g.py_node_key(py, tgt_node), py_path)?;
                    }
                }
                result.set_item(g.py_node_key(py, src_node), inner)?;
            }
            Ok(result.into_any().unbind())
        }
    }
}

// ---------------------------------------------------------------------------
// shortest_path_length
// ---------------------------------------------------------------------------

/// Return the shortest path length between source and target.
///
/// Parameters
/// ----------
/// G : Graph
/// source : node
/// target : node
/// weight : str or None
///     Currently only unweighted (BFS) length is supported.
///
/// Returns
/// -------
/// int
///     Length of the shortest path.
#[pyfunction]
#[pyo3(signature = (g, source, target, weight=None))]
pub fn shortest_path_length(
    py: Python<'_>,
    g: &PyGraph,
    source: &Bound<'_, PyAny>,
    target: &Bound<'_, PyAny>,
    weight: Option<&str>,
) -> PyResult<PyObject> {
    let s = node_key_to_string(py, source)?;
    let t = node_key_to_string(py, target)?;
    validate_node_exists(g, &s, source)?;
    validate_node_exists(g, &t, target)?;

    if let Some(_w) = weight {
        // Use weighted shortest path and sum weights
        let result = fnx_algorithms::shortest_path_weighted(&g.inner, &s, &t, _w);
        match result.path {
            Some(path) => {
                // Sum the edge weights along the path
                let mut total: f64 = 0.0;
                for i in 0..path.len() - 1 {
                    let attrs = g.inner.edge_attrs(&path[i], &path[i + 1]);
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
        let result = fnx_algorithms::shortest_path_length(&g.inner, &s, &t);
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

/// Return True if there is a path between source and target.
#[pyfunction]
pub fn has_path(
    py: Python<'_>,
    g: &PyGraph,
    source: &Bound<'_, PyAny>,
    target: &Bound<'_, PyAny>,
) -> PyResult<bool> {
    let s = node_key_to_string(py, source)?;
    let t = node_key_to_string(py, target)?;
    validate_node_exists(g, &s, source)?;
    validate_node_exists(g, &t, target)?;
    let result = fnx_algorithms::has_path(&g.inner, &s, &t);
    Ok(result.has_path)
}

// ---------------------------------------------------------------------------
// average_shortest_path_length
// ---------------------------------------------------------------------------

/// Return the average shortest path length of the graph.
///
/// Raises ``NetworkXError`` if the graph is not connected.
#[pyfunction]
#[pyo3(signature = (g, weight=None))]
pub fn average_shortest_path_length(
    py: Python<'_>,
    g: &PyGraph,
    weight: Option<&str>,
) -> PyResult<f64> {
    if weight.is_some() {
        return Err(crate::NetworkXNotImplemented::new_err(
            "weighted average_shortest_path_length not yet supported",
        ));
    }
    let inner = &g.inner;
    let (connected, avg) = py.allow_threads(|| {
        let conn = fnx_algorithms::is_connected(inner);
        let result = fnx_algorithms::average_shortest_path_length(inner);
        (conn.is_connected, result.average_shortest_path_length)
    });
    if !connected {
        return Err(NetworkXError::new_err(
            "Graph is not connected, so d(u,v) is infinite for some pairs.",
        ));
    }
    Ok(avg)
}

// ---------------------------------------------------------------------------
// dijkstra_path
// ---------------------------------------------------------------------------

/// Return the shortest weighted path using Dijkstra's algorithm.
#[pyfunction]
#[pyo3(signature = (g, source, target, weight="weight"))]
pub fn dijkstra_path(
    py: Python<'_>,
    g: &PyGraph,
    source: &Bound<'_, PyAny>,
    target: &Bound<'_, PyAny>,
    weight: &str,
) -> PyResult<Vec<PyObject>> {
    let s = node_key_to_string(py, source)?;
    let t = node_key_to_string(py, target)?;
    validate_node_exists(g, &s, source)?;
    validate_node_exists(g, &t, target)?;

    let result = fnx_algorithms::shortest_path_weighted(&g.inner, &s, &t, weight);
    match result.path {
        Some(p) => Ok(p.iter().map(|n| g.py_node_key(py, n)).collect()),
        None => Err(NetworkXNoPath::new_err(format!(
            "No path between {} and {}.",
            s, t
        ))),
    }
}

// ---------------------------------------------------------------------------
// bellman_ford_path
// ---------------------------------------------------------------------------

/// Return the shortest weighted path using Bellman-Ford algorithm.
///
/// This handles negative edge weights but raises if a negative cycle exists.
#[pyfunction]
#[pyo3(signature = (g, source, target, weight="weight"))]
pub fn bellman_ford_path(
    py: Python<'_>,
    g: &PyGraph,
    source: &Bound<'_, PyAny>,
    target: &Bound<'_, PyAny>,
    weight: &str,
) -> PyResult<Vec<PyObject>> {
    let s = node_key_to_string(py, source)?;
    let t = node_key_to_string(py, target)?;
    validate_node_exists(g, &s, source)?;
    validate_node_exists(g, &t, target)?;

    let result = fnx_algorithms::bellman_ford_shortest_paths(&g.inner, &s, weight);
    if result.negative_cycle_detected {
        return Err(crate::NetworkXUnbounded::new_err(
            "Negative cost cycle detected.",
        ));
    }

    // Reconstruct path from predecessors
    let pred_map: std::collections::HashMap<&str, Option<&str>> = result
        .predecessors
        .iter()
        .map(|e| (e.node.as_str(), e.predecessor.as_deref()))
        .collect();

    // Check target is reachable
    if !pred_map.contains_key(t.as_str()) {
        return Err(NetworkXNoPath::new_err(format!(
            "No path between {} and {}.",
            s, t
        )));
    }

    // Build path by walking predecessors from target to source
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
    Ok(path.iter().map(|n| g.py_node_key(py, n)).collect())
}

// ---------------------------------------------------------------------------
// multi_source_dijkstra
// ---------------------------------------------------------------------------

/// Find shortest weighted paths from multiple source nodes.
///
/// Returns
/// -------
/// tuple of (distances, paths)
///     distances: dict mapping node -> float distance
///     paths: dict mapping node -> list of nodes
#[pyfunction]
#[pyo3(signature = (g, sources, weight="weight"))]
pub fn multi_source_dijkstra(
    py: Python<'_>,
    g: &PyGraph,
    sources: &Bound<'_, PyAny>,
    weight: &str,
) -> PyResult<(PyObject, PyObject)> {
    // Convert sources to canonical strings
    let iter = pyo3::types::PyIterator::from_object(sources)?;
    let mut source_strs = Vec::new();
    for item in iter {
        let item = item?;
        let s = node_key_to_string(py, &item)?;
        validate_node_exists_str(g, &s)?;
        source_strs.push(s);
    }
    let source_refs: Vec<&str> = source_strs.iter().map(String::as_str).collect();

    let result = fnx_algorithms::multi_source_dijkstra(&g.inner, &source_refs, weight);

    // Build distance dict
    let dist_dict = PyDict::new(py);
    for entry in &result.distances {
        dist_dict.set_item(g.py_node_key(py, &entry.node), entry.distance)?;
    }

    // Build paths dict by reconstructing from predecessors
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
        let py_path: Vec<PyObject> = path.iter().map(|n| g.py_node_key(py, n)).collect();
        paths_dict.set_item(g.py_node_key(py, &entry.node), py_path)?;
    }

    Ok((
        dist_dict.into_any().unbind(),
        paths_dict.into_any().unbind(),
    ))
}

// ---------------------------------------------------------------------------
// is_connected
// ---------------------------------------------------------------------------

/// Return True if the graph is connected.
#[pyfunction]
pub fn is_connected(py: Python<'_>, g: &PyGraph) -> bool {
    let inner = &g.inner;
    py.allow_threads(|| fnx_algorithms::is_connected(inner).is_connected)
}

// ---------------------------------------------------------------------------
// density
// ---------------------------------------------------------------------------

/// Return the density of the graph.
#[pyfunction]
pub fn density(py: Python<'_>, g: &PyGraph) -> f64 {
    let inner = &g.inner;
    py.allow_threads(|| fnx_algorithms::density(inner).density)
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

fn validate_node_exists(g: &PyGraph, canonical: &str, py_key: &Bound<'_, PyAny>) -> PyResult<()> {
    if !g.inner.has_node(canonical) {
        return Err(NodeNotFound::new_err(format!(
            "Node {} is not in G",
            py_key.repr()?
        )));
    }
    Ok(())
}

fn validate_node_exists_str(g: &PyGraph, canonical: &str) -> PyResult<()> {
    if !g.inner.has_node(canonical) {
        return Err(NodeNotFound::new_err(format!(
            "Node '{}' is not in G",
            canonical
        )));
    }
    Ok(())
}

fn compute_single_shortest_path(
    g: &PyGraph,
    source: &str,
    target: &str,
    weight: Option<&str>,
    method: &str,
) -> PyResult<Option<Vec<String>>> {
    match weight {
        None => {
            let result = fnx_algorithms::shortest_path_unweighted(&g.inner, source, target);
            Ok(result.path)
        }
        Some(w) => match method {
            "dijkstra" => {
                let result = fnx_algorithms::shortest_path_weighted(&g.inner, source, target, w);
                Ok(result.path)
            }
            "bellman-ford" => {
                let result = fnx_algorithms::bellman_ford_shortest_paths(&g.inner, source, w);
                if result.negative_cycle_detected {
                    return Err(crate::NetworkXUnbounded::new_err(
                        "Negative cost cycle detected.",
                    ));
                }
                // Reconstruct path to target from predecessors
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

// ===========================================================================
// Connectivity algorithms
// ===========================================================================

/// Return the connected components as a list of sets.
#[pyfunction]
pub fn connected_components(py: Python<'_>, g: &PyGraph) -> Vec<PyObject> {
    let inner = &g.inner;
    let result = py.allow_threads(|| fnx_algorithms::connected_components(inner));
    result
        .components
        .iter()
        .map(|comp| {
            let py_set: Vec<PyObject> = comp.iter().map(|n| g.py_node_key(py, n)).collect();
            py_set.into_pyobject(py).unwrap().into_any().unbind()
        })
        .collect()
}

/// Return the number of connected components.
#[pyfunction]
pub fn number_connected_components(py: Python<'_>, g: &PyGraph) -> usize {
    let inner = &g.inner;
    py.allow_threads(|| fnx_algorithms::number_connected_components(inner).count)
}

/// Return the node connectivity of the graph.
#[pyfunction]
pub fn node_connectivity(py: Python<'_>, g: &PyGraph) -> usize {
    let inner = &g.inner;
    py.allow_threads(|| fnx_algorithms::global_node_connectivity(inner).value)
}

/// Return a minimum node cut of the graph.
#[pyfunction]
pub fn minimum_node_cut(py: Python<'_>, g: &PyGraph) -> Vec<PyObject> {
    let inner = &g.inner;
    let result = py.allow_threads(|| fnx_algorithms::global_minimum_node_cut(inner));
    result
        .cut_nodes
        .iter()
        .map(|n| g.py_node_key(py, n))
        .collect()
}

/// Return the edge connectivity of the graph.
#[pyfunction]
#[pyo3(signature = (g, capacity="capacity"))]
pub fn edge_connectivity(py: Python<'_>, g: &PyGraph, capacity: &str) -> f64 {
    let inner = &g.inner;
    let cap = capacity.to_owned();
    py.allow_threads(move || fnx_algorithms::global_edge_connectivity_edmonds_karp(inner, &cap).value)
}

/// Return articulation points (cut vertices) of the graph.
#[pyfunction]
pub fn articulation_points(py: Python<'_>, g: &PyGraph) -> Vec<PyObject> {
    let inner = &g.inner;
    let result = py.allow_threads(|| fnx_algorithms::articulation_points(inner));
    result
        .nodes
        .iter()
        .map(|n| g.py_node_key(py, n))
        .collect()
}

/// Return bridges (cut edges) of the graph.
#[pyfunction]
pub fn bridges(py: Python<'_>, g: &PyGraph) -> Vec<(PyObject, PyObject)> {
    let inner = &g.inner;
    let result = py.allow_threads(|| fnx_algorithms::bridges(inner));
    result
        .edges
        .iter()
        .map(|(u, v)| (g.py_node_key(py, u), g.py_node_key(py, v)))
        .collect()
}

// ===========================================================================
// Centrality algorithms
// ===========================================================================

/// Helper to convert CentralityScore vec to Python dict.
fn centrality_to_dict(py: Python<'_>, g: &PyGraph, scores: &[fnx_algorithms::CentralityScore]) -> PyResult<Py<PyDict>> {
    let dict = PyDict::new(py);
    for s in scores {
        dict.set_item(g.py_node_key(py, &s.node), s.score)?;
    }
    Ok(dict.unbind())
}

/// Return the degree centrality for all nodes.
#[pyfunction]
pub fn degree_centrality(py: Python<'_>, g: &PyGraph) -> PyResult<Py<PyDict>> {
    let inner = &g.inner;
    let result = py.allow_threads(|| fnx_algorithms::degree_centrality(inner));
    centrality_to_dict(py, g, &result.scores)
}

/// Return the closeness centrality for all nodes.
#[pyfunction]
pub fn closeness_centrality(py: Python<'_>, g: &PyGraph) -> PyResult<Py<PyDict>> {
    let inner = &g.inner;
    let result = py.allow_threads(|| fnx_algorithms::closeness_centrality(inner));
    centrality_to_dict(py, g, &result.scores)
}

/// Return the harmonic centrality for all nodes.
#[pyfunction]
pub fn harmonic_centrality(py: Python<'_>, g: &PyGraph) -> PyResult<Py<PyDict>> {
    let inner = &g.inner;
    let result = py.allow_threads(|| fnx_algorithms::harmonic_centrality(inner));
    centrality_to_dict(py, g, &result.scores)
}

/// Return the Katz centrality for all nodes.
#[pyfunction]
pub fn katz_centrality(py: Python<'_>, g: &PyGraph) -> PyResult<Py<PyDict>> {
    let inner = &g.inner;
    let result = py.allow_threads(|| fnx_algorithms::katz_centrality(inner));
    centrality_to_dict(py, g, &result.scores)
}

/// Return the betweenness centrality for all nodes.
#[pyfunction]
pub fn betweenness_centrality(py: Python<'_>, g: &PyGraph) -> PyResult<Py<PyDict>> {
    let inner = &g.inner;
    let result = py.allow_threads(|| fnx_algorithms::betweenness_centrality(inner));
    centrality_to_dict(py, g, &result.scores)
}

/// Return the edge betweenness centrality for all edges.
#[pyfunction]
pub fn edge_betweenness_centrality(py: Python<'_>, g: &PyGraph) -> PyResult<Py<PyDict>> {
    let inner = &g.inner;
    let result = py.allow_threads(|| fnx_algorithms::edge_betweenness_centrality(inner));
    let dict = PyDict::new(py);
    for s in &result.scores {
        let key = pyo3::types::PyTuple::new(py, &[
            g.py_node_key(py, &s.left),
            g.py_node_key(py, &s.right),
        ])?;
        dict.set_item(key, s.score)?;
    }
    Ok(dict.unbind())
}

/// Return the eigenvector centrality for all nodes.
#[pyfunction]
pub fn eigenvector_centrality(py: Python<'_>, g: &PyGraph) -> PyResult<Py<PyDict>> {
    let inner = &g.inner;
    let result = py.allow_threads(|| fnx_algorithms::eigenvector_centrality(inner));
    centrality_to_dict(py, g, &result.scores)
}

/// Return the PageRank for all nodes.
#[pyfunction]
pub fn pagerank(py: Python<'_>, g: &PyGraph) -> PyResult<Py<PyDict>> {
    let inner = &g.inner;
    let result = py.allow_threads(|| fnx_algorithms::pagerank(inner));
    centrality_to_dict(py, g, &result.scores)
}

/// Return HITS hubs and authorities scores.
///
/// Returns (hubs_dict, authorities_dict).
#[pyfunction]
pub fn hits(py: Python<'_>, g: &PyGraph) -> PyResult<(Py<PyDict>, Py<PyDict>)> {
    let inner = &g.inner;
    let result = py.allow_threads(|| fnx_algorithms::hits_centrality(inner));
    let hubs = centrality_to_dict(py, g, &result.hubs)?;
    let auths = centrality_to_dict(py, g, &result.authorities)?;
    Ok((hubs, auths))
}

/// Return the average neighbor degree for each node.
#[pyfunction]
pub fn average_neighbor_degree(py: Python<'_>, g: &PyGraph) -> PyResult<Py<PyDict>> {
    let inner = &g.inner;
    let result = py.allow_threads(|| fnx_algorithms::average_neighbor_degree(inner));
    let dict = PyDict::new(py);
    for s in &result.scores {
        dict.set_item(g.py_node_key(py, &s.node), s.avg_neighbor_degree)?;
    }
    Ok(dict.unbind())
}

/// Return the degree assortativity coefficient.
#[pyfunction]
pub fn degree_assortativity_coefficient(py: Python<'_>, g: &PyGraph) -> f64 {
    let inner = &g.inner;
    py.allow_threads(|| fnx_algorithms::degree_assortativity_coefficient(inner).coefficient)
}

/// Return a list of nodes in decreasing voterank order.
#[pyfunction]
pub fn voterank(py: Python<'_>, g: &PyGraph) -> Vec<PyObject> {
    let inner = &g.inner;
    let result = py.allow_threads(|| fnx_algorithms::voterank(inner));
    result.ranked.iter().map(|n| g.py_node_key(py, n)).collect()
}

// ===========================================================================
// Clustering algorithms
// ===========================================================================

/// Return the clustering coefficient for each node.
#[pyfunction]
pub fn clustering(py: Python<'_>, g: &PyGraph) -> PyResult<Py<PyDict>> {
    let inner = &g.inner;
    let result = py.allow_threads(|| fnx_algorithms::clustering_coefficient(inner));
    centrality_to_dict(py, g, &result.scores)
}

/// Return the average clustering coefficient.
#[pyfunction]
pub fn average_clustering(py: Python<'_>, g: &PyGraph) -> f64 {
    let inner = &g.inner;
    py.allow_threads(|| fnx_algorithms::clustering_coefficient(inner).average_clustering)
}

/// Return the transitivity (global clustering coefficient).
#[pyfunction]
pub fn transitivity(py: Python<'_>, g: &PyGraph) -> f64 {
    let inner = &g.inner;
    py.allow_threads(|| fnx_algorithms::clustering_coefficient(inner).transitivity)
}

/// Return the number of triangles for each node.
#[pyfunction]
pub fn triangles(py: Python<'_>, g: &PyGraph) -> PyResult<Py<PyDict>> {
    let inner = &g.inner;
    let result = py.allow_threads(|| fnx_algorithms::triangles(inner));
    let dict = PyDict::new(py);
    for t in &result.triangles {
        dict.set_item(g.py_node_key(py, &t.node), t.count)?;
    }
    Ok(dict.unbind())
}

/// Return the square clustering coefficient for each node.
#[pyfunction]
pub fn square_clustering(py: Python<'_>, g: &PyGraph) -> PyResult<Py<PyDict>> {
    let inner = &g.inner;
    let result = py.allow_threads(|| fnx_algorithms::square_clustering(inner));
    centrality_to_dict(py, g, &result.scores)
}

/// Return all maximal cliques as a list of lists.
#[pyfunction]
pub fn find_cliques(py: Python<'_>, g: &PyGraph) -> Vec<Vec<PyObject>> {
    let inner = &g.inner;
    let result = py.allow_threads(|| fnx_algorithms::find_cliques(inner));
    result
        .cliques
        .iter()
        .map(|clique| clique.iter().map(|n| g.py_node_key(py, n)).collect())
        .collect()
}

/// Return the size of the largest maximal clique.
#[pyfunction]
pub fn graph_clique_number(py: Python<'_>, g: &PyGraph) -> usize {
    let inner = &g.inner;
    py.allow_threads(|| fnx_algorithms::graph_clique_number(inner).clique_number)
}

// ===========================================================================
// Matching algorithms
// ===========================================================================

/// Return a maximal matching as a set of edge tuples.
#[pyfunction]
pub fn maximal_matching(py: Python<'_>, g: &PyGraph) -> Vec<(PyObject, PyObject)> {
    let inner = &g.inner;
    let result = py.allow_threads(|| fnx_algorithms::maximal_matching(inner));
    result
        .matching
        .iter()
        .map(|(u, v)| (g.py_node_key(py, u), g.py_node_key(py, v)))
        .collect()
}

/// Return a max-weight matching as a set of edge tuples.
#[pyfunction]
#[pyo3(signature = (g, weight="weight"))]
pub fn max_weight_matching(py: Python<'_>, g: &PyGraph, weight: &str) -> Vec<(PyObject, PyObject)> {
    let inner = &g.inner;
    let w = weight.to_owned();
    let result = py.allow_threads(move || fnx_algorithms::min_weight_matching(inner, &w));
    result
        .matching
        .iter()
        .map(|(u, v)| (g.py_node_key(py, u), g.py_node_key(py, v)))
        .collect()
}

/// Return a min-weight matching as a set of edge tuples.
#[pyfunction]
#[pyo3(signature = (g, weight="weight"))]
pub fn min_weight_matching(py: Python<'_>, g: &PyGraph, weight: &str) -> Vec<(PyObject, PyObject)> {
    let inner = &g.inner;
    let w = weight.to_owned();
    let result = py.allow_threads(move || fnx_algorithms::min_weight_matching(inner, &w));
    result
        .matching
        .iter()
        .map(|(u, v)| (g.py_node_key(py, u), g.py_node_key(py, v)))
        .collect()
}

/// Return a minimum edge cover as a set of edge tuples.
#[pyfunction]
pub fn min_edge_cover(py: Python<'_>, g: &PyGraph) -> PyResult<Vec<(PyObject, PyObject)>> {
    let inner = &g.inner;
    let result = py.allow_threads(|| fnx_algorithms::min_edge_cover(inner));
    match result {
        Some(r) => Ok(r
            .edges
            .iter()
            .map(|(u, v)| (g.py_node_key(py, u), g.py_node_key(py, v)))
            .collect()),
        None => Err(NetworkXError::new_err(
            "Graph has isolated nodes, no edge cover exists.",
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
    g: &PyGraph,
    source: &Bound<'_, PyAny>,
    sink: &Bound<'_, PyAny>,
    capacity: &str,
) -> PyResult<f64> {
    let s = node_key_to_string(py, source)?;
    let t = node_key_to_string(py, sink)?;
    let inner = &g.inner;
    let cap = capacity.to_owned();
    Ok(py.allow_threads(move || fnx_algorithms::max_flow_edmonds_karp(inner, &s, &t, &cap).value))
}

/// Return the minimum cut value between source and sink.
#[pyfunction]
#[pyo3(signature = (g, source, sink, capacity="capacity"))]
pub fn minimum_cut_value(
    py: Python<'_>,
    g: &PyGraph,
    source: &Bound<'_, PyAny>,
    sink: &Bound<'_, PyAny>,
    capacity: &str,
) -> PyResult<f64> {
    let s = node_key_to_string(py, source)?;
    let t = node_key_to_string(py, sink)?;
    let inner = &g.inner;
    let cap = capacity.to_owned();
    Ok(py.allow_threads(move || fnx_algorithms::minimum_cut_edmonds_karp(inner, &s, &t, &cap).value))
}

// ===========================================================================
// Distance measures
// ===========================================================================

/// Return the eccentricity of each node as a dict.
#[pyfunction]
pub fn eccentricity(py: Python<'_>, g: &PyGraph) -> PyResult<Py<PyDict>> {
    let inner = &g.inner;
    let result = py.allow_threads(|| fnx_algorithms::distance_measures(inner));
    let dict = PyDict::new(py);
    for e in &result.eccentricity {
        dict.set_item(g.py_node_key(py, &e.node), e.value)?;
    }
    Ok(dict.unbind())
}

/// Return the diameter of the graph.
#[pyfunction]
pub fn diameter(py: Python<'_>, g: &PyGraph) -> PyResult<usize> {
    let inner = &g.inner;
    let (connected, result) = py.allow_threads(|| {
        let c = fnx_algorithms::is_connected(inner);
        let r = fnx_algorithms::distance_measures(inner);
        (c.is_connected, r)
    });
    if !connected {
        return Err(NetworkXError::new_err("Graph is not connected."));
    }
    Ok(result.diameter)
}

/// Return the radius of the graph.
#[pyfunction]
pub fn radius(py: Python<'_>, g: &PyGraph) -> PyResult<usize> {
    let inner = &g.inner;
    let (connected, result) = py.allow_threads(|| {
        let c = fnx_algorithms::is_connected(inner);
        let r = fnx_algorithms::distance_measures(inner);
        (c.is_connected, r)
    });
    if !connected {
        return Err(NetworkXError::new_err("Graph is not connected."));
    }
    Ok(result.radius)
}

/// Return the center of the graph.
#[pyfunction]
pub fn center(py: Python<'_>, g: &PyGraph) -> PyResult<Vec<PyObject>> {
    let inner = &g.inner;
    let (connected, result) = py.allow_threads(|| {
        let c = fnx_algorithms::is_connected(inner);
        let r = fnx_algorithms::distance_measures(inner);
        (c.is_connected, r)
    });
    if !connected {
        return Err(NetworkXError::new_err("Graph is not connected."));
    }
    Ok(result.center.iter().map(|n| g.py_node_key(py, n)).collect())
}

/// Return the periphery of the graph.
#[pyfunction]
pub fn periphery(py: Python<'_>, g: &PyGraph) -> PyResult<Vec<PyObject>> {
    let inner = &g.inner;
    let (connected, result) = py.allow_threads(|| {
        let c = fnx_algorithms::is_connected(inner);
        let r = fnx_algorithms::distance_measures(inner);
        (c.is_connected, r)
    });
    if !connected {
        return Err(NetworkXError::new_err("Graph is not connected."));
    }
    Ok(result
        .periphery
        .iter()
        .map(|n| g.py_node_key(py, n))
        .collect())
}

// ===========================================================================
// Tree, forest, bipartite, coloring, core algorithms
// ===========================================================================

/// Return True if the graph is a tree.
#[pyfunction]
pub fn is_tree(py: Python<'_>, g: &PyGraph) -> bool {
    let inner = &g.inner;
    py.allow_threads(|| fnx_algorithms::is_tree(inner).is_tree)
}

/// Return True if the graph is a forest.
#[pyfunction]
pub fn is_forest(py: Python<'_>, g: &PyGraph) -> bool {
    let inner = &g.inner;
    py.allow_threads(|| fnx_algorithms::is_forest(inner).is_forest)
}

/// Return True if the graph is bipartite.
#[pyfunction]
pub fn is_bipartite(py: Python<'_>, g: &PyGraph) -> bool {
    let inner = &g.inner;
    py.allow_threads(|| fnx_algorithms::is_bipartite(inner).is_bipartite)
}

/// Return the two bipartite node sets.
#[pyfunction]
pub fn bipartite_sets(
    py: Python<'_>,
    g: &PyGraph,
) -> PyResult<(Vec<PyObject>, Vec<PyObject>)> {
    let inner = &g.inner;
    let result = py.allow_threads(|| fnx_algorithms::bipartite_sets(inner));
    if !result.is_bipartite {
        return Err(NetworkXError::new_err("Graph is not bipartite."));
    }
    let a: Vec<PyObject> = result.set_a.iter().map(|n| g.py_node_key(py, n)).collect();
    let b: Vec<PyObject> = result.set_b.iter().map(|n| g.py_node_key(py, n)).collect();
    Ok((a, b))
}

/// Return a greedy graph coloring as a dict mapping node -> color.
#[pyfunction]
pub fn greedy_color(py: Python<'_>, g: &PyGraph) -> PyResult<Py<PyDict>> {
    let inner = &g.inner;
    let result = py.allow_threads(|| fnx_algorithms::greedy_color(inner));
    let dict = PyDict::new(py);
    for nc in &result.coloring {
        dict.set_item(g.py_node_key(py, &nc.node), nc.color)?;
    }
    Ok(dict.unbind())
}

/// Return the core number for each node.
#[pyfunction]
pub fn core_number(py: Python<'_>, g: &PyGraph) -> PyResult<Py<PyDict>> {
    let inner = &g.inner;
    let result = py.allow_threads(|| fnx_algorithms::core_number(inner));
    let dict = PyDict::new(py);
    for nc in &result.core_numbers {
        dict.set_item(g.py_node_key(py, &nc.node), nc.core)?;
    }
    Ok(dict.unbind())
}

/// Return a minimum spanning tree as a new Graph.
#[pyfunction]
#[pyo3(signature = (g, weight="weight"))]
pub fn minimum_spanning_tree(
    py: Python<'_>,
    g: &PyGraph,
    weight: &str,
) -> PyResult<PyGraph> {
    let inner = &g.inner;
    let w = weight.to_owned();
    let result = py.allow_threads(move || fnx_algorithms::minimum_spanning_tree(inner, &w));
    let mut new_graph = PyGraph::new_empty(py)?;
    // Add all nodes from original graph
    for node in g.inner.nodes_ordered() {
        new_graph.inner.add_node(node.to_owned());
        if let Some(py_key) = g.node_key_map.get(node) {
            new_graph
                .node_key_map
                .insert(node.to_owned(), py_key.clone_ref(py));
        }
    }
    // Add MST edges
    for edge in &result.edges {
        let _ = new_graph.inner.add_edge(edge.left.clone(), edge.right.clone());
        // Copy edge attrs from original graph if present
        let ek = PyGraph::edge_key(&edge.left, &edge.right);
        if let Some(attrs) = g.edge_py_attrs.get(&ek) {
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
pub fn is_eulerian(py: Python<'_>, g: &PyGraph) -> bool {
    let inner = &g.inner;
    py.allow_threads(|| fnx_algorithms::is_eulerian(inner).is_eulerian)
}

/// Return True if the graph has an Eulerian path.
#[pyfunction]
pub fn has_eulerian_path(py: Python<'_>, g: &PyGraph) -> bool {
    let inner = &g.inner;
    py.allow_threads(|| fnx_algorithms::has_eulerian_path(inner).has_eulerian_path)
}

/// Return True if the graph is semi-Eulerian.
#[pyfunction]
pub fn is_semieulerian(py: Python<'_>, g: &PyGraph) -> bool {
    let inner = &g.inner;
    py.allow_threads(|| fnx_algorithms::is_semieulerian(inner).is_semieulerian)
}

/// Return an Eulerian circuit as a list of edge tuples.
#[pyfunction]
#[pyo3(signature = (g, source=None))]
pub fn eulerian_circuit(
    py: Python<'_>,
    g: &PyGraph,
    source: Option<&Bound<'_, PyAny>>,
) -> PyResult<Vec<(PyObject, PyObject)>> {
    let src = source
        .map(|s| node_key_to_string(py, s))
        .transpose()?;
    let inner = &g.inner;
    let result = py.allow_threads(|| fnx_algorithms::eulerian_circuit(inner, src.as_deref()));
    match result {
        Some(r) => Ok(r
            .edges
            .iter()
            .map(|(u, v)| (g.py_node_key(py, u), g.py_node_key(py, v)))
            .collect()),
        None => Err(NetworkXError::new_err("Graph is not Eulerian.")),
    }
}

/// Return an Eulerian path as a list of edge tuples.
#[pyfunction]
#[pyo3(signature = (g, source=None))]
pub fn eulerian_path(
    py: Python<'_>,
    g: &PyGraph,
    source: Option<&Bound<'_, PyAny>>,
) -> PyResult<Vec<(PyObject, PyObject)>> {
    let src = source
        .map(|s| node_key_to_string(py, s))
        .transpose()?;
    let inner = &g.inner;
    let result = py.allow_threads(|| fnx_algorithms::eulerian_path(inner, src.as_deref()));
    match result {
        Some(r) => Ok(r
            .edges
            .iter()
            .map(|(u, v)| (g.py_node_key(py, u), g.py_node_key(py, v)))
            .collect()),
        None => Err(NetworkXError::new_err("Graph has no Eulerian path.")),
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
    g: &PyGraph,
    source: &Bound<'_, PyAny>,
    target: &Bound<'_, PyAny>,
    cutoff: Option<usize>,
) -> PyResult<Vec<Vec<PyObject>>> {
    let s = node_key_to_string(py, source)?;
    let t = node_key_to_string(py, target)?;
    let inner = &g.inner;
    let result = py.allow_threads(|| fnx_algorithms::all_simple_paths(inner, &s, &t, cutoff));
    Ok(result
        .paths
        .iter()
        .map(|path| path.iter().map(|n| g.py_node_key(py, n)).collect())
        .collect())
}

/// Return a list of cycles forming a basis for the cycle space.
#[pyfunction]
#[pyo3(signature = (g, root=None))]
pub fn cycle_basis(
    py: Python<'_>,
    g: &PyGraph,
    root: Option<&Bound<'_, PyAny>>,
) -> PyResult<Vec<Vec<PyObject>>> {
    let r = root
        .map(|r| node_key_to_string(py, r))
        .transpose()?;
    let inner = &g.inner;
    let result = py.allow_threads(|| fnx_algorithms::cycle_basis(inner, r.as_deref()));
    Ok(result
        .cycles
        .iter()
        .map(|cycle| cycle.iter().map(|n| g.py_node_key(py, n)).collect())
        .collect())
}

// ===========================================================================
// Graph efficiency measures
// ===========================================================================

/// Return the global efficiency of the graph.
#[pyfunction]
pub fn global_efficiency(py: Python<'_>, g: &PyGraph) -> f64 {
    let inner = &g.inner;
    py.allow_threads(|| fnx_algorithms::global_efficiency(inner).efficiency)
}

/// Return the local efficiency of the graph.
#[pyfunction]
pub fn local_efficiency(py: Python<'_>, g: &PyGraph) -> f64 {
    let inner = &g.inner;
    py.allow_threads(|| fnx_algorithms::local_efficiency(inner).efficiency)
}

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
