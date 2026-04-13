#![forbid(unsafe_code)]

// Risk probability calibration for dispatch requests:
//
// 0.03 — Well-tested text formats (edgelist, adjacency list).
//         Low incompatibility risk because the format is simple and
//         round-trip tested in conformance fixtures.
//
// 0.08 — Structured formats (JSON graph, GML, GraphML).
//         Moderate risk due to attribute type coercion, XML namespace
//         handling, and directed/undirected auto-detection heuristics.
//
// 0.09 — Complex parse paths (GraphML with attribute keys).
//         Slightly higher than JSON due to XML parser edge cases.
//
// These values feed into decision_theoretic_action() in fnx-dispatch.
// In strict mode, risk_probability < 0.5 results in Allow.
// In hardened mode, the threshold is more conservative.

use fnx_classes::digraph::{DiGraph, DiGraphSnapshot};
use fnx_classes::{AttrMap, Graph, GraphError, GraphSnapshot};
use fnx_dispatch::{BackendRegistry, BackendSpec, DispatchError, DispatchRequest};
use fnx_runtime::{
    CgseValue, CompatibilityMode, DecisionAction, DecisionRecord, EvidenceLedger, EvidenceTerm,
    unix_time_ms,
};
use quick_xml::events::{BytesDecl, BytesEnd, BytesStart, BytesText, Event};
use quick_xml::{Reader, Writer};
use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, BTreeSet};
use std::fmt;
use std::io::Cursor;

#[derive(Debug, Clone)]
pub struct ReadWriteReport {
    pub graph: Graph,
    pub graph_attrs: AttrMap,
    pub warnings: Vec<String>,
}

#[derive(Debug, Clone)]
pub struct DiReadWriteReport {
    pub graph: DiGraph,
    pub graph_attrs: AttrMap,
    pub warnings: Vec<String>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
struct JsonGraphPayload {
    pub mode: CompatibilityMode,
    #[serde(default)]
    pub directed: Option<bool>,
    #[serde(default)]
    pub graph_attrs: AttrMap,
    pub nodes: Vec<String>,
    pub edges: Vec<fnx_classes::EdgeSnapshot>,
}

#[derive(Debug, Clone)]
struct GraphmlKeyDef {
    scope: String,
    name: String,
    attr_type: String,
    default: Option<CgseValue>,
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
                "read_adjlist",
                "write_adjlist",
                "read_json_graph",
                "write_json_graph",
                "read_graphml",
                "write_graphml",
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

    pub fn write_digraph_edgelist(&mut self, graph: &DiGraph) -> Result<String, ReadWriteError> {
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
            "digraph edgelist serialization completed",
            0.02,
        );

        Ok(lines.join("\n"))
    }

    pub fn write_adjlist(&mut self, graph: &Graph) -> Result<String, ReadWriteError> {
        self.dispatch.resolve(&DispatchRequest {
            operation: "write_adjlist".to_owned(),
            requested_backend: None,
            required_features: set(["write_adjlist"]),
            risk_probability: 0.03,
            unknown_incompatible_feature: false,
        })?;

        let mut lines = Vec::new();
        let mut seen = std::collections::HashSet::new();
        for node in graph.nodes_ordered() {
            let mut tokens = Vec::new();
            tokens.push(node.to_owned());
            if let Some(neighbors) = graph.neighbors(node) {
                for neighbor in neighbors {
                    if !seen.contains(neighbor) {
                        tokens.push(neighbor.to_owned());
                    }
                }
            }
            lines.push(tokens.join(" "));
            seen.insert(node.to_owned());
        }

        self.record(
            "write_adjlist",
            DecisionAction::Allow,
            "adjlist serialization completed",
            0.02,
        );

        Ok(lines.join("\n"))
    }

