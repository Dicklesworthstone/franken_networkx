//! Directed graph (DiGraph) storage.
//!
//! Mirrors the undirected [`Graph`] API with directed semantics:
//! - Edge `(u, v)` is distinct from `(v, u)`.
//! - Adjacency is split into **successors** (outgoing) and **predecessors** (incoming).
//! - `neighbors(n)` returns successors (matching NetworkX convention).

use crate::{AttrMap, EdgeSnapshot, GraphError};
use fnx_runtime::{CompatibilityMode, DecisionAction, EvidenceLedger, EvidenceTerm, RuntimePolicy};
use indexmap::{IndexMap, IndexSet};
use serde::{Deserialize, Serialize};

// ---------------------------------------------------------------------------
// DirectedEdgeKey — order-preserving (NOT canonicalized)
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, PartialEq, Eq, Hash)]
struct DirectedEdgeKey {
    source: String,
    target: String,
}

impl DirectedEdgeKey {
    fn new(source: &str, target: &str) -> Self {
        Self {
            source: source.to_owned(),
            target: target.to_owned(),
        }
    }
}

#[derive(Hash, PartialEq, Eq, Clone, Copy)]
struct DirectedEdgeKeyRef<'a> {
    source: &'a str,
    target: &'a str,
}

impl<'a> DirectedEdgeKeyRef<'a> {
    fn new(source: &'a str, target: &'a str) -> Self {
        Self { source, target }
    }
}

impl<'a> indexmap::Equivalent<DirectedEdgeKey> for DirectedEdgeKeyRef<'a> {
    fn equivalent(&self, key: &DirectedEdgeKey) -> bool {
        self.source == key.source && self.target == key.target
    }
}

