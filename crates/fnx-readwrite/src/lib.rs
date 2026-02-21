#![forbid(unsafe_code)]

use fnx_classes::{AttrMap, Graph, GraphError, GraphSnapshot};
use fnx_dispatch::{BackendRegistry, BackendSpec, DispatchError, DispatchRequest};
use fnx_runtime::{
    CompatibilityMode, DecisionAction, DecisionRecord, EvidenceLedger, EvidenceTerm, unix_time_ms,
};
use quick_xml::events::{BytesDecl, BytesEnd, BytesStart, BytesText, Event};
use quick_xml::{Reader, Writer};
use std::collections::{BTreeMap, BTreeSet};
use std::fmt;
use std::io::Cursor;

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

            // Optimization lever: parse tokens in a streaming fashion to avoid per-line Vec allocation.
            let mut parts = line.split_whitespace();
            let left = parts.next();
            let right = parts.next();
            let attrs = parts.next();
            let extra = parts.next();
            if left.is_none() || right.is_none() || extra.is_some() {
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

            let left = left.expect("left token should be present after malformed check");
            let right = right.expect("right token should be present after malformed check");
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

        Ok(ReadWriteReport { graph, warnings })
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

    pub fn write_graphml(&mut self, graph: &Graph) -> Result<String, ReadWriteError> {
        self.dispatch.resolve(&DispatchRequest {
            operation: "write_graphml".to_owned(),
            requested_backend: None,
            required_features: set(["write_graphml"]),
            risk_probability: 0.03,
            unknown_incompatible_feature: false,
        })?;

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

        let snapshot = graph.snapshot();

        // Collect all distinct attribute keys from nodes and edges.
        let mut node_attr_keys = BTreeSet::new();
        let mut edge_attr_keys = BTreeSet::new();
        for node_id in &snapshot.nodes {
            if let Some(attrs) = graph.node_attrs(node_id) {
                for key in attrs.keys() {
                    node_attr_keys.insert(key.clone());
                }
            }
        }
        for edge in &snapshot.edges {
            for key in edge.attrs.keys() {
                edge_attr_keys.insert(key.clone());
            }
        }

        // Emit <key> declarations for node attributes.
        let mut key_counter = 0_usize;
        let mut node_key_ids: BTreeMap<String, String> = BTreeMap::new();
        for attr_name in &node_attr_keys {
            let key_id = format!("d{key_counter}");
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
            let key_id = format!("d{key_counter}");
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
        graph_elem.push_attribute(("edgedefault", "undirected"));
        writer
            .write_event(Event::Start(graph_elem))
            .map_err(|e| xml_write_err("graph_start", e))?;

        // Emit <node> elements in insertion order.
        for node_id in &snapshot.nodes {
            let node_attrs = graph.node_attrs(node_id);
            let has_data = node_attrs.is_some_and(|a| !a.is_empty());
            let mut node_elem = BytesStart::new("node");
            node_elem.push_attribute(("id", node_id.as_str()));

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
                            writer
                                .write_event(Event::Text(BytesText::new(attr_value)))
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

        // Emit <edge> elements in insertion order.
        for edge in &snapshot.edges {
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
                        writer
                            .write_event(Event::Text(BytesText::new(attr_value)))
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
        let mut warnings = Vec::new();

        // Key registry: key_id -> (for_scope, attr_name)
        let mut key_registry: BTreeMap<String, (String, String)> = BTreeMap::new();

        let mut reader = Reader::from_str(input);
        reader.config_mut().trim_text(true);

        // Parser state.
        let mut in_graph = false;
        let mut current_node: Option<String> = None;
        let mut current_edge: Option<(String, String)> = None;
        let mut current_data_key: Option<String> = None;
        let mut current_data_text = String::new();

        // Collect node/edge attrs to apply after parsing each element.
        let mut pending_node_attrs: AttrMap = AttrMap::new();
        let mut pending_edge_attrs: AttrMap = AttrMap::new();

        loop {
            let event = reader.read_event();
            match event {
                Ok(Event::Start(ref e)) => {
                    self.handle_graphml_start_element(
                        e,
                        false,
                        &mut graph,
                        &mut warnings,
                        &mut key_registry,
                        &mut in_graph,
                        &mut current_node,
                        &mut current_edge,
                        &mut current_data_key,
                        &mut current_data_text,
                        &mut pending_node_attrs,
                        &mut pending_edge_attrs,
                    )?;
                }
                Ok(Event::Empty(ref e)) => {
                    self.handle_graphml_start_element(
                        e,
                        true,
                        &mut graph,
                        &mut warnings,
                        &mut key_registry,
                        &mut in_graph,
                        &mut current_node,
                        &mut current_edge,
                        &mut current_data_key,
                        &mut current_data_text,
                        &mut pending_node_attrs,
                        &mut pending_edge_attrs,
                    )?;
                    // For empty elements like <node id="x"/>, immediately finalize.
                    self.handle_graphml_end_element(
                        e.name().as_ref(),
                        &mut graph,
                        &mut warnings,
                        &mut in_graph,
                        &mut current_node,
                        &mut current_edge,
                        &mut current_data_key,
                        &mut current_data_text,
                        &mut pending_node_attrs,
                        &mut pending_edge_attrs,
                        &key_registry,
                    )?;
                }
                Ok(Event::Text(ref e)) => {
                    if current_data_key.is_some() {
                        current_data_text.push_str(&e.unescape().unwrap_or_default());
                    }
                }
                Ok(Event::End(ref e)) => {
                    self.handle_graphml_end_element(
                        e.name().as_ref(),
                        &mut graph,
                        &mut warnings,
                        &mut in_graph,
                        &mut current_node,
                        &mut current_edge,
                        &mut current_data_key,
                        &mut current_data_text,
                        &mut pending_node_attrs,
                        &mut pending_edge_attrs,
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

        self.record(
            "read_graphml",
            DecisionAction::Allow,
            "graphml parse completed",
            0.04,
        );

        Ok(ReadWriteReport { graph, warnings })
    }

    #[allow(clippy::too_many_arguments)]
    fn handle_graphml_start_element(
        &mut self,
        e: &BytesStart<'_>,
        _is_empty: bool,
        graph: &mut Graph,
        warnings: &mut Vec<String>,
        key_registry: &mut BTreeMap<String, (String, String)>,
        in_graph: &mut bool,
        current_node: &mut Option<String>,
        current_edge: &mut Option<(String, String)>,
        current_data_key: &mut Option<String>,
        current_data_text: &mut String,
        pending_node_attrs: &mut AttrMap,
        pending_edge_attrs: &mut AttrMap,
    ) -> Result<(), ReadWriteError> {
        let tag_name = e.name();
        let local = tag_name.as_ref();
        match local {
            b"key" => {
                let mut key_id = String::new();
                let mut for_scope = String::new();
                let mut attr_name = String::new();
                for attr in e.attributes().flatten() {
                    match attr.key.as_ref() {
                        b"id" => {
                            key_id = String::from_utf8_lossy(&attr.value).into_owned();
                        }
                        b"for" => {
                            for_scope = String::from_utf8_lossy(&attr.value).into_owned();
                        }
                        b"attr.name" => {
                            attr_name = String::from_utf8_lossy(&attr.value).into_owned();
                        }
                        _ => {}
                    }
                }
                if !key_id.is_empty() && !attr_name.is_empty() {
                    key_registry.insert(key_id, (for_scope, attr_name));
                }
            }
            b"graph" => {
                *in_graph = true;
            }
            b"node" if *in_graph => {
                let mut node_id = String::new();
                for attr in e.attributes().flatten() {
                    if attr.key.as_ref() == b"id" {
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
                for attr in e.attributes().flatten() {
                    match attr.key.as_ref() {
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
                for attr in e.attributes().flatten() {
                    if attr.key.as_ref() == b"key" {
                        *current_data_key = Some(String::from_utf8_lossy(&attr.value).into_owned());
                    }
                }
            }
            _ => {}
        }
        Ok(())
    }

    #[allow(clippy::too_many_arguments)]
    fn handle_graphml_end_element(
        &mut self,
        local: &[u8],
        graph: &mut Graph,
        warnings: &mut Vec<String>,
        in_graph: &mut bool,
        current_node: &mut Option<String>,
        current_edge: &mut Option<(String, String)>,
        current_data_key: &mut Option<String>,
        current_data_text: &mut String,
        pending_node_attrs: &mut AttrMap,
        pending_edge_attrs: &mut AttrMap,
        key_registry: &BTreeMap<String, (String, String)>,
    ) -> Result<(), ReadWriteError> {
        match local {
            b"data" => {
                if let Some(key_id) = current_data_key.take()
                    && let Some((_scope, attr_name)) = key_registry.get(&key_id)
                {
                    let value = std::mem::take(current_data_text);
                    if current_node.is_some() && current_edge.is_none() {
                        pending_node_attrs.insert(attr_name.clone(), value);
                    } else if current_edge.is_some() {
                        pending_edge_attrs.insert(attr_name.clone(), value);
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
                *in_graph = false;
            }
            _ => {}
        }
        Ok(())
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

fn xml_write_err(context: &str, err: std::io::Error) -> ReadWriteError {
    ReadWriteError::FailClosed {
        operation: "write_graphml",
        reason: format!("xml write error ({context}): {err}"),
    }
}

fn set<const N: usize>(values: [&str; N]) -> BTreeSet<String> {
    values.into_iter().map(str::to_owned).collect()
}

#[cfg(test)]
mod tests {
    use super::{EdgeListEngine, ReadWriteError};
    use fnx_classes::{Graph, GraphSnapshot};
    use fnx_runtime::{
        CompatibilityMode, DecisionAction, ForensicsBundleIndex, StructuredTestLog, TestKind,
        TestStatus, canonical_environment_fingerprint, structured_test_log_schema_version,
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
                    .map(|(key, value)| format!("{key}={value}"))
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
                BTreeMap::from([("weight".to_owned(), "1".to_owned())]),
            )
            .expect("edge add should succeed");
        graph
            .add_edge_with_attrs(
                "a".to_owned(),
                "c".to_owned(),
                BTreeMap::from([("label".to_owned(), "blue".to_owned())]),
            )
            .expect("edge add should succeed");
        graph
            .add_edge_with_attrs(
                "b".to_owned(),
                "d".to_owned(),
                BTreeMap::from([
                    ("weight".to_owned(), "3".to_owned()),
                    ("capacity".to_owned(), "7".to_owned()),
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
    fn adjlist_round_trip_is_deterministic() {
        let mut graph = Graph::strict();
        graph.add_edge("a", "b").expect("edge add should succeed");
        graph.add_edge("a", "c").expect("edge add should succeed");
        graph.add_node("d");

        let mut engine = EdgeListEngine::strict();
        let text = engine
            .write_adjlist(&graph)
            .expect("adjlist serialization should succeed");
        assert_eq!(text, "a b c\nb a\nc a\nd");

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
    fn graphml_round_trip_with_edge_attrs() {
        let mut graph = Graph::strict();
        graph
            .add_edge_with_attrs(
                "a".to_owned(),
                "b".to_owned(),
                BTreeMap::from([("weight".to_owned(), "1".to_owned())]),
            )
            .expect("edge add should succeed");
        graph
            .add_edge_with_attrs(
                "b".to_owned(),
                "c".to_owned(),
                BTreeMap::from([("weight".to_owned(), "3".to_owned())]),
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
            BTreeMap::from([("color".to_owned(), "red".to_owned())]),
        );
        graph.add_node_with_attrs(
            "b".to_owned(),
            BTreeMap::from([("color".to_owned(), "blue".to_owned())]),
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
                            ((u16::from(*left) + u16::from(*right)) + 1).to_string(),
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
    }
}
