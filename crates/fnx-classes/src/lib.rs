#![forbid(unsafe_code)]

pub mod digraph;

use fnx_runtime::{
    CompatibilityMode, DecisionAction, DecisionRecord, EvidenceLedger, EvidenceTerm, unix_time_ms,
    CgseValue,
};
use indexmap::{IndexMap, IndexSet};
use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use std::collections::HashSet;
use std::fmt;

pub type AttrMap = BTreeMap<String, CgseValue>;

#[derive(Debug, Clone, PartialEq, Eq, Hash)]
struct EdgeKey {
    left: String,
    right: String,
}

impl EdgeKey {
    fn new(left: &str, right: &str) -> Self {
        if left <= right {
            Self {
                left: left.to_owned(),
                right: right.to_owned(),
            }
        } else {
            Self {
                left: right.to_owned(),
                right: left.to_owned(),
            }
        }
    }
}

#[derive(Hash, PartialEq, Eq, Clone, Copy)]
struct EdgeKeyRef<'a> {
    left: &'a str,
    right: &'a str,
}

impl<'a> EdgeKeyRef<'a> {
    fn new(left: &'a str, right: &'a str) -> Self {
        if left <= right {
            Self { left, right }
        } else {
            Self {
                left: right,
                right: left,
            }
        }
    }
}

impl<'a> indexmap::Equivalent<EdgeKey> for EdgeKeyRef<'a> {
    fn equivalent(&self, key: &EdgeKey) -> bool {
        self.left == key.left && self.right == key.right
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum GraphError {
    FailClosed {
        operation: &'static str,
        reason: String,
    },
}

impl fmt::Display for GraphError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::FailClosed { operation, reason } => {
                write!(f, "operation `{operation}` failed closed: {reason}")
            }
        }
    }
}

