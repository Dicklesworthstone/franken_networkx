#![forbid(unsafe_code)]

use fnx_classes::digraph::{DiGraph, MultiDiGraph};
use fnx_classes::{AttrMap, Graph, GraphError, GraphSnapshot, MultiGraph};
use fnx_dispatch::{BackendRegistry, BackendSpec, DispatchError, DispatchRequest};
use fnx_runtime::{CompatibilityMode, DecisionAction, EvidenceLedger, EvidenceTerm, RuntimePolicy};
use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, BTreeSet};
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
    #[serde(default)]
    pub nodes: Vec<String>,
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
        self.dispatch.resolve(&DispatchRequest {
            operation: "convert_edge_list".to_owned(),
            requested_backend: None,
            required_features: set([feature]),
            risk_probability: 0.05,
            unknown_incompatible_feature: false,
        })?;

        let mut graph = Graph::new(self.mode);
        let mut warnings = Vec::new();

        self.populate_from_edge_list(&mut graph, &mut warnings, payload)?;

        self.record(
            "convert_edge_list",
            DecisionAction::Allow,
            "edge-list conversion completed",
            0.02,
        );

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
        self.dispatch.resolve(&DispatchRequest {
            operation: "convert_edge_list".to_owned(),
            requested_backend: None,
            required_features: set([feature]),
            risk_probability: 0.05,
            unknown_incompatible_feature: false,
        })?;

        let mut graph = DiGraph::new(self.mode);
        let mut warnings = Vec::new();

        self.populate_from_edge_list(&mut graph, &mut warnings, payload)?;

        self.record(
            "convert_edge_list",
            DecisionAction::Allow,
            "digraph edge-list conversion completed",
            0.02,
        );

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
        self.dispatch.resolve(&DispatchRequest {
            operation: "convert_edge_list".to_owned(),
            requested_backend: None,
            required_features: set([feature]),
            risk_probability: 0.05,
            unknown_incompatible_feature: false,
        })?;

        let mut graph = MultiGraph::new(self.mode);
        let mut warnings = Vec::new();

        self.populate_from_edge_list(&mut graph, &mut warnings, payload)?;

        self.record(
            "convert_edge_list",
            DecisionAction::Allow,
            "multigraph edge-list conversion completed",
            0.02,
        );

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
        self.dispatch.resolve(&DispatchRequest {
            operation: "convert_edge_list".to_owned(),
            requested_backend: None,
            required_features: set([feature]),
            risk_probability: 0.05,
            unknown_incompatible_feature: false,
        })?;

        let mut graph = MultiDiGraph::new(self.mode);
        let mut warnings = Vec::new();

        self.populate_from_edge_list(&mut graph, &mut warnings, payload)?;

        self.record(
            "convert_edge_list",
            DecisionAction::Allow,
            "multidigraph edge-list conversion completed",
            0.02,
        );

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

    pub fn from_adjacency(
        &mut self,
        payload: &AdjacencyPayload,
    ) -> Result<ConvertReport, ConvertError> {
        let feature = "convert_adjacency";
        self.dispatch.resolve(&DispatchRequest {
            operation: "convert_adjacency".to_owned(),
            requested_backend: None,
            required_features: set([feature]),
            risk_probability: 0.08,
            unknown_incompatible_feature: false,
        })?;

        let mut graph = Graph::new(self.mode);
        let mut warnings = Vec::new();

        self.populate_from_adjacency(&mut graph, &mut warnings, payload)?;

        self.record(
            "convert_adjacency",
            DecisionAction::Allow,
            "adjacency conversion completed",
            0.03,
        );

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
        self.dispatch.resolve(&DispatchRequest {
            operation: "convert_adjacency".to_owned(),
            requested_backend: None,
            required_features: set([feature]),
            risk_probability: 0.08,
            unknown_incompatible_feature: false,
        })?;

        let mut graph = DiGraph::new(self.mode);
        let mut warnings = Vec::new();

        self.populate_from_adjacency(&mut graph, &mut warnings, payload)?;

        self.record(
            "convert_adjacency",
            DecisionAction::Allow,
            "digraph adjacency conversion completed",
            0.03,
        );

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
        self.dispatch.resolve(&DispatchRequest {
            operation: "convert_adjacency".to_owned(),
            requested_backend: None,
            required_features: set([feature]),
            risk_probability: 0.08,
            unknown_incompatible_feature: false,
        })?;

        let mut graph = MultiGraph::new(self.mode);
        let mut warnings = Vec::new();

        self.populate_from_adjacency(&mut graph, &mut warnings, payload)?;

        self.record(
            "convert_adjacency",
            DecisionAction::Allow,
            "multigraph adjacency conversion completed",
            0.03,
        );

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
        self.dispatch.resolve(&DispatchRequest {
            operation: "convert_adjacency".to_owned(),
            requested_backend: None,
            required_features: set([feature]),
            risk_probability: 0.08,
            unknown_incompatible_feature: false,
        })?;

        let mut graph = MultiDiGraph::new(self.mode);
        let mut warnings = Vec::new();

        self.populate_from_adjacency(&mut graph, &mut warnings, payload)?;

        self.record(
            "convert_adjacency",
            DecisionAction::Allow,
            "multidigraph adjacency conversion completed",
            0.03,
        );

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
}

#[must_use]
pub fn to_normalized_payload(graph: &Graph) -> GraphSnapshot {
    graph.snapshot()
}

fn set<const N: usize>(values: [&str; N]) -> BTreeSet<String> {
    values.into_iter().map(str::to_owned).collect()
}

impl GraphConverter {
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
    use fnx_classes::AttrMap;
    use fnx_runtime::{CgseValue, CompatibilityMode};
    use std::collections::BTreeMap;

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
}
