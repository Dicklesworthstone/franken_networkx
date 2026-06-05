//! NetworkX-compatible view objects (NodeView, EdgeView, DegreeView).
//!
//! These views provide dict-like read access to graph data and reflect
//! the current state of the graph (they are "live" views backed by Py<PyGraph>).

use crate::{NodeIterator, PyGraph, PyObject, node_key_to_string};
use pyo3::exceptions::{PyKeyError, PyRuntimeError};
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyIterator, PyTuple};

// ---------------------------------------------------------------------------
// NodeView — returned by G.nodes or G.nodes(data=True)
// ---------------------------------------------------------------------------

/// A view of the graph's nodes. Supports ``len``, ``in``, iteration, and ``[]``.
///
/// When ``data=True``, iteration yields ``(node, attr_dict)`` pairs.
/// When ``data="attr_name"``, yields ``(node, attr_value)`` pairs.
#[pyclass(module = "franken_networkx")]
pub struct NodeView {
    graph: Py<PyGraph>,
    data: NodeViewData,
}

enum NodeViewData {
    NoData,
    AllData,
    Attr(String),
    AttrWithDefault(String, PyObject),
}

impl Clone for NodeViewData {
    fn clone(&self) -> Self {
        match self {
            Self::NoData => Self::NoData,
            Self::AllData => Self::AllData,
            Self::Attr(s) => Self::Attr(s.clone()),
            Self::AttrWithDefault(s, obj) => {
                Python::attach(|py| Self::AttrWithDefault(s.clone(), obj.clone_ref(py)))
            }
        }
    }
}

#[pymethods]
impl NodeView {
    fn __len__(&self, py: Python<'_>) -> usize {
        let g = self.graph.borrow(py);
        g.inner.node_count()
    }

    fn __contains__(&self, py: Python<'_>, n: &Bound<'_, PyAny>) -> PyResult<bool> {
        let g = self.graph.borrow(py);
        let canonical = node_key_to_string(py, n)?;
        Ok(g.inner.has_node(&canonical))
    }

    fn __iter__(&self, py: Python<'_>) -> PyResult<Py<NodeViewIterator>> {
        let nodes: Vec<String> = {
            let g = self.graph.borrow(py);
            g.inner
                .nodes_ordered()
                .into_iter()
                .map(str::to_owned)
                .collect()
        };
        let items: Vec<PyObject> = match &self.data {
            NodeViewData::NoData => {
                let g = self.graph.borrow(py);
                nodes.iter().map(|n| g.py_node_key(py, n)).collect()
            }
            NodeViewData::AllData => nodes
                .iter()
                .map(|n| {
                    let mut g = self.graph.borrow_mut(py);
                    let py_key = g.py_node_key(py, n);
                    let attrs = g.materialize_node_py_attrs(py, n);
                    tuple_object(py, &[py_key, attrs.into_any()])
                })
                .collect::<PyResult<Vec<_>>>()?,
            NodeViewData::Attr(attr) => {
                let g = self.graph.borrow(py);
                nodes
                    .iter()
                    .map(|n| {
                        let py_key = g.py_node_key(py, n);
                        let val = g
                            .node_py_attrs
                            .get(n)
                            .and_then(|dict| dict.bind(py).get_item(attr.as_str()).ok().flatten())
                            .map_or_else(|| py.None(), |v| v.unbind());
                        tuple_object(py, &[py_key, val])
                    })
                    .collect::<PyResult<Vec<_>>>()?
            }
            NodeViewData::AttrWithDefault(attr, default) => {
                let g = self.graph.borrow(py);
                nodes
                    .iter()
                    .map(|n| {
                        let py_key = g.py_node_key(py, n);
                        let val = g
                            .node_py_attrs
                            .get(n)
                            .and_then(|dict| dict.bind(py).get_item(attr.as_str()).ok().flatten())
                            .map_or_else(|| default.clone_ref(py), |v| v.unbind());
                        tuple_object(py, &[py_key, val])
                    })
                    .collect::<PyResult<Vec<_>>>()?
            }
        };
        let expected_seq = self.graph.borrow(py).nodes_seq;
        Py::new(
            py,
            NodeViewIterator {
                inner: items.into_iter(),
                graph: Some(self.graph.clone_ref(py)),
                expected_count: Some(nodes.len()),
                expected_seq: Some(expected_seq),
            },
        )
    }

    fn __getitem__(&self, py: Python<'_>, n: &Bound<'_, PyAny>) -> PyResult<Py<PyDict>> {
        let mut g = self.graph.borrow_mut(py);
        let canonical = node_key_to_string(py, n)?;
        if !g.inner.has_node(&canonical) {
            return Err(crate::missing_key_error(n));
        }
        Ok(g.materialize_node_py_attrs(py, &canonical))
    }

    #[pyo3(signature = (n, default=None))]
    fn get(
        &self,
        py: Python<'_>,
        n: &Bound<'_, PyAny>,
        default: Option<PyObject>,
    ) -> PyResult<PyObject> {
        let mut g = self.graph.borrow_mut(py);
        let canonical = node_key_to_string(py, n)?;
        if !g.inner.has_node(&canonical) {
            return Ok(default.unwrap_or_else(|| py.None()));
        }
        Ok(g.materialize_node_py_attrs(py, &canonical).into_any())
    }

    fn __repr__(&self, py: Python<'_>) -> String {
        let g = self.graph.borrow(py);
        let nodes: Vec<String> = g
            .inner
            .nodes_ordered()
            .iter()
            .map(|n| format!("'{}'", n))
            .collect();
        format!("NodeView(({}))", nodes.join(", "))
    }

    fn __bool__(&self, py: Python<'_>) -> bool {
        let g = self.graph.borrow(py);
        g.inner.node_count() > 0
    }

