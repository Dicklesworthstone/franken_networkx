#![forbid(unsafe_code)]

use fnx_classes::{AttrMap, Graph, GraphError, GraphSnapshot};
use fnx_dispatch::{BackendRegistry, BackendSpec, DispatchError, DispatchRequest};
use fnx_runtime::{
    CompatibilityMode, DecisionAction, DecisionRecord, EvidenceLedger, EvidenceTerm, unix_time_ms,
};
use std::collections::BTreeSet;
use std::fmt;

#[derive(Debug, Clone)]
pub struct ReadWriteReport {
    pub graph: Graph,
    pub warnings: Vec<String>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ReadWriteError {
    Dispatch(DispatchError),
    Graph(GraphError),
    FailClosed {
        operation: &'static str,
        reason: String,
    },
}

impl fmt::Display for ReadWriteError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Dispatch(err) => write!(f, "{err}"),
            Self::Graph(err) => write!(f, "{err}"),
            Self::FailClosed { operation, reason } => {
                write!(f, "readwrite `{operation}` failed closed: {reason}")
            }
        }
    }
}

impl std::error::Error for ReadWriteError {}

impl From<DispatchError> for ReadWriteError {
    fn from(value: DispatchError) -> Self {
        Self::Dispatch(value)
    }
}

impl From<GraphError> for ReadWriteError {
    fn from(value: GraphError) -> Self {
        Self::Graph(value)
    }
}

#[derive(Debug, Clone)]
pub struct EdgeListEngine {
    mode: CompatibilityMode,
    dispatch: BackendRegistry,
    ledger: EvidenceLedger,
}

