#![allow(clippy::type_complexity, clippy::too_many_arguments)]
#![forbid(unsafe_code)]

//! PyO3 Python bindings for FrankenNetworkX.
//!
//! This crate compiles to a cdylib that Python loads as `franken_networkx._fnx`.
//! The public Python API is re-exported through `python/franken_networkx/__init__.py`.

mod algorithms;
pub(crate) mod digraph;
mod generators;
mod readwrite;
mod views;

use fnx_classes::{AttrMap, Graph, MultiGraph};
use fnx_runtime::CgseValue;
use pyo3::exceptions::{PyKeyError, PyTypeError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyIterator, PyTuple};
use std::collections::{HashMap, HashSet};
use std::convert::Infallible;

// ---------------------------------------------------------------------------
// Exception hierarchy — mirrors NetworkX for drop-in compatibility.
// ---------------------------------------------------------------------------

pyo3::create_exception!(_fnx, NetworkXError, pyo3::exceptions::PyException);
pyo3::create_exception!(_fnx, NetworkXPointlessConcept, NetworkXError);
pyo3::create_exception!(_fnx, NetworkXAlgorithmError, NetworkXError);
pyo3::create_exception!(_fnx, NetworkXUnfeasible, NetworkXError);
pyo3::create_exception!(_fnx, NetworkXNoPath, NetworkXUnfeasible);
pyo3::create_exception!(_fnx, NetworkXNoCycle, NetworkXUnfeasible);
pyo3::create_exception!(_fnx, NetworkXUnbounded, NetworkXError);
pyo3::create_exception!(_fnx, NetworkXNotImplemented, NetworkXError);
pyo3::create_exception!(_fnx, NotATree, NetworkXError);
pyo3::create_exception!(_fnx, NodeNotFound, NetworkXError);
pyo3::create_exception!(_fnx, HasACycle, NetworkXError);
pyo3::create_exception!(_fnx, PowerIterationFailedConvergence, NetworkXError);

// ---------------------------------------------------------------------------
// NodeKey — bridge Python's dynamic node identifiers to Rust String keys.
// ---------------------------------------------------------------------------

/// Convert a Python node key to a canonical string for the Rust Graph.
fn node_key_to_string(_py: Python<'_>, key: &Bound<'_, PyAny>) -> PyResult<String> {
    if let Ok(s) = key.extract::<String>() {
        return Ok(s);
    }
    if let Ok(i) = key.extract::<i64>() {
        return Ok(i.to_string());
    }
    // For other hashable types, use repr as the canonical key.
    let repr = key.repr()?;
    Ok(repr.to_string())
}

pub(crate) fn py_dict_to_attr_map(attrs: &Bound<'_, PyDict>) -> PyResult<AttrMap> {
    let mut rust_attrs = AttrMap::new();
    for (k, v) in attrs.iter() {
        let key: String = k.extract()?;
        let val = if let Ok(s) = v.extract::<String>() {
            CgseValue::String(s)
        } else if let Ok(b) = v.extract::<bool>() {
            // bool must be checked before i64/f64 because Python bool is a subclass of int
            CgseValue::Bool(b)
        } else if let Ok(i) = v.extract::<i64>() {
            CgseValue::Int(i)
        } else if let Ok(f) = v.extract::<f64>() {
            CgseValue::Float(f)
        } else {
            CgseValue::String(v.str()?.to_string())
        };
        rust_attrs.insert(key, val);
    }
    Ok(rust_attrs)
}

use pyo3::IntoPyObjectExt;

pub(crate) fn cgse_value_to_py(py: Python<'_>, val: &CgseValue) -> PyObject {
    match val {
        CgseValue::String(s) => s.into_py_any(py).unwrap(),
        CgseValue::Float(f) => f.into_py_any(py).unwrap(),
        CgseValue::Int(i) => i.into_py_any(py).unwrap(),
        CgseValue::Bool(b) => b.into_py_any(py).unwrap(),
    }
}

// ---------------------------------------------------------------------------
// PyGraph — the main graph class wrapping fnx_classes::Graph.
// ---------------------------------------------------------------------------

/// An undirected graph — a Rust-backed drop-in replacement for ``networkx.Graph``.
#[pyclass(module = "franken_networkx", name = "Graph", dict, weakref, subclass)]
pub(crate) struct PyGraph {
    pub(crate) inner: Graph,
    /// Maps canonical string key -> original Python object for faithful round-trip.
    pub(crate) node_key_map: HashMap<String, PyObject>,
    /// Per-node Python attribute dicts.
    pub(crate) node_py_attrs: HashMap<String, Py<PyDict>>,
    /// Per-edge Python attribute dicts. Key is (canonical_left, canonical_right).
    pub(crate) edge_py_attrs: HashMap<(String, String), Py<PyDict>>,
    /// Graph-level attribute dict.
    pub(crate) graph_attrs: Py<PyDict>,
}

impl PyGraph {
    /// Get the canonical edge key tuple (left <= right for undirected).
    pub(crate) fn edge_key(u: &str, v: &str) -> (String, String) {
        if u <= v {
            (u.to_owned(), v.to_owned())
        } else {
            (v.to_owned(), u.to_owned())
        }
    }

    /// Return the original Python object for a node key, falling back to string.
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

    /// Create a new empty PyGraph (no nodes, no edges, empty graph attrs).
    pub(crate) fn new_empty(py: Python<'_>) -> PyResult<Self> {
        Ok(Self {
            inner: Graph::strict(),
            node_key_map: HashMap::new(),
            node_py_attrs: HashMap::new(),
            edge_py_attrs: HashMap::new(),
            graph_attrs: PyDict::new(py).unbind(),
        })
    }
}

#[pyclass(
    module = "franken_networkx",
    name = "MultiGraph",
    dict,
    weakref,
    subclass
)]
pub(crate) struct PyMultiGraph {
    pub(crate) inner: MultiGraph,
    pub(crate) node_key_map: HashMap<String, PyObject>,
    pub(crate) node_py_attrs: HashMap<String, Py<PyDict>>,
    pub(crate) edge_py_attrs: HashMap<(String, String, usize), Py<PyDict>>,
    pub(crate) graph_attrs: Py<PyDict>,
}

impl PyMultiGraph {
    pub(crate) fn edge_key(u: &str, v: &str, key: usize) -> (String, String, usize) {
        if u <= v {
            (u.to_owned(), v.to_owned(), key)
        } else {
            (v.to_owned(), u.to_owned(), key)
        }
    }