    /// Return a list of (node, data) or just nodes for calling like G.nodes(data=True).
    #[pyo3(signature = (data=None, default=None))]
    fn __call__(
        &self,
        py: Python<'_>,
        data: Option<&Bound<'_, PyAny>>,
        default: Option<&Bound<'_, PyAny>>,
    ) -> PyResult<Py<NodeView>> {
        let mut view_data = parse_data_param(data)?;
        // When a specific attribute is requested and default is provided,
        // upgrade to AttrWithDefault so iteration uses the default value
        if let (Some(def), NodeViewData::Attr(attr)) = (default, &view_data) {
            view_data = NodeViewData::AttrWithDefault(attr.clone(), def.clone().unbind());
        }
        Py::new(
            py,
            NodeView {
                graph: self.graph.clone_ref(py),
                data: view_data,
            },
        )
    }

    /// Return a list of node keys (like dict.keys()).
    fn keys(&self, py: Python<'_>) -> PyResult<Vec<PyObject>> {
        let g = self.graph.borrow(py);
        Ok(g.inner
            .nodes_ordered()
            .iter()
            .map(|n| g.py_node_key(py, n))
            .collect())
    }

    /// Return a list of (node, attrs) pairs (like dict.items()).
    fn items(&self, py: Python<'_>) -> PyResult<Vec<PyObject>> {
        let nodes: Vec<String> = {
            let g = self.graph.borrow(py);
            g.inner
                .nodes_ordered()
                .iter()
                .map(|n| (*n).to_owned())
                .collect()
        };
        let mut g = self.graph.borrow_mut(py);
        nodes
            .iter()
            .map(|n| {
                let py_key = g.py_node_key(py, n);
                let attrs = g.materialize_node_py_attrs(py, n).into_any();
                tuple_object(py, &[py_key, attrs])
            })
            .collect()
    }

    /// Return a list of attr dicts (like dict.values()).
    fn values(&self, py: Python<'_>) -> PyResult<Vec<PyObject>> {
        let nodes: Vec<String> = {
            let g = self.graph.borrow(py);
            g.inner
                .nodes_ordered()
                .iter()
                .map(|n| (*n).to_owned())
                .collect()
        };
        let mut g = self.graph.borrow_mut(py);
        Ok(nodes
            .iter()
            .map(|n| g.materialize_node_py_attrs(py, n).into_any())
            .collect())
    }

    /// Return a NodeDataView for iterating over (node, data) pairs.
    #[pyo3(signature = (data=None, default=None))]
    fn data(
        &self,
        py: Python<'_>,
        data: Option<&Bound<'_, PyAny>>,
        default: Option<&Bound<'_, PyAny>>,
    ) -> PyResult<Py<NodeView>> {
        let view_data = if let Some(d) = data {
            if d.is_truthy()? {
                if let Ok(s) = d.extract::<String>() {
                    if let Some(def) = default {
                        NodeViewData::AttrWithDefault(s, def.clone().unbind())
                    } else {
                        NodeViewData::Attr(s)
                    }
                } else {
                    NodeViewData::AllData
                }
            } else {
                NodeViewData::AllData
            }
        } else {
            NodeViewData::AllData
        };
        Py::new(
            py,
            NodeView {
                graph: self.graph.clone_ref(py),
                data: view_data,
            },
        )
    }

    /// Union: self | other
    fn __or__(&self, py: Python<'_>, other: &Bound<'_, PyAny>) -> PyResult<PyObject> {
        let g = self.graph.borrow(py);
        let self_nodes: Vec<PyObject> = g
            .inner
            .nodes_ordered()
            .iter()
            .map(|n| g.py_node_key(py, n))
            .collect();
        let self_set = pyo3::types::PySet::new(py, self_nodes.iter())?;
        for item in PyIterator::from_object(other)? {
            self_set.add(item?)?;
        }
        Ok(self_set.into_any().unbind())
    }

    /// Intersection: self & other
    fn __and__(&self, py: Python<'_>, other: &Bound<'_, PyAny>) -> PyResult<PyObject> {
        let g = self.graph.borrow(py);
        let other_vec: Vec<PyObject> = PyIterator::from_object(other)?
            .map(|r| r.map(|o| o.unbind()))
            .collect::<PyResult<Vec<_>>>()?;
        let other_set = pyo3::types::PySet::new(py, other_vec.iter())?;
        let mut result = Vec::new();
        for node in g.inner.nodes_ordered() {
            let py_key = g.py_node_key(py, node);
            if other_set.contains(&py_key)? {
                result.push(py_key);
            }
        }
        let set = pyo3::types::PySet::new(py, result.iter())?;
        Ok(set.into_any().unbind())
    }

    /// Difference: self - other
    fn __sub__(&self, py: Python<'_>, other: &Bound<'_, PyAny>) -> PyResult<PyObject> {
        let g = self.graph.borrow(py);
        let other_vec: Vec<PyObject> = PyIterator::from_object(other)?
            .map(|r| r.map(|o| o.unbind()))
            .collect::<PyResult<Vec<_>>>()?;
        let other_set = pyo3::types::PySet::new(py, other_vec.iter())?;
        let mut result = Vec::new();
        for node in g.inner.nodes_ordered() {
            let py_key = g.py_node_key(py, node);
            if !other_set.contains(&py_key)? {
                result.push(py_key);
            }
        }
        let set = pyo3::types::PySet::new(py, result.iter())?;
        Ok(set.into_any().unbind())
    }