// ---------------------------------------------------------------------------
// DiGraphSnapshot
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct DiGraphSnapshot {
    pub mode: CompatibilityMode,
    pub nodes: Vec<String>,
    /// br-snapnodeattrs: per-node attributes preserved across snapshot
    /// round-trip. Defaults to empty for backward compatibility.
    #[serde(default)]
    pub node_attrs: std::collections::BTreeMap<String, AttrMap>,
    /// Edges in source→target order. `left` = source, `right` = target.
    pub edges: Vec<EdgeSnapshot>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct MultiDiEdgeSnapshot {
    pub source: String,
    pub target: String,
    pub key: usize,
    pub attrs: AttrMap,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct MultiDiGraphSnapshot {
    pub mode: CompatibilityMode,
    pub nodes: Vec<String>,
    /// See DiGraphSnapshot::node_attrs.
    #[serde(default)]
    pub node_attrs: std::collections::BTreeMap<String, AttrMap>,
    pub edges: Vec<MultiDiEdgeSnapshot>,
}

// ---------------------------------------------------------------------------
// DiGraph
// ---------------------------------------------------------------------------

#[derive(Debug, Clone)]
pub struct DiGraph {
    mode: CompatibilityMode,
    revision: u64,
    nodes: IndexMap<String, AttrMap>,
    /// Outgoing adjacency: node → set of successors.
    successors: IndexMap<String, IndexSet<String>>,
    /// Incoming adjacency: node → set of predecessors.
    predecessors: IndexMap<String, IndexSet<String>>,
    /// Directed edges keyed by (source, target) — order matters.
    edges: IndexMap<DirectedEdgeKey, AttrMap>,
    runtime_policy: RuntimePolicy,
}

impl DiGraph {
    // -----------------------------------------------------------------------
    // Constructors
    // -----------------------------------------------------------------------

    #[must_use]
    pub fn new(mode: CompatibilityMode) -> Self {
        Self {
            mode,
            revision: 0,
            nodes: IndexMap::new(),
            successors: IndexMap::new(),
            predecessors: IndexMap::new(),
            edges: IndexMap::new(),
            runtime_policy: RuntimePolicy::new(mode),
        }
    }

    #[must_use]
    pub fn with_runtime_policy(runtime_policy: RuntimePolicy) -> Self {
        let mode = runtime_policy.mode();
        Self {
            mode,
            revision: 0,
            nodes: IndexMap::new(),
            successors: IndexMap::new(),
            predecessors: IndexMap::new(),
            edges: IndexMap::new(),
            runtime_policy,
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

    // -----------------------------------------------------------------------
    // Read-only queries
    // -----------------------------------------------------------------------

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

    /// Check for directed edge source→target.
    #[must_use]
    pub fn has_edge(&self, source: &str, target: &str) -> bool {
        self.edges
            .contains_key(&DirectedEdgeKeyRef::new(source, target))
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

    // -- Directed adjacency queries ----------------------------------------

    /// Successors of `node` (outgoing neighbors). Returns `None` if node absent.
    #[must_use]
    pub fn successors(&self, node: &str) -> Option<Vec<&str>> {
        self.successors
            .get(node)
            .map(|s| s.iter().map(String::as_str).collect())
    }

    #[must_use]
    pub fn successors_iter(&self, node: &str) -> Option<impl Iterator<Item = &str> + '_> {
        self.successors
            .get(node)
            .map(|s| s.iter().map(String::as_str))
    }

    /// Predecessors of `node` (incoming neighbors). Returns `None` if node absent.
    #[must_use]
    pub fn predecessors(&self, node: &str) -> Option<Vec<&str>> {
        self.predecessors
            .get(node)
            .map(|p| p.iter().map(String::as_str).collect())
    }

    #[must_use]
    pub fn predecessors_iter(&self, node: &str) -> Option<impl Iterator<Item = &str> + '_> {
        self.predecessors
            .get(node)
            .map(|p| p.iter().map(String::as_str))
    }

    /// Neighbors = successors (matches NetworkX `DiGraph.neighbors()` convention).
    #[must_use]
    pub fn neighbors(&self, node: &str) -> Option<Vec<&str>> {
        self.successors(node)
    }

    #[must_use]
    pub fn neighbors_iter(&self, node: &str) -> Option<impl Iterator<Item = &str> + '_> {
        self.successors_iter(node)
    }

    #[must_use]
    pub fn neighbor_count(&self, node: &str) -> usize {
        self.successors.get(node).map_or(0, IndexSet::len)
    }

    /// Out-degree: number of successors.
    #[must_use]
    pub fn out_degree(&self, node: &str) -> usize {
        self.successors.get(node).map_or(0, IndexSet::len)
    }

    /// In-degree: number of predecessors.
    #[must_use]
    pub fn in_degree(&self, node: &str) -> usize {
        self.predecessors.get(node).map_or(0, IndexSet::len)
    }

    /// Total degree: in_degree + out_degree.
    #[must_use]
    pub fn degree(&self, node: &str) -> usize {
        self.in_degree(node) + self.out_degree(node)
    }

    /// Outgoing edges from `node` as (source, target) pairs.
    #[must_use]
    pub fn out_edges<'a>(&'a self, node: &'a str) -> Vec<(&'a str, &'a str)> {
        self.successors.get(node).map_or_else(Vec::new, |succs| {
            succs.iter().map(|t| (node, t.as_str())).collect()
        })
    }

    /// Incoming edges to `node` as (source, target) pairs.
    #[must_use]
    pub fn in_edges<'a>(&'a self, node: &'a str) -> Vec<(&'a str, &'a str)> {
        self.predecessors.get(node).map_or_else(Vec::new, |preds| {
            preds.iter().map(|s| (s.as_str(), node)).collect()
        })
    }

    // -- Attribute queries -------------------------------------------------

    #[must_use]
    pub fn node_attrs(&self, node: &str) -> Option<&AttrMap> {
        self.nodes.get(node)
    }

    /// Attributes of directed edge source→target.
    #[must_use]
    pub fn edge_attrs(&self, source: &str, target: &str) -> Option<&AttrMap> {
        self.edges.get(&DirectedEdgeKeyRef::new(source, target))
    }

    #[must_use]
    pub fn evidence_ledger(&self) -> &EvidenceLedger {
        self.runtime_policy.decision_log()
    }

    #[must_use]
    pub fn runtime_policy(&self) -> &RuntimePolicy {
        &self.runtime_policy
    }

    pub fn set_runtime_policy(&mut self, runtime_policy: RuntimePolicy) {
        self.mode = runtime_policy.mode();
        self.runtime_policy = runtime_policy;
    }

    /// Type identity: always `true` for DiGraph.
    #[must_use]
    pub fn is_directed(&self) -> bool {
        true
    }

    /// Type identity: always `false` for DiGraph (not a multigraph).
    #[must_use]
    pub fn is_multigraph(&self) -> bool {
        false
    }

    // -----------------------------------------------------------------------
    // Mutations
    // -----------------------------------------------------------------------

    pub fn add_node(&mut self, node: impl Into<String>) -> bool {
        self.add_node_with_attrs(node, AttrMap::new())
    }

    pub fn add_node_with_attrs(&mut self, node: impl Into<String>, attrs: AttrMap) -> bool {
        let node = node.into();
        let existed = self.nodes.contains_key(&node);
        let mut changed = !existed;
        let attrs_count = {
            let bucket = self.nodes.entry(node.clone()).or_default();
            if !attrs.is_empty()
                && attrs
                    .iter()
                    .any(|(key, value)| bucket.get(key) != Some(value))
            {
                changed = true;
            }
            bucket.extend(attrs);
            bucket.len()
        };
        self.successors.entry(node.clone()).or_default();
        self.predecessors.entry(node.clone()).or_default();
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
        changed
    }

    pub fn apply_node_defaults(&mut self, defaults: &AttrMap) -> bool {
        if defaults.is_empty() {
            return false;
        }
        let mut inserted = 0usize;
        for attrs in self.nodes.values_mut() {
            for (key, value) in defaults {
                if !attrs.contains_key(key) {
                    attrs.insert(key.clone(), value.clone());
                    inserted += 1;
                }
            }
        }
        if inserted > 0 {
            self.revision = self.revision.saturating_add(1);
            self.record_decision(
                "apply_node_defaults",
                0.0,
                false,
                vec![EvidenceTerm {
                    signal: "defaults_applied".to_owned(),
                    observed_value: inserted.to_string(),
                    log_likelihood_ratio: 0.0,
                }],
            );
            return true;
        }
        false
    }

    pub fn add_edge(
        &mut self,
        source: impl Into<String>,
        target: impl Into<String>,
    ) -> Result<(), GraphError> {
        self.add_edge_with_attrs(source, target, AttrMap::new())
    }

    pub fn add_edge_with_attrs(
        &mut self,
        source: impl Into<String>,
        target: impl Into<String>,
        attrs: AttrMap,
    ) -> Result<(), GraphError> {
        let source = source.into();
        let target = target.into();

        let unknown_feature = attrs
            .keys()
            .any(|key| key.starts_with("__fnx_incompatible"));
        let self_loop = source == target;
        let incompatibility_probability = if unknown_feature {
            1.0
        } else if self_loop {
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

        if action == DecisionAction::FailClosed || action == DecisionAction::FullValidate {
            return Err(GraphError::FailClosed {
                operation: "add_edge",
                reason: "incompatible edge metadata".to_owned(),
            });
        }

        // Auto-create nodes.
        let mut source_autocreated = false;
        if !self.nodes.contains_key(&source) {
            let _ = self.add_node(source.clone());
            source_autocreated = true;
        }
        let mut target_autocreated = false;
        if self_loop {
            target_autocreated = source_autocreated;
        } else if !self.nodes.contains_key(&target) {
            let _ = self.add_node(target.clone());
            target_autocreated = true;
        }

        let edge_key = DirectedEdgeKey::new(&source, &target);
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

        // Directed adjacency: only source→target direction.
        self.successors
            .entry(source.clone())
            .or_default()
            .insert(target.clone());
        self.predecessors
            .entry(target.clone())
            .or_default()
            .insert(source.clone());

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
                    signal: "source_autocreated".to_owned(),
                    observed_value: source_autocreated.to_string(),
                    log_likelihood_ratio: -1.25,
                },
                EvidenceTerm {
                    signal: "target_autocreated".to_owned(),
                    observed_value: target_autocreated.to_string(),
                    log_likelihood_ratio: -1.25,
                },
            ],
        );

        Ok(())
    }

    /// Bulk-add a sequence of attribute-free directed edges. Bypasses
    /// the per-edge `runtime_policy.record_decision` call that
    /// [`add_edge_with_attrs`] makes. Instead, emit one summary record
    /// for the whole batch.
    ///
    /// Intended for fnx-internal callers that build a fresh graph
    /// from a known-good edge list where per-edge compatibility
    /// accounting would add constant-factor overhead without adding
    /// useful policy evidence. Nodes referenced by edges are
    /// auto-created if absent, matching `add_edge` semantics.
    #[must_use]
    pub fn extend_edges_unrecorded<I, S, T>(&mut self, edges: I) -> usize
    where
        I: IntoIterator<Item = (S, T)>,
        S: Into<String>,
        T: Into<String>,
    {
        let mut inserted = 0usize;
        for (source, target) in edges {
            let source = source.into();
            let target = target.into();
            if !self.nodes.contains_key(&source) {
                self.nodes.insert(source.clone(), AttrMap::new());
                self.successors.entry(source.clone()).or_default();
                self.predecessors.entry(source.clone()).or_default();
            }
            if source != target && !self.nodes.contains_key(&target) {
                self.nodes.insert(target.clone(), AttrMap::new());
                self.successors.entry(target.clone()).or_default();
                self.predecessors.entry(target.clone()).or_default();
            }
            let edge_key = DirectedEdgeKey::new(&source, &target);
            if self.edges.contains_key(&edge_key) {
                continue;
            }

            self.edges.insert(edge_key, AttrMap::new());
            self.successors
                .entry(source.clone())
                .or_default()
                .insert(target.clone());
            self.predecessors
                .entry(target)
                .or_default()
                .insert(source);
            inserted += 1;
        }

        if inserted > 0 {
            self.revision = self
                .revision
                .saturating_add(u64::try_from(inserted).unwrap_or(u64::MAX));
            self.record_decision(
                "extend_edges_unrecorded",
                0.0,
                false,
                vec![EvidenceTerm {
                    signal: "batch_edge_count".to_owned(),
                    observed_value: inserted.to_string(),
                    log_likelihood_ratio: -1.0,
                }],
            );
        }

        inserted
    }

    pub fn apply_edge_defaults(&mut self, defaults: &AttrMap) -> bool {
        if defaults.is_empty() {
            return false;
        }
        let mut inserted = 0usize;
        for attrs in self.edges.values_mut() {
            for (key, value) in defaults {
                if !attrs.contains_key(key) {
                    attrs.insert(key.clone(), value.clone());
                    inserted += 1;
                }
            }
        }
        if inserted > 0 {
            self.revision = self.revision.saturating_add(1);
            self.record_decision(
                "apply_edge_defaults",
                0.0,
                false,
                vec![EvidenceTerm {
                    signal: "defaults_applied".to_owned(),
                    observed_value: inserted.to_string(),
                    log_likelihood_ratio: 0.0,
                }],
            );
            return true;
        }
        false
    }

    /// Remove directed edge source→target. Returns `true` if it existed.
    pub fn remove_edge(&mut self, source: &str, target: &str) -> bool {
        let removed = self
            .edges
            .shift_remove(&DirectedEdgeKeyRef::new(source, target))
            .is_some();
        if removed {
            if let Some(succs) = self.successors.get_mut(source) {
                succs.shift_remove(target);
            }
            if let Some(preds) = self.predecessors.get_mut(target) {
                preds.shift_remove(source);
            }
            self.revision = self.revision.saturating_add(1);
        }
        removed
    }

    /// Remove node and all incident edges (both incoming and outgoing).
    pub fn remove_node(&mut self, node: &str) -> bool {
        if !self.nodes.contains_key(node) {
            return false;
        }

        // 1. Remove outgoing edges and clean up successors' predecessor lists.
        if let Some(succs) = self.successors.get(node) {
            let targets: Vec<String> = succs.iter().cloned().collect();
            for target in targets {
                if target != node
                    && let Some(preds) = self.predecessors.get_mut(&target)
                {
                    preds.shift_remove(node);
                }
                let _ = self
                    .edges
                    .shift_remove(&DirectedEdgeKey::new(node, &target));
            }
        }

        // 2. Remove incoming edges and clean up predecessors' successor lists.
        if let Some(preds) = self.predecessors.get(node) {
            let sources: Vec<String> = preds.iter().cloned().collect();
            for source in sources {
                if source != node
                    && let Some(succs) = self.successors.get_mut(&source)
                {
                    succs.shift_remove(node);
                }
                let _ = self
                    .edges
                    .shift_remove(&DirectedEdgeKey::new(&source, node));
            }
        }

        self.successors.shift_remove(node);
        self.predecessors.shift_remove(node);
        self.nodes.shift_remove(node);
        self.revision = self.revision.saturating_add(1);
        true
    }

    // -----------------------------------------------------------------------
    // Snapshot / ordered iteration
    // -----------------------------------------------------------------------

    /// Edges in deterministic order: iterate nodes in insertion order, then
    /// each node's successors in insertion order.
    #[must_use]
    pub fn edges_ordered(&self) -> Vec<EdgeSnapshot> {
        let mut ordered = Vec::with_capacity(self.edges.len());

        for node in self.nodes.keys() {
            if let Some(succs) = self.successors.get(node) {
                for target in succs {
                    let key = DirectedEdgeKey::new(node, target);
                    if let Some(attrs) = self.edges.get(&key) {
                        ordered.push(EdgeSnapshot {
                            left: node.clone(),
                            right: target.clone(),
                            attrs: attrs.clone(),
                        });
                    }
                }
            }
        }

        ordered
    }

    #[must_use]
    pub fn edges_ordered_borrowed(&self) -> Vec<(&str, &str, &AttrMap)> {
        let mut ordered = Vec::with_capacity(self.edges.len());

        for node in self.nodes.keys() {
            if let Some(succs) = self.successors.get(node) {
                for target in succs {
                    let key = DirectedEdgeKeyRef::new(node, target);
                    if let Some(attrs) = self.edges.get(&key) {
                        ordered.push((node.as_str(), target.as_str(), attrs));
                    }
                }
            }
        }

        ordered
    }

    #[must_use]
    pub fn snapshot(&self) -> DiGraphSnapshot {
        let node_attrs: std::collections::BTreeMap<String, AttrMap> = self
            .nodes
            .iter()
            .filter(|(_, attrs)| !attrs.is_empty())
            .map(|(name, attrs)| (name.clone(), attrs.clone()))
            .collect();
        DiGraphSnapshot {
            mode: self.mode,
            nodes: self.nodes.keys().cloned().collect(),
            node_attrs,
            edges: self.edges_ordered(),
        }
    }

    /// Convert to an undirected Graph by dropping directionality.
    /// Both (u→v) and (v→u) merge into a single undirected edge.
    /// When both exist, the latter's attributes overwrite the former's.
    #[must_use]
    pub fn to_undirected(&self) -> crate::Graph {
        let mut g = crate::Graph::with_runtime_policy(self.runtime_policy.clone());
        for (node, attrs) in &self.nodes {
            g.add_node_with_attrs(node.clone(), attrs.clone());
        }
        for (key, attrs) in &self.edges {
            let _ = g.add_edge_with_attrs(key.source.clone(), key.target.clone(), attrs.clone());
        }
        g
    }

    // -----------------------------------------------------------------------
    // Internal
    // -----------------------------------------------------------------------

    fn record_decision(
        &mut self,
        operation: &'static str,
        incompatibility_probability: f64,
        unknown_incompatible_feature: bool,
        evidence: Vec<EvidenceTerm>,
    ) -> DecisionAction {
        let action = self
            .runtime_policy
            .action_for(incompatibility_probability, unknown_incompatible_feature);
        self.runtime_policy.record(
            operation,
            action,
            incompatibility_probability,
            "argmin expected loss over {allow,full_validate,fail_closed}",
            evidence,
        );
        action
    }
}

