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
    pub directed: bool,
    #[serde(default)]
    pub graph_attrs: AttrMap,
    pub nodes: Vec<String>,
    pub edges: Vec<fnx_classes::EdgeSnapshot>,
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
            let line = raw_line.trim();
            if line.is_empty() || line.starts_with('#') {
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
            let line = raw_line.trim();
            if line.is_empty() || line.starts_with('#') {
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
            let line = raw_line.trim();
            if line.is_empty() || line.starts_with('#') {
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
            let line = raw_line.trim();
            if line.is_empty() || line.starts_with('#') {
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
            directed: false,
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
            directed: true,
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
                    directed: false,
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
                    directed: true,
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

        let mut graph = DiGraph::new(self.mode);
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

        // Collect all distinct attribute keys from graph, nodes, and edges.
        let mut graph_attr_keys = BTreeSet::new();
        let mut node_attr_keys = BTreeSet::new();
        let mut edge_attr_keys = BTreeSet::new();

        for key in graph_attrs.keys() {
            graph_attr_keys.insert(key.clone());
        }

        let nodes = graph.nodes_ordered();
        for node_id in &nodes {
            if let Some(attrs) = graph.node_attrs(node_id) {
                for key in attrs.keys() {
                    node_attr_keys.insert(key.clone());
                }
            }
        }

        let edges = graph.edges_ordered();
        for edge in &edges {
            for key in edge.attrs.keys() {
                edge_attr_keys.insert(key.clone());
            }
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
        let mut node_key_ids: BTreeMap<String, String> = BTreeMap::new();
        for attr_name in &node_attr_keys {
            let key_id = format!("n{key_counter}");
            key_counter += 1;
            let mut key_elem = BytesStart::new("key");
            key_elem.push_attribute(("id", key_id.as_str()));
            key_elem.push_attribute(("for", "node"));
            key_elem.push_attribute(("attr.name", attr_name.as_str()));
            key_elem.push_attribute(("attr.type", "string"));
            writer
                .write_event(Event::Empty(key_elem))
                .map_err(|e| xml_write_err("key_node", e))?;
            node_key_ids.insert(attr_name.clone(), key_id);
        }

        // Emit <key> declarations for edge attributes.
        let mut edge_key_ids: BTreeMap<String, String> = BTreeMap::new();
        for attr_name in &edge_attr_keys {
            let key_id = format!("e{key_counter}");
            key_counter += 1;
            let mut key_elem = BytesStart::new("key");
            key_elem.push_attribute(("id", key_id.as_str()));
            key_elem.push_attribute(("for", "edge"));
            key_elem.push_attribute(("attr.name", attr_name.as_str()));
            key_elem.push_attribute(("attr.type", "string"));
            writer
                .write_event(Event::Empty(key_elem))
                .map_err(|e| xml_write_err("key_edge", e))?;
            edge_key_ids.insert(attr_name.clone(), key_id);
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
                        if let Some(key_id) = node_key_ids.get(attr_name) {
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
                    if let Some(key_id) = edge_key_ids.get(attr_name) {
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
        let mut reader = Reader::from_str(input);
        reader.config_mut().trim_text(true);
        let mut buffer = Vec::new();

        loop {
            match reader.read_event_into(&mut buffer) {
                Ok(Event::Start(element)) | Ok(Event::Empty(element))
                    if xml_local_name(element.name().as_ref()) == b"graph" =>
                {
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
                                return Ok(false);
                            }
                        };
                        if xml_local_name(attr.key.as_ref()) == b"edgedefault" {
                            return Ok(attr.value.as_ref() == b"directed");
                        }
                    }
                    return Ok(false);
                }
                Ok(Event::Eof) => return Ok(false),
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
                    return Ok(false);
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
        let mut key_registry: BTreeMap<String, (String, String, String)> = BTreeMap::new();
        let mut reader = Reader::from_str(input);
        reader.config_mut().trim_text(true);

        let mut in_graph = false;
        let mut current_node: Option<String> = None;
        let mut current_edge: Option<(String, String)> = None;
        let mut current_data_key: Option<String> = None;
        let mut current_data_text = String::new();

        let mut pending_graph_attrs: AttrMap = AttrMap::new();
        let mut pending_node_attrs: AttrMap = AttrMap::new();
        let mut pending_edge_attrs: AttrMap = AttrMap::new();

        loop {
            match reader.read_event() {
                Ok(Event::Start(ref e)) => {
                    self.handle_graphml_start_element(
                        e,
                        graph,
                        warnings,
                        &mut key_registry,
                        &mut in_graph,
                        &mut current_node,
                        &mut current_edge,
                        &mut current_data_key,
                        &mut current_data_text,
                        &mut pending_graph_attrs,
                        &mut pending_node_attrs,
                        &mut pending_edge_attrs,
                    )?;
                }
                Ok(Event::Empty(ref e)) => {
                    self.handle_graphml_start_element(
                        e,
                        graph,
                        warnings,
                        &mut key_registry,
                        &mut in_graph,
                        &mut current_node,
                        &mut current_edge,
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
                        &mut current_node,
                        &mut current_edge,
                        &mut current_data_key,
                        &mut current_data_text,
                        &mut pending_graph_attrs,
                        &mut pending_node_attrs,
                        &mut pending_edge_attrs,
                        graph_attrs,
                        &key_registry,
                    )?;
                }
                Ok(Event::Text(ref e)) if current_data_key.is_some() => match e.unescape() {
                    Ok(text) => current_data_text.push_str(&text),
                    Err(err) => {
                        let warning = format!("graphml data text unescape error: {err}");
                        if self.mode == CompatibilityMode::Strict {
                            self.record("read_graphml", DecisionAction::FailClosed, &warning, 1.0);
                            return Err(ReadWriteError::FailClosed {
                                operation: "read_graphml",
                                reason: warning,
                            });
                        }
                        warnings.push(warning.clone());
                        self.record("read_graphml", DecisionAction::FullValidate, &warning, 0.8);
                        current_data_text.clear();
                        current_data_key = None;
                    }
                },
                Ok(Event::End(ref e)) => {
                    self.handle_graphml_end_element(
                        xml_local_name(e.name().as_ref()),
                        graph,
                        warnings,
                        &mut in_graph,
                        &mut current_node,
                        &mut current_edge,
                        &mut current_data_key,
                        &mut current_data_text,
                        &mut pending_graph_attrs,
                        &mut pending_node_attrs,
                        &mut pending_edge_attrs,
                        graph_attrs,
                        &key_registry,
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
        Ok(())
    }

    #[allow(clippy::too_many_arguments)]
    fn handle_graphml_start_element<G>(
        &mut self,
        e: &BytesStart<'_>,
        graph: &mut G,
        warnings: &mut Vec<String>,
        key_registry: &mut BTreeMap<String, (String, String, String)>,
        in_graph: &mut bool,
        current_node: &mut Option<String>,
        current_edge: &mut Option<(String, String)>,
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
                        _ => {}
                    }
                }
                if !key_id.is_empty() && !attr_name.is_empty() {
                    key_registry.insert(key_id, (for_scope, attr_name, attr_type));
                }
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
                pending_node_attrs.clear();
            }
            b"edge" if *in_graph => {
                let mut source = String::new();
                let mut target = String::new();
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
                *current_edge = Some((source, target));
                pending_edge_attrs.clear();
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
        current_node: &mut Option<String>,
        current_edge: &mut Option<(String, String)>,
        current_data_key: &mut Option<String>,
        current_data_text: &mut String,
        pending_graph_attrs: &mut AttrMap,
        pending_node_attrs: &mut AttrMap,
        pending_edge_attrs: &mut AttrMap,
        graph_attrs: &mut AttrMap,
        key_registry: &BTreeMap<String, (String, String, String)>,
    ) -> Result<(), ReadWriteError>
    where
        G: GraphLike,
    {
        match local {
            b"data" => {
                if let Some(key_id) = current_data_key.take() {
                    let (scope, attr_name, attr_type) = match key_registry.get(&key_id) {
                        Some(entry) => entry,
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
                    if !graphml_scope_matches(scope, target_scope) {
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
                        self.parse_graphml_typed_value(&key_id, attr_type, raw_value, warnings)?;
                    if current_node.is_some() && current_edge.is_none() {
                        pending_node_attrs.insert(attr_name.clone(), value);
                    } else if current_edge.is_some() {
                        pending_edge_attrs.insert(attr_name.clone(), value);
                    } else {
                        pending_graph_attrs.insert(attr_name.clone(), value);
                    }
                }
                current_data_text.clear();
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
                    let result = graph.add_edge_with_attrs(
                        source,
                        target,
                        std::mem::take(pending_edge_attrs),
                    );
                    if let Err(err) = result {
                        let warning = format!("graphml edge add failed: {err}");
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
                pending_edge_attrs.clear();
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

        let parsed = match attr_type.as_str() {
            "" => Ok(CgseValue::parse_relaxed(trimmed)),
            "string" => Ok(CgseValue::String(raw_value)),
            "boolean" => match trimmed.to_ascii_lowercase().as_str() {
                "true" => Ok(CgseValue::Bool(true)),
                "false" => Ok(CgseValue::Bool(false)),
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
        let is_directed = self.read_gml_into(&mut graph, &mut graph_attrs, &mut warnings, input)?;
        if is_directed {
            warnings.push("GML declares directed=1 but read into undirected Graph".to_owned());
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
        let _ = self.read_gml_into(&mut graph, &mut graph_attrs, &mut warnings, input)?;
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

        while pos + 1 < tokens.len() {
            match tokens[pos].as_str() {
                "directed" => return Ok(tokens[pos + 1] == "1"),
                "node" | "edge" | "]" => return Ok(false),
                _ => pos += 1,
            }
        }

        Ok(false)
    }

    /// Parse GML into a generic graph. Returns whether directed=1 was declared.
    fn read_gml_into<G>(
        &mut self,
        graph: &mut G,
        graph_attrs: &mut AttrMap,
        warnings: &mut Vec<String>,
        input: &str,
    ) -> Result<bool, ReadWriteError>
    where
        G: GraphLike,
    {
        let mut directed = false;
        let mut id_to_label: BTreeMap<i64, String> = BTreeMap::new();
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
                    directed = tokens[pos + 1] == "1";
                    pos += 2;
                }
                "node" if pos + 1 < tokens.len() && tokens[pos + 1] == "[" => {
                    pos += 2;
                    let (id, label, attrs, new_pos) =
                        self.parse_gml_node(&tokens, pos, warnings)?;
                    let node_label = label.unwrap_or_else(|| id.to_string());
                    id_to_label.insert(id, node_label.clone());
                    let _ = graph.add_node(node_label);
                    if !attrs.is_empty() {
                        node_attrs_pending.insert(id, attrs);
                    }
                    pos = new_pos;
                }
                "edge" if pos + 1 < tokens.len() && tokens[pos + 1] == "[" => {
                    pos += 2;
                    let (source, target, attrs, new_pos) =
                        self.parse_gml_edge(&tokens, pos, warnings)?;
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

        Ok(directed)
    }

    fn parse_gml_node(
        &self,
        tokens: &[String],
        mut pos: usize,
        _warnings: &mut Vec<String>,
    ) -> Result<(i64, Option<String>, AttrMap, usize), ReadWriteError> {
        let mut id: i64 = 0;
        let mut label: Option<String> = None;
        let mut attrs = AttrMap::new();

        while pos < tokens.len() {
            match tokens[pos].as_str() {
                "]" => {
                    pos += 1;
                    return Ok((id, label, attrs, pos));
                }
                "id" if pos + 1 < tokens.len() => {
                    id =
                        tokens[pos + 1]
                            .parse::<i64>()
                            .map_err(|_| ReadWriteError::FailClosed {
                                operation: "read_gml",
                                reason: format!("invalid node id '{}'", tokens[pos + 1]),
                            })?;
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
        Ok((id, label, attrs, pos))
    }

    fn parse_gml_edge(
        &self,
        tokens: &[String],
        mut pos: usize,
        _warnings: &mut Vec<String>,
    ) -> Result<(i64, i64, AttrMap, usize), ReadWriteError> {
        let mut source: i64 = 0;
        let mut target: i64 = 0;
        let mut attrs = AttrMap::new();

        while pos < tokens.len() {
            match tokens[pos].as_str() {
                "]" => {
                    pos += 1;
                    return Ok((source, target, attrs, pos));
                }
                "source" if pos + 1 < tokens.len() => {
                    source =
                        tokens[pos + 1]
                            .parse::<i64>()
                            .map_err(|_| ReadWriteError::FailClosed {
                                operation: "read_gml",
                                reason: format!("invalid edge source id '{}'", tokens[pos + 1]),
                            })?;
                    pos += 2;
                }
                "target" if pos + 1 < tokens.len() => {
                    target =
                        tokens[pos + 1]
                            .parse::<i64>()
                            .map_err(|_| ReadWriteError::FailClosed {
                                operation: "read_gml",
                                reason: format!("invalid edge target id '{}'", tokens[pos + 1]),
                            })?;
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
        Ok((source, target, attrs, pos))
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
    s.replace('\\', "\\\\").replace('"', "\\\"")
}

/// Format a value for GML: try numeric, otherwise quote it.
fn gml_value_str(value: &CgseValue) -> String {
    let s = value.as_str();
    if value.as_f64().is_some() || s.parse::<i64>().is_ok() {
        s
    } else {
        format!("\"{}\"", gml_escape(&s))
    }
}

fn graphml_attr_type(value: &CgseValue) -> &'static str {
    match value {
        CgseValue::String(_) => "string",
        CgseValue::Float(_) => "double",
        CgseValue::Int(_) => "int",
        CgseValue::Bool(_) => "boolean",
    }
}

/// Remove surrounding quotes from a GML token.
fn gml_unescape(s: &str) -> String {
    let trimmed = s.trim_matches('"');
    trimmed.replace("\\\"", "\"").replace("\\\\", "\\")
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
}

fn attr_escape(s: &str) -> String {
    s.replace('%', "%25")
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

fn graphml_scope_matches(for_scope: &str, target: &str) -> bool {
    let scope = for_scope.trim().to_ascii_lowercase();
    if scope.is_empty() || scope == "all" {
        return true;
    }
    scope == target
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