    /// Symmetric difference: self ^ other
    fn __xor__(&self, py: Python<'_>, other: &Bound<'_, PyAny>) -> PyResult<PyObject> {
        let g = self.graph.borrow(py);
        let self_nodes: Vec<PyObject> = g
            .inner
            .nodes_ordered()
            .iter()
            .map(|n| g.py_node_key(py, n))
            .collect();
        let self_set = pyo3::types::PySet::new(py, self_nodes.iter())?;
        let other_vec: Vec<PyObject> = PyIterator::from_object(other)?
            .map(|r| r.map(|o| o.unbind()))
            .collect::<PyResult<Vec<_>>>()?;
        let other_set = pyo3::types::PySet::new(py, other_vec.iter())?;
        // XOR = (self - other) | (other - self)
        let mut result = Vec::new();
        for py_key in &self_nodes {
            if !other_set.contains(py_key)? {
                result.push(py_key.clone_ref(py));
            }
        }
        for py_key in &other_vec {
            if !self_set.contains(py_key)? {
                result.push(py_key.clone_ref(py));
            }
        }
        let set = pyo3::types::PySet::new(py, result.iter())?;
        Ok(set.into_any().unbind())
    }
}

// ---------------------------------------------------------------------------
// EdgeView — returned by G.edges
// ---------------------------------------------------------------------------

/// br-r37-c1-2zudj: inlined `PyGraph::py_node_key` for the edge-major
/// materialization helper below (kept byte-identical to the method) so it can
/// be called while `edge_py_attrs` is mutably borrowed via field-splitting.
#[inline]
fn edgeview_py_node_key(
    py: Python<'_>,
    node_key_map: &std::collections::HashMap<String, PyObject>,
    lazy_int_node_stop: i64,
    canonical: &str,
) -> PyObject {
    if let Some(obj) = node_key_map.get(canonical) {
        return obj.clone_ref(py);
    }
    if let Ok(value) = canonical.parse::<i64>() {
        if (0..lazy_int_node_stop).contains(&value) {
            return crate::unwrap_infallible(value.into_pyobject(py))
                .into_any()
                .unbind();
        }
    }
    crate::unwrap_infallible(canonical.to_owned().into_pyobject(py))
        .into_any()
        .unbind()
}

/// br-r37-c1-2zudj: one-pass `data=True` edge materialization. The previous
/// code collected an owned `Vec<(String, String)>` of endpoints (two String
/// clones per edge) just to release the `inner` borrow before calling the
/// `&mut materialize_edge_py_attrs`. Field-split PyGraph instead so the
/// immutable `inner`/`node_key_map` borrow coexists with the `&mut
/// edge_py_attrs` borrow: iterate `edges_ordered_borrowed()` (nx EdgeView
/// order) once, reuse/materialize the LIVE per-edge attr-dict handle (so the
/// yielded dict `is G[u][v]`, matching nx + the prior behaviour), and build the
/// tuple. `node_filter`, when set, keeps only edges with an endpoint in the set
/// (the `G.edges(nbunch, data=True)` contract). Caller handles mark_edges_dirty.
fn edge_alldata_items(
    py: Python<'_>,
    g: &mut PyGraph,
    node_filter: Option<&std::collections::HashSet<String>>,
) -> PyResult<Vec<PyObject>> {
    let inner = &g.inner;
    let edge_py_attrs = &mut g.edge_py_attrs;
    let node_key_map = &g.node_key_map;
    let lazy_stop = g.lazy_int_node_stop;
    let mut items = Vec::with_capacity(inner.edge_count());
    for (left, right, _attrs) in inner.edges_ordered_borrowed() {
        if let Some(ns) = node_filter {
            if !(ns.contains(left) || ns.contains(right)) {
                continue;
            }
        }
        let py_u = edgeview_py_node_key(py, node_key_map, lazy_stop, left);
        let py_v = edgeview_py_node_key(py, node_key_map, lazy_stop, right);
        let dict = edge_py_attrs
            .entry(PyGraph::edge_key(left, right))
            .or_insert_with(|| PyDict::new(py).unbind())
            .clone_ref(py)
            .into_any();
        items.push(tuple_object(py, &[py_u, py_v, dict])?);
    }
    Ok(items)
}

/// A view of the graph's edges. Supports ``len``, ``in``, iteration, and ``[]``.
#[pyclass(module = "franken_networkx")]
pub struct EdgeView {
    graph: Py<PyGraph>,
    data: NodeViewData,
}

impl EdgeView {
    /// br-r37-c1-edgesetborrow: collect (u, v) tuples for the set-algebra
    /// operators, scoping the graph borrow to this call so it is released
    /// before the caller iterates the `other` operand (which may borrow_mut the
    /// same graph when it is a view over it).
    fn collect_edge_tuples(&self, py: Python<'_>) -> PyResult<Vec<PyObject>> {
        let g = self.graph.borrow(py);
        g.inner
            .edges_ordered_borrowed()
            .into_iter()
            .map(|(left, right, _)| {
                let py_u = g.py_node_key(py, left);
                let py_v = g.py_node_key(py, right);
                tuple_object(py, &[py_u, py_v])
            })
            .collect()
    }
}

#[pymethods]
impl EdgeView {
    fn __len__(&self, py: Python<'_>) -> usize {
        let g = self.graph.borrow(py);
        g.inner.edge_count()
    }

    fn __contains__(&self, py: Python<'_>, edge: &Bound<'_, PyAny>) -> PyResult<bool> {
        let tuple = edge
            .downcast::<PyTuple>()
            .map_err(|_| pyo3::exceptions::PyTypeError::new_err("edge must be a (u, v) tuple"))?;
        if tuple.len() < 2 {
            return Ok(false);
        }
        let u = node_key_to_string(py, &tuple.get_item(0)?)?;
        let v = node_key_to_string(py, &tuple.get_item(1)?)?;
        let g = self.graph.borrow(py);
        Ok(g.inner.has_edge(&u, &v))
    }

