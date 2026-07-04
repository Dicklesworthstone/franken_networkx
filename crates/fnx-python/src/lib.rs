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
mod network_simplex;
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

/// br-r37-c1-d58s8 ctor lever: one native pass over a ctor edge-list
/// candidate replacing the Python per-item validation walk (the cProfile
/// split showed 46% of Graph(edges) inside the wrapper loop — 10
/// Python ops per edge). Returns (valid, needs_tuple_conversion) with
/// EXACTLY the wrapper's semantics: str/bytes items invalid; items
/// without len() invalid; len outside {2,3} (+4 for multigraphs)
/// invalid; multigraph 4-tuples must carry a dict 4th element;
/// non-tuple items flag conversion.
#[pyfunction]
pub fn validate_ctor_edge_list(
    _py: Python<'_>,
    data: &Bound<'_, PyAny>,
    is_multi: bool,
) -> PyResult<(bool, bool, bool)> {
    let mut needs_tuple_conversion = false;
    let mut endpoints_hashable = true;
    for item in data.try_iter()? {
        let item = item?;
        // br-r37-c1-ewtd1: str/bytes ITEMS are valid 2/3-element edge
        // specs in nx (it iterates them: 'ab' -> ('a','b'),
        // b'xy' -> (120, 121)). They have len()/get_item(), so they flow
        // through the same length+3rd-element rules below and just need
        // tuple() conversion in the absorb.
        let Ok(item_len) = item.len() else {
            return Ok((false, false, true));
        };
        let valid_len = if is_multi {
            (2..=4).contains(&item_len)
        } else {
            (2..=3).contains(&item_len)
        };
        if !valid_len {
            return Ok((false, false, true));
        }
        if is_multi && item_len == 4 && !item.get_item(3)?.is_instance_of::<PyDict>() {
            return Ok((false, false, true));
        }
        // br-r37-c1-ft8c0: a NON-multi 3-tuple's third element is the
        // edge data dict (nx does datadict.update(e[2])); a non-dict
        // third makes the whole input invalid, matching nx's
        // "Input is not a valid edge list". (For multigraphs the third
        // element is the edge KEY — any hashable is fine.)
        if !is_multi && item_len == 3 && !item.get_item(2)?.is_instance_of::<PyDict>() {
            return Ok((false, false, true));
        }
        if !item.is_instance_of::<pyo3::types::PyTuple>() {
            needs_tuple_conversion = true;
        }
        // Fold the post-absorb endpoint-hashability walk (a full Python
        // NodeIterator pass) into this same native pass. The old walk
        // also caught non-multi 3-tuples whose NON-DICT third element
        // the Rust __new__ mis-absorbs as a node (e.g. (1, 2, [3])) —
        // mirror that by hashing such third elements too.
        if endpoints_hashable
            && (item.get_item(0)?.hash().is_err() || item.get_item(1)?.hash().is_err())
        {
            endpoints_hashable = false;
        }
        // (non-multi non-dict-third already rejected above)
    }
    Ok((true, needs_tuple_conversion, endpoints_hashable))
}

fn geometric_positions_from_py(positions: &Bound<'_, PyAny>) -> PyResult<Option<Vec<Vec<f64>>>> {
    let mut points = Vec::new();
    let mut dim: Option<usize> = None;
    for point in positions.try_iter()? {
        let point = point?;
        let mut coords = Vec::new();
        for coord in point.try_iter()? {
            let value = coord?.extract::<f64>()?;
            if !value.is_finite() {
                return Ok(None);
            }
            coords.push(value);
        }
        if coords.is_empty() {
            return Ok(None);
        }
        match dim {
            Some(expected) if expected != coords.len() => return Ok(None),
            None => dim = Some(coords.len()),
            _ => {}
        }
        points.push(coords);
    }
    Ok(Some(points))
}

fn geometric_within_radius(left: &[f64], right: &[f64], radius: f64, p: f64) -> bool {
    if p == f64::INFINITY {
        let mut max_delta = 0.0;
        for (a, b) in left.iter().zip(right) {
            let delta = (a - b).abs();
            if delta > max_delta {
                max_delta = delta;
            }
        }
        max_delta <= radius
    } else if p == 2.0 {
        let mut sum = 0.0;
        for (a, b) in left.iter().zip(right) {
            let delta = a - b;
            sum += delta * delta;
        }
        sum <= radius * radius
    } else {
        let mut sum = 0.0;
        for (a, b) in left.iter().zip(right) {
            sum += (a - b).abs().powf(p);
        }
        sum <= radius.powf(p)
    }
}

fn enumerate_geometric_cells(
    ranges: &[(i64, i64)],
    depth: usize,
    current: &mut Vec<i64>,
    buckets: &HashMap<Vec<i64>, Vec<usize>>,
    out: &mut Vec<usize>,
) {
    if depth == ranges.len() {
        if let Some(indices) = buckets.get(current) {
            out.extend(indices.iter().copied());
        }
        return;
    }
    let (start, end) = ranges[depth];
    for cell in start..=end {
        current.push(cell);
        enumerate_geometric_cells(ranges, depth + 1, current, buckets, out);
        current.pop();
    }
}

