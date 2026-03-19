//! PyDiGraph — PyO3 wrapper for directed graph.
//!
//! This mirrors [`PyGraph`] but with directed edge semantics:
//! - `(u, v)` is distinct from `(v, u)`.
//! - `neighbors()` returns successors (matches NetworkX convention).
//! - Additional methods: `predecessors`, `successors`, `in_degree`, `out_degree`.

use crate::{NetworkXError, NodeNotFound, PyGraph, node_key_to_string, unwrap_infallible};
use fnx_classes::AttrMap;
use fnx_classes::digraph::{DiGraph, MultiDiGraph};
use pyo3::exceptions::{PyKeyError, PyTypeError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyIterator, PyTuple};
use std::collections::{HashMap, HashSet};

// ---------------------------------------------------------------------------
// PyDiGraph
// ---------------------------------------------------------------------------

/// A directed graph — a Rust-backed drop-in replacement for ``networkx.DiGraph``.
#[pyclass(module = "franken_networkx", name = "DiGraph", dict, weakref, subclass)]
pub struct PyDiGraph {
    pub(crate) inner: DiGraph,
    pub(crate) node_key_map: HashMap<String, PyObject>,
    pub(crate) node_py_attrs: HashMap<String, Py<PyDict>>,
    /// Per-edge Python attrs. Key is (source, target) — NOT canonicalized.
    pub(crate) edge_py_attrs: HashMap<(String, String), Py<PyDict>>,
    pub(crate) graph_attrs: Py<PyDict>,
}

#[pyclass(
    module = "franken_networkx",
    name = "MultiDiGraph",
    dict,
    weakref,
    subclass
)]
pub struct PyMultiDiGraph {
    pub(crate) inner: MultiDiGraph,
    pub(crate) node_key_map: HashMap<String, PyObject>,
    pub(crate) node_py_attrs: HashMap<String, Py<PyDict>>,
    pub(crate) edge_py_attrs: HashMap<(String, String, usize), Py<PyDict>>,
    pub(crate) graph_attrs: Py<PyDict>,
}

impl PyMultiDiGraph {
    fn edge_key(u: &str, v: &str, key: usize) -> (String, String, usize) {
        (u.to_owned(), v.to_owned(), key)
    }

    fn py_node_key(&self, py: Python<'_>, canonical: &str) -> PyObject {
        self.node_key_map.get(canonical).map_or_else(
            || {
                unwrap_infallible(canonical.to_owned().into_pyobject(py))
                    .into_any()
                    .unbind()
            },
            |obj| obj.clone_ref(py),
        )
    }

    fn successor_dict(&self, py: Python<'_>, source: &str, target: &str) -> PyResult<Py<PyDict>> {
        let result = PyDict::new(py);
        for key in self.inner.edge_keys(source, target).unwrap_or_default() {
            let ek = Self::edge_key(source, target, key);
            let attrs = self
                .edge_py_attrs
                .get(&ek)
                .map_or_else(|| PyDict::new(py).unbind(), |d| d.clone_ref(py));
            result.set_item(key, attrs.bind(py))?;
        }
        Ok(result.unbind())
    }
}

