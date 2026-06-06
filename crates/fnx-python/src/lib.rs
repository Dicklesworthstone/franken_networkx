#![allow(clippy::type_complexity, clippy::too_many_arguments, deprecated)]
#![forbid(unsafe_code)]

//! PyO3 Python bindings for FrankenNetworkX.
//!
//! This crate compiles to a cdylib that Python loads as `franken_networkx._fnx`.
//! The public Python API is re-exported through `python/franken_networkx/__init__.py`.

mod algorithms;
mod cgse;
pub(crate) mod digraph;
mod generators;
mod readwrite;
mod views;

pub use readwrite::{RawNodeLinkError, RawNodeLinkReport, parse_raw_node_link_json};

use fnx_classes::{AttrMap, Graph, MultiGraph};
use fnx_runtime::{CgseValue, CompatibilityMode, RuntimePolicy};
use pyo3::exceptions::{PyKeyError, PyRuntimeError, PyTypeError, PyValueError};
use pyo3::marker::Ungil;
use pyo3::prelude::*;
use pyo3::types::{PyAny, PyBool, PyDict, PyFloat, PyInt, PyIterator, PyList, PyString, PyTuple};
use std::collections::{HashMap, HashSet};
use std::convert::Infallible;
use std::sync::atomic::{AtomicBool, Ordering};

pub(crate) type PyObject = Py<PyAny>;

pub(crate) trait PythonAllowThreadsExt {
    fn allow_threads<T, F>(self, f: F) -> T
    where
        T: Ungil,
        F: Ungil + FnOnce() -> T;
}

impl<'py> PythonAllowThreadsExt for Python<'py> {
    fn allow_threads<T, F>(self, f: F) -> T
    where
        T: Ungil,
        F: Ungil + FnOnce() -> T,
    {
        self.detach(f)
    }
}

// ---------------------------------------------------------------------------
// Exception hierarchy — mirrors NetworkX for drop-in compatibility.
// ---------------------------------------------------------------------------

pyo3::import_exception!(networkx.exception, NetworkXException);
pyo3::import_exception!(networkx.exception, NetworkXError);
pyo3::import_exception!(networkx.exception, NetworkXPointlessConcept);
pyo3::import_exception!(networkx.exception, NetworkXAlgorithmError);
pyo3::import_exception!(networkx.exception, NetworkXUnfeasible);
pyo3::import_exception!(networkx.exception, NetworkXNoPath);
pyo3::import_exception!(networkx.exception, NetworkXNoCycle);
pyo3::import_exception!(networkx.exception, NetworkXUnbounded);
pyo3::import_exception!(networkx.exception, NetworkXNotImplemented);
pyo3::import_exception!(networkx.algorithms.community.quality, NotAPartition);
pyo3::import_exception!(networkx.algorithms.tree.coding, NotATree);
pyo3::import_exception!(networkx.exception, NodeNotFound);
pyo3::import_exception!(networkx.exception, HasACycle);
pyo3::import_exception!(networkx.exception, PowerIterationFailedConvergence);

// ---------------------------------------------------------------------------
// NodeKey — bridge Python's dynamic node identifiers to Rust String keys.
// ---------------------------------------------------------------------------

/// Convert a Python node key to a canonical string for the Rust Graph.
///
/// br-r37-c1-intfloatnode: Python's dict treats numerically-equal
/// `int`/`bool`/`float` as the SAME key (because their hashes collide:
/// `hash(0) == hash(0.0) == hash(False)`). nx uses dicts for node
/// storage, so `G.has_node(0.0)` returns `True` when node `0` was
/// added. fnx canonicalises node keys to strings here, and previously
/// produced `"0"` for int `0` but `"0.0"` for float `0.0`, splitting
/// what should be a single node across two distinct keys. This broke
/// `__contains__`, `has_node`, `has_edge`, `__getitem__`, `degree`,
/// `remove_node`, and `add_node`/`add_edge` deduplication for any
/// drop-in caller that round-trips int node ids through float (e.g.
/// loading from NumPy/JSON, which promotes ints to floats).
///
/// Fix: route integral floats (finite, in `i64` range, zero
/// fractional part — including `-0.0`) through the int canonical
/// form so `0.0`, `0`, and `False` all canonicalise to `"0"`. Non-
/// integral / out-of-range / non-finite floats keep their `repr`-
/// based canonical so distinct hashes (NaN, Inf, 1.5, 1e20) remain
/// distinct nodes.
///
/// br-r37-c1-hej8k: Python strings live in their own dict-key
/// namespace; ``1`` and ``"1"`` are distinct even though ``1`` /
/// ``1.0`` / ``True`` are equal keys. Prefix strings so text nodes do
/// not collide with numeric canonical keys.
fn node_key_to_string(_py: Python<'_>, key: &Bound<'_, PyAny>) -> PyResult<String> {
    // br-ctaxkey: `downcast::<PyString>()` is a cheap isinstance check that
    // builds NO Python exception on a non-string, unlike `extract::<String>()`
    // which constructs and discards a `PyErr` for every int / float node key.
    // On the construction hot path (2 node-key conversions per edge, the
    // overwhelming majority int- or str-keyed) that discarded PyErr dominated.
    // The produced canonical string ("str:{len}:{s}") is byte-identical.
    if let Ok(s) = key.downcast::<PyString>() {
        let s = s.to_str()?;
        return Ok(format!("str:{}:{s}", s.len()));
    }
    // bool is a subclass of int, so extract::<i64>() handles both —
    // True → "1", False → "0", aligning with hash(True)==hash(1),
    // hash(False)==hash(0).
    if let Ok(i) = key.extract::<i64>() {
        return Ok(i.to_string());
    }
    // Floats that exactly represent an integer in i64 range collide
    // (by hash + ==) with their int counterpart in Python dicts.
    if let Ok(f) = key.extract::<f64>() {
        if f.is_finite() && f.fract() == 0.0 && f >= i64::MIN as f64 && f <= i64::MAX as f64 {
            return Ok((f as i64).to_string());
        }
        let repr = key.repr()?;
        return Ok(repr.to_string());
    }
    // br-r37-c1-y7m24: all-int tuples — the node-key shape of grid_2d /
    // hypercube / kneser and most relabeled lattices — get their canonical
    // built in Rust, byte-identical to CPython's tuple repr ("(0, 1)",
    // singleton "(0,)"). The generic key.repr() below is a full Python
    // call and dominated tuple-keyed construction (grid_2d_graph spent
    // 18.7ms of 29.7ms in batch canonicalization at 60x60). Exact-int
    // elements only: bool is excluded (repr "True" differs) and ints
    // outside i64 fall back to repr (their canonical already came from
    // repr, so the formats stay consistent).
    if let Ok(t) = key.downcast::<PyTuple>() {
        let n = t.len();
        if n > 0 {
            let mut parts: Vec<i64> = Vec::with_capacity(n);
            let mut all_int = true;
            for item in t.iter() {
                if item.is_exact_instance_of::<PyInt>()
                    && let Ok(v) = item.extract::<i64>()
                {
                    parts.push(v);
                    continue;
                }
                all_int = false;
                break;
            }
            if all_int {
                let mut s = String::with_capacity(n * 6 + 2);
                s.push('(');
                for (i, v) in parts.iter().enumerate() {
                    if i > 0 {
                        s.push_str(", ");
                    }
                    s.push_str(&v.to_string());
                }
                if n == 1 {
                    s.push(',');
                }
                s.push(')');
                return Ok(s);
            }
        }
    }
    // For other hashable types, use repr as the canonical key.
    let repr = key.repr()?;
    Ok(repr.to_string())
}

/// br-r37-c1-ymeml: detect an fnx-native graph instance and return its
/// compatibility mode. Graph-instance constructor inputs are ALWAYS
/// rebuilt by the Python `__init__` (`_copy_constructor_graph_source` /
/// the dgctor kernel — see br-copyedgeord for why), so the Rust `__new__`
/// must NOT absorb them: that work was cleared and redone every time
/// (21.2ms of a 40ms DiGraph(G) at n=1500/E=5217). `__new__` carries only
/// the source's mode so Strict/Hardened behavior survives the rebuild.
/// This also matches nx, where data absorption lives in `__init__`.
pub(crate) fn fnx_graph_instance_mode(data: &Bound<'_, PyAny>) -> Option<CompatibilityMode> {
    if let Ok(g) = data.extract::<PyRef<'_, PyGraph>>() {
        return Some(g.inner.mode());
    }
    if let Ok(g) = data.extract::<PyRef<'_, crate::digraph::PyDiGraph>>() {
        return Some(g.inner.mode());
    }
    if let Ok(g) = data.extract::<PyRef<'_, PyMultiGraph>>() {
        return Some(g.inner.mode());
    }
    if let Ok(g) = data.extract::<PyRef<'_, crate::digraph::PyMultiDiGraph>>() {
        return Some(g.inner.mode());
    }
    None
}

pub(crate) fn missing_key_error(key: &Bound<'_, PyAny>) -> PyErr {
    PyKeyError::new_err((key.clone().unbind(),))
}

pub(crate) fn edge_key_lookup_string(_py: Python<'_>, key: &Bound<'_, PyAny>) -> PyResult<String> {
    // br-r37-c1-edgekeyint: MultiGraph/MultiDiGraph edge keys must
    // honour Python's dict semantics — ``hash(0) == hash(0.0) ==
    // hash(False)``, so an edge added with ``key=0`` is the SAME
    // edge that lookup with ``key=0.0`` should find. nx uses dicts
    // for edge-key storage; fnx canonicalises here.  Pre-fix, three
    // hash-equivalent inputs produced three distinct canonicals
    // (``"int:0"`` / ``"bool:false"`` / ``"float:0.0"``), splitting
    // a single logical edge across multiple Rust-side slots and
    // breaking ``has_edge(key=0.0)`` and ``add_edge(key=0.0)``
    // dedup after a prior ``add_edge(key=0)``.
    //
    // Fix mirrors ``node_key_to_string``: collapse bool/int into a
    // single canonical, and route integral floats (finite, in i64
    // range, zero fractional part — including ``-0.0``) through the
    // same form. Non-integral / out-of-range / non-finite floats
    // keep the float canonical so NaN, Inf, 1.5, 1e20 stay distinct.
    if let Ok(s) = key.extract::<String>() {
        return Ok(format!("str:{s}"));
    }
    // bool is a subclass of int — extract::<i64>() handles both,
    // mapping True → "int:1" and False → "int:0" so bool/int keys
    // collide with their numerically-equal counterparts.
    if let Ok(i) = key.extract::<i64>() {
        return Ok(format!("int:{i}"));
    }
    if let Ok(f) = key.extract::<f64>() {
        if f.is_finite() && f.fract() == 0.0 && f >= i64::MIN as f64 && f <= i64::MAX as f64 {
            return Ok(format!("int:{}", f as i64));
        }
        return Ok(format!("float:{f:?}"));
    }
    let ty = key.get_type().name()?.to_string_lossy().into_owned();
    let repr = key.repr()?.to_string();
    Ok(format!("{ty}:{repr}"))
}

pub(crate) fn weighted_edge_triplet<'py>(
    item: &Bound<'py, PyAny>,
) -> PyResult<(Bound<'py, PyAny>, Bound<'py, PyAny>, Bound<'py, PyAny>)> {
    let unpack_error = || {
        let ty = item
            .get_type()
            .name()
            .map(|name| name.to_string_lossy().into_owned())
            .unwrap_or_else(|_| "object".to_owned());
        PyTypeError::new_err(format!("cannot unpack non-iterable {ty} object"))
    };
    let mut iter = PyIterator::from_object(item).map_err(|_| unpack_error())?;
    let Some(u) = iter.next() else {
        return Err(PyValueError::new_err(
            "not enough values to unpack (expected 3, got 0)",
        ));
    };
    let Some(v) = iter.next() else {
        return Err(PyValueError::new_err(
            "not enough values to unpack (expected 3, got 1)",
        ));
    };
    let Some(w) = iter.next() else {
        return Err(PyValueError::new_err(
            "not enough values to unpack (expected 3, got 2)",
        ));
    };
    if let Some(extra) = iter.next() {
        let _ = extra?;
        return Err(PyValueError::new_err(
            "too many values to unpack (expected 3)",
        ));
    }
    Ok((u?, v?, w?))
}

pub(crate) fn py_dict_to_attr_map(attrs: &Bound<'_, PyDict>) -> PyResult<AttrMap> {
    let mut rust_attrs = AttrMap::new();
    for (k, v) in attrs.iter() {
        let key: String = if let Ok(s) = k.extract::<String>() {
            s
        } else {
            k.str()?.to_string_lossy().into_owned()
        };
        rust_attrs.insert(key, py_value_to_cgse(&v)?);
    }
    Ok(rust_attrs)
}

pub(crate) fn py_dict_to_attr_map_with_mirror(
    py: Python<'_>,
    attrs: &Bound<'_, PyDict>,
) -> PyResult<(AttrMap, Py<PyDict>)> {
    let mut rust_attrs = AttrMap::new();
    let mirror = PyDict::new(py);
    for (k, v) in attrs.iter() {
        let key: String = if let Ok(s) = k.extract::<String>() {
            s
        } else {
            k.str()?.to_string_lossy().into_owned()
        };
        rust_attrs.insert(key, py_value_to_cgse(&v)?);
        mirror.set_item(&k, &v)?;
    }
    Ok((rust_attrs, mirror.unbind()))
}

/// Convert a Python attribute value to a `CgseValue`.
///
/// br-r37-c1-aefbatch: a leading exact-type dispatch handles the overwhelmingly
/// common scalar kinds (float weights, ints, strings, bools) with a single cheap
/// `is_exact_instance_of` check plus one `extract`, instead of the up-to-four
/// failed `extract` attempts the fallback chain performs (each failure builds and
/// discards a `PyErr`). Non-exact types — `dict`, numpy scalars, anything with a
/// custom `__float__`/`__index__` — fall through to the original chain, so the
/// resulting `CgseValue` is byte-for-byte identical to the previous behavior.
fn py_value_to_cgse(v: &Bound<'_, PyAny>) -> PyResult<CgseValue> {
    // Exact-type fast paths (bool before int: Python bool subclasses int).
    if v.is_exact_instance_of::<PyBool>() {
        return Ok(CgseValue::Bool(v.extract::<bool>()?));
    }
    if v.is_exact_instance_of::<PyFloat>() {
        return Ok(CgseValue::Float(v.extract::<f64>()?));
    }
    if v.is_exact_instance_of::<PyInt>() {
        if let Ok(i) = v.extract::<i64>() {
            return Ok(CgseValue::Int(i));
        }
        // Oversized int: fall through to the chain (which yields Float via f64).
    } else if v.is_exact_instance_of::<PyString>() {
        return Ok(CgseValue::String(v.extract::<String>()?));
    }

    if let Ok(d) = v.downcast::<PyDict>() {
        let nested = py_dict_to_attr_map(d)?;
        Ok(CgseValue::Map(nested))
    } else if let Ok(s) = v.extract::<String>() {
        Ok(CgseValue::String(s))
    } else if let Ok(b) = v.extract::<bool>() {
        // bool must be checked before i64/f64 because Python bool is a subclass of int
        Ok(CgseValue::Bool(b))
    } else if let Ok(i) = v.extract::<i64>() {
        Ok(CgseValue::Int(i))
    } else if let Ok(f) = v.extract::<f64>() {
        Ok(CgseValue::Float(f))
    } else {
        Ok(CgseValue::String(v.str()?.to_string()))
    }
}

pub(crate) fn deepcopy_py_dict(
    py: Python<'_>,
    deepcopy: &Bound<'_, PyAny>,
    attrs: &Py<PyDict>,
) -> PyResult<Py<PyDict>> {
    let bound = attrs.bind(py);
    // perf (to_directed/to_undirected/copy family): an EMPTY attr dict —
    // the overwhelmingly common case for attr-less graphs, since mirrors
    // are created eagerly per node/edge — needs no recursive Python
    // deepcopy. A fresh dict is semantically identical (deepcopy({}) ==
    // {}; the memo cannot matter for an empty dict) and skips an
    // interpreter round-trip per node/edge (~12k calls on a 12k-edge
    // graph were the dominant cost of to_directed).
    if bound.is_empty() {
        return Ok(PyDict::new(py).unbind());
    }
    Ok(deepcopy.call1((bound,))?.downcast_into::<PyDict>()?.unbind())
}

use pyo3::IntoPyObjectExt;

pub(crate) fn cgse_value_to_py(py: Python<'_>, val: &CgseValue) -> PyResult<PyObject> {
    match val {
        CgseValue::String(s) => s.into_py_any(py),
        CgseValue::Float(f) => f.into_py_any(py),
        CgseValue::Int(i) => i.into_py_any(py),
        CgseValue::Bool(b) => b.into_py_any(py),
        CgseValue::Map(map) => {
            let dict = PyDict::new(py);
            for (k, v) in map {
                dict.set_item(k, cgse_value_to_py(py, v)?)?;
            }
            dict.into_py_any(py)
        }
    }
}

pub(crate) const fn compatibility_mode_name(mode: CompatibilityMode) -> &'static str {
    match mode {
        CompatibilityMode::Strict => "strict",
        CompatibilityMode::Hardened => "hardened",
    }
}

pub(crate) fn compatibility_mode_from_py(
    value: Option<&Bound<'_, PyAny>>,
) -> PyResult<CompatibilityMode> {
    let Some(value) = value else {
        return Ok(CompatibilityMode::Strict);
    };
    match value.extract::<String>()?.as_str() {
        "strict" => Ok(CompatibilityMode::Strict),
        "hardened" => Ok(CompatibilityMode::Hardened),
        other => Err(PyValueError::new_err(format!(
            "unknown compatibility mode `{other}` in graph state"
        ))),
    }
}

pub(crate) fn runtime_policy_json(policy: &RuntimePolicy) -> PyResult<String> {
    serde_json::to_string(policy)
        .map_err(|err| PyValueError::new_err(format!("failed to serialize runtime policy: {err}")))
}

pub(crate) fn runtime_policy_from_state(
    state: &Bound<'_, PyDict>,
    expected_mode: CompatibilityMode,
) -> PyResult<RuntimePolicy> {
    let runtime_policy_json = state
        .get_item("runtime_policy")?
        .ok_or_else(|| PyValueError::new_err("missing runtime_policy in graph state"))?
        .extract::<String>()?;
    let runtime_policy =
        serde_json::from_str::<RuntimePolicy>(&runtime_policy_json).map_err(|err| {
            PyValueError::new_err(format!("failed to deserialize runtime policy: {err}"))
        })?;
    if runtime_policy.mode() != expected_mode {
        return Err(PyValueError::new_err(format!(
            "runtime policy mode `{}` does not match graph mode `{}`",
            compatibility_mode_name(runtime_policy.mode()),
            compatibility_mode_name(expected_mode)
        )));
    }
    Ok(runtime_policy)
}

// ---------------------------------------------------------------------------
// PyGraph — the main graph class wrapping fnx_classes::Graph.
// ---------------------------------------------------------------------------

/// An undirected graph — a Rust-backed drop-in replacement for ``networkx.Graph``.
pub(crate) struct DictOfDictsCache {
    pub(crate) nodes_seq: u64,
    pub(crate) edges_seq: u64,
    pub(crate) rows: Vec<(PyObject, Py<PyDict>)>,
}