    fn __iter__(&self, py: Python<'_>) -> PyResult<Py<NodeViewIterator>> {
        let (items, node_count, nodes_seq) = match &self.data {
            NodeViewData::AllData => {
                // br-r37-c1-2zudj: one-pass field-split materialization (see
                // edge_alldata_items) — was a two-pass owned-String collection.
                let mut g = self.graph.borrow_mut(py);
                if g.inner.edge_count() > 0 {
                    g.mark_edges_dirty();
                }
                let node_count = g.inner.node_count();
                let nodes_seq = g.nodes_seq;
                let items = edge_alldata_items(py, &mut g, None)?;
                (items, node_count, nodes_seq)
            }
            _ => {
                let g = self.graph.borrow(py);
                // br-r37-c1-eqedg: use O(1) node_count() instead of allocating nodes_ordered() Vec
                let node_count = g.inner.node_count();
                let nodes_seq = g.nodes_seq;
                // br-r37-c1-eqedg: use edges_ordered_borrowed to avoid string cloning in Rust
                let items: Vec<PyObject> = g
                    .inner
                    .edges_ordered_borrowed()
                    .into_iter()
                    .map(|(left, right, _attrs)| {
                        let py_u = g.py_node_key(py, left);
                        let py_v = g.py_node_key(py, right);
                        // br-r37-c1-7gxek: the canonical edge_key + edge_py_attrs lookup
                        // are only needed by the data-bearing variants. Computing them
                        // eagerly cost 2 String clones + a hashmap probe per edge on the
                        // plain `G.edges()` (NoData) hot path where they are discarded;
                        // resolve them lazily inside the branches that use them.
                        match &self.data {
                            NodeViewData::NoData => tuple_object(py, &[py_u, py_v]),
                            NodeViewData::Attr(attr_name) => {
                                let attrs = g.edge_py_attrs.get(&PyGraph::edge_key(left, right));
                                let val = attrs
                                    .and_then(|d| {
                                        d.bind(py).get_item(attr_name.as_str()).ok().flatten()
                                    })
                                    .map_or_else(|| py.None(), |v| v.unbind());
                                tuple_object(py, &[py_u, py_v, val])
                            }
                            NodeViewData::AttrWithDefault(attr_name, def_val) => {
                                let attrs = g.edge_py_attrs.get(&PyGraph::edge_key(left, right));
                                let val = attrs
                                    .and_then(|d| {
                                        d.bind(py).get_item(attr_name.as_str()).ok().flatten()
                                    })
                                    .map_or_else(|| def_val.clone_ref(py), |v| v.unbind());
                                tuple_object(py, &[py_u, py_v, val])
                            }
                            NodeViewData::AllData => unreachable!(),
                        }
                    })
                    .collect::<PyResult<Vec<_>>>()?;
                (items, node_count, nodes_seq)
            }
        };
        Py::new(
            py,
            NodeViewIterator {
                inner: items.into_iter(),
                graph: Some(self.graph.clone_ref(py)),
                expected_count: Some(node_count),
                expected_seq: Some(nodes_seq),
            },
        )
    }

    fn __getitem__(&self, py: Python<'_>, edge: &Bound<'_, PyAny>) -> PyResult<Py<PyDict>> {
        let tuple = edge.downcast::<PyTuple>().map_err(|_| {
            pyo3::exceptions::PyTypeError::new_err("edge key must be a (u, v) tuple")
        })?;
        let u = node_key_to_string(py, &tuple.get_item(0)?)?;
        let v = node_key_to_string(py, &tuple.get_item(1)?)?;
        let mut g = self.graph.borrow_mut(py);
        if !g.inner.has_edge(&u, &v) {
            return Err(PyKeyError::new_err(format!("({}, {})", u, v)));
        }
        g.mark_edges_dirty();
        Ok(g.materialize_edge_py_attrs(py, &u, &v))
    }

    fn __repr__(&self, py: Python<'_>) -> String {
        let g = self.graph.borrow(py);
        let count = g.inner.edge_count();
        format!("EdgeView({} edges)", count)
    }

    fn __bool__(&self, py: Python<'_>) -> bool {
        let g = self.graph.borrow(py);
        g.inner.edge_count() > 0
    }