impl std::error::Error for GraphError {}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct EdgeSnapshot {
    pub left: String,
    pub right: String,
    pub attrs: AttrMap,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct GraphSnapshot {
    pub mode: CompatibilityMode,
    pub nodes: Vec<String>,
    pub edges: Vec<EdgeSnapshot>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct MultiEdgeSnapshot {
    pub left: String,
    pub right: String,
    pub key: usize,
    pub attrs: AttrMap,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct MultiGraphSnapshot {
    pub mode: CompatibilityMode,
    pub nodes: Vec<String>,
    pub edges: Vec<MultiEdgeSnapshot>,
}

#[derive(Debug, Clone)]
pub struct Graph {
    mode: CompatibilityMode,
    revision: u64,
    nodes: IndexMap<String, AttrMap>,
    adjacency: IndexMap<String, IndexSet<String>>,
    edges: IndexMap<EdgeKey, AttrMap>,
    ledger: EvidenceLedger,
}

impl Graph {
    #[must_use]
    pub fn new(mode: CompatibilityMode) -> Self {
        Self {
            mode,
            revision: 0,
            nodes: IndexMap::new(),
            adjacency: IndexMap::new(),
            edges: IndexMap::new(),
            ledger: EvidenceLedger::new(),
        }
    }

    #[must_use]
    pub fn strict() -> Self {
        Self::new(CompatibilityMode::Strict)
    }

    #[must_use]
    pub fn hardened() -> Self {
        Self::new(CompatibilityMode::Hardened)
    }

    #[must_use]
    pub fn mode(&self) -> CompatibilityMode {
        self.mode
    }

    #[must_use]
    pub fn node_count(&self) -> usize {
        self.nodes.len()
    }

    #[must_use]
    pub fn edge_count(&self) -> usize {
        self.edges.len()
    }

    #[must_use]
    pub fn revision(&self) -> u64 {
        self.revision
    }

    #[must_use]
    pub fn has_node(&self, node: &str) -> bool {
        self.nodes.contains_key(node)
    }

    #[must_use]
    pub fn has_edge(&self, left: &str, right: &str) -> bool {
        self.edges.contains_key(&EdgeKeyRef::new(left, right))
    }

    #[must_use]
    pub fn nodes_ordered(&self) -> Vec<&str> {
        self.nodes.keys().map(String::as_str).collect()
    }

    #[must_use]
    pub fn get_node_index(&self, node: &str) -> Option<usize> {
        self.nodes.get_index_of(node)
    }

    #[must_use]
    pub fn get_node_name(&self, index: usize) -> Option<&str> {
        self.nodes.get_index(index).map(|(k, _)| k.as_str())
    }

    #[must_use]
    pub fn neighbors(&self, node: &str) -> Option<Vec<&str>> {
        self.adjacency
            .get(node)
            .map(|neighbors| neighbors.iter().map(String::as_str).collect::<Vec<&str>>())
    }

    #[must_use]
    pub fn neighbors_iter(&self, node: &str) -> Option<impl Iterator<Item = &str> + '_> {
        self.adjacency
            .get(node)
            .map(|neighbors| neighbors.iter().map(String::as_str))
    }

    #[must_use]
    pub fn neighbor_count(&self, node: &str) -> usize {
        self.adjacency.get(node).map_or(0, IndexSet::len)
    }

    /// Return the degree of a node.
    /// Self-loops contribute 2 to the degree (NetworkX convention).
    #[must_use]
    pub fn degree(&self, node: &str) -> usize {
        let count = self.neighbor_count(node);
        // If node has a self-loop, add 1 extra (self-loop contributes 2 total)
        if self.has_edge(node, node) {
            count + 1
        } else {
            count
        }
    }

    #[must_use]
    pub fn node_attrs(&self, node: &str) -> Option<&AttrMap> {
        self.nodes.get(node)
    }

    #[must_use]
    pub fn edge_attrs(&self, left: &str, right: &str) -> Option<&AttrMap> {
        self.edges.get(&EdgeKeyRef::new(left, right))
    }

    #[must_use]
    pub fn evidence_ledger(&self) -> &EvidenceLedger {
        &self.ledger
    }

    /// Type identity: always `false` for undirected Graph.
    #[must_use]
    pub fn is_directed(&self) -> bool {
        false
    }

    /// Type identity: always `false` for Graph (not a multigraph).
    #[must_use]
    pub fn is_multigraph(&self) -> bool {
        false
    }

    pub fn add_node(&mut self, node: impl Into<String>) -> bool {
        self.add_node_with_attrs(node, AttrMap::new())
    }

    pub fn add_node_with_attrs(&mut self, node: impl Into<String>, attrs: AttrMap) -> bool {
        let node = node.into();
        let existed = self.nodes.contains_key(&node);
        let mut changed = !existed;
        let attrs_for_change_check = attrs.clone();
        let attrs_count = {
            let bucket = self.nodes.entry(node.clone()).or_default();
            if !attrs_for_change_check.is_empty()
                && attrs_for_change_check
                    .iter()
                    .any(|(key, value)| bucket.get(key) != Some(value))
            {
                changed = true;
            }
            bucket.extend(attrs);
            bucket.len()
        };
        self.adjacency.entry(node.clone()).or_default();
        if changed {
            self.revision = self.revision.saturating_add(1);
        }
        self.record_decision(
            "add_node",
            0.0,
            false,
            vec![
                EvidenceTerm {
                    signal: "node_preexisting".to_owned(),
                    observed_value: existed.to_string(),
                    log_likelihood_ratio: -3.0,
                },
                EvidenceTerm {
                    signal: "attrs_count".to_owned(),
                    observed_value: attrs_count.to_string(),
                    log_likelihood_ratio: -1.0,
                },
            ],
        );
        !existed
    }

    pub fn add_edge(
        &mut self,
        left: impl Into<String>,
        right: impl Into<String>,
    ) -> Result<(), GraphError> {
        self.add_edge_with_attrs(left, right, AttrMap::new())
    }

    pub fn add_edge_with_attrs(
        &mut self,
        left: impl Into<String>,
        right: impl Into<String>,
        attrs: AttrMap,
    ) -> Result<(), GraphError> {
        let left = left.into();
        let right = right.into();

        let unknown_feature = attrs
            .keys()
            .any(|key| key.starts_with("__fnx_incompatible"));
        let incompatibility_probability = if unknown_feature {
            1.0
        } else if left == right {
            0.22
        } else {
            0.08
        };

        let action = self.record_decision(
            "add_edge",
            incompatibility_probability,
            unknown_feature,
            vec![EvidenceTerm {
                signal: "unknown_incompatible_feature".to_owned(),
                observed_value: unknown_feature.to_string(),
                log_likelihood_ratio: 12.0,
            }],
        );

        if action == DecisionAction::FailClosed {
            return Err(GraphError::FailClosed {
                operation: "add_edge",
                reason: "incompatible edge metadata".to_owned(),
            });
        }

        let mut left_autocreated = false;
        if !self.nodes.contains_key(&left) {
            let _ = self.add_node(left.clone());
            left_autocreated = true;
        }
        let mut right_autocreated = false;
        if left == right {
            right_autocreated = left_autocreated;
        } else if !self.nodes.contains_key(&right) {
            let _ = self.add_node(right.clone());
            right_autocreated = true;
        }

        let edge_key = EdgeKey::new(&left, &right);
        let self_loop = left == right;
        let mut changed = !self.edges.contains_key(&edge_key);
        let edge_attr_count = {
            let edge_attrs = self.edges.entry(edge_key).or_default();
            if !attrs.is_empty()
                && attrs
                    .iter()
                    .any(|(key, value)| edge_attrs.get(key) != Some(value))
            {
                changed = true;
            }
            edge_attrs.extend(attrs);
            edge_attrs.len()
        };

        self.adjacency
            .entry(left.clone())
            .or_default()
            .insert(right.clone());
        self.adjacency
            .entry(right.clone())
            .or_default()
            .insert(left);
        if changed {
            self.revision = self.revision.saturating_add(1);
        }

        self.record_decision(
            "add_edge",
            incompatibility_probability,
            unknown_feature,
            vec![
                EvidenceTerm {
                    signal: "self_loop".to_owned(),
                    observed_value: self_loop.to_string(),
                    log_likelihood_ratio: -0.5,
                },
                EvidenceTerm {
                    signal: "edge_attr_count".to_owned(),
                    observed_value: edge_attr_count.to_string(),
                    log_likelihood_ratio: -2.0,
                },
                EvidenceTerm {
                    signal: "left_autocreated".to_owned(),
                    observed_value: left_autocreated.to_string(),
                    log_likelihood_ratio: -1.25,
                },
                EvidenceTerm {
                    signal: "right_autocreated".to_owned(),
                    observed_value: right_autocreated.to_string(),
                    log_likelihood_ratio: -1.25,
                },
            ],
        );

        Ok(())
    }

    pub fn remove_edge(&mut self, left: &str, right: &str) -> bool {
        let removed = self
            .edges
            .shift_remove(&EdgeKeyRef::new(left, right))
            .is_some();
        if removed {
            if let Some(left_neighbors) = self.adjacency.get_mut(left) {
                left_neighbors.shift_remove(right);
            }
            if left != right
                && let Some(right_neighbors) = self.adjacency.get_mut(right)
            {
                right_neighbors.shift_remove(left);
            }
            self.revision = self.revision.saturating_add(1);
        }
        removed
    }

    pub fn remove_node(&mut self, node: &str) -> bool {
        if !self.nodes.contains_key(node) {
            return false;
        }

        // 1. Remove node from its neighbors' adjacency lists.
        if let Some(neighbors) = self.adjacency.get(node) {
            let neighbor_names: Vec<String> = neighbors.iter().cloned().collect();
            for neighbor in neighbor_names {
                if neighbor != node {
                    if let Some(remote_neighbors) = self.adjacency.get_mut(&neighbor) {
                        remote_neighbors.shift_remove(node);
                    }
                }
            }
        }

        // 2. Remove all incident edges from the edges map using retain (O(E)).
        self.edges.retain(|key, _| key.left != node && key.right != node);

        // 3. Remove node from adjacency and nodes maps.
        self.adjacency.shift_remove(node);
        self.nodes.shift_remove(node);

        self.revision = self.revision.saturating_add(1);
        true
    }

    #[must_use]
    pub fn edges_ordered(&self) -> Vec<EdgeSnapshot> {
        let mut ordered = Vec::with_capacity(self.edges.len());
        let mut seen = HashSet::<EdgeKey>::with_capacity(self.edges.len());

        for node in self.nodes.keys() {
            if let Some(neighbors) = self.adjacency.get(node) {
                for neighbor in neighbors {
                    let key = EdgeKey::new(node, neighbor);
                    if !seen.insert(key.clone()) {
                        continue;
                    }
                    if let Some(attrs) = self.edges.get(&key) {
                        ordered.push(EdgeSnapshot {
                            left: key.left.clone(),
                            right: key.right.clone(),
                            attrs: attrs.clone(),
                        });
                    }
                }
            }
        }

        // Keep a deterministic fallback path if adjacency/edge indexes diverge.
        if ordered.len() < self.edges.len() {
            for (key, attrs) in &self.edges {
                if seen.insert(key.clone()) {
                    ordered.push(EdgeSnapshot {
                        left: key.left.clone(),
                        right: key.right.clone(),
                        attrs: attrs.clone(),
                    });
                }
            }
        }

        ordered
    }

    #[must_use]
    pub fn edges_ordered_borrowed(&self) -> Vec<(&str, &str, &AttrMap)> {
        let mut ordered = Vec::with_capacity(self.edges.len());
        let mut seen = HashSet::<EdgeKeyRef>::with_capacity(self.edges.len());

        for node in self.nodes.keys() {
            if let Some(neighbors) = self.adjacency.get(node) {
                for neighbor in neighbors {
                    let key = EdgeKeyRef::new(node, neighbor);
                    if !seen.insert(key) {
                        continue;
                    }
                    if let Some(attrs) = self.edges.get(&key) {
                        ordered.push((node.as_str(), neighbor.as_str(), attrs));
                    }
                }
            }
        }

        if ordered.len() < self.edges.len() {
            for (key, attrs) in &self.edges {
                let rkey = EdgeKeyRef {
                    left: &key.left,
                    right: &key.right,
                };
                if seen.insert(rkey) {
                    ordered.push((&key.left, &key.right, attrs));
                }
            }
        }

        ordered
    }

    #[must_use]
    pub fn snapshot(&self) -> GraphSnapshot {
        GraphSnapshot {
            mode: self.mode,
            nodes: self.nodes.keys().cloned().collect(),
            edges: self.edges_ordered(),
        }
    }

    fn record_decision(
        &mut self,
        operation: &'static str,
        incompatibility_probability: f64,
        unknown_incompatible_feature: bool,
        evidence: Vec<EvidenceTerm>,
    ) -> DecisionAction {
        let action = fnx_runtime::decision_theoretic_action(
            self.mode,
            incompatibility_probability,
            unknown_incompatible_feature,
        );
        self.ledger.record(DecisionRecord {
            ts_unix_ms: unix_time_ms(),
            operation: operation.to_owned(),
            mode: self.mode,
            action,
            incompatibility_probability,
            rationale: "argmin expected loss over {allow,full_validate,fail_closed}".to_owned(),
            evidence,
        });
        action
    }
}

#[derive(Debug, Clone)]
pub struct MultiGraph {
    mode: CompatibilityMode,
    revision: u64,
    nodes: IndexMap<String, AttrMap>,
    adjacency: IndexMap<String, IndexMap<String, IndexSet<usize>>>,
    edges: IndexMap<EdgeKey, IndexMap<usize, AttrMap>>,
    next_edge_key: IndexMap<EdgeKey, usize>,
    ledger: EvidenceLedger,
}

impl MultiGraph {
    #[must_use]
    pub fn new(mode: CompatibilityMode) -> Self {
        Self {
            mode,
            revision: 0,
            nodes: IndexMap::new(),
            adjacency: IndexMap::new(),
            edges: IndexMap::new(),
            next_edge_key: IndexMap::new(),
            ledger: EvidenceLedger::new(),
        }
    }

    #[must_use]
    pub fn strict() -> Self {
        Self::new(CompatibilityMode::Strict)
    }

    #[must_use]
    pub fn hardened() -> Self {
        Self::new(CompatibilityMode::Hardened)
    }

    #[must_use]
    pub fn mode(&self) -> CompatibilityMode {
        self.mode
    }

    #[must_use]
    pub fn node_count(&self) -> usize {
        self.nodes.len()
    }

    #[must_use]
    pub fn edge_count(&self) -> usize {
        self.edges.values().map(IndexMap::len).sum()
    }

    #[must_use]
    pub fn revision(&self) -> u64 {
        self.revision
    }

    #[must_use]
    pub fn has_node(&self, node: &str) -> bool {
        self.nodes.contains_key(node)
    }

    #[must_use]
    pub fn has_edge(&self, left: &str, right: &str) -> bool {
        self.edges
            .get(&EdgeKeyRef::new(left, right))
            .is_some_and(|edge_bucket| !edge_bucket.is_empty())
    }

    #[must_use]
    pub fn nodes_ordered(&self) -> Vec<&str> {
        self.nodes.keys().map(String::as_str).collect()
    }

    #[must_use]
    pub fn neighbors(&self, node: &str) -> Option<Vec<&str>> {
        self.adjacency
            .get(node)
            .map(|neighbors| neighbors.keys().map(String::as_str).collect::<Vec<&str>>())
    }

    #[must_use]
    pub fn edge_keys(&self, left: &str, right: &str) -> Option<Vec<usize>> {
        self.edges
            .get(&EdgeKeyRef::new(left, right))
            .map(|edge_bucket| edge_bucket.keys().copied().collect::<Vec<usize>>())
    }

    #[must_use]
    pub fn node_attrs(&self, node: &str) -> Option<&AttrMap> {
        self.nodes.get(node)
    }

    #[must_use]
    pub fn edge_attrs(&self, left: &str, right: &str, key: usize) -> Option<&AttrMap> {
        self.edges
            .get(&EdgeKeyRef::new(left, right))
            .and_then(|edge_bucket| edge_bucket.get(&key))
    }

    #[must_use]
    pub fn evidence_ledger(&self) -> &EvidenceLedger {
        &self.ledger
    }

    #[must_use]
    pub fn is_directed(&self) -> bool {
        false
    }

    #[must_use]
    pub fn is_multigraph(&self) -> bool {
        true
    }

    /// Return the degree of a node (total number of parallel edges incident).
    /// Self-loops contribute 2 to the degree each (NetworkX convention).
    #[must_use]
    pub fn degree(&self, node: &str) -> usize {
        self.adjacency.get(node).map_or(0, |neighbors| {
            let mut deg = 0;
            for (neighbor, keys) in neighbors {
                let count = keys.len();
                if neighbor == node {
                    // Self-loops count double (NetworkX convention)
                    deg += count * 2;
                } else {
                    deg += count;
                }
            }
            deg
        })
    }

    pub fn add_node(&mut self, node: impl Into<String>) -> bool {
        self.add_node_with_attrs(node, AttrMap::new())
    }

    pub fn add_node_with_attrs(&mut self, node: impl Into<String>, attrs: AttrMap) -> bool {
        let node = node.into();
        let existed = self.nodes.contains_key(&node);
        let mut changed = !existed;
        let attrs_for_change_check = attrs.clone();
        let attrs_count = {
            let bucket = self.nodes.entry(node.clone()).or_default();
            if !attrs_for_change_check.is_empty()
                && attrs_for_change_check
                    .iter()
                    .any(|(key, value)| bucket.get(key) != Some(value))
            {
                changed = true;
            }
            bucket.extend(attrs);
            bucket.len()
        };
        self.adjacency.entry(node.clone()).or_default();
        if changed {
            self.revision = self.revision.saturating_add(1);
        }
        self.record_decision(
            "add_node",
            0.0,
            false,
            vec![
                EvidenceTerm {
                    signal: "node_preexisting".to_owned(),
                    observed_value: existed.to_string(),
                    log_likelihood_ratio: -3.0,
                },
                EvidenceTerm {
                    signal: "attrs_count".to_owned(),
                    observed_value: attrs_count.to_string(),
                    log_likelihood_ratio: -1.0,
                },
            ],
        );
        !existed
    }

    pub fn add_edge(
        &mut self,
        left: impl Into<String>,
        right: impl Into<String>,
    ) -> Result<usize, GraphError> {
        self.add_edge_impl(left, right, None, AttrMap::new())
    }

    pub fn add_edge_with_attrs(
        &mut self,
        left: impl Into<String>,
        right: impl Into<String>,
        attrs: AttrMap,
    ) -> Result<usize, GraphError> {
        self.add_edge_impl(left, right, None, attrs)
    }

    pub fn add_edge_with_key_and_attrs(
        &mut self,
        left: impl Into<String>,
        right: impl Into<String>,
        key: usize,
        attrs: AttrMap,
    ) -> Result<usize, GraphError> {
        self.add_edge_impl(left, right, Some(key), attrs)
    }

    fn add_edge_impl(
        &mut self,
        left: impl Into<String>,
        right: impl Into<String>,
        explicit_key: Option<usize>,
        attrs: AttrMap,
    ) -> Result<usize, GraphError> {
        let left = left.into();
        let right = right.into();

        let unknown_feature = attrs
            .keys()
            .any(|key| key.starts_with("__fnx_incompatible"));
        let incompatibility_probability = if unknown_feature {
            1.0
        } else if left == right {
            0.22
        } else {
            0.08
        };

        let action = self.record_decision(
            "add_edge",
            incompatibility_probability,
            unknown_feature,
            vec![EvidenceTerm {
                signal: "unknown_incompatible_feature".to_owned(),
                observed_value: unknown_feature.to_string(),
                log_likelihood_ratio: 12.0,
            }],
        );

        if action == DecisionAction::FailClosed {
            return Err(GraphError::FailClosed {
                operation: "add_edge",
                reason: "incompatible edge metadata".to_owned(),
            });
        }

        let mut left_autocreated = false;
        if !self.nodes.contains_key(&left) {
            let _ = self.add_node(left.clone());
            left_autocreated = true;
        }
        let mut right_autocreated = false;
        if left == right {
            right_autocreated = left_autocreated;
        } else if !self.nodes.contains_key(&right) {
            let _ = self.add_node(right.clone());
            right_autocreated = true;
        }

        let edge_key = EdgeKey::new(&left, &right);
        let key =
            explicit_key.unwrap_or_else(|| self.next_edge_key.get(&edge_key).copied().unwrap_or(0));
        let mut changed;
        let edge_attr_count = {
            let edge_bucket = self.edges.entry(edge_key.clone()).or_default();
            changed = !edge_bucket.contains_key(&key);
            let attrs_for_change_check = attrs.clone();
            let edge_attrs = edge_bucket.entry(key).or_default();
            if !attrs_for_change_check.is_empty()
                && attrs_for_change_check
                    .iter()
                    .any(|(attr_key, value)| edge_attrs.get(attr_key) != Some(value))
            {
                changed = true;
            }
            edge_attrs.extend(attrs);
            edge_bucket.len()
        };
        if explicit_key.is_none() {
            let next_key = key.saturating_add(1);
            self.next_edge_key
                .entry(edge_key)
                .and_modify(|next| *next = (*next).max(next_key))
                .or_insert(next_key);
        }

        self.adjacency
            .entry(left.clone())
            .or_default()
            .entry(right.clone())
            .or_default()
            .insert(key);
        if left != right {
            self.adjacency
                .entry(right.clone())
                .or_default()
                .entry(left.clone())
                .or_default()
                .insert(key);
        }
        if changed {
            self.revision = self.revision.saturating_add(1);
        }

        self.record_decision(
            "add_edge",
            incompatibility_probability,
            unknown_feature,
            vec![
                EvidenceTerm {
                    signal: "edge_key".to_owned(),
                    observed_value: key.to_string(),
                    log_likelihood_ratio: -2.0,
                },
                EvidenceTerm {
                    signal: "edge_attr_count".to_owned(),
                    observed_value: edge_attr_count.to_string(),
                    log_likelihood_ratio: -2.0,
                },
                EvidenceTerm {
                    signal: "left_autocreated".to_owned(),
                    observed_value: left_autocreated.to_string(),
                    log_likelihood_ratio: -1.25,
                },
                EvidenceTerm {
                    signal: "right_autocreated".to_owned(),
                    observed_value: right_autocreated.to_string(),
                    log_likelihood_ratio: -1.25,
                },
            ],
        );

        Ok(key)
    }

    pub fn remove_edge(&mut self, left: &str, right: &str, key: Option<usize>) -> bool {
        let edge_key = EdgeKeyRef::new(left, right);
        let removal_key = key.or_else(|| {
            self.edges
                .get(&edge_key)
                .and_then(|edge_bucket| edge_bucket.keys().next_back().copied())
        });

        let Some(removal_key) = removal_key else {
            return false;
        };

        let removed = self
            .edges
            .get_mut(&edge_key)
            .is_some_and(|edge_bucket| edge_bucket.shift_remove(&removal_key).is_some());
        if !removed {
            return false;
        }

        let should_drop_bucket = self.edges.get(&edge_key).is_some_and(IndexMap::is_empty);
        if should_drop_bucket {
            self.edges.shift_remove(&edge_key);
            self.next_edge_key.shift_remove(&edge_key);
        }

        self.remove_adjacency_key(left, right, removal_key);
        self.remove_adjacency_key(right, left, removal_key);
        self.revision = self.revision.saturating_add(1);
        true
    }

    pub fn remove_node(&mut self, node: &str) -> bool {
        if !self.nodes.contains_key(node) {
            return false;
        }

        // 1. Remove node from its neighbors' adjacency lists.
        if let Some(neighbors) = self.adjacency.get(node) {
            let neighbor_names: Vec<String> = neighbors.keys().cloned().collect();
            for neighbor in neighbor_names {
                if neighbor != node {
                    if let Some(remote_neighbors) = self.adjacency.get_mut(&neighbor) {
                        remote_neighbors.shift_remove(node);
                    }
                }
            }
        }

        // 2. Remove all incident edges from edges and next_edge_key maps using retain (O(E)).
        self.edges.retain(|key, _| key.left != node && key.right != node);
        self.next_edge_key.retain(|key, _| key.left != node && key.right != node);

        // 3. Remove node from adjacency and nodes maps.
        self.adjacency.shift_remove(node);
        self.nodes.shift_remove(node);
        self.revision = self.revision.saturating_add(1);
        true
    }

    #[must_use]
    pub fn edges_ordered(&self) -> Vec<MultiEdgeSnapshot> {
        let mut ordered = Vec::with_capacity(self.edge_count());
        let mut seen = HashSet::<(String, String, usize)>::with_capacity(self.edge_count());

        for node in self.nodes.keys() {
            if let Some(neighbors) = self.adjacency.get(node) {
                for neighbor in neighbors.keys() {
                    let pair = EdgeKeyRef::new(node, neighbor);
                    if let Some(edge_bucket) = self.edges.get(&pair) {
                        for (key, attrs) in edge_bucket {
                            let instance = (pair.left.to_owned(), pair.right.to_owned(), *key);
                            if !seen.insert(instance.clone()) {
                                continue;
                            }
                            ordered.push(MultiEdgeSnapshot {
                                left: instance.0,
                                right: instance.1,
                                key: instance.2,
                                attrs: attrs.clone(),
                            });
                        }
                    }
                }
            }
        }

        if ordered.len() < self.edge_count() {
            for (pair, edge_bucket) in &self.edges {
                for (key, attrs) in edge_bucket {
                    let instance = (pair.left.clone(), pair.right.clone(), *key);
                    if seen.insert(instance.clone()) {
                        ordered.push(MultiEdgeSnapshot {
                            left: instance.0,
                            right: instance.1,
                            key: instance.2,
                            attrs: attrs.clone(),
                        });
                    }
                }
            }
        }

        ordered
    }

    #[must_use]
    pub fn edges_ordered_borrowed(&self) -> Vec<(&str, &str, usize, &AttrMap)> {
        let mut ordered = Vec::with_capacity(self.edge_count());
        let mut seen = HashSet::<(EdgeKeyRef, usize)>::with_capacity(self.edge_count());

        for node in self.nodes.keys() {
            if let Some(neighbors) = self.adjacency.get(node) {
                for neighbor in neighbors.keys() {
                    let pair = EdgeKeyRef::new(node, neighbor);
                    if let Some(edge_bucket) = self.edges.get(&pair) {
                        for (key, attrs) in edge_bucket {
                            if !seen.insert((pair, *key)) {
                                continue;
                            }
                            ordered.push((pair.left, pair.right, *key, attrs));
                        }
                    }
                }
            }
        }

        if ordered.len() < self.edge_count() {
            for (pair, edge_bucket) in &self.edges {
                let rpair = EdgeKeyRef {
                    left: &pair.left,
                    right: &pair.right,
                };
                for (key, attrs) in edge_bucket {
                    if seen.insert((rpair, *key)) {
                        ordered.push((rpair.left, rpair.right, *key, attrs));
                    }
                }
            }
        }

        ordered
    }

    #[must_use]
    pub fn snapshot(&self) -> MultiGraphSnapshot {
        MultiGraphSnapshot {
            mode: self.mode,
            nodes: self.nodes.keys().cloned().collect(),
            edges: self.edges_ordered(),
        }
    }

    fn remove_adjacency_key(&mut self, source: &str, target: &str, key: usize) {
        let mut drop_neighbor = false;
        if let Some(neighbors) = self.adjacency.get_mut(source)
            && let Some(keys) = neighbors.get_mut(target)
        {
            keys.shift_remove(&key);
            drop_neighbor = keys.is_empty();
        }
        if drop_neighbor && let Some(neighbors) = self.adjacency.get_mut(source) {
            neighbors.shift_remove(target);
        }
    }

    fn record_decision(
        &mut self,
        operation: &'static str,
        incompatibility_probability: f64,
        unknown_incompatible_feature: bool,
        evidence: Vec<EvidenceTerm>,
    ) -> DecisionAction {
        let action = fnx_runtime::decision_theoretic_action(
            self.mode,
            incompatibility_probability,
            unknown_incompatible_feature,
        );
        self.ledger.record(DecisionRecord {
            ts_unix_ms: unix_time_ms(),
            operation: operation.to_owned(),
            mode: self.mode,
            action,
            incompatibility_probability,
            rationale: "argmin expected loss over {allow,full_validate,fail_closed}".to_owned(),
            evidence,
        });
        action
    }
}

#[cfg(test)]
mod tests {
    use super::{AttrMap, Graph, GraphError, MultiGraph};
    use fnx_runtime::{CompatibilityMode, DecisionAction, DecisionRecord};
    use proptest::prelude::*;
    use std::collections::BTreeSet;

    fn node_name(id: u8) -> String {
        format!("n{}", id % 8)
    }

    fn canonical_edge(left: &str, right: &str) -> (String, String) {
        if left <= right {
            (left.to_owned(), right.to_owned())
        } else {
            (right.to_owned(), left.to_owned())
        }
    }

    #[test]
    fn edges_ordered_tracks_node_and_neighbor_iteration_order() {
        let mut graph = Graph::strict();
        graph
            .add_edge_with_attrs("a", "b", AttrMap::new())
            .expect("edge add should succeed");
        graph
            .add_edge_with_attrs("b", "c", AttrMap::new())
            .expect("edge add should succeed");
        graph
            .add_edge_with_attrs("a", "c", AttrMap::new())
            .expect("edge add should succeed");

        let pairs = graph
            .edges_ordered()
            .into_iter()
            .map(|edge| (edge.left, edge.right))
            .collect::<Vec<(String, String)>>();
        assert_eq!(
            pairs,
            vec![
                ("a".to_owned(), "b".to_owned()),
                ("a".to_owned(), "c".to_owned()),
                ("b".to_owned(), "c".to_owned()),
            ]
        );
    }

    fn assert_graph_core_invariants(graph: &Graph) {
        let mut unique_edges = BTreeSet::new();
        for node in graph.nodes_ordered() {
            let neighbors = graph
                .neighbors(node)
                .expect("graph nodes should always have adjacency buckets");
            for neighbor in neighbors {
                assert!(graph.has_node(neighbor));
                assert!(graph.has_edge(node, neighbor));
                let reverse_neighbors = graph
                    .neighbors(neighbor)
                    .expect("neighbor should always have adjacency bucket");
                assert!(reverse_neighbors.contains(&node));
                unique_edges.insert(canonical_edge(node, neighbor));
            }
        }
        assert_eq!(graph.edge_count(), unique_edges.len());
    }

    fn assert_multigraph_core_invariants(graph: &MultiGraph) {
        let mut edge_instances = BTreeSet::new();
        for node in graph.nodes_ordered() {
            let neighbors = graph
                .neighbors(node)
                .expect("multigraph nodes should always have adjacency buckets");
            for neighbor in neighbors {
                assert!(graph.has_node(neighbor));
                assert!(graph.has_edge(node, neighbor));
                let reverse_neighbors = graph
                    .neighbors(neighbor)
                    .expect("neighbor should always have adjacency bucket");
                assert!(reverse_neighbors.contains(&node));
                let keys = graph
                    .edge_keys(node, neighbor)
                    .expect("parallel edge bucket should exist");
                for key in keys {
                    let canonical = canonical_edge(node, neighbor);
                    edge_instances.insert((canonical.0, canonical.1, key));
                }
            }
        }
        assert_eq!(graph.edge_count(), edge_instances.len());
    }

    fn assert_decision_record_schema(record: &DecisionRecord, expected_mode: CompatibilityMode) {
        assert!(record.ts_unix_ms > 0);
        assert!(!record.operation.trim().is_empty());
        assert_eq!(record.mode, expected_mode);
        assert!((0.0..=1.0).contains(&record.incompatibility_probability));
        assert!(!record.rationale.trim().is_empty());
        assert!(!record.evidence.is_empty());
        for term in &record.evidence {
            assert!(!term.signal.trim().is_empty());
            assert!(!term.observed_value.trim().is_empty());
        }
    }

    #[test]
    fn add_edge_autocreates_nodes_and_preserves_order() {
        let mut graph = Graph::strict();
        graph
            .add_edge_with_attrs("a", "b", AttrMap::new())
            .expect("edge insert should succeed");
        graph
            .add_edge_with_attrs("a", "c", AttrMap::new())
            .expect("edge insert should succeed");

        assert_eq!(graph.node_count(), 3);
        assert_eq!(graph.edge_count(), 2);
        assert_eq!(graph.nodes_ordered(), vec!["a", "b", "c"]);
        assert_eq!(graph.neighbors("a"), Some(vec!["b", "c"]));
    }

    #[test]
    fn neighbors_iter_preserves_deterministic_order() {
        let mut graph = Graph::strict();
        graph.add_edge("a", "b").expect("edge add should succeed");
        graph.add_edge("a", "c").expect("edge add should succeed");
        graph.add_edge("a", "d").expect("edge add should succeed");

        let neighbors = graph
            .neighbors_iter("a")
            .expect("neighbors should exist")
            .collect::<Vec<&str>>();
        assert_eq!(neighbors, vec!["b", "c", "d"]);
    }

    #[test]
    fn neighbor_count_matches_neighbors_len() {
        let mut graph = Graph::strict();
        graph.add_edge("a", "b").expect("edge add should succeed");
        graph.add_edge("a", "c").expect("edge add should succeed");
        assert_eq!(graph.neighbor_count("a"), 2);
        assert_eq!(graph.neighbor_count("missing"), 0);
    }

    #[test]
    fn repeated_edge_updates_attrs_in_place() {
        let mut graph = Graph::strict();
        let mut first = AttrMap::new();
        first.insert("weight".to_owned(), "1".to_owned());
        graph
            .add_edge_with_attrs("a", "b", first)
            .expect("edge insert should succeed");

        let mut second = AttrMap::new();
        second.insert("color".to_owned(), "blue".to_owned());
        graph
            .add_edge_with_attrs("b", "a", second)
            .expect("edge update should succeed");

        let attrs = graph
            .edge_attrs("a", "b")
            .expect("edge attrs should be present");
        assert_eq!(attrs.get("weight"), Some(&"1".to_owned()));
        assert_eq!(attrs.get("color"), Some(&"blue".to_owned()));
        assert_eq!(graph.edge_count(), 1);
    }

    #[test]
    fn remove_node_removes_incident_edges() {
        let mut graph = Graph::strict();
        graph.add_edge("a", "b").expect("edge add should succeed");
        graph.add_edge("b", "c").expect("edge add should succeed");
        assert!(graph.remove_node("b"));
        assert_eq!(graph.node_count(), 2);
        assert_eq!(graph.edge_count(), 0);
    }

    #[test]
    fn strict_mode_fails_closed_for_unknown_incompatible_feature() {
        let mut graph = Graph::strict();
        let mut attrs = AttrMap::new();
        attrs.insert("__fnx_incompatible_decoder".to_owned(), "v2".to_owned());
        let err = graph
            .add_edge_with_attrs("a", "b", attrs)
            .expect_err("strict mode should fail closed");

        assert_eq!(
            err,
            GraphError::FailClosed {
                operation: "add_edge",
                reason: "incompatible edge metadata".to_owned(),
            }
        );

        let last_record = graph
            .evidence_ledger()
            .records()
            .last()
            .expect("strict fail-closed path should emit a ledger row");
        assert_decision_record_schema(last_record, CompatibilityMode::Strict);
        assert_eq!(last_record.operation, "add_edge");
        assert_eq!(last_record.action, DecisionAction::FailClosed);
        assert!(
            last_record
                .evidence
                .iter()
                .any(|term| term.signal == "unknown_incompatible_feature")
        );
    }

    #[test]
    fn revision_increments_on_mutating_operations() {
        let mut graph = Graph::strict();
        let r0 = graph.revision();
        let _ = graph.add_node("a");
        let r1 = graph.revision();
        assert!(r1 > r0);

        graph.add_edge("a", "b").expect("edge add should succeed");
        let r2 = graph.revision();
        assert!(r2 > r1);

        let _ = graph.remove_edge("a", "b");
        let r3 = graph.revision();
        assert!(r3 > r2);
    }

    #[test]
    fn hardened_self_loop_records_full_validate_decision() {
        let mut graph = Graph::hardened();
        graph
            .add_edge("loop", "loop")
            .expect("hardened self-loop edge should be accepted");

        let add_edge_record = graph
            .evidence_ledger()
            .records()
            .iter()
            .rev()
            .find(|record| record.operation == "add_edge")
            .expect("add_edge operation should emit ledger row");
        assert_decision_record_schema(add_edge_record, CompatibilityMode::Hardened);
        assert_eq!(add_edge_record.action, DecisionAction::FullValidate);
        assert!(
            add_edge_record
                .evidence
                .iter()
                .any(|term| term.signal == "self_loop" && term.observed_value == "true")
        );
    }

    #[test]
    fn snapshot_roundtrip_replays_to_identical_state() {
        let mut graph = Graph::strict();

        let mut first_attrs = AttrMap::new();
        first_attrs.insert("weight".to_owned(), "7".to_owned());
        graph
            .add_edge_with_attrs("a", "b", first_attrs)
            .expect("edge insert should succeed");

        let mut second_attrs = AttrMap::new();
        second_attrs.insert("color".to_owned(), "green".to_owned());
        graph
            .add_edge_with_attrs("b", "c", second_attrs)
            .expect("edge insert should succeed");

        let snapshot = graph.snapshot();
        let mut replayed = Graph::new(snapshot.mode);
        for node in &snapshot.nodes {
            let _ = replayed.add_node(node.clone());
        }
        for edge in &snapshot.edges {
            replayed
                .add_edge_with_attrs(edge.left.clone(), edge.right.clone(), edge.attrs.clone())
                .expect("snapshot replay should be valid");
        }

        assert_eq!(replayed.snapshot(), snapshot);
        assert_graph_core_invariants(&replayed);
    }

    #[test]
    fn multigraph_tracks_parallel_edges_with_distinct_keys() {
        let mut graph = MultiGraph::strict();
        let first = graph.add_edge("a", "b").expect("edge add should succeed");
        let second = graph.add_edge("a", "b").expect("edge add should succeed");

        assert_ne!(first, second);
        assert_eq!(graph.edge_count(), 2);
        assert_eq!(graph.edge_keys("a", "b"), Some(vec![0, 1]));
        assert_multigraph_core_invariants(&graph);
    }

    #[test]
    fn multigraph_remove_edge_without_key_removes_latest_instance() {
        let mut graph = MultiGraph::strict();
        let first = graph.add_edge("a", "b").expect("edge add should succeed");
        let second = graph.add_edge("a", "b").expect("edge add should succeed");

        assert!(graph.remove_edge("a", "b", None));
        assert_eq!(graph.edge_count(), 1);
        assert_eq!(graph.edge_keys("a", "b"), Some(vec![first]));
        assert_ne!(first, second);
        assert_multigraph_core_invariants(&graph);
    }

    #[test]
    fn multigraph_remove_node_clears_parallel_incident_edges() {
        let mut graph = MultiGraph::strict();
        let _ = graph.add_edge("a", "b").expect("edge add should succeed");
        let _ = graph.add_edge("a", "b").expect("edge add should succeed");
        let _ = graph.add_edge("b", "c").expect("edge add should succeed");

        assert!(graph.remove_node("b"));
        assert_eq!(graph.edge_count(), 0);
        assert!(!graph.has_node("b"));
        assert_eq!(graph.neighbors("a"), Some(vec![]));
        assert_eq!(graph.neighbors("c"), Some(vec![]));
        assert_multigraph_core_invariants(&graph);
    }

    #[test]
    fn multigraph_roundtrips_sparse_snapshot_keys() {
        let mut graph = MultiGraph::strict();
        assert_eq!(
            graph.add_edge("a", "b").expect("edge add should succeed"),
            0
        );
        assert_eq!(
            graph.add_edge("a", "b").expect("edge add should succeed"),
            1
        );
        assert_eq!(
            graph.add_edge("a", "b").expect("edge add should succeed"),
            2
        );
        assert!(graph.remove_edge("a", "b", Some(1)));
        assert_eq!(
            graph.add_edge("a", "b").expect("edge add should succeed"),
            3
        );

        let snapshot = graph.snapshot();
        assert_eq!(
            snapshot
                .edges
                .iter()
                .map(|edge| edge.key)
                .collect::<Vec<_>>(),
            vec![0, 2, 3]
        );

        let mut replayed = MultiGraph::new(snapshot.mode);
        for node in &snapshot.nodes {
            let _ = replayed.add_node(node.clone());
        }
        for edge in &snapshot.edges {
            replayed
                .add_edge_with_key_and_attrs(
                    edge.left.clone(),
                    edge.right.clone(),
                    edge.key,
                    edge.attrs.clone(),
                )
                .expect("snapshot replay should preserve explicit keys");
        }

        assert_eq!(replayed.snapshot(), snapshot);
        assert_multigraph_core_invariants(&replayed);
    }

    proptest! {
        #[test]
        fn prop_core_invariants_hold_for_mixed_edge_mutations(
            ops in prop::collection::vec((0_u8..8, 0_u8..8, any::<bool>()), 1..80),
        ) {
            let mut graph = Graph::strict();
            let mut last_revision = graph.revision();

            for (left_id, right_id, is_add) in ops {
                let left = node_name(left_id);
                let right = node_name(right_id);
                if is_add {
                    prop_assert!(graph.add_edge(left.clone(), right.clone()).is_ok());
                } else {
                    let _ = graph.remove_edge(&left, &right);
                }
                let revision = graph.revision();
                prop_assert!(revision >= last_revision);
                last_revision = revision;
                assert_graph_core_invariants(&graph);
            }
        }

        #[test]
        fn prop_snapshot_is_deterministic_for_same_operation_stream(
            ops in prop::collection::vec((0_u8..8, 0_u8..8, 0_u8..3), 0..64),
        ) {
            let mut graph_left = Graph::hardened();
            let mut graph_right = Graph::hardened();

            for (left_id, right_id, attrs_variant) in ops {
                let left = node_name(left_id);
                let right = node_name(right_id);
                let mut attrs = AttrMap::new();
                if attrs_variant == 1 {
                    attrs.insert("weight".to_owned(), (left_id % 5).to_string());
                } else if attrs_variant == 2 {
                    attrs.insert("tag".to_owned(), format!("k{}", right_id % 4));
                }
                prop_assert!(
                    graph_left
                        .add_edge_with_attrs(left.clone(), right.clone(), attrs.clone())
                        .is_ok()
                );
                prop_assert!(
                    graph_right
                        .add_edge_with_attrs(left, right, attrs)
                        .is_ok()
                );
            }

            prop_assert_eq!(graph_left.snapshot(), graph_right.snapshot());
            prop_assert_eq!(graph_left.snapshot(), graph_left.snapshot());
        }

        #[test]
        fn prop_reapplying_identical_edge_attrs_is_revision_stable(
            left_id in 0_u8..8,
            right_id in 0_u8..8,
            weight in 0_u16..5000,
        ) {
            let mut graph = Graph::strict();
            let left = node_name(left_id);
            let right = node_name(right_id);
            let mut attrs = AttrMap::new();
            attrs.insert("weight".to_owned(), weight.to_string());

            prop_assert!(
                graph
                    .add_edge_with_attrs(left.clone(), right.clone(), attrs.clone())
                    .is_ok()
            );
            let revision_after_first = graph.revision();
            prop_assert!(
                graph
                    .add_edge_with_attrs(left, right, attrs)
                    .is_ok()
            );
            prop_assert_eq!(graph.revision(), revision_after_first);
        }

        #[test]
        fn prop_remove_node_clears_incident_edges(
            ops in prop::collection::vec((0_u8..8, 0_u8..8), 1..64),
            target_id in 0_u8..8,
        ) {
            let mut graph = Graph::strict();
            for (left_id, right_id) in ops {
                let left = node_name(left_id);
                let right = node_name(right_id);
                prop_assert!(graph.add_edge(left, right).is_ok());
            }

            let target = node_name(target_id);
            let removed = graph.remove_node(&target);
            if removed {
                prop_assert!(!graph.has_node(&target));
                for node in graph.nodes_ordered() {
                    let neighbors = graph
                        .neighbors(node)
                        .expect("graph nodes should always have adjacency buckets");
                    prop_assert!(!neighbors.contains(&target.as_str()));
                    prop_assert!(!graph.has_edge(node, &target));
                }
            }
            assert_graph_core_invariants(&graph);
        }

        #[test]
        fn prop_decision_ledger_records_follow_schema(
            ops in prop::collection::vec((0_u8..8, 0_u8..8, 0_u8..4), 1..72),
        ) {
            let mut graph = Graph::strict();
            for (left_id, right_id, attrs_kind) in ops {
                let left = node_name(left_id);
                let right = node_name(right_id);
                let mut attrs = AttrMap::new();
                match attrs_kind {
                    0 => {}
                    1 => {
                        attrs.insert("weight".to_owned(), (left_id % 9).to_string());
                    }
                    2 => {
                        attrs.insert("color".to_owned(), format!("c{}", right_id % 6));
                    }
                    _ => {
                        attrs.insert("__fnx_incompatible_decoder".to_owned(), "v2".to_owned());
                    }
                }
                let _ = graph.add_edge_with_attrs(left, right, attrs);
            }

            let records = graph.evidence_ledger().records();
            prop_assert!(!records.is_empty());
            for record in records {
                assert_decision_record_schema(record, CompatibilityMode::Strict);
                if record.operation == "add_node" {
                    prop_assert_eq!(record.action, DecisionAction::Allow);
                    prop_assert!(record.evidence.iter().any(|term| term.signal == "node_preexisting"));
                    prop_assert!(record.evidence.iter().any(|term| term.signal == "attrs_count"));
                } else {
                    prop_assert_eq!(&record.operation, "add_edge");
                    if record.action == DecisionAction::FailClosed {
                        prop_assert!(
                            record
                                .evidence
                                .iter()
                                .any(|term| term.signal == "unknown_incompatible_feature")
                        );
                    } else {
                        prop_assert_eq!(record.action, DecisionAction::FullValidate);
                        // add_edge records two decisions: a pre-check (only
                        // unknown_incompatible_feature) and a post-check (with
                        // self_loop, edge_attr_count, etc.). Both are valid.
                        let is_precheck = record
                            .evidence
                            .iter()
                            .any(|term| term.signal == "unknown_incompatible_feature")
                            && !record
                                .evidence
                                .iter()
                                .any(|term| term.signal == "edge_attr_count");
                        if !is_precheck {
                            prop_assert!(record.evidence.iter().any(|term| term.signal == "edge_attr_count"));
                            prop_assert!(record.evidence.iter().any(|term| term.signal == "self_loop"));
                        }
                    }
                }
            }
        }
    }
}