#[pymethods]
impl PyMultiDiGraph {
    #[new]
    #[pyo3(signature = (incoming_graph_data=None, **attr))]
    fn new(
        py: Python<'_>,
        incoming_graph_data: Option<&Bound<'_, PyAny>>,
        attr: Option<&Bound<'_, PyDict>>,
    ) -> PyResult<Self> {
        let graph_attrs = PyDict::new(py);
        if let Some(a) = attr {
            graph_attrs.update(a.as_mapping())?;
        }

        let mut g = Self {
            inner: MultiDiGraph::strict(),
            node_key_map: HashMap::new(),
            node_py_attrs: HashMap::new(),
            edge_py_attrs: HashMap::new(),
            graph_attrs: graph_attrs.unbind(),
        };

        if let Some(data) = incoming_graph_data {
            if let Ok(other) = data.extract::<PyRef<'_, PyMultiDiGraph>>() {
                for (canonical, py_key) in &other.node_key_map {
                    let rust_attrs = other
                        .node_py_attrs
                        .get(canonical)
                        .map(|attrs| crate::py_dict_to_attr_map(attrs.bind(py)))
                        .transpose()?
                        .unwrap_or_default();
                    g.inner.add_node_with_attrs(canonical.clone(), rust_attrs);
                    g.node_key_map
                        .insert(canonical.clone(), py_key.clone_ref(py));
                    if let Some(attrs) = other.node_py_attrs.get(canonical) {
                        g.node_py_attrs
                            .insert(canonical.clone(), attrs.bind(py).copy()?.unbind());
                    }
                }
                for ((u, v, key), attrs) in &other.edge_py_attrs {
                    let rust_attrs = crate::py_dict_to_attr_map(attrs.bind(py))?;
                    let _ =
                        g.inner
                            .add_edge_with_key_and_attrs(u.clone(), v.clone(), *key, rust_attrs);
                    g.edge_py_attrs.insert(
                        (u.clone(), v.clone(), *key),
                        attrs.bind(py).copy()?.unbind(),
                    );
                }
                g.graph_attrs = other.graph_attrs.bind(py).copy()?.unbind();
            } else if let Ok(other) = data.extract::<PyRef<'_, PyDiGraph>>() {
                for (canonical, py_key) in &other.node_key_map {
                    let rust_attrs = other
                        .node_py_attrs
                        .get(canonical)
                        .map(|attrs| crate::py_dict_to_attr_map(attrs.bind(py)))
                        .transpose()?
                        .unwrap_or_default();
                    g.inner.add_node_with_attrs(canonical.clone(), rust_attrs);
                    g.node_key_map
                        .insert(canonical.clone(), py_key.clone_ref(py));
                    if let Some(attrs) = other.node_py_attrs.get(canonical) {
                        g.node_py_attrs
                            .insert(canonical.clone(), attrs.bind(py).copy()?.unbind());
                    }
                }
                for ((u, v), attrs) in &other.edge_py_attrs {
                    let rust_attrs = crate::py_dict_to_attr_map(attrs.bind(py))?;
                    let _ =
                        g.inner
                            .add_edge_with_key_and_attrs(u.clone(), v.clone(), 0, rust_attrs);
                    g.edge_py_attrs
                        .insert((u.clone(), v.clone(), 0), attrs.bind(py).copy()?.unbind());
                }
                g.graph_attrs = other.graph_attrs.bind(py).copy()?.unbind();
            }
        }

        Ok(g)
    }

    #[getter]
    fn graph(&self, py: Python<'_>) -> Py<PyDict> {
        self.graph_attrs.clone_ref(py)
    }

    #[getter]
    fn name(&self, py: Python<'_>) -> PyResult<String> {
        let gd = self.graph_attrs.bind(py);
        match gd.get_item("name")? {
            Some(v) => v.extract(),
            None => Ok(String::new()),
        }
    }

    #[setter]
    fn set_name(&self, py: Python<'_>, value: String) -> PyResult<()> {
        self.graph_attrs.bind(py).set_item("name", value)
    }

    fn is_directed(&self) -> bool {
        true
    }

    fn is_multigraph(&self) -> bool {
        true
    }

    fn number_of_nodes(&self) -> usize {
        self.inner.node_count()
    }

    fn order(&self) -> usize {
        self.inner.node_count()
    }

    #[pyo3(signature = (u=None, v=None))]
    fn number_of_edges(
        &self,
        py: Python<'_>,
        u: Option<&Bound<'_, PyAny>>,
        v: Option<&Bound<'_, PyAny>>,
    ) -> PyResult<usize> {
        match (u, v) {
            (Some(u_node), Some(v_node)) => {
                let u_c = node_key_to_string(py, u_node)?;
                let v_c = node_key_to_string(py, v_node)?;
                Ok(self
                    .inner
                    .edge_keys(&u_c, &v_c)
                    .map_or(0, |keys| keys.len()))
            }
            _ => Ok(self.inner.edge_count()),
        }
    }

    #[pyo3(signature = (weight=None))]
    fn size(&self, py: Python<'_>, weight: Option<&str>) -> PyResult<f64> {
        match weight {
            None => Ok(self.inner.edge_count() as f64),
            Some(attr) => {
                let mut total = 0.0_f64;
                for dict in self.edge_py_attrs.values() {
                    let bound = dict.bind(py);
                    match bound.get_item(attr)? {
                        Some(val) => total += val.extract::<f64>()?,
                        None => total += 1.0,
                    }
                }
                Ok(total)
            }
        }
    }

    #[pyo3(signature = (n, **attr))]
    fn add_node(
        &mut self,
        py: Python<'_>,
        n: &Bound<'_, PyAny>,
        attr: Option<&Bound<'_, PyDict>>,
    ) -> PyResult<()> {
        let canonical = node_key_to_string(py, n)?;
        self.node_key_map
            .insert(canonical.clone(), n.clone().unbind());
        let mut rust_attrs = AttrMap::new();
        let py_dict = self
            .node_py_attrs
            .entry(canonical.clone())
            .or_insert_with(|| PyDict::new(py).unbind());
        if let Some(a) = attr {
            for (k, v) in a.iter() {
                let key: String = k.extract()?;
                rust_attrs.insert(key.clone(), v.str()?.to_string());
                py_dict.bind(py).set_item(k, v)?;
            }
        }
        self.inner.add_node_with_attrs(canonical, rust_attrs);
        Ok(())
    }

    #[pyo3(signature = (nodes_for_adding, **attr))]
    fn add_nodes_from(
        &mut self,
        py: Python<'_>,
        nodes_for_adding: &Bound<'_, PyAny>,
        attr: Option<&Bound<'_, PyDict>>,
    ) -> PyResult<()> {
        let iter = PyIterator::from_object(nodes_for_adding)?;
        for item in iter {
            let item = item?;
            if let Ok(tuple) = item.downcast::<PyTuple>()
                && tuple.len() == 2
            {
                let node = tuple.get_item(0)?;
                let node_attrs = tuple.get_item(1)?;
                let merged = PyDict::new(py);
                if let Some(a) = attr {
                    merged.update(a.as_mapping())?;
                }
                if let Ok(d) = node_attrs.downcast::<PyDict>() {
                    merged.update(d.as_mapping())?;
                }
                self.add_node(py, &node, Some(&merged))?;
                continue;
            }
            self.add_node(py, &item, attr)?;
        }
        Ok(())
    }

    #[pyo3(signature = (u, v, key=None, **attr))]
    fn add_edge(
        &mut self,
        py: Python<'_>,
        u: &Bound<'_, PyAny>,
        v: &Bound<'_, PyAny>,
        key: Option<usize>,
        attr: Option<&Bound<'_, PyDict>>,
    ) -> PyResult<usize> {
        let u_canonical = node_key_to_string(py, u)?;
        let v_canonical = node_key_to_string(py, v)?;
        self.node_key_map
            .entry(u_canonical.clone())
            .or_insert_with(|| u.clone().unbind());
        self.node_key_map
            .entry(v_canonical.clone())
            .or_insert_with(|| v.clone().unbind());
        self.node_py_attrs
            .entry(u_canonical.clone())
            .or_insert_with(|| PyDict::new(py).unbind());
        self.node_py_attrs
            .entry(v_canonical.clone())
            .or_insert_with(|| PyDict::new(py).unbind());

        let mut rust_attrs = AttrMap::new();
        if let Some(a) = attr {
            for (k, val) in a.iter() {
                let attr_key: String = k.extract()?;
                rust_attrs.insert(attr_key, val.str()?.to_string());
            }
        }
        let actual_key = match key {
            Some(explicit_key) => self
                .inner
                .add_edge_with_key_and_attrs(
                    u_canonical.clone(),
                    v_canonical.clone(),
                    explicit_key,
                    rust_attrs,
                )
                .map_err(|e| NetworkXError::new_err(e.to_string()))?,
            None => self
                .inner
                .add_edge_with_attrs(u_canonical.clone(), v_canonical.clone(), rust_attrs)
                .map_err(|e| NetworkXError::new_err(e.to_string()))?,
        };

        let ek = Self::edge_key(&u_canonical, &v_canonical, actual_key);
        let py_dict = self
            .edge_py_attrs
            .entry(ek)
            .or_insert_with(|| PyDict::new(py).unbind());
        if let Some(a) = attr {
            for (k, val) in a.iter() {
                py_dict.bind(py).set_item(k, val)?;
            }
        }
        Ok(actual_key)
    }

    #[pyo3(signature = (ebunch_to_add, **attr))]
    fn add_edges_from(
        &mut self,
        py: Python<'_>,
        ebunch_to_add: &Bound<'_, PyAny>,
        attr: Option<&Bound<'_, PyDict>>,
    ) -> PyResult<()> {
        let iter = PyIterator::from_object(ebunch_to_add)?;
        for item in iter {
            let item = item?;
            let tuple = item.downcast::<PyTuple>().map_err(|_| {
                PyTypeError::new_err(
                    "each edge must be a tuple (u, v), (u, v, data), or (u, v, key, data)",
                )
            })?;
            let merged = PyDict::new(py);
            if let Some(a) = attr {
                merged.update(a.as_mapping())?;
            }
            match tuple.len() {
                2 => {
                    self.add_edge(
                        py,
                        &tuple.get_item(0)?,
                        &tuple.get_item(1)?,
                        None,
                        Some(&merged),
                    )?;
                }
                3 => {
                    let third = tuple.get_item(2)?;
                    if let Ok(d) = third.downcast::<PyDict>() {
                        merged.update(d.as_mapping())?;
                        self.add_edge(
                            py,
                            &tuple.get_item(0)?,
                            &tuple.get_item(1)?,
                            None,
                            Some(&merged),
                        )?;
                    } else {
                        let edge_key = third.extract::<usize>()?;
                        self.add_edge(
                            py,
                            &tuple.get_item(0)?,
                            &tuple.get_item(1)?,
                            Some(edge_key),
                            Some(&merged),
                        )?;
                    }
                }
                4 => {
                    let edge_key = tuple.get_item(2)?.extract::<usize>()?;
                    if let Ok(d) = tuple.get_item(3)?.downcast::<PyDict>() {
                        merged.update(d.as_mapping())?;
                    }
                    self.add_edge(
                        py,
                        &tuple.get_item(0)?,
                        &tuple.get_item(1)?,
                        Some(edge_key),
                        Some(&merged),
                    )?;
                }
                _ => {
                    return Err(PyValueError::new_err(
                        "edge tuple must have 2, 3, or 4 elements",
                    ));
                }
            }
        }
        Ok(())
    }

    #[pyo3(signature = (u, v, key=None))]
    fn remove_edge(
        &mut self,
        py: Python<'_>,
        u: &Bound<'_, PyAny>,
        v: &Bound<'_, PyAny>,
        key: Option<usize>,
    ) -> PyResult<()> {
        let u_canonical = node_key_to_string(py, u)?;
        let v_canonical = node_key_to_string(py, v)?;
        let auto_removal_key = key.or_else(|| {
            self.inner
                .edge_keys(&u_canonical, &v_canonical)
                .and_then(|keys| keys.last().copied())
        });
        let removed = self
            .inner
            .remove_edge(&u_canonical, &v_canonical, auto_removal_key);
        if !removed {
            return Err(NetworkXError::new_err(format!(
                "The edge {}-{} is not in the graph",
                u.repr()?,
                v.repr()?
            )));
        }
        if let Some(explicit_key) = auto_removal_key {
            self.edge_py_attrs
                .remove(&Self::edge_key(&u_canonical, &v_canonical, explicit_key));
        }
        Ok(())
    }

    fn remove_node(&mut self, py: Python<'_>, n: &Bound<'_, PyAny>) -> PyResult<()> {
        let canonical = node_key_to_string(py, n)?;
        if !self.inner.has_node(&canonical) {
            return Err(NodeNotFound::new_err(format!(
                "The node {} is not in the graph.",
                n.repr()?
            )));
        }
        self.inner.remove_node(&canonical);
        self.node_key_map.remove(&canonical);
        self.node_py_attrs.remove(&canonical);
        let keys_to_remove: Vec<(String, String, usize)> = self
            .edge_py_attrs
            .keys()
            .filter(|(u, v, _)| u == &canonical || v == &canonical)
            .cloned()
            .collect();
        for k in keys_to_remove {
            self.edge_py_attrs.remove(&k);
        }
        Ok(())
    }

    fn remove_nodes_from(&mut self, py: Python<'_>, nodes: &Bound<'_, PyAny>) -> PyResult<()> {
        let iter = PyIterator::from_object(nodes)?;
        for item in iter {
            let item = item?;
            let canonical = node_key_to_string(py, &item)?;
            if self.inner.has_node(&canonical) {
                self.inner.remove_node(&canonical);
                self.node_key_map.remove(&canonical);
                self.node_py_attrs.remove(&canonical);
                let keys_to_remove: Vec<(String, String, usize)> = self
                    .edge_py_attrs
                    .keys()
                    .filter(|(u, v, _)| u == &canonical || v == &canonical)
                    .cloned()
                    .collect();
                for k in keys_to_remove {
                    self.edge_py_attrs.remove(&k);
                }
            }
        }
        Ok(())
    }

    #[pyo3(signature = (u, v, key=None))]
    fn has_edge(
        &self,
        py: Python<'_>,
        u: &Bound<'_, PyAny>,
        v: &Bound<'_, PyAny>,
        key: Option<usize>,
    ) -> PyResult<bool> {
        let u_c = node_key_to_string(py, u)?;
        let v_c = node_key_to_string(py, v)?;
        Ok(match key {
            Some(edge_key) => self.inner.edge_attrs(&u_c, &v_c, edge_key).is_some(),
            None => self.inner.has_edge(&u_c, &v_c),
        })
    }

    fn successors(&self, py: Python<'_>, n: &Bound<'_, PyAny>) -> PyResult<Vec<PyObject>> {
        let canonical = node_key_to_string(py, n)?;
        match self.inner.successors(&canonical) {
            Some(succs) => Ok(succs.into_iter().map(|s| self.py_node_key(py, s)).collect()),
            None => Err(NodeNotFound::new_err(format!(
                "The node {} is not in the graph.",
                n.repr()?
            ))),
        }
    }

    #[pyo3(name = "predecessors")]
    fn predecessors_method(&self, py: Python<'_>, n: &Bound<'_, PyAny>) -> PyResult<Vec<PyObject>> {
        let canonical = node_key_to_string(py, n)?;
        match self.inner.predecessors(&canonical) {
            Some(preds) => Ok(preds.into_iter().map(|p| self.py_node_key(py, p)).collect()),
            None => Err(NodeNotFound::new_err(format!(
                "The node {} is not in the graph.",
                n.repr()?
            ))),
        }
    }

    fn neighbors(&self, py: Python<'_>, n: &Bound<'_, PyAny>) -> PyResult<Vec<PyObject>> {
        self.successors(py, n)
    }

    fn clear(&mut self, py: Python<'_>) -> PyResult<()> {
        self.inner = MultiDiGraph::strict();
        self.node_key_map.clear();
        self.node_py_attrs.clear();
        self.edge_py_attrs.clear();
        self.graph_attrs = PyDict::new(py).unbind();
        Ok(())
    }

    fn clear_edges(&mut self) {
        self.inner = MultiDiGraph::strict();
        Python::with_gil(|py| {
            for canonical in self.node_key_map.keys() {
                let rust_attrs = self
                    .node_py_attrs
                    .get(canonical)
                    .map(|attrs| crate::py_dict_to_attr_map(attrs.bind(py)))
                    .transpose()
                    .ok()
                    .flatten()
                    .unwrap_or_default();
                self.inner
                    .add_node_with_attrs(canonical.clone(), rust_attrs);
            }
        });
        self.edge_py_attrs.clear();
    }

    fn has_node(&self, py: Python<'_>, n: &Bound<'_, PyAny>) -> PyResult<bool> {
        let canonical = node_key_to_string(py, n)?;
        Ok(self.inner.has_node(&canonical))
    }

    fn __len__(&self) -> usize {
        self.inner.node_count()
    }

    fn __contains__(&self, py: Python<'_>, n: &Bound<'_, PyAny>) -> PyResult<bool> {
        let canonical = node_key_to_string(py, n)?;
        Ok(self.inner.has_node(&canonical))
    }

    fn __iter__(&self, py: Python<'_>) -> PyResult<Py<crate::NodeIterator>> {
        let nodes: Vec<PyObject> = self
            .inner
            .nodes_ordered()
            .into_iter()
            .map(|n| self.py_node_key(py, n))
            .collect();
        Py::new(
            py,
            crate::NodeIterator {
                inner: nodes.into_iter(),
            },
        )
    }

    fn __getitem__(&self, py: Python<'_>, n: &Bound<'_, PyAny>) -> PyResult<Py<PyDict>> {
        let canonical = node_key_to_string(py, n)?;
        if !self.inner.has_node(&canonical) {
            return Err(PyKeyError::new_err(format!("{}", n.repr()?)));
        }
        let result = PyDict::new(py);
        for successor in self.inner.successors(&canonical).unwrap_or_default() {
            result.set_item(
                self.py_node_key(py, successor),
                self.successor_dict(py, &canonical, successor)?.bind(py),
            )?;
        }
        Ok(result.unbind())
    }

    fn __str__(&self) -> String {
        format!(
            "MultiDiGraph with {} nodes and {} edges",
            self.inner.node_count(),
            self.inner.edge_count()
        )
    }

    fn __repr__(&self, py: Python<'_>) -> PyResult<String> {
        let name = self.name(py)?;
        if name.is_empty() {
            Ok(format!(
                "MultiDiGraph(nodes={}, edges={})",
                self.inner.node_count(),
                self.inner.edge_count()
            ))
        } else {
            Ok(format!(
                "MultiDiGraph(name='{}', nodes={}, edges={})",
                name,
                self.inner.node_count(),
                self.inner.edge_count()
            ))
        }
    }

    fn __bool__(&self) -> bool {
        self.inner.node_count() > 0
    }

    // -----------------------------------------------------------------------
    // View-like property methods
    // -----------------------------------------------------------------------

    #[getter]
    fn nodes(slf: PyRef<'_, Self>) -> PyResult<Py<MultiDiGraphNodeView>> {
        let py = slf.py();
        let graph_py: Py<PyMultiDiGraph> = Py::from(slf);
        Py::new(py, MultiDiGraphNodeView { graph: graph_py })
    }

    #[getter]
    fn edges(slf: PyRef<'_, Self>) -> PyResult<Py<MultiDiGraphEdgeView>> {
        let py = slf.py();
        let graph_py: Py<PyMultiDiGraph> = Py::from(slf);
        Py::new(py, MultiDiGraphEdgeView { graph: graph_py })
    }

    #[getter]
    fn degree(slf: PyRef<'_, Self>) -> PyResult<Py<MultiDiGraphDegreeView>> {
        let py = slf.py();
        let graph_py: Py<PyMultiDiGraph> = Py::from(slf);
        Py::new(py, MultiDiGraphDegreeView { graph: graph_py, kind: DegreeKind::Total })
    }

    #[getter]
    fn in_degree(slf: PyRef<'_, Self>) -> PyResult<Py<MultiDiGraphDegreeView>> {
        let py = slf.py();
        let graph_py: Py<PyMultiDiGraph> = Py::from(slf);
        Py::new(py, MultiDiGraphDegreeView { graph: graph_py, kind: DegreeKind::In })
    }

    #[getter]
    fn out_degree(slf: PyRef<'_, Self>) -> PyResult<Py<MultiDiGraphDegreeView>> {
        let py = slf.py();
        let graph_py: Py<PyMultiDiGraph> = Py::from(slf);
        Py::new(py, MultiDiGraphDegreeView { graph: graph_py, kind: DegreeKind::Out })
    }

    #[getter]
    fn adj(&self, py: Python<'_>) -> PyResult<Py<PyDict>> {
        self.adjacency(py)
    }

    fn adjacency(&self, py: Python<'_>) -> PyResult<Py<PyDict>> {
        let result = PyDict::new(py);
        for node in self.inner.nodes_ordered() {
            let py_node = self.py_node_key(py, node);
            let nbrs_dict = PyDict::new(py);
            for successor in self.inner.successors(node).unwrap_or_default() {
                let py_succ = self.py_node_key(py, successor);
                let edge_dict = PyDict::new(py);
                for key in self.inner.edge_keys(node, successor).unwrap_or_default() {
                    let ek = Self::edge_key(node, successor, key);
                    let attrs = self
                        .edge_py_attrs
                        .get(&ek)
                        .map_or_else(|| PyDict::new(py).unbind(), |d| d.clone_ref(py));
                    edge_dict.set_item(key, attrs.bind(py))?;
                }
                nbrs_dict.set_item(&py_succ, edge_dict)?;
            }
            result.set_item(py_node, nbrs_dict)?;
        }
        Ok(result.unbind())
    }

    #[getter]
    fn succ(&self, py: Python<'_>) -> PyResult<Py<PyDict>> {
        self.adjacency(py)
    }

    #[getter]
    fn pred(&self, py: Python<'_>) -> PyResult<Py<PyDict>> {
        let result = PyDict::new(py);
        for node in self.inner.nodes_ordered() {
            let py_node = self.py_node_key(py, node);
            let preds_dict = PyDict::new(py);
            for predecessor in self.inner.predecessors(node).unwrap_or_default() {
                let py_pred = self.py_node_key(py, predecessor);
                let edge_dict = PyDict::new(py);
                for key in self.inner.edge_keys(predecessor, node).unwrap_or_default() {
                    let ek = Self::edge_key(predecessor, node, key);
                    let attrs = self
                        .edge_py_attrs
                        .get(&ek)
                        .map_or_else(|| PyDict::new(py).unbind(), |d| d.clone_ref(py));
                    edge_dict.set_item(key, attrs.bind(py))?;
                }
                preds_dict.set_item(&py_pred, edge_dict)?;
            }
            result.set_item(py_node, preds_dict)?;
        }
        Ok(result.unbind())
    }

    // -----------------------------------------------------------------------
    // Copy / subgraph / conversion
    // -----------------------------------------------------------------------

    fn copy(&self, py: Python<'_>) -> PyResult<Self> {
        let mut new_graph = Self {
            inner: MultiDiGraph::strict(),
            node_key_map: HashMap::new(),
            node_py_attrs: HashMap::new(),
            edge_py_attrs: HashMap::new(),
            graph_attrs: self.graph_attrs.bind(py).copy()?.unbind(),
        };
        for (canonical, py_key) in &self.node_key_map {
            let rust_attrs = self
                .node_py_attrs
                .get(canonical)
                .map(|attrs| crate::py_dict_to_attr_map(attrs.bind(py)))
                .transpose()?
                .unwrap_or_default();
            new_graph.inner.add_node_with_attrs(canonical.clone(), rust_attrs);
            new_graph
                .node_key_map
                .insert(canonical.clone(), py_key.clone_ref(py));
            if let Some(attrs) = self.node_py_attrs.get(canonical) {
                new_graph
                    .node_py_attrs
                    .insert(canonical.clone(), attrs.bind(py).copy()?.unbind());
            }
        }
        for ((u, v, key), attrs) in &self.edge_py_attrs {
            let rust_attrs = crate::py_dict_to_attr_map(attrs.bind(py))?;
            let _ = new_graph.inner.add_edge_with_key_and_attrs(
                u.clone(), v.clone(), *key, rust_attrs,
            );
            new_graph
                .edge_py_attrs
                .insert((u.clone(), v.clone(), *key), attrs.bind(py).copy()?.unbind());
        }
        Ok(new_graph)
    }

    fn subgraph(&self, py: Python<'_>, nodes: &Bound<'_, PyAny>) -> PyResult<Self> {
        let iter = PyIterator::from_object(nodes)?;
        let mut keep: HashSet<String> = HashSet::new();
        for item in iter {
            let item = item?;
            let canonical = node_key_to_string(py, &item)?;
            if self.inner.has_node(&canonical) {
                keep.insert(canonical);
            }
        }

        let mut new_graph = Self {
            inner: MultiDiGraph::strict(),
            node_key_map: HashMap::new(),
            node_py_attrs: HashMap::new(),
            edge_py_attrs: HashMap::new(),
            graph_attrs: self.graph_attrs.bind(py).copy()?.unbind(),
        };

        for canonical in &keep {
            let rust_attrs = self
                .node_py_attrs
                .get(canonical)
                .map(|attrs| crate::py_dict_to_attr_map(attrs.bind(py)))
                .transpose()?
                .unwrap_or_default();
            new_graph.inner.add_node_with_attrs(canonical.clone(), rust_attrs);
            if let Some(py_key) = self.node_key_map.get(canonical) {
                new_graph
                    .node_key_map
                    .insert(canonical.clone(), py_key.clone_ref(py));
            }
            if let Some(attrs) = self.node_py_attrs.get(canonical) {
                new_graph
                    .node_py_attrs
                    .insert(canonical.clone(), attrs.bind(py).copy()?.unbind());
            }
        }

        for ((u, v, key), attrs) in &self.edge_py_attrs {
            if keep.contains(u) && keep.contains(v) {
                let rust_attrs = crate::py_dict_to_attr_map(attrs.bind(py))?;
                let _ = new_graph.inner.add_edge_with_key_and_attrs(
                    u.clone(), v.clone(), *key, rust_attrs,
                );
                new_graph
                    .edge_py_attrs
                    .insert((u.clone(), v.clone(), *key), attrs.bind(py).copy()?.unbind());
            }
        }

        Ok(new_graph)
    }

    fn edge_subgraph(&self, py: Python<'_>, edges: &Bound<'_, PyAny>) -> PyResult<Self> {
        let iter = PyIterator::from_object(edges)?;
        let mut involved_nodes: HashSet<String> = HashSet::new();
        let mut new_graph = Self {
            inner: MultiDiGraph::strict(),
            node_key_map: HashMap::new(),
            node_py_attrs: HashMap::new(),
            edge_py_attrs: HashMap::new(),
            graph_attrs: self.graph_attrs.bind(py).copy()?.unbind(),
        };

        for item in iter {
            let item = item?;
            let tuple = item
                .downcast::<PyTuple>()
                .map_err(|_| PyTypeError::new_err("each edge must be a tuple"))?;
            let u = node_key_to_string(py, &tuple.get_item(0)?)?;
            let v = node_key_to_string(py, &tuple.get_item(1)?)?;
            let key_filter: Option<usize> = if tuple.len() >= 3 {
                Some(tuple.get_item(2)?.extract::<usize>()?)
            } else {
                None
            };

            let keys = self.inner.edge_keys(&u, &v).unwrap_or_default();
            for k in keys {
                if key_filter.is_some() && key_filter != Some(k) {
                    continue;
                }
                involved_nodes.insert(u.clone());
                involved_nodes.insert(v.clone());
                let ek = Self::edge_key(&u, &v, k);
                if let Some(attrs) = self.edge_py_attrs.get(&ek) {
                    let rust_attrs = crate::py_dict_to_attr_map(attrs.bind(py))?;
                    let _ = new_graph.inner.add_edge_with_key_and_attrs(
                        u.clone(), v.clone(), k, rust_attrs,
                    );
                    new_graph
                        .edge_py_attrs
                        .insert(ek, attrs.bind(py).copy()?.unbind());
                } else {
                    let _ = new_graph.inner.add_edge_with_key_and_attrs(
                        u.clone(), v.clone(), k, AttrMap::new(),
                    );
                }
            }
        }

        for canonical in &involved_nodes {
            if let Some(py_key) = self.node_key_map.get(canonical) {
                new_graph
                    .node_key_map
                    .insert(canonical.clone(), py_key.clone_ref(py));
            }
            if let Some(attrs) = self.node_py_attrs.get(canonical) {
                new_graph
                    .node_py_attrs
                    .insert(canonical.clone(), attrs.bind(py).copy()?.unbind());
            }
        }

        Ok(new_graph)
    }

    fn to_directed(&self, py: Python<'_>) -> PyResult<Self> {
        self.copy(py)
    }

    fn to_undirected(&self) -> PyResult<()> {
        Err(crate::NetworkXNotImplemented::new_err(
            "to_undirected() is not yet supported for MultiDiGraph.",
        ))
    }

    fn reverse(&self, py: Python<'_>) -> PyResult<Self> {
        let mut new_graph = Self {
            inner: MultiDiGraph::strict(),
            node_key_map: HashMap::new(),
            node_py_attrs: HashMap::new(),
            edge_py_attrs: HashMap::new(),
            graph_attrs: self.graph_attrs.bind(py).copy()?.unbind(),
        };
        for (canonical, py_key) in &self.node_key_map {
            let rust_attrs = self
                .node_py_attrs
                .get(canonical)
                .map(|attrs| crate::py_dict_to_attr_map(attrs.bind(py)))
                .transpose()?
                .unwrap_or_default();
            new_graph.inner.add_node_with_attrs(canonical.clone(), rust_attrs);
            new_graph
                .node_key_map
                .insert(canonical.clone(), py_key.clone_ref(py));
            if let Some(attrs) = self.node_py_attrs.get(canonical) {
                new_graph
                    .node_py_attrs
                    .insert(canonical.clone(), attrs.bind(py).copy()?.unbind());
            }
        }
        // Reverse all edges
        for ((u, v, key), attrs) in &self.edge_py_attrs {
            let rust_attrs = crate::py_dict_to_attr_map(attrs.bind(py))?;
            let _ = new_graph.inner.add_edge_with_key_and_attrs(
                v.clone(), u.clone(), *key, rust_attrs,
            );
            new_graph
                .edge_py_attrs
                .insert((v.clone(), u.clone(), *key), attrs.bind(py).copy()?.unbind());
        }
        Ok(new_graph)
    }

    // -----------------------------------------------------------------------
    // Bulk mutation
    // -----------------------------------------------------------------------

    #[pyo3(signature = (ebunch_to_add, weight=None))]
    fn add_weighted_edges_from(
        &mut self,
        py: Python<'_>,
        ebunch_to_add: &Bound<'_, PyAny>,
        weight: Option<&str>,
    ) -> PyResult<()> {
        let weight_key = weight.unwrap_or("weight");
        let iter = PyIterator::from_object(ebunch_to_add)?;
        for item in iter {
            let item = item?;
            let tuple = item.downcast::<PyTuple>().map_err(|_| {
                PyTypeError::new_err("each edge must be a (u, v, w) tuple")
            })?;
            if tuple.len() < 3 {
                return Err(PyValueError::new_err(
                    "each edge must have at least 3 elements (u, v, weight)",
                ));
            }
            let u = &tuple.get_item(0)?;
            let v = &tuple.get_item(1)?;
            let w = &tuple.get_item(2)?;
            let d = PyDict::new(py);
            d.set_item(weight_key, w)?;
            self.add_edge(py, u, v, None, Some(&d))?;
        }
        Ok(())
    }

    fn remove_edges_from(&mut self, py: Python<'_>, ebunch: &Bound<'_, PyAny>) -> PyResult<()> {
        let iter = PyIterator::from_object(ebunch)?;
        for item in iter {
            let item = item?;
            let tuple = item
                .downcast::<PyTuple>()
                .map_err(|_| PyTypeError::new_err("each edge must be a tuple"))?;
            let u = &tuple.get_item(0)?;
            let v = &tuple.get_item(1)?;
            let key = if tuple.len() >= 3 {
                Some(tuple.get_item(2)?.extract::<usize>()?)
            } else {
                None
            };
            let u_c = node_key_to_string(py, u)?;
            let v_c = node_key_to_string(py, v)?;
            if self.inner.has_edge(&u_c, &v_c) {
                let _ = self.remove_edge(py, u, v, key);
            }
        }
        Ok(())
    }

    #[pyo3(signature = (edges=None, nodes=None))]
    fn update(
        &mut self,
        py: Python<'_>,
        edges: Option<&Bound<'_, PyAny>>,
        nodes: Option<&Bound<'_, PyAny>>,
    ) -> PyResult<()> {
        if let Some(e) = edges {
            self.add_edges_from(py, e, None)?;
        }
        if let Some(n) = nodes {
            self.add_nodes_from(py, n, None)?;
        }
        Ok(())
    }

    #[pyo3(signature = (u=None, v=None))]
    fn number_of_edges_between(
        &self,
        py: Python<'_>,
        u: Option<&Bound<'_, PyAny>>,
        v: Option<&Bound<'_, PyAny>>,
    ) -> PyResult<usize> {
        match (u, v) {
            (Some(u_node), Some(v_node)) => {
                let u_c = node_key_to_string(py, u_node)?;
                let v_c = node_key_to_string(py, v_node)?;
                Ok(self
                    .inner
                    .edge_keys(&u_c, &v_c)
                    .map_or(0, |keys| keys.len()))
            }
            _ => Ok(self.inner.edge_count()),
        }
    }

    /// Return edge attributes. If key is None, returns dict of key -> attrs.
    #[pyo3(signature = (u, v, key=None, default=None))]
    fn get_edge_data(
        &self,
        py: Python<'_>,
        u: &Bound<'_, PyAny>,
        v: &Bound<'_, PyAny>,
        key: Option<usize>,
        default: Option<PyObject>,
    ) -> PyResult<PyObject> {
        let u_c = node_key_to_string(py, u)?;
        let v_c = node_key_to_string(py, v)?;
        if let Some(k) = key {
            let ek = Self::edge_key(&u_c, &v_c, k);
            Ok(self.edge_py_attrs.get(&ek).map_or_else(
                || default.unwrap_or_else(|| py.None()),
                |d| d.clone_ref(py).into_any(),
            ))
        } else {
            let keys = self.inner.edge_keys(&u_c, &v_c).unwrap_or_default();
            if keys.is_empty() {
                Ok(default.unwrap_or_else(|| py.None()))
            } else {
                let result = PyDict::new(py);
                for k in keys {
                    let ek = Self::edge_key(&u_c, &v_c, k);
                    let attrs = self
                        .edge_py_attrs
                        .get(&ek)
                        .map_or_else(|| PyDict::new(py).unbind(), |d| d.clone_ref(py));
                    result.set_item(k, attrs.bind(py))?;
                }
                Ok(result.into_any().unbind())
            }
        }
    }
}

