#![forbid(unsafe_code)]

use fnx_classes::{AttrMap, Graph, GraphError, GraphSnapshot};
use fnx_dispatch::{BackendRegistry, BackendSpec, DispatchError, DispatchRequest};
use fnx_runtime::{
    CompatibilityMode, DecisionAction, DecisionRecord, EvidenceLedger, EvidenceTerm, unix_time_ms,
};
use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, BTreeSet};
use std::fmt;

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct EdgeRecord {
    pub left: String,
    pub right: String,
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
    pub attrs: AttrMap,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct AdjacencyPayload {
    pub adjacency: BTreeMap<String, Vec<AdjacencyEntry>>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct NormalizedGraphPayload {
    pub mode: CompatibilityMode,
    pub nodes: Vec<String>,
    pub edges: Vec<EdgeRecord>,
}

#[derive(Debug, Clone)]
pub struct ConvertReport {
    pub graph: Graph,
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
    ledger: EvidenceLedger,
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
    pub fn evidence_ledger(&self) -> &EvidenceLedger {
        &self.ledger
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
            graph.add_edge_with_attrs(edge.left.clone(), edge.right.clone(), edge.attrs.clone())?;
        }

        self.record(
            "convert_edge_list",
            DecisionAction::Allow,
            "edge-list conversion completed",
            0.02,
        );

        Ok(ConvertReport {
            graph,
            warnings,
            ledger: self.ledger.clone(),
        })
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
                graph.add_edge_with_attrs(
                    node.clone(),
                    neighbor.to.clone(),
                    neighbor.attrs.clone(),
                )?;
            }
        }

        self.record(
            "convert_adjacency",
            DecisionAction::Allow,
            "adjacency conversion completed",
            0.03,
        );

        Ok(ConvertReport {
            graph,
            warnings,
            ledger: self.ledger.clone(),
        })
    }
}

#[must_use]
pub fn to_normalized_payload(graph: &Graph) -> NormalizedGraphPayload {
    let snapshot: GraphSnapshot = graph.snapshot();
    NormalizedGraphPayload {
        mode: snapshot.mode,
        nodes: snapshot.nodes,
        edges: snapshot
            .edges
            .into_iter()
            .map(|edge| EdgeRecord {
                left: edge.left,
                right: edge.right,
                attrs: edge.attrs,
            })
            .collect(),
    }
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
        self.ledger.record(DecisionRecord {
            ts_unix_ms: unix_time_ms(),
            operation: operation.to_owned(),
            mode: self.mode,
            action,
            incompatibility_probability: incompatibility_probability.clamp(0.0, 1.0),
            rationale: message.to_owned(),
            evidence: vec![EvidenceTerm {
                signal: "message".to_owned(),
                observed_value: message.to_owned(),
                log_likelihood_ratio: if action == DecisionAction::Allow {
                    -1.5
                } else {
                    2.0
                },
            }],
        });
    }
}

#[cfg(test)]
mod tests {
    use super::{
        AdjacencyEntry, AdjacencyPayload, ConvertError, EdgeListPayload, EdgeRecord,
        GraphConverter, to_normalized_payload,
    };
    use fnx_runtime::CompatibilityMode;
    use std::collections::BTreeMap;

    #[test]
    fn edge_list_conversion_is_deterministic() {
        let mut converter = GraphConverter::strict();
        let payload = EdgeListPayload {
            nodes: vec!["a".to_owned(), "b".to_owned(), "c".to_owned()],
            edges: vec![
                EdgeRecord {
                    left: "a".to_owned(),
                    right: "b".to_owned(),
                    attrs: BTreeMap::new(),
                },
                EdgeRecord {
                    left: "a".to_owned(),
                    right: "c".to_owned(),
                    attrs: BTreeMap::new(),
                },
            ],
        };
        let report = converter
            .from_edge_list(&payload)
            .expect("strict conversion should succeed");
        let normalized = to_normalized_payload(&report.graph);
        assert_eq!(normalized.mode, CompatibilityMode::Strict);
        assert_eq!(normalized.nodes, vec!["a", "b", "c"]);
        assert_eq!(normalized.edges.len(), 2);
    }

    #[test]
    fn strict_mode_fails_closed_for_malformed_edge() {
        let mut converter = GraphConverter::strict();
        let payload = EdgeListPayload {
            nodes: vec![],
            edges: vec![EdgeRecord {
                left: "".to_owned(),
                right: "b".to_owned(),
                attrs: BTreeMap::new(),
            }],
        };
        let err = converter
            .from_edge_list(&payload)
            .expect_err("strict mode should fail closed");
        assert!(matches!(err, ConvertError::FailClosed { .. }));
    }

    #[test]
    fn hardened_mode_skips_malformed_and_keeps_good_edges() {
        let mut converter = GraphConverter::hardened();
        let payload = AdjacencyPayload {
            adjacency: BTreeMap::from([
                (
                    "x".to_owned(),
                    vec![
                        AdjacencyEntry {
                            to: "".to_owned(),
                            attrs: BTreeMap::new(),
                        },
                        AdjacencyEntry {
                            to: "y".to_owned(),
                            attrs: BTreeMap::new(),
                        },
                    ],
                ),
                ("y".to_owned(), Vec::new()),
            ]),
        };

        let report = converter
            .from_adjacency(&payload)
            .expect("hardened mode should retain valid edges");
        assert!(!report.warnings.is_empty());
        let normalized = to_normalized_payload(&report.graph);
        assert_eq!(normalized.nodes, vec!["x", "y"]);
        assert_eq!(normalized.edges.len(), 1);
    }
}
