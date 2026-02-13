#![forbid(unsafe_code)]

use fnx_runtime::{
    CompatibilityMode, DecisionAction, DecisionRecord, EvidenceLedger, EvidenceTerm,
    decision_theoretic_action, unix_time_ms,
};
use indexmap::{IndexMap, IndexSet};
use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use std::fmt;

pub type AttrMap = BTreeMap<String, String>;

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
        self.edges.contains_key(&EdgeKey::new(left, right))
    }

    #[must_use]
    pub fn nodes_ordered(&self) -> Vec<&str> {
        self.nodes.keys().map(String::as_str).collect()
    }

    #[must_use]
    pub fn neighbors(&self, node: &str) -> Option<Vec<&str>> {
        self.adjacency
            .get(node)
            .map(|neighbors| neighbors.iter().map(String::as_str).collect::<Vec<&str>>())
    }

    #[must_use]
    pub fn node_attrs(&self, node: &str) -> Option<&AttrMap> {
        self.nodes.get(node)
    }

    #[must_use]
    pub fn edge_attrs(&self, left: &str, right: &str) -> Option<&AttrMap> {
        self.edges.get(&EdgeKey::new(left, right))
    }

    #[must_use]
    pub fn evidence_ledger(&self) -> &EvidenceLedger {
        &self.ledger
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
            DecisionAction::Allow,
            0.0,
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

        let action =
            decision_theoretic_action(self.mode, incompatibility_probability, unknown_feature);

        if action == DecisionAction::FailClosed {
            self.record_decision(
                "add_edge",
                action,
                incompatibility_probability,
                vec![EvidenceTerm {
                    signal: "unknown_incompatible_feature".to_owned(),
                    observed_value: unknown_feature.to_string(),
                    log_likelihood_ratio: 12.0,
                }],
            );
            return Err(GraphError::FailClosed {
                operation: "add_edge",
                reason: "incompatible edge metadata".to_owned(),
            });
        }

        self.add_node(left.clone());
        self.add_node(right.clone());

        let edge_key = EdgeKey::new(&left, &right);
        let self_loop = left == right;
        let mut changed = !self.edges.contains_key(&edge_key);
        let attrs_for_change_check = attrs.clone();
        let edge_attr_count = {
            let edge_attrs = self.edges.entry(edge_key).or_default();
            if !attrs_for_change_check.is_empty()
                && attrs_for_change_check
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
            action,
            incompatibility_probability,
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
            ],
        );

        Ok(())
    }

    pub fn remove_edge(&mut self, left: &str, right: &str) -> bool {
        let removed = self
            .edges
            .shift_remove(&EdgeKey::new(left, right))
            .is_some();
        if removed {
            if let Some(left_neighbors) = self.adjacency.get_mut(left) {
                left_neighbors.shift_remove(right);
            }
            if let Some(right_neighbors) = self.adjacency.get_mut(right) {
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

        let incident_neighbors = self
            .adjacency
            .get(node)
            .map_or_else(Vec::new, |neighbors| neighbors.iter().cloned().collect());

        for neighbor in &incident_neighbors {
            let _ = self.remove_edge(node, neighbor);
        }

        self.adjacency.shift_remove(node);
        self.nodes.shift_remove(node);
        self.revision = self.revision.saturating_add(1);
        true
    }

    #[must_use]
    pub fn edges_ordered(&self) -> Vec<EdgeSnapshot> {
        self.edges
            .iter()
            .map(|(key, attrs)| EdgeSnapshot {
                left: key.left.clone(),
                right: key.right.clone(),
                attrs: attrs.clone(),
            })
            .collect()
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
        action: DecisionAction,
        incompatibility_probability: f64,
        evidence: Vec<EvidenceTerm>,
    ) {
        self.ledger.record(DecisionRecord {
            ts_unix_ms: unix_time_ms(),
            operation: operation.to_owned(),
            mode: self.mode,
            action,
            incompatibility_probability,
            rationale: "argmin expected loss over {allow,full_validate,fail_closed}".to_owned(),
            evidence,
        });
    }
}

#[cfg(test)]
mod tests {
    use super::{AttrMap, Graph, GraphError};

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
}
