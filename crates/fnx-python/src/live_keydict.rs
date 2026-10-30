//! Persistent Python keydict rows for multigraph edge pairs.
//!
//! NetworkX's ``G.get_edge_data(u, v)`` returns ``G._adj[u][v]``: the graph's
//! own keydict, a real ``dict``. The bindings keep the graph structure in Rust,
//! so a keydict handed out is registered here and every edge mutation keeps its
//! contents in step, in place, through the C-level ``PyDict`` API (which does
//! not dispatch to the Python subclass's overrides). Writes made THROUGH the
//! dict go the other way: the Python subclass (``_MultiEdgeKeydict`` in the
//! package, registered with [`set_keydict_class`]) forwards them to the graph.
//!
//! What happens to a held keydict follows networkx exactly
//! (br-r37-c1-rc0923-epic-honest-measurement-vbneu.3):
//! - the last edge of the pair removed through the GRAPH: the dict is emptied
//!   and detached (a later add_edge creates a new keydict);
//! - the last key deleted THROUGH the dict: it stays registered, empty (a
//!   "ghost" pair, as networkx leaves the empty keydict in ``_adj``), and a
//!   later add_edge on the pair reuses it;
//! - a node removal, ``clear()`` or ``clear_edges()``: the dict is detached with
//!   its contents untouched (networkx drops the adjacency entry, not the keys).
//! - replacing a pair's entire keydict: the old dict is detached intact and a
//!   fresh dict becomes live, without removing the ordered neighbor cells.
//!
//! Detached means unregistered and ``_fnx_graph`` reset to ``None``, so later
//! writes through it are plain dict writes, as on a networkx keydict that is no
//! longer part of a graph.

use pyo3::gc::{PyTraverseError, PyVisit};
use pyo3::intern;
use pyo3::prelude::*;
use pyo3::sync::PyOnceLock;
use pyo3::types::{PyDict, PyType};
// Fx, not SipHash: every to_dict_of_dicts row entry and every keydict-backed
// get_edge_data hashes two node labels here, and no output order depends on
// these maps (br-r37-c1-49u7h).
use rustc_hash::{FxHashMap as HashMap, FxHashSet as HashSet};
use std::sync::Arc;

static KEYDICT_CLASS: PyOnceLock<Py<PyType>> = PyOnceLock::new();

/// Register the package's ``dict`` subclass used for keydict rows. Called once
/// at import, right after the class is defined.
#[pyfunction]
pub(crate) fn _set_multigraph_keydict_class(
    py: Python<'_>,
    cls: Bound<'_, PyType>,
) -> PyResult<()> {
    if !cls.is_subclass_of::<PyDict>()? {
        return Err(pyo3::exceptions::PyTypeError::new_err(
            "the multigraph keydict class must subclass dict",
        ));
    }
    let _ = KEYDICT_CLASS.set(py, cls.unbind());
    Ok(())
}

/// A new, empty keydict row owned by `graph` for the pair `(source, target)`:
/// an instance of the registered subclass wired for write-through, or a plain
/// ``dict`` (reads and graph-side liveness only) when none is registered.
pub(crate) fn new_row<'py>(
    py: Python<'py>,
    graph: &Bound<'py, PyAny>,
    source: &str,
    target: &str,
) -> PyResult<Bound<'py, PyDict>> {
    let Some(cls) = KEYDICT_CLASS.get(py) else {
        return Ok(PyDict::new(py));
    };
    // dict.__new__(cls): an instance of the subclass without running its
    // Python __init__ - every slot is set just below. That __init__ frame was
    // the largest single cost of building a keydict (br-r37-c1-49u7h).
    let row = py
        .get_type::<PyDict>()
        .call_method1(intern!(py, "__new__"), (cls.bind(py),))?
        .cast_into::<PyDict>()?;
    row.setattr(intern!(py, "_fnx_u"), source)?;
    row.setattr(intern!(py, "_fnx_v"), target)?;
    row.setattr(intern!(py, "_fnx_graph"), graph)?;
    Ok(row)
}

fn detach(py: Python<'_>, row: &Py<PyDict>) {
    // A plain-dict fallback row has no such attribute; nothing to detach.
    let _ = row.bind(py).setattr(intern!(py, "_fnx_graph"), py.None());
}

#[derive(Default)]
pub(crate) struct LiveKeydictRows {
    // Both indexes share the endpoint labels. Allocate once per source/target
    // index entry, not four strings per pair (including discarded entry keys).
    // Arc keeps this state Send, as required by the graph's PyO3 class.
    rows: HashMap<Arc<str>, HashMap<Arc<str>, Py<PyDict>>>,
    /// target -> sources holding a row for it, so a node removal finds its
    /// rows without scanning every registered row.
    sources_by_target: HashMap<Arc<str>, HashSet<Arc<str>>>,
}

impl LiveKeydictRows {
    #[inline]
    pub(crate) fn is_empty(&self) -> bool {
        self.rows.is_empty()
    }

