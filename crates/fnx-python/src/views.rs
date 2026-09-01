//! NetworkX-compatible view objects (NodeView, EdgeView, DegreeView).
//!
//! These views provide dict-like read access to graph data and reflect
//! the current state of the graph (they are "live" views backed by Py<PyGraph>).

use crate::{
    NetworkXError, NodeIterator, NodeLookupCache, PyGraph, PyObject, attr_map_to_pydict,
    node_key_can_use_index_lookaside, node_key_to_string,
};
use arrayvec::ArrayString;
use pyo3::exceptions::{PyKeyError, PyRuntimeError, PyTypeError, PyValueError};
use pyo3::gc::{PyTraverseError, PyVisit};
use pyo3::intern;
use pyo3::prelude::*;
use pyo3::sync::PyOnceLock;
use pyo3::types::{PyDict, PyIterator, PyList, PyModule, PySlice, PyString, PyTuple};

/// Decide what a spec endpoint that will not canonicalise should do
/// (br-r37-c1-dtrpe).
///
/// networkx reaches the endpoint through `self._adjdict[u]`, so the outcome
/// depends on the endpoint itself, not on our canonicalisation:
///   * an UNHASHABLE endpoint makes that dict lookup raise TypeError, which nx
///     does not catch, so it must escape here too;
///   * a hashable endpoint we cannot canonicalise simply is not a node, which
///     nx answers with False by way of KeyError.
fn endpoint_not_a_node(item: &Bound<'_, PyAny>, canonical_err: PyErr) -> PyResult<bool> {
    match item.hash() {
        Ok(_) => Ok(false),
        // The canonicalisation error is dropped on purpose: the endpoint being
        // unhashable is the reason nx raises, and its message is the one nx
        // surfaces. br-r37-c1-q32e6: nx surfaces it from a DICT LOOKUP, whose
        // wording CPython 3.14 made longer than a bare hash's, so the error is
        // re-taken through `hash_key_as_dict_would` rather than forwarded.
        Err(hash_err) => {
            drop(canonical_err);
            drop(hash_err);
            crate::hash_key_as_dict_would(item).map(|()| false)
        }
    }
}

/// networkx's KeyError text for a missing edge subscript (br-r37-c1-ef8rt).
///
/// nx re-raises with `f"The edge {e} is not in the graph."` carrying the
/// ORIGINAL spec object, so the message shows what the caller passed rather
/// than the canonical bytes we looked up.
///
/// `str`, not `repr`: an f-string formats with `__str__`, so a STRING subscript
/// reads `The edge xy is not in the graph.` and not `The edge 'xy' ...`. A
/// tuple renders identically either way, which is why only the string spec
/// catches this — `test_edges_subscript_message_and_typeerror_match_nx` does.
fn missing_edge_key_error(edge: &Bound<'_, PyAny>) -> PyErr {
    match edge.str() {
        Ok(text) => PyKeyError::new_err(format!("The edge {text} is not in the graph.")),
        Err(err) => err,
    }
}

/// CPython's "too many values to unpack" text, WITH the count when — and only
/// when — CPython itself supplies one.
///
/// br-r37-c1-eccks: CPython 3.14 reports the length it
/// actually got, and this message was frozen at the older countless form, so
/// `G.edges[('a','b','c')]` said "(expected 2)" where networkx said
/// "(expected 2, got 3)". The count is NOT unconditional — measured against a
/// live unpack, `a, b = x` reports it for an exact tuple, list or dict and
/// omits it for `str`, `bytes`, `bytearray`, `range`, `set`, `frozenset`,
/// `deque`, a `collections.abc.Sequence` and any plain iterator. Reporting it
/// everywhere would trade one divergence for nine.
fn too_many_values_to_unpack(source: &Bound<'_, PyAny>, expected: usize) -> PyErr {
    let cpython_counts = source.is_exact_instance_of::<PyTuple>()
        || source.is_exact_instance_of::<PyList>()
        || source.is_exact_instance_of::<PyDict>();
    match cpython_counts.then(|| source.len().ok()).flatten() {
        Some(got) => PyValueError::new_err(format!(
            "too many values to unpack (expected {expected}, got {got})"
        )),
        None => PyValueError::new_err(format!("too many values to unpack (expected {expected})")),
    }
}

/// `u, v = e`, with CPython's own wording on both failure modes.
///
/// br-r37-c1-ef8rt: callers match on these messages, and nx gets them for free
/// from the interpreter's unpack. A non-iterable is a TypeError, and any length
/// other than two is a ValueError — which `EdgeView.__getitem__` does NOT catch,
/// unlike `__contains__`.
fn unpack_two_endpoints<'py>(
    edge: &Bound<'py, PyAny>,
) -> PyResult<(Bound<'py, PyAny>, Bound<'py, PyAny>)> {
    let mut items = edge.try_iter().map_err(|err| {
        if err.is_instance_of::<PyTypeError>(edge.py()) {
            let name = edge
                .get_type()
                .name()
                .map(|n| n.to_string())
                .unwrap_or_else(|_| "object".to_owned());
            PyTypeError::new_err(format!("cannot unpack non-iterable {name} object"))
        } else {
            err
        }
    })?;
    let first = items.next().transpose()?;
    let second = items.next().transpose()?;
    let got = usize::from(first.is_some()) + usize::from(second.is_some());
    let (Some(first), Some(second)) = (first, second) else {
        return Err(PyValueError::new_err(format!(
            "not enough values to unpack (expected 2, got {got})"
        )));
    };
    if items.next().transpose()?.is_some() {
        return Err(too_many_values_to_unpack(edge, 2));
    }
    Ok((first, second))
}

// ---------------------------------------------------------------------------
// NodeView — returned by G.nodes or G.nodes(data=True)
// ---------------------------------------------------------------------------

/// A view of the graph's nodes. Supports ``len``, ``in``, iteration, and ``[]``.
///
/// When ``data=True``, iteration yields ``(node, attr_dict)`` pairs.
/// When ``data="attr_name"``, yields ``(node, attr_value)`` pairs.
/// br-r37-c1-abccache: `collections.abc` view types, imported ONCE.
///
/// `keys()`, `items()` and `values()` on this view each did
/// `PyModule::import(py, "collections.abc")` followed by a `getattr` on EVERY
/// call, to construct the `KeysView` / `ItemsView` / `ValuesView` that networkx
/// returns. networkx reaches those types through a module global - one
/// `LOAD_GLOBAL` - so fnx was paying a sys.modules probe plus an attribute
/// lookup that the incumbent does not pay at all.
///
/// Measured: fnx `row.keys()` 444.6ns against networkx's 174.2ns, a 270ns gap,
/// while the same row's `iter()` (56.6ns) and `len()` (36.9ns) are already fast
/// - so the row is fine and it is the view CONSTRUCTION that costs. The Python
/// proxy for the removed work, `import_module("collections.abc").KeysView`,
/// measures 296.0ns against 22.8ns for a cached global, which accounts for the
/// gap.
///
/// Cached per-interpreter with `PyOnceLock` (pyo3 0.28 renamed `GILOnceCell`),
/// which is the supported way to hold
/// a `Py<PyAny>` that must not be initialised before the GIL exists.
static ABC_KEYS_VIEW: PyOnceLock<Py<PyAny>> = PyOnceLock::new();
static ABC_ITEMS_VIEW: PyOnceLock<Py<PyAny>> = PyOnceLock::new();
static ABC_VALUES_VIEW: PyOnceLock<Py<PyAny>> = PyOnceLock::new();

