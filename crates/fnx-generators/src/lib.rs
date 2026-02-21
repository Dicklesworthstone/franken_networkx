#![forbid(unsafe_code)]

use fnx_classes::Graph;
use fnx_runtime::{
    CompatibilityMode, DecisionAction, DecisionRecord, EvidenceLedger, EvidenceTerm,
    decision_theoretic_action, unix_time_ms,
};
use rand::{RngExt, SeedableRng, rngs::StdRng};
use std::fmt;

const MAX_N_GENERIC: usize = 100_000;
const MAX_N_STAR: usize = MAX_N_GENERIC - 1;
const MAX_N_COMPLETE: usize = 2_000;
const MAX_N_GNP: usize = 20_000;

#[derive(Debug, Clone)]
pub struct GenerationReport {
    pub graph: Graph,
    pub warnings: Vec<String>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum GenerationError {
    FailClosed {
        operation: &'static str,
        reason: String,
    },
}

impl fmt::Display for GenerationError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::FailClosed { operation, reason } => {
                write!(f, "generator `{operation}` failed closed: {reason}")
            }
        }
    }
}

impl std::error::Error for GenerationError {}

#[derive(Debug, Clone)]
pub struct GraphGenerator {
    mode: CompatibilityMode,
    ledger: EvidenceLedger,
}