    pub fn write_digraph_adjlist(&mut self, graph: &DiGraph) -> Result<String, ReadWriteError> {
        self.dispatch.resolve(&DispatchRequest {
            operation: "write_adjlist".to_owned(),
            requested_backend: None,
            required_features: set(["write_adjlist"]),
            risk_probability: 0.03,
            unknown_incompatible_feature: false,
        })?;

        let mut lines = Vec::new();
        for node in graph.nodes_ordered() {
            let mut tokens = Vec::new();
            tokens.push(node.to_owned());
            if let Some(successors) = graph.successors(node) {
                for succ in successors {
                    tokens.push(succ.to_owned());
                }
            }
            lines.push(tokens.join(" "));
        }

        self.record(
            "write_adjlist",
            DecisionAction::Allow,
            "digraph adjlist serialization completed",
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
            let line = raw_line
                .split_once('#')
                .map_or(raw_line, |(prefix, _)| prefix)
                .trim();
            if line.is_empty() {
                continue;
            }

            let mut parts = line.split_whitespace();
            let left = parts.next();
            let right = parts.next();
            let attrs = parts.next();
            let extra = parts.next();
            let (left, right) = match (left, right) {
                (Some(l), Some(r)) if extra.is_none() => (l, r),
                _ => {
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
            };

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

            let attrs_encoded = attrs.unwrap_or("-");
            let attrs = decode_attrs(attrs_encoded, self.mode, &mut warnings, line_no + 1)?;
            graph.add_edge_with_attrs(left.to_owned(), right.to_owned(), attrs)?;
        }

        self.record(
            "read_edgelist",
            DecisionAction::Allow,
            "edgelist parse completed",
            0.04,
        );

        Ok(ReadWriteReport {
            graph,
            graph_attrs: AttrMap::new(),
            warnings,
        })
    }

    pub fn read_digraph_edgelist(
        &mut self,
        input: &str,
    ) -> Result<DiReadWriteReport, ReadWriteError> {
        self.dispatch.resolve(&DispatchRequest {
            operation: "read_edgelist".to_owned(),
            requested_backend: None,
            required_features: set(["read_edgelist"]),
            risk_probability: 0.08,
            unknown_incompatible_feature: false,
        })?;

        let mut graph = DiGraph::new(self.mode);
        let mut warnings = Vec::new();

        for (line_no, raw_line) in input.lines().enumerate() {
            let line = raw_line
                .split_once('#')
                .map_or(raw_line, |(prefix, _)| prefix)
                .trim();
            if line.is_empty() {
                continue;
            }

            let mut parts = line.split_whitespace();
            let left = parts.next();
            let right = parts.next();
            let attrs = parts.next();
            let extra = parts.next();
            let (left, right) = match (left, right) {
                (Some(l), Some(r)) if extra.is_none() => (l, r),
                _ => {
                    let warning = format!(
                        "line {} malformed: expected `source target [attrs]`",
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
            };

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

            let attrs_encoded = attrs.unwrap_or("-");
            let attrs = decode_attrs(attrs_encoded, self.mode, &mut warnings, line_no + 1)?;
            graph.add_edge_with_attrs(left.to_owned(), right.to_owned(), attrs)?;
        }

        self.record(
            "read_edgelist",
            DecisionAction::Allow,
            "digraph edgelist parse completed",
            0.04,
        );

        Ok(DiReadWriteReport {
            graph,
            graph_attrs: AttrMap::new(),
            warnings,
        })
    }

    pub fn read_adjlist(&mut self, input: &str) -> Result<ReadWriteReport, ReadWriteError> {
        self.dispatch.resolve(&DispatchRequest {
            operation: "read_adjlist".to_owned(),
            requested_backend: None,
            required_features: set(["read_adjlist"]),
            risk_probability: 0.08,
            unknown_incompatible_feature: false,
        })?;

        let mut graph = Graph::new(self.mode);
        let mut warnings = Vec::new();

        for (line_no, raw_line) in input.lines().enumerate() {
            let line = raw_line
                .split_once('#')
                .map_or(raw_line, |(prefix, _)| prefix)
                .trim();
            if line.is_empty() {
                continue;
            }

            let mut parts = line.split_whitespace();
            let Some(node) = parts.next() else {
                continue;
            };

            if node.is_empty() {
                let warning = format!("line {} malformed: missing node id", line_no + 1);
                if self.mode == CompatibilityMode::Strict {
                    self.record("read_adjlist", DecisionAction::FailClosed, &warning, 1.0);
                    return Err(ReadWriteError::FailClosed {
                        operation: "read_adjlist",
                        reason: warning,
                    });
                }
                warnings.push(warning.clone());
                self.record("read_adjlist", DecisionAction::FullValidate, &warning, 0.7);
                continue;
            }

            let node = node.to_owned();
            let _ = graph.add_node(node.clone());
            for neighbor in parts {
                graph.add_edge(node.clone(), neighbor.to_owned())?;
            }
        }

        self.record(
            "read_adjlist",
            DecisionAction::Allow,
            "adjlist parse completed",
            0.04,
        );

        Ok(ReadWriteReport {
            graph,
            graph_attrs: AttrMap::new(),
            warnings,
        })
    }

    pub fn read_digraph_adjlist(
        &mut self,
        input: &str,
    ) -> Result<DiReadWriteReport, ReadWriteError> {
        self.dispatch.resolve(&DispatchRequest {
            operation: "read_adjlist".to_owned(),
            requested_backend: None,
            required_features: set(["read_adjlist"]),
            risk_probability: 0.08,
            unknown_incompatible_feature: false,
        })?;

        let mut graph = DiGraph::new(self.mode);
        let mut warnings = Vec::new();

        for (line_no, raw_line) in input.lines().enumerate() {
            let line = raw_line
                .split_once('#')
                .map_or(raw_line, |(prefix, _)| prefix)
                .trim();
            if line.is_empty() {
                continue;
            }

            let mut parts = line.split_whitespace();
            let Some(node) = parts.next() else {
                continue;
            };

            if node.is_empty() {
                let warning = format!("line {} malformed: missing node id", line_no + 1);
                if self.mode == CompatibilityMode::Strict {
                    self.record("read_adjlist", DecisionAction::FailClosed, &warning, 1.0);
                    return Err(ReadWriteError::FailClosed {
                        operation: "read_adjlist",
                        reason: warning,
                    });
                }
                warnings.push(warning.clone());
                self.record("read_adjlist", DecisionAction::FullValidate, &warning, 0.7);
                continue;
            }

            let node = node.to_owned();
            let _ = graph.add_node(node.clone());
            for neighbor in parts {
                graph.add_edge(node.clone(), neighbor.to_owned())?;
            }
        }

        self.record(
            "read_adjlist",
            DecisionAction::Allow,
            "digraph adjlist parse completed",
            0.04,
        );

        Ok(DiReadWriteReport {
            graph,
            graph_attrs: AttrMap::new(),
            warnings,
        })
    }

    pub fn write_json_graph(&mut self, graph: &Graph) -> Result<String, ReadWriteError> {
        self.write_json_graph_with_graph_attrs(graph, &AttrMap::new())
    }

    pub fn write_json_graph_with_graph_attrs(
        &mut self,
        graph: &Graph,
        graph_attrs: &AttrMap,
    ) -> Result<String, ReadWriteError> {
        self.dispatch.resolve(&DispatchRequest {
            operation: "write_json_graph".to_owned(),
            requested_backend: None,
            required_features: set(["write_json_graph"]),
            risk_probability: 0.03,
            unknown_incompatible_feature: false,
        })?;

        let snapshot = graph.snapshot();
        let payload = JsonGraphPayload {
            mode: snapshot.mode,
            directed: Some(false),
            graph_attrs: graph_attrs.clone(),
            nodes: snapshot.nodes,
            edges: snapshot.edges,
        };
        let serialized =
            serde_json::to_string_pretty(&payload).map_err(|err| ReadWriteError::FailClosed {
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

    pub fn write_digraph_json_graph(&mut self, graph: &DiGraph) -> Result<String, ReadWriteError> {
        self.write_digraph_json_graph_with_graph_attrs(graph, &AttrMap::new())
    }

    pub fn write_digraph_json_graph_with_graph_attrs(
        &mut self,
        graph: &DiGraph,
        graph_attrs: &AttrMap,
    ) -> Result<String, ReadWriteError> {
        self.dispatch.resolve(&DispatchRequest {
            operation: "write_json_graph".to_owned(),
            requested_backend: None,
            required_features: set(["write_json_graph"]),
            risk_probability: 0.03,
            unknown_incompatible_feature: false,
        })?;

        let snapshot = graph.snapshot();
        let payload = JsonGraphPayload {
            mode: snapshot.mode,
            directed: Some(true),
            graph_attrs: graph_attrs.clone(),
            nodes: snapshot.nodes,
            edges: snapshot.edges,
        };
        let serialized =
            serde_json::to_string_pretty(&payload).map_err(|err| ReadWriteError::FailClosed {
                operation: "write_json_graph",
                reason: format!("json serialization failed: {err}"),
            })?;

        self.record(
            "write_json_graph",
            DecisionAction::Allow,
            "digraph json graph serialization completed",
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

        let parsed: JsonGraphPayload = match serde_json::from_str(input) {
            Ok(value) => value,
            Err(err) => match serde_json::from_str::<GraphSnapshot>(input) {
                Ok(legacy) => JsonGraphPayload {
                    mode: legacy.mode,
                    directed: Some(false),
                    graph_attrs: AttrMap::new(),
                    nodes: legacy.nodes,
                    edges: legacy.edges,
                },
                Err(_) => {
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
                        graph_attrs: AttrMap::new(),
                        warnings: vec![warning],
                    });
                }
            },
        };

        let mut warnings = Vec::new();
        if parsed.directed == Some(true) {
            let warning = "json graph directed=true but read into undirected Graph".to_owned();
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
        }
        let mut graph = Graph::new(self.mode);
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

        Ok(ReadWriteReport {
            graph,
            graph_attrs: parsed.graph_attrs,
            warnings,
        })
    }

    pub fn read_digraph_json_graph(
        &mut self,
        input: &str,
    ) -> Result<DiReadWriteReport, ReadWriteError> {
        self.dispatch.resolve(&DispatchRequest {
            operation: "read_json_graph".to_owned(),
            requested_backend: None,
            required_features: set(["read_json_graph"]),
            risk_probability: 0.09,
            unknown_incompatible_feature: false,
        })?;

        let parsed: JsonGraphPayload = match serde_json::from_str(input) {
            Ok(value) => value,
            Err(err) => match serde_json::from_str::<DiGraphSnapshot>(input) {
                Ok(legacy) => JsonGraphPayload {
                    mode: legacy.mode,
                    directed: Some(true),
                    graph_attrs: AttrMap::new(),
                    nodes: legacy.nodes,
                    edges: legacy.edges,
                },
                Err(_) => {
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
                    return Ok(DiReadWriteReport {
                        graph: DiGraph::new(self.mode),
                        graph_attrs: AttrMap::new(),
                        warnings: vec![warning],
                    });
                }
            },
        };

        let mut warnings = Vec::new();
        if parsed.directed == Some(false) {
            let warning = "json graph directed=false but read into directed DiGraph".to_owned();
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
        }
        let mut graph = DiGraph::new(self.mode);
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
            "digraph json graph parse completed",
            0.04,
        );

        Ok(DiReadWriteReport {
            graph,
            graph_attrs: parsed.graph_attrs,
            warnings,
        })
    }

    pub fn write_graphml(&mut self, graph: &Graph) -> Result<String, ReadWriteError> {
        self.write_graphml_with_graph_attrs(graph, &AttrMap::new())
    }

    pub fn write_graphml_with_graph_attrs(
        &mut self,
        graph: &Graph,
        graph_attrs: &AttrMap,
    ) -> Result<String, ReadWriteError> {
        self.dispatch.resolve(&DispatchRequest {
            operation: "write_graphml".to_owned(),
            requested_backend: None,
            required_features: set(["write_graphml"]),
            risk_probability: 0.03,
            unknown_incompatible_feature: false,
        })?;

        self.write_graphml_impl(graph, graph_attrs, false)
    }

    pub fn write_digraph_graphml(&mut self, graph: &DiGraph) -> Result<String, ReadWriteError> {
        self.write_digraph_graphml_with_graph_attrs(graph, &AttrMap::new())
    }

    pub fn write_digraph_graphml_with_graph_attrs(
        &mut self,
        graph: &DiGraph,
        graph_attrs: &AttrMap,
    ) -> Result<String, ReadWriteError> {
        self.dispatch.resolve(&DispatchRequest {
            operation: "write_graphml".to_owned(),
            requested_backend: None,
            required_features: set(["write_graphml"]),
            risk_probability: 0.03,
            unknown_incompatible_feature: false,
        })?;

        self.write_graphml_impl(graph, graph_attrs, true)
    }

    fn write_graphml_impl<G>(
        &mut self,
        graph: &G,
        graph_attrs: &AttrMap,
        directed: bool,
    ) -> Result<String, ReadWriteError>
    where
        G: GraphLikeRead,
    {
        let mut writer = Writer::new_with_indent(Cursor::new(Vec::new()), b' ', 2);

        writer
            .write_event(Event::Decl(BytesDecl::new("1.0", Some("UTF-8"), None)))
            .map_err(|e| xml_write_err("xml_decl", e))?;

        let mut graphml_start = BytesStart::new("graphml");
        graphml_start.push_attribute(("xmlns", "http://graphml.graphdrawing.org/xmlns"));
        graphml_start.push_attribute(("xmlns:xsi", "http://www.w3.org/2001/XMLSchema-instance"));
        graphml_start.push_attribute((
            "xsi:schemaLocation",
            "http://graphml.graphdrawing.org/xmlns http://graphml.graphdrawing.org/xmlns/1.0/graphml.xsd",
        ));
        writer
            .write_event(Event::Start(graphml_start))
            .map_err(|e| xml_write_err("graphml_start", e))?;

        let mut node_defaults = AttrMap::new();
        let mut edge_defaults = AttrMap::new();
        if let Some(value) = graph_attrs.get("node_default") {
            match value {
                CgseValue::Map(map) => {
                    node_defaults = map.clone();
                }
                _ => {
                    let warning = format!(
                        "graphml node_default must be a map: value={}",
                        value.as_str()
                    );
                    if self.mode == CompatibilityMode::Strict {
                        return Err(ReadWriteError::FailClosed {
                            operation: "write_graphml",
                            reason: warning,
                        });
                    }
                    self.record("write_graphml", DecisionAction::FullValidate, &warning, 0.6);
                }
            }
        }
        if let Some(value) = graph_attrs.get("edge_default") {
            match value {
                CgseValue::Map(map) => {
                    edge_defaults = map.clone();
                }
                _ => {
                    let warning = format!(
                        "graphml edge_default must be a map: value={}",
                        value.as_str()
                    );
                    if self.mode == CompatibilityMode::Strict {
                        return Err(ReadWriteError::FailClosed {
                            operation: "write_graphml",
                            reason: warning,
                        });
                    }
                    self.record("write_graphml", DecisionAction::FullValidate, &warning, 0.6);
                }
            }
        }

        // Collect all distinct attribute keys from graph, nodes, and edges.
        let mut graph_attr_keys = BTreeSet::new();
        let mut node_attr_keys: BTreeSet<(String, GraphmlValueType)> = BTreeSet::new();
        let mut edge_attr_keys: BTreeSet<(String, GraphmlValueType)> = BTreeSet::new();

        for key in graph_attrs.keys() {
            if key == "node_default" || key == "edge_default" {
                continue;
            }
            graph_attr_keys.insert(key.clone());
        }

        let nodes = graph.nodes_ordered();
        for node_id in &nodes {
            if let Some(attrs) = graph.node_attrs(node_id) {
                for (key, value) in attrs {
                    node_attr_keys.insert((key.clone(), GraphmlValueType::from_value(value)));
                }
            }
        }

        for (key, value) in &node_defaults {
            node_attr_keys.insert((key.clone(), GraphmlValueType::from_value(value)));
        }

        let edges = graph.edges_ordered();
        for edge in &edges {
            for (key, value) in &edge.attrs {
                edge_attr_keys.insert((key.clone(), GraphmlValueType::from_value(value)));
            }
        }

        for (key, value) in &edge_defaults {
            edge_attr_keys.insert((key.clone(), GraphmlValueType::from_value(value)));
        }

        // Emit <key> declarations for graph attributes.
        let mut key_counter = 0_usize;
        let mut graph_key_ids: BTreeMap<String, String> = BTreeMap::new();
        for attr_name in &graph_attr_keys {
            let key_id = format!("g{key_counter}");
            key_counter += 1;
            let mut key_elem = BytesStart::new("key");
            key_elem.push_attribute(("id", key_id.as_str()));
            key_elem.push_attribute(("for", "graph"));
            key_elem.push_attribute(("attr.name", attr_name.as_str()));
            key_elem.push_attribute(("attr.type", graphml_attr_type(&graph_attrs[attr_name])));
            writer
                .write_event(Event::Empty(key_elem))
                .map_err(|e| xml_write_err("key_graph", e))?;
            graph_key_ids.insert(attr_name.clone(), key_id);
        }

        // Emit <key> declarations for node attributes.
        let mut node_key_ids: BTreeMap<(String, GraphmlValueType), String> = BTreeMap::new();
        for (attr_name, attr_type) in &node_attr_keys {
            let key_id = format!("n{key_counter}");
            key_counter += 1;
            let mut key_elem = BytesStart::new("key");
            key_elem.push_attribute(("id", key_id.as_str()));
            key_elem.push_attribute(("for", "node"));
            key_elem.push_attribute(("attr.name", attr_name.as_str()));
            key_elem.push_attribute(("attr.type", attr_type.as_str()));
            let default_value = node_defaults.get(attr_name).and_then(|value| {
                if GraphmlValueType::from_value(value) == *attr_type {
                    Some(value)
                } else {
                    None
                }
            });
            if let Some(default_value) = default_value {
                writer
                    .write_event(Event::Start(key_elem))
                    .map_err(|e| xml_write_err("key_node_start", e))?;
                let default_elem = BytesStart::new("default");
                writer
                    .write_event(Event::Start(default_elem))
                    .map_err(|e| xml_write_err("key_node_default_start", e))?;
                let default_text = default_value.as_str();
                writer
                    .write_event(Event::Text(BytesText::new(&default_text)))
                    .map_err(|e| xml_write_err("key_node_default_text", e))?;
                writer
                    .write_event(Event::End(BytesEnd::new("default")))
                    .map_err(|e| xml_write_err("key_node_default_end", e))?;
                writer
                    .write_event(Event::End(BytesEnd::new("key")))
                    .map_err(|e| xml_write_err("key_node_end", e))?;
            } else {
                writer
                    .write_event(Event::Empty(key_elem))
                    .map_err(|e| xml_write_err("key_node", e))?;
            }
            node_key_ids.insert((attr_name.clone(), *attr_type), key_id);
        }

        // Emit <key> declarations for edge attributes.
        let mut edge_key_ids: BTreeMap<(String, GraphmlValueType), String> = BTreeMap::new();
        for (attr_name, attr_type) in &edge_attr_keys {
            let key_id = format!("e{key_counter}");
            key_counter += 1;
            let mut key_elem = BytesStart::new("key");
            key_elem.push_attribute(("id", key_id.as_str()));
            key_elem.push_attribute(("for", "edge"));
            key_elem.push_attribute(("attr.name", attr_name.as_str()));
            key_elem.push_attribute(("attr.type", attr_type.as_str()));
            let default_value = edge_defaults.get(attr_name).and_then(|value| {
                if GraphmlValueType::from_value(value) == *attr_type {
                    Some(value)
                } else {
                    None
                }
            });
            if let Some(default_value) = default_value {
                writer
                    .write_event(Event::Start(key_elem))
                    .map_err(|e| xml_write_err("key_edge_start", e))?;
                let default_elem = BytesStart::new("default");
                writer
                    .write_event(Event::Start(default_elem))
                    .map_err(|e| xml_write_err("key_edge_default_start", e))?;
                let default_text = default_value.as_str();
                writer
                    .write_event(Event::Text(BytesText::new(&default_text)))
                    .map_err(|e| xml_write_err("key_edge_default_text", e))?;
                writer
                    .write_event(Event::End(BytesEnd::new("default")))
                    .map_err(|e| xml_write_err("key_edge_default_end", e))?;
                writer
                    .write_event(Event::End(BytesEnd::new("key")))
                    .map_err(|e| xml_write_err("key_edge_end", e))?;
            } else {
                writer
                    .write_event(Event::Empty(key_elem))
                    .map_err(|e| xml_write_err("key_edge", e))?;
            }
            edge_key_ids.insert((attr_name.clone(), *attr_type), key_id);
        }

        // Emit <graph> element.
        let mut graph_elem = BytesStart::new("graph");
        graph_elem.push_attribute(("id", "G"));
        graph_elem.push_attribute((
            "edgedefault",
            if directed { "directed" } else { "undirected" },
        ));
        writer
            .write_event(Event::Start(graph_elem))
            .map_err(|e| xml_write_err("graph_start", e))?;

        for (attr_name, attr_value) in graph_attrs {
            if attr_name == "node_default" || attr_name == "edge_default" {
                continue;
            }
            if let Some(key_id) = graph_key_ids.get(attr_name) {
                let mut data_elem = BytesStart::new("data");
                data_elem.push_attribute(("key", key_id.as_str()));
                writer
                    .write_event(Event::Start(data_elem))
                    .map_err(|e| xml_write_err("graph_data_start", e))?;
                let attr_text = attr_value.as_str();
                writer
                    .write_event(Event::Text(BytesText::new(&attr_text)))
                    .map_err(|e| xml_write_err("graph_data_text", e))?;
                writer
                    .write_event(Event::End(BytesEnd::new("data")))
                    .map_err(|e| xml_write_err("graph_data_end", e))?;
            }
        }

        // Emit <node> elements.
        for node_id in &nodes {
            let node_attrs = graph.node_attrs(node_id);
            let has_data = node_attrs.is_some_and(|a| !a.is_empty());
            let mut node_elem = BytesStart::new("node");
            node_elem.push_attribute(("id", *node_id));

            if has_data {
                writer
                    .write_event(Event::Start(node_elem))
                    .map_err(|e| xml_write_err("node_start", e))?;
                if let Some(attrs) = node_attrs {
                    for (attr_name, attr_value) in attrs {
                        let attr_type = GraphmlValueType::from_value(attr_value);
                        let key = (attr_name.clone(), attr_type);
                        let key_id =
                            node_key_ids
                                .get(&key)
                                .ok_or_else(|| ReadWriteError::FailClosed {
                                    operation: "write_graphml",
                                    reason: format!(
                                        "graphml node key not declared: name={attr_name} type={:?}",
                                        attr_type
                                    ),
                                })?;
                        let mut data_elem = BytesStart::new("data");
                        data_elem.push_attribute(("key", key_id.as_str()));
                        writer
                            .write_event(Event::Start(data_elem))
                            .map_err(|e| xml_write_err("data_start", e))?;
                        let attr_text = attr_value.as_str();
                        writer
                            .write_event(Event::Text(BytesText::new(&attr_text)))
                            .map_err(|e| xml_write_err("data_text", e))?;
                        writer
                            .write_event(Event::End(BytesEnd::new("data")))
                            .map_err(|e| xml_write_err("data_end", e))?;
                    }
                }
                writer
                    .write_event(Event::End(BytesEnd::new("node")))
                    .map_err(|e| xml_write_err("node_end", e))?;
            } else {
                writer
                    .write_event(Event::Empty(node_elem))
                    .map_err(|e| xml_write_err("node_empty", e))?;
            }
        }

        // Emit <edge> elements.
        for edge in &edges {
            let has_data = !edge.attrs.is_empty();
            let mut edge_elem = BytesStart::new("edge");
            edge_elem.push_attribute(("source", edge.left.as_str()));
            edge_elem.push_attribute(("target", edge.right.as_str()));

            if has_data {
                writer
                    .write_event(Event::Start(edge_elem))
                    .map_err(|e| xml_write_err("edge_start", e))?;
                for (attr_name, attr_value) in &edge.attrs {
                    let attr_type = GraphmlValueType::from_value(attr_value);
                    let key = (attr_name.clone(), attr_type);
                    let key_id =
                        edge_key_ids
                            .get(&key)
                            .ok_or_else(|| ReadWriteError::FailClosed {
                                operation: "write_graphml",
                                reason: format!(
                                    "graphml edge key not declared: name={attr_name} type={:?}",
                                    attr_type
                                ),
                            })?;
                    let mut data_elem = BytesStart::new("data");
                    data_elem.push_attribute(("key", key_id.as_str()));
                    writer
                        .write_event(Event::Start(data_elem))
                        .map_err(|e| xml_write_err("data_start", e))?;
                    let attr_text = attr_value.as_str();
                    writer
                        .write_event(Event::Text(BytesText::new(&attr_text)))
                        .map_err(|e| xml_write_err("data_text", e))?;
                    writer
                        .write_event(Event::End(BytesEnd::new("data")))
                        .map_err(|e| xml_write_err("data_end", e))?;
                }
                writer
                    .write_event(Event::End(BytesEnd::new("edge")))
                    .map_err(|e| xml_write_err("edge_end", e))?;
            } else {
                writer
                    .write_event(Event::Empty(edge_elem))
                    .map_err(|e| xml_write_err("edge_empty", e))?;
            }
        }

        writer
            .write_event(Event::End(BytesEnd::new("graph")))
            .map_err(|e| xml_write_err("graph_end", e))?;
        writer
            .write_event(Event::End(BytesEnd::new("graphml")))
            .map_err(|e| xml_write_err("graphml_end", e))?;

        let result = writer.into_inner().into_inner();
        let output = String::from_utf8(result).map_err(|e| ReadWriteError::FailClosed {
            operation: "write_graphml",
            reason: format!("UTF-8 encoding error: {e}"),
        })?;

        self.record(
            "write_graphml",
            DecisionAction::Allow,
            "graphml serialization completed",
            0.02,
        );

        Ok(output)
    }

    pub fn read_graphml(&mut self, input: &str) -> Result<ReadWriteReport, ReadWriteError> {
        self.dispatch.resolve(&DispatchRequest {
            operation: "read_graphml".to_owned(),
            requested_backend: None,
            required_features: set(["read_graphml"]),
            risk_probability: 0.10,
            unknown_incompatible_feature: false,
        })?;

        let mut graph = Graph::new(self.mode);
        let mut graph_attrs = AttrMap::new();
        let mut warnings = Vec::new();
        let directed = self.graphml_directed_flag(input)?;
        if let Some(warning) = directed.warning.as_ref() {
            warnings.push(warning.clone());
        }

        if directed.declared && directed.value {
            let warning = "graphml declares directed but read into undirected Graph".to_owned();
            if self.mode == CompatibilityMode::Strict {
                self.record("read_graphml", DecisionAction::FailClosed, &warning, 1.0);
                return Err(ReadWriteError::FailClosed {
                    operation: "read_graphml",
                    reason: warning,
                });
            }
            warnings.push(warning.clone());
            self.record("read_graphml", DecisionAction::FullValidate, &warning, 0.7);
        }

        self.read_graphml_into(&mut graph, &mut graph_attrs, &mut warnings, input)?;

        self.record(
            "read_graphml",
            DecisionAction::Allow,
            "graphml parse completed",
            0.04,
        );

        Ok(ReadWriteReport {
            graph,
            graph_attrs,
            warnings,
        })
    }

    pub fn graphml_declares_directed(&mut self, input: &str) -> Result<bool, ReadWriteError> {
        self.graphml_directed_flag(input).map(|flag| flag.value)
    }

    fn graphml_directed_flag(
        &mut self,
        input: &str,
    ) -> Result<GraphmlDirectedFlag, ReadWriteError> {
        let mut reader = Reader::from_str(input);
        reader.config_mut().trim_text(true);
        let mut buffer = Vec::new();

        loop {
            match reader.read_event_into(&mut buffer) {
                Ok(Event::Start(element)) | Ok(Event::Empty(element))
                    if xml_local_name(element.name().as_ref()) == b"graph" =>
                {
                    let mut declared = false;
                    let mut value = false;
                    for attr in element.attributes() {
                        let attr = match attr {
                            Ok(attr) => attr,
                            Err(err) => {
                                let warning = format!("graphml attribute parse error: {err}");
                                if self.mode == CompatibilityMode::Strict {
                                    self.record(
                                        "read_graphml",
                                        DecisionAction::FailClosed,
                                        &warning,
                                        1.0,
                                    );
                                    return Err(ReadWriteError::FailClosed {
                                        operation: "read_graphml",
                                        reason: warning,
                                    });
                                }
                                self.record(
                                    "read_graphml",
                                    DecisionAction::FullValidate,
                                    &warning,
                                    0.7,
                                );
                                return Ok(GraphmlDirectedFlag {
                                    declared: false,
                                    value: false,
                                    warning: Some(warning),
                                });
                            }
                        };
                        if xml_local_name(attr.key.as_ref()) == b"edgedefault" {
                            declared = true;
                            match parse_graphml_edgedefault_value(attr.value.as_ref()) {
                                Some(flag) => {
                                    value = flag;
                                    break;
                                }
                                None => {
                                    let warning = format!(
                                        "graphml edgedefault invalid: value={:?}",
                                        String::from_utf8_lossy(attr.value.as_ref())
                                    );
                                    if self.mode == CompatibilityMode::Strict {
                                        self.record(
                                            "read_graphml",
                                            DecisionAction::FailClosed,
                                            &warning,
                                            1.0,
                                        );
                                        return Err(ReadWriteError::FailClosed {
                                            operation: "read_graphml",
                                            reason: warning,
                                        });
                                    }
                                    self.record(
                                        "read_graphml",
                                        DecisionAction::FullValidate,
                                        &warning,
                                        0.7,
                                    );
                                    return Ok(GraphmlDirectedFlag {
                                        declared: false,
                                        value: false,
                                        warning: Some(warning),
                                    });
                                }
                            }
                        }
                    }
                    if !declared {
                        let warning = "graphml missing edgedefault attribute".to_owned();
                        if self.mode == CompatibilityMode::Strict {
                            self.record("read_graphml", DecisionAction::FailClosed, &warning, 1.0);
                            return Err(ReadWriteError::FailClosed {
                                operation: "read_graphml",
                                reason: warning,
                            });
                        }
                        self.record("read_graphml", DecisionAction::FullValidate, &warning, 0.7);
                        return Ok(GraphmlDirectedFlag {
                            declared: false,
                            value: false,
                            warning: Some(warning),
                        });
                    }
                    return Ok(GraphmlDirectedFlag {
                        declared,
                        value,
                        warning: None,
                    });
                }
                Ok(Event::Eof) => {
                    return Ok(GraphmlDirectedFlag {
                        declared: false,
                        value: false,
                        warning: None,
                    });
                }
                Err(err) => {
                    let warning = format!("graphml directed detection failed: {err}");
                    if self.mode == CompatibilityMode::Strict {
                        self.record("read_graphml", DecisionAction::FailClosed, &warning, 1.0);
                        return Err(ReadWriteError::FailClosed {
                            operation: "read_graphml",
                            reason: warning,
                        });
                    }
                    self.record("read_graphml", DecisionAction::FullValidate, &warning, 0.7);
                    return Ok(GraphmlDirectedFlag {
                        declared: false,
                        value: false,
                        warning: Some(warning),
                    });
                }
                _ => {}
            }
            buffer.clear();
        }
    }

    pub fn read_digraph_graphml(
        &mut self,
        input: &str,
    ) -> Result<DiReadWriteReport, ReadWriteError> {
        self.dispatch.resolve(&DispatchRequest {
            operation: "read_graphml".to_owned(),
            requested_backend: None,
            required_features: set(["read_graphml"]),
            risk_probability: 0.10,
            unknown_incompatible_feature: false,
        })?;

        let mut graph = DiGraph::new(self.mode);
        let mut graph_attrs = AttrMap::new();
        let mut warnings = Vec::new();
        let directed = self.graphml_directed_flag(input)?;
        if let Some(warning) = directed.warning.as_ref() {
            warnings.push(warning.clone());
        }

        if directed.declared && !directed.value {
            let warning = "graphml declares undirected but read into directed DiGraph".to_owned();
            if self.mode == CompatibilityMode::Strict {
                self.record("read_graphml", DecisionAction::FailClosed, &warning, 1.0);
                return Err(ReadWriteError::FailClosed {
                    operation: "read_graphml",
                    reason: warning,
                });
            }
            warnings.push(warning.clone());
            self.record("read_graphml", DecisionAction::FullValidate, &warning, 0.7);
        }

        self.read_graphml_into(&mut graph, &mut graph_attrs, &mut warnings, input)?;

        self.record(
            "read_graphml",
            DecisionAction::Allow,
            "digraph graphml parse completed",
            0.04,
        );

        Ok(DiReadWriteReport {
            graph,
            graph_attrs,
            warnings,
        })
    }

    fn read_graphml_into<G>(
        &mut self,
        graph: &mut G,
        graph_attrs: &mut AttrMap,
        warnings: &mut Vec<String>,
        input: &str,
    ) -> Result<(), ReadWriteError>
    where
        G: GraphLike,
    {
        let mut key_registry: BTreeMap<String, GraphmlKeyDef> = BTreeMap::new();
        let mut reader = Reader::from_str(input);
        reader.config_mut().trim_text(true);

        let mut in_graph = false;
        let mut current_key_id: Option<String> = None;
        let mut current_key_default_key: Option<String> = None;
        let mut current_key_default_text = String::new();
        let mut current_node: Option<String> = None;
        let mut current_edge: Option<(String, String)> = None;
        let mut current_data_key: Option<String> = None;
        let mut current_data_text = String::new();
        let mut current_data_has_children = false;
        let mut current_edge_directed: Option<bool> = None;
        let mut current_edge_skip = false;

        let mut graphml_node_defaults: AttrMap = AttrMap::new();
        let mut graphml_edge_defaults: AttrMap = AttrMap::new();
        let mut graphml_graph_defaults: AttrMap = AttrMap::new();

        let mut pending_graph_attrs: AttrMap = AttrMap::new();
        let mut pending_node_attrs: AttrMap = AttrMap::new();
        let mut pending_edge_attrs: AttrMap = AttrMap::new();

        loop {
            match reader.read_event() {
                Ok(Event::Start(ref e)) => {
                    let name = e.name();
                    let local = xml_local_name(name.as_ref());
                    if local == b"data" {
                        current_data_has_children = false;
                    } else if current_data_key.is_some() {
                        current_data_has_children = true;
                        current_data_text.clear();
                    }
                    self.handle_graphml_start_element(
                        e,
                        graph,
                        warnings,
                        &mut key_registry,
                        &mut in_graph,
                        &mut current_key_id,
                        &mut current_key_default_key,
                        &mut current_key_default_text,
                        &graphml_node_defaults,
                        &graphml_edge_defaults,
                        &mut current_node,
                        &mut current_edge,
                        &mut current_edge_directed,
                        &mut current_edge_skip,
                        &mut current_data_key,
                        &mut current_data_text,
                        &mut pending_graph_attrs,
                        &mut pending_node_attrs,
                        &mut pending_edge_attrs,
                    )?;
                }
                Ok(Event::Empty(ref e)) => {
                    let name = e.name();
                    let local = xml_local_name(name.as_ref());
                    if local == b"data" {
                        current_data_has_children = false;
                    } else if current_data_key.is_some() {
                        current_data_has_children = true;
                        current_data_text.clear();
                    }
                    self.handle_graphml_start_element(
                        e,
                        graph,
                        warnings,
                        &mut key_registry,
                        &mut in_graph,
                        &mut current_key_id,
                        &mut current_key_default_key,
                        &mut current_key_default_text,
                        &graphml_node_defaults,
                        &graphml_edge_defaults,
                        &mut current_node,
                        &mut current_edge,
                        &mut current_edge_directed,
                        &mut current_edge_skip,
                        &mut current_data_key,
                        &mut current_data_text,
                        &mut pending_graph_attrs,
                        &mut pending_node_attrs,
                        &mut pending_edge_attrs,
                    )?;
                    self.handle_graphml_end_element(
                        xml_local_name(e.name().as_ref()),
                        graph,
                        warnings,
                        &mut in_graph,
                        &mut current_key_id,
                        &mut current_key_default_key,
                        &mut current_key_default_text,
                        &mut current_node,
                        &mut current_edge,
                        &mut current_edge_directed,
                        &mut current_edge_skip,
                        &mut current_data_key,
                        &mut current_data_text,
                        &mut current_data_has_children,
                        &mut graphml_node_defaults,
                        &mut graphml_edge_defaults,
                        &mut graphml_graph_defaults,
                        &mut pending_graph_attrs,
                        &mut pending_node_attrs,
                        &mut pending_edge_attrs,
                        graph_attrs,
                        &mut key_registry,
                    )?;
                }
                Ok(Event::Text(ref e))
                    if current_data_key.is_some() && !current_data_has_children =>
                {
                    match e.unescape() {
                        Ok(text) => current_data_text.push_str(&text),
                        Err(err) => {
                            let warning = format!("graphml data text unescape error: {err}");
                            if self.mode == CompatibilityMode::Strict {
                                self.record(
                                    "read_graphml",
                                    DecisionAction::FailClosed,
                                    &warning,
                                    1.0,
                                );
                                return Err(ReadWriteError::FailClosed {
                                    operation: "read_graphml",
                                    reason: warning,
                                });
                            }
                            warnings.push(warning.clone());
                            self.record(
                                "read_graphml",
                                DecisionAction::FullValidate,
                                &warning,
                                0.8,
                            );
                            current_data_text.clear();
                            current_data_key = None;
                        }
                    }
                }
                Ok(Event::Text(ref e)) if current_key_default_key.is_some() => match e.unescape() {
                    Ok(text) => current_key_default_text.push_str(&text),
                    Err(err) => {
                        let warning = format!("graphml default text unescape error: {err}");
                        if self.mode == CompatibilityMode::Strict {
                            self.record("read_graphml", DecisionAction::FailClosed, &warning, 1.0);
                            return Err(ReadWriteError::FailClosed {
                                operation: "read_graphml",
                                reason: warning,
                            });
                        }
                        warnings.push(warning.clone());
                        self.record("read_graphml", DecisionAction::FullValidate, &warning, 0.8);
                        current_key_default_text.clear();
                        current_key_default_key = None;
                    }
                },
                Ok(Event::End(ref e)) => {
                    self.handle_graphml_end_element(
                        xml_local_name(e.name().as_ref()),
                        graph,
                        warnings,
                        &mut in_graph,
                        &mut current_key_id,
                        &mut current_key_default_key,
                        &mut current_key_default_text,
                        &mut current_node,
                        &mut current_edge,
                        &mut current_edge_directed,
                        &mut current_edge_skip,
                        &mut current_data_key,
                        &mut current_data_text,
                        &mut current_data_has_children,
                        &mut graphml_node_defaults,
                        &mut graphml_edge_defaults,
                        &mut graphml_graph_defaults,
                        &mut pending_graph_attrs,
                        &mut pending_node_attrs,
                        &mut pending_edge_attrs,
                        graph_attrs,
                        &mut key_registry,
                    )?;
                }
                Ok(Event::Eof) => break,
                Err(e) => {
                    let warning = format!("graphml xml parse error: {e}");
                    if self.mode == CompatibilityMode::Strict {
                        self.record("read_graphml", DecisionAction::FailClosed, &warning, 1.0);
                        return Err(ReadWriteError::FailClosed {
                            operation: "read_graphml",
                            reason: warning,
                        });
                    }
                    warnings.push(warning.clone());
                    self.record("read_graphml", DecisionAction::FullValidate, &warning, 0.8);
                    break;
                }
                _ => {}
            }
        }
        graph.apply_node_defaults(&graphml_node_defaults);
        graph.apply_edge_defaults(&graphml_edge_defaults);
        for (key, value) in &graphml_graph_defaults {
            graph_attrs
                .entry(key.clone())
                .or_insert_with(|| value.clone());
        }

        let mut combined_graph_attrs = AttrMap::new();
        combined_graph_attrs.insert(
            "node_default".to_owned(),
            CgseValue::Map(std::mem::take(&mut graphml_node_defaults)),
        );
        combined_graph_attrs.insert(
            "edge_default".to_owned(),
            CgseValue::Map(std::mem::take(&mut graphml_edge_defaults)),
        );
        combined_graph_attrs.extend(std::mem::take(graph_attrs));
        *graph_attrs = combined_graph_attrs;
        Ok(())
    }

    #[allow(clippy::too_many_arguments)]
    fn handle_graphml_start_element<G>(
        &mut self,
        e: &BytesStart<'_>,
        graph: &mut G,
        warnings: &mut Vec<String>,
        key_registry: &mut BTreeMap<String, GraphmlKeyDef>,
        in_graph: &mut bool,
        current_key_id: &mut Option<String>,
        current_key_default_key: &mut Option<String>,
        current_key_default_text: &mut String,
        graphml_node_defaults: &AttrMap,
        graphml_edge_defaults: &AttrMap,
        current_node: &mut Option<String>,
        current_edge: &mut Option<(String, String)>,
        current_edge_directed: &mut Option<bool>,
        current_edge_skip: &mut bool,
        current_data_key: &mut Option<String>,
        current_data_text: &mut String,
        pending_graph_attrs: &mut AttrMap,
        pending_node_attrs: &mut AttrMap,
        pending_edge_attrs: &mut AttrMap,
    ) -> Result<(), ReadWriteError>
    where
        G: GraphLike,
    {
        let tag_name = e.name();
        let local = xml_local_name(tag_name.as_ref());
        match local {
            b"key" => {
                let mut key_id = String::new();
                let mut for_scope = String::new();
                let mut attr_name = String::new();
                let mut attr_type = String::new();
                let mut yfiles_type = String::new();
                for attr in e.attributes() {
                    let attr = match attr {
                        Ok(attr) => attr,
                        Err(err) => {
                            let warning = format!("graphml key attribute parse error: {err}");
                            if self.mode == CompatibilityMode::Strict {
                                self.record(
                                    "read_graphml",
                                    DecisionAction::FailClosed,
                                    &warning,
                                    1.0,
                                );
                                return Err(ReadWriteError::FailClosed {
                                    operation: "read_graphml",
                                    reason: warning,
                                });
                            }
                            warnings.push(warning.clone());
                            self.record(
                                "read_graphml",
                                DecisionAction::FullValidate,
                                &warning,
                                0.7,
                            );
                            return Ok(());
                        }
                    };
                    match xml_local_name(attr.key.as_ref()) {
                        b"id" => {
                            key_id = String::from_utf8_lossy(&attr.value).into_owned();
                        }
                        b"for" => {
                            for_scope = String::from_utf8_lossy(&attr.value).into_owned();
                        }
                        b"attr.name" => {
                            attr_name = String::from_utf8_lossy(&attr.value).into_owned();
                        }
                        b"attr.type" => {
                            attr_type = String::from_utf8_lossy(&attr.value).into_owned();
                        }
                        b"yfiles.type" => {
                            yfiles_type = String::from_utf8_lossy(&attr.value).into_owned();
                        }
                        _ => {}
                    }
                }
                if attr_name.is_empty() && !yfiles_type.is_empty() {
                    attr_name = yfiles_type;
                    if attr_type.is_empty() {
                        attr_type = "string".to_owned();
                    }
                }
                if key_id.is_empty() {
                    let warning = "graphml key missing id attribute".to_owned();
                    if self.mode == CompatibilityMode::Strict {
                        self.record("read_graphml", DecisionAction::FailClosed, &warning, 1.0);
                        return Err(ReadWriteError::FailClosed {
                            operation: "read_graphml",
                            reason: warning,
                        });
                    }
                    warnings.push(warning.clone());
                    self.record("read_graphml", DecisionAction::FullValidate, &warning, 0.7);
                    return Ok(());
                }
                if attr_name.is_empty() {
                    let warning = format!("graphml key missing attr.name: id={key_id}");
                    if self.mode == CompatibilityMode::Strict {
                        self.record("read_graphml", DecisionAction::FailClosed, &warning, 1.0);
                        return Err(ReadWriteError::FailClosed {
                            operation: "read_graphml",
                            reason: warning,
                        });
                    }
                    warnings.push(warning.clone());
                    self.record("read_graphml", DecisionAction::FullValidate, &warning, 0.7);
                    return Ok(());
                }
                if attr_type.trim().is_empty() {
                    let warning =
                        format!("graphml key missing attr.type: id={key_id} name={attr_name}");
                    warnings.push(warning.clone());
                    self.record("read_graphml", DecisionAction::FullValidate, &warning, 0.6);
                    attr_type = "string".to_owned();
                }
                key_registry.insert(
                    key_id.clone(),
                    GraphmlKeyDef {
                        scope: for_scope,
                        name: attr_name,
                        attr_type,
                        default: None,
                    },
                );
                *current_key_id = Some(key_id);
                *current_key_default_key = None;
                current_key_default_text.clear();
            }
            b"default" => {
                if let Some(key_id) = current_key_id.clone() {
                    *current_key_default_key = Some(key_id);
                    current_key_default_text.clear();
                }
            }
            b"hyperedge" => {
                let warning = "graphml reader does not support hyperedges".to_owned();
                if self.mode == CompatibilityMode::Strict {
                    self.record("read_graphml", DecisionAction::FailClosed, &warning, 1.0);
                    return Err(ReadWriteError::FailClosed {
                        operation: "read_graphml",
                        reason: warning,
                    });
                }
                warnings.push(warning.clone());
                self.record("read_graphml", DecisionAction::FullValidate, &warning, 0.7);
            }
            b"graph" => {
                *in_graph = true;
                pending_graph_attrs.clear();
            }
            b"node" if *in_graph => {
                let mut node_id = String::new();
                for attr in e.attributes() {
                    let attr = match attr {
                        Ok(attr) => attr,
                        Err(err) => {
                            let warning = format!("graphml node attribute parse error: {err}");
                            if self.mode == CompatibilityMode::Strict {
                                self.record(
                                    "read_graphml",
                                    DecisionAction::FailClosed,
                                    &warning,
                                    1.0,
                                );
                                return Err(ReadWriteError::FailClosed {
                                    operation: "read_graphml",
                                    reason: warning,
                                });
                            }
                            warnings.push(warning.clone());
                            self.record(
                                "read_graphml",
                                DecisionAction::FullValidate,
                                &warning,
                                0.7,
                            );
                            return Ok(());
                        }
                    };
                    if xml_local_name(attr.key.as_ref()) == b"id" {
                        node_id = String::from_utf8_lossy(&attr.value).into_owned();
                    }
                }
                if node_id.is_empty() {
                    let warning = "graphml node missing id attribute".to_owned();
                    if self.mode == CompatibilityMode::Strict {
                        self.record("read_graphml", DecisionAction::FailClosed, &warning, 1.0);
                        return Err(ReadWriteError::FailClosed {
                            operation: "read_graphml",
                            reason: warning,
                        });
                    }
                    warnings.push(warning.clone());
                    self.record("read_graphml", DecisionAction::FullValidate, &warning, 0.7);
                    return Ok(());
                }
                let _ = graph.add_node(node_id.clone());
                *current_node = Some(node_id);
                *pending_node_attrs = graphml_node_defaults.clone();
            }
            b"edge" if *in_graph => {
                let mut source = String::new();
                let mut target = String::new();
                let mut edge_id_attr: Option<String> = None;
                *current_edge_directed = None;
                *current_edge_skip = false;
                for attr in e.attributes() {
                    let attr = match attr {
                        Ok(attr) => attr,
                        Err(err) => {
                            let warning = format!("graphml edge attribute parse error: {err}");
                            if self.mode == CompatibilityMode::Strict {
                                self.record(
                                    "read_graphml",
                                    DecisionAction::FailClosed,
                                    &warning,
                                    1.0,
                                );
                                return Err(ReadWriteError::FailClosed {
                                    operation: "read_graphml",
                                    reason: warning,
                                });
                            }
                            warnings.push(warning.clone());
                            self.record(
                                "read_graphml",
                                DecisionAction::FullValidate,
                                &warning,
                                0.7,
                            );
                            return Ok(());
                        }
                    };
                    match xml_local_name(attr.key.as_ref()) {
                        b"source" => {
                            source = String::from_utf8_lossy(&attr.value).into_owned();
                        }
                        b"target" => {
                            target = String::from_utf8_lossy(&attr.value).into_owned();
                        }
                        b"directed" => {
                            let directed_value = parse_graphml_directed_value(attr.value.as_ref());
                            match directed_value {
                                Some(parsed) => {
                                    *current_edge_directed = Some(parsed);
                                }
                                None => {
                                    let warning = format!(
                                        "graphml edge directed attribute invalid: value={:?}",
                                        String::from_utf8_lossy(&attr.value)
                                    );
                                    if self.mode == CompatibilityMode::Strict {
                                        self.record(
                                            "read_graphml",
                                            DecisionAction::FailClosed,
                                            &warning,
                                            1.0,
                                        );
                                        return Err(ReadWriteError::FailClosed {
                                            operation: "read_graphml",
                                            reason: warning,
                                        });
                                    }
                                    warnings.push(warning.clone());
                                    self.record(
                                        "read_graphml",
                                        DecisionAction::FullValidate,
                                        &warning,
                                        0.7,
                                    );
                                }
                            }
                        }
                        b"id" => {
                            edge_id_attr = Some(String::from_utf8_lossy(&attr.value).into_owned());
                        }
                        _ => {}
                    }
                }
                if source.is_empty() || target.is_empty() {
                    let warning = format!(
                        "graphml edge missing source/target: source={source:?} target={target:?}"
                    );
                    if self.mode == CompatibilityMode::Strict {
                        self.record("read_graphml", DecisionAction::FailClosed, &warning, 1.0);
                        return Err(ReadWriteError::FailClosed {
                            operation: "read_graphml",
                            reason: warning,
                        });
                    }
                    warnings.push(warning.clone());
                    self.record("read_graphml", DecisionAction::FullValidate, &warning, 0.7);
                    return Ok(());
                }
                if let Some(edge_directed) = *current_edge_directed
                    && edge_directed != graph.is_directed()
                {
                    let warning = format!(
                        "graphml edge directed mismatch: edge_directed={edge_directed} graph_directed={}",
                        graph.is_directed()
                    );
                    if self.mode == CompatibilityMode::Strict {
                        self.record("read_graphml", DecisionAction::FailClosed, &warning, 1.0);
                        return Err(ReadWriteError::FailClosed {
                            operation: "read_graphml",
                            reason: warning,
                        });
                    }
                    warnings.push(warning.clone());
                    self.record("read_graphml", DecisionAction::FullValidate, &warning, 0.7);
                    *current_edge_skip = true;
                }
                if graph.has_edge(&source, &target) {
                    let warning = format!(
                        "graphml multiedge not supported: source={source:?} target={target:?}"
                    );
                    if self.mode == CompatibilityMode::Strict {
                        self.record("read_graphml", DecisionAction::FailClosed, &warning, 1.0);
                        return Err(ReadWriteError::FailClosed {
                            operation: "read_graphml",
                            reason: warning,
                        });
                    }
                    warnings.push(warning.clone());
                    self.record("read_graphml", DecisionAction::FullValidate, &warning, 0.7);
                    *current_edge_skip = true;
                }
                *current_edge = Some((source, target));
                *pending_edge_attrs = graphml_edge_defaults.clone();
                if let Some(edge_id) = edge_id_attr {
                    pending_edge_attrs.insert("id".to_owned(), CgseValue::parse_relaxed(&edge_id));
                }
            }
            b"data" => {
                current_data_text.clear();
                *current_data_key = None;
                for attr in e.attributes() {
                    let attr = match attr {
                        Ok(attr) => attr,
                        Err(err) => {
                            let warning = format!("graphml data attribute parse error: {err}");
                            if self.mode == CompatibilityMode::Strict {
                                self.record(
                                    "read_graphml",
                                    DecisionAction::FailClosed,
                                    &warning,
                                    1.0,
                                );
                                return Err(ReadWriteError::FailClosed {
                                    operation: "read_graphml",
                                    reason: warning,
                                });
                            }
                            warnings.push(warning.clone());
                            self.record(
                                "read_graphml",
                                DecisionAction::FullValidate,
                                &warning,
                                0.7,
                            );
                            return Ok(());
                        }
                    };
                    if xml_local_name(attr.key.as_ref()) == b"key" {
                        *current_data_key = Some(String::from_utf8_lossy(&attr.value).into_owned());
                    }
                }
                if current_data_key.is_none() {
                    let warning = "graphml data missing key attribute".to_owned();
                    if self.mode == CompatibilityMode::Strict {
                        self.record("read_graphml", DecisionAction::FailClosed, &warning, 1.0);
                        return Err(ReadWriteError::FailClosed {
                            operation: "read_graphml",
                            reason: warning,
                        });
                    }
                    warnings.push(warning.clone());
                    self.record("read_graphml", DecisionAction::FullValidate, &warning, 0.7);
                }
            }
            _ => {}
        }
        Ok(())
    }

    #[allow(clippy::too_many_arguments)]
    fn handle_graphml_end_element<G>(
        &mut self,
        local: &[u8],
        graph: &mut G,
        warnings: &mut Vec<String>,
        in_graph: &mut bool,
        current_key_id: &mut Option<String>,
        current_key_default_key: &mut Option<String>,
        current_key_default_text: &mut String,
        current_node: &mut Option<String>,
        current_edge: &mut Option<(String, String)>,
        current_edge_directed: &mut Option<bool>,
        current_edge_skip: &mut bool,
        current_data_key: &mut Option<String>,
        current_data_text: &mut String,
        current_data_has_children: &mut bool,
        graphml_node_defaults: &mut AttrMap,
        graphml_edge_defaults: &mut AttrMap,
        graphml_graph_defaults: &mut AttrMap,
        pending_graph_attrs: &mut AttrMap,
        pending_node_attrs: &mut AttrMap,
        pending_edge_attrs: &mut AttrMap,
        graph_attrs: &mut AttrMap,
        key_registry: &mut BTreeMap<String, GraphmlKeyDef>,
    ) -> Result<(), ReadWriteError>
    where
        G: GraphLike,
    {
        match local {
            b"data" => {
                if *current_data_has_children {
                    let warning =
                        "graphml data contains nested elements (yfiles extensions not supported)"
                            .to_owned();
                    if self.mode == CompatibilityMode::Strict {
                        self.record("read_graphml", DecisionAction::FailClosed, &warning, 1.0);
                        return Err(ReadWriteError::FailClosed {
                            operation: "read_graphml",
                            reason: warning,
                        });
                    }
                    warnings.push(warning.clone());
                    self.record("read_graphml", DecisionAction::FullValidate, &warning, 0.7);
                    current_data_text.clear();
                    current_data_key.take();
                    *current_data_has_children = false;
                    return Ok(());
                }
                if let Some(key_id) = current_data_key.take() {
                    let (scope, attr_name, attr_type) = match key_registry.get(&key_id) {
                        Some(entry) => (
                            entry.scope.clone(),
                            entry.name.clone(),
                            entry.attr_type.clone(),
                        ),
                        None => {
                            let warning = format!("graphml data key not declared: key={key_id}");
                            if self.mode == CompatibilityMode::Strict {
                                self.record(
                                    "read_graphml",
                                    DecisionAction::FailClosed,
                                    &warning,
                                    1.0,
                                );
                                return Err(ReadWriteError::FailClosed {
                                    operation: "read_graphml",
                                    reason: warning,
                                });
                            }
                            warnings.push(warning.clone());
                            self.record(
                                "read_graphml",
                                DecisionAction::FullValidate,
                                &warning,
                                0.7,
                            );
                            current_data_text.clear();
                            return Ok(());
                        }
                    };
                    let target_scope = if current_edge.is_some() {
                        "edge"
                    } else if current_node.is_some() {
                        "node"
                    } else {
                        "graph"
                    };
                    if !graphml_scope_matches(&scope, target_scope) {
                        let warning = format!(
                            "graphml data key scope mismatch: key={key_id} declared_for={scope:?} target={target_scope}"
                        );
                        if self.mode == CompatibilityMode::Strict {
                            self.record("read_graphml", DecisionAction::FailClosed, &warning, 1.0);
                            return Err(ReadWriteError::FailClosed {
                                operation: "read_graphml",
                                reason: warning,
                            });
                        }
                        warnings.push(warning.clone());
                        self.record("read_graphml", DecisionAction::FullValidate, &warning, 0.7);
                        current_data_text.clear();
                        return Ok(());
                    }
                    let raw_value = std::mem::take(current_data_text);
                    let value =
                        self.parse_graphml_typed_value(&key_id, &attr_type, raw_value, warnings)?;
                    if current_node.is_some() && current_edge.is_none() {
                        pending_node_attrs.insert(attr_name, value);
                    } else if current_edge.is_some() {
                        pending_edge_attrs.insert(attr_name, value);
                    } else {
                        pending_graph_attrs.insert(attr_name, value);
                    }
                }
                current_data_text.clear();
                *current_data_has_children = false;
            }
            b"default" => {
                if let Some(key_id) = current_key_default_key.take() {
                    let raw_value = std::mem::take(current_key_default_text);
                    if let Some(key_def) = key_registry.get_mut(&key_id) {
                        let value = self.parse_graphml_typed_value(
                            &key_id,
                            &key_def.attr_type,
                            raw_value,
                            warnings,
                        )?;
                        key_def.default = Some(value.clone());
                        let scope = key_def.scope.trim().to_ascii_lowercase();
                        match scope.as_str() {
                            "node" => {
                                graphml_node_defaults.insert(key_def.name.clone(), value);
                            }
                            "edge" => {
                                graphml_edge_defaults.insert(key_def.name.clone(), value);
                            }
                            "graph" => {
                                graphml_graph_defaults.insert(key_def.name.clone(), value);
                            }
                            "all" | "" => {
                                graphml_node_defaults.insert(key_def.name.clone(), value.clone());
                                graphml_edge_defaults.insert(key_def.name.clone(), value.clone());
                                graphml_graph_defaults.insert(key_def.name.clone(), value);
                            }
                            _ => {}
                        }
                    }
                }
            }
            b"node" => {
                if let Some(node_id) = current_node.as_ref()
                    && !pending_node_attrs.is_empty()
                {
                    graph.add_node_with_attrs(node_id.clone(), std::mem::take(pending_node_attrs));
                }
                *current_node = None;
                pending_node_attrs.clear();
            }
            b"edge" => {
                if let Some((source, target)) = current_edge.take() {
                    if *current_edge_skip {
                        *current_edge_skip = false;
                        pending_edge_attrs.clear();
                    } else {
                        let result = graph.add_edge_with_attrs(
                            source,
                            target,
                            std::mem::take(pending_edge_attrs),
                        );
                        if let Err(err) = result {
                            let warning = format!("graphml edge add failed: {err}");
                            if self.mode == CompatibilityMode::Strict {
                                self.record(
                                    "read_graphml",
                                    DecisionAction::FailClosed,
                                    &warning,
                                    1.0,
                                );
                                return Err(ReadWriteError::FailClosed {
                                    operation: "read_graphml",
                                    reason: warning,
                                });
                            }
                            warnings.push(warning.clone());
                            self.record(
                                "read_graphml",
                                DecisionAction::FullValidate,
                                &warning,
                                0.7,
                            );
                        }
                    }
                }
                *current_edge_directed = None;
                pending_edge_attrs.clear();
            }
            b"key" => {
                *current_key_id = None;
                *current_key_default_key = None;
                current_key_default_text.clear();
            }
            b"graph" => {
                *graph_attrs = std::mem::take(pending_graph_attrs);
                *in_graph = false;
            }
            _ => {}
        }
        Ok(())
    }

    fn parse_graphml_typed_value(
        &mut self,
        key_id: &str,
        attr_type: &str,
        raw_value: String,
        warnings: &mut Vec<String>,
    ) -> Result<CgseValue, ReadWriteError> {
        let raw_value_for_error = raw_value.clone();
        let attr_type = attr_type.trim().to_ascii_lowercase();
        let trimmed = raw_value.trim();

        if raw_value.is_empty() {
            return Ok(CgseValue::String(raw_value));
        }

        let parsed = match attr_type.as_str() {
            "" | "string" => Ok(CgseValue::String(raw_value)),
            "boolean" => match trimmed.to_ascii_lowercase().as_str() {
                "true" | "1" => Ok(CgseValue::Bool(true)),
                "false" | "0" => Ok(CgseValue::Bool(false)),
                _ => Err("boolean"),
            },
            "int" | "long" => trimmed
                .parse::<i64>()
                .map(CgseValue::Int)
                .map_err(|_| "int"),
            "float" | "double" => trimmed
                .parse::<f64>()
                .map(CgseValue::Float)
                .map_err(|_| "float"),
            _ => Ok(CgseValue::parse_relaxed(trimmed)),
        };

        match parsed {
            Ok(value) => Ok(value),
            Err(expected) => {
                let warning = format!(
                    "graphml attr parse failed: key={key_id} type={attr_type} expected={expected} value={raw_value_for_error:?}"
                );
                if self.mode == CompatibilityMode::Strict {
                    self.record("read_graphml", DecisionAction::FailClosed, &warning, 1.0);
                    return Err(ReadWriteError::FailClosed {
                        operation: "read_graphml",
                        reason: warning,
                    });
                }
                warnings.push(warning.clone());
                self.record("read_graphml", DecisionAction::FullValidate, &warning, 0.8);
                Ok(CgseValue::String(raw_value_for_error))
            }
        }
    }

    // -----------------------------------------------------------------------
    // GML (Graph Modelling Language)
    // -----------------------------------------------------------------------

    /// Write an undirected graph to GML format.
    pub fn write_gml(&mut self, graph: &Graph) -> Result<String, ReadWriteError> {
        self.write_gml_with_graph_attrs(graph, &AttrMap::new())
    }

    pub fn write_gml_with_graph_attrs(
        &mut self,
        graph: &Graph,
        graph_attrs: &AttrMap,
    ) -> Result<String, ReadWriteError> {
        self.write_gml_impl(graph, graph_attrs, false)
    }

    /// Write a directed graph to GML format.
    pub fn write_digraph_gml(&mut self, graph: &DiGraph) -> Result<String, ReadWriteError> {
        self.write_digraph_gml_with_graph_attrs(graph, &AttrMap::new())
    }

    pub fn write_digraph_gml_with_graph_attrs(
        &mut self,
        graph: &DiGraph,
        graph_attrs: &AttrMap,
    ) -> Result<String, ReadWriteError> {
        self.write_gml_impl(graph, graph_attrs, true)
    }

    fn write_gml_impl(
        &mut self,
        graph: &dyn GraphLikeRead,
        graph_attrs: &AttrMap,
        directed: bool,
    ) -> Result<String, ReadWriteError> {
        let mut out = String::new();
        out.push_str("graph [\n");
        out.push_str(&format!("  directed {}\n", if directed { 1 } else { 0 }));
        for (key, value) in graph_attrs {
            out.push_str(&format!("  {} {}\n", key, gml_value_str(value)));
        }

        // Build node-name → id map (use integer label if parseable, otherwise assign sequentially)
        let mut label_to_id: BTreeMap<String, i64> = BTreeMap::new();
        let mut used_ids = std::collections::HashSet::new();

        // First pass: reserve parsed integer IDs
        for node_name in graph.nodes_ordered() {
            if let Ok(id) = node_name.parse::<i64>() {
                label_to_id.insert(node_name.to_owned(), id);
                used_ids.insert(id);
            }
        }

        // Second pass: assign remaining nodes to unused sequential IDs
        let mut next_id: i64 = 0;
        for node_name in graph.nodes_ordered() {
            if !label_to_id.contains_key(node_name) {
                while used_ids.contains(&next_id) {
                    next_id += 1;
                }
                label_to_id.insert(node_name.to_owned(), next_id);
                used_ids.insert(next_id);
                next_id += 1;
            }
        }

        for node_name in graph.nodes_ordered() {
            out.push_str("  node [\n");
            let id = label_to_id[node_name];
            out.push_str(&format!("    id {id}\n"));
            out.push_str(&format!("    label \"{}\"\n", gml_escape(node_name)));
            if let Some(attrs) = graph.node_attrs(node_name) {
                for (key, value) in attrs {
                    out.push_str(&format!("    {} {}\n", key, gml_value_str(value)));
                }
            }
            out.push_str("  ]\n");
        }

        for edge in graph.edges_ordered() {
            out.push_str("  edge [\n");
            let src_id =
                label_to_id
                    .get(&edge.left)
                    .copied()
                    .ok_or_else(|| ReadWriteError::FailClosed {
                        operation: "write_gml",
                        reason: format!(
                            "edge source node '{}' missing from node mapping",
                            edge.left
                        ),
                    })?;
            let tgt_id = label_to_id.get(&edge.right).copied().ok_or_else(|| {
                ReadWriteError::FailClosed {
                    operation: "write_gml",
                    reason: format!(
                        "edge target node '{}' missing from node mapping",
                        edge.right
                    ),
                }
            })?;
            out.push_str(&format!("    source {src_id}\n"));
            out.push_str(&format!("    target {tgt_id}\n"));
            for (key, value) in &edge.attrs {
                out.push_str(&format!("    {} {}\n", key, gml_value_str(value)));
            }
            out.push_str("  ]\n");
        }

        out.push_str("]\n");

        self.record(
            "write_gml",
            DecisionAction::Allow,
            "gml write completed",
            0.04,
        );
        Ok(out)
    }

    /// Read a GML string into an undirected graph.
    pub fn read_gml(&mut self, input: &str) -> Result<ReadWriteReport, ReadWriteError> {
        let mut graph = Graph::new(self.mode);
        let mut graph_attrs = AttrMap::new();
        let mut warnings = Vec::new();
        let directed = self.read_gml_into(&mut graph, &mut graph_attrs, &mut warnings, input)?;
        if directed.declared && directed.value {
            let warning = "GML declares directed=1 but read into undirected Graph".to_owned();
            if self.mode == CompatibilityMode::Strict {
                self.record("read_gml", DecisionAction::FailClosed, &warning, 1.0);
                return Err(ReadWriteError::FailClosed {
                    operation: "read_gml",
                    reason: warning,
                });
            }
            warnings.push(warning.clone());
            self.record("read_gml", DecisionAction::FullValidate, &warning, 0.7);
        }
        self.record(
            "read_gml",
            DecisionAction::Allow,
            "gml parse completed",
            0.04,
        );
        Ok(ReadWriteReport {
            graph,
            graph_attrs,
            warnings,
        })
    }

    /// Read a GML string into a directed graph.
    pub fn read_digraph_gml(&mut self, input: &str) -> Result<DiReadWriteReport, ReadWriteError> {
        let mut graph = DiGraph::new(self.mode);
        let mut graph_attrs = AttrMap::new();
        let mut warnings = Vec::new();
        let directed = self.read_gml_into(&mut graph, &mut graph_attrs, &mut warnings, input)?;
        if directed.declared && !directed.value {
            let warning = "GML declares directed=0 but read into directed DiGraph".to_owned();
            if self.mode == CompatibilityMode::Strict {
                self.record("read_gml", DecisionAction::FailClosed, &warning, 1.0);
                return Err(ReadWriteError::FailClosed {
                    operation: "read_gml",
                    reason: warning,
                });
            }
            warnings.push(warning.clone());
            self.record("read_gml", DecisionAction::FullValidate, &warning, 0.7);
        }
        self.record(
            "read_gml",
            DecisionAction::Allow,
            "digraph gml parse completed",
            0.04,
        );
        Ok(DiReadWriteReport {
            graph,
            graph_attrs,
            warnings,
        })
    }

    pub fn gml_declares_directed(&mut self, input: &str) -> Result<bool, ReadWriteError> {
        let tokens = gml_tokenize(input);
        let mut pos = 0;

        while pos < tokens.len() {
            if tokens[pos] == "graph" && pos + 1 < tokens.len() && tokens[pos + 1] == "[" {
                pos += 2;
                break;
            }
            pos += 1;
        }

        let mut depth: usize = if pos > 0 { 1 } else { 0 };
        while pos < tokens.len() && depth > 0 {
            match tokens[pos].as_str() {
                "[" => {
                    depth += 1;
                    pos += 1;
                }
                "]" => {
                    depth = depth.saturating_sub(1);
                    pos += 1;
                }
                "directed" if depth == 1 && pos + 1 < tokens.len() => {
                    let value = &tokens[pos + 1];
                    return match parse_gml_directed_value(value) {
                        Some(flag) => Ok(flag),
                        None => {
                            let warning = format!("gml directed value '{value}' must be 0 or 1");
                            if self.mode == CompatibilityMode::Strict {
                                self.record("read_gml", DecisionAction::FailClosed, &warning, 1.0);
                                Err(ReadWriteError::FailClosed {
                                    operation: "read_gml",
                                    reason: warning,
                                })
                            } else {
                                self.record(
                                    "read_gml",
                                    DecisionAction::FullValidate,
                                    &warning,
                                    0.7,
                                );
                                Ok(false)
                            }
                        }
                    };
                }
                _ => pos += 1,
            }
        }

        Ok(false)
    }

    /// Parse GML into a generic graph. Returns the directed flag plus whether it was declared.
    fn read_gml_into<G>(
        &mut self,
        graph: &mut G,
        graph_attrs: &mut AttrMap,
        warnings: &mut Vec<String>,
        input: &str,
    ) -> Result<GmlDirectedFlag, ReadWriteError>
    where
        G: GraphLike,
    {
        let mut directed = false;
        let mut directed_declared = false;
        let mut id_to_label: BTreeMap<i64, String> = BTreeMap::new();
        let mut label_set: BTreeSet<String> = BTreeSet::new();
        let mut node_attrs_pending: BTreeMap<i64, AttrMap> = BTreeMap::new();

        // Simple GML token parser
        let tokens = gml_tokenize(input);
        let mut pos = 0;

        // Skip to "graph ["
        while pos < tokens.len() {
            if tokens[pos] == "graph" && pos + 1 < tokens.len() && tokens[pos + 1] == "[" {
                pos += 2;
                break;
            }
            pos += 1;
        }

        while pos < tokens.len() {
            let tok = &tokens[pos];
            match tok.as_str() {
                "directed" if pos + 1 < tokens.len() => {
                    directed_declared = true;
                    let value = &tokens[pos + 1];
                    match parse_gml_directed_value(value) {
                        Some(flag) => {
                            directed = flag;
                        }
                        None => {
                            let warning = format!("gml directed value '{value}' must be 0 or 1");
                            if self.mode == CompatibilityMode::Strict {
                                self.record("read_gml", DecisionAction::FailClosed, &warning, 1.0);
                                return Err(ReadWriteError::FailClosed {
                                    operation: "read_gml",
                                    reason: warning,
                                });
                            }
                            warnings.push(warning.clone());
                            self.record("read_gml", DecisionAction::FullValidate, &warning, 0.7);
                            directed_declared = false;
                            directed = false;
                        }
                    }
                    pos += 2;
                }
                "node" if pos + 1 < tokens.len() && tokens[pos + 1] == "[" => {
                    pos += 2;
                    let (node, new_pos) = self.parse_gml_node(&tokens, pos, warnings)?;
                    if let Some((id, label, attrs)) = node {
                        if id_to_label.contains_key(&id) {
                            let warning = format!("gml node duplicate id {id}");
                            if self.mode == CompatibilityMode::Strict {
                                self.record("read_gml", DecisionAction::FailClosed, &warning, 1.0);
                                return Err(ReadWriteError::FailClosed {
                                    operation: "read_gml",
                                    reason: warning,
                                });
                            }
                            warnings.push(warning.clone());
                            self.record("read_gml", DecisionAction::FullValidate, &warning, 0.7);
                            pos = new_pos;
                            continue;
                        }

                        let node_label = match label {
                            Some(label) => label,
                            None => {
                                let warning = format!("gml node {id} missing label");
                                if self.mode == CompatibilityMode::Strict {
                                    self.record(
                                        "read_gml",
                                        DecisionAction::FailClosed,
                                        &warning,
                                        1.0,
                                    );
                                    return Err(ReadWriteError::FailClosed {
                                        operation: "read_gml",
                                        reason: warning,
                                    });
                                }
                                warnings.push(warning.clone());
                                self.record(
                                    "read_gml",
                                    DecisionAction::FullValidate,
                                    &warning,
                                    0.6,
                                );
                                id.to_string()
                            }
                        };

                        if label_set.contains(&node_label) {
                            let warning = format!("gml node duplicate label '{node_label}'");
                            if self.mode == CompatibilityMode::Strict {
                                self.record("read_gml", DecisionAction::FailClosed, &warning, 1.0);
                                return Err(ReadWriteError::FailClosed {
                                    operation: "read_gml",
                                    reason: warning,
                                });
                            }
                            warnings.push(warning.clone());
                            self.record("read_gml", DecisionAction::FullValidate, &warning, 0.7);
                            pos = new_pos;
                            continue;
                        }

                        label_set.insert(node_label.clone());
                        id_to_label.insert(id, node_label.clone());
                        let _ = graph.add_node(node_label);
                        if !attrs.is_empty() {
                            node_attrs_pending.insert(id, attrs);
                        }
                    }
                    pos = new_pos;
                }
                "edge" if pos + 1 < tokens.len() && tokens[pos + 1] == "[" => {
                    pos += 2;
                    let (edge, new_pos) = self.parse_gml_edge(&tokens, pos, warnings)?;
                    if let Some((source, target, attrs)) = edge {
                        let mut skip_edge = false;
                        if let std::collections::btree_map::Entry::Vacant(entry) =
                            id_to_label.entry(source)
                        {
                            let warning = format!("gml edge references missing source {source}");
                            if self.mode == CompatibilityMode::Strict {
                                self.record("read_gml", DecisionAction::FailClosed, &warning, 1.0);
                                return Err(ReadWriteError::FailClosed {
                                    operation: "read_gml",
                                    reason: warning,
                                });
                            }
                            warnings.push(warning.clone());
                            self.record("read_gml", DecisionAction::FullValidate, &warning, 0.7);
                            let candidate = source.to_string();
                            if label_set.contains(&candidate) {
                                skip_edge = true;
                            } else {
                                label_set.insert(candidate.clone());
                                entry.insert(candidate);
                            }
                        }
                        if let std::collections::btree_map::Entry::Vacant(entry) =
                            id_to_label.entry(target)
                        {
                            let warning = format!("gml edge references missing target {target}");
                            if self.mode == CompatibilityMode::Strict {
                                self.record("read_gml", DecisionAction::FailClosed, &warning, 1.0);
                                return Err(ReadWriteError::FailClosed {
                                    operation: "read_gml",
                                    reason: warning,
                                });
                            }
                            warnings.push(warning.clone());
                            self.record("read_gml", DecisionAction::FullValidate, &warning, 0.7);
                            let candidate = target.to_string();
                            if label_set.contains(&candidate) {
                                skip_edge = true;
                            } else {
                                label_set.insert(candidate.clone());
                                entry.insert(candidate);
                            }
                        }
                        if skip_edge {
                            pos = new_pos;
                            continue;
                        }
                        let source_label = id_to_label
                            .get(&source)
                            .cloned()
                            .unwrap_or_else(|| source.to_string());
                        let target_label = id_to_label
                            .get(&target)
                            .cloned()
                            .unwrap_or_else(|| target.to_string());
                        // Ensure nodes exist
                        id_to_label.entry(source).or_insert_with(|| {
                            let _ = graph.add_node(source_label.clone());
                            source_label.clone()
                        });
                        id_to_label.entry(target).or_insert_with(|| {
                            let _ = graph.add_node(target_label.clone());
                            target_label.clone()
                        });
                        let _ = graph.add_edge_with_attrs(source_label, target_label, attrs);
                    }
                    pos = new_pos;
                }
                "]" => break,
                key if pos + 1 < tokens.len()
                    && tokens[pos + 1] != "["
                    && tokens[pos + 1] != "]" =>
                {
                    graph_attrs.insert(
                        key.to_owned(),
                        CgseValue::String(gml_unescape(&tokens[pos + 1])),
                    );
                    pos += 2;
                }
                _ => {
                    pos += 1;
                }
            }
        }

        // Apply node attributes
        for (id, attrs) in node_attrs_pending {
            if let Some(label) = id_to_label.get(&id) {
                graph.add_node_with_attrs(label.clone(), attrs);
            }
        }

        Ok(GmlDirectedFlag {
            declared: directed_declared,
            value: directed,
        })
    }

    fn parse_gml_node(
        &mut self,
        tokens: &[String],
        mut pos: usize,
        warnings: &mut Vec<String>,
    ) -> GmlNodeParseResult {
        let mut id: Option<i64> = None;
        let mut label: Option<String> = None;
        let mut attrs = AttrMap::new();
        let mut invalid = false;

        while pos < tokens.len() {
            match tokens[pos].as_str() {
                "]" => {
                    pos += 1;
                    if id.is_none() {
                        let warning = "gml node missing id".to_owned();
                        if self.mode == CompatibilityMode::Strict {
                            self.record("read_gml", DecisionAction::FailClosed, &warning, 1.0);
                            return Err(ReadWriteError::FailClosed {
                                operation: "read_gml",
                                reason: warning,
                            });
                        }
                        warnings.push(warning.clone());
                        self.record("read_gml", DecisionAction::FullValidate, &warning, 0.7);
                        return Ok((None, pos));
                    }
                    if invalid {
                        return Ok((None, pos));
                    }
                    return Ok(match id {
                        Some(id) => (Some((id, label, attrs)), pos),
                        None => (None, pos),
                    });
                }
                "id" if pos + 1 < tokens.len() => {
                    match tokens[pos + 1].parse::<i64>() {
                        Ok(parsed) => {
                            id = Some(parsed);
                        }
                        Err(_) => {
                            let warning = format!("invalid node id '{}'", tokens[pos + 1]);
                            if self.mode == CompatibilityMode::Strict {
                                self.record("read_gml", DecisionAction::FailClosed, &warning, 1.0);
                                return Err(ReadWriteError::FailClosed {
                                    operation: "read_gml",
                                    reason: warning,
                                });
                            }
                            warnings.push(warning.clone());
                            self.record("read_gml", DecisionAction::FullValidate, &warning, 0.7);
                            invalid = true;
                        }
                    }
                    pos += 2;
                }
                "label" if pos + 1 < tokens.len() => {
                    label = Some(gml_unescape(&tokens[pos + 1]));
                    pos += 2;
                }
                key => {
                    if pos + 1 < tokens.len() && tokens[pos + 1] != "[" && tokens[pos + 1] != "]" {
                        attrs.insert(
                            key.to_owned(),
                            CgseValue::String(gml_unescape(&tokens[pos + 1])),
                        );
                        pos += 2;
                    } else {
                        pos += 1;
                    }
                }
            }
        }
        let warning = "gml node missing closing bracket".to_owned();
        if self.mode == CompatibilityMode::Strict {
            self.record("read_gml", DecisionAction::FailClosed, &warning, 1.0);
            return Err(ReadWriteError::FailClosed {
                operation: "read_gml",
                reason: warning,
            });
        }
        warnings.push(warning.clone());
        self.record("read_gml", DecisionAction::FullValidate, &warning, 0.7);
        Ok((None, pos))
    }

    fn parse_gml_edge(
        &mut self,
        tokens: &[String],
        mut pos: usize,
        warnings: &mut Vec<String>,
    ) -> GmlEdgeParseResult {
        let mut source: Option<i64> = None;
        let mut target: Option<i64> = None;
        let mut attrs = AttrMap::new();
        let mut invalid = false;

        while pos < tokens.len() {
            match tokens[pos].as_str() {
                "]" => {
                    pos += 1;
                    if source.is_none() || target.is_none() {
                        let warning = format!(
                            "gml edge missing source/target: source={:?} target={:?}",
                            source, target
                        );
                        if self.mode == CompatibilityMode::Strict {
                            self.record("read_gml", DecisionAction::FailClosed, &warning, 1.0);
                            return Err(ReadWriteError::FailClosed {
                                operation: "read_gml",
                                reason: warning,
                            });
                        }
                        warnings.push(warning.clone());
                        self.record("read_gml", DecisionAction::FullValidate, &warning, 0.7);
                        return Ok((None, pos));
                    }
                    if invalid {
                        return Ok((None, pos));
                    }
                    return Ok(match (source, target) {
                        (Some(source), Some(target)) => (Some((source, target, attrs)), pos),
                        _ => (None, pos),
                    });
                }
                "source" if pos + 1 < tokens.len() => {
                    match tokens[pos + 1].parse::<i64>() {
                        Ok(parsed) => {
                            source = Some(parsed);
                        }
                        Err(_) => {
                            let warning = format!("invalid edge source id '{}'", tokens[pos + 1]);
                            if self.mode == CompatibilityMode::Strict {
                                self.record("read_gml", DecisionAction::FailClosed, &warning, 1.0);
                                return Err(ReadWriteError::FailClosed {
                                    operation: "read_gml",
                                    reason: warning,
                                });
                            }
                            warnings.push(warning.clone());
                            self.record("read_gml", DecisionAction::FullValidate, &warning, 0.7);
                            invalid = true;
                        }
                    }
                    pos += 2;
                }
                "target" if pos + 1 < tokens.len() => {
                    match tokens[pos + 1].parse::<i64>() {
                        Ok(parsed) => {
                            target = Some(parsed);
                        }
                        Err(_) => {
                            let warning = format!("invalid edge target id '{}'", tokens[pos + 1]);
                            if self.mode == CompatibilityMode::Strict {
                                self.record("read_gml", DecisionAction::FailClosed, &warning, 1.0);
                                return Err(ReadWriteError::FailClosed {
                                    operation: "read_gml",
                                    reason: warning,
                                });
                            }
                            warnings.push(warning.clone());
                            self.record("read_gml", DecisionAction::FullValidate, &warning, 0.7);
                            invalid = true;
                        }
                    }
                    pos += 2;
                }
                key => {
                    if pos + 1 < tokens.len() && tokens[pos + 1] != "[" && tokens[pos + 1] != "]" {
                        attrs.insert(
                            key.to_owned(),
                            CgseValue::String(gml_unescape(&tokens[pos + 1])),
                        );
                        pos += 2;
                    } else {
                        pos += 1;
                    }
                }
            }
        }
        let warning = "gml edge missing closing bracket".to_owned();
        if self.mode == CompatibilityMode::Strict {
            self.record("read_gml", DecisionAction::FailClosed, &warning, 1.0);
            return Err(ReadWriteError::FailClosed {
                operation: "read_gml",
                reason: warning,
            });
        }
        warnings.push(warning.clone());
        self.record("read_gml", DecisionAction::FullValidate, &warning, 0.7);
        Ok((None, pos))
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

// ---------------------------------------------------------------------------
// GML helpers
// ---------------------------------------------------------------------------

/// Tokenize a GML string into a flat list of tokens.
/// Handles quoted strings, brackets, and whitespace-separated values.
fn gml_tokenize(input: &str) -> Vec<String> {
    let mut tokens = Vec::new();
    let mut chars = input.chars().peekable();

    while let Some(&ch) = chars.peek() {
        match ch {
            ' ' | '\t' | '\n' | '\r' => {
                chars.next();
            }
            '#' => {
                // Skip comment to end of line
                while let Some(&c) = chars.peek() {
                    chars.next();
                    if c == '\n' {
                        break;
                    }
                }
            }
            '[' | ']' => {
                tokens.push(ch.to_string());
                chars.next();
            }
            '"' => {
                chars.next(); // consume opening quote
                let mut s = String::new();
                while let Some(&c) = chars.peek() {
                    chars.next();
                    if c == '"' {
                        break;
                    }
                    if c == '\\' {
                        if let Some(&escaped) = chars.peek() {
                            chars.next();
                            s.push(escaped);
                        }
                    } else {
                        s.push(c);
                    }
                }
                tokens.push(s);
            }
            _ => {
                let mut word = String::new();
                while let Some(&c) = chars.peek() {
                    if c.is_whitespace() || c == '[' || c == ']' || c == '"' {
                        break;
                    }
                    word.push(c);
                    chars.next();
                }
                if !word.is_empty() {
                    tokens.push(word);
                }
            }
        }
    }

    tokens
}

/// Escape a string for GML output (wrap in quotes).
fn gml_escape(s: &str) -> String {
    let mut out = String::with_capacity(s.len());
    for ch in s.chars() {
        let needs_escape = matches!(ch, '&' | '"') || !(' '..='~').contains(&ch);
        if needs_escape {
            out.push_str(&format!("&#{};", ch as u32));
        } else {
            out.push(ch);
        }
    }
    out
}

/// Format a value for GML: try numeric, otherwise quote it.
fn gml_value_str(value: &CgseValue) -> String {
    match value {
        CgseValue::String(s) => format!("\"{}\"", gml_escape(s)),
        CgseValue::Int(i) => i.to_string(),
        CgseValue::Bool(b) => {
            if *b {
                "1".to_owned()
            } else {
                "0".to_owned()
            }
        }
        CgseValue::Map(map) => {
            let text = serde_json::to_string(map).unwrap_or_else(|_| "{}".to_owned());
            format!("\"{}\"", gml_escape(&text))
        }
        CgseValue::Float(f) => {
            if f.is_infinite() {
                if f.is_sign_positive() {
                    "+INF".to_owned()
                } else {
                    "-INF".to_owned()
                }
            } else if f.is_nan() {
                "NAN".to_owned()
            } else {
                let mut text = f.to_string();
                if !text.contains('.') && !text.contains('e') && !text.contains('E') {
                    text.push_str(".0");
                }
                text
            }
        }
    }
}

fn parse_gml_directed_value(value: &str) -> Option<bool> {
    match value.trim() {
        "0" => Some(false),
        "1" => Some(true),
        _ => None,
    }
}

fn graphml_attr_type(value: &CgseValue) -> &'static str {
    GraphmlValueType::from_value(value).as_str()
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash)]
enum GraphmlValueType {
    Boolean,
    Int,
    Float,
    String,
}

impl GraphmlValueType {
    fn from_value(value: &CgseValue) -> Self {
        match value {
            CgseValue::Bool(_) => Self::Boolean,
            CgseValue::Int(_) => Self::Int,
            CgseValue::Float(_) => Self::Float,
            CgseValue::String(_) => Self::String,
            CgseValue::Map(_) => Self::String,
        }
    }

    const fn as_str(self) -> &'static str {
        match self {
            Self::Boolean => "boolean",
            Self::Int => "int",
            Self::Float => "double",
            Self::String => "string",
        }
    }
}

/// Remove surrounding quotes from a GML token.
fn gml_unescape(s: &str) -> String {
    let mut out = String::with_capacity(s.len());
    let mut chars = s.chars().peekable();

    while let Some(ch) = chars.next() {
        if ch != '&' {
            out.push(ch);
            continue;
        }

        let mut entity = String::new();
        let mut terminated = false;
        while let Some(&next) = chars.peek() {
            chars.next();
            if next == ';' {
                terminated = true;
                break;
            }
            entity.push(next);
        }

        if !terminated {
            out.push('&');
            out.push_str(&entity);
            break;
        }

        let decoded = if let Some(hex) = entity
            .strip_prefix("#x")
            .or_else(|| entity.strip_prefix("#X"))
        {
            u32::from_str_radix(hex, 16).ok()
        } else if let Some(dec) = entity.strip_prefix('#') {
            dec.parse::<u32>().ok()
        } else {
            match entity.as_str() {
                "amp" => Some('&' as u32),
                "quot" => Some('"' as u32),
                "lt" => Some('<' as u32),
                "gt" => Some('>' as u32),
                "apos" => Some('\'' as u32),
                _ => None,
            }
        };

        if let Some(codepoint) = decoded.and_then(char::from_u32) {
            out.push(codepoint);
        } else {
            out.push('&');
            out.push_str(&entity);
            out.push(';');
        }
    }

    out
}

trait GraphLikeRead {
    fn nodes_ordered(&self) -> Vec<&str>;
    fn node_attrs(&self, node: &str) -> Option<&AttrMap>;
    fn edges_ordered(&self) -> Vec<fnx_classes::EdgeSnapshot>;
}

impl GraphLikeRead for Graph {
    fn nodes_ordered(&self) -> Vec<&str> {
        self.nodes_ordered()
    }
    fn node_attrs(&self, node: &str) -> Option<&AttrMap> {
        self.node_attrs(node)
    }
    fn edges_ordered(&self) -> Vec<fnx_classes::EdgeSnapshot> {
        self.edges_ordered()
    }
}

impl GraphLikeRead for DiGraph {
    fn nodes_ordered(&self) -> Vec<&str> {
        self.nodes_ordered()
    }
    fn node_attrs(&self, node: &str) -> Option<&AttrMap> {
        self.node_attrs(node)
    }
    fn edges_ordered(&self) -> Vec<fnx_classes::EdgeSnapshot> {
        self.edges_ordered()
    }
}

trait GraphLike {
    fn add_node(&mut self, node: String) -> bool;
    fn add_node_with_attrs(&mut self, node: String, attrs: AttrMap) -> bool;
    fn add_edge_with_attrs(
        &mut self,
        source: String,
        target: String,
        attrs: AttrMap,
    ) -> Result<bool, GraphError>;
    fn apply_node_defaults(&mut self, defaults: &AttrMap);
    fn apply_edge_defaults(&mut self, defaults: &AttrMap);
    fn is_directed(&self) -> bool;
    fn has_edge(&self, source: &str, target: &str) -> bool;
}

impl GraphLike for Graph {
    fn add_node(&mut self, node: String) -> bool {
        self.add_node(node)
    }
    fn add_node_with_attrs(&mut self, node: String, attrs: AttrMap) -> bool {
        self.add_node_with_attrs(node, attrs)
    }
    fn add_edge_with_attrs(
        &mut self,
        source: String,
        target: String,
        attrs: AttrMap,
    ) -> Result<bool, GraphError> {
        self.add_edge_with_attrs(source, target, attrs)
            .map(|_| true)
    }

    fn apply_node_defaults(&mut self, defaults: &AttrMap) {
        let _ = Graph::apply_node_defaults(self, defaults);
    }

    fn apply_edge_defaults(&mut self, defaults: &AttrMap) {
        let _ = Graph::apply_edge_defaults(self, defaults);
    }

    fn is_directed(&self) -> bool {
        false
    }

    fn has_edge(&self, source: &str, target: &str) -> bool {
        self.has_edge(source, target)
    }
}

impl GraphLike for DiGraph {
    fn add_node(&mut self, node: String) -> bool {
        self.add_node(node)
    }
    fn add_node_with_attrs(&mut self, node: String, attrs: AttrMap) -> bool {
        self.add_node_with_attrs(node, attrs)
    }
    fn add_edge_with_attrs(
        &mut self,
        source: String,
        target: String,
        attrs: AttrMap,
    ) -> Result<bool, GraphError> {
        self.add_edge_with_attrs(source, target, attrs)
            .map(|_| true)
    }

    fn apply_node_defaults(&mut self, defaults: &AttrMap) {
        let _ = DiGraph::apply_node_defaults(self, defaults);
    }

    fn apply_edge_defaults(&mut self, defaults: &AttrMap) {
        let _ = DiGraph::apply_edge_defaults(self, defaults);
    }

    fn is_directed(&self) -> bool {
        true
    }

    fn has_edge(&self, source: &str, target: &str) -> bool {
        self.has_edge(source, target)
    }
}

fn attr_escape(s: &str) -> String {
    s.replace('%', "%25")
        .replace('#', "%23")
        .replace('=', "%3D")
        .replace(';', "%3B")
        .replace(' ', "%20")
        .replace('\t', "%09")
        .replace('\n', "%0A")
        .replace('\r', "%0D")
}

fn attr_unescape(s: &str) -> String {
    s.replace("%0D", "\r")
        .replace("%0d", "\r")
        .replace("%0A", "\n")
        .replace("%0a", "\n")
        .replace("%09", "\t")
        .replace("%20", " ")
        .replace("%23", "#")
        .replace("%3B", ";")
        .replace("%3b", ";")
        .replace("%3D", "=")
        .replace("%3d", "=")
        .replace("%25", "%")
}

fn encode_attrs(attrs: &AttrMap) -> String {
    if attrs.is_empty() {
        return "-".to_owned();
    }
    attrs
        .iter()
        .map(|(k, v)| format!("{}={}", attr_escape(k), attr_escape(&v.as_str())))
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
        if key.is_empty() {
            let warning = format!("line {line_no} malformed attr pair `{pair}`");
            if mode == CompatibilityMode::Strict {
                return Err(ReadWriteError::FailClosed {
                    operation: "read_edgelist",
                    reason: warning,
                });
            }
            warnings.push(warning);
            continue;
        }
        attrs.insert(
            attr_unescape(key),
            CgseValue::parse_relaxed(&attr_unescape(value)),
        );
    }
    Ok(attrs)
}

fn xml_write_err(context: &str, err: std::io::Error) -> ReadWriteError {
    ReadWriteError::FailClosed {
        operation: "write_graphml",
        reason: format!("xml write error ({context}): {err}"),
    }
}

fn set<const N: usize>(values: [&str; N]) -> BTreeSet<String> {
    values.into_iter().map(str::to_owned).collect()
}

fn xml_local_name(name: &[u8]) -> &[u8] {
    name.iter()
        .rposition(|b| *b == b':')
        .map_or(name, |idx| &name[idx + 1..])
}

type GmlNodeParsed = (i64, Option<String>, AttrMap);
type GmlEdgeParsed = (i64, i64, AttrMap);
type GmlNodeParseResult = Result<(Option<GmlNodeParsed>, usize), ReadWriteError>;
type GmlEdgeParseResult = Result<(Option<GmlEdgeParsed>, usize), ReadWriteError>;

#[derive(Clone, Copy, Debug)]
struct GmlDirectedFlag {
    declared: bool,
    value: bool,
}

#[derive(Clone, Debug)]
struct GraphmlDirectedFlag {
    declared: bool,
    value: bool,
    warning: Option<String>,
}

fn graphml_scope_matches(for_scope: &str, target: &str) -> bool {
    let scope = for_scope.trim().to_ascii_lowercase();
    if scope.is_empty() || scope == "all" {
        return true;
    }
    scope == target
}

fn parse_graphml_directed_value(value: &[u8]) -> Option<bool> {
    let text = std::str::from_utf8(value).ok()?;
    match text.trim().to_ascii_lowercase().as_str() {
        "true" | "1" => Some(true),
        "false" | "0" => Some(false),
        _ => None,
    }
}

fn parse_graphml_edgedefault_value(value: &[u8]) -> Option<bool> {
    let text = std::str::from_utf8(value).ok()?;
    match text.trim().to_ascii_lowercase().as_str() {
        "directed" => Some(true),
        "undirected" => Some(false),
        _ => None,
    }
}

#[cfg(test)]
mod tests {
    use super::{EdgeListEngine, ReadWriteError};
    use fnx_classes::digraph::DiGraph;
    use fnx_classes::{Graph, GraphSnapshot};
    use fnx_runtime::{
        CgseValue, CompatibilityMode, DecisionAction, ForensicsBundleIndex, StructuredTestLog,
        TestKind, TestStatus, canonical_environment_fingerprint,
        structured_test_log_schema_version,
    };
    use proptest::prelude::*;
    use std::collections::BTreeMap;

    fn packet_006_forensics_bundle(
        run_id: &str,
        test_id: &str,
        replay_ref: &str,
        bundle_id: &str,
        artifact_refs: Vec<String>,
    ) -> ForensicsBundleIndex {
        ForensicsBundleIndex {
            bundle_id: bundle_id.to_owned(),
            run_id: run_id.to_owned(),
            test_id: test_id.to_owned(),
            bundle_hash_id: "bundle-hash-p2c006".to_owned(),
            captured_unix_ms: 1,
            replay_ref: replay_ref.to_owned(),
            artifact_refs,
            raptorq_sidecar_refs: Vec::new(),
            decode_proof_refs: Vec::new(),
        }
    }

    fn stable_digest_hex(input: &str) -> String {
        let mut hash = 0xcbf2_9ce4_8422_2325_u64;
        for byte in input.as_bytes() {
            hash ^= u64::from(*byte);
            hash = hash.wrapping_mul(0x0000_0100_0000_01B3_u64);
        }
        format!("sha256:{hash:016x}")
    }

    fn snapshot_digest(snapshot: &GraphSnapshot) -> String {
        let canonical = serde_json::to_string(snapshot).expect("snapshot json should serialize");
        stable_digest_hex(&canonical)
    }

    fn graph_fingerprint(graph: &Graph) -> String {
        let snapshot = graph.snapshot();
        let mode = match snapshot.mode {
            CompatibilityMode::Strict => "strict",
            CompatibilityMode::Hardened => "hardened",
        };
        let mut edge_signature = snapshot
            .edges
            .iter()
            .map(|edge| {
                let attrs = edge
                    .attrs
                    .iter()
                    .map(|(key, value)| format!("{key}={}", value.as_str()))
                    .collect::<Vec<String>>()
                    .join(";");
                format!("{}>{}[{attrs}]", edge.left, edge.right)
            })
            .collect::<Vec<String>>();
        edge_signature.sort();
        format!(
            "mode:{mode};nodes:{};edges:{};sig:{}",
            snapshot.nodes.join(","),
            snapshot.edges.len(),
            edge_signature.join("|")
        )
    }

    fn packet_006_contract_graph() -> Graph {
        let mut graph = Graph::strict();
        graph
            .add_edge_with_attrs(
                "a".to_owned(),
                "b".to_owned(),
                BTreeMap::from([("weight".to_owned(), CgseValue::Int(1))]),
            )
            .expect("edge add should succeed");
        graph
            .add_edge_with_attrs(
                "a".to_owned(),
                "c".to_owned(),
                BTreeMap::from([("label".to_owned(), CgseValue::String("blue".to_owned()))]),
            )
            .expect("edge add should succeed");
        graph
            .add_edge_with_attrs(
                "b".to_owned(),
                "d".to_owned(),
                BTreeMap::from([
                    ("weight".to_owned(), CgseValue::Int(3)),
                    ("capacity".to_owned(), CgseValue::Int(7)),
                ]),
            )
            .expect("edge add should succeed");
        graph
    }

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
    fn edgelist_roundtrip_preserves_whitespace_attrs() {
        let mut graph = Graph::strict();
        graph
            .add_edge_with_attrs(
                "a".to_owned(),
                "b".to_owned(),
                BTreeMap::from([
                    (
                        "note".to_owned(),
                        CgseValue::String("line1\nline2\tend\r".to_owned()),
                    ),
                    ("label".to_owned(), CgseValue::String("a b;c%".to_owned())),
                    ("hash".to_owned(), CgseValue::String("tag#a".to_owned())),
                ]),
            )
            .expect("edge add should succeed");

        let mut engine = EdgeListEngine::strict();
        let text = engine
            .write_edgelist(&graph)
            .expect("serialization should succeed");
        assert!(text.contains("%0A"));
        assert!(text.contains("%09"));
        assert!(text.contains("%0D"));
        assert!(text.contains("%23"));

        let parsed = engine
            .read_edgelist(&text)
            .expect("parse should succeed")
            .graph;

        let attrs = parsed.edge_attrs("a", "b").expect("edge should exist");
        assert_eq!(
            attrs.get("note"),
            Some(&CgseValue::String("line1\nline2\tend\r".to_owned()))
        );
        assert_eq!(
            attrs.get("label"),
            Some(&CgseValue::String("a b;c%".to_owned()))
        );
        assert_eq!(
            attrs.get("hash"),
            Some(&CgseValue::String("tag#a".to_owned()))
        );
    }

    #[test]
    fn adjlist_round_trip_is_deterministic() {
        let mut graph = Graph::strict();
        graph.add_edge("a", "b").expect("edge add should succeed");
        graph.add_edge("a", "c").expect("edge add should succeed");
        graph.add_node("d");

        let mut engine = EdgeListEngine::strict();
        let text = engine
            .write_adjlist(&graph)
            .expect("adjlist serialization should succeed");
        assert_eq!(text, "a b c\nb\nc\nd");

        let parsed = engine
            .read_adjlist(&text)
            .expect("adjlist parse should succeed")
            .graph;
        assert_eq!(graph.snapshot(), parsed.snapshot());
    }

    #[test]
    fn hardened_adjlist_ignores_comments_and_empty_lines() {
        let mut engine = EdgeListEngine::hardened();
        let input = "# comment\n\na b c\nc a\n";
        let report = engine
            .read_adjlist(input)
            .expect("hardened adjlist parse should succeed");
        assert!(report.warnings.is_empty());
        assert_eq!(report.graph.node_count(), 3);
        assert_eq!(report.graph.edge_count(), 2);
    }

    #[test]
    fn adjlist_strips_inline_comments() {
        let mut engine = EdgeListEngine::strict();
        let input = "a b c # trailing comment\nb a # another\n# full line comment\nc a\n";
        let report = engine
            .read_adjlist(input)
            .expect("strict adjlist parse should succeed");
        assert!(report.warnings.is_empty());
        assert_eq!(report.graph.node_count(), 3);
        assert_eq!(report.graph.edge_count(), 2);
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
    fn strict_mode_fails_closed_for_empty_attr_key() {
        let mut engine = EdgeListEngine::strict();
        let err = engine
            .read_edgelist("a b =1")
            .expect_err("strict parser should fail on empty attr key");
        assert!(matches!(err, ReadWriteError::FailClosed { .. }));
    }

    #[test]
    fn hardened_mode_warns_for_empty_attr_key() {
        let mut engine = EdgeListEngine::hardened();
        let report = engine
            .read_edgelist("a b =1")
            .expect("hardened parser should recover");
        assert!(!report.warnings.is_empty());
        let attrs = report
            .graph
            .edge_attrs("a", "b")
            .expect("edge should exist");
        assert!(attrs.is_empty());
    }

    #[test]
    fn edgelist_strips_inline_comments() {
        let mut engine = EdgeListEngine::strict();
        let input = "a b weight=1;color=blue # trailing\nc d - # comment\n";
        let report = engine
            .read_edgelist(input)
            .expect("strict edgelist parse should succeed");
        assert!(report.warnings.is_empty());
        assert_eq!(report.graph.edge_count(), 2);
        let attrs = report
            .graph
            .edge_attrs("a", "b")
            .expect("edge should exist");
        assert_eq!(attrs.get("weight"), Some(&CgseValue::Int(1)));
        assert_eq!(
            attrs.get("color"),
            Some(&CgseValue::String("blue".to_owned()))
        );
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

    #[test]
    fn graphml_round_trip_no_attrs() {
        let mut graph = Graph::strict();
        graph.add_edge("a", "b").expect("edge add should succeed");
        graph.add_edge("b", "c").expect("edge add should succeed");

        let mut engine = EdgeListEngine::strict();
        let xml = engine
            .write_graphml(&graph)
            .expect("graphml write should succeed");
        assert!(xml.contains("<graphml"));
        assert!(xml.contains("edgedefault=\"undirected\""));

        let parsed = engine
            .read_graphml(&xml)
            .expect("graphml read should succeed");
        assert!(parsed.warnings.is_empty());
        assert_eq!(graph.snapshot(), parsed.graph.snapshot());
    }

    #[test]
    fn digraph_graphml_round_trip() {
        let mut graph = DiGraph::strict();
        graph.add_edge("a", "b").expect("edge add should succeed");
        graph.add_edge("b", "c").expect("edge add should succeed");

        let mut engine = EdgeListEngine::strict();
        let xml = engine
            .write_digraph_graphml(&graph)
            .expect("graphml write should succeed");
        assert!(xml.contains("<graphml"));
        assert!(xml.contains("edgedefault=\"directed\""));

        let parsed = engine
            .read_digraph_graphml(&xml)
            .expect("graphml read should succeed");
        assert!(parsed.warnings.is_empty());
        assert_eq!(graph.snapshot(), parsed.graph.snapshot());
    }

    #[test]
    fn graphml_round_trip_with_edge_attrs() {
        let mut graph = Graph::strict();
        graph
            .add_edge_with_attrs(
                "a".to_owned(),
                "b".to_owned(),
                BTreeMap::from([("weight".to_owned(), "1".into())]),
            )
            .expect("edge add should succeed");
        graph
            .add_edge_with_attrs(
                "b".to_owned(),
                "c".to_owned(),
                BTreeMap::from([("weight".to_owned(), "3".into())]),
            )
            .expect("edge add should succeed");

        let mut engine = EdgeListEngine::strict();
        let xml = engine
            .write_graphml(&graph)
            .expect("graphml write should succeed");
        let parsed = engine
            .read_graphml(&xml)
            .expect("graphml read should succeed");
        assert!(parsed.warnings.is_empty());
        assert_eq!(graph.snapshot(), parsed.graph.snapshot());
    }

    #[test]
    fn graphml_round_trip_with_node_attrs() {
        let mut graph = Graph::strict();
        graph.add_node_with_attrs(
            "a".to_owned(),
            BTreeMap::from([("color".to_owned(), "red".into())]),
        );
        graph.add_node_with_attrs(
            "b".to_owned(),
            BTreeMap::from([("color".to_owned(), "blue".into())]),
        );
        graph.add_edge("a", "b").expect("edge add should succeed");

        let mut engine = EdgeListEngine::strict();
        let xml = engine
            .write_graphml(&graph)
            .expect("graphml write should succeed");
        let parsed = engine
            .read_graphml(&xml)
            .expect("graphml read should succeed");
        assert!(parsed.warnings.is_empty());
        assert_eq!(graph.snapshot(), parsed.graph.snapshot());
        assert_eq!(
            parsed.graph.node_attrs("a").unwrap().get("color").unwrap(),
            &CgseValue::String("red".to_owned())
        );
    }

    #[test]
    fn graphml_round_trip_preserves_typed_attrs() {
        let mut graph = Graph::strict();
        graph.add_node_with_attrs(
            "a".to_owned(),
            BTreeMap::from([
                ("count".to_owned(), CgseValue::Int(2)),
                ("ratio".to_owned(), CgseValue::Float(1.5)),
                ("ok".to_owned(), CgseValue::Bool(true)),
            ]),
        );
        graph
            .add_edge_with_attrs(
                "a".to_owned(),
                "b".to_owned(),
                BTreeMap::from([
                    ("weight".to_owned(), CgseValue::Float(2.5)),
                    ("flag".to_owned(), CgseValue::Bool(false)),
                ]),
            )
            .expect("edge add should succeed");

        let mut engine = EdgeListEngine::strict();
        let xml = engine
            .write_graphml(&graph)
            .expect("graphml write should succeed");
        let parsed = engine
            .read_graphml(&xml)
            .expect("graphml read should succeed");

        let attrs = parsed.graph.node_attrs("a").expect("node attrs");
        assert_eq!(attrs.get("count"), Some(&CgseValue::Int(2)));
        assert_eq!(attrs.get("ratio"), Some(&CgseValue::Float(1.5)));
        assert_eq!(attrs.get("ok"), Some(&CgseValue::Bool(true)));

        let edges = parsed.graph.edges_ordered();
        assert_eq!(edges.len(), 1);
        let edge_attrs = &edges[0].attrs;
        assert_eq!(edge_attrs.get("weight"), Some(&CgseValue::Float(2.5)));
        assert_eq!(edge_attrs.get("flag"), Some(&CgseValue::Bool(false)));
    }

    #[test]
    fn write_json_graph_preserves_graph_attrs_and_directed_flag() {
        let mut graph = DiGraph::strict();
        graph.add_edge("a", "b").expect("edge add should succeed");
        let graph_attrs = BTreeMap::from([
            ("name".to_owned(), CgseValue::String("demo".to_owned())),
            ("version".to_owned(), CgseValue::Int(3)),
        ]);

        let mut engine = EdgeListEngine::strict();
        let payload = engine
            .write_digraph_json_graph_with_graph_attrs(&graph, &graph_attrs)
            .expect("json graph write should succeed");

        assert!(payload.contains("\"directed\": true"));
        assert!(payload.contains("\"graph_attrs\""));
        assert!(payload.contains("\"name\": \"demo\""));
        assert!(payload.contains("\"version\": 3"));
    }

    #[test]
    fn read_json_graph_preserves_graph_attrs() {
        let input = r#"{
  "mode": "strict",
  "directed": false,
  "graph_attrs": {
    "name": "demo",
    "version": 3
  },
  "nodes": ["a", "b"],
  "edges": [
    {
      "left": "a",
      "right": "b",
      "attrs": {}
    }
  ]
}"#;

        let mut engine = EdgeListEngine::strict();
        let parsed = engine
            .read_json_graph(input)
            .expect("json graph read should succeed");

        assert_eq!(
            parsed.graph_attrs.get("name"),
            Some(&CgseValue::String("demo".to_owned()))
        );
        assert_eq!(parsed.graph_attrs.get("version"), Some(&CgseValue::Int(3)));
    }

    #[test]
    fn strict_json_missing_directed_allows_graph() {
        let input = r#"{
  "mode": "strict",
  "graph_attrs": {},
  "nodes": ["a", "b"],
  "edges": [
    { "left": "a", "right": "b", "attrs": {} }
  ]
}"#;

        let mut engine = EdgeListEngine::strict();
        let report = engine
            .read_json_graph(input)
            .expect("missing directed should not fail for Graph");
        assert!(report.warnings.is_empty());
        assert_eq!(report.graph.edge_count(), 1);
    }

    #[test]
    fn strict_json_missing_directed_allows_digraph() {
        let input = r#"{
  "mode": "strict",
  "graph_attrs": {},
  "nodes": ["a", "b"],
  "edges": [
    { "left": "a", "right": "b", "attrs": {} }
  ]
}"#;

        let mut engine = EdgeListEngine::strict();
        let report = engine
            .read_digraph_json_graph(input)
            .expect("missing directed should not fail for DiGraph");
        assert!(report.warnings.is_empty());
        assert_eq!(report.graph.edge_count(), 1);
    }

    #[test]
    fn strict_json_directed_mismatch_fails_closed() {
        let input = r#"{
  "mode": "strict",
  "directed": true,
  "graph_attrs": {},
  "nodes": ["a", "b"],
  "edges": [
    { "left": "a", "right": "b", "attrs": {} }
  ]
}"#;

        let mut engine = EdgeListEngine::strict();
        let err = engine
            .read_json_graph(input)
            .expect_err("strict mode should fail on directed json for undirected reader");
        assert!(matches!(err, ReadWriteError::FailClosed { .. }));
    }