// ---------------------------------------------------------------------------
// MultiDiGraph view types
// ---------------------------------------------------------------------------

#[pyclass]
pub struct MultiDiGraphNodeView {
    graph: Py<PyMultiDiGraph>,
}

#[pymethods]
impl MultiDiGraphNodeView {
    fn __len__(&self, py: Python<'_>) -> usize {
        self.graph.borrow(py).inner.node_count()
    }

    fn __contains__(&self, py: Python<'_>, n: &Bound<'_, PyAny>) -> PyResult<bool> {
        let canonical = node_key_to_string(py, n)?;
        Ok(self.graph.borrow(py).inner.has_node(&canonical))
    }

    fn __iter__(&self, py: Python<'_>) -> PyResult<Py<crate::NodeIterator>> {
        let g = self.graph.borrow(py);
        let nodes: Vec<PyObject> = g
            .inner
            .nodes_ordered()
            .into_iter()
            .map(|n| g.py_node_key(py, n))
            .collect();
        Py::new(py, crate::NodeIterator { inner: nodes.into_iter() })
    }

    #[pyo3(signature = (data=false, default=None))]
    fn __call__(
        &self,
        py: Python<'_>,
        data: bool,
        default: Option<PyObject>,
    ) -> PyResult<Vec<PyObject>> {
        let g = self.graph.borrow(py);
        if data {
            let mut result = Vec::new();
            for node in g.inner.nodes_ordered() {
                let py_node = g.py_node_key(py, node);
                let attrs = g
                    .node_py_attrs
                    .get(node)
                    .map_or_else(
                        || default.as_ref().map_or_else(|| PyDict::new(py).into_any().unbind(), |d| d.clone_ref(py)),
                        |d| d.clone_ref(py).into_any(),
                    );
                let pair = PyTuple::new(py, &[py_node, attrs])?;
                result.push(pair.into_any().unbind());
            }
            Ok(result)
        } else {
            Ok(g.inner.nodes_ordered().into_iter().map(|n| g.py_node_key(py, n)).collect())
        }
    }

