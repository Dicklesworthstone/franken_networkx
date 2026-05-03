#![forbid(unsafe_code)]

use fnx_classes::Graph;
use fnx_classes::digraph::{DiGraph, MultiDiGraph};
use fnx_runtime::{CompatibilityMode, DecisionAction, EvidenceLedger, EvidenceTerm, RuntimePolicy};
use mt19937::{MT19937, gen_res53};
use rand::Rng;
use std::fmt;

/// Maximum nodes for general generators (path, cycle, empty, etc.).
/// At average degree ~10, a 100k-node graph uses ~2M edges ≈ 48MB.
/// This cap prevents accidental denial-of-service from huge inputs.
const MAX_N_GENERIC: usize = 100_000;

/// Star graph cap. star_graph(n) creates a hub with n spokes = n edges.
/// Set to MAX_N_GENERIC - 1 so total nodes (hub + spokes) stays within
/// the generic budget.
const MAX_N_STAR: usize = MAX_N_GENERIC - 1;

/// Complete graph cap. K_n has n*(n-1)/2 edges.
/// K_2000 ≈ 2M edges ≈ 48MB edge storage. K_3000 would be ~4.5M edges,
/// pushing memory above 100MB for a single graph.
const MAX_N_COMPLETE: usize = 2_000;

/// G(n,p) and similar O(n²) random graph cap.
/// The naive algorithm iterates all n*(n-1)/2 candidate edges.
/// At n=20000 that's ~200M iterations — ~1 second in Rust.
/// Beyond this, generation time becomes user-visible.
const MAX_N_GNP: usize = 20_000;

/// Tolerance for validating probability parameter sums (e.g.,
/// scale_free_graph alpha+beta+gamma = 1.0). Matches NetworkX.
const PARAM_SUM_EPSILON: f64 = 1.0e-6;

#[derive(Debug, Clone)]
pub struct GenerationReport {
    pub graph: Graph,
    pub warnings: Vec<String>,
}

#[derive(Debug, Clone)]
pub struct DiGenerationReport {
    pub graph: DiGraph,
    pub warnings: Vec<String>,
}

#[derive(Debug, Clone)]
pub struct MultiDiGenerationReport {
    pub graph: MultiDiGraph,
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
    runtime_policy: RuntimePolicy,
}

