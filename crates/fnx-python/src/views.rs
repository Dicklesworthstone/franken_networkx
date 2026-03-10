//! NetworkX-compatible view objects (NodeView, EdgeView, DegreeView).
//!
//! These views provide dict-like read access to graph data and reflect
//! the current state of the graph (they are "live" views backed by Py<PyGraph>).

use crate::{NodeIterator, PyGraph, node_key_to_string};
use pyo3::exceptions::PyKeyError;
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

#[derive(Clone)]
enum NodeViewData {
    NoData,
    AllData,
    Attr(String),
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
        let g = self.graph.borrow(py);
        let nodes = g.inner.nodes_ordered();
        let items: Vec<PyObject> = match &self.data {
            NodeViewData::NoData => nodes.iter().map(|n| g.py_node_key(py, n)).collect(),
            NodeViewData::AllData => nodes
                .iter()
                .map(|n| {
                    let py_key = g.py_node_key(py, n);
                    let attrs = g
                        .node_py_attrs
                        .get(*n)
                        .map_or_else(|| PyDict::new(py).unbind(), |d| d.clone_ref(py));
                    tuple_object(py, &[py_key, attrs.into_any()])
                })
                .collect::<PyResult<Vec<_>>>()?,
            NodeViewData::Attr(attr) => nodes
                .iter()
                .map(|n| {
                    let py_key = g.py_node_key(py, n);
                    let val = g
                        .node_py_attrs
                        .get(*n)
                        .and_then(|dict| dict.bind(py).get_item(attr.as_str()).ok().flatten())
                        .map_or_else(|| py.None(), |v| v.unbind());
                    tuple_object(py, &[py_key, val])
                })
                .collect::<PyResult<Vec<_>>>()?,
        };
        Py::new(
            py,
            NodeViewIterator {
                inner: items.into_iter(),
            },
        )
    }

    fn __getitem__(&self, py: Python<'_>, n: &Bound<'_, PyAny>) -> PyResult<Py<PyDict>> {
        let g = self.graph.borrow(py);
        let canonical = node_key_to_string(py, n)?;
        if !g.inner.has_node(&canonical) {
            return Err(PyKeyError::new_err(format!("{}", n.repr()?)));
        }
        Ok(g.node_py_attrs
            .get(&canonical)
            .map_or_else(|| PyDict::new(py).unbind(), |d| d.clone_ref(py)))
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
        let _ = default; // reserved for future use
        let view_data = parse_data_param(data)?;
        Py::new(
            py,
            NodeView {
                graph: self.graph.clone_ref(py),
                data: view_data,
            },
        )
    }
}

// ---------------------------------------------------------------------------
// EdgeView — returned by G.edges
// ---------------------------------------------------------------------------