    fn __getitem__(&self, py: Python<'_>, n: &Bound<'_, PyAny>) -> PyResult<PyObject> {
        let g = self.graph.borrow(py);
        let canonical = node_key_to_string(py, n)?;
        if !g.inner.has_node(&canonical) {
            return Err(PyKeyError::new_err(format!("{}", n.repr()?)));
        }
        Ok(g.node_py_attrs
            .get(&canonical)
            .map_or_else(|| PyDict::new(py).into_any().unbind(), |d| d.clone_ref(py).into_any()))
    }
}

#[pyclass]
pub struct MultiDiGraphEdgeView {
    graph: Py<PyMultiDiGraph>,
}

#[pymethods]
impl MultiDiGraphEdgeView {
    fn __len__(&self, py: Python<'_>) -> usize {
        self.graph.borrow(py).inner.edge_count()
    }

    fn __iter__(&self, py: Python<'_>) -> PyResult<Py<crate::NodeIterator>> {
        self.__call__(py, false, false, None)
    }

    #[pyo3(signature = (data=false, keys=false, default=None))]
    fn __call__(
        &self,
        py: Python<'_>,
        data: bool,
        keys: bool,
        default: Option<PyObject>,
    ) -> PyResult<Py<crate::NodeIterator>> {
        let g = self.graph.borrow(py);
        let mut result = Vec::new();
        let edges = g.inner.edges_ordered();
        for edge in &edges {
            let py_u = g.py_node_key(py, &edge.source);
            let py_v = g.py_node_key(py, &edge.target);
            if data && keys {
                let ek = PyMultiDiGraph::edge_key(&edge.source, &edge.target, edge.key);
                let attrs = g
                    .edge_py_attrs
                    .get(&ek)
                    .map_or_else(
                        || default.as_ref().map_or_else(|| PyDict::new(py).into_any().unbind(), |d| d.clone_ref(py)),
                        |d| d.clone_ref(py).into_any(),
                    );
                let key_obj: PyObject = edge.key.into_pyobject(py).expect("key").into_any().unbind();
                let tuple = PyTuple::new(py, &[py_u, py_v, key_obj, attrs])?;
                result.push(tuple.into_any().unbind());
            } else if data {
                let ek = PyMultiDiGraph::edge_key(&edge.source, &edge.target, edge.key);
                let attrs = g
                    .edge_py_attrs
                    .get(&ek)
                    .map_or_else(
                        || default.as_ref().map_or_else(|| PyDict::new(py).into_any().unbind(), |d| d.clone_ref(py)),
                        |d| d.clone_ref(py).into_any(),
                    );
                let tuple = PyTuple::new(py, &[py_u, py_v, attrs])?;
                result.push(tuple.into_any().unbind());
            } else if keys {
                let key_obj: PyObject = edge.key.into_pyobject(py).expect("key").into_any().unbind();
                let tuple = PyTuple::new(py, &[py_u, py_v, key_obj])?;
                result.push(tuple.into_any().unbind());
            } else {
                let tuple = PyTuple::new(py, &[py_u, py_v])?;
                result.push(tuple.into_any().unbind());
            }
        }
        Py::new(py, crate::NodeIterator { inner: result.into_iter() })
    }
}

#[pyclass]
pub struct MultiDiGraphDegreeView {
    graph: Py<PyMultiDiGraph>,
    kind: DegreeKind,
}

#[pymethods]
impl MultiDiGraphDegreeView {
    fn __len__(&self, py: Python<'_>) -> usize {
        self.graph.borrow(py).inner.node_count()
    }

    fn __getitem__(&self, py: Python<'_>, n: &Bound<'_, PyAny>) -> PyResult<usize> {
        let g = self.graph.borrow(py);
        let canonical = node_key_to_string(py, n)?;
        if !g.inner.has_node(&canonical) {
            return Err(PyKeyError::new_err(format!("{}", n.repr()?)));
        }
        Ok(match self.kind {
            DegreeKind::Total => g.inner.degree(&canonical),
            DegreeKind::In => g.inner.in_degree(&canonical),
            DegreeKind::Out => g.inner.out_degree(&canonical),
        })
    }

    fn __iter__(&self, py: Python<'_>) -> PyResult<Py<crate::NodeIterator>> {
        let g = self.graph.borrow(py);
        let mut result = Vec::new();
        for node in g.inner.nodes_ordered() {
            let py_node = g.py_node_key(py, node);
            let deg = match self.kind {
                DegreeKind::Total => g.inner.degree(node),
                DegreeKind::In => g.inner.in_degree(node),
                DegreeKind::Out => g.inner.out_degree(node),
            };
            let deg_obj: PyObject = deg.into_pyobject(py).expect("degree").into_any().unbind();
            let pair = PyTuple::new(py, &[py_node, deg_obj])?;
            result.push(pair.into_any().unbind());
        }
        Py::new(py, crate::NodeIterator { inner: result.into_iter() })
    }
}

impl PyDiGraph {
    /// Directed edge key — preserves order (no canonicalization).
    pub(crate) fn edge_key(u: &str, v: &str) -> (String, String) {
        (u.to_owned(), v.to_owned())
    }

    pub(crate) fn py_node_key(&self, py: Python<'_>, canonical: &str) -> PyObject {
        self.node_key_map.get(canonical).map_or_else(
            || {
                unwrap_infallible(canonical.to_owned().into_pyobject(py))
                    .into_any()
                    .unbind()
            },
            |obj| obj.clone_ref(py),
        )
    }

    #[allow(dead_code)] // Used by directed algorithm bindings (bd-uode.3).
    pub(crate) fn new_empty(py: Python<'_>) -> PyResult<Self> {
        Ok(Self {
            inner: DiGraph::strict(),
            node_key_map: HashMap::new(),
            node_py_attrs: HashMap::new(),
            edge_py_attrs: HashMap::new(),
            graph_attrs: PyDict::new(py).unbind(),
        })
    }
}