impl EdgeListEngine {
    #[must_use]
    pub fn new(mode: CompatibilityMode) -> Self {
        let mut dispatch = BackendRegistry::new(mode);
        dispatch.register_backend(BackendSpec {
            name: "native_edgelist".to_owned(),
            priority: 100,
            supported_features: [
                "read_edgelist",
                "write_edgelist",
                "read_json_graph",
                "write_json_graph",
            ]
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

    pub fn write_edgelist(&mut self, graph: &Graph) -> Result<String, ReadWriteError> {
        self.dispatch.resolve(&DispatchRequest {
            operation: "write_edgelist".to_owned(),
            requested_backend: None,
            required_features: set(["write_edgelist"]),
            risk_probability: 0.03,
            unknown_incompatible_feature: false,
        })?;

        let mut lines = Vec::new();
        for edge in graph.edges_ordered() {
            let attrs = encode_attrs(&edge.attrs);
            lines.push(format!("{} {} {}", edge.left, edge.right, attrs));
        }

        self.record(
            "write_edgelist",
            DecisionAction::Allow,
            "edgelist serialization completed",
            0.02,
        );

        Ok(lines.join("\n"))
    }

    pub fn read_edgelist(&mut self, input: &str) -> Result<ReadWriteReport, ReadWriteError> {
        self.dispatch.resolve(&DispatchRequest {
            operation: "read_edgelist".to_owned(),
            requested_backend: None,
            required_features: set(["read_edgelist"]),
            risk_probability: 0.08,
            unknown_incompatible_feature: false,
        })?;

        let mut graph = Graph::new(self.mode);
        let mut warnings = Vec::new();

        for (line_no, raw_line) in input.lines().enumerate() {
            let line = raw_line.trim();
            if line.is_empty() || line.starts_with('#') {
                continue;
            }

            let parts: Vec<&str> = line.split_whitespace().collect();
            if parts.len() < 2 || parts.len() > 3 {
                let warning = format!(
                    "line {} malformed: expected `left right [attrs]`",
                    line_no + 1
                );
                if self.mode == CompatibilityMode::Strict {
                    self.record("read_edgelist", DecisionAction::FailClosed, &warning, 1.0);
                    return Err(ReadWriteError::FailClosed {
                        operation: "read_edgelist",
                        reason: warning,
                    });
                }
                warnings.push(warning.clone());
                self.record("read_edgelist", DecisionAction::FullValidate, &warning, 0.7);
                continue;
            }

            let left = parts[0];
            let right = parts[1];
            if left.is_empty() || right.is_empty() {
                let warning = format!("line {} malformed endpoints", line_no + 1);
                if self.mode == CompatibilityMode::Strict {
                    self.record("read_edgelist", DecisionAction::FailClosed, &warning, 1.0);
                    return Err(ReadWriteError::FailClosed {
                        operation: "read_edgelist",
                        reason: warning,
                    });
                }
                warnings.push(warning.clone());
                self.record("read_edgelist", DecisionAction::FullValidate, &warning, 0.7);
                continue;
            }

            let attrs_encoded = if parts.len() == 3 { parts[2] } else { "-" };
            let attrs = decode_attrs(attrs_encoded, self.mode, &mut warnings, line_no + 1)?;
            graph.add_edge_with_attrs(left.to_owned(), right.to_owned(), attrs)?;
        }

        self.record(
            "read_edgelist",
            DecisionAction::Allow,
            "edgelist parse completed",
            0.04,
        );

        Ok(ReadWriteReport { graph, warnings })
    }

    pub fn write_json_graph(&mut self, graph: &Graph) -> Result<String, ReadWriteError> {
        self.dispatch.resolve(&DispatchRequest {
            operation: "write_json_graph".to_owned(),
            requested_backend: None,
            required_features: set(["write_json_graph"]),
            risk_probability: 0.03,
            unknown_incompatible_feature: false,
        })?;

        let snapshot = graph.snapshot();
        let serialized =
            serde_json::to_string_pretty(&snapshot).map_err(|err| ReadWriteError::FailClosed {
                operation: "write_json_graph",
                reason: format!("json serialization failed: {err}"),
            })?;

        self.record(
            "write_json_graph",
            DecisionAction::Allow,
            "json graph serialization completed",
            0.02,
        );
        Ok(serialized)
    }

    pub fn read_json_graph(&mut self, input: &str) -> Result<ReadWriteReport, ReadWriteError> {
        self.dispatch.resolve(&DispatchRequest {
            operation: "read_json_graph".to_owned(),
            requested_backend: None,
            required_features: set(["read_json_graph"]),
            risk_probability: 0.09,
            unknown_incompatible_feature: false,
        })?;

        let parsed: GraphSnapshot = match serde_json::from_str(input) {
            Ok(value) => value,
            Err(err) => {
                let warning = format!("json parse error: {err}");
                if self.mode == CompatibilityMode::Strict {
                    self.record("read_json_graph", DecisionAction::FailClosed, &warning, 1.0);
                    return Err(ReadWriteError::FailClosed {
                        operation: "read_json_graph",
                        reason: warning,
                    });
                }
                self.record(
                    "read_json_graph",
                    DecisionAction::FullValidate,
                    &warning,
                    0.8,
                );
                return Ok(ReadWriteReport {
                    graph: Graph::new(self.mode),
                    warnings: vec![warning],
                });
            }
        };

        let mut graph = Graph::new(self.mode);
        let mut warnings = Vec::new();
        for node in parsed.nodes {
            if node.is_empty() {
                let warning = "empty node id in json graph".to_owned();
                if self.mode == CompatibilityMode::Strict {
                    self.record("read_json_graph", DecisionAction::FailClosed, &warning, 1.0);
                    return Err(ReadWriteError::FailClosed {
                        operation: "read_json_graph",
                        reason: warning,
                    });
                }
                warnings.push(warning.clone());
                self.record(
                    "read_json_graph",
                    DecisionAction::FullValidate,
                    &warning,
                    0.7,
                );
                continue;
            }
            let _ = graph.add_node(node);
        }
        for edge in parsed.edges {
            if edge.left.is_empty() || edge.right.is_empty() {
                let warning = "empty edge endpoint in json graph".to_owned();
                if self.mode == CompatibilityMode::Strict {
                    self.record("read_json_graph", DecisionAction::FailClosed, &warning, 1.0);
                    return Err(ReadWriteError::FailClosed {
                        operation: "read_json_graph",
                        reason: warning,
                    });
                }
                warnings.push(warning.clone());
                self.record(
                    "read_json_graph",
                    DecisionAction::FullValidate,
                    &warning,
                    0.7,
                );
                continue;
            }
            graph.add_edge_with_attrs(edge.left, edge.right, edge.attrs)?;
        }

        self.record(
            "read_json_graph",
            DecisionAction::Allow,
            "json graph parse completed",
            0.04,
        );

        Ok(ReadWriteReport { graph, warnings })
    }

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
                    -1.0
                } else {
                    2.0
                },
            }],
        });
    }
}