#[pyclass(module = "franken_networkx", name = "Graph", dict, weakref, subclass)]
pub(crate) struct PyGraph {
    pub(crate) inner: Graph,
    /// Maps canonical string key -> original Python object for faithful round-trip.
    pub(crate) node_key_map: HashMap<String, PyObject>,
    /// Range fast path marker: canonical integer nodes in ``0..stop`` can be
    /// displayed as Python ints even when node_key_map has not materialized them.
    pub(crate) lazy_int_node_stop: i64,
    /// br-r37-c1-z6uka: per-adjacency-ROW display objects. nx's `_adj[u]`
    /// dict keeps the py object passed in the call that CREATED that cell,
    /// which can differ from the `_node` (first-wins) object when
    /// hash-equal keys of different types are mixed (28 vs 28.0 vs True).
    /// SPARSE: an entry exists ONLY when the cell's object differs from
    /// what `py_node_key` would render — empty for every uniform-key
    /// graph, so `py_adj_key` is a free `is_empty()` check on the hot
    /// render paths. Keyed (owner_canonical, neighbor_canonical).
    pub(crate) adj_py_keys: HashMap<(String, String), PyObject>,
    /// Per-node Python attribute dicts.
    pub(crate) node_py_attrs: HashMap<String, Py<PyDict>>,
    /// Per-edge Python attribute dicts. Key is (canonical_left, canonical_right).
    pub(crate) edge_py_attrs: HashMap<(String, String), Py<PyDict>>,
    /// Cached NetworkX-style adjacency rows for `to_dict_of_dicts`.
    pub(crate) dict_of_dicts_cache: Option<DictOfDictsCache>,
    /// Graph-level attribute dict.
    pub(crate) graph_attrs: Py<PyDict>,
    /// Monotonic counter bumped on every node add/remove (br-r37-c1-39d82).
    /// Used by NodeIteratorGuard to detect concurrent node-set mutations
    /// during iteration in O(1) without re-cloning ``nodes_ordered()``.
    /// Wraps via ``wrapping_add`` so we never trip the overflow-checks
    /// fuzz harness, but the diff-based comparison is correct under
    /// wrap so long as ≥ 2⁶⁴ mutations don't happen between
    /// construction and a single next() call.
    pub(crate) nodes_seq: u64,
    /// Sibling to nodes_seq bumped on every edge mutation (add_edge,
    /// remove_edge, add_edges_from, remove_edges_from, etc).  Together
    /// with nodes_seq forms a ``(nodes_seq, edges_seq)`` tuple that any
    /// caller can use as a monotonic graph-mutation key (br-r37-c1-jft0i)
    /// — e.g. the view materialization cache reverted in br-r37-c1-jy3j3
    /// needs both to catch count-preserving rewires.
    pub(crate) edges_seq: u64,
    /// Monotonic dirty marker for Python-visible edge attr dict handouts.
    pub(crate) edges_dirty: AtomicBool,
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
        if let Some(obj) = self.node_key_map.get(canonical) {
            return obj.clone_ref(py);
        }
        if let Some(value) = self.lazy_int_node_value(canonical) {
            return unwrap_infallible(value.into_pyobject(py))
                .into_any()
                .unbind();
        }
        unwrap_infallible(canonical.to_owned().into_pyobject(py))
            .into_any()
            .unbind()
    }

    /// br-r37-c1-z6uka: the display object for neighbor `nbr` inside
    /// `owner`'s adjacency row — nx's `_adj[owner]` dict key. Falls back to
    /// the global node object; the override map is empty for uniform-key
    /// graphs so this adds one branch to the hot render paths.
    pub(crate) fn py_adj_key(&self, py: Python<'_>, owner: &str, nbr: &str) -> PyObject {
        if !self.adj_py_keys.is_empty()
            && let Some(obj) = self.adj_py_keys.get(&(owner.to_owned(), nbr.to_owned()))
        {
            return obj.clone_ref(py);
        }
        self.py_node_key(py, nbr)
    }

    /// br-r37-c1-z6uka: record `passed` as the adjacency-row object for
    /// (owner -> nbr) iff it would render differently from `py_node_key`
    /// (identity first; type+value equality rescues un-interned equal
    /// ints/floats so uniform-key graphs never populate the map). Only
    /// call for NEWLY created adjacency cells — nx keeps the original
    /// object for existing cells.
    pub(crate) fn maybe_store_adj_key(
        &mut self,
        py: Python<'_>,
        owner: &str,
        nbr_canonical: &str,
        passed: &Bound<'_, PyAny>,
    ) {
        let differs = match self.node_key_map.get(nbr_canonical) {
            Some(stored) => {
                let stored = stored.bind(py);
                !(stored.is(passed)
                    || stored.get_type().is(passed.get_type())
                        && stored.eq(passed).unwrap_or(false))
            }
            None => {
                // canonical renders via lazy-int (an exact int) or the
                // canonical string itself; exact ints render identically.
                self.lazy_int_node_value(nbr_canonical).is_some()
                    && !passed.is_exact_instance_of::<PyInt>()
            }
        };
        if differs {
            self.adj_py_keys
                .entry((owner.to_owned(), nbr_canonical.to_owned()))
                .or_insert_with(|| passed.clone().unbind());
        }
    }

    /// br-r37-c1-z6uka: clone the adjacency-row override map (deep
    /// `clone_ref` per entry; no-op for the common empty map).
    pub(crate) fn clone_adj_py_keys(&self, py: Python<'_>) -> HashMap<(String, String), PyObject> {
        self.adj_py_keys
            .iter()
            .map(|(k, v)| (k.clone(), v.clone_ref(py)))
            .collect()
    }

    /// br-r37-c1-z6uka: the override map a COPY built by nx's u-major
    /// `add_edges_from((u, v, d) for u, nbrs in adj.items() ...)` walk
    /// would carry: the FIRST-encountered direction of each edge keeps the
    /// source row object; the reverse cell is created with the node object
    /// (no override). `result_inner` scopes the walk (full graph for
    /// copy(), the filtered graph for subgraphs).
    pub(crate) fn derive_copy_adj_py_keys(
        &self,
        py: Python<'_>,
        result_inner: &Graph,
    ) -> HashMap<(String, String), PyObject> {
        let mut out = HashMap::new();
        if self.adj_py_keys.is_empty() {
            return out;
        }
        let mut seen: HashSet<(String, String)> = HashSet::new();
        for u in result_inner.nodes_ordered() {
            for v in result_inner.neighbors(u).unwrap_or_default() {
                if seen.contains(&(u.to_owned(), v.to_owned())) {
                    continue;
                }
                seen.insert((v.to_owned(), u.to_owned()));
                if let Some(obj) = self.adj_py_keys.get(&(u.to_owned(), v.to_owned())) {
                    out.insert((u.to_owned(), v.to_owned()), obj.clone_ref(py));
                }
            }
        }
        out
    }

    /// br-r37-c1-z6uka: would `passed` display differently from `first`
    /// for the same canonical key (hash-equal mixed types: 28 vs 28.0 vs
    /// True)? Identity short-circuits; type+value equality rescues
    /// un-interned equal values so uniform-key batches never trip this.
    // br-r37-c1-z6uka: pub(crate) for the PyDiGraph row-key probes.
    pub(crate) fn display_objs_conflict(a: &Bound<'_, PyAny>, b: &Bound<'_, PyAny>) -> bool {
        !(a.is(b) || a.get_type().is(b.get_type()) && a.eq(b).unwrap_or(false))
    }

    /// br-r37-c1-z6uka: batch-bail probe — true when adding `passed` under
    /// `canonical` could need a per-adjacency-row display override (the
    /// batch paths then fall back to the per-edge add_edge, which records
    /// it). `batch_first` carries the first object seen per canonical
    /// within the current batch.
    fn plain_batch_display_conflict(
        &self,
        py: Python<'_>,
        canonical: &str,
        passed: &Bound<'_, PyAny>,
        batch_first: &mut HashMap<String, PyObject>,
    ) -> bool {
        if passed.is_exact_instance_of::<PyString>() {
            // str canonicals ("str:len:s") collide only with equal strings —
            // no display conflict possible; skips the probe for the dominant
            // str-keyed batches.
            return false;
        }
        if let Some(stored) = self.node_key_map.get(canonical) {
            return Self::display_objs_conflict(stored.bind(py), passed);
        }
        if let Some(first) = batch_first.get(canonical) {
            return Self::display_objs_conflict(first.bind(py), passed);
        }
        if self.lazy_int_node_value(canonical).is_some() && !passed.is_exact_instance_of::<PyInt>()
        {
            return true;
        }
        batch_first.insert(canonical.to_owned(), passed.clone().unbind());
        false
    }

    #[inline]
    fn lazy_int_node_value(&self, canonical: &str) -> Option<i64> {
        let value = canonical.parse::<i64>().ok()?;
        (0..self.lazy_int_node_stop)
            .contains(&value)
            .then_some(value)
    }

    #[inline]
    fn should_store_node_key(&self, canonical: &str, was_new: bool) -> bool {
        was_new || self.lazy_int_node_value(canonical).is_none()
    }

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

    pub(crate) fn materialize_edge_py_attrs(
        &mut self,
        py: Python<'_>,
        left: &str,
        right: &str,
    ) -> Py<PyDict> {
        let key = Self::edge_key(left, right);
        self.edge_py_attrs
            .entry(key)
            .or_insert_with(|| PyDict::new(py).unbind())
            .clone_ref(py)
    }

    /// Create a new empty PyGraph (no nodes, no edges, empty graph attrs).
    #[allow(dead_code)] // Used by wrapper tests and parity helpers.
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
            inner: Graph::with_runtime_policy(runtime_policy),
            node_key_map: HashMap::new(),
            lazy_int_node_stop: 0,
            node_py_attrs: HashMap::new(),
            edge_py_attrs: HashMap::new(),
            adj_py_keys: HashMap::new(), // br-r37-c1-z6uka
            dict_of_dicts_cache: None,
            graph_attrs: PyDict::new(py).unbind(),
            nodes_seq: 0,
            edges_seq: 0,
            edges_dirty: AtomicBool::new(false),
        })
    }

    /// Bump the node-mutation counter after any add/remove operation
    /// (br-r37-c1-39d82).  ``wrapping_add`` avoids overflow-check
    /// panics — the diff-based comparison in NodeIteratorGuard's
    /// __next__ is correct under wrap.
    #[inline]
    pub(crate) fn bump_nodes_seq(&mut self) {
        self.nodes_seq = self.nodes_seq.wrapping_add(1);
    }

    /// Bump the edge-mutation counter after any edge add/remove
    /// (br-r37-c1-jft0i).  Used together with nodes_seq to form a
    /// monotonic ``(nodes_seq, edges_seq)`` graph-mutation key that's
    /// exposed to Python for the view materialization cache.
    #[inline]
    pub(crate) fn bump_edges_seq(&mut self) {
        self.edges_seq = self.edges_seq.wrapping_add(1);
    }

    #[inline]
    pub(crate) fn mark_edges_dirty(&self) {
        self.edges_dirty.store(true, Ordering::Relaxed);
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

    fn collect_plain_edge_batch<'py, I>(
        &self,
        py: Python<'py>,
        items: I,
        len: usize,
    ) -> PyResult<Option<(Vec<(String, String)>, Vec<(String, PyObject)>, u64)>>
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
        let mut batch_first: HashMap<String, PyObject> = HashMap::new(); // br-r37-c1-z6uka

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
            // br-r37-c1-z6uka: hash-equal mixed-type keys (28 vs 28.0)
            // need per-adjacency-row display objects — bail to the
            // per-edge path, which records them.
            if self.plain_batch_display_conflict(py, &u_canonical, &u, &mut batch_first)
                || self.plain_batch_display_conflict(py, &v_canonical, &v, &mut batch_first)
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
        _py: Python<'_>,
        edges: Vec<(String, String)>,
        new_nodes: Vec<(String, PyObject)>,
        node_bumps: u64,
    ) {
        let edge_bumps = u64::try_from(edges.len())
            .unwrap_or(u64::MAX)
            .wrapping_add(1);

        for (canonical, node) in new_nodes {
            self.node_key_map.entry(canonical).or_insert(node);
        }
        // br-r37-c1-89kxg: NO eager empty mirror dicts — every reader goes
        // through materialize_*/ensure_*/entry().or_insert, so absence is
        // observationally identical to an empty dict. ~6700 PyDict allocs
        // saved per 5217-edge build.

        let _inserted = self.inner.extend_edges_unrecorded(edges);
        self.nodes_seq = self.nodes_seq.wrapping_add(node_bumps);
        self.edges_seq = self.edges_seq.wrapping_add(edge_bumps);
    }

    fn try_add_plain_edge_batch(
        &mut self,
        py: Python<'_>,
        ebunch_to_add: &Bound<'_, PyAny>,
    ) -> PyResult<bool> {
        const PLAIN_EDGE_BATCH_MIN: usize = 8;
        if let Ok(list) = ebunch_to_add.downcast::<PyList>() {
            if list.len() < PLAIN_EDGE_BATCH_MIN {
                return Ok(false);
            }
            if let Some((edges, new_nodes, node_bumps)) =
                self.collect_plain_edge_batch(py, list.iter(), list.len())?
            {
                self.add_plain_edge_batch(py, edges, new_nodes, node_bumps);
                return Ok(true);
            }
        } else if let Ok(tuple) = ebunch_to_add.downcast::<PyTuple>()
            && tuple.len() >= PLAIN_EDGE_BATCH_MIN
            && let Some((edges, new_nodes, node_bumps)) =
                self.collect_plain_edge_batch(py, tuple.iter(), tuple.len())?
        {
            self.add_plain_edge_batch(py, edges, new_nodes, node_bumps);
            return Ok(true);
        }
        Ok(false)
    }

    /// br-r37-c1-pr8q6: collect a batch of attributed edges — a mix of
    /// (u, v) and (u, v, dict) tuples — for single-commit insertion.
    /// Pure collect: NO mutation of self. Returns Ok(None) (caller falls
    /// back to the per-edge loop, which owns every error and
    /// partial-prefix contract) on ANY item the batch can't replicate
    /// exactly: non-tuple items, bad arity, non-dict third element,
    /// non-plain endpoints, attr values `py_dict_to_attr_map` rejects, or
    /// `"__fnx_incompatible"` attr keys (whose FailClosed contract lives
    /// in `add_edge_with_attrs`).
    fn collect_attr_edge_batch<'py, I>(
        &self,
        py: Python<'py>,
        items: I,
        len: usize,
    ) -> PyResult<Option<AttrEdgeBatch>>
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
        let mut batch_first: HashMap<String, PyObject> = HashMap::new(); // br-r37-c1-z6uka

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
                let Ok(d) = third.downcast::<PyDict>() else {
                    return Ok(None);
                };
                let Ok(attrs) = py_dict_to_attr_map(d) else {
                    return Ok(None);
                };
                if attrs.keys().any(|k| k.starts_with("__fnx_incompatible")) {
                    return Ok(None);
                }
                (attrs, Some(d.clone().unbind()))
            } else {
                (AttrMap::new(), None)
            };

            let Ok(u_canonical) = node_key_to_string(py, &u) else {
                return Ok(None);
            };
            let Ok(v_canonical) = node_key_to_string(py, &v) else {
                return Ok(None);
            };
            // br-r37-c1-z6uka: see collect_plain_edge_batch — mixed-type
            // hash-equal keys bail to the per-edge path.
            if self.plain_batch_display_conflict(py, &u_canonical, &u, &mut batch_first)
                || self.plain_batch_display_conflict(py, &v_canonical, &v, &mut batch_first)
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

    /// Commit a collected attributed-edge batch: PyDict mirrors first
    /// (entry+update — merges into an existing edge's dict exactly like
    /// the per-edge `add_edge` does), then ONE
    /// `extend_edges_with_attrs_unrecorded` call into the inner graph
    /// (insert-or-merge, no per-edge ledger), then the same seq bumps the
    /// plain batch performs.
    fn add_attr_edge_batch(
        &mut self,
        py: Python<'_>,
        edges: Vec<(String, String, AttrMap, Option<Py<PyDict>>)>,
        new_nodes: Vec<(String, PyObject)>,
        node_bumps: u64,
    ) -> PyResult<()> {
        let edge_bumps = u64::try_from(edges.len())
            .unwrap_or(u64::MAX)
            .wrapping_add(1);

        for (canonical, node) in new_nodes {
            self.node_key_map.entry(canonical).or_insert(node);
        }
        // br-r37-c1-89kxg: mirrors are LAZY — only attributed edges
        // materialize a dict here (content copy); empty mirrors are
        // created on first observation by the render paths.
        for (u, v, _, src) in &edges {
            if let Some(src) = src {
                let bound = src.bind(py);
                if !bound.is_empty() {
                    self.edge_py_attrs
                        .entry(Self::edge_key(u, v))
                        .or_insert_with(|| PyDict::new(py).unbind())
                        .bind(py)
                        .update(bound.as_mapping())?;
                }
            }
        }

        let _inserted = self
            .inner
            .extend_edges_with_attrs_unrecorded(edges.into_iter().map(|(u, v, a, _)| (u, v, a)));
        self.nodes_seq = self.nodes_seq.wrapping_add(node_bumps);
        self.edges_seq = self.edges_seq.wrapping_add(edge_bumps);
        Ok(())
    }

    /// br-r37-c1-pr8q6: attributed sibling of `try_add_plain_edge_batch`.
    /// Tried AFTER the plain batch (which is cheaper when every tuple is
    /// a 2-tuple); accepts mixed 2-/3-tuple lists.
    fn try_add_attr_edge_batch(
        &mut self,
        py: Python<'_>,
        ebunch_to_add: &Bound<'_, PyAny>,
    ) -> PyResult<bool> {
        const ATTR_EDGE_BATCH_MIN: usize = 8;
        if let Ok(list) = ebunch_to_add.downcast::<PyList>() {
            if list.len() < ATTR_EDGE_BATCH_MIN {
                return Ok(false);
            }
            if let Some((edges, new_nodes, node_bumps)) =
                self.collect_attr_edge_batch(py, list.iter(), list.len())?
            {
                self.add_attr_edge_batch(py, edges, new_nodes, node_bumps)?;
                return Ok(true);
            }
        } else if let Ok(tuple) = ebunch_to_add.downcast::<PyTuple>()
            && tuple.len() >= ATTR_EDGE_BATCH_MIN
            && let Some((edges, new_nodes, node_bumps)) =
                self.collect_attr_edge_batch(py, tuple.iter(), tuple.len())?
        {
            self.add_attr_edge_batch(py, edges, new_nodes, node_bumps)?;
            return Ok(true);
        }
        Ok(false)
    }
}

/// br-r37-c1-pr8q6: collected attributed-edge batch —
/// (edges, new_nodes, node_bumps); each edge carries its converted
/// `AttrMap` plus the source `PyDict` for the mirror update.
type AttrEdgeBatch = (
    Vec<(String, String, AttrMap, Option<Py<PyDict>>)>,
    Vec<(String, PyObject)>,
    u64,
);

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
    /// br-r37-c1-z6uka: per-adjacency-CELL display objects (see
    /// PyGraph::adj_py_keys) — a cell is created by the FIRST key of a
    /// (u, v) pair; parallel keys reuse it.
    pub(crate) adj_py_keys: HashMap<(String, String), PyObject>,
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
}

impl PyMultiGraph {
    /// br-r37-c1-z6uka: adjacency-cell display object (see PyGraph::py_adj_key).
    pub(crate) fn py_adj_key(&self, py: Python<'_>, owner: &str, nbr: &str) -> PyObject {
        if !self.adj_py_keys.is_empty()
            && let Some(obj) = self.adj_py_keys.get(&(owner.to_owned(), nbr.to_owned()))
        {
            return obj.clone_ref(py);
        }
        self.py_node_key(py, nbr)
    }

    /// br-r37-c1-z6uka: see PyGraph::derive_copy_adj_py_keys — nx's u-major
    /// copy walk keeps the first-encountered direction's cell object.
    pub(crate) fn derive_copy_adj_py_keys(
        &self,
        py: Python<'_>,
    ) -> HashMap<(String, String), PyObject> {
        let mut out = HashMap::new();
        if self.adj_py_keys.is_empty() {
            return out;
        }
        let mut seen: HashSet<(String, String)> = HashSet::new();
        for u in self.inner.nodes_ordered() {
            for v in self.inner.neighbors(u).unwrap_or_default() {
                if seen.contains(&(u.to_owned(), v.to_owned())) {
                    continue;
                }
                seen.insert((v.to_owned(), u.to_owned()));
                if let Some(obj) = self.adj_py_keys.get(&(u.to_owned(), v.to_owned())) {
                    out.insert((u.to_owned(), v.to_owned()), obj.clone_ref(py));
                }
            }
        }
        out
    }

