//! PyDiGraph — PyO3 wrapper for directed graph.
//!
//! This mirrors [`PyGraph`] but with directed edge semantics:
//! - `(u, v)` is distinct from `(v, u)`.
//! - `neighbors()` returns successors (matches NetworkX convention).
//! - Additional methods: `predecessors`, `successors`, `in_degree`, `out_degree`.

use crate::{
    NetworkXError, NodeNotFound, PyGraph, PyObject, attr_map_to_pydict,
    collect_index_weight_attr_edges, compatibility_mode_from_py, compatibility_mode_name,
    edge_key_lookup_string, node_key_to_string, py_dict_to_attr_map,
    py_dict_to_attr_map_with_mirror, runtime_policy_from_state, runtime_policy_json,
    unwrap_infallible, weighted_edge_triplet,
};
use fnx_classes::AttrMap;
use fnx_classes::digraph::{DiGraph, MultiDiGraph};
use fnx_runtime::{CgseValue, CompatibilityMode, RuntimePolicy};
use pyo3::IntoPyObjectExt;
use pyo3::exceptions::{PyKeyError, PyRuntimeError, PyTypeError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::{
    PyAny, PyBool, PyDict, PyFloat, PyInt, PyIterator, PyList, PySet, PyString, PyTuple,
};
use std::collections::{HashMap, HashSet, VecDeque};
use std::sync::atomic::{AtomicBool, Ordering};

fn single_weight_float_attr_map(attrs: &Bound<'_, PyDict>) -> PyResult<Option<AttrMap>> {
    if attrs.len() != 1 {
        return Ok(None);
    }
    let Some((key, value)) = attrs.iter().next() else {
        return Ok(None);
    };
    if !key.is_exact_instance_of::<PyString>() || !value.is_exact_instance_of::<PyFloat>() {
        return Ok(None);
    }
    let key_text = key.extract::<String>()?;
    if key_text != "weight" {
        return Ok(None);
    }

    let mut rust_attrs = AttrMap::new();
    rust_attrs.insert(
        "weight".to_owned(),
        CgseValue::Float(value.extract::<f64>()?),
    );
    Ok(Some(rust_attrs))
}

fn single_weight_float_attr_map_with_mirror(
    py: Python<'_>,
    attrs: &Bound<'_, PyDict>,
) -> PyResult<Option<(AttrMap, Py<PyDict>)>> {
    let Some(rust_attrs) = single_weight_float_attr_map(attrs)? else {
        return Ok(None);
    };
    let Some((key, value)) = attrs.iter().next() else {
        return Ok(None);
    };
    let mirror = PyDict::new(py);
    mirror.set_item(&key, &value)?;
    Ok(Some((rust_attrs, mirror.unbind())))
}

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
    /// br-r37-c1-z6uka: per-SUCC-row display objects — nx `_succ[u][v]`
    /// keeps the v object passed in the creating add_edge call. Sparse:
    /// empty for uniform-key graphs (see PyGraph::adj_py_keys).
    pub(crate) succ_py_keys: HashMap<(String, String), PyObject>,
    /// br-r37-c1-z6uka: per-PRED-row display objects — nx `_pred[v][u]`
    /// keeps the u object from the same call (asymmetric to succ for
    /// mixed-type self-loops: add_edge(12.0, 12) -> succ row 12, pred
    /// row 12.0).
    pub(crate) pred_py_keys: HashMap<(String, String), PyObject>,
    pub(crate) succ_row_py: HashMap<String, Py<PyDict>>,
    pub(crate) pred_row_py: HashMap<String, Py<PyDict>>,
    pub(crate) graph_attrs: Py<PyDict>,
    /// br-r37-c1-39d82: see PyGraph::nodes_seq.
    pub(crate) nodes_seq: u64,
    /// br-r37-c1-jft0i: see PyGraph::edges_seq.
    pub(crate) edges_seq: u64,
    /// See PyGraph::edges_dirty.
    pub(crate) edges_dirty: AtomicBool,
    pub(crate) node_keys_cache: std::sync::Mutex<Option<(u64, Py<pyo3::types::PyTuple>)>>,
    /// br-r37-c1-4b5ie: mirror of PyGraph::node_data_mirror — caches the
    /// {node: attr_dict} dict (keyed on nodes_seq) so repeated
    /// nodes(data=...) calls on an unchanged graph reuse it instead of
    /// rebuilding every (node, dict) pair. Gives DiGraph the warm-call
    /// parity Graph already has.
    pub(crate) node_data_mirror: std::sync::Mutex<Option<(u64, Py<PyDict>)>>,
    /// br-r37-c1-eveun: mirror of PyGraph::dict_of_dicts_cache — caches the
    /// successor {node: {succ: edge_attr_dict}} rows keyed on (nodes_seq,
    /// edges_seq). adjacency()/to_dict_of_dicts copy fresh rows out of it so
    /// repeats skip the full rebuild (DiGraph adjacency was uncached -> 21x).
    pub(crate) dict_of_dicts_cache: Option<crate::DictOfDictsCache>,
    /// br-r37-c1-o07ax: (nodes_seq, edges_seq)-keyed cache of the node-major
    /// (u, v, live_attr_dict) tuples backing edges(data=True). Tuples are
    /// immutable and the inner dicts stay live, so repeats return a fresh list
    /// of the same tuple objects instead of rebuilding (was 3x slower than nx).
    pub(crate) edges_with_data_cache: Option<(u64, u64, Vec<PyObject>)>,
    /// br-r37-c1-inedges-cache (cc): in_edges(data=True) analog of
    /// edges_with_data_cache — (nodes_seq, edges_seq)-keyed target-major
    /// (source, target, live_attr) tuples. out_edges(data=True) was 12x faster
    /// than in_edges purely because in_edges rebuilt every call; this caches it.
    pub(crate) in_edges_with_data_cache: Option<(u64, u64, Vec<PyObject>)>,
    /// (nodes_seq, edges_seq)-keyed live attr-dict handles in edge iteration
    /// order for `edges(data=<key>)`. This caches dict lookup by edge, not
    /// attr values, so edge-attr mutations remain visible.
    pub(crate) edges_attr_dicts_cache: Option<(u64, u64, Vec<Py<PyDict>>)>,
    /// Incremental mirror of PyGraph::node_iter_mirror — a live ``{node: None}``
    /// PyDict kept in insertion order. ``iter(G)`` / ``list(G.nodes())`` return
    /// its ``dict_keyiterator`` directly (matching nx's ``iter(self._nodes)``)
    /// instead of rebuilding a ``Vec<PyObject>`` of every display key per call
    /// (was 6-15x slower than nx). It is mutated IN PLACE by every node add /
    /// remove / clear hook so mutation-during-iteration raises CPython's native
    /// "dictionary changed size during iteration" exactly as nx does.
    pub(crate) node_iter_mirror: std::sync::Mutex<Option<Py<PyDict>>>,
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
    /// br-r37-c1-z6uka: per-SUCC-row display objects (see PyDiGraph).
    pub(crate) succ_py_keys: HashMap<(String, String), PyObject>,
    /// br-r37-c1-z6uka: per-PRED-row display objects.
    pub(crate) pred_py_keys: HashMap<(String, String), PyObject>,
    pub(crate) node_py_attrs: HashMap<String, Py<PyDict>>,
    pub(crate) edge_py_attrs: HashMap<(String, String, usize), Py<PyDict>>,
    pub(crate) edge_py_keys: HashMap<(String, String, usize), PyObject>,
    pub(crate) graph_attrs: Py<PyDict>,
    /// br-r37-c1-39d82: see PyGraph::nodes_seq.
    pub(crate) nodes_seq: u64,
    /// br-r37-c1-jft0i: see PyGraph::edges_seq.
    pub(crate) edges_seq: u64,
    /// See PyGraph::edges_dirty.
    pub(crate) edges_dirty: AtomicBool,
    /// Precise maybe-dirty keys for keyed live edge-dict access. `None` means
    /// a broad mutable edge-attr view escaped, so every mirror must be replayed.
    pub(crate) edge_dirty_keys: std::sync::Mutex<Option<HashSet<(String, String, usize)>>>,
    pub(crate) node_keys_cache:
        std::sync::Mutex<Option<(u64, Py<pyo3::types::PyTuple>, Py<pyo3::types::PySet>)>>,
    /// br-r37-c1-4b5ie: see PyGraph::node_data_mirror — nodes_seq-keyed
    /// {node: attr_dict} cache so repeated nodes(data=...) reuse it.
    pub(crate) node_data_mirror: std::sync::Mutex<Option<(u64, Py<PyDict>)>>,
    /// br-r37-c1-pcw2s: (nodes_seq, edges_seq)-keyed nested successor adjacency
    /// {node: {succ: {key: edge_dict}}} cache so repeated adjacency() calls reuse
    /// it instead of rebuilding the 3-level dict (was 47x slower than nx).
    pub(crate) dict_of_dicts_cache: Option<crate::DictOfDictsCache>,
    /// br-r37-c1-o07ax: (nodes_seq, edges_seq)-keyed cache of the node-major
    /// (u, v[, key], live_attr) tuples for edges(data=True, no nbunch). The bool
    /// is the `keys` flag (br-r37-c1-mdgkd, cc): edges(data=True, keys=False) and
    /// edges(keys=True, data=True) are distinct result shapes, cached one-at-a-time
    /// in this slot (last-requested keys variant wins; symmetric to PyMultiGraph).
    pub(crate) edges_with_data_cache: Option<(u64, u64, bool, Vec<PyObject>)>,
    /// br-r37-c1-mdginedges (cc): (nodes_seq, edges_seq)-keyed in_edges(data=True,
    /// keys=False) target-major tuples — analog of edges_with_data_cache for
    /// in_edges. in_edges(data=True) was a pure-Python pred-loop (~11x slower);
    /// this caches the native list so repeats clone instead of rebuilding.
    pub(crate) in_edges_with_data_cache: Option<(u64, u64, Vec<PyObject>)>,
    /// br-r37-c1-qwqvn: (nodes_seq, edges_seq)-keyed cache of immutable
    /// (u, v, key) tuples for edges(keys=True, data=False, no nbunch).
    pub(crate) edges_with_keys_cache: Option<(u64, u64, Vec<PyObject>)>,
    /// Incremental node-iteration mirror — see PyDiGraph::node_iter_mirror.
    /// Live `{node: None}` dict serving iter(G)/list(G.nodes()) as a
    /// dict_keyiterator, mutated in place by node add/remove/clear hooks.
    pub(crate) node_iter_mirror: std::sync::Mutex<Option<Py<PyDict>>>,
}

impl PyMultiDiGraph {
    /// br-r37-c1-qwqvn: cache the immutable no-data keyed edge tuples for the
    /// common all-edge view. Nodes/key display objects are the same first-wins
    /// objects the uncached path would clone; graph mutation bumps a sequence and
    /// invalidates the tuple list.
    pub(crate) fn edges_key_tuples(&mut self, py: Python<'_>) -> PyResult<Vec<PyObject>> {
        let valid = matches!(
            &self.edges_with_keys_cache,
            Some((ns, es, _)) if *ns == self.nodes_seq && *es == self.edges_seq
        );
        if !valid {
            let edges: Vec<(String, String, usize)> = self
                .inner
                .edges_ordered_borrowed()
                .into_iter()
                .map(|(source, target, key, _attrs)| (source.to_owned(), target.to_owned(), key))
                .collect();
            let mut result: Vec<PyObject> = Vec::with_capacity(edges.len());
            for (source, target, key) in &edges {
                let py_u = self.py_node_key(py, source);
                let py_v = self.py_succ_key(py, source, target);
                let py_key = self.py_edge_key(py, source, target, *key);
                result.push(tuple_object(py, &[py_u, py_v, py_key])?);
            }
            self.edges_with_keys_cache = Some((self.nodes_seq, self.edges_seq, result));
        }
        let cached = self
            .edges_with_keys_cache
            .as_ref()
            .map(|(_, _, tuples)| tuples)
            .ok_or_else(|| PyRuntimeError::new_err("edge key tuple cache missing"))?;
        Ok(cached.iter().map(|tuple| tuple.clone_ref(py)).collect())
    }

    /// br-r37-c1-o07ax: build (and cache) the node-major (u, v, live_attr) tuples
    /// for edges(data=True, keys=False) — the same AllData/!keys branch as
    /// MultiDiGraphEdgeView.__call__, served from a (nodes_seq, edges_seq) cache.
    pub(crate) fn edges_alldata_tuples(&mut self, py: Python<'_>) -> PyResult<Vec<PyObject>> {
        if self.inner.edge_count() > 0 {
            self.mark_edges_dirty();
        }
        let valid = matches!(
            &self.edges_with_data_cache,
            Some((ns, es, keys, _)) if *ns == self.nodes_seq && *es == self.edges_seq && !*keys
        );
        if !valid {
            let edges: Vec<(String, String, usize)> = self
                .inner
                .edges_ordered()
                .into_iter()
                .map(|edge| (edge.source.to_owned(), edge.target.to_owned(), edge.key))
                .collect();
            let mut result: Vec<PyObject> = Vec::with_capacity(edges.len());
            for (source, target, key) in &edges {
                let py_u = self.py_node_key(py, source);
                let py_v = self.py_succ_key(py, source, target);
                let attrs = self
                    .ensure_edge_py_attrs(py, source, target, *key)
                    .clone_ref(py)
                    .into_any();
                result.push(tuple_object(py, &[py_u, py_v, attrs])?);
            }
            self.edges_with_data_cache = Some((self.nodes_seq, self.edges_seq, false, result));
        }
        let cached = &self.edges_with_data_cache.as_ref().unwrap().3;
        Ok(cached.iter().map(|t| t.clone_ref(py)).collect())
    }

    /// Build the all-edge ``edges(keys=True, data=True)`` result in one pass when
    /// every edge already has its live Python attr mirror. Plain/sparse edges fall
    /// back to the generic path, which materializes missing mirrors before return.
    pub(crate) fn edges_key_alldata_existing_mirrors(
        &self,
        py: Python<'_>,
    ) -> PyResult<Option<Vec<PyObject>>> {
        let edges = self.inner.edges_ordered_borrowed();
        let mut result: Vec<PyObject> = Vec::with_capacity(edges.len());
        for (source, target, key, _attrs) in edges {
            let Some(attrs) = self.edge_py_attrs.get(&Self::edge_key(source, target, key)) else {
                return Ok(None);
            };
            let py_u = self.py_node_key(py, source);
            let py_v = self.py_succ_key(py, source, target);
            let py_key = self.py_edge_key(py, source, target, key);
            let attrs = attrs.clone_ref(py).into_any();
            result.push(tuple_object(py, &[py_u, py_v, py_key, attrs])?);
        }
        Ok(Some(result))
    }

    /// Native all-edge list for MultiDiGraph.edges(...), matching the Python
    /// wrapper's no-nbunch tuple shapes while avoiding a Python pass over a
    /// native NodeIterator just to populate the final list subclass.
    fn native_edge_view_list(
        &mut self,
        py: Python<'_>,
        data: &Bound<'_, PyAny>,
        keys: bool,
        default: PyObject,
    ) -> PyResult<Vec<PyObject>> {
        let data_is_bool = data.is_instance_of::<PyBool>();
        let want_dict = data_is_bool && data.extract::<bool>()?;
        let want_value = !data_is_bool;
        if want_dict && self.inner.edge_count() > 0 {
            self.mark_edges_dirty();
        }
        if keys && !want_dict && !want_value {
            return self.edges_key_tuples(py);
        }
        if want_dict && !keys {
            return self.edges_alldata_tuples(py);
        }
        if want_dict && keys {
            // br-r37-c1-mdgkd (cc): serve/repopulate the keys+data variant from the
            // shared edges_with_data_cache (flag=true). Previously this combo had no
            // cache and rebuilt every call (materializing empty mirrors) -> 0.78x.
            let valid = matches!(
                &self.edges_with_data_cache,
                Some((ns, es, k, _)) if *ns == self.nodes_seq && *es == self.edges_seq && *k
            );
            if valid {
                let cached = &self.edges_with_data_cache.as_ref().unwrap().3;
                return Ok(cached.iter().map(|t| t.clone_ref(py)).collect());
            }
            if let Some(result) = self.edges_key_alldata_existing_mirrors(py)? {
                self.edges_with_data_cache = Some((
                    self.nodes_seq,
                    self.edges_seq,
                    true,
                    result.iter().map(|t| t.clone_ref(py)).collect(),
                ));
                return Ok(result);
            }
        }

        let edges: Vec<(String, String, usize)> = self
            .inner
            .edges_ordered_borrowed()
            .into_iter()
            .map(|(source, target, key, _attrs)| (source.to_owned(), target.to_owned(), key))
            .collect();
        let mut result: Vec<PyObject> = Vec::with_capacity(edges.len());
        for (source, target, key) in &edges {
            let py_u = self.py_node_key(py, source);
            let py_v = self.py_succ_key(py, source, target);
            let py_key = self.py_edge_key(py, source, target, *key);
            let item = if want_dict {
                let attrs = self
                    .ensure_edge_py_attrs(py, source, target, *key)
                    .clone_ref(py)
                    .into_any();
                tuple_object(py, &[py_u, py_v, py_key, attrs])?
            } else if want_value {
                let val = self
                    .ensure_edge_py_attrs(py, source, target, *key)
                    .bind(py)
                    .get_item(data)
                    .ok()
                    .flatten()
                    .map_or_else(|| default.clone_ref(py), |v| v.unbind());
                if keys {
                    tuple_object(py, &[py_u, py_v, py_key, val])?
                } else {
                    tuple_object(py, &[py_u, py_v, val])?
                }
            } else if keys {
                tuple_object(py, &[py_u, py_v, py_key])?
            } else {
                tuple_object(py, &[py_u, py_v])?
            };
            result.push(item);
        }
        if want_dict && keys {
            // cache the generic-loop keys+data result (mirrors materialized above)
            self.edges_with_data_cache = Some((
                self.nodes_seq,
                self.edges_seq,
                true,
                result.iter().map(|t| t.clone_ref(py)).collect(),
            ));
        }
        Ok(result)
    }
}

impl PyMultiDiGraph {
    fn edge_key(u: &str, v: &str, key: usize) -> (String, String, usize) {
        (u.to_owned(), v.to_owned(), key)
    }

    /// br-r37-c1-degnbnative (cc): shared impl for MultiDiGraph degree(nbunch)
    /// subset kernels (in/out/total multiplicity degree). String-based (multi
    /// inner has no by-index degree); absent nodes skipped; unhashable element ->
    /// TypeError(exact msg) for the wrapper to map to NetworkXError.
    fn degree_pairs_subset_impl(
        &self,
        py: Python<'_>,
        nbunch: &Bound<'_, PyAny>,
        kind: DegreeKind,
    ) -> PyResult<Vec<(PyObject, usize)>> {
        let mut out: Vec<(PyObject, usize)> = Vec::new();
        for item in nbunch.try_iter()? {
            let node = item?;
            if node.hash().is_err() {
                let label = node
                    .str()
                    .map(|s| s.to_string_lossy().into_owned())
                    .unwrap_or_else(|_| "?".to_owned());
                return Err(pyo3::exceptions::PyTypeError::new_err(format!(
                    "Node {label} in sequence nbunch is not a valid node."
                )));
            }
            let canonical = node_key_to_string(py, &node)?;
            if self.inner.has_node(&canonical) {
                let deg = match kind {
                    DegreeKind::In => self.inner.in_degree(&canonical),
                    DegreeKind::Out => self.inner.out_degree(&canonical),
                    DegreeKind::Total => self.inner.degree(&canonical),
                };
                out.push((node.clone().unbind(), deg));
            }
        }
        Ok(out)
    }

    pub(crate) fn clean_edge_dirty_keys()
    -> std::sync::Mutex<Option<HashSet<(String, String, usize)>>> {
        std::sync::Mutex::new(Some(HashSet::new()))
    }

    fn cloned_edge_dirty_keys(&self) -> std::sync::Mutex<Option<HashSet<(String, String, usize)>>> {
        std::sync::Mutex::new(self.edge_dirty_keys.lock().unwrap().clone())
    }

    fn should_sync_dirty_edge(
        dirty_keys: &Option<HashSet<(String, String, usize)>>,
        u: &str,
        v: &str,
        key: usize,
    ) -> bool {
        match dirty_keys {
            None => true,
            Some(keys) => keys.contains(&Self::edge_key(u, v, key)),
        }
    }

    fn py_dict_is_lossless_attr_map(attrs: &Bound<'_, PyDict>) -> bool {
        attrs.iter().all(|(key, value)| {
            key.is_exact_instance_of::<PyString>()
                && (value.is_exact_instance_of::<PyBool>()
                    || value.is_exact_instance_of::<PyInt>()
                    || value.is_exact_instance_of::<PyFloat>()
                    || value.is_exact_instance_of::<PyString>())
        })
    }

    fn ensure_edge_py_attrs(
        &mut self,
        py: Python<'_>,
        u: &str,
        v: &str,
        key: usize,
    ) -> &Py<PyDict> {
        let ek = Self::edge_key(u, v, key);
        if !self.edge_py_attrs.contains_key(&ek) {
            let dict = match self.inner.edge_attrs(u, v, key) {
                Some(attrs) => attr_map_to_pydict(py, attrs)
                    .expect("stored string-keyed edge attrs must convert to Python"),
                None => PyDict::new(py).unbind(),
            };
            self.edge_py_attrs.insert(ek.clone(), dict);
        }
        self.edge_py_attrs
            .get(&ek)
            .expect("edge attr entry inserted above")
    }

    fn edge_data_value_or_default(
        &mut self,
        py: Python<'_>,
        u: &str,
        v: &str,
        key: usize,
        data: &Bound<'_, PyAny>,
        default_obj: &PyObject,
    ) -> PyResult<PyObject> {
        let ek = Self::edge_key(u, v, key);
        if let Some(attrs) = self.edge_py_attrs.get(&ek) {
            return Ok(attrs
                .bind(py)
                .get_item(data)
                .ok()
                .flatten()
                .map_or_else(|| default_obj.clone_ref(py), |value| value.unbind()));
        }

        if let Ok(attr_name) = data.downcast::<PyString>() {
            let attr_name = attr_name.to_str()?;
            if let Some(value) = self
                .inner
                .edge_attrs(u, v, key)
                .and_then(|attrs| attrs.get(attr_name))
                .cloned()
            {
                if matches!(value, CgseValue::Map(_)) {
                    let attrs = self.ensure_edge_py_attrs(py, u, v, key);
                    return Ok(attrs
                        .bind(py)
                        .get_item(data)
                        .ok()
                        .flatten()
                        .map_or_else(|| default_obj.clone_ref(py), |value| value.unbind()));
                }
                return crate::cgse_value_to_py(py, &value);
            }
        }

        Ok(default_obj.clone_ref(py))
    }

    /// Native `MultiDiGraph(Graph)` constructor body.
    ///
    /// The Python fallback walks `source.nodes(data=True)` and
    /// `source.edges(data=True)`, builds a bidirected edge list, then replays it
    /// through `add_edges_from`. For exact in-package `Graph` sources we can copy
    /// the Rust core in source adjacency-row order instead, preserving nx's
    /// `Graph.to_directed()` expansion: every undirected edge becomes `(u, v, 0)`
    /// and `(v, u, 0)`, while self-loops appear once.
    fn absorb_graph_bidirected_from_graph(
        &mut self,
        py: Python<'_>,
        source: PyRef<'_, PyGraph>,
    ) -> PyResult<bool> {
        if !source.adj_py_keys.is_empty() {
            // Mixed-display adjacency cells need the Python replay path to
            // preserve per-row display objects exactly.
            return Ok(false);
        }

        let graph_attrs = PyDict::new(py);
        graph_attrs.update(source.graph_attrs.bind(py).as_mapping())?;

        let nodes: Vec<String> = source
            .inner
            .nodes_ordered()
            .into_iter()
            .map(str::to_owned)
            .collect();
        let mut node_key_map: HashMap<String, PyObject> = HashMap::with_capacity(nodes.len());
        let mut node_py_attrs: HashMap<String, Py<PyDict>> = HashMap::new();
        let mut nodes_bulk: Vec<(String, AttrMap)> = Vec::with_capacity(nodes.len());
        for node in &nodes {
            node_key_map.insert(node.clone(), source.py_node_key(py, node));
            let mut rust_attrs = AttrMap::new();
            if let Some(py_attrs) = source.node_py_attrs.get(node) {
                let bound = py_attrs.bind(py);
                if !bound.is_empty() {
                    rust_attrs = py_dict_to_attr_map(bound)?;
                    if rust_attrs
                        .keys()
                        .any(|key| key.starts_with("__fnx_incompatible"))
                    {
                        return Ok(false);
                    }
                    let mirror = PyDict::new(py);
                    mirror.update(bound.as_mapping())?;
                    node_py_attrs.insert(node.clone(), mirror.unbind());
                }
            } else if let Some(attrs) = source.inner.node_attrs(node)
                && !attrs.is_empty()
            {
                if attrs
                    .keys()
                    .any(|key| key.starts_with("__fnx_incompatible"))
                {
                    return Ok(false);
                }
                rust_attrs = attrs.clone();
                node_py_attrs.insert(node.clone(), attr_map_to_pydict(py, attrs)?);
            }
            nodes_bulk.push((node.clone(), rust_attrs));
        }

        let mut edge_py_attrs: HashMap<(String, String, usize), Py<PyDict>> = HashMap::new();
        let mut edges_bulk: Vec<(String, String, usize, AttrMap)> = Vec::new();
        for u in &nodes {
            let Some(neighbors) = source.inner.neighbors(u) else {
                continue;
            };
            for v in neighbors {
                let edge_key = PyGraph::edge_key(u, v);
                let (rust_attrs, mirror) =
                    if let Some(py_attrs) = source.edge_py_attrs.get(&edge_key) {
                        let bound = py_attrs.bind(py);
                        let attrs = if bound.is_empty() {
                            AttrMap::new()
                        } else {
                            let attrs = py_dict_to_attr_map(bound)?;
                            if attrs
                                .keys()
                                .any(|key| key.starts_with("__fnx_incompatible"))
                            {
                                return Ok(false);
                            }
                            attrs
                        };
                        let mirror = if bound.is_empty() {
                            None
                        } else {
                            let dict = PyDict::new(py);
                            dict.update(bound.as_mapping())?;
                            Some(dict.unbind())
                        };
                        (attrs, mirror)
                    } else if let Some(attrs) = source.inner.edge_attrs(u, v) {
                        if attrs
                            .keys()
                            .any(|key| key.starts_with("__fnx_incompatible"))
                        {
                            return Ok(false);
                        }
                        let mirror = if attrs.is_empty() {
                            None
                        } else {
                            Some(attr_map_to_pydict(py, attrs)?)
                        };
                        (attrs.clone(), mirror)
                    } else {
                        (AttrMap::new(), None)
                    };
                let key = 0_usize;
                let target = v.to_owned();
                if let Some(mirror) = mirror {
                    edge_py_attrs.insert(Self::edge_key(u, &target, key), mirror);
                }
                edges_bulk.push((u.clone(), target, key, rust_attrs));
            }
        }

        let mut inner = MultiDiGraph::new(source.inner.mode());
        let _ = inner.extend_nodes_with_attrs_unrecorded(nodes_bulk);
        let _ = inner.extend_keyed_edges_with_attrs_unrecorded(edges_bulk);

        self.inner = inner;
        self.node_key_map = node_key_map;
        self.succ_py_keys.clear();
        self.pred_py_keys.clear();
        self.node_py_attrs = node_py_attrs;
        self.edge_py_attrs = edge_py_attrs;
        self.edge_py_keys.clear();
        self.graph_attrs = graph_attrs.unbind();
        self.dict_of_dicts_cache = None;
        self.edges_with_data_cache = None;
        self.node_keys_cache = std::sync::Mutex::new(None);
        self.node_data_mirror = std::sync::Mutex::new(None);
        self.node_iter_mirror = std::sync::Mutex::new(None);
        self.bump_nodes_seq();
        self.bump_edges_seq();
        Ok(true)
    }

    /// br-r37-c1-mdgdig (cc): exact `MultiDiGraph(DiGraph)` copy-constructor
    /// absorb — the directional analog of `absorb_graph_bidirected_from_graph`.
    /// Each source directed edge (u, v) becomes a key-0 MultiDiGraph edge in
    /// node-major successor-row order; NO bidirection (the source is already
    /// directed, so each edge appears exactly once via `successors`). Replaces
    /// ALL of self's state wholesale (the clear()+rebuild the Python replay path
    /// otherwise performs). Returns Ok(false) (fall through to the Python
    /// replay) on mixed-display rows or `__fnx_incompatible` attrs.
    fn absorb_digraph_keyed_from_digraph(
        &mut self,
        py: Python<'_>,
        source: PyRef<'_, PyDiGraph>,
    ) -> PyResult<bool> {
        if !source.succ_py_keys.is_empty() || !source.pred_py_keys.is_empty() {
            // Mixed-display adjacency cells need the Python replay path to
            // preserve per-row display objects exactly.
            return Ok(false);
        }

        let graph_attrs = PyDict::new(py);
        graph_attrs.update(source.graph_attrs.bind(py).as_mapping())?;

        let nodes: Vec<String> = source
            .inner
            .nodes_ordered()
            .into_iter()
            .map(str::to_owned)
            .collect();
        let mut node_key_map: HashMap<String, PyObject> = HashMap::with_capacity(nodes.len());
        let mut node_py_attrs: HashMap<String, Py<PyDict>> = HashMap::new();
        let mut nodes_bulk: Vec<(String, AttrMap)> = Vec::with_capacity(nodes.len());
        for node in &nodes {
            node_key_map.insert(node.clone(), source.py_node_key(py, node));
            let mut rust_attrs = AttrMap::new();
            if let Some(py_attrs) = source.node_py_attrs.get(node) {
                let bound = py_attrs.bind(py);
                if !bound.is_empty() {
                    rust_attrs = py_dict_to_attr_map(bound)?;
                    if rust_attrs
                        .keys()
                        .any(|key| key.starts_with("__fnx_incompatible"))
                    {
                        return Ok(false);
                    }
                    let mirror = PyDict::new(py);
                    mirror.update(bound.as_mapping())?;
                    node_py_attrs.insert(node.clone(), mirror.unbind());
                }
            } else if let Some(attrs) = source.inner.node_attrs(node)
                && !attrs.is_empty()
            {
                if attrs
                    .keys()
                    .any(|key| key.starts_with("__fnx_incompatible"))
                {
                    return Ok(false);
                }
                rust_attrs = attrs.clone();
                node_py_attrs.insert(node.clone(), attr_map_to_pydict(py, attrs)?);
            }
            nodes_bulk.push((node.clone(), rust_attrs));
        }

        let mut edge_py_attrs: HashMap<(String, String, usize), Py<PyDict>> = HashMap::new();
        let mut edges_bulk: Vec<(String, String, usize, AttrMap)> = Vec::new();
        for u in &nodes {
            let Some(neighbors) = source.inner.successors(u) else {
                continue;
            };
            for v in neighbors {
                let edge_key = PyDiGraph::edge_key(u, v);
                let (rust_attrs, mirror) =
                    if let Some(py_attrs) = source.edge_py_attrs.get(&edge_key) {
                        let bound = py_attrs.bind(py);
                        let attrs = if bound.is_empty() {
                            AttrMap::new()
                        } else {
                            let attrs = py_dict_to_attr_map(bound)?;
                            if attrs
                                .keys()
                                .any(|key| key.starts_with("__fnx_incompatible"))
                            {
                                return Ok(false);
                            }
                            attrs
                        };
                        let mirror = if bound.is_empty() {
                            None
                        } else {
                            let dict = PyDict::new(py);
                            dict.update(bound.as_mapping())?;
                            Some(dict.unbind())
                        };
                        (attrs, mirror)
                    } else if let Some(attrs) = source.inner.edge_attrs(u, v) {
                        if attrs
                            .keys()
                            .any(|key| key.starts_with("__fnx_incompatible"))
                        {
                            return Ok(false);
                        }
                        let mirror = if attrs.is_empty() {
                            None
                        } else {
                            Some(attr_map_to_pydict(py, attrs)?)
                        };
                        (attrs.clone(), mirror)
                    } else {
                        (AttrMap::new(), None)
                    };
                let key = 0_usize;
                let target = v.to_owned();
                if let Some(mirror) = mirror {
                    edge_py_attrs.insert(Self::edge_key(u, &target, key), mirror);
                }
                edges_bulk.push((u.clone(), target, key, rust_attrs));
            }
        }

        let mut inner = MultiDiGraph::new(source.inner.mode());
        let _ = inner.extend_nodes_with_attrs_unrecorded(nodes_bulk);
        let _ = inner.extend_keyed_edges_with_attrs_unrecorded(edges_bulk);

        self.inner = inner;
        self.node_key_map = node_key_map;
        self.succ_py_keys.clear();
        self.pred_py_keys.clear();
        self.node_py_attrs = node_py_attrs;
        self.edge_py_attrs = edge_py_attrs;
        self.edge_py_keys.clear();
        self.graph_attrs = graph_attrs.unbind();
        self.dict_of_dicts_cache = None;
        self.edges_with_data_cache = None;
        self.node_keys_cache = std::sync::Mutex::new(None);
        self.node_data_mirror = std::sync::Mutex::new(None);
        self.node_iter_mirror = std::sync::Mutex::new(None);
        self.bump_nodes_seq();
        self.bump_edges_seq();
        Ok(true)
    }

    /// br-r37-c1-4b5ie: canonical (stored) attr dict — allocate+store empty on
    /// first touch so the data mirror caches the SAME object later writes hit.
    pub(crate) fn materialize_node_py_attrs(
        &mut self,
        py: Python<'_>,
        canonical: &str,
    ) -> Py<PyDict> {
        self.node_py_attrs
            .entry(canonical.to_owned())
            .or_insert_with(|| PyDict::new(py).unbind())
            .clone_ref(py)
    }

    /// br-r37-c1-4b5ie: mirror of PyGraph::node_data_items_view — cache
    /// {node: attr_dict} keyed on nodes_seq and return its `.items()`.
    pub(crate) fn node_data_items_view(&mut self, py: Python<'_>) -> PyResult<PyObject> {
        let seq = self.nodes_seq;
        if let Some(dict) = self
            .node_data_mirror
            .lock()
            .unwrap()
            .as_ref()
            .and_then(|(cached_seq, dict)| (*cached_seq == seq).then(|| dict.clone_ref(py)))
        {
            return Ok(dict.bind(py).call_method0("items")?.unbind());
        }
        let nodes: Vec<String> = self
            .inner
            .nodes_ordered()
            .iter()
            .map(|node| (*node).to_owned())
            .collect();
        let dict = PyDict::new(py);
        for node in &nodes {
            let py_key = self.py_node_key(py, node);
            let attrs = self.materialize_node_py_attrs(py, node);
            dict.set_item(py_key, attrs.bind(py))?;
        }
        let owned = dict.unbind();
        *self.node_data_mirror.lock().unwrap() = Some((seq, owned.clone_ref(py)));
        Ok(owned.bind(py).call_method0("items")?.unbind())
    }

    /// br-r37-c1-natdiff: canonical lookup string of the DISPLAY edge key for
    /// `(u, v, internal_key)` — the form nx compares in set-ops. With no
    /// `edge_py_keys` entry the display key is the internal usize as an int, so
    /// `edge_key_lookup_string` of it is `"int:{key}"`.
    fn display_key_lookup(&self, py: Python<'_>, u: &str, v: &str, key: usize) -> PyResult<String> {
        match self.edge_py_keys.get(&Self::edge_key(u, v, key)) {
            Some(obj) => crate::edge_key_lookup_string(py, obj.bind(py)),
            None => Ok(format!("int:{key}")),
        }
    }

    /// br-r37-c1-urle5: display-conflict guard for the plain-edge batch (mirrors
    /// `PyDiGraph::batch_display_conflict`).
    fn batch_display_conflict(
        &self,
        py: Python<'_>,
        canonical: &str,
        passed: &Bound<'_, PyAny>,
        batch_first: &mut HashMap<String, PyObject>,
    ) -> bool {
        if passed.is_exact_instance_of::<PyString>() {
            return false;
        }
        if let Some(stored) = self.node_key_map.get(canonical) {
            return crate::PyGraph::display_objs_conflict(stored.bind(py), passed);
        }
        if let Some(first) = batch_first.get(canonical) {
            return crate::PyGraph::display_objs_conflict(first.bind(py), passed);
        }
        batch_first.insert(canonical.to_owned(), passed.clone().unbind());
        false
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

    /// br-r37-c1-fpssi: all node display objects as a Vec, reusing the
    /// nodes_seq-keyed tuple cache (clone_ref of cached elements) instead of
    /// rebuilding via py_node_key per node. Backs the graph node iterator
    /// (`set(G)` / `for n in G`), which keeps its per-next nodes_seq guard.
    // br-r37-c1-qwqvn: infra for the pending MultiDiGraph edges() index lever
    // (symmetric with the wired PyGraph/PyDiGraph variants); not yet a consumer.
    #[allow(dead_code)]
    pub(crate) fn cached_node_key_vec(&self, py: Python<'_>) -> Vec<PyObject> {
        let seq = self.nodes_seq;
        {
            let guard = self.node_keys_cache.lock().unwrap();
            if let Some((cached_seq, tup, _set)) = guard.as_ref()
                && *cached_seq == seq
            {
                return tup.bind(py).iter().map(|o| o.unbind()).collect();
            }
        }
        let keys: Vec<PyObject> = self
            .inner
            .nodes_ordered()
            .into_iter()
            .map(|n| self.py_node_key(py, n))
            .collect();
        let tup = pyo3::types::PyTuple::new(py, &keys)
            .expect("node-keys tuple")
            .unbind();
        let set = PySet::new(py, keys.iter()).expect("node-keys set").unbind();
        *self.node_keys_cache.lock().unwrap() = Some((seq, tup.clone_ref(py), set));
        keys
    }

    /// Incremental node-iteration mirror (see PyDiGraph::node_iter_mirror_or_init).
    pub(crate) fn node_iter_mirror_or_init(&self, py: Python<'_>) -> PyResult<Py<PyDict>> {
        if let Some(dict) = self
            .node_iter_mirror
            .lock()
            .unwrap()
            .as_ref()
            .map(|dict| dict.clone_ref(py))
        {
            return Ok(dict);
        }
        let dict = PyDict::new(py);
        for canonical in self.inner.nodes_ordered() {
            dict.set_item(self.py_node_key(py, canonical), py.None())?;
        }
        let owned = dict.unbind();
        *self.node_iter_mirror.lock().unwrap() = Some(owned.clone_ref(py));
        Ok(owned)
    }

    fn node_iter_mirror_active(&self) -> bool {
        self.node_iter_mirror.lock().unwrap().is_some()
    }

    fn node_iter_mirror_insert(&self, py: Python<'_>, canonical: &str) -> PyResult<()> {
        let Some(dict) = self
            .node_iter_mirror
            .lock()
            .unwrap()
            .as_ref()
            .map(|dict| dict.clone_ref(py))
        else {
            return Ok(());
        };
        dict.bind(py)
            .set_item(self.py_node_key(py, canonical), py.None())
    }

    fn node_iter_mirror_remove_key(&self, py: Python<'_>, key: &Bound<'_, PyAny>) {
        let Some(dict) = self
            .node_iter_mirror
            .lock()
            .unwrap()
            .as_ref()
            .map(|dict| dict.clone_ref(py))
        else {
            return;
        };
        let _ = dict.bind(py).del_item(key);
    }

    fn node_iter_mirror_clear(&self, py: Python<'_>) -> PyResult<()> {
        let Some(dict) = self
            .node_iter_mirror
            .lock()
            .unwrap()
            .as_ref()
            .map(|dict| dict.clone_ref(py))
        else {
            return Ok(());
        };
        dict.bind(py).call_method0("clear")?;
        Ok(())
    }

    fn multi_row_keydict(
        &self,
        py: Python<'_>,
        source: &str,
        target: &str,
    ) -> PyResult<Py<PyDict>> {
        let kd = PyDict::new(py);
        for key in self.inner.edge_keys(source, target).unwrap_or_default() {
            let edge_key = PyMultiDiGraph::edge_key(source, target, key);
            let attrs = self
                .edge_py_attrs
                .get(&edge_key)
                .map_or_else(|| PyDict::new(py).unbind(), |d| d.clone_ref(py));
            kd.set_item(self.py_edge_key(py, source, target, key), attrs.bind(py))?;
        }
        Ok(kd.unbind())
    }

    fn py_edge_key(&self, py: Python<'_>, u: &str, v: &str, key: usize) -> PyObject {
        self.edge_py_keys
            .get(&Self::edge_key(u, v, key))
            .map_or_else(
                || unwrap_infallible(key.into_pyobject(py)).into_any().unbind(),
                |obj| obj.clone_ref(py),
            )
    }

    /// br-r37-c1-z6uka: succ-cell display object (see PyDiGraph::py_succ_key;
    /// a multi cell is created by the FIRST key of a (u, v) pair and parallel
    /// keys reuse it).
    pub(crate) fn py_succ_key(&self, py: Python<'_>, owner: &str, nbr: &str) -> PyObject {
        if !self.succ_py_keys.is_empty()
            && let Some(obj) = self.succ_py_keys.get(&(owner.to_owned(), nbr.to_owned()))
        {
            return obj.clone_ref(py);
        }
        self.py_node_key(py, nbr)
    }

    /// br-r37-c1-z6uka: pred-cell display object.
    pub(crate) fn py_pred_key(&self, py: Python<'_>, owner: &str, nbr: &str) -> PyObject {
        if !self.pred_py_keys.is_empty()
            && let Some(obj) = self.pred_py_keys.get(&(owner.to_owned(), nbr.to_owned()))
        {
            return obj.clone_ref(py);
        }
        self.py_node_key(py, nbr)
    }

    /// br-r37-c1-z6uka: record per-cell overrides for a NEWLY created
    /// (u, v) cell — succ[u][v] keeps v's object, pred[v][u] keeps u's
    /// (both apply for self-loops: distinct dict cells in nx).
    fn maybe_store_row_keys(
        &mut self,
        py: Python<'_>,
        u_canonical: &str,
        v_canonical: &str,
        u: &Bound<'_, PyAny>,
        v: &Bound<'_, PyAny>,
    ) {
        let differs = |canonical: &str, passed: &Bound<'_, PyAny>| -> bool {
            self.node_key_map.get(canonical).is_some_and(|stored| {
                crate::PyGraph::display_objs_conflict(stored.bind(py), passed)
            })
        };
        if differs(v_canonical, v) {
            self.succ_py_keys
                .entry((u_canonical.to_owned(), v_canonical.to_owned()))
                .or_insert_with(|| v.clone().unbind());
        }
        if differs(u_canonical, u) {
            self.pred_py_keys
                .entry((v_canonical.to_owned(), u_canonical.to_owned()))
                .or_insert_with(|| u.clone().unbind());
        }
    }

    fn remember_edge_key(
        &mut self,
        py: Python<'_>,
        u: &str,
        v: &str,
        key: usize,
        external_key: Option<&Bound<'_, PyAny>>,
    ) -> PyObject {
        let py_key = external_key.map_or_else(
            || unwrap_infallible(key.into_pyobject(py)).into_any().unbind(),
            |value| value.clone().unbind(),
        );
        // br-r37-c1-edgekeyfirstwins: see lib.rs::remember_edge_key
        // for the rationale — nx dict-based edge-key storage means
        // first-Py-form-added wins for display, while add_edge
        // returns the user-provided Py-form for echo.
        self.edge_py_keys
            .entry(Self::edge_key(u, v, key))
            .or_insert_with(|| py_key.clone_ref(py));
        py_key
    }

    pub(crate) fn remember_edge_key_object(
        &mut self,
        py: Python<'_>,
        u: &str,
        v: &str,
        key: usize,
        external_key: &PyObject,
    ) {
        // First-wins: see remember_edge_key above.
        self.edge_py_keys
            .entry(Self::edge_key(u, v, key))
            .or_insert_with(|| external_key.clone_ref(py));
    }

    fn resolve_internal_edge_key(
        &self,
        py: Python<'_>,
        u: &str,
        v: &str,
        key: &Bound<'_, PyAny>,
    ) -> PyResult<Option<usize>> {
        let requested = edge_key_lookup_string(py, key)?;
        for internal_key in self.inner.edge_keys(u, v).unwrap_or_default() {
            let stored_key = self.py_edge_key(py, u, v, internal_key);
            if edge_key_lookup_string(py, stored_key.bind(py).as_any())? == requested {
                return Ok(Some(internal_key));
            }
        }
        Ok(None)
    }

    fn remove_edge_metadata(&mut self, u: &str, v: &str, key: usize) {
        let ek = Self::edge_key(u, v, key);
        self.edge_py_attrs.remove(&ek);
        self.edge_py_keys.remove(&ek);
    }

    pub(crate) fn new_empty_with_mode(py: Python<'_>, mode: CompatibilityMode) -> PyResult<Self> {
        Self::new_empty_with_policy(py, RuntimePolicy::new(mode))
    }

    pub(crate) fn new_empty_with_policy(
        py: Python<'_>,
        runtime_policy: RuntimePolicy,
    ) -> PyResult<Self> {
        Ok(Self {
            inner: MultiDiGraph::with_runtime_policy(runtime_policy),
            node_key_map: HashMap::new(),
            succ_py_keys: HashMap::new(), // br-r37-c1-z6uka
            pred_py_keys: HashMap::new(), // br-r37-c1-z6uka
            node_py_attrs: HashMap::new(),
            edge_py_attrs: HashMap::new(),
            edge_py_keys: HashMap::new(),
            graph_attrs: PyDict::new(py).unbind(),
            nodes_seq: 0,
            edges_seq: 0,
            edges_dirty: AtomicBool::new(false),
            edge_dirty_keys: Self::clean_edge_dirty_keys(),
            node_keys_cache: std::sync::Mutex::new(None),
            node_data_mirror: std::sync::Mutex::new(None),
            dict_of_dicts_cache: None,
            edges_with_data_cache: None,
            in_edges_with_data_cache: None,
            edges_with_keys_cache: None,
            node_iter_mirror: std::sync::Mutex::new(None),
        })
    }

    /// br-r37-c1-39d82: see PyGraph::bump_nodes_seq.
    #[inline]
    pub(crate) fn bump_nodes_seq(&mut self) {
        self.nodes_seq = self.nodes_seq.wrapping_add(1);
    }

    /// br-r37-c1-jft0i: see PyGraph::bump_edges_seq.
    #[inline]
    pub(crate) fn bump_edges_seq(&mut self) {
        self.edges_seq = self.edges_seq.wrapping_add(1);
    }

    #[inline]
    pub(crate) fn mark_edges_dirty(&self) {
        self.edges_dirty.store(true, Ordering::Relaxed);
        *self.edge_dirty_keys.lock().unwrap() = None;
    }

    fn mark_edge_dirty(&self, u: &str, v: &str, key: usize) {
        self.edges_dirty.store(true, Ordering::Relaxed);
        if let Some(keys) = self.edge_dirty_keys.lock().unwrap().as_mut() {
            keys.insert(Self::edge_key(u, v, key));
        }
    }

    fn try_absorb_exact_int_str_keyed_ctor_edges(
        &mut self,
        py: Python<'_>,
        data: &Bound<'_, PyAny>,
    ) -> PyResult<bool> {
        let items: Vec<Bound<'_, PyAny>> = if let Ok(list) = data.downcast::<PyList>() {
            list.iter().collect()
        } else if let Ok(tuple) = data.downcast::<PyTuple>() {
            tuple.iter().collect()
        } else {
            return Ok(false);
        };

        let mut edge_batch: Vec<(String, String, usize, AttrMap)> = Vec::with_capacity(items.len());
        let mut node_seen: HashSet<String> = HashSet::new();
        let mut node_entries: Vec<(String, PyObject)> = Vec::new();
        let mut occupied_keys: HashMap<(String, String), HashSet<usize>> = HashMap::new();
        let mut public_to_internal: HashMap<(String, String, String), usize> = HashMap::new();
        let mut edge_attrs: HashMap<(String, String, usize), Py<PyDict>> = HashMap::new();
        let mut edge_keys: HashMap<(String, String, usize), PyObject> = HashMap::new();

        for item in items {
            let Ok(tuple) = item.downcast::<PyTuple>() else {
                return Ok(false);
            };
            let tuple_len = tuple.len();
            // br-r37-c1-ctor2tuple: accept bare `(u, v)` edges too. nx's
            // from_edgelist (and the Rust constructor's per-edge fallback) treat a
            // 2-tuple as `add_edge(u, v)` with an AUTO integer key. Previously only
            // 3/4-tuples hit this batch path, so a plain `MultiDiGraph([(u, v), ...])`
            // fell through to the per-edge add_edge loop (~2x nx); 3/4-tuples keep
            // their explicit string-key dedup semantics unchanged.
            if !(2..=4).contains(&tuple_len) {
                return Ok(false);
            }
            let u = tuple.get_item(0)?;
            let v = tuple.get_item(1)?;
            if !u.is_exact_instance_of::<PyInt>() || !v.is_exact_instance_of::<PyInt>() {
                return Ok(false);
            }
            let key = if tuple_len >= 3 {
                let key = tuple.get_item(2)?;
                if !key.is_exact_instance_of::<PyString>() {
                    return Ok(false);
                }
                Some(key)
            } else {
                None
            };
            let Ok(u_value) = u.extract::<i64>() else {
                return Ok(false);
            };
            let Ok(v_value) = v.extract::<i64>() else {
                return Ok(false);
            };
            let u_canonical = u_value.to_string();
            let v_canonical = v_value.to_string();
            if node_seen.insert(u_canonical.clone()) {
                node_entries.push((u_canonical.clone(), u.clone().unbind()));
            }
            if node_seen.insert(v_canonical.clone()) {
                node_entries.push((v_canonical.clone(), v.clone().unbind()));
            }

            let pair = (u_canonical.clone(), v_canonical.clone());
            let internal_key = match &key {
                // Auto-key: each bare (u, v) is a distinct parallel edge; assign the
                // next free integer key for the pair (matches `add_edge` / nx).
                None => {
                    let occupied = occupied_keys.entry(pair).or_default();
                    let mut candidate = occupied.len();
                    while occupied.contains(&candidate) {
                        candidate += 1;
                    }
                    occupied.insert(candidate);
                    candidate
                }
                Some(key) => {
                    let public_lookup = edge_key_lookup_string(py, key)?;
                    let lookup_key = (pair.0.clone(), pair.1.clone(), public_lookup);
                    if let Some(existing) = public_to_internal.get(&lookup_key) {
                        *existing
                    } else {
                        let occupied = occupied_keys.entry(pair).or_default();
                        let mut candidate = occupied.len();
                        while occupied.contains(&candidate) {
                            candidate += 1;
                        }
                        occupied.insert(candidate);
                        public_to_internal.insert(lookup_key, candidate);
                        candidate
                    }
                }
            };

            let edge_key = Self::edge_key(&u_canonical, &v_canonical, internal_key);
            let rust_attrs = if tuple_len == 4 {
                let fourth = tuple.get_item(3)?;
                let Ok(dict) = fourth.downcast::<PyDict>() else {
                    return Ok(false);
                };
                let py_attrs = edge_attrs
                    .entry(edge_key.clone())
                    .or_insert_with(|| PyDict::new(py).unbind());
                py_attrs.bind(py).update(dict.as_mapping())?;
                py_dict_to_attr_map(dict)?
            } else if tuple_len == 3 {
                // Unchanged: 3-tuples eagerly allocate the empty py attr dict.
                edge_attrs
                    .entry(edge_key.clone())
                    .or_insert_with(|| PyDict::new(py).unbind());
                AttrMap::new()
            } else {
                // br-r37-c1-ctor2tuple: bare 2-tuple, no attrs — leave the py attr
                // dict LAZY (the mirror materializes an empty dict on demand),
                // matching add_edge and skipping a per-edge PyDict alloc.
                AttrMap::new()
            };
            // Only 3/4-tuples carry an explicit (string) key object; bare 2-tuple
            // auto-keys stay LAZY — py_edge_key falls back to the integer key,
            // exactly as nx surfaces an auto integer key.
            if let Some(key) = key {
                edge_keys
                    .entry(edge_key)
                    .or_insert_with(|| key.clone().unbind());
            }
            edge_batch.push((u_canonical, v_canonical, internal_key, rust_attrs));
        }

        let mirror_active = self.node_iter_mirror_active();
        for (canonical, node) in node_entries {
            self.node_key_map.entry(canonical.clone()).or_insert(node);
            self.node_py_attrs
                .entry(canonical.clone())
                .or_insert_with(|| PyDict::new(py).unbind());
            if mirror_active {
                self.node_iter_mirror_insert(py, &canonical)?;
            }
        }
        let inserted_edges = self
            .inner
            .extend_keyed_edges_with_attrs_unrecorded(edge_batch);
        self.edge_py_attrs.extend(edge_attrs);
        self.edge_py_keys.extend(edge_keys);
        if !node_seen.is_empty() {
            self.bump_nodes_seq();
        }
        if inserted_edges > 0 {
            self.bump_edges_seq();
        }
        Ok(true)
    }

    /// br-r37-c1-nodebatch: collect a batch of attributed nodes for a FRESH
    /// MultiDiGraph (sibling of `PyDiGraph::collect_attr_node_batch`). Pure
    /// collect; bails to the per-node loop on any shape it can't replicate.
    fn collect_attr_node_batch<'py, I>(
        &self,
        py: Python<'py>,
        items: I,
        len: usize,
    ) -> PyResult<Option<DiAttrNodeBatch>>
    where
        I: IntoIterator<Item = Bound<'py, PyAny>>,
    {
        let mut nodes: Vec<(String, AttrMap, Option<Py<PyDict>>)> = Vec::with_capacity(len);
        let mut new_nodes: Vec<(String, PyObject)> = Vec::new();
        let mut seen_nodes: HashSet<String> = HashSet::new();
        let mut node_bumps = 0_u64;
        let mut batch_first: HashMap<String, PyObject> = HashMap::new();

        for item in items {
            let (node, src_dict): (Bound<'py, PyAny>, Option<Bound<'py, PyDict>>) =
                if let Ok(tuple) = item.downcast::<PyTuple>() {
                    if tuple.len() == 2 {
                        let second = tuple.get_item(1)?;
                        if let Ok(d) = second.downcast::<PyDict>() {
                            (tuple.get_item(0)?, Some(d.clone()))
                        } else {
                            (item.clone(), None)
                        }
                    } else {
                        (item.clone(), None)
                    }
                } else {
                    (item.clone(), None)
                };

            if !PyDiGraph::is_plain_batch_node(&node) {
                return Ok(None);
            }

            let (rust_attrs, src) = match &src_dict {
                Some(d) => {
                    let Ok(attrs) = py_dict_to_attr_map(d) else {
                        return Ok(None);
                    };
                    if attrs.keys().any(|k| k.starts_with("__fnx_incompatible")) {
                        return Ok(None);
                    }
                    (attrs, Some(d.clone().unbind()))
                }
                None => (AttrMap::new(), None),
            };

            let Ok(canonical) = node_key_to_string(py, &node) else {
                return Ok(None);
            };
            if self.batch_display_conflict(py, &canonical, &node, &mut batch_first) {
                return Ok(None);
            }
            if seen_nodes.insert(canonical.clone()) {
                node_bumps = node_bumps.wrapping_add(1);
                new_nodes.push((canonical.clone(), node.clone().unbind()));
            }
            nodes.push((canonical, rust_attrs, src));
        }

        Ok(Some((nodes, new_nodes, node_bumps)))
    }

    /// Commit a collected attributed-node batch (MultiDiGraph EAGER mirror —
    /// matching `add_node`): every node gets a `node_py_attrs` dict, attributed
    /// nodes merge theirs, ONE `extend_nodes_with_attrs_unrecorded`, `nodes_seq`
    /// bump.
    fn add_attr_node_batch(
        &mut self,
        py: Python<'_>,
        nodes: Vec<(String, AttrMap, Option<Py<PyDict>>)>,
        new_nodes: Vec<(String, PyObject)>,
        node_bumps: u64,
    ) -> PyResult<()> {
        let mirror_active = self.node_iter_mirror_active();
        for (canonical, node) in new_nodes {
            let mirror_key = if mirror_active {
                Some(canonical.clone())
            } else {
                None
            };
            self.node_key_map.entry(canonical.clone()).or_insert(node);
            self.node_py_attrs
                .entry(canonical)
                .or_insert_with(|| PyDict::new(py).unbind());
            if let Some(c) = mirror_key {
                self.node_iter_mirror_insert(py, &c)?;
            }
        }
        for (canonical, _, src) in &nodes {
            if let Some(src) = src {
                let bound = src.bind(py);
                if !bound.is_empty()
                    && let Some(dict) = self.node_py_attrs.get(canonical)
                {
                    dict.bind(py).update(bound.as_mapping())?;
                }
            }
        }
        let _inserted = self
            .inner
            .extend_nodes_with_attrs_unrecorded(nodes.into_iter().map(|(c, a, _)| (c, a)));
        self.nodes_seq = self.nodes_seq.wrapping_add(node_bumps);
        Ok(())
    }

    fn collect_fresh_exact_int_attr_edge_batch<'py, I>(
        &self,
        py: Python<'py>,
        items: I,
        len: usize,
    ) -> PyResult<Option<MultiDiIndexedAttrEdgeBatch>>
    where
        I: IntoIterator<Item = Bound<'py, PyAny>>,
    {
        let mut node_indices: HashMap<i64, usize> = HashMap::new();
        let mut node_labels: Vec<String> = Vec::new();
        let mut node_objects: Vec<PyObject> = Vec::new();
        let mut pair_count: HashMap<(usize, usize), usize> = HashMap::new();
        let mut edges: Vec<(usize, usize, usize, AttrMap, Py<PyDict>)> = Vec::with_capacity(len);
        let mut node_bumps = 0_u64;

        for item in items {
            let Ok(tuple) = item.downcast::<PyTuple>() else {
                return Ok(None);
            };
            if tuple.len() != 3 {
                return Ok(None);
            }

            let u = tuple.get_item(0)?;
            let v = tuple.get_item(1)?;
            if !u.is_exact_instance_of::<PyInt>()
                || !v.is_exact_instance_of::<PyInt>()
                || u.is_exact_instance_of::<PyBool>()
                || v.is_exact_instance_of::<PyBool>()
            {
                return Ok(None);
            }
            let Ok(u_value) = u.extract::<i64>() else {
                return Ok(None);
            };
            let Ok(v_value) = v.extract::<i64>() else {
                return Ok(None);
            };

            let third = tuple.get_item(2)?;
            let Ok(dict) = third.downcast::<PyDict>() else {
                return Ok(None);
            };
            let fast_weight = match single_weight_float_attr_map_with_mirror(py, dict) {
                Ok(converted) => converted,
                Err(_) => return Ok(None),
            };
            let (attrs, mirror) = match fast_weight {
                Some(converted) => converted,
                None => match py_dict_to_attr_map_with_mirror(py, dict) {
                    Ok(converted) => converted,
                    Err(_) => return Ok(None),
                },
            };
            if attrs
                .keys()
                .any(|key| key.starts_with("__fnx_incompatible"))
            {
                return Ok(None);
            }

            let mut edge_added_node = false;
            let u_index = match node_indices.get(&u_value).copied() {
                Some(index) => index,
                None => {
                    let index = node_labels.len();
                    node_indices.insert(u_value, index);
                    node_labels.push(u_value.to_string());
                    node_objects.push(u.clone().unbind());
                    edge_added_node = true;
                    index
                }
            };
            let v_index = match node_indices.get(&v_value).copied() {
                Some(index) => index,
                None => {
                    let index = node_labels.len();
                    node_indices.insert(v_value, index);
                    node_labels.push(v_value.to_string());
                    node_objects.push(v.clone().unbind());
                    edge_added_node = true;
                    index
                }
            };
            if edge_added_node {
                node_bumps = node_bumps.wrapping_add(1);
            }

            let counter = pair_count.entry((u_index, v_index)).or_insert(0);
            let key = *counter;
            *counter += 1;
            edges.push((u_index, v_index, key, attrs, mirror));
        }

        Ok(Some((node_labels, node_objects, edges, node_bumps)))
    }

    fn add_fresh_exact_int_attr_edge_batch(
        &mut self,
        py: Python<'_>,
        node_labels: Vec<String>,
        node_objects: Vec<PyObject>,
        edges: Vec<(usize, usize, usize, AttrMap, Py<PyDict>)>,
        node_bumps: u64,
    ) -> PyResult<()> {
        let edge_bumps = u64::try_from(edges.len()).unwrap_or(u64::MAX);
        let mirror_active = self.node_iter_mirror_active();
        for (canonical, node) in node_labels.iter().zip(node_objects) {
            self.node_key_map.entry(canonical.clone()).or_insert(node);
            if mirror_active {
                self.node_iter_mirror_insert(py, canonical)?;
            }
        }

        let mut inner_edges = Vec::with_capacity(edges.len());
        for (source_idx, target_idx, key, attrs, mirror) in edges {
            let source = &node_labels[source_idx];
            let target = &node_labels[target_idx];
            if !mirror.bind(py).is_empty() {
                self.edge_py_attrs
                    .entry(Self::edge_key(source, target, key))
                    .or_insert(mirror);
            }
            inner_edges.push((source_idx, target_idx, key, attrs));
        }

        let _inserted = self
            .inner
            .extend_fresh_index_keyed_edges_with_attrs_unrecorded(node_labels, inner_edges);
        self.nodes_seq = self.nodes_seq.wrapping_add(node_bumps);
        self.edges_seq = self.edges_seq.wrapping_add(edge_bumps);
        Ok(())
    }

    fn try_add_fresh_exact_int_attr_edge_batch(
        &mut self,
        py: Python<'_>,
        ebunch_to_add: &Bound<'_, PyAny>,
    ) -> PyResult<bool> {
        const ATTR_EDGE_BATCH_MIN: usize = 8;
        if self.inner.node_count() != 0
            || self.inner.edge_count() != 0
            || !self.node_key_map.is_empty()
            || !self.node_py_attrs.is_empty()
            || !self.edge_py_attrs.is_empty()
            || !self.edge_py_keys.is_empty()
            || !self.succ_py_keys.is_empty()
            || !self.pred_py_keys.is_empty()
        {
            return Ok(false);
        }

        let collected = if let Ok(list) = ebunch_to_add.downcast::<PyList>() {
            if list.len() < ATTR_EDGE_BATCH_MIN {
                return Ok(false);
            }
            self.collect_fresh_exact_int_attr_edge_batch(py, list.iter(), list.len())?
        } else if let Ok(tuple) = ebunch_to_add.downcast::<PyTuple>() {
            if tuple.len() < ATTR_EDGE_BATCH_MIN {
                return Ok(false);
            }
            self.collect_fresh_exact_int_attr_edge_batch(py, tuple.iter(), tuple.len())?
        } else {
            return Ok(false);
        };

        let Some((node_labels, node_objects, edges, node_bumps)) = collected else {
            return Ok(false);
        };
        self.add_fresh_exact_int_attr_edge_batch(py, node_labels, node_objects, edges, node_bumps)?;
        Ok(true)
    }
}

#[derive(Clone, Copy)]
enum MultiDiAdjKind {
    Successors,
    Predecessors,
}

#[pyclass(module = "franken_networkx", mapping)]
struct MultiDiAtlasView {
    graph: Py<PyMultiDiGraph>,
    node: String,
    kind: MultiDiAdjKind,
}

impl MultiDiAtlasView {
    fn new(graph: Py<PyMultiDiGraph>, node: String, kind: MultiDiAdjKind) -> Self {
        Self { graph, node, kind }
    }

    fn endpoint_pair(&self, other: String) -> (String, String) {
        match self.kind {
            MultiDiAdjKind::Successors => (self.node.clone(), other),
            MultiDiAdjKind::Predecessors => (other, self.node.clone()),
        }
    }

    fn materialize(&self, py: Python<'_>) -> PyResult<Py<PyDict>> {
        let g = self.graph.borrow(py);
        let neighbors = match self.kind {
            MultiDiAdjKind::Successors => g.inner.successors(&self.node).unwrap_or_default(),
            MultiDiAdjKind::Predecessors => g.inner.predecessors(&self.node).unwrap_or_default(),
        };
        let result = PyDict::new(py);
        for neighbor in neighbors {
            let py_neighbor = match self.kind {
                // br-r37-c1-z6uka
                MultiDiAdjKind::Successors => g.py_succ_key(py, &self.node, neighbor),
                MultiDiAdjKind::Predecessors => g.py_pred_key(py, &self.node, neighbor),
            };
            let (source, target) = self.endpoint_pair(neighbor.to_owned());
            let keydict = MultiDiKeyDictView::new(self.graph.clone_ref(py), source, target)
                .materialize(py)?;
            result.set_item(py_neighbor, keydict.bind(py))?;
        }
        Ok(result.unbind())
    }
}

#[pymethods]
impl MultiDiAtlasView {
    fn __getitem__(
        &self,
        py: Python<'_>,
        v: &Bound<'_, PyAny>,
    ) -> PyResult<Py<MultiDiKeyDictView>> {
        let g = self.graph.borrow(py);
        let v_canon = node_key_to_string(py, v)?;
        let (source, target) = self.endpoint_pair(v_canon);
        if !g.inner.has_edge(&source, &target) {
            return Err(PyKeyError::new_err((v.clone().unbind(),)));
        }
        Py::new(
            py,
            MultiDiKeyDictView::new(self.graph.clone_ref(py), source, target),
        )
    }

    fn __contains__(&self, py: Python<'_>, v: &Bound<'_, PyAny>) -> PyResult<bool> {
        let g = self.graph.borrow(py);
        let v_canon = node_key_to_string(py, v)?;
        let (source, target) = self.endpoint_pair(v_canon);
        Ok(g.inner.has_edge(&source, &target))
    }

    fn __len__(&self, py: Python<'_>) -> usize {
        let g = self.graph.borrow(py);
        match self.kind {
            MultiDiAdjKind::Successors => g
                .inner
                .successors(&self.node)
                .map_or(0, |successors| successors.len()),
            MultiDiAdjKind::Predecessors => g
                .inner
                .predecessors(&self.node)
                .map_or(0, |predecessors| predecessors.len()),
        }
    }

    fn __iter__(&self, py: Python<'_>) -> PyResult<Py<crate::NodeIterator>> {
        let g = self.graph.borrow(py);
        let neighbors = match self.kind {
            MultiDiAdjKind::Successors => g.inner.successors(&self.node).unwrap_or_default(),
            MultiDiAdjKind::Predecessors => g.inner.predecessors(&self.node).unwrap_or_default(),
        };
        let nodes: Vec<PyObject> = neighbors // br-r37-c1-z6uka
            .iter()
            .map(|node| match self.kind {
                MultiDiAdjKind::Successors => g.py_succ_key(py, &self.node, node),
                MultiDiAdjKind::Predecessors => g.py_pred_key(py, &self.node, node),
            })
            .collect();
        Py::new(py, crate::NodeIterator::unguarded(nodes))
    }

    fn keys(&self, py: Python<'_>) -> PyResult<Py<crate::NodeIterator>> {
        self.__iter__(py)
    }

    fn items(&self, py: Python<'_>) -> PyResult<Vec<(PyObject, Py<MultiDiKeyDictView>)>> {
        let g = self.graph.borrow(py);
        let neighbors = match self.kind {
            MultiDiAdjKind::Successors => g.inner.successors(&self.node).unwrap_or_default(),
            MultiDiAdjKind::Predecessors => g.inner.predecessors(&self.node).unwrap_or_default(),
        };
        let mut out = Vec::with_capacity(neighbors.len());
        for neighbor in neighbors {
            let py_neighbor = match self.kind {
                // br-r37-c1-z6uka
                MultiDiAdjKind::Successors => g.py_succ_key(py, &self.node, neighbor),
                MultiDiAdjKind::Predecessors => g.py_pred_key(py, &self.node, neighbor),
            };
            let (source, target) = self.endpoint_pair(neighbor.to_owned());
            out.push((
                py_neighbor,
                Py::new(
                    py,
                    MultiDiKeyDictView::new(self.graph.clone_ref(py), source, target),
                )?,
            ));
        }
        Ok(out)
    }

    fn values(&self, py: Python<'_>) -> PyResult<Vec<Py<MultiDiKeyDictView>>> {
        Ok(self
            .items(py)?
            .into_iter()
            .map(|(_, value)| value)
            .collect())
    }

    #[pyo3(signature = (v, default=None))]
    fn get(
        &self,
        py: Python<'_>,
        v: &Bound<'_, PyAny>,
        default: Option<PyObject>,
    ) -> PyResult<PyObject> {
        match self.__getitem__(py, v) {
            Ok(value) => Ok(value.into_any()),
            Err(e) if e.is_instance_of::<PyKeyError>(py) => {
                Ok(default.unwrap_or_else(|| py.None()))
            }
            Err(e) => Err(e),
        }
    }

    fn copy(&self, py: Python<'_>) -> PyResult<Py<PyDict>> {
        let g = self.graph.borrow(py);
        let neighbors = match self.kind {
            MultiDiAdjKind::Successors => g.inner.successors(&self.node).unwrap_or_default(),
            MultiDiAdjKind::Predecessors => g.inner.predecessors(&self.node).unwrap_or_default(),
        };
        let result = PyDict::new(py);
        for neighbor in neighbors {
            let py_neighbor = match self.kind {
                // br-r37-c1-z6uka
                MultiDiAdjKind::Successors => g.py_succ_key(py, &self.node, neighbor),
                MultiDiAdjKind::Predecessors => g.py_pred_key(py, &self.node, neighbor),
            };
            let (source, target) = self.endpoint_pair(neighbor.to_owned());
            let keydict =
                MultiDiKeyDictView::new(self.graph.clone_ref(py), source, target).copy(py)?;
            result.set_item(py_neighbor, keydict)?;
        }
        Ok(result.unbind())
    }

    fn __eq__(&self, py: Python<'_>, other: &Bound<'_, PyAny>) -> PyResult<bool> {
        let materialized = self.materialize(py)?;
        materialized.bind(py).eq(other)
    }

    fn __ne__(&self, py: Python<'_>, other: &Bound<'_, PyAny>) -> PyResult<bool> {
        Ok(!self.__eq__(py, other)?)
    }

    fn __str__(&self, py: Python<'_>) -> PyResult<String> {
        let materialized = self.materialize(py)?;
        Ok(materialized.bind(py).str()?.to_string())
    }

    fn __repr__(&self, py: Python<'_>) -> PyResult<String> {
        let materialized = self.materialize(py)?;
        Ok(format!(
            "AdjacencyView({})",
            materialized.bind(py).repr()?.to_str()?
        ))
    }

    fn __bool__(&self, py: Python<'_>) -> bool {
        self.__len__(py) > 0
    }
}

#[pyclass(module = "franken_networkx", mapping)]
struct MultiDiKeyDictView {
    graph: Py<PyMultiDiGraph>,
    source: String,
    target: String,
}

impl MultiDiKeyDictView {
    fn new(graph: Py<PyMultiDiGraph>, source: String, target: String) -> Self {
        Self {
            graph,
            source,
            target,
        }
    }

    fn materialize(&self, py: Python<'_>) -> PyResult<Py<PyDict>> {
        let g = self.graph.borrow(py);
        let result = PyDict::new(py);
        for key in g
            .inner
            .edge_keys(&self.source, &self.target)
            .unwrap_or_default()
        {
            let edge_key = PyMultiDiGraph::edge_key(&self.source, &self.target, key);
            let attrs = g
                .edge_py_attrs
                .get(&edge_key)
                .map_or_else(|| PyDict::new(py).unbind(), |d| d.clone_ref(py));
            result.set_item(g.py_edge_key(py, &self.source, &self.target, key), attrs)?;
        }
        Ok(result.unbind())
    }
}

#[pymethods]
impl MultiDiKeyDictView {
    fn __getitem__(&self, py: Python<'_>, key: &Bound<'_, PyAny>) -> PyResult<Py<PyDict>> {
        let internal_key = {
            let g = self.graph.borrow(py);
            let Some(internal_key) =
                g.resolve_internal_edge_key(py, &self.source, &self.target, key)?
            else {
                return Err(PyKeyError::new_err((key.clone().unbind(),)));
            };
            internal_key
        };
        let mut g = self.graph.borrow_mut(py);
        g.mark_edge_dirty(&self.source, &self.target, internal_key);
        Ok(
            g.ensure_edge_py_attrs(py, &self.source, &self.target, internal_key)
                .clone_ref(py),
        )
    }

    fn __contains__(&self, py: Python<'_>, key: &Bound<'_, PyAny>) -> PyResult<bool> {
        let g = self.graph.borrow(py);
        Ok(
            g.resolve_internal_edge_key(py, &self.source, &self.target, key)?
                .is_some(),
        )
    }

    fn __len__(&self, py: Python<'_>) -> usize {
        self.graph
            .borrow(py)
            .inner
            .edge_keys(&self.source, &self.target)
            .map_or(0, |keys| keys.len())
    }

    fn __iter__(&self, py: Python<'_>) -> PyResult<Py<crate::NodeIterator>> {
        let g = self.graph.borrow(py);
        let keys: Vec<PyObject> = g
            .inner
            .edge_keys(&self.source, &self.target)
            .unwrap_or_default()
            .into_iter()
            .map(|key| g.py_edge_key(py, &self.source, &self.target, key))
            .collect();
        Py::new(py, crate::NodeIterator::unguarded(keys))
    }

    fn keys(&self, py: Python<'_>) -> PyResult<Py<crate::NodeIterator>> {
        self.__iter__(py)
    }

    fn items(&self, py: Python<'_>) -> PyResult<Vec<(PyObject, Py<PyDict>)>> {
        let g = self.graph.borrow(py);
        let keys = g
            .inner
            .edge_keys(&self.source, &self.target)
            .unwrap_or_default();
        if !keys.is_empty() {
            g.mark_edges_dirty();
        }
        let mut out = Vec::with_capacity(keys.len());
        for key in keys {
            let edge_key = PyMultiDiGraph::edge_key(&self.source, &self.target, key);
            let attrs = g
                .edge_py_attrs
                .get(&edge_key)
                .map_or_else(|| PyDict::new(py).unbind(), |d| d.clone_ref(py));
            out.push((g.py_edge_key(py, &self.source, &self.target, key), attrs));
        }
        Ok(out)
    }

    fn values(&self, py: Python<'_>) -> PyResult<Vec<Py<PyDict>>> {
        Ok(self
            .items(py)?
            .into_iter()
            .map(|(_, attrs)| attrs)
            .collect())
    }

    #[pyo3(signature = (key, default=None))]
    fn get(
        &self,
        py: Python<'_>,
        key: &Bound<'_, PyAny>,
        default: Option<PyObject>,
    ) -> PyResult<PyObject> {
        match self.__getitem__(py, key) {
            Ok(value) => Ok(value.into_any()),
            Err(e) if e.is_instance_of::<PyKeyError>(py) => {
                Ok(default.unwrap_or_else(|| py.None()))
            }
            Err(e) => Err(e),
        }
    }

    fn copy(&self, py: Python<'_>) -> PyResult<Py<PyDict>> {
        let g = self.graph.borrow(py);
        let result = PyDict::new(py);
        for key in g
            .inner
            .edge_keys(&self.source, &self.target)
            .unwrap_or_default()
        {
            let edge_key = PyMultiDiGraph::edge_key(&self.source, &self.target, key);
            let attrs = match g.edge_py_attrs.get(&edge_key) {
                Some(attrs) => attrs.bind(py).copy()?.unbind(),
                None => PyDict::new(py).unbind(),
            };
            result.set_item(g.py_edge_key(py, &self.source, &self.target, key), attrs)?;
        }
        Ok(result.unbind())
    }

    fn __eq__(&self, py: Python<'_>, other: &Bound<'_, PyAny>) -> PyResult<bool> {
        let materialized = self.materialize(py)?;
        materialized.bind(py).eq(other)
    }

    fn __ne__(&self, py: Python<'_>, other: &Bound<'_, PyAny>) -> PyResult<bool> {
        Ok(!self.__eq__(py, other)?)
    }

    fn __str__(&self, py: Python<'_>) -> PyResult<String> {
        let materialized = self.materialize(py)?;
        Ok(materialized.bind(py).str()?.to_string())
    }

    fn __repr__(&self, py: Python<'_>) -> PyResult<String> {
        let materialized = self.materialize(py)?;
        Ok(format!(
            "AtlasView({})",
            materialized.bind(py).repr()?.to_str()?
        ))
    }

    fn __bool__(&self, py: Python<'_>) -> bool {
        self.__len__(py) > 0
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

        let mut g = Self::new_empty_with_mode(py, CompatibilityMode::Strict)?;
        g.graph_attrs = graph_attrs.unbind();

        if let Some(data) = incoming_graph_data {
            // br-r37-c1-ymeml: see crate::fnx_graph_instance_mode — __init__
            // owns population for graph-instance inputs; absorb skipped.
            if let Some(mode) = crate::fnx_graph_instance_mode(data) {
                g.inner = MultiDiGraph::new(mode);
                return Ok(g);
            }
            if let Ok(other) = data.extract::<PyRef<'_, PyMultiDiGraph>>() {
                g.inner = MultiDiGraph::with_runtime_policy(other.inner.runtime_policy().clone());
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
                    if let Some(py_key) = other.edge_py_keys.get(&(u.clone(), v.clone(), *key)) {
                        g.remember_edge_key_object(py, u, v, *key, py_key);
                    } else {
                        g.remember_edge_key(py, u, v, *key, None);
                    }
                }
                g.graph_attrs = other.graph_attrs.bind(py).copy()?.unbind();
            } else if let Ok(other) = data.extract::<PyRef<'_, PyDiGraph>>() {
                g.inner = MultiDiGraph::with_runtime_policy(other.inner.runtime_policy().clone());
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
                    let key = g
                        .inner
                        .add_edge_with_key_and_attrs(u.clone(), v.clone(), 0, rust_attrs)
                        .map_err(|e| NetworkXError::new_err(e.to_string()))?;
                    g.edge_py_attrs
                        .insert((u.clone(), v.clone(), key), attrs.bind(py).copy()?.unbind());
                    g.remember_edge_key(py, u, v, key, None);
                }
                g.graph_attrs = other.graph_attrs.bind(py).copy()?.unbind();
            } else if g.try_absorb_exact_int_str_keyed_ctor_edges(py, data)? {
                // Constructor-only batch path for exact int endpoints + exact str keys.
            } else if let Ok(iter) = PyIterator::from_object(data) {
                // br-r37-c1-baqyi: nx's to_networkx_graph wraps every
                // from_edgelist failure in NetworkXError("Input is not a
                // valid edge list") — unhashable keys raise TypeError from
                // add_edge, which must not leak raw out of the constructor
                // (same closure as the PyMultiGraph ctor).
                let edge_list_err = |e: PyErr| {
                    if e.is_instance_of::<PyTypeError>(py) {
                        NetworkXError::new_err("Input is not a valid edge list")
                    } else {
                        e
                    }
                };
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
                                )
                                .map_err(edge_list_err)?;
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
                                    )
                                    .map_err(edge_list_err)?;
                                } else {
                                    // br-r37-c1-baqyi: nx tries
                                    // ddd.update(dd) FIRST; only a
                                    // TypeError/ValueError makes the third
                                    // element the key. Dict-able iterables
                                    // of pairs are DATA.
                                    let throwaway = PyDict::new(py);
                                    match throwaway.call_method1("update", (&third,)) {
                                        Ok(_) => {
                                            merged.update(throwaway.as_mapping())?;
                                            g.add_edge(
                                                py,
                                                &tuple.get_item(0)?,
                                                &tuple.get_item(1)?,
                                                None,
                                                Some(&merged),
                                            )
                                            .map_err(edge_list_err)?;
                                        }
                                        Err(err)
                                            if err.is_instance_of::<PyTypeError>(py)
                                                || err.is_instance_of::<PyValueError>(py) =>
                                        {
                                            g.add_edge(
                                                py,
                                                &tuple.get_item(0)?,
                                                &tuple.get_item(1)?,
                                                Some(&third),
                                                Some(&merged),
                                            )
                                            .map_err(edge_list_err)?;
                                        }
                                        Err(err) => return Err(err),
                                    }
                                }
                            }
                            4 => {
                                let edge_key = tuple.get_item(2)?;
                                let fourth = tuple.get_item(3)?;
                                if let Ok(d) = fourth.downcast::<PyDict>() {
                                    merged.update(d.as_mapping())?;
                                } else {
                                    // br-r37-c1-baqyi: nx's ddd.update(dd)
                                    // runs BEFORE add_edge — a non-dict
                                    // 4th raises with NOTHING created (the
                                    // ctor wraps it as an invalid edge
                                    // list, like nx to_networkx_graph).
                                    let throwaway = PyDict::new(py);
                                    throwaway
                                        .call_method1("update", (&fourth,))
                                        .map_err(edge_list_err)?;
                                    merged.update(throwaway.as_mapping())?;
                                }
                                g.add_edge(
                                    py,
                                    &tuple.get_item(0)?,
                                    &tuple.get_item(1)?,
                                    Some(&edge_key),
                                    Some(&merged),
                                )
                                .map_err(edge_list_err)?;
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

    /// All node display objects in ONE PyO3 call (br-r37-c1-cijlm). Mirrors the
    /// simple-graph binding (lib.rs): Python ``set(graph)`` crosses the PyO3
    /// boundary per node (~2x nx on node-set construction), and ``set(graph.adj)``
    /// re-materialises every AdjacencyView row; building the Vec in Rust lets
    /// callers like ``non_neighbors`` enumerate every node in one crossing.
    /// Order = node insertion order (``nodes_ordered``).
    fn _native_node_keys(&self, py: Python<'_>) -> PyObject {
        let seq = self.nodes_seq;
        {
            let guard = self.node_keys_cache.lock().unwrap();
            if let Some((cached_seq, tup, _set)) = guard.as_ref()
                && *cached_seq == seq
            {
                return tup.clone_ref(py).into_any();
            }
        }
        let keys: Vec<PyObject> = self
            .inner
            .nodes_ordered()
            .into_iter()
            .map(|n| self.py_node_key(py, n))
            .collect();
        let tup = pyo3::types::PyTuple::new(py, &keys)
            .expect("node-keys tuple")
            .unbind();
        let set = PySet::new(py, keys.iter()).expect("node-keys set").unbind();
        *self.node_keys_cache.lock().unwrap() = Some((seq, tup.clone_ref(py), set));
        tup.into_any()
    }

    fn _native_node_key_set(&self, py: Python<'_>) -> PyResult<PyObject> {
        let seq = self.nodes_seq;
        {
            let guard = self.node_keys_cache.lock().unwrap();
            if let Some((cached_seq, _tup, set)) = guard.as_ref()
                && *cached_seq == seq
            {
                return Ok(set.bind(py).call_method0("copy")?.unbind());
            }
        }
        let keys: Vec<PyObject> = self
            .inner
            .nodes_ordered()
            .into_iter()
            .map(|n| self.py_node_key(py, n))
            .collect();
        let tup = pyo3::types::PyTuple::new(py, &keys)
            .expect("node-keys tuple")
            .unbind();
        let set = PySet::new(py, keys.iter()).expect("node-keys set").unbind();
        let result = set.bind(py).call_method0("copy")?.unbind();
        *self.node_keys_cache.lock().unwrap() = Some((seq, tup, set));
        Ok(result)
    }

    /// Monotonic node-mutation counter (br-r37-c1-39d82 / jft0i).
    /// Exposed to Python so view-materialization caches can key on
    /// ``(nodes_seq, edges_seq)`` without scanning for changes.
    #[getter]
    fn nodes_seq(&self) -> u64 {
        self.nodes_seq
    }

    /// Monotonic edge-mutation counter (br-r37-c1-jft0i).
    #[getter]
    fn edges_seq(&self) -> u64 {
        self.edges_seq
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

    // br-r37-c1-addnoden: the node param must be named like nx's public
    // ``add_node(node_for_adding, **attr)`` — a bare ``n`` collides with
    // a node attribute literally keyed "n" (e.g. read_graphml of a graph
    // with an 'n' attr: add_node(node, n=7) -> "multiple values for n").
    // nx has the same collision only for an attr keyed "node_for_adding",
    // so matching the name gives exact drop-in parity.
    #[pyo3(signature = (node_for_adding, **attr))]
    fn add_node(
        &mut self,
        py: Python<'_>,
        node_for_adding: &Bound<'_, PyAny>,
        attr: Option<&Bound<'_, PyDict>>,
    ) -> PyResult<()> {
        let canonical = node_key_to_string(py, node_for_adding)?;
        // br-r37-c1-firstwins: nx uses dicts for node storage, so the
        // FIRST Python object added under a given canonical key wins
        // (subsequent ``add_node`` calls with hash-equivalent keys are
        // no-ops at the storage level — the original Py object is
        // preserved for ``list(G.nodes())`` and friends). Use
        // ``entry().or_insert_with`` here so re-adding ``0.0`` after
        // ``0`` doesn't overwrite the displayed Py form.
        self.node_key_map
            .entry(canonical.clone())
            .or_insert_with(|| node_for_adding.clone().unbind());
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
        self.node_iter_mirror_insert(py, &canonical)?;
        self.inner.add_node_with_attrs(canonical, rust_attrs);
        self.bump_nodes_seq();
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
        self.bump_nodes_seq();
        Ok(())
    }

    // br-r37-c1-addnoden follow-up: nx multigraph names are
    // u_for_edge/v_for_edge; bare u/v collide with edge attrs keyed
    // 'u'/'v'. Match nx; alias for the body.
    /// br-r37-c1-urle5: native plain-edge batch for `add_edges_from([(u, v), ...])`
    /// on a FRESH MultiDiGraph (no existing edges). See
    /// `PyMultiGraph::_try_add_edges_from_batch` — directed edges are NOT
    /// canonicalized, so the per-pair sequential auto-key tracks `(u, v)` in
    /// order. Returns `false` (no mutation) for anything outside the fast shape.
    fn _try_add_edges_from_batch(
        &mut self,
        py: Python<'_>,
        ebunch_to_add: &Bound<'_, PyAny>,
    ) -> PyResult<bool> {
        const PLAIN_EDGE_BATCH_MIN: usize = 8;
        if self.inner.edge_count() != 0
            || !self.succ_py_keys.is_empty()
            || !self.pred_py_keys.is_empty()
        {
            return Ok(false);
        }
        let items: Vec<Bound<'_, PyAny>> = if let Ok(list) = ebunch_to_add.downcast::<PyList>() {
            if list.len() < PLAIN_EDGE_BATCH_MIN {
                return Ok(false);
            }
            list.iter().collect()
        } else if let Ok(tuple) = ebunch_to_add.downcast::<PyTuple>() {
            if tuple.len() < PLAIN_EDGE_BATCH_MIN {
                return Ok(false);
            }
            tuple.iter().collect()
        } else {
            return Ok(false);
        };

        let mut edges: Vec<(String, String, usize, fnx_classes::AttrMap)> =
            Vec::with_capacity(items.len());
        let mut new_nodes: Vec<(String, PyObject)> = Vec::new();
        let mut seen_nodes: std::collections::HashSet<String> = self
            .inner
            .nodes_ordered()
            .into_iter()
            .map(str::to_owned)
            .collect();
        let mut batch_first: HashMap<String, PyObject> = HashMap::new();
        let mut pair_count: HashMap<(String, String), usize> = HashMap::new();
        let mut node_bumps = 0_u64;

        for item in &items {
            let Ok(tuple) = item.downcast::<PyTuple>() else {
                return Ok(false);
            };
            if tuple.len() != 2 {
                return Ok(false);
            }
            let u = tuple.get_item(0)?;
            let v = tuple.get_item(1)?;
            if !PyDiGraph::is_plain_batch_node(&u) || !PyDiGraph::is_plain_batch_node(&v) {
                return Ok(false);
            }
            let uc = node_key_to_string(py, &u)?;
            let vc = node_key_to_string(py, &v)?;
            if self.batch_display_conflict(py, &uc, &u, &mut batch_first)
                || self.batch_display_conflict(py, &vc, &v, &mut batch_first)
            {
                return Ok(false);
            }
            if !seen_nodes.contains(&uc) || !seen_nodes.contains(&vc) {
                node_bumps = node_bumps.wrapping_add(1);
            }
            if seen_nodes.insert(uc.clone()) {
                new_nodes.push((uc.clone(), u.clone().unbind()));
            }
            if seen_nodes.insert(vc.clone()) {
                new_nodes.push((vc.clone(), v.clone().unbind()));
            }
            let counter = pair_count.entry((uc.clone(), vc.clone())).or_insert(0);
            let key = *counter;
            *counter += 1;
            edges.push((uc, vc, key, fnx_classes::AttrMap::new()));
        }

        let edge_bumps = u64::try_from(edges.len()).unwrap_or(u64::MAX);
        let mirror_active = self.node_iter_mirror_active();
        for (canonical, node) in new_nodes {
            let mirror_key = if mirror_active {
                Some(canonical.clone())
            } else {
                None
            };
            self.node_key_map.entry(canonical).or_insert(node);
            if let Some(c) = mirror_key {
                let _ = self.node_iter_mirror_insert(py, &c);
            }
        }
        self.inner.extend_keyed_edges_with_attrs_unrecorded(edges);
        self.nodes_seq = self.nodes_seq.wrapping_add(node_bumps);
        self.edges_seq = self.edges_seq.wrapping_add(edge_bumps);
        Ok(true)
    }

    /// br-r37-c1-nodebatch: native attributed-node batch for
    /// `add_nodes_from([(n, dict), ...])` on a FRESH MultiDiGraph — sibling of
    /// `PyDiGraph::_try_add_nodes_from_batch`. The per-node loop pays ~5.5x nx
    /// on attributed bulk construction. Returns `false` (NO mutation) for
    /// anything outside this shape so the per-node loop owns every error.
    fn _try_add_nodes_from_batch(
        &mut self,
        py: Python<'_>,
        nodes_to_add: &Bound<'_, PyAny>,
    ) -> PyResult<bool> {
        const NODE_BATCH_MIN: usize = 8;
        if self.inner.node_count() != 0
            || self.inner.edge_count() != 0
            || !self.succ_py_keys.is_empty()
            || !self.pred_py_keys.is_empty()
        {
            return Ok(false);
        }
        if let Ok(list) = nodes_to_add.downcast::<PyList>() {
            if list.len() < NODE_BATCH_MIN {
                return Ok(false);
            }
            if let Some((nodes, new_nodes, node_bumps)) =
                self.collect_attr_node_batch(py, list.iter(), list.len())?
            {
                self.add_attr_node_batch(py, nodes, new_nodes, node_bumps)?;
                return Ok(true);
            }
        } else if let Ok(tuple) = nodes_to_add.downcast::<PyTuple>()
            && tuple.len() >= NODE_BATCH_MIN
            && let Some((nodes, new_nodes, node_bumps)) =
                self.collect_attr_node_batch(py, tuple.iter(), tuple.len())?
        {
            self.add_attr_node_batch(py, nodes, new_nodes, node_bumps)?;
            return Ok(true);
        }
        Ok(false)
    }

    /// br-r37-c1-digbatch: bulk fast path for `add_nodes_from(range / int list)` on a
    /// MultiDiGraph — the multi-directed sibling of `PyGraph::_fast_add_int_nodes`, using
    /// the inner `extend_nodes_with_attrs_unrecorded` with empty AttrMaps. Py int objects
    /// are stored (no lazy_int_node_stop). Atomic validate-then-mutate: exact-int only
    /// (excludes bool), else raise so the wrapper falls back. Was the 0.30x / 0.43x loss.
    fn _fast_add_int_nodes(&mut self, py: Python<'_>, nodes: &Bound<'_, PyAny>) -> PyResult<()> {
        let iter = PyIterator::from_object(nodes)?;
        let mut ints: Vec<i64> = Vec::new();
        for item in iter {
            let item = item?;
            if !item.is_exact_instance_of::<PyInt>() {
                return Err(PyTypeError::new_err(
                    "fast int-node path requires exact int elements",
                ));
            }
            ints.push(item.extract::<i64>()?);
        }
        let mut fresh: Vec<(String, AttrMap)> = Vec::with_capacity(ints.len());
        for node in ints {
            let canonical = node.to_string();
            let was_absent =
                !self.node_key_map.contains_key(&canonical) && !self.inner.has_node(&canonical);
            self.node_key_map
                .entry(canonical.clone())
                .or_insert_with(|| {
                    unwrap_infallible(node.into_pyobject(py))
                        .into_any()
                        .unbind()
                });
            if was_absent {
                self.node_iter_mirror_insert(py, &canonical)?;
                fresh.push((canonical, AttrMap::new()));
            }
            self.bump_nodes_seq();
        }
        let _ = self.inner.extend_nodes_with_attrs_unrecorded(fresh);
        Ok(())
    }

    /// br-r37-c1-trzrx: attributed sibling of `_try_add_edges_from_batch` —
    /// native fast path for `add_edges_from([(u, v, data), ...])` (mixed with
    /// plain `(u, v)`) on a FRESH MultiDiGraph. The
    /// directed twin of `PyMultiGraph::_try_add_attr_edges_from_batch`: edges
    /// are NOT canonicalized, so the per-pair sequential auto-key counter and
    /// the `edge_py_attrs` mirror both track `(u, v)` in order. Each 3-tuple's
    /// third element MUST be a `dict` (multigraph DATA; nx auto-keys it).
    /// Optional global `**attr` merges first; per-edge dicts override. Returns
    /// `false` (NO mutation) for anything outside this shape so the per-edge
    /// loop owns every error + partial-prefix contract.
    #[pyo3(signature = (ebunch_to_add, global_attr=None))]
    fn _try_add_attr_edges_from_batch(
        &mut self,
        py: Python<'_>,
        ebunch_to_add: &Bound<'_, PyAny>,
        global_attr: Option<&Bound<'_, PyDict>>,
    ) -> PyResult<bool> {
        const ATTR_EDGE_BATCH_MIN: usize = 8;
        if global_attr.is_none_or(|attrs| attrs.is_empty())
            && self.try_add_fresh_exact_int_attr_edge_batch(py, ebunch_to_add)?
        {
            return Ok(true);
        }
        if self.inner.edge_count() != 0
            || !self.succ_py_keys.is_empty()
            || !self.pred_py_keys.is_empty()
        {
            return Ok(false);
        }
        let items: Vec<Bound<'_, PyAny>> = if let Ok(list) = ebunch_to_add.downcast::<PyList>() {
            if list.len() < ATTR_EDGE_BATCH_MIN {
                return Ok(false);
            }
            list.iter().collect()
        } else if let Ok(tuple) = ebunch_to_add.downcast::<PyTuple>() {
            if tuple.len() < ATTR_EDGE_BATCH_MIN {
                return Ok(false);
            }
            tuple.iter().collect()
        } else {
            return Ok(false);
        };

        let global_map: fnx_classes::AttrMap = match global_attr {
            Some(a) if !a.is_empty() => match py_dict_to_attr_map(a) {
                Ok(attrs)
                    if !attrs
                        .keys()
                        .any(|key| key.starts_with("__fnx_incompatible")) =>
                {
                    attrs
                }
                _ => return Ok(false),
            },
            _ => fnx_classes::AttrMap::new(),
        };
        let mut edges: Vec<(String, String, usize, fnx_classes::AttrMap)> =
            Vec::with_capacity(items.len());
        let mut mirrors: Vec<((String, String, usize), Py<PyDict>)> = Vec::new();
        let mut new_nodes: Vec<(String, PyObject)> = Vec::new();
        let mut seen_nodes: std::collections::HashSet<String> = self
            .inner
            .nodes_ordered()
            .into_iter()
            .map(str::to_owned)
            .collect();
        let mut batch_first: HashMap<String, PyObject> = HashMap::new();
        let mut pair_count: HashMap<(String, String), usize> = HashMap::new();
        let mut node_bumps = 0_u64;

        for item in &items {
            let Ok(tuple) = item.downcast::<PyTuple>() else {
                return Ok(false);
            };
            let tlen = tuple.len();
            if !(2..=3).contains(&tlen) {
                return Ok(false);
            }
            let u = tuple.get_item(0)?;
            let v = tuple.get_item(1)?;
            if !PyDiGraph::is_plain_batch_node(&u) || !PyDiGraph::is_plain_batch_node(&v) {
                return Ok(false);
            }
            let (rust_attrs, src): (fnx_classes::AttrMap, Option<Bound<'_, PyDict>>) = if tlen == 3
            {
                let third = tuple.get_item(2)?;
                let Ok(d) = third.downcast::<PyDict>() else {
                    return Ok(false);
                };
                let Ok(attrs) = py_dict_to_attr_map(d) else {
                    return Ok(false);
                };
                if attrs.keys().any(|k| k.starts_with("__fnx_incompatible")) {
                    return Ok(false);
                }
                if global_map.is_empty() {
                    (attrs, Some(d.clone()))
                } else {
                    let mut merged_map = global_map.clone();
                    merged_map.extend(attrs);
                    let merged = global_attr
                        .expect("non-empty global_map implies global_attr")
                        .copy()?;
                    merged.update(d.as_mapping())?;
                    (merged_map, Some(merged))
                }
            } else if global_map.is_empty() {
                (fnx_classes::AttrMap::new(), None)
            } else {
                let merged = global_attr
                    .expect("non-empty global_map implies global_attr")
                    .copy()?;
                (global_map.clone(), Some(merged))
            };

            let Ok(uc) = node_key_to_string(py, &u) else {
                return Ok(false);
            };
            let Ok(vc) = node_key_to_string(py, &v) else {
                return Ok(false);
            };
            if self.batch_display_conflict(py, &uc, &u, &mut batch_first)
                || self.batch_display_conflict(py, &vc, &v, &mut batch_first)
            {
                return Ok(false);
            }
            if !seen_nodes.contains(&uc) || !seen_nodes.contains(&vc) {
                node_bumps = node_bumps.wrapping_add(1);
            }
            if seen_nodes.insert(uc.clone()) {
                new_nodes.push((uc.clone(), u.clone().unbind()));
            }
            if seen_nodes.insert(vc.clone()) {
                new_nodes.push((vc.clone(), v.clone().unbind()));
            }
            let counter = pair_count.entry((uc.clone(), vc.clone())).or_insert(0);
            let key = *counter;
            *counter += 1;
            if let Some(d) = src
                && !d.is_empty()
            {
                let mirror = PyDict::new(py);
                mirror.update(d.as_mapping())?;
                mirrors.push((Self::edge_key(&uc, &vc, key), mirror.unbind()));
            }
            edges.push((uc, vc, key, rust_attrs));
        }

        let edge_bumps = u64::try_from(edges.len()).unwrap_or(u64::MAX);
        for (canonical, node) in new_nodes {
            self.node_key_map.entry(canonical).or_insert(node);
        }
        for (ek, dict) in mirrors {
            self.edge_py_attrs.entry(ek).or_insert(dict);
        }
        self.inner.extend_keyed_edges_with_attrs_unrecorded(edges);
        self.nodes_seq = self.nodes_seq.wrapping_add(node_bumps);
        self.edges_seq = self.edges_seq.wrapping_add(edge_bumps);
        Ok(true)
    }

    /// br-r37-c1-urle5b: native `(u, v, key)` no-data batch on a FRESH
    /// MultiDiGraph — see `PyMultiGraph::_native_add_keyed_edges_no_data`.
    /// Directed edges are NOT canonicalized, so the per-pair auto-key counter
    /// and the duplicate guard track `(u, v)` in order.
    fn _native_add_keyed_edges_no_data(
        &mut self,
        py: Python<'_>,
        ebunch_to_add: &Bound<'_, PyAny>,
    ) -> PyResult<bool> {
        if self.inner.edge_count() != 0
            || !self.succ_py_keys.is_empty()
            || !self.pred_py_keys.is_empty()
        {
            return Ok(false);
        }
        let Ok(list) = ebunch_to_add.downcast::<PyList>() else {
            return Ok(false);
        };
        let mut edges: Vec<(String, String, usize, fnx_classes::AttrMap)> =
            Vec::with_capacity(list.len());
        let mut display_keys: Vec<(String, String, usize, PyObject)> =
            Vec::with_capacity(list.len());
        let mut new_nodes: Vec<(String, PyObject)> = Vec::new();
        let mut seen_nodes: std::collections::HashSet<String> = self
            .inner
            .nodes_ordered()
            .into_iter()
            .map(str::to_owned)
            .collect();
        let mut batch_first: HashMap<String, PyObject> = HashMap::new();
        let mut pair_count: HashMap<(String, String), usize> = HashMap::new();
        let mut seen_edges: std::collections::HashSet<(String, String, String)> =
            std::collections::HashSet::new();
        let mut node_bumps = 0_u64;

        for item in list.iter() {
            let Ok(tuple) = item.downcast::<PyTuple>() else {
                return Ok(false);
            };
            if tuple.len() != 3 {
                return Ok(false);
            }
            let u = tuple.get_item(0)?;
            let v = tuple.get_item(1)?;
            let k = tuple.get_item(2)?;
            if !PyDiGraph::is_plain_batch_node(&u) || !PyDiGraph::is_plain_batch_node(&v) {
                return Ok(false);
            }
            if k.hash().is_err() {
                return Ok(false);
            }
            let uc = node_key_to_string(py, &u)?;
            let vc = node_key_to_string(py, &v)?;
            if self.batch_display_conflict(py, &uc, &u, &mut batch_first)
                || self.batch_display_conflict(py, &vc, &v, &mut batch_first)
            {
                return Ok(false);
            }
            let key_lookup = crate::edge_key_lookup_string(py, &k)?;
            if !seen_edges.insert((uc.clone(), vc.clone(), key_lookup)) {
                return Ok(false);
            }
            if !seen_nodes.contains(&uc) || !seen_nodes.contains(&vc) {
                node_bumps = node_bumps.wrapping_add(1);
            }
            if seen_nodes.insert(uc.clone()) {
                new_nodes.push((uc.clone(), u.clone().unbind()));
            }
            if seen_nodes.insert(vc.clone()) {
                new_nodes.push((vc.clone(), v.clone().unbind()));
            }
            let counter = pair_count.entry((uc.clone(), vc.clone())).or_insert(0);
            let internal_key = *counter;
            *counter += 1;
            display_keys.push((uc.clone(), vc.clone(), internal_key, k.clone().unbind()));
            edges.push((uc, vc, internal_key, fnx_classes::AttrMap::new()));
        }

        let edge_bumps = u64::try_from(edges.len()).unwrap_or(u64::MAX);
        let mirror_active = self.node_iter_mirror_active();
        for (canonical, node) in new_nodes {
            let mirror_key = if mirror_active {
                Some(canonical.clone())
            } else {
                None
            };
            self.node_key_map.entry(canonical).or_insert(node);
            if let Some(c) = mirror_key {
                let _ = self.node_iter_mirror_insert(py, &c);
            }
        }
        self.inner.extend_keyed_edges_with_attrs_unrecorded(edges);
        for (u, v, key, obj) in display_keys {
            self.edge_py_keys
                .entry(Self::edge_key(&u, &v, key))
                .or_insert(obj);
        }
        self.nodes_seq = self.nodes_seq.wrapping_add(node_bumps);
        self.edges_seq = self.edges_seq.wrapping_add(edge_bumps);
        Ok(true)
    }

    /// br-r37-c1-mgcompose: native `(u, v, key, data)` keyed-WITH-data batch on a
    /// FRESH MultiDiGraph — the with-data sibling of `_native_add_keyed_edges_no_data`,
    /// for compose/convert paths that replay a source multigraph's exact keys + attrs
    /// (`add_edges_from((u,v,key,dict(d)) ...)` otherwise pays per-edge
    /// add_edge_with_key_and_attrs = TWO record_decision/edge -> 0.32x vs nx). The user
    /// key `k` is stored as the DISPLAY key; the internal storage key is the per-pair
    /// auto counter (matching how this multigraph keys edges). Bails (Ok(false), NO
    /// mutation) on anything outside the exact all-4-tuple shape so the per-edge loop
    /// keeps every error/duplicate contract. Eager empty edge-attr dicts are dropped
    /// (lazy materialize is identity-preserving, aab122464).
    fn _native_add_keyed_edges_with_data(
        &mut self,
        py: Python<'_>,
        ebunch_to_add: &Bound<'_, PyAny>,
    ) -> PyResult<bool> {
        if self.inner.edge_count() != 0
            || !self.succ_py_keys.is_empty()
            || !self.pred_py_keys.is_empty()
        {
            return Ok(false);
        }
        let Ok(list) = ebunch_to_add.downcast::<PyList>() else {
            return Ok(false);
        };
        let mut edges: Vec<(String, String, usize, fnx_classes::AttrMap)> =
            Vec::with_capacity(list.len());
        let mut display_keys: Vec<(String, String, usize, PyObject)> =
            Vec::with_capacity(list.len());
        let mut mirrors: Vec<((String, String, usize), Py<PyDict>)> = Vec::new();
        let mut new_nodes: Vec<(String, PyObject)> = Vec::new();
        let mut seen_nodes: std::collections::HashSet<String> = self
            .inner
            .nodes_ordered()
            .into_iter()
            .map(str::to_owned)
            .collect();
        let mut batch_first: HashMap<String, PyObject> = HashMap::new();
        let mut pair_count: HashMap<(String, String), usize> = HashMap::new();
        let mut seen_edges: std::collections::HashSet<(String, String, String)> =
            std::collections::HashSet::new();
        let mut node_bumps = 0_u64;

        for item in list.iter() {
            let Ok(tuple) = item.downcast::<PyTuple>() else {
                return Ok(false);
            };
            if tuple.len() != 4 {
                return Ok(false);
            }
            let u = tuple.get_item(0)?;
            let v = tuple.get_item(1)?;
            let k = tuple.get_item(2)?;
            let data = tuple.get_item(3)?;
            if !PyDiGraph::is_plain_batch_node(&u) || !PyDiGraph::is_plain_batch_node(&v) {
                return Ok(false);
            }
            if k.hash().is_err() {
                return Ok(false);
            }
            let Ok(d) = data.downcast::<PyDict>() else {
                return Ok(false);
            };
            let Ok(rust_attrs) = py_dict_to_attr_map(d) else {
                return Ok(false);
            };
            if rust_attrs
                .keys()
                .any(|key| key.starts_with("__fnx_incompatible"))
            {
                return Ok(false);
            }
            let uc = node_key_to_string(py, &u)?;
            let vc = node_key_to_string(py, &v)?;
            if self.batch_display_conflict(py, &uc, &u, &mut batch_first)
                || self.batch_display_conflict(py, &vc, &v, &mut batch_first)
            {
                return Ok(false);
            }
            let key_lookup = crate::edge_key_lookup_string(py, &k)?;
            if !seen_edges.insert((uc.clone(), vc.clone(), key_lookup)) {
                return Ok(false);
            }
            if !seen_nodes.contains(&uc) || !seen_nodes.contains(&vc) {
                node_bumps = node_bumps.wrapping_add(1);
            }
            if seen_nodes.insert(uc.clone()) {
                new_nodes.push((uc.clone(), u.clone().unbind()));
            }
            if seen_nodes.insert(vc.clone()) {
                new_nodes.push((vc.clone(), v.clone().unbind()));
            }
            let counter = pair_count.entry((uc.clone(), vc.clone())).or_insert(0);
            let internal_key = *counter;
            *counter += 1;
            if !d.is_empty() {
                let mirror = PyDict::new(py);
                mirror.update(d.as_mapping())?;
                mirrors.push((Self::edge_key(&uc, &vc, internal_key), mirror.unbind()));
            }
            display_keys.push((uc.clone(), vc.clone(), internal_key, k.clone().unbind()));
            edges.push((uc, vc, internal_key, rust_attrs));
        }

        let edge_bumps = u64::try_from(edges.len()).unwrap_or(u64::MAX);
        let mirror_active = self.node_iter_mirror_active();
        for (canonical, node) in new_nodes {
            let mirror_key = if mirror_active {
                Some(canonical.clone())
            } else {
                None
            };
            self.node_key_map.entry(canonical).or_insert(node);
            if let Some(c) = mirror_key {
                let _ = self.node_iter_mirror_insert(py, &c);
            }
        }
        self.inner.extend_keyed_edges_with_attrs_unrecorded(edges);
        for (ek, dict) in mirrors {
            self.edge_py_attrs.entry(ek).or_insert(dict);
        }
        for (u, v, key, obj) in display_keys {
            self.edge_py_keys
                .entry(Self::edge_key(&u, &v, key))
                .or_insert(obj);
        }
        self.nodes_seq = self.nodes_seq.wrapping_add(node_bumps);
        self.edges_seq = self.edges_seq.wrapping_add(edge_bumps);
        Ok(true)
    }

    /// br-r37-c1-natdiff: fully-native `difference(G, H)` for MultiDiGraph — builds
    /// the result entirely in Rust (G's nodes, no data; G's edges whose DISPLAY
    /// `(u, v, key)` is not in H), eliminating BOTH the per-edge `add_edge`
    /// construction tax AND the Python `set(*.edges(keys=True))` EdgeView
    /// materialization the wrapper otherwise pays twice. H's display edges are
    /// hashed into a canonical `(u, v, key_lookup)` set; G is walked in
    /// `edges(keys=True)` order (node-major / successor / key) and kept edges are
    /// re-keyed sequentially per pair on the fresh result, carrying G's display
    /// key object. Returns `None` (so the wrapper falls back) when H is not an
    /// exact MultiDiGraph. The caller validates node-set equality first.
    fn _native_difference(
        slf: PyRef<'_, Self>,
        py: Python<'_>,
        h: &Bound<'_, PyAny>,
    ) -> PyResult<Option<Py<Self>>> {
        let Ok(h_ref) = h.extract::<PyRef<'_, Self>>() else {
            return Ok(None);
        };
        let g = &*slf;
        let hh = &*h_ref;

        // H's display-edge canonical set.
        let mut h_set: std::collections::HashSet<(String, String, String)> =
            std::collections::HashSet::new();
        for u in hh.inner.nodes_ordered() {
            for v in hh.inner.successors(u).unwrap_or_default() {
                for key in hh.inner.edge_keys(u, v).unwrap_or_default() {
                    let kl = hh.display_key_lookup(py, u, v, key)?;
                    h_set.insert((u.to_owned(), v.to_owned(), kl));
                }
            }
        }

        let mut r = Self::new_empty_with_mode(py, g.inner.mode())?;
        let g_nodes: Vec<String> = g
            .inner
            .nodes_ordered()
            .into_iter()
            .map(str::to_owned)
            .collect();
        for node in &g_nodes {
            r.node_key_map.insert(node.clone(), g.py_node_key(py, node));
        }
        let _ = r.inner.extend_nodes_with_attrs_unrecorded(
            g_nodes
                .iter()
                .map(|n| (n.clone(), fnx_classes::AttrMap::new())),
        );

        let mut edges: Vec<(String, String, usize, fnx_classes::AttrMap)> = Vec::new();
        let mut display: Vec<(String, String, usize, PyObject)> = Vec::new();
        let mut pair_count: HashMap<(String, String), usize> = HashMap::new();
        for u in &g_nodes {
            for v in g.inner.successors(u).unwrap_or_default() {
                let vk = v.to_owned();
                for key in g.inner.edge_keys(u, &vk).unwrap_or_default() {
                    let kl = g.display_key_lookup(py, u, &vk, key)?;
                    if !h_set.contains(&(u.clone(), vk.clone(), kl)) {
                        let counter = pair_count.entry((u.clone(), vk.clone())).or_insert(0);
                        let internal = *counter;
                        *counter += 1;
                        let disp = g.py_edge_key(py, u, &vk, key);
                        edges.push((u.clone(), vk.clone(), internal, fnx_classes::AttrMap::new()));
                        display.push((u.clone(), vk.clone(), internal, disp));
                    }
                }
            }
        }
        let n_edges = edges.len();
        let _ = r.inner.extend_keyed_edges_with_attrs_unrecorded(edges);
        for (u, v, key, obj) in display {
            r.edge_py_keys
                .entry(Self::edge_key(&u, &v, key))
                .or_insert(obj);
        }
        r.nodes_seq = u64::try_from(g_nodes.len()).unwrap_or(u64::MAX);
        r.edges_seq = u64::try_from(n_edges).unwrap_or(u64::MAX);
        Py::new(py, r).map(Some)
    }

    /// br-r37-c1-y0xps: fully-native `symmetric_difference(G, H)` for
    /// MultiDiGraph. This mirrors the Python wrapper's order exactly: G-only
    /// edges first, then H-only edges, with display-key equality matching
    /// NetworkX dict semantics through `display_key_lookup`.
    fn _native_symmetric_difference(
        slf: PyRef<'_, Self>,
        py: Python<'_>,
        h: &Bound<'_, PyAny>,
    ) -> PyResult<Option<Py<Self>>> {
        let Ok(h_ref) = h.extract::<PyRef<'_, Self>>() else {
            return Ok(None);
        };
        let g = &*slf;
        let hh = &*h_ref;

        let mut h_set: HashSet<(String, String, String)> = HashSet::new();
        for u in hh.inner.nodes_ordered() {
            for v in hh.inner.successors(u).unwrap_or_default() {
                for key in hh.inner.edge_keys(u, v).unwrap_or_default() {
                    let kl = hh.display_key_lookup(py, u, v, key)?;
                    h_set.insert((u.to_owned(), v.to_owned(), kl));
                }
            }
        }

        let mut g_set: HashSet<(String, String, String)> = HashSet::new();
        for u in g.inner.nodes_ordered() {
            for v in g.inner.successors(u).unwrap_or_default() {
                for key in g.inner.edge_keys(u, v).unwrap_or_default() {
                    let kl = g.display_key_lookup(py, u, v, key)?;
                    g_set.insert((u.to_owned(), v.to_owned(), kl));
                }
            }
        }

        let mut r = Self::new_empty_with_mode(py, g.inner.mode())?;
        let g_nodes: Vec<String> = g
            .inner
            .nodes_ordered()
            .into_iter()
            .map(str::to_owned)
            .collect();
        for node in &g_nodes {
            r.node_key_map.insert(node.clone(), g.py_node_key(py, node));
        }
        let _ = r.inner.extend_nodes_with_attrs_unrecorded(
            g_nodes
                .iter()
                .map(|n| (n.clone(), fnx_classes::AttrMap::new())),
        );

        let mut edges: Vec<(String, String, usize, fnx_classes::AttrMap)> = Vec::new();
        let mut display: Vec<(String, String, usize, PyObject)> = Vec::new();
        let mut pair_count: HashMap<(String, String), usize> = HashMap::new();

        for u in &g_nodes {
            for v in g.inner.successors(u).unwrap_or_default() {
                let vk = v.to_owned();
                for key in g.inner.edge_keys(u, &vk).unwrap_or_default() {
                    let kl = g.display_key_lookup(py, u, &vk, key)?;
                    if !h_set.contains(&(u.clone(), vk.clone(), kl)) {
                        let counter = pair_count.entry((u.clone(), vk.clone())).or_insert(0);
                        let internal = *counter;
                        *counter += 1;
                        let disp = g.py_edge_key(py, u, &vk, key);
                        edges.push((u.clone(), vk.clone(), internal, fnx_classes::AttrMap::new()));
                        display.push((u.clone(), vk.clone(), internal, disp));
                    }
                }
            }
        }

        let h_nodes: Vec<String> = hh
            .inner
            .nodes_ordered()
            .into_iter()
            .map(str::to_owned)
            .collect();
        for u in &h_nodes {
            for v in hh.inner.successors(u).unwrap_or_default() {
                let vk = v.to_owned();
                for key in hh.inner.edge_keys(u, &vk).unwrap_or_default() {
                    let kl = hh.display_key_lookup(py, u, &vk, key)?;
                    if !g_set.contains(&(u.clone(), vk.clone(), kl)) {
                        let counter = pair_count.entry((u.clone(), vk.clone())).or_insert(0);
                        let internal = *counter;
                        *counter += 1;
                        let disp = hh.py_edge_key(py, u, &vk, key);
                        edges.push((u.clone(), vk.clone(), internal, fnx_classes::AttrMap::new()));
                        display.push((u.clone(), vk.clone(), internal, disp));
                    }
                }
            }
        }

        let n_edges = edges.len();
        let _ = r.inner.extend_keyed_edges_with_attrs_unrecorded(edges);
        for (u, v, key, obj) in display {
            r.edge_py_keys
                .entry(Self::edge_key(&u, &v, key))
                .or_insert(obj);
        }
        r.nodes_seq = u64::try_from(g_nodes.len()).unwrap_or(u64::MAX);
        r.edges_seq = u64::try_from(n_edges).unwrap_or(u64::MAX);
        Py::new(py, r).map(Some)
    }

    #[pyo3(signature = (u_for_edge, v_for_edge, key=None, **attr))]
    fn add_edge(
        &mut self,
        py: Python<'_>,
        u_for_edge: &Bound<'_, PyAny>,
        v_for_edge: &Bound<'_, PyAny>,
        key: Option<&Bound<'_, PyAny>>,
        attr: Option<&Bound<'_, PyDict>>,
    ) -> PyResult<PyObject> {
        let u = u_for_edge;
        let v = v_for_edge;
        let u_canonical = node_key_to_string(py, u)?;
        let v_canonical = node_key_to_string(py, v)?;

        // br-r37-c1-39d82: track new-node creation to bump
        // nodes_seq for iterator staleness detection.
        let u_was_new = !self.node_key_map.contains_key(&u_canonical);
        let v_was_new = !self.node_key_map.contains_key(&v_canonical);
        let __was_new = u_was_new || v_was_new;
        self.node_key_map
            .entry(u_canonical.clone())
            .or_insert_with(|| u.clone().unbind());
        self.node_key_map
            .entry(v_canonical.clone())
            .or_insert_with(|| v.clone().unbind());
        if __was_new {
            self.bump_nodes_seq();
            // Keep the node-iteration mirror live (nx order: u before v).
            if self.node_iter_mirror_active() {
                if u_was_new {
                    self.node_iter_mirror_insert(py, &u_canonical)?;
                }
                if v_was_new {
                    self.node_iter_mirror_insert(py, &v_canonical)?;
                }
            }
        }
        // br-r37-c1-z6uka: a NEW (u, v) cell (no keys yet for this pair)
        // records both row display objects; parallel keys reuse the cell.
        if !self.inner.has_edge(&u_canonical, &v_canonical) {
            self.maybe_store_row_keys(py, &u_canonical, &v_canonical, u, v);
        }
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
        if let Some(explicit_key) = key
            && !explicit_key.is_none()
            && explicit_key.hash().is_err()
        {
            // br-r37-c1-baqyi: nx creates BOTH endpoint nodes before the
            // unhashable key raises (key is first used after node
            // insertion). Also keeps inner consistent with the mirror
            // inserts above (which already ran).
            self.add_node(py, u, None)?;
            self.add_node(py, v, None)?;
            explicit_key.hash()?;
        }
        let actual_key = match key {
            Some(explicit_key) => {
                if let Some(internal_key) =
                    self.resolve_internal_edge_key(py, &u_canonical, &v_canonical, explicit_key)?
                {
                    self.inner
                        .add_edge_with_key_and_attrs(
                            u_canonical.clone(),
                            v_canonical.clone(),
                            internal_key,
                            rust_attrs,
                        )
                        .map_err(|e| NetworkXError::new_err(e.to_string()))?
                } else {
                    self.inner
                        .add_edge_with_attrs(u_canonical.clone(), v_canonical.clone(), rust_attrs)
                        .map_err(|e| NetworkXError::new_err(e.to_string()))?
                }
            }
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
        // br-r37-c1-jft0i: bump edges_seq so view-materialization caches invalidate.
        self.bump_edges_seq();
        Ok(self.remember_edge_key(py, &u_canonical, &v_canonical, actual_key, key))
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
                        // br-r37-c1-baqyi: nx tries ddd.update(dd) FIRST;
                        // only a TypeError/ValueError makes the third
                        // element the key. Dict-able iterables of pairs
                        // are DATA.
                        let throwaway = PyDict::new(py);
                        match throwaway.call_method1("update", (&third,)) {
                            Ok(_) => {
                                merged.update(throwaway.as_mapping())?;
                                self.add_edge(
                                    py,
                                    &tuple.get_item(0)?,
                                    &tuple.get_item(1)?,
                                    None,
                                    Some(&merged),
                                )?;
                            }
                            Err(err)
                                if err.is_instance_of::<PyTypeError>(py)
                                    || err.is_instance_of::<PyValueError>(py) =>
                            {
                                self.add_edge(
                                    py,
                                    &tuple.get_item(0)?,
                                    &tuple.get_item(1)?,
                                    Some(&third),
                                    Some(&merged),
                                )?;
                            }
                            Err(err) => return Err(err),
                        }
                    }
                }
                4 => {
                    let edge_key = tuple.get_item(2)?;
                    let fourth = tuple.get_item(3)?;
                    if let Ok(d) = fourth.downcast::<PyDict>() {
                        merged.update(d.as_mapping())?;
                    } else {
                        // br-r37-c1-baqyi: nx's ddd.update(dd) runs BEFORE
                        // add_edge — a non-dict 4th element raises with
                        // NOTHING created (fnx previously ignored it and
                        // added the edge). Dict-able iterables of pairs
                        // still merge.
                        let throwaway = PyDict::new(py);
                        throwaway.call_method1("update", (&fourth,))?;
                        merged.update(throwaway.as_mapping())?;
                    }
                    self.add_edge(
                        py,
                        &tuple.get_item(0)?,
                        &tuple.get_item(1)?,
                        Some(&edge_key),
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
        self.bump_edges_seq();
        Ok(())
    }

    #[pyo3(signature = (u, v, key=None))]
    fn remove_edge(
        &mut self,
        py: Python<'_>,
        u: &Bound<'_, PyAny>,
        v: &Bound<'_, PyAny>,
        key: Option<&Bound<'_, PyAny>>,
    ) -> PyResult<()> {
        let u_canonical = node_key_to_string(py, u)?;
        let v_canonical = node_key_to_string(py, v)?;
        let auto_removal_key = match key {
            Some(explicit_key) => {
                self.resolve_internal_edge_key(py, &u_canonical, &v_canonical, explicit_key)?
            }
            None => self
                .inner
                .edge_keys(&u_canonical, &v_canonical)
                .and_then(|keys| keys.last().copied()),
        };
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
            self.remove_edge_metadata(&u_canonical, &v_canonical, explicit_key);
        }
        if (!self.succ_py_keys.is_empty() || !self.pred_py_keys.is_empty())
            && !self.inner.has_edge(&u_canonical, &v_canonical)
        {
            // br-r37-c1-z6uka: the LAST key emptied the (u, v) cell — nx
            // deletes the row entries, so a re-add creates fresh objects.
            self.succ_py_keys
                .remove(&(u_canonical.clone(), v_canonical.clone()));
            self.pred_py_keys.remove(&(v_canonical, u_canonical));
        }
        self.bump_edges_seq();
        Ok(())
    }

    fn remove_node(&mut self, py: Python<'_>, n: &Bound<'_, PyAny>) -> PyResult<()> {
        let canonical = node_key_to_string(py, n)?;
        if !self.inner.has_node(&canonical) {
            return Err(crate::NetworkXError::new_err(format!(
                "The node {} is not in the graph.",
                n.repr()?
            )));
        }

        // surgically remove attributes for incident edges before removing node from inner graph
        let mut had_incident_edges = false;
        let succs = self
            .inner
            .successors(&canonical)
            .map(|succs| succs.into_iter().map(str::to_owned).collect::<Vec<_>>());
        if let Some(succs) = succs {
            for v in succs {
                if let Some(keys) = self.inner.edge_keys(&canonical, &v) {
                    for key in keys {
                        self.remove_edge_metadata(&canonical, &v, key);
                        had_incident_edges = true;
                    }
                }
            }
        }
        let preds = self
            .inner
            .predecessors(&canonical)
            .map(|preds| preds.into_iter().map(str::to_owned).collect::<Vec<_>>());
        if let Some(preds) = preds {
            for u in preds {
                if let Some(keys) = self.inner.edge_keys(&u, &canonical) {
                    for key in keys {
                        self.remove_edge_metadata(&u, &canonical, key);
                        had_incident_edges = true;
                    }
                }
            }
        }

        if self.node_iter_mirror_active() {
            // Remove from the live mirror while node_key_map still holds the
            // display object (mirror keys are the display py objects).
            let py_key = self.py_node_key(py, &canonical);
            self.node_iter_mirror_remove_key(py, py_key.bind(py));
        }
        self.inner.remove_node(&canonical);
        self.node_key_map.remove(&canonical);
        self.node_py_attrs.remove(&canonical);
        if !self.succ_py_keys.is_empty() || !self.pred_py_keys.is_empty() {
            // br-r37-c1-z6uka: drop cell overrides touching the removed node.
            self.succ_py_keys
                .retain(|(a, b), _| a != &canonical && b != &canonical);
            self.pred_py_keys
                .retain(|(a, b), _| a != &canonical && b != &canonical);
        }
        self.bump_nodes_seq();
        // br-r37-c1-jft0i: removing a node with incident edges also mutates the
        // edge set, so bump edges_seq to invalidate edge-keyed caches.
        if had_incident_edges {
            self.bump_edges_seq();
        }
        Ok(())
    }

    fn remove_nodes_from(&mut self, py: Python<'_>, nodes: &Bound<'_, PyAny>) -> PyResult<()> {
        let iter = PyIterator::from_object(nodes)?;
        let mut had_incident_edges = false;
        for item in iter {
            let item = item?;
            let canonical = node_key_to_string(py, &item)?;
            if self.inner.has_node(&canonical) {
                let succs = self
                    .inner
                    .successors(&canonical)
                    .map(|succs| succs.into_iter().map(str::to_owned).collect::<Vec<_>>());
                if let Some(succs) = succs {
                    for v in succs {
                        if let Some(keys) = self.inner.edge_keys(&canonical, &v) {
                            for key in keys {
                                self.remove_edge_metadata(&canonical, &v, key);
                                had_incident_edges = true;
                            }
                        }
                    }
                }
                let preds = self
                    .inner
                    .predecessors(&canonical)
                    .map(|preds| preds.into_iter().map(str::to_owned).collect::<Vec<_>>());
                if let Some(preds) = preds {
                    for u in preds {
                        if let Some(keys) = self.inner.edge_keys(&u, &canonical) {
                            for key in keys {
                                self.remove_edge_metadata(&u, &canonical, key);
                                had_incident_edges = true;
                            }
                        }
                    }
                }
                if self.node_iter_mirror_active() {
                    // Remove from the live mirror before node_key_map drops the
                    // display object (mirror keys are the display py objects).
                    let py_key = self.py_node_key(py, &canonical);
                    self.node_iter_mirror_remove_key(py, py_key.bind(py));
                }
                self.inner.remove_node(&canonical);
                self.node_key_map.remove(&canonical);
                self.node_py_attrs.remove(&canonical);
                if !self.succ_py_keys.is_empty() || !self.pred_py_keys.is_empty() {
                    // br-r37-c1-z6uka: drop cell overrides touching removed nodes.
                    self.succ_py_keys
                        .retain(|(a, b), _| a != &canonical && b != &canonical);
                    self.pred_py_keys
                        .retain(|(a, b), _| a != &canonical && b != &canonical);
                }
            }
        }
        self.bump_nodes_seq();
        if had_incident_edges {
            self.bump_edges_seq(); // br-r37-c1-jft0i
        }
        Ok(())
    }

    #[pyo3(signature = (u, v, key=None))]
    fn has_edge(
        &self,
        py: Python<'_>,
        u: &Bound<'_, PyAny>,
        v: &Bound<'_, PyAny>,
        key: Option<&Bound<'_, PyAny>>,
    ) -> PyResult<bool> {
        let u_c = node_key_to_string(py, u)?;
        let v_c = node_key_to_string(py, v)?;
        Ok(match key {
            Some(edge_key) => self
                .resolve_internal_edge_key(py, &u_c, &v_c, edge_key)?
                .is_some_and(|internal_key| {
                    self.inner.edge_attrs(&u_c, &v_c, internal_key).is_some()
                }),
            None => self.inner.has_edge(&u_c, &v_c),
        })
    }

    fn successors(&self, py: Python<'_>, n: &Bound<'_, PyAny>) -> PyResult<Vec<PyObject>> {
        let canonical = node_key_to_string(py, n)?;
        match self.inner.successors(&canonical) {
            Some(succs) => Ok(succs
                .into_iter()
                .map(
                    |s| self.py_succ_key(py, &canonical, s), /* br-r37-c1-z6uka */
                )
                .collect()),
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
            Some(preds) => Ok(preds
                .into_iter()
                .map(
                    |p| self.py_pred_key(py, &canonical, p), /* br-r37-c1-z6uka */
                )
                .collect()),
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
        self.inner = MultiDiGraph::with_runtime_policy(self.inner.runtime_policy().clone());
        self.node_key_map.clear();
        self.node_py_attrs.clear();
        self.edge_py_attrs.clear();
        self.succ_py_keys.clear(); // br-r37-c1-z6uka
        self.pred_py_keys.clear(); // br-r37-c1-z6uka
        self.edge_py_keys.clear();
        self.graph_attrs = PyDict::new(py).unbind();
        // Clear the live mirror in place so an in-flight iter raises like nx.
        self.node_iter_mirror_clear(py)?;
        self.bump_nodes_seq();
        self.bump_edges_seq(); // br-r37-c1-jft0i
        Ok(())
    }

    fn clear_edges(&mut self) {
        // br-r37-c1-pb8bj: capture node INSERTION order before resetting inner.
        // The old code re-added nodes by iterating `node_key_map.keys()` (a
        // HashMap — random order), scrambling node order vs nx, which preserves
        // insertion order across clear_edges(). `nodes_ordered()` keeps it.
        let ordered: Vec<String> = self
            .inner
            .nodes_ordered()
            .into_iter()
            .map(str::to_owned)
            .collect();
        // br-r37-c1-1uv81: rebuild a FRESH inner (the old code re-added nodes
        // into the existing graph, leaving every edge in place — clear_edges
        // was a no-op for MultiDiGraph; the other three classes reset inner).
        let policy = self.inner.runtime_policy().clone();
        Python::attach(|py| {
            let mut fresh = MultiDiGraph::with_runtime_policy(policy);
            for canonical in &ordered {
                let rust_attrs = self
                    .node_py_attrs
                    .get(canonical)
                    .map(|attrs| crate::py_dict_to_attr_map(attrs.bind(py)))
                    .transpose()
                    .ok()
                    .flatten()
                    .unwrap_or_default();
                fresh.add_node_with_attrs(canonical.clone(), rust_attrs);
            }
            self.inner = fresh;
        });
        self.edge_py_attrs.clear();
        self.succ_py_keys.clear(); // br-r37-c1-z6uka
        self.pred_py_keys.clear(); // br-r37-c1-z6uka
        self.edge_py_keys.clear();
        self.bump_edges_seq(); // br-r37-c1-jft0i
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

    fn __iter__(slf: PyRef<'_, Self>) -> PyResult<PyObject> {
        // Serve iteration from the live node_iter_mirror dict_keyiterator
        // (matching nx) instead of rebuilding a Vec<PyObject> per call.
        let py = slf.py();
        let mirror = slf.node_iter_mirror_or_init(py)?;
        Ok(mirror.bind(py).call_method0("__iter__")?.unbind())
    }

    fn _native_successor_row(
        slf: PyRef<'_, Self>,
        n: &Bound<'_, PyAny>,
    ) -> PyResult<Py<MultiDiAtlasView>> {
        let py = slf.py();
        let canonical = node_key_to_string(py, n)?;
        if !slf.inner.has_node(&canonical) {
            return Err(crate::missing_key_error(n));
        }
        Py::new(
            py,
            MultiDiAtlasView::new(Py::from(slf), canonical, MultiDiAdjKind::Successors),
        )
    }

    fn _native_to_dict_of_dicts_live(
        slf: PyRef<'_, Self>,
        view_cls: &Bound<'_, PyAny>,
        cache: &Bound<'_, PyDict>,
    ) -> PyResult<Py<PyDict>> {
        let py = slf.py();
        let graph = Py::from(slf);
        let g = graph.borrow(py);
        let result = PyDict::new(py);
        for node in g.inner.nodes_ordered() {
            let py_node = g.py_node_key(py, node);
            let row = PyDict::new(py);
            let row_cache: Py<PyDict> = match cache.get_item(py_node.bind(py))? {
                Some(existing) => existing.downcast::<PyDict>()?.clone().unbind(),
                None => {
                    let created = PyDict::new(py);
                    cache.set_item(py_node.bind(py), &created)?;
                    created.unbind()
                }
            };
            let row_cache = row_cache.bind(py);
            for neighbor in g.inner.successors(node).unwrap_or_default() {
                let py_neighbor = g.py_succ_key(py, node, neighbor);
                if let Some(view) = row_cache.get_item(py_neighbor.bind(py))? {
                    row.set_item(py_neighbor.bind(py), &view)?;
                } else {
                    let view = view_cls.call1((
                        graph.clone_ref(py),
                        py_node.clone_ref(py),
                        py_neighbor.clone_ref(py),
                    ))?;
                    row_cache.set_item(py_neighbor.bind(py), &view)?;
                    row.set_item(py_neighbor.bind(py), &view)?;
                }
            }
            result.set_item(py_node.bind(py), row)?;
        }
        Ok(result.unbind())
    }

    fn _native_predecessor_row(
        slf: PyRef<'_, Self>,
        n: &Bound<'_, PyAny>,
    ) -> PyResult<Py<MultiDiAtlasView>> {
        let py = slf.py();
        let canonical = node_key_to_string(py, n)?;
        if !slf.inner.has_node(&canonical) {
            return Err(crate::missing_key_error(n));
        }
        Py::new(
            py,
            MultiDiAtlasView::new(Py::from(slf), canonical, MultiDiAdjKind::Predecessors),
        )
    }

    // br-r37-c1-gchm1: plain dict-of-dicts row accessors mirroring
    // PyDiGraph's. Unlike _native_*_row (which returns a lazy
    // MultiDiAtlasView whose inner values are MultiDiKeyDictView), these
    // materialise to a PLAIN {neighbor: {key: attrs}} dict — the exact
    // type nx exposes for .succ/.pred rows — so reverse/filtered views can
    // read them at O(deg) without breaking deep snapshot/type parity.
    fn _native_successor_row_dict(
        &self,
        py: Python<'_>,
        n: &Bound<'_, PyAny>,
    ) -> PyResult<Py<PyDict>> {
        let canonical = node_key_to_string(py, n)?;
        if !self.inner.has_node(&canonical) {
            return Err(crate::missing_key_error(n));
        }
        let row = PyDict::new(py);
        let neighbors: Vec<String> = self
            .inner
            .successors(&canonical)
            .unwrap_or_default()
            .into_iter()
            .map(str::to_owned)
            .collect();
        for neighbor in &neighbors {
            let py_neighbor = self.py_succ_key(py, &canonical, neighbor);
            let keydict = self.multi_row_keydict(py, &canonical, neighbor)?;
            row.set_item(py_neighbor, keydict.bind(py))?;
        }
        Ok(row.unbind())
    }

    fn _native_predecessor_row_dict(
        &self,
        py: Python<'_>,
        n: &Bound<'_, PyAny>,
    ) -> PyResult<Py<PyDict>> {
        let canonical = node_key_to_string(py, n)?;
        if !self.inner.has_node(&canonical) {
            return Err(crate::missing_key_error(n));
        }
        let row = PyDict::new(py);
        let neighbors: Vec<String> = self
            .inner
            .predecessors(&canonical)
            .unwrap_or_default()
            .into_iter()
            .map(str::to_owned)
            .collect();
        for neighbor in &neighbors {
            let py_neighbor = self.py_pred_key(py, &canonical, neighbor);
            // pred edge is (neighbor -> canonical): source=neighbor, target=canonical
            let keydict = self.multi_row_keydict(py, neighbor, &canonical)?;
            row.set_item(py_neighbor, keydict.bind(py))?;
        }
        Ok(row.unbind())
    }

    /// br-r37-c1-i5cf1: bulk predecessor KEY order for every node, in one native
    /// crossing. Returns ``[(node, [pred, ...]), ...]`` in ``nodes_ordered``
    /// order, each predecessor list in the inner ``predecessors`` (== fg.pred /
    /// edge-insertion) order, with the z6uka display-key override applied. This
    /// is the cheap source ``_fnx_to_nx`` needs to realign a converted
    /// MultiDiGraph's ``_pred`` rows without the per-node AtlasView walk
    /// (``{v: list(fg.pred[v])}`` is an O(V*deg) wrapper tax).
    fn _native_predecessor_keys_bulk(
        &self,
        py: Python<'_>,
    ) -> PyResult<Vec<(PyObject, Vec<PyObject>)>> {
        let nodes: Vec<String> = self
            .inner
            .nodes_ordered()
            .into_iter()
            .map(str::to_owned)
            .collect();
        let mut out: Vec<(PyObject, Vec<PyObject>)> = Vec::with_capacity(nodes.len());
        for node in &nodes {
            let preds: Vec<PyObject> = self
                .inner
                .predecessors(node)
                .unwrap_or_default()
                .into_iter()
                .map(|p| self.py_pred_key(py, node, p))
                .collect();
            out.push((self.py_node_key(py, node), preds));
        }
        Ok(out)
    }

    fn __getitem__(slf: PyRef<'_, Self>, n: &Bound<'_, PyAny>) -> PyResult<Py<MultiDiAtlasView>> {
        Self::_native_successor_row(slf, n)
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
}

#[pymethods]
impl PyMultiDiGraph {
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

    /// br-r37-c1-tmuly: non-shadowed accessor for the native edge view. The
    /// Python-side MultiDiGraph.edges is overridden with a property returning a
    /// pure-Python _MultiDiGraphEdgeView whose __call__ triple-loops over the
    /// succ AtlasView lambdas (~3000-7000x slower than nx). The Python view now
    /// materializes its result list from THIS native view (which builds tuples
    /// from inner.edges_ordered() in nx order, reusing the live edge dicts).
    fn _native_edge_view(slf: PyRef<'_, Self>) -> PyResult<Py<MultiDiGraphEdgeView>> {
        let py = slf.py();
        let graph_py: Py<PyMultiDiGraph> = Py::from(slf);
        Py::new(py, MultiDiGraphEdgeView { graph: graph_py })
    }

    fn _native_edge_view_list(
        &mut self,
        py: Python<'_>,
        data: &Bound<'_, PyAny>,
        keys: bool,
        default: PyObject,
    ) -> PyResult<Vec<PyObject>> {
        self.native_edge_view_list(py, data, keys, default)
    }

    #[getter]
    fn degree(slf: PyRef<'_, Self>) -> PyResult<Py<MultiDiGraphDegreeView>> {
        let py = slf.py();
        let graph_py: Py<PyMultiDiGraph> = Py::from(slf);
        Py::new(
            py,
            MultiDiGraphDegreeView {
                graph: graph_py,
                kind: DegreeKind::Total,
            },
        )
    }

    #[getter]
    fn in_degree(slf: PyRef<'_, Self>) -> PyResult<Py<MultiDiGraphDegreeView>> {
        let py = slf.py();
        let graph_py: Py<PyMultiDiGraph> = Py::from(slf);
        Py::new(
            py,
            MultiDiGraphDegreeView {
                graph: graph_py,
                kind: DegreeKind::In,
            },
        )
    }

    #[getter]
    fn out_degree(slf: PyRef<'_, Self>) -> PyResult<Py<MultiDiGraphDegreeView>> {
        let py = slf.py();
        let graph_py: Py<PyMultiDiGraph> = Py::from(slf);
        Py::new(
            py,
            MultiDiGraphDegreeView {
                graph: graph_py,
                kind: DegreeKind::Out,
            },
        )
    }

    /// br-r37-c1-kjaqc: O(1)-amortized native single-node out-degree (edge
    /// multiplicity), used by the Python _DirectedDegreeView fast path so the
    /// unweighted MultiDiGraph case avoids the pure-Python
    /// sum(len(keydict) for keydict in succ_atlasview.values()) walk.
    fn _native_out_degree(&self, py: Python<'_>, n: &Bound<'_, PyAny>) -> PyResult<usize> {
        let canonical = node_key_to_string(py, n)?;
        Ok(self.inner.out_degree(&canonical))
    }

    /// br-r37-c1-kjaqc: O(1)-amortized native single-node in-degree (see above).
    fn _native_in_degree(&self, py: Python<'_>, n: &Bound<'_, PyAny>) -> PyResult<usize> {
        let canonical = node_key_to_string(py, n)?;
        Ok(self.inner.in_degree(&canonical))
    }

    // br-r37-c1-snabulk: native bulk set_node_attributes(values, name)
    // — one Rust loop over the values dict (mirror is authoritative;
    // inner refreshed at copy/export; missing nodes skipped per nx).

    /// br-r37-c1-seabulk-multi: native bulk set_edge_attributes for
    /// multigraphs — keys are (u, v, key) 3-tuples. Resolves the
    /// internal edge key, sets the edge_py_attrs mirror, marks dirty
    /// once (lazy inner flush reaches kernels). Non-3-tuples skipped
    /// (nx ValueError-on-unpack swallow); missing edge/key skipped.
    fn _native_set_edge_attribute_scalar_multi(
        &mut self,
        py: Python<'_>,
        values: &Bound<'_, PyDict>,
        name: &str,
    ) -> PyResult<()> {
        for (k, val) in values.iter() {
            let Ok(len) = k.len() else { continue };
            if len != 3 {
                continue;
            }
            let u = node_key_to_string(py, &k.get_item(0)?)?;
            let v = node_key_to_string(py, &k.get_item(1)?)?;
            let key_obj = k.get_item(2)?;
            if let Some(internal_key) = self.resolve_internal_edge_key(py, &u, &v, &key_obj)? {
                let ek = Self::edge_key(&u, &v, internal_key);
                let dict = self
                    .edge_py_attrs
                    .entry(ek)
                    .or_insert_with(|| PyDict::new(py).unbind());
                dict.bind(py).set_item(name, &val)?;
            }
        }
        self.mark_edges_dirty();
        Ok(())
    }

    fn _native_set_node_attribute_scalar(
        &mut self,
        py: Python<'_>,
        values: &Bound<'_, PyDict>,
        name: &str,
    ) -> PyResult<()> {
        for (k, v) in values.iter() {
            let canonical = node_key_to_string(py, &k)?;
            if self.inner.has_node(&canonical) {
                let dict = self
                    .node_py_attrs
                    .entry(canonical)
                    .or_insert_with(|| PyDict::new(py).unbind());
                dict.bind(py).set_item(name, &v)?;
            }
        }
        Ok(())
    }

    /// br-r37-c1-degidx: bulk (node, in/out-degree) pairs — one Rust
    /// loop instead of N per-node PyO3 round-trips. Multi rows are still
    /// String-keyed (s2teo unflipped), so this sums IndexSet lens per
    /// node, but in a single native pass.
    fn _native_out_degree_pairs(&self, py: Python<'_>) -> PyResult<Vec<(PyObject, usize)>> {
        let names: Vec<String> = self
            .inner
            .nodes_ordered()
            .iter()
            .map(|s| (*s).to_owned())
            .collect();
        Ok(names
            .iter()
            .map(|n| (self.py_node_key(py, n), self.inner.out_degree(n)))
            .collect())
    }

    fn _native_in_degree_pairs(&self, py: Python<'_>) -> PyResult<Vec<(PyObject, usize)>> {
        let names: Vec<String> = self
            .inner
            .nodes_ordered()
            .iter()
            .map(|s| (*s).to_owned())
            .collect();
        Ok(names
            .iter()
            .map(|n| (self.py_node_key(py, n), self.inner.in_degree(n)))
            .collect())
    }

    /// br-r37-c1-mdgoutedge (cc): MultiDiGraph out_edges(nbunch, data=False). nx
    /// iterates succ[u].items() keydicts in Python; this walks successors x
    /// edge_keys in rust (no dedup — directed edges unique), node-deduped, emitting
    /// (u, v) or (u, v, key). Gated on succ_py_keys empty (+ edge_py_keys for keys).
    fn _native_mdg_out_edges_nbunch_no_data(
        &self,
        py: Python<'_>,
        nbunch: &Bound<'_, PyAny>,
        keys: bool,
    ) -> PyResult<Option<Vec<PyObject>>> {
        // br-r37-c1-mdgoutedge (cc): keys=True no longer gates on edge_py_keys — it
        // emits the DISPLAY key via py_edge_key (== fnx's own out_edges(keys=True);
        // falls back to the internal int when no mirror). The prior edge_py_keys gate
        // sent keys=True to the slow self.edges path for every MultiDiGraph(gnm)
        // (which carries an edge_py_keys mirror). Pairs with the __init__ wrap fix
        // (_OutMultiEdgesKeysView) for the edges() route.
        if !self.succ_py_keys.is_empty() {
            return Ok(None);
        }
        let mut out: Vec<PyObject> = Vec::new();
        let mut seen_nodes: std::collections::HashSet<String> = std::collections::HashSet::new();
        for item in nbunch.try_iter()? {
            let node = item?;
            if node.hash().is_err() {
                let label = node
                    .str()
                    .map(|s| s.to_string_lossy().into_owned())
                    .unwrap_or_else(|_| "?".to_owned());
                return Err(pyo3::exceptions::PyTypeError::new_err(format!(
                    "Node {label} in sequence nbunch is not a valid node."
                )));
            }
            let canonical = node_key_to_string(py, &node)?;
            let Some(successors) = self.inner.successors(&canonical) else {
                continue;
            };
            if !seen_nodes.insert(canonical.clone()) {
                continue;
            }
            for nbr in successors {
                for key in self.inner.edge_keys(&canonical, nbr).unwrap_or_default() {
                    let nbr_obj = self.py_node_key(py, nbr);
                    if keys {
                        let key_obj = self.py_edge_key(py, &canonical, nbr, key);
                        out.push(tuple_object(
                            py,
                            &[node.clone().unbind(), nbr_obj, key_obj],
                        )?);
                    } else {
                        out.push(tuple_object(py, &[node.clone().unbind(), nbr_obj])?);
                    }
                }
            }
        }
        Ok(Some(out))
    }

    /// br-r37-c1-mdgoutedge (cc): MultiDiGraph out_edges(nbunch, data=True). Emits
    /// (u, v[, key], live_attr_dict). successors/edge_keys collected as owned so the
    /// &mut ensure_edge_py_attrs (identity-preserving live dict) has no live inner
    /// borrow. node-deduped, succ_py_keys/edge_py_keys display gate.
    fn _native_mdg_out_edges_nbunch_data(
        &mut self,
        py: Python<'_>,
        nbunch: &Bound<'_, PyAny>,
        keys: bool,
    ) -> PyResult<Option<Vec<PyObject>>> {
        if !self.succ_py_keys.is_empty() || (keys && !self.edge_py_keys.is_empty()) {
            return Ok(None);
        }
        let mut out: Vec<PyObject> = Vec::new();
        let mut seen_nodes: std::collections::HashSet<String> = std::collections::HashSet::new();
        for item in nbunch.try_iter()? {
            let node = item?;
            if node.hash().is_err() {
                let label = node
                    .str()
                    .map(|s| s.to_string_lossy().into_owned())
                    .unwrap_or_else(|_| "?".to_owned());
                return Err(pyo3::exceptions::PyTypeError::new_err(format!(
                    "Node {label} in sequence nbunch is not a valid node."
                )));
            }
            let canonical = node_key_to_string(py, &node)?;
            let successors: Vec<String> = match self.inner.successors(&canonical) {
                Some(v) => v.iter().map(|s| (*s).to_owned()).collect(),
                None => continue,
            };
            if !seen_nodes.insert(canonical.clone()) {
                continue;
            }
            for nbr in &successors {
                let keys_vec: Vec<usize> =
                    self.inner.edge_keys(&canonical, nbr).unwrap_or_default();
                for key in keys_vec {
                    let nbr_obj = self.py_node_key(py, nbr);
                    let attrs = self
                        .ensure_edge_py_attrs(py, &canonical, nbr, key)
                        .clone_ref(py)
                        .into_any();
                    if keys {
                        let key_obj = crate::unwrap_infallible(key.into_pyobject(py))
                            .into_any()
                            .unbind();
                        out.push(tuple_object(
                            py,
                            &[node.clone().unbind(), nbr_obj, key_obj, attrs],
                        )?);
                    } else {
                        out.push(tuple_object(py, &[node.clone().unbind(), nbr_obj, attrs])?);
                    }
                }
            }
        }
        Ok(Some(out))
    }

    /// br-r37-c1-mdginedges (cc): full-graph in_edges(data=True) for MultiDiGraph.
    /// The Python wrapper looped `self.pred[target].items()` per node (building a
    /// pred AtlasView + nested keydicts in Python) -> ~11x slower than nx. One
    /// native target-major pass (nodes_ordered -> predecessors -> edge_keys) over
    /// the live attr dicts is byte-identical to that loop (same adjacency order)
    /// but ~30x faster. Bails to the Python path when pred custom-key mirrors are
    /// active (z6uka), exactly like the out_edges nbunch natives.
    fn _native_mdg_in_edges_with_data(&mut self, py: Python<'_>) -> PyResult<Option<Vec<PyObject>>> {
        if !self.pred_py_keys.is_empty() {
            return Ok(None);
        }
        if self.inner.edge_count() > 0 {
            self.mark_edges_dirty();
        }
        // (nodes_seq, edges_seq)-keyed cache like _native_edges_with_data: on a
        // seq match return a fresh list of the same tuple objects (live attr
        // dicts; node/edge mutation bumps a seq and invalidates).
        let valid = matches!(
            &self.in_edges_with_data_cache,
            Some((ns, es, _)) if *ns == self.nodes_seq && *es == self.edges_seq
        );
        if !valid {
            let triples: Vec<(String, String, usize)> = {
                let mut v = Vec::with_capacity(self.inner.edge_count());
                for target in self.inner.nodes_ordered() {
                    if let Some(preds) = self.inner.predecessors(target) {
                        for source in preds {
                            for key in self.inner.edge_keys(source, target).unwrap_or_default() {
                                v.push((source.to_owned(), target.to_owned(), key));
                            }
                        }
                    }
                }
                v
            };
            let mut out: Vec<PyObject> = Vec::with_capacity(triples.len());
            for (source, target, key) in triples {
                let src_obj = self.py_node_key(py, &source);
                let tgt_obj = self.py_node_key(py, &target);
                let attrs = self
                    .ensure_edge_py_attrs(py, &source, &target, key)
                    .clone_ref(py)
                    .into_any();
                out.push(tuple_object(py, &[src_obj, tgt_obj, attrs])?);
            }
            self.in_edges_with_data_cache = Some((self.nodes_seq, self.edges_seq, out));
        }
        let cached = &self.in_edges_with_data_cache.as_ref().unwrap().2;
        let fresh: Vec<PyObject> = cached.iter().map(|t| t.clone_ref(py)).collect();
        Ok(Some(fresh))
    }

    /// br-r37-c1-04z53 cod-b: attr-key sibling of
    /// `_native_mdg_out_edges_nbunch_data`. The prior route first materialized
    /// every live attr dict via data=True and then projected one scalar.
    fn _native_mdg_out_edges_nbunch_data_key(
        &mut self,
        py: Python<'_>,
        nbunch: &Bound<'_, PyAny>,
        data: &Bound<'_, PyAny>,
        default: PyObject,
    ) -> PyResult<Option<Vec<PyObject>>> {
        if !self.succ_py_keys.is_empty() {
            return Ok(None);
        }
        let mut out: Vec<PyObject> = Vec::new();
        let mut seen_nodes: std::collections::HashSet<String> = std::collections::HashSet::new();
        for item in nbunch.try_iter()? {
            let node = item?;
            if node.hash().is_err() {
                let label = node
                    .str()
                    .map(|s| s.to_string_lossy().into_owned())
                    .unwrap_or_else(|_| "?".to_owned());
                return Err(pyo3::exceptions::PyTypeError::new_err(format!(
                    "Node {label} in sequence nbunch is not a valid node."
                )));
            }
            let canonical = node_key_to_string(py, &node)?;
            let successors: Vec<String> = match self.inner.successors(&canonical) {
                Some(v) => v.iter().map(|s| (*s).to_owned()).collect(),
                None => continue,
            };
            if !seen_nodes.insert(canonical.clone()) {
                continue;
            }
            for nbr in &successors {
                let keys_vec: Vec<usize> =
                    self.inner.edge_keys(&canonical, nbr).unwrap_or_default();
                for key in keys_vec {
                    let nbr_obj = self.py_node_key(py, nbr);
                    let value =
                        self.edge_data_value_or_default(py, &canonical, nbr, key, data, &default)?;
                    out.push(tuple_object(py, &[node.clone().unbind(), nbr_obj, value])?);
                }
            }
        }
        Ok(Some(out))
    }

    /// br-r37-c1-selfloopmulti (cc): self-loop nodes in node order via a rust scan
    /// (replaces selfloop_edges' O(N) per-node has_edge(n,n) PyO3 probe).
    fn _native_selfloop_nodes(&self, py: Python<'_>) -> Vec<PyObject> {
        self.inner
            .nodes_ordered()
            .iter()
            .filter(|n| self.inner.has_edge(n, n))
            .map(|n| self.py_node_key(py, n))
            .collect()
    }

    /// br-r37-c1-8egkh: full native MultiDiGraph self-loop edge emission.
    /// This is the directed sibling of PyMultiGraph::_native_selfloop_edges:
    /// skip Python `G[n]`/`nbrs[n]` row materialization and emit the final
    /// NetworkX-shaped tuples directly while preserving display keys and live
    /// attr-dict identity.
    #[pyo3(signature = (data, keys=false, default=None))]
    fn _native_selfloop_edges(
        &mut self,
        py: Python<'_>,
        data: &Bound<'_, PyAny>,
        keys: bool,
        default: Option<PyObject>,
    ) -> PyResult<Py<crate::NodeIterator>> {
        let data_is_bool = data.is_instance_of::<PyBool>();
        let want_dict = data_is_bool && data.extract::<bool>()?;
        let want_value = !data_is_bool;
        let default_obj = default.unwrap_or_else(|| py.None());
        if want_dict && self.inner.edge_count() > 0 {
            self.mark_edges_dirty();
        }

        let nodes: Vec<String> = self
            .inner
            .nodes_ordered()
            .iter()
            .filter(|node| self.inner.has_edge(node, node))
            .map(|node| (*node).to_owned())
            .collect();
        let mut out: Vec<PyObject> = Vec::with_capacity(self.inner.number_of_selfloops());
        for node in &nodes {
            let edge_keys = self.inner.edge_keys(node, node).unwrap_or_default();
            let py_node = self.py_node_key(py, node);
            for key in edge_keys {
                let py_source = py_node.clone_ref(py);
                let py_target = py_node.clone_ref(py);
                let key_obj = if keys {
                    Some(if self.edge_py_keys.is_empty() {
                        unwrap_infallible(key.into_pyobject(py)).into_any().unbind()
                    } else {
                        self.py_edge_key(py, node, node, key)
                    })
                } else {
                    None
                };
                if want_dict {
                    let attrs = self
                        .ensure_edge_py_attrs(py, node, node, key)
                        .clone_ref(py)
                        .into_any();
                    if let Some(key_obj) = key_obj {
                        out.push(tuple_object(py, &[py_source, py_target, key_obj, attrs])?);
                    } else {
                        out.push(tuple_object(py, &[py_source, py_target, attrs])?);
                    }
                } else if want_value {
                    let val =
                        self.edge_data_value_or_default(py, node, node, key, data, &default_obj)?;
                    if let Some(key_obj) = key_obj {
                        out.push(tuple_object(py, &[py_source, py_target, key_obj, val])?);
                    } else {
                        out.push(tuple_object(py, &[py_source, py_target, val])?);
                    }
                } else if let Some(key_obj) = key_obj {
                    out.push(tuple_object(py, &[py_source, py_target, key_obj])?);
                } else {
                    out.push(tuple_object(py, &[py_source, py_target])?);
                }
            }
        }
        Py::new(py, crate::NodeIterator::unguarded(out))
    }

    /// br-r37-c1-degnbnative (cc): MultiDiGraph degree(nbunch) subset kernels — one
    /// native pass (canonical filter + multiplicity in/out/total degree) replacing
    /// the per-node native-degree + nbunch_iter membership Python path. Routed via
    /// the existing _DirectedDegreeView.__call__ (succ->out / pred->in).
    fn _native_out_degree_pairs_subset(
        &self,
        py: Python<'_>,
        nbunch: &Bound<'_, PyAny>,
    ) -> PyResult<Vec<(PyObject, usize)>> {
        self.degree_pairs_subset_impl(py, nbunch, DegreeKind::Out)
    }

    fn _native_in_degree_pairs_subset(
        &self,
        py: Python<'_>,
        nbunch: &Bound<'_, PyAny>,
    ) -> PyResult<Vec<(PyObject, usize)>> {
        self.degree_pairs_subset_impl(py, nbunch, DegreeKind::In)
    }

    #[getter]
    fn adj(&self, py: Python<'_>) -> PyResult<Py<PyDict>> {
        self.adjacency(py)
    }

    fn adjacency(&self, py: Python<'_>) -> PyResult<Py<PyDict>> {
        if self.inner.edge_count() > 0 {
            self.mark_edges_dirty();
        }
        let result = PyDict::new(py);
        for node in self.inner.nodes_ordered() {
            let py_node = self.py_node_key(py, node);
            let nbrs_dict = PyDict::new(py);
            for successor in self.inner.successors(node).unwrap_or_default() {
                let py_succ = self.py_succ_key(py, node, successor) /* br-r37-c1-z6uka */;
                let edge_dict = PyDict::new(py);
                for key in self.inner.edge_keys(node, successor).unwrap_or_default() {
                    let ek = Self::edge_key(node, successor, key);
                    let attrs = self
                        .edge_py_attrs
                        .get(&ek)
                        .map_or_else(|| PyDict::new(py).unbind(), |d| d.clone_ref(py));
                    edge_dict
                        .set_item(self.py_edge_key(py, node, successor, key), attrs.bind(py))?;
                }
                nbrs_dict.set_item(&py_succ, edge_dict)?;
            }
            result.set_item(py_node, nbrs_dict)?;
        }
        Ok(result.unbind())
    }

    /// br-r37-c1-mdadj: non-shadowed accessor for the native nested adjacency
    /// snapshot ({node: {nbr: {key: attrs}}}). The Python MultiDiGraph.adjacency
    /// (_multigraph_adjacency) walks self.adj[node] via the MultiAdjacencyView
    /// lambda chain per element (~33000x slower than nx); routing it here builds
    /// the identical snapshot natively from inner adjacency.
    fn _native_adjacency_dict(&mut self, py: Python<'_>) -> PyResult<Py<PyDict>> {
        self.adjacency_dict_cached(py)
    }

    /// br-r37-c1-adjshare: cached form of `adjacency` — serve the nested
    /// {node: {succ: {key: edge_dict}}} snapshot from the (nodes_seq, edges_seq)-
    /// keyed `dict_of_dicts_cache` with SHARED rows (no per-row copy). nx's
    /// adjacency() hands out live rows (`r1[u] is r2[u]`); sharing matches that
    /// AND drops the O(V+E) per-call copy (was ~7x slower than nx). Deepest edge
    /// dicts stay live; only adjacency() uses this, so sharing is safe.
    pub(crate) fn adjacency_dict_cached(&mut self, py: Python<'_>) -> PyResult<Py<PyDict>> {
        if self.inner.edge_count() > 0 {
            self.mark_edges_dirty();
        }
        let matches = self
            .dict_of_dicts_cache
            .as_ref()
            .is_some_and(|c| c.nodes_seq == self.nodes_seq && c.edges_seq == self.edges_seq);
        if !matches {
            self.rebuild_adjacency_cache(py)?;
        }
        let cache = self
            .dict_of_dicts_cache
            .as_ref()
            .ok_or_else(|| PyRuntimeError::new_err("dict_of_dicts cache missing after rebuild"))?;
        crate::readwrite::share_dict_of_dicts_cache(py, cache)
    }

    fn rebuild_adjacency_cache(&mut self, py: Python<'_>) -> PyResult<()> {
        let nodes: Vec<String> = self
            .inner
            .nodes_ordered()
            .into_iter()
            .map(str::to_owned)
            .collect();
        let mut rows = Vec::with_capacity(nodes.len());
        for node in &nodes {
            let py_node = self.py_node_key(py, node);
            let nbrs_dict = PyDict::new(py);
            let successors: Vec<String> = self
                .inner
                .successors(node)
                .unwrap_or_default()
                .into_iter()
                .map(str::to_owned)
                .collect();
            for successor in &successors {
                let py_succ = self.py_succ_key(py, node, successor);
                let edge_dict = PyDict::new(py);
                let keys: Vec<usize> = self.inner.edge_keys(node, successor).unwrap_or_default();
                for key in keys {
                    let ek = Self::edge_key(node, successor, key);
                    let attrs = self
                        .edge_py_attrs
                        .get(&ek)
                        .map_or_else(|| PyDict::new(py).unbind(), |d| d.clone_ref(py));
                    edge_dict
                        .set_item(self.py_edge_key(py, node, successor, key), attrs.bind(py))?;
                }
                nbrs_dict.set_item(&py_succ, edge_dict)?;
            }
            rows.push((py_node, nbrs_dict.unbind()));
        }
        self.dict_of_dicts_cache = Some(crate::DictOfDictsCache {
            nodes_seq: self.nodes_seq,
            edges_seq: self.edges_seq,
            rows,
        });
        Ok(())
    }

    /// br-r37-c1-wdeg: native total weighted degree (in + out), returning the
    /// full ``(node, total)`` sequence in node order. The Python
    /// MultiDiGraphDegreeView weighted path calls module-level
    /// ``degree(G, node, weight)`` per node, which walks ``G.succ[node]`` and
    /// ``G.pred[node]`` via the MultiAdjacencyView lambda chain plus
    /// ``keydict.values()`` (~6000x slower than nx).
    ///
    /// nx's ``DiMultiDegreeView`` computes ``deg = sum(<flat over succ>) +
    /// sum(<flat over pred>)`` — TWO separate ``sum()`` accumulations (each a
    /// fresh running total) added together, NOT one continuous fold. To stay
    /// bit-identical (CPython ``sum`` is Neumaier-compensated for floats and
    /// the association matters), we build the succ/pred value lists in nx's
    /// exact order and call the SAME builtin ``sum`` for each.
    fn _native_weighted_degree(
        &self,
        py: Python<'_>,
        weight: &str,
    ) -> PyResult<Vec<(PyObject, PyObject)>> {
        let one = 1i64.into_pyobject(py)?.into_any();
        let sum_fn = py.import("builtins")?.getattr("sum")?;
        let mut out: Vec<(PyObject, PyObject)> = Vec::with_capacity(self.inner.node_count());
        for node in self.inner.nodes_ordered() {
            let succ_vals = pyo3::types::PyList::empty(py);
            for successor in self.inner.successors(node).unwrap_or_default() {
                for key in self.inner.edge_keys(node, successor).unwrap_or_default() {
                    let ek = Self::edge_key(node, successor, key);
                    let value = match self.edge_py_attrs.get(&ek) {
                        Some(d) => d
                            .bind(py)
                            .get_item(weight)
                            .ok()
                            .flatten()
                            .unwrap_or_else(|| one.clone()),
                        None => one.clone(),
                    };
                    succ_vals.append(value)?;
                }
            }
            let pred_vals = pyo3::types::PyList::empty(py);
            for predecessor in self.inner.predecessors(node).unwrap_or_default() {
                for key in self.inner.edge_keys(predecessor, node).unwrap_or_default() {
                    let ek = Self::edge_key(predecessor, node, key);
                    let value = match self.edge_py_attrs.get(&ek) {
                        Some(d) => d
                            .bind(py)
                            .get_item(weight)
                            .ok()
                            .flatten()
                            .unwrap_or_else(|| one.clone()),
                        None => one.clone(),
                    };
                    pred_vals.append(value)?;
                }
            }
            let deg = sum_fn
                .call1((succ_vals,))?
                .add(sum_fn.call1((pred_vals,))?)?;
            out.push((self.py_node_key(py, node), deg.unbind()));
        }
        Ok(out)
    }

    fn native_weighted_directional_degree(
        &self,
        py: Python<'_>,
        weight: &str,
        outgoing: bool,
    ) -> PyResult<Vec<(PyObject, PyObject)>> {
        let one = 1i64.into_pyobject(py)?.into_any();
        let sum_fn = py.import("builtins")?.getattr("sum")?;
        let mut out: Vec<(PyObject, PyObject)> = Vec::with_capacity(self.inner.node_count());
        for node in self.inner.nodes_ordered() {
            let vals = pyo3::types::PyList::empty(py);
            if outgoing {
                for successor in self.inner.successors(node).unwrap_or_default() {
                    for key in self.inner.edge_keys(node, successor).unwrap_or_default() {
                        let ek = Self::edge_key(node, successor, key);
                        let value = match self.edge_py_attrs.get(&ek) {
                            Some(d) => d
                                .bind(py)
                                .get_item(weight)
                                .ok()
                                .flatten()
                                .unwrap_or_else(|| one.clone()),
                            None => one.clone(),
                        };
                        vals.append(value)?;
                    }
                }
            } else {
                for predecessor in self.inner.predecessors(node).unwrap_or_default() {
                    for key in self.inner.edge_keys(predecessor, node).unwrap_or_default() {
                        let ek = Self::edge_key(predecessor, node, key);
                        let value = match self.edge_py_attrs.get(&ek) {
                            Some(d) => d
                                .bind(py)
                                .get_item(weight)
                                .ok()
                                .flatten()
                                .unwrap_or_else(|| one.clone()),
                            None => one.clone(),
                        };
                        vals.append(value)?;
                    }
                }
            }
            let deg = sum_fn.call1((vals,))?;
            out.push((self.py_node_key(py, node), deg.unbind()));
        }
        Ok(out)
    }

    fn _native_weighted_out_degree(
        &self,
        py: Python<'_>,
        weight: &str,
    ) -> PyResult<Vec<(PyObject, PyObject)>> {
        self.native_weighted_directional_degree(py, weight, true)
    }

    fn _native_weighted_in_degree(
        &self,
        py: Python<'_>,
        weight: &str,
    ) -> PyResult<Vec<(PyObject, PyObject)>> {
        self.native_weighted_directional_degree(py, weight, false)
    }

    #[getter]
    fn succ(&self, py: Python<'_>) -> PyResult<Py<PyDict>> {
        self.adjacency(py)
    }

    #[getter]
    fn pred(&self, py: Python<'_>) -> PyResult<Py<PyDict>> {
        if self.inner.edge_count() > 0 {
            self.mark_edges_dirty();
        }
        let result = PyDict::new(py);
        for node in self.inner.nodes_ordered() {
            let py_node = self.py_node_key(py, node);
            let preds_dict = PyDict::new(py);
            for predecessor in self.inner.predecessors(node).unwrap_or_default() {
                let py_pred = self.py_pred_key(py, node, predecessor) /* br-r37-c1-z6uka */;
                let edge_dict = PyDict::new(py);
                for key in self.inner.edge_keys(predecessor, node).unwrap_or_default() {
                    let ek = Self::edge_key(predecessor, node, key);
                    let attrs = self
                        .edge_py_attrs
                        .get(&ek)
                        .map_or_else(|| PyDict::new(py).unbind(), |d| d.clone_ref(py));
                    edge_dict
                        .set_item(self.py_edge_key(py, predecessor, node, key), attrs.bind(py))?;
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

    /// br-r37-c1-8uh84: native insertion-order-preserving copy (see
    /// PyMultiGraph::_native_copy). Iterates `nodes_ordered()` for node order
    /// (the internal `copy()` scrambles it via `node_key_map` HashMap) and
    /// `edges_ordered()` for edge order + orientation. Shallow attr copies.
    fn _native_copy(&self, py: Python<'_>) -> PyResult<Self> {
        // br-r37-c1-mdgcopyclone: CLONE the inner wholesale + clone the Python
        // mirrors, instead of rebuilding edge-by-edge via add_edge_with_key_and_attrs
        // (15000 String-keyed succ+pred IndexMap inserts on a dense graph -> 0.61x vs
        // nx). The old rebuild walked edges_ordered() (edge INSERTION order) then
        // reordered PRED; an inner clone is ALREADY in that order (succ is never
        // reordered — reorder_pred only touches pred rows), so clone + reorder_pred is
        // field-identical to the rebuild, just bulk. Fields match the rebuild exactly:
        // pred_py_keys re-derived (empty), graph_attrs a FRESH dict (G.copy semantics),
        // edge_dirty_keys clean. (We also drop the rebuild's eager empty edge attr
        // PyDicts — lazy materialize is identity-preserving, br-r37-c1-aab122464.)
        let mut new_graph = Self {
            inner: self.inner.clone_with_fresh_policy(),
            node_key_map: self
                .node_key_map
                .iter()
                .map(|(k, v)| (k.clone(), v.clone_ref(py)))
                .collect(),
            // br-r37-c1-z6uka: succ overrides survive nx's u-major copy walk;
            // pred rows are re-derived with node objects.
            succ_py_keys: PyDiGraph::clone_row_keys(py, &self.succ_py_keys),
            pred_py_keys: HashMap::new(),
            node_py_attrs: self
                .node_py_attrs
                .iter()
                .map(|(k, v)| Ok((k.clone(), v.bind(py).copy()?.unbind())))
                .collect::<PyResult<_>>()?,
            edge_py_attrs: self
                .edge_py_attrs
                .iter()
                .map(|(k, v)| Ok((k.clone(), v.bind(py).copy()?.unbind())))
                .collect::<PyResult<_>>()?,
            edge_py_keys: self
                .edge_py_keys
                .iter()
                .map(|(k, v)| (k.clone(), v.clone_ref(py)))
                .collect(),
            graph_attrs: self.graph_attrs.bind(py).copy()?.unbind(),
            nodes_seq: 0,
            edges_seq: 0,
            edges_dirty: AtomicBool::new(false),
            edge_dirty_keys: Self::clean_edge_dirty_keys(),
            node_keys_cache: std::sync::Mutex::new(None),
            node_data_mirror: std::sync::Mutex::new(None),
            dict_of_dicts_cache: None,
            edges_with_data_cache: None,
            in_edges_with_data_cache: None,
            edges_with_keys_cache: None,
            node_iter_mirror: std::sync::Mutex::new(None),
        };
        // br-r37-c1-s0d4x: pred rows in nx's u-major copy-walk order (the inner
        // clone above is in edge INSERTION order).
        new_graph.inner.reorder_pred_rows_for_nx_copy_walk();
        Ok(new_graph)
    }

    fn _native_to_directed_deepcopy(&self, py: Python<'_>) -> PyResult<Self> {
        let deepcopy = py.import("copy")?.getattr("deepcopy")?;
        let mut new_graph = Self {
            inner: MultiDiGraph::with_runtime_policy(self.inner.runtime_policy().clone()),
            node_key_map: HashMap::new(),
            succ_py_keys: HashMap::new(), // br-r37-c1-z6uka
            pred_py_keys: HashMap::new(), // br-r37-c1-z6uka
            node_py_attrs: HashMap::new(),
            edge_py_attrs: HashMap::new(),
            edge_py_keys: HashMap::new(),
            graph_attrs: crate::deepcopy_py_dict(py, &deepcopy, &self.graph_attrs)?,
            nodes_seq: 0,
            edges_seq: 0,
            edges_dirty: AtomicBool::new(false),
            edge_dirty_keys: Self::clean_edge_dirty_keys(),
            node_keys_cache: std::sync::Mutex::new(None),
            node_data_mirror: std::sync::Mutex::new(None),
            dict_of_dicts_cache: None,
            edges_with_data_cache: None,
            in_edges_with_data_cache: None,
            edges_with_keys_cache: None,
            node_iter_mirror: std::sync::Mutex::new(None),
        };
        for node in self.inner.nodes_ordered() {
            let py_attrs = self.node_py_attrs.get(node).map_or_else(
                || Ok(PyDict::new(py).unbind()),
                |attrs| crate::deepcopy_py_dict(py, &deepcopy, attrs),
            )?;
            let rust_attrs = py_dict_to_attr_map(py_attrs.bind(py))?;
            new_graph
                .inner
                .add_node_with_attrs(node.to_owned(), rust_attrs);
            new_graph
                .node_key_map
                .insert(node.to_owned(), self.py_node_key(py, node));
            new_graph.node_py_attrs.insert(node.to_owned(), py_attrs);
        }
        for source in self.inner.nodes_ordered() {
            for target in self.inner.successors(source).unwrap_or_default() {
                for key in self.inner.edge_keys(source, target).unwrap_or_default() {
                    let attrs_entry = self.edge_py_attrs.get(&Self::edge_key(source, target, key));
                    let py_attrs = attrs_entry.map_or_else(
                        || Ok(PyDict::new(py).unbind()),
                        |attrs| crate::deepcopy_py_dict(py, &deepcopy, attrs),
                    )?;
                    let rust_attrs = py_dict_to_attr_map(py_attrs.bind(py))?;
                    let new_key = new_graph
                        .inner
                        .add_edge_with_attrs(source.to_owned(), target.to_owned(), rust_attrs)
                        .map_err(|e| NetworkXError::new_err(e.to_string()))?;
                    new_graph
                        .edge_py_attrs
                        .insert((source.to_owned(), target.to_owned(), new_key), py_attrs);
                    let py_key = self.py_edge_key(py, source, target, key);
                    new_graph.remember_edge_key_object(py, source, target, new_key, &py_key);
                }
            }
        }
        Ok(new_graph)
    }

    fn _native_to_undirected_deepcopy(&self, py: Python<'_>) -> PyResult<crate::PyMultiGraph> {
        let deepcopy = py.import("copy")?.getattr("deepcopy")?;
        // br-r37-c1-l5ve7: fresh ledger + lazy attr mirrors (see the
        // PyMultiGraph::_native_to_directed_deepcopy sibling).
        let mut ug = crate::PyMultiGraph {
            inner: fnx_classes::MultiGraph::with_runtime_policy(fnx_runtime::RuntimePolicy::new(
                self.inner.mode(),
            )),
            node_key_map: HashMap::new(),
            adj_py_keys: HashMap::new(), // br-r37-c1-z6uka
            node_py_attrs: HashMap::new(),
            edge_py_attrs: HashMap::new(),
            edge_py_keys: HashMap::new(),
            graph_attrs: crate::deepcopy_py_dict(py, &deepcopy, &self.graph_attrs)?,
            nodes_seq: 0,
            edges_seq: 0,
            edges_dirty: AtomicBool::new(false),
            node_keys_cache: std::sync::Mutex::new(None),
            node_data_mirror: std::sync::Mutex::new(None),
            dict_of_dicts_cache: None,
            edges_with_data_cache: None,
            edges_with_keys_cache: None,
            node_iter_mirror: std::sync::Mutex::new(None),
        };
        let mut node_batch: Vec<(String, fnx_classes::AttrMap)> =
            Vec::with_capacity(self.inner.node_count());
        for node in self.inner.nodes_ordered() {
            let rust_attrs = if let Some(attrs) = self.node_py_attrs.get(node) {
                let py_attrs = crate::deepcopy_py_dict(py, &deepcopy, attrs)?;
                let rust_attrs = py_dict_to_attr_map(py_attrs.bind(py))?;
                ug.node_py_attrs.insert(node.to_owned(), py_attrs);
                rust_attrs
            } else {
                Default::default()
            };
            ug.node_key_map
                .insert(node.to_owned(), self.py_node_key(py, node));
            node_batch.push((node.to_owned(), rust_attrs));
        }
        ug.inner.extend_nodes_with_attrs_unrecorded(node_batch);
        // br-r37-c1-l5ve7 lever 10: RESOLVE-AWARE bulk — the reciprocal
        // merge resolves arcs by their key's canonical lookup STRING
        // (resolve_internal_edge_key compares edge_key_lookup_string).
        // A local shadow map replicates that resolution against the
        // accumulating result (the old per-edge path queried the result
        // graph and paid two ledger records per arc); the miss path
        // replicates the kernel's len-then-probe auto-key allocation.
        let mut pair_keys: std::collections::HashMap<
            (String, String),
            (
                std::collections::HashMap<String, usize>,
                std::collections::HashSet<usize>,
            ),
        > = std::collections::HashMap::new();
        let mut edge_batch: Vec<(String, String, usize, fnx_classes::AttrMap)> = Vec::new();
        for source in self.inner.nodes_ordered() {
            for target in self.inner.successors(source).unwrap_or_default() {
                for key in self.inner.edge_keys(source, target).unwrap_or_default() {
                    let attrs_entry = self.edge_py_attrs.get(&Self::edge_key(source, target, key));
                    let rust_attrs;
                    let mirror = match attrs_entry {
                        Some(attrs) => {
                            let py_attrs = crate::deepcopy_py_dict(py, &deepcopy, attrs)?;
                            rust_attrs = py_dict_to_attr_map(py_attrs.bind(py))?;
                            Some(py_attrs)
                        }
                        None => {
                            rust_attrs = Default::default();
                            None
                        }
                    };
                    let py_key = self.py_edge_key(py, source, target, key);
                    let lookup = crate::edge_key_lookup_string(py, py_key.bind(py).as_any())?;
                    let pair = if *source <= *target {
                        (source.to_owned(), target.to_owned())
                    } else {
                        (target.to_owned(), source.to_owned())
                    };
                    let entry = pair_keys.entry(pair).or_default();
                    let actual_key = match entry.0.get(&lookup) {
                        Some(&existing) => existing,
                        None => {
                            // kernel auto-key: start at bucket len, probe up
                            let mut k = entry.1.len();
                            while entry.1.contains(&k) {
                                k += 1;
                            }
                            entry.0.insert(lookup, k);
                            entry.1.insert(k);
                            k
                        }
                    };
                    // lazy mirror: only materialize/merge when the source
                    // arc actually carries attrs (an empty dict's update
                    // is a no-op; absent entries are tolerated).
                    if let Some(py_attrs) = mirror {
                        let edge_key = crate::PyMultiGraph::edge_key(source, target, actual_key);
                        let edge_key_rev =
                            crate::PyMultiGraph::edge_key(target, source, actual_key);
                        if let Some(existing_attrs) = ug
                            .edge_py_attrs
                            .get(&edge_key)
                            .or_else(|| ug.edge_py_attrs.get(&edge_key_rev))
                        {
                            existing_attrs
                                .bind(py)
                                .update(py_attrs.bind(py).as_mapping())?;
                        } else {
                            ug.edge_py_attrs.insert(edge_key, py_attrs);
                        }
                    }
                    ug.remember_edge_key_object(py, source, target, actual_key, &py_key);
                    edge_batch.push((source.to_owned(), target.to_owned(), actual_key, rust_attrs));
                }
            }
        }
        ug.inner
            .extend_keyed_edges_with_attrs_unrecorded(edge_batch);
        Ok(ug)
    }

    /// br-r37-c1-s0d4x: wholesale same-type constructor absorb — nx's
    /// ``cls(G)`` structure is identical to ``G.copy()`` (probed: nodes,
    /// edges+data, adjacency/pred rows, graph attrs, shallow attr-dict
    /// copying, all four classes). The Python ctor wrapper routes the
    /// exact-same-type case here instead of the per-edge rebuild walk.
    fn _fnx_absorb_copy(&mut self, py: Python<'_>, other: PyRef<'_, Self>) -> PyResult<()> {
        *self = other.copy(py)?;
        Ok(())
    }

    /// br-r37-c1-k1k74: exact `MultiDiGraph(Graph)` copy-constructor absorb.
    fn _fnx_absorb_graph_bidirected(
        &mut self,
        py: Python<'_>,
        source: PyRef<'_, PyGraph>,
    ) -> PyResult<bool> {
        self.absorb_graph_bidirected_from_graph(py, source)
    }

    /// br-r37-c1-mdgdig: exact `MultiDiGraph(DiGraph)` copy-constructor absorb.
    fn _fnx_absorb_digraph_keyed(
        &mut self,
        py: Python<'_>,
        source: PyRef<'_, PyDiGraph>,
    ) -> PyResult<bool> {
        self.absorb_digraph_keyed_from_digraph(py, source)
    }

    /// br-r37-c1-mdgdju (cc): native MultiDiGraph disjoint_union — keyed analog of
    /// PyDiGraph::_native_disjoint_union. Relabels both parts to fresh int ranges
    /// (so the source NODE display + succ/pred row overrides are discarded — the
    /// result nodes are plain ints), walks SUCCESSORS x edge_keys (no symmetric
    /// dedup; directed), and PRESERVES each edge's DISPLAY key by copying the
    /// edge_py_keys mirror (nx preserves keys; the inner integer key may differ
    /// from the Python display key for explicit/non-default keys). Bulk
    /// extend_keyed_edges_with_attrs_unrecorded. No gating needed.
    fn _native_disjoint_union(&self, py: Python<'_>, other: PyRef<'_, Self>) -> PyResult<Py<Self>> {
        let mut g = Self::new_empty_with_mode(py, self.inner.mode())?;
        let merged_graph_attrs = PyDict::new(py);
        merged_graph_attrs.update(self.graph_attrs.bind(py).as_mapping())?;
        merged_graph_attrs.update(other.graph_attrs.bind(py).as_mapping())?;
        g.graph_attrs = merged_graph_attrs.unbind();
        let n1 = self.inner.node_count();
        for (part, offset) in [(self, 0usize), (&*other, n1)] {
            let nodes: Vec<String> = part
                .inner
                .nodes_ordered()
                .into_iter()
                .map(str::to_owned)
                .collect();
            let index_of: HashMap<&str, usize> = nodes
                .iter()
                .enumerate()
                .map(|(i, n)| (n.as_str(), i + offset))
                .collect();
            let mut node_batch: Vec<(String, AttrMap)> = Vec::with_capacity(nodes.len());
            for (i, node) in nodes.iter().enumerate() {
                let canonical = (i + offset).to_string();
                if let Some(attrs) = part.node_py_attrs.get(node) {
                    g.node_py_attrs
                        .insert(canonical.clone(), attrs.bind(py).copy()?.unbind());
                }
                g.node_key_map.insert(
                    canonical.clone(),
                    crate::unwrap_infallible((i + offset).into_pyobject(py))
                        .into_any()
                        .unbind(),
                );
                node_batch.push((
                    canonical,
                    part.inner.node_attrs(node).cloned().unwrap_or_default(),
                ));
            }
            let _ = g.inner.extend_nodes_with_attrs_unrecorded(node_batch);
            let mut edge_batch: Vec<(String, String, usize, AttrMap)> = Vec::new();
            for u in &nodes {
                for v in part.inner.successors(u).unwrap_or_default() {
                    let uc = index_of[u.as_str()].to_string();
                    let vc = index_of[v].to_string();
                    for key in part.inner.edge_keys(u, v).unwrap_or_default() {
                        let src_ek = Self::edge_key(u, v, key);
                        let dst_ek = Self::edge_key(&uc, &vc, key);
                        if let Some(attrs) = part.edge_py_attrs.get(&src_ek) {
                            g.edge_py_attrs
                                .insert(dst_ek.clone(), attrs.bind(py).copy()?.unbind());
                        }
                        if let Some(display_key) = part.edge_py_keys.get(&src_ek) {
                            g.edge_py_keys.insert(dst_ek, display_key.clone_ref(py));
                        }
                        edge_batch.push((
                            uc.clone(),
                            vc.clone(),
                            key,
                            part.inner
                                .edge_attrs(u, v, key)
                                .cloned()
                                .unwrap_or_default(),
                        ));
                    }
                }
            }
            g.inner.extend_keyed_edges_with_attrs_unrecorded(edge_batch);
        }
        Py::new(py, g)
    }

    fn copy(&self, py: Python<'_>) -> PyResult<Self> {
        // br-r37-c1-6xe9c: bulk-clone the inner Rust multidigraph instead of
        // rebuilding it edge-by-edge. The previous loop iterated
        // `self.node_key_map` (a randomized-order HashMap) to re-add nodes, so
        // `list(G.copy())` came out in hash order — non-deterministic and
        // diverging from `list(G)` / networkx (project_copy_node_order). It also
        // re-added each edge via `add_edge_with_key_and_attrs` plus a redundant
        // `py_dict_to_attr_map` re-parse. `MultiDiGraph::clone` copies the
        // IndexMap/IndexSet/Vec verbatim, preserving node + edge + parallel-key
        // insertion order exactly; only the deep-copy of the Python attr dicts /
        // key objects remains.
        let mut new_graph = Self {
            inner: self.inner.clone_with_fresh_policy(), // br-r37-c1-7dpyg: skip ledger
            node_key_map: HashMap::with_capacity(self.node_key_map.len()),
            // br-r37-c1-z6uka: succ overrides survive nx's u-major copy walk;
            // pred rows are re-derived with node objects.
            succ_py_keys: PyDiGraph::clone_row_keys(py, &self.succ_py_keys),
            pred_py_keys: HashMap::new(),
            node_py_attrs: HashMap::with_capacity(self.node_py_attrs.len()),
            edge_py_attrs: HashMap::with_capacity(self.edge_py_attrs.len()),
            edge_py_keys: HashMap::with_capacity(self.edge_py_keys.len()),
            graph_attrs: self.graph_attrs.bind(py).copy()?.unbind(),
            nodes_seq: 0,
            edges_seq: 0,
            edges_dirty: AtomicBool::new(self.edges_dirty.load(Ordering::Relaxed)),
            edge_dirty_keys: self.cloned_edge_dirty_keys(),
            node_keys_cache: std::sync::Mutex::new(None),
            node_data_mirror: std::sync::Mutex::new(None),
            dict_of_dicts_cache: None,
            edges_with_data_cache: None,
            in_edges_with_data_cache: None,
            edges_with_keys_cache: None,
            node_iter_mirror: std::sync::Mutex::new(None),
        };
        // br-r37-c1-s0d4x: nx's MultiDiGraph.copy() walk fills PRED rows
        // in u-major order (succ rows keep original order); the verbatim
        // clone preserved the source's pred rows instead.
        new_graph.inner.reorder_pred_rows_for_nx_copy_walk();
        // Node-attr mutations are not tracked by `edges_dirty`, so refresh the
        // cloned inner's node attrs from the authoritative Python dicts.
        for (canonical, py_key) in &self.node_key_map {
            new_graph
                .node_key_map
                .insert(canonical.clone(), py_key.clone_ref(py));
            if let Some(attrs) = self.node_py_attrs.get(canonical) {
                let bound = attrs.bind(py);
                new_graph
                    .inner
                    .replace_node_attrs(canonical, crate::py_dict_to_attr_map(bound)?);
                new_graph
                    .node_py_attrs
                    .insert(canonical.clone(), bound.copy()?.unbind());
            }
        }
        // Deep-copy the edge attr dicts and per-edge Python key objects verbatim
        // (preserving first-wins key identity). For a digraph (u, v) is the
        // stored orientation, so a direct copy keeps keys aligned with the
        // cloned inner.
        for (key, attrs) in &self.edge_py_attrs {
            new_graph
                .edge_py_attrs
                .insert(key.clone(), attrs.bind(py).copy()?.unbind());
        }
        for (key, py_key) in &self.edge_py_keys {
            new_graph
                .edge_py_keys
                .insert(key.clone(), py_key.clone_ref(py));
        }
        Ok(new_graph)
    }

    /// Support ``copy.copy(G)`` — returns a shallow copy.
    ///
    /// NetworkX parity (br-r37-c1-5ctpe): `copy.copy(G)` must share the same
    /// attribute dict references (graph, node, edge attrs are `is`, not just `==`).
    /// `G.copy()` returns a deep copy; `copy.copy(G)` returns a shallow copy.
    fn __copy__(&self, py: Python<'_>) -> PyResult<Self> {
        // br-r37-c1-o1i86: wholesale inner clone (see PyMultiGraph::__copy__)
        // — the old rebuild iterated node_key_map (HashMap, scrambled node
        // order) and replayed edge iteration order, diverging succ/pred row
        // content order from the source after remove+re-add. Python-side
        // dicts are clone_ref'd so attrs stay SHARED (shallow-copy
        // semantics); row-key override maps clone exactly.
        Ok(Self {
            inner: self.inner.clone_with_fresh_policy(), // br-r37-c1-7dpyg: skip ledger
            node_key_map: self
                .node_key_map
                .iter()
                .map(|(k, v)| (k.clone(), v.clone_ref(py)))
                .collect(),
            succ_py_keys: PyDiGraph::clone_row_keys(py, &self.succ_py_keys), // br-r37-c1-z6uka
            pred_py_keys: PyDiGraph::clone_row_keys(py, &self.pred_py_keys), // br-r37-c1-z6uka
            node_py_attrs: self
                .node_py_attrs
                .iter()
                .map(|(k, v)| Ok((k.clone(), v.bind(py).copy()?.unbind())))
                .collect::<PyResult<_>>()?,
            edge_py_attrs: self
                .edge_py_attrs
                .iter()
                .map(|(k, v)| Ok((k.clone(), v.bind(py).copy()?.unbind())))
                .collect::<PyResult<_>>()?,
            edge_py_keys: self
                .edge_py_keys
                .iter()
                .map(|(k, v)| (k.clone(), v.clone_ref(py)))
                .collect(),
            // SHARE the graph attrs dict (shallow copy)
            graph_attrs: self.graph_attrs.clone_ref(py),
            nodes_seq: 0,
            edges_seq: 0,
            edges_dirty: AtomicBool::new(self.edges_dirty.load(Ordering::Relaxed)),
            edge_dirty_keys: self.cloned_edge_dirty_keys(),
            node_keys_cache: std::sync::Mutex::new(None),
            node_data_mirror: std::sync::Mutex::new(None),
            dict_of_dicts_cache: None,
            edges_with_data_cache: None,
            in_edges_with_data_cache: None,
            edges_with_keys_cache: None,
            node_iter_mirror: std::sync::Mutex::new(None),
        })
    }

    /// Support ``copy.deepcopy(G)`` — returns a deep copy.
    #[pyo3(signature = (_memo=None))]
    fn __deepcopy__(&self, py: Python<'_>, _memo: Option<&Bound<'_, PyAny>>) -> PyResult<Self> {
        // br-r37-c1-z6uka: copy.deepcopy clones the dict structure verbatim,
        // so BOTH row-override maps survive (copy() re-derives pred rows
        // with node objects per nx's u-major walk — deepcopy must not).
        let mut new_graph = self.copy(py)?;
        new_graph.pred_py_keys = PyDiGraph::clone_row_keys(py, &self.pred_py_keys);
        Ok(new_graph)
    }

    /// br-r37-c1-489mp: native same-type deepcopy (see PyGraph variant). VERBATIM
    /// structure via `__copy__` (preserves source succ/pred row order + the
    /// row-key override maps) + deep-copied node/edge attr dicts under ONE shared
    /// memo. The Python `_graph_deepcopy` tail (which routes here via hasattr) adds
    /// graph attrs, frozen flag and custom instance attrs. Replaces that override's
    /// per-node/edge AtlasView walk (the deepcopy bottleneck).
    #[pyo3(signature = (memo=None))]
    fn _native_deepcopy(&self, py: Python<'_>, memo: Option<&Bound<'_, PyAny>>) -> PyResult<Self> {
        let mut new_graph = self.__copy__(py)?;
        let deepcopy = py.import("copy")?.getattr("deepcopy")?;
        let memo_obj: Bound<'_, PyAny> = match memo {
            Some(m) if !m.is_none() => m.clone(),
            _ => PyDict::new(py).into_any(),
        };
        let node_keys: Vec<String> = new_graph.node_py_attrs.keys().cloned().collect();
        for k in node_keys {
            let deep = crate::deepcopy_py_dict_memo(
                py,
                &deepcopy,
                &new_graph.node_py_attrs[&k],
                &memo_obj,
            )?;
            new_graph.node_py_attrs.insert(k, deep);
        }
        let edge_keys: Vec<(String, String, usize)> =
            new_graph.edge_py_attrs.keys().cloned().collect();
        for k in edge_keys {
            let deep = crate::deepcopy_py_dict_memo(
                py,
                &deepcopy,
                &new_graph.edge_py_attrs[&k],
                &memo_obj,
            )?;
            new_graph.edge_py_attrs.insert(k, deep);
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
            inner: MultiDiGraph::with_runtime_policy(self.inner.runtime_policy().clone()),
            node_key_map: HashMap::new(),
            succ_py_keys: HashMap::new(), // br-r37-c1-z6uka
            pred_py_keys: HashMap::new(), // br-r37-c1-z6uka
            node_py_attrs: HashMap::new(),
            edge_py_attrs: HashMap::new(),
            edge_py_keys: HashMap::new(),
            graph_attrs: self.graph_attrs.bind(py).copy()?.unbind(),
            nodes_seq: 0,
            edges_seq: 0,
            edges_dirty: AtomicBool::new(false),
            edge_dirty_keys: Self::clean_edge_dirty_keys(),
            node_keys_cache: std::sync::Mutex::new(None),
            node_data_mirror: std::sync::Mutex::new(None),
            dict_of_dicts_cache: None,
            edges_with_data_cache: None,
            in_edges_with_data_cache: None,
            edges_with_keys_cache: None,
            node_iter_mirror: std::sync::Mutex::new(None),
        };

        for canonical in &keep {
            let rust_attrs = self
                .node_py_attrs
                .get(canonical)
                .map(|attrs| crate::py_dict_to_attr_map(attrs.bind(py)))
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
                let rust_attrs = crate::py_dict_to_attr_map(attrs.bind(py))?;
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
                if let Some(py_key) = self.edge_py_keys.get(&(u.clone(), v.clone(), *key)) {
                    new_graph.remember_edge_key_object(py, u, v, *key, py_key);
                } else {
                    new_graph.remember_edge_key(py, u, v, *key, None);
                }
            }
        }

        if !self.succ_py_keys.is_empty() {
            // br-r37-c1-z6uka: succ overrides for surviving cells; pred rows
            // are re-derived with node objects (nx walk semantics).
            new_graph.succ_py_keys = self
                .succ_py_keys
                .iter()
                .filter(|((a, b), _)| new_graph.inner.has_edge(a, b))
                .map(|(k, v)| (k.clone(), v.clone_ref(py)))
                .collect();
        }
        Ok(new_graph)
    }

    fn edge_subgraph(&self, py: Python<'_>, edges: &Bound<'_, PyAny>) -> PyResult<Self> {
        let iter = PyIterator::from_object(edges)?;
        let mut involved_nodes: HashSet<String> = HashSet::new();
        let mut new_graph = Self {
            inner: MultiDiGraph::with_runtime_policy(self.inner.runtime_policy().clone()),
            node_key_map: HashMap::new(),
            succ_py_keys: HashMap::new(), // br-r37-c1-z6uka
            pred_py_keys: HashMap::new(), // br-r37-c1-z6uka
            node_py_attrs: HashMap::new(),
            edge_py_attrs: HashMap::new(),
            edge_py_keys: HashMap::new(),
            graph_attrs: self.graph_attrs.bind(py).copy()?.unbind(),
            nodes_seq: 0,
            edges_seq: 0,
            edges_dirty: AtomicBool::new(false),
            edge_dirty_keys: Self::clean_edge_dirty_keys(),
            node_keys_cache: std::sync::Mutex::new(None),
            node_data_mirror: std::sync::Mutex::new(None),
            dict_of_dicts_cache: None,
            edges_with_data_cache: None,
            in_edges_with_data_cache: None,
            edges_with_keys_cache: None,
            node_iter_mirror: std::sync::Mutex::new(None),
        };

        for item in iter {
            let item = item?;
            let tuple = item
                .downcast::<PyTuple>()
                .map_err(|_| PyTypeError::new_err("each edge must be a tuple"))?;
            let u = node_key_to_string(py, &tuple.get_item(0)?)?;
            let v = node_key_to_string(py, &tuple.get_item(1)?)?;
            let key_filter = if tuple.len() >= 3 {
                self.resolve_internal_edge_key(py, &u, &v, &tuple.get_item(2)?)?
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
                        u.clone(),
                        v.clone(),
                        k,
                        rust_attrs,
                    );
                    new_graph
                        .edge_py_attrs
                        .insert(ek, attrs.bind(py).copy()?.unbind());
                    if let Some(py_key) = self.edge_py_keys.get(&Self::edge_key(&u, &v, k)) {
                        new_graph.remember_edge_key_object(py, &u, &v, k, py_key);
                    } else {
                        new_graph.remember_edge_key(py, &u, &v, k, None);
                    }
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

        if !self.succ_py_keys.is_empty() {
            // br-r37-c1-z6uka: succ overrides for surviving cells; pred rows
            // are re-derived with node objects (nx walk semantics).
            new_graph.succ_py_keys = self
                .succ_py_keys
                .iter()
                .filter(|((a, b), _)| new_graph.inner.has_edge(a, b))
                .map(|(k, v)| (k.clone(), v.clone_ref(py)))
                .collect();
        }
        Ok(new_graph)
    }

    fn to_directed(&self, py: Python<'_>) -> PyResult<Self> {
        self.copy(py)
    }

    fn to_undirected(&self, py: Python<'_>) -> PyResult<crate::PyMultiGraph> {
        let mut ug = crate::PyMultiGraph {
            inner: fnx_classes::MultiGraph::with_runtime_policy(
                self.inner.runtime_policy().clone(),
            ),
            node_key_map: HashMap::new(),
            adj_py_keys: HashMap::new(), // br-r37-c1-z6uka
            node_py_attrs: HashMap::new(),
            edge_py_attrs: HashMap::new(),
            edge_py_keys: HashMap::new(),
            graph_attrs: self.graph_attrs.bind(py).copy()?.unbind(),
            nodes_seq: 0,
            edges_seq: 0,
            edges_dirty: AtomicBool::new(false),
            node_keys_cache: std::sync::Mutex::new(None),
            node_data_mirror: std::sync::Mutex::new(None),
            dict_of_dicts_cache: None,
            edges_with_data_cache: None,
            edges_with_keys_cache: None,
            node_iter_mirror: std::sync::Mutex::new(None),
        };

        for (canonical, py_key) in &self.node_key_map {
            let rust_attrs = self
                .node_py_attrs
                .get(canonical)
                .map(|attrs| py_dict_to_attr_map(attrs.bind(py)))
                .transpose()?
                .unwrap_or_default();
            ug.inner.add_node_with_attrs(canonical.clone(), rust_attrs);
            ug.node_key_map
                .insert(canonical.clone(), py_key.clone_ref(py));
            if let Some(attrs) = self.node_py_attrs.get(canonical) {
                ug.node_py_attrs
                    .insert(canonical.clone(), attrs.bind(py).copy()?.unbind());
            }
        }

        for edge in self.inner.edges_ordered() {
            let u = &edge.source;
            let v = &edge.target;
            let k = edge.key;

            let mut rust_attrs = edge.attrs.clone();

            let mut py_attrs_copy = None;
            if let Some(py_attrs) = self.edge_py_attrs.get(&(u.clone(), v.clone(), k)) {
                py_attrs_copy = Some(py_attrs.bind(py).copy()?.unbind());
                rust_attrs.extend(crate::py_dict_to_attr_map(py_attrs.bind(py))?);
            }

            let new_k = ug
                .inner
                .add_edge_with_key_and_attrs(u.clone(), v.clone(), k, rust_attrs)
                .map_err(|e| crate::NetworkXError::new_err(e.to_string()))?;

            if let Some(pa) = py_attrs_copy {
                let u_undir = if u < v { u.clone() } else { v.clone() };
                let v_undir = if u < v { v.clone() } else { u.clone() };
                ug.edge_py_attrs.insert((u_undir, v_undir, new_k), pa);
            }
            ug.remember_edge_key_object(py, u, v, new_k, &self.py_edge_key(py, u, v, k));
        }

        Ok(ug)
    }

    fn reverse(&self, py: Python<'_>) -> PyResult<Self> {
        let source_edges_dirty = self.edges_dirty.load(Ordering::Relaxed);
        let dirty_edge_keys = if source_edges_dirty {
            self.edge_dirty_keys.lock().unwrap().clone()
        } else {
            Some(HashSet::new())
        };
        let mut new_graph = Self {
            inner: self.inner.reversed(),
            node_key_map: HashMap::with_capacity(self.node_key_map.len()),
            // br-r37-c1-z6uka: nx reverse walks edges(keys=True, data=True)
            // u-major and adds (v, u) — the new succ cells get NODE objects,
            // the new pred cells get the OLD succ-row objects (transpose).
            succ_py_keys: HashMap::new(),
            pred_py_keys: PyDiGraph::clone_row_keys(py, &self.succ_py_keys),
            node_py_attrs: HashMap::new(),
            edge_py_attrs: HashMap::new(),
            edge_py_keys: HashMap::with_capacity(self.edge_py_keys.len()),
            graph_attrs: self.graph_attrs.bind(py).copy()?.unbind(),
            nodes_seq: 0,
            edges_seq: 0,
            edges_dirty: AtomicBool::new(false),
            edge_dirty_keys: Self::clean_edge_dirty_keys(),
            node_keys_cache: std::sync::Mutex::new(None),
            node_data_mirror: std::sync::Mutex::new(None),
            dict_of_dicts_cache: None,
            edges_with_data_cache: None,
            in_edges_with_data_cache: None,
            edges_with_keys_cache: None,
            node_iter_mirror: std::sync::Mutex::new(None),
        };

        for canonical in self.inner.nodes_ordered() {
            new_graph
                .node_key_map
                .insert(canonical.to_owned(), self.py_node_key(py, canonical));
        }

        // Node attr dictionaries are mutable Python mirrors. They do not have a
        // dirty bit, so copy them and refresh the transposed inner store exactly
        // as the old per-node rebuild did.
        for (canonical, attrs) in &self.node_py_attrs {
            let copied_attrs = attrs.bind(py).copy()?.unbind();
            let rust_attrs = crate::py_dict_to_attr_map(copied_attrs.bind(py))?;
            new_graph.inner.replace_node_attrs(canonical, rust_attrs);
            new_graph
                .node_py_attrs
                .insert(canonical.clone(), copied_attrs);
        }

        // Preserve explicit edge-key display objects under the transposed
        // endpoints. Missing entries naturally display as the internal usize,
        // so they do not need eager materialization.
        for ((u, v, key), py_key) in &self.edge_py_keys {
            new_graph.remember_edge_key_object(py, v, u, *key, py_key);
        }

        // Edge attr mirrors are copied for Python object identity/isolation.
        // When the source mirror was dirtied after creation, also push that
        // authoritative Python dict into the already-transposed inner graph.
        for ((u, v, key), attrs) in &self.edge_py_attrs {
            let should_sync =
                source_edges_dirty && Self::should_sync_dirty_edge(&dirty_edge_keys, u, v, *key);
            let bound_attrs = attrs.bind(py);
            if should_sync || !Self::py_dict_is_lossless_attr_map(bound_attrs) {
                let copied_attrs = bound_attrs.copy()?.unbind();
                if should_sync {
                    let rust_attrs = crate::py_dict_to_attr_map(copied_attrs.bind(py))?;
                    new_graph.inner.replace_edge_attrs(v, u, *key, rust_attrs);
                }
                new_graph
                    .edge_py_attrs
                    .insert((v.clone(), u.clone(), *key), copied_attrs);
            }
        }

        Ok(new_graph)
    }

    // -----------------------------------------------------------------------
    // Bulk mutation
    // -----------------------------------------------------------------------

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
            let (u, v, w) = weighted_edge_triplet(&item)?;
            let d = PyDict::new(py);
            d.set_item(weight, &w)?;
            self.add_edge(py, &u, &v, None, Some(&d))?;
        }
        self.bump_edges_seq();
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
                Some(tuple.get_item(2)?)
            } else {
                None
            };
            let u_c = node_key_to_string(py, u)?;
            let v_c = node_key_to_string(py, v)?;
            if self.inner.has_edge(&u_c, &v_c) {
                let _ = self.remove_edge(py, u, v, key.as_ref());
            }
        }
        self.bump_edges_seq();
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

    /// br-r37-c1-sjf4t: push the per-node and per-edge Python attribute
    /// dicts back into the Rust ``inner`` graph. Called by Python-level
    /// wrappers before invoking native algorithms so post-creation
    /// mutations (``G[u][v]['k']=v``) are visible to the Rust kernels.
    fn _fnx_sync_attrs_to_inner(&mut self, py: Python<'_>) -> PyResult<()> {
        let nodes: Vec<(String, AttrMap)> = self
            .node_py_attrs
            .iter()
            .map(|(canonical, dict)| Ok((canonical.clone(), py_dict_to_attr_map(dict.bind(py))?)))
            .collect::<PyResult<_>>()?;
        for (canonical, attrs) in nodes {
            self.inner.replace_node_attrs(&canonical, attrs);
        }
        if !self.edges_dirty.load(Ordering::Relaxed) {
            return Ok(());
        }
        let dirty_keys = self.edge_dirty_keys.lock().unwrap().clone();
        let edges: Vec<(String, String, usize, AttrMap)> = self
            .edge_py_attrs
            .iter()
            .filter(|((u, v, key), _)| Self::should_sync_dirty_edge(&dirty_keys, u, v, *key))
            .map(|((u, v, key), dict)| {
                Ok((
                    u.clone(),
                    v.clone(),
                    *key,
                    py_dict_to_attr_map(dict.bind(py))?,
                ))
            })
            .collect::<PyResult<_>>()?;
        for (u, v, key, attrs) in edges {
            self.inner.replace_edge_attrs(&u, &v, key, attrs);
        }
        Ok(())
    }

    /// br-r37-c1-iyu0a: edge-only attr sync mirroring `PyDiGraph` /
    /// `PyGraph::_fnx_sync_edge_attrs_to_inner`. The full
    /// `_fnx_sync_attrs_to_inner` above walks ALL `node_py_attrs`
    /// unconditionally (MultiDiGraph `add_edge` eagerly creates empty per-node
    /// attr dicts), costing ~2.5ms even for an unmutated graph — the tax behind
    /// MultiDiGraph matrix exporters / pagerank / weighted shortest paths
    /// losing to NetworkX. Callers that only need edge attrs (the
    /// `_sync_rust_edge_attrs(..., edge_only=True)` path) get the cheap
    /// `edges_dirty` short-circuit and skip the node walk entirely.
    fn _fnx_sync_edge_attrs_to_inner(&mut self, py: Python<'_>) -> PyResult<()> {
        if !self.edges_dirty.load(Ordering::Relaxed) {
            return Ok(());
        }
        let dirty_keys = self.edge_dirty_keys.lock().unwrap().clone();
        let edges: Vec<(String, String, usize, AttrMap)> = self
            .edge_py_attrs
            .iter()
            .filter(|((u, v, key), _)| Self::should_sync_dirty_edge(&dirty_keys, u, v, *key))
            .map(|((u, v, key), dict)| {
                Ok((
                    u.clone(),
                    v.clone(),
                    *key,
                    py_dict_to_attr_map(dict.bind(py))?,
                ))
            })
            .collect::<PyResult<_>>()?;
        for (u, v, key, attrs) in edges {
            self.inner.replace_edge_attrs(&u, &v, key, attrs);
        }
        Ok(())
    }

    /// Return edge attributes. If key is None, returns dict of key -> attrs.
    #[pyo3(signature = (u, v, key=None, default=None))]
    fn get_edge_data(
        &mut self,
        py: Python<'_>,
        u: &Bound<'_, PyAny>,
        v: &Bound<'_, PyAny>,
        key: Option<&Bound<'_, PyAny>>,
        default: Option<PyObject>,
    ) -> PyResult<PyObject> {
        let u_c = node_key_to_string(py, u)?;
        let v_c = node_key_to_string(py, v)?;
        if let Some(key_obj) = key {
            let Some(internal_key) = self.resolve_internal_edge_key(py, &u_c, &v_c, key_obj)?
            else {
                return Ok(default.unwrap_or_else(|| py.None()));
            };
            self.mark_edges_dirty();
            Ok(self
                .ensure_edge_py_attrs(py, &u_c, &v_c, internal_key)
                .clone_ref(py)
                .into_any())
        } else {
            let keys = self.inner.edge_keys(&u_c, &v_c).unwrap_or_default();
            if keys.is_empty() {
                Ok(default.unwrap_or_else(|| py.None()))
            } else {
                self.mark_edges_dirty();
                let result = PyDict::new(py);
                for k in keys {
                    let attrs = self.ensure_edge_py_attrs(py, &u_c, &v_c, k).clone_ref(py);
                    result.set_item(self.py_edge_key(py, &u_c, &v_c, k), attrs.bind(py))?;
                }
                Ok(result.into_any().unbind())
            }
        }
    }

    fn __getstate__(&self, py: Python<'_>) -> PyResult<PyObject> {
        let state = PyDict::new(py);
        state.set_item("mode", compatibility_mode_name(self.inner.mode()))?;
        state.set_item(
            "runtime_policy",
            runtime_policy_json(self.inner.runtime_policy())?,
        )?;

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

        let edges_list: Vec<(PyObject, PyObject, PyObject, Py<PyDict>)> = self
            .inner
            .edges_ordered()
            .into_iter()
            .map(|edge| {
                let py_u = self.py_node_key(py, &edge.source);
                let py_v = self.py_node_key(py, &edge.target);
                let py_key = self.py_edge_key(py, &edge.source, &edge.target, edge.key);
                let attrs = self
                    .edge_py_attrs
                    .get(&Self::edge_key(&edge.source, &edge.target, edge.key))
                    .map_or_else(|| PyDict::new(py).unbind(), |d| d.clone_ref(py));
                (py_u, py_v, py_key, attrs)
            })
            .collect();
        state.set_item("edges", edges_list)?;
        state.set_item("graph", self.graph_attrs.bind(py))?;
        // br-r37-c1-u3qyn: store succ/pred rows + display overrides so the
        // round-trip preserves structure verbatim (see PyGraph).
        let row_dump = |pred: bool| -> Vec<(String, Vec<String>)> {
            self.inner
                .nodes_ordered()
                .into_iter()
                .map(|nd| {
                    let row = if pred {
                        self.inner.predecessors(nd)
                    } else {
                        self.inner.successors(nd)
                    };
                    (
                        nd.to_owned(),
                        row.unwrap_or_default()
                            .into_iter()
                            .map(str::to_owned)
                            .collect(),
                    )
                })
                .collect()
        };
        state.set_item("succ_rows", row_dump(false))?;
        state.set_item("pred_rows", row_dump(true))?;
        let dump_overrides = |m: &HashMap<(String, String), PyObject>| {
            m.iter()
                .map(|((a, b), o)| (a.clone(), b.clone(), o.clone_ref(py)))
                .collect::<Vec<(String, String, PyObject)>>()
        };
        if !self.succ_py_keys.is_empty() {
            state.set_item("succ_py_keys", dump_overrides(&self.succ_py_keys))?;
        }
        if !self.pred_py_keys.is_empty() {
            state.set_item("pred_py_keys", dump_overrides(&self.pred_py_keys))?;
        }
        Ok(state.into_any().unbind())
    }

    fn __setstate__(&mut self, py: Python<'_>, state: &Bound<'_, PyDict>) -> PyResult<()> {
        let mode = compatibility_mode_from_py(state.get_item("mode")?.as_ref())?;
        self.inner = MultiDiGraph::with_runtime_policy(runtime_policy_from_state(state, mode)?);
        self.node_key_map.clear();
        self.node_py_attrs.clear();
        self.edge_py_attrs.clear();
        self.succ_py_keys.clear(); // br-r37-c1-u3qyn
        self.pred_py_keys.clear(); // br-r37-c1-u3qyn
        self.edge_py_keys.clear();
        self.graph_attrs = PyDict::new(py).unbind();

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
                let key = tuple.get_item(2)?;
                let attrs = tuple.get_item(3)?;
                let attrs_dict = attrs.downcast::<PyDict>()?;
                self.add_edge(py, &u, &v, Some(&key), Some(attrs_dict))?;
            }
        }

        // br-r37-c1-u3qyn: restore exact succ/pred row order and display
        // overrides when the state carries them (optional, back-compat).
        if let Some(rows) = state.get_item("succ_rows")? {
            let orders: Vec<(String, Vec<String>)> = rows.extract()?;
            self.inner.apply_row_orders(&orders, false);
        }
        if let Some(rows) = state.get_item("pred_rows")? {
            let orders: Vec<(String, Vec<String>)> = rows.extract()?;
            self.inner.apply_row_orders(&orders, true);
        }
        if let Some(overrides) = state.get_item("succ_py_keys")? {
            let entries: Vec<(String, String, PyObject)> = overrides.extract()?;
            for (a, b, o) in entries {
                self.succ_py_keys.insert((a, b), o);
            }
        }
        if let Some(overrides) = state.get_item("pred_py_keys")? {
            let entries: Vec<(String, String, PyObject)> = overrides.extract()?;
            for (a, b, o) in entries {
                self.pred_py_keys.insert((a, b), o);
            }
        }

        Ok(())
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

    fn __iter__(&self, py: Python<'_>) -> PyResult<PyObject> {
        // Serve from the live node_iter_mirror dict_keyiterator (matching nx)
        // instead of rebuilding a Vec<PyObject> of every display key per call.
        let mirror = self.graph.borrow(py).node_iter_mirror_or_init(py)?;
        Ok(mirror.bind(py).call_method0("__iter__")?.unbind())
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
            return Err(crate::missing_key_error(n));
        }
        Ok(g.node_py_attrs.get(&canonical).map_or_else(
            || PyDict::new(py).into_any().unbind(),
            |d| d.clone_ref(py).into_any(),
        ))
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
        // br-r37-c1-d58s8: materialize absent mirrors (write-through).
        Ok(g.node_py_attrs
            .entry(canonical)
            .or_insert_with(|| PyDict::new(py).unbind())
            .clone_ref(py)
            .into_any())
    }

    /// Return a list of node keys (like dict.keys()).
    fn keys(&self, py: Python<'_>) -> PyResult<Vec<PyObject>> {
        let g = self.graph.borrow(py);
        Ok(g.inner
            .nodes_ordered()
            .into_iter()
            .map(|n| g.py_node_key(py, n))
            .collect())
    }

    /// Return (node, attrs) pairs (like dict.items()).
    /// br-r37-c1-4b5ie: serve from the nodes_seq-keyed node_data_mirror so
    /// repeated nodes(data=...) on an unchanged graph reuse the cache.
    fn items(&self, py: Python<'_>) -> PyResult<PyObject> {
        let mut g = self.graph.borrow_mut(py);
        g.node_data_items_view(py)
    }

    /// Return a list of attr dicts (like dict.values()).
    fn values(&self, py: Python<'_>) -> PyResult<Vec<PyObject>> {
        let g = self.graph.borrow(py);
        Ok(g.inner
            .nodes_ordered()
            .into_iter()
            .map(|n| {
                g.node_py_attrs.get(n).map_or_else(
                    || PyDict::new(py).into_any().unbind(),
                    |d| d.clone_ref(py).into_any(),
                )
            })
            .collect())
    }

    /// Return a view iterating over (node, data) pairs.
    #[pyo3(signature = (data=None, default=None))]
    fn data(
        &self,
        py: Python<'_>,
        data: Option<&Bound<'_, PyAny>>,
        default: Option<PyObject>,
    ) -> PyResult<Vec<PyObject>> {
        let g = self.graph.borrow(py);
        let mut result = Vec::new();
        for node in g.inner.nodes_ordered() {
            let py_node = g.py_node_key(py, node);
            let val = if let Some(d) = data {
                if let Ok(attr_name) = d.extract::<String>() {
                    g.node_py_attrs
                        .get(node)
                        .and_then(|dict| dict.bind(py).get_item(attr_name.as_str()).ok().flatten())
                        .map_or_else(
                            || default.as_ref().map_or(py.None(), |d| d.clone_ref(py)),
                            |v| v.unbind(),
                        )
                } else {
                    g.node_py_attrs.get(node).map_or_else(
                        || PyDict::new(py).into_any().unbind(),
                        |d| d.clone_ref(py).into_any(),
                    )
                }
            } else {
                g.node_py_attrs.get(node).map_or_else(
                    || PyDict::new(py).into_any().unbind(),
                    |d| d.clone_ref(py).into_any(),
                )
            };
            let pair = PyTuple::new(py, &[py_node, val])?;
            result.push(pair.into_any().unbind());
        }
        Ok(result)
    }

    /// Union: self | other
    fn __or__(&self, py: Python<'_>, other: &Bound<'_, PyAny>) -> PyResult<PyObject> {
        let g = self.graph.borrow(py);
        let self_nodes: Vec<PyObject> = g
            .inner
            .nodes_ordered()
            .into_iter()
            .map(|n| g.py_node_key(py, n))
            .collect();
        let self_set = pyo3::types::PySet::new(py, self_nodes.iter())?;
        for item in pyo3::types::PyIterator::from_object(other)? {
            self_set.add(item?)?;
        }
        Ok(self_set.into_any().unbind())
    }

    /// Intersection: self & other
    fn __and__(&self, py: Python<'_>, other: &Bound<'_, PyAny>) -> PyResult<PyObject> {
        let g = self.graph.borrow(py);
        let other_vec: Vec<PyObject> = pyo3::types::PyIterator::from_object(other)?
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
        let other_vec: Vec<PyObject> = pyo3::types::PyIterator::from_object(other)?
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
            .into_iter()
            .map(|n| g.py_node_key(py, n))
            .collect();
        let self_set = pyo3::types::PySet::new(py, self_nodes.iter())?;
        let other_vec: Vec<PyObject> = pyo3::types::PyIterator::from_object(other)?
            .map(|r| r.map(|o| o.unbind()))
            .collect::<PyResult<Vec<_>>>()?;
        let other_set = pyo3::types::PySet::new(py, other_vec.iter())?;
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

#[pyclass]
pub struct MultiDiGraphEdgeView {
    graph: Py<PyMultiDiGraph>,
}

#[pymethods]
impl MultiDiGraphEdgeView {
    fn __len__(&self, py: Python<'_>) -> usize {
        self.graph.borrow(py).inner.edge_count()
    }

    fn __contains__(&self, py: Python<'_>, edge: &Bound<'_, PyAny>) -> PyResult<bool> {
        let tuple = edge
            .downcast::<PyTuple>()
            .map_err(|_| pyo3::exceptions::PyTypeError::new_err("edge must be a tuple"))?;
        let len = tuple.len();
        if len < 2 {
            return Ok(false);
        }
        let u = node_key_to_string(py, &tuple.get_item(0)?)?;
        let v = node_key_to_string(py, &tuple.get_item(1)?)?;
        let g = self.graph.borrow(py);
        if !g.inner.has_edge(&u, &v) {
            return Ok(false);
        }
        if len == 2 {
            // 2-tuple: just check if edge exists
            return Ok(true);
        }
        // 3-tuple: check if specific key exists
        let key_obj = tuple.get_item(2)?;
        let key: usize = key_obj.extract().unwrap_or(usize::MAX);
        // Check if this key exists by looking at all edges
        for edge in g.inner.edges_ordered() {
            if edge.source.as_str() == u && edge.target.as_str() == v && edge.key == key {
                return Ok(true);
            }
        }
        Ok(false)
    }

    fn __iter__(&self, py: Python<'_>) -> PyResult<Py<crate::NodeIterator>> {
        self.__call__(py, None, None, false, None)
    }

    #[pyo3(signature = (nbunch=None, data=None, keys=false, default=None))]
    fn __call__(
        &self,
        py: Python<'_>,
        nbunch: Option<&Bound<'_, PyAny>>,
        data: Option<&Bound<'_, PyAny>>,
        keys: bool,
        default: Option<&Bound<'_, PyAny>>,
    ) -> PyResult<Py<crate::NodeIterator>> {
        let mut g = self.graph.borrow_mut(py);
        // Only the node COUNT is needed (NodeIterator mutation guard); avoid
        // cloning every node key into a Vec<String> per call.
        let node_count = g.inner.node_count();
        let source_nodes = parse_edge_nbunch_for_multidigraph(py, &g, nbunch)?;
        let mut view_data = parse_view_data(data)?;
        if let (Some(def), ViewData::Attr(attr)) = (default, &view_data) {
            view_data = ViewData::AttrWithDefault(attr.clone(), def.clone().unbind());
        }
        if matches!(&view_data, ViewData::AllData) && g.inner.edge_count() > 0 {
            g.mark_edges_dirty();
        }
        // br-r37-c1-o07ax: the data=True, keys=False, no-nbunch variant (the
        // common edges(data=True)) yields (u, v, live_attr) immutable tuples —
        // serve them from the (nodes_seq, edges_seq) cache via a borrow_mut.
        if source_nodes.is_none() && matches!(&view_data, ViewData::AllData) && !keys {
            drop(g);
            let result = self.graph.borrow_mut(py).edges_alldata_tuples(py)?;
            return Py::new(
                py,
                crate::NodeIterator::with_graph_guard(
                    py,
                    result,
                    crate::NodeIteratorGuard::MultiDiGraph(self.graph.clone_ref(py)),
                    node_count,
                ),
            );
        }
        if source_nodes.is_none() && matches!(&view_data, ViewData::NoData) && keys {
            drop(g);
            let result = self.graph.borrow_mut(py).edges_key_tuples(py)?;
            return Py::new(
                py,
                crate::NodeIterator::with_graph_guard(
                    py,
                    result,
                    crate::NodeIteratorGuard::MultiDiGraph(self.graph.clone_ref(py)),
                    node_count,
                ),
            );
        }
        if source_nodes.is_none()
            && matches!(&view_data, ViewData::AllData)
            && keys
            && let Some(result) = g.edges_key_alldata_existing_mirrors(py)?
        {
            drop(g);
            return Py::new(
                py,
                crate::NodeIterator::with_graph_guard(
                    py,
                    result,
                    crate::NodeIteratorGuard::MultiDiGraph(self.graph.clone_ref(py)),
                    node_count,
                ),
            );
        }
        let mut result = Vec::new();
        // br-r37-c1-edgesnbunch: walk only the requested sources' out-edges
        // (in nbunch order) instead of cloning + scanning EVERY edge via the
        // owned edges_ordered(). edges_ordered() clones each edge's AttrMap
        // (unused here — attrs come from edge_py_attrs), so the old path was
        // O(E) clones per call even for a single-node nbunch (~295x slower
        // than nx). The borrowed per-source walk is O(sum out-deg) with zero
        // clones, and emitting sources in nbunch order matches nx's
        // OutMultiEdgeView (the old filter-by-membership path yielded
        // node-iteration order — a latent divergence for multi-node nbunch).
        let edge_keys: Vec<(String, String, usize)> = match source_nodes.as_ref() {
            Some(sources) => {
                let mut v = Vec::new();
                for s in sources {
                    v.extend(
                        g.inner
                            .out_edges_ordered_borrowed(s)
                            .into_iter()
                            .map(|(src, tgt, key, _attrs)| (src.to_owned(), tgt.to_owned(), key)),
                    );
                }
                v
            }
            None => g
                .inner
                .edges_ordered_borrowed()
                .into_iter()
                .map(|(src, tgt, key, _attrs)| (src.to_owned(), tgt.to_owned(), key))
                .collect(),
        };
        for (src, tgt, ekey) in &edge_keys {
            let py_u = g.py_node_key(py, src);
            let py_v = g.py_succ_key(py, src, tgt) /* br-r37-c1-z6uka */;
            let key_obj = g.py_edge_key(py, src, tgt, *ekey);
            let item = match &view_data {
                ViewData::NoData => {
                    if keys {
                        tuple_object(py, &[py_u, py_v, key_obj])?
                    } else {
                        tuple_object(py, &[py_u, py_v])?
                    }
                }
                ViewData::AllData => {
                    let attrs = g
                        .ensure_edge_py_attrs(py, src, tgt, *ekey)
                        .clone_ref(py)
                        .into_any();
                    if keys {
                        tuple_object(py, &[py_u, py_v, key_obj, attrs])?
                    } else {
                        tuple_object(py, &[py_u, py_v, attrs])?
                    }
                }
                ViewData::Attr(attr_name) => {
                    let val = g
                        .ensure_edge_py_attrs(py, src, tgt, *ekey)
                        .bind(py)
                        .get_item(attr_name.as_str())
                        .ok()
                        .flatten()
                        .map_or_else(|| py.None(), |v| v.unbind());
                    if keys {
                        tuple_object(py, &[py_u, py_v, key_obj, val])?
                    } else {
                        tuple_object(py, &[py_u, py_v, val])?
                    }
                }
                ViewData::AttrWithDefault(attr_name, def_val) => {
                    let val = g
                        .ensure_edge_py_attrs(py, src, tgt, *ekey)
                        .bind(py)
                        .get_item(attr_name.as_str())
                        .ok()
                        .flatten()
                        .map_or_else(|| def_val.clone_ref(py), |v| v.unbind());
                    if keys {
                        tuple_object(py, &[py_u, py_v, key_obj, val])?
                    } else {
                        tuple_object(py, &[py_u, py_v, val])?
                    }
                }
            };
            result.push(item);
        }
        drop(g);
        Py::new(
            py,
            crate::NodeIterator::with_graph_guard(
                py,
                result,
                crate::NodeIteratorGuard::MultiDiGraph(self.graph.clone_ref(py)),
                node_count,
            ),
        )
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
            return Err(crate::missing_key_error(n));
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
            let deg_obj = deg.into_py_any(py)?;
            let pair = PyTuple::new(py, &[py_node, deg_obj])?;
            result.push(pair.into_any().unbind());
        }
        Py::new(py, crate::NodeIterator::unguarded(result))
    }
}

impl PyDiGraph {
    /// Directed edge key — preserves order (no canonicalization).
    pub(crate) fn edge_key(u: &str, v: &str) -> (String, String) {
        (u.to_owned(), v.to_owned())
    }

    /// br-r37-c1-degnbnative (cc): shared impl for the directed degree(nbunch)
    /// subset kernels (total / in / out).
    fn degree_pairs_subset_impl(
        &self,
        py: Python<'_>,
        nbunch: &Bound<'_, PyAny>,
        kind: DegreeKind,
    ) -> PyResult<Vec<(PyObject, usize)>> {
        let mut out: Vec<(PyObject, usize)> = Vec::new();
        for item in nbunch.try_iter()? {
            let node = item?;
            if node.hash().is_err() {
                let label = node
                    .str()
                    .map(|s| s.to_string_lossy().into_owned())
                    .unwrap_or_else(|_| "?".to_owned());
                return Err(pyo3::exceptions::PyTypeError::new_err(format!(
                    "Node {label} in sequence nbunch is not a valid node."
                )));
            }
            let canonical = node_key_to_string(py, &node)?;
            if let Some(idx) = self.inner.get_node_index(&canonical) {
                let deg = match kind {
                    DegreeKind::In => self.inner.in_degree_by_index(idx),
                    DegreeKind::Out => self.inner.out_degree_by_index(idx),
                    DegreeKind::Total => self.inner.degree_by_index(idx),
                };
                out.push((node.clone().unbind(), deg));
            }
        }
        Ok(out)
    }

    /// br-r37-c1-edgenbnative (cc): shared impl for out/in_edges(nbunch) data=False.
    /// out_dir=true -> successors (out-edges, (node, target)); false -> predecessors
    /// (in-edges, (source, node)). nbunch order x row order, matching the Python
    /// edges()/pred-walk; absent nodes skipped; unhashable -> TypeError(exact msg).
    fn edges_nbunch_no_data_impl(
        &self,
        py: Python<'_>,
        nbunch: &Bound<'_, PyAny>,
        out_dir: bool,
    ) -> PyResult<Option<Vec<(PyObject, PyObject)>>> {
        // Row order MUST match nx's succ[u] / pred[v] iteration; the inner INDEX
        // rows (successors_indices/predecessors_indices) preserve it (the string
        // accessors do not). Per-cell z6uka row-display overrides aren't captured
        // by the cached node objects -> fall back to Python for those.
        if (out_dir && !self.succ_py_keys.is_empty()) || (!out_dir && !self.pred_py_keys.is_empty())
        {
            return Ok(None);
        }
        let py_nodes = self.cached_node_key_vec(py);
        let mut out: Vec<(PyObject, PyObject)> = Vec::new();
        // nx dedups repeated nbunch nodes (out_edges([1,1,2]) == out_edges([1,2])).
        let mut seen: std::collections::HashSet<usize> = std::collections::HashSet::new();
        for item in nbunch.try_iter()? {
            let node = item?;
            if node.hash().is_err() {
                let label = node
                    .str()
                    .map(|s| s.to_string_lossy().into_owned())
                    .unwrap_or_else(|_| "?".to_owned());
                return Err(pyo3::exceptions::PyTypeError::new_err(format!(
                    "Node {label} in sequence nbunch is not a valid node."
                )));
            }
            let canonical = node_key_to_string(py, &node)?;
            let Some(idx) = self.inner.get_node_index(&canonical) else {
                continue;
            };
            if !seen.insert(idx) {
                continue;
            }
            let neighbors = if out_dir {
                self.inner.successors_indices(idx)
            } else {
                self.inner.predecessors_indices(idx)
            };
            for &nbr_idx in neighbors.unwrap_or(&[]) {
                let nbr_obj = py_nodes[nbr_idx].clone_ref(py);
                if out_dir {
                    out.push((node.clone().unbind(), nbr_obj));
                } else {
                    out.push((nbr_obj, node.clone().unbind()));
                }
            }
        }
        Ok(Some(out))
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

    /// br-r37-c1-4b5ie: mirror of PyGraph::materialize_node_py_attrs — return
    /// the canonical (stored) Python attr dict for `canonical`, allocating and
    /// storing an empty one on first touch so later writes (via
    /// DiNodeView.__getitem__) land on the SAME object the data mirror caches.
    pub(crate) fn materialize_node_py_attrs(
        &mut self,
        py: Python<'_>,
        canonical: &str,
    ) -> Py<PyDict> {
        self.node_py_attrs
            .entry(canonical.to_owned())
            .or_insert_with(|| PyDict::new(py).unbind())
            .clone_ref(py)
    }

    /// br-r37-c1-4b5ie: mirror of PyGraph::node_data_items_view — build (and
    /// cache, keyed on nodes_seq) the {node: attr_dict} dict in node order and
    /// return its `.items()`. Repeat calls on an unchanged graph reuse the
    /// cached dict instead of rebuilding every (node, dict) pair. The cached
    /// dict holds the SAME live attr-dict objects stored in node_py_attrs, so
    /// in-place attr mutations reflect; node insertion bumps nodes_seq and
    /// invalidates the cache.
    pub(crate) fn node_data_items_view(&mut self, py: Python<'_>) -> PyResult<PyObject> {
        let seq = self.nodes_seq;
        if let Some(dict) = self
            .node_data_mirror
            .lock()
            .unwrap()
            .as_ref()
            .and_then(|(cached_seq, dict)| (*cached_seq == seq).then(|| dict.clone_ref(py)))
        {
            return Ok(dict.bind(py).call_method0("items")?.unbind());
        }

        let nodes: Vec<String> = self
            .inner
            .nodes_ordered()
            .iter()
            .map(|node| (*node).to_owned())
            .collect();
        let dict = PyDict::new(py);
        for node in &nodes {
            let py_key = self.py_node_key(py, node);
            let attrs = self.materialize_node_py_attrs(py, node);
            dict.set_item(py_key, attrs.bind(py))?;
        }
        let owned = dict.unbind();
        *self.node_data_mirror.lock().unwrap() = Some((seq, owned.clone_ref(py)));
        Ok(owned.bind(py).call_method0("items")?.unbind())
    }

    /// br-r37-c1-fpssi: all node display objects as a Vec, reusing the
    /// nodes_seq-keyed tuple cache (clone_ref of cached elements) instead of
    /// rebuilding via py_node_key per node. Backs the graph node iterator
    /// (`set(G)` / `for n in G`), which keeps its per-next nodes_seq guard.
    pub(crate) fn cached_node_key_vec(&self, py: Python<'_>) -> Vec<PyObject> {
        self.cached_node_key_tuple(py)
            .bind(py)
            .iter()
            .map(|o| o.unbind())
            .collect()
    }

    fn cached_node_key_tuple(&self, py: Python<'_>) -> Py<PyTuple> {
        let seq = self.nodes_seq;
        {
            let guard = self.node_keys_cache.lock().unwrap();
            if let Some((cached_seq, tup)) = guard.as_ref()
                && *cached_seq == seq
            {
                return tup.clone_ref(py);
            }
        }
        let keys: Vec<PyObject> = self
            .inner
            .nodes_ordered()
            .into_iter()
            .map(|n| self.py_node_key(py, n))
            .collect();
        let tup = pyo3::types::PyTuple::new(py, &keys)
            .expect("node-keys tuple")
            .unbind();
        *self.node_keys_cache.lock().unwrap() = Some((seq, tup.clone_ref(py)));
        tup
    }

    /// Incremental node-iteration mirror (see the `node_iter_mirror` field).
    /// Lazily built from `nodes_ordered()` on first access, then kept live by
    /// the insert/remove/clear hooks. Mirrors PyGraph::node_iter_mirror_or_init.
    pub(crate) fn node_iter_mirror_or_init(&self, py: Python<'_>) -> PyResult<Py<PyDict>> {
        if let Some(dict) = self
            .node_iter_mirror
            .lock()
            .unwrap()
            .as_ref()
            .map(|dict| dict.clone_ref(py))
        {
            return Ok(dict);
        }
        let dict = PyDict::new(py);
        for canonical in self.inner.nodes_ordered() {
            dict.set_item(self.py_node_key(py, canonical), py.None())?;
        }
        let owned = dict.unbind();
        *self.node_iter_mirror.lock().unwrap() = Some(owned.clone_ref(py));
        Ok(owned)
    }

    /// True when the mirror has been materialised (so hooks must run).
    fn node_iter_mirror_active(&self) -> bool {
        self.node_iter_mirror.lock().unwrap().is_some()
    }

    fn node_iter_mirror_insert(&self, py: Python<'_>, canonical: &str) -> PyResult<()> {
        let Some(dict) = self
            .node_iter_mirror
            .lock()
            .unwrap()
            .as_ref()
            .map(|dict| dict.clone_ref(py))
        else {
            return Ok(());
        };
        dict.bind(py)
            .set_item(self.py_node_key(py, canonical), py.None())
    }

    fn node_iter_mirror_remove_key(&self, py: Python<'_>, key: &Bound<'_, PyAny>) {
        let Some(dict) = self
            .node_iter_mirror
            .lock()
            .unwrap()
            .as_ref()
            .map(|dict| dict.clone_ref(py))
        else {
            return;
        };
        let _ = dict.bind(py).del_item(key);
    }

    fn node_iter_mirror_clear(&self, py: Python<'_>) -> PyResult<()> {
        let Some(dict) = self
            .node_iter_mirror
            .lock()
            .unwrap()
            .as_ref()
            .map(|dict| dict.clone_ref(py))
        else {
            return Ok(());
        };
        dict.bind(py).call_method0("clear")?;
        Ok(())
    }

    /// br-r37-c1-z6uka: succ-row display object (see PyGraph::py_adj_key).
    pub(crate) fn py_succ_key(&self, py: Python<'_>, owner: &str, nbr: &str) -> PyObject {
        if !self.succ_py_keys.is_empty()
            && let Some(obj) = self.succ_py_keys.get(&(owner.to_owned(), nbr.to_owned()))
        {
            return obj.clone_ref(py);
        }
        self.py_node_key(py, nbr)
    }

    /// br-r37-c1-z6uka: pred-row display object.
    pub(crate) fn py_pred_key(&self, py: Python<'_>, owner: &str, nbr: &str) -> PyObject {
        if !self.pred_py_keys.is_empty()
            && let Some(obj) = self.pred_py_keys.get(&(owner.to_owned(), nbr.to_owned()))
        {
            return obj.clone_ref(py);
        }
        self.py_node_key(py, nbr)
    }

    /// br-r37-c1-z6uka: deep-clone a row-override map.
    pub(crate) fn clone_row_keys(
        py: Python<'_>,
        m: &HashMap<(String, String), PyObject>,
    ) -> HashMap<(String, String), PyObject> {
        m.iter()
            .map(|(k, v)| (k.clone(), v.clone_ref(py)))
            .collect()
    }

    /// br-r37-c1-z6uka: record per-row overrides for a NEWLY created
    /// directed edge — succ[u][v] keeps v's object, pred[v][u] keeps u's
    /// (both apply for self-loops: distinct dict cells in nx).
    fn maybe_store_row_keys(
        &mut self,
        py: Python<'_>,
        u_canonical: &str,
        v_canonical: &str,
        u: &Bound<'_, PyAny>,
        v: &Bound<'_, PyAny>,
    ) {
        let differs = |canonical: &str, passed: &Bound<'_, PyAny>| -> bool {
            self.node_key_map.get(canonical).is_some_and(|stored| {
                crate::PyGraph::display_objs_conflict(stored.bind(py), passed)
            })
        };
        if differs(v_canonical, v) {
            self.succ_py_keys
                .entry((u_canonical.to_owned(), v_canonical.to_owned()))
                .or_insert_with(|| v.clone().unbind());
        }
        if differs(u_canonical, u) {
            self.pred_py_keys
                .entry((v_canonical.to_owned(), u_canonical.to_owned()))
                .or_insert_with(|| u.clone().unbind());
        }
    }

    fn is_plain_batch_node(key: &Bound<'_, PyAny>) -> bool {
        if key.is_instance_of::<PyString>()
            || key.is_instance_of::<PyInt>()
            || key.is_instance_of::<PyFloat>()
        {
            return true;
        }
        if let Ok(tuple) = key.downcast::<PyTuple>() {
            return tuple.iter().all(|item| {
                item.is_instance_of::<PyString>()
                    || item.is_instance_of::<PyInt>()
                    || item.is_instance_of::<PyFloat>()
            });
        }
        false
    }

    fn batch_display_conflict(
        &self,
        py: Python<'_>,
        canonical: &str,
        passed: &Bound<'_, PyAny>,
        batch_first: &mut HashMap<String, PyObject>,
    ) -> bool {
        if passed.is_exact_instance_of::<PyString>() {
            return false;
        }
        if let Some(stored) = self.node_key_map.get(canonical) {
            return PyGraph::display_objs_conflict(stored.bind(py), passed);
        }
        if let Some(first) = batch_first.get(canonical) {
            return PyGraph::display_objs_conflict(first.bind(py), passed);
        }
        batch_first.insert(canonical.to_owned(), passed.clone().unbind());
        false
    }

    fn collect_plain_edge_batch<'py, I>(
        &self,
        py: Python<'py>,
        items: I,
        len: usize,
    ) -> PyResult<Option<DiEdgeBatch>>
    where
        I: IntoIterator<Item = Bound<'py, PyAny>>,
    {
        let mut edges = Vec::with_capacity(len);
        let mut new_nodes = Vec::new();
        let mut seen_nodes: HashSet<String> = self
            .inner
            .nodes_ordered()
            .into_iter()
            .map(str::to_owned)
            .collect();
        let mut node_bumps = 0_u64;
        let mut batch_first: HashMap<String, PyObject> = HashMap::new();

        for item in items {
            let Ok(tuple) = item.downcast::<PyTuple>() else {
                return Ok(None);
            };
            if tuple.len() != 2 {
                return Ok(None);
            }

            let u = tuple.get_item(0)?;
            let v = tuple.get_item(1)?;
            if !Self::is_plain_batch_node(&u) || !Self::is_plain_batch_node(&v) {
                return Ok(None);
            }

            let u_canonical = node_key_to_string(py, &u)?;
            let v_canonical = node_key_to_string(py, &v)?;
            if self.batch_display_conflict(py, &u_canonical, &u, &mut batch_first)
                || self.batch_display_conflict(py, &v_canonical, &v, &mut batch_first)
            {
                return Ok(None);
            }

            if !seen_nodes.contains(&u_canonical) || !seen_nodes.contains(&v_canonical) {
                node_bumps = node_bumps.wrapping_add(1);
            }
            if seen_nodes.insert(u_canonical.clone()) {
                new_nodes.push((u_canonical.clone(), u.clone().unbind()));
            }
            if seen_nodes.insert(v_canonical.clone()) {
                new_nodes.push((v_canonical.clone(), v.clone().unbind()));
            }
            edges.push((u_canonical, v_canonical));
        }

        Ok(Some((edges, new_nodes, node_bumps)))
    }

    fn add_plain_edge_batch(
        &mut self,
        py: Python<'_>,
        edges: Vec<(String, String)>,
        new_nodes: Vec<(String, PyObject)>,
        node_bumps: u64,
        final_edge_bump: bool,
    ) {
        let edge_bumps = u64::try_from(edges.len())
            .unwrap_or(u64::MAX)
            .wrapping_add(u64::from(final_edge_bump));

        let mirror_active = self.node_iter_mirror_active();
        for (canonical, node) in new_nodes {
            let mirror_key = if mirror_active {
                Some(canonical.clone())
            } else {
                None
            };
            self.node_key_map.entry(canonical).or_insert(node);
            if let Some(c) = mirror_key {
                let _ = self.node_iter_mirror_insert(py, &c);
            }
        }
        // br-r37-c1-89kxg (DiGraph parity): NO eager empty mirror dicts — the
        // simple PyGraph batch already dropped these; every node/edge attr
        // reader goes through materialize_*/ensure_*/entry().or_insert, so an
        // absent mirror is observationally identical to an empty dict. Saves one
        // PyDict::new per new node + one per edge during bulk construction
        // (add_edges_from / set-ops / copy on DiGraph).
        let _ = py;
        let _inserted = self.inner.extend_edges_unrecorded(edges);
        self.nodes_seq = self.nodes_seq.wrapping_add(node_bumps);
        self.edges_seq = self.edges_seq.wrapping_add(edge_bumps);
    }

    fn try_add_plain_edge_batch(
        &mut self,
        py: Python<'_>,
        ebunch_to_add: &Bound<'_, PyAny>,
        final_edge_bump: bool,
    ) -> PyResult<bool> {
        const PLAIN_EDGE_BATCH_MIN: usize = 8;
        if !self.succ_row_py.is_empty() || !self.pred_row_py.is_empty() {
            return Ok(false);
        }
        if let Ok(list) = ebunch_to_add.downcast::<PyList>() {
            if list.len() < PLAIN_EDGE_BATCH_MIN {
                return Ok(false);
            }
            if let Some((edges, new_nodes, node_bumps)) =
                self.collect_plain_edge_batch(py, list.iter(), list.len())?
            {
                self.add_plain_edge_batch(py, edges, new_nodes, node_bumps, final_edge_bump);
                return Ok(true);
            }
        } else if let Ok(tuple) = ebunch_to_add.downcast::<PyTuple>()
            && tuple.len() >= PLAIN_EDGE_BATCH_MIN
            && let Some((edges, new_nodes, node_bumps)) =
                self.collect_plain_edge_batch(py, tuple.iter(), tuple.len())?
        {
            self.add_plain_edge_batch(py, edges, new_nodes, node_bumps, final_edge_bump);
            return Ok(true);
        }
        Ok(false)
    }

    fn collect_attr_edge_batch<'py, I>(
        &self,
        py: Python<'py>,
        items: I,
        len: usize,
    ) -> PyResult<Option<DiAttrEdgeBatch>>
    where
        I: IntoIterator<Item = Bound<'py, PyAny>>,
    {
        let mut edges: Vec<(String, String, AttrMap, Option<Py<PyDict>>)> = Vec::with_capacity(len);
        let mut new_nodes = Vec::new();
        let mut seen_nodes: HashSet<String> = self
            .inner
            .nodes_ordered()
            .into_iter()
            .map(str::to_owned)
            .collect();
        let mut node_bumps = 0_u64;
        let mut batch_first: HashMap<String, PyObject> = HashMap::new();

        for item in items {
            let Ok(tuple) = item.downcast::<PyTuple>() else {
                return Ok(None);
            };
            let tlen = tuple.len();
            if !(2..=3).contains(&tlen) {
                return Ok(None);
            }

            let u = tuple.get_item(0)?;
            let v = tuple.get_item(1)?;
            if !Self::is_plain_batch_node(&u) || !Self::is_plain_batch_node(&v) {
                return Ok(None);
            }

            let (rust_attrs, src_dict) = if tlen == 3 {
                let third = tuple.get_item(2)?;
                let Ok(dict) = third.downcast::<PyDict>() else {
                    return Ok(None);
                };
                let Ok((attrs, mirror)) = py_dict_to_attr_map_with_mirror(py, dict) else {
                    return Ok(None);
                };
                if attrs
                    .keys()
                    .any(|key| key.starts_with("__fnx_incompatible"))
                {
                    return Ok(None);
                }
                (attrs, Some(mirror))
            } else {
                (AttrMap::new(), None)
            };

            let u_canonical = node_key_to_string(py, &u)?;
            let v_canonical = node_key_to_string(py, &v)?;
            if self.batch_display_conflict(py, &u_canonical, &u, &mut batch_first)
                || self.batch_display_conflict(py, &v_canonical, &v, &mut batch_first)
            {
                return Ok(None);
            }

            if !seen_nodes.contains(&u_canonical) || !seen_nodes.contains(&v_canonical) {
                node_bumps = node_bumps.wrapping_add(1);
            }
            if seen_nodes.insert(u_canonical.clone()) {
                new_nodes.push((u_canonical.clone(), u.clone().unbind()));
            }
            if seen_nodes.insert(v_canonical.clone()) {
                new_nodes.push((v_canonical.clone(), v.clone().unbind()));
            }
            edges.push((u_canonical, v_canonical, rust_attrs, src_dict));
        }

        Ok(Some((edges, new_nodes, node_bumps)))
    }

    fn collect_fresh_exact_int_attr_edge_batch<'py, I>(
        &self,
        _py: Python<'py>,
        items: I,
        len: usize,
    ) -> PyResult<Option<DiIndexedAttrEdgeBatch>>
    where
        I: IntoIterator<Item = Bound<'py, PyAny>>,
    {
        let node_capacity = len.saturating_mul(2);
        let mut node_indices: HashMap<i64, usize> = HashMap::with_capacity(node_capacity);
        let mut node_labels: Vec<String> = Vec::with_capacity(node_capacity);
        let mut node_objects: Vec<PyObject> = Vec::with_capacity(node_capacity);
        let mut edges: Vec<(usize, usize, AttrMap)> = Vec::with_capacity(len);
        let mut node_bumps = 0_u64;

        for item in items {
            let Ok(tuple) = item.downcast::<PyTuple>() else {
                return Ok(None);
            };
            if tuple.len() != 3 {
                return Ok(None);
            }

            let u = tuple.get_item(0)?;
            let v = tuple.get_item(1)?;
            if !u.is_exact_instance_of::<PyInt>()
                || !v.is_exact_instance_of::<PyInt>()
                || u.is_exact_instance_of::<PyBool>()
                || v.is_exact_instance_of::<PyBool>()
            {
                return Ok(None);
            }
            let Ok(u_value) = u.extract::<i64>() else {
                return Ok(None);
            };
            let Ok(v_value) = v.extract::<i64>() else {
                return Ok(None);
            };

            let third = tuple.get_item(2)?;
            let Ok(dict) = third.downcast::<PyDict>() else {
                return Ok(None);
            };
            let attrs = match single_weight_float_attr_map(dict) {
                Ok(Some(attrs)) => attrs,
                Ok(None) => {
                    let Ok(attrs) = py_dict_to_attr_map(dict) else {
                        return Ok(None);
                    };
                    attrs
                }
                Err(_) => return Ok(None),
            };
            if attrs
                .keys()
                .any(|key| key.starts_with("__fnx_incompatible"))
            {
                return Ok(None);
            }

            let mut edge_added_node = false;
            let u_index = match node_indices.get(&u_value).copied() {
                Some(index) => index,
                None => {
                    let index = node_labels.len();
                    node_indices.insert(u_value, index);
                    node_labels.push(u_value.to_string());
                    node_objects.push(u.clone().unbind());
                    edge_added_node = true;
                    index
                }
            };
            let v_index = match node_indices.get(&v_value).copied() {
                Some(index) => index,
                None => {
                    let index = node_labels.len();
                    node_indices.insert(v_value, index);
                    node_labels.push(v_value.to_string());
                    node_objects.push(v.clone().unbind());
                    edge_added_node = true;
                    index
                }
            };
            if edge_added_node {
                node_bumps = node_bumps.wrapping_add(1);
            }
            edges.push((u_index, v_index, attrs));
        }

        Ok(Some((node_labels, node_objects, edges, node_bumps)))
    }

    fn add_fresh_exact_int_attr_edge_batch(
        &mut self,
        py: Python<'_>,
        node_labels: Vec<String>,
        node_objects: Vec<PyObject>,
        edges: Vec<(usize, usize, AttrMap)>,
        node_bumps: u64,
        final_edge_bump: bool,
    ) -> PyResult<()> {
        let edge_count = edges.len();
        let edge_bumps = u64::try_from(edge_count)
            .unwrap_or(u64::MAX)
            .wrapping_add(u64::from(final_edge_bump));

        let mirror_active = self.node_iter_mirror_active();
        self.node_key_map.reserve(node_labels.len());
        for (canonical, node) in node_labels.iter().zip(node_objects) {
            self.node_key_map.entry(canonical.clone()).or_insert(node);
            if mirror_active {
                self.node_iter_mirror_insert(py, canonical)?;
            }
        }

        let mut inner_edges = Vec::with_capacity(edge_count);
        for (source_idx, target_idx, attrs) in edges {
            inner_edges.push((source_idx, target_idx, attrs));
        }

        let _inserted = self
            .inner
            .extend_fresh_index_edges_with_attrs_unrecorded(node_labels, inner_edges);
        self.nodes_seq = self.nodes_seq.wrapping_add(node_bumps);
        self.edges_seq = self.edges_seq.wrapping_add(edge_bumps);
        Ok(())
    }

    fn try_add_fresh_exact_int_attr_edge_batch(
        &mut self,
        py: Python<'_>,
        ebunch_to_add: &Bound<'_, PyAny>,
        final_edge_bump: bool,
    ) -> PyResult<bool> {
        const ATTR_EDGE_BATCH_MIN: usize = 8;
        if self.inner.node_count() != 0
            || self.inner.edge_count() != 0
            || !self.node_key_map.is_empty()
            || !self.node_py_attrs.is_empty()
            || !self.edge_py_attrs.is_empty()
            || !self.succ_py_keys.is_empty()
            || !self.pred_py_keys.is_empty()
            || !self.succ_row_py.is_empty()
            || !self.pred_row_py.is_empty()
        {
            return Ok(false);
        }

        let collected = if let Ok(list) = ebunch_to_add.downcast::<PyList>() {
            if list.len() < ATTR_EDGE_BATCH_MIN {
                return Ok(false);
            }
            self.collect_fresh_exact_int_attr_edge_batch(py, list.iter(), list.len())?
        } else if let Ok(tuple) = ebunch_to_add.downcast::<PyTuple>() {
            if tuple.len() < ATTR_EDGE_BATCH_MIN {
                return Ok(false);
            }
            self.collect_fresh_exact_int_attr_edge_batch(py, tuple.iter(), tuple.len())?
        } else {
            return Ok(false);
        };

        let Some((node_labels, node_objects, edges, node_bumps)) = collected else {
            return Ok(false);
        };
        self.add_fresh_exact_int_attr_edge_batch(
            py,
            node_labels,
            node_objects,
            edges,
            node_bumps,
            final_edge_bump,
        )?;
        Ok(true)
    }

    /// br-r37-c1-dodattrbatch: every node display key is a plain int matching its
    /// canonical label, and no per-row display overrides — the precondition for
    /// resolving int edge endpoints by label.
    fn di_int_prefix_display_keys_are_plain_ints(&self, py: Python<'_>) -> bool {
        if !self.succ_py_keys.is_empty() || !self.pred_py_keys.is_empty() {
            return false;
        }
        for (canonical, obj) in &self.node_key_map {
            let bound = obj.bind(py);
            if !bound.is_exact_instance_of::<PyInt>() {
                return false;
            }
            let Ok(value) = bound.extract::<i64>() else {
                return false;
            };
            if value.to_string() != canonical.as_str() {
                return false;
            }
        }
        true
    }

    /// br-r37-c1-dodattrbatch: collect `(u, v, dict)` triples as
    /// `(source_idx, target_idx, AttrMap)` against EXISTING int-labeled nodes via
    /// a one-time int-label -> index map (one int hash per endpoint vs String
    /// hashing). Bails on any non-int node, a new (not-present) endpoint, or a
    /// non-3-tuple — those route to the slow path that owns node creation.
    fn collect_existing_int_label_attr_edge_indices<'py, I>(
        &self,
        items: I,
        len: usize,
    ) -> PyResult<Option<Vec<(usize, usize, AttrMap)>>>
    where
        I: IntoIterator<Item = Bound<'py, PyAny>>,
    {
        let nodes = self.inner.nodes_ordered();
        let mut label_to_index: HashMap<i64, usize> = HashMap::with_capacity(nodes.len());
        for (idx, name) in nodes.iter().enumerate() {
            let Ok(label) = name.parse::<i64>() else {
                return Ok(None);
            };
            label_to_index.insert(label, idx);
        }
        let mut edges = Vec::with_capacity(len);
        for item in items {
            let Ok(tuple) = item.downcast::<PyTuple>() else {
                return Ok(None);
            };
            if tuple.len() != 3 {
                return Ok(None);
            }
            let u = tuple.get_item(0)?;
            let v = tuple.get_item(1)?;
            if !u.is_exact_instance_of::<PyInt>()
                || !v.is_exact_instance_of::<PyInt>()
                || u.is_exact_instance_of::<PyBool>()
                || v.is_exact_instance_of::<PyBool>()
            {
                return Ok(None);
            }
            let Ok(u_value) = u.extract::<i64>() else {
                return Ok(None);
            };
            let Ok(v_value) = v.extract::<i64>() else {
                return Ok(None);
            };
            let Some(&u_index) = label_to_index.get(&u_value) else {
                return Ok(None);
            };
            let Some(&v_index) = label_to_index.get(&v_value) else {
                return Ok(None);
            };
            let third = tuple.get_item(2)?;
            let Ok(dict) = third.downcast::<PyDict>() else {
                return Ok(None);
            };
            let Ok(attrs) = crate::py_dict_to_attr_map(dict) else {
                return Ok(None);
            };
            if attrs
                .keys()
                .any(|key| key.starts_with("__fnx_incompatible"))
            {
                return Ok(None);
            }
            edges.push((u_index, v_index, attrs));
        }
        Ok(Some(edges))
    }

    /// br-r37-c1-dodattrbatch: fast bulk add of ATTRIBUTED int edges onto a
    /// DiGraph whose int-labeled nodes already exist with no edges yet (e.g.
    /// relabel_nodes / convert_node_labels_to_integers / from_dict_of_dicts).
    /// Attrs stay LAZY in the inner AttrMap.
    fn try_add_existing_int_label_attr_edge_batch(
        &mut self,
        py: Python<'_>,
        ebunch_to_add: &Bound<'_, PyAny>,
        final_edge_bump: bool,
    ) -> PyResult<bool> {
        const INT_LABEL_ATTR_BATCH_MIN: usize = 8;
        if self.inner.edge_count() != 0
            || !self.edge_py_attrs.is_empty()
            || !self.succ_row_py.is_empty()
            || !self.pred_row_py.is_empty()
            || !self.di_int_prefix_display_keys_are_plain_ints(py)
        {
            return Ok(false);
        }
        let edges = if let Ok(list) = ebunch_to_add.downcast::<PyList>() {
            if list.len() < INT_LABEL_ATTR_BATCH_MIN {
                return Ok(false);
            }
            self.collect_existing_int_label_attr_edge_indices(list.iter(), list.len())?
        } else if let Ok(tuple) = ebunch_to_add.downcast::<PyTuple>() {
            if tuple.len() < INT_LABEL_ATTR_BATCH_MIN {
                return Ok(false);
            }
            self.collect_existing_int_label_attr_edge_indices(tuple.iter(), tuple.len())?
        } else {
            return Ok(false);
        };
        let Some(edges) = edges else {
            return Ok(false);
        };
        let edge_bumps = u64::try_from(edges.len())
            .unwrap_or(u64::MAX)
            .wrapping_add(1);
        let _ = self
            .inner
            .extend_existing_index_edges_with_attrs_unrecorded(edges);
        if final_edge_bump {
            self.edges_seq = self.edges_seq.wrapping_add(edge_bumps);
        }
        Ok(true)
    }

    fn add_attr_edge_batch(
        &mut self,
        py: Python<'_>,
        edges: Vec<(String, String, AttrMap, Option<Py<PyDict>>)>,
        new_nodes: Vec<(String, PyObject)>,
        node_bumps: u64,
        final_edge_bump: bool,
    ) -> PyResult<()> {
        let edge_bumps = u64::try_from(edges.len())
            .unwrap_or(u64::MAX)
            .wrapping_add(u64::from(final_edge_bump));

        let mut inner_new_nodes = Vec::with_capacity(new_nodes.len());
        for (canonical, node) in new_nodes {
            inner_new_nodes.push(canonical.clone());
            self.node_key_map.entry(canonical).or_insert(node);
        }
        // Keep the node-iteration mirror live (in insertion order).
        if self.node_iter_mirror_active() {
            for c in &inner_new_nodes {
                self.node_iter_mirror_insert(py, c)?;
            }
        }
        // Match PyGraph's attributed edge batch: empty node-attribute mirrors
        // are materialized lazily by node views, so construction does not need
        // one fresh PyDict per endpoint.
        let mut inner_edges = Vec::with_capacity(edges.len());
        for (u, v, attrs, src) in edges {
            match src {
                Some(src) => match self.edge_py_attrs.entry(Self::edge_key(&u, &v)) {
                    std::collections::hash_map::Entry::Occupied(entry) => {
                        entry.get().bind(py).update(src.bind(py).as_mapping())?;
                    }
                    std::collections::hash_map::Entry::Vacant(entry) => {
                        entry.insert(src);
                    }
                },
                None => {
                    self.edge_py_attrs
                        .entry(Self::edge_key(&u, &v))
                        .or_insert_with(|| PyDict::new(py).unbind());
                }
            }
            inner_edges.push((u, v, attrs));
        }

        let _inserted = self
            .inner
            .extend_prepared_edges_with_attrs_row_staged_unrecorded(inner_new_nodes, inner_edges);
        self.nodes_seq = self.nodes_seq.wrapping_add(node_bumps);
        self.edges_seq = self.edges_seq.wrapping_add(edge_bumps);
        Ok(())
    }

    fn try_add_attr_edge_batch(
        &mut self,
        py: Python<'_>,
        ebunch_to_add: &Bound<'_, PyAny>,
        final_edge_bump: bool,
    ) -> PyResult<bool> {
        const ATTR_EDGE_BATCH_MIN: usize = 8;
        if !self.succ_row_py.is_empty() || !self.pred_row_py.is_empty() {
            return Ok(false);
        }
        if self.try_add_fresh_exact_int_attr_edge_batch(py, ebunch_to_add, final_edge_bump)? {
            return Ok(true);
        }
        // br-r37-c1-dodattrbatch: attributed edges onto a DiGraph whose int nodes
        // were pre-added (relabel / convert_node_labels / from_dict_of_dicts) —
        // the fresh path bails (node_count != 0), so resolve endpoints by int
        // label instead of the ~4x-slower String-keyed general batch.
        if self.try_add_existing_int_label_attr_edge_batch(py, ebunch_to_add, final_edge_bump)? {
            return Ok(true);
        }
        if let Ok(list) = ebunch_to_add.downcast::<PyList>() {
            if list.len() < ATTR_EDGE_BATCH_MIN {
                return Ok(false);
            }
            if let Some((edges, new_nodes, node_bumps)) =
                self.collect_attr_edge_batch(py, list.iter(), list.len())?
            {
                self.add_attr_edge_batch(py, edges, new_nodes, node_bumps, final_edge_bump)?;
                return Ok(true);
            }
        } else if let Ok(tuple) = ebunch_to_add.downcast::<PyTuple>()
            && tuple.len() >= ATTR_EDGE_BATCH_MIN
            && let Some((edges, new_nodes, node_bumps)) =
                self.collect_attr_edge_batch(py, tuple.iter(), tuple.len())?
        {
            self.add_attr_edge_batch(py, edges, new_nodes, node_bumps, final_edge_bump)?;
            return Ok(true);
        }
        Ok(false)
    }

    /// br-r37-c1-nodebatch: collect a batch of attributed nodes — a mix of
    /// plain `n` and `(n, dict)` tuples — for single-commit insertion on a
    /// FRESH DiGraph. Pure collect: NO mutation of self. Returns `Ok(None)`
    /// (caller falls back to the per-node loop, which owns every error and
    /// partial-prefix contract) on ANY item it can't replicate exactly.
    /// Directed sibling of `PyGraph::collect_attr_node_batch`.
    ///
    /// nx's unhashable-pair rule: a 2-tuple is unpacked as `(node, attrs)` only
    /// when its second element is a dict, so tuple nodes like `(0, 1)` stay nodes.
    fn collect_attr_node_batch<'py, I>(
        &self,
        py: Python<'py>,
        items: I,
        len: usize,
    ) -> PyResult<Option<DiAttrNodeBatch>>
    where
        I: IntoIterator<Item = Bound<'py, PyAny>>,
    {
        let mut nodes: Vec<(String, AttrMap, Option<Py<PyDict>>)> = Vec::with_capacity(len);
        let mut new_nodes: Vec<(String, PyObject)> = Vec::new();
        let mut seen_nodes: HashSet<String> = HashSet::new();
        let mut node_bumps = 0_u64;
        let mut batch_first: HashMap<String, PyObject> = HashMap::new();

        for item in items {
            let (node, src_dict): (Bound<'py, PyAny>, Option<Bound<'py, PyDict>>) =
                if let Ok(tuple) = item.downcast::<PyTuple>() {
                    if tuple.len() == 2 {
                        let second = tuple.get_item(1)?;
                        if let Ok(d) = second.downcast::<PyDict>() {
                            (tuple.get_item(0)?, Some(d.clone()))
                        } else {
                            (item.clone(), None)
                        }
                    } else {
                        (item.clone(), None)
                    }
                } else {
                    (item.clone(), None)
                };

            if !Self::is_plain_batch_node(&node) {
                return Ok(None);
            }

            let (rust_attrs, src) = match &src_dict {
                Some(d) => {
                    let Ok(attrs) = py_dict_to_attr_map(d) else {
                        return Ok(None);
                    };
                    if attrs.keys().any(|k| k.starts_with("__fnx_incompatible")) {
                        return Ok(None);
                    }
                    (attrs, Some(d.clone().unbind()))
                }
                None => (AttrMap::new(), None),
            };

            let Ok(canonical) = node_key_to_string(py, &node) else {
                return Ok(None);
            };
            if self.batch_display_conflict(py, &canonical, &node, &mut batch_first) {
                return Ok(None);
            }
            if seen_nodes.insert(canonical.clone()) {
                node_bumps = node_bumps.wrapping_add(1);
                new_nodes.push((canonical.clone(), node.clone().unbind()));
            }
            nodes.push((canonical, rust_attrs, src));
        }

        Ok(Some((nodes, new_nodes, node_bumps)))
    }

    /// Commit a collected attributed-node batch. PyDiGraph mirrors are EAGER
    /// (every node gets a `node_py_attrs` dict, matching `add_node`), then
    /// attributed nodes update theirs (merge for duplicate nodes), then ONE
    /// `extend_nodes_with_attrs_unrecorded` (insert-or-merge, one ledger record)
    /// and the same `nodes_seq` bump the per-node path performs.
    fn add_attr_node_batch(
        &mut self,
        py: Python<'_>,
        nodes: Vec<(String, AttrMap, Option<Py<PyDict>>)>,
        new_nodes: Vec<(String, PyObject)>,
        node_bumps: u64,
    ) -> PyResult<()> {
        let mirror_active = self.node_iter_mirror_active();
        for (canonical, node) in new_nodes {
            let mirror_key = if mirror_active {
                Some(canonical.clone())
            } else {
                None
            };
            self.node_key_map.entry(canonical.clone()).or_insert(node);
            self.node_py_attrs
                .entry(canonical)
                .or_insert_with(|| PyDict::new(py).unbind());
            if let Some(c) = mirror_key {
                self.node_iter_mirror_insert(py, &c)?;
            }
        }
        for (canonical, _, src) in &nodes {
            if let Some(src) = src {
                let bound = src.bind(py);
                if !bound.is_empty()
                    && let Some(dict) = self.node_py_attrs.get(canonical)
                {
                    dict.bind(py).update(bound.as_mapping())?;
                }
            }
        }
        let _inserted = self
            .inner
            .extend_nodes_with_attrs_unrecorded(nodes.into_iter().map(|(c, a, _)| (c, a)));
        self.nodes_seq = self.nodes_seq.wrapping_add(node_bumps);
        Ok(())
    }

    #[allow(dead_code)] // Used by directed algorithm bindings (bd-uode.3).
    pub(crate) fn new_empty(py: Python<'_>) -> PyResult<Self> {
        Self::new_empty_with_mode(py, CompatibilityMode::Strict)
    }

    pub(crate) fn new_empty_with_mode(py: Python<'_>, mode: CompatibilityMode) -> PyResult<Self> {
        Self::new_empty_with_policy(py, RuntimePolicy::new(mode))
    }

    pub(crate) fn new_empty_with_policy(
        py: Python<'_>,
        runtime_policy: RuntimePolicy,
    ) -> PyResult<Self> {
        Ok(Self {
            inner: DiGraph::with_runtime_policy(runtime_policy),
            node_key_map: HashMap::new(),
            node_py_attrs: HashMap::new(),
            edge_py_attrs: HashMap::new(),
            succ_py_keys: HashMap::new(), // br-r37-c1-z6uka
            pred_py_keys: HashMap::new(), // br-r37-c1-z6uka
            succ_row_py: HashMap::new(),
            pred_row_py: HashMap::new(),
            graph_attrs: PyDict::new(py).unbind(),
            nodes_seq: 0,
            edges_seq: 0,
            edges_dirty: AtomicBool::new(false),
            node_keys_cache: std::sync::Mutex::new(None),
            node_data_mirror: std::sync::Mutex::new(None),
            dict_of_dicts_cache: None,
            edges_with_data_cache: None,
            in_edges_with_data_cache: None,
            edges_attr_dicts_cache: None,
            node_iter_mirror: std::sync::Mutex::new(None),
        })
    }

    /// br-r37-c1-39d82: see PyGraph::bump_nodes_seq.
    #[inline]
    pub(crate) fn bump_nodes_seq(&mut self) {
        self.nodes_seq = self.nodes_seq.wrapping_add(1);
    }

    /// br-r37-c1-jft0i: see PyGraph::bump_edges_seq.
    #[inline]
    pub(crate) fn bump_edges_seq(&mut self) {
        self.edges_seq = self.edges_seq.wrapping_add(1);
    }

    #[inline]
    pub(crate) fn mark_edges_dirty(&self) {
        self.edges_dirty.store(true, Ordering::Relaxed);
    }

    fn materialize_edge_py_attrs(&mut self, py: Python<'_>, u: &str, v: &str) -> Py<PyDict> {
        let key = Self::edge_key(u, v);
        if let Some(attrs) = self.edge_py_attrs.get(&key) {
            return attrs.clone_ref(py);
        }
        let attrs = self
            .inner
            .edge_attrs(u, v)
            .map_or_else(
                || Ok(PyDict::new(py).unbind()),
                |attrs| attr_map_to_pydict(py, attrs),
            )
            .expect("stored directed edge attrs must convert to Python");
        self.edge_py_attrs.insert(key.clone(), attrs);
        self.edge_py_attrs
            .get(&key)
            .expect("just inserted directed edge attrs")
            .clone_ref(py)
    }

    pub(crate) fn edge_attr_py_value(
        &self,
        py: Python<'_>,
        source: &str,
        target: &str,
        attr: &str,
    ) -> PyResult<Option<PyObject>> {
        let key = Self::edge_key(source, target);
        if let Some(dict) = self.edge_py_attrs.get(&key) {
            return Ok(dict.bind(py).get_item(attr)?.map(|value| value.unbind()));
        }
        match self
            .inner
            .edge_attrs(source, target)
            .and_then(|attrs| attrs.get(attr))
        {
            Some(value) => Ok(Some(crate::cgse_value_to_py(py, value)?)),
            None => Ok(None),
        }
    }

    fn edge_attr_value_or_default(
        &mut self,
        py: Python<'_>,
        source: &str,
        target: &str,
        data: &Bound<'_, PyAny>,
        default: &PyObject,
    ) -> PyResult<PyObject> {
        if self.edge_py_attrs.is_empty()
            && let Ok(attr_name) = data.downcast::<PyString>()
        {
            let attr_name = attr_name.to_str()?;
            if let Some(value) = self
                .inner
                .edge_attrs(source, target)
                .and_then(|attrs| attrs.get(attr_name))
                .cloned()
            {
                if !matches!(value, CgseValue::Map(_)) {
                    return crate::cgse_value_to_py(py, &value);
                }
            } else {
                return Ok(default.clone_ref(py));
            }
        }

        let key = Self::edge_key(source, target);
        if let Some(dict) = self.edge_py_attrs.get(&key) {
            return Ok(dict
                .bind(py)
                .get_item(data)?
                .map_or_else(|| default.clone_ref(py), |value| value.unbind()));
        }

        if let Ok(attr_name) = data.downcast::<PyString>() {
            let attr_name = attr_name.to_str()?;
            if let Some(value) = self
                .inner
                .edge_attrs(source, target)
                .and_then(|attrs| attrs.get(attr_name))
                .cloned()
            {
                if matches!(value, CgseValue::Map(_)) {
                    let attrs = self.materialize_edge_py_attrs(py, source, target);
                    return Ok(attrs
                        .bind(py)
                        .get_item(data)?
                        .map_or_else(|| default.clone_ref(py), |value| value.unbind()));
                }
                return crate::cgse_value_to_py(py, &value);
            }
        }

        Ok(default.clone_ref(py))
    }

    fn cached_succ_set_edge(&mut self, py: Python<'_>, owner: &str, nbr: &str) -> PyResult<()> {
        let Some(row) = self.succ_row_py.get(owner).map(|row| row.clone_ref(py)) else {
            return Ok(());
        };
        let py_nbr = self.py_succ_key(py, owner, nbr);
        let attrs = self.materialize_edge_py_attrs(py, owner, nbr);
        row.bind(py).set_item(py_nbr, attrs.bind(py))?;
        Ok(())
    }

    fn cached_pred_set_edge(&mut self, py: Python<'_>, owner: &str, nbr: &str) -> PyResult<()> {
        let Some(row) = self.pred_row_py.get(owner).map(|row| row.clone_ref(py)) else {
            return Ok(());
        };
        let py_nbr = self.py_pred_key(py, owner, nbr);
        let attrs = self.materialize_edge_py_attrs(py, nbr, owner);
        row.bind(py).set_item(py_nbr, attrs.bind(py))?;
        Ok(())
    }

    fn cached_succ_remove_key(&self, py: Python<'_>, owner: &str, nbr: &str) {
        if let Some(row) = self.succ_row_py.get(owner) {
            let py_nbr = self.py_succ_key(py, owner, nbr);
            let _ = row.bind(py).del_item(py_nbr);
        }
    }

    fn cached_pred_remove_key(&self, py: Python<'_>, owner: &str, nbr: &str) {
        if let Some(row) = self.pred_row_py.get(owner) {
            let py_nbr = self.py_pred_key(py, owner, nbr);
            let _ = row.bind(py).del_item(py_nbr);
        }
    }

    fn cached_directed_clear_edges_in_place(&self, py: Python<'_>) -> PyResult<()> {
        for row in self.succ_row_py.values() {
            row.bind(py).call_method0("clear")?;
        }
        for row in self.pred_row_py.values() {
            row.bind(py).call_method0("clear")?;
        }
        Ok(())
    }

    fn successor_row_dict_by_canonical(
        &mut self,
        py: Python<'_>,
        canonical: &str,
    ) -> PyResult<Py<PyDict>> {
        if let Some(row) = self.succ_row_py.get(canonical) {
            return Ok(row.clone_ref(py));
        }
        let row = PyDict::new(py);
        let neighbors: Vec<String> = self
            .inner
            .successors(canonical)
            .unwrap_or_default()
            .into_iter()
            .map(str::to_owned)
            .collect();
        if !neighbors.is_empty() {
            self.mark_edges_dirty();
        }
        for neighbor in neighbors {
            let py_neighbor = self.py_succ_key(py, canonical, &neighbor);
            let attrs = self.materialize_edge_py_attrs(py, canonical, &neighbor);
            row.set_item(py_neighbor, attrs.bind(py))?;
        }
        let row = row.unbind();
        self.succ_row_py
            .insert(canonical.to_owned(), row.clone_ref(py));
        Ok(row)
    }

    fn predecessor_row_dict_by_canonical(
        &mut self,
        py: Python<'_>,
        canonical: &str,
    ) -> PyResult<Py<PyDict>> {
        if let Some(row) = self.pred_row_py.get(canonical) {
            return Ok(row.clone_ref(py));
        }
        let row = PyDict::new(py);
        let neighbors: Vec<String> = self
            .inner
            .predecessors(canonical)
            .unwrap_or_default()
            .into_iter()
            .map(str::to_owned)
            .collect();
        if !neighbors.is_empty() {
            self.mark_edges_dirty();
        }
        for neighbor in neighbors {
            let py_neighbor = self.py_pred_key(py, canonical, &neighbor);
            let attrs = self.materialize_edge_py_attrs(py, &neighbor, canonical);
            row.set_item(py_neighbor, attrs.bind(py))?;
        }
        let row = row.unbind();
        self.pred_row_py
            .insert(canonical.to_owned(), row.clone_ref(py));
        Ok(row)
    }
}

type DiEdgeBatch = (Vec<(String, String)>, Vec<(String, PyObject)>, u64);
type DiAttrEdgeBatch = (
    Vec<(String, String, AttrMap, Option<Py<PyDict>>)>,
    Vec<(String, PyObject)>,
    u64,
);
type DiIndexedAttrEdgeBatch = (
    Vec<String>,
    Vec<PyObject>,
    Vec<(usize, usize, AttrMap)>,
    u64,
);
type MultiDiIndexedAttrEdgeBatch = (
    Vec<String>,
    Vec<PyObject>,
    Vec<(usize, usize, usize, AttrMap, Py<PyDict>)>,
    u64,
);

/// br-r37-c1-nodebatch: collected attributed-node batch for PyDiGraph —
/// (nodes, new_nodes, node_bumps); each node carries its converted `AttrMap`
/// plus the source `PyDict` for the eager mirror update.
type DiAttrNodeBatch = (
    Vec<(String, AttrMap, Option<Py<PyDict>>)>,
    Vec<(String, PyObject)>,
    u64,
);

#[pymethods]
impl PyDiGraph {
    /// br-r37-c1-natdiffsimple-di: fully-native `difference(G, H)` for simple
    /// `DiGraph` (the directed sibling of `PyGraph::_native_difference`). Builds
    /// the result entirely in Rust in G's integer index space: H's directed edges
    /// are hashed into a `HashSet<(usize, usize)>` of G-index pairs (no min/max —
    /// orientation matters), G is walked via `successors_indices` in node-major
    /// `edges()` order, and kept edges (absent from H) go straight onto the fresh
    /// result. Node display keys come from copying `node_key_map` (never per-node
    /// `py_node_key`). Skips the Python `create_empty_copy` + EdgeView set +
    /// `add_edges_from` round-trip (~1.36x nx). Returns `None` (wrapper falls back)
    /// when either graph carries z6uka succ/pred display overrides, or when an H
    /// node is somehow absent from G (the wrapper already enforces equal sets).
    fn _native_difference(
        slf: PyRef<'_, Self>,
        py: Python<'_>,
        h: &Bound<'_, PyAny>,
    ) -> PyResult<Option<Py<Self>>> {
        let Ok(h_ref) = h.extract::<PyRef<'_, Self>>() else {
            return Ok(None);
        };
        let g = &*slf;
        let hh = &*h_ref;
        if !g.succ_py_keys.is_empty()
            || !g.pred_py_keys.is_empty()
            || !hh.succ_py_keys.is_empty()
            || !hh.pred_py_keys.is_empty()
        {
            return Ok(None);
        }

        // Work in G's integer index space — no String alloc in the hot loops.
        let g_nodes: Vec<&str> = g.inner.nodes_ordered();
        let g_index: HashMap<&str, usize> =
            g_nodes.iter().enumerate().map(|(i, &n)| (n, i)).collect();

        // H's directed edge set as (source_idx, target_idx) G-index pairs.
        let mut h_set: std::collections::HashSet<(usize, usize)> = std::collections::HashSet::new();
        for u in hh.inner.nodes_ordered() {
            let Some(&ui) = g_index.get(u) else {
                return Ok(None);
            };
            for v in hh.inner.successors(u).unwrap_or_default() {
                let Some(&vi) = g_index.get(v) else {
                    return Ok(None);
                };
                h_set.insert((ui, vi));
            }
        }

        let mut r = Self::new_empty_with_mode(py, g.inner.mode())?;
        // Copy ONLY G's materialized node objects; never call py_node_key per node.
        for (canonical, obj) in &g.node_key_map {
            r.node_key_map.insert(canonical.clone(), obj.clone_ref(py));
        }
        let _ = r.inner.extend_nodes_with_attrs_unrecorded(
            g_nodes
                .iter()
                .map(|n| ((*n).to_owned(), fnx_classes::AttrMap::new())),
        );

        // G's directed edges in node-major `edges()` order (each appears once in
        // its source's out-row), kept when absent from H. Orientation preserved.
        let mut edges: Vec<(String, String, fnx_classes::AttrMap)> = Vec::new();
        for (ui, &u) in g_nodes.iter().enumerate() {
            let Some(succ) = g.inner.successors_indices(ui) else {
                continue;
            };
            for &vi in succ {
                if !h_set.contains(&(ui, vi)) {
                    edges.push((
                        u.to_owned(),
                        g_nodes[vi].to_owned(),
                        fnx_classes::AttrMap::new(),
                    ));
                }
            }
        }
        let n_edges = edges.len();
        let node_count = g_nodes.len();
        let _ = r.inner.extend_edges_with_attrs_unrecorded(edges);
        r.nodes_seq = u64::try_from(node_count).unwrap_or(u64::MAX);
        r.edges_seq = u64::try_from(n_edges).unwrap_or(u64::MAX);
        Py::new(py, r).map(Some)
    }

    /// br-r37-c1-natsymdiff-di: fully-native `symmetric_difference(G, H)` for
    /// simple `DiGraph` (directed sibling of `PyGraph::_native_symmetric_difference`).
    /// Two passes in G's integer index space: G-only directed edges (G node-major
    /// order) then H-only directed edges (H node-major order) — exactly the Python
    /// wrapper's order. Node display keys come from G (`create_empty_copy(G)`
    /// semantics). Returns `None` on z6uka succ/pred overrides or if a node is
    /// missing from G (wrapper enforces equal node sets).
    fn _native_symmetric_difference(
        slf: PyRef<'_, Self>,
        py: Python<'_>,
        h: &Bound<'_, PyAny>,
    ) -> PyResult<Option<Py<Self>>> {
        let Ok(h_ref) = h.extract::<PyRef<'_, Self>>() else {
            return Ok(None);
        };
        let g = &*slf;
        let hh = &*h_ref;
        if !g.succ_py_keys.is_empty()
            || !g.pred_py_keys.is_empty()
            || !hh.succ_py_keys.is_empty()
            || !hh.pred_py_keys.is_empty()
        {
            return Ok(None);
        }

        // Common index space = G's node order (= result node order).
        let g_nodes: Vec<&str> = g.inner.nodes_ordered();
        let g_index: HashMap<&str, usize> =
            g_nodes.iter().enumerate().map(|(i, &n)| (n, i)).collect();

        // G's and H's directed edge sets as (src_idx, tgt_idx) G-index pairs.
        let mut g_set: std::collections::HashSet<(usize, usize)> = std::collections::HashSet::new();
        for (ui, _u) in g_nodes.iter().enumerate() {
            if let Some(succ) = g.inner.successors_indices(ui) {
                for &vi in succ {
                    g_set.insert((ui, vi));
                }
            }
        }
        let mut h_set: std::collections::HashSet<(usize, usize)> = std::collections::HashSet::new();
        let h_nodes: Vec<&str> = hh.inner.nodes_ordered();
        for u in &h_nodes {
            let Some(&ui) = g_index.get(*u) else {
                return Ok(None);
            };
            for v in hh.inner.successors(u).unwrap_or_default() {
                let Some(&vi) = g_index.get(v) else {
                    return Ok(None);
                };
                h_set.insert((ui, vi));
            }
        }

        let mut r = Self::new_empty_with_mode(py, g.inner.mode())?;
        for (canonical, obj) in &g.node_key_map {
            r.node_key_map.insert(canonical.clone(), obj.clone_ref(py));
        }
        let _ = r.inner.extend_nodes_with_attrs_unrecorded(
            g_nodes
                .iter()
                .map(|n| ((*n).to_owned(), fnx_classes::AttrMap::new())),
        );

        // Pass 1: G-only edges (absent from H), G node-major order.
        let mut edges: Vec<(String, String, fnx_classes::AttrMap)> = Vec::new();
        for (ui, &u) in g_nodes.iter().enumerate() {
            if let Some(succ) = g.inner.successors_indices(ui) {
                for &vi in succ {
                    if !h_set.contains(&(ui, vi)) {
                        edges.push((
                            u.to_owned(),
                            g_nodes[vi].to_owned(),
                            fnx_classes::AttrMap::new(),
                        ));
                    }
                }
            }
        }
        // Pass 2: H-only edges (absent from G), H node-major order.
        for u in &h_nodes {
            let ui = g_index[*u];
            for v in hh.inner.successors(u).unwrap_or_default() {
                let vi = g_index[v];
                if !g_set.contains(&(ui, vi)) {
                    edges.push(((*u).to_owned(), v.to_owned(), fnx_classes::AttrMap::new()));
                }
            }
        }
        let n_edges = edges.len();
        let node_count = g_nodes.len();
        let _ = r.inner.extend_edges_with_attrs_unrecorded(edges);
        r.nodes_seq = u64::try_from(node_count).unwrap_or(u64::MAX);
        r.edges_seq = u64::try_from(n_edges).unwrap_or(u64::MAX);
        Py::new(py, r).map(Some)
    }

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

        let mut g = Self::new_empty_with_mode(py, CompatibilityMode::Strict)?;
        g.graph_attrs = graph_attrs.unbind();

        if let Some(data) = incoming_graph_data {
            // br-r37-c1-ymeml: see crate::fnx_graph_instance_mode — __init__
            // owns population for graph-instance inputs; absorb skipped.
            if let Some(mode) = crate::fnx_graph_instance_mode(data) {
                g.inner = DiGraph::new(mode);
                return Ok(g);
            }
            // Copy from another PyDiGraph.
            if let Ok(other) = data.extract::<PyRef<'_, PyDiGraph>>() {
                g.inner = DiGraph::with_runtime_policy(other.inner.runtime_policy().clone());
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
            }
            // Copy from undirected PyGraph — create both directions.
            else if let Ok(other) = data.extract::<PyRef<'_, PyGraph>>() {
                for canonical in other.inner.nodes_ordered() {
                    g.inner.add_node(canonical.to_owned());
                    g.node_key_map
                        .insert(canonical.to_owned(), other.py_node_key(py, canonical));
                    if let Some(attrs) = other.node_py_attrs.get(canonical) {
                        g.node_py_attrs
                            .insert(canonical.to_owned(), attrs.bind(py).copy()?.unbind());
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
            } else if g.try_add_plain_edge_batch(py, data, false)?
                || g.try_add_attr_edge_batch(py, data, false)?
            {
            } else if let Ok(iter) = PyIterator::from_object(data) {
                // br-r37-c1-d58s8 ctor lever 2 (directed twin): batch the
                // edge-tuple stream through ONE
                // extend_edges_with_attrs_unrecorded call, replicating
                // add_edge's display semantics inline (as-passed node
                // keys, z6uka succ/pred row objects on new cells, LAZY
                // mirrors — attr-ful edges only, C-level update merge).
                // Pending-state sets stand in for has_node/has_edge until
                // the flush; slow items flush-then-fallback verbatim.
                let mut edge_batch: Vec<(String, String, fnx_classes::AttrMap)> = Vec::new();
                // br-r37-c1-d58s8: node_key_map doubles as the pending-node
                // oracle; no separate pending set (see PyGraph::new).
                let mut pending_cells: std::collections::HashSet<(String, String)> =
                    std::collections::HashSet::new();
                macro_rules! flush_batch {
                    () => {
                        if !edge_batch.is_empty() {
                            let drained: Vec<(String, String, fnx_classes::AttrMap)> =
                                std::mem::take(&mut edge_batch);
                            let _ = g.inner.extend_edges_with_attrs_unrecorded(drained);
                            pending_cells.clear();
                            g.bump_nodes_seq();
                            g.bump_edges_seq();
                        }
                    };
                }
                for item in iter {
                    let item = item?;
                    let mut batched = false;
                    if let Ok(tuple) = item.downcast::<PyTuple>() {
                        let tuple_len = tuple.len();
                        if tuple_len == 2 || tuple_len == 3 {
                            let dict3 = if tuple_len == 3 {
                                tuple.get_item(2)?.downcast::<PyDict>().ok().cloned()
                            } else {
                                None
                            };
                            if tuple_len == 2 || dict3.is_some() {
                                let u = tuple.get_item(0)?;
                                let v = tuple.get_item(1)?;
                                if let (Ok(u_canonical), Ok(v_canonical)) =
                                    (node_key_to_string(py, &u), node_key_to_string(py, &v))
                                {
                                    g.node_key_map
                                        .entry(u_canonical.clone())
                                        .or_insert_with(|| u.clone().unbind());
                                    g.node_key_map
                                        .entry(v_canonical.clone())
                                        .or_insert_with(|| v.clone().unbind());
                                    let cell = (u_canonical.clone(), v_canonical.clone());
                                    if !g.inner.has_edge(&u_canonical, &v_canonical)
                                        && !pending_cells.contains(&cell)
                                    {
                                        g.maybe_store_row_keys(
                                            py,
                                            &u_canonical,
                                            &v_canonical,
                                            &u,
                                            &v,
                                        );
                                        pending_cells.insert(cell);
                                    }
                                    let mut rust_attrs = fnx_classes::AttrMap::new();
                                    if let Some(d) = &dict3
                                        && !d.is_empty()
                                    {
                                        rust_attrs = py_dict_to_attr_map(d)?;
                                        let ek = Self::edge_key(&u_canonical, &v_canonical);
                                        g.edge_py_attrs
                                            .entry(ek)
                                            .or_insert_with(|| PyDict::new(py).unbind())
                                            .bind(py)
                                            .update(d.as_mapping())?;
                                    }
                                    edge_batch.push((u_canonical, v_canonical, rust_attrs));
                                    batched = true;
                                }
                            }
                        }
                    }
                    if batched {
                        continue;
                    }
                    flush_batch!();
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
                flush_batch!();
            }
        }

        if let Some(a) = attr {
            g.graph_attrs.bind(py).update(a.as_mapping())?;
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

    /// All node display objects in ONE PyO3 call (br-r37-c1-cijlm). Mirrors the
    /// simple-graph binding (lib.rs): Python ``set(graph)`` crosses the PyO3
    /// boundary per node (~2x nx on node-set construction), and ``set(graph.adj)``
    /// re-materialises every AdjacencyView row; building the Vec in Rust lets
    /// callers like ``non_neighbors`` enumerate every node in one crossing.
    /// Order = node insertion order (``nodes_ordered``).
    fn _native_node_keys(&self, py: Python<'_>) -> PyObject {
        let seq = self.nodes_seq;
        {
            let guard = self.node_keys_cache.lock().unwrap();
            if let Some((cached_seq, tup)) = guard.as_ref()
                && *cached_seq == seq
            {
                return tup.clone_ref(py).into_any();
            }
        }
        let keys: Vec<PyObject> = self
            .inner
            .nodes_ordered()
            .into_iter()
            .map(|n| self.py_node_key(py, n))
            .collect();
        let tup = pyo3::types::PyTuple::new(py, keys)
            .expect("node-keys tuple")
            .unbind();
        *self.node_keys_cache.lock().unwrap() = Some((seq, tup.clone_ref(py)));
        tup.into_any()
    }

    /// Monotonic node-mutation counter (br-r37-c1-39d82 / jft0i).
    /// Exposed to Python so view-materialization caches can key on
    /// ``(nodes_seq, edges_seq)`` without scanning for changes.
    #[getter]
    fn nodes_seq(&self) -> u64 {
        self.nodes_seq
    }

    /// Monotonic edge-mutation counter (br-r37-c1-jft0i).
    #[getter]
    fn edges_seq(&self) -> u64 {
        self.edges_seq
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
                for (source, target, _) in self.inner.edges_ordered_borrowed() {
                    let ek = Self::edge_key(source, target);
                    match self
                        .edge_py_attrs
                        .get(&ek)
                        .and_then(|dict| dict.bind(py).get_item(attr).ok().flatten())
                    {
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

    // br-r37-c1-addnoden: the node param must be named like nx's public
    // ``add_node(node_for_adding, **attr)`` — a bare ``n`` collides with
    // a node attribute literally keyed "n" (e.g. read_graphml of a graph
    // with an 'n' attr: add_node(node, n=7) -> "multiple values for n").
    // nx has the same collision only for an attr keyed "node_for_adding",
    // so matching the name gives exact drop-in parity.
    #[pyo3(signature = (node_for_adding, **attr))]
    fn add_node(
        &mut self,
        py: Python<'_>,
        node_for_adding: &Bound<'_, PyAny>,
        attr: Option<&Bound<'_, PyDict>>,
    ) -> PyResult<()> {
        let canonical = node_key_to_string(py, node_for_adding)?;
        // br-r37-c1-firstwins: nx uses dicts for node storage, so the
        // FIRST Python object added under a given canonical key wins
        // (subsequent ``add_node`` calls with hash-equivalent keys are
        // no-ops at the storage level — the original Py object is
        // preserved for ``list(G.nodes())`` and friends). Use
        // ``entry().or_insert_with`` here so re-adding ``0.0`` after
        // ``0`` doesn't overwrite the displayed Py form.
        self.node_key_map
            .entry(canonical.clone())
            .or_insert_with(|| node_for_adding.clone().unbind());

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

        self.node_iter_mirror_insert(py, &canonical)?;
        self.inner.add_node_with_attrs(canonical, rust_attrs);
        self.bump_nodes_seq();
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
        self.bump_nodes_seq();
        Ok(())
    }

    fn remove_node(&mut self, py: Python<'_>, n: &Bound<'_, PyAny>) -> PyResult<()> {
        let canonical = node_key_to_string(py, n)?;
        if !self.inner.has_node(&canonical) {
            return Err(crate::NetworkXError::new_err(format!(
                "The node {} is not in the graph.",
                n.repr()?
            )));
        }

        // surgically remove attributes for incident edges before removing node from inner graph
        let mut had_incident_edges = false;
        if let Some(succs) = self.inner.successors(&canonical) {
            for v in succs {
                let ek = Self::edge_key(&canonical, v);
                self.edge_py_attrs.remove(&ek);
                self.cached_pred_remove_key(py, v, &canonical);
                had_incident_edges = true;
            }
        }
        if let Some(preds) = self.inner.predecessors(&canonical) {
            for u in preds {
                let ek = Self::edge_key(u, &canonical);
                self.edge_py_attrs.remove(&ek);
                self.cached_succ_remove_key(py, u, &canonical);
                had_incident_edges = true;
            }
        }

        if self.node_iter_mirror_active() {
            // Remove from the live mirror while node_key_map still holds the
            // display object (mirror keys are the display py objects).
            let py_key = self.py_node_key(py, &canonical);
            self.node_iter_mirror_remove_key(py, py_key.bind(py));
        }
        self.inner.remove_node(&canonical);
        self.node_key_map.remove(&canonical);
        self.node_py_attrs.remove(&canonical);
        self.succ_row_py.remove(&canonical);
        self.pred_row_py.remove(&canonical);
        if !self.succ_py_keys.is_empty() || !self.pred_py_keys.is_empty() {
            // br-r37-c1-z6uka: drop row overrides touching the removed node.
            self.succ_py_keys
                .retain(|(a, b), _| a != &canonical && b != &canonical);
            self.pred_py_keys
                .retain(|(a, b), _| a != &canonical && b != &canonical);
        }
        self.bump_nodes_seq();
        // br-r37-c1-jft0i: removing a node with incident edges also mutates the
        // edge set, so bump edges_seq to invalidate edge-keyed caches.
        if had_incident_edges {
            self.bump_edges_seq();
        }
        Ok(())
    }

    fn _native_fill_weighted_int_edges(
        &mut self,
        py: Python<'_>,
        node_count: usize,
        rows: &Bound<'_, PyAny>,
        cols: &Bound<'_, PyAny>,
        values: &Bound<'_, PyAny>,
        edge_attr: &str,
    ) -> PyResult<bool> {
        if edge_attr.starts_with("__fnx_incompatible")
            || self.inner.node_count() != 0
            || self.inner.edge_count() != 0
            || !self.node_key_map.is_empty()
            || !self.node_py_attrs.is_empty()
            || !self.edge_py_attrs.is_empty()
            || !self.succ_py_keys.is_empty()
            || !self.pred_py_keys.is_empty()
            || !self.succ_row_py.is_empty()
            || !self.pred_row_py.is_empty()
        {
            return Ok(false);
        }

        let edges = collect_index_weight_attr_edges(rows, cols, values, node_count, edge_attr)?;
        let edge_bumps = u64::try_from(edges.len())
            .unwrap_or(u64::MAX)
            .wrapping_add(1);
        let node_bumps = u64::try_from(node_count).unwrap_or(u64::MAX);
        let node_labels: Vec<String> = (0..node_count).map(|node| node.to_string()).collect();
        let mirror_active = self.node_iter_mirror_active();

        for (index, canonical) in node_labels.iter().enumerate() {
            let py_node = unwrap_infallible((index as i64).into_pyobject(py))
                .into_any()
                .unbind();
            self.node_key_map.insert(canonical.clone(), py_node);
            if mirror_active {
                self.node_iter_mirror_insert(py, canonical)?;
            }
        }
        let _ = self
            .inner
            .extend_fresh_index_edges_with_attrs_unrecorded(node_labels, edges);
        self.nodes_seq = self.nodes_seq.wrapping_add(node_bumps);
        self.edges_seq = self.edges_seq.wrapping_add(edge_bumps);
        Ok(true)
    }

    fn remove_nodes_from(&mut self, py: Python<'_>, nodes: &Bound<'_, PyAny>) -> PyResult<()> {
        let iter = PyIterator::from_object(nodes)?;
        let mut present = HashSet::<String>::new();
        for item in iter {
            let item = item?;
            let canonical = node_key_to_string(py, &item)?;
            if self.inner.has_node(&canonical) {
                present.insert(canonical);
            }
        }
        let present_refs: HashSet<&str> = present.iter().map(String::as_str).collect();
        let mut removed_py_edge_attrs = false;
        self.edge_py_attrs.retain(|(source, target), _| {
            let keep =
                !present_refs.contains(source.as_str()) && !present_refs.contains(target.as_str());
            if !keep {
                removed_py_edge_attrs = true;
            }
            keep
        });
        let (_removed_nodes, removed_edges) =
            self.inner.remove_nodes_from(present_refs.iter().copied());
        if self.node_iter_mirror_active() {
            // Remove from the live mirror while node_key_map still holds the
            // display objects (mirror keys are the display py objects).
            for canonical in &present {
                let py_key = self.py_node_key(py, canonical);
                self.node_iter_mirror_remove_key(py, py_key.bind(py));
            }
        }
        for canonical in &present {
            self.node_key_map.remove(canonical);
            self.node_py_attrs.remove(canonical);
        }
        if !self.succ_py_keys.is_empty() || !self.pred_py_keys.is_empty() {
            // br-r37-c1-z6uka: drop row overrides touching removed nodes.
            self.succ_py_keys
                .retain(|(a, b), _| !present.contains(a) && !present.contains(b));
            self.pred_py_keys
                .retain(|(a, b), _| !present.contains(a) && !present.contains(b));
        }
        for canonical in &present {
            self.succ_row_py.remove(canonical);
            self.pred_row_py.remove(canonical);
        }
        for (owner, row) in &self.succ_row_py {
            for canonical in &present {
                let py_node = self.py_succ_key(py, owner, canonical);
                let _ = row.bind(py).del_item(py_node);
            }
        }
        for (owner, row) in &self.pred_row_py {
            for canonical in &present {
                let py_node = self.py_pred_key(py, owner, canonical);
                let _ = row.bind(py).del_item(py_node);
            }
        }
        self.bump_nodes_seq();
        if removed_edges > 0 || removed_py_edge_attrs {
            self.bump_edges_seq(); // br-r37-c1-jft0i
        }
        Ok(())
    }

    // ---- Edge mutation ----

    // br-r37-c1-addnoden follow-up: nx names these u_of_edge/v_of_edge;
    // a bare u/v collides with an edge attr keyed 'u' or 'v'
    // (add_edge(0, 1, u=5)). Match nx's names; alias to u/v for the body.
    #[pyo3(signature = (u_of_edge, v_of_edge, **attr))]
    fn add_edge(
        &mut self,
        py: Python<'_>,
        u_of_edge: &Bound<'_, PyAny>,
        v_of_edge: &Bound<'_, PyAny>,
        attr: Option<&Bound<'_, PyDict>>,
    ) -> PyResult<()> {
        let u = u_of_edge;
        let v = v_of_edge;
        let u_canonical = node_key_to_string(py, u)?;
        let v_canonical = node_key_to_string(py, v)?;

        // br-r37-c1-39d82: track new-node creation to bump
        // nodes_seq for iterator staleness detection.
        let u_was_new = !self.node_key_map.contains_key(&u_canonical);
        let v_was_new = !self.node_key_map.contains_key(&v_canonical);
        let __was_new = u_was_new || v_was_new;

        self.node_key_map
            .entry(u_canonical.clone())
            .or_insert_with(|| u.clone().unbind());
        self.node_key_map
            .entry(v_canonical.clone())
            .or_insert_with(|| v.clone().unbind());
        if __was_new {
            self.bump_nodes_seq();
        }
        // br-r37-c1-z6uka: NEW directed edges record per-row display
        // objects (succ gets v, pred gets u).
        if !self.inner.has_edge(&u_canonical, &v_canonical) {
            self.maybe_store_row_keys(py, &u_canonical, &v_canonical, u, v);
        }
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
            rust_attrs = py_dict_to_attr_map(a)?;
            for (k, val) in a.iter() {
                py_dict.bind(py).set_item(k, val)?;
            }
        }

        self.inner
            .add_edge_with_attrs(u_canonical.clone(), v_canonical.clone(), rust_attrs)
            .map_err(|e| NetworkXError::new_err(e.to_string()))?;
        // Keep the node-iteration mirror live (nx order: u before v).
        if (u_was_new || v_was_new) && self.node_iter_mirror_active() {
            if u_was_new {
                self.node_iter_mirror_insert(py, &u_canonical)?;
            }
            if v_was_new {
                self.node_iter_mirror_insert(py, &v_canonical)?;
            }
        }
        if !self.succ_row_py.is_empty() {
            self.cached_succ_set_edge(py, &u_canonical, &v_canonical)?;
        }
        if !self.pred_row_py.is_empty() {
            self.cached_pred_set_edge(py, &v_canonical, &u_canonical)?;
        }
        // br-r37-c1-jft0i: bump edges_seq so view-materialization caches invalidate.
        self.bump_edges_seq();
        Ok(())
    }

    #[pyo3(signature = (ebunch_to_add, **attr))]
    fn add_edges_from(
        &mut self,
        py: Python<'_>,
        ebunch_to_add: &Bound<'_, PyAny>,
        attr: Option<&Bound<'_, PyDict>>,
    ) -> PyResult<()> {
        let has_global_attr = attr.is_some_and(|a| !a.is_empty());
        if !has_global_attr && self.try_add_plain_edge_batch(py, ebunch_to_add, true)? {
            return Ok(());
        }
        if !has_global_attr && self.try_add_attr_edge_batch(py, ebunch_to_add, true)? {
            return Ok(());
        }
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
                // br-edges3rd: match nx — non-dict third element triggers
                // a TypeError via dict.update's iteration (e.g.
                // ``'float' object is not iterable``). Previously fnx
                // silently dropped non-dict thirds.
                if let Ok(dict_arg) = d.downcast::<PyDict>() {
                    merged.update(dict_arg.as_mapping())?;
                } else {
                    // br-r37-c1-baqyi: nx creates BOTH endpoint nodes
                    // before ``datadict.update(dd)`` raises (its
                    // add_edges_from inserts u and v into _succ/_pred
                    // first), so the partial error state keeps them.
                    // PyGraph has carried this since br-edges3rd; the
                    // DiGraph path never got it.
                    self.add_node(py, &u, None)?;
                    self.add_node(py, &v, None)?;
                    let throwaway = PyDict::new(py);
                    throwaway.call_method1("update", (d,))?;
                    merged.update(throwaway.as_mapping())?;
                }
            }
            self.add_edge(py, &u, &v, Some(&merged))?;
        }
        self.bump_edges_seq();
        Ok(())
    }

    fn _try_add_edges_from_batch(
        &mut self,
        py: Python<'_>,
        ebunch_to_add: &Bound<'_, PyAny>,
    ) -> PyResult<bool> {
        if self.try_add_plain_edge_batch(py, ebunch_to_add, true)? {
            return Ok(true);
        }
        if self.try_add_attr_edge_batch(py, ebunch_to_add, true)? {
            return Ok(true);
        }
        Ok(false)
    }

    /// br-r37-c1-nodebatch: native attributed-node batch for
    /// `add_nodes_from([(n, dict), ...])` (mixed with plain `n`) on a FRESH
    /// DiGraph — the directed sibling of `PyGraph::_try_add_nodes_from_batch`.
    /// The per-node Python loop pays ~4.5x nx on attributed bulk construction.
    /// Returns `false` (NO mutation) for anything outside this shape so the
    /// per-node loop owns every error and partial-prefix contract.
    fn _try_add_nodes_from_batch(
        &mut self,
        py: Python<'_>,
        nodes_to_add: &Bound<'_, PyAny>,
    ) -> PyResult<bool> {
        const NODE_BATCH_MIN: usize = 8;
        // FRESH gate: no existing nodes/edges/row-display mirrors, so a batch
        // never has to merge into pre-existing storage (appends fall through).
        if self.inner.node_count() != 0
            || self.inner.edge_count() != 0
            || !self.succ_row_py.is_empty()
            || !self.pred_row_py.is_empty()
        {
            return Ok(false);
        }
        if let Ok(list) = nodes_to_add.downcast::<PyList>() {
            if list.len() < NODE_BATCH_MIN {
                return Ok(false);
            }
            if let Some((nodes, new_nodes, node_bumps)) =
                self.collect_attr_node_batch(py, list.iter(), list.len())?
            {
                self.add_attr_node_batch(py, nodes, new_nodes, node_bumps)?;
                return Ok(true);
            }
        } else if let Ok(tuple) = nodes_to_add.downcast::<PyTuple>()
            && tuple.len() >= NODE_BATCH_MIN
            && let Some((nodes, new_nodes, node_bumps)) =
                self.collect_attr_node_batch(py, tuple.iter(), tuple.len())?
        {
            self.add_attr_node_batch(py, nodes, new_nodes, node_bumps)?;
            return Ok(true);
        }
        Ok(false)
    }

    /// br-r37-c1-digbatch: bulk fast path for `add_nodes_from(range / int list)` on a
    /// DiGraph — the directed sibling of `PyGraph::_fast_add_int_nodes`. PyDiGraph has no
    /// `lazy_int_node_stop`, so Py int objects are stored (not lazy keys). Atomic
    /// validate-then-mutate: every element must be an EXACT `int` (`is_exact_instance_of`
    /// excludes `bool`) and fit i64, else raise so the wrapper falls back to the general
    /// per-node loop before any node is touched. First-occurrence order; dedup on
    /// `node_key_map`. Was the 0.33x (range) / 0.54x (int list) DiGraph node-add loss.
    fn _fast_add_int_nodes(&mut self, py: Python<'_>, nodes: &Bound<'_, PyAny>) -> PyResult<()> {
        let iter = PyIterator::from_object(nodes)?;
        let mut ints: Vec<i64> = Vec::new();
        for item in iter {
            let item = item?;
            if !item.is_exact_instance_of::<PyInt>() {
                return Err(PyTypeError::new_err(
                    "fast int-node path requires exact int elements",
                ));
            }
            ints.push(item.extract::<i64>()?);
        }
        let mut fresh_canonicals = Vec::with_capacity(ints.len());
        for node in ints {
            let canonical = node.to_string();
            let was_absent =
                !self.node_key_map.contains_key(&canonical) && !self.inner.has_node(&canonical);
            self.node_key_map
                .entry(canonical.clone())
                .or_insert_with(|| {
                    unwrap_infallible(node.into_pyobject(py))
                        .into_any()
                        .unbind()
                });
            if was_absent {
                self.node_iter_mirror_insert(py, &canonical)?;
                fresh_canonicals.push(canonical);
            }
            self.bump_nodes_seq();
        }
        let _ = self.inner.extend_nodes_unrecorded(fresh_canonicals);
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
            let (u, v, w) = weighted_edge_triplet(&item)?;
            let d = PyDict::new(py);
            d.set_item(weight, &w)?;
            self.add_edge(py, &u, &v, Some(&d))?;
        }
        self.bump_edges_seq();
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
        self.cached_succ_remove_key(py, &u_canonical, &v_canonical);
        self.cached_pred_remove_key(py, &v_canonical, &u_canonical);
        if !self.succ_py_keys.is_empty() || !self.pred_py_keys.is_empty() {
            // br-r37-c1-z6uka: drop row overrides for the removed edge.
            self.succ_py_keys
                .remove(&(u_canonical.clone(), v_canonical.clone()));
            self.pred_py_keys.remove(&(v_canonical, u_canonical));
        }
        self.bump_edges_seq();
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
            self.cached_succ_remove_key(py, &u_c, &v_c);
            self.cached_pred_remove_key(py, &v_c, &u_c);
            if !self.succ_py_keys.is_empty() || !self.pred_py_keys.is_empty() {
                // br-r37-c1-z6uka: drop row overrides for the removed edge.
                self.succ_py_keys.remove(&(u_c.clone(), v_c.clone()));
                self.pred_py_keys.remove(&(v_c.clone(), u_c.clone()));
            }
        }
        self.bump_edges_seq();
        Ok(())
    }

    // ---- Directed-specific queries ----

    /// Return a list of successors of node n.
    fn successors(&self, py: Python<'_>, n: &Bound<'_, PyAny>) -> PyResult<Vec<PyObject>> {
        let canonical = node_key_to_string(py, n)?;
        match self.inner.successors(&canonical) {
            Some(succs) => Ok(succs
                .into_iter()
                .map(
                    |s| self.py_succ_key(py, &canonical, s), /* br-r37-c1-z6uka */
                )
                .collect()),
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
            Some(preds) => Ok(preds
                .into_iter()
                .map(
                    |p| self.py_pred_key(py, &canonical, p), /* br-r37-c1-z6uka */
                )
                .collect()),
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
                .map(|s| self.py_succ_key(py, node, s) /* br-r37-c1-z6uka */)
                .collect();
            result.push((py_node, succs));
        }
        Ok(result)
    }

    /// br-r37-c1-toposucc: private-named (node, [successor]) snapshot the Python
    /// ``DiGraph.adjacency`` wrapper (which returns nx's {succ: attrs} dict form)
    /// does not shadow. Lets topological_sort build the successor map in ONE
    /// native call and then do O(1) dict lookups in Kahn's loop instead of a
    /// per-node ``succ[u]`` AtlasView getitem. Successor (out-neighbour) keys in
    /// node x adjacency order; no edge-attr dicts built.
    fn _native_adjacency_keys<'py>(
        &self,
        py: Python<'py>,
    ) -> PyResult<Vec<(PyObject, Vec<PyObject>)>> {
        self.adjacency(py)
    }

    /// br-r37-c1-zt6lj: true when canonical node strings are also the Python
    /// display strings used by `generate_adjlist`; sparse row-key override maps
    /// force the generic fallback.
    fn _native_adjlist_canonical_body_safe(&self) -> bool {
        self.node_key_map.is_empty() && self.succ_py_keys.is_empty()
    }

    fn _native_has_succ_py_keys(&self) -> bool {
        !self.succ_py_keys.is_empty()
    }

    fn _native_has_pred_py_keys(&self) -> bool {
        !self.pred_py_keys.is_empty()
    }

    /// br-r37-c1-gadj: native nested adjacency snapshot ({node: {successor:
    /// attrs}}) so the Python DiGraph.adjacency (_simple_graph_adjacency) builds
    /// it natively instead of walking ``dict(self.adj[node])`` via the AtlasView
    /// lambda chain per node (~135x slower than nx). Inner ``{succ: attrs}``
    /// dicts reuse the live ``edge_py_attrs`` references (directed edge_key), in
    /// node x successor adjacency order.
    fn _native_adjacency_dict(&self, py: Python<'_>) -> PyResult<Py<PyDict>> {
        if self.inner.edge_count() > 0 {
            self.mark_edges_dirty();
        }
        let result = PyDict::new(py);
        for node in self.inner.nodes_ordered() {
            let py_node = self.py_node_key(py, node);
            let succs_dict = PyDict::new(py);
            for successor in self.inner.successors(node).unwrap_or_default() {
                let py_succ = self.py_succ_key(py, node, successor) /* br-r37-c1-z6uka */;
                let ek = Self::edge_key(node, successor);
                let attrs = self
                    .edge_py_attrs
                    .get(&ek)
                    .map_or_else(|| PyDict::new(py).unbind(), |d| d.clone_ref(py));
                succs_dict.set_item(&py_succ, attrs.bind(py))?;
            }
            result.set_item(py_node, succs_dict)?;
        }
        Ok(result.unbind())
    }

    fn _native_successor_row_dict(
        &mut self,
        py: Python<'_>,
        node: &Bound<'_, PyAny>,
    ) -> PyResult<Py<PyDict>> {
        let canonical = node_key_to_string(py, node)?;
        if !self.inner.has_node(&canonical) {
            return Err(crate::missing_key_error(node));
        }
        self.successor_row_dict_by_canonical(py, &canonical)
    }

    fn _native_predecessor_row_dict(
        &mut self,
        py: Python<'_>,
        node: &Bound<'_, PyAny>,
    ) -> PyResult<Py<PyDict>> {
        let canonical = node_key_to_string(py, node)?;
        if !self.inner.has_node(&canonical) {
            return Err(crate::missing_key_error(node));
        }
        self.predecessor_row_dict_by_canonical(py, &canonical)
    }

    fn _native_adjacency_row_dict(
        &mut self,
        py: Python<'_>,
        node: &Bound<'_, PyAny>,
    ) -> PyResult<Py<PyDict>> {
        self._native_successor_row_dict(py, node)
    }

    // ---- Utility methods ----

    fn clear(&mut self, py: Python<'_>) -> PyResult<()> {
        self.inner = DiGraph::with_runtime_policy(self.inner.runtime_policy().clone());
        self.node_key_map.clear();
        self.node_py_attrs.clear();
        self.edge_py_attrs.clear();
        self.succ_py_keys.clear(); // br-r37-c1-z6uka
        self.pred_py_keys.clear(); // br-r37-c1-z6uka
        self.succ_row_py.clear();
        self.pred_row_py.clear();
        self.graph_attrs = PyDict::new(py).unbind();
        // Clear the live mirror in place so an in-flight iter raises like nx.
        self.node_iter_mirror_clear(py)?;
        self.bump_nodes_seq();
        self.bump_edges_seq(); // br-r37-c1-jft0i
        Ok(())
    }

    fn clear_edges(&mut self) {
        let edges: Vec<(String, String)> = self.edge_py_attrs.keys().cloned().collect();
        for (u, v) in edges {
            self.inner.remove_edge(&u, &v);
        }
        self.edge_py_attrs.clear();
        self.succ_py_keys.clear(); // br-r37-c1-z6uka
        self.pred_py_keys.clear(); // br-r37-c1-z6uka
        let _ = Python::attach(|py| self.cached_directed_clear_edges_in_place(py));
        self.bump_edges_seq(); // br-r37-c1-jft0i
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
        // br-r37-c1-revborrow: FAST PATH for the common case where no Python
        // attribute mirror dicts have been materialised (the inner Rust attr
        // maps are then the sole source of truth — true for every generator /
        // bulk-built graph and any graph whose attrs were never fetched via
        // ``G[u][v]`` / ``G.nodes[n]``). ``DiGraph::reversed`` transposes the
        // topology in pure integer index space (O(V+E), zero String hashing /
        // re-insertion), which is identical to walking ``edges_ordered`` and
        // re-adding every edge through the name table — but ~10x cheaper at
        // scale. ``pred_py_keys`` (z6uka display overrides) still transpose
        // exactly as the slow path. ``add_node``/``add_edge`` eagerly create
        // EMPTY ``node_py_attrs`` dicts for every endpoint, so a non-empty map
        // does NOT imply real attrs — gate on every mirror dict being empty.
        // Then the inner Rust attr map is authoritative and ``reversed``
        // reproduces the slow path exactly (edges read inner attrs; a node is
        // empty iff its mirror dict is empty). Any non-empty mirror dict (a real
        // attr, possibly an unsynced post-creation mutation) falls back to the
        // proven per-edge rebuild below.
        let mirrors_all_empty = self.node_py_attrs.values().all(|d| d.bind(py).is_empty())
            && self.edge_py_attrs.values().all(|d| d.bind(py).is_empty());
        if mirrors_all_empty {
            let mut rev = Self {
                inner: self.inner.reversed(),
                node_key_map: HashMap::with_capacity(self.node_key_map.len()),
                node_py_attrs: HashMap::new(),
                edge_py_attrs: HashMap::new(),
                succ_py_keys: HashMap::new(),
                pred_py_keys: Self::clone_row_keys(py, &self.succ_py_keys),
                succ_row_py: HashMap::new(),
                pred_row_py: HashMap::new(),
                graph_attrs: self.graph_attrs.bind(py).copy()?.unbind(),
                nodes_seq: 0,
                edges_seq: 0,
                edges_dirty: AtomicBool::new(false),
                node_keys_cache: std::sync::Mutex::new(None),
                node_data_mirror: std::sync::Mutex::new(None),
                dict_of_dicts_cache: None,
                edges_with_data_cache: None,
                in_edges_with_data_cache: None,
                edges_attr_dicts_cache: None,
                node_iter_mirror: std::sync::Mutex::new(None),
            };
            for canonical in self.inner.nodes_ordered() {
                rev.node_key_map
                    .insert(canonical.to_owned(), self.py_node_key(py, canonical));
            }
            return Ok(rev);
        }
        let mut rev = Self {
            inner: DiGraph::with_runtime_policy(self.inner.runtime_policy().clone()),
            node_key_map: HashMap::new(),
            node_py_attrs: HashMap::new(),
            edge_py_attrs: HashMap::new(),
            succ_py_keys: HashMap::new(), // br-r37-c1-z6uka
            pred_py_keys: Self::clone_row_keys(py, &self.succ_py_keys), // br-r37-c1-z6uka
            succ_row_py: HashMap::new(),
            pred_row_py: HashMap::new(),
            graph_attrs: self.graph_attrs.bind(py).copy()?.unbind(),
            nodes_seq: 0,
            edges_seq: 0,
            edges_dirty: AtomicBool::new(false),
            node_keys_cache: std::sync::Mutex::new(None),
            node_data_mirror: std::sync::Mutex::new(None),
            dict_of_dicts_cache: None,
            edges_with_data_cache: None,
            in_edges_with_data_cache: None,
            edges_attr_dicts_cache: None,
            node_iter_mirror: std::sync::Mutex::new(None),
        };
        // br-r37-c1-revbulk: node + edge BATCHES through the unrecorded
        // path (one ledger record vs per-edge add_edge_with_attrs +
        // record_decision). Node order = source insertion order; edge
        // order = source edge order with endpoints transposed — both
        // preserve nx iteration. Mirrors stay lazy.
        let mut node_batch: Vec<(String, fnx_classes::AttrMap)> = Vec::new();
        for canonical in self.inner.nodes_ordered() {
            let rust_attrs = self
                .node_py_attrs
                .get(canonical)
                .map(|attrs| py_dict_to_attr_map(attrs.bind(py)))
                .transpose()?
                .unwrap_or_default();
            rev.node_key_map
                .insert(canonical.to_owned(), self.py_node_key(py, canonical));
            if let Some(attrs) = self.node_py_attrs.get(canonical) {
                rev.node_py_attrs
                    .insert(canonical.to_owned(), attrs.bind(py).copy()?.unbind());
            }
            node_batch.push((canonical.to_owned(), rust_attrs));
        }
        let _ = rev.inner.extend_nodes_with_attrs_unrecorded(node_batch);
        let mut edge_batch: Vec<(String, String, fnx_classes::AttrMap)> = Vec::new();
        for edge in self.inner.edges_ordered() {
            let u = &edge.left;
            let v = &edge.right;
            let edge_key = Self::edge_key(u, v);
            let rust_attrs = if let Some(attrs) = self.edge_py_attrs.get(&edge_key) {
                let copied = attrs.bind(py).copy()?.unbind();
                let am = py_dict_to_attr_map(copied.bind(py))?;
                rev.edge_py_attrs.insert((v.clone(), u.clone()), copied);
                am
            } else {
                edge.attrs.clone()
            };
            edge_batch.push((v.clone(), u.clone(), rust_attrs));
        }
        let _ = rev.inner.extend_edges_with_attrs_unrecorded(edge_batch);
        Ok(rev)
    }

    /// Convert to undirected PyGraph — merges parallel directed edges.
    fn to_undirected(&self, py: Python<'_>) -> PyResult<PyGraph> {
        let mut ug = PyGraph::new_empty_with_policy(py, self.inner.runtime_policy().clone())?;
        let mut needs_edge_attr_sync = false;
        // br-r37-c1-tbh4q: this conversion is primarily a topology copy. Keep
        // Python attr mirrors authoritative and defer Rust AttrMap materialization
        // until a native read asks for it, instead of crossing every attr dict
        // during construction.
        for (canonical, py_key) in &self.node_key_map {
            ug.inner
                .add_node_with_attrs(canonical.clone(), AttrMap::new());
            ug.node_key_map
                .insert(canonical.clone(), py_key.clone_ref(py));
            if let Some(attrs) = self.node_py_attrs.get(canonical) {
                ug.node_py_attrs
                    .insert(canonical.clone(), attrs.bind(py).copy()?.unbind());
            }
        }
        // br-r37-c1-78os5: copy edges in canonical node->successor order
        // (`edges_ordered`) — NOT `edge_py_attrs` HashMap order — and merge
        // reciprocal directions with networkx's semantics: for a<->b the
        // LATER-processed direction's attrs win (dict.update). The previous loop
        // iterated the `edge_py_attrs` HashMap (non-deterministic order) and kept
        // the FIRST-seen direction, so the reciprocal-edge winner was random and
        // diverged from nx depending on the process's hash seed.
        for snapshot in self.inner.edges_ordered() {
            let u = snapshot.left;
            let v = snapshot.right;
            let ek = PyGraph::edge_key(&u, &v);
            let src = self.edge_py_attrs.get(&(u.clone(), v.clone()));
            if let Some(d) = src
                && !d.bind(py).is_empty()
            {
                needs_edge_attr_sync = true;
            }
            // Inner topology only; Python side below keeps nx's latter-wins
            // attr merge. Weighted native callers will sync from the mirrors.
            let _ = ug.inner.add_edge_with_attrs(u, v, AttrMap::new());
            // Python side: latter wins -> update the existing undirected dict;
            // otherwise insert a fresh copy.
            match ug.edge_py_attrs.entry(ek) {
                std::collections::hash_map::Entry::Occupied(existing) => {
                    if let Some(d) = src {
                        existing
                            .get()
                            .bind(py)
                            .call_method1("update", (d.bind(py),))?;
                    }
                }
                std::collections::hash_map::Entry::Vacant(entry) => {
                    let copy = match src {
                        Some(d) => d.bind(py).copy()?.unbind(),
                        None => PyDict::new(py).unbind(),
                    };
                    entry.insert(copy);
                }
            }
        }
        if needs_edge_attr_sync {
            ug.mark_edges_dirty();
        }
        ug.graph_attrs = self.graph_attrs.bind(py).copy()?.unbind();
        Ok(ug)
    }

    /// Return a directed copy.
    fn to_directed(&self, py: Python<'_>) -> PyResult<Self> {
        self.copy(py)
    }

    /// br-r37-c1-s0d4x: wholesale same-type constructor absorb — nx's
    /// ``cls(G)`` structure is identical to ``G.copy()`` (probed: nodes,
    /// edges+data, adjacency/pred rows, graph attrs, shallow attr-dict
    /// copying, all four classes). The Python ctor wrapper routes the
    /// exact-same-type case here instead of the per-edge rebuild walk.
    /// br-r37-c1-l5ve7: native DiGraph -> Graph deepcopy for
    /// to_undirected(reciprocal=False), replacing the pure-Python
    /// add_edges_from walk (1.1M Python calls on 12k edges). nx
    /// semantics mirrored: u-major succ walk; a reciprocal (v, u) edge
    /// MERGES (dict update) into the first cell; adjacency cells keep
    /// FIRST-TOUCH objects (forward cell = the succ-row object, reverse
    /// cell = the u iteration object). Construction-tax recipe: fresh
    /// ledger + bulk unrecorded inserts + lazy attr mirrors.
    fn _native_to_undirected_deepcopy(&self, py: Python<'_>) -> PyResult<Py<crate::PyGraph>> {
        let deepcopy = py.import("copy")?.getattr("deepcopy")?;
        let mut g = crate::PyGraph::new_empty_with_policy(
            py,
            fnx_runtime::RuntimePolicy::new(self.inner.mode()),
        )?;
        g.graph_attrs = crate::deepcopy_py_dict(py, &deepcopy, &self.graph_attrs)?;
        let mut node_batch: Vec<(String, fnx_classes::AttrMap)> =
            Vec::with_capacity(self.inner.node_count());
        for node in self.inner.nodes_ordered() {
            let rust_attrs = if let Some(attrs) = self.node_py_attrs.get(node) {
                let py_attrs = crate::deepcopy_py_dict(py, &deepcopy, attrs)?;
                let rust_attrs = py_dict_to_attr_map(py_attrs.bind(py))?;
                g.node_py_attrs.insert(node.to_owned(), py_attrs);
                rust_attrs
            } else {
                Default::default()
            };
            g.node_key_map
                .insert(node.to_owned(), self.py_node_key(py, node));
            node_batch.push((node.to_owned(), rust_attrs));
        }
        g.inner.extend_nodes_with_attrs_unrecorded(node_batch);
        let mut edge_batch: Vec<(String, String, fnx_classes::AttrMap)> =
            Vec::with_capacity(self.inner.edge_count());
        let mut seen: std::collections::HashSet<(String, String)> =
            std::collections::HashSet::with_capacity(self.inner.edge_count());
        for source in self.inner.nodes_ordered() {
            for target in self.inner.successors(source).unwrap_or_default() {
                let unordered = if source <= target {
                    (source.to_owned(), target.to_owned())
                } else {
                    (target.to_owned(), source.to_owned())
                };
                if seen.insert(unordered) {
                    // first touch of this undirected cell: nx keeps the
                    // objects from THIS add (succ-row v, iteration u).
                    let v_obj = self.py_succ_key(py, source, target);
                    g.maybe_store_adj_key(py, source, target, v_obj.bind(py));
                    let u_obj = self.py_node_key(py, source);
                    g.maybe_store_adj_key(py, target, source, u_obj.bind(py));
                }
                let rust_attrs = match self
                    .edge_py_attrs
                    .get(&(source.to_owned(), target.to_owned()))
                {
                    Some(attrs) => {
                        let py_attrs = crate::deepcopy_py_dict(py, &deepcopy, attrs)?;
                        let rust_attrs = py_dict_to_attr_map(py_attrs.bind(py))?;
                        let ek_fwd = crate::PyGraph::edge_key(source, target);
                        let ek_rev = crate::PyGraph::edge_key(target, source);
                        if let Some(existing) = g
                            .edge_py_attrs
                            .get(&ek_fwd)
                            .or_else(|| g.edge_py_attrs.get(&ek_rev))
                        {
                            // reciprocal edge: nx's datadict.update merge.
                            existing.bind(py).update(py_attrs.bind(py).as_mapping())?;
                        } else {
                            g.edge_py_attrs.insert(ek_fwd, py_attrs);
                        }
                        rust_attrs
                    }
                    // attr-less edge stays lazy (no PyDict alloc)
                    None => Default::default(),
                };
                edge_batch.push((source.to_owned(), target.to_owned(), rust_attrs));
            }
        }
        g.inner.extend_edges_with_attrs_unrecorded(edge_batch);
        Py::new(py, g)
    }

    fn _fnx_absorb_copy(&mut self, py: Python<'_>, other: PyRef<'_, Self>) -> PyResult<()> {
        *self = other.copy(py)?;
        Ok(())
    }

    fn copy(&self, py: Python<'_>) -> PyResult<Self> {
        // br-r37-c1-copyclone: bulk-clone the inner Rust digraph instead of
        // rebuilding it edge-by-edge (String hashing + adjacency inserts +
        // edge_index_endpoints push + a redundant py_dict_to_attr_map re-parse
        // per edge). `DiGraph::clone` copies the IndexMap/IndexSet/Vec verbatim,
        // so node + edge insertion order are preserved exactly — which ALSO
        // fixes the prior non-deterministic copy node order (the previous loop
        // rebuilt `inner` in `self.node_key_map` HashMap-iteration order, so
        // `list(G.copy())` could diverge from `list(G)`; project_copy_node_order).
        // Only the unavoidable deep-copy of the Python attr dicts remains.
        let mut new_graph = Self {
            inner: self.inner.clone_with_fresh_policy(), // br-r37-c1-7dpyg: skip ledger
            node_key_map: HashMap::with_capacity(self.node_key_map.len()),
            node_py_attrs: HashMap::with_capacity(self.node_py_attrs.len()),
            edge_py_attrs: HashMap::with_capacity(self.edge_py_attrs.len()),
            succ_py_keys: Self::clone_row_keys(py, &self.succ_py_keys), // br-r37-c1-z6uka
            pred_py_keys: HashMap::new(),                               // br-r37-c1-z6uka
            succ_row_py: HashMap::new(),
            pred_row_py: HashMap::new(),
            graph_attrs: self.graph_attrs.bind(py).copy()?.unbind(),
            nodes_seq: 0,
            edges_seq: 0,
            edges_dirty: AtomicBool::new(self.edges_dirty.load(Ordering::Relaxed)),
            node_keys_cache: std::sync::Mutex::new(None),
            node_data_mirror: std::sync::Mutex::new(None),
            dict_of_dicts_cache: None,
            edges_with_data_cache: None,
            in_edges_with_data_cache: None,
            edges_attr_dicts_cache: None,
            node_iter_mirror: std::sync::Mutex::new(None),
        };
        // br-r37-c1-0ek49: nx's DiGraph.copy() rebuild walk recreates succ
        // rows in original order but fills PRED rows in u-major walk order;
        // the verbatim clone above preserves the source's pred rows instead.
        new_graph.inner.reorder_pred_rows_for_nx_copy_walk();
        // Node-attr mutations are not tracked by `edges_dirty`, so refresh the
        // cloned inner's node attrs from the authoritative Python dicts.
        for (canonical, py_key) in &self.node_key_map {
            new_graph
                .node_key_map
                .insert(canonical.clone(), py_key.clone_ref(py));
            if let Some(attrs) = self.node_py_attrs.get(canonical) {
                let bound = attrs.bind(py);
                new_graph
                    .inner
                    .replace_node_attrs(canonical, py_dict_to_attr_map(bound)?);
                new_graph
                    .node_py_attrs
                    .insert(canonical.clone(), bound.copy()?.unbind());
            }
        }
        // Deep-copy the edge attr dicts (key orientation preserved verbatim;
        // edges() order comes from the cloned inner, so HashMap walk order here
        // is irrelevant).
        for (key, attrs) in &self.edge_py_attrs {
            new_graph
                .edge_py_attrs
                .insert(key.clone(), attrs.bind(py).copy()?.unbind());
        }
        Ok(new_graph)
    }

    /// br-r37-c1-copynative: stable alias exposing the native order-preserving
    /// `copy` (above) to the Python `_copy_preserving_insertion_order` wrapper
    /// (which shadows `copy` at the Python class level), so exact-type
    /// `DiGraph.copy()` uses the bulk `inner.clone()` path instead of the
    /// ~4x-slower edges(data=True) + add_edges_from rebuild.
    fn _native_copy(&self, py: Python<'_>) -> PyResult<Self> {
        self.copy(py)
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
            inner: DiGraph::with_runtime_policy(self.inner.runtime_policy().clone()),
            node_key_map: HashMap::new(),
            node_py_attrs: HashMap::new(),
            edge_py_attrs: HashMap::new(),
            succ_py_keys: HashMap::new(), // br-r37-c1-z6uka
            pred_py_keys: HashMap::new(), // br-r37-c1-z6uka
            succ_row_py: HashMap::new(),
            pred_row_py: HashMap::new(),
            graph_attrs: self.graph_attrs.bind(py).copy()?.unbind(),
            nodes_seq: 0,
            edges_seq: 0,
            edges_dirty: AtomicBool::new(false),
            node_keys_cache: std::sync::Mutex::new(None),
            node_data_mirror: std::sync::Mutex::new(None),
            dict_of_dicts_cache: None,
            edges_with_data_cache: None,
            in_edges_with_data_cache: None,
            edges_attr_dicts_cache: None,
            node_iter_mirror: std::sync::Mutex::new(None),
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

        if !self.succ_py_keys.is_empty() {
            // br-r37-c1-z6uka: succ overrides for surviving edges; pred rows
            // are re-derived with node objects (nx walk semantics).
            new_graph.succ_py_keys = self
                .succ_py_keys
                .iter()
                .filter(|((a, b), _)| new_graph.inner.has_edge(a, b))
                .map(|(k, v)| (k.clone(), v.clone_ref(py)))
                .collect();
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
            inner: DiGraph::with_runtime_policy(self.inner.runtime_policy().clone()),
            node_key_map: HashMap::new(),
            node_py_attrs: HashMap::new(),
            edge_py_attrs: HashMap::new(),
            succ_py_keys: HashMap::new(), // br-r37-c1-z6uka
            pred_py_keys: HashMap::new(), // br-r37-c1-z6uka
            succ_row_py: HashMap::new(),
            pred_row_py: HashMap::new(),
            graph_attrs: self.graph_attrs.bind(py).copy()?.unbind(),
            nodes_seq: 0,
            edges_seq: 0,
            edges_dirty: AtomicBool::new(false),
            node_keys_cache: std::sync::Mutex::new(None),
            node_data_mirror: std::sync::Mutex::new(None),
            dict_of_dicts_cache: None,
            edges_with_data_cache: None,
            in_edges_with_data_cache: None,
            edges_attr_dicts_cache: None,
            node_iter_mirror: std::sync::Mutex::new(None),
        };

        let mut nodes_needed: std::collections::HashSet<String> = std::collections::HashSet::new();
        for (u, v) in &keep_edges {
            nodes_needed.insert(u.clone());
            nodes_needed.insert(v.clone());
        }
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

        if !self.succ_py_keys.is_empty() {
            // br-r37-c1-z6uka: succ overrides for surviving edges; pred rows
            // are re-derived with node objects (nx walk semantics).
            new_graph.succ_py_keys = self
                .succ_py_keys
                .iter()
                .filter(|((a, b), _)| new_graph.inner.has_edge(a, b))
                .map(|(k, v)| (k.clone(), v.clone_ref(py)))
                .collect();
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

    /// br-r37-c1-d58s8: test-only consistency oracle for the eager
    /// index rows (DiGraph flip P1).
    #[doc(hidden)]
    fn _debug_index_rows_consistent(&self) -> bool {
        self.inner.debug_index_rows_consistent()
    }

    /// Return attributes of the edge (u, v).
    #[pyo3(signature = (u, v, default=None))]
    fn get_edge_data(
        &mut self,
        py: Python<'_>,
        u: &Bound<'_, PyAny>,
        v: &Bound<'_, PyAny>,
        default: Option<PyObject>,
    ) -> PyResult<PyObject> {
        let u_c = node_key_to_string(py, u)?;
        let v_c = node_key_to_string(py, v)?;
        // br-r37-c1-d58s8: gate on the INNER edge, not mirror presence —
        // lazy-mirror paths (ctor bulk absorb, clone converters) create
        // no mirrors for attr-less edges; an existing edge must return
        // its (materialized) dict, not the default.
        if !self.inner.has_edge(&u_c, &v_c) {
            return Ok(default.unwrap_or_else(|| py.None()));
        }
        self.mark_edges_dirty();
        Ok(self.materialize_edge_py_attrs(py, &u_c, &v_c).into_any())
    }

    /// br-r37-c1-sjf4t: push the per-node and per-edge Python attribute
    /// dicts back into the Rust ``inner`` graph. Called by Python-level
    /// wrappers before invoking native algorithms so post-creation
    /// mutations (``G[u][v]['k']=v``) are visible to the Rust kernels.
    fn _fnx_sync_attrs_to_inner(&mut self, py: Python<'_>) -> PyResult<()> {
        let nodes: Vec<(String, AttrMap)> = self
            .node_py_attrs
            .iter()
            .map(|(canonical, dict)| Ok((canonical.clone(), py_dict_to_attr_map(dict.bind(py))?)))
            .collect::<PyResult<_>>()?;
        for (canonical, attrs) in nodes {
            self.inner.replace_node_attrs(&canonical, attrs);
        }
        if !self.edges_dirty.load(Ordering::Relaxed) {
            return Ok(());
        }
        let edges: Vec<(String, String, AttrMap)> = self
            .edge_py_attrs
            .iter()
            .map(|((u, v), dict)| Ok((u.clone(), v.clone(), py_dict_to_attr_map(dict.bind(py))?)))
            .collect::<PyResult<_>>()?;
        for (u, v, attrs) in edges {
            self.inner.replace_edge_attrs(&u, &v, attrs);
        }
        Ok(())
    }

    /// Edge-only sibling for kernels that read weights but never node attrs.
    fn _fnx_sync_edge_attrs_to_inner(&mut self, py: Python<'_>) -> PyResult<()> {
        if !self.edges_dirty.load(Ordering::Relaxed) {
            return Ok(());
        }
        let edges: Vec<(String, String, AttrMap)> = self
            .edge_py_attrs
            .iter()
            .map(|((u, v), dict)| Ok((u.clone(), v.clone(), py_dict_to_attr_map(dict.bind(py))?)))
            .collect::<PyResult<_>>()?;
        for (u, v, attrs) in edges {
            self.inner.replace_edge_attrs(&u, &v, attrs);
        }
        Ok(())
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

    /// br-r37-c1-acuub: native ordered no-data edge materialization for the
    /// Python _DiGraphEdgeView fast path. This follows the same node-order,
    /// successor-order traversal as NetworkX and the existing Python wrapper,
    /// but avoids per-edge AtlasView traversal in Python.
    fn _native_edges_no_data(&self, py: Python<'_>) -> PyResult<PyObject> {
        // br-r37-c1-2a00r: index fast path — clone the per-index cached node-key
        // object (O(1) incref) instead of hashing the canonical String per
        // endpoint via py_node_key/py_succ_key. edges_ordered_indices() yields
        // (u, v) in the SAME node-major successor order as edges_ordered_borrowed.
        // Gated on succ_py_keys empty: when non-empty (non-uniform successor
        // display objects, br-r37-c1-z6uka) the v object can differ from the
        // node's own key, so fall through to the exact per-edge path.
        if self.succ_py_keys.is_empty() {
            let keys = self.cached_node_key_vec(py);
            let mut items = Vec::with_capacity(self.inner.edge_count());
            for (u, v) in self.inner.edges_ordered_indices() {
                items.push(tuple_object(
                    py,
                    &[keys[u].clone_ref(py), keys[v].clone_ref(py)],
                )?);
            }
            return Ok(items.into_pyobject(py)?.into_any().unbind());
        }
        let mut items = Vec::with_capacity(self.inner.edge_count());
        for (u, v, _) in self.inner.edges_ordered_borrowed() {
            let py_u = self.py_node_key(py, u);
            let py_v = self.py_succ_key(py, u, v) /* br-r37-c1-z6uka */;
            items.push(tuple_object(py, &[py_u, py_v])?);
        }
        Ok(items.into_pyobject(py)?.into_any().unbind())
    }

    /// br-r37-c1-deg-data: native ordered ``(u, v, attrs)`` materialization for
    /// the Python _DiGraphEdgeView ``edges(data=True)`` fast path. Same node x
    /// successor traversal as ``_native_edges_no_data`` (matches nx and the
    /// Python wrapper), reusing the live ``edge_py_attrs`` dict per edge so the
    /// yielded data dict is identity-shared with ``G[u][v]`` (nx contract).
    /// Avoids the per-edge ``succ[source].items()`` AtlasView walk (~58x).
    fn _native_edges_with_data(&mut self, py: Python<'_>) -> PyResult<PyObject> {
        // br-r37-c1-deg-data: we hand back the LIVE edge attr dicts, so a caller
        // mutating ``(u, v, d)``'s ``d`` (e.g. d['weight'] = x) edits
        // edge_py_attrs in place. Mark edges dirty so the next weighted-kernel
        // call re-syncs those dicts into inner (cf reference_edge_attr_sync_
        // staleness — the succ AtlasView path this replaces did this implicitly).
        if self.inner.edge_count() > 0 {
            self.mark_edges_dirty();
        }
        // br-r37-c1-o07ax: serve the node-major (u, v, live_attr) tuples from a
        // (nodes_seq, edges_seq)-keyed cache. Tuples are immutable + the inner
        // dicts are the live edge_py_attrs entries, so a fresh list of the same
        // tuple objects is byte-identical to a rebuild (attr mutations reflect;
        // edge/node mutation bumps a seq and invalidates).
        let valid = matches!(
            &self.edges_with_data_cache,
            Some((ns, es, _)) if *ns == self.nodes_seq && *es == self.edges_seq
        );
        if !valid {
            let mut items: Vec<PyObject> = Vec::with_capacity(self.inner.edge_count());
            let edges: Vec<(String, String)> = self
                .inner
                .edges_ordered_borrowed()
                .into_iter()
                .map(|(u, v, _)| (u.to_owned(), v.to_owned()))
                .collect();
            for (u, v) in edges {
                let py_u = self.py_node_key(py, &u);
                let py_v = self.py_succ_key(py, &u, &v) /* br-r37-c1-z6uka */;
                let attrs = self.materialize_edge_py_attrs(py, &u, &v);
                items.push(tuple_object(py, &[py_u, py_v, attrs.into_any()])?);
            }
            self.edges_with_data_cache = Some((self.nodes_seq, self.edges_seq, items));
        }
        let cached = &self.edges_with_data_cache.as_ref().unwrap().2;
        let fresh: Vec<PyObject> = cached.iter().map(|t| t.clone_ref(py)).collect();
        Ok(fresh.into_pyobject(py)?.into_any().unbind())
    }

    fn ordered_edge_attr_dicts(&mut self, py: Python<'_>) -> Option<Vec<Py<PyDict>>> {
        let valid = matches!(
            &self.edges_attr_dicts_cache,
            Some((ns, es, _)) if *ns == self.nodes_seq && *es == self.edges_seq
        );
        if !valid {
            let mut dicts = Vec::with_capacity(self.inner.edge_count());
            let edges: Vec<(String, String)> = self
                .inner
                .edges_ordered_borrowed()
                .into_iter()
                .map(|(u, v, _)| (u.to_owned(), v.to_owned()))
                .collect();
            for (u, v) in edges {
                let attrs = self.materialize_edge_py_attrs(py, &u, &v);
                dicts.push(attrs.clone_ref(py));
            }
            self.edges_attr_dicts_cache = Some((self.nodes_seq, self.edges_seq, dicts));
        }
        self.edges_attr_dicts_cache
            .as_ref()
            .map(|(_, _, dicts)| dicts.iter().map(|d| d.clone_ref(py)).collect())
    }

    /// br-r37-c1-deg-datakey: native ordered ``(u, v, attrs.get(key, default))``
    /// materialization for the Python _DiGraphEdgeView ``edges(data=<key>)``
    /// fast path. Same node x successor traversal as ``_native_edges_no_data``;
    /// reads each edge's value for ``key`` from the live ``edge_py_attrs`` dict
    /// (falling back to ``default``), avoiding the per-edge
    /// ``succ[source].items()`` AtlasView walk (~40x). Yields a VALUE (not the
    /// dict) so no dirty-mark is needed (read-only, matches nx's
    /// ``attrs.get(data, default)``).
    fn _native_edges_data_key(
        &mut self,
        py: Python<'_>,
        key: &Bound<'_, PyAny>,
        default: PyObject,
    ) -> PyResult<PyObject> {
        if self.succ_py_keys.is_empty() {
            let keys = self.cached_node_key_vec(py);
            let mut items = Vec::with_capacity(self.inner.edge_count());
            if let Some(attr_dicts) = self.ordered_edge_attr_dicts(py) {
                for ((u_idx, v_idx), attrs) in self
                    .inner
                    .edges_ordered_indices()
                    .into_iter()
                    .zip(attr_dicts)
                {
                    let value = attrs
                        .bind(py)
                        .get_item(key)
                        .ok()
                        .flatten()
                        .map_or_else(|| default.clone_ref(py), |val| val.unbind());
                    items.push(tuple_object(
                        py,
                        &[keys[u_idx].clone_ref(py), keys[v_idx].clone_ref(py), value],
                    )?);
                }
                return Ok(items.into_pyobject(py)?.into_any().unbind());
            }
            for (u_idx, v_idx) in self.inner.edges_ordered_indices() {
                let u = self
                    .inner
                    .get_node_name(u_idx)
                    .expect("edge index source must name an existing node")
                    .to_owned();
                let v = self
                    .inner
                    .get_node_name(v_idx)
                    .expect("edge index target must name an existing node")
                    .to_owned();
                let attrs = self.materialize_edge_py_attrs(py, &u, &v);
                let value = attrs
                    .bind(py)
                    .get_item(key)
                    .ok()
                    .flatten()
                    .map_or_else(|| default.clone_ref(py), |val| val.unbind());
                items.push(tuple_object(
                    py,
                    &[keys[u_idx].clone_ref(py), keys[v_idx].clone_ref(py), value],
                )?);
            }
            return Ok(items.into_pyobject(py)?.into_any().unbind());
        }
        let mut items = Vec::with_capacity(self.inner.edge_count());
        let edges: Vec<(String, String)> = self
            .inner
            .edges_ordered_borrowed()
            .into_iter()
            .map(|(u, v, _)| (u.to_owned(), v.to_owned()))
            .collect();
        for (u, v) in edges {
            let py_u = self.py_node_key(py, &u);
            let py_v = self.py_succ_key(py, &u, &v) /* br-r37-c1-z6uka */;
            let attrs = self.materialize_edge_py_attrs(py, &u, &v);
            let value = attrs
                .bind(py)
                .get_item(key)
                .ok()
                .flatten()
                .map_or_else(|| default.clone_ref(py), |val| val.unbind());
            items.push(tuple_object(py, &[py_u, py_v, value])?);
        }
        Ok(items.into_pyobject(py)?.into_any().unbind())
    }

    fn _native_guarded_edge_list_iter(
        slf: PyRef<'_, Self>,
        py: Python<'_>,
        items: PyObject,
    ) -> PyResult<Py<DiGraphGuardedEdgeListIter>> {
        let len = items.bind(py).len()?;
        let expected_nodes_seq = slf.nodes_seq;
        let expected_edges_seq = slf.edges_seq;
        let graph = Py::from(slf);
        Py::new(
            py,
            DiGraphGuardedEdgeListIter {
                graph,
                items,
                index: 0,
                len,
                expected_nodes_seq,
                expected_edges_seq,
            },
        )
    }

    fn _native_guarded_edge_stream_iter(
        slf: PyRef<'_, Self>,
        py: Python<'_>,
    ) -> PyResult<Option<Py<DiGraphGuardedEdgeStreamIter>>> {
        if !slf.succ_py_keys.is_empty() {
            return Ok(None);
        }
        let node_keys = slf.cached_node_key_tuple(py);
        let node_count = slf.inner.node_count();
        let expected_nodes_seq = slf.nodes_seq;
        let expected_edges_seq = slf.edges_seq;
        let graph = Py::from(slf);
        Ok(Some(Py::new(
            py,
            DiGraphGuardedEdgeStreamIter {
                graph,
                node_keys,
                node_idx: 0,
                succ_idx: 0,
                node_count,
                expected_nodes_seq,
                expected_edges_seq,
            },
        )?))
    }

    /// br-r37-c1-inedges: native in-edges materialization. nx's in_edges
    /// iterates node-major over predecessors (``for t in nodes: for s in
    /// pred[t]: yield (s, t, ...)``) — a different order than edges_ordered. The
    /// Python `_digraph_in_edges` walks ``pred[target].items()`` via the
    /// DiAdjacencyView lambda chain (~176x no-data / ~50x data). These build the
    /// same node x predecessor order natively from inner adjacency.
    fn _native_in_edges_no_data(&self, py: Python<'_>) -> PyResult<PyObject> {
        if self.pred_py_keys.is_empty() {
            let node_count = self.inner.node_count();
            let py_nodes = self.cached_node_key_vec(py);
            let mut items = Vec::with_capacity(self.inner.edge_count());
            for target_idx in 0..node_count {
                let py_t = py_nodes.get(target_idx).ok_or_else(|| {
                    PyRuntimeError::new_err("node index should resolve during in_edges")
                })?;
                if let Some(predecessors) = self.inner.predecessors_indices(target_idx) {
                    for &source_idx in predecessors {
                        let py_s = py_nodes.get(source_idx).ok_or_else(|| {
                            PyRuntimeError::new_err(
                                "predecessor index should resolve during in_edges",
                            )
                        })?;
                        items.push(tuple_object(py, &[py_s.clone_ref(py), py_t.clone_ref(py)])?);
                    }
                }
            }
            return Ok(items.into_pyobject(py)?.into_any().unbind());
        }

        let mut items = Vec::with_capacity(self.inner.edge_count());
        for target in self.inner.nodes_ordered() {
            let py_t = self.py_node_key(py, target);
            for source in self.inner.predecessors(target).unwrap_or_default() {
                let py_s = self.py_pred_key(py, target, source) /* br-r37-c1-z6uka */;
                items.push(tuple_object(py, &[py_s, py_t.clone_ref(py)])?);
            }
        }
        Ok(items.into_pyobject(py)?.into_any().unbind())
    }

    /// br-r37-c1-04z53.9110: bare ``DG.reverse(copy=False).edges()`` has the
    /// same node-major predecessor traversal as ``in_edges()``, but emits the
    /// reversed orientation ``(target, source)``. Build that batch natively for
    /// exact DiGraph reverse views instead of walking Python pred rows.
    fn _native_reverse_edges_no_data(&self, py: Python<'_>) -> PyResult<PyObject> {
        if self.pred_py_keys.is_empty() {
            let node_count = self.inner.node_count();
            let mut py_nodes = Vec::with_capacity(node_count);
            for idx in 0..node_count {
                let node = self
                    .inner
                    .get_node_name(idx)
                    .expect("node index should resolve");
                py_nodes.push(self.py_node_key(py, node));
            }

            let mut items = Vec::with_capacity(self.inner.edge_count());
            for target_idx in 0..node_count {
                let py_t = &py_nodes[target_idx];
                if let Some(predecessors) = self.inner.predecessors_indices(target_idx) {
                    for &source_idx in predecessors {
                        let py_s = &py_nodes[source_idx];
                        items.push(tuple_object(py, &[py_t.clone_ref(py), py_s.clone_ref(py)])?);
                    }
                }
            }
            return Ok(items.into_pyobject(py)?.into_any().unbind());
        }

        let mut items = Vec::with_capacity(self.inner.edge_count());
        for target in self.inner.nodes_ordered() {
            let py_t = self.py_node_key(py, target);
            for source in self.inner.predecessors(target).unwrap_or_default() {
                let py_s = self.py_pred_key(py, target, source) /* br-r37-c1-z6uka */;
                items.push(tuple_object(py, &[py_t.clone_ref(py), py_s])?);
            }
        }
        Ok(items.into_pyobject(py)?.into_any().unbind())
    }

    /// br-r37-c1-inedges: in_edges(data=True). Reuses the live edge attr dict
    /// per edge (identity-shared with G[s][t]); marks edges dirty so a weight
    /// mutation through the yielded dict re-syncs to the weighted kernel.
    fn _native_in_edges_with_data(&mut self, py: Python<'_>) -> PyResult<PyObject> {
        if self.inner.edge_count() > 0 {
            self.mark_edges_dirty();
        }
        // br-r37-c1-inedges-cache (cc): mirror _native_edges_with_data's
        // (nodes_seq, edges_seq)-keyed cache. Previously in_edges(data=True)
        // rebuilt every call (+ alloc'd an empty PyDict per attr-less edge),
        // making it 12x slower than out_edges(data=True). Cache the target-major
        // (source, target, live_attr) tuples; on a seq match return a fresh list
        // of the same tuple objects (attr mutations stay visible via live dicts;
        // node/edge mutation bumps a seq and invalidates).
        let valid = matches!(
            &self.in_edges_with_data_cache,
            Some((ns, es, _)) if *ns == self.nodes_seq && *es == self.edges_seq
        );
        if !valid {
            let pairs: Vec<(String, String)> = {
                let mut v = Vec::with_capacity(self.inner.edge_count());
                for target in self.inner.nodes_ordered() {
                    for source in self.inner.predecessors(target).unwrap_or_default() {
                        v.push((source.to_owned(), target.to_owned()));
                    }
                }
                v
            };
            let mut items: Vec<PyObject> = Vec::with_capacity(pairs.len());
            for (source, target) in pairs {
                let py_s = self.py_pred_key(py, &target, &source) /* br-r37-c1-z6uka */;
                let py_t = self.py_node_key(py, &target);
                let attrs = self.materialize_edge_py_attrs(py, &source, &target);
                items.push(tuple_object(py, &[py_s, py_t, attrs.into_any()])?);
            }
            self.in_edges_with_data_cache = Some((self.nodes_seq, self.edges_seq, items));
        }
        let cached = &self.in_edges_with_data_cache.as_ref().unwrap().2;
        let fresh: Vec<PyObject> = cached.iter().map(|t| t.clone_ref(py)).collect();
        Ok(fresh.into_pyobject(py)?.into_any().unbind())
    }

    /// br-r37-c1-inedges: in_edges(data=<key>). Yields ``attrs.get(key,
    /// default)`` per edge (a value, read-only — no dirty-mark).
    fn _native_in_edges_data_key(
        &self,
        py: Python<'_>,
        key: &Bound<'_, PyAny>,
        default: PyObject,
    ) -> PyResult<PyObject> {
        let mut items = Vec::with_capacity(self.inner.edge_count());
        for target in self.inner.nodes_ordered() {
            let py_t = self.py_node_key(py, target);
            for source in self.inner.predecessors(target).unwrap_or_default() {
                let py_s = self.py_pred_key(py, target, source) /* br-r37-c1-z6uka */;
                let ek = Self::edge_key(source, target);
                let value = match self.edge_py_attrs.get(&ek) {
                    Some(d) => d
                        .bind(py)
                        .get_item(key)
                        .ok()
                        .flatten()
                        .map_or_else(|| default.clone_ref(py), |val| val.unbind()),
                    None => default.clone_ref(py),
                };
                items.push(tuple_object(py, &[py_s, py_t.clone_ref(py), value])?);
            }
        }
        Ok(items.into_pyobject(py)?.into_any().unbind())
    }

    /// br-r37-c1-vij0v: exact-DiGraph DAG longest-path snapshot primitive.
    /// Computes nx/Kahn FIFO topological order and predecessor weight groups
    /// in one native pass over the Rust adjacency, while leaving arithmetic and
    /// comparison in Python so custom weights, NaN, and TypeError behavior stay
    /// byte-compatible with NetworkX.
    fn _native_dag_topo_pred_data_key(
        &self,
        py: Python<'_>,
        key: &Bound<'_, PyAny>,
        default: PyObject,
    ) -> PyResult<PyObject> {
        let nodes = self.inner.nodes_ordered();
        let node_count = nodes.len();
        let mut node_index = HashMap::with_capacity(node_count);
        for (idx, node) in nodes.iter().copied().enumerate() {
            node_index.insert(node, idx);
        }

        let mut indegree = vec![0_usize; node_count];
        for source in nodes.iter().copied() {
            for target in self.inner.successors(source).unwrap_or_default() {
                if let Some(&target_idx) = node_index.get(target) {
                    indegree[target_idx] += 1;
                }
            }
        }

        let mut queue = VecDeque::with_capacity(node_count);
        for (idx, degree) in indegree.iter().copied().enumerate() {
            if degree == 0 {
                queue.push_back(idx);
            }
        }

        let mut topo_indices = Vec::with_capacity(node_count);
        while let Some(source_idx) = queue.pop_front() {
            topo_indices.push(source_idx);
            let source = nodes[source_idx];
            for target in self.inner.successors(source).unwrap_or_default() {
                if let Some(&target_idx) = node_index.get(target) {
                    indegree[target_idx] -= 1;
                    if indegree[target_idx] == 0 {
                        queue.push_back(target_idx);
                    }
                }
            }
        }

        if topo_indices.len() != node_count {
            return Err(crate::NetworkXUnfeasible::new_err(
                "Graph contains a cycle or graph changed during iteration",
            ));
        }

        let topo_order = topo_indices
            .iter()
            .map(|&idx| self.py_node_key(py, nodes[idx]))
            .collect::<Vec<_>>()
            .into_pyobject(py)?
            .into_any()
            .unbind();

        let mut pred_groups = Vec::with_capacity(node_count);
        for &target_idx in &topo_indices {
            let target = nodes[target_idx];
            let mut preds = Vec::new();
            for source in self.inner.predecessors(target).unwrap_or_default() {
                let py_s = self.py_pred_key(py, target, source) /* br-r37-c1-z6uka */;
                let ek = Self::edge_key(source, target);
                let value = match self.edge_py_attrs.get(&ek) {
                    Some(d) => d
                        .bind(py)
                        .get_item(key)
                        .ok()
                        .flatten()
                        .map_or_else(|| default.clone_ref(py), |val| val.unbind()),
                    None => default.clone_ref(py),
                };
                preds.push(tuple_object(py, &[py_s, value])?);
            }
            pred_groups.push(preds.into_pyobject(py)?.into_any().unbind());
        }
        let pred_groups = pred_groups.into_pyobject(py)?.into_any().unbind();
        tuple_object(py, &[topo_order, pred_groups])
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

    /// br-r37-c1-yo1nt: native total weighted degree (in + out), returning the
    /// full ``(node, total)`` sequence in node order. The Python
    /// `_WeightAwareDegreeView` weighted path builds ``dict(G.succ[node])`` +
    /// ``dict(G.pred[node])`` per node (AtlasView walk) — ~37x slower than nx.
    /// nx's `DiDegreeView` total is ``sum(<succ>) + sum(<pred>)`` — two
    /// separate Neumaier-compensated ``sum`` accumulations added — so we build
    /// the succ/pred value lists in adjacency order and call the SAME builtin
    /// ``sum`` for each, for bit-identical numeric parity.
    fn _native_weighted_degree(
        &self,
        py: Python<'_>,
        weight: &str,
    ) -> PyResult<Vec<(PyObject, PyObject)>> {
        let one = 1i64.into_pyobject(py)?.into_any();
        let sum_fn = py.import("builtins")?.getattr("sum")?;
        let mut out: Vec<(PyObject, PyObject)> = Vec::with_capacity(self.inner.node_count());
        for node in self.inner.nodes_ordered() {
            let succ_vals = pyo3::types::PyList::empty(py);
            for successor in self.inner.successors(node).unwrap_or_default() {
                let ek = Self::edge_key(node, successor);
                let value = match self.edge_py_attrs.get(&ek) {
                    Some(d) => d
                        .bind(py)
                        .get_item(weight)
                        .ok()
                        .flatten()
                        .unwrap_or_else(|| one.clone()),
                    None => one.clone(),
                };
                succ_vals.append(value)?;
            }
            let pred_vals = pyo3::types::PyList::empty(py);
            for predecessor in self.inner.predecessors(node).unwrap_or_default() {
                let ek = Self::edge_key(predecessor, node);
                let value = match self.edge_py_attrs.get(&ek) {
                    Some(d) => d
                        .bind(py)
                        .get_item(weight)
                        .ok()
                        .flatten()
                        .unwrap_or_else(|| one.clone()),
                    None => one.clone(),
                };
                pred_vals.append(value)?;
            }
            let deg = sum_fn
                .call1((succ_vals,))?
                .add(sum_fn.call1((pred_vals,))?)?;
            out.push((self.py_node_key(py, node), deg.unbind()));
        }
        Ok(out)
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

    /// br-r37-c1-5670z: O(1) native single-node out-degree, used by the Python
    /// _DirectedDegreeView fast path for the unweighted simple-graph case. The
    /// Python `len(self._adjacency[node])` path walks the per-node succ
    /// AtlasView in pure Python (O(degree)), making `list(G.out_degree())` O(E)
    /// in slow Python; `inner.out_degree` is `successors.get(node).len()`.
    fn _native_out_degree(&self, py: Python<'_>, n: &Bound<'_, PyAny>) -> PyResult<usize> {
        let canonical = node_key_to_string(py, n)?;
        Ok(self.inner.out_degree(&canonical))
    }

    /// br-r37-c1-5670z: O(1) native single-node in-degree (see _native_out_degree).
    fn _native_in_degree(&self, py: Python<'_>, n: &Bound<'_, PyAny>) -> PyResult<usize> {
        let canonical = node_key_to_string(py, n)?;
        Ok(self.inner.in_degree(&canonical))
    }

    /// br-r37-c1-snabulk: native bulk set_node_attributes(values, name)
    /// — one Rust loop over the values dict (mirror is authoritative;
    /// inner refreshed at copy/export; missing nodes skipped per nx).
    /// br-r37-c1-seabulk: native bulk set_edge_attributes(values, name)
    /// — one Rust loop over the {(u,v): value} dict instead of the
    /// Python wrapper per-edge G[u][v] resolve + setitem. Mirrors the
    /// single-edge path: has_edge gate, materialize the edge_py_attrs
    /// mirror (edge_key canonicalizes), set the key, mark_edges_dirty
    /// ONCE so the lazy _fnx_sync_attrs_to_inner flush reaches the Rust
    /// kernels. Non-2-tuple keys skipped (nx ValueError-unpack swallow).
    fn _native_set_edge_attribute_scalar(
        &mut self,
        py: Python<'_>,
        values: &Bound<'_, PyDict>,
        name: &str,
    ) -> PyResult<()> {
        for (k, val) in values.iter() {
            let Ok(len) = k.len() else { continue };
            if len != 2 {
                continue;
            }
            let u = node_key_to_string(py, &k.get_item(0)?)?;
            let v = node_key_to_string(py, &k.get_item(1)?)?;
            if self.inner.has_edge(&u, &v) {
                let dict = self
                    .edge_py_attrs
                    .entry((u, v))
                    .or_insert_with(|| PyDict::new(py).unbind());
                dict.bind(py).set_item(name, &val)?;
            }
        }
        self.mark_edges_dirty();
        Ok(())
    }

    fn _native_set_node_attribute_scalar(
        &mut self,
        py: Python<'_>,
        values: &Bound<'_, PyDict>,
        name: &str,
    ) -> PyResult<()> {
        for (k, v) in values.iter() {
            let canonical = node_key_to_string(py, &k)?;
            if self.inner.has_node(&canonical) {
                let dict = self
                    .node_py_attrs
                    .entry(canonical)
                    .or_insert_with(|| PyDict::new(py).unbind());
                dict.bind(py).set_item(name, &v)?;
            }
        }
        Ok(())
    }

    /// br-r37-c1-degidx: bulk (node, in/out-degree) pairs for the
    /// unweighted _DirectedDegreeView.__iter__ — one Rust loop by index
    /// (zero String hashing) instead of N per-node PyO3 round-trips.
    fn _native_out_degree_pairs(&self, py: Python<'_>) -> PyResult<Vec<(PyObject, usize)>> {
        let names = self.inner.nodes_ordered();
        Ok(names
            .iter()
            .enumerate()
            .map(|(i, n)| (self.py_node_key(py, n), self.inner.out_degree_by_index(i)))
            .collect())
    }

    fn _native_in_degree_pairs(&self, py: Python<'_>) -> PyResult<Vec<(PyObject, usize)>> {
        let names = self.inner.nodes_ordered();
        Ok(names
            .iter()
            .enumerate()
            .map(|(i, n)| (self.py_node_key(py, n), self.inner.in_degree_by_index(i)))
            .collect())
    }

    /// br-r37-c1-degcounts (cc): counts-only in node-index order, with NO
    /// per-node `py_node_key` PyObject rebuild. The Python degree-view zips these
    /// with the cached node list (`list(G)` via node_iter_mirror, ~0.09ms @ 20k)
    /// instead of `_native_*_degree_pairs`, which rebuilt a node object per entry
    /// — the entire unweighted in_degree/out_degree dict gap (pairs 1.5ms vs nx
    /// 1.25ms = 0.62x; zip+counts ~0.8ms = ~1.4x). `nodes_ordered()` index order
    /// == `list(G)` order (verified), so the zip is byte-identical.
    fn _native_out_degree_counts(&self) -> Vec<usize> {
        (0..self.inner.node_count())
            .map(|i| self.inner.out_degree_by_index(i))
            .collect()
    }

    fn _native_in_degree_counts(&self) -> Vec<usize> {
        (0..self.inner.node_count())
            .map(|i| self.inner.in_degree_by_index(i))
            .collect()
    }

    /// br-r37-c1-degnbnative (cc): one-pass (node, total/in/out-degree) pairs for a
    /// node subset (directed degree(nbunch)). Directed analog of
    /// PyGraph::_native_degree_pairs_subset — collapses the Python nbunch_iter
    /// membership filter + per-node native-degree PyO3 calls into one call.
    /// Unhashable element -> TypeError(exact msg) so the wrapper maps it to
    /// NetworkXError, matching nx's nbunch_iter contract.
    fn _native_degree_pairs_subset(
        &self,
        py: Python<'_>,
        nbunch: &Bound<'_, PyAny>,
    ) -> PyResult<Vec<(PyObject, usize)>> {
        self.degree_pairs_subset_impl(py, nbunch, DegreeKind::Total)
    }

    fn _native_in_degree_pairs_subset(
        &self,
        py: Python<'_>,
        nbunch: &Bound<'_, PyAny>,
    ) -> PyResult<Vec<(PyObject, usize)>> {
        self.degree_pairs_subset_impl(py, nbunch, DegreeKind::In)
    }

    fn _native_out_degree_pairs_subset(
        &self,
        py: Python<'_>,
        nbunch: &Bound<'_, PyAny>,
    ) -> PyResult<Vec<(PyObject, usize)>> {
        self.degree_pairs_subset_impl(py, nbunch, DegreeKind::Out)
    }

    /// br-r37-c1-edgenbnative (cc): one-pass (source, target) tuples for a node
    /// subset's out/in edges (data=False). Replaces the Python edges()/pred-walk
    /// machinery (per-node row-view access in a Python loop) with one native call.
    fn _native_out_edges_nbunch_no_data(
        &self,
        py: Python<'_>,
        nbunch: &Bound<'_, PyAny>,
    ) -> PyResult<Option<Vec<(PyObject, PyObject)>>> {
        self.edges_nbunch_no_data_impl(py, nbunch, true)
    }

    /// br-r37-c1-edgenbnative (cc): out_edges(nbunch, data=True) — one native pass
    /// (succ rows + live attr dict via materialize_edge_py_attrs, identity-
    /// preserving == G[u][v]) vs the EdgeDataView machinery (~0.21x). Gated on
    /// succ_py_keys empty (row display -> Python fallback). Successors collected as
    /// owned indices so the &mut materialize call has no live inner borrow.
    fn _native_out_edges_nbunch_data(
        &mut self,
        py: Python<'_>,
        nbunch: &Bound<'_, PyAny>,
    ) -> PyResult<Option<Vec<PyObject>>> {
        if !self.succ_py_keys.is_empty() {
            return Ok(None);
        }
        let mut out: Vec<PyObject> = Vec::new();
        // nx dedups repeated nbunch nodes (out_edges([1,1,2]) == out_edges([1,2])).
        let mut seen_nodes = vec![false; self.inner.node_count()];
        let py_nodes = self.cached_node_key_vec(py);
        let inner = &self.inner;
        let edge_py_attrs = &mut self.edge_py_attrs;
        for item in nbunch.try_iter()? {
            let node = item?;
            if node.hash().is_err() {
                let label = node
                    .str()
                    .map(|s| s.to_string_lossy().into_owned())
                    .unwrap_or_else(|_| "?".to_owned());
                return Err(pyo3::exceptions::PyTypeError::new_err(format!(
                    "Node {label} in sequence nbunch is not a valid node."
                )));
            }
            let canonical = node_key_to_string(py, &node)?;
            let Some(idx) = inner.get_node_index(&canonical) else {
                continue;
            };
            if seen_nodes[idx] {
                continue;
            }
            seen_nodes[idx] = true;
            let source_obj = node.clone().unbind();
            let Some(source_name) = inner.get_node_name(idx) else {
                continue;
            };
            for &nbr_idx in inner.successors_indices(idx).unwrap_or(&[]) {
                let target_name = inner
                    .get_node_name(nbr_idx)
                    .expect("successor index should resolve during out_edges");
                let nbr_obj = py_nodes[nbr_idx].clone_ref(py);
                let attrs = edge_py_attrs
                    .entry(Self::edge_key(source_name, target_name))
                    .or_insert_with(|| match inner.edge_attrs_by_indices(idx, nbr_idx) {
                        Some(attrs) => attr_map_to_pydict(py, attrs)
                            .expect("stored directed edge attrs must convert to Python"),
                        None => PyDict::new(py).unbind(),
                    })
                    .clone_ref(py)
                    .into_any();
                out.push(tuple_object(
                    py,
                    &[source_obj.clone_ref(py), nbr_obj, attrs],
                )?);
            }
        }
        if !out.is_empty() {
            self.mark_edges_dirty();
        }
        Ok(Some(out))
    }

    /// br-r37-c1-04z53 cod-b: out_edges(nbunch, data=<key>) without first
    /// materializing live attr dicts for every edge. Keeps the existing native
    /// nbunch dedup/order contract and returns final scalar projection tuples.
    fn _native_out_edges_nbunch_data_key(
        &mut self,
        py: Python<'_>,
        nbunch: &Bound<'_, PyAny>,
        data: &Bound<'_, PyAny>,
        default: PyObject,
    ) -> PyResult<Option<Vec<PyObject>>> {
        if !self.succ_py_keys.is_empty() {
            return Ok(None);
        }
        let py_nodes = self.cached_node_key_vec(py);
        let clean_string_attr = (!self.edges_dirty.load(Ordering::Relaxed))
            .then(|| data.downcast::<PyString>().ok())
            .flatten()
            .map(|s| s.to_str())
            .transpose()?;
        if let Some(attr_name) = clean_string_attr {
            let inner = &self.inner;
            let edge_py_attrs = &mut self.edge_py_attrs;
            let mut out: Vec<PyObject> = Vec::new();
            let mut seen_nodes = vec![false; self.inner.node_count()];
            for item in nbunch.try_iter()? {
                let node = item?;
                if node.hash().is_err() {
                    let label = node
                        .str()
                        .map(|s| s.to_string_lossy().into_owned())
                        .unwrap_or_else(|_| "?".to_owned());
                    return Err(pyo3::exceptions::PyTypeError::new_err(format!(
                        "Node {label} in sequence nbunch is not a valid node."
                    )));
                }
                let canonical = node_key_to_string(py, &node)?;
                let Some(idx) = inner.get_node_index(&canonical) else {
                    continue;
                };
                if seen_nodes[idx] {
                    continue;
                }
                seen_nodes[idx] = true;
                let source_obj = node.clone().unbind();
                let Some(source_name) = inner.get_node_name(idx) else {
                    continue;
                };
                for &nbr_idx in inner.successors_indices(idx).unwrap_or(&[]) {
                    let nbr_obj = py_nodes[nbr_idx].clone_ref(py);
                    let value = match inner
                        .edge_attrs_by_indices(idx, nbr_idx)
                        .and_then(|attrs| attrs.get(attr_name))
                    {
                        Some(value) if !matches!(value, CgseValue::Map(_)) => {
                            crate::cgse_value_to_py(py, value)?
                        }
                        Some(_) => {
                            let target_name = inner
                                .get_node_name(nbr_idx)
                                .expect("successor index should resolve during out_edges");
                            let attrs = edge_py_attrs
                                .entry(Self::edge_key(source_name, target_name))
                                .or_insert_with(|| {
                                    match inner.edge_attrs_by_indices(idx, nbr_idx) {
                                        Some(attrs) => attr_map_to_pydict(py, attrs).expect(
                                            "stored directed edge attrs must convert to Python",
                                        ),
                                        None => PyDict::new(py).unbind(),
                                    }
                                });
                            attrs
                                .bind(py)
                                .get_item(data)?
                                .map_or_else(|| default.clone_ref(py), |value| value.unbind())
                        }
                        None => default.clone_ref(py),
                    };
                    out.push(tuple_object(
                        py,
                        &[source_obj.clone_ref(py), nbr_obj, value],
                    )?);
                }
            }
            return Ok(Some(out));
        }
        let mut out: Vec<PyObject> = Vec::new();
        let mut seen_nodes: std::collections::HashSet<usize> = std::collections::HashSet::new();
        for item in nbunch.try_iter()? {
            let node = item?;
            if node.hash().is_err() {
                let label = node
                    .str()
                    .map(|s| s.to_string_lossy().into_owned())
                    .unwrap_or_else(|_| "?".to_owned());
                return Err(pyo3::exceptions::PyTypeError::new_err(format!(
                    "Node {label} in sequence nbunch is not a valid node."
                )));
            }
            let canonical = node_key_to_string(py, &node)?;
            let Some(idx) = self.inner.get_node_index(&canonical) else {
                continue;
            };
            if !seen_nodes.insert(idx) {
                continue;
            }
            let succ: Vec<usize> = self
                .inner
                .successors_indices(idx)
                .map(<[usize]>::to_vec)
                .unwrap_or_default();
            for nbr_idx in succ {
                let nbr_obj = py_nodes[nbr_idx].clone_ref(py);
                let target_name = self
                    .inner
                    .get_node_name(nbr_idx)
                    .expect("successor index should resolve during out_edges")
                    .to_owned();
                let value =
                    self.edge_attr_value_or_default(py, &canonical, &target_name, data, &default)?;
                out.push(tuple_object(py, &[node.clone().unbind(), nbr_obj, value])?);
            }
        }
        Ok(Some(out))
    }

    /// br-r37-c1-composedir (cc): native DiGraph compose — directional analog of
    /// PyGraph::_native_compose (which gives undirected compose 1.99x; directed
    /// fell to the Python add_nodes/add_edges replay at ~0.74x). Walks SUCCESSORS
    /// (no symmetric dedup — directed edges are unique), directional edge mirrors,
    /// and commits nodes/edges via the bulk extend_*_unrecorded APIs. Returns
    /// Ok(None) (Python fallback) when either part carries succ/pred row-display
    /// overrides — those need the per-cell maybe_store path the replay handles.
    /// node/edge order = G-nodes then H-new, succ-row order == nx's
    /// add_edges_from(G.edges()) then add_edges_from(H.edges()); H's overlapping
    /// node/edge attrs UPDATE (last-wins), matching nx.
    fn _native_compose(
        &self,
        py: Python<'_>,
        other: PyRef<'_, Self>,
    ) -> PyResult<Option<Py<Self>>> {
        if !self.succ_py_keys.is_empty()
            || !self.pred_py_keys.is_empty()
            || !other.succ_py_keys.is_empty()
            || !other.pred_py_keys.is_empty()
        {
            return Ok(None);
        }
        let mut g = Self::new_empty_with_mode(py, self.inner.mode())?;
        let merged_graph_attrs = PyDict::new(py);
        merged_graph_attrs.update(self.graph_attrs.bind(py).as_mapping())?;
        merged_graph_attrs.update(other.graph_attrs.bind(py).as_mapping())?;
        g.graph_attrs = merged_graph_attrs.unbind();
        for part in [self, &*other] {
            let nodes: Vec<String> = part
                .inner
                .nodes_ordered()
                .into_iter()
                .map(str::to_owned)
                .collect();
            let mut node_batch: Vec<(String, AttrMap)> = Vec::with_capacity(nodes.len());
            for node in &nodes {
                if let Some(attrs) = part.node_py_attrs.get(node) {
                    if let Some(existing) = g.node_py_attrs.get(node) {
                        existing.bind(py).update(attrs.bind(py).as_mapping())?;
                    } else {
                        g.node_py_attrs
                            .insert(node.clone(), attrs.bind(py).copy()?.unbind());
                    }
                }
                if let std::collections::hash_map::Entry::Vacant(e) =
                    g.node_key_map.entry(node.clone())
                {
                    e.insert(part.py_node_key(py, node));
                }
                node_batch.push((
                    node.clone(),
                    part.inner.node_attrs(node).cloned().unwrap_or_default(),
                ));
            }
            let _ = g.inner.extend_nodes_with_attrs_unrecorded(node_batch);
            let mut edge_batch: Vec<(String, String, AttrMap)> = Vec::new();
            for (ui, u) in nodes.iter().enumerate() {
                for &vi in part.inner.successors_indices(ui).unwrap_or(&[]) {
                    let v = &nodes[vi];
                    if !part.edge_py_attrs.is_empty()
                        && let Some(attrs) = part.edge_py_attrs.get(&Self::edge_key(u, v))
                    {
                        let ek = Self::edge_key(u, v);
                        if let Some(existing) = g.edge_py_attrs.get(&ek) {
                            existing.bind(py).update(attrs.bind(py).as_mapping())?;
                        } else {
                            g.edge_py_attrs.insert(ek, attrs.bind(py).copy()?.unbind());
                        }
                    }
                    edge_batch.push((
                        u.clone(),
                        v.clone(),
                        part.inner
                            .edge_attrs_by_indices(ui, vi)
                            .cloned()
                            .unwrap_or_default(),
                    ));
                }
            }
            let _ = g.inner.extend_edges_with_attrs_unrecorded(edge_batch);
        }
        Ok(Some(Py::new(py, g)?))
    }

    /// br-r37-c1-djudir (cc): native DiGraph disjoint_union — directional analog of
    /// PyGraph::_native_disjoint_union (undirected 2.03x; directed fell to the
    /// Python int-relabel + union replay at ~0.79x). Relabels BOTH parts to fresh
    /// integer ranges (0.. and n1..), so the source row-display is discarded — NO
    /// gating needed. Walks SUCCESSORS (no symmetric dedup; directed edges unique),
    /// directional edge mirrors, bulk extend_*_unrecorded. Byte-identical node/edge
    /// order to nx's disjoint_union (G then H, succ-row order).
    fn _native_disjoint_union(&self, py: Python<'_>, other: PyRef<'_, Self>) -> PyResult<Py<Self>> {
        let mut g = Self::new_empty_with_mode(py, self.inner.mode())?;
        let merged_graph_attrs = PyDict::new(py);
        merged_graph_attrs.update(self.graph_attrs.bind(py).as_mapping())?;
        merged_graph_attrs.update(other.graph_attrs.bind(py).as_mapping())?;
        g.graph_attrs = merged_graph_attrs.unbind();
        let n1 = self.inner.node_count();
        for (part, offset) in [(self, 0usize), (&*other, n1)] {
            let nodes: Vec<String> = part
                .inner
                .nodes_ordered()
                .into_iter()
                .map(str::to_owned)
                .collect();
            let index_of: std::collections::HashMap<&str, usize> = nodes
                .iter()
                .enumerate()
                .map(|(i, n)| (n.as_str(), i + offset))
                .collect();
            let mut node_batch: Vec<(String, AttrMap)> = Vec::with_capacity(nodes.len());
            for (i, node) in nodes.iter().enumerate() {
                let canonical = (i + offset).to_string();
                if let Some(attrs) = part.node_py_attrs.get(node) {
                    g.node_py_attrs
                        .insert(canonical.clone(), attrs.bind(py).copy()?.unbind());
                }
                g.node_key_map.insert(
                    canonical.clone(),
                    crate::unwrap_infallible((i + offset).into_pyobject(py))
                        .into_any()
                        .unbind(),
                );
                node_batch.push((
                    canonical,
                    part.inner.node_attrs(node).cloned().unwrap_or_default(),
                ));
            }
            let _ = g.inner.extend_nodes_with_attrs_unrecorded(node_batch);
            let mut edge_batch: Vec<(String, String, AttrMap)> = Vec::new();
            for u in &nodes {
                for v in part.inner.successors(u).unwrap_or_default() {
                    let uc = index_of[u.as_str()].to_string();
                    let vc = index_of[v].to_string();
                    if let Some(attrs) = part.edge_py_attrs.get(&Self::edge_key(u, v)) {
                        g.edge_py_attrs
                            .insert(Self::edge_key(&uc, &vc), attrs.bind(py).copy()?.unbind());
                    }
                    edge_batch.push((
                        uc,
                        vc,
                        part.inner.edge_attrs(u, v).cloned().unwrap_or_default(),
                    ));
                }
            }
            let _ = g.inner.extend_edges_with_attrs_unrecorded(edge_batch);
        }
        Py::new(py, g)
    }

    // ---- Python special methods ----

    fn __len__(&self) -> usize {
        self.inner.node_count()
    }

    fn __contains__(&self, py: Python<'_>, n: &Bound<'_, PyAny>) -> PyResult<bool> {
        let canonical = node_key_to_string(py, n)?;
        Ok(self.inner.has_node(&canonical))
    }

    fn __iter__(slf: PyRef<'_, Self>) -> PyResult<PyObject> {
        // Serve iteration from the live node_iter_mirror dict — a
        // ``dict_keyiterator`` (matching nx's ``iter(self._nodes)``) instead of
        // rebuilding a Vec<PyObject> of every display key per call. The mirror's
        // in-place mutation hooks give nx's native "changed size during
        // iteration" semantics for free.
        let py = slf.py();
        let mirror = slf.node_iter_mirror_or_init(py)?;
        Ok(mirror.bind(py).call_method0("__iter__")?.unbind())
    }

    /// ``G[n]`` — return dict of successors with edge data.
    fn __getitem__(
        slf: PyRef<'_, Self>,
        py: Python<'_>,
        n: &Bound<'_, PyAny>,
    ) -> PyResult<Py<DiAtlasView>> {
        // br-r37-c1-ozcko: return a LAZY DiAtlasView over successors instead of
        // eagerly materialising the whole `{successor: edge_attr_dict}` PyDict.
        // nx's `G[u]` is `self._adj[u]` (an AtlasView); makes `G[u][v]` /
        // `v in G[u]` O(1) and the view live (reflects later edge additions).
        let canonical = node_key_to_string(py, n)?;
        if !slf.inner.has_node(&canonical) {
            return Err(crate::missing_key_error(n));
        }
        let graph_py: Py<PyDiGraph> = Py::from(slf);
        Py::new(
            py,
            DiAtlasView::new(graph_py, canonical, AdjKind::Successors),
        )
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

    /// Support ``copy.copy(G)`` — returns a shallow copy.
    ///
    /// NetworkX parity (br-r37-c1-5ctpe): `copy.copy(G)` must share the same
    /// attribute dict references (graph, node, edge attrs are `is`, not just `==`).
    /// `G.copy()` returns a deep copy; `copy.copy(G)` returns a shallow copy.
    fn __copy__(&self, py: Python<'_>) -> PyResult<Self> {
        // br-r37-c1-o1i86: wholesale inner clone — the old rebuild iterated
        // node_key_map (HashMap, scrambled node order) and replayed edge
        // iteration order, diverging adjacency row content order from the
        // source after remove+re-add. Node/edge attr dicts are independent
        // COPIES (fnx's locked copy.copy contract — see
        // test_adj_mapping_parity; structural sharing is impossible across
        // Rust storages and the override pattern caused write-loss).
        Ok(Self {
            inner: self.inner.clone_with_fresh_policy(), // br-r37-c1-7dpyg: skip ledger
            node_key_map: self
                .node_key_map
                .iter()
                .map(|(k, v)| (k.clone(), v.clone_ref(py)))
                .collect(),
            succ_py_keys: Self::clone_row_keys(py, &self.succ_py_keys), // br-r37-c1-z6uka
            pred_py_keys: Self::clone_row_keys(py, &self.pred_py_keys), // br-r37-c1-z6uka
            succ_row_py: HashMap::new(),
            pred_row_py: HashMap::new(),
            node_py_attrs: self
                .node_py_attrs
                .iter()
                .map(|(k, v)| Ok((k.clone(), v.bind(py).copy()?.unbind())))
                .collect::<PyResult<_>>()?,
            edge_py_attrs: self
                .edge_py_attrs
                .iter()
                .map(|(k, v)| Ok((k.clone(), v.bind(py).copy()?.unbind())))
                .collect::<PyResult<_>>()?,
            // SHARE the graph attrs dict (shallow copy)
            graph_attrs: self.graph_attrs.clone_ref(py),
            nodes_seq: 0,
            edges_seq: 0,
            edges_dirty: AtomicBool::new(self.edges_dirty.load(Ordering::Relaxed)),
            node_keys_cache: std::sync::Mutex::new(None),
            node_data_mirror: std::sync::Mutex::new(None),
            dict_of_dicts_cache: None,
            edges_with_data_cache: None,
            in_edges_with_data_cache: None,
            edges_attr_dicts_cache: None,
            node_iter_mirror: std::sync::Mutex::new(None),
        })
    }

    #[pyo3(signature = (_memo=None))]
    fn __deepcopy__(&self, py: Python<'_>, _memo: Option<&Bound<'_, PyAny>>) -> PyResult<Self> {
        // br-r37-c1-z6uka: copy.deepcopy clones the dict structure verbatim,
        // so BOTH row-override maps survive (copy() re-derives pred rows
        // with node objects per nx's u-major walk — deepcopy must not).
        let mut new_graph = self.copy(py)?;
        new_graph.pred_py_keys = Self::clone_row_keys(py, &self.pred_py_keys);
        Ok(new_graph)
    }

    /// br-r37-c1-489mp: native same-type deepcopy (see PyGraph variant). VERBATIM
    /// structure via `__copy__` + deep-copied node/edge attr dicts under ONE shared
    /// memo; the Python `_graph_deepcopy` tail (routes here via hasattr) adds graph
    /// attrs, frozen flag and custom instance attrs.
    #[pyo3(signature = (memo=None))]
    fn _native_deepcopy(&self, py: Python<'_>, memo: Option<&Bound<'_, PyAny>>) -> PyResult<Self> {
        let mut new_graph = self.__copy__(py)?;
        let deepcopy = py.import("copy")?.getattr("deepcopy")?;
        let memo_obj: Bound<'_, PyAny> = match memo {
            Some(m) if !m.is_none() => m.clone(),
            _ => PyDict::new(py).into_any(),
        };
        let node_keys: Vec<String> = new_graph.node_py_attrs.keys().cloned().collect();
        for k in node_keys {
            let deep = crate::deepcopy_py_dict_memo(
                py,
                &deepcopy,
                &new_graph.node_py_attrs[&k],
                &memo_obj,
            )?;
            new_graph.node_py_attrs.insert(k, deep);
        }
        let edge_keys: Vec<(String, String)> = new_graph.edge_py_attrs.keys().cloned().collect();
        for k in edge_keys {
            let deep = crate::deepcopy_py_dict_memo(
                py,
                &deepcopy,
                &new_graph.edge_py_attrs[&k],
                &memo_obj,
            )?;
            new_graph.edge_py_attrs.insert(k, deep);
        }
        Ok(new_graph)
    }

    // ---- Pickle ----

    fn __getstate__(&self, py: Python<'_>) -> PyResult<PyObject> {
        let state = PyDict::new(py);
        state.set_item("mode", compatibility_mode_name(self.inner.mode()))?;
        state.set_item(
            "runtime_policy",
            runtime_policy_json(self.inner.runtime_policy())?,
        )?;
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

        // br-r37-c1-u3qyn: the old edge list iterated the edge_py_attrs
        // HashMap (RANDOM order — round-trip edge/row order was luck) and
        // missed attr-less edges with a sparse mirror. Emit from inner's
        // edge insertion order instead.
        let edges_list: Vec<(PyObject, PyObject, Py<PyDict>)> = self
            .inner
            .edges_ordered()
            .into_iter()
            .map(|edge| {
                let py_u = self.py_node_key(py, &edge.left);
                let py_v = self.py_node_key(py, &edge.right);
                let attrs = self
                    .edge_py_attrs
                    .get(&Self::edge_key(&edge.left, &edge.right))
                    .map_or_else(|| PyDict::new(py).unbind(), |d| d.clone_ref(py));
                (py_u, py_v, attrs)
            })
            .collect();
        state.set_item("edges", edges_list)?;
        state.set_item("graph", self.graph_attrs.bind(py))?;
        // br-r37-c1-u3qyn: store succ/pred rows + display overrides so the
        // round-trip preserves structure verbatim (see PyGraph).
        let row_dump = |pred: bool| -> Vec<(String, Vec<String>)> {
            self.inner
                .nodes_ordered()
                .into_iter()
                .map(|nd| {
                    let row = if pred {
                        self.inner.predecessors(nd)
                    } else {
                        self.inner.successors(nd)
                    };
                    (
                        nd.to_owned(),
                        row.unwrap_or_default()
                            .into_iter()
                            .map(str::to_owned)
                            .collect(),
                    )
                })
                .collect()
        };
        state.set_item("succ_rows", row_dump(false))?;
        state.set_item("pred_rows", row_dump(true))?;
        let dump_overrides = |m: &HashMap<(String, String), PyObject>| {
            m.iter()
                .map(|((a, b), o)| (a.clone(), b.clone(), o.clone_ref(py)))
                .collect::<Vec<(String, String, PyObject)>>()
        };
        if !self.succ_py_keys.is_empty() {
            state.set_item("succ_py_keys", dump_overrides(&self.succ_py_keys))?;
        }
        if !self.pred_py_keys.is_empty() {
            state.set_item("pred_py_keys", dump_overrides(&self.pred_py_keys))?;
        }
        Ok(state.into_any().unbind())
    }

    fn __setstate__(&mut self, py: Python<'_>, state: &Bound<'_, PyDict>) -> PyResult<()> {
        let mode = compatibility_mode_from_py(state.get_item("mode")?.as_ref())?;
        self.inner = DiGraph::with_runtime_policy(runtime_policy_from_state(state, mode)?);
        self.node_key_map.clear();
        self.node_py_attrs.clear();
        self.edge_py_attrs.clear();
        self.succ_py_keys.clear(); // br-r37-c1-u3qyn
        self.pred_py_keys.clear(); // br-r37-c1-u3qyn
        self.graph_attrs = PyDict::new(py).unbind();

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

        // br-r37-c1-u3qyn: restore exact succ/pred row order and display
        // overrides when the state carries them (optional, back-compat).
        if let Some(rows) = state.get_item("succ_rows")? {
            let orders: Vec<(String, Vec<String>)> = rows.extract()?;
            self.inner.apply_row_orders(&orders, false);
        }
        if let Some(rows) = state.get_item("pred_rows")? {
            let orders: Vec<(String, Vec<String>)> = rows.extract()?;
            self.inner.apply_row_orders(&orders, true);
        }
        if let Some(overrides) = state.get_item("succ_py_keys")? {
            let entries: Vec<(String, String, PyObject)> = overrides.extract()?;
            for (a, b, o) in entries {
                self.succ_py_keys.insert((a, b), o);
            }
        }
        if let Some(overrides) = state.get_item("pred_py_keys")? {
            let entries: Vec<(String, String, PyObject)> = overrides.extract()?;
            for (a, b, o) in entries {
                self.pred_py_keys.insert((a, b), o);
            }
        }

        Ok(())
    }
}

// ===========================================================================
// DiGraph views
// ===========================================================================

enum ViewData {
    NoData,
    AllData,
    Attr(String),
    AttrWithDefault(String, PyObject),
}

impl Clone for ViewData {
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

fn parse_edge_nbunch_for_multidigraph(
    py: Python<'_>,
    graph: &PyMultiDiGraph,
    nbunch: Option<&Bound<'_, PyAny>>,
) -> PyResult<Option<Vec<String>>> {
    let Some(nbunch) = nbunch else {
        return Ok(None);
    };

    if let Ok(canonical) = node_key_to_string(py, nbunch)
        && graph.inner.has_node(&canonical)
    {
        return Ok(Some(vec![canonical]));
    }

    match PyIterator::from_object(nbunch) {
        Ok(iter) => {
            // nx's nbunch_iter walks nbunch in user-given order, yields each
            // present node once (first occurrence), skipping missing nodes.
            // Preserve that order + first-occurrence dedup so edges(nbunch)
            // matches nx's OutMultiEdgeView ordering exactly.
            let mut nodes: Vec<String> = Vec::new();
            let mut seen: HashSet<String> = HashSet::new();
            for item in iter {
                let item = item?;
                if let Err(exc) = item.hash() {
                    if exc.is_instance_of::<PyTypeError>(py) {
                        let display = item.str()?.to_string_lossy().into_owned();
                        return Err(NetworkXError::new_err(format!(
                            "Node {} in sequence nbunch is not a valid node.",
                            display
                        )));
                    }
                    return Err(exc);
                }
                let canonical = node_key_to_string(py, &item)?;
                if graph.inner.has_node(&canonical) && seen.insert(canonical.clone()) {
                    nodes.push(canonical);
                }
            }
            Ok(Some(nodes))
        }
        Err(exc) => {
            if exc.is_instance_of::<PyTypeError>(py) {
                let display = nbunch.str()?.to_string_lossy().into_owned();
                Err(NetworkXError::new_err(format!(
                    "Node {} is not in the graph.",
                    display
                )))
            } else {
                Err(NetworkXError::new_err(
                    "nbunch is not a node or a sequence of nodes.",
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

    fn __iter__(&self, py: Python<'_>) -> PyResult<PyObject> {
        // NoData (list(G.nodes()) / for n in G.nodes()) serves the SAME live
        // node_iter_mirror dict that PyDiGraph.__iter__ uses -> a
        // ``dict_keyiterator`` (matching nx) in O(1) instead of rebuilding a
        // Vec<PyObject> of every display key per call (was 15x slower than nx).
        if matches!(self.data, ViewData::NoData) {
            let mirror = self.graph.borrow(py).node_iter_mirror_or_init(py)?;
            return Ok(mirror.bind(py).call_method0("__iter__")?.unbind());
        }
        let g = self.graph.borrow(py);
        let nodes: Vec<String> = g
            .inner
            .nodes_ordered()
            .into_iter()
            .map(str::to_owned)
            .collect();
        let items: Vec<PyObject> = match &self.data {
            ViewData::NoData => unreachable!("NoData handled above"),
            ViewData::AllData => nodes
                .iter()
                .map(|n| {
                    let py_key = g.py_node_key(py, n);
                    let attrs = g
                        .node_py_attrs
                        .get(n)
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
                        .get(n)
                        .and_then(|dict| dict.bind(py).get_item(attr.as_str()).ok().flatten())
                        .map_or_else(|| py.None(), |v| v.unbind());
                    tuple_object(py, &[py_key, val])
                })
                .collect::<PyResult<Vec<_>>>()?,
            ViewData::AttrWithDefault(attr, def_val) => nodes
                .iter()
                .map(|n| {
                    let py_key = g.py_node_key(py, n);
                    let val = g
                        .node_py_attrs
                        .get(n)
                        .and_then(|dict| dict.bind(py).get_item(attr.as_str()).ok().flatten())
                        .map_or_else(|| def_val.clone_ref(py), |v| v.unbind());
                    tuple_object(py, &[py_key, val])
                })
                .collect::<PyResult<Vec<_>>>()?,
        };
        Ok(Py::new(
            py,
            DiViewIterator {
                inner: items.into_iter(),
                graph: Some(self.graph.clone_ref(py)),
                expected_count: Some(nodes.len()),
                expected_seq: Some(g.nodes_seq),
            },
        )?
        .into_any())
    }

    fn __getitem__(&self, py: Python<'_>, n: &Bound<'_, PyAny>) -> PyResult<Py<PyDict>> {
        let mut g = self.graph.borrow_mut(py);
        let canonical = node_key_to_string(py, n)?;
        if !g.inner.has_node(&canonical) {
            return Err(crate::missing_key_error(n));
        }
        // br-r37-c1-d58s8: MATERIALIZE absent mirrors (lazy-mirror paths
        // produce none) — a fresh unstored dict silently loses writes.
        Ok(g.node_py_attrs
            .entry(canonical)
            .or_insert_with(|| PyDict::new(py).unbind())
            .clone_ref(py))
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
        // br-r37-c1-d58s8: materialize absent mirrors (write-through).
        Ok(g.node_py_attrs
            .entry(canonical)
            .or_insert_with(|| PyDict::new(py).unbind())
            .clone_ref(py)
            .into_any())
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
        let mut view_data = parse_view_data(data)?;
        if let (Some(def), ViewData::Attr(attr)) = (default, &view_data) {
            view_data = ViewData::AttrWithDefault(attr.clone(), def.clone().unbind());
        }
        Py::new(
            py,
            DiNodeView {
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

    /// Return (node, attrs) pairs (like dict.items()).
    /// br-r37-c1-4b5ie: serve from the nodes_seq-keyed node_data_mirror
    /// (mirror of Graph's NodeView.items) so repeated nodes(data=...) calls on
    /// an unchanged graph reuse the cached {node: attr_dict} dict instead of
    /// rebuilding every (node, dict) pair.
    fn items(&self, py: Python<'_>) -> PyResult<PyObject> {
        let mut g = self.graph.borrow_mut(py);
        g.node_data_items_view(py)
    }

    /// Return a list of attr dicts (like dict.values()).
    fn values(&self, py: Python<'_>) -> PyResult<Vec<PyObject>> {
        let g = self.graph.borrow(py);
        Ok(g.inner
            .nodes_ordered()
            .iter()
            .map(|n| {
                g.node_py_attrs.get(*n).map_or_else(
                    || PyDict::new(py).into_any().unbind(),
                    |d| d.clone_ref(py).into_any(),
                )
            })
            .collect())
    }

    /// Return a NodeDataView for iterating over (node, data) pairs.
    #[pyo3(signature = (data=None, default=None))]
    fn data(
        &self,
        py: Python<'_>,
        data: Option<&Bound<'_, PyAny>>,
        default: Option<&Bound<'_, PyAny>>,
    ) -> PyResult<Py<DiNodeView>> {
        let view_data = if let Some(d) = data {
            if d.is_truthy()? {
                if let Ok(s) = d.extract::<String>() {
                    if let Some(def) = default {
                        ViewData::AttrWithDefault(s, def.clone().unbind())
                    } else {
                        ViewData::Attr(s)
                    }
                } else {
                    ViewData::AllData
                }
            } else {
                ViewData::AllData
            }
        } else {
            ViewData::AllData
        };
        Py::new(
            py,
            DiNodeView {
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
        for item in pyo3::types::PyIterator::from_object(other)? {
            self_set.add(item?)?;
        }
        Ok(self_set.into_any().unbind())
    }

    /// Intersection: self & other
    fn __and__(&self, py: Python<'_>, other: &Bound<'_, PyAny>) -> PyResult<PyObject> {
        let g = self.graph.borrow(py);
        let other_vec: Vec<PyObject> = pyo3::types::PyIterator::from_object(other)?
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
        let other_vec: Vec<PyObject> = pyo3::types::PyIterator::from_object(other)?
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
        let other_vec: Vec<PyObject> = pyo3::types::PyIterator::from_object(other)?
            .map(|r| r.map(|o| o.unbind()))
            .collect::<PyResult<Vec<_>>>()?;
        let other_set = pyo3::types::PySet::new(py, other_vec.iter())?;
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
        let mut g = self.graph.borrow_mut(py);
        if matches!(&self.data, ViewData::AllData) && g.inner.edge_count() > 0 {
            g.mark_edges_dirty();
        }
        // br-r37-c1-divit: only the node_count + nodes_seq are needed for the
        // O(1) per-next staleness check, not a full nodes_ordered() Vec.
        let node_count = g.inner.node_count();
        let nodes_seq = g.nodes_seq;
        let edges: Vec<(String, String)> = g
            .inner
            .edges_ordered_borrowed()
            .into_iter()
            .map(|(u, v, _)| (u.to_owned(), v.to_owned()))
            .collect();
        let mut items = Vec::with_capacity(edges.len());
        for (u, v) in edges {
            let py_u = g.py_node_key(py, &u);
            let py_v = g.py_node_key(py, &v);
            let item = match &self.data {
                ViewData::NoData => tuple_object(py, &[py_u, py_v]),
                ViewData::AllData => {
                    let a: PyObject = g.materialize_edge_py_attrs(py, &u, &v).into_any();
                    tuple_object(py, &[py_u, py_v, a])
                }
                ViewData::Attr(attr_name) => {
                    let attrs = g.materialize_edge_py_attrs(py, &u, &v);
                    let val = attrs
                        .bind(py)
                        .get_item(attr_name.as_str())
                        .ok()
                        .flatten()
                        .map_or_else(|| py.None(), |v| v.unbind());
                    tuple_object(py, &[py_u, py_v, val])
                }
                ViewData::AttrWithDefault(attr_name, def_val) => {
                    let attrs = g.materialize_edge_py_attrs(py, &u, &v);
                    let val = attrs
                        .bind(py)
                        .get_item(attr_name.as_str())
                        .ok()
                        .flatten()
                        .map_or_else(|| def_val.clone_ref(py), |v| v.unbind());
                    tuple_object(py, &[py_u, py_v, val])
                }
            }?;
            items.push(item);
        }
        Py::new(
            py,
            DiViewIterator {
                inner: items.into_iter(),
                graph: Some(self.graph.clone_ref(py)),
                expected_count: Some(node_count),
                expected_seq: Some(nodes_seq),
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
        g.mark_edges_dirty();
        drop(g);
        let mut g = self.graph.borrow_mut(py);
        Ok(g.materialize_edge_py_attrs(py, &u, &v))
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
        if let Some(nb) = nbunch {
            let iter = PyIterator::from_object(nb)?;
            let g = self.graph.borrow(py);
            let mut node_set: std::collections::HashSet<String> = std::collections::HashSet::new();
            for item in iter {
                let item = item?;
                node_set.insert(node_key_to_string(py, &item)?);
            }
            let mut view_data = parse_view_data(data)?;
            if let (Some(def), ViewData::Attr(attr)) = (default, &view_data) {
                view_data = ViewData::AttrWithDefault(attr.clone(), def.clone().unbind());
            }
            if matches!(&view_data, ViewData::AllData) && g.inner.edge_count() > 0 {
                g.mark_edges_dirty();
            }
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
                        ViewData::AttrWithDefault(attr_name, def_val) => {
                            let val = attrs
                                .bind(py)
                                .get_item(attr_name.as_str())
                                .ok()
                                .flatten()
                                .map_or_else(|| def_val.clone_ref(py), |v| v.unbind());
                            tuple_object(py, &[py_u, py_v, val])
                        }
                    }
                })
                .collect::<PyResult<Vec<_>>>()?;
            Ok(items.into_pyobject(py)?.into_any().unbind())
        } else {
            let mut view_data = parse_view_data(data)?;
            if let (Some(def), ViewData::Attr(attr)) = (default, &view_data) {
                view_data = ViewData::AttrWithDefault(attr.clone(), def.clone().unbind());
            }
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

    // br-r37-c1-degidx: O(1) by-index, no String hashing.
    fn node_degree_by_index(&self, g: &PyDiGraph, idx: usize) -> usize {
        match self.kind {
            DegreeKind::Total => g.inner.degree_by_index(idx),
            DegreeKind::In => g.inner.in_degree_by_index(idx),
            DegreeKind::Out => g.inner.out_degree_by_index(idx),
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
            .enumerate()
            .map(|(i, n)| {
                let py_key = g.py_node_key(py, n);
                let deg = self.node_degree_by_index(&g, i);
                let py_degree = unwrap_infallible(deg.into_pyobject(py)).into_any().unbind();
                tuple_object(py, &[py_key, py_degree])
            })
            .collect::<PyResult<Vec<_>>>()?;
        Py::new(
            py,
            DiViewIterator {
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

    /// Make DiDegreeView callable like NetworkX: G.degree() returns self,
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
            let deg = view.node_degree(&g, &canonical);
            return Ok(deg.into_pyobject(py)?.into_any().unbind());
        }

        // Try as iterable of nodes
        if let Ok(iter) = PyIterator::from_object(nb) {
            let mut items: Vec<PyObject> = Vec::new();
            for item in iter {
                let item = item?;
                let canonical = node_key_to_string(py, &item)?;
                if !g.inner.has_node(&canonical) {
                    return Err(NodeNotFound::new_err(format!(
                        "The node {} is not in the graph.",
                        item.repr()?
                    )));
                }
                let deg = view.node_degree(&g, &canonical);
                let py_key = g.py_node_key(py, &canonical);
                let py_degree = deg.into_pyobject(py)?.into_any().unbind();
                items.push(tuple_object(py, &[py_key, py_degree])?);
            }
            return Ok(items.into_pyobject(py)?.into_any().unbind());
        }

        // Neither a node nor iterable - error
        Err(NodeNotFound::new_err(format!(
            "The node {} is not in the graph.",
            nb.repr()?
        )))
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

    fn __getitem__(&self, py: Python<'_>, n: &Bound<'_, PyAny>) -> PyResult<Py<DiAtlasView>> {
        // br-r37-c1-ozcko: `G.succ[u]` / `G.pred[u]` return the same lazy
        // DiAtlasView as `G[u]` (was an eager O(degree) PyDict materialisation).
        let canonical = node_key_to_string(py, n)?;
        if !self.graph.borrow(py).inner.has_node(&canonical) {
            return Err(crate::missing_key_error(n));
        }
        Py::new(
            py,
            DiAtlasView::new(self.graph.clone_ref(py), canonical, self.kind),
        )
    }

    fn __iter__(&self, py: Python<'_>) -> PyResult<Py<crate::NodeIterator>> {
        let g = self.graph.borrow(py);
        let nodes: Vec<PyObject> = g
            .inner
            .nodes_ordered()
            .into_iter()
            .map(|n| g.py_node_key(py, n))
            .collect();
        Py::new(py, crate::NodeIterator::unguarded(nodes))
    }

    fn __bool__(&self, py: Python<'_>) -> bool {
        self.graph.borrow(py).inner.node_count() > 0
    }
}

// ---------------------------------------------------------------------------
// DiAtlasView — lazy view of ONE node's successor (or predecessor) adjacency
// ({neighbour: edge_attr_dict}), returned by `G[u]` / `G.succ[u]` / `G.pred[u]`
// for a DiGraph. Directed analogue of `views::AtlasView` (br-r37-c1-ozcko): the
// previous `__getitem__` EAGERLY materialised the whole neighbour dict
// (O(out/in-degree)); this makes `G[u][v]` and `v in G[u]` O(1) and is LIVE
// (reflects later edge additions) like networkx's AtlasView.
// ---------------------------------------------------------------------------
#[pyclass(module = "franken_networkx", mapping)]
pub struct DiAtlasView {
    graph: Py<PyDiGraph>,
    node: String,
    kind: AdjKind,
}

impl DiAtlasView {
    fn new(graph: Py<PyDiGraph>, node: String, kind: AdjKind) -> Self {
        Self { graph, node, kind }
    }

    /// Materialise the full `{neighbour: shared_edge_attr_dict}` (O(degree)) —
    /// only when a materialising method (items/values/==/str/repr) is called.
    fn materialize(&self, py: Python<'_>) -> PyResult<Py<PyDict>> {
        let mut g = self.graph.borrow_mut(py);
        let neighbors = match self.kind {
            AdjKind::Successors => g.inner.successors(&self.node).unwrap_or_default(),
            AdjKind::Predecessors => g.inner.predecessors(&self.node).unwrap_or_default(),
        }
        .into_iter()
        .map(str::to_owned)
        .collect::<Vec<_>>();
        let result = PyDict::new(py);
        for nb in &neighbors {
            let py_nb = match self.kind {
                // br-r37-c1-z6uka
                AdjKind::Successors => g.py_succ_key(py, &self.node, nb),
                AdjKind::Predecessors => g.py_pred_key(py, &self.node, nb),
            };
            let edge_attrs = match self.kind {
                AdjKind::Successors => g.materialize_edge_py_attrs(py, &self.node, nb),
                AdjKind::Predecessors => g.materialize_edge_py_attrs(py, nb, &self.node),
            };
            result.set_item(py_nb, edge_attrs.bind(py))?;
        }
        Ok(result.unbind())
    }
}

#[pymethods]
impl DiAtlasView {
    fn __getitem__(&self, py: Python<'_>, v: &Bound<'_, PyAny>) -> PyResult<Py<PyDict>> {
        let g = self.graph.borrow(py);
        let v_canon = node_key_to_string(py, v)?;
        let exists = match self.kind {
            AdjKind::Successors => g.inner.has_edge(&self.node, &v_canon),
            AdjKind::Predecessors => g.inner.has_edge(&v_canon, &self.node),
        };
        if !exists {
            return Err(PyKeyError::new_err((v.clone().unbind(),)));
        }
        // Returned dict is the SAME shared Py<PyDict> the graph stores, so
        // `G[u][v]['w'] = x` mutates live edge attrs — flag dirty.
        // br-r37-c1-d58s8: MATERIALIZE absent mirrors (lazy-mirror paths
        // produce none) — a fresh unstored dict silently loses writes.
        g.mark_edges_dirty();
        drop(g);
        let mut g = self.graph.borrow_mut(py);
        match self.kind {
            AdjKind::Successors => Ok(g.materialize_edge_py_attrs(py, &self.node, &v_canon)),
            AdjKind::Predecessors => Ok(g.materialize_edge_py_attrs(py, &v_canon, &self.node)),
        }
    }

    fn __contains__(&self, py: Python<'_>, v: &Bound<'_, PyAny>) -> PyResult<bool> {
        let g = self.graph.borrow(py);
        let v_canon = node_key_to_string(py, v)?;
        Ok(match self.kind {
            AdjKind::Successors => g.inner.has_edge(&self.node, &v_canon),
            AdjKind::Predecessors => g.inner.has_edge(&v_canon, &self.node),
        })
    }

    fn __len__(&self, py: Python<'_>) -> usize {
        let g = self.graph.borrow(py);
        match self.kind {
            AdjKind::Successors => g.inner.out_degree(&self.node),
            AdjKind::Predecessors => g.inner.in_degree(&self.node),
        }
    }

    fn __iter__(&self, py: Python<'_>) -> PyResult<PyObject> {
        let row = {
            let mut g = self.graph.borrow_mut(py);
            match self.kind {
                AdjKind::Successors => g.successor_row_dict_by_canonical(py, &self.node)?,
                AdjKind::Predecessors => g.predecessor_row_dict_by_canonical(py, &self.node)?,
            }
        };
        Ok(row.bind(py).call_method0("__iter__")?.unbind())
    }

    fn keys(&self, py: Python<'_>) -> PyResult<PyObject> {
        self.__iter__(py)
    }

    fn items(&self, py: Python<'_>) -> PyResult<Vec<(PyObject, Py<PyDict>)>> {
        let mut g = self.graph.borrow_mut(py);
        let neighbors = match self.kind {
            AdjKind::Successors => g.inner.successors(&self.node).unwrap_or_default(),
            AdjKind::Predecessors => g.inner.predecessors(&self.node).unwrap_or_default(),
        }
        .into_iter()
        .map(str::to_owned)
        .collect::<Vec<_>>();
        let mut out = Vec::with_capacity(neighbors.len());
        for nb in &neighbors {
            let py_nb = match self.kind {
                // br-r37-c1-z6uka
                AdjKind::Successors => g.py_succ_key(py, &self.node, nb),
                AdjKind::Predecessors => g.py_pred_key(py, &self.node, nb),
            };
            let ed = match self.kind {
                AdjKind::Successors => g.materialize_edge_py_attrs(py, &self.node, nb),
                AdjKind::Predecessors => g.materialize_edge_py_attrs(py, nb, &self.node),
            };
            out.push((py_nb, ed));
        }
        Ok(out)
    }

    fn values(&self, py: Python<'_>) -> PyResult<Vec<Py<PyDict>>> {
        Ok(self.items(py)?.into_iter().map(|(_, d)| d).collect())
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

    /// nx ``AtlasView.copy`` -> ``{n: self[n].copy()}``.
    fn copy(&self, py: Python<'_>) -> PyResult<Py<PyDict>> {
        let mut g = self.graph.borrow_mut(py);
        let neighbors = match self.kind {
            AdjKind::Successors => g.inner.successors(&self.node).unwrap_or_default(),
            AdjKind::Predecessors => g.inner.predecessors(&self.node).unwrap_or_default(),
        }
        .into_iter()
        .map(str::to_owned)
        .collect::<Vec<_>>();
        let result = PyDict::new(py);
        for nb in &neighbors {
            let py_nb = match self.kind {
                // br-r37-c1-z6uka
                AdjKind::Successors => g.py_succ_key(py, &self.node, nb),
                AdjKind::Predecessors => g.py_pred_key(py, &self.node, nb),
            };
            let attrs = match self.kind {
                AdjKind::Successors => g.materialize_edge_py_attrs(py, &self.node, nb),
                AdjKind::Predecessors => g.materialize_edge_py_attrs(py, nb, &self.node),
            };
            let copied = attrs.bind(py).copy()?.unbind();
            result.set_item(py_nb, copied)?;
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
// Shared view iterator
// ---------------------------------------------------------------------------

#[pyclass]
pub struct DiViewIterator {
    inner: std::vec::IntoIter<PyObject>,
    graph: Option<Py<PyDiGraph>>,
    // br-r37-c1-divit: snapshot node_count + nodes_seq for an O(1) staleness
    // check per next(), mirroring the undirected NodeViewIterator
    // (br-gauntlet-perf-nodeviewiter). The previous `Vec<String>` rebuilt
    // nodes_ordered() and compared every element on EVERY next() — O(N^2) to
    // iterate a DiGraph view.
    expected_count: Option<usize>,
    expected_seq: Option<u64>,
}

#[pymethods]
impl DiViewIterator {
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
            // br-r37-c1-divit: O(1) mutation-counter check. add_node / remove_node
            // bumps nodes_seq; only when it changes do we disambiguate
            // size-change vs key-permutation via node_count, preserving the exact
            // Python-dict error wording. Equivalent to the prior O(N) per-next
            // nodes_ordered() rebuild + element compare.
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

#[pyclass]
pub struct DiGraphGuardedEdgeListIter {
    graph: Py<PyDiGraph>,
    items: PyObject,
    index: usize,
    len: usize,
    expected_nodes_seq: u64,
    expected_edges_seq: u64,
}

#[pymethods]
impl DiGraphGuardedEdgeListIter {
    fn __iter__(slf: PyRef<'_, Self>) -> PyRef<'_, Self> {
        slf
    }

    fn __next__(mut slf: PyRefMut<'_, Self>) -> PyResult<Option<PyObject>> {
        if slf.index >= slf.len {
            return Ok(None);
        }
        let py = slf.py();
        {
            let graph = slf.graph.borrow(py);
            if graph.nodes_seq != slf.expected_nodes_seq
                || graph.edges_seq != slf.expected_edges_seq
            {
                return Err(PyRuntimeError::new_err(
                    "dictionary changed size during iteration",
                ));
            }
        }
        let item = slf.items.bind(py).get_item(slf.index)?.unbind();
        slf.index += 1;
        Ok(Some(item))
    }
}

#[pyclass]
pub struct DiGraphGuardedEdgeStreamIter {
    graph: Py<PyDiGraph>,
    node_keys: Py<PyTuple>,
    node_idx: usize,
    succ_idx: usize,
    node_count: usize,
    expected_nodes_seq: u64,
    expected_edges_seq: u64,
}

#[pymethods]
impl DiGraphGuardedEdgeStreamIter {
    fn __iter__(slf: PyRef<'_, Self>) -> PyRef<'_, Self> {
        slf
    }

    fn __next__(mut slf: PyRefMut<'_, Self>) -> PyResult<Option<PyObject>> {
        if slf.node_idx >= slf.node_count {
            return Ok(None);
        }

        let py = slf.py();
        let graph_py = slf.graph.clone_ref(py);
        let mut node_idx = slf.node_idx;
        let mut succ_idx = slf.succ_idx;
        let node_count = slf.node_count;
        let edge = {
            let graph = graph_py.borrow(py);
            if graph.nodes_seq != slf.expected_nodes_seq
                || graph.edges_seq != slf.expected_edges_seq
            {
                return Err(PyRuntimeError::new_err(
                    "dictionary changed size during iteration",
                ));
            }

            let mut found = None;
            while node_idx < node_count {
                if let Some(successors) = graph.inner.successors_indices(node_idx)
                    && succ_idx < successors.len()
                {
                    let target_idx = successors[succ_idx];
                    succ_idx += 1;
                    found = Some((node_idx, target_idx));
                    break;
                }
                node_idx += 1;
                succ_idx = 0;
            }
            found
        };

        slf.node_idx = node_idx;
        slf.succ_idx = succ_idx;

        let Some((source_idx, target_idx)) = edge else {
            slf.node_idx = slf.node_count;
            return Ok(None);
        };

        let keys = slf.node_keys.bind(py);
        let source = keys.get_item(source_idx)?.unbind();
        let target = keys.get_item(target_idx)?.unbind();
        Ok(Some(tuple_object(py, &[source, target])?))
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
    m.add_class::<DiAtlasView>()?;
    m.add_class::<DiViewIterator>()?;
    m.add_class::<DiGraphGuardedEdgeListIter>()?;
    m.add_class::<DiGraphGuardedEdgeStreamIter>()?;
    // MultiDiGraph views
    m.add_class::<MultiDiGraphNodeView>()?;
    m.add_class::<MultiDiGraphEdgeView>()?;
    m.add_class::<MultiDiGraphDegreeView>()?;
    m.add_class::<MultiDiAtlasView>()?;
    m.add_class::<MultiDiKeyDictView>()?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use fnx_runtime::{CompatibilityMode, RuntimePolicy};

    fn ensure_python() {
        Python::initialize();
    }

    fn seeded_digraph_policy() -> RuntimePolicy {
        let mut graph = DiGraph::new(CompatibilityMode::Hardened);
        graph.add_node("seed".to_owned());
        graph.runtime_policy().clone()
    }

    fn seeded_multidigraph_policy() -> RuntimePolicy {
        let mut graph = MultiDiGraph::new(CompatibilityMode::Hardened);
        graph.add_node("seed".to_owned());
        graph.runtime_policy().clone()
    }

    #[test]
    fn digraph_new_empty_with_policy_preserves_runtime_policy_state() {
        ensure_python();
        Python::attach(|py| {
            let expected_policy = seeded_digraph_policy();
            let graph = PyDiGraph::new_empty_with_policy(py, expected_policy.clone())
                .expect("digraph should initialize");
            assert_eq!(graph.inner.runtime_policy(), &expected_policy);
        });
    }

    #[test]
    fn digraph_clear_preserves_runtime_policy_state() {
        ensure_python();
        Python::attach(|py| {
            let expected_policy = seeded_digraph_policy();
            let mut graph = PyDiGraph::new_empty_with_policy(py, expected_policy.clone())
                .expect("digraph should initialize");

            graph.clear(py).expect("clear should succeed");

            assert_eq!(graph.inner.runtime_policy(), &expected_policy);
        });
    }

    #[test]
    fn multidigraph_clear_edges_preserves_runtime_policy_state() {
        ensure_python();
        Python::attach(|py| {
            let expected_policy = seeded_multidigraph_policy();
            let mut graph = PyMultiDiGraph::new_empty_with_policy(py, expected_policy.clone())
                .expect("multidigraph should initialize");

            graph.clear_edges();

            assert_eq!(graph.inner.runtime_policy(), &expected_policy);
        });
    }

    #[test]
    fn digraph_pickle_state_roundtrips_runtime_policy_state() {
        ensure_python();
        Python::attach(|py| {
            let expected_policy = seeded_digraph_policy();
            let graph = PyDiGraph::new_empty_with_policy(py, expected_policy.clone())
                .expect("digraph should initialize");

            let state = graph
                .__getstate__(py)
                .expect("state export should succeed")
                .into_bound(py)
                .downcast_into::<PyDict>()
                .expect("state should be a dict");
            let mode = state
                .get_item("mode")
                .expect("dict lookup should succeed")
                .expect("mode should be present")
                .extract::<String>()
                .expect("mode should be a string");
            assert_eq!(mode, "hardened");
            assert!(
                state
                    .get_item("runtime_policy")
                    .expect("dict lookup should succeed")
                    .is_some(),
                "runtime policy should be serialized"
            );

            let mut restored = PyDiGraph::new(py, None, None).expect("digraph should initialize");
            restored
                .__setstate__(py, &state)
                .expect("state import should succeed");

            assert_eq!(restored.inner.runtime_policy(), &expected_policy);
        });
    }

    #[test]
    fn digraph_constructor_copy_preserves_runtime_policy_state() {
        ensure_python();
        Python::attach(|py| {
            let expected_policy = seeded_digraph_policy();
            let source = Py::new(
                py,
                PyDiGraph::new_empty_with_policy(py, expected_policy.clone())
                    .expect("digraph should initialize"),
            )
            .expect("py digraph should initialize");

            let copied = PyDiGraph::new(py, Some(source.bind(py).as_any()), None)
                .expect("copy construction should succeed");

            // br-r37-c1-ymeml: __new__ no longer absorbs graph-instance
            // inputs (the Python __init__ owns population and always
            // rebuilt them anyway) — it returns an EMPTY graph carrying
            // the source's compatibility mode.
            assert_eq!(copied.inner.mode(), CompatibilityMode::Hardened);
            assert_eq!(copied.inner.node_count(), 0);
        });
    }

    #[test]
    fn multidigraph_reverse_preserves_runtime_policy_state() {
        ensure_python();
        Python::attach(|py| {
            let expected_policy = seeded_multidigraph_policy();
            let graph = PyMultiDiGraph::new_empty_with_policy(py, expected_policy.clone())
                .expect("multidigraph should initialize");

            let reversed = graph.reverse(py).expect("reverse should succeed");

            assert_eq!(reversed.inner.runtime_policy(), &expected_policy);
        });
    }

    #[test]
    fn digraph_reverse_preserves_networkx_edge_iteration_order() {
        ensure_python();
        Python::attach(|py| {
            let mut graph = PyDiGraph::new_empty_with_policy(py, RuntimePolicy::default())
                .expect("digraph should initialize");
            for (left, right) in [("c", "d"), ("a", "b"), ("b", "c"), ("d", "a"), ("c", "a")] {
                graph
                    .inner
                    .add_edge(left.to_owned(), right.to_owned())
                    .expect("edge add should succeed");
            }

            let reversed = graph.reverse(py).expect("reverse should succeed");
            let edges = reversed
                .inner
                .edges_ordered()
                .into_iter()
                .map(|edge| (edge.left, edge.right))
                .collect::<Vec<_>>();

            assert_eq!(
                edges,
                vec![
                    ("c".to_owned(), "b".to_owned()),
                    ("d".to_owned(), "c".to_owned()),
                    ("a".to_owned(), "c".to_owned()),
                    ("a".to_owned(), "d".to_owned()),
                    ("b".to_owned(), "a".to_owned()),
                ]
            );
        });
    }

    #[test]
    fn multidigraph_reverse_preserves_networkx_edge_key_order() {
        ensure_python();
        Python::attach(|py| {
            let mut graph = PyMultiDiGraph::new_empty_with_policy(py, RuntimePolicy::default())
                .expect("multidigraph should initialize");
            graph
                .inner
                .add_edge("a".to_owned(), "b".to_owned())
                .expect("edge add should succeed");
            graph
                .inner
                .add_edge("a".to_owned(), "b".to_owned())
                .expect("edge add should succeed");
            graph
                .inner
                .add_edge("b".to_owned(), "c".to_owned())
                .expect("edge add should succeed");

            let reversed = graph.reverse(py).expect("reverse should succeed");
            let edges = reversed
                .inner
                .edges_ordered()
                .into_iter()
                .map(|edge| (edge.source, edge.target, edge.key))
                .collect::<Vec<_>>();

            assert_eq!(
                edges,
                vec![
                    ("b".to_owned(), "a".to_owned(), 0),
                    ("b".to_owned(), "a".to_owned(), 1),
                    ("c".to_owned(), "b".to_owned(), 0),
                ]
            );
        });
    }

    #[test]
    fn multidigraph_pickle_state_roundtrips_runtime_policy_state() {
        ensure_python();
        Python::attach(|py| {
            let expected_policy = seeded_multidigraph_policy();
            let graph = PyMultiDiGraph::new_empty_with_policy(py, expected_policy.clone())
                .expect("multidigraph should initialize");

            let state = graph
                .__getstate__(py)
                .expect("state export should succeed")
                .into_bound(py)
                .downcast_into::<PyDict>()
                .expect("state should be a dict");
            let mode = state
                .get_item("mode")
                .expect("dict lookup should succeed")
                .expect("mode should be present")
                .extract::<String>()
                .expect("mode should be a string");
            assert_eq!(mode, "hardened");
            assert!(
                state
                    .get_item("runtime_policy")
                    .expect("dict lookup should succeed")
                    .is_some(),
                "runtime policy should be serialized"
            );

            let mut restored =
                PyMultiDiGraph::new(py, None, None).expect("multidigraph should initialize");
            restored
                .__setstate__(py, &state)
                .expect("state import should succeed");

            assert_eq!(restored.inner.runtime_policy(), &expected_policy);
        });
    }
}