    /// Return an EdgeView with data, callable as G.edges(data=True).
    #[pyo3(signature = (data=None, nbunch=None, default=None))]
    fn __call__(
        &self,
        py: Python<'_>,
        data: Option<&Bound<'_, PyAny>>,
        nbunch: Option<&Bound<'_, PyAny>>,
        default: Option<&Bound<'_, PyAny>>,
    ) -> PyResult<PyObject> {
        // If nbunch is provided, filter edges
        if let Some(nb) = nbunch {
            let iter = PyIterator::from_object(nb)?;
            let mut node_set: std::collections::HashSet<String> = std::collections::HashSet::new();
            for item in iter {
                let item = item?;
                node_set.insert(node_key_to_string(py, &item)?);
            }
            let mut view_data = parse_data_param(data)?;
            if let (Some(def), NodeViewData::Attr(attr)) = (default, &view_data) {
                view_data = NodeViewData::AttrWithDefault(attr.clone(), def.clone().unbind());
            }
            let items: Vec<PyObject> = if matches!(&view_data, NodeViewData::AllData) {
                // br-r37-c1-2zudj: one-pass field-split materialization with the
                // nbunch node filter (see edge_alldata_items).
                let mut g = self.graph.borrow_mut(py);
                if g.inner.edge_count() > 0 {
                    g.mark_edges_dirty();
                }
                edge_alldata_items(py, &mut g, Some(&node_set))?
            } else {
                let g = self.graph.borrow(py);
                // br-r37-c1-eqedg: use edges_ordered_borrowed to avoid string cloning
                g.inner
                    .edges_ordered_borrowed()
                    .into_iter()
                    .filter(|(left, right, _)| {
                        node_set.contains(*left) || node_set.contains(*right)
                    })
                    .map(|(left, right, _attrs)| {
                        let py_u = g.py_node_key(py, left);
                        let py_v = g.py_node_key(py, right);
                        let attrs = g.edge_py_attrs.get(&PyGraph::edge_key(left, right));
                        match &view_data {
                            NodeViewData::NoData => tuple_object(py, &[py_u, py_v]),
                            NodeViewData::Attr(attr_name) => {
                                let val = attrs
                                    .and_then(|d| {
                                        d.bind(py).get_item(attr_name.as_str()).ok().flatten()
                                    })
                                    .map_or_else(|| py.None(), |v| v.unbind());
                                tuple_object(py, &[py_u, py_v, val])
                            }
                            NodeViewData::AttrWithDefault(attr_name, def_val) => {
                                let val = attrs
                                    .and_then(|d| {
                                        d.bind(py).get_item(attr_name.as_str()).ok().flatten()
                                    })
                                    .map_or_else(|| def_val.clone_ref(py), |v| v.unbind());
                                tuple_object(py, &[py_u, py_v, val])
                            }
                            NodeViewData::AllData => unreachable!(),
                        }
                    })
                    .collect::<PyResult<Vec<_>>>()?
            };
            Ok(items.into_pyobject(py)?.into_any().unbind())
        } else {
            let mut view_data = parse_data_param(data)?;
            if let (Some(def), NodeViewData::Attr(attr)) = (default, &view_data) {
                view_data = NodeViewData::AttrWithDefault(attr.clone(), def.clone().unbind());
            }
            let view = Py::new(
                py,
                EdgeView {
                    graph: self.graph.clone_ref(py),
                    data: view_data,
                },
            )?;
            Ok(view.into_any())
        }
    }

    /// Union: self | other
    fn __or__(&self, py: Python<'_>, other: &Bound<'_, PyAny>) -> PyResult<PyObject> {
        // br-r37-c1-edgesetborrow: collect self's edges and DROP the graph
        // borrow before iterating `other`. When `other` is a view over the same
        // graph (e.g. a subgraph view), its iteration borrow_mut's the graph
        // (AtlasView.__getitem__), which panicked "Already borrowed" while this
        // method held an immutable borrow across the `other` iteration.
        let self_edges = self.collect_edge_tuples(py)?;
        let self_set = pyo3::types::PySet::new(py, self_edges.iter())?;
        for item in PyIterator::from_object(other)? {
            self_set.add(item?)?;
        }
        Ok(self_set.into_any().unbind())
    }

    /// Intersection: self & other
    fn __and__(&self, py: Python<'_>, other: &Bound<'_, PyAny>) -> PyResult<PyObject> {
        // br-r37-c1-edgesetborrow: drop the graph borrow before iterating `other`.
        let self_edges = self.collect_edge_tuples(py)?;
        let other_vec: Vec<PyObject> = PyIterator::from_object(other)?
            .map(|r| r.map(|o| o.unbind()))
            .collect::<PyResult<Vec<_>>>()?;
        let other_set = pyo3::types::PySet::new(py, other_vec.iter())?;
        let mut result = Vec::new();
        for py_edge in self_edges {
            if other_set.contains(&py_edge)? {
                result.push(py_edge);
            }
        }
        let set = pyo3::types::PySet::new(py, result.iter())?;
        Ok(set.into_any().unbind())
    }

    /// Difference: self - other
    fn __sub__(&self, py: Python<'_>, other: &Bound<'_, PyAny>) -> PyResult<PyObject> {
        // br-r37-c1-edgesetborrow: drop the graph borrow before iterating `other`.
        let self_edges = self.collect_edge_tuples(py)?;
        let other_vec: Vec<PyObject> = PyIterator::from_object(other)?
            .map(|r| r.map(|o| o.unbind()))
            .collect::<PyResult<Vec<_>>>()?;
        let other_set = pyo3::types::PySet::new(py, other_vec.iter())?;
        let mut result = Vec::new();
        for py_edge in self_edges {
            if !other_set.contains(&py_edge)? {
                result.push(py_edge);
            }
        }
        let set = pyo3::types::PySet::new(py, result.iter())?;
        Ok(set.into_any().unbind())
    }

    /// Symmetric difference: self ^ other
    fn __xor__(&self, py: Python<'_>, other: &Bound<'_, PyAny>) -> PyResult<PyObject> {
        // br-r37-c1-edgesetborrow: drop the graph borrow before iterating `other`.
        let self_edges = self.collect_edge_tuples(py)?;
        let self_set = pyo3::types::PySet::new(py, self_edges.iter())?;
        let other_vec: Vec<PyObject> = PyIterator::from_object(other)?
            .map(|r| r.map(|o| o.unbind()))
            .collect::<PyResult<Vec<_>>>()?;
        let other_set = pyo3::types::PySet::new(py, other_vec.iter())?;
        let mut result = Vec::new();
        for py_edge in &self_edges {
            if !other_set.contains(py_edge)? {
                result.push(py_edge.clone_ref(py));
            }
        }
        for py_edge in &other_vec {
            if !self_set.contains(py_edge)? {
                result.push(py_edge.clone_ref(py));
            }
        }
        let set = pyo3::types::PySet::new(py, result.iter())?;
        Ok(set.into_any().unbind())
    }
}

// ---------------------------------------------------------------------------
// DegreeView — returned by G.degree
// ---------------------------------------------------------------------------