impl GraphGenerator {
    #[must_use]
    pub fn new(mode: CompatibilityMode) -> Self {
        Self {
            mode,
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

    pub fn empty_graph(&mut self, n: usize) -> Result<GenerationReport, GenerationError> {
        let (n, warnings) = self.validate_n("empty_graph", n, MAX_N_GENERIC)?;
        let (graph, _) = graph_with_n_nodes(self.mode, n);
        self.record(
            "empty_graph",
            DecisionAction::Allow,
            0.02,
            format!("generated empty graph with n={n}"),
        );
        Ok(GenerationReport { graph, warnings })
    }

    pub fn path_graph(&mut self, n: usize) -> Result<GenerationReport, GenerationError> {
        let (n, warnings) = self.validate_n("path_graph", n, MAX_N_GENERIC)?;
        let (mut graph, node_labels) = graph_with_n_nodes(self.mode, n);

        for i in 0..n.saturating_sub(1) {
            graph
                .add_edge(node_labels[i].clone(), node_labels[i + 1].clone())
                .map_err(|err| GenerationError::FailClosed {
                    operation: "path_graph",
                    reason: err.to_string(),
                })?;
        }

        self.record(
            "path_graph",
            DecisionAction::Allow,
            0.03,
            format!("generated path graph with n={n}"),
        );
        Ok(GenerationReport { graph, warnings })
    }

    pub fn star_graph(&mut self, n: usize) -> Result<GenerationReport, GenerationError> {
        // NetworkX integer semantics: star_graph(n) has n spokes and n + 1 nodes total.
        let (n, warnings) = self.validate_n("star_graph", n, MAX_N_STAR)?;
        let (mut graph, node_labels) = graph_with_n_nodes(self.mode, n + 1);
        if let Some((hub, spokes)) = node_labels.split_first() {
            for spoke in spokes {
                graph.add_edge(hub.clone(), spoke.clone()).map_err(|err| {
                    GenerationError::FailClosed {
                        operation: "star_graph",
                        reason: err.to_string(),
                    }
                })?;
            }
        }

        self.record(
            "star_graph",
            DecisionAction::Allow,
            0.03,
            format!("generated star graph with spokes={n}"),
        );
        Ok(GenerationReport { graph, warnings })
    }

    pub fn cycle_graph(&mut self, n: usize) -> Result<GenerationReport, GenerationError> {
        let (n, warnings) = self.validate_n("cycle_graph", n, MAX_N_GENERIC)?;
        let (mut graph, node_labels) = graph_with_n_nodes(self.mode, n);

        if n == 1 {
            graph
                .add_edge(node_labels[0].clone(), node_labels[0].clone())
                .map_err(|err| GenerationError::FailClosed {
                    operation: "cycle_graph",
                    reason: err.to_string(),
                })?;
        } else if n == 2 {
            graph
                .add_edge(node_labels[0].clone(), node_labels[1].clone())
                .map_err(|err| GenerationError::FailClosed {
                    operation: "cycle_graph",
                    reason: err.to_string(),
                })?;
        } else if n >= 3 {
            graph
                .add_edge(node_labels[0].clone(), node_labels[1].clone())
                .map_err(|err| GenerationError::FailClosed {
                    operation: "cycle_graph",
                    reason: err.to_string(),
                })?;
            graph
                .add_edge(node_labels[0].clone(), node_labels[n - 1].clone())
                .map_err(|err| GenerationError::FailClosed {
                    operation: "cycle_graph",
                    reason: err.to_string(),
                })?;
            for i in 1..(n - 1) {
                graph
                    .add_edge(node_labels[i].clone(), node_labels[i + 1].clone())
                    .map_err(|err| GenerationError::FailClosed {
                        operation: "cycle_graph",
                        reason: err.to_string(),
                    })?;
            }
        }

        self.record(
            "cycle_graph",
            DecisionAction::Allow,
            0.03,
            format!("generated cycle graph with n={n}"),
        );
        Ok(GenerationReport { graph, warnings })
    }

    pub fn complete_graph(&mut self, n: usize) -> Result<GenerationReport, GenerationError> {
        let (n, warnings) = self.validate_n("complete_graph", n, MAX_N_COMPLETE)?;
        let (mut graph, node_labels) = graph_with_n_nodes(self.mode, n);

        for left in 0..n {
            for right in (left + 1)..n {
                graph
                    .add_edge(node_labels[left].clone(), node_labels[right].clone())
                    .map_err(|err| GenerationError::FailClosed {
                        operation: "complete_graph",
                        reason: err.to_string(),
                    })?;
            }
        }

        self.record(
            "complete_graph",
            DecisionAction::Allow,
            0.05,
            format!("generated complete graph with n={n}"),
        );
        Ok(GenerationReport { graph, warnings })
    }

    pub fn gnp_random_graph(
        &mut self,
        n: usize,
        p: f64,
        seed: u64,
    ) -> Result<GenerationReport, GenerationError> {
        let (n, mut warnings) = self.validate_n("gnp_random_graph", n, MAX_N_GNP)?;
        let (p, p_warning) = self.validate_probability("gnp_random_graph", p)?;
        if let Some(warning) = p_warning {
            warnings.push(warning);
        }

        let (mut graph, node_labels) = graph_with_n_nodes(self.mode, n);
        let mut rng = StdRng::seed_from_u64(seed);
        for left in 0..n {
            for right in (left + 1)..n {
                let draw: f64 = rng.random();
                if draw < p {
                    graph
                        .add_edge(node_labels[left].clone(), node_labels[right].clone())
                        .map_err(|err| GenerationError::FailClosed {
                            operation: "gnp_random_graph",
                            reason: err.to_string(),
                        })?;
                }
            }
        }

        self.record(
            "gnp_random_graph",
            if warnings.is_empty() {
                DecisionAction::Allow
            } else {
                DecisionAction::FullValidate
            },
            if warnings.is_empty() { 0.08 } else { 0.35 },
            format!("generated gnp graph with n={n}, p={p}, seed={seed}"),
        );
        Ok(GenerationReport { graph, warnings })
    }

    fn validate_n(
        &mut self,
        operation: &'static str,
        n: usize,
        max_allowed: usize,
    ) -> Result<(usize, Vec<String>), GenerationError> {
        if n <= max_allowed {
            return Ok((n, Vec::new()));
        }

        let reason = format!("n={n} exceeds max_allowed={max_allowed}");
        let action = decision_theoretic_action(self.mode, 0.55, false);
        if self.mode == CompatibilityMode::Strict || action == DecisionAction::FailClosed {
            self.record(operation, DecisionAction::FailClosed, 0.95, reason.clone());
            return Err(GenerationError::FailClosed { operation, reason });
        }

        let warning =
            format!("{operation} received n={n}; clamped to {max_allowed} in hardened mode");
        self.record(
            operation,
            DecisionAction::FullValidate,
            0.65,
            warning.clone(),
        );
        Ok((max_allowed, vec![warning]))
    }

    fn validate_probability(
        &mut self,
        operation: &'static str,
        p: f64,
    ) -> Result<(f64, Option<String>), GenerationError> {
        if p.is_nan() {
            let reason = "p is NaN".to_owned();
            if self.mode == CompatibilityMode::Strict {
                self.record(operation, DecisionAction::FailClosed, 1.0, reason.clone());
                return Err(GenerationError::FailClosed { operation, reason });
            }
            let warning = format!("{operation} received NaN probability; clamped to p=0.0");
            self.record(
                operation,
                DecisionAction::FullValidate,
                0.7,
                warning.clone(),
            );
            return Ok((0.0, Some(warning)));
        }
        if (0.0..=1.0).contains(&p) {
            return Ok((p, None));
        }
        let reason = format!("p={p} is outside [0.0, 1.0]");
        if self.mode == CompatibilityMode::Strict {
            self.record(operation, DecisionAction::FailClosed, 1.0, reason.clone());
            return Err(GenerationError::FailClosed { operation, reason });
        }

        let clamped = p.clamp(0.0, 1.0);
        let warning =
            format!("{operation} received out-of-range probability p={p}; clamped to p={clamped}");
        self.record(
            operation,
            DecisionAction::FullValidate,
            0.7,
            warning.clone(),
        );
        Ok((clamped, Some(warning)))
    }

    fn record(
        &mut self,
        operation: &'static str,
        action: DecisionAction,
        incompatibility_probability: f64,
        rationale: String,
    ) {
        self.ledger.record(DecisionRecord {
            ts_unix_ms: unix_time_ms(),
            operation: operation.to_owned(),
            mode: self.mode,
            action,
            incompatibility_probability: incompatibility_probability.clamp(0.0, 1.0),
            rationale: rationale.clone(),
            evidence: vec![EvidenceTerm {
                signal: "generator_rationale".to_owned(),
                observed_value: rationale,
                log_likelihood_ratio: if action == DecisionAction::Allow {
                    -1.0
                } else {
                    2.0
                },
            }],
        });
    }
}

fn graph_with_n_nodes(mode: CompatibilityMode, n: usize) -> (Graph, Vec<String>) {
    let mut graph = Graph::new(mode);
    let mut node_labels = Vec::with_capacity(n);
    for i in 0..n {
        let node_label = i.to_string();
        let _ = graph.add_node(node_label.clone());
        node_labels.push(node_label);
    }
    (graph, node_labels)
}

#[cfg(test)]
mod tests {
    use super::{GenerationError, GraphGenerator, MAX_N_COMPLETE, MAX_N_GENERIC, MAX_N_STAR};
    use fnx_classes::Graph;
    use fnx_runtime::{
        CompatibilityMode, DecisionAction, ForensicsBundleIndex, StructuredTestLog, TestKind,
        TestStatus, canonical_environment_fingerprint, structured_test_log_schema_version,
    };
    use proptest::prelude::*;
    use std::collections::BTreeMap;

    fn packet_007_forensics_bundle(
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
            bundle_hash_id: "bundle-hash-p2c007".to_owned(),
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

    fn graph_fingerprint(graph: &Graph) -> String {
        let snapshot = graph.snapshot();
        let mode = match snapshot.mode {
            CompatibilityMode::Strict => "strict",
            CompatibilityMode::Hardened => "hardened",
        };
        let mut edge_signature = snapshot
            .edges
            .iter()
            .map(|edge| format!("{}>{}", edge.left, edge.right))
            .collect::<Vec<String>>();
        edge_signature.sort();
        format!(
            "mode:{mode};nodes:{};edges:{};sig:{}",
            snapshot.nodes.join(","),
            snapshot.edges.len(),
            edge_signature.join("|")
        )
    }

    #[test]
    fn path_graph_has_expected_structure() {
        let mut generator = GraphGenerator::strict();
        let report = generator
            .path_graph(4)
            .expect("path graph generation should succeed");
        let snapshot = report.graph.snapshot();
        assert_eq!(snapshot.nodes, vec!["0", "1", "2", "3"]);
        assert_eq!(snapshot.edges.len(), 3);
        assert_eq!(snapshot.edges[0].left, "0");
        assert_eq!(snapshot.edges[0].right, "1");
        assert_eq!(snapshot.edges[2].left, "2");
        assert_eq!(snapshot.edges[2].right, "3");
    }

    #[test]
    fn star_graph_has_expected_structure_and_order() {
        let mut generator = GraphGenerator::strict();
        let report = generator
            .star_graph(4)
            .expect("star graph generation should succeed");
        let snapshot = report.graph.snapshot();
        assert_eq!(snapshot.nodes, vec!["0", "1", "2", "3", "4"]);
        let got = snapshot
            .edges
            .iter()
            .map(|edge| (edge.left.clone(), edge.right.clone()))
            .collect::<Vec<(String, String)>>();
        let expected = vec![
            ("0".to_owned(), "1".to_owned()),
            ("0".to_owned(), "2".to_owned()),
            ("0".to_owned(), "3".to_owned()),
            ("0".to_owned(), "4".to_owned()),
        ];
        assert_eq!(got, expected);
    }

    #[test]
    fn star_graph_zero_spokes_has_single_node() {
        let mut generator = GraphGenerator::strict();
        let report = generator
            .star_graph(0)
            .expect("star graph generation should succeed");
        let snapshot = report.graph.snapshot();
        assert_eq!(snapshot.nodes, vec!["0"]);
        assert!(snapshot.edges.is_empty());
    }

    #[test]
    fn cycle_graph_matches_networkx_small_n_behavior() {
        let mut generator = GraphGenerator::strict();
        let one = generator
            .cycle_graph(1)
            .expect("cycle graph generation should succeed");
        let two = generator
            .cycle_graph(2)
            .expect("cycle graph generation should succeed");

        assert_eq!(one.graph.edge_count(), 1, "n=1 should produce a self-loop");
        assert_eq!(two.graph.edge_count(), 1, "n=2 should produce one edge");
    }

    #[test]
    fn cycle_graph_edge_order_matches_networkx_for_n_five() {
        let mut generator = GraphGenerator::strict();
        let report = generator
            .cycle_graph(5)
            .expect("cycle graph generation should succeed");
        let edges = report.graph.snapshot().edges;
        let got = edges
            .iter()
            .map(|edge| (edge.left.clone(), edge.right.clone()))
            .collect::<Vec<(String, String)>>();
        let expected = vec![
            ("0".to_owned(), "1".to_owned()),
            ("0".to_owned(), "4".to_owned()),
            ("1".to_owned(), "2".to_owned()),
            ("2".to_owned(), "3".to_owned()),
            ("3".to_owned(), "4".to_owned()),
        ];
        assert_eq!(got, expected);
    }

    #[test]
    fn complete_graph_has_n_choose_2_edges() {
        let mut generator = GraphGenerator::strict();
        let report = generator
            .complete_graph(5)
            .expect("complete graph generation should succeed");
        assert_eq!(report.graph.edge_count(), 10);
    }

    #[test]
    fn empty_graph_has_expected_nodes_and_no_edges() {
        let mut generator = GraphGenerator::strict();
        let report = generator
            .empty_graph(4)
            .expect("empty graph generation should succeed");
        let snapshot = report.graph.snapshot();
        assert_eq!(snapshot.nodes, vec!["0", "1", "2", "3"]);
        assert!(snapshot.edges.is_empty());
    }

    #[test]
    fn gnp_random_graph_is_seed_reproducible() {
        let mut generator = GraphGenerator::strict();
        let first = generator
            .gnp_random_graph(20, 0.2, 42)
            .expect("gnp generation should succeed")
            .graph
            .snapshot();
        let second = generator
            .gnp_random_graph(20, 0.2, 42)
            .expect("gnp generation should succeed")
            .graph
            .snapshot();
        assert_eq!(first, second);
    }

    #[test]
    fn strict_mode_fails_for_invalid_probability() {
        let mut generator = GraphGenerator::strict();
        let err = generator
            .gnp_random_graph(10, 1.5, 1)
            .expect_err("strict mode should fail closed");
        assert!(matches!(err, GenerationError::FailClosed { .. }));
    }

    #[test]
    fn strict_mode_fails_for_excessive_node_count() {
        let mut generator = GraphGenerator::strict();
        let err = generator
            .complete_graph(MAX_N_COMPLETE + 1)
            .expect_err("strict mode should fail closed for oversize n");
        assert!(matches!(err, GenerationError::FailClosed { .. }));
    }

    #[test]
    fn strict_mode_fails_for_excessive_star_spokes() {
        let mut generator = GraphGenerator::strict();
        let err = generator
            .star_graph(MAX_N_STAR + 1)
            .expect_err("strict mode should fail closed for oversize n");
        assert!(matches!(err, GenerationError::FailClosed { .. }));
    }

    #[test]
    fn hardened_mode_clamps_invalid_probability_with_warning() {
        let mut generator = GraphGenerator::hardened();
        let report = generator
            .gnp_random_graph(10, -0.25, 1)
            .expect("hardened mode should recover");
        assert!(!report.warnings.is_empty());
        assert_eq!(
            report.graph.edge_count(),
            0,
            "clamped p=0 should yield zero edges"
        );
    }

    #[test]
    fn hardened_mode_clamps_excessive_node_count_with_warning() {
        let mut generator = GraphGenerator::hardened();
        let report = generator
            .empty_graph(MAX_N_GENERIC + 5)
            .expect("hardened mode should clamp oversize n");
        assert!(!report.warnings.is_empty());
        assert_eq!(report.graph.node_count(), MAX_N_GENERIC);
        assert_eq!(report.graph.edge_count(), 0);
    }

    #[test]
    fn unit_packet_007_contract_asserted() {
        let mut generator = GraphGenerator::strict();
        let empty = generator
            .empty_graph(4)
            .expect("packet-007 empty_graph contract should succeed");
        let path = generator
            .path_graph(5)
            .expect("packet-007 path_graph contract should succeed");
        let cycle = generator
            .cycle_graph(5)
            .expect("packet-007 cycle_graph contract should succeed");
        let complete = generator
            .complete_graph(4)
            .expect("packet-007 complete_graph contract should succeed");

        assert!(empty.warnings.is_empty());
        assert!(path.warnings.is_empty());
        assert!(cycle.warnings.is_empty());
        assert!(complete.warnings.is_empty());
        assert_eq!(empty.graph.edge_count(), 0, "P2C007-OC-4 drift");
        assert_eq!(path.graph.edge_count(), 4, "P2C007-OC-3 drift");
        assert_eq!(cycle.graph.edge_count(), 5, "P2C007-OC-2 drift");
        assert_eq!(complete.graph.edge_count(), 6, "P2C007-OC-1 drift");

        let path_edges = path
            .graph
            .snapshot()
            .edges
            .into_iter()
            .map(|edge| format!("{}>{}", edge.left, edge.right))
            .collect::<Vec<String>>();
        assert_eq!(
            path_edges,
            vec!["0>1", "1>2", "2>3", "3>4"],
            "P2C007-DC-3 ordered path emission drift"
        );

        let cycle_edges = cycle
            .graph
            .snapshot()
            .edges
            .into_iter()
            .map(|edge| format!("{}>{}", edge.left, edge.right))
            .collect::<Vec<String>>();
        assert_eq!(
            cycle_edges,
            vec!["0>1", "0>4", "1>2", "2>3", "3>4"],
            "P2C007-DC-2 cycle closure ordering drift"
        );

        let oversized = generator.complete_graph(MAX_N_COMPLETE + 1);
        assert!(
            matches!(oversized, Err(GenerationError::FailClosed { .. })),
            "P2C007-EC-2 strict unknown-incompatibility path must fail closed"
        );

        let records = generator.evidence_ledger().records();
        assert!(
            records
                .iter()
                .any(|record| record.operation == "empty_graph"),
            "empty_graph decision record missing"
        );
        assert!(
            records
                .iter()
                .any(|record| record.operation == "path_graph"),
            "path_graph decision record missing"
        );
        assert!(
            records
                .iter()
                .any(|record| record.operation == "cycle_graph"),
            "cycle_graph decision record missing"
        );
        assert!(
            records
                .iter()
                .filter(|record| record.operation == "complete_graph")
                .count()
                >= 2,
            "complete_graph should record both allow and fail-closed pathways"
        );
        assert!(
            records.iter().any(|record| {
                record.operation == "complete_graph" && record.action == DecisionAction::FailClosed
            }),
            "packet-007 strict oversized complete_graph must emit fail-closed evidence"
        );

        let mut environment = BTreeMap::new();
        environment.insert("os".to_owned(), std::env::consts::OS.to_owned());
        environment.insert("arch".to_owned(), std::env::consts::ARCH.to_owned());
        environment.insert(
            "graph_fingerprint".to_owned(),
            graph_fingerprint(&complete.graph),
        );
        environment.insert("mode_policy".to_owned(), "strict".to_owned());
        environment.insert("invariant_id".to_owned(), "P2C007-IV-1".to_owned());
        environment.insert(
            "input_digest".to_owned(),
            stable_digest_hex("empty=4;path=5;cycle=5;complete=4;oversized=true"),
        );
        environment.insert(
            "output_digest".to_owned(),
            stable_digest_hex(&format!(
                "{}|{}|{}|{}",
                graph_fingerprint(&empty.graph),
                graph_fingerprint(&path.graph),
                graph_fingerprint(&cycle.graph),
                graph_fingerprint(&complete.graph)
            )),
        );

        let replay_command = "rch exec -- cargo test -p fnx-generators unit_packet_007_contract_asserted -- --nocapture";
        let artifact_refs = vec![
            "artifacts/phase2c/FNX-P2C-007/contract_table.md".to_owned(),
            "artifacts/conformance/latest/structured_logs.jsonl".to_owned(),
        ];
        let log = StructuredTestLog {
            schema_version: structured_test_log_schema_version().to_owned(),
            run_id: "generators-p2c007-unit".to_owned(),
            ts_unix_ms: 1,
            crate_name: "fnx-generators".to_owned(),
            suite_id: "unit".to_owned(),
            packet_id: "FNX-P2C-007".to_owned(),
            test_name: "unit_packet_007_contract_asserted".to_owned(),
            test_id: "unit::fnx-p2c-007::contract".to_owned(),
            test_kind: TestKind::Unit,
            mode: CompatibilityMode::Strict,
            fixture_id: Some("generators::contract::classic_first_wave".to_owned()),
            seed: Some(7007),
            env_fingerprint: canonical_environment_fingerprint(&environment),
            environment,
            duration_ms: 8,
            replay_command: replay_command.to_owned(),
            artifact_refs: artifact_refs.clone(),
            forensic_bundle_id: "forensics::generators::unit::contract".to_owned(),
            hash_id: "sha256:generators-p2c007-unit".to_owned(),
            status: TestStatus::Passed,
            reason_code: None,
            failure_repro: None,
            e2e_step_traces: Vec::new(),
            forensics_bundle_index: Some(packet_007_forensics_bundle(
                "generators-p2c007-unit",
                "unit::fnx-p2c-007::contract",
                replay_command,
                "forensics::generators::unit::contract",
                artifact_refs,
            )),
        };
        log.validate()
            .expect("packet-007 unit telemetry log should satisfy strict schema");
    }

    proptest! {
        #[test]
        fn property_packet_007_invariants(
            n_path in 0_usize..40,
            n_cycle in 0_usize..40,
            n_complete in 0_usize..30,
            n_random in 0_usize..80,
            seed in any::<u64>(),
            p in 0.0_f64..1.0_f64,
            invalid_probability in prop_oneof![(-2.0_f64..-0.001_f64), (1.001_f64..3.0_f64)],
        ) {
            let mut strict_a = GraphGenerator::strict();
            let mut strict_b = GraphGenerator::strict();

            let path_a = strict_a.path_graph(n_path).expect("strict path_graph should succeed");
            let path_b = strict_b.path_graph(n_path).expect("strict replay path_graph should succeed");

            // Invariant family 1: strict path_graph output is deterministic.
            prop_assert_eq!(
                path_a.graph.snapshot(),
                path_b.graph.snapshot(),
                "P2C007-IV-1 path_graph deterministic output drift"
            );

            let cycle_a = strict_a.cycle_graph(n_cycle).expect("strict cycle_graph should succeed");
            let cycle_b = strict_b.cycle_graph(n_cycle).expect("strict replay cycle_graph should succeed");

            // Invariant family 2: strict cycle_graph output is deterministic.
            prop_assert_eq!(
                cycle_a.graph.snapshot(),
                cycle_b.graph.snapshot(),
                "P2C007-IV-1 cycle_graph deterministic output drift"
            );

            let complete_a = strict_a
                .complete_graph(n_complete)
                .expect("strict complete_graph should succeed");
            let complete_b = strict_b
                .complete_graph(n_complete)
                .expect("strict replay complete_graph should succeed");
            let expected_complete_edges = n_complete.saturating_mul(n_complete.saturating_sub(1)) / 2;

            // Invariant family 3: complete_graph cardinality and ordering remain deterministic.
            prop_assert_eq!(
                complete_a.graph.snapshot(),
                complete_b.graph.snapshot(),
                "P2C007-IV-1 complete_graph deterministic output drift"
            );
            prop_assert_eq!(
                complete_a.graph.edge_count(),
                expected_complete_edges,
                "P2C007-OC-1 complete_graph edge cardinality drift"
            );

            let random_a = strict_a
                .gnp_random_graph(n_random, p, seed)
                .expect("strict gnp_random_graph should succeed");
            let random_b = strict_b
                .gnp_random_graph(n_random, p, seed)
                .expect("strict replay gnp_random_graph should succeed");

            // Invariant family 4: gnp_random_graph is seed-reproducible in strict mode.
            prop_assert_eq!(
                random_a.graph.snapshot(),
                random_b.graph.snapshot(),
                "P2C007-DC-1 seeded random generation drift"
            );

            let mut hardened_prob_a = GraphGenerator::hardened();
            let mut hardened_prob_b = GraphGenerator::hardened();
            let hardened_prob_report_a = hardened_prob_a
                .gnp_random_graph(n_random, invalid_probability, seed)
                .expect("hardened invalid probability should recover deterministically");
            let hardened_prob_report_b = hardened_prob_b
                .gnp_random_graph(n_random, invalid_probability, seed)
                .expect("hardened replay invalid probability should recover deterministically");

            // Invariant family 5: hardened invalid-probability recovery is deterministic and warning-auditable.
            prop_assert_eq!(
                hardened_prob_report_a.graph.snapshot(),
                hardened_prob_report_b.graph.snapshot(),
                "P2C007-IV-3 hardened invalid-probability recovery snapshot drift"
            );
            prop_assert_eq!(
                &hardened_prob_report_a.warnings,
                &hardened_prob_report_b.warnings,
                "P2C007-IV-3 hardened invalid-probability warning envelope drift"
            );
            prop_assert!(
                !hardened_prob_report_a.warnings.is_empty(),
                "P2C007-IV-3 hardened invalid-probability path must emit warnings"
            );

            for strict_engine in [&strict_a, &strict_b] {
                let records = strict_engine.evidence_ledger().records();
                prop_assert!(
                    records.iter().all(|record| record.action == DecisionAction::Allow),
                    "strict property runs should remain allow-only for in-range generated payloads"
                );
            }

            for hardened_engine in [&hardened_prob_a, &hardened_prob_b] {
                let records = hardened_engine.evidence_ledger().records();
                prop_assert!(
                    records.iter().any(|record| record.action == DecisionAction::FullValidate),
                    "hardened property runs should include at least one full-validate decision"
                );
            }

            let deterministic_seed = (n_path as u64)
                .wrapping_mul(131)
                .wrapping_add((n_cycle as u64).wrapping_mul(137))
                .wrapping_add((n_complete as u64).wrapping_mul(149))
                .wrapping_add((n_random as u64).wrapping_mul(157))
                .wrapping_add(seed.rotate_left(7));

            let mut environment = BTreeMap::new();
            environment.insert("os".to_owned(), std::env::consts::OS.to_owned());
            environment.insert("arch".to_owned(), std::env::consts::ARCH.to_owned());
            environment.insert(
                "graph_fingerprint".to_owned(),
                graph_fingerprint(&random_a.graph),
            );
            environment.insert("mode_policy".to_owned(), "strict_and_hardened".to_owned());
            environment.insert("invariant_id".to_owned(), "P2C007-IV-1..IV-3".to_owned());
            environment.insert(
                "input_digest".to_owned(),
                stable_digest_hex(&format!(
                    "n_path={n_path};n_cycle={n_cycle};n_complete={n_complete};n_random={n_random};p={p:.6};invalid_probability={invalid_probability:.6};seed={seed}"
                )),
            );
            environment.insert(
                "output_digest".to_owned(),
                stable_digest_hex(&format!(
                    "{}|{}",
                    graph_fingerprint(&random_a.graph),
                    graph_fingerprint(&hardened_prob_report_a.graph)
                )),
            );

            let replay_command =
                "rch exec -- cargo test -p fnx-generators property_packet_007_invariants -- --nocapture";
            let artifact_refs = vec![
                "artifacts/conformance/latest/structured_log_emitter_normalization_report.json"
                    .to_owned(),
            ];
            let log = StructuredTestLog {
                schema_version: structured_test_log_schema_version().to_owned(),
                run_id: "generators-p2c007-property".to_owned(),
                ts_unix_ms: 2,
                crate_name: "fnx-generators".to_owned(),
                suite_id: "property".to_owned(),
                packet_id: "FNX-P2C-007".to_owned(),
                test_name: "property_packet_007_invariants".to_owned(),
                test_id: "property::fnx-p2c-007::invariants".to_owned(),
                test_kind: TestKind::Property,
                mode: CompatibilityMode::Hardened,
                fixture_id: Some("generators::property::classic_first_wave_matrix".to_owned()),
                seed: Some(deterministic_seed),
                env_fingerprint: canonical_environment_fingerprint(&environment),
                environment,
                duration_ms: 17,
                replay_command: replay_command.to_owned(),
                artifact_refs: artifact_refs.clone(),
                forensic_bundle_id: "forensics::generators::property::invariants".to_owned(),
                hash_id: "sha256:generators-p2c007-property".to_owned(),
                status: TestStatus::Passed,
                reason_code: None,
                failure_repro: None,
                e2e_step_traces: Vec::new(),
                forensics_bundle_index: Some(packet_007_forensics_bundle(
                    "generators-p2c007-property",
                    "property::fnx-p2c-007::invariants",
                    replay_command,
                    "forensics::generators::property::invariants",
                    artifact_refs,
                )),
            };
            prop_assert!(
                log.validate().is_ok(),
                "packet-007 property telemetry log should satisfy strict schema"
            );
        }
    }
}
