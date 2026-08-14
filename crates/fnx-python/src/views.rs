//! NetworkX-compatible view objects (NodeView, EdgeView, DegreeView).
//!
//! These views provide dict-like read access to graph data and reflect
//! the current state of the graph (they are "live" views backed by Py<PyGraph>).

use crate::{
    NodeIterator, NodeLookupCache, PyGraph, PyObject, attr_map_to_pydict, node_key_to_string,
};
use arrayvec::ArrayString;
use pyo3::exceptions::{PyKeyError, PyRuntimeError};
use pyo3::gc::{PyTraverseError, PyVisit};
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyIterator, PyModule, PyTuple};

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
    lookup_cache: NodeLookupCache,
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
    fn __traverse__(&self, visit: PyVisit<'_>) -> Result<(), PyTraverseError> {
        visit.call(&self.graph)?;
        self.lookup_cache.traverse(visit.clone())?;
        if let NodeViewData::AttrWithDefault(_, default) = &self.data {
            visit.call(default)?;
        }
        Ok(())
    }

    fn __len__(&self, py: Python<'_>) -> usize {
        let g = self.graph.borrow(py);
        g.inner.node_count()
    }

    fn __contains__(&self, py: Python<'_>, n: &Bound<'_, PyAny>) -> PyResult<bool> {
        // br-r37-c1-m7xek: keep NetworkX's unhashable-node TypeError inside
        // the native slot so ordinary Graph NodeView membership no longer
        // needs a Python hash+delegate wrapper on every present/missing probe.
        //
        // br-r37-c1-ey6ob: but an EXACT `str` cannot fail to hash, so for the
        // dominant node-key type this call only proved something the type
        // system already guarantees. It was the single largest item in the
        // probe — `PyObject_Hash` at 21.90% of 568 Ir/call (callgrind,
        // --toggle-collect on this pymethod so the module import is excluded).
        // The result was discarded either way; nothing downstream reads it.
        //
        // EXACT type only. A `str` SUBCLASS may override `__hash__` and raise,
        // and nx's `n in self._nodes` would call it, so subclasses keep the
        // probe. Every non-str key keeps it too — that is where hashing
        // genuinely fails (a list, or a tuple containing one).
        if !n.is_exact_instance_of::<pyo3::types::PyString>() {
            n.hash()?;
        }
        // br-r37-c1-ey6ob: probe with the BORROWED canonical key. This is a
        // read-only membership test, so the owned `String` that
        // `node_key_to_string` returns existed only to be hashed and dropped —
        // one malloc/free per `n in G.nodes()` against nx's zero. The borrowed
        // form (br-r37-c1-oe93x) writes the identical bytes into a stack buffer
        // for short `str` keys and falls back to the owned build for everything
        // else, so the canonical is unchanged on every key shape.
        crate::with_node_key_str(py, n, |canonical| {
            self.graph.borrow(py).inner.has_node(canonical)
        })
    }

    fn __iter__(&self, py: Python<'_>) -> PyResult<PyObject> {
        // br-r37-c1-spg9n: the NoData path (list(G.nodes()) / for n in G.nodes())
        // serves the SAME cached node_iter_mirror dict that PyGraph.__iter__ uses
        // -> a ``dict_keyiterator`` (matching nx's ``iter(self._nodes)``) instead
        // of rebuilding a Vec<PyObject> of every node display key per call. Was
        // ~10x slower than nx AND the wrong iterator type (NodeViewIterator); the
        // mirror gives both parity speed and nx's iterator type + its native
        // "changed size during iteration" semantics.
        if matches!(self.data, NodeViewData::NoData) {
            let mirror = self.graph.borrow(py).node_iter_mirror_or_init(py)?;
            return Ok(mirror.bind(py).call_method0("__iter__")?.unbind());
        }
        let nodes: Vec<String> = {
            let g = self.graph.borrow(py);
            g.inner
                .nodes_ordered()
                .into_iter()
                .map(str::to_owned)
                .collect()
        };
        let items: Vec<PyObject> = match &self.data {
            NodeViewData::NoData => unreachable!("NoData handled above"),
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
        Ok(Py::new(
            py,
            NodeViewIterator {
                inner: items.into_iter(),
                graph: Some(self.graph.clone_ref(py)),
                expected_count: Some(nodes.len()),
                expected_seq: Some(expected_seq),
            },
        )?
        .into_any())
    }

    fn __getitem__(&self, py: Python<'_>, n: &Bound<'_, PyAny>) -> PyResult<Py<PyDict>> {
        let nodes_seq = self.graph.borrow(py).nodes_seq;
        if let Some(attrs) = self.lookup_cache.get(py, nodes_seq, n)? {
            return Ok(attrs);
        }
        if self.lookup_cache.is_known_missing(py, n)? {
            return Err(crate::missing_key_error(n));
        }
        // br-r37-c1-ey6ob: borrowed canonical probe (see `__contains__`). The
        // graph borrow now opens INSIDE the closure, i.e. AFTER canonicalization
        // rather than around it — `node_key_to_string` can call back into Python
        // (`repr`) for exotic keys, and holding `borrow_mut` across that is what
        // turns a re-entrant key into a `BorrowMutError`.
        let found = crate::with_node_key_str(py, n, |canonical| {
            let mut g = self.graph.borrow_mut(py);
            if !g.inner.has_node(canonical) {
                return None;
            }
            let public_key = g.py_node_key(py, canonical);
            let attrs = g.materialize_node_py_attrs(py, canonical);
            Some((public_key, attrs))
        })?;
        let Some((public_key, attrs)) = found else {
            self.lookup_cache.insert_missing(py, n)?;
            return Err(crate::missing_key_error(n));
        };
        self.lookup_cache.insert(py, public_key.bind(py), &attrs)?;
        Ok(attrs)
    }

    #[pyo3(signature = (n, default=None))]
    fn get(
        &self,
        py: Python<'_>,
        n: &Bound<'_, PyAny>,
        default: Option<PyObject>,
    ) -> PyResult<PyObject> {
        // br-r37-c1-ey6ob: borrowed canonical probe (see `__contains__`).
        let found = crate::with_node_key_str(py, n, |canonical| {
            let mut g = self.graph.borrow_mut(py);
            if !g.inner.has_node(canonical) {
                return None;
            }
            Some(g.materialize_node_py_attrs(py, canonical))
        })?;
        Ok(match found {
            Some(attrs) => attrs.into_any(),
            None => default.unwrap_or_else(|| py.None()),
        })
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
                lookup_cache: NodeLookupCache::new(py),
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
    fn items(&self, py: Python<'_>) -> PyResult<PyObject> {
        let mut g = self.graph.borrow_mut(py);
        g.node_data_items_view(py)
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
                lookup_cache: NodeLookupCache::new(py),
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
    node_key_map: &crate::PyNodeKeyMap<String, PyObject>,
    lazy_int_node_stop: i64,
    canonical: &str,
) -> PyObject {
    if let Some(obj) = node_key_map.get(canonical) {
        return obj.clone_ref(py);
    }
    if let Ok(value) = canonical.parse::<i64>()
        && (0..lazy_int_node_stop).contains(&value)
    {
        return crate::unwrap_infallible(value.into_pyobject(py))
            .into_any()
            .unbind();
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
    let adj_py_keys = &g.adj_py_keys; // br-r37-c1-z6uka
    let lazy_stop = g.lazy_int_node_stop;
    let mut items = Vec::with_capacity(inner.edge_count());
    // br-r37-c1-2a00r: index fast path — build the node-index -> Python key
    // object Vec ONCE (a node of degree d was hashed via edgeview_py_node_key
    // ~d times across its incident edges) and walk edges by index, so each
    // endpoint is an O(1) Vec index + incref with no canonical-String hash.
    // Gated on adj_py_keys being empty: when non-empty (non-uniform
    // adjacency-row key objects, br-r37-c1-z6uka) the neighbor's display object
    // can differ from the node's own key, so fall through to the exact
    // per-edge path below. (The edge_py_attrs `edge_key` String probe is
    // unchanged — re-keying that map by index is a separate, larger lever.)
    if adj_py_keys.is_empty() {
        let nodes: Vec<&str> = inner.nodes_ordered();
        let key_vec: Vec<PyObject> = nodes
            .iter()
            .map(|n| edgeview_py_node_key(py, node_key_map, lazy_stop, n))
            .collect();
        for (u, v) in inner.edges_ordered_indices() {
            let left = nodes[u];
            let right = nodes[v];
            if let Some(ns) = node_filter
                && !(ns.contains(left) || ns.contains(right))
            {
                continue;
            }
            let dict = edge_py_attrs
                .entry(PyGraph::edge_key(left, right))
                .or_insert_with(|| match inner.edge_attrs_by_indices(u, v) {
                    Some(attrs) => attr_map_to_pydict(py, attrs)
                        .expect("stored string-keyed edge attrs must convert to Python"),
                    None => PyDict::new(py).unbind(),
                })
                .clone_ref(py)
                .into_any();
            items.push(tuple_object(
                py,
                &[key_vec[u].clone_ref(py), key_vec[v].clone_ref(py), dict],
            )?);
        }
        return Ok(items);
    }
    for (left, right, attrs) in inner.edges_ordered_borrowed() {
        if let Some(ns) = node_filter
            && !(ns.contains(left) || ns.contains(right))
        {
            continue;
        }
        let py_u = edgeview_py_node_key(py, node_key_map, lazy_stop, left);
        // br-r37-c1-z6uka: the v side of an edge tuple is the ADJACENCY-ROW
        // object of left's row (nx EdgeView walks _adj rows).
        let py_v = if !adj_py_keys.is_empty()
            && let Some(obj) = adj_py_keys.get(&(left.to_owned(), right.to_owned()))
        {
            obj.clone_ref(py)
        } else {
            edgeview_py_node_key(py, node_key_map, lazy_stop, right)
        };
        let dict = edge_py_attrs
            .entry(PyGraph::edge_key(left, right))
            .or_insert_with(|| {
                attr_map_to_pydict(py, attrs)
                    .expect("stored string-keyed edge attrs must convert to Python")
            })
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
                let py_v = g.py_adj_key(py, left, right); // br-r37-c1-z6uka
                tuple_object(py, &[py_u, py_v])
            })
            .collect()
    }
}

#[pymethods]
impl EdgeView {
    fn __traverse__(&self, visit: PyVisit<'_>) -> Result<(), PyTraverseError> {
        visit.call(&self.graph)?;
        if let NodeViewData::AttrWithDefault(_, default) = &self.data {
            visit.call(default)?;
        }
        Ok(())
    }

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
        // br-r37-c1-ey6ob: `(u, v) in G.edges()` is a read-only probe, so both
        // endpoint canonicals are borrowed out of stack buffers instead of being
        // heap-allocated to be hashed once and dropped — two mallocs per probe.
        // Same two-buffer shape as `_fnx_edge_attr_dict_get` (lib.rs).
        // br-r37-c1-ey6ob: BORROWED tuple items. `get_item` hands back an owned
        // `Bound`, so each endpoint cost an incref on the way in and a decref on
        // the way out — `_Py_DecRef` and `PyTuple_GetItem` together are 4.81% of
        // this probe's 1040 Ir (callgrind, --toggle-collect on this pymethod).
        // The endpoints are only read, and the tuple outlives both borrows, so
        // the refcount round-trip bought nothing.
        let u_item = tuple.get_borrowed_item(0)?;
        let v_item = tuple.get_borrowed_item(1)?;
        let mut u_buf = ArrayString::new();
        let mut v_buf = ArrayString::new();
        let u = crate::canonical_node_key_in(py, &u_item, &mut u_buf)?;
        let v = crate::canonical_node_key_in(py, &v_item, &mut v_buf)?;
        let g = self.graph.borrow(py);
        Ok(g.inner.has_edge(u.as_str(), v.as_str()))
    }

    fn __iter__(&self, py: Python<'_>) -> PyResult<Py<NodeViewIterator>> {
        // br-r37-c1-2a00r: NoData fast path — `list(G.edges())` was ~2.4x slower
        // than nx because each edge endpoint went through py_node_key/py_adj_key,
        // hashing the canonical String in a HashMap<String, PyObject> per node
        // per edge. Iterate edges by node INDEX (edges_ordered_indices, same
        // node-major order as edges_ordered_borrowed) and clone the per-index
        // cached Python node-key object directly (O(1) incref, no string hash).
        // Gated on adj_py_keys being empty: when non-empty (non-uniform
        // adjacency-row key objects, br-r37-c1-z6uka) the neighbor's display
        // object can differ from the node's own key, so fall through to the
        // exact per-edge py_adj_key path below.
        // Covers NoData (`G.edges()`), Attr (`data="w"`) and AttrWithDefault —
        // every non-AllData variant. AllData has its own one-pass helper
        // (edge_alldata_items) which carries the same index path.
        if !matches!(self.data, NodeViewData::AllData) {
            let g = self.graph.borrow(py);
            if g.adj_py_keys.is_empty() {
                let node_count = g.inner.node_count();
                let nodes_seq = g.nodes_seq;
                let nodes: Vec<&str> = g.inner.nodes_ordered();
                let keys = g.cached_node_key_vec(py);
                let items: Vec<PyObject> = g
                    .inner
                    .edges_ordered_indices()
                    .into_iter()
                    .map(|(u, v)| {
                        let py_u = keys[u].clone_ref(py);
                        let py_v = keys[v].clone_ref(py);
                        match &self.data {
                            NodeViewData::NoData => tuple_object(py, &[py_u, py_v]),
                            NodeViewData::Attr(attr_name) => {
                                let val = g
                                    .edge_attr_py_value(py, nodes[u], nodes[v], attr_name)?
                                    .unwrap_or_else(|| py.None());
                                tuple_object(py, &[py_u, py_v, val])
                            }
                            NodeViewData::AttrWithDefault(attr_name, def_val) => {
                                let val = g
                                    .edge_attr_py_value(py, nodes[u], nodes[v], attr_name)?
                                    .unwrap_or_else(|| def_val.clone_ref(py));
                                tuple_object(py, &[py_u, py_v, val])
                            }
                            NodeViewData::AllData => unreachable!(),
                        }
                    })
                    .collect::<PyResult<Vec<_>>>()?;
                return Py::new(
                    py,
                    NodeViewIterator {
                        inner: items.into_iter(),
                        graph: Some(self.graph.clone_ref(py)),
                        expected_count: Some(node_count),
                        expected_seq: Some(nodes_seq),
                    },
                );
            }
        }
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
                        let py_v = g.py_adj_key(py, left, right); // br-r37-c1-z6uka
                        // br-r37-c1-7gxek: the canonical edge_key + edge_py_attrs lookup
                        // are only needed by the data-bearing variants. Computing them
                        // eagerly cost 2 String clones + a hashmap probe per edge on the
                        // plain `G.edges()` (NoData) hot path where they are discarded;
                        // resolve them lazily inside the branches that use them.
                        match &self.data {
                            NodeViewData::NoData => tuple_object(py, &[py_u, py_v]),
                            NodeViewData::Attr(attr_name) => {
                                let val = g
                                    .edge_attr_py_value(py, left, right, attr_name)?
                                    .unwrap_or_else(|| py.None());
                                tuple_object(py, &[py_u, py_v, val])
                            }
                            NodeViewData::AttrWithDefault(attr_name, def_val) => {
                                let val = g
                                    .edge_attr_py_value(py, left, right, attr_name)?
                                    .unwrap_or_else(|| def_val.clone_ref(py));
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
        // br-r37-c1-ey6ob: borrowed endpoint canonicals (see `__contains__`).
        // `materialize_edge_py_attrs` already takes `&str`, and the KeyError text
        // is built from the same canonical bytes, so the message is unchanged.
        let u_item = tuple.get_item(0)?;
        let v_item = tuple.get_item(1)?;
        let mut u_buf = ArrayString::new();
        let mut v_buf = ArrayString::new();
        let u = crate::canonical_node_key_in(py, &u_item, &mut u_buf)?;
        let v = crate::canonical_node_key_in(py, &v_item, &mut v_buf)?;
        let (u, v) = (u.as_str(), v.as_str());
        let mut g = self.graph.borrow_mut(py);
        if !g.inner.has_edge(u, v) {
            return Err(PyKeyError::new_err(format!("({u}, {v})")));
        }
        g.mark_edges_dirty();
        Ok(g.materialize_edge_py_attrs(py, u, v))
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
                        let py_v = g.py_adj_key(py, left, right); // br-r37-c1-z6uka
                        match &view_data {
                            NodeViewData::NoData => tuple_object(py, &[py_u, py_v]),
                            NodeViewData::Attr(attr_name) => {
                                let val = g
                                    .edge_attr_py_value(py, left, right, attr_name)?
                                    .unwrap_or_else(|| py.None());
                                tuple_object(py, &[py_u, py_v, val])
                            }
                            NodeViewData::AttrWithDefault(attr_name, def_val) => {
                                let val = g
                                    .edge_attr_py_value(py, left, right, attr_name)?
                                    .unwrap_or_else(|| def_val.clone_ref(py));
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
    fn __traverse__(&self, visit: PyVisit<'_>) -> Result<(), PyTraverseError> {
        visit.call(&self.graph)
    }

    fn __len__(&self, py: Python<'_>) -> usize {
        let g = self.graph.borrow(py);
        g.inner.node_count()
    }

    fn __iter__(&self, py: Python<'_>) -> PyResult<Py<NodeViewIterator>> {
        let g = self.graph.borrow(py);
        // br-r37-c1-degidx: walk by index — degree_by_index is O(1)
        // with no String hashing (the &str degree path cost 2 hashes
        // per node). Node names still come from the ordered list.
        let names = g.inner.nodes_ordered();
        let items: Vec<PyObject> = names
            .iter()
            .enumerate()
            .map(|(i, n)| {
                let py_key = g.py_node_key(py, n);
                let py_degree = g
                    .inner
                    .degree_by_index(i)
                    .into_pyobject(py)?
                    .into_any()
                    .unbind();
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
        // br-r37-c1-ey6ob: borrowed canonical probe (see NodeView::__contains__).
        // `G.degree[n]` reads a degree and never inserts, so the owned canonical
        // was a malloc/free per call.
        let degree = crate::with_node_key_str(py, n, |canonical| {
            let g = self.graph.borrow(py);
            g.inner
                .has_node(canonical)
                .then(|| g.inner.degree(canonical))
        })?;
        degree.ok_or_else(|| match n.repr() {
            Ok(repr) => {
                crate::NodeNotFound::new_err(format!("The node {repr} is not in the graph."))
            }
            Err(err) => err,
        })
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

        // Try as single node first.
        // br-r37-c1-ey6ob: borrowed canonical probe. This arm runs on EVERY
        // `G.degree(x)` call, including the ones where `x` turns out to be an
        // nbunch iterable and the owned canonical was built and thrown away.
        let mut nb_buf = ArrayString::new();
        if let Ok(canonical) = crate::canonical_node_key_in(py, nb, &mut nb_buf)
            && g.inner.has_node(canonical.as_str())
        {
            let deg = g.inner.degree(canonical.as_str());
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

/// The owning-graph handle of a view has been dropped by CPython's cyclic
/// garbage collector (``__clear__``). A cleared view is reachable only from
/// inside the collector's teardown of the cycle it belonged to, so this is a
/// defined answer for the fallible methods rather than a state user code can
/// observe. (br-r37-c1-5gam7)
pub(crate) fn cleared_view_error() -> PyErr {
    PyRuntimeError::new_err("view's graph reference was cleared by the garbage collector")
}

/// A view of the graph's adjacency structure. ``G.adj[n]`` returns a dict of neighbors.
///
/// `subclass` is what lets the Python `AdjacencyView` inherit from this class so
/// `len(G.adj)` resolves to the C slot below instead of a Python frame
/// (br-r37-c1-5gam7). Everything else about `G.adj` keeps coming from the Python
/// class, which sits after this one in the MRO.
#[pyclass(module = "franken_networkx", subclass)]
pub struct AdjacencyView {
    /// `None` once `__clear__` has run — see [`cleared_view_error`]. The handle
    /// must be nullable so `tp_clear` can break the ``graph -> view -> graph``
    /// reference cycle, which is invisible to CPython without `__traverse__`
    /// and unbreakable without `__clear__` (br-r37-c1-5gam7).
    graph: Option<Py<PyGraph>>,
}

impl AdjacencyView {
    fn graph(&self) -> PyResult<&Py<PyGraph>> {
        self.graph.as_ref().ok_or_else(cleared_view_error)
    }
}

#[pymethods]
impl AdjacencyView {
    /// Constructible from Python so the MRO subclass built in
    /// `franken_networkx/__init__.py` can call `__new__` with the owning graph
    /// (br-r37-c1-5gam7). The subclass supplies its own `__init__`, so this only
    /// has to install the handle the C slots read.
    #[new]
    fn py_new(graph: Py<PyGraph>) -> Self {
        Self { graph: Some(graph) }
    }

    fn __traverse__(&self, visit: PyVisit<'_>) -> Result<(), PyTraverseError> {
        visit.call(&self.graph)
    }

    fn __clear__(&mut self) {
        self.graph = None;
    }

    fn __len__(&self, py: Python<'_>) -> usize {
        self.graph
            .as_ref()
            .map_or(0, |graph| graph.borrow(py).inner.node_count())
    }

    fn __contains__(&self, py: Python<'_>, n: &Bound<'_, PyAny>) -> PyResult<bool> {
        // br-r37-c1-ey6ob: borrowed canonical probe (see NodeView::__contains__).
        let graph = self.graph()?;
        crate::with_node_key_str(py, n, |canonical| {
            graph.borrow(py).inner.has_node(canonical)
        })
    }

    fn __getitem__(&self, py: Python<'_>, n: &Bound<'_, PyAny>) -> PyResult<Py<AtlasView>> {
        // br-r37-c1-njs5g: `G.adj[u]` returns the same lazy AtlasView as `G[u]`
        // (was an eager O(degree) PyDict materialisation).
        let graph = self.graph()?;
        let canonical = node_key_to_string(py, n)?;
        if !graph.borrow(py).inner.has_node(&canonical) {
            return Err(crate::missing_key_error(n));
        }
        Py::new(py, AtlasView::new(graph.clone_ref(py), canonical))
    }

    fn __iter__(&self, py: Python<'_>) -> PyResult<Py<NodeIterator>> {
        let g = self.graph()?.borrow(py);
        let nodes: Vec<PyObject> = g
            .inner
            .nodes_ordered()
            .iter()
            .map(|n| g.py_node_key(py, n))
            .collect();
        Py::new(py, NodeIterator::unguarded(nodes))
    }

    fn __repr__(&self, py: Python<'_>) -> String {
        match &self.graph {
            Some(graph) => format!(
                "AdjacencyView({} nodes)",
                graph.borrow(py).inner.node_count()
            ),
            None => "AdjacencyView(<cleared>)".to_owned(),
        }
    }

    fn __bool__(&self, py: Python<'_>) -> bool {
        self.graph
            .as_ref()
            .is_some_and(|graph| graph.borrow(py).inner.node_count() > 0)
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
    /// `None` once `__clear__` has run — see [`cleared_view_error`].
    /// `AdjacencyView::__getitem__` hands out an AtlasView holding its OWN
    /// clone of the graph handle, so this view is on the same cycle and needs
    /// the same treatment (br-r37-c1-5gam7).
    graph: Option<Py<PyGraph>>,
    node: String,
    /// The persistent row mirror once a mapping-wide operation has requested
    /// it. The graph mutators update this dictionary in place; retaining it
    /// also gives a captured row NetworkX's detached-row behaviour after its
    /// owner node is removed.
    row: Option<Py<PyDict>>,
}

impl AtlasView {
    pub(crate) fn new(graph: Py<PyGraph>, node: String) -> Self {
        Self {
            graph: Some(graph),
            node,
            row: None,
        }
    }

    fn graph(&self) -> PyResult<&Py<PyGraph>> {
        self.graph.as_ref().ok_or_else(cleared_view_error)
    }

    /// Materialise the persistent `{neighbour: shared_edge_attr_dict}` row
    /// only for mapping-wide operations. The cold `__getitem__` route stays
    /// O(1), while an already-materialised row remains live across edge churn
    /// and detached after node removal, matching NetworkX's inner dict.
    fn materialize(&mut self, py: Python<'_>) -> PyResult<Py<PyDict>> {
        if let Some(row) = &self.row {
            return Ok(row.clone_ref(py));
        }
        let graph = self.graph()?.clone_ref(py);
        let mut graph = graph.borrow_mut(py);
        if !graph.inner.has_node(&self.node) {
            return Err(PyKeyError::new_err((self.node.clone(),)));
        }
        if let Some(row) = graph.adj_row_py.get(&self.node) {
            let row = row.clone_ref(py);
            self.row = Some(row.clone_ref(py));
            return Ok(row);
        }
        let row = PyDict::new(py);
        let neighbors: Vec<String> = graph
            .inner
            .neighbors(&self.node)
            .unwrap_or_default()
            .into_iter()
            .map(str::to_owned)
            .collect();
        if !neighbors.is_empty() {
            graph.mark_edges_dirty();
        }
        for neighbor in neighbors {
            let py_neighbor = graph.py_adj_key(py, &self.node, &neighbor);
            let attrs = graph.materialize_edge_py_attrs(py, &self.node, &neighbor);
            row.set_item(py_neighbor, attrs.bind(py))?;
        }
        let row = row.unbind();
        graph.adj_row_py.insert(self.node.clone(), row.clone_ref(py));
        self.row = Some(row.clone_ref(py));
        Ok(row)
    }

    fn copy_row(py: Python<'_>, row: &Bound<'_, PyDict>) -> PyResult<Py<PyDict>> {
        let result = PyDict::new(py);
        for (key, value) in row.iter() {
            let copied = value.downcast::<PyDict>()?.copy()?.unbind();
            result.set_item(key, copied)?;
        }
        Ok(result.unbind())
    }
}

#[pymethods]
impl AtlasView {
    fn __traverse__(&self, visit: PyVisit<'_>) -> Result<(), PyTraverseError> {
        visit.call(&self.graph)?;
        visit.call(&self.row)
    }

    fn __clear__(&mut self) {
        self.graph = None;
        self.row = None;
    }

    #[new]
    fn py_new(
        py: Python<'_>,
        graph: Py<PyGraph>,
        node: &Bound<'_, PyAny>,
    ) -> PyResult<Self> {
        let canonical = node_key_to_string(py, node)?;
        if !graph.borrow(py).inner.has_node(&canonical) {
            return Err(crate::missing_key_error(node));
        }
        Ok(Self::new(graph, canonical))
    }

    fn __getitem__(&mut self, py: Python<'_>, v: &Bound<'_, PyAny>) -> PyResult<Py<PyDict>> {
        if let Some(row) = &self.row {
            let Some(attrs) = row.bind(py).get_item(v)? else {
                return Err(PyKeyError::new_err((v.clone().unbind(),)));
            };
            self.graph()?.borrow(py).mark_edges_dirty();
            return Ok(attrs.downcast::<PyDict>()?.clone().unbind());
        }
        // br-r37-c1-ey6ob: `G[u][v]`'s inner subscript. `self.node` is ALREADY
        // canonical, so this call only ever had to canonicalize `v` — and it did
        // so into an owned String that was hashed twice and dropped. Borrowed
        // now; `has_edge` and `materialize_edge_py_attrs` both take `&str`, and
        // the returned dict is still the SAME shared `Py<PyDict>` the graph
        // stores, so `G[u][v]['w'] = x` keeps mutating the live edge attrs.
        let graph = self.graph()?;
        let mut v_buf = ArrayString::new();
        let v_key = crate::canonical_node_key_in(py, v, &mut v_buf)?;
        let v_canon = v_key.as_str();
        let mut g = graph.borrow_mut(py);
        if !g.inner.has_edge(&self.node, v_canon) {
            return Err(PyKeyError::new_err((v.clone().unbind(),)));
        }
        // The returned dict is the SAME shared Py<PyDict> the graph stores, so
        // `G[u][v]['w'] = x` mutates the live edge attrs — flag the edge store
        // dirty so a later native read reconciles it (matches the old eager
        // `G[u]`, which marked dirty unconditionally).
        g.mark_edges_dirty();
        Ok(g.materialize_edge_py_attrs(py, &self.node, v_canon))
    }

    fn __contains__(&self, py: Python<'_>, v: &Bound<'_, PyAny>) -> PyResult<bool> {
        if let Some(row) = &self.row {
            return row.bind(py).contains(v);
        }
        // br-r37-c1-ey6ob: borrowed canonical probe (see `__getitem__`).
        let graph = self.graph()?;
        crate::with_node_key_str(py, v, |v_canon| {
            graph.borrow(py).inner.has_edge(&self.node, v_canon)
        })
    }

    fn __len__(&self, py: Python<'_>) -> usize {
        if let Some(row) = &self.row {
            return row.bind(py).len();
        }
        self.graph
            .as_ref()
            .map_or(0, |graph| graph.borrow(py).inner.neighbor_count(&self.node))
    }

    fn __iter__(&mut self, py: Python<'_>) -> PyResult<PyObject> {
        Ok(self
            .materialize(py)?
            .bind(py)
            .call_method0("__iter__")?
            .unbind())
    }

    fn keys(&mut self, py: Python<'_>) -> PyResult<PyObject> {
        Ok(self
            .materialize(py)?
            .bind(py)
            .call_method0("keys")?
            .unbind())
    }

    fn items(&mut self, py: Python<'_>) -> PyResult<PyObject> {
        Ok(self
            .materialize(py)?
            .bind(py)
            .call_method0("items")?
            .unbind())
    }

    fn values(&mut self, py: Python<'_>) -> PyResult<PyObject> {
        Ok(self
            .materialize(py)?
            .bind(py)
            .call_method0("values")?
            .unbind())
    }

    #[pyo3(signature = (v, default=None))]
    fn get(
        &mut self,
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
    fn copy(&mut self, py: Python<'_>) -> PyResult<Py<PyDict>> {
        let row = self.materialize(py)?;
        Self::copy_row(py, row.bind(py))
    }

    fn __eq__(&mut self, py: Python<'_>, other: &Bound<'_, PyAny>) -> PyResult<bool> {
        let m = self.materialize(py)?;
        m.bind(py).eq(other)
    }

    fn __ne__(&mut self, py: Python<'_>, other: &Bound<'_, PyAny>) -> PyResult<bool> {
        Ok(!self.__eq__(py, other)?)
    }

    fn __str__(&mut self, py: Python<'_>) -> PyResult<String> {
        let m = self.materialize(py)?;
        Ok(m.bind(py).str()?.to_string())
    }

    fn __repr__(&mut self, py: Python<'_>) -> PyResult<String> {
        let m = self.materialize(py)?;
        Ok(format!("AtlasView({})", m.bind(py).repr()?.to_str()?))
    }

    fn __bool__(&self, py: Python<'_>) -> bool {
        self.__len__(py) > 0
    }

    fn __reduce__(&mut self, py: Python<'_>) -> PyResult<(PyObject, (Py<PyDict>,))> {
        let module = PyModule::import(py, "franken_networkx")?;
        let reconstruct = module.getattr("_reconstruct_atlas_view")?.unbind();
        Ok((reconstruct, (self.copy(py)?,)))
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
            lookup_cache: NodeLookupCache::new(py),
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
    Py::new(py, AdjacencyView { graph: Some(graph) })
}