#[derive(Debug, Clone)]
pub struct MultiDiGraph {
    mode: CompatibilityMode,
    revision: u64,
    nodes: IndexMap<String, AttrMap>,
    successors: IndexMap<String, IndexMap<String, IndexSet<usize>>>,
    predecessors: IndexMap<String, IndexMap<String, IndexSet<usize>>>,
    edges: IndexMap<DirectedEdgeKey, IndexMap<usize, AttrMap>>,
    runtime_policy: RuntimePolicy,
    edge_count: usize,
}

impl MultiDiGraph {
    #[must_use]
    pub fn new(mode: CompatibilityMode) -> Self {
        Self {
            mode,
            revision: 0,
            nodes: IndexMap::new(),
            successors: IndexMap::new(),
            predecessors: IndexMap::new(),
            edges: IndexMap::new(),
            runtime_policy: RuntimePolicy::new(mode),
            edge_count: 0,
        }
    }

    #[must_use]
    pub fn with_runtime_policy(runtime_policy: RuntimePolicy) -> Self {
        let mode = runtime_policy.mode();
        Self {
            mode,
            revision: 0,
            nodes: IndexMap::new(),
            successors: IndexMap::new(),
            predecessors: IndexMap::new(),
            edges: IndexMap::new(),
            runtime_policy,
            edge_count: 0,
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
        self.edge_count
    }

    /// Return an iterator over keys for edges from source to target.
    /// Edge keys as Vec.
    #[must_use]
    pub fn edge_keys(&self, source: &str, target: &str) -> Option<Vec<usize>> {
        self.successors
            .get(source)?
            .get(target)
            .map(|keys| keys.iter().copied().collect())
    }

    /// Edge keys as iterator.
    pub fn edge_keys_iter(
        &self,
        source: &str,
        target: &str,
    ) -> Option<impl Iterator<Item = &usize>> {
        self.successors
            .get(source)?
            .get(target)
            .map(|keys| keys.iter())
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
    pub fn has_edge(&self, source: &str, target: &str) -> bool {
        self.edges
            .get(&DirectedEdgeKeyRef::new(source, target))
            .is_some_and(|edge_bucket| !edge_bucket.is_empty())
    }

    #[must_use]
    pub fn nodes_ordered(&self) -> Vec<&str> {
        self.nodes.keys().map(String::as_str).collect()
    }

    #[must_use]
    pub fn successors(&self, node: &str) -> Option<Vec<&str>> {
        self.successors
            .get(node)
            .map(|neighbors| neighbors.keys().map(String::as_str).collect::<Vec<&str>>())
    }

    #[must_use]
    pub fn predecessors(&self, node: &str) -> Option<Vec<&str>> {
        self.predecessors
            .get(node)
            .map(|neighbors| neighbors.keys().map(String::as_str).collect::<Vec<&str>>())
    }

    #[must_use]
    pub fn neighbors(&self, node: &str) -> Option<Vec<&str>> {
        self.successors(node)
    }

    #[must_use]
    pub fn node_attrs(&self, node: &str) -> Option<&AttrMap> {
        self.nodes.get(node)
    }

    #[must_use]
    pub fn edge_attrs(&self, source: &str, target: &str, key: usize) -> Option<&AttrMap> {
        self.edges
            .get(&DirectedEdgeKeyRef::new(source, target))
            .and_then(|edge_bucket| edge_bucket.get(&key))
    }

    #[must_use]
    pub fn evidence_ledger(&self) -> &EvidenceLedger {
        self.runtime_policy.decision_log()
    }

    #[must_use]
    pub fn runtime_policy(&self) -> &RuntimePolicy {
        &self.runtime_policy
    }

    pub fn set_runtime_policy(&mut self, runtime_policy: RuntimePolicy) {
        self.mode = runtime_policy.mode();
        self.runtime_policy = runtime_policy;
    }

    #[must_use]
    pub fn is_directed(&self) -> bool {
        true
    }

    #[must_use]
    pub fn is_multigraph(&self) -> bool {
        true
    }

    /// Return the out-degree of a node (number of outgoing parallel edges).
    #[must_use]
    pub fn out_degree(&self, node: &str) -> usize {
        self.successors
            .get(node)
            .map_or(0, |succs| succs.values().map(IndexSet::len).sum())
    }

    /// Return the in-degree of a node (number of incoming parallel edges).
    #[must_use]
    pub fn in_degree(&self, node: &str) -> usize {
        self.predecessors
            .get(node)
            .map_or(0, |preds| preds.values().map(IndexSet::len).sum())
    }

    /// Return the degree of a node (in-degree + out-degree).
    #[must_use]
    pub fn degree(&self, node: &str) -> usize {
        self.in_degree(node) + self.out_degree(node)
    }

    pub fn add_node(&mut self, node: impl Into<String>) -> bool {
        self.add_node_with_attrs(node, AttrMap::new())
    }

    pub fn add_node_with_attrs(&mut self, node: impl Into<String>, attrs: AttrMap) -> bool {
        let node = node.into();
        let existed = self.nodes.contains_key(&node);
        let mut changed = !existed;
        let attrs_count = {
            let bucket = self.nodes.entry(node.clone()).or_default();
            if !attrs.is_empty()
                && attrs
                    .iter()
                    .any(|(key, value)| bucket.get(key) != Some(value))
            {
                changed = true;
            }
            bucket.extend(attrs);
            bucket.len()
        };
        self.successors.entry(node.clone()).or_default();
        self.predecessors.entry(node.clone()).or_default();
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
        changed
    }

    pub fn add_edge(
        &mut self,
        source: impl Into<String>,
        target: impl Into<String>,
    ) -> Result<usize, GraphError> {
        self.add_edge_impl(source, target, None, AttrMap::new())
    }

    pub fn add_edge_with_attrs(
        &mut self,
        source: impl Into<String>,
        target: impl Into<String>,
        attrs: AttrMap,
    ) -> Result<usize, GraphError> {
        self.add_edge_impl(source, target, None, attrs)
    }

    pub fn add_edge_with_key_and_attrs(
        &mut self,
        source: impl Into<String>,
        target: impl Into<String>,
        key: usize,
        attrs: AttrMap,
    ) -> Result<usize, GraphError> {
        self.add_edge_impl(source, target, Some(key), attrs)
    }

    fn add_edge_impl(
        &mut self,
        source: impl Into<String>,
        target: impl Into<String>,
        explicit_key: Option<usize>,
        attrs: AttrMap,
    ) -> Result<usize, GraphError> {
        let source = source.into();
        let target = target.into();

        let unknown_feature = attrs
            .keys()
            .any(|key| key.starts_with("__fnx_incompatible"));
        let self_loop = source == target;
        let incompatibility_probability = if unknown_feature {
            1.0
        } else if self_loop {
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

        if action == DecisionAction::FailClosed || action == DecisionAction::FullValidate {
            return Err(GraphError::FailClosed {
                operation: "add_edge",
                reason: "incompatible edge metadata".to_owned(),
            });
        }

        let mut source_autocreated = false;
        if !self.nodes.contains_key(&source) {
            let _ = self.add_node(source.clone());
            source_autocreated = true;
        }
        let mut target_autocreated = false;
        if self_loop {
            target_autocreated = source_autocreated;
        } else if !self.nodes.contains_key(&target) {
            let _ = self.add_node(target.clone());
            target_autocreated = true;
        }

        let edge_key = DirectedEdgeKey::new(&source, &target);
        let key = explicit_key.unwrap_or_else(|| {
            let edge_bucket = self.edges.get(&edge_key);
            let mut k = edge_bucket.map_or(0, |b| b.len());
            if let Some(b) = edge_bucket {
                while b.contains_key(&k) {
                    k += 1;
                }
            }
            k
        });
        let mut changed;
        let edge_attr_count = {
            let edge_bucket = self.edges.entry(edge_key.clone()).or_default();
            let is_new = !edge_bucket.contains_key(&key);
            if is_new {
                self.edge_count += 1;
            }
            changed = is_new;
            let edge_attrs = edge_bucket.entry(key).or_default();
            if !attrs.is_empty()
                && attrs
                    .iter()
                    .any(|(attr_key, value)| edge_attrs.get(attr_key) != Some(value))
            {
                changed = true;
            }
            edge_attrs.extend(attrs);
            edge_bucket.len()
        };

        self.successors
            .entry(source.clone())
            .or_default()
            .entry(target.clone())
            .or_default()
            .insert(key);
        self.predecessors
            .entry(target.clone())
            .or_default()
            .entry(source.clone())
            .or_default()
            .insert(key);
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
                    signal: "source_autocreated".to_owned(),
                    observed_value: source_autocreated.to_string(),
                    log_likelihood_ratio: -1.25,
                },
                EvidenceTerm {
                    signal: "target_autocreated".to_owned(),
                    observed_value: target_autocreated.to_string(),
                    log_likelihood_ratio: -1.25,
                },
            ],
        );

        Ok(key)
    }

