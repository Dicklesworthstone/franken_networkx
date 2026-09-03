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
    rows: HashMap<String, HashMap<String, LiveKeydictRow>>,
}

struct LiveKeydictRow {
    expected_len: usize,
    dict: Py<PyDict>,
}

impl LiveKeydictRows {
    pub(crate) fn get(&self, py: Python<'_>, source: &str, target: &str) -> Option<Py<PyDict>> {
        self.rows
            .get(source)
            .and_then(|targets| targets.get(target))
            .map(|row| row.dict.clone_ref(py))
    }

    pub(crate) fn get_if_pristine(
        &self,
        py: Python<'_>,
        source: &str,
        target: &str,
    ) -> Option<Py<PyDict>> {
        self.rows
            .get(source)
            .and_then(|targets| targets.get(target))
            .filter(|row| row.dict.bind(py).len() == row.expected_len)
            .map(|row| row.dict.clone_ref(py))
    }

    pub(crate) fn insert(
        &mut self,
        py: Python<'_>,
        source: String,
        target: String,
        dict: Py<PyDict>,
    ) {
        let expected_len = dict.bind(py).len();
        self.rows
            .entry(source)
            .or_default()
            .insert(target, LiveKeydictRow { expected_len, dict });
    }

    pub(crate) fn refresh_len(&mut self, py: Python<'_>, source: &str, target: &str) {
        if let Some(row) = self
            .rows
            .get_mut(source)
            .and_then(|targets| targets.get_mut(target))
        {
            row.expected_len = row.dict.bind(py).len();
        }
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
            row.dict.bind(py).clear();
        }
    }

    pub(crate) fn remove_touching_in_place(&mut self, py: Python<'_>, node: &str) {
        let mut removed = Vec::new();
        for (source, targets) in &mut self.rows {
            if source == node {
                removed.extend(targets.drain().map(|(_, row)| row.dict));
            } else if let Some(row) = targets.remove(node) {
                removed.push(row.dict);
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
                row.dict.bind(py).clear();
            }
        }
        self.rows.clear();
    }

    pub(crate) fn traverse(&self, visit: &PyVisit<'_>) -> Result<(), PyTraverseError> {
        for targets in self.rows.values() {
            for row in targets.values() {
                visit.call(&row.dict)?;
            }
        }
        Ok(())
    }
}