    /// Empty live pairs are adjacency entries, not unit-weight edges: a
    /// Dijkstra weight reduction over their parallel dictionaries is min([]).
    /// Inspect the underlying dict without calling Python subclass hooks.
    pub(crate) fn has_empty_row(&self, py: Python<'_>) -> bool {
        self.rows
            .values()
            .any(|targets| targets.values().any(|row| row.bind(py).is_empty()))
    }

    pub(crate) fn get(&self, py: Python<'_>, source: &str, target: &str) -> Option<Py<PyDict>> {
        self.rows
            .get(source)
            .and_then(|targets| targets.get(target))
            .map(|row| row.clone_ref(py))
    }

    pub(crate) fn contains(&self, source: &str, target: &str) -> bool {
        self.rows
            .get(source)
            .is_some_and(|targets| targets.contains_key(target))
    }

    pub(crate) fn insert(&mut self, source: &str, target: &str, row: Py<PyDict>) {
        let source = self
            .rows
            .get_key_value(source)
            .map_or_else(|| Arc::<str>::from(source), |(label, _)| Arc::clone(label));
        let target = self
            .sources_by_target
            .get_key_value(target)
            .map_or_else(|| Arc::<str>::from(target), |(label, _)| Arc::clone(label));
        self.rows
            .entry(Arc::clone(&source))
            .or_default()
            .insert(Arc::clone(&target), row);
        self.sources_by_target
            .entry(target)
            .or_default()
            .insert(source);
    }

    /// Replace the pair's live row without changing a held old row's contents.
    pub(crate) fn replace(&mut self, py: Python<'_>, source: &str, target: &str, row: Py<PyDict>) {
        if let Some(previous) = self.get(py, source, target)
            && !previous.bind(py).is(row.bind(py))
        {
            detach(py, &previous);
        }
        self.insert(source, target, row);
    }

    fn unregister(&mut self, source: &str, target: &str) -> Option<Py<PyDict>> {
        let row = self.rows.get_mut(source)?.remove(target)?;
        if self
            .rows
            .get(source)
            .is_some_and(|targets| targets.is_empty())
        {
            self.rows.remove(source);
        }
        if let Some(sources) = self.sources_by_target.get_mut(target) {
            sources.remove(source);
            if sources.is_empty() {
                self.sources_by_target.remove(target);
            }
        }
        Some(row)
    }

    /// The pair's last edge was removed through the graph: empty the row (the
    /// removed keys leave it, as in networkx) and detach it.
    pub(crate) fn pair_emptied(&mut self, py: Python<'_>, source: &str, target: &str) {
        if let Some(row) = self.unregister(source, target) {
            row.bind(py).clear();
            detach(py, &row);
        }
    }

    /// A node was removed: detach every row that has it as an endpoint, with
    /// its contents untouched.
    pub(crate) fn node_removed(&mut self, py: Python<'_>, node: &str) {
        let targets: Vec<Arc<str>> = self
            .rows
            .get(node)
            .map(|targets| targets.keys().cloned().collect())
            .unwrap_or_default();
        for target in targets {
            if let Some(row) = self.unregister(node, &target) {
                detach(py, &row);
            }
        }
        let sources: Vec<Arc<str>> = self
            .sources_by_target
            .get(node)
            .map(|sources| sources.iter().cloned().collect())
            .unwrap_or_default();
        for source in sources {
            if let Some(row) = self.unregister(&source, node) {
                detach(py, &row);
            }
        }
    }

    /// ``clear()`` / ``clear_edges()`` / garbage collection: detach every row,
    /// contents untouched.
    pub(crate) fn detach_all(&mut self, py: Python<'_>) {
        for targets in self.rows.values() {
            for row in targets.values() {
                detach(py, row);
            }
        }
        self.rows.clear();
        self.sources_by_target.clear();
    }