    pub fn remove_edge(&mut self, source: &str, target: &str, key: Option<usize>) -> bool {
        let edge_key = DirectedEdgeKeyRef::new(source, target);
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

        self.edge_count -= 1;

        let should_drop_bucket = self.edges.get(&edge_key).is_some_and(IndexMap::is_empty);
        if should_drop_bucket {
            self.edges.shift_remove(&edge_key);
        }

        self.remove_successor_key(source, target, removal_key);
        self.remove_predecessor_key(target, source, removal_key);
        self.revision = self.revision.saturating_add(1);
        true
    }

    pub fn remove_node(&mut self, node: &str) -> bool {
        if !self.nodes.contains_key(node) {
            return false;
        }

        // 1. Remove outgoing edges and clean up successors' predecessor lists.
        if let Some(succs) = self.successors.get(node) {
            let targets: Vec<String> = succs.keys().cloned().collect();
            for target in targets {
                if target != node
                    && let Some(preds) = self.predecessors.get_mut(&target)
                {
                    preds.shift_remove(node);
                }
                let k = DirectedEdgeKey::new(node, &target);
                if let Some(removed_bucket) = self.edges.shift_remove(&k) {
                    self.edge_count -= removed_bucket.len();
                }
            }
        }

        // 2. Remove incoming edges and clean up predecessors' successor lists.
        if let Some(preds) = self.predecessors.get(node) {
            let sources: Vec<String> = preds.keys().cloned().collect();
            for source in sources {
                if source != node
                    && let Some(succs) = self.successors.get_mut(&source)
                {
                    succs.shift_remove(node);
                }
                let k = DirectedEdgeKey::new(&source, node);
                if let Some(removed_bucket) = self.edges.shift_remove(&k) {
                    self.edge_count -= removed_bucket.len();
                }
            }
        }

        self.successors.shift_remove(node);
        self.predecessors.shift_remove(node);
        self.nodes.shift_remove(node);
        self.revision = self.revision.saturating_add(1);
        true
    }