#[pymethods]
impl PyDiGraph {
    /// Create a new DiGraph.
    #[new]
    #[pyo3(signature = (incoming_graph_data=None, **attr))]
    fn new(
        py: Python<'_>,
        incoming_graph_data: Option<&Bound<'_, PyAny>>,
        attr: Option<&Bound<'_, PyDict>>,
    ) -> PyResult<Self> {
        let graph_attrs = PyDict::new(py);
        if let Some(a) = attr {
            graph_attrs.update(a.as_mapping())?;
        }

        let mut g = Self {
            inner: DiGraph::strict(),
            node_key_map: HashMap::new(),
            node_py_attrs: HashMap::new(),
            edge_py_attrs: HashMap::new(),
            graph_attrs: graph_attrs.unbind(),
        };

        if let Some(data) = incoming_graph_data {
            // Copy from another PyDiGraph.
            if let Ok(other) = data.extract::<PyRef<'_, PyDiGraph>>() {
                for (canonical, py_key) in &other.node_key_map {
                    g.inner.add_node(canonical.clone());
                    g.node_key_map
                        .insert(canonical.clone(), py_key.clone_ref(py));
                    if let Some(attrs) = other.node_py_attrs.get(canonical) {
                        g.node_py_attrs
                            .insert(canonical.clone(), attrs.bind(py).copy()?.unbind());
                    }
                }
                for ((u, v), attrs) in &other.edge_py_attrs {
                    let _ = g.inner.add_edge(u.clone(), v.clone());
                    g.edge_py_attrs
                        .insert((u.clone(), v.clone()), attrs.bind(py).copy()?.unbind());
                }
                g.graph_attrs = other.graph_attrs.bind(py).copy()?.unbind();
            }
            // Copy from undirected PyGraph — create both directions.
            else if let Ok(other) = data.extract::<PyRef<'_, PyGraph>>() {
                for (canonical, py_key) in &other.node_key_map {
                    g.inner.add_node(canonical.clone());
                    g.node_key_map
                        .insert(canonical.clone(), py_key.clone_ref(py));
                    if let Some(attrs) = other.node_py_attrs.get(canonical) {
                        g.node_py_attrs
                            .insert(canonical.clone(), attrs.bind(py).copy()?.unbind());
                    }
                }
                // For each undirected edge, add both directions.
                for ((u, v), attrs) in &other.edge_py_attrs {
                    let _ = g.inner.add_edge(u.clone(), v.clone());
                    g.edge_py_attrs
                        .insert((u.clone(), v.clone()), attrs.bind(py).copy()?.unbind());
                    // Add reverse direction too (unless self-loop).
                    if u != v {
                        let _ = g.inner.add_edge(v.clone(), u.clone());
                        g.edge_py_attrs
                            .insert((v.clone(), u.clone()), attrs.bind(py).copy()?.unbind());
                    }
                }
                g.graph_attrs = other.graph_attrs.bind(py).copy()?.unbind();
            }
        }

        Ok(g)
    }

    // ---- Properties ----

    #[getter]
    fn graph(&self, py: Python<'_>) -> Py<PyDict> {
        self.graph_attrs.clone_ref(py)
    }

    #[getter]
    fn name(&self, py: Python<'_>) -> PyResult<String> {
        let gd = self.graph_attrs.bind(py);
        match gd.get_item("name")? {
            Some(v) => v.extract(),
            None => Ok(String::new()),
        }
    }

    #[setter]
    fn set_name(&self, py: Python<'_>, value: String) -> PyResult<()> {
        self.graph_attrs.bind(py).set_item("name", value)
    }

    // ---- Predicates ----

    /// Always ``True`` for DiGraph.
    fn is_directed(&self) -> bool {
        true
    }

    /// Always ``False`` for DiGraph.
    fn is_multigraph(&self) -> bool {
        false
    }

    // ---- Counts ----

    fn number_of_nodes(&self) -> usize {
        self.inner.node_count()
    }

    fn order(&self) -> usize {
        self.inner.node_count()
    }

    fn number_of_edges(&self) -> usize {
        self.inner.edge_count()
    }

    /// Number of edges, optionally weighted.
    #[pyo3(signature = (weight=None))]
    fn size(&self, py: Python<'_>, weight: Option<&str>) -> PyResult<f64> {
        match weight {
            None => Ok(self.inner.edge_count() as f64),
            Some(attr) => {
                let mut total = 0.0_f64;
                for dict in self.edge_py_attrs.values() {
                    let bound = dict.bind(py);
                    match bound.get_item(attr)? {
                        Some(val) => {
                            total += val.extract::<f64>()?;
                        }
                        None => {
                            total += 1.0;
                        }
                    }
                }
                Ok(total)
            }
        }
    }

    // ---- Node mutation ----

    #[pyo3(signature = (n, **attr))]
    fn add_node(
        &mut self,
        py: Python<'_>,
        n: &Bound<'_, PyAny>,
        attr: Option<&Bound<'_, PyDict>>,
    ) -> PyResult<()> {
        let canonical = node_key_to_string(py, n)?;
        self.node_key_map
            .insert(canonical.clone(), n.clone().unbind());

        let mut rust_attrs = AttrMap::new();
        let py_dict = self
            .node_py_attrs
            .entry(canonical.clone())
            .or_insert_with(|| PyDict::new(py).unbind());
        if let Some(a) = attr {
            for (k, v) in a.iter() {
                let key: String = k.extract()?;
                let val_str = v.str()?.to_string();
                rust_attrs.insert(key.clone(), val_str);
                py_dict.bind(py).set_item(k, v)?;
            }
        }

        self.inner.add_node_with_attrs(canonical, rust_attrs);
        Ok(())
    }

    #[pyo3(signature = (nodes_for_adding, **attr))]
    fn add_nodes_from(
        &mut self,
        py: Python<'_>,
        nodes_for_adding: &Bound<'_, PyAny>,
        attr: Option<&Bound<'_, PyDict>>,
    ) -> PyResult<()> {
        let iter = PyIterator::from_object(nodes_for_adding)?;
        for item in iter {
            let item = item?;
            if let Ok(tuple) = item.downcast::<PyTuple>()
                && tuple.len() == 2
            {
                let node = tuple.get_item(0)?;
                let node_attrs = tuple.get_item(1)?;
                let merged = PyDict::new(py);
                if let Some(a) = attr {
                    merged.update(a.as_mapping())?;
                }
                if let Ok(d) = node_attrs.downcast::<PyDict>() {
                    merged.update(d.as_mapping())?;
                }
                self.add_node(py, &node, Some(&merged))?;
                continue;
            }
            self.add_node(py, &item, attr)?;
        }
        Ok(())
    }

    fn remove_node(&mut self, py: Python<'_>, n: &Bound<'_, PyAny>) -> PyResult<()> {
        let canonical = node_key_to_string(py, n)?;
        if !self.inner.has_node(&canonical) {
            return Err(NodeNotFound::new_err(format!(
                "The node {} is not in the graph.",
                n.repr()?
            )));
        }
        self.inner.remove_node(&canonical);
        self.node_key_map.remove(&canonical);
        self.node_py_attrs.remove(&canonical);
        let keys_to_remove: Vec<(String, String)> = self
            .edge_py_attrs
            .keys()
            .filter(|(u, v)| u == &canonical || v == &canonical)
            .cloned()
            .collect();
        for k in keys_to_remove {
            self.edge_py_attrs.remove(&k);
        }
        Ok(())
    }

    fn remove_nodes_from(&mut self, py: Python<'_>, nodes: &Bound<'_, PyAny>) -> PyResult<()> {
        let iter = PyIterator::from_object(nodes)?;
        for item in iter {
            let item = item?;
            let canonical = node_key_to_string(py, &item)?;
            if self.inner.has_node(&canonical) {
                self.inner.remove_node(&canonical);
                self.node_key_map.remove(&canonical);
                self.node_py_attrs.remove(&canonical);
                let keys_to_remove: Vec<(String, String)> = self
                    .edge_py_attrs
                    .keys()
                    .filter(|(u, v)| u == &canonical || v == &canonical)
                    .cloned()
                    .collect();
                for k in keys_to_remove {
                    self.edge_py_attrs.remove(&k);
                }
            }
        }
        Ok(())
    }

    // ---- Edge mutation ----

    #[pyo3(signature = (u, v, **attr))]
    fn add_edge(
        &mut self,
        py: Python<'_>,
        u: &Bound<'_, PyAny>,
        v: &Bound<'_, PyAny>,
        attr: Option<&Bound<'_, PyDict>>,
    ) -> PyResult<()> {
        let u_canonical = node_key_to_string(py, u)?;
        let v_canonical = node_key_to_string(py, v)?;

        self.node_key_map
            .entry(u_canonical.clone())
            .or_insert_with(|| u.clone().unbind());
        self.node_key_map
            .entry(v_canonical.clone())
            .or_insert_with(|| v.clone().unbind());
        self.node_py_attrs
            .entry(u_canonical.clone())
            .or_insert_with(|| PyDict::new(py).unbind());
        self.node_py_attrs
            .entry(v_canonical.clone())
            .or_insert_with(|| PyDict::new(py).unbind());

        let mut rust_attrs = AttrMap::new();
        // Directed: edge key is (source, target) — NOT canonicalized.
        let ek = Self::edge_key(&u_canonical, &v_canonical);
        let py_dict = self
            .edge_py_attrs
            .entry(ek)
            .or_insert_with(|| PyDict::new(py).unbind());
        if let Some(a) = attr {
            for (k, val) in a.iter() {
                let key: String = k.extract()?;
                let val_str = val.str()?.to_string();
                rust_attrs.insert(key, val_str);
                py_dict.bind(py).set_item(k, val)?;
            }
        }

        self.inner
            .add_edge_with_attrs(u_canonical, v_canonical, rust_attrs)
            .map_err(|e| NetworkXError::new_err(e.to_string()))
    }

    #[pyo3(signature = (ebunch_to_add, **attr))]
    fn add_edges_from(
        &mut self,
        py: Python<'_>,
        ebunch_to_add: &Bound<'_, PyAny>,
        attr: Option<&Bound<'_, PyDict>>,
    ) -> PyResult<()> {
        let iter = PyIterator::from_object(ebunch_to_add)?;
        for item in iter {
            let item = item?;
            let tuple = item.downcast::<PyTuple>().map_err(|_| {
                PyTypeError::new_err("each edge must be a tuple (u, v) or (u, v, attr_dict)")
            })?;
            let len = tuple.len();
            if !(2..=3).contains(&len) {
                return Err(PyValueError::new_err(
                    "edge tuple must have 2 or 3 elements",
                ));
            }
            let u = tuple.get_item(0)?;
            let v = tuple.get_item(1)?;
            let merged = PyDict::new(py);
            if let Some(a) = attr {
                merged.update(a.as_mapping())?;
            }
            if len == 3 {
                let d = tuple.get_item(2)?;
                if let Ok(d) = d.downcast::<PyDict>() {
                    merged.update(d.as_mapping())?;
                }
            }
            self.add_edge(py, &u, &v, Some(&merged))?;
        }
        Ok(())
    }

    #[pyo3(signature = (ebunch_to_add, weight="weight"))]
    fn add_weighted_edges_from(
        &mut self,
        py: Python<'_>,
        ebunch_to_add: &Bound<'_, PyAny>,
        weight: &str,
    ) -> PyResult<()> {
        let iter = PyIterator::from_object(ebunch_to_add)?;
        for item in iter {
            let item = item?;
            let tuple = item
                .downcast::<PyTuple>()
                .map_err(|_| PyTypeError::new_err("each element must be a (u, v, w) tuple"))?;
            if tuple.len() != 3 {
                return Err(PyValueError::new_err("expected (u, v, w) tuples"));
            }
            let u = tuple.get_item(0)?;
            let v = tuple.get_item(1)?;
            let w = tuple.get_item(2)?;
            let d = PyDict::new(py);
            d.set_item(weight, w)?;
            self.add_edge(py, &u, &v, Some(&d))?;
        }
        Ok(())
    }

    fn remove_edge(
        &mut self,
        py: Python<'_>,
        u: &Bound<'_, PyAny>,
        v: &Bound<'_, PyAny>,
    ) -> PyResult<()> {
        let u_canonical = node_key_to_string(py, u)?;
        let v_canonical = node_key_to_string(py, v)?;
        let removed = self.inner.remove_edge(&u_canonical, &v_canonical);
        if !removed {
            return Err(NetworkXError::new_err(format!(
                "The edge {}-{} is not in the graph",
                u.repr()?,
                v.repr()?
            )));
        }
        let ek = Self::edge_key(&u_canonical, &v_canonical);
        self.edge_py_attrs.remove(&ek);
        Ok(())
    }

    fn remove_edges_from(&mut self, py: Python<'_>, ebunch: &Bound<'_, PyAny>) -> PyResult<()> {
        let iter = PyIterator::from_object(ebunch)?;
        for item in iter {
            let item = item?;
            let tuple = item
                .downcast::<PyTuple>()
                .map_err(|_| PyTypeError::new_err("each element must be a (u, v) tuple"))?;
            if tuple.len() < 2 {
                continue;
            }
            let u = tuple.get_item(0)?;
            let v = tuple.get_item(1)?;
            let u_c = node_key_to_string(py, &u)?;
            let v_c = node_key_to_string(py, &v)?;
            self.inner.remove_edge(&u_c, &v_c);
            let ek = Self::edge_key(&u_c, &v_c);
            self.edge_py_attrs.remove(&ek);
        }
        Ok(())
    }

    // ---- Directed-specific queries ----

    /// Return a list of successors of node n.
    fn successors(&self, py: Python<'_>, n: &Bound<'_, PyAny>) -> PyResult<Vec<PyObject>> {
        let canonical = node_key_to_string(py, n)?;
        match self.inner.successors(&canonical) {
            Some(succs) => Ok(succs.into_iter().map(|s| self.py_node_key(py, s)).collect()),
            None => Err(NodeNotFound::new_err(format!(
                "The node {} is not in the graph.",
                n.repr()?
            ))),
        }
    }

    /// Return a list of predecessors of node n.
    #[pyo3(name = "predecessors")]
    fn predecessors_method(&self, py: Python<'_>, n: &Bound<'_, PyAny>) -> PyResult<Vec<PyObject>> {
        let canonical = node_key_to_string(py, n)?;
        match self.inner.predecessors(&canonical) {
            Some(preds) => Ok(preds.into_iter().map(|p| self.py_node_key(py, p)).collect()),
            None => Err(NodeNotFound::new_err(format!(
                "The node {} is not in the graph.",
                n.repr()?
            ))),
        }
    }

    /// Neighbors = successors (matches NetworkX ``DiGraph.neighbors()``).
    fn neighbors(&self, py: Python<'_>, n: &Bound<'_, PyAny>) -> PyResult<Vec<PyObject>> {
        self.successors(py, n)
    }

    fn adjacency<'py>(&self, py: Python<'py>) -> PyResult<Vec<(PyObject, Vec<PyObject>)>> {
        let nodes = self.inner.nodes_ordered();
        let mut result = Vec::with_capacity(nodes.len());
        for node in nodes {
            let py_node = self.py_node_key(py, node);
            let succs = self
                .inner
                .successors(node)
                .unwrap_or_default()
                .into_iter()
                .map(|s| self.py_node_key(py, s))
                .collect();
            result.push((py_node, succs));
        }
        Ok(result)
    }

    // ---- Utility methods ----

    fn clear(&mut self, py: Python<'_>) -> PyResult<()> {
        self.inner = DiGraph::strict();
        self.node_key_map.clear();
        self.node_py_attrs.clear();
        self.edge_py_attrs.clear();
        self.graph_attrs = PyDict::new(py).unbind();
        Ok(())
    }

    fn clear_edges(&mut self) {
        let edges: Vec<(String, String)> = self.edge_py_attrs.keys().cloned().collect();
        for (u, v) in edges {
            self.inner.remove_edge(&u, &v);
        }
        self.edge_py_attrs.clear();
    }

    fn has_node(&self, py: Python<'_>, n: &Bound<'_, PyAny>) -> PyResult<bool> {
        let canonical = node_key_to_string(py, n)?;
        Ok(self.inner.has_node(&canonical))
    }

    /// Return True if directed edge (u, v) exists.
    fn has_edge(
        &self,
        py: Python<'_>,
        u: &Bound<'_, PyAny>,
        v: &Bound<'_, PyAny>,
    ) -> PyResult<bool> {
        let u_c = node_key_to_string(py, u)?;
        let v_c = node_key_to_string(py, v)?;
        Ok(self.inner.has_edge(&u_c, &v_c))
    }

    /// Return a reversed copy of the digraph.
    fn reverse(&self, py: Python<'_>) -> PyResult<Self> {
        let mut rev = Self {
            inner: DiGraph::strict(),
            node_key_map: HashMap::new(),
            node_py_attrs: HashMap::new(),
            edge_py_attrs: HashMap::new(),
            graph_attrs: self.graph_attrs.bind(py).copy()?.unbind(),
        };
        // Copy nodes.
        for (canonical, py_key) in &self.node_key_map {
            rev.inner.add_node(canonical.clone());
            rev.node_key_map
                .insert(canonical.clone(), py_key.clone_ref(py));
            if let Some(attrs) = self.node_py_attrs.get(canonical) {
                rev.node_py_attrs
                    .insert(canonical.clone(), attrs.bind(py).copy()?.unbind());
            }
        }
        // Reverse edges: (u, v) -> (v, u).
        for ((u, v), attrs) in &self.edge_py_attrs {
            let _ = rev.inner.add_edge(v.clone(), u.clone());
            rev.edge_py_attrs
                .insert((v.clone(), u.clone()), attrs.bind(py).copy()?.unbind());
        }
        Ok(rev)
    }

    /// Convert to undirected PyGraph — merges parallel directed edges.
    fn to_undirected(&self, py: Python<'_>) -> PyResult<PyGraph> {
        let mut ug = PyGraph::new_empty(py)?;
        // Copy nodes.
        for (canonical, py_key) in &self.node_key_map {
            ug.inner.add_node(canonical.clone());
            ug.node_key_map
                .insert(canonical.clone(), py_key.clone_ref(py));
            if let Some(attrs) = self.node_py_attrs.get(canonical) {
                ug.node_py_attrs
                    .insert(canonical.clone(), attrs.bind(py).copy()?.unbind());
            }
        }
        // Copy edges (merging directions).
        for ((u, v), attrs) in &self.edge_py_attrs {
            let _ = ug.inner.add_edge(u.clone(), v.clone());
            let ek = PyGraph::edge_key(u, v);
            if let std::collections::hash_map::Entry::Vacant(entry) = ug.edge_py_attrs.entry(ek) {
                entry.insert(attrs.bind(py).copy()?.unbind());
            }
        }
        ug.graph_attrs = self.graph_attrs.bind(py).copy()?.unbind();
        Ok(ug)
    }

    /// Return a directed copy.
    fn to_directed(&self, py: Python<'_>) -> PyResult<Self> {
        self.copy(py)
    }

    fn copy(&self, py: Python<'_>) -> PyResult<Self> {
        let mut new_graph = Self {
            inner: DiGraph::strict(),
            node_key_map: HashMap::new(),
            node_py_attrs: HashMap::new(),
            edge_py_attrs: HashMap::new(),
            graph_attrs: self.graph_attrs.bind(py).copy()?.unbind(),
        };
        for (canonical, py_key) in &self.node_key_map {
            new_graph.inner.add_node(canonical.clone());
            new_graph
                .node_key_map
                .insert(canonical.clone(), py_key.clone_ref(py));
            if let Some(attrs) = self.node_py_attrs.get(canonical) {
                new_graph
                    .node_py_attrs
                    .insert(canonical.clone(), attrs.bind(py).copy()?.unbind());
            }
        }
        for ((u, v), attrs) in &self.edge_py_attrs {
            let _ = new_graph.inner.add_edge(u.clone(), v.clone());
            new_graph
                .edge_py_attrs
                .insert((u.clone(), v.clone()), attrs.bind(py).copy()?.unbind());
        }
        Ok(new_graph)
    }

    fn subgraph(&self, py: Python<'_>, nodes: &Bound<'_, PyAny>) -> PyResult<Self> {
        let iter = PyIterator::from_object(nodes)?;
        let mut keep: std::collections::HashSet<String> = std::collections::HashSet::new();
        for item in iter {
            let item = item?;
            let canonical = node_key_to_string(py, &item)?;
            if self.inner.has_node(&canonical) {
                keep.insert(canonical);
            }
        }

        let mut new_graph = Self {
            inner: DiGraph::strict(),
            node_key_map: HashMap::new(),
            node_py_attrs: HashMap::new(),
            edge_py_attrs: HashMap::new(),
            graph_attrs: self.graph_attrs.bind(py).copy()?.unbind(),
        };

        for canonical in &keep {
            new_graph.inner.add_node(canonical.clone());
            if let Some(py_key) = self.node_key_map.get(canonical) {
                new_graph
                    .node_key_map
                    .insert(canonical.clone(), py_key.clone_ref(py));
            }
            if let Some(attrs) = self.node_py_attrs.get(canonical) {
                new_graph
                    .node_py_attrs
                    .insert(canonical.clone(), attrs.bind(py).copy()?.unbind());
            }
        }

        for ((u, v), attrs) in &self.edge_py_attrs {
            if keep.contains(u) && keep.contains(v) {
                let _ = new_graph.inner.add_edge(u.clone(), v.clone());
                new_graph
                    .edge_py_attrs
                    .insert((u.clone(), v.clone()), attrs.bind(py).copy()?.unbind());
            }
        }

        Ok(new_graph)
    }

    fn edge_subgraph(&self, py: Python<'_>, edges: &Bound<'_, PyAny>) -> PyResult<Self> {
        let iter = PyIterator::from_object(edges)?;
        let mut keep_edges: Vec<(String, String)> = Vec::new();
        for item in iter {
            let item = item?;
            let tuple = item
                .downcast::<PyTuple>()
                .map_err(|_| PyTypeError::new_err("each edge must be a (u, v) tuple"))?;
            let u = node_key_to_string(py, &tuple.get_item(0)?)?;
            let v = node_key_to_string(py, &tuple.get_item(1)?)?;
            if self.inner.has_edge(&u, &v) {
                keep_edges.push(Self::edge_key(&u, &v));
            }
        }

        let mut new_graph = Self {
            inner: DiGraph::strict(),
            node_key_map: HashMap::new(),
            node_py_attrs: HashMap::new(),
            edge_py_attrs: HashMap::new(),
            graph_attrs: self.graph_attrs.bind(py).copy()?.unbind(),
        };

        let mut nodes_needed: std::collections::HashSet<String> = std::collections::HashSet::new();
        for (u, v) in &keep_edges {
            nodes_needed.insert(u.clone());
            nodes_needed.insert(v.clone());
        }
        for canonical in &nodes_needed {
            new_graph.inner.add_node(canonical.clone());
            if let Some(py_key) = self.node_key_map.get(canonical) {
                new_graph
                    .node_key_map
                    .insert(canonical.clone(), py_key.clone_ref(py));
            }
            if let Some(attrs) = self.node_py_attrs.get(canonical) {
                new_graph
                    .node_py_attrs
                    .insert(canonical.clone(), attrs.bind(py).copy()?.unbind());
            }
        }
        for (u, v) in &keep_edges {
            let _ = new_graph.inner.add_edge(u.clone(), v.clone());
            if let Some(attrs) = self.edge_py_attrs.get(&(u.clone(), v.clone())) {
                new_graph
                    .edge_py_attrs
                    .insert((u.clone(), v.clone()), attrs.bind(py).copy()?.unbind());
            }
        }

        Ok(new_graph)
    }

    #[pyo3(signature = (edges=None, nodes=None))]
    fn update(
        &mut self,
        py: Python<'_>,
        edges: Option<&Bound<'_, PyAny>>,
        nodes: Option<&Bound<'_, PyAny>>,
    ) -> PyResult<()> {
        if let Some(e) = edges {
            self.add_edges_from(py, e, None)?;
        }
        if let Some(n) = nodes {
            self.add_nodes_from(py, n, None)?;
        }
        Ok(())
    }

    #[pyo3(signature = (u=None, v=None))]
    fn number_of_edges_between(
        &self,
        py: Python<'_>,
        u: Option<&Bound<'_, PyAny>>,
        v: Option<&Bound<'_, PyAny>>,
    ) -> PyResult<usize> {
        match (u, v) {
            (Some(u_node), Some(v_node)) => {
                let u_c = node_key_to_string(py, u_node)?;
                let v_c = node_key_to_string(py, v_node)?;
                Ok(usize::from(self.inner.has_edge(&u_c, &v_c)))
            }
            _ => Ok(self.inner.edge_count()),
        }
    }

    /// Return attributes of the edge (u, v).
    #[pyo3(signature = (u, v, default=None))]
    fn get_edge_data(
        &self,
        py: Python<'_>,
        u: &Bound<'_, PyAny>,
        v: &Bound<'_, PyAny>,
        default: Option<PyObject>,
    ) -> PyResult<PyObject> {
        let u_c = node_key_to_string(py, u)?;
        let v_c = node_key_to_string(py, v)?;
        let ek = (u_c, v_c);
        Ok(self
            .edge_py_attrs
            .get(&ek)
            .map_or_else(|| default.unwrap_or_else(|| py.None()), |d| d.clone_ref(py).into_any()))
    }

    // ---- Views (properties) ----

    #[getter]
    fn nodes(slf: PyRef<'_, Self>) -> PyResult<Py<DiNodeView>> {
        let py = slf.py();
        let graph_py: Py<PyDiGraph> = Py::from(slf);
        Py::new(
            py,
            DiNodeView {
                graph: graph_py,
                data: ViewData::NoData,
            },
        )
    }

    #[getter]
    fn edges(slf: PyRef<'_, Self>) -> PyResult<Py<DiEdgeView>> {
        let py = slf.py();
        let graph_py: Py<PyDiGraph> = Py::from(slf);
        Py::new(
            py,
            DiEdgeView {
                graph: graph_py,
                data: ViewData::NoData,
            },
        )
    }

    /// ``G.adj`` / ``G.succ`` — successor adjacency.
    #[getter]
    fn adj(slf: PyRef<'_, Self>) -> PyResult<Py<DiAdjacencyView>> {
        let py = slf.py();
        let graph_py: Py<PyDiGraph> = Py::from(slf);
        Py::new(
            py,
            DiAdjacencyView {
                graph: graph_py,
                kind: AdjKind::Successors,
            },
        )
    }

    /// ``G.succ`` — same as ``G.adj`` for DiGraph.
    #[getter]
    fn succ(slf: PyRef<'_, Self>) -> PyResult<Py<DiAdjacencyView>> {
        let py = slf.py();
        let graph_py: Py<PyDiGraph> = Py::from(slf);
        Py::new(
            py,
            DiAdjacencyView {
                graph: graph_py,
                kind: AdjKind::Successors,
            },
        )
    }

    /// ``G.pred`` — predecessor adjacency.
    #[getter]
    fn pred(slf: PyRef<'_, Self>) -> PyResult<Py<DiAdjacencyView>> {
        let py = slf.py();
        let graph_py: Py<PyDiGraph> = Py::from(slf);
        Py::new(
            py,
            DiAdjacencyView {
                graph: graph_py,
                kind: AdjKind::Predecessors,
            },
        )
    }

    /// ``G.degree`` — total degree (in + out) per node.
    #[getter]
    fn degree(slf: PyRef<'_, Self>) -> PyResult<Py<DiDegreeView>> {
        let py = slf.py();
        let graph_py: Py<PyDiGraph> = Py::from(slf);
        Py::new(
            py,
            DiDegreeView {
                graph: graph_py,
                kind: DegreeKind::Total,
            },
        )
    }

    /// ``G.in_degree`` — in-degree per node.
    #[getter]
    fn in_degree(slf: PyRef<'_, Self>) -> PyResult<Py<DiDegreeView>> {
        let py = slf.py();
        let graph_py: Py<PyDiGraph> = Py::from(slf);
        Py::new(
            py,
            DiDegreeView {
                graph: graph_py,
                kind: DegreeKind::In,
            },
        )
    }

    /// ``G.out_degree`` — out-degree per node.
    #[getter]
    fn out_degree(slf: PyRef<'_, Self>) -> PyResult<Py<DiDegreeView>> {
        let py = slf.py();
        let graph_py: Py<PyDiGraph> = Py::from(slf);
        Py::new(
            py,
            DiDegreeView {
                graph: graph_py,
                kind: DegreeKind::Out,
            },
        )
    }

    // ---- Python special methods ----

    fn __len__(&self) -> usize {
        self.inner.node_count()
    }

    fn __contains__(&self, py: Python<'_>, n: &Bound<'_, PyAny>) -> PyResult<bool> {
        let canonical = node_key_to_string(py, n)?;
        Ok(self.inner.has_node(&canonical))
    }

    fn __iter__(&self, py: Python<'_>) -> PyResult<Py<crate::NodeIterator>> {
        let nodes: Vec<PyObject> = self
            .inner
            .nodes_ordered()
            .into_iter()
            .map(|n| self.py_node_key(py, n))
            .collect();
        Py::new(
            py,
            crate::NodeIterator {
                inner: nodes.into_iter(),
            },
        )
    }

    /// ``G[n]`` — return dict of successors with edge data.
    fn __getitem__(&self, py: Python<'_>, n: &Bound<'_, PyAny>) -> PyResult<Py<PyDict>> {
        let canonical = node_key_to_string(py, n)?;
        if !self.inner.has_node(&canonical) {
            return Err(PyKeyError::new_err(format!("{}", n.repr()?)));
        }
        let succs = self.inner.successors(&canonical).unwrap_or_default();
        let result = PyDict::new(py);
        for s in succs {
            let py_s = self.py_node_key(py, s);
            let ek = Self::edge_key(&canonical, s);
            let edge_attrs = self
                .edge_py_attrs
                .get(&ek)
                .map_or_else(|| PyDict::new(py).unbind(), |d| d.clone_ref(py));
            result.set_item(py_s, edge_attrs.bind(py))?;
        }
        Ok(result.unbind())
    }

    fn __str__(&self) -> String {
        format!(
            "DiGraph with {} nodes and {} edges",
            self.inner.node_count(),
            self.inner.edge_count()
        )
    }

    fn __repr__(&self, py: Python<'_>) -> PyResult<String> {
        let name = self.name(py)?;
        if name.is_empty() {
            Ok(format!(
                "DiGraph(nodes={}, edges={})",
                self.inner.node_count(),
                self.inner.edge_count()
            ))
        } else {
            Ok(format!(
                "DiGraph(name='{}', nodes={}, edges={})",
                name,
                self.inner.node_count(),
                self.inner.edge_count()
            ))
        }
    }

    fn __bool__(&self) -> bool {
        self.inner.node_count() > 0
    }

    fn __eq__(&self, py: Python<'_>, other: &Bound<'_, PyAny>) -> PyResult<bool> {
        let other = match other.extract::<PyRef<'_, PyDiGraph>>() {
            Ok(g) => g,
            Err(_) => return Ok(false),
        };

        let my_nodes = self.inner.nodes_ordered();
        let other_nodes = other.inner.nodes_ordered();
        if my_nodes != other_nodes {
            return Ok(false);
        }

        for n in &my_nodes {
            let my_attrs = self.node_py_attrs.get(*n);
            let other_attrs = other.node_py_attrs.get(*n);
            match (my_attrs, other_attrs) {
                (Some(a), Some(b)) => {
                    if !a.bind(py).eq(b.bind(py))? {
                        return Ok(false);
                    }
                }
                (None, None) => {}
                _ => return Ok(false),
            }
        }

        if self.edge_py_attrs.len() != other.edge_py_attrs.len() {
            return Ok(false);
        }
        for ((u, v), attrs) in &self.edge_py_attrs {
            match other.edge_py_attrs.get(&(u.clone(), v.clone())) {
                Some(other_attrs) => {
                    if !attrs.bind(py).eq(other_attrs.bind(py))? {
                        return Ok(false);
                    }
                }
                None => return Ok(false),
            }
        }

        self.graph_attrs.bind(py).eq(other.graph_attrs.bind(py))
    }

    fn __copy__(&self, py: Python<'_>) -> PyResult<Self> {
        self.copy(py)
    }

    #[pyo3(signature = (_memo=None))]
    fn __deepcopy__(&self, py: Python<'_>, _memo: Option<&Bound<'_, PyAny>>) -> PyResult<Self> {
        self.copy(py)
    }

    // ---- Pickle ----

    fn __getstate__(&self, py: Python<'_>) -> PyResult<PyObject> {
        let state = PyDict::new(py);
        let nodes_list: Vec<(PyObject, Py<PyDict>)> = self
            .inner
            .nodes_ordered()
            .into_iter()
            .map(|n| {
                let py_key = self.py_node_key(py, n);
                let attrs = self
                    .node_py_attrs
                    .get(n)
                    .map_or_else(|| PyDict::new(py).unbind(), |d| d.clone_ref(py));
                (py_key, attrs)
            })
            .collect();
        state.set_item("nodes", nodes_list)?;

        let edges_list: Vec<(PyObject, PyObject, Py<PyDict>)> = self
            .edge_py_attrs
            .iter()
            .map(|((u, v), attrs)| {
                let py_u = self.py_node_key(py, u);
                let py_v = self.py_node_key(py, v);
                (py_u, py_v, attrs.clone_ref(py))
            })
            .collect();
        state.set_item("edges", edges_list)?;
        state.set_item("graph", self.graph_attrs.bind(py))?;
        Ok(state.into_any().unbind())
    }

    fn __setstate__(&mut self, py: Python<'_>, state: &Bound<'_, PyDict>) -> PyResult<()> {
        self.inner = DiGraph::strict();
        self.node_key_map.clear();
        self.node_py_attrs.clear();
        self.edge_py_attrs.clear();

        if let Some(graph_attrs) = state.get_item("graph")? {
            self.graph_attrs = graph_attrs.downcast::<PyDict>()?.copy()?.unbind();
        }

        if let Some(nodes) = state.get_item("nodes")? {
            let iter = PyIterator::from_object(&nodes)?;
            for item in iter {
                let item = item?;
                let tuple = item.downcast::<PyTuple>()?;
                let node = tuple.get_item(0)?;
                let attrs = tuple.get_item(1)?;
                let attrs_dict = attrs.downcast::<PyDict>()?;
                self.add_node(py, &node, Some(attrs_dict))?;
            }
        }

        if let Some(edges) = state.get_item("edges")? {
            let iter = PyIterator::from_object(&edges)?;
            for item in iter {
                let item = item?;
                let tuple = item.downcast::<PyTuple>()?;
                let u = tuple.get_item(0)?;
                let v = tuple.get_item(1)?;
                let attrs = tuple.get_item(2)?;
                let attrs_dict = attrs.downcast::<PyDict>()?;
                self.add_edge(py, &u, &v, Some(attrs_dict))?;
            }
        }

        Ok(())
    }
}