/// br-r37-c1-nt3co: deterministic safe-Rust radius-query candidate generator.
///
/// The Python geometric generators need the exact sorted ``i < j`` pair order
/// because ``soft_random_geometric_graph`` consumes RNG once per in-radius
/// candidate. A uniform grid shrinks the candidate set, exact-reranks every
/// candidate with the same p-norm predicate, then sorts the final pairs to keep
/// the NetworkX-visible order unchanged.
#[pyfunction]
pub fn geometric_pairs_grid(
    positions: &Bound<'_, PyAny>,
    radius: f64,
    p: f64,
) -> PyResult<Option<Vec<(usize, usize)>>> {
    let Some(points) = geometric_positions_from_py(positions)? else {
        return Ok(None);
    };
    if points.len() < 2 {
        return Ok(Some(Vec::new()));
    }
    if !radius.is_finite() || radius <= 0.0 || !(p == f64::INFINITY || p >= 1.0) {
        let mut pairs = Vec::new();
        for i in 0..points.len() {
            for j in (i + 1)..points.len() {
                if geometric_within_radius(&points[i], &points[j], radius, p) {
                    pairs.push((i, j));
                }
            }
        }
        return Ok(Some(pairs));
    }

    let dim = points[0].len();
    let mut buckets: HashMap<Vec<i64>, Vec<usize>> = HashMap::with_capacity(points.len());
    for (idx, point) in points.iter().enumerate() {
        let key: Vec<i64> = point
            .iter()
            .map(|coord| (coord / radius).floor() as i64)
            .collect();
        buckets.entry(key).or_default().push(idx);
    }

    let mut pairs = Vec::new();
    let mut candidate_indices = Vec::new();
    let mut current_cell = Vec::with_capacity(dim);
    for (i, point) in points.iter().enumerate() {
        let ranges: Vec<(i64, i64)> = point
            .iter()
            .map(|coord| {
                (
                    ((coord - radius) / radius).floor() as i64,
                    ((coord + radius) / radius).floor() as i64,
                )
            })
            .collect();
        candidate_indices.clear();
        enumerate_geometric_cells(
            &ranges,
            0,
            &mut current_cell,
            &buckets,
            &mut candidate_indices,
        );
        for &j in &candidate_indices {
            if j > i && geometric_within_radius(point, &points[j], radius, p) {
                pairs.push((i, j));
            }
        }
    }
    pairs.sort_unstable();
    Ok(Some(pairs))
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

fn single_weight_float_attr_map_with_mirror(
    py: Python<'_>,
    attrs: &Bound<'_, PyDict>,
) -> PyResult<Option<(AttrMap, Py<PyDict>)>> {
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
    let mirror = PyDict::new(py);
    mirror.set_item(&key, &value)?;
    Ok(Some((rust_attrs, mirror.unbind())))
}

pub(crate) fn attr_map_to_pydict(py: Python<'_>, attrs: &AttrMap) -> PyResult<Py<PyDict>> {
    let dict = PyDict::new(py);
    for (key, value) in attrs {
        dict.set_item(key, cgse_value_to_py(py, value)?)?;
    }
    Ok(dict.unbind())
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
pub(crate) fn py_value_to_cgse(v: &Bound<'_, PyAny>) -> PyResult<CgseValue> {
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

/// br-r37-c1-nodebatchlossless (cc): the attributed node-batch fast path rebuilds the
/// node-attr mirror LAZILY from the CgseValue store on first read
/// (br-r37-c1-lazynodeattr), so a batch is only correct when every attr value round-trips
/// through the store. Scalars (bool / exact-i64 int / float / str) do; tuples, lists,
/// None, nested dicts, oversized ints, and custom objects do NOT — `py_value_to_cgse`
/// stringifies (or lossily floats) them, corrupting the value (e.g. a `pos` tuple ->
/// '(x, y)' string, as in waxman_graph). Returning false routes the batch to the
/// per-node `add_node` path, which keeps the real Python object in the mirror.
pub(crate) fn attr_dict_is_batch_lossless(d: &Bound<'_, PyDict>) -> bool {
    d.iter().all(|(_, v)| {
        v.is_exact_instance_of::<PyBool>()
            || v.is_exact_instance_of::<PyFloat>()
            || v.is_exact_instance_of::<PyString>()
            || (v.is_exact_instance_of::<PyInt>() && v.extract::<i64>().is_ok())
    })
}

/// br-r37-c1-edgebatchlossless (cc): true iff every 3-tuple edge's attr dict in the
/// ebunch is losslessly store-representable (see attr_dict_is_batch_lossless). The
/// attributed edge-batch dispatchers and their int/general sub-collectors rebuild edge
/// mirrors LAZILY from the CgseValue store, so a non-scalar edge attr (tuple/list/None/
/// dict/oversized int/custom) would be corrupted to its str()/lossy-float. `false`
/// routes the whole batch to the per-edge add_edge path (keeps the Python object).
///
/// CRITICAL: the batch sub-collectors only consume a list/tuple ebunch (they downcast).
/// A one-shot generator must NOT be iterated here — doing so would EXHAUST it before the
/// per-edge fallback runs (dropping every edge). So return `true` (no bail, no scan) for
/// any non-list/tuple ebunch; it never reaches a stringifying sub-collector anyway.
pub(crate) fn ebunch_batch_lossless(ebunch: &Bound<'_, PyAny>) -> PyResult<bool> {
    if ebunch.downcast::<PyList>().is_err() && ebunch.downcast::<PyTuple>().is_err() {
        return Ok(true);
    }
    for item in ebunch.try_iter()? {
        let item = item?;
        if let Ok(tuple) = item.downcast::<PyTuple>()
            && tuple.len() == 3
            && let Ok(d) = tuple.get_item(2)?.downcast::<PyDict>()
            && !attr_dict_is_batch_lossless(d)
        {
            return Ok(false);
        }
    }
    Ok(true)
}

pub(crate) fn collect_index_weight_attr_edges(
    rows: &Bound<'_, PyAny>,
    cols: &Bound<'_, PyAny>,
    values: &Bound<'_, PyAny>,
    node_count: usize,
    edge_attr: &str,
) -> PyResult<Vec<(usize, usize, AttrMap)>> {
    let mut row_iter = PyIterator::from_object(rows)?;
    let mut col_iter = PyIterator::from_object(cols)?;
    let mut value_iter = PyIterator::from_object(values)?;
    let mut edges = Vec::new();

    loop {
        let row = row_iter.next();
        let col = col_iter.next();
        let value = value_iter.next();
        match (row, col, value) {
            (None, None, None) => break,
            (Some(Ok(row)), Some(Ok(col)), Some(Ok(value))) => {
                let row = row.extract::<usize>()?;
                let col = col.extract::<usize>()?;
                if row >= node_count || col >= node_count {
                    return Err(PyValueError::new_err(
                        "matrix coordinate is outside graph node range",
                    ));
                }
                let mut attrs = AttrMap::new();
                attrs.insert(edge_attr.to_owned(), py_value_to_cgse(&value)?);
                edges.push((row, col, attrs));
            }
            (Some(Err(err)), _, _) | (_, Some(Err(err)), _) | (_, _, Some(Err(err))) => {
                return Err(err);
            }
            _ => {
                return Err(PyValueError::new_err(
                    "matrix coordinate and value arrays must have equal length",
                ));
            }
        }
    }

    Ok(edges)
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
    // perf (br-r37-c1-bjomp, cc): when EVERY value is an immutable scalar
    // (None/bool/int/float/str), `copy.deepcopy` is observably identical to a
    // shallow dict copy — immutables are never actually copied (deepcopy returns
    // the same object for them, and `_deepcopy_atomic` is a no-op), and there are
    // no nested containers for the memo to matter. A shallow `dict.copy()` then
    // produces a dict that is `==` to the deepcopy with the same (immutable,
    // hence safely shared) values, skipping the Python copy.deepcopy round-trip
    // that cProfile showed dominating to_directed (918k calls / 1.38s of 1.88s on
    // attributed gnp(2000)). Conservative: ANY non-scalar value (list/dict/set/
    // tuple/custom object) falls through to the exact copy.deepcopy path, so
    // nested-mutable + memo-sharing semantics are unchanged.
    let mut all_immutable_scalars = true;
    for value in bound.values().iter() {
        // PyBool is a subclass of PyInt in CPython, so the PyInt check covers it;
        // it is listed explicitly for clarity.
        let immutable = value.is_none()
            || value.is_instance_of::<PyBool>()
            || value.is_instance_of::<PyInt>()
            || value.is_instance_of::<PyFloat>()
            || value.is_instance_of::<PyString>();
        if !immutable {
            all_immutable_scalars = false;
            break;
        }
    }
    if all_immutable_scalars {
        return Ok(bound.copy()?.unbind());
    }
    Ok(deepcopy
        .call1((bound,))?
        .downcast_into::<PyDict>()?
        .unbind())
}

/// br-r37-c1-489mp: memo-preserving deep-copy of one attr dict, EXACTLY mirroring
/// the Python `_graph_deepcopy._dc_attrs` fast-path so a native `__deepcopy__` is
/// byte-identical to the Python override it replaces. Differences from
/// `deepcopy_py_dict` (used by to_directed/to_undirected, which take no memo):
///   * the shared `memo` is forwarded to `copy.deepcopy(dict, memo)` so a mutable
///     object referenced by two different attr dicts is copied ONCE (cross-attr
///     identity preserved), matching the override's single shared `memo`.
///   * the immutable fast-path uses EXACT type identity (`type(v) in
///     (bool,int,float,str)`), not `isinstance`, matching `_dc_attrs` — a custom
///     int/str subclass instance therefore falls through to real deepcopy.
pub(crate) fn deepcopy_py_dict_memo(
    py: Python<'_>,
    deepcopy: &Bound<'_, PyAny>,
    attrs: &Py<PyDict>,
    memo: &Bound<'_, PyAny>,
) -> PyResult<Py<PyDict>> {
    let bound = attrs.bind(py);
    if bound.is_empty() {
        return Ok(PyDict::new(py).unbind());
    }
    let mut all_immutable_scalars = true;
    for value in bound.values().iter() {
        let immutable = value.is_none()
            || value.is_exact_instance_of::<PyBool>()
            || value.is_exact_instance_of::<PyInt>()
            || value.is_exact_instance_of::<PyFloat>()
            || value.is_exact_instance_of::<PyString>();
        if !immutable {
            all_immutable_scalars = false;
            break;
        }
    }
    if all_immutable_scalars {
        return Ok(bound.copy()?.unbind());
    }
    Ok(deepcopy
        .call1((bound, memo))?
        .downcast_into::<PyDict>()?
        .unbind())
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
    /// br-r37-c1-adjouter: lazily-built outer `{node: shared_row}` dict for the
    /// SHARED (`adjacency()`) assembly path. `share_dict_of_dicts_cache` rebuilt
    /// this outer dict (one `set_item` per node = O(V)) on EVERY call even though
    /// the rows were already cached, so `dict(G.adjacency())` paid that O(V) outer
    /// rebuild on top of the user-side `dict()` copy (~0.57x vs nx). Caching the
    /// outer here serves warm repeated calls — and the internal
    /// `_native_adjacency_dict()` consumers — the same outer object (all read-only;
    /// the wrapper hands out `iter(outer.items())`, never the dict itself). The
    /// whole cache (incl. this field) is replaced atomically on any
    /// nodes_seq/edges_seq change, so the cached outer never goes stale.
    pub(crate) shared_outer: std::sync::Mutex<Option<Py<PyDict>>>,
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
    /// Live NetworkX-style adjacency row mirrors for simple Graph view iteration.
    pub(crate) adj_row_py: HashMap<String, Py<PyDict>>,
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
    pub(crate) node_keys_cache: std::sync::Mutex<Option<(u64, Py<pyo3::types::PyTuple>)>>,
    node_iter_mirror: std::sync::Mutex<Option<Py<PyDict>>>,
    node_data_mirror: std::sync::Mutex<Option<(u64, Py<PyDict>)>>,
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

    /// br-r37-c1-fpssi: all node display objects as a Vec, reusing the
    /// nodes_seq-keyed tuple cache (clone_ref of cached elements) instead of
    /// rebuilding via py_node_key per node. Backs the graph node iterator
    /// (`set(G)` / `for n in G`), which keeps its per-next nodes_seq guard.
    #[allow(dead_code)]
    pub(crate) fn cached_node_key_vec(&self, py: Python<'_>) -> Vec<PyObject> {
        let seq = self.nodes_seq;
        {
            let guard = self.node_keys_cache.lock().unwrap();
            if let Some((cached_seq, tup)) = guard.as_ref()
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
        *self.node_keys_cache.lock().unwrap() = Some((seq, tup.clone_ref(py)));
        keys
    }

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
        // br-r37-c1-lazynodeattr: lazily build the Python mirror from the inner
        // node AttrMap on first read (symmetric to materialize_edge_py_attrs /
        // the edge lever aab122464). This lets the batch constructor store attrs
        // ONLY in the inner and skip the eager per-node PyDict alloc+copy.
        self.node_py_attrs
            .entry(canonical.to_owned())
            .or_insert_with(|| match self.inner.node_attrs(canonical) {
                Some(attrs) => {
                    attr_map_to_pydict(py, attrs).expect("stored node attrs must convert to Python")
                }
                None => PyDict::new(py).unbind(),
            })
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
            .or_insert_with(|| match self.inner.edge_attrs(left, right) {
                Some(attrs) => attr_map_to_pydict(py, attrs)
                    .expect("stored string-keyed edge attrs must convert to Python"),
                None => PyDict::new(py).unbind(),
            })
            .clone_ref(py)
    }

    pub(crate) fn edge_attr_py_value(
        &self,
        py: Python<'_>,
        left: &str,
        right: &str,
        attr: &str,
    ) -> PyResult<Option<PyObject>> {
        let key = Self::edge_key(left, right);
        if let Some(dict) = self.edge_py_attrs.get(&key) {
            return Ok(dict.bind(py).get_item(attr)?.map(|value| value.unbind()));
        }
        match self
            .inner
            .edge_attrs(left, right)
            .and_then(|attrs| attrs.get(attr))
        {
            Some(value) => Ok(Some(cgse_value_to_py(py, value)?)),
            None => Ok(None),
        }
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
            adj_row_py: HashMap::new(),
            graph_attrs: PyDict::new(py).unbind(),
            nodes_seq: 0,
            edges_seq: 0,
            edges_dirty: AtomicBool::new(false),
            node_keys_cache: std::sync::Mutex::new(None),
            node_iter_mirror: std::sync::Mutex::new(None),
            node_data_mirror: std::sync::Mutex::new(None),
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

    fn cached_adj_set_edge(&mut self, py: Python<'_>, owner: &str, nbr: &str) -> PyResult<()> {
        let Some(row) = self.adj_row_py.get(owner).map(|row| row.clone_ref(py)) else {
            return Ok(());
        };
        let py_nbr = self.py_adj_key(py, owner, nbr);
        let attrs = self.materialize_edge_py_attrs(py, owner, nbr);
        row.bind(py).set_item(py_nbr, attrs.bind(py))?;
        Ok(())
    }

    fn cached_adj_remove_key(&self, py: Python<'_>, owner: &str, nbr: &str) -> PyResult<()> {
        if let Some(row) = self.adj_row_py.get(owner) {
            let py_nbr = self.py_adj_key(py, owner, nbr);
            let _ = row.bind(py).del_item(py_nbr);
        }
        Ok(())
    }

    fn cached_adj_clear_edges_in_place(&self, py: Python<'_>) -> PyResult<()> {
        for row in self.adj_row_py.values() {
            row.bind(py).call_method0("clear")?;
        }
        Ok(())
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
        py: Python<'_>,
        edges: Vec<(String, String)>,
        new_nodes: Vec<(String, PyObject)>,
        node_bumps: u64,
    ) -> PyResult<()> {
        let edge_bumps = u64::try_from(edges.len())
            .unwrap_or(u64::MAX)
            .wrapping_add(1);

        for (canonical, node) in new_nodes {
            self.node_key_map.entry(canonical.clone()).or_insert(node);
            self.node_iter_mirror_insert(py, &canonical)?;
        }
        // br-r37-c1-89kxg: NO eager empty mirror dicts — every reader goes
        // through materialize_*/ensure_*/entry().or_insert, so absence is
        // observationally identical to an empty dict. ~6700 PyDict allocs
        // saved per 5217-edge build.

        let _inserted = self.inner.extend_edges_unrecorded(edges);
        self.nodes_seq = self.nodes_seq.wrapping_add(node_bumps);
        self.edges_seq = self.edges_seq.wrapping_add(edge_bumps);
        Ok(())
    }

    fn int_prefix_display_keys_are_plain_ints(&self, py: Python<'_>) -> bool {
        if !self.adj_py_keys.is_empty() {
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

    fn collect_existing_exact_int_edge_indices<'py, I>(
        &self,
        items: I,
        len: usize,
    ) -> PyResult<Option<Vec<(usize, usize)>>>
    where
        I: IntoIterator<Item = Bound<'py, PyAny>>,
    {
        if !self.inner.nodes_are_contiguous_int_prefix() {
            return Ok(None);
        }
        let node_count = self.inner.node_count();
        let mut edges = Vec::with_capacity(len);
        for item in items {
            let Ok(tuple) = item.downcast::<PyTuple>() else {
                return Ok(None);
            };
            if tuple.len() != 2 {
                return Ok(None);
            }

            let u = tuple.get_item(0)?;
            let v = tuple.get_item(1)?;
            if !u.is_exact_instance_of::<PyInt>() || !v.is_exact_instance_of::<PyInt>() {
                return Ok(None);
            }
            let Ok(u_value) = u.extract::<i64>() else {
                return Ok(None);
            };
            let Ok(v_value) = v.extract::<i64>() else {
                return Ok(None);
            };
            let Ok(u_index) = usize::try_from(u_value) else {
                return Ok(None);
            };
            let Ok(v_index) = usize::try_from(v_value) else {
                return Ok(None);
            };
            if u_index >= node_count || v_index >= node_count {
                return Ok(None);
            }
            edges.push((u_index, v_index));
        }
        Ok(Some(edges))
    }

    /// br-r37-c1-dodattrbatch: attributed sibling of
    /// `collect_existing_exact_int_edge_indices` — collect `(u, v, dict)` triples
    /// as `(u_idx, v_idx, AttrMap)` against an EXISTING contiguous-int node
    /// prefix. Bails (per-edge fallback) on any non-int endpoint, a non-dict
    /// third element, an out-of-range index, or a FailClosed attr key.
    fn collect_existing_exact_int_attr_edge_indices<'py, I>(
        &self,
        py: Python<'py>,
        items: I,
        len: usize,
    ) -> PyResult<Option<Vec<(usize, usize, AttrMap, Option<Py<PyDict>>)>>>
    where
        I: IntoIterator<Item = Bound<'py, PyAny>>,
    {
        if !self.inner.nodes_are_contiguous_int_prefix() {
            return Ok(None);
        }
        let node_count = self.inner.node_count();
        let mut edges = Vec::with_capacity(len);
        // br-r37-c1-batchattrorder (cc): duplicate edge -> nx merges attrs; decline
        // to the per-edge path (exact merge). Rare in from_dict_of_dicts (unique
        // neighbour keys). Lets the >=2-key ordered mirror below skip the multi-
        // occurrence merge.
        let mut seen_edges: HashSet<(usize, usize)> = HashSet::with_capacity(len);
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
            let Ok(u_index) = usize::try_from(u_value) else {
                return Ok(None);
            };
            let Ok(v_index) = usize::try_from(v_value) else {
                return Ok(None);
            };
            if u_index >= node_count || v_index >= node_count {
                return Ok(None);
            }
            if !seen_edges.insert((u_index, v_index)) {
                return Ok(None);
            }
            let third = tuple.get_item(2)?;
            let Ok(dict) = third.downcast::<PyDict>() else {
                return Ok(None);
            };
            // br-r37-c1-batchattrorder (cc): >=2-key dict -> retain the ORDERED
            // mirror so edges(data) keeps nx insertion order (the BTreeMap store
            // sorts). Single-key/empty stay mirror-free (no order to preserve).
            let (attrs, mirror) = if dict.len() >= 2 {
                let Ok((attrs, m)) = py_dict_to_attr_map_with_mirror(py, dict) else {
                    return Ok(None);
                };
                (attrs, Some(m))
            } else {
                let Ok(attrs) = py_dict_to_attr_map(dict) else {
                    return Ok(None);
                };
                (attrs, None)
            };
            if attrs
                .keys()
                .any(|key| key.starts_with("__fnx_incompatible"))
            {
                return Ok(None);
            }
            edges.push((u_index, v_index, attrs, mirror));
        }
        Ok(Some(edges))
    }

    /// br-r37-c1-dodattrbatch: fast bulk add of ATTRIBUTED int edges onto a graph
    /// whose nodes already exist as a contiguous-int prefix with no edges yet —
    /// e.g. from_dict_of_dicts / from_dict_of_lists, which `add_nodes_from(d)`
    /// BEFORE `add_edges_from`, defeating the FRESH attr fast path (node_count==0).
    /// Edge attrs stay LAZY in the inner AttrMap (no eager py mirror), matching
    /// the fresh path.
    fn try_add_existing_exact_int_attr_edge_index_batch(
        &mut self,
        py: Python<'_>,
        ebunch_to_add: &Bound<'_, PyAny>,
    ) -> PyResult<bool> {
        const EXACT_INT_ATTR_INDEX_BATCH_MIN: usize = 8;
        if self.inner.edge_count() != 0
            || !self.adj_row_py.is_empty()
            || !self.edge_py_attrs.is_empty()
            || !self.int_prefix_display_keys_are_plain_ints(py)
        {
            return Ok(false);
        }
        let edges = if let Ok(list) = ebunch_to_add.downcast::<PyList>() {
            if list.len() < EXACT_INT_ATTR_INDEX_BATCH_MIN {
                return Ok(false);
            }
            self.collect_existing_exact_int_attr_edge_indices(py, list.iter(), list.len())?
        } else if let Ok(tuple) = ebunch_to_add.downcast::<PyTuple>() {
            if tuple.len() < EXACT_INT_ATTR_INDEX_BATCH_MIN {
                return Ok(false);
            }
            self.collect_existing_exact_int_attr_edge_indices(py, tuple.iter(), tuple.len())?
        } else {
            return Ok(false);
        };
        let Some(edges) = edges else {
            return Ok(false);
        };
        let edge_bumps = u64::try_from(edges.len())
            .unwrap_or(u64::MAX)
            .wrapping_add(1);
        // br-r37-c1-batchattrorder (cc): store the ORDERED mirror for multi-attr
        // edges (label == index for the contiguous-int prefix; undirected key
        // canonicalised) so edges(data) preserves nx insertion order.
        let mut store_edges: Vec<(usize, usize, AttrMap)> = Vec::with_capacity(edges.len());
        for (u_index, v_index, attrs, mirror) in edges {
            if let Some(m) = mirror {
                let ek = Self::edge_key(&u_index.to_string(), &v_index.to_string());
                self.edge_py_attrs.insert(ek, m);
            }
            store_edges.push((u_index, v_index, attrs));
        }
        let _ = self
            .inner
            .extend_existing_index_edges_with_attrs_unrecorded(store_edges);
        self.edges_seq = self.edges_seq.wrapping_add(edge_bumps);
        Ok(true)
    }

    /// br-r37-c1-dodattrbatch: like `collect_existing_exact_int_attr_edge_indices`
    /// but for int nodes whose LABELS are NOT their indices (e.g. a graph from
    /// `to_dict_of_dicts` of a non-0..n-ordered source). Builds an int-label ->
    /// index map ONCE from the existing nodes, then resolves each endpoint via
    /// that map (one int hash, vs the String hashing of the general path). Bails
    /// on any non-int node, a 2-tuple/4-tuple, or an endpoint that is not an
    /// already-present node (this batch never creates nodes).
    #[allow(clippy::type_complexity)]
    fn collect_existing_int_label_attr_edge_indices<'py, I>(
        &self,
        py: Python<'py>,
        items: I,
        len: usize,
    ) -> PyResult<
        Option<
            Vec<(
                usize,
                usize,
                AttrMap,
                Option<((String, String), Py<PyDict>)>,
            )>,
        >,
    >
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
        // br-r37-c1-batchattrorder (cc): dup edge -> decline (nx merges); rare.
        let mut seen_edges: HashSet<(usize, usize)> = HashSet::with_capacity(len);
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
            if !seen_edges.insert((u_index, v_index)) {
                return Ok(None);
            }
            let third = tuple.get_item(2)?;
            let Ok(dict) = third.downcast::<PyDict>() else {
                return Ok(None);
            };
            // br-r37-c1-batchattrorder (cc): >=2-key dict -> retain the ORDERED
            // mirror keyed by the canonical LABEL pair (label != index here) so
            // edges(data) preserves nx insertion order; single-key/empty stay lazy.
            let (attrs, mirror) = if dict.len() >= 2 {
                let Ok((attrs, m)) = py_dict_to_attr_map_with_mirror(py, dict) else {
                    return Ok(None);
                };
                let ek = Self::edge_key(&u_value.to_string(), &v_value.to_string());
                (attrs, Some((ek, m)))
            } else {
                let Ok(attrs) = py_dict_to_attr_map(dict) else {
                    return Ok(None);
                };
                (attrs, None)
            };
            if attrs
                .keys()
                .any(|key| key.starts_with("__fnx_incompatible"))
            {
                return Ok(None);
            }
            edges.push((u_index, v_index, attrs, mirror));
        }
        Ok(Some(edges))
    }

    /// br-r37-c1-dodattrbatch: int-LABEL (not index) attributed batch — handles
    /// the scrambled-int-node case the exact-index path above misses.
    fn try_add_existing_int_label_attr_edge_batch(
        &mut self,
        py: Python<'_>,
        ebunch_to_add: &Bound<'_, PyAny>,
    ) -> PyResult<bool> {
        const INT_LABEL_ATTR_BATCH_MIN: usize = 8;
        if self.inner.edge_count() != 0
            || !self.adj_row_py.is_empty()
            || !self.edge_py_attrs.is_empty()
            || !self.int_prefix_display_keys_are_plain_ints(py)
        {
            return Ok(false);
        }
        let edges = if let Ok(list) = ebunch_to_add.downcast::<PyList>() {
            if list.len() < INT_LABEL_ATTR_BATCH_MIN {
                return Ok(false);
            }
            self.collect_existing_int_label_attr_edge_indices(py, list.iter(), list.len())?
        } else if let Ok(tuple) = ebunch_to_add.downcast::<PyTuple>() {
            if tuple.len() < INT_LABEL_ATTR_BATCH_MIN {
                return Ok(false);
            }
            self.collect_existing_int_label_attr_edge_indices(py, tuple.iter(), tuple.len())?
        } else {
            return Ok(false);
        };
        let Some(edges) = edges else {
            return Ok(false);
        };
        let edge_bumps = u64::try_from(edges.len())
            .unwrap_or(u64::MAX)
            .wrapping_add(1);
        // br-r37-c1-batchattrorder (cc): store the ordered mirror (canonical label
        // key) for multi-attr edges so edges(data) keeps nx insertion order.
        let mut store_edges: Vec<(usize, usize, AttrMap)> = Vec::with_capacity(edges.len());
        for (u_index, v_index, attrs, mirror) in edges {
            if let Some((ek, m)) = mirror {
                self.edge_py_attrs.insert(ek, m);
            }
            store_edges.push((u_index, v_index, attrs));
        }
        let _ = self
            .inner
            .extend_existing_index_edges_with_attrs_unrecorded(store_edges);
        self.edges_seq = self.edges_seq.wrapping_add(edge_bumps);
        Ok(true)
    }

    fn try_add_existing_exact_int_edge_index_batch(
        &mut self,
        py: Python<'_>,
        ebunch_to_add: &Bound<'_, PyAny>,
    ) -> PyResult<bool> {
        const EXACT_INT_INDEX_BATCH_MIN: usize = 8;
        if !self.adj_row_py.is_empty() || !self.int_prefix_display_keys_are_plain_ints(py) {
            return Ok(false);
        }

        let edges = if let Ok(list) = ebunch_to_add.downcast::<PyList>() {
            if list.len() < EXACT_INT_INDEX_BATCH_MIN {
                return Ok(false);
            }
            self.collect_existing_exact_int_edge_indices(list.iter(), list.len())?
        } else if let Ok(tuple) = ebunch_to_add.downcast::<PyTuple>() {
            if tuple.len() < EXACT_INT_INDEX_BATCH_MIN {
                return Ok(false);
            }
            self.collect_existing_exact_int_edge_indices(tuple.iter(), tuple.len())?
        } else {
            return Ok(false);
        };

        let Some(edges) = edges else {
            return Ok(false);
        };
        let edge_bumps = u64::try_from(edges.len())
            .unwrap_or(u64::MAX)
            .wrapping_add(1);
        let _ = self.inner.extend_existing_index_edges_unrecorded(edges);
        self.edges_seq = self.edges_seq.wrapping_add(edge_bumps);
        Ok(true)
    }

    fn collect_fresh_exact_int_prefix_edges<'py, I>(
        items: I,
        len: usize,
    ) -> PyResult<Option<(usize, Vec<(usize, usize)>)>>
    where
        I: IntoIterator<Item = Bound<'py, PyAny>>,
    {
        let mut edges = Vec::with_capacity(len);
        let mut seen = Vec::<bool>::new();
        let mut next_node = 0usize;

        for item in items {
            let Ok(tuple) = item.downcast::<PyTuple>() else {
                return Ok(None);
            };
            if tuple.len() != 2 {
                return Ok(None);
            }

            let u = tuple.get_item(0)?;
            let v = tuple.get_item(1)?;
            if !u.is_exact_instance_of::<PyInt>() || !v.is_exact_instance_of::<PyInt>() {
                return Ok(None);
            }
            let Ok(u_value) = u.extract::<i64>() else {
                return Ok(None);
            };
            let Ok(v_value) = v.extract::<i64>() else {
                return Ok(None);
            };
            let Ok(u_index) = usize::try_from(u_value) else {
                return Ok(None);
            };
            let Ok(v_index) = usize::try_from(v_value) else {
                return Ok(None);
            };

            for index in [u_index, v_index] {
                if index >= seen.len() {
                    seen.resize(index + 1, false);
                }
                if !seen[index] {
                    if index != next_node {
                        return Ok(None);
                    }
                    seen[index] = true;
                    next_node += 1;
                }
            }
            edges.push((u_index, v_index));
        }

        Ok(Some((next_node, edges)))
    }

    fn try_add_fresh_exact_int_prefix_edge_batch(
        &mut self,
        py: Python<'_>,
        ebunch_to_add: &Bound<'_, PyAny>,
    ) -> PyResult<bool> {
        const FRESH_EXACT_INT_PREFIX_BATCH_MIN: usize = 8;
        if self.inner.node_count() != 0
            || self.inner.edge_count() != 0
            || self.lazy_int_node_stop != 0
            || !self.node_key_map.is_empty()
            || !self.adj_py_keys.is_empty()
            || !self.node_py_attrs.is_empty()
        {
            return Ok(false);
        }

        let collected = if let Ok(list) = ebunch_to_add.downcast::<PyList>() {
            if list.len() < FRESH_EXACT_INT_PREFIX_BATCH_MIN {
                return Ok(false);
            }
            Self::collect_fresh_exact_int_prefix_edges(list.iter(), list.len())?
        } else if let Ok(tuple) = ebunch_to_add.downcast::<PyTuple>() {
            if tuple.len() < FRESH_EXACT_INT_PREFIX_BATCH_MIN {
                return Ok(false);
            }
            Self::collect_fresh_exact_int_prefix_edges(tuple.iter(), tuple.len())?
        } else {
            return Ok(false);
        };

        let Some((node_count, edges)) = collected else {
            return Ok(false);
        };
        let Ok(node_stop) = i64::try_from(node_count) else {
            return Ok(false);
        };
        self._fast_add_int_nodes_range_stop(py, node_stop)?;
        let edge_bumps = u64::try_from(edges.len())
            .unwrap_or(u64::MAX)
            .wrapping_add(1);
        let _ = self.inner.extend_existing_index_edges_unrecorded(edges);
        self.edges_seq = self.edges_seq.wrapping_add(edge_bumps);
        Ok(true)
    }

    fn try_add_plain_edge_batch(
        &mut self,
        py: Python<'_>,
        ebunch_to_add: &Bound<'_, PyAny>,
    ) -> PyResult<bool> {
        const PLAIN_EDGE_BATCH_MIN: usize = 8;
        if !self.adj_row_py.is_empty() {
            return Ok(false);
        }
        if self.try_add_fresh_exact_int_prefix_edge_batch(py, ebunch_to_add)? {
            return Ok(true);
        }
        if self.try_add_existing_exact_int_edge_index_batch(py, ebunch_to_add)? {
            return Ok(true);
        }
        if let Ok(list) = ebunch_to_add.downcast::<PyList>() {
            if list.len() < PLAIN_EDGE_BATCH_MIN {
                return Ok(false);
            }
            if let Some((edges, new_nodes, node_bumps)) =
                self.collect_plain_edge_batch(py, list.iter(), list.len())?
            {
                self.add_plain_edge_batch(py, edges, new_nodes, node_bumps)?;
                return Ok(true);
            }
        } else if let Ok(tuple) = ebunch_to_add.downcast::<PyTuple>()
            && tuple.len() >= PLAIN_EDGE_BATCH_MIN
            && let Some((edges, new_nodes, node_bumps)) =
                self.collect_plain_edge_batch(py, tuple.iter(), tuple.len())?
        {
            self.add_plain_edge_batch(py, edges, new_nodes, node_bumps)?;
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
        global_attr: Option<&Bound<'py, PyDict>>,
    ) -> PyResult<Option<AttrEdgeBatch>>
    where
        I: IntoIterator<Item = Bound<'py, PyAny>>,
    {
        // br-r37-c1-d58s8: global **attr support — nx applies
        // datadict.update(attr) FIRST, then the per-edge dd overrides.
        let global_map: AttrMap = match global_attr {
            Some(a) if !a.is_empty() => match py_dict_to_attr_map(a) {
                Ok(m) if !m.keys().any(|k| k.starts_with("__fnx_incompatible")) => m,
                _ => return Ok(None),
            },
            _ => AttrMap::new(),
        };
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
                if global_map.is_empty() {
                    (attrs, Some(d.clone().unbind()))
                } else {
                    let mut merged_map = global_map.clone();
                    merged_map.extend(attrs);
                    let merged = global_attr
                        .expect("non-empty global_map implies global_attr")
                        .copy()?;
                    merged.update(d.as_mapping())?;
                    (merged_map, Some(merged.unbind()))
                }
            } else if global_map.is_empty() {
                (AttrMap::new(), None)
            } else {
                let merged = global_attr
                    .expect("non-empty global_map implies global_attr")
                    .copy()?;
                (global_map.clone(), Some(merged.unbind()))
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

    fn collect_fresh_exact_int_attr_edge_batch<'py, I>(
        &self,
        py: Python<'py>,
        items: I,
        len: usize,
    ) -> PyResult<Option<IndexedAttrEdgeBatch>>
    where
        I: IntoIterator<Item = Bound<'py, PyAny>>,
    {
        let mut node_indices: HashMap<i64, usize> = HashMap::new();
        let mut node_labels: Vec<String> = Vec::new();
        let mut node_objects: Vec<PyObject> = Vec::new();
        let mut edges: Vec<(usize, usize, AttrMap, Option<Py<PyDict>>)> = Vec::with_capacity(len);
        // br-r37-c1-batchattrorder (cc): a duplicate edge => nx merges attrs
        // (dict.update); the ordered mirror would need the same multi-occurrence
        // merge, so decline to the per-edge path (exact merge+order). Undirected:
        // (u,v)==(v,u), so canonicalise the seen key. Rare in a fresh batch.
        let mut seen_edges: HashSet<(i64, i64)> = HashSet::with_capacity(len);
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
            // Undirected: (u,v) and (v,u) are the same edge.
            let canon = if u_value <= v_value {
                (u_value, v_value)
            } else {
                (v_value, u_value)
            };
            if !seen_edges.insert(canon) {
                return Ok(None);
            }

            let third = tuple.get_item(2)?;
            let Ok(dict) = third.downcast::<PyDict>() else {
                return Ok(None);
            };
            // br-r37-c1-batchattrorder (cc): >=2 keys -> retain the ORDERED mirror so
            // edges(data)/get_edge_data preserve nx insertion order (the BTreeMap store
            // sorts keys). Single-key/empty dicts have no order to preserve.
            let (attrs, mirror) = if dict.len() >= 2 {
                let Ok((attrs, m)) = py_dict_to_attr_map_with_mirror(py, dict) else {
                    return Ok(None);
                };
                (attrs, Some(m))
            } else {
                let Ok(attrs) = py_dict_to_attr_map(dict) else {
                    return Ok(None);
                };
                (attrs, None)
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
            edges.push((u_index, v_index, attrs, mirror));
        }

        Ok(Some((node_labels, node_objects, edges, node_bumps)))
    }

    fn add_fresh_exact_int_attr_edge_batch(
        &mut self,
        py: Python<'_>,
        node_labels: Vec<String>,
        node_objects: Vec<PyObject>,
        edges: Vec<(usize, usize, AttrMap, Option<Py<PyDict>>)>,
        node_bumps: u64,
    ) -> PyResult<()> {
        let edge_bumps = u64::try_from(edges.len())
            .unwrap_or(u64::MAX)
            .wrapping_add(1);

        for (canonical, node) in node_labels.iter().zip(node_objects) {
            self.node_key_map.entry(canonical.clone()).or_insert(node);
            self.node_iter_mirror_insert(py, canonical)?;
        }

        // br-r37-c1-batchattrorder (cc): store ORDERED mirrors for multi-attr edges
        // (undirected key canonicalised) before the node_labels move, then insert the
        // store edges. edges(data)/get_edge_data read the mirror -> insertion order.
        let mut inner_edges: Vec<(usize, usize, AttrMap)> = Vec::with_capacity(edges.len());
        for (u_index, v_index, attrs, mirror) in edges {
            if let Some(m) = mirror {
                let ek = Self::edge_key(&node_labels[u_index], &node_labels[v_index]);
                self.edge_py_attrs.insert(ek, m);
            }
            inner_edges.push((u_index, v_index, attrs));
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
    ) -> PyResult<bool> {
        const ATTR_EDGE_BATCH_MIN: usize = 8;
        if self.inner.node_count() != 0
            || self.inner.edge_count() != 0
            || !self.node_key_map.is_empty()
            || !self.adj_py_keys.is_empty()
            || !self.node_py_attrs.is_empty()
            || !self.edge_py_attrs.is_empty()
            || !self.adj_row_py.is_empty()
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

    /// br-cc-strnodeidremap: fresh-graph attributed-edge batch for STR / TUPLE
    /// (any non-exact-int) node labels — the integer-node-id-remapping primitive.
    /// The general `collect_attr_edge_batch` path stores edges String-keyed, so
    /// `extend_edges_with_attrs_unrecorded` pays a `nodes.get_index_of(&String)`
    /// hash lookup PER ENDPOINT (2*|E| lookups into the growing store). That made
    /// str+attr construction ~0.46x vs nx while int+attr — which already remaps to
    /// a dense index and uses `extend_fresh_index_edges_with_attrs_unrecorded` —
    /// wins 1.15x. Canonicalise each DISTINCT node ONCE, remap to a 0..N index, and
    /// reuse the int fast path's index extend + applier. Same mirror rule as the int
    /// batch (>=2 attrs -> fresh ordered mirror; <2 -> deferred; the deferred single-
    /// attr case is safe now that fnx_to_nx_adjacency store-falls-back). Declines
    /// (-> the general merge path) on duplicate edges or non-plain nodes.
    fn collect_fresh_general_attr_edge_batch<'py, I>(
        &self,
        py: Python<'py>,
        items: I,
        len: usize,
    ) -> PyResult<Option<IndexedAttrEdgeBatch>>
    where
        I: IntoIterator<Item = Bound<'py, PyAny>>,
    {
        let mut node_indices: HashMap<String, usize> = HashMap::new();
        let mut node_labels: Vec<String> = Vec::new();
        let mut node_objects: Vec<PyObject> = Vec::new();
        let mut edges: Vec<(usize, usize, AttrMap, Option<Py<PyDict>>)> = Vec::with_capacity(len);
        let mut seen_edges: HashSet<(usize, usize)> = HashSet::with_capacity(len);
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
            if !Self::is_plain_batch_node(&u) || !Self::is_plain_batch_node(&v) {
                return Ok(None);
            }
            let u_canon = node_key_to_string(py, &u)?;
            let v_canon = node_key_to_string(py, &v)?;

            let third = tuple.get_item(2)?;
            let Ok(dict) = third.downcast::<PyDict>() else {
                return Ok(None);
            };
            // Mirror rule identical to collect_fresh_exact_int_attr_edge_batch.
            let (attrs, mirror) = if dict.len() >= 2 {
                let Ok((attrs, m)) = py_dict_to_attr_map_with_mirror(py, dict) else {
                    return Ok(None);
                };
                (attrs, Some(m))
            } else {
                let Ok(attrs) = py_dict_to_attr_map(dict) else {
                    return Ok(None);
                };
                (attrs, None)
            };
            if attrs
                .keys()
                .any(|key| key.starts_with("__fnx_incompatible"))
            {
                return Ok(None);
            }

            let mut edge_added_node = false;
            let u_index = match node_indices.get(&u_canon).copied() {
                Some(index) => index,
                None => {
                    let index = node_labels.len();
                    node_indices.insert(u_canon.clone(), index);
                    node_labels.push(u_canon);
                    node_objects.push(u.clone().unbind());
                    edge_added_node = true;
                    index
                }
            };
            let v_index = match node_indices.get(&v_canon).copied() {
                Some(index) => index,
                None => {
                    let index = node_labels.len();
                    node_indices.insert(v_canon.clone(), index);
                    node_labels.push(v_canon);
                    node_objects.push(v.clone().unbind());
                    edge_added_node = true;
                    index
                }
            };
            if edge_added_node {
                node_bumps = node_bumps.wrapping_add(1);
            }
            // Undirected: (u,v)==(v,u) — canonicalise the index pair. A duplicate
            // in-batch edge needs nx's dict.update merge, which this fast path does
            // NOT do, so decline to the general (merge-aware) path.
            let canon = if u_index <= v_index {
                (u_index, v_index)
            } else {
                (v_index, u_index)
            };
            if !seen_edges.insert(canon) {
                return Ok(None);
            }
            edges.push((u_index, v_index, attrs, mirror));
        }

        Ok(Some((node_labels, node_objects, edges, node_bumps)))
    }

    fn try_add_fresh_general_attr_edge_batch(
        &mut self,
        py: Python<'_>,
        ebunch_to_add: &Bound<'_, PyAny>,
    ) -> PyResult<bool> {
        const ATTR_EDGE_BATCH_MIN: usize = 8;
        if self.inner.node_count() != 0
            || self.inner.edge_count() != 0
            || !self.node_key_map.is_empty()
            || !self.adj_py_keys.is_empty()
            || !self.node_py_attrs.is_empty()
            || !self.edge_py_attrs.is_empty()
            || !self.adj_row_py.is_empty()
        {
            return Ok(false);
        }

        let collected = if let Ok(list) = ebunch_to_add.downcast::<PyList>() {
            if list.len() < ATTR_EDGE_BATCH_MIN {
                return Ok(false);
            }
            self.collect_fresh_general_attr_edge_batch(py, list.iter(), list.len())?
        } else if let Ok(tuple) = ebunch_to_add.downcast::<PyTuple>() {
            if tuple.len() < ATTR_EDGE_BATCH_MIN {
                return Ok(false);
            }
            self.collect_fresh_general_attr_edge_batch(py, tuple.iter(), tuple.len())?
        } else {
            return Ok(false);
        };

        let Some((node_labels, node_objects, edges, node_bumps)) = collected else {
            return Ok(false);
        };
        self.add_fresh_exact_int_attr_edge_batch(py, node_labels, node_objects, edges, node_bumps)?;
        Ok(true)
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
            self.node_key_map.entry(canonical.clone()).or_insert(node);
            self.node_iter_mirror_insert(py, &canonical)?;
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
        global_attr: Option<&Bound<'_, PyDict>>,
    ) -> PyResult<bool> {
        const ATTR_EDGE_BATCH_MIN: usize = 8;
        if !self.adj_row_py.is_empty() {
            return Ok(false);
        }
        // br-r37-c1-edgebatchlossless (cc): a non-scalar per-edge OR global attr can't
        // round-trip the CgseValue store that the int/general sub-batches below rebuild
        // their lazy mirrors from -> bail the whole batch to the per-edge add_edge path
        // (which keeps the Python object). Scalar batches (incl. weighted {w:float})
        // proceed unchanged.
        if global_attr.is_some_and(|a| !attr_dict_is_batch_lossless(a))
            || !ebunch_batch_lossless(ebunch_to_add)?
        {
            return Ok(false);
        }
        if global_attr.is_none_or(|attrs| attrs.is_empty())
            && self.try_add_fresh_exact_int_attr_edge_batch(py, ebunch_to_add)?
        {
            return Ok(true);
        }
        // br-r37-c1-dodattrbatch: attributed edges onto a graph whose nodes were
        // pre-added as a contiguous-int prefix (from_dict_of_dicts etc.) — the
        // fresh path above bails because node_count != 0, so use the existing-
        // nodes index batch instead of the ~4x-slower String-keyed general path.
        if global_attr.is_none_or(|attrs| attrs.is_empty())
            && self.try_add_existing_exact_int_attr_edge_index_batch(py, ebunch_to_add)?
        {
            return Ok(true);
        }
        // br-r37-c1-dodattrbatch: scrambled-int nodes (label != index) — int-label
        // map lookup beats the String-keyed general batch.
        if global_attr.is_none_or(|attrs| attrs.is_empty())
            && self.try_add_existing_int_label_attr_edge_batch(py, ebunch_to_add)?
        {
            return Ok(true);
        }
        // br-cc-strnodeidremap: FRESH graph with STR / TUPLE (non-exact-int) nodes —
        // remap to a dense index and reuse the int fast path's index extend instead
        // of the String-keyed general batch's per-endpoint get_index_of. Only per-edge
        // attrs (no global), fresh graph; declines (dup edge / non-plain node / global
        // attr) fall through to the general collect_attr_edge_batch below.
        if global_attr.is_none_or(|attrs| attrs.is_empty())
            && self.try_add_fresh_general_attr_edge_batch(py, ebunch_to_add)?
        {
            return Ok(true);
        }
        if let Ok(list) = ebunch_to_add.downcast::<PyList>() {
            if list.len() < ATTR_EDGE_BATCH_MIN {
                return Ok(false);
            }
            if let Some((edges, new_nodes, node_bumps)) =
                self.collect_attr_edge_batch(py, list.iter(), list.len(), global_attr)?
            {
                self.add_attr_edge_batch(py, edges, new_nodes, node_bumps)?;
                return Ok(true);
            }
        } else if let Ok(tuple) = ebunch_to_add.downcast::<PyTuple>()
            && tuple.len() >= ATTR_EDGE_BATCH_MIN
            && let Some((edges, new_nodes, node_bumps)) =
                self.collect_attr_edge_batch(py, tuple.iter(), tuple.len(), global_attr)?
        {
            self.add_attr_edge_batch(py, edges, new_nodes, node_bumps)?;
            return Ok(true);
        }
        Ok(false)
    }

    /// br-r37-c1-nodebatch: collect a batch of attributed nodes — a mix of
    /// plain `n` and `(n, dict)` tuples — for single-commit insertion on a
    /// FRESH graph. Pure collect: NO mutation of self. Returns `Ok(None)`
    /// (caller falls back to the per-node loop, which owns every error and
    /// partial-prefix contract) on ANY item the batch can't replicate
    /// exactly: non-plain nodes, attr values `py_dict_to_attr_map` rejects,
    /// `"__fnx_incompatible"` attr keys, or hash-equal display conflicts.
    /// Mirrors `collect_attr_edge_batch`.
    ///
    /// nx distinguishes a `(node, attr_dict)` pair from a tuple NODE by
    /// hashability: a 2-tuple is unpacked iff it is unhashable, i.e. its
    /// second element is a dict. `(0, 1)` therefore stays a single tuple node.
    fn collect_attr_node_batch<'py, I>(
        &self,
        py: Python<'py>,
        items: I,
        len: usize,
    ) -> PyResult<Option<AttrNodeBatch>>
    where
        I: IntoIterator<Item = Bound<'py, PyAny>>,
    {
        // Per-occurrence (canonical, AttrMap, Option<src dict>) — duplicate
        // canonicals are merged by `extend_nodes_with_attrs_unrecorded`
        // (later wins) and by the mirror `entry().update` below, matching the
        // per-node `add_node` sequence exactly.
        let mut nodes: Vec<(String, AttrMap, Option<Py<PyDict>>)> = Vec::with_capacity(len);
        let mut new_nodes: Vec<(String, PyObject)> = Vec::new();
        let mut seen_nodes: HashSet<String> = HashSet::new();
        let mut node_bumps = 0_u64;
        let mut batch_first: HashMap<String, PyObject> = HashMap::new(); // br-r37-c1-z6uka

        for item in items {
            // Decide (node, attrs): unpack a 2-tuple ONLY when its second
            // element is a dict (nx's unhashable-pair rule). Everything else —
            // scalars and tuple nodes like (0, 1) — is a plain node.
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
                    if !attr_dict_is_batch_lossless(d) {
                        // non-store-round-trippable attr (tuple/list/None/dict/oversized
                        // int/custom) -> bail to the per-node path, which preserves the
                        // Python object in the mirror (br-r37-c1-nodebatchlossless).
                        return Ok(None);
                    }
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
            if self.plain_batch_display_conflict(py, &canonical, &node, &mut batch_first) {
                return Ok(None);
            }
            if !seen_nodes.insert(canonical.clone()) {
                // br-r37-c1-batchattrorder (cc): duplicate node -> nx merges attrs; decline to
                // the per-node path (exact merge+order); the multi-attr mirror only keeps the
                // last occurrence, so a per-node merge is required for correctness.
                return Ok(None);
            }
            node_bumps = node_bumps.wrapping_add(1);
            new_nodes.push((canonical.clone(), node.clone().unbind()));
            nodes.push((canonical, rust_attrs, src));
        }

        Ok(Some((nodes, new_nodes, node_bumps)))
    }

    /// Commit a collected attributed-node batch: node display objects +
    /// iter-mirror keys first, then LAZY PyDict mirrors (only non-empty attr
    /// dicts materialize — `entry().update` merges duplicate-node attrs
    /// exactly like the per-node `add_node`), then ONE
    /// `extend_nodes_with_attrs_unrecorded` (insert-or-merge, no per-node
    /// ledger), then the same `nodes_seq` bump the per-node path performs.
    fn add_attr_node_batch(
        &mut self,
        py: Python<'_>,
        nodes: Vec<(String, AttrMap, Option<Py<PyDict>>)>,
        new_nodes: Vec<(String, PyObject)>,
        node_bumps: u64,
    ) -> PyResult<()> {
        for (canonical, node) in new_nodes {
            self.node_key_map.entry(canonical.clone()).or_insert(node);
            self.node_iter_mirror_insert(py, &canonical)?;
        }
        // br-r37-c1-batchattrorder (cc): create+merge the ORDERED mirror for ATTR'd
        // nodes. The store's AttrMap (BTreeMap) sorts keys, so lazy materialisation
        // of nodes(data)/nodes[n] from it ALPHABETISED multi-attr dicts vs nx's
        // insertion order. `dict.update(src)` preserves the src key order and merges
        // duplicate-node attrs exactly like the per-node add_node sequence. Plain
        // (attr-less) nodes stay mirror-free (empty -> order trivial), so single-
        // weight bulk construction keeps the lazynodeattr win. Matches the DiGraph
        // node batch, which already carried this.
        for (canonical, _, src) in &nodes {
            if let Some(src) = src {
                let bound = src.bind(py);
                if bound.len() >= 2 {
                    let dict = self
                        .node_py_attrs
                        .entry(canonical.clone())
                        .or_insert_with(|| PyDict::new(py).unbind());
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
}

/// br-r37-c1-pr8q6: collected attributed-edge batch —
/// (edges, new_nodes, node_bumps); each edge carries its converted
/// `AttrMap` plus the source `PyDict` for the mirror update.
type AttrEdgeBatch = (
    Vec<(String, String, AttrMap, Option<Py<PyDict>>)>,
    Vec<(String, PyObject)>,
    u64,
);

type IndexedAttrEdgeBatch = (
    Vec<String>,
    Vec<PyObject>,
    // br-r37-c1-batchattrorder (cc): 4th slot = ORDERED mirror PyDict for multi-key
    // (>=2) attr dicts. The store's AttrMap (BTreeMap) sorts keys, so materialising
    // edges(data) from it alphabetises multi-attr dicts vs nx's insertion order.
    Vec<(usize, usize, AttrMap, Option<Py<PyDict>>)>,
    u64,
);

type IndexedKeyedAttrEdgeBatch = (
    Vec<String>,
    Vec<PyObject>,
    Vec<(usize, usize, usize, AttrMap, Option<Py<PyDict>>)>,
    u64,
);

/// br-r37-c1-nodebatch: collected attributed-node batch —
/// (nodes, new_nodes, node_bumps); each node carries its converted
/// `AttrMap` plus the source `PyDict` for the lazy mirror update.
type AttrNodeBatch = (
    Vec<(String, AttrMap, Option<Py<PyDict>>)>,
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
    /// br-paralleladd (bt): true once some edge carries an INT public key whose
    /// value differs from its internal key (the only thing that makes the public
    /// int-key space diverge from the dense/gapped internal key space). While
    /// this is `false`, an auto (`key=None`) add's public key is exactly the
    /// internal auto key, so `add_edge` skips the O(existing-keys) PyO3
    /// public-key scan — repeated parallel `add_edge(u, v)` drops from O(N^2) to
    /// O(N). Maintained by `note_public_key_value` at every key-store site and
    /// propagated verbatim across copy/clone. String/float keys never occupy an
    /// int slot, so they leave it clear.
    pub(crate) has_remapped_int_key: bool,
    pub(crate) edge_mirrors_stale: bool,
    pub(crate) graph_attrs: Py<PyDict>,
    /// br-r37-c1-39d82: see PyGraph::nodes_seq.
    pub(crate) nodes_seq: u64,
    /// br-r37-c1-jft0i: see PyGraph::edges_seq.
    pub(crate) edges_seq: u64,
    /// See PyGraph::edges_dirty.
    pub(crate) edges_dirty: AtomicBool,
    pub(crate) node_keys_cache: std::sync::Mutex<Option<(u64, Py<pyo3::types::PyTuple>)>>,
    /// br-r37-c1-4b5ie: see PyGraph::node_data_mirror — nodes_seq-keyed
    /// {node: attr_dict} cache so repeated nodes(data=...) reuse it.
    pub(crate) node_data_mirror: std::sync::Mutex<Option<(u64, Py<PyDict>)>>,
    /// br-r37-c1-pcw2s: see PyGraph::dict_of_dicts_cache — (nodes_seq, edges_seq)-
    /// keyed {node: {nbr: {key: edge_dict}}} cache so repeated adjacency() calls
    /// reuse the 3-level nested dict instead of rebuilding it (was 131x slower).
    pub(crate) dict_of_dicts_cache: Option<DictOfDictsCache>,
    /// br-r37-c1-o07ax: (nodes_seq, edges_seq)-keyed cache of the (u, v,
    /// live_attr_dict) tuples backing edges(data=True, keys=False). Tuples
    /// immutable + inner dicts live, so repeats return a fresh list of the same
    /// tuple objects instead of re-walking neighbors x edge_keys (was 1.7x).
    pub(crate) edges_with_data_cache: Option<(u64, u64, bool, Vec<PyObject>)>,
    /// br-inedges-attrcache (bt): scalar-snapshot cache for the whole-graph
    /// edges(data=<attr>) tuples (the data=True caches above don't cover scalar
    /// values). Keyed (nodes_seq, edges_seq, keys, attr, default); served only while
    /// !edges_dirty and DROPPED in mark_edges_dirty (attr edits don't bump
    /// edges_seq). Mutex so the &self mark hook can clear it. Single-slot.
    pub(crate) edges_data_attr_cache:
        std::sync::Mutex<Option<(u64, u64, bool, String, PyObject, Vec<PyObject>)>>,
    /// br-r37-c1-3oc6v: (nodes_seq, edges_seq)-keyed cache of immutable
    /// (u, v, key) tuples for edges(keys=True, data=False, no nbunch).
    pub(crate) edges_with_keys_cache: Option<(u64, u64, Vec<PyObject>)>,
    /// Incremental node-iteration mirror — see PyGraph::node_iter_mirror.
    /// Live `{node: None}` dict serving iter(G)/list(G.nodes()) as a
    /// dict_keyiterator, mutated in place by node add/remove/clear hooks.
    pub(crate) node_iter_mirror: std::sync::Mutex<Option<Py<PyDict>>>,
}

impl PyMultiGraph {
    /// br-r37-c1-3oc6v: cache the immutable no-data keyed edge tuples for the
    /// common all-edge MultiGraph view. The tuple content is exactly the same
    /// as `_native_edge_view_list(data=False, keys=True)`: edge orientation is
    /// the first node/neighbor traversal that sees the undirected edge,
    /// endpoint display uses the first-wins adjacency-cell key, and the public
    /// edge key uses the stored first-wins key object.
    pub(crate) fn edges_key_tuples(&mut self, py: Python<'_>) -> PyResult<Vec<PyObject>> {
        let valid = matches!(
            &self.edges_with_keys_cache,
            Some((ns, es, _)) if *ns == self.nodes_seq && *es == self.edges_seq
        );
        if !valid {
            let mut seen: HashSet<(String, String, usize)> =
                HashSet::with_capacity(self.inner.edge_count());
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
                        if !seen.insert(ek) {
                            continue;
                        }
                        let py_u = self.py_node_key(py, node);
                        let py_v = self.py_adj_key(py, node, neighbor);
                        let py_key = self.py_edge_key(py, node, neighbor, key);
                        result.push(PyTuple::new(py, &[py_u, py_v, py_key])?.into_any().unbind());
                    }
                }
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

    /// br-r37-c1-4b5ie: mirror of PyGraph::node_data_items_view for MultiGraph —
    /// cache {node: attr_dict} keyed on nodes_seq and return its `.items()`.
    /// Uses ensure_node_py_attrs so cached dicts are the canonical stored ones
    /// (mutations reflect); node insertion bumps nodes_seq, invalidating it.
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
            let attrs = self.ensure_node_py_attrs(py, node).clone_ref(py);
            dict.set_item(py_key, attrs.bind(py))?;
        }
        let owned = dict.unbind();
        *self.node_data_mirror.lock().unwrap() = Some((seq, owned.clone_ref(py)));
        Ok(owned.bind(py).call_method0("items")?.unbind())
    }

    /// br-r37-c1-urle5: display-conflict guard for the plain-edge batch (mirrors
    /// `PyDiGraph::batch_display_conflict`) — bail if a node's passed display
    /// object would conflict with an already-stored one for the same canonical
    /// key (hash-equal int/float/bool collisions).
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
            // br-r37-c1-lazynodeattr: build the mirror from the inner node AttrMap
            // lazily (symmetric to PyGraph) so the batch skips the eager alloc+copy.
            .or_insert_with(|| match self.inner.node_attrs(canonical) {
                Some(attrs) => {
                    attr_map_to_pydict(py, attrs).expect("stored node attrs must convert to Python")
                }
                None => PyDict::new(py).unbind(),
            })
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
        self.ensure_edge_py_attrs_with_key(py, u, v, key, &ek)
    }

    fn ensure_edge_py_attrs_with_key(
        &mut self,
        py: Python<'_>,
        u: &str,
        v: &str,
        key: usize,
        ek: &(String, String, usize),
    ) -> &Py<PyDict> {
        if !self.edge_py_attrs.contains_key(ek) {
            let dict = match self.inner.edge_attrs(u, v, key) {
                Some(attrs) => attr_map_to_pydict(py, attrs)
                    .expect("stored string-keyed edge attrs must convert to Python"),
                None => PyDict::new(py).unbind(),
            };
            self.edge_py_attrs.insert(ek.clone(), dict);
        }
        self.edge_py_attrs
            .get(ek)
            .expect("edge attr entry inserted above")
    }

    fn edge_attr_py_value(
        &self,
        py: Python<'_>,
        u: &str,
        v: &str,
        key: usize,
        attr: &str,
    ) -> PyResult<Option<PyObject>> {
        match self
            .inner
            .edge_attrs(u, v, key)
            .and_then(|attrs| attrs.get(attr))
        {
            Some(value) => Ok(Some(cgse_value_to_py(py, value)?)),
            None => Ok(None),
        }
    }

    fn edge_data_value_or_default_with_key(
        &mut self,
        py: Python<'_>,
        u: &str,
        v: &str,
        key: usize,
        ek: &(String, String, usize),
        data: &Bound<'_, PyAny>,
        default_obj: &PyObject,
    ) -> PyResult<PyObject> {
        if let Some(attrs) = self.edge_py_attrs.get(ek) {
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
                    let attrs = self.ensure_edge_py_attrs_with_key(py, u, v, key, ek);
                    return Ok(attrs
                        .bind(py)
                        .get_item(data)
                        .ok()
                        .flatten()
                        .map_or_else(|| default_obj.clone_ref(py), |value| value.unbind()));
                }
                return cgse_value_to_py(py, &value);
            }
        }

        Ok(default_obj.clone_ref(py))
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

    /// br-paralleladd (bt): record whether a stored public key REMAPS the int
    /// key space — i.e. it is an int whose value differs from its internal key.
    /// Only such an override can collide with a future auto key (`k in G[u][v]`
    /// where `k` is the int auto candidate), so it is exactly the condition that
    /// disables the O(1) auto-key fast path. Non-int keys (str/float) never
    /// occupy an int slot and leave the flag clear; an int key stored AT its own
    /// value (the identity case, including the `add_fresh_edge_with_key`
    /// explicit-int path) also leaves it clear.
    #[inline]
    fn note_public_key_value(&mut self, internal_key: usize, py_key: &Bound<'_, PyAny>) {
        if self.has_remapped_int_key {
            return;
        }
        // The O(1) auto-key fast path (echo the internal auto key) is valid ONLY
        // when the internal int-key space equals the PUBLIC int-key space. That
        // holds iff every public key is the identity int (public == internal).
        // A non-int key (str/float) occupies an internal int slot WITHOUT
        // occupying the matching public int slot, and a remapped int occupies a
        // different public int — both break the correspondence, so either one
        // forces the slow public-key scan (= nx's exact `len; while k in keys`).
        let is_identity_int = py_key
            .extract::<i64>()
            .ok()
            .and_then(|i| usize::try_from(i).ok())
            == Some(internal_key);
        if !is_identity_int {
            self.has_remapped_int_key = true;
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
        self.note_public_key_value(key, py_key.bind(py));
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
        self.note_public_key_value(key, external_key.bind(py));
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
            edges_data_attr_cache: std::sync::Mutex::new(None),
            inner: MultiGraph::with_runtime_policy(runtime_policy),
            node_key_map: HashMap::new(),
            adj_py_keys: HashMap::new(), // br-r37-c1-z6uka
            node_py_attrs: HashMap::new(),
            edge_py_attrs: HashMap::new(),
            edge_py_keys: HashMap::new(),
            has_remapped_int_key: false,
            edge_mirrors_stale: false,
            graph_attrs: PyDict::new(py).unbind(),
            nodes_seq: 0,
            edges_seq: 0,
            edges_dirty: AtomicBool::new(false),
            node_keys_cache: std::sync::Mutex::new(None),
            node_data_mirror: std::sync::Mutex::new(None),
            dict_of_dicts_cache: None,
            edges_with_data_cache: None,
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
    fn clear_stale_edge_mirrors(&mut self) {
        if self.edge_mirrors_stale {
            self.edge_py_attrs.clear();
            self.edge_py_keys.clear();
            self.edge_mirrors_stale = false;
        }
    }

    #[inline]
    pub(crate) fn mark_edges_dirty(&self) {
        self.edges_dirty.store(true, Ordering::Relaxed);
        // br-inedges-attrcache (bt): an attr mutation that dirties the graph
        // invalidates the frozen scalar snapshot (edges_seq is NOT bumped on attr
        // edits, so the seq key cannot catch it).
        *self.edges_data_attr_cache.lock().unwrap() = None;
    }

    fn collect_fresh_exact_int_keyed_attr_edge_batch(
        &self,
        py: Python<'_>,
        items: &[Bound<'_, PyAny>],
    ) -> PyResult<Option<IndexedKeyedAttrEdgeBatch>> {
        let mut node_indices: HashMap<i64, usize> = HashMap::new();
        let mut node_labels: Vec<String> = Vec::new();
        let mut node_objects: Vec<PyObject> = Vec::new();
        if items.len() > (u32::MAX as usize) / 2 {
            return Ok(None);
        }
        let mut pair_count: HashMap<u64, usize> = HashMap::with_capacity(items.len());
        let mut edges: Vec<(usize, usize, usize, AttrMap, Option<Py<PyDict>>)> =
            Vec::with_capacity(items.len());
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
                Some((attrs, mirror)) => (attrs, Some(mirror)),
                None => match py_dict_to_attr_map_with_mirror(py, dict) {
                    Ok((attrs, mirror)) => {
                        let mirror = if dict.is_empty() { None } else { Some(mirror) };
                        (attrs, mirror)
                    }
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

            let pair = if node_labels[u_index].as_str() <= node_labels[v_index].as_str() {
                (u_index, v_index)
            } else {
                (v_index, u_index)
            };
            let pair_key = ((pair.0 as u64) << 32) | (pair.1 as u64);
            let counter = pair_count.entry(pair_key).or_insert(0);
            let key = *counter;
            *counter += 1;
            edges.push((u_index, v_index, key, attrs, mirror));
        }

        Ok(Some((node_labels, node_objects, edges, node_bumps)))
    }

    fn add_fresh_exact_int_keyed_attr_edge_batch(
        &mut self,
        py: Python<'_>,
        node_labels: Vec<String>,
        node_objects: Vec<PyObject>,
        edges: Vec<(usize, usize, usize, AttrMap, Option<Py<PyDict>>)>,
        node_bumps: u64,
    ) {
        let edge_bumps = u64::try_from(edges.len()).unwrap_or(u64::MAX);

        let mirror_active = self.node_iter_mirror_active();
        for (canonical, node) in node_labels.iter().zip(node_objects) {
            let mk = if mirror_active {
                Some(canonical.clone())
            } else {
                None
            };
            self.node_key_map.entry(canonical.clone()).or_insert(node);
            if let Some(c) = mk {
                let _ = self.node_iter_mirror_insert(py, &c);
            }
        }

        let mut inner_edges = Vec::with_capacity(edges.len());
        for (left_idx, right_idx, key, attrs, mirror) in edges {
            let left = &node_labels[left_idx];
            let right = &node_labels[right_idx];
            if let Some(dict) = mirror {
                self.edge_py_attrs
                    .entry(Self::edge_key(left, right, key))
                    .or_insert(dict);
            }
            inner_edges.push((left_idx, right_idx, key, attrs));
        }

        let _ = self
            .inner
            .extend_fresh_index_keyed_edges_with_attrs_unrecorded(node_labels, inner_edges);
        self.nodes_seq = self.nodes_seq.wrapping_add(node_bumps);
        self.edges_seq = self.edges_seq.wrapping_add(edge_bumps);
    }

    /// br-edgekeyedbatch (bt): 4-tuple EXPLICIT-key sibling of
    /// collect_fresh_exact_int_keyed_attr_edge_batch (which is a 3-tuple AUTO-key
    /// collector despite its name). For a FRESH MultiGraph built directly from
    /// `(u, v, key, attrs)` 4-tuples (was 0.31x vs nx — no fresh 4-tuple batch on
    /// MG). Node first-seen order + given (u,v) edge order = the per-edge add_edge
    /// layout (byte-exact undirected orientation), reusing the same commit. A
    /// DUPLICATE canonical (u<=v, key) within the batch bails to per-edge (nx's
    /// later-overwrites-earlier). ebunch_batch_lossless skips 4-tuples so the attr
    /// dict is validated here.
    fn collect_fresh_exact_int_keyed4_attr_edge_batch(
        &self,
        py: Python<'_>,
        items: &[Bound<'_, PyAny>],
    ) -> PyResult<Option<IndexedKeyedAttrEdgeBatch>> {
        let mut node_indices: HashMap<i64, usize> = HashMap::new();
        let mut node_labels: Vec<String> = Vec::new();
        let mut node_objects: Vec<PyObject> = Vec::new();
        if items.len() > (u32::MAX as usize) / 2 {
            return Ok(None);
        }
        let mut seen_canonical: HashSet<(usize, usize, usize)> =
            HashSet::with_capacity(items.len());
        let mut edges: Vec<(usize, usize, usize, AttrMap, Option<Py<PyDict>>)> =
            Vec::with_capacity(items.len());
        let mut node_bumps = 0_u64;

        for item in items {
            let Ok(tuple) = item.downcast::<PyTuple>() else {
                return Ok(None);
            };
            if tuple.len() != 4 {
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
            let (Ok(u_value), Ok(v_value)) = (u.extract::<i64>(), v.extract::<i64>()) else {
                return Ok(None);
            };
            let key_obj = tuple.get_item(2)?;
            if !key_obj.is_exact_instance_of::<PyInt>() || key_obj.is_exact_instance_of::<PyBool>()
            {
                return Ok(None);
            }
            let Ok(key) = key_obj.extract::<usize>() else {
                return Ok(None);
            };
            let fourth = tuple.get_item(3)?;
            let Ok(dict) = fourth.downcast::<PyDict>() else {
                return Ok(None);
            };
            if !attr_dict_is_batch_lossless(dict) {
                return Ok(None);
            }
            let fast_weight = match single_weight_float_attr_map_with_mirror(py, dict) {
                Ok(converted) => converted,
                Err(_) => return Ok(None),
            };
            let (attrs, mirror) = match fast_weight {
                Some((attrs, mirror)) => (attrs, Some(mirror)),
                None => match py_dict_to_attr_map_with_mirror(py, dict) {
                    Ok((attrs, mirror)) => {
                        let mirror = if dict.is_empty() { None } else { Some(mirror) };
                        (attrs, mirror)
                    }
                    Err(_) => return Ok(None),
                },
            };
            if attrs.keys().any(|k| k.starts_with("__fnx_incompatible")) {
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

            // canonical (u<=v) pair + key dedup — undirected (u,v,key)==(v,u,key)
            let pair = if node_labels[u_index].as_str() <= node_labels[v_index].as_str() {
                (u_index, v_index)
            } else {
                (v_index, u_index)
            };
            if !seen_canonical.insert((pair.0, pair.1, key)) {
                return Ok(None);
            }
            // store in the GIVEN (u,v) order (symmetric adjacency = per-edge layout)
            edges.push((u_index, v_index, key, attrs, mirror));
        }

        Ok(Some((node_labels, node_objects, edges, node_bumps)))
    }

    fn try_add_fresh_exact_int_keyed4_attr_edge_batch(
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
            || !self.adj_py_keys.is_empty()
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
        let collected = self.collect_fresh_exact_int_keyed4_attr_edge_batch(py, &items)?;
        let Some((node_labels, node_objects, edges, node_bumps)) = collected else {
            return Ok(false);
        };
        self.add_fresh_exact_int_keyed_attr_edge_batch(
            py,
            node_labels,
            node_objects,
            edges,
            node_bumps,
        );
        Ok(true)
    }

    fn try_add_fresh_exact_int_keyed_attr_edge_batch(
        &mut self,
        py: Python<'_>,
        ebunch_to_add: &Bound<'_, PyAny>,
        global_attr: Option<&Bound<'_, PyDict>>,
    ) -> PyResult<bool> {
        self.clear_stale_edge_mirrors();
        const ATTR_EDGE_BATCH_MIN: usize = 8;
        if global_attr.is_some_and(|attrs| !attrs.is_empty())
            || self.inner.node_count() != 0
            || self.inner.edge_count() != 0
            || !self.node_key_map.is_empty()
            || !self.adj_py_keys.is_empty()
            || !self.node_py_attrs.is_empty()
            || !self.edge_py_attrs.is_empty()
            || !self.edge_py_keys.is_empty()
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
        let collected = self.collect_fresh_exact_int_keyed_attr_edge_batch(py, &items)?;

        let Some((node_labels, node_objects, edges, node_bumps)) = collected else {
            return Ok(false);
        };
        self.add_fresh_exact_int_keyed_attr_edge_batch(
            py,
            node_labels,
            node_objects,
            edges,
            node_bumps,
        );
        Ok(true)
    }

    /// br-edgekeyedbatch (bt): undirected sibling of PyMultiDiGraph's
    /// try_add_keyed_attr_edges_existing_nodes_batch — an EDGES-ONLY 4-tuple
    /// (u, v, key, attrs) batch for an EDGELESS graph whose nodes already exist
    /// (MultiGraph subgraph().copy(): add_nodes_from THEN add_edges_from(4-tuples),
    /// node_count!=0 bails the fresh batch -> per-edge PyO3 ~0.76x vs nx). Every
    /// endpoint MUST already be a node (any new node bails to per-edge). One Rust
    /// extend_keyed_edges_with_attrs_unrecorded commit (undirected: symmetric
    /// adjacency built in the given (u, v) order = the per-edge add_edge order, so
    /// edges() output stays byte-identical). edge_py_attrs mirror keyed via the
    /// CANONICAL edge_key (u<=v). Safe-subset bail-to-per-edge for everything else.
    fn try_add_keyed_attr_edges_existing_nodes_batch(
        &mut self,
        py: Python<'_>,
        ebunch_to_add: &Bound<'_, PyAny>,
    ) -> PyResult<bool> {
        const ATTR_EDGE_BATCH_MIN: usize = 8;
        if self.inner.edge_count() != 0
            || !self.edge_py_attrs.is_empty()
            || !self.edge_py_keys.is_empty()
            || !self.adj_py_keys.is_empty()
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

        let mut edges: Vec<(String, String, usize, AttrMap)> = Vec::with_capacity(items.len());
        let mut mirrors: Vec<((String, String, usize), Py<PyDict>)> = Vec::new();
        let mut seen_canonical: HashSet<(String, String, usize)> = HashSet::new();
        for item in &items {
            let Ok(tuple) = item.downcast::<PyTuple>() else {
                return Ok(false);
            };
            if tuple.len() != 4 {
                return Ok(false);
            }
            let u = tuple.get_item(0)?;
            let v = tuple.get_item(1)?;
            if !u.is_exact_instance_of::<PyInt>()
                || !v.is_exact_instance_of::<PyInt>()
                || u.is_exact_instance_of::<PyBool>()
                || v.is_exact_instance_of::<PyBool>()
            {
                return Ok(false);
            }
            let (Ok(u_value), Ok(v_value)) = (u.extract::<i64>(), v.extract::<i64>()) else {
                return Ok(false);
            };
            let u_canonical = u_value.to_string();
            let v_canonical = v_value.to_string();
            if !self.node_key_map.contains_key(&u_canonical)
                || !self.node_key_map.contains_key(&v_canonical)
            {
                return Ok(false);
            }
            let key_obj = tuple.get_item(2)?;
            if !key_obj.is_exact_instance_of::<PyInt>() || key_obj.is_exact_instance_of::<PyBool>()
            {
                return Ok(false);
            }
            let Ok(key) = key_obj.extract::<usize>() else {
                return Ok(false);
            };
            let fourth = tuple.get_item(3)?;
            let Ok(dict) = fourth.downcast::<PyDict>() else {
                return Ok(false);
            };
            // ebunch_batch_lossless only inspects 3-tuples -> validate the 4-tuple's
            // attrs here (a non-scalar value would be stringified = batch corruption).
            if !attr_dict_is_batch_lossless(dict) {
                return Ok(false);
            }
            let fast_weight = match single_weight_float_attr_map_with_mirror(py, dict) {
                Ok(converted) => converted,
                Err(_) => return Ok(false),
            };
            let (attrs, mirror) = match fast_weight {
                Some((attrs, mirror)) => (attrs, Some(mirror)),
                None => match py_dict_to_attr_map_with_mirror(py, dict) {
                    Ok((attrs, mirror)) => {
                        let mirror = if dict.is_empty() { None } else { Some(mirror) };
                        (attrs, mirror)
                    }
                    Err(_) => return Ok(false),
                },
            };
            if attrs.keys().any(|k| k.starts_with("__fnx_incompatible")) {
                return Ok(false);
            }
            // canonical (u<=v) dedup: an undirected (u,v,key) == (v,u,key)
            let canon = Self::edge_key(&u_canonical, &v_canonical, key);
            if !seen_canonical.insert(canon.clone()) {
                return Ok(false);
            }
            if let Some(mirror) = mirror {
                mirrors.push((canon, mirror));
            }
            // store edges in the GIVEN (u, v) order so extend_keyed builds the same
            // symmetric adjacency the per-edge path would.
            edges.push((u_canonical, v_canonical, key, attrs));
        }

        let edge_bumps = u64::try_from(edges.len()).unwrap_or(u64::MAX);
        for (canon, mirror) in mirrors {
            self.edge_py_attrs.entry(canon).or_insert(mirror);
        }
        let _inserted = self.inner.extend_keyed_edges_with_attrs_unrecorded(edges);
        self.edges_seq = self.edges_seq.wrapping_add(edge_bumps);
        Ok(true)
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
            // br-r37-c1-ctor2tuple: accept bare `(u, v)` edges too (auto integer
            // key, like add_edge) — a plain `MultiGraph([(u, v), ...])` otherwise
            // fell through to the per-edge add_edge loop (~1.5x nx). 3/4-tuples keep
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

            // Undirected: key counter is per UNORDERED pair (min, max).
            let pair = if u_canonical <= v_canonical {
                (u_canonical.clone(), v_canonical.clone())
            } else {
                (v_canonical.clone(), u_canonical.clone())
            };
            let internal_key = match &key {
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
                edge_attrs
                    .entry(edge_key.clone())
                    .or_insert_with(|| PyDict::new(py).unbind());
                AttrMap::new()
            } else {
                // br-r37-c1-ctor2tuple: bare 2-tuple, lazy attr dict (no per-edge alloc).
                AttrMap::new()
            };
            if let Some(key) = key {
                // br-r37-c1-mgkeyidentity (cc): an EXACT non-negative int public key
                // equal to its internal auto-key needs NO edge_py_keys mirror entry —
                // display_key_lookup falls back to int:{internal}. Skip recording it so
                // the common identity-int keyed batch (compose/union of auto-key
                // multigraphs pass 4-tuples (u,v,0/1/2,data)) avoids the per-edge mirror
                // insert + note_public_key_value. Non-identity (str/float/bool/remapped)
                // keys still mirror. Byte-identical read path.
                let key_is_identity_int = key.is_exact_instance_of::<PyInt>()
                    && key
                        .extract::<i64>()
                        .ok()
                        .and_then(|i| usize::try_from(i).ok())
                        == Some(internal_key);
                if !key_is_identity_int {
                    edge_keys
                        .entry(edge_key)
                        .or_insert_with(|| key.clone().unbind());
                }
            }
            edge_batch.push((u_canonical, v_canonical, internal_key, rust_attrs));
        }

        let mirror_active = self.node_iter_mirror_active();
        for (canonical, node) in node_entries {
            let mk = if mirror_active {
                Some(canonical.clone())
            } else {
                None
            };
            self.node_key_map.entry(canonical).or_insert(node);
            if let Some(c) = mk {
                let _ = self.node_iter_mirror_insert(py, &c);
            }
        }
        let inserted_edges = self
            .inner
            .extend_keyed_edges_with_attrs_unrecorded(edge_batch);
        self.edge_py_attrs.extend(edge_attrs);
        for (ek, obj) in &edge_keys {
            self.note_public_key_value(ek.2, obj.bind(py));
        }
        self.edge_py_keys.extend(edge_keys);
        if !node_seen.is_empty() {
            self.bump_nodes_seq();
        }
        if inserted_edges > 0 {
            self.bump_edges_seq();
        }
        Ok(true)
    }

    /// br-r37-c1-nodebatch: collect a batch of attributed nodes — a mix of
    /// plain `n` and `(n, dict)` tuples — for single-commit insertion on a
    /// FRESH MultiGraph. Pure collect: NO mutation. Returns `Ok(None)` (caller
    /// falls back to the per-node loop, which owns every error and
    /// partial-prefix contract) on any shape it can't replicate exactly.
    /// Sibling of `PyGraph::collect_attr_node_batch`. nx's unhashable-pair
    /// rule: a 2-tuple is `(node, attrs)` only when its 2nd element is a dict.
    fn collect_attr_node_batch<'py, I>(
        &self,
        py: Python<'py>,
        items: I,
        len: usize,
    ) -> PyResult<Option<AttrNodeBatch>>
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

            if !PyGraph::is_plain_batch_node(&node) {
                return Ok(None);
            }

            let (rust_attrs, src) = match &src_dict {
                Some(d) => {
                    if !attr_dict_is_batch_lossless(d) {
                        // non-store-round-trippable attr (tuple/list/None/dict/oversized
                        // int/custom) -> bail to the per-node path, which preserves the
                        // Python object in the mirror (br-r37-c1-nodebatchlossless).
                        return Ok(None);
                    }
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
            if !seen_nodes.insert(canonical.clone()) {
                // br-r37-c1-batchattrorder (cc): duplicate node -> nx merges attrs; decline to
                // the per-node path (exact merge+order); the multi-attr mirror only keeps the
                // last occurrence, so a per-node merge is required for correctness.
                return Ok(None);
            }
            node_bumps = node_bumps.wrapping_add(1);
            new_nodes.push((canonical.clone(), node.clone().unbind()));
            nodes.push((canonical, rust_attrs, src));
        }

        Ok(Some((nodes, new_nodes, node_bumps)))
    }

    /// Commit a collected attributed-node batch (MultiGraph LAZY mirror —
    /// matching `add_node`'s `ensure_node_py_attrs`-only-when-attrs): node
    /// display objects first, then non-empty PyDict mirrors (`entry().update`
    /// merges duplicate-node attrs), then ONE
    /// `extend_nodes_with_attrs_unrecorded` and the `nodes_seq` bump.
    fn add_attr_node_batch(
        &mut self,
        py: Python<'_>,
        nodes: Vec<(String, AttrMap, Option<Py<PyDict>>)>,
        new_nodes: Vec<(String, PyObject)>,
        node_bumps: u64,
    ) -> PyResult<()> {
        let mirror_active = self.node_iter_mirror_active();
        for (canonical, node) in new_nodes {
            let mk = if mirror_active {
                Some(canonical.clone())
            } else {
                None
            };
            self.node_key_map.entry(canonical).or_insert(node);
            if let Some(c) = mk {
                let _ = self.node_iter_mirror_insert(py, &c);
            }
        }
        // br-r37-c1-batchattrorder (cc): ordered mirror for ATTR'd nodes so
        // nodes(data) preserves nx insertion order (the BTreeMap store sorts) +
        // merges duplicate-node attrs. Plain nodes stay lazy. See PyGraph twin.
        for (canonical, _, src) in &nodes {
            if let Some(src) = src {
                let bound = src.bind(py);
                if bound.len() >= 2 {
                    let dict = self
                        .node_py_attrs
                        .entry(canonical.clone())
                        .or_insert_with(|| PyDict::new(py).unbind());
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
                // br-r37-c1-tbh4q: single-pass attr crossing via
                // py_dict_to_attr_map_with_mirror (Rust AttrMap + Python mirror
                // in ONE dict iteration) instead of py_dict_to_attr_map (pass 1)
                // + dict.copy() (pass 2) + a duplicate hashmap lookup. The mirror
                // is a shallow copy with contents/order identical to `.copy()`,
                // and there is no reciprocal merge on this same-type absorb path
                // (each node/edge appears once), so the result is byte-identical.
                for (canonical, py_key) in &other.node_key_map {
                    g.node_key_map
                        .insert(canonical.clone(), py_key.clone_ref(py));
                    match other.node_py_attrs.get(canonical) {
                        Some(attrs) => {
                            let (rust_attrs, mirror) =
                                py_dict_to_attr_map_with_mirror(py, attrs.bind(py))?;
                            g.inner.add_node_with_attrs(canonical.clone(), rust_attrs);
                            g.node_py_attrs.insert(canonical.clone(), mirror);
                        }
                        None => {
                            g.inner
                                .add_node_with_attrs(canonical.clone(), AttrMap::new());
                        }
                    }
                }
                for edge in other.inner.edges_ordered() {
                    let ek = Self::edge_key(&edge.left, &edge.right, edge.key);
                    match other.edge_py_attrs.get(&ek) {
                        Some(attrs) => {
                            let (rust_attrs, mirror) =
                                py_dict_to_attr_map_with_mirror(py, attrs.bind(py))?;
                            let _ = g.inner.add_edge_with_key_and_attrs(
                                edge.left.clone(),
                                edge.right.clone(),
                                edge.key,
                                rust_attrs,
                            );
                            g.edge_py_attrs.insert(ek.clone(), mirror);
                        }
                        None => {
                            let _ = g.inner.add_edge_with_key_and_attrs(
                                edge.left.clone(),
                                edge.right.clone(),
                                edge.key,
                                AttrMap::new(),
                            );
                        }
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
                // br-r37-c1-tbh4q: single-pass attr crossing (with_mirror) on the
                // MultiGraph(PyGraph) absorb — no reciprocal merge (each node/edge
                // appears once), mirror is byte-identical to .copy().
                for canonical in other.inner.nodes_ordered() {
                    g.node_key_map
                        .insert(canonical.to_owned(), other.py_node_key(py, canonical));
                    match other.node_py_attrs.get(canonical) {
                        Some(attrs) => {
                            let (rust_attrs, mirror) =
                                py_dict_to_attr_map_with_mirror(py, attrs.bind(py))?;
                            g.inner
                                .add_node_with_attrs(canonical.to_owned(), rust_attrs);
                            g.node_py_attrs.insert(canonical.to_owned(), mirror);
                        }
                        None => {
                            g.inner
                                .add_node_with_attrs(canonical.to_owned(), AttrMap::new());
                        }
                    }
                }
                for edge in other.inner.edges_ordered() {
                    let ek = PyGraph::edge_key(&edge.left, &edge.right);
                    let (rust_attrs, mirror) = match other.edge_py_attrs.get(&ek) {
                        Some(attrs) => {
                            let (r, m) = py_dict_to_attr_map_with_mirror(py, attrs.bind(py))?;
                            (r, Some(m))
                        }
                        None => (AttrMap::new(), None),
                    };
                    let key = g
                        .inner
                        .add_edge_with_key_and_attrs(
                            edge.left.clone(),
                            edge.right.clone(),
                            0,
                            rust_attrs,
                        )
                        .map_err(|e| NetworkXError::new_err(e.to_string()))?;
                    if let Some(mirror) = mirror {
                        g.edge_py_attrs
                            .insert(Self::edge_key(&edge.left, &edge.right, key), mirror);
                    }
                    g.remember_edge_key(py, &edge.left, &edge.right, key, None);
                }
                g.graph_attrs = other.graph_attrs.bind(py).copy()?.unbind();
            } else if g.try_absorb_exact_int_str_keyed_ctor_edges(py, data)? {
                // Constructor-only batch path for exact int endpoints + exact str keys.
            } else if g._try_add_attr_edges_from_batch(py, data, None)? {
                // br-r37-c1-ctorbatch (cc): (u,v,attr_dict) 3-tuples route through
                // the add_edges_from fast batch (lazy mirrors); try_absorb above
                // only handles (u,v)/(u,v,key_string)/(u,v,key,dict), so weighted
                // 3-tuples fell to the per-edge loop (~0.38x). Mutation-free on
                // false -> the iterator loop below still owns declined inputs.
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

    /// br-r37-c1-nodekeys: all node DISPLAY objects as a flat Python list in
    /// ONE call. Python ``set(graph)`` / ``set(graph.nodes())`` cross PyO3 per
    /// node (~5x nx on node-set construction); building the Vec in Rust lets
    /// callers like ``non_neighbors`` enumerate every node in a single
    /// boundary crossing. Order = node insertion order (``nodes_ordered``).
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

    /// br-inedges-autokey (bt): side-effect-free public-key set for a (u, v)
    /// pair, for the auto-key add_edge path's `new_edge_key` computation. Unlike
    /// `get_edge_data(u, v)` (which materializes live mirror attr dicts AND marks
    /// the WHOLE graph dirty so it can hand out mutable dicts), this returns ONLY
    /// the key objects -- no attr materialization, no dirty mark. Keeping the
    /// graph clean lets subsequent read-views stay on their store-read fast paths
    /// after a parallel-edge build.
    fn _native_edge_key_set(
        &self,
        py: Python<'_>,
        u: &Bound<'_, PyAny>,
        v: &Bound<'_, PyAny>,
    ) -> PyResult<PyObject> {
        let u_c = node_key_to_string(py, u)?;
        let v_c = node_key_to_string(py, v)?;
        let set = pyo3::types::PySet::empty(py)?;
        if let Some(keys) = self.inner.edge_keys(&u_c, &v_c) {
            for k in keys {
                set.add(self.py_edge_key(py, &u_c, &v_c, k))?;
            }
        }
        Ok(set.into_any().unbind())
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
        self.edges_dirty.store(false, Ordering::Relaxed);
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
                        None => match self.edge_attr_py_value(
                            py,
                            &edge.left,
                            &edge.right,
                            edge.key,
                            attr,
                        )? {
                            Some(val) => total += val.bind(py).extract::<f64>()?,
                            None => total += 1.0,
                        },
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
        // ``0`` doesn't overwrite the displayed Py form. ``add_edge``
        // already uses this pattern at the call site below.
        self.node_key_map
            .entry(canonical.clone())
            .or_insert_with(|| node_for_adding.clone().unbind());

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

        if self.node_iter_mirror_active() {
            // Remove from the live mirror while node_key_map still holds the
            // display object (mirror keys are the display py objects).
            let py_key = self.py_node_key(py, &canonical);
            self.node_iter_mirror_remove_key(py, py_key.bind(py));
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
        // br-r37-c1-mgrnf: batch the inner removal. The old per-node loop called
        // `inner.remove_node` k times, and MultiGraph::remove_node does two
        // O(|V|) `shift_remove`s per call, so `remove_nodes_from` was O(k·|V|)
        // (~8x slower than nx on a 500-node sweep). Purge each removed node's
        // Python-side mirror entries while `inner` is still intact, then compact
        // `inner` ONCE via `remove_nodes_from` — the same fix the simple `Graph`
        // binding already carries (see PyGraph::remove_nodes_from).
        let iter = PyIterator::from_object(nodes)?;
        let mut present: Vec<String> = Vec::new();
        // FxHashSet: probed once per edge-mirror / adj-override entry in the
        // retains below (SipHash on those string keys was a hot spot).
        let mut present_set: rustc_hash::FxHashSet<String> = rustc_hash::FxHashSet::default();
        for item in iter {
            let item = item?;
            let canonical = node_key_to_string(py, &item)?;
            if self.inner.has_node(&canonical) && present_set.insert(canonical.clone()) {
                present.push(canonical);
            }
        }
        if present.is_empty() {
            self.bump_nodes_seq();
            return Ok(());
        }
        // br-r37-c1-mgrnf2: node-side mirror purge is O(k), independent of degree.
        for canonical in &present {
            if self.node_iter_mirror_active() {
                // Remove from the live mirror while node_key_map still holds the
                // display object (mirror keys are the display py objects).
                let py_key = self.py_node_key(py, canonical);
                self.node_iter_mirror_remove_key(py, py_key.bind(py));
            }
            self.node_key_map.remove(canonical);
            self.node_py_attrs.remove(canonical);
        }
        // br-r37-c1-mgrnf2: KILL the O(k·degree) per-node edge walk. The prior
        // version called inner.neighbors()+edge_keys() per removed node (a fresh
        // Vec<String>+Vec<usize> alloc per incident edge plus a canonical-String
        // edge_key build per HashMap probe) purely to purge the edge mirrors —
        // O(k·degree) allocations that DOMINATED wall time (per-removal cost scaled
        // linearly with degree: 3.3us@deg4 -> 56us@deg40). Drop it for a single
        // endpoint-keyed retain over each mirror (O(mirror size) once, and 0 for
        // the common bulk-built/pristine graph). An entry (l,r,k) is dropped iff
        // EITHER endpoint is removed — correct regardless of key canonicalisation,
        // and also sweeps any stale entry the inner-walk would have missed.
        // br-r37-c1-mgrnf-incident: adaptive mirror purge. The whole-mirror retain
        // is O(|mirror|) — fine for a large removal, but it scans EVERY edge-attr
        // entry even to drop a handful of nodes, so on per-edge-built graphs (whose
        // mirrors are populated eagerly) a small removal paid O(|E|) (removing 10
        // nodes from a 2000/10000 graph was 0.02x). For a small removal, reconstruct
        // exactly the removed nodes' incident mirror keys from `inner` (still intact)
        // — O(k·degree), cheap when k is small — and drop only those.
        let mut removed_py_edge_mirror = false;
        let mirrors_populated = !self.edge_py_attrs.is_empty() || !self.edge_py_keys.is_empty();
        if mirrors_populated {
            if present.len().saturating_mul(4) <= self.inner.node_count() {
                for canonical in &present {
                    if let Some(neighbors) = self
                        .inner
                        .neighbors(canonical)
                        .map(|v| v.into_iter().map(str::to_owned).collect::<Vec<_>>())
                    {
                        for nb in &neighbors {
                            if let Some(keys) = self.inner.edge_keys(canonical, nb) {
                                for key in keys {
                                    self.remove_edge_metadata(canonical, nb, key);
                                    removed_py_edge_mirror = true;
                                }
                            }
                        }
                    }
                }
            } else {
                if !self.edge_py_attrs.is_empty() {
                    self.edge_py_attrs.retain(|(l, r, _k), _| {
                        let keep = !present_set.contains(l) && !present_set.contains(r);
                        if !keep {
                            removed_py_edge_mirror = true;
                        }
                        keep
                    });
                }
                if !self.edge_py_keys.is_empty() {
                    self.edge_py_keys.retain(|(l, r, _k), _| {
                        !present_set.contains(l) && !present_set.contains(r)
                    });
                }
            }
        }
        if !self.adj_py_keys.is_empty() {
            // br-r37-c1-z6uka: drop cell overrides touching any removed node.
            self.adj_py_keys
                .retain(|(a, b), _| !present_set.contains(a) && !present_set.contains(b));
        }
        let present_refs: Vec<&str> = present.iter().map(String::as_str).collect();
        // removed_edges (parallel-edge instances) tells us whether the edge set
        // changed — the had_incident_edges signal, now free from the inner batch.
        let (_removed_nodes, removed_edges) =
            self.inner.remove_nodes_from(present_refs.iter().copied());
        self.bump_nodes_seq();
        if removed_edges > 0 || removed_py_edge_mirror {
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
        self.clear_stale_edge_mirrors();
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
        //
        // br-paralleladd (bt): that divergence happens ONLY when some int public
        // key was remapped off its internal key (tracked by has_remapped_int_key).
        // While no such remap exists, the public int space equals the internal
        // key space exactly (gaps included), so the internal auto key computed by
        // `inner.add_edge_with_attrs` below IS the public key — leave
        // `auto_public_key = None` and let `remember_edge_key` echo `int(actual
        // _key)`. This skips the O(existing-keys) PyO3 scan, turning a loop of
        // parallel `add_edge(u, v)` from O(N^2) into O(N).
        let auto_public_key: Option<PyObject> = if key.is_none() && self.has_remapped_int_key {
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

    /// br-r37-c1-urle5: native plain-edge batch for `add_edges_from([(u, v), ...])`
    /// on a FRESH MultiGraph (no existing edges). The multigraph path otherwise
    /// falls to per-edge Python `_multi_add_edges_from` → `add_edge` (~4x nx on
    /// bulk construction). Restricting to `edge_count == 0` makes every auto-key
    /// SEQUENTIAL per pair (0, 1, 2, …) — no gap-aware public-key computation is
    /// needed, the internal key equals the public key, and plain nodes need no
    /// z6uka adj-cell display objects. Returns `false` (no mutation performed) for
    /// anything outside this fast shape so the Python path handles it. Mirrors
    /// `PyGraph::collect_plain_edge_batch` + lazy attr mirrors, with one bulk
    /// `extend_keyed_edges_with_attrs_unrecorded` (one ledger record).
    fn _try_add_edges_from_batch(
        &mut self,
        py: Python<'_>,
        ebunch_to_add: &Bound<'_, PyAny>,
    ) -> PyResult<bool> {
        self.clear_stale_edge_mirrors();
        const PLAIN_EDGE_BATCH_MIN: usize = 8;
        if self.inner.edge_count() != 0 || !self.adj_py_keys.is_empty() {
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

        let mut edges: Vec<(String, String, usize, AttrMap)> = Vec::with_capacity(items.len());
        let mut new_nodes: Vec<(String, PyObject)> = Vec::new();
        let mut seen_nodes: HashSet<String> = self
            .inner
            .nodes_ordered()
            .into_iter()
            .map(str::to_owned)
            .collect();
        let mut batch_first: HashMap<String, PyObject> = HashMap::new();
        let mut pair_count: HashMap<(String, String), usize> = HashMap::new();
        let mut node_bumps = 0_u64;
        // br-r37-c1-batchstrmemo: memoize node_key_to_string by Python object IDENTITY
        // within this batch. The same node object recurs across many edges (a star's
        // hub is in every edge; dense generators reuse cached small ints), so the
        // canonical-key string was re-formatted O(deg) times per node. Cache it (keyed
        // by the object pointer, stable within one call) -> O(unique) builds, not O(E).
        let mut str_memo: HashMap<usize, String> = HashMap::new();

        for item in &items {
            let Ok(tuple) = item.downcast::<PyTuple>() else {
                return Ok(false);
            };
            if tuple.len() != 2 {
                return Ok(false);
            }
            let u = tuple.get_item(0)?;
            let v = tuple.get_item(1)?;
            if !PyGraph::is_plain_batch_node(&u) || !PyGraph::is_plain_batch_node(&v) {
                return Ok(false);
            }
            let uc = match str_memo.get(&(u.as_ptr() as usize)) {
                Some(s) => s.clone(),
                None => {
                    let s = node_key_to_string(py, &u)?;
                    str_memo.insert(u.as_ptr() as usize, s.clone());
                    s
                }
            };
            let vc = match str_memo.get(&(v.as_ptr() as usize)) {
                Some(s) => s.clone(),
                None => {
                    let s = node_key_to_string(py, &v)?;
                    str_memo.insert(v.as_ptr() as usize, s.clone());
                    s
                }
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
            // Undirected pair key matches `EdgeKey::new` (string-ordered).
            let pair = if uc <= vc {
                (uc.clone(), vc.clone())
            } else {
                (vc.clone(), uc.clone())
            };
            let counter = pair_count.entry(pair).or_insert(0);
            let key = *counter;
            *counter += 1;
            edges.push((uc, vc, key, AttrMap::new()));
        }

        let edge_bumps = u64::try_from(edges.len()).unwrap_or(u64::MAX);
        let mirror_active = self.node_iter_mirror_active();
        for (canonical, node) in new_nodes {
            let mk = if mirror_active {
                Some(canonical.clone())
            } else {
                None
            };
            self.node_key_map.entry(canonical).or_insert(node);
            if let Some(c) = mk {
                let _ = self.node_iter_mirror_insert(py, &c);
            }
        }
        self.inner.extend_keyed_edges_with_attrs_unrecorded(edges);
        self.nodes_seq = self.nodes_seq.wrapping_add(node_bumps);
        self.edges_seq = self.edges_seq.wrapping_add(edge_bumps);
        Ok(true)
    }

    /// br-r37-c1-nodebatch: native attributed-node batch for
    /// `add_nodes_from([(n, dict), ...])` on a FRESH MultiGraph — sibling of
    /// `PyGraph::_try_add_nodes_from_batch`. The per-node loop pays ~5.5x nx on
    /// attributed bulk construction. Returns `false` (NO mutation) for anything
    /// outside this shape so the per-node loop owns every error/partial-prefix
    /// contract.
    fn _try_add_nodes_from_batch(
        &mut self,
        py: Python<'_>,
        nodes_to_add: &Bound<'_, PyAny>,
    ) -> PyResult<bool> {
        const NODE_BATCH_MIN: usize = 8;
        if self.inner.node_count() != 0
            || self.inner.edge_count() != 0
            || !self.adj_py_keys.is_empty()
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
    /// MultiGraph — the multi sibling of `PyGraph::_fast_add_int_nodes`, using the inner
    /// `extend_nodes_with_attrs_unrecorded` with empty AttrMaps. Py int objects are stored
    /// (no lazy_int_node_stop). Atomic validate-then-mutate: exact-int only (excludes
    /// bool), else raise so the wrapper falls back. Was the 0.28x / 0.54x node-add loss.
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
    /// plain `(u, v)`) on a FRESH MultiGraph. The
    /// per-edge Python loop in `_multi_add_edges_from` paid ~3.6x nx on
    /// attributed bulk construction (PyO3 `add_edge` + `get_edge_data().update`
    /// per edge). On a fresh graph every auto-key is SEQUENTIAL per canonical
    /// pair (0, 1, 2, …) — internal key == public key, exactly as the plain
    /// batch. Each 3-tuple's third element MUST be a `dict` (multigraph DATA;
    /// nx auto-keys it); convert it to an `AttrMap` and lazily mirror non-empty
    /// dicts into `edge_py_attrs` (canonical `edge_key`, a FRESH fnx-owned dict
    /// — never aliasing the caller's input). Optional global `**attr` merges
    /// first and per-edge dicts override. One bulk
    /// `extend_keyed_edges_with_attrs_unrecorded`. Returns `false` (NO mutation)
    /// for anything outside this shape (4-tuples, non-dict thirds, non-plain
    /// nodes, `__fnx_incompatible`/unconvertible attr values, hash-equal
    /// display conflicts, non-fresh graph) so the per-edge loop owns every
    /// error and partial-prefix contract.
    #[pyo3(signature = (ebunch_to_add, global_attr=None))]
    fn _try_add_attr_edges_from_batch(
        &mut self,
        py: Python<'_>,
        ebunch_to_add: &Bound<'_, PyAny>,
        global_attr: Option<&Bound<'_, PyDict>>,
    ) -> PyResult<bool> {
        self.clear_stale_edge_mirrors();
        // br-r37-c1-edgebatchlossless (cc): non-scalar per-edge/global attr -> per-edge
        // add_edge (sub-batches rebuild lazy mirrors from the scalar-only store).
        if global_attr.is_some_and(|a| !attr_dict_is_batch_lossless(a))
            || !ebunch_batch_lossless(ebunch_to_add)?
        {
            return Ok(false);
        }
        if self.try_add_fresh_exact_int_keyed_attr_edge_batch(py, ebunch_to_add, global_attr)? {
            return Ok(true);
        }
        // br-edgekeyedbatch (bt): FRESH 4-tuple explicit-key batch (the "fresh_keyed"
        // attempt above is a 3-tuple AUTO-key collector; MG fresh 4-tuple keyed
        // add_edges_from was 0.31x vs nx). Self-validates + bails to per-edge.
        if global_attr.is_none_or(|attrs| attrs.is_empty())
            && self.try_add_fresh_exact_int_keyed4_attr_edge_batch(py, ebunch_to_add)?
        {
            return Ok(true);
        }
        // br-edgekeyedbatch (bt): edges-only 4-tuple keyed batch for an edgeless graph
        // whose nodes already exist (MultiGraph subgraph().copy()). Bails to per-edge
        // if any endpoint is new. Only when there is no global **attr to merge.
        if global_attr.is_none_or(|attrs| attrs.is_empty())
            && self.try_add_keyed_attr_edges_existing_nodes_batch(py, ebunch_to_add)?
        {
            return Ok(true);
        }
        const ATTR_EDGE_BATCH_MIN: usize = 8;
        if self.inner.edge_count() != 0 || !self.adj_py_keys.is_empty() {
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

        let global_map: AttrMap = match global_attr {
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
            _ => AttrMap::new(),
        };
        let mut edges: Vec<(String, String, usize, AttrMap)> = Vec::with_capacity(items.len());
        // Lazy mirrors: only NON-EMPTY edge dicts materialize here, keyed by the
        // canonical (u, v, internal_key) exactly as per-edge `add_edge` stores them.
        let mut mirrors: Vec<((String, String, usize), Py<PyDict>)> = Vec::new();
        let mut new_nodes: Vec<(String, PyObject)> = Vec::new();
        let mut seen_nodes: HashSet<String> = self
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
            if !PyGraph::is_plain_batch_node(&u) || !PyGraph::is_plain_batch_node(&v) {
                return Ok(false);
            }
            // 3-tuple third element MUST be a dict (multigraph DATA). A non-dict
            // third is nx's "key" disambiguation path — bail to the per-edge loop.
            let (rust_attrs, src): (AttrMap, Option<Bound<'_, PyDict>>) = if tlen == 3 {
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
                (AttrMap::new(), None)
            } else {
                (global_map.clone(), None)
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
            // Canonical (undirected) pair for the sequential auto-key counter —
            // matches `EdgeKey::new` string ordering (same as the plain batch).
            let pair = if uc <= vc {
                (uc.clone(), vc.clone())
            } else {
                (vc.clone(), uc.clone())
            };
            let counter = pair_count.entry(pair).or_insert(0);
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
        let mirror_active = self.node_iter_mirror_active();
        for (canonical, node) in new_nodes {
            let mk = if mirror_active {
                Some(canonical.clone())
            } else {
                None
            };
            self.node_key_map.entry(canonical).or_insert(node);
            if let Some(c) = mk {
                let _ = self.node_iter_mirror_insert(py, &c);
            }
        }
        for (ek, dict) in mirrors {
            self.edge_py_attrs.entry(ek).or_insert(dict);
        }
        self.inner.extend_keyed_edges_with_attrs_unrecorded(edges);
        self.nodes_seq = self.nodes_seq.wrapping_add(node_bumps);
        self.edges_seq = self.edges_seq.wrapping_add(edge_bumps);
        Ok(true)
    }

    /// br-r37-c1-04z53.80: native batch for NetworkX-unambiguous
    /// `(int, int, str)` no-data edges on a FRESH MultiGraph. The Python
    /// wrapper only calls this for no-`**attr` list/tuple inputs; this method
    /// narrows further to list inputs, exact int endpoints, and exact
    /// NON-EMPTY string keys. Empty strings and dict-able third elements must
    /// fall back because `dict.update("")` succeeds in NetworkX's 3-tuple
    /// data-vs-key disambiguation. Duplicate public keys also fall back before
    /// mutation so the per-edge path owns first-wins merge semantics.
    fn _try_add_str_keyed_edges_from_batch(
        &mut self,
        py: Python<'_>,
        ebunch_to_add: &Bound<'_, PyAny>,
    ) -> PyResult<bool> {
        self.clear_stale_edge_mirrors();
        const STR_KEYED_EDGE_BATCH_MIN: usize = 8;
        if self.try_add_fresh_int_prefix_str_keyed_edges_from_batch(py, ebunch_to_add)? {
            return Ok(true);
        }
        if self.inner.edge_count() != 0 || !self.adj_py_keys.is_empty() {
            return Ok(false);
        }
        let Ok(list) = ebunch_to_add.downcast::<PyList>() else {
            return Ok(false);
        };
        if list.len() < STR_KEYED_EDGE_BATCH_MIN {
            return Ok(false);
        }

        let mut edges: Vec<(String, String, usize, AttrMap)> = Vec::with_capacity(list.len());
        let mut display_keys: Vec<(String, String, usize, PyObject)> =
            Vec::with_capacity(list.len());
        let mut new_nodes: Vec<(String, PyObject)> = Vec::new();
        let mut seen_nodes: HashSet<String> = self
            .inner
            .nodes_ordered()
            .into_iter()
            .map(str::to_owned)
            .collect();
        let mut batch_first: HashMap<String, PyObject> = HashMap::new();
        let mut pair_count: HashMap<(String, String), usize> = HashMap::new();
        let mut seen_edges: HashSet<(String, String, String)> = HashSet::new();
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
            if !u.is_exact_instance_of::<PyInt>() || !v.is_exact_instance_of::<PyInt>() {
                return Ok(false);
            }
            if !k.is_exact_instance_of::<PyString>() {
                return Ok(false);
            }
            let Ok(key_string) = k.downcast::<PyString>() else {
                return Ok(false);
            };
            let Ok(key_text) = key_string.to_str() else {
                return Ok(false);
            };
            if key_text.is_empty() {
                return Ok(false);
            }

            let uc = node_key_to_string(py, &u)?;
            let vc = node_key_to_string(py, &v)?;
            if self.batch_display_conflict(py, &uc, &u, &mut batch_first)
                || self.batch_display_conflict(py, &vc, &v, &mut batch_first)
            {
                return Ok(false);
            }

            let pair = if uc <= vc {
                (uc.clone(), vc.clone())
            } else {
                (vc.clone(), uc.clone())
            };
            let key_lookup = edge_key_lookup_string(py, &k)?;
            if !seen_edges.insert((pair.0.clone(), pair.1.clone(), key_lookup)) {
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
            let counter = pair_count.entry(pair).or_insert(0);
            let internal_key = *counter;
            *counter += 1;
            // br-r37-c1-mgkeyidentity (cc): a public key that is the EXACT non-negative
            // int equal to its internal auto-key needs NO edge_py_keys mirror entry —
            // display_key_lookup falls back to `int:{internal}` when the mirror is
            // absent, and note_public_key_value would not flag it remapped. So only
            // record NON-identity keys, skipping the per-edge String clones + edge_key
            // build + HashMap insert for the common auto-int-key case (read path is
            // byte-identical). bool/float/str/remapped-int keys are not exact PyInt (or
            // differ from internal_key), so they still mirror. Strict work removal on
            // the multigraph keyed-batch cluster (add_edges_from + set-algebra + union).
            let key_is_identity_int = k.is_exact_instance_of::<PyInt>()
                && k.extract::<i64>()
                    .ok()
                    .and_then(|i| usize::try_from(i).ok())
                    == Some(internal_key);
            if !key_is_identity_int {
                display_keys.push((uc.clone(), vc.clone(), internal_key, k.clone().unbind()));
            }
            edges.push((uc, vc, internal_key, AttrMap::new()));
        }

        let edge_bumps = u64::try_from(edges.len()).unwrap_or(u64::MAX);
        let mirror_active = self.node_iter_mirror_active();
        for (canonical, node) in new_nodes {
            let mk = if mirror_active {
                Some(canonical.clone())
            } else {
                None
            };
            self.node_key_map.entry(canonical).or_insert(node);
            if let Some(c) = mk {
                let _ = self.node_iter_mirror_insert(py, &c);
            }
        }
        self.inner.extend_keyed_edges_with_attrs_unrecorded(edges);
        for (u, v, key, obj) in display_keys {
            self.note_public_key_value(key, obj.bind(py));
            self.edge_py_keys
                .entry(Self::edge_key(&u, &v, key))
                .or_insert(obj);
        }
        self.nodes_seq = self.nodes_seq.wrapping_add(node_bumps);
        self.edges_seq = self.edges_seq.wrapping_add(edge_bumps);
        Ok(true)
    }

    fn try_add_fresh_int_prefix_str_keyed_edges_from_batch(
        &mut self,
        py: Python<'_>,
        ebunch_to_add: &Bound<'_, PyAny>,
    ) -> PyResult<bool> {
        const STR_KEYED_EDGE_BATCH_MIN: usize = 8;
        if self.inner.node_count() != 0
            || self.inner.edge_count() != 0
            || !self.adj_py_keys.is_empty()
        {
            return Ok(false);
        }
        let Ok(list) = ebunch_to_add.downcast::<PyList>() else {
            return Ok(false);
        };
        if list.len() < STR_KEYED_EDGE_BATCH_MIN {
            return Ok(false);
        }

        let mut edges: Vec<(usize, usize, usize)> = Vec::with_capacity(list.len());
        let mut display_keys: Vec<(usize, usize, usize, PyObject)> = Vec::with_capacity(list.len());
        let mut node_objects: Vec<PyObject> = Vec::new();
        let mut pair_first_display: HashMap<(usize, usize), usize> = HashMap::new();
        let mut pair_counts: HashMap<(usize, usize), usize> = HashMap::new();
        let mut repeated_pair_keys: HashMap<(usize, usize), HashSet<String>> = HashMap::new();

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
            if !u.is_exact_instance_of::<PyInt>() || !v.is_exact_instance_of::<PyInt>() {
                return Ok(false);
            }
            if !k.is_exact_instance_of::<PyString>() {
                return Ok(false);
            }
            let Ok(key_string) = k.downcast::<PyString>() else {
                return Ok(false);
            };
            let Ok(key_text) = key_string.to_str() else {
                return Ok(false);
            };
            if key_text.is_empty() {
                return Ok(false);
            }

            let Ok(left_raw) = u.extract::<i64>() else {
                return Ok(false);
            };
            let Ok(right_raw) = v.extract::<i64>() else {
                return Ok(false);
            };
            if left_raw < 0 || right_raw < 0 {
                return Ok(false);
            }
            let Ok(left_idx) = usize::try_from(left_raw) else {
                return Ok(false);
            };
            let Ok(right_idx) = usize::try_from(right_raw) else {
                return Ok(false);
            };

            for (idx, obj) in [(left_idx, &u), (right_idx, &v)] {
                if idx == node_objects.len() {
                    node_objects.push(obj.clone().unbind());
                } else if idx > node_objects.len() {
                    return Ok(false);
                }
            }

            let pair = if left_idx <= right_idx {
                (left_idx, right_idx)
            } else {
                (right_idx, left_idx)
            };
            let internal_key = if let Some(keys) = repeated_pair_keys.get_mut(&pair) {
                if !keys.insert(key_text.to_owned()) {
                    return Ok(false);
                }
                let counter = pair_counts
                    .get_mut(&pair)
                    .expect("repeated pair should have a counter");
                let key = *counter;
                *counter += 1;
                key
            } else if let Some(first_display) = pair_first_display.get(&pair).copied() {
                let first_key = display_keys[first_display]
                    .3
                    .bind(py)
                    .downcast::<PyString>()?
                    .to_str()?
                    .to_owned();
                let mut keys = HashSet::with_capacity(4);
                keys.insert(first_key);
                if !keys.insert(key_text.to_owned()) {
                    return Ok(false);
                }
                repeated_pair_keys.insert(pair, keys);
                pair_counts.insert(pair, 2);
                1
            } else {
                pair_first_display.insert(pair, display_keys.len());
                0
            };
            display_keys.push((left_idx, right_idx, internal_key, k.clone().unbind()));
            edges.push((left_idx, right_idx, internal_key));
        }

        let node_count = node_objects.len();
        let mirror_active = self.node_iter_mirror_active();
        for (idx, node) in node_objects.into_iter().enumerate() {
            let canonical = idx.to_string();
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
        let edge_bumps = u64::try_from(edges.len()).unwrap_or(u64::MAX);
        let _ = self
            .inner
            .extend_fresh_int_prefix_keyed_edges_unrecorded(node_count, edges);
        for (u, v, key, obj) in display_keys {
            let u = u.to_string();
            let v = v.to_string();
            self.note_public_key_value(key, obj.bind(py));
            self.edge_py_keys
                .entry(Self::edge_key(&u, &v, key))
                .or_insert(obj);
        }
        self.nodes_seq = self
            .nodes_seq
            .wrapping_add(u64::try_from(node_count).unwrap_or(u64::MAX));
        self.edges_seq = self.edges_seq.wrapping_add(edge_bumps);
        Ok(true)
    }

    /// br-r37-c1-urle5b: native batch for `(u, v, key)` no-data edges on a FRESH
    /// MultiGraph — the shape multigraph set-ops (difference / symmetric_difference
    /// / intersection) feed `R.add_edges_from(...)`. The caller GUARANTEES the
    /// third element is a real edge key (sourced from `G.edges(keys=True)`), so no
    /// nx data-vs-key disambiguation is attempted here. On a fresh graph the
    /// internal usize key is sequential per pair (0, 1, 2, …) — the DISPLAY key is
    /// the passed object, stored in `edge_py_keys` (filtering can leave gaps, so
    /// the display key need not equal the internal). One bulk
    /// `extend_keyed_edges_with_attrs_unrecorded`, lazy attr mirrors. Returns
    /// `false` (no mutation) for a non-fresh graph, present display objects, a
    /// non-3-tuple / non-plain node / unhashable key, or a hash-colliding
    /// duplicate `(u, v, key)` (which would need nx's first-wins merge).
    fn _native_add_keyed_edges_no_data(
        &mut self,
        py: Python<'_>,
        ebunch_to_add: &Bound<'_, PyAny>,
    ) -> PyResult<bool> {
        self.clear_stale_edge_mirrors();
        if self.inner.edge_count() != 0 || !self.adj_py_keys.is_empty() {
            return Ok(false);
        }
        let Ok(list) = ebunch_to_add.downcast::<PyList>() else {
            return Ok(false);
        };
        let mut edges: Vec<(String, String, usize, AttrMap)> = Vec::with_capacity(list.len());
        let mut display_keys: Vec<(String, String, usize, PyObject)> =
            Vec::with_capacity(list.len());
        let mut new_nodes: Vec<(String, PyObject)> = Vec::new();
        let mut seen_nodes: HashSet<String> = self
            .inner
            .nodes_ordered()
            .into_iter()
            .map(str::to_owned)
            .collect();
        let mut batch_first: HashMap<String, PyObject> = HashMap::new();
        let mut pair_count: HashMap<(String, String), usize> = HashMap::new();
        let mut seen_edges: HashSet<(String, String, String)> = HashSet::new();
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
            if !PyGraph::is_plain_batch_node(&u) || !PyGraph::is_plain_batch_node(&v) {
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
            // Canonical (undirected) pair for both the auto-key counter and the
            // duplicate guard — matches `EdgeKey::new` string ordering.
            let pair = if uc <= vc {
                (uc.clone(), vc.clone())
            } else {
                (vc.clone(), uc.clone())
            };
            let key_lookup = edge_key_lookup_string(py, &k)?;
            if !seen_edges.insert((pair.0.clone(), pair.1.clone(), key_lookup)) {
                return Ok(false); // hash-colliding duplicate → defer to nx merge
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
            let counter = pair_count.entry(pair).or_insert(0);
            let internal_key = *counter;
            *counter += 1;
            // br-r37-c1-mgkeyidentity (cc): a public key that is the EXACT non-negative
            // int equal to its internal auto-key needs NO edge_py_keys mirror entry —
            // display_key_lookup falls back to `int:{internal}` when the mirror is
            // absent, and note_public_key_value would not flag it remapped. So only
            // record NON-identity keys, skipping the per-edge String clones + edge_key
            // build + HashMap insert for the common auto-int-key case (read path is
            // byte-identical). bool/float/str/remapped-int keys are not exact PyInt (or
            // differ from internal_key), so they still mirror. Strict work removal on
            // the multigraph keyed-batch cluster (add_edges_from + set-algebra + union).
            let key_is_identity_int = k.is_exact_instance_of::<PyInt>()
                && k.extract::<i64>()
                    .ok()
                    .and_then(|i| usize::try_from(i).ok())
                    == Some(internal_key);
            if !key_is_identity_int {
                display_keys.push((uc.clone(), vc.clone(), internal_key, k.clone().unbind()));
            }
            edges.push((uc, vc, internal_key, AttrMap::new()));
        }

        let edge_bumps = u64::try_from(edges.len()).unwrap_or(u64::MAX);
        let mirror_active = self.node_iter_mirror_active();
        for (canonical, node) in new_nodes {
            let mk = if mirror_active {
                Some(canonical.clone())
            } else {
                None
            };
            self.node_key_map.entry(canonical).or_insert(node);
            if let Some(c) = mk {
                let _ = self.node_iter_mirror_insert(py, &c);
            }
        }
        self.inner.extend_keyed_edges_with_attrs_unrecorded(edges);
        for (u, v, key, obj) in display_keys {
            // br-r37-c1-urle5b: `py_edge_key` looks up the CANONICALIZED key
            // (u <= v for undirected) — store under the same form.
            self.note_public_key_value(key, obj.bind(py));
            self.edge_py_keys
                .entry(Self::edge_key(&u, &v, key))
                .or_insert(obj);
        }
        self.nodes_seq = self.nodes_seq.wrapping_add(node_bumps);
        self.edges_seq = self.edges_seq.wrapping_add(edge_bumps);
        Ok(true)
    }

    /// br-r37-c1-degnbnative (cc): native MultiGraph degree(nbunch) subset — one
    /// pass (canonical filter + multiplicity degree) vs the per-node native-degree
    /// + nbunch_iter Python path. nx sums keydict lengths in Python (O(deg)/node);
    /// fnx sums in rust, so it dominates. Unhashable -> TypeError(exact msg).
    fn _native_degree_pairs_subset(
        &self,
        py: Python<'_>,
        nbunch: &Bound<'_, PyAny>,
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
                out.push((node.clone().unbind(), self.inner.degree(&canonical)));
            }
        }
        Ok(out)
    }

    /// br-r37-c1-mgedgenb (cc): native MultiGraph edges(nbunch, data=False). The
    /// Python path triple-loops self.adj[source] (MultiAdjacencyView lambda chain,
    /// ~24ms/750 src) + a frozenset((u,v)) dedup per edge (~0.09x vs nx). This
    /// walks neighbors() (nx adj order) x edge_keys() once, dedups undirected
    /// parallels by a normalized (lo,hi,key) string-pair, and emits (u,v) or
    /// (u,v,key). Returns Ok(None) (Python fallback) for adj_py_keys row display,
    /// or for keys=true with a non-default edge_py_keys display mirror.
    /// br-r37-c1-selfloopmulti (cc): self-loop nodes in node-iteration order via a
    /// rust scan, replacing selfloop_edges' O(N) per-node `has_edge(n,n)` PyO3
    /// probe (the multigraph path was ~0.05x vs nx).
    fn _native_selfloop_nodes(&self, py: Python<'_>) -> Vec<PyObject> {
        self.inner
            .nodes_ordered()
            .iter()
            .filter(|n| self.inner.has_edge(n, n))
            .map(|n| self.py_node_key(py, n))
            .collect()
    }

    /// br-r37-c1-8egkh: full native MultiGraph self-loop edge emission.
    /// `_native_selfloop_nodes` removed the O(N) probe, but dense self-loop
    /// cases still paid `G[n]` / `nbrs[n]` Python row materialization per
    /// loop node. Emit the final NetworkX-shaped tuples directly in node/key
    /// order while preserving display keys and live attr-dict identity.
    #[pyo3(signature = (data, keys=false, default=None))]
    fn _native_selfloop_edges(
        &mut self,
        py: Python<'_>,
        data: &Bound<'_, PyAny>,
        keys: bool,
        default: Option<PyObject>,
    ) -> PyResult<Py<NodeIterator>> {
        let data_is_bool = data.is_instance_of::<PyBool>();
        let want_dict = data_is_bool && data.extract::<bool>()?;
        let want_value = !data_is_bool;
        let default_obj = default.unwrap_or_else(|| py.None());
        if want_dict && self.inner.edge_count() > 0 {
            self.mark_edges_dirty();
        }

        // br-r37-c1-eilce/selfloop (cc): clean scalar fast path for `data="<attr>"`.
        // If the edge mirror has not been dirtied, the Rust CgseValue store is
        // authoritative even when construction left pristine Python mirrors around.
        // Read scalar values directly; missing/custom/Map cases still route through
        // the mirror path below so arbitrary Python attribute objects and dict
        // identity remain NetworkX-shaped.
        let value_attr_name: Option<String> =
            if want_value && !self.edges_dirty.load(Ordering::Relaxed) {
                data.downcast::<PyString>()
                    .ok()
                    .map(|s| s.to_str().map(str::to_owned))
                    .transpose()?
            } else {
                None
            };
        let value_fast_path = value_attr_name.is_some();

        // Direct clean scalar self-loop emission for the hottest
        // `selfloop_edges(keys=True, data="<attr>")` path. With default display
        // keys and clean scalar attrs, the generic loop's intermediate
        // self-loop collection and per-edge mirror probe are pure overhead.
        if want_value && value_fast_path && keys && self.edge_py_keys.is_empty() {
            let attr_name = value_attr_name
                .as_deref()
                .expect("value fast path has an attribute name");
            let mut out: Vec<PyObject> = Vec::with_capacity(self.inner.edge_count());
            let nodes: Vec<String> = self
                .inner
                .nodes_ordered()
                .into_iter()
                .map(ToOwned::to_owned)
                .collect();
            for node in &nodes {
                let node = node.as_str();
                let Some(edge_keys) = self.inner.edge_keys(node, node) else {
                    continue;
                };
                if edge_keys.is_empty() {
                    continue;
                }
                let py_node = self.py_node_key(py, node);
                for key in edge_keys {
                    let val = match self
                        .inner
                        .edge_attrs(node, node, key)
                        .and_then(|attrs| attrs.get(attr_name))
                    {
                        Some(CgseValue::Map(_)) => {
                            let ek = Self::edge_key(node, node, key);
                            self.edge_data_value_or_default_with_key(
                                py,
                                node,
                                node,
                                key,
                                &ek,
                                data,
                                &default_obj,
                            )?
                        }
                        Some(value) => cgse_value_to_py(py, value)?,
                        None if self.edge_py_attrs.is_empty() => default_obj.clone_ref(py),
                        None => {
                            let ek = Self::edge_key(node, node, key);
                            self.edge_data_value_or_default_with_key(
                                py,
                                node,
                                node,
                                key,
                                &ek,
                                data,
                                &default_obj,
                            )?
                        }
                    };
                    let key_obj = unwrap_infallible(key.into_pyobject(py)).into_any().unbind();
                    out.push(
                        PyTuple::new(
                            py,
                            &[py_node.clone_ref(py), py_node.clone_ref(py), key_obj, val],
                        )?
                        .into_any()
                        .unbind(),
                    );
                }
            }
            return Py::new(py, NodeIterator::unguarded(out));
        }

        // br-r37-c1-selfloopnodecollect (cc): collect (selfloop node, its keys) in
        // ONE pass via edge_keys(n, n) -- which is BOTH the self-loop test (None for
        // non-loop nodes) AND the keys we need in the loop. The old path did a
        // separate has_edge(n, n) scan over all nodes (redundant edge_pair_key +
        // edges.get per node) THEN re-fetched edge_keys per loop node. Node order +
        // owned collection (released self.inner borrow before the &mut want_dict
        // path) are preserved.
        let selfloops: Vec<(String, Vec<usize>)> = self
            .inner
            .nodes_ordered()
            .iter()
            .filter_map(|node| {
                let keys = self.inner.edge_keys(node, node)?;
                if keys.is_empty() {
                    None
                } else {
                    Some(((*node).to_owned(), keys))
                }
            })
            .collect();
        let mut out: Vec<PyObject> = Vec::with_capacity(self.inner.number_of_selfloops());
        for (node, edge_keys) in &selfloops {
            let node = node.as_str();
            let py_node = self.py_node_key(py, node);
            for &key in edge_keys {
                let needs_lookup_key = want_dict
                    || (want_value && !value_fast_path)
                    || (keys && !self.edge_py_keys.is_empty());
                let lookup_key = if needs_lookup_key {
                    Some(Self::edge_key(node, node, key))
                } else {
                    None
                };
                let py_source = py_node.clone_ref(py);
                let py_target = py_node.clone_ref(py);
                let key_obj = if keys {
                    Some(if self.edge_py_keys.is_empty() {
                        unwrap_infallible(key.into_pyobject(py)).into_any().unbind()
                    } else {
                        self.edge_py_keys
                            .get(
                                lookup_key
                                    .as_ref()
                                    .expect("lookup key exists for display keys"),
                            )
                            .map_or_else(
                                || unwrap_infallible(key.into_pyobject(py)).into_any().unbind(),
                                |obj| obj.clone_ref(py),
                            )
                    })
                } else {
                    None
                };
                if want_dict {
                    let attrs = self
                        .ensure_edge_py_attrs_with_key(
                            py,
                            node,
                            node,
                            key,
                            lookup_key
                                .as_ref()
                                .expect("lookup key exists for edge data"),
                        )
                        .clone_ref(py)
                        .into_any();
                    if let Some(key_obj) = key_obj {
                        out.push(
                            PyTuple::new(py, &[py_source, py_target, key_obj, attrs])?
                                .into_any()
                                .unbind(),
                        );
                    } else {
                        out.push(
                            PyTuple::new(py, &[py_source, py_target, attrs])?
                                .into_any()
                                .unbind(),
                        );
                    }
                } else if want_value {
                    let val = if let Some(attr_name) = value_attr_name.as_deref() {
                        // Pristine-mirror path: convert scalars directly from the store.
                        // A `Map` value falls back to the mirror to keep dict identity.
                        let converted = match self
                            .inner
                            .edge_attrs(node, node, key)
                            .and_then(|attrs| attrs.get(attr_name))
                        {
                            Some(CgseValue::Map(_)) => None,
                            Some(value) => Some(cgse_value_to_py(py, value)?),
                            None if self.edge_py_attrs.is_empty() => {
                                Some(default_obj.clone_ref(py))
                            }
                            None => None,
                        };
                        match converted {
                            Some(value) => value,
                            None => {
                                let ek = Self::edge_key(node, node, key);
                                self.edge_data_value_or_default_with_key(
                                    py,
                                    node,
                                    node,
                                    key,
                                    &ek,
                                    data,
                                    &default_obj,
                                )?
                            }
                        }
                    } else {
                        self.edge_data_value_or_default_with_key(
                            py,
                            node,
                            node,
                            key,
                            lookup_key
                                .as_ref()
                                .expect("lookup key exists for edge data"),
                            data,
                            &default_obj,
                        )?
                    };
                    if let Some(key_obj) = key_obj {
                        out.push(
                            PyTuple::new(py, &[py_source, py_target, key_obj, val])?
                                .into_any()
                                .unbind(),
                        );
                    } else {
                        out.push(
                            PyTuple::new(py, &[py_source, py_target, val])?
                                .into_any()
                                .unbind(),
                        );
                    }
                } else if let Some(key_obj) = key_obj {
                    out.push(
                        PyTuple::new(py, &[py_source, py_target, key_obj])?
                            .into_any()
                            .unbind(),
                    );
                } else {
                    out.push(
                        PyTuple::new(py, &[py_source, py_target])?
                            .into_any()
                            .unbind(),
                    );
                }
            }
        }
        Py::new(py, NodeIterator::unguarded(out))
    }

    fn _native_mg_edges_nbunch_no_data(
        &self,
        py: Python<'_>,
        nbunch: &Bound<'_, PyAny>,
        keys: bool,
    ) -> PyResult<Option<Vec<PyObject>>> {
        // br-r37-c1-mgedgenbkeys (cc): keys=True no longer gates on edge_py_keys —
        // emit the DISPLAY key via the mirror-aware py_edge_key (default int when no
        // mirror). The old gate sent keys=True to the Python adj-chain (~0.09x) for
        // every MultiGraph that carries an edge_py_keys mirror.
        if !self.adj_py_keys.is_empty() {
            return Ok(None);
        }
        let mut out: Vec<PyObject> = Vec::new();
        let mut seen: std::collections::HashSet<(String, String, usize)> =
            std::collections::HashSet::new();
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
            let Some(neighbors) = self.inner.neighbors(&canonical) else {
                continue;
            };
            for nbr in neighbors {
                let (lo, hi) = if canonical.as_str() <= nbr {
                    (canonical.as_str(), nbr)
                } else {
                    (nbr, canonical.as_str())
                };
                for key in self.inner.edge_keys(&canonical, nbr).unwrap_or_default() {
                    if !seen.insert((lo.to_owned(), hi.to_owned(), key)) {
                        continue;
                    }
                    let nbr_obj = self.py_node_key(py, nbr);
                    if keys {
                        let key_obj = if self.edge_py_keys.is_empty() {
                            crate::unwrap_infallible(key.into_pyobject(py))
                                .into_any()
                                .unbind()
                        } else {
                            self.py_edge_key(py, &canonical, nbr, key)
                        };
                        out.push(
                            PyTuple::new(py, &[node.clone().unbind(), nbr_obj, key_obj])?
                                .into_any()
                                .unbind(),
                        );
                    } else {
                        out.push(
                            PyTuple::new(py, &[node.clone().unbind(), nbr_obj])?
                                .into_any()
                                .unbind(),
                        );
                    }
                }
            }
        }
        Ok(Some(out))
    }

    /// br-r37-c1-mgedgenb (cc): data=True sibling of _native_mg_edges_nbunch_no_data.
    /// Emits (u, v[, key], live_attr_dict) — the attr dict is the materialized live
    /// edge_py_attrs mirror (identity-preserving, == G[u][v][key], matching nx).
    /// neighbors/keys are collected as owned Vecs first so the &mut ensure call has
    /// no live inner borrow. Same adj_py_keys / edge_py_keys display gate.
    fn _native_mg_edges_nbunch_data(
        &mut self,
        py: Python<'_>,
        nbunch: &Bound<'_, PyAny>,
        keys: bool,
    ) -> PyResult<Option<Vec<PyObject>>> {
        // br-r37-c1-mgedgenbkeys (cc): keys=True no longer gates on edge_py_keys —
        // emit the DISPLAY key via the mirror-aware py_edge_key (default int when no
        // mirror). The old gate sent keys=True to the Python adj-chain (~0.09x) for
        // every MultiGraph that carries an edge_py_keys mirror.
        if !self.adj_py_keys.is_empty() {
            return Ok(None);
        }
        let mut out: Vec<PyObject> = Vec::new();
        // br-r37-c1-mgnbdedup (cc): dedup by processed nbunch SOURCE node (nx's exact
        // edges(nbunch) algorithm) instead of a per-edge canonical (String,String,usize)
        // seen-set — drops the per-edge (lo,hi) tuple clone + hash insert. A neighbor
        // already a processed source had the edge emitted from its side; matches nx
        // including duplicate-nbunch re-emission (the per-edge set diverged there).
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
            if seen_nodes.contains(canonical.as_str()) {
                continue; // duplicate nbunch node — already emitted as a source (nx dedups)
            }
            let neighbors: Vec<String> = match self.inner.neighbors(&canonical) {
                Some(v) => v.iter().map(|s| (*s).to_owned()).collect(),
                None => continue,
            };
            for nbr in &neighbors {
                if seen_nodes.contains(nbr.as_str()) {
                    continue;
                }
                let keys_vec: Vec<usize> =
                    self.inner.edge_keys(&canonical, nbr).unwrap_or_default();
                for key in keys_vec {
                    let nbr_obj = self.py_node_key(py, nbr);
                    let attrs = self
                        .ensure_edge_py_attrs(py, &canonical, nbr, key)
                        .clone_ref(py)
                        .into_any();
                    if keys {
                        let key_obj = if self.edge_py_keys.is_empty() {
                            crate::unwrap_infallible(key.into_pyobject(py))
                                .into_any()
                                .unbind()
                        } else {
                            self.py_edge_key(py, &canonical, nbr, key)
                        };
                        out.push(
                            PyTuple::new(py, &[node.clone().unbind(), nbr_obj, key_obj, attrs])?
                                .into_any()
                                .unbind(),
                        );
                    } else {
                        out.push(
                            PyTuple::new(py, &[node.clone().unbind(), nbr_obj, attrs])?
                                .into_any()
                                .unbind(),
                        );
                    }
                }
            }
            seen_nodes.insert(canonical);
        }
        Ok(Some(out))
    }

    /// br-r37-c1-mgedgenbdk (cc): MultiGraph edges(nbunch, data=<key>) — value
    /// sibling of _native_mg_edges_nbunch_data. The data=key nbunch shape had no
    /// native and fell to the Python adj-chain (~0.11x). Projects
    /// attrs.get(data, default) per edge (via edge_data_value_or_default_with_key).
    fn _native_mg_edges_nbunch_data_key(
        &mut self,
        py: Python<'_>,
        nbunch: &Bound<'_, PyAny>,
        data: &Bound<'_, PyAny>,
        default: PyObject,
        keys: bool,
    ) -> PyResult<Option<Vec<PyObject>>> {
        if !self.adj_py_keys.is_empty() {
            return Ok(None);
        }
        // br-r37-c1-mgedgesnbattr (cc): pristine store-read fast path (sibling of the
        // out/in_edges nbunch data_key wins) -- read the attr from the store instead
        // of edge_data_value_or_default_with_key's edge_key build + mirror probe.
        let pristine = self.edge_py_attrs.is_empty();
        let attr_name: Option<String> = if pristine {
            data.extract::<String>().ok()
        } else {
            None
        };
        let mut out: Vec<PyObject> = Vec::new();
        // br-r37-c1-mgnbdedup (cc): dedup by processed nbunch SOURCE node (nx's exact
        // algorithm), replacing the per-edge canonical seen-set. See
        // _native_mg_edges_nbunch_data for the rationale + correctness notes.
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
            if seen_nodes.contains(canonical.as_str()) {
                continue; // duplicate nbunch node — already emitted as a source (nx dedups)
            }
            let neighbors: Vec<String> = match self.inner.neighbors(&canonical) {
                Some(v) => v.iter().map(|s| (*s).to_owned()).collect(),
                None => continue,
            };
            for nbr in &neighbors {
                if seen_nodes.contains(nbr.as_str()) {
                    continue;
                }
                let keys_vec: Vec<usize> =
                    self.inner.edge_keys(&canonical, nbr).unwrap_or_default();
                for key in keys_vec {
                    let nbr_obj = self.py_node_key(py, nbr);
                    let value = if let Some(an) = attr_name.as_deref() {
                        match self
                            .inner
                            .edge_attrs(&canonical, nbr, key)
                            .and_then(|a| a.get(an))
                        {
                            Some(v) => cgse_value_to_py(py, v)?,
                            None => default.clone_ref(py),
                        }
                    } else {
                        let ek = Self::edge_key(&canonical, nbr, key);
                        self.edge_data_value_or_default_with_key(
                            py, &canonical, nbr, key, &ek, data, &default,
                        )?
                    };
                    if keys {
                        let key_obj = if self.edge_py_keys.is_empty() {
                            crate::unwrap_infallible(key.into_pyobject(py))
                                .into_any()
                                .unbind()
                        } else {
                            self.py_edge_key(py, &canonical, nbr, key)
                        };
                        out.push(
                            PyTuple::new(py, &[node.clone().unbind(), nbr_obj, key_obj, value])?
                                .into_any()
                                .unbind(),
                        );
                    } else {
                        out.push(
                            PyTuple::new(py, &[node.clone().unbind(), nbr_obj, value])?
                                .into_any()
                                .unbind(),
                        );
                    }
                }
            }
            seen_nodes.insert(canonical);
        }
        Ok(Some(out))
    }

    /// br-r37-c1-mgdju (cc): native MultiGraph disjoint_union — undirected keyed
    /// analog of PyDiGraph/PyMultiDiGraph::_native_disjoint_union. Relabels both
    /// parts to fresh int ranges (so source node + adj_py_keys row display are
    /// discarded — no gating), walks neighbors with symmetric dedup (each
    /// undirected edge once, via canonical edge_key), PRESERVES each edge's inner
    /// key + DISPLAY key (edge_py_keys mirror; nx preserves keys) and attrs.
    fn _native_disjoint_union(&self, py: Python<'_>, other: PyRef<'_, Self>) -> PyResult<Py<Self>> {
        let mut g = Self::new_empty_with_mode(py, self.inner.mode())?;
        let merged_graph_attrs = PyDict::new(py);
        merged_graph_attrs.update(self.graph_attrs.bind(py).as_mapping())?;
        merged_graph_attrs.update(other.graph_attrs.bind(py).as_mapping())?;
        g.graph_attrs = merged_graph_attrs.unbind();
        let n1 = self.inner.node_count();
        let mut total_edges = 0usize;
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
            let mut display: Vec<(String, String, usize, PyObject)> = Vec::new();
            let mut seen: HashSet<(String, String, usize)> = HashSet::new();
            for u in &nodes {
                for v in part.inner.neighbors(u).unwrap_or_default() {
                    let vk = v.to_owned();
                    for key in part.inner.edge_keys(u, &vk).unwrap_or_default() {
                        if !seen.insert(Self::edge_key(u, &vk, key)) {
                            continue; // each undirected edge once
                        }
                        let uc = index_of[u.as_str()].to_string();
                        let vc = index_of[vk.as_str()].to_string();
                        let dst_ek = Self::edge_key(&uc, &vc, key);
                        let src_ek = Self::edge_key(u, &vk, key);
                        if let Some(attrs) = part.edge_py_attrs.get(&src_ek) {
                            g.edge_py_attrs
                                .insert(dst_ek.clone(), attrs.bind(py).copy()?.unbind());
                        }
                        display.push((
                            uc.clone(),
                            vc.clone(),
                            key,
                            part.py_edge_key(py, u, &vk, key),
                        ));
                        edge_batch.push((
                            uc,
                            vc,
                            key,
                            part.inner
                                .edge_attrs(u, &vk, key)
                                .cloned()
                                .unwrap_or_default(),
                        ));
                    }
                }
            }
            total_edges += edge_batch.len();
            let _ = g.inner.extend_keyed_edges_with_attrs_unrecorded(edge_batch);
            for (u, v, key, obj) in display {
                g.note_public_key_value(key, obj.bind(py));
                g.edge_py_keys
                    .entry(Self::edge_key(&u, &v, key))
                    .or_insert(obj);
            }
        }
        g.nodes_seq = u64::try_from(n1 + other.inner.node_count()).unwrap_or(u64::MAX);
        g.edges_seq = u64::try_from(total_edges).unwrap_or(u64::MAX);
        Py::new(py, g)
    }

    /// br-r37-c1-natdiff / cc-mgnatdiff-identity: fully-native `difference(G, H)`
    /// for MultiGraph (the undirected sibling of `PyMultiDiGraph::_native_difference`).
    /// FAST identity-int path only: when both operands are all-identity-int keyed
    /// (`!has_remapped_int_key`) and carry no z6uka adjacency-cell display overrides,
    /// a multigraph edge key value equals its internal key, so membership can be
    /// tested on INTERNAL `(u, v, key)` (no per-edge `display_key_lookup` String
    /// build) and G's exact keys are preserved on the result (no re-sequencing, no
    /// `edge_py_keys` mirror — `display_key_lookup` reconstructs `int:{internal}`).
    /// H's edges are hashed BOTH orientations (an undirected edge matches either
    /// way); G is walked in `edges(keys=True)` order (node-major, each undirected
    /// edge once via the canonical-bucket `seen` set). This eliminates the Python
    /// `set(*.edges(keys=True))` materialization the wrapper otherwise pays plus the
    /// mirror/display tax the old native path carried. Returns `None` (wrapper falls
    /// back to the proven set-snapshot path) when H is not an exact MultiGraph or
    /// either operand carries remapped/str/float keys or display overrides.
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
        if g.has_remapped_int_key
            || hh.has_remapped_int_key
            || !g.adj_py_keys.is_empty()
            || !hh.adj_py_keys.is_empty()
        {
            return Ok(None);
        }

        // H's edge set on INTERNAL keys (== display for identity-int), BOTH
        // orientations (an undirected edge matches in either direction).
        let mut h_set: HashSet<(String, String, usize)> = HashSet::new();
        for u in hh.inner.nodes_ordered() {
            for v in hh.inner.neighbors(u).unwrap_or_default() {
                for key in hh.inner.edge_keys(u, v).unwrap_or_default() {
                    h_set.insert((u.to_owned(), v.to_owned(), key));
                    h_set.insert((v.to_owned(), u.to_owned(), key));
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
            g_nodes.iter().map(|n| (n.clone(), AttrMap::new())),
        );

        let mut edges: Vec<(String, String, usize, AttrMap)> = Vec::new();
        let mut g_seen: HashSet<(String, String, usize)> = HashSet::new();
        for u in &g_nodes {
            for v in g.inner.neighbors(u).unwrap_or_default() {
                let vk = v.to_owned();
                for key in g.inner.edge_keys(u, &vk).unwrap_or_default() {
                    if !g_seen.insert(Self::edge_key(u, &vk, key)) {
                        continue;
                    }
                    if !h_set.contains(&(u.clone(), vk.clone(), key)) {
                        // Preserve G's exact key (identity-int -> byte-exact,
                        // incl. removed-noncontiguous buckets; no mirror needed).
                        edges.push((u.clone(), vk.clone(), key, AttrMap::new()));
                    }
                }
            }
        }
        let n_edges = edges.len();
        let _ = r.inner.extend_keyed_edges_with_attrs_unrecorded(edges);
        r.nodes_seq = u64::try_from(g_nodes.len()).unwrap_or(u64::MAX);
        r.edges_seq = u64::try_from(n_edges).unwrap_or(u64::MAX);
        Py::new(py, r).map(Some)
    }

    /// br-r37-c1-y0xps / cc-mgnatsymdiff-identity: fully-native
    /// `symmetric_difference(G, H)` for MultiGraph — the two-sided sibling of
    /// `_native_difference`. FAST identity-int path only (both operands
    /// `!has_remapped_int_key`, no z6uka display overrides): membership is tested
    /// on INTERNAL `(u, v, key)` (== display for identity-int, no per-edge
    /// `display_key_lookup`), and each operand's own keys are PRESERVED on the
    /// result — NOT re-sequenced. Re-sequencing (the old dead-code path) diverged
    /// from NetworkX whenever a pair had non-contiguous kept keys (e.g. G keys
    /// {0,1} minus H {0} must yield key 1, not a re-keyed 0). G-only edges are
    /// emitted first, then H-only, matching the wrapper's two comprehensions; the
    /// two key sets for any pair are disjoint (a key present in both graphs is in
    /// neither pass), so no bucket collision. No `edge_py_keys` mirror is built
    /// (identity-int -> `display_key_lookup` reconstructs `int:{internal}`).
    /// Returns `None` (wrapper falls back) for non-MultiGraph H or
    /// remapped/str/float keys / display overrides.
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
        if g.has_remapped_int_key
            || hh.has_remapped_int_key
            || !g.adj_py_keys.is_empty()
            || !hh.adj_py_keys.is_empty()
        {
            return Ok(None);
        }

        // Internal-key membership sets, BOTH orientations (undirected).
        let mut h_set: HashSet<(String, String, usize)> = HashSet::new();
        for u in hh.inner.nodes_ordered() {
            for v in hh.inner.neighbors(u).unwrap_or_default() {
                for key in hh.inner.edge_keys(u, v).unwrap_or_default() {
                    h_set.insert((u.to_owned(), v.to_owned(), key));
                    h_set.insert((v.to_owned(), u.to_owned(), key));
                }
            }
        }
        let mut g_set: HashSet<(String, String, usize)> = HashSet::new();
        for u in g.inner.nodes_ordered() {
            for v in g.inner.neighbors(u).unwrap_or_default() {
                for key in g.inner.edge_keys(u, v).unwrap_or_default() {
                    g_set.insert((u.to_owned(), v.to_owned(), key));
                    g_set.insert((v.to_owned(), u.to_owned(), key));
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
            g_nodes.iter().map(|n| (n.clone(), AttrMap::new())),
        );

        let mut edges: Vec<(String, String, usize, AttrMap)> = Vec::new();

        // G-only edges (preserve G's keys).
        let mut g_seen: HashSet<(String, String, usize)> = HashSet::new();
        for u in &g_nodes {
            for v in g.inner.neighbors(u).unwrap_or_default() {
                let vk = v.to_owned();
                for key in g.inner.edge_keys(u, &vk).unwrap_or_default() {
                    if !g_seen.insert(Self::edge_key(u, &vk, key)) {
                        continue;
                    }
                    if !h_set.contains(&(u.clone(), vk.clone(), key)) {
                        edges.push((u.clone(), vk.clone(), key, AttrMap::new()));
                    }
                }
            }
        }

        // H-only edges (preserve H's keys).
        let h_nodes: Vec<String> = hh
            .inner
            .nodes_ordered()
            .into_iter()
            .map(str::to_owned)
            .collect();
        let mut h_seen_for_emit: HashSet<(String, String, usize)> = HashSet::new();
        for u in &h_nodes {
            for v in hh.inner.neighbors(u).unwrap_or_default() {
                let vk = v.to_owned();
                for key in hh.inner.edge_keys(u, &vk).unwrap_or_default() {
                    if !h_seen_for_emit.insert(Self::edge_key(u, &vk, key)) {
                        continue;
                    }
                    if !g_set.contains(&(u.clone(), vk.clone(), key)) {
                        edges.push((u.clone(), vk.clone(), key, AttrMap::new()));
                    }
                }
            }
        }

        let n_edges = edges.len();
        let _ = r.inner.extend_keyed_edges_with_attrs_unrecorded(edges);
        r.nodes_seq = u64::try_from(g_nodes.len()).unwrap_or(u64::MAX);
        r.edges_seq = u64::try_from(n_edges).unwrap_or(u64::MAX);
        Py::new(py, r).map(Some)
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

        let u_was_new = !self.node_key_map.contains_key(&u_canonical);
        let v_was_new = !self.node_key_map.contains_key(&v_canonical);
        let was_new_node = u_was_new || v_was_new;
        self.node_key_map
            .entry(u_canonical.clone())
            .or_insert_with(|| u.clone().unbind());
        self.node_key_map
            .entry(v_canonical.clone())
            .or_insert_with(|| v.clone().unbind());
        if was_new_node {
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
        self.note_public_key_value(actual_key, key);
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
        // br-r37-c1-rmedge-oE (cc): capture the pair's INTERNAL bucket keys
        // BEFORE removal so the pair-empty purge below can drop the exact
        // mirror slots in O(bucket) instead of the O(|E|) scan over the whole
        // edge_py_attrs/edge_py_keys maps. Only needed when a mirror exists and
        // keys are identity-int (the common weighted add_edges_from case, where
        // the mirror is keyed by the internal bucket key). Under key remapping
        // the mirror can live under a public key not in the bucket, so that
        // path keeps the exhaustive retain (see below).
        let bucket_keys_before: Option<Vec<usize>> = if !self.has_remapped_int_key
            && (!self.edge_py_attrs.is_empty() || !self.edge_py_keys.is_empty())
        {
            self.inner.edge_keys(&u_canonical, &v_canonical)
        } else {
            None
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
            //
            // br-r37-c1-rmedge-oE (cc): the retain is O(|E|) over the WHOLE
            // mirror and fired on EVERY pair-emptying removal — the dominant
            // cost of weighted-MultiGraph remove_edges_from (O(k*|E|); MG
            // weighted removal was 0.002x at scale). When keys are identity-int
            // (!has_remapped_int_key) the mirror is keyed by exactly the
            // internal bucket keys, so purging the captured bucket keys +
            // removed_key drops every entry for the pair in O(bucket). Only the
            // remapped case (mirror possibly under a public key not in the
            // bucket) still needs the exhaustive scan.
            if let Some(keys) = bucket_keys_before {
                for k in keys {
                    self.remove_edge_metadata(&u_canonical, &v_canonical, k);
                }
            } else {
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
        self.edge_mirrors_stale = false;
        self.graph_attrs = PyDict::new(py).unbind();
        // Clear the live mirror in place so an in-flight iter raises like nx.
        self.node_iter_mirror_clear(py)?;
        self.bump_nodes_seq();
        self.bump_edges_seq(); // br-r37-c1-jft0i
        Ok(())
    }

    fn clear_edges(&mut self) {
        self.inner.clear_edges();
        if !self.edge_py_attrs.is_empty() || !self.edge_py_keys.is_empty() {
            self.edge_mirrors_stale = true;
        }
        self.adj_py_keys.clear(); // br-r37-c1-z6uka
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

    /// br-cc-nbunchbulk: bulk nbunch filter — see PyGraph::_nbunch_present.
    fn _nbunch_present(
        &self,
        py: Python<'_>,
        nbunch: &Bound<'_, PyAny>,
    ) -> PyResult<Option<Vec<PyObject>>> {
        let mut out: Vec<PyObject> = Vec::new();
        for item in nbunch.try_iter()? {
            let item = item?;
            if item.hash().is_err() {
                return Ok(None);
            }
            if item.is_exact_instance_of::<PyInt>()
                && let Ok(i) = item.extract::<usize>()
                && self.inner.node_index_matches_int(i)
            {
                out.push(item.clone().unbind());
                continue;
            }
            let canonical = node_key_to_string(py, &item)?;
            if self.inner.has_node(&canonical) {
                out.push(item.clone().unbind());
            }
        }
        Ok(Some(out))
    }

    fn __iter__(slf: PyRef<'_, Self>) -> PyResult<PyObject> {
        // Serve iteration from the live node_iter_mirror dict_keyiterator
        // (matching nx) instead of rebuilding a Vec<PyObject> per call.
        let py = slf.py();
        let mirror = slf.node_iter_mirror_or_init(py)?;
        Ok(mirror.bind(py).call_method0("__iter__")?.unbind())
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

    /// br-r37-c1-snabulk-dict (cc): native bulk set_node_attributes(values) for
    /// the DICT-OF-DICTS form ({node: {attr: val, ...}}, no name). The Python
    /// wrapper otherwise loops `G.nodes[node].update(d)` — a NodeView
    /// __getitem__ PyO3 round-trip per node (~0.27x vs nx's plain dict update).
    /// One Rust pass; node_py_attrs is the authoritative store, so entry() keeps
    /// any existing attrs and `.update(d)` merges (no store/mirror split like
    /// edges). Missing nodes skipped (matching the wrapper's has_node gate).
    fn _native_set_node_attributes_dict(
        &mut self,
        py: Python<'_>,
        values: &Bound<'_, PyDict>,
    ) -> PyResult<()> {
        for (k, attrs) in values.iter() {
            let canonical = node_key_to_string(py, &k)?;
            if self.inner.has_node(&canonical) {
                let dict = self
                    .node_py_attrs
                    .entry(canonical)
                    .or_insert_with(|| PyDict::new(py).unbind());
                dict.bind(py).call_method1("update", (&attrs,))?;
            }
        }
        Ok(())
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
            for neighbor in g.inner.neighbors(node).unwrap_or_default() {
                let py_neighbor = g.py_adj_key(py, node, neighbor);
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
        self.adjacency_dict_cached(py)
    }

    /// br-r37-c1-adjshare: cached form of `adjacency` — serve the nested
    /// {node: {nbr: {key: edge_dict}}} snapshot from the (nodes_seq, edges_seq)-
    /// keyed `dict_of_dicts_cache` with SHARED rows (no per-row copy). nx's
    /// adjacency() hands out the live `_adj[node]` rows, so two calls yield the
    /// SAME row object (`r1[u] is r2[u]`); sharing matches that AND drops the
    /// O(V+E) per-call copy (was ~9x slower than nx). Deepest edge dicts stay the
    /// live `G[u][v][k]`; only adjacency() uses this (to_dict_of_dicts has its own
    /// copying view path), so sharing is safe.
    pub(crate) fn adjacency_dict_cached(&mut self, py: Python<'_>) -> PyResult<Py<PyDict>> {
        // adjacency() hands out live edge attr dicts; preserve the dirty flag on
        // every call (it only flips an AtomicBool — does NOT bump edges_seq, so
        // it never invalidates this cache).
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
            let neighbors: Vec<String> = self
                .inner
                .neighbors(node)
                .unwrap_or_default()
                .into_iter()
                .map(str::to_owned)
                .collect();
            for neighbor in &neighbors {
                let py_nbr = self.py_adj_key(py, node, neighbor);
                nbrs_dict.set_item(&py_nbr, self.neighbor_dict(py, node, neighbor)?.bind(py))?;
            }
            rows.push((py_node, nbrs_dict.unbind()));
        }
        self.dict_of_dicts_cache = Some(DictOfDictsCache {
            nodes_seq: self.nodes_seq,
            edges_seq: self.edges_seq,
            rows,
            shared_outer: std::sync::Mutex::new(None),
        });
        Ok(())
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
        if keys && !want_dict && !want_value {
            return self.edges_key_tuples(py);
        }
        // br-r37-c1-o07ax: the data=True, keys=False variant (the common
        // edges(data=True)) yields (u, v, live_attr) immutable tuples — cache
        // them keyed on (nodes_seq, edges_seq) and return a fresh list of the
        // same tuple objects on repeats. Other variants (keys, data=<key>,
        // data=False) are NOT cached (value/key tuples differ).
        // br-r37-c1-mgkd (cc): cache BOTH the data-only and the keys+data variant
        // in the single slot, discriminated by a `keys` flag, so
        // edges(keys=True, data=True) stops rebuilding on every call (was 0.5x vs
        // nx; the partial variants' wins were warm cache-hit artifacts). Mixed
        // data-only / keys+data calls on the SAME MultiGraph (rare) thrash the
        // slot but stay correct (seq+flag mismatch → rebuild).
        let cacheable = want_dict;
        if cacheable
            && matches!(
                &self.edges_with_data_cache,
                Some((ns, es, kf, _))
                    if *ns == self.nodes_seq && *es == self.edges_seq && *kf == keys
            )
        {
            let cached = &self.edges_with_data_cache.as_ref().unwrap().3;
            return Ok(cached.iter().map(|t| t.clone_ref(py)).collect());
        }
        // br-inedges-attrcache (bt): whole-graph edges(data=<attr>) scalar snapshot
        // cache. Only a string attr on a clean graph is cacheable; served while
        // seqs/keys/attr/default match, dropped on the next mark_edges_dirty. nx
        // rebuilds its MultiEdgeDataView every call -> repeats clone refs.
        let cacheable_attr: Option<String> =
            if want_value && !self.edges_dirty.load(Ordering::Relaxed) {
                data.extract::<String>().ok()
            } else {
                None
            };
        if let Some(attr_name) = &cacheable_attr {
            let cache = self.edges_data_attr_cache.lock().unwrap();
            if let Some((ns, es, kf, cattr, cdef, ctuples)) = cache.as_ref()
                && *ns == self.nodes_seq
                && *es == self.edges_seq
                && *kf == keys
                && cattr == attr_name
                && cdef.bind(py).eq(default.bind(py))?
            {
                return Ok(ctuples.iter().map(|t| t.clone_ref(py)).collect());
            }
        }
        // br-r37-c1-mgedgededup (cc): dedup undirected edges by NODE (emit each edge
        // from the first-encountered endpoint) — nx's exact algorithm — instead of a
        // per-edge canonical (String,String,usize) seen-set. Drops the per-edge ek
        // clone + tuple-hash insert (O(E)) for an O(N) node-processed set; the raw ek
        // is now built only for the want_value mirror probe. Orientation
        // (current-node-first), node->neighbor->key order, and self-loop-once are all
        // unchanged: a self-loop's `node` is not yet in `processed`, and a neighbor
        // already processed (earlier in node order) had this edge emitted from its side.
        let mut processed: HashSet<String> = HashSet::new();
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
                if processed.contains(neighbor.as_str()) {
                    continue;
                }
                let edge_keys = self.inner.edge_keys(node, neighbor).unwrap_or_default();
                for key in edge_keys {
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
                        let ek = Self::edge_key(node, neighbor, key);
                        let val = match self.edge_py_attrs.get(&ek) {
                            Some(d) => d
                                .bind(py)
                                .get_item(data)
                                .ok()
                                .flatten()
                                .map_or_else(|| default.clone_ref(py), |v| v.unbind()),
                            None => data.extract::<String>().map_or_else(
                                |_| Ok(default.clone_ref(py)),
                                |attr| {
                                    self.edge_attr_py_value(py, node, neighbor, key, &attr)
                                        .map(|value| value.unwrap_or_else(|| default.clone_ref(py)))
                                },
                            )?,
                        };
                        elems.push(val);
                    }
                    result.push(PyTuple::new(py, &elems)?.into_any().unbind());
                }
            }
            processed.insert(node.clone());
        }
        if cacheable {
            let cached: Vec<PyObject> = result.iter().map(|t| t.clone_ref(py)).collect();
            self.edges_with_data_cache = Some((self.nodes_seq, self.edges_seq, keys, cached));
        }
        if let Some(attr_name) = cacheable_attr {
            // br-inedges-attrcache (bt): snapshot scalar tuples (clean here),
            // dropped on the next attr mutation via mark_edges_dirty.
            let snapshot: Vec<PyObject> = result.iter().map(|t| t.clone_ref(py)).collect();
            *self.edges_data_attr_cache.lock().unwrap() = Some((
                self.nodes_seq,
                self.edges_seq,
                keys,
                attr_name,
                default.clone_ref(py),
                snapshot,
            ));
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
    /// br-r37-c1-mgwdegfs (cc): all-int weighted total degree of one node read
    /// straight from the native CgseValue store (zero PyO3). nx's undirected
    /// MultiDegreeView sums every incident edge's weight once and adds a
    /// self-loop's weight a SECOND time, so accumulate the self-loop weights into
    /// a separate bucket and add it back. Integer addition is associative, so the
    /// store iteration order need not match nx's adjacency order — only the
    /// multiset of contributing weights does (each neighbor edge once, each
    /// self-loop edge twice). `None` (-> exact fallback) on any non-int value so
    /// missing-default-1, float, and mixed weights stay byte-exact. Edgeless node
    /// returns Some(0) = nx's int 0. CALLER gates on `!edges_dirty`.
    fn weighted_degree_store_int_node(&self, node: &str, weight: &str) -> Option<i128> {
        let mut total = 0i128;
        let mut selfloop_extra = 0i128;
        if let Some(neighbors) = self.inner.neighbors_iter(node) {
            for neighbor in neighbors {
                let is_self = neighbor == node;
                // Integer addition is associative, so order is irrelevant; iterate
                // the pair's AttrMaps directly (one bucket lookup) rather than a
                // per-key hash lookup per parallel edge.
                for attrs in self.inner.edge_attr_values(node, neighbor)? {
                    let value = match attrs.get(weight) {
                        Some(CgseValue::Int(v)) => i128::from(*v),
                        Some(_) => return None,
                        None => 1,
                    };
                    total = total.checked_add(value)?;
                    if is_self {
                        selfloop_extra = selfloop_extra.checked_add(value)?;
                    }
                }
            }
        }
        total.checked_add(selfloop_extra)
    }

    /// All-node int weighted total degree from the store, gated on a clean graph
    /// (no pending mirror edits -> store authoritative). Bails to None on the
    /// first non-int node so the float/PyList fallbacks handle float/mixed graphs.
    fn native_weighted_total_degree_store_int(
        &self,
        py: Python<'_>,
        weight: &str,
    ) -> PyResult<Option<Vec<(PyObject, PyObject)>>> {
        if self.edges_dirty.load(Ordering::Relaxed) {
            return Ok(None);
        }
        let mut out: Vec<(PyObject, PyObject)> = Vec::with_capacity(self.inner.node_count());
        for node in self.inner.nodes_ordered() {
            let Some(total) = self.weighted_degree_store_int_node(node, weight) else {
                return Ok(None);
            };
            let Ok(total_i64) = i64::try_from(total) else {
                return Ok(None);
            };
            out.push((self.py_node_key(py, node), total_i64.into_py_any(py)?));
        }
        Ok(Some(out))
    }

    /// br-r37-c1-wsize (cc): native scalar `size(weight)` for the integer/clean
    /// case. The Python `size` wrapper routes weighted size through
    /// `sum(d for _, d in self.degree(weight))/2`, which materialises N
    /// `(node, PyFloat)` degree pairs only to reduce them to one number. When the
    /// graph is clean (store authoritative) and every weight is an integer, sum
    /// the CgseValue store once and return the scalar directly — no per-node
    /// PyObject. Returns `None` (Python falls back to the exact degree path) on a
    /// dirty mirror or any non-integer weight. Byte-identical to nx's
    /// `sum(int degrees)/2`: integer degree sums are exact (`2 * size`), and
    /// `(2*size)/2` rounds to the same f64 as `size as f64`.
    fn _weighted_size_fast(&self, weight: &str) -> Option<f64> {
        if self.edges_dirty.load(Ordering::Relaxed) {
            return None;
        }
        self.inner.weighted_size_int(weight).map(|t| t as f64)
    }

    fn _native_weighted_degree(
        &self,
        py: Python<'_>,
        weight: &str,
    ) -> PyResult<Vec<(PyObject, PyObject)>> {
        // br-r37-c1-mgwdegfs (cc): Rust-store int path first (zero per-edge PyO3
        // on a clean graph), before the float Neumaier path and the PyList+sum
        // fallback. The store accumulator is the int analog of the MultiDiGraph
        // path; integer sums are order-independent so it needs no order match.
        if let Some(out) = self.native_weighted_total_degree_store_int(py, weight)? {
            return Ok(out);
        }
        let one = 1i64.into_pyobject(py)?.into_any();
        let sum_fn = py.import("builtins")?.getattr("sum")?;
        // cc-mgwdegfstore: on a clean graph the CgseValue store is authoritative,
        // so read exact floats straight from it (no per-edge PyObject); on a dirty
        // graph the live mirror is authoritative, so keep the PyObject mirror twin.
        let store_authoritative = !self.edges_dirty.load(Ordering::Relaxed);
        let mut out: Vec<(PyObject, PyObject)> = Vec::with_capacity(self.inner.node_count());
        for node in self.inner.nodes_ordered() {
            // br-r37-c1-mgwdegf (cc): float fast path. When EVERY contributing
            // weight value is an exact float (and the node has >=1 edge), sum
            // them with CPython's Neumaier (Kahan-Babuska) compensation directly
            // in Rust — bit-identical to builtins.sum (verified 30k cases) —
            // skipping the per-edge PyList append and the per-node builtins.sum
            // call. Returns None (-> exact PyList+sum fallback below) on ANY
            // non-float value (missing-weight default int 1, or an int/other
            // weight) AND for an edgeless node, so int/mixed parity, numeric
            // promotion, and nx's int-0 for isolated nodes stay byte-exact.
            let float_total = if store_authoritative {
                self.weighted_degree_float_node_store(node, weight)
            } else {
                self.weighted_degree_float_node(py, node, weight)?
            };
            if let Some(total) = float_total {
                out.push((
                    self.py_node_key(py, node),
                    pyo3::types::PyFloat::new(py, total).into_any().unbind(),
                ));
                continue;
            }
            let values = pyo3::types::PyList::empty(py);
            let mut selfloop = false;
            for neighbor in self.inner.neighbors(node).unwrap_or_default() {
                if neighbor == node {
                    selfloop = true;
                }
                for key in self.inner.edge_keys(node, neighbor).unwrap_or_default() {
                    let ek = Self::edge_key(node, neighbor, key);
                    if let Some(d) = self.edge_py_attrs.get(&ek) {
                        let value = d
                            .bind(py)
                            .get_item(weight)
                            .ok()
                            .flatten()
                            .unwrap_or_else(|| one.clone());
                        values.append(value)?;
                    } else if let Some(value) =
                        self.edge_attr_py_value(py, node, neighbor, key, weight)?
                    {
                        values.append(value.bind(py))?;
                    } else {
                        values.append(&one)?;
                    }
                }
            }
            let mut deg = sum_fn.call1((values,))?;
            if selfloop {
                let sl = pyo3::types::PyList::empty(py);
                for key in self.inner.edge_keys(node, node).unwrap_or_default() {
                    let ek = Self::edge_key(node, node, key);
                    if let Some(d) = self.edge_py_attrs.get(&ek) {
                        let value = d
                            .bind(py)
                            .get_item(weight)
                            .ok()
                            .flatten()
                            .unwrap_or_else(|| one.clone());
                        sl.append(value)?;
                    } else if let Some(value) =
                        self.edge_attr_py_value(py, node, node, key, weight)?
                    {
                        sl.append(value.bind(py))?;
                    } else {
                        sl.append(&one)?;
                    }
                }
                deg = deg.add(sum_fn.call1((sl,))?)?;
            }
            out.push((self.py_node_key(py, node), deg.unbind()));
        }
        Ok(out)
    }

    /// br-r37-c1-degnbw (cc): weighted-subset sibling of _native_weighted_degree —
    /// degree(nbunch, weight) over the (validated, in-graph) nbunch nodes only.
    /// nbunch+weight previously fell to the Python _degree_compute loop (~0.04x).
    /// NOT deduped (matches nx degree(nbunch)); KEEP builtins.sum for float parity;
    /// selfloop weight double-counted via the separate trailing sum.
    fn _native_weighted_degree_subset(
        &self,
        py: Python<'_>,
        nbunch: &Bound<'_, PyAny>,
        weight: &str,
    ) -> PyResult<Vec<(PyObject, PyObject)>> {
        if let Some(pairs) = self.weighted_degree_subset_py_int_impl(py, nbunch, weight)? {
            return Ok(pairs);
        }

        let one = 1i64.into_pyobject(py)?.into_any();
        let sum_fn = py.import("builtins")?.getattr("sum")?;
        let mut out: Vec<(PyObject, PyObject)> = Vec::new();
        for item in nbunch.try_iter()? {
            let node_obj = item?;
            if node_obj.hash().is_err() {
                let label = node_obj
                    .str()
                    .map(|s| s.to_string_lossy().into_owned())
                    .unwrap_or_else(|_| "?".to_owned());
                return Err(pyo3::exceptions::PyTypeError::new_err(format!(
                    "Node {label} in sequence nbunch is not a valid node."
                )));
            }
            let node = node_key_to_string(py, &node_obj)?;
            if !self.inner.has_node(&node) {
                continue;
            }
            let values = pyo3::types::PyList::empty(py);
            let mut selfloop = false;
            for neighbor in self.inner.neighbors(&node).unwrap_or_default() {
                if neighbor == node.as_str() {
                    selfloop = true;
                }
                for key in self.inner.edge_keys(&node, neighbor).unwrap_or_default() {
                    let ek = Self::edge_key(&node, neighbor, key);
                    if let Some(d) = self.edge_py_attrs.get(&ek) {
                        let value = d
                            .bind(py)
                            .get_item(weight)
                            .ok()
                            .flatten()
                            .unwrap_or_else(|| one.clone());
                        values.append(value)?;
                    } else if let Some(value) =
                        self.edge_attr_py_value(py, &node, neighbor, key, weight)?
                    {
                        values.append(value.bind(py))?;
                    } else {
                        values.append(&one)?;
                    }
                }
            }
            let mut deg = sum_fn.call1((values,))?;
            if selfloop {
                let sl = pyo3::types::PyList::empty(py);
                for key in self.inner.edge_keys(&node, &node).unwrap_or_default() {
                    let ek = Self::edge_key(&node, &node, key);
                    if let Some(d) = self.edge_py_attrs.get(&ek) {
                        let value = d
                            .bind(py)
                            .get_item(weight)
                            .ok()
                            .flatten()
                            .unwrap_or_else(|| one.clone());
                        sl.append(value)?;
                    } else if let Some(value) =
                        self.edge_attr_py_value(py, &node, &node, key, weight)?
                    {
                        sl.append(value.bind(py))?;
                    } else {
                        sl.append(&one)?;
                    }
                }
                deg = deg.add(sum_fn.call1((sl,))?)?;
            }
            out.push((node_obj.clone().unbind(), deg.unbind()));
        }
        Ok(out)
    }

    fn weighted_degree_subset_py_int_impl(
        &self,
        py: Python<'_>,
        nbunch: &Bound<'_, PyAny>,
        weight: &str,
    ) -> PyResult<Option<Vec<(PyObject, PyObject)>>> {
        let mut out: Vec<(PyObject, PyObject)> = Vec::new();
        for item in nbunch.try_iter()? {
            let node_obj = item?;
            if node_obj.hash().is_err() {
                let label = node_obj
                    .str()
                    .map(|s| s.to_string_lossy().into_owned())
                    .unwrap_or_else(|_| "?".to_owned());
                return Err(pyo3::exceptions::PyTypeError::new_err(format!(
                    "Node {label} in sequence nbunch is not a valid node."
                )));
            }
            let node = node_key_to_string(py, &node_obj)?;
            if !self.inner.has_node(&node) {
                continue;
            }

            let Some(total) = self.weighted_degree_py_int_row(py, &node, weight) else {
                return Ok(None);
            };
            let Ok(total_i64) = i64::try_from(total) else {
                return Ok(None);
            };
            out.push((node_obj.clone().unbind(), total_i64.into_py_any(py)?));
        }
        Ok(Some(out))
    }

    fn weighted_degree_py_int_row(&self, py: Python<'_>, node: &str, weight: &str) -> Option<i128> {
        let mut total = 0i128;
        let mut selfloop = false;
        if let Some(neighbors) = self.inner.neighbors_iter(node) {
            for neighbor in neighbors {
                if neighbor == node {
                    selfloop = true;
                }
                let keys = self.inner.edge_keys_iter(node, neighbor)?;
                for key in keys {
                    let value = self.multigraph_py_int_weight(py, node, neighbor, *key, weight)?;
                    total = total.checked_add(i128::from(value))?;
                }
            }
        }
        if selfloop {
            let keys = self.inner.edge_keys_iter(node, node)?;
            for key in keys {
                let value = self.multigraph_py_int_weight(py, node, node, *key, weight)?;
                total = total.checked_add(i128::from(value))?;
            }
        }
        Some(total)
    }

    fn multigraph_py_int_weight(
        &self,
        py: Python<'_>,
        source: &str,
        target: &str,
        key: usize,
        weight: &str,
    ) -> Option<i64> {
        let ek = Self::edge_key(source, target, key);
        match self.edge_py_attrs.get(&ek) {
            Some(attrs) => match attrs.bind(py).get_item(weight).ok().flatten() {
                Some(value) => {
                    if !value.is_exact_instance_of::<PyInt>() {
                        return None;
                    }
                    value.extract::<i64>().ok()
                }
                None => Some(1),
            },
            None => match self
                .inner
                .edge_attrs(source, target, key)
                .and_then(|attrs| attrs.get(weight))
            {
                Some(CgseValue::Int(value)) => Some(*value),
                Some(_) => None,
                None => Some(1),
            },
        }
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
        // br-r37-c1-mdgcopyclone NOTE: the MultiDiGraph clone+reorder fix does NOT
        // port here. MultiGraph's reorder_rows_for_nx_copy_walk is INPUT-ORDER
        // DEPENDENT (early neighbours sort by index-of-u-within-adj[v]), so it must
        // run on the edge-INSERTION-order adjacency that the edges_ordered() rebuild
        // below guarantees; an inner clone preserves the SOURCE's (possibly already
        // u-major reordered) row order, which makes copy-of-a-copy diverge
        // (test_roundtrip_of_copy_keeps_walk_reordered_rows[MultiGraph]). The
        // directed sibling is safe because reorder_pred rebuilds pred from the
        // never-reordered succ. Keep the rebuild.
        let mut new_graph = Self {
            edges_data_attr_cache: std::sync::Mutex::new(None),
            // br-r37-c1-7dpyg: fresh ledger, mode only (skip ledger clone)
            inner: MultiGraph::with_runtime_policy(fnx_runtime::RuntimePolicy::new(
                self.inner.mode(),
            )),
            node_key_map: HashMap::new(),
            adj_py_keys: self.derive_copy_adj_py_keys(py), // br-r37-c1-z6uka
            node_py_attrs: HashMap::new(),
            edge_py_attrs: HashMap::new(),
            edge_py_keys: HashMap::new(),
            has_remapped_int_key: self.has_remapped_int_key,
            edge_mirrors_stale: false,
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
        // br-r37-c1-tbh4q: single-pass attr crossing (with_mirror) on copy() —
        // node attrs still cross once; clean edge attrs below reuse the
        // synchronized Rust AttrMap and only copy the Python mirror.
        for node in self.inner.nodes_ordered() {
            match self.node_py_attrs.get(node) {
                Some(attrs) => {
                    let (rust_attrs, mirror) = py_dict_to_attr_map_with_mirror(py, attrs.bind(py))?;
                    new_graph
                        .inner
                        .add_node_with_attrs(node.to_owned(), rust_attrs);
                    new_graph.node_py_attrs.insert(node.to_owned(), mirror);
                }
                None => {
                    new_graph
                        .inner
                        .add_node_with_attrs(node.to_owned(), AttrMap::new());
                }
            }
            new_graph
                .node_key_map
                .insert(node.to_owned(), self.py_node_key(py, node));
        }
        // br-r37-c1-mgcopybatch: collect the keyed edges in edge-INSERTION order
        // (edges_ordered) and commit them through ONE extend_keyed_edges_with_attrs_
        // _unrecorded — the bulk API DESIGNED for copy/convert (per-edge
        // add_edge_with_key_and_attrs pays TWO record_decision ledger pushes/edge).
        // Insertion order is preserved (the bulk insert appends in collected order),
        // so the input-order-dependent reorder_rows below still produces nx's u-major
        // copy walk. The Python mirrors (edge_py_attrs / remember_edge_key) are still
        // populated per edge — they don't touch the inner.
        let mut keyed_edges: Vec<(String, String, usize, AttrMap)> =
            Vec::with_capacity(self.inner.edge_count());
        let source_edges_dirty = self.edges_dirty.load(Ordering::Relaxed);
        for snapshot in self.inner.edges_ordered() {
            let (u, v, key) = (snapshot.left.clone(), snapshot.right.clone(), snapshot.key);
            let attrs_entry = self
                .edge_py_attrs
                .get(&(u.clone(), v.clone(), key))
                .or_else(|| self.edge_py_attrs.get(&(v.clone(), u.clone(), key)));
            // br-r37-c1-aab122464: drop the eager empty edge-attr PyDict for attr-less
            // edges (15000 allocs on a dense graph) — lazy materialize_edge_py_attrs is
            // identity-preserving, so an absent mirror reads identically to an empty dict.
            let rust_attrs = if source_edges_dirty {
                match attrs_entry {
                    Some(attrs) => {
                        let (rust_attrs, mirror) =
                            py_dict_to_attr_map_with_mirror(py, attrs.bind(py))?;
                        new_graph
                            .edge_py_attrs
                            .insert((u.clone(), v.clone(), key), mirror);
                        rust_attrs
                    }
                    None => snapshot.attrs.clone(),
                }
            } else {
                if let Some(attrs) = attrs_entry {
                    new_graph
                        .edge_py_attrs
                        .insert((u.clone(), v.clone(), key), attrs.bind(py).copy()?.unbind());
                }
                snapshot.attrs.clone()
            };
            keyed_edges.push((u.clone(), v.clone(), key, rust_attrs));
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
        let _ = new_graph
            .inner
            .extend_keyed_edges_with_attrs_unrecorded(keyed_edges);
        // br-r37-c1-s0d4x: cells in nx's u-major copy-walk order (the
        // edges_ordered rebuild above is edge INSERTION order).
        new_graph.inner.reorder_rows_for_nx_copy_walk();
        Ok(new_graph)
    }

    fn _native_to_undirected_deepcopy(&self, py: Python<'_>) -> PyResult<Self> {
        let deepcopy = py.import("copy")?.getattr("deepcopy")?;
        let mut new_graph = Self {
            edges_data_attr_cache: std::sync::Mutex::new(None),
            inner: MultiGraph::with_runtime_policy(self.inner.runtime_policy().clone()),
            node_key_map: HashMap::new(),
            adj_py_keys: HashMap::new(), // br-r37-c1-z6uka
            node_py_attrs: HashMap::new(),
            edge_py_attrs: HashMap::new(),
            edge_py_keys: HashMap::new(),
            has_remapped_int_key: self.has_remapped_int_key,
            edge_mirrors_stale: false,
            graph_attrs: deepcopy_py_dict(py, &deepcopy, &self.graph_attrs)?,
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
        // br-r37-c1-l5ve7: fresh ledger (the policy clone deep-copied the
        // source's unbounded decision ledger) + LAZY attr mirrors (the
        // old loop allocated an empty PyDict per attr-less node/edge —
        // the bindings tolerate absent entries throughout).
        let mut mdg = crate::digraph::PyMultiDiGraph {
            in_edges_data_attr_cache: std::sync::Mutex::new(None),
            edges_data_attr_cache: std::sync::Mutex::new(None),
            inner: fnx_classes::digraph::MultiDiGraph::with_runtime_policy(
                fnx_runtime::RuntimePolicy::new(self.inner.mode()),
            ),
            node_key_map: HashMap::new(),
            succ_py_keys: HashMap::new(), // br-r37-c1-z6uka
            pred_py_keys: HashMap::new(), // br-r37-c1-z6uka
            node_py_attrs: HashMap::new(),
            edge_py_attrs: HashMap::new(),
            edge_py_keys: HashMap::new(),
            has_remapped_int_key: self.has_remapped_int_key,
            graph_attrs: deepcopy_py_dict(py, &deepcopy, &self.graph_attrs)?,
            nodes_seq: 0,
            edges_seq: 0,
            edges_dirty: AtomicBool::new(false),
            edge_dirty_keys: crate::digraph::PyMultiDiGraph::clean_edge_dirty_keys(),
            node_keys_cache: std::sync::Mutex::new(None),
            node_data_mirror: std::sync::Mutex::new(None),
            dict_of_dicts_cache: None,
            edges_with_data_cache: None,
            in_edges_with_data_cache: None,
            edges_with_keys_cache: None,
            node_iter_mirror: std::sync::Mutex::new(None),
        };
        let mut node_batch: Vec<(String, fnx_classes::AttrMap)> =
            Vec::with_capacity(self.inner.node_count());
        for node in self.inner.nodes_ordered() {
            let rust_attrs = if let Some(attrs) = self.node_py_attrs.get(node) {
                let py_attrs = deepcopy_py_dict(py, &deepcopy, attrs)?;
                let rust_attrs = py_dict_to_attr_map(py_attrs.bind(py))?;
                mdg.node_py_attrs.insert(node.to_owned(), py_attrs);
                rust_attrs
            } else {
                Default::default()
            };
            mdg.node_key_map
                .insert(node.to_owned(), self.py_node_key(py, node));
            node_batch.push((node.to_owned(), rust_attrs));
        }
        mdg.inner.extend_nodes_with_attrs_unrecorded(node_batch);
        // br-r37-c1-l5ve7 lever 8: bulk KEYED inserts preserve the
        // SOURCE's internal keys (the old per-edge add_edge_with_attrs
        // auto-keyed and paid two ledger records per edge), keeping the
        // display-key mapping 1:1 with the source.
        let mut edge_batch: Vec<(String, String, usize, fnx_classes::AttrMap)> = Vec::new();
        for source in self.inner.nodes_ordered() {
            for target in self.inner.neighbors(source).unwrap_or_default() {
                for key in self.inner.edge_keys(source, target).unwrap_or_default() {
                    let attrs_entry = self.edge_py_attrs.get(&Self::edge_key(source, target, key));
                    let rust_attrs = match attrs_entry {
                        Some(attrs) => {
                            let py_attrs = deepcopy_py_dict(py, &deepcopy, attrs)?;
                            let rust_attrs = py_dict_to_attr_map(py_attrs.bind(py))?;
                            mdg.edge_py_attrs
                                .insert((source.to_owned(), target.to_owned(), key), py_attrs);
                            rust_attrs
                        }
                        None => Default::default(),
                    };
                    let py_key = self.py_edge_key(py, source, target, key);
                    mdg.remember_edge_key_object(py, source, target, key, &py_key);
                    edge_batch.push((source.to_owned(), target.to_owned(), key, rust_attrs));
                }
            }
        }
        mdg.inner
            .extend_keyed_edges_with_attrs_unrecorded(edge_batch);
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
            edges_data_attr_cache: std::sync::Mutex::new(None),
            inner: self.inner.clone_with_fresh_policy(), // br-r37-c1-7dpyg: skip ledger
            node_key_map: HashMap::with_capacity(self.node_key_map.len()),
            adj_py_keys: self.derive_copy_adj_py_keys(py), // br-r37-c1-z6uka
            node_py_attrs: HashMap::with_capacity(self.node_py_attrs.len()),
            edge_py_attrs: HashMap::with_capacity(self.edge_py_attrs.len()),
            edge_py_keys: HashMap::with_capacity(self.edge_py_keys.len()),
            has_remapped_int_key: self.has_remapped_int_key,
            edge_mirrors_stale: self.edge_mirrors_stale,
            graph_attrs: self.graph_attrs.bind(py).copy()?.unbind(),
            nodes_seq: 0,
            edges_seq: 0,
            edges_dirty: AtomicBool::new(self.edges_dirty.load(Ordering::Relaxed)),
            node_keys_cache: std::sync::Mutex::new(None),
            node_data_mirror: std::sync::Mutex::new(None),
            dict_of_dicts_cache: None,
            edges_with_data_cache: None,
            edges_with_keys_cache: None,
            node_iter_mirror: std::sync::Mutex::new(None),
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
            edges_data_attr_cache: std::sync::Mutex::new(None),
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
            has_remapped_int_key: self.has_remapped_int_key,
            edge_mirrors_stale: self.edge_mirrors_stale,
            // SHARE the graph attrs dict (shallow copy)
            graph_attrs: self.graph_attrs.clone_ref(py),
            nodes_seq: 0,
            edges_seq: 0,
            edges_dirty: AtomicBool::new(self.edges_dirty.load(Ordering::Relaxed)),
            node_keys_cache: std::sync::Mutex::new(None),
            node_data_mirror: std::sync::Mutex::new(None),
            dict_of_dicts_cache: None,
            edges_with_data_cache: None,
            edges_with_keys_cache: None,
            node_iter_mirror: std::sync::Mutex::new(None),
        })
    }

    /// Support ``copy.deepcopy(G)`` — returns a deep copy.
    #[pyo3(signature = (_memo=None))]
    fn __deepcopy__(&self, py: Python<'_>, _memo: Option<&Bound<'_, PyAny>>) -> PyResult<Self> {
        self.copy(py)
    }

    /// br-r37-c1-489mp: native same-type deepcopy. VERBATIM structure (via
    /// `__copy__` — NOT `copy()`'s copy-walk reorder, matching the Python
    /// `_graph_deepcopy` override's `copy.copy` base) + deep-copied node/edge
    /// attr dicts under ONE shared memo. The thin Python tail still handles
    /// graph attrs, frozen and custom instance attributes. Replaces that
    /// override's per-node/edge AtlasView walk (the deepcopy bottleneck:
    /// `out[u][v]` rebuilt the adjacency row keydict 17k× on a 4k-edge graph).
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
            let deep =
                deepcopy_py_dict_memo(py, &deepcopy, &new_graph.node_py_attrs[&k], &memo_obj)?;
            new_graph.node_py_attrs.insert(k, deep);
        }
        let edge_keys: Vec<(String, String, usize)> =
            new_graph.edge_py_attrs.keys().cloned().collect();
        for k in edge_keys {
            let deep =
                deepcopy_py_dict_memo(py, &deepcopy, &new_graph.edge_py_attrs[&k], &memo_obj)?;
            new_graph.edge_py_attrs.insert(k, deep);
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
            edges_data_attr_cache: std::sync::Mutex::new(None),
            inner: MultiGraph::with_runtime_policy(self.inner.runtime_policy().clone()),
            node_key_map: HashMap::new(),
            adj_py_keys: HashMap::new(), // br-r37-c1-z6uka
            node_py_attrs: HashMap::new(),
            edge_py_attrs: HashMap::new(),
            edge_py_keys: HashMap::new(),
            has_remapped_int_key: self.has_remapped_int_key,
            edge_mirrors_stale: false,
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

        for canonical in &keep {
            // br-r37-c1-tbh4q: single-pass attr crossing (with_mirror) — induced
            // subgraph keeps each node/edge once (no merge); mirror is shallow-copy
            // byte-identical to .copy(); conditional node_key_map insert preserved.
            match self.node_py_attrs.get(canonical) {
                Some(attrs) => {
                    let (rust_attrs, mirror) = py_dict_to_attr_map_with_mirror(py, attrs.bind(py))?;
                    new_graph
                        .inner
                        .add_node_with_attrs(canonical.clone(), rust_attrs);
                    new_graph.node_py_attrs.insert(canonical.clone(), mirror);
                }
                None => {
                    new_graph
                        .inner
                        .add_node_with_attrs(canonical.clone(), AttrMap::new());
                }
            }
            if let Some(py_key) = self.node_key_map.get(canonical) {
                new_graph
                    .node_key_map
                    .insert(canonical.clone(), py_key.clone_ref(py));
            }
        }

        for edge in self.inner.edges_ordered() {
            if keep.contains(&edge.left) && keep.contains(&edge.right) {
                let ek = Self::edge_key(&edge.left, &edge.right, edge.key);
                match self.edge_py_attrs.get(&ek) {
                    Some(attrs) => {
                        let (rust_attrs, mirror) =
                            py_dict_to_attr_map_with_mirror(py, attrs.bind(py))?;
                        let _ = new_graph.inner.add_edge_with_key_and_attrs(
                            edge.left.clone(),
                            edge.right.clone(),
                            edge.key,
                            rust_attrs,
                        );
                        new_graph.edge_py_attrs.insert(ek.clone(), mirror);
                    }
                    None => {
                        let _ = new_graph.inner.add_edge_with_key_and_attrs(
                            edge.left.clone(),
                            edge.right.clone(),
                            edge.key,
                            AttrMap::new(),
                        );
                    }
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
            edges_data_attr_cache: std::sync::Mutex::new(None),
            inner: MultiGraph::with_runtime_policy(self.inner.runtime_policy().clone()),
            node_key_map: HashMap::new(),
            adj_py_keys: HashMap::new(), // br-r37-c1-z6uka
            node_py_attrs: HashMap::new(),
            edge_py_attrs: HashMap::new(),
            edge_py_keys: HashMap::new(),
            has_remapped_int_key: self.has_remapped_int_key,
            edge_mirrors_stale: false,
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
                    // br-r37-c1-tbh4q: single-pass Rust AttrMap + Python mirror.
                    let (rust_attrs, mirror) = py_dict_to_attr_map_with_mirror(py, attrs.bind(py))?;
                    let _ = new_graph.inner.add_edge_with_key_and_attrs(
                        u.clone(),
                        v.clone(),
                        k,
                        rust_attrs,
                    );
                    new_graph.edge_py_attrs.insert(ek, mirror);
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
            // br-r37-c1-tbh4q: single-pass attr crossing (with_mirror); conditional
            // node_key_map insert preserved.
            match self.node_py_attrs.get(canonical) {
                Some(attrs) => {
                    let (rust_attrs, mirror) = py_dict_to_attr_map_with_mirror(py, attrs.bind(py))?;
                    new_graph
                        .inner
                        .add_node_with_attrs(canonical.clone(), rust_attrs);
                    new_graph.node_py_attrs.insert(canonical.clone(), mirror);
                }
                None => {
                    new_graph
                        .inner
                        .add_node_with_attrs(canonical.clone(), AttrMap::new());
                }
            }
            if let Some(py_key) = self.node_key_map.get(canonical) {
                new_graph
                    .node_key_map
                    .insert(canonical.clone(), py_key.clone_ref(py));
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
            in_edges_data_attr_cache: std::sync::Mutex::new(None),
            edges_data_attr_cache: std::sync::Mutex::new(None),
            inner: fnx_classes::digraph::MultiDiGraph::with_runtime_policy(
                self.inner.runtime_policy().clone(),
            ),
            node_key_map: HashMap::new(),
            succ_py_keys: HashMap::new(), // br-r37-c1-z6uka
            pred_py_keys: HashMap::new(), // br-r37-c1-z6uka
            node_py_attrs: HashMap::new(),
            edge_py_attrs: HashMap::new(),
            edge_py_keys: HashMap::new(),
            has_remapped_int_key: self.has_remapped_int_key,
            graph_attrs: self.graph_attrs.bind(py).copy()?.unbind(),
            nodes_seq: 0,
            edges_seq: 0,
            edges_dirty: AtomicBool::new(false),
            edge_dirty_keys: crate::digraph::PyMultiDiGraph::clean_edge_dirty_keys(),
            node_keys_cache: std::sync::Mutex::new(None),
            node_data_mirror: std::sync::Mutex::new(None),
            dict_of_dicts_cache: None,
            edges_with_data_cache: None,
            in_edges_with_data_cache: None,
            edges_with_keys_cache: None,
            node_iter_mirror: std::sync::Mutex::new(None),
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
            .map(|n| -> PyResult<_> {
                let py_key = self.py_node_key(py, n);
                // br-r37-c1-getstate-storemiss (cc): a MISSING node mirror does NOT
                // mean empty attrs — single-attr / bulk-added nodes stay LAZY in the
                // CgseValue store with no node_py_attrs entry (only multi-attr nodes
                // get an eager mirror). The old `map_or_else(|| PyDict::new(...))`
                // DROPPED single-attr node attributes on pickle/deepcopy (e.g.
                // add_nodes_from([(i,{'p':i})]) or convert_node_labels_to_integers ->
                // pickle -> every node came back {}). Fall back to the store's AttrMap.
                let attrs = match self.node_py_attrs.get(n) {
                    Some(d) => d.clone_ref(py),
                    None => match self.inner.node_attrs(n) {
                        Some(a) => attr_map_to_pydict(py, a)?,
                        None => PyDict::new(py).unbind(),
                    },
                };
                Ok((py_key, attrs))
            })
            .collect::<PyResult<Vec<_>>>()?;
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
        self.edge_mirrors_stale = false;
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

    /// br-r37-c1-mgwdegf: total weighted degree of `node` as an f64 iff the node
    /// has at least one edge AND every contributing weight value is an exact
    /// float; otherwise None (signalling the caller's exact builtins.sum
    /// fallback). Replicates CPython sum's Neumaier compensation over the main
    /// (neighbor, key) pass in adjacency order and re-adds the self-loop weights
    /// with a second compensated sum, matching nx's `sum(main) + sum(self_loop)`
    /// bitwise. Returning None for an edgeless node preserves nx's int `0`
    /// (sum of an empty sequence) rather than a float `0.0`.
    fn weighted_degree_float_node(
        &self,
        py: Python<'_>,
        node: &str,
        weight: &str,
    ) -> PyResult<Option<f64>> {
        let mut f = 0.0f64;
        let mut c = 0.0f64;
        let mut sf = 0.0f64;
        let mut sc = 0.0f64;
        let mut has_selfloop = false;
        let mut saw = false;
        for neighbor in self.inner.neighbors(node).unwrap_or_default() {
            let is_self = neighbor == node;
            if is_self {
                has_selfloop = true;
            }
            for key in self.inner.edge_keys(node, neighbor).unwrap_or_default() {
                let Some(x) = self.edge_weight_exact_f64(py, node, neighbor, key, weight)? else {
                    return Ok(None);
                };
                saw = true;
                let t = f + x;
                if f.abs() >= x.abs() {
                    c += (f - t) + x;
                } else {
                    c += (x - t) + f;
                }
                f = t;
                if is_self {
                    let ts = sf + x;
                    if sf.abs() >= x.abs() {
                        sc += (sf - ts) + x;
                    } else {
                        sc += (x - ts) + sf;
                    }
                    sf = ts;
                }
            }
        }
        if !saw {
            return Ok(None);
        }
        let mut total = f + c;
        if has_selfloop {
            total += sf + sc;
        }
        Ok(Some(total))
    }

    /// cc-mgwdegfstore: store twin of `weighted_degree_float_node`. The mirror
    /// twin fetches each edge's weight through `edge_weight_exact_f64`, which on a
    /// bulk-built graph (`edge_py_attrs` left lazy/empty by `add_edges_from` /
    /// `add_weighted_edges_from`) materialises a PyObject per edge via the store —
    /// so the float fast path paid a per-edge PyObject on the common weighted case
    /// and `degree(weight)` fell to ~0.5x nx. This reads the exact float straight
    /// from the CgseValue store in the SAME `neighbors -> edge_keys` order as the
    /// (proven byte-exact) mirror twin and with the SAME two Neumaier-compensated
    /// sums (every incident edge once, plus a SECOND pass over self-loop weights —
    /// nx's undirected `MultiDegreeView` counts a self-loop's weight twice), so it
    /// is bit-identical to the mirror twin's store-fallback path. Returns `None`
    /// (caller uses the exact PyList+`builtins.sum` fallback) on any non-float or
    /// absent value (nx default int 1) or a fully edgeless node (nx int 0). CALLER
    /// must gate on `!edges_dirty` (store authoritative). Undirected sibling of
    /// `PyMultiDiGraph::weighted_total_degree_float_node_store`.
    fn weighted_degree_float_node_store(&self, node: &str, weight: &str) -> Option<f64> {
        let mut f = 0.0f64;
        let mut c = 0.0f64;
        let mut sf = 0.0f64;
        let mut sc = 0.0f64;
        let mut has_selfloop = false;
        let mut saw = false;
        if let Some(neighbors) = self.inner.neighbors_iter(node) {
            for neighbor in neighbors {
                let is_self = neighbor == node;
                if is_self {
                    has_selfloop = true;
                }
                // `edge_attr_values` yields the pair's AttrMaps in the SAME order
                // as `edge_keys` (adjacency IndexSet and the edges IndexMap stay
                // key-synced), so this is bit-identical to the per-key path but
                // does ONE bucket lookup per pair instead of two hash lookups per
                // parallel edge — the residual cost that kept MG below nx.
                for attrs in self.inner.edge_attr_values(node, neighbor)? {
                    let CgseValue::Float(x) = attrs.get(weight)? else {
                        return None;
                    };
                    let x = *x;
                    saw = true;
                    let t = f + x;
                    if f.abs() >= x.abs() {
                        c += (f - t) + x;
                    } else {
                        c += (x - t) + f;
                    }
                    f = t;
                    if is_self {
                        let ts = sf + x;
                        if sf.abs() >= x.abs() {
                            sc += (sf - ts) + x;
                        } else {
                            sc += (x - ts) + sf;
                        }
                        sf = ts;
                    }
                }
            }
        }
        if !saw {
            return None;
        }
        let mut total = f + c;
        if has_selfloop {
            total += sf + sc;
        }
        Some(total)
    }

    /// Exact-float weight value for one multigraph edge, or None when the value
    /// is missing (nx default int 1) or any non-float — both routing the caller
    /// to the exact PyList+builtins.sum path. Mirrors the fallback's value fetch
    /// (live edge-attr mirror first, then the CgseValue store) exactly.
    fn edge_weight_exact_f64(
        &self,
        py: Python<'_>,
        node: &str,
        neighbor: &str,
        key: usize,
        weight: &str,
    ) -> PyResult<Option<f64>> {
        let ek = Self::edge_key(node, neighbor, key);
        if let Some(d) = self.edge_py_attrs.get(&ek) {
            match d.bind(py).get_item(weight).ok().flatten() {
                Some(v) => {
                    if v.is_exact_instance_of::<pyo3::types::PyFloat>() {
                        Ok(Some(v.extract::<f64>()?))
                    } else {
                        Ok(None)
                    }
                }
                None => Ok(None),
            }
        } else if let Some(value) = self.edge_attr_py_value(py, node, neighbor, key, weight)? {
            let vb = value.bind(py);
            if vb.is_exact_instance_of::<pyo3::types::PyFloat>() {
                Ok(Some(vb.extract::<f64>()?))
            } else {
                Ok(None)
            }
        } else {
            Ok(None)
        }
    }

    /// br-r37-c1-fpssi: all node display objects as a Vec, reusing the
    /// nodes_seq-keyed tuple cache (clone_ref of cached elements) instead of
    /// rebuilding via py_node_key per node. Backs the graph node iterator
    /// (`set(G)` / `for n in G`), which keeps its per-next nodes_seq guard.
    // br-r37-c1-qwqvn: infra for the pending MultiGraph edges() index lever
    // (symmetric with the wired PyGraph/PyDiGraph variants); not yet a consumer.
    #[allow(dead_code)]
    pub(crate) fn cached_node_key_vec(&self, py: Python<'_>) -> Vec<PyObject> {
        let seq = self.nodes_seq;
        {
            let guard = self.node_keys_cache.lock().unwrap();
            if let Some((cached_seq, tup)) = guard.as_ref()
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
        *self.node_keys_cache.lock().unwrap() = Some((seq, tup.clone_ref(py)));
        keys
    }

    /// Incremental node-iteration mirror (see PyGraph::node_iter_mirror_or_init).
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

    /// Return (node, attrs) pairs (like dict.items()).
    /// br-r37-c1-4b5ie: serve from the nodes_seq-keyed node_data_mirror so
    /// repeated nodes(data=...) on an unchanged graph reuse the cache.
    fn items(&self, py: Python<'_>) -> PyResult<PyObject> {
        let mut g = self.graph.borrow_mut(py);
        g.node_data_items_view(py)
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
    /// br-r37-c1-natdiffsimple: fully-native `difference(G, H)` for simple Graph
    /// (the undirected-simple sibling of `PyMultiGraph::_native_difference`).
    /// Builds the result entirely in Rust: H's edges are hashed into a canonical
    /// set, G is walked in node-major `edges()` order (each undirected pair once,
    /// emitted at its first/earlier-node encounter exactly like nx's `G.edges()`
    /// stream) and kept edges go straight onto the fresh result carrying G's node
    /// display keys. Skips the Python `create_empty_copy` + EdgeView set
    /// materialization + `add_edges_from` round-trip (~3.3x nx). Returns `None`
    /// (wrapper falls back) when either graph carries z6uka adjacency-cell display
    /// overrides (mixed hash-equal node objects), which the plain node_key_map
    /// path can't honour.
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
        if !g.adj_py_keys.is_empty() || !hh.adj_py_keys.is_empty() {
            return Ok(None);
        }

        // Work entirely in G's integer index space to avoid per-edge String
        // allocation. g_nodes[i] is the canonical key at G-index i; g_index maps
        // canonical -> G-index. H shares G's node SET (wrapper precondition) but
        // may index it differently, so H's edges are translated into G-index
        // pairs; decline (-> None) if any H node is somehow absent from G.
        let g_nodes: Vec<&str> = g.inner.nodes_ordered();
        let g_index: HashMap<&str, usize> =
            g_nodes.iter().enumerate().map(|(i, &n)| (n, i)).collect();

        // H's edge set as canonical (min, max) G-index pairs.
        let mut h_set: HashSet<(usize, usize)> = HashSet::new();
        for u in hh.inner.nodes_ordered() {
            let Some(&ui) = g_index.get(u) else {
                return Ok(None);
            };
            for v in hh.inner.neighbors(u).unwrap_or_default() {
                let Some(&vi) = g_index.get(v) else {
                    return Ok(None);
                };
                h_set.insert(if ui <= vi { (ui, vi) } else { (vi, ui) });
            }
        }

        let mut r = Self::new_empty_with_mode(py, g.inner.mode())?;
        // Propagate G's lazy-int range and copy ONLY its explicitly-materialized
        // node objects — never call `py_node_key` per node, which would force a
        // fresh PyInt for every lazy-range node (the dominant cost on large
        // integer-node graphs). Result renders node display keys identically.
        r.lazy_int_node_stop = g.lazy_int_node_stop;
        for (canonical, obj) in &g.node_key_map {
            r.node_key_map.insert(canonical.clone(), obj.clone_ref(py));
        }
        let _ = r.inner.extend_nodes_with_attrs_unrecorded(
            g_nodes.iter().map(|n| ((*n).to_owned(), AttrMap::new())),
        );

        // G's edges in node-major `edges()` order, each undirected pair once at its
        // first (earlier-node) encounter; kept when the canonical pair is absent
        // from H. Emitted as (current_node, neighbor) to match nx's orientation.
        let mut edges: Vec<(String, String, AttrMap)> = Vec::new();
        let mut seen: HashSet<(usize, usize)> = HashSet::new();
        for (ui, &u) in g_nodes.iter().enumerate() {
            let Some(nbrs) = g.inner.neighbors_indices(ui) else {
                continue;
            };
            for &vi in nbrs {
                let pair = if ui <= vi { (ui, vi) } else { (vi, ui) };
                if !seen.insert(pair) {
                    continue;
                }
                if !h_set.contains(&pair) {
                    edges.push((u.to_owned(), g_nodes[vi].to_owned(), AttrMap::new()));
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

    /// br-r37-c1-natsymdiff: fully-native `symmetric_difference(G, H)` for simple
    /// Graph (sibling of `PyGraph::_native_difference` and the MultiGraph
    /// `_native_symmetric_difference`). Two passes in G's integer index space:
    /// G-only edges (G node-major `edges()` order) then H-only edges (H node-major
    /// `edges()` order) — exactly the Python wrapper's order. Undirected, so each
    /// pass dedups by canonical (min,max) index pair and membership is
    /// orientation-independent. Node display keys come from G. Returns `None` on
    /// z6uka display overrides or a node missing from G.
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
        if !g.adj_py_keys.is_empty() || !hh.adj_py_keys.is_empty() {
            return Ok(None);
        }

        // Common index space = G's node order (= result node order).
        let g_nodes: Vec<&str> = g.inner.nodes_ordered();
        let g_index: HashMap<&str, usize> =
            g_nodes.iter().enumerate().map(|(i, &n)| (n, i)).collect();

        // G's and H's edge sets as canonical (min,max) G-index pairs.
        let mut g_set: HashSet<(usize, usize)> = HashSet::new();
        for (ui, _u) in g_nodes.iter().enumerate() {
            if let Some(nbrs) = g.inner.neighbors_indices(ui) {
                for &vi in nbrs {
                    g_set.insert(if ui <= vi { (ui, vi) } else { (vi, ui) });
                }
            }
        }
        let h_nodes: Vec<&str> = hh.inner.nodes_ordered();
        let mut h_set: HashSet<(usize, usize)> = HashSet::new();
        for u in &h_nodes {
            let Some(&ui) = g_index.get(*u) else {
                return Ok(None);
            };
            for v in hh.inner.neighbors(u).unwrap_or_default() {
                let Some(&vi) = g_index.get(v) else {
                    return Ok(None);
                };
                h_set.insert(if ui <= vi { (ui, vi) } else { (vi, ui) });
            }
        }

        let mut r = Self::new_empty_with_mode(py, g.inner.mode())?;
        r.lazy_int_node_stop = g.lazy_int_node_stop;
        for (canonical, obj) in &g.node_key_map {
            r.node_key_map.insert(canonical.clone(), obj.clone_ref(py));
        }
        let _ = r.inner.extend_nodes_with_attrs_unrecorded(
            g_nodes.iter().map(|n| ((*n).to_owned(), AttrMap::new())),
        );

        let mut edges: Vec<(String, String, AttrMap)> = Vec::new();
        // Pass 1: G-only edges (absent from H), G node-major order, each pair once.
        let mut seen_g: HashSet<(usize, usize)> = HashSet::new();
        for (ui, &u) in g_nodes.iter().enumerate() {
            if let Some(nbrs) = g.inner.neighbors_indices(ui) {
                for &vi in nbrs {
                    let pair = if ui <= vi { (ui, vi) } else { (vi, ui) };
                    if !seen_g.insert(pair) {
                        continue;
                    }
                    if !h_set.contains(&pair) {
                        edges.push((u.to_owned(), g_nodes[vi].to_owned(), AttrMap::new()));
                    }
                }
            }
        }
        // Pass 2: H-only edges (absent from G), H node-major order, each pair once.
        let mut seen_h: HashSet<(usize, usize)> = HashSet::new();
        for u in &h_nodes {
            let ui = g_index[*u];
            for v in hh.inner.neighbors(u).unwrap_or_default() {
                let vi = g_index[v];
                let pair = if ui <= vi { (ui, vi) } else { (vi, ui) };
                if !seen_h.insert(pair) {
                    continue;
                }
                if !g_set.contains(&pair) {
                    edges.push(((*u).to_owned(), v.to_owned(), AttrMap::new()));
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
            } else if g._try_add_edges_from_batch(py, data)? {
                // br-r37-c1-ctorbatch (cc): route fresh edge-list construction
                // through the add_edges_from fast batch — the constructor's own
                // edge loop pays per-edge `has_node`/`has_edge`/`maybe_store_adj_key`
                // (z6uka display) that this lean batch avoids (seen_nodes set +
                // batch_display_conflict + lazy mirrors), 4x cheaper.
                // `Graph([(u,v,{..})])` 0.46x->1.8x. The batch is mutation-free on
                // false (graph stays empty), so the iterator loop below still runs
                // for any input it declines (small / non-plain-node / weird tuples).
            } else if let Ok(iter) = PyIterator::from_object(data) {
                // br-r37-c1-d58s8 ctor lever 2: batch the edge-tuple stream
                // through ONE extend_edges_with_attrs_unrecorded call (one
                // ledger record for the batch vs two record_decision per
                // edge) while replicating add_edge's display semantics
                // inline (as-passed node keys via should_store_node_key,
                // z6uka row objects on new cells, lazy mirrors, attr-dict
                // C-level merge). Pending-state sets stand in for
                // inner.has_node/has_edge until the flush; non-edge items
                // flush first so interleaved node insertion order holds.
                let mut edge_batch: Vec<(String, String, AttrMap)> = Vec::new();
                // br-r37-c1-d58s8: node_key_map doubles as the pending-node
                // oracle (entries land inline below), so no separate
                // pending_nodes set — two String clones+hashes per edge
                // saved. pending_cells stays: the z6uka first-touch gate is
                // call-order-sensitive (maybe_store's `differs` check can
                // store a LATER object on dup edges if invoked again).
                let mut pending_cells: std::collections::HashSet<(String, String)> =
                    std::collections::HashSet::new();
                macro_rules! flush_batch {
                    () => {
                        if !edge_batch.is_empty() {
                            let drained: Vec<(String, String, AttrMap)> =
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
                                    let u_was_new = !g.inner.has_node(&u_canonical)
                                        && !g.node_key_map.contains_key(&u_canonical);
                                    let v_was_new = !g.inner.has_node(&v_canonical)
                                        && !g.node_key_map.contains_key(&v_canonical);
                                    if g.should_store_node_key(&u_canonical, u_was_new) {
                                        g.node_key_map
                                            .entry(u_canonical.clone())
                                            .or_insert_with(|| u.clone().unbind());
                                    }
                                    if g.should_store_node_key(&v_canonical, v_was_new) {
                                        g.node_key_map
                                            .entry(v_canonical.clone())
                                            .or_insert_with(|| v.clone().unbind());
                                    }
                                    let cell = if u_canonical <= v_canonical {
                                        (u_canonical.clone(), v_canonical.clone())
                                    } else {
                                        (v_canonical.clone(), u_canonical.clone())
                                    };
                                    if !g.inner.has_edge(&u_canonical, &v_canonical)
                                        && !pending_cells.contains(&cell)
                                    {
                                        g.maybe_store_adj_key(py, &u_canonical, &v_canonical, &v);
                                        if u_canonical != v_canonical {
                                            g.maybe_store_adj_key(
                                                py,
                                                &v_canonical,
                                                &u_canonical,
                                                &u,
                                            );
                                        }
                                        pending_cells.insert(cell);
                                    }
                                    let mut rust_attrs = AttrMap::new();
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
                    // Slow item: flush so node insertion ORDER is preserved,
                    // then run the original per-item semantics verbatim.
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

    /// br-r37-c1-nodekeys: all node DISPLAY objects as a flat Python list in
    /// ONE call. Python ``set(graph)`` / ``set(graph.nodes())`` cross PyO3 per
    /// node (~5x nx on node-set construction); building the Vec in Rust lets
    /// callers like ``non_neighbors`` enumerate every node in a single
    /// boundary crossing. Order = node insertion order (``nodes_ordered``).
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
                    match self.edge_attr_py_value(py, left, right, attr)? {
                        Some(val) => total += val.bind(py).extract::<f64>()?,
                        None => total += 1.0,
                    }
                }
                Ok(total)
            }
        }
    }

    // ---- Node mutation ----

    /// Add a single node with optional attributes.
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
                .or_insert_with(|| node_for_adding.clone().unbind());
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
        if was_new {
            self.node_iter_mirror_insert(py, &canonical)?;
        }
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

    fn _fast_add_int_nodes_range_stop(&mut self, py: Python<'_>, stop: i64) -> PyResult<()> {
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
        for canonical in &canonicals {
            self.node_iter_mirror_insert(py, canonical)?;
        }
        let _ = self.inner.extend_nodes_unrecorded(canonicals);
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
            || self.lazy_int_node_stop != 0
            || !self.node_key_map.is_empty()
            || !self.adj_py_keys.is_empty()
            || !self.node_py_attrs.is_empty()
            || !self.edge_py_attrs.is_empty()
            || !self.adj_row_py.is_empty()
        {
            return Ok(false);
        }

        let Ok(stop) = i64::try_from(node_count) else {
            return Ok(false);
        };
        let edges = collect_index_weight_attr_edges(rows, cols, values, node_count, edge_attr)?;
        let edge_bumps = u64::try_from(edges.len())
            .unwrap_or(u64::MAX)
            .wrapping_add(1);
        let node_bumps = u64::try_from(node_count).unwrap_or(u64::MAX);
        let node_labels: Vec<String> = (0..node_count).map(|node| node.to_string()).collect();

        self.lazy_int_node_stop = stop;
        for canonical in &node_labels {
            self.node_iter_mirror_insert(py, canonical)?;
        }
        let _ = self
            .inner
            .extend_fresh_index_edges_with_attrs_unrecorded(node_labels, edges);
        self.nodes_seq = self.nodes_seq.wrapping_add(node_bumps);
        self.edges_seq = self.edges_seq.wrapping_add(edge_bumps);
        Ok(true)
    }

    fn _fast_add_int_nodes(&mut self, py: Python<'_>, nodes: &Bound<'_, PyAny>) -> PyResult<()> {
        // br-r37-c1-u2jod: bulk fast path for `add_nodes_from(list_of_ints)`,
        // mirroring `_fast_add_int_nodes_range_stop` (lazy attrs + a single
        // unrecorded bulk inner insert) instead of the eager per-node path.
        // Drops (a) the eager `node_py_attrs` PyDict alloc — attrs materialize
        // lazily via `ensure_node_py_attrs` on first access, exactly like the
        // no-attr `add_node` branch — and (b) the per-node recorded
        // `add_node_with_attrs` ledger push, batching the structural insert
        // through `extend_nodes_unrecorded`.
        //
        // Atomic validate-then-mutate: every element must be an EXACT `int`
        // (`is_exact_instance_of::<PyInt>` excludes `bool` — `True`/`1` share a
        // node but the general path keeps the `True` Py object for display, so a
        // bool here must fall back) and fit in i64.  Any other element raises
        // (the Python wrapper then falls back to the general loop) before a
        // single node is touched.  First-occurrence order and first-wins are
        // preserved by keying dedup on `node_key_map`; Py int objects are stored
        // (not lazy keys) to avoid the lazy int canonical/display divergence.
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

    /// br-r37-c1-u2jod: wrapper-facing batch entry for `add_nodes_from`'s sister
    /// `add_edges_from`. DiGraph/MultiGraph already expose this; PyGraph did not,
    /// so the Python wrapper's batch short-circuit never fired for a plain Graph
    /// and EVERY `add_edges_from(list/tuple)` paid the per-edge Python validation
    /// loop before reaching the (already fast) native batch via `raw(...)`.
    ///
    /// Chains the two proven collect-then-commit batches the native
    /// `add_edges_from` uses: the plain (u, v) batch first (cheapest), then the
    /// attributed (u, v, dict) batch. Returns `true` only when the batch fully
    /// replicated valid input — so the wrapper safely skips its validation loop;
    /// any item the batch can't replicate exactly leaves `false` and the wrapper
    /// runs its per-edge loop unchanged (owning all error / partial-prefix
    /// contracts). Byte-identical to the existing path: the wrapper's valid-input
    /// case already routed through these same batches via `raw(materialized)`.
    fn _try_add_edges_from_batch(
        &mut self,
        py: Python<'_>,
        ebunch_to_add: &Bound<'_, PyAny>,
    ) -> PyResult<bool> {
        if self.try_add_plain_edge_batch(py, ebunch_to_add)? {
            return Ok(true);
        }
        self.try_add_attr_edge_batch(py, ebunch_to_add, None)
    }

    /// br-r37-c1-nodebatch: native attributed-node batch for
    /// `add_nodes_from([(n, dict), ...])` (mixed with plain `n`) on a FRESH
    /// simple Graph. The per-node Python loop pays ~3.4x nx on attributed
    /// bulk construction (PyO3 `add_node` + per-key `set_item` per node);
    /// every construction path that rebuilds attributed nodes (relabel /
    /// union / convert / subgraph copy) inherits that tax. One bulk
    /// `extend_nodes_with_attrs_unrecorded` (one ledger record) replaces it.
    /// Returns `false` (NO mutation) for anything outside this shape so the
    /// per-node loop owns every error and partial-prefix contract.
    fn _try_add_nodes_from_batch(
        &mut self,
        py: Python<'_>,
        nodes_to_add: &Bound<'_, PyAny>,
    ) -> PyResult<bool> {
        const NODE_BATCH_MIN: usize = 8;
        // FRESH gate: no existing nodes/edges/mirror state, so a batch never
        // has to merge into pre-existing storage (appends to a non-empty graph
        // fall through to the per-node loop).
        if self.inner.node_count() != 0
            || self.inner.edge_count() != 0
            || !self.adj_row_py.is_empty()
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
        let mirror_key = self.py_node_key(py, &canonical);

        // surgically remove attributes for incident edges before removing node from inner graph
        let mut had_incident_edges = false;
        let neighbors = self
            .inner
            .neighbors(&canonical)
            .map(|neighbors| neighbors.into_iter().map(str::to_owned).collect::<Vec<_>>());
        if let Some(neighbors) = &neighbors {
            for nb in neighbors {
                let ek = Self::edge_key(&canonical, nb);
                self.edge_py_attrs.remove(&ek);
                self.cached_adj_remove_key(py, nb, &canonical)?;
                had_incident_edges = true;
            }
        }

        self.inner.remove_node(&canonical);
        self.node_iter_mirror_remove_key(py, mirror_key.bind(py));
        self.node_key_map.remove(&canonical);
        self.node_py_attrs.remove(&canonical);
        if !self.adj_py_keys.is_empty() {
            // br-r37-c1-z6uka: drop adjacency-row overrides touching the
            // removed node.
            self.adj_py_keys
                .retain(|(a, b), _| a != &canonical && b != &canonical);
        }
        self.adj_row_py.remove(&canonical);
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
        for canonical in &present {
            if let Some(neighbors) = self
                .inner
                .neighbors(canonical)
                .map(|neighbors| neighbors.into_iter().map(str::to_owned).collect::<Vec<_>>())
            {
                for nb in neighbors {
                    self.cached_adj_remove_key(py, &nb, canonical)?;
                }
            }
        }
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
            let mirror_key = self.py_node_key(py, canonical);
            self.node_iter_mirror_remove_key(py, mirror_key.bind(py));
            self.node_key_map.remove(canonical);
            self.node_py_attrs.remove(canonical);
            self.adj_row_py.remove(canonical);
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
            if u_was_new {
                self.node_iter_mirror_insert(py, &u_canonical)?;
            }
            if v_was_new {
                self.node_iter_mirror_insert(py, &v_canonical)?;
            }
            self.bump_nodes_seq();
        }
        // br-r37-c1-z6uka: a NEW edge creates both adjacency cells with
        // the objects passed in THIS call (nx `_adj[u][v] = ...` /
        // `_adj[v][u] = ...`); existing cells keep their original object.
        // For a SELF-LOOP both nx assignments hit the same dict cell and
        // the second cannot replace the hash-equal key — only v's object
        // applies (shrunk repro: add_edge(12.0, 12) renders (12, 12)).
        let was_new_edge = !self.inner.has_edge(&u_canonical, &v_canonical);
        if was_new_edge {
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
            .add_edge_with_attrs(u_canonical.clone(), v_canonical.clone(), rust_attrs)
            .map_err(|e| NetworkXError::new_err(e.to_string()))?;
        if was_new_edge && !self.adj_row_py.is_empty() {
            self.cached_adj_set_edge(py, &u_canonical, &v_canonical)?;
            if u_canonical != v_canonical {
                self.cached_adj_set_edge(py, &v_canonical, &u_canonical)?;
            }
        }
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
        // br-r37-c1-d58s8: global **attr now batches too (was the 7x
        // residual: nx merge order = global first, per-edge overrides).
        if self.try_add_attr_edge_batch(py, ebunch_to_add, attr)? {
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
        for pair in flat.as_chunks::<2>().0 {
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

            let was_new_edge = !self.inner.has_edge(&u_s, &v_s);
            let _ = self
                .inner
                .add_edge_with_attrs(u_s.clone(), v_s.clone(), empty_attrs.clone());
            if was_new_edge && !self.adj_row_py.is_empty() {
                self.cached_adj_set_edge(py, &u_s, &v_s)?;
                if u_s != v_s {
                    self.cached_adj_set_edge(py, &v_s, &u_s)?;
                }
            }
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
        let py_u_key = self.py_adj_key(py, &v_canonical, &u_canonical);
        let py_v_key = self.py_adj_key(py, &u_canonical, &v_canonical);
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
        if let Some(row) = self.adj_row_py.get(&u_canonical) {
            let _ = row.bind(py).del_item(py_v_key);
        }
        if u_canonical != v_canonical
            && let Some(row) = self.adj_row_py.get(&v_canonical)
        {
            let _ = row.bind(py).del_item(py_u_key);
        }
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
            let py_u_key = self.py_adj_key(py, &v_c, &u_c);
            let py_v_key = self.py_adj_key(py, &u_c, &v_c);
            self.inner.remove_edge(&u_c, &v_c);
            let ek = Self::edge_key(&u_c, &v_c);
            self.edge_py_attrs.remove(&ek);
            if let Some(row) = self.adj_row_py.get(&u_c) {
                let _ = row.bind(py).del_item(py_v_key);
            }
            if u_c != v_c
                && let Some(row) = self.adj_row_py.get(&v_c)
            {
                let _ = row.bind(py).del_item(py_u_key);
            }
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
        self.adj_row_py.clear();
        self.graph_attrs = PyDict::new(py).unbind();
        self.node_iter_mirror_clear(py)?;
        self.bump_nodes_seq();
        self.bump_edges_seq(); // br-r37-c1-jft0i
        Ok(())
    }

    /// Remove all edges but keep nodes and their attributes.
    fn clear_edges(&mut self, py: Python<'_>) -> PyResult<()> {
        // br-r37-c1-clearedgesinplace (cc): drop edges IN PLACE via the native
        // Graph::clear_edges (edges + endpoints + adj_indices rows, keeping nodes).
        // The prior path rebuilt a fresh Graph with a per-node add_node_with_attrs
        // loop — that paid the ledger record_decision tax + a node-attr clone per
        // node + the old-inner drop, measuring ~0.05x vs nx (20x slower) on a
        // 2000-node/16000-edge graph. In-place clear is O(E)+O(V), no rebuild/clone/
        // ledger. Nodes (index, order, attrs) are untouched, so all node-side mirrors
        // stay valid; edge-side mirrors are cleared exactly as before.
        self.inner.clear_edges();
        self.edge_py_attrs.clear();
        self.adj_py_keys.clear(); // br-r37-c1-z6uka
        self.cached_adj_clear_edges_in_place(py)?;
        self.bump_edges_seq(); // br-r37-c1-jft0i
        Ok(())
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
        // cc-hasedgeintidx: identity-int fast path. `G.has_edge(u, v)` on int nodes
        // otherwise pays 2 `i.to_string()` heap allocs + 2 String-hash
        // `get_index_of` (vs nx's 2 int-dict lookups). When u and v are EXACT ints
        // (bool excluded: it's an int subclass with canonical "0"/"1") that fit in
        // usize AND the node stored at each index IS that int (verified per call —
        // any removal / re-add / remap that broke index==value fails the check and
        // falls through), resolve the edge straight by index: no alloc, no String
        // hash. `node_index_matches_int` is O(1) index access + a no-alloc parse.
        if u.is_exact_instance_of::<PyInt>()
            && v.is_exact_instance_of::<PyInt>()
            && let Ok(iu) = u.extract::<usize>()
            && let Ok(iv) = v.extract::<usize>()
            && self.inner.node_index_matches_int(iu)
            && self.inner.node_index_matches_int(iv)
        {
            return Ok(self.inner.has_edge_by_indices(iu, iv));
        }
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

    /// br-r37-c1-snabulk: bulk set_node_attributes(values, name) — one
    /// Rust loop over the values dict instead of the Python wrapper's
    /// per-node has_node + G.nodes[n] materialization + setitem (3 PyO3
    /// round-trips/node). node_py_attrs is the authoritative node-attr
    /// store (inner is refreshed from it at copy/export), so updating
    /// the mirror dict matches the single-set path exactly. Missing
    /// nodes are skipped (nx catches the KeyError).
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
                let dict = self.materialize_edge_py_attrs(py, &u, &v);
                dict.bind(py).set_item(name, &val)?;
            }
        }
        self.mark_edges_dirty();
        Ok(())
    }

    /// br-r37-c1-seabulk-dict (cc): native bulk set_edge_attributes(values)
    /// for the DICT-OF-DICTS form ({(u,v): {attr: val, ...}}, no name). The
    /// Python wrapper otherwise loops `_edge_attribute_dict(G, edge).update(d)`,
    /// where `_edge_attribute_dict` resolves `G[u][v]` — a full EdgeAttrDict
    /// VIEW construction per edge (~0.06x vs nx's plain `G._adj[u][v].update`).
    /// One Rust pass: materialize the edge_py_attrs mirror directly and
    /// `.update(d)` it, mark edges dirty ONCE so the lazy inner flush reaches
    /// the kernels. Non-2-tuple keys / missing edges skipped (matching the
    /// wrapper's KeyError/ValueError swallow). Simple graphs only.
    fn _native_set_edge_attributes_dict(
        &mut self,
        py: Python<'_>,
        values: &Bound<'_, PyDict>,
    ) -> PyResult<()> {
        for (k, attrs) in values.iter() {
            let Ok(len) = k.len() else { continue };
            if len != 2 {
                continue;
            }
            let u = node_key_to_string(py, &k.get_item(0)?)?;
            let v = node_key_to_string(py, &k.get_item(1)?)?;
            if self.inner.has_edge(&u, &v) {
                let dict = self.materialize_edge_py_attrs(py, &u, &v);
                dict.bind(py).call_method1("update", (&attrs,))?;
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

    /// br-r37-c1-snabulk-dict (cc): native bulk set_node_attributes(values) for
    /// the DICT-OF-DICTS form ({node: {attr: val, ...}}, no name). The Python
    /// wrapper otherwise loops `G.nodes[node].update(d)` — a NodeView
    /// __getitem__ PyO3 round-trip per node (~0.27x vs nx's plain dict update).
    /// One Rust pass; node_py_attrs is the authoritative store, so entry() keeps
    /// any existing attrs and `.update(d)` merges (no store/mirror split like
    /// edges). Missing nodes skipped (matching the wrapper's has_node gate).
    fn _native_set_node_attributes_dict(
        &mut self,
        py: Python<'_>,
        values: &Bound<'_, PyDict>,
    ) -> PyResult<()> {
        for (k, attrs) in values.iter() {
            let canonical = node_key_to_string(py, &k)?;
            if self.inner.has_node(&canonical) {
                let dict = self
                    .node_py_attrs
                    .entry(canonical)
                    .or_insert_with(|| PyDict::new(py).unbind());
                dict.bind(py).call_method1("update", (&attrs,))?;
            }
        }
        Ok(())
    }

    // br-r37-c1-setattrbcast (cc): native BROADCAST of one attr value onto EVERY
    // node. The Python `set_node_attributes(G, scalar, name)` path looped
    // `for n in G.nodes(): G.nodes[n][name] = value`, paying a NodeView __getitem__
    // PyO3 round-trip per node (~0.22x vs nx). One Rust pass over node order,
    // entry-or-insert the mirror, set_item directly — node_py_attrs is authoritative.
    fn _native_broadcast_node_attribute(
        &mut self,
        py: Python<'_>,
        name: &str,
        value: &Bound<'_, PyAny>,
    ) -> PyResult<()> {
        let nodes: Vec<String> = self
            .inner
            .nodes_ordered()
            .iter()
            .map(|s| (*s).to_owned())
            .collect();
        for canonical in nodes {
            // materialize_node_py_attrs populates any store-only attrs into the
            // mirror first (matching the Python `G.nodes[n]` full-dict read),
            // so a pre-existing attr is preserved alongside the new one.
            // (br-r37-c1-syncdirty buildfix: PyGraph has materialize_node_py_attrs,
            // not ensure_node_py_attrs — the latter is PyMultiGraph-only and broke
            // the build when 0b2df6108 landed this method.)
            let dict = self.materialize_node_py_attrs(py, &canonical);
            dict.bind(py).set_item(name, value)?;
        }
        Ok(())
    }

    // br-r37-c1-setattrbcast (cc): native BROADCAST onto EVERY edge. The Python
    // path looped `for u,v,attrs in G.edges(data=True): attrs[name] = value`
    // (~0.39x). One Rust pass: materialize each edge mirror, set_item, mark dirty
    // (so the lazy store flush reaches the native kernels), exactly as the dict
    // scalar setter does.
    fn _native_broadcast_edge_attribute(
        &mut self,
        py: Python<'_>,
        name: &str,
        value: &Bound<'_, PyAny>,
    ) -> PyResult<()> {
        // cc-broadcastattrmirror: when the edge-attr mirror is COMPLETE (one PyDict
        // per edge — the common state, since a simple Graph populates edge_py_attrs
        // eagerly), set the attribute straight on each mirror dict. The general path
        // below collects an `edges_ordered()` Vec of owned (String, String) pairs
        // (2 String clones/edge) and re-derives each edge's (String, String, usize)
        // mirror key to `materialize_edge_py_attrs` (hash 2 Strings/edge) — pure
        // overhead when the dict already exists. Iterating `edge_py_attrs.values()`
        // skips both; the result is byte-identical (same PyDict objects, same
        // set_item append) and order-independent (same scalar on every edge). Gated
        // on len == edge_count so a lazy/partial mirror (which would MISS edges)
        // falls through to the exact per-edge materialize path.
        if self.edge_py_attrs.len() == self.inner.edge_count() {
            for dict in self.edge_py_attrs.values() {
                dict.bind(py).set_item(name, value)?;
            }
            self.mark_edges_dirty();
            return Ok(());
        }
        let edges: Vec<(String, String)> = self
            .inner
            .edges_ordered()
            .into_iter()
            .map(|e| (e.left, e.right))
            .collect();
        for (u, v) in edges {
            let dict = self.materialize_edge_py_attrs(py, &u, &v);
            dict.bind(py).set_item(name, value)?;
        }
        self.mark_edges_dirty();
        Ok(())
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

    /// br-r37-c1-bipcolor-native (cc): native CSR stack-BFS 2-coloring for
    /// bipartite.color. Replaces the Python `dict(_native_adjacency_keys())`
    /// snapshot (~39% of the call) + Python stack-BFS with a single integer-index
    /// pass. Each node's color is the parity of its BFS distance from its
    /// component's first node (root colored 1), which is identical to networkx —
    /// the root is the first uncolored non-isolate node in node order (matches nx)
    /// and parity is order-INVARIANT, so fnx's sorted adjacency is safe. Returns
    /// `{node: 0|1}` (discovery order, isolates=0 appended); raises NetworkXError
    /// on an odd cycle / self-loop, exactly as nx.
    fn _native_bipartite_color(&self, py: Python<'_>) -> PyResult<PyObject> {
        let n = self.inner.node_count();
        let keys = self.cached_node_key_vec(py);
        let mut color = vec![-1i8; n];
        let dict = pyo3::types::PyDict::new(py);
        for s in 0..n {
            if color[s] != -1 || self.inner.degree_by_index(s) == 0 {
                continue;
            }
            color[s] = 1;
            dict.set_item(&keys[s], 1)?;
            let mut stack = vec![s];
            while let Some(v) = stack.pop() {
                let cv = color[v];
                let c = 1 - cv;
                if let Some(nbrs) = self.inner.neighbors_indices(v) {
                    for &w in nbrs {
                        if color[w] != -1 {
                            if color[w] == cv {
                                return Err(NetworkXError::new_err("Graph is not bipartite."));
                            }
                        } else {
                            color[w] = c;
                            dict.set_item(&keys[w], c)?;
                            stack.push(w);
                        }
                    }
                }
            }
        }
        // Isolates colored 0, appended in node order — matches networkx's
        // `color.update(dict.fromkeys(isolates, 0))`.
        for (s, key) in keys.iter().enumerate().take(n) {
            if self.inner.degree_by_index(s) == 0 {
                dict.set_item(key, 0)?;
            }
        }
        Ok(dict.into_any().unbind())
    }

    /// br-r37-c1-degnbnative (cc): one-pass (node_obj, degree) pairs for a node
    /// subset (degree(nbunch) unweighted total). Replaces the Python
    /// `[n for n in nbunch if n in G]` membership filter + per-node `raw[n]` degree
    /// lookup (two per-element passes, each its own PyO3 round-trip) with a single
    /// PyO3 call that canonicalizes once, filters absent nodes, and reads
    /// degree_by_index. Errors (unhashable / non-iterable nbunch) propagate so the
    /// Python wrapper maps them to NetworkXError, matching the prior filter.
    fn _native_degree_pairs_subset(
        &self,
        py: Python<'_>,
        nbunch: &Bound<'_, PyAny>,
    ) -> PyResult<Vec<(PyObject, usize)>> {
        let mut out: Vec<(PyObject, usize)> = Vec::new();
        for item in nbunch.try_iter()? {
            let node = item?;
            // nx's degree(nbunch) raises NetworkXError on an unhashable element;
            // raise a TypeError carrying that exact message (str(node)) so the
            // Python wrapper re-raises it as NetworkXError, matching the prior loop.
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
                out.push((node.clone().unbind(), self.inner.degree_by_index(idx)));
            }
        }
        Ok(out)
    }

    /// Build `generate_adjlist` body lines without a Python adjacency-row snapshot.
    fn _native_generate_adjlist_lines(
        &self,
        py: Python<'_>,
        delimiter: &str,
    ) -> PyResult<Vec<String>> {
        let nodes: Vec<String> = self
            .inner
            .nodes_ordered()
            .into_iter()
            .map(str::to_owned)
            .collect();
        let mut lines = Vec::with_capacity(nodes.len());
        let mut seen: HashSet<String> = HashSet::with_capacity(nodes.len());
        for node in &nodes {
            let py_node = self.py_node_key(py, node);
            let mut line = py_node.bind(py).str()?.to_str()?.to_owned();
            for neighbor in self.inner.neighbors(node).unwrap_or_default() {
                if seen.contains(neighbor) {
                    continue;
                }
                line.push_str(delimiter);
                let py_neighbor = self.py_adj_key(py, node, neighbor);
                line.push_str(py_neighbor.bind(py).str()?.to_str()?);
            }
            seen.insert(node.clone());
            lines.push(line);
        }
        Ok(lines)
    }

    #[pyo3(name = "_native_adjacency_row_dict")]
    fn native_adjacency_row_dict(
        &mut self,
        py: Python<'_>,
        node: &Bound<'_, PyAny>,
    ) -> PyResult<Py<PyDict>> {
        let canonical = node_key_to_string(py, node)?;
        if !self.inner.has_node(&canonical) {
            return Err(missing_key_error(node));
        }
        if let Some(row) = self.adj_row_py.get(&canonical) {
            return Ok(row.clone_ref(py));
        }
        let row = PyDict::new(py);
        let neighbors: Vec<String> = self
            .inner
            .neighbors(&canonical)
            .unwrap_or_default()
            .into_iter()
            .map(str::to_owned)
            .collect();
        if !neighbors.is_empty() {
            self.mark_edges_dirty();
        }
        for neighbor in neighbors {
            let py_neighbor = self.py_adj_key(py, &canonical, &neighbor);
            let attrs = self.materialize_edge_py_attrs(py, &canonical, &neighbor);
            row.set_item(py_neighbor, attrs.bind(py))?;
        }
        let row = row.unbind();
        self.adj_row_py.insert(canonical, row.clone_ref(py));
        Ok(row)
    }

    /// br-r37-c1-zt6lj: true when the internal canonical node strings are also
    /// the Python display strings used by `generate_adjlist`. In that shape the
    /// existing Rust readwrite serializer is byte-body identical and can avoid
    /// the Python generator path; mixed/custom Python node keys fall back.
    fn _native_adjlist_canonical_body_safe(&self) -> bool {
        self.node_key_map.is_empty() && self.adj_py_keys.is_empty()
    }

    fn _native_has_adj_py_keys(&self) -> bool {
        !self.adj_py_keys.is_empty()
    }

    fn _native_is_complete_unweighted_graph(
        &self,
        py: Python<'_>,
        weight: Option<&str>,
    ) -> PyResult<bool> {
        let node_count = self.inner.node_count();
        if node_count == 0 {
            return Ok(false);
        }
        if self.inner.edge_count() != node_count * (node_count - 1) / 2 {
            return Ok(false);
        }
        for idx in 0..node_count {
            if self.inner.degree_by_index(idx) != node_count - 1 {
                return Ok(false);
            }
        }
        let Some(weight_key) = weight else {
            return Ok(true);
        };
        for (_, _, attrs) in self.inner.edges_storage_order_index_iter() {
            if attrs.contains_key(weight_key) {
                return Ok(false);
            }
        }
        for attrs in self.edge_py_attrs.values() {
            if attrs.bind(py).get_item(weight_key)?.is_some() {
                return Ok(false);
            }
        }
        Ok(true)
    }

    fn _native_complete_bipartite_certificate_parts(
        &self,
        weight: Option<&str>,
        nodes_seq: u64,
        edges_seq: u64,
        left_size: usize,
        right_size: usize,
    ) -> Option<(usize, usize)> {
        let node_count = self.inner.node_count();
        if self.nodes_seq != nodes_seq
            || self.edges_seq != edges_seq
            || left_size == 0
            || right_size == 0
            || left_size.checked_add(right_size) != Some(node_count)
            || left_size.checked_mul(right_size) != Some(self.inner.edge_count())
        {
            return None;
        }
        if weight.is_some() && self.edges_dirty.load(Ordering::Relaxed) {
            return None;
        }
        Some((left_size, right_size))
    }

    fn _native_complete_bipartite_unweighted_parts(
        &self,
        py: Python<'_>,
        weight: Option<&str>,
    ) -> PyResult<Option<(usize, usize)>> {
        let node_count = self.inner.node_count();
        let edge_count = self.inner.edge_count();
        if node_count < 2 || edge_count == 0 {
            return Ok(None);
        }

        let mut colors = vec![u8::MAX; node_count];
        let mut stack = Vec::with_capacity(node_count);
        colors[0] = 0;
        stack.push(0_usize);
        while let Some(node_idx) = stack.pop() {
            let next_color = 1 - colors[node_idx];
            let Some(neighbors) = self.inner.neighbors_indices(node_idx) else {
                return Ok(None);
            };
            for &neighbor_idx in neighbors {
                let color = colors[neighbor_idx];
                if color == u8::MAX {
                    colors[neighbor_idx] = next_color;
                    stack.push(neighbor_idx);
                } else if color != next_color {
                    return Ok(None);
                }
            }
        }
        if colors.contains(&u8::MAX) {
            return Ok(None);
        }

        let left_size = colors.iter().filter(|&&color| color == 0).count();
        let right_size = node_count - left_size;
        if left_size == 0
            || right_size == 0
            || left_size.checked_mul(right_size) != Some(edge_count)
        {
            return Ok(None);
        }
        for (idx, color) in colors.iter().copied().enumerate() {
            let expected_degree = if color == 0 { right_size } else { left_size };
            if self.inner.degree_by_index(idx) != expected_degree {
                return Ok(None);
            }
        }

        let Some(weight_key) = weight else {
            return Ok(Some((left_size, right_size)));
        };
        for (_, _, attrs) in self.inner.edges_storage_order_index_iter() {
            if attrs.contains_key(weight_key) {
                return Ok(None);
            }
        }
        for attrs in self.edge_py_attrs.values() {
            if attrs.bind(py).get_item(weight_key)?.is_some() {
                return Ok(None);
            }
        }
        Ok(Some((left_size, right_size)))
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

    /// br-cc-nbunchbulk: bulk nbunch filter — the in-graph members of `nbunch`, in
    /// order, as the ORIGINAL objects (== nx `nbunch_iter`). One Python->Rust
    /// crossing for the whole (re-iterable list/tuple/set) nbunch instead of the
    /// per-node `n in self.adj` the Python generator pays (each of which crosses the
    /// PyO3 boundary + allocates a canonical String). An EXACT int sitting at its own
    /// index is present with NO String work (`node_index_matches_int`). Returns None
    /// (-> the Python lazy generator, which raises nx's exact NetworkXError) on the
    /// first unhashable element, so error semantics stay byte-identical. Caller must
    /// only pass a re-iterable nbunch (a one-shot generator would be half-consumed
    /// before the None fallback).
    fn _nbunch_present(
        &self,
        py: Python<'_>,
        nbunch: &Bound<'_, PyAny>,
    ) -> PyResult<Option<Vec<PyObject>>> {
        let mut out: Vec<PyObject> = Vec::new();
        for item in nbunch.try_iter()? {
            let item = item?;
            if item.hash().is_err() {
                return Ok(None);
            }
            if item.is_exact_instance_of::<PyInt>()
                && let Ok(i) = item.extract::<usize>()
                && self.inner.node_index_matches_int(i)
            {
                out.push(item.clone().unbind());
                continue;
            }
            let canonical = node_key_to_string(py, &item)?;
            if self.inner.has_node(&canonical) {
                out.push(item.clone().unbind());
            }
        }
        Ok(Some(out))
    }

    /// Iterate over nodes (called by ``for n in G``).
    fn __iter__(slf: PyRef<'_, Self>) -> PyResult<PyObject> {
        let py = slf.py();
        let mirror = slf.node_iter_mirror_or_init(py)?;
        Ok(mirror.bind(py).call_method0("__iter__")?.unbind())
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
            adj_row_py: HashMap::new(),
            graph_attrs: self.graph_attrs.bind(py).copy()?.unbind(),
            nodes_seq: 0,
            edges_seq: 0,
            // Edge-attr staleness IS tracked by `edges_dirty`; propagate it so a
            // dirty source yields a copy that reconciles `inner` from the copied
            // Python dicts on the next native read (same contract as the source).
            edges_dirty: AtomicBool::new(self.edges_dirty.load(Ordering::Relaxed)),
            node_keys_cache: std::sync::Mutex::new(None),
            node_iter_mirror: std::sync::Mutex::new(None),
            node_data_mirror: std::sync::Mutex::new(None),
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
            adj_row_py: HashMap::new(),
            graph_attrs: self.graph_attrs.bind(py).copy()?.unbind(),
            nodes_seq: 0,
            edges_seq: 0,
            edges_dirty: AtomicBool::new(false),
            node_keys_cache: std::sync::Mutex::new(None),
            node_iter_mirror: std::sync::Mutex::new(None),
            node_data_mirror: std::sync::Mutex::new(None),
        };

        // Add kept nodes using the existing HashSet iteration behavior; only
        // node-key materialization changes for sparse range fast-path keys.
        // br-r37-c1-tbh4q: single-pass attr crossing (with_mirror) — the induced
        // subgraph keeps each node/edge once (no merge), so the Rust AttrMap +
        // Python mirror can be built in ONE dict pass instead of
        // py_dict_to_attr_map + dict.copy(). Mirror is byte-identical to .copy().
        for canonical in &keep {
            new_graph
                .node_key_map
                .insert(canonical.clone(), self.py_node_key(py, canonical));
            match self.node_py_attrs.get(canonical) {
                Some(attrs) => {
                    let (rust_attrs, mirror) = py_dict_to_attr_map_with_mirror(py, attrs.bind(py))?;
                    new_graph
                        .inner
                        .add_node_with_attrs(canonical.clone(), rust_attrs);
                    new_graph.node_py_attrs.insert(canonical.clone(), mirror);
                }
                None => {
                    new_graph
                        .inner
                        .add_node_with_attrs(canonical.clone(), AttrMap::new());
                }
            }
        }

        // Add edges where both endpoints are in the subgraph.
        for (u, v, attrs) in self.inner.edges_ordered_borrowed() {
            if keep.contains(u) && keep.contains(v) {
                let key = Self::edge_key(u, v);
                match self.edge_py_attrs.get(&key) {
                    Some(py_attrs) => {
                        let (rust_attrs, mirror) =
                            py_dict_to_attr_map_with_mirror(py, py_attrs.bind(py))?;
                        let _ = new_graph.inner.add_edge_with_attrs(
                            u.to_owned(),
                            v.to_owned(),
                            rust_attrs,
                        );
                        new_graph.edge_py_attrs.insert(key, mirror);
                    }
                    None => {
                        // No Python mirror -> reuse the Rust edge attrs directly.
                        let _ = new_graph.inner.add_edge_with_attrs(
                            u.to_owned(),
                            v.to_owned(),
                            attrs.clone(),
                        );
                    }
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
            adj_row_py: HashMap::new(),
            graph_attrs: self.graph_attrs.bind(py).copy()?.unbind(),
            nodes_seq: 0,
            edges_seq: 0,
            edges_dirty: AtomicBool::new(false),
            node_keys_cache: std::sync::Mutex::new(None),
            node_iter_mirror: std::sync::Mutex::new(None),
            node_data_mirror: std::sync::Mutex::new(None),
        };

        // Collect nodes from kept edges
        let mut nodes_needed: std::collections::HashSet<String> = std::collections::HashSet::new();
        for (u, v) in &keep_edges {
            nodes_needed.insert(u.clone());
            nodes_needed.insert(v.clone());
        }

        // Add nodes using the existing HashSet iteration behavior; only
        // node-key materialization changes for sparse range fast-path keys.
        // br-r37-c1-tbh4q: single-pass attr crossing (with_mirror) — edge
        // subgraph keeps each node/edge once (no merge); mirror is shallow-copy
        // byte-identical to .copy(); unconditional node_key_map insert preserved.
        for canonical in &nodes_needed {
            match self.node_py_attrs.get(canonical) {
                Some(attrs) => {
                    let (rust_attrs, mirror) = py_dict_to_attr_map_with_mirror(py, attrs.bind(py))?;
                    new_graph
                        .inner
                        .add_node_with_attrs(canonical.clone(), rust_attrs);
                    new_graph.node_py_attrs.insert(canonical.clone(), mirror);
                }
                None => {
                    new_graph
                        .inner
                        .add_node_with_attrs(canonical.clone(), AttrMap::new());
                }
            }
            new_graph
                .node_key_map
                .insert(canonical.clone(), self.py_node_key(py, canonical));
        }

        // Add edges
        for (u, v) in &keep_edges {
            match self.edge_py_attrs.get(&(u.clone(), v.clone())) {
                Some(attrs) => {
                    let (rust_attrs, mirror) = py_dict_to_attr_map_with_mirror(py, attrs.bind(py))?;
                    let _ = new_graph
                        .inner
                        .add_edge_with_attrs(u.clone(), v.clone(), rust_attrs);
                    new_graph
                        .edge_py_attrs
                        .insert((u.clone(), v.clone()), mirror);
                }
                None => {
                    let _ =
                        new_graph
                            .inner
                            .add_edge_with_attrs(u.clone(), v.clone(), AttrMap::new());
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

        // br-r37-c1-tbh4q: single-pass attr crossing (with_mirror) on the
        // to_directed node loop — each node once (no merge), mirror byte-identical
        // to .copy(), unconditional node_key_map insert preserved.
        for canonical in self.inner.nodes_ordered() {
            match self.node_py_attrs.get(canonical) {
                Some(attrs) => {
                    let (rust_attrs, mirror) = py_dict_to_attr_map_with_mirror(py, attrs.bind(py))?;
                    dg.inner
                        .add_node_with_attrs(canonical.to_owned(), rust_attrs);
                    dg.node_py_attrs.insert(canonical.to_owned(), mirror);
                }
                None => {
                    dg.inner
                        .add_node_with_attrs(canonical.to_owned(), AttrMap::new());
                }
            }
            dg.node_key_map
                .insert(canonical.to_owned(), self.py_node_key(py, canonical));
        }

        // br-r37-c1-todirborrow (cc): iterate edges_ordered_borrowed (no per-edge
        // EdgeSnapshot left/right String + attrs clones) and clone the BORROWED
        // AttrMap once per direction. The old path used edges_ordered() (snapshot
        // clones) THEN edge.attrs.clone() THEN rust_attrs.clone() = one wasted
        // AttrMap clone + 2 wasted String clones per edge. The mirror edge_key
        // probe runs only when the edge mirror is non-pristine.
        let mirror_pristine = self.edge_py_attrs.is_empty();
        for (u, v, attrs) in self.inner.edges_ordered_borrowed() {
            let py_attrs_copy = if mirror_pristine {
                None
            } else {
                let ek = PyGraph::edge_key(u, v);
                match self.edge_py_attrs.get(&ek) {
                    Some(py_attrs) => Some(py_attrs.bind(py).copy()?.unbind()),
                    None => None,
                }
            };

            dg.inner
                .add_edge_with_attrs(u.to_owned(), v.to_owned(), attrs.clone())
                .map_err(|e| crate::NetworkXError::new_err(e.to_string()))?;
            if u != v {
                dg.inner
                    .add_edge_with_attrs(v.to_owned(), u.to_owned(), attrs.clone())
                    .map_err(|e| crate::NetworkXError::new_err(e.to_string()))?;
            }

            if let Some(pa) = py_attrs_copy {
                dg.edge_py_attrs
                    .insert((u.to_owned(), v.to_owned()), pa.clone_ref(py));
                if u != v {
                    dg.edge_py_attrs.insert((v.to_owned(), u.to_owned()), pa);
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
    /// br-r37-c1-l5ve7: canonical-key disjointness test for union's
    /// precondition — the Python `set(G).isdisjoint(H)` built full
    /// PyObject sets (~24ms on 3k+3k nodes); this walks the smaller
    /// graph's canonical keys against the larger's index.
    fn _native_nodes_disjoint(&self, other: PyRef<'_, Self>) -> bool {
        let (small, large) = if self.inner.node_count() <= other.inner.node_count() {
            (&self.inner, &other.inner)
        } else {
            (&other.inner, &self.inner)
        };
        small.nodes_ordered().iter().all(|n| !large.has_node(n))
    }

    /// br-r37-c1-l5ve7: native compose for the exact Graph x Graph case
    /// (also serves union once the wrapper's disjointness check passes —
    /// the outputs coincide on disjoint inputs). nx compose_all
    /// semantics: per graph, graph.update / add_nodes_from(data) /
    /// add_edges_from(data) — H's attr values WIN on overlap via
    /// datadict.update; first-insert keeps G's display objects; H's new
    /// neighbors append to existing rows. Construction-tax recipe
    /// throughout (bulk extend_* merge on duplicates == nx update).
    fn _native_compose(&self, py: Python<'_>, other: PyRef<'_, Self>) -> PyResult<Py<Self>> {
        let mut g =
            Self::new_empty_with_policy(py, fnx_runtime::RuntimePolicy::new(self.inner.mode()))?;
        let merged_graph_attrs = PyDict::new(py);
        merged_graph_attrs.update(self.graph_attrs.bind(py).as_mapping())?;
        merged_graph_attrs.update(other.graph_attrs.bind(py).as_mapping())?;
        g.graph_attrs = merged_graph_attrs.unbind();
        for (part_idx, part) in [self, &*other].into_iter().enumerate() {
            let nodes = part.inner.nodes_ordered();
            // node index map: lets the per-walk edge dedup run on (usize,
            // usize) pairs instead of allocating String pairs per edge.
            // nodes newly inserted by THIS part: their result display
            // object is THIS part's object by construction, so the
            // first-touch row store is a guaranteed no-op when the part
            // carries no row overrides — skip the per-edge PyObject work.
            let mut new_this_part: Vec<bool> = vec![false; nodes.len()];
            let mut node_batch: Vec<(String, fnx_classes::AttrMap)> =
                Vec::with_capacity(nodes.len());
            for (i, node) in nodes.iter().enumerate() {
                if let Some(attrs) = part.node_py_attrs.get(*node) {
                    if let Some(existing) = g.node_py_attrs.get(*node) {
                        // overlap: later graph's values win (dict update)
                        existing.bind(py).update(attrs.bind(py).as_mapping())?;
                    } else {
                        g.node_py_attrs
                            .insert((*node).to_owned(), attrs.bind(py).copy()?.unbind());
                    }
                }
                if let std::collections::hash_map::Entry::Vacant(e) =
                    g.node_key_map.entry((*node).to_owned())
                {
                    e.insert(part.py_node_key(py, node));
                    new_this_part[i] = true;
                }
                node_batch.push((
                    (*node).to_owned(),
                    part.inner.node_attrs(node).cloned().unwrap_or_default(),
                ));
            }
            g.inner.extend_nodes_with_attrs_unrecorded(node_batch);
            let part_rows_clean = part.adj_py_keys.is_empty();
            let mut edge_batch: Vec<(String, String, fnx_classes::AttrMap)> = Vec::new();
            let mut seen_this_walk: std::collections::HashSet<(usize, usize)> =
                std::collections::HashSet::new();
            // br-r37-c1-d58s8 accessor audit: walk the part's INTEGER rows
            // (part-local indices from enumeration; zero String hashing
            // per edge) and pre-resolve each part node's index in SELF
            // once (the per-edge has_edge(u, v) paid two node probes
            // post-flip).
            let self_idx: Vec<Option<usize>> =
                nodes.iter().map(|n| self.inner.get_node_index(n)).collect();
            for (ui, u) in nodes.iter().enumerate() {
                for &vi in part.inner.neighbors_indices(ui).unwrap_or(&[]) {
                    let v = nodes[vi];
                    if !seen_this_walk.insert((ui.min(vi), ui.max(vi))) {
                        continue; // each undirected edge once per walk
                    }
                    // first-touch row store: cells created by the FIRST
                    // part keep its objects, so the second part only
                    // stores for cells G does not already have. The store
                    // is also a guaranteed no-op (skippable) when this
                    // part has no row overrides AND both endpoints'
                    // result display objects came from this part
                    // (identity holds in maybe_store's comparison).
                    let store_needed = !(part_rows_clean && new_this_part[ui] && new_this_part[vi]);
                    let first_touch = part_idx == 0
                        || match (self_idx[ui], self_idx[vi]) {
                            (Some(si), Some(ti)) => {
                                self.inner.edge_attrs_by_indices(si, ti).is_none()
                            }
                            _ => true,
                        };
                    if first_touch && store_needed {
                        // first touch ACROSS graphs: store this walk's objects
                        let v_obj = part.py_adj_key(py, u, v);
                        g.maybe_store_adj_key(py, u, v, v_obj.bind(py));
                        let u_obj = part.py_node_key(py, u);
                        g.maybe_store_adj_key(py, v, u, u_obj.bind(py));
                    }
                    // attr-less fast path: no mirror lookups or edge_key
                    // String allocs when the source carries no edge mirrors.
                    if !part.edge_py_attrs.is_empty()
                        && let Some(attrs) = part
                            .edge_py_attrs
                            .get(&Self::edge_key(u, v))
                            .or_else(|| part.edge_py_attrs.get(&Self::edge_key(v, u)))
                    {
                        let ek_fwd = Self::edge_key(u, v);
                        let ek_rev = Self::edge_key(v, u);
                        if let Some(existing) = g
                            .edge_py_attrs
                            .get(&ek_fwd)
                            .or_else(|| g.edge_py_attrs.get(&ek_rev))
                        {
                            existing.bind(py).update(attrs.bind(py).as_mapping())?;
                        } else {
                            g.edge_py_attrs
                                .insert(ek_fwd, attrs.bind(py).copy()?.unbind());
                        }
                    }
                    edge_batch.push((
                        (*u).to_owned(),
                        v.to_owned(),
                        part.inner
                            .edge_attrs_by_indices(ui, vi)
                            .cloned()
                            .unwrap_or_default(),
                    ));
                }
            }
            g.inner.extend_edges_with_attrs_unrecorded(edge_batch);
        }
        Py::new(py, g)
    }

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
    fn _native_disjoint_union(&self, py: Python<'_>, other: PyRef<'_, Self>) -> PyResult<Py<Self>> {
        let mut g =
            Self::new_empty_with_policy(py, fnx_runtime::RuntimePolicy::new(self.inner.mode()))?;
        let merged_graph_attrs = PyDict::new(py);
        merged_graph_attrs.update(self.graph_attrs.bind(py).as_mapping())?;
        merged_graph_attrs.update(other.graph_attrs.bind(py).as_mapping())?;
        g.graph_attrs = merged_graph_attrs.unbind();
        let n1 = self.inner.node_count();
        for (part, offset) in [(self, 0usize), (&*other, n1)] {
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
            let mut seen: std::collections::HashSet<(usize, usize)> =
                std::collections::HashSet::new();
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
        let _ = dg.inner.extend_nodes_with_attrs_unrecorded(node_batch);
        let mut edge_batch: Vec<(String, String, fnx_classes::AttrMap)> =
            Vec::with_capacity(self.inner.edge_count() * 2);
        // br-inedges-distorefix (bt): when the mirror is PRISTINE (empty), the
        // attr-less `Default` arc is correct — the lazy mirror carries nothing and
        // the store attrs flow through the edge_batch path. But once the mirror is
        // NON-pristine (e.g. a single get_edge_data(v, u) materialized ONE edge),
        // `Default` for a store-only edge DROPPED its attrs — a bulk-built graph
        // with one stray mirror entry lost every store-only arc's attrs. Read the
        // CgseValue store for store-only edges in that case.
        let mirror_pristine = self.edge_py_attrs.is_empty();
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
                    None if mirror_pristine => Default::default(),
                    None => self
                        .inner
                        .edge_attrs(source, target)
                        .cloned()
                        .unwrap_or_default(),
                };
                edge_batch.push((source.to_owned(), target.to_owned(), rust_attrs));
            }
        }
        let _ = dg.inner.extend_edges_with_attrs_unrecorded(edge_batch);
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

    /// br-r37-c1-slgraph (cc): native simple-Graph self-loop edge emission. The
    /// Python `selfloop_edges` path did `G[n]` / `nbrs[n]` per self-loop node --
    /// the AtlasView + keydict machinery (~75k Python calls) made
    /// `selfloop_edges(data=True)` 0.16x vs nx even though the underlying attr-dict
    /// build is cheap and cached. Emit the NetworkX-shaped tuples directly in node
    /// order, handing out the LIVE edge attr dict (`materialize_edge_py_attrs`) so
    /// `data=True` mutations persist exactly like nx's live adjacency dict. Returns
    /// `None` (Python fallback) for the `data="<attr>"` value form (out of scope).
    #[pyo3(signature = (data, default=None))]
    fn _native_selfloop_edges(
        &mut self,
        py: Python<'_>,
        data: &Bound<'_, PyAny>,
        default: Option<PyObject>,
    ) -> PyResult<Option<Py<NodeIterator>>> {
        let _ = default;
        if !data.is_instance_of::<PyBool>() {
            return Ok(None); // data="<attr>" value form -> Python path
        }
        let want_dict = data.extract::<bool>()?;
        if want_dict && self.inner.edge_count() > 0 {
            self.mark_edges_dirty();
        }
        let sl_nodes: Vec<String> = self
            .inner
            .nodes_ordered()
            .iter()
            .filter(|n| self.inner.has_edge(n, n))
            .map(|n| (*n).to_owned())
            .collect();
        let mut out: Vec<PyObject> = Vec::with_capacity(sl_nodes.len());
        for node in &sl_nodes {
            let node = node.as_str();
            let py_node = self.py_node_key(py, node);
            if want_dict {
                let d = self.materialize_edge_py_attrs(py, node, node);
                out.push(
                    PyTuple::new(py, [py_node.clone_ref(py), py_node, d.into_any()])?
                        .into_any()
                        .unbind(),
                );
            } else {
                out.push(
                    PyTuple::new(py, [py_node.clone_ref(py), py_node])?
                        .into_any()
                        .unbind(),
                );
            }
        }
        Ok(Some(Py::new(py, NodeIterator::unguarded(out))?))
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

    /// br-r37-c1-atlasget (cc): O(1) single-edge live attr dict for
    /// `AtlasView.__getitem__` (`G[u][v]`). Returns `None` when the edge is
    /// absent (the Python caller raises `KeyError(v)` with the original key),
    /// else the SAME live `edge_py_attrs` dict that
    /// `_native_adjacency_row_dict(u)[v]` yields (materialize_edge_py_attrs is
    /// the shared entry point, so identity + mutation-reflection are preserved).
    /// Skips building the whole row keydict (O(degree)) for one edge access —
    /// `G[u][v]` was 0.04x vs nx because AtlasView fell back to the row build.
    /// Marks edges dirty exactly as the row-dict path does (the returned dict is
    /// live + mutable).
    fn _fnx_edge_attr_dict_fast(
        &mut self,
        py: Python<'_>,
        u: &Bound<'_, PyAny>,
        v: &Bound<'_, PyAny>,
    ) -> PyResult<Option<Py<PyDict>>> {
        let u_c = node_key_to_string(py, u)?;
        let v_c = node_key_to_string(py, v)?;
        if !self.inner.has_edge(&u_c, &v_c) {
            return Ok(None);
        }
        self.mark_edges_dirty();
        Ok(Some(self.materialize_edge_py_attrs(py, &u_c, &v_c)))
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
        self.edges_dirty.store(false, Ordering::Relaxed);
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
        self.edges_dirty.store(false, Ordering::Relaxed);
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

    /// br-r37-c1-wsize (cc): native scalar `size(weight)` for the integer/clean
    /// case — see `PyMultiGraph::_weighted_size_fast`. PyGraph's
    /// `_native_weighted_degree` has no store fast path at all (it always builds a
    /// per-node PyList + `builtins.sum`), so weighted `size` paid full per-node
    /// PyObject materialisation; this skips straight to the store scalar.
    fn _weighted_size_fast(&self, weight: &str) -> Option<f64> {
        if self.edges_dirty.load(Ordering::Relaxed) {
            return None;
        }
        self.inner.weighted_size_int(weight).map(|t| t as f64)
    }

    /// br-cc-undegvals: values-only INT total weighted degree in node-index order
    /// (NO per-node `py_node_key`, NO whole-graph `to_dict_of_dicts`). The Python
    /// total-degree gen zips these with the cached node list — the same win the
    /// DiGraph degree(weight) path carries (0.76x -> 3.7x). Accumulates i128 per
    /// node straight from the CgseValue store via the integer index rows; an
    /// undirected self-loop appears ONCE in `adj_indices` but nx counts its weight
    /// TWICE, so it contributes 2·w. Gated on `!edges_dirty`; returns None (-> the
    /// byte-identical `to_dict_of_dicts` sum) on a dirty store, any non-int weight,
    /// or i128->i64 overflow, so float/heterogeneous/bignum graphs are unaffected.
    fn _native_weighted_degree_int_values(
        &self,
        py: Python<'_>,
        weight: &str,
    ) -> PyResult<Option<Vec<PyObject>>> {
        if self.edges_dirty.load(Ordering::Relaxed) {
            return Ok(None);
        }
        let n = self.inner.node_count();
        let mut out: Vec<PyObject> = Vec::with_capacity(n);
        for i in 0..n {
            let mut total: i128 = 0;
            if let Some(nbrs) = self.inner.neighbors_indices(i) {
                for &j in nbrs {
                    let w = match self
                        .inner
                        .edge_attrs_by_indices(i, j)
                        .map(|a| a.get(weight))
                    {
                        Some(Some(CgseValue::Int(v))) => i128::from(*v),
                        Some(Some(_)) => return Ok(None), // non-int -> gen fallback
                        _ => 1,                           // missing weight -> default 1
                    };
                    // Undirected self-loop counts twice (nx degree semantics).
                    let contrib = if i == j { w.checked_mul(2) } else { Some(w) };
                    let Some(contrib) = contrib else {
                        return Ok(None);
                    };
                    let Some(t) = total.checked_add(contrib) else {
                        return Ok(None);
                    };
                    total = t;
                }
            }
            let Ok(total_i64) = i64::try_from(total) else {
                return Ok(None);
            };
            out.push(total_i64.into_pyobject(py)?.into_any().unbind());
        }
        Ok(Some(out))
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
                let value = self
                    .edge_attr_py_value(py, node, neighbor, weight)?
                    .unwrap_or_else(|| one.clone().unbind());
                values.append(value.bind(py))?;
            }
            let mut deg = sum_fn.call1((values,))?;
            if selfloop {
                let value = self
                    .edge_attr_py_value(py, node, node, weight)?
                    .unwrap_or_else(|| one.clone().unbind());
                deg = deg.add(value.bind(py))?;
            }
            out.push((self.py_node_key(py, node), deg.unbind()));
        }
        Ok(out)
    }

    /// br-r37-c1-degnbw (cc): weighted-subset sibling of _native_weighted_degree —
    /// degree(nbunch, weight) over only the (validated, in-graph) nbunch nodes.
    /// nbunch+weight previously had no native and fell to the Python _degree_compute
    /// AtlasView loop (~0.12x). NOT deduped (matches _native_degree_pairs_subset /
    /// nx degree(nbunch) — repeated nbunch nodes repeat); KEEP builtins.sum for
    /// float parity; selfloops double-count via the trailing add.
    fn _native_weighted_degree_subset(
        &self,
        py: Python<'_>,
        nbunch: &Bound<'_, PyAny>,
        weight: &str,
    ) -> PyResult<Vec<(PyObject, PyObject)>> {
        // Materialize the (validated, in-graph) nbunch ONCE — nbunch may be a
        // one-shot iterator, and both the int-store fast path and the exact path
        // walk it. Preserve nx validation: unhashable -> TypeError, absent -> skip.
        let mut items: Vec<(Bound<'_, PyAny>, String)> = Vec::new();
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
            if self.inner.get_node_index(&canonical).is_none() {
                continue;
            }
            items.push((node, canonical));
        }

        // br-cc-undegnbint: INT-store fast path — i128 accumulate per node straight
        // from the CgseValue store via integer index rows (undirected self-loop is
        // counted twice), reusing the passed nbunch object as the key (== nx). Skips
        // the per-node PyList + builtins.sum + per-neighbour String-keyed
        // edge_attr_py_value probe of the exact path (degree(nbunch,w) was 0.58x).
        // Gated !edges_dirty; bails (whole subset) on any non-int weight / overflow.
        if !self.edges_dirty.load(Ordering::Relaxed) {
            let mut int_pairs: Vec<(PyObject, PyObject)> = Vec::with_capacity(items.len());
            let mut all_int = true;
            'nodes: for (node, canonical) in &items {
                let Some(idx) = self.inner.get_node_index(canonical) else {
                    all_int = false;
                    break;
                };
                let mut total: i128 = 0;
                if let Some(nbrs) = self.inner.neighbors_indices(idx) {
                    for &j in nbrs {
                        let w = match self
                            .inner
                            .edge_attrs_by_indices(idx, j)
                            .map(|a| a.get(weight))
                        {
                            Some(Some(CgseValue::Int(v))) => i128::from(*v),
                            Some(Some(_)) => {
                                all_int = false;
                                break 'nodes;
                            }
                            _ => 1,
                        };
                        // Undirected self-loop counts twice.
                        let contrib = if idx == j { w.checked_mul(2) } else { Some(w) };
                        let Some(t) = contrib.and_then(|c| total.checked_add(c)) else {
                            all_int = false;
                            break 'nodes;
                        };
                        total = t;
                    }
                }
                match i64::try_from(total) {
                    Ok(t64) => int_pairs.push((
                        node.clone().unbind(),
                        t64.into_pyobject(py)?.into_any().unbind(),
                    )),
                    Err(_) => {
                        all_int = false;
                        break;
                    }
                }
            }
            if all_int {
                return Ok(int_pairs);
            }
        }

        let one = 1i64.into_pyobject(py)?.into_any();
        let sum_fn = py.import("builtins")?.getattr("sum")?;
        let mut out: Vec<(PyObject, PyObject)> = Vec::with_capacity(items.len());
        for (node, canonical) in &items {
            let values = pyo3::types::PyList::empty(py);
            let mut selfloop = false;
            for neighbor in self.inner.neighbors(canonical).unwrap_or_default() {
                if neighbor == canonical.as_str() {
                    selfloop = true;
                }
                let value = self
                    .edge_attr_py_value(py, canonical, neighbor, weight)?
                    .unwrap_or_else(|| one.clone().unbind());
                values.append(value.bind(py))?;
            }
            let mut deg = sum_fn.call1((values,))?;
            if selfloop {
                let value = self
                    .edge_attr_py_value(py, canonical, canonical, weight)?
                    .unwrap_or_else(|| one.clone().unbind());
                deg = deg.add(value.bind(py))?;
            }
            out.push((node.clone().unbind(), deg.unbind()));
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
        // generated and fresh-batch graphs; a missing entry uses the canonical
        // Rust attrs until a live Python dict is materialized.
        if self.inner.edge_count() != other.inner.edge_count() {
            return Ok(false);
        }
        for (u, v, attrs) in self.inner.edges_ordered_borrowed() {
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
                    let Some(other_inner_attrs) = other.inner.edge_attrs(u, v) else {
                        return Ok(false);
                    };
                    let other_dict = attr_map_to_pydict(py, other_inner_attrs)?;
                    if !attrs.bind(py).eq(other_dict.bind(py))? {
                        return Ok(false);
                    }
                }
                (None, Some(other_attrs)) => {
                    let self_dict = attr_map_to_pydict(py, attrs)?;
                    if !self_dict.bind(py).eq(other_attrs.bind(py))? {
                        return Ok(false);
                    }
                }
                (None, None) => {
                    let Some(other_inner_attrs) = other.inner.edge_attrs(u, v) else {
                        return Ok(false);
                    };
                    if attrs != other_inner_attrs {
                        return Ok(false);
                    }
                }
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
            adj_row_py: HashMap::new(),
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
            node_iter_mirror: std::sync::Mutex::new(None),
            node_data_mirror: std::sync::Mutex::new(None),
        })
    }

    /// Support ``copy.deepcopy(G)`` — returns a deep copy.
    #[pyo3(signature = (_memo=None))]
    fn __deepcopy__(&self, py: Python<'_>, _memo: Option<&Bound<'_, PyAny>>) -> PyResult<Self> {
        self.copy(py)
    }

    /// br-r37-c1-489mp: native same-type deepcopy — see PyMultiGraph variant.
    /// VERBATIM structure (via `__copy__`) + deep-copied node/edge attr dicts
    /// under ONE shared memo; the Python `_graph_deepcopy` tail adds graph
    /// attrs, frozen and custom instance attributes.
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
            let deep =
                deepcopy_py_dict_memo(py, &deepcopy, &new_graph.node_py_attrs[&k], &memo_obj)?;
            new_graph.node_py_attrs.insert(k, deep);
        }
        let edge_keys: Vec<(String, String)> = new_graph.edge_py_attrs.keys().cloned().collect();
        for k in edge_keys {
            let deep =
                deepcopy_py_dict_memo(py, &deepcopy, &new_graph.edge_py_attrs[&k], &memo_obj)?;
            new_graph.edge_py_attrs.insert(k, deep);
        }
        Ok(new_graph)
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
            .map(|n| -> PyResult<_> {
                let py_key = self.py_node_key(py, n);
                // br-r37-c1-getstate-storemiss (cc): a MISSING node mirror does NOT
                // mean empty attrs — single-attr / bulk-added nodes stay LAZY in the
                // CgseValue store with no node_py_attrs entry (only multi-attr nodes
                // get an eager mirror). The old `map_or_else(|| PyDict::new(...))`
                // DROPPED single-attr node attributes on pickle/deepcopy (e.g.
                // add_nodes_from([(i,{'p':i})]) or convert_node_labels_to_integers ->
                // pickle -> every node came back {}). Fall back to the store's AttrMap.
                let attrs = match self.node_py_attrs.get(n) {
                    Some(d) => d.clone_ref(py),
                    None => match self.inner.node_attrs(n) {
                        Some(a) => attr_map_to_pydict(py, a)?,
                        None => PyDict::new(py).unbind(),
                    },
                };
                Ok((py_key, attrs))
            })
            .collect::<PyResult<Vec<_>>>()?;
        state.set_item("nodes", nodes_list)?;

        // Store edges as list of (u, v, attrs) tuples. Generated and fresh-batch
        // graphs keep edge_py_attrs sparse until the first live attr-dict
        // handout, so the edge structure and unmaterialized attrs come from
        // inner rather than edge_py_attrs.
        let edges_list: Vec<(PyObject, PyObject, Py<PyDict>)> = self
            .inner
            .edges_ordered_borrowed()
            .into_iter()
            .map(|(u, v, inner_attrs)| {
                let py_u = self.py_node_key(py, u);
                let py_v = self.py_node_key(py, v);
                let key = Self::edge_key(u, v);
                let attrs = self.edge_py_attrs.get(&key).map_or_else(
                    || attr_map_to_pydict(py, inner_attrs),
                    |d| Ok(d.clone_ref(py)),
                )?;
                Ok((py_u, py_v, attrs))
            })
            .collect::<PyResult<_>>()?;
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

    fn exact_int_attr_ebunch(py: Python<'_>) -> PyResult<(Bound<'_, PyList>, Py<PyDict>)> {
        let ebunch = PyList::empty(py);
        let mut first_attrs = None;
        for i in 0_i64..8 {
            let attrs = PyDict::new(py);
            attrs.set_item("weight", i)?;
            attrs.set_item("label", format!("edge-{i}"))?;
            let attrs_object = attrs.clone().unbind();
            if i == 0 {
                first_attrs = Some(attrs_object.clone_ref(py));
            }
            let tuple_items = [
                i.into_py_any(py)?,
                (i + 1).into_py_any(py)?,
                attrs_object.into_any(),
            ];
            ebunch.append(PyTuple::new(py, &tuple_items)?)?;
        }
        Ok((ebunch, first_attrs.expect("loop always creates attrs")))
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
    fn graph_fresh_exact_int_attr_batch_keeps_attrs_with_lazy_mirrors() {
        ensure_python();
        Python::attach(|py| -> PyResult<()> {
            let (ebunch, first_source_attrs) = exact_int_attr_ebunch(py)?;
            let mut sparse = PyGraph::new_empty(py)?;

            assert!(sparse.try_add_fresh_exact_int_attr_edge_batch(py, ebunch.as_any())?);
            assert_eq!(sparse.inner.node_count(), 9);
            assert_eq!(sparse.inner.edge_count(), 8);
            assert!(
                sparse.edge_py_attrs.is_empty(),
                "fresh exact-int attributed batch should leave Python edge mirrors lazy"
            );

            let first_inner_attrs = sparse
                .inner
                .edge_attrs("0", "1")
                .expect("edge attrs should stay canonical in inner graph");
            assert_eq!(first_inner_attrs.get("weight"), Some(&CgseValue::Int(0)));
            assert_eq!(
                first_inner_attrs.get("label"),
                Some(&CgseValue::String("edge-0".to_owned()))
            );

            first_source_attrs.bind(py).set_item("weight", 99)?;
            assert_eq!(
                sparse
                    .inner
                    .edge_attrs("0", "1")
                    .and_then(|attrs| attrs.get("weight")),
                Some(&CgseValue::Int(0)),
                "source dict mutation must not alias graph attrs"
            );

            let state = sparse
                .__getstate__(py)?
                .into_bound(py)
                .downcast_into::<PyDict>()?;
            let edges = state
                .get_item("edges")?
                .expect("pickle state should include edges");
            let first_edge = edges.get_item(0)?;
            let first_edge_tuple = first_edge.downcast::<PyTuple>()?;
            let state_attrs = first_edge_tuple.get_item(2)?.downcast_into::<PyDict>()?;
            assert_eq!(
                state_attrs
                    .get_item("weight")?
                    .expect("state attrs should include weight")
                    .extract::<i64>()?,
                0
            );
            assert_eq!(
                state_attrs
                    .get_item("label")?
                    .expect("state attrs should include label")
                    .extract::<String>()?,
                "edge-0"
            );
            assert!(
                sparse.edge_py_attrs.is_empty(),
                "__getstate__ should not eagerly materialize live edge mirrors"
            );

            let (ebunch, _) = exact_int_attr_ebunch(py)?;
            let mut materialized = PyGraph::new_empty(py)?;
            assert!(materialized.try_add_fresh_exact_int_attr_edge_batch(py, ebunch.as_any())?);
            let zero = 0_i64.into_pyobject(py)?.into_any();
            let one = 1_i64.into_pyobject(py)?.into_any();
            let data = materialized.get_edge_data(py, &zero, &one, None)?;
            let data_dict = data.bind(py).downcast::<PyDict>()?;
            assert_eq!(
                data_dict
                    .get_item("weight")?
                    .expect("materialized attrs should include weight")
                    .extract::<i64>()?,
                0
            );
            assert_eq!(materialized.edge_py_attrs.len(), 1);

            let sparse_py = Py::new(py, sparse)?;
            let materialized_py = Py::new(py, materialized)?;
            assert!(
                sparse_py
                    .borrow(py)
                    .__eq__(py, materialized_py.bind(py).as_any())?
            );
            assert!(
                materialized_py
                    .borrow(py)
                    .__eq__(py, sparse_py.bind(py).as_any())?
            );
            Ok(())
        })
        .expect("fresh exact-int attr batch parity should hold");
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
    #[allow(dead_code)]
    Graph(Py<PyGraph>),
    MultiGraph(Py<PyMultiGraph>),
    #[allow(dead_code)]
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

/// br-r37-c1-g6wla: native integer-CSR per-node overlap counts for the bipartite
/// `node_redundancy` coefficient. For each node v returns `(overlap, deg)` where
/// `overlap` is the number of neighbour pairs `{u,w} ⊆ N(v)` that share a common
/// neighbour other than v, and `deg = |N(v)|`; networkx's `_node_redundancy`
/// computes `(2*overlap) / (deg*(deg-1))`. The Python wrapper performs that exact
/// division so the result is byte-identical, and raises networkx's error when any
/// requested node has `deg < 2`. `overlap` is a graph invariant (a pair count),
/// so node iteration order is irrelevant. Counts are emitted in node order.
/// Returns `None` for directed / multigraph graphs (Python delegates to nx).
#[pyfunction]
pub fn node_redundancy_overlaps(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,
) -> PyResult<Option<Vec<(u64, u64)>>> {
    let gr = crate::algorithms::extract_graph(g)?;
    let crate::algorithms::GraphRef::Undirected(pg) = &gr else {
        return Ok(None);
    };
    let inner = &pg.inner;
    let n = inner.node_count();
    let out = py.allow_threads(|| {
        let mut result: Vec<(u64, u64)> = Vec::with_capacity(n);
        let mut mark = vec![false; n]; // marks N(u) \ {v}
        for v in 0..n {
            let nv = inner.neighbors_indices(v).unwrap_or(&[]);
            let deg = nv.len();
            if deg < 2 {
                result.push((0, deg as u64));
                continue;
            }
            let mut overlap: u64 = 0;
            for i in 0..deg {
                let u = nv[i];
                if let Some(nu) = inner.neighbors_indices(u) {
                    for &z in nu {
                        if z != v {
                            mark[z] = true;
                        }
                    }
                }
                for &w in &nv[(i + 1)..] {
                    // (N(u) ∩ N(w)) \ {v} nonempty? mark already excludes v.
                    let mut hit = false;
                    if let Some(nw) = inner.neighbors_indices(w) {
                        for &z in nw {
                            if mark[z] {
                                hit = true;
                                break;
                            }
                        }
                    }
                    if hit {
                        overlap += 1;
                    }
                }
                if let Some(nu) = inner.neighbors_indices(u) {
                    for &z in nu {
                        mark[z] = false;
                    }
                }
            }
            result.push((overlap, deg as u64));
        }
        result
    });
    Ok(Some(out))
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

    m.add_function(wrap_pyfunction!(validate_ctor_edge_list, m)?)?;
    m.add_function(wrap_pyfunction!(geometric_pairs_grid, m)?)?;
    m.add_function(wrap_pyfunction!(node_redundancy_overlaps, m)?)?;
    m.add_function(wrap_pyfunction!(network_simplex::network_simplex_int, m)?)?;

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
