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
    use fnx_runtime::{
        CompatibilityMode, DecisionAction, ForensicsBundleIndex, StructuredTestLog, TestKind,
        TestStatus, canonical_environment_fingerprint, structured_test_log_schema_version,
    };
    use proptest::prelude::*;
    use std::collections::{BTreeMap, BTreeSet};

    fn packet_004_forensics_bundle(
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
            bundle_hash_id: "bundle-hash-p2c004".to_owned(),
            captured_unix_ms: 1,
            replay_ref: replay_ref.to_owned(),
            artifact_refs,
            raptorq_sidecar_refs: Vec::new(),
            decode_proof_refs: Vec::new(),
        }
    }

    fn graph_fingerprint(nodes: &[String], edges: &[EdgeRecord]) -> String {
        let edge_signature = edges
            .iter()
            .map(|edge| format!("{}>{}", edge.left, edge.right))
            .collect::<Vec<String>>()
            .join("|");
        format!(
            "nodes:{};edges:{};sig:{edge_signature}",
            nodes.join(","),
            edges.len()
        )
    }

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

    #[test]
    fn unit_packet_004_contract_asserted() {
        let mut converter = GraphConverter::strict();
        let payload = EdgeListPayload {
            nodes: vec!["n0".to_owned(), "n1".to_owned(), "n2".to_owned()],
            edges: vec![
                EdgeRecord {
                    left: "n0".to_owned(),
                    right: "n1".to_owned(),
                    attrs: BTreeMap::new(),
                },
                EdgeRecord {
                    left: "n1".to_owned(),
                    right: "n2".to_owned(),
                    attrs: BTreeMap::from([("weight".to_owned(), "3".to_owned())]),
                },
            ],
        };

        let report = converter
            .from_edge_list(&payload)
            .expect("packet-004 unit contract fixture should convert");
        assert!(report.warnings.is_empty());
        let normalized = to_normalized_payload(&report.graph);
        assert_eq!(normalized.mode, CompatibilityMode::Strict);
        assert_eq!(normalized.nodes, vec!["n0", "n1", "n2"]);
        assert_eq!(normalized.edges.len(), 2);

        let records = report.ledger.records();
        assert_eq!(
            records.len(),
            1,
            "unit contract should emit one decision record"
        );
        let record = &records[0];
        assert_eq!(record.operation, "convert_edge_list");
        assert_eq!(record.mode, CompatibilityMode::Strict);
        assert_eq!(record.action, DecisionAction::Allow);
        assert!(
            record
                .evidence
                .iter()
                .any(|term| term.signal == "message" && term.observed_value.contains("completed")),
            "ledger evidence should include successful conversion marker"
        );

        let mut environment = BTreeMap::new();
        environment.insert("os".to_owned(), std::env::consts::OS.to_owned());
        environment.insert("arch".to_owned(), std::env::consts::ARCH.to_owned());
        environment.insert("conversion_path".to_owned(), "edge_list".to_owned());
        environment.insert("input_shape".to_owned(), "edge_list_payload".to_owned());
        environment.insert("strict_mode".to_owned(), "true".to_owned());

        let replay_command = "rch exec -- cargo test -p fnx-convert unit_packet_004_contract_asserted -- --nocapture";
        let log = StructuredTestLog {
            schema_version: structured_test_log_schema_version().to_owned(),
            run_id: "convert-p2c004-unit".to_owned(),
            ts_unix_ms: 1,
            crate_name: "fnx-convert".to_owned(),
            suite_id: "unit".to_owned(),
            packet_id: "FNX-P2C-004".to_owned(),
            test_name: "unit_packet_004_contract_asserted".to_owned(),
            test_id: "unit::fnx-p2c-004::contract".to_owned(),
            test_kind: TestKind::Unit,
            mode: CompatibilityMode::Strict,
            fixture_id: Some("convert::contract::edge_list".to_owned()),
            seed: Some(7104),
            env_fingerprint: canonical_environment_fingerprint(&environment),
            environment,
            duration_ms: 4,
            replay_command: replay_command.to_owned(),
            artifact_refs: vec!["artifacts/conformance/latest/structured_logs.jsonl".to_owned()],
            forensic_bundle_id: "forensics::convert::unit::contract".to_owned(),
            hash_id: "sha256:convert-p2c004-unit".to_owned(),
            status: TestStatus::Passed,
            reason_code: None,
            failure_repro: None,
            e2e_step_traces: Vec::new(),
            forensics_bundle_index: Some(packet_004_forensics_bundle(
                "convert-p2c004-unit",
                "unit::fnx-p2c-004::contract",
                replay_command,
                "forensics::convert::unit::contract",
                vec!["artifacts/conformance/latest/structured_logs.jsonl".to_owned()],
            )),
        };
        log.validate()
            .expect("unit packet-004 telemetry log should satisfy strict schema");
    }

    proptest! {
        #[test]
        fn property_packet_004_invariants(edges in prop::collection::vec((0_u8..8, 0_u8..8), 1..32)) {
            let mut node_set = BTreeSet::new();
            let mut edge_records = Vec::with_capacity(edges.len());
            for (left, right) in &edges {
                let left_node = format!("n{left}");
                let right_node = format!("n{right}");
                node_set.insert(left_node.clone());
                node_set.insert(right_node.clone());
                edge_records.push(EdgeRecord {
                    left: left_node,
                    right: right_node,
                    attrs: BTreeMap::new(),
                });
            }

            let payload = EdgeListPayload {
                nodes: node_set.into_iter().collect(),
                edges: edge_records,
            };

            let mut strict_left = GraphConverter::strict();
            let mut strict_right = GraphConverter::strict();
            let left = strict_left
                .from_edge_list(&payload)
                .expect("strict conversion should succeed for generated payload");
            let right = strict_right
                .from_edge_list(&payload)
                .expect("strict conversion replay should succeed");
            let left_normalized = to_normalized_payload(&left.graph);
            let right_normalized = to_normalized_payload(&right.graph);

            // Invariant family 1: strict replay determinism.
            prop_assert_eq!(
                &left_normalized,
                &right_normalized,
                "P2C004-IV-1 strict conversion replay drifted"
            );

            let mut hardened_left = GraphConverter::hardened();
            let mut hardened_right = GraphConverter::hardened();
            let hardened_a = hardened_left
                .from_edge_list(&payload)
                .expect("hardened conversion should succeed for generated payload");
            let hardened_b = hardened_right
                .from_edge_list(&payload)
                .expect("hardened conversion replay should succeed");
            let hardened_a_normalized = to_normalized_payload(&hardened_a.graph);
            let hardened_b_normalized = to_normalized_payload(&hardened_b.graph);

            // Invariant family 2: hardened replay determinism.
            prop_assert_eq!(
                &hardened_a_normalized,
                &hardened_b_normalized,
                "P2C004-IV-2 hardened conversion replay drifted"
            );

            // Invariant family 3: edge endpoints are represented in node set.
            for edge in &left_normalized.edges {
                prop_assert!(
                    left_normalized.nodes.contains(&edge.left),
                    "P2C004-IV-3 missing left endpoint node"
                );
                prop_assert!(
                    left_normalized.nodes.contains(&edge.right),
                    "P2C004-IV-3 missing right endpoint node"
                );
            }

            // Invariant family 4: valid payloads produce no warnings.
            prop_assert!(
                left.warnings.is_empty() && right.warnings.is_empty(),
                "P2C004-IV-4 strict mode unexpectedly emitted warnings"
            );
            prop_assert!(
                hardened_a.warnings.is_empty() && hardened_b.warnings.is_empty(),
                "P2C004-IV-4 hardened mode unexpectedly emitted warnings"
            );

            // Invariant family 5: decision ledger remains single-step allow for valid edge-list conversion.
            for ledger in [&left.ledger, &right.ledger, &hardened_a.ledger, &hardened_b.ledger] {
                prop_assert_eq!(ledger.records().len(), 1);
                let record = &ledger.records()[0];
                prop_assert_eq!(record.operation.as_str(), "convert_edge_list");
                prop_assert_eq!(record.action, DecisionAction::Allow);
            }

            let deterministic_seed = edges.iter().fold(7204_u64, |acc, (left, right)| {
                acc.wrapping_mul(131)
                    .wrapping_add((*left as u64) << 8)
                    .wrapping_add(*right as u64)
            });
            let mut environment = BTreeMap::new();
            environment.insert("os".to_owned(), std::env::consts::OS.to_owned());
            environment.insert("arch".to_owned(), std::env::consts::ARCH.to_owned());
            environment.insert(
                "graph_fingerprint".to_owned(),
                graph_fingerprint(&left_normalized.nodes, &left_normalized.edges),
            );
            environment.insert("relabel_mode".to_owned(), "copy".to_owned());
            environment.insert("invariant_id".to_owned(), "P2C004-IV-1".to_owned());

            let replay_command =
                "rch exec -- cargo test -p fnx-convert property_packet_004_invariants -- --nocapture";
            let log = StructuredTestLog {
                schema_version: structured_test_log_schema_version().to_owned(),
                run_id: "convert-p2c004-property".to_owned(),
                ts_unix_ms: 2,
                crate_name: "fnx-convert".to_owned(),
                suite_id: "property".to_owned(),
                packet_id: "FNX-P2C-004".to_owned(),
                test_name: "property_packet_004_invariants".to_owned(),
                test_id: "property::fnx-p2c-004::invariants".to_owned(),
                test_kind: TestKind::Property,
                mode: CompatibilityMode::Hardened,
                fixture_id: Some("convert::property::edge_list_matrix".to_owned()),
                seed: Some(deterministic_seed),
                env_fingerprint: canonical_environment_fingerprint(&environment),
                environment,
                duration_ms: 11,
                replay_command: replay_command.to_owned(),
                artifact_refs: vec![
                    "artifacts/conformance/latest/structured_log_emitter_normalization_report.json"
                        .to_owned(),
                ],
                forensic_bundle_id: "forensics::convert::property::invariants".to_owned(),
                hash_id: "sha256:convert-p2c004-property".to_owned(),
                status: TestStatus::Passed,
                reason_code: None,
                failure_repro: None,
                e2e_step_traces: Vec::new(),
                forensics_bundle_index: Some(packet_004_forensics_bundle(
                    "convert-p2c004-property",
                    "property::fnx-p2c-004::invariants",
                    replay_command,
                    "forensics::convert::property::invariants",
                    vec![
                        "artifacts/conformance/latest/structured_log_emitter_normalization_report.json"
                            .to_owned(),
                    ],
                )),
            };
            prop_assert!(
                log.validate().is_ok(),
                "packet-004 property telemetry log should satisfy strict schema"
            );
        }
    }
}