impl GraphGenerator {
    #[must_use]
    pub fn new(mode: CompatibilityMode) -> Self {
        Self {
            mode,
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

    fn finish_graph_report(&self, mut graph: Graph, warnings: Vec<String>) -> GenerationReport {
        graph.set_runtime_policy(self.runtime_policy.clone());
        GenerationReport { graph, warnings }
    }

    fn finish_digraph_report(
        &self,
        mut graph: DiGraph,
        warnings: Vec<String>,
    ) -> DiGenerationReport {
        graph.set_runtime_policy(self.runtime_policy.clone());
        DiGenerationReport { graph, warnings }
    }

    fn finish_multidigraph_report(
        &self,
        mut graph: MultiDiGraph,
        warnings: Vec<String>,
    ) -> MultiDiGenerationReport {
        graph.set_runtime_policy(self.runtime_policy.clone());
        MultiDiGenerationReport { graph, warnings }
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
        Ok(self.finish_graph_report(graph, warnings))
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
        Ok(self.finish_graph_report(graph, warnings))
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
        Ok(self.finish_graph_report(graph, warnings))
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
        Ok(self.finish_graph_report(graph, warnings))
    }

    pub fn complete_graph(&mut self, n: usize) -> Result<GenerationReport, GenerationError> {
        let (n, warnings) = self.validate_n("complete_graph", n, MAX_N_COMPLETE)?;
        let graph = Graph::complete_graph(self.mode, n);

        self.record(
            "complete_graph",
            DecisionAction::Allow,
            0.05,
            format!("generated complete graph with n={n}"),
        );
        Ok(self.finish_graph_report(graph, warnings))
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
        let mut rng = PythonRandom::new(seed);
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
        Ok(self.finish_graph_report(graph, warnings))
    }

    /// Generate a Watts-Strogatz small-world graph.
    ///
    /// Start with a ring lattice of `n` nodes where each node is connected
    /// to its `k` nearest neighbours (floor(k/2) on each side). Then rewire
    /// each edge with probability `p`.
    ///
    /// Matches NetworkX semantics: odd `k` connects to `k - 1` nearest
    /// neighbors, and `k == n` returns the complete graph.
    pub fn watts_strogatz_graph(
        &mut self,
        n: usize,
        k: usize,
        p: f64,
        seed: u64,
    ) -> Result<GenerationReport, GenerationError> {
        let (n, mut warnings) = self.validate_n("watts_strogatz_graph", n, MAX_N_GNP)?;
        let (p, p_warning) = self.validate_probability("watts_strogatz_graph", p)?;
        if let Some(warning) = p_warning {
            warnings.push(warning);
        }

        if k > n {
            return Err(GenerationError::FailClosed {
                operation: "watts_strogatz_graph",
                reason: "k>n, choose smaller k or larger n".to_owned(),
            });
        }
        if k == n {
            return self.complete_graph(n);
        }
        if k < 2 {
            return Err(GenerationError::FailClosed {
                operation: "watts_strogatz_graph",
                reason: format!("requires k >= 2, got k={k}"),
            });
        }

        let half_k = k / 2;
        let mut rng = PythonRandom::new(seed);
        let graph = watts_strogatz_graph_core(self.mode, n, half_k, p, &mut rng);

        self.record(
            "watts_strogatz_graph",
            if warnings.is_empty() {
                DecisionAction::Allow
            } else {
                DecisionAction::FullValidate
            },
            if warnings.is_empty() { 0.08 } else { 0.35 },
            format!("generated watts-strogatz graph with n={n}, k={k}, p={p}, seed={seed}"),
        );
        Ok(self.finish_graph_report(graph, warnings))
    }

    /// Generate a Barabási-Albert preferential attachment graph.
    ///
    /// Start with a complete graph of `m` nodes, then add `n - m` nodes
    /// one at a time, each connecting to `m` existing nodes chosen with
    /// probability proportional to their degree.
    ///
    /// Requires `m >= 1` and `n >= m`.
    pub fn barabasi_albert_graph(
        &mut self,
        n: usize,
        m: usize,
        seed: u64,
    ) -> Result<GenerationReport, GenerationError> {
        let (n, mut warnings) = self.validate_n("barabasi_albert_graph", n, MAX_N_GNP)?;

        if m < 1 || m >= n {
            return Err(GenerationError::FailClosed {
                operation: "barabasi_albert_graph",
                reason: format!("requires 1 <= m < n, got m={m}, n={n}"),
            });
        }

        // NetworkX default initial graph: star graph on m + 1 nodes (0..m).
        let report = self.star_graph(m)?;
        let mut graph = report.graph;
        warnings.extend(report.warnings);

        // Maintain a "repeated list" of nodes for proportional-to-degree sampling.
        // Each time an edge (u, v) is added, both u and v appear once more.
        let mut repeated_nodes: Vec<usize> = vec![0; m];
        // Star graph (m+1 nodes) has node 0 as center connected to nodes 1..m.
        // Degree(0) = m, Degree(1..m) = 1.
        for i in 1..=m {
            repeated_nodes.push(i);
        }

        // Node labels are "0", "1", ..., "n-1"
        let node_labels: Vec<String> = (0..n).map(|i| i.to_string()).collect();

        let mut rng = PythonRandom::new(seed);
        // Grow the graph: add nodes m+1..n-1 one at a time.
        for source in (m + 1)..n {
            graph.add_node(node_labels[source].clone());

            // Choose m distinct targets from existing nodes proportional to degree.
            let mut targets = Vec::with_capacity(m);
            let mut target_set = std::collections::HashSet::new();

            while targets.len() < m {
                let idx = rng.randrange(repeated_nodes.len());
                let candidate = repeated_nodes[idx];
                if target_set.insert(candidate) {
                    targets.push(candidate);
                }
            }

            // Add edges from new node to chosen targets.
            for &target in &targets {
                let _ = graph.add_edge(node_labels[source].clone(), node_labels[target].clone());
                repeated_nodes.push(source);
                repeated_nodes.push(target);
            }
        }

        self.record(
            "barabasi_albert_graph",
            DecisionAction::Allow,
            0.08,
            format!("generated barabasi-albert graph with n={n}, m={m}, seed={seed}"),
        );
        Ok(self.finish_graph_report(graph, warnings))
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
        let action = self.runtime_policy.action_for(0.55, false);
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

    /// Generate a Newman-Watts-Strogatz small-world graph.
    ///
    /// Like Watts-Strogatz but adds shortcut edges instead of rewiring,
    /// guaranteeing the graph stays connected.
    pub fn newman_watts_strogatz_graph(
        &mut self,
        n: usize,
        k: usize,
        p: f64,
        seed: u64,
    ) -> Result<GenerationReport, GenerationError> {
        let (n, mut warnings) = self.validate_n("newman_watts_strogatz_graph", n, MAX_N_GNP)?;
        let (p, p_warning) = self.validate_probability("newman_watts_strogatz_graph", p)?;
        if let Some(warning) = p_warning {
            warnings.push(warning);
        }

        if k > n {
            return Err(GenerationError::FailClosed {
                operation: "newman_watts_strogatz_graph",
                reason: "k>=n, choose smaller k or larger n".to_owned(),
            });
        }
        if k == n {
            return self.complete_graph(n);
        }
        if k < 2 {
            return Err(GenerationError::FailClosed {
                operation: "newman_watts_strogatz_graph",
                reason: format!("requires k >= 2, got k={k}"),
            });
        }

        let (mut graph, node_labels) = graph_with_n_nodes(self.mode, n);
        let half_k = k / 2;
        let mut rng = PythonRandom::new(seed);

        let ring_edges = ring_lattice_edges(n, half_k);
        for &(u, v) in &ring_edges {
            let _ = graph.add_edge(node_labels[u].clone(), node_labels[v].clone());
        }

        let edge_order: Vec<(usize, usize)> = (0..n)
            .flat_map(|u| {
                graph
                    .neighbors(&node_labels[u])
                    .unwrap_or_default()
                    .into_iter()
                    .filter_map(move |neighbor| {
                        let v = neighbor.parse::<usize>().ok()?;
                        (v > u).then_some((u, v))
                    })
            })
            .collect();

        for (u, _) in edge_order {
            if rng.random() < p {
                let mut new_target = rng.randrange(n);
                let mut skip_shortcut = false;
                while new_target == u || graph.has_edge(&node_labels[u], &node_labels[new_target]) {
                    new_target = rng.randrange(n);
                    if graph.degree(&node_labels[u]) >= n - 1 {
                        skip_shortcut = true;
                        break;
                    }
                }
                if !skip_shortcut {
                    let _ = graph.add_edge(node_labels[u].clone(), node_labels[new_target].clone());
                }
            }
        }

        self.record(
            "newman_watts_strogatz_graph",
            DecisionAction::Allow,
            0.08,
            format!("generated newman-watts-strogatz graph with n={n}, k={k}, p={p}, seed={seed}"),
        );
        Ok(self.finish_graph_report(graph, warnings))
    }

    /// Generate a connected Watts-Strogatz small-world graph.
    ///
    /// Repeatedly generates a Watts-Strogatz graph until a connected one is
    /// found, advancing a single RNG stream across attempts.
    pub fn connected_watts_strogatz_graph(
        &mut self,
        n: usize,
        k: usize,
        p: f64,
        tries: usize,
        seed: u64,
    ) -> Result<GenerationReport, GenerationError> {
        let (n, mut warnings) = self.validate_n("connected_watts_strogatz_graph", n, MAX_N_GNP)?;
        let (p, p_warning) = self.validate_probability("connected_watts_strogatz_graph", p)?;
        if let Some(warning) = p_warning {
            warnings.push(warning);
        }

        if k > n {
            return Err(GenerationError::FailClosed {
                operation: "connected_watts_strogatz_graph",
                reason: "k>n, choose smaller k or larger n".to_owned(),
            });
        }
        if k == n {
            return self.complete_graph(n);
        }
        if k < 2 {
            return Err(GenerationError::FailClosed {
                operation: "connected_watts_strogatz_graph",
                reason: format!("requires k >= 2, got k={k}"),
            });
        }

        let half_k = k / 2;
        let mut rng = PythonRandom::new(seed);
        for _ in 0..tries {
            let graph = watts_strogatz_graph_core(self.mode, n, half_k, p, &mut rng);
            if graph_is_connected(&graph) {
                self.record(
                    "connected_watts_strogatz_graph",
                    if warnings.is_empty() {
                        DecisionAction::Allow
                    } else {
                        DecisionAction::FullValidate
                    },
                    if warnings.is_empty() { 0.08 } else { 0.35 },
                    format!(
                        "generated connected watts-strogatz graph with n={n}, k={k}, p={p}, tries={tries}, seed={seed}"
                    ),
                );
                return Ok(self.finish_graph_report(graph, warnings));
            }
        }
        Err(GenerationError::FailClosed {
            operation: "connected_watts_strogatz_graph",
            reason: "Maximum number of tries exceeded".to_owned(),
        })
    }

    /// Generate a random k-regular graph on n nodes.
    ///
    /// Uses the pairing model: generate a random perfect matching on
    /// n*k half-edges, then check for multi-edges. Retry if invalid.
    pub fn random_regular_graph(
        &mut self,
        n: usize,
        d: usize,
        seed: u64,
    ) -> Result<GenerationReport, GenerationError> {
        let (n, warnings) = self.validate_n("random_regular_graph", n, MAX_N_GNP)?;

        if !(n * d).is_multiple_of(2) {
            return Err(GenerationError::FailClosed {
                operation: "random_regular_graph",
                reason: format!("n*d must be even, got n={n}, d={d}"),
            });
        }
        if d >= n {
            return Err(GenerationError::FailClosed {
                operation: "random_regular_graph",
                reason: format!("d must be < n, got n={n}, d={d}"),
            });
        }

        let mut rng = PythonRandom::new(seed);
        let (_, node_labels) = graph_with_n_nodes(self.mode, n);
        // br-r37-c1-nzo8r: port nx's smarter stub-pairing algorithm.
        // The naive "any duplicate/self-edge → throw away the whole
        // attempt" loop fails for ~20% of seeds at d=4,n=10. nx tracks
        // unmatched stubs in `potential_edges` and only restarts the
        // outer attempt when `_suitable` proves no remaining edges can
        // be placed. With this, convergence is essentially always 1
        // outer attempt.
        let max_tries = 100;

        for _ in 0..max_tries {
            if let Some(edge_pairs) = try_create_random_regular(&mut rng, n, d) {
                let mut graph = Graph::new(self.mode);
                for label in &node_labels {
                    let _ = graph.add_node(label.clone());
                }
                for (u, v) in &edge_pairs {
                    let _ = graph.add_edge(node_labels[*u].clone(), node_labels[*v].clone());
                }
                self.record(
                    "random_regular_graph",
                    DecisionAction::Allow,
                    0.08,
                    format!("generated random regular graph with n={n}, d={d}, seed={seed}"),
                );
                return Ok(self.finish_graph_report(graph, warnings));
            }
        }

        Err(GenerationError::FailClosed {
            operation: "random_regular_graph",
            reason: format!("failed to generate a valid regular graph after {max_tries} attempts"),
        })
    }

    /// Generate a Holme-Kim powerlaw cluster graph.
    ///
    /// Like Barabási-Albert with an additional triangle-closing step:
    /// after each preferential attachment, with probability `p` close a
    /// triangle by connecting to a random neighbor of the target.
    pub fn powerlaw_cluster_graph(
        &mut self,
        n: usize,
        m: usize,
        p: f64,
        seed: u64,
    ) -> Result<GenerationReport, GenerationError> {
        let (n, mut warnings) = self.validate_n("powerlaw_cluster_graph", n, MAX_N_GNP)?;
        let (p, p_warning) = self.validate_probability("powerlaw_cluster_graph", p)?;
        if let Some(warning) = p_warning {
            warnings.push(warning);
        }

        if m < 1 || m > n {
            return Err(GenerationError::FailClosed {
                operation: "powerlaw_cluster_graph",
                reason: format!("requires 1 <= m <= n, got m={m}, n={n}"),
            });
        }

        let (mut graph, node_labels) = graph_with_n_nodes(self.mode, n);
        let mut rng = PythonRandom::new(seed);

        let mut repeated_nodes: Vec<usize> = (0..m).collect();

        for source in m..n {
            let mut possible_targets = random_subset_python(&repeated_nodes, m, &mut rng);
            let Some(mut target) = possible_targets.pop_first() else {
                continue;
            };
            let _ = graph.add_edge(node_labels[source].clone(), node_labels[target].clone());
            repeated_nodes.push(target);

            let mut count = 1;
            while count < m {
                if rng.random() < p {
                    let neighborhood = graph.neighbors(&node_labels[target]).unwrap_or_default();
                    let candidates: Vec<usize> = neighborhood
                        .into_iter()
                        .filter_map(|neighbor| neighbor.parse::<usize>().ok())
                        .filter(|&neighbor| {
                            neighbor != source
                                && !graph.has_edge(&node_labels[source], &node_labels[neighbor])
                        })
                        .collect();
                    if !candidates.is_empty() {
                        let nbr = candidates[rng.choice_index(candidates.len())];
                        let _ =
                            graph.add_edge(node_labels[source].clone(), node_labels[nbr].clone());
                        repeated_nodes.push(nbr);
                        count += 1;
                        continue;
                    }
                }

                let Some(next_target) = possible_targets.pop_first() else {
                    break;
                };
                target = next_target;
                let _ = graph.add_edge(node_labels[source].clone(), node_labels[target].clone());
                repeated_nodes.push(target);
                count += 1;
            }

            repeated_nodes.extend(std::iter::repeat_n(source, m));
        }

        self.record(
            "powerlaw_cluster_graph",
            DecisionAction::Allow,
            0.08,
            format!("generated powerlaw cluster graph with n={n}, m={m}, p={p}, seed={seed}"),
        );
        Ok(self.finish_graph_report(graph, warnings))
    }

    /// Fast G(n,p) random graph using Batagelj-Brandes algorithm.
    ///
    /// O(n + m) expected time instead of O(n²) for the naive approach.
    /// Generates the same graph topology as `gnp_random_graph` but skips
    /// over non-edges using geometric distribution sampling.
    pub fn fast_gnp_random_graph(
        &mut self,
        n: usize,
        p: f64,
        seed: u64,
        directed: bool,
    ) -> Result<GenerationReport, GenerationError> {
        if directed {
            return Err(GenerationError::FailClosed {
                operation: "fast_gnp_random_graph",
                reason: "directed graphs are produced by fast_gnp_random_digraph".to_owned(),
            });
        }

        let (n, mut warnings) = self.validate_n("fast_gnp_random_graph", n, MAX_N_GNP)?;
        let (p, p_warning) = self.validate_probability("fast_gnp_random_graph", p)?;
        if let Some(warning) = p_warning {
            warnings.push(warning);
        }

        let (mut graph, node_labels) = graph_with_n_nodes(self.mode, n);
        if n < 2 || p <= 0.0 {
            self.record(
                "fast_gnp_random_graph",
                DecisionAction::Allow,
                0.05,
                format!("fast_gnp empty: n={n}, p={p}"),
            );
            return Ok(self.finish_graph_report(graph, warnings));
        }
        if p >= 1.0 {
            // Complete graph
            for i in 0..n {
                for j in (i + 1)..n {
                    graph
                        .add_edge(node_labels[i].clone(), node_labels[j].clone())
                        .map_err(|err| GenerationError::FailClosed {
                            operation: "fast_gnp_random_graph",
                            reason: err.to_string(),
                        })?;
                }
            }
            self.record(
                "fast_gnp_random_graph",
                DecisionAction::Allow,
                0.05,
                format!("fast_gnp complete: n={n}, p={p}"),
            );
            return Ok(self.finish_graph_report(graph, warnings));
        }

        let mut rng = PythonRandom::new(seed);
        let lp = (1.0 - p).ln();

        // Nodes in graph are from 0,n-1 (start with v as the second node index).
        let mut v: isize = 1;
        let mut w: isize = -1;
        while v < n as isize {
            let lr: f64 = (1.0 - rng.random()).ln();
            w += 1 + (lr / lp) as isize;
            while w >= v && v < n as isize {
                w -= v;
                v += 1;
            }
            if v < n as isize {
                graph
                    .add_edge(
                        node_labels[v as usize].clone(),
                        node_labels[w as usize].clone(),
                    )
                    .map_err(|err| GenerationError::FailClosed {
                        operation: "fast_gnp_random_graph",
                        reason: err.to_string(),
                    })?;
            }
        }

        self.record(
            "fast_gnp_random_graph",
            DecisionAction::Allow,
            0.08,
            format!("generated fast_gnp graph: n={n}, p={p}, directed={directed}, seed={seed}"),
        );
        Ok(self.finish_graph_report(graph, warnings))
    }

    pub fn fast_gnp_random_digraph(
        &mut self,
        n: usize,
        p: f64,
        seed: u64,
    ) -> Result<DiGenerationReport, GenerationError> {
        let (n, mut warnings) = self.validate_n("fast_gnp_random_digraph", n, MAX_N_GNP)?;
        let (p, p_warning) = self.validate_probability("fast_gnp_random_digraph", p)?;
        if let Some(warning) = p_warning {
            warnings.push(warning);
        }

        let (mut graph, node_labels) = digraph_with_n_nodes(self.mode, n);
        if n < 2 || p <= 0.0 {
            self.record(
                "fast_gnp_random_digraph",
                DecisionAction::Allow,
                0.05,
                format!("fast_gnp digraph empty: n={n}, p={p}"),
            );
            return Ok(self.finish_digraph_report(graph, warnings));
        }
        if p >= 1.0 {
            for i in 0..n {
                for j in 0..n {
                    if i != j {
                        graph
                            .add_edge(node_labels[i].clone(), node_labels[j].clone())
                            .map_err(|err| GenerationError::FailClosed {
                                operation: "fast_gnp_random_digraph",
                                reason: err.to_string(),
                            })?;
                    }
                }
            }
            self.record(
                "fast_gnp_random_digraph",
                DecisionAction::Allow,
                0.05,
                format!("fast_gnp digraph complete: n={n}, p={p}"),
            );
            return Ok(self.finish_digraph_report(graph, warnings));
        }

        let mut rng = PythonRandom::new(seed);
        let lp = (1.0 - p).ln();

        // First loop: edges (w, v) where w < v
        let mut v: isize = 1;
        let mut w: isize = -1;
        while v < n as isize {
            let lr: f64 = (1.0 - rng.random()).ln();
            w += 1 + (lr / lp) as isize;
            while w >= v && v < n as isize {
                w -= v;
                v += 1;
            }
            if v < n as isize {
                graph
                    .add_edge(
                        node_labels[w as usize].clone(),
                        node_labels[v as usize].clone(),
                    )
                    .map_err(|err| GenerationError::FailClosed {
                        operation: "fast_gnp_random_digraph",
                        reason: err.to_string(),
                    })?;
            }
        }

        // Second loop: edges (v, w) where v > w
        let mut v2: isize = 1;
        let mut w2: isize = -1;
        while v2 < n as isize {
            let lr: f64 = (1.0 - rng.random()).ln();
            w2 += 1 + (lr / lp) as isize;
            while w2 >= v2 && v2 < n as isize {
                w2 -= v2;
                v2 += 1;
            }
            if v2 < n as isize {
                graph
                    .add_edge(
                        node_labels[v2 as usize].clone(),
                        node_labels[w2 as usize].clone(),
                    )
                    .map_err(|err| GenerationError::FailClosed {
                        operation: "fast_gnp_random_digraph",
                        reason: err.to_string(),
                    })?;
            }
        }

        self.record(
            "fast_gnp_random_digraph",
            DecisionAction::Allow,
            0.08,
            format!("generated fast_gnp digraph: n={n}, p={p}, seed={seed}"),
        );
        Ok(self.finish_digraph_report(graph, warnings))
    }

    /// Generate a growing network digraph (GN model).
    ///
    /// Nodes are added one at a time. Each new node connects to an existing
    /// node chosen with probability proportional to its current degree.
    pub fn gn_graph(&mut self, n: usize, seed: u64) -> Result<DiGenerationReport, GenerationError> {
        let (n, warnings) = self.validate_n("gn_graph", n, MAX_N_GENERIC)?;
        let mut graph = DiGraph::new(self.mode);
        if n == 0 {
            self.record(
                "gn_graph",
                DecisionAction::Allow,
                0.05,
                "gn_graph n=0".to_owned(),
            );
            return Ok(self.finish_digraph_report(graph, warnings));
        }
        let _ = graph.add_node("0".to_owned());
        if n == 1 {
            self.record(
                "gn_graph",
                DecisionAction::Allow,
                0.05,
                "gn_graph n=1".to_owned(),
            );
            return Ok(self.finish_digraph_report(graph, warnings));
        }

        let mut rng = PythonRandom::new(seed);
        graph
            .add_edge("1".to_owned(), "0".to_owned())
            .map_err(|err| GenerationError::FailClosed {
                operation: "gn_graph",
                reason: err.to_string(),
            })?;
        let mut degree_sequence = vec![1.0_f64, 1.0_f64];

        for i in 2..n {
            let target = weighted_choice_python(&degree_sequence, &mut rng);
            graph
                .add_edge(i.to_string(), target.to_string())
                .map_err(|err| GenerationError::FailClosed {
                    operation: "gn_graph",
                    reason: err.to_string(),
                })?;
            degree_sequence.push(1.0);
            degree_sequence[target] += 1.0;
        }

        self.record(
            "gn_graph",
            DecisionAction::Allow,
            0.08,
            format!("generated gn_graph: n={n}, seed={seed}"),
        );
        Ok(self.finish_digraph_report(graph, warnings))
    }

    /// Generate a growing network with redirection digraph (GNR model).
    ///
    /// Each new node tries to connect to a random existing node; with
    /// probability `p`, it redirects to that node's successor instead.
    pub fn gnr_graph(
        &mut self,
        n: usize,
        p: f64,
        seed: u64,
    ) -> Result<DiGenerationReport, GenerationError> {
        let (n, warnings) = self.validate_n("gnr_graph", n, MAX_N_GENERIC)?;
        let mut graph = DiGraph::new(self.mode);
        if n == 0 {
            self.record(
                "gnr_graph",
                DecisionAction::Allow,
                0.05,
                "gnr_graph n=0".to_owned(),
            );
            return Ok(self.finish_digraph_report(graph, warnings));
        }
        let _ = graph.add_node("0".to_owned());
        let mut rng = PythonRandom::new(seed);
        for i in 1..n {
            let src = i.to_string();
            let _ = graph.add_node(src.clone());
            let mut target = rng.randrange(i);
            let draw = rng.random();
            if draw < p && target != 0 {
                // Redirect to the target's successor, matching NetworkX.
                let target_name = target.to_string();
                if let Some(successors) = graph.successors(&target_name)
                    && let Some(succ) = successors.first()
                    && let Ok(pred_idx) = succ.parse::<usize>()
                {
                    target = pred_idx;
                }
            }
            graph
                .add_edge(src, target.to_string())
                .map_err(|err| GenerationError::FailClosed {
                    operation: "gnr_graph",
                    reason: err.to_string(),
                })?;
        }

        self.record(
            "gnr_graph",
            DecisionAction::Allow,
            0.08,
            format!("generated gnr_graph: n={n}, p={p}, seed={seed}"),
        );
        Ok(self.finish_digraph_report(graph, warnings))
    }

    /// Generate a growing network with copying digraph (GNC model).
    ///
    /// Each new node connects to a random existing node and to all of
    /// that node's successors.
    pub fn gnc_graph(
        &mut self,
        n: usize,
        seed: u64,
    ) -> Result<DiGenerationReport, GenerationError> {
        let (n, warnings) = self.validate_n("gnc_graph", n, MAX_N_GENERIC)?;
        let mut graph = DiGraph::new(self.mode);
        if n == 0 {
            self.record(
                "gnc_graph",
                DecisionAction::Allow,
                0.05,
                "gnc_graph n=0".to_owned(),
            );
            return Ok(self.finish_digraph_report(graph, warnings));
        }
        let _ = graph.add_node("0".to_owned());
        let mut rng = PythonRandom::new(seed);
        for i in 1..n {
            let src = i.to_string();
            let _ = graph.add_node(src.clone());
            let target = rng.randrange(i);
            let target_name = target.to_string();
            let successors = graph
                .successors(&target_name)
                .unwrap_or_default()
                .into_iter()
                .map(str::to_owned)
                .collect::<Vec<String>>();
            for succ in successors {
                graph
                    .add_edge(src.clone(), succ)
                    .map_err(|err| GenerationError::FailClosed {
                        operation: "gnc_graph",
                        reason: err.to_string(),
                    })?;
            }
            graph
                .add_edge(src, target_name)
                .map_err(|err| GenerationError::FailClosed {
                    operation: "gnc_graph",
                    reason: err.to_string(),
                })?;
        }

        self.record(
            "gnc_graph",
            DecisionAction::Allow,
            0.08,
            format!("generated gnc_graph: n={n}, seed={seed}"),
        );
        Ok(self.finish_digraph_report(graph, warnings))
    }

    /// Generate a scale-free directed graph using Bollobás's model.
    ///
    /// At each step, add a new node→existing (prob α), existing→new (prob β),
    /// or existing→existing (prob γ). Target selection uses preferential
    /// attachment via in-degree. α + β + γ must equal 1.
    #[allow(clippy::too_many_arguments)]
    pub fn scale_free_graph(
        &mut self,
        n: usize,
        alpha: f64,
        beta: f64,
        gamma: f64,
        delta_in: f64,
        delta_out: f64,
        initial_graph: Option<MultiDiGraph>,
        seed: u64,
    ) -> Result<MultiDiGenerationReport, GenerationError> {
        let (n, warnings) = self.validate_n("scale_free_graph", n, MAX_N_GNP)?;
        if alpha <= 0.0 {
            return Err(GenerationError::FailClosed {
                operation: "scale_free_graph",
                reason: "alpha must be > 0".to_owned(),
            });
        }
        if beta <= 0.0 {
            return Err(GenerationError::FailClosed {
                operation: "scale_free_graph",
                reason: "beta must be > 0".to_owned(),
            });
        }
        if gamma <= 0.0 {
            return Err(GenerationError::FailClosed {
                operation: "scale_free_graph",
                reason: "gamma must be > 0".to_owned(),
            });
        }
        if delta_in < 0.0 {
            return Err(GenerationError::FailClosed {
                operation: "scale_free_graph",
                reason: "delta_in must be >= 0".to_owned(),
            });
        }
        if delta_out < 0.0 {
            return Err(GenerationError::FailClosed {
                operation: "scale_free_graph",
                reason: "delta_out must be >= 0".to_owned(),
            });
        }

        let sum = alpha + beta + gamma;
        if (sum - 1.0).abs() > PARAM_SUM_EPSILON {
            return Err(GenerationError::FailClosed {
                operation: "scale_free_graph",
                reason: format!("alpha + beta + gamma must = 1.0, got {sum}"),
            });
        }

        let mut graph =
            initial_graph.unwrap_or_else(|| default_scale_free_initial_graph(self.mode));
        let mut rng = PythonRandom::new(seed);
        let mut out_state = degree_state_from_graph(&graph, true);
        let mut in_state = degree_state_from_graph(&graph, false);
        let mut node_list = graph
            .nodes_ordered()
            .into_iter()
            .filter_map(|node| node.parse::<usize>().ok())
            .collect::<Vec<usize>>();
        let mut cursor = node_list
            .iter()
            .max()
            .map_or(0, |node| node.saturating_add(1));

        while graph.node_count() < n.max(3) {
            let r = rng.random();
            let (source, target) = if r < alpha {
                let source = cursor;
                cursor = cursor.saturating_add(1);
                node_list.push(source);
                let target = choose_scale_free_node(&in_state, &node_list, delta_in, &mut rng);
                (source, target)
            } else if r < alpha + beta {
                let source = choose_scale_free_node(&out_state, &node_list, delta_out, &mut rng);
                let target = choose_scale_free_node(&in_state, &node_list, delta_in, &mut rng);
                (source, target)
            } else {
                let source = choose_scale_free_node(&out_state, &node_list, delta_out, &mut rng);
                let target = cursor;
                cursor = cursor.saturating_add(1);
                node_list.push(target);
                (source, target)
            };

            graph
                .add_edge_with_attrs(
                    source.to_string(),
                    target.to_string(),
                    fnx_classes::AttrMap::new(),
                )
                .map_err(|err| GenerationError::FailClosed {
                    operation: "scale_free_graph",
                    reason: err.to_string(),
                })?;
            out_state.push(source);
            in_state.push(target);
        }

        self.record(
            "scale_free_graph",
            DecisionAction::Allow,
            0.08,
            format!(
                "generated scale_free_graph: n={n}, α={alpha}, β={beta}, γ={gamma}, δ_in={delta_in}, δ_out={delta_out}, seed={seed}"
            ),
        );
        Ok(self.finish_multidigraph_report(graph, warnings))
    }

    fn record(
        &mut self,
        operation: &'static str,
        action: DecisionAction,
        incompatibility_probability: f64,
        rationale: String,
    ) {
        self.runtime_policy.record(
            operation,
            action,
            incompatibility_probability,
            &rationale,
            vec![EvidenceTerm {
                signal: "generator_rationale".to_owned(),
                observed_value: rationale.clone(),
                log_likelihood_ratio: if action == DecisionAction::Allow {
                    -1.0
                } else {
                    2.0
                },
            }],
        );
    }
}

#[derive(Debug)]
struct PythonRandom {
    inner: MT19937,
}

impl PythonRandom {
    fn new(seed: u64) -> Self {
        let words = if seed <= u64::from(u32::MAX) {
            vec![seed as u32]
        } else {
            let low = seed as u32;
            let high = (seed >> 32) as u32;
            vec![low, high]
        };
        Self {
            inner: MT19937::new_with_slice_seed(&words),
        }
    }

    fn random(&mut self) -> f64 {
        gen_res53(&mut self.inner)
    }

    fn randrange(&mut self, stop: usize) -> usize {
        self.randbelow(stop)
    }

    fn choice_index(&mut self, len: usize) -> usize {
        self.randbelow(len)
    }

    fn randbelow(&mut self, upper: usize) -> usize {
        debug_assert!(upper > 0);
        let bit_count = usize::BITS - upper.leading_zeros();
        loop {
            let candidate = self.getrandbits(bit_count);
            if candidate < upper {
                return candidate;
            }
        }
    }

    fn getrandbits(&mut self, bit_count: u32) -> usize {
        if bit_count == 0 {
            return 0;
        }

        let mut remaining = bit_count;
        let mut result: usize = 0;
        while remaining >= 32 {
            result = (result << 32) | self.inner.next_u32() as usize;
            remaining -= 32;
        }
        if remaining > 0 {
            let word = self.inner.next_u32() >> (32 - remaining);
            result = (result << remaining) | word as usize;
        }
        result
    }
}

/// br-r37-c1-nzo8r: port of nx.generators.random_graphs._random_subset's
/// inner `_try_creation` loop. Tracks unmatched stubs in `potential_edges`
/// after each shuffle pass and only fully restarts when `_suitable` proves
/// no remaining edge can be placed, instead of throwing away the entire
/// attempt on the first duplicate or self-loop.
fn try_create_random_regular(
    rng: &mut PythonRandom,
    n: usize,
    d: usize,
) -> Option<Vec<(usize, usize)>> {
    use std::collections::{BTreeMap, HashSet};

    let mut edges: HashSet<(usize, usize)> = HashSet::new();
    let mut stubs: Vec<usize> = Vec::with_capacity(n * d);
    for i in 0..n {
        for _ in 0..d {
            stubs.push(i);
        }
    }

    while !stubs.is_empty() {
        for i in (1..stubs.len()).rev() {
            let j = rng.randrange(i + 1);
            stubs.swap(i, j);
        }

        // BTreeMap keeps deterministic iteration order across runs.
        let mut potential_edges: BTreeMap<usize, usize> = BTreeMap::new();
        for pair in stubs.chunks_exact(2) {
            let (mut s1, mut s2) = (pair[0], pair[1]);
            if s1 > s2 {
                std::mem::swap(&mut s1, &mut s2);
            }
            if s1 != s2 && !edges.contains(&(s1, s2)) {
                edges.insert((s1, s2));
            } else {
                *potential_edges.entry(s1).or_insert(0) += 1;
                *potential_edges.entry(s2).or_insert(0) += 1;
            }
        }

        if !rrg_suitable(&edges, &potential_edges) {
            return None;
        }

        stubs.clear();
        for (&node, &potential) in &potential_edges {
            for _ in 0..potential {
                stubs.push(node);
            }
        }
    }

    Some(edges.into_iter().collect())
}

/// Checks whether the remaining unmatched stubs in `potential_edges` could
/// possibly form at least one valid edge given the edges already placed.
/// Returns false (= must restart) if every cross-pair is already an edge.
/// Mirrors nx's `_suitable` predicate in random_regular_graph.
fn rrg_suitable(
    edges: &std::collections::HashSet<(usize, usize)>,
    potential_edges: &std::collections::BTreeMap<usize, usize>,
) -> bool {
    if potential_edges.is_empty() {
        return true;
    }
    let nodes: Vec<usize> = potential_edges.keys().copied().collect();
    for i in 1..nodes.len() {
        let s1 = nodes[i];
        for &s2 in &nodes[..i] {
            let (lo, hi) = if s1 < s2 { (s1, s2) } else { (s2, s1) };
            if !edges.contains(&(lo, hi)) {
                return true;
            }
        }
    }
    false
}

fn ring_lattice_edges(n: usize, half_k: usize) -> Vec<(usize, usize)> {
    let mut edges = Vec::with_capacity(n * half_k);
    for offset in 1..=half_k {
        for source in 0..n {
            edges.push((source, (source + offset) % n));
        }
    }
    edges
}

fn watts_strogatz_graph_core(
    mode: CompatibilityMode,
    n: usize,
    half_k: usize,
    p: f64,
    rng: &mut PythonRandom,
) -> Graph {
    let (mut graph, node_labels) = graph_with_n_nodes(mode, n);
    let ring_edges = ring_lattice_edges(n, half_k);
    for &(u, v) in &ring_edges {
        let _ = graph.add_edge(node_labels[u].clone(), node_labels[v].clone());
    }

    for &(u, v) in &ring_edges {
        if rng.random() < p {
            let mut new_target = rng.randrange(n);
            let mut skip_rewire = false;
            while new_target == u || graph.has_edge(&node_labels[u], &node_labels[new_target]) {
                new_target = rng.randrange(n);
                if graph.degree(&node_labels[u]) >= n - 1 {
                    skip_rewire = true;
                    break;
                }
            }
            if !skip_rewire {
                let _ = graph.remove_edge(&node_labels[u], &node_labels[v]);
                let _ = graph.add_edge(node_labels[u].clone(), node_labels[new_target].clone());
            }
        }
    }

    graph
}

fn graph_is_connected(graph: &Graph) -> bool {
    let nodes = graph.nodes_ordered();
    if nodes.len() <= 1 {
        return true;
    }

    let mut visited = std::collections::HashSet::new();
    let mut queue = std::collections::VecDeque::new();
    visited.insert(nodes[0]);
    queue.push_back(nodes[0]);
    while let Some(current) = queue.pop_front() {
        if let Some(neighbors) = graph.neighbors(current) {
            for neighbor in neighbors {
                if visited.insert(neighbor) {
                    queue.push_back(neighbor);
                }
            }
        }
    }
    visited.len() == nodes.len()
}

/// Sample `count` distinct elements from `seq` with replacement-by-set,
/// matching the inner loop of nx's `_random_subset`.
///
/// Caller must ensure `seq` contains at least `count` *distinct* values —
/// otherwise the loop cannot terminate. We guard against that here by
/// bailing out if `seq` is empty (no candidates) or if its distinct-value
/// count is below `count` (impossible to fill the set), returning a
/// truncated result rather than spinning forever.
fn random_subset_python(
    seq: &[usize],
    count: usize,
    rng: &mut PythonRandom,
) -> std::collections::BTreeSet<usize> {
    let mut targets = std::collections::BTreeSet::new();
    if seq.is_empty() || count == 0 {
        return targets;
    }
    let unique_cap = {
        let mut tmp: std::collections::BTreeSet<usize> = std::collections::BTreeSet::new();
        for &v in seq {
            tmp.insert(v);
        }
        tmp.len()
    };
    let target_count = count.min(unique_cap);
    while targets.len() < target_count {
        let choice = seq[rng.choice_index(seq.len())];
        targets.insert(choice);
    }
    targets
}

fn weighted_choice_python(weights: &[f64], rng: &mut PythonRandom) -> usize {
    if weights.is_empty() {
        // Degenerate input — no candidate to pick. Return 0 by convention so
        // upstream call sites that index into a sibling vector see an
        // out-of-bounds error rather than the silent infinite loop that
        // ``rng.choice_index(0)`` would produce.
        return 0;
    }
    let total: f64 = weights.iter().sum();
    if total <= 0.0 {
        return rng.choice_index(weights.len());
    }

    let mut cdf = Vec::with_capacity(weights.len() + 1);
    cdf.push(0.0);
    let mut cumulative = 0.0;
    for &weight in weights {
        cumulative += weight;
        cdf.push(cumulative / total);
    }

    let sample = rng.random();
    let insertion = cdf.partition_point(|value| *value < sample);
    if insertion == 0 {
        weights.len() - 1
    } else {
        insertion - 1
    }
}

fn choose_scale_free_node(
    candidates: &[usize],
    node_list: &[usize],
    delta: f64,
    rng: &mut PythonRandom,
) -> usize {
    if delta > 0.0 {
        let bias_sum = node_list.len() as f64 * delta;
        let p_delta = bias_sum / (bias_sum + candidates.len() as f64);
        if rng.random() < p_delta {
            return node_list[rng.choice_index(node_list.len())];
        }
    }
    if candidates.is_empty() {
        return node_list[rng.choice_index(node_list.len())];
    }
    candidates[rng.choice_index(candidates.len())]
}

fn default_scale_free_initial_graph(mode: CompatibilityMode) -> MultiDiGraph {
    let mut graph = MultiDiGraph::new(mode);
    let _ = graph.add_edge_with_attrs("0".to_owned(), "1".to_owned(), fnx_classes::AttrMap::new());
    let _ = graph.add_edge_with_attrs("1".to_owned(), "2".to_owned(), fnx_classes::AttrMap::new());
    let _ = graph.add_edge_with_attrs("2".to_owned(), "0".to_owned(), fnx_classes::AttrMap::new());
    graph
}

fn degree_state_from_graph(graph: &MultiDiGraph, out_degree: bool) -> Vec<usize> {
    let mut state = Vec::new();
    for node in graph.nodes_ordered() {
        if let Ok(index) = node.parse::<usize>() {
            let degree = if out_degree {
                graph.out_degree(node)
            } else {
                graph.in_degree(node)
            };
            state.extend(std::iter::repeat_n(index, degree));
        }
    }
    state
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

fn digraph_with_n_nodes(mode: CompatibilityMode, n: usize) -> (DiGraph, Vec<String>) {
    let mut graph = DiGraph::new(mode);
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
    use fnx_classes::digraph::MultiDiGraph;
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
    fn watts_strogatz_basic_structure() {
        let mut gg = GraphGenerator::strict();
        let report = gg
            .watts_strogatz_graph(20, 4, 0.0, 42)
            .expect("watts-strogatz should succeed");
        // With p=0 no rewiring happens — we get a ring lattice.
        // Each of 20 nodes connects to 2 neighbors on each side → 20*2 = 40 half-edges → 40 edges.
        assert_eq!(report.graph.node_count(), 20);
        assert_eq!(report.graph.edge_count(), 40);
    }

    #[test]
    fn watts_strogatz_with_rewiring_is_seed_reproducible() {
        let mut gg_a = GraphGenerator::strict();
        let mut gg_b = GraphGenerator::strict();
        let a = gg_a
            .watts_strogatz_graph(30, 4, 0.3, 123)
            .expect("ws should succeed")
            .graph
            .snapshot();
        let b = gg_b
            .watts_strogatz_graph(30, 4, 0.3, 123)
            .expect("ws should succeed")
            .graph
            .snapshot();
        assert_eq!(a, b, "watts-strogatz must be seed-reproducible");
    }

    #[test]
    fn watts_strogatz_accepts_odd_k_as_k_minus_one_neighbors() {
        let mut gg = GraphGenerator::strict();
        let report = gg
            .watts_strogatz_graph(7, 3, 0.0, 1)
            .expect("odd k should succeed");
        assert_eq!(report.graph.node_count(), 7);
        assert_eq!(report.graph.edge_count(), 7);
    }

    #[test]
    fn watts_strogatz_k_equal_n_returns_complete_graph() {
        let mut gg = GraphGenerator::strict();
        let report = gg
            .watts_strogatz_graph(6, 6, 0.3, 1)
            .expect("k == n should succeed");
        assert_eq!(report.graph.node_count(), 6);
        assert_eq!(report.graph.edge_count(), 15);
    }

    #[test]
    fn watts_strogatz_rejects_k_gt_n() {
        let mut gg = GraphGenerator::strict();
        let err = gg
            .watts_strogatz_graph(4, 6, 0.1, 1)
            .expect_err("k > n should fail");
        assert!(matches!(err, GenerationError::FailClosed { .. }));
    }

    #[test]
    fn newman_watts_strogatz_accepts_odd_k_as_k_minus_one_neighbors() {
        let mut gg = GraphGenerator::strict();
        let report = gg
            .newman_watts_strogatz_graph(7, 3, 0.0, 1)
            .expect("odd k should succeed");
        assert_eq!(report.graph.node_count(), 7);
        assert_eq!(report.graph.edge_count(), 7);
    }

    #[test]
    fn connected_watts_strogatz_zero_tries_fails_immediately() {
        let mut gg = GraphGenerator::strict();
        let err = gg
            .connected_watts_strogatz_graph(10, 4, 0.5, 0, 1)
            .expect_err("zero tries should fail");
        assert!(matches!(err, GenerationError::FailClosed { .. }));
    }

    #[test]
    fn barabasi_albert_basic_structure() {
        let mut gg = GraphGenerator::strict();
        let report = gg
            .barabasi_albert_graph(20, 2, 42)
            .expect("barabasi-albert should succeed");
        assert_eq!(report.graph.node_count(), 20);
        // Initial star graph on m+1 = 3 nodes has 2 edges.
        // Then 17 nodes are added, each with 2 edges → 2 + 17*2 = 36 edges.
        assert_eq!(report.graph.edge_count(), 36);
    }

    #[test]
    fn barabasi_albert_is_seed_reproducible() {
        let mut gg_a = GraphGenerator::strict();
        let mut gg_b = GraphGenerator::strict();
        let a = gg_a
            .barabasi_albert_graph(50, 3, 99)
            .expect("ba should succeed")
            .graph
            .snapshot();
        let b = gg_b
            .barabasi_albert_graph(50, 3, 99)
            .expect("ba should succeed")
            .graph
            .snapshot();
        assert_eq!(a, b, "barabasi-albert must be seed-reproducible");
    }

    #[test]
    fn barabasi_albert_rejects_m_zero() {
        let mut gg = GraphGenerator::strict();
        let err = gg
            .barabasi_albert_graph(10, 0, 1)
            .expect_err("m=0 should fail");
        assert!(matches!(err, GenerationError::FailClosed { .. }));
    }

    #[test]
    fn barabasi_albert_rejects_m_ge_n() {
        let mut gg = GraphGenerator::strict();
        // m=n should fail
        let err = gg
            .barabasi_albert_graph(5, 5, 1)
            .expect_err("m=n should fail");
        assert!(matches!(err, GenerationError::FailClosed { .. }));

        // m > n should fail
        let err = gg
            .barabasi_albert_graph(3, 5, 1)
            .expect_err("m > n should fail");
        assert!(matches!(err, GenerationError::FailClosed { .. }));
    }

    #[test]
    fn barabasi_albert_m_one_does_not_panic() {
        let mut gg = GraphGenerator::strict();
        let report = gg
            .barabasi_albert_graph(10, 1, 42)
            .expect("ba with m=1 should succeed");
        assert_eq!(report.graph.node_count(), 10);
        // Initial star(1) has 1 edge; 8 new nodes each attach 1 edge → 1 + 8 = 9 edges.
        assert_eq!(report.graph.edge_count(), 9);
    }

    #[test]
    fn directed_growth_generators_are_directed_and_seed_reproducible() {
        let mut gg = GraphGenerator::strict();

        let gn = gg.gn_graph(6, 1).expect("gn_graph should succeed");
        assert!(gn.graph.is_directed());
        assert_eq!(gn.graph.node_count(), 6);
        assert_eq!(gn.graph.edge_count(), 5);
        let gn_again = gg.gn_graph(6, 1).expect("gn_graph replay should succeed");
        assert_eq!(gn.graph.snapshot(), gn_again.graph.snapshot());

        let gnr = gg.gnr_graph(6, 0.5, 1).expect("gnr_graph should succeed");
        assert!(gnr.graph.is_directed());
        assert_eq!(gnr.graph.node_count(), 6);
        assert_eq!(gnr.graph.edge_count(), 5);
        let gnr_again = gg
            .gnr_graph(6, 0.5, 1)
            .expect("gnr_graph replay should succeed");
        assert_eq!(gnr.graph.snapshot(), gnr_again.graph.snapshot());

        let gnc = gg.gnc_graph(6, 1).expect("gnc_graph should succeed");
        assert!(gnc.graph.is_directed());
        assert_eq!(gnc.graph.node_count(), 6);
        assert!(gnc.graph.edge_count() >= 5);
        let gnc_again = gg.gnc_graph(6, 1).expect("gnc_graph replay should succeed");
        assert_eq!(gnc.graph.snapshot(), gnc_again.graph.snapshot());
    }

    #[test]
    fn directed_growth_generators_match_networkx_seeded_examples() {
        let mut gg = GraphGenerator::strict();

        let gn = gg.gn_graph(6, 1).expect("gn_graph should succeed");
        let gn_edges = gn
            .graph
            .snapshot()
            .edges
            .into_iter()
            .map(|edge| (edge.left, edge.right))
            .collect::<Vec<(String, String)>>();
        assert_eq!(
            gn_edges,
            vec![
                ("1".to_owned(), "0".to_owned()),
                ("2".to_owned(), "0".to_owned()),
                ("3".to_owned(), "2".to_owned()),
                ("4".to_owned(), "2".to_owned()),
                ("5".to_owned(), "1".to_owned()),
            ]
        );

        let gnr = gg.gnr_graph(6, 0.5, 1).expect("gnr_graph should succeed");
        let gnr_edges = gnr
            .graph
            .snapshot()
            .edges
            .into_iter()
            .map(|edge| (edge.left, edge.right))
            .collect::<Vec<(String, String)>>();
        assert_eq!(
            gnr_edges,
            vec![
                ("1".to_owned(), "0".to_owned()),
                ("2".to_owned(), "0".to_owned()),
                ("3".to_owned(), "1".to_owned()),
                ("4".to_owned(), "3".to_owned()),
                ("5".to_owned(), "0".to_owned()),
            ]
        );

        let gnc = gg.gnc_graph(6, 1).expect("gnc_graph should succeed");
        let gnc_edges = gnc
            .graph
            .snapshot()
            .edges
            .into_iter()
            .map(|edge| (edge.left, edge.right))
            .collect::<Vec<(String, String)>>();
        assert_eq!(
            gnc_edges,
            vec![
                ("1".to_owned(), "0".to_owned()),
                ("2".to_owned(), "0".to_owned()),
                ("3".to_owned(), "0".to_owned()),
                ("3".to_owned(), "1".to_owned()),
                ("4".to_owned(), "0".to_owned()),
                ("5".to_owned(), "0".to_owned()),
                ("5".to_owned(), "1".to_owned()),
                ("5".to_owned(), "3".to_owned()),
            ]
        );
    }

    #[test]
    fn scale_free_graph_is_directed_multigraph_and_seed_reproducible() {
        let mut gg = GraphGenerator::strict();
        let report = gg
            .scale_free_graph(6, 0.41, 0.54, 0.05, 0.2, 0.0, None, 1)
            .expect("scale_free_graph should succeed");
        assert!(report.graph.is_directed());
        assert!(report.graph.is_multigraph());

        let snapshot = report.graph.snapshot();
        assert_eq!(snapshot.nodes, vec!["0", "1", "2", "3", "4", "5"]);
        let edge_set = snapshot
            .edges
            .iter()
            .map(|edge| (edge.source.clone(), edge.target.clone(), edge.key))
            .collect::<std::collections::HashSet<(String, String, usize)>>();
        assert!(edge_set.contains(&("0".to_owned(), "1".to_owned(), 0)));
        assert!(edge_set.contains(&("1".to_owned(), "2".to_owned(), 0)));
        assert!(edge_set.contains(&("2".to_owned(), "0".to_owned(), 0)));

        let report_again = gg
            .scale_free_graph(6, 0.41, 0.54, 0.05, 0.2, 0.0, None, 1)
            .expect("scale_free_graph replay should succeed");
        assert_eq!(snapshot, report_again.graph.snapshot());
    }

    #[test]
    fn scale_free_graph_matches_networkx_seeded_example() {
        let mut gg = GraphGenerator::strict();
        let report = gg
            .scale_free_graph(6, 0.41, 0.54, 0.05, 0.2, 0.0, None, 1)
            .expect("scale_free_graph should succeed");
        let edges = report
            .graph
            .snapshot()
            .edges
            .into_iter()
            .map(|edge| (edge.source, edge.target, edge.key))
            .collect::<Vec<(String, String, usize)>>();
        assert_eq!(
            edges,
            vec![
                ("0".to_owned(), "1".to_owned(), 0),
                ("1".to_owned(), "2".to_owned(), 0),
                ("1".to_owned(), "0".to_owned(), 0),
                ("2".to_owned(), "0".to_owned(), 0),
                ("2".to_owned(), "1".to_owned(), 0),
                ("3".to_owned(), "0".to_owned(), 0),
                ("3".to_owned(), "0".to_owned(), 1),
                ("3".to_owned(), "0".to_owned(), 2),
                ("4".to_owned(), "0".to_owned(), 0),
                ("5".to_owned(), "0".to_owned(), 0),
            ]
        );
    }

    #[test]
    fn fast_gnp_random_digraph_is_directed_and_seed_reproducible() {
        let mut gg = GraphGenerator::strict();
        let report = gg
            .fast_gnp_random_digraph(6, 0.4, 7)
            .expect("fast_gnp_random_digraph should succeed");
        assert!(report.graph.is_directed());
        assert_eq!(report.graph.node_count(), 6);

        let snapshot = report.graph.snapshot();
        let report_again = gg
            .fast_gnp_random_digraph(6, 0.4, 7)
            .expect("fast_gnp_random_digraph replay should succeed");
        assert_eq!(snapshot, report_again.graph.snapshot());
    }

    #[test]
    fn scale_free_graph_respects_initial_multidigraph() {
        let mut initial = MultiDiGraph::strict();
        initial
            .add_edge_with_attrs("7".to_owned(), "8".to_owned(), fnx_classes::AttrMap::new())
            .expect("initial edge should be valid");

        let mut gg = GraphGenerator::strict();
        let report = gg
            .scale_free_graph(4, 0.41, 0.54, 0.05, 0.2, 0.0, Some(initial), 1)
            .expect("scale_free_graph should accept initial graph");
        let edges = report
            .graph
            .snapshot()
            .edges
            .into_iter()
            .map(|edge| (edge.source, edge.target, edge.key))
            .collect::<Vec<(String, String, usize)>>();
        assert_eq!(
            edges,
            vec![
                ("7".to_owned(), "8".to_owned(), 0),
                ("9".to_owned(), "8".to_owned(), 0),
                ("10".to_owned(), "8".to_owned(), 0),
            ]
        );
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

    #[test]
    fn runtime_policy_tracks_generator_validation_state() {
        let mut generator = GraphGenerator::hardened();
        let report = generator
            .gnp_random_graph(8, f64::NAN, 7)
            .expect("hardened generator should recover from NaN probability");

        assert!(!report.warnings.is_empty());
        assert_eq!(
            generator.runtime_policy().mode(),
            CompatibilityMode::Hardened
        );
        assert!(
            !generator
                .runtime_policy()
                .decision_log()
                .records()
                .is_empty()
        );
        assert!(generator.runtime_policy().posterior().observation_count >= 1);
    }

    #[test]
    fn result_graph_inherits_generator_runtime_policy() {
        let mut generator = GraphGenerator::strict();
        let report = generator
            .path_graph(4)
            .expect("path graph generation should succeed");

        assert_eq!(report.graph.runtime_policy(), generator.runtime_policy());
        assert_eq!(report.graph.evidence_ledger(), generator.evidence_ledger());
    }

    #[test]
    fn result_digraph_inherits_generator_runtime_policy() {
        let mut generator = GraphGenerator::strict();
        let report = generator
            .gn_graph(6, 1)
            .expect("gn_graph generation should succeed");

        assert_eq!(report.graph.runtime_policy(), generator.runtime_policy());
        assert_eq!(report.graph.evidence_ledger(), generator.evidence_ledger());
    }

    #[test]
    fn result_multidigraph_inherits_generator_runtime_policy() {
        let mut generator = GraphGenerator::strict();
        let report = generator
            .scale_free_graph(6, 0.41, 0.54, 0.05, 0.2, 0.0, None, 1)
            .expect("scale_free_graph generation should succeed");

        assert_eq!(report.graph.runtime_policy(), generator.runtime_policy());
        assert_eq!(report.graph.evidence_ledger(), generator.evidence_ledger());
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