    pub(crate) fn traverse(&self, visit: &PyVisit<'_>) -> Result<(), PyTraverseError> {
        for targets in self.rows.values() {
            for row in targets.values() {
                visit.call(row)?;
            }
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::LiveKeydictRows;
    use pyo3::prelude::*;
    use pyo3::types::PyDict;
    use std::sync::Arc;

    #[test]
    fn unit_weight_dijkstra_path_detects_empty_live_rows() {
        Python::initialize();
        Python::attach(|py| {
            let mut rows = LiveKeydictRows::default();
            assert!(!rows.has_empty_row(py));
            let row = PyDict::new(py);
            row.set_item(0, PyDict::new(py)).expect("key should add");
            rows.insert("s", "t", row.clone().unbind());
            assert!(!rows.has_empty_row(py));
            row.clear();
            assert!(rows.has_empty_row(py));
            row.set_item(1, PyDict::new(py)).expect("key should add");
            assert!(!rows.has_empty_row(py));
        });
    }

    #[test]
    fn endpoint_labels_are_shared_between_both_indexes() {
        Python::initialize();
        Python::attach(|py| {
            let mut rows = LiveKeydictRows::default();
            rows.insert("source-a", "target-b", PyDict::new(py).unbind());
            rows.insert("source-a", "target-c", PyDict::new(py).unbind());
            rows.insert("source-d", "target-b", PyDict::new(py).unbind());
            let source_a = rows.rows.get_key_value("source-a").expect("source-a").0;
            let target_b = rows
                .sources_by_target
                .get_key_value("target-b")
                .expect("target-b")
                .0;
            for target in ["target-b", "target-c"] {
                assert!(Arc::ptr_eq(
                    source_a,
                    rows.sources_by_target[target]
                        .get("source-a")
                        .expect("reverse source"),
                ));
            }
            for source in ["source-a", "source-d"] {
                assert!(Arc::ptr_eq(
                    target_b,
                    rows.rows[source]
                        .get_key_value("target-b")
                        .expect("forward target")
                        .0,
                ));
            }
        });
    }

    #[test]
    fn replacement_and_unregister_keep_indexes_in_step() {
        Python::initialize();
        Python::attach(|py| {
            let mut rows = LiveKeydictRows::default();
            let old = PyDict::new(py);
            let replacement = PyDict::new(py);
            rows.insert("a", "b", old.unbind());
            rows.insert("a", "b", replacement.clone().unbind());
            rows.insert("a", "c", PyDict::new(py).unbind());
            rows.insert("d", "b", PyDict::new(py).unbind());
            assert_eq!(rows.sources_by_target["b"].len(), 2);
            assert!(
                rows.get(py, "a", "b")
                    .expect("row")
                    .bind(py)
                    .is(&replacement)
            );
            assert!(rows.unregister("a", "missing").is_none());
            assert!(
                rows.unregister("a", "b")
                    .expect("row")
                    .bind(py)
                    .is(&replacement)
            );
            assert!(rows.contains("a", "c"));
            assert!(rows.contains("d", "b"));
            assert!(!rows.sources_by_target["b"].contains("a"));
            assert!(rows.unregister("a", "c").is_some());
            assert!(!rows.rows.contains_key("a"));
            assert!(!rows.sources_by_target.contains_key("c"));
            assert!(rows.unregister("d", "b").is_some());
            assert!(rows.is_empty());
            assert!(rows.sources_by_target.is_empty());
        });
    }

    #[test]
    fn node_removal_handles_both_roles_and_self_loop_without_emptying_rows() {
        Python::initialize();
        Python::attach(|py| -> PyResult<()> {
            let mut rows = LiveKeydictRows::default();
            let mut held = Vec::new();
            for (source, target) in [("hub", "left"), ("right", "hub"), ("hub", "hub")] {
                let row = PyDict::new(py);
                row.set_item("edge", 7)?;
                rows.insert(source, target, row.clone().unbind());
                held.push(row);
            }
            rows.insert("unrelated", "other", PyDict::new(py).unbind());
            rows.node_removed(py, "missing");
            rows.node_removed(py, "hub");
            assert!(!rows.rows.contains_key("hub"));
            assert!(!rows.rows.contains_key("right"));
            assert!(!rows.sources_by_target.contains_key("hub"));
            assert!(!rows.sources_by_target.contains_key("left"));
            assert!(rows.contains("unrelated", "other"));
            for row in held {
                assert_eq!(row.get_item("edge")?.expect("edge").extract::<i32>()?, 7);
            }
            rows.detach_all(py);
            assert!(rows.is_empty());
            assert!(rows.sources_by_target.is_empty());
            Ok(())
        })
        .expect("held rows stay intact");
    }

    #[test]
    fn pair_emptying_clears_only_its_held_row_and_releases_its_labels() {
        Python::initialize();
        Python::attach(|py| -> PyResult<()> {
            let mut rows = LiveKeydictRows::default();
            let row = PyDict::new(py);
            row.set_item("edge", 7)?;
            rows.insert("a", "b", row.clone().unbind());
            let unrelated = PyDict::new(py);
            unrelated.set_item("edge", 9)?;
            rows.insert("other", "unrelated", unrelated.clone().unbind());
            let source = Arc::downgrade(rows.rows.get_key_value("a").expect("source").0);
            let target =
                Arc::downgrade(rows.sources_by_target.get_key_value("b").expect("target").0);
            rows.pair_emptied(py, "a", "missing");
            assert_eq!(row.len(), 1);
            rows.pair_emptied(py, "a", "b");
            assert!(row.is_empty());
            assert!(rows.contains("other", "unrelated"));
            assert_eq!(rows.rows.len(), 1);
            assert_eq!(rows.sources_by_target.len(), 1);
            assert_eq!(
                unrelated
                    .get_item("edge")?
                    .expect("edge")
                    .extract::<i32>()?,
                9
            );
            assert!(source.upgrade().is_none());
            assert!(target.upgrade().is_none());
            Ok(())
        })
        .expect("only the emptied pair is cleared");
    }
}