/// A view of node degrees. Supports ``len``, ``in``, iteration, and ``[n]``.
#[pyclass(module = "franken_networkx")]
pub struct DegreeView {
    graph: Py<PyGraph>,
}

#[pymethods]
impl DegreeView {
    fn __len__(&self, py: Python<'_>) -> usize {
        let g = self.graph.borrow(py);
        g.inner.node_count()
    }

    fn __iter__(&self, py: Python<'_>) -> PyResult<Py<NodeViewIterator>> {
        let g = self.graph.borrow(py);
        let items: Vec<PyObject> = g
            .inner
            .nodes_ordered()
            .iter()
            .map(|n| {
                let py_key = g.py_node_key(py, n);
                let deg = g.inner.degree(n);
                let py_degree = deg.into_pyobject(py)?.into_any().unbind();
                tuple_object(py, &[py_key, py_degree])
            })
            .collect::<PyResult<Vec<_>>>()?;
        Py::new(
            py,
            NodeViewIterator {
                inner: items.into_iter(),
                graph: None,
                expected_count: None,
                expected_seq: None,
            },
        )
    }

    fn __getitem__(&self, py: Python<'_>, n: &Bound<'_, PyAny>) -> PyResult<usize> {
        let g = self.graph.borrow(py);
        let canonical = node_key_to_string(py, n)?;
        if !g.inner.has_node(&canonical) {
            return Err(crate::NodeNotFound::new_err(format!(
                "The node {} is not in the graph.",
                n.repr()?
            )));
        }
        Ok(g.inner.degree(&canonical))
    }

    fn __repr__(&self, py: Python<'_>) -> String {
        let g = self.graph.borrow(py);
        let items: Vec<String> = g
            .inner
            .nodes_ordered()
            .iter()
            .map(|n| format!("('{}', {})", n, g.inner.degree(n)))
            .collect();
        format!("DegreeView([{}])", items.join(", "))
    }

    fn __bool__(&self, py: Python<'_>) -> bool {
        let g = self.graph.borrow(py);
        g.inner.node_count() > 0
    }

    /// Make DegreeView callable like NetworkX: G.degree() returns self,
    /// G.degree(node) returns int, G.degree([nodes]) returns filtered list.
    #[pyo3(signature = (nbunch=None, weight=None))]
    fn __call__(
        slf: Py<Self>,
        py: Python<'_>,
        nbunch: Option<&Bound<'_, PyAny>>,
        weight: Option<&Bound<'_, PyAny>>,
    ) -> PyResult<PyObject> {
        // weight parameter is accepted for API compat but ignored (unweighted view)
        let _ = weight;

        let Some(nb) = nbunch else {
            // No args: return self
            return Ok(slf.into_any());
        };

        let view = slf.borrow(py);
        let g = view.graph.borrow(py);

        // Try as single node first
        if let Ok(canonical) = node_key_to_string(py, nb)
            && g.inner.has_node(&canonical)
        {
            let deg = g.inner.degree(&canonical);
            return Ok(deg.into_pyobject(py)?.into_any().unbind());
        }

        // Try as iterable of nodes
        if let Ok(iter) = PyIterator::from_object(nb) {
            let mut items: Vec<PyObject> = Vec::new();
            for item in iter {
                let item = item?;
                let canonical = node_key_to_string(py, &item)?;
                if !g.inner.has_node(&canonical) {
                    return Err(crate::NodeNotFound::new_err(format!(
                        "The node {} is not in the graph.",
                        item.repr()?
                    )));
                }
                let deg = g.inner.degree(&canonical);
                let py_key = g.py_node_key(py, &canonical);
                let py_degree = deg.into_pyobject(py)?.into_any().unbind();
                items.push(tuple_object(py, &[py_key, py_degree])?);
            }
            return Ok(items.into_pyobject(py)?.into_any().unbind());
        }

        // Neither a node nor iterable - error
        Err(crate::NodeNotFound::new_err(format!(
            "The node {} is not in the graph.",
            nb.repr()?
        )))
    }
}

// ---------------------------------------------------------------------------
// AdjacencyView — returned by G.adj
// ---------------------------------------------------------------------------

/// A view of the graph's adjacency structure. ``G.adj[n]`` returns a dict of neighbors.
#[pyclass(module = "franken_networkx")]
pub struct AdjacencyView {
    graph: Py<PyGraph>,
}

#[pymethods]
impl AdjacencyView {
    fn __len__(&self, py: Python<'_>) -> usize {
        let g = self.graph.borrow(py);
        g.inner.node_count()
    }

    fn __contains__(&self, py: Python<'_>, n: &Bound<'_, PyAny>) -> PyResult<bool> {
        let g = self.graph.borrow(py);
        let canonical = node_key_to_string(py, n)?;
        Ok(g.inner.has_node(&canonical))
    }

    fn __getitem__(&self, py: Python<'_>, n: &Bound<'_, PyAny>) -> PyResult<Py<AtlasView>> {
        // br-r37-c1-njs5g: `G.adj[u]` returns the same lazy AtlasView as `G[u]`
        // (was an eager O(degree) PyDict materialisation).
        let canonical = node_key_to_string(py, n)?;
        if !self.graph.borrow(py).inner.has_node(&canonical) {
            return Err(crate::missing_key_error(n));
        }
        Py::new(py, AtlasView::new(self.graph.clone_ref(py), canonical))
    }

    fn __iter__(&self, py: Python<'_>) -> PyResult<Py<NodeIterator>> {
        let g = self.graph.borrow(py);
        let nodes: Vec<PyObject> = g
            .inner
            .nodes_ordered()
            .iter()
            .map(|n| g.py_node_key(py, n))
            .collect();
        Py::new(py, NodeIterator::unguarded(nodes))
    }