    #[test]
    fn hardened_json_directed_mismatch_warns() {
        let input = r#"{
  "mode": "hardened",
  "directed": true,
  "graph_attrs": {},
  "nodes": ["a", "b"],
  "edges": [
    { "left": "a", "right": "b", "attrs": {} }
  ]
}"#;

        let mut engine = EdgeListEngine::hardened();
        let report = engine
            .read_json_graph(input)
            .expect("hardened mode should recover from directed json");
        assert!(!report.warnings.is_empty());
        assert_eq!(report.graph.edge_count(), 1);
    }

    #[test]
    fn strict_json_undirected_mismatch_fails_closed() {
        let input = r#"{
  "mode": "strict",
  "directed": false,
  "graph_attrs": {},
  "nodes": ["a", "b"],
  "edges": [
    { "left": "a", "right": "b", "attrs": {} }
  ]
}"#;

        let mut engine = EdgeListEngine::strict();
        let err = engine
            .read_digraph_json_graph(input)
            .expect_err("strict mode should fail on undirected json for digraph reader");
        assert!(matches!(err, ReadWriteError::FailClosed { .. }));
    }

    #[test]
    fn hardened_json_undirected_mismatch_warns() {
        let input = r#"{
  "mode": "hardened",
  "directed": false,
  "graph_attrs": {},
  "nodes": ["a", "b"],
  "edges": [
    { "left": "a", "right": "b", "attrs": {} }
  ]
}"#;

        let mut engine = EdgeListEngine::hardened();
        let report = engine
            .read_digraph_json_graph(input)
            .expect("hardened mode should recover from undirected json");
        assert!(!report.warnings.is_empty());
        assert_eq!(report.graph.edge_count(), 1);
    }

    #[test]
    fn graphml_declares_directed_handles_single_quotes() {
        let input = r#"<?xml version='1.0' encoding='UTF-8'?>
<graphml xmlns='http://graphml.graphdrawing.org/xmlns'>
  <graph id='G' edgedefault='directed'>
    <node id='a'/>
    <node id='b'/>
    <edge source='a' target='b'/>
  </graph>
</graphml>"#;

        let mut engine = EdgeListEngine::strict();
        assert!(
            engine
                .graphml_declares_directed(input)
                .expect("graphml directed detection should succeed")
        );
    }

    #[test]
    fn graphml_declares_directed_handles_prefixed_graph() {
        let input = r#"<?xml version="1.0" encoding="UTF-8"?>
<g:graphml xmlns:g="http://graphml.graphdrawing.org/xmlns">
  <g:graph id="G" edgedefault="directed">
    <g:node id="a"/>
    <g:node id="b"/>
    <g:edge source="a" target="b"/>
  </g:graph>
</g:graphml>"#;

        let mut engine = EdgeListEngine::strict();
        assert!(
            engine
                .graphml_declares_directed(input)
                .expect("graphml directed detection should succeed")
        );
    }

    #[test]
    fn graphml_declares_directed_hardened_recovers_from_malformed_xml() {
        let mut engine = EdgeListEngine::hardened();
        assert!(
            !engine
                .graphml_declares_directed("<graphml><graph")
                .expect("hardened directed detection should recover")
        );
    }

    #[test]
    fn strict_graphml_directed_mismatch_fails_closed() {
        let input = r#"<?xml version="1.0" encoding="UTF-8"?>
<graphml xmlns="http://graphml.graphdrawing.org/xmlns">
  <graph id="G" edgedefault="directed">
    <node id="a"/>
    <node id="b"/>
    <edge source="a" target="b"/>
  </graph>
</graphml>"#;

        let mut engine = EdgeListEngine::strict();
        let err = engine
            .read_graphml(input)
            .expect_err("strict mode should fail on directed graphml for Graph");
        assert!(matches!(err, ReadWriteError::FailClosed { .. }));
    }

    #[test]
    fn hardened_graphml_directed_mismatch_warns() {
        let input = r#"<?xml version="1.0" encoding="UTF-8"?>
<graphml xmlns="http://graphml.graphdrawing.org/xmlns">
  <graph id="G" edgedefault="directed">
    <node id="a"/>
    <node id="b"/>
    <edge source="a" target="b"/>
  </graph>
</graphml>"#;

        let mut engine = EdgeListEngine::hardened();
        let report = engine
            .read_graphml(input)
            .expect("hardened mode should recover from directed graphml");
        assert!(!report.warnings.is_empty());
        assert_eq!(report.graph.edge_count(), 1);
    }

    #[test]
    fn strict_graphml_undirected_mismatch_fails_closed() {
        let input = r#"<?xml version="1.0" encoding="UTF-8"?>
<graphml xmlns="http://graphml.graphdrawing.org/xmlns">
  <graph id="G" edgedefault="undirected">
    <node id="a"/>
    <node id="b"/>
    <edge source="a" target="b"/>
  </graph>
</graphml>"#;

        let mut engine = EdgeListEngine::strict();
        let err = engine
            .read_digraph_graphml(input)
            .expect_err("strict mode should fail on undirected graphml for DiGraph");
        assert!(matches!(err, ReadWriteError::FailClosed { .. }));
    }

    #[test]
    fn hardened_graphml_undirected_mismatch_warns() {
        let input = r#"<?xml version="1.0" encoding="UTF-8"?>
<graphml xmlns="http://graphml.graphdrawing.org/xmlns">
  <graph id="G" edgedefault="undirected">
    <node id="a"/>
    <node id="b"/>
    <edge source="a" target="b"/>
  </graph>
</graphml>"#;

        let mut engine = EdgeListEngine::hardened();
        let report = engine
            .read_digraph_graphml(input)
            .expect("hardened mode should recover from undirected graphml");
        assert!(!report.warnings.is_empty());
        assert_eq!(report.graph.edge_count(), 1);
    }

    #[test]
    fn strict_graphml_invalid_edgedefault_fails_closed() {
        let input = r#"<?xml version="1.0" encoding="UTF-8"?>
<graphml xmlns="http://graphml.graphdrawing.org/xmlns">
  <graph id="G" edgedefault="sideways">
    <node id="a"/>
    <node id="b"/>
    <edge source="a" target="b"/>
  </graph>
</graphml>"#;

        let mut engine = EdgeListEngine::strict();
        let err = engine
            .read_graphml(input)
            .expect_err("strict mode should fail on invalid edgedefault");
        assert!(matches!(err, ReadWriteError::FailClosed { .. }));
    }

    #[test]
    fn hardened_graphml_invalid_edgedefault_warns() {
        let input = r#"<?xml version="1.0" encoding="UTF-8"?>
<graphml xmlns="http://graphml.graphdrawing.org/xmlns">
  <graph id="G" edgedefault="sideways">
    <node id="a"/>
    <node id="b"/>
    <edge source="a" target="b"/>
  </graph>
</graphml>"#;

        let mut engine = EdgeListEngine::hardened();
        let report = engine
            .read_graphml(input)
            .expect("hardened mode should recover from invalid edgedefault");
        assert!(!report.warnings.is_empty());
        assert_eq!(report.graph.edge_count(), 1);
    }

    #[test]
    fn strict_graphml_missing_edgedefault_fails_closed() {
        let input = r#"<?xml version="1.0" encoding="UTF-8"?>
<graphml xmlns="http://graphml.graphdrawing.org/xmlns">
  <graph id="G">
    <node id="a"/>
    <node id="b"/>
    <edge source="a" target="b"/>
  </graph>
</graphml>"#;

        let mut engine = EdgeListEngine::strict();
        let err = engine
            .read_graphml(input)
            .expect_err("strict mode should fail on missing edgedefault");
        assert!(matches!(err, ReadWriteError::FailClosed { .. }));
    }

    #[test]
    fn hardened_graphml_missing_edgedefault_warns() {
        let input = r#"<?xml version="1.0" encoding="UTF-8"?>
<graphml xmlns="http://graphml.graphdrawing.org/xmlns">
  <graph id="G">
    <node id="a"/>
    <node id="b"/>
    <edge source="a" target="b"/>
  </graph>
</graphml>"#;

        let mut engine = EdgeListEngine::hardened();
        let report = engine
            .read_graphml(input)
            .expect("hardened mode should recover from missing edgedefault");
        assert!(!report.warnings.is_empty());
        assert_eq!(report.graph.edge_count(), 1);
    }

    #[test]
    fn gml_declares_directed_ignores_attribute_text() {
        let input = r#"graph [
  label "mentions directed 1"
  directed 0
  node [
    id 0
    label "a"
  ]
]"#;

        let mut engine = EdgeListEngine::strict();
        assert!(
            !engine
                .gml_declares_directed(input)
                .expect("gml directed detection should succeed")
        );
    }

    #[test]
    fn gml_declares_directed_detects_late_header() {
        let input = r#"graph [
  node [
    id 0
    label "a"
  ]
  directed 1
  edge [
    source 0
    target 0
  ]
]"#;

        let mut engine = EdgeListEngine::strict();
        assert!(
            engine
                .gml_declares_directed(input)
                .expect("gml directed detection should succeed")
        );
    }

    #[test]
    fn strict_gml_directed_mismatch_fails_closed() {
        let input = r#"graph [
  directed 1
  node [
    id 0
    label "a"
  ]
  node [
    id 1
    label "b"
  ]
  edge [
    source 0
    target 1
  ]
]"#;

        let mut engine = EdgeListEngine::strict();
        let err = engine
            .read_gml(input)
            .expect_err("strict mode should fail on directed gml for Graph");
        assert!(matches!(err, ReadWriteError::FailClosed { .. }));
    }

    #[test]
    fn hardened_gml_directed_mismatch_warns() {
        let input = r#"graph [
  directed 1
  node [
    id 0
    label "a"
  ]
  node [
    id 1
    label "b"
  ]
  edge [
    source 0
    target 1
  ]
]"#;

        let mut engine = EdgeListEngine::hardened();
        let report = engine
            .read_gml(input)
            .expect("hardened mode should recover from directed gml");
        assert!(!report.warnings.is_empty());
        assert_eq!(report.graph.edge_count(), 1);
    }

    #[test]
    fn strict_gml_invalid_directed_value_fails_closed() {
        let input = r#"graph [
  directed 2
  node [
    id 0
    label "a"
  ]
  node [
    id 1
    label "b"
  ]
  edge [
    source 0
    target 1
  ]
]"#;

        let mut engine = EdgeListEngine::strict();
        let err = engine
            .read_gml(input)
            .expect_err("strict gml should fail on invalid directed value");
        assert!(matches!(err, ReadWriteError::FailClosed { .. }));
    }

    #[test]
    fn hardened_gml_invalid_directed_value_warns() {
        let input = r#"graph [
  directed 2
  node [
    id 0
    label "a"
  ]
  node [
    id 1
    label "b"
  ]
  edge [
    source 0
    target 1
  ]
]"#;

        let mut engine = EdgeListEngine::hardened();
        let report = engine
            .read_gml(input)
            .expect("hardened gml should recover from invalid directed value");
        assert!(report.warnings.iter().any(
            |warning| warning.contains("directed value") && warning.contains("must be 0 or 1")
        ));
    }

    #[test]
    fn strict_gml_undirected_mismatch_fails_closed() {
        let input = r#"graph [
  directed 0
  node [
    id 0
    label "a"
  ]
  node [
    id 1
    label "b"
  ]
  edge [
    source 0
    target 1
  ]
]"#;

        let mut engine = EdgeListEngine::strict();
        let err = engine
            .read_digraph_gml(input)
            .expect_err("strict mode should fail on undirected gml for DiGraph");
        assert!(matches!(err, ReadWriteError::FailClosed { .. }));
    }

    #[test]
    fn hardened_gml_undirected_mismatch_warns() {
        let input = r#"graph [
  directed 0
  node [
    id 0
    label "a"
  ]
  node [
    id 1
    label "b"
  ]
  edge [
    source 0
    target 1
  ]
]"#;

        let mut engine = EdgeListEngine::hardened();
        let report = engine
            .read_digraph_gml(input)
            .expect("hardened mode should recover from undirected gml");
        assert!(!report.warnings.is_empty());
        assert_eq!(report.graph.edge_count(), 1);
    }

    #[test]
    fn read_gml_preserves_graph_attrs() {
        let input = r#"graph [
  directed 0
  label "demo"
  owner "qa"
  node [
    id 0
    label "a"
  ]
  node [
    id 1
    label "b"
  ]
  edge [
    source 0
    target 1
  ]
]"#;

        let mut engine = EdgeListEngine::strict();
        let parsed = engine.read_gml(input).expect("gml read should succeed");

        assert_eq!(
            parsed.graph_attrs.get("label"),
            Some(&CgseValue::String("demo".to_owned()))
        );
        assert_eq!(
            parsed.graph_attrs.get("owner"),
            Some(&CgseValue::String("qa".to_owned()))
        );
    }

    #[test]
    fn gml_escaped_quotes_preserved_in_label() {
        let input = r#"graph [
  node [
    id 1
    label "\"quoted\""
  ]
]"#;

        let mut engine = EdgeListEngine::strict();
        let report = engine.read_gml(input).expect("gml read should succeed");
        let nodes = report.graph.nodes_ordered();
        assert_eq!(nodes, vec!["\"quoted\""]);
    }

    #[test]
    fn gml_unescape_numeric_entity_decodes() {
        let input = r#"graph [
  node [
    id 1
    label "fish &#38; chips"
  ]
]"#;

        let mut engine = EdgeListEngine::strict();
        let report = engine.read_gml(input).expect("gml read should succeed");
        let nodes = report.graph.nodes_ordered();
        assert_eq!(nodes, vec!["fish & chips"]);
    }

    #[test]
    fn gml_unescape_named_entity_decodes() {
        let input = r#"graph [
  node [
    id 1
    label "bread &amp; butter &quot;ok&quot; &lt;tag&gt; &apos;x&apos;"
  ]
]"#;

        let mut engine = EdgeListEngine::strict();
        let report = engine.read_gml(input).expect("gml read should succeed");
        let nodes = report.graph.nodes_ordered();
        assert_eq!(nodes, vec!["bread & butter \"ok\" <tag> 'x'"]);
    }

    #[test]
    fn gml_node_missing_label_strict_fails_closed() {
        let input = r#"graph [
  node [
    id 0
  ]
]"#;

        let mut engine = EdgeListEngine::strict();
        let err = engine
            .read_gml(input)
            .expect_err("strict gml should fail on node missing label");
        assert!(matches!(err, ReadWriteError::FailClosed { .. }));
    }

    #[test]
    fn gml_node_missing_label_hardened_recovers_with_id_label() {
        let input = r#"graph [
  node [
    id 0
  ]
]"#;

        let mut engine = EdgeListEngine::hardened();
        let report = engine.read_gml(input).expect("hardened gml should recover");
        assert!(!report.warnings.is_empty());
        assert_eq!(report.graph.node_count(), 1);
        assert_eq!(report.graph.nodes_ordered(), vec!["0"]);
    }

    #[test]
    fn gml_node_duplicate_id_strict_fails_closed() {
        let input = r#"graph [
  node [
    id 0
    label "a"
  ]
  node [
    id 0
    label "b"
  ]
]"#;

        let mut engine = EdgeListEngine::strict();
        let err = engine
            .read_gml(input)
            .expect_err("strict gml should fail on duplicate node id");
        assert!(matches!(err, ReadWriteError::FailClosed { .. }));
    }

    #[test]
    fn gml_node_duplicate_id_hardened_warns_and_skips() {
        let input = r#"graph [
  node [
    id 0
    label "a"
  ]
  node [
    id 0
    label "b"
  ]
]"#;

        let mut engine = EdgeListEngine::hardened();
        let report = engine.read_gml(input).expect("hardened gml should recover");
        assert!(!report.warnings.is_empty());
        assert_eq!(report.graph.node_count(), 1);
        assert_eq!(report.graph.nodes_ordered(), vec!["a"]);
    }

    #[test]
    fn gml_node_duplicate_label_strict_fails_closed() {
        let input = r#"graph [
  node [
    id 0
    label "a"
  ]
  node [
    id 1
    label "a"
  ]
]"#;

        let mut engine = EdgeListEngine::strict();
        let err = engine
            .read_gml(input)
            .expect_err("strict gml should fail on duplicate node label");
        assert!(matches!(err, ReadWriteError::FailClosed { .. }));
    }

    #[test]
    fn gml_node_duplicate_label_hardened_warns_and_skips() {
        let input = r#"graph [
  node [
    id 0
    label "a"
  ]
  node [
    id 1
    label "a"
  ]
]"#;

        let mut engine = EdgeListEngine::hardened();
        let report = engine.read_gml(input).expect("hardened gml should recover");
        assert!(!report.warnings.is_empty());
        assert_eq!(report.graph.node_count(), 1);
        assert_eq!(report.graph.nodes_ordered(), vec!["a"]);
    }

    #[test]
    fn gml_node_missing_id_strict_fails_closed() {
        let input = r#"graph [
  directed 0
  node [
    label "a"
  ]
]"#;

        let mut engine = EdgeListEngine::strict();
        let err = engine
            .read_gml(input)
            .expect_err("strict gml should fail on node missing id");
        assert!(matches!(err, ReadWriteError::FailClosed { .. }));
    }

    #[test]
    fn gml_node_missing_id_hardened_warns_and_skips() {
        let input = r#"graph [
  directed 0
  node [
    label "a"
  ]
]"#;

        let mut engine = EdgeListEngine::hardened();
        let report = engine.read_gml(input).expect("hardened gml should recover");
        assert!(!report.warnings.is_empty());
        assert_eq!(report.graph.node_count(), 0);
    }

    #[test]
    fn gml_node_missing_closing_bracket_strict_fails_closed() {
        let input = r#"graph [
  node [
    id 1
    label "a"
"#;

        let mut engine = EdgeListEngine::strict();
        let err = engine
            .read_gml(input)
            .expect_err("strict gml should fail on missing closing bracket");
        assert!(matches!(err, ReadWriteError::FailClosed { .. }));
    }

    #[test]
    fn gml_node_missing_closing_bracket_hardened_warns_and_skips() {
        let input = r#"graph [
  node [
    id 1
    label "a"
"#;

        let mut engine = EdgeListEngine::hardened();
        let report = engine.read_gml(input).expect("hardened gml should recover");
        assert!(!report.warnings.is_empty());
        assert_eq!(report.graph.node_count(), 0);
    }

    #[test]
    fn gml_node_invalid_id_strict_fails_closed() {
        let input = r#"graph [
  directed 0
  node [
    id abc
    label "a"
  ]
]"#;

        let mut engine = EdgeListEngine::strict();
        let err = engine
            .read_gml(input)
            .expect_err("strict gml should fail on invalid node id");
        assert!(matches!(err, ReadWriteError::FailClosed { .. }));
    }

    #[test]
    fn gml_node_invalid_id_hardened_warns_and_skips() {
        let input = r#"graph [
  directed 0
  node [
    id abc
    label "a"
  ]
]"#;

        let mut engine = EdgeListEngine::hardened();
        let report = engine.read_gml(input).expect("hardened gml should recover");
        assert!(!report.warnings.is_empty());
        assert_eq!(report.graph.node_count(), 0);
    }

    #[test]
    fn gml_edge_missing_target_strict_fails_closed() {
        let input = r#"graph [
  directed 0
  node [
    id 0
    label "a"
  ]
  node [
    id 1
    label "b"
  ]
  edge [
    source 0
  ]
]"#;

        let mut engine = EdgeListEngine::strict();
        let err = engine
            .read_gml(input)
            .expect_err("strict gml should fail on edge missing target");
        assert!(matches!(err, ReadWriteError::FailClosed { .. }));
    }

    #[test]
    fn gml_edge_missing_target_hardened_warns_and_skips() {
        let input = r#"graph [
  directed 0
  node [
    id 0
    label "a"
  ]
  node [
    id 1
    label "b"
  ]
  edge [
    source 0
  ]
]"#;

        let mut engine = EdgeListEngine::hardened();
        let report = engine.read_gml(input).expect("hardened gml should recover");
        assert!(!report.warnings.is_empty());
        assert_eq!(report.graph.node_count(), 2);
        assert_eq!(report.graph.edge_count(), 0);
    }

    #[test]
    fn gml_edge_unknown_endpoint_strict_fails_closed() {
        let input = r#"graph [
  directed 0
  node [
    id 0
    label "a"
  ]
  edge [
    source 0
    target 1
  ]
]"#;

        let mut engine = EdgeListEngine::strict();
        let err = engine
            .read_gml(input)
            .expect_err("strict gml should fail on unknown edge endpoint");
        assert!(matches!(err, ReadWriteError::FailClosed { .. }));
    }

    #[test]
    fn gml_edge_unknown_endpoint_hardened_recovers_creates_node() {
        let input = r#"graph [
  directed 0
  node [
    id 0
    label "a"
  ]
  edge [
    source 0
    target 1
  ]
]"#;

        let mut engine = EdgeListEngine::hardened();
        let report = engine.read_gml(input).expect("hardened gml should recover");
        assert!(!report.warnings.is_empty());
        assert_eq!(report.graph.node_count(), 2);
        assert_eq!(report.graph.edge_count(), 1);
        assert_eq!(report.graph.nodes_ordered(), vec!["a", "1"]);
    }

    #[test]
    fn read_graphml_preserves_graph_attrs() {
        let input = r#"<?xml version="1.0" encoding="UTF-8"?>
<graphml xmlns="http://graphml.graphdrawing.org/xmlns">
  <key id="g0" for="graph" attr.name="name" attr.type="string"/>
  <key id="g1" for="graph" attr.name="version" attr.type="int"/>
  <graph id="G" edgedefault="undirected">
    <data key="g0">demo</data>
    <data key="g1">3</data>
    <node id="a"/>
    <node id="b"/>
    <edge source="a" target="b"/>
  </graph>
</graphml>"#;

        let mut engine = EdgeListEngine::strict();
        let parsed = engine
            .read_graphml(input)
            .expect("graphml read should succeed");

        assert_eq!(
            parsed.graph_attrs.get("name"),
            Some(&CgseValue::String("demo".to_owned()))
        );
        assert_eq!(parsed.graph_attrs.get("version"), Some(&CgseValue::Int(3)));
    }

    #[test]
    fn graphml_data_missing_key_strict_fails_closed() {
        let input = r#"<?xml version="1.0" encoding="UTF-8"?>
<graphml xmlns="http://graphml.graphdrawing.org/xmlns">
  <graph edgedefault="undirected">
    <node id="n0">
      <data>oops</data>
    </node>
  </graph>
</graphml>"#;

        let mut engine = EdgeListEngine::strict();
        let err = engine
            .read_graphml(input)
            .expect_err("strict mode should fail on missing data key");
        assert!(matches!(err, ReadWriteError::FailClosed { .. }));
    }

    #[test]
    fn graphml_data_missing_key_hardened_warns_and_skips() {
        let input = r#"<?xml version="1.0" encoding="UTF-8"?>
<graphml xmlns="http://graphml.graphdrawing.org/xmlns">
  <graph edgedefault="undirected">
    <node id="n0">
      <data>oops</data>
    </node>
  </graph>
</graphml>"#;

        let mut engine = EdgeListEngine::hardened();
        let report = engine
            .read_graphml(input)
            .expect("hardened mode should recover");
        assert!(!report.warnings.is_empty());
        let attrs = report.graph.node_attrs("n0").expect("node should exist");
        assert!(attrs.is_empty());
    }

    #[test]
    fn graphml_node_attr_parse_error_strict_fails_closed() {
        let input = r#"<?xml version="1.0" encoding="UTF-8"?>
<graphml xmlns="http://graphml.graphdrawing.org/xmlns">
  <graph edgedefault="undirected">
    <node id="n0" bad/>
  </graph>
</graphml>"#;

        let mut engine = EdgeListEngine::strict();
        let err = engine
            .read_graphml(input)
            .expect_err("strict mode should fail on malformed node attribute");
        assert!(matches!(err, ReadWriteError::FailClosed { .. }));
    }

    #[test]
    fn graphml_node_attr_parse_error_hardened_warns_and_skips() {
        let input = r#"<?xml version="1.0" encoding="UTF-8"?>
<graphml xmlns="http://graphml.graphdrawing.org/xmlns">
  <graph edgedefault="undirected">
    <node id="n0" bad/>
  </graph>
</graphml>"#;

        let mut engine = EdgeListEngine::hardened();
        let report = engine
            .read_graphml(input)
            .expect("hardened mode should recover");
        assert!(!report.warnings.is_empty());
        assert_eq!(report.graph.node_count(), 0);
    }

    #[test]
    fn graphml_edge_attr_parse_error_strict_fails_closed() {
        let input = r#"<?xml version="1.0" encoding="UTF-8"?>
<graphml xmlns="http://graphml.graphdrawing.org/xmlns">
  <graph edgedefault="undirected">
    <node id="a"/>
    <node id="b"/>
    <edge source="a" target="b" bad/>
  </graph>
</graphml>"#;

        let mut engine = EdgeListEngine::strict();
        let err = engine
            .read_graphml(input)
            .expect_err("strict mode should fail on malformed edge attribute");
        assert!(matches!(err, ReadWriteError::FailClosed { .. }));
    }

    #[test]
    fn graphml_edge_attr_parse_error_hardened_warns_and_skips() {
        let input = r#"<?xml version="1.0" encoding="UTF-8"?>
<graphml xmlns="http://graphml.graphdrawing.org/xmlns">
  <graph edgedefault="undirected">
    <node id="a"/>
    <node id="b"/>
    <edge source="a" target="b" bad/>
  </graph>
</graphml>"#;

        let mut engine = EdgeListEngine::hardened();
        let report = engine
            .read_graphml(input)
            .expect("hardened mode should recover");
        assert!(!report.warnings.is_empty());
        assert_eq!(report.graph.node_count(), 2);
        assert_eq!(report.graph.edge_count(), 0);
    }

    #[test]
    fn graphml_data_unknown_key_strict_fails_closed() {
        let input = r#"<?xml version="1.0" encoding="UTF-8"?>
<graphml xmlns="http://graphml.graphdrawing.org/xmlns">
  <graph edgedefault="undirected">
    <node id="n0">
      <data key="d0">oops</data>
    </node>
  </graph>
</graphml>"#;

        let mut engine = EdgeListEngine::strict();
        let err = engine
            .read_graphml(input)
            .expect_err("strict mode should fail on unknown data key");
        assert!(matches!(err, ReadWriteError::FailClosed { .. }));
    }

    #[test]
    fn graphml_data_unknown_key_hardened_warns_and_skips() {
        let input = r#"<?xml version="1.0" encoding="UTF-8"?>
<graphml xmlns="http://graphml.graphdrawing.org/xmlns">
  <graph edgedefault="undirected">
    <node id="n0">
      <data key="d0">oops</data>
    </node>
  </graph>
</graphml>"#;

        let mut engine = EdgeListEngine::hardened();
        let report = engine
            .read_graphml(input)
            .expect("hardened mode should recover");
        assert!(!report.warnings.is_empty());
        let attrs = report.graph.node_attrs("n0").expect("node should exist");
        assert!(attrs.is_empty());
    }

    #[test]
    fn graphml_data_scope_mismatch_strict_fails_closed() {
        let input = r#"<?xml version="1.0" encoding="UTF-8"?>
<graphml xmlns="http://graphml.graphdrawing.org/xmlns">
  <key id="d0" for="edge" attr.name="weight" attr.type="int"/>
  <graph edgedefault="undirected">
    <node id="n0">
      <data key="d0">1</data>
    </node>
  </graph>
</graphml>"#;

        let mut engine = EdgeListEngine::strict();
        let err = engine
            .read_graphml(input)
            .expect_err("strict mode should fail on scope mismatch");
        assert!(matches!(err, ReadWriteError::FailClosed { .. }));
    }

    #[test]
    fn graphml_data_scope_mismatch_hardened_warns_and_skips() {
        let input = r#"<?xml version="1.0" encoding="UTF-8"?>
<graphml xmlns="http://graphml.graphdrawing.org/xmlns">
  <key id="d0" for="edge" attr.name="weight" attr.type="int"/>
  <graph edgedefault="undirected">
    <node id="n0">
      <data key="d0">1</data>
    </node>
  </graph>
</graphml>"#;

        let mut engine = EdgeListEngine::hardened();
        let report = engine
            .read_graphml(input)
            .expect("hardened mode should recover");
        assert!(!report.warnings.is_empty());
        let attrs = report.graph.node_attrs("n0").expect("node should exist");
        assert!(attrs.is_empty());
    }

    #[test]
    fn read_graphml_handles_prefixed_elements() {
        let input = r#"<?xml version="1.0" encoding="UTF-8"?>
<g:graphml xmlns:g="http://graphml.graphdrawing.org/xmlns">
  <g:key id="d0" for="node" attr.name="color" attr.type="string"/>
  <g:graph id="G" edgedefault="undirected">
    <g:node id="n0">
      <g:data key="d0">red</g:data>
    </g:node>
  </g:graph>
</g:graphml>"#;

        let mut engine = EdgeListEngine::strict();
        let parsed = engine
            .read_graphml(input)
            .expect("graphml read should succeed");

        assert!(parsed.warnings.is_empty());
        assert_eq!(parsed.graph.node_count(), 1);
        let attrs = parsed.graph.node_attrs("n0").expect("node should exist");
        assert_eq!(
            attrs.get("color"),
            Some(&CgseValue::String("red".to_owned()))
        );
    }

    #[test]
    fn write_gml_preserves_graph_attrs() {
        let mut graph = Graph::strict();
        graph.add_edge("a", "b").expect("edge add should succeed");
        let graph_attrs = BTreeMap::from([
            ("label".to_owned(), CgseValue::String("demo".to_owned())),
            ("owner".to_owned(), CgseValue::String("qa".to_owned())),
        ]);

        let mut engine = EdgeListEngine::strict();
        let gml = engine
            .write_gml_with_graph_attrs(&graph, &graph_attrs)
            .expect("gml write should succeed");

        assert!(gml.contains("  label \"demo\"\n"));
        assert!(gml.contains("  owner \"qa\"\n"));
    }

    #[test]
    fn gml_round_trip_preserves_entities() {
        let mut graph = Graph::strict();
        graph
            .add_edge("caf\u{00e9} & tea", "b")
            .expect("edge add should succeed");
        let mut engine = EdgeListEngine::strict();
        let gml = engine.write_gml(&graph).expect("gml write should succeed");
        assert!(gml.contains("caf&#233; &#38; tea"));

        let parsed = engine.read_gml(&gml).expect("gml read should succeed");
        assert!(parsed.graph.has_node("caf\u{00e9} & tea"));
    }

    #[test]
    fn write_gml_preserves_string_types_and_scalars() {
        let mut graph = Graph::strict();
        graph.add_edge("a", "b").expect("edge add should succeed");
        let graph_attrs = BTreeMap::from([
            ("enabled".to_owned(), CgseValue::Bool(true)),
            ("ratio".to_owned(), CgseValue::Float(1.0)),
            ("version".to_owned(), CgseValue::String("01".to_owned())),
        ]);

        let mut engine = EdgeListEngine::strict();
        let gml = engine
            .write_gml_with_graph_attrs(&graph, &graph_attrs)
            .expect("gml write should succeed");

        assert!(gml.contains("  enabled 1\n"));
        assert!(gml.contains("  ratio 1.0\n"));
        assert!(gml.contains("  version \"01\"\n"));
    }

    #[test]
    fn write_graphml_preserves_graph_attrs() {
        let mut graph = Graph::strict();
        graph.add_edge("a", "b").expect("edge add should succeed");
        let graph_attrs = BTreeMap::from([
            ("name".to_owned(), CgseValue::String("demo".to_owned())),
            ("version".to_owned(), CgseValue::Int(3)),
            ("public".to_owned(), CgseValue::Bool(true)),
        ]);

        let mut engine = EdgeListEngine::strict();
        let xml = engine
            .write_graphml_with_graph_attrs(&graph, &graph_attrs)
            .expect("graphml write should succeed");

        assert!(xml.contains(r#"<key id="g0" for="graph" attr.name="name" attr.type="string"/>"#));
        assert!(
            xml.contains(r#"<key id="g1" for="graph" attr.name="public" attr.type="boolean"/>"#)
        );
        assert!(xml.contains(r#"<key id="g2" for="graph" attr.name="version" attr.type="int"/>"#));
        assert!(xml.contains(r#"<data key="g0">demo</data>"#));
        assert!(xml.contains(r#"<data key="g1">true</data>"#));
        assert!(xml.contains(r#"<data key="g2">3</data>"#));
    }

    #[test]
    fn write_graphml_emits_default_keys() {
        let mut graph = Graph::strict();
        graph.add_edge("a", "b").expect("edge add should succeed");
        let node_defaults =
            BTreeMap::from([("color".to_owned(), CgseValue::String("yellow".to_owned()))]);
        let edge_defaults = BTreeMap::from([("weight".to_owned(), CgseValue::Int(7))]);
        let graph_attrs = BTreeMap::from([
            ("node_default".to_owned(), CgseValue::Map(node_defaults)),
            ("edge_default".to_owned(), CgseValue::Map(edge_defaults)),
        ]);

        let mut engine = EdgeListEngine::strict();
        let xml = engine
            .write_graphml_with_graph_attrs(&graph, &graph_attrs)
            .expect("graphml write should succeed");

        assert!(xml.contains(r#"attr.name="color""#));
        assert!(xml.contains(r#"<default>yellow</default>"#));
        assert!(xml.contains(r#"attr.name="weight""#));
        assert!(xml.contains(r#"<default>7</default>"#));
        assert!(!xml.contains("node_default"));
        assert!(!xml.contains("edge_default"));
    }

    #[test]
    fn graphml_strict_fails_closed_for_malformed_xml() {
        let mut engine = EdgeListEngine::strict();
        let err = engine
            .read_graphml("<not-valid-graphml")
            .expect_err("strict graphml parsing should fail closed for malformed xml");
        assert!(matches!(err, ReadWriteError::FailClosed { .. }));
    }

    #[test]
    fn graphml_hardened_recovers_for_malformed_xml() {
        let mut engine = EdgeListEngine::hardened();
        let report = engine
            .read_graphml("<not-valid-graphml")
            .expect("hardened mode should recover");
        assert!(!report.warnings.is_empty());
    }

    #[test]
    fn graphml_invalid_entity_strict_fails_closed() {
        let graphml = r#"
<graphml>
  <key id="d0" for="node" attr.name="label" attr.type="string"/>
  <graph edgedefault="undirected">
    <node id="n0">
      <data key="d0">&bogus;</data>
    </node>
  </graph>
</graphml>
"#;
        let mut engine = EdgeListEngine::strict();
        let err = engine
            .read_graphml(graphml)
            .expect_err("strict mode should fail closed on invalid entity");
        assert!(matches!(err, ReadWriteError::FailClosed { .. }));
    }

    #[test]
    fn graphml_invalid_entity_hardened_warns_and_skips_attr() {
        let graphml = r#"
<graphml>
  <key id="d0" for="node" attr.name="label" attr.type="string"/>
  <graph edgedefault="undirected">
    <node id="n0">
      <data key="d0">&bogus;</data>
    </node>
  </graph>
</graphml>
"#;
        let mut engine = EdgeListEngine::hardened();
        let report = engine
            .read_graphml(graphml)
            .expect("hardened mode should recover from invalid entity");
        assert!(!report.warnings.is_empty());
        assert_eq!(report.graph.node_count(), 1);
        let attrs = report.graph.node_attrs("n0").expect("node should exist");
        assert!(attrs.is_empty());
    }

    #[test]
    fn graphml_typed_double_parses_float() {
        let graphml = r#"
<graphml>
  <key id="d0" for="node" attr.name="weight" attr.type="double"/>
  <graph edgedefault="undirected">
    <node id="n0">
      <data key="d0">1</data>
    </node>
  </graph>
</graphml>
"#;
        let mut engine = EdgeListEngine::strict();
        let report = engine
            .read_graphml(graphml)
            .expect("typed double should parse");
        let attrs = report.graph.node_attrs("n0").expect("node should exist");
        assert_eq!(attrs.get("weight"), Some(&CgseValue::Float(1.0)));
    }

    #[test]
    fn graphml_missing_attr_type_defaults_to_string() {
        let graphml = r#"
<graphml>
  <key id="d0" for="node" attr.name="count"/>
  <graph edgedefault="undirected">
    <node id="n0">
      <data key="d0">1</data>
    </node>
  </graph>
</graphml>
"#;
        let mut engine = EdgeListEngine::strict();
        let report = engine
            .read_graphml(graphml)
            .expect("missing attr.type should default to string");
        assert!(!report.warnings.is_empty());
        let attrs = report.graph.node_attrs("n0").expect("node should exist");
        assert_eq!(attrs.get("count"), Some(&CgseValue::String("1".to_owned())));
    }

    #[test]
    fn graphml_missing_attr_name_strict_fails_closed() {
        let graphml = r#"
<graphml>
  <key id="d0" for="node" attr.type="int"/>
  <graph edgedefault="undirected">
    <node id="n0">
      <data key="d0">1</data>
    </node>
  </graph>
</graphml>
"#;
        let mut engine = EdgeListEngine::strict();
        let err = engine
            .read_graphml(graphml)
            .expect_err("strict mode should fail on missing attr.name");
        assert!(matches!(err, ReadWriteError::FailClosed { .. }));
    }

    #[test]
    fn graphml_missing_attr_name_hardened_warns_and_skips_key() {
        let graphml = r#"
<graphml>
  <key id="d0" for="node" attr.type="int"/>
  <graph edgedefault="undirected">
    <node id="n0">
      <data key="d0">1</data>
    </node>
  </graph>
</graphml>
"#;
        let mut engine = EdgeListEngine::hardened();
        let report = engine
            .read_graphml(graphml)
            .expect("hardened mode should recover from missing attr.name");
        assert!(!report.warnings.is_empty());
        let attrs = report.graph.node_attrs("n0").expect("node should exist");
        assert!(attrs.is_empty());
    }

    #[test]
    fn graphml_key_default_applies_to_node_attrs() {
        let graphml = r#"
<graphml>
  <key id="d0" for="node" attr.name="color" attr.type="string">
    <default>yellow</default>
  </key>
  <graph edgedefault="undirected">
    <node id="n0"/>
  </graph>
</graphml>
"#;
        let mut engine = EdgeListEngine::strict();
        let report = engine
            .read_graphml(graphml)
            .expect("graphml default for node should parse");
        let attrs = report.graph.node_attrs("n0").expect("node should exist");
        assert_eq!(
            attrs.get("color"),
            Some(&CgseValue::String("yellow".to_owned()))
        );
    }

    #[test]
    fn graphml_key_default_applies_to_edge_attrs() {
        let graphml = r#"
<graphml>
  <key id="d0" for="edge" attr.name="weight" attr.type="int">
    <default>7</default>
  </key>
  <graph edgedefault="undirected">
    <node id="n0"/>
    <node id="n1"/>
    <edge source="n0" target="n1"/>
  </graph>
</graphml>
"#;
        let mut engine = EdgeListEngine::strict();
        let report = engine
            .read_graphml(graphml)
            .expect("graphml default for edge should parse");
        let attrs = report
            .graph
            .edge_attrs("n0", "n1")
            .expect("edge should exist");
        assert_eq!(attrs.get("weight"), Some(&CgseValue::Int(7)));
    }

    #[test]
    fn graphml_defaults_apply_when_keys_after_graph() {
        let graphml = r#"
<graphml>
  <graph edgedefault="undirected">
    <node id="n0"/>
    <node id="n1"/>
    <edge source="n0" target="n1"/>
  </graph>
  <key id="d0" for="node" attr.name="color" attr.type="string">
    <default>yellow</default>
  </key>
  <key id="d1" for="edge" attr.name="weight" attr.type="int">
    <default>7</default>
  </key>
</graphml>
"#;
        let mut engine = EdgeListEngine::strict();
        let report = engine
            .read_graphml(graphml)
            .expect("graphml defaults should apply after graph");
        let node_attrs = report.graph.node_attrs("n0").expect("node should exist");
        assert_eq!(
            node_attrs.get("color"),
            Some(&CgseValue::String("yellow".to_owned()))
        );
        let edge_attrs = report
            .graph
            .edge_attrs("n0", "n1")
            .expect("edge should exist");
        assert_eq!(edge_attrs.get("weight"), Some(&CgseValue::Int(7)));
    }

    #[test]
    fn graphml_defaults_recorded_in_graph_attrs() {
        let graphml = r#"
<graphml>
  <key id="d0" for="node" attr.name="color" attr.type="string">
    <default>yellow</default>
  </key>
  <key id="d1" for="edge" attr.name="weight" attr.type="int">
    <default>7</default>
  </key>
  <graph edgedefault="undirected">
    <node id="n0"/>
    <node id="n1"/>
    <edge source="n0" target="n1"/>
  </graph>
</graphml>
"#;
        let mut engine = EdgeListEngine::strict();
        let report = engine
            .read_graphml(graphml)
            .expect("graphml defaults should parse");
        let node_default = report
            .graph_attrs
            .get("node_default")
            .expect("node_default should exist");
        assert!(
            matches!(node_default, CgseValue::Map(_)),
            "node_default should be map"
        );
        if let CgseValue::Map(map) = node_default {
            assert_eq!(
                map.get("color"),
                Some(&CgseValue::String("yellow".to_owned()))
            );
        }
        let edge_default = report
            .graph_attrs
            .get("edge_default")
            .expect("edge_default should exist");
        assert!(
            matches!(edge_default, CgseValue::Map(_)),
            "edge_default should be map"
        );
        if let CgseValue::Map(map) = edge_default {
            assert_eq!(map.get("weight"), Some(&CgseValue::Int(7)));
        }
    }

    #[test]
    fn graphml_graph_default_applies_to_graph_attrs() {
        let graphml = r#"
<graphml>
  <graph edgedefault="undirected">
    <node id="n0"/>
  </graph>
  <key id="g0" for="graph" attr.name="creator" attr.type="string">
    <default>nx</default>
  </key>
</graphml>
"#;
        let mut engine = EdgeListEngine::strict();
        let report = engine
            .read_graphml(graphml)
            .expect("graphml graph default should apply");
        assert_eq!(
            report.graph_attrs.get("creator"),
            Some(&CgseValue::String("nx".to_owned()))
        );
    }

    #[test]
    fn graphml_edge_id_attribute_preserved() {
        let graphml = r#"
<graphml>
  <graph edgedefault="undirected">
    <node id="n0"/>
    <node id="n1"/>
    <edge id="edge-7" source="n0" target="n1"/>
  </graph>
</graphml>
"#;
        let mut engine = EdgeListEngine::strict();
        let report = engine
            .read_graphml(graphml)
            .expect("graphml edge id should parse");
        let attrs = report
            .graph
            .edge_attrs("n0", "n1")
            .expect("edge should exist");
        assert_eq!(
            attrs.get("id"),
            Some(&CgseValue::String("edge-7".to_owned()))
        );
    }

    #[test]
    fn graphml_multiedge_strict_fails_closed() {
        let graphml = r#"
<graphml>
  <graph edgedefault="undirected">
    <node id="n0"/>
    <node id="n1"/>
    <edge source="n0" target="n1"/>
    <edge source="n0" target="n1"/>
  </graph>
</graphml>
"#;
        let mut engine = EdgeListEngine::strict();
        let err = engine
            .read_graphml(graphml)
            .expect_err("strict mode should fail on multiedge graphml");
        assert!(matches!(err, ReadWriteError::FailClosed { .. }));
    }

    #[test]
    fn graphml_multiedge_hardened_warns_and_skips() {
        let graphml = r#"
<graphml>
  <graph edgedefault="undirected">
    <node id="n0"/>
    <node id="n1"/>
    <edge source="n0" target="n1"/>
    <edge source="n0" target="n1"/>
  </graph>
</graphml>
"#;
        let mut engine = EdgeListEngine::hardened();
        let report = engine
            .read_graphml(graphml)
            .expect("hardened mode should recover from multiedge");
        assert!(!report.warnings.is_empty());
        assert_eq!(report.graph.edge_count(), 1);
    }

    #[test]
    fn graphml_data_nested_elements_strict_fails_closed() {
        let graphml = r#"
<graphml xmlns="http://graphml.graphdrawing.org/xmlns" xmlns:y="http://www.yworks.com/xml/graphml">
  <key id="d0" for="node" attr.name="label" attr.type="string"/>
  <graph edgedefault="undirected">
    <node id="n0">
      <data key="d0">
        <y:ShapeNode/>
      </data>
    </node>
  </graph>
</graphml>
"#;
        let mut engine = EdgeListEngine::strict();
        let err = engine
            .read_graphml(graphml)
            .expect_err("strict mode should fail on nested data elements");
        assert!(matches!(err, ReadWriteError::FailClosed { .. }));
    }

    #[test]
    fn graphml_data_nested_elements_hardened_warns_and_skips() {
        let graphml = r#"
<graphml xmlns="http://graphml.graphdrawing.org/xmlns" xmlns:y="http://www.yworks.com/xml/graphml">
  <key id="d0" for="node" attr.name="label" attr.type="string"/>
  <graph edgedefault="undirected">
    <node id="n0">
      <data key="d0">
        <y:ShapeNode/>
      </data>
    </node>
  </graph>
</graphml>
"#;
        let mut engine = EdgeListEngine::hardened();
        let report = engine
            .read_graphml(graphml)
            .expect("hardened mode should skip nested data elements");
        assert!(!report.warnings.is_empty());
        let attrs = report.graph.node_attrs("n0").expect("node should exist");
        assert!(attrs.is_empty());
    }

    #[test]
    fn graphml_nested_data_does_not_poison_next_data() {
        let graphml = r#"
<graphml xmlns="http://graphml.graphdrawing.org/xmlns" xmlns:y="http://www.yworks.com/xml/graphml">
  <key id="d0" for="node" attr.name="label" attr.type="string"/>
  <key id="d1" for="node" attr.name="color" attr.type="string"/>
  <graph edgedefault="undirected">
    <node id="n0">
      <data key="d0">
        <y:ShapeNode/>
      </data>
      <data key="d1">blue</data>
    </node>
  </graph>
</graphml>
"#;
        let mut engine = EdgeListEngine::hardened();
        let report = engine
            .read_graphml(graphml)
            .expect("hardened mode should recover from nested data");
        assert!(!report.warnings.is_empty());
        let attrs = report.graph.node_attrs("n0").expect("node should exist");
        assert_eq!(
            attrs.get("color"),
            Some(&CgseValue::String("blue".to_owned()))
        );
        assert!(attrs.get("label").is_none());
    }

    #[test]
    fn graphml_hyperedge_strict_fails_closed() {
        let graphml = r#"
<graphml>
  <graph edgedefault="undirected">
    <node id="n0"/>
    <node id="n1"/>
    <hyperedge id="h0">
      <endpoint node="n0"/>
      <endpoint node="n1"/>
    </hyperedge>
  </graph>
</graphml>
"#;
        let mut engine = EdgeListEngine::strict();
        let err = engine
            .read_graphml(graphml)
            .expect_err("strict mode should fail on hyperedge");
        assert!(matches!(err, ReadWriteError::FailClosed { .. }));
    }

    #[test]
    fn graphml_hyperedge_hardened_warns_and_skips() {
        let graphml = r#"
<graphml>
  <graph edgedefault="undirected">
    <node id="n0"/>
    <node id="n1"/>
    <hyperedge id="h0">
      <endpoint node="n0"/>
      <endpoint node="n1"/>
    </hyperedge>
  </graph>
</graphml>
"#;
        let mut engine = EdgeListEngine::hardened();
        let report = engine
            .read_graphml(graphml)
            .expect("hardened mode should skip hyperedge");
        assert!(!report.warnings.is_empty());
        assert_eq!(report.graph.node_count(), 2);
        assert_eq!(report.graph.edge_count(), 0);
    }

    #[test]
    fn graphml_edge_directed_in_undirected_strict_fails_closed() {
        let graphml = r#"
<graphml>
  <graph edgedefault="undirected">
    <node id="n0"/>
    <node id="n1"/>
    <edge source="n0" target="n1" directed="true"/>
  </graph>
</graphml>
"#;
        let mut engine = EdgeListEngine::strict();
        let err = engine
            .read_graphml(graphml)
            .expect_err("strict mode should fail on directed edge in undirected graph");
        assert!(matches!(err, ReadWriteError::FailClosed { .. }));
    }

    #[test]
    fn graphml_edge_directed_in_undirected_hardened_warns_and_skips() {
        let graphml = r#"
<graphml>
  <graph edgedefault="undirected">
    <node id="n0"/>
    <node id="n1"/>
    <edge source="n0" target="n1" directed="true"/>
  </graph>
</graphml>
"#;
        let mut engine = EdgeListEngine::hardened();
        let report = engine
            .read_graphml(graphml)
            .expect("hardened mode should recover from directed edge in undirected graph");
        assert!(!report.warnings.is_empty());
        assert_eq!(report.graph.node_count(), 2);
        assert_eq!(report.graph.edge_count(), 0);
    }

    #[test]
    fn graphml_edge_undirected_in_directed_strict_fails_closed() {
        let graphml = r#"
<graphml>
  <graph edgedefault="directed">
    <node id="n0"/>
    <node id="n1"/>
    <edge source="n0" target="n1" directed="false"/>
  </graph>
</graphml>
"#;
        let mut engine = EdgeListEngine::strict();
        let err = engine
            .read_digraph_graphml(graphml)
            .expect_err("strict mode should fail on undirected edge in directed graph");
        assert!(matches!(err, ReadWriteError::FailClosed { .. }));
    }

    #[test]
    fn graphml_edge_undirected_in_directed_hardened_warns_and_skips() {
        let graphml = r#"
<graphml>
  <graph edgedefault="directed">
    <node id="n0"/>
    <node id="n1"/>
    <edge source="n0" target="n1" directed="false"/>
  </graph>
</graphml>
"#;
        let mut engine = EdgeListEngine::hardened();
        let report = engine
            .read_digraph_graphml(graphml)
            .expect("hardened mode should recover from undirected edge in directed graph");
        assert!(!report.warnings.is_empty());
        assert_eq!(report.graph.node_count(), 2);
        assert_eq!(report.graph.edge_count(), 0);
    }

    #[test]
    fn graphml_typed_int_allows_empty_data() {
        let graphml = r#"
<graphml>
  <key id="d0" for="node" attr.name="count" attr.type="int"/>
  <graph edgedefault="undirected">
    <node id="n0">
      <data key="d0"/>
    </node>
  </graph>
</graphml>
"#;
        let mut engine = EdgeListEngine::strict();
        let report = engine
            .read_graphml(graphml)
            .expect("empty typed data should parse as empty string");
        let attrs = report.graph.node_attrs("n0").expect("node should exist");
        assert_eq!(attrs.get("count"), Some(&CgseValue::String(String::new())));
    }

    #[test]
    fn graphml_typed_int_strict_fails_on_non_int() {
        let graphml = r#"
<graphml>
  <key id="d0" for="node" attr.name="count" attr.type="int"/>
  <graph edgedefault="undirected">
    <node id="n0">
      <data key="d0">1.5</data>
    </node>
  </graph>
</graphml>
"#;
        let mut engine = EdgeListEngine::strict();
        let err = engine
            .read_graphml(graphml)
            .expect_err("strict mode should fail on invalid int");
        assert!(matches!(err, ReadWriteError::FailClosed { .. }));
    }

    #[test]
    fn graphml_typed_int_hardened_warns_and_preserves_string() {
        let graphml = r#"
<graphml>
  <key id="d0" for="node" attr.name="count" attr.type="int"/>
  <graph edgedefault="undirected">
    <node id="n0">
      <data key="d0">1.5</data>
    </node>
  </graph>
</graphml>
"#;
        let mut engine = EdgeListEngine::hardened();
        let report = engine
            .read_graphml(graphml)
            .expect("hardened mode should recover");
        assert!(!report.warnings.is_empty());
        let attrs = report.graph.node_attrs("n0").expect("node should exist");
        assert_eq!(
            attrs.get("count"),
            Some(&CgseValue::String("1.5".to_owned()))
        );
    }

    #[test]
    fn graphml_typed_boolean_accepts_numeric_literals() {
        let graphml = r#"
<graphml>
  <key id="d0" for="node" attr.name="flag" attr.type="boolean"/>
  <key id="d1" for="node" attr.name="off" attr.type="boolean"/>
  <graph edgedefault="undirected">
    <node id="n0">
      <data key="d0">1</data>
      <data key="d1">0</data>
    </node>
  </graph>
</graphml>
"#;
        let mut engine = EdgeListEngine::strict();
        let report = engine
            .read_graphml(graphml)
            .expect("boolean numeric literals should parse");
        let attrs = report.graph.node_attrs("n0").expect("node should exist");
        assert_eq!(attrs.get("flag"), Some(&CgseValue::Bool(true)));
        assert_eq!(attrs.get("off"), Some(&CgseValue::Bool(false)));
    }

    #[test]
    fn graphml_deterministic_emission() {
        let mut graph = Graph::strict();
        graph.add_edge("x", "y").expect("edge add should succeed");
        graph.add_edge("y", "z").expect("edge add should succeed");

        let mut engine_a = EdgeListEngine::strict();
        let mut engine_b = EdgeListEngine::strict();
        let xml_a = engine_a
            .write_graphml(&graph)
            .expect("graphml write should succeed");
        let xml_b = engine_b
            .write_graphml(&graph)
            .expect("graphml replay should succeed");
        assert_eq!(xml_a, xml_b, "graphml emission must be deterministic");
    }

    #[test]
    fn unit_packet_006_contract_asserted() {
        let graph = packet_006_contract_graph();
        let expected_snapshot = graph.snapshot();

        let mut engine = EdgeListEngine::strict();
        let edgelist = engine
            .write_edgelist(&graph)
            .expect("packet-006 unit contract edgelist write should succeed");
        let parsed_edgelist = engine
            .read_edgelist(&edgelist)
            .expect("packet-006 unit contract edgelist read should succeed");
        assert!(
            parsed_edgelist.warnings.is_empty(),
            "strict edgelist path must stay warning-free for valid fixture"
        );
        assert_eq!(parsed_edgelist.graph.snapshot(), expected_snapshot);

        let json_payload = engine
            .write_json_graph(&graph)
            .expect("packet-006 unit contract json write should succeed");
        let parsed_json = engine
            .read_json_graph(&json_payload)
            .expect("packet-006 unit contract json read should succeed");
        assert!(
            parsed_json.warnings.is_empty(),
            "strict json path must stay warning-free for valid fixture"
        );
        assert_eq!(parsed_json.graph.snapshot(), expected_snapshot);

        let records = engine.evidence_ledger().records();
        assert_eq!(records.len(), 4, "unit contract should emit four decisions");
        let expected_operations = [
            "write_edgelist",
            "read_edgelist",
            "write_json_graph",
            "read_json_graph",
        ];
        for (index, record) in records.iter().enumerate() {
            assert_eq!(
                record.operation, expected_operations[index],
                "decision order drifted at index {index}"
            );
            assert_eq!(
                record.action,
                DecisionAction::Allow,
                "valid fixture should remain allow-only"
            );
        }

        let mut adversarial_engine = EdgeListEngine::strict();
        let err = adversarial_engine
            .read_edgelist("malformed")
            .expect_err("strict mode should fail closed for malformed packet-006 input");
        assert!(matches!(err, ReadWriteError::FailClosed { .. }));

        let mut environment = BTreeMap::new();
        environment.insert("os".to_owned(), std::env::consts::OS.to_owned());
        environment.insert("arch".to_owned(), std::env::consts::ARCH.to_owned());
        environment.insert("io_path".to_owned(), "edgelist+json_graph".to_owned());
        environment.insert("strict_mode".to_owned(), "true".to_owned());
        environment.insert("input_digest".to_owned(), stable_digest_hex(&edgelist));
        environment.insert(
            "output_digest".to_owned(),
            snapshot_digest(&parsed_json.graph.snapshot()),
        );

        let replay_command = "rch exec -- cargo test -p fnx-readwrite unit_packet_006_contract_asserted -- --nocapture";
        let artifact_refs = vec!["artifacts/conformance/latest/structured_logs.jsonl".to_owned()];
        let log = StructuredTestLog {
            schema_version: structured_test_log_schema_version().to_owned(),
            run_id: "readwrite-p2c006-unit".to_owned(),
            ts_unix_ms: 1,
            crate_name: "fnx-readwrite".to_owned(),
            suite_id: "unit".to_owned(),
            packet_id: "FNX-P2C-006".to_owned(),
            test_name: "unit_packet_006_contract_asserted".to_owned(),
            test_id: "unit::fnx-p2c-006::contract".to_owned(),
            test_kind: TestKind::Unit,
            mode: CompatibilityMode::Strict,
            fixture_id: Some("readwrite::contract::edgelist_json_roundtrip".to_owned()),
            seed: Some(7106),
            env_fingerprint: canonical_environment_fingerprint(&environment),
            environment,
            duration_ms: 9,
            replay_command: replay_command.to_owned(),
            artifact_refs: artifact_refs.clone(),
            forensic_bundle_id: "forensics::readwrite::unit::contract".to_owned(),
            hash_id: "sha256:readwrite-p2c006-unit".to_owned(),
            status: TestStatus::Passed,
            reason_code: None,
            failure_repro: None,
            e2e_step_traces: Vec::new(),
            forensics_bundle_index: Some(packet_006_forensics_bundle(
                "readwrite-p2c006-unit",
                "unit::fnx-p2c-006::contract",
                replay_command,
                "forensics::readwrite::unit::contract",
                artifact_refs,
            )),
        };
        log.validate()
            .expect("unit packet-006 telemetry log should satisfy strict schema");
    }

    // --- Adversarial fixture tests ---
    // Verify parsers handle malformed and adversarial inputs gracefully.

    #[test]
    fn adversarial_empty_edgelist_strict_returns_empty() {
        let mut engine = EdgeListEngine::strict();
        let report = engine
            .read_edgelist("")
            .expect("empty edgelist should return empty graph");
        assert_eq!(report.graph.node_count(), 0);
        assert_eq!(report.graph.edge_count(), 0);
    }

    #[test]
    fn adversarial_empty_edgelist_hardened_returns_empty() {
        let mut engine = EdgeListEngine::hardened();
        let report = engine
            .read_edgelist("")
            .expect("hardened empty edgelist should return empty graph");
        assert_eq!(report.graph.node_count(), 0);
        assert_eq!(report.graph.edge_count(), 0);
    }

    #[test]
    fn adversarial_empty_json_strict_fails_closed() {
        let mut engine = EdgeListEngine::strict();
        let err = engine
            .read_json_graph("")
            .expect_err("empty json in strict mode should fail");
        assert!(matches!(err, ReadWriteError::FailClosed { .. }));
    }

    #[test]
    fn adversarial_empty_graphml_strict_returns_empty() {
        let mut engine = EdgeListEngine::strict();
        // Empty XML returns empty graph (no graph element found).
        let report = engine
            .read_graphml("")
            .expect("empty graphml should return empty graph");
        assert_eq!(report.graph.node_count(), 0);
        assert_eq!(report.graph.edge_count(), 0);
    }

    #[test]
    fn adversarial_empty_gml_strict_returns_empty() {
        let mut engine = EdgeListEngine::strict();
        // Empty GML returns empty graph (no graph block found).
        let report = engine
            .read_gml("")
            .expect("empty gml should return empty graph");
        assert_eq!(report.graph.node_count(), 0);
        assert_eq!(report.graph.edge_count(), 0);
    }

    #[test]
    fn adversarial_unicode_json_parses_correctly() {
        let input = include_str!("../../fnx-conformance/fixtures/adversarial/unicode_nodes.json");
        let mut engine = EdgeListEngine::strict();
        let report = engine
            .read_json_graph(input)
            .expect("unicode json should parse in strict mode");
        assert_eq!(report.graph.node_count(), 7, "should have 7 unicode nodes");
        assert_eq!(report.graph.edge_count(), 4);
    }

    #[test]
    fn adversarial_self_loops_json_parses() {
        let input = include_str!("../../fnx-conformance/fixtures/adversarial/self_loops_only.json");
        let mut engine = EdgeListEngine::strict();
        // Self-loops may or may not be supported; either Ok or Err is fine, but no panic.
        let _ = engine.read_json_graph(input);
    }

    #[test]
    fn adversarial_negative_weights_json_parses() {
        let input =
            include_str!("../../fnx-conformance/fixtures/adversarial/negative_weights.json");
        let mut engine = EdgeListEngine::strict();
        let report = engine
            .read_digraph_json_graph(input)
            .expect("negative weights json should parse as digraph");
        assert_eq!(report.graph.node_count(), 5);
        assert_eq!(report.graph.edge_count(), 7);
    }

    #[test]
    fn adversarial_malformed_graphml_hardened_recovers() {
        let input =
            include_str!("../../fnx-conformance/fixtures/adversarial/malformed_xml.graphml");
        let mut engine = EdgeListEngine::hardened();
        // Must not panic. Should return Ok with warnings or Err.
        let _ = engine.read_graphml(input);
    }

    #[test]
    fn adversarial_malformed_gml_hardened_recovers() {
        let input =
            include_str!("../../fnx-conformance/fixtures/adversarial/malformed_nesting.gml");
        let mut engine = EdgeListEngine::hardened();
        // Must not panic. Should return Ok with warnings or Err.
        let _ = engine.read_gml(input);
    }

    proptest! {
        #[test]
        fn property_packet_006_invariants(edges in prop::collection::vec((0_u8..8, 0_u8..8), 1..40)) {
            let mut graph = Graph::strict();
            for (left, right) in &edges {
                let left_node = format!("n{left}");
                let right_node = format!("n{right}");
                graph
                    .add_edge_with_attrs(
                        left_node,
                        right_node,
                        BTreeMap::from([(
                            "weight".to_owned(),
                            ((u16::from(*left) + u16::from(*right)) + 1)
                                .to_string()
                                .into(),
                        )]),
                    )
                    .expect("generated edge insertion should succeed");
            }
            prop_assume!(graph.edge_count() > 0);

            let mut strict_a = EdgeListEngine::strict();
            let mut strict_b = EdgeListEngine::strict();

            let edgelist_a = strict_a
                .write_edgelist(&graph)
                .expect("strict edgelist emit should succeed");
            let edgelist_b = strict_b
                .write_edgelist(&graph)
                .expect("strict edgelist replay emit should succeed");

            // Invariant family 1: strict edgelist emission is deterministic.
            prop_assert_eq!(
                &edgelist_a,
                &edgelist_b,
                "P2C006-IV-1 strict edgelist emission drifted"
            );

            let strict_parsed_a = strict_a
                .read_edgelist(&edgelist_a)
                .expect("strict edgelist parse should succeed");
            let strict_parsed_b = strict_b
                .read_edgelist(&edgelist_b)
                .expect("strict edgelist replay parse should succeed");

            // Invariant family 2: strict round-trip topology/data is deterministic and warning-free.
            prop_assert_eq!(
                &strict_parsed_a.graph.snapshot(),
                &strict_parsed_b.graph.snapshot(),
                "P2C006-IV-2 strict round-trip snapshot drifted"
            );
            prop_assert!(
                strict_parsed_a.warnings.is_empty() && strict_parsed_b.warnings.is_empty(),
                "P2C006-IV-2 strict round-trip should not emit warnings for valid generated payloads"
            );

            let json_a = strict_a
                .write_json_graph(&graph)
                .expect("strict json emit should succeed");
            let json_b = strict_b
                .write_json_graph(&graph)
                .expect("strict json replay emit should succeed");

            // Invariant family 3: strict json emission is deterministic.
            prop_assert_eq!(
                &json_a,
                &json_b,
                "P2C006-IV-3 strict json emission drifted"
            );

            let strict_json_a = strict_a
                .read_json_graph(&json_a)
                .expect("strict json parse should succeed");
            let strict_json_b = strict_b
                .read_json_graph(&json_b)
                .expect("strict json replay parse should succeed");

            // Invariant family 4: strict json reconstruction is deterministic and warning-free.
            prop_assert_eq!(
                &strict_json_a.graph.snapshot(),
                &strict_json_b.graph.snapshot(),
                "P2C006-IV-3 strict json reconstruction drifted"
            );
            prop_assert!(
                strict_json_a.warnings.is_empty() && strict_json_b.warnings.is_empty(),
                "P2C006-IV-3 strict json reconstruction should not emit warnings for valid payloads"
            );

            let malformed_payload = format!(
                "{edgelist_a}\nmalformed\n# comment only\ninvalid_attr_line x y z\na\n"
            );
            let mut hardened_a = EdgeListEngine::hardened();
            let mut hardened_b = EdgeListEngine::hardened();
            let hardened_report_a = hardened_a
                .read_edgelist(&malformed_payload)
                .expect("hardened parse should recover deterministically");
            let hardened_report_b = hardened_b
                .read_edgelist(&malformed_payload)
                .expect("hardened replay parse should recover deterministically");

            // Invariant family 5: hardened malformed-input recovery is deterministic and auditable.
            prop_assert_eq!(
                &hardened_report_a.graph.snapshot(),
                &hardened_report_b.graph.snapshot(),
                "P2C006-IV-2 hardened recovery snapshot drifted"
            );
            prop_assert_eq!(
                &hardened_report_a.warnings,
                &hardened_report_b.warnings,
                "P2C006-IV-2 hardened recovery warning envelope drifted"
            );
            prop_assert!(
                !hardened_report_a.warnings.is_empty(),
                "P2C006-IV-2 adversarial malformed payload should emit deterministic warnings"
            );

            for strict_engine in [&strict_a, &strict_b] {
                let records = strict_engine.evidence_ledger().records();
                prop_assert_eq!(
                    records.len(),
                    4,
                    "strict replay ledger should contain exactly write/read decisions for edgelist+json"
                );
                prop_assert!(
                    records.iter().all(|record| {
                        record.action == DecisionAction::Allow
                            && matches!(
                                record.operation.as_str(),
                                "write_edgelist"
                                    | "read_edgelist"
                                    | "write_json_graph"
                                    | "read_json_graph"
                            )
                    }),
                    "strict replay ledger should remain allow-only for valid generated payloads"
                );
            }

            for hardened_engine in [&hardened_a, &hardened_b] {
                let records = hardened_engine.evidence_ledger().records();
                prop_assert!(
                    records
                        .iter()
                        .any(|record| record.action == DecisionAction::FullValidate),
                    "hardened malformed replay should include a full-validate decision"
                );
                prop_assert_eq!(
                    records.last().map(|record| record.action),
                    Some(DecisionAction::Allow),
                    "hardened malformed replay should end with allow after bounded recovery"
                );
            }

            let deterministic_seed = edges.iter().fold(7206_u64, |acc, (left, right)| {
                acc.wrapping_mul(131)
                    .wrapping_add((u64::from(*left)) << 8)
                    .wrapping_add(u64::from(*right))
            });

            let mut environment = BTreeMap::new();
            environment.insert("os".to_owned(), std::env::consts::OS.to_owned());
            environment.insert("arch".to_owned(), std::env::consts::ARCH.to_owned());
            environment.insert("graph_fingerprint".to_owned(), graph_fingerprint(&graph));
            environment.insert("mode_policy".to_owned(), "strict_and_hardened".to_owned());
            environment.insert("invariant_id".to_owned(), "P2C006-IV-1".to_owned());
            environment.insert("input_digest".to_owned(), stable_digest_hex(&malformed_payload));
            environment.insert(
                "output_digest".to_owned(),
                snapshot_digest(&strict_json_a.graph.snapshot()),
            );

            let replay_command =
                "rch exec -- cargo test -p fnx-readwrite property_packet_006_invariants -- --nocapture";
            let artifact_refs = vec![
                "artifacts/conformance/latest/structured_log_emitter_normalization_report.json"
                    .to_owned(),
            ];
            let log = StructuredTestLog {
                schema_version: structured_test_log_schema_version().to_owned(),
                run_id: "readwrite-p2c006-property".to_owned(),
                ts_unix_ms: 2,
                crate_name: "fnx-readwrite".to_owned(),
                suite_id: "property".to_owned(),
                packet_id: "FNX-P2C-006".to_owned(),
                test_name: "property_packet_006_invariants".to_owned(),
                test_id: "property::fnx-p2c-006::invariants".to_owned(),
                test_kind: TestKind::Property,
                mode: CompatibilityMode::Hardened,
                fixture_id: Some("readwrite::property::roundtrip_recovery_matrix".to_owned()),
                seed: Some(deterministic_seed),
                env_fingerprint: canonical_environment_fingerprint(&environment),
                environment,
                duration_ms: 15,
                replay_command: replay_command.to_owned(),
                artifact_refs: artifact_refs.clone(),
                forensic_bundle_id: "forensics::readwrite::property::invariants".to_owned(),
                hash_id: "sha256:readwrite-p2c006-property".to_owned(),
                status: TestStatus::Passed,
                reason_code: None,
                failure_repro: None,
                e2e_step_traces: Vec::new(),
                forensics_bundle_index: Some(packet_006_forensics_bundle(
                    "readwrite-p2c006-property",
                    "property::fnx-p2c-006::invariants",
                    replay_command,
                    "forensics::readwrite::property::invariants",
                    artifact_refs,
                )),
            };
            prop_assert!(
                log.validate().is_ok(),
                "packet-006 property telemetry log should satisfy strict schema"
            );
        }

        #[test]
        fn property_gml_round_trip(edges in prop::collection::vec((0_u8..8, 0_u8..8), 1..30)) {
            // GML format coerces attribute types to strings, so use string attrs.
            let mut graph = Graph::strict();
            for (left, right) in &edges {
                let left_node = format!("n{left}");
                let right_node = format!("n{right}");
                let _ = graph.add_edge_with_attrs(
                    left_node,
                    right_node,
                    BTreeMap::from([("weight".to_owned(), CgseValue::String(format!("{}", *left + 1)))]),
                );
            }
            prop_assume!(graph.edge_count() > 0);

            let mut engine = EdgeListEngine::strict();
            let gml = engine.write_gml(&graph).expect("gml write should succeed");
            let parsed = engine.read_gml(&gml).expect("gml read should succeed");

            prop_assert!(parsed.warnings.is_empty(), "strict gml round-trip should have no warnings");
            prop_assert_eq!(
                graph.snapshot(),
                parsed.graph.snapshot(),
                "gml round-trip snapshot should be identical"
            );

            // Determinism: writing the same graph twice produces identical GML.
            let mut engine2 = EdgeListEngine::strict();
            let gml2 = engine2.write_gml(&graph).expect("gml replay write should succeed");
            prop_assert_eq!(&gml, &gml2, "gml emission must be deterministic");
        }

        #[test]
        fn property_graphml_round_trip(edges in prop::collection::vec((0_u8..8, 0_u8..8), 1..30)) {
            let mut graph = Graph::strict();
            for (left, right) in &edges {
                let left_node = format!("n{left}");
                let right_node = format!("n{right}");
                let _ = graph.add_edge_with_attrs(
                    left_node,
                    right_node,
                    BTreeMap::from([("weight".to_owned(), CgseValue::String(format!("{}", *left + 1)))]),
                );
            }
            prop_assume!(graph.edge_count() > 0);

            let mut engine = EdgeListEngine::strict();
            let xml = engine.write_graphml(&graph).expect("graphml write should succeed");
            let parsed = engine.read_graphml(&xml).expect("graphml read should succeed");

            prop_assert!(parsed.warnings.is_empty(), "strict graphml round-trip should have no warnings");
            prop_assert_eq!(
                graph.snapshot(),
                parsed.graph.snapshot(),
                "graphml round-trip snapshot should be identical"
            );

            // Determinism check.
            let mut engine2 = EdgeListEngine::strict();
            let xml2 = engine2.write_graphml(&graph).expect("graphml replay write should succeed");
            prop_assert_eq!(&xml, &xml2, "graphml emission must be deterministic");
        }

        #[test]
        fn property_adjlist_round_trip(edges in prop::collection::vec((0_u8..8, 0_u8..8), 1..30)) {
            let mut graph = Graph::strict();
            for (left, right) in &edges {
                let left_node = format!("n{left}");
                let right_node = format!("n{right}");
                let _ = graph.add_edge(&left_node, &right_node);
            }
            prop_assume!(graph.edge_count() > 0);

            let mut engine = EdgeListEngine::strict();
            let text = engine.write_adjlist(&graph).expect("adjlist write should succeed");
            let parsed = engine.read_adjlist(&text).expect("adjlist read should succeed");

            prop_assert!(parsed.warnings.is_empty(), "strict adjlist round-trip should have no warnings");
            // Adjlist may reorder nodes (adjacency-list enumeration order);
            // compare node/edge sets rather than exact snapshot.
            prop_assert_eq!(graph.node_count(), parsed.graph.node_count(), "node count mismatch");
            prop_assert_eq!(graph.edge_count(), parsed.graph.edge_count(), "edge count mismatch");
            let mut orig_nodes: Vec<_> = graph.snapshot().nodes.clone();
            let mut parsed_nodes: Vec<_> = parsed.graph.snapshot().nodes.clone();
            orig_nodes.sort();
            parsed_nodes.sort();
            prop_assert_eq!(orig_nodes, parsed_nodes, "node sets differ");
        }

        #[test]
        fn property_edgelist_round_trip(edges in prop::collection::vec((0_u8..8, 0_u8..8), 1..30)) {
            let mut graph = Graph::strict();
            for (left, right) in &edges {
                let left_node = format!("n{left}");
                let right_node = format!("n{right}");
                // Use Int type since edgelist parse_relaxed infers numeric types
                let _ = graph.add_edge_with_attrs(
                    left_node,
                    right_node,
                    BTreeMap::from([("weight".to_owned(), CgseValue::Int(i64::from(*left) + 1))]),
                );
            }
            prop_assume!(graph.edge_count() > 0);

            let mut engine = EdgeListEngine::strict();
            let text = engine.write_edgelist(&graph).expect("edgelist write should succeed");
            let parsed = engine.read_edgelist(&text).expect("edgelist read should succeed");

            prop_assert!(parsed.warnings.is_empty(), "strict edgelist round-trip should have no warnings");
            // Edgelist format doesn't preserve node order - compare as sets
            let orig = graph.snapshot();
            let parsed_snap = parsed.graph.snapshot();
            prop_assert_eq!(orig.mode, parsed_snap.mode, "modes should match");
            let mut orig_nodes = orig.nodes.clone();
            let mut parsed_nodes = parsed_snap.nodes.clone();
            orig_nodes.sort();
            parsed_nodes.sort();
            prop_assert_eq!(orig_nodes, parsed_nodes, "node sets should match");
            let mut orig_edges = orig.edges.clone();
            let mut parsed_edges = parsed_snap.edges.clone();
            orig_edges.sort_by(|a, b| (&a.left, &a.right).cmp(&(&b.left, &b.right)));
            parsed_edges.sort_by(|a, b| (&a.left, &a.right).cmp(&(&b.left, &b.right)));
            prop_assert_eq!(orig_edges, parsed_edges, "edge sets should match");
        }

        #[test]
        fn property_json_graph_round_trip(edges in prop::collection::vec((0_u8..8, 0_u8..8), 1..30)) {
            let mut graph = Graph::strict();
            for (left, right) in &edges {
                let left_node = format!("n{left}");
                let right_node = format!("n{right}");
                let _ = graph.add_edge_with_attrs(
                    left_node,
                    right_node,
                    BTreeMap::from([("weight".to_owned(), CgseValue::String(format!("{}", *left + 1)))]),
                );
            }
            prop_assume!(graph.edge_count() > 0);

            let mut engine = EdgeListEngine::strict();
            let json = engine.write_json_graph(&graph).expect("json write should succeed");
            let parsed = engine.read_json_graph(&json).expect("json read should succeed");

            prop_assert!(parsed.warnings.is_empty(), "strict json round-trip should have no warnings");
            prop_assert_eq!(
                graph.snapshot(),
                parsed.graph.snapshot(),
                "json round-trip snapshot should be identical"
            );
        }

        #[test]
        fn property_digraph_gml_round_trip(edges in prop::collection::vec((0_u8..8, 0_u8..8), 1..30)) {
            let mut graph = DiGraph::strict();
            for (left, right) in &edges {
                let left_node = format!("n{left}");
                let right_node = format!("n{right}");
                let _ = graph.add_edge_with_attrs(
                    left_node,
                    right_node,
                    BTreeMap::from([("weight".to_owned(), CgseValue::String(format!("{}", *left + 1)))]),
                );
            }
            prop_assume!(graph.edge_count() > 0);

            let mut engine = EdgeListEngine::strict();
            let gml = engine.write_digraph_gml(&graph).expect("gml write should succeed");
            let parsed = engine.read_digraph_gml(&gml).expect("gml read should succeed");

            prop_assert!(parsed.warnings.is_empty(), "strict digraph gml round-trip should have no warnings");
            prop_assert_eq!(
                graph.snapshot(),
                parsed.graph.snapshot(),
                "digraph gml round-trip snapshot should be identical"
            );
        }

        #[test]
        fn property_digraph_graphml_round_trip(edges in prop::collection::vec((0_u8..8, 0_u8..8), 1..30)) {
            let mut graph = DiGraph::strict();
            for (left, right) in &edges {
                let left_node = format!("n{left}");
                let right_node = format!("n{right}");
                let _ = graph.add_edge_with_attrs(
                    left_node,
                    right_node,
                    BTreeMap::from([("weight".to_owned(), CgseValue::String(format!("{}", *left + 1)))]),
                );
            }
            prop_assume!(graph.edge_count() > 0);

            let mut engine = EdgeListEngine::strict();
            let xml = engine.write_digraph_graphml(&graph).expect("graphml write should succeed");
            let parsed = engine.read_digraph_graphml(&xml).expect("graphml read should succeed");

            prop_assert!(parsed.warnings.is_empty(), "strict digraph graphml round-trip should have no warnings");
            prop_assert_eq!(
                graph.snapshot(),
                parsed.graph.snapshot(),
                "digraph graphml round-trip snapshot should be identical"
            );
        }

        #[test]
        fn property_digraph_adjlist_round_trip(edges in prop::collection::vec((0_u8..8, 0_u8..8), 1..30)) {
            let mut graph = DiGraph::strict();
            for (left, right) in &edges {
                let left_node = format!("n{left}");
                let right_node = format!("n{right}");
                let _ = graph.add_edge(&left_node, &right_node);
            }
            prop_assume!(graph.edge_count() > 0);

            let mut engine = EdgeListEngine::strict();
            let text = engine.write_digraph_adjlist(&graph).expect("adjlist write should succeed");
            let parsed = engine.read_digraph_adjlist(&text).expect("adjlist read should succeed");

            prop_assert!(parsed.warnings.is_empty(), "strict digraph adjlist round-trip should have no warnings");
            prop_assert_eq!(graph.node_count(), parsed.graph.node_count(), "node count mismatch");
            prop_assert_eq!(graph.edge_count(), parsed.graph.edge_count(), "edge count mismatch");
            let mut orig_nodes: Vec<_> = graph.snapshot().nodes.clone();
            let mut parsed_nodes: Vec<_> = parsed.graph.snapshot().nodes.clone();
            orig_nodes.sort();
            parsed_nodes.sort();
            prop_assert_eq!(orig_nodes, parsed_nodes, "node sets differ");
        }

        #[test]
        fn property_digraph_edgelist_round_trip(edges in prop::collection::vec((0_u8..8, 0_u8..8), 1..30)) {
            let mut graph = DiGraph::strict();
            for (left, right) in &edges {
                let left_node = format!("n{left}");
                let right_node = format!("n{right}");
                // Use Int type since edgelist parse_relaxed infers numeric types
                let _ = graph.add_edge_with_attrs(
                    left_node,
                    right_node,
                    BTreeMap::from([("weight".to_owned(), CgseValue::Int(i64::from(*left) + 1))]),
                );
            }
            prop_assume!(graph.edge_count() > 0);

            let mut engine = EdgeListEngine::strict();
            let text = engine.write_digraph_edgelist(&graph).expect("edgelist write should succeed");
            let parsed = engine.read_digraph_edgelist(&text).expect("edgelist read should succeed");

            prop_assert!(parsed.warnings.is_empty(), "strict digraph edgelist round-trip should have no warnings");
            // Edgelist format doesn't preserve node order - compare as sets
            let orig = graph.snapshot();
            let parsed_snap = parsed.graph.snapshot();
            prop_assert_eq!(orig.mode, parsed_snap.mode, "modes should match");
            let mut orig_nodes = orig.nodes.clone();
            let mut parsed_nodes = parsed_snap.nodes.clone();
            orig_nodes.sort();
            parsed_nodes.sort();
            prop_assert_eq!(orig_nodes, parsed_nodes, "node sets should match");
            let mut orig_edges = orig.edges.clone();
            let mut parsed_edges = parsed_snap.edges.clone();
            orig_edges.sort_by(|a, b| (&a.left, &a.right).cmp(&(&b.left, &b.right)));
            parsed_edges.sort_by(|a, b| (&a.left, &a.right).cmp(&(&b.left, &b.right)));
            prop_assert_eq!(orig_edges, parsed_edges, "edge sets should match");
        }

        #[test]
        fn property_digraph_json_graph_round_trip(edges in prop::collection::vec((0_u8..8, 0_u8..8), 1..30)) {
            let mut graph = DiGraph::strict();
            for (left, right) in &edges {
                let left_node = format!("n{left}");
                let right_node = format!("n{right}");
                let _ = graph.add_edge_with_attrs(
                    left_node,
                    right_node,
                    BTreeMap::from([("weight".to_owned(), CgseValue::String(format!("{}", *left + 1)))]),
                );
            }
            prop_assume!(graph.edge_count() > 0);

            let mut engine = EdgeListEngine::strict();
            let json = engine.write_digraph_json_graph(&graph).expect("json write should succeed");
            let parsed = engine.read_digraph_json_graph(&json).expect("json read should succeed");

            prop_assert!(parsed.warnings.is_empty(), "strict digraph json round-trip should have no warnings");
            prop_assert_eq!(
                graph.snapshot(),
                parsed.graph.snapshot(),
                "digraph json round-trip snapshot should be identical"
            );
        }

    }

    proptest! {
        #![proptest_config(proptest::prelude::ProptestConfig::with_cases(64))]

        /// Fast text-format parsers: edgelist, adjlist, JSON, GML.
        /// GraphML (XML) is excluded because quick-xml can be slow on adversarial
        /// input; that surface is covered by the cargo-fuzz harness instead.
        #[test]
        fn property_malformed_input_never_panics(data in "[\\x20-\\x7e]{0,120}") {
            let mut strict = EdgeListEngine::strict();
            let _ = strict.read_edgelist(&data);

            let mut strict2 = EdgeListEngine::strict();
            let _ = strict2.read_adjlist(&data);

            let mut strict3 = EdgeListEngine::strict();
            let _ = strict3.read_json_graph(&data);

            let mut strict4 = EdgeListEngine::strict();
            let _ = strict4.read_gml(&data);

            // Hardened mode must never panic either.
            let mut hardened = EdgeListEngine::hardened();
            let _ = hardened.read_edgelist(&data);

            let mut hardened2 = EdgeListEngine::hardened();
            let _ = hardened2.read_adjlist(&data);

            let mut hardened3 = EdgeListEngine::hardened();
            let _ = hardened3.read_json_graph(&data);

            let mut hardened4 = EdgeListEngine::hardened();
            let _ = hardened4.read_gml(&data);
        }
    }
}