/// A view of the graph's edges. Supports ``len``, ``in``, iteration, and ``[]``.
#[pyclass(module = "franken_networkx")]
pub struct EdgeView {
    graph: Py<PyGraph>,
    data: NodeViewData,
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
        let g = self.graph.borrow(py);
        let items: Vec<PyObject> = g
            .edge_py_attrs
            .iter()
            .map(|((u, v), attrs)| {
                let py_u = g.py_node_key(py, u);
                let py_v = g.py_node_key(py, v);
                match &self.data {
                    NodeViewData::NoData => tuple_object(py, &[py_u, py_v]),
                    NodeViewData::AllData => {
                        let a: PyObject = attrs.clone_ref(py).into_any();
                        tuple_object(py, &[py_u, py_v, a])
                    }
                    NodeViewData::Attr(attr_name) => {
                        let val = attrs
                            .bind(py)
                            .get_item(attr_name.as_str())
                            .ok()
                            .flatten()
                            .map_or_else(|| py.None(), |v| v.unbind());
                        tuple_object(py, &[py_u, py_v, val])
                    }
                }
            })
            .collect::<PyResult<Vec<_>>>()?;
        Py::new(
            py,
            NodeViewIterator {
                inner: items.into_iter(),
            },
        )
    }

    fn __getitem__(&self, py: Python<'_>, edge: &Bound<'_, PyAny>) -> PyResult<Py<PyDict>> {
        let tuple = edge.downcast::<PyTuple>().map_err(|_| {
            pyo3::exceptions::PyTypeError::new_err("edge key must be a (u, v) tuple")
        })?;
        let u = node_key_to_string(py, &tuple.get_item(0)?)?;
        let v = node_key_to_string(py, &tuple.get_item(1)?)?;
        let g = self.graph.borrow(py);
        let ek = PyGraph::edge_key(&u, &v);
        if !g.inner.has_edge(&u, &v) {
            return Err(PyKeyError::new_err(format!("({}, {})", u, v)));
        }
        Ok(g.edge_py_attrs
            .get(&ek)
            .map_or_else(|| PyDict::new(py).unbind(), |d| d.clone_ref(py)))
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
        let _ = default;
        // If nbunch is provided, filter edges
        if let Some(nb) = nbunch {
            let iter = PyIterator::from_object(nb)?;
            let g = self.graph.borrow(py);
            let mut node_set: std::collections::HashSet<String> = std::collections::HashSet::new();
            for item in iter {
                let item = item?;
                node_set.insert(node_key_to_string(py, &item)?);
            }
            let view_data = parse_data_param(data)?;
            let items: Vec<PyObject> = g
                .edge_py_attrs
                .iter()
                .filter(|((u, v), _)| node_set.contains(u) || node_set.contains(v))
                .map(|((u, v), attrs)| {
                    let py_u = g.py_node_key(py, u);
                    let py_v = g.py_node_key(py, v);
                    match &view_data {
                        NodeViewData::NoData => tuple_object(py, &[py_u, py_v]),
                        NodeViewData::AllData => {
                            let a: PyObject = attrs.clone_ref(py).into_any();
                            tuple_object(py, &[py_u, py_v, a])
                        }
                        NodeViewData::Attr(attr_name) => {
                            let val = attrs
                                .bind(py)
                                .get_item(attr_name.as_str())
                                .ok()
                                .flatten()
                                .map_or_else(|| py.None(), |v| v.unbind());
                            tuple_object(py, &[py_u, py_v, val])
                        }
                    }
                })
                .collect::<PyResult<Vec<_>>>()?;
            Ok(items.into_pyobject(py)?.into_any().unbind())
        } else {
            let view_data = parse_data_param(data)?;
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
                let deg = g.inner.neighbor_count(n);
                let py_degree = deg.into_pyobject(py)?.into_any().unbind();
                tuple_object(py, &[py_key, py_degree])
            })
            .collect::<PyResult<Vec<_>>>()?;
        Py::new(
            py,
            NodeViewIterator {
                inner: items.into_iter(),
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
        Ok(g.inner.neighbor_count(&canonical))
    }

    fn __repr__(&self, py: Python<'_>) -> String {
        let g = self.graph.borrow(py);
        let items: Vec<String> = g
            .inner
            .nodes_ordered()
            .iter()
            .map(|n| format!("('{}', {})", n, g.inner.neighbor_count(n)))
            .collect();
        format!("DegreeView([{}])", items.join(", "))
    }

    fn __bool__(&self, py: Python<'_>) -> bool {
        let g = self.graph.borrow(py);
        g.inner.node_count() > 0
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

    fn __getitem__(&self, py: Python<'_>, n: &Bound<'_, PyAny>) -> PyResult<Py<PyDict>> {
        let g = self.graph.borrow(py);
        let canonical = node_key_to_string(py, n)?;
        if !g.inner.has_node(&canonical) {
            return Err(PyKeyError::new_err(format!("{}", n.repr()?)));
        }
        let neighbors = g.inner.neighbors(&canonical).unwrap_or_default();
        let result = PyDict::new(py);
        for nb in neighbors {
            let py_nb = g.py_node_key(py, nb);
            let ek = PyGraph::edge_key(&canonical, nb);
            let edge_attrs = g
                .edge_py_attrs
                .get(&ek)
                .map_or_else(|| PyDict::new(py).unbind(), |d| d.clone_ref(py));
            result.set_item(py_nb, edge_attrs.bind(py))?;
        }
        Ok(result.unbind())
    }

    fn __iter__(&self, py: Python<'_>) -> PyResult<Py<NodeIterator>> {
        let g = self.graph.borrow(py);
        let nodes: Vec<PyObject> = g
            .inner
            .nodes_ordered()
            .iter()
            .map(|n| g.py_node_key(py, n))
            .collect();
        Py::new(
            py,
            NodeIterator {
                inner: nodes.into_iter(),
            },
        )
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
// Shared iterator (reused for all view iterations)
// ---------------------------------------------------------------------------

#[pyclass]
pub struct NodeViewIterator {
    inner: std::vec::IntoIter<PyObject>,
}

#[pymethods]
impl NodeViewIterator {
    fn __iter__(slf: PyRef<'_, Self>) -> PyRef<'_, Self> {
        slf
    }
    fn __next__(mut slf: PyRefMut<'_, Self>) -> Option<PyObject> {
        slf.inner.next()
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