    #[must_use]
    pub fn edges_ordered(&self) -> Vec<MultiDiEdgeSnapshot> {
        let mut ordered = Vec::with_capacity(self.edge_count());

        for node in self.nodes.keys() {
            if let Some(neighbors) = self.successors.get(node) {
                for target in neighbors.keys() {
                    let pair = DirectedEdgeKey::new(node, target);
                    if let Some(edge_bucket) = self.edges.get(&pair) {
                        for (key, attrs) in edge_bucket {
                            ordered.push(MultiDiEdgeSnapshot {
                                source: node.clone(),
                                target: target.clone(),
                                key: *key,
                                attrs: attrs.clone(),
                            });
                        }
                    }
                }
            }
        }

        ordered
    }

    #[must_use]
    pub fn edges_ordered_borrowed(&self) -> Vec<(&str, &str, usize, &AttrMap)> {
        let mut ordered = Vec::with_capacity(self.edge_count());

        for node in self.nodes.keys() {
            if let Some(neighbors) = self.successors.get(node) {
                for target in neighbors.keys() {
                    let pair = DirectedEdgeKeyRef::new(node, target);
                    if let Some(edge_bucket) = self.edges.get(&pair) {
                        for (key, attrs) in edge_bucket {
                            ordered.push((node.as_str(), target.as_str(), *key, attrs));
                        }
                    }
                }
            }
        }

        ordered
    }

    #[must_use]
    pub fn snapshot(&self) -> MultiDiGraphSnapshot {
        let node_attrs: std::collections::BTreeMap<String, AttrMap> = self
            .nodes
            .iter()
            .filter(|(_, attrs)| !attrs.is_empty())
            .map(|(name, attrs)| (name.clone(), attrs.clone()))
            .collect();
        MultiDiGraphSnapshot {
            mode: self.mode,
            nodes: self.nodes.keys().cloned().collect(),
            node_attrs,
            edges: self.edges_ordered(),
        }
    }

    fn remove_successor_key(&mut self, source: &str, target: &str, key: usize) {
        let mut drop_neighbor = false;
        if let Some(neighbors) = self.successors.get_mut(source)
            && let Some(keys) = neighbors.get_mut(target)
        {
            keys.shift_remove(&key);
            drop_neighbor = keys.is_empty();
        }
        if drop_neighbor && let Some(neighbors) = self.successors.get_mut(source) {
            neighbors.shift_remove(target);
        }
    }

    fn remove_predecessor_key(&mut self, target: &str, source: &str, key: usize) {
        let mut drop_neighbor = false;
        if let Some(neighbors) = self.predecessors.get_mut(target)
            && let Some(keys) = neighbors.get_mut(source)
        {
            keys.shift_remove(&key);
            drop_neighbor = keys.is_empty();
        }
        if drop_neighbor && let Some(neighbors) = self.predecessors.get_mut(target) {
            neighbors.shift_remove(source);
        }
    }

