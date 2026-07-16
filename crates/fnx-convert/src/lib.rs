#![forbid(unsafe_code)]

use fnx_classes::digraph::{DiGraph, DiGraphSnapshot, MultiDiGraph, MultiDiGraphSnapshot};
use fnx_classes::{AttrMap, Graph, GraphError, GraphSnapshot, MultiGraph, MultiGraphSnapshot};
use fnx_dispatch::{BackendRegistry, BackendSpec, DispatchError, DispatchRequest};
use fnx_runtime::{CompatibilityMode, DecisionAction, EvidenceLedger, EvidenceTerm, RuntimePolicy};
use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, BTreeSet, HashMap};
use std::fmt;

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct EdgeRecord {
    pub left: String,
    pub right: String,
    #[serde(default)]
    pub key: Option<usize>,
    #[serde(default)]
    pub attrs: AttrMap,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct EdgeListPayload {
    /// br-payloaddefault: ``#[serde(default)]`` on both fields so an
    /// empty payload ``{}`` deserializes as a 0-node 0-edge graph
    /// (instead of failing with "missing field"). Either field alone
    /// is also a valid payload — e.g. ``{"nodes": ["a"]}`` for an
    /// isolated-node graph.
    #[serde(default)]
    pub nodes: Vec<String>,
    #[serde(default)]
    pub edges: Vec<EdgeRecord>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct AdjacencyEntry {
    pub to: String,
    #[serde(default)]
    pub key: Option<usize>,
    #[serde(default)]
    pub attrs: AttrMap,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct AdjacencyPayload {
    /// See ``EdgeListPayload`` — empty ``{}`` deserializes to an
    /// empty graph instead of failing with "missing field".
    #[serde(default)]
    pub adjacency: BTreeMap<String, Vec<AdjacencyEntry>>,
}

#[derive(Debug, Clone)]
pub struct ConvertReport {
    pub graph: Graph,
    pub warnings: Vec<String>,
    pub ledger: EvidenceLedger,
}

#[derive(Debug, Clone)]
pub struct DiConvertReport {
    pub graph: DiGraph,
    pub warnings: Vec<String>,
    pub ledger: EvidenceLedger,
}

#[derive(Debug, Clone)]
pub struct MultiConvertReport {
    pub graph: MultiGraph,
    pub warnings: Vec<String>,
    pub ledger: EvidenceLedger,
}

#[derive(Debug, Clone)]
pub struct MultiDiConvertReport {
    pub graph: MultiDiGraph,
    pub warnings: Vec<String>,
    pub ledger: EvidenceLedger,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ConvertError {
    Dispatch(DispatchError),
    Graph(GraphError),
    FailClosed {
        operation: &'static str,
        reason: String,
    },
}

impl fmt::Display for ConvertError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Dispatch(err) => write!(f, "{err}"),
            Self::Graph(err) => write!(f, "{err}"),
            Self::FailClosed { operation, reason } => {
                write!(f, "conversion `{operation}` failed closed: {reason}")
            }
        }
    }
}

impl std::error::Error for ConvertError {}

impl From<DispatchError> for ConvertError {
    fn from(value: DispatchError) -> Self {
        Self::Dispatch(value)
    }
}

impl From<GraphError> for ConvertError {
    fn from(value: GraphError) -> Self {
        Self::Graph(value)
    }
}

#[derive(Debug, Clone)]
pub struct GraphConverter {
    mode: CompatibilityMode,
    dispatch: BackendRegistry,
    runtime_policy: RuntimePolicy,
}

impl GraphConverter {
    #[must_use]
    pub fn new(mode: CompatibilityMode) -> Self {
        let mut dispatch = BackendRegistry::new(mode);
        dispatch.register_backend(BackendSpec {
            name: "native_convert".to_owned(),
            priority: 100,
            supported_features: ["convert_edge_list", "convert_adjacency"]
                .into_iter()
                .map(str::to_owned)
                .collect(),
            allow_in_strict: true,
            allow_in_hardened: true,
        });

        Self {
            mode,
            dispatch,
            runtime_policy: RuntimePolicy::new(mode),
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
    pub fn evidence_ledger(&self) -> &EvidenceLedger {
        self.runtime_policy.decision_log()
    }

    #[must_use]
    pub fn runtime_policy(&self) -> &RuntimePolicy {
        &self.runtime_policy
    }

    pub fn from_edge_list(
        &mut self,
        payload: &EdgeListPayload,
    ) -> Result<ConvertReport, ConvertError> {
        let feature = "convert_edge_list";
        let resolve = self.dispatch.resolve(&DispatchRequest {
            operation: "convert_edge_list".to_owned(),
            requested_backend: None,
            required_features: set([feature]),
            risk_probability: 0.05,
            unknown_incompatible_feature: false,
        });
        if let Err(err) = &resolve {
            self.record_dispatch_failure("convert_edge_list", err);
        }
        resolve?;

        let mut graph = Graph::new(self.mode);
        let mut warnings = Vec::new();

        if !Self::try_populate_plain_graph_from_edge_list(&mut graph, payload) {
            self.populate_from_edge_list(&mut graph, &mut warnings, payload)?;
        }

        self.record(
            "convert_edge_list",
            DecisionAction::Allow,
            "edge-list conversion completed",
            0.02,
        );

        graph.adopt_runtime_policy(self.runtime_policy.clone());

        Ok(ConvertReport {
            graph,
            warnings,
            ledger: self.runtime_policy.decision_log().clone(),
        })
    }

    pub fn digraph_from_edge_list(
        &mut self,
        payload: &EdgeListPayload,
    ) -> Result<DiConvertReport, ConvertError> {
        let feature = "convert_edge_list";
        let resolve = self.dispatch.resolve(&DispatchRequest {
            operation: "convert_edge_list".to_owned(),
            requested_backend: None,
            required_features: set([feature]),
            risk_probability: 0.05,
            unknown_incompatible_feature: false,
        });
        if let Err(err) = &resolve {
            self.record_dispatch_failure("convert_edge_list", err);
        }
        resolve?;

        let mut graph = DiGraph::new(self.mode);
        let mut warnings = Vec::new();

        if !Self::try_populate_plain_digraph_from_edge_list(&mut graph, payload) {
            self.populate_from_edge_list(&mut graph, &mut warnings, payload)?;
        }

        self.record(
            "convert_edge_list",
            DecisionAction::Allow,
            "digraph edge-list conversion completed",
            0.02,
        );

        graph.adopt_runtime_policy(self.runtime_policy.clone());

        Ok(DiConvertReport {
            graph,
            warnings,
            ledger: self.runtime_policy.decision_log().clone(),
        })
    }

    pub fn multigraph_from_edge_list(
        &mut self,
        payload: &EdgeListPayload,
    ) -> Result<MultiConvertReport, ConvertError> {
        let feature = "convert_edge_list";
        let resolve = self.dispatch.resolve(&DispatchRequest {
            operation: "convert_edge_list".to_owned(),
            requested_backend: None,
            required_features: set([feature]),
            risk_probability: 0.05,
            unknown_incompatible_feature: false,
        });
        if let Err(err) = &resolve {
            self.record_dispatch_failure("convert_edge_list", err);
        }
        resolve?;

        let mut graph = MultiGraph::new(self.mode);
        let mut warnings = Vec::new();

        self.populate_from_edge_list(&mut graph, &mut warnings, payload)?;

        self.record(
            "convert_edge_list",
            DecisionAction::Allow,
            "multigraph edge-list conversion completed",
            0.02,
        );

        graph.adopt_runtime_policy(self.runtime_policy.clone());

        Ok(MultiConvertReport {
            graph,
            warnings,
            ledger: self.runtime_policy.decision_log().clone(),
        })
    }

    pub fn multidigraph_from_edge_list(
        &mut self,
        payload: &EdgeListPayload,
    ) -> Result<MultiDiConvertReport, ConvertError> {
        let feature = "convert_edge_list";
        let resolve = self.dispatch.resolve(&DispatchRequest {
            operation: "convert_edge_list".to_owned(),
            requested_backend: None,
            required_features: set([feature]),
            risk_probability: 0.05,
            unknown_incompatible_feature: false,
        });
        if let Err(err) = &resolve {
            self.record_dispatch_failure("convert_edge_list", err);
        }
        resolve?;

        let mut graph = MultiDiGraph::new(self.mode);
        let mut warnings = Vec::new();

        self.populate_from_edge_list(&mut graph, &mut warnings, payload)?;

        self.record(
            "convert_edge_list",
            DecisionAction::Allow,
            "multidigraph edge-list conversion completed",
            0.02,
        );

        graph.adopt_runtime_policy(self.runtime_policy.clone());

        Ok(MultiDiConvertReport {
            graph,
            warnings,
            ledger: self.runtime_policy.decision_log().clone(),
        })
    }

    fn populate_from_edge_list<G>(
        &mut self,
        graph: &mut G,
        warnings: &mut Vec<String>,
        payload: &EdgeListPayload,
    ) -> Result<(), ConvertError>
    where
        G: GraphLike,
    {
        for node in &payload.nodes {
            if node.is_empty() {
                let warning = "empty node id encountered".to_owned();
                if self.mode == CompatibilityMode::Strict {
                    self.record(
                        "convert_edge_list",
                        DecisionAction::FailClosed,
                        &warning,
                        1.0,
                    );
                    return Err(ConvertError::FailClosed {
                        operation: "convert_edge_list",
                        reason: warning,
                    });
                }
                warnings.push(warning.clone());
                self.record(
                    "convert_edge_list",
                    DecisionAction::FullValidate,
                    &warning,
                    0.4,
                );
                continue;
            }
            let _ = graph.add_node(node.clone());
        }

        for edge in &payload.edges {
            if edge.left.is_empty() || edge.right.is_empty() {
                let warning = format!(
                    "malformed edge endpoint: left=`{}` right=`{}`",
                    edge.left, edge.right
                );
                if self.mode == CompatibilityMode::Strict {
                    self.record(
                        "convert_edge_list",
                        DecisionAction::FailClosed,
                        &warning,
                        1.0,
                    );
                    return Err(ConvertError::FailClosed {
                        operation: "convert_edge_list",
                        reason: warning,
                    });
                }
                warnings.push(warning.clone());
                self.record(
                    "convert_edge_list",
                    DecisionAction::FullValidate,
                    &warning,
                    0.5,
                );
                continue;
            }
            graph.add_edge_with_key_and_attrs(
                edge.left.clone(),
                edge.right.clone(),
                if edge.key.is_some() && !graph.supports_parallel_edges() {
                    let warning = format!(
                        "edge key provided for non-multigraph edge: left=`{}` right=`{}` key={:?}",
                        edge.left, edge.right, edge.key
                    );
                    if self.mode == CompatibilityMode::Strict {
                        self.record(
                            "convert_edge_list",
                            DecisionAction::FailClosed,
                            &warning,
                            1.0,
                        );
                        return Err(ConvertError::FailClosed {
                            operation: "convert_edge_list",
                            reason: warning,
                        });
                    }
                    warnings.push(warning.clone());
                    self.record(
                        "convert_edge_list",
                        DecisionAction::FullValidate,
                        &warning,
                        0.6,
                    );
                    None
                } else {
                    edge.key
                },
                edge.attrs.clone(),
            )?;
        }
        Ok(())
    }

    /// Fast path for the common plain simple-graph payload: all nodes are
    /// explicit, all edges are keyless and attribute-free, and every endpoint
    /// is already present. Resolving names once lets `Graph` consume existing
    /// indices in one batch instead of allocating two endpoint Strings and two
    /// compatibility-ledger records per edge.
    ///
    /// Returning `false` is mutation-free so the generic validator retains
    /// strict/hardened recovery, keyed-edge, attributed-edge, and implicit-node
    /// behavior unchanged.
    fn try_populate_plain_graph_from_edge_list(
        graph: &mut Graph,
        payload: &EdgeListPayload,
    ) -> bool {
        let mut node_indices = HashMap::with_capacity(payload.nodes.len());
        for node in &payload.nodes {
            if node.is_empty() {
                return false;
            }
            let next_index = node_indices.len();
            node_indices.entry(node.as_str()).or_insert(next_index);
        }

        let mut indexed_edges = Vec::with_capacity(payload.edges.len());
        for edge in &payload.edges {
            if edge.key.is_some() || !edge.attrs.is_empty() {
                return false;
            }
            let Some(&left_index) = node_indices.get(edge.left.as_str()) else {
                return false;
            };
            let Some(&right_index) = node_indices.get(edge.right.as_str()) else {
                return false;
            };
            indexed_edges.push((left_index, right_index));
        }

        let _ = graph.extend_nodes_unrecorded(payload.nodes.iter().cloned());
        let _ = graph.extend_existing_index_edges_unrecorded(indexed_edges);
        true
    }

    /// Directed sibling of `try_populate_plain_graph_from_edge_list`. The
    /// eligibility pass resolves every endpoint before mutation, then preserves
    /// payload order while inserting the directed pairs by existing node index.
    fn try_populate_plain_digraph_from_edge_list(
        graph: &mut DiGraph,
        payload: &EdgeListPayload,
    ) -> bool {
        let mut node_indices = HashMap::with_capacity(payload.nodes.len());
        for node in &payload.nodes {
            if node.is_empty() {
                return false;
            }
            let next_index = node_indices.len();
            node_indices.entry(node.as_str()).or_insert(next_index);
        }

        let mut indexed_edges = Vec::with_capacity(payload.edges.len());
        for edge in &payload.edges {
            if edge.key.is_some() || !edge.attrs.is_empty() {
                return false;
            }
            let Some(&left_index) = node_indices.get(edge.left.as_str()) else {
                return false;
            };
            let Some(&right_index) = node_indices.get(edge.right.as_str()) else {
                return false;
            };
            indexed_edges.push((left_index, right_index));
        }

        let _ = graph.extend_nodes_unrecorded(payload.nodes.iter().cloned());
        let _ = graph.extend_existing_index_edges_unrecorded(indexed_edges);
        true
    }

    /// Fast path for keyless, attribute-free simple-Graph adjacency payloads.
    /// The eligibility pass reproduces the generic loop's source-then-target
    /// first-touch order while resolving each distinct name only once.
    /// Returning `false` is mutation-free so malformed, keyed, or attributed
    /// entries retain the generic validation and recovery path.
    fn try_populate_plain_graph_from_adjacency(
        graph: &mut Graph,
        payload: &AdjacencyPayload,
    ) -> bool {
        let entry_count = payload.adjacency.values().map(Vec::len).sum::<usize>();
        let mut nodes = Vec::with_capacity(payload.adjacency.len());
        let mut node_indices = HashMap::with_capacity(payload.adjacency.len());
        let mut indexed_edges = Vec::with_capacity(entry_count);

        for (source, adjacency) in &payload.adjacency {
            if source.is_empty() {
                return false;
            }
            let source_index = if let Some(&index) = node_indices.get(source.as_str()) {
                index
            } else {
                let index = nodes.len();
                node_indices.insert(source.as_str(), index);
                nodes.push(source.clone());
                index
            };

            for neighbor in adjacency {
                if neighbor.to.is_empty() || neighbor.key.is_some() || !neighbor.attrs.is_empty() {
                    return false;
                }
                let target_index = if let Some(&index) = node_indices.get(neighbor.to.as_str()) {
                    index
                } else {
                    let index = nodes.len();
                    node_indices.insert(neighbor.to.as_str(), index);
                    nodes.push(neighbor.to.clone());
                    index
                };
                indexed_edges.push((source_index, target_index));
            }
        }

        let _ = graph.extend_nodes_unrecorded(nodes);
        let _ = graph.extend_existing_index_edges_unrecorded(indexed_edges);
        true
    }

    pub fn from_adjacency(
        &mut self,
        payload: &AdjacencyPayload,
    ) -> Result<ConvertReport, ConvertError> {
        let feature = "convert_adjacency";
        let resolve = self.dispatch.resolve(&DispatchRequest {
            operation: "convert_adjacency".to_owned(),
            requested_backend: None,
            required_features: set([feature]),
            risk_probability: 0.08,
            unknown_incompatible_feature: false,
        });
        if let Err(err) = &resolve {
            self.record_dispatch_failure("convert_adjacency", err);
        }
        resolve?;

        let mut graph = Graph::new(self.mode);
        let mut warnings = Vec::new();

        if !Self::try_populate_plain_graph_from_adjacency(&mut graph, payload) {
            self.populate_from_adjacency(&mut graph, &mut warnings, payload)?;
        }

        self.record(
            "convert_adjacency",
            DecisionAction::Allow,
            "adjacency conversion completed",
            0.03,
        );

        graph.adopt_runtime_policy(self.runtime_policy.clone());

        Ok(ConvertReport {
            graph,
            warnings,
            ledger: self.runtime_policy.decision_log().clone(),
        })
    }

    pub fn digraph_from_adjacency(
        &mut self,
        payload: &AdjacencyPayload,
    ) -> Result<DiConvertReport, ConvertError> {
        let feature = "convert_adjacency";
        let resolve = self.dispatch.resolve(&DispatchRequest {
            operation: "convert_adjacency".to_owned(),
            requested_backend: None,
            required_features: set([feature]),
            risk_probability: 0.08,
            unknown_incompatible_feature: false,
        });
        if let Err(err) = &resolve {
            self.record_dispatch_failure("convert_adjacency", err);
        }
        resolve?;

        let mut graph = DiGraph::new(self.mode);
        let mut warnings = Vec::new();

        self.populate_from_adjacency(&mut graph, &mut warnings, payload)?;

        self.record(
            "convert_adjacency",
            DecisionAction::Allow,
            "digraph adjacency conversion completed",
            0.03,
        );

        graph.adopt_runtime_policy(self.runtime_policy.clone());

        Ok(DiConvertReport {
            graph,
            warnings,
            ledger: self.runtime_policy.decision_log().clone(),
        })
    }

    pub fn multigraph_from_adjacency(
        &mut self,
        payload: &AdjacencyPayload,
    ) -> Result<MultiConvertReport, ConvertError> {
        let feature = "convert_adjacency";
        let resolve = self.dispatch.resolve(&DispatchRequest {
            operation: "convert_adjacency".to_owned(),
            requested_backend: None,
            required_features: set([feature]),
            risk_probability: 0.08,
            unknown_incompatible_feature: false,
        });
        if let Err(err) = &resolve {
            self.record_dispatch_failure("convert_adjacency", err);
        }
        resolve?;

        let mut graph = MultiGraph::new(self.mode);
        let mut warnings = Vec::new();

        self.populate_from_adjacency(&mut graph, &mut warnings, payload)?;

        self.record(
            "convert_adjacency",
            DecisionAction::Allow,
            "multigraph adjacency conversion completed",
            0.03,
        );

        graph.adopt_runtime_policy(self.runtime_policy.clone());

        Ok(MultiConvertReport {
            graph,
            warnings,
            ledger: self.runtime_policy.decision_log().clone(),
        })
    }

    pub fn multidigraph_from_adjacency(
        &mut self,
        payload: &AdjacencyPayload,
    ) -> Result<MultiDiConvertReport, ConvertError> {
        let feature = "convert_adjacency";
        let resolve = self.dispatch.resolve(&DispatchRequest {
            operation: "convert_adjacency".to_owned(),
            requested_backend: None,
            required_features: set([feature]),
            risk_probability: 0.08,
            unknown_incompatible_feature: false,
        });
        if let Err(err) = &resolve {
            self.record_dispatch_failure("convert_adjacency", err);
        }
        resolve?;

        let mut graph = MultiDiGraph::new(self.mode);
        let mut warnings = Vec::new();

        self.populate_from_adjacency(&mut graph, &mut warnings, payload)?;

        self.record(
            "convert_adjacency",
            DecisionAction::Allow,
            "multidigraph adjacency conversion completed",
            0.03,
        );

        graph.adopt_runtime_policy(self.runtime_policy.clone());

        Ok(MultiDiConvertReport {
            graph,
            warnings,
            ledger: self.runtime_policy.decision_log().clone(),
        })
    }

    fn populate_from_adjacency<G>(
        &mut self,
        graph: &mut G,
        warnings: &mut Vec<String>,
        payload: &AdjacencyPayload,
    ) -> Result<(), ConvertError>
    where
        G: GraphLike,
    {
        for (node, adjacency) in &payload.adjacency {
            if node.is_empty() {
                let warning = "empty source node in adjacency payload".to_owned();
                if self.mode == CompatibilityMode::Strict {
                    self.record(
                        "convert_adjacency",
                        DecisionAction::FailClosed,
                        &warning,
                        1.0,
                    );
                    return Err(ConvertError::FailClosed {
                        operation: "convert_adjacency",
                        reason: warning,
                    });
                }
                warnings.push(warning.clone());
                self.record(
                    "convert_adjacency",
                    DecisionAction::FullValidate,
                    &warning,
                    0.6,
                );
                continue;
            }
            let _ = graph.add_node(node.clone());
            for neighbor in adjacency {
                if neighbor.to.is_empty() {
                    let warning =
                        format!("empty target node in adjacency list for source `{node}`");
                    if self.mode == CompatibilityMode::Strict {
                        self.record(
                            "convert_adjacency",
                            DecisionAction::FailClosed,
                            &warning,
                            1.0,
                        );
                        return Err(ConvertError::FailClosed {
                            operation: "convert_adjacency",
                            reason: warning,
                        });
                    }
                    warnings.push(warning.clone());
                    self.record(
                        "convert_adjacency",
                        DecisionAction::FullValidate,
                        &warning,
                        0.6,
                    );
                    continue;
                }
                graph.add_edge_with_key_and_attrs(
                    node.clone(),
                    neighbor.to.clone(),
                    if neighbor.key.is_some() && !graph.supports_parallel_edges() {
                        let warning = format!(
                            "edge key provided for non-multigraph adjacency entry: source=`{}` target=`{}` key={:?}",
                            node, neighbor.to, neighbor.key
                        );
                        if self.mode == CompatibilityMode::Strict {
                            self.record(
                                "convert_adjacency",
                                DecisionAction::FailClosed,
                                &warning,
                                1.0,
                            );
                            return Err(ConvertError::FailClosed {
                                operation: "convert_adjacency",
                                reason: warning,
                            });
                        }
                        warnings.push(warning.clone());
                        self.record(
                            "convert_adjacency",
                            DecisionAction::FullValidate,
                            &warning,
                            0.6,
                        );
                        None
                    } else {
                        neighbor.key
                    },
                    neighbor.attrs.clone(),
                )?;
            }
        }
        Ok(())
    }
}

trait GraphLike {
    fn add_node(&mut self, node: String) -> bool;
    fn add_edge_with_key_and_attrs(
        &mut self,
        source: String,
        target: String,
        key: Option<usize>,
        attrs: AttrMap,
    ) -> Result<usize, GraphError>;
    fn supports_parallel_edges(&self) -> bool;
    fn adopt_runtime_policy(&mut self, runtime_policy: RuntimePolicy);
}

impl GraphLike for Graph {
    fn add_node(&mut self, node: String) -> bool {
        self.add_node(node)
    }
    fn add_edge_with_key_and_attrs(
        &mut self,
        source: String,
        target: String,
        _key: Option<usize>,
        attrs: AttrMap,
    ) -> Result<usize, GraphError> {
        self.add_edge_with_attrs(source, target, attrs).map(|_| 0)
    }
    fn supports_parallel_edges(&self) -> bool {
        false
    }
    fn adopt_runtime_policy(&mut self, runtime_policy: RuntimePolicy) {
        self.set_runtime_policy(runtime_policy);
    }
}

impl GraphLike for DiGraph {
    fn add_node(&mut self, node: String) -> bool {
        self.add_node(node)
    }
    fn add_edge_with_key_and_attrs(
        &mut self,
        source: String,
        target: String,
        _key: Option<usize>,
        attrs: AttrMap,
    ) -> Result<usize, GraphError> {
        self.add_edge_with_attrs(source, target, attrs).map(|_| 0)
    }
    fn supports_parallel_edges(&self) -> bool {
        false
    }
    fn adopt_runtime_policy(&mut self, runtime_policy: RuntimePolicy) {
        self.set_runtime_policy(runtime_policy);
    }
}

impl GraphLike for MultiGraph {
    fn add_node(&mut self, node: String) -> bool {
        self.add_node(node)
    }
    fn add_edge_with_key_and_attrs(
        &mut self,
        source: String,
        target: String,
        key: Option<usize>,
        attrs: AttrMap,
    ) -> Result<usize, GraphError> {
        match key {
            Some(k) => self.add_edge_with_key_and_attrs(source, target, k, attrs),
            None => self.add_edge_with_attrs(source, target, attrs),
        }
    }
    fn supports_parallel_edges(&self) -> bool {
        true
    }
    fn adopt_runtime_policy(&mut self, runtime_policy: RuntimePolicy) {
        self.set_runtime_policy(runtime_policy);
    }
}

impl GraphLike for MultiDiGraph {
    fn add_node(&mut self, node: String) -> bool {
        self.add_node(node)
    }
    fn add_edge_with_key_and_attrs(
        &mut self,
        source: String,
        target: String,
        key: Option<usize>,
        attrs: AttrMap,
    ) -> Result<usize, GraphError> {
        match key {
            Some(k) => self.add_edge_with_key_and_attrs(source, target, k, attrs),
            None => self.add_edge_with_attrs(source, target, attrs),
        }
    }
    fn supports_parallel_edges(&self) -> bool {
        true
    }
    fn adopt_runtime_policy(&mut self, runtime_policy: RuntimePolicy) {
        self.set_runtime_policy(runtime_policy);
    }
}

#[must_use]
pub fn to_normalized_payload(graph: &Graph) -> GraphSnapshot {
    graph.snapshot()
}

/// br-convertapi: ``to_normalized_payload`` previously only handled
/// the undirected ``Graph`` case, leaving ``DiGraph`` / ``MultiGraph``
/// / ``MultiDiGraph`` callers to do their own ``.snapshot()`` call.
/// Add the parallel variants so the API is symmetric across all four
/// graph types.
#[must_use]
pub fn digraph_to_normalized_payload(graph: &DiGraph) -> DiGraphSnapshot {
    graph.snapshot()
}

#[must_use]
pub fn multigraph_to_normalized_payload(graph: &MultiGraph) -> MultiGraphSnapshot {
    graph.snapshot()
}

#[must_use]
pub fn multidigraph_to_normalized_payload(graph: &MultiDiGraph) -> MultiDiGraphSnapshot {
    graph.snapshot()
}

fn set<const N: usize>(values: [&str; N]) -> BTreeSet<String> {
    values.into_iter().map(str::to_owned).collect()
}

impl GraphConverter {
    /// br-dispatchaudit: when the dispatcher rejects a request the
    /// converter previously returned the error directly without
    /// leaving an audit-trail entry. Add a fail-closed decision so
    /// ``evidence_ledger()`` reflects the rejection.
    fn record_dispatch_failure(&mut self, operation: &'static str, err: &DispatchError) {
        let message = format!("dispatch rejected: {err}");
        self.record(operation, DecisionAction::FailClosed, &message, 1.0);
    }

    fn record(
        &mut self,
        operation: &'static str,
        action: DecisionAction,
        message: &str,
        incompatibility_probability: f64,
    ) {
        self.runtime_policy.record(
            operation,
            action,
            incompatibility_probability,
            message,
            vec![EvidenceTerm {
                signal: "message".to_owned(),
                observed_value: message.to_owned(),
                log_likelihood_ratio: if action == DecisionAction::Allow {
                    -1.5
                } else {
                    2.0
                },
            }],
        );
    }
}

#[cfg(test)]
mod tests {
    use super::{
        AdjacencyEntry, AdjacencyPayload, ConvertError, EdgeListPayload, EdgeRecord, GraphConverter,
    };
    use fnx_classes::{AttrMap, Graph, digraph::DiGraph};
    use fnx_runtime::{CgseValue, CompatibilityMode};
    use std::collections::BTreeMap;

    fn populate_plain_graph_frozen(payload: &EdgeListPayload) -> Graph {
        let mut converter = GraphConverter::strict();
        let mut graph = Graph::strict();
        let mut warnings = Vec::new();
        converter
            .populate_from_edge_list(&mut graph, &mut warnings, payload)
            .expect("plain frozen payload should convert");
        assert!(warnings.is_empty());
        graph
    }

    fn populate_plain_graph_batched(payload: &EdgeListPayload) -> Graph {
        let mut graph = Graph::strict();
        assert!(GraphConverter::try_populate_plain_graph_from_edge_list(
            &mut graph, payload
        ));
        graph
    }

    fn populate_plain_digraph_frozen(payload: &EdgeListPayload) -> DiGraph {
        let mut converter = GraphConverter::strict();
        let mut graph = DiGraph::strict();
        let mut warnings = Vec::new();
        converter
            .populate_from_edge_list(&mut graph, &mut warnings, payload)
            .expect("plain frozen payload should convert");
        assert!(warnings.is_empty());
        graph
    }

    fn populate_plain_digraph_batched(payload: &EdgeListPayload) -> DiGraph {
        let mut graph = DiGraph::strict();
        assert!(GraphConverter::try_populate_plain_digraph_from_edge_list(
            &mut graph, payload
        ));
        graph
    }

    fn populate_plain_graph_adjacency_frozen(payload: &AdjacencyPayload) -> Graph {
        let mut converter = GraphConverter::strict();
        let mut graph = Graph::strict();
        let mut warnings = Vec::new();
        converter
            .populate_from_adjacency(&mut graph, &mut warnings, payload)
            .expect("plain frozen adjacency should convert");
        assert!(warnings.is_empty());
        graph
    }

    fn populate_plain_graph_adjacency_batched(payload: &AdjacencyPayload) -> Graph {
        let mut graph = Graph::strict();
        assert!(GraphConverter::try_populate_plain_graph_from_adjacency(
            &mut graph, payload
        ));
        graph
    }

    #[test]
    fn convert_from_edge_list_basic() {
        let mut converter = GraphConverter::strict();
        let payload = EdgeListPayload {
            nodes: vec!["a".to_owned(), "b".to_owned()],
            edges: vec![EdgeRecord {
                left: "a".to_owned(),
                right: "b".to_owned(),
                key: None,
                attrs: AttrMap::from([("weight".to_owned(), CgseValue::String("1.0".to_owned()))]),
            }],
        };

        let report = converter
            .from_edge_list(&payload)
            .expect("conversion should succeed");
        assert_eq!(report.graph.node_count(), 2);
        assert_eq!(report.graph.edge_count(), 1);
        assert_eq!(report.graph.node_attrs("a").unwrap().len(), 0);
        assert_eq!(
            report
                .graph
                .edge_attrs("a", "b")
                .unwrap()
                .get("weight")
                .unwrap()
                .as_str(),
            "1.0"
        );
    }

    #[test]
    fn plain_graph_edge_list_batch_preserves_order_and_revision() {
        let edge = |left: &str, right: &str| EdgeRecord {
            left: left.to_owned(),
            right: right.to_owned(),
            key: None,
            attrs: AttrMap::new(),
        };
        let payloads = [
            EdgeListPayload {
                nodes: Vec::new(),
                edges: Vec::new(),
            },
            EdgeListPayload {
                nodes: ["z", "a", "m", "a", "q"]
                    .into_iter()
                    .map(str::to_owned)
                    .collect(),
                edges: vec![
                    edge("z", "z"),
                    edge("q", "a"),
                    edge("m", "z"),
                    edge("z", "q"),
                    edge("q", "z"),
                ],
            },
        ];

        for payload in payloads {
            let frozen = populate_plain_graph_frozen(&payload);
            let batched = populate_plain_graph_batched(&payload);
            assert_eq!(batched.snapshot(), frozen.snapshot());
            assert_eq!(batched.revision(), frozen.revision());
        }
    }

    #[test]
    fn plain_graph_edge_list_batch_fallback_is_mutation_free() {
        let payload = EdgeListPayload {
            nodes: vec!["a".to_owned(), "b".to_owned()],
            edges: vec![
                EdgeRecord {
                    left: "a".to_owned(),
                    right: "b".to_owned(),
                    key: None,
                    attrs: AttrMap::new(),
                },
                EdgeRecord {
                    left: "b".to_owned(),
                    right: "implicit".to_owned(),
                    key: None,
                    attrs: AttrMap::new(),
                },
            ],
        };
        let mut graph = Graph::strict();

        assert!(!GraphConverter::try_populate_plain_graph_from_edge_list(
            &mut graph, &payload
        ));
        assert_eq!(graph.node_count(), 0);
        assert_eq!(graph.edge_count(), 0);
        assert_eq!(graph.revision(), 0);
    }

    /// Same-binary paired A/B for the plain simple-Graph population kernel.
    /// The frozen arm retains the former generic per-item insertion loop; the
    /// candidate resolves endpoint names once and submits existing indices in
    /// one batch. Both include converter/graph setup and object destruction.
    #[test]
    #[ignore = "measurement; run with --profile release --ignored --nocapture"]
    fn plain_graph_edge_list_index_batch_ab() {
        use std::hint::black_box;
        use std::time::Instant;

        let n = 2_048usize;
        let nodes = (0..n)
            .map(|node| format!("node-{node:05}"))
            .collect::<Vec<_>>();
        let mut edges = Vec::with_capacity(n * 4 + 1);
        for node in 0..n {
            for offset in [1usize, 17, 97, 257] {
                edges.push(EdgeRecord {
                    left: nodes[node].clone(),
                    right: nodes[(node + offset) % n].clone(),
                    key: None,
                    attrs: AttrMap::new(),
                });
            }
        }
        edges.push(EdgeRecord {
            left: nodes[0].clone(),
            right: nodes[0].clone(),
            key: None,
            attrs: AttrMap::new(),
        });
        let payload = EdgeListPayload { nodes, edges };

        let frozen = populate_plain_graph_frozen(&payload);
        let batched = populate_plain_graph_batched(&payload);
        assert_eq!(batched.snapshot(), frozen.snapshot());
        assert_eq!(batched.revision(), frozen.revision());

        let rounds = 15usize;
        let time = |batch: bool| {
            let started = Instant::now();
            let mut converter = GraphConverter::strict();
            let mut graph = Graph::strict();
            let mut warnings = Vec::new();
            if batch {
                assert!(GraphConverter::try_populate_plain_graph_from_edge_list(
                    &mut graph, &payload
                ));
            } else {
                converter
                    .populate_from_edge_list(&mut graph, &mut warnings, &payload)
                    .expect("frozen plain payload should convert");
            }
            black_box((converter, graph, warnings));
            started.elapsed().as_nanos()
        };
        for _ in 0..3 {
            black_box(time(false));
            black_box(time(true));
        }

        let paired = |candidate: bool, baseline: bool| {
            let mut baseline_ns = Vec::with_capacity(rounds);
            let mut candidate_ns = Vec::with_capacity(rounds);
            for round in 0..rounds {
                let (base, cand) = if round % 2 == 0 {
                    (time(baseline), time(candidate))
                } else {
                    let cand = time(candidate);
                    let base = time(baseline);
                    (base, cand)
                };
                baseline_ns.push(base);
                candidate_ns.push(cand);
            }
            (baseline_ns, candidate_ns)
        };
        let median = |samples: &[u128]| {
            let mut sorted = samples.to_vec();
            sorted.sort_unstable();
            sorted[sorted.len() / 2]
        };
        let report = |name: &str, baseline_ns: &[u128], candidate_ns: &[u128]| {
            let baseline_median = median(baseline_ns);
            let candidate_median = median(candidate_ns);
            let wins = baseline_ns
                .iter()
                .zip(candidate_ns)
                .filter(|(baseline, candidate)| baseline > candidate)
                .count();
            println!(
                "CONVERT_PLAIN_INDEX_BATCH_AB {name}: baseline_median_ns={baseline_median} \
                 candidate_median_ns={candidate_median} ratio={:.4}x wins={wins}/{rounds}",
                baseline_median as f64 / candidate_median as f64,
            );
        };

        let (baseline_ns, candidate_ns) = paired(true, false);
        report("frozen_vs_index_batch", &baseline_ns, &candidate_ns);
        let (null_a_ns, null_b_ns) = paired(true, true);
        report("index_batch_vs_index_batch_null", &null_a_ns, &null_b_ns);
    }

    #[test]
    fn plain_digraph_edge_list_batch_preserves_direction_order_and_revision() {
        let edge = |left: &str, right: &str| EdgeRecord {
            left: left.to_owned(),
            right: right.to_owned(),
            key: None,
            attrs: AttrMap::new(),
        };
        let payloads = [
            EdgeListPayload {
                nodes: Vec::new(),
                edges: Vec::new(),
            },
            EdgeListPayload {
                nodes: ["z", "a", "m", "a", "q"]
                    .into_iter()
                    .map(str::to_owned)
                    .collect(),
                edges: vec![
                    edge("z", "z"),
                    edge("q", "a"),
                    edge("a", "q"),
                    edge("m", "z"),
                    edge("z", "q"),
                    edge("q", "z"),
                    edge("q", "a"),
                ],
            },
        ];

        for payload in payloads {
            let frozen = populate_plain_digraph_frozen(&payload);
            let batched = populate_plain_digraph_batched(&payload);
            assert_eq!(batched.snapshot(), frozen.snapshot());
            assert_eq!(batched.revision(), frozen.revision());
        }
    }

    #[test]
    fn plain_digraph_edge_list_batch_fallback_is_mutation_free() {
        let payload = EdgeListPayload {
            nodes: vec!["a".to_owned(), "b".to_owned()],
            edges: vec![
                EdgeRecord {
                    left: "a".to_owned(),
                    right: "b".to_owned(),
                    key: None,
                    attrs: AttrMap::new(),
                },
                EdgeRecord {
                    left: "b".to_owned(),
                    right: "implicit".to_owned(),
                    key: None,
                    attrs: AttrMap::new(),
                },
            ],
        };
        let mut graph = DiGraph::strict();

        assert!(!GraphConverter::try_populate_plain_digraph_from_edge_list(
            &mut graph, &payload
        ));
        assert_eq!(graph.node_count(), 0);
        assert_eq!(graph.edge_count(), 0);
        assert_eq!(graph.revision(), 0);
    }

    /// Same-binary paired A/B for the plain simple-DiGraph population kernel.
    /// The frozen arm retains the former generic per-item insertion loop; the
    /// candidate resolves endpoint names once and submits directed index pairs.
    #[test]
    #[ignore = "measurement; run with --profile release --ignored --nocapture"]
    fn plain_digraph_edge_list_index_batch_ab() {
        use std::hint::black_box;
        use std::time::Instant;

        let n = 2_048usize;
        let nodes = (0..n)
            .map(|node| format!("node-{node:05}"))
            .collect::<Vec<_>>();
        let mut edges = Vec::with_capacity(n * 4 + 1);
        for node in 0..n {
            for offset in [1usize, 17, 97, 257] {
                edges.push(EdgeRecord {
                    left: nodes[node].clone(),
                    right: nodes[(node + offset) % n].clone(),
                    key: None,
                    attrs: AttrMap::new(),
                });
            }
        }
        edges.push(EdgeRecord {
            left: nodes[0].clone(),
            right: nodes[0].clone(),
            key: None,
            attrs: AttrMap::new(),
        });
        let payload = EdgeListPayload { nodes, edges };

        let frozen = populate_plain_digraph_frozen(&payload);
        let batched = populate_plain_digraph_batched(&payload);
        assert_eq!(batched.snapshot(), frozen.snapshot());
        assert_eq!(batched.revision(), frozen.revision());

        let rounds = 15usize;
        let time = |batch: bool| {
            let started = Instant::now();
            let mut converter = GraphConverter::strict();
            let mut graph = DiGraph::strict();
            let mut warnings = Vec::new();
            if batch {
                assert!(GraphConverter::try_populate_plain_digraph_from_edge_list(
                    &mut graph, &payload
                ));
            } else {
                converter
                    .populate_from_edge_list(&mut graph, &mut warnings, &payload)
                    .expect("frozen plain payload should convert");
            }
            black_box((converter, graph, warnings));
            started.elapsed().as_nanos()
        };
        for _ in 0..3 {
            black_box(time(false));
            black_box(time(true));
        }

        let paired = |candidate: bool, baseline: bool| {
            let mut baseline_ns = Vec::with_capacity(rounds);
            let mut candidate_ns = Vec::with_capacity(rounds);
            for round in 0..rounds {
                let (base, cand) = if round % 2 == 0 {
                    (time(baseline), time(candidate))
                } else {
                    let cand = time(candidate);
                    let base = time(baseline);
                    (base, cand)
                };
                baseline_ns.push(base);
                candidate_ns.push(cand);
            }
            (baseline_ns, candidate_ns)
        };
        let median = |samples: &[u128]| {
            let mut sorted = samples.to_vec();
            sorted.sort_unstable();
            sorted[sorted.len() / 2]
        };
        let report = |name: &str, baseline_ns: &[u128], candidate_ns: &[u128]| {
            let baseline_median = median(baseline_ns);
            let candidate_median = median(candidate_ns);
            let wins = baseline_ns
                .iter()
                .zip(candidate_ns)
                .filter(|(baseline, candidate)| baseline > candidate)
                .count();
            println!(
                "CONVERT_PLAIN_DIGRAPH_INDEX_BATCH_AB {name}: baseline_median_ns={baseline_median} \
                 candidate_median_ns={candidate_median} ratio={:.4}x wins={wins}/{rounds}",
                baseline_median as f64 / candidate_median as f64,
            );
        };

        let (baseline_ns, candidate_ns) = paired(true, false);
        report("frozen_vs_index_batch", &baseline_ns, &candidate_ns);
        let (null_a_ns, null_b_ns) = paired(true, true);
        report("index_batch_vs_index_batch_null", &null_a_ns, &null_b_ns);
    }

    #[test]
    fn plain_graph_adjacency_batch_preserves_order_and_revision() {
        let entry = |target: &str| AdjacencyEntry {
            to: target.to_owned(),
            key: None,
            attrs: AttrMap::new(),
        };
        let payloads = [
            AdjacencyPayload {
                adjacency: BTreeMap::new(),
            },
            AdjacencyPayload {
                adjacency: BTreeMap::from([
                    (
                        "m".to_owned(),
                        vec![entry("z"), entry("m"), entry("a"), entry("z")],
                    ),
                    ("z".to_owned(), vec![entry("a"), entry("m")]),
                    ("a".to_owned(), Vec::new()),
                ]),
            },
        ];

        for payload in payloads {
            let frozen = populate_plain_graph_adjacency_frozen(&payload);
            let batched = populate_plain_graph_adjacency_batched(&payload);
            assert_eq!(batched.snapshot(), frozen.snapshot());
            assert_eq!(batched.revision(), frozen.revision());
        }
    }

    #[test]
    fn plain_graph_adjacency_batch_fallback_is_mutation_free() {
        let payloads = [
            AdjacencyPayload {
                adjacency: BTreeMap::from([
                    (
                        "a".to_owned(),
                        vec![AdjacencyEntry {
                            to: "b".to_owned(),
                            key: None,
                            attrs: AttrMap::new(),
                        }],
                    ),
                    (
                        "z".to_owned(),
                        vec![AdjacencyEntry {
                            to: "a".to_owned(),
                            key: None,
                            attrs: AttrMap::from([("weight".to_owned(), CgseValue::Int(1))]),
                        }],
                    ),
                ]),
            },
            AdjacencyPayload {
                adjacency: BTreeMap::from([(
                    "a".to_owned(),
                    vec![AdjacencyEntry {
                        to: "b".to_owned(),
                        key: Some(7),
                        attrs: AttrMap::new(),
                    }],
                )]),
            },
            AdjacencyPayload {
                adjacency: BTreeMap::from([(
                    "a".to_owned(),
                    vec![AdjacencyEntry {
                        to: String::new(),
                        key: None,
                        attrs: AttrMap::new(),
                    }],
                )]),
            },
        ];

        for payload in payloads {
            let mut graph = Graph::strict();
            assert!(!GraphConverter::try_populate_plain_graph_from_adjacency(
                &mut graph, &payload
            ));
            assert_eq!(graph.node_count(), 0);
            assert_eq!(graph.edge_count(), 0);
            assert_eq!(graph.revision(), 0);
        }
    }

    /// Same-binary paired A/B for the plain simple-Graph adjacency kernel.
    /// The frozen arm retains the generic source/neighbor mutation loop; the
    /// candidate resolves exact first-touch node order and batches index edges.
    #[test]
    #[ignore = "measurement; run with --profile release --ignored --nocapture"]
    fn plain_graph_adjacency_index_batch_ab() {
        use std::hint::black_box;
        use std::time::Instant;

        let n = 2_048usize;
        let node_labels = (0..n)
            .map(|node| format!("node-{node:05}"))
            .collect::<Vec<_>>();
        let adjacency = node_labels
            .iter()
            .enumerate()
            .map(|(source, source_label)| {
                let neighbors = [0usize, 1, 17, 257]
                    .into_iter()
                    .map(|offset| AdjacencyEntry {
                        to: node_labels[(source + offset) % n].clone(),
                        key: None,
                        attrs: AttrMap::new(),
                    })
                    .collect();
                (source_label.clone(), neighbors)
            })
            .collect::<BTreeMap<_, _>>();
        let payload = AdjacencyPayload { adjacency };

        let frozen = populate_plain_graph_adjacency_frozen(&payload);
        let batched = populate_plain_graph_adjacency_batched(&payload);
        assert_eq!(batched.snapshot(), frozen.snapshot());
        assert_eq!(batched.revision(), frozen.revision());

        let rounds = 15usize;
        let time = |batch: bool| {
            let started = Instant::now();
            let mut converter = GraphConverter::strict();
            let mut graph = Graph::strict();
            let mut warnings = Vec::new();
            if batch {
                assert!(GraphConverter::try_populate_plain_graph_from_adjacency(
                    &mut graph, &payload
                ));
            } else {
                converter
                    .populate_from_adjacency(&mut graph, &mut warnings, &payload)
                    .expect("frozen plain adjacency should convert");
            }
            black_box((converter, graph, warnings));
            started.elapsed().as_nanos()
        };
        for _ in 0..3 {
            black_box(time(false));
            black_box(time(true));
        }

        let paired = |candidate: bool, baseline: bool| {
            let mut baseline_ns = Vec::with_capacity(rounds);
            let mut candidate_ns = Vec::with_capacity(rounds);
            for round in 0..rounds {
                let (base, cand) = if round % 2 == 0 {
                    (time(baseline), time(candidate))
                } else {
                    let cand = time(candidate);
                    let base = time(baseline);
                    (base, cand)
                };
                baseline_ns.push(base);
                candidate_ns.push(cand);
            }
            (baseline_ns, candidate_ns)
        };
        let median = |samples: &[u128]| {
            let mut sorted = samples.to_vec();
            sorted.sort_unstable();
            sorted[sorted.len() / 2]
        };
        let report = |name: &str, baseline_ns: &[u128], candidate_ns: &[u128]| {
            let baseline_median = median(baseline_ns);
            let candidate_median = median(candidate_ns);
            let wins = baseline_ns
                .iter()
                .zip(candidate_ns)
                .filter(|(baseline, candidate)| baseline > candidate)
                .count();
            println!(
                "CONVERT_PLAIN_ADJACENCY_INDEX_BATCH_AB {name}: entries={} \
                 baseline_median_ns={baseline_median} candidate_median_ns={candidate_median} \
                 ratio={:.4}x wins={wins}/{rounds} exact_snapshot_revision=true",
                n * 4,
                baseline_median as f64 / candidate_median as f64,
            );
        };

        let (baseline_ns, candidate_ns) = paired(true, false);
        report("generic_vs_index_batch", &baseline_ns, &candidate_ns);
        let (null_a_ns, null_b_ns) = paired(true, true);
        report("index_batch_vs_index_batch_null", &null_a_ns, &null_b_ns);
    }

    #[test]
    fn convert_from_adjacency_basic() {
        let mut converter = GraphConverter::strict();
        let mut adjacency = BTreeMap::new();
        adjacency.insert(
            "a".to_owned(),
            vec![AdjacencyEntry {
                to: "b".to_owned(),
                key: None,
                attrs: AttrMap::from([("weight".to_owned(), CgseValue::String("2.0".to_owned()))]),
            }],
        );
        let payload = AdjacencyPayload { adjacency };

        let report = converter
            .from_adjacency(&payload)
            .expect("conversion should succeed");
        assert_eq!(report.graph.node_count(), 2);
        assert_eq!(report.graph.edge_count(), 1);
        assert_eq!(
            report
                .graph
                .edge_attrs("a", "b")
                .unwrap()
                .get("weight")
                .unwrap()
                .as_str(),
            "2.0"
        );
    }

    #[test]
    fn strict_edge_list_rejects_key_for_graph() {
        let mut converter = GraphConverter::strict();
        let payload = EdgeListPayload {
            nodes: vec!["a".to_owned(), "b".to_owned()],
            edges: vec![EdgeRecord {
                left: "a".to_owned(),
                right: "b".to_owned(),
                key: Some(7),
                attrs: AttrMap::new(),
            }],
        };

        let err = converter
            .from_edge_list(&payload)
            .expect_err("strict mode should reject edge keys for Graph");
        assert!(matches!(err, ConvertError::FailClosed { .. }));
    }

    #[test]
    fn hardened_edge_list_warns_and_drops_key_for_graph() {
        let mut converter = GraphConverter::hardened();
        let payload = EdgeListPayload {
            nodes: vec!["a".to_owned(), "b".to_owned()],
            edges: vec![EdgeRecord {
                left: "a".to_owned(),
                right: "b".to_owned(),
                key: Some(3),
                attrs: AttrMap::new(),
            }],
        };

        let report = converter
            .from_edge_list(&payload)
            .expect("hardened mode should drop key and recover");
        assert!(!report.warnings.is_empty());
        assert_eq!(report.graph.edge_count(), 1);
    }

    #[test]
    fn strict_adjacency_rejects_key_for_graph() {
        let mut converter = GraphConverter::strict();
        let mut adjacency = BTreeMap::new();
        adjacency.insert(
            "a".to_owned(),
            vec![AdjacencyEntry {
                to: "b".to_owned(),
                key: Some(1),
                attrs: AttrMap::new(),
            }],
        );
        let payload = AdjacencyPayload { adjacency };

        let err = converter
            .from_adjacency(&payload)
            .expect_err("strict mode should reject adjacency keys for Graph");
        assert!(matches!(err, ConvertError::FailClosed { .. }));
    }

    #[test]
    fn hardened_adjacency_warns_and_drops_key_for_graph() {
        let mut converter = GraphConverter::hardened();
        let mut adjacency = BTreeMap::new();
        adjacency.insert(
            "a".to_owned(),
            vec![AdjacencyEntry {
                to: "b".to_owned(),
                key: Some(5),
                attrs: AttrMap::new(),
            }],
        );
        let payload = AdjacencyPayload { adjacency };

        let report = converter
            .from_adjacency(&payload)
            .expect("hardened mode should drop key and recover");
        assert!(!report.warnings.is_empty());
        assert_eq!(report.graph.edge_count(), 1);
    }

    #[test]
    fn convert_digraph_from_edge_list() {
        let mut converter = GraphConverter::strict();
        let payload = EdgeListPayload {
            nodes: vec!["a".to_owned(), "b".to_owned()],
            edges: vec![EdgeRecord {
                left: "a".to_owned(),
                right: "b".to_owned(),
                key: None,
                attrs: AttrMap::new(),
            }],
        };

        let report = converter
            .digraph_from_edge_list(&payload)
            .expect("conversion should succeed");
        assert!(report.graph.has_edge("a", "b"));
        assert!(!report.graph.has_edge("b", "a"));
    }

    #[test]
    fn convert_multigraph_from_edge_list() {
        let mut converter = GraphConverter::strict();
        let payload = EdgeListPayload {
            nodes: vec!["a".to_owned(), "b".to_owned()],
            edges: vec![
                EdgeRecord {
                    left: "a".to_owned(),
                    right: "b".to_owned(),
                    key: Some(0),
                    attrs: AttrMap::new(),
                },
                EdgeRecord {
                    left: "a".to_owned(),
                    right: "b".to_owned(),
                    key: Some(1),
                    attrs: AttrMap::new(),
                },
            ],
        };

        let report = converter
            .multigraph_from_edge_list(&payload)
            .expect("conversion should succeed");
        assert_eq!(report.graph.node_count(), 2);
        assert_eq!(report.graph.edge_count(), 2);
    }

    #[test]
    fn runtime_policy_tracks_hardened_conversion_recovery() {
        let mut converter = GraphConverter::hardened();
        let payload = EdgeListPayload {
            nodes: vec!["a".to_owned(), "b".to_owned()],
            edges: vec![EdgeRecord {
                left: "a".to_owned(),
                right: "b".to_owned(),
                key: Some(9),
                attrs: AttrMap::new(),
            }],
        };

        let report = converter
            .from_edge_list(&payload)
            .expect("hardened conversion should recover by dropping the key");
        assert!(!report.warnings.is_empty());
        assert_eq!(
            converter.runtime_policy().mode(),
            CompatibilityMode::Hardened
        );
        assert!(
            !converter
                .runtime_policy()
                .decision_log()
                .records()
                .is_empty()
        );
        assert!(converter.runtime_policy().posterior().observation_count >= 1);
    }

    #[test]
    fn result_graph_inherits_converter_runtime_policy_after_recovery() {
        let mut converter = GraphConverter::hardened();
        let payload = EdgeListPayload {
            nodes: vec!["a".to_owned(), "b".to_owned()],
            edges: vec![EdgeRecord {
                left: "a".to_owned(),
                right: "b".to_owned(),
                key: Some(9),
                attrs: AttrMap::new(),
            }],
        };

        let report = converter
            .from_edge_list(&payload)
            .expect("hardened conversion should recover by dropping the key");

        assert_eq!(report.graph.runtime_policy(), converter.runtime_policy());
        assert_eq!(&report.ledger, report.graph.evidence_ledger());
    }

    #[test]
    fn result_multidigraph_inherits_converter_runtime_policy() {
        let mut converter = GraphConverter::hardened();
        let payload = AdjacencyPayload {
            adjacency: BTreeMap::from([(
                "a".to_owned(),
                vec![AdjacencyEntry {
                    to: "b".to_owned(),
                    key: Some(3),
                    attrs: AttrMap::new(),
                }],
            )]),
        };

        let report = converter
            .multidigraph_from_adjacency(&payload)
            .expect("multidigraph adjacency conversion should succeed");

        assert_eq!(report.graph.runtime_policy(), converter.runtime_policy());
        assert_eq!(&report.ledger, report.graph.evidence_ledger());
    }

    #[test]
    fn empty_payload_deserializes_via_serde_default() {
        // br-payloaddefault: serde defaults on EdgeListPayload.{nodes,edges}
        // mean an empty JSON object decodes to an empty graph instead of
        // failing with "missing field". Same for AdjacencyPayload.
        let edge_list: EdgeListPayload = serde_json::from_str("{}").expect("empty edge list");
        assert!(edge_list.nodes.is_empty() && edge_list.edges.is_empty());
        let adj: AdjacencyPayload = serde_json::from_str("{}").expect("empty adjacency");
        assert!(adj.adjacency.is_empty());
        // Mixed: nodes only, no edges field (and vice versa).
        let nodes_only: EdgeListPayload =
            serde_json::from_str(r#"{"nodes":["a","b"]}"#).expect("nodes only");
        assert_eq!(nodes_only.nodes.len(), 2);
        assert!(nodes_only.edges.is_empty());
        let edges_only: EdgeListPayload =
            serde_json::from_str(r#"{"edges":[{"left":"a","right":"b"}]}"#).expect("edges only");
        assert!(edges_only.nodes.is_empty());
        assert_eq!(edges_only.edges.len(), 1);
    }

    #[test]
    fn to_normalized_payload_variants_match_underlying_snapshot() {
        // br-convertapi: digraph_to_normalized_payload, multigraph_*,
        // multidigraph_* all defer to the underlying graph.snapshot().
        // The audit added them for API symmetry; this test pins the
        // contract that they don't drift from snapshot().
        use fnx_classes::digraph::{DiGraph, MultiDiGraph};
        use fnx_classes::{Graph, MultiGraph};

        let mut g = Graph::new(CompatibilityMode::Strict);
        let _ = g.add_edge_with_attrs("a", "b", AttrMap::new());
        assert_eq!(super::to_normalized_payload(&g), g.snapshot());

        let mut dg = DiGraph::new(CompatibilityMode::Strict);
        let _ = dg.add_edge_with_attrs("a", "b", AttrMap::new());
        assert_eq!(super::digraph_to_normalized_payload(&dg), dg.snapshot());

        let mut mg = MultiGraph::new(CompatibilityMode::Strict);
        let _ = mg.add_edge_with_attrs("a", "b", AttrMap::new());
        assert_eq!(super::multigraph_to_normalized_payload(&mg), mg.snapshot());

        let mut mdg = MultiDiGraph::new(CompatibilityMode::Strict);
        let _ = mdg.add_edge_with_attrs("a", "b", AttrMap::new());
        assert_eq!(
            super::multidigraph_to_normalized_payload(&mdg),
            mdg.snapshot()
        );
    }

    #[test]
    fn successful_conversion_records_decision_in_ledger() {
        // br-dispatchaudit: even on the success path, the converter
        // records its decision (operation completion) so the ledger
        // is never empty after a real conversion. The new
        // record_dispatch_failure helper is exercised in the
        // negative path during integration testing.
        let mut converter = GraphConverter::strict();
        let payload = EdgeListPayload {
            nodes: vec!["a".to_owned(), "b".to_owned()],
            edges: vec![EdgeRecord {
                left: "a".to_owned(),
                right: "b".to_owned(),
                key: None,
                attrs: AttrMap::new(),
            }],
        };
        let _ = converter
            .from_edge_list(&payload)
            .expect("conversion should succeed");
        assert!(
            !converter.evidence_ledger().is_empty(),
            "successful conversion must log at least one decision"
        );
    }
}