    fn __repr__(&self, py: Python<'_>) -> String {
        let g = self.graph.borrow(py);
        format!("AdjacencyView({} nodes)", g.inner.node_count())
    }

    fn __bool__(&self, py: Python<'_>) -> bool {
        let g = self.graph.borrow(py);
        g.inner.node_count() > 0
    }
}

// ---------------------------------------------------------------------------
// AtlasView — lazy view of ONE node's adjacency ({neighbor: edge_attr_dict}),
// returned by `G[u]` / `G.adj[u]` for an undirected simple Graph. Mirrors
// `networkx.classes.coreviews.AtlasView` (a read-only Mapping). The previous
// `G[u]` EAGERLY materialised the whole neighbour dict (O(degree)); this view
// makes `G[u][v]` and `v in G[u]` O(1) and is LIVE (reflects later edge
// additions) like nx, fixing the prior snapshot divergence. (br-r37-c1-njs5g)
// ---------------------------------------------------------------------------
#[pyclass(module = "franken_networkx", mapping)]
pub struct AtlasView {
    graph: Py<PyGraph>,
    node: String,
}

impl AtlasView {
    pub(crate) fn new(graph: Py<PyGraph>, node: String) -> Self {
        Self { graph, node }
    }

    /// Materialise the full `{neighbour: shared_edge_attr_dict}` (O(degree)) —
    /// only when a materialising method (items/values/==/str/repr) is called.
    fn materialize(&self, py: Python<'_>) -> PyResult<Py<PyDict>> {
        let mut g = self.graph.borrow_mut(py);
        let result = PyDict::new(py);
        let neighbors: Vec<String> = g
            .inner
            .neighbors(&self.node)
            .unwrap_or_default()
            .into_iter()
            .map(str::to_owned)
            .collect();
        for nb in neighbors {
            let py_nb = g.py_node_key(py, &nb);
            let edge_attrs = g.materialize_edge_py_attrs(py, &self.node, &nb);
            result.set_item(py_nb, edge_attrs.bind(py))?;
        }
        Ok(result.unbind())
    }
}

#[pymethods]
impl AtlasView {
    fn __getitem__(&self, py: Python<'_>, v: &Bound<'_, PyAny>) -> PyResult<Py<PyDict>> {
        let mut g = self.graph.borrow_mut(py);
        let v_canon = node_key_to_string(py, v)?;
        if !g.inner.has_edge(&self.node, &v_canon) {
            return Err(PyKeyError::new_err((v.clone().unbind(),)));
        }
        // The returned dict is the SAME shared Py<PyDict> the graph stores, so
        // `G[u][v]['w'] = x` mutates the live edge attrs — flag the edge store
        // dirty so a later native read reconciles it (matches the old eager
        // `G[u]`, which marked dirty unconditionally).
        g.mark_edges_dirty();
        Ok(g.materialize_edge_py_attrs(py, &self.node, &v_canon))
    }

    fn __contains__(&self, py: Python<'_>, v: &Bound<'_, PyAny>) -> PyResult<bool> {
        let g = self.graph.borrow(py);
        let v_canon = node_key_to_string(py, v)?;
        Ok(g.inner.has_edge(&self.node, &v_canon))
    }

    fn __len__(&self, py: Python<'_>) -> usize {
        let g = self.graph.borrow(py);
        g.inner.neighbor_count(&self.node)
    }

    fn __iter__(&self, py: Python<'_>) -> PyResult<Py<NodeIterator>> {
        let g = self.graph.borrow(py);
        let nbrs: Vec<PyObject> = g
            .inner
            .neighbors(&self.node)
            .unwrap_or_default()
            .iter()
            .map(|nb| g.py_node_key(py, nb))
            .collect();
        Py::new(py, NodeIterator::unguarded(nbrs))
    }

    fn keys(&self, py: Python<'_>) -> PyResult<Py<NodeIterator>> {
        self.__iter__(py)
    }

    fn items(&self, py: Python<'_>) -> PyResult<Vec<(PyObject, Py<PyDict>)>> {
        let mut g = self.graph.borrow_mut(py);
        let mut out = Vec::with_capacity(g.inner.neighbor_count(&self.node));
        let neighbors: Vec<String> = g
            .inner
            .neighbors(&self.node)
            .unwrap_or_default()
            .into_iter()
            .map(str::to_owned)
            .collect();
        for nb in neighbors {
            let py_nb = g.py_node_key(py, &nb);
            let ed = g.materialize_edge_py_attrs(py, &self.node, &nb);
            out.push((py_nb, ed));
        }
        Ok(out)
    }

    fn values(&self, py: Python<'_>) -> PyResult<Vec<Py<PyDict>>> {
        let mut g = self.graph.borrow_mut(py);
        let mut out = Vec::with_capacity(g.inner.neighbor_count(&self.node));
        let neighbors: Vec<String> = g
            .inner
            .neighbors(&self.node)
            .unwrap_or_default()
            .into_iter()
            .map(str::to_owned)
            .collect();
        for nb in neighbors {
            let ed = g.materialize_edge_py_attrs(py, &self.node, &nb);
            out.push(ed);
        }
        Ok(out)
    }

    #[pyo3(signature = (v, default=None))]
    fn get(
        &self,
        py: Python<'_>,
        v: &Bound<'_, PyAny>,
        default: Option<PyObject>,
    ) -> PyResult<PyObject> {
        match self.__getitem__(py, v) {
            Ok(d) => Ok(d.into_any()),
            Err(e) if e.is_instance_of::<PyKeyError>(py) => {
                Ok(default.unwrap_or_else(|| py.None()))
            }
            Err(e) => Err(e),
        }
    }