    pub(crate) fn edge_key(u: &str, v: &str, key: usize) -> (String, String, usize) {
        if u <= v {
            (u.to_owned(), v.to_owned(), key)
        } else {
            (v.to_owned(), u.to_owned(), key)
        }
    }

    fn ensure_node_py_attrs(&mut self, py: Python<'_>, canonical: &str) -> &Py<PyDict> {
        self.node_py_attrs
            .entry(canonical.to_owned())
            .or_insert_with(|| PyDict::new(py).unbind())
    }

    fn ensure_edge_py_attrs(
        &mut self,
        py: Python<'_>,
        u: &str,
        v: &str,
        key: usize,
    ) -> &Py<PyDict> {
        // Empty edge attrs stay sparse on construction and become live only when
        // a NetworkX-observable mapping is handed out.
        let ek = Self::edge_key(u, v, key);
        self.edge_py_attrs
            .entry(ek)
            .or_insert_with(|| PyDict::new(py).unbind())
    }

    fn neighbor_dict(
        &mut self,
        py: Python<'_>,
        node: &str,
        neighbor: &str,
    ) -> PyResult<Py<PyDict>> {
        let result = PyDict::new(py);
        for key in self.inner.edge_keys(node, neighbor).unwrap_or_default() {
            let attrs = self
                .ensure_edge_py_attrs(py, node, neighbor, key)
                .clone_ref(py);
            let py_key = self.py_edge_key(py, node, neighbor, key);
            result.set_item(py_key, attrs.bind(py))?;
        }
        Ok(result.unbind())
    }

    fn py_edge_key(&self, py: Python<'_>, u: &str, v: &str, key: usize) -> PyObject {
        self.edge_py_keys
            .get(&Self::edge_key(u, v, key))
            .map_or_else(
                || unwrap_infallible(key.into_pyobject(py)).into_any().unbind(),
                |obj| obj.clone_ref(py),
            )
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
        // br-r37-c1-edgekeyfirstwins: nx uses dicts for per-edge-pair
        // key storage, so the FIRST Py-form added under a given
        // canonical key (e.g. ``hash(0) == hash(0.0) == hash(False)``)
        // wins for ``list(G.edges(keys=True))`` display. Subsequent
        // ``add_edge`` calls with hash-equivalent keys are dedup at
        // the storage level (post-cycle-182 edge_key_lookup_string
        // fix) but echo back the user-provided Py-form as the return
        // value (matching nx's add_edge contract). Use
        // ``entry().or_insert_with`` here so re-adding ``key=0.0``
        // after ``key=0`` doesn't overwrite the displayed Py-form.
        self.edge_py_keys
            .entry(Self::edge_key(u, v, key))
            .or_insert_with(|| py_key.clone_ref(py));
        py_key
    }

    fn remember_edge_key_object(
        &mut self,
        py: Python<'_>,
        u: &str,
        v: &str,
        key: usize,
        external_key: &PyObject,
    ) {
        // First-wins: see remember_edge_key above for the rationale.
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
            inner: MultiGraph::with_runtime_policy(runtime_policy),
            node_key_map: HashMap::new(),
            adj_py_keys: HashMap::new(), // br-r37-c1-z6uka
            node_py_attrs: HashMap::new(),
            edge_py_attrs: HashMap::new(),
            edge_py_keys: HashMap::new(),
            graph_attrs: PyDict::new(py).unbind(),
            nodes_seq: 0,
            edges_seq: 0,
            edges_dirty: AtomicBool::new(false),
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
}

#[pyclass(module = "franken_networkx", mapping)]
struct MultiAtlasView {
    graph: Py<PyMultiGraph>,
    node: String,
}

impl MultiAtlasView {
    fn new(graph: Py<PyMultiGraph>, node: String) -> Self {
        Self { graph, node }
    }

    fn materialize(&self, py: Python<'_>) -> PyResult<Py<PyDict>> {
        let g = self.graph.borrow(py);
        let result = PyDict::new(py);
        for neighbor in g.inner.neighbors(&self.node).unwrap_or_default() {
            let py_neighbor = g.py_adj_key(py, &self.node, neighbor) /* br-r37-c1-z6uka */;
            let keydict = MultiKeyDictView::new(
                self.graph.clone_ref(py),
                self.node.clone(),
                neighbor.to_owned(),
            )
            .materialize(py)?;
            result.set_item(py_neighbor, keydict.bind(py))?;
        }
        Ok(result.unbind())
    }
}

#[pymethods]
impl MultiAtlasView {
    fn __getitem__(&self, py: Python<'_>, v: &Bound<'_, PyAny>) -> PyResult<Py<MultiKeyDictView>> {
        let g = self.graph.borrow(py);
        let v_canon = node_key_to_string(py, v)?;
        if !g.inner.has_edge(&self.node, &v_canon) {
            return Err(PyKeyError::new_err((v.clone().unbind(),)));
        }
        Py::new(
            py,
            MultiKeyDictView::new(self.graph.clone_ref(py), self.node.clone(), v_canon),
        )
    }

    fn __contains__(&self, py: Python<'_>, v: &Bound<'_, PyAny>) -> PyResult<bool> {
        let g = self.graph.borrow(py);
        let v_canon = node_key_to_string(py, v)?;
        Ok(g.inner.has_edge(&self.node, &v_canon))
    }

    fn __len__(&self, py: Python<'_>) -> usize {
        self.graph
            .borrow(py)
            .inner
            .neighbors(&self.node)
            .map_or(0, |neighbors| neighbors.len())
    }

    fn __iter__(&self, py: Python<'_>) -> PyResult<Py<NodeIterator>> {
        let g = self.graph.borrow(py);
        let nodes: Vec<PyObject> = g
            .inner
            .neighbors(&self.node)
            .unwrap_or_default()
            .iter()
            .map(
                |neighbor| g.py_adj_key(py, &self.node, neighbor), /* br-r37-c1-z6uka */
            )
            .collect();
        Py::new(py, NodeIterator::unguarded(nodes))
    }

    fn keys(&self, py: Python<'_>) -> PyResult<Py<NodeIterator>> {
        self.__iter__(py)
    }

    fn items(&self, py: Python<'_>) -> PyResult<Vec<(PyObject, Py<MultiKeyDictView>)>> {
        let g = self.graph.borrow(py);
        let neighbors = g.inner.neighbors(&self.node).unwrap_or_default();
        let mut out = Vec::with_capacity(neighbors.len());
        for neighbor in neighbors {
            out.push((
                g.py_adj_key(py, &self.node, neighbor), /* br-r37-c1-z6uka */
                Py::new(
                    py,
                    MultiKeyDictView::new(
                        self.graph.clone_ref(py),
                        self.node.clone(),
                        neighbor.to_owned(),
                    ),
                )?,
            ));
        }
        Ok(out)
    }

