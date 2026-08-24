//! Persistent Python keydict rows for multigraph edge pairs.
//!
//! NetworkX stores ``_adj[u][v]`` as a dict.  The bindings keep the graph
//! structure in Rust, but a returned keydict must still be one stable Python
//! object so graph-side mutations can update held references in place.

use pyo3::gc::{PyTraverseError, PyVisit};
use pyo3::prelude::*;
use pyo3::types::PyDict;
use std::collections::HashMap;

#[derive(Default)]
pub(crate) struct LiveKeydictRows {
    rows: HashMap<String, HashMap<String, Py<PyDict>>>,
}

impl LiveKeydictRows {
    pub(crate) fn get(&self, py: Python<'_>, source: &str, target: &str) -> Option<Py<PyDict>> {
        self.rows
            .get(source)
            .and_then(|targets| targets.get(target))
            .map(|row| row.clone_ref(py))
    }

    pub(crate) fn insert(&mut self, source: String, target: String, row: Py<PyDict>) {
        self.rows.entry(source).or_default().insert(target, row);
    }

    pub(crate) fn remove_in_place(&mut self, py: Python<'_>, source: &str, target: &str) {
        let row = self
            .rows
            .get_mut(source)
            .and_then(|targets| targets.remove(target));
        if self.rows.get(source).is_some_and(HashMap::is_empty) {
            self.rows.remove(source);
        }
        if let Some(row) = row {
            row.bind(py).clear();
        }
    }

    pub(crate) fn remove_touching_in_place(&mut self, py: Python<'_>, node: &str) {
        let mut removed = Vec::new();
        for (source, targets) in &mut self.rows {
            if source == node {
                removed.extend(targets.drain().map(|(_, row)| row));
            } else if let Some(row) = targets.remove(node) {
                removed.push(row);
            }
        }
        self.rows.retain(|_, targets| !targets.is_empty());
        for row in removed {
            row.bind(py).clear();
        }
    }

    pub(crate) fn clear_in_place(&mut self, py: Python<'_>) {
        for targets in self.rows.values() {
            for row in targets.values() {
                row.bind(py).clear();
            }
        }
        self.rows.clear();
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