// ===========================================================================
// DiGraph views
// ===========================================================================

#[derive(Clone)]
enum ViewData {
    NoData,
    AllData,
    Attr(String),
}

fn parse_view_data(data: Option<&Bound<'_, PyAny>>) -> PyResult<ViewData> {
    match data {
        None => Ok(ViewData::NoData),
        Some(d) => {
            if let Ok(b) = d.extract::<bool>() {
                if b {
                    Ok(ViewData::AllData)
                } else {
                    Ok(ViewData::NoData)
                }
            } else if let Ok(attr) = d.extract::<String>() {
                Ok(ViewData::Attr(attr))
            } else {
                Err(PyTypeError::new_err(
                    "data must be True, False, or a string attribute name",
                ))
            }
        }
    }
}

// ---------------------------------------------------------------------------
// DiNodeView
// ---------------------------------------------------------------------------

#[pyclass(module = "franken_networkx")]
pub struct DiNodeView {
    graph: Py<PyDiGraph>,
    data: ViewData,
}

#[pymethods]
impl DiNodeView {
    fn __len__(&self, py: Python<'_>) -> usize {
        self.graph.borrow(py).inner.node_count()
    }

    fn __contains__(&self, py: Python<'_>, n: &Bound<'_, PyAny>) -> PyResult<bool> {
        let g = self.graph.borrow(py);
        let canonical = node_key_to_string(py, n)?;
        Ok(g.inner.has_node(&canonical))
    }