    fn record_decision(
        &mut self,
        operation: &'static str,
        incompatibility_probability: f64,
        unknown_incompatible_feature: bool,
        evidence: Vec<EvidenceTerm>,
    ) -> DecisionAction {
        let action = self
            .runtime_policy
            .action_for(incompatibility_probability, unknown_incompatible_feature);
        self.runtime_policy.record(
            operation,
            action,
            incompatibility_probability,
            "argmin expected loss over {allow,full_validate,fail_closed}",
            evidence,
        );
        action
    }
}

// ===========================================================================
// Tests
// ===========================================================================

#[cfg(test)]
mod tests {
    use super::*;
    use fnx_runtime::{
        CgseValue, CompatibilityMode, DecisionAction, DecisionRecord, RuntimePolicy,
    };
    use proptest::prelude::*;

    fn node_name(id: u8) -> String {
        format!("n{}", id % 8)
    }

    fn single_attr(key: &str, value: &str) -> AttrMap {
        let mut attrs = AttrMap::new();
        attrs.insert(key.to_owned(), CgseValue::from(value));
        attrs
    }

    fn assert_runtime_policy_preserved(source: &RuntimePolicy, result: &RuntimePolicy) {
        assert_eq!(result.mode(), source.mode());
        assert_eq!(result.allowlist(), source.allowlist());
        assert_eq!(result.loss_matrix(), source.loss_matrix());
        assert!(result.posterior().observation_count >= source.posterior().observation_count);
        assert!(
            result
                .decision_log()
                .records()
                .starts_with(source.decision_log().records())
        );
    }

    // -- Invariant checker --------------------------------------------------

    fn assert_digraph_core_invariants(g: &DiGraph) {
        // Every edge in the edge map must be reflected in successors/predecessors.
        for (key, _attrs) in &g.edges {
            assert!(
                g.has_node(&key.source),
                "edge source {} should be a node",
                key.source
            );
            assert!(
                g.has_node(&key.target),
                "edge target {} should be a node",
                key.target
            );
            let succs = g
                .successors(&key.source)
                .expect("source should have successors bucket");
            assert!(
                succs.contains(&key.target.as_str()),
                "{} should be in successors of {}",
                key.target,
                key.source
            );
            let preds = g
                .predecessors(&key.target)
                .expect("target should have predecessors bucket");
            assert!(
                preds.contains(&key.source.as_str()),
                "{} should be in predecessors of {}",
                key.source,
                key.target
            );
        }

        // Every successor entry should have a corresponding edge.
        let mut edge_count_from_adj = 0usize;
        for node in g.nodes_ordered() {
            let succs = g
                .successors(node)
                .expect("node should have successors bucket");
            for s in &succs {
                assert!(
                    g.has_edge(node, s),
                    "successor {} of {} should have directed edge",
                    s,
                    node
                );
                edge_count_from_adj += 1;
            }
            // Every predecessor entry should have a corresponding edge.
            let preds = g
                .predecessors(node)
                .expect("node should have predecessors bucket");
            for p in &preds {
                assert!(
                    g.has_edge(p, node),
                    "predecessor {} of {} should have directed edge",
                    p,
                    node
                );
            }
        }
        assert_eq!(g.edge_count(), edge_count_from_adj);
    }

    #[test]
    fn add_node_with_attrs_reports_change_on_existing_node() {
        let mut graph = DiGraph::strict();
        assert!(graph.add_node_with_attrs("a", single_attr("color", "red")));
        let r1 = graph.revision();
        assert!(graph.add_node_with_attrs("a", single_attr("color", "blue")));
        let r2 = graph.revision();
        assert!(r2 > r1);
        let expected = CgseValue::from("blue");
        assert_eq!(graph.node_attrs("a").unwrap().get("color"), Some(&expected));
    }

    #[test]
    fn multidigraph_add_node_with_attrs_reports_change_on_existing_node() {
        let mut graph = MultiDiGraph::strict();
        assert!(graph.add_node_with_attrs("a", single_attr("color", "red")));
        let r1 = graph.revision();
        assert!(graph.add_node_with_attrs("a", single_attr("color", "blue")));
        let r2 = graph.revision();
        assert!(r2 > r1);
        let expected = CgseValue::from("blue");
        assert_eq!(graph.node_attrs("a").unwrap().get("color"), Some(&expected));
    }