fn encode_attrs(attrs: &AttrMap) -> String {
    if attrs.is_empty() {
        return "-".to_owned();
    }
    attrs
        .iter()
        .map(|(k, v)| format!("{k}={v}"))
        .collect::<Vec<String>>()
        .join(";")
}

fn decode_attrs(
    encoded: &str,
    mode: CompatibilityMode,
    warnings: &mut Vec<String>,
    line_no: usize,
) -> Result<AttrMap, ReadWriteError> {
    if encoded == "-" {
        return Ok(AttrMap::new());
    }

    let mut attrs = AttrMap::new();
    for pair in encoded.split(';') {
        if pair.is_empty() {
            continue;
        }
        let Some((key, value)) = pair.split_once('=') else {
            let warning = format!("line {line_no} malformed attr pair `{pair}`");
            if mode == CompatibilityMode::Strict {
                return Err(ReadWriteError::FailClosed {
                    operation: "read_edgelist",
                    reason: warning,
                });
            }
            warnings.push(warning);
            continue;
        };
        attrs.insert(key.to_owned(), value.to_owned());
    }
    Ok(attrs)
}

fn set<const N: usize>(values: [&str; N]) -> BTreeSet<String> {
    values.into_iter().map(str::to_owned).collect()
}

#[cfg(test)]
mod tests {
    use super::{EdgeListEngine, ReadWriteError};
    use fnx_classes::Graph;

    #[test]
    fn round_trip_is_deterministic() {
        let mut graph = Graph::strict();
        graph.add_edge("a", "b").expect("edge add should succeed");
        graph.add_edge("a", "c").expect("edge add should succeed");

        let mut engine = EdgeListEngine::strict();
        let text = engine
            .write_edgelist(&graph)
            .expect("serialization should succeed");
        let parsed = engine
            .read_edgelist(&text)
            .expect("parse should succeed")
            .graph;

        assert_eq!(graph.snapshot(), parsed.snapshot());
    }

    #[test]
    fn strict_mode_fails_closed_for_malformed_line() {
        let mut engine = EdgeListEngine::strict();
        let err = engine
            .read_edgelist("a\n")
            .expect_err("strict parser should fail closed");
        assert!(matches!(err, ReadWriteError::FailClosed { .. }));
    }

    #[test]
    fn hardened_mode_keeps_valid_lines_with_warnings() {
        let mut engine = EdgeListEngine::hardened();
        let input = "a b weight=1;color=blue\nmalformed\nc d -";
        let report = engine
            .read_edgelist(input)
            .expect("hardened parser should keep valid lines");
        assert!(!report.warnings.is_empty());
        assert_eq!(report.graph.edge_count(), 2);
    }

    #[test]
    fn json_round_trip_is_deterministic() {
        let mut graph = Graph::strict();
        graph.add_edge("a", "b").expect("edge add should succeed");
        graph.add_edge("b", "c").expect("edge add should succeed");
        let mut engine = EdgeListEngine::strict();
        let json = engine
            .write_json_graph(&graph)
            .expect("json write should succeed");
        let parsed = engine
            .read_json_graph(&json)
            .expect("json read should succeed")
            .graph;
        assert_eq!(graph.snapshot(), parsed.snapshot());
    }

    #[test]
    fn strict_mode_fails_closed_for_malformed_json() {
        let mut engine = EdgeListEngine::strict();
        let err = engine
            .read_json_graph("{invalid")
            .expect_err("strict json parsing should fail closed");
        assert!(matches!(err, ReadWriteError::FailClosed { .. }));
    }

    #[test]
    fn hardened_mode_warns_and_recovers_for_malformed_json() {
        let mut engine = EdgeListEngine::hardened();
        let report = engine
            .read_json_graph("{invalid")
            .expect("hardened mode should recover");
        assert!(!report.warnings.is_empty());
        assert_eq!(report.graph.node_count(), 0);
        assert_eq!(report.graph.edge_count(), 0);
    }
}