    /// nx ``AtlasView.copy`` -> ``{n: self[n].copy()}`` (a plain dict of
    /// independent edge-attr-dict copies).
    fn copy(&self, py: Python<'_>) -> PyResult<Py<PyDict>> {
        let g = self.graph.borrow(py);
        let result = PyDict::new(py);
        if let Some(neighbors) = g.inner.neighbors(&self.node) {
            for nb in neighbors {
                let py_nb = g.py_node_key(py, nb);
                let ek = PyGraph::edge_key(&self.node, nb);
                let copied = match g.edge_py_attrs.get(&ek) {
                    Some(d) => d.bind(py).copy()?.unbind(),
                    None => PyDict::new(py).unbind(),
                };
                result.set_item(py_nb, copied)?;
            }
        }
        Ok(result.unbind())
    }

    fn __eq__(&self, py: Python<'_>, other: &Bound<'_, PyAny>) -> PyResult<bool> {
        let m = self.materialize(py)?;
        m.bind(py).eq(other)
    }

    fn __ne__(&self, py: Python<'_>, other: &Bound<'_, PyAny>) -> PyResult<bool> {
        Ok(!self.__eq__(py, other)?)
    }

    fn __str__(&self, py: Python<'_>) -> PyResult<String> {
        let m = self.materialize(py)?;
        Ok(m.bind(py).str()?.to_string())
    }

    fn __repr__(&self, py: Python<'_>) -> PyResult<String> {
        let m = self.materialize(py)?;
        Ok(format!("AtlasView({})", m.bind(py).repr()?.to_str()?))
    }

    fn __bool__(&self, py: Python<'_>) -> bool {
        self.__len__(py) > 0
    }
}

// ---------------------------------------------------------------------------
// Shared iterator (reused for all view iterations)
// ---------------------------------------------------------------------------

#[pyclass]
pub struct NodeViewIterator {
    inner: std::vec::IntoIter<PyObject>,
    graph: Option<Py<PyGraph>>,
    // br-gauntlet-perf-nodeviewiter: O(1) mutation guard. The old design stored
    // the full expected node list and rebuilt+compared it on EVERY __next__
    // (O(N) per next → O(N^2) total), which made list(G.nodes()) ~900x slower
    // than list(G) at n=20000. We now snapshot the node count + nodes_seq and
    // do an O(1) comparison per next, mirroring NodeIterator (br-r37-c1-39d82).
    expected_count: Option<usize>,
    expected_seq: Option<u64>,
}

#[pymethods]
impl NodeViewIterator {
    fn __iter__(slf: PyRef<'_, Self>) -> PyRef<'_, Self> {
        slf
    }
    fn __next__(mut slf: PyRefMut<'_, Self>) -> PyResult<Option<PyObject>> {
        let Some(item) = slf.inner.next() else {
            return Ok(None);
        };
        if let (Some(graph), Some(expected_count), Some(expected_seq)) =
            (&slf.graph, slf.expected_count, slf.expected_seq)
        {
            // br-gauntlet-perf-nodeviewiter: O(1) mutation-counter check (was an
            // O(N) nodes_ordered() rebuild + full element compare on EVERY next,
            // i.e. O(N^2) to iterate, ~900x slower than list(G) at n=20000). Any
            // add_node / remove_node bumps nodes_seq; only when it changes do we
            // disambiguate size-change vs key-permutation via node_count, so the
            // exact Python-dict error wording (size vs keys) is preserved.
            let py = slf.py();
            let g = graph.borrow(py);
            if g.nodes_seq != expected_seq {
                if g.inner.node_count() != expected_count {
                    return Err(PyRuntimeError::new_err(
                        "dictionary changed size during iteration",
                    ));
                }
                return Err(PyRuntimeError::new_err(
                    "dictionary keys changed during iteration",
                ));
            }
        }
        Ok(Some(item))
    }
}

// ---------------------------------------------------------------------------
// Helper
// ---------------------------------------------------------------------------

fn parse_data_param(data: Option<&Bound<'_, PyAny>>) -> PyResult<NodeViewData> {
    match data {
        None => Ok(NodeViewData::NoData),
        Some(d) => {
            if let Ok(b) = d.extract::<bool>() {
                if b {
                    Ok(NodeViewData::AllData)
                } else {
                    Ok(NodeViewData::NoData)
                }
            } else if let Ok(attr) = d.extract::<String>() {
                Ok(NodeViewData::Attr(attr))
            } else {
                Err(pyo3::exceptions::PyTypeError::new_err(
                    "data must be True, False, or a string attribute name",
                ))
            }
        }
    }
}

fn tuple_object(py: Python<'_>, elements: &[PyObject]) -> PyResult<PyObject> {
    Ok(PyTuple::new(py, elements)?.into_any().unbind())
}

// ---------------------------------------------------------------------------
// Constructor helpers — called from PyGraph properties
// ---------------------------------------------------------------------------

pub fn new_node_view(py: Python<'_>, graph: Py<PyGraph>) -> PyResult<Py<NodeView>> {
    Py::new(
        py,
        NodeView {
            graph,
            data: NodeViewData::NoData,
        },
    )
}

pub fn new_edge_view(py: Python<'_>, graph: Py<PyGraph>) -> PyResult<Py<EdgeView>> {
    Py::new(
        py,
        EdgeView {
            graph,
            data: NodeViewData::NoData,
        },
    )
}

pub fn new_degree_view(py: Python<'_>, graph: Py<PyGraph>) -> PyResult<Py<DegreeView>> {
    Py::new(py, DegreeView { graph })
}

pub fn new_adjacency_view(py: Python<'_>, graph: Py<PyGraph>) -> PyResult<Py<AdjacencyView>> {
    Py::new(py, AdjacencyView { graph })
}
