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
//!
//! Detached means unregistered and ``_fnx_graph`` reset to ``None``, so later
//! writes through it are plain dict writes, as on a networkx keydict that is no
//! longer part of a graph.

use pyo3::gc::{PyTraverseError, PyVisit};
use pyo3::intern;
use pyo3::prelude::*;
use pyo3::sync::PyOnceLock;
use pyo3::types::{PyDict, PyType};
use std::collections::{HashMap, HashSet};

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
    let row = cls.bind(py).call0()?.cast_into::<PyDict>()?;
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
    rows: HashMap<String, HashMap<String, Py<PyDict>>>,
    /// target -> sources holding a row for it, so a node removal finds its
    /// rows without scanning every registered row.
    sources_by_target: HashMap<String, HashSet<String>>,
}

impl LiveKeydictRows {
    #[inline]
    pub(crate) fn is_empty(&self) -> bool {
        self.rows.is_empty()
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
        self.rows
            .entry(source.to_owned())
            .or_default()
            .insert(target.to_owned(), row);
        self.sources_by_target
            .entry(target.to_owned())
            .or_default()
            .insert(source.to_owned());
    }

    fn unregister(&mut self, source: &str, target: &str) -> Option<Py<PyDict>> {
        let row = self.rows.get_mut(source)?.remove(target)?;
        if self.rows.get(source).is_some_and(HashMap::is_empty) {
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
        let targets: Vec<String> = self
            .rows
            .get(node)
            .map(|targets| targets.keys().cloned().collect())
            .unwrap_or_default();
        for target in targets {
            if let Some(row) = self.unregister(node, &target) {
                detach(py, &row);
            }
        }
        let sources: Vec<String> = self
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
