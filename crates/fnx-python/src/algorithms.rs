//! Python bindings for FrankenNetworkX algorithms.
//!
//! Each function follows the NetworkX API signature, accepts a `Graph` or `DiGraph`,
//! delegates to the Rust implementation in `fnx_algorithms`, and returns
//! Python-native types (lists, dicts, floats, bools).

use crate::digraph::{PyDiGraph, PyMultiDiGraph};
use crate::{
    NetworkXError, NetworkXNoCycle, NetworkXNoPath, NetworkXUnfeasible, NodeNotFound, PyGraph,
    PyMultiGraph, node_key_to_string,
};
use fnx_classes::AttrMap;
use pyo3::exceptions::{PyIndexError, PyValueError, PyZeroDivisionError};
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList, PyTuple};
use std::collections::{HashMap, HashSet};

type SpanningEdgeSamples = (Vec<(String, String)>, Vec<f64>);

// ---------------------------------------------------------------------------
// GraphRef — unified graph access for algorithms accepting both Graph & DiGraph
// ---------------------------------------------------------------------------

/// Unified graph reference for algorithm bindings that accept Graph, DiGraph,
/// MultiGraph, or MultiDiGraph.
///
/// For undirected graphs, borrows the inner `Graph` directly.
/// For directed graphs, converts to undirected once and stores the result.
/// For multigraphs, converts to simple graph (collapsing parallel edges).
pub(crate) enum GraphRef<'py> {
    Undirected(PyRef<'py, PyGraph>),
    Directed {
        dg: PyRef<'py, PyDiGraph>,
        undirected: Box<fnx_classes::Graph>,
    },
    /// MultiGraph converted to simple undirected Graph.
    MultiUndirected {
        mg: PyRef<'py, PyMultiGraph>,
        simple: Box<fnx_classes::Graph>,
    },
    /// MultiDiGraph converted to simple DiGraph (+ its undirected projection).
    MultiDirected {
        mdg: PyRef<'py, PyMultiDiGraph>,
        simple_dg: Box<fnx_classes::digraph::DiGraph>,
        undirected: Box<fnx_classes::Graph>,
    },
}

enum WeightedGraphProjection<'a> {
    Borrowed(&'a fnx_classes::Graph),
    Owned(Box<fnx_classes::Graph>),
}

impl WeightedGraphProjection<'_> {
    fn as_ref(&self) -> &fnx_classes::Graph {
        match self {
            Self::Borrowed(graph) => graph,
            Self::Owned(graph) => graph,
        }
    }
}

enum WeightedDiGraphProjection<'a> {
    Borrowed(&'a fnx_classes::digraph::DiGraph),
    Owned(Box<fnx_classes::digraph::DiGraph>),
}

impl WeightedDiGraphProjection<'_> {
    fn as_ref(&self) -> &fnx_classes::digraph::DiGraph {
        match self {
            Self::Borrowed(graph) => graph,
            Self::Owned(graph) => graph,
        }
    }
}

impl<'py> GraphRef<'py> {
    /// Get a reference to the undirected graph (for algorithm dispatch).
    pub(crate) fn undirected(&self) -> &fnx_classes::Graph {
        match self {
            GraphRef::Undirected(pg) => &pg.inner,
            GraphRef::Directed { undirected, .. } | GraphRef::MultiDirected { undirected, .. } => {
                undirected
            }
            GraphRef::MultiUndirected { simple, .. } => simple,
        }
    }

    /// Convert a canonical node key to Python object.
    fn py_node_key(&self, py: Python<'_>, canonical: &str) -> PyObject {
        let key_map = self.node_key_map();
        key_map.get(canonical).map_or_else(
            || {
                crate::unwrap_infallible(canonical.to_owned().into_pyobject(py))
                    .into_any()
                    .unbind()
            },
            |obj| obj.clone_ref(py),
        )
    }

    /// Check if a node exists.
    fn has_node(&self, canonical: &str) -> bool {
        match self {
            GraphRef::Undirected(pg) => pg.inner.has_node(canonical),
            GraphRef::Directed { dg, .. } => dg.inner.has_node(canonical),
            GraphRef::MultiUndirected { mg, .. } => mg.inner.has_node(canonical),
            GraphRef::MultiDirected { mdg, .. } => mdg.inner.has_node(canonical),
        }
    }

    /// Is this a directed graph?
    pub(crate) fn is_directed(&self) -> bool {
        matches!(
            self,
            GraphRef::Directed { .. } | GraphRef::MultiDirected { .. }
        )
    }

    /// Get a reference to the inner DiGraph (for directed-specific algorithms).
    /// Returns `None` for undirected graphs.
    pub(crate) fn digraph(&self) -> Option<&fnx_classes::digraph::DiGraph> {
        match self {
            GraphRef::Directed { dg, .. } => Some(&dg.inner),
            GraphRef::MultiDirected { simple_dg, .. } => Some(simple_dg),
            _ => None,
        }
    }

    /// Get the original graph's node key map.
    fn node_key_map(&self) -> &HashMap<String, PyObject> {
        match self {
            GraphRef::Undirected(pg) => &pg.node_key_map,
            GraphRef::Directed { dg, .. } => &dg.node_key_map,
            GraphRef::MultiUndirected { mg, .. } => &mg.node_key_map,
            GraphRef::MultiDirected { mdg, .. } => &mdg.node_key_map,
        }
    }

    /// Look up edge attributes from the original graph for an undirected edge.
    /// For DiGraph, tries both directions.
    /// For multigraphs, returns first matching parallel edge's attributes.
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
            GraphRef::MultiUndirected { mg, .. } => {
                // Return first parallel edge's attrs (key 0)
                let ek = PyMultiGraph::edge_key(left, right, 0);
                mg.edge_py_attrs.get(&ek)
            }
            GraphRef::MultiDirected { mdg, .. } => {
                let ek1 = (left.to_owned(), right.to_owned(), 0);
                if let Some(attrs) = mdg.edge_py_attrs.get(&ek1) {
                    return Some(attrs);
                }
                let ek2 = (right.to_owned(), left.to_owned(), 0);
                mdg.edge_py_attrs.get(&ek2)
            }
        }
    }

    fn weighted_undirected_projection(&self, weight_attr: &str) -> WeightedGraphProjection<'_> {
        match self {
            GraphRef::Undirected(pg) => WeightedGraphProjection::Borrowed(&pg.inner),
            GraphRef::Directed { undirected, .. } => WeightedGraphProjection::Borrowed(undirected),
            GraphRef::MultiUndirected { mg, .. } => WeightedGraphProjection::Owned(Box::new(
                multigraph_to_weighted_simple_graph(&mg.inner, weight_attr),
            )),
            GraphRef::MultiDirected { .. } => WeightedGraphProjection::Borrowed(self.undirected()),
        }
    }

    fn weighted_digraph_projection(
        &self,
        weight_attr: &str,
    ) -> Option<WeightedDiGraphProjection<'_>> {
        match self {
            GraphRef::Directed { dg, .. } => Some(WeightedDiGraphProjection::Borrowed(&dg.inner)),
            GraphRef::MultiDirected { mdg, .. } => {
                Some(WeightedDiGraphProjection::Owned(Box::new(
                    multidigraph_to_weighted_simple_digraph(&mdg.inner, weight_attr),
                )))
            }
            _ => None,
        }
    }
}

/// Extract a `PyGraph`, `PyDiGraph`, `PyMultiGraph`, or `PyMultiDiGraph` from
/// a Python argument, converting multigraphs to simple graphs for algorithm dispatch.
pub(crate) fn extract_graph<'py>(g: &'py Bound<'py, PyAny>) -> PyResult<GraphRef<'py>> {
    if let Ok(pg) = g.extract::<PyRef<'py, PyGraph>>() {
        Ok(GraphRef::Undirected(pg))
    } else if let Ok(dg) = g.extract::<PyRef<'py, PyDiGraph>>() {
        let undirected = dg.inner.to_undirected();
        Ok(GraphRef::Directed {
            dg,
            undirected: Box::new(undirected),
        })
    } else if let Ok(mg) = g.extract::<PyRef<'py, PyMultiGraph>>() {
        // Convert MultiGraph to simple Graph by collapsing parallel edges.
        let simple = multigraph_to_simple_graph(&mg.inner);
        Ok(GraphRef::MultiUndirected {
            mg,
            simple: Box::new(simple),
        })
    } else if let Ok(mdg) = g.extract::<PyRef<'py, PyMultiDiGraph>>() {
        // Convert MultiDiGraph to simple DiGraph and its undirected projection.
        let simple_di = multidigraph_to_simple_digraph(&mdg.inner);
        let undirected = simple_di.to_undirected();
        Ok(GraphRef::MultiDirected {
            mdg,
            simple_dg: Box::new(simple_di),
            undirected: Box::new(undirected),
        })
    } else {
        Err(pyo3::exceptions::PyTypeError::new_err(
            "expected Graph, DiGraph, MultiGraph, or MultiDiGraph",
        ))
    }
}

/// Convert a MultiGraph to a simple Graph by collapsing parallel edges.
/// Edge attributes from the first parallel edge (key 0) are kept.
fn multigraph_to_simple_graph(mg: &fnx_classes::MultiGraph) -> fnx_classes::Graph {
    let mut g = fnx_classes::Graph::strict();
    for node in mg.nodes_ordered() {
        let attrs = mg.node_attrs(node).cloned().unwrap_or_default();
        g.add_node_with_attrs(node.to_owned(), attrs);
    }
    for edge in mg.edges_ordered() {
        // Only add the first parallel edge (skip duplicates)
        if !g.has_edge(&edge.left, &edge.right) {
            let _ = g.add_edge_with_attrs(edge.left, edge.right, edge.attrs);
        }
    }
    g
}

fn projected_weight(attrs: &AttrMap, weight_attr: &str) -> f64 {
    attrs
        .get(weight_attr)
        .and_then(|raw| raw.as_f64())
        .filter(|weight| weight.is_finite())
        .unwrap_or(1.0)
}

/// Convert a MultiGraph to a simple Graph by choosing the minimum-weight
/// parallel edge for each node pair, matching NetworkX shortest-path semantics.
fn multigraph_to_weighted_simple_graph(
    mg: &fnx_classes::MultiGraph,
    weight_attr: &str,
) -> fnx_classes::Graph {
    let mut g = fnx_classes::Graph::strict();
    let mut selected = HashMap::<(String, String), (f64, usize)>::new();

    for node in mg.nodes_ordered() {
        let attrs = mg.node_attrs(node).cloned().unwrap_or_default();
        g.add_node_with_attrs(node.to_owned(), attrs);
    }

    for edge in mg.edges_ordered() {
        let pair = (edge.left.clone(), edge.right.clone());
        let candidate_weight = projected_weight(&edge.attrs, weight_attr);
        match selected.get_mut(&pair) {
            Some((best_weight, best_key)) if candidate_weight < *best_weight => {
                *best_weight = candidate_weight;
                *best_key = edge.key;
            }
            None => {
                selected.insert(pair, (candidate_weight, edge.key));
            }
            _ => {}
        }
    }

    for edge in mg.edges_ordered() {
        let pair = (edge.left.clone(), edge.right.clone());
        if selected
            .get(&pair)
            .is_some_and(|(_, selected_key)| *selected_key == edge.key)
        {
            let _ = g.add_edge_with_attrs(edge.left, edge.right, edge.attrs);
        }
    }

    g
}

/// Convert a MultiDiGraph to a simple DiGraph by collapsing parallel edges.
fn multidigraph_to_simple_digraph(
    mdg: &fnx_classes::digraph::MultiDiGraph,
) -> fnx_classes::digraph::DiGraph {
    let mut dg = fnx_classes::digraph::DiGraph::strict();
    for node in mdg.nodes_ordered() {
        let attrs = mdg.node_attrs(node).cloned().unwrap_or_default();
        dg.add_node_with_attrs(node.to_owned(), attrs);
    }
    for edge in mdg.edges_ordered() {
        if !dg.has_edge(&edge.source, &edge.target) {
            let _ = dg.add_edge_with_attrs(edge.source, edge.target, edge.attrs);
        }
    }
    dg
}