fn abc_view_type<'py>(
    py: Python<'py>,
    cell: &'static PyOnceLock<Py<PyAny>>,
    name: &str,
) -> PyResult<&'py Bound<'py, PyAny>> {
    let cached = cell.get_or_try_init(py, || -> PyResult<Py<PyAny>> {
        Ok(PyModule::import(py, "collections.abc")?
            .getattr(name)?
            .unbind())
    })?;
    Ok(cached.bind(py))
}

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
        // br-r37-c1-uk664: an exact `str` goes through the present-key memo, as
        // the other three node views now do. This was the last one without it,
        // which left the SIMPLE Graph the worst of the four on `n in G.nodes()`
        // once its siblings were fixed.
        if n.is_exact_instance_of::<pyo3::types::PyString>() {
            return self.graph.borrow(py).exact_str_node_is_present(py, n);
        }
        crate::hash_key_as_dict_would(n)?;
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
/// (the `G.edges(nbunch, data=True)` contract).
///
/// Every yielded dictionary is live, so the caller also records precisely the
/// yielded edge positions through `mark_alldata_edges_exposed` before calling
/// this helper. That lets the weighted-size kernels read those dictionaries as
/// authoritative rather than disabling the store for unrelated edges.
fn edge_alldata_items(
    py: Python<'_>,
    g: &mut PyGraph,
    node_filter: Option<&std::collections::HashSet<String>>,
) -> PyResult<Vec<PyObject>> {
    // br-r37-c1-ml7s5: read the generation BEFORE the field borrows below — the
    // accessor methods take `&self` and would conflict with them.
    let nodes_seq = g.nodes_seq;
    let inner = &g.inner;
    let edge_py_attrs = &mut g.edge_py_attrs;
    let edge_py_attrs_by_index = &mut g.edge_py_attrs_by_index;
    let edge_py_attrs_by_endpoint = &mut g.edge_py_attrs_by_endpoint;
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
            // br-r37-c1-ml7s5: probe the INDEX lookaside before building a
            // canonical key.
            //
            // `PyGraph::edge_key(left, right)` returns `(String, String)` — two
            // owned allocations of full node-key length, per edge, purely to
            // build a probe key. That is why this call grew with node-key length
            // while the directed twin stayed flat: 114.9us at 3-character keys
            // against 713.5us at 2000, where networkx is flat at ~322us. At 300
            // edges and 2000-character keys it is 600 allocations and ~1.2MB
            // hashed per call.
            //
            // br-r37-c1-2a00r removed the ENDPOINT hashing here with the
            // `key_vec` index walk above and recorded that this probe was left:
            // "re-keying that map by index is a separate, larger lever". It is
            // not a larger lever any more — that walk already yields `(u, v)`
            // INDICES at exactly this point, and `edge_py_attrs_by_index`
            // already exists (br-r37-c1-ptiz2), stamped with `nodes_seq` and
            // cleared by `bump_edges_seq`.
            //
            // The entry is filled from the SAME dict the string-keyed mirror
            // holds, never a fresh one, so the two maps cannot disagree about
            // identity — `edges(data=True)` must keep handing out the graph's
            // live dicts, which `test_edges_data_attr_dict_liveness.py` pins.
            let index_key = if u <= v { (u, v) } else { (v, u) };
            let dict = match edge_py_attrs_by_index.get(&index_key) {
                Some((seq, cached)) if *seq == nodes_seq => cached.clone_ref(py),
                _ => {
                    let live = edge_py_attrs
                        .entry(PyGraph::edge_key(left, right))
                        .or_insert_with(|| match inner.edge_attrs_by_indices(u, v) {
                            Some(attrs) => attr_map_to_pydict(py, attrs)
                                .expect("stored string-keyed edge attrs must convert to Python"),
                            None => PyDict::new(py).unbind(),
                        })
                        .clone_ref(py);
                    edge_py_attrs_by_index.insert(index_key, (nodes_seq, live.clone_ref(py)));
                    live
                }
            };
            let (endpoint_left, endpoint_right) = PyGraph::edge_key(left, right);
            edge_py_attrs_by_endpoint
                .entry(endpoint_left)
                .or_default()
                .insert(endpoint_right, dict.clone_ref(py));
            items.push(tuple_object(
                py,
                &[
                    key_vec[u].clone_ref(py),
                    key_vec[v].clone_ref(py),
                    dict.into_any(),
                ],
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
            .clone_ref(py);
        let (endpoint_left, endpoint_right) = PyGraph::edge_key(left, right);
        edge_py_attrs_by_endpoint
            .entry(endpoint_left)
            .or_default()
            .insert(endpoint_right, dict.clone_ref(py));
        items.push(tuple_object(py, &[py_u, py_v, dict.into_any()])?);
    }
    Ok(items)
}

/// Record every live edge-attribute dictionary an all-data edge view can hand
/// out. Bulk `edges(data=True)` used to call `mark_edges_dirty`, which widened
/// the escape scope to unknown and permanently disabled the weighted-store
/// scalar even when the graph was only read. The store already supports a named
/// escape scope: it keeps its native value for clean edges and consults the live
/// Python dictionary for each named edge. Recording this exact set is therefore
/// sound even if the caller mutates any returned raw `dict` later.
///
/// The filtered spelling must record only dictionaries it actually returns. An
/// empty `nbunch` consequently leaves the store clean, matching its having
/// exposed no mutable state at all.
fn mark_alldata_edges_exposed(
    g: &PyGraph,
    node_filter: Option<&std::collections::HashSet<String>>,
) {
    let nodes = node_filter.map(|_| g.inner.nodes_ordered());
    for (u, v) in g.inner.edges_ordered_indices() {
        if let (Some(filter), Some(nodes)) = (node_filter, nodes.as_ref())
            && !(filter.contains(nodes[u]) || filter.contains(nodes[v]))
        {
            continue;
        }
        g.mark_edge_exposed(u, v);
    }
}

/// A view of the graph's edges. Supports ``len``, ``in``, iteration, and ``[]``.
#[pyclass(module = "franken_networkx")]
pub struct EdgeView {
    graph: Py<PyGraph>,
    data: NodeViewData,
    /// br-r37-c1-hvw2e-8smdi: the private adjacency mapping as it stood WHEN
    /// THIS VIEW WAS BUILT, or `None` for an ordinary graph. networkx binds
    /// `self._adjdict` in `__init__` and never re-reads it, so a held view is
    /// blind to a later `G._adj = ...`; this field is that binding.
    private_adj: Option<PyObject>,
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
        if let Some(mapping) = &self.private_adj {
            visit.call(mapping)?;
        }
        Ok(())
    }

    fn __len__(&self, py: Python<'_>) -> usize {
        let g = self.graph.borrow(py);
        g.inner.edge_count()
    }

    /// The permissive half of nx's `EdgeView.__contains__`, for specs that are
    /// not tuples: `e[:2]` then `u, v = ...`.
    ///
    /// Which exception escapes is the contract, and it is not uniform. nx wraps
    /// the whole body in `except (KeyError, ValueError)`, so:
    ///   * a non-subscriptable spec (`5`, `None`, a set, a generator) raises
    ///     TypeError from `e[:2]`, with CPython's own wording;
    ///   * a dict raises KeyError from `e[:2]` — slices became hashable in
    ///     Python 3.12, so it is a missing key, not a type error — and answers
    ///     False;
    ///   * a spec that slices but does not unpack to exactly two (`"a"`, `""`,
    ///     a 1-list) is a ValueError, and answers False.
    fn contains_edge_spec(&self, py: Python<'_>, edge: &Bound<'_, PyAny>) -> PyResult<bool> {
        let two = 2usize.into_pyobject(py)?;
        let head = py
            .get_type::<PySlice>()
            .call1((py.None(), two, py.None()))?;
        let sliced = match edge.get_item(&head) {
            Ok(value) => value,
            Err(err) if err.is_instance_of::<PyKeyError>(py) => return Ok(false),
            Err(err) if err.is_instance_of::<PyValueError>(py) => return Ok(false),
            Err(err) => return Err(err),
        };
        // `u, v = sliced`: not iterable is a TypeError and propagates; any
        // length other than two is a ValueError, which nx answers with False.
        let mut items = sliced.try_iter()?;
        let (Some(u_item), Some(v_item)) = (items.next().transpose()?, items.next().transpose()?)
        else {
            return Ok(false);
        };
        if items.next().transpose()?.is_some() {
            return Ok(false);
        }
        // br-r37-c1-lvlu7: nx's body is `v in self._adjdict[u]` inside
        // `except (KeyError, ValueError)`, so an UNHASHABLE endpoint raises
        // TypeError out of the dict — not caught there, and not answered here
        // either. fnx canonicalises by reading characters and never calls
        // `__hash__`, so `(Unhash("n0"), "n1") in G.edges` answered True.
        //
        // THE ORDER IS PART OF THE CONTRACT: `u` is hashed and looked up first,
        // and an absent `u` short-circuits to False through KeyError WITHOUT
        // `v` ever being hashed — `("missing", Unhash("n1")) in G.edges` is
        // False in nx, so hashing both up front trades one divergence for
        // another. Both directions are pinned in
        // tests/python/test_unhashable_key_parity.py.
        //
        // The graph borrow is taken for the `u` probe and DROPPED before `v` is
        // hashed: `__hash__` runs arbitrary Python and could re-enter this
        // graph, which is how br-r37-c1-oqvk5 shipped a P0 RefCell panic.
        crate::require_hashable_node_key(&u_item)?;
        let mut u_buf = ArrayString::new();
        let mut v_buf = ArrayString::new();
        let u = match crate::canonical_node_key_in(py, &u_item, &mut u_buf) {
            Ok(key) => key,
            Err(err) => return endpoint_not_a_node(&u_item, err),
        };
        // br-r37-c1-n4c8l: the u-presence lookup exists ONLY to reproduce nx's
        // short-circuit — an absent `u` must answer False before `v` is hashed.
        // When hashing `v` cannot raise, that ordering is unobservable, so the
        // probe goes straight to `has_edge` and pays ONE String-keyed lookup
        // instead of two. Ordering it unconditionally cost 973.2 Ir/call
        // against 696.0 before, three `get_index_of::<str>` probes where two
        // are needed, and took the row from 1.0183x to 0.7954x.
        if !crate::node_key_hash_cannot_raise(&v_item) {
            {
                let g = self.graph.borrow(py);
                if !g.inner.has_node(u.as_str()) {
                    return Ok(false);
                }
            }
            crate::require_hashable_node_key(&v_item)?;
        }
        let v = match crate::canonical_node_key_in(py, &v_item, &mut v_buf) {
            Ok(key) => key,
            Err(err) => return endpoint_not_a_node(&v_item, err),
        };
        let g = self.graph.borrow(py);
        Ok(g.inner.has_edge(u.as_str(), v.as_str()))
    }

    /// networkx's `EdgeView.__contains__`, natively (br-r37-c1-dtrpe)::
    ///
    ///     try:
    ///         u, v = e[:2]
    ///         return v in self._adjdict[u] or u in self._adjdict[v]
    ///     except (KeyError, ValueError):
    ///         return False
    ///
    /// This used to raise `TypeError("edge must be a (u, v) tuple")` for every
    /// non-tuple spec, and `python/franken_networkx/__init__.py` rebound the
    /// slot to a Python function that re-implemented the permissive half around
    /// it. That wrapper was 45.5% of the probe's instructions (1114.7 of 2451.4
    /// Ir) and 1.1190x of its wall clock, so the semantics live here now and
    /// the rebind is gone.
    ///
    /// The tuple fast path is unchanged and pays nothing for any of it: the
    /// permissive path, the hashability probe, and the `e[:2]` slice all sit
    /// behind a branch a `(u, v)` tuple never takes.
    fn __contains__(&self, py: Python<'_>, edge: &Bound<'_, PyAny>) -> PyResult<bool> {
        let Ok(tuple) = edge.downcast::<PyTuple>() else {
            return self.contains_edge_spec(py, edge);
        };
        if tuple.len() < 2 {
            // `u, v = e[:2]` on a shorter spec is a ValueError, which nx
            // answers with False.
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
        // br-r37-c1-p1tvg, TRIED AND REVERTED — NO DEMONSTRATED WIN: routing
        // the exact-`str` endpoints through
        // `PyGraph::cached_exact_string_node_index` (the Python-dict lookaside
        // `has_edge` uses) removes 101 Ir/call here — a quarter of what the
        // bead predicted, because it costed the removal and not the CPython
        // dict probe plus PyLong round-trip that replaces it — and bought no
        // measurable time.
        //
        // The wall-clock draws I first recorded (incumbent/candidate 0.779x /
        // 0.791x / 0.768x, read as "1.27x slower") are CONFOUNDED and the
        // magnitude is retracted: the candidate was invoked as a slot
        // `wrapper_descriptor` while the control was a plain method
        // descriptor, and that call-protocol difference alone is ~25 ns/call
        // against a ~150 ns operation, biased in the direction of the
        // conclusion. Correcting for it leaves roughly 1.1x slower, which is
        // an estimate and not a measurement. A clean re-test must reach both
        // arms through the SAME call protocol.
        //
        // What IS established: no wall-clock win, and an Ir cut that did not
        // translate. Do not re-land this on an Ir argument alone. The real
        // lever on this row was br-r37-c1-dtrpe (the Python wrapper), which
        // took it from 0.81x to ~1.15-1.20x vs networkx on two harnesses.
        // br-r37-c1-lvlu7: nx's body is `v in self._adjdict[u]` inside
        // `except (KeyError, ValueError)`, so an UNHASHABLE endpoint raises
        // TypeError out of the dict — not caught there, and not answered here
        // either. fnx canonicalises by reading characters and never calls
        // `__hash__`, so `(Unhash("n0"), "n1") in G.edges` answered True.
        //
        // THE ORDER IS PART OF THE CONTRACT: `u` is hashed and looked up first,
        // and an absent `u` short-circuits to False through KeyError WITHOUT
        // `v` ever being hashed — `("missing", Unhash("n1")) in G.edges` is
        // False in nx, so hashing both up front trades one divergence for
        // another. Both directions are pinned in
        // tests/python/test_unhashable_key_parity.py.
        //
        // The graph borrow is taken for the `u` probe and DROPPED before `v` is
        // hashed: `__hash__` runs arbitrary Python and could re-enter this
        // graph, which is how br-r37-c1-oqvk5 shipped a P0 RefCell panic.
        crate::require_hashable_node_key(&u_item)?;
        // Exact `str` and exact `int` endpoints resolve by cached index.  Both
        // are built-ins with non-raising hashes; subclasses and bool retain the
        // canonical path so their established semantics stay unchanged.
        //
        // THIS IS br-r37-c1-p1tvg RE-RUN, AND THE LEDGER RECORDS THAT AS
        // REJECTED. That rejection stands where it was measured and does not
        // cover this regime. p1tvg tested SHORT keys, where this row already
        // reads 1.0560x — fnx AHEAD of networkx — so there was nothing for an
        // index path to win, and it correctly found "101 Ir/call removed, no
        // measurable time". The cost being removed scales with key LENGTH: at
        // 8000-character nodes the two `canonical_node_key_in` calls spill their
        // `ArrayString` to the heap and `has_edge` then hashes ~16000 bytes, and
        // this row measures 0.0844x. Re-running a rejected lever in a regime the
        // rejection never tested is the point; the SHORT-key row is carried as a
        // control in the same invocation so a regression there would show.
        //
        // Ordering is preserved rather than assumed: nx short-circuits an absent
        // `u` to False BEFORE `v` is hashed, and that is only observable when
        // hashing `v` can raise. The exact built-ins admitted by this gate
        // cannot raise, so nothing observable is reordered.
        if node_key_can_use_index_lookaside(&u_item) && node_key_can_use_index_lookaside(&v_item) {
            let g = self.graph.borrow(py);
            if let Some(u_index) = g.cached_exact_string_node_index(py, &u_item)? {
                return Ok(match g.cached_exact_string_node_index(py, &v_item)? {
                    Some(v_index) => g.inner.has_edge_by_indices(u_index, v_index),
                    None => false,
                });
            }
            return Ok(false);
        }
        let mut u_buf = ArrayString::new();
        let mut v_buf = ArrayString::new();
        let u = match crate::canonical_node_key_in(py, &u_item, &mut u_buf) {
            Ok(key) => key,
            Err(err) => return endpoint_not_a_node(&u_item, err),
        };
        // br-r37-c1-n4c8l: the u-presence lookup exists ONLY to reproduce nx's
        // short-circuit — an absent `u` must answer False before `v` is hashed.
        // When hashing `v` cannot raise, that ordering is unobservable, so the
        // probe goes straight to `has_edge` and pays ONE String-keyed lookup
        // instead of two. Ordering it unconditionally cost 973.2 Ir/call
        // against 696.0 before, three `get_index_of::<str>` probes where two
        // are needed, and took the row from 1.0183x to 0.7954x.
        if !crate::node_key_hash_cannot_raise(&v_item) {
            {
                let g = self.graph.borrow(py);
                if !g.inner.has_node(u.as_str()) {
                    return Ok(false);
                }
            }
            crate::require_hashable_node_key(&v_item)?;
        }
        let v = match crate::canonical_node_key_in(py, &v_item, &mut v_buf) {
            Ok(key) => key,
            Err(err) => return endpoint_not_a_node(&v_item, err),
        };
        let g = self.graph.borrow(py);
        Ok(g.inner.has_edge(u.as_str(), v.as_str()))
    }

    fn __iter__(&self, py: Python<'_>) -> PyResult<PyObject> {
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
                )
                .map(|iterator| iterator.into_any());
            }
        }
        if matches!(self.data, NodeViewData::AllData) {
            let mut g = self.graph.borrow_mut(py);
            mark_alldata_edges_exposed(&g, None);
            let nodes_seq = g.nodes_seq;
            let edges_seq = g.edges_seq;
            let cached = match &g.edges_alldata_cache {
                Some((cached_nodes_seq, cached_edges_seq, cached))
                    if *cached_nodes_seq == nodes_seq && *cached_edges_seq == edges_seq =>
                {
                    cached.clone_ref(py)
                }
                _ => {
                    let items = edge_alldata_items(py, &mut g, None)?;
                    let cached = PyDict::new(py);
                    for (index, item) in items.iter().enumerate() {
                        cached.set_item(index, item)?;
                    }
                    let cached = cached.unbind();
                    g.edges_alldata_cache = Some((nodes_seq, edges_seq, cached.clone_ref(py)));
                    cached
                }
            };
            return cached
                .bind(py)
                .call_method0("values")?
                .call_method0("__iter__")
                .map(Bound::unbind);
        }
        let (items, node_count, nodes_seq) = match &self.data {
            NodeViewData::AllData => {
                unreachable!("AllData returns through the cached dict iterator")
            }
            _ => {
                let g = self.graph.borrow(py);
                // br-r37-c1-eqedg: use O(1) node_count() instead of allocating nodes_ordered() Vec
                let node_count = g.inner.node_count();
                let nodes_seq = g.nodes_seq;
                // br-r37-c1-eqedg: use edges_ordered_borrowed to avoid string cloning in Rust
                // br-r37-c1-lecmc: INDEX WALK for the all-edges data-bearing
                // branch - the lever `edge_alldata_items` carries at
                // br-r37-c1-2a00r, which this branch never received.
                //
                // `py_node_key` + `py_adj_key` hash each endpoint's full
                // canonical name, twice per edge, on every call; a node of
                // degree d is hashed ~d times across its incident edges.
                // AllData stopped doing that by building the node-index ->
                // Python-key Vec ONCE and walking `edges_ordered_indices()`.
                // That is the measured asymmetry: `edges(data=True)` stands at
                // 2.4560x against networkx while `edges(data=<key>)` sits at
                // 0.9697x, with IDENTICAL Python-level call counts for the two
                // spellings (20137 either way), so the difference is here.
                //
                // The VALUE path is deliberately untouched: `edge_attr_py_value`
                // keeps its mirror-first / store-fallback semantics, and this
                // branch still yields a VALUE rather than a live attr dict, so
                // unlike AllData it marks nothing dirty (br-r37-c1-igdzi). Only
                // the endpoint keys get cheaper.
                //
                // Gated on `adj_py_keys.is_empty()` for the same reason
                // `edge_alldata_items` is: with non-uniform adjacency-row key
                // objects (br-r37-c1-z6uka) a neighbour's display object can
                // differ from the node's own key and only `py_adj_key` knows it.
                // Non-empty falls through to the original per-edge path below.
                //
                // NO CACHE IS ADDED. `edges_alldata_cache` is keyed on
                // (nodes_seq, edges_seq) alone; an Attr request also varies by
                // attribute name and default, so sharing an entry would serve
                // one key's values for another key's request - the wrong-answer
                // class that cache's own comment warns about, invisible to
                // mutation tests because the generation never moves.
                let index_walk: Option<Vec<PyObject>> = if g.adj_py_keys.is_empty() {
                    let nodes: Vec<&str> = g.inner.nodes_ordered();
                    let key_vec: Vec<PyObject> =
                        nodes.iter().map(|n| g.py_node_key(py, n)).collect();
                    let mut built: Vec<PyObject> = Vec::with_capacity(g.inner.edge_count());
                    for (u, v) in g.inner.edges_ordered_indices() {
                        let left = nodes[u];
                        let right = nodes[v];
                        let py_u = key_vec[u].clone_ref(py);
                        let py_v = key_vec[v].clone_ref(py);
                        let tuple = match &self.data {
                            NodeViewData::NoData => tuple_object(py, &[py_u, py_v])?,
                            NodeViewData::Attr(attr_name) => {
                                let val = g
                                    .edge_attr_py_value(py, left, right, attr_name)?
                                    .unwrap_or_else(|| py.None());
                                tuple_object(py, &[py_u, py_v, val])?
                            }
                            NodeViewData::AttrWithDefault(attr_name, def_val) => {
                                let val = g
                                    .edge_attr_py_value(py, left, right, attr_name)?
                                    .unwrap_or_else(|| def_val.clone_ref(py));
                                tuple_object(py, &[py_u, py_v, val])?
                            }
                            NodeViewData::AllData => unreachable!(),
                        };
                        built.push(tuple);
                    }
                    Some(built)
                } else {
                    None
                };
                let items: Vec<PyObject> = if let Some(built) = index_walk {
                    built
                } else {
                    g.inner
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
                        .collect::<PyResult<Vec<_>>>()?
                };
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
        .map(|iterator| iterator.into_any())
    }

    /// networkx's `EdgeView.__getitem__`, natively (br-r37-c1-ef8rt)::
    ///
    ///     if isinstance(e, slice): raise nx.NetworkXError(...)
    ///     u, v = e
    ///     try: return self._adjdict[u][v]
    ///     except KeyError: raise KeyError(f"The edge {e} is not in the graph.")
    ///
    /// `G.edges[u, v]` was the worst read probe on the surface at 0.25x, and
    /// this slot was DEAD: `python/franken_networkx/__init__.py` rebound
    /// `__getitem__` to a Python function that unpacked, called `hash()` twice,
    /// looked the owning graph up in a weak dict keyed by `id(self)`, and then
    /// called `get_edge_data` — the native slot below was never reached for a
    /// plain `Graph`. The owner it went to that trouble to recover is the
    /// `graph` field this view already holds.
    ///
    /// The unpack is nx's `u, v = e`, NOT `e[:2]`: a 3-tuple is a ValueError
    /// here where `__contains__` accepts it. CPython's own wording for both
    /// failure modes is reproduced because callers match on it.
    fn __getitem__(&self, py: Python<'_>, edge: &Bound<'_, PyAny>) -> PyResult<Py<PyDict>> {
        if edge.is_instance_of::<PySlice>() {
            let (start, stop, step) = (
                edge.getattr(intern!(py, "start"))?,
                edge.getattr(intern!(py, "stop"))?,
                edge.getattr(intern!(py, "step"))?,
            );
            return Err(NetworkXError::new_err(format!(
                "EdgeView does not support slicing, try list(G.edges)[{start}:{stop}:{step}]"
            )));
        }
        let (u_item, v_item) = unpack_two_endpoints(edge)?;
        // br-r37-c1-lvlu7: nx hashes `u` inside `self._adjdict[u]`, so an
        // unhashable `u` raises TypeError and an ABSENT `u` becomes the KeyError
        // below without `v` ever being hashed.
        crate::require_hashable_node_key(&u_item)?;
        // br-r37-c1-ef8rt: a graph carrying networkx private storage reads the
        // ASSIGNED adjacency, not the native store — `G._adj = {...}` replaces
        // exactly what this subscript returns. One bool test for every ordinary
        // graph; the Python wrapper this slot replaced owned the same branch.
        // br-r37-c1-hvw2e-8smdi: read the mapping THIS VIEW CAPTURED, never the
        // graph's current one. The previous version re-probed private storage on
        // every subscript, so a held view noticed a `G._adj` assigned after it
        // was built - the inverse of networkx, which binds `_adjdict` in
        // `__init__` and cannot see a later reassignment. That made fnx raise
        // KeyError where networkx returns the edge. It also cost a probe per
        // call; this costs one `Option` test.
        if let Some(mapping) = self.private_adj.as_ref() {
            let mapping = mapping.bind(py);
            let row = match mapping.get_item(&u_item) {
                Ok(row) => row,
                Err(err) if err.is_instance_of::<PyKeyError>(py) => {
                    return Err(missing_edge_key_error(edge));
                }
                Err(err) => return Err(err),
            };
            if row.is_none() {
                return Err(missing_edge_key_error(edge));
            }
            crate::require_hashable_node_key(&v_item)?;
            return match row.get_item(&v_item) {
                Ok(attrs) => Ok(attrs.downcast_into::<PyDict>()?.unbind()),
                Err(err) if err.is_instance_of::<PyKeyError>(py) => {
                    Err(missing_edge_key_error(edge))
                }
                Err(err) => Err(err),
            };
        }
        // br-r37-c1-ptiz2: INDEX-keyed lookaside first, before any canonical is
        // built at all. This is the whole lever: the string-keyed probe below
        // hashes BOTH full-length canonical endpoints on every read, and above
        // the 128-byte ArrayString the canonical itself becomes an owned heap
        // String. Measured on `G.edges[u,v]` against node-key length — 1.17x
        // growth below the buffer (hashing), a 2.03x STEP across it at canon
        // bytes 128 -> 133 (allocation), linear above — while networkx stays
        // flat at 92.6-92.7ns because CPython caches the str hash.
        //
        // Exact `str` only, mirroring `has_edge`, which is FLAT in key length
        // for exactly this reason. `cached_exact_string_node_index` is itself
        // `nodes_seq`-guarded, and the lookaside entry carries its own
        // `nodes_seq`, so a node removal that renumbers indices makes this a
        // MISS rather than a wrong hit.
        //
        // ORDER: the hit is existence proof (entries only exist for edges that
        // were present), so `v`'s hashability is checked here exactly as it is
        // on the string-keyed hit path below — networkx hashes `v` only once
        // `u` resolves.
        if node_key_can_use_index_lookaside(&u_item) && node_key_can_use_index_lookaside(&v_item) {
            let g = self.graph.borrow(py);
            let indices = (
                g.cached_exact_string_node_index(py, &u_item)?,
                g.cached_exact_string_node_index(py, &v_item)?,
            );
            if let (Some(ui), Some(vi)) = indices
                && let Some(attrs) = g.cached_edge_py_attrs_by_index(py, ui, vi)
            {
                crate::require_hashable_node_key(&v_item)?;
                // br-r37-c1-igdzi: `G.edges[u, v]` escapes ONE edge's dict and
                // both positions are already in hand, so record the edge rather
                // than the whole graph.
                g.mark_edge_exposed(ui, vi);
                return Ok(attrs);
            }
        }
        // br-r37-c1-ey6ob: borrowed endpoint canonicals (see `__contains__`).
        // `materialize_edge_py_attrs` already takes `&str`.
        let mut u_buf = ArrayString::new();
        let mut v_buf = ArrayString::new();
        let u = crate::canonical_node_key_in(py, &u_item, &mut u_buf)?;
        let v = crate::canonical_node_key_in(py, &v_item, &mut v_buf)?;
        let (u, v) = (u.as_str(), v.as_str());
        let mut g = self.graph.borrow_mut(py);
        // br-r37-c1-y2ww1: consult the endpoint lookaside BEFORE probing the
        // graph for `u`. A hit is existence proof — the entry exists only for
        // an edge that was present, and `bump_edges_seq` clears it on any
        // structural mutation (br-r37-c1-ef8rt) — so the `has_node(u)` probe
        // that used to run first was duplicate work on the common path. Same
        // shape as br-r37-c1-dlqkq and br-r37-c1-do7g5.
        //
        // ORDER MATTERS and canonicalization does not hash. networkx evaluates
        // `self._adjdict[u][v]`: `u` is hashed, and if `u` is ABSENT it raises
        // KeyError WITHOUT ever hashing `v`. So `v`'s hashability is only
        // checked once `u`'s presence is established — by the lookaside hit
        // here, or by `has_node(u)` on the miss path below.
        if let Some(attrs) = g.cached_edge_py_attrs(py, u, v) {
            crate::require_hashable_node_key(&v_item)?;
            // br-r37-c1-igdzi: same single edge, reached by name.
            g.mark_edge_exposed_by_name(u, v);
            return Ok(attrs);
        }
        if !g.inner.has_node(u) {
            return Err(missing_edge_key_error(edge));
        }
        crate::require_hashable_node_key(&v_item)?;
        if !g.inner.has_edge(u, v) {
            return Err(missing_edge_key_error(edge));
        }
        // br-r37-c1-igdzi: still exactly one edge, so the flag carries its name.
        g.mark_edge_exposed_by_name(u, v);
        let attrs = g.materialize_edge_py_attrs(py, u, v);
        // br-r37-c1-ptiz2: fill the index lookaside on the miss path, with the
        // SAME dict the string-keyed mirror just recorded, so the two can never
        // disagree about identity. The same exact scalar gate as the probe
        // above keeps unsupported key types on the canonical route.
        if node_key_can_use_index_lookaside(&u_item) && node_key_can_use_index_lookaside(&v_item) {
            let indices = (
                g.cached_exact_string_node_index(py, &u_item)?,
                g.cached_exact_string_node_index(py, &v_item)?,
            );
            if let (Some(ui), Some(vi)) = indices {
                g.remember_edge_py_attrs_by_index(py, ui, vi, &attrs);
            }
        }
        Ok(attrs)
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
                mark_alldata_edges_exposed(&g, Some(&node_set));
                edge_alldata_items(py, &mut g, Some(&node_set))?
            } else {
                let g = self.graph.borrow(py);
                // br-r37-c1-lecmc: the NBUNCH sibling of the all-edges index walk
                // in `__iter__`. Same defect, same fix: this called
                // `py_node_key` + `py_adj_key` per surviving edge, hashing each
                // endpoint's full canonical name twice, where the `AllData` arm
                // directly above already reaches `edge_alldata_items` and its
                // index walk. Found by applying to my own change the rule this
                // ledger keeps recording - fix the sibling, or the next reader
                // measures one spelling and is surprised by the other.
                //
                // The node filter moves onto the INDEXED names, so it is the
                // same predicate on the same strings, just without rebuilding a
                // Python key object to get there. Capacity is left to the Vec:
                // a one-node nbunch on a large graph keeps very few edges, and
                // `with_capacity(edge_count())` would allocate the whole edge
                // list for it.
                //
                // Value semantics, the `adj_py_keys` gate and the absence of a
                // cache are all exactly as in the all-edges walk - see that
                // comment for why each is load-bearing.
                let index_walk: Option<Vec<PyObject>> = if g.adj_py_keys.is_empty() {
                    // br-r37-c1-lecmc / br-r37-c1-hihrf: keys are built on first
                    // use rather than one per node in the graph, so this branch
                    // costs one key per node it actually emits.
                    //
                    // READ THIS BEFORE MEASURING ANYTHING HERE. This walk is NOT
                    // what serves `G.edges(nbunch)`. That returns the PYTHON
                    // `EdgeDataView` in __init__.py, whose `__iter__` walks
                    // adjacency rows itself; this arm is reached only through the
                    // native view's own nbunch iteration. I attributed a measured
                    // decay (1.8106x of networkx at 2000 nodes falling to 0.7812x
                    // at 16000) to the eager key vector that used to live here,
                    // changed it, and measured EXACTLY ZERO effect - because this
                    // code did not run. Two signals had already said so: removing
                    // 16000 eager key constructions cannot be free, and the
                    // emission order matched networkx's strictly nbunch-major
                    // order, which a filtered global scan cannot produce.
                    //
                    // The lazy keys are kept because they are correct and cost
                    // nothing, not because they bought anything. The real cost is
                    // in a native helper called from the Python walk; see
                    // br-r37-c1-hihrf for the localisation.
                    //
                    // Keys are now built on first use and reused across edges, so
                    // the cost is one per node actually EMITTED. The walk itself
                    // stays over `edges_ordered_indices` because that is what
                    // reproduces networkx's edge ORDER for an nbunch query;
                    // switching to a per-node adjacency walk would be O(degree)
                    // but is an ordering change, which is a parity question and
                    // not this fix.
                    let nodes: Vec<&str> = g.inner.nodes_ordered();
                    let mut key_cache: std::collections::HashMap<usize, PyObject> =
                        std::collections::HashMap::new();
                    let mut built: Vec<PyObject> = Vec::new();
                    for (u, v) in g.inner.edges_ordered_indices() {
                        let left = nodes[u];
                        let right = nodes[v];
                        if !(node_set.contains(left) || node_set.contains(right)) {
                            continue;
                        }
                        let py_u = key_cache
                            .entry(u)
                            .or_insert_with(|| g.py_node_key(py, left))
                            .clone_ref(py);
                        let py_v = key_cache
                            .entry(v)
                            .or_insert_with(|| g.py_node_key(py, right))
                            .clone_ref(py);
                        let tuple = match &view_data {
                            NodeViewData::NoData => tuple_object(py, &[py_u, py_v])?,
                            NodeViewData::Attr(attr_name) => {
                                let val = g
                                    .edge_attr_py_value(py, left, right, attr_name)?
                                    .unwrap_or_else(|| py.None());
                                tuple_object(py, &[py_u, py_v, val])?
                            }
                            NodeViewData::AttrWithDefault(attr_name, def_val) => {
                                let val = g
                                    .edge_attr_py_value(py, left, right, attr_name)?
                                    .unwrap_or_else(|| def_val.clone_ref(py));
                                tuple_object(py, &[py_u, py_v, val])?
                            }
                            NodeViewData::AllData => unreachable!(),
                        };
                        built.push(tuple);
                    }
                    Some(built)
                } else {
                    None
                };
                if let Some(built) = index_walk {
                    built
                } else {
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
                }
            };
            Ok(items.into_pyobject(py)?.into_any().unbind())
        } else {
            let mut view_data = parse_data_param(data)?;
            if let (Some(def), NodeViewData::Attr(attr)) = (default, &view_data) {
                view_data = NodeViewData::AttrWithDefault(attr.clone(), def.clone().unbind());
            }
            // Captured for the derived view at ITS construction, exactly as
            // networkx rebinds `_adjdict` in the new view's `__init__`.
            let private_adj = self
                .graph
                .borrow(py)
                .instance_dict_gc
                .private_adj_mapping(py)?
                .map(pyo3::Bound::unbind);
            let view = Py::new(
                py,
                EdgeView {
                    graph: self.graph.clone_ref(py),
                    data: view_data,
                    private_adj,
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
        // br-r37-c1-ptiz2: exact-`str` resolves by CACHED INDEX and reads the
        // degree by index — O(1) in key length.
        //
        // The borrowed-canonical path below still builds `"str:{len}:{s}"` and
        // then hashes it TWICE: once for `has_node` and again for `degree`. At
        // 8000-character nodes that is ~16000 bytes hashed per call, and it is
        // 92 percent of `G.degree(u)` — measured 1989.0ns of 2169.5ns, against
        // `G.has_node(u)` on the SAME key at 49.7ns because that already takes
        // the index path. A 40x gap between two node lookups is not a property
        // of degree; it is this function paying for a key the graph has already
        // interned.
        //
        // `degree_by_index` is the same primitive `degree` resolves to once it
        // has an index, and its self-loop equivalence to the string form is
        // covered by `degree_by_index_selfloop_ab` in fnx-classes.
        if n.is_exact_instance_of::<PyString>() {
            let g = self.graph.borrow(py);
            if let Some(index) = g.cached_exact_string_node_index(py, n)? {
                return Ok(g.inner.degree_by_index(index));
            }
            drop(g);
            return Err(match n.repr() {
                Ok(repr) => {
                    crate::NodeNotFound::new_err(format!("The node {repr} is not in the graph."))
                }
                Err(err) => err,
            });
        }
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
// br-r37-c1-rgmef: `subclass` is the PREREQUISITE for making plain `Graph`'s
// private `_adj` rows writable. `G._adj[u][v] = {...}` works on networkx and
// raised on fnx; the fix is a writable SUBCLASS of the row view, so that reads
// stay the same function objects (see
// tests/python/test_private_adj_read_path_stays_native.py, which measured a
// wrapper at ~1.55x and rejected it). DiGraph is fixed already because its row
// is the Python `AtlasView`. Graph's row is THIS type, and without `subclass`
// `type("X", (AtlasView,), {})` raises "not an acceptable base type".
//
// UNBUILT: committed under a disk freeze, so it is compiled and measured later.
// This type is on br-r37-c1-ey6ob's hot `G[u]` C-slot path, and `subclass` sets
// Py_TPFLAGS_BASETYPE, so the rebuild must re-measure that path before the
// Python half is wired up.
#[pyclass(module = "franken_networkx", mapping, subclass)]
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
    /// br-r37-c1-ptiz2: this row's node INDEX, stamped with the `nodes_seq` it
    /// was resolved under.
    ///
    /// `node` above is the CANONICAL STRING, so the index lookaside that fixed
    /// the other two routes to the edge attr dict could not be used here —
    /// resolving the index per subscript would cost the very O(key length) hash
    /// the lookaside exists to avoid. Caching it on the ROW makes that hash
    /// once per `G[u]` instead of once per `G[u][v]`, which is the whole point:
    /// a row is subscripted many times.
    ///
    /// The stamp is not optional. Node removal RENUMBERS indices, so a stale
    /// index would not merely miss — it would name a DIFFERENT node, and if
    /// that pair happened to be cached it would return another edge's live
    /// dict. Mismatched seq means re-resolve.
    node_index: Option<(u64, usize)>,
}

impl AtlasView {
    pub(crate) fn new(graph: Py<PyGraph>, node: String) -> Self {
        Self {
            graph: Some(graph),
            node,
            row: None,
            node_index: None,
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
        graph
            .adj_row_py
            .insert(self.node.clone(), row.clone_ref(py));
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
    fn py_new(py: Python<'_>, graph: Py<PyGraph>, node: &Bound<'_, PyAny>) -> PyResult<Self> {
        let canonical = node_key_to_string(py, node)?;
        if !graph.borrow(py).inner.has_node(&canonical) {
            return Err(crate::missing_key_error(node));
        }
        Ok(Self::new(graph, canonical))
    }

    fn __getitem__(&mut self, py: Python<'_>, v: &Bound<'_, PyAny>) -> PyResult<Py<PyDict>> {
        // br-r37-c1-x7bqd: networkx subscripts a dict here, which HASHES v, so
        // an unhashable key is a TypeError — not a KeyError, and not None from
        // `get`. `canonical_node_key_in` below canonicalises by VALUE and never
        // hashes, so `G[u][['x']]` raised KeyError and `G.adj[u].get(['x'])`
        // quietly returned None.
        //
        // br-r37-c1-espyz fixed exactly this on `__contains__` of this same
        // class and stopped there; `__getitem__` and the `get` that delegates to
        // it kept the gap. Simple Graph is the only class where it is publicly
        // reachable, because its row IS this native view — the other three carry
        // a Python wrapper whose own hash masks it.
        //
        // Guarded ahead of BOTH branches, not just the unmaterialised one. The
        // materialised branch already raises through `PyDict::get_item`, so
        // guarding only the other would leave the answer depending on whether
        // the row happened to be materialised, which is the cache-state bug
        // pattern br-r37-c1-alll4 pinned. `require_hashable_node_key`
        // short-circuits on an exact str/int/float/bool, so the common shape
        // pays one type check and never hashes.
        crate::require_hashable_node_key(v)?;
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
        let graph = self.graph()?.clone_ref(py);
        let mut g = graph.borrow_mut(py);
        // br-r37-c1-ptiz2: INDEX-keyed probe, before `v` is canonicalised at
        // all. The string-keyed lookaside below hashes BOTH canonicals in full,
        // and `self.node` is the row's own key — at 8000 characters that is the
        // whole cost. Measured before this: `G[u][v]` 0.0639x against its two
        // sibling routes to the SAME dict at 0.7270x and 0.7012x.
        //
        // The row's index is resolved ONCE per `G[u]` and reused for every
        // subscript on it, seq-stamped so a node removal that renumbers indices
        // forces a re-resolve rather than naming a different node.
        let nodes_seq = g.nodes_seq;
        let u_index = match self.node_index {
            Some((seq, index)) if seq == nodes_seq => Some(index),
            _ => {
                let resolved = g.inner.get_node_index(self.node.as_str());
                if let Some(index) = resolved {
                    self.node_index = Some((nodes_seq, index));
                }
                resolved
            }
        };
        if let Some(u_index) = u_index
            && node_key_can_use_index_lookaside(v)
            && let Some(v_index) = g.cached_exact_string_node_index(py, v)?
            && let Some(attrs) = g.cached_edge_py_attrs_by_index(py, u_index, v_index)
        {
            // br-r37-c1-igdzi: ONE edge escaped, and this path already knows
            // both of its positions — so name it instead of condemning the whole
            // graph. This is the row subscript `G[u][v]`, which measured as
            // destructive as a full `edges(data=True)`: 6.12x to 0.73x.
            g.mark_edge_exposed(u_index, v_index);
            return Ok(attrs);
        }
        let mut v_buf = ArrayString::new();
        let v_key = crate::canonical_node_key_in(py, v, &mut v_buf)?;
        let v_canon = v_key.as_str();
        if let Some(attrs) = g.cached_edge_py_attrs(py, &self.node, v_canon) {
            // br-r37-c1-igdzi: same single edge, reached by name.
            g.mark_edge_exposed_by_name(&self.node, v_canon);
            return Ok(attrs);
        }
        if !g.inner.has_edge(&self.node, v_canon) {
            return Err(PyKeyError::new_err((v.clone().unbind(),)));
        }
        // The returned dict is the SAME shared Py<PyDict> the graph stores, so
        // `G[u][v]['w'] = x` mutates the live edge attrs — flag the edge store
        // dirty so a later native read reconciles it (matches the old eager
        // `G[u]`, which marked dirty unconditionally).
        // br-r37-c1-igdzi: still exactly one edge, so the flag carries its name.
        g.mark_edge_exposed_by_name(&self.node, v_canon);
        let attrs = g.materialize_edge_py_attrs(py, &self.node, v_canon);
        // br-r37-c1-ptiz2: fill the index lookaside with the SAME dict the
        // string-keyed mirror just returned, so the two can never disagree
        // about identity. Only when both indices are known; anything else keeps
        // paying the string path.
        //
        // br-r37-c1-ktsxn: exact `str` OR exact `int`, matching the probe above
        // and the rest of the family. `Graph.adj[u][v]` measured 341.0 ns/call on
        // int node keys against 285.7 on str -- a 1.19x key-type gap on the ONE
        // class whose row subscript is a native C slot, i.e. the one place where
        // this gate is the binding constraint rather than the Python view chain.
        if let Some(u_index) = u_index
            && node_key_can_use_index_lookaside(v)
            && let Some(v_index) = g.cached_exact_string_node_index(py, v)?
        {
            g.remember_edge_py_attrs_by_index(py, u_index, v_index, &attrs);
        }
        Ok(attrs)
    }

    fn __contains__(&self, py: Python<'_>, v: &Bound<'_, PyAny>) -> PyResult<bool> {
        // br-r37-c1-espyz: networkx answers this with `v in self._atlas[node]`,
        // a dict probe that HASHES v — so an unhashable key is a TypeError, not
        // False. `with_node_key_str` below canonicalises by VALUE and never
        // hashes, so `['x'] in G.adj['a']` quietly returned False here while
        // networkx raised. Simple `Graph` was the only class still diverging:
        // its row is this native view (br-r37-c1-ey6ob routes it), while the
        // other three carry the Python `AdjacencyView`, whose `__contains__`
        // got the same explicit guard in br-r37-c1-hcn5w.
        //
        // The guard is nearly free on the hot path: `require_hashable_node_key`
        // short-circuits on an exact `str`/`int`/`float`/`bool`, which are
        // always hashable, so the common shape pays one type check and never
        // hashes. It is applied ahead of BOTH branches so the contract does not
        // depend on whether this view happens to have materialised its row —
        // the materialised branch already raised, via `PyDict::contains`, and
        // an answer that depends on cache state is the bug pattern
        // br-r37-c1-alll4 pinned for node membership.
        crate::require_hashable_node_key(v)?;
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
        // br-r37-c1-do7g5: `try_iter()` is PyObject_GetIter, the C-level slot.
        // `call_method0("__iter__")` looked the method up on the dict's type and
        // called it to build the same `dict_keyiterator`.
        Ok(self
            .materialize(py)?
            .bind(py)
            .try_iter()?
            .into_any()
            .unbind())
    }

    fn keys(mut slf: PyRefMut<'_, Self>, py: Python<'_>) -> PyResult<PyObject> {
        slf.materialize(py)?;
        // br-r37-c1-abccache: cached type, not a per-call import.
        Ok(abc_view_type(py, &ABC_KEYS_VIEW, "KeysView")?
            .call1((slf,))?
            .unbind())
    }

    fn items(mut slf: PyRefMut<'_, Self>, py: Python<'_>) -> PyResult<PyObject> {
        slf.materialize(py)?;
        // br-r37-c1-abccache: cached type, not a per-call import.
        Ok(abc_view_type(py, &ABC_ITEMS_VIEW, "ItemsView")?
            .call1((slf,))?
            .unbind())
    }

    fn values(mut slf: PyRefMut<'_, Self>, py: Python<'_>) -> PyResult<PyObject> {
        slf.materialize(py)?;
        // br-r37-c1-abccache: cached type, not a per-call import.
        Ok(abc_view_type(py, &ABC_VALUES_VIEW, "ValuesView")?
            .call1((slf,))?
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

    // br-r37-c1-ynpbt: A VIEW MUST EQUAL ITSELF.
    //
    // This materialised `self` into a dict and compared `dict == other`,
    // delegating the AtlasView-vs-AtlasView case to Python's reflected
    // comparison. `dict.__eq__(AtlasView)` returns NotImplemented, so Python
    // calls the OTHER view's `__eq__` -- which needs a `borrow_mut` while this
    // method's `&mut self` borrow is still live. The reflected call therefore
    // cannot complete and Python falls back to identity, so `r == r` was
    // FALSE. Reflexivity is a language-level invariant: any caller that put
    // these rows in a set, deduplicated them, or asserted `x == x` was
    // silently wrong.
    //
    // Comparing against a plain dict always worked, which is exactly why this
    // survived -- the natural test writes `row == {...}`.
    //
    // Handled explicitly rather than by reflection now. Identical objects
    // short-circuit; two distinct views compare as their materialised
    // mappings. Each `borrow_mut` is a temporary dropped before the other side
    // is touched, so the nested borrow that broke the reflected path cannot
    // recur.
    //
    // Only simple `Graph` rows reach this class, via the `type(owner) is Graph`
    // fast path in `AdjacencyView.__getitem__`; the other three classes are
    // Python-backed, were already correct, and are the control in
    // `tests/python/test_view_repr_and_equality_parity.py`.
    fn __eq__(slf: &Bound<'_, Self>, other: &Bound<'_, PyAny>) -> PyResult<bool> {
        if slf.is(other) {
            return Ok(true);
        }
        let py = slf.py();
        let mine = slf.borrow_mut().materialize(py)?;
        if let Ok(other_view) = other.downcast::<Self>() {
            let theirs = other_view.borrow_mut().materialize(py)?;
            return mine.bind(py).eq(theirs.bind(py));
        }
        mine.bind(py).eq(other)
    }

    fn __ne__(slf: &Bound<'_, Self>, other: &Bound<'_, PyAny>) -> PyResult<bool> {
        Ok(!Self::__eq__(slf, other)?)
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

    fn __setitem__(&self, _key: &Bound<'_, PyAny>, _value: &Bound<'_, PyAny>) -> PyResult<()> {
        Err(PyTypeError::new_err(
            "'AtlasView' object does not support item assignment",
        ))
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
    let private_adj = graph
        .borrow(py)
        .instance_dict_gc
        .private_adj_mapping(py)?
        .map(pyo3::Bound::unbind);
    Py::new(
        py,
        EdgeView {
            graph,
            data: NodeViewData::NoData,
            private_adj,
        },
    )
}

pub fn new_degree_view(py: Python<'_>, graph: Py<PyGraph>) -> PyResult<Py<DegreeView>> {
    Py::new(py, DegreeView { graph })
}

pub fn new_adjacency_view(py: Python<'_>, graph: Py<PyGraph>) -> PyResult<Py<AdjacencyView>> {
    Py::new(py, AdjacencyView { graph: Some(graph) })
}
