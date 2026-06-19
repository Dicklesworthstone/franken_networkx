//! Python bindings for FrankenNetworkX algorithms.
//!
//! Each function follows the NetworkX API signature, accepts a `Graph` or `DiGraph`,
//! delegates to the Rust implementation in `fnx_algorithms`, and returns
//! Python-native types (lists, dicts, floats, bools).

use crate::digraph::{PyDiGraph, PyMultiDiGraph};
use crate::{
    NetworkXError, NetworkXNoCycle, NetworkXNoPath, NetworkXNotImplemented, NetworkXUnfeasible,
    NodeNotFound, NotAPartition, PowerIterationFailedConvergence, PyGraph, PyMultiGraph, PyObject,
    PythonAllowThreadsExt, node_key_to_string,
};
use fnx_classes::AttrMap;
use pyo3::class::basic::CompareOp;
use pyo3::exceptions::{
    PyIndexError, PyKeyError, PyRuntimeError, PyValueError, PyZeroDivisionError,
};
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyInt, PyIterator, PyList, PySet, PyTuple};
use std::cell::OnceCell;
use std::collections::{BinaryHeap, HashMap, HashSet};
use std::sync::atomic::{AtomicBool, Ordering};

type SpanningEdgeSamples = (Vec<(String, String)>, Vec<f64>);
const PAGERANK_WEIGHT_ATTR: &str = "__fnx_pagerank_weight__";

#[derive(Copy, Clone, PartialEq)]
struct PyDijkstraState {
    dist: f64,
    seq: u64,
    node: usize,
}

impl Eq for PyDijkstraState {}

impl PartialOrd for PyDijkstraState {
    fn partial_cmp(&self, other: &Self) -> Option<std::cmp::Ordering> {
        Some(self.cmp(other))
    }
}

impl Ord for PyDijkstraState {
    fn cmp(&self, other: &Self) -> std::cmp::Ordering {
        other
            .dist
            .partial_cmp(&self.dist)
            .unwrap_or(std::cmp::Ordering::Equal)
            .then_with(|| other.seq.cmp(&self.seq))
    }
}

// ---------------------------------------------------------------------------
// GraphRef — unified graph access for algorithms accepting both Graph & DiGraph
// ---------------------------------------------------------------------------

/// Unified graph reference for algorithm bindings that accept Graph, DiGraph,
/// MultiGraph, or MultiDiGraph.
///
/// For undirected graphs, borrows the inner `Graph` directly.
/// For directed graphs, converts to undirected lazily and stores the result.
/// For multigraphs, converts to simple graph (collapsing parallel edges) lazily.
pub(crate) enum GraphRef<'py> {
    Undirected(PyRef<'py, PyGraph>),
    Directed {
        dg: PyRef<'py, PyDiGraph>,
        undirected: OnceCell<Box<fnx_classes::Graph>>,
    },
    /// MultiGraph converted to simple undirected Graph lazily.
    MultiUndirected {
        mg: PyRef<'py, PyMultiGraph>,
        simple: OnceCell<Box<fnx_classes::Graph>>,
    },
    /// MultiDiGraph converted to simple DiGraph (+ its undirected projection) lazily.
    MultiDirected {
        mdg: PyRef<'py, PyMultiDiGraph>,
        simple_dg: OnceCell<Box<fnx_classes::digraph::DiGraph>>,
        undirected: OnceCell<Box<fnx_classes::Graph>>,
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
            GraphRef::Directed { dg, undirected } => {
                undirected.get_or_init(|| Box::new(dg.inner.to_undirected()))
            }
            GraphRef::MultiUndirected { mg, simple } => {
                simple.get_or_init(|| Box::new(multigraph_to_simple_graph(&mg.inner)))
            }
            GraphRef::MultiDirected {
                mdg,
                simple_dg,
                undirected,
            } => undirected.get_or_init(|| {
                let simple =
                    simple_dg.get_or_init(|| Box::new(multidigraph_to_simple_digraph(&mdg.inner)));
                Box::new(simple.to_undirected())
            }),
        }
    }

    /// Convert a canonical node key to Python object.
    fn py_node_key(&self, py: Python<'_>, canonical: &str) -> PyObject {
        if let GraphRef::Undirected(pg) = self {
            return pg.py_node_key(py, canonical);
        }
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

    /// br-r37-c1-wvbzw: adjacency-ROW display object — nx traversal
    /// iterators yield neighbors as the objects stored in `G.adj[u]`
    /// (the z6uka per-row overrides for mixed hash-equal keys), not the
    /// node-map object. Directed rows are succ rows.
    fn py_row_key(&self, py: Python<'_>, owner: &str, nbr: &str) -> PyObject {
        match self {
            GraphRef::Undirected(pg) => pg.py_adj_key(py, owner, nbr),
            GraphRef::Directed { dg, .. } => dg.py_succ_key(py, owner, nbr),
            GraphRef::MultiUndirected { mg, .. } => mg.py_adj_key(py, owner, nbr),
            GraphRef::MultiDirected { mdg, .. } => mdg.py_succ_key(py, owner, nbr),
        }
    }

    /// br-r37-c1-6hpa9: PRED-row display object — reverse traversals
    /// iterate `G.pred[u]` in nx, so discovered nodes carry the pred-row
    /// override. Undirected graphs have a single row space.
    fn py_pred_row_key(&self, py: Python<'_>, owner: &str, nbr: &str) -> PyObject {
        match self {
            GraphRef::Undirected(pg) => pg.py_adj_key(py, owner, nbr),
            GraphRef::Directed { dg, .. } => dg.py_pred_key(py, owner, nbr),
            GraphRef::MultiUndirected { mg, .. } => mg.py_adj_key(py, owner, nbr),
            GraphRef::MultiDirected { mdg, .. } => mdg.py_pred_key(py, owner, nbr),
        }
    }

    /// br-r37-c1-6hpa9: build the DISCOVERY-object map from a canonical
    /// tree-edge stream — the seed as passed, every discovered node as
    /// its parent's row object (pred rows when `reverse`). Roots not in
    /// the map fall back to the node-map object via `disp_or_node_key`.
    fn discovery_map(
        &self,
        py: Python<'_>,
        edges: &[(String, String)],
        seed: Option<(&str, PyObject)>,
        reverse: bool,
    ) -> std::collections::HashMap<String, PyObject> {
        let mut disp: std::collections::HashMap<String, PyObject> =
            std::collections::HashMap::with_capacity(edges.len() + 1);
        if let Some((k, s)) = seed {
            disp.insert(k.to_owned(), s);
        }
        for (u, v) in edges {
            if !disp.contains_key(u.as_str()) {
                disp.insert(u.clone(), self.py_node_key(py, u));
            }
            let v_obj = if reverse {
                self.py_pred_row_key(py, u, v)
            } else {
                self.py_row_key(py, u, v)
            };
            disp.insert(v.clone(), v_obj);
        }
        disp
    }

    /// br-r37-c1-6hpa9: discovery object with node-map fallback.
    fn disp_or_node_key(
        &self,
        py: Python<'_>,
        disp: &std::collections::HashMap<String, PyObject>,
        key: &str,
    ) -> PyObject {
        disp.get(key)
            .map_or_else(|| self.py_node_key(py, key), |o| o.clone_ref(py))
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

    fn node_count_original(&self) -> usize {
        match self {
            GraphRef::Undirected(pg) => pg.inner.node_count(),
            GraphRef::Directed { dg, .. } => dg.inner.node_count(),
            GraphRef::MultiUndirected { mg, .. } => mg.inner.node_count(),
            GraphRef::MultiDirected { mdg, .. } => mdg.inner.node_count(),
        }
    }

    fn edge_count_original(&self) -> usize {
        match self {
            GraphRef::Undirected(pg) => pg.inner.edge_count(),
            GraphRef::Directed { dg, .. } => dg.inner.edge_count(),
            GraphRef::MultiUndirected { mg, .. } => mg.inner.edge_count(),
            GraphRef::MultiDirected { mdg, .. } => mdg.inner.edge_count(),
        }
    }

    fn graph_description(&self) -> String {
        let prefix = match self {
            GraphRef::Undirected(_) => "Graph",
            GraphRef::Directed { .. } => "DiGraph",
            GraphRef::MultiUndirected { .. } => "MultiGraph",
            GraphRef::MultiDirected { .. } => "MultiDiGraph",
        };
        format!(
            "{prefix} with {} nodes and {} edges",
            self.node_count_original(),
            self.edge_count_original()
        )
    }

    fn total_degree_sequence(&self) -> Vec<usize> {
        let mut degrees: Vec<usize> = match self {
            GraphRef::Undirected(pg) => pg
                .inner
                .nodes_ordered()
                .iter()
                .map(|node| pg.inner.degree(node))
                .collect(),
            GraphRef::Directed { dg, .. } => dg
                .inner
                .nodes_ordered()
                .iter()
                .map(|node| dg.inner.degree(node))
                .collect(),
            GraphRef::MultiUndirected { mg, .. } => mg
                .inner
                .nodes_ordered()
                .iter()
                .map(|node| mg.inner.degree(node))
                .collect(),
            GraphRef::MultiDirected { mdg, .. } => mdg
                .inner
                .nodes_ordered()
                .iter()
                .map(|node| mdg.inner.degree(node))
                .collect(),
        };
        degrees.sort_unstable();
        degrees
    }

    /// Is this a multigraph?
    pub(crate) fn is_multigraph(&self) -> bool {
        matches!(
            self,
            GraphRef::MultiUndirected { .. } | GraphRef::MultiDirected { .. }
        )
    }

    /// Get a reference to the inner DiGraph (for directed-specific algorithms).
    /// Returns `None` for undirected graphs.
    pub(crate) fn digraph(&self) -> Option<&fnx_classes::digraph::DiGraph> {
        match self {
            GraphRef::Directed { dg, .. } => Some(&dg.inner),
            GraphRef::MultiDirected { mdg, simple_dg, .. } => {
                Some(simple_dg.get_or_init(|| Box::new(multidigraph_to_simple_digraph(&mdg.inner))))
            }
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

    fn node_attrs_for(&self, canonical: &str) -> Option<&Py<PyDict>> {
        match self {
            GraphRef::Undirected(pg) => pg.node_py_attrs.get(canonical),
            GraphRef::Directed { dg, .. } => dg.node_py_attrs.get(canonical),
            GraphRef::MultiUndirected { mg, .. } => mg.node_py_attrs.get(canonical),
            GraphRef::MultiDirected { mdg, .. } => mdg.node_py_attrs.get(canonical),
        }
    }

    fn graph_attrs(&self) -> &Py<PyDict> {
        match self {
            GraphRef::Undirected(pg) => &pg.graph_attrs,
            GraphRef::Directed { dg, .. } => &dg.graph_attrs,
            GraphRef::MultiUndirected { mg, .. } => &mg.graph_attrs,
            GraphRef::MultiDirected { mdg, .. } => &mdg.graph_attrs,
        }
    }

    fn nodes_ordered(&self) -> Vec<&str> {
        match self {
            GraphRef::Undirected(pg) => pg.inner.nodes_ordered(),
            GraphRef::Directed { dg, .. } => dg.inner.nodes_ordered(),
            GraphRef::MultiUndirected { mg, .. } => mg.inner.nodes_ordered(),
            GraphRef::MultiDirected { mdg, .. } => mdg.inner.nodes_ordered(),
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
                let keys = mg.inner.edge_keys(left, right)?;
                let key = keys.first()?;
                let ek = PyMultiGraph::edge_key(left, right, *key);
                mg.edge_py_attrs.get(&ek)
            }
            GraphRef::MultiDirected { mdg, .. } => {
                if let Some(keys) = mdg.inner.edge_keys(left, right)
                    && let Some(key) = keys.first()
                {
                    let ek = (left.to_owned(), right.to_owned(), *key);
                    if let Some(attrs) = mdg.edge_py_attrs.get(&ek) {
                        return Some(attrs);
                    }
                }
                if let Some(keys) = mdg.inner.edge_keys(right, left)
                    && let Some(key) = keys.first()
                {
                    let ek = (right.to_owned(), left.to_owned(), *key);
                    if let Some(attrs) = mdg.edge_py_attrs.get(&ek) {
                        return Some(attrs);
                    }
                }
                None
            }
        }
    }

    /// Look up edge attributes from the original graph for a directed edge.
    #[allow(dead_code)]
    fn edge_attrs_for_directed(&self, source: &str, target: &str) -> Option<&Py<PyDict>> {
        match self {
            GraphRef::Directed { dg, .. } => {
                let ek = (source.to_owned(), target.to_owned());
                dg.edge_py_attrs.get(&ek)
            }
            GraphRef::MultiDirected { mdg, .. } => {
                let key = mdg.inner.edge_keys(source, target)?.first().copied()?;
                let key = &key;
                let ek = (source.to_owned(), target.to_owned(), *key);
                mdg.edge_py_attrs.get(&ek)
            }
            _ => self.edge_attrs_for_undirected(source, target),
        }
    }

    fn weighted_undirected_projection(&self, weight_attr: &str) -> WeightedGraphProjection<'_> {
        match self {
            GraphRef::Undirected(pg) => WeightedGraphProjection::Borrowed(&pg.inner),
            GraphRef::Directed { .. } => WeightedGraphProjection::Borrowed(self.undirected()),
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

    fn dijkstra_weighted_undirected_projection(
        &self,
        py: Python<'_>,
        weight_attr: &str,
    ) -> PyResult<WeightedGraphProjection<'_>> {
        match self {
            GraphRef::Undirected(pg) => Ok(WeightedGraphProjection::Owned(Box::new(
                dijkstra_single_weight_graph_projection(py, pg, weight_attr)?,
            ))),
            GraphRef::Directed { .. } => Ok(WeightedGraphProjection::Borrowed(self.undirected())),
            GraphRef::MultiUndirected { mg, .. } => Ok(WeightedGraphProjection::Owned(Box::new(
                multigraph_to_weighted_simple_graph(&mg.inner, weight_attr),
            ))),
            GraphRef::MultiDirected { .. } => {
                Ok(WeightedGraphProjection::Borrowed(self.undirected()))
            }
        }
    }

    fn dijkstra_weighted_digraph_projection(
        &self,
        py: Python<'_>,
        weight_attr: &str,
    ) -> PyResult<Option<WeightedDiGraphProjection<'_>>> {
        match self {
            GraphRef::Directed { dg, .. } => Ok(Some(WeightedDiGraphProjection::Owned(Box::new(
                dijkstra_single_weight_digraph_projection(py, dg, weight_attr)?,
            )))),
            GraphRef::MultiDirected { mdg, .. } => {
                Ok(Some(WeightedDiGraphProjection::Owned(Box::new(
                    multidigraph_to_weighted_simple_digraph(&mdg.inner, weight_attr),
                ))))
            }
            _ => Ok(None),
        }
    }
}

/// Extract a `PyGraph`, `PyDiGraph`, `PyMultiGraph`, or `PyMultiDiGraph` from
/// a Python argument, converting multigraphs to simple graphs for algorithm dispatch.
pub(crate) fn extract_graph<'py>(g: &'py Bound<'py, PyAny>) -> PyResult<GraphRef<'py>> {
    if let Ok(pg) = g.extract::<PyRef<'py, PyGraph>>() {
        Ok(GraphRef::Undirected(pg))
    } else if let Ok(dg) = g.extract::<PyRef<'py, PyDiGraph>>() {
        Ok(GraphRef::Directed {
            dg,
            undirected: OnceCell::new(),
        })
    } else if let Ok(mg) = g.extract::<PyRef<'py, PyMultiGraph>>() {
        Ok(GraphRef::MultiUndirected {
            mg,
            simple: OnceCell::new(),
        })
    } else if let Ok(mdg) = g.extract::<PyRef<'py, PyMultiDiGraph>>() {
        Ok(GraphRef::MultiDirected {
            mdg,
            simple_dg: OnceCell::new(),
            undirected: OnceCell::new(),
        })
    } else {
        Err(pyo3::exceptions::PyTypeError::new_err(
            "expected Graph, DiGraph, MultiGraph, or MultiDiGraph",
        ))
    }
}

fn sync_rust_attrs_if_available(g: &Bound<'_, PyAny>) -> PyResult<()> {
    let Ok(sync) = g.getattr("_fnx_sync_attrs_to_inner") else {
        return Ok(());
    };
    if !sync.is_callable() {
        return Ok(());
    }
    match sync.call0() {
        Ok(_) => Ok(()),
        Err(err) => {
            if err.is_instance_of::<PyRuntimeError>(g.py())
                && err.to_string().contains("Already borrowed")
            {
                Ok(())
            } else {
                Err(err)
            }
        }
    }
}

fn sync_rust_attrs_for_non_simple(g: &Bound<'_, PyAny>) -> PyResult<()> {
    let is_simple_graph = g.extract::<PyRef<'_, PyGraph>>().is_ok();
    let is_simple_digraph = !is_simple_graph && g.extract::<PyRef<'_, PyDiGraph>>().is_ok();
    if is_simple_graph || is_simple_digraph {
        return Ok(());
    }
    sync_rust_attrs_if_available(g)
}

fn dijkstra_single_weight_attrs(
    py: Python<'_>,
    weight_attr: &str,
    value: Option<PyObject>,
) -> PyResult<AttrMap> {
    let mut attrs = AttrMap::new();
    if let Some(value) = value {
        attrs.insert(
            weight_attr.to_owned(),
            crate::py_value_to_cgse(value.bind(py))?,
        );
    }
    Ok(attrs)
}

fn dijkstra_single_weight_graph_projection(
    py: Python<'_>,
    pg: &PyGraph,
    weight_attr: &str,
) -> PyResult<fnx_classes::Graph> {
    let nodes: Vec<String> = pg
        .inner
        .nodes_ordered()
        .into_iter()
        .map(str::to_owned)
        .collect();
    let edge_indices = pg.inner.edges_ordered_indices();
    let mut edges: Vec<(usize, usize, AttrMap)> = Vec::with_capacity(edge_indices.len());
    for (left_idx, right_idx) in edge_indices {
        let left = pg
            .inner
            .get_node_name(left_idx)
            .expect("edge index endpoint refers to an existing node");
        let right = pg
            .inner
            .get_node_name(right_idx)
            .expect("edge index endpoint refers to an existing node");
        let attrs = dijkstra_single_weight_attrs(
            py,
            weight_attr,
            pg.edge_attr_py_value(py, left, right, weight_attr)?,
        )?;
        edges.push((left_idx, right_idx, attrs));
    }

    let mut projection = fnx_classes::Graph::new(pg.inner.mode());
    let _ = projection.extend_fresh_index_edges_with_attrs_unrecorded(nodes, edges);
    Ok(projection)
}

fn dijkstra_single_weight_digraph_projection(
    py: Python<'_>,
    dg: &PyDiGraph,
    weight_attr: &str,
) -> PyResult<fnx_classes::digraph::DiGraph> {
    let nodes: Vec<String> = dg
        .inner
        .nodes_ordered()
        .into_iter()
        .map(str::to_owned)
        .collect();
    let edge_indices = dg.inner.edges_ordered_indices();
    let mut edges: Vec<(usize, usize, AttrMap)> = Vec::with_capacity(edge_indices.len());
    for (source_idx, target_idx) in edge_indices {
        let source = dg
            .inner
            .get_node_name(source_idx)
            .expect("edge index endpoint refers to an existing node");
        let target = dg
            .inner
            .get_node_name(target_idx)
            .expect("edge index endpoint refers to an existing node");
        let attrs = dijkstra_single_weight_attrs(
            py,
            weight_attr,
            dg.edge_attr_py_value(py, source, target, weight_attr)?,
        )?;
        edges.push((source_idx, target_idx, attrs));
    }

    let mut projection = fnx_classes::digraph::DiGraph::new(dg.inner.mode());
    let _ = projection.extend_fresh_index_edges_with_attrs_unrecorded(nodes, edges);
    Ok(projection)
}

/// generators-matrix follow-up 2026-06-06: every projection below builds
/// its simple graph from `edges_ordered()` — a u-major adjacency walk
/// that HOISTS reverse-orientation cells to the u side, scrambling the
/// projection's row order vs the source multigraph (observable: BFS/DFS
/// tie-breaks on MultiGraphs diverged from nx when traversing from a
/// node whose row held a hoisted back-edge). Restore the source's row
/// orders after building.
fn mg_row_orders(mg: &fnx_classes::MultiGraph) -> Vec<(String, Vec<String>)> {
    mg.nodes_ordered()
        .iter()
        .map(|n| {
            (
                (*n).to_owned(),
                mg.neighbors(n)
                    .unwrap_or_default()
                    .iter()
                    .map(|s| (*s).to_owned())
                    .collect(),
            )
        })
        .collect()
}

fn mdg_row_orders(
    mdg: &fnx_classes::digraph::MultiDiGraph,
) -> (Vec<(String, Vec<String>)>, Vec<(String, Vec<String>)>) {
    let succ = mdg
        .nodes_ordered()
        .iter()
        .map(|n| {
            (
                (*n).to_owned(),
                mdg.successors(n)
                    .unwrap_or_default()
                    .iter()
                    .map(|s| (*s).to_owned())
                    .collect(),
            )
        })
        .collect();
    let pred = mdg
        .nodes_ordered()
        .iter()
        .map(|n| {
            (
                (*n).to_owned(),
                mdg.predecessors(n)
                    .unwrap_or_default()
                    .iter()
                    .map(|s| (*s).to_owned())
                    .collect(),
            )
        })
        .collect();
    (succ, pred)
}

/// Convert a MultiGraph to a simple Graph by collapsing parallel edges.
/// Edge attributes from the first parallel edge (key 0) are kept.
fn multigraph_to_simple_graph(mg: &fnx_classes::MultiGraph) -> fnx_classes::Graph {
    let runtime_policy = mg.runtime_policy().clone();
    let mut g = fnx_classes::Graph::with_runtime_policy(runtime_policy.clone());
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
    g.apply_row_orders(&mg_row_orders(mg)); // restore source row orders (u-major walk hoists)
    g.set_runtime_policy(runtime_policy);
    g
}

/// br-r37-c1-ccmulti: structure-only undirected simplification of a MultiGraph
/// for CONNECTIVITY (is_connected / connected_components /
/// number_connected_components). The full `multigraph_to_simple_graph` clones
/// every node/edge AttrMap and pays the per-element ledger tax via
/// add_*_with_attrs — ~24x nx, since extract_graph builds a fresh GraphRef per
/// call so the simple-graph OnceCell never persists. Connectivity needs only
/// the STRUCTURE, so build with the ledger-free bulk unrecorded inserts and no
/// attrs. Node order (nodes_ordered) is preserved so the connected_components
/// component ORDER matches nx; self-loops are kept (harmless for connectivity).
fn multigraph_to_simple_graph_structure_only(mg: &fnx_classes::MultiGraph) -> fnx_classes::Graph {
    let mut g = fnx_classes::Graph::with_runtime_policy(mg.runtime_policy().clone());
    let nodes = mg.nodes_ordered();
    let _ = g.extend_nodes_unrecorded(nodes.iter().map(|n| (*n).to_owned()));
    let mut edges: Vec<(String, String)> = Vec::new();
    for u in &nodes {
        if let Some(nbrs) = mg.neighbors(u) {
            for v in nbrs {
                if **u <= *v {
                    edges.push(((*u).to_owned(), v.to_owned()));
                }
            }
        }
    }
    let _ = g.extend_edges_unrecorded(edges);
    g
}

/// br-r37-c1-mexh6-dfs: structure-only simplification that ALSO restores each
/// node's source adjacency-row order (apply_row_orders), so DFS/BFS traversal
/// order matches nx's direct multigraph walk. Skips the attr clones + per-edge
/// ledger of the full `multigraph_to_simple_graph` (used by dfs_tree etc., ~14x
/// nx). apply_row_orders fixes the row order regardless of edge-insertion order.
#[allow(dead_code)] // br-r37-c1-86c7r: superseded by direct multigraph DFS/BFS walk; retained as a reusable order-preserving conversion
fn multigraph_to_simple_graph_structure_only_ordered(
    mg: &fnx_classes::MultiGraph,
) -> fnx_classes::Graph {
    let mut g = fnx_classes::Graph::with_runtime_policy(mg.runtime_policy().clone());
    let nodes = mg.nodes_ordered();
    let _ = g.extend_nodes_unrecorded(nodes.iter().map(|n| (*n).to_owned()));
    let mut edges: Vec<(String, String)> = Vec::new();
    for u in &nodes {
        if let Some(nbrs) = mg.neighbors(u) {
            for v in nbrs {
                if **u <= *v {
                    edges.push(((*u).to_owned(), v.to_owned()));
                }
            }
        }
    }
    let _ = g.extend_edges_unrecorded(edges);
    g.apply_row_orders(&mg_row_orders(mg));
    g
}

fn projected_weight(attrs: &AttrMap, weight_attr: &str) -> f64 {
    attrs
        .get(weight_attr)
        .and_then(|raw| raw.as_f64())
        .filter(|weight| weight.is_finite())
        .unwrap_or(1.0)
}

fn pagerank_projected_weight(attrs: &AttrMap, weight_attr: Option<&str>) -> f64 {
    let Some(weight_attr) = weight_attr else {
        return 1.0;
    };
    attrs
        .get(weight_attr)
        .and_then(|raw| raw.as_f64())
        .filter(|weight| weight.is_finite())
        .unwrap_or(1.0)
}

fn pagerank_weight_attrs(weight: f64) -> AttrMap {
    let mut attrs = AttrMap::new();
    attrs.insert(PAGERANK_WEIGHT_ATTR.to_owned(), weight.into());
    attrs
}

fn multigraph_to_pagerank_simple_graph(
    mg: &fnx_classes::MultiGraph,
    weight_attr: Option<&str>,
) -> fnx_classes::Graph {
    let runtime_policy = mg.runtime_policy().clone();
    let mut g = fnx_classes::Graph::with_runtime_policy(runtime_policy.clone());
    let mut weights = HashMap::<(String, String), f64>::new();

    for node in mg.nodes_ordered() {
        let attrs = mg.node_attrs(node).cloned().unwrap_or_default();
        g.add_node_with_attrs(node.to_owned(), attrs);
    }

    for edge in mg.edges_ordered() {
        let pair = (edge.left.clone(), edge.right.clone());
        *weights.entry(pair).or_insert(0.0) += pagerank_projected_weight(&edge.attrs, weight_attr);
    }

    for ((left, right), weight) in weights {
        let _ = g.add_edge_with_attrs(left, right, pagerank_weight_attrs(weight));
    }

    g.apply_row_orders(&mg_row_orders(mg)); // restore source row orders (u-major walk hoists)
    g.set_runtime_policy(runtime_policy);
    g
}

fn multidigraph_to_pagerank_simple_digraph(
    mdg: &fnx_classes::digraph::MultiDiGraph,
    weight_attr: Option<&str>,
) -> fnx_classes::digraph::DiGraph {
    let runtime_policy = mdg.runtime_policy().clone();
    let mut dg = fnx_classes::digraph::DiGraph::with_runtime_policy(runtime_policy.clone());
    let mut weights = HashMap::<(String, String), f64>::new();

    for node in mdg.nodes_ordered() {
        let attrs = mdg.node_attrs(node).cloned().unwrap_or_default();
        dg.add_node_with_attrs(node.to_owned(), attrs);
    }

    for edge in mdg.edges_ordered() {
        let pair = (edge.source.clone(), edge.target.clone());
        *weights.entry(pair).or_insert(0.0) += pagerank_projected_weight(&edge.attrs, weight_attr);
    }

    for ((source, target), weight) in weights {
        let _ = dg.add_edge_with_attrs(source, target, pagerank_weight_attrs(weight));
    }

    {
        let (succ_orders, pred_orders) = mdg_row_orders(mdg);
        dg.apply_row_orders(&succ_orders, false);
        dg.apply_row_orders(&pred_orders, true);
    } // restore source row orders (u-major walk hoists)
    dg.set_runtime_policy(runtime_policy);
    dg
}

/// Convert a MultiGraph to a simple Graph by choosing the minimum-weight
/// parallel edge for each node pair, matching NetworkX shortest-path semantics.
fn multigraph_to_weighted_simple_graph(
    mg: &fnx_classes::MultiGraph,
    weight_attr: &str,
) -> fnx_classes::Graph {
    let runtime_policy = mg.runtime_policy().clone();
    let mut g = fnx_classes::Graph::with_runtime_policy(runtime_policy.clone());
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

    g.apply_row_orders(&mg_row_orders(mg)); // restore source row orders (u-major walk hoists)
    g.set_runtime_policy(runtime_policy);
    g
}

/// Convert a MultiDiGraph to a simple DiGraph by collapsing parallel edges.
fn multidigraph_to_simple_digraph(
    mdg: &fnx_classes::digraph::MultiDiGraph,
) -> fnx_classes::digraph::DiGraph {
    let runtime_policy = mdg.runtime_policy().clone();
    let mut dg = fnx_classes::digraph::DiGraph::with_runtime_policy(runtime_policy.clone());
    for node in mdg.nodes_ordered() {
        let attrs = mdg.node_attrs(node).cloned().unwrap_or_default();
        dg.add_node_with_attrs(node.to_owned(), attrs);
    }
    for edge in mdg.edges_ordered() {
        if !dg.has_edge(&edge.source, &edge.target) {
            let _ = dg.add_edge_with_attrs(edge.source, edge.target, edge.attrs);
        }
    }
    {
        let (succ_orders, pred_orders) = mdg_row_orders(mdg);
        dg.apply_row_orders(&succ_orders, false);
        dg.apply_row_orders(&pred_orders, true);
    } // restore source row orders (u-major walk hoists)
    dg.set_runtime_policy(runtime_policy);
    dg
}

/// br-r37-c1-mexh6-dir: structure-only MultiDiGraph -> simple DiGraph for
/// order-INVARIANT directed algorithms (is_strongly_connected etc.). Skips the
/// attr clones + per-element ledger of multidigraph_to_simple_digraph (~61x nx
/// on is_strongly_connected). No apply_row_orders (callers are order-invariant).
fn multidigraph_to_simple_digraph_structure_only(
    mdg: &fnx_classes::digraph::MultiDiGraph,
) -> fnx_classes::digraph::DiGraph {
    let mut dg = fnx_classes::digraph::DiGraph::with_runtime_policy(mdg.runtime_policy().clone());
    let nodes = mdg.nodes_ordered();
    let _ = dg.extend_nodes_with_attrs_unrecorded(
        nodes
            .iter()
            .map(|n| ((*n).to_owned(), fnx_classes::AttrMap::new())),
    );
    let mut edges: Vec<(String, String)> = Vec::new();
    for u in &nodes {
        if let Some(succs) = mdg.successors(u) {
            for v in succs {
                edges.push(((*u).to_owned(), v.to_owned()));
            }
        }
    }
    let _ = dg.extend_edges_unrecorded(edges);
    dg
}

/// br-r37-c1-mexh6-dirtree: structure-only MultiDiGraph -> simple DiGraph that
/// ALSO restores each node's successor AND predecessor row order
/// (apply_row_orders), so DFS/BFS traversal order matches nx's direct
/// multidigraph walk. Directed sibling of
/// `multigraph_to_simple_graph_structure_only_ordered`: skips the attr clones +
/// per-edge `has_edge` ledger of the full `multidigraph_to_simple_digraph`
/// (which kept dfs_tree/bfs_tree ~14-16x nx on MultiDiGraph). `successors(u)`
/// already yields DISTINCT targets, so no parallel-edge dedup is needed.
#[allow(dead_code)] // br-r37-c1-86c7r: superseded by direct multigraph DFS/BFS walk; retained as a reusable order-preserving conversion
fn multidigraph_to_simple_digraph_structure_only_ordered(
    mdg: &fnx_classes::digraph::MultiDiGraph,
) -> fnx_classes::digraph::DiGraph {
    let mut dg = fnx_classes::digraph::DiGraph::with_runtime_policy(mdg.runtime_policy().clone());
    let nodes = mdg.nodes_ordered();
    let _ = dg.extend_nodes_with_attrs_unrecorded(
        nodes
            .iter()
            .map(|n| ((*n).to_owned(), fnx_classes::AttrMap::new())),
    );
    let mut edges: Vec<(String, String)> = Vec::new();
    for u in &nodes {
        if let Some(succs) = mdg.successors(u) {
            for v in succs {
                edges.push(((*u).to_owned(), v.to_owned()));
            }
        }
    }
    let _ = dg.extend_edges_unrecorded(edges);
    let (succ_orders, pred_orders) = mdg_row_orders(mdg);
    dg.apply_row_orders(&succ_orders, false);
    dg.apply_row_orders(&pred_orders, true);
    dg
}

/// Convert a MultiDiGraph to a simple DiGraph by choosing the minimum-weight
/// parallel edge for each directed edge, matching NetworkX shortest-path semantics.
fn multidigraph_to_weighted_simple_digraph(
    mdg: &fnx_classes::digraph::MultiDiGraph,
    weight_attr: &str,
) -> fnx_classes::digraph::DiGraph {
    let runtime_policy = mdg.runtime_policy().clone();
    let mut dg = fnx_classes::digraph::DiGraph::with_runtime_policy(runtime_policy.clone());
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

    {
        let (succ_orders, pred_orders) = mdg_row_orders(mdg);
        dg.apply_row_orders(&succ_orders, false);
        dg.apply_row_orders(&pred_orders, true);
    } // restore source row orders (u-major walk hoists)
    dg.set_runtime_policy(runtime_policy);
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

fn require_not_multigraph(gr: &GraphRef<'_>) -> PyResult<()> {
    if gr.is_multigraph() {
        return Err(crate::NetworkXNotImplemented::new_err(
            "not implemented for multigraph type",
        ));
    }
    Ok(())
}

fn require_directed(gr: &GraphRef<'_>, _algo_name: &str) -> PyResult<()> {
    if !gr.is_directed() {
        let msg = format!("{} is not defined for undirected graphs.", _algo_name);
        return Err(crate::NetworkXNotImplemented::new_err(msg));
    }
    Ok(())
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

fn validate_node(
    gr: &GraphRef<'_>,
    canonical: &str,
    py_key: &Bound<'_, PyAny>,
    prefix: &str,
) -> PyResult<()> {
    if !gr.has_node(canonical) {
        return Err(crate::NodeNotFound::new_err(format!(
            "{} {} is not in G",
            prefix,
            py_key.repr()?
        )));
    }
    Ok(())
}

fn validate_node_str(gr: &GraphRef<'_>, canonical: &str, prefix: &str) -> PyResult<()> {
    if !gr.has_node(canonical) {
        return Err(crate::NodeNotFound::new_err(format!(
            "{} '{}' is not in G",
            prefix, canonical
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
            // br-r37-c1-k4wsy: nx routes single-pair unweighted through
            // BIDIRECTIONAL BFS — the unidirectional kernel picked a
            // different (equal-length) path on tie-breaks.
            let result = py.allow_threads(|| {
                fnx_algorithms::bidirectional_shortest_path_meta(inner, source, target)
            });
            Ok(result.map(|p| p.into_iter().map(|(n, _, _)| n).collect()))
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
            // br-r37-c1-k4wsy: nx tie-break parity needs the bidirectional
            // walk (see compute_single_shortest_path).
            let result = py.allow_threads(|| {
                fnx_algorithms::bidirectional_shortest_path_directed_meta(inner, source, target)
            });
            Ok(result.map(|p| p.into_iter().map(|(n, _, _)| n).collect()))
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

/// br-r37-c1-6hpa9: returns the kernel's ORDERED Vec — the old
/// `.collect::<HashMap>()` scrambled the user-visible dict key order
/// (nx emits BFS/finalize order; HashMap iteration was nondeterministic).
fn compute_single_source_shortest_paths(
    py: Python<'_>,
    inner: &fnx_classes::Graph,
    source: &str,
    weight: Option<&str>,
    method: &str,
) -> PyResult<Vec<(String, Vec<String>)>> {
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

/// br-r37-c1-6hpa9: emit a {node: path} dict in kernel order with nx
/// DISCOVERY objects derived from the paths themselves — a node's
/// discovering parent is its path's second-to-last element (zero extra
/// walks).
fn emit_paths_dict_discovery(
    py: Python<'_>,
    gr: &GraphRef<'_>,
    paths: &[(String, Vec<String>)],
    source_key: &str,
    source_obj: PyObject,
) -> PyResult<pyo3::Py<PyDict>> {
    let mut disp: std::collections::HashMap<String, PyObject> =
        std::collections::HashMap::with_capacity(paths.len());
    disp.insert(source_key.to_owned(), source_obj);
    for (node, p) in paths {
        if p.len() >= 2 {
            let parent = &p[p.len() - 2];
            disp.insert(node.clone(), gr.py_row_key(py, parent, node));
        }
    }
    let dict = PyDict::new(py);
    for (node, p) in paths {
        let py_path: Vec<PyObject> = p
            .iter()
            .map(|n| gr.disp_or_node_key(py, &disp, n))
            .collect();
        dict.set_item(gr.disp_or_node_key(py, &disp, node), py_path)?;
    }
    Ok(dict.unbind())
}

/// br-r37-c1-ssspidx: index-space variant of [`emit_paths_dict_discovery`].
/// `paths` carries `(target_idx, path_indices)`; node names come from `nodes`
/// (no `String` allocation in the kernel). Display objects are deduped in
/// `disp` exactly as the String version, so the emitted dict is byte-identical.
fn emit_paths_dict_discovery_index(
    py: Python<'_>,
    gr: &GraphRef<'_>,
    paths: &[(usize, Vec<usize>)],
    nodes: &[&str],
    source_idx: usize,
    source_obj: PyObject,
) -> PyResult<pyo3::Py<PyDict>> {
    let mut disp: std::collections::HashMap<usize, PyObject> =
        std::collections::HashMap::with_capacity(paths.len());
    disp.insert(source_idx, source_obj);
    for (node_idx, p) in paths {
        if p.len() >= 2 {
            let parent_idx = p[p.len() - 2];
            disp.insert(
                *node_idx,
                gr.py_row_key(py, nodes[parent_idx], nodes[*node_idx]),
            );
        }
    }
    let dict = PyDict::new(py);
    for (node_idx, p) in paths {
        let py_path: Vec<PyObject> = p
            .iter()
            .map(|&i| match disp.get(&i) {
                Some(o) => o.clone_ref(py),
                None => gr.py_node_key(py, nodes[i]),
            })
            .collect();
        let key = match disp.get(node_idx) {
            Some(o) => o.clone_ref(py),
            None => gr.py_node_key(py, nodes[*node_idx]),
        };
        dict.set_item(key, py_path)?;
    }
    Ok(dict.unbind())
}

/// br-r37-c1-k4wsy: nx `shortest_path(G, target=t)` runs ONE level-BFS
/// from the target over pred rows (directed) / adj rows (undirected),
/// `paths[w] = [w] + paths[v]`, dict keys in discovery order (target
/// first), every node displayed as its reverse-walk discovery object.
/// `edges` is the reverse-BFS tree stream (parent = closer to target).
/// The old branch looped per-node bidirectional searches — O(V) walks
/// AND a different tie-break than nx's reverse tree.
fn emit_single_target_paths_dict(
    py: Python<'_>,
    gr: &GraphRef<'_>,
    edges: &[(String, String)],
    target_key: &str,
    target_obj: PyObject,
    directed: bool,
) -> PyResult<pyo3::Py<PyDict>> {
    let mut paths: std::collections::HashMap<String, Vec<String>> =
        std::collections::HashMap::with_capacity(edges.len() + 1);
    paths.insert(target_key.to_owned(), vec![target_key.to_owned()]);
    let mut disp: std::collections::HashMap<String, PyObject> =
        std::collections::HashMap::with_capacity(edges.len() + 1);
    disp.insert(target_key.to_owned(), target_obj.clone_ref(py));
    let dict = PyDict::new(py);
    dict.set_item(target_obj.clone_ref(py), vec![target_obj])?;
    for (parent, child) in edges {
        let mut p = Vec::with_capacity(paths[parent.as_str()].len() + 1);
        p.push(child.clone());
        p.extend_from_slice(&paths[parent.as_str()]);
        let child_obj = if directed {
            gr.py_pred_row_key(py, parent, child)
        } else {
            gr.py_row_key(py, parent, child)
        };
        disp.insert(child.clone(), child_obj);
        let py_path: Vec<PyObject> = p
            .iter()
            .map(|n| gr.disp_or_node_key(py, &disp, n))
            .collect();
        dict.set_item(gr.disp_or_node_key(py, &disp, child), py_path)?;
        paths.insert(child.clone(), p);
    }
    Ok(dict.unbind())
}

/// weighted sp(target) batch: nx runs single_source dijkstra/bellman on
/// `G.reverse(copy=False)` from the target, then flips each path. Keys
/// stay in the single-source dict order; discovery objects come from
/// PRED rows (the reverse view's adjacency). `paths` are the
/// reverse-orientation paths BEFORE flipping (target ... node order is
/// [target, ..., node] reversed at emission).
fn emit_reversed_target_paths_dict(
    py: Python<'_>,
    gr: &GraphRef<'_>,
    paths: &[(String, Vec<String>)],
    target_key: &str,
    target_obj: PyObject,
) -> PyResult<pyo3::Py<PyDict>> {
    let mut disp: std::collections::HashMap<String, PyObject> =
        std::collections::HashMap::with_capacity(paths.len() + 1);
    disp.insert(target_key.to_owned(), target_obj);
    for (node, p) in paths {
        if p.len() >= 2 {
            let parent = &p[p.len() - 2];
            disp.insert(node.clone(), gr.py_pred_row_key(py, parent, node));
        }
    }
    let dict = PyDict::new(py);
    for (node, p) in paths {
        let py_path: Vec<PyObject> = p
            .iter()
            .rev()
            .map(|n| gr.disp_or_node_key(py, &disp, n))
            .collect();
        dict.set_item(gr.disp_or_node_key(py, &disp, node), py_path)?;
    }
    Ok(dict.unbind())
}

/// br-r37-c1-6hpa9: ordered Vec — see compute_single_source_shortest_paths.
fn compute_single_source_shortest_paths_directed(
    py: Python<'_>,
    inner: &fnx_classes::digraph::DiGraph,
    source: &str,
    weight: Option<&str>,
    method: &str,
) -> PyResult<Vec<(String, Vec<String>)>> {
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

fn graph_degree_centrality_to_dict(py: Python<'_>, pg: &PyGraph) -> PyResult<Py<PyDict>> {
    let inner = &pg.inner;
    let n = inner.node_count();
    let dict = PyDict::new(py);
    if n == 0 {
        return Ok(dict.unbind());
    }
    if n <= 1 {
        for idx in 0..n {
            let node = inner
                .get_node_name(idx)
                .expect("degree centrality index must resolve to node");
            dict.set_item(pg.py_node_key(py, node), 1.0)?;
        }
        return Ok(dict.unbind());
    }

    let reciprocal = 1.0 / ((n - 1) as f64);
    for idx in 0..n {
        let node = inner
            .get_node_name(idx)
            .expect("degree centrality index must resolve to node");
        let score = (inner.degree_by_index(idx) as f64) * reciprocal;
        dict.set_item(pg.py_node_key(py, node), score)?;
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
                for node in gr
                    .digraph()
                    .expect("is_directed checked above")
                    .nodes_ordered()
                {
                    let adjacency = PyDict::new(py).unbind();
                    if let Some(neighbors) = gr
                        .digraph()
                        .expect("is_directed checked above")
                        .successors_iter(node)
                    {
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
    let runtime_policy = inner.runtime_policy().clone();
    let mut sanitized = fnx_classes::Graph::with_runtime_policy(runtime_policy.clone());

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

    sanitized.set_runtime_policy(runtime_policy);
    Ok(sanitized)
}

/// br-r37-c1-mstcsr: validate that no edge carries a NaN weight, raising the
/// exact networkx error (same `edges_ordered()` scan order and message as
/// `spanning_input_graph`) — but WITHOUT building a sanitized graph copy. For
/// the common `ignore_nan=false` path this lets the MST kernel run directly on
/// the original graph (the kernel reads the `weight` attr in place), avoiding
/// the O(V+E) construction tax that dominated the previous binding.
fn validate_spanning_no_nan(py: Python<'_>, gr: &GraphRef<'_>, weight: &str) -> PyResult<()> {
    let inner = gr.undirected();
    for edge in inner.edges_ordered() {
        let has_nan_weight = edge
            .attrs
            .get(weight)
            .and_then(|weight_value| weight_value.as_f64())
            .is_some_and(f64::is_nan);
        if has_nan_weight {
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
    }
    Ok(())
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
    let runtime_policy = pg.inner.runtime_policy().clone();
    let mut tree = PyGraph::new_empty_with_policy(py, runtime_policy.clone())?;
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

    tree.inner.set_runtime_policy(runtime_policy);
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

fn extract_partition_edges(
    py: Python<'_>,
    value: &Bound<'_, PyAny>,
) -> PyResult<Vec<(String, String)>> {
    let mut edges = Vec::new();
    for item in value.try_iter()? {
        let item = item?;
        let pair = item.downcast::<PyTuple>()?;
        if pair.len() != 2 {
            return Err(pyo3::exceptions::PyTypeError::new_err(
                "init_partition edges must be 2-tuples",
            ));
        }
        let source = node_key_to_string(py, &pair.get_item(0)?)?;
        let target = node_key_to_string(py, &pair.get_item(1)?)?;
        edges.push((source, target));
    }
    Ok(edges)
}

fn extract_init_partition(
    py: Python<'_>,
    init_partition: Option<&Bound<'_, PyAny>>,
) -> PyResult<(Vec<(String, String)>, Vec<(String, String)>)> {
    let Some(init_partition) = init_partition else {
        return Ok((Vec::new(), Vec::new()));
    };
    let tuple = init_partition.downcast::<PyTuple>()?;
    if tuple.len() != 2 {
        return Err(pyo3::exceptions::PyTypeError::new_err(
            "init_partition must be a 2-tuple of (included_edges, excluded_edges)",
        ));
    }
    let included = extract_partition_edges(py, &tuple.get_item(0)?)?;
    let excluded = extract_partition_edges(py, &tuple.get_item(1)?)?;
    Ok((included, excluded))
}

fn extract_edge_partition_from_attr(
    py: Python<'_>,
    dg: &PyDiGraph,
    partition_attr: &str,
) -> PyResult<(Vec<(String, String)>, Vec<(String, String)>)> {
    let mut included = Vec::new();
    let mut excluded = Vec::new();
    for edge in dg.inner.edges_ordered() {
        let key = PyDiGraph::edge_key(&edge.left, &edge.right);
        let Some(attrs) = dg.edge_py_attrs.get(&key) else {
            continue;
        };
        let attrs = attrs.bind(py);
        let Ok(value) = attrs.get_item(partition_attr) else {
            continue;
        };
        let Some(value) = value else {
            continue;
        };
        let value_str = value.str()?;
        let raw = value_str.to_str()?;
        match raw {
            "EdgePartition.INCLUDED" | "INCLUDED" | "Included" | "included" => {
                included.push((edge.left.clone(), edge.right.clone()));
            }
            "EdgePartition.EXCLUDED" | "EXCLUDED" | "Excluded" | "excluded" => {
                excluded.push((edge.left.clone(), edge.right.clone()));
            }
            _ => {}
        }
    }
    Ok((included, excluded))
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
    let runtime_policy = dg.inner.runtime_policy().clone();
    let mut tree = PyDiGraph::new_empty_with_policy(py, runtime_policy.clone())?;
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
    tree.inner.set_runtime_policy(runtime_policy);
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
                    validate_node(&gr, &s, src, "Source")?;
                    validate_node(&gr, &t, tgt, "Target")?;

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
                    validate_node(&gr, &s, src, "Source")?;
                    let paths = compute_single_source_shortest_paths_directed(
                        py,
                        inner,
                        &s,
                        Some(weight_attr),
                        method,
                    )?;
                    // weighted sp batch: kernel dict order (dijkstra
                    // finalize / bellman SPFA discovery) + discovery
                    // objects (a node's parent is its path's
                    // second-to-last element — same trick as unweighted).
                    let dict =
                        emit_paths_dict_discovery(py, &gr, &paths, &s, src.clone().unbind())?;
                    Ok(dict.into_any())
                }
                (None, Some(tgt)) => {
                    let t = node_key_to_string(py, tgt)?;
                    validate_node(&gr, &t, tgt, "Target")?;
                    // weighted sp batch: nx runs single_source on
                    // G.reverse(copy=False) from the target and flips
                    // each path — ONE walk (the old per-node loop was
                    // O(V) single-pair searches AND different
                    // tie-breaks), pred-row discovery objects.
                    let reversed = py.allow_threads(|| fnx_algorithms::reverse_digraph(inner));
                    let paths = compute_single_source_shortest_paths_directed(
                        py,
                        &reversed,
                        &t,
                        Some(weight_attr),
                        method,
                    )?;
                    let dict =
                        emit_reversed_target_paths_dict(py, &gr, &paths, &t, tgt.clone().unbind())?;
                    Ok(dict.into_any())
                }
                (None, None) => {
                    let result = PyDict::new(py);
                    for src_node in inner.nodes_ordered() {
                        let paths = compute_single_source_shortest_paths_directed(
                            py,
                            inner,
                            src_node,
                            Some(weight_attr),
                            method,
                        )?;
                        // weighted sp batch: all-pairs sources keep their
                        // node-map object (nx iterates G).
                        let inner_dict = emit_paths_dict_discovery(
                            py,
                            &gr,
                            &paths,
                            src_node,
                            gr.py_node_key(py, src_node),
                        )?;
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
                    validate_node(&gr, &s, src, "Source")?;
                    validate_node(&gr, &t, tgt, "Target")?;

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
                    validate_node(&gr, &s, src, "Source")?;
                    let paths = compute_single_source_shortest_paths(
                        py,
                        inner,
                        &s,
                        Some(weight_attr),
                        method,
                    )?;
                    // weighted sp batch: kernel order + discovery objects.
                    let dict =
                        emit_paths_dict_discovery(py, &gr, &paths, &s, src.clone().unbind())?;
                    Ok(dict.into_any())
                }
                (None, Some(tgt)) => {
                    let t = node_key_to_string(py, tgt)?;
                    validate_node(&gr, &t, tgt, "Target")?;
                    let paths = compute_single_source_shortest_paths(
                        py,
                        inner,
                        &t,
                        Some(weight_attr),
                        method,
                    )?;
                    // weighted sp batch: undirected target-only = same
                    // graph from target, paths flipped, adj-row discovery
                    // (py_pred_row_key == py_adj_key for undirected).
                    let dict =
                        emit_reversed_target_paths_dict(py, &gr, &paths, &t, tgt.clone().unbind())?;
                    Ok(dict.into_any())
                }
                (None, None) => {
                    let result = PyDict::new(py);
                    for src_node in inner.nodes_ordered() {
                        let paths = compute_single_source_shortest_paths(
                            py,
                            inner,
                            src_node,
                            Some(weight_attr),
                            method,
                        )?;
                        // weighted sp batch: all-pairs sources keep their
                        // node-map object (nx iterates G).
                        let inner_dict = emit_paths_dict_discovery(
                            py,
                            &gr,
                            &paths,
                            src_node,
                            gr.py_node_key(py, src_node),
                        )?;
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
                validate_node(&gr, &s, src, "Source")?;
                validate_node(&gr, &t, tgt, "Target")?;

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
                validate_node(&gr, &s, src, "Source")?;
                let paths =
                    compute_single_source_shortest_paths_directed(py, inner, &s, None, method)?;
                // br-r37-c1-6hpa9: kernel order + discovery objects.
                let dict = emit_paths_dict_discovery(py, &gr, &paths, &s, src.clone().unbind())?;
                Ok(dict.into_any())
            }
            (None, Some(tgt)) => {
                let t = node_key_to_string(py, tgt)?;
                validate_node(&gr, &t, tgt, "Target")?;
                // br-r37-c1-k4wsy: ONE reverse level-BFS like nx's
                // single_target_shortest_path (key order, tie-breaks,
                // pred-row discovery objects) — replaces the O(V)
                // per-node bidirectional loop.
                let edges = py
                    .allow_threads(|| fnx_algorithms::bfs_edges_directed_reverse(inner, &t, None));
                let dict =
                    emit_single_target_paths_dict(py, &gr, &edges, &t, tgt.clone().unbind(), true)?;
                Ok(dict.into_any())
            }
            (None, None) => {
                let result = PyDict::new(py);
                for src_node in inner.nodes_ordered() {
                    let paths = compute_single_source_shortest_paths_directed(
                        py, inner, src_node, None, method,
                    )?;
                    // br-r37-c1-6hpa9: all-pairs sources keep their node-map
                    // object (nx iterates G).
                    let inner_dict = emit_paths_dict_discovery(
                        py,
                        &gr,
                        &paths,
                        src_node,
                        gr.py_node_key(py, src_node),
                    )?;
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
                    validate_node(&gr, &s, src, "Source")?;
                    validate_node(&gr, &t, tgt, "Target")?;

                    let path =
                        compute_single_shortest_path_directed(py, inner, &s, &t, None, method)?;
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
                    validate_node(&gr, &s, src, "Source")?;
                    let paths =
                        compute_single_source_shortest_paths_directed(py, inner, &s, None, method)?;
                    // br-r37-c1-6hpa9: kernel order + discovery objects.
                    let dict =
                        emit_paths_dict_discovery(py, &gr, &paths, &s, src.clone().unbind())?;
                    Ok(dict.into_any())
                }
                (None, Some(tgt)) => {
                    let t = node_key_to_string(py, tgt)?;
                    validate_node(&gr, &t, tgt, "Target")?;
                    // br-r37-c1-k4wsy: see the fast-path branch above.
                    let edges = py.allow_threads(|| {
                        fnx_algorithms::bfs_edges_directed_reverse(inner, &t, None)
                    });
                    let dict = emit_single_target_paths_dict(
                        py,
                        &gr,
                        &edges,
                        &t,
                        tgt.clone().unbind(),
                        true,
                    )?;
                    Ok(dict.into_any())
                }
                (None, None) => {
                    let result = PyDict::new(py);
                    for src_node in inner.nodes_ordered() {
                        let paths = compute_single_source_shortest_paths_directed(
                            py, inner, src_node, None, method,
                        )?;
                        // br-r37-c1-6hpa9: all-pairs sources keep their
                        // node-map object (nx iterates G).
                        let inner_dict = emit_paths_dict_discovery(
                            py,
                            &gr,
                            &paths,
                            src_node,
                            gr.py_node_key(py, src_node),
                        )?;
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
                    validate_node(&gr, &s, src, "Source")?;
                    validate_node(&gr, &t, tgt, "Target")?;

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
                    validate_node(&gr, &s, src, "Source")?;
                    let paths = compute_single_source_shortest_paths(py, inner, &s, None, method)?;
                    // br-r37-c1-6hpa9: kernel order + discovery objects.
                    let dict =
                        emit_paths_dict_discovery(py, &gr, &paths, &s, src.clone().unbind())?;
                    Ok(dict.into_any())
                }
                (None, Some(tgt)) => {
                    let t = node_key_to_string(py, tgt)?;
                    validate_node(&gr, &t, tgt, "Target")?;
                    // br-r37-c1-k4wsy: nx single_target semantics — one
                    // reverse level-BFS over adj rows, discovery objects.
                    let edges = py.allow_threads(|| fnx_algorithms::bfs_edges(inner, &t, None));
                    let dict = emit_single_target_paths_dict(
                        py,
                        &gr,
                        &edges,
                        &t,
                        tgt.clone().unbind(),
                        false,
                    )?;
                    Ok(dict.into_any())
                }
                (None, None) => {
                    let result = PyDict::new(py);
                    for src_node in inner.nodes_ordered() {
                        let paths = compute_single_source_shortest_paths(
                            py, inner, src_node, None, method,
                        )?;
                        // br-r37-c1-6hpa9: all-pairs sources keep their
                        // node-map object (nx iterates G).
                        let inner_dict = emit_paths_dict_discovery(
                            py,
                            &gr,
                            &paths,
                            src_node,
                            gr.py_node_key(py, src_node),
                        )?;
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
    validate_node(&gr, &s, source, "Source")?;
    validate_node(&gr, &t, target, "Target")?;
    // br-r37-c1-zid1b: unweighted MultiDiGraph single-pair uses a target-early-exit BFS
    // over the successor adjacency instead of the gr.digraph() conversion.
    if weight.is_none() {
        if let GraphRef::MultiDirected { mdg, .. } = &gr {
            let inner = &mdg.inner;
            let dist = py.allow_threads(|| multidigraph_target_bfs_distance(inner, &s, &t));
            return match dist {
                Some(d) => Ok(d.into_pyobject(py)?.into_any().unbind()),
                None => Err(NetworkXNoPath::new_err(format!(
                    "No path between {} and {}.",
                    s, t
                ))),
            };
        }
    }
    if let Some(inner) = gr.digraph() {
        if let Some(w) = weight {
            let weighted_projection = gr.weighted_digraph_projection(w).expect("directed graph");
            let result = {
                let __wp = weighted_projection.as_ref();
                py.allow_threads(|| fnx_algorithms::dijkstra_path_length_directed(__wp, &s, &t, w))
            };
            match result {
                Some(len) => Ok(len.into_pyobject(py)?.into_any().unbind()),
                None => Err(NetworkXNoPath::new_err(format!(
                    "No path between {} and {}.",
                    s, t
                ))),
            }
        } else {
            let result = py
                .allow_threads(|| fnx_algorithms::shortest_path_unweighted_directed(inner, &s, &t));
            match result.path {
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
        // br-r37-c1-ubizp: unweighted MultiGraph single-pair uses a target-early-exit
        // BFS over the adjacency instead of the gr.undirected() simple-Graph conversion
        // (was ~huge for single-pair). Distance is multiplicity-invariant.
        if weight.is_none() {
            if let GraphRef::MultiUndirected { mg, .. } = &gr {
                let inner = &mg.inner;
                let dist = py.allow_threads(|| multigraph_target_bfs_distance(inner, &s, &t));
                return match dist {
                    Some(d) => Ok(d.into_pyobject(py)?.into_any().unbind()),
                    None => Err(NetworkXNoPath::new_err(format!(
                        "No path between {} and {}.",
                        s, t
                    ))),
                };
            }
        }
        let inner = gr.undirected();
        if let Some(_w) = weight {
            let weighted_projection = gr.weighted_undirected_projection(_w);
            let inner = weighted_projection.as_ref();
            let result =
                py.allow_threads(|| fnx_algorithms::shortest_path_weighted(inner, &s, &t, _w));
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
            let result = py.allow_threads(|| fnx_algorithms::shortest_path_length(inner, &s, &t));
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
    validate_node(&gr, &s, source, "Source")?;
    validate_node(&gr, &t, target, "Target")?;
    if let GraphRef::MultiDirected { mdg, .. } = &gr {
        // br-r37-c1-zid1b: MultiDiGraph reachability via successor target-BFS.
        let inner = &mdg.inner;
        let reachable =
            py.allow_threads(|| multidigraph_target_bfs_distance(inner, &s, &t).is_some());
        return Ok(reachable);
    }
    if let Some(inner) = gr.digraph() {
        let result = py.allow_threads(|| fnx_algorithms::has_path_directed(inner, &s, &t));
        Ok(result.has_path)
    } else {
        // br-r37-c1-ubizp: MultiGraph reachability via target-early-exit BFS over the
        // adjacency instead of the gr.undirected() conversion (multiplicity-invariant).
        if let GraphRef::MultiUndirected { mg, .. } = &gr {
            let inner = &mg.inner;
            let reachable =
                py.allow_threads(|| multigraph_target_bfs_distance(inner, &s, &t).is_some());
            return Ok(reachable);
        }
        let inner = gr.undirected();
        let result = py.allow_threads(|| fnx_algorithms::has_path(inner, &s, &t));
        Ok(result.has_path)
    }
}

// ---------------------------------------------------------------------------
// average_shortest_path_length
// ---------------------------------------------------------------------------

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
enum AverageShortestPathLengthFailure {
    Disconnected,
    NegativeCycle,
}

fn accumulate_weighted_average_shortest_path_length<F>(
    sources: &[&str],
    node_count: usize,
    mut distances_for_source: F,
) -> Result<f64, AverageShortestPathLengthFailure>
where
    F: FnMut(&str) -> Result<HashMap<String, f64>, AverageShortestPathLengthFailure>,
{
    let mut total_distance = 0.0;
    for &source in sources {
        let distances = distances_for_source(source)?;
        if distances.len() < node_count {
            return Err(AverageShortestPathLengthFailure::Disconnected);
        }
        total_distance += distances.values().sum::<f64>();
    }
    Ok(total_distance)
}

#[pyfunction]
#[pyo3(signature = (g, weight=None, method=None))]
pub fn average_shortest_path_length(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    weight: Option<&str>,
    method: Option<&str>,
) -> PyResult<f64> {
    let gr = extract_graph(g)?;
    if gr.node_count_original() == 0 {
        return Err(crate::NetworkXPointlessConcept::new_err(
            "the null graph has no paths, thus there is no average shortest path length",
        ));
    }

    let effective_method = match method.unwrap_or(if weight.is_some() {
        "dijkstra"
    } else {
        "unweighted"
    }) {
        "unweighted" => "unweighted",
        "dijkstra" => "dijkstra",
        "bellman-ford" => "bellman-ford",
        other => {
            return Err(PyValueError::new_err(format!(
                "method not supported: {other}"
            )));
        }
    };

    if weight.is_none() || effective_method == "unweighted" {
        if gr.is_directed() {
            let dg_ref = gr.digraph().expect("is_directed checked above");
            let result =
                py.allow_threads(|| fnx_algorithms::average_shortest_path_length_directed(dg_ref));
            if !result.average_shortest_path_length.is_finite() {
                return Err(NetworkXError::new_err("Graph is not strongly connected."));
            }
            return Ok(result.average_shortest_path_length);
        }

        let inner = gr.undirected();
        let result = py.allow_threads(|| fnx_algorithms::average_shortest_path_length(inner));
        if !result.average_shortest_path_length.is_finite() {
            return Err(NetworkXError::new_err("Graph is not connected."));
        }
        return Ok(result.average_shortest_path_length);
    }

    let weight_attr = weight.expect("weighted branch requires weight");
    let node_count = gr.node_count_original();
    if node_count <= 1 {
        return Ok(0.0);
    }
    let denominator = (node_count * (node_count - 1)) as f64;

    if gr.is_directed() {
        let weighted_projection = gr
            .weighted_digraph_projection(weight_attr)
            .expect("directed graph");
        let dg_ref = weighted_projection.as_ref();

        let total_distance = match effective_method {
            "dijkstra" => match py.allow_threads(|| {
                let sources = dg_ref.nodes_ordered();
                accumulate_weighted_average_shortest_path_length(&sources, node_count, |source| {
                    Ok(fnx_algorithms::single_source_dijkstra_path_length_directed(
                        dg_ref,
                        source,
                        weight_attr,
                    )
                    .into_iter()
                    .collect())
                })
            }) {
                Ok(total_distance) => total_distance,
                Err(AverageShortestPathLengthFailure::Disconnected) => {
                    return Err(NetworkXError::new_err("Graph is not strongly connected."));
                }
                Err(AverageShortestPathLengthFailure::NegativeCycle) => {
                    unreachable!("Dijkstra traversal cannot emit negative-cycle failure")
                }
            },
            "bellman-ford" => {
                let result = py.allow_threads(|| {
                    let sources = dg_ref.nodes_ordered();
                    accumulate_weighted_average_shortest_path_length(
                        &sources,
                        node_count,
                        |source| {
                            fnx_algorithms::single_source_bellman_ford_path_length_directed(
                                dg_ref,
                                source,
                                weight_attr,
                            )
                            .map(|v| v.into_iter().collect())
                            .ok_or(AverageShortestPathLengthFailure::NegativeCycle)
                        },
                    )
                });
                match result {
                    Ok(total_distance) => total_distance,
                    Err(AverageShortestPathLengthFailure::Disconnected) => {
                        return Err(NetworkXError::new_err("Graph is not strongly connected."));
                    }
                    Err(AverageShortestPathLengthFailure::NegativeCycle) => {
                        return Err(crate::NetworkXUnbounded::new_err(
                            "Negative cycle detected.",
                        ));
                    }
                }
            }
            _ => unreachable!("weighted directed branch only supports dijkstra or bellman-ford"),
        };
        return Ok(total_distance / denominator);
    }

    let weighted_projection = gr.weighted_undirected_projection(weight_attr);
    let graph_ref = weighted_projection.as_ref();

    let total_distance = match effective_method {
        "dijkstra" => match py.allow_threads(|| {
            let sources = graph_ref.nodes_ordered();
            accumulate_weighted_average_shortest_path_length(&sources, node_count, |source| {
                Ok(fnx_algorithms::single_source_dijkstra_path_length(
                    graph_ref,
                    source,
                    weight_attr,
                )
                .into_iter()
                .collect())
            })
        }) {
            Ok(total_distance) => total_distance,
            Err(AverageShortestPathLengthFailure::Disconnected) => {
                return Err(NetworkXError::new_err("Graph is not connected."));
            }
            Err(AverageShortestPathLengthFailure::NegativeCycle) => {
                unreachable!("Dijkstra traversal cannot emit negative-cycle failure")
            }
        },
        "bellman-ford" => {
            match py.allow_threads(|| {
                let sources = graph_ref.nodes_ordered();
                accumulate_weighted_average_shortest_path_length(&sources, node_count, |source| {
                    fnx_algorithms::single_source_bellman_ford_path_length(
                        graph_ref,
                        source,
                        weight_attr,
                    )
                    .map(|v| v.into_iter().collect())
                    .ok_or(AverageShortestPathLengthFailure::NegativeCycle)
                })
            }) {
                Ok(total_distance) => total_distance,
                Err(AverageShortestPathLengthFailure::Disconnected) => {
                    return Err(NetworkXError::new_err("Graph is not connected."));
                }
                Err(AverageShortestPathLengthFailure::NegativeCycle) => {
                    return Err(crate::NetworkXUnbounded::new_err(
                        "Negative cycle detected.",
                    ));
                }
            }
        }
        _ => unreachable!("weighted undirected branch only supports dijkstra or bellman-ford"),
    };

    Ok(total_distance / denominator)
}

// ---------------------------------------------------------------------------
// dijkstra_path / negative-weight pre-check
// ---------------------------------------------------------------------------

/// Native O(|E|) scan for any negative finite edge weight under
/// ``weight_attr``. Used by the Python ``dijkstra_path`` /
/// ``bellman_ford`` dispatcher (br-r37-c1-644fx) to avoid a slow
/// per-edge Python iteration when deciding whether to delegate to nx
/// for the negative-weight case.
///
/// Returns ``Ok(None)`` for multigraph inputs — the caller falls back
/// to the Python path for those.
#[pyfunction]
#[pyo3(signature = (g, weight_attr))]
pub fn graph_has_negative_edge_weight(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    weight_attr: &str,
) -> PyResult<Option<bool>> {
    let gr = extract_graph(g)?;
    let result = match &gr {
        GraphRef::Undirected(pg) => {
            let inner = &pg.inner;
            Some(py.allow_threads(|| {
                fnx_algorithms::graph_has_negative_edge_weight(inner, weight_attr)
            }))
        }
        GraphRef::Directed { dg, .. } => {
            let inner = &dg.inner;
            Some(py.allow_threads(|| {
                fnx_algorithms::digraph_has_negative_edge_weight(inner, weight_attr)
            }))
        }
        GraphRef::MultiUndirected { .. } | GraphRef::MultiDirected { .. } => None,
    };
    Ok(result)
}

/// Build COO-format adjacency arrays (rows, cols, data) directly from
/// the Rust storage.  Used by the Python ``to_scipy_sparse_array`` /
/// ``to_numpy_array`` wrappers (br-r37-c1-lqlx2) to skip the per-edge
/// PyO3 tuple alloc that ``G._adj.items()`` iteration in Python pays.
///
/// ``nodelist`` is a Python sequence of fnx node objects (int/str/tuple
/// — anything ``node_key_to_string`` accepts) defining the row/column
/// ordering.  ``weight_attr`` is the edge-attribute name to read; when
/// ``None`` every edge gets ``default_weight`` (matching nx's
/// ``weight=None`` contract).
///
/// For undirected graphs the function emits BOTH ``(u, v)`` and
/// ``(v, u)`` entries (modulo self-loop dedup) so the resulting COO
/// array constructs the full symmetric matrix.  For directed graphs
/// each edge emits a single ``(src, dst)`` entry.  Edges with
/// endpoints outside ``nodelist`` are skipped (matching the Python
/// wrapper's ``if u not in index`` filter).
///
/// Returns ``None`` for multigraphs (caller falls back to the Python
/// path which dedups parallel edges).
#[pyfunction]
#[pyo3(signature = (g, nodelist, weight_attr, default_weight=1.0))]
pub fn adjacency_arrays(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    nodelist: &Bound<'_, PyAny>,
    weight_attr: Option<&str>,
    default_weight: f64,
) -> PyResult<Option<(Vec<u32>, Vec<u32>, Vec<f64>)>> {
    let nodes_iter = pyo3::types::PyIterator::from_object(nodelist)?;
    let mut index: HashMap<String, u32> = HashMap::new();
    for (count, item) in (0_u32..).zip(nodes_iter) {
        let item = item?;
        let canonical = node_key_to_string(py, &item)?;
        index.entry(canonical).or_insert(count);
    }

    let gr = extract_graph(g)?;
    let (rows, cols, data) = match &gr {
        GraphRef::Undirected(pg) => {
            let inner = &pg.inner;
            let edge_count = inner.edge_count();
            let mut rows: Vec<u32> = Vec::with_capacity(edge_count * 2);
            let mut cols: Vec<u32> = Vec::with_capacity(edge_count * 2);
            let mut data: Vec<f64> = Vec::with_capacity(edge_count * 2);
            for (u, v, attrs) in inner.edges_ordered_borrowed() {
                let Some(&ui) = index.get(u) else { continue };
                let Some(&vi) = index.get(v) else { continue };
                let w = weight_attr
                    .and_then(|attr| attrs.get(attr).and_then(|val| val.as_f64()))
                    .unwrap_or(default_weight);
                rows.push(ui);
                cols.push(vi);
                data.push(w);
                if ui != vi {
                    rows.push(vi);
                    cols.push(ui);
                    data.push(w);
                }
            }
            (rows, cols, data)
        }
        GraphRef::Directed { dg, .. } => {
            let inner = &dg.inner;
            let edge_count = inner.edge_count();
            let mut rows: Vec<u32> = Vec::with_capacity(edge_count);
            let mut cols: Vec<u32> = Vec::with_capacity(edge_count);
            let mut data: Vec<f64> = Vec::with_capacity(edge_count);
            for (u, v, attrs) in inner.edges_ordered_borrowed() {
                let Some(&ui) = index.get(u) else { continue };
                let Some(&vi) = index.get(v) else { continue };
                let w = weight_attr
                    .and_then(|attr| attrs.get(attr).and_then(|val| val.as_f64()))
                    .unwrap_or(default_weight);
                rows.push(ui);
                cols.push(vi);
                data.push(w);
            }
            (rows, cols, data)
        }
        GraphRef::MultiUndirected { .. } | GraphRef::MultiDirected { .. } => {
            // Multigraph: parallel-edge accumulation has subtle nx
            // contracts (sum vs first vs ignore).  Defer to the
            // Python path.
            return Ok(None);
        }
    };
    Ok(Some((rows, cols, data)))
}

/// Return COO row/column arrays for an unweighted simple graph.
///
/// This is the default-weight sibling of ``adjacency_arrays``. It can also
/// prove that a string weight attribute is absent while collecting COO indices,
/// avoiding a separate native edge-attribute scan before sparse export.
#[pyfunction]
#[pyo3(signature = (g, nodelist, absent_weight_attr=None))]
pub fn adjacency_index_arrays(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    nodelist: &Bound<'_, PyAny>,
    absent_weight_attr: Option<&str>,
) -> PyResult<Option<(Vec<u32>, Vec<u32>)>> {
    let nodes_iter = pyo3::types::PyIterator::from_object(nodelist)?;
    let mut index: HashMap<String, u32> = HashMap::new();
    for (count, item) in (0_u32..).zip(nodes_iter) {
        let item = item?;
        let canonical = node_key_to_string(py, &item)?;
        index.entry(canonical).or_insert(count);
    }

    let gr = extract_graph(g)?;
    let (rows, cols) = match &gr {
        GraphRef::Undirected(pg) => {
            if let Some(attr) = absent_weight_attr {
                for dict in pg.edge_py_attrs.values() {
                    if dict.bind(py).contains(attr)? {
                        return Ok(None);
                    }
                }
            }
            let inner = &pg.inner;
            let edge_count = inner.edge_count();
            let mut rows: Vec<u32> = Vec::with_capacity(edge_count * 2);
            let mut cols: Vec<u32> = Vec::with_capacity(edge_count * 2);
            for (u, v, _) in inner.edges_ordered_borrowed() {
                let Some(&ui) = index.get(u) else { continue };
                let Some(&vi) = index.get(v) else { continue };
                rows.push(ui);
                cols.push(vi);
                if ui != vi {
                    rows.push(vi);
                    cols.push(ui);
                }
            }
            (rows, cols)
        }
        GraphRef::Directed { dg, .. } => {
            if let Some(attr) = absent_weight_attr {
                for dict in dg.edge_py_attrs.values() {
                    if dict.bind(py).contains(attr)? {
                        return Ok(None);
                    }
                }
            }
            let inner = &dg.inner;
            let edge_count = inner.edge_count();
            let mut rows: Vec<u32> = Vec::with_capacity(edge_count);
            let mut cols: Vec<u32> = Vec::with_capacity(edge_count);
            for (u, v, _) in inner.edges_ordered_borrowed() {
                let Some(&ui) = index.get(u) else { continue };
                let Some(&vi) = index.get(v) else { continue };
                rows.push(ui);
                cols.push(vi);
            }
            (rows, cols)
        }
        GraphRef::MultiUndirected { .. } | GraphRef::MultiDirected { .. } => {
            return Ok(None);
        }
    };
    Ok(Some((rows, cols)))
}

/// br-r37-c1-18cp7: rectangular biadjacency COO for bipartite
/// ``biadjacency_matrix`` (an arbitrary ``row_order`` x ``column_order`` node
/// submatrix). Returns ``(rows, cols, data, all_int)`` where ``rows[k]`` /
/// ``cols[k]`` are positions within the row/column orderings and ``data[k]`` is
/// the edge weight (default 1.0). ``all_int`` is true iff every emitted weight
/// is an integer (or the missing-attr default 1), letting the Python wrapper
/// reproduce networkx's dtype inference (`int64` for an all-integer non-empty
/// matrix, `float64` otherwise) — the one parity subtlety of replacing the
/// per-edge ``B.edges(row_order, data=True)`` Python loop. Emission order is
/// irrelevant: ``coo_array(...).asformat(...)`` canonicalises, so the
/// (row, col, data) triple SET fully determines the matrix. Each undirected edge
/// is visited once and emitted from whichever endpoint lands in ``row_order``
/// (the other in ``column_order``), matching nx's ``u in row_index and v in
/// col_index`` filter. Returns ``None`` (Python falls back to its exact loop)
/// for directed / multigraph graphs or a non-numeric weight value.
#[pyfunction]
#[pyo3(signature = (g, row_order, column_order, weight=None))]
pub fn biadjacency_coo(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    row_order: &Bound<'_, PyAny>,
    column_order: &Bound<'_, PyAny>,
    weight: Option<&str>,
) -> PyResult<Option<(Vec<u32>, Vec<u32>, Vec<f64>, bool)>> {
    let mut row_index: HashMap<String, u32> = HashMap::new();
    for (count, item) in (0_u32..).zip(pyo3::types::PyIterator::from_object(row_order)?) {
        let canonical = node_key_to_string(py, &item?)?;
        row_index.entry(canonical).or_insert(count);
    }
    let mut col_index: HashMap<String, u32> = HashMap::new();
    for (count, item) in (0_u32..).zip(pyo3::types::PyIterator::from_object(column_order)?) {
        let canonical = node_key_to_string(py, &item?)?;
        col_index.entry(canonical).or_insert(count);
    }

    let gr = extract_graph(g)?;
    let GraphRef::Undirected(pg) = &gr else {
        return Ok(None);
    };
    let inner = &pg.inner;
    let edge_count = inner.edge_count();
    let mut rows: Vec<u32> = Vec::with_capacity(edge_count);
    let mut cols: Vec<u32> = Vec::with_capacity(edge_count);
    let mut data: Vec<f64> = Vec::with_capacity(edge_count);
    let mut all_int = true;
    for (u, v, attrs) in inner.edges_ordered_borrowed() {
        let (ri, ci) = if let (Some(&ri), Some(&ci)) = (row_index.get(u), col_index.get(v)) {
            (ri, ci)
        } else if let (Some(&ri), Some(&ci)) = (row_index.get(v), col_index.get(u)) {
            (ri, ci)
        } else {
            continue;
        };
        let w = match weight {
            None => 1.0,
            Some(attr) => match attrs.get(attr) {
                None => 1.0,
                Some(val) => match val.as_f64() {
                    Some(f) => {
                        if !val.is_int() {
                            all_int = false;
                        }
                        f
                    }
                    None => return Ok(None),
                },
            },
        };
        rows.push(ri);
        cols.push(ci);
        data.push(w);
    }
    Ok(Some((rows, cols, data, all_int)))
}

/// Return COO row/column arrays for an unweighted Graph in insertion order.
///
/// This is the default-nodelist sibling of ``adjacency_index_arrays``. It uses
/// cached neighbor-index slices, avoiding Python nodelist canonicalization and
/// per-edge string lookups on the common ``nodelist=None`` CSR path.
#[pyfunction]
#[pyo3(signature = (g, absent_weight_attr=None))]
pub fn adjacency_default_order_index_arrays(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    absent_weight_attr: Option<&str>,
) -> PyResult<Option<(Vec<usize>, Vec<usize>)>> {
    let gr = extract_graph(g)?;
    // br-r37-c1-prdir: directed graphs build the row-major out-adjacency COO
    // (rows=source, cols=target, each edge once) from successors_indices.
    match &gr {
        GraphRef::Undirected(pg) => {
            if let Some(attr) = absent_weight_attr {
                for dict in pg.edge_py_attrs.values() {
                    if dict.bind(py).contains(attr)? {
                        return Ok(None);
                    }
                }
            }
            let inner = &pg.inner;
            let mut rows = Vec::with_capacity(inner.edge_count() * 2);
            let mut cols = Vec::with_capacity(inner.edge_count() * 2);
            for row in 0..inner.node_count() {
                let Some(neighbors) = inner.neighbors_indices(row) else {
                    continue;
                };
                for &col in neighbors {
                    rows.push(row);
                    cols.push(col);
                }
            }
            Ok(Some((rows, cols)))
        }
        GraphRef::Directed { dg, .. } => {
            if let Some(attr) = absent_weight_attr {
                for dict in dg.edge_py_attrs.values() {
                    if dict.bind(py).contains(attr)? {
                        return Ok(None);
                    }
                }
            }
            let inner = &dg.inner;
            let mut rows = Vec::with_capacity(inner.edge_count());
            let mut cols = Vec::with_capacity(inner.edge_count());
            for row in 0..inner.node_count() {
                let Some(succ) = inner.successors_indices(row) else {
                    continue;
                };
                for &col in succ {
                    rows.push(row);
                    cols.push(col);
                }
            }
            Ok(Some((rows, cols)))
        }
        _ => Ok(None),
    }
}

/// Return weighted COO arrays for an undirected Graph in insertion order.
///
/// This is the default-nodelist sibling of ``adjacency_arrays`` for the common
/// weighted CSR route. It reuses cached neighbor-index slices and synced Rust
/// edge attrs, avoiding Python nodelist canonicalization plus per-edge node
/// string-to-index lookups.
#[pyfunction]
#[pyo3(signature = (g, weight_attr, default_weight=1.0))]
pub fn adjacency_default_order_arrays(
    g: &Bound<'_, PyAny>,
    weight_attr: Option<&str>,
    default_weight: f64,
) -> PyResult<Option<(Vec<usize>, Vec<usize>, Vec<f64>)>> {
    let gr = extract_graph(g)?;
    // br-r37-c1-coowt: read each edge's weight by INTEGER index pair
    // (edge_attrs_by_indices) instead of get_node_name(row)+get_node_name(col)+
    // edge_attrs(&str,&str) — that paid two index->String resolutions plus a
    // String->index round-trip per edge (the String-adjacency tax on the
    // weighted CSR export used by to_scipy_sparse_array / adjacency_matrix).
    // br-r37-c1-prdir: directed graphs build the row-major out-adjacency COO
    // (rows=source, cols=target, each edge ONCE) from successors_indices.
    match &gr {
        GraphRef::Undirected(pg) => {
            let inner = &pg.inner;
            let mut rows = Vec::with_capacity(inner.edge_count() * 2);
            let mut cols = Vec::with_capacity(inner.edge_count() * 2);
            let mut data = Vec::with_capacity(inner.edge_count() * 2);
            for row in 0..inner.node_count() {
                let Some(neighbors) = inner.neighbors_indices(row) else {
                    continue;
                };
                for &col in neighbors {
                    let w = inner
                        .edge_attrs_by_indices(row, col)
                        .and_then(|attrs| {
                            weight_attr
                                .and_then(|attr| attrs.get(attr).and_then(|val| val.as_f64()))
                        })
                        .unwrap_or(default_weight);
                    rows.push(row);
                    cols.push(col);
                    data.push(w);
                }
            }
            Ok(Some((rows, cols, data)))
        }
        GraphRef::Directed { dg, .. } => {
            let inner = &dg.inner;
            let ecount = inner.edge_count();
            let mut rows = Vec::with_capacity(ecount);
            let mut cols = Vec::with_capacity(ecount);
            let mut data = Vec::with_capacity(ecount);
            // Iterate the index-keyed edge store directly: one attr lookup per
            // edge, no per-edge `edges.get(&(u,v))` hash. Order is edge-insertion;
            // COO assembly is order-independent.
            for ((u, v), attrs) in inner.edges_indexed() {
                let w = weight_attr
                    .and_then(|attr| attrs.get(attr).and_then(|val| val.as_f64()))
                    .unwrap_or(default_weight);
                rows.push(u);
                cols.push(v);
                data.push(w);
            }
            Ok(Some((rows, cols, data)))
        }
        _ => Ok(None),
    }
}

/// Return weighted COO arrays plus dtype metadata for a default-order Graph.
///
/// This is the dtype-preserving sibling of ``adjacency_default_order_arrays``
/// for ``dtype=None`` sparse exports. It returns ``None`` for value kinds where
/// converting through f64 would change NetworkX dtype/value semantics.
#[pyfunction]
#[pyo3(signature = (g, weight_attr, default_weight=1.0))]
pub fn adjacency_default_order_typed_arrays(
    g: &Bound<'_, PyAny>,
    weight_attr: &str,
    default_weight: f64,
) -> PyResult<Option<(Vec<usize>, Vec<usize>, Vec<f64>, bool)>> {
    let gr = extract_graph(g)?;
    const MAX_EXACT_F64_INT: i64 = 9_007_199_254_740_992;
    let mut needs_float_dtype = default_weight.fract() != 0.0;
    match &gr {
        GraphRef::Undirected(pg) => {
            let inner = &pg.inner;
            let mut rows = Vec::with_capacity(inner.edge_count() * 2);
            let mut cols = Vec::with_capacity(inner.edge_count() * 2);
            let mut data = Vec::with_capacity(inner.edge_count() * 2);
            for (row, col, attrs) in inner.edges_storage_order_index_iter() {
                let value = match attrs.get(weight_attr) {
                    Some(fnx_runtime::CgseValue::Int(i)) => {
                        if *i < -MAX_EXACT_F64_INT || *i > MAX_EXACT_F64_INT {
                            return Ok(None);
                        }
                        *i as f64
                    }
                    Some(fnx_runtime::CgseValue::Float(f)) => {
                        needs_float_dtype = true;
                        *f
                    }
                    None => default_weight,
                    Some(
                        fnx_runtime::CgseValue::Bool(_)
                        | fnx_runtime::CgseValue::String(_)
                        | fnx_runtime::CgseValue::Map(_),
                    ) => return Ok(None),
                };
                rows.push(row);
                cols.push(col);
                data.push(value);
                if row != col {
                    rows.push(col);
                    cols.push(row);
                    data.push(value);
                }
            }
            Ok(Some((rows, cols, data, needs_float_dtype)))
        }
        // br-r37-c1-pmqhz: directed default-order typed COO — out-edges only (no
        // symmetric duplication), storage index == default node order. Lets the
        // dtype=None weighted to_scipy fast path cover DiGraphs (was per-edge
        // Python fallback, ~3.3x slower than nx).
        GraphRef::Directed { dg, .. } => {
            let inner = &dg.inner;
            let mut rows = Vec::with_capacity(inner.edge_count());
            let mut cols = Vec::with_capacity(inner.edge_count());
            let mut data = Vec::with_capacity(inner.edge_count());
            for ((row, col), attrs) in inner.edges_indexed() {
                let value = match attrs.get(weight_attr) {
                    Some(fnx_runtime::CgseValue::Int(i)) => {
                        if *i < -MAX_EXACT_F64_INT || *i > MAX_EXACT_F64_INT {
                            return Ok(None);
                        }
                        *i as f64
                    }
                    Some(fnx_runtime::CgseValue::Float(f)) => {
                        needs_float_dtype = true;
                        *f
                    }
                    None => default_weight,
                    Some(
                        fnx_runtime::CgseValue::Bool(_)
                        | fnx_runtime::CgseValue::String(_)
                        | fnx_runtime::CgseValue::Map(_),
                    ) => return Ok(None),
                };
                rows.push(row);
                cols.push(col);
                data.push(value);
            }
            Ok(Some((rows, cols, data, needs_float_dtype)))
        }
        // Multigraphs keep the Python path (caller already gates this out).
        _ => Ok(None),
    }
}

/// Weighted COO arrays + dtype metadata for an EXPLICIT nodelist (Graph or
/// DiGraph). br-r37-c1-pmqhz-nl: dtype-preserving sibling of
/// `adjacency_default_order_typed_arrays` for the non-default node order — remaps
/// each edge's endpoints (storage order -> node key -> nodelist position) so the
/// dtype=None weighted to_scipy fast path covers explicit nodelists too (was a
/// per-edge G[u][v] Python fallback, ~3.5-4.2x slower than nx). Edges with an
/// endpoint outside `nodelist` are skipped (subset nodelists, matching nx).
#[pyfunction]
#[pyo3(signature = (g, nodelist, weight_attr, default_weight=1.0))]
pub fn adjacency_nodelist_typed_arrays(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    nodelist: &Bound<'_, PyAny>,
    weight_attr: &str,
    default_weight: f64,
) -> PyResult<Option<(Vec<usize>, Vec<usize>, Vec<f64>, bool)>> {
    let gr = extract_graph(g)?;
    const MAX_EXACT_F64_INT: i64 = 9_007_199_254_740_992;
    let mut needs_float_dtype = default_weight.fract() != 0.0;
    // Convert each Python node object to its canonical string key (matching
    // inner.nodes_ordered()), so the endpoint remap works for int/str/any nodes.
    let mut keys: Vec<String> = Vec::new();
    for item in nodelist.try_iter()? {
        keys.push(node_key_to_string(py, &item?)?);
    }
    let pos: std::collections::HashMap<&str, usize> = keys
        .iter()
        .enumerate()
        .map(|(i, n)| (n.as_str(), i))
        .collect();
    match &gr {
        GraphRef::Undirected(pg) => {
            let inner = &pg.inner;
            let order = inner.nodes_ordered();
            let mut rows = Vec::with_capacity(inner.edge_count() * 2);
            let mut cols = Vec::with_capacity(inner.edge_count() * 2);
            let mut data = Vec::with_capacity(inner.edge_count() * 2);
            for (r, c, attrs) in inner.edges_storage_order_index_iter() {
                let (Some(&ri), Some(&ci)) = (pos.get(order[r]), pos.get(order[c])) else {
                    continue;
                };
                let value = match attrs.get(weight_attr) {
                    Some(fnx_runtime::CgseValue::Int(i)) => {
                        if *i < -MAX_EXACT_F64_INT || *i > MAX_EXACT_F64_INT {
                            return Ok(None);
                        }
                        *i as f64
                    }
                    Some(fnx_runtime::CgseValue::Float(f)) => {
                        needs_float_dtype = true;
                        *f
                    }
                    None => default_weight,
                    Some(
                        fnx_runtime::CgseValue::Bool(_)
                        | fnx_runtime::CgseValue::String(_)
                        | fnx_runtime::CgseValue::Map(_),
                    ) => return Ok(None),
                };
                rows.push(ri);
                cols.push(ci);
                data.push(value);
                if ri != ci {
                    rows.push(ci);
                    cols.push(ri);
                    data.push(value);
                }
            }
            Ok(Some((rows, cols, data, needs_float_dtype)))
        }
        GraphRef::Directed { dg, .. } => {
            let inner = &dg.inner;
            let order = inner.nodes_ordered();
            let mut rows = Vec::with_capacity(inner.edge_count());
            let mut cols = Vec::with_capacity(inner.edge_count());
            let mut data = Vec::with_capacity(inner.edge_count());
            for ((r, c), attrs) in inner.edges_indexed() {
                let (Some(&ri), Some(&ci)) = (pos.get(order[r]), pos.get(order[c])) else {
                    continue;
                };
                let value = match attrs.get(weight_attr) {
                    Some(fnx_runtime::CgseValue::Int(i)) => {
                        if *i < -MAX_EXACT_F64_INT || *i > MAX_EXACT_F64_INT {
                            return Ok(None);
                        }
                        *i as f64
                    }
                    Some(fnx_runtime::CgseValue::Float(f)) => {
                        needs_float_dtype = true;
                        *f
                    }
                    None => default_weight,
                    Some(
                        fnx_runtime::CgseValue::Bool(_)
                        | fnx_runtime::CgseValue::String(_)
                        | fnx_runtime::CgseValue::Map(_),
                    ) => return Ok(None),
                };
                rows.push(ri);
                cols.push(ci);
                data.push(value);
            }
            Ok(Some((rows, cols, data, needs_float_dtype)))
        }
        _ => Ok(None),
    }
}

/// Bulk per-node adjacency + edge attrs for the `_fnx_to_nx` parity conversion.
///
/// Returns, for each node in node-insertion order, its neighbors in
/// adjacency-insertion order paired with that edge's Python attribute dict
/// (read from `edge_py_attrs`, the fresh Python source — no `inner` staleness).
/// Undirected graphs emit each edge twice (once per endpoint), matching the
/// `G._adj.items()` iteration the Python path replaces; directed graphs emit
/// out-edges only.
///
/// This collapses the two per-element-PyO3 view passes in `_fnx_to_nx`
/// (`attrs_by_pair` + the topo `queues` build) into a single boundary crossing.
/// Returns `None` for multigraphs (caller keeps the Python path). Edges with no
/// attributes share one empty dict sentinel; the Python side copies via
/// `dict(attrs)` so sharing is safe. (br-r37-c1-xykjs)
#[pyfunction]
pub fn fnx_to_nx_adjacency(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
) -> PyResult<Option<Vec<(PyObject, Vec<(PyObject, PyObject)>)>>> {
    let gr = extract_graph(g)?;
    let empty: PyObject = PyDict::new(py).into_any().unbind();
    let result = match &gr {
        GraphRef::Undirected(pg) => {
            let inner = &pg.inner;
            let node_order: Vec<&str> = inner.nodes_ordered();
            let mut out: Vec<(PyObject, Vec<(PyObject, PyObject)>)> =
                Vec::with_capacity(node_order.len());
            for node in node_order {
                let mut nbrs: Vec<(PyObject, PyObject)> = Vec::new();
                if let Some(it) = inner.neighbors_iter(node) {
                    for nbr in it {
                        let attrs = match gr.edge_attrs_for_undirected(node, nbr) {
                            Some(d) => d.clone_ref(py).into_any(),
                            None => empty.clone_ref(py),
                        };
                        nbrs.push((gr.py_node_key(py, nbr), attrs));
                    }
                }
                out.push((gr.py_node_key(py, node), nbrs));
            }
            out
        }
        GraphRef::Directed { dg, .. } => {
            let inner = &dg.inner;
            let node_order: Vec<&str> = inner.nodes_ordered();
            let mut out: Vec<(PyObject, Vec<(PyObject, PyObject)>)> =
                Vec::with_capacity(node_order.len());
            for node in node_order {
                let mut nbrs: Vec<(PyObject, PyObject)> = Vec::new();
                if let Some(it) = inner.successors_iter(node) {
                    for nbr in it {
                        let attrs = match gr.edge_attrs_for_directed(node, nbr) {
                            Some(d) => d.clone_ref(py).into_any(),
                            None => empty.clone_ref(py),
                        };
                        nbrs.push((gr.py_node_key(py, nbr), attrs));
                    }
                }
                out.push((gr.py_node_key(py, node), nbrs));
            }
            out
        }
        GraphRef::MultiUndirected { .. } | GraphRef::MultiDirected { .. } => {
            return Ok(None);
        }
    };
    Ok(Some(result))
}

/// Return whether any simple-graph edge has a Python-visible attribute key.
///
/// This scans ``edge_py_attrs`` instead of the Rust ``inner`` attrs so callers
/// can make routing decisions before paying the O(E) sync cost. Multigraphs
/// return ``None`` because their matrix aggregation contracts stay on the
/// Python fallback path.
#[pyfunction]
#[pyo3(signature = (g, weight_attr))]
pub fn graph_has_edge_attr(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    weight_attr: &str,
) -> PyResult<Option<bool>> {
    let gr = extract_graph(g)?;
    let has_attr = match &gr {
        GraphRef::Undirected(pg) => Some(pg.edge_py_attrs.values().try_fold(
            false,
            |found, dict| -> PyResult<bool> {
                if found {
                    return Ok(true);
                }
                dict.bind(py).contains(weight_attr)
            },
        )?),
        GraphRef::Directed { dg, .. } => Some(dg.edge_py_attrs.values().try_fold(
            false,
            |found, dict| -> PyResult<bool> {
                if found {
                    return Ok(true);
                }
                dict.bind(py).contains(weight_attr)
            },
        )?),
        GraphRef::MultiUndirected { .. } | GraphRef::MultiDirected { .. } => None,
    };
    Ok(has_attr)
}

/// Return whether any simple graph node or edge has a Python-visible attr.
///
/// ``graph`` attributes are intentionally ignored: product and relabel fast
/// paths copy ``G.graph`` separately and only need to know whether node/edge
/// construction must preserve per-item dictionaries. Multigraphs return
/// ``None`` so callers keep the Python fallback for keyed-edge semantics.
#[pyfunction]
pub fn graph_has_any_attrs(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<Option<bool>> {
    let gr = extract_graph(g)?;
    let has_attrs = match &gr {
        GraphRef::Undirected(pg) => {
            let has_node_attrs =
                pg.node_py_attrs
                    .values()
                    .try_fold(false, |found, dict| -> PyResult<bool> {
                        if found {
                            return Ok(true);
                        }
                        Ok(!dict.bind(py).is_empty())
                    })?;
            if has_node_attrs {
                Some(true)
            } else {
                Some(pg.edge_py_attrs.values().try_fold(
                    false,
                    |found, dict| -> PyResult<bool> {
                        if found {
                            return Ok(true);
                        }
                        Ok(!dict.bind(py).is_empty())
                    },
                )?)
            }
        }
        GraphRef::Directed { dg, .. } => {
            let has_node_attrs =
                dg.node_py_attrs
                    .values()
                    .try_fold(false, |found, dict| -> PyResult<bool> {
                        if found {
                            return Ok(true);
                        }
                        Ok(!dict.bind(py).is_empty())
                    })?;
            if has_node_attrs {
                Some(true)
            } else {
                Some(dg.edge_py_attrs.values().try_fold(
                    false,
                    |found, dict| -> PyResult<bool> {
                        if found {
                            return Ok(true);
                        }
                        Ok(!dict.bind(py).is_empty())
                    },
                )?)
            }
        }
        GraphRef::MultiUndirected { .. } | GraphRef::MultiDirected { .. } => None,
    };
    Ok(has_attrs)
}

/// Return whether any simple-graph edge has a present non-unit weight attr.
///
/// This mirrors Python's ``attrs[weight] != 1`` check against the live
/// ``edge_py_attrs`` dicts without materializing ``G.edges(data=True)``. The
/// Python edge view marks those dicts dirty because user code may mutate them;
/// this internal read-only scan must not poison Dijkstra's mutation token.
#[pyfunction]
#[pyo3(signature = (g, weight_attr))]
pub fn graph_has_explicit_nonunit_weight_fast(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    weight_attr: &str,
) -> PyResult<Option<bool>> {
    let gr = extract_graph(g)?;
    let one = 1_i64.into_pyobject(py)?;
    let dict_has_nonunit = |dict: &Py<PyDict>| -> PyResult<bool> {
        let bound = dict.bind(py);
        let Some(value) = bound.get_item(weight_attr)? else {
            return Ok(false);
        };
        match value.rich_compare(one.as_any(), CompareOp::Ne) {
            Ok(nonunit) => nonunit.is_truthy(),
            Err(_) => Ok(true),
        }
    };
    let has_nonunit = match &gr {
        GraphRef::Undirected(pg) => {
            let mut found = false;
            for dict in pg.edge_py_attrs.values() {
                if dict_has_nonunit(dict)? {
                    found = true;
                    break;
                }
            }
            Some(found)
        }
        GraphRef::Directed { dg, .. } => {
            let mut found = false;
            for dict in dg.edge_py_attrs.values() {
                if dict_has_nonunit(dict)? {
                    found = true;
                    break;
                }
            }
            Some(found)
        }
        GraphRef::MultiUndirected { .. } | GraphRef::MultiDirected { .. } => None,
    };
    Ok(has_nonunit)
}

/// Native O(|E|) scan for any non-finite or non-numeric edge weight
/// at ``weight_attr``. Used by the Python ``pagerank`` dispatcher
/// (br-r37-c1-s0tno) to decide whether to delegate to nx without
/// paying ~40 ms of Python edge iteration on BA5000.
///
/// Returns ``Ok(None)`` for multigraphs — caller falls back to the
/// Python scan in that case.
#[pyfunction]
#[pyo3(signature = (g, weight_attr))]
pub fn graph_has_nonfinite_edge_weight(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    weight_attr: &str,
) -> PyResult<Option<bool>> {
    let gr = extract_graph(g)?;
    let result = match &gr {
        GraphRef::Undirected(pg) => {
            let inner = &pg.inner;
            Some(py.allow_threads(|| {
                fnx_algorithms::graph_has_nonfinite_edge_weight(inner, weight_attr)
            }))
        }
        GraphRef::Directed { dg, .. } => {
            let inner = &dg.inner;
            Some(py.allow_threads(|| {
                fnx_algorithms::digraph_has_nonfinite_edge_weight(inner, weight_attr)
            }))
        }
        GraphRef::MultiUndirected { .. } | GraphRef::MultiDirected { .. } => None,
    };
    Ok(result)
}

#[pyfunction]
#[pyo3(signature = (g, weight_attr))]
pub fn graph_has_nonnumeric_edge_weight(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    weight_attr: &str,
) -> PyResult<Option<bool>> {
    let gr = extract_graph(g)?;
    let result = match &gr {
        GraphRef::Undirected(pg) => {
            let inner = &pg.inner;
            Some(py.allow_threads(|| {
                fnx_algorithms::graph_has_nonnumeric_edge_weight(inner, weight_attr)
            }))
        }
        GraphRef::Directed { dg, .. } => {
            let inner = &dg.inner;
            Some(py.allow_threads(|| {
                fnx_algorithms::digraph_has_nonnumeric_edge_weight(inner, weight_attr)
            }))
        }
        GraphRef::MultiUndirected { .. } | GraphRef::MultiDirected { .. } => None,
    };
    Ok(result)
}

#[pyfunction]
#[pyo3(signature = (g, weight_attr))]
pub fn graph_edge_weights_all_int(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    weight_attr: &str,
) -> PyResult<Option<bool>> {
    let gr = extract_graph(g)?;
    let result =
        match &gr {
            GraphRef::Undirected(pg) => {
                let inner = &pg.inner;
                Some(py.allow_threads(|| {
                    fnx_algorithms::graph_edge_weights_all_int(inner, weight_attr)
                }))
            }
            GraphRef::Directed { dg, .. } => {
                let inner = &dg.inner;
                Some(py.allow_threads(|| {
                    fnx_algorithms::digraph_edge_weights_all_int(inner, weight_attr)
                }))
            }
            GraphRef::MultiUndirected { .. } | GraphRef::MultiDirected { .. } => None,
        };
    Ok(result)
}

#[pyfunction]
#[pyo3(signature = (g, weight_attr))]
pub fn check_dijkstra_edge_weights_fast(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    weight_attr: &str,
) -> PyResult<Option<(bool, bool, bool)>> {
    let gr = extract_graph(g)?;
    match &gr {
        GraphRef::Undirected(pg) => {
            let mut has_negative = false;
            let mut has_nonfinite = false;
            let mut has_nonnumeric = false;
            for dict in pg.edge_py_attrs.values() {
                let bound = dict.bind(py);
                if let Some(val) = bound.get_item(weight_attr)? {
                    if let Ok(f) = val.extract::<f64>() {
                        if f < 0.0 {
                            has_negative = true;
                        }
                        if !f.is_finite() {
                            has_nonfinite = true;
                        }
                    } else if let Ok(i) = val.extract::<i64>() {
                        if i < 0 {
                            has_negative = true;
                        }
                    } else if val.extract::<bool>().is_err() {
                        has_nonnumeric = true;
                    }
                }
                if has_negative && has_nonfinite && has_nonnumeric {
                    break;
                }
            }
            Ok(Some((has_negative, has_nonfinite, has_nonnumeric)))
        }
        GraphRef::Directed { dg, .. } => {
            let mut has_negative = false;
            let mut has_nonfinite = false;
            let mut has_nonnumeric = false;
            for dict in dg.edge_py_attrs.values() {
                let bound = dict.bind(py);
                if let Some(val) = bound.get_item(weight_attr)? {
                    if let Ok(f) = val.extract::<f64>() {
                        if f < 0.0 {
                            has_negative = true;
                        }
                        if !f.is_finite() {
                            has_nonfinite = true;
                        }
                    } else if let Ok(i) = val.extract::<i64>() {
                        if i < 0 {
                            has_negative = true;
                        }
                    } else if val.extract::<bool>().is_err() {
                        has_nonnumeric = true;
                    }
                }
                if has_negative && has_nonfinite && has_nonnumeric {
                    break;
                }
            }
            Ok(Some((has_negative, has_nonfinite, has_nonnumeric)))
        }
        GraphRef::MultiUndirected { .. } | GraphRef::MultiDirected { .. } => Ok(None),
    }
}

#[pyfunction]
#[pyo3(signature = (g))]
pub fn dijkstra_weight_cache_token(g: &Bound<'_, PyAny>) -> PyResult<Option<(u64, u64, bool)>> {
    let gr = extract_graph(g)?;
    match &gr {
        GraphRef::Undirected(pg) => Ok(Some((
            pg.nodes_seq,
            pg.edges_seq,
            pg.edges_dirty.load(Ordering::Relaxed),
        ))),
        GraphRef::Directed { dg, .. } => Ok(Some((
            dg.nodes_seq,
            dg.edges_seq,
            dg.edges_dirty.load(Ordering::Relaxed),
        ))),
        GraphRef::MultiUndirected { .. } | GraphRef::MultiDirected { .. } => Ok(None),
    }
}

#[pyfunction]
#[pyo3(signature = (g, source, target, weight="weight"))]
pub fn dijkstra_path(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    source: &Bound<'_, PyAny>,
    target: &Bound<'_, PyAny>,
    weight: &str,
) -> PyResult<Vec<PyObject>> {
    sync_rust_attrs_for_non_simple(g)?;
    let gr = extract_graph(g)?;
    let s = node_key_to_string(py, source)?;
    let t = node_key_to_string(py, target)?;
    validate_node(&gr, &s, source, "Source")?;
    validate_node(&gr, &t, target, "Target")?;

    let result =
        if let Some(weighted_projection) = gr.dijkstra_weighted_digraph_projection(py, weight)? {
            {
                let __wp = weighted_projection.as_ref();
                py.allow_threads(|| {
                    fnx_algorithms::shortest_path_weighted_directed(__wp, &s, &t, weight)
                })
            }
        } else {
            let weighted_projection = gr.dijkstra_weighted_undirected_projection(py, weight)?;
            {
                let __wp = weighted_projection.as_ref();
                py.allow_threads(|| fnx_algorithms::shortest_path_weighted(__wp, &s, &t, weight))
            }
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
    sync_rust_attrs_if_available(g)?;
    let gr = extract_graph(g)?;
    let s = node_key_to_string(py, source)?;
    let t = node_key_to_string(py, target)?;
    validate_node(&gr, &s, source, "Source")?;
    validate_node(&gr, &t, target, "Target")?;

    let result = if let Some(weighted_projection) = gr.weighted_digraph_projection(weight) {
        {
            let __wp = weighted_projection.as_ref();
            py.allow_threads(|| {
                fnx_algorithms::bellman_ford_shortest_paths_directed(__wp, &s, weight)
            })
        }
    } else {
        let weighted_projection = gr.weighted_undirected_projection(weight);
        {
            let __wp = weighted_projection.as_ref();
            py.allow_threads(|| fnx_algorithms::bellman_ford_shortest_paths(__wp, &s, weight))
        }
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
    sync_rust_attrs_for_non_simple(g)?;
    let gr = extract_graph(g)?;
    let iter = pyo3::types::PyIterator::from_object(sources)?;
    let mut source_strs = Vec::new();
    // br-r37-c1-7hsew: keep the PASSED source objects — nx seeds
    // `{source: [source] for source in sources}`, so sources display AS
    // PASSED (iterating the caller's set object in-process also gives
    // nx's exact seed order at any hash seed).
    let mut seed_objs: std::collections::HashMap<String, PyObject> =
        std::collections::HashMap::new();
    for item in iter {
        let item = item?;
        let s = node_key_to_string(py, &item)?;
        validate_node_str(&gr, &s, "Source")?;
        seed_objs.entry(s.clone()).or_insert_with(|| item.unbind());
        source_strs.push(s);
    }
    let source_refs: Vec<&str> = source_strs.iter().map(String::as_str).collect();

    let result = if let Some(weighted_projection) =
        gr.dijkstra_weighted_digraph_projection(py, weight)?
    {
        {
            let __wp = weighted_projection.as_ref();
            py.allow_threads(|| {
                fnx_algorithms::multi_source_dijkstra_directed(__wp, &source_refs, weight)
            })
        }
    } else {
        let weighted_projection = gr.dijkstra_weighted_undirected_projection(py, weight)?;
        {
            let __wp = weighted_projection.as_ref();
            py.allow_threads(|| fnx_algorithms::multi_source_dijkstra(__wp, &source_refs, weight))
        }
    };

    let pred_map: std::collections::HashMap<&str, Option<&str>> = result
        .predecessors
        .iter()
        .map(|e| (e.node.as_str(), e.predecessor.as_deref()))
        .collect();

    // br-r37-c1-7hsew: discovery objects — seeds as passed, every other
    // node as its finalizing predecessor's row object.
    let mut disp: std::collections::HashMap<String, PyObject> = seed_objs;
    for entry in &result.distances {
        if let Some(Some(p)) = pred_map.get(entry.node.as_str()) {
            disp.entry(entry.node.clone())
                .or_insert_with(|| gr.py_row_key(py, p, &entry.node));
        }
    }

    let dist_dict = PyDict::new(py);
    for entry in &result.distances {
        dist_dict.set_item(gr.disp_or_node_key(py, &disp, &entry.node), entry.distance)?;
    }

    let paths_dict = PyDict::new(py);
    for entry in &result.distances {
        let mut path = vec![entry.node.clone()];
        let mut current = entry.node.as_str();
        while let Some(Some(prev)) = pred_map.get(current) {
            path.push((*prev).to_owned());
            current = prev;
        }
        path.reverse();
        let py_path: Vec<PyObject> = path
            .iter()
            .map(|n| gr.disp_or_node_key(py, &disp, n))
            .collect();
        paths_dict.set_item(gr.disp_or_node_key(py, &disp, &entry.node), py_path)?;
    }

    Ok((
        dist_dict.into_any().unbind(),
        paths_dict.into_any().unbind(),
    ))
}

// ---------------------------------------------------------------------------
// bidirectional_dijkstra (undirected native kernel, br-r37-c1-k4p0b)
// ---------------------------------------------------------------------------

/// Native undirected bidirectional Dijkstra: returns `(length, path)`
/// byte-identical to `networkx.bidirectional_dijkstra`. The Python wrapper only
/// routes simple undirected graphs with a string weight key and non-negative
/// finite numeric weights here (everything else is delegated / kept on the
/// in-process port); it also performs the nx `NodeNotFound` / `source == target`
/// checks before calling, so this kernel assumes both nodes are present.
#[pyfunction]
#[pyo3(signature = (g, source, target, weight="weight"))]
pub fn bidirectional_dijkstra(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    source: &Bound<'_, PyAny>,
    target: &Bound<'_, PyAny>,
    weight: &str,
) -> PyResult<(f64, bool, PyObject)> {
    // The Python wrapper has already run the edge-only, dirty-gated
    // `_fnx_sync_edge_attrs_to_inner` (a no-op for unmutated graphs), so the
    // inner AttrMap weights this kernel reads are current. We deliberately do
    // NOT call the heavy `_fnx_sync_attrs_to_inner` here: it unconditionally
    // re-syncs all node attrs (O(n)) on every call, which dominated the
    // single-pair cost and made the native kernel slower than nx.
    let gr = extract_graph(g)?;
    let source_str = node_key_to_string(py, source)?;
    let target_str = node_key_to_string(py, target)?;
    validate_node_str(&gr, &source_str, "Source")?;
    validate_node_str(&gr, &target_str, "Target")?;

    let projection = gr.weighted_undirected_projection(weight);
    let outcome = {
        let inner = projection.as_ref();
        py.allow_threads(|| {
            fnx_algorithms::bidirectional_dijkstra_undirected(
                inner,
                &source_str,
                &target_str,
                weight,
            )
        })
    };

    match outcome {
        fnx_algorithms::BidirectionalDijkstraOutcome::Found(length, all_int, path) => {
            let py_path: Vec<PyObject> = path.iter().map(|n| gr.py_node_key(py, n)).collect();
            Ok((
                length,
                all_int,
                py_path.into_pyobject(py)?.into_any().unbind(),
            ))
        }
        fnx_algorithms::BidirectionalDijkstraOutcome::NoPath => Err(NetworkXNoPath::new_err(
            format!("No path between {} and {}.", source_str, target_str),
        )),
        fnx_algorithms::BidirectionalDijkstraOutcome::Contradiction => Err(PyValueError::new_err(
            "Contradictory paths found: negative weights?",
        )),
        fnx_algorithms::BidirectionalDijkstraOutcome::NodeMissing => {
            Err(NodeNotFound::new_err(format!(
                "Either source {} or target {} is not in G",
                source_str, target_str
            )))
        }
    }
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
/// br-r37-c1-fyxma2 (cc): is a MultiGraph connected? early-exit BFS from the first
/// node over the adjacency (no intermediate simple-Graph build, multiplicity is
/// irrelevant to connectivity) — same lever that fixed connected_components.
fn multigraph_is_connected(mg: &fnx_classes::MultiGraph) -> bool {
    use std::collections::{HashSet, VecDeque};
    let nodes = mg.nodes_ordered();
    if nodes.is_empty() {
        return true; // null graph; caller raises before reaching here
    }
    let mut visited: HashSet<&str> = HashSet::with_capacity(nodes.len());
    let start = nodes[0];
    visited.insert(start);
    let mut queue: VecDeque<&str> = VecDeque::new();
    queue.push_back(start);
    while let Some(node) = queue.pop_front() {
        if let Some(nbrs) = mg.neighbors(node) {
            for v in nbrs {
                if visited.insert(v) {
                    queue.push_back(v);
                }
            }
        }
    }
    visited.len() == nodes.len()
}

/// br-r37-c1-fyxma2 (cc): the connected component containing `start` in a MultiGraph,
/// by direct BFS over the adjacency.
fn multigraph_node_connected_component<'a>(
    mg: &'a fnx_classes::MultiGraph,
    start: &str,
) -> Vec<&'a str> {
    use std::collections::{HashSet, VecDeque};
    let mut comp: Vec<&'a str> = Vec::new();
    let nodes = mg.nodes_ordered();
    let start_ref: &'a str = match nodes.iter().copied().find(|&n| n == start) {
        Some(s) => s,
        None => return comp,
    };
    let mut visited: HashSet<&'a str> = HashSet::new();
    visited.insert(start_ref);
    comp.push(start_ref);
    let mut queue: VecDeque<&'a str> = VecDeque::new();
    queue.push_back(start_ref);
    while let Some(node) = queue.pop_front() {
        if let Some(nbrs) = mg.neighbors(node) {
            for v in nbrs {
                if visited.insert(v) {
                    comp.push(v);
                    queue.push_back(v);
                }
            }
        }
    }
    comp
}

/// br-r37-c1-fyxma3 (cc): single-source BFS distances + discovery parents over a
/// MultiGraph's adjacency directly (no intermediate simple-Graph build). Distance is
/// multiplicity-invariant, and processing mg.neighbors() in adjacency order yields the
/// same discovery parents as nx's BFS over the converted simple graph. Returns
/// (node, length, parent) in BFS-discovery order, matching the simple-graph kernel.
fn multigraph_sssp_length_with_parents<'a>(
    mg: &'a fnx_classes::MultiGraph,
    source: &str,
    cutoff: Option<usize>,
) -> Vec<(&'a str, usize, Option<&'a str>)> {
    use std::collections::{HashSet, VecDeque};
    let mut out: Vec<(&'a str, usize, Option<&'a str>)> = Vec::new();
    let nodes = mg.nodes_ordered();
    let source_ref: &'a str = match nodes.iter().copied().find(|&n| n == source) {
        Some(s) => s,
        None => return out,
    };
    let mut visited: HashSet<&'a str> = HashSet::new();
    visited.insert(source_ref);
    out.push((source_ref, 0, None));
    let mut queue: VecDeque<(&'a str, usize)> = VecDeque::new();
    queue.push_back((source_ref, 0));
    while let Some((node, dist)) = queue.pop_front() {
        if let Some(c) = cutoff {
            if dist >= c {
                continue;
            }
        }
        if let Some(nbrs) = mg.neighbors(node) {
            for v in nbrs {
                if visited.insert(v) {
                    out.push((v, dist + 1, Some(node)));
                    queue.push_back((v, dist + 1));
                }
            }
        }
    }
    out
}

/// br-r37-c1-ubizp (cc): single-source shortest PATHS over a MultiGraph's adjacency
/// directly (no simple-Graph build). Builds each node's path incrementally from its
/// discovery parent's path (paths[v] = paths[parent] + [v]), processing neighbors in
/// adjacency order to match nx's BFS-tree paths. Returns (node, path) in BFS order.
fn multigraph_sssp_paths<'a>(
    mg: &'a fnx_classes::MultiGraph,
    source: &str,
    cutoff: Option<usize>,
) -> Vec<(String, Vec<String>)> {
    use std::collections::{HashMap, VecDeque};
    let mut out: Vec<(String, Vec<String>)> = Vec::new();
    let nodes = mg.nodes_ordered();
    let source_ref: &'a str = match nodes.iter().copied().find(|&n| n == source) {
        Some(s) => s,
        None => return out,
    };
    // paths held as &str (clone = cheap pointer copies, like nx's list-of-refs);
    // materialized into owned Strings exactly once, at push time.
    let mut path_of: HashMap<&'a str, Vec<&'a str>> = HashMap::new();
    path_of.insert(source_ref, vec![source_ref]);
    out.push((source_ref.to_owned(), vec![source_ref.to_owned()]));
    let mut queue: VecDeque<(&'a str, usize)> = VecDeque::new();
    queue.push_back((source_ref, 0));
    while let Some((node, dist)) = queue.pop_front() {
        if let Some(c) = cutoff {
            if dist >= c {
                continue;
            }
        }
        if let Some(nbrs) = mg.neighbors(node) {
            let parent_path = path_of[node].clone();
            for v in nbrs {
                if !path_of.contains_key(v) {
                    let mut p = parent_path.clone();
                    p.push(v);
                    out.push((v.to_owned(), p.iter().map(|s| s.to_string()).collect()));
                    path_of.insert(v, p);
                    queue.push_back((v, dist + 1));
                }
            }
        }
    }
    out
}

/// br-r37-c1-ubizp (cc): unweighted single-pair distance over a MultiGraph by a
/// target-early-exit BFS over the adjacency (no simple-Graph build). Distance is
/// multiplicity-invariant. Returns Some(distance) or None if target is unreachable.
fn multigraph_target_bfs_distance(
    mg: &fnx_classes::MultiGraph,
    source: &str,
    target: &str,
) -> Option<usize> {
    use std::collections::{HashSet, VecDeque};
    if source == target {
        return Some(0);
    }
    // O(1) source resolution: seed the BFS from source's neighbors directly (one hash
    // lookup) instead of an O(|V|) scan to find the borrowed source &str. The source
    // never re-enters the frontier (skip neighbors equal to it), so no revisit loop.
    let mut visited: HashSet<&str> = HashSet::new();
    let mut queue: VecDeque<(&str, usize)> = VecDeque::new();
    if let Some(nbrs) = mg.neighbors(source) {
        for v in nbrs {
            if v == target {
                return Some(1);
            }
            if v != source && visited.insert(v) {
                queue.push_back((v, 1));
            }
        }
    }
    while let Some((node, dist)) = queue.pop_front() {
        if let Some(nbrs) = mg.neighbors(node) {
            for v in nbrs {
                if v == target {
                    return Some(dist + 1);
                }
                if v != source && visited.insert(v) {
                    queue.push_back((v, dist + 1));
                }
            }
        }
    }
    None
}

/// br-r37-c1-zid1b (cc): single-source BFS distances + discovery parents over a
/// MultiDiGraph's successor adjacency directly (no simple-DiGraph build). Mirrors the
/// MultiGraph helper using successors() for the forward direction. Distance is
/// multiplicity-invariant; processing successors in order matches nx's discovery.
fn multidigraph_sssp_length_with_parents<'a>(
    mdg: &'a fnx_classes::digraph::MultiDiGraph,
    source: &str,
    cutoff: Option<usize>,
) -> Vec<(&'a str, usize, Option<&'a str>)> {
    use std::collections::{HashSet, VecDeque};
    let mut out: Vec<(&'a str, usize, Option<&'a str>)> = Vec::new();
    let nodes = mdg.nodes_ordered();
    let source_ref: &'a str = match nodes.iter().copied().find(|&n| n == source) {
        Some(s) => s,
        None => return out,
    };
    let mut visited: HashSet<&'a str> = HashSet::new();
    visited.insert(source_ref);
    out.push((source_ref, 0, None));
    let mut queue: VecDeque<(&'a str, usize)> = VecDeque::new();
    queue.push_back((source_ref, 0));
    while let Some((node, dist)) = queue.pop_front() {
        if let Some(c) = cutoff {
            if dist >= c {
                continue;
            }
        }
        if let Some(succs) = mdg.successors(node) {
            for v in succs {
                if visited.insert(v) {
                    out.push((v, dist + 1, Some(node)));
                    queue.push_back((v, dist + 1));
                }
            }
        }
    }
    out
}

/// br-r37-c1-zid1b (cc): weakly-connected components of a MultiDiGraph by direct BFS
/// over the UNDIRECTED adjacency (successors ∪ predecessors) — no simple-DiGraph build.
/// Multiplicity is irrelevant to weak connectivity. Components in node-iteration order.
fn multidigraph_weak_components_borrowed<'a>(
    mdg: &'a fnx_classes::digraph::MultiDiGraph,
) -> Vec<Vec<&'a str>> {
    use std::collections::{HashSet, VecDeque};
    let nodes = mdg.nodes_ordered();
    let mut visited: HashSet<&'a str> = HashSet::with_capacity(nodes.len());
    let mut components: Vec<Vec<&'a str>> = Vec::new();
    for &start in &nodes {
        if !visited.insert(start) {
            continue;
        }
        let mut comp: Vec<&'a str> = vec![start];
        let mut queue: VecDeque<&'a str> = VecDeque::new();
        queue.push_back(start);
        while let Some(node) = queue.pop_front() {
            if let Some(succs) = mdg.successors(node) {
                for v in succs {
                    if visited.insert(v) {
                        comp.push(v);
                        queue.push_back(v);
                    }
                }
            }
            if let Some(preds) = mdg.predecessors(node) {
                for v in preds {
                    if visited.insert(v) {
                        comp.push(v);
                        queue.push_back(v);
                    }
                }
            }
        }
        components.push(comp);
    }
    components
}

/// br-r37-c1-zid1b (cc): is a MultiDiGraph weakly connected? early-exit BFS over the
/// undirected adjacency (successors ∪ predecessors) from the first node.
fn multidigraph_is_weakly_connected(mdg: &fnx_classes::digraph::MultiDiGraph) -> bool {
    use std::collections::{HashSet, VecDeque};
    let nodes = mdg.nodes_ordered();
    if nodes.is_empty() {
        return true;
    }
    let mut visited: HashSet<&str> = HashSet::with_capacity(nodes.len());
    let start = nodes[0];
    visited.insert(start);
    let mut queue: VecDeque<&str> = VecDeque::new();
    queue.push_back(start);
    while let Some(node) = queue.pop_front() {
        if let Some(succs) = mdg.successors(node) {
            for v in succs {
                if visited.insert(v) {
                    queue.push_back(v);
                }
            }
        }
        if let Some(preds) = mdg.predecessors(node) {
            for v in preds {
                if visited.insert(v) {
                    queue.push_back(v);
                }
            }
        }
    }
    visited.len() == nodes.len()
}

/// br-r37-c1-zid1b (cc): unweighted single-pair directed distance over a MultiDiGraph
/// by a target-early-exit BFS over the SUCCESSOR adjacency (no simple-DiGraph build),
/// O(1) source seeding. Multiplicity-invariant. Some(distance) or None if unreachable.
fn multidigraph_target_bfs_distance(
    mdg: &fnx_classes::digraph::MultiDiGraph,
    source: &str,
    target: &str,
) -> Option<usize> {
    use std::collections::{HashSet, VecDeque};
    if source == target {
        return Some(0);
    }
    let mut visited: HashSet<&str> = HashSet::new();
    let mut queue: VecDeque<(&str, usize)> = VecDeque::new();
    if let Some(succs) = mdg.successors(source) {
        for v in succs {
            if v == target {
                return Some(1);
            }
            if v != source && visited.insert(v) {
                queue.push_back((v, 1));
            }
        }
    }
    while let Some((node, dist)) = queue.pop_front() {
        if let Some(succs) = mdg.successors(node) {
            for v in succs {
                if v == target {
                    return Some(dist + 1);
                }
                if v != source && visited.insert(v) {
                    queue.push_back((v, dist + 1));
                }
            }
        }
    }
    None
}

/// br-r37-c1-zid1b (cc): BFS reachable-count over an integer CSR adjacency from `start`.
fn csr_reach_count(adj: &[Vec<usize>], start: usize, n: usize) -> usize {
    use std::collections::VecDeque;
    let mut visited = vec![false; n];
    visited[start] = true;
    let mut count = 1usize;
    let mut queue: VecDeque<usize> = VecDeque::new();
    queue.push_back(start);
    while let Some(node) = queue.pop_front() {
        for &v in &adj[node] {
            if !visited[v] {
                visited[v] = true;
                count += 1;
                queue.push_back(v);
            }
        }
    }
    count
}

/// br-r37-c1-zid1b (cc): is a MultiDiGraph strongly connected? Build an integer CSR
/// once (one String->index pass), then forward + reverse reachability from node 0 over
/// the integer adjacency (no per-BFS String hashing / Vec allocs, no simple-DiGraph
/// build). Multiplicity-invariant. Mirrors strongly_connected_via_reachability.
fn multidigraph_is_strongly_connected(mdg: &fnx_classes::digraph::MultiDiGraph) -> bool {
    use std::collections::HashMap;
    let nodes = mdg.nodes_ordered();
    let n = nodes.len();
    if n == 0 {
        return true;
    }
    let index: HashMap<&str, usize> = nodes.iter().enumerate().map(|(i, &nd)| (nd, i)).collect();
    let mut succ: Vec<Vec<usize>> = vec![Vec::new(); n];
    let mut pred: Vec<Vec<usize>> = vec![Vec::new(); n];
    for (i, &nd) in nodes.iter().enumerate() {
        if let Some(ss) = mdg.successors(nd) {
            for s in ss {
                if let Some(&j) = index.get(s) {
                    succ[i].push(j);
                    pred[j].push(i);
                }
            }
        }
    }
    if csr_reach_count(&succ, 0, n) != n {
        return false;
    }
    csr_reach_count(&pred, 0, n) == n
}

/// br-r37-c1-zid1b (cc): BFS tree edges (parent, child) from `source` over a
/// MultiDiGraph's successor adjacency — mirrors bfs_edges_directed for descendants,
/// processing successors in order so discovery parents match nx. No simple-DiGraph build.
fn multidigraph_bfs_edges(
    mdg: &fnx_classes::digraph::MultiDiGraph,
    source: &str,
) -> Vec<(String, String)> {
    use std::collections::{HashSet, VecDeque};
    let mut edges: Vec<(String, String)> = Vec::new();
    let nodes = mdg.nodes_ordered();
    let source_ref = match nodes.iter().copied().find(|&n| n == source) {
        Some(s) => s,
        None => return edges,
    };
    let mut visited: HashSet<&str> = HashSet::new();
    visited.insert(source_ref);
    let mut queue: VecDeque<&str> = VecDeque::new();
    queue.push_back(source_ref);
    while let Some(node) = queue.pop_front() {
        if let Some(succs) = mdg.successors(node) {
            for v in succs {
                if visited.insert(v) {
                    edges.push((node.to_owned(), v.to_owned()));
                    queue.push_back(v);
                }
            }
        }
    }
    edges
}

/// br-r37-c1-zid1b (cc): reverse BFS tree edges (node, predecessor) from `source` over
/// a MultiDiGraph's PREDECESSOR adjacency — mirrors bfs_edges_directed_reverse for
/// ancestors. No simple-DiGraph build.
fn multidigraph_bfs_edges_reverse(
    mdg: &fnx_classes::digraph::MultiDiGraph,
    source: &str,
) -> Vec<(String, String)> {
    use std::collections::{HashSet, VecDeque};
    let mut edges: Vec<(String, String)> = Vec::new();
    let nodes = mdg.nodes_ordered();
    let source_ref = match nodes.iter().copied().find(|&n| n == source) {
        Some(s) => s,
        None => return edges,
    };
    let mut visited: HashSet<&str> = HashSet::new();
    visited.insert(source_ref);
    let mut queue: VecDeque<&str> = VecDeque::new();
    queue.push_back(source_ref);
    while let Some(node) = queue.pop_front() {
        if let Some(preds) = mdg.predecessors(node) {
            for v in preds {
                if visited.insert(v) {
                    edges.push((node.to_owned(), v.to_owned()));
                    queue.push_back(v);
                }
            }
        }
    }
    edges
}

/// br-r37-c1-zid1b2 (cc): is a MultiDiGraph a DAG? Kahn's algorithm over an integer CSR
/// of DISTINCT successors (parallel edges don't affect acyclicity; a self-loop does).
/// Order-invariant boolean — no simple-DiGraph build. True iff all nodes get removed.
fn multidigraph_is_dag(mdg: &fnx_classes::digraph::MultiDiGraph) -> bool {
    use std::collections::{HashMap, HashSet, VecDeque};
    let nodes = mdg.nodes_ordered();
    let n = nodes.len();
    if n == 0 {
        return true;
    }
    let index: HashMap<&str, usize> = nodes.iter().enumerate().map(|(i, &nd)| (nd, i)).collect();
    let mut succ: Vec<Vec<usize>> = vec![Vec::new(); n];
    let mut indeg: Vec<usize> = vec![0; n];
    for (i, &nd) in nodes.iter().enumerate() {
        if let Some(ss) = mdg.successors(nd) {
            let mut seen: HashSet<usize> = HashSet::new();
            for s in ss {
                if let Some(&j) = index.get(s) {
                    if seen.insert(j) {
                        succ[i].push(j);
                        indeg[j] += 1;
                    }
                }
            }
        }
    }
    let mut queue: VecDeque<usize> = (0..n).filter(|&i| indeg[i] == 0).collect();
    let mut processed = 0usize;
    while let Some(u) = queue.pop_front() {
        processed += 1;
        for &v in &succ[u] {
            indeg[v] -= 1;
            if indeg[v] == 0 {
                queue.push_back(v);
            }
        }
    }
    processed == n
}

#[pyfunction]
pub fn is_connected(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<bool> {
    let gr = extract_graph(g)?;
    require_undirected(&gr, "is_connected")?;
    // br-r37-c1-fyxma2: MultiGraph uses a direct-adjacency BFS (early-exit) instead
    // of building a full simple Graph first (was 11x slower than the Graph path).
    if let GraphRef::MultiUndirected { mg, .. } = &gr {
        let inner = &mg.inner;
        if inner.nodes_ordered().is_empty() {
            return Err(crate::NetworkXPointlessConcept::new_err(
                "Connectivity is undefined for the null graph.",
            ));
        }
        return Ok(py.allow_threads(|| multigraph_is_connected(inner)));
    }
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
        GraphRef::MultiUndirected { .. } => {
            let simple = gr.undirected();
            (simple.nodes_ordered().len(), simple.edge_count(), false)
        }
        GraphRef::MultiDirected { .. } => {
            let simple_dg = gr.digraph().expect("is_directed checked above");
            (
                simple_dg.nodes_ordered().len(),
                simple_dg.edge_count(),
                true,
            )
        }
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
/// comp : list of sets
///     A list of sets, one per connected component, each containing
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
    // br-r37-c1-fyxma (cc): MultiGraph BFSes DIRECTLY over the adjacency (a visited
    // HashSet of node keys) instead of first building a full simple Graph via
    // multigraph_to_simple_graph_structure_only. That conversion cloned every
    // node+edge key to String and rebuilt the IndexMap/IndexSet adjacency
    // (~8ms / 114x slower than the Graph path on 1500n/6000e). Multiplicity is
    // irrelevant to connectivity, so the direct BFS is identical to nx's own
    // multigraph walk and skips the intermediate Graph entirely.
    //
    // br-r37-c1-anace: the simple path routes through the borrowed BFS variant --
    // skips the ~|V| String::to_owned allocations the public API performs to wrap
    // the result in Vec<Vec<String>>; emit Python sets directly.
    let components: Vec<Vec<&str>> = match &gr {
        GraphRef::MultiUndirected { mg, .. } => {
            let inner = &mg.inner;
            py.allow_threads(|| multigraph_connected_components_borrowed(inner))
        }
        _ => {
            let inner = gr.undirected();
            py.allow_threads(|| fnx_algorithms::connected_components_borrowed(inner).0)
        }
    };
    components
        .iter()
        .map(|comp| {
            pyo3::types::PySet::new(
                py,
                comp.iter()
                    .map(|node| gr.py_node_key(py, node))
                    .collect::<Vec<_>>(),
            )
            .map(|set| set.into_any().unbind())
        })
        .collect()
}

/// br-r37-c1-fyxma: connected components of a MultiGraph by direct BFS over the
/// adjacency (no intermediate simple-Graph construction). Multiplicity does not
/// affect connectivity, so visiting each distinct neighbor once via a node-key
/// HashSet yields the same components as networkx — at int-CSR-class speed.
fn multigraph_connected_components_borrowed(mg: &fnx_classes::MultiGraph) -> Vec<Vec<&str>> {
    use std::collections::{HashSet, VecDeque};
    let nodes = mg.nodes_ordered();
    let mut visited: HashSet<&str> = HashSet::with_capacity(nodes.len());
    let mut components: Vec<Vec<&str>> = Vec::new();
    for &start in &nodes {
        if !visited.insert(start) {
            continue;
        }
        let mut comp: Vec<&str> = vec![start];
        let mut queue: VecDeque<&str> = VecDeque::new();
        queue.push_back(start);
        while let Some(node) = queue.pop_front() {
            if let Some(nbrs) = mg.neighbors(node) {
                for v in nbrs {
                    if visited.insert(v) {
                        comp.push(v);
                        queue.push_back(v);
                    }
                }
            }
        }
        components.push(comp);
    }
    components
}

/// Return the number of connected components.
/// Raises ``NetworkXNotImplemented`` on DiGraph.
#[pyfunction]
pub fn number_connected_components(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<usize> {
    let gr = extract_graph(g)?;
    require_undirected(&gr, "number_connected_components")?;
    // br-r37-c1-fyxma2: MultiGraph counts components via direct-adjacency BFS
    // instead of building a full simple Graph first (was 12x slower).
    if let GraphRef::MultiUndirected { mg, .. } = &gr {
        let inner = &mg.inner;
        return Ok(py.allow_threads(|| multigraph_connected_components_borrowed(inner).len()));
    }
    let inner = gr.undirected();
    Ok(py.allow_threads(|| fnx_algorithms::number_connected_components(inner).count))
}

/// Return the node connectivity of the graph.
#[pyfunction]
#[pyo3(signature = (g, s=None, t=None))]
pub fn node_connectivity(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    s: Option<&Bound<'_, PyAny>>,
    t: Option<&Bound<'_, PyAny>>,
) -> PyResult<usize> {
    let gr = extract_graph(g)?;

    if s.is_some() != t.is_some() {
        return Err(NetworkXError::new_err(
            "Both s and t must be specified, or neither.",
        ));
    }

    if let (Some(source), Some(sink)) = (s, t) {
        let (s_name, t_name) = flow_terminals(py, &gr, source, sink)?;
        if gr.is_directed() {
            let dg = gr.digraph().expect("is_directed checked above");
            Ok(py
                .allow_threads(|| fnx_algorithms::node_connectivity_directed(dg, &s_name, &t_name))
                .value)
        } else {
            let inner = gr.undirected();
            Ok(py
                .allow_threads(|| fnx_algorithms::node_connectivity(inner, &s_name, &t_name).value))
        }
    } else {
        if gr.is_directed() {
            let dg = gr.digraph().expect("is_directed checked above");
            Ok(py.allow_threads(|| fnx_algorithms::node_connectivity_directed_global(dg).value))
        } else {
            let inner = gr.undirected();
            Ok(py.allow_threads(|| fnx_algorithms::global_node_connectivity(inner).value))
        }
    }
}

/// Approximate local node connectivity for an undirected simple Graph.
#[pyfunction]
#[pyo3(signature = (g, source, target, cutoff=None))]
pub fn approx_local_node_connectivity_undirected_rust(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    source: &Bound<'_, PyAny>,
    target: &Bound<'_, PyAny>,
    cutoff: Option<usize>,
) -> PyResult<usize> {
    let gr = extract_graph(g)?;
    let GraphRef::Undirected(pg) = gr else {
        return Err(crate::NetworkXNotImplemented::new_err(
            "not implemented for directed or multigraph type",
        ));
    };

    let source_name = node_key_to_string(py, source)?;
    if !pg.inner.has_node(&source_name) {
        return Err(NetworkXError::new_err(format!(
            "Node {source_name} is not in the graph."
        )));
    }
    let target_name = node_key_to_string(py, target)?;
    if !pg.inner.has_node(&target_name) {
        return Err(NetworkXError::new_err(format!(
            "Node {target_name} is not in the graph."
        )));
    }
    if source_name == target_name {
        return Err(NetworkXError::new_err(
            "source and target have to be different nodes.",
        ));
    }

    let inner = &pg.inner;
    Ok(py.allow_threads(|| {
        fnx_algorithms::approximate_local_node_connectivity(
            inner,
            &source_name,
            &target_name,
            cutoff,
        )
    }))
}

/// Return a minimum node cut of the graph.
#[pyfunction]
#[pyo3(signature = (g, s=None, t=None, flow_func=None))]
pub fn minimum_node_cut(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    s: Option<Bound<'_, PyAny>>,
    t: Option<Bound<'_, PyAny>>,
    flow_func: Option<Bound<'_, PyAny>>,
) -> PyResult<Vec<PyObject>> {
    if s.is_some() != t.is_some() {
        return Err(NetworkXError::new_err(
            "Both s and t must be specified, or neither.",
        ));
    }
    if flow_func.is_some() {
        return Err(crate::NetworkXNotImplemented::new_err(
            "franken_networkx currently only supports the default flow_func for minimum_node_cut",
        ));
    }
    let gr = extract_graph(g)?;
    if matches!(
        gr,
        GraphRef::MultiUndirected { .. } | GraphRef::MultiDirected { .. }
    ) {
        return Err(crate::NetworkXNotImplemented::new_err(
            "not implemented for multigraph type",
        ));
    }
    let result = if let (Some(source), Some(sink)) = (s.as_ref(), t.as_ref()) {
        let (s_name, t_name) = flow_terminals(py, &gr, source, sink)?;
        if gr.is_directed() {
            let dg = gr.digraph().expect("is_directed checked above");
            py.allow_threads(|| fnx_algorithms::minimum_node_cut_directed(dg, &s_name, &t_name))
        } else {
            let inner = gr.undirected();
            py.allow_threads(|| fnx_algorithms::minimum_node_cut(inner, &s_name, &t_name))
        }
    } else {
        if gr.is_directed() {
            let dg = gr.digraph().expect("is_directed checked above");
            if !py.allow_threads(|| fnx_algorithms::is_weakly_connected(dg)) {
                return Err(NetworkXError::new_err("Input graph is not connected"));
            }
            py.allow_threads(|| fnx_algorithms::global_minimum_node_cut_directed(dg))
        } else {
            let inner = gr.undirected();
            if !py.allow_threads(|| fnx_algorithms::is_connected(inner).is_connected) {
                return Err(NetworkXError::new_err("Input graph is not connected"));
            }
            py.allow_threads(|| fnx_algorithms::global_minimum_node_cut(inner))
        }
    };
    Ok(result
        .cut_nodes
        .iter()
        .map(|n| gr.py_node_key(py, n))
        .collect())
}

/// Return the edge connectivity of the graph.
#[pyfunction]
#[pyo3(signature = (g, s=None, t=None, cutoff=None))]
pub fn edge_connectivity(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    s: Option<&Bound<'_, PyAny>>,
    t: Option<&Bound<'_, PyAny>>,
    cutoff: Option<f64>,
) -> PyResult<f64> {
    let gr = extract_graph(g)?;

    if s.is_some() != t.is_some() {
        return Err(NetworkXError::new_err(
            "Both s and t must be specified, or neither.",
        ));
    }

    if cutoff.is_some() {
        return Err(crate::NetworkXNotImplemented::new_err(
            "franken_networkx currently does not support the cutoff parameter for edge_connectivity",
        ));
    }

    let cap = "capacity".to_owned();

    if let (Some(source), Some(sink)) = (s, t) {
        let (s_name, t_name) = flow_terminals(py, &gr, source, sink)?;
        if gr.is_directed() {
            let dg = gr.digraph().expect("is_directed checked above");
            let result = py.allow_threads(move || {
                fnx_algorithms::edge_connectivity_edmonds_karp_directed(dg, &s_name, &t_name, &cap)
            });
            Ok(result.map_err(flow_py_error)?.value)
        } else {
            let inner = gr.undirected();
            let result = py.allow_threads(move || {
                fnx_algorithms::edge_connectivity_edmonds_karp(inner, &s_name, &t_name, &cap)
            });
            Ok(result.map_err(flow_py_error)?.value)
        }
    } else {
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
            return graph_degree_centrality_to_dict(py, pg);
        }
        GraphRef::Directed { dg, .. } => {
            let inner = &dg.inner;
            py.allow_threads(|| fnx_algorithms::degree_centrality_directed(inner))
        }
        _ => {
            if gr.is_directed() {
                let inner = gr.digraph().expect("is_directed checked above");
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
                let inner = gr.digraph().expect("is_directed checked above");
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
                let inner = gr.digraph().expect("is_directed checked above");
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
    // br-r37-c1-ua4i8: use the checked variant so non-convergence
    // raises ``PowerIterationFailedConvergence`` matching nx instead
    // of silently returning the un-converged (and possibly wrong)
    // normalized vector.
    let result = match &gr {
        GraphRef::Undirected(pg) => {
            let inner = &pg.inner;
            py.allow_threads(|| fnx_algorithms::katz_centrality_checked(inner))
        }
        GraphRef::Directed { dg, .. } => {
            let inner = &dg.inner;
            py.allow_threads(|| fnx_algorithms::katz_centrality_directed_checked(inner))
        }
        _ => {
            if gr.is_directed() {
                let inner = gr.digraph().expect("is_directed checked above");
                py.allow_threads(|| fnx_algorithms::katz_centrality_directed_checked(inner))
            } else {
                let inner = gr.undirected();
                py.allow_threads(|| fnx_algorithms::katz_centrality_checked(inner))
            }
        }
    };
    let result =
        result.map_err(|err| crate::PowerIterationFailedConvergence::new_err(err.iterations))?;
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
#[pyo3(signature = (g, k=None, normalized=true, weight=None, endpoints=false, seed=None))]
pub fn betweenness_centrality(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    k: Option<Bound<'_, PyAny>>,
    normalized: bool,
    weight: Option<&str>,
    endpoints: bool,
    seed: Option<Bound<'_, PyAny>>,
) -> PyResult<Py<PyDict>> {
    if k.is_some() || seed.is_some() {
        return Err(crate::NetworkXNotImplemented::new_err(
            "franken_networkx currently only supports k=None and seed=None for betweenness_centrality",
        ));
    }
    let gr = extract_graph(g)?;
    log::info!(target: "franken_networkx", "betweenness_centrality: nodes={}", gr.undirected().node_count());
    // br-r37-c1-7iiky: weighted betweenness (a string `weight` key) runs the
    // native weighted Brandes (Dijkstra SSSP, parallel, byte-exact with nx)
    // instead of delegating to networkx's single-threaded Python. The Python
    // wrapper only reaches here for finite, non-negative numeric weights on a
    // simple Graph/DiGraph; everything else delegates to nx for parity.
    let result = if let Some(weight_attr) = weight {
        match &gr {
            GraphRef::Undirected(pg) => {
                let inner = &pg.inner;
                py.allow_threads(|| {
                    fnx_algorithms::betweenness_centrality_weighted(
                        inner,
                        Some(weight_attr),
                        normalized,
                        endpoints,
                    )
                })
            }
            GraphRef::Directed { dg, .. } => {
                let inner = &dg.inner;
                py.allow_threads(|| {
                    fnx_algorithms::betweenness_centrality_weighted_directed(
                        inner,
                        Some(weight_attr),
                        normalized,
                        endpoints,
                    )
                })
            }
            _ => {
                if gr.is_directed() {
                    let inner = gr.digraph().expect("is_directed checked above");
                    py.allow_threads(|| {
                        fnx_algorithms::betweenness_centrality_weighted_directed(
                            inner,
                            Some(weight_attr),
                            normalized,
                            endpoints,
                        )
                    })
                } else {
                    let inner = gr.undirected();
                    py.allow_threads(|| {
                        fnx_algorithms::betweenness_centrality_weighted(
                            inner,
                            Some(weight_attr),
                            normalized,
                            endpoints,
                        )
                    })
                }
            }
        }
    } else {
        match &gr {
            GraphRef::Undirected(pg) => {
                let inner = &pg.inner;
                py.allow_threads(|| {
                    fnx_algorithms::betweenness_centrality_with_params(inner, normalized, endpoints)
                })
            }
            GraphRef::Directed { dg, .. } => {
                let inner = &dg.inner;
                py.allow_threads(|| {
                    fnx_algorithms::betweenness_centrality_directed_with_params(
                        inner, normalized, endpoints,
                    )
                })
            }
            _ => {
                if gr.is_directed() {
                    let inner = gr.digraph().expect("is_directed checked above");
                    py.allow_threads(|| {
                        fnx_algorithms::betweenness_centrality_directed_with_params(
                            inner, normalized, endpoints,
                        )
                    })
                } else {
                    let inner = gr.undirected();
                    py.allow_threads(|| {
                        fnx_algorithms::betweenness_centrality_with_params(
                            inner, normalized, endpoints,
                        )
                    })
                }
            }
        }
    };
    centrality_to_dict(py, &gr, &result.scores)
}

/// Compute unweighted betweenness centrality from a sampled source list.
#[pyfunction]
#[pyo3(signature = (g, sources, normalized=true, endpoints=false))]
pub fn betweenness_centrality_sampled_rust(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    sources: Vec<Bound<'_, PyAny>>,
    normalized: bool,
    endpoints: bool,
) -> PyResult<Py<PyDict>> {
    let gr = extract_graph(g)?;
    let source_keys: Vec<String> = sources
        .iter()
        .map(|n| node_key_to_string(py, n))
        .collect::<PyResult<_>>()?;
    let src_refs: Vec<&str> = source_keys.iter().map(String::as_str).collect();
    let result = match &gr {
        GraphRef::Undirected(pg) => {
            let inner = &pg.inner;
            py.allow_threads(|| {
                fnx_algorithms::betweenness_centrality_sampled_with_params(
                    inner, &src_refs, normalized, endpoints,
                )
            })
        }
        GraphRef::Directed { dg, .. } => {
            let inner = &dg.inner;
            py.allow_threads(|| {
                fnx_algorithms::betweenness_centrality_sampled_directed_with_params(
                    inner, &src_refs, normalized, endpoints,
                )
            })
        }
        _ => {
            if gr.is_directed() {
                let inner = gr.digraph().expect("is_directed checked above");
                py.allow_threads(|| {
                    fnx_algorithms::betweenness_centrality_sampled_directed_with_params(
                        inner, &src_refs, normalized, endpoints,
                    )
                })
            } else {
                let inner = gr.undirected();
                py.allow_threads(|| {
                    fnx_algorithms::betweenness_centrality_sampled_with_params(
                        inner, &src_refs, normalized, endpoints,
                    )
                })
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
                let inner = gr.digraph().expect("is_directed checked above");
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

/// Weighted edge betweenness centrality (normalized). br-r37-c1-4v1mt: native
/// weighted Brandes (Dijkstra SSSP, parallel, byte-exact) for a string `weight`
/// key; returns a canonical-keyed dict that the Python wrapper re-keys into
/// `G.edges()` order, exactly like the unweighted path.
#[pyfunction]
pub fn edge_betweenness_centrality_weighted(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    weight: &str,
) -> PyResult<Py<PyDict>> {
    let gr = extract_graph(g)?;
    let result = match &gr {
        GraphRef::Undirected(pg) => {
            let inner = &pg.inner;
            py.allow_threads(|| {
                fnx_algorithms::edge_betweenness_centrality_weighted(inner, Some(weight))
            })
        }
        GraphRef::Directed { dg, .. } => {
            let inner = &dg.inner;
            py.allow_threads(|| {
                fnx_algorithms::edge_betweenness_centrality_weighted_directed(inner, Some(weight))
            })
        }
        _ => {
            if gr.is_directed() {
                let inner = gr.digraph().expect("is_directed checked above");
                py.allow_threads(|| {
                    fnx_algorithms::edge_betweenness_centrality_weighted_directed(
                        inner,
                        Some(weight),
                    )
                })
            } else {
                let inner = gr.undirected();
                py.allow_threads(|| {
                    fnx_algorithms::edge_betweenness_centrality_weighted(inner, Some(weight))
                })
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

/// Betweenness centrality restricted to source/target node subsets (unweighted).
#[pyfunction]
#[pyo3(signature = (g, sources, targets, normalized=false))]
pub fn betweenness_centrality_subset_rust(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    sources: Vec<Bound<'_, PyAny>>,
    targets: Vec<Bound<'_, PyAny>>,
    normalized: bool,
) -> PyResult<Py<PyDict>> {
    let gr = extract_graph(g)?;
    let source_keys: Vec<String> = sources
        .iter()
        .map(|n| node_key_to_string(py, n))
        .collect::<PyResult<_>>()?;
    let target_keys: Vec<String> = targets
        .iter()
        .map(|n| node_key_to_string(py, n))
        .collect::<PyResult<_>>()?;
    let src_refs: Vec<&str> = source_keys.iter().map(String::as_str).collect();
    let tgt_refs: Vec<&str> = target_keys.iter().map(String::as_str).collect();
    let result = match &gr {
        GraphRef::Undirected(pg) => {
            let inner = &pg.inner;
            py.allow_threads(|| {
                fnx_algorithms::betweenness_centrality_subset(
                    inner, &src_refs, &tgt_refs, normalized,
                )
            })
        }
        GraphRef::Directed { dg, .. } => {
            let inner = &dg.inner;
            py.allow_threads(|| {
                fnx_algorithms::betweenness_centrality_subset_directed(
                    inner, &src_refs, &tgt_refs, normalized,
                )
            })
        }
        _ => {
            if gr.is_directed() {
                let inner = gr.digraph().expect("is_directed checked above");
                py.allow_threads(|| {
                    fnx_algorithms::betweenness_centrality_subset_directed(
                        inner, &src_refs, &tgt_refs, normalized,
                    )
                })
            } else {
                let inner = gr.undirected();
                py.allow_threads(|| {
                    fnx_algorithms::betweenness_centrality_subset(
                        inner, &src_refs, &tgt_refs, normalized,
                    )
                })
            }
        }
    };
    centrality_to_dict(py, &gr, &result.scores)
}

/// Weighted subset betweenness. br-r37-c1-664w5: native weighted subset Brandes
/// (Dijkstra SSSP, byte-exact) for a string `weight` key.
#[pyfunction]
#[pyo3(signature = (g, sources, targets, weight, normalized=false))]
pub fn betweenness_centrality_subset_weighted_rust(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    sources: Vec<Bound<'_, PyAny>>,
    targets: Vec<Bound<'_, PyAny>>,
    weight: &str,
    normalized: bool,
) -> PyResult<Py<PyDict>> {
    let gr = extract_graph(g)?;
    let source_keys: Vec<String> = sources
        .iter()
        .map(|n| node_key_to_string(py, n))
        .collect::<PyResult<_>>()?;
    let target_keys: Vec<String> = targets
        .iter()
        .map(|n| node_key_to_string(py, n))
        .collect::<PyResult<_>>()?;
    let src_refs: Vec<&str> = source_keys.iter().map(String::as_str).collect();
    let tgt_refs: Vec<&str> = target_keys.iter().map(String::as_str).collect();
    let result = match &gr {
        GraphRef::Undirected(pg) => {
            let inner = &pg.inner;
            py.allow_threads(|| {
                fnx_algorithms::betweenness_centrality_subset_weighted(
                    inner,
                    &src_refs,
                    &tgt_refs,
                    Some(weight),
                    normalized,
                )
            })
        }
        GraphRef::Directed { dg, .. } => {
            let inner = &dg.inner;
            py.allow_threads(|| {
                fnx_algorithms::betweenness_centrality_subset_weighted_directed(
                    inner,
                    &src_refs,
                    &tgt_refs,
                    Some(weight),
                    normalized,
                )
            })
        }
        _ => {
            if gr.is_directed() {
                let inner = gr.digraph().expect("is_directed checked above");
                py.allow_threads(|| {
                    fnx_algorithms::betweenness_centrality_subset_weighted_directed(
                        inner,
                        &src_refs,
                        &tgt_refs,
                        Some(weight),
                        normalized,
                    )
                })
            } else {
                let inner = gr.undirected();
                py.allow_threads(|| {
                    fnx_algorithms::betweenness_centrality_subset_weighted(
                        inner,
                        &src_refs,
                        &tgt_refs,
                        Some(weight),
                        normalized,
                    )
                })
            }
        }
    };
    centrality_to_dict(py, &gr, &result.scores)
}

/// Edge betweenness centrality restricted to source/target node subsets (unweighted).
#[pyfunction]
#[pyo3(signature = (g, sources, targets, normalized=false))]
pub fn edge_betweenness_centrality_subset_rust(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    sources: Vec<Bound<'_, PyAny>>,
    targets: Vec<Bound<'_, PyAny>>,
    normalized: bool,
) -> PyResult<Py<PyDict>> {
    let gr = extract_graph(g)?;
    let source_keys: Vec<String> = sources
        .iter()
        .map(|n| node_key_to_string(py, n))
        .collect::<PyResult<_>>()?;
    let target_keys: Vec<String> = targets
        .iter()
        .map(|n| node_key_to_string(py, n))
        .collect::<PyResult<_>>()?;
    let src_refs: Vec<&str> = source_keys.iter().map(String::as_str).collect();
    let tgt_refs: Vec<&str> = target_keys.iter().map(String::as_str).collect();
    let result = match &gr {
        GraphRef::Undirected(pg) => {
            let inner = &pg.inner;
            py.allow_threads(|| {
                fnx_algorithms::edge_betweenness_centrality_subset(
                    inner, &src_refs, &tgt_refs, normalized,
                )
            })
        }
        GraphRef::Directed { dg, .. } => {
            let inner = &dg.inner;
            py.allow_threads(|| {
                fnx_algorithms::edge_betweenness_centrality_subset_directed(
                    inner, &src_refs, &tgt_refs, normalized,
                )
            })
        }
        _ => {
            if gr.is_directed() {
                let inner = gr.digraph().expect("is_directed checked above");
                py.allow_threads(|| {
                    fnx_algorithms::edge_betweenness_centrality_subset_directed(
                        inner, &src_refs, &tgt_refs, normalized,
                    )
                })
            } else {
                let inner = gr.undirected();
                py.allow_threads(|| {
                    fnx_algorithms::edge_betweenness_centrality_subset(
                        inner, &src_refs, &tgt_refs, normalized,
                    )
                })
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

/// Weighted subset edge betweenness. br-r37-c1-gqgds: native weighted subset
/// edge Brandes (Dijkstra SSSP, byte-exact) for a string `weight` key; returns a
/// canonical-keyed dict the Python wrapper re-keys into `G.edges()` order.
#[pyfunction]
#[pyo3(signature = (g, sources, targets, weight, normalized=false))]
pub fn edge_betweenness_centrality_subset_weighted_rust(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    sources: Vec<Bound<'_, PyAny>>,
    targets: Vec<Bound<'_, PyAny>>,
    weight: &str,
    normalized: bool,
) -> PyResult<Py<PyDict>> {
    let gr = extract_graph(g)?;
    let source_keys: Vec<String> = sources
        .iter()
        .map(|n| node_key_to_string(py, n))
        .collect::<PyResult<_>>()?;
    let target_keys: Vec<String> = targets
        .iter()
        .map(|n| node_key_to_string(py, n))
        .collect::<PyResult<_>>()?;
    let src_refs: Vec<&str> = source_keys.iter().map(String::as_str).collect();
    let tgt_refs: Vec<&str> = target_keys.iter().map(String::as_str).collect();
    let result = match &gr {
        GraphRef::Undirected(pg) => {
            let inner = &pg.inner;
            py.allow_threads(|| {
                fnx_algorithms::edge_betweenness_centrality_subset_weighted(
                    inner,
                    &src_refs,
                    &tgt_refs,
                    Some(weight),
                    normalized,
                )
            })
        }
        GraphRef::Directed { dg, .. } => {
            let inner = &dg.inner;
            py.allow_threads(|| {
                fnx_algorithms::edge_betweenness_centrality_subset_weighted_directed(
                    inner,
                    &src_refs,
                    &tgt_refs,
                    Some(weight),
                    normalized,
                )
            })
        }
        _ => {
            if gr.is_directed() {
                let inner = gr.digraph().expect("is_directed checked above");
                py.allow_threads(|| {
                    fnx_algorithms::edge_betweenness_centrality_subset_weighted_directed(
                        inner,
                        &src_refs,
                        &tgt_refs,
                        Some(weight),
                        normalized,
                    )
                })
            } else {
                let inner = gr.undirected();
                py.allow_threads(|| {
                    fnx_algorithms::edge_betweenness_centrality_subset_weighted(
                        inner,
                        &src_refs,
                        &tgt_refs,
                        Some(weight),
                        normalized,
                    )
                })
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

/// Return the load centrality for all nodes.
///
/// Load centrality of a node is the fraction of all shortest paths that
/// pass through that node.
///
/// Matches `networkx.load_centrality`.
#[pyfunction]
#[pyo3(signature = (g, v=None, cutoff=None, normalized=true, weight=None))]
pub fn load_centrality(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    v: Option<Bound<'_, PyAny>>,
    cutoff: Option<usize>,
    normalized: bool,
    weight: Option<&str>,
) -> PyResult<Py<PyDict>> {
    if v.is_some() || cutoff.is_some() || weight.is_some() {
        return Err(crate::NetworkXNotImplemented::new_err(
            "franken_networkx currently only supports default parameters for load_centrality (v, cutoff, weight unsupported)",
        ));
    }
    let gr = extract_graph(g)?;
    log::info!(target: "franken_networkx", "load_centrality: nodes={}", gr.undirected().node_count());
    let result = match &gr {
        GraphRef::Undirected(pg) => {
            let inner = &pg.inner;
            py.allow_threads(|| fnx_algorithms::load_centrality_normalized(inner, normalized))
        }
        GraphRef::Directed { dg, .. } => {
            let inner = &dg.inner;
            py.allow_threads(|| {
                fnx_algorithms::load_centrality_directed_normalized(inner, normalized)
            })
        }
        _ => {
            if gr.is_directed() {
                let inner = gr.digraph().expect("is_directed checked above");
                py.allow_threads(|| {
                    fnx_algorithms::load_centrality_directed_normalized(inner, normalized)
                })
            } else {
                let inner = gr.undirected();
                py.allow_threads(|| fnx_algorithms::load_centrality_normalized(inner, normalized))
            }
        }
    };
    centrality_to_dict(py, &gr, &result.scores)
}

/// Weighted percolation centrality. br-r37-c1-percw: native weighted percolation
/// (Dijkstra SSSP, parallel, byte-exact). `states` holds each node's percolation
/// state aligned to the graph's node-iteration order (the Python wrapper extracts
/// it from the node attribute / `states` dict).
#[pyfunction]
pub fn percolation_centrality_weighted(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    weight: &str,
    states: Vec<f64>,
) -> PyResult<Py<PyDict>> {
    let gr = extract_graph(g)?;
    let result = match &gr {
        GraphRef::Undirected(pg) => {
            let inner = &pg.inner;
            py.allow_threads(|| {
                fnx_algorithms::percolation_centrality_weighted(inner, Some(weight), &states)
            })
        }
        GraphRef::Directed { dg, .. } => {
            let inner = &dg.inner;
            py.allow_threads(|| {
                fnx_algorithms::percolation_centrality_weighted_directed(
                    inner,
                    Some(weight),
                    &states,
                )
            })
        }
        _ => {
            if gr.is_directed() {
                let inner = gr.digraph().expect("is_directed checked above");
                py.allow_threads(|| {
                    fnx_algorithms::percolation_centrality_weighted_directed(
                        inner,
                        Some(weight),
                        &states,
                    )
                })
            } else {
                let inner = gr.undirected();
                py.allow_threads(|| {
                    fnx_algorithms::percolation_centrality_weighted(inner, Some(weight), &states)
                })
            }
        }
    };
    centrality_to_dict(py, &gr, &result.scores)
}

/// Weighted Newman load centrality. br-r37-c1-loadw: native weighted load
/// (Dijkstra SSSP, parallel, byte-exact) for the whole-graph case. `value_rank`
/// is the position of each node in `sorted(G.nodes())` (computed by the Python
/// wrapper from the real node objects) — aligned to the graph's node-iteration
/// order — so the `onodes` `(length, vert)` tie-break matches nx's node-value
/// ordering exactly.
#[pyfunction]
pub fn load_centrality_weighted(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    weight: &str,
    value_rank: Vec<usize>,
    normalized: bool,
) -> PyResult<Py<PyDict>> {
    let gr = extract_graph(g)?;
    let result = match &gr {
        GraphRef::Undirected(pg) => {
            let inner = &pg.inner;
            py.allow_threads(|| {
                fnx_algorithms::load_centrality_weighted(
                    inner,
                    Some(weight),
                    &value_rank,
                    normalized,
                )
            })
        }
        GraphRef::Directed { dg, .. } => {
            let inner = &dg.inner;
            py.allow_threads(|| {
                fnx_algorithms::load_centrality_weighted_directed(
                    inner,
                    Some(weight),
                    &value_rank,
                    normalized,
                )
            })
        }
        _ => {
            if gr.is_directed() {
                let inner = gr.digraph().expect("is_directed checked above");
                py.allow_threads(|| {
                    fnx_algorithms::load_centrality_weighted_directed(
                        inner,
                        Some(weight),
                        &value_rank,
                        normalized,
                    )
                })
            } else {
                let inner = gr.undirected();
                py.allow_threads(|| {
                    fnx_algorithms::load_centrality_weighted(
                        inner,
                        Some(weight),
                        &value_rank,
                        normalized,
                    )
                })
            }
        }
    };
    centrality_to_dict(py, &gr, &result.scores)
}

/// Return the closeness vitality of nodes.
///
/// Closeness vitality of a node is the change in the Wiener index
/// of the graph when that node is removed.
///
/// Matches `networkx.closeness_vitality`.
#[pyfunction]
#[pyo3(signature = (g, node=None, weight=None, wiener_index=None))]
pub fn closeness_vitality(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    node: Option<Bound<'_, PyAny>>,
    weight: Option<&str>,
    wiener_index: Option<f64>,
) -> PyResult<PyObject> {
    // Currently we only support unweighted graphs
    if weight.is_some() {
        return Err(crate::NetworkXNotImplemented::new_err(
            "franken_networkx currently only supports unweighted closeness_vitality",
        ));
    }
    if wiener_index.is_some() {
        return Err(crate::NetworkXNotImplemented::new_err(
            "franken_networkx does not support precomputed wiener_index parameter",
        ));
    }

    let gr = extract_graph(g)?;
    log::info!(target: "franken_networkx", "closeness_vitality: nodes={}", gr.undirected().node_count());

    // If a specific node is requested, use the single-node function
    if let Some(node_obj) = node {
        let node_str = node_obj.extract::<String>()?;
        let inner = gr.undirected();
        let result =
            py.allow_threads(|| fnx_algorithms::closeness_vitality_single(inner, &node_str));
        match result {
            Some(v) => Ok(v.into_pyobject(py)?.unbind().into()),
            None => Err(crate::NodeNotFound::new_err(format!(
                "node {} not in graph",
                node_str
            ))),
        }
    } else {
        // Compute for all nodes
        let inner = gr.undirected();
        let result = py.allow_threads(|| fnx_algorithms::closeness_vitality(inner));
        let dict = PyDict::new(py);
        for (node_id, vitality) in &result.vitality {
            dict.set_item(gr.py_node_key(py, node_id), *vitality)?;
        }
        Ok(dict.unbind().into())
    }
}

/// Return the eigenvector centrality for all nodes.
#[pyfunction]
#[pyo3(signature = (g, max_iter=100, tol=1.0e-6, nstart=None, weight=None))]
pub fn eigenvector_centrality(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    max_iter: usize,
    tol: f64,
    nstart: Option<Bound<'_, PyAny>>,
    weight: Option<&str>,
) -> PyResult<Py<PyDict>> {
    if nstart.is_some() || weight.is_some() {
        return Err(crate::NetworkXNotImplemented::new_err(
            "franken_networkx currently only supports nstart=None and weight=None for eigenvector_centrality",
        ));
    }
    let gr = extract_graph(g)?;
    let (result, converged) = match &gr {
        GraphRef::Undirected(pg) => {
            let inner = &pg.inner;
            py.allow_threads(|| {
                fnx_algorithms::eigenvector_centrality_with_params(inner, max_iter, tol)
            })
        }
        GraphRef::Directed { dg, .. } => {
            let inner = &dg.inner;
            py.allow_threads(|| {
                fnx_algorithms::eigenvector_centrality_directed_with_params(inner, max_iter, tol)
            })
        }
        _ => {
            if gr.is_directed() {
                let inner = gr.digraph().expect("is_directed checked above");
                py.allow_threads(|| {
                    fnx_algorithms::eigenvector_centrality_directed_with_params(
                        inner, max_iter, tol,
                    )
                })
            } else {
                let inner = gr.undirected();
                py.allow_threads(|| {
                    fnx_algorithms::eigenvector_centrality_with_params(inner, max_iter, tol)
                })
            }
        }
    };
    if !converged {
        return Err(PowerIterationFailedConvergence::new_err(max_iter));
    }
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
#[pyo3(signature = (g, alpha=0.85, personalization=None, max_iter=100, tol=1.0e-6, nstart=None, weight="weight", dangling=None))]
pub fn pagerank(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    alpha: f64,
    personalization: Option<Bound<'_, PyAny>>,
    max_iter: isize,
    tol: f64,
    nstart: Option<Bound<'_, PyAny>>,
    weight: Option<&str>,
    dangling: Option<Bound<'_, PyAny>>,
) -> PyResult<Py<PyDict>> {
    if personalization.is_some() || nstart.is_some() || dangling.is_some() {
        return Err(crate::NetworkXNotImplemented::new_err(
            "franken_networkx pagerank does not yet support personalization, nstart, or dangling",
        ));
    }
    let max_iter_usize = usize::try_from(max_iter)
        .map_err(|_| PowerIterationFailedConvergence::new_err(max_iter))?;
    let gr = extract_graph(g)?;
    log::info!(target: "franken_networkx", "pagerank: nodes={}", gr.undirected().node_count());
    let result = match &gr {
        GraphRef::Undirected(pg) => {
            let inner = &pg.inner;
            py.allow_threads(|| {
                fnx_algorithms::pagerank_with_weight_checked(
                    inner,
                    alpha,
                    max_iter_usize,
                    tol,
                    weight,
                )
            })
        }
        GraphRef::Directed { dg, .. } => {
            let inner = &dg.inner;
            py.allow_threads(|| {
                fnx_algorithms::pagerank_with_weight_checked(
                    inner,
                    alpha,
                    max_iter_usize,
                    tol,
                    weight,
                )
            })
        }
        GraphRef::MultiUndirected { mg, .. } => {
            let graph = multigraph_to_pagerank_simple_graph(&mg.inner, weight);
            py.allow_threads(|| {
                fnx_algorithms::pagerank_with_weight_checked(
                    &graph,
                    alpha,
                    max_iter_usize,
                    tol,
                    Some(PAGERANK_WEIGHT_ATTR),
                )
            })
        }
        GraphRef::MultiDirected { mdg, .. } => {
            let graph = multidigraph_to_pagerank_simple_digraph(&mdg.inner, weight);
            py.allow_threads(|| {
                fnx_algorithms::pagerank_with_weight_checked(
                    &graph,
                    alpha,
                    max_iter_usize,
                    tol,
                    Some(PAGERANK_WEIGHT_ATTR),
                )
            })
        }
    };
    let result = result.map_err(|_| {
        crate::NetworkXNotImplemented::new_err(
            "franken_networkx pagerank fast-path requires non-negative edge weights",
        )
    })?;
    if !result.converged {
        return Err(PowerIterationFailedConvergence::new_err(max_iter));
    }
    centrality_to_dict(py, &gr, &result.scores)
}

/// Return HITS hubs and authorities scores.
#[pyfunction]
#[pyo3(signature = (g, max_iter=100, tol=1.0e-8, nstart=None, normalized=true))]
pub fn hits(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    max_iter: usize,
    tol: f64,
    nstart: Option<Bound<'_, PyAny>>,
    normalized: bool,
) -> PyResult<(Py<PyDict>, Py<PyDict>)> {
    if max_iter != 100 || (tol - 1.0e-8).abs() > f64::EPSILON || nstart.is_some() || !normalized {
        return Err(crate::NetworkXNotImplemented::new_err(
            "franken_networkx currently only supports default parameters for hits",
        ));
    }
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
                let inner = gr.digraph().expect("is_directed checked above");
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

/// br-r37-c1-d7etr: native directed degree assortativity ((out, in) pairs) for
/// simple DiGraphs — replaces the fnx->nx delegation (~5x). Returns `None` for
/// non-DiGraph inputs so the Python wrapper keeps its existing path.
#[pyfunction]
pub fn degree_assortativity_coefficient_directed(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
) -> PyResult<Option<f64>> {
    let gr = extract_graph(g)?;
    match &gr {
        GraphRef::Directed { dg, .. } => {
            let inner = &dg.inner;
            Ok(Some(py.allow_threads(|| {
                fnx_algorithms::degree_assortativity_coefficient_directed(inner).coefficient
            })))
        }
        _ => Ok(None),
    }
}

/// Return a list of nodes in decreasing voterank order.
#[pyfunction]
#[pyo3(signature = (g, number_of_nodes=None))]
pub fn voterank(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    number_of_nodes: Option<usize>,
) -> PyResult<Vec<PyObject>> {
    let gr = extract_graph(g)?;
    let result = match &gr {
        GraphRef::Undirected(pg) => {
            let inner = &pg.inner;
            py.allow_threads(|| fnx_algorithms::voterank(inner, number_of_nodes))
        }
        GraphRef::Directed { dg, .. } => {
            let inner = &dg.inner;
            py.allow_threads(|| fnx_algorithms::voterank_directed(inner, number_of_nodes))
        }
        _ => {
            if gr.is_directed() {
                let inner = gr.digraph().expect("is_directed checked above");
                py.allow_threads(|| fnx_algorithms::voterank_directed(inner, number_of_nodes))
            } else {
                let inner = gr.undirected();
                py.allow_threads(|| fnx_algorithms::voterank(inner, number_of_nodes))
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
    // br-r37-c1-djohp: kernel collapses multigraph input, silently
    // returning the simple-graph projection's clustering coefficient.
    // nx and the public wrapper both raise NetworkXNotImplemented on
    // multigraph; mirror that here.
    require_not_multigraph(&gr)?;
    let result = if gr.is_directed() {
        let dg = gr.digraph().expect("is_directed checked");
        py.allow_threads(|| fnx_algorithms::clustering_coefficient_directed(dg))
    } else {
        let inner = gr.undirected();
        py.allow_threads(|| fnx_algorithms::clustering_coefficient(inner))
    };
    centrality_to_dict(py, &gr, &result.scores)
}

/// Return the average clustering coefficient.
#[pyfunction]
pub fn average_clustering(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<f64> {
    let gr = extract_graph(g)?;
    // br-r37-c1-djohp: see clustering rationale.
    require_not_multigraph(&gr)?;
    // br-r37-c1-djohp: nx computes ``sum(c) / len(c)`` which raises
    // ZeroDivisionError on the empty-graph case; mirror that contract
    // so direct callers can't paper over an empty input.
    if gr.node_count_original() == 0 {
        return Err(pyo3::exceptions::PyZeroDivisionError::new_err(
            "division by zero",
        ));
    }
    let result = if gr.is_directed() {
        let dg = gr.digraph().expect("is_directed checked");
        py.allow_threads(|| fnx_algorithms::clustering_coefficient_directed(dg))
    } else {
        let inner = gr.undirected();
        py.allow_threads(|| fnx_algorithms::clustering_coefficient(inner))
    };
    Ok(result.average_clustering)
}

/// Return the transitivity (global clustering coefficient).
#[pyfunction]
pub fn transitivity(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<f64> {
    let gr = extract_graph(g)?;
    // br-r37-c1-p7p7l: previously this called gr.undirected() unconditionally
    // on directed input, silently returning the undirected-projection
    // transitivity (e.g. 1.0 on cycle3 when nx.transitivity returns 0). nx
    // computes directed transitivity by counting u→v→w→u patterns; the
    // Rust impl here only knows undirected triangles. Sister functions
    // (triangles, clustering, square_clustering) already guard with
    // require_undirected; mirror that contract here so direct _fnx callers
    // get a clear NetworkXNotImplemented instead of a silently wrong value.
    // The Python wrapper at python/franken_networkx/__init__.py:26142
    // already routes directed inputs through a native triangle-iter path,
    // so end users of fnx.transitivity are unaffected.
    require_undirected(&gr, "transitivity")?;
    // br-r37-c1-djohp: also reject multigraph (sister kernels do too).
    require_not_multigraph(&gr)?;
    let inner = gr.undirected();
    Ok(py.allow_threads(|| fnx_algorithms::clustering_coefficient(inner).transitivity))
}

/// Return the number of triangles for each node.
#[pyfunction]
pub fn triangles(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<Py<PyDict>> {
    let gr = extract_graph(g)?;
    require_undirected(&gr, "triangles")?;
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

/// br-r37-c1-niit0: native integer-CSR counts for Robins & Alexander bipartite
/// clustering. Returns `(c4_numer, l3_numer)` where networkx's `_four_cycles`
/// returns `c4_numer / 4` and `_threepaths` returns `l3_numer / 2`; the Python
/// wrapper performs the SAME float arithmetic
/// (`(4.0 * (c4_numer / 4)) / (l3_numer / 2)`) so the result is byte-identical.
/// Both counts are graph invariants (order-independent integer sums), so no
/// node-order matching is required. Returns `None` for directed / multigraph
/// graphs (the Python wrapper then delegates to networkx).
#[pyfunction]
pub fn robins_alexander_counts(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
) -> PyResult<Option<(u128, u128)>> {
    let gr = extract_graph(g)?;
    let GraphRef::Undirected(pg) = &gr else {
        return Ok(None);
    };
    let inner = &pg.inner;
    let n = inner.node_count();
    let counts = py.allow_threads(|| {
        // _four_cycles: cycles = sum over v, over second-order neighbours x (not
        // already `seen`), of p2*(p2-1) where p2 = |N(v) ∩ N(x)|.
        let mut cycles: u128 = 0;
        let mut seen = vec![false; n];
        let mut in_nv = vec![false; n]; // marks N(v) for the intersection count
        let mut in_two_hop = vec![false; n];
        let mut two_hop: Vec<usize> = Vec::new();
        for v in 0..n {
            seen[v] = true;
            let Some(nv) = inner.neighbors_indices(v) else {
                continue;
            };
            if nv.len() < 2 {
                continue;
            }
            for &u in nv {
                in_nv[u] = true;
            }
            two_hop.clear();
            for &u in nv {
                if let Some(nu) = inner.neighbors_indices(u) {
                    for &x in nu {
                        if !seen[x] && !in_two_hop[x] {
                            in_two_hop[x] = true;
                            two_hop.push(x);
                        }
                    }
                }
            }
            for &x in &two_hop {
                in_two_hop[x] = false;
                let mut p2: u128 = 0;
                if let Some(nx) = inner.neighbors_indices(x) {
                    for &y in nx {
                        if in_nv[y] {
                            p2 += 1;
                        }
                    }
                }
                if p2 > 1 {
                    cycles += p2 * (p2 - 1);
                }
            }
            for &u in nv {
                in_nv[u] = false;
            }
        }

        // _threepaths: paths = sum over v, u∈N(v), w∈N(u)\{v} of |N(w) \ {v,u}|.
        // For a simple undirected graph |N(w)\{v,u}| = deg(w) - [v∈N(w)] -
        // [u∈N(w)]; since w∈N(u) the edge (u,w) exists so u∈N(w) ALWAYS, and
        // v∈N(w) ⟺ w∈N(v).
        let mut paths: u128 = 0;
        let mut in_nv2 = vec![false; n]; // marks N(v): w∈N(v) ⟺ v∈N(w)
        for v in 0..n {
            let Some(nv) = inner.neighbors_indices(v) else {
                continue;
            };
            for &w in nv {
                in_nv2[w] = true;
            }
            for &u in nv {
                if let Some(nu) = inner.neighbors_indices(u) {
                    for &w in nu {
                        if w == v {
                            continue;
                        }
                        let degw = inner.neighbors_indices(w).map_or(0, |s| s.len());
                        // deg(w) - 1 (drop u, always present) - (v present ? 1 : 0)
                        let mut cnt = degw as i128 - 1;
                        if in_nv2[w] {
                            cnt -= 1;
                        }
                        if cnt > 0 {
                            paths += cnt as u128;
                        }
                    }
                }
            }
            for &w in nv {
                in_nv2[w] = false;
            }
        }
        (cycles, paths)
    });
    Ok(Some(counts))
}

/// Return all maximal cliques as a list of lists.
#[pyfunction]
pub fn find_cliques(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<Vec<Vec<PyObject>>> {
    let gr = extract_graph(g)?;
    // br-r37-c1-ewpss: kernel previously collapsed directed input via
    // ``gr.undirected()`` and silently returned cliques on the
    // underlying undirected projection. nx and the public wrapper both
    // reject directed input; mirror the find_cliques_adjacency_sets
    // contract so direct callers of `_raw_find_cliques` see the same
    // NetworkXNotImplemented error.
    require_undirected(&gr, "find_cliques")?;
    let inner = gr.undirected();
    let result = py.allow_threads(|| fnx_algorithms::find_cliques(inner));
    Ok(result
        .cliques
        .iter()
        .map(|clique| clique.iter().map(|n| gr.py_node_key(py, n)).collect())
        .collect())
}

/// Return `{node: set(neighbors)}` for the simple Graph `find_cliques` fast path.
#[pyfunction]
pub fn find_cliques_adjacency_sets(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<Py<PyDict>> {
    let gr = extract_graph(g)?;
    let GraphRef::Undirected(pg) = gr else {
        return Err(NetworkXNotImplemented::new_err(
            "not implemented for directed type",
        ));
    };

    let adjacency = PyDict::new(py);
    for node in pg.inner.nodes_ordered() {
        let py_node = pg.py_node_key(py, node);
        let py_neighbors: Vec<PyObject> = pg
            .inner
            .neighbors(node)
            .unwrap_or_default()
            .into_iter()
            .filter(|neighbor| *neighbor != node)
            .map(|neighbor| pg.py_node_key(py, neighbor))
            .collect();
        let neighbor_set = pyo3::types::PySet::new(py, py_neighbors.iter())?;
        adjacency.set_item(py_node, neighbor_set)?;
    }
    Ok(adjacency.unbind())
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
pub fn maximal_matching(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<Py<pyo3::types::PySet>> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    let result = py.allow_threads(|| fnx_algorithms::maximal_matching(inner));
    let set = pyo3::types::PySet::empty(py)?;
    for (u, v) in result.matching {
        let py_u = gr.py_node_key(py, &u);
        let py_v = gr.py_node_key(py, &v);
        let tuple = pyo3::types::PyTuple::new(py, &[py_u, py_v])?;
        set.add(tuple)?;
    }
    Ok(set.unbind())
}

/// Return a max-weight matching as a set of edge tuples.
#[pyfunction]
#[pyo3(signature = (g, maxcardinality=false, weight="weight"))]
pub fn max_weight_matching(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    maxcardinality: bool,
    weight: &str,
) -> PyResult<Py<pyo3::types::PySet>> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    let w = weight.to_owned();
    let result =
        py.allow_threads(move || fnx_algorithms::max_weight_matching(inner, maxcardinality, &w));

    let set = pyo3::types::PySet::empty(py)?;
    for (u, v) in result.matching {
        let py_u = gr.py_node_key(py, &u);
        let py_v = gr.py_node_key(py, &v);
        let tuple = pyo3::types::PyTuple::new(py, &[py_u, py_v])?;
        set.add(tuple)?;
    }
    Ok(set.unbind())
}

/// Return a min-weight matching as a set of edge tuples.
#[pyfunction]
#[pyo3(signature = (g, weight="weight"))]
pub fn min_weight_matching(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    weight: &str,
) -> PyResult<Py<pyo3::types::PySet>> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    let w = weight.to_owned();
    let result = py.allow_threads(move || fnx_algorithms::min_weight_matching(inner, &w));

    let set = pyo3::types::PySet::empty(py)?;
    for (u, v) in result.matching {
        let py_u = gr.py_node_key(py, &u);
        let py_v = gr.py_node_key(py, &v);
        let tuple = pyo3::types::PyTuple::new(py, &[py_u, py_v])?;
        set.add(tuple)?;
    }
    Ok(set.unbind())
}

/// Return a minimum edge cover as a set of edge tuples.
#[pyfunction]
pub fn min_edge_cover(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<Py<pyo3::types::PySet>> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    let result = py.allow_threads(|| fnx_algorithms::min_edge_cover(inner));
    match result {
        Some(r) => {
            let set = pyo3::types::PySet::empty(py)?;
            for (u, v) in r.edges {
                let py_u = gr.py_node_key(py, &u);
                let py_v = gr.py_node_key(py, &v);
                let tuple = pyo3::types::PyTuple::new(py, &[py_u, py_v])?;
                set.add(tuple)?;
            }
            Ok(set.unbind())
        }
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
                let inner = gr.digraph().expect("is_directed checked above");
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
                let inner = gr.digraph().expect("is_directed checked above");
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
                let inner = gr.digraph().expect("is_directed checked above");
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
                let inner = gr.digraph().expect("is_directed checked above");
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

/// Compute minimum cost flow on a directed graph.
///
/// Nodes must have demand attributes following NetworkX convention:
/// - negative = supply (node produces flow)
/// - positive = demand (node consumes flow)
///
/// Edges must have capacity and weight (cost) attributes.
/// Returns (flow_dict, total_cost) where flow_dict maps (u, v) -> flow value.
///
/// Matches `networkx.min_cost_flow`.
#[pyfunction]
#[pyo3(signature = (g, demand="demand", capacity="capacity", weight="weight"))]
pub fn min_cost_flow(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    demand: &str,
    capacity: &str,
    weight: &str,
) -> PyResult<(PyObject, f64)> {
    let gr = extract_graph(g)?;
    let demand_attr = demand.to_owned();
    let capacity_attr = capacity.to_owned();
    let weight_attr = weight.to_owned();

    let result = if let Some(dg) = gr.digraph() {
        py.allow_threads(move || {
            fnx_algorithms::min_cost_flow(dg, &demand_attr, &capacity_attr, &weight_attr)
        })
    } else {
        return Err(NetworkXNotImplemented::new_err(
            "min_cost_flow requires a directed graph",
        ));
    };

    match result {
        Some(r) => {
            let dict = PyDict::new(py);
            for ((u, v), flow) in &r.flow {
                let key = (gr.py_node_key(py, u), gr.py_node_key(py, v));
                dict.set_item(key, flow)?;
            }
            Ok((dict.into_any().unbind(), r.cost))
        }
        None => Err(NetworkXUnfeasible::new_err(
            "No feasible flow satisfying the demands",
        )),
    }
}

/// Compute only the cost of the minimum cost flow (not the full flow dict).
#[pyfunction]
#[pyo3(signature = (g, demand="demand", capacity="capacity", weight="weight"))]
pub fn min_cost_flow_cost(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    demand: &str,
    capacity: &str,
    weight: &str,
) -> PyResult<f64> {
    let gr = extract_graph(g)?;
    let demand_attr = demand.to_owned();
    let capacity_attr = capacity.to_owned();
    let weight_attr = weight.to_owned();

    let result = if let Some(dg) = gr.digraph() {
        py.allow_threads(move || {
            fnx_algorithms::min_cost_flow(dg, &demand_attr, &capacity_attr, &weight_attr)
        })
    } else {
        return Err(NetworkXNotImplemented::new_err(
            "min_cost_flow_cost requires a directed graph",
        ));
    };

    match result {
        Some(r) => Ok(r.cost),
        None => Err(NetworkXUnfeasible::new_err(
            "No feasible flow satisfying the demands",
        )),
    }
}

// ===========================================================================
// Distance measures
// ===========================================================================

/// Return the eccentricity of each node as a dict.
#[pyfunction]
pub fn eccentricity(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<Py<PyDict>> {
    let gr = extract_graph(g)?;
    // br-r37-c1-t8055: this kernel collapses directed input via
    // ``gr.undirected()``, producing wrong eccentricity values for
    // weakly-but-not-strongly-connected DiGraphs (e.g. a directed
    // chain). The public wrapper at
    // python/franken_networkx/__init__.py:eccentricity (br-eccdir)
    // already routes directed graphs through a directed-aware path
    // and only calls this kernel on undirected input. Match the
    // sister-function contract (diameter/radius/center/periphery
    // require_undirected) so direct callers of `_raw_eccentricity`
    // see the same nx-shaped error rather than silently-wrong data.
    require_undirected(&gr, "eccentricity")?;
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
    // br-r37-c1-0xhhq: previously gr.undirected() collapsed antiparallel
    // edges and returned a wrong value on directed input. Sister
    // functions (transitivity, triangles, clustering, square_clustering)
    // already guard with require_undirected; mirror that contract here.
    // Public-API users are routed through the directed-aware
    // fnx.eccentricity path in the Python wrapper (br-r37-c1-wojl3).
    require_undirected(&gr, "diameter")?;
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
    // br-r37-c1-0xhhq: same directed-collapse defect as diameter.
    require_undirected(&gr, "radius")?;
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
    // br-r37-c1-0xhhq: same directed-collapse defect.
    require_undirected(&gr, "center")?;
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
    // br-r37-c1-0xhhq: same directed-collapse defect.
    require_undirected(&gr, "periphery")?;
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
    // br-r37-c1-djohp: nx rejects multigraph (parallel edges break the
    // bucket-based k-core decomposition); mirror that contract.
    require_not_multigraph(&gr)?;
    let inner = gr.undirected();
    // br-r37-c1-ftorb: nx also rejects self-loops because the bucket
    // decomposition double-counts loops in the degree, producing wrong
    // core numbers. nx raises NetworkXNotImplemented with a remediation
    // hint; mirror it.
    for node in inner.nodes_ordered() {
        if let Some(neighbors) = inner.neighbors(node)
            && neighbors.contains(&node)
        {
            return Err(crate::NetworkXNotImplemented::new_err(
                "Input graph has self loops which is not permitted; \
                 Consider using G.remove_edges_from(nx.selfloop_edges(G)).",
            ));
        }
    }
    let result = py.allow_threads(|| fnx_algorithms::core_number(inner));
    let dict = PyDict::new(py);
    for nc in &result.core_numbers {
        dict.set_item(gr.py_node_key(py, &nc.node), nc.core)?;
    }
    Ok(dict.unbind())
}

/// Return the k-core subgraph.
/// If k is None, returns the main core (largest k-core).
#[pyfunction]
#[pyo3(signature = (g, k=None))]
pub fn k_core_rust(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    k: Option<usize>,
) -> PyResult<Py<PyGraph>> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    let runtime_policy = inner.runtime_policy().clone();
    let result = py.allow_threads(|| fnx_algorithms::k_core(inner, k));

    let mut new_graph = PyGraph::new_empty_with_policy(py, runtime_policy.clone())?;
    for node in &result.nodes {
        new_graph.inner.add_node(node.clone());
        new_graph
            .node_key_map
            .insert(node.clone(), gr.py_node_key(py, node));
    }
    for (u, v) in &result.edges {
        let _ = new_graph.inner.add_edge(u.clone(), v.clone());
    }
    new_graph.inner.set_runtime_policy(runtime_policy);
    Py::new(py, new_graph)
}

/// Return the k-shell subgraph.
/// The k-shell is the subgraph induced by nodes with core number exactly k.
/// If k is None, returns the outer shell (max core number).
#[pyfunction]
#[pyo3(signature = (g, k=None))]
pub fn k_shell_rust(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    k: Option<usize>,
) -> PyResult<Py<PyGraph>> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    let runtime_policy = inner.runtime_policy().clone();
    let result = py.allow_threads(|| fnx_algorithms::k_shell(inner, k));

    let mut new_graph = PyGraph::new_empty_with_policy(py, runtime_policy.clone())?;
    for node in &result.nodes {
        new_graph.inner.add_node(node.clone());
        new_graph
            .node_key_map
            .insert(node.clone(), gr.py_node_key(py, node));
    }
    for (u, v) in &result.edges {
        let _ = new_graph.inner.add_edge(u.clone(), v.clone());
    }
    new_graph.inner.set_runtime_policy(runtime_policy);
    Py::new(py, new_graph)
}

/// Return the k-crust subgraph.
/// The k-crust is the subgraph induced by nodes with core number <= k.
/// If k is None, uses max_core - 1 as the default.
#[pyfunction]
#[pyo3(signature = (g, k=None))]
pub fn k_crust_rust(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    k: Option<usize>,
) -> PyResult<Py<PyGraph>> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    let runtime_policy = inner.runtime_policy().clone();
    let result = py.allow_threads(|| fnx_algorithms::k_crust(inner, k));

    let mut new_graph = PyGraph::new_empty_with_policy(py, runtime_policy.clone())?;
    for node in &result.nodes {
        new_graph.inner.add_node(node.clone());
        new_graph
            .node_key_map
            .insert(node.clone(), gr.py_node_key(py, node));
    }
    for (u, v) in &result.edges {
        let _ = new_graph.inner.add_edge(u.clone(), v.clone());
    }
    new_graph.inner.set_runtime_policy(runtime_policy);
    Py::new(py, new_graph)
}

/// Return the k-corona subgraph.
/// The k-corona is the subgraph of nodes in the k-core which have
/// exactly k neighbors in the k-core.
#[pyfunction]
pub fn k_corona_rust(py: Python<'_>, g: &Bound<'_, PyAny>, k: usize) -> PyResult<Py<PyGraph>> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    let runtime_policy = inner.runtime_policy().clone();
    let result = py.allow_threads(|| fnx_algorithms::k_corona(inner, k));

    let mut new_graph = PyGraph::new_empty_with_policy(py, runtime_policy.clone())?;
    for node in &result.nodes {
        new_graph.inner.add_node(node.clone());
        new_graph
            .node_key_map
            .insert(node.clone(), gr.py_node_key(py, node));
    }
    for (u, v) in &result.edges {
        let _ = new_graph.inner.add_edge(u.clone(), v.clone());
    }
    new_graph.inner.set_runtime_policy(runtime_policy);
    Py::new(py, new_graph)
}

/// Reconstruct labeled tree from Prüfer sequence.
#[pyfunction]
pub fn from_prufer_sequence_rust(py: Python<'_>, sequence: Vec<usize>) -> PyResult<PyObject> {
    // br-r37-c1-zs68s defense-in-depth: the Python wrapper validates
    // upstream, but if the Rust function is called with an out-of-range
    // value, return a typed NetworkXError rather than letting a Rust
    // panic leak through PyO3 as a PanicException.
    let result = py
        .allow_threads(|| fnx_algorithms::from_prufer_sequence(&sequence))
        .map_err(NetworkXError::new_err)?;
    let edges = PyList::new(
        py,
        result.edges.iter().map(|(u, v)| {
            PyTuple::new(
                py,
                [
                    u.into_pyobject(py)
                        .expect("is_directed checked above")
                        .into_any(),
                    v.into_pyobject(py)
                        .expect("is_directed checked above")
                        .into_any(),
                ],
            )
            .expect("is_directed checked above")
            .into_any()
        }),
    )?;
    Ok(edges.into_any().unbind())
}

/// Extract Prüfer sequence from labeled tree.
#[pyfunction]
pub fn to_prufer_sequence_rust(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<Vec<usize>> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    if inner.node_count() < 2 {
        return Err(crate::NetworkXPointlessConcept::new_err(
            "Prüfer sequence undefined for trees with fewer than two nodes",
        ));
    }
    if !py.allow_threads(|| fnx_algorithms::is_tree(inner).is_tree) {
        return Err(crate::NotATree::new_err("provided graph is not a tree"));
    }
    py.allow_threads(|| fnx_algorithms::to_prufer_sequence(inner))
        .map_err(PyKeyError::new_err)
}

/// Onion layer decomposition (generalized k-core peeling).
#[pyfunction]
pub fn onion_layers_rust(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<Py<PyDict>> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    let result = py.allow_threads(|| fnx_algorithms::onion_layers(inner));
    let dict = PyDict::new(py);
    for nl in &result.layers {
        dict.set_item(gr.py_node_key(py, &nl.node), nl.layer)?;
    }
    Ok(dict.unbind())
}

/// Return the k-truss subgraph.
#[pyfunction]
pub fn k_truss_rust(py: Python<'_>, g: &Bound<'_, PyAny>, k: usize) -> PyResult<Py<PyDict>> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    let result = py.allow_threads(|| fnx_algorithms::k_truss(inner, k));
    let dict = PyDict::new(py);
    let nodes = PyList::new(py, result.nodes.iter().map(|n| gr.py_node_key(py, n)))?;
    let edges = PyList::new(
        py,
        result.edges.iter().map(|(u, v)| {
            PyTuple::new(py, [gr.py_node_key(py, u), gr.py_node_key(py, v)])
                .expect("is_directed checked above")
                .into_any()
        }),
    )?;
    dict.set_item("nodes", nodes)?;
    dict.set_item("edges", edges)?;
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
    // br-r37-c1-7dpyg: fresh ledger, mode only — the old triple
    // runtime-policy clone (clone + clone-into-ctor + set) copied the
    // source's unbounded decision ledger and made MST 2.45x slower on
    // ctor-built sources with identical structure.
    let tree_mode = inner.mode();
    let w = weight.to_owned();
    let result = py.allow_threads(move || fnx_algorithms::minimum_spanning_tree(inner, &w));
    let mut new_graph = PyGraph::new_empty_with_mode(py, tree_mode)?;

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

/// br-r37-c1-approxacc: byte-exact native
/// ``approximation.average_clustering(G, trials, seed)`` for an integer seed.
/// The kernel reproduces nx's CPython ``random.Random(seed)`` draw sequence
/// (node indices via ``random()``, neighbour pairs via ``sample``) over
/// ``neighbors_indices``. The Python wrapper gates eligibility (simple Graph,
/// non-negative int seed, trials >= 1, |V| >= 1).
#[pyfunction]
#[pyo3(signature = (g, trials, seed))]
pub fn approx_average_clustering(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    trials: usize,
    seed: u64,
) -> PyResult<f64> {
    let gr = extract_graph(g)?;
    require_undirected(&gr, "approx_average_clustering")?;
    let inner = gr.undirected();
    Ok(py.allow_threads(|| fnx_algorithms::approx_average_clustering(inner, trials, seed)))
}

/// br-r37-c1-bngez: byte-exact bipartite Hopcroft-Karp maximum matching,
/// returning the result dict (node -> matched partner). ``left`` / ``right`` are
/// the node indices of the two bipartite sets in nx's ``bipartite_sets``
/// iteration order (CPython set order, computed in Python). The native kernel
/// runs the BFS/DFS matching over ``neighbors_indices``; the dict is built in
/// nx's order (matched left nodes in ``left`` order, then matched right nodes in
/// ``right`` order), each node object resolved once.
#[pyfunction]
#[pyo3(signature = (g, left, right))]
pub fn bipartite_hopcroft_karp_matching(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    left: Vec<usize>,
    right: Vec<usize>,
) -> PyResult<pyo3::Py<PyDict>> {
    let gr = extract_graph(g)?;
    require_undirected(&gr, "bipartite_hopcroft_karp_matching")?;
    let inner = gr.undirected();
    let pairs = py.allow_threads(|| fnx_algorithms::bipartite_hopcroft_karp(inner, &left, &right));
    let names = inner.nodes_ordered();
    let mut cache: Vec<Option<PyObject>> = (0..names.len()).map(|_| None).collect();
    let dict = PyDict::new(py);
    for (a, b) in pairs {
        if cache[a].is_none() {
            cache[a] = Some(gr.py_node_key(py, names[a]));
        }
        if cache[b].is_none() {
            cache[b] = Some(gr.py_node_key(py, names[b]));
        }
        dict.set_item(
            cache[a].as_ref().expect("cached").clone_ref(py),
            cache[b].as_ref().expect("cached").clone_ref(py),
        )?;
    }
    Ok(dict.unbind())
}

/// br-r37-c1-primidx: byte-exact Prim MST edges as (u, v) node-object pairs.
/// ``start_order`` is the CPython ``set(G).pop()`` sequence (node indices),
/// computed in Python because it depends on CPython set iteration order that
/// can't be reproduced in safe Rust. Returns ``None`` when a NaN weight is hit
/// with ``ignore_nan = false`` so the Python wrapper delegates to nx for the
/// exact ``ValueError``.
#[pyfunction]
#[pyo3(signature = (g, weight, minimum, start_order, ignore_nan))]
pub fn prim_spanning_edges(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    weight: &str,
    minimum: bool,
    start_order: Vec<usize>,
    ignore_nan: bool,
) -> PyResult<Option<Vec<(PyObject, PyObject)>>> {
    let gr = extract_graph(g)?;
    require_undirected(&gr, "prim_spanning_edges")?;
    let inner = gr.undirected();
    let w = weight.to_owned();
    let result = py.allow_threads(move || {
        fnx_algorithms::prim_spanning_edges_indexed(inner, &w, minimum, &start_order, ignore_nan)
    });
    match result {
        None => Ok(None),
        Some(edges) => {
            let names = inner.nodes_ordered();
            let mut cache: Vec<Option<PyObject>> = (0..names.len()).map(|_| None).collect();
            let mut out: Vec<(PyObject, PyObject)> = Vec::with_capacity(edges.len());
            for (u, v) in edges {
                if cache[u].is_none() {
                    cache[u] = Some(gr.py_node_key(py, names[u]));
                }
                if cache[v].is_none() {
                    cache[v] = Some(gr.py_node_key(py, names[v]));
                }
                out.push((
                    cache[u].as_ref().expect("cached").clone_ref(py),
                    cache[v].as_ref().expect("cached").clone_ref(py),
                ));
            }
            Ok(Some(out))
        }
    }
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
    require_undirected(&gr, "spanning_edges")?;
    let w = weight.to_owned();
    // br-r37-c1-mstcsr: ignore_nan must DROP NaN-weighted edges, which only the
    // sanitized copy does; the common (ignore_nan=false) path just validates and
    // runs the kernel directly on the original graph — no copy.
    let result = if ignore_nan {
        let input = spanning_input_graph(py, &gr, weight, ignore_nan)?;
        py.allow_threads(move || fnx_algorithms::minimum_spanning_tree(&input, &w))
    } else {
        validate_spanning_no_nan(py, &gr, weight)?;
        let inner = gr.undirected();
        fnx_algorithms::minimum_spanning_tree(inner, &w)
    };
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
    // br-r37-c1-mstmaxnative: mirror minimum_spanning_tree — a fresh
    // mode-only policy. The old triple runtime-policy clone (clone +
    // new_empty_with_policy + set_runtime_policy) deep-copied the source's
    // unbounded decision ledger and was ~2x slower (reference_runtime_policy_clone_tax).
    let tree_mode = inner.mode();
    let w = weight.to_owned();
    let result = py.allow_threads(move || fnx_algorithms::maximum_spanning_tree(inner, &w));
    let mut new_graph = PyGraph::new_empty_with_mode(py, tree_mode)?;

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
                if gr
                    .digraph()
                    .expect("is_directed checked above")
                    .node_count()
                    == 0
                {
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
                if !gr
                    .digraph()
                    .expect("is_directed checked above")
                    .has_node(&canonical_root)
                {
                    return Err(NetworkXError::new_err(
                        "The node root is not in the graph G.",
                    ));
                }
                let inner = gr.digraph().expect("is_directed checked above");
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
    if gr.is_multigraph() {
        return Err(crate::NetworkXNotImplemented::new_err(
            "not implemented for multigraph type",
        ));
    }
    let GraphRef::Undirected(pg) = &gr else {
        return Err(pyo3::exceptions::PyValueError::new_err(
            "require_undirected and is_multigraph should reject all other types",
        ));
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
    if gr.is_multigraph() {
        return Err(crate::NetworkXNotImplemented::new_err(
            "not implemented for multigraph type",
        ));
    }
    let GraphRef::Undirected(pg) = &gr else {
        return Err(pyo3::exceptions::PyValueError::new_err(
            "require_undirected and is_multigraph should reject all other types",
        ));
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
    let gr = extract_graph(g)?;
    if let GraphRef::Directed { dg, .. } = &gr {
        if dg.inner.node_count() == 0 {
            return Err(crate::NetworkXPointlessConcept::new_err("G has no nodes."));
        }
        let inner = &dg.inner;
        let attr_name = attr.to_owned();
        let (included_edges, excluded_edges) = match partition {
            Some(partition_attr) => extract_edge_partition_from_attr(py, dg, partition_attr)?,
            None => (Vec::new(), Vec::new()),
        };
        let result = py.allow_threads(move || {
            if included_edges.is_empty() && excluded_edges.is_empty() {
                fnx_algorithms::maximum_spanning_arborescence(inner, &attr_name, default)
            } else {
                fnx_algorithms::maximum_spanning_arborescence_with_edge_partition(
                    inner,
                    &attr_name,
                    default,
                    &included_edges,
                    &excluded_edges,
                )
            }
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
    let gr = extract_graph(g)?;
    if let GraphRef::Directed { dg, .. } = &gr {
        if dg.inner.node_count() == 0 {
            return Err(crate::NetworkXPointlessConcept::new_err("G has no nodes."));
        }
        let inner = &dg.inner;
        let attr_name = attr.to_owned();
        let (included_edges, excluded_edges) = match partition {
            Some(partition_attr) => extract_edge_partition_from_attr(py, dg, partition_attr)?,
            None => (Vec::new(), Vec::new()),
        };
        let result = py.allow_threads(move || {
            if included_edges.is_empty() && excluded_edges.is_empty() {
                fnx_algorithms::minimum_spanning_arborescence(inner, &attr_name, default)
            } else {
                fnx_algorithms::minimum_spanning_arborescence_with_edge_partition(
                    inner,
                    &attr_name,
                    default,
                    &included_edges,
                    &excluded_edges,
                )
            }
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
    if gr.node_count_original() == 0 {
        return Err(crate::NetworkXPointlessConcept::new_err(
            "Connectivity is undefined for the null graph.",
        ));
    }
    if gr.is_directed() {
        // NetworkX directed contract: every node has in-degree equal to
        // out-degree AND the graph is strongly connected. The previous
        // implementation collapsed to undirected and checked degree
        // parity, which silently accepted directed acyclic tournaments
        // like 0->1, 1->2, 0->2 (each undirected degree is 2 → even,
        // so the undirected K3 check passed) even though those are not
        // Eulerian.
        if gr.is_multigraph() {
            // For MultiDiGraph, parallel edges affect in/out-degree; ask
            // Python's degree views so parallel-edge counting matches NX.
            let nodes_method = g.call_method0("nodes")?;
            let nodes: Vec<Bound<'_, PyAny>> =
                nodes_method.try_iter()?.collect::<PyResult<Vec<_>>>()?;
            let in_deg_view = g.getattr("in_degree")?;
            let out_deg_view = g.getattr("out_degree")?;
            for node in &nodes {
                let in_d: usize = in_deg_view.get_item(node)?.extract()?;
                let out_d: usize = out_deg_view.get_item(node)?.extract()?;
                if in_d != out_d {
                    return Ok(false);
                }
            }
        } else {
            // br-r37-c1-euleridx: O(1)/node integer in/out-degree (slice lengths)
            // instead of dg.in_degree(name)/out_degree(name), which resolve a
            // String key (and the in-degree path can scan edges). nx short-circuits
            // on the first in!=out node, so this matters most for the common
            // not-Eulerian case (returns before the strongly-connected check).
            let dg = gr.digraph().expect("is_directed checked above");
            for i in 0..dg.node_count() {
                let out_d = dg.successors_indices(i).map_or(0, <[usize]>::len);
                let in_d = dg.predecessors_indices(i).map_or(0, <[usize]>::len);
                if in_d != out_d {
                    return Ok(false);
                }
            }
        }
        let dg = gr.digraph().expect("is_directed checked above");
        return Ok(py.allow_threads(|| fnx_algorithms::is_strongly_connected(dg)));
    }
    let inner = gr.undirected();
    // For multigraphs, the simple-graph conversion collapses parallel edges
    // which changes degree parity. Check multigraph degree directly via Python.
    if gr.is_multigraph() {
        if inner.node_count() > 1 && inner.nodes_ordered().iter().any(|n| inner.degree(n) == 0) {
            return Ok(false);
        }
        let nodes_method = g.call_method0("nodes")?;
        let nodes: Vec<Bound<'_, PyAny>> =
            nodes_method.try_iter()?.collect::<PyResult<Vec<_>>>()?;
        let degree_view = g.getattr("degree")?;
        for node in &nodes {
            let deg: usize = degree_view.get_item(node)?.extract()?;
            if !deg.is_multiple_of(2) {
                return Ok(false);
            }
        }
        // Also check connectivity via the simple graph.
        return Ok(py.allow_threads(|| fnx_algorithms::is_connected(inner).is_connected));
    }
    for idx in 0..inner.node_count() {
        let row_degree = inner.neighbors_indices(idx).map_or(0, <[usize]>::len);
        let self_loop_extra = usize::from(inner.edge_attrs_by_indices(idx, idx).is_some());
        if !(row_degree + self_loop_extra).is_multiple_of(2) {
            return Ok(false);
        }
    }
    Ok(py.allow_threads(|| fnx_algorithms::is_connected(inner).is_connected))
}

/// Return True if the graph has an Eulerian path.
#[pyfunction]
pub fn has_eulerian_path(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<bool> {
    let gr = extract_graph(g)?;
    if gr.node_count_original() == 0 {
        return Err(crate::NetworkXPointlessConcept::new_err(
            "Connectivity is undefined for the null graph.",
        ));
    }
    if gr.is_directed() {
        // br-r37-c1-eulerpathdir: native directed has-Eulerian-path. nx's exact
        // contract: if is_eulerian (all in==out AND strongly connected) -> True;
        // else at most one node with in-out==1, at most one with out-in==1, every
        // other node balanced, AND weakly connected. Integer O(1) in/out-degree
        // (in_degree_by_index/out_degree_by_index) + early exit on |in-out| > 1 ==
        // nx's short-circuit, so random (non-path) digraphs return without the
        // strongly/weakly-connected walk. The previous code raised here and the
        // wrapper paid a full fnx->nx conversion (~20ms / 3600 edges, 2714x).
        // MultiDiGraph parallel-edge degrees stay on the Python/nx path.
        let GraphRef::Directed { dg, .. } = &gr else {
            return Err(crate::NetworkXNotImplemented::new_err(
                "not implemented for multidigraph type",
            ));
        };
        let dg = &dg.inner;
        let n = dg.node_count();
        let all_balanced = (0..n).all(|i| dg.in_degree_by_index(i) == dg.out_degree_by_index(i));
        if all_balanced && py.allow_threads(|| fnx_algorithms::is_strongly_connected(dg)) {
            return Ok(true); // is_eulerian -> has an Eulerian path
        }
        let mut unbalanced_ins = 0usize;
        let mut unbalanced_outs = 0usize;
        for i in 0..n {
            let ind = dg.in_degree_by_index(i);
            let outd = dg.out_degree_by_index(i);
            if ind == outd + 1 {
                unbalanced_ins += 1;
            } else if outd == ind + 1 {
                unbalanced_outs += 1;
            } else if ind != outd {
                return Ok(false);
            }
        }
        return Ok(unbalanced_ins <= 1
            && unbalanced_outs <= 1
            && py.allow_threads(|| fnx_algorithms::is_weakly_connected(dg)));
    }
    let inner = gr.undirected();
    if inner.node_count() > 1 && inner.nodes_ordered().iter().any(|n| inner.degree(n) == 0) {
        return Ok(false);
    }
    if gr.is_multigraph() {
        let nodes_method = g.call_method0("nodes")?;
        let nodes: Vec<Bound<'_, PyAny>> =
            nodes_method.try_iter()?.collect::<PyResult<Vec<_>>>()?;
        let degree_view = g.getattr("degree")?;
        let mut odd_count = 0usize;
        for node in &nodes {
            let deg: usize = degree_view.get_item(node)?.extract()?;
            if !deg.is_multiple_of(2) {
                odd_count += 1;
            }
        }
        if odd_count != 0 && odd_count != 2 {
            return Ok(false);
        }
        return Ok(py.allow_threads(|| fnx_algorithms::is_connected(inner).is_connected));
    }
    Ok(py.allow_threads(|| fnx_algorithms::has_eulerian_path(inner).has_eulerian_path))
}

/// Return True if the graph is semi-Eulerian.
#[pyfunction]
pub fn is_semieulerian(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<bool> {
    let gr = extract_graph(g)?;
    if gr.node_count_original() == 0 {
        return Err(crate::NetworkXPointlessConcept::new_err(
            "Connectivity is undefined for the null graph.",
        ));
    }
    let has_path = has_eulerian_path(py, g)?;
    if !has_path {
        return Ok(false);
    }
    let is_circuit = is_eulerian(py, g)?;
    Ok(!is_circuit)
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
    if gr.node_count_original() == 0 {
        return Err(crate::NetworkXPointlessConcept::new_err(
            "Connectivity is undefined for the null graph.",
        ));
    }
    let src = source.map(|s| node_key_to_string(py, s)).transpose()?;
    if let (Some(src_key), Some(src_obj)) = (&src, source) {
        validate_node(&gr, src_key, src_obj, "Source")?;
    }
    let inner = gr.undirected();
    if inner.node_count() > 1 && inner.nodes_ordered().iter().any(|n| inner.degree(n) == 0) {
        return Err(NetworkXError::new_err("G is not Eulerian."));
    }
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
    if gr.node_count_original() == 0 {
        return Err(crate::NetworkXPointlessConcept::new_err(
            "Connectivity is undefined for the null graph.",
        ));
    }
    let src = source.map(|s| node_key_to_string(py, s)).transpose()?;
    if let (Some(src_key), Some(src_obj)) = (&src, source) {
        validate_node(&gr, src_key, src_obj, "Source")?;
    }
    if gr.is_directed() {
        if gr.is_multigraph() {
            return Err(crate::NetworkXNotImplemented::new_err(
                "not implemented for multigraph type",
            ));
        }
        let dg = gr.digraph().expect("is_directed checked above");
        let result =
            py.allow_threads(|| fnx_algorithms::eulerian_path_directed(dg, src.as_deref()));
        return match result {
            Some(r) => Ok(r
                .edges
                .iter()
                .map(|(u, v)| (gr.py_node_key(py, u), gr.py_node_key(py, v)))
                .collect()),
            None => Err(NetworkXError::new_err("Graph has no Eulerian paths.")),
        };
    }
    let inner = gr.undirected();
    if inner.node_count() > 1 && inner.nodes_ordered().iter().any(|n| inner.degree(n) == 0) {
        return Err(NetworkXError::new_err("Graph has no Eulerian paths."));
    }
    let odd_nodes: Vec<&str> = inner
        .nodes_ordered()
        .iter()
        .copied()
        .filter(|n| !inner.degree(n).is_multiple_of(2))
        .collect();
    let odd_count = odd_nodes.len();
    if odd_count != 0 && odd_count != 2 {
        return Err(NetworkXError::new_err("Graph has no Eulerian paths."));
    }
    if let Some(src_key) = src.as_deref() {
        if inner.node_count() > 1 && inner.degree(src_key) == 0 {
            return Err(NetworkXError::new_err("Graph has no Eulerian paths."));
        }
        if odd_count == 2 && !odd_nodes.contains(&src_key) {
            return Err(NetworkXError::new_err("Graph has no Eulerian paths."));
        }
    }
    let connected = py.allow_threads(|| fnx_algorithms::is_connected(inner).is_connected);
    if !connected {
        return Err(NetworkXError::new_err("Graph has no Eulerian paths."));
    }
    let result = py.allow_threads(|| fnx_algorithms::eulerian_path(inner, src.as_deref()));
    match result {
        Some(r) => Ok(r
            .edges
            .iter()
            .map(|(u, v)| (gr.py_node_key(py, u), gr.py_node_key(py, v)))
            .collect()),
        None => Err(NetworkXError::new_err("Graph has no Eulerian paths.")),
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

    let result = if gr.is_directed() {
        let dg = gr.digraph().expect("is_directed is true");
        py.allow_threads(|| fnx_algorithms::all_simple_paths_directed(dg, &s, &t, cutoff))
    } else {
        let inner = gr.undirected();
        py.allow_threads(|| fnx_algorithms::all_simple_paths(inner, &s, &t, cutoff))
    };

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
    // br-r37-c1-cbcsr: the core returns cycles as node INDICES, so map each one
    // straight to a cached Python node object (one ``py_node_key`` lookup per
    // node, then a refcount bump per cycle membership) instead of materializing
    // a ``String`` per cycle-node in the kernel and re-resolving it here.
    let (idx_cycles, _touched, _scanned, _peak) =
        py.allow_threads(|| fnx_algorithms::cycle_basis_index_cycles(inner, r.as_deref()));
    let node_objs: Vec<PyObject> = inner
        .nodes_ordered()
        .iter()
        .map(|n| gr.py_node_key(py, n))
        .collect();
    Ok(idx_cycles
        .iter()
        .map(|cycle| cycle.iter().map(|&i| node_objs[i].clone_ref(py)).collect())
        .collect())
}

/// Return a minimum weight cycle basis for an undirected simple graph.
/// Raises ``NetworkXNotImplemented`` on DiGraph and MultiGraph inputs.
#[pyfunction]
#[pyo3(signature = (g, weight=None))]
pub fn minimum_cycle_basis(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    weight: Option<&str>,
) -> PyResult<Vec<Vec<PyObject>>> {
    let gr = extract_graph(g)?;
    require_undirected(&gr, "minimum_cycle_basis")?;
    require_not_multigraph(&gr)?;
    let chord_order = if let GraphRef::Undirected(pg) = &gr {
        Some(minimum_cycle_basis_python_chord_order(py, pg)?)
    } else {
        None
    };
    let inner = gr.undirected();
    let result = py
        .allow_threads(|| {
            fnx_algorithms::minimum_cycle_basis_with_chord_order(
                inner,
                weight,
                chord_order.as_deref(),
            )
        })
        .map_err(|err| match err {
            fnx_algorithms::MinimumCycleBasisError::NegativeWeight { .. } => {
                PyValueError::new_err(("Contradictory paths found:", "negative weights?"))
            }
        })?;
    Ok(result
        .cycles
        .iter()
        .map(|cycle| cycle.iter().map(|n| gr.py_node_key(py, n)).collect())
        .collect())
}

fn minimum_cycle_basis_python_chord_order(py: Python<'_>, graph: &PyGraph) -> PyResult<Vec<usize>> {
    let node_names = graph.inner.nodes_ordered();
    let node_to_idx: HashMap<&str, usize> = node_names
        .iter()
        .enumerate()
        .map(|(idx, &node)| (node, idx))
        .collect();
    let edges = graph.inner.edges_ordered_borrowed();
    let mut edge_key_to_idx = HashMap::with_capacity(edges.len());
    for (edge_idx, (left, right, _attrs)) in edges.iter().enumerate() {
        edge_key_to_idx.insert(PyGraph::edge_key(left, right), edge_idx);
    }

    let tree_edges = minimum_cycle_basis_python_tree_edges(node_names.len(), &edges, &node_to_idx);
    let components = minimum_cycle_basis_python_components(node_names.len(), &edges, &node_to_idx);
    let mut chord_order = Vec::new();

    for component in components {
        let component_nodes: HashSet<usize> = component.into_iter().collect();
        let chords = pyo3::types::PySet::empty(py)?;
        for (edge_idx, (left, right, _attrs)) in edges.iter().enumerate() {
            let Some(&left_idx) = node_to_idx.get(*left) else {
                continue;
            };
            let Some(&right_idx) = node_to_idx.get(*right) else {
                continue;
            };
            if tree_edges.contains(&edge_idx)
                || !component_nodes.contains(&left_idx)
                || !component_nodes.contains(&right_idx)
            {
                continue;
            }
            let py_left = graph.py_node_key(py, left);
            let py_right = graph.py_node_key(py, right);
            let tuple = PyTuple::new(py, &[py_left, py_right])?;
            chords.add(tuple)?;
        }

        for item in chords.iter() {
            let tuple = item.downcast::<PyTuple>()?;
            let left = node_key_to_string(py, &tuple.get_item(0)?)?;
            let right = node_key_to_string(py, &tuple.get_item(1)?)?;
            if let Some(&edge_idx) = edge_key_to_idx.get(&PyGraph::edge_key(&left, &right)) {
                chord_order.push(edge_idx);
            }
        }
    }

    Ok(chord_order)
}

fn minimum_cycle_basis_python_tree_edges(
    node_count: usize,
    edges: &[(&str, &str, &AttrMap)],
    node_to_idx: &HashMap<&str, usize>,
) -> HashSet<usize> {
    let mut parent: Vec<usize> = (0..node_count).collect();
    let mut tree_edges = HashSet::new();
    for (edge_idx, (left, right, _attrs)) in edges.iter().enumerate() {
        let Some(&left_idx) = node_to_idx.get(*left) else {
            continue;
        };
        let Some(&right_idx) = node_to_idx.get(*right) else {
            continue;
        };
        if left_idx == right_idx {
            continue;
        }
        if minimum_cycle_basis_python_union(&mut parent, left_idx, right_idx) {
            tree_edges.insert(edge_idx);
        }
    }
    tree_edges
}

fn minimum_cycle_basis_python_components(
    node_count: usize,
    edges: &[(&str, &str, &AttrMap)],
    node_to_idx: &HashMap<&str, usize>,
) -> Vec<Vec<usize>> {
    let mut adjacency = vec![Vec::<usize>::new(); node_count];
    for (left, right, _attrs) in edges {
        let Some(&left_idx) = node_to_idx.get(*left) else {
            continue;
        };
        let Some(&right_idx) = node_to_idx.get(*right) else {
            continue;
        };
        if left_idx == right_idx {
            continue;
        }
        adjacency[left_idx].push(right_idx);
        adjacency[right_idx].push(left_idx);
    }

    let mut components = Vec::new();
    let mut seen = vec![false; node_count];
    for start in 0..node_count {
        if seen[start] {
            continue;
        }
        let mut component = Vec::new();
        let mut stack = vec![start];
        seen[start] = true;
        while let Some(node) = stack.pop() {
            component.push(node);
            for &neighbor in &adjacency[node] {
                if !seen[neighbor] {
                    seen[neighbor] = true;
                    stack.push(neighbor);
                }
            }
        }
        component.sort_unstable();
        components.push(component);
    }
    components
}

fn minimum_cycle_basis_python_find(parent: &mut [usize], node: usize) -> usize {
    if parent[node] != node {
        parent[node] = minimum_cycle_basis_python_find(parent, parent[node]);
    }
    parent[node]
}

fn minimum_cycle_basis_python_union(parent: &mut [usize], left: usize, right: usize) -> bool {
    let left_root = minimum_cycle_basis_python_find(parent, left);
    let right_root = minimum_cycle_basis_python_find(parent, right);
    if left_root == right_root {
        return false;
    }
    if left_root < right_root {
        parent[right_root] = left_root;
    } else {
        parent[left_root] = right_root;
    }
    true
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
    validate_node(&gr, &u_key, u, "Node")?;
    validate_node(&gr, &v_key, v, "Node")?;
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
    let _ = sort_neighbors; // accepted for API compat, handled in Python wrapper
    let gr = extract_graph(g)?;
    let source_key = node_key_to_string(py, source)?;
    if !gr.has_node(&source_key) {
        return Err(NodeNotFound::new_err(format!(
            "The node {} is not in the graph.",
            source.str()?
        )));
    }

    let edges = match &gr {
        GraphRef::Directed { dg, .. } => {
            let inner = &dg.inner;
            if reverse {
                py.allow_threads(|| {
                    fnx_algorithms::bfs_edges_directed_reverse(inner, &source_key, depth_limit)
                })
            } else {
                py.allow_threads(|| {
                    fnx_algorithms::bfs_edges_directed(inner, &source_key, depth_limit)
                })
            }
        }

        GraphRef::Undirected(pg) => {
            let inner = &pg.inner;

            py.allow_threads(|| fnx_algorithms::bfs_edges(inner, &source_key, depth_limit))
        }
        _ => {
            if let GraphRef::MultiDirected { mdg, .. } = &gr {
                // br-r37-c1-86c7r: walk the MultiDiGraph successor (or predecessor,
                // for reverse) adjacency DIRECTLY — no conversion.
                let inner = &mdg.inner;
                py.allow_threads(|| {
                    let nodes = inner.nodes_ordered();
                    let Some(src) = nodes.iter().position(|&n| n == source_key) else {
                        return Vec::new();
                    };
                    let adj = build_index_adjacency(&nodes, |u| {
                        if reverse {
                            inner.predecessors(u).unwrap_or_default()
                        } else {
                            inner.successors(u).unwrap_or_default()
                        }
                    });
                    bfs_edges_indexed(&adj, &nodes, src, depth_limit)
                })
            } else if gr.is_directed() {
                let inner = gr.digraph().expect("is_directed checked above");
                if reverse {
                    py.allow_threads(|| {
                        fnx_algorithms::bfs_edges_directed_reverse(inner, &source_key, depth_limit)
                    })
                } else {
                    py.allow_threads(|| {
                        fnx_algorithms::bfs_edges_directed(inner, &source_key, depth_limit)
                    })
                }
            } else if let GraphRef::MultiUndirected { mg, .. } = &gr {
                // br-r37-c1-86c7r: walk the MultiGraph neighbor adjacency
                // DIRECTLY — no conversion.
                let inner = &mg.inner;
                py.allow_threads(|| {
                    let nodes = inner.nodes_ordered();
                    let Some(src) = nodes.iter().position(|&n| n == source_key) else {
                        return Vec::new();
                    };
                    let adj =
                        build_index_adjacency(&nodes, |u| inner.neighbors(u).unwrap_or_default());
                    bfs_edges_indexed(&adj, &nodes, src, depth_limit)
                })
            } else {
                let inner = gr.undirected();
                py.allow_threads(|| fnx_algorithms::bfs_edges(inner, &source_key, depth_limit))
            }
        }
    };

    // br-r37-c1-6hpa9: nx yields DISCOVERY objects (source as passed,
    // children as their parent's adjacency-row object; pred rows when
    // reverse).
    let disp = gr.discovery_map(
        py,
        &edges,
        Some((&source_key, source.clone().unbind())),
        reverse,
    );
    Ok(edges
        .iter()
        .map(|(u, v)| {
            (
                gr.disp_or_node_key(py, &disp, u),
                gr.disp_or_node_key(py, &disp, v),
            )
        })
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
    let _ = sort_neighbors;
    let gr = extract_graph(g)?;
    let source_key = node_key_to_string(py, source)?;
    if !gr.has_node(&source_key) {
        return Err(NodeNotFound::new_err(format!(
            "The node {} is not in the graph.",
            source.str()?
        )));
    }

    let edges = match &gr {
        GraphRef::Directed { dg, .. } => {
            let inner = &dg.inner;
            if reverse {
                py.allow_threads(|| {
                    fnx_algorithms::bfs_edges_directed_reverse(inner, &source_key, depth_limit)
                })
            } else {
                py.allow_threads(|| {
                    fnx_algorithms::bfs_edges_directed(inner, &source_key, depth_limit)
                })
            }
        }

        GraphRef::Undirected(pg) => {
            let inner = &pg.inner;

            py.allow_threads(|| fnx_algorithms::bfs_edges(inner, &source_key, depth_limit))
        }
        _ => {
            if let GraphRef::MultiDirected { mdg, .. } = &gr {
                // br-r37-c1-86c7r: walk the MultiDiGraph successor (or predecessor,
                // for reverse) adjacency DIRECTLY — no conversion.
                let inner = &mdg.inner;
                py.allow_threads(|| {
                    let nodes = inner.nodes_ordered();
                    let Some(src) = nodes.iter().position(|&n| n == source_key) else {
                        return Vec::new();
                    };
                    let adj = build_index_adjacency(&nodes, |u| {
                        if reverse {
                            inner.predecessors(u).unwrap_or_default()
                        } else {
                            inner.successors(u).unwrap_or_default()
                        }
                    });
                    bfs_edges_indexed(&adj, &nodes, src, depth_limit)
                })
            } else if gr.is_directed() {
                let inner = gr.digraph().expect("is_directed checked above");
                if reverse {
                    py.allow_threads(|| {
                        fnx_algorithms::bfs_edges_directed_reverse(inner, &source_key, depth_limit)
                    })
                } else {
                    py.allow_threads(|| {
                        fnx_algorithms::bfs_edges_directed(inner, &source_key, depth_limit)
                    })
                }
            } else if let GraphRef::MultiUndirected { mg, .. } = &gr {
                // br-r37-c1-86c7r: walk the MultiGraph neighbor adjacency
                // DIRECTLY — no conversion.
                let inner = &mg.inner;
                py.allow_threads(|| {
                    let nodes = inner.nodes_ordered();
                    let Some(src) = nodes.iter().position(|&n| n == source_key) else {
                        return Vec::new();
                    };
                    let adj =
                        build_index_adjacency(&nodes, |u| inner.neighbors(u).unwrap_or_default());
                    bfs_edges_indexed(&adj, &nodes, src, depth_limit)
                })
            } else {
                let inner = gr.undirected();
                py.allow_threads(|| fnx_algorithms::bfs_edges(inner, &source_key, depth_limit))
            }
        }
    };

    // br-r37-c1-wvbzw: do NOT clone the source's RuntimePolicy — its
    // decision ledger is unbounded (one entry per recorded op, e.g. E
    // entries after a per-edge ctor), and the old
    // `runtime_policy().clone()` + `set_runtime_policy(tree_policy)`
    // pair cloned it TWICE per call: bfs_tree on a ctor-built source was
    // 5.3x slower than on an identical native-built one. The tree only
    // needs the MODE; start a fresh ledger
    // (reference_runtime_policy_clone_tax).
    let tree_mode = match &gr {
        // br-r37-c1-mexh6-dfs/-dirtree: read the mode straight off the
        // Multi(Di)Graph instead of gr.undirected()/gr.digraph() (which would
        // build the full simple-graph conversion just for the RuntimePolicy
        // mode — defeating the structure-only-ordered edge path above).
        GraphRef::MultiUndirected { mg, .. } => mg.inner.mode(),
        GraphRef::MultiDirected { mdg, .. } => mdg.inner.mode(),
        _ if gr.is_directed() => gr.digraph().expect("is_directed checked above").mode(),
        _ => gr.undirected().mode(),
    };
    let mut tree = crate::digraph::PyDiGraph::new_empty_with_mode(py, tree_mode)?;
    let source_py = source.clone().unbind();
    let source_s = source_key.clone();
    tree.inner.add_node(&source_s);
    tree.node_key_map.insert(source_s, source_py);

    // br-r37-c1-d58s8 tree-assembly tier: mirrors stay LAZY — absent
    // node/edge attr-dict entries are tolerated everywhere (proven by
    // the wholesale-clone converters, which produce none). The old
    // eager empty-PyDict inserts cost three allocations per edge.
    for (u, v) in &edges {
        // br-r37-c1-6hpa9: discovery object — the parent's row override
        // (pred rows when reverse), not the node-map object.
        let v_obj = if reverse {
            gr.py_pred_row_key(py, u, v)
        } else {
            gr.py_row_key(py, u, v)
        };
        tree.node_key_map.insert(v.clone(), v_obj);
    }
    let _inserted = tree.inner.extend_edges_unrecorded(edges);

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
            source.str()?
        )));
    }

    let preds = match &gr {
        GraphRef::Directed { dg, .. } => {
            let __dg_inner = &dg.inner;
            py.allow_threads(|| {
                fnx_algorithms::bfs_predecessors_directed(__dg_inner, &source_key, depth_limit)
            })
        }

        GraphRef::Undirected(pg) => {
            let inner = &pg.inner;

            py.allow_threads(|| fnx_algorithms::bfs_predecessors(inner, &source_key, depth_limit))
        }
        _ => {
            if gr.is_directed() {
                {
                    let __gr_digraph = gr.digraph().expect("is_directed checked above");
                    py.allow_threads(|| {
                        fnx_algorithms::bfs_predecessors_directed(
                            __gr_digraph,
                            &source_key,
                            depth_limit,
                        )
                    })
                }
            } else {
                let inner = gr.undirected();

                py.allow_threads(|| {
                    fnx_algorithms::bfs_predecessors(inner, &source_key, depth_limit)
                })
            }
        }
    };

    // br-r37-c1-6hpa9: the (child, parent) pairs ARE the BFS tree edges
    // in discovery order — derive nx's discovery objects from them.
    let stream: Vec<(String, String)> = preds
        .iter()
        .map(|(child, parent)| (parent.clone(), child.clone()))
        .collect();
    let disp = gr.discovery_map(
        py,
        &stream,
        Some((&source_key, source.clone().unbind())),
        false,
    );
    Ok(preds
        .into_iter()
        .map(|(child, parent)| {
            (
                gr.disp_or_node_key(py, &disp, &child),
                gr.disp_or_node_key(py, &disp, &parent),
            )
        })
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
            source.str()?
        )));
    }

    let succs = match &gr {
        GraphRef::Directed { dg, .. } => {
            let __dg_inner = &dg.inner;
            py.allow_threads(|| {
                fnx_algorithms::bfs_successors_directed(__dg_inner, &source_key, depth_limit)
            })
        }

        GraphRef::Undirected(pg) => {
            let inner = &pg.inner;

            py.allow_threads(|| fnx_algorithms::bfs_successors(inner, &source_key, depth_limit))
        }
        _ => {
            if gr.is_directed() {
                {
                    let __gr_digraph = gr.digraph().expect("is_directed checked above");
                    py.allow_threads(|| {
                        fnx_algorithms::bfs_successors_directed(
                            __gr_digraph,
                            &source_key,
                            depth_limit,
                        )
                    })
                }
            } else {
                let inner = gr.undirected();

                py.allow_threads(|| fnx_algorithms::bfs_successors(inner, &source_key, depth_limit))
            }
        }
    };

    // br-r37-c1-6hpa9: flatten (parent, [children]) into the BFS tree
    // edge stream (discovery order) and map through discovery objects.
    let stream: Vec<(String, String)> = succs
        .iter()
        .flat_map(|(parent, children)| children.iter().map(move |c| (parent.clone(), c.clone())))
        .collect();
    let disp = gr.discovery_map(
        py,
        &stream,
        Some((&source_key, source.clone().unbind())),
        false,
    );
    Ok(succs
        .into_iter()
        .map(|(parent, children)| {
            let py_parent = gr.disp_or_node_key(py, &disp, &parent);
            let py_children: Vec<PyObject> = children
                .iter()
                .map(|c| gr.disp_or_node_key(py, &disp, c))
                .collect();
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
    // br-r37-c1-6hpa9: nx layer members carry DISCOVERY objects — sources
    // as passed, every other node as its discovering parent's
    // adjacency-row object. The _with_parents kernels emit the parent for
    // free; seeds map canonical -> passed object.
    let emit = |layers: Vec<Vec<(String, Option<String>)>>,
                seeds: &std::collections::HashMap<String, PyObject>|
     -> Vec<Vec<PyObject>> {
        layers
            .into_iter()
            .map(|layer| {
                layer
                    .into_iter()
                    .map(|(n, parent)| match parent {
                        Some(p) => gr.py_row_key(py, &p, &n),
                        None => seeds
                            .get(n.as_str())
                            .map_or_else(|| gr.py_node_key(py, &n), |o| o.clone_ref(py)),
                    })
                    .collect()
            })
            .collect()
    };
    // sources can be a single node or iterable of nodes
    let source_key = node_key_to_string(py, sources)?;
    if gr.has_node(&source_key) {
        // Single source
        let source_refs = [source_key.as_str()];
        let layers = if gr.is_directed() {
            let __gr_digraph = gr.digraph().expect("is_directed checked above");
            py.allow_threads(|| {
                fnx_algorithms::bfs_layers_directed_multi_with_parents(__gr_digraph, &source_refs)
            })
        } else {
            let inner = gr.undirected();
            py.allow_threads(|| fnx_algorithms::bfs_layers_multi_with_parents(inner, &source_refs))
        };
        let mut seeds = std::collections::HashMap::new();
        seeds.insert(source_key, sources.clone().unbind());
        return Ok(emit(layers, &seeds));
    }

    // Try as iterable of source nodes
    if let Ok(iter) = sources.try_iter() {
        // br-r37-c1-6hpa9: nx does `visited = set(sources);
        // current_layer = list(visited)` — layer 0 (and therefore the
        // whole traversal seed order) is CPython SET iteration order.
        // Build a real PySet in-process so the order matches nx exactly
        // at any hash seed.
        let items: Vec<Bound<'_, PyAny>> = iter.collect::<PyResult<Vec<_>>>()?;
        let py_set = pyo3::types::PySet::new(py, &items)?;
        let mut source_keys: Vec<String> = Vec::new();
        let mut seeds: std::collections::HashMap<String, PyObject> =
            std::collections::HashMap::new();
        for item in py_set.iter() {
            let k = node_key_to_string(py, &item)?;
            if !gr.has_node(&k) {
                // nx raises NetworkXError (not NodeNotFound) here.
                return Err(NetworkXError::new_err(format!(
                    "The node {} is not in the graph.",
                    item.str()?
                )));
            }
            seeds.entry(k.clone()).or_insert_with(|| item.unbind());
            source_keys.push(k);
        }
        let source_refs: Vec<&str> = source_keys.iter().map(String::as_str).collect();
        let layers = if gr.is_directed() {
            let __gr_digraph = gr.digraph().expect("is_directed checked above");
            py.allow_threads(|| {
                fnx_algorithms::bfs_layers_directed_multi_with_parents(__gr_digraph, &source_refs)
            })
        } else {
            let inner = gr.undirected();
            py.allow_threads(|| fnx_algorithms::bfs_layers_multi_with_parents(inner, &source_refs))
        };
        return Ok(emit(layers, &seeds));
    }

    Err(NodeNotFound::new_err(format!(
        "The node {} is not in the graph.",
        sources.str()?
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
            source.str()?
        )));
    }

    let nodes = match &gr {
        GraphRef::Directed { dg, .. } => {
            let __dg_inner = &dg.inner;
            py.allow_threads(|| {
                fnx_algorithms::descendants_at_distance_directed(__dg_inner, &source_key, distance)
            })
        }

        GraphRef::Undirected(pg) => {
            let inner = &pg.inner;

            py.allow_threads(|| {
                fnx_algorithms::descendants_at_distance(inner, &source_key, distance)
            })
        }
        _ => {
            if gr.is_directed() {
                {
                    let __gr_digraph = gr.digraph().expect("is_directed checked above");
                    py.allow_threads(|| {
                        fnx_algorithms::descendants_at_distance_directed(
                            __gr_digraph,
                            &source_key,
                            distance,
                        )
                    })
                }
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

fn dfs_forest_undirected(
    graph: &fnx_classes::Graph,
    nodes: &[&str],
    depth_limit: Option<usize>,
) -> (Vec<(String, String)>, Vec<String>) {
    let max_depth = depth_limit.unwrap_or(usize::MAX);
    let mut visited: HashSet<&str> = HashSet::new();
    let mut edges: Vec<(String, String)> = Vec::new();
    let mut preorder: Vec<String> = Vec::new();

    for &start in nodes {
        if visited.contains(start) {
            continue;
        }
        visited.insert(start);
        preorder.push(start.to_owned());
        let mut stack: Vec<(Option<&str>, &str, usize)> = Vec::new();
        // br-r37-c1-br12g: nx ALWAYS yields a root's depth-1 edges, even when
        // depth_limit <= 0 (the limit only gates descent BEYOND depth 1). The
        // old `max_depth > 0` guard suppressed the entire depth-1 star at dl=0,
        // so dfs_edges/dfs_predecessors/dfs_successors(source=None, depth_limit=0)
        // returned an empty forest instead of nx's star. Push depth-1
        // unconditionally; `depth < max_depth` below still blocks deeper descent.
        if let Some(neighbors) = graph.neighbors(start) {
            for neighbor in neighbors.into_iter().rev() {
                if !visited.contains(neighbor) {
                    stack.push((Some(start), neighbor, 1));
                }
            }
        }
        while let Some((parent, node, depth)) = stack.pop() {
            if visited.contains(node) {
                continue;
            }
            visited.insert(node);
            preorder.push(node.to_owned());
            if let Some(p) = parent {
                edges.push((p.to_owned(), node.to_owned()));
            }
            if depth < max_depth
                && let Some(neighbors) = graph.neighbors(node)
            {
                for neighbor in neighbors.into_iter().rev() {
                    if !visited.contains(neighbor) {
                        stack.push((Some(node), neighbor, depth + 1));
                    }
                }
            }
        }
    }

    (edges, preorder)
}

fn dfs_forest_directed(
    digraph: &fnx_classes::digraph::DiGraph,
    nodes: &[&str],
    depth_limit: Option<usize>,
) -> (Vec<(String, String)>, Vec<String>) {
    let max_depth = depth_limit.unwrap_or(usize::MAX);
    let mut visited: HashSet<&str> = HashSet::new();
    let mut edges: Vec<(String, String)> = Vec::new();
    let mut preorder: Vec<String> = Vec::new();

    for &start in nodes {
        if visited.contains(start) {
            continue;
        }
        visited.insert(start);
        preorder.push(start.to_owned());
        let mut stack: Vec<(Option<&str>, &str, usize)> = Vec::new();
        // br-r37-c1-br12g: see dfs_forest_undirected — push depth-1 successors
        // unconditionally so dl=0 yields nx's depth-1 star, not an empty forest.
        if let Some(succs) = digraph.successors(start) {
            for succ in succs.into_iter().rev() {
                if !visited.contains(succ) {
                    stack.push((Some(start), succ, 1));
                }
            }
        }
        while let Some((parent, node, depth)) = stack.pop() {
            if visited.contains(node) {
                continue;
            }
            visited.insert(node);
            preorder.push(node.to_owned());
            if let Some(p) = parent {
                edges.push((p.to_owned(), node.to_owned()));
            }
            if depth < max_depth
                && let Some(succs) = digraph.successors(node)
            {
                for succ in succs.into_iter().rev() {
                    if !visited.contains(succ) {
                        stack.push((Some(node), succ, depth + 1));
                    }
                }
            }
        }
    }

    (edges, preorder)
}

// ---------------------------------------------------------------------------
// br-r37-c1-86c7r: integer-indexed DFS/BFS walks over a precomputed adjacency
// slice `adj[i] = neighbor indices of node i in adjacency order`. These let the
// multigraph DFS/BFS tree paths walk the MultiGraph/MultiDiGraph inner's
// DISTINCT-neighbor index rows (neighbors_indices / successors_indices /
// predecessors_indices) DIRECTLY — eliminating the
// multigraph->simple-graph-structure-only-ordered conversion (build a whole new
// Graph + apply_row_orders) that was ~100% of the dfs_tree/bfs_tree multigraph
// runtime (~12ms @ N=1200/m=6000). The walk discipline is byte-identical to the
// simple-graph kernels: `mg.neighbors_indices(i)` order == the converted
// graph's row order (the conversion is BUILT from that same adjacency +
// apply_row_orders), so the emitted edge sequence is unchanged.

/// Build `(nodes, adj)` where `adj[i]` is the DISTINCT-neighbor index row of node
/// `i` in adjacency order, straight from the multigraph inner's string adjacency
/// (`neighbors` / `successors` / `predecessors`). One O(V+E) pass — no
/// simple-graph materialization, no `apply_row_orders`. The IndexMap-backed
/// `neighbors(u)` order is exactly the order the structure-only-ordered
/// conversion restored, so the emitted DFS/BFS edge sequence is unchanged.
fn build_index_adjacency<'a>(
    nodes: &[&'a str],
    str_neighbors: impl Fn(&str) -> Vec<&'a str>,
) -> Vec<Vec<usize>> {
    let mut index: std::collections::HashMap<&str, usize> =
        std::collections::HashMap::with_capacity(nodes.len());
    for (i, &n) in nodes.iter().enumerate() {
        index.insert(n, i);
    }
    nodes
        .iter()
        .map(|&u| {
            str_neighbors(u)
                .into_iter()
                .filter_map(|v| index.get(v).copied())
                .collect()
        })
        .collect()
}

/// Single-source DFS — mirrors `fnx_algorithms::dfs_edges` / `dfs_edges_directed`
/// (reverse-push stack; immediate neighbors always pushed at depth 1 regardless
/// of `depth_limit`, deeper descent gated on `depth < max_depth`).
fn dfs_edges_indexed(
    adj: &[Vec<usize>],
    nodes: &[&str],
    source_idx: usize,
    depth_limit: Option<usize>,
) -> Vec<(String, String)> {
    let max_depth = depth_limit.unwrap_or(usize::MAX);
    let n = nodes.len();
    let mut visited = vec![false; n];
    let mut edges: Vec<(String, String)> = Vec::new();
    visited[source_idx] = true;
    let mut stack: Vec<(usize, usize, usize)> = Vec::new();
    for &nbr in adj[source_idx].iter().rev() {
        if !visited[nbr] {
            stack.push((source_idx, nbr, 1));
        }
    }
    while let Some((parent, node, depth)) = stack.pop() {
        if visited[node] {
            continue;
        }
        visited[node] = true;
        edges.push((nodes[parent].to_owned(), nodes[node].to_owned()));
        if depth < max_depth {
            for &nbr in adj[node].iter().rev() {
                if !visited[nbr] {
                    stack.push((node, nbr, depth + 1));
                }
            }
        }
    }
    edges
}

/// Forest DFS (no source) — mirrors `dfs_forest_undirected` / `dfs_forest_directed`
/// EXACTLY, including the `max_depth > 0` guard before pushing a root's depth-1
/// neighbors (so `depth_limit=0` yields an empty forest, preserving current
/// behavior — the separate dl=0 parity bug is tracked elsewhere).
fn dfs_forest_indexed(
    adj: &[Vec<usize>],
    nodes: &[&str],
    depth_limit: Option<usize>,
) -> Vec<(String, String)> {
    let max_depth = depth_limit.unwrap_or(usize::MAX);
    let n = nodes.len();
    let mut visited = vec![false; n];
    let mut edges: Vec<(String, String)> = Vec::new();
    for start in 0..n {
        if visited[start] {
            continue;
        }
        visited[start] = true;
        let mut stack: Vec<(usize, usize, usize)> = Vec::new();
        // br-r37-c1-br12g: push depth-1 unconditionally (nx yields the depth-1
        // star even at dl=0); `depth < max_depth` below still gates descent.
        for &nbr in adj[start].iter().rev() {
            if !visited[nbr] {
                stack.push((start, nbr, 1));
            }
        }
        while let Some((parent, node, depth)) = stack.pop() {
            if visited[node] {
                continue;
            }
            visited[node] = true;
            edges.push((nodes[parent].to_owned(), nodes[node].to_owned()));
            if depth < max_depth {
                for &nbr in adj[node].iter().rev() {
                    if !visited[nbr] {
                        stack.push((node, nbr, depth + 1));
                    }
                }
            }
        }
    }
    edges
}

/// Single-source BFS — mirrors `fnx_algorithms::bfs_edges` / `bfs_edges_directed`
/// (FIFO queue; `depth >= max_depth` short-circuits descent).
fn bfs_edges_indexed(
    adj: &[Vec<usize>],
    nodes: &[&str],
    source_idx: usize,
    depth_limit: Option<usize>,
) -> Vec<(String, String)> {
    let max_depth = depth_limit.unwrap_or(usize::MAX);
    let n = nodes.len();
    let mut visited = vec![false; n];
    let mut edges: Vec<(String, String)> = Vec::new();
    visited[source_idx] = true;
    let mut queue: std::collections::VecDeque<(usize, usize)> = std::collections::VecDeque::new();
    queue.push_back((source_idx, 0));
    while let Some((node, depth)) = queue.pop_front() {
        if depth >= max_depth {
            continue;
        }
        for &nbr in &adj[node] {
            if !visited[nbr] {
                visited[nbr] = true;
                edges.push((nodes[node].to_owned(), nodes[nbr].to_owned()));
                queue.push_back((nbr, depth + 1));
            }
        }
    }
    edges
}

// br-r37-c1-ijgj4: forest DFS postorder mirroring nx's `dfs_labeled_edges`
// EXACTLY (the source via `iter(G[node])` per-frame). The old version had two
// bugs vs nx when `depth_limit` was set on the forest (source=None) path:
//   1. off-by-one depth — nx's `depth_now` is the STACK DEPTH (the start frame
//      is depth 1, so its children are pushed only when `depth_now < limit`);
//      the old code used a 0-based `depth` so it descended one level too far.
//   2. at the depth boundary nx still MARKS a node's immediate neighbors visited
//      (yields them "forward") even though it does not descend into them, so
//      they do NOT become separate forest roots and are NOT post-ordered. The
//      old code skipped the neighbors entirely, leaving them to be revisited as
//      roots. Only nodes that receive a stack frame (start + descended nodes)
//      are post-ordered. `depth_limit=None` -> usize::MAX is equivalent to nx's
//      `len(G)` (a component is never deeper than its node count).
fn dfs_postorder_forest_walk<'a>(
    nodes: &[&'a str],
    neighbors_of: impl Fn(&str) -> Vec<&'a str>,
    depth_limit: Option<usize>,
) -> Vec<String> {
    let depth_limit = depth_limit.unwrap_or(usize::MAX);
    let mut visited: HashSet<&str> = HashSet::new();
    let mut postorder: Vec<String> = Vec::new();

    for &start in nodes {
        if visited.contains(start) {
            continue;
        }
        visited.insert(start);
        // Each frame: (node, its neighbor list, next-child index). The stack
        // length is nx's `depth_now` (start frame => 1).
        let mut stack: Vec<(&str, Vec<&'a str>, usize)> = vec![(start, neighbors_of(start), 0)];
        while !stack.is_empty() {
            let depth_now = stack.len();
            let (_, children, idx) = stack.last_mut().expect("stack non-empty");
            let mut descended = false;
            while *idx < children.len() {
                let child = children[*idx];
                *idx += 1;
                if !visited.contains(child) {
                    visited.insert(child);
                    if depth_now < depth_limit {
                        let child_nbrs = neighbors_of(child);
                        stack.push((child, child_nbrs, 0));
                        descended = true;
                        break;
                    }
                    // boundary: marked visited but not descended / not post-ordered
                }
            }
            if !descended {
                let (node, _, _) = stack.pop().expect("stack non-empty");
                postorder.push(node.to_owned());
            }
        }
    }

    postorder
}

fn dfs_postorder_forest_undirected(
    graph: &fnx_classes::Graph,
    nodes: &[&str],
    depth_limit: Option<usize>,
) -> Vec<String> {
    dfs_postorder_forest_walk(
        nodes,
        |n| graph.neighbors(n).unwrap_or_default(),
        depth_limit,
    )
}

fn dfs_postorder_forest_directed(
    digraph: &fnx_classes::digraph::DiGraph,
    nodes: &[&str],
    depth_limit: Option<usize>,
) -> Vec<String> {
    dfs_postorder_forest_walk(
        nodes,
        |n| digraph.successors(n).unwrap_or_default(),
        depth_limit,
    )
}

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
                    s.str()?
                )));
            }
            Some(k)
        }
        None => None,
    };

    let edges = dfs_edges_canonical(py, &gr, source_key.clone(), depth_limit);

    // br-r37-c1-wvbzw: nx yields DISCOVERY objects — the source as passed,
    // every other node as its parent's adjacency-ROW object (z6uka row
    // overrides for mixed hash-equal keys). Propagate along the walk.
    let mut disp: std::collections::HashMap<String, PyObject> = std::collections::HashMap::new();
    if let (Some(k), Some(s)) = (source_key, source) {
        disp.insert(k, s.clone().unbind());
    }
    let mut out = Vec::with_capacity(edges.len());
    for (u, v) in edges {
        let u_obj = disp
            .get(u.as_str())
            .map_or_else(|| gr.py_node_key(py, &u), |o| o.clone_ref(py));
        let v_obj = gr.py_row_key(py, &u, &v);
        disp.entry(u).or_insert_with(|| u_obj.clone_ref(py));
        disp.insert(v, v_obj.clone_ref(py));
        out.push((u_obj, v_obj));
    }
    Ok(out)
}

/// br-r37-c1-wvbzw: canonical-STRING DFS edge stream shared by dfs_edges
/// (which converts to PyObjects for Python) and dfs_tree (which previously
/// consumed the PyObject list and re-canonicalized EVERY endpoint via
/// node_key_to_string — a per-edge Python round-trip that kept dfs_tree at
/// 2x nx after the ledger fix).
fn dfs_edges_canonical(
    py: Python<'_>,
    gr: &GraphRef<'_>,
    source_key: Option<String>,
    depth_limit: Option<usize>,
) -> Vec<(String, String)> {
    match source_key {
        Some(source_key) => match gr {
            GraphRef::Directed { dg, .. } => {
                let __dg_inner = &dg.inner;
                py.allow_threads(|| {
                    fnx_algorithms::dfs_edges_directed(__dg_inner, &source_key, depth_limit)
                })
            }

            GraphRef::Undirected(pg) => {
                let inner = &pg.inner;

                py.allow_threads(|| fnx_algorithms::dfs_edges(inner, &source_key, depth_limit))
            }
            _ => {
                if let GraphRef::MultiDirected { mdg, .. } = gr {
                    // br-r37-c1-86c7r: walk the MultiDiGraph successor adjacency
                    // DIRECTLY — no multidigraph->simple-digraph conversion.
                    let inner = &mdg.inner;
                    py.allow_threads(|| {
                        let nodes = inner.nodes_ordered();
                        let Some(src) = nodes.iter().position(|&n| n == source_key) else {
                            return Vec::new();
                        };
                        let adj = build_index_adjacency(&nodes, |u| {
                            inner.successors(u).unwrap_or_default()
                        });
                        dfs_edges_indexed(&adj, &nodes, src, depth_limit)
                    })
                } else if gr.is_directed() {
                    let __gr_digraph = gr.digraph().expect("is_directed checked above");
                    py.allow_threads(|| {
                        fnx_algorithms::dfs_edges_directed(__gr_digraph, &source_key, depth_limit)
                    })
                } else if let GraphRef::MultiUndirected { mg, .. } = gr {
                    // br-r37-c1-86c7r: walk the MultiGraph neighbor adjacency
                    // DIRECTLY — no multigraph->simple-graph conversion.
                    let inner = &mg.inner;
                    py.allow_threads(|| {
                        let nodes = inner.nodes_ordered();
                        let Some(src) = nodes.iter().position(|&n| n == source_key) else {
                            return Vec::new();
                        };
                        let adj = build_index_adjacency(&nodes, |u| {
                            inner.neighbors(u).unwrap_or_default()
                        });
                        dfs_edges_indexed(&adj, &nodes, src, depth_limit)
                    })
                } else {
                    let inner = gr.undirected();
                    py.allow_threads(|| fnx_algorithms::dfs_edges(inner, &source_key, depth_limit))
                }
            }
        },
        None => {
            let nodes = gr.nodes_ordered();
            if nodes.is_empty() {
                return Vec::new();
            }
            match gr {
                GraphRef::Directed { dg, .. } => {
                    let __dg_inner = &dg.inner;
                    py.allow_threads(|| dfs_forest_directed(__dg_inner, &nodes, depth_limit).0)
                }
                GraphRef::Undirected(pg) => {
                    let inner = &pg.inner;
                    py.allow_threads(|| dfs_forest_undirected(inner, &nodes, depth_limit).0)
                }
                _ => {
                    if let GraphRef::MultiDirected { mdg, .. } = gr {
                        // br-r37-c1-86c7r: forest walk over the MultiDiGraph
                        // successor adjacency DIRECTLY — no conversion.
                        let inner = &mdg.inner;
                        py.allow_threads(|| {
                            let mnodes = inner.nodes_ordered();
                            let adj = build_index_adjacency(&mnodes, |u| {
                                inner.successors(u).unwrap_or_default()
                            });
                            dfs_forest_indexed(&adj, &mnodes, depth_limit)
                        })
                    } else if gr.is_directed() {
                        let __gr_digraph = gr.digraph().expect("is_directed checked above");
                        py.allow_threads(|| {
                            dfs_forest_directed(__gr_digraph, &nodes, depth_limit).0
                        })
                    } else if let GraphRef::MultiUndirected { mg, .. } = gr {
                        // br-r37-c1-86c7r: forest walk over the MultiGraph
                        // neighbor adjacency DIRECTLY — no conversion.
                        let inner = &mg.inner;
                        py.allow_threads(|| {
                            let mnodes = inner.nodes_ordered();
                            let adj = build_index_adjacency(&mnodes, |u| {
                                inner.neighbors(u).unwrap_or_default()
                            });
                            dfs_forest_indexed(&adj, &mnodes, depth_limit)
                        })
                    } else {
                        let inner = gr.undirected();
                        py.allow_threads(|| dfs_forest_undirected(inner, &nodes, depth_limit).0)
                    }
                }
            }
        }
    }
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
    let gr = extract_graph(g)?;
    // br-r37-c1-wvbzw lever 2: consume the kernel's canonical STRINGS
    // directly. The old path called dfs_edges (strings -> PyObjects) and
    // then re-canonicalized every endpoint via node_key_to_string — a
    // per-edge Python round-trip that kept dfs_tree at ~2x nx after the
    // ledger fix. Display keys come from the source's node_key_map.
    let source_key = match source {
        Some(s) => {
            let k = node_key_to_string(py, s)?;
            if !gr.has_node(&k) {
                return Err(NodeNotFound::new_err(format!(
                    "The node {} is not in the graph.",
                    s.str()?
                )));
            }
            Some(k)
        }
        None => None,
    };
    let edge_list = dfs_edges_canonical(py, &gr, source_key.clone(), depth_limit);

    // fresh ledger, mode only (lever 1) — see bfs_tree above.
    let tree_mode = match &gr {
        // br-r37-c1-mexh6-dfs/-dirtree: read the mode straight off the
        // Multi(Di)Graph instead of gr.undirected()/gr.digraph() (which would
        // build the full simple-graph conversion just for the RuntimePolicy
        // mode — defeating the structure-only-ordered edge path above).
        GraphRef::MultiUndirected { mg, .. } => mg.inner.mode(),
        GraphRef::MultiDirected { mdg, .. } => mdg.inner.mode(),
        _ if gr.is_directed() => gr.digraph().expect("is_directed checked above").mode(),
        _ => gr.undirected().mode(),
    };
    let mut tree = crate::digraph::PyDiGraph::new_empty_with_mode(py, tree_mode)?;

    // br-r37-c1-d58s8 tree-assembly tier: mirrors stay LAZY — absent
    // node/edge attr-dict entries are tolerated everywhere (proven by
    // the wholesale-clone converters, which produce none).
    if let Some(sk) = source_key {
        tree.inner.add_node(&sk);
        tree.node_key_map.insert(
            sk,
            source.expect("source_key implies source").clone().unbind(),
        );
    } else {
        for node in gr.nodes_ordered() {
            tree.node_key_map
                .insert(node.to_owned(), gr.py_node_key(py, node));
        }
        let _ = tree.inner.extend_nodes_with_attrs_unrecorded(
            gr.nodes_ordered()
                .into_iter()
                .map(|n| (n.to_owned(), fnx_classes::AttrMap::new())),
        );
    }

    for (u, v) in &edge_list {
        // mirrors for the v endpoints created by the edge walk (u is
        // always already present: it is the source or a previous v).
        // br-r37-c1-wvbzw: nx's tree nodes carry DISCOVERY objects — the
        // parent's adjacency-ROW object (z6uka row overrides), not the
        // node-map object.
        if !tree.node_key_map.contains_key(v) {
            tree.node_key_map.insert(v.clone(), gr.py_row_key(py, u, v));
        }
    }
    // node first-touch creation (u then v) matches the old per-edge
    // add_node sequence; one ledger record for the whole batch.
    let _inserted = tree.inner.extend_edges_unrecorded(edge_list);

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

    let dict = PyDict::new(py);
    let source_key = match source {
        Some(s) => {
            let k = node_key_to_string(py, s)?;
            if !gr.has_node(&k) {
                return Err(NodeNotFound::new_err(format!(
                    "The node {} is not in the graph.",
                    s.str()?
                )));
            }
            Some(k)
        }
        None => None,
    };

    match source_key {
        Some(source_key) => {
            let preds = match &gr {
                GraphRef::Directed { dg, .. } => {
                    let __dg_inner = &dg.inner;
                    py.allow_threads(|| {
                        fnx_algorithms::dfs_predecessors_directed(
                            __dg_inner,
                            &source_key,
                            depth_limit,
                        )
                    })
                }

                GraphRef::Undirected(pg) => {
                    let inner = &pg.inner;

                    py.allow_threads(|| {
                        fnx_algorithms::dfs_predecessors(inner, &source_key, depth_limit)
                    })
                }
                _ => {
                    if gr.is_directed() {
                        let __gr_digraph = gr.digraph().expect("is_directed checked above");
                        py.allow_threads(|| {
                            fnx_algorithms::dfs_predecessors_directed(
                                __gr_digraph,
                                &source_key,
                                depth_limit,
                            )
                        })
                    } else {
                        let inner = gr.undirected();

                        py.allow_threads(|| {
                            fnx_algorithms::dfs_predecessors(inner, &source_key, depth_limit)
                        })
                    }
                }
            };

            for (child, parent) in &preds {
                dict.set_item(gr.py_node_key(py, child), gr.py_node_key(py, parent))?;
            }
        }
        None => {
            let nodes = gr.nodes_ordered();
            if nodes.is_empty() {
                return Ok(dict.unbind());
            }
            let edges = match &gr {
                GraphRef::Directed { dg, .. } => {
                    let __dg_inner = &dg.inner;
                    py.allow_threads(|| dfs_forest_directed(__dg_inner, &nodes, depth_limit).0)
                }
                GraphRef::Undirected(pg) => {
                    let inner = &pg.inner;
                    py.allow_threads(|| dfs_forest_undirected(inner, &nodes, depth_limit).0)
                }
                _ => {
                    if gr.is_directed() {
                        let __gr_digraph = gr.digraph().expect("is_directed checked above");
                        py.allow_threads(|| {
                            dfs_forest_directed(__gr_digraph, &nodes, depth_limit).0
                        })
                    } else {
                        let inner = gr.undirected();
                        py.allow_threads(|| dfs_forest_undirected(inner, &nodes, depth_limit).0)
                    }
                }
            };
            for (parent, child) in &edges {
                dict.set_item(gr.py_node_key(py, child), gr.py_node_key(py, parent))?;
            }
        }
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

    let dict = PyDict::new(py);
    let source_key = match source {
        Some(s) => {
            let k = node_key_to_string(py, s)?;
            if !gr.has_node(&k) {
                return Err(NodeNotFound::new_err(format!(
                    "The node {} is not in the graph.",
                    s.str()?
                )));
            }
            Some(k)
        }
        None => None,
    };

    match source_key {
        Some(source_key) => {
            let succs = match &gr {
                GraphRef::Directed { dg, .. } => {
                    let __dg_inner = &dg.inner;
                    py.allow_threads(|| {
                        fnx_algorithms::dfs_successors_directed(
                            __dg_inner,
                            &source_key,
                            depth_limit,
                        )
                    })
                }

                GraphRef::Undirected(pg) => {
                    let inner = &pg.inner;

                    py.allow_threads(|| {
                        fnx_algorithms::dfs_successors(inner, &source_key, depth_limit)
                    })
                }
                _ => {
                    if gr.is_directed() {
                        let __gr_digraph = gr.digraph().expect("is_directed checked above");
                        py.allow_threads(|| {
                            fnx_algorithms::dfs_successors_directed(
                                __gr_digraph,
                                &source_key,
                                depth_limit,
                            )
                        })
                    } else {
                        let inner = gr.undirected();

                        py.allow_threads(|| {
                            fnx_algorithms::dfs_successors(inner, &source_key, depth_limit)
                        })
                    }
                }
            };

            for (parent, children) in &succs {
                let py_children: Vec<PyObject> =
                    children.iter().map(|c| gr.py_node_key(py, c)).collect();
                dict.set_item(gr.py_node_key(py, parent), py_children)?;
            }
        }
        None => {
            let nodes = gr.nodes_ordered();
            if nodes.is_empty() {
                return Ok(dict.unbind());
            }
            let edges = match &gr {
                GraphRef::Directed { dg, .. } => {
                    let __dg_inner = &dg.inner;
                    py.allow_threads(|| dfs_forest_directed(__dg_inner, &nodes, depth_limit).0)
                }
                GraphRef::Undirected(pg) => {
                    let inner = &pg.inner;
                    py.allow_threads(|| dfs_forest_undirected(inner, &nodes, depth_limit).0)
                }
                _ => {
                    if gr.is_directed() {
                        let __gr_digraph = gr.digraph().expect("is_directed checked above");
                        py.allow_threads(|| {
                            dfs_forest_directed(__gr_digraph, &nodes, depth_limit).0
                        })
                    } else {
                        let inner = gr.undirected();
                        py.allow_threads(|| dfs_forest_undirected(inner, &nodes, depth_limit).0)
                    }
                }
            };
            let mut succs: HashMap<String, Vec<String>> = HashMap::new();
            for (parent, child) in edges {
                succs.entry(parent).or_default().push(child);
            }
            for (parent, children) in &succs {
                let py_children: Vec<PyObject> =
                    children.iter().map(|c| gr.py_node_key(py, c)).collect();
                dict.set_item(gr.py_node_key(py, parent), py_children)?;
            }
        }
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
                    s.str()?
                )));
            }
            Some(k)
        }
        None => None,
    };

    let source_key_for_disp = source_key.clone(); // br-r37-c1-6hpa9
    let nodes = match source_key {
        Some(source_key) => match &gr {
            GraphRef::Directed { dg, .. } => {
                let __dg_inner = &dg.inner;
                py.allow_threads(|| {
                    fnx_algorithms::dfs_preorder_nodes_directed(
                        __dg_inner,
                        &source_key,
                        depth_limit,
                    )
                })
            }

            GraphRef::Undirected(pg) => {
                let inner = &pg.inner;

                py.allow_threads(|| {
                    fnx_algorithms::dfs_preorder_nodes(inner, &source_key, depth_limit)
                })
            }
            _ => {
                if gr.is_directed() {
                    let __gr_digraph = gr.digraph().expect("is_directed checked above");
                    py.allow_threads(|| {
                        fnx_algorithms::dfs_preorder_nodes_directed(
                            __gr_digraph,
                            &source_key,
                            depth_limit,
                        )
                    })
                } else {
                    let inner = gr.undirected();

                    py.allow_threads(|| {
                        fnx_algorithms::dfs_preorder_nodes(inner, &source_key, depth_limit)
                    })
                }
            }
        },
        None => {
            let ordered = gr.nodes_ordered();
            if ordered.is_empty() {
                return Ok(Vec::new());
            }
            match &gr {
                GraphRef::Directed { dg, .. } => {
                    let __dg_inner = &dg.inner;
                    py.allow_threads(|| dfs_forest_directed(__dg_inner, &ordered, depth_limit).1)
                }
                GraphRef::Undirected(pg) => {
                    let inner = &pg.inner;
                    py.allow_threads(|| dfs_forest_undirected(inner, &ordered, depth_limit).1)
                }
                _ => {
                    if gr.is_directed() {
                        let __gr_digraph = gr.digraph().expect("is_directed checked above");
                        py.allow_threads(|| {
                            dfs_forest_directed(__gr_digraph, &ordered, depth_limit).1
                        })
                    } else {
                        let inner = gr.undirected();
                        py.allow_threads(|| dfs_forest_undirected(inner, &ordered, depth_limit).1)
                    }
                }
            }
        }
    };

    // br-r37-c1-6hpa9: nx yields DISCOVERY objects — derive the map from
    // the DFS tree-edge stream (roots fall back to node-map objects).
    let tree_edges = dfs_edges_canonical(py, &gr, source_key_for_disp.clone(), depth_limit);
    let seed = source_key_for_disp
        .as_deref()
        .zip(source)
        .map(|(k, s)| (k, s.clone().unbind()));
    let disp = gr.discovery_map(py, &tree_edges, seed, false);
    Ok(nodes
        .iter()
        .map(|n| gr.disp_or_node_key(py, &disp, n))
        .collect())
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
                    s.str()?
                )));
            }
            Some(k)
        }
        None => None,
    };

    let source_key_for_disp = source_key.clone(); // br-r37-c1-6hpa9
    let nodes = match source_key {
        Some(source_key) => match &gr {
            GraphRef::Directed { dg, .. } => {
                let __dg_inner = &dg.inner;
                py.allow_threads(|| {
                    fnx_algorithms::dfs_postorder_nodes_directed(
                        __dg_inner,
                        &source_key,
                        depth_limit,
                    )
                })
            }

            GraphRef::Undirected(pg) => {
                let inner = &pg.inner;

                py.allow_threads(|| {
                    fnx_algorithms::dfs_postorder_nodes(inner, &source_key, depth_limit)
                })
            }
            _ => {
                if gr.is_directed() {
                    let __gr_digraph = gr.digraph().expect("is_directed checked above");
                    py.allow_threads(|| {
                        fnx_algorithms::dfs_postorder_nodes_directed(
                            __gr_digraph,
                            &source_key,
                            depth_limit,
                        )
                    })
                } else {
                    let inner = gr.undirected();

                    py.allow_threads(|| {
                        fnx_algorithms::dfs_postorder_nodes(inner, &source_key, depth_limit)
                    })
                }
            }
        },
        None => {
            let ordered = gr.nodes_ordered();
            if ordered.is_empty() {
                return Ok(Vec::new());
            }
            match &gr {
                GraphRef::Directed { dg, .. } => {
                    let __dg_inner = &dg.inner;
                    py.allow_threads(|| {
                        dfs_postorder_forest_directed(__dg_inner, &ordered, depth_limit)
                    })
                }
                GraphRef::Undirected(pg) => {
                    let inner = &pg.inner;
                    py.allow_threads(|| {
                        dfs_postorder_forest_undirected(inner, &ordered, depth_limit)
                    })
                }
                _ => {
                    if gr.is_directed() {
                        let __gr_digraph = gr.digraph().expect("is_directed checked above");
                        py.allow_threads(|| {
                            dfs_postorder_forest_directed(__gr_digraph, &ordered, depth_limit)
                        })
                    } else {
                        let inner = gr.undirected();
                        py.allow_threads(|| {
                            dfs_postorder_forest_undirected(inner, &ordered, depth_limit)
                        })
                    }
                }
            }
        }
    };

    // br-r37-c1-6hpa9: nx yields DISCOVERY objects — derive the map from
    // the DFS tree-edge stream (roots fall back to node-map objects).
    let tree_edges = dfs_edges_canonical(py, &gr, source_key_for_disp.clone(), depth_limit);
    let seed = source_key_for_disp
        .as_deref()
        .zip(source)
        .map(|(k, s)| (k, s.clone().unbind()));
    let disp = gr.discovery_map(py, &tree_edges, seed, false);
    Ok(nodes
        .iter()
        .map(|n| gr.disp_or_node_key(py, &disp, n))
        .collect())
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
        match py.allow_threads(|| fnx_algorithms::topological_sort(dg_ref)) {
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
        match py.allow_threads(|| fnx_algorithms::topological_generations(dg_ref)) {
            Some(result) => {
                // re-audit 2026-06-06: generation 0 carries node-map
                // objects (nx reads G.in_degree()); later members carry
                // the ZEROING parent's succ-row object (nx appends the
                // child from the parent's adjacency scan).
                let gens: Vec<Vec<PyObject>> = result
                    .generations
                    .iter()
                    .map(|generation| {
                        generation
                            .iter()
                            .map(|(n, parent)| match parent {
                                Some(p) => gr.py_row_key(py, p, n),
                                None => gr.py_node_key(py, n),
                            })
                            .collect()
                    })
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
/// Matches `networkx.dag_longest_path(G, weight=, default_weight=)`.
/// When ``weight`` is None, falls back to the unweighted hop-count
/// path. When provided, edges are summed via ``edge_attrs[weight]``
/// with ``default_weight`` filling in for missing attribute values.
#[pyfunction]
#[pyo3(signature = (g, weight=None, default_weight=1.0))]
pub fn dag_longest_path(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    weight: Option<&str>,
    default_weight: f64,
) -> PyResult<Vec<PyObject>> {
    if weight.is_some() {
        sync_rust_attrs_if_available(g)?;
    }
    let gr = extract_graph(g)?;
    if !gr.is_directed() {
        return Err(NetworkXError::new_err(
            "dag_longest_path not defined on undirected graphs.",
        ));
    }
    let dg_ref = gr.digraph().expect("is_directed checked above");
    let result = match weight {
        None => py.allow_threads(|| fnx_algorithms::dag_longest_path(dg_ref)),
        Some(w) => py
            .allow_threads(|| fnx_algorithms::dag_longest_path_weighted(dg_ref, w, default_weight)),
    };
    match result {
        Some(path) => Ok(path.iter().map(|n| gr.py_node_key(py, n)).collect()),
        None => Err(crate::HasACycle::new_err("Graph contains a cycle.")),
    }
}

/// Return the length of the longest path in a DAG.
///
/// Matches `networkx.dag_longest_path_length(G, weight=, default_weight=)`.
/// When ``weight`` is None the result is an unweighted hop-count
/// (returned as a Python int). When provided the result is the
/// weighted sum (Python float).
#[pyfunction]
#[pyo3(signature = (g, weight=None, default_weight=1.0))]
pub fn dag_longest_path_length(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    weight: Option<&str>,
    default_weight: f64,
) -> PyResult<PyObject> {
    if weight.is_some() {
        sync_rust_attrs_if_available(g)?;
    }
    let gr = extract_graph(g)?;
    if !gr.is_directed() {
        return Err(NetworkXError::new_err(
            "dag_longest_path_length not defined on undirected graphs.",
        ));
    }
    let dg_ref = gr.digraph().expect("is_directed checked above");
    match weight {
        None => match py.allow_threads(|| fnx_algorithms::dag_longest_path_length(dg_ref)) {
            Some(length) => Ok(length.into_pyobject(py)?.into_any().unbind()),
            None => Err(crate::HasACycle::new_err("Graph contains a cycle.")),
        },
        Some(w) => match py.allow_threads(|| {
            fnx_algorithms::dag_longest_path_length_weighted(dg_ref, w, default_weight)
        }) {
            Some(length) => Ok(length.into_pyobject(py)?.into_any().unbind()),
            None => Err(crate::HasACycle::new_err("Graph contains a cycle.")),
        },
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
        match py.allow_threads(|| fnx_algorithms::lexicographic_topological_sort(dg_ref)) {
            Some(order) => Ok(order.iter().map(|n| gr.py_node_key(py, n)).collect()),
            None => Err(crate::HasACycle::new_err(
                "Graph contains a cycle, topological sort is not possible.",
            )),
        }
    }
}

/// Return True if the directed graph G is a directed acyclic graph (DAG).
#[pyfunction]
pub fn is_directed_acyclic_graph(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<bool> {
    let gr = extract_graph(g)?;
    if !gr.is_directed() {
        return Ok(false);
    }
    if let GraphRef::MultiDirected { mdg, .. } = &gr {
        // br-r37-c1-zid1b2: direct Kahn's over the multidigraph adjacency, no conversion.
        let inner = &mdg.inner;
        return Ok(py.allow_threads(|| multidigraph_is_dag(inner)));
    }
    {
        let dg_ref = gr.digraph().expect("is_directed checked above");
        Ok(py.allow_threads(|| fnx_algorithms::is_directed_acyclic_graph(dg_ref)))
    }
}

/// Return all ancestors of node in the directed graph.
#[pyfunction]
pub fn ancestors(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    source: &Bound<'_, PyAny>,
) -> PyResult<pyo3::Py<pyo3::types::PySet>> {
    let gr = extract_graph(g)?;
    let source_key = node_key_to_string(py, source)?;
    if !gr.has_node(&source_key) {
        let graph_kind = if gr.is_directed() { "digraph" } else { "graph" };
        return Err(NetworkXError::new_err(format!(
            "The node {} is not in the {}.",
            source.str()?,
            graph_kind
        )));
    }

    if !gr.is_directed() {
        let inner = gr.undirected();
        let edges = py.allow_threads(|| fnx_algorithms::bfs_edges(inner, &source_key, None));
        // br-r37-c1-6hpa9: nx's set members carry DISCOVERY objects.
        let disp = gr.discovery_map(
            py,
            &edges,
            Some((&source_key, source.clone().unbind())),
            false,
        );
        let mut result: HashSet<String> = HashSet::new();
        for (u, v) in edges {
            if u != source_key {
                result.insert(u);
            }
            if v != source_key {
                result.insert(v);
            }
        }
        let py_nodes: Vec<PyObject> = result
            .iter()
            .map(|n| gr.disp_or_node_key(py, &disp, n))
            .collect();
        return pyo3::types::PySet::new(py, &py_nodes).map(|s| s.unbind());
    }

    if let GraphRef::MultiDirected { mdg, .. } = &gr {
        // br-r37-c1-zid1b: ancestors via direct predecessor-BFS reverse tree edges.
        let inner = &mdg.inner;
        let edges = py.allow_threads(|| multidigraph_bfs_edges_reverse(inner, &source_key));
        let disp = gr.discovery_map(
            py,
            &edges,
            Some((&source_key, source.clone().unbind())),
            true,
        );
        let mut result: HashSet<String> = HashSet::new();
        for (u, v) in &edges {
            if u != &source_key {
                result.insert(u.clone());
            }
            if v != &source_key {
                result.insert(v.clone());
            }
        }
        let py_nodes: Vec<PyObject> = result
            .iter()
            .map(|n| gr.disp_or_node_key(py, &disp, n))
            .collect();
        return pyo3::types::PySet::new(py, &py_nodes).map(|s| s.unbind());
    }

    {
        // br-r37-c1-6hpa9: nx ancestors walks the REVERSE bfs — members
        // carry pred-row discovery objects. Derive from the reverse tree
        // stream instead of the set-returning kernel.
        let dg_ref = gr.digraph().expect("is_directed checked above");
        let edges = py.allow_threads(|| {
            fnx_algorithms::bfs_edges_directed_reverse(dg_ref, &source_key, None)
        });
        let disp = gr.discovery_map(
            py,
            &edges,
            Some((&source_key, source.clone().unbind())),
            true,
        );
        let mut result: HashSet<String> = HashSet::new();
        for (u, v) in &edges {
            if u != &source_key {
                result.insert(u.clone());
            }
            if v != &source_key {
                result.insert(v.clone());
            }
        }
        let py_nodes: Vec<PyObject> = result
            .iter()
            .map(|n| gr.disp_or_node_key(py, &disp, n))
            .collect();
        pyo3::types::PySet::new(py, &py_nodes).map(|s| s.unbind())
    }
}

/// Return all descendants of node in the directed graph.
#[pyfunction]
pub fn descendants(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    source: &Bound<'_, PyAny>,
) -> PyResult<pyo3::Py<pyo3::types::PySet>> {
    let gr = extract_graph(g)?;
    let source_key = node_key_to_string(py, source)?;
    if !gr.has_node(&source_key) {
        let graph_kind = if gr.is_directed() { "digraph" } else { "graph" };
        return Err(NetworkXError::new_err(format!(
            "The node {} is not in the {}.",
            source.str()?,
            graph_kind
        )));
    }

    if !gr.is_directed() {
        let inner = gr.undirected();
        let edges = py.allow_threads(|| fnx_algorithms::bfs_edges(inner, &source_key, None));
        // br-r37-c1-6hpa9: nx's set members carry DISCOVERY objects.
        let disp = gr.discovery_map(
            py,
            &edges,
            Some((&source_key, source.clone().unbind())),
            false,
        );
        let mut result: HashSet<String> = HashSet::new();
        for (u, v) in edges {
            if u != source_key {
                result.insert(u);
            }
            if v != source_key {
                result.insert(v);
            }
        }
        let py_nodes: Vec<PyObject> = result
            .iter()
            .map(|n| gr.disp_or_node_key(py, &disp, n))
            .collect();
        return pyo3::types::PySet::new(py, &py_nodes).map(|s| s.unbind());
    }

    if let GraphRef::MultiDirected { mdg, .. } = &gr {
        // br-r37-c1-zid1b: descendants via direct successor-BFS tree edges, no conversion.
        let inner = &mdg.inner;
        let edges = py.allow_threads(|| multidigraph_bfs_edges(inner, &source_key));
        let disp = gr.discovery_map(
            py,
            &edges,
            Some((&source_key, source.clone().unbind())),
            false,
        );
        let mut result: HashSet<String> = HashSet::new();
        for (u, v) in &edges {
            if u != &source_key {
                result.insert(u.clone());
            }
            if v != &source_key {
                result.insert(v.clone());
            }
        }
        let py_nodes: Vec<PyObject> = result
            .iter()
            .map(|n| gr.disp_or_node_key(py, &disp, n))
            .collect();
        return pyo3::types::PySet::new(py, &py_nodes).map(|s| s.unbind());
    }

    {
        // br-r37-c1-6hpa9: forward-BFS discovery objects for the members.
        let dg_ref = gr.digraph().expect("is_directed checked above");
        let edges =
            py.allow_threads(|| fnx_algorithms::bfs_edges_directed(dg_ref, &source_key, None));
        let disp = gr.discovery_map(
            py,
            &edges,
            Some((&source_key, source.clone().unbind())),
            false,
        );
        let mut result: HashSet<String> = HashSet::new();
        for (u, v) in &edges {
            if u != &source_key {
                result.insert(u.clone());
            }
            if v != &source_key {
                result.insert(v.clone());
            }
        }
        let py_nodes: Vec<PyObject> = result
            .iter()
            .map(|n| gr.disp_or_node_key(py, &disp, n))
            .collect();
        pyo3::types::PySet::new(py, &py_nodes).map(|s| s.unbind())
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
    let effective_method = method.unwrap_or(if weight.is_some() {
        "dijkstra"
    } else {
        "unweighted"
    });
    let gr = extract_graph(g)?;
    let source_key = node_key_to_string(py, source)?;
    let target_key = node_key_to_string(py, target)?;

    if !gr.has_node(&source_key) {
        let source_name = source.str()?;
        let message = if weight.is_some() && effective_method != "unweighted" {
            format!("Node {source_name} is not found in the graph")
        } else {
            format!("Source {source_name} not in G")
        };
        return Err(NodeNotFound::new_err(message));
    }
    if !gr.has_node(&target_key) {
        return Err(NetworkXNoPath::new_err(format!(
            "Target {} cannot be reached from given sources",
            target.str()?
        )));
    }

    let paths = if gr.is_directed() {
        match (weight, effective_method) {
            (Some(w), "bellman-ford") => {
                let dg_ref = gr.digraph().expect("is_directed checked above");
                let result = py.allow_threads(|| {
                    fnx_algorithms::all_shortest_paths_weighted_directed_bellman_ford(
                        dg_ref,
                        &source_key,
                        &target_key,
                        w,
                    )
                });
                match result {
                    Ok(paths) => paths,
                    Err(()) => {
                        return Err(crate::NetworkXUnbounded::new_err(
                            "Negative cycle detected.",
                        ));
                    }
                }
            }
            (Some(w), "dijkstra") => {
                let dg_ref = gr.digraph().expect("is_directed checked above");
                py.allow_threads(|| {
                    fnx_algorithms::all_shortest_paths_weighted_directed(
                        dg_ref,
                        &source_key,
                        &target_key,
                        w,
                    )
                })
            }
            (Some(w), _) => {
                let dg_ref = gr.digraph().expect("is_directed checked above");
                py.allow_threads(|| {
                    fnx_algorithms::all_shortest_paths_weighted_directed(
                        dg_ref,
                        &source_key,
                        &target_key,
                        w,
                    )
                })
            }
            (None, _) => {
                let dg_ref = gr.digraph().expect("is_directed checked above");
                py.allow_threads(|| {
                    fnx_algorithms::all_shortest_paths_directed(dg_ref, &source_key, &target_key)
                })
            }
        }
    } else {
        let inner = gr.undirected();
        match (weight, effective_method) {
            (Some(w), "bellman-ford") => {
                let result = py.allow_threads(|| {
                    fnx_algorithms::all_shortest_paths_weighted_bellman_ford(
                        inner,
                        &source_key,
                        &target_key,
                        w,
                    )
                });
                match result {
                    Ok(paths) => paths,
                    Err(()) => {
                        return Err(crate::NetworkXUnbounded::new_err(
                            "Negative cycle detected.",
                        ));
                    }
                }
            }
            (Some(w), _) => py.allow_threads(|| {
                fnx_algorithms::all_shortest_paths_weighted(inner, &source_key, &target_key, w)
            }),
            (None, "unweighted") | (None, _) => py.allow_threads(|| {
                fnx_algorithms::all_shortest_paths(inner, &source_key, &target_key)
            }),
        }
    };

    if paths.is_empty() {
        return Err(NetworkXNoPath::new_err(format!(
            "Target {} cannot be reached from given sources",
            target.str()?
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
        // br-r37-c1-4jd8m: skip the intermediate result Graph that the
        // legacy ``fnx_algorithms::complement`` materialized — its
        // per-edge ``Graph::add_edge`` chain (with runtime_policy
        // record_decision allocations) doubled the wall time of
        // ``fnx.complement`` because the binding then re-inserted
        // every edge into the PyGraph. The new ``complement_edges``
        // pre-computes the canonical (u, v) pairs once; the binding
        // does the single PyGraph insertion pass.
        let nodes_owned: Vec<String> = pg
            .inner
            .nodes_ordered()
            .into_iter()
            .map(str::to_owned)
            .collect();
        let edges = {
            let __pg_inner = &pg.inner;
            py.allow_threads(|| fnx_algorithms::complement_edges(__pg_inner))
        };

        let mut py_graph = PyGraph::new_empty_with_policy(py, pg.inner.runtime_policy().clone())?;
        for node in &nodes_owned {
            let py_key = pg.py_node_key(py, node);
            py_graph.node_key_map.insert(node.clone(), py_key);
            py_graph
                .node_py_attrs
                .insert(node.clone(), pyo3::types::PyDict::new(py).unbind());
            py_graph.inner.add_node(node);
        }
        // br-r37-c1-4jd8m: bulk insertion via extend_edges_unrecorded
        // skips per-edge runtime_policy.record_decision overhead. For
        // BA1000 complement this avoids hundreds of thousands of hot
        // path policy-log records; one summary record covers the batch.
        let inserted = py_graph
            .inner
            .extend_edges_unrecorded(edges.iter().map(|(l, r)| (l.as_str(), r.as_str())));
        debug_assert_eq!(inserted, edges.len());
        // br-r37-c1-complazy: do NOT eagerly allocate an empty PyDict per
        // complement edge — the complement carries no edge data, and
        // `materialize_edge_py_attrs` (used by every `G[u][v]` / edges(data=True)
        // / to_dict_of_dicts path) lazily `or_insert_with(PyDict::new)` on first
        // access, returning the same shared object thereafter (so `G[u][v] is
        // G[u][v]` identity holds). The eager loop allocated O(V^2) PyDicts +
        // edge-key String tuples for the dense complement result — the dominant
        // construction tax. Lazy materialisation is byte-identical.

        Ok(py_graph.into_pyobject(py)?.into_any().unbind())
    } else if let Ok(dg) = g.extract::<PyRef<'_, PyDiGraph>>() {
        // br-r37-c1-4jd8m: same one-pass insertion as the Graph branch.
        let nodes_owned: Vec<String> = dg
            .inner
            .nodes_ordered()
            .into_iter()
            .map(str::to_owned)
            .collect();
        let edges = {
            let __dg_inner = &dg.inner;
            py.allow_threads(|| fnx_algorithms::complement_edges_directed(__dg_inner))
        };

        let mut py_dg = PyDiGraph::new_empty_with_policy(py, dg.inner.runtime_policy().clone())?;
        for node in &nodes_owned {
            let py_key = dg.py_node_key(py, node);
            py_dg.node_key_map.insert(node.clone(), py_key);
            py_dg
                .node_py_attrs
                .insert(node.clone(), pyo3::types::PyDict::new(py).unbind());
            py_dg.inner.add_node(node);
        }
        let inserted = py_dg
            .inner
            .extend_edges_unrecorded(edges.iter().map(|(l, r)| (l.as_str(), r.as_str())));
        debug_assert_eq!(inserted, edges.len());
        // br-r37-c1-complazy: skip the O(V^2) eager empty-PyDict-per-edge
        // allocation — lazy `materialize_edge_py_attrs` covers every attr access
        // path byte-identically (see the Graph branch above).

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
    for &(k, v) in &result {
        dict.set_item(k, v)?;
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
    // br-r37-c1-cfsoi: build per-source paths over integer adjacency in
    // BFS-discovery order natively (mirrors all_pairs_shortest_path_length's
    // ordered path). The previous binding collected the kernel's
    // `HashMap<String, HashMap<String, _>>`, which loses BFS-visit order, and
    // the Python wrapper paid a full re-BFS (`_bfs_visit_order`) per source to
    // recover nx's inner-dict key order — an 8-10x tax. Emitting in discovery
    // order here lets the wrapper yield directly.
    let gr = extract_graph(g)?;
    let (nodes, result) = if gr.is_directed() {
        let inner = gr.digraph().expect("is_directed checked above");
        let nodes = inner.nodes_ordered();
        let adjacency = digraph_shortest_path_adjacency_indices(inner, &nodes);
        let result =
            py.allow_threads(|| all_pairs_shortest_path_from_adjacency(&adjacency, cutoff));
        (nodes, result)
    } else {
        let inner = gr.undirected();
        let nodes = inner.nodes_ordered();
        let adjacency = graph_shortest_path_adjacency_indices(inner, &nodes);
        let result =
            py.allow_threads(|| all_pairs_shortest_path_from_adjacency(&adjacency, cutoff));
        (nodes, result)
    };
    let outer_dict = pyo3::types::PyDict::new(py);
    for (source, paths) in &result {
        // br-r37-c1-6hpa9: discovery objects per source; sources keep their
        // node-map object (nx iterates G). `paths` is already in BFS-visit
        // order, so emit_paths_dict_discovery preserves nx's inner key order.
        let target_paths: Vec<(String, Vec<String>)> = paths
            .iter()
            .map(|(target, path)| {
                (
                    nodes[*target].to_owned(),
                    path.iter().map(|&idx| nodes[idx].to_owned()).collect(),
                )
            })
            .collect();
        let source_key = nodes[*source];
        let inner_dict = emit_paths_dict_discovery(
            py,
            &gr,
            &target_paths,
            source_key,
            gr.py_node_key(py, source_key),
        )?;
        outer_dict.set_item(gr.py_node_key(py, source_key), inner_dict)?;
    }
    Ok(outer_dict.into_any().unbind())
}

/// BFS from every source over an integer adjacency list, returning per-source
/// `(source, [(target, path)])` with targets in BFS-discovery order (matching
/// `networkx.single_source_shortest_path`'s dict-insertion order). Paths are
/// reconstructed from a predecessor array so each target's path is the BFS-tree
/// path (the first predecessor that discovers it), identical to nx's
/// `paths[w] = paths[v] + [w]`.
fn all_pairs_shortest_path_from_adjacency(
    adjacency: &[Vec<usize>],
    cutoff: Option<usize>,
) -> Vec<(usize, Vec<(usize, Vec<usize>)>)> {
    let node_count = adjacency.len();
    let mut result = Vec::with_capacity(node_count);
    let mut seen_epoch = vec![0usize; node_count];
    let mut pred = vec![0usize; node_count];
    let mut frontier = Vec::with_capacity(node_count);
    let mut next_frontier = Vec::with_capacity(node_count);
    let mut epoch = 1usize;

    for source in 0..node_count {
        let mut order: Vec<usize> = Vec::with_capacity(node_count);
        frontier.clear();
        next_frontier.clear();
        seen_epoch[source] = epoch;
        pred[source] = source;
        frontier.push(source);
        order.push(source);

        let mut level = 0usize;
        while !frontier.is_empty() {
            if let Some(c) = cutoff
                && level >= c
            {
                break;
            }
            next_frontier.clear();
            for &node in &frontier {
                for &neighbor in &adjacency[node] {
                    if seen_epoch[neighbor] != epoch {
                        seen_epoch[neighbor] = epoch;
                        pred[neighbor] = node;
                        order.push(neighbor);
                        next_frontier.push(neighbor);
                    }
                }
            }
            std::mem::swap(&mut frontier, &mut next_frontier);
            level += 1;
        }

        // Reconstruct each target's path in discovery order via the pred chain.
        let mut paths = Vec::with_capacity(order.len());
        for &target in &order {
            let mut rev = Vec::new();
            let mut cur = target;
            loop {
                rev.push(cur);
                if cur == source {
                    break;
                }
                cur = pred[cur];
            }
            rev.reverse();
            paths.push((target, rev));
        }

        result.push((source, paths));
        epoch = epoch.saturating_add(1);
        if epoch == usize::MAX {
            seen_epoch.fill(0);
            epoch = 1;
        }
    }

    result
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
    let (nodes, result) = if gr.is_directed() {
        let inner = gr.digraph().expect("is_directed checked above");
        let nodes = inner.nodes_ordered();
        let result = py.allow_threads(|| {
            all_pairs_shortest_path_length_directed_ordered(inner, &nodes, cutoff)
        });
        (nodes, result)
    } else {
        let inner = gr.undirected();
        let nodes = inner.nodes_ordered();
        let result =
            py.allow_threads(|| all_pairs_shortest_path_length_ordered(inner, &nodes, cutoff));
        (nodes, result)
    };
    let outer_dict = pyo3::types::PyDict::new(py);
    for (source, targets) in result {
        let inner_dict = pyo3::types::PyDict::new(py);
        for (target, length) in targets {
            inner_dict.set_item(gr.py_node_key(py, nodes[target]), length)?;
        }
        outer_dict.set_item(gr.py_node_key(py, nodes[source]), inner_dict)?;
    }
    Ok(outer_dict.into_any().unbind())
}

fn all_pairs_shortest_path_length_ordered(
    graph: &fnx_classes::Graph,
    nodes: &[&str],
    cutoff: Option<usize>,
) -> Vec<(usize, Vec<(usize, usize)>)> {
    let adjacency = graph_shortest_path_adjacency_indices(graph, nodes);
    all_pairs_shortest_path_length_from_adjacency(&adjacency, cutoff)
}

fn graph_shortest_path_adjacency_indices(
    graph: &fnx_classes::Graph,
    nodes: &[&str],
) -> Vec<Vec<usize>> {
    let node_indices: HashMap<&str, usize> = nodes
        .iter()
        .copied()
        .enumerate()
        .map(|(index, node)| (node, index))
        .collect();
    nodes
        .iter()
        .map(|&node| {
            graph
                .neighbors_iter(node)
                .map_or_else(Vec::new, |neighbors| {
                    neighbors
                        .filter_map(|neighbor| node_indices.get(neighbor).copied())
                        .collect()
                })
        })
        .collect()
}

fn all_pairs_shortest_path_length_directed_ordered(
    digraph: &fnx_classes::digraph::DiGraph,
    nodes: &[&str],
    cutoff: Option<usize>,
) -> Vec<(usize, Vec<(usize, usize)>)> {
    let adjacency = digraph_shortest_path_adjacency_indices(digraph, nodes);
    all_pairs_shortest_path_length_from_adjacency(&adjacency, cutoff)
}

fn digraph_shortest_path_adjacency_indices(
    digraph: &fnx_classes::digraph::DiGraph,
    nodes: &[&str],
) -> Vec<Vec<usize>> {
    let node_indices: HashMap<&str, usize> = nodes
        .iter()
        .copied()
        .enumerate()
        .map(|(index, node)| (node, index))
        .collect();
    nodes
        .iter()
        .map(|&node| {
            digraph
                .successors_iter(node)
                .map_or_else(Vec::new, |successors| {
                    successors
                        .filter_map(|successor| node_indices.get(successor).copied())
                        .collect()
                })
        })
        .collect()
}

fn all_pairs_shortest_path_length_from_adjacency(
    adjacency: &[Vec<usize>],
    cutoff: Option<usize>,
) -> Vec<(usize, Vec<(usize, usize)>)> {
    let node_count = adjacency.len();
    let mut result = Vec::with_capacity(node_count);
    let mut seen_epoch = vec![0usize; node_count];
    let mut frontier = Vec::with_capacity(node_count);
    let mut next_frontier = Vec::with_capacity(node_count);
    let mut epoch = 1usize;

    for source in 0..node_count {
        let mut lengths = Vec::with_capacity(node_count);
        frontier.clear();
        next_frontier.clear();
        seen_epoch[source] = epoch;
        frontier.push(source);
        lengths.push((source, 0));

        let mut level = 0usize;
        while !frontier.is_empty() {
            if let Some(c) = cutoff
                && level >= c
            {
                break;
            }
            next_frontier.clear();
            for &node in &frontier {
                for &neighbor in &adjacency[node] {
                    if seen_epoch[neighbor] != epoch {
                        seen_epoch[neighbor] = epoch;
                        lengths.push((neighbor, level + 1));
                        next_frontier.push(neighbor);
                    }
                }
            }
            std::mem::swap(&mut frontier, &mut next_frontier);
            level += 1;
        }

        result.push((source, lengths));
        epoch = epoch.saturating_add(1);
        if epoch == usize::MAX {
            seen_epoch.fill(0);
            epoch = 1;
        }
    }

    result
}

// ===========================================================================
// Graph Predicates & Utilities
// ===========================================================================

/// Return whether the graph has no edges.
#[pyfunction]
pub fn is_empty(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<bool> {
    let gr = extract_graph(g)?;
    match &gr {
        GraphRef::Undirected(pg) => {
            let inner = &pg.inner;
            Ok(py.allow_threads(|| fnx_algorithms::is_empty(inner)))
        }
        GraphRef::Directed { dg, .. } => {
            let inner = &dg.inner;
            Ok(py.allow_threads(|| fnx_algorithms::is_empty_directed(inner)))
        }
        _ => {
            if gr.is_directed() {
                let inner = gr.digraph().expect("is_directed checked above");
                Ok(py.allow_threads(|| fnx_algorithms::is_empty_directed(inner)))
            } else {
                let inner = gr.undirected();
                Ok(py.allow_threads(|| fnx_algorithms::is_empty(inner)))
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
    let result = py.allow_threads(|| fnx_algorithms::non_neighbors(inner, &node_key));
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
    // br-r37-c1-eaclidx: the core returns cliques as node INDICES. Each node
    // appears in many cliques, so resolve every Python node object exactly once
    // (then a refcount bump per clique membership) instead of re-running
    // ``py_node_key`` for every node of every clique and materializing a
    // ``String`` per clique-node in the kernel.
    let idx_cliques = py.allow_threads(|| fnx_algorithms::enumerate_all_cliques_index(inner));
    let names = inner.nodes_ordered();
    let mut cache: Vec<Option<PyObject>> = (0..names.len()).map(|_| None).collect();
    let mut out: Vec<Vec<PyObject>> = Vec::with_capacity(idx_cliques.len());
    for clique in &idx_cliques {
        let mut row: Vec<PyObject> = Vec::with_capacity(clique.len());
        for &i in clique {
            if cache[i].is_none() {
                cache[i] = Some(gr.py_node_key(py, names[i]));
            }
            row.push(cache[i].as_ref().expect("cached above").clone_ref(py));
        }
        out.push(row);
    }
    Ok(out)
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

/// Return the n-dimensional grid graph.
///
/// The dimension n is the length of `dim` and the size in each dimension
/// is the value of the corresponding list element.
#[pyfunction]
#[pyo3(signature = (dim,))]
pub fn grid_graph(py: Python<'_>, dim: Vec<usize>) -> PyResult<PyObject> {
    let result = py.allow_threads(|| fnx_algorithms::grid_graph(&dim));
    rust_graph_to_py_standalone(py, &result)
}

/// Return the Dorogovtsev-Goltsev-Mendes graph.
///
/// A hierarchically constructed scale-free graph with deterministic structure.
/// After n generations: (3^n + 3)/2 nodes, 3^n edges.
#[pyfunction]
#[pyo3(signature = (n,))]
pub fn dorogovtsev_goltsev_mendes_graph(py: Python<'_>, n: usize) -> PyResult<PyObject> {
    let result = py
        .allow_threads(|| fnx_algorithms::dorogovtsev_goltsev_mendes_graph(n))
        .map_err(NetworkXError::new_err)?;
    rust_graph_to_py_standalone(py, &result)
}

#[pyfunction]
pub fn null_graph(py: Python<'_>) -> PyResult<PyObject> {
    let result = py.allow_threads(fnx_algorithms::null_graph);
    rust_graph_to_py_standalone(py, &result)
}

#[pyfunction]
pub fn trivial_graph(py: Python<'_>) -> PyResult<PyObject> {
    let result = py.allow_threads(fnx_algorithms::trivial_graph);
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

/// Return the n-Sudoku graph.
///
/// The n-Sudoku graph has n^4 vertices (cells of an n^2 × n^2 grid).
/// Two cells are adjacent iff they share a row, column, or n×n box.
#[pyfunction]
#[pyo3(signature = (n=3))]
pub fn sudoku_graph(py: Python<'_>, n: usize) -> PyResult<PyObject> {
    let result = py.allow_threads(|| fnx_algorithms::sudoku_graph(n));
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
    let source_key = node_key_to_string(py, source)?;
    // br-r37-c1-6hpa9: kernel (BFS) order + discovery objects.
    if gr.is_directed() {
        let inner = gr.digraph().expect("is_directed checked above");
        let result = py.allow_threads(|| {
            fnx_algorithms::single_source_shortest_path_directed(inner, &source_key, cutoff)
        });
        let dict =
            emit_paths_dict_discovery(py, &gr, &result, &source_key, source.clone().unbind())?;
        return Ok(dict.into_any());
    }
    // br-r37-c1-ubizp: MultiGraph builds paths via direct-adjacency BFS instead of
    // the gr.undirected() simple-Graph conversion (was ~25x slower).
    if let GraphRef::MultiUndirected { mg, .. } = &gr {
        let inner = &mg.inner;
        let paths = py.allow_threads(|| multigraph_sssp_paths(inner, &source_key, cutoff));
        let dict =
            emit_paths_dict_discovery(py, &gr, &paths, &source_key, source.clone().unbind())?;
        return Ok(dict.into_any());
    }
    // br-r37-c1-ssspidx: undirected path returns node INDICES from the kernel and
    // resolves them once here, skipping the per-path-node String materialization.
    let inner = gr.undirected();
    let idx_paths = py.allow_threads(|| {
        fnx_algorithms::single_source_shortest_path_index(inner, &source_key, cutoff)
    });
    let nodes = inner.nodes_ordered();
    let source_idx = inner.get_node_index(&source_key).unwrap_or(usize::MAX);
    let dict = emit_paths_dict_discovery_index(
        py,
        &gr,
        &idx_paths,
        &nodes,
        source_idx,
        source.clone().unbind(),
    )?;
    Ok(dict.into_any())
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
    let source_key = node_key_to_string(py, source)?;
    let dict = pyo3::types::PyDict::new(py);
    // br-r37-c1-6hpa9: nx's dict keys carry DISCOVERY objects — the source
    // as passed, every other node as its discovering parent's
    // adjacency-row object. The _with_parents kernels emit the parent for
    // free (no second walk).
    if gr.is_directed() {
        if let GraphRef::MultiDirected { mdg, .. } = &gr {
            // br-r37-c1-zid1b: BFS directly over the multidigraph successor adjacency
            // instead of building a full simple DiGraph first (was ~33x slower).
            let inner = &mdg.inner;
            let result = py.allow_threads(|| {
                multidigraph_sssp_length_with_parents(inner, &source_key, cutoff)
            });
            for (node, length, parent) in &result {
                let key = match parent {
                    Some(p) => gr.py_row_key(py, p, node),
                    None => source.clone().unbind(),
                };
                dict.set_item(key, *length)?;
            }
        } else {
            let inner = gr.digraph().expect("is_directed checked above");
            let result = py.allow_threads(|| {
                fnx_algorithms::single_source_shortest_path_length_directed_with_parents(
                    inner,
                    &source_key,
                    cutoff,
                )
            });
            for (node, length, parent) in &result {
                let key = match parent {
                    Some(p) => gr.py_row_key(py, p, node),
                    None => source.clone().unbind(),
                };
                dict.set_item(key, *length)?;
            }
        }
    } else if let GraphRef::MultiUndirected { mg, .. } = &gr {
        // br-r37-c1-fyxma3: BFS directly over the multigraph adjacency instead of
        // building a full simple Graph first (was ~33x slower than the Graph path).
        let inner = &mg.inner;
        let result =
            py.allow_threads(|| multigraph_sssp_length_with_parents(inner, &source_key, cutoff));
        for (node, length, parent) in &result {
            let key = match parent {
                Some(p) => gr.py_row_key(py, p, node),
                None => source.clone().unbind(),
            };
            dict.set_item(key, *length)?;
        }
    } else {
        let inner = gr.undirected();
        let result = py.allow_threads(|| {
            fnx_algorithms::single_source_shortest_path_length_with_parents_borrowed(
                inner,
                &source_key,
                cutoff,
            )
        });
        for (node, length, parent) in &result {
            let key = match parent {
                Some(p) => gr.py_row_key(py, p, node),
                None => source.clone().unbind(),
            };
            dict.set_item(key, *length)?;
        }
    };
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
    Ok(py.allow_threads(|| fnx_algorithms::is_dominating_set(inner, &refs)))
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
    let result = py.allow_threads(|| strongly_connected_components_nx_ordered(dg_ref));
    result
        .iter()
        .map(|comp| {
            let py_nodes: Vec<PyObject> =
                comp.iter().map(|node| gr.py_node_key(py, node)).collect();
            pyo3::types::PySet::new(py, py_nodes).map(|set| set.into_any().unbind())
        })
        .collect()
}

fn strongly_connected_components_nx_ordered(
    digraph: &fnx_classes::digraph::DiGraph,
) -> Vec<Vec<String>> {
    let nodes = digraph.nodes_ordered();
    let node_indices: HashMap<&str, usize> = nodes
        .iter()
        .copied()
        .enumerate()
        .map(|(index, node)| (node, index))
        .collect();
    let mut predecessors = vec![Vec::<usize>::new(); nodes.len()];
    let successors: Vec<Vec<usize>> = nodes
        .iter()
        .enumerate()
        .map(|(index, &node)| {
            digraph.successors_iter(node).map_or_else(Vec::new, |iter| {
                iter.filter_map(|succ| {
                    let succ_index = node_indices.get(succ).copied()?;
                    predecessors[succ_index].push(index);
                    Some(succ_index)
                })
                .collect()
            })
        })
        .collect();

    if nodes.is_empty() {
        return Vec::new();
    }
    if reaches_every_node(0, &successors) && reaches_every_node(0, &predecessors) {
        return vec![nodes.into_iter().map(str::to_owned).collect()];
    }

    let mut preorder = vec![0usize; nodes.len()];
    let mut lowlink = vec![0usize; nodes.len()];
    let mut scc_found = vec![false; nodes.len()];
    let mut scc_queue = Vec::<usize>::new();
    let mut neighbor_pos = vec![0usize; nodes.len()];
    let mut preorder_counter = 0usize;
    let mut result = Vec::new();

    for source in 0..nodes.len() {
        if scc_found[source] {
            continue;
        }
        let mut queue = vec![source];
        while let Some(&v) = queue.last() {
            if preorder[v] == 0 {
                preorder_counter += 1;
                preorder[v] = preorder_counter;
            }

            let mut done = true;
            while neighbor_pos[v] < successors[v].len() {
                let w = successors[v][neighbor_pos[v]];
                neighbor_pos[v] += 1;
                if preorder[w] == 0 {
                    queue.push(w);
                    done = false;
                    break;
                }
            }

            if done {
                lowlink[v] = preorder[v];
                for &w in &successors[v] {
                    if !scc_found[w] {
                        if preorder[w] > preorder[v] {
                            lowlink[v] = lowlink[v].min(lowlink[w]);
                        } else {
                            lowlink[v] = lowlink[v].min(preorder[w]);
                        }
                    }
                }
                queue.pop();
                if lowlink[v] == preorder[v] {
                    let mut component_indices = vec![v];
                    while scc_queue
                        .last()
                        .is_some_and(|&queued| preorder[queued] > preorder[v])
                    {
                        if let Some(queued) = scc_queue.pop() {
                            component_indices.push(queued);
                        }
                    }
                    for &idx in &component_indices {
                        scc_found[idx] = true;
                    }
                    let component = component_indices
                        .into_iter()
                        .map(|idx| nodes[idx].to_owned())
                        .collect();
                    result.push(component);
                } else {
                    scc_queue.push(v);
                }
            }
        }
    }

    result
}

fn reaches_every_node(source: usize, adjacency: &[Vec<usize>]) -> bool {
    let mut visited = vec![false; adjacency.len()];
    let mut stack = vec![source];
    visited[source] = true;
    let mut seen = 1usize;

    while let Some(node) = stack.pop() {
        for &neighbor in &adjacency[node] {
            if !visited[neighbor] {
                visited[neighbor] = true;
                seen += 1;
                stack.push(neighbor);
            }
        }
    }

    seen == adjacency.len()
}

/// Return the number of strongly connected components.
#[pyfunction]
pub fn number_strongly_connected_components(
    py: Python<'_>,
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
        Ok(py.allow_threads(|| fnx_algorithms::number_strongly_connected_components(dg_ref)))
    }
}

/// Return whether the directed graph is strongly connected.
#[pyfunction]
pub fn is_strongly_connected(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<bool> {
    let gr = extract_graph(g)?;
    if !gr.is_directed() {
        return Err(crate::NetworkXNotImplemented::new_err(
            "is_strongly_connected is not defined for undirected graphs. Use is_connected instead.",
        ));
    }
    if let GraphRef::MultiDirected { mdg, .. } = &gr {
        // br-r37-c1-zid1b: direct forward+reverse reachability over the multidigraph
        // adjacency instead of building a simple DiGraph first (was ~50x slower).
        let inner = &mdg.inner;
        if inner.nodes_ordered().is_empty() {
            return Err(crate::NetworkXPointlessConcept::new_err(
                "Connectivity is undefined for the null graph.",
            ));
        }
        return Ok(py.allow_threads(|| multidigraph_is_strongly_connected(inner)));
    }
    {
        let dg_ref = gr.digraph().expect("is_directed checked above");
        if dg_ref.node_count() == 0 {
            return Err(crate::NetworkXPointlessConcept::new_err(
                "Connectivity is undefined for the null graph.",
            ));
        }
        Ok(py.allow_threads(|| strongly_connected_via_reachability(dg_ref)))
    }
}

/// br-r37-c1-04z53: a digraph is strongly connected iff, from any single
/// vertex, every vertex is reachable following edges FORWARD and every vertex
/// can reach it (i.e. is reachable following edges BACKWARD). Two index-space
/// traversals with early-exit on the forward pass — O(V+E), and bails on the
/// first pass for the common not-strongly-connected case. The previous kernel
/// (`number_strongly_connected_components == 1`) computed the FULL SCC
/// decomposition, labelling every component before counting, which was ~2x
/// slower than nx's `len(next(strongly_connected_components(G))) == len(G)`
/// (nx stops after the first, often size-1, SCC). Boolean output is
/// order-invariant, so this matches nx exactly. `node_count() > 0` is
/// guaranteed by the caller.
fn strongly_connected_via_reachability(dg: &fnx_classes::digraph::DiGraph) -> bool {
    let n = dg.node_count();
    let mut seen = vec![false; n];
    let mut stack: Vec<usize> = Vec::with_capacity(n);

    // Forward reachability from node 0; bail the instant it cannot reach all.
    seen[0] = true;
    stack.push(0);
    let mut count = 1usize;
    while let Some(u) = stack.pop() {
        if let Some(succs) = dg.successors_indices(u) {
            for &v in succs {
                if !seen[v] {
                    seen[v] = true;
                    count += 1;
                    stack.push(v);
                }
            }
        }
    }
    if count != n {
        return false;
    }

    // Backward reachability from node 0 (forward over the transpose).
    for s in &mut seen {
        *s = false;
    }
    seen[0] = true;
    stack.push(0);
    count = 1;
    while let Some(u) = stack.pop() {
        if let Some(preds) = dg.predecessors_indices(u) {
            for &v in preds {
                if !seen[v] {
                    seen[v] = true;
                    count += 1;
                    stack.push(v);
                }
            }
        }
    }
    count == n
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
        let (cond_graph, node_mapping) = py.allow_threads(|| fnx_algorithms::condensation(dg_ref));
        // Build the condensation DiGraph
        let mut py_dg = PyDiGraph::new_empty_with_policy(py, dg_ref.runtime_policy().clone())?;
        for node in cond_graph.nodes_ordered() {
            py_dg.node_key_map.insert(
                node.to_owned(),
                node.parse::<i64>()
                    .expect("is_directed checked above")
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

/// Build `condensation(G)` with NetworkX-compatible SCC labels in one native pass.
#[pyfunction]
pub fn condensation_nx_ordered(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<PyObject> {
    let gr = extract_graph(g)?;
    if !gr.is_directed() {
        return Err(crate::NetworkXNotImplemented::new_err(
            "condensation is not defined for undirected graphs.",
        ));
    }

    let dg_ref = gr.digraph().expect("is_directed checked above");
    let components = py.allow_threads(|| strongly_connected_components_nx_ordered(dg_ref));

    let mut py_dg = PyDiGraph::new_empty_with_policy(py, dg_ref.runtime_policy().clone())?;
    let mapping = PyDict::new(py);
    // br-r37-c1-cond-csr: index the SCC map by integer node index (Vec) instead
    // of hashing the String endpoints per edge.
    let n = dg_ref.node_count();
    let mut scc_of = vec![usize::MAX; n];

    for (idx, component) in components.iter().enumerate() {
        let label = idx.to_string();
        let py_nodes: Vec<PyObject> = component
            .iter()
            .map(|node| gr.py_node_key(py, node))
            .collect();
        let members = PySet::new(py, py_nodes)?;
        let attrs = PyDict::new(py);
        attrs.set_item("members", members)?;
        py_dg
            .node_key_map
            .insert(label.clone(), idx.into_pyobject(py)?.into_any().unbind());
        py_dg.node_py_attrs.insert(label, attrs.unbind());

        for node in component {
            if let Some(ni) = dg_ref.get_node_index(node) {
                scc_of[ni] = idx;
            }
            mapping.set_item(gr.py_node_key(py, node), idx)?;
        }
    }

    for idx in 0..components.len() {
        py_dg.inner.add_node(idx.to_string());
    }

    // br-r37-c1-cond-csr: walk the integer successor rows in source-major order
    // (exactly nx's ``for u, v in G.edges()`` order) instead of
    // ``edges_ordered()``, which clones every edge's AttrMap. Same edge set,
    // same first-seen dedup, same order -> byte-identical condensation DAG.
    let mut seen = HashSet::new();
    let mut cond_edges = Vec::new();
    for u_idx in 0..n {
        let cu = scc_of[u_idx];
        let Some(succs) = dg_ref.successors_indices(u_idx) else {
            continue;
        };
        for &v_idx in succs {
            let cv = scc_of[v_idx];
            if cu == cv || !seen.insert((cu, cv)) {
                continue;
            }
            let left = cu.to_string();
            let right = cv.to_string();
            py_dg
                .edge_py_attrs
                .insert((left.clone(), right.clone()), PyDict::new(py).unbind());
            cond_edges.push((left, right));
        }
    }
    let _ = py_dg.inner.extend_edges_unrecorded(cond_edges);
    py_dg.graph_attrs.bind(py).set_item("mapping", mapping)?;

    Ok(py_dg.into_pyobject(py)?.into_any().unbind())
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
    if let GraphRef::MultiDirected { mdg, .. } = &gr {
        // br-r37-c1-zid1b: direct undirected BFS over the multidigraph adjacency.
        let inner = &mdg.inner;
        let result = py.allow_threads(|| multidigraph_weak_components_borrowed(inner));
        return result
            .iter()
            .map(|comp| {
                let py_set: Vec<PyObject> = comp.iter().map(|n| gr.py_node_key(py, n)).collect();
                py_set.into_pyobject(py).map(|obj| obj.into_any().unbind())
            })
            .collect();
    }
    {
        let dg_ref = gr.digraph().expect("is_directed checked above");
        let result = py.allow_threads(|| fnx_algorithms::weakly_connected_components(dg_ref));
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
pub fn number_weakly_connected_components(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<usize> {
    let gr = extract_graph(g)?;
    if !gr.is_directed() {
        return Err(crate::NetworkXNotImplemented::new_err(
            "number_weakly_connected_components is not defined for undirected graphs.",
        ));
    }
    if let GraphRef::MultiDirected { mdg, .. } = &gr {
        let inner = &mdg.inner;
        return Ok(py.allow_threads(|| multidigraph_weak_components_borrowed(inner).len()));
    }
    {
        let dg_ref = gr.digraph().expect("is_directed checked above");
        Ok(py.allow_threads(|| fnx_algorithms::number_weakly_connected_components(dg_ref)))
    }
}

/// Return whether the directed graph is weakly connected.
#[pyfunction]
pub fn is_weakly_connected(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<bool> {
    let gr = extract_graph(g)?;
    if !gr.is_directed() {
        return Err(crate::NetworkXNotImplemented::new_err(
            "is_weakly_connected is not defined for undirected graphs. Use is_connected instead.",
        ));
    }
    if let GraphRef::MultiDirected { mdg, .. } = &gr {
        let inner = &mdg.inner;
        if inner.nodes_ordered().is_empty() {
            return Err(crate::NetworkXPointlessConcept::new_err(
                "Connectivity is undefined for the null graph.",
            ));
        }
        return Ok(py.allow_threads(|| multidigraph_is_weakly_connected(inner)));
    }
    {
        let dg_ref = gr.digraph().expect("is_directed checked above");
        if dg_ref.node_count() == 0 {
            return Err(crate::NetworkXPointlessConcept::new_err(
                "Connectivity is undefined for the null graph.",
            ));
        }
        Ok(py.allow_threads(|| fnx_algorithms::is_weakly_connected(dg_ref)))
    }
}

// ===========================================================================
// Transitive Closure / Reduction
// ===========================================================================

/// Return the transitive closure of a directed graph.
#[pyfunction]
#[pyo3(signature = (g, reflexive=false))]
pub fn transitive_closure(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    reflexive: bool,
) -> PyResult<PyObject> {
    let gr = extract_graph(g)?;
    if !gr.is_directed() {
        return Err(crate::NetworkXNotImplemented::new_err(
            "transitive_closure is not defined for undirected graphs.",
        ));
    }
    {
        let dg_ref = gr.digraph().expect("is_directed checked above");
        let result =
            py.allow_threads(|| fnx_algorithms::transitive_closure(dg_ref, Some(reflexive)));
        // br-r37-c1-tc-cyclic: move the kernel's closure DiGraph straight into
        // the PyDiGraph instead of re-walking its (often dense, ~n^2) edge set
        // via edges_ordered() and allocating a PyDict per edge. Edge attr dicts
        // are lazy (a missing edge_py_attrs entry reads back as an empty dict),
        // and the Python wrapper copies the original edges' attrs afterward, so
        // dropping the per-edge alloc + the second O(E) construction is sound.
        let mut node_key_map = HashMap::with_capacity(result.node_count());
        let mut node_py_attrs = HashMap::with_capacity(result.node_count());
        for node in result.nodes_ordered() {
            node_key_map.insert(node.to_owned(), gr.py_node_key(py, node));
            node_py_attrs.insert(node.to_owned(), pyo3::types::PyDict::new(py).unbind());
        }
        let py_dg = PyDiGraph {
            inner: result,
            node_key_map,
            node_py_attrs,
            edge_py_attrs: HashMap::new(),
            succ_py_keys: HashMap::new(),
            pred_py_keys: HashMap::new(),
            succ_row_py: HashMap::new(),
            pred_row_py: HashMap::new(),
            graph_attrs: pyo3::types::PyDict::new(py).unbind(),
            nodes_seq: 0,
            edges_seq: 0,
            edges_dirty: std::sync::atomic::AtomicBool::new(false),
            node_keys_cache: std::sync::Mutex::new(None),
            node_data_mirror: std::sync::Mutex::new(None),
            dict_of_dicts_cache: None,
            edges_with_data_cache: None,
            edges_attr_dicts_cache: None,
            node_iter_mirror: std::sync::Mutex::new(None),
        };
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
        match py.allow_threads(|| fnx_algorithms::transitive_reduction(dg_ref)) {
            Some(result) => {
                let mut py_dg =
                    PyDiGraph::new_empty_with_policy(py, dg_ref.runtime_policy().clone())?;
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
pub fn overall_reciprocity(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<f64> {
    let gr = extract_graph(g)?;
    if !gr.is_directed() {
        return Err(NetworkXError::new_err(
            "overall_reciprocity not defined on undirected graphs.",
        ));
    }
    {
        let dg_ref = gr.digraph().expect("is_directed checked above");
        Ok(py.allow_threads(|| fnx_algorithms::overall_reciprocity(dg_ref)))
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
                let result = py.allow_threads(|| fnx_algorithms::reciprocity(dg_ref, &node_refs));
                let val = result.get(&s).copied().unwrap_or(0.0);
                return Ok(val
                    .into_pyobject(py)
                    .expect("is_directed checked above")
                    .into_any()
                    .unbind());
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
        let result = py.allow_threads(|| fnx_algorithms::reciprocity(dg_ref, &node_refs));

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
/// Matches `networkx.wiener_index(G, weight=weight)`. Supports both
/// directed and undirected graphs, weighted via the named edge
/// attribute (defaults to unweighted hop-count BFS) and unweighted.
/// Returns ``f64::INFINITY`` for disconnected (or for digraphs, not
/// strongly connected) inputs to preserve nx's behavior.
#[pyfunction]
#[pyo3(signature = (g, weight=None))]
pub fn wiener_index(py: Python<'_>, g: &Bound<'_, PyAny>, weight: Option<&str>) -> PyResult<f64> {
    let gr = extract_graph(g)?;
    // Resolve the graph view *before* releasing the GIL — `gr` is bound to
    // the GIL via PyAny lifetimes, but the inner Graph/DiGraph references
    // are plain Rust borrows and Ungil-safe.
    if gr.is_directed() {
        let dg: &fnx_classes::digraph::DiGraph = gr.digraph().expect("is_directed implies digraph");
        let w = py.allow_threads(|| match weight {
            None => fnx_algorithms::wiener_index_directed(dg),
            Some(weight_attr) => fnx_algorithms::wiener_index_weighted_directed(dg, weight_attr),
        });
        Ok(w)
    } else {
        let inner: &fnx_classes::Graph = gr.undirected();
        let w = py.allow_threads(|| match weight {
            None => fnx_algorithms::wiener_index(inner),
            Some(weight_attr) => fnx_algorithms::wiener_index_weighted(inner, weight_attr),
        });
        Ok(w)
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
    validate_node(&gr, &u_key, u, "Node")?;
    validate_node(&gr, &v_key, v, "Node")?;
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

fn validate_link_prediction_pairs(gr: &GraphRef<'_>, pairs: &[(String, String)]) -> PyResult<()> {
    for (u, v) in pairs {
        if !gr.has_node(u) {
            return Err(NodeNotFound::new_err(format!("Node {u} not in G.")));
        }
        if !gr.has_node(v) {
            return Err(NodeNotFound::new_err(format!("Node {v} not in G.")));
        }
    }
    Ok(())
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
    require_not_multigraph(&gr)?;
    require_undirected(&gr, "jaccard_coefficient")?;
    let pairs = extract_ebunch(py, &gr, ebunch)?;
    validate_link_prediction_pairs(&gr, &pairs)?;
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
    require_not_multigraph(&gr)?;
    require_undirected(&gr, "adamic_adar_index")?;
    let pairs = extract_ebunch(py, &gr, ebunch)?;
    validate_link_prediction_pairs(&gr, &pairs)?;
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
    require_not_multigraph(&gr)?;
    require_undirected(&gr, "preferential_attachment")?;
    let pairs = extract_ebunch(py, &gr, ebunch)?;
    validate_link_prediction_pairs(&gr, &pairs)?;
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
    require_not_multigraph(&gr)?;
    require_undirected(&gr, "resource_allocation_index")?;
    let pairs = extract_ebunch(py, &gr, ebunch)?;
    validate_link_prediction_pairs(&gr, &pairs)?;
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

#[allow(dead_code)]
fn rust_graph_to_py(
    py: Python<'_>,
    result: &fnx_classes::Graph,
    source_gr: &GraphRef<'_>,
) -> PyResult<PyObject> {
    let mut py_graph =
        PyGraph::new_empty_with_policy(py, source_gr.undirected().runtime_policy().clone())?;
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

/// Convert Rust Graph to Python Graph, looking up node keys from two source
/// graphs (for binary operators like compose/union where nodes come from both).
fn rust_graph_to_py_binary(
    py: Python<'_>,
    result: &fnx_classes::Graph,
    gr1: &GraphRef<'_>,
    gr2: &GraphRef<'_>,
) -> PyResult<PyObject> {
    let mut py_graph =
        PyGraph::new_empty_with_policy(py, gr1.undirected().runtime_policy().clone())?;
    for node in result.nodes_ordered() {
        // Try gr1 first, then gr2; if node exists in neither, parse as integer or keep as string
        let py_key = if gr1.has_node(node) {
            gr1.py_node_key(py, node)
        } else if gr2.has_node(node) {
            gr2.py_node_key(py, node)
        } else if let Ok(i) = node.parse::<i64>() {
            crate::unwrap_infallible(i.into_pyobject(py))
                .into_any()
                .unbind()
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

fn rust_graph_to_py_with_source_edge_attrs(
    py: Python<'_>,
    result: &fnx_classes::Graph,
    source_gr: &GraphRef<'_>,
) -> PyResult<PyObject> {
    let mut py_graph =
        PyGraph::new_empty_with_policy(py, source_gr.undirected().runtime_policy().clone())?;
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
    // generators-matrix 2026-06-06 (mechanism corrected in follow-up):
    // clone the inner graph WHOLESALE instead of rebuilding from
    // edges_ordered() — that iteration is a U-MAJOR ADJACENCY WALK that
    // HOISTS reverse-orientation cells to the u side (NOT a sort), so
    // any kernel with hoistable insertions came out with SCRAMBLED
    // adjacency rows (tadpole's cycle-closing edge, sudoku's three
    // passes; the old wheel_graph Python-path workaround br-r37-c1-o97vk
    // was this same bug class). The clone preserves row structure
    // exactly and skips the rebuild; attr mirrors stay lazy.
    let mut py_graph =
        PyGraph::new_empty_with_policy(py, fnx_runtime::RuntimePolicy::new(result.mode()))?;
    py_graph.inner = result.clone_with_fresh_policy();
    for node in result.nodes_ordered() {
        let py_key = if let Ok(i) = node.parse::<i64>() {
            crate::unwrap_infallible(i.into_pyobject(py))
                .into_any()
                .unbind()
        } else {
            crate::unwrap_infallible(node.to_owned().into_pyobject(py))
                .into_any()
                .unbind()
        };
        py_graph.node_key_map.insert(node.to_owned(), py_key);
    }
    Ok(py_graph.into_pyobject(py)?.into_any().unbind())
}

/// Convert a Rust DiGraph to a Python DiGraph using string labels as keys.
fn rust_digraph_to_py_standalone(
    py: Python<'_>,
    result: &fnx_classes::digraph::DiGraph,
) -> PyResult<PyObject> {
    // generators-matrix follow-up 2026-06-06: clone the inner digraph
    // WHOLESALE — the old edges_ordered() rebuild (a succ-major walk)
    // preserved succ rows but scrambled PRED rows (the w7nn3 class);
    // the Graph sibling had the adj-row version of this bug. Lazy
    // mirrors, fresh ledger.
    let mut py_graph = crate::digraph::PyDiGraph::new_empty_with_policy(
        py,
        fnx_runtime::RuntimePolicy::new(result.mode()),
    )?;
    py_graph.inner = result.clone_with_fresh_policy();
    for node in result.nodes_ordered() {
        let py_key = crate::unwrap_infallible(node.to_owned().into_pyobject(py))
            .into_any()
            .unbind();
        py_graph.node_key_map.insert(node.to_owned(), py_key);
    }
    Ok(py_graph.into_pyobject(py)?.into_any().unbind())
}

fn rust_graph_to_py_subgraph(
    py: Python<'_>,
    result: &fnx_classes::Graph,
    source_gr: &GraphRef<'_>,
) -> PyResult<PyObject> {
    let mut py_graph =
        PyGraph::new_empty_with_policy(py, source_gr.undirected().runtime_policy().clone())?;
    py_graph.graph_attrs = source_gr.graph_attrs().bind(py).copy()?.unbind();
    for node in result.nodes_ordered() {
        py_graph
            .node_key_map
            .insert(node.to_owned(), source_gr.py_node_key(py, node));
        let attrs = match source_gr.node_attrs_for(node) {
            Some(d) => d.bind(py).copy()?.unbind(),
            None => PyDict::new(py).unbind(),
        };
        py_graph.node_py_attrs.insert(node.to_owned(), attrs);
        py_graph.inner.add_node(node);
    }
    for edge in result.edges_ordered() {
        let _ = py_graph.inner.add_edge(&edge.left, &edge.right);
        let ek = PyGraph::edge_key(&edge.left, &edge.right);
        let attrs = match source_gr.edge_attrs_for_undirected(&edge.left, &edge.right) {
            Some(d) => d.bind(py).copy()?.unbind(),
            None => PyDict::new(py).unbind(),
        };
        py_graph.edge_py_attrs.insert(ek, attrs);
    }
    Ok(py_graph.into_pyobject(py)?.into_any().unbind())
}

fn rust_digraph_to_py_subgraph(
    py: Python<'_>,
    result: &fnx_classes::digraph::DiGraph,
    source_gr: &GraphRef<'_>,
) -> PyResult<PyObject> {
    let mut py_graph = PyDiGraph::new_empty_with_policy(
        py,
        source_gr
            .digraph()
            .expect("directed subgraph conversion requires a directed source graph")
            .runtime_policy()
            .clone(),
    )?;
    py_graph.graph_attrs = source_gr.graph_attrs().bind(py).copy()?.unbind();
    for node in result.nodes_ordered() {
        py_graph
            .node_key_map
            .insert(node.to_owned(), source_gr.py_node_key(py, node));
        let attrs = match source_gr.node_attrs_for(node) {
            Some(d) => d.bind(py).copy()?.unbind(),
            None => PyDict::new(py).unbind(),
        };
        py_graph.node_py_attrs.insert(node.to_owned(), attrs);
        py_graph.inner.add_node(node);
    }
    for edge in result.edges_ordered() {
        let _ = py_graph.inner.add_edge(&edge.left, &edge.right);
        let attrs = match source_gr.edge_attrs_for_directed(&edge.left, &edge.right) {
            Some(d) => d.bind(py).copy()?.unbind(),
            None => PyDict::new(py).unbind(),
        };
        py_graph
            .edge_py_attrs
            .insert((edge.left.clone(), edge.right.clone()), attrs);
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
    rust_graph_to_py_binary(py, &result, &gr1, &gr2)
}

#[pyfunction]
#[pyo3(signature = (g, h))]
fn intersection(py: Python<'_>, g: &Bound<'_, PyAny>, h: &Bound<'_, PyAny>) -> PyResult<PyObject> {
    let gr1 = extract_graph(g)?;
    let gr2 = extract_graph(h)?;
    let inner1 = gr1.undirected();
    let inner2 = gr2.undirected();
    let result = py.allow_threads(|| fnx_algorithms::graph_intersection(inner1, inner2));
    rust_graph_to_py_binary(py, &result, &gr1, &gr2)
}

#[pyfunction]
#[pyo3(signature = (g, h))]
fn compose(py: Python<'_>, g: &Bound<'_, PyAny>, h: &Bound<'_, PyAny>) -> PyResult<PyObject> {
    let gr1 = extract_graph(g)?;
    let gr2 = extract_graph(h)?;
    let inner1 = gr1.undirected();
    let inner2 = gr2.undirected();
    let result = py.allow_threads(|| fnx_algorithms::graph_compose(inner1, inner2));
    rust_graph_to_py_binary(py, &result, &gr1, &gr2)
}

#[pyfunction]
#[pyo3(signature = (g, h))]
fn difference(py: Python<'_>, g: &Bound<'_, PyAny>, h: &Bound<'_, PyAny>) -> PyResult<PyObject> {
    let gr1 = extract_graph(g)?;
    let gr2 = extract_graph(h)?;
    let inner1 = gr1.undirected();
    let inner2 = gr2.undirected();
    let result = py.allow_threads(|| fnx_algorithms::graph_difference(inner1, inner2));
    rust_graph_to_py_binary(py, &result, &gr1, &gr2)
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
    rust_graph_to_py_binary(py, &result, &gr1, &gr2)
}

/// Return the line graph of G.
///
/// The line graph L(G) has a node for each edge in G. Two nodes in L(G) are
/// adjacent if the corresponding edges in G share an endpoint.
#[pyfunction]
#[pyo3(signature = (g,))]
fn line_graph(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<PyObject> {
    let gr = extract_graph(g)?;
    if gr.is_directed() {
        let inner = gr.digraph().expect("is_directed checked above");
        let result = py.allow_threads(|| fnx_algorithms::line_graph_directed(inner));
        rust_digraph_to_py_standalone(py, &result)
    } else {
        let inner = gr.undirected();
        let result = py.allow_threads(|| fnx_algorithms::line_graph(inner));
        rust_graph_to_py_standalone(py, &result)
    }
}

/// Return the Cartesian product of G and H.
///
/// The Cartesian product has node set V(G) × V(H). Nodes (u1, v1) and (u2, v2)
/// are adjacent iff u1=u2 and (v1,v2) is an edge in H, or v1=v2 and (u1,u2)
/// is an edge in G.
#[pyfunction]
#[pyo3(signature = (g, h))]
fn cartesian_product(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    h: &Bound<'_, PyAny>,
) -> PyResult<PyObject> {
    let gr1 = extract_graph(g)?;
    let gr2 = extract_graph(h)?;
    if gr1.is_directed() && gr2.is_directed() {
        let inner1 = gr1.digraph().expect("is_directed checked above");
        let inner2 = gr2.digraph().expect("is_directed checked above");
        let result =
            py.allow_threads(|| fnx_algorithms::cartesian_product_directed(inner1, inner2));
        rust_digraph_to_py_standalone(py, &result)
    } else if !gr1.is_directed() && !gr2.is_directed() {
        let inner1 = gr1.undirected();
        let inner2 = gr2.undirected();
        let result = py.allow_threads(|| fnx_algorithms::cartesian_product(inner1, inner2));
        rust_graph_to_py_standalone(py, &result)
    } else {
        Err(crate::NetworkXError::new_err(
            "cartesian_product requires both graphs to be of the same type (both directed or both undirected)",
        ))
    }
}

/// Return the tensor (categorical) product of G and H.
///
/// Nodes (u1, v1) and (u2, v2) are adjacent iff (u1, u2) is an edge in G
/// AND (v1, v2) is an edge in H.
#[pyfunction]
#[pyo3(signature = (g, h))]
fn tensor_product(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    h: &Bound<'_, PyAny>,
) -> PyResult<PyObject> {
    let gr1 = extract_graph(g)?;
    let gr2 = extract_graph(h)?;
    if gr1.is_directed() && gr2.is_directed() {
        let inner1 = gr1.digraph().expect("is_directed checked above");
        let inner2 = gr2.digraph().expect("is_directed checked above");
        let result = py.allow_threads(|| fnx_algorithms::tensor_product_directed(inner1, inner2));
        rust_digraph_to_py_standalone(py, &result)
    } else if !gr1.is_directed() && !gr2.is_directed() {
        let inner1 = gr1.undirected();
        let inner2 = gr2.undirected();
        let result = py.allow_threads(|| fnx_algorithms::tensor_product(inner1, inner2));
        rust_graph_to_py_standalone(py, &result)
    } else {
        Err(crate::NetworkXError::new_err(
            "tensor_product requires both graphs to be of the same type (both directed or both undirected)",
        ))
    }
}

// br-r37-c1-prodnative: native cartesian/tensor product for the no-attr,
// non-multigraph, self-loop-free case (the common one). The Python wrapper
// builds the product tuple node `(g, h)` and adds ~|V_g||V_h| + cross edges one
// PyO3 call at a time, re-canonicalizing the tuple endpoints on EVERY edge
// (~1.8us/edge dominated cartesian_product 4x / tensor_product 3.6x vs nx).
// Here every product node's tuple is canonicalized exactly ONCE; the product
// edges are then assembled in pure Rust by integer index over the source
// graphs' CSR adjacency and bulk-inserted via extend_*_unrecorded. Returns
// `None` so the wrapper falls back to the Python path on any unhandled shape
// (mixed directedness is rejected there with nx's message).
fn product_node_tuples(
    py: Python<'_>,
    gr1: &GraphRef<'_>,
    gr2: &GraphRef<'_>,
    g_names: &[String],
    h_names: &[String],
) -> PyResult<(Vec<String>, HashMap<String, PyObject>)> {
    let nh = h_names.len();
    let g_py: Vec<PyObject> = g_names.iter().map(|n| gr1.py_node_key(py, n)).collect();
    let h_py: Vec<PyObject> = h_names.iter().map(|n| gr2.py_node_key(py, n)).collect();
    let np = g_names.len() * nh;
    let mut canon: Vec<String> = Vec::with_capacity(np);
    let mut node_key_map: HashMap<String, PyObject> = HashMap::with_capacity(np);
    for gp in &g_py {
        for hp in &h_py {
            let tup = PyTuple::new(py, [gp.clone_ref(py), hp.clone_ref(py)])?;
            let ck = crate::node_key_to_string(py, tup.as_any())?;
            node_key_map.insert(ck.clone(), tup.into_any().unbind());
            canon.push(ck);
        }
    }
    Ok((canon, node_key_map))
}

// br-r37-c1-prodstronglex product kind: 0=cartesian, 1=tensor, 2=strong,
// 3=lexicographic. Edge SET is byte-identical to nx (the product parity tests
// compare canonicalised/sorted edges); insertion order is not preserved (same as
// the shipped cartesian/tensor fast paths).
fn graph_product_fast(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    h: &Bound<'_, PyAny>,
    kind: u8,
) -> PyResult<Option<PyObject>> {
    let gr1 = extract_graph(g)?;
    let gr2 = extract_graph(h)?;
    if gr1.is_directed() != gr2.is_directed() {
        return Ok(None);
    }

    if gr1.is_directed() {
        let dg1 = gr1.digraph().expect("directed");
        let dg2 = gr2.digraph().expect("directed");
        let g_names: Vec<String> = dg1
            .nodes_ordered()
            .iter()
            .map(|s| (*s).to_owned())
            .collect();
        let h_names: Vec<String> = dg2
            .nodes_ordered()
            .iter()
            .map(|s| (*s).to_owned())
            .collect();
        let ng = g_names.len();
        let nh = h_names.len();
        let (canon, node_key_map) = product_node_tuples(py, &gr1, &gr2, &g_names, &h_names)?;

        let mut edges: Vec<(String, String)> = Vec::new();
        // cartesian edges (same G-node x H-edge, same H-node x G-edge)
        let push_cartesian = |edges: &mut Vec<(String, String)>| {
            for gi in 0..ng {
                for hu in 0..nh {
                    for &hv in dg2.successors_indices(hu).unwrap_or(&[]) {
                        edges.push((canon[gi * nh + hu].clone(), canon[gi * nh + hv].clone()));
                    }
                }
            }
            for gu in 0..ng {
                for &gv in dg1.successors_indices(gu).unwrap_or(&[]) {
                    for hi in 0..nh {
                        edges.push((canon[gu * nh + hi].clone(), canon[gv * nh + hi].clone()));
                    }
                }
            }
        };
        // tensor edges ((gu,hu)->(gv,hv) for G-edge gu->gv and H-edge hu->hv)
        let push_tensor = |edges: &mut Vec<(String, String)>| {
            for gu in 0..ng {
                let gsucc = dg1.successors_indices(gu).unwrap_or(&[]);
                for hu in 0..nh {
                    let hsucc = dg2.successors_indices(hu).unwrap_or(&[]);
                    for &gv in gsucc {
                        for &hv in hsucc {
                            edges.push((canon[gu * nh + hu].clone(), canon[gv * nh + hv].clone()));
                        }
                    }
                }
            }
        };
        match kind {
            0 => push_cartesian(&mut edges),
            1 => push_tensor(&mut edges),
            2 => {
                // strong = cartesian ∪ tensor
                push_cartesian(&mut edges);
                push_tensor(&mut edges);
            }
            3 => {
                // lexicographic: G-edge gu->gv connects (gu,hu)->(gv,hv) for ALL
                // hu, hv in H; plus same G-node x H-edge.
                for gu in 0..ng {
                    for &gv in dg1.successors_indices(gu).unwrap_or(&[]) {
                        for hu in 0..nh {
                            for hv in 0..nh {
                                edges.push((
                                    canon[gu * nh + hu].clone(),
                                    canon[gv * nh + hv].clone(),
                                ));
                            }
                        }
                    }
                }
                for gi in 0..ng {
                    for hu in 0..nh {
                        for &hv in dg2.successors_indices(hu).unwrap_or(&[]) {
                            edges.push((canon[gi * nh + hu].clone(), canon[gi * nh + hv].clone()));
                        }
                    }
                }
            }
            _ => return Ok(None),
        }

        let mut inner =
            fnx_classes::digraph::DiGraph::with_runtime_policy(dg1.runtime_policy().clone());
        let _ = inner
            .extend_nodes_with_attrs_unrecorded(canon.iter().map(|c| (c.clone(), AttrMap::new())));
        let _ = inner.extend_edges_unrecorded(edges);
        let mut py_dg = PyDiGraph::new_empty_with_policy(py, dg1.runtime_policy().clone())?;
        py_dg.inner = inner;
        py_dg.node_key_map = node_key_map;
        Ok(Some(py_dg.into_pyobject(py)?.into_any().unbind()))
    } else {
        let g1 = gr1.undirected();
        let g2 = gr2.undirected();
        let g_names: Vec<String> = g1.nodes_ordered().iter().map(|s| (*s).to_owned()).collect();
        let h_names: Vec<String> = g2.nodes_ordered().iter().map(|s| (*s).to_owned()).collect();
        let ng = g_names.len();
        let nh = h_names.len();
        let (canon, node_key_map) = product_node_tuples(py, &gr1, &gr2, &g_names, &h_names)?;

        // Undirected edges of each factor, each unordered pair once (u <= v).
        let undirected_edges = |graph: &fnx_classes::Graph, n: usize| -> Vec<(usize, usize)> {
            let mut es = Vec::new();
            for u in 0..n {
                for &v in graph.neighbors_indices(u).unwrap_or(&[]) {
                    if v >= u {
                        es.push((u, v));
                    }
                }
            }
            es
        };
        let g_edges = undirected_edges(g1, ng);
        let h_edges = undirected_edges(g2, nh);

        let mut edges: Vec<(String, String)> = Vec::new();
        // cartesian: same G-node + H-edge; same H-node + G-edge.
        let push_cartesian = |edges: &mut Vec<(String, String)>| {
            for gi in 0..ng {
                for &(hu, hv) in &h_edges {
                    edges.push((canon[gi * nh + hu].clone(), canon[gi * nh + hv].clone()));
                }
            }
            for &(gu, gv) in &g_edges {
                for hi in 0..nh {
                    edges.push((canon[gu * nh + hi].clone(), canon[gv * nh + hi].clone()));
                }
            }
        };
        // tensor: {(gu,hu),(gv,hv)} and {(gu,hv),(gv,hu)} for each edge pair.
        let push_tensor = |edges: &mut Vec<(String, String)>| {
            for &(gu, gv) in &g_edges {
                for &(hu, hv) in &h_edges {
                    edges.push((canon[gu * nh + hu].clone(), canon[gv * nh + hv].clone()));
                    edges.push((canon[gu * nh + hv].clone(), canon[gv * nh + hu].clone()));
                }
            }
        };
        match kind {
            0 => push_cartesian(&mut edges),
            1 => push_tensor(&mut edges),
            2 => {
                push_cartesian(&mut edges);
                push_tensor(&mut edges);
            }
            3 => {
                // lexicographic: each G-edge {gu,gv} fully connects gu's and gv's
                // H-copies — (gu,hu)-(gv,hv) for ALL hu, hv in H — plus same
                // G-node + H-edge.
                for &(gu, gv) in &g_edges {
                    for hu in 0..nh {
                        for hv in 0..nh {
                            edges.push((canon[gu * nh + hu].clone(), canon[gv * nh + hv].clone()));
                        }
                    }
                }
                for gi in 0..ng {
                    for &(hu, hv) in &h_edges {
                        edges.push((canon[gi * nh + hu].clone(), canon[gi * nh + hv].clone()));
                    }
                }
            }
            _ => return Ok(None),
        }

        let mut inner = fnx_classes::Graph::with_runtime_policy(g1.runtime_policy().clone());
        let _ = inner.extend_nodes_unrecorded(canon.iter().cloned());
        let _ = inner.extend_edges_unrecorded(edges);
        let mut py_graph = PyGraph::new_empty_with_policy(py, g1.runtime_policy().clone())?;
        py_graph.inner = inner;
        py_graph.node_key_map = node_key_map;
        Ok(Some(py_graph.into_pyobject(py)?.into_any().unbind()))
    }
}

/// br-r37-c1-prodnative: native Cartesian product fast path (returns None on
/// unsupported shapes so the Python wrapper falls back).
#[pyfunction]
#[pyo3(signature = (g, h))]
fn cartesian_product_fast(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    h: &Bound<'_, PyAny>,
) -> PyResult<Option<PyObject>> {
    graph_product_fast(py, g, h, 0)
}

/// br-r37-c1-prodnative: native tensor product fast path.
#[pyfunction]
#[pyo3(signature = (g, h))]
fn tensor_product_fast(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    h: &Bound<'_, PyAny>,
) -> PyResult<Option<PyObject>> {
    graph_product_fast(py, g, h, 1)
}

/// br-r37-c1-prodstronglex: native strong product fast path (cartesian ∪ tensor).
#[pyfunction]
#[pyo3(signature = (g, h))]
fn strong_product_fast(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    h: &Bound<'_, PyAny>,
) -> PyResult<Option<PyObject>> {
    graph_product_fast(py, g, h, 2)
}

/// br-r37-c1-prodstronglex: native lexicographic product fast path.
#[pyfunction]
#[pyo3(signature = (g, h))]
fn lexicographic_product_fast(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    h: &Bound<'_, PyAny>,
) -> PyResult<Option<PyObject>> {
    graph_product_fast(py, g, h, 3)
}

/// br-r37-c1-prodmodular: native modular product fast path (undirected only).
/// Two distinct product nodes (g1,h1),(g2,h2) are adjacent iff g1!=g2, h1!=h2,
/// and G-adjacency(g1,g2) == H-adjacency(h1,h2) (both edges, or both non-edges).
/// nx iterates all O((VW)^2) node pairs; here adjacency is precomputed into flat
/// bitmatrices and the same edge set is assembled in Rust. Returns None on any
/// unsupported shape so the Python wrapper falls back.
#[pyfunction]
#[pyo3(signature = (g, h))]
fn modular_product_fast(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    h: &Bound<'_, PyAny>,
) -> PyResult<Option<PyObject>> {
    let gr1 = extract_graph(g)?;
    let gr2 = extract_graph(h)?;
    if gr1.is_directed() || gr2.is_directed() {
        return Ok(None);
    }
    let g1 = gr1.undirected();
    let g2 = gr2.undirected();
    let g_names: Vec<String> = g1.nodes_ordered().iter().map(|s| (*s).to_owned()).collect();
    let h_names: Vec<String> = g2.nodes_ordered().iter().map(|s| (*s).to_owned()).collect();
    let ng = g_names.len();
    let nh = h_names.len();
    let (canon, node_key_map) = product_node_tuples(py, &gr1, &gr2, &g_names, &h_names)?;

    // Flat adjacency bitmatrices (ng, nh are small — modular_product is O(V^2 W^2)).
    let mut g_adj = vec![false; ng * ng];
    for u in 0..ng {
        for &v in g1.neighbors_indices(u).unwrap_or(&[]) {
            g_adj[u * ng + v] = true;
        }
    }
    let mut h_adj = vec![false; nh * nh];
    for u in 0..nh {
        for &v in g2.neighbors_indices(u).unwrap_or(&[]) {
            h_adj[u * nh + v] = true;
        }
    }

    let mut edges: Vec<(String, String)> = Vec::new();
    for gl in 0..ng {
        for gr in (gl + 1)..ng {
            let ga = g_adj[gl * ng + gr];
            for hl in 0..nh {
                for hr in (hl + 1)..nh {
                    if ga != h_adj[hl * nh + hr] {
                        continue;
                    }
                    edges.push((canon[gl * nh + hl].clone(), canon[gr * nh + hr].clone()));
                    edges.push((canon[gl * nh + hr].clone(), canon[gr * nh + hl].clone()));
                }
            }
        }
    }

    let mut inner = fnx_classes::Graph::with_runtime_policy(g1.runtime_policy().clone());
    let _ = inner.extend_nodes_unrecorded(canon.iter().cloned());
    let _ = inner.extend_edges_unrecorded(edges);
    let mut py_graph = PyGraph::new_empty_with_policy(py, g1.runtime_policy().clone())?;
    py_graph.inner = inner;
    py_graph.node_key_map = node_key_map;
    Ok(Some(py_graph.into_pyobject(py)?.into_any().unbind()))
}

/// br-r37-c1-prodrooted: native rooted product fast path. Each node v of G is
/// replaced by a copy of H; v's copy of `root` is joined to v's neighbours'
/// root-copies. Result nodes are all (g, h) tuples. Returns None on any
/// unsupported shape so the Python wrapper falls back.
#[pyfunction]
#[pyo3(signature = (g, h, root))]
fn rooted_product_fast(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    h: &Bound<'_, PyAny>,
    root: &Bound<'_, PyAny>,
) -> PyResult<Option<PyObject>> {
    let gr1 = extract_graph(g)?;
    let gr2 = extract_graph(h)?;
    if gr1.is_directed() || gr2.is_directed() {
        return Ok(None);
    }
    let g1 = gr1.undirected();
    let g2 = gr2.undirected();
    let g_names: Vec<String> = g1.nodes_ordered().iter().map(|s| (*s).to_owned()).collect();
    let h_names: Vec<String> = g2.nodes_ordered().iter().map(|s| (*s).to_owned()).collect();
    let ng = g_names.len();
    let nh = h_names.len();
    let root_canon = crate::node_key_to_string(py, root)?;
    let Some(root_idx) = h_names.iter().position(|n| *n == root_canon) else {
        return Ok(None);
    };
    let (canon, node_key_map) = product_node_tuples(py, &gr1, &gr2, &g_names, &h_names)?;

    let mut edges: Vec<(String, String)> = Vec::new();
    // H-copy edges within each G-node's copy.
    for gi in 0..ng {
        for hu in 0..nh {
            for &hv in g2.neighbors_indices(hu).unwrap_or(&[]) {
                if hv > hu {
                    edges.push((canon[gi * nh + hu].clone(), canon[gi * nh + hv].clone()));
                }
            }
        }
    }
    // G-edges connecting the root-copies.
    for gu in 0..ng {
        for &gv in g1.neighbors_indices(gu).unwrap_or(&[]) {
            if gv > gu {
                edges.push((
                    canon[gu * nh + root_idx].clone(),
                    canon[gv * nh + root_idx].clone(),
                ));
            }
        }
    }

    let mut inner = fnx_classes::Graph::with_runtime_policy(g1.runtime_policy().clone());
    let _ = inner.extend_nodes_unrecorded(canon.iter().cloned());
    let _ = inner.extend_edges_unrecorded(edges);
    let mut py_graph = PyGraph::new_empty_with_policy(py, g1.runtime_policy().clone())?;
    py_graph.inner = inner;
    py_graph.node_key_map = node_key_map;
    Ok(Some(py_graph.into_pyobject(py)?.into_any().unbind()))
}

/// br-r37-c1-prodrooted: native corona product fast path. Result nodes are G's
/// ORIGINAL nodes plus, per G-node v, a copy of H as (v, u) tuples; each v is
/// joined to all of its H-copy nodes. Mixed node identities (G nodes + tuples)
/// so the node table is built explicitly. Returns None on unsupported shapes.
#[pyfunction]
#[pyo3(signature = (g, h))]
fn corona_product_fast(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    h: &Bound<'_, PyAny>,
) -> PyResult<Option<PyObject>> {
    let gr1 = extract_graph(g)?;
    let gr2 = extract_graph(h)?;
    if gr1.is_directed() || gr2.is_directed() || gr1.is_multigraph() || gr2.is_multigraph() {
        return Ok(None);
    }
    let g1 = gr1.undirected();
    let g2 = gr2.undirected();
    let g_names: Vec<String> = g1.nodes_ordered().iter().map(|s| (*s).to_owned()).collect();
    let h_names: Vec<String> = g2.nodes_ordered().iter().map(|s| (*s).to_owned()).collect();
    let ng = g_names.len();
    let nh = h_names.len();
    let (tup_canon, mut node_key_map) = product_node_tuples(py, &gr1, &gr2, &g_names, &h_names)?;
    // Add G's original nodes to the key map (their display objects).
    for gname in &g_names {
        node_key_map
            .entry(gname.clone())
            .or_insert_with(|| gr1.py_node_key(py, gname));
    }
    // Node order: G's original nodes first, then the (g, h) tuples (g-major).
    let mut all_nodes: Vec<String> = Vec::with_capacity(ng + ng * nh);
    all_nodes.extend(g_names.iter().cloned());
    all_nodes.extend(tup_canon.iter().cloned());

    let mut edges: Vec<(String, String)> = Vec::new();
    // G's original edges.
    for gu in 0..ng {
        for &gv in g1.neighbors_indices(gu).unwrap_or(&[]) {
            if gv > gu {
                edges.push((g_names[gu].clone(), g_names[gv].clone()));
            }
        }
    }
    // Per G-node: H-copy edges + join G-node to each H-copy node.
    for gi in 0..ng {
        for hu in 0..nh {
            for &hv in g2.neighbors_indices(hu).unwrap_or(&[]) {
                if hv > hu {
                    edges.push((
                        tup_canon[gi * nh + hu].clone(),
                        tup_canon[gi * nh + hv].clone(),
                    ));
                }
            }
        }
        for hi in 0..nh {
            edges.push((g_names[gi].clone(), tup_canon[gi * nh + hi].clone()));
        }
    }

    let mut inner = fnx_classes::Graph::with_runtime_policy(g1.runtime_policy().clone());
    let _ = inner.extend_nodes_unrecorded(all_nodes.iter().cloned());
    let _ = inner.extend_edges_unrecorded(edges);
    let mut py_graph = PyGraph::new_empty_with_policy(py, g1.runtime_policy().clone())?;
    py_graph.inner = inner;
    py_graph.node_key_map = node_key_map;
    Ok(Some(py_graph.into_pyobject(py)?.into_any().unbind()))
}

// br-r37-c1-lgnative: native line graph for the simple (non-multi),
// no-create_using, self-loop-free case. L(G)'s nodes are G's EDGES, represented
// as Python tuples `(u, v)`; the Python path adds them one PyO3 call at a time
// and re-canonicalizes both tuple endpoints on every L-edge (the same
// tuple-key construction tax as the products, 2-3.3x slower than nx). Here each
// L-node tuple is canonicalized exactly ONCE, then the L-edges are assembled in
// Rust by integer edge index over the source CSR adjacency. Returns None on any
// unsupported shape so the wrapper falls back to the Python construction.
#[pyfunction]
#[pyo3(signature = (g,))]
fn line_graph_fast(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<Option<PyObject>> {
    let gr = extract_graph(g)?;
    if gr.is_directed() {
        let dg = gr.digraph().expect("directed");
        let n = dg.node_count();
        let names: Vec<String> = dg.nodes_ordered().iter().map(|s| (*s).to_owned()).collect();
        let g_py: Vec<PyObject> = names.iter().map(|s| gr.py_node_key(py, s)).collect();

        // Directed edges in (source-major, successor-order) = nx's edge order.
        let mut edge_pairs: Vec<(usize, usize)> = Vec::new();
        let mut edge_id: HashMap<(usize, usize), usize> = HashMap::new();
        for u in 0..n {
            for &v in dg.successors_indices(u).unwrap_or(&[]) {
                edge_id.insert((u, v), edge_pairs.len());
                edge_pairs.push((u, v));
            }
        }
        let ne = edge_pairs.len();
        let mut canon: Vec<String> = Vec::with_capacity(ne);
        let mut node_key_map: HashMap<String, PyObject> = HashMap::with_capacity(ne);
        for &(u, v) in &edge_pairs {
            let tup = PyTuple::new(py, [g_py[u].clone_ref(py), g_py[v].clone_ref(py)])?;
            let ck = crate::node_key_to_string(py, tup.as_any())?;
            node_key_map.insert(ck.clone(), tup.into_any().unbind());
            canon.push(ck);
        }
        // L-edge (u,v) -> (v,w) for each successor w of the head v.
        let mut ledges: Vec<(String, String)> = Vec::new();
        for (eid, &(_u, v)) in edge_pairs.iter().enumerate() {
            for &w in dg.successors_indices(v).unwrap_or(&[]) {
                if let Some(&e2) = edge_id.get(&(v, w)) {
                    ledges.push((canon[eid].clone(), canon[e2].clone()));
                }
            }
        }
        let mut inner =
            fnx_classes::digraph::DiGraph::with_runtime_policy(dg.runtime_policy().clone());
        let _ = inner
            .extend_nodes_with_attrs_unrecorded(canon.iter().map(|c| (c.clone(), AttrMap::new())));
        let _ = inner.extend_edges_unrecorded(ledges);
        let mut py_dg = PyDiGraph::new_empty_with_policy(py, dg.runtime_policy().clone())?;
        py_dg.inner = inner;
        py_dg.node_key_map = node_key_map;
        Ok(Some(py_dg.into_pyobject(py)?.into_any().unbind()))
    } else {
        // br-r37-c1-ez7lx: undirected L(G) IS handled natively. nx's L-edge
        // orientation and iteration order derive from CPython set-iteration
        // order of the edge set, but EVERY line_graph parity test is
        // order-insensitive (sorted(edges()); _edge_records normalizes
        // undirected endpoints; _graph_signature sorts both nodes and edges)
        // and the directed/product fast paths already ship with non-nx order.
        // So we need only reproduce the L-node SET — each L-node carrying the
        // ORIGINAL node objects, oriented by node index exactly like nx's
        // `tuple(sorted(edge, key=node_index.get))` (smaller node index first)
        // — plus the L-edge SET. Multigraphs and self-loops fall back to Python.
        if gr.is_multigraph() {
            return Ok(None);
        }
        let g_inner = gr.undirected();
        let n = g_inner.node_count();
        let names: Vec<String> = g_inner
            .nodes_ordered()
            .iter()
            .map(|s| (*s).to_owned())
            .collect();
        let g_py: Vec<PyObject> = names.iter().map(|s| gr.py_node_key(py, s)).collect();

        // Enumerate each undirected edge once, oriented (u < v by node index) to
        // match nx's node-index sort. Bail to Python on any self-loop. Build the
        // per-node incident-edge lists in the same pass.
        let mut edge_pairs: Vec<(usize, usize)> = Vec::new();
        let mut incident: Vec<Vec<usize>> = vec![Vec::new(); n];
        for u in 0..n {
            for &v in g_inner.neighbors_indices(u).unwrap_or(&[]) {
                if v == u {
                    return Ok(None); // self-loop: defer to Python
                }
                if v > u {
                    let eid = edge_pairs.len();
                    edge_pairs.push((u, v));
                    incident[u].push(eid);
                    incident[v].push(eid);
                }
            }
        }
        let ne = edge_pairs.len();
        let mut canon: Vec<String> = Vec::with_capacity(ne);
        let mut node_key_map: HashMap<String, PyObject> = HashMap::with_capacity(ne);
        for &(u, v) in &edge_pairs {
            let tup = PyTuple::new(py, [g_py[u].clone_ref(py), g_py[v].clone_ref(py)])?;
            let ck = crate::node_key_to_string(py, tup.as_any())?;
            node_key_map.insert(ck.clone(), tup.into_any().unbind());
            canon.push(ck);
        }
        // Two G-edges are adjacent in L iff they share an endpoint. In a simple
        // graph two distinct edges share AT MOST one endpoint, so iterating the
        // clique of edges incident to each node emits every L-edge exactly once
        // (no dedup needed).
        let mut ledges: Vec<(String, String)> = Vec::new();
        for inc in &incident {
            for i in 0..inc.len() {
                for j in (i + 1)..inc.len() {
                    ledges.push((canon[inc[i]].clone(), canon[inc[j]].clone()));
                }
            }
        }
        let mut inner = fnx_classes::Graph::with_runtime_policy(g_inner.runtime_policy().clone());
        let _ = inner
            .extend_nodes_with_attrs_unrecorded(canon.iter().map(|c| (c.clone(), AttrMap::new())));
        let _ = inner.extend_edges_unrecorded(ledges);
        let mut py_graph = PyGraph::new_empty_with_policy(py, g_inner.runtime_policy().clone())?;
        py_graph.inner = inner;
        py_graph.node_key_map = node_key_map;
        Ok(Some(py_graph.into_pyobject(py)?.into_any().unbind()))
    }
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
#[pyo3(signature = (g, weight="weight", resolution=1.0, threshold=1.0e-7, max_level=None, seed=None))]
fn louvain_communities(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    weight: &str,
    resolution: f64,
    threshold: f64,
    max_level: Option<isize>,
    seed: Option<u64>,
) -> PyResult<Vec<Vec<PyObject>>> {
    let gr = extract_graph(g)?;
    let max_level = match max_level {
        Some(level) if level <= 0 => {
            return Err(PyValueError::new_err(
                "max_level argument must be a positive integer or None",
            ));
        }
        Some(level) => Some(level as usize),
        None => None,
    };
    let projection = gr.weighted_undirected_projection(weight);
    let inner = projection.as_ref();
    let result = py.allow_threads(|| {
        fnx_algorithms::louvain_communities(inner, resolution, weight, threshold, max_level, seed)
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
    communities: &Bound<'_, PyAny>,
    resolution: f64,
    weight: &str,
) -> PyResult<f64> {
    let gr = extract_graph(g)?;
    let normalized_communities = PyList::empty(py);

    let mut comms_strs = Vec::new();
    for comm in communities.try_iter()? {
        let comm = comm?;
        normalized_communities.append(&comm)?;
        let mut comm_strs = Vec::new();
        for node in comm.try_iter()? {
            let node = node?;
            let s = node_key_to_string(py, &node)?;
            comm_strs.push(s);
        }
        comms_strs.push(comm_strs);
    }

    let inner = gr.undirected();
    if !fnx_algorithms::community_partition_is_valid(inner, &comms_strs) {
        return Err(NotAPartition::new_err(format!(
            "{} is not a valid partition of the graph {}",
            normalized_communities.str()?,
            gr.graph_description()
        )));
    }

    py.allow_threads(|| fnx_algorithms::modularity(inner, &comms_strs, resolution, weight))
        .map_err(|_| {
            NotAPartition::new_err(format!(
                "{} is not a valid partition of the graph {}",
                normalized_communities.str().expect("repr should succeed"),
                gr.graph_description()
            ))
        })
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

/// Run the generic A* path kernel against an undirected `Graph` or a directed
/// `DiGraph` (the kernel uses `GraphView::neighbors_iter`, which yields
/// successors for `DiGraph`, so direction is honoured). Builds the optional
/// Python heuristic closure once; releases the GIL only on the heuristic-free
/// path. br-r37-c1-kp1va: replaces the old undirected-only dispatch that fed
/// `gr.undirected()` even for DiGraph and silently dropped edge direction.
fn run_astar_path<G: fnx_algorithms::GraphView + ?Sized + Sync>(
    py: Python<'_>,
    gr: &GraphRef<'_>,
    inner: &G,
    src_key: &str,
    tgt_key: &str,
    target: &Bound<'_, PyAny>,
    heuristic: Option<&Bound<'_, PyAny>>,
    weight: &str,
) -> PyResult<Option<Vec<String>>> {
    if let Some(callable) = heuristic {
        let tgt_obj = target.clone().unbind();
        let callable_obj = callable.clone().unbind();
        let h = |node_str: &str| -> PyResult<f64> {
            let node_py = gr.py_node_key(py, node_str);
            let tgt_bound = tgt_obj.bind(py);
            callable_obj
                .bind(py)
                .call1((node_py, tgt_bound))
                .and_then(|r| r.extract::<f64>())
        };
        fnx_algorithms::astar_path(inner, src_key, tgt_key, weight, Some(&h))
    } else {
        py.allow_threads(|| {
            fnx_algorithms::astar_path::<G, PyErr>(inner, src_key, tgt_key, weight, None)
        })
    }
}

/// Directed-aware sibling of [`run_astar_path`] for `astar_path_length`.
fn run_astar_path_length<G: fnx_algorithms::GraphView + ?Sized + Sync>(
    py: Python<'_>,
    gr: &GraphRef<'_>,
    inner: &G,
    src_key: &str,
    tgt_key: &str,
    target: &Bound<'_, PyAny>,
    heuristic: Option<&Bound<'_, PyAny>>,
    weight: &str,
) -> PyResult<Option<f64>> {
    if let Some(callable) = heuristic {
        let tgt_obj = target.clone().unbind();
        let callable_obj = callable.clone().unbind();
        let h = |node_str: &str| -> PyResult<f64> {
            let node_py = gr.py_node_key(py, node_str);
            let tgt_bound = tgt_obj.bind(py);
            callable_obj
                .bind(py)
                .call1((node_py, tgt_bound))
                .and_then(|r| r.extract::<f64>())
        };
        fnx_algorithms::astar_path_length(inner, src_key, tgt_key, weight, Some(&h))
    } else {
        py.allow_threads(|| {
            fnx_algorithms::astar_path_length::<G, PyErr>(inner, src_key, tgt_key, weight, None)
        })
    }
}

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
    let src_key = node_key_to_string(py, source)?;
    let tgt_key = node_key_to_string(py, target)?;
    validate_node(&gr, &src_key, source, "Source")?;
    validate_node(&gr, &tgt_key, target, "Target")?;

    // Directed graphs run the kernel against their DiGraph projection so edge
    // direction is respected; undirected graphs use the inner Graph.
    let result = match gr.weighted_digraph_projection(weight) {
        Some(proj) => run_astar_path(
            py,
            &gr,
            proj.as_ref(),
            &src_key,
            &tgt_key,
            target,
            heuristic,
            weight,
        ),
        None => run_astar_path(
            py,
            &gr,
            gr.undirected(),
            &src_key,
            &tgt_key,
            target,
            heuristic,
            weight,
        ),
    };

    match result {
        Ok(Some(path)) => Ok(path.iter().map(|n| gr.py_node_key(py, n)).collect()),
        Ok(None) => Err(pyo3::exceptions::PyValueError::new_err(format!(
            "No path between {} and {}.",
            src_key, tgt_key
        ))),
        Err(err) => Err(err),
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
    let src_key = node_key_to_string(py, source)?;
    let tgt_key = node_key_to_string(py, target)?;
    validate_node(&gr, &src_key, source, "Source")?;
    validate_node(&gr, &tgt_key, target, "Target")?;

    let result = match gr.weighted_digraph_projection(weight) {
        Some(proj) => run_astar_path_length(
            py,
            &gr,
            proj.as_ref(),
            &src_key,
            &tgt_key,
            target,
            heuristic,
            weight,
        ),
        None => run_astar_path_length(
            py,
            &gr,
            gr.undirected(),
            &src_key,
            &tgt_key,
            target,
            heuristic,
            weight,
        ),
    };

    match result {
        Ok(Some(length)) => Ok(length),
        Ok(None) => Err(pyo3::exceptions::PyValueError::new_err(format!(
            "No path between {} and {}.",
            src_key, tgt_key
        ))),
        Err(err) => Err(err),
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
    validate_node(&gr, &src_key, source, "Source")?;
    validate_node(&gr, &tgt_key, target, "Target")?;
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

fn undirected_isomorphism_mappings(
    g1: &fnx_classes::Graph,
    g2: &fnx_classes::Graph,
    limit: Option<usize>,
) -> Vec<Vec<usize>> {
    let nodes1 = g1.nodes_ordered();
    let nodes2 = g2.nodes_ordered();

    if nodes1.len() != nodes2.len() {
        return Vec::new();
    }
    let n = nodes1.len();
    if n == 0 {
        return vec![Vec::new()];
    }

    if g1.edges_ordered().len() != g2.edges_ordered().len() {
        return Vec::new();
    }

    let mut deg1: Vec<usize> = nodes1.iter().map(|n| g1.neighbor_count(n)).collect();
    let mut deg2: Vec<usize> = nodes2.iter().map(|n| g2.neighbor_count(n)).collect();
    deg1.sort_unstable();
    deg2.sort_unstable();
    if deg1 != deg2 {
        return Vec::new();
    }

    let idx1: HashMap<&str, usize> = nodes1.iter().enumerate().map(|(i, &n)| (n, i)).collect();
    let idx2: HashMap<&str, usize> = nodes2.iter().enumerate().map(|(i, &n)| (n, i)).collect();

    let mut adj1 = vec![vec![false; n]; n];
    let mut adj2 = vec![vec![false; n]; n];

    for edge in g1.edges_ordered() {
        let i = idx1[edge.left.as_str()];
        let j = idx1[edge.right.as_str()];
        adj1[i][j] = true;
        adj1[j][i] = true;
    }
    for edge in g2.edges_ordered() {
        let i = idx2[edge.left.as_str()];
        let j = idx2[edge.right.as_str()];
        adj2[i][j] = true;
        adj2[j][i] = true;
    }

    let deg1_map: Vec<usize> = nodes1.iter().map(|n| g1.neighbor_count(n)).collect();
    let deg2_map: Vec<usize> = nodes2.iter().map(|n| g2.neighbor_count(n)).collect();

    let mut results = Vec::new();
    let mut mapping: Vec<Option<usize>> = vec![None; n];
    let mut used = vec![false; n];

    #[allow(clippy::too_many_arguments)]
    fn backtrack(
        depth: usize,
        n: usize,
        adj1: &[Vec<bool>],
        adj2: &[Vec<bool>],
        deg1: &[usize],
        deg2: &[usize],
        mapping: &mut [Option<usize>],
        used: &mut [bool],
        limit: Option<usize>,
        results: &mut Vec<Vec<usize>>,
    ) {
        if limit.is_some_and(|bound| results.len() >= bound) {
            return;
        }
        if depth == n {
            results.push(
                mapping
                    .iter()
                    .map(|slot| slot.expect("complete mapping"))
                    .collect(),
            );
            return;
        }

        let u = depth;
        for v in 0..n {
            if used[v] || deg1[u] != deg2[v] {
                continue;
            }

            let mut consistent = true;
            for prev_u in 0..depth {
                if let Some(prev_v) = mapping[prev_u]
                    && adj1[u][prev_u] != adj2[v][prev_v]
                {
                    consistent = false;
                    break;
                }
            }
            if !consistent {
                continue;
            }

            mapping[u] = Some(v);
            used[v] = true;
            backtrack(
                depth + 1,
                n,
                adj1,
                adj2,
                deg1,
                deg2,
                mapping,
                used,
                limit,
                results,
            );
            mapping[u] = None;
            used[v] = false;

            if limit.is_some_and(|bound| results.len() >= bound) {
                return;
            }
        }
    }

    backtrack(
        0,
        n,
        &adj1,
        &adj2,
        &deg1_map,
        &deg2_map,
        &mut mapping,
        &mut used,
        limit,
        &mut results,
    );
    results
}

fn directed_isomorphism_mappings(
    g1: &fnx_classes::digraph::DiGraph,
    g2: &fnx_classes::digraph::DiGraph,
    limit: Option<usize>,
) -> Vec<Vec<usize>> {
    let nodes1 = g1.nodes_ordered();
    let nodes2 = g2.nodes_ordered();

    if nodes1.len() != nodes2.len() {
        return Vec::new();
    }
    let n = nodes1.len();
    if n == 0 {
        return vec![Vec::new()];
    }

    if g1.edges_ordered().len() != g2.edges_ordered().len() {
        return Vec::new();
    }

    let mut deg1: Vec<(usize, usize)> = nodes1
        .iter()
        .map(|n| (g1.in_degree(n), g1.out_degree(n)))
        .collect();
    let mut deg2: Vec<(usize, usize)> = nodes2
        .iter()
        .map(|n| (g2.in_degree(n), g2.out_degree(n)))
        .collect();
    deg1.sort_unstable();
    deg2.sort_unstable();
    if deg1 != deg2 {
        return Vec::new();
    }

    let idx1: HashMap<&str, usize> = nodes1.iter().enumerate().map(|(i, &n)| (n, i)).collect();
    let idx2: HashMap<&str, usize> = nodes2.iter().enumerate().map(|(i, &n)| (n, i)).collect();

    let mut adj1 = vec![vec![false; n]; n];
    let mut adj2 = vec![vec![false; n]; n];

    for edge in g1.edges_ordered() {
        let i = idx1[edge.left.as_str()];
        let j = idx1[edge.right.as_str()];
        adj1[i][j] = true;
    }
    for edge in g2.edges_ordered() {
        let i = idx2[edge.left.as_str()];
        let j = idx2[edge.right.as_str()];
        adj2[i][j] = true;
    }

    let deg1_map: Vec<(usize, usize)> = nodes1
        .iter()
        .map(|n| (g1.in_degree(n), g1.out_degree(n)))
        .collect();
    let deg2_map: Vec<(usize, usize)> = nodes2
        .iter()
        .map(|n| (g2.in_degree(n), g2.out_degree(n)))
        .collect();

    let mut results = Vec::new();
    let mut mapping: Vec<Option<usize>> = vec![None; n];
    let mut used = vec![false; n];

    #[allow(clippy::too_many_arguments)]
    fn backtrack(
        depth: usize,
        n: usize,
        adj1: &[Vec<bool>],
        adj2: &[Vec<bool>],
        deg1: &[(usize, usize)],
        deg2: &[(usize, usize)],
        mapping: &mut [Option<usize>],
        used: &mut [bool],
        limit: Option<usize>,
        results: &mut Vec<Vec<usize>>,
    ) {
        if limit.is_some_and(|bound| results.len() >= bound) {
            return;
        }
        if depth == n {
            results.push(
                mapping
                    .iter()
                    .map(|slot| slot.expect("complete mapping"))
                    .collect(),
            );
            return;
        }

        let u = depth;
        for v in 0..n {
            if used[v] || deg1[u] != deg2[v] {
                continue;
            }

            let mut consistent = true;
            for prev_u in 0..depth {
                if let Some(prev_v) = mapping[prev_u]
                    && (adj1[u][prev_u] != adj2[v][prev_v] || adj1[prev_u][u] != adj2[prev_v][v])
                {
                    consistent = false;
                    break;
                }
            }
            if !consistent {
                continue;
            }

            mapping[u] = Some(v);
            used[v] = true;
            backtrack(
                depth + 1,
                n,
                adj1,
                adj2,
                deg1,
                deg2,
                mapping,
                used,
                limit,
                results,
            );
            mapping[u] = None;
            used[v] = false;

            if limit.is_some_and(|bound| results.len() >= bound) {
                return;
            }
        }
    }

    backtrack(
        0,
        n,
        &adj1,
        &adj2,
        &deg1_map,
        &deg2_map,
        &mut mapping,
        &mut used,
        limit,
        &mut results,
    );
    results
}

/// Check if two graphs are isomorphic (VF2 algorithm).
#[pyfunction]
#[pyo3(signature = (g1, g2))]
fn is_isomorphic(py: Python<'_>, g1: &Bound<'_, PyAny>, g2: &Bound<'_, PyAny>) -> PyResult<bool> {
    let gr1 = extract_graph(g1)?;
    let gr2 = extract_graph(g2)?;

    if gr1.is_directed() != gr2.is_directed() {
        return Err(NetworkXError::new_err(
            "Graphs G1 and G2 are not of the same type.",
        ));
    }
    if gr1.node_count_original() != gr2.node_count_original()
        || gr1.edge_count_original() != gr2.edge_count_original()
    {
        return Ok(false);
    }

    if gr1.is_directed() {
        let dg1 = gr1.digraph().expect("is_directed checked above");
        let dg2 = gr2.digraph().expect("is_directed checked above");
        Ok(py.allow_threads(|| fnx_algorithms::is_isomorphic_directed(dg1, dg2)))
    } else {
        let inner1 = gr1.undirected();
        let inner2 = gr2.undirected();
        Ok(py.allow_threads(|| fnx_algorithms::is_isomorphic(inner1, inner2)))
    }
}

#[pyfunction]
#[pyo3(signature = (g1, g2))]
fn vf2pp_isomorphism_rust(
    py: Python<'_>,
    g1: &Bound<'_, PyAny>,
    g2: &Bound<'_, PyAny>,
) -> PyResult<Option<PyObject>> {
    let gr1 = extract_graph(g1)?;
    let gr2 = extract_graph(g2)?;

    if gr1.is_directed() != gr2.is_directed() {
        return Ok(None);
    }

    let mappings = if gr1.is_directed() {
        let dg1 = gr1.digraph().expect("is_directed checked above");
        let dg2 = gr2.digraph().expect("is_directed checked above");
        py.allow_threads(|| directed_isomorphism_mappings(dg1, dg2, Some(1)))
    } else {
        let inner1 = gr1.undirected();
        let inner2 = gr2.undirected();
        py.allow_threads(|| undirected_isomorphism_mappings(inner1, inner2, Some(1)))
    };

    let Some(mapping) = mappings.first() else {
        return Ok(None);
    };

    let nodes1 = if gr1.is_directed() {
        gr1.digraph()
            .expect("is_directed checked above")
            .nodes_ordered()
    } else {
        gr1.undirected().nodes_ordered()
    };
    let nodes2 = if gr2.is_directed() {
        gr2.digraph()
            .expect("is_directed checked above")
            .nodes_ordered()
    } else {
        gr2.undirected().nodes_ordered()
    };

    let dict = PyDict::new(py);
    for (left_idx, &right_idx) in mapping.iter().enumerate() {
        dict.set_item(
            gr1.py_node_key(py, nodes1[left_idx]),
            gr2.py_node_key(py, nodes2[right_idx]),
        )?;
    }
    Ok(Some(dict.into_any().unbind()))
}

#[pyfunction]
#[pyo3(signature = (g1, g2))]
fn vf2pp_all_isomorphisms_rust(
    py: Python<'_>,
    g1: &Bound<'_, PyAny>,
    g2: &Bound<'_, PyAny>,
) -> PyResult<Vec<PyObject>> {
    let gr1 = extract_graph(g1)?;
    let gr2 = extract_graph(g2)?;

    if gr1.is_directed() != gr2.is_directed() {
        return Ok(Vec::new());
    }

    let mappings = if gr1.is_directed() {
        let dg1 = gr1.digraph().expect("is_directed checked above");
        let dg2 = gr2.digraph().expect("is_directed checked above");
        py.allow_threads(|| directed_isomorphism_mappings(dg1, dg2, None))
    } else {
        let inner1 = gr1.undirected();
        let inner2 = gr2.undirected();
        py.allow_threads(|| undirected_isomorphism_mappings(inner1, inner2, None))
    };

    let nodes1 = if gr1.is_directed() {
        gr1.digraph()
            .expect("is_directed checked above")
            .nodes_ordered()
    } else {
        gr1.undirected().nodes_ordered()
    };
    let nodes2 = if gr2.is_directed() {
        gr2.digraph()
            .expect("is_directed checked above")
            .nodes_ordered()
    } else {
        gr2.undirected().nodes_ordered()
    };

    mappings
        .into_iter()
        .map(|mapping| {
            let dict = PyDict::new(py);
            for (left_idx, right_idx) in mapping.into_iter().enumerate() {
                dict.set_item(
                    gr1.py_node_key(py, nodes1[left_idx]),
                    gr2.py_node_key(py, nodes2[right_idx]),
                )?;
            }
            Ok(dict.into_any().unbind())
        })
        .collect()
}

#[pyfunction]
#[pyo3(signature = (g1, g2, upper_bound=None))]
fn graph_edit_distance_common_rust(
    py: Python<'_>,
    g1: &Bound<'_, PyAny>,
    g2: &Bound<'_, PyAny>,
    upper_bound: Option<f64>,
) -> PyResult<Option<PyObject>> {
    let gr1 = extract_graph(g1)?;
    let gr2 = extract_graph(g2)?;

    if gr1.is_multigraph() || gr2.is_multigraph() || gr1.is_directed() != gr2.is_directed() {
        return Ok(None);
    }

    let result = if gr1.is_directed() {
        let dg1 = gr1.digraph().expect("is_directed checked above");
        let dg2 = gr2.digraph().expect("is_directed checked above");
        py.allow_threads(|| {
            fnx_algorithms::common_graph_edit_distance_mappings(dg1, dg2, upper_bound)
        })
    } else {
        let inner1 = gr1.undirected();
        let inner2 = gr2.undirected();
        py.allow_threads(|| {
            fnx_algorithms::common_graph_edit_distance_mappings(inner1, inner2, upper_bound)
        })
    };

    let Some(result) = result else {
        return Ok(None);
    };

    let nodes1 = if gr1.is_directed() {
        gr1.digraph()
            .expect("is_directed checked above")
            .nodes_ordered()
    } else {
        gr1.undirected().nodes_ordered()
    };
    let nodes2 = if gr2.is_directed() {
        gr2.digraph()
            .expect("is_directed checked above")
            .nodes_ordered()
    } else {
        gr2.undirected().nodes_ordered()
    };

    let mappings = PyList::empty(py);
    for mapping in result.mappings {
        let dict = PyDict::new(py);
        for (left_idx, maybe_right_idx) in mapping.into_iter().enumerate() {
            if let Some(right_idx) = maybe_right_idx {
                dict.set_item(
                    gr1.py_node_key(py, nodes1[left_idx]),
                    gr2.py_node_key(py, nodes2[right_idx]),
                )?;
            }
        }
        mappings.append(dict)?;
    }

    let payload = PyTuple::new(
        py,
        [mappings.as_any(), result.cost.into_pyobject(py)?.as_any()],
    )?;
    Ok(Some(payload.into_any().unbind()))
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
    if gr1.node_count_original() != gr2.node_count_original()
        || gr1.edge_count_original() != gr2.edge_count_original()
        || gr1.total_degree_sequence() != gr2.total_degree_sequence()
    {
        return Ok(false);
    }
    if gr1.is_directed() || gr2.is_directed() {
        return Err(NetworkXNotImplemented::new_err(
            "not implemented for directed type",
        ));
    }
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
    if gr1.node_count_original() != gr2.node_count_original()
        || gr1.edge_count_original() != gr2.edge_count_original()
        || gr1.total_degree_sequence() != gr2.total_degree_sequence()
    {
        return Ok(false);
    }
    if gr1.is_directed() || gr2.is_directed() {
        return Err(NetworkXNotImplemented::new_err(
            "not implemented for directed type",
        ));
    }
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
    // `weight = None` -> every node weight 1 (networkx ignores node attrs then).
    let result = py.allow_threads(|| fnx_algorithms::min_weighted_vertex_cover(inner, weight));
    // NetworkX returns a set of nodes (ignoring weights).
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
        // br-r37-c1-dxm71: random.choice(seq) == seq[random._randbelow(len(seq))];
        // call _randbelow directly so we never clone the whole node list into a
        // Python list just to pick one element.
        let i = random
            .call_method1("_randbelow", (ordered_nodes.len(),))?
            .extract::<usize>()?;
        required.push(ordered_nodes[i].clone());
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

    // br-r37-c1-dxm71: run the peeling loop on node INDICES with a Vec<bool>
    // ``blocked`` and per-node adjacency built once. The previous loop cloned
    // the entire remaining ``available_nodes`` Vec<String> into a Python list
    // on every iteration (to feed random.choice) and used a HashSet<String>
    // for blocking — O(N) string clones + a PyO3 list build per pick, the
    // dominant cost (~7x slower than nx). Using ``random._randbelow(len)`` for
    // the index keeps nx's exact RNG sequence while never materialising the
    // node list in Python. Output is byte-identical (same index per pick, same
    // greedy removal order, same node strings).
    let n = ordered_nodes.len();
    let node_to_idx: HashMap<&str, usize> = ordered_nodes
        .iter()
        .enumerate()
        .map(|(i, node)| (node.as_str(), i))
        .collect();
    let mut adj: Vec<Vec<usize>> = vec![Vec::new(); n];
    for (i, node) in ordered_nodes.iter().enumerate() {
        if let Some(neighbors) = inner.neighbors(node) {
            for nbr in neighbors {
                if let Some(&j) = node_to_idx.get(nbr) {
                    adj[i].push(j);
                }
            }
        }
    }

    let mut blocked = vec![false; n];
    let mut indep_idx: Vec<usize> = Vec::with_capacity(n);
    for node in &required {
        let i = node_to_idx[node.as_str()];
        indep_idx.push(i);
        blocked[i] = true;
        for &j in &adj[i] {
            blocked[j] = true;
        }
    }

    // Candidate indices in node-insertion order (matches the previous
    // ``ordered_nodes`` filter order).
    let mut available: Vec<usize> = (0..n).filter(|&i| !blocked[i]).collect();
    while !available.is_empty() {
        let i = random
            .call_method1("_randbelow", (available.len(),))?
            .extract::<usize>()?;
        let chosen = available[i];
        indep_idx.push(chosen);
        blocked[chosen] = true;
        for &j in &adj[chosen] {
            blocked[j] = true;
        }
        // Drops the chosen node and its neighbours together — identical to the
        // old ``remove(index)`` + neighbour ``retain`` (order preserved).
        available.retain(|&idx| !blocked[idx]);
    }

    Ok(indep_idx
        .into_iter()
        .map(|idx| gr.py_node_key(py, &ordered_nodes[idx]))
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

    let random_inst = random_module.getattr("_inst")?;
    maximal_independent_set_with_random(py, &gr, inner, &initial_nodes, random_inst.as_any())
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
    _py: Python<'_>,
    g1: &Bound<'_, PyAny>,
    g2: &Bound<'_, PyAny>,
) -> PyResult<bool> {
    let gr1 = extract_graph(g1)?;
    let gr2 = extract_graph(g2)?;
    Ok(gr1.node_count_original() == gr2.node_count_original()
        && gr1.edge_count_original() == gr2.edge_count_original()
        && gr1.total_degree_sequence() == gr2.total_degree_sequence())
}

/// Check if a graph is planar (can be drawn without edge crossings).
#[pyfunction]
#[pyo3(signature = (g,))]
fn is_planar(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<bool> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    Ok(py.allow_threads(|| fnx_algorithms::is_planar(inner)))
}

/// Exact planarity test via the Left-Right algorithm (boolean only).
///
/// Unlike `is_planar` (a necessary-only Euler-bound check), this correctly
/// rejects K5, K3,3, Petersen and every other non-planar graph, matching
/// NetworkX's `check_planarity(G)[0]`.
#[pyfunction]
#[pyo3(signature = (g,))]
fn is_planar_lr(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<bool> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    Ok(py.allow_threads(|| fnx_algorithms::is_planar_lr(inner)))
}

/// Return whether Euler's simple loopless bound proves non-planarity.
#[pyfunction]
#[pyo3(signature = (g,))]
fn planarity_euler_reject(g: &Bound<'_, PyAny>) -> PyResult<Option<bool>> {
    let gr = extract_graph(g)?;
    let GraphRef::Undirected(pg) = &gr else {
        return Ok(None);
    };
    let inner = &pg.inner;
    let node_count = inner.node_count();
    if node_count < 3 {
        return Ok(Some(false));
    }
    let edge_bound = (3 * node_count) - 6;
    if inner.edge_count() <= edge_bound {
        return Ok(Some(false));
    }
    if fnx_algorithms::number_of_selfloops(inner) != 0 {
        return Ok(Some(false));
    }
    Ok(Some(true))
}

/// Check if a graph is chordal (every cycle of length 4+ has a chord).
#[pyfunction]
#[pyo3(signature = (g,))]
fn is_chordal(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<bool> {
    let gr = extract_graph(g)?;
    // br-r37-c1-djohp/br-r37-c1-tiy27: nx rejects multigraph before
    // directed on MultiDiGraph; mirror that guard precedence.
    require_not_multigraph(&gr)?;
    // br-r37-c1-ewpss: see find_cliques for rationale. is_chordal is
    // an undirected-graph concept; nx and the public wrapper both
    // reject directed input.
    require_undirected(&gr, "is_chordal")?;
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
    // br-r37-c1-0xhhq: same directed-collapse defect as the rest of
    // the distance-metric family. Public-API users go through
    // fnx.barycenter which handles directed via shortest_path_length
    // (br-r37-c1-ecqmz).
    require_undirected(&gr, "barycenter")?;
    let inner = gr.undirected();
    // br-r37-c1-djohp: nx raises NetworkXPointlessConcept on empty
    // input; mirror that here so direct callers see a clear error
    // rather than the empty list the kernel would otherwise return.
    if inner.node_count() == 0 {
        return Err(crate::NetworkXPointlessConcept::new_err("G has no nodes."));
    }
    if inner.node_count() > 0 {
        let connected = py.allow_threads(|| fnx_algorithms::is_connected(inner).is_connected);
        if !connected {
            // br-r37-c1-ftorb: nx's error message includes the graph
            // repr ("Graph with N nodes and M edges"). Mirror that
            // shape so users matching on the message string keep
            // working when migrating from nx.
            let kind = if gr.is_directed() { "DiGraph" } else { "Graph" };
            let msg = format!(
                "Input graph {} with {} nodes and {} edges is disconnected, \
                 so every induced subgraph has infinite barycentricity.",
                kind,
                inner.node_count(),
                inner.edge_count(),
            );
            return Err(NetworkXNoPath::new_err(msg));
        }
    }
    // br-r37-c1-baryidx: the lib.rs kernel runs a String-keyed
    // HashMap<&str,usize> BFS from every source (re-resolving neighbor names
    // and allocating a Vec per visit) — O(V*(V+E)) but with a heavy per-op
    // constant, ~23-80x slower than nx. Replay the graph's integer adjacency
    // instead (same node-index iteration order, integer distance sums), which
    // matches nx's argmin tie-set exactly while dropping the string tax.
    let nodes = inner.nodes_ordered();
    let adjacency = graph_shortest_path_adjacency_indices(inner, &nodes);
    let result = py.allow_threads(|| barycenter_from_adjacency(&adjacency));
    Ok(result
        .iter()
        .map(|&idx| gr.py_node_key(py, nodes[idx]))
        .collect())
}

/// Barycenter over an integer adjacency list: BFS from every source, sum the
/// (unweighted) distances, and return the node indices whose total is minimal,
/// in ascending node-index order. Mirrors `fnx_algorithms::barycenter` (which
/// iterates `nodes_ordered` and keeps the min-total tie set) but in integer
/// index space. Distance sums are exact integers, so the min/tie comparison is
/// byte-identical to the kernel's f64-EPSILON test.
fn barycenter_from_adjacency(adjacency: &[Vec<usize>]) -> Vec<usize> {
    let node_count = adjacency.len();
    if node_count == 0 {
        return Vec::new();
    }
    let mut seen_stamp = vec![0u32; node_count];
    let mut dist = vec![0usize; node_count];
    let mut queue: std::collections::VecDeque<usize> = std::collections::VecDeque::new();
    let mut totals: Vec<(usize, usize)> = Vec::with_capacity(node_count);
    let mut min_total = usize::MAX;

    for source in 0..node_count {
        let stamp = (source as u32) + 1;
        seen_stamp[source] = stamp;
        dist[source] = 0;
        queue.clear();
        queue.push_back(source);
        let mut reached = 0usize;
        let mut total = 0usize;

        while let Some(u) = queue.pop_front() {
            reached += 1;
            let d = dist[u];
            total += d;
            for &v in &adjacency[u] {
                if seen_stamp[v] != stamp {
                    seen_stamp[v] = stamp;
                    dist[v] = d + 1;
                    queue.push_back(v);
                }
            }
        }

        // Disconnected source (shouldn't happen — binding gates on connected —
        // but keep the kernel's skip for parity).
        if reached != node_count {
            continue;
        }
        if total < min_total {
            min_total = total;
        }
        totals.push((source, total));
    }

    totals
        .into_iter()
        .filter(|&(_, total)| total == min_total)
        .map(|(index, _)| index)
        .collect()
}

/// Native fast path for `find_cycle(G)` — the common case
/// `orientation=None, source=None`, simple (non-multi) graph. A faithful,
/// line-by-line port of networkx's fused `edge_dfs` + `find_cycle` over an
/// integer adjacency list (successors for directed, neighbors for undirected;
/// each row in `G.edges(node)` order). Returns the cycle edges as
/// `(tail, head)` index pairs in DFS-traversal direction, rotated to begin at
/// `final_node`, or `None` if the graph is acyclic. Identical to nx because the
/// traversal order, edge-id dedup (frozenset for undirected / ordered pair for
/// directed), and the active-path trim logic all match exactly.
fn find_cycle_simple_dfs<'a>(
    node_count: usize,
    directed: bool,
    neighbors: impl Fn(usize) -> &'a [usize],
) -> Option<Vec<(usize, usize)>> {
    let mut explored: HashSet<usize> = HashSet::new();
    let edge_id =
        |u: usize, v: usize| -> (usize, usize) { if directed || u <= v { (u, v) } else { (v, u) } };

    for start in 0..node_count {
        if explored.contains(&start) {
            continue;
        }

        // find_cycle per-start consumer state
        let mut edges: Vec<(usize, usize)> = Vec::new();
        let mut seen: HashSet<usize> = HashSet::new();
        seen.insert(start);
        let mut active_nodes: HashSet<usize> = HashSet::new();
        active_nodes.insert(start);
        let mut previous_head: Option<usize> = None;

        // edge_dfs per-start state (fresh for each start, like nx)
        let mut visited_edges: HashSet<(usize, usize)> = HashSet::new();
        let mut visited_nodes: HashSet<usize> = HashSet::new();
        let mut pos: HashMap<usize, usize> = HashMap::new();
        let mut stack: Vec<usize> = vec![start];

        while let Some(&current) = stack.last() {
            if !visited_nodes.contains(&current) {
                visited_nodes.insert(current);
                pos.insert(current, 0);
            }
            let p = *pos.get(&current).expect("pos initialized above");
            let row = neighbors(current);
            if p >= row.len() {
                stack.pop();
                continue;
            }
            *pos.get_mut(&current).expect("pos initialized above") = p + 1;
            let nbr = row[p];
            let eid = edge_id(current, nbr);
            if visited_edges.contains(&eid) {
                continue;
            }
            visited_edges.insert(eid);
            stack.push(nbr);

            // === yield (current, nbr) into the find_cycle consumer ===
            let (tail, head) = (current, nbr);
            if explored.contains(&head) {
                continue;
            }
            if let Some(ph) = previous_head
                && tail != ph
            {
                loop {
                    match edges.pop() {
                        None => {
                            edges.clear();
                            active_nodes.clear();
                            active_nodes.insert(tail);
                            break;
                        }
                        Some(popped) => {
                            active_nodes.remove(&popped.1);
                        }
                    }
                    if let Some(last) = edges.last()
                        && tail == last.1
                    {
                        break;
                    }
                }
            }
            edges.push((tail, head));

            if active_nodes.contains(&head) {
                // cycle found — rotate to begin at final_node (== head)
                let final_node = head;
                let start_idx = edges
                    .iter()
                    .position(|&(t, _)| t == final_node)
                    .unwrap_or(0);
                return Some(edges[start_idx..].to_vec());
            }
            seen.insert(head);
            active_nodes.insert(head);
            previous_head = Some(head);
        }

        for &node in &seen {
            explored.insert(node);
        }
    }

    None
}

/// `find_cycle(G)` fast path (orientation=None, source=None, simple graph).
/// Returns the cycle edges as `(u, v)` node-key pairs, or `None` if acyclic.
/// The Python wrapper raises `NetworkXNoCycle` on `None` and keeps the verbatim
/// Python port for multigraph / explicit source / non-None orientation.
#[pyfunction]
#[pyo3(signature = (g,))]
fn find_cycle_simple(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
) -> PyResult<Option<Vec<(PyObject, PyObject)>>> {
    let gr = extract_graph(g)?;
    let directed = gr.is_directed();
    // br-r37-c1-7yn51: query integer adjacency ON DEMAND (neighbors_indices /
    // successors_indices) so an early-exit cycle costs only the rows actually
    // visited — NOT an O(V+E) whole-graph adjacency build (which regressed the
    // common dense-graph case 200x+). nodes_ordered() is O(V) name refs, only
    // used to map the (small) found cycle's indices back to node keys.
    let cycle = if directed {
        let dg = gr.digraph().expect("is_directed checked above");
        let n = dg.node_count();
        py.allow_threads(|| {
            find_cycle_simple_dfs(n, true, |i| dg.successors_indices(i).unwrap_or(&[]))
        })
    } else {
        let ug = gr.undirected();
        let n = ug.node_count();
        py.allow_threads(|| {
            find_cycle_simple_dfs(n, false, |i| ug.neighbors_indices(i).unwrap_or(&[]))
        })
    };
    let result = cycle.map(|edges| {
        let nodes = if directed {
            gr.digraph().expect("checked").nodes_ordered()
        } else {
            gr.undirected().nodes_ordered()
        };
        edges
            .iter()
            .map(|&(u, v)| (gr.py_node_key(py, nodes[u]), gr.py_node_key(py, nodes[v])))
            .collect::<Vec<_>>()
    });
    Ok(result)
}

// ===========================================================================
// Tree recognition — is_arborescence, is_branching
// ===========================================================================

/// Return True if `G` is an arborescence (a directed rooted tree).
#[pyfunction]
#[pyo3(signature = (g,))]
fn is_arborescence(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<bool> {
    let gr = extract_graph(g)?;
    if !gr.is_directed() {
        return Err(crate::NetworkXNotImplemented::new_err(
            "not implemented for undirected type",
        ));
    }
    {
        let dg_ref = gr.digraph().expect("is_directed checked above");
        if dg_ref.node_count() == 0 {
            return Err(crate::NetworkXPointlessConcept::new_err("G has no nodes."));
        }
        Ok(py.allow_threads(|| fnx_algorithms::is_arborescence(dg_ref)))
    }
}

/// Return True if `G` is a branching (a directed forest).
#[pyfunction]
#[pyo3(signature = (g,))]
fn is_branching(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<bool> {
    let gr = extract_graph(g)?;
    if !gr.is_directed() {
        return Err(crate::NetworkXNotImplemented::new_err(
            "not implemented for undirected type",
        ));
    }
    {
        let dg_ref = gr.digraph().expect("is_directed checked above");
        if dg_ref.node_count() == 0 {
            return Err(crate::NetworkXPointlessConcept::new_err("G has no nodes."));
        }
        Ok(py.allow_threads(|| fnx_algorithms::is_branching(dg_ref)))
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
    validate_node(&gr, &key, node, "Node")?;
    match &gr {
        GraphRef::Undirected(pg) => Ok({
            let __pg_inner = &pg.inner;
            py.allow_threads(|| fnx_algorithms::is_isolate(__pg_inner, &key))
        }),
        GraphRef::Directed { dg, .. } => Ok({
            let __dg_inner = &dg.inner;
            py.allow_threads(|| fnx_algorithms::is_isolate_directed(__dg_inner, &key))
        }),
        _ => {
            if gr.is_directed() {
                Ok({
                    let __gr_digraph = gr.digraph().expect("is_directed checked above");
                    py.allow_threads(|| fnx_algorithms::is_isolate_directed(__gr_digraph, &key))
                })
            } else {
                Ok({
                    let __gr_undirected = gr.undirected();
                    py.allow_threads(|| fnx_algorithms::is_isolate(__gr_undirected, &key))
                })
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
        GraphRef::Undirected(pg) => {
            let __pg_inner = &pg.inner;
            py.allow_threads(|| fnx_algorithms::isolates(__pg_inner))
        }
        GraphRef::Directed { dg, .. } => {
            let __dg_inner = &dg.inner;
            py.allow_threads(|| fnx_algorithms::isolates_directed(__dg_inner))
        }
        _ => {
            if gr.is_directed() {
                {
                    let __gr_digraph = gr.digraph().expect("is_directed checked above");
                    py.allow_threads(|| fnx_algorithms::isolates_directed(__gr_digraph))
                }
            } else {
                {
                    let __gr_undirected = gr.undirected();
                    py.allow_threads(|| fnx_algorithms::isolates(__gr_undirected))
                }
            }
        }
    };
    Ok(result.iter().map(|n| gr.py_node_key(py, n)).collect())
}

/// Return the number of isolate nodes.
#[pyfunction]
#[pyo3(signature = (g,))]
fn number_of_isolates(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<usize> {
    let gr = extract_graph(g)?;
    match &gr {
        GraphRef::Undirected(pg) => Ok({
            let __pg_inner = &pg.inner;
            py.allow_threads(|| fnx_algorithms::number_of_isolates(__pg_inner))
        }),
        GraphRef::Directed { dg, .. } => Ok({
            let __dg_inner = &dg.inner;
            py.allow_threads(|| fnx_algorithms::number_of_isolates_directed(__dg_inner))
        }),
        _ => {
            if gr.is_directed() {
                Ok({
                    let __gr_digraph = gr.digraph().expect("is_directed checked above");
                    py.allow_threads(|| fnx_algorithms::number_of_isolates_directed(__gr_digraph))
                })
            } else {
                Ok({
                    let __gr_undirected = gr.undirected();
                    py.allow_threads(|| fnx_algorithms::number_of_isolates(__gr_undirected))
                })
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
            let __pg_inner = &pg.inner;
            py.allow_threads(|| {
                fnx_algorithms::edge_boundary(__pg_inner, &s1_refs, s2_refs.as_deref())
            })
        }
        GraphRef::Directed { dg, .. } => {
            let __dg_inner = &dg.inner;
            py.allow_threads(|| {
                fnx_algorithms::edge_boundary_directed(__dg_inner, &s1_refs, s2_refs.as_deref())
            })
        }
        _ => {
            if gr.is_directed() {
                {
                    let __gr_digraph = gr.digraph().expect("is_directed checked above");
                    py.allow_threads(|| {
                        fnx_algorithms::edge_boundary_directed(
                            __gr_digraph,
                            &s1_refs,
                            s2_refs.as_deref(),
                        )
                    })
                }
            } else {
                {
                    let __gr_undirected = gr.undirected();
                    py.allow_threads(|| {
                        fnx_algorithms::edge_boundary(__gr_undirected, &s1_refs, s2_refs.as_deref())
                    })
                }
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
            let __pg_inner = &pg.inner;
            py.allow_threads(|| {
                fnx_algorithms::node_boundary(__pg_inner, &s1_refs, s2_refs.as_deref())
            })
        }
        GraphRef::Directed { dg, .. } => {
            let __dg_inner = &dg.inner;
            py.allow_threads(|| {
                fnx_algorithms::node_boundary_directed(__dg_inner, &s1_refs, s2_refs.as_deref())
            })
        }
        _ => {
            if gr.is_directed() {
                {
                    let __gr_digraph = gr.digraph().expect("is_directed checked above");
                    py.allow_threads(|| {
                        fnx_algorithms::node_boundary_directed(
                            __gr_digraph,
                            &s1_refs,
                            s2_refs.as_deref(),
                        )
                    })
                }
            } else {
                {
                    let __gr_undirected = gr.undirected();
                    py.allow_threads(|| {
                        fnx_algorithms::node_boundary(__gr_undirected, &s1_refs, s2_refs.as_deref())
                    })
                }
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
            let __pg_inner = &pg.inner;
            py.allow_threads(|| {
                fnx_algorithms::cut_size(__pg_inner, &s1_refs, s2_refs.as_deref(), weight)
            })
        }
        GraphRef::Directed { dg, .. } => {
            let __dg_inner = &dg.inner;
            py.allow_threads(|| {
                fnx_algorithms::cut_size_directed(__dg_inner, &s1_refs, s2_refs.as_deref(), weight)
            })
        }
        _ => {
            if gr.is_directed() {
                {
                    let __gr_digraph = gr.digraph().expect("is_directed checked above");
                    py.allow_threads(|| {
                        fnx_algorithms::cut_size_directed(
                            __gr_digraph,
                            &s1_refs,
                            s2_refs.as_deref(),
                            weight,
                        )
                    })
                }
            } else {
                {
                    let __gr_undirected = gr.undirected();
                    py.allow_threads(|| {
                        fnx_algorithms::cut_size(
                            __gr_undirected,
                            &s1_refs,
                            s2_refs.as_deref(),
                            weight,
                        )
                    })
                }
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
            let __pg_inner = &pg.inner;
            py.allow_threads(|| {
                fnx_algorithms::normalized_cut_size(
                    __pg_inner,
                    &s1_refs,
                    s2_refs.as_deref(),
                    weight,
                )
            })
        }
        GraphRef::Directed { dg, .. } => {
            let __dg_inner = &dg.inner;
            py.allow_threads(|| {
                fnx_algorithms::normalized_cut_size_directed(
                    __dg_inner,
                    &s1_refs,
                    s2_refs.as_deref(),
                    weight,
                )
            })
        }
        _ => {
            if gr.is_directed() {
                {
                    let __gr_digraph = gr.digraph().expect("is_directed checked above");
                    py.allow_threads(|| {
                        fnx_algorithms::normalized_cut_size_directed(
                            __gr_digraph,
                            &s1_refs,
                            s2_refs.as_deref(),
                            weight,
                        )
                    })
                }
            } else {
                {
                    let __gr_undirected = gr.undirected();
                    py.allow_threads(|| {
                        fnx_algorithms::normalized_cut_size(
                            __gr_undirected,
                            &s1_refs,
                            s2_refs.as_deref(),
                            weight,
                        )
                    })
                }
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
        GraphRef::Undirected(pg) => Ok({
            let __pg_inner = &pg.inner;
            py.allow_threads(|| fnx_algorithms::is_simple_path(__pg_inner, &key_refs))
        }),
        GraphRef::Directed { dg, .. } => Ok({
            let __dg_inner = &dg.inner;
            py.allow_threads(|| fnx_algorithms::is_simple_path_directed(__dg_inner, &key_refs))
        }),
        _ => {
            if gr.is_directed() {
                Ok({
                    let __gr_digraph = gr.digraph().expect("is_directed checked above");
                    py.allow_threads(|| {
                        fnx_algorithms::is_simple_path_directed(__gr_digraph, &key_refs)
                    })
                })
            } else {
                Ok({
                    let __gr_undirected = gr.undirected();
                    py.allow_threads(|| fnx_algorithms::is_simple_path(__gr_undirected, &key_refs))
                })
            }
        }
    }
}

// ===========================================================================
// Matching validators — is_matching, is_maximal_matching, is_perfect_matching
// ===========================================================================

/// Extract edge pairs from any iterable of 2-tuples (list, set, etc.).
fn extract_matching_edges(
    py: Python<'_>,
    matching: &Bound<'_, PyAny>,
) -> PyResult<Vec<(String, String)>> {
    use pyo3::types::PyDict;
    // br-matchingdict: nx accepts both ``set`` of (u,v) edges and
    // ``dict``-form matchings ({u: v, v: u, ...}). For the dict form,
    // iterating yields keys only, so the per-element ``get_item(0)``
    // path fails. Detect dict-shape input and read both u and the
    // mate via ``__getitem__`` instead.
    if let Ok(dict) = matching.downcast::<PyDict>() {
        let mut edges = Vec::with_capacity(dict.len());
        let mut seen = std::collections::HashSet::<(String, String)>::new();
        for (k, v) in dict.iter() {
            let u_s = node_key_to_string(py, &k)?;
            let v_s = node_key_to_string(py, &v)?;
            // Each unordered pair appears twice (u→v and v→u); skip
            // the duplicate so the validator sees a clean edge list.
            let canon = if u_s <= v_s {
                (u_s.clone(), v_s.clone())
            } else {
                (v_s.clone(), u_s.clone())
            };
            if seen.insert(canon) {
                edges.push((u_s, v_s));
            }
        }
        return Ok(edges);
    }

    let mut edges = Vec::new();
    for item in matching.try_iter()? {
        let pair = item?;
        let u = pair.get_item(0)?;
        let v = pair.get_item(1)?;
        edges.push((node_key_to_string(py, &u)?, node_key_to_string(py, &v)?));
    }
    Ok(edges)
}

/// Validate that every endpoint in ``edges`` is a node of ``inner``;
/// raise a NetworkXError matching nx's wording if not. nx's
/// ``is_matching`` raises (rather than returning False) when an
/// edge references a node missing from G.
fn ensure_matching_nodes_in_graph(
    inner: &fnx_classes::Graph,
    edges: &[(String, String)],
) -> PyResult<()> {
    for (u, v) in edges {
        if !inner.has_node(u) {
            return Err(NetworkXError::new_err(format!(
                "matching contains edge ({u}, {v}) with node not in G"
            )));
        }
        if !inner.has_node(v) {
            return Err(NetworkXError::new_err(format!(
                "matching contains edge ({u}, {v}) with node not in G"
            )));
        }
    }
    Ok(())
}

/// Return True if `matching` is a valid matching of `G`.
#[pyfunction]
#[pyo3(signature = (g, matching))]
fn is_matching(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    matching: &Bound<'_, PyAny>,
) -> PyResult<bool> {
    let gr = extract_graph(g)?;
    require_undirected(&gr, "is_matching")?;
    let inner = gr.undirected();
    let edges = extract_matching_edges(py, matching)?;
    ensure_matching_nodes_in_graph(inner, &edges)?;
    Ok(py.allow_threads(|| fnx_algorithms::is_matching(inner, &edges)))
}

/// Return True if `matching` is a maximal matching of `G`.
#[pyfunction]
#[pyo3(signature = (g, matching))]
fn is_maximal_matching(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    matching: &Bound<'_, PyAny>,
) -> PyResult<bool> {
    let gr = extract_graph(g)?;
    require_undirected(&gr, "is_maximal_matching")?;
    let inner = gr.undirected();
    let edges = extract_matching_edges(py, matching)?;
    ensure_matching_nodes_in_graph(inner, &edges)?;
    Ok(py.allow_threads(|| fnx_algorithms::is_maximal_matching(inner, &edges)))
}

/// Return True if `matching` is a perfect matching of `G`.
#[pyfunction]
#[pyo3(signature = (g, matching))]
fn is_perfect_matching(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    matching: &Bound<'_, PyAny>,
) -> PyResult<bool> {
    let gr = extract_graph(g)?;
    require_undirected(&gr, "is_perfect_matching")?;
    let inner = gr.undirected();
    let edges = extract_matching_edges(py, matching)?;
    ensure_matching_nodes_in_graph(inner, &edges)?;
    Ok(py.allow_threads(|| fnx_algorithms::is_perfect_matching(inner, &edges)))
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
        let result = py.allow_threads(|| fnx_algorithms::simple_cycles(dg_ref));
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
        GraphRef::Undirected(pg) => {
            let __pg_inner = &pg.inner;
            py.allow_threads(|| fnx_algorithms::find_cycle_undirected(__pg_inner))
        }
        GraphRef::Directed { dg, .. } => {
            let __dg_inner = &dg.inner;
            py.allow_threads(|| fnx_algorithms::find_cycle_directed(__dg_inner))
        }
        _ => {
            if gr.is_directed() {
                {
                    let __gr_digraph = gr.digraph().expect("is_directed checked above");
                    py.allow_threads(|| fnx_algorithms::find_cycle_directed(__gr_digraph))
                }
            } else {
                {
                    let __gr_undirected = gr.undirected();
                    py.allow_threads(|| fnx_algorithms::find_cycle_undirected(__gr_undirected))
                }
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
) -> PyResult<PyObject> {
    sync_rust_attrs_if_available(g)?;
    let gr = extract_graph(g)?;
    let s = node_key_to_string(py, source)?;
    let t = node_key_to_string(py, target)?;
    validate_node(&gr, &s, source, "Source")?;
    validate_node(&gr, &t, target, "Target")?;
    let result = if let Some(weighted_projection) = gr.weighted_digraph_projection(weight) {
        {
            let __wp = weighted_projection.as_ref();
            py.allow_threads(|| {
                fnx_algorithms::dijkstra_path_length_typed_directed(__wp, &s, &t, weight)
            })
        }
    } else {
        let weighted_projection = gr.weighted_undirected_projection(weight);
        {
            let __wp = weighted_projection.as_ref();
            py.allow_threads(|| fnx_algorithms::dijkstra_path_length_typed(__wp, &s, &t, weight))
        }
    };
    match result {
        Some((d, all_int))
            if all_int
                && d.is_finite()
                && d.fract() == 0.0
                && d >= i128::MIN as f64
                && d <= i128::MAX as f64 =>
        {
            Ok(PyInt::new(py, d as i128).into_any().unbind())
        }
        Some((d, _)) => Ok(d.into_pyobject(py)?.into_any().unbind()),
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
    sync_rust_attrs_if_available(g)?;
    let gr = extract_graph(g)?;
    let s = node_key_to_string(py, source)?;
    let t = node_key_to_string(py, target)?;
    validate_node(&gr, &s, source, "Source")?;
    validate_node(&gr, &t, target, "Target")?;
    let result = if let Some(weighted_projection) = gr.weighted_digraph_projection(weight) {
        let bf = {
            let __wp = weighted_projection.as_ref();
            py.allow_threads(|| {
                fnx_algorithms::bellman_ford_shortest_paths_directed(__wp, &s, weight)
            })
        };
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
        {
            let __wp = weighted_projection.as_ref();
            py.allow_threads(|| fnx_algorithms::bellman_ford_path_length(__wp, &s, &t, weight))
        }
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
    sync_rust_attrs_if_available(g)?;
    let gr = extract_graph(g)?;
    let s = node_key_to_string(py, source)?;
    validate_node_str(&gr, &s, "Source")?;
    let (dists, paths) = if let Some(weighted_projection) = gr.weighted_digraph_projection(weight) {
        let __wp = weighted_projection.as_ref();
        py.allow_threads(|| fnx_algorithms::single_source_dijkstra_full_directed(__wp, &s, weight))
    } else {
        let weighted_projection = gr.weighted_undirected_projection(weight);
        let __wp = weighted_projection.as_ref();
        py.allow_threads(|| fnx_algorithms::single_source_dijkstra_full(__wp, &s, weight))
    };
    // weighted sp batch: discovery objects (a node displays as its
    // path's second-to-last element's row object; source as passed)
    // for BOTH the distance and path dicts, in kernel finalize order.
    let mut disp: std::collections::HashMap<String, PyObject> =
        std::collections::HashMap::with_capacity(paths.len() + 1);
    disp.insert(s.clone(), source.clone().unbind());
    for (node, p) in &paths {
        if p.len() >= 2 {
            disp.insert(node.clone(), gr.py_row_key(py, &p[p.len() - 2], node));
        }
    }
    let dist_dict = PyDict::new(py);
    for (node, d) in &dists {
        dist_dict.set_item(gr.disp_or_node_key(py, &disp, node), d)?;
    }
    let path_dict = PyDict::new(py);
    for (node, path) in &paths {
        let py_path: Vec<PyObject> = path
            .iter()
            .map(|n| gr.disp_or_node_key(py, &disp, n))
            .collect();
        path_dict.set_item(gr.disp_or_node_key(py, &disp, node), py_path)?;
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
    sync_rust_attrs_if_available(g)?;
    let gr = extract_graph(g)?;
    let s = node_key_to_string(py, source)?;
    validate_node_str(&gr, &s, "Source")?;
    let paths = if let Some(weighted_projection) = gr.weighted_digraph_projection(weight) {
        let __wp = weighted_projection.as_ref();
        py.allow_threads(|| fnx_algorithms::single_source_dijkstra_path_directed(__wp, &s, weight))
    } else {
        let weighted_projection = gr.weighted_undirected_projection(weight);
        let __wp = weighted_projection.as_ref();
        py.allow_threads(|| fnx_algorithms::single_source_dijkstra_path(__wp, &s, weight))
    };
    // weighted sp batch: discovery objects from the paths themselves.
    let dict = emit_paths_dict_discovery(py, &gr, &paths, &s, source.clone().unbind())?;
    Ok(dict.into_any())
}

/// Return distances from a single source using Dijkstra.
#[pyfunction]
#[pyo3(signature = (g, source, weight="weight", cutoff=None))]
fn single_source_dijkstra_path_length(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    source: &Bound<'_, PyAny>,
    weight: &str,
    cutoff: Option<f64>,
) -> PyResult<PyObject> {
    sync_rust_attrs_if_available(g)?;
    let gr = extract_graph(g)?;
    let s = node_key_to_string(py, source)?;
    validate_node_str(&gr, &s, "Source")?;
    // br-r37-c1-d58s8 scoreboard fix: length-only queries no longer
    // build full path Vecs — the with_pred kernels give the finalizing
    // PREDECESSOR (== path[-2], the discovery-object parent) alongside
    // finalize-ordered distances.
    let entries = if let Some(weighted_projection) = gr.weighted_digraph_projection(weight) {
        let __wp = weighted_projection.as_ref();
        py.allow_threads(|| {
            fnx_algorithms::single_source_dijkstra_path_length_typed_with_pred_directed(
                __wp, &s, weight, cutoff,
            )
        })
    } else {
        let weighted_projection = gr.weighted_undirected_projection(weight);
        let __wp = weighted_projection.as_ref();
        py.allow_threads(|| {
            fnx_algorithms::single_source_dijkstra_path_length_typed_with_pred(
                __wp, &s, weight, cutoff,
            )
        })
    };
    let mut disp: std::collections::HashMap<String, PyObject> =
        std::collections::HashMap::with_capacity(entries.len() + 1);
    disp.insert(s.clone(), source.clone().unbind());
    for (node, _, _, pred) in &entries {
        if let Some(p) = pred {
            disp.insert(node.clone(), gr.py_row_key(py, p, node));
        }
    }
    let dict = PyDict::new(py);
    for (node, d, all_int, _) in &entries {
        let key = gr.disp_or_node_key(py, &disp, node);
        if *all_int
            && d.is_finite()
            && d.fract() == 0.0
            && *d >= i128::MIN as f64
            && *d <= i128::MAX as f64
        {
            dict.set_item(key, PyInt::new(py, *d as i128))?;
        } else {
            dict.set_item(key, d)?;
        }
    }
    Ok(dict.into_any().unbind())
}

/// Return predecessor lists and distances from a single source using Dijkstra.
#[pyfunction]
#[pyo3(signature = (g, source, weight="weight", cutoff=None))]
fn dijkstra_predecessor_and_distance(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    source: &Bound<'_, PyAny>,
    weight: &str,
    cutoff: Option<f64>,
) -> PyResult<(PyObject, PyObject)> {
    sync_rust_attrs_if_available(g)?;
    let gr = extract_graph(g)?;
    let s = node_key_to_string(py, source)?;
    validate_node_str(&gr, &s, "Source")?;
    let (predecessors, distances) =
        if let Some(weighted_projection) = gr.weighted_digraph_projection(weight) {
            let __wp = weighted_projection.as_ref();
            py.allow_threads(|| {
                fnx_algorithms::dijkstra_predecessor_and_distance_directed(__wp, &s, weight, cutoff)
            })
        } else {
            let weighted_projection = gr.weighted_undirected_projection(weight);
            let __wp = weighted_projection.as_ref();
            py.allow_threads(|| {
                fnx_algorithms::dijkstra_predecessor_and_distance(__wp, &s, weight, cutoff)
            })
        };

    let mut disp: std::collections::HashMap<String, PyObject> =
        std::collections::HashMap::with_capacity(predecessors.len() + 1);
    disp.insert(s.clone(), source.clone().unbind());
    for (node, preds) in &predecessors {
        if node == &s {
            continue;
        }
        if let Some(first_pred) = preds.first() {
            disp.insert(node.clone(), gr.py_row_key(py, first_pred, node));
        }
    }

    let pred_dict = PyDict::new(py);
    for (node, preds) in &predecessors {
        let py_preds: Vec<PyObject> = preds
            .iter()
            .map(|pred| gr.disp_or_node_key(py, &disp, pred))
            .collect();
        pred_dict.set_item(gr.disp_or_node_key(py, &disp, node), py_preds)?;
    }

    let dist_dict = PyDict::new(py);
    for (node, distance, all_int) in &distances {
        let key = gr.disp_or_node_key(py, &disp, node);
        if *all_int
            && distance.is_finite()
            && distance.fract() == 0.0
            && *distance >= i128::MIN as f64
            && *distance <= i128::MAX as f64
        {
            dist_dict.set_item(key, PyInt::new(py, *distance as i128))?;
        } else {
            dist_dict.set_item(key, distance)?;
        }
    }

    Ok((pred_dict.into_any().unbind(), dist_dict.into_any().unbind()))
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
    sync_rust_attrs_if_available(g)?;
    let gr = extract_graph(g)?;
    let s = node_key_to_string(py, source)?;
    validate_node_str(&gr, &s, "Source")?;
    let result = if let Some(weighted_projection) = gr.weighted_digraph_projection(weight) {
        let bf = {
            let __wp = weighted_projection.as_ref();
            py.allow_threads(|| {
                fnx_algorithms::bellman_ford_shortest_paths_directed(__wp, &s, weight)
            })
        };
        if bf.negative_cycle_detected {
            None
        } else {
            // bf.distances is in nx's SPFA first-discovery order; preserve it
            // by emitting ordered Vecs instead of HashMaps. (br-r37-c1-e9rea)
            let predecessors = bf
                .predecessors
                .iter()
                .map(|entry| (entry.node.as_str(), entry.predecessor.as_deref()))
                .collect::<HashMap<_, _>>();
            let mut distances = Vec::with_capacity(bf.distances.len());
            let mut paths = Vec::with_capacity(bf.distances.len());
            for entry in &bf.distances {
                distances.push((entry.node.clone(), entry.distance));
                let mut path = vec![entry.node.clone()];
                let mut cur = entry.node.as_str();
                while let Some(Some(prev)) = predecessors.get(cur) {
                    path.push((*prev).to_owned());
                    cur = prev;
                }
                path.reverse();
                paths.push((entry.node.clone(), path));
            }
            Some((distances, paths))
        }
    } else {
        let weighted_projection = gr.weighted_undirected_projection(weight);
        let __wp = weighted_projection.as_ref();
        py.allow_threads(|| fnx_algorithms::single_source_bellman_ford(__wp, &s, weight))
    };
    match result {
        Some((dists, paths)) => {
            // weighted sp batch 2: discovery objects — a node displays as
            // its path's second-to-last element's row object (the SPFA
            // relaxation parent); source as passed.
            let mut disp: std::collections::HashMap<String, PyObject> =
                std::collections::HashMap::with_capacity(paths.len() + 1);
            disp.insert(s.clone(), source.clone().unbind());
            for (node, p) in &paths {
                if p.len() >= 2 {
                    disp.insert(node.clone(), gr.py_row_key(py, &p[p.len() - 2], node));
                }
            }
            let dist_dict = PyDict::new(py);
            for (node, d) in &dists {
                dist_dict.set_item(gr.disp_or_node_key(py, &disp, node), d)?;
            }
            let path_dict = PyDict::new(py);
            for (node, path) in &paths {
                let py_path: Vec<PyObject> = path
                    .iter()
                    .map(|n| gr.disp_or_node_key(py, &disp, n))
                    .collect();
                path_dict.set_item(gr.disp_or_node_key(py, &disp, node), py_path)?;
            }
            Ok((dist_dict.into_any().unbind(), path_dict.into_any().unbind()))
        }
        None => Err(crate::NetworkXUnbounded::new_err(
            "Negative cycle detected.",
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
    sync_rust_attrs_if_available(g)?;
    let gr = extract_graph(g)?;
    let s = node_key_to_string(py, source)?;
    validate_node_str(&gr, &s, "Source")?;
    let result = if let Some(weighted_projection) = gr.weighted_digraph_projection(weight) {
        let __wp = weighted_projection.as_ref();
        py.allow_threads(|| {
            fnx_algorithms::single_source_bellman_ford_path_directed(__wp, &s, weight)
        })
    } else {
        let weighted_projection = gr.weighted_undirected_projection(weight);
        let __wp = weighted_projection.as_ref();
        py.allow_threads(|| fnx_algorithms::single_source_bellman_ford_path(__wp, &s, weight))
    };
    match result {
        Some(paths) => {
            // weighted sp batch 2: discovery objects via the paths.
            let dict = emit_paths_dict_discovery(py, &gr, &paths, &s, source.clone().unbind())?;
            Ok(dict.into_any())
        }
        None => Err(crate::NetworkXUnbounded::new_err(
            "Negative cycle detected.",
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
    sync_rust_attrs_if_available(g)?;
    let gr = extract_graph(g)?;
    let s = node_key_to_string(py, source)?;
    validate_node_str(&gr, &s, "Source")?;
    // weighted sp batch 2: predecessors give the discovery objects (a
    // node displays as its SPFA relaxation parent's row object) without
    // a second walk — use the predecessor-carrying kernels.
    let result = if let Some(weighted_projection) = gr.weighted_digraph_projection(weight) {
        let bf = {
            let __wp = weighted_projection.as_ref();
            py.allow_threads(|| {
                fnx_algorithms::bellman_ford_shortest_paths_directed(__wp, &s, weight)
            })
        };
        if bf.negative_cycle_detected {
            None
        } else {
            let preds: std::collections::HashMap<String, Option<String>> = bf
                .predecessors
                .iter()
                .map(|e| (e.node.clone(), e.predecessor.clone()))
                .collect();
            Some((
                bf.distances
                    .iter()
                    .map(|e| (e.node.clone(), e.distance))
                    .collect::<Vec<_>>(),
                preds,
            ))
        }
    } else {
        let bf = {
            let weighted_projection = gr.weighted_undirected_projection(weight);
            let __wp = weighted_projection.as_ref();
            py.allow_threads(|| fnx_algorithms::bellman_ford_shortest_paths(__wp, &s, weight))
        };
        if bf.negative_cycle_detected {
            None
        } else {
            let preds: std::collections::HashMap<String, Option<String>> = bf
                .predecessors
                .iter()
                .map(|e| (e.node.clone(), e.predecessor.clone()))
                .collect();
            Some((
                bf.distances
                    .iter()
                    .map(|e| (e.node.clone(), e.distance))
                    .collect::<Vec<_>>(),
                preds,
            ))
        }
    };
    match result {
        Some((dists, preds)) => {
            let mut disp: std::collections::HashMap<String, PyObject> =
                std::collections::HashMap::with_capacity(dists.len() + 1);
            disp.insert(s.clone(), source.clone().unbind());
            for (node, _) in &dists {
                if let Some(Some(p)) = preds.get(node) {
                    disp.insert(node.clone(), gr.py_row_key(py, p, node));
                }
            }
            let dict = PyDict::new(py);
            for (node, d) in &dists {
                dict.set_item(gr.disp_or_node_key(py, &disp, node), d)?;
            }
            Ok(dict.into_any().unbind())
        }
        None => Err(crate::NetworkXUnbounded::new_err(
            "Negative cycle detected.",
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
    // br-r37-c1-stsp: reverse-BFS from `target` over integer adjacency
    // (undirected: neighbors, directed: predecessors), emitting `{node: path}`
    // with keys in BFS-discovery-from-target order — matching nx's
    // single_target_shortest_path dict-insertion order. The old kernel
    // collected results into a HashMap, losing that order, which forced a
    // pure-Python reverse-BFS wrapper (~4-5x slower than nx).
    let gr = extract_graph(g)?;
    let t = node_key_to_string(py, target)?;
    validate_node_str(&gr, &t, "Target")?;
    let (nodes, result) = if let Some(dg) = gr.digraph() {
        let nodes = dg.nodes_ordered();
        let adjacency = digraph_predecessor_adjacency_indices(dg, &nodes);
        let target_idx = nodes
            .iter()
            .position(|&n| n == t)
            .expect("target validated above");
        let result = py.allow_threads(|| {
            single_target_shortest_path_from_adjacency(&adjacency, target_idx, cutoff)
        });
        (nodes, result)
    } else {
        let inner = gr.undirected();
        let nodes = inner.nodes_ordered();
        let adjacency = graph_shortest_path_adjacency_indices(inner, &nodes);
        let target_idx = nodes
            .iter()
            .position(|&n| n == t)
            .expect("target validated above");
        let result = py.allow_threads(|| {
            single_target_shortest_path_from_adjacency(&adjacency, target_idx, cutoff)
        });
        (nodes, result)
    };
    let dict = PyDict::new(py);
    for (node, path) in &result {
        let py_path: Vec<PyObject> = path.iter().map(|&i| gr.py_node_key(py, nodes[i])).collect();
        dict.set_item(gr.py_node_key(py, nodes[*node]), py_path)?;
    }
    Ok(dict.into_any().unbind())
}

/// Reverse adjacency (predecessor rows) for a directed graph in node-index
/// space, preserving each node's `predecessors_iter` order.
fn digraph_predecessor_adjacency_indices(
    digraph: &fnx_classes::digraph::DiGraph,
    nodes: &[&str],
) -> Vec<Vec<usize>> {
    let node_indices: HashMap<&str, usize> = nodes
        .iter()
        .copied()
        .enumerate()
        .map(|(index, node)| (node, index))
        .collect();
    nodes
        .iter()
        .map(|&node| {
            digraph
                .predecessors_iter(node)
                .map_or_else(Vec::new, |preds| {
                    preds
                        .filter_map(|pred| node_indices.get(pred).copied())
                        .collect()
                })
        })
        .collect()
}

/// Reverse BFS from `target` over `adjacency`, returning `(node, path)` pairs in
/// BFS-discovery order. Each path runs node -> ... -> target (matching nx's
/// `paths[w] = [w] + paths[v]`), reconstructed via a successor-toward-target
/// array recorded when each node is first reached.
fn single_target_shortest_path_from_adjacency(
    adjacency: &[Vec<usize>],
    target: usize,
    cutoff: Option<usize>,
) -> Vec<(usize, Vec<usize>)> {
    let node_count = adjacency.len();
    let mut seen = vec![false; node_count];
    let mut succ = vec![0usize; node_count];
    let mut order: Vec<usize> = Vec::with_capacity(node_count);
    let mut frontier = vec![target];
    let mut next_frontier = Vec::new();
    seen[target] = true;
    succ[target] = target;
    order.push(target);

    let cutoff = cutoff.unwrap_or(usize::MAX);
    let mut level = 0usize;
    while !frontier.is_empty() && level < cutoff {
        next_frontier.clear();
        for &node in &frontier {
            for &neighbor in &adjacency[node] {
                if !seen[neighbor] {
                    seen[neighbor] = true;
                    succ[neighbor] = node;
                    order.push(neighbor);
                    next_frontier.push(neighbor);
                }
            }
        }
        std::mem::swap(&mut frontier, &mut next_frontier);
        level += 1;
    }

    let mut result = Vec::with_capacity(order.len());
    for &node in &order {
        let mut path = Vec::new();
        let mut cur = node;
        loop {
            path.push(cur);
            if cur == target {
                break;
            }
            cur = succ[cur];
        }
        result.push((node, path));
    }
    result
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
    let t = node_key_to_string(py, target)?;
    validate_node_str(&gr, &t, "Target")?;
    let dict = PyDict::new(py);
    if let Some(dg) = gr.digraph() {
        let result = py.allow_threads(|| {
            fnx_algorithms::single_target_shortest_path_length_directed(dg, &t, cutoff)
        });
        for (node, length) in &result {
            dict.set_item(gr.py_node_key(py, node), *length)?;
        }
    } else {
        let __gr_undirected = gr.undirected();
        let result = py.allow_threads(|| {
            fnx_algorithms::single_target_shortest_path_length(__gr_undirected, &t, cutoff)
        });
        for (node, length) in &result {
            dict.set_item(gr.py_node_key(py, node), *length)?;
        }
    };
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
    sync_rust_attrs_if_available(g)?;
    let gr = extract_graph(g)?;
    let result = if gr.is_directed() {
        let dg = gr
            .weighted_digraph_projection(weight)
            .expect("is_directed checked above");
        py.allow_threads(|| {
            fnx_algorithms::all_pairs_dijkstra_path_length_with_pred_directed(dg.as_ref(), weight)
        })
    } else {
        let weighted_projection = gr.weighted_undirected_projection(weight);
        {
            let __wp = weighted_projection.as_ref();
            py.allow_threads(|| {
                fnx_algorithms::all_pairs_dijkstra_path_length_with_pred(__wp, weight)
            })
        }
    };
    let outer_dict = PyDict::new(py);
    for (source, dists) in &result {
        let mut disp: std::collections::HashMap<String, PyObject> =
            std::collections::HashMap::with_capacity(dists.len());
        for (node, _distance, _all_int, predecessor) in dists {
            if let Some(pred) = predecessor {
                disp.insert(node.clone(), gr.py_row_key(py, pred, node));
            }
        }
        let inner_dict = PyDict::new(py);
        for (target, d, _all_int, _predecessor) in dists {
            inner_dict.set_item(gr.disp_or_node_key(py, &disp, target), d)?;
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
    sync_rust_attrs_if_available(g)?;
    let gr = extract_graph(g)?;
    let result = if gr.is_directed() {
        let dg = gr
            .weighted_digraph_projection(weight)
            .expect("is_directed checked above");
        py.allow_threads(|| fnx_algorithms::all_pairs_dijkstra_directed(dg.as_ref(), weight))
            .into_iter()
            .map(|(source, (_dists, paths))| (source, paths))
            .collect::<Vec<_>>()
    } else {
        let weighted_projection = gr.weighted_undirected_projection(weight);
        {
            let __wp = weighted_projection.as_ref();
            py.allow_threads(|| fnx_algorithms::all_pairs_dijkstra_path(__wp, weight))
        }
    };
    let outer_dict = PyDict::new(py);
    for (source, targets) in &result {
        // weighted sp batch: discovery objects per source; sources keep
        // their node-map object (nx iterates G).
        let inner_dict =
            emit_paths_dict_discovery(py, &gr, targets, source, gr.py_node_key(py, source))?;
        outer_dict.set_item(gr.py_node_key(py, source), inner_dict)?;
    }
    Ok(outer_dict.into_any().unbind())
}

/// Return Johnson all-pairs shortest paths for exact directed graphs.
#[allow(dead_code)]
#[pyfunction]
#[pyo3(signature = (g, weight="weight"))]
fn johnson_path_directed(py: Python<'_>, g: &Bound<'_, PyAny>, weight: &str) -> PyResult<PyObject> {
    sync_rust_attrs_if_available(g)?;
    let gr = extract_graph(g)?;
    let Some(dg) = gr.digraph() else {
        return Err(crate::NetworkXNotImplemented::new_err(
            "not implemented for undirected type",
        ));
    };
    let Some(result) = py.allow_threads(|| fnx_algorithms::johnson_path_directed(dg, weight))
    else {
        return Err(crate::NetworkXUnbounded::new_err(
            "Negative cycle detected.",
        ));
    };
    let outer_dict = PyDict::new(py);
    for (source, targets) in &result {
        let inner_dict =
            emit_paths_dict_discovery(py, &gr, targets, source, gr.py_node_key(py, source))?;
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
    sync_rust_attrs_if_available(g)?;
    let gr = extract_graph(g)?;
    // br-r37-c1-7hsew: loop the PRED-carrying kernels so each source's
    // length dict gets discovery objects (the SPFA relaxation parent's
    // row object) without extra walks.
    let outer_dict = PyDict::new(py);
    if let Some(weighted_projection) = gr.weighted_digraph_projection(weight) {
        let __wp = weighted_projection.as_ref();
        for source in __wp.nodes_ordered() {
            let bf = py.allow_threads(|| {
                fnx_algorithms::bellman_ford_shortest_paths_directed(__wp, source, weight)
            });
            if bf.negative_cycle_detected {
                return Err(crate::NetworkXUnbounded::new_err(
                    "Negative cycle detected.",
                ));
            }
            let mut disp: std::collections::HashMap<String, PyObject> =
                std::collections::HashMap::with_capacity(bf.distances.len());
            for e in &bf.predecessors {
                if let Some(p) = &e.predecessor {
                    disp.insert(e.node.clone(), gr.py_row_key(py, p, &e.node));
                }
            }
            let inner_dict = PyDict::new(py);
            for e in &bf.distances {
                inner_dict.set_item(gr.disp_or_node_key(py, &disp, &e.node), e.distance)?;
            }
            outer_dict.set_item(gr.py_node_key(py, source), inner_dict)?;
        }
    } else {
        let weighted_projection = gr.weighted_undirected_projection(weight);
        let __wp = weighted_projection.as_ref();
        for source in __wp.nodes_ordered() {
            let bf = py.allow_threads(|| {
                fnx_algorithms::bellman_ford_shortest_paths(__wp, source, weight)
            });
            if bf.negative_cycle_detected {
                return Err(crate::NetworkXUnbounded::new_err(
                    "Negative cycle detected.",
                ));
            }
            let mut disp: std::collections::HashMap<String, PyObject> =
                std::collections::HashMap::with_capacity(bf.distances.len());
            for e in &bf.predecessors {
                if let Some(p) = &e.predecessor {
                    disp.insert(e.node.clone(), gr.py_row_key(py, p, &e.node));
                }
            }
            let inner_dict = PyDict::new(py);
            for e in &bf.distances {
                inner_dict.set_item(gr.disp_or_node_key(py, &disp, &e.node), e.distance)?;
            }
            outer_dict.set_item(gr.py_node_key(py, source), inner_dict)?;
        }
    }
    Ok(outer_dict.into_any().unbind())
}

/// Return all-pairs shortest paths using Bellman-Ford.
#[pyfunction]
#[pyo3(signature = (g, weight="weight"))]
fn all_pairs_bellman_ford_path(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    weight: &str,
) -> PyResult<PyObject> {
    sync_rust_attrs_if_available(g)?;
    let gr = extract_graph(g)?;
    let result = if let Some(weighted_projection) = gr.weighted_digraph_projection(weight) {
        let __wp = weighted_projection.as_ref();
        let mut all_paths = Vec::new();
        for source in __wp.nodes_ordered() {
            let Some(paths) = py.allow_threads(|| {
                fnx_algorithms::single_source_bellman_ford_path_directed(__wp, source, weight)
            }) else {
                return Err(crate::NetworkXUnbounded::new_err(
                    "Negative cycle detected.",
                ));
            };
            all_paths.push((source.to_owned(), paths));
        }
        Some(all_paths)
    } else {
        let weighted_projection = gr.weighted_undirected_projection(weight);
        let __wp = weighted_projection.as_ref();
        py.allow_threads(|| fnx_algorithms::all_pairs_bellman_ford_path(__wp, weight))
    };
    match result {
        Some(data) => {
            let outer_dict = PyDict::new(py);
            for (source, targets) in &data {
                // br-r37-c1-7hsew: discovery objects per source; sources
                // keep their node-map object (nx iterates G).
                let inner_dict = emit_paths_dict_discovery(
                    py,
                    &gr,
                    targets,
                    source,
                    gr.py_node_key(py, source),
                )?;
                outer_dict.set_item(gr.py_node_key(py, source), inner_dict)?;
            }
            Ok(outer_dict.into_any().unbind())
        }
        None => Err(crate::NetworkXUnbounded::new_err(
            "Negative cycle detected.",
        )),
    }
}

/// Return Floyd-Warshall all-pairs shortest path distances.
#[pyfunction]
#[pyo3(signature = (g, weight="weight"))]
fn floyd_warshall(py: Python<'_>, g: &Bound<'_, PyAny>, weight: &str) -> PyResult<PyObject> {
    sync_rust_attrs_if_available(g)?;
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
    sync_rust_attrs_if_available(g)?;
    let gr = extract_graph(g)?;
    require_undirected(&gr, "floyd_warshall_predecessor_and_distance")?;
    let weighted_projection = gr.weighted_undirected_projection(weight);
    let (dists, preds) = {
        let __wp = weighted_projection.as_ref();
        py.allow_threads(|| fnx_algorithms::floyd_warshall_predecessor_and_distance(__wp, weight))
    };
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

fn emit_bidirectional_index_path(
    py: Python<'_>,
    gr: &GraphRef<'_>,
    nodes: &[&str],
    path: &[(usize, Option<usize>, bool)],
    source: &Bound<'_, PyAny>,
    target: &Bound<'_, PyAny>,
) -> PyResult<Vec<PyObject>> {
    path.iter()
        .map(|(node_idx, parent_idx, from_reverse)| {
            let node = nodes.get(*node_idx).ok_or_else(|| {
                NetworkXError::new_err("internal bidirectional path index out of bounds")
            })?;
            match parent_idx {
                Some(parent_idx) => {
                    let parent = nodes.get(*parent_idx).ok_or_else(|| {
                        NetworkXError::new_err("internal bidirectional parent index out of bounds")
                    })?;
                    if *from_reverse {
                        Ok(gr.py_pred_row_key(py, parent, node))
                    } else {
                        Ok(gr.py_row_key(py, parent, node))
                    }
                }
                None => {
                    if *from_reverse {
                        Ok(target.clone().unbind())
                    } else {
                        Ok(source.clone().unbind())
                    }
                }
            }
        })
        .collect()
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
    let s = node_key_to_string(py, source)?;
    let t = node_key_to_string(py, target)?;
    validate_node(&gr, &s, source, "Source")?;
    validate_node(&gr, &t, target, "Target")?;
    // br-r37-c1-k4wsy: nx-faithful bidirectional meta kernel — exact
    // tie-break path VALUES (the old directed route delegated to nx over
    // a conversion whose succ-major walk REORDERS pred rows, poisoning
    // the tie-break: br-r37-c1-w7nn3) and exact DISCOVERY objects
    // (forward = succ-row, reverse = pred-row, endpoints as passed,
    // meet node from the returning frontier).
    let result = if gr.is_directed() {
        let inner = gr.digraph().expect("is_directed checked above");
        let indexed = py.allow_threads(|| {
            fnx_algorithms::bidirectional_shortest_path_directed_index_meta(inner, &s, &t)
        });
        indexed.map(|path| {
            let nodes = inner.nodes_ordered();
            emit_bidirectional_index_path(py, &gr, &nodes, &path, source, target)
        })
    } else {
        let inner = gr.undirected();
        let indexed = py.allow_threads(|| {
            fnx_algorithms::bidirectional_shortest_path_index_meta(inner, &s, &t)
        });
        indexed.map(|path| {
            let nodes = inner.nodes_ordered();
            emit_bidirectional_index_path(py, &gr, &nodes, &path, source, target)
        })
    };
    match result {
        Some(path) => path,
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
    sync_rust_attrs_if_available(g)?;
    let gr = extract_graph(g)?;
    require_undirected(&gr, "negative_edge_cycle")?;
    let weighted_projection = gr.weighted_undirected_projection(weight);
    Ok({
        let __wp = weighted_projection.as_ref();
        py.allow_threads(|| fnx_algorithms::negative_edge_cycle(__wp, weight))
    })
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
    validate_node_str(&gr, &s, "Source")?;
    let result = {
        let __gr_undirected = gr.undirected();
        py.allow_threads(|| fnx_algorithms::predecessor(__gr_undirected, &s, cutoff))
    };
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
    sync_rust_attrs_if_available(g)?;
    let gr = extract_graph(g)?;
    let path_strs: Vec<String> = path
        .iter()
        .map(|n| node_key_to_string(py, n))
        .collect::<PyResult<_>>()?;
    let path_refs: Vec<&str> = path_strs.iter().map(String::as_str).collect();
    let result = match &gr {
        GraphRef::Undirected(pg) => {
            let __pg_inner = &pg.inner;
            py.allow_threads(|| fnx_algorithms::path_weight(__pg_inner, &path_refs, weight))
        }
        GraphRef::Directed { dg, .. } => {
            let __dg_inner = &dg.inner;
            py.allow_threads(|| {
                fnx_algorithms::path_weight_directed(__dg_inner, &path_refs, weight)
            })
        }
        GraphRef::MultiUndirected { .. } => {
            let weighted_projection = gr.weighted_undirected_projection(weight);
            {
                let __wp = weighted_projection.as_ref();
                py.allow_threads(|| fnx_algorithms::path_weight(__wp, &path_refs, weight))
            }
        }
        GraphRef::MultiDirected { .. } => {
            let weighted_projection = gr
                .weighted_digraph_projection(weight)
                .expect("multidigraph");
            {
                let __wp = weighted_projection.as_ref();
                py.allow_threads(|| fnx_algorithms::path_weight_directed(__wp, &path_refs, weight))
            }
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
        let scores = py.allow_threads(|| fnx_algorithms::in_degree_centrality(dg_ref));
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
        let scores = py.allow_threads(|| fnx_algorithms::out_degree_centrality(dg_ref));
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
    validate_node(&gr, &node, v, "Node")?;
    match &gr {
        GraphRef::Undirected(pg) => Ok({
            let __pg_inner = &pg.inner;
            py.allow_threads(|| fnx_algorithms::local_reaching_centrality(__pg_inner, &node))
        }),
        GraphRef::Directed { dg, .. } => Ok({
            let __dg_inner = &dg.inner;
            py.allow_threads(|| {
                fnx_algorithms::local_reaching_centrality_directed(__dg_inner, &node)
            })
        }),
        _ => {
            if gr.is_directed() {
                Ok({
                    let __gr_digraph = gr.digraph().expect("is_directed checked above");
                    py.allow_threads(|| {
                        fnx_algorithms::local_reaching_centrality_directed(__gr_digraph, &node)
                    })
                })
            } else {
                Ok({
                    let __gr_undirected = gr.undirected();
                    py.allow_threads(|| {
                        fnx_algorithms::local_reaching_centrality(__gr_undirected, &node)
                    })
                })
            }
        }
    }
}

/// Return the global reaching centrality.
#[pyfunction]
pub fn global_reaching_centrality(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<f64> {
    let gr = extract_graph(g)?;
    match &gr {
        GraphRef::Undirected(pg) => Ok({
            let __pg_inner = &pg.inner;
            py.allow_threads(|| fnx_algorithms::global_reaching_centrality(__pg_inner))
        }),
        GraphRef::Directed { dg, .. } => Ok({
            let __dg_inner = &dg.inner;
            py.allow_threads(|| fnx_algorithms::global_reaching_centrality_directed(__dg_inner))
        }),
        _ => {
            if gr.is_directed() {
                Ok({
                    let __gr_digraph = gr.digraph().expect("is_directed checked above");
                    py.allow_threads(|| {
                        fnx_algorithms::global_reaching_centrality_directed(__gr_digraph)
                    })
                })
            } else {
                Ok({
                    let __gr_undirected = gr.undirected();
                    py.allow_threads(|| fnx_algorithms::global_reaching_centrality(__gr_undirected))
                })
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
    Ok(py.allow_threads(|| fnx_algorithms::group_degree_centrality(inner, &group_refs)))
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
        Ok(py.allow_threads(|| fnx_algorithms::group_in_degree_centrality(dg_ref, &group_refs)))
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
        Ok(py.allow_threads(|| fnx_algorithms::group_out_degree_centrality(dg_ref, &group_refs)))
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
    let node = node_key_to_string(py, n)?;
    validate_node(&gr, &node, n, "Node")?;
    // br-r37-c1-fyxma2: MultiGraph uses a direct single-source BFS over the
    // adjacency instead of the slow simple-Graph path (was 50x slower).
    if let GraphRef::MultiUndirected { mg, .. } = &gr {
        let inner = &mg.inner;
        let node_ref = node.as_str();
        let comp =
            py.allow_threads(|| multigraph_node_connected_component(inner, node_ref));
        return Ok(comp.iter().map(|&s| gr.py_node_key(py, s)).collect());
    }
    let inner = gr.undirected();
    let result = py.allow_threads(|| fnx_algorithms::node_connected_component(inner, &node));
    Ok(result.iter().map(|s| gr.py_node_key(py, s)).collect())
}

/// Return True if the graph is biconnected.
#[pyfunction]
pub fn is_biconnected(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<bool> {
    let gr = extract_graph(g)?;
    require_undirected(&gr, "is_biconnected")?;
    let inner = gr.undirected();
    Ok(py.allow_threads(|| fnx_algorithms::is_biconnected(inner)))
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
    // br-r37-c1-bcedfs: port nx's iterative DFS edge-stack algorithm
    // (`_biconnected_dfs`) so edges come out in DFS-traversal order WITH nx's
    // discovery direction (e.g. (4, 2) back edge, not canonical (2, 4)). The
    // previous kernel emitted sorted canonical edges, which forced the Python
    // wrapper to delegate to nx via a full fnx->nx conversion (~3x slower).
    let gr = extract_graph(g)?;
    require_undirected(&gr, "biconnected_component_edges")?;
    let inner = gr.undirected();
    let nodes = inner.nodes_ordered();
    let adjacency = graph_shortest_path_adjacency_indices(inner, &nodes);
    let result = py.allow_threads(|| biconnected_component_edges_dfs(&adjacency));
    Ok(result
        .iter()
        .map(|comp| {
            comp.iter()
                .map(|&(u, v)| (gr.py_node_key(py, nodes[u]), gr.py_node_key(py, nodes[v])))
                .collect()
        })
        .collect())
}

/// Iterative DFS that yields each biconnected component's edges in nx's
/// edge-stack order and discovery direction. Direct port of networkx's
/// `_biconnected_dfs(G, components=True)` over an integer adjacency list (each
/// row in `iter(G[node])` order), so results are byte-identical to nx including
/// edge tuple orientation and intra-component ordering.
fn biconnected_component_edges_dfs(adjacency: &[Vec<usize>]) -> Vec<Vec<(usize, usize)>> {
    let n = adjacency.len();
    let mut visited = vec![false; n];
    let mut discovery = vec![0usize; n];
    let mut low = vec![0usize; n];
    let mut out: Vec<Vec<(usize, usize)>> = Vec::new();

    for start in 0..n {
        if visited[start] {
            continue;
        }
        discovery[start] = 0;
        low[start] = 0;
        let mut disc_counter = 1usize; // == len(discovery) in nx
        visited[start] = true;
        let mut edge_stack: Vec<(usize, usize)> = Vec::new();
        let mut edge_index: HashMap<(usize, usize), usize> = HashMap::new();
        // (grandparent, parent, next-child-cursor into adjacency[parent])
        let mut stack: Vec<(usize, usize, usize)> = vec![(start, start, 0)];

        while let Some(&(grandparent, parent, pos)) = stack.last() {
            if pos < adjacency[parent].len() {
                stack.last_mut().expect("non-empty").2 = pos + 1;
                let child = adjacency[parent][pos];
                if grandparent == child {
                    continue;
                }
                if visited[child] {
                    if discovery[child] <= discovery[parent] {
                        // back edge
                        low[parent] = low[parent].min(discovery[child]);
                        edge_index.insert((parent, child), edge_stack.len());
                        edge_stack.push((parent, child));
                    }
                } else {
                    discovery[child] = disc_counter;
                    low[child] = disc_counter;
                    disc_counter += 1;
                    visited[child] = true;
                    stack.push((parent, child, 0));
                    edge_index.insert((parent, child), edge_stack.len());
                    edge_stack.push((parent, child));
                }
            } else {
                stack.pop();
                if stack.len() > 1 {
                    if low[parent] >= discovery[grandparent] {
                        let ind = edge_index[&(grandparent, parent)];
                        out.push(edge_stack[ind..].to_vec());
                        edge_stack.truncate(ind);
                    }
                    low[grandparent] = low[parent].min(low[grandparent]);
                } else if !stack.is_empty() {
                    // grandparent is the DFS root
                    let ind = edge_index[&(grandparent, parent)];
                    out.push(edge_stack[ind..].to_vec());
                    edge_stack.truncate(ind);
                }
            }
        }
    }
    out
}

/// Return True if the directed graph is semiconnected.
#[pyfunction]
pub fn is_semiconnected(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<bool> {
    let gr = extract_graph(g)?;
    if !gr.is_directed() {
        return Err(crate::NetworkXNotImplemented::new_err(
            "is_semiconnected is not defined for undirected graphs.",
        ));
    }
    {
        let dg_ref = gr.digraph().expect("is_directed checked above");
        Ok(py.allow_threads(|| fnx_algorithms::is_semiconnected(dg_ref)))
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
        let result =
            py.allow_threads(|| fnx_algorithms::kosaraju_strongly_connected_components(dg_ref));
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
        let result = py.allow_threads(|| fnx_algorithms::attracting_components(dg_ref));
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
pub fn number_attracting_components(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<usize> {
    let gr = extract_graph(g)?;
    if !gr.is_directed() {
        return Err(crate::NetworkXNotImplemented::new_err(
            "number_attracting_components is not defined for undirected graphs.",
        ));
    }
    {
        let dg_ref = gr.digraph().expect("is_directed checked above");
        Ok(py.allow_threads(|| fnx_algorithms::number_attracting_components(dg_ref)))
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
        Ok(py.allow_threads(|| fnx_algorithms::is_attracting_component(dg_ref, &comp_refs)))
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
    // br-r37-c1-djohp: nx rejects multigraph because parallel edges
    // create length-2 cycles that aren't meaningful in the simple-graph
    // sense; mirror that contract.
    require_not_multigraph(&gr)?;
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
    let result = {
        let __wp = weighted_projection.as_ref();
        py.allow_threads(|| fnx_algorithms::find_negative_cycle(__wp, &src, weight))
    };
    match result {
        Some(cycle) => Ok(cycle.iter().map(|n| gr.py_node_key(py, n)).collect()),
        None => Err(crate::NetworkXError::new_err("No negative cycle found.")),
    }
}

// ===========================================================================
// Graph predicates
// ===========================================================================

#[pyfunction]
#[pyo3(signature = (sequence,))]
pub fn is_graphical(py: Python<'_>, sequence: Vec<usize>) -> bool {
    py.allow_threads(|| fnx_algorithms::is_graphical(&sequence))
}

#[pyfunction]
#[pyo3(signature = (sequence,))]
pub fn is_digraphical(py: Python<'_>, sequence: Vec<(usize, usize)>) -> bool {
    py.allow_threads(|| fnx_algorithms::is_digraphical(&sequence))
}

#[pyfunction]
#[pyo3(signature = (sequence,))]
pub fn is_multigraphical(py: Python<'_>, sequence: Vec<usize>) -> bool {
    py.allow_threads(|| fnx_algorithms::is_multigraphical(&sequence))
}

#[pyfunction]
#[pyo3(signature = (sequence,))]
pub fn is_pseudographical(py: Python<'_>, sequence: Vec<usize>) -> bool {
    py.allow_threads(|| fnx_algorithms::is_pseudographical(&sequence))
}

#[pyfunction]
#[pyo3(signature = (g,))]
pub fn is_regular(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<bool> {
    // br-r37-c1-regidx: native O(|V|) integer degree-equality check with short-
    // circuit. Undirected: all nodes share one degree. Directed: all share one
    // in-degree AND one out-degree (nx's definition). Uses degree_by_index /
    // in/out_degree_by_index (O(1)/node, no String key resolution and no
    // DegreeView Python round-trip per node). Multigraphs (parallel-edge degree
    // multiplicity) stay on the Python degree-view path in the wrapper.
    let gr = extract_graph(g)?;
    if gr.node_count_original() == 0 {
        return Err(crate::NetworkXPointlessConcept::new_err(
            "Graph has no nodes.",
        ));
    }
    if let GraphRef::Directed { dg, .. } = &gr {
        let dg = &dg.inner;
        Ok(py.allow_threads(|| {
            let n = dg.node_count();
            let in0 = dg.in_degree_by_index(0);
            let out0 = dg.out_degree_by_index(0);
            (1..n).all(|i| dg.in_degree_by_index(i) == in0 && dg.out_degree_by_index(i) == out0)
        }))
    } else {
        let inner = gr.undirected();
        Ok(py.allow_threads(|| {
            let n = inner.node_count();
            let d0 = inner.degree_by_index(0);
            (1..n).all(|i| inner.degree_by_index(i) == d0)
        }))
    }
}

#[pyfunction]
#[pyo3(signature = (g, k))]
pub fn is_k_regular(py: Python<'_>, g: &Bound<'_, PyAny>, k: i64) -> PyResult<bool> {
    let gr = extract_graph(g)?;
    require_undirected(&gr, "is_k_regular")?;
    let inner = gr.undirected();
    if k < 0 {
        // NetworkX implements `is_k_regular` as ``all(d == k for n, d in
        // degrees())``. On an empty graph the iterator is empty, so
        // ``all()`` returns True regardless of ``k``. For graphs with
        // nodes, every degree is non-negative, so no degree can equal a
        // negative ``k`` and the answer is False. Mirror that exactly
        // — the previous `return Ok(false)` shortcut diverged on the
        // empty-graph case.
        return Ok(inner.node_count() == 0);
    }
    Ok(py.allow_threads(|| fnx_algorithms::is_k_regular(inner, k as usize)))
}

#[pyfunction]
#[pyo3(signature = (g,))]
pub fn is_tournament(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<bool> {
    let gr = extract_graph(g)?;
    require_directed(&gr, "is_tournament")?;
    if gr.is_multigraph() {
        return Err(crate::NetworkXNotImplemented::new_err(
            "is_tournament is not defined for multigraphs.",
        ));
    }
    {
        let dg_ref = gr.digraph().expect("is_directed checked above");
        Ok(py.allow_threads(|| fnx_algorithms::is_tournament(dg_ref)))
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
        GraphRef::Undirected(pg) => {
            let __pg_inner = &pg.inner;
            py.allow_threads(|| fnx_algorithms::edge_bfs(__pg_inner, &src))
        }
        GraphRef::Directed { dg, .. } => {
            let __dg_inner = &dg.inner;
            py.allow_threads(|| fnx_algorithms::edge_bfs_directed(__dg_inner, &src))
        }
        _ => {
            if gr.is_directed() {
                {
                    let __gr_digraph = gr.digraph().expect("is_directed checked above");
                    py.allow_threads(|| fnx_algorithms::edge_bfs_directed(__gr_digraph, &src))
                }
            } else {
                {
                    let __gr_undirected = gr.undirected();
                    py.allow_threads(|| fnx_algorithms::edge_bfs(__gr_undirected, &src))
                }
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
        GraphRef::Undirected(pg) => {
            let inner = &pg.inner;
            py.allow_threads(|| fnx_algorithms::edge_dfs(inner, &src))
        }
        GraphRef::Directed { dg, .. } => {
            let inner = &dg.inner;
            py.allow_threads(|| fnx_algorithms::edge_dfs_directed(inner, &src))
        }
        _ => {
            if gr.is_directed() {
                let inner = gr.digraph().expect("is_directed checked above");
                py.allow_threads(|| fnx_algorithms::edge_dfs_directed(inner, &src))
            } else {
                let inner = gr.undirected();
                py.allow_threads(|| fnx_algorithms::edge_dfs(inner, &src))
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
    Ok(py.allow_threads(|| fnx_algorithms::is_edge_cover(inner, &edge_refs)))
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
pub fn is_aperiodic(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<bool> {
    let gr = extract_graph(g)?;
    if !gr.is_directed() {
        return Err(crate::NetworkXNotImplemented::new_err(
            "is_aperiodic is not defined for undirected graphs.",
        ));
    }
    {
        let dg_ref = gr.digraph().expect("is_directed checked above");
        Ok(py.allow_threads(|| fnx_algorithms::is_aperiodic(dg_ref)))
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
        let result = py.allow_threads(|| fnx_algorithms::antichains(dg_ref));
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
        let result = py.allow_threads(|| fnx_algorithms::immediate_dominators(dg_ref, &src));
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
        let result = py.allow_threads(|| fnx_algorithms::dominance_frontiers(dg_ref, &src));
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
    Ok({
        let __gr_undirected = gr.undirected();
        py.allow_threads(|| fnx_algorithms::volume(__gr_undirected, &refs))
    })
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
    Ok({
        let __gr_undirected = gr.undirected();
        py.allow_threads(|| fnx_algorithms::boundary_expansion(__gr_undirected, &refs))
    })
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
    Ok({
        let __gr_undirected = gr.undirected();
        py.allow_threads(|| fnx_algorithms::conductance(__gr_undirected, &refs))
    })
}

/// Return the edge expansion of a set of nodes.
#[pyfunction]
#[pyo3(signature = (g, nodes))]
fn edge_expansion(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    nodes: Vec<Bound<'_, PyAny>>,
) -> PyResult<f64> {
    if nodes.is_empty() {
        return Err(PyZeroDivisionError::new_err("division by zero"));
    }
    let gr = extract_graph(g)?;
    let node_strs: Vec<String> = nodes
        .iter()
        .map(|n| node_key_to_string(py, n))
        .collect::<PyResult<_>>()?;
    let refs: Vec<&str> = node_strs.iter().map(|s| s.as_str()).collect();
    Ok({
        let __gr_undirected = gr.undirected();
        py.allow_threads(|| fnx_algorithms::edge_expansion(__gr_undirected, &refs))
    })
}

/// Return the node expansion of a set of nodes.
#[pyfunction]
#[pyo3(signature = (g, nodes))]
fn node_expansion(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    nodes: Vec<Bound<'_, PyAny>>,
) -> PyResult<f64> {
    if nodes.is_empty() {
        return Err(PyZeroDivisionError::new_err("division by zero"));
    }
    let gr = extract_graph(g)?;
    let node_strs: Vec<String> = nodes
        .iter()
        .map(|n| node_key_to_string(py, n))
        .collect::<PyResult<_>>()?;
    let refs: Vec<&str> = node_strs.iter().map(|s| s.as_str()).collect();
    Ok({
        let __gr_undirected = gr.undirected();
        py.allow_threads(|| fnx_algorithms::node_expansion(__gr_undirected, &refs))
    })
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
    Ok({
        let __gr_undirected = gr.undirected();
        py.allow_threads(|| fnx_algorithms::mixing_expansion(__gr_undirected, &refs))
    })
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
                {
                    let __gr_undirected = gr.undirected();
                    py.allow_threads(|| fnx_algorithms::non_edges(__gr_undirected))
                }
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

fn dijkstra_weight_from_attrs(attrs: Option<&AttrMap>, weight: &str) -> f64 {
    attrs
        .and_then(|attrs| attrs.get(weight))
        .and_then(|value| value.as_f64())
        .filter(|value| value.is_finite() && *value >= 0.0)
        .unwrap_or(1.0)
}

fn packed_graph_dijkstra_adjacency(
    graph: &fnx_classes::Graph,
    weight: &str,
) -> Vec<Vec<(usize, f64)>> {
    let nodes = graph.nodes_ordered();
    let mut adjacency = vec![Vec::new(); nodes.len()];
    for (source_idx, source) in nodes.iter().enumerate() {
        let Some(neighbors) = graph.neighbors_indices(source_idx) else {
            continue;
        };
        adjacency[source_idx].reserve(neighbors.len());
        for &target_idx in neighbors {
            let target = nodes[target_idx];
            let weight_value = dijkstra_weight_from_attrs(graph.edge_attrs(source, target), weight);
            adjacency[source_idx].push((target_idx, weight_value));
        }
    }
    adjacency
}

fn packed_digraph_dijkstra_adjacency(
    digraph: &fnx_classes::digraph::DiGraph,
    weight: &str,
) -> Vec<Vec<(usize, f64)>> {
    let nodes = digraph.nodes_ordered();
    let mut adjacency = vec![Vec::new(); nodes.len()];
    for (source_idx, source) in nodes.iter().enumerate() {
        let Some(successors) = digraph.successors_iter(source) else {
            continue;
        };
        for target in successors {
            let Some(target_idx) = digraph.get_node_index(target) else {
                continue;
            };
            let weight_value =
                dijkstra_weight_from_attrs(digraph.edge_attrs(source, target), weight);
            adjacency[source_idx].push((target_idx, weight_value));
        }
    }
    adjacency
}

fn set_dijkstra_distance_item(
    dict: &Bound<'_, PyDict>,
    key: PyObject,
    distance: f64,
    all_int_weights: bool,
) -> PyResult<()> {
    if distance == 0.0
        || (all_int_weights
            && distance.fract() == 0.0
            && distance >= i64::MIN as f64
            && distance <= i64::MAX as f64)
    {
        dict.set_item(key, distance as i64)
    } else {
        dict.set_item(key, distance)
    }
}

fn all_pairs_dijkstra_packed_py(
    py: Python<'_>,
    gr: &GraphRef<'_>,
    nodes: &[&str],
    adjacency: &[Vec<(usize, f64)>],
    all_int_weights: bool,
) -> PyResult<PyObject> {
    let py_keys: Vec<PyObject> = nodes.iter().map(|node| gr.py_node_key(py, node)).collect();
    let outer = PyDict::new(py);
    let mut seen = vec![f64::INFINITY; nodes.len()];
    let mut predecessors = vec![None::<usize>; nodes.len()];
    let mut finalized = vec![false; nodes.len()];
    let mut finalize_order = Vec::<usize>::with_capacity(nodes.len());
    let mut heap = BinaryHeap::<PyDijkstraState>::new();
    let mut path_indices = Vec::<usize>::with_capacity(nodes.len());

    for source_idx in 0..nodes.len() {
        seen.fill(f64::INFINITY);
        predecessors.fill(None);
        finalized.fill(false);
        finalize_order.clear();
        heap.clear();
        let mut seq = 0_u64;

        seen[source_idx] = 0.0;
        heap.push(PyDijkstraState {
            dist: 0.0,
            seq,
            node: source_idx,
        });
        seq += 1;

        while let Some(PyDijkstraState {
            dist,
            node: current,
            ..
        }) = heap.pop()
        {
            if finalized[current] {
                continue;
            }
            finalized[current] = true;
            finalize_order.push(current);

            for &(target, weight) in &adjacency[current] {
                let next_dist = dist + weight;
                if finalized[target] {
                    if next_dist < seen[target] {
                        return Err(PyValueError::new_err((
                            "Contradictory paths found:",
                            "negative weights?",
                        )));
                    }
                    continue;
                }
                if next_dist < seen[target] {
                    seen[target] = next_dist;
                    predecessors[target] = Some(current);
                    heap.push(PyDijkstraState {
                        dist: next_dist,
                        seq,
                        node: target,
                    });
                    seq += 1;
                }
            }
        }

        // br-r37-c1-7hsew: discovery objects — a node displays as its
        // finalizing predecessor's row object; sources keep their
        // node-map object (nx iterates G).
        let mut disp_keys: Vec<Option<PyObject>> = (0..nodes.len()).map(|_| None).collect();
        for &target_idx in &finalize_order {
            disp_keys[target_idx] = Some(match predecessors[target_idx] {
                Some(p) => gr.py_row_key(py, nodes[p], nodes[target_idx]),
                None => py_keys[target_idx].clone_ref(py),
            });
        }
        let disp = |idx: usize| -> PyObject {
            disp_keys[idx]
                .as_ref()
                .map_or_else(|| py_keys[idx].clone_ref(py), |o| o.clone_ref(py))
        };
        let dist_dict = PyDict::new(py);
        let path_dict = PyDict::new(py);
        for &target_idx in &finalize_order {
            set_dijkstra_distance_item(
                &dist_dict,
                disp(target_idx),
                seen[target_idx],
                all_int_weights,
            )?;

            path_indices.clear();
            let mut cursor = Some(target_idx);
            while let Some(idx) = cursor {
                path_indices.push(idx);
                cursor = predecessors[idx];
            }
            let py_path = PyList::empty(py);
            for &idx in path_indices.iter().rev() {
                py_path.append(disp(idx))?;
            }
            path_dict.set_item(disp(target_idx), py_path)?;
        }
        let pair = PyTuple::new(py, [dist_dict.as_any(), path_dict.as_any()])?;
        outer.set_item(py_keys[source_idx].clone_ref(py), pair)?;
    }

    Ok(outer.into_any().unbind())
}

/// Return all-pairs Dijkstra distances and paths.
#[pyfunction]
#[pyo3(signature = (g, weight="weight"))]
fn all_pairs_dijkstra(py: Python<'_>, g: &Bound<'_, PyAny>, weight: &str) -> PyResult<PyObject> {
    sync_rust_attrs_if_available(g)?;
    let gr = extract_graph(g)?;
    if !gr.is_multigraph() {
        if gr.is_directed() {
            let digraph = gr
                .weighted_digraph_projection(weight)
                .expect("is_directed checked above");
            let nodes = digraph.as_ref().nodes_ordered();
            let adjacency = packed_digraph_dijkstra_adjacency(digraph.as_ref(), weight);
            let all_int_weights =
                fnx_algorithms::digraph_edge_weights_all_int(digraph.as_ref(), weight);
            return all_pairs_dijkstra_packed_py(py, &gr, &nodes, &adjacency, all_int_weights);
        }

        let graph = gr.weighted_undirected_projection(weight);
        let nodes = graph.as_ref().nodes_ordered();
        let adjacency = packed_graph_dijkstra_adjacency(graph.as_ref(), weight);
        let all_int_weights = fnx_algorithms::graph_edge_weights_all_int(graph.as_ref(), weight);
        return all_pairs_dijkstra_packed_py(py, &gr, &nodes, &adjacency, all_int_weights);
    }

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
        // br-r37-c1-7hsew: per-source discovery objects via the paths.
        let mut disp: std::collections::HashMap<String, PyObject> =
            std::collections::HashMap::with_capacity(paths.len());
        for (node, p) in paths {
            if p.len() >= 2 {
                disp.insert(node.clone(), gr.py_row_key(py, &p[p.len() - 2], node));
            }
        }
        let dist_dict = PyDict::new(py);
        for (target, dist) in dists {
            dist_dict.set_item(gr.disp_or_node_key(py, &disp, target), *dist)?;
        }
        let path_dict = PyDict::new(py);
        for (target, path) in paths {
            let py_path: Vec<PyObject> = path
                .iter()
                .map(|n| gr.disp_or_node_key(py, &disp, n))
                .collect();
            path_dict.set_item(
                gr.disp_or_node_key(py, &disp, target),
                PyList::new(py, &py_path)?,
            )?;
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
        Ok(py.allow_threads(|| {
            fnx_algorithms::number_of_spanning_arborescences(dg_ref, &root_str, weight)
        }))
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

/// br-r37-c1-35oum: nx-exact Stoer-Wagner phases. Returns
/// (cut_value, contractions, best_phase, copy_nodes) — the Python
/// wrapper runs nx's set-order-dependent partition recovery tail with
/// real CPython sets. Display objects follow nx's working copy: a node
/// first touched in v-position carries the (u, v) row object.
#[pyfunction]
#[pyo3(signature = (g, weight="weight"))]
pub fn stoer_wagner_phases(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    weight: &str,
) -> PyResult<(f64, Vec<(PyObject, PyObject)>, usize, Vec<PyObject>)> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    let result = py.allow_threads(|| fnx_algorithms::stoer_wagner_nx(inner, weight));
    match result {
        Ok((cut_value, contractions, best_phase, copy_nodes)) => {
            let mut disp: std::collections::HashMap<String, PyObject> =
                std::collections::HashMap::with_capacity(copy_nodes.len());
            let mut nodes_py: Vec<PyObject> = Vec::with_capacity(copy_nodes.len());
            for (node, parent) in &copy_nodes {
                let obj = match parent {
                    Some(p) => gr.py_row_key(py, p, node),
                    None => gr.py_node_key(py, node),
                };
                disp.insert(node.clone(), obj.clone_ref(py));
                nodes_py.push(obj);
            }
            let pairs: Vec<(PyObject, PyObject)> = contractions
                .iter()
                .map(|(a, b)| {
                    (
                        gr.disp_or_node_key(py, &disp, a),
                        gr.disp_or_node_key(py, &disp, b),
                    )
                })
                .collect();
            Ok((cut_value, pairs, best_phase, nodes_py))
        }
        Err("negative") => Err(crate::NetworkXError::new_err(
            "graph has a negative-weighted edge.",
        )),
        Err(_) => Err(crate::NetworkXError::new_err(
            "graph has less than two nodes.",
        )),
    }
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
    let result =
        py.allow_threads(|| fnx_algorithms::chain_decomposition(inner, root_key.as_deref()));
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

/// Return Burt's effective size for unweighted simple directed graphs.
#[pyfunction]
pub fn effective_size_directed_rust(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
) -> PyResult<Py<PyDict>> {
    let gr = extract_graph(g)?;
    let inner = gr.digraph().expect("directed graph expected");
    let result = py.allow_threads(|| fnx_algorithms::effective_size_directed(inner));
    let dict = PyDict::new(py);
    for (node, val) in &result {
        dict.set_item(gr.py_node_key(py, node), val)?;
    }
    Ok(dict.unbind())
}

// ---------------------------------------------------------------------------
// Dispersion
// ---------------------------------------------------------------------------

/// Native bitset dispersion (full dict form). Returns {u: {v: value}} with the
/// normalized dispersion value for every neighbour pair.
#[pyfunction]
#[pyo3(signature = (g, alpha, b, c))]
pub fn dispersion_full_rust(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    alpha: f64,
    b: f64,
    c: f64,
) -> PyResult<Py<PyDict>> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    let result = py.allow_threads(|| fnx_algorithms::dispersion_full(inner, alpha, b, c));
    let dict = PyDict::new(py);
    for (node, row) in &result {
        let inner_dict = PyDict::new(py);
        for (nbr, val) in row {
            inner_dict.set_item(gr.py_node_key(py, nbr), val)?;
        }
        dict.set_item(gr.py_node_key(py, node), inner_dict)?;
    }
    Ok(dict.unbind())
}

/// br-r37-c1-dispego: single-node (ego) dispersion. Returns the inner dict
/// `{neighbour: value}` for `dispersion(G, u)` in `G.neighbors(u)` order,
/// computed in the local `N(u)` universe (no whole-graph allocation).
#[pyfunction]
pub fn dispersion_node_rust(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    u: &Bound<'_, PyAny>,
    alpha: f64,
    b: f64,
    c: f64,
) -> PyResult<Option<Py<PyDict>>> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    let key = node_key_to_string(py, u)?;
    let result = py.allow_threads(|| fnx_algorithms::dispersion_node(inner, &key, alpha, b, c));
    let Some(row) = result else {
        return Ok(None);
    };
    let dict = PyDict::new(py);
    for (nbr, val) in &row {
        dict.set_item(gr.py_node_key(py, nbr), val)?;
    }
    Ok(Some(dict.unbind()))
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
        let dg = gr
            .digraph()
            .ok_or_else(|| crate::NetworkXError::new_err("expected directed graph"))?;
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
    let result = if gr.is_directed() {
        let inner = gr.digraph().expect("is_directed checked above");
        py.allow_threads(|| fnx_algorithms::node_disjoint_paths_directed(inner, &s, &t))
    } else {
        let inner = gr.undirected();
        py.allow_threads(|| fnx_algorithms::node_disjoint_paths(inner, &s, &t))
    };
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
pub fn power_rust(py: Python<'_>, g: &Bound<'_, PyAny>, k: usize) -> PyResult<PyObject> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    let result = py.allow_threads(|| fnx_algorithms::power(inner, k));
    // Convert Rust Graph to PyGraph
    let pg = crate::PyGraph {
        inner: result,
        node_key_map: std::collections::HashMap::new(),
        lazy_int_node_stop: 0,
        node_py_attrs: std::collections::HashMap::new(),
        edge_py_attrs: std::collections::HashMap::new(),
        adj_py_keys: HashMap::new(), // br-r37-c1-z6uka
        dict_of_dicts_cache: None,
        adj_row_py: HashMap::new(),
        graph_attrs: PyDict::new(py).unbind(),
        nodes_seq: 0,
        edges_seq: 0,
        edges_dirty: AtomicBool::new(false),
        node_keys_cache: std::sync::Mutex::new(None),
        node_iter_mirror: std::sync::Mutex::new(None),
        node_data_mirror: std::sync::Mutex::new(None),
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

/// br-r37-c1-sqclfast: fast whole-graph square clustering for simple
/// undirected graphs. Runs the integer-CSR two-hop kernel and builds the
/// node-keyed result in insertion order, reproducing nx's
/// `squares / potential if potential > 0 else 0` exactly (int-`0` vs float).
#[pyfunction]
pub fn square_clustering_fast(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<Py<PyDict>> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    let pairs = py.allow_threads(|| fnx_algorithms::square_clustering_pairs(inner));
    let nodes = inner.nodes_ordered();
    let dict = PyDict::new(py);
    for (i, &node) in nodes.iter().enumerate() {
        let (squares, potential) = pairs[i];
        if potential > 0 {
            dict.set_item(gr.py_node_key(py, node), squares as f64 / potential as f64)?;
        } else {
            dict.set_item(gr.py_node_key(py, node), 0i64)?;
        }
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
        lazy_int_node_stop: 0,
        node_py_attrs: std::collections::HashMap::new(),
        edge_py_attrs: std::collections::HashMap::new(),
        adj_py_keys: HashMap::new(), // br-r37-c1-z6uka
        dict_of_dicts_cache: None,
        adj_row_py: HashMap::new(),
        graph_attrs: PyDict::new(py).unbind(),
        nodes_seq: 0,
        edges_seq: 0,
        edges_dirty: AtomicBool::new(false),
        node_keys_cache: std::sync::Mutex::new(None),
        node_iter_mirror: std::sync::Mutex::new(None),
        node_data_mirror: std::sync::Mutex::new(None),
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
        let dg = gr.digraph().expect("is_directed checked above");
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
pub fn full_join_rust(
    py: Python<'_>,
    g1: &Bound<'_, PyAny>,
    g2: &Bound<'_, PyAny>,
) -> PyResult<PyObject> {
    let gr1 = extract_graph(g1)?;
    let gr2 = extract_graph(g2)?;
    let inner1 = gr1.undirected();
    let inner2 = gr2.undirected();
    let result = py.allow_threads(|| fnx_algorithms::full_join(inner1, inner2));
    let pg = crate::PyGraph {
        inner: result,
        node_key_map: std::collections::HashMap::new(),
        lazy_int_node_stop: 0,
        node_py_attrs: std::collections::HashMap::new(),
        edge_py_attrs: std::collections::HashMap::new(),
        adj_py_keys: HashMap::new(), // br-r37-c1-z6uka
        dict_of_dicts_cache: None,
        adj_row_py: HashMap::new(),
        graph_attrs: PyDict::new(py).unbind(),
        nodes_seq: 0,
        edges_seq: 0,
        edges_dirty: AtomicBool::new(false),
        node_keys_cache: std::sync::Mutex::new(None),
        node_iter_mirror: std::sync::Mutex::new(None),
        node_data_mirror: std::sync::Mutex::new(None),
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
        lazy_int_node_stop: 0,
        node_py_attrs: std::collections::HashMap::new(),
        edge_py_attrs: std::collections::HashMap::new(),
        adj_py_keys: HashMap::new(), // br-r37-c1-z6uka
        dict_of_dicts_cache: None,
        adj_row_py: HashMap::new(),
        graph_attrs: PyDict::new(py).unbind(),
        nodes_seq: 0,
        edges_seq: 0,
        edges_dirty: AtomicBool::new(false),
        node_keys_cache: std::sync::Mutex::new(None),
        node_iter_mirror: std::sync::Mutex::new(None),
        node_data_mirror: std::sync::Mutex::new(None),
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
        .map(|(a, b, c, t)| {
            (
                gr.py_node_key(py, &a),
                gr.py_node_key(py, &b),
                gr.py_node_key(py, &c),
                t,
            )
        })
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
        let dg = gr.digraph().expect("is_directed checked above");
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
    let (result_graph, compressors) =
        py.allow_threads(|| fnx_algorithms::dedensify(inner, threshold));
    let pg = crate::PyGraph {
        inner: result_graph,
        node_key_map: std::collections::HashMap::new(),
        lazy_int_node_stop: 0,
        node_py_attrs: std::collections::HashMap::new(),
        edge_py_attrs: std::collections::HashMap::new(),
        adj_py_keys: HashMap::new(), // br-r37-c1-z6uka
        dict_of_dicts_cache: None,
        adj_row_py: HashMap::new(),
        graph_attrs: PyDict::new(py).unbind(),
        nodes_seq: 0,
        edges_seq: 0,
        edges_dirty: AtomicBool::new(false),
        node_keys_cache: std::sync::Mutex::new(None),
        node_iter_mirror: std::sync::Mutex::new(None),
        node_data_mirror: std::sync::Mutex::new(None),
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
        dict.set_item((gr.py_node_key(py, u), gr.py_node_key(py, v)), val.as_str())?;
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
        lazy_int_node_stop: 0,
        node_py_attrs: std::collections::HashMap::new(),
        edge_py_attrs: std::collections::HashMap::new(),
        adj_py_keys: HashMap::new(), // br-r37-c1-z6uka
        dict_of_dicts_cache: None,
        adj_row_py: HashMap::new(),
        graph_attrs: PyDict::new(py).unbind(),
        nodes_seq: 0,
        edges_seq: 0,
        edges_dirty: AtomicBool::new(false),
        node_keys_cache: std::sync::Mutex::new(None),
        node_iter_mirror: std::sync::Mutex::new(None),
        node_data_mirror: std::sync::Mutex::new(None),
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
    let dg = gr
        .digraph()
        .ok_or_else(|| crate::NetworkXError::new_err("moral_graph requires DiGraph"))?;
    // br-r37-c1-umz6c: the kernel result Graph carries canonical node
    // identities (e.g. "0", "1") that match the source's inner DiGraph,
    // but wrapping it directly with empty maps dropped the Python display
    // keys (int 0, not str "0") AND all node/edge attributes (the lazy-key
    // canonical divergence bug). Rebuild the result PyGraph in the kernel's
    // node/edge iteration order — which already mirrors nx's order
    // (digraph.nodes_ordered() then existing edges then co-parent edges) —
    // while re-keying through the source's display keys and copying node/
    // edge/graph attrs.
    //
    // nx's moral_graph is `H = G.to_undirected(); H.add_edges_from(co_parents)`.
    // `DiGraph.to_undirected()` walks directed edges in node-major order and is
    // LAST-WRITER-WINS on the undirected edge data: for a reciprocal pair the
    // edge processed later (the larger-source-index direction) overwrites the
    // earlier one. The generic `rust_graph_to_py_subgraph` helper instead keeps
    // the FIRST orientation's attrs, which diverges from nx whenever reciprocal
    // edges carry distinct data (e.g. the nx docstring's (3,4)/(4,3)). So build
    // the undirected edge-attr map here by replaying the source's directed edge
    // order with overwrite semantics; co-parent edges (in the result but not in
    // the source) get an empty dict, matching the Python batch path exactly.
    let result = py.allow_threads(|| fnx_algorithms::moral_graph(dg));

    let mut edge_attr_map: HashMap<(String, String), Py<PyDict>> = HashMap::new();
    for e in dg.edges_ordered() {
        let attrs = match gr.edge_attrs_for_directed(&e.left, &e.right) {
            Some(d) => d.bind(py).copy()?.unbind(),
            None => PyDict::new(py).unbind(),
        };
        edge_attr_map.insert(PyGraph::edge_key(&e.left, &e.right), attrs);
    }

    let mut py_graph =
        PyGraph::new_empty_with_policy(py, gr.undirected().runtime_policy().clone())?;
    py_graph.graph_attrs = gr.graph_attrs().bind(py).copy()?.unbind();
    for node in result.nodes_ordered() {
        py_graph
            .node_key_map
            .insert(node.to_owned(), gr.py_node_key(py, node));
        let attrs = match gr.node_attrs_for(node) {
            Some(d) => d.bind(py).copy()?.unbind(),
            None => PyDict::new(py).unbind(),
        };
        py_graph.node_py_attrs.insert(node.to_owned(), attrs);
        py_graph.inner.add_node(node);
    }
    for edge in result.edges_ordered() {
        let _ = py_graph.inner.add_edge(&edge.left, &edge.right);
        let ek = PyGraph::edge_key(&edge.left, &edge.right);
        let attrs = match edge_attr_map.remove(&ek) {
            Some(d) => d,
            None => PyDict::new(py).unbind(),
        };
        py_graph.edge_py_attrs.insert(ek, attrs);
    }
    Ok(py_graph.into_pyobject(py)?.into_any().unbind())
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

/// Weighted Hyper-Wiener index for simple undirected graphs.
#[pyfunction]
#[pyo3(signature = (g, weight_attr))]
pub fn hyper_wiener_index_weighted_rust(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    weight_attr: &str,
) -> PyResult<f64> {
    sync_rust_attrs_if_available(g)?;
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    py.allow_threads(|| fnx_algorithms::hyper_wiener_index_weighted(inner, weight_attr))
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
pub fn selfloop_edges_rust(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
) -> PyResult<Vec<(PyObject, PyObject)>> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    let result = py.allow_threads(|| fnx_algorithms::selfloop_edges(inner));
    Ok(result
        .iter()
        .map(|(u, v)| (gr.py_node_key(py, u), gr.py_node_key(py, v)))
        .collect())
}

/// Count self-loops.
#[pyfunction]
pub fn number_of_selfloops_rust(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<usize> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    Ok(py.allow_threads(|| fnx_algorithms::number_of_selfloops(inner)))
}

/// Count self-loops in a MultiGraph or MultiDiGraph without materializing edges.
#[pyfunction]
pub fn multigraph_number_of_selfloops_rust(g: &Bound<'_, PyAny>) -> PyResult<usize> {
    let gr = extract_graph(g)?;
    match &gr {
        GraphRef::MultiUndirected { mg, .. } => Ok(mg.inner.number_of_selfloops()),
        GraphRef::MultiDirected { mdg, .. } => Ok(mdg.inner.number_of_selfloops()),
        _ => Err(NetworkXNotImplemented::new_err(
            "not implemented for non-multigraph type",
        )),
    }
}

/// Nodes with self-loops.
#[pyfunction]
pub fn nodes_with_selfloops_rust(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<Vec<PyObject>> {
    let gr = extract_graph(g)?;
    // br-r37-c1-selfloopdir: a DiGraph must NOT be projected to its undirected
    // form just to find self-loops — `gr.undirected()` builds the whole O(|V|+|E|)
    // undirected copy, which was the ENTIRE cost of number_of_selfloops on a
    // DiGraph (~24ms at 3600 edges, and number_of_selfloops has many internal
    // callers, e.g. the is_eulerian self-loop guard). Scan the digraph's own
    // (i, i) edges in O(|V|) with O(1) index-pair lookups, in node-insertion
    // order (== networkx node order).
    if let GraphRef::Directed { dg, .. } = &gr {
        let inner = &dg.inner;
        let names: Vec<String> = (0..inner.node_count())
            .filter(|&i| inner.edge_attrs_by_indices(i, i).is_some())
            .filter_map(|i| inner.get_node_name(i).map(str::to_owned))
            .collect();
        return Ok(names.iter().map(|n| gr.py_node_key(py, n)).collect());
    }
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
#[pyo3(signature = (g, ebunch=None, community="community"))]
pub fn cn_soundarajan_hopcroft_rust(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    ebunch: Option<&Bound<'_, PyAny>>,
    community: &str,
) -> PyResult<Vec<(PyObject, PyObject, f64)>> {
    let gr = extract_graph(g)?;
    require_not_multigraph(&gr)?;
    require_undirected(&gr, "cn_soundarajan_hopcroft")?;
    let pairs = extract_ebunch(py, &gr, ebunch)?;
    validate_link_prediction_pairs(&gr, &pairs)?;
    let inner = gr.undirected();
    let result =
        py.allow_threads(|| fnx_algorithms::cn_soundarajan_hopcroft(inner, &pairs, community));
    Ok(result
        .into_iter()
        .map(|(u, v, s)| (gr.py_node_key(py, &u), gr.py_node_key(py, &v), s))
        .collect())
}

/// RA-index Soundarajan-Hopcroft link prediction.
#[pyfunction]
#[pyo3(signature = (g, ebunch=None, community="community"))]
pub fn ra_index_soundarajan_hopcroft_rust(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    ebunch: Option<&Bound<'_, PyAny>>,
    community: &str,
) -> PyResult<Vec<(PyObject, PyObject, f64)>> {
    let gr = extract_graph(g)?;
    require_not_multigraph(&gr)?;
    require_undirected(&gr, "ra_index_soundarajan_hopcroft")?;
    let pairs = extract_ebunch(py, &gr, ebunch)?;
    validate_link_prediction_pairs(&gr, &pairs)?;
    let inner = gr.undirected();
    let result = py
        .allow_threads(|| fnx_algorithms::ra_index_soundarajan_hopcroft(inner, &pairs, community));
    Ok(result
        .into_iter()
        .map(|(u, v, s)| (gr.py_node_key(py, &u), gr.py_node_key(py, &v), s))
        .collect())
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
    let dg = gr
        .digraph()
        .ok_or_else(|| crate::NetworkXError::new_err("triad_type requires DiGraph"))?;
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
    Ok(result
        .iter()
        .map(|(u, v)| (gr.py_node_key(py, u), gr.py_node_key(py, v)))
        .collect())
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
    let dg = gr
        .digraph()
        .ok_or_else(|| crate::NetworkXError::new_err("requires DiGraph"))?;
    let n = node_key_to_string(py, node)?;
    let result = py.allow_threads(|| fnx_algorithms::all_neighbors_directed(dg, &n));
    Ok(result.iter().map(|n| gr.py_node_key(py, n)).collect())
}

// ---------------------------------------------------------------------------
// Local bridges (Rust)
// ---------------------------------------------------------------------------

/// Return local bridges.
#[pyfunction]
pub fn local_bridges_rust(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
) -> PyResult<Vec<(PyObject, PyObject)>> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    let result = py.allow_threads(|| fnx_algorithms::local_bridges_list(inner));
    Ok(result
        .iter()
        .map(|(u, v)| (gr.py_node_key(py, u), gr.py_node_key(py, v)))
        .collect())
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
    Ok(result
        .iter()
        .map(|(u, v)| (gr.py_node_key(py, u), gr.py_node_key(py, v)))
        .collect())
}

// ---------------------------------------------------------------------------
// Graph info
// ---------------------------------------------------------------------------

/// Return text description of graph.
#[pyfunction]
pub fn graph_info_rust(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<String> {
    let gr = extract_graph(g)?;
    Ok(if gr.is_directed() {
        let dg = gr.digraph().expect("is_directed checked above");
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
    let dg = gr
        .digraph()
        .ok_or_else(|| crate::NetworkXError::new_err("LCA requires DiGraph"))?;
    let pair_keys: Vec<(String, String)> = pairs
        .iter()
        .map(|(u, v)| Ok((node_key_to_string(py, u)?, node_key_to_string(py, v)?)))
        .collect::<PyResult<_>>()?;
    let result =
        py.allow_threads(|| fnx_algorithms::all_pairs_lowest_common_ancestor(dg, &pair_keys));
    Ok(result
        .into_iter()
        .map(|((u, v), lca)| {
            (
                (gr.py_node_key(py, &u), gr.py_node_key(py, &v)),
                gr.py_node_key(py, &lca),
            )
        })
        .collect())
}

/// Find tree LCA results for all pairs or a requested pair set.
#[pyfunction]
#[pyo3(signature = (g, root, pairs=None))]
pub fn tree_all_pairs_lca_rust(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    root: &Bound<'_, PyAny>,
    pairs: Option<Vec<(Bound<'_, PyAny>, Bound<'_, PyAny>)>>,
) -> PyResult<Vec<((PyObject, PyObject), PyObject)>> {
    let gr = extract_graph(g)?;
    let dg = gr
        .digraph()
        .ok_or_else(|| crate::NetworkXError::new_err("Tree LCA requires DiGraph"))?;
    let root_key = node_key_to_string(py, root)?;
    let pair_keys = pairs
        .as_ref()
        .map(|pairs| {
            pairs
                .iter()
                .map(|(u, v)| Ok((node_key_to_string(py, u)?, node_key_to_string(py, v)?)))
                .collect::<PyResult<Vec<_>>>()
        })
        .transpose()?;
    let result = py.allow_threads(|| {
        fnx_algorithms::tree_all_pairs_lowest_common_ancestor(dg, &root_key, pair_keys.as_deref())
    });
    Ok(result
        .into_iter()
        .map(|((u, v), lca)| {
            (
                (gr.py_node_key(py, &u), gr.py_node_key(py, &v)),
                gr.py_node_key(py, &lca),
            )
        })
        .collect())
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
    let keys: Vec<String> = group
        .iter()
        .map(|n| node_key_to_string(py, n))
        .collect::<PyResult<_>>()?;
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

// ---------------------------------------------------------------------------
// Gomory-Hu tree
// ---------------------------------------------------------------------------

/// Build Gomory-Hu tree.
#[pyfunction]
#[pyo3(signature = (g, weight="weight"))]
pub fn gomory_hu_tree_rust(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    weight: &str,
) -> PyResult<PyObject> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    let result = py.allow_threads(|| fnx_algorithms::gomory_hu_tree(inner, weight));
    let pg = crate::PyGraph {
        inner: result,
        node_key_map: std::collections::HashMap::new(),
        lazy_int_node_stop: 0,
        node_py_attrs: std::collections::HashMap::new(),
        edge_py_attrs: std::collections::HashMap::new(),
        adj_py_keys: HashMap::new(), // br-r37-c1-z6uka
        dict_of_dicts_cache: None,
        adj_row_py: HashMap::new(),
        graph_attrs: PyDict::new(py).unbind(),
        nodes_seq: 0,
        edges_seq: 0,
        edges_dirty: AtomicBool::new(false),
        node_keys_cache: std::sync::Mutex::new(None),
        node_iter_mirror: std::sync::Mutex::new(None),
        node_data_mirror: std::sync::Mutex::new(None),
    };
    Ok(pg.into_pyobject(py)?.into_any().unbind())
}

// ---------------------------------------------------------------------------
// Find asteroidal triple
// ---------------------------------------------------------------------------

/// Find an asteroidal triple (or None if AT-free).
#[pyfunction]
pub fn find_asteroidal_triple_rust(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
) -> PyResult<Option<(PyObject, PyObject, PyObject)>> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    let result = py.allow_threads(|| fnx_algorithms::find_asteroidal_triple(inner));
    Ok(result.map(|(u, v, w)| {
        (
            gr.py_node_key(py, &u),
            gr.py_node_key(py, &v),
            gr.py_node_key(py, &w),
        )
    }))
}

// ---------------------------------------------------------------------------
// SNAP aggregation
// ---------------------------------------------------------------------------

/// SNAP aggregation: group nodes by attributes and neighbor signatures.
#[pyfunction]
pub fn snap_aggregation_rust(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    node_attributes: Vec<String>,
) -> PyResult<PyObject> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    let result = py.allow_threads(|| fnx_algorithms::snap_aggregation(inner, &node_attributes));
    let pg = crate::PyGraph {
        inner: result,
        node_key_map: std::collections::HashMap::new(),
        lazy_int_node_stop: 0,
        node_py_attrs: std::collections::HashMap::new(),
        edge_py_attrs: std::collections::HashMap::new(),
        adj_py_keys: HashMap::new(), // br-r37-c1-z6uka
        dict_of_dicts_cache: None,
        adj_row_py: HashMap::new(),
        graph_attrs: PyDict::new(py).unbind(),
        nodes_seq: 0,
        edges_seq: 0,
        edges_dirty: AtomicBool::new(false),
        node_keys_cache: std::sync::Mutex::new(None),
        node_iter_mirror: std::sync::Mutex::new(None),
        node_data_mirror: std::sync::Mutex::new(None),
    };
    Ok(pg.into_pyobject(py)?.into_any().unbind())
}

// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// Spanning tree / arborescence iterators
// ---------------------------------------------------------------------------

#[pyclass(unsendable, name = "spanning_tree_iterator_rust")]
pub struct SpanningTreeIteratorRust {
    items: Vec<fnx_classes::Graph>,
    index: usize,
    original_graph: PyObject,
}

#[pymethods]
impl SpanningTreeIteratorRust {
    #[new]
    #[pyo3(signature = (g, weight="weight", minimum=true, max_count=100))]
    fn new(
        py: Python<'_>,
        g: &Bound<'_, PyAny>,
        weight: &str,
        minimum: bool,
        max_count: usize,
    ) -> PyResult<Self> {
        let gr = extract_graph(g)?;
        if gr.is_directed() {
            return Err(crate::NetworkXNotImplemented::new_err(
                "not implemented for directed type",
            ));
        }
        if matches!(
            gr,
            GraphRef::MultiUndirected { .. } | GraphRef::MultiDirected { .. }
        ) {
            return Err(crate::NetworkXNotImplemented::new_err(
                "not implemented for multigraph type",
            ));
        }
        let items = {
            let __gr_undirected = gr.undirected();
            py.allow_threads(|| {
                fnx_algorithms::spanning_tree_iterator_ordered(
                    __gr_undirected,
                    weight,
                    minimum,
                    max_count,
                )
            })
        };
        Ok(Self {
            items,
            index: 0,
            original_graph: g.clone().unbind(),
        })
    }

    fn __iter__(slf: PyRef<'_, Self>) -> PyRef<'_, Self> {
        slf
    }

    fn __next__(mut slf: PyRefMut<'_, Self>, py: Python<'_>) -> PyResult<Option<PyObject>> {
        if slf.index >= slf.items.len() {
            return Ok(None);
        }
        let tree = slf.items[slf.index].clone();
        slf.index += 1;
        let g_bound = slf.original_graph.bind(py);
        let gr = extract_graph(g_bound)?;
        Ok(Some(rust_graph_to_py_subgraph(py, &tree, &gr)?))
    }
}

#[pyclass(unsendable, name = "arborescence_iterator_rust")]
pub struct ArborescenceIteratorRust {
    items: Vec<fnx_classes::digraph::DiGraph>,
    index: usize,
    original_graph: PyObject,
}

#[pymethods]
impl ArborescenceIteratorRust {
    #[new]
    #[pyo3(signature = (g, weight="weight", minimum=true, max_count=100, init_partition=None))]
    fn new(
        py: Python<'_>,
        g: &Bound<'_, PyAny>,
        weight: &str,
        minimum: bool,
        max_count: usize,
        init_partition: Option<&Bound<'_, PyAny>>,
    ) -> PyResult<Self> {
        let gr = extract_graph(g)?;
        if !gr.is_directed() {
            return Err(crate::NetworkXNotImplemented::new_err(
                "not implemented for undirected type",
            ));
        }
        if matches!(
            gr,
            GraphRef::MultiUndirected { .. } | GraphRef::MultiDirected { .. }
        ) {
            return Err(crate::NetworkXNotImplemented::new_err(
                "not implemented for multigraph type",
            ));
        }
        let (included_edges, excluded_edges) = extract_init_partition(py, init_partition)?;
        let items = {
            let __gr_digraph = gr.digraph().expect("is_directed checked above");
            py.allow_threads(|| {
                fnx_algorithms::arborescence_iterator_ordered_with_partition(
                    __gr_digraph,
                    weight,
                    minimum,
                    max_count,
                    &included_edges,
                    &excluded_edges,
                )
            })
        };
        if items.is_empty()
            && gr
                .digraph()
                .expect("is_directed checked above")
                .node_count()
                > 1
        {
            let message = if minimum {
                "No minimum spanning arborescence in G."
            } else {
                "No maximum spanning arborescence in G."
            };
            return Err(crate::NetworkXError::new_err(message));
        }
        Ok(Self {
            items,
            index: 0,
            original_graph: g.clone().unbind(),
        })
    }

    fn __iter__(slf: PyRef<'_, Self>) -> PyRef<'_, Self> {
        slf
    }

    fn __next__(mut slf: PyRefMut<'_, Self>, py: Python<'_>) -> PyResult<Option<PyObject>> {
        if slf.index >= slf.items.len() {
            return Ok(None);
        }
        let tree = slf.items[slf.index].clone();
        slf.index += 1;
        let g_bound = slf.original_graph.bind(py);
        let gr = extract_graph(g_bound)?;
        Ok(Some(rust_digraph_to_py_subgraph(py, &tree, &gr)?))
    }
}

// ---------------------------------------------------------------------------
// GraphML writer (Rust) — full NX-compatible with type inference
// ---------------------------------------------------------------------------

/// Generate GraphML XML string with full NX-compatible options.
#[pyfunction]
#[pyo3(signature = (g, prettyprint=true, infer_numeric_types=false, named_key_ids=false, edge_id_from_attribute=None))]
pub fn write_graphml_string_rust(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    prettyprint: bool,
    infer_numeric_types: bool,
    named_key_ids: bool,
    edge_id_from_attribute: Option<String>,
) -> PyResult<String> {
    let gr = extract_graph(g)?;
    if matches!(
        gr,
        GraphRef::MultiUndirected { .. } | GraphRef::MultiDirected { .. }
    ) {
        return Err(pyo3::exceptions::PyTypeError::new_err(
            "write_graphml_string_rust does not support MultiGraph or MultiDiGraph without losing parallel edges",
        ));
    }
    let graph_attrs = crate::py_dict_to_attr_map(gr.graph_attrs().bind(py))?;
    let config = fnx_algorithms::GraphMLWriterConfig {
        prettyprint,
        infer_numeric_types,
        named_key_ids,
        edge_id_from_attribute,
    };
    Ok(if gr.is_directed() {
        let dg = gr.digraph().expect("is_directed checked above");
        fnx_algorithms::write_graphml_string_directed_config_with_graph_attrs(
            dg,
            Some(&graph_attrs),
            &config,
        )
    } else {
        let inner = gr.undirected();
        py.allow_threads(|| {
            fnx_algorithms::write_graphml_string_config_with_graph_attrs(
                inner,
                Some(&graph_attrs),
                &config,
            )
        })
    })
}

// ---------------------------------------------------------------------------
// All-pairs node connectivity / all-pairs all shortest paths / LCA
// ---------------------------------------------------------------------------

/// All-pairs node connectivity.
#[pyfunction]
pub fn all_pairs_node_connectivity_rust(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
) -> PyResult<Py<PyDict>> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    let result = py.allow_threads(|| fnx_algorithms::all_pairs_node_connectivity(inner));
    let dict = PyDict::new(py);
    for ((u, v), conn) in &result {
        dict.set_item((gr.py_node_key(py, u), gr.py_node_key(py, v)), conn)?;
    }
    Ok(dict.unbind())
}

/// All-pairs all shortest paths.
#[pyfunction]
pub fn all_pairs_all_shortest_paths_rust(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
) -> PyResult<Py<PyDict>> {
    let gr = extract_graph(g)?;
    let result = if gr.is_directed() {
        let inner = gr.digraph().expect("is_directed checked above");
        py.allow_threads(|| fnx_algorithms::all_pairs_all_shortest_paths(inner))
    } else {
        let inner = gr.undirected();
        py.allow_threads(|| fnx_algorithms::all_pairs_all_shortest_paths(inner))
    };
    let outer = PyDict::new(py);
    for (source, targets) in &result {
        let inner_dict = PyDict::new(py);
        for (target, paths) in targets {
            let py_paths: Vec<Vec<PyObject>> = paths
                .iter()
                .map(|p| p.iter().map(|n| gr.py_node_key(py, n)).collect())
                .collect();
            inner_dict.set_item(gr.py_node_key(py, target), py_paths)?;
        }
        outer.set_item(gr.py_node_key(py, source), inner_dict)?;
    }
    Ok(outer.unbind())
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

// ---------------------------------------------------------------------------
// SimRank similarity
// ---------------------------------------------------------------------------

/// SimRank similarity between all pairs.
#[pyfunction]
#[pyo3(signature = (g, source=None, target=None, importance_factor=0.9, max_iterations=100, tolerance=1e-4))]
pub fn simrank_similarity_rust(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    source: Option<&Bound<'_, PyAny>>,
    target: Option<&Bound<'_, PyAny>>,
    importance_factor: f64,
    max_iterations: usize,
    tolerance: f64,
) -> PyResult<PyObject> {
    let gr = extract_graph(g)?;
    if let (Some(src), Some(tgt)) = (source, target) {
        let s = node_key_to_string(py, src)?;
        let t = node_key_to_string(py, tgt)?;
        if gr.is_directed() {
            let dg = gr.digraph().expect("is_directed checked above");
            let val = py.allow_threads(|| {
                let all = fnx_algorithms::simrank_similarity_directed(
                    dg,
                    importance_factor,
                    max_iterations,
                    tolerance,
                );
                all.get(&s)
                    .and_then(|row| row.get(&t))
                    .copied()
                    .unwrap_or(0.0)
            });
            Ok(val.into_pyobject(py)?.into_any().unbind())
        } else {
            let inner = gr.undirected();
            let val = py.allow_threads(|| {
                fnx_algorithms::simrank_similarity_pair(
                    inner,
                    &s,
                    &t,
                    importance_factor,
                    max_iterations,
                    tolerance,
                )
            });
            Ok(val.into_pyobject(py)?.into_any().unbind())
        }
    } else {
        if gr.is_directed() {
            let dg = gr.digraph().expect("is_directed checked above");
            let result = py.allow_threads(|| {
                fnx_algorithms::simrank_similarity_directed(
                    dg,
                    importance_factor,
                    max_iterations,
                    tolerance,
                )
            });
            let dict = PyDict::new(py);
            for (u, row) in &result {
                let inner_dict = PyDict::new(py);
                for (v, val) in row {
                    inner_dict.set_item(gr.py_node_key(py, v), val)?;
                }
                dict.set_item(gr.py_node_key(py, u), inner_dict)?;
            }
            Ok(dict.into_any().unbind())
        } else {
            let inner = gr.undirected();
            let result = py.allow_threads(|| {
                fnx_algorithms::simrank_similarity(
                    inner,
                    importance_factor,
                    max_iterations,
                    tolerance,
                )
            });
            let dict = PyDict::new(py);
            for (u, row) in &result {
                let inner_dict = PyDict::new(py);
                for (v, val) in row {
                    inner_dict.set_item(gr.py_node_key(py, v), val)?;
                }
                dict.set_item(gr.py_node_key(py, u), inner_dict)?;
            }
            Ok(dict.into_any().unbind())
        }
    }
}

// ---------------------------------------------------------------------------
// Google matrix
// ---------------------------------------------------------------------------

/// Google PageRank matrix.
#[pyfunction]
#[pyo3(signature = (g, alpha=0.85, weight="weight"))]
pub fn google_matrix_rust(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    alpha: f64,
    weight: &str,
) -> PyResult<PyObject> {
    let gr = extract_graph(g)?;
    let w = weight.to_owned();
    let (mat, node_list) = if gr.is_directed() {
        let dg = gr.digraph().expect("is_directed checked above");
        py.allow_threads(|| fnx_algorithms::google_matrix_directed(dg, alpha, &w))
    } else {
        let inner = gr.undirected();
        py.allow_threads(|| fnx_algorithms::google_matrix(inner, alpha, &w))
    };
    // Return as list of lists (Python doesn't have numpy here)
    let n = node_list.len();
    let outer = pyo3::types::PyList::empty(py);
    for i in 0..n {
        let row = pyo3::types::PyList::empty(py);
        for j in 0..n {
            row.append(mat[i * n + j])?;
        }
        outer.append(row)?;
    }
    Ok(outer.into_any().unbind())
}

// ---------------------------------------------------------------------------
// Second-order centrality
// ---------------------------------------------------------------------------

/// Second-order centrality.
#[pyfunction]
pub fn second_order_centrality_rust(py: Python<'_>, g: &Bound<'_, PyAny>) -> PyResult<PyObject> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    let result = py.allow_threads(|| fnx_algorithms::second_order_centrality(inner));
    let dict = PyDict::new(py);
    for (node, val) in &result {
        dict.set_item(gr.py_node_key(py, node), val)?;
    }
    Ok(dict.into_any().unbind())
}

// ---------------------------------------------------------------------------
// Communicability betweenness centrality
// ---------------------------------------------------------------------------

/// Communicability betweenness centrality.
#[pyfunction]
#[pyo3(signature = (g, normalized=true))]
pub fn communicability_betweenness_centrality_rust(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    normalized: bool,
) -> PyResult<PyObject> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    let result = py.allow_threads(|| {
        fnx_algorithms::communicability_betweenness_centrality(inner, normalized)
    });
    let dict = PyDict::new(py);
    for (node, val) in &result {
        dict.set_item(gr.py_node_key(py, node), val)?;
    }
    Ok(dict.into_any().unbind())
}

// ---------------------------------------------------------------------------
// Subgraph centrality
// ---------------------------------------------------------------------------

/// Subgraph centrality via native safe-Rust matrix exponential diagonal.
#[pyfunction]
pub fn subgraph_centrality_expdiag_rust(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
) -> PyResult<PyObject> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    let result = py.allow_threads(|| fnx_algorithms::subgraph_centrality_expdiag(inner));
    let dict = PyDict::new(py);
    for score in &result {
        dict.set_item(gr.py_node_key(py, &score.node), score.score)?;
    }
    Ok(dict.into_any().unbind())
}

/// Native safe-Rust Lanczos/Ritz Fiedler vector for dense unweighted simple graphs.
#[pyfunction]
#[pyo3(signature = (g, max_iter=96, tolerance=1e-8))]
pub fn fiedler_vector_unweighted_lanczos_rust(
    _py: Python<'_>,
    g: &Bound<'_, PyAny>,
    max_iter: usize,
    tolerance: f64,
) -> PyResult<Option<Vec<f64>>> {
    let gr = extract_graph(g)?;
    let GraphRef::Undirected(pg) = &gr else {
        return Ok(None);
    };
    let result = fnx_algorithms::fiedler_vector_unweighted_lanczos(&pg.inner, max_iter, tolerance);
    Ok(result)
}

/// Ascending eigenvalues of a real symmetric `n×n` matrix supplied as a flat
/// C-order `f64` sequence, via a 100% safe-Rust Householder→QL pipeline (no C
/// BLAS/LAPACK). Behavioural analogue of `numpy.linalg.eigvalsh` for symmetric
/// input. Returns `None` on a dimension mismatch or non-convergence so the
/// Python caller can fall back to the dense reference path. (br-r37-c1-04z53.9109)
#[pyfunction]
#[pyo3(signature = (matrix, n))]
pub fn symmetric_eigvals_rust(
    py: Python<'_>,
    matrix: Vec<f64>,
    n: usize,
) -> PyResult<Option<Vec<f64>>> {
    if matrix.len() != n * n {
        return Ok(None);
    }
    let result = py.allow_threads(|| fnx_algorithms::symmetric_eigvals(&matrix, n));
    Ok(result)
}

/// Eigenvalues of a real dense `n×n` matrix supplied as flat C-order `f64`,
/// returned as `(real, imag)` pairs from the safe-Rust Hessenberg→QR prototype.
/// This is intentionally separate from `adjacency_spectrum` until public raw
/// order parity with SciPy's `eigvals` is proven.
#[pyfunction]
#[pyo3(signature = (matrix, n))]
pub fn real_general_eigvals_rust(
    py: Python<'_>,
    matrix: Vec<f64>,
    n: usize,
) -> PyResult<Option<Vec<(f64, f64)>>> {
    if matrix.len() != n * n {
        return Ok(None);
    }
    let result = py.allow_threads(|| fnx_algorithms::real_general_eigvals(&matrix, n));
    Ok(result)
}

/// Small-graph unweighted Laplacian spectrum via native dense Laplacian
/// construction plus the safe-Rust symmetric eigensolver. Returns `None` for
/// directed/multigraph inputs, graphs above `max_n`, or edges carrying the
/// requested weight attribute so Python can fall back to the exact matrix path.
#[pyfunction]
#[pyo3(signature = (g, weight_attr=None, max_n=64))]
pub fn unweighted_laplacian_spectrum_rust(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    weight_attr: Option<&str>,
    max_n: usize,
) -> PyResult<Option<Vec<f64>>> {
    let gr = extract_graph(g)?;
    let GraphRef::Undirected(pg) = &gr else {
        return Ok(None);
    };
    if let Some(attr) = weight_attr {
        for dict in pg.edge_py_attrs.values() {
            if dict.bind(py).contains(attr)? {
                return Ok(None);
            }
        }
    }
    let result = fnx_algorithms::unweighted_laplacian_spectrum(&pg.inner, weight_attr, max_n);
    Ok(result)
}

// ---------------------------------------------------------------------------
// Current-flow betweenness centrality
// ---------------------------------------------------------------------------

/// Current-flow betweenness centrality.
#[pyfunction]
#[pyo3(signature = (g, normalized=true, weight="weight"))]
pub fn current_flow_betweenness_centrality_rust(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    normalized: bool,
    weight: &str,
) -> PyResult<PyObject> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    let w = weight.to_owned();
    let result = py.allow_threads(|| {
        fnx_algorithms::current_flow_betweenness_centrality(inner, normalized, &w)
    });
    let dict = PyDict::new(py);
    for (node, val) in &result {
        dict.set_item(gr.py_node_key(py, node), val)?;
    }
    Ok(dict.into_any().unbind())
}

/// Pseudo-peripheral start node for the current-flow RCM ordering.
#[pyfunction]
pub fn current_flow_pseudo_peripheral_node_rust(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
) -> PyResult<PyObject> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    let result = py
        .allow_threads(|| fnx_algorithms::current_flow_pseudo_peripheral_node(inner))
        .ok_or_else(|| PyRuntimeError::new_err("empty graph has no pseudo-peripheral node"))?;
    Ok(gr.py_node_key(py, &result))
}

/// NetworkX-compatible current-flow betweenness for the default full-solver path.
#[pyfunction]
#[pyo3(signature = (g, ordering, normalized=true, weight=None))]
pub fn current_flow_betweenness_centrality_nx_ordered_rust(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    ordering: &Bound<'_, PyAny>,
    normalized: bool,
    weight: Option<&str>,
) -> PyResult<PyObject> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    let mut canonical_ordering = Vec::with_capacity(inner.node_count());
    for item in PyIterator::from_object(ordering)? {
        let node = item?;
        canonical_ordering.push(node_key_to_string(py, &node)?);
    }
    let result = py
        .allow_threads(|| {
            fnx_algorithms::current_flow_betweenness_centrality_nx_ordered(
                inner,
                &canonical_ordering,
                normalized,
                weight,
            )
        })
        .ok_or_else(|| PyRuntimeError::new_err("singular grounded Laplacian"))?;
    let dict = PyDict::new(py);
    for score in &result {
        dict.set_item(gr.py_node_key(py, &score.node), score.score)?;
    }
    Ok(dict.into_any().unbind())
}

/// Current-flow closeness centrality for the default unweighted LU path.
#[pyfunction]
#[pyo3(signature = (g, ordering, weight=None))]
pub fn current_flow_closeness_centrality_rust(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    ordering: &Bound<'_, PyAny>,
    weight: Option<&str>,
) -> PyResult<PyObject> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    let mut canonical_ordering = Vec::with_capacity(inner.node_count());
    for item in PyIterator::from_object(ordering)? {
        let node = item?;
        canonical_ordering.push(node_key_to_string(py, &node)?);
    }
    let result = py
        .allow_threads(|| {
            fnx_algorithms::current_flow_closeness_centrality_ordered(
                inner,
                &canonical_ordering,
                weight,
            )
        })
        .ok_or_else(|| PyRuntimeError::new_err("singular grounded Laplacian"))?;
    let dict = PyDict::new(py);
    for score in &result {
        dict.set_item(gr.py_node_key(py, &score.node), score.score)?;
    }
    Ok(dict.into_any().unbind())
}

// ---------------------------------------------------------------------------
// k-clique communities
// ---------------------------------------------------------------------------

/// k-clique communities via clique percolation.
#[pyfunction]
#[pyo3(signature = (g, k))]
pub fn k_clique_communities_rust(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    k: usize,
) -> PyResult<Vec<PyObject>> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    let communities = py.allow_threads(|| fnx_algorithms::k_clique_communities(inner, k));
    communities
        .into_iter()
        .map(|comm| {
            let py_set =
                pyo3::types::PyFrozenSet::new(py, comm.iter().map(|n| gr.py_node_key(py, n)))?;
            Ok(py_set.into_any().unbind())
        })
        .collect()
}

// ---------------------------------------------------------------------------
// Edge current-flow betweenness centrality
// ---------------------------------------------------------------------------

/// Edge current-flow betweenness centrality.
#[pyfunction]
#[pyo3(signature = (g, normalized=true, weight="weight"))]
pub fn edge_current_flow_betweenness_centrality_rust(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    normalized: bool,
    weight: &str,
) -> PyResult<PyObject> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    let w = weight.to_owned();
    let result = py.allow_threads(|| {
        fnx_algorithms::edge_current_flow_betweenness_centrality(inner, normalized, &w)
    });
    let dict = PyDict::new(py);
    for ((u, v), val) in &result {
        let key = (gr.py_node_key(py, u), gr.py_node_key(py, v));
        dict.set_item(key, val)?;
    }
    Ok(dict.into_any().unbind())
}

/// NetworkX-compatible edge current-flow betweenness for the default full-solver path.
#[pyfunction]
#[pyo3(signature = (g, ordering, normalized=true, weight=None))]
pub fn edge_current_flow_betweenness_centrality_nx_ordered_rust(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
    ordering: &Bound<'_, PyAny>,
    normalized: bool,
    weight: Option<&str>,
) -> PyResult<PyObject> {
    let gr = extract_graph(g)?;
    let inner = gr.undirected();
    let mut canonical_ordering = Vec::with_capacity(inner.node_count());
    for item in PyIterator::from_object(ordering)? {
        let node = item?;
        canonical_ordering.push(node_key_to_string(py, &node)?);
    }
    let result = py
        .allow_threads(|| {
            fnx_algorithms::edge_current_flow_betweenness_centrality_nx_ordered(
                inner,
                &canonical_ordering,
                normalized,
                weight,
            )
        })
        .ok_or_else(|| PyRuntimeError::new_err("singular grounded Laplacian"))?;
    let dict = PyDict::new(py);
    for score in &result {
        let key = (
            gr.py_node_key(py, &score.left),
            gr.py_node_key(py, &score.right),
        );
        dict.set_item(key, score.score)?;
    }
    Ok(dict.into_any().unbind())
}

/// Register all algorithm functions into the Python module.
pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    // Shortest path
    m.add_function(wrap_pyfunction!(shortest_path, m)?)?;
    m.add_function(wrap_pyfunction!(shortest_path_length, m)?)?;
    m.add_function(wrap_pyfunction!(has_path, m)?)?;
    m.add_function(wrap_pyfunction!(average_shortest_path_length, m)?)?;
    m.add_function(wrap_pyfunction!(dijkstra_path, m)?)?;
    m.add_function(wrap_pyfunction!(graph_has_negative_edge_weight, m)?)?;
    m.add_function(wrap_pyfunction!(graph_has_nonfinite_edge_weight, m)?)?;
    m.add_function(wrap_pyfunction!(graph_has_nonnumeric_edge_weight, m)?)?;
    m.add_function(wrap_pyfunction!(graph_edge_weights_all_int, m)?)?;
    m.add_function(wrap_pyfunction!(check_dijkstra_edge_weights_fast, m)?)?;
    m.add_function(wrap_pyfunction!(graph_has_explicit_nonunit_weight_fast, m)?)?;
    m.add_function(wrap_pyfunction!(dijkstra_weight_cache_token, m)?)?;
    m.add_function(wrap_pyfunction!(adjacency_arrays, m)?)?;
    m.add_function(wrap_pyfunction!(adjacency_index_arrays, m)?)?;
    m.add_function(wrap_pyfunction!(biadjacency_coo, m)?)?;
    m.add_function(wrap_pyfunction!(adjacency_default_order_index_arrays, m)?)?;
    m.add_function(wrap_pyfunction!(adjacency_default_order_arrays, m)?)?;
    m.add_function(wrap_pyfunction!(adjacency_default_order_typed_arrays, m)?)?;
    m.add_function(wrap_pyfunction!(adjacency_nodelist_typed_arrays, m)?)?;
    m.add_function(wrap_pyfunction!(fnx_to_nx_adjacency, m)?)?;
    m.add_function(wrap_pyfunction!(graph_has_edge_attr, m)?)?;
    m.add_function(wrap_pyfunction!(graph_has_any_attrs, m)?)?;
    m.add_function(wrap_pyfunction!(bellman_ford_path, m)?)?;
    m.add_function(wrap_pyfunction!(multi_source_dijkstra, m)?)?;
    m.add_function(wrap_pyfunction!(bidirectional_dijkstra, m)?)?;
    // Connectivity
    m.add_function(wrap_pyfunction!(is_connected, m)?)?;
    m.add_function(wrap_pyfunction!(connected_components, m)?)?;
    m.add_function(wrap_pyfunction!(number_connected_components, m)?)?;
    m.add_function(wrap_pyfunction!(node_connectivity, m)?)?;
    m.add_function(wrap_pyfunction!(
        approx_local_node_connectivity_undirected_rust,
        m
    )?)?;
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
    m.add_function(wrap_pyfunction!(betweenness_centrality_sampled_rust, m)?)?;
    m.add_function(wrap_pyfunction!(edge_betweenness_centrality, m)?)?;
    m.add_function(wrap_pyfunction!(edge_betweenness_centrality_weighted, m)?)?;
    m.add_function(wrap_pyfunction!(betweenness_centrality_subset_rust, m)?)?;
    m.add_function(wrap_pyfunction!(
        betweenness_centrality_subset_weighted_rust,
        m
    )?)?;
    m.add_function(wrap_pyfunction!(
        edge_betweenness_centrality_subset_rust,
        m
    )?)?;
    m.add_function(wrap_pyfunction!(
        edge_betweenness_centrality_subset_weighted_rust,
        m
    )?)?;
    m.add_function(wrap_pyfunction!(load_centrality, m)?)?;
    m.add_function(wrap_pyfunction!(load_centrality_weighted, m)?)?;
    m.add_function(wrap_pyfunction!(percolation_centrality_weighted, m)?)?;
    m.add_function(wrap_pyfunction!(closeness_vitality, m)?)?;
    m.add_function(wrap_pyfunction!(eigenvector_centrality, m)?)?;
    m.add_function(wrap_pyfunction!(pagerank, m)?)?;
    m.add_function(wrap_pyfunction!(hits, m)?)?;
    m.add_function(wrap_pyfunction!(average_neighbor_degree, m)?)?;
    m.add_function(wrap_pyfunction!(degree_assortativity_coefficient, m)?)?;
    m.add_function(wrap_pyfunction!(
        degree_assortativity_coefficient_directed,
        m
    )?)?;
    m.add_function(wrap_pyfunction!(voterank, m)?)?;
    // Clustering
    m.add_function(wrap_pyfunction!(clustering, m)?)?;
    m.add_function(wrap_pyfunction!(average_clustering, m)?)?;
    m.add_function(wrap_pyfunction!(transitivity, m)?)?;
    m.add_function(wrap_pyfunction!(triangles, m)?)?;
    m.add_function(wrap_pyfunction!(square_clustering, m)?)?;
    m.add_function(wrap_pyfunction!(robins_alexander_counts, m)?)?;
    m.add_function(wrap_pyfunction!(find_cliques, m)?)?;
    m.add_function(wrap_pyfunction!(find_cliques_adjacency_sets, m)?)?;
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
    m.add_function(wrap_pyfunction!(min_cost_flow, m)?)?;
    m.add_function(wrap_pyfunction!(min_cost_flow_cost, m)?)?;
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
    m.add_function(wrap_pyfunction!(k_core_rust, m)?)?;
    m.add_function(wrap_pyfunction!(k_shell_rust, m)?)?;
    m.add_function(wrap_pyfunction!(k_crust_rust, m)?)?;
    m.add_function(wrap_pyfunction!(k_corona_rust, m)?)?;
    m.add_function(wrap_pyfunction!(onion_layers_rust, m)?)?;
    m.add_function(wrap_pyfunction!(from_prufer_sequence_rust, m)?)?;
    m.add_function(wrap_pyfunction!(to_prufer_sequence_rust, m)?)?;
    m.add_function(wrap_pyfunction!(k_truss_rust, m)?)?;
    m.add_function(wrap_pyfunction!(number_of_spanning_trees, m)?)?;
    m.add_function(wrap_pyfunction!(partition_spanning_tree, m)?)?;
    m.add_function(wrap_pyfunction!(random_spanning_tree, m)?)?;
    m.add_function(wrap_pyfunction!(minimum_spanning_tree, m)?)?;
    m.add_function(wrap_pyfunction!(minimum_spanning_edges, m)?)?;
    m.add_function(wrap_pyfunction!(prim_spanning_edges, m)?)?;
    m.add_function(wrap_pyfunction!(bipartite_hopcroft_karp_matching, m)?)?;
    m.add_function(wrap_pyfunction!(approx_average_clustering, m)?)?;
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
    m.add_function(wrap_pyfunction!(minimum_cycle_basis, m)?)?;
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
    m.add_function(wrap_pyfunction!(condensation_nx_ordered, m)?)?;
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
    m.add_function(wrap_pyfunction!(grid_graph, m)?)?;
    m.add_function(wrap_pyfunction!(dorogovtsev_goltsev_mendes_graph, m)?)?;
    m.add_function(wrap_pyfunction!(null_graph, m)?)?;
    m.add_function(wrap_pyfunction!(trivial_graph, m)?)?;
    m.add_function(wrap_pyfunction!(binomial_tree, m)?)?;
    m.add_function(wrap_pyfunction!(full_rary_tree, m)?)?;
    m.add_function(wrap_pyfunction!(circulant_graph, m)?)?;
    m.add_function(wrap_pyfunction!(kneser_graph, m)?)?;
    m.add_function(wrap_pyfunction!(paley_graph, m)?)?;
    m.add_function(wrap_pyfunction!(chordal_cycle_graph, m)?)?;
    m.add_function(wrap_pyfunction!(sudoku_graph, m)?)?;
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
    m.add_function(wrap_pyfunction!(line_graph, m)?)?;
    m.add_function(wrap_pyfunction!(cartesian_product, m)?)?;
    m.add_function(wrap_pyfunction!(tensor_product, m)?)?;
    m.add_function(wrap_pyfunction!(cartesian_product_fast, m)?)?;
    m.add_function(wrap_pyfunction!(tensor_product_fast, m)?)?;
    m.add_function(wrap_pyfunction!(strong_product_fast, m)?)?;
    m.add_function(wrap_pyfunction!(lexicographic_product_fast, m)?)?;
    m.add_function(wrap_pyfunction!(modular_product_fast, m)?)?;
    m.add_function(wrap_pyfunction!(rooted_product_fast, m)?)?;
    m.add_function(wrap_pyfunction!(corona_product_fast, m)?)?;
    m.add_function(wrap_pyfunction!(line_graph_fast, m)?)?;
    m.add_function(wrap_pyfunction!(degree_histogram, m)?)?;
    // A* shortest path
    m.add_function(wrap_pyfunction!(astar_path, m)?)?;
    m.add_function(wrap_pyfunction!(astar_path_length, m)?)?;
    m.add_function(wrap_pyfunction!(shortest_simple_paths, m)?)?;
    // Graph isomorphism
    m.add_function(wrap_pyfunction!(is_isomorphic, m)?)?;
    m.add_function(wrap_pyfunction!(vf2pp_isomorphism_rust, m)?)?;
    m.add_function(wrap_pyfunction!(vf2pp_all_isomorphisms_rust, m)?)?;
    m.add_function(wrap_pyfunction!(graph_edit_distance_common_rust, m)?)?;
    m.add_function(wrap_pyfunction!(could_be_isomorphic, m)?)?;
    m.add_function(wrap_pyfunction!(fast_could_be_isomorphic, m)?)?;
    m.add_function(wrap_pyfunction!(faster_could_be_isomorphic, m)?)?;
    // Planarity
    m.add_function(wrap_pyfunction!(is_planar, m)?)?;
    m.add_function(wrap_pyfunction!(is_planar_lr, m)?)?;
    m.add_function(wrap_pyfunction!(planarity_euler_reject, m)?)?;
    // Chordality
    m.add_function(wrap_pyfunction!(is_chordal, m)?)?;
    // Barycenter
    m.add_function(wrap_pyfunction!(barycenter, m)?)?;
    m.add_function(wrap_pyfunction!(find_cycle_simple, m)?)?;
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
    m.add_function(wrap_pyfunction!(dijkstra_predecessor_and_distance, m)?)?;
    m.add_function(wrap_pyfunction!(single_source_bellman_ford, m)?)?;
    m.add_function(wrap_pyfunction!(single_source_bellman_ford_path, m)?)?;
    m.add_function(wrap_pyfunction!(single_source_bellman_ford_path_length, m)?)?;
    m.add_function(wrap_pyfunction!(single_target_shortest_path, m)?)?;
    m.add_function(wrap_pyfunction!(single_target_shortest_path_length, m)?)?;
    m.add_function(wrap_pyfunction!(all_pairs_dijkstra_path_length, m)?)?;
    m.add_function(wrap_pyfunction!(all_pairs_dijkstra_path, m)?)?;
    m.add_function(wrap_pyfunction!(johnson_path_directed, m)?)?;
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
    m.add_function(wrap_pyfunction!(stoer_wagner_phases, m)?)?;
    // Chain decomposition
    m.add_function(wrap_pyfunction!(chain_decomposition, m)?)?;
    // All topological sorts
    m.add_function(wrap_pyfunction!(all_topological_sorts_rust, m)?)?;
    // Structural holes
    m.add_function(wrap_pyfunction!(constraint_rust, m)?)?;
    m.add_function(wrap_pyfunction!(local_constraint_rust, m)?)?;
    m.add_function(wrap_pyfunction!(effective_size_rust, m)?)?;
    m.add_function(wrap_pyfunction!(effective_size_directed_rust, m)?)?;
    m.add_function(wrap_pyfunction!(dispersion_full_rust, m)?)?;
    m.add_function(wrap_pyfunction!(dispersion_node_rust, m)?)?;
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
    m.add_function(wrap_pyfunction!(square_clustering_fast, m)?)?;
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
    m.add_function(wrap_pyfunction!(hyper_wiener_index_weighted_rust, m)?)?;
    m.add_function(wrap_pyfunction!(schultz_index_rust, m)?)?;
    m.add_function(wrap_pyfunction!(harmonic_diameter_rust, m)?)?;
    // Self-loop functions
    m.add_function(wrap_pyfunction!(selfloop_edges_rust, m)?)?;
    m.add_function(wrap_pyfunction!(number_of_selfloops_rust, m)?)?;
    m.add_function(wrap_pyfunction!(multigraph_number_of_selfloops_rust, m)?)?;
    m.add_function(wrap_pyfunction!(nodes_with_selfloops_rust, m)?)?;
    // To dict of lists
    m.add_function(wrap_pyfunction!(to_dict_of_lists_rust, m)?)?;
    // Soundarajan-Hopcroft link prediction
    m.add_function(wrap_pyfunction!(cn_soundarajan_hopcroft_rust, m)?)?;
    m.add_function(wrap_pyfunction!(ra_index_soundarajan_hopcroft_rust, m)?)?;
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
    m.add_function(wrap_pyfunction!(tree_all_pairs_lca_rust, m)?)?;
    // Generate edgelist
    m.add_function(wrap_pyfunction!(generate_edgelist_rust, m)?)?;
    // Group betweenness
    m.add_function(wrap_pyfunction!(group_betweenness_centrality_rust, m)?)?;
    // Attribute assortativity
    m.add_function(wrap_pyfunction!(
        attribute_assortativity_coefficient_rust,
        m
    )?)?;
    // Gomory-Hu tree
    m.add_function(wrap_pyfunction!(gomory_hu_tree_rust, m)?)?;
    // Find asteroidal triple
    m.add_function(wrap_pyfunction!(find_asteroidal_triple_rust, m)?)?;
    // SNAP aggregation
    m.add_function(wrap_pyfunction!(snap_aggregation_rust, m)?)?;
    // Iterators
    m.add_class::<SpanningTreeIteratorRust>()?;
    m.add_class::<ArborescenceIteratorRust>()?;
    // GraphML writer
    m.add_function(wrap_pyfunction!(write_graphml_string_rust, m)?)?;
    // All-pairs
    m.add_function(wrap_pyfunction!(all_pairs_node_connectivity_rust, m)?)?;
    m.add_function(wrap_pyfunction!(all_pairs_all_shortest_paths_rust, m)?)?;
    // SimRank, Google matrix, second-order centrality, communicability/current-flow betweenness
    m.add_function(wrap_pyfunction!(simrank_similarity_rust, m)?)?;
    m.add_function(wrap_pyfunction!(google_matrix_rust, m)?)?;
    m.add_function(wrap_pyfunction!(second_order_centrality_rust, m)?)?;
    m.add_function(wrap_pyfunction!(subgraph_centrality_expdiag_rust, m)?)?;
    m.add_function(wrap_pyfunction!(fiedler_vector_unweighted_lanczos_rust, m)?)?;
    m.add_function(wrap_pyfunction!(symmetric_eigvals_rust, m)?)?;
    m.add_function(wrap_pyfunction!(real_general_eigvals_rust, m)?)?;
    m.add_function(wrap_pyfunction!(unweighted_laplacian_spectrum_rust, m)?)?;
    m.add_function(wrap_pyfunction!(
        communicability_betweenness_centrality_rust,
        m
    )?)?;
    m.add_function(wrap_pyfunction!(
        current_flow_betweenness_centrality_rust,
        m
    )?)?;
    m.add_function(wrap_pyfunction!(
        current_flow_betweenness_centrality_nx_ordered_rust,
        m
    )?)?;
    m.add_function(wrap_pyfunction!(
        current_flow_pseudo_peripheral_node_rust,
        m
    )?)?;
    m.add_function(wrap_pyfunction!(current_flow_closeness_centrality_rust, m)?)?;
    m.add_function(wrap_pyfunction!(k_clique_communities_rust, m)?)?;
    m.add_function(wrap_pyfunction!(
        edge_current_flow_betweenness_centrality_rust,
        m
    )?)?;
    m.add_function(wrap_pyfunction!(
        edge_current_flow_betweenness_centrality_nx_ordered_rust,
        m
    )?)?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use fnx_classes::digraph::MultiDiGraph;
    use fnx_classes::{AttrMap, MultiGraph};
    use fnx_runtime::CompatibilityMode;

    fn ensure_python() {
        Python::initialize();
    }

    #[test]
    fn multigraph_projections_preserve_mode() {
        let mut graph = MultiGraph::new(CompatibilityMode::Hardened);
        let mut attrs = AttrMap::new();
        attrs.insert("weight".to_owned(), 2.0.into());
        graph
            .add_edge_with_attrs("u".to_owned(), "v".to_owned(), attrs)
            .expect("edge should add");
        let expected_policy = graph.runtime_policy().clone();

        let simple = multigraph_to_simple_graph(&graph);
        let weighted = multigraph_to_weighted_simple_graph(&graph, "weight");

        assert_eq!(simple.mode(), CompatibilityMode::Hardened);
        assert_eq!(simple.runtime_policy(), &expected_policy);
        assert_eq!(weighted.mode(), CompatibilityMode::Hardened);
        assert_eq!(weighted.runtime_policy(), &expected_policy);
    }

    #[test]
    fn multidigraph_projections_preserve_mode() {
        let mut graph = MultiDiGraph::new(CompatibilityMode::Hardened);
        let mut attrs = AttrMap::new();
        attrs.insert("weight".to_owned(), 3.0.into());
        graph
            .add_edge_with_attrs("u".to_owned(), "v".to_owned(), attrs)
            .expect("edge should add");
        let expected_policy = graph.runtime_policy().clone();

        let simple = multidigraph_to_simple_digraph(&graph);
        let weighted = multidigraph_to_weighted_simple_digraph(&graph, "weight");

        assert_eq!(simple.mode(), CompatibilityMode::Hardened);
        assert_eq!(simple.runtime_policy(), &expected_policy);
        assert_eq!(weighted.mode(), CompatibilityMode::Hardened);
        assert_eq!(weighted.runtime_policy(), &expected_policy);
    }

    #[test]
    fn dijkstra_simple_graph_projection_reads_live_weight_dict() {
        ensure_python();
        Python::attach(|py| {
            let mut graph = PyGraph::new_empty(py).expect("graph should initialize");
            let weighted_edge = |weight: f64| {
                let mut attrs = AttrMap::new();
                attrs.insert("weight".to_owned(), weight.into());
                attrs
            };
            graph
                .inner
                .add_edge_with_attrs("a".to_owned(), "b".to_owned(), weighted_edge(100.0))
                .expect("edge should add");
            graph
                .inner
                .add_edge_with_attrs("a".to_owned(), "c".to_owned(), weighted_edge(1.0))
                .expect("edge should add");
            graph
                .inner
                .add_edge_with_attrs("c".to_owned(), "b".to_owned(), weighted_edge(1.0))
                .expect("edge should add");

            let live_attrs = PyDict::new(py);
            live_attrs
                .set_item("weight", 0.25)
                .expect("weight attr should set");
            graph
                .edge_py_attrs
                .insert(PyGraph::edge_key("a", "b"), live_attrs.unbind());
            graph.edges_dirty.store(true, Ordering::Relaxed);

            let projection = dijkstra_single_weight_graph_projection(py, &graph, "weight")
                .expect("projection should build");
            let result = fnx_algorithms::shortest_path_weighted(&projection, "a", "b", "weight");

            assert_eq!(result.path, Some(vec!["a".to_owned(), "b".to_owned()]));
        });
    }

    #[test]
    fn dijkstra_simple_digraph_projection_reads_live_weight_dict() {
        ensure_python();
        Python::attach(|py| {
            let mut graph = PyDiGraph::new_empty(py).expect("digraph should initialize");
            let weighted_edge = |weight: f64| {
                let mut attrs = AttrMap::new();
                attrs.insert("weight".to_owned(), weight.into());
                attrs
            };
            graph
                .inner
                .add_edge_with_attrs("a".to_owned(), "b".to_owned(), weighted_edge(100.0))
                .expect("edge should add");
            graph
                .inner
                .add_edge_with_attrs("a".to_owned(), "c".to_owned(), weighted_edge(1.0))
                .expect("edge should add");
            graph
                .inner
                .add_edge_with_attrs("c".to_owned(), "b".to_owned(), weighted_edge(1.0))
                .expect("edge should add");

            let live_attrs = PyDict::new(py);
            live_attrs
                .set_item("weight", 0.25)
                .expect("weight attr should set");
            graph
                .edge_py_attrs
                .insert(PyDiGraph::edge_key("a", "b"), live_attrs.unbind());
            graph.edges_dirty.store(true, Ordering::Relaxed);

            let projection = dijkstra_single_weight_digraph_projection(py, &graph, "weight")
                .expect("projection should build");
            let result =
                fnx_algorithms::shortest_path_weighted_directed(&projection, "a", "b", "weight");

            assert_eq!(result.path, Some(vec!["a".to_owned(), "b".to_owned()]));
        });
    }

    #[test]
    fn spanning_helpers_preserve_mode() {
        ensure_python();
        Python::attach(|py| {
            let mut graph = PyGraph::new_empty(py).expect("graph should initialize");
            graph.inner = fnx_classes::Graph::new(CompatibilityMode::Hardened);
            let mut attrs = AttrMap::new();
            attrs.insert("weight".to_owned(), 1.0.into());
            graph
                .inner
                .add_edge_with_attrs("a".to_owned(), "b".to_owned(), attrs)
                .expect("edge should add");
            let expected_policy = graph.inner.runtime_policy().clone();

            let source = Py::new(py, graph).expect("py graph should initialize");

            {
                let borrow = source.bind(py).borrow();
                let gr = GraphRef::Undirected(borrow);
                let sanitized = spanning_input_graph(py, &gr, "weight", false)
                    .expect("sanitization should work");
                assert_eq!(sanitized.mode(), CompatibilityMode::Hardened);
                assert_eq!(sanitized.runtime_policy(), &expected_policy);
            }

            let borrow = source.bind(py).borrow();
            let tree = undirected_spanning_edges_to_pygraph(
                py,
                &borrow,
                &[("a".to_owned(), "b".to_owned())],
            )
            .expect("tree conversion should work");
            assert_eq!(tree.inner.mode(), CompatibilityMode::Hardened);
            assert_eq!(tree.inner.runtime_policy(), &expected_policy);
        });
    }

    #[test]
    fn python_algorithm_wrappers_preserve_mode() {
        ensure_python();
        Python::attach(|py| {
            let mut multigraph = PyMultiGraph {
                inner: MultiGraph::new(CompatibilityMode::Hardened),
                node_key_map: HashMap::new(),
                node_py_attrs: HashMap::new(),
                edge_py_attrs: HashMap::new(),
                adj_py_keys: HashMap::new(), // br-r37-c1-z6uka
                edge_py_keys: HashMap::new(),
                graph_attrs: PyDict::new(py).unbind(),
                nodes_seq: 0,
                edges_seq: 0,
                edges_dirty: AtomicBool::new(false),
                node_keys_cache: std::sync::Mutex::new(None),
                node_data_mirror: std::sync::Mutex::new(None),
                dict_of_dicts_cache: None,
                edges_with_data_cache: None,
                node_iter_mirror: std::sync::Mutex::new(None),
                edges_with_keys_cache: None,
            };
            let mut weighted_attrs = AttrMap::new();
            weighted_attrs.insert("weight".to_owned(), 1.0.into());
            multigraph
                .inner
                .add_edge_with_attrs("a".to_owned(), "b".to_owned(), weighted_attrs)
                .expect("edge should add");
            let expected_multigraph_policy = multigraph.inner.runtime_policy().clone();
            let multigraph = Py::new(py, multigraph).expect("py multigraph should initialize");

            let mst =
                minimum_spanning_tree(py, multigraph.bind(py).as_any(), "weight").expect("mst");
            assert_eq!(mst.inner.mode(), CompatibilityMode::Hardened);
            // br-r37-c1-cyyfg: the MST wrapper intentionally builds the result on
            // a fresh mode-only RuntimePolicy (br-r37-c1-7dpyg) rather than cloning
            // the source's unbounded decision ledger, which made MST 2.45x slower on
            // ctor-built sources. The preserved contract is therefore the
            // compatibility MODE and the policy allowlist, NOT the source's ledger;
            // the result's decision log is rebuilt from the tree's own construction.
            let mst_policy = mst.inner.runtime_policy();
            assert_eq!(mst_policy.mode(), expected_multigraph_policy.mode());
            assert_eq!(
                mst_policy.allowlist(),
                expected_multigraph_policy.allowlist()
            );

            let mut graph = PyGraph::new_empty(py).expect("graph should initialize");
            graph.inner = fnx_classes::Graph::new(CompatibilityMode::Hardened);
            graph
                .inner
                .add_edge("a".to_owned(), "b".to_owned())
                .expect("edge should add");
            graph
                .inner
                .add_edge("b".to_owned(), "c".to_owned())
                .expect("edge should add");
            let expected_graph_policy = graph.inner.runtime_policy().clone();
            let graph = Py::new(py, graph).expect("py graph should initialize");

            // br-r37-c1-cyyfg: these construction helpers build their result via the
            // bulk extend_*_unrecorded fast paths on a fresh mode-only policy, so the
            // preserved contract is the compatibility MODE and allowlist, not the
            // source's full decision ledger.
            let core =
                k_core_rust(py, graph.bind(py).as_any(), None).expect("k-core should succeed");
            let core_ref = core.bind(py).borrow();
            assert_eq!(core_ref.inner.mode(), CompatibilityMode::Hardened);
            assert_eq!(
                core_ref.inner.runtime_policy().mode(),
                expected_graph_policy.mode(),
            );
            assert_eq!(
                core_ref.inner.runtime_policy().allowlist(),
                expected_graph_policy.allowlist(),
            );

            let dfs = dfs_tree(py, graph.bind(py).as_any(), None, None, None)
                .expect("dfs tree should succeed");
            assert_eq!(dfs.inner.mode(), CompatibilityMode::Hardened);
            assert_eq!(
                dfs.inner.runtime_policy().mode(),
                expected_graph_policy.mode(),
            );
            assert_eq!(
                dfs.inner.runtime_policy().allowlist(),
                expected_graph_policy.allowlist(),
            );
        });
    }

    #[test]
    fn minimum_cycle_basis_binding_returns_python_cycles() {
        ensure_python();
        Python::attach(|py| {
            let mut graph = PyGraph::new_empty(py).expect("graph should initialize");
            let weighted_edge = |weight: f64| {
                let mut attrs = AttrMap::new();
                attrs.insert("weight".to_owned(), weight.into());
                attrs
            };
            graph
                .inner
                .add_edge_with_attrs("a".to_owned(), "b".to_owned(), weighted_edge(1.0))
                .expect("edge should add");
            graph
                .inner
                .add_edge_with_attrs("b".to_owned(), "c".to_owned(), weighted_edge(1.0))
                .expect("edge should add");
            graph
                .inner
                .add_edge_with_attrs("c".to_owned(), "a".to_owned(), weighted_edge(1.0))
                .expect("edge should add");
            let graph = Py::new(py, graph).expect("py graph should initialize");

            let cycles = minimum_cycle_basis(py, graph.bind(py).as_any(), Some("weight"))
                .expect("minimum cycle basis should succeed");
            let mut cycle = cycles
                .into_iter()
                .next()
                .expect("triangle should produce one cycle")
                .into_iter()
                .map(|node| node.extract::<String>(py).expect("string node"))
                .collect::<Vec<_>>();
            cycle.sort();

            assert_eq!(cycle, vec!["a", "b", "c"]);
        });
    }

    #[test]
    fn accumulate_weighted_average_shortest_path_length_sums_per_source() {
        let sources = vec!["a", "b", "c"];
        let mut visited = Vec::new();

        let total = accumulate_weighted_average_shortest_path_length(&sources, 3, |source| {
            visited.push(source.to_owned());
            Ok(HashMap::from([
                (source.to_owned(), 0.0),
                ("x".to_owned(), 1.5),
                ("y".to_owned(), 2.5),
            ]))
        })
        .expect("all sources should contribute");

        assert_eq!(visited, vec!["a", "b", "c"]);
        assert!((total - 12.0).abs() < f64::EPSILON);
    }

    #[test]
    fn accumulate_weighted_average_shortest_path_length_rejects_disconnected_sources() {
        let sources = vec!["a", "b"];
        let result = accumulate_weighted_average_shortest_path_length(&sources, 3, |_source| {
            Ok(HashMap::from([
                ("a".to_owned(), 0.0),
                ("b".to_owned(), 1.0),
            ]))
        });

        assert_eq!(result, Err(AverageShortestPathLengthFailure::Disconnected));
    }

    #[test]
    fn accumulate_weighted_average_shortest_path_length_propagates_negative_cycle() {
        let sources = vec!["a"];
        let result = accumulate_weighted_average_shortest_path_length(&sources, 1, |_source| {
            Err(AverageShortestPathLengthFailure::NegativeCycle)
        });

        assert_eq!(result, Err(AverageShortestPathLengthFailure::NegativeCycle));
    }
}
