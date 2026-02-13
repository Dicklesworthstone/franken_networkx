#![forbid(unsafe_code)]

use fnx_classes::Graph;
use fnx_runtime::{
    CompatibilityMode, DecisionAction, DecisionRecord, EvidenceLedger, EvidenceTerm,
    decision_theoretic_action, unix_time_ms,
};
use rand::{Rng, SeedableRng, rngs::StdRng};
use std::fmt;

const MAX_N_GENERIC: usize = 100_000;
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
        let graph = graph_with_n_nodes(self.mode, n);
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
        let mut graph = graph_with_n_nodes(self.mode, n);

        for i in 0..n.saturating_sub(1) {
            graph
                .add_edge(i.to_string(), (i + 1).to_string())
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

    pub fn cycle_graph(&mut self, n: usize) -> Result<GenerationReport, GenerationError> {
        let (n, warnings) = self.validate_n("cycle_graph", n, MAX_N_GENERIC)?;
        let mut graph = graph_with_n_nodes(self.mode, n);

        if n == 1 {
            graph
                .add_edge("0", "0")
                .map_err(|err| GenerationError::FailClosed {
                    operation: "cycle_graph",
                    reason: err.to_string(),
                })?;
        } else if n == 2 {
            graph
                .add_edge("0", "1")
                .map_err(|err| GenerationError::FailClosed {
                    operation: "cycle_graph",
                    reason: err.to_string(),
                })?;
        } else if n >= 3 {
            graph
                .add_edge("0", "1")
                .map_err(|err| GenerationError::FailClosed {
                    operation: "cycle_graph",
                    reason: err.to_string(),
                })?;
            graph.add_edge("0", (n - 1).to_string()).map_err(|err| {
                GenerationError::FailClosed {
                    operation: "cycle_graph",
                    reason: err.to_string(),
                }
            })?;
            for i in 1..(n - 1) {
                graph
                    .add_edge(i.to_string(), (i + 1).to_string())
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
        let mut graph = graph_with_n_nodes(self.mode, n);

        for left in 0..n {
            for right in (left + 1)..n {
                graph
                    .add_edge(left.to_string(), right.to_string())
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

        let mut graph = graph_with_n_nodes(self.mode, n);
        let mut rng = StdRng::seed_from_u64(seed);
        for left in 0..n {
            for right in (left + 1)..n {
                let draw: f64 = rng.random();
                if draw < p {
                    graph
                        .add_edge(left.to_string(), right.to_string())
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

fn graph_with_n_nodes(mode: CompatibilityMode, n: usize) -> Graph {
    let mut graph = Graph::new(mode);
    for i in 0..n {
        let _ = graph.add_node(i.to_string());
    }
    graph
}

#[cfg(test)]
mod tests {
    use super::{GenerationError, GraphGenerator, MAX_N_COMPLETE, MAX_N_GENERIC};

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
}