    fn values(&self, py: Python<'_>) -> PyResult<Vec<Py<MultiKeyDictView>>> {
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
        let result = PyDict::new(py);
        for neighbor in g.inner.neighbors(&self.node).unwrap_or_default() {
            let py_neighbor = g.py_adj_key(py, &self.node, neighbor) /* br-r37-c1-z6uka */;
            let keydict = MultiKeyDictView::new(
                self.graph.clone_ref(py),
                self.node.clone(),
                neighbor.to_owned(),
            )
            .copy(py)?;
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
struct MultiKeyDictView {
    graph: Py<PyMultiGraph>,
    source: String,
    target: String,
}

impl MultiKeyDictView {
    fn new(graph: Py<PyMultiGraph>, source: String, target: String) -> Self {
        Self {
            graph,
            source,
            target,
        }
    }

    fn materialize(&self, py: Python<'_>) -> PyResult<Py<PyDict>> {
        let mut g = self.graph.borrow_mut(py);
        let result = PyDict::new(py);
        for key in g
            .inner
            .edge_keys(&self.source, &self.target)
            .unwrap_or_default()
        {
            let attrs = g
                .ensure_edge_py_attrs(py, &self.source, &self.target, key)
                .clone_ref(py);
            let py_key = g.py_edge_key(py, &self.source, &self.target, key);
            result.set_item(py_key, attrs)?;
        }
        Ok(result.unbind())
    }
}

#[pymethods]
impl MultiKeyDictView {
    fn __getitem__(&self, py: Python<'_>, key: &Bound<'_, PyAny>) -> PyResult<Py<PyDict>> {
        let mut g = self.graph.borrow_mut(py);
        let Some(internal_key) =
            g.resolve_internal_edge_key(py, &self.source, &self.target, key)?
        else {
            return Err(PyKeyError::new_err((key.clone().unbind(),)));
        };
        g.mark_edges_dirty();
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

    fn __iter__(&self, py: Python<'_>) -> PyResult<Py<NodeIterator>> {
        let g = self.graph.borrow(py);
        let keys: Vec<PyObject> = g
            .inner
            .edge_keys(&self.source, &self.target)
            .unwrap_or_default()
            .into_iter()
            .map(|key| g.py_edge_key(py, &self.source, &self.target, key))
            .collect();
        Py::new(py, NodeIterator::unguarded(keys))
    }

    fn keys(&self, py: Python<'_>) -> PyResult<Py<NodeIterator>> {
        self.__iter__(py)
    }

    fn items(&self, py: Python<'_>) -> PyResult<Vec<(PyObject, Py<PyDict>)>> {
        let mut g = self.graph.borrow_mut(py);
        let keys = g
            .inner
            .edge_keys(&self.source, &self.target)
            .unwrap_or_default();
        if !keys.is_empty() {
            g.mark_edges_dirty();
        }
        let mut out = Vec::with_capacity(keys.len());
        for key in keys {
            let attrs = g
                .ensure_edge_py_attrs(py, &self.source, &self.target, key)
                .clone_ref(py);
            let py_key = g.py_edge_key(py, &self.source, &self.target, key);
            out.push((py_key, attrs));
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
            let edge_key = PyMultiGraph::edge_key(&self.source, &self.target, key);
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

        let mut g = Self::new_empty_with_mode(py, CompatibilityMode::Strict)?;
        g.graph_attrs = graph_attrs.unbind();

        if let Some(data) = incoming_graph_data {
            // br-r37-c1-ymeml: see fnx_graph_instance_mode — __init__ owns
            // population for graph-instance inputs; absorb skipped.
            if let Some(mode) = fnx_graph_instance_mode(data) {
                g.inner = MultiGraph::new(mode);
                return Ok(g);
            }
            if let Ok(other) = data.extract::<PyRef<'_, PyMultiGraph>>() {
                g.inner = MultiGraph::with_runtime_policy(other.inner.runtime_policy().clone());
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
                for edge in other.inner.edges_ordered() {
                    let ek = Self::edge_key(&edge.left, &edge.right, edge.key);
                    let rust_attrs = other
                        .edge_py_attrs
                        .get(&ek)
                        .map(|attrs| py_dict_to_attr_map(attrs.bind(py)))
                        .transpose()?
                        .unwrap_or_default();
                    let _ = g.inner.add_edge_with_key_and_attrs(
                        edge.left.clone(),
                        edge.right.clone(),
                        edge.key,
                        rust_attrs,
                    );
                    if let Some(attrs) = other.edge_py_attrs.get(&ek) {
                        g.edge_py_attrs
                            .insert(ek.clone(), attrs.bind(py).copy()?.unbind());
                    }
                    if let Some(py_key) = other.edge_py_keys.get(&ek) {
                        g.remember_edge_key_object(py, &edge.left, &edge.right, edge.key, py_key);
                    } else {
                        g.remember_edge_key(py, &edge.left, &edge.right, edge.key, None);
                    }
                }
                g.graph_attrs = other.graph_attrs.bind(py).copy()?.unbind();
            } else if let Ok(other) = data.extract::<PyRef<'_, PyGraph>>() {
                g.inner = MultiGraph::with_runtime_policy(other.inner.runtime_policy().clone());
                for canonical in other.inner.nodes_ordered() {
                    let rust_attrs = other
                        .node_py_attrs
                        .get(canonical)
                        .map(|attrs| py_dict_to_attr_map(attrs.bind(py)))
                        .transpose()?
                        .unwrap_or_default();
                    g.inner
                        .add_node_with_attrs(canonical.to_owned(), rust_attrs);
                    g.node_key_map
                        .insert(canonical.to_owned(), other.py_node_key(py, canonical));
                    if let Some(attrs) = other.node_py_attrs.get(canonical) {
                        g.node_py_attrs
                            .insert(canonical.to_owned(), attrs.bind(py).copy()?.unbind());
                    }
                }
                for edge in other.inner.edges_ordered() {
                    let ek = PyGraph::edge_key(&edge.left, &edge.right);
                    let rust_attrs = other
                        .edge_py_attrs
                        .get(&ek)
                        .map(|attrs| py_dict_to_attr_map(attrs.bind(py)))
                        .transpose()?
                        .unwrap_or_default();
                    let key = g
                        .inner
                        .add_edge_with_key_and_attrs(
                            edge.left.clone(),
                            edge.right.clone(),
                            0,
                            rust_attrs,
                        )
                        .map_err(|e| NetworkXError::new_err(e.to_string()))?;
                    if let Some(attrs) = other.edge_py_attrs.get(&ek) {
                        g.edge_py_attrs.insert(
                            Self::edge_key(&edge.left, &edge.right, key),
                            attrs.bind(py).copy()?.unbind(),
                        );
                    }
                    g.remember_edge_key(py, &edge.left, &edge.right, key, None);
                }
                g.graph_attrs = other.graph_attrs.bind(py).copy()?.unbind();
            } else if let Ok(iter) = PyIterator::from_object(data) {
                // br-r37-c1-fl36h: nx's to_networkx_graph wraps every
                // from_edgelist failure in NetworkXError("Input is not a
                // valid edge list"). Unhashable endpoints/keys raise
                // TypeError from add_edge's hash guard, which must not
                // leak raw out of the constructor (Graph/DiGraph absorb
                // by id and translate in the Python __init__ backstop;
                // MultiGraph's eager hash fires here first).
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
                            _ => g.add_node(py, &item, None).map_err(edge_list_err)?,
                        }
                    } else {
                        g.add_node(py, &item, None).map_err(edge_list_err)?;
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
        let edges: Vec<(String, String, usize, AttrMap)> = self
            .edge_py_attrs
            .iter()
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

    /// If key is None, returns a dict of key -> attr_dict.
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
                    let py_key = self.py_edge_key(py, &u_c, &v_c, k);
                    result.set_item(py_key, attrs.bind(py))?;
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
                for edge in self.inner.edges_ordered() {
                    let ek = Self::edge_key(&edge.left, &edge.right, edge.key);
                    match self.edge_py_attrs.get(&ek) {
                        Some(dict) => {
                            let bound = dict.bind(py);
                            match bound.get_item(attr)? {
                                Some(val) => total += val.extract::<f64>()?,
                                None => total += 1.0,
                            }
                        }
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
        // br-r37-c1-firstwins: nx uses dicts for node storage, so the
        // FIRST Python object added under a given canonical key wins
        // (subsequent ``add_node`` calls with hash-equivalent keys are
        // no-ops at the storage level — the original Py object is
        // preserved for ``list(G.nodes())`` and friends). Use
        // ``entry().or_insert_with`` here so re-adding ``0.0`` after
        // ``0`` doesn't overwrite the displayed Py form. ``add_edge``
        // already uses this pattern at the call site below.
        self.node_key_map
            .entry(canonical.clone())
            .or_insert_with(|| n.clone().unbind());

        let rust_attrs = if let Some(a) = attr {
            let rust_attrs = py_dict_to_attr_map(a)?;
            let py_dict = self.ensure_node_py_attrs(py, &canonical);
            for (k, v) in a.iter() {
                py_dict.bind(py).set_item(k, v)?;
            }
            rust_attrs
        } else {
            AttrMap::new()
        };

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
        let neighbors = self
            .inner
            .neighbors(&canonical)
            .map(|neighbors| neighbors.into_iter().map(str::to_owned).collect::<Vec<_>>());
        let mut had_incident_edges = false;
        if let Some(neighbors) = neighbors {
            for nb in neighbors {
                if let Some(keys) = self.inner.edge_keys(&canonical, &nb) {
                    for key in keys {
                        self.remove_edge_metadata(&canonical, &nb, key);
                        had_incident_edges = true;
                    }
                }
            }
        }

        self.inner.remove_node(&canonical);
        self.node_key_map.remove(&canonical);
        self.node_py_attrs.remove(&canonical);
        if !self.adj_py_keys.is_empty() {
            // br-r37-c1-z6uka: drop cell overrides touching the removed node.
            self.adj_py_keys
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
                let neighbors = self
                    .inner
                    .neighbors(&canonical)
                    .map(|neighbors| neighbors.into_iter().map(str::to_owned).collect::<Vec<_>>());
                if let Some(neighbors) = neighbors {
                    for nb in neighbors {
                        if let Some(keys) = self.inner.edge_keys(&canonical, &nb) {
                            for key in keys {
                                self.remove_edge_metadata(&canonical, &nb, key);
                                had_incident_edges = true;
                            }
                        }
                    }
                }
                self.inner.remove_node(&canonical);
                self.node_key_map.remove(&canonical);
                self.node_py_attrs.remove(&canonical);
                if !self.adj_py_keys.is_empty() {
                    // br-r37-c1-z6uka: drop cell overrides touching removed nodes.
                    self.adj_py_keys
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
        // br-r37-c1 mutation-state batch 2: nx creates node u BEFORE
        // examining v, so a bad v leaves u on the graph.
        if u.is_none() {
            return Err(PyValueError::new_err("None cannot be a node"));
        }
        u.hash()?;
        if v.is_none() {
            self.add_node(py, u, None)?;
            return Err(PyValueError::new_err("None cannot be a node"));
        }
        if v.hash().is_err() {
            self.add_node(py, u, None)?;
            v.hash()?;
        }
        if let Some(explicit_key) = key
            && !explicit_key.is_none()
            && explicit_key.hash().is_err()
        {
            // br-r37-c1-baqyi: nx creates BOTH endpoint nodes before the
            // unhashable key raises (the key is first used after node
            // insertion in nx add_edge), so the partial state keeps them.
            self.add_node(py, u, None)?;
            self.add_node(py, v, None)?;
            explicit_key.hash()?;
        }

        let attr_is_empty = attr.is_none_or(|attrs| attrs.is_empty());
        if attr_is_empty
            && u.is_exact_instance_of::<PyInt>()
            && v.is_exact_instance_of::<PyInt>()
            && let Some(explicit_key) = key
        {
            if explicit_key.is_exact_instance_of::<PyInt>() {
                if let Some(fast_key) =
                    self.fast_add_explicit_fresh_int_endpoint_edge(py, u, v, explicit_key)?
                {
                    return Ok(fast_key);
                }
            } else if explicit_key.is_exact_instance_of::<PyString>()
                && let Some(fast_key) =
                    self.fast_add_explicit_fresh_int_endpoint_edge(py, u, v, explicit_key)?
            {
                return Ok(fast_key);
            }
        }

        let u_canonical = node_key_to_string(py, u)?;
        let v_canonical = node_key_to_string(py, v)?;

        // br-r37-c1-39d82: track new-node creation to bump
        // nodes_seq for iterator staleness detection.
        let __was_new = !self.node_key_map.contains_key(&u_canonical)
            || !self.node_key_map.contains_key(&v_canonical);

        self.node_key_map
            .entry(u_canonical.clone())
            .or_insert_with(|| u.clone().unbind());
        self.node_key_map
            .entry(v_canonical.clone())
            .or_insert_with(|| v.clone().unbind());
        if __was_new {
            self.bump_nodes_seq();
        }
        // br-r37-c1-z6uka: a NEW adjacency CELL (no keys yet for this
        // pair) records both row display objects; parallel keys reuse
        // the cell. Self-loops keep only v's object (nx's reverse
        // assignment cannot replace the hash-equal dict key).
        if !self.inner.has_edge(&u_canonical, &v_canonical) {
            let differs = |canonical: &str, passed: &Bound<'_, PyAny>| -> bool {
                self.node_key_map
                    .get(canonical)
                    .is_some_and(|stored| PyGraph::display_objs_conflict(stored.bind(py), passed))
            };
            if differs(&v_canonical, v) {
                self.adj_py_keys
                    .entry((u_canonical.clone(), v_canonical.clone()))
                    .or_insert_with(|| v.clone().unbind());
            }
            if u_canonical != v_canonical && differs(&u_canonical, u) {
                self.adj_py_keys
                    .entry((v_canonical.clone(), u_canonical.clone()))
                    .or_insert_with(|| u.clone().unbind());
            }
        }

        let mut rust_attrs = AttrMap::new();
        if let Some(a) = attr {
            rust_attrs = py_dict_to_attr_map(a)?;
        }

        // br-r37-c1-mgkey: for an AUTO key (key=None), compute the PUBLIC key as
        // networkx does — `k = len(G[u][v]); while k in G[u][v]: k += 1` over the
        // PUBLIC key set. fnx echoes the internal usize key as the public key for
        // auto-adds, but the internal key space diverges from the public keys
        // when explicit non-sequential public keys were added (e.g. an explicit
        // public key 1 mapped to internal key 0), so the auto key would COLLIDE
        // with an existing public key and silently overwrite that parallel edge.
        let auto_public_key: Option<PyObject> = if key.is_none() {
            let existing = self
                .inner
                .edge_keys(&u_canonical, &v_canonical)
                .unwrap_or_default();
            let mut int_public_keys = std::collections::HashSet::<i64>::new();
            for &k in &existing {
                if let Ok(i) = self
                    .py_edge_key(py, &u_canonical, &v_canonical, k)
                    .bind(py)
                    .extract::<i64>()
                {
                    int_public_keys.insert(i);
                }
            }
            let mut pk = existing.len() as i64;
            while int_public_keys.contains(&pk) {
                pk += 1;
            }
            Some(pk.into_pyobject(py)?.into_any().unbind())
        } else {
            None
        };

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
            // br-r37-c1-aefbatch: single C-level dict.update instead of N
            // per-item set_item calls (see PyGraph::add_edge).
            py_dict.bind(py).update(a.as_mapping())?;
        }
        // br-r37-c1-jft0i: bump edges_seq so view-materialization caches invalidate.
        self.bump_edges_seq();
        // Prefer the user's explicit key; otherwise echo the nx-computed public
        // auto key (NOT the internal usize key).
        let external = key.or_else(|| auto_public_key.as_ref().map(|o| o.bind(py)));
        Ok(self.remember_edge_key(py, &u_canonical, &v_canonical, actual_key, external))
    }

    /// Fast path for ``MultiGraph.add_edge(int, int, key=int)`` when the
    /// endpoint pair has no existing edge and no attributes are supplied.
    fn _fast_add_explicit_int_edge(
        &mut self,
        py: Python<'_>,
        u: &Bound<'_, PyAny>,
        v: &Bound<'_, PyAny>,
        key: &Bound<'_, PyAny>,
    ) -> PyResult<Option<PyObject>> {
        self.fast_add_explicit_fresh_int_endpoint_edge(py, u, v, key)
    }

    /// Fast path for ``MultiGraph.add_edge(int, int, key=str)`` when the
    /// endpoint pair has no existing edge and no attributes are supplied.
    fn _fast_add_explicit_str_edge(
        &mut self,
        py: Python<'_>,
        u: &Bound<'_, PyAny>,
        v: &Bound<'_, PyAny>,
        key: &Bound<'_, PyAny>,
    ) -> PyResult<Option<PyObject>> {
        self.fast_add_explicit_fresh_int_endpoint_edge(py, u, v, key)
    }

    fn fast_add_explicit_fresh_int_endpoint_edge(
        &mut self,
        py: Python<'_>,
        u: &Bound<'_, PyAny>,
        v: &Bound<'_, PyAny>,
        key: &Bound<'_, PyAny>,
    ) -> PyResult<Option<PyObject>> {
        let Ok(u_value) = u.extract::<i64>() else {
            return Ok(None);
        };
        let Ok(v_value) = v.extract::<i64>() else {
            return Ok(None);
        };

        let u_canonical = u_value.to_string();
        let v_canonical = v_value.to_string();
        if self.inner.has_edge(&u_canonical, &v_canonical) {
            return Ok(None);
        }
        // br-r37-c1-z6uka: if either endpoint's stored display object would
        // conflict with this exact-int key (e.g. node "16" stored as 16.0),
        // the slow path must record per-cell row objects — bail.
        let display_conflict = |canonical: &str, passed: &Bound<'_, PyAny>| -> bool {
            self.node_key_map
                .get(canonical)
                .is_some_and(|stored| PyGraph::display_objs_conflict(stored.bind(py), passed))
        };
        if display_conflict(&u_canonical, u) || display_conflict(&v_canonical, v) {
            return Ok(None);
        }

        let was_new_node = !self.node_key_map.contains_key(&u_canonical)
            || !self.node_key_map.contains_key(&v_canonical);
        self.node_key_map
            .entry(u_canonical.clone())
            .or_insert_with(|| u.clone().unbind());
        self.node_key_map
            .entry(v_canonical.clone())
            .or_insert_with(|| v.clone().unbind());
        if was_new_node {
            self.bump_nodes_seq();
        }
        if !key.is_instance_of::<PyBool>()
            && let Ok(explicit_key) = key.extract::<usize>()
        {
            let Some(_actual_key) = self.inner.add_fresh_edge_with_key_unrecorded(
                u_canonical.clone(),
                v_canonical.clone(),
                explicit_key,
            ) else {
                return Ok(None);
            };
            self.bump_edges_seq();
            return Ok(Some(key.clone().unbind()));
        }

        let Some(actual_key) = self
            .inner
            .add_fresh_edge_unrecorded(u_canonical.clone(), v_canonical.clone())
        else {
            return Ok(None);
        };
        let ek = Self::edge_key(&u_canonical, &v_canonical, actual_key);
        let py_key = key.clone().unbind();
        self.edge_py_keys.insert(ek, py_key.clone_ref(py));
        self.bump_edges_seq();
        Ok(Some(py_key))
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
        let removed = auto_removal_key.is_some()
            && self
                .inner
                .remove_edge(&u_canonical, &v_canonical, auto_removal_key);
        if !removed {
            return Err(NetworkXError::new_err(format!(
                "The edge {}-{} is not in the graph",
                u.repr()?,
                v.repr()?
            )));
        }
        if let Some(removed_key) = auto_removal_key {
            // br-r37-c1-0a0uo: purge the removed key's mirror entries even
            // when OTHER parallel keys survive — the bucket-emptying purge
            // below only runs when the pair empties, so a non-emptying
            // removal left a stale attrs dict that a re-added edge at the
            // same internal slot silently resurrected (add(4,3); add(4,3,
            // weight=7); remove_edge(4,3); add(4,3) showed weight=7 again;
            // metamorphic fuzz seeds 48/184/203).
            self.remove_edge_metadata(&u_canonical, &v_canonical, removed_key);
        }
        if !self.inner.has_edge(&u_canonical, &v_canonical) {
            if !self.adj_py_keys.is_empty() {
                // br-r37-c1-z6uka: the LAST parallel key removed empties the
                // adjacency cell — drop its row overrides (a re-add creates
                // fresh cells in nx).
                self.adj_py_keys
                    .remove(&(u_canonical.clone(), v_canonical.clone()));
                self.adj_py_keys
                    .remove(&(v_canonical.clone(), u_canonical.clone()));
            }
            // br-r37-c1-kuxuc: purge ALL mirror entries for the emptied
            // pair. The single-key remove_edge_metadata above can miss the
            // slot the mirror actually lives under (internal bucket keys vs
            // the key resolve_internal_edge_key returns), leaving a STALE
            // attrs/key dict that a re-added edge at the same internal slot
            // silently resurrects (add(0,0,attrs); remove; re-add showed the
            // old attrs — hypothesis fuzz catch). Exhaustive-by-pair removal
            // is exact regardless of which key space the entries used.
            let (a, b) = if u_canonical <= v_canonical {
                (u_canonical.clone(), v_canonical.clone())
            } else {
                (v_canonical.clone(), u_canonical.clone())
            };
            self.edge_py_attrs
                .retain(|(x, y, _), _| !(x == &a && y == &b));
            self.edge_py_keys
                .retain(|(x, y, _), _| !(x == &a && y == &b));
        }
        self.bump_edges_seq();
        Ok(())
    }

    fn clear(&mut self, py: Python<'_>) -> PyResult<()> {
        self.inner = MultiGraph::with_runtime_policy(self.inner.runtime_policy().clone());
        self.node_key_map.clear();
        self.node_py_attrs.clear();
        self.edge_py_attrs.clear();
        self.adj_py_keys.clear(); // br-r37-c1-z6uka
        self.edge_py_keys.clear();
        self.graph_attrs = PyDict::new(py).unbind();
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
        let policy = self.inner.runtime_policy().clone();
        Python::attach(|py| {
            let mut fresh = MultiGraph::with_runtime_policy(policy);
            for canonical in &ordered {
                let rust_attrs = self
                    .node_py_attrs
                    .get(canonical)
                    .map(|attrs| py_dict_to_attr_map(attrs.bind(py)))
                    .transpose()
                    .ok()
                    .flatten()
                    .unwrap_or_default();
                fresh.add_node_with_attrs(canonical.clone(), rust_attrs);
            }
            self.inner = fresh;
        });
        self.edge_py_attrs.clear();
        self.adj_py_keys.clear(); // br-r37-c1-z6uka
        self.edge_py_keys.clear();
        self.bump_edges_seq(); // br-r37-c1-jft0i
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

    fn __iter__(slf: PyRef<'_, Self>) -> PyResult<Py<NodeIterator>> {
        let py = slf.py();
        let expected_nodes: Vec<String> = slf
            .inner
            .nodes_ordered()
            .into_iter()
            .map(str::to_owned)
            .collect();
        let nodes: Vec<PyObject> = expected_nodes
            .iter()
            .map(|n| {
                slf.node_key_map.get(n).map_or_else(
                    || {
                        unwrap_infallible(n.to_owned().into_pyobject(py))
                            .into_any()
                            .unbind()
                    },
                    |obj| obj.clone_ref(py),
                )
            })
            .collect();
        let graph = Py::from(slf);
        Py::new(
            py,
            NodeIterator::with_graph_guard(
                py,
                nodes,
                NodeIteratorGuard::MultiGraph(graph),
                expected_nodes.len(),
            ),
        )
    }

    fn _native_adjacency_row(
        slf: PyRef<'_, Self>,
        n: &Bound<'_, PyAny>,
    ) -> PyResult<Py<MultiAtlasView>> {
        let py = slf.py();
        let canonical = node_key_to_string(py, n)?;
        if !slf.inner.has_node(&canonical) {
            return Err(missing_key_error(n));
        }
        Py::new(py, MultiAtlasView::new(Py::from(slf), canonical))
    }

    fn __getitem__(slf: PyRef<'_, Self>, n: &Bound<'_, PyAny>) -> PyResult<Py<MultiAtlasView>> {
        Self::_native_adjacency_row(slf, n)
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
    fn adj(&mut self, py: Python<'_>) -> PyResult<Py<PyDict>> {
        self.adjacency(py)
    }

    /// Return an adjacency dict: {node: {neighbor: {key: edge_attrs}}}.
    fn adjacency(&mut self, py: Python<'_>) -> PyResult<Py<PyDict>> {
        if self.inner.edge_count() > 0 {
            self.mark_edges_dirty();
        }
        let result = PyDict::new(py);
        let nodes: Vec<String> = self
            .inner
            .nodes_ordered()
            .into_iter()
            .map(str::to_owned)
            .collect();
        for node in &nodes {
            let py_node = self.py_node_key(py, node);
            let nbrs_dict = PyDict::new(py);
            let neighbors: Vec<String> = self
                .inner
                .neighbors(node)
                .unwrap_or_default()
                .into_iter()
                .map(str::to_owned)
                .collect();
            for neighbor in &neighbors {
                let py_nbr = self.py_adj_key(py, node, neighbor) /* br-r37-c1-z6uka */;
                nbrs_dict.set_item(&py_nbr, self.neighbor_dict(py, node, neighbor)?.bind(py))?;
            }
            result.set_item(py_node, nbrs_dict)?;
        }
        Ok(result.unbind())
    }

    /// br-r37-c1-mdadj: non-shadowed accessor for the native nested adjacency
    /// snapshot, so the Python MultiGraph.adjacency (_multigraph_adjacency) can
    /// build it natively instead of walking self.adj[node] via the
    /// MultiAdjacencyView lambda chain per element (~30000x slower than nx).
    fn _native_adjacency_dict(&mut self, py: Python<'_>) -> PyResult<Py<PyDict>> {
        self.adjacency(py)
    }

    /// br-r37-c1-mgedges: native node-major edge list so the Python
    /// _MultiGraphEdgeView.__call__ builds the all-edges result natively instead
    /// of triple-looping over self.adj[source] via the MultiAdjacencyView lambda
    /// chain (~10000x slower than nx). Matches nx's order EXACTLY: iterate
    /// nodes_ordered() (source), then neighbors (target, adjacency order), then
    /// edge_keys (key order), deduping each undirected edge by its canonical
    /// edge_key (so each parallel edge is emitted once, from its first-iterated
    /// endpoint). Tuple shape mirrors the Python branches: (u, v[, key][, attr])
    /// where attr is the live dict (data=True), attrs.get(key, default) (data=
    /// <key>), or absent (data=False). data=True marks edges dirty (live dict).
    fn _native_edge_view_list(
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
        let mut seen: HashSet<(String, String, usize)> = HashSet::new();
        let mut result: Vec<PyObject> = Vec::with_capacity(self.inner.edge_count());
        let nodes: Vec<String> = self
            .inner
            .nodes_ordered()
            .into_iter()
            .map(str::to_owned)
            .collect();
        for node in &nodes {
            let neighbors: Vec<String> = self
                .inner
                .neighbors(node)
                .unwrap_or_default()
                .into_iter()
                .map(str::to_owned)
                .collect();
            for neighbor in &neighbors {
                let edge_keys = self.inner.edge_keys(node, neighbor).unwrap_or_default();
                for key in edge_keys {
                    let ek = Self::edge_key(node, neighbor, key);
                    if !seen.insert(ek.clone()) {
                        continue;
                    }
                    let mut elems: Vec<PyObject> = Vec::with_capacity(4);
                    elems.push(self.py_node_key(py, node));
                    elems.push(
                        self.py_adj_key(py, node, neighbor), /* br-r37-c1-z6uka */
                    );
                    if keys {
                        elems.push(self.py_edge_key(py, node, neighbor, key));
                    }
                    if want_dict {
                        let attrs = self
                            .ensure_edge_py_attrs(py, node, neighbor, key)
                            .clone_ref(py)
                            .into_any();
                        elems.push(attrs);
                    } else if want_value {
                        let val = match self.edge_py_attrs.get(&ek) {
                            Some(d) => d
                                .bind(py)
                                .get_item(data)
                                .ok()
                                .flatten()
                                .map_or_else(|| default.clone_ref(py), |v| v.unbind()),
                            None => default.clone_ref(py),
                        };
                        elems.push(val);
                    }
                    result.push(PyTuple::new(py, &elems)?.into_any().unbind());
                }
            }
        }
        Ok(result)
    }

    /// br-r37-c1-wdeg: native total weighted degree, returning the full
    /// ``(node, total)`` sequence in node order. The Python
    /// MultiGraphDegreeView weighted path calls the module-level
    /// ``degree(G, node, weight)`` per node, which walks ``G.adj[node]`` via
    /// the MultiAdjacencyView lambda chain and ``keydict.values()`` per
    /// neighbor (~16000x slower than nx).
    ///
    /// nx's ``MultiDegreeView`` computes ``deg = sum(d.get(weight, 1) for
    /// key_dict in nbrs.values() for d in key_dict.values())`` — a single
    /// FLAT ``sum()`` over every (neighbor, key) in adjacency order — and,
    /// when a self-loop exists, ``deg += sum(d.get(weight, 1) for d in
    /// nbrs[n].values())`` (a second fresh ``sum`` over the self-loop keys).
    /// To stay bit-identical (CPython's ``sum`` is Neumaier-compensated for
    /// floats, and the association of the running total matters), we build
    /// the value list in nx's exact order and call the SAME builtin ``sum``
    /// rather than folding with ``+`` in Rust.
    fn _native_weighted_degree(
        &self,
        py: Python<'_>,
        weight: &str,
    ) -> PyResult<Vec<(PyObject, PyObject)>> {
        let one = 1i64.into_pyobject(py)?.into_any();
        let sum_fn = py.import("builtins")?.getattr("sum")?;
        let mut out: Vec<(PyObject, PyObject)> = Vec::with_capacity(self.inner.node_count());
        for node in self.inner.nodes_ordered() {
            let values = pyo3::types::PyList::empty(py);
            let mut selfloop = false;
            for neighbor in self.inner.neighbors(node).unwrap_or_default() {
                if neighbor == node {
                    selfloop = true;
                }
                for key in self.inner.edge_keys(node, neighbor).unwrap_or_default() {
                    let ek = Self::edge_key(node, neighbor, key);
                    let value = match self.edge_py_attrs.get(&ek) {
                        Some(d) => d
                            .bind(py)
                            .get_item(weight)
                            .ok()
                            .flatten()
                            .unwrap_or_else(|| one.clone()),
                        None => one.clone(),
                    };
                    values.append(value)?;
                }
            }
            let mut deg = sum_fn.call1((values,))?;
            if selfloop {
                let sl = pyo3::types::PyList::empty(py);
                for key in self.inner.edge_keys(node, node).unwrap_or_default() {
                    let ek = Self::edge_key(node, node, key);
                    let value = match self.edge_py_attrs.get(&ek) {
                        Some(d) => d
                            .bind(py)
                            .get_item(weight)
                            .ok()
                            .flatten()
                            .unwrap_or_else(|| one.clone()),
                        None => one.clone(),
                    };
                    sl.append(value)?;
                }
                deg = deg.add(sum_fn.call1((sl,))?)?;
            }
            out.push((self.py_node_key(py, node), deg.unbind()));
        }
        Ok(out)
    }

    // -----------------------------------------------------------------------
    // Copy / subgraph
    // -----------------------------------------------------------------------

    /// br-r37-c1-8uh84: native insertion-order-preserving copy, so the Python
    /// MultiGraph.copy (_copy_preserving_insertion_order) can build the clone
    /// natively instead of walking self.edges(keys=True, data=True) via the
    /// MultiAdjacencyView lambda chain into add_edges_from (~2100x slower).
    ///
    /// Unlike the internal `copy()` (which iterates the `node_key_map` HashMap
    /// and therefore scrambles node order), this iterates `nodes_ordered()` for
    /// node insertion order and `edges_ordered()` for edge insertion order +
    /// public endpoint orientation. Attr dicts are shallow-copied
    /// (`dict.copy()` — new dict, shared values) to match nx's shallow-copy
    /// contract (br-r37-c1-3tlkj).
    fn _native_copy(&self, py: Python<'_>) -> PyResult<Self> {
        let mut new_graph = Self {
            // br-r37-c1-7dpyg: fresh ledger, mode only (skip ledger clone)
            inner: MultiGraph::with_runtime_policy(fnx_runtime::RuntimePolicy::new(
                self.inner.mode(),
            )),
            node_key_map: HashMap::new(),
            adj_py_keys: self.derive_copy_adj_py_keys(py), // br-r37-c1-z6uka
            node_py_attrs: HashMap::new(),
            edge_py_attrs: HashMap::new(),
            edge_py_keys: HashMap::new(),
            graph_attrs: self.graph_attrs.bind(py).copy()?.unbind(),
            nodes_seq: 0,
            edges_seq: 0,
            edges_dirty: AtomicBool::new(false),
        };
        for node in self.inner.nodes_ordered() {
            let rust_attrs = self
                .node_py_attrs
                .get(node)
                .map(|attrs| py_dict_to_attr_map(attrs.bind(py)))
                .transpose()?
                .unwrap_or_default();
            new_graph
                .inner
                .add_node_with_attrs(node.to_owned(), rust_attrs);
            new_graph
                .node_key_map
                .insert(node.to_owned(), self.py_node_key(py, node));
            if let Some(attrs) = self.node_py_attrs.get(node) {
                new_graph
                    .node_py_attrs
                    .insert(node.to_owned(), attrs.bind(py).copy()?.unbind());
            }
        }
        for snapshot in self.inner.edges_ordered() {
            let (u, v, key) = (snapshot.left.clone(), snapshot.right.clone(), snapshot.key);
            let attrs_entry = self
                .edge_py_attrs
                .get(&(u.clone(), v.clone(), key))
                .or_else(|| self.edge_py_attrs.get(&(v.clone(), u.clone(), key)));
            let py_attrs = match attrs_entry {
                Some(attrs) => attrs.bind(py).copy()?.unbind(),
                None => PyDict::new(py).unbind(),
            };
            let rust_attrs = py_dict_to_attr_map(py_attrs.bind(py))?;
            let _ =
                new_graph
                    .inner
                    .add_edge_with_key_and_attrs(u.clone(), v.clone(), key, rust_attrs);
            new_graph
                .edge_py_attrs
                .insert((u.clone(), v.clone(), key), py_attrs);
            let py_key_slot = self
                .edge_py_keys
                .get(&(u.clone(), v.clone(), key))
                .or_else(|| self.edge_py_keys.get(&(v.clone(), u.clone(), key)));
            if let Some(py_key) = py_key_slot {
                new_graph.remember_edge_key_object(py, &u, &v, key, py_key);
            } else {
                new_graph.remember_edge_key(py, &u, &v, key, None);
            }
        }
        // br-r37-c1-s0d4x: cells in nx's u-major copy-walk order (the
        // edges_ordered rebuild above is edge INSERTION order).
        new_graph.inner.reorder_rows_for_nx_copy_walk();
        Ok(new_graph)
    }

    fn _native_to_undirected_deepcopy(&self, py: Python<'_>) -> PyResult<Self> {
        let deepcopy = py.import("copy")?.getattr("deepcopy")?;
        let mut new_graph = Self {
            inner: MultiGraph::with_runtime_policy(self.inner.runtime_policy().clone()),
            node_key_map: HashMap::new(),
            adj_py_keys: HashMap::new(), // br-r37-c1-z6uka
            node_py_attrs: HashMap::new(),
            edge_py_attrs: HashMap::new(),
            edge_py_keys: HashMap::new(),
            graph_attrs: deepcopy_py_dict(py, &deepcopy, &self.graph_attrs)?,
            nodes_seq: 0,
            edges_seq: 0,
            edges_dirty: AtomicBool::new(false),
        };
        for node in self.inner.nodes_ordered() {
            let py_attrs = self.node_py_attrs.get(node).map_or_else(
                || Ok(PyDict::new(py).unbind()),
                |attrs| deepcopy_py_dict(py, &deepcopy, attrs),
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
        for snapshot in self.inner.edges_ordered() {
            let (u, v, key) = (snapshot.left.clone(), snapshot.right.clone(), snapshot.key);
            let attrs_entry = self
                .edge_py_attrs
                .get(&Self::edge_key(&u, &v, key))
                .or_else(|| self.edge_py_attrs.get(&Self::edge_key(&v, &u, key)));
            let py_attrs = attrs_entry.map_or_else(
                || Ok(PyDict::new(py).unbind()),
                |attrs| deepcopy_py_dict(py, &deepcopy, attrs),
            )?;
            let rust_attrs = py_dict_to_attr_map(py_attrs.bind(py))?;
            let _ = new_graph
                .inner
                .add_edge_with_key_and_attrs(u.clone(), v.clone(), key, rust_attrs)
                .map_err(|e| NetworkXError::new_err(e.to_string()))?;
            new_graph
                .edge_py_attrs
                .insert(Self::edge_key(&u, &v, key), py_attrs);
            let py_key = self.py_edge_key(py, &u, &v, key);
            new_graph.remember_edge_key_object(py, &u, &v, key, &py_key);
        }
        Ok(new_graph)
    }

    fn _native_to_directed_deepcopy(
        &self,
        py: Python<'_>,
    ) -> PyResult<crate::digraph::PyMultiDiGraph> {
        let deepcopy = py.import("copy")?.getattr("deepcopy")?;
        let mut mdg = crate::digraph::PyMultiDiGraph {
            inner: fnx_classes::digraph::MultiDiGraph::with_runtime_policy(
                self.inner.runtime_policy().clone(),
            ),
            node_key_map: HashMap::new(),
            succ_py_keys: HashMap::new(), // br-r37-c1-z6uka
            pred_py_keys: HashMap::new(), // br-r37-c1-z6uka
            node_py_attrs: HashMap::new(),
            edge_py_attrs: HashMap::new(),
            edge_py_keys: HashMap::new(),
            graph_attrs: deepcopy_py_dict(py, &deepcopy, &self.graph_attrs)?,
            nodes_seq: 0,
            edges_seq: 0,
            edges_dirty: AtomicBool::new(false),
        };
        for node in self.inner.nodes_ordered() {
            let py_attrs = self.node_py_attrs.get(node).map_or_else(
                || Ok(PyDict::new(py).unbind()),
                |attrs| deepcopy_py_dict(py, &deepcopy, attrs),
            )?;
            let rust_attrs = py_dict_to_attr_map(py_attrs.bind(py))?;
            mdg.inner.add_node_with_attrs(node.to_owned(), rust_attrs);
            mdg.node_key_map
                .insert(node.to_owned(), self.py_node_key(py, node));
            mdg.node_py_attrs.insert(node.to_owned(), py_attrs);
        }
        for source in self.inner.nodes_ordered() {
            for target in self.inner.neighbors(source).unwrap_or_default() {
                for key in self.inner.edge_keys(source, target).unwrap_or_default() {
                    let attrs_entry = self.edge_py_attrs.get(&Self::edge_key(source, target, key));
                    let py_attrs = attrs_entry.map_or_else(
                        || Ok(PyDict::new(py).unbind()),
                        |attrs| deepcopy_py_dict(py, &deepcopy, attrs),
                    )?;
                    let rust_attrs = py_dict_to_attr_map(py_attrs.bind(py))?;
                    let new_key = mdg
                        .inner
                        .add_edge_with_attrs(source.to_owned(), target.to_owned(), rust_attrs)
                        .map_err(|e| NetworkXError::new_err(e.to_string()))?;
                    mdg.edge_py_attrs
                        .insert((source.to_owned(), target.to_owned(), new_key), py_attrs);
                    let py_key = self.py_edge_key(py, source, target, key);
                    mdg.remember_edge_key_object(py, source, target, new_key, &py_key);
                }
            }
        }
        Ok(mdg)
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

    /// Return a deep copy of the multigraph.
    fn copy(&self, py: Python<'_>) -> PyResult<Self> {
        // br-r37-c1-6xe9c: bulk-clone the inner Rust multigraph instead of
        // rebuilding it edge-by-edge. The previous loop iterated
        // `self.node_key_map` (a randomized-order HashMap) to re-add nodes, so
        // `list(G.copy())` came out in hash order — non-deterministic and
        // diverging from `list(G)` / networkx (project_copy_node_order). It also
        // re-added every edge via `add_edge_with_key_and_attrs` (String hashing
        // + adjacency insert) plus a redundant `py_dict_to_attr_map` re-parse.
        // `MultiGraph::clone` copies the IndexMap/IndexSet/Vec verbatim,
        // preserving node + edge + parallel-key insertion order exactly; only
        // the deep-copy of the Python attr dicts / key objects remains.
        let mut new_graph = Self {
            inner: self.inner.clone_with_fresh_policy(), // br-r37-c1-7dpyg: skip ledger
            node_key_map: HashMap::with_capacity(self.node_key_map.len()),
            adj_py_keys: self.derive_copy_adj_py_keys(py), // br-r37-c1-z6uka
            node_py_attrs: HashMap::with_capacity(self.node_py_attrs.len()),
            edge_py_attrs: HashMap::with_capacity(self.edge_py_attrs.len()),
            edge_py_keys: HashMap::with_capacity(self.edge_py_keys.len()),
            graph_attrs: self.graph_attrs.bind(py).copy()?.unbind(),
            nodes_seq: 0,
            edges_seq: 0,
            edges_dirty: AtomicBool::new(self.edges_dirty.load(Ordering::Relaxed)),
        };
        // br-r37-c1-s0d4x: nx's MultiGraph.copy() rebuild walk reorders
        // adjacency CELLS (u-major first-touch) just like simple Graph
        // (42bb1a8f8); the verbatim clone preserved source rows instead.
        new_graph.inner.reorder_rows_for_nx_copy_walk();
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
        // Deep-copy the edge attr dicts and the per-edge Python key objects
        // verbatim (preserving the first-wins key identity). Key orientation is
        // irrelevant — lookups probe both directions and edges() order comes
        // from the cloned inner.
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
        // br-r37-c1-o1i86: clone the inner Rust graph WHOLESALE.
        // The old rebuild iterated node_key_map (a HashMap — scrambled
        // node insertion order) and replayed edges_ordered() (adjacency-
        // walk order, NOT chronological), so adjacency ROW content order
        // diverged from the source after remove+re-add sequences. nx's
        // copy.copy shares _adj outright — rows must be IDENTICAL to the
        // source. MultiGraph::clone copies the IndexMap/IndexSet
        // structures verbatim (node order, edge order, row order, key
        // buckets). Node/edge attr dicts are independent COPIES (fnx's
        // locked copy.copy contract — see test_adj_mapping_parity).
        Ok(Self {
            inner: self.inner.clone_with_fresh_policy(), // br-r37-c1-7dpyg: skip ledger
            node_key_map: self
                .node_key_map
                .iter()
                .map(|(k, v)| (k.clone(), v.clone_ref(py)))
                .collect(),
            adj_py_keys: crate::digraph::PyDiGraph::clone_row_keys(py, &self.adj_py_keys), // br-r37-c1-z6uka
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
        })
    }

    /// Support ``copy.deepcopy(G)`` — returns a deep copy.
    #[pyo3(signature = (_memo=None))]
    fn __deepcopy__(&self, py: Python<'_>, _memo: Option<&Bound<'_, PyAny>>) -> PyResult<Self> {
        self.copy(py)
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
            inner: MultiGraph::with_runtime_policy(self.inner.runtime_policy().clone()),
            node_key_map: HashMap::new(),
            adj_py_keys: HashMap::new(), // br-r37-c1-z6uka
            node_py_attrs: HashMap::new(),
            edge_py_attrs: HashMap::new(),
            edge_py_keys: HashMap::new(),
            graph_attrs: self.graph_attrs.bind(py).copy()?.unbind(),
            nodes_seq: 0,
            edges_seq: 0,
            edges_dirty: AtomicBool::new(false),
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

        for edge in self.inner.edges_ordered() {
            if keep.contains(&edge.left) && keep.contains(&edge.right) {
                let ek = Self::edge_key(&edge.left, &edge.right, edge.key);
                let rust_attrs = self
                    .edge_py_attrs
                    .get(&ek)
                    .map(|attrs| py_dict_to_attr_map(attrs.bind(py)))
                    .transpose()?
                    .unwrap_or_default();
                let _ = new_graph.inner.add_edge_with_key_and_attrs(
                    edge.left.clone(),
                    edge.right.clone(),
                    edge.key,
                    rust_attrs,
                );
                if let Some(attrs) = self.edge_py_attrs.get(&ek) {
                    new_graph
                        .edge_py_attrs
                        .insert(ek.clone(), attrs.bind(py).copy()?.unbind());
                }
                if let Some(py_key) = self.edge_py_keys.get(&ek) {
                    new_graph.remember_edge_key_object(
                        py,
                        &edge.left,
                        &edge.right,
                        edge.key,
                        py_key,
                    );
                } else {
                    new_graph.remember_edge_key(py, &edge.left, &edge.right, edge.key, None);
                }
            }
        }

        if !self.adj_py_keys.is_empty() {
            // br-r37-c1-z6uka: cell overrides for surviving cells (nx walk).
            new_graph.adj_py_keys = self
                .derive_copy_adj_py_keys(py)
                .into_iter()
                .filter(|((a, b), _)| new_graph.inner.has_edge(a, b))
                .collect();
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
                self.resolve_internal_edge_key(py, &u, &v, &tuple.get_item(2)?)?
            } else {
                None
            };
            keep_edges.push((u, v, key));
        }

        let mut involved_nodes: HashSet<String> = HashSet::new();
        let mut new_graph = Self {
            inner: MultiGraph::with_runtime_policy(self.inner.runtime_policy().clone()),
            node_key_map: HashMap::new(),
            adj_py_keys: HashMap::new(), // br-r37-c1-z6uka
            node_py_attrs: HashMap::new(),
            edge_py_attrs: HashMap::new(),
            edge_py_keys: HashMap::new(),
            graph_attrs: self.graph_attrs.bind(py).copy()?.unbind(),
            nodes_seq: 0,
            edges_seq: 0,
            edges_dirty: AtomicBool::new(false),
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
                    if let Some(py_key) = self.edge_py_keys.get(&Self::edge_key(u, v, k)) {
                        new_graph.remember_edge_key_object(py, u, v, k, py_key);
                    } else {
                        new_graph.remember_edge_key(py, u, v, k, None);
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

        if !self.adj_py_keys.is_empty() {
            // br-r37-c1-z6uka: cell overrides for surviving cells (nx walk).
            new_graph.adj_py_keys = self
                .derive_copy_adj_py_keys(py)
                .into_iter()
                .filter(|((a, b), _)| new_graph.inner.has_edge(a, b))
                .collect();
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
            inner: fnx_classes::digraph::MultiDiGraph::with_runtime_policy(
                self.inner.runtime_policy().clone(),
            ),
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
            mdg.remember_edge_key_object(py, u, v, new_k1, &self.py_edge_key(py, u, v, k));

            if u != v {
                let new_k2 = mdg
                    .inner
                    .add_edge_with_attrs(v.clone(), u.clone(), rust_attrs)
                    .map_err(|e| crate::NetworkXError::new_err(e.to_string()))?;
                if let Some(pa) = py_attrs_copy {
                    mdg.edge_py_attrs.insert((v.clone(), u.clone(), new_k2), pa);
                }
                mdg.remember_edge_key_object(py, v, u, new_k2, &self.py_edge_key(py, u, v, k));
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
            let (u, v, w) = weighted_edge_triplet(&item)?;
            let d = PyDict::new(py);
            d.set_item(weight, &w)?;
            self.add_edge(py, &u, &v, None, Some(&d))?;
        }
        self.bump_edges_seq();
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
                Some(tuple.get_item(2)?)
            } else {
                None
            };
            let u_c = node_key_to_string(py, u)?;
            let v_c = node_key_to_string(py, v)?;
            // Silently skip edges not in the graph
            if self.inner.has_edge(&u_c, &v_c) {
                let _ = self.remove_edge(py, u, v, key.as_ref());
            }
        }
        self.bump_edges_seq();
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
                let py_u = self.py_node_key(py, &edge.left);
                let py_v = self.py_adj_key(py, &edge.left, &edge.right) /* br-r37-c1-z6uka */;
                let py_key = self.py_edge_key(py, &edge.left, &edge.right, edge.key);
                let attrs = self
                    .edge_py_attrs
                    .get(&Self::edge_key(&edge.left, &edge.right, edge.key))
                    .map_or_else(|| PyDict::new(py).unbind(), |d| d.clone_ref(py));
                (py_u, py_v, py_key, attrs)
            })
            .collect();
        state.set_item("edges", edges_list)?;
        state.set_item("graph", self.graph_attrs.bind(py))?;
        // br-r37-c1-u3qyn: store adjacency rows + display overrides so the
        // round-trip preserves row order verbatim (see PyGraph).
        let adj_rows: Vec<(String, Vec<String>)> = self
            .inner
            .nodes_ordered()
            .into_iter()
            .map(|n| {
                (
                    n.to_owned(),
                    self.inner
                        .neighbors(n)
                        .unwrap_or_default()
                        .into_iter()
                        .map(str::to_owned)
                        .collect(),
                )
            })
            .collect();
        state.set_item("adj_rows", adj_rows)?;
        if !self.adj_py_keys.is_empty() {
            let overrides: Vec<(String, String, PyObject)> = self
                .adj_py_keys
                .iter()
                .map(|((a, b), o)| (a.clone(), b.clone(), o.clone_ref(py)))
                .collect();
            state.set_item("adj_py_keys", overrides)?;
        }
        Ok(state.into_any().unbind())
    }

    fn __setstate__(&mut self, py: Python<'_>, state: &Bound<'_, PyDict>) -> PyResult<()> {
        let mode = compatibility_mode_from_py(state.get_item("mode")?.as_ref())?;
        self.inner = MultiGraph::with_runtime_policy(runtime_policy_from_state(state, mode)?);
        self.node_key_map.clear();
        self.node_py_attrs.clear();
        self.edge_py_attrs.clear();
        self.adj_py_keys.clear(); // br-r37-c1-u3qyn
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

        // br-r37-c1-u3qyn: restore the source's exact adjacency row order
        // and display-object overrides when the state carries them.
        if let Some(rows) = state.get_item("adj_rows")? {
            let orders: Vec<(String, Vec<String>)> = rows.extract()?;
            self.inner.apply_row_orders(&orders);
        }
        if let Some(overrides) = state.get_item("adj_py_keys")? {
            let entries: Vec<(String, String, PyObject)> = overrides.extract()?;
            for (a, b, o) in entries {
                self.adj_py_keys.insert((a, b), o);
            }
        }

        Ok(())
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
        Py::new(py, NodeIterator::unguarded(nodes))
    }

    #[pyo3(signature = (data=false, default=None))]
    fn __call__(
        &self,
        py: Python<'_>,
        data: bool,
        default: Option<PyObject>,
    ) -> PyResult<Vec<PyObject>> {
        let _ = default;
        if data {
            let mut g = self.graph.borrow_mut(py);
            let mut result = Vec::new();
            let nodes: Vec<String> = g
                .inner
                .nodes_ordered()
                .into_iter()
                .map(str::to_owned)
                .collect();
            for node in &nodes {
                let py_node = g.py_node_key(py, node);
                let attrs = g.ensure_node_py_attrs(py, node).clone_ref(py).into_any();
                let pair = PyTuple::new(py, &[py_node, attrs])?;
                result.push(pair.into_any().unbind());
            }
            Ok(result)
        } else {
            let g = self.graph.borrow(py);
            Ok(g.inner
                .nodes_ordered()
                .into_iter()
                .map(|n| g.py_node_key(py, n))
                .collect())
        }
    }

    fn __getitem__(&self, py: Python<'_>, n: &Bound<'_, PyAny>) -> PyResult<PyObject> {
        let mut g = self.graph.borrow_mut(py);
        let canonical = node_key_to_string(py, n)?;
        if !g.inner.has_node(&canonical) {
            return Err(missing_key_error(n));
        }
        Ok(g.ensure_node_py_attrs(py, &canonical)
            .clone_ref(py)
            .into_any())
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
        Ok(g.ensure_node_py_attrs(py, &canonical)
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

    /// Return a list of (node, attrs) pairs (like dict.items()).
    fn items(&self, py: Python<'_>) -> PyResult<Vec<PyObject>> {
        let mut g = self.graph.borrow_mut(py);
        let mut result = Vec::new();
        let nodes: Vec<String> = g
            .inner
            .nodes_ordered()
            .into_iter()
            .map(str::to_owned)
            .collect();
        for node in &nodes {
            let py_key = g.py_node_key(py, node);
            let attrs = g.ensure_node_py_attrs(py, node).clone_ref(py).into_any();
            let pair = PyTuple::new(py, &[py_key, attrs])?;
            result.push(pair.into_any().unbind());
        }
        Ok(result)
    }

    /// Return a list of attr dicts (like dict.values()).
    fn values(&self, py: Python<'_>) -> PyResult<Vec<PyObject>> {
        let mut g = self.graph.borrow_mut(py);
        let nodes: Vec<String> = g
            .inner
            .nodes_ordered()
            .into_iter()
            .map(str::to_owned)
            .collect();
        Ok(nodes
            .iter()
            .map(|n| g.ensure_node_py_attrs(py, n).clone_ref(py).into_any())
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
        let mut g = self.graph.borrow_mut(py);
        let mut result = Vec::new();
        let nodes: Vec<String> = g
            .inner
            .nodes_ordered()
            .into_iter()
            .map(str::to_owned)
            .collect();
        for node in &nodes {
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
                    g.ensure_node_py_attrs(py, node).clone_ref(py).into_any()
                }
            } else {
                g.ensure_node_py_attrs(py, node).clone_ref(py).into_any()
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
        // Undirected graph: check both orientations
        let has = g.inner.has_edge(&u, &v) || g.inner.has_edge(&v, &u);
        if !has {
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
            let el = edge.left.as_str();
            let er = edge.right.as_str();
            let u_str = u.as_str();
            let v_str = v.as_str();
            if (el == u_str && er == v_str && edge.key == key)
                || (el == v_str && er == u_str && edge.key == key)
            {
                return Ok(true);
            }
        }
        Ok(false)
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
        let _ = default;
        let mut g = self.graph.borrow_mut(py);
        if data && g.inner.edge_count() > 0 {
            g.mark_edges_dirty();
        }
        let expected_nodes: Vec<String> = g
            .inner
            .nodes_ordered()
            .into_iter()
            .map(str::to_owned)
            .collect();
        let mut result = Vec::new();
        let edges = g.inner.edges_ordered();
        for edge in &edges {
            let py_u = g.py_node_key(py, &edge.left);
            let py_v = g.py_node_key(py, &edge.right);
            if data && keys {
                let attrs = g
                    .ensure_edge_py_attrs(py, &edge.left, &edge.right, edge.key)
                    .clone_ref(py)
                    .into_any();
                let key_obj = g.py_edge_key(py, &edge.left, &edge.right, edge.key);
                let tuple = PyTuple::new(py, &[py_u, py_v, key_obj, attrs])?;
                result.push(tuple.into_any().unbind());
            } else if data {
                let attrs = g
                    .ensure_edge_py_attrs(py, &edge.left, &edge.right, edge.key)
                    .clone_ref(py)
                    .into_any();
                let tuple = PyTuple::new(py, &[py_u, py_v, attrs])?;
                result.push(tuple.into_any().unbind());
            } else if keys {
                let key_obj = g.py_edge_key(py, &edge.left, &edge.right, edge.key);
                let tuple = PyTuple::new(py, &[py_u, py_v, key_obj])?;
                result.push(tuple.into_any().unbind());
            } else {
                let tuple = PyTuple::new(py, &[py_u, py_v])?;
                result.push(tuple.into_any().unbind());
            }
        }
        Py::new(
            py,
            NodeIterator::with_graph_guard(
                py,
                result,
                NodeIteratorGuard::MultiGraph(self.graph.clone_ref(py)),
                expected_nodes.len(),
            ),
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
            return Err(missing_key_error(n));
        }
        // For multigraphs, degree counts all parallel edges
        Ok(g.inner.degree(&canonical))
    }

    fn __iter__(&self, py: Python<'_>) -> PyResult<Py<NodeIterator>> {
        let g = self.graph.borrow(py);
        let mut result = Vec::new();
        for node in g.inner.nodes_ordered() {
            let py_node = g.py_node_key(py, node);
            let deg = g.inner.degree(node).into_py_any(py)?;
            let pair = PyTuple::new(py, &[py_node, deg])?;
            result.push(pair.into_any().unbind());
        }
        Py::new(py, NodeIterator::unguarded(result))
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

        let mut g = Self::new_empty_with_mode(py, CompatibilityMode::Strict)?;
        g.graph_attrs = graph_attrs.unbind();

        if let Some(data) = incoming_graph_data {
            // br-r37-c1-ymeml: fnx-native graph inputs are rebuilt by the
            // Python __init__ unconditionally — skip the absorb (the
            // graph-copy branches below are now dead for native inputs;
            // cleanup once the shared-file locks lift). Mode carries over.
            if let Some(mode) = fnx_graph_instance_mode(data) {
                g.inner = Graph::new(mode);
                return Ok(g);
            }
            // If it's another PyGraph, copy it.
            if let Ok(other) = data.extract::<PyRef<'_, PyGraph>>() {
                g.inner = other.inner.clone();
                g.lazy_int_node_stop = other.lazy_int_node_stop;
                for canonical in other.inner.nodes_ordered() {
                    g.node_key_map
                        .insert(canonical.to_owned(), other.py_node_key(py, canonical));
                    if let Some(attrs) = other.node_py_attrs.get(canonical) {
                        let copied = attrs.bind(py).copy()?.unbind();
                        g.inner
                            .replace_node_attrs(canonical, py_dict_to_attr_map(copied.bind(py))?);
                        g.node_py_attrs.insert(canonical.to_owned(), copied);
                    }
                }
                for ((u, v), attrs) in &other.edge_py_attrs {
                    let copied = attrs.bind(py).copy()?.unbind();
                    g.edge_py_attrs
                        .insert((u.clone(), v.clone()), copied.clone_ref(py));
                    g.inner
                        .replace_edge_attrs(u, v, py_dict_to_attr_map(copied.bind(py))?);
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

        if let Some(a) = attr {
            g.graph_attrs.bind(py).update(a.as_mapping())?;
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
                for (left, right, _attrs) in self.inner.edges_ordered_borrowed() {
                    let key = Self::edge_key(left, right);
                    match self.edge_py_attrs.get(&key) {
                        Some(dict) => match dict.bind(py).get_item(attr)? {
                            Some(val) => {
                                total += val.extract::<f64>()?;
                            }
                            None => {
                                total += 1.0;
                            }
                        },
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
        let was_new = !self.inner.has_node(&canonical);
        // br-r37-c1-firstwins: nx uses dicts for node storage, so the
        // FIRST Python object added under a given canonical key wins
        // (subsequent ``add_node`` calls with hash-equivalent keys are
        // no-ops at the storage level — the original Py object is
        // preserved for ``list(G.nodes())`` and friends). Use
        // ``entry().or_insert_with`` here so re-adding ``0.0`` after
        // ``0`` doesn't overwrite the displayed Py form. ``add_edge``
        // already uses this pattern at the call site below.
        if self.should_store_node_key(&canonical, was_new) {
            self.node_key_map
                .entry(canonical.clone())
                .or_insert_with(|| n.clone().unbind());
        }

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
        self.bump_nodes_seq();
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
        self.bump_nodes_seq();
        Ok(())
    }

    fn _fast_add_int_nodes_range_stop(&mut self, _py: Python<'_>, stop: i64) -> PyResult<()> {
        if stop <= 0 {
            return Ok(());
        }
        let count = usize::try_from(stop).unwrap_or(usize::MAX);
        let mut canonicals = Vec::with_capacity(count);
        self.lazy_int_node_stop = self.lazy_int_node_stop.max(stop);
        for node in 0..stop {
            let canonical = node.to_string();
            canonicals.push(canonical);
            self.bump_nodes_seq();
        }
        let _ = self.inner.extend_nodes_unrecorded(canonicals);
        Ok(())
    }

    fn _fast_add_int_nodes(&mut self, py: Python<'_>, nodes: Vec<i64>) -> PyResult<()> {
        let empty_attrs = AttrMap::new();
        for node in nodes {
            let canonical = node.to_string();
            self.node_key_map
                .entry(canonical.clone())
                .or_insert_with(|| {
                    unwrap_infallible(node.into_pyobject(py))
                        .into_any()
                        .unbind()
                });
            self.node_py_attrs
                .entry(canonical.clone())
                .or_insert_with(|| PyDict::new(py).unbind());
            self.inner
                .add_node_with_attrs(canonical, empty_attrs.clone());
            self.bump_nodes_seq();
        }
        Ok(())
    }

    /// Remove a single node. Raises ``NetworkXError`` if not present.
    fn remove_node(&mut self, py: Python<'_>, n: &Bound<'_, PyAny>) -> PyResult<()> {
        let canonical = node_key_to_string(py, n)?;
        if !self.inner.has_node(&canonical) {
            return Err(crate::NetworkXError::new_err(format!(
                "The node {} is not in the graph.",
                n.repr()?
            )));
        }
        log::debug!(target: "franken_networkx", "remove_node: {canonical}");

        // surgically remove attributes for incident edges before removing node from inner graph
        let mut had_incident_edges = false;
        if let Some(neighbors) = self.inner.neighbors(&canonical) {
            for nb in neighbors {
                let ek = Self::edge_key(&canonical, nb);
                self.edge_py_attrs.remove(&ek);
                had_incident_edges = true;
            }
        }

        self.inner.remove_node(&canonical);
        self.node_key_map.remove(&canonical);
        self.node_py_attrs.remove(&canonical);
        if !self.adj_py_keys.is_empty() {
            // br-r37-c1-z6uka: drop adjacency-row overrides touching the
            // removed node.
            self.adj_py_keys
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

    /// Remove multiple nodes. Silently skips absent nodes.
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
        self.edge_py_attrs.retain(|(left, right), _| {
            let keep =
                !present_refs.contains(left.as_str()) && !present_refs.contains(right.as_str());
            if !keep {
                removed_py_edge_attrs = true;
            }
            keep
        });
        let (_removed_nodes, removed_edges) =
            self.inner.remove_nodes_from(present_refs.iter().copied());
        for canonical in &present {
            self.node_key_map.remove(canonical);
            self.node_py_attrs.remove(canonical);
        }
        if !self.adj_py_keys.is_empty() {
            // br-r37-c1-z6uka: drop adjacency-row overrides touching removed nodes.
            self.adj_py_keys
                .retain(|(a, b), _| !present.contains(a) && !present.contains(b));
        }
        self.bump_nodes_seq();
        if removed_edges > 0 || removed_py_edge_attrs {
            self.bump_edges_seq(); // br-r37-c1-jft0i
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

        // br-r37-c1-39d82: track new-node creation to bump
        // nodes_seq for iterator staleness detection.
        let u_was_new = !self.inner.has_node(&u_canonical);
        let v_was_new = !self.inner.has_node(&v_canonical);
        let __was_new = u_was_new || v_was_new;

        // Ensure nodes exist in our maps.
        if self.should_store_node_key(&u_canonical, u_was_new) {
            self.node_key_map
                .entry(u_canonical.clone())
                .or_insert_with(|| u.clone().unbind());
        }
        if self.should_store_node_key(&v_canonical, v_was_new) {
            self.node_key_map
                .entry(v_canonical.clone())
                .or_insert_with(|| v.clone().unbind());
        }
        if __was_new {
            self.bump_nodes_seq();
        }
        // br-r37-c1-z6uka: a NEW edge creates both adjacency cells with
        // the objects passed in THIS call (nx `_adj[u][v] = ...` /
        // `_adj[v][u] = ...`); existing cells keep their original object.
        // For a SELF-LOOP both nx assignments hit the same dict cell and
        // the second cannot replace the hash-equal key — only v's object
        // applies (shrunk repro: add_edge(12.0, 12) renders (12, 12)).
        if !self.inner.has_edge(&u_canonical, &v_canonical) {
            self.maybe_store_adj_key(py, &u_canonical, &v_canonical, v);
            if u_canonical != v_canonical {
                self.maybe_store_adj_key(py, &v_canonical, &u_canonical, u);
            }
        }
        // br-r37-c1-89kxg: mirrors are LAZY — node dicts and attr-less edge
        // dicts are created on first observation by the render paths.
        // Build Rust AttrMap.
        let mut rust_attrs = AttrMap::new();
        if let Some(a) = attr
            && !a.is_empty()
        {
            rust_attrs = py_dict_to_attr_map(a)?;
            let ek = Self::edge_key(&u_canonical, &v_canonical);
            // br-r37-c1-aefbatch: a single C-level dict.update copies all items
            // in one call instead of N Rust->Python set_item round-trips, which
            // dominated attributed edge construction (add_edges_from / from_dict
            // build paths were ~7x nx). The edge dict is freshly created for new
            // edges and merged-into for existing ones; update() matches both.
            self.edge_py_attrs
                .entry(ek)
                .or_insert_with(|| PyDict::new(py).unbind())
                .bind(py)
                .update(a.as_mapping())?;
        }

        log::debug!(target: "franken_networkx", "add_edge: {u_canonical} -- {v_canonical}");
        self.inner
            .add_edge_with_attrs(u_canonical, v_canonical, rust_attrs)
            .map_err(|e| NetworkXError::new_err(e.to_string()))?;
        // br-r37-c1-jft0i: bump edges_seq so view-materialization caches invalidate.
        self.bump_edges_seq();
        Ok(())
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
        if !has_global_attr && self.try_add_plain_edge_batch(py, ebunch_to_add)? {
            return Ok(());
        }
        // br-r37-c1-pr8q6: attributed batch — (u, v, dict) tuples (mixed
        // with plain (u, v)) commit through ONE
        // extend_edges_with_attrs_unrecorded call instead of the per-edge
        // add_edge below (whose record_decision ledger push dominated
        // attributed construction at ~6x nx). Any item the batch can't
        // replicate exactly falls through to the loop unchanged.
        if !has_global_attr && self.try_add_attr_edge_batch(py, ebunch_to_add)? {
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
            // Fast path: no global attrs and no per-edge attrs.
            if !has_global_attr && len == 2 {
                self.add_edge(py, &u, &v, None)?;
            } else if !has_global_attr && len == 3 {
                // br-r37-c1-aefbatch: with no global attr, the third element
                // (when already a dict) is the edge data verbatim. ``add_edge``
                // copies it into its own edge_py_attrs dict, so we can hand it
                // through directly instead of materializing+updating a throwaway
                // ``merged`` PyDict per edge (one fewer dict alloc + copy on the
                // dominant construction path: from_dict_of_dicts / list-of-3-tuples).
                let d = tuple.get_item(2)?;
                if let Ok(dict_arg) = d.downcast::<PyDict>() {
                    self.add_edge(py, &u, &v, Some(dict_arg))?;
                } else {
                    // Non-dict third element: replicate nx's TypeError shape by
                    // routing through ``dict.update`` (see br-edges3rd below).
                    //
                    // br-r37-c1-a4zlp: nx adds BOTH endpoint nodes before it
                    // touches the edge datadict (``if u not in self._node:
                    // ... if v not in self._node: ... datadict.update(dd)``),
                    // so when the update raises, u and v persist on the
                    // graph. Create them first so the partial error state
                    // matches nx exactly.
                    self.add_node(py, &u, None)?;
                    self.add_node(py, &v, None)?;
                    let merged = PyDict::new(py);
                    match merged.call_method1("update", (d,)) {
                        Ok(_) => {}
                        Err(err) => return Err(err),
                    }
                    self.add_edge(py, &u, &v, Some(&merged))?;
                }
            } else {
                let merged = PyDict::new(py);
                if let Some(a) = attr {
                    merged.update(a.as_mapping())?;
                }
                if len == 3 {
                    let d = tuple.get_item(2)?;
                    // br-edges3rd: nx raises TypeError when the third
                    // element isn't a dict-or-iterable-of-pairs, e.g.
                    // ``add_edges_from([(0, 1, 1.5)])`` — the float gets
                    // passed to ``dict.update()`` which fails with
                    // ``'float' object is not iterable``. Previously
                    // fnx silently dropped non-dict third elements,
                    // diverging from nx parity.
                    if let Ok(dict_arg) = d.downcast::<PyDict>() {
                        merged.update(dict_arg.as_mapping())?;
                    } else {
                        // Try treating it as a mapping-iterable (list of
                        // (key, value) pairs); on failure raise the same
                        // TypeError shape nx surfaces. We cast through
                        // ``PyDict.update`` to get nx-compatible wording.
                        //
                        // br-r37-c1-a4zlp: as in the no-global-attr branch
                        // above, nx creates both endpoint nodes before the
                        // failing datadict.update — reproduce that partial
                        // state before raising.
                        self.add_node(py, &u, None)?;
                        self.add_node(py, &v, None)?;
                        let throwaway = PyDict::new(py);
                        match throwaway.call_method1("update", (d,)) {
                            Ok(_) => {
                                merged.update(throwaway.as_mapping())?;
                            }
                            Err(err) => return Err(err),
                        }
                    }
                }
                self.add_edge(py, &u, &v, Some(&merged))?;
            }
        }
        self.bump_edges_seq();
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
            let u_was_new = !self.inner.has_node(&u_s);
            let v_was_new = !self.inner.has_node(&v_s);

            // Insert node key maps only if new.
            if self.should_store_node_key(&u_s, u_was_new) {
                self.node_key_map
                    .entry(u_s.clone())
                    .or_insert_with(|| unwrap_infallible(u.into_pyobject(py)).into_any().unbind());
            }
            if self.should_store_node_key(&v_s, v_was_new) {
                self.node_key_map
                    .entry(v_s.clone())
                    .or_insert_with(|| unwrap_infallible(v.into_pyobject(py)).into_any().unbind());
            }
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
            let (u, v, w) = weighted_edge_triplet(&item)?;
            let d = PyDict::new(py);
            d.set_item(weight, &w)?;
            self.add_edge(py, &u, &v, Some(&d))?;
        }
        self.bump_edges_seq();
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
        if !self.adj_py_keys.is_empty() {
            // br-r37-c1-z6uka: re-adding the edge later creates FRESH
            // adjacency cells (nx deletes the row entries) — drop overrides.
            self.adj_py_keys
                .remove(&(u_canonical.clone(), v_canonical.clone()));
            self.adj_py_keys.remove(&(v_canonical, u_canonical));
        }
        self.bump_edges_seq();
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
            if !self.adj_py_keys.is_empty() {
                // br-r37-c1-z6uka: drop adjacency-row overrides for the removed edge.
                self.adj_py_keys.remove(&(u_c.clone(), v_c.clone()));
                self.adj_py_keys.remove(&(v_c.clone(), u_c.clone()));
            }
        }
        self.bump_edges_seq();
        Ok(())
    }

    // ---- Utility methods ----

    /// Remove all nodes and edges.
    fn clear(&mut self, py: Python<'_>) -> PyResult<()> {
        // Rebuild from scratch is simpler and correct.
        self.inner = Graph::with_runtime_policy(self.inner.runtime_policy().clone());
        self.node_key_map.clear();
        self.lazy_int_node_stop = 0;
        self.node_py_attrs.clear();
        self.edge_py_attrs.clear();
        self.adj_py_keys.clear(); // br-r37-c1-z6uka
        self.graph_attrs = PyDict::new(py).unbind();
        self.bump_nodes_seq();
        self.bump_edges_seq(); // br-r37-c1-jft0i
        Ok(())
    }

    /// Remove all edges but keep nodes and their attributes.
    fn clear_edges(&mut self) {
        // Remove all edges from inner graph.
        let edges: Vec<(String, String)> = self
            .inner
            .edges_ordered_borrowed()
            .into_iter()
            .map(|(left, right, _)| (left.to_owned(), right.to_owned()))
            .collect();
        for (u, v) in edges {
            self.inner.remove_edge(&u, &v);
        }
        self.edge_py_attrs.clear();
        self.adj_py_keys.clear(); // br-r37-c1-z6uka
        self.bump_edges_seq(); // br-r37-c1-jft0i
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
                .map(|nb| self.py_adj_key(py, &canonical, nb)) // br-r37-c1-z6uka
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
                .map(|nb| self.py_adj_key(py, node, nb)) // br-r37-c1-z6uka
                .collect();
            result.push((py_node, neighbors));
        }
        Ok(result)
    }

    /// br-r37-c1-genadjbulk: private-named node-major neighbour-KEY snapshot for
    /// `generate_adjlist`, so it walks the whole graph in ONE native call instead
    /// of `len(G)` per-node `G.neighbors()` PyO3 round-trips. Same `(node,
    /// [neighbour, ...])` shape and source/adjacency order as `adjacency()`, but
    /// under a private name the Python `Graph.adjacency` wrapper (which returns
    /// nx's `{nbr: attrs}` dict form) does not shadow. No edge-attr dicts built.
    fn _native_adjacency_keys<'py>(
        &self,
        py: Python<'py>,
    ) -> PyResult<Vec<(PyObject, Vec<PyObject>)>> {
        self.adjacency(py)
    }

    /// br-r37-c1-zt6lj: true when the internal canonical node strings are also
    /// the Python display strings used by `generate_adjlist`. In that shape the
    /// existing Rust readwrite serializer is byte-body identical and can avoid
    /// the Python generator path; mixed/custom Python node keys fall back.
    fn _native_adjlist_canonical_body_safe(&self) -> bool {
        self.node_key_map.is_empty() && self.adj_py_keys.is_empty()
    }

    /// br-r37-c1-gadj: native nested adjacency snapshot ({node: {nbr: attrs}})
    /// so the Python Graph.adjacency (_simple_graph_adjacency) builds it
    /// natively instead of walking ``dict(self.adj[node])`` via the AtlasView
    /// lambda chain per node (~150x slower than nx). The inner ``{nbr: attrs}``
    /// dicts reuse the live ``edge_py_attrs`` Py<PyDict> references (matching
    /// nx's shared-datadict semantics: ``dict(G.adjacency())[u][v] is
    /// G[u][v]``), in node x neighbour adjacency order.
    fn _native_adjacency_dict(&mut self, py: Python<'_>) -> PyResult<Py<PyDict>> {
        if self.inner.edge_count() > 0 {
            self.mark_edges_dirty();
        }
        let result = PyDict::new(py);
        let nodes: Vec<String> = self
            .inner
            .nodes_ordered()
            .into_iter()
            .map(str::to_owned)
            .collect();
        for node in nodes {
            let py_node = self.py_node_key(py, &node);
            let nbrs_dict = PyDict::new(py);
            let neighbors: Vec<String> = self
                .inner
                .neighbors(&node)
                .unwrap_or_default()
                .into_iter()
                .map(str::to_owned)
                .collect();
            for neighbor in neighbors {
                let py_nbr = self.py_node_key(py, &neighbor);
                let attrs = self.materialize_edge_py_attrs(py, &node, &neighbor);
                nbrs_dict.set_item(&py_nbr, attrs.bind(py))?;
            }
            result.set_item(py_node, nbrs_dict)?;
        }
        Ok(result.unbind())
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
    fn __iter__(slf: PyRef<'_, Self>) -> PyResult<Py<NodeIterator>> {
        let py = slf.py();
        let expected_nodes: Vec<String> = slf
            .inner
            .nodes_ordered()
            .into_iter()
            .map(str::to_owned)
            .collect();
        let nodes: Vec<PyObject> = expected_nodes
            .iter()
            .map(|n| slf.py_node_key(py, n))
            .collect();
        let graph = Py::from(slf);
        Py::new(
            py,
            NodeIterator::with_graph_guard(
                py,
                nodes,
                NodeIteratorGuard::Graph(graph),
                expected_nodes.len(),
            ),
        )
    }

    /// Get adjacency dict for node (called by ``G[n]``).
    fn __getitem__(
        slf: PyRef<'_, Self>,
        py: Python<'_>,
        n: &Bound<'_, PyAny>,
    ) -> PyResult<Py<views::AtlasView>> {
        // br-r37-c1-njs5g: return a LAZY AtlasView instead of eagerly
        // materialising the whole `{neighbour: edge_attr_dict}` PyDict. nx's
        // `G[u]` is `self.adj[u]` (an AtlasView); making `G[u][v]` / `v in G[u]`
        // O(1) instead of O(degree), and the view is live (reflects later edge
        // additions) like nx. `mark_edges_dirty` is deferred to actual edge-dict
        // access (AtlasView::__getitem__), not paid on every bare `G[u]`.
        let canonical = node_key_to_string(py, n)?;
        if !slf.inner.has_node(&canonical) {
            return Err(missing_key_error(n));
        }
        let graph_py: Py<PyGraph> = Py::from(slf);
        Py::new(py, views::AtlasView::new(graph_py, canonical))
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

    /// br-r37-c1-s0d4x: wholesale same-type constructor absorb — nx's
    /// ``cls(G)`` structure is identical to ``G.copy()`` (probed: nodes,
    /// edges+data, adjacency/pred rows, graph attrs, shallow attr-dict
    /// copying, all four classes). The Python ctor wrapper routes the
    /// exact-same-type case here instead of the per-edge rebuild walk.
    fn _fnx_absorb_copy(&mut self, py: Python<'_>, other: PyRef<'_, Self>) -> PyResult<()> {
        *self = other.copy(py)?;
        Ok(())
    }

    /// Return a deep copy of the graph.
    fn copy(&self, py: Python<'_>) -> PyResult<Self> {
        // br-r37-c1-copyclone: bulk-clone the inner Rust graph instead of
        // rebuilding it edge-by-edge. The previous loop called
        // `add_edge_with_attrs` per edge (String hashing + adjacency IndexSet
        // insert + edge_index_endpoints push) PLUS a redundant
        // `py_dict_to_attr_map` re-parse of the just-copied PyDict — O(E) of
        // Rust reconstruction on every copy/subgraph/relabel/to_directed.
        // `Graph::clone` copies the IndexMap/IndexSet/Vec structures verbatim,
        // preserving node + edge insertion order exactly, so the only remaining
        // per-element work is the unavoidable deep-copy of the Python attr dicts.
        let mut new_graph = Self {
            inner: self.inner.clone_with_fresh_policy(), // br-r37-c1-7dpyg: skip ledger
            node_key_map: HashMap::with_capacity(self.node_key_map.len()),
            lazy_int_node_stop: 0,
            node_py_attrs: HashMap::with_capacity(self.node_py_attrs.len()),
            edge_py_attrs: HashMap::with_capacity(self.edge_py_attrs.len()),
            adj_py_keys: self.derive_copy_adj_py_keys(py, &self.inner), // br-r37-c1-z6uka
            dict_of_dicts_cache: None,
            graph_attrs: self.graph_attrs.bind(py).copy()?.unbind(),
            nodes_seq: 0,
            edges_seq: 0,
            // Edge-attr staleness IS tracked by `edges_dirty`; propagate it so a
            // dirty source yields a copy that reconciles `inner` from the copied
            // Python dicts on the next native read (same contract as the source).
            edges_dirty: AtomicBool::new(self.edges_dirty.load(Ordering::Relaxed)),
        };
        // br-r37-c1-0ek49: nx's G.copy() rebuild walk reorders undirected
        // adjacency rows (a pair enters both rows at its first u-major touch);
        // the verbatim clone above preserves the source's rows instead.
        new_graph.inner.reorder_rows_for_nx_copy_walk();
        // Node Python-side maps. Node-attr mutations are NOT tracked by
        // `edges_dirty`, so refresh the cloned inner's node attrs from the
        // authoritative Python dicts here (cheap: nodes << edges) to keep the
        // copy's native node-attr reads correct even for a "clean" source.
        for canonical in self.inner.nodes_ordered() {
            new_graph
                .node_key_map
                .insert(canonical.to_owned(), self.py_node_key(py, canonical));
            if let Some(attrs) = self.node_py_attrs.get(canonical) {
                let bound = attrs.bind(py);
                new_graph
                    .inner
                    .replace_node_attrs(canonical, py_dict_to_attr_map(bound)?);
                new_graph
                    .node_py_attrs
                    .insert(canonical.to_owned(), bound.copy()?.unbind());
            }
        }
        // Deep-copy the edge attr dicts. Key orientation is preserved verbatim;
        // edge lookups already probe both (u, v) and (v, u), and the copy's
        // `G.edges()` order comes from the cloned inner — so the HashMap walk
        // order here is irrelevant (unlike the old rebuild-from-edge_py_attrs).
        for (key, attrs) in &self.edge_py_attrs {
            new_graph
                .edge_py_attrs
                .insert(key.clone(), attrs.bind(py).copy()?.unbind());
        }
        Ok(new_graph)
    }

    /// br-r37-c1-copynative: stable alias exposing the native order-preserving
    /// `copy` (above) to the Python `_copy_preserving_insertion_order` wrapper,
    /// which shadows `copy` at the Python class level. Lets exact-type
    /// `Graph.copy()` use the bulk `inner.clone()` path (order + endpoint
    /// orientation + shallow attr-dict copy preserved) instead of the ~4x-slower
    /// rebuild via `self.edges(data=True)` + `add_edges_from`.
    fn _native_copy(&self, py: Python<'_>) -> PyResult<Self> {
        self.copy(py)
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
            inner: Graph::with_runtime_policy(self.inner.runtime_policy().clone()),
            node_key_map: HashMap::new(),
            lazy_int_node_stop: 0,
            node_py_attrs: HashMap::new(),
            edge_py_attrs: HashMap::new(),
            adj_py_keys: HashMap::new(), // br-r37-c1-z6uka
            dict_of_dicts_cache: None,
            graph_attrs: self.graph_attrs.bind(py).copy()?.unbind(),
            nodes_seq: 0,
            edges_seq: 0,
            edges_dirty: AtomicBool::new(false),
        };

        // Add kept nodes using the existing HashSet iteration behavior; only
        // node-key materialization changes for sparse range fast-path keys.
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
            new_graph
                .node_key_map
                .insert(canonical.clone(), self.py_node_key(py, canonical));
            if let Some(attrs) = self.node_py_attrs.get(canonical) {
                new_graph
                    .node_py_attrs
                    .insert(canonical.clone(), attrs.bind(py).copy()?.unbind());
            }
        }

        // Add edges where both endpoints are in the subgraph.
        for (u, v, attrs) in self.inner.edges_ordered_borrowed() {
            if keep.contains(u) && keep.contains(v) {
                let key = Self::edge_key(u, v);
                let py_attrs = self.edge_py_attrs.get(&key);
                let rust_attrs = py_attrs
                    .map(|attrs| py_dict_to_attr_map(attrs.bind(py)))
                    .transpose()?
                    .unwrap_or_else(|| attrs.clone());
                let _ = new_graph
                    .inner
                    .add_edge_with_attrs(u.to_owned(), v.to_owned(), rust_attrs);
                if let Some(attrs) = py_attrs {
                    new_graph
                        .edge_py_attrs
                        .insert(key, attrs.bind(py).copy()?.unbind());
                }
            }
        }

        if !self.adj_py_keys.is_empty() {
            // br-r37-c1-z6uka: carry adjacency-row overrides for cells that
            // survived the filter (nx subgraphs keep the original row objects).
            new_graph.adj_py_keys = self.derive_copy_adj_py_keys(py, &new_graph.inner);
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
            inner: Graph::with_runtime_policy(self.inner.runtime_policy().clone()),
            node_key_map: HashMap::new(),
            lazy_int_node_stop: 0,
            node_py_attrs: HashMap::new(),
            edge_py_attrs: HashMap::new(),
            adj_py_keys: HashMap::new(), // br-r37-c1-z6uka
            dict_of_dicts_cache: None,
            graph_attrs: self.graph_attrs.bind(py).copy()?.unbind(),
            nodes_seq: 0,
            edges_seq: 0,
            edges_dirty: AtomicBool::new(false),
        };

        // Collect nodes from kept edges
        let mut nodes_needed: std::collections::HashSet<String> = std::collections::HashSet::new();
        for (u, v) in &keep_edges {
            nodes_needed.insert(u.clone());
            nodes_needed.insert(v.clone());
        }

        // Add nodes using the existing HashSet iteration behavior; only
        // node-key materialization changes for sparse range fast-path keys.
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
            new_graph
                .node_key_map
                .insert(canonical.clone(), self.py_node_key(py, canonical));
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

        if !self.adj_py_keys.is_empty() {
            // br-r37-c1-z6uka: carry adjacency-row overrides for cells that
            // survived the filter (nx subgraphs keep the original row objects).
            new_graph.adj_py_keys = self.derive_copy_adj_py_keys(py, &new_graph.inner);
        }
        Ok(new_graph)
    }

    /// Return an undirected copy of the graph (no-op for Graph).
    fn to_undirected(&self, py: Python<'_>) -> PyResult<Self> {
        self.copy(py)
    }

    /// Return a directed copy of the graph.
    fn to_directed(&self, py: Python<'_>) -> PyResult<Py<crate::digraph::PyDiGraph>> {
        let mut dg = crate::digraph::PyDiGraph::new_empty_with_policy(
            py,
            self.inner.runtime_policy().clone(),
        )?;

        for canonical in self.inner.nodes_ordered() {
            let rust_attrs = self
                .node_py_attrs
                .get(canonical)
                .map(|attrs| py_dict_to_attr_map(attrs.bind(py)))
                .transpose()?
                .unwrap_or_default();
            dg.inner
                .add_node_with_attrs(canonical.to_owned(), rust_attrs);
            dg.node_key_map
                .insert(canonical.to_owned(), self.py_node_key(py, canonical));
            if let Some(attrs) = self.node_py_attrs.get(canonical) {
                dg.node_py_attrs
                    .insert(canonical.to_owned(), attrs.bind(py).copy()?.unbind());
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

    /// br-r37-c1-todirnative: native DEEP-copying Graph->DiGraph for the Python
    /// `_graph_to_directed_copy` wrapper (exact Graph type only). Builds the
    /// DiGraph in Rust in nx's adjacency-grouped edge order (`for source in
    /// nodes_ordered, for target in neighbors(source)` — each undirected edge
    /// br-r37-c1-l5ve7: fused native disjoint_union for the exact
    /// Graph x Graph case — nx's pipeline is convert_node_labels_to_
    /// integers(G) + convert(H, first_label=n1) + union_all, i.e. THREE
    /// full Python rebuilds. One native pass replicates the composite:
    /// nodes 0..n1-1 then n1.., int display objects, rows = the u-major
    /// edge-stream walk per graph (the pipeline's stable fixed point),
    /// graph attrs G-then-H update, node/edge attr dicts SHALLOW-copied
    /// (fresh dicts, shared values — nx add_*_from datadict.update
    /// semantics). Construction-tax recipe: fresh ledger + bulk
    /// unrecorded inserts + lazy mirrors.
    fn _native_disjoint_union(
        &self,
        py: Python<'_>,
        other: PyRef<'_, Self>,
    ) -> PyResult<Py<Self>> {
        let mut g =
            Self::new_empty_with_policy(py, fnx_runtime::RuntimePolicy::new(self.inner.mode()))?;
        let merged_graph_attrs = PyDict::new(py);
        merged_graph_attrs.update(self.graph_attrs.bind(py).as_mapping())?;
        merged_graph_attrs.update(other.graph_attrs.bind(py).as_mapping())?;
        g.graph_attrs = merged_graph_attrs.unbind();
        let n1 = self.inner.node_count();
        for (part, offset) in [(&*self, 0usize), (&*other, n1)] {
            let nodes = part.inner.nodes_ordered();
            let index_of: std::collections::HashMap<&str, usize> = nodes
                .iter()
                .enumerate()
                .map(|(i, n)| (*n, i + offset))
                .collect();
            let mut node_batch: Vec<(String, fnx_classes::AttrMap)> =
                Vec::with_capacity(nodes.len());
            for (i, node) in nodes.iter().enumerate() {
                let canonical = (i + offset).to_string();
                if let Some(attrs) = part.node_py_attrs.get(*node) {
                    // shallow copy: fresh dict, shared values (nx semantics)
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
            g.inner.extend_nodes_with_attrs_unrecorded(node_batch);
            let mut edge_batch: Vec<(String, String, fnx_classes::AttrMap)> = Vec::new();
            let mut seen: std::collections::HashSet<(usize, usize)> = std::collections::HashSet::new();
            for u in &nodes {
                for v in part.inner.neighbors(u).unwrap_or_default() {
                    let ui = index_of[*u];
                    let vi = index_of[v];
                    let pair = (ui.min(vi), ui.max(vi));
                    if !seen.insert(pair) {
                        continue; // u-major edge stream emits each undirected edge once
                    }
                    let uc = ui.to_string();
                    let vc = vi.to_string();
                    if let Some(attrs) = part
                        .edge_py_attrs
                        .get(&Self::edge_key(u, v))
                        .or_else(|| part.edge_py_attrs.get(&Self::edge_key(v, u)))
                    {
                        g.edge_py_attrs.insert(
                            Self::edge_key(&uc, &vc),
                            attrs.bind(py).copy()?.unbind(),
                        );
                    }
                    edge_batch.push((
                        uc,
                        vc,
                        part.inner.edge_attrs(u, v).cloned().unwrap_or_default(),
                    ));
                }
            }
            g.inner.extend_edges_with_attrs_unrecorded(edge_batch);
        }
        Py::new(py, g)
    }

    /// emits both directed arcs in nx's `G.adj` iteration order), deep-copying
    /// attrs via `copy.deepcopy` to honor nx's to_directed deep-copy contract.
    /// Attr-less nodes/edges get a fresh empty dict (already independent — skips
    /// the per-element deepcopy). Replaces the Python per-arc adjacency
    /// materialization + add_edge dispatch (~4.2x slower than nx). Unlike the
    /// shallow, edge-grouped `to_directed` above, this matches nx's deep-copy
    /// semantics AND public edge order.
    fn _native_to_directed_deepcopy(
        &self,
        py: Python<'_>,
    ) -> PyResult<Py<crate::digraph::PyDiGraph>> {
        let deepcopy = py.import("copy")?.getattr("deepcopy")?;
        // br-r37-c1-l5ve7: fresh ledger (the policy clone deep-copied the
        // source's unbounded decision ledger — the 7dpyg result-ctor class)
        // + BULK unrecorded inserts (the per-edge recorded add_* pushed a
        // ledger record per node/edge — the dominant residual after the
        // empty-dict fast path).
        let mut dg = crate::digraph::PyDiGraph::new_empty_with_policy(
            py,
            fnx_runtime::RuntimePolicy::new(self.inner.mode()),
        )?;
        dg.graph_attrs = deepcopy_py_dict(py, &deepcopy, &self.graph_attrs)?;
        let mut node_batch: Vec<(String, fnx_classes::AttrMap)> =
            Vec::with_capacity(self.inner.node_count());
        for node in self.inner.nodes_ordered() {
            // Attr-less nodes stay lazy (no PyDict / py_dict_to_attr_map) — same
            // contract as the native copy kernel; the dict materializes on demand.
            let rust_attrs = if let Some(attrs) = self.node_py_attrs.get(node) {
                let py_attrs = deepcopy_py_dict(py, &deepcopy, attrs)?;
                let rust_attrs = py_dict_to_attr_map(py_attrs.bind(py))?;
                dg.node_py_attrs.insert(node.to_owned(), py_attrs);
                rust_attrs
            } else {
                Default::default()
            };
            dg.node_key_map
                .insert(node.to_owned(), self.py_node_key(py, node));
            node_batch.push((node.to_owned(), rust_attrs));
        }
        dg.inner.extend_nodes_with_attrs_unrecorded(node_batch);
        let mut edge_batch: Vec<(String, String, fnx_classes::AttrMap)> =
            Vec::with_capacity(self.inner.edge_count() * 2);
        for source in self.inner.nodes_ordered() {
            for target in self.inner.neighbors(source).unwrap_or_default() {
                let entry = self
                    .edge_py_attrs
                    .get(&PyGraph::edge_key(source, target))
                    .or_else(|| self.edge_py_attrs.get(&PyGraph::edge_key(target, source)));
                let rust_attrs = match entry {
                    Some(attrs) => {
                        let py_attrs = deepcopy_py_dict(py, &deepcopy, attrs)?;
                        let rust_attrs = py_dict_to_attr_map(py_attrs.bind(py))?;
                        dg.edge_py_attrs
                            .insert((source.to_owned(), target.to_owned()), py_attrs);
                        rust_attrs
                    }
                    // Attr-less arc stays lazy (no PyDict alloc).
                    None => Default::default(),
                };
                edge_batch.push((source.to_owned(), target.to_owned(), rust_attrs));
            }
        }
        dg.inner.extend_edges_with_attrs_unrecorded(edge_batch);
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
        &mut self,
        py: Python<'_>,
        u: &Bound<'_, PyAny>,
        v: &Bound<'_, PyAny>,
        default: Option<PyObject>,
    ) -> PyResult<PyObject> {
        let u_c = node_key_to_string(py, u)?;
        let v_c = node_key_to_string(py, v)?;
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
    ///
    /// `to_scipy_sparse_array(..., weight=...)` was paying an O(N) node-attr
    /// rebuild before the edge dirty check on every native sparse export. This
    /// preserves the same persistent dirty-edge semantics while leaving full
    /// node+edge sync available for callers that need node attributes.
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

    /// br-r37-c1-yo1nt: native weighted degree, returning the full
    /// ``(node, total)`` sequence in node order. The Python
    /// `_WeightAwareDegreeView` weighted path builds ``dict(G.adj[node])``
    /// per node (AtlasView walk) — ~43x slower than nx. nx's `DegreeView`
    /// computes ``sum(dd.get(weight, 1) for dd in nbrs.values())`` plus, for a
    /// self-loop, ``+ nbrs[n].get(weight, 1)``. CPython ``sum`` is
    /// Neumaier-compensated, so we build the value list in adjacency order and
    /// call the SAME builtin ``sum`` for bit-identical numeric parity rather
    /// than folding with ``+`` in Rust.
    fn _native_weighted_degree(
        &self,
        py: Python<'_>,
        weight: &str,
    ) -> PyResult<Vec<(PyObject, PyObject)>> {
        let one = 1i64.into_pyobject(py)?.into_any();
        let sum_fn = py.import("builtins")?.getattr("sum")?;
        let mut out: Vec<(PyObject, PyObject)> = Vec::with_capacity(self.inner.node_count());
        for node in self.inner.nodes_ordered() {
            let values = pyo3::types::PyList::empty(py);
            let mut selfloop = false;
            for neighbor in self.inner.neighbors(node).unwrap_or_default() {
                if neighbor == node {
                    selfloop = true;
                }
                let ek = Self::edge_key(node, neighbor);
                let value = match self.edge_py_attrs.get(&ek) {
                    Some(d) => d
                        .bind(py)
                        .get_item(weight)
                        .ok()
                        .flatten()
                        .unwrap_or_else(|| one.clone()),
                    None => one.clone(),
                };
                values.append(value)?;
            }
            let mut deg = sum_fn.call1((values,))?;
            if selfloop {
                let ek = Self::edge_key(node, node);
                let value = match self.edge_py_attrs.get(&ek) {
                    Some(d) => d
                        .bind(py)
                        .get_item(weight)
                        .ok()
                        .flatten()
                        .unwrap_or_else(|| one.clone()),
                    None => one.clone(),
                };
                deg = deg.add(value)?;
            }
            out.push((self.py_node_key(py, node), deg.unbind()));
        }
        Ok(out)
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
                (Some(a), None) => {
                    if !a.bind(py).is_empty() {
                        return Ok(false);
                    }
                }
                (None, Some(b)) => {
                    if !b.bind(py).is_empty() {
                        return Ok(false);
                    }
                }
                (None, None) => {}
            }
        }

        // Compare edge sets and attributes. `edge_py_attrs` can be sparse for
        // generator-built graphs; a missing entry is equivalent to an empty
        // live dict until first materialization.
        if self.inner.edge_count() != other.inner.edge_count() {
            return Ok(false);
        }
        for (u, v, _attrs) in self.inner.edges_ordered_borrowed() {
            if !other.inner.has_edge(u, v) {
                return Ok(false);
            }
            let key = Self::edge_key(u, v);
            match (self.edge_py_attrs.get(&key), other.edge_py_attrs.get(&key)) {
                (Some(attrs), Some(other_attrs)) => {
                    if !attrs.bind(py).eq(other_attrs.bind(py))? {
                        return Ok(false);
                    }
                }
                (Some(attrs), None) => {
                    if !attrs.bind(py).is_empty() {
                        return Ok(false);
                    }
                }
                (None, Some(other_attrs)) => {
                    if !other_attrs.bind(py).is_empty() {
                        return Ok(false);
                    }
                }
                (None, None) => {}
            }
        }

        // Compare graph attributes
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
            lazy_int_node_stop: self.lazy_int_node_stop,
            adj_py_keys: self.clone_adj_py_keys(py), // br-r37-c1-z6uka
            dict_of_dicts_cache: None,
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
        })
    }

    /// Support ``copy.deepcopy(G)`` — returns a deep copy.
    #[pyo3(signature = (_memo=None))]
    fn __deepcopy__(&self, py: Python<'_>, _memo: Option<&Bound<'_, PyAny>>) -> PyResult<Self> {
        self.copy(py)
    }

    // ---- Serialization (pickle) ----

    fn __getstate__(&self, py: Python<'_>) -> PyResult<PyObject> {
        let state = PyDict::new(py);
        state.set_item("mode", compatibility_mode_name(self.inner.mode()))?;
        state.set_item(
            "runtime_policy",
            runtime_policy_json(self.inner.runtime_policy())?,
        )?;
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

        // Store edges as list of (u, v, attrs) tuples. Generated graphs keep
        // edge_py_attrs sparse until the first live attr-dict handout, so the
        // edge structure must come from inner rather than edge_py_attrs.
        let edges_list: Vec<(PyObject, PyObject, Py<PyDict>)> = self
            .inner
            .edges_ordered_borrowed()
            .into_iter()
            .map(|(u, v, _attrs)| {
                let py_u = self.py_node_key(py, u);
                let py_v = self.py_node_key(py, v);
                let key = Self::edge_key(u, v);
                let attrs = self
                    .edge_py_attrs
                    .get(&key)
                    .map_or_else(|| PyDict::new(py).unbind(), |d| d.clone_ref(py));
                (py_u, py_v, attrs)
            })
            .collect();
        state.set_item("edges", edges_list)?;
        state.set_item("graph", self.graph_attrs.bind(py))?;
        // br-r37-c1-u3qyn: the edges list above is the u-major adjacency
        // WALK, and rebuilding from it scrambles adjacency row order (nx
        // pickles the dict structure verbatim). Store the rows explicitly
        // (canonical keys) plus the sparse display-object overrides so
        // __setstate__ can restore the structure byte-identically. Both
        // fields are optional — old pickles keep the legacy rebuild.
        let adj_rows: Vec<(String, Vec<String>)> = self
            .inner
            .nodes_ordered()
            .into_iter()
            .map(|n| {
                (
                    n.to_owned(),
                    self.inner
                        .neighbors(n)
                        .unwrap_or_default()
                        .into_iter()
                        .map(str::to_owned)
                        .collect(),
                )
            })
            .collect();
        state.set_item("adj_rows", adj_rows)?;
        if !self.adj_py_keys.is_empty() {
            let overrides: Vec<(String, String, PyObject)> = self
                .adj_py_keys
                .iter()
                .map(|((a, b), o)| (a.clone(), b.clone(), o.clone_ref(py)))
                .collect();
            state.set_item("adj_py_keys", overrides)?;
        }
        Ok(state.into_any().unbind())
    }

    fn __setstate__(&mut self, py: Python<'_>, state: &Bound<'_, PyDict>) -> PyResult<()> {
        let mode = compatibility_mode_from_py(state.get_item("mode")?.as_ref())?;
        self.inner = Graph::with_runtime_policy(runtime_policy_from_state(state, mode)?);
        self.node_key_map.clear();
        self.lazy_int_node_stop = 0;
        self.node_py_attrs.clear();
        self.edge_py_attrs.clear();
        self.adj_py_keys.clear(); // br-r37-c1-u3qyn
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

        // br-r37-c1-u3qyn: restore the source's exact adjacency row order
        // and display-object overrides when the state carries them.
        if let Some(rows) = state.get_item("adj_rows")? {
            let orders: Vec<(String, Vec<String>)> = rows.extract()?;
            self.inner.apply_row_orders(&orders);
        }
        if let Some(overrides) = state.get_item("adj_py_keys")? {
            let entries: Vec<(String, String, PyObject)> = overrides.extract()?;
            for (a, b, o) in entries {
                self.adj_py_keys.insert((a, b), o);
            }
        }

        Ok(())
    }
}

pub(crate) fn unwrap_infallible<T>(result: Result<T, Infallible>) -> T {
    result.unwrap_or_else(|never| match never {})
}

#[cfg(test)]
mod tests {
    use super::*;
    use fnx_runtime::RuntimePolicy;

    fn ensure_python() {
        Python::initialize();
    }

    fn seeded_graph_policy() -> RuntimePolicy {
        let mut graph = Graph::new(CompatibilityMode::Hardened);
        graph.add_node("seed".to_owned());
        graph.runtime_policy().clone()
    }

    fn seeded_multigraph_policy() -> RuntimePolicy {
        let mut graph = MultiGraph::new(CompatibilityMode::Hardened);
        graph.add_node("seed".to_owned());
        graph.runtime_policy().clone()
    }

    #[test]
    fn graph_new_empty_with_policy_preserves_runtime_policy_state() {
        ensure_python();
        Python::attach(|py| {
            let expected_policy = seeded_graph_policy();
            let graph = PyGraph::new_empty_with_policy(py, expected_policy.clone())
                .expect("graph should initialize");
            assert_eq!(graph.inner.runtime_policy(), &expected_policy);
        });
    }

    #[test]
    fn graph_clear_preserves_runtime_policy_state() {
        ensure_python();
        Python::attach(|py| {
            let expected_policy = seeded_graph_policy();
            let mut graph = PyGraph::new_empty_with_policy(py, expected_policy.clone())
                .expect("graph should initialize");

            graph.clear(py).expect("clear should succeed");

            assert_eq!(graph.inner.runtime_policy(), &expected_policy);
        });
    }

    #[test]
    fn multigraph_clear_edges_preserves_runtime_policy_state() {
        ensure_python();
        Python::attach(|py| {
            let expected_policy = seeded_multigraph_policy();
            let mut graph = PyMultiGraph::new_empty_with_policy(py, expected_policy.clone())
                .expect("multigraph should initialize");

            graph.clear_edges();

            assert_eq!(graph.inner.runtime_policy(), &expected_policy);
        });
    }

    #[test]
    fn graph_pickle_state_roundtrips_runtime_policy_state() {
        ensure_python();
        Python::attach(|py| {
            let expected_policy = seeded_graph_policy();
            let graph = PyGraph::new_empty_with_policy(py, expected_policy.clone())
                .expect("graph should initialize");

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

            let mut restored = PyGraph::new_empty(py).expect("graph should initialize");
            restored
                .__setstate__(py, &state)
                .expect("state import should succeed");

            assert_eq!(restored.inner.runtime_policy(), &expected_policy);
        });
    }

    #[test]
    fn graph_constructor_copy_preserves_runtime_policy_state() {
        ensure_python();
        Python::attach(|py| {
            let expected_policy = seeded_graph_policy();
            let source = Py::new(
                py,
                PyGraph::new_empty_with_policy(py, expected_policy.clone())
                    .expect("graph should initialize"),
            )
            .expect("py graph should initialize");

            let copied = PyGraph::new(py, Some(source.bind(py).as_any()), None)
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
    fn multigraph_to_directed_preserves_runtime_policy_state() {
        ensure_python();
        Python::attach(|py| {
            let expected_policy = seeded_multigraph_policy();
            let graph = PyMultiGraph::new_empty_with_policy(py, expected_policy.clone())
                .expect("multigraph should initialize");

            let directed = graph.to_directed(py).expect("conversion should succeed");

            assert_eq!(directed.inner.runtime_policy(), &expected_policy);
        });
    }

    #[test]
    fn multigraph_pickle_state_roundtrips_runtime_policy_state() {
        ensure_python();
        Python::attach(|py| {
            let expected_policy = seeded_multigraph_policy();
            let graph = PyMultiGraph::new_empty_with_policy(py, expected_policy.clone())
                .expect("multigraph should initialize");

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
                PyMultiGraph::new(py, None, None).expect("multigraph should initialize");
            restored
                .__setstate__(py, &state)
                .expect("state import should succeed");

            assert_eq!(restored.inner.runtime_policy(), &expected_policy);
        });
    }
}

// ---------------------------------------------------------------------------
// Node iterator — returned by ``for n in G``.
// ---------------------------------------------------------------------------

#[pyclass]
pub(crate) struct NodeIterator {
    inner: std::vec::IntoIter<PyObject>,
    /// (guard, expected_node_count, expected_nodes_seq)
    /// — br-r37-c1-39d82 added the seq snapshot so __next__ can
    /// detect node-set mutations in O(1) instead of O(N) clone +
    /// compare on every call.  br-r37-c1-iter-strvec: replaced the
    /// owned Vec<String> of expected node names with a single
    /// expected_count usize — __next__ only ever read
    /// ``expected_nodes.len()``, so the O(N) String allocations at
    /// construction were pure waste.  Drops list(G) on n=200 from
    /// ~27 µs to ~5 µs (cascades into every algorithm that does
    /// ``list(G.nodes())``).
    guard: Option<(NodeIteratorGuard, usize, u64)>,
}

pub(crate) enum NodeIteratorGuard {
    Graph(Py<PyGraph>),
    MultiGraph(Py<PyMultiGraph>),
    DiGraph(Py<digraph::PyDiGraph>),
    MultiDiGraph(Py<digraph::PyMultiDiGraph>),
}

impl NodeIteratorGuard {
    #[allow(dead_code)]
    fn current_nodes(&self, py: Python<'_>) -> Vec<String> {
        match self {
            Self::Graph(graph) => graph
                .borrow(py)
                .inner
                .nodes_ordered()
                .into_iter()
                .map(str::to_owned)
                .collect(),
            Self::MultiGraph(graph) => graph
                .borrow(py)
                .inner
                .nodes_ordered()
                .into_iter()
                .map(str::to_owned)
                .collect(),
            Self::DiGraph(graph) => graph
                .borrow(py)
                .inner
                .nodes_ordered()
                .into_iter()
                .map(str::to_owned)
                .collect(),
            Self::MultiDiGraph(graph) => graph
                .borrow(py)
                .inner
                .nodes_ordered()
                .into_iter()
                .map(str::to_owned)
                .collect(),
        }
    }

    /// O(1) node-count for the guard's underlying graph — used by the
    /// per-next size-change check (br-r37-c1-nodeitergsfast).  Avoids
    /// the O(N) ``current_nodes()`` clone on every ``__next__`` call.
    fn node_count(&self, py: Python<'_>) -> usize {
        match self {
            Self::Graph(graph) => graph.borrow(py).inner.node_count(),
            Self::MultiGraph(graph) => graph.borrow(py).inner.node_count(),
            Self::DiGraph(graph) => graph.borrow(py).inner.node_count(),
            Self::MultiDiGraph(graph) => graph.borrow(py).inner.node_count(),
        }
    }

    /// br-r37-c1-39d82: O(1) monotonic counter bumped on every
    /// add_node/remove_node.  Iterators capture this at construction
    /// and compare in __next__ to detect ANY node-set mutation
    /// (including count-preserving remove+add) without re-cloning
    /// ``nodes_ordered()``.
    fn nodes_seq(&self, py: Python<'_>) -> u64 {
        match self {
            Self::Graph(graph) => graph.borrow(py).nodes_seq,
            Self::MultiGraph(graph) => graph.borrow(py).nodes_seq,
            Self::DiGraph(graph) => graph.borrow(py).nodes_seq,
            Self::MultiDiGraph(graph) => graph.borrow(py).nodes_seq,
        }
    }
}

impl NodeIterator {
    pub(crate) fn unguarded(items: Vec<PyObject>) -> Self {
        Self {
            inner: items.into_iter(),
            guard: None,
        }
    }

    pub(crate) fn with_graph_guard(
        py: Python<'_>,
        items: Vec<PyObject>,
        graph: NodeIteratorGuard,
        expected_count: usize,
    ) -> Self {
        // br-r37-c1-39d82: capture nodes_seq at construction so
        // __next__ can detect mutations in O(1) instead of cloning
        // ``nodes_ordered()`` on every call.
        // br-r37-c1-iter-strvec: only the count is needed for the
        // dict-changed-size disambiguation message; the actual node
        // names were never read by __next__.
        let expected_seq = graph.nodes_seq(py);
        Self {
            inner: items.into_iter(),
            guard: Some((graph, expected_count, expected_seq)),
        }
    }
}

#[pymethods]
impl NodeIterator {
    fn __iter__(slf: PyRef<'_, Self>) -> PyRef<'_, Self> {
        slf
    }

    fn __next__(mut slf: PyRefMut<'_, Self>) -> PyResult<Option<PyObject>> {
        let Some(item) = slf.inner.next() else {
            return Ok(None);
        };
        if let Some((graph, expected_count, expected_seq)) = &slf.guard {
            // br-r37-c1-39d82: O(1) mutation-counter check.  Any
            // add_node / remove_node / add_nodes_from /
            // remove_nodes_from bumps nodes_seq; a mismatch here means
            // the node set changed during iteration.  Disambiguate
            // size-change vs key-permutation via the count check so
            // the error wording matches Python's dict contract.
            let current_seq = graph.nodes_seq(slf.py());
            if current_seq != *expected_seq {
                let current_count = graph.node_count(slf.py());
                if current_count != *expected_count {
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
    m.add_class::<views::AtlasView>()?;

    // MultiGraph view classes
    m.add_class::<MultiGraphNodeView>()?;
    m.add_class::<MultiGraphEdgeView>()?;
    m.add_class::<MultiGraphDegreeView>()?;
    m.add_class::<MultiAtlasView>()?;
    m.add_class::<MultiKeyDictView>()?;

    // Algorithm functions
    algorithms::register(m)?;

    // Generator functions
    generators::register(m)?;

    // Read/write functions
    readwrite::register(m)?;

    // CGSE submodule
    cgse::register_module(m)?;

    // Exception hierarchy
    m.add("NetworkXException", m.py().get_type::<NetworkXException>())?;
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
    m.add("NotAPartition", m.py().get_type::<NotAPartition>())?;
    m.add("NotATree", m.py().get_type::<NotATree>())?;
    m.add("NodeNotFound", m.py().get_type::<NodeNotFound>())?;
    m.add("HasACycle", m.py().get_type::<HasACycle>())?;
    m.add(
        "PowerIterationFailedConvergence",
        m.py().get_type::<PowerIterationFailedConvergence>(),
    )?;

    Ok(())
}