/// Convert a MultiDiGraph to a simple DiGraph by choosing the minimum-weight
/// parallel edge for each directed edge, matching NetworkX shortest-path semantics.
fn multidigraph_to_weighted_simple_digraph(
    mdg: &fnx_classes::digraph::MultiDiGraph,
    weight_attr: &str,
) -> fnx_classes::digraph::DiGraph {
    let mut dg = fnx_classes::digraph::DiGraph::strict();
    let mut selected = HashMap::<(String, String), (f64, usize)>::new();

    for node in mdg.nodes_ordered() {
        let attrs = mdg.node_attrs(node).cloned().unwrap_or_default();
        dg.add_node_with_attrs(node.to_owned(), attrs);
    }

    for edge in mdg.edges_ordered() {
        let pair = (edge.source.clone(), edge.target.clone());
        let candidate_weight = projected_weight(&edge.attrs, weight_attr);
        match selected.get_mut(&pair) {
            Some((best_weight, best_key)) if candidate_weight < *best_weight => {
                *best_weight = candidate_weight;
                *best_key = edge.key;
            }
            None => {
                selected.insert(pair, (candidate_weight, edge.key));
            }
            _ => {}
        }
    }

    for edge in mdg.edges_ordered() {
        let pair = (edge.source.clone(), edge.target.clone());
        if selected
            .get(&pair)
            .is_some_and(|(_, selected_key)| *selected_key == edge.key)
        {
            let _ = dg.add_edge_with_attrs(edge.source, edge.target, edge.attrs);
        }
    }

    dg
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
    py: Python<'_>,
    inner: &fnx_classes::Graph,
    source: &str,
    target: &str,
    weight: Option<&str>,
    method: &str,
) -> PyResult<Option<Vec<String>>> {
    match weight {
        None => {
            let result = py
                .allow_threads(|| fnx_algorithms::shortest_path_unweighted(inner, source, target));
            Ok(result.path)
        }
        Some(w) => match method {
            "dijkstra" => {
                let result = py.allow_threads(|| {
                    fnx_algorithms::shortest_path_weighted(inner, source, target, w)
                });
                Ok(result.path)
            }
            "bellman-ford" => {
                let result = py.allow_threads(|| {
                    fnx_algorithms::bellman_ford_shortest_paths(inner, source, w)
                });
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

fn compute_single_shortest_path_directed(
    py: Python<'_>,
    inner: &fnx_classes::digraph::DiGraph,
    source: &str,
    target: &str,
    weight: Option<&str>,
    method: &str,
) -> PyResult<Option<Vec<String>>> {
    match weight {
        None => {
            let result = py.allow_threads(|| {
                fnx_algorithms::shortest_path_unweighted_directed(inner, source, target)
            });
            Ok(result.path)
        }
        Some(w) => match method {
            "dijkstra" => {
                let result = py.allow_threads(|| {
                    fnx_algorithms::shortest_path_weighted_directed(inner, source, target, w)
                });
                Ok(result.path)
            }
            "bellman-ford" => {
                let result = py.allow_threads(|| {
                    fnx_algorithms::bellman_ford_shortest_paths_directed(inner, source, w)
                });
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

fn compute_single_source_shortest_paths(
    py: Python<'_>,
    inner: &fnx_classes::Graph,
    source: &str,
    weight: Option<&str>,
    method: &str,
) -> PyResult<std::collections::HashMap<String, Vec<String>>> {
    match weight {
        None => {
            Ok(py
                .allow_threads(|| fnx_algorithms::single_source_shortest_path(inner, source, None)))
        }
        Some(w) => {
            match method {
                "dijkstra" => Ok(py.allow_threads(|| {
                    fnx_algorithms::single_source_dijkstra_path(inner, source, w)
                })),
                "bellman-ford" => {
                    let result = py.allow_threads(|| {
                        fnx_algorithms::single_source_bellman_ford_path(inner, source, w)
                    });
                    match result {
                        Some(paths) => Ok(paths),
                        None => Err(crate::NetworkXUnbounded::new_err(
                            "Negative cost cycle detected.",
                        )),
                    }
                }
                other => Err(NetworkXError::new_err(format!(
                    "Method {other} not supported for shortest_path."
                ))),
            }
        }
    }
}

fn compute_single_source_shortest_paths_directed(
    py: Python<'_>,
    inner: &fnx_classes::digraph::DiGraph,
    source: &str,
    weight: Option<&str>,
    method: &str,
) -> PyResult<std::collections::HashMap<String, Vec<String>>> {
    match weight {
        None => Ok(py.allow_threads(|| {
            fnx_algorithms::single_source_shortest_path_directed(inner, source, None)
        })),
        Some(w) => match method {
            "dijkstra" => Ok(py.allow_threads(|| {
                fnx_algorithms::single_source_dijkstra_path_directed(inner, source, w)
            })),
            "bellman-ford" => {
                let result = py.allow_threads(|| {
                    fnx_algorithms::single_source_bellman_ford_path_directed(inner, source, w)
                });
                match result {
                    Some(paths) => Ok(paths),
                    None => Err(crate::NetworkXUnbounded::new_err(
                        "Negative cost cycle detected.",
                    )),
                }
            }
            other => Err(NetworkXError::new_err(format!(
                "Method {other} not supported for shortest_path."
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

fn tuple_object(py: Python<'_>, elements: &[PyObject]) -> PyResult<PyObject> {
    Ok(PyTuple::new(py, elements)?.into_any().unbind())
}

fn flow_dict_object(
    py: Python<'_>,
    gr: &GraphRef<'_>,
    flows: &[fnx_algorithms::FlowEdgeValue],
) -> PyResult<PyObject> {
    let outer = PyDict::new(py);
    let mut adjacency_by_source = HashMap::<String, Py<PyDict>>::new();

    match gr {
        GraphRef::Undirected(pg) => {
            for node in pg.inner.nodes_ordered() {
                let adjacency = PyDict::new(py).unbind();
                if let Some(neighbors) = pg.inner.neighbors_iter(node) {
                    for neighbor in neighbors {
                        adjacency
                            .bind(py)
                            .set_item(pg.py_node_key(py, neighbor), 0.0)?;
                    }
                }
                outer.set_item(pg.py_node_key(py, node), adjacency.bind(py))?;
                adjacency_by_source.insert(node.to_owned(), adjacency);
            }
        }
        GraphRef::Directed { dg, .. } => {
            for node in dg.inner.nodes_ordered() {
                let adjacency = PyDict::new(py).unbind();
                if let Some(neighbors) = dg.inner.successors_iter(node) {
                    for neighbor in neighbors {
                        adjacency
                            .bind(py)
                            .set_item(dg.py_node_key(py, neighbor), 0.0)?;
                    }
                }
                outer.set_item(dg.py_node_key(py, node), adjacency.bind(py))?;
                adjacency_by_source.insert(node.to_owned(), adjacency);
            }
        }
        _ => {
            if gr.is_directed() {
                for node in gr.digraph().unwrap().nodes_ordered() {
                    let adjacency = PyDict::new(py).unbind();
                    if let Some(neighbors) = gr.digraph().unwrap().successors_iter(node) {
                        for neighbor in neighbors {
                            adjacency
                                .bind(py)
                                .set_item(gr.py_node_key(py, neighbor), 0.0)?;
                        }
                    }
                    outer.set_item(gr.py_node_key(py, node), adjacency.bind(py))?;
                    adjacency_by_source.insert(node.to_owned(), adjacency);
                }
            } else {
                for node in gr.undirected().nodes_ordered() {
                    let adjacency = PyDict::new(py).unbind();
                    if let Some(neighbors) = gr.undirected().neighbors_iter(node) {
                        for neighbor in neighbors {
                            adjacency
                                .bind(py)
                                .set_item(gr.py_node_key(py, neighbor), 0.0)?;
                        }
                    }
                    outer.set_item(gr.py_node_key(py, node), adjacency.bind(py))?;
                    adjacency_by_source.insert(node.to_owned(), adjacency);
                }
            }
        }
    }

    for flow in flows {
        if let Some(adjacency) = adjacency_by_source.get(&flow.source) {
            adjacency
                .bind(py)
                .set_item(gr.py_node_key(py, &flow.target), flow.flow)?;
        }
    }

    Ok(outer.into_any().unbind())
}

fn validate_spanning_algorithm(algorithm: &str) -> PyResult<()> {
    if algorithm != "kruskal" {
        return Err(PyValueError::new_err(format!(
            "Only 'kruskal' is currently supported for spanning edge generation; got '{algorithm}'."
        )));
    }
    Ok(())
}

fn spanning_input_graph(
    py: Python<'_>,
    gr: &GraphRef<'_>,
    weight: &str,
    ignore_nan: bool,
) -> PyResult<fnx_classes::Graph> {
    require_undirected(gr, "spanning_edges")?;

    let inner = gr.undirected();
    let mut sanitized = fnx_classes::Graph::strict();

    for node in inner.nodes_ordered() {
        sanitized.add_node(node.to_owned());
    }

    for edge in inner.edges_ordered() {
        let has_nan_weight = edge
            .attrs
            .get(weight)
            .and_then(|weight_value| weight_value.as_f64())
            .is_some_and(f64::is_nan);
        if has_nan_weight {
            if ignore_nan {
                continue;
            }

            let py_u = gr.py_node_key(py, &edge.left);
            let py_v = gr.py_node_key(py, &edge.right);
            let edge_attrs = match gr.edge_attrs_for_undirected(&edge.left, &edge.right) {
                Some(attrs) => attrs.bind(py).copy()?,
                None => PyDict::new(py),
            };

            return Err(PyValueError::new_err(format!(
                "NaN found as an edge weight. Edge ({}, {}, {})",
                py_u.bind(py).repr()?,
                py_v.bind(py).repr()?,
                edge_attrs.repr()?,
            )));
        }

        let attrs = edge
            .attrs
            .get(weight)
            .map_or_else(AttrMap::new, |weight_value| {
                let mut attrs = AttrMap::new();
                attrs.insert(weight.to_owned(), weight_value.clone());
                attrs
            });

        sanitized
            .add_edge_with_attrs(edge.left, edge.right, attrs)
            .map_err(|err| PyValueError::new_err(err.to_string()))?;
    }

    Ok(sanitized)
}

fn mst_edges_to_python(
    py: Python<'_>,
    gr: &GraphRef<'_>,
    edges: &[fnx_algorithms::MstEdge],
    data: bool,
) -> PyResult<Vec<PyObject>> {
    edges
        .iter()
        .map(|edge| {
            let u = gr.py_node_key(py, &edge.left);
            let v = gr.py_node_key(py, &edge.right);
            if data {
                let attrs = match gr.edge_attrs_for_undirected(&edge.left, &edge.right) {
                    Some(dict) => dict.bind(py).copy()?.into_any().unbind(),
                    None => PyDict::new(py).into_any().unbind(),
                };
                tuple_object(py, &[u, v, attrs])
            } else {
                tuple_object(py, &[u, v])
            }
        })
        .collect()
}

fn undirected_spanning_edges_to_pygraph(
    py: Python<'_>,
    pg: &PyGraph,
    edges: &[(String, String)],
) -> PyResult<PyGraph> {
    let mut tree = PyGraph::new_empty(py)?;
    tree.graph_attrs = pg.graph_attrs.bind(py).copy()?.unbind();

    for node in pg.inner.nodes_ordered() {
        let py_key = pg.py_node_key(py, node);
        tree.node_key_map.insert(node.to_owned(), py_key);
        let node_attrs = match pg.node_py_attrs.get(node) {
            Some(attrs) => attrs.bind(py).copy()?.unbind(),
            None => PyDict::new(py).unbind(),
        };
        tree.node_py_attrs.insert(node.to_owned(), node_attrs);
        tree.inner.add_node(node);
    }

    for (left, right) in edges {
        let _ = tree.inner.add_edge(left, right);
        let edge_key = PyGraph::edge_key(left, right);
        let edge_attrs = match pg.edge_py_attrs.get(&edge_key) {
            Some(attrs) => attrs.bind(py).copy()?.unbind(),
            None => PyDict::new(py).unbind(),
        };
        tree.edge_py_attrs.insert(edge_key, edge_attrs);
    }

    Ok(tree)
}

fn random_source(py: Python<'_>, seed: Option<u64>) -> PyResult<Bound<'_, PyAny>> {
    let random_module = py.import("random")?;
    if let Some(seed) = seed {
        random_module.getattr("Random")?.call1((seed,))
    } else {
        Ok(random_module.into_any())
    }
}

fn shuffled_spanning_edges_with_random(
    py: Python<'_>,
    inner: &fnx_classes::Graph,
    random: &Bound<'_, PyAny>,
) -> PyResult<SpanningEdgeSamples> {
    let edge_items = inner
        .edges_ordered()
        .into_iter()
        .map(|edge| (edge.left, edge.right))
        .collect::<Vec<_>>();
    let edge_list = PyList::new(py, &edge_items)?;
    random.call_method1("shuffle", (&edge_list,))?;
    let shuffled_edges = edge_list.extract::<Vec<(String, String)>>()?;
    let random_values = (0..shuffled_edges.len())
        .map(|_| random.call_method1("uniform", (0.0, 1.0))?.extract::<f64>())
        .collect::<PyResult<Vec<_>>>()?;
    Ok((shuffled_edges, random_values))
}

fn ensure_random_spanning_weight_key(py: Python<'_>, pg: &PyGraph, weight: &str) -> PyResult<()> {
    for attrs in pg.edge_py_attrs.values() {
        if attrs.bind(py).get_item(weight)?.is_none() {
            return Err(pyo3::exceptions::PyKeyError::new_err(weight.to_owned()));
        }
    }
    Ok(())
}

fn directed_branching_to_pydigraph(
    py: Python<'_>,
    dg: &PyDiGraph,
    edges: &[fnx_algorithms::BranchingEdge],
    attr: &str,
    preserve_attrs: bool,
) -> PyResult<PyDiGraph> {
    let mut tree = PyDiGraph::new_empty(py)?;
    for node in dg.inner.nodes_ordered() {
        let py_key = dg.py_node_key(py, node);
        tree.node_key_map.insert(node.to_owned(), py_key);
        tree.node_py_attrs
            .insert(node.to_owned(), PyDict::new(py).unbind());
        tree.inner.add_node(node);
    }
    for edge in edges {
        let _ = tree.inner.add_edge(&edge.left, &edge.right);
        let attrs = if preserve_attrs {
            match dg
                .edge_py_attrs
                .get(&(edge.left.clone(), edge.right.clone()))
            {
                Some(dict) => dict.bind(py).copy()?,
                None => PyDict::new(py),
            }
        } else {
            PyDict::new(py)
        };
        attrs.set_item(attr, edge.weight)?;
        tree.edge_py_attrs
            .insert((edge.left.clone(), edge.right.clone()), attrs.unbind());
    }
    Ok(tree)
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
    if let Some(weight_attr) = weight {
        if let Some(weighted_projection) = gr.weighted_digraph_projection(weight_attr) {
            let inner = weighted_projection.as_ref();
            log::info!(target: "franken_networkx", "shortest_path: directed nodes={} edges={}", inner.node_count(), inner.edge_count());
            match (source, target) {
                (Some(src), Some(tgt)) => {
                    let s = node_key_to_string(py, src)?;
                    let t = node_key_to_string(py, tgt)?;
                    validate_node(&gr, &s, src)?;
                    validate_node(&gr, &t, tgt)?;

                    let path = compute_single_shortest_path_directed(
                        py,
                        inner,
                        &s,
                        &t,
                        Some(weight_attr),
                        method,
                    )?;
                    match path {
                        Some(p) => {
                            let py_path: Vec<PyObject> =
                                p.iter().map(|n| gr.py_node_key(py, n)).collect();
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
                    let paths = compute_single_source_shortest_paths_directed(
                        py,
                        inner,
                        &s,
                        Some(weight_attr),
                        method,
                    )?;
                    let result = PyDict::new(py);
                    for (node, p) in paths {
                        let py_path: Vec<PyObject> =
                            p.iter().map(|n| gr.py_node_key(py, n)).collect();
                        result.set_item(gr.py_node_key(py, &node), py_path)?;
                    }
                    Ok(result.into_any().unbind())
                }
                (None, Some(tgt)) => {
                    let t = node_key_to_string(py, tgt)?;
                    validate_node(&gr, &t, tgt)?;
                    let result = PyDict::new(py);
                    for node in inner.nodes_ordered() {
                        if let Some(p) = compute_single_shortest_path_directed(
                            py,
                            inner,
                            node,
                            &t,
                            Some(weight_attr),
                            method,
                        )? {
                            let py_path: Vec<PyObject> =
                                p.iter().map(|n| gr.py_node_key(py, n)).collect();
                            result.set_item(gr.py_node_key(py, node), py_path)?;
                        }
                    }
                    Ok(result.into_any().unbind())
                }
                (None, None) => {
                    let result = PyDict::new(py);
                    for src_node in inner.nodes_ordered() {
                        let inner_dict = PyDict::new(py);
                        let paths = compute_single_source_shortest_paths_directed(
                            py,
                            inner,
                            src_node,
                            Some(weight_attr),
                            method,
                        )?;
                        for (tgt_node, p) in paths {
                            let py_path: Vec<PyObject> =
                                p.iter().map(|n| gr.py_node_key(py, n)).collect();
                            inner_dict.set_item(gr.py_node_key(py, &tgt_node), py_path)?;
                        }
                        result.set_item(gr.py_node_key(py, src_node), inner_dict)?;
                    }
                    Ok(result.into_any().unbind())
                }
            }
        } else {
            let weighted_projection = gr.weighted_undirected_projection(weight_attr);
            let inner = weighted_projection.as_ref();
            log::info!(target: "franken_networkx", "shortest_path: nodes={} edges={}", inner.node_count(), inner.edge_count());
            match (source, target) {
                (Some(src), Some(tgt)) => {
                    let s = node_key_to_string(py, src)?;
                    let t = node_key_to_string(py, tgt)?;
                    validate_node(&gr, &s, src)?;
                    validate_node(&gr, &t, tgt)?;

                    let path =
                        compute_single_shortest_path(py, inner, &s, &t, Some(weight_attr), method)?;
                    match path {
                        Some(p) => {
                            let py_path: Vec<PyObject> =
                                p.iter().map(|n| gr.py_node_key(py, n)).collect();
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
                    let paths = compute_single_source_shortest_paths(
                        py,
                        inner,
                        &s,
                        Some(weight_attr),
                        method,
                    )?;
                    let result = PyDict::new(py);
                    for (node, p) in paths {
                        let py_path: Vec<PyObject> =
                            p.iter().map(|n| gr.py_node_key(py, n)).collect();
                        result.set_item(gr.py_node_key(py, &node), py_path)?;
                    }
                    Ok(result.into_any().unbind())
                }
                (None, Some(tgt)) => {
                    let t = node_key_to_string(py, tgt)?;
                    validate_node(&gr, &t, tgt)?;
                    let paths = compute_single_source_shortest_paths(
                        py,
                        inner,
                        &t,
                        Some(weight_attr),
                        method,
                    )?;
                    let result = PyDict::new(py);
                    for (node, mut p) in paths {
                        p.reverse();
                        let py_path: Vec<PyObject> =
                            p.iter().map(|n| gr.py_node_key(py, n)).collect();
                        result.set_item(gr.py_node_key(py, &node), py_path)?;
                    }
                    Ok(result.into_any().unbind())
                }
                (None, None) => {
                    let result = PyDict::new(py);
                    for src_node in inner.nodes_ordered() {
                        let inner_dict = PyDict::new(py);
                        let paths = compute_single_source_shortest_paths(
                            py,
                            inner,
                            src_node,
                            Some(weight_attr),
                            method,
                        )?;
                        for (tgt_node, p) in paths {
                            let py_path: Vec<PyObject> =
                                p.iter().map(|n| gr.py_node_key(py, n)).collect();
                            inner_dict.set_item(gr.py_node_key(py, &tgt_node), py_path)?;
                        }
                        result.set_item(gr.py_node_key(py, src_node), inner_dict)?;
                    }
                    Ok(result.into_any().unbind())
                }
            }
        }
    } else if let Some(inner) = gr.digraph() {
        log::info!(target: "franken_networkx", "shortest_path: directed nodes={} edges={}", inner.node_count(), inner.edge_count());
        match (source, target) {
            (Some(src), Some(tgt)) => {
                let s = node_key_to_string(py, src)?;
                let t = node_key_to_string(py, tgt)?;
                validate_node(&gr, &s, src)?;
                validate_node(&gr, &t, tgt)?;

                let path = compute_single_shortest_path_directed(py, inner, &s, &t, None, method)?;
                match path {
                    Some(p) => {
                        let py_path: Vec<PyObject> =
                            p.iter().map(|n| gr.py_node_key(py, n)).collect();
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
                let paths =
                    compute_single_source_shortest_paths_directed(py, inner, &s, None, method)?;
                let result = PyDict::new(py);
                for (node, p) in paths {
                    let py_path: Vec<PyObject> = p.iter().map(|n| gr.py_node_key(py, n)).collect();
                    result.set_item(gr.py_node_key(py, &node), py_path)?;
                }
                Ok(result.into_any().unbind())
            }
            (None, Some(tgt)) => {
                let t = node_key_to_string(py, tgt)?;
                validate_node(&gr, &t, tgt)?;
                let result = PyDict::new(py);
                for node in inner.nodes_ordered() {
                    if let Some(p) =
                        compute_single_shortest_path_directed(py, inner, node, &t, None, method)?
                    {
                        let py_path: Vec<PyObject> =
                            p.iter().map(|n| gr.py_node_key(py, n)).collect();
                        result.set_item(gr.py_node_key(py, node), py_path)?;
                    }
                }
                Ok(result.into_any().unbind())
            }
            (None, None) => {
                let result = PyDict::new(py);
                for src_node in inner.nodes_ordered() {
                    let inner_dict = PyDict::new(py);
                    let paths = compute_single_source_shortest_paths_directed(
                        py, inner, src_node, None, method,
                    )?;
                    for (tgt_node, p) in paths {
                        let py_path: Vec<PyObject> =
                            p.iter().map(|n| gr.py_node_key(py, n)).collect();
                        inner_dict.set_item(gr.py_node_key(py, &tgt_node), py_path)?;
                    }
                    result.set_item(gr.py_node_key(py, src_node), inner_dict)?;
                }
                Ok(result.into_any().unbind())
            }
        }
    } else {
        if let Some(inner) = gr.digraph() {
            log::info!(target: "franken_networkx", "shortest_path: directed nodes={} edges={}", inner.node_count(), inner.edge_count());
            match (source, target) {
                (Some(src), Some(tgt)) => {
                    let s = node_key_to_string(py, src)?;
                    let t = node_key_to_string(py, tgt)?;
                    validate_node(&gr, &s, src)?;
                    validate_node(&gr, &t, tgt)?;

                    let path = compute_single_shortest_path_directed(py, inner, &s, &t, None, method)?;
                    match path {
                        Some(p) => {
                            let py_path: Vec<PyObject> =
                                p.iter().map(|n| gr.py_node_key(py, n)).collect();
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
                    let paths = compute_single_source_shortest_paths_directed(py, inner, &s, None, method)?;
                    let result = PyDict::new(py);
                    for (node, p) in paths {
                        let py_path: Vec<PyObject> = p.iter().map(|n| gr.py_node_key(py, n)).collect();
                        result.set_item(gr.py_node_key(py, &node), py_path)?;
                    }
                    Ok(result.into_any().unbind())
                }
                (None, Some(tgt)) => {
                    let t = node_key_to_string(py, tgt)?;
                    validate_node(&gr, &t, tgt)?;
                    let result = PyDict::new(py);
                    for node in inner.nodes_ordered() {
                        if let Some(p) = compute_single_shortest_path_directed(
                            py,
                            inner,
                            node,
                            &t,
                            None,
                            method,
                        )? {
                            let py_path: Vec<PyObject> =
                                p.iter().map(|n| gr.py_node_key(py, n)).collect();
                            result.set_item(gr.py_node_key(py, node), py_path)?;
                        }
                    }
                    Ok(result.into_any().unbind())
                }
                (None, None) => {
                    let result = PyDict::new(py);
                    for src_node in inner.nodes_ordered() {
                        let inner_dict = PyDict::new(py);
                        let paths =
                            compute_single_source_shortest_paths_directed(py, inner, src_node, None, method)?;
                        for (tgt_node, p) in paths {
                            let py_path: Vec<PyObject> =
                                p.iter().map(|n| gr.py_node_key(py, n)).collect();
                            inner_dict.set_item(gr.py_node_key(py, &tgt_node), py_path)?;
                        }
                        result.set_item(gr.py_node_key(py, src_node), inner_dict)?;
                    }
                    Ok(result.into_any().unbind())
                }
            }
        } else {
            let inner = gr.undirected();
            log::info!(target: "franken_networkx", "shortest_path: nodes={} edges={}", inner.node_count(), inner.edge_count());
            match (source, target) {
                (Some(src), Some(tgt)) => {
                    let s = node_key_to_string(py, src)?;
                    let t = node_key_to_string(py, tgt)?;
                    validate_node(&gr, &s, src)?;
                    validate_node(&gr, &t, tgt)?;

                    let path = compute_single_shortest_path(py, inner, &s, &t, None, method)?;
                    match path {
                        Some(p) => {
                            let py_path: Vec<PyObject> =
                                p.iter().map(|n| gr.py_node_key(py, n)).collect();
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
                    let paths = compute_single_source_shortest_paths(py, inner, &s, None, method)?;
                    let result = PyDict::new(py);
                    for (node, p) in paths {
                        let py_path: Vec<PyObject> = p.iter().map(|n| gr.py_node_key(py, n)).collect();
                        result.set_item(gr.py_node_key(py, &node), py_path)?;
                    }
                    Ok(result.into_any().unbind())
                }
                (None, Some(tgt)) => {
                    let t = node_key_to_string(py, tgt)?;
                    validate_node(&gr, &t, tgt)?;
                    let paths = compute_single_source_shortest_paths(py, inner, &t, None, method)?;
                    let result = PyDict::new(py);
                    for (node, mut p) in paths {
                        p.reverse();
                        let py_path: Vec<PyObject> = p.iter().map(|n| gr.py_node_key(py, n)).collect();
                        result.set_item(gr.py_node_key(py, &node), py_path)?;
                    }
                    Ok(result.into_any().unbind())
                }
                (None, None) => {
                    let result = PyDict::new(py);
                    for src_node in inner.nodes_ordered() {
                        let inner_dict = PyDict::new(py);
                        let paths =
                            compute_single_source_shortest_paths(py, inner, src_node, None, method)?;
                        for (tgt_node, p) in paths {
                            let py_path: Vec<PyObject> =
                                p.iter().map(|n| gr.py_node_key(py, n)).collect();
                            inner_dict.set_item(gr.py_node_key(py, &tgt_node), py_path)?;
                        }
                        result.set_item(gr.py_node_key(py, src_node), inner_dict)?;
                    }
                    Ok(result.into_any().unbind())
                }
            }
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
    if let Some(inner) = gr.digraph() {
        if let Some(w) = weight {
            let weighted_projection = gr.weighted_digraph_projection(w).expect("directed graph");
            match fnx_algorithms::dijkstra_path_length_directed(
                weighted_projection.as_ref(),
                &s,
                &t,
                w,
            ) {
                Some(len) => Ok(len.into_pyobject(py)?.into_any().unbind()),
                None => Err(NetworkXNoPath::new_err(format!(
                    "No path between {} and {}.",
                    s, t
                ))),
            }
        } else {
            match fnx_algorithms::shortest_path_unweighted_directed(inner, &s, &t).path {
                Some(path) => Ok((path.len().saturating_sub(1))
                    .into_pyobject(py)?
                    .into_any()
                    .unbind()),
                None => Err(NetworkXNoPath::new_err(format!(
                    "No path between {} and {}.",
                    s, t
                ))),
            }
        }
    } else {
        let inner = gr.undirected();
        if let Some(_w) = weight {
            let weighted_projection = gr.weighted_undirected_projection(_w);
            let inner = weighted_projection.as_ref();
            let result = fnx_algorithms::shortest_path_weighted(inner, &s, &t, _w);
            match result.path {
                Some(path) => {
                    let mut total: f64 = 0.0;
                    for i in 0..path.len() - 1 {
                        let attrs = inner.edge_attrs(&path[i], &path[i + 1]);
                        let w = attrs
                            .and_then(|a| a.get(_w))
                            .and_then(|v| v.as_f64())
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
    if let Some(inner) = gr.digraph() {
        let result = py.allow_threads(|| fnx_algorithms::has_path_directed(inner, &s, &t));
        Ok(result.has_path)
    } else {
        let inner = gr.undirected();
        let result = py.allow_threads(|| fnx_algorithms::has_path(inner, &s, &t));
        Ok(result.has_path)
    }
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
    if inner.node_count() == 0 {
        return Err(crate::NetworkXPointlessConcept::new_err(
            "Connectivity is undefined for the null graph.",
        ));
    }
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

    let result = if let Some(weighted_projection) = gr.weighted_digraph_projection(weight) {
        fnx_algorithms::shortest_path_weighted_directed(
            weighted_projection.as_ref(),
            &s,
            &t,
            weight,
        )
    } else {
        let weighted_projection = gr.weighted_undirected_projection(weight);
        fnx_algorithms::shortest_path_weighted(weighted_projection.as_ref(), &s, &t, weight)
    };
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

    let result = if let Some(weighted_projection) = gr.weighted_digraph_projection(weight) {
        fnx_algorithms::bellman_ford_shortest_paths_directed(
            weighted_projection.as_ref(),
            &s,
            weight,
        )
    } else {
        let weighted_projection = gr.weighted_undirected_projection(weight);
        fnx_algorithms::bellman_ford_shortest_paths(weighted_projection.as_ref(), &s, weight)
    };
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

    let result = if let Some(weighted_projection) = gr.weighted_digraph_projection(weight) {
        fnx_algorithms::multi_source_dijkstra_directed(
            weighted_projection.as_ref(),
            &source_refs,
            weight,
        )
    } else {
        let weighted_projection = gr.weighted_undirected_projection(weight);
        fnx_algorithms::multi_source_dijkstra(weighted_projection.as_ref(), &source_refs, weight)
    };

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
    if inner.node_count() == 0 {
        return Err(crate::NetworkXPointlessConcept::new_err(
            "Connectivity is undefined for the null graph.",
        ));
    }
    log::info!(target: "franken_networkx", "is_connected: nodes={} edges={}", inner.node_count(), inner.edge_count());
    Ok(py.allow_threads(|| fnx_algorithms::is_connected(inner).is_connected))
}

/// Return the density of the graph.
///
/// For undirected graphs: ``2 * m / (n * (n - 1))``.
/// For directed graphs: ``m / (n * (n - 1))``.
#[pyfunction]
pub fn density(_py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<f64> {
    let gr = extract_graph(g)?;
    let (n, m, directed) = match &gr {
        GraphRef::Undirected(pg) => (pg.inner.nodes_ordered().len(), pg.inner.edge_count(), false),
        GraphRef::Directed { dg, .. } => {
            (dg.inner.nodes_ordered().len(), dg.inner.edge_count(), true)
        }
        GraphRef::MultiUndirected { simple, .. } => {
            (simple.nodes_ordered().len(), simple.edge_count(), false)
        }
        GraphRef::MultiDirected { simple_dg, .. } => (
            simple_dg.nodes_ordered().len(),
            simple_dg.edge_count(),
            true,
        ),
    };
    if n < 2 {
        return Ok(0.0);
    }
    let denom = (n * (n - 1)) as f64;
    if directed {
        Ok(m as f64 / denom)
    } else {
        Ok(2.0 * m as f64 / denom)
    }
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
    if gr.is_directed() {
        let dg = gr.digraph().expect("is_directed checked above");
        Ok(py.allow_threads(|| fnx_algorithms::node_connectivity_directed_global(dg).value))
    } else {
        let inner = gr.undirected();
        Ok(py.allow_threads(|| fnx_algorithms::global_node_connectivity(inner).value))
    }
}

/// Return a minimum node cut of the graph.
#[pyfunction]
pub fn minimum_node_cut(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<Vec<PyObject>> {
    let gr = extract_graph(g)?;
    let result = if gr.is_directed() {
        let dg = gr.digraph().expect("is_directed checked above");
        if !fnx_algorithms::is_weakly_connected(dg) {
            return Err(NetworkXError::new_err("Input graph is not connected"));
        }
        py.allow_threads(|| fnx_algorithms::global_minimum_node_cut_directed(dg))
    } else {
        let inner = gr.undirected();
        if !fnx_algorithms::is_connected(inner).is_connected {
            return Err(NetworkXError::new_err("Input graph is not connected"));
        }
        py.allow_threads(|| fnx_algorithms::global_minimum_node_cut(inner))
    };
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
    let cap = capacity.to_owned();
    if gr.is_directed() {
        let dg = gr.digraph().expect("is_directed checked above");
        Ok(py.allow_threads(move || {
            fnx_algorithms::global_edge_connectivity_edmonds_karp_directed(dg, &cap).value
        }))
    } else {
        let inner = gr.undirected();
        Ok(py.allow_threads(move || {
            fnx_algorithms::global_edge_connectivity_edmonds_karp(inner, &cap).value
        }))
    }
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
    let result = match &gr {
        GraphRef::Undirected(pg) => {
            let inner = &pg.inner;
            py.allow_threads(|| fnx_algorithms::degree_centrality(inner))
        }
        GraphRef::Directed { dg, .. } => {
            let inner = &dg.inner;
            py.allow_threads(|| fnx_algorithms::degree_centrality_directed(inner))
        }
        _ => {
            if gr.is_directed() {
                let inner = gr.digraph().unwrap();
                py.allow_threads(|| fnx_algorithms::degree_centrality_directed(inner))
            } else {
                let inner = gr.undirected();
                py.allow_threads(|| fnx_algorithms::degree_centrality(inner))
            }
        }
    };
    centrality_to_dict(py, &gr, &result.scores)
}

/// Return the closeness centrality for all nodes.
#[pyfunction]
pub fn closeness_centrality(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<Py<PyDict>> {
    let gr = extract_graph(g)?;
    let result = match &gr {
        GraphRef::Undirected(pg) => {
            let inner = &pg.inner;
            py.allow_threads(|| fnx_algorithms::closeness_centrality(inner))
        }
        GraphRef::Directed { dg, .. } => {
            let inner = &dg.inner;
            py.allow_threads(|| fnx_algorithms::closeness_centrality_directed(inner))
        }
        _ => {
            if gr.is_directed() {
                let inner = gr.digraph().unwrap();
                py.allow_threads(|| fnx_algorithms::closeness_centrality_directed(inner))
            } else {
                let inner = gr.undirected();
                py.allow_threads(|| fnx_algorithms::closeness_centrality(inner))
            }
        }
    };
    centrality_to_dict(py, &gr, &result.scores)
}

/// Return the harmonic centrality for all nodes.
#[pyfunction]
pub fn harmonic_centrality(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<Py<PyDict>> {
    let gr = extract_graph(g)?;
    let result = match &gr {
        GraphRef::Undirected(pg) => {
            let inner = &pg.inner;
            py.allow_threads(|| fnx_algorithms::harmonic_centrality(inner))
        }
        GraphRef::Directed { dg, .. } => {
            let inner = &dg.inner;
            py.allow_threads(|| fnx_algorithms::harmonic_centrality_directed(inner))
        }
        _ => {
            if gr.is_directed() {
                let inner = gr.digraph().unwrap();
                py.allow_threads(|| fnx_algorithms::harmonic_centrality_directed(inner))
            } else {
                let inner = gr.undirected();
                py.allow_threads(|| fnx_algorithms::harmonic_centrality(inner))
            }
        }
    };
    centrality_to_dict(py, &gr, &result.scores)
}

/// Return the Katz centrality for all nodes.
#[pyfunction]
pub fn katz_centrality(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<Py<PyDict>> {
    let gr = extract_graph(g)?;
    let result = match &gr {
        GraphRef::Undirected(pg) => {
            let inner = &pg.inner;
            py.allow_threads(|| fnx_algorithms::katz_centrality(inner))
        }
        GraphRef::Directed { dg, .. } => {
            let inner = &dg.inner;
            py.allow_threads(|| fnx_algorithms::katz_centrality_directed(inner))
        }
        _ => {
            if gr.is_directed() {
                let inner = gr.digraph().unwrap();
                py.allow_threads(|| fnx_algorithms::katz_centrality_directed(inner))
            } else {
                let inner = gr.undirected();
                py.allow_threads(|| fnx_algorithms::katz_centrality(inner))
            }
        }
    };
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
    log::info!(target: "franken_networkx", "betweenness_centrality: nodes={}", gr.undirected().node_count());
    let result = match &gr {
        GraphRef::Undirected(pg) => {
            let inner = &pg.inner;
            py.allow_threads(|| fnx_algorithms::betweenness_centrality(inner))
        }
        GraphRef::Directed { dg, .. } => {
            let inner = &dg.inner;
            py.allow_threads(|| fnx_algorithms::betweenness_centrality_directed(inner))
        }
        _ => {
            if gr.is_directed() {
                let inner = gr.digraph().unwrap();
                py.allow_threads(|| fnx_algorithms::betweenness_centrality_directed(inner))
            } else {
                let inner = gr.undirected();
                py.allow_threads(|| fnx_algorithms::betweenness_centrality(inner))
            }
        }
    };
    centrality_to_dict(py, &gr, &result.scores)
}

/// Return the edge betweenness centrality for all edges.
#[pyfunction]
pub fn edge_betweenness_centrality(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<Py<PyDict>> {
    let gr = extract_graph(g)?;
    let result = match &gr {
        GraphRef::Undirected(pg) => {
            let inner = &pg.inner;
            py.allow_threads(|| fnx_algorithms::edge_betweenness_centrality(inner))
        }
        GraphRef::Directed { dg, .. } => {
            let inner = &dg.inner;
            py.allow_threads(|| fnx_algorithms::edge_betweenness_centrality_directed(inner))
        }
        _ => {
            if gr.is_directed() {
                let inner = gr.digraph().unwrap();
                py.allow_threads(|| fnx_algorithms::edge_betweenness_centrality_directed(inner))
            } else {
                let inner = gr.undirected();
                py.allow_threads(|| fnx_algorithms::edge_betweenness_centrality(inner))
            }
        }
    };
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
    let result = match &gr {
        GraphRef::Undirected(pg) => {
            let inner = &pg.inner;
            py.allow_threads(|| fnx_algorithms::eigenvector_centrality(inner))
        }
        GraphRef::Directed { dg, .. } => {
            let inner = &dg.inner;
            py.allow_threads(|| fnx_algorithms::eigenvector_centrality_directed(inner))
        }
        _ => {
            if gr.is_directed() {
                let inner = gr.digraph().unwrap();
                py.allow_threads(|| fnx_algorithms::eigenvector_centrality_directed(inner))
            } else {
                let inner = gr.undirected();
                py.allow_threads(|| fnx_algorithms::eigenvector_centrality(inner))
            }
        }
    };
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
#[pyo3(signature = (g, alpha=0.85, max_iter=100, tol=1.0e-6, weight="weight"))]
pub fn pagerank(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    alpha: f64,
    max_iter: usize,
    tol: f64,
    weight: &str,
) -> PyResult<Py<PyDict>> {
    let _ = weight; // weight attr threading deferred to Rust internals
    let gr = extract_graph(g)?;
    log::info!(target: "franken_networkx", "pagerank: nodes={}", gr.undirected().node_count());
    let result = match &gr {
        GraphRef::Undirected(pg) => {
            let inner = &pg.inner;
            py.allow_threads(|| fnx_algorithms::pagerank_with_params(inner, alpha, max_iter, tol))
        }
        GraphRef::Directed { dg, .. } => {
            let inner = &dg.inner;
            py.allow_threads(|| fnx_algorithms::pagerank_with_params(inner, alpha, max_iter, tol))
        }
        _ => {
            if gr.is_directed() {
                let inner = gr.digraph().unwrap();
                py.allow_threads(|| fnx_algorithms::pagerank_with_params(inner, alpha, max_iter, tol))
            } else {
                let inner = gr.undirected();
                py.allow_threads(|| fnx_algorithms::pagerank_with_params(inner, alpha, max_iter, tol))
            }
        }
    };
    centrality_to_dict(py, &gr, &result.scores)
}

/// Return HITS hubs and authorities scores.
#[pyfunction]
pub fn hits(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<(Py<PyDict>, Py<PyDict>)> {
    let gr = extract_graph(g)?;
    let result = match &gr {
        GraphRef::Undirected(pg) => {
            let inner = &pg.inner;
            py.allow_threads(|| fnx_algorithms::hits_centrality(inner))
        }
        GraphRef::Directed { dg, .. } => {
            let inner = &dg.inner;
            py.allow_threads(|| fnx_algorithms::hits_centrality_directed(inner))
        }
        _ => {
            if gr.is_directed() {
                let inner = gr.digraph().unwrap();
                py.allow_threads(|| fnx_algorithms::hits_centrality_directed(inner))
            } else {
                let inner = gr.undirected();
                py.allow_threads(|| fnx_algorithms::hits_centrality(inner))
            }
        }
    };
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
    let result = match &gr {
        GraphRef::Undirected(pg) => {
            let inner = &pg.inner;
            py.allow_threads(|| fnx_algorithms::voterank(inner))
        }
        GraphRef::Directed { dg, .. } => {
            let inner = &dg.inner;
            py.allow_threads(|| fnx_algorithms::voterank_directed(inner))
        }
        _ => {
            if gr.is_directed() {
                let inner = gr.digraph().unwrap();
                py.allow_threads(|| fnx_algorithms::voterank_directed(inner))
            } else {
                let inner = gr.undirected();
                py.allow_threads(|| fnx_algorithms::voterank(inner))
            }
        }
    };
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
    let result = py.allow_threads(move || fnx_algorithms::max_weight_matching(inner, false, &w));
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

fn flow_terminals(
    py: Python<'_>,
    gr: &GraphRef<'_>,
    source: &Bound<'_, PyAny>,
    sink: &Bound<'_, PyAny>,
) -> PyResult<(String, String)> {
    let s = node_key_to_string(py, source)?;
    if !gr.has_node(&s) {
        return Err(NetworkXError::new_err(format!("node {s} not in graph")));
    }
    let t = node_key_to_string(py, sink)?;
    if !gr.has_node(&t) {
        return Err(NetworkXError::new_err(format!("node {t} not in graph")));
    }
    if s == t {
        return Err(NetworkXError::new_err("source and sink are the same node"));
    }
    Ok((s, t))
}

fn flow_py_error(err: fnx_algorithms::FlowError) -> PyErr {
    NetworkXError::new_err(err.to_string())
}

/// Return the maximum flow value and flow dictionary between source and sink.
#[pyfunction]
#[pyo3(signature = (g, source, sink, capacity="capacity"))]
pub fn maximum_flow(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    source: &Bound<'_, PyAny>,
    sink: &Bound<'_, PyAny>,
    capacity: &str,
) -> PyResult<(f64, PyObject)> {
    let gr = extract_graph(g)?;
    let (s, t) = flow_terminals(py, &gr, source, sink)?;
    let cap = capacity.to_owned();
    let result = match &gr {
        GraphRef::Undirected(pg) => {
            let inner = &pg.inner;
            py.allow_threads(move || fnx_algorithms::max_flow_edmonds_karp(inner, &s, &t, &cap))
        }
        GraphRef::Directed { dg, .. } => {
            let inner = &dg.inner;
            py.allow_threads(move || {
                fnx_algorithms::max_flow_edmonds_karp_directed(inner, &s, &t, &cap)
            })
        }
        _ => {
            if gr.is_directed() {
                let inner = gr.digraph().unwrap();
                py.allow_threads(move || {
                    fnx_algorithms::max_flow_edmonds_karp_directed(inner, &s, &t, &cap)
                })
            } else {
                let inner = gr.undirected();
                py.allow_threads(move || fnx_algorithms::max_flow_edmonds_karp(inner, &s, &t, &cap))
            }
        }
    };
    let result = result.map_err(flow_py_error)?;
    let flow_dict = flow_dict_object(py, &gr, &result.flows)?;
    Ok((result.value, flow_dict))
}

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
    let (s, t) = flow_terminals(py, &gr, source, sink)?;
    let cap = capacity.to_owned();
    match &gr {
        GraphRef::Undirected(pg) => {
            let inner = &pg.inner;
            py.allow_threads(move || fnx_algorithms::max_flow_edmonds_karp(inner, &s, &t, &cap))
                .map(|result| result.value)
                .map_err(flow_py_error)
        }
        GraphRef::Directed { dg, .. } => {
            let inner = &dg.inner;
            py.allow_threads(move || {
                fnx_algorithms::max_flow_edmonds_karp_directed(inner, &s, &t, &cap)
            })
            .map(|result| result.value)
            .map_err(flow_py_error)
        }
        _ => {
            if gr.is_directed() {
                let inner = gr.digraph().unwrap();
                py.allow_threads(move || {
                    fnx_algorithms::max_flow_edmonds_karp_directed(inner, &s, &t, &cap)
                })
                .map(|result| result.value)
                .map_err(flow_py_error)
            } else {
                let inner = gr.undirected();
                py.allow_threads(move || fnx_algorithms::max_flow_edmonds_karp(inner, &s, &t, &cap))
                    .map(|result| result.value)
                    .map_err(flow_py_error)
            }
        }
    }
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
    let (s, t) = flow_terminals(py, &gr, source, sink)?;
    let cap = capacity.to_owned();
    match &gr {
        GraphRef::Undirected(pg) => {
            let inner = &pg.inner;
            py.allow_threads(move || fnx_algorithms::minimum_cut_edmonds_karp(inner, &s, &t, &cap))
                .map(|result| result.value)
                .map_err(flow_py_error)
        }
        GraphRef::Directed { dg, .. } => {
            let inner = &dg.inner;
            py.allow_threads(move || {
                fnx_algorithms::minimum_cut_edmonds_karp_directed(inner, &s, &t, &cap)
            })
            .map(|result| result.value)
            .map_err(flow_py_error)
        }
        _ => {
            if gr.is_directed() {
                let inner = gr.digraph().unwrap();
                py.allow_threads(move || {
                    fnx_algorithms::minimum_cut_edmonds_karp_directed(inner, &s, &t, &cap)
                })
                .map(|result| result.value)
                .map_err(flow_py_error)
            } else {
                let inner = gr.undirected();
                py.allow_threads(move || {
                    fnx_algorithms::minimum_cut_edmonds_karp(inner, &s, &t, &cap)
                })
                .map(|result| result.value)
                .map_err(flow_py_error)
            }
        }
    }
}

/// Return the minimum cut value and node partition between source and sink.
#[pyfunction]
#[pyo3(signature = (g, source, sink, capacity="capacity"))]
pub fn minimum_cut(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    source: &Bound<'_, PyAny>,
    sink: &Bound<'_, PyAny>,
    capacity: &str,
) -> PyResult<(f64, PyObject)> {
    let gr = extract_graph(g)?;
    let (s, t) = flow_terminals(py, &gr, source, sink)?;
    let cap = capacity.to_owned();
    let cut = match &gr {
        GraphRef::Undirected(pg) => {
            let inner = &pg.inner;
            py.allow_threads(move || fnx_algorithms::minimum_cut_edmonds_karp(inner, &s, &t, &cap))
        }
        GraphRef::Directed { dg, .. } => {
            let inner = &dg.inner;
            py.allow_threads(move || {
                fnx_algorithms::minimum_cut_edmonds_karp_directed(inner, &s, &t, &cap)
            })
        }
        _ => {
            if gr.is_directed() {
                let inner = gr.digraph().unwrap();
                py.allow_threads(move || {
                    fnx_algorithms::minimum_cut_edmonds_karp_directed(inner, &s, &t, &cap)
                })
            } else {
                let inner = gr.undirected();
                py.allow_threads(move || {
                    fnx_algorithms::minimum_cut_edmonds_karp(inner, &s, &t, &cap)
                })
            }
        }
    };

    let cut = cut.map_err(flow_py_error)?;
    let source_partition = pyo3::types::PySet::new(
        py,
        cut.source_partition
            .iter()
            .map(|node| gr.py_node_key(py, node))
            .collect::<Vec<_>>(),
    )?;
    let sink_partition = pyo3::types::PySet::new(
        py,
        cut.sink_partition
            .iter()
            .map(|node| gr.py_node_key(py, node))
            .collect::<Vec<_>>(),
    )?;
    let partition = tuple_object(
        py,
        &[
            source_partition.into_any().unbind(),
            sink_partition.into_any().unbind(),
        ],
    )?;

    Ok((cut.value, partition))
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
    if inner.node_count() == 0 {
        return Err(crate::NetworkXPointlessConcept::new_err("G has no nodes."));
    }
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
    if inner.node_count() == 0 {
        return Err(crate::NetworkXPointlessConcept::new_err("G has no nodes."));
    }
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
    if inner.node_count() == 0 {
        return Err(crate::NetworkXPointlessConcept::new_err("G has no nodes."));
    }
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
    if inner.node_count() == 0 {
        return Err(crate::NetworkXPointlessConcept::new_err("G has no nodes."));
    }
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
    if inner.node_count() == 0 {
        return Err(crate::NetworkXPointlessConcept::new_err("G has no nodes."));
    }
    Ok(py.allow_threads(|| fnx_algorithms::is_tree(inner).is_tree))
}

/// Return True if the graph is a forest.
#[pyfunction]
pub fn is_forest(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<bool> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    if inner.node_count() == 0 {
        return Err(crate::NetworkXPointlessConcept::new_err("G has no nodes."));
    }
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
///
/// Parameters
/// ----------
/// g : Graph or DiGraph
///     The input graph.
/// strategy : str, optional
///     Node ordering strategy. One of ``"largest_first"`` (default),
///     ``"smallest_last"``, ``"random_sequential"``, ``"DSATUR"``,
///     ``"saturation_largest_first"``, or ``"connected_sequential"``.
#[pyfunction]
#[pyo3(signature = (g, strategy="largest_first"))]
pub fn greedy_color(py: Python<'_>, g: &Bound<'_, PyAny>, strategy: &str) -> PyResult<Py<PyDict>> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    let s = strategy.to_owned();
    let result = py.allow_threads(move || fnx_algorithms::greedy_color_with_strategy(inner, &s));
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

/// Return the edges of a minimum spanning forest.
#[pyfunction]
#[pyo3(signature = (g, algorithm="kruskal", weight="weight", keys=true, data=true, ignore_nan=false))]
pub fn minimum_spanning_edges(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    algorithm: &str,
    weight: &str,
    keys: bool,
    data: bool,
    ignore_nan: bool,
) -> PyResult<Vec<PyObject>> {
    let _ = keys;
    validate_spanning_algorithm(algorithm)?;
    let gr = extract_graph(g)?;
    let input = spanning_input_graph(py, &gr, weight, ignore_nan)?;
    let w = weight.to_owned();
    let result = py.allow_threads(move || fnx_algorithms::minimum_spanning_tree(&input, &w));
    mst_edges_to_python(py, &gr, &result.edges, data)
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

/// Return the edges of a maximum spanning forest.
#[pyfunction]
#[pyo3(signature = (g, algorithm="kruskal", weight="weight", keys=true, data=true, ignore_nan=false))]
pub fn maximum_spanning_edges(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    algorithm: &str,
    weight: &str,
    keys: bool,
    data: bool,
    ignore_nan: bool,
) -> PyResult<Vec<PyObject>> {
    let _ = keys;
    validate_spanning_algorithm(algorithm)?;
    let gr = extract_graph(g)?;
    let input = spanning_input_graph(py, &gr, weight, ignore_nan)?;
    let w = weight.to_owned();
    let result = py.allow_threads(move || fnx_algorithms::maximum_spanning_tree(&input, &w));
    mst_edges_to_python(py, &gr, &result.edges, data)
}

/// Return the number of spanning trees or rooted spanning arborescences.
#[pyfunction]
#[pyo3(signature = (g, root=None, weight=None))]
pub fn number_of_spanning_trees(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    root: Option<&Bound<'_, PyAny>>,
    weight: Option<&str>,
) -> PyResult<f64> {
    let gr = extract_graph(g)?;
    match &gr {
        GraphRef::Undirected(pg) => {
            if pg.inner.node_count() == 0 {
                return Err(crate::NetworkXPointlessConcept::new_err(
                    "Graph G must contain at least one node.",
                ));
            }
            let inner = &pg.inner;
            Ok(py.allow_threads(|| fnx_algorithms::number_of_spanning_trees(inner, weight)))
        }
        GraphRef::Directed { dg, .. } => {
            if dg.inner.node_count() == 0 {
                return Err(crate::NetworkXPointlessConcept::new_err(
                    "Graph G must contain at least one node.",
                ));
            }
            let Some(root) = root else {
                return Err(NetworkXError::new_err(
                    "Input `root` must be provided when G is directed",
                ));
            };
            let canonical_root = node_key_to_string(py, root)?;
            if !dg.inner.has_node(&canonical_root) {
                return Err(NetworkXError::new_err(
                    "The node root is not in the graph G.",
                ));
            }
            let inner = &dg.inner;
            Ok(py.allow_threads(move || {
                fnx_algorithms::number_of_spanning_arborescences(inner, &canonical_root, weight)
            }))
        }
        _ => {
            if gr.is_directed() {
                if gr.digraph().unwrap().node_count() == 0 {
                    return Err(crate::NetworkXPointlessConcept::new_err(
                        "Graph G must contain at least one node.",
                    ));
                }
                let Some(root) = root else {
                    return Err(NetworkXError::new_err(
                        "Input `root` must be provided when G is directed",
                    ));
                };
                let canonical_root = node_key_to_string(py, root)?;
                if !gr.digraph().unwrap().has_node(&canonical_root) {
                    return Err(NetworkXError::new_err(
                        "The node root is not in the graph G.",
                    ));
                }
                let inner = gr.digraph().unwrap();
                Ok(py.allow_threads(move || {
                    fnx_algorithms::number_of_spanning_arborescences(inner, &canonical_root, weight)
                }))
            } else {
                if gr.undirected().node_count() == 0 {
                    return Err(crate::NetworkXPointlessConcept::new_err(
                        "Graph G must contain at least one node.",
                    ));
                }
                let inner = gr.undirected();
                Ok(py.allow_threads(|| fnx_algorithms::number_of_spanning_trees(inner, weight)))
            }
        }
    }
}

/// Find a spanning tree while respecting edge partition constraints.
#[pyfunction]
#[pyo3(signature = (g, minimum=true, weight="weight", partition="partition", ignore_nan=false))]
pub fn partition_spanning_tree(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    minimum: bool,
    weight: &str,
    partition: &str,
    ignore_nan: bool,
) -> PyResult<PyGraph> {
    let gr = extract_graph(g)?;
    require_undirected(&gr, "partition_spanning_tree")?;
    let GraphRef::Undirected(pg) = &gr else {
        unreachable!("require_undirected should reject directed graphs")
    };
    let weight_name = weight.to_owned();
    let partition_name = partition.to_owned();
    let inner = &pg.inner;
    let result = match py.allow_threads(move || {
        fnx_algorithms::partition_spanning_tree(
            inner,
            minimum,
            &weight_name,
            &partition_name,
            ignore_nan,
        )
    }) {
        Ok(result) => result,
        Err(fnx_algorithms::PartitionSpanningTreeError::NaNWeight { left, right }) => {
            let py_u = pg.py_node_key(py, &left);
            let py_v = pg.py_node_key(py, &right);
            let edge_attrs = match pg.edge_py_attrs.get(&PyGraph::edge_key(&left, &right)) {
                Some(attrs) => attrs.bind(py).copy()?,
                None => PyDict::new(py),
            };
            return Err(PyValueError::new_err(format!(
                "NaN found as an edge weight. Edge ({}, {}, {})",
                py_u.bind(py).repr()?,
                py_v.bind(py).repr()?,
                edge_attrs.repr()?,
            )));
        }
    };
    let edge_pairs = result
        .edges
        .iter()
        .map(|edge| (edge.left.clone(), edge.right.clone()))
        .collect::<Vec<_>>();
    undirected_spanning_edges_to_pygraph(py, pg, &edge_pairs)
}

/// Sample a random spanning tree.
#[pyfunction]
#[pyo3(signature = (g, weight=None, multiplicative=true, seed=None))]
pub fn random_spanning_tree(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    weight: Option<&str>,
    multiplicative: bool,
    seed: Option<u64>,
) -> PyResult<PyGraph> {
    let gr = extract_graph(g)?;
    require_undirected(&gr, "random_spanning_tree")?;
    let GraphRef::Undirected(pg) = &gr else {
        unreachable!("require_undirected should reject directed graphs")
    };
    if let Some(weight_attr) = weight {
        ensure_random_spanning_weight_key(py, pg, weight_attr)?;
    }

    let random = random_source(py, seed)?;
    let (shuffled_edges, random_values) =
        shuffled_spanning_edges_with_random(py, &pg.inner, &random)?;
    let inner = &pg.inner;
    let result = py
        .allow_threads(move || {
            fnx_algorithms::random_spanning_tree_from_samples(
                inner,
                weight,
                multiplicative,
                &shuffled_edges,
                &random_values,
            )
        })
        .map_err(|err| match err {
            fnx_algorithms::RandomSpanningTreeError::DivisionByZero => {
                PyZeroDivisionError::new_err("division by zero")
            }
            fnx_algorithms::RandomSpanningTreeError::MissingRandomSample
            | fnx_algorithms::RandomSpanningTreeError::IncompleteTree => {
                crate::NetworkXAlgorithmError::new_err(err.to_string())
            }
        })?;
    let edge_pairs = result
        .edges_ordered()
        .into_iter()
        .map(|edge| (edge.left, edge.right))
        .collect::<Vec<_>>();
    undirected_spanning_edges_to_pygraph(py, pg, &edge_pairs)
}

/// Return a maximum branching of a directed graph.
#[pyfunction]
#[pyo3(signature = (g, attr="weight", default=1.0, preserve_attrs=false, partition=None))]
pub fn maximum_branching(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    attr: &str,
    default: f64,
    preserve_attrs: bool,
    partition: Option<&str>,
) -> PyResult<PyDiGraph> {
    if partition.is_some() {
        return Err(crate::NetworkXNotImplemented::new_err(
            "edge partition constraints are not implemented for maximum_branching.",
        ));
    }
    let gr = extract_graph(g)?;
    if let GraphRef::Directed { dg, .. } = &gr {
        let inner = &dg.inner;
        let attr_name = attr.to_owned();
        let result =
            py.allow_threads(move || fnx_algorithms::maximum_branching(inner, &attr_name, default));
        directed_branching_to_pydigraph(py, dg, &result.edges, attr, preserve_attrs)
    } else {
        Err(crate::NetworkXNotImplemented::new_err(
            "maximum_branching is only implemented for directed graphs.",
        ))
    }
}

/// Return a minimum branching of a directed graph.
#[pyfunction]
#[pyo3(signature = (g, attr="weight", default=1.0, preserve_attrs=false, partition=None))]
pub fn minimum_branching(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    attr: &str,
    default: f64,
    preserve_attrs: bool,
    partition: Option<&str>,
) -> PyResult<PyDiGraph> {
    if partition.is_some() {
        return Err(crate::NetworkXNotImplemented::new_err(
            "edge partition constraints are not implemented for minimum_branching.",
        ));
    }
    let gr = extract_graph(g)?;
    if let GraphRef::Directed { dg, .. } = &gr {
        let inner = &dg.inner;
        let attr_name = attr.to_owned();
        let result =
            py.allow_threads(move || fnx_algorithms::minimum_branching(inner, &attr_name, default));
        directed_branching_to_pydigraph(py, dg, &result.edges, attr, preserve_attrs)
    } else {
        Err(crate::NetworkXNotImplemented::new_err(
            "minimum_branching is only implemented for directed graphs.",
        ))
    }
}

/// Return a maximum spanning arborescence of a directed graph.
#[pyfunction]
#[pyo3(signature = (g, attr="weight", default=1.0, preserve_attrs=false, partition=None))]
pub fn maximum_spanning_arborescence(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    attr: &str,
    default: f64,
    preserve_attrs: bool,
    partition: Option<&str>,
) -> PyResult<PyDiGraph> {
    if partition.is_some() {
        return Err(crate::NetworkXNotImplemented::new_err(
            "edge partition constraints are not implemented for maximum_spanning_arborescence.",
        ));
    }
    let gr = extract_graph(g)?;
    if let GraphRef::Directed { dg, .. } = &gr {
        if dg.inner.node_count() == 0 {
            return Err(crate::NetworkXPointlessConcept::new_err("G has no nodes."));
        }
        let inner = &dg.inner;
        let attr_name = attr.to_owned();
        let result = py.allow_threads(move || {
            fnx_algorithms::maximum_spanning_arborescence(inner, &attr_name, default)
        });
        let result = result
            .ok_or_else(|| NetworkXError::new_err("No maximum spanning arborescence in G."))?;
        directed_branching_to_pydigraph(py, dg, &result.edges, attr, preserve_attrs)
    } else {
        Err(crate::NetworkXNotImplemented::new_err(
            "maximum_spanning_arborescence is only implemented for directed graphs.",
        ))
    }
}

/// Return a minimum spanning arborescence of a directed graph.
#[pyfunction]
#[pyo3(signature = (g, attr="weight", default=1.0, preserve_attrs=false, partition=None))]
pub fn minimum_spanning_arborescence(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    attr: &str,
    default: f64,
    preserve_attrs: bool,
    partition: Option<&str>,
) -> PyResult<PyDiGraph> {
    if partition.is_some() {
        return Err(crate::NetworkXNotImplemented::new_err(
            "edge partition constraints are not implemented for minimum_spanning_arborescence.",
        ));
    }
    let gr = extract_graph(g)?;
    if let GraphRef::Directed { dg, .. } = &gr {
        if dg.inner.node_count() == 0 {
            return Err(crate::NetworkXPointlessConcept::new_err("G has no nodes."));
        }
        let inner = &dg.inner;
        let attr_name = attr.to_owned();
        let result = py.allow_threads(move || {
            fnx_algorithms::minimum_spanning_arborescence(inner, &attr_name, default)
        });
        let result = result
            .ok_or_else(|| NetworkXError::new_err("No minimum spanning arborescence in G."))?;
        directed_branching_to_pydigraph(py, dg, &result.edges, attr, preserve_attrs)
    } else {
        Err(crate::NetworkXNotImplemented::new_err(
            "minimum_spanning_arborescence is only implemented for directed graphs.",
        ))
    }
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

/// Return the efficiency of a pair of nodes in an undirected graph.
#[pyfunction]
pub fn efficiency(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    u: &Bound<'_, PyAny>,
    v: &Bound<'_, PyAny>,
) -> PyResult<f64> {
    let gr = extract_graph(g)?;
    require_undirected(&gr, "efficiency")?;
    let u_key = node_key_to_string(py, u)?;
    let v_key = node_key_to_string(py, v)?;
    validate_node(&gr, &u_key, u)?;
    validate_node(&gr, &v_key, v)?;
    if u_key == v_key {
        return Err(PyZeroDivisionError::new_err("division by zero"));
    }
    let inner = gr.undirected();
    Ok(py
        .allow_threads(|| fnx_algorithms::efficiency(inner, &u_key, &v_key))
        .unwrap_or(0.0))
}

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

/// Return the broadcast center of a tree.
#[pyfunction]
pub fn tree_broadcast_center(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<(usize, PyObject)> {
    let gr = extract_graph(g)?;
    require_undirected(&gr, "tree_broadcast_center")?;
    let inner = gr.undirected();
    if inner.node_count() == 0 {
        return Err(crate::NetworkXPointlessConcept::new_err("G has no nodes."));
    }
    if !py.allow_threads(|| fnx_algorithms::is_tree(inner).is_tree) {
        return Err(crate::NotATree::new_err("G is not a tree"));
    }

    let (time, center) = py
        .allow_threads(|| fnx_algorithms::tree_broadcast_center(inner))
        .expect("non-empty tree should have a broadcast center");
    let pyset = pyo3::types::PySet::new(
        py,
        center
            .iter()
            .map(|node| gr.py_node_key(py, node))
            .collect::<Vec<_>>(),
    )?;
    Ok((time, pyset.into_any().unbind()))
}

/// Return the broadcast time of a tree or of a specific node in that tree.
#[pyfunction]
#[pyo3(signature = (g, node=None))]
pub fn tree_broadcast_time(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    node: Option<&Bound<'_, PyAny>>,
) -> PyResult<usize> {
    let gr = extract_graph(g)?;
    require_undirected(&gr, "tree_broadcast_time")?;
    let inner = gr.undirected();
    if inner.node_count() == 0 {
        return Err(crate::NetworkXPointlessConcept::new_err("G has no nodes."));
    }
    if !py.allow_threads(|| fnx_algorithms::is_tree(inner).is_tree) {
        return Err(crate::NotATree::new_err("G is not a tree"));
    }

    let node_key = node
        .map(|value| node_key_to_string(py, value))
        .transpose()?;
    if let Some(candidate) = &node_key
        && !gr.has_node(candidate)
    {
        return Err(NodeNotFound::new_err(format!("node {candidate} not in G")));
    }

    py.allow_threads(|| fnx_algorithms::tree_broadcast_time(inner, node_key.as_deref()))
        .ok_or_else(|| NetworkXError::new_err("G is not a tree"))
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

    let edges = match &gr {
        GraphRef::Directed { dg, .. } => {
            fnx_algorithms::bfs_edges_directed(&dg.inner, &source_key, depth_limit)
        }

        GraphRef::Undirected(pg) => {
            let inner = &pg.inner;

            py.allow_threads(|| fnx_algorithms::bfs_edges(inner, &source_key, depth_limit))
        }
        _ => {
            if gr.is_directed() {
                fnx_algorithms::bfs_edges_directed(gr.digraph().unwrap(), &source_key, depth_limit)
            } else {
                let inner = gr.undirected();

                py.allow_threads(|| fnx_algorithms::bfs_edges(inner, &source_key, depth_limit))
            }
        }
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

    let edges = match &gr {
        GraphRef::Directed { dg, .. } => {
            fnx_algorithms::bfs_edges_directed(&dg.inner, &source_key, depth_limit)
        }

        GraphRef::Undirected(pg) => {
            let inner = &pg.inner;

            py.allow_threads(|| fnx_algorithms::bfs_edges(inner, &source_key, depth_limit))
        }
        _ => {
            if gr.is_directed() {
                fnx_algorithms::bfs_edges_directed(gr.digraph().unwrap(), &source_key, depth_limit)
            } else {
                let inner = gr.undirected();

                py.allow_threads(|| fnx_algorithms::bfs_edges(inner, &source_key, depth_limit))
            }
        }
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
            tree.node_key_map.insert(v.clone(), gr.py_node_key(py, v));
            tree.node_py_attrs
                .insert(v.clone(), pyo3::types::PyDict::new(py).unbind());
        }
        let _ = tree.inner.add_edge(u, v);
        tree.edge_py_attrs.insert(
            (u.clone(), v.clone()),
            pyo3::types::PyDict::new(py).unbind(),
        );
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

    let preds = match &gr {
        GraphRef::Directed { dg, .. } => {
            fnx_algorithms::bfs_predecessors_directed(&dg.inner, &source_key, depth_limit)
        }

        GraphRef::Undirected(pg) => {
            let inner = &pg.inner;

            py.allow_threads(|| fnx_algorithms::bfs_predecessors(inner, &source_key, depth_limit))
        }
        _ => {
            if gr.is_directed() {
                fnx_algorithms::bfs_predecessors_directed(
                    gr.digraph().unwrap(),
                    &source_key,
                    depth_limit,
                )
            } else {
                let inner = gr.undirected();

                py.allow_threads(|| {
                    fnx_algorithms::bfs_predecessors(inner, &source_key, depth_limit)
                })
            }
        }
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

    let succs = match &gr {
        GraphRef::Directed { dg, .. } => {
            fnx_algorithms::bfs_successors_directed(&dg.inner, &source_key, depth_limit)
        }

        GraphRef::Undirected(pg) => {
            let inner = &pg.inner;

            py.allow_threads(|| fnx_algorithms::bfs_successors(inner, &source_key, depth_limit))
        }
        _ => {
            if gr.is_directed() {
                fnx_algorithms::bfs_successors_directed(
                    gr.digraph().unwrap(),
                    &source_key,
                    depth_limit,
                )
            } else {
                let inner = gr.undirected();

                py.allow_threads(|| fnx_algorithms::bfs_successors(inner, &source_key, depth_limit))
            }
        }
    };

    Ok(succs
        .into_iter()
        .map(|(parent, children)| {
            let py_parent = gr.py_node_key(py, &parent);
            let py_children: Vec<PyObject> =
                children.iter().map(|c| gr.py_node_key(py, c)).collect();
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
        let layers = match &gr {
            GraphRef::Directed { dg, .. } => {
                fnx_algorithms::bfs_layers_directed(&dg.inner, &source_key)
            }

            GraphRef::Undirected(pg) => {
                let inner = &pg.inner;

                py.allow_threads(|| fnx_algorithms::bfs_layers(inner, &source_key))
            }
            _ => {
                if gr.is_directed() {
                    fnx_algorithms::bfs_layers_directed(gr.digraph().unwrap(), &source_key)
                } else {
                    let inner = gr.undirected();

                    py.allow_threads(|| fnx_algorithms::bfs_layers(inner, &source_key))
                }
            }
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

    let nodes = match &gr {
        GraphRef::Directed { dg, .. } => {
            fnx_algorithms::descendants_at_distance_directed(&dg.inner, &source_key, distance)
        }

        GraphRef::Undirected(pg) => {
            let inner = &pg.inner;

            py.allow_threads(|| {
                fnx_algorithms::descendants_at_distance(inner, &source_key, distance)
            })
        }
        _ => {
            if gr.is_directed() {
                fnx_algorithms::descendants_at_distance_directed(
                    gr.digraph().unwrap(),
                    &source_key,
                    distance,
                )
            } else {
                let inner = gr.undirected();

                py.allow_threads(|| {
                    fnx_algorithms::descendants_at_distance(inner, &source_key, distance)
                })
            }
        }
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

    let edges = match &gr {
        GraphRef::Directed { dg, .. } => {
            fnx_algorithms::dfs_edges_directed(&dg.inner, &source_key, depth_limit)
        }

        GraphRef::Undirected(pg) => {
            let inner = &pg.inner;

            py.allow_threads(|| fnx_algorithms::dfs_edges(inner, &source_key, depth_limit))
        }
        _ => {
            if gr.is_directed() {
                fnx_algorithms::dfs_edges_directed(gr.digraph().unwrap(), &source_key, depth_limit)
            } else {
                let inner = gr.undirected();

                py.allow_threads(|| fnx_algorithms::dfs_edges(inner, &source_key, depth_limit))
            }
        }
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

    let preds = match &gr {
        GraphRef::Directed { dg, .. } => {
            fnx_algorithms::dfs_predecessors_directed(&dg.inner, &source_key, depth_limit)
        }

        GraphRef::Undirected(pg) => {
            let inner = &pg.inner;

            py.allow_threads(|| fnx_algorithms::dfs_predecessors(inner, &source_key, depth_limit))
        }
        _ => {
            if gr.is_directed() {
                fnx_algorithms::dfs_predecessors_directed(
                    gr.digraph().unwrap(),
                    &source_key,
                    depth_limit,
                )
            } else {
                let inner = gr.undirected();

                py.allow_threads(|| {
                    fnx_algorithms::dfs_predecessors(inner, &source_key, depth_limit)
                })
            }
        }
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

    let succs = match &gr {
        GraphRef::Directed { dg, .. } => {
            fnx_algorithms::dfs_successors_directed(&dg.inner, &source_key, depth_limit)
        }

        GraphRef::Undirected(pg) => {
            let inner = &pg.inner;

            py.allow_threads(|| fnx_algorithms::dfs_successors(inner, &source_key, depth_limit))
        }
        _ => {
            if gr.is_directed() {
                fnx_algorithms::dfs_successors_directed(
                    gr.digraph().unwrap(),
                    &source_key,
                    depth_limit,
                )
            } else {
                let inner = gr.undirected();

                py.allow_threads(|| fnx_algorithms::dfs_successors(inner, &source_key, depth_limit))
            }
        }
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

    let nodes = match &gr {
        GraphRef::Directed { dg, .. } => {
            fnx_algorithms::dfs_preorder_nodes_directed(&dg.inner, &source_key, depth_limit)
        }

        GraphRef::Undirected(pg) => {
            let inner = &pg.inner;

            py.allow_threads(|| fnx_algorithms::dfs_preorder_nodes(inner, &source_key, depth_limit))
        }
        _ => {
            if gr.is_directed() {
                fnx_algorithms::dfs_preorder_nodes_directed(
                    gr.digraph().unwrap(),
                    &source_key,
                    depth_limit,
                )
            } else {
                let inner = gr.undirected();

                py.allow_threads(|| {
                    fnx_algorithms::dfs_preorder_nodes(inner, &source_key, depth_limit)
                })
            }
        }
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

    let nodes = match &gr {
        GraphRef::Directed { dg, .. } => {
            fnx_algorithms::dfs_postorder_nodes_directed(&dg.inner, &source_key, depth_limit)
        }

        GraphRef::Undirected(pg) => {
            let inner = &pg.inner;

            py.allow_threads(|| {
                fnx_algorithms::dfs_postorder_nodes(inner, &source_key, depth_limit)
            })
        }
        _ => {
            if gr.is_directed() {
                fnx_algorithms::dfs_postorder_nodes_directed(
                    gr.digraph().unwrap(),
                    &source_key,
                    depth_limit,
                )
            } else {
                let inner = gr.undirected();

                py.allow_threads(|| {
                    fnx_algorithms::dfs_postorder_nodes(inner, &source_key, depth_limit)
                })
            }
        }
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
pub fn topological_sort(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<Vec<PyObject>> {
    let gr = extract_graph(g)?;
    if !gr.is_directed() {
        return Err(NetworkXError::new_err(
            "Topological sort not defined on undirected graphs.",
        ));
    }
    {
        let dg_ref = gr.digraph().expect("is_directed checked above");
        match fnx_algorithms::topological_sort(dg_ref) {
            Some(result) => Ok(result.order.iter().map(|n| gr.py_node_key(py, n)).collect()),
            None => Err(crate::HasACycle::new_err(
                "Graph contains a cycle, topological sort is not possible.",
            )),
        }
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
    {
        let dg_ref = gr.digraph().expect("is_directed checked above");
        match fnx_algorithms::topological_generations(dg_ref) {
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
    }
}

/// Return the longest path in a DAG.
///
/// Matches `networkx.dag_longest_path(G)`.
#[pyfunction]
pub fn dag_longest_path(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<Vec<PyObject>> {
    let gr = extract_graph(g)?;
    if !gr.is_directed() {
        return Err(NetworkXError::new_err(
            "dag_longest_path not defined on undirected graphs.",
        ));
    }
    {
        let dg_ref = gr.digraph().expect("is_directed checked above");
        match fnx_algorithms::dag_longest_path(dg_ref) {
            Some(path) => Ok(path.iter().map(|n| gr.py_node_key(py, n)).collect()),
            None => Err(crate::HasACycle::new_err("Graph contains a cycle.")),
        }
    }
}

/// Return the length of the longest path in a DAG.
///
/// Matches `networkx.dag_longest_path_length(G)`.
#[pyfunction]
pub fn dag_longest_path_length(_py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<usize> {
    let gr = extract_graph(g)?;
    if !gr.is_directed() {
        return Err(NetworkXError::new_err(
            "dag_longest_path_length not defined on undirected graphs.",
        ));
    }
    {
        let dg_ref = gr.digraph().expect("is_directed checked above");
        match fnx_algorithms::dag_longest_path_length(dg_ref) {
            Some(length) => Ok(length),
            None => Err(crate::HasACycle::new_err("Graph contains a cycle.")),
        }
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
    {
        let dg_ref = gr.digraph().expect("is_directed checked above");
        match fnx_algorithms::lexicographic_topological_sort(dg_ref) {
            Some(order) => Ok(order.iter().map(|n| gr.py_node_key(py, n)).collect()),
            None => Err(crate::HasACycle::new_err(
                "Graph contains a cycle, topological sort is not possible.",
            )),
        }
    }
}

/// Return True if the directed graph G is a directed acyclic graph (DAG).
#[pyfunction]
pub fn is_directed_acyclic_graph(_py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<bool> {
    let gr = extract_graph(g)?;
    if !gr.is_directed() {
        return Ok(false);
    }
    {
        let dg_ref = gr.digraph().expect("is_directed checked above");
        Ok(fnx_algorithms::is_directed_acyclic_graph(dg_ref))
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

    {
        let dg_ref = gr.digraph().expect("is_directed checked above");
        let result = fnx_algorithms::ancestors(dg_ref, &source_key);
        let py_nodes: Vec<PyObject> = result.iter().map(|n| gr.py_node_key(py, n)).collect();
        pyo3::types::PyFrozenSet::new(py, &py_nodes).map(|s| s.unbind())
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

    {
        let dg_ref = gr.digraph().expect("is_directed checked above");
        let result = fnx_algorithms::descendants(dg_ref, &source_key);
        let py_nodes: Vec<PyObject> = result.iter().map(|n| gr.py_node_key(py, n)).collect();
        pyo3::types::PyFrozenSet::new(py, &py_nodes).map(|s| s.unbind())
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
        {
            let dg_ref = gr.digraph().expect("is_directed checked above");
            fnx_algorithms::all_shortest_paths_directed(dg_ref, &source_key, &target_key)
        }
    } else {
        let inner = gr.undirected();
        match weight {
            Some(w) => py.allow_threads(|| {
                fnx_algorithms::all_shortest_paths_weighted(inner, &source_key, &target_key, w)
            }),
            None => py.allow_threads(|| {
                fnx_algorithms::all_shortest_paths(inner, &source_key, &target_key)
            }),
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
            py_graph
                .node_py_attrs
                .insert(node.to_owned(), pyo3::types::PyDict::new(py).unbind());
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
            py_dg
                .node_py_attrs
                .insert(node.to_owned(), pyo3::types::PyDict::new(py).unbind());
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
pub fn average_degree_connectivity(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<PyObject> {
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
pub fn rich_club_coefficient(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<PyObject> {
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
pub fn s_metric(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<f64> {
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
pub fn is_empty(_py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<bool> {
    let gr = extract_graph(g)?;
    match &gr {
        GraphRef::Undirected(pg) => Ok(fnx_algorithms::is_empty(&pg.inner)),
        GraphRef::Directed { dg, .. } => Ok(fnx_algorithms::is_empty_directed(&dg.inner)),
        _ => {
            if gr.is_directed() {
                Ok(fnx_algorithms::is_empty_directed(gr.digraph().unwrap()))
            } else {
                Ok(fnx_algorithms::is_empty(gr.undirected()))
            }
        }
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
pub fn number_of_cliques(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<PyObject> {
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

/// Return all triangles as a list of 3-tuples.
#[pyfunction]
#[pyo3(signature = (g,))]
pub fn all_triangles(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
) -> PyResult<Vec<(PyObject, PyObject, PyObject)>> {
    let gr = extract_graph(g)?;
    require_undirected(&gr, "all_triangles")?;
    let inner = gr.undirected();
    let result = py.allow_threads(|| fnx_algorithms::all_triangles(inner));
    Ok(result
        .iter()
        .map(|(a, b, c)| {
            (
                gr.py_node_key(py, a),
                gr.py_node_key(py, b),
                gr.py_node_key(py, c),
            )
        })
        .collect())
}

/// Return the clique number of each node (size of the largest clique containing that node).
#[pyfunction]
#[pyo3(signature = (g,))]
pub fn node_clique_number(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<PyObject> {
    let gr = extract_graph(g)?;
    require_undirected(&gr, "node_clique_number")?;
    let inner = gr.undirected();
    let result = py.allow_threads(|| fnx_algorithms::node_clique_number(inner));
    let dict = pyo3::types::PyDict::new(py);
    for (node, size) in &result {
        dict.set_item(gr.py_node_key(py, node), *size)?;
    }
    Ok(dict.into_any().unbind())
}

/// Enumerate all cliques (not just maximal) in a graph.
#[pyfunction]
#[pyo3(signature = (g,))]
pub fn enumerate_all_cliques(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<Vec<Vec<PyObject>>> {
    let gr = extract_graph(g)?;
    require_undirected(&gr, "enumerate_all_cliques")?;
    let inner = gr.undirected();
    let result = py.allow_threads(|| fnx_algorithms::enumerate_all_cliques(inner));
    Ok(result
        .iter()
        .map(|clique| clique.iter().map(|n| gr.py_node_key(py, n)).collect())
        .collect())
}

/// Find all maximal cliques using a recursive Bron-Kerbosch algorithm.
#[pyfunction]
#[pyo3(signature = (g,))]
pub fn find_cliques_recursive(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
) -> PyResult<Vec<Vec<PyObject>>> {
    let gr = extract_graph(g)?;
    require_undirected(&gr, "find_cliques_recursive")?;
    let inner = gr.undirected();
    let result = py.allow_threads(|| fnx_algorithms::find_cliques_recursive(inner));
    Ok(result
        .iter()
        .map(|clique| clique.iter().map(|n| gr.py_node_key(py, n)).collect())
        .collect())
}

/// Return maximal cliques of a chordal graph.
#[pyfunction]
#[pyo3(signature = (g,))]
pub fn chordal_graph_cliques(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<Vec<Vec<PyObject>>> {
    let gr = extract_graph(g)?;
    require_undirected(&gr, "chordal_graph_cliques")?;
    let inner = gr.undirected();
    if inner
        .nodes_ordered()
        .into_iter()
        .any(|node| inner.has_edge(node, node))
    {
        return Err(NetworkXError::new_err("Input graph is not chordal."));
    }
    let result = py.allow_threads(|| fnx_algorithms::chordal_graph_cliques(inner));
    Ok(result
        .iter()
        .map(|clique| clique.iter().map(|n| gr.py_node_key(py, n)).collect())
        .collect())
}

/// Return the treewidth of a chordal graph.
#[pyfunction]
#[pyo3(signature = (g,))]
pub fn chordal_graph_treewidth(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<usize> {
    let gr = extract_graph(g)?;
    require_undirected(&gr, "chordal_graph_treewidth")?;
    let inner = gr.undirected();
    if inner.node_count() == 0 {
        return Err(PyValueError::new_err("max() iterable argument is empty"));
    }
    py.allow_threads(|| fnx_algorithms::chordal_graph_treewidth(inner))
        .map_err(|err| NetworkXError::new_err(err.to_string()))
}

/// Build the max clique graph.
#[pyfunction]
#[pyo3(signature = (g,))]
pub fn make_max_clique_graph(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<PyObject> {
    let gr = extract_graph(g)?;
    require_undirected(&gr, "make_max_clique_graph")?;
    let inner = gr.undirected();
    let result = py.allow_threads(|| fnx_algorithms::make_max_clique_graph(inner));
    rust_graph_to_py_standalone(py, &result)
}

/// Generate a ring of cliques graph.
#[pyfunction]
#[pyo3(signature = (num_cliques, clique_size))]
pub fn ring_of_cliques(
    py: Python<'_>,
    num_cliques: usize,
    clique_size: usize,
) -> PyResult<PyObject> {
    let result = py
        .allow_threads(|| fnx_algorithms::ring_of_cliques(num_cliques, clique_size))
        .map_err(NetworkXError::new_err)?;
    rust_graph_to_py_standalone(py, &result)
}

// ===========================================================================
// Classic graph generators
// ===========================================================================

#[pyfunction]
#[pyo3(signature = (r, h))]
pub fn balanced_tree(py: Python<'_>, r: usize, h: usize) -> PyResult<PyObject> {
    let result = py.allow_threads(|| fnx_algorithms::balanced_tree(r, h));
    rust_graph_to_py_standalone(py, &result)
}

#[pyfunction]
#[pyo3(signature = (n1, n2))]
pub fn barbell_graph(py: Python<'_>, n1: usize, n2: usize) -> PyResult<PyObject> {
    let result = py
        .allow_threads(|| fnx_algorithms::barbell_graph(n1, n2))
        .map_err(NetworkXError::new_err)?;
    rust_graph_to_py_standalone(py, &result)
}

#[pyfunction]
pub fn bull_graph(py: Python<'_>) -> PyResult<PyObject> {
    let result = py.allow_threads(fnx_algorithms::bull_graph);
    rust_graph_to_py_standalone(py, &result)
}

#[pyfunction]
pub fn chvatal_graph(py: Python<'_>) -> PyResult<PyObject> {
    let result = py.allow_threads(fnx_algorithms::chvatal_graph);
    rust_graph_to_py_standalone(py, &result)
}

#[pyfunction]
pub fn cubical_graph(py: Python<'_>) -> PyResult<PyObject> {
    let result = py.allow_threads(fnx_algorithms::cubical_graph);
    rust_graph_to_py_standalone(py, &result)
}

#[pyfunction]
pub fn desargues_graph(py: Python<'_>) -> PyResult<PyObject> {
    let result = py.allow_threads(fnx_algorithms::desargues_graph);
    rust_graph_to_py_standalone(py, &result)
}

#[pyfunction]
pub fn diamond_graph(py: Python<'_>) -> PyResult<PyObject> {
    let result = py.allow_threads(fnx_algorithms::diamond_graph);
    rust_graph_to_py_standalone(py, &result)
}

#[pyfunction]
pub fn dodecahedral_graph(py: Python<'_>) -> PyResult<PyObject> {
    let result = py.allow_threads(fnx_algorithms::dodecahedral_graph);
    rust_graph_to_py_standalone(py, &result)
}

#[pyfunction]
pub fn frucht_graph(py: Python<'_>) -> PyResult<PyObject> {
    let result = py.allow_threads(fnx_algorithms::frucht_graph);
    rust_graph_to_py_standalone(py, &result)
}

#[pyfunction]
pub fn heawood_graph(py: Python<'_>) -> PyResult<PyObject> {
    let result = py.allow_threads(fnx_algorithms::heawood_graph);
    rust_graph_to_py_standalone(py, &result)
}

#[pyfunction]
pub fn house_graph(py: Python<'_>) -> PyResult<PyObject> {
    let result = py.allow_threads(fnx_algorithms::house_graph);
    rust_graph_to_py_standalone(py, &result)
}

#[pyfunction]
pub fn house_x_graph(py: Python<'_>) -> PyResult<PyObject> {
    let result = py.allow_threads(fnx_algorithms::house_x_graph);
    rust_graph_to_py_standalone(py, &result)
}

#[pyfunction]
pub fn icosahedral_graph(py: Python<'_>) -> PyResult<PyObject> {
    let result = py.allow_threads(fnx_algorithms::icosahedral_graph);
    rust_graph_to_py_standalone(py, &result)
}

#[pyfunction]
pub fn krackhardt_kite_graph(py: Python<'_>) -> PyResult<PyObject> {
    let result = py.allow_threads(fnx_algorithms::krackhardt_kite_graph);
    rust_graph_to_py_standalone(py, &result)
}

#[pyfunction]
pub fn moebius_kantor_graph(py: Python<'_>) -> PyResult<PyObject> {
    let result = py.allow_threads(fnx_algorithms::moebius_kantor_graph);
    rust_graph_to_py_standalone(py, &result)
}

#[pyfunction]
pub fn octahedral_graph(py: Python<'_>) -> PyResult<PyObject> {
    let result = py.allow_threads(fnx_algorithms::octahedral_graph);
    rust_graph_to_py_standalone(py, &result)
}

#[pyfunction]
pub fn pappus_graph(py: Python<'_>) -> PyResult<PyObject> {
    let result = py.allow_threads(fnx_algorithms::pappus_graph);
    rust_graph_to_py_standalone(py, &result)
}

#[pyfunction]
pub fn petersen_graph(py: Python<'_>) -> PyResult<PyObject> {
    let result = py.allow_threads(fnx_algorithms::petersen_graph);
    rust_graph_to_py_standalone(py, &result)
}

#[pyfunction]
pub fn sedgewick_maze_graph(py: Python<'_>) -> PyResult<PyObject> {
    let result = py.allow_threads(fnx_algorithms::sedgewick_maze_graph);
    rust_graph_to_py_standalone(py, &result)
}

#[pyfunction]
pub fn tetrahedral_graph(py: Python<'_>) -> PyResult<PyObject> {
    let result = py.allow_threads(fnx_algorithms::tetrahedral_graph);
    rust_graph_to_py_standalone(py, &result)
}

#[pyfunction]
pub fn truncated_cube_graph(py: Python<'_>) -> PyResult<PyObject> {
    let result = py.allow_threads(fnx_algorithms::truncated_cube_graph);
    rust_graph_to_py_standalone(py, &result)
}

#[pyfunction]
pub fn truncated_tetrahedron_graph(py: Python<'_>) -> PyResult<PyObject> {
    let result = py.allow_threads(fnx_algorithms::truncated_tetrahedron_graph);
    rust_graph_to_py_standalone(py, &result)
}

#[pyfunction]
pub fn tutte_graph(py: Python<'_>) -> PyResult<PyObject> {
    let result = py.allow_threads(fnx_algorithms::tutte_graph);
    rust_graph_to_py_standalone(py, &result)
}

#[pyfunction]
pub fn hoffman_singleton_graph(py: Python<'_>) -> PyResult<PyObject> {
    let result = py.allow_threads(fnx_algorithms::hoffman_singleton_graph);
    rust_graph_to_py_standalone(py, &result)
}

#[pyfunction]
#[pyo3(signature = (n, k))]
pub fn generalized_petersen_graph(py: Python<'_>, n: usize, k: usize) -> PyResult<PyObject> {
    let result = py
        .allow_threads(|| fnx_algorithms::generalized_petersen_graph(n, k))
        .map_err(NetworkXError::new_err)?;
    rust_graph_to_py_standalone(py, &result)
}

#[pyfunction]
#[pyo3(signature = (n,))]
pub fn wheel_graph(py: Python<'_>, n: usize) -> PyResult<PyObject> {
    let result = py
        .allow_threads(|| fnx_algorithms::wheel_graph(n))
        .map_err(NetworkXError::new_err)?;
    rust_graph_to_py_standalone(py, &result)
}

#[pyfunction]
#[pyo3(signature = (n,))]
pub fn ladder_graph(py: Python<'_>, n: usize) -> PyResult<PyObject> {
    let result = py
        .allow_threads(|| fnx_algorithms::ladder_graph(n))
        .map_err(NetworkXError::new_err)?;
    rust_graph_to_py_standalone(py, &result)
}

#[pyfunction]
#[pyo3(signature = (n,))]
pub fn circular_ladder_graph(py: Python<'_>, n: usize) -> PyResult<PyObject> {
    let result = py
        .allow_threads(|| fnx_algorithms::circular_ladder_graph(n))
        .map_err(NetworkXError::new_err)?;
    rust_graph_to_py_standalone(py, &result)
}

#[pyfunction]
#[pyo3(signature = (m, n))]
pub fn lollipop_graph(py: Python<'_>, m: usize, n: usize) -> PyResult<PyObject> {
    let result = py
        .allow_threads(|| fnx_algorithms::lollipop_graph(m, n))
        .map_err(NetworkXError::new_err)?;
    rust_graph_to_py_standalone(py, &result)
}

#[pyfunction]
#[pyo3(signature = (m, n))]
pub fn tadpole_graph(py: Python<'_>, m: usize, n: usize) -> PyResult<PyObject> {
    let result = py
        .allow_threads(|| fnx_algorithms::tadpole_graph(m, n))
        .map_err(NetworkXError::new_err)?;
    rust_graph_to_py_standalone(py, &result)
}

#[pyfunction]
#[pyo3(signature = (n, r))]
pub fn turan_graph(py: Python<'_>, n: usize, r: usize) -> PyResult<PyObject> {
    let result = py
        .allow_threads(|| fnx_algorithms::turan_graph(n, r))
        .map_err(NetworkXError::new_err)?;
    rust_graph_to_py_standalone(py, &result)
}

#[pyfunction]
#[pyo3(signature = (k, n))]
pub fn windmill_graph(py: Python<'_>, k: usize, n: usize) -> PyResult<PyObject> {
    let result = py
        .allow_threads(|| fnx_algorithms::windmill_graph(k, n))
        .map_err(NetworkXError::new_err)?;
    rust_graph_to_py_standalone(py, &result)
}

#[pyfunction]
#[pyo3(signature = (n,))]
pub fn hypercube_graph(py: Python<'_>, n: usize) -> PyResult<PyObject> {
    let result = py
        .allow_threads(|| fnx_algorithms::hypercube_graph(n))
        .map_err(NetworkXError::new_err)?;
    rust_graph_to_py_standalone(py, &result)
}

#[pyfunction]
#[pyo3(signature = (n1, n2))]
pub fn complete_bipartite_graph(py: Python<'_>, n1: usize, n2: usize) -> PyResult<PyObject> {
    let result = py
        .allow_threads(|| fnx_algorithms::complete_bipartite_graph(n1, n2))
        .map_err(NetworkXError::new_err)?;
    rust_graph_to_py_standalone(py, &result)
}

#[pyfunction]
#[pyo3(signature = (block_sizes,))]
pub fn complete_multipartite_graph(py: Python<'_>, block_sizes: Vec<usize>) -> PyResult<PyObject> {
    let result = py
        .allow_threads(|| fnx_algorithms::complete_multipartite_graph(&block_sizes))
        .map_err(NetworkXError::new_err)?;
    rust_graph_to_py_standalone(py, &result)
}

#[pyfunction]
#[pyo3(signature = (m, n))]
pub fn grid_2d_graph(py: Python<'_>, m: usize, n: usize) -> PyResult<PyObject> {
    let result = py.allow_threads(|| fnx_algorithms::grid_2d_graph(m, n));
    rust_graph_to_py_standalone(py, &result)
}

#[pyfunction]
pub fn null_graph(py: Python<'_>) -> PyResult<PyObject> {
    let result = fnx_algorithms::null_graph();
    rust_graph_to_py_standalone(py, &result)
}

#[pyfunction]
pub fn trivial_graph(py: Python<'_>) -> PyResult<PyObject> {
    let result = fnx_algorithms::trivial_graph();
    rust_graph_to_py_standalone(py, &result)
}

#[pyfunction]
#[pyo3(signature = (n,))]
pub fn binomial_tree(py: Python<'_>, n: usize) -> PyResult<PyObject> {
    let result = py.allow_threads(|| fnx_algorithms::binomial_tree(n));
    rust_graph_to_py_standalone(py, &result)
}

#[pyfunction]
#[pyo3(signature = (r, n))]
pub fn full_rary_tree(py: Python<'_>, r: usize, n: usize) -> PyResult<PyObject> {
    let result = py.allow_threads(|| fnx_algorithms::full_rary_tree(r, n));
    rust_graph_to_py_standalone(py, &result)
}

#[pyfunction]
#[pyo3(signature = (n, offsets))]
pub fn circulant_graph(py: Python<'_>, n: usize, offsets: Vec<usize>) -> PyResult<PyObject> {
    let result = py
        .allow_threads(|| fnx_algorithms::circulant_graph(n, &offsets))
        .map_err(NetworkXError::new_err)?;
    rust_graph_to_py_standalone(py, &result)
}

#[pyfunction]
#[pyo3(signature = (n, k))]
pub fn kneser_graph(py: Python<'_>, n: usize, k: usize) -> PyResult<PyObject> {
    let result = py
        .allow_threads(|| fnx_algorithms::kneser_graph(n, k))
        .map_err(NetworkXError::new_err)?;
    rust_graph_to_py_standalone(py, &result)
}

#[pyfunction]
#[pyo3(signature = (q,))]
pub fn paley_graph(py: Python<'_>, q: usize) -> PyResult<PyObject> {
    let result = py
        .allow_threads(|| fnx_algorithms::paley_graph(q))
        .map_err(NetworkXError::new_err)?;
    rust_graph_to_py_standalone(py, &result)
}

#[pyfunction]
#[pyo3(signature = (n,))]
pub fn chordal_cycle_graph(py: Python<'_>, n: usize) -> PyResult<PyObject> {
    let result = py
        .allow_threads(|| fnx_algorithms::chordal_cycle_graph(n))
        .map_err(NetworkXError::new_err)?;
    rust_graph_to_py_standalone(py, &result)
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
pub fn dominating_set(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<Vec<PyObject>> {
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
    let dg_ref = gr.digraph().expect("is_directed checked above");
    let result = fnx_algorithms::strongly_connected_components(dg_ref);
    result
        .iter()
        .map(|comp| {
            let py_set: Vec<PyObject> = comp.iter().map(|n| gr.py_node_key(py, n)).collect();
            py_set.into_pyobject(py).map(|obj| obj.into_any().unbind())
        })
        .collect()
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
    {
        let dg_ref = gr.digraph().expect("is_directed checked above");
        Ok(fnx_algorithms::number_strongly_connected_components(dg_ref))
    }
}

/// Return whether the directed graph is strongly connected.
#[pyfunction]
pub fn is_strongly_connected(_py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<bool> {
    let gr = extract_graph(g)?;
    if !gr.is_directed() {
        return Err(crate::NetworkXNotImplemented::new_err(
            "is_strongly_connected is not defined for undirected graphs. Use is_connected instead.",
        ));
    }
    {
        let dg_ref = gr.digraph().expect("is_directed checked above");
        Ok(fnx_algorithms::is_strongly_connected(dg_ref))
    }
}

/// Condense a directed graph by contracting each SCC into a single node.
///
/// Returns a tuple (condensation_graph, mapping) where mapping is a dict
/// from original nodes to SCC indices.
#[pyfunction]
pub fn condensation(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<(PyObject, PyObject)> {
    let gr = extract_graph(g)?;
    if !gr.is_directed() {
        return Err(crate::NetworkXNotImplemented::new_err(
            "condensation is not defined for undirected graphs.",
        ));
    }
    {
        let dg_ref = gr.digraph().expect("is_directed checked above");
        let (cond_graph, node_mapping) = fnx_algorithms::condensation(dg_ref);
        // Build the condensation DiGraph
        let mut py_dg = PyDiGraph::new_empty(py)?;
        for node in cond_graph.nodes_ordered() {
            py_dg.node_key_map.insert(
                node.to_owned(),
                node.parse::<i64>()
                    .unwrap()
                    .into_pyobject(py)?
                    .into_any()
                    .unbind(),
            );
            py_dg
                .node_py_attrs
                .insert(node.to_owned(), pyo3::types::PyDict::new(py).unbind());
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
            mapping.set_item(gr.py_node_key(py, node), *scc_idx)?;
        }
        Ok((py_cond, mapping.into_any().unbind()))
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
    {
        let dg_ref = gr.digraph().expect("is_directed checked above");
        let result = fnx_algorithms::weakly_connected_components(dg_ref);
        result
            .iter()
            .map(|comp| {
                let py_set: Vec<PyObject> = comp.iter().map(|n| gr.py_node_key(py, n)).collect();
                py_set.into_pyobject(py).map(|obj| obj.into_any().unbind())
            })
            .collect()
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
    {
        let dg_ref = gr.digraph().expect("is_directed checked above");
        Ok(fnx_algorithms::number_weakly_connected_components(dg_ref))
    }
}

/// Return whether the directed graph is weakly connected.
#[pyfunction]
pub fn is_weakly_connected(_py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<bool> {
    let gr = extract_graph(g)?;
    if !gr.is_directed() {
        return Err(crate::NetworkXNotImplemented::new_err(
            "is_weakly_connected is not defined for undirected graphs. Use is_connected instead.",
        ));
    }
    {
        let dg_ref = gr.digraph().expect("is_directed checked above");
        if dg_ref.node_count() == 0 {
            return Err(crate::NetworkXPointlessConcept::new_err(
                "Connectivity is undefined for the null graph.",
            ));
        }
        Ok(fnx_algorithms::is_weakly_connected(dg_ref))
    }
}

// ===========================================================================
// Transitive Closure / Reduction
// ===========================================================================

/// Return the transitive closure of a directed graph.
#[pyfunction]
pub fn transitive_closure(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<PyObject> {
    let gr = extract_graph(g)?;
    if !gr.is_directed() {
        return Err(crate::NetworkXNotImplemented::new_err(
            "transitive_closure is not defined for undirected graphs.",
        ));
    }
    {
        let dg_ref = gr.digraph().expect("is_directed checked above");
        let result = fnx_algorithms::transitive_closure(dg_ref);
        let mut py_dg = PyDiGraph::new_empty(py)?;
        for node in result.nodes_ordered() {
            let py_key = gr.py_node_key(py, node);
            py_dg.node_key_map.insert(node.to_owned(), py_key);
            py_dg
                .node_py_attrs
                .insert(node.to_owned(), pyo3::types::PyDict::new(py).unbind());
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
}

/// Return the transitive reduction of a directed acyclic graph.
#[pyfunction]
pub fn transitive_reduction(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<PyObject> {
    let gr = extract_graph(g)?;
    if !gr.is_directed() {
        return Err(crate::NetworkXNotImplemented::new_err(
            "transitive_reduction is not defined for undirected graphs.",
        ));
    }
    {
        let dg_ref = gr.digraph().expect("is_directed checked above");
        match fnx_algorithms::transitive_reduction(dg_ref) {
            Some(result) => {
                let mut py_dg = PyDiGraph::new_empty(py)?;
                for node in result.nodes_ordered() {
                    let py_key = gr.py_node_key(py, node);
                    py_dg.node_key_map.insert(node.to_owned(), py_key);
                    py_dg
                        .node_py_attrs
                        .insert(node.to_owned(), pyo3::types::PyDict::new(py).unbind());
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
    }
}

// ===========================================================================
// Reciprocity
// ===========================================================================

/// Compute the overall reciprocity of a directed graph.
///
/// Matches `networkx.overall_reciprocity(G)`.
#[pyfunction]
pub fn overall_reciprocity(_py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<f64> {
    let gr = extract_graph(g)?;
    if !gr.is_directed() {
        return Err(NetworkXError::new_err(
            "overall_reciprocity not defined on undirected graphs.",
        ));
    }
    {
        let dg_ref = gr.digraph().expect("is_directed checked above");
        Ok(fnx_algorithms::overall_reciprocity(dg_ref))
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
    {
        let dg_ref = gr.digraph().expect("is_directed checked above");
        let node_list: Vec<String> = if let Some(ns) = nodes {
            // Check if it's a single node (not iterable list)
            if let Ok(s) = node_key_to_string(py, ns)
                && dg_ref.has_node(&s)
            {
                // Single node: return a float directly
                let node_refs: Vec<&str> = vec![s.as_str()];
                let result = fnx_algorithms::reciprocity(dg_ref, &node_refs);
                let val = result.get(&s).copied().unwrap_or(0.0);
                return Ok(val.into_pyobject(py).unwrap().into_any().unbind());
            }
            // Try as iterable
            ns.try_iter()?
                .map(|item| node_key_to_string(py, &item?))
                .collect::<PyResult<Vec<_>>>()?
        } else {
            dg_ref
                .nodes_ordered()
                .into_iter()
                .map(|s| s.to_owned())
                .collect()
        };

        let node_refs: Vec<&str> = node_list.iter().map(String::as_str).collect();
        let result = fnx_algorithms::reciprocity(dg_ref, &node_refs);

        let dict = pyo3::types::PyDict::new(py);
        for (k, v) in &result {
            let py_key = gr.py_node_key(py, k);
            dict.set_item(py_key, v)?;
        }
        Ok(dict.into_any().unbind())
    }
}

// ===========================================================================
// Wiener Index
// ===========================================================================

/// Compute the Wiener index of a connected graph.
///
/// Matches `networkx.wiener_index(G)`.
#[pyfunction]
pub fn wiener_index(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<f64> {
    let gr = extract_graph(g)?;
    require_undirected(&gr, "wiener_index")?;
    let inner = gr.undirected();
    match py.allow_threads(|| fnx_algorithms::wiener_index(inner)) {
        Some(w) => Ok(w),
        None => Err(NetworkXError::new_err("Graph is not connected.")),
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

fn rust_graph_to_py(
    py: Python<'_>,
    result: &fnx_classes::Graph,
    source_gr: &GraphRef<'_>,
) -> PyResult<PyObject> {
    let mut py_graph = PyGraph::new_empty(py)?;
    for node in result.nodes_ordered() {
        let py_key = source_gr.py_node_key(py, node);
        py_graph.node_key_map.insert(node.to_owned(), py_key);
        py_graph
            .node_py_attrs
            .insert(node.to_owned(), pyo3::types::PyDict::new(py).unbind());
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

fn rust_graph_to_py_with_source_edge_attrs(
    py: Python<'_>,
    result: &fnx_classes::Graph,
    source_gr: &GraphRef<'_>,
) -> PyResult<PyObject> {
    let mut py_graph = PyGraph::new_empty(py)?;
    for node in result.nodes_ordered() {
        let py_key = source_gr.py_node_key(py, node);
        py_graph.node_key_map.insert(node.to_owned(), py_key);
        py_graph
            .node_py_attrs
            .insert(node.to_owned(), pyo3::types::PyDict::new(py).unbind());
        py_graph.inner.add_node(node);
    }
    for edge in result.edges_ordered() {
        let _ = py_graph.inner.add_edge(&edge.left, &edge.right);
        let ek = PyGraph::edge_key(&edge.left, &edge.right);
        let attrs = if let Some(source_attrs) =
            source_gr.edge_attrs_for_undirected(&edge.left, &edge.right)
        {
            source_attrs.bind(py).copy()?.unbind()
        } else {
            pyo3::types::PyDict::new(py).unbind()
        };
        py_graph.edge_py_attrs.insert(ek, attrs);
    }
    Ok(py_graph.into_pyobject(py)?.into_any().unbind())
}

/// Convert a Rust Graph to a Python Graph using NetworkX-style integer labels
/// when the canonical keys are numeric.
fn rust_graph_to_py_standalone(py: Python<'_>, result: &fnx_classes::Graph) -> PyResult<PyObject> {
    let mut py_graph = PyGraph::new_empty(py)?;
    for node in result.nodes_ordered() {
        let py_key = if let Ok(i) = node.parse::<i64>() {
            crate::unwrap_infallible(i.into_pyobject(py)).into_any().unbind()
        } else {
            crate::unwrap_infallible(node.to_owned().into_pyobject(py))
                .into_any()
                .unbind()
        };
        py_graph.node_key_map.insert(node.to_owned(), py_key);
        py_graph
            .node_py_attrs
            .insert(node.to_owned(), pyo3::types::PyDict::new(py).unbind());
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
fn symmetric_difference(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    h: &Bound<'_, PyAny>,
) -> PyResult<PyObject> {
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
    let result =
        py.allow_threads(|| fnx_algorithms::louvain_communities(inner, resolution, weight, seed));
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
    communities: &Bound<'_, PyAny>,
    resolution: f64,
    weight: &str,
) -> PyResult<f64> {
    let gr = extract_graph(g)?;
    
    let mut comms_strs = Vec::new();
    for comm in communities.try_iter()? {
        let comm = comm?;
        let mut comm_strs = Vec::new();
        for node in comm.try_iter()? {
            let node = node?;
            let s = node_key_to_string(py, &node)?;
            validate_node(&gr, &s, &node)?;
            comm_strs.push(s);
        }
        comms_strs.push(comm_strs);
    }
    
    let inner = gr.undirected();
    Ok(py.allow_threads(|| fnx_algorithms::modularity(inner, &comms_strs, resolution, weight)))
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
    let result = py
        .allow_threads(|| fnx_algorithms::greedy_modularity_communities(inner, resolution, weight));
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
        py.allow_threads(|| fnx_algorithms::astar_path(inner, &src_key, &tgt_key, weight, None))
    };

    match result {
        Some(path) => Ok(path.iter().map(|n| gr.py_node_key(py, n)).collect()),
        None => Err(pyo3::exceptions::PyValueError::new_err(format!(
            "No path between {} and {}.",
            src_key, tgt_key
        ))),
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
        None => Err(pyo3::exceptions::PyValueError::new_err(format!(
            "No path between {} and {}.",
            src_key, tgt_key
        ))),
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
    let result = py
        .allow_threads(|| fnx_algorithms::shortest_simple_paths(inner, &src_key, &tgt_key, weight));
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
fn could_be_isomorphic(
    py: Python<'_>,
    g1: &Bound<'_, PyAny>,
    g2: &Bound<'_, PyAny>,
) -> PyResult<bool> {
    let gr1 = extract_graph(g1)?;
    let gr2 = extract_graph(g2)?;
    let inner1 = gr1.undirected();
    let inner2 = gr2.undirected();
    Ok(py.allow_threads(|| fnx_algorithms::could_be_isomorphic(inner1, inner2)))
}

/// Fast check if two graphs could be isomorphic (node/edge count + degree sequence).
#[pyfunction]
#[pyo3(signature = (g1, g2))]
fn fast_could_be_isomorphic(
    py: Python<'_>,
    g1: &Bound<'_, PyAny>,
    g2: &Bound<'_, PyAny>,
) -> PyResult<bool> {
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
    let pyset = pyo3::types::PySet::new(
        py,
        result
            .keys()
            .map(|n| gr.py_node_key(py, n))
            .collect::<Vec<_>>(),
    )?;
    Ok(pyset.into_any().unbind())
}

fn maximal_independent_set_with_random(
    py: Python<'_>,
    gr: &GraphRef<'_>,
    inner: &fnx_classes::Graph,
    initial_nodes: &[String],
    random: &Bound<'_, PyAny>,
) -> PyResult<Vec<PyObject>> {
    let ordered_nodes: Vec<String> = inner
        .nodes_ordered()
        .into_iter()
        .map(str::to_owned)
        .collect();
    let node_set: HashSet<&str> = ordered_nodes.iter().map(String::as_str).collect();
    let mut required = Vec::new();
    let mut seen = HashSet::new();
    for node in initial_nodes {
        if !node_set.contains(node.as_str()) {
            return Err(NetworkXUnfeasible::new_err(format!(
                "{initial_nodes:?} is not a subset of the nodes of G"
            )));
        }
        if seen.insert(node.clone()) {
            required.push(node.clone());
        }
    }
    if required.is_empty() {
        if ordered_nodes.is_empty() {
            return Err(PyIndexError::new_err(
                "Cannot choose from an empty sequence",
            ));
        }
        let first = random
            .call_method1("choice", (ordered_nodes.clone(),))?
            .extract::<String>()?;
        required.push(first);
    }

    let required_set: HashSet<&str> = required.iter().map(String::as_str).collect();
    for node in &required {
        if inner
            .neighbors(node)
            .unwrap_or_default()
            .into_iter()
            .any(|neighbor| required_set.contains(neighbor))
        {
            return Err(NetworkXUnfeasible::new_err(format!(
                "{initial_nodes:?} is not an independent set of G"
            )));
        }
    }

    let mut indep_nodes = required;
    let mut blocked: HashSet<String> = indep_nodes.iter().cloned().collect();
    for node in &indep_nodes {
        if let Some(neighbors) = inner.neighbors(node) {
            blocked.extend(neighbors.into_iter().map(str::to_owned));
        }
    }

    let mut available_nodes: Vec<String> = ordered_nodes
        .into_iter()
        .filter(|node| !blocked.contains(node))
        .collect();

    while !available_nodes.is_empty() {
        let chosen = random
            .call_method1("choice", (available_nodes.clone(),))?
            .extract::<String>()?;
        let index = available_nodes
            .iter()
            .position(|candidate| candidate == &chosen)
            .expect("choice must return an available node");
        available_nodes.remove(index);
        indep_nodes.push(chosen.clone());

        let mut banned = HashSet::from([chosen.clone()]);
        if let Some(neighbors) = inner.neighbors(&chosen) {
            banned.extend(neighbors.into_iter().map(str::to_owned));
        }
        available_nodes.retain(|candidate| !banned.contains(candidate));
    }

    Ok(indep_nodes
        .into_iter()
        .map(|node| gr.py_node_key(py, &node))
        .collect())
}

/// Maximal independent set (not maximum), optionally seeded.
#[pyfunction]
#[pyo3(signature = (g, nodes=None, seed=None))]
fn maximal_independent_set(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    nodes: Option<&Bound<'_, PyAny>>,
    seed: Option<u64>,
) -> PyResult<Vec<PyObject>> {
    let gr = extract_graph(g)?;
    require_undirected(&gr, "maximal_independent_set")?;
    let inner = gr.undirected();
    let initial_nodes = if let Some(items) = nodes {
        items
            .try_iter()?
            .map(|item| node_key_to_string(py, &item?))
            .collect::<PyResult<Vec<_>>>()?
    } else {
        Vec::new()
    };

    let random_module = py.import("random")?;
    if let Some(seed) = seed {
        let random = random_module.getattr("Random")?.call1((seed,))?;
        return maximal_independent_set_with_random(py, &gr, inner, &initial_nodes, &random);
    }

    maximal_independent_set_with_random(py, &gr, inner, &initial_nodes, random_module.as_any())
}

/// Greedy approximation for maximum independent set.
#[pyfunction]
#[pyo3(signature = (g,))]
fn maximum_independent_set(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<PyObject> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    let result = py.allow_threads(|| fnx_algorithms::maximum_independent_set(inner));
    let pyset = pyo3::types::PySet::new(
        py,
        result
            .iter()
            .map(|n| gr.py_node_key(py, n))
            .collect::<Vec<_>>(),
    )?;
    Ok(pyset.into_any().unbind())
}

/// Greedy approximation for maximum clique.
#[pyfunction]
#[pyo3(signature = (g,))]
fn max_clique(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<PyObject> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    let result = py.allow_threads(|| fnx_algorithms::max_clique_approx(inner));
    let pyset = pyo3::types::PySet::new(
        py,
        result
            .iter()
            .map(|n| gr.py_node_key(py, n))
            .collect::<Vec<_>>(),
    )?;
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
        iset.iter()
            .map(|n| gr.py_node_key(py, n))
            .collect::<Vec<_>>(),
    )?;
    let py_cliques: Vec<PyObject> = cliques
        .iter()
        .map(|clique| {
            pyo3::types::PySet::new(
                py,
                clique
                    .iter()
                    .map(|n| gr.py_node_key(py, n))
                    .collect::<Vec<_>>(),
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

/// Compute a graph spanner with the given stretch.
#[pyfunction]
#[pyo3(signature = (g, stretch, weight=None, seed=None))]
fn spanner(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    stretch: f64,
    weight: Option<&str>,
    seed: Option<u64>,
) -> PyResult<PyObject> {
    let gr = extract_graph(g)?;
    require_undirected(&gr, "spanner")?;
    let inner = gr.undirected();
    let result = py
        .allow_threads(|| fnx_algorithms::spanner(inner, stretch, weight, seed))
        .map_err(|err| match err {
            fnx_algorithms::SpannerError::InvalidStretch => PyValueError::new_err(err.to_string()),
        })?;
    rust_graph_to_py_with_source_edge_attrs(py, &result, &gr)
}

/// Fastest isomorphism pre-check (order + size only).
#[pyfunction]
#[pyo3(signature = (g1, g2))]
fn faster_could_be_isomorphic(
    py: Python<'_>,
    g1: &Bound<'_, PyAny>,
    g2: &Bound<'_, PyAny>,
) -> PyResult<bool> {
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

/// Check if a graph is chordal (every cycle of length 4+ has a chord).
#[pyfunction]
#[pyo3(signature = (g,))]
fn is_chordal(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<bool> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    Ok(py.allow_threads(|| fnx_algorithms::is_chordal(inner)))
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
// Tree recognition — is_arborescence, is_branching
// ===========================================================================

/// Return True if `G` is an arborescence (a directed rooted tree).
#[pyfunction]
#[pyo3(signature = (g,))]
fn is_arborescence(_py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<bool> {
    let gr = extract_graph(g)?;
    if !gr.is_directed() {
        return Ok(false);
    }
    {
        let dg_ref = gr.digraph().expect("is_directed checked above");
        Ok(fnx_algorithms::is_arborescence(dg_ref))
    }
}

/// Return True if `G` is a branching (a directed forest).
#[pyfunction]
#[pyo3(signature = (g,))]
fn is_branching(_py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<bool> {
    let gr = extract_graph(g)?;
    if !gr.is_directed() {
        return Ok(false);
    }
    {
        let dg_ref = gr.digraph().expect("is_directed checked above");
        Ok(fnx_algorithms::is_branching(dg_ref))
    }
}

// ===========================================================================
// Isolates — is_isolate, isolates, number_of_isolates
// ===========================================================================

/// Return True if `node` is an isolate (degree 0).
#[pyfunction]
#[pyo3(signature = (g, node))]
fn is_isolate(py: Python<'_>, g: &Bound<'_, PyAny>, node: &Bound<'_, PyAny>) -> PyResult<bool> {
    let gr = extract_graph(g)?;
    let key = node_key_to_string(py, node)?;
    validate_node(&gr, &key, node)?;
    match &gr {
        GraphRef::Undirected(pg) => Ok(fnx_algorithms::is_isolate(&pg.inner, &key)),
        GraphRef::Directed { dg, .. } => Ok(fnx_algorithms::is_isolate_directed(&dg.inner, &key)),
        _ => {
            if gr.is_directed() {
                Ok(fnx_algorithms::is_isolate_directed(
                    gr.digraph().unwrap(),
                    &key,
                ))
            } else {
                Ok(fnx_algorithms::is_isolate(gr.undirected(), &key))
            }
        }
    }
}

/// Return a list of isolate nodes.
#[pyfunction]
#[pyo3(signature = (g,))]
fn isolates(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<Vec<PyObject>> {
    let gr = extract_graph(g)?;
    let result = match &gr {
        GraphRef::Undirected(pg) => fnx_algorithms::isolates(&pg.inner),
        GraphRef::Directed { dg, .. } => fnx_algorithms::isolates_directed(&dg.inner),
        _ => {
            if gr.is_directed() {
                fnx_algorithms::isolates_directed(gr.digraph().unwrap())
            } else {
                fnx_algorithms::isolates(gr.undirected())
            }
        }
    };
    Ok(result.iter().map(|n| gr.py_node_key(py, n)).collect())
}

/// Return the number of isolate nodes.
#[pyfunction]
#[pyo3(signature = (g,))]
fn number_of_isolates(_py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<usize> {
    let gr = extract_graph(g)?;
    match &gr {
        GraphRef::Undirected(pg) => Ok(fnx_algorithms::number_of_isolates(&pg.inner)),
        GraphRef::Directed { dg, .. } => Ok(fnx_algorithms::number_of_isolates_directed(&dg.inner)),
        _ => {
            if gr.is_directed() {
                Ok(fnx_algorithms::number_of_isolates_directed(
                    gr.digraph().unwrap(),
                ))
            } else {
                Ok(fnx_algorithms::number_of_isolates(gr.undirected()))
            }
        }
    }
}

// ===========================================================================
// Boundary — edge_boundary, node_boundary
// ===========================================================================

/// Return the edges at the boundary of `nbunch1`.
#[pyfunction]
#[pyo3(signature = (g, nbunch1, nbunch2=None))]
fn edge_boundary(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    nbunch1: Vec<Bound<'_, PyAny>>,
    nbunch2: Option<Vec<Bound<'_, PyAny>>>,
) -> PyResult<Vec<(PyObject, PyObject)>> {
    let gr = extract_graph(g)?;
    let s1: Vec<String> = nbunch1
        .iter()
        .map(|n| node_key_to_string(py, n))
        .collect::<PyResult<_>>()?;
    let s2: Option<Vec<String>> = match nbunch2.as_ref() {
        Some(v) => Some(
            v.iter()
                .map(|n| node_key_to_string(py, n))
                .collect::<PyResult<_>>()?,
        ),
        None => None,
    };
    let s1_refs: Vec<&str> = s1.iter().map(|s| s.as_str()).collect();
    let s2_refs: Option<Vec<&str>> = s2.as_ref().map(|v| v.iter().map(|s| s.as_str()).collect());
    let result = match &gr {
        GraphRef::Undirected(pg) => {
            fnx_algorithms::edge_boundary(&pg.inner, &s1_refs, s2_refs.as_deref())
        }
        GraphRef::Directed { dg, .. } => {
            fnx_algorithms::edge_boundary_directed(&dg.inner, &s1_refs, s2_refs.as_deref())
        }
        _ => {
            if gr.is_directed() {
                fnx_algorithms::edge_boundary_directed(
                    gr.digraph().unwrap(),
                    &s1_refs,
                    s2_refs.as_deref(),
                )
            } else {
                fnx_algorithms::edge_boundary(gr.undirected(), &s1_refs, s2_refs.as_deref())
            }
        }
    };
    Ok(result
        .iter()
        .map(|(u, v)| (gr.py_node_key(py, u), gr.py_node_key(py, v)))
        .collect())
}

/// Return the nodes at the boundary of `nbunch1`.
#[pyfunction]
#[pyo3(signature = (g, nbunch1, nbunch2=None))]
fn node_boundary(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    nbunch1: Vec<Bound<'_, PyAny>>,
    nbunch2: Option<Vec<Bound<'_, PyAny>>>,
) -> PyResult<Vec<PyObject>> {
    let gr = extract_graph(g)?;
    let s1: Vec<String> = nbunch1
        .iter()
        .map(|n| node_key_to_string(py, n))
        .collect::<PyResult<_>>()?;
    let s2: Option<Vec<String>> = match nbunch2.as_ref() {
        Some(v) => Some(
            v.iter()
                .map(|n| node_key_to_string(py, n))
                .collect::<PyResult<_>>()?,
        ),
        None => None,
    };
    let s1_refs: Vec<&str> = s1.iter().map(|s| s.as_str()).collect();
    let s2_refs: Option<Vec<&str>> = s2.as_ref().map(|v| v.iter().map(|s| s.as_str()).collect());
    let result = match &gr {
        GraphRef::Undirected(pg) => {
            fnx_algorithms::node_boundary(&pg.inner, &s1_refs, s2_refs.as_deref())
        }
        GraphRef::Directed { dg, .. } => {
            fnx_algorithms::node_boundary_directed(&dg.inner, &s1_refs, s2_refs.as_deref())
        }
        _ => {
            if gr.is_directed() {
                fnx_algorithms::node_boundary_directed(
                    gr.digraph().unwrap(),
                    &s1_refs,
                    s2_refs.as_deref(),
                )
            } else {
                fnx_algorithms::node_boundary(gr.undirected(), &s1_refs, s2_refs.as_deref())
            }
        }
    };
    Ok(result.iter().map(|n| gr.py_node_key(py, n)).collect())
}

/// Return the size of the cut between `nbunch1` and `nbunch2`.
#[pyfunction]
#[pyo3(signature = (g, nbunch1, nbunch2=None, weight=None))]
fn cut_size(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    nbunch1: Vec<Bound<'_, PyAny>>,
    nbunch2: Option<Vec<Bound<'_, PyAny>>>,
    weight: Option<&str>,
) -> PyResult<f64> {
    let gr = extract_graph(g)?;
    let s1: Vec<String> = nbunch1
        .iter()
        .map(|n| node_key_to_string(py, n))
        .collect::<PyResult<_>>()?;
    let s2: Option<Vec<String>> = match nbunch2.as_ref() {
        Some(v) => Some(
            v.iter()
                .map(|n| node_key_to_string(py, n))
                .collect::<PyResult<_>>()?,
        ),
        None => None,
    };
    let s1_refs: Vec<&str> = s1.iter().map(|s| s.as_str()).collect();
    let s2_refs: Option<Vec<&str>> = s2.as_ref().map(|v| v.iter().map(|s| s.as_str()).collect());
    Ok(match &gr {
        GraphRef::Undirected(pg) => {
            fnx_algorithms::cut_size(&pg.inner, &s1_refs, s2_refs.as_deref(), weight)
        }
        GraphRef::Directed { dg, .. } => {
            fnx_algorithms::cut_size_directed(&dg.inner, &s1_refs, s2_refs.as_deref(), weight)
        }
        _ => {
            if gr.is_directed() {
                fnx_algorithms::cut_size_directed(
                    gr.digraph().unwrap(),
                    &s1_refs,
                    s2_refs.as_deref(),
                    weight,
                )
            } else {
                fnx_algorithms::cut_size(gr.undirected(), &s1_refs, s2_refs.as_deref(), weight)
            }
        }
    })
}

/// Return the normalized cut size between `nbunch1` and `nbunch2`.
#[pyfunction]
#[pyo3(signature = (g, nbunch1, nbunch2=None, weight=None))]
fn normalized_cut_size(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    nbunch1: Vec<Bound<'_, PyAny>>,
    nbunch2: Option<Vec<Bound<'_, PyAny>>>,
    weight: Option<&str>,
) -> PyResult<f64> {
    let gr = extract_graph(g)?;
    let s1: Vec<String> = nbunch1
        .iter()
        .map(|n| node_key_to_string(py, n))
        .collect::<PyResult<_>>()?;
    let s2: Option<Vec<String>> = match nbunch2.as_ref() {
        Some(v) => Some(
            v.iter()
                .map(|n| node_key_to_string(py, n))
                .collect::<PyResult<_>>()?,
        ),
        None => None,
    };
    let s1_refs: Vec<&str> = s1.iter().map(|s| s.as_str()).collect();
    let s2_refs: Option<Vec<&str>> = s2.as_ref().map(|v| v.iter().map(|s| s.as_str()).collect());
    let result = match &gr {
        GraphRef::Undirected(pg) => {
            fnx_algorithms::normalized_cut_size(&pg.inner, &s1_refs, s2_refs.as_deref(), weight)
        }
        GraphRef::Directed { dg, .. } => fnx_algorithms::normalized_cut_size_directed(
            &dg.inner,
            &s1_refs,
            s2_refs.as_deref(),
            weight,
        ),
        _ => {
            if gr.is_directed() {
                fnx_algorithms::normalized_cut_size_directed(
                    gr.digraph().unwrap(),
                    &s1_refs,
                    s2_refs.as_deref(),
                    weight,
                )
            } else {
                fnx_algorithms::normalized_cut_size(
                    gr.undirected(),
                    &s1_refs,
                    s2_refs.as_deref(),
                    weight,
                )
            }
        }
    };
    result.ok_or_else(|| PyZeroDivisionError::new_err("division by zero"))
}

// ===========================================================================
// is_simple_path
// ===========================================================================

/// Return True if `path` is a simple path in `G`.
#[pyfunction]
#[pyo3(signature = (g, path))]
fn is_simple_path(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    path: Vec<Bound<'_, PyAny>>,
) -> PyResult<bool> {
    let gr = extract_graph(g)?;
    let keys: Vec<String> = path
        .iter()
        .map(|n| node_key_to_string(py, n))
        .collect::<PyResult<_>>()?;
    let key_refs: Vec<&str> = keys.iter().map(|s| s.as_str()).collect();
    match &gr {
        GraphRef::Undirected(pg) => Ok(fnx_algorithms::is_simple_path(&pg.inner, &key_refs)),
        GraphRef::Directed { dg, .. } => Ok(fnx_algorithms::is_simple_path_directed(
            &dg.inner, &key_refs,
        )),
        _ => {
            if gr.is_directed() {
                Ok(fnx_algorithms::is_simple_path_directed(
                    gr.digraph().unwrap(),
                    &key_refs,
                ))
            } else {
                Ok(fnx_algorithms::is_simple_path(gr.undirected(), &key_refs))
            }
        }
    }
}

// ===========================================================================
// Matching validators — is_matching, is_maximal_matching, is_perfect_matching
// ===========================================================================

/// Return True if `matching` is a valid matching of `G`.
#[pyfunction]
#[pyo3(signature = (g, matching))]
fn is_matching(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    matching: Vec<(Bound<'_, PyAny>, Bound<'_, PyAny>)>,
) -> PyResult<bool> {
    let gr = extract_graph(g)?;
    require_undirected(&gr, "is_matching")?;
    let inner = gr.undirected();
    let edges: Vec<(String, String)> = matching
        .iter()
        .map(|(u, v)| Ok((node_key_to_string(py, u)?, node_key_to_string(py, v)?)))
        .collect::<PyResult<_>>()?;
    Ok(fnx_algorithms::is_matching(inner, &edges))
}

/// Return True if `matching` is a maximal matching of `G`.
#[pyfunction]
#[pyo3(signature = (g, matching))]
fn is_maximal_matching(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    matching: Vec<(Bound<'_, PyAny>, Bound<'_, PyAny>)>,
) -> PyResult<bool> {
    let gr = extract_graph(g)?;
    require_undirected(&gr, "is_maximal_matching")?;
    let inner = gr.undirected();
    let edges: Vec<(String, String)> = matching
        .iter()
        .map(|(u, v)| Ok((node_key_to_string(py, u)?, node_key_to_string(py, v)?)))
        .collect::<PyResult<_>>()?;
    Ok(fnx_algorithms::is_maximal_matching(inner, &edges))
}

/// Return True if `matching` is a perfect matching of `G`.
#[pyfunction]
#[pyo3(signature = (g, matching))]
fn is_perfect_matching(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    matching: Vec<(Bound<'_, PyAny>, Bound<'_, PyAny>)>,
) -> PyResult<bool> {
    let gr = extract_graph(g)?;
    require_undirected(&gr, "is_perfect_matching")?;
    let inner = gr.undirected();
    let edges: Vec<(String, String)> = matching
        .iter()
        .map(|(u, v)| Ok((node_key_to_string(py, u)?, node_key_to_string(py, v)?)))
        .collect::<PyResult<_>>()?;
    Ok(fnx_algorithms::is_perfect_matching(inner, &edges))
}

// ===========================================================================
// simple_cycles, find_cycle
// ===========================================================================

/// Find simple cycles (elementary circuits) of a directed graph.
#[pyfunction]
#[pyo3(signature = (g,))]
fn simple_cycles(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<Vec<Vec<PyObject>>> {
    let gr = extract_graph(g)?;
    if !gr.is_directed() {
        return Err(NetworkXError::new_err(
            "simple_cycles is not defined for undirected graphs. Use cycle_basis instead.",
        ));
    }
    {
        let dg_ref = gr.digraph().expect("is_directed checked above");
        let result = fnx_algorithms::simple_cycles(dg_ref);
        Ok(result
            .into_iter()
            .map(|cycle| cycle.iter().map(|n| gr.py_node_key(py, n)).collect())
            .collect())
    }
}

/// Find a cycle in the graph. Returns a list of nodes forming the cycle,
/// or raises ``NetworkXNoCycle`` if no cycle exists.
#[pyfunction]
#[pyo3(signature = (g,))]
fn find_cycle(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<Vec<(PyObject, PyObject)>> {
    let gr = extract_graph(g)?;
    let result = match &gr {
        GraphRef::Undirected(pg) => fnx_algorithms::find_cycle_undirected(&pg.inner),
        GraphRef::Directed { dg, .. } => fnx_algorithms::find_cycle_directed(&dg.inner),
        _ => {
            if gr.is_directed() {
                fnx_algorithms::find_cycle_directed(gr.digraph().unwrap())
            } else {
                fnx_algorithms::find_cycle_undirected(gr.undirected())
            }
        }
    };
    match result {
        Some(cycle) => {
            // Return as edge list from consecutive node pairs
            let mut edges = Vec::new();
            for w in cycle.windows(2) {
                edges.push((gr.py_node_key(py, &w[0]), gr.py_node_key(py, &w[1])));
            }
            Ok(edges)
        }
        None => Err(NetworkXNoCycle::new_err("No cycle found.")),
    }
}

// ===========================================================================
// Additional shortest path bindings
// ===========================================================================

/// Return the shortest path length from source to target using Dijkstra.
#[pyfunction]
#[pyo3(signature = (g, source, target, weight="weight"))]
fn dijkstra_path_length(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    source: &Bound<'_, PyAny>,
    target: &Bound<'_, PyAny>,
    weight: &str,
) -> PyResult<f64> {
    let gr = extract_graph(g)?;
    let s = node_key_to_string(py, source)?;
    let t = node_key_to_string(py, target)?;
    validate_node(&gr, &s, source)?;
    validate_node(&gr, &t, target)?;
    let result = if let Some(weighted_projection) = gr.weighted_digraph_projection(weight) {
        fnx_algorithms::dijkstra_path_length_directed(weighted_projection.as_ref(), &s, &t, weight)
    } else {
        let weighted_projection = gr.weighted_undirected_projection(weight);
        fnx_algorithms::dijkstra_path_length(weighted_projection.as_ref(), &s, &t, weight)
    };
    match result {
        Some(d) => Ok(d),
        None => Err(NetworkXNoPath::new_err(format!(
            "No path between {} and {}.",
            s, t
        ))),
    }
}

/// Return the shortest path length from source to target using Bellman-Ford.
#[pyfunction]
#[pyo3(signature = (g, source, target, weight="weight"))]
fn bellman_ford_path_length(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    source: &Bound<'_, PyAny>,
    target: &Bound<'_, PyAny>,
    weight: &str,
) -> PyResult<f64> {
    let gr = extract_graph(g)?;
    let s = node_key_to_string(py, source)?;
    let t = node_key_to_string(py, target)?;
    validate_node(&gr, &s, source)?;
    validate_node(&gr, &t, target)?;
    let result = if let Some(weighted_projection) = gr.weighted_digraph_projection(weight) {
        let bf = fnx_algorithms::bellman_ford_shortest_paths_directed(
            weighted_projection.as_ref(),
            &s,
            weight,
        );
        if bf.negative_cycle_detected {
            Err(true)
        } else {
            bf.distances
                .iter()
                .find(|entry| entry.node == t)
                .map(|entry| entry.distance)
                .ok_or(false)
        }
    } else {
        let weighted_projection = gr.weighted_undirected_projection(weight);
        fnx_algorithms::bellman_ford_path_length(weighted_projection.as_ref(), &s, &t, weight)
    };
    match result {
        Ok(d) => Ok(d),
        Err(true) => Err(crate::NetworkXUnbounded::new_err(
            "Negative cost cycle detected.",
        )),
        Err(false) => Err(NetworkXNoPath::new_err(format!(
            "No path between {} and {}.",
            s, t
        ))),
    }
}

/// Return (distances, paths) from a single source using Dijkstra.
#[pyfunction]
#[pyo3(signature = (g, source, weight="weight"))]
fn single_source_dijkstra(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    source: &Bound<'_, PyAny>,
    weight: &str,
) -> PyResult<(PyObject, PyObject)> {
    let gr = extract_graph(g)?;
    require_undirected(&gr, "single_source_dijkstra")?;
    let s = node_key_to_string(py, source)?;
    validate_node_str(&gr, &s)?;
    let weighted_projection = gr.weighted_undirected_projection(weight);
    let (dists, paths) =
        fnx_algorithms::single_source_dijkstra_full(weighted_projection.as_ref(), &s, weight);
    let dist_dict = PyDict::new(py);
    for (node, d) in &dists {
        dist_dict.set_item(gr.py_node_key(py, node), d)?;
    }
    let path_dict = PyDict::new(py);
    for (node, path) in &paths {
        let py_path: Vec<PyObject> = path.iter().map(|n| gr.py_node_key(py, n)).collect();
        path_dict.set_item(gr.py_node_key(py, node), py_path)?;
    }
    Ok((dist_dict.into_any().unbind(), path_dict.into_any().unbind()))
}

/// Return paths from a single source using Dijkstra.
#[pyfunction]
#[pyo3(signature = (g, source, weight="weight"))]
fn single_source_dijkstra_path(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    source: &Bound<'_, PyAny>,
    weight: &str,
) -> PyResult<PyObject> {
    let gr = extract_graph(g)?;
    require_undirected(&gr, "single_source_dijkstra_path")?;
    let s = node_key_to_string(py, source)?;
    validate_node_str(&gr, &s)?;
    let weighted_projection = gr.weighted_undirected_projection(weight);
    let paths =
        fnx_algorithms::single_source_dijkstra_path(weighted_projection.as_ref(), &s, weight);
    let dict = PyDict::new(py);
    for (node, path) in &paths {
        let py_path: Vec<PyObject> = path.iter().map(|n| gr.py_node_key(py, n)).collect();
        dict.set_item(gr.py_node_key(py, node), py_path)?;
    }
    Ok(dict.into_any().unbind())
}

/// Return distances from a single source using Dijkstra.
#[pyfunction]
#[pyo3(signature = (g, source, weight="weight"))]
fn single_source_dijkstra_path_length(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    source: &Bound<'_, PyAny>,
    weight: &str,
) -> PyResult<PyObject> {
    let gr = extract_graph(g)?;
    require_undirected(&gr, "single_source_dijkstra_path_length")?;
    let s = node_key_to_string(py, source)?;
    validate_node_str(&gr, &s)?;
    let weighted_projection = gr.weighted_undirected_projection(weight);
    let dists = fnx_algorithms::single_source_dijkstra_path_length(
        weighted_projection.as_ref(),
        &s,
        weight,
    );
    let dict = PyDict::new(py);
    for (node, d) in &dists {
        dict.set_item(gr.py_node_key(py, node), d)?;
    }
    Ok(dict.into_any().unbind())
}

/// Return (distances, paths) from a single source using Bellman-Ford.
#[pyfunction]
#[pyo3(signature = (g, source, weight="weight"))]
fn single_source_bellman_ford(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    source: &Bound<'_, PyAny>,
    weight: &str,
) -> PyResult<(PyObject, PyObject)> {
    let gr = extract_graph(g)?;
    require_undirected(&gr, "single_source_bellman_ford")?;
    let s = node_key_to_string(py, source)?;
    validate_node_str(&gr, &s)?;
    let weighted_projection = gr.weighted_undirected_projection(weight);
    let result =
        fnx_algorithms::single_source_bellman_ford(weighted_projection.as_ref(), &s, weight);
    match result {
        Some((dists, paths)) => {
            let dist_dict = PyDict::new(py);
            for (node, d) in &dists {
                dist_dict.set_item(gr.py_node_key(py, node), d)?;
            }
            let path_dict = PyDict::new(py);
            for (node, path) in &paths {
                let py_path: Vec<PyObject> = path.iter().map(|n| gr.py_node_key(py, n)).collect();
                path_dict.set_item(gr.py_node_key(py, node), py_path)?;
            }
            Ok((dist_dict.into_any().unbind(), path_dict.into_any().unbind()))
        }
        None => Err(crate::NetworkXUnbounded::new_err(
            "Negative cost cycle detected.",
        )),
    }
}

/// Return paths from a single source using Bellman-Ford.
#[pyfunction]
#[pyo3(signature = (g, source, weight="weight"))]
fn single_source_bellman_ford_path(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    source: &Bound<'_, PyAny>,
    weight: &str,
) -> PyResult<PyObject> {
    let gr = extract_graph(g)?;
    require_undirected(&gr, "single_source_bellman_ford_path")?;
    let s = node_key_to_string(py, source)?;
    validate_node_str(&gr, &s)?;
    let weighted_projection = gr.weighted_undirected_projection(weight);
    let result =
        fnx_algorithms::single_source_bellman_ford_path(weighted_projection.as_ref(), &s, weight);
    match result {
        Some(paths) => {
            let dict = PyDict::new(py);
            for (node, path) in &paths {
                let py_path: Vec<PyObject> = path.iter().map(|n| gr.py_node_key(py, n)).collect();
                dict.set_item(gr.py_node_key(py, node), py_path)?;
            }
            Ok(dict.into_any().unbind())
        }
        None => Err(crate::NetworkXUnbounded::new_err(
            "Negative cost cycle detected.",
        )),
    }
}

/// Return distances from a single source using Bellman-Ford.
#[pyfunction]
#[pyo3(signature = (g, source, weight="weight"))]
fn single_source_bellman_ford_path_length(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    source: &Bound<'_, PyAny>,
    weight: &str,
) -> PyResult<PyObject> {
    let gr = extract_graph(g)?;
    require_undirected(&gr, "single_source_bellman_ford_path_length")?;
    let s = node_key_to_string(py, source)?;
    validate_node_str(&gr, &s)?;
    let weighted_projection = gr.weighted_undirected_projection(weight);
    let result = fnx_algorithms::single_source_bellman_ford_path_length(
        weighted_projection.as_ref(),
        &s,
        weight,
    );
    match result {
        Some(dists) => {
            let dict = PyDict::new(py);
            for (node, d) in &dists {
                dict.set_item(gr.py_node_key(py, node), d)?;
            }
            Ok(dict.into_any().unbind())
        }
        None => Err(crate::NetworkXUnbounded::new_err(
            "Negative cost cycle detected.",
        )),
    }
}

/// Return shortest paths from all nodes to a single target (unweighted BFS).
#[pyfunction]
#[pyo3(signature = (g, target, cutoff=None))]
fn single_target_shortest_path(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    target: &Bound<'_, PyAny>,
    cutoff: Option<usize>,
) -> PyResult<PyObject> {
    let gr = extract_graph(g)?;
    require_undirected(&gr, "single_target_shortest_path")?;
    let t = node_key_to_string(py, target)?;
    validate_node_str(&gr, &t)?;
    let result = fnx_algorithms::single_target_shortest_path(gr.undirected(), &t, cutoff);
    let dict = PyDict::new(py);
    for (node, path) in &result {
        let py_path: Vec<PyObject> = path.iter().map(|n| gr.py_node_key(py, n)).collect();
        dict.set_item(gr.py_node_key(py, node), py_path)?;
    }
    Ok(dict.into_any().unbind())
}

/// Return shortest path lengths from all nodes to a single target (unweighted BFS).
#[pyfunction]
#[pyo3(signature = (g, target, cutoff=None))]
fn single_target_shortest_path_length(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    target: &Bound<'_, PyAny>,
    cutoff: Option<usize>,
) -> PyResult<PyObject> {
    let gr = extract_graph(g)?;
    require_undirected(&gr, "single_target_shortest_path_length")?;
    let t = node_key_to_string(py, target)?;
    validate_node_str(&gr, &t)?;
    let result = fnx_algorithms::single_target_shortest_path_length(gr.undirected(), &t, cutoff);
    let dict = PyDict::new(py);
    for (node, length) in &result {
        dict.set_item(gr.py_node_key(py, node), *length)?;
    }
    Ok(dict.into_any().unbind())
}

/// Return all-pairs shortest path distances using Dijkstra.
#[pyfunction]
#[pyo3(signature = (g, weight="weight"))]
fn all_pairs_dijkstra_path_length(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    weight: &str,
) -> PyResult<PyObject> {
    let gr = extract_graph(g)?;
    let result = if gr.is_directed() {
        let dg = gr
            .weighted_digraph_projection(weight)
            .expect("is_directed checked above");
        py.allow_threads(|| {
            fnx_algorithms::all_pairs_dijkstra_directed(dg.as_ref(), weight)
                .into_iter()
                .map(|(source, (dists, _paths))| (source, dists))
                .collect::<HashMap<_, _>>()
        })
    } else {
        let weighted_projection = gr.weighted_undirected_projection(weight);
        py.allow_threads(|| {
            fnx_algorithms::all_pairs_dijkstra_path_length(weighted_projection.as_ref(), weight)
        })
    };
    let outer_dict = PyDict::new(py);
    for (source, targets) in &result {
        let inner_dict = PyDict::new(py);
        for (target, d) in targets {
            inner_dict.set_item(gr.py_node_key(py, target), d)?;
        }
        outer_dict.set_item(gr.py_node_key(py, source), inner_dict)?;
    }
    Ok(outer_dict.into_any().unbind())
}

/// Return all-pairs shortest paths using Dijkstra.
#[pyfunction]
#[pyo3(signature = (g, weight="weight"))]
fn all_pairs_dijkstra_path(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    weight: &str,
) -> PyResult<PyObject> {
    let gr = extract_graph(g)?;
    let result = if gr.is_directed() {
        let dg = gr
            .weighted_digraph_projection(weight)
            .expect("is_directed checked above");
        py.allow_threads(|| {
            fnx_algorithms::all_pairs_dijkstra_directed(dg.as_ref(), weight)
                .into_iter()
                .map(|(source, (_dists, paths))| (source, paths))
                .collect::<HashMap<_, _>>()
        })
    } else {
        let weighted_projection = gr.weighted_undirected_projection(weight);
        py.allow_threads(|| {
            fnx_algorithms::all_pairs_dijkstra_path(weighted_projection.as_ref(), weight)
        })
    };
    let outer_dict = PyDict::new(py);
    for (source, targets) in &result {
        let inner_dict = PyDict::new(py);
        for (target, path) in targets {
            let py_path: Vec<PyObject> = path.iter().map(|n| gr.py_node_key(py, n)).collect();
            inner_dict.set_item(gr.py_node_key(py, target), py_path)?;
        }
        outer_dict.set_item(gr.py_node_key(py, source), inner_dict)?;
    }
    Ok(outer_dict.into_any().unbind())
}

/// Return all-pairs shortest path distances using Bellman-Ford.
#[pyfunction]
#[pyo3(signature = (g, weight="weight"))]
fn all_pairs_bellman_ford_path_length(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    weight: &str,
) -> PyResult<PyObject> {
    let gr = extract_graph(g)?;
    require_undirected(&gr, "all_pairs_bellman_ford_path_length")?;
    let weighted_projection = gr.weighted_undirected_projection(weight);
    let result = py.allow_threads(|| {
        fnx_algorithms::all_pairs_bellman_ford_path_length(weighted_projection.as_ref(), weight)
    });
    match result {
        Some(data) => {
            let outer_dict = PyDict::new(py);
            for (source, targets) in &data {
                let inner_dict = PyDict::new(py);
                for (target, d) in targets {
                    inner_dict.set_item(gr.py_node_key(py, target), d)?;
                }
                outer_dict.set_item(gr.py_node_key(py, source), inner_dict)?;
            }
            Ok(outer_dict.into_any().unbind())
        }
        None => Err(crate::NetworkXUnbounded::new_err(
            "Negative cost cycle detected.",
        )),
    }
}

/// Return all-pairs shortest paths using Bellman-Ford.
#[pyfunction]
#[pyo3(signature = (g, weight="weight"))]
fn all_pairs_bellman_ford_path(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    weight: &str,
) -> PyResult<PyObject> {
    let gr = extract_graph(g)?;
    require_undirected(&gr, "all_pairs_bellman_ford_path")?;
    let weighted_projection = gr.weighted_undirected_projection(weight);
    let result = py.allow_threads(|| {
        fnx_algorithms::all_pairs_bellman_ford_path(weighted_projection.as_ref(), weight)
    });
    match result {
        Some(data) => {
            let outer_dict = PyDict::new(py);
            for (source, targets) in &data {
                let inner_dict = PyDict::new(py);
                for (target, path) in targets {
                    let py_path: Vec<PyObject> =
                        path.iter().map(|n| gr.py_node_key(py, n)).collect();
                    inner_dict.set_item(gr.py_node_key(py, target), py_path)?;
                }
                outer_dict.set_item(gr.py_node_key(py, source), inner_dict)?;
            }
            Ok(outer_dict.into_any().unbind())
        }
        None => Err(crate::NetworkXUnbounded::new_err(
            "Negative cost cycle detected.",
        )),
    }
}

/// Return Floyd-Warshall all-pairs shortest path distances.
#[pyfunction]
#[pyo3(signature = (g, weight="weight"))]
fn floyd_warshall(py: Python<'_>, g: &Bound<'_, PyAny>, weight: &str) -> PyResult<PyObject> {
    let gr = extract_graph(g)?;
    require_undirected(&gr, "floyd_warshall")?;
    let weighted_projection = gr.weighted_undirected_projection(weight);
    let result =
        py.allow_threads(|| fnx_algorithms::floyd_warshall(weighted_projection.as_ref(), weight));
    let outer_dict = PyDict::new(py);
    for (source, targets) in &result {
        let inner_dict = PyDict::new(py);
        for (target, d) in targets {
            inner_dict.set_item(gr.py_node_key(py, target), d)?;
        }
        outer_dict.set_item(gr.py_node_key(py, source), inner_dict)?;
    }
    Ok(outer_dict.into_any().unbind())
}

/// Return Floyd-Warshall predecessors and distances.
#[pyfunction]
#[pyo3(signature = (g, weight="weight"))]
fn floyd_warshall_predecessor_and_distance(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    weight: &str,
) -> PyResult<(PyObject, PyObject)> {
    let gr = extract_graph(g)?;
    require_undirected(&gr, "floyd_warshall_predecessor_and_distance")?;
    let weighted_projection = gr.weighted_undirected_projection(weight);
    let (dists, preds) = py.allow_threads(|| {
        fnx_algorithms::floyd_warshall_predecessor_and_distance(
            weighted_projection.as_ref(),
            weight,
        )
    });
    let dist_outer = PyDict::new(py);
    for (source, targets) in &dists {
        let inner_dict = PyDict::new(py);
        for (target, d) in targets {
            inner_dict.set_item(gr.py_node_key(py, target), d)?;
        }
        dist_outer.set_item(gr.py_node_key(py, source), inner_dict)?;
    }
    let pred_outer = PyDict::new(py);
    for (source, targets) in &preds {
        let inner_dict = PyDict::new(py);
        for (target, pred_list) in targets {
            if let Some(predecessor) = pred_list.first() {
                inner_dict.set_item(gr.py_node_key(py, target), gr.py_node_key(py, predecessor))?;
            }
        }
        pred_outer.set_item(gr.py_node_key(py, source), inner_dict)?;
    }
    Ok((
        pred_outer.into_any().unbind(),
        dist_outer.into_any().unbind(),
    ))
}

/// Return shortest path between source and target using bidirectional BFS.
#[pyfunction]
#[pyo3(signature = (g, source, target))]
fn bidirectional_shortest_path(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    source: &Bound<'_, PyAny>,
    target: &Bound<'_, PyAny>,
) -> PyResult<Vec<PyObject>> {
    let gr = extract_graph(g)?;
    require_undirected(&gr, "bidirectional_shortest_path")?;
    let s = node_key_to_string(py, source)?;
    let t = node_key_to_string(py, target)?;
    validate_node(&gr, &s, source)?;
    validate_node(&gr, &t, target)?;
    let result = fnx_algorithms::bidirectional_shortest_path(gr.undirected(), &s, &t);
    match result {
        Some(path) => Ok(path.iter().map(|n| gr.py_node_key(py, n)).collect()),
        None => Err(NetworkXNoPath::new_err(format!(
            "No path between {} and {}.",
            s, t
        ))),
    }
}

/// Return True if a negative edge cycle exists in the graph.
#[pyfunction]
#[pyo3(signature = (g, weight="weight"))]
fn negative_edge_cycle(py: Python<'_>, g: &Bound<'_, PyAny>, weight: &str) -> PyResult<bool> {
    let gr = extract_graph(g)?;
    require_undirected(&gr, "negative_edge_cycle")?;
    let weighted_projection = gr.weighted_undirected_projection(weight);
    Ok(py.allow_threads(|| {
        fnx_algorithms::negative_edge_cycle(weighted_projection.as_ref(), weight)
    }))
}

/// Return the predecessor dictionary from BFS.
#[pyfunction]
#[pyo3(name = "predecessor", signature = (g, source, cutoff=None))]
fn predecessor_fn(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    source: &Bound<'_, PyAny>,
    cutoff: Option<usize>,
) -> PyResult<PyObject> {
    let gr = extract_graph(g)?;
    require_undirected(&gr, "predecessor")?;
    let s = node_key_to_string(py, source)?;
    validate_node_str(&gr, &s)?;
    let result = fnx_algorithms::predecessor(gr.undirected(), &s, cutoff);
    let dict = PyDict::new(py);
    for (node, preds) in &result {
        let py_preds: Vec<PyObject> = preds.iter().map(|n| gr.py_node_key(py, n)).collect();
        dict.set_item(gr.py_node_key(py, node), py_preds)?;
    }
    Ok(dict.into_any().unbind())
}

/// Return the weight of a path given edge weights.
#[pyfunction]
#[pyo3(signature = (g, path, weight="weight"))]
fn path_weight(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    path: Vec<Bound<'_, PyAny>>,
    weight: &str,
) -> PyResult<f64> {
    let gr = extract_graph(g)?;
    let path_strs: Vec<String> = path
        .iter()
        .map(|n| node_key_to_string(py, n))
        .collect::<PyResult<_>>()?;
    let path_refs: Vec<&str> = path_strs.iter().map(String::as_str).collect();
    let result = match &gr {
        GraphRef::Undirected(pg) => fnx_algorithms::path_weight(&pg.inner, &path_refs, weight),
        GraphRef::Directed { dg, .. } => {
            fnx_algorithms::path_weight_directed(&dg.inner, &path_refs, weight)
        }
        GraphRef::MultiUndirected { .. } => {
            let weighted_projection = gr.weighted_undirected_projection(weight);
            fnx_algorithms::path_weight(weighted_projection.as_ref(), &path_refs, weight)
        }
        GraphRef::MultiDirected { .. } => {
            let weighted_projection = gr
                .weighted_digraph_projection(weight)
                .expect("multidigraph");
            fnx_algorithms::path_weight_directed(weighted_projection.as_ref(), &path_refs, weight)
        }
    };
    match result {
        Some(w) => Ok(w),
        None => Err(NetworkXNoPath::new_err("path contains edges not in graph")),
    }
}

// ===========================================================================
// Additional centrality algorithms
// ===========================================================================

/// Return the in-degree centrality for directed graph nodes.
#[pyfunction]
pub fn in_degree_centrality(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<Py<PyDict>> {
    let gr = extract_graph(g)?;
    if !gr.is_directed() {
        return Err(crate::NetworkXNotImplemented::new_err(
            "in_degree_centrality is not defined for undirected graphs.",
        ));
    }
    {
        let dg_ref = gr.digraph().expect("is_directed checked above");
        let scores = fnx_algorithms::in_degree_centrality(dg_ref);
        centrality_to_dict(py, &gr, &scores)
    }
}

/// Return the out-degree centrality for directed graph nodes.
#[pyfunction]
pub fn out_degree_centrality(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<Py<PyDict>> {
    let gr = extract_graph(g)?;
    if !gr.is_directed() {
        return Err(crate::NetworkXNotImplemented::new_err(
            "out_degree_centrality is not defined for undirected graphs.",
        ));
    }
    {
        let dg_ref = gr.digraph().expect("is_directed checked above");
        let scores = fnx_algorithms::out_degree_centrality(dg_ref);
        centrality_to_dict(py, &gr, &scores)
    }
}

/// Return the local reaching centrality of a node.
#[pyfunction]
pub fn local_reaching_centrality(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    v: &Bound<'_, PyAny>,
) -> PyResult<f64> {
    let gr = extract_graph(g)?;
    let node = node_key_to_string(py, v)?;
    validate_node(&gr, &node, v)?;
    match &gr {
        GraphRef::Undirected(pg) => Ok(fnx_algorithms::local_reaching_centrality(&pg.inner, &node)),
        GraphRef::Directed { dg, .. } => Ok(fnx_algorithms::local_reaching_centrality_directed(
            &dg.inner, &node,
        )),
        _ => {
            if gr.is_directed() {
                Ok(fnx_algorithms::local_reaching_centrality_directed(
                    gr.digraph().unwrap(),
                    &node,
                ))
            } else {
                Ok(fnx_algorithms::local_reaching_centrality(
                    gr.undirected(),
                    &node,
                ))
            }
        }
    }
}

/// Return the global reaching centrality.
#[pyfunction]
pub fn global_reaching_centrality(_py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<f64> {
    let gr = extract_graph(g)?;
    match &gr {
        GraphRef::Undirected(pg) => Ok(fnx_algorithms::global_reaching_centrality(&pg.inner)),
        GraphRef::Directed { dg, .. } => Ok(fnx_algorithms::global_reaching_centrality_directed(
            &dg.inner,
        )),
        _ => {
            if gr.is_directed() {
                Ok(fnx_algorithms::global_reaching_centrality_directed(
                    gr.digraph().unwrap(),
                ))
            } else {
                Ok(fnx_algorithms::global_reaching_centrality(gr.undirected()))
            }
        }
    }
}

/// Return the group degree centrality for a group of nodes.
#[pyfunction]
pub fn group_degree_centrality(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    s: &Bound<'_, PyAny>,
) -> PyResult<f64> {
    let gr = extract_graph(g)?;
    require_undirected(&gr, "group_degree_centrality")?;
    let inner = gr.undirected();
    let group_iter = s.try_iter()?;
    let group_strings: Vec<String> = group_iter
        .map(|item| node_key_to_string(py, &item?))
        .collect::<PyResult<Vec<String>>>()?;
    let group_refs: Vec<&str> = group_strings.iter().map(|s| s.as_str()).collect();
    Ok(fnx_algorithms::group_degree_centrality(inner, &group_refs))
}

/// Return the group in-degree centrality.
#[pyfunction]
pub fn group_in_degree_centrality(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    s: &Bound<'_, PyAny>,
) -> PyResult<f64> {
    let gr = extract_graph(g)?;
    if !gr.is_directed() {
        return Err(crate::NetworkXNotImplemented::new_err(
            "group_in_degree_centrality is not defined for undirected graphs.",
        ));
    }
    {
        let dg_ref = gr.digraph().expect("is_directed checked above");
        let group_iter = s.try_iter()?;
        let group_strings: Vec<String> = group_iter
            .map(|item| node_key_to_string(py, &item?))
            .collect::<PyResult<Vec<String>>>()?;
        let group_refs: Vec<&str> = group_strings.iter().map(|s| s.as_str()).collect();
        Ok(fnx_algorithms::group_in_degree_centrality(
            dg_ref,
            &group_refs,
        ))
    }
}

/// Return the group out-degree centrality.
#[pyfunction]
pub fn group_out_degree_centrality(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    s: &Bound<'_, PyAny>,
) -> PyResult<f64> {
    let gr = extract_graph(g)?;
    if !gr.is_directed() {
        return Err(crate::NetworkXNotImplemented::new_err(
            "group_out_degree_centrality is not defined for undirected graphs.",
        ));
    }
    {
        let dg_ref = gr.digraph().expect("is_directed checked above");
        let group_iter = s.try_iter()?;
        let group_strings: Vec<String> = group_iter
            .map(|item| node_key_to_string(py, &item?))
            .collect::<PyResult<Vec<String>>>()?;
        let group_refs: Vec<&str> = group_strings.iter().map(|s| s.as_str()).collect();
        Ok(fnx_algorithms::group_out_degree_centrality(
            dg_ref,
            &group_refs,
        ))
    }
}

// ===========================================================================
// Component algorithms
// ===========================================================================

/// Return the connected component containing the given node.
#[pyfunction]
pub fn node_connected_component(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    n: &Bound<'_, PyAny>,
) -> PyResult<Vec<PyObject>> {
    let gr = extract_graph(g)?;
    require_undirected(&gr, "node_connected_component")?;
    let inner = gr.undirected();
    let node = node_key_to_string(py, n)?;
    validate_node(&gr, &node, n)?;
    let result = py.allow_threads(|| fnx_algorithms::node_connected_component(inner, &node));
    Ok(result.iter().map(|s| gr.py_node_key(py, s)).collect())
}

/// Return True if the graph is biconnected.
#[pyfunction]
pub fn is_biconnected(_py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<bool> {
    let gr = extract_graph(g)?;
    require_undirected(&gr, "is_biconnected")?;
    let inner = gr.undirected();
    Ok(fnx_algorithms::is_biconnected(inner))
}

/// Return the biconnected components of the graph.
#[pyfunction]
pub fn biconnected_components(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<Vec<PyObject>> {
    let gr = extract_graph(g)?;
    require_undirected(&gr, "biconnected_components")?;
    let inner = gr.undirected();
    let result = py.allow_threads(|| fnx_algorithms::biconnected_components(inner));
    result
        .iter()
        .map(|comp| {
            let py_set: Vec<PyObject> = comp.iter().map(|n| gr.py_node_key(py, n)).collect();
            py_set.into_pyobject(py).map(|obj| obj.into_any().unbind())
        })
        .collect()
}

/// Return the biconnected component edges.
#[pyfunction]
pub fn biconnected_component_edges(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
) -> PyResult<Vec<Vec<(PyObject, PyObject)>>> {
    let gr = extract_graph(g)?;
    require_undirected(&gr, "biconnected_component_edges")?;
    let inner = gr.undirected();
    let result = py.allow_threads(|| fnx_algorithms::biconnected_component_edges(inner));
    Ok(result
        .iter()
        .map(|comp| {
            comp.iter()
                .map(|(u, v)| (gr.py_node_key(py, u), gr.py_node_key(py, v)))
                .collect()
        })
        .collect())
}

/// Return True if the directed graph is semiconnected.
#[pyfunction]
pub fn is_semiconnected(_py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<bool> {
    let gr = extract_graph(g)?;
    if !gr.is_directed() {
        return Err(crate::NetworkXNotImplemented::new_err(
            "is_semiconnected is not defined for undirected graphs.",
        ));
    }
    {
        let dg_ref = gr.digraph().expect("is_directed checked above");
        Ok(fnx_algorithms::is_semiconnected(dg_ref))
    }
}

/// Return the SCCs using Kosaraju's algorithm.
#[pyfunction]
pub fn kosaraju_strongly_connected_components(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
) -> PyResult<Vec<PyObject>> {
    let gr = extract_graph(g)?;
    if !gr.is_directed() {
        return Err(crate::NetworkXNotImplemented::new_err(
            "kosaraju_strongly_connected_components is not defined for undirected graphs.",
        ));
    }
    {
        let dg_ref = gr.digraph().expect("is_directed checked above");
        let result = fnx_algorithms::kosaraju_strongly_connected_components(dg_ref);
        result
            .iter()
            .map(|comp| {
                let py_set: Vec<PyObject> = comp.iter().map(|n| gr.py_node_key(py, n)).collect();
                py_set.into_pyobject(py).map(|obj| obj.into_any().unbind())
            })
            .collect()
    }
}

/// Return the attracting components of a directed graph.
#[pyfunction]
pub fn attracting_components(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<Vec<PyObject>> {
    let gr = extract_graph(g)?;
    if !gr.is_directed() {
        return Err(crate::NetworkXNotImplemented::new_err(
            "attracting_components is not defined for undirected graphs.",
        ));
    }
    {
        let dg_ref = gr.digraph().expect("is_directed checked above");
        let result = fnx_algorithms::attracting_components(dg_ref);
        result
            .iter()
            .map(|comp| {
                let py_set: Vec<PyObject> = comp.iter().map(|n| gr.py_node_key(py, n)).collect();
                py_set.into_pyobject(py).map(|obj| obj.into_any().unbind())
            })
            .collect()
    }
}

/// Return the number of attracting components.
#[pyfunction]
pub fn number_attracting_components(_py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<usize> {
    let gr = extract_graph(g)?;
    if !gr.is_directed() {
        return Err(crate::NetworkXNotImplemented::new_err(
            "number_attracting_components is not defined for undirected graphs.",
        ));
    }
    {
        let dg_ref = gr.digraph().expect("is_directed checked above");
        Ok(fnx_algorithms::number_attracting_components(dg_ref))
    }
}

/// Return True if the given component is an attracting component.
#[pyfunction]
pub fn is_attracting_component(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    component: &Bound<'_, PyAny>,
) -> PyResult<bool> {
    let gr = extract_graph(g)?;
    if !gr.is_directed() {
        return Err(crate::NetworkXNotImplemented::new_err(
            "is_attracting_component is not defined for undirected graphs.",
        ));
    }
    {
        let dg_ref = gr.digraph().expect("is_directed checked above");
        let comp_iter = component.try_iter()?;
        let comp_strings: Vec<String> = comp_iter
            .map(|item| node_key_to_string(py, &item?))
            .collect::<PyResult<Vec<String>>>()?;
        let comp_refs: Vec<&str> = comp_strings.iter().map(|s| s.as_str()).collect();
        Ok(fnx_algorithms::is_attracting_component(dg_ref, &comp_refs))
    }
}

// ===========================================================================
// Cycle algorithms — additional
// ===========================================================================

#[pyfunction]
#[pyo3(signature = (g,))]
pub fn girth(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<Option<usize>> {
    let gr = extract_graph(g)?;
    require_undirected(&gr, "girth")?;
    let inner = gr.undirected();
    Ok(py.allow_threads(|| fnx_algorithms::girth(inner)))
}

#[pyfunction]
#[pyo3(signature = (g, source, weight = "weight"))]
pub fn find_negative_cycle(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    source: &Bound<'_, PyAny>,
    weight: &str,
) -> PyResult<Vec<PyObject>> {
    let gr = extract_graph(g)?;
    require_undirected(&gr, "find_negative_cycle")?;
    let src = node_key_to_string(py, source)?;
    let weighted_projection = gr.weighted_undirected_projection(weight);
    match fnx_algorithms::find_negative_cycle(weighted_projection.as_ref(), &src, weight) {
        Some(cycle) => Ok(cycle.iter().map(|n| gr.py_node_key(py, n)).collect()),
        None => Err(crate::NetworkXError::new_err("No negative cycle found.")),
    }
}

// ===========================================================================
// Graph predicates
// ===========================================================================

#[pyfunction]
#[pyo3(signature = (sequence,))]
pub fn is_graphical(sequence: Vec<usize>) -> bool {
    fnx_algorithms::is_graphical(&sequence)
}

#[pyfunction]
#[pyo3(signature = (sequence,))]
pub fn is_digraphical(sequence: Vec<(usize, usize)>) -> bool {
    fnx_algorithms::is_digraphical(&sequence)
}

#[pyfunction]
#[pyo3(signature = (sequence,))]
pub fn is_multigraphical(sequence: Vec<usize>) -> bool {
    fnx_algorithms::is_multigraphical(&sequence)
}

#[pyfunction]
#[pyo3(signature = (sequence,))]
pub fn is_pseudographical(sequence: Vec<usize>) -> bool {
    fnx_algorithms::is_pseudographical(&sequence)
}

#[pyfunction]
#[pyo3(signature = (g,))]
pub fn is_regular(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<bool> {
    let gr = extract_graph(g)?;
    require_undirected(&gr, "is_regular")?;
    let inner = gr.undirected();
    Ok(py.allow_threads(|| fnx_algorithms::is_regular(inner)))
}

#[pyfunction]
#[pyo3(signature = (g, k))]
pub fn is_k_regular(py: Python<'_>, g: &Bound<'_, PyAny>, k: usize) -> PyResult<bool> {
    let gr = extract_graph(g)?;
    require_undirected(&gr, "is_k_regular")?;
    let inner = gr.undirected();
    Ok(py.allow_threads(|| fnx_algorithms::is_k_regular(inner, k)))
}

#[pyfunction]
#[pyo3(signature = (g,))]
pub fn is_tournament(g: &Bound<'_, PyAny>) -> PyResult<bool> {
    let gr = extract_graph(g)?;
    if !gr.is_directed() {
        return Err(crate::NetworkXNotImplemented::new_err(
            "is_tournament is not defined for undirected graphs.",
        ));
    }
    {
        let dg_ref = gr.digraph().expect("is_directed checked above");
        Ok(fnx_algorithms::is_tournament(dg_ref))
    }
}

#[pyfunction]
#[pyo3(signature = (g, weight = "weight"))]
pub fn is_weighted(py: Python<'_>, g: &Bound<'_, PyAny>, weight: &str) -> PyResult<bool> {
    let gr = extract_graph(g)?;
    require_undirected(&gr, "is_weighted")?;
    let inner = gr.undirected();
    let w = weight.to_string();
    Ok(py.allow_threads(|| fnx_algorithms::is_weighted(inner, &w)))
}

#[pyfunction]
#[pyo3(signature = (g, weight = "weight"))]
pub fn is_negatively_weighted(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    weight: &str,
) -> PyResult<bool> {
    let gr = extract_graph(g)?;
    require_undirected(&gr, "is_negatively_weighted")?;
    let inner = gr.undirected();
    let w = weight.to_string();
    Ok(py.allow_threads(|| fnx_algorithms::is_negatively_weighted(inner, &w)))
}

#[pyfunction]
#[pyo3(signature = (g,))]
pub fn is_path(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<bool> {
    let gr = extract_graph(g)?;
    require_undirected(&gr, "is_path")?;
    let inner = gr.undirected();
    Ok(py.allow_threads(|| fnx_algorithms::is_path_graph(inner)))
}

#[pyfunction]
#[pyo3(signature = (g,))]
pub fn is_distance_regular(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<bool> {
    let gr = extract_graph(g)?;
    require_undirected(&gr, "is_distance_regular")?;
    let inner = gr.undirected();
    Ok(py.allow_threads(|| fnx_algorithms::is_distance_regular(inner)))
}

// ===========================================================================
// Traversal algorithms — additional
// ===========================================================================

#[pyfunction]
#[pyo3(signature = (g, source))]
pub fn edge_bfs(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    source: &Bound<'_, PyAny>,
) -> PyResult<Vec<(PyObject, PyObject)>> {
    let gr = extract_graph(g)?;
    let src = node_key_to_string(py, source)?;
    let result = match &gr {
        GraphRef::Undirected(pg) => fnx_algorithms::edge_bfs(&pg.inner, &src),
        GraphRef::Directed { dg, .. } => fnx_algorithms::edge_bfs_directed(&dg.inner, &src),
        _ => {
            if gr.is_directed() {
                fnx_algorithms::edge_bfs_directed(gr.digraph().unwrap(), &src)
            } else {
                fnx_algorithms::edge_bfs(gr.undirected(), &src)
            }
        }
    };
    Ok(result
        .iter()
        .map(|(u, v)| (gr.py_node_key(py, u), gr.py_node_key(py, v)))
        .collect())
}

#[pyfunction]
#[pyo3(signature = (g, source))]
pub fn edge_dfs(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    source: &Bound<'_, PyAny>,
) -> PyResult<Vec<(PyObject, PyObject)>> {
    let gr = extract_graph(g)?;
    let src = node_key_to_string(py, source)?;
    let result = match &gr {
        GraphRef::Undirected(pg) => fnx_algorithms::edge_dfs(&pg.inner, &src),
        GraphRef::Directed { dg, .. } => fnx_algorithms::edge_dfs_directed(&dg.inner, &src),
        _ => {
            if gr.is_directed() {
                fnx_algorithms::edge_dfs_directed(gr.digraph().unwrap(), &src)
            } else {
                fnx_algorithms::edge_dfs(gr.undirected(), &src)
            }
        }
    };
    Ok(result
        .iter()
        .map(|(u, v)| (gr.py_node_key(py, u), gr.py_node_key(py, v)))
        .collect())
}

// ===========================================================================
// Matching algorithms — additional
// ===========================================================================

#[pyfunction]
#[pyo3(signature = (g, edges))]
pub fn is_edge_cover(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    edges: &Bound<'_, PyAny>,
) -> PyResult<bool> {
    let gr = extract_graph(g)?;
    require_undirected(&gr, "is_edge_cover")?;
    let inner = gr.undirected();
    let edge_iter = edges.try_iter()?;
    let mut edge_pairs: Vec<(String, String)> = Vec::new();
    for item in edge_iter {
        let item = item?;
        let tuple = item.downcast::<pyo3::types::PyTuple>()?;
        let u = node_key_to_string(py, &tuple.get_item(0)?)?;
        let v = node_key_to_string(py, &tuple.get_item(1)?)?;
        edge_pairs.push((u, v));
    }
    let edge_refs: Vec<(&str, &str)> = edge_pairs
        .iter()
        .map(|(u, v)| (u.as_str(), v.as_str()))
        .collect();
    Ok(fnx_algorithms::is_edge_cover(inner, &edge_refs))
}

#[pyfunction]
#[pyo3(signature = (g, weight = "weight"))]
pub fn max_weight_clique(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    weight: &str,
) -> PyResult<(Vec<PyObject>, f64)> {
    let gr = extract_graph(g)?;
    require_undirected(&gr, "max_weight_clique")?;
    let inner = gr.undirected();
    let w = weight.to_string();
    let (clique, total_weight) = py.allow_threads(|| fnx_algorithms::max_weight_clique(inner, &w));
    let py_clique: Vec<PyObject> = clique.iter().map(|n| gr.py_node_key(py, n)).collect();
    Ok((py_clique, total_weight))
}

// ===========================================================================
// DAG algorithms — additional
// ===========================================================================

#[pyfunction]
#[pyo3(signature = (g,))]
pub fn is_aperiodic(g: &Bound<'_, PyAny>) -> PyResult<bool> {
    let gr = extract_graph(g)?;
    if !gr.is_directed() {
        return Err(crate::NetworkXNotImplemented::new_err(
            "is_aperiodic is not defined for undirected graphs.",
        ));
    }
    {
        let dg_ref = gr.digraph().expect("is_directed checked above");
        Ok(fnx_algorithms::is_aperiodic(dg_ref))
    }
}

#[pyfunction]
#[pyo3(signature = (g,))]
pub fn antichains(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<Vec<Vec<PyObject>>> {
    let gr = extract_graph(g)?;
    if !gr.is_directed() {
        return Err(crate::NetworkXNotImplemented::new_err(
            "antichains is not defined for undirected graphs.",
        ));
    }
    {
        let dg_ref = gr.digraph().expect("is_directed checked above");
        let result = fnx_algorithms::antichains(dg_ref);
        Ok(result
            .into_iter()
            .map(|chain| chain.iter().map(|n| gr.py_node_key(py, n)).collect())
            .collect())
    }
}

#[pyfunction]
#[pyo3(signature = (g, start))]
pub fn immediate_dominators(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    start: &Bound<'_, PyAny>,
) -> PyResult<PyObject> {
    let gr = extract_graph(g)?;
    if !gr.is_directed() {
        return Err(crate::NetworkXNotImplemented::new_err(
            "immediate_dominators is not defined for undirected graphs.",
        ));
    }
    let src = node_key_to_string(py, start)?;
    {
        let dg_ref = gr.digraph().expect("is_directed checked above");
        let result = fnx_algorithms::immediate_dominators(dg_ref, &src);
        let dict = pyo3::types::PyDict::new(py);
        for (node, dom) in &result {
            dict.set_item(gr.py_node_key(py, node), gr.py_node_key(py, dom))?;
        }
        Ok(dict.into_any().unbind())
    }
}

#[pyfunction]
#[pyo3(signature = (g, start))]
pub fn dominance_frontiers(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    start: &Bound<'_, PyAny>,
) -> PyResult<PyObject> {
    let gr = extract_graph(g)?;
    if !gr.is_directed() {
        return Err(crate::NetworkXNotImplemented::new_err(
            "dominance_frontiers is not defined for undirected graphs.",
        ));
    }
    let src = node_key_to_string(py, start)?;
    {
        let dg_ref = gr.digraph().expect("is_directed checked above");
        let result = fnx_algorithms::dominance_frontiers(dg_ref, &src);
        let dict = pyo3::types::PyDict::new(py);
        for (node, frontier) in &result {
            let fset = pyo3::types::PySet::new(
                py,
                frontier
                    .iter()
                    .map(|n| gr.py_node_key(py, n))
                    .collect::<Vec<_>>()
                    .as_slice(),
            )?;
            dict.set_item(gr.py_node_key(py, node), fset)?;
        }
        Ok(dict.into_any().unbind())
    }
}

// ===========================================================================
// Graph metrics — expansion, conductance, volume
// ===========================================================================

/// Return the volume of a set of nodes (sum of degrees).
#[pyfunction]
#[pyo3(signature = (g, nodes))]
fn volume(py: Python<'_>, g: &Bound<'_, PyAny>, nodes: Vec<Bound<'_, PyAny>>) -> PyResult<usize> {
    let gr = extract_graph(g)?;
    let node_strs: Vec<String> = nodes
        .iter()
        .map(|n| node_key_to_string(py, n))
        .collect::<PyResult<_>>()?;
    let refs: Vec<&str> = node_strs.iter().map(|s| s.as_str()).collect();
    Ok(fnx_algorithms::volume(gr.undirected(), &refs))
}

/// Return the boundary expansion of a set of nodes.
#[pyfunction]
#[pyo3(signature = (g, nodes))]
fn boundary_expansion(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    nodes: Vec<Bound<'_, PyAny>>,
) -> PyResult<f64> {
    let gr = extract_graph(g)?;
    let node_strs: Vec<String> = nodes
        .iter()
        .map(|n| node_key_to_string(py, n))
        .collect::<PyResult<_>>()?;
    let refs: Vec<&str> = node_strs.iter().map(|s| s.as_str()).collect();
    Ok(fnx_algorithms::boundary_expansion(gr.undirected(), &refs))
}

/// Return the conductance of a set of nodes.
#[pyfunction]
#[pyo3(signature = (g, nodes))]
fn conductance(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    nodes: Vec<Bound<'_, PyAny>>,
) -> PyResult<f64> {
    let gr = extract_graph(g)?;
    let node_strs: Vec<String> = nodes
        .iter()
        .map(|n| node_key_to_string(py, n))
        .collect::<PyResult<_>>()?;
    let refs: Vec<&str> = node_strs.iter().map(|s| s.as_str()).collect();
    Ok(fnx_algorithms::conductance(gr.undirected(), &refs))
}

/// Return the edge expansion of a set of nodes.
#[pyfunction]
#[pyo3(signature = (g, nodes))]
fn edge_expansion(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    nodes: Vec<Bound<'_, PyAny>>,
) -> PyResult<f64> {
    let gr = extract_graph(g)?;
    let node_strs: Vec<String> = nodes
        .iter()
        .map(|n| node_key_to_string(py, n))
        .collect::<PyResult<_>>()?;
    let refs: Vec<&str> = node_strs.iter().map(|s| s.as_str()).collect();
    Ok(fnx_algorithms::edge_expansion(gr.undirected(), &refs))
}

/// Return the node expansion of a set of nodes.
#[pyfunction]
#[pyo3(signature = (g, nodes))]
fn node_expansion(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    nodes: Vec<Bound<'_, PyAny>>,
) -> PyResult<f64> {
    let gr = extract_graph(g)?;
    let node_strs: Vec<String> = nodes
        .iter()
        .map(|n| node_key_to_string(py, n))
        .collect::<PyResult<_>>()?;
    let refs: Vec<&str> = node_strs.iter().map(|s| s.as_str()).collect();
    Ok(fnx_algorithms::node_expansion(gr.undirected(), &refs))
}

/// Return the mixing expansion of a set of nodes.
#[pyfunction]
#[pyo3(signature = (g, nodes))]
fn mixing_expansion(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    nodes: Vec<Bound<'_, PyAny>>,
) -> PyResult<f64> {
    let gr = extract_graph(g)?;
    let node_strs: Vec<String> = nodes
        .iter()
        .map(|n| node_key_to_string(py, n))
        .collect::<PyResult<_>>()?;
    let refs: Vec<&str> = node_strs.iter().map(|s| s.as_str()).collect();
    Ok(fnx_algorithms::mixing_expansion(gr.undirected(), &refs))
}

/// Return all non-edges of the graph.
#[pyfunction]
#[pyo3(signature = (g,))]
fn non_edges(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<Vec<(PyObject, PyObject)>> {
    let gr = extract_graph(g)?;
    let result: Vec<(String, String)> = match &gr {
        GraphRef::Directed { dg, .. } => {
            let nodes = dg.inner.nodes_ordered();
            let mut missing = Vec::new();
            for &u in &nodes {
                for &v in &nodes {
                    if u != v && !dg.inner.has_edge(u, v) {
                        missing.push((u.to_owned(), v.to_owned()));
                    }
                }
            }
            missing
        }
        _ => {
            if gr.is_directed() {
                let dg = gr.digraph().expect("is_directed checked above");
                let nodes = dg.nodes_ordered();
                let mut missing = Vec::new();
                for &u in &nodes {
                    for &v in &nodes {
                        if u != v && !dg.has_edge(u, v) {
                            missing.push((u.to_owned(), v.to_owned()));
                        }
                    }
                }
                missing
            } else {
                fnx_algorithms::non_edges(gr.undirected())
            }
        }
    };
    Ok(result
        .iter()
        .map(|(u, v)| (gr.py_node_key(py, u), gr.py_node_key(py, v)))
        .collect())
}

/// Return the average node connectivity of the graph.
#[pyfunction]
#[pyo3(signature = (g,))]
fn average_node_connectivity(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<f64> {
    let gr = extract_graph(g)?;
    if gr.is_directed() {
        let dg = gr.digraph().expect("is_directed checked above");
        Ok(py.allow_threads(|| fnx_algorithms::average_node_connectivity_directed(dg)))
    } else {
        let inner = gr.undirected();
        Ok(py.allow_threads(|| fnx_algorithms::average_node_connectivity(inner)))
    }
}

/// Return True if the graph is k-edge-connected.
#[pyfunction]
#[pyo3(signature = (g, k))]
fn is_k_edge_connected(py: Python<'_>, g: &Bound<'_, PyAny>, k: usize) -> PyResult<bool> {
    let gr = extract_graph(g)?;
    if gr.is_directed() {
        return Err(crate::NetworkXNotImplemented::new_err(
            "is_k_edge_connected is not implemented for directed graphs.",
        ));
    }
    let inner = gr.undirected();
    Ok(py.allow_threads(|| fnx_algorithms::is_k_edge_connected(inner, k)))
}

/// Return all-pairs Dijkstra distances and paths.
#[pyfunction]
#[pyo3(signature = (g, weight="weight"))]
fn all_pairs_dijkstra(py: Python<'_>, g: &Bound<'_, PyAny>, weight: &str) -> PyResult<PyObject> {
    let gr = extract_graph(g)?;
    let w = weight.to_owned();
    let result = if gr.is_directed() {
        let dg = gr
            .weighted_digraph_projection(weight)
            .expect("is_directed checked above");
        py.allow_threads(|| fnx_algorithms::all_pairs_dijkstra_directed(dg.as_ref(), &w))
    } else {
        let weighted_projection = gr.weighted_undirected_projection(weight);
        py.allow_threads(|| fnx_algorithms::all_pairs_dijkstra(weighted_projection.as_ref(), &w))
    };
    let outer = PyDict::new(py);
    for (source, (dists, paths)) in &result {
        let dist_dict = PyDict::new(py);
        for (target, &dist) in dists {
            dist_dict.set_item(gr.py_node_key(py, target), dist)?;
        }
        let path_dict = PyDict::new(py);
        for (target, path) in paths {
            let py_path: Vec<PyObject> = path.iter().map(|n| gr.py_node_key(py, n)).collect();
            path_dict.set_item(gr.py_node_key(py, target), PyList::new(py, &py_path)?)?;
        }
        let pair = PyTuple::new(py, [dist_dict.as_any(), path_dict.as_any()])?;
        outer.set_item(gr.py_node_key(py, source), pair)?;
    }
    Ok(outer.into_any().unbind())
}

/// Return the number of spanning arborescences of a directed graph rooted at `root`.
#[pyfunction]
#[pyo3(signature = (g, root, weight=None))]
fn number_of_spanning_arborescences(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    root: &Bound<'_, PyAny>,
    weight: Option<&str>,
) -> PyResult<f64> {
    let gr = extract_graph(g)?;
    if !gr.is_directed() {
        return Err(crate::NetworkXNotImplemented::new_err(
            "number_of_spanning_arborescences is not defined for undirected graphs.",
        ));
    }
    let root_str = node_key_to_string(py, root)?;
    {
        let dg_ref = gr.digraph().expect("is_directed checked above");
        Ok(fnx_algorithms::number_of_spanning_arborescences(
            dg_ref, &root_str, weight,
        ))
    }
}

/// Return the global node connectivity of the graph.
#[pyfunction]
#[pyo3(signature = (g,))]
fn global_node_connectivity(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<usize> {
    let gr = extract_graph(g)?;
    if gr.is_directed() {
        let dg = gr.digraph().expect("is_directed checked above");
        let result = py.allow_threads(|| fnx_algorithms::global_node_connectivity_directed(dg));
        Ok(result.value)
    } else {
        let inner = gr.undirected();
        let result = py.allow_threads(|| fnx_algorithms::global_node_connectivity(inner));
        Ok(result.value)
    }
}

// ===========================================================================
// ---------------------------------------------------------------------------
// Stoer-Wagner minimum cut
// ---------------------------------------------------------------------------

/// Return the minimum cut value and partition using the Stoer-Wagner algorithm.
#[pyfunction]
#[pyo3(signature = (g, weight="weight"))]
pub fn stoer_wagner(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    weight: &str,
) -> PyResult<(f64, (Vec<PyObject>, Vec<PyObject>))> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    let result = py
        .allow_threads(|| fnx_algorithms::stoer_wagner(inner, weight))
        .ok_or_else(|| {
            crate::NetworkXError::new_err("stoer_wagner requires a connected graph with >= 2 nodes")
        })?;
    let part_a: Vec<PyObject> = result
        .partition
        .0
        .iter()
        .map(|n| gr.py_node_key(py, n))
        .collect();
    let part_b: Vec<PyObject> = result
        .partition
        .1
        .iter()
        .map(|n| gr.py_node_key(py, n))
        .collect();
    Ok((result.cut_value, (part_a, part_b)))
}

// ---------------------------------------------------------------------------
// Chain decomposition
// ---------------------------------------------------------------------------

/// Return the chain decomposition of the graph.
#[pyfunction]
#[pyo3(signature = (g, root=None))]
pub fn chain_decomposition(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    root: Option<&Bound<'_, PyAny>>,
) -> PyResult<Vec<Vec<(PyObject, PyObject)>>> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    let root_key = match root {
        Some(r) => Some(node_key_to_string(py, r)?),
        None => None,
    };
    let result = py.allow_threads(|| {
        fnx_algorithms::chain_decomposition(inner, root_key.as_deref())
    });
    Ok(result
        .into_iter()
        .map(|chain| {
            chain
                .into_iter()
                .map(|(u, v)| (gr.py_node_key(py, &u), gr.py_node_key(py, &v)))
                .collect()
        })
        .collect())
}

// ---------------------------------------------------------------------------
// All topological sorts
// ---------------------------------------------------------------------------

/// Return all topological orderings of a directed acyclic graph.
#[pyfunction]
pub fn all_topological_sorts_rust(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
) -> PyResult<Vec<Vec<PyObject>>> {
    let gr = extract_graph(g)?;
    let dg = gr
        .digraph()
        .ok_or_else(|| crate::NetworkXError::new_err("all_topological_sorts requires a DiGraph"))?;
    let result = py.allow_threads(|| fnx_algorithms::all_topological_sorts(dg));
    Ok(result
        .into_iter()
        .map(|order| order.iter().map(|n| gr.py_node_key(py, n)).collect())
        .collect())
}

// ---------------------------------------------------------------------------
// Constraint (structural holes)
// ---------------------------------------------------------------------------

/// Return Burt's constraint for each node.
#[pyfunction]
pub fn constraint_rust(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<Py<PyDict>> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    let result = py.allow_threads(|| fnx_algorithms::constraint(inner));
    let dict = PyDict::new(py);
    for (node, val) in &result {
        dict.set_item(gr.py_node_key(py, node), val)?;
    }
    Ok(dict.unbind())
}

/// Return local constraint of u with respect to v.
#[pyfunction]
pub fn local_constraint_rust(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    u: &Bound<'_, PyAny>,
    v: &Bound<'_, PyAny>,
) -> PyResult<f64> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    let u_key = node_key_to_string(py, u)?;
    let v_key = node_key_to_string(py, v)?;
    Ok(py.allow_threads(|| fnx_algorithms::local_constraint(inner, &u_key, &v_key)))
}

// ---------------------------------------------------------------------------
// Effective size
// ---------------------------------------------------------------------------

/// Return Burt's effective size for each node.
#[pyfunction]
pub fn effective_size_rust(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<Py<PyDict>> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    let result = py.allow_threads(|| fnx_algorithms::effective_size(inner));
    let dict = PyDict::new(py);
    for (node, val) in &result {
        dict.set_item(gr.py_node_key(py, node), val)?;
    }
    Ok(dict.unbind())
}

// ---------------------------------------------------------------------------
// Voronoi cells
// ---------------------------------------------------------------------------

/// Partition nodes into Voronoi cells based on nearest center.
#[pyfunction]
pub fn voronoi_cells_rust(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    center_nodes: Vec<Bound<'_, PyAny>>,
) -> PyResult<Py<PyDict>> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    let center_keys: Vec<String> = center_nodes
        .iter()
        .map(|n| node_key_to_string(py, n))
        .collect::<PyResult<_>>()?;
    let center_refs: Vec<&str> = center_keys.iter().map(String::as_str).collect();
    let result = py.allow_threads(|| fnx_algorithms::voronoi_cells(inner, &center_refs));
    let dict = PyDict::new(py);
    for (center, nodes) in &result {
        let py_nodes: Vec<PyObject> = nodes.iter().map(|n| gr.py_node_key(py, n)).collect();
        dict.set_item(gr.py_node_key(py, center), py_nodes)?;
    }
    Ok(dict.unbind())
}

// ---------------------------------------------------------------------------
// D-separation
// ---------------------------------------------------------------------------

/// Test whether x and y are d-separated by z in a DAG.
#[pyfunction]
pub fn is_d_separator_rust(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    x: Vec<Bound<'_, PyAny>>,
    y: Vec<Bound<'_, PyAny>>,
    z: Vec<Bound<'_, PyAny>>,
) -> PyResult<bool> {
    let gr = extract_graph(g)?;
    let dg = gr
        .digraph()
        .ok_or_else(|| crate::NetworkXError::new_err("is_d_separator requires a DiGraph"))?;
    let x_set: std::collections::HashSet<String> = x
        .iter()
        .map(|n| node_key_to_string(py, n))
        .collect::<PyResult<_>>()?;
    let y_set: std::collections::HashSet<String> = y
        .iter()
        .map(|n| node_key_to_string(py, n))
        .collect::<PyResult<_>>()?;
    let z_set: std::collections::HashSet<String> = z
        .iter()
        .map(|n| node_key_to_string(py, n))
        .collect::<PyResult<_>>()?;
    Ok(py.allow_threads(|| fnx_algorithms::is_d_separator(dg, &x_set, &y_set, &z_set)))
}

// ---------------------------------------------------------------------------
// Edge-disjoint paths
// ---------------------------------------------------------------------------

/// Find edge-disjoint paths between source and target.
#[pyfunction]
pub fn edge_disjoint_paths_rust(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    source: &Bound<'_, PyAny>,
    target: &Bound<'_, PyAny>,
) -> PyResult<Vec<Vec<PyObject>>> {
    let gr = extract_graph(g)?;
    let s = node_key_to_string(py, source)?;
    let t = node_key_to_string(py, target)?;
    let result = if gr.is_directed() {
        let dg = gr.digraph().ok_or_else(|| {
            crate::NetworkXError::new_err("expected directed graph")
        })?;
        py.allow_threads(|| fnx_algorithms::edge_disjoint_paths_directed(dg, &s, &t))
    } else {
        let inner = gr.undirected();
        py.allow_threads(|| fnx_algorithms::edge_disjoint_paths(inner, &s, &t))
    };
    Ok(result
        .into_iter()
        .map(|path| path.iter().map(|n| gr.py_node_key(py, n)).collect())
        .collect())
}

// ---------------------------------------------------------------------------
// Node-disjoint paths
// ---------------------------------------------------------------------------

/// Find node-disjoint paths between source and target.
#[pyfunction]
pub fn node_disjoint_paths_rust(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    source: &Bound<'_, PyAny>,
    target: &Bound<'_, PyAny>,
) -> PyResult<Vec<Vec<PyObject>>> {
    let gr = extract_graph(g)?;
    let s = node_key_to_string(py, source)?;
    let t = node_key_to_string(py, target)?;
    let inner = gr.undirected();
    let result = py.allow_threads(|| fnx_algorithms::node_disjoint_paths(inner, &s, &t));
    Ok(result
        .into_iter()
        .map(|path| path.iter().map(|n| gr.py_node_key(py, n)).collect())
        .collect())
}

// ---------------------------------------------------------------------------
// Clustering coefficient (Rust)
// ---------------------------------------------------------------------------

/// Return clustering coefficient for each node.
#[pyfunction]
pub fn clustering_rust(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<Py<PyDict>> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    let result = py.allow_threads(|| fnx_algorithms::clustering_coefficient(inner));
    let dict = PyDict::new(py);
    for score in &result.scores {
        dict.set_item(gr.py_node_key(py, &score.node), score.score)?;
    }
    Ok(dict.unbind())
}

/// Return average clustering coefficient.
#[pyfunction]
pub fn average_clustering_rust(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<f64> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    let result = py.allow_threads(|| fnx_algorithms::clustering_coefficient(inner));
    Ok(result.average_clustering)
}

/// Return transitivity.
#[pyfunction]
pub fn transitivity_rust(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<f64> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    let result = py.allow_threads(|| fnx_algorithms::clustering_coefficient(inner));
    Ok(result.transitivity)
}

// ---------------------------------------------------------------------------
// Generalized degree
// ---------------------------------------------------------------------------

/// Return generalized degree for each node.
#[pyfunction]
pub fn generalized_degree_rust(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<Py<PyDict>> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    let result = py.allow_threads(|| fnx_algorithms::generalized_degree(inner));
    let outer = PyDict::new(py);
    for (node, degree_dist) in &result {
        let inner_dict = PyDict::new(py);
        for (tri_count, count) in degree_dist {
            inner_dict.set_item(tri_count, count)?;
        }
        outer.set_item(gr.py_node_key(py, node), inner_dict)?;
    }
    Ok(outer.unbind())
}

// ---------------------------------------------------------------------------
// Is strongly regular
// ---------------------------------------------------------------------------

/// Check if graph is strongly regular.
#[pyfunction]
pub fn is_strongly_regular_rust(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<bool> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    Ok(py.allow_threads(|| fnx_algorithms::is_strongly_regular(inner)))
}

// ---------------------------------------------------------------------------
// Flow hierarchy
// ---------------------------------------------------------------------------

/// Return the flow hierarchy of a directed graph.
#[pyfunction]
pub fn flow_hierarchy_rust(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<f64> {
    let gr = extract_graph(g)?;
    let dg = gr
        .digraph()
        .ok_or_else(|| crate::NetworkXError::new_err("flow_hierarchy requires a DiGraph"))?;
    Ok(py.allow_threads(|| fnx_algorithms::flow_hierarchy_directed(dg)))
}

// ---------------------------------------------------------------------------
// Graph power
// ---------------------------------------------------------------------------

/// Return the k-th power of graph G.
#[pyfunction]
pub fn power_rust(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    k: usize,
) -> PyResult<PyObject> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    let result = py.allow_threads(|| fnx_algorithms::power(inner, k));
    // Convert Rust Graph to PyGraph
    let pg = crate::PyGraph {
        inner: result,
        node_key_map: std::collections::HashMap::new(),
        node_py_attrs: std::collections::HashMap::new(),
        edge_py_attrs: std::collections::HashMap::new(),
        graph_attrs: PyDict::new(py).unbind(),
    };
    Ok(pg.into_pyobject(py)?.into_any().unbind())
}

// ---------------------------------------------------------------------------
// Square clustering
// ---------------------------------------------------------------------------

/// Return square clustering for each node.
#[pyfunction]
pub fn square_clustering_rust(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<Py<PyDict>> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    let result = py.allow_threads(|| fnx_algorithms::square_clustering_map(inner));
    let dict = PyDict::new(py);
    for (node, val) in &result {
        dict.set_item(gr.py_node_key(py, node), val)?;
    }
    Ok(dict.unbind())
}

// ---------------------------------------------------------------------------
// Ego graph
// ---------------------------------------------------------------------------

/// Return the ego graph of center within given radius.
#[pyfunction]
#[pyo3(signature = (g, center, radius=1, undirected=false))]
pub fn ego_graph_rust(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    center: &Bound<'_, PyAny>,
    radius: usize,
    undirected: bool,
) -> PyResult<PyObject> {
    let _ = undirected;
    let gr = extract_graph(g)?;
    let c = node_key_to_string(py, center)?;
    let inner = gr.undirected();
    let result = py.allow_threads(|| fnx_algorithms::ego_graph(inner, &c, radius));
    let pg = crate::PyGraph {
        inner: result,
        node_key_map: std::collections::HashMap::new(),
        node_py_attrs: std::collections::HashMap::new(),
        edge_py_attrs: std::collections::HashMap::new(),
        graph_attrs: PyDict::new(py).unbind(),
    };
    Ok(pg.into_pyobject(py)?.into_any().unbind())
}

// ---------------------------------------------------------------------------
// Degree mixing dict
// ---------------------------------------------------------------------------

/// Return degree mixing dictionary.
#[pyfunction]
pub fn degree_mixing_dict_rust(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<Py<PyDict>> {
    let gr = extract_graph(g)?;
    let result = if gr.is_directed() {
        let dg = gr.digraph().unwrap();
        py.allow_threads(|| fnx_algorithms::degree_mixing_dict_directed(dg))
    } else {
        let inner = gr.undirected();
        py.allow_threads(|| fnx_algorithms::degree_mixing_dict(inner))
    };
    let dict = PyDict::new(py);
    for ((du, dv), count) in &result {
        dict.set_item((*du, *dv), count)?;
    }
    Ok(dict.unbind())
}

// ---------------------------------------------------------------------------
// Connected dominating set
// ---------------------------------------------------------------------------

/// Return a greedy connected dominating set.
#[pyfunction]
pub fn connected_dominating_set_rust(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
) -> PyResult<Vec<PyObject>> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    let result = py.allow_threads(|| fnx_algorithms::connected_dominating_set(inner));
    Ok(result.iter().map(|n| gr.py_node_key(py, n)).collect())
}

// ---------------------------------------------------------------------------
// Triadic census
// ---------------------------------------------------------------------------

/// Return the triadic census of a directed graph.
#[pyfunction]
pub fn triadic_census_rust(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<Py<PyDict>> {
    let gr = extract_graph(g)?;
    let dg = gr
        .digraph()
        .ok_or_else(|| crate::NetworkXError::new_err("triadic_census requires a DiGraph"))?;
    let result = py.allow_threads(|| fnx_algorithms::triadic_census(dg));
    let dict = PyDict::new(py);
    for (name, count) in &result {
        dict.set_item(name, count)?;
    }
    Ok(dict.unbind())
}

// ---------------------------------------------------------------------------
// Attribute mixing / assortativity
// ---------------------------------------------------------------------------

/// Return attribute mixing dictionary.
#[pyfunction]
pub fn attribute_mixing_dict_rust(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    attribute: &str,
) -> PyResult<Py<PyDict>> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    let result = py.allow_threads(|| fnx_algorithms::attribute_mixing_dict(inner, attribute));
    let dict = PyDict::new(py);
    for ((a, b), count) in &result {
        dict.set_item((a.as_str(), b.as_str()), count)?;
    }
    Ok(dict.unbind())
}

/// Return attribute assortativity coefficient.
#[pyfunction]
pub fn attribute_assortativity_rust(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    attribute: &str,
) -> PyResult<f64> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    Ok(py.allow_threads(|| fnx_algorithms::attribute_assortativity(inner, attribute)))
}

// ---------------------------------------------------------------------------
// AT-free
// ---------------------------------------------------------------------------

/// Check if graph is asteroidal-triple-free.
#[pyfunction]
pub fn is_at_free_rust(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<bool> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    Ok(py.allow_threads(|| fnx_algorithms::is_at_free(inner)))
}

// ---------------------------------------------------------------------------
// Full join
// ---------------------------------------------------------------------------

/// Return the full join of two graphs.
#[pyfunction]
pub fn full_join_rust(py: Python<'_>, g1: &Bound<'_, PyAny>, g2: &Bound<'_, PyAny>) -> PyResult<PyObject> {
    let gr1 = extract_graph(g1)?;
    let gr2 = extract_graph(g2)?;
    let inner1 = gr1.undirected();
    let inner2 = gr2.undirected();
    let result = py.allow_threads(|| fnx_algorithms::full_join(inner1, inner2));
    let pg = crate::PyGraph {
        inner: result,
        node_key_map: std::collections::HashMap::new(),
        node_py_attrs: std::collections::HashMap::new(),
        edge_py_attrs: std::collections::HashMap::new(),
        graph_attrs: PyDict::new(py).unbind(),
    };
    Ok(pg.into_pyobject(py)?.into_any().unbind())
}

// ---------------------------------------------------------------------------
// Identified nodes (contract)
// ---------------------------------------------------------------------------

/// Contract node v into node u.
#[pyfunction]
pub fn identified_nodes_rust(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    u: &Bound<'_, PyAny>,
    v: &Bound<'_, PyAny>,
) -> PyResult<PyObject> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    let u_key = node_key_to_string(py, u)?;
    let v_key = node_key_to_string(py, v)?;
    let result = py.allow_threads(|| fnx_algorithms::identified_nodes(inner, &u_key, &v_key));
    let pg = crate::PyGraph {
        inner: result,
        node_key_map: std::collections::HashMap::new(),
        node_py_attrs: std::collections::HashMap::new(),
        edge_py_attrs: std::collections::HashMap::new(),
        graph_attrs: PyDict::new(py).unbind(),
    };
    Ok(pg.into_pyobject(py)?.into_any().unbind())
}

// ---------------------------------------------------------------------------
// All triads
// ---------------------------------------------------------------------------

/// Enumerate all non-null triads in a directed graph.
#[pyfunction]
pub fn all_triads_rust(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
) -> PyResult<Vec<(PyObject, PyObject, PyObject, String)>> {
    let gr = extract_graph(g)?;
    let dg = gr
        .digraph()
        .ok_or_else(|| crate::NetworkXError::new_err("all_triads requires a DiGraph"))?;
    let result = py.allow_threads(|| fnx_algorithms::all_triads(dg));
    Ok(result
        .into_iter()
        .map(|(a, b, c, t)| (gr.py_node_key(py, &a), gr.py_node_key(py, &b), gr.py_node_key(py, &c), t))
        .collect())
}

// ---------------------------------------------------------------------------
// Node degree xy
// ---------------------------------------------------------------------------

/// Return (source_degree, target_degree) pairs for each edge.
#[pyfunction]
#[pyo3(signature = (g, x="out", y="in", weight=None, nodes=None))]
pub fn node_degree_xy_rust(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    x: &str,
    y: &str,
    weight: Option<&str>,
    nodes: Option<Vec<Bound<'_, PyAny>>>,
) -> PyResult<Vec<(usize, usize)>> {
    let _ = weight;
    let _ = nodes;
    let gr = extract_graph(g)?;
    let result = if gr.is_directed() {
        let dg = gr.digraph().unwrap();
        py.allow_threads(|| fnx_algorithms::node_degree_xy_directed(dg, x, y))
    } else {
        let inner = gr.undirected();
        py.allow_threads(|| fnx_algorithms::node_degree_xy(inner))
    };
    Ok(result)
}

// ---------------------------------------------------------------------------
// Dedensify
// ---------------------------------------------------------------------------

/// Return a dedensified graph with compressor nodes.
#[pyfunction]
#[pyo3(signature = (g, threshold, prefix=None, copy=true))]
pub fn dedensify_rust(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    threshold: usize,
    prefix: Option<&str>,
    copy: bool,
) -> PyResult<(PyObject, Vec<String>)> {
    let _ = prefix;
    let _ = copy;
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    let (result_graph, compressors) = py.allow_threads(|| fnx_algorithms::dedensify(inner, threshold));
    let pg = crate::PyGraph {
        inner: result_graph,
        node_key_map: std::collections::HashMap::new(),
        node_py_attrs: std::collections::HashMap::new(),
        edge_py_attrs: std::collections::HashMap::new(),
        graph_attrs: PyDict::new(py).unbind(),
    };
    Ok((pg.into_pyobject(py)?.into_any().unbind(), compressors))
}

// ---------------------------------------------------------------------------
// Numeric assortativity
// ---------------------------------------------------------------------------

/// Numeric assortativity coefficient for a scalar node attribute.
#[pyfunction]
pub fn numeric_assortativity_coefficient_rust(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    attribute: &str,
) -> PyResult<f64> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    Ok(py.allow_threads(|| fnx_algorithms::numeric_assortativity_coefficient(inner, attribute)))
}

// ---------------------------------------------------------------------------
// Group closeness centrality
// ---------------------------------------------------------------------------

/// Group closeness centrality.
#[pyfunction]
pub fn group_closeness_centrality_rust(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    group: Vec<Bound<'_, PyAny>>,
) -> PyResult<f64> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    let group_keys: Vec<String> = group
        .iter()
        .map(|n| node_key_to_string(py, n))
        .collect::<PyResult<_>>()?;
    let group_refs: Vec<&str> = group_keys.iter().map(String::as_str).collect();
    Ok(py.allow_threads(|| fnx_algorithms::group_closeness_centrality(inner, &group_refs)))
}

// ---------------------------------------------------------------------------
// Get node/edge attributes
// ---------------------------------------------------------------------------

/// Get a specific attribute from all nodes.
#[pyfunction]
pub fn get_node_attributes_rust(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    name: &str,
) -> PyResult<Py<PyDict>> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    let result = py.allow_threads(|| fnx_algorithms::get_node_attributes(inner, name));
    let dict = PyDict::new(py);
    for (node, val) in &result {
        dict.set_item(gr.py_node_key(py, node), val.as_str())?;
    }
    Ok(dict.unbind())
}

/// Get a specific attribute from all edges.
#[pyfunction]
pub fn get_edge_attributes_rust(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    name: &str,
) -> PyResult<Py<PyDict>> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    let result = py.allow_threads(|| fnx_algorithms::get_edge_attributes(inner, name));
    let dict = PyDict::new(py);
    for ((u, v), val) in &result {
        dict.set_item(
            (gr.py_node_key(py, u), gr.py_node_key(py, v)),
            val.as_str(),
        )?;
    }
    Ok(dict.unbind())
}

// ---------------------------------------------------------------------------
// Quotient graph
// ---------------------------------------------------------------------------

/// Build a quotient graph from a partition.
#[pyfunction]
pub fn quotient_graph_rust(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    partition: Vec<Vec<Bound<'_, PyAny>>>,
) -> PyResult<PyObject> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    let partition_keys: Vec<Vec<String>> = partition
        .iter()
        .map(|block| {
            block
                .iter()
                .map(|n| node_key_to_string(py, n))
                .collect::<PyResult<Vec<String>>>()
        })
        .collect::<PyResult<_>>()?;
    let result = py.allow_threads(|| fnx_algorithms::quotient_graph(inner, &partition_keys));
    let pg = crate::PyGraph {
        inner: result,
        node_key_map: std::collections::HashMap::new(),
        node_py_attrs: std::collections::HashMap::new(),
        edge_py_attrs: std::collections::HashMap::new(),
        graph_attrs: PyDict::new(py).unbind(),
    };
    Ok(pg.into_pyobject(py)?.into_any().unbind())
}

// ---------------------------------------------------------------------------
// Moral graph
// ---------------------------------------------------------------------------

/// Return the moral graph of a DAG.
#[pyfunction]
pub fn moral_graph_rust(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<PyObject> {
    let gr = extract_graph(g)?;
    let dg = gr.digraph().ok_or_else(|| crate::NetworkXError::new_err("moral_graph requires DiGraph"))?;
    let result = py.allow_threads(|| fnx_algorithms::moral_graph(dg));
    let pg = crate::PyGraph {
        inner: result,
        node_key_map: std::collections::HashMap::new(),
        node_py_attrs: std::collections::HashMap::new(),
        edge_py_attrs: std::collections::HashMap::new(),
        graph_attrs: PyDict::new(py).unbind(),
    };
    Ok(pg.into_pyobject(py)?.into_any().unbind())
}

// ---------------------------------------------------------------------------
// Distance indices
// ---------------------------------------------------------------------------

/// Gutman index.
#[pyfunction]
pub fn gutman_index_rust(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<f64> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    py.allow_threads(|| fnx_algorithms::gutman_index(inner))
        .ok_or_else(|| crate::NetworkXError::new_err("Graph is not connected"))
}

/// Hyper-Wiener index.
#[pyfunction]
pub fn hyper_wiener_index_rust(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<f64> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    py.allow_threads(|| fnx_algorithms::hyper_wiener_index(inner))
        .ok_or_else(|| crate::NetworkXError::new_err("Graph is not connected"))
}

/// Schultz index.
#[pyfunction]
pub fn schultz_index_rust(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<f64> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    py.allow_threads(|| fnx_algorithms::schultz_index(inner))
        .ok_or_else(|| crate::NetworkXError::new_err("Graph is not connected"))
}

/// Harmonic diameter.
#[pyfunction]
pub fn harmonic_diameter_rust(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<f64> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    Ok(py.allow_threads(|| fnx_algorithms::harmonic_diameter(inner)))
}

// ---------------------------------------------------------------------------
// Self-loop functions
// ---------------------------------------------------------------------------

/// Return self-loop edges.
#[pyfunction]
pub fn selfloop_edges_rust(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<Vec<(PyObject, PyObject)>> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    let result = py.allow_threads(|| fnx_algorithms::selfloop_edges(inner));
    Ok(result.iter().map(|(u, v)| (gr.py_node_key(py, u), gr.py_node_key(py, v))).collect())
}

/// Count self-loops.
#[pyfunction]
pub fn number_of_selfloops_rust(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<usize> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    Ok(py.allow_threads(|| fnx_algorithms::number_of_selfloops(inner)))
}

/// Nodes with self-loops.
#[pyfunction]
pub fn nodes_with_selfloops_rust(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<Vec<PyObject>> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    let result = py.allow_threads(|| fnx_algorithms::nodes_with_selfloops(inner));
    Ok(result.iter().map(|n| gr.py_node_key(py, n)).collect())
}

// ---------------------------------------------------------------------------
// To edgelist / to dict of lists
// ---------------------------------------------------------------------------

/// Convert graph to dict-of-lists adjacency.
#[pyfunction]
pub fn to_dict_of_lists_rust(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<Py<PyDict>> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    let result = py.allow_threads(|| fnx_algorithms::to_dict_of_lists(inner));
    let dict = PyDict::new(py);
    for (node, nbrs) in &result {
        let py_nbrs: Vec<PyObject> = nbrs.iter().map(|n| gr.py_node_key(py, n)).collect();
        dict.set_item(gr.py_node_key(py, node), py_nbrs)?;
    }
    Ok(dict.unbind())
}

// ---------------------------------------------------------------------------
// CN Soundarajan-Hopcroft
// ---------------------------------------------------------------------------

/// CN Soundarajan-Hopcroft link prediction.
#[pyfunction]
#[pyo3(signature = (g, ebunch, community="community"))]
pub fn cn_soundarajan_hopcroft_rust(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    ebunch: Vec<(Bound<'_, PyAny>, Bound<'_, PyAny>)>,
    community: &str,
) -> PyResult<Vec<(PyObject, PyObject, f64)>> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    let pairs: Vec<(String, String)> = ebunch
        .iter()
        .map(|(u, v)| Ok((node_key_to_string(py, u)?, node_key_to_string(py, v)?)))
        .collect::<PyResult<_>>()?;
    let result = py.allow_threads(|| fnx_algorithms::cn_soundarajan_hopcroft(inner, &pairs, community));
    Ok(result.into_iter().map(|(u, v, s)| (gr.py_node_key(py, &u), gr.py_node_key(py, &v), s)).collect())
}

// ---------------------------------------------------------------------------
// Triad type
// ---------------------------------------------------------------------------

/// Classify the triad type of three nodes.
#[pyfunction]
pub fn triad_type_rust(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    u: &Bound<'_, PyAny>,
    v: &Bound<'_, PyAny>,
    w: &Bound<'_, PyAny>,
) -> PyResult<String> {
    let gr = extract_graph(g)?;
    let dg = gr.digraph().ok_or_else(|| crate::NetworkXError::new_err("triad_type requires DiGraph"))?;
    let uk = node_key_to_string(py, u)?;
    let vk = node_key_to_string(py, v)?;
    let wk = node_key_to_string(py, w)?;
    Ok(py.allow_threads(|| fnx_algorithms::triad_type(dg, &uk, &vk, &wk)))
}

// ---------------------------------------------------------------------------
// BFS beam edges
// ---------------------------------------------------------------------------

/// BFS with beam width.
#[pyfunction]
#[pyo3(signature = (g, source, width=100))]
pub fn bfs_beam_edges_rust(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    source: &Bound<'_, PyAny>,
    width: usize,
) -> PyResult<Vec<(PyObject, PyObject)>> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    let s = node_key_to_string(py, source)?;
    let result = py.allow_threads(|| fnx_algorithms::bfs_beam_edges(inner, &s, width));
    Ok(result.iter().map(|(u, v)| (gr.py_node_key(py, u), gr.py_node_key(py, v))).collect())
}

// ---------------------------------------------------------------------------
// All neighbors (directed)
// ---------------------------------------------------------------------------

/// Return all neighbors of a node in a directed graph.
#[pyfunction]
pub fn all_neighbors_directed_rust(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    node: &Bound<'_, PyAny>,
) -> PyResult<Vec<PyObject>> {
    let gr = extract_graph(g)?;
    let dg = gr.digraph().ok_or_else(|| crate::NetworkXError::new_err("requires DiGraph"))?;
    let n = node_key_to_string(py, node)?;
    let result = py.allow_threads(|| fnx_algorithms::all_neighbors_directed(dg, &n));
    Ok(result.iter().map(|n| gr.py_node_key(py, n)).collect())
}

// ---------------------------------------------------------------------------
// Local bridges (Rust)
// ---------------------------------------------------------------------------

/// Return local bridges.
#[pyfunction]
pub fn local_bridges_rust(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<Vec<(PyObject, PyObject)>> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    let result = py.allow_threads(|| fnx_algorithms::local_bridges_list(inner));
    Ok(result.iter().map(|(u, v)| (gr.py_node_key(py, u), gr.py_node_key(py, v))).collect())
}

// ---------------------------------------------------------------------------
// Generic BFS edges
// ---------------------------------------------------------------------------

/// BFS edges with optional depth limit.
#[pyfunction]
#[pyo3(signature = (g, source, depth_limit=None))]
pub fn generic_bfs_edges_rust(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    source: &Bound<'_, PyAny>,
    depth_limit: Option<usize>,
) -> PyResult<Vec<(PyObject, PyObject)>> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    let s = node_key_to_string(py, source)?;
    let result = py.allow_threads(|| fnx_algorithms::generic_bfs_edges(inner, &s, depth_limit));
    Ok(result.iter().map(|(u, v)| (gr.py_node_key(py, u), gr.py_node_key(py, v))).collect())
}

// ---------------------------------------------------------------------------
// Graph info
// ---------------------------------------------------------------------------

/// Return text description of graph.
#[pyfunction]
pub fn graph_info_rust(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<String> {
    let gr = extract_graph(g)?;
    Ok(if gr.is_directed() {
        let dg = gr.digraph().unwrap();
        py.allow_threads(|| fnx_algorithms::digraph_info(dg))
    } else {
        let inner = gr.undirected();
        py.allow_threads(|| fnx_algorithms::graph_info(inner))
    })
}

// ---------------------------------------------------------------------------
// All pairs LCA
// ---------------------------------------------------------------------------

/// Find LCA for given pairs in a DAG.
#[pyfunction]
pub fn all_pairs_lca_rust(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    pairs: Vec<(Bound<'_, PyAny>, Bound<'_, PyAny>)>,
) -> PyResult<Vec<((PyObject, PyObject), PyObject)>> {
    let gr = extract_graph(g)?;
    let dg = gr.digraph().ok_or_else(|| crate::NetworkXError::new_err("LCA requires DiGraph"))?;
    let pair_keys: Vec<(String, String)> = pairs.iter()
        .map(|(u, v)| Ok((node_key_to_string(py, u)?, node_key_to_string(py, v)?)))
        .collect::<PyResult<_>>()?;
    let result = py.allow_threads(|| fnx_algorithms::all_pairs_lowest_common_ancestor(dg, &pair_keys));
    Ok(result.into_iter().map(|((u, v), lca)| {
        ((gr.py_node_key(py, &u), gr.py_node_key(py, &v)), gr.py_node_key(py, &lca))
    }).collect())
}

// ---------------------------------------------------------------------------
// Generate edgelist
// ---------------------------------------------------------------------------

/// Generate edgelist lines.
#[pyfunction]
#[pyo3(signature = (g, delimiter=" "))]
pub fn generate_edgelist_rust(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    delimiter: &str,
) -> PyResult<Vec<String>> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    Ok(py.allow_threads(|| fnx_algorithms::generate_edgelist(inner, delimiter)))
}

// ---------------------------------------------------------------------------
// Group betweenness centrality
// ---------------------------------------------------------------------------

/// Group betweenness centrality.
#[pyfunction]
pub fn group_betweenness_centrality_rust(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    group: Vec<Bound<'_, PyAny>>,
) -> PyResult<f64> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    let keys: Vec<String> = group.iter().map(|n| node_key_to_string(py, n)).collect::<PyResult<_>>()?;
    let refs: Vec<&str> = keys.iter().map(String::as_str).collect();
    Ok(py.allow_threads(|| fnx_algorithms::group_betweenness_centrality(inner, &refs)))
}

// ---------------------------------------------------------------------------
// Attribute assortativity coefficient
// ---------------------------------------------------------------------------

/// Attribute assortativity coefficient.
#[pyfunction]
pub fn attribute_assortativity_coefficient_rust(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    attribute: &str,
) -> PyResult<f64> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    Ok(py.allow_threads(|| fnx_algorithms::attribute_assortativity_coefficient(inner, attribute)))
}

// Registration
// ===========================================================================

// ---------------------------------------------------------------------------
// Double/directed edge swap (Rust)
// ---------------------------------------------------------------------------

/// Perform degree-preserving double edge swaps (Rust).
#[pyfunction]
#[pyo3(signature = (g, nswap=1, max_tries=100, seed=None))]
pub fn double_edge_swap_rust(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    nswap: usize,
    max_tries: usize,
    seed: Option<u64>,
) -> PyResult<usize> {
    let gr = extract_graph(g)?;
    match &gr {
        GraphRef::Undirected(pg) => {
            // Safety: we need mutable access. Clone, swap, copy back.
            let mut graph_copy = pg.inner.clone();
            let swaps = py.allow_threads(|| {
                fnx_algorithms::double_edge_swap_seeded(
                    &mut graph_copy,
                    nswap,
                    max_tries,
                    seed.unwrap_or(0),
                )
            });
            // We can't mutate through the PyRef, so return count only
            // The Python wrapper handles in-place mutation
            Ok(swaps)
        }
        _ => Err(crate::NetworkXError::new_err(
            "double_edge_swap requires undirected Graph",
        )),
    }
}

// ---------------------------------------------------------------------------
// Global parameters (distance-regular)
// ---------------------------------------------------------------------------

/// Return global parameters (b, c) of a distance-regular graph.
#[pyfunction]
pub fn global_parameters_rust(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
) -> PyResult<Option<(Vec<usize>, Vec<usize>)>> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    Ok(py.allow_threads(|| fnx_algorithms::global_parameters(inner)))
}

// ---------------------------------------------------------------------------
// BFS labeled edges
// ---------------------------------------------------------------------------

/// BFS with edge labeling.
#[pyfunction]
pub fn bfs_labeled_edges_rust(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    source: &Bound<'_, PyAny>,
) -> PyResult<Vec<(PyObject, PyObject, String)>> {
    let gr = extract_graph(g)?;
    let s = node_key_to_string(py, source)?;
    let inner = gr.undirected();
    let result = py.allow_threads(|| fnx_algorithms::bfs_labeled_edges(inner, &s));
    Ok(result
        .into_iter()
        .map(|(u, v, label)| (gr.py_node_key(py, &u), gr.py_node_key(py, &v), label))
        .collect())
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
    m.add_function(wrap_pyfunction!(maximum_flow, m)?)?;
    m.add_function(wrap_pyfunction!(maximum_flow_value, m)?)?;
    m.add_function(wrap_pyfunction!(minimum_cut, m)?)?;
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
    m.add_function(wrap_pyfunction!(number_of_spanning_trees, m)?)?;
    m.add_function(wrap_pyfunction!(partition_spanning_tree, m)?)?;
    m.add_function(wrap_pyfunction!(random_spanning_tree, m)?)?;
    m.add_function(wrap_pyfunction!(minimum_spanning_tree, m)?)?;
    m.add_function(wrap_pyfunction!(minimum_spanning_edges, m)?)?;
    m.add_function(wrap_pyfunction!(maximum_branching, m)?)?;
    m.add_function(wrap_pyfunction!(minimum_branching, m)?)?;
    m.add_function(wrap_pyfunction!(maximum_spanning_arborescence, m)?)?;
    m.add_function(wrap_pyfunction!(minimum_spanning_arborescence, m)?)?;
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
    m.add_function(wrap_pyfunction!(efficiency, m)?)?;
    m.add_function(wrap_pyfunction!(global_efficiency, m)?)?;
    m.add_function(wrap_pyfunction!(local_efficiency, m)?)?;
    m.add_function(wrap_pyfunction!(tree_broadcast_center, m)?)?;
    m.add_function(wrap_pyfunction!(tree_broadcast_time, m)?)?;
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
    m.add_function(wrap_pyfunction!(maximum_spanning_edges, m)?)?;
    m.add_function(wrap_pyfunction!(maximum_branching, m)?)?;
    m.add_function(wrap_pyfunction!(minimum_branching, m)?)?;
    m.add_function(wrap_pyfunction!(maximum_spanning_arborescence, m)?)?;
    m.add_function(wrap_pyfunction!(minimum_spanning_arborescence, m)?)?;
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
    m.add_function(wrap_pyfunction!(all_triangles, m)?)?;
    m.add_function(wrap_pyfunction!(node_clique_number, m)?)?;
    m.add_function(wrap_pyfunction!(enumerate_all_cliques, m)?)?;
    m.add_function(wrap_pyfunction!(find_cliques_recursive, m)?)?;
    m.add_function(wrap_pyfunction!(chordal_graph_cliques, m)?)?;
    m.add_function(wrap_pyfunction!(chordal_graph_treewidth, m)?)?;
    m.add_function(wrap_pyfunction!(make_max_clique_graph, m)?)?;
    m.add_function(wrap_pyfunction!(ring_of_cliques, m)?)?;
    // Classic graph generators
    m.add_function(wrap_pyfunction!(balanced_tree, m)?)?;
    m.add_function(wrap_pyfunction!(barbell_graph, m)?)?;
    m.add_function(wrap_pyfunction!(bull_graph, m)?)?;
    m.add_function(wrap_pyfunction!(chvatal_graph, m)?)?;
    m.add_function(wrap_pyfunction!(cubical_graph, m)?)?;
    m.add_function(wrap_pyfunction!(desargues_graph, m)?)?;
    m.add_function(wrap_pyfunction!(diamond_graph, m)?)?;
    m.add_function(wrap_pyfunction!(dodecahedral_graph, m)?)?;
    m.add_function(wrap_pyfunction!(frucht_graph, m)?)?;
    m.add_function(wrap_pyfunction!(heawood_graph, m)?)?;
    m.add_function(wrap_pyfunction!(house_graph, m)?)?;
    m.add_function(wrap_pyfunction!(house_x_graph, m)?)?;
    m.add_function(wrap_pyfunction!(icosahedral_graph, m)?)?;
    m.add_function(wrap_pyfunction!(krackhardt_kite_graph, m)?)?;
    m.add_function(wrap_pyfunction!(moebius_kantor_graph, m)?)?;
    m.add_function(wrap_pyfunction!(octahedral_graph, m)?)?;
    m.add_function(wrap_pyfunction!(pappus_graph, m)?)?;
    m.add_function(wrap_pyfunction!(petersen_graph, m)?)?;
    m.add_function(wrap_pyfunction!(sedgewick_maze_graph, m)?)?;
    m.add_function(wrap_pyfunction!(tetrahedral_graph, m)?)?;
    m.add_function(wrap_pyfunction!(truncated_cube_graph, m)?)?;
    m.add_function(wrap_pyfunction!(truncated_tetrahedron_graph, m)?)?;
    m.add_function(wrap_pyfunction!(tutte_graph, m)?)?;
    m.add_function(wrap_pyfunction!(hoffman_singleton_graph, m)?)?;
    m.add_function(wrap_pyfunction!(generalized_petersen_graph, m)?)?;
    m.add_function(wrap_pyfunction!(wheel_graph, m)?)?;
    m.add_function(wrap_pyfunction!(ladder_graph, m)?)?;
    m.add_function(wrap_pyfunction!(circular_ladder_graph, m)?)?;
    m.add_function(wrap_pyfunction!(lollipop_graph, m)?)?;
    m.add_function(wrap_pyfunction!(tadpole_graph, m)?)?;
    m.add_function(wrap_pyfunction!(turan_graph, m)?)?;
    m.add_function(wrap_pyfunction!(windmill_graph, m)?)?;
    m.add_function(wrap_pyfunction!(hypercube_graph, m)?)?;
    m.add_function(wrap_pyfunction!(complete_bipartite_graph, m)?)?;
    m.add_function(wrap_pyfunction!(complete_multipartite_graph, m)?)?;
    m.add_function(wrap_pyfunction!(grid_2d_graph, m)?)?;
    m.add_function(wrap_pyfunction!(null_graph, m)?)?;
    m.add_function(wrap_pyfunction!(trivial_graph, m)?)?;
    m.add_function(wrap_pyfunction!(binomial_tree, m)?)?;
    m.add_function(wrap_pyfunction!(full_rary_tree, m)?)?;
    m.add_function(wrap_pyfunction!(circulant_graph, m)?)?;
    m.add_function(wrap_pyfunction!(kneser_graph, m)?)?;
    m.add_function(wrap_pyfunction!(paley_graph, m)?)?;
    m.add_function(wrap_pyfunction!(chordal_cycle_graph, m)?)?;
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
    // Chordality
    m.add_function(wrap_pyfunction!(is_chordal, m)?)?;
    // Barycenter
    m.add_function(wrap_pyfunction!(barycenter, m)?)?;
    // Approximation algorithms
    m.add_function(wrap_pyfunction!(min_weighted_vertex_cover, m)?)?;
    m.add_function(wrap_pyfunction!(maximal_independent_set, m)?)?;
    m.add_function(wrap_pyfunction!(maximum_independent_set, m)?)?;
    m.add_function(wrap_pyfunction!(max_clique, m)?)?;
    m.add_function(wrap_pyfunction!(clique_removal, m)?)?;
    m.add_function(wrap_pyfunction!(large_clique_size, m)?)?;
    m.add_function(wrap_pyfunction!(spanner, m)?)?;
    // Tree recognition
    m.add_function(wrap_pyfunction!(is_arborescence, m)?)?;
    m.add_function(wrap_pyfunction!(is_branching, m)?)?;
    // Isolates
    m.add_function(wrap_pyfunction!(is_isolate, m)?)?;
    m.add_function(wrap_pyfunction!(isolates, m)?)?;
    m.add_function(wrap_pyfunction!(number_of_isolates, m)?)?;
    // Boundary
    m.add_function(wrap_pyfunction!(edge_boundary, m)?)?;
    m.add_function(wrap_pyfunction!(node_boundary, m)?)?;
    m.add_function(wrap_pyfunction!(cut_size, m)?)?;
    m.add_function(wrap_pyfunction!(normalized_cut_size, m)?)?;
    // Path validation
    m.add_function(wrap_pyfunction!(is_simple_path, m)?)?;
    // Matching validators
    m.add_function(wrap_pyfunction!(is_matching, m)?)?;
    m.add_function(wrap_pyfunction!(is_maximal_matching, m)?)?;
    m.add_function(wrap_pyfunction!(is_perfect_matching, m)?)?;
    // Cycles
    m.add_function(wrap_pyfunction!(simple_cycles, m)?)?;
    m.add_function(wrap_pyfunction!(find_cycle, m)?)?;
    // Additional shortest path algorithms
    m.add_function(wrap_pyfunction!(dijkstra_path_length, m)?)?;
    m.add_function(wrap_pyfunction!(bellman_ford_path_length, m)?)?;
    m.add_function(wrap_pyfunction!(single_source_dijkstra, m)?)?;
    m.add_function(wrap_pyfunction!(single_source_dijkstra_path, m)?)?;
    m.add_function(wrap_pyfunction!(single_source_dijkstra_path_length, m)?)?;
    m.add_function(wrap_pyfunction!(single_source_bellman_ford, m)?)?;
    m.add_function(wrap_pyfunction!(single_source_bellman_ford_path, m)?)?;
    m.add_function(wrap_pyfunction!(single_source_bellman_ford_path_length, m)?)?;
    m.add_function(wrap_pyfunction!(single_target_shortest_path, m)?)?;
    m.add_function(wrap_pyfunction!(single_target_shortest_path_length, m)?)?;
    m.add_function(wrap_pyfunction!(all_pairs_dijkstra_path_length, m)?)?;
    m.add_function(wrap_pyfunction!(all_pairs_dijkstra_path, m)?)?;
    m.add_function(wrap_pyfunction!(all_pairs_bellman_ford_path_length, m)?)?;
    m.add_function(wrap_pyfunction!(all_pairs_bellman_ford_path, m)?)?;
    m.add_function(wrap_pyfunction!(floyd_warshall, m)?)?;
    m.add_function(wrap_pyfunction!(
        floyd_warshall_predecessor_and_distance,
        m
    )?)?;
    m.add_function(wrap_pyfunction!(bidirectional_shortest_path, m)?)?;
    m.add_function(wrap_pyfunction!(negative_edge_cycle, m)?)?;
    m.add_function(wrap_pyfunction!(predecessor_fn, m)?)?;
    m.add_function(wrap_pyfunction!(path_weight, m)?)?;
    // Additional centrality algorithms
    m.add_function(wrap_pyfunction!(in_degree_centrality, m)?)?;
    m.add_function(wrap_pyfunction!(out_degree_centrality, m)?)?;
    m.add_function(wrap_pyfunction!(local_reaching_centrality, m)?)?;
    m.add_function(wrap_pyfunction!(global_reaching_centrality, m)?)?;
    m.add_function(wrap_pyfunction!(group_degree_centrality, m)?)?;
    m.add_function(wrap_pyfunction!(group_in_degree_centrality, m)?)?;
    m.add_function(wrap_pyfunction!(group_out_degree_centrality, m)?)?;
    // Expansion and conductance metrics
    m.add_function(wrap_pyfunction!(volume, m)?)?;
    m.add_function(wrap_pyfunction!(boundary_expansion, m)?)?;
    m.add_function(wrap_pyfunction!(conductance, m)?)?;
    m.add_function(wrap_pyfunction!(edge_expansion, m)?)?;
    m.add_function(wrap_pyfunction!(node_expansion, m)?)?;
    m.add_function(wrap_pyfunction!(mixing_expansion, m)?)?;
    m.add_function(wrap_pyfunction!(non_edges, m)?)?;
    m.add_function(wrap_pyfunction!(average_node_connectivity, m)?)?;
    m.add_function(wrap_pyfunction!(is_k_edge_connected, m)?)?;
    m.add_function(wrap_pyfunction!(all_pairs_dijkstra, m)?)?;
    m.add_function(wrap_pyfunction!(number_of_spanning_arborescences, m)?)?;
    m.add_function(wrap_pyfunction!(global_node_connectivity, m)?)?;
    // Component algorithms
    m.add_function(wrap_pyfunction!(node_connected_component, m)?)?;
    m.add_function(wrap_pyfunction!(is_biconnected, m)?)?;
    m.add_function(wrap_pyfunction!(biconnected_components, m)?)?;
    m.add_function(wrap_pyfunction!(biconnected_component_edges, m)?)?;
    m.add_function(wrap_pyfunction!(is_semiconnected, m)?)?;
    m.add_function(wrap_pyfunction!(kosaraju_strongly_connected_components, m)?)?;
    m.add_function(wrap_pyfunction!(attracting_components, m)?)?;
    m.add_function(wrap_pyfunction!(number_attracting_components, m)?)?;
    m.add_function(wrap_pyfunction!(is_attracting_component, m)?)?;
    // Cycle algorithms — additional
    m.add_function(wrap_pyfunction!(girth, m)?)?;
    m.add_function(wrap_pyfunction!(find_negative_cycle, m)?)?;
    // Graph predicates
    m.add_function(wrap_pyfunction!(is_graphical, m)?)?;
    m.add_function(wrap_pyfunction!(is_digraphical, m)?)?;
    m.add_function(wrap_pyfunction!(is_multigraphical, m)?)?;
    m.add_function(wrap_pyfunction!(is_pseudographical, m)?)?;
    m.add_function(wrap_pyfunction!(is_regular, m)?)?;
    m.add_function(wrap_pyfunction!(is_k_regular, m)?)?;
    m.add_function(wrap_pyfunction!(is_tournament, m)?)?;
    m.add_function(wrap_pyfunction!(is_weighted, m)?)?;
    m.add_function(wrap_pyfunction!(is_negatively_weighted, m)?)?;
    m.add_function(wrap_pyfunction!(is_path, m)?)?;
    m.add_function(wrap_pyfunction!(is_distance_regular, m)?)?;
    // Traversal algorithms — additional
    m.add_function(wrap_pyfunction!(edge_bfs, m)?)?;
    m.add_function(wrap_pyfunction!(edge_dfs, m)?)?;
    // Matching algorithms — additional
    m.add_function(wrap_pyfunction!(is_edge_cover, m)?)?;
    m.add_function(wrap_pyfunction!(max_weight_clique, m)?)?;
    // DAG algorithms — additional
    m.add_function(wrap_pyfunction!(is_aperiodic, m)?)?;
    m.add_function(wrap_pyfunction!(antichains, m)?)?;
    m.add_function(wrap_pyfunction!(immediate_dominators, m)?)?;
    m.add_function(wrap_pyfunction!(dominance_frontiers, m)?)?;
    // Graph metrics — expansion, conductance, volume
    m.add_function(wrap_pyfunction!(volume, m)?)?;
    m.add_function(wrap_pyfunction!(boundary_expansion, m)?)?;
    m.add_function(wrap_pyfunction!(conductance, m)?)?;
    m.add_function(wrap_pyfunction!(edge_expansion, m)?)?;
    m.add_function(wrap_pyfunction!(node_expansion, m)?)?;
    m.add_function(wrap_pyfunction!(mixing_expansion, m)?)?;
    m.add_function(wrap_pyfunction!(non_edges, m)?)?;
    m.add_function(wrap_pyfunction!(average_node_connectivity, m)?)?;
    m.add_function(wrap_pyfunction!(is_k_edge_connected, m)?)?;
    m.add_function(wrap_pyfunction!(all_pairs_dijkstra, m)?)?;
    m.add_function(wrap_pyfunction!(number_of_spanning_arborescences, m)?)?;
    m.add_function(wrap_pyfunction!(global_node_connectivity, m)?)?;
    // Stoer-Wagner min cut
    m.add_function(wrap_pyfunction!(stoer_wagner, m)?)?;
    // Chain decomposition
    m.add_function(wrap_pyfunction!(chain_decomposition, m)?)?;
    // All topological sorts
    m.add_function(wrap_pyfunction!(all_topological_sorts_rust, m)?)?;
    // Structural holes
    m.add_function(wrap_pyfunction!(constraint_rust, m)?)?;
    m.add_function(wrap_pyfunction!(local_constraint_rust, m)?)?;
    m.add_function(wrap_pyfunction!(effective_size_rust, m)?)?;
    // Voronoi cells
    m.add_function(wrap_pyfunction!(voronoi_cells_rust, m)?)?;
    // D-separation
    m.add_function(wrap_pyfunction!(is_d_separator_rust, m)?)?;
    // Edge/node disjoint paths
    m.add_function(wrap_pyfunction!(edge_disjoint_paths_rust, m)?)?;
    m.add_function(wrap_pyfunction!(node_disjoint_paths_rust, m)?)?;
    // Clustering (Rust)
    m.add_function(wrap_pyfunction!(clustering_rust, m)?)?;
    m.add_function(wrap_pyfunction!(average_clustering_rust, m)?)?;
    m.add_function(wrap_pyfunction!(transitivity_rust, m)?)?;
    // Generalized degree
    m.add_function(wrap_pyfunction!(generalized_degree_rust, m)?)?;
    // Is strongly regular
    m.add_function(wrap_pyfunction!(is_strongly_regular_rust, m)?)?;
    // Flow hierarchy
    m.add_function(wrap_pyfunction!(flow_hierarchy_rust, m)?)?;
    // Graph power
    m.add_function(wrap_pyfunction!(power_rust, m)?)?;
    // Square clustering
    m.add_function(wrap_pyfunction!(square_clustering_rust, m)?)?;
    // Ego graph
    m.add_function(wrap_pyfunction!(ego_graph_rust, m)?)?;
    // Degree mixing
    m.add_function(wrap_pyfunction!(degree_mixing_dict_rust, m)?)?;
    // Connected dominating set
    m.add_function(wrap_pyfunction!(connected_dominating_set_rust, m)?)?;
    // Triadic census
    m.add_function(wrap_pyfunction!(triadic_census_rust, m)?)?;
    // Attribute mixing/assortativity
    m.add_function(wrap_pyfunction!(attribute_mixing_dict_rust, m)?)?;
    m.add_function(wrap_pyfunction!(attribute_assortativity_rust, m)?)?;
    // AT-free
    m.add_function(wrap_pyfunction!(is_at_free_rust, m)?)?;
    // Double edge swap
    m.add_function(wrap_pyfunction!(double_edge_swap_rust, m)?)?;
    // Global parameters
    m.add_function(wrap_pyfunction!(global_parameters_rust, m)?)?;
    // BFS labeled edges
    m.add_function(wrap_pyfunction!(bfs_labeled_edges_rust, m)?)?;
    // Full join
    m.add_function(wrap_pyfunction!(full_join_rust, m)?)?;
    // Identified nodes
    m.add_function(wrap_pyfunction!(identified_nodes_rust, m)?)?;
    // All triads
    m.add_function(wrap_pyfunction!(all_triads_rust, m)?)?;
    // Node degree xy
    m.add_function(wrap_pyfunction!(node_degree_xy_rust, m)?)?;
    // Dedensify
    m.add_function(wrap_pyfunction!(dedensify_rust, m)?)?;
    // Numeric assortativity
    m.add_function(wrap_pyfunction!(numeric_assortativity_coefficient_rust, m)?)?;
    // Group closeness centrality
    m.add_function(wrap_pyfunction!(group_closeness_centrality_rust, m)?)?;
    // Get node/edge attributes
    m.add_function(wrap_pyfunction!(get_node_attributes_rust, m)?)?;
    m.add_function(wrap_pyfunction!(get_edge_attributes_rust, m)?)?;
    // Quotient graph
    m.add_function(wrap_pyfunction!(quotient_graph_rust, m)?)?;
    // Moral graph
    m.add_function(wrap_pyfunction!(moral_graph_rust, m)?)?;
    // Distance indices
    m.add_function(wrap_pyfunction!(gutman_index_rust, m)?)?;
    m.add_function(wrap_pyfunction!(hyper_wiener_index_rust, m)?)?;
    m.add_function(wrap_pyfunction!(schultz_index_rust, m)?)?;
    m.add_function(wrap_pyfunction!(harmonic_diameter_rust, m)?)?;
    // Self-loop functions
    m.add_function(wrap_pyfunction!(selfloop_edges_rust, m)?)?;
    m.add_function(wrap_pyfunction!(number_of_selfloops_rust, m)?)?;
    m.add_function(wrap_pyfunction!(nodes_with_selfloops_rust, m)?)?;
    // To dict of lists
    m.add_function(wrap_pyfunction!(to_dict_of_lists_rust, m)?)?;
    // CN Soundarajan-Hopcroft
    m.add_function(wrap_pyfunction!(cn_soundarajan_hopcroft_rust, m)?)?;
    // Triad type
    m.add_function(wrap_pyfunction!(triad_type_rust, m)?)?;
    // BFS beam edges
    m.add_function(wrap_pyfunction!(bfs_beam_edges_rust, m)?)?;
    // All neighbors directed
    m.add_function(wrap_pyfunction!(all_neighbors_directed_rust, m)?)?;
    // Local bridges
    m.add_function(wrap_pyfunction!(local_bridges_rust, m)?)?;
    // Generic BFS edges
    m.add_function(wrap_pyfunction!(generic_bfs_edges_rust, m)?)?;
    // Graph info
    m.add_function(wrap_pyfunction!(graph_info_rust, m)?)?;
    // LCA
    m.add_function(wrap_pyfunction!(all_pairs_lca_rust, m)?)?;
    // Generate edgelist
    m.add_function(wrap_pyfunction!(generate_edgelist_rust, m)?)?;
    // Group betweenness
    m.add_function(wrap_pyfunction!(group_betweenness_centrality_rust, m)?)?;
    // Attribute assortativity
    m.add_function(wrap_pyfunction!(attribute_assortativity_coefficient_rust, m)?)?;
    Ok(())
}