    fn __iter__(&self, py: Python<'_>) -> PyResult<Py<DiViewIterator>> {
        let g = self.graph.borrow(py);
        let nodes = g.inner.nodes_ordered();
        let items: Vec<PyObject> = match &self.data {
            ViewData::NoData => nodes.iter().map(|n| g.py_node_key(py, n)).collect(),
            ViewData::AllData => nodes
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
            ViewData::Attr(attr) => nodes
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
            DiViewIterator {
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

    fn __bool__(&self, py: Python<'_>) -> bool {
        self.graph.borrow(py).inner.node_count() > 0
    }

    #[pyo3(signature = (data=None, default=None))]
    fn __call__(
        &self,
        py: Python<'_>,
        data: Option<&Bound<'_, PyAny>>,
        default: Option<&Bound<'_, PyAny>>,
    ) -> PyResult<Py<DiNodeView>> {
        let _ = default;
        let view_data = parse_view_data(data)?;
        Py::new(
            py,
            DiNodeView {
                graph: self.graph.clone_ref(py),
                data: view_data,
            },
        )
    }
}

// ---------------------------------------------------------------------------
// DiEdgeView
// ---------------------------------------------------------------------------

#[pyclass(module = "franken_networkx")]
pub struct DiEdgeView {
    graph: Py<PyDiGraph>,
    data: ViewData,
}

#[pymethods]
impl DiEdgeView {
    fn __len__(&self, py: Python<'_>) -> usize {
        self.graph.borrow(py).inner.edge_count()
    }

    fn __contains__(&self, py: Python<'_>, edge: &Bound<'_, PyAny>) -> PyResult<bool> {
        let tuple = edge
            .downcast::<PyTuple>()
            .map_err(|_| PyTypeError::new_err("edge must be a (u, v) tuple"))?;
        if tuple.len() < 2 {
            return Ok(false);
        }
        let u = node_key_to_string(py, &tuple.get_item(0)?)?;
        let v = node_key_to_string(py, &tuple.get_item(1)?)?;
        Ok(self.graph.borrow(py).inner.has_edge(&u, &v))
    }

    fn __iter__(&self, py: Python<'_>) -> PyResult<Py<DiViewIterator>> {
        let g = self.graph.borrow(py);
        let items: Vec<PyObject> = g
            .edge_py_attrs
            .iter()
            .map(|((u, v), attrs)| {
                let py_u = g.py_node_key(py, u);
                let py_v = g.py_node_key(py, v);
                match &self.data {
                    ViewData::NoData => tuple_object(py, &[py_u, py_v]),
                    ViewData::AllData => {
                        let a: PyObject = attrs.clone_ref(py).into_any();
                        tuple_object(py, &[py_u, py_v, a])
                    }
                    ViewData::Attr(attr_name) => {
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
            DiViewIterator {
                inner: items.into_iter(),
            },
        )
    }

    fn __getitem__(&self, py: Python<'_>, edge: &Bound<'_, PyAny>) -> PyResult<Py<PyDict>> {
        let tuple = edge
            .downcast::<PyTuple>()
            .map_err(|_| PyTypeError::new_err("edge key must be a (u, v) tuple"))?;
        let u = node_key_to_string(py, &tuple.get_item(0)?)?;
        let v = node_key_to_string(py, &tuple.get_item(1)?)?;
        let g = self.graph.borrow(py);
        if !g.inner.has_edge(&u, &v) {
            return Err(PyKeyError::new_err(format!("({}, {})", u, v)));
        }
        let ek = PyDiGraph::edge_key(&u, &v);
        Ok(g.edge_py_attrs
            .get(&ek)
            .map_or_else(|| PyDict::new(py).unbind(), |d| d.clone_ref(py)))
    }

    fn __bool__(&self, py: Python<'_>) -> bool {
        self.graph.borrow(py).inner.edge_count() > 0
    }

    #[pyo3(signature = (data=None, nbunch=None, default=None))]
    fn __call__(
        &self,
        py: Python<'_>,
        data: Option<&Bound<'_, PyAny>>,
        nbunch: Option<&Bound<'_, PyAny>>,
        default: Option<&Bound<'_, PyAny>>,
    ) -> PyResult<PyObject> {
        let _ = default;
        if let Some(nb) = nbunch {
            let iter = PyIterator::from_object(nb)?;
            let g = self.graph.borrow(py);
            let mut node_set: std::collections::HashSet<String> = std::collections::HashSet::new();
            for item in iter {
                let item = item?;
                node_set.insert(node_key_to_string(py, &item)?);
            }
            let view_data = parse_view_data(data)?;
            let items: Vec<PyObject> = g
                .edge_py_attrs
                .iter()
                .filter(|((u, _v), _)| node_set.contains(u))
                .map(|((u, v), attrs)| {
                    let py_u = g.py_node_key(py, u);
                    let py_v = g.py_node_key(py, v);
                    match &view_data {
                        ViewData::NoData => tuple_object(py, &[py_u, py_v]),
                        ViewData::AllData => {
                            let a: PyObject = attrs.clone_ref(py).into_any();
                            tuple_object(py, &[py_u, py_v, a])
                        }
                        ViewData::Attr(attr_name) => {
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
            let view_data = parse_view_data(data)?;
            let view = Py::new(
                py,
                DiEdgeView {
                    graph: self.graph.clone_ref(py),
                    data: view_data,
                },
            )?;
            Ok(view.into_any())
        }
    }
}

// ---------------------------------------------------------------------------
// DiDegreeView — total / in / out degree
// ---------------------------------------------------------------------------

#[derive(Clone, Copy)]
enum DegreeKind {
    Total,
    In,
    Out,
}

#[pyclass(module = "franken_networkx")]
pub struct DiDegreeView {
    graph: Py<PyDiGraph>,
    kind: DegreeKind,
}

impl DiDegreeView {
    fn node_degree(&self, g: &PyDiGraph, node: &str) -> usize {
        match self.kind {
            DegreeKind::Total => g.inner.degree(node),
            DegreeKind::In => g.inner.in_degree(node),
            DegreeKind::Out => g.inner.out_degree(node),
        }
    }
}

#[pymethods]
impl DiDegreeView {
    fn __len__(&self, py: Python<'_>) -> usize {
        self.graph.borrow(py).inner.node_count()
    }

    fn __iter__(&self, py: Python<'_>) -> PyResult<Py<DiViewIterator>> {
        let g = self.graph.borrow(py);
        let items: Vec<PyObject> = g
            .inner
            .nodes_ordered()
            .iter()
            .map(|n| {
                let py_key = g.py_node_key(py, n);
                let deg = self.node_degree(&g, n);
                let py_degree = unwrap_infallible(deg.into_pyobject(py)).into_any().unbind();
                tuple_object(py, &[py_key, py_degree])
            })
            .collect::<PyResult<Vec<_>>>()?;
        Py::new(
            py,
            DiViewIterator {
                inner: items.into_iter(),
            },
        )
    }

    fn __getitem__(&self, py: Python<'_>, n: &Bound<'_, PyAny>) -> PyResult<usize> {
        let g = self.graph.borrow(py);
        let canonical = node_key_to_string(py, n)?;
        if !g.inner.has_node(&canonical) {
            return Err(NodeNotFound::new_err(format!(
                "The node {} is not in the graph.",
                n.repr()?
            )));
        }
        Ok(self.node_degree(&g, &canonical))
    }

    fn __bool__(&self, py: Python<'_>) -> bool {
        self.graph.borrow(py).inner.node_count() > 0
    }
}

// ---------------------------------------------------------------------------
// DiAdjacencyView — successor or predecessor adjacency
// ---------------------------------------------------------------------------

#[derive(Clone, Copy)]
enum AdjKind {
    Successors,
    Predecessors,
}

#[pyclass(module = "franken_networkx")]
pub struct DiAdjacencyView {
    graph: Py<PyDiGraph>,
    kind: AdjKind,
}

#[pymethods]
impl DiAdjacencyView {
    fn __len__(&self, py: Python<'_>) -> usize {
        self.graph.borrow(py).inner.node_count()
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
        let neighbors = match self.kind {
            AdjKind::Successors => g.inner.successors(&canonical).unwrap_or_default(),
            AdjKind::Predecessors => g.inner.predecessors(&canonical).unwrap_or_default(),
        };
        let result = PyDict::new(py);
        for nb in neighbors {
            let py_nb = g.py_node_key(py, nb);
            let ek = match self.kind {
                AdjKind::Successors => PyDiGraph::edge_key(&canonical, nb),
                AdjKind::Predecessors => PyDiGraph::edge_key(nb, &canonical),
            };
            let edge_attrs = g
                .edge_py_attrs
                .get(&ek)
                .map_or_else(|| PyDict::new(py).unbind(), |d| d.clone_ref(py));
            result.set_item(py_nb, edge_attrs.bind(py))?;
        }
        Ok(result.unbind())
    }

    fn __iter__(&self, py: Python<'_>) -> PyResult<Py<crate::NodeIterator>> {
        let g = self.graph.borrow(py);
        let nodes: Vec<PyObject> = g
            .inner
            .nodes_ordered()
            .into_iter()
            .map(|n| g.py_node_key(py, n))
            .collect();
        Py::new(
            py,
            crate::NodeIterator {
                inner: nodes.into_iter(),
            },
        )
    }

    fn __bool__(&self, py: Python<'_>) -> bool {
        self.graph.borrow(py).inner.node_count() > 0
    }
}

// ---------------------------------------------------------------------------
// Shared view iterator
// ---------------------------------------------------------------------------

#[pyclass]
pub struct DiViewIterator {
    inner: std::vec::IntoIter<PyObject>,
}

#[pymethods]
impl DiViewIterator {
    fn __iter__(slf: PyRef<'_, Self>) -> PyRef<'_, Self> {
        slf
    }
    fn __next__(mut slf: PyRefMut<'_, Self>) -> Option<PyObject> {
        slf.inner.next()
    }
}

fn tuple_object(py: Python<'_>, elements: &[PyObject]) -> PyResult<PyObject> {
    Ok(PyTuple::new(py, elements)?.into_any().unbind())
}

// ---------------------------------------------------------------------------
// Registration helper
// ---------------------------------------------------------------------------

pub fn register_digraph_classes(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<PyDiGraph>()?;
    m.add_class::<PyMultiDiGraph>()?;
    m.add_class::<DiNodeView>()?;
    m.add_class::<DiEdgeView>()?;
    m.add_class::<DiDegreeView>()?;
    m.add_class::<DiAdjacencyView>()?;
    m.add_class::<DiViewIterator>()?;
    // MultiDiGraph views
    m.add_class::<MultiDiGraphNodeView>()?;
    m.add_class::<MultiDiGraphEdgeView>()?;
    m.add_class::<MultiDiGraphDegreeView>()?;
    Ok(())
}