    fn assert_multidigraph_core_invariants(g: &MultiDiGraph) {
        let mut edge_instances = std::collections::BTreeSet::new();
        for node in g.nodes_ordered() {
            let successors = g
                .successors(node)
                .expect("multidigraph nodes should always have successor buckets");
            for target in successors {
                assert!(g.has_node(target));
                assert!(g.has_edge(node, target));
                let preds = g
                    .predecessors(target)
                    .expect("target should always have predecessor buckets");
                assert!(preds.contains(&node));
                let keys = g
                    .edge_keys(node, target)
                    .expect("parallel directed edge bucket should exist");
                for key in keys {
                    edge_instances.insert((node.to_owned(), target.to_owned(), key));
                }
            }
        }
        assert_eq!(g.edge_count(), edge_instances.len());
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

    // -- Basic operations ---------------------------------------------------

    #[test]
    fn add_directed_edge_autocreates_nodes() {
        let mut g = DiGraph::strict();
        g.add_edge("a", "b").unwrap();

        assert_eq!(g.node_count(), 2);
        assert_eq!(g.edge_count(), 1);
        assert!(g.has_edge("a", "b"));
        assert!(!g.has_edge("b", "a")); // directed: reverse does NOT exist
        assert_digraph_core_invariants(&g);
    }

    #[test]
    fn directed_edge_asymmetry() {
        let mut g = DiGraph::strict();
        g.add_edge("a", "b").unwrap();
        g.add_edge("b", "a").unwrap();

        assert_eq!(g.edge_count(), 2);
        assert!(g.has_edge("a", "b"));
        assert!(g.has_edge("b", "a"));
        assert_digraph_core_invariants(&g);
    }

    #[test]
    fn successors_and_predecessors() {
        let mut g = DiGraph::strict();
        g.add_edge("a", "b").unwrap();
        g.add_edge("a", "c").unwrap();
        g.add_edge("d", "a").unwrap();

        assert_eq!(g.successors("a"), Some(vec!["b", "c"]));
        assert_eq!(g.predecessors("a"), Some(vec!["d"]));
        assert_eq!(g.out_degree("a"), 2);
        assert_eq!(g.in_degree("a"), 1);
        assert_eq!(g.degree("a"), 3);
        assert_digraph_core_invariants(&g);
    }

    #[test]
    fn neighbors_returns_successors() {
        let mut g = DiGraph::strict();
        g.add_edge("a", "b").unwrap();
        g.add_edge("c", "a").unwrap();

        // neighbors() = successors() per NetworkX convention
        assert_eq!(g.neighbors("a"), Some(vec!["b"]));
        assert_digraph_core_invariants(&g);
    }

    #[test]
    fn in_edges_and_out_edges() {
        let mut g = DiGraph::strict();
        g.add_edge("x", "y").unwrap();
        g.add_edge("z", "y").unwrap();
        g.add_edge("y", "w").unwrap();

        assert_eq!(g.out_edges("y"), vec![("y", "w")]);
        assert_eq!(g.in_edges("y"), vec![("x", "y"), ("z", "y")]);
        assert_digraph_core_invariants(&g);
    }

    #[test]
    fn remove_directed_edge() {
        let mut g = DiGraph::strict();
        g.add_edge("a", "b").unwrap();
        g.add_edge("b", "a").unwrap();

        assert!(g.remove_edge("a", "b"));
        assert!(!g.has_edge("a", "b"));
        assert!(g.has_edge("b", "a")); // reverse still exists
        assert_eq!(g.edge_count(), 1);
        assert_digraph_core_invariants(&g);
    }

    #[test]
    fn remove_node_removes_all_incident_directed_edges() {
        let mut g = DiGraph::strict();
        g.add_edge("a", "b").unwrap();
        g.add_edge("b", "c").unwrap();
        g.add_edge("c", "a").unwrap();
        g.add_edge("d", "b").unwrap();

        assert!(g.remove_node("b"));
        assert_eq!(g.node_count(), 3);
        assert!(!g.has_edge("a", "b"));
        assert!(!g.has_edge("b", "c"));
        assert!(!g.has_edge("d", "b"));
        assert!(g.has_edge("c", "a")); // not incident to b
        assert_digraph_core_invariants(&g);
    }

    #[test]
    fn self_loop_directed() {
        let mut g = DiGraph::strict();
        g.add_edge("a", "a").unwrap();

        assert_eq!(g.edge_count(), 1);
        assert!(g.has_edge("a", "a"));
        assert_eq!(g.out_degree("a"), 1);
        assert_eq!(g.in_degree("a"), 1);
        assert_digraph_core_invariants(&g);
    }

    #[test]
    fn edge_attrs_directed() {
        let mut g = DiGraph::strict();
        let mut attrs = AttrMap::new();
        attrs.insert("weight".to_owned(), "5".into());
        g.add_edge_with_attrs("a", "b", attrs).unwrap();

        assert_eq!(
            g.edge_attrs("a", "b").unwrap().get("weight"),
            Some(&CgseValue::String("5".to_owned()))
        );
        assert!(g.edge_attrs("b", "a").is_none()); // reverse has no attrs
    }

    #[test]
    fn repeated_edge_merges_attrs() {
        let mut g = DiGraph::strict();
        let mut first = AttrMap::new();
        first.insert("weight".to_owned(), "1".into());
        g.add_edge_with_attrs("a", "b", first).unwrap();

        let mut second = AttrMap::new();
        second.insert("color".to_owned(), "red".into());
        g.add_edge_with_attrs("a", "b", second).unwrap();

        assert_eq!(g.edge_count(), 1);
        let attrs = g.edge_attrs("a", "b").unwrap();
        assert_eq!(
            attrs.get("weight"),
            Some(&CgseValue::String("1".to_owned()))
        );
        assert_eq!(
            attrs.get("color"),
            Some(&CgseValue::String("red".to_owned()))
        );
    }

    #[test]
    fn edges_ordered_preserves_direction() {
        let mut g = DiGraph::strict();
        g.add_edge("b", "a").unwrap();
        g.add_edge("a", "c").unwrap();

        let pairs: Vec<(String, String)> = g
            .edges_ordered()
            .into_iter()
            .map(|e| (e.left, e.right))
            .collect();
        // b was added first as source, so b→a first, then a→c
        assert_eq!(
            pairs,
            vec![
                ("b".to_owned(), "a".to_owned()),
                ("a".to_owned(), "c".to_owned()),
            ]
        );
    }

    #[test]
    fn type_identity() {
        let g = DiGraph::strict();
        assert!(g.is_directed());
        assert!(!g.is_multigraph());
    }

    #[test]
    fn to_undirected_merges_edges() {
        let mut g = DiGraph::strict();
        g.add_edge("a", "b").unwrap();
        g.add_edge("b", "a").unwrap();
        g.add_edge("b", "c").unwrap();

        let ug = g.to_undirected();
        assert_eq!(ug.node_count(), 3);
        assert_eq!(ug.edge_count(), 2); // (a,b) merged, plus (b,c)
        assert!(ug.has_edge("a", "b"));
        assert!(ug.has_edge("b", "a")); // undirected: same edge
        assert!(ug.has_edge("b", "c"));
    }

    #[test]
    fn to_undirected_preserves_runtime_policy() {
        let mut g = DiGraph::hardened();
        g.add_edge("a", "b").unwrap();
        g.add_edge("b", "a").unwrap();
        let expected_policy = g.runtime_policy().clone();

        let ug = g.to_undirected();

        assert_runtime_policy_preserved(&expected_policy, ug.runtime_policy());
    }

    #[test]
    fn snapshot_roundtrip() {
        let mut g = DiGraph::strict();
        let mut attrs = AttrMap::new();
        attrs.insert("weight".to_owned(), "3".into());
        g.add_edge_with_attrs("a", "b", attrs).unwrap();
        g.add_edge("b", "c").unwrap();
        g.add_edge("c", "a").unwrap();

        let snap = g.snapshot();
        let mut replayed = DiGraph::new(snap.mode);
        for node in &snap.nodes {
            let _ = replayed.add_node(node.clone());
        }
        for edge in &snap.edges {
            replayed
                .add_edge_with_attrs(edge.left.clone(), edge.right.clone(), edge.attrs.clone())
                .unwrap();
        }

        assert_eq!(replayed.snapshot(), snap);
        assert_digraph_core_invariants(&replayed);
    }

    #[test]
    fn multidigraph_tracks_parallel_edges_with_distinct_keys() {
        let mut graph = MultiDiGraph::strict();
        let first = graph.add_edge("a", "b").expect("edge add should succeed");
        let second = graph.add_edge("a", "b").expect("edge add should succeed");

        assert_ne!(first, second);
        assert_eq!(graph.edge_count(), 2);
        assert_eq!(graph.edge_keys("a", "b"), Some(vec![0, 1]));
        assert_multidigraph_core_invariants(&graph);
    }

    #[test]
    fn multidigraph_remove_node_clears_incoming_and_outgoing_parallel_edges() {
        let mut graph = MultiDiGraph::strict();
        let _ = graph.add_edge("a", "b").expect("edge add should succeed");
        let _ = graph.add_edge("a", "b").expect("edge add should succeed");
        let _ = graph.add_edge("b", "a").expect("edge add should succeed");
        let _ = graph.add_edge("b", "c").expect("edge add should succeed");

        assert!(graph.remove_node("b"));
        assert_eq!(graph.edge_count(), 0);
        assert!(!graph.has_node("b"));
        assert_eq!(graph.successors("a"), Some(vec![]));
        assert_eq!(graph.predecessors("a"), Some(vec![]));
        assert_multidigraph_core_invariants(&graph);
    }

    #[test]
    fn multidigraph_roundtrips_sparse_snapshot_keys() {
        let mut graph = MultiDiGraph::strict();
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

        let mut replayed = MultiDiGraph::new(snapshot.mode);
        for node in &snapshot.nodes {
            let _ = replayed.add_node(node.clone());
        }
        for edge in &snapshot.edges {
            replayed
                .add_edge_with_key_and_attrs(
                    edge.source.clone(),
                    edge.target.clone(),
                    edge.key,
                    edge.attrs.clone(),
                )
                .expect("snapshot replay should preserve explicit keys");
        }

        assert_eq!(replayed.snapshot(), snapshot);
        assert_multidigraph_core_invariants(&replayed);
    }

    #[test]
    fn runtime_policy_tracks_hardened_multidigraph_recovery() {
        let mut g = MultiDiGraph::hardened();
        g.add_edge("a", "b")
            .expect("hardened multidigraph edge add should succeed");

        assert_eq!(g.runtime_policy().mode(), CompatibilityMode::Hardened);
        assert!(!g.runtime_policy().decision_log().records().is_empty());
        assert!(g.runtime_policy().posterior().observation_count >= 1);
    }

    #[test]
    fn strict_mode_fails_closed_for_incompatible_attrs() {
        let mut g = DiGraph::strict();
        let mut attrs = AttrMap::new();
        attrs.insert("__fnx_incompatible_decoder".to_owned(), "v2".into());
        let err = g
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
    fn revision_increments_on_mutations() {
        let mut g = DiGraph::strict();
        let r0 = g.revision();
        let _ = g.add_node("a");
        let r1 = g.revision();
        assert!(r1 > r0);

        g.add_edge("a", "b").unwrap();
        let r2 = g.revision();
        assert!(r2 > r1);

        let _ = g.remove_edge("a", "b");
        let r3 = g.revision();
        assert!(r3 > r2);
    }

    #[test]
    fn hardened_self_loop_records_allow() {
        let mut g = DiGraph::hardened();
        g.add_edge("loop", "loop").unwrap();

        let record = g
            .evidence_ledger()
            .records()
            .iter()
            .rev()
            .find(|r| r.operation == "add_edge")
            .expect("add_edge should emit ledger row");
        assert_decision_record_schema(record, CompatibilityMode::Hardened);
        assert_eq!(record.action, DecisionAction::Allow);
    }

    #[test]
    fn runtime_policy_tracks_hardened_digraph_recovery() {
        let mut g = DiGraph::hardened();
        g.add_edge("a", "b")
            .expect("hardened digraph edge add should succeed");

        assert_eq!(g.runtime_policy().mode(), CompatibilityMode::Hardened);
        assert!(!g.runtime_policy().decision_log().records().is_empty());
        assert!(g.runtime_policy().posterior().observation_count >= 1);
    }

    // -- Proptest -----------------------------------------------------------

    proptest! {
        #[test]
        fn prop_digraph_invariants_under_mixed_mutations(
            ops in prop::collection::vec((0_u8..8, 0_u8..8, any::<bool>()), 1..80),
        ) {
            let mut g = DiGraph::strict();
            let mut last_rev = g.revision();

            for (src_id, tgt_id, is_add) in ops {
                let src = node_name(src_id);
                let tgt = node_name(tgt_id);
                if is_add {
                    prop_assert!(g.add_edge(src, tgt).is_ok());
                } else {
                    let _ = g.remove_edge(&src, &tgt);
                }
                let rev = g.revision();
                prop_assert!(rev >= last_rev);
                last_rev = rev;
                assert_digraph_core_invariants(&g);
            }
        }

        #[test]
        fn prop_digraph_snapshot_deterministic(
            ops in prop::collection::vec((0_u8..8, 0_u8..8, 0_u8..3), 0..64),
        ) {
            let mut g1 = DiGraph::hardened();
            let mut g2 = DiGraph::hardened();

            for (src_id, tgt_id, attrs_variant) in ops {
                let src = node_name(src_id);
                let tgt = node_name(tgt_id);
                let mut attrs = AttrMap::new();
                if attrs_variant == 1 {
                    attrs.insert("weight".to_owned(), (src_id % 5).to_string().into());
                } else if attrs_variant == 2 {
                    attrs.insert("tag".to_owned(), format!("k{}", tgt_id % 4).into());
                }
                prop_assert!(g1.add_edge_with_attrs(src.clone(), tgt.clone(), attrs.clone()).is_ok());
                prop_assert!(g2.add_edge_with_attrs(src, tgt, attrs).is_ok());
            }

            prop_assert_eq!(g1.snapshot(), g2.snapshot());
        }

        #[test]
        fn prop_remove_node_clears_all_directed_edges(
            ops in prop::collection::vec((0_u8..8, 0_u8..8), 1..64),
            target_id in 0_u8..8,
        ) {
            let mut g = DiGraph::strict();
            for (src_id, tgt_id) in ops {
                prop_assert!(g.add_edge(node_name(src_id), node_name(tgt_id)).is_ok());
            }

            let target = node_name(target_id);
            let removed = g.remove_node(&target);
            if removed {
                prop_assert!(!g.has_node(&target));
                for node in g.nodes_ordered() {
                    prop_assert!(!g.has_edge(node, &target));
                    prop_assert!(!g.has_edge(&target, node));
                }
            }
            assert_digraph_core_invariants(&g);
        }

        #[test]
        fn prop_directed_edge_count_equals_successor_sum(
            ops in prop::collection::vec((0_u8..8, 0_u8..8), 1..64),
        ) {
            let mut g = DiGraph::strict();
            for (src_id, tgt_id) in ops {
                prop_assert!(g.add_edge(node_name(src_id), node_name(tgt_id)).is_ok());
            }

            let total_out: usize = g.nodes_ordered().iter().map(|n| g.out_degree(n)).sum();
            let total_in: usize = g.nodes_ordered().iter().map(|n| g.in_degree(n)).sum();
            prop_assert_eq!(g.edge_count(), total_out);
            prop_assert_eq!(g.edge_count(), total_in);
        }
    }
}