    fn neighbor_dict(&self, py: Python<'_>, node: &str, neighbor: &str) -> PyResult<Py<PyDict>> {
        let result = PyDict::new(py);
        for key in self.inner.edge_keys(node, neighbor).unwrap_or_default() {
            let ek = Self::edge_key(node, neighbor, key);
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
impl PyMultiGraph {
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
            inner: MultiGraph::strict(),
            node_key_map: HashMap::new(),
            node_py_attrs: HashMap::new(),
            edge_py_attrs: HashMap::new(),
            graph_attrs: graph_attrs.unbind(),
        };

        if let Some(data) = incoming_graph_data {
            if let Ok(other) = data.extract::<PyRef<'_, PyMultiGraph>>() {
                for (canonical, py_key) in &other.node_key_map {
                    let rust_attrs = other
                        .node_py_attrs
                        .get(canonical)
                        .map(|attrs| py_dict_to_attr_map(attrs.bind(py)))
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
                    let rust_attrs = py_dict_to_attr_map(attrs.bind(py))?;
                    let _ =
                        g.inner
                            .add_edge_with_key_and_attrs(u.clone(), v.clone(), *key, rust_attrs);
                    g.edge_py_attrs.insert(
                        (u.clone(), v.clone(), *key),
                        attrs.bind(py).copy()?.unbind(),
                    );
                }
                g.graph_attrs = other.graph_attrs.bind(py).copy()?.unbind();
            } else if let Ok(other) = data.extract::<PyRef<'_, PyGraph>>() {
                for (canonical, py_key) in &other.node_key_map {
                    let rust_attrs = other
                        .node_py_attrs
                        .get(canonical)
                        .map(|attrs| py_dict_to_attr_map(attrs.bind(py)))
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
                    let rust_attrs = py_dict_to_attr_map(attrs.bind(py))?;
                    let key = g
                        .inner
                        .add_edge_with_key_and_attrs(u.clone(), v.clone(), 0, rust_attrs)
                        .map_err(|e| NetworkXError::new_err(e.to_string()))?;
                    g.edge_py_attrs
                        .insert((u.clone(), v.clone(), key), attrs.bind(py).copy()?.unbind());
                }
                g.graph_attrs = other.graph_attrs.bind(py).copy()?.unbind();
            } else if let Ok(iter) = PyIterator::from_object(data) {
                for item in iter {
                    let item = item?;
                    if let Ok(tuple) = item.downcast::<PyTuple>() {
                        let merged = PyDict::new(py);
                        match tuple.len() {
                            2 => {
                                g.add_edge(
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
                                    g.add_edge(
                                        py,
                                        &tuple.get_item(0)?,
                                        &tuple.get_item(1)?,
                                        None,
                                        Some(&merged),
                                    )?;
                                } else {
                                    let edge_key = third.extract::<usize>()?;
                                    g.add_edge(
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
                                g.add_edge(
                                    py,
                                    &tuple.get_item(0)?,
                                    &tuple.get_item(1)?,
                                    Some(edge_key),
                                    Some(&merged),
                                )?;
                            }
                            _ => g.add_node(py, &item, None)?,
                        }
                    } else {
                        g.add_node(py, &item, None)?;
                    }
                }
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
        false
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

    /// Return attributes of the edge (u, v).
    /// If key is None, returns a dict of key -> attr_dict.
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
            rust_attrs = py_dict_to_attr_map(a)?;
            for (k, v) in a.iter() {
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

        // surgically remove attributes for incident edges before removing node from inner graph
        if let Some(neighbors) = self.inner.neighbors(&canonical) {
            for nb in neighbors {
                if let Some(keys) = self.inner.edge_keys(&canonical, nb) {
                    for key in keys {
                        let ek = Self::edge_key(&canonical, nb, key);
                        self.edge_py_attrs.remove(&ek);
                    }
                }
            }
        }

        self.inner.remove_node(&canonical);
        self.node_key_map.remove(&canonical);
        self.node_py_attrs.remove(&canonical);
        Ok(())
    }

    fn remove_nodes_from(&mut self, py: Python<'_>, nodes: &Bound<'_, PyAny>) -> PyResult<()> {
        let iter = PyIterator::from_object(nodes)?;
        for item in iter {
            let item = item?;
            let canonical = node_key_to_string(py, &item)?;
            if self.inner.has_node(&canonical) {
                if let Some(neighbors) = self.inner.neighbors(&canonical) {
                    for nb in neighbors {
                        if let Some(keys) = self.inner.edge_keys(&canonical, nb) {
                            for key in keys {
                                let ek = Self::edge_key(&canonical, nb, key);
                                self.edge_py_attrs.remove(&ek);
                            }
                        }
                    }
                }
                self.inner.remove_node(&canonical);
                self.node_key_map.remove(&canonical);
                self.node_py_attrs.remove(&canonical);
            }
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
            rust_attrs = py_dict_to_attr_map(a)?;
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

    fn clear(&mut self, py: Python<'_>) -> PyResult<()> {
        self.inner = MultiGraph::strict();
        self.node_key_map.clear();
        self.node_py_attrs.clear();
        self.edge_py_attrs.clear();
        self.graph_attrs = PyDict::new(py).unbind();
        Ok(())
    }

    fn clear_edges(&mut self) {
        self.inner = MultiGraph::strict();
        Python::with_gil(|py| {
            for canonical in self.node_key_map.keys() {
                let rust_attrs = self
                    .node_py_attrs
                    .get(canonical)
                    .map(|attrs| py_dict_to_attr_map(attrs.bind(py)))
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

    fn neighbors(&self, py: Python<'_>, n: &Bound<'_, PyAny>) -> PyResult<Vec<PyObject>> {
        let canonical = node_key_to_string(py, n)?;
        match self.inner.neighbors(&canonical) {
            Some(neighbors) => Ok(neighbors
                .into_iter()
                .map(|nb| {
                    self.node_key_map.get(nb).map_or_else(
                        || {
                            unwrap_infallible(nb.to_owned().into_pyobject(py))
                                .into_any()
                                .unbind()
                        },
                        |obj| obj.clone_ref(py),
                    )
                })
                .collect()),
            None => Err(NodeNotFound::new_err(format!(
                "The node {} is not in the graph.",
                n.repr()?
            ))),
        }
    }

    fn __len__(&self) -> usize {
        self.inner.node_count()
    }

    fn __contains__(&self, py: Python<'_>, n: &Bound<'_, PyAny>) -> PyResult<bool> {
        let canonical = node_key_to_string(py, n)?;
        Ok(self.inner.has_node(&canonical))
    }

    fn __iter__(&self, py: Python<'_>) -> PyResult<Py<NodeIterator>> {
        let nodes: Vec<PyObject> = self
            .inner
            .nodes_ordered()
            .into_iter()
            .map(|n| {
                self.node_key_map.get(n).map_or_else(
                    || {
                        unwrap_infallible(n.to_owned().into_pyobject(py))
                            .into_any()
                            .unbind()
                    },
                    |obj| obj.clone_ref(py),
                )
            })
            .collect();
        Py::new(
            py,
            NodeIterator {
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
        for neighbor in self.inner.neighbors(&canonical).unwrap_or_default() {
            let py_nb = self.node_key_map.get(neighbor).map_or_else(
                || {
                    unwrap_infallible(neighbor.to_owned().into_pyobject(py))
                        .into_any()
                        .unbind()
                },
                |obj| obj.clone_ref(py),
            );
            result.set_item(
                py_nb,
                self.neighbor_dict(py, &canonical, neighbor)?.bind(py),
            )?;
        }
        Ok(result.unbind())
    }

    fn __str__(&self) -> String {
        format!(
            "MultiGraph with {} nodes and {} edges",
            self.inner.node_count(),
            self.inner.edge_count()
        )
    }

    fn __repr__(&self, py: Python<'_>) -> PyResult<String> {
        let name = self.name(py)?;
        if name.is_empty() {
            Ok(format!(
                "MultiGraph(nodes={}, edges={})",
                self.inner.node_count(),
                self.inner.edge_count()
            ))
        } else {
            Ok(format!(
                "MultiGraph(name='{}', nodes={}, edges={})",
                name,
                self.inner.node_count(),
                self.inner.edge_count()
            ))
        }
    }

    fn __bool__(&self) -> bool {
        self.inner.node_count() > 0
    }
}

#[pymethods]
impl PyMultiGraph {
    // -----------------------------------------------------------------------
    // View-like property methods
    // -----------------------------------------------------------------------

    /// ``G.nodes`` — returns a NodeView-like list of nodes.
    /// Supports ``G.nodes(data=True)`` via the ``data`` kwarg.
    #[getter]
    fn nodes(slf: PyRef<'_, Self>) -> PyResult<Py<MultiGraphNodeView>> {
        let py = slf.py();
        let graph_py: Py<PyMultiGraph> = Py::from(slf);
        Py::new(py, MultiGraphNodeView { graph: graph_py })
    }

    /// ``G.edges`` — returns an EdgeView-like list of edges.
    /// Supports ``G.edges(data=True, keys=True)`` via kwargs.
    #[getter]
    fn edges(slf: PyRef<'_, Self>) -> PyResult<Py<MultiGraphEdgeView>> {
        let py = slf.py();
        let graph_py: Py<PyMultiGraph> = Py::from(slf);
        Py::new(py, MultiGraphEdgeView { graph: graph_py })
    }

    /// ``G.degree`` — returns a DegreeView-like object.
    #[getter]
    fn degree(slf: PyRef<'_, Self>) -> PyResult<Py<MultiGraphDegreeView>> {
        let py = slf.py();
        let graph_py: Py<PyMultiGraph> = Py::from(slf);
        Py::new(py, MultiGraphDegreeView { graph: graph_py })
    }

    /// ``G.adj`` — returns the adjacency dict.
    #[getter]
    fn adj(&self, py: Python<'_>) -> PyResult<Py<PyDict>> {
        self.adjacency(py)
    }

    /// Return an adjacency dict: {node: {neighbor: {key: edge_attrs}}}.
    fn adjacency(&self, py: Python<'_>) -> PyResult<Py<PyDict>> {
        let result = PyDict::new(py);
        for node in self.inner.nodes_ordered() {
            let py_node = self.py_node_key(py, node);
            let nbrs_dict = PyDict::new(py);
            for neighbor in self.inner.neighbors(node).unwrap_or_default() {
                let py_nbr = self.py_node_key(py, neighbor);
                nbrs_dict.set_item(&py_nbr, self.neighbor_dict(py, node, neighbor)?.bind(py))?;
            }
            result.set_item(py_node, nbrs_dict)?;
        }
        Ok(result.unbind())
    }

    // -----------------------------------------------------------------------
    // Copy / subgraph
    // -----------------------------------------------------------------------

    /// Return a deep copy of the multigraph.
    fn copy(&self, py: Python<'_>) -> PyResult<Self> {
        let mut new_graph = Self {
            inner: MultiGraph::strict(),
            node_key_map: HashMap::new(),
            node_py_attrs: HashMap::new(),
            edge_py_attrs: HashMap::new(),
            graph_attrs: self.graph_attrs.bind(py).copy()?.unbind(),
        };
        for (canonical, py_key) in &self.node_key_map {
            let rust_attrs = self
                .node_py_attrs
                .get(canonical)
                .map(|attrs| py_dict_to_attr_map(attrs.bind(py)))
                .transpose()?
                .unwrap_or_default();
            new_graph
                .inner
                .add_node_with_attrs(canonical.clone(), rust_attrs);
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
            let rust_attrs = py_dict_to_attr_map(attrs.bind(py))?;
            let _ =
                new_graph
                    .inner
                    .add_edge_with_key_and_attrs(u.clone(), v.clone(), *key, rust_attrs);
            new_graph.edge_py_attrs.insert(
                (u.clone(), v.clone(), *key),
                attrs.bind(py).copy()?.unbind(),
            );
        }
        Ok(new_graph)
    }

    /// Return a subgraph containing only the specified nodes.
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
            inner: MultiGraph::strict(),
            node_key_map: HashMap::new(),
            node_py_attrs: HashMap::new(),
            edge_py_attrs: HashMap::new(),
            graph_attrs: self.graph_attrs.bind(py).copy()?.unbind(),
        };

        for canonical in &keep {
            let rust_attrs = self
                .node_py_attrs
                .get(canonical)
                .map(|attrs| py_dict_to_attr_map(attrs.bind(py)))
                .transpose()?
                .unwrap_or_default();
            new_graph
                .inner
                .add_node_with_attrs(canonical.clone(), rust_attrs);
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
                let rust_attrs = py_dict_to_attr_map(attrs.bind(py))?;
                let _ = new_graph.inner.add_edge_with_key_and_attrs(
                    u.clone(),
                    v.clone(),
                    *key,
                    rust_attrs,
                );
                new_graph.edge_py_attrs.insert(
                    (u.clone(), v.clone(), *key),
                    attrs.bind(py).copy()?.unbind(),
                );
            }
        }

        Ok(new_graph)
    }

    /// Return a subgraph containing only the specified edges.
    fn edge_subgraph(&self, py: Python<'_>, edges: &Bound<'_, PyAny>) -> PyResult<Self> {
        let iter = PyIterator::from_object(edges)?;
        let mut keep_edges: Vec<(String, String, Option<usize>)> = Vec::new();
        for item in iter {
            let item = item?;
            let tuple = item
                .downcast::<PyTuple>()
                .map_err(|_| PyTypeError::new_err("each edge must be a tuple"))?;
            let u = node_key_to_string(py, &tuple.get_item(0)?)?;
            let v = node_key_to_string(py, &tuple.get_item(1)?)?;
            let key = if tuple.len() >= 3 {
                Some(tuple.get_item(2)?.extract::<usize>()?)
            } else {
                None
            };
            keep_edges.push((u, v, key));
        }

        let mut involved_nodes: HashSet<String> = HashSet::new();
        let mut new_graph = Self {
            inner: MultiGraph::strict(),
            node_key_map: HashMap::new(),
            node_py_attrs: HashMap::new(),
            edge_py_attrs: HashMap::new(),
            graph_attrs: self.graph_attrs.bind(py).copy()?.unbind(),
        };

        for (u, v, key_filter) in &keep_edges {
            let keys = self.inner.edge_keys(u, v).unwrap_or_default();
            for k in keys {
                if key_filter.is_some() && *key_filter != Some(k) {
                    continue;
                }
                involved_nodes.insert(u.clone());
                involved_nodes.insert(v.clone());
                let ek = Self::edge_key(u, v, k);
                if let Some(attrs) = self.edge_py_attrs.get(&ek) {
                    let rust_attrs = py_dict_to_attr_map(attrs.bind(py))?;
                    let _ = new_graph.inner.add_edge_with_key_and_attrs(
                        u.clone(),
                        v.clone(),
                        k,
                        rust_attrs,
                    );
                    new_graph
                        .edge_py_attrs
                        .insert(ek, attrs.bind(py).copy()?.unbind());
                } else {
                    let _ = new_graph.inner.add_edge_with_key_and_attrs(
                        u.clone(),
                        v.clone(),
                        k,
                        AttrMap::new(),
                    );
                }
            }
        }

        for canonical in &involved_nodes {
            let rust_attrs = self
                .node_py_attrs
                .get(canonical)
                .map(|attrs| py_dict_to_attr_map(attrs.bind(py)))
                .transpose()?
                .unwrap_or_default();
            new_graph
                .inner
                .add_node_with_attrs(canonical.clone(), rust_attrs);
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

    // -----------------------------------------------------------------------
    // Conversion
    // -----------------------------------------------------------------------

    /// Return an undirected copy (no-op for MultiGraph).
    fn to_undirected(&self, py: Python<'_>) -> PyResult<Self> {
        self.copy(py)
    }

    /// Return a directed copy of the graph.
    fn to_directed(&self, py: Python<'_>) -> PyResult<crate::digraph::PyMultiDiGraph> {
        let mut mdg = crate::digraph::PyMultiDiGraph {
            inner: fnx_classes::digraph::MultiDiGraph::strict(),
            node_key_map: HashMap::new(),
            node_py_attrs: HashMap::new(),
            edge_py_attrs: HashMap::new(),
            graph_attrs: self.graph_attrs.bind(py).copy()?.unbind(),
        };

        for (canonical, py_key) in &self.node_key_map {
            mdg.inner.add_node(canonical.clone());
            mdg.node_key_map
                .insert(canonical.clone(), py_key.clone_ref(py));
            if let Some(attrs) = self.node_py_attrs.get(canonical) {
                mdg.node_py_attrs
                    .insert(canonical.clone(), attrs.bind(py).copy()?.unbind());
            }
        }

        for edge in self.inner.edges_ordered() {
            let u = &edge.left;
            let v = &edge.right;
            let k = edge.key;

            let rust_attrs = edge.attrs.clone();

            let mut py_attrs_copy = None;
            let ek = PyMultiGraph::edge_key(u, v, k);
            if let Some(py_attrs) = self.edge_py_attrs.get(&ek) {
                py_attrs_copy = Some(py_attrs.bind(py).copy()?.unbind());
            }

            let new_k1 = mdg
                .inner
                .add_edge_with_attrs(u.clone(), v.clone(), rust_attrs.clone())
                .map_err(|e| crate::NetworkXError::new_err(e.to_string()))?;
            if let Some(pa) = &py_attrs_copy {
                mdg.edge_py_attrs
                    .insert((u.clone(), v.clone(), new_k1), pa.clone_ref(py));
            }

            if u != v {
                let new_k2 = mdg
                    .inner
                    .add_edge_with_attrs(v.clone(), u.clone(), rust_attrs)
                    .map_err(|e| crate::NetworkXError::new_err(e.to_string()))?;
                if let Some(pa) = py_attrs_copy {
                    mdg.edge_py_attrs.insert((v.clone(), u.clone(), new_k2), pa);
                }
            }
        }

        Ok(mdg)
    }

    // -----------------------------------------------------------------------
    // Bulk mutation
    // -----------------------------------------------------------------------

    /// Add weighted edges from a list of (u, v, weight) tuples.
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
                .map_err(|_| PyTypeError::new_err("each edge must be a (u, v, w) tuple"))?;
            if tuple.len() < 3 {
                return Err(PyValueError::new_err(
                    "each edge must have at least 3 elements (u, v, weight)",
                ));
            }
            let u = &tuple.get_item(0)?;
            let v = &tuple.get_item(1)?;
            let w = &tuple.get_item(2)?;
            let d = PyDict::new(py);
            d.set_item(weight, w)?;
            self.add_edge(py, u, v, None, Some(&d))?;
        }
        Ok(())
    }

    /// Remove edges from an iterable of edge tuples.
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
            // Silently skip edges not in the graph
            let u_c = node_key_to_string(py, u)?;
            let v_c = node_key_to_string(py, v)?;
            if self.inner.has_edge(&u_c, &v_c) {
                let _ = self.remove_edge(py, u, v, key);
            }
        }
        Ok(())
    }

    /// Update the graph from edges and/or nodes.
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

    /// Return the number of edges between u and v.
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
}

// ---------------------------------------------------------------------------
// MultiGraph view types
// ---------------------------------------------------------------------------

impl PyMultiGraph {
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
}

/// NodeView for MultiGraph — supports ``len``, ``in``, iteration, and ``G.nodes(data=True)``.
#[pyclass]
pub(crate) struct MultiGraphNodeView {
    graph: Py<PyMultiGraph>,
}

#[pymethods]
impl MultiGraphNodeView {
    fn __len__(&self, py: Python<'_>) -> usize {
        self.graph.borrow(py).inner.node_count()
    }

    fn __contains__(&self, py: Python<'_>, n: &Bound<'_, PyAny>) -> PyResult<bool> {
        let canonical = node_key_to_string(py, n)?;
        Ok(self.graph.borrow(py).inner.has_node(&canonical))
    }

    fn __iter__(&self, py: Python<'_>) -> PyResult<Py<NodeIterator>> {
        let g = self.graph.borrow(py);
        let nodes: Vec<PyObject> = g
            .inner
            .nodes_ordered()
            .into_iter()
            .map(|n| g.py_node_key(py, n))
            .collect();
        Py::new(
            py,
            NodeIterator {
                inner: nodes.into_iter(),
            },
        )
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
                let attrs = g.node_py_attrs.get(node).map_or_else(
                    || {
                        default.as_ref().map_or_else(
                            || PyDict::new(py).into_any().unbind(),
                            |d| d.clone_ref(py),
                        )
                    },
                    |d| d.clone_ref(py).into_any(),
                );
                let pair = PyTuple::new(py, &[py_node, attrs])?;
                result.push(pair.into_any().unbind());
            }
            Ok(result)
        } else {
            Ok(g.inner
                .nodes_ordered()
                .into_iter()
                .map(|n| g.py_node_key(py, n))
                .collect())
        }
    }

    fn __getitem__(&self, py: Python<'_>, n: &Bound<'_, PyAny>) -> PyResult<PyObject> {
        let g = self.graph.borrow(py);
        let canonical = node_key_to_string(py, n)?;
        if !g.inner.has_node(&canonical) {
            return Err(PyKeyError::new_err(format!("{}", n.repr()?)));
        }
        Ok(g.node_py_attrs.get(&canonical).map_or_else(
            || PyDict::new(py).into_any().unbind(),
            |d| d.clone_ref(py).into_any(),
        ))
    }
}

/// EdgeView for MultiGraph — supports ``len``, iteration, and ``G.edges(data=True, keys=True)``.
#[pyclass]
pub(crate) struct MultiGraphEdgeView {
    graph: Py<PyMultiGraph>,
}

#[pymethods]
impl MultiGraphEdgeView {
    fn __len__(&self, py: Python<'_>) -> usize {
        self.graph.borrow(py).inner.edge_count()
    }

    fn __iter__(&self, py: Python<'_>) -> PyResult<Py<NodeIterator>> {
        self.__call__(py, false, false, None)
    }

    #[pyo3(signature = (data=false, keys=false, default=None))]
    fn __call__(
        &self,
        py: Python<'_>,
        data: bool,
        keys: bool,
        default: Option<PyObject>,
    ) -> PyResult<Py<NodeIterator>> {
        let g = self.graph.borrow(py);
        let mut result = Vec::new();
        let edges = g.inner.edges_ordered();
        for edge in &edges {
            let py_u = g.py_node_key(py, &edge.left);
            let py_v = g.py_node_key(py, &edge.right);
            if data && keys {
                let ek = PyMultiGraph::edge_key(&edge.left, &edge.right, edge.key);
                let attrs = g.edge_py_attrs.get(&ek).map_or_else(
                    || {
                        default.as_ref().map_or_else(
                            || PyDict::new(py).into_any().unbind(),
                            |d| d.clone_ref(py),
                        )
                    },
                    |d| d.clone_ref(py).into_any(),
                );
                let key_obj: PyObject = edge
                    .key
                    .into_pyobject(py)
                    .expect("key conversion")
                    .into_any()
                    .unbind();
                let tuple = PyTuple::new(py, &[py_u, py_v, key_obj, attrs])?;
                result.push(tuple.into_any().unbind());
            } else if data {
                let ek = PyMultiGraph::edge_key(&edge.left, &edge.right, edge.key);
                let attrs = g.edge_py_attrs.get(&ek).map_or_else(
                    || {
                        default.as_ref().map_or_else(
                            || PyDict::new(py).into_any().unbind(),
                            |d| d.clone_ref(py),
                        )
                    },
                    |d| d.clone_ref(py).into_any(),
                );
                let tuple = PyTuple::new(py, &[py_u, py_v, attrs])?;
                result.push(tuple.into_any().unbind());
            } else if keys {
                let key_obj: PyObject = edge
                    .key
                    .into_pyobject(py)
                    .expect("key conversion")
                    .into_any()
                    .unbind();
                let tuple = PyTuple::new(py, &[py_u, py_v, key_obj])?;
                result.push(tuple.into_any().unbind());
            } else {
                let tuple = PyTuple::new(py, &[py_u, py_v])?;
                result.push(tuple.into_any().unbind());
            }
        }
        Py::new(
            py,
            NodeIterator {
                inner: result.into_iter(),
            },
        )
    }
}

/// DegreeView for MultiGraph — supports ``len``, ``__getitem__``, iteration.
#[pyclass]
pub(crate) struct MultiGraphDegreeView {
    graph: Py<PyMultiGraph>,
}

#[pymethods]
impl MultiGraphDegreeView {
    fn __len__(&self, py: Python<'_>) -> usize {
        self.graph.borrow(py).inner.node_count()
    }

    fn __getitem__(&self, py: Python<'_>, n: &Bound<'_, PyAny>) -> PyResult<usize> {
        let g = self.graph.borrow(py);
        let canonical = node_key_to_string(py, n)?;
        if !g.inner.has_node(&canonical) {
            return Err(PyKeyError::new_err(format!("{}", n.repr()?)));
        }
        // For multigraphs, degree counts all parallel edges
        Ok(g.inner.degree(&canonical))
    }

    fn __iter__(&self, py: Python<'_>) -> PyResult<Py<NodeIterator>> {
        let g = self.graph.borrow(py);
        let mut result = Vec::new();
        for node in g.inner.nodes_ordered() {
            let py_node = g.py_node_key(py, node);
            let deg: PyObject = g
                .inner
                .degree(node)
                .into_pyobject(py)
                .expect("degree conversion")
                .into_any()
                .unbind();
            let pair = PyTuple::new(py, &[py_node, deg])?;
            result.push(pair.into_any().unbind());
        }
        Py::new(
            py,
            NodeIterator {
                inner: result.into_iter(),
            },
        )
    }
}

#[pymethods]
impl PyGraph {
    /// Create a new Graph.
    ///
    /// Parameters
    /// ----------
    /// incoming_graph_data : optional
    ///     Data to initialize graph. Currently supports another PyGraph.
    /// **attr : keyword arguments
    ///     Graph-level attributes, stored in ``G.graph``.
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
            inner: Graph::strict(),
            node_key_map: HashMap::new(),
            node_py_attrs: HashMap::new(),
            edge_py_attrs: HashMap::new(),
            graph_attrs: graph_attrs.unbind(),
        };

        if let Some(data) = incoming_graph_data {
            // If it's another PyGraph, copy it.
            if let Ok(other) = data.extract::<PyRef<'_, PyGraph>>() {
                for (canonical, py_key) in &other.node_key_map {
                    let rust_attrs = other
                        .node_py_attrs
                        .get(canonical)
                        .map(|attrs| py_dict_to_attr_map(attrs.bind(py)))
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
                    let rust_attrs = py_dict_to_attr_map(attrs.bind(py))?;
                    let _ = g
                        .inner
                        .add_edge_with_attrs(u.clone(), v.clone(), rust_attrs);
                    g.edge_py_attrs
                        .insert((u.clone(), v.clone()), attrs.bind(py).copy()?.unbind());
                }
                g.graph_attrs = other.graph_attrs.bind(py).copy()?.unbind();
            } else if let Ok(iter) = PyIterator::from_object(data) {
                for item in iter {
                    let item = item?;
                    if let Ok(tuple) = item.downcast::<PyTuple>() {
                        let merged = PyDict::new(py);
                        match tuple.len() {
                            2 => {
                                g.add_edge(
                                    py,
                                    &tuple.get_item(0)?,
                                    &tuple.get_item(1)?,
                                    Some(&merged),
                                )?;
                            }
                            3 => {
                                if let Ok(d) = tuple.get_item(2)?.downcast::<PyDict>() {
                                    merged.update(d.as_mapping())?;
                                    g.add_edge(
                                        py,
                                        &tuple.get_item(0)?,
                                        &tuple.get_item(1)?,
                                        Some(&merged),
                                    )?;
                                } else {
                                    g.add_node(py, &item, None)?;
                                }
                            }
                            _ => g.add_node(py, &item, None)?,
                        }
                    } else {
                        g.add_node(py, &item, None)?;
                    }
                }
            }
        }

        Ok(g)
    }

    // ---- Properties ----

    /// Graph-level attribute dictionary.
    #[getter]
    fn graph(&self, py: Python<'_>) -> Py<PyDict> {
        self.graph_attrs.clone_ref(py)
    }

    /// The graph name, stored in ``G.graph['name']``.
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

    /// Returns ``True`` if graph is directed. Always ``False`` for Graph.
    fn is_directed(&self) -> bool {
        false
    }

    /// Returns ``True`` if graph is a multigraph. Always ``False`` for Graph.
    fn is_multigraph(&self) -> bool {
        false
    }

    // ---- Counts ----

    /// Number of nodes in the graph.
    fn number_of_nodes(&self) -> usize {
        self.inner.node_count()
    }

    /// Number of nodes in the graph (alias for ``number_of_nodes``).
    fn order(&self) -> usize {
        self.inner.node_count()
    }

    /// Number of edges in the graph.
    fn number_of_edges(&self) -> usize {
        self.inner.edge_count()
    }

    /// Number of edges, optionally weighted.
    /// When *weight* is given, returns the sum of that edge attribute
    /// (defaulting to 1.0 for edges missing the attribute).
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

    /// Add a single node with optional attributes.
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

        // Build Rust AttrMap from Python kwargs for the inner graph.
        let mut rust_attrs = AttrMap::new();
        let py_dict = self
            .node_py_attrs
            .entry(canonical.clone())
            .or_insert_with(|| PyDict::new(py).unbind());
        if let Some(a) = attr {
            rust_attrs = py_dict_to_attr_map(a)?;
            for (k, v) in a.iter() {
                py_dict.bind(py).set_item(k, v)?;
            }
        }

        self.inner
            .add_node_with_attrs(canonical.clone(), rust_attrs);
        log::debug!(target: "franken_networkx", "add_node: {canonical}");
        Ok(())
    }

    /// Add multiple nodes from an iterable.
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
            // Check if it's a (node, attr_dict) tuple.
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
            // Otherwise, it's just a node key.
            self.add_node(py, &item, attr)?;
        }
        Ok(())
    }

    /// Remove a single node. Raises ``NetworkXError`` if not present.
    fn remove_node(&mut self, py: Python<'_>, n: &Bound<'_, PyAny>) -> PyResult<()> {
        let canonical = node_key_to_string(py, n)?;
        if !self.inner.has_node(&canonical) {
            return Err(NodeNotFound::new_err(format!(
                "The node {} is not in the graph.",
                n.repr()?
            )));
        }
        log::debug!(target: "franken_networkx", "remove_node: {canonical}");

        // surgically remove attributes for incident edges before removing node from inner graph
        if let Some(neighbors) = self.inner.neighbors(&canonical) {
            for nb in neighbors {
                let ek = Self::edge_key(&canonical, nb);
                self.edge_py_attrs.remove(&ek);
            }
        }

        self.inner.remove_node(&canonical);
        self.node_key_map.remove(&canonical);
        self.node_py_attrs.remove(&canonical);
        Ok(())
    }

    /// Remove multiple nodes. Silently skips absent nodes.
    fn remove_nodes_from(&mut self, py: Python<'_>, nodes: &Bound<'_, PyAny>) -> PyResult<()> {
        let iter = PyIterator::from_object(nodes)?;
        for item in iter {
            let item = item?;
            let canonical = node_key_to_string(py, &item)?;
            if self.inner.has_node(&canonical) {
                if let Some(neighbors) = self.inner.neighbors(&canonical) {
                    for nb in neighbors {
                        let ek = Self::edge_key(&canonical, nb);
                        self.edge_py_attrs.remove(&ek);
                    }
                }
                self.inner.remove_node(&canonical);
                self.node_key_map.remove(&canonical);
                self.node_py_attrs.remove(&canonical);
            }
        }
        Ok(())
    }

    // ---- Edge mutation ----

    /// Add an edge between u and v with optional attributes.
    /// Nodes are created automatically if not present.
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

        // Ensure nodes exist in our maps.
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

        // Build Rust AttrMap.
        let mut rust_attrs = AttrMap::new();
        let ek = Self::edge_key(&u_canonical, &v_canonical);
        let py_dict = self
            .edge_py_attrs
            .entry(ek)
            .or_insert_with(|| PyDict::new(py).unbind());
        if let Some(a) = attr {
            rust_attrs = py_dict_to_attr_map(a)?;
            for (k, val) in a.iter() {
                py_dict.bind(py).set_item(k, val)?;
            }
        }

        log::debug!(target: "franken_networkx", "add_edge: {u_canonical} -- {v_canonical}");
        self.inner
            .add_edge_with_attrs(u_canonical, v_canonical, rust_attrs)
            .map_err(|e| NetworkXError::new_err(e.to_string()))
    }

    /// Add edges from an iterable of (u, v) or (u, v, attr_dict) tuples.
    #[pyo3(signature = (ebunch_to_add, **attr))]
    fn add_edges_from(
        &mut self,
        py: Python<'_>,
        ebunch_to_add: &Bound<'_, PyAny>,
        attr: Option<&Bound<'_, PyDict>>,
    ) -> PyResult<()> {
        let has_global_attr = attr.is_some_and(|a| !a.is_empty());
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
            // Fast path: no global attrs and no per-edge attrs.
            if !has_global_attr && len == 2 {
                self.add_edge(py, &u, &v, None)?;
            } else {
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
        }
        Ok(())
    }

    /// Fast batch edge insertion for integer-keyed graphs without attributes.
    ///
    /// Takes a flat list of ``[u0, v0, u1, v1, ...]`` integers and adds all
    /// edges in a tight loop with minimal Python object overhead.
    fn _fast_add_int_edges(&mut self, py: Python<'_>, flat: Vec<i64>) -> PyResult<()> {
        if !flat.len().is_multiple_of(2) {
            return Err(PyValueError::new_err(
                "flat edge list must have even length",
            ));
        }
        let empty_attrs = AttrMap::new();
        for pair in flat.chunks_exact(2) {
            let u = pair[0];
            let v = pair[1];
            let u_s = u.to_string();
            let v_s = v.to_string();

            // Insert node key maps only if new.
            self.node_key_map
                .entry(u_s.clone())
                .or_insert_with(|| unwrap_infallible(u.into_pyobject(py)).into_any().unbind());
            self.node_key_map
                .entry(v_s.clone())
                .or_insert_with(|| unwrap_infallible(v.into_pyobject(py)).into_any().unbind());
            self.node_py_attrs
                .entry(u_s.clone())
                .or_insert_with(|| PyDict::new(py).unbind());
            self.node_py_attrs
                .entry(v_s.clone())
                .or_insert_with(|| PyDict::new(py).unbind());

            let ek = Self::edge_key(&u_s, &v_s);
            self.edge_py_attrs
                .entry(ek)
                .or_insert_with(|| PyDict::new(py).unbind());

            let _ = self
                .inner
                .add_edge_with_attrs(u_s, v_s, empty_attrs.clone());
        }
        Ok(())
    }

    /// Add weighted edges from an iterable of (u, v, weight) triples.
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

    /// Remove edge between u and v. Raises ``NetworkXError`` if not present.
    fn remove_edge(
        &mut self,
        py: Python<'_>,
        u: &Bound<'_, PyAny>,
        v: &Bound<'_, PyAny>,
    ) -> PyResult<()> {
        let u_canonical = node_key_to_string(py, u)?;
        let v_canonical = node_key_to_string(py, v)?;
        log::debug!(target: "franken_networkx", "remove_edge: {u_canonical} -- {v_canonical}");
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

    /// Remove edges from an iterable. Silently skips absent edges.
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

    // ---- Utility methods ----

    /// Remove all nodes and edges.
    fn clear(&mut self, py: Python<'_>) -> PyResult<()> {
        // Rebuild from scratch is simpler and correct.
        self.inner = Graph::strict();
        self.node_key_map.clear();
        self.node_py_attrs.clear();
        self.edge_py_attrs.clear();
        self.graph_attrs = PyDict::new(py).unbind();
        Ok(())
    }

    /// Remove all edges but keep nodes and their attributes.
    fn clear_edges(&mut self) {
        // Remove all edges from inner graph.
        let edges: Vec<(String, String)> = self.edge_py_attrs.keys().cloned().collect();
        for (u, v) in edges {
            self.inner.remove_edge(&u, &v);
        }
        self.edge_py_attrs.clear();
    }

    /// Return True if graph has node n.
    fn has_node(&self, py: Python<'_>, n: &Bound<'_, PyAny>) -> PyResult<bool> {
        let canonical = node_key_to_string(py, n)?;
        Ok(self.inner.has_node(&canonical))
    }

    /// Return True if graph has edge (u, v).
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

    /// Return a list of neighbors of node n.
    fn neighbors(&self, py: Python<'_>, n: &Bound<'_, PyAny>) -> PyResult<Vec<PyObject>> {
        let canonical = node_key_to_string(py, n)?;
        match self.inner.neighbors(&canonical) {
            Some(neighbors) => Ok(neighbors
                .into_iter()
                .map(|nb| self.py_node_key(py, nb))
                .collect()),
            None => Err(NodeNotFound::new_err(format!(
                "The node {} is not in the graph.",
                n.repr()?
            ))),
        }
    }

    /// Return adjacency list as list of (node, [neighbors]) pairs.
    fn adjacency<'py>(&self, py: Python<'py>) -> PyResult<Vec<(PyObject, Vec<PyObject>)>> {
        let nodes = self.inner.nodes_ordered();
        let mut result = Vec::with_capacity(nodes.len());
        for node in nodes {
            let py_node = self.py_node_key(py, node);
            let neighbors = self
                .inner
                .neighbors(node)
                .unwrap_or_default()
                .into_iter()
                .map(|nb| self.py_node_key(py, nb))
                .collect();
            result.push((py_node, neighbors));
        }
        Ok(result)
    }

    // ---- Python special methods ----

    /// Number of nodes (called by ``len(G)``).
    fn __len__(&self) -> usize {
        self.inner.node_count()
    }

    /// Membership test (called by ``n in G``).
    fn __contains__(&self, py: Python<'_>, n: &Bound<'_, PyAny>) -> PyResult<bool> {
        let canonical = node_key_to_string(py, n)?;
        Ok(self.inner.has_node(&canonical))
    }

    /// Iterate over nodes (called by ``for n in G``).
    fn __iter__(&self, py: Python<'_>) -> PyResult<Py<NodeIterator>> {
        let nodes: Vec<PyObject> = self
            .inner
            .nodes_ordered()
            .into_iter()
            .map(|n| self.py_node_key(py, n))
            .collect();
        Py::new(
            py,
            NodeIterator {
                inner: nodes.into_iter(),
            },
        )
    }

    /// Get adjacency dict for node (called by ``G[n]``).
    fn __getitem__(&self, py: Python<'_>, n: &Bound<'_, PyAny>) -> PyResult<Py<PyDict>> {
        let canonical = node_key_to_string(py, n)?;
        if !self.inner.has_node(&canonical) {
            return Err(PyKeyError::new_err(format!("{}", n.repr()?)));
        }
        let neighbors = self.inner.neighbors(&canonical).unwrap_or_default();
        let result = PyDict::new(py);
        for nb in neighbors {
            let py_nb = self.py_node_key(py, nb);
            let ek = Self::edge_key(&canonical, nb);
            let edge_attrs = self
                .edge_py_attrs
                .get(&ek)
                .map_or_else(|| PyDict::new(py).unbind(), |d| d.clone_ref(py));
            result.set_item(py_nb, edge_attrs.bind(py))?;
        }
        Ok(result.unbind())
    }

    fn __str__(&self) -> String {
        format!(
            "Graph with {} nodes and {} edges",
            self.inner.node_count(),
            self.inner.edge_count()
        )
    }

    fn __repr__(&self, py: Python<'_>) -> PyResult<String> {
        let name = self.name(py)?;
        if name.is_empty() {
            Ok(format!(
                "Graph(nodes={}, edges={})",
                self.inner.node_count(),
                self.inner.edge_count()
            ))
        } else {
            Ok(format!(
                "Graph(name='{}', nodes={}, edges={})",
                name,
                self.inner.node_count(),
                self.inner.edge_count()
            ))
        }
    }

    fn __bool__(&self) -> bool {
        // Match NetworkX: bool(G) is True if there are nodes.
        self.inner.node_count() > 0
    }

    // ---- Graph utility methods ----

    /// Return a deep copy of the graph.
    fn copy(&self, py: Python<'_>) -> PyResult<Self> {
        let mut new_graph = Self {
            inner: Graph::strict(),
            node_key_map: HashMap::new(),
            node_py_attrs: HashMap::new(),
            edge_py_attrs: HashMap::new(),
            graph_attrs: self.graph_attrs.bind(py).copy()?.unbind(),
        };
        // Copy nodes
        for (canonical, py_key) in &self.node_key_map {
            let rust_attrs = self
                .node_py_attrs
                .get(canonical)
                .map(|attrs| py_dict_to_attr_map(attrs.bind(py)))
                .transpose()?
                .unwrap_or_default();
            new_graph
                .inner
                .add_node_with_attrs(canonical.clone(), rust_attrs);
            new_graph
                .node_key_map
                .insert(canonical.clone(), py_key.clone_ref(py));
            if let Some(attrs) = self.node_py_attrs.get(canonical) {
                new_graph
                    .node_py_attrs
                    .insert(canonical.clone(), attrs.bind(py).copy()?.unbind());
            }
        }
        // Copy edges
        for ((u, v), attrs) in &self.edge_py_attrs {
            let rust_attrs = py_dict_to_attr_map(attrs.bind(py))?;
            let _ = new_graph
                .inner
                .add_edge_with_attrs(u.clone(), v.clone(), rust_attrs);
            new_graph
                .edge_py_attrs
                .insert((u.clone(), v.clone()), attrs.bind(py).copy()?.unbind());
        }
        Ok(new_graph)
    }

    /// Return a subgraph view containing only the specified nodes.
    ///
    /// Returns a new graph (not a view) with the specified nodes and all
    /// edges between them. Node and edge attributes are copied.
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
            inner: Graph::strict(),
            node_key_map: HashMap::new(),
            node_py_attrs: HashMap::new(),
            edge_py_attrs: HashMap::new(),
            graph_attrs: self.graph_attrs.bind(py).copy()?.unbind(),
        };

        // Add kept nodes
        for canonical in &keep {
            let rust_attrs = self
                .node_py_attrs
                .get(canonical)
                .map(|attrs| py_dict_to_attr_map(attrs.bind(py)))
                .transpose()?
                .unwrap_or_default();
            new_graph
                .inner
                .add_node_with_attrs(canonical.clone(), rust_attrs);
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

        // Add edges where both endpoints are in the subgraph
        for ((u, v), attrs) in &self.edge_py_attrs {
            if keep.contains(u) && keep.contains(v) {
                let rust_attrs = py_dict_to_attr_map(attrs.bind(py))?;
                let _ = new_graph
                    .inner
                    .add_edge_with_attrs(u.clone(), v.clone(), rust_attrs);
                new_graph
                    .edge_py_attrs
                    .insert((u.clone(), v.clone()), attrs.bind(py).copy()?.unbind());
            }
        }

        Ok(new_graph)
    }

    /// Return a subgraph containing only the specified edges.
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
            inner: Graph::strict(),
            node_key_map: HashMap::new(),
            node_py_attrs: HashMap::new(),
            edge_py_attrs: HashMap::new(),
            graph_attrs: self.graph_attrs.bind(py).copy()?.unbind(),
        };

        // Collect nodes from kept edges
        let mut nodes_needed: std::collections::HashSet<String> = std::collections::HashSet::new();
        for (u, v) in &keep_edges {
            nodes_needed.insert(u.clone());
            nodes_needed.insert(v.clone());
        }

        // Add nodes
        for canonical in &nodes_needed {
            let rust_attrs = self
                .node_py_attrs
                .get(canonical)
                .map(|attrs| py_dict_to_attr_map(attrs.bind(py)))
                .transpose()?
                .unwrap_or_default();
            new_graph
                .inner
                .add_node_with_attrs(canonical.clone(), rust_attrs);
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

        // Add edges
        for (u, v) in &keep_edges {
            let rust_attrs = self
                .edge_py_attrs
                .get(&(u.clone(), v.clone()))
                .map(|attrs| py_dict_to_attr_map(attrs.bind(py)))
                .transpose()?
                .unwrap_or_default();
            let _ = new_graph
                .inner
                .add_edge_with_attrs(u.clone(), v.clone(), rust_attrs);
            if let Some(attrs) = self.edge_py_attrs.get(&(u.clone(), v.clone())) {
                new_graph
                    .edge_py_attrs
                    .insert((u.clone(), v.clone()), attrs.bind(py).copy()?.unbind());
            }
        }

        Ok(new_graph)
    }

    /// Return an undirected copy of the graph (no-op for Graph).
    fn to_undirected(&self, py: Python<'_>) -> PyResult<Self> {
        self.copy(py)
    }

    /// Return a directed copy of the graph.
    fn to_directed(&self, py: Python<'_>) -> PyResult<Py<crate::digraph::PyDiGraph>> {
        let mut dg = crate::digraph::PyDiGraph::new_empty(py)?;

        for (canonical, py_key) in &self.node_key_map {
            let rust_attrs = self
                .node_py_attrs
                .get(canonical)
                .map(|attrs| py_dict_to_attr_map(attrs.bind(py)))
                .transpose()?
                .unwrap_or_default();
            dg.inner.add_node_with_attrs(canonical.clone(), rust_attrs);
            dg.node_key_map
                .insert(canonical.clone(), py_key.clone_ref(py));
            if let Some(attrs) = self.node_py_attrs.get(canonical) {
                dg.node_py_attrs
                    .insert(canonical.clone(), attrs.bind(py).copy()?.unbind());
            }
        }

        for edge in self.inner.edges_ordered() {
            let u = &edge.left;
            let v = &edge.right;

            let rust_attrs = edge.attrs.clone();
            let mut py_attrs_copy = None;
            let ek = PyGraph::edge_key(u, v);

            if let Some(py_attrs) = self.edge_py_attrs.get(&ek) {
                py_attrs_copy = Some(py_attrs.bind(py).copy()?.unbind());
            }

            dg.inner
                .add_edge_with_attrs(u.clone(), v.clone(), rust_attrs.clone())
                .map_err(|e| crate::NetworkXError::new_err(e.to_string()))?;
            if u != v {
                dg.inner
                    .add_edge_with_attrs(v.clone(), u.clone(), rust_attrs)
                    .map_err(|e| crate::NetworkXError::new_err(e.to_string()))?;
            }

            if let Some(pa) = py_attrs_copy {
                dg.edge_py_attrs
                    .insert((u.clone(), v.clone()), pa.clone_ref(py));
                if u != v {
                    dg.edge_py_attrs.insert((v.clone(), u.clone()), pa);
                }
            }
        }

        dg.graph_attrs = self.graph_attrs.bind(py).copy()?.unbind();
        Py::new(py, dg)
    }

    /// Update the graph from edges and/or nodes.
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

    /// Return the number of edges between two nodes, or total edges.
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
        let ek = Self::edge_key(&u_c, &v_c);
        Ok(self.edge_py_attrs.get(&ek).map_or_else(
            || default.unwrap_or_else(|| py.None()),
            |d| d.clone_ref(py).into_any(),
        ))
    }

    /// ``G.nodes`` — a `NodeView` of the graph's nodes. Supports ``len``, ``in``,
    /// iteration, and ``G.nodes(data=True)``.
    #[getter]
    fn nodes(slf: PyRef<'_, Self>) -> PyResult<Py<views::NodeView>> {
        let py = slf.py();
        let graph_py: Py<PyGraph> = Py::from(slf);
        views::new_node_view(py, graph_py)
    }

    /// ``G.edges`` — an `EdgeView` of the graph's edges. Supports ``len``, ``in``,
    /// iteration, and ``G.edges(data=True)``.
    #[getter]
    fn edges(slf: PyRef<'_, Self>) -> PyResult<Py<views::EdgeView>> {
        let py = slf.py();
        let graph_py: Py<PyGraph> = Py::from(slf);
        views::new_edge_view(py, graph_py)
    }

    /// ``G.adj`` — an `AdjacencyView` of the graph. ``G.adj[n]`` returns a dict
    /// of neighbors and edge attributes.
    #[getter]
    fn adj(slf: PyRef<'_, Self>) -> PyResult<Py<views::AdjacencyView>> {
        let py = slf.py();
        let graph_py: Py<PyGraph> = Py::from(slf);
        views::new_adjacency_view(py, graph_py)
    }

    /// ``G.degree`` — a `DegreeView` of node degrees. ``G.degree[n]`` returns the
    /// degree of node n.
    #[getter]
    fn degree(slf: PyRef<'_, Self>) -> PyResult<Py<views::DegreeView>> {
        let py = slf.py();
        let graph_py: Py<PyGraph> = Py::from(slf);
        views::new_degree_view(py, graph_py)
    }

    /// Equality check — two graphs are equal if they have the same nodes, edges, and attributes.
    fn __eq__(&self, py: Python<'_>, other: &Bound<'_, PyAny>) -> PyResult<bool> {
        let other = match other.extract::<PyRef<'_, PyGraph>>() {
            Ok(g) => g,
            Err(_) => return Ok(false),
        };

        // Compare node sets
        let my_nodes = self.inner.nodes_ordered();
        let other_nodes = other.inner.nodes_ordered();
        if my_nodes != other_nodes {
            return Ok(false);
        }

        // Compare node attributes
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

        // Compare edge sets and attributes
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

        // Compare graph attributes
        self.graph_attrs.bind(py).eq(other.graph_attrs.bind(py))
    }

    /// Support ``copy.copy(G)`` — returns a deep copy.
    fn __copy__(&self, py: Python<'_>) -> PyResult<Self> {
        self.copy(py)
    }

    /// Support ``copy.deepcopy(G)`` — returns a deep copy.
    #[pyo3(signature = (_memo=None))]
    fn __deepcopy__(&self, py: Python<'_>, _memo: Option<&Bound<'_, PyAny>>) -> PyResult<Self> {
        self.copy(py)
    }

    // ---- Serialization (pickle) ----

    fn __getstate__(&self, py: Python<'_>) -> PyResult<PyObject> {
        let state = PyDict::new(py);
        // Store nodes as list of (key, attrs) tuples.
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

        // Store edges as list of (u, v, attrs) tuples.
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
        self.inner = Graph::strict();
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

pub(crate) fn unwrap_infallible<T>(result: Result<T, Infallible>) -> T {
    result.unwrap_or_else(|never| match never {})
}

// ---------------------------------------------------------------------------
// Node iterator — returned by ``for n in G``.
// ---------------------------------------------------------------------------

#[pyclass]
struct NodeIterator {
    inner: std::vec::IntoIter<PyObject>,
}

#[pymethods]
impl NodeIterator {
    fn __iter__(slf: PyRef<'_, Self>) -> PyRef<'_, Self> {
        slf
    }

    fn __next__(mut slf: PyRefMut<'_, Self>) -> Option<PyObject> {
        slf.inner.next()
    }
}

// ---------------------------------------------------------------------------
// Module initialization.
// ---------------------------------------------------------------------------

/// Module initialization — entry point when ``import franken_networkx._fnx`` runs.
#[pymodule]
fn _fnx(m: &Bound<'_, PyModule>) -> PyResult<()> {
    // Bridge Rust log macros to Python's logging module under "franken_networkx".
    pyo3_log::init();

    m.add("__version__", env!("CARGO_PKG_VERSION"))?;

    // Graph class
    m.add_class::<PyGraph>()?;
    m.add_class::<PyMultiGraph>()?;
    m.add_class::<NodeIterator>()?;

    // DiGraph class + views
    digraph::register_digraph_classes(m)?;

    // Undirected view classes
    m.add_class::<views::NodeView>()?;
    m.add_class::<views::EdgeView>()?;
    m.add_class::<views::DegreeView>()?;
    m.add_class::<views::AdjacencyView>()?;

    // MultiGraph view classes
    m.add_class::<MultiGraphNodeView>()?;
    m.add_class::<MultiGraphEdgeView>()?;
    m.add_class::<MultiGraphDegreeView>()?;

    // Algorithm functions
    algorithms::register(m)?;

    // Generator functions
    generators::register(m)?;

    // Read/write functions
    readwrite::register(m)?;

    // Exception hierarchy
    m.add("NetworkXError", m.py().get_type::<NetworkXError>())?;
    m.add(
        "NetworkXPointlessConcept",
        m.py().get_type::<NetworkXPointlessConcept>(),
    )?;
    m.add(
        "NetworkXAlgorithmError",
        m.py().get_type::<NetworkXAlgorithmError>(),
    )?;
    m.add(
        "NetworkXUnfeasible",
        m.py().get_type::<NetworkXUnfeasible>(),
    )?;
    m.add("NetworkXNoPath", m.py().get_type::<NetworkXNoPath>())?;
    m.add("NetworkXNoCycle", m.py().get_type::<NetworkXNoCycle>())?;
    m.add("NetworkXUnbounded", m.py().get_type::<NetworkXUnbounded>())?;
    m.add(
        "NetworkXNotImplemented",
        m.py().get_type::<NetworkXNotImplemented>(),
    )?;
    m.add("NotATree", m.py().get_type::<NotATree>())?;
    m.add("NodeNotFound", m.py().get_type::<NodeNotFound>())?;
    m.add("HasACycle", m.py().get_type::<HasACycle>())?;
    m.add(
        "PowerIterationFailedConvergence",
        m.py().get_type::<PowerIterationFailedConvergence>(),
    )?;

    Ok(())
}
