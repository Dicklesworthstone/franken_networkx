//! # Canonical Graph Semantics Engine (CGSE)
//!
//! Deterministic tie-break policies with complexity witness artifacts per
//! algorithm family. This is FrankenNetworkX's crown-jewel innovation: every
//! algorithm declares its ordering policy at the type level, and every
//! execution emits a cryptographic witness that proves which tie-break
//! decisions were taken.
//!
//! ## Architecture
//!
//! - [`TieBreakPolicy`]: closed sum type with 12 named ordering variants.
//! - [`ComplexityWitness`]: per-execution record carrying `(n, m, observed_ops,
//!   policy_id, decision_path_blake3)`.
//! - [`WitnessSink`]: thread-local collector that algorithms call on every
//!   tie-break decision.
//! - [`WitnessLedger`]: append-only log of witnesses, serializable to JSONL
//!   with RaptorQ sidecar support.

#![forbid(unsafe_code)]

use serde::{Deserialize, Serialize};
use std::cell::{Cell, RefCell};

// ---------------------------------------------------------------------------
// Tie-Break Policies
// ---------------------------------------------------------------------------

/// The 12 canonical tie-break orderings that NetworkX algorithms exhibit.
///
/// Each algorithm family declares exactly one policy. When two candidates
/// are equally ranked by the algorithm's primary metric (cost, weight, degree,
/// etc.), the policy determines which candidate is chosen.
///
/// The variant set is **closed** in V1 — users cannot define new policies.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum TieBreakPolicy {
    /// Lexicographically smallest node/edge label wins.
    LexMin,
    /// Lexicographically largest node/edge label wins.
    LexMax,
    /// First-inserted candidate wins (adjacency-list order).
    InsertionOrder,
    /// Last-inserted candidate wins (reverse adjacency-list order).
    ReverseInsertionOrder,
    /// Primary: weight ascending; secondary: lex-min label.
    WeightThenLex,
    /// Primary: lex-min label; secondary: weight ascending.
    LexThenWeight,
    /// Deterministic hash of (seed, label) — reproducible but order-agnostic.
    DeterministicHash { seed: u64 },
    /// Minimum-degree node wins; ties broken by lex-min label.
    DegreeMinThenLex,
    /// Maximum-degree node wins; ties broken by lex-min label.
    DegreeMaxThenLex,
    /// DFS pre-order traversal order.
    DfsPreorder,
    /// BFS level order, within-level lex-min.
    BfsLevelLex,
    /// Edge key lex-min (for multigraph algorithms).
    EdgeKeyLex,
}

impl TieBreakPolicy {
    /// Short stable identifier for serialization and ledger entries.
    #[must_use]
    pub fn id(&self) -> &'static str {
        match self {
            Self::LexMin => "lex_min",
            Self::LexMax => "lex_max",
            Self::InsertionOrder => "insertion_order",
            Self::ReverseInsertionOrder => "reverse_insertion_order",
            Self::WeightThenLex => "weight_then_lex",
            Self::LexThenWeight => "lex_then_weight",
            Self::DeterministicHash { .. } => "deterministic_hash",
            Self::DegreeMinThenLex => "degree_min_then_lex",
            Self::DegreeMaxThenLex => "degree_max_then_lex",
            Self::DfsPreorder => "dfs_preorder",
            Self::BfsLevelLex => "bfs_level_lex",
            Self::EdgeKeyLex => "edge_key_lex",
        }
    }

    /// Sort a list of candidates according to the policy.
    pub fn sort_candidates<T: AsRef<str>>(&self, candidates: &mut [T]) {
        match self {
            Self::LexMin => candidates.sort_unstable_by(|a, b| a.as_ref().cmp(b.as_ref())),
            Self::LexMax => {
                candidates.sort_unstable_by(|a, b| b.as_ref().cmp(a.as_ref()));
            }
            Self::InsertionOrder | Self::ReverseInsertionOrder => {
                // These are governed by the underlying IndexMap order;
                // typically no-op or handled at the iterator level.
            }
            Self::WeightThenLex | Self::LexThenWeight => {
                // These require external weight data; handled by specialized
                // priority queue wrappers in fnx-algorithms.
            }
            Self::DeterministicHash { seed } => {
                let s = *seed;
                candidates.sort_unstable_by_key(|label| {
                    let mut hasher = blake3::Hasher::new();
                    hasher.update(&s.to_le_bytes());
                    hasher.update(label.as_ref().as_bytes());
                    *hasher.finalize().as_bytes()
                });
            }
            Self::DegreeMinThenLex | Self::DegreeMaxThenLex => {
                // Handled in algorithm inner loops where degree data is live.
            }
            Self::DfsPreorder | Self::BfsLevelLex | Self::EdgeKeyLex => {
                // Structural policies handled by traversal state machines.
            }
        }
    }
}

// ---------------------------------------------------------------------------
// Complexity Witness
// ---------------------------------------------------------------------------

/// A per-execution record emitted by every CGSE-instrumented algorithm.
///
/// The `decision_path_blake3` field is a Merkle-style hash of every tie-break
/// decision taken during execution: two runs on the same graph with the same
/// policy produce identical hashes, and any ordering drift manifests as a
/// hash mismatch.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ComplexityWitness {
    /// Number of nodes in the input graph.
    pub n: usize,
    /// Number of edges in the input graph.
    pub m: usize,
    /// Dominant complexity term symbol (e.g. "n_log_n", "n_m", "n_squared").
    pub dominant_term: String,
    /// Observed operation count (tie-break decisions + primary loop iterations).
    pub observed_count: u64,
    /// Which policy governed this execution.
    pub policy: TieBreakPolicy,
    /// Optional RNG seed (for randomized algorithms).
    pub seed: Option<u64>,
    /// Blake3 hash over the ordered sequence of tie-break decisions.
    pub decision_path_blake3: [u8; 32],
}

// ---------------------------------------------------------------------------
// Witness Sink — the per-execution collector
// ---------------------------------------------------------------------------

/// Collects tie-break decisions during a single algorithm execution.
///
/// Algorithms call [`WitnessSink::record_decision`] on every tie-break;
/// the sink updates a streaming Blake3 hasher and increments the counter.
/// When the algorithm finishes, call [`WitnessSink::finalize`] to produce
/// a [`ComplexityWitness`].
pub struct WitnessSink {
    hasher: blake3::Hasher,
    count: u64,
    policy: TieBreakPolicy,
}

impl WitnessSink {
    /// Create a new sink for the given policy.
    #[must_use]
    pub fn new(policy: TieBreakPolicy) -> Self {
        Self {
            hasher: blake3::Hasher::new(),
            count: 0,
            policy,
        }
    }

    /// Record a tie-break decision. The `chosen` and `rejected` labels are
    /// hashed in order to build the decision-path fingerprint.
    pub fn record_decision(&mut self, chosen: &str, rejected: &str) {
        self.record_len_prefixed(chosen.as_bytes());
        self.record_len_prefixed(rejected.as_bytes());
        self.count += 1;
    }

    /// Record an arbitrary decision byte slice (for numeric node labels).
    pub fn record_decision_bytes(&mut self, chosen: &[u8], rejected: &[u8]) {
        self.record_len_prefixed(chosen);
        self.record_len_prefixed(rejected);
        self.count += 1;
    }

    fn record_len_prefixed(&mut self, bytes: &[u8]) {
        let len = bytes.len() as u64;
        self.hasher.update(&len.to_le_bytes());
        self.hasher.update(bytes);
    }

    /// Finalize the sink into a [`ComplexityWitness`].
    #[must_use]
    pub fn finalize(
        self,
        n: usize,
        m: usize,
        dominant_term: &str,
        seed: Option<u64>,
    ) -> ComplexityWitness {
        let hash = *self.hasher.finalize().as_bytes();
        ComplexityWitness {
            n,
            m,
            dominant_term: dominant_term.to_string(),
            observed_count: self.count,
            policy: self.policy,
            seed,
            decision_path_blake3: hash,
        }
    }
}

// ---------------------------------------------------------------------------
// Witness Ledger — append-only log
// ---------------------------------------------------------------------------

/// Append-only ledger of [`ComplexityWitness`] records.
///
/// Serializable to JSONL for RaptorQ sidecar support. Thread-local access
/// pattern via [`with_ledger`].
#[derive(Debug, Default, Serialize, Deserialize)]
pub struct WitnessLedger {
    pub entries: Vec<ComplexityWitness>,
}

impl WitnessLedger {
    #[must_use]
    pub fn new() -> Self {
        Self {
            entries: Vec::new(),
        }
    }

    pub fn append(&mut self, witness: ComplexityWitness) {
        self.entries.push(witness);
    }

    /// Serialize the ledger to JSONL (one JSON object per line).
    pub fn to_jsonl(&self) -> String {
        self.entries
            .iter()
            .map(|w| serde_json::to_string(w).unwrap_or_default())
            .collect::<Vec<_>>()
            .join("\n")
    }

    /// Clear all entries.
    pub fn clear(&mut self) {
        self.entries.clear();
    }
}

// Thread-local ledger for automatic witness collection.
thread_local! {
    static THREAD_LEDGER: RefCell<WitnessLedger> = RefCell::new(WitnessLedger::new());
}

/// Execute a closure with access to the thread-local witness ledger.
///
/// Returns `Some(R)` on success, or `None` if the ledger is already
/// borrowed (reentrant call). Witness collection is best-effort
/// instrumentation, not a correctness primitive — nested calls
/// become a no-op rather than panicking with `BorrowMutError`
/// (br-r37-c1-g80ih).
pub fn with_ledger<F, R>(f: F) -> Option<R>
where
    F: FnOnce(&mut WitnessLedger) -> R,
{
    THREAD_LEDGER.with(|cell| match cell.try_borrow_mut() {
        Ok(mut guard) => Some(f(&mut guard)),
        Err(_) => None,
    })
}

/// Drain and return all witnesses from the thread-local ledger.
///
/// Returns an empty vector if the ledger is already borrowed
/// (reentrant call) — see [`with_ledger`] for the same defensive
/// behaviour (br-r37-c1-g80ih).
pub fn drain_witnesses() -> Vec<ComplexityWitness> {
    THREAD_LEDGER.with(|cell| match cell.try_borrow_mut() {
        Ok(mut ledger) => std::mem::take(&mut ledger.entries),
        Err(_) => Vec::new(),
    })
}

thread_local! {
    static WITNESS_COLLECTION_ACTIVE: Cell<bool> = const { Cell::new(false) };
}

/// Return whether CGSE witness collection is active for the current thread.
#[must_use]
pub fn witness_collection_enabled() -> bool {
    WITNESS_COLLECTION_ACTIVE.with(Cell::get)
}

struct WitnessGuard {
    was_active: bool,
}

impl Drop for WitnessGuard {
    fn drop(&mut self) {
        if !self.was_active {
            WITNESS_COLLECTION_ACTIVE.with(|cell| cell.set(false));
        }
    }
}

/// Run a closure with CGSE witness collection enabled and return the drained
/// witnesses produced inside it.
///
/// Nested calls share the active ledger; only the outermost invocation drains
/// the accumulated witnesses.
pub fn collect_witnesses<F, R>(f: F) -> (R, Vec<ComplexityWitness>)
where
    F: FnOnce() -> R,
{
    let was_active = WITNESS_COLLECTION_ACTIVE.with(|cell| {
        let active = cell.get();
        if !active {
            cell.set(true);
        }
        active
    });

    if !was_active {
        with_ledger(WitnessLedger::clear);
    }

    let _guard = WitnessGuard { was_active };

    let result = f();
    let witnesses = if was_active {
        Vec::new()
    } else {
        drain_witnesses()
    };

    (result, witnesses)
}

// ---------------------------------------------------------------------------
// Algorithm family registry
// ---------------------------------------------------------------------------

/// Declares the canonical tie-break policy for an algorithm family.
///
/// This is used by conformance tests to verify that each algorithm's
/// declared policy matches its observed ordering behavior.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AlgorithmFamilyPolicy {
    pub family: String,
    pub algorithm: String,
    pub policy: TieBreakPolicy,
    pub dominant_complexity: String,
}

/// The V1 reference algorithms whose call sites are wired through CGSE.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ReferenceAlgorithm {
    Dijkstra,
    BellmanFord,
    Bfs,
    Dfs,
    MaxWeightMatching,
    MinWeightMatching,
    ConnectedComponents,
    StronglyConnectedComponents,
    Kruskal,
    Prim,
    EulerianCircuit,
    TopologicalSort,
}

impl ReferenceAlgorithm {
    pub const ALL: [Self; 12] = [
        Self::Dijkstra,
        Self::BellmanFord,
        Self::Bfs,
        Self::Dfs,
        Self::MaxWeightMatching,
        Self::MinWeightMatching,
        Self::ConnectedComponents,
        Self::StronglyConnectedComponents,
        Self::Kruskal,
        Self::Prim,
        Self::EulerianCircuit,
        Self::TopologicalSort,
    ];

    #[must_use]
    pub const fn family(self) -> &'static str {
        match self {
            Self::Dijkstra | Self::BellmanFord => "shortest_path",
            Self::Bfs | Self::Dfs => "traversal",
            Self::MaxWeightMatching | Self::MinWeightMatching => "matching",
            Self::ConnectedComponents | Self::StronglyConnectedComponents => "connectivity",
            Self::Kruskal | Self::Prim => "trees",
            Self::EulerianCircuit => "euler",
            Self::TopologicalSort => "dag",
        }
    }

    #[must_use]
    pub const fn algorithm(self) -> &'static str {
        match self {
            Self::Dijkstra => "dijkstra",
            Self::BellmanFord => "bellman_ford",
            Self::Bfs => "bfs",
            Self::Dfs => "dfs",
            Self::MaxWeightMatching => "max_weight_matching",
            Self::MinWeightMatching => "min_weight_matching",
            Self::ConnectedComponents => "connected_components",
            Self::StronglyConnectedComponents => "strongly_connected_components",
            Self::Kruskal => "kruskal",
            Self::Prim => "prim",
            Self::EulerianCircuit => "eulerian_circuit",
            Self::TopologicalSort => "topological_sort",
        }
    }

    #[must_use]
    pub const fn policy(self) -> TieBreakPolicy {
        match self {
            Self::Dijkstra => TieBreakPolicy::WeightThenLex,
            Self::BellmanFord => TieBreakPolicy::InsertionOrder,
            Self::Bfs => TieBreakPolicy::InsertionOrder,
            Self::Dfs => TieBreakPolicy::InsertionOrder,
            Self::MaxWeightMatching => TieBreakPolicy::WeightThenLex,
            Self::MinWeightMatching => TieBreakPolicy::WeightThenLex,
            Self::ConnectedComponents => TieBreakPolicy::LexMin,
            Self::StronglyConnectedComponents => TieBreakPolicy::InsertionOrder,
            Self::Kruskal => TieBreakPolicy::WeightThenLex,
            Self::Prim => TieBreakPolicy::WeightThenLex,
            Self::EulerianCircuit => TieBreakPolicy::InsertionOrder,
            Self::TopologicalSort => TieBreakPolicy::InsertionOrder,
        }
    }

    #[must_use]
    pub const fn dominant_complexity(self) -> &'static str {
        match self {
            Self::Dijkstra => "n_plus_m_log_n",
            Self::BellmanFord => "n_m",
            Self::Bfs => "n_plus_m",
            Self::Dfs => "n_plus_m",
            Self::MaxWeightMatching | Self::MinWeightMatching => "n_m_alpha",
            Self::ConnectedComponents => "n_plus_m",
            Self::StronglyConnectedComponents => "n_plus_m",
            Self::Kruskal => "m_log_m",
            Self::Prim => "m_log_n",
            Self::EulerianCircuit => "m",
            Self::TopologicalSort => "n_plus_m",
        }
    }

    #[must_use]
    pub fn policy_row(self) -> AlgorithmFamilyPolicy {
        AlgorithmFamilyPolicy {
            family: self.family().to_owned(),
            algorithm: self.algorithm().to_owned(),
            policy: self.policy(),
            dominant_complexity: self.dominant_complexity().to_owned(),
        }
    }

    #[must_use]
    pub fn from_algorithm_id(algorithm: &str) -> Option<Self> {
        Some(match algorithm {
            "dijkstra" => Self::Dijkstra,
            "bellman_ford" => Self::BellmanFord,
            "bfs" => Self::Bfs,
            "dfs" => Self::Dfs,
            "max_weight_matching" => Self::MaxWeightMatching,
            "min_weight_matching" => Self::MinWeightMatching,
            "connected_components" => Self::ConnectedComponents,
            "strongly_connected_components" => Self::StronglyConnectedComponents,
            "kruskal" => Self::Kruskal,
            "prim" => Self::Prim,
            "eulerian_circuit" => Self::EulerianCircuit,
            "topological_sort" => Self::TopologicalSort,
            _ => return None,
        })
    }
}

/// The canonical policy registry for V1 algorithms.
///
/// Each entry maps an algorithm to its declared tie-break policy and
/// dominant complexity term.
#[must_use]
pub fn v1_policy_registry() -> Vec<AlgorithmFamilyPolicy> {
    ReferenceAlgorithm::ALL
        .into_iter()
        .map(ReferenceAlgorithm::policy_row)
        .collect()
}

// ---------------------------------------------------------------------------
// Complexity Oracle — C8
// ---------------------------------------------------------------------------

/// Result of complexity bound verification.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ComplexityBoundResult {
    pub within_bounds: bool,
    pub observed_count: u64,
    pub upper_bound: u64,
    pub dominant_term: String,
    pub formula: String,
}

/// Evaluate the analytic upper bound for a complexity class.
pub fn analytic_upper_bound(dominant_term: &str, n: usize, m: usize) -> Option<u64> {
    let n = n as u64;
    let m = m as u64;
    match dominant_term {
        "n" => Some(n),
        "m" => Some(m),
        "n_plus_m" => Some(n.saturating_add(m)),
        "n_log_n" => {
            let log_n = if n <= 1 {
                1
            } else {
                (n as f64).log2().ceil() as u64
            };
            Some(n.saturating_mul(log_n))
        }
        "n_plus_m_log_n" => {
            let log_n = if n <= 1 {
                1
            } else {
                (n as f64).log2().ceil() as u64
            };
            Some(n.saturating_add(m.saturating_mul(log_n)))
        }
        "n_m" => Some(n.saturating_mul(m)),
        "n_squared" => Some(n.saturating_mul(n)),
        "n_m_alpha" => {
            // n * m * inverse_ackermann(n), approximated as n * m * log*(n)
            let alpha = if n <= 1 {
                1
            } else {
                ((n as f64).log2().log2().ceil() as u64).max(1)
            };
            Some(n.saturating_mul(m).saturating_mul(alpha))
        }
        "m_log_m" => {
            let log_m = if m <= 1 {
                1
            } else {
                (m as f64).log2().ceil() as u64
            };
            Some(m.saturating_mul(log_m))
        }
        "m_log_n" => {
            let log_n = if n <= 1 {
                1
            } else {
                (n as f64).log2().ceil() as u64
            };
            Some(m.saturating_mul(log_n))
        }
        _ => None,
    }
}

/// Verify that a witness's observed count is within the expected complexity bounds.
/// Returns a result indicating whether the count is acceptable.
pub fn verify_complexity_bound(witness: &ComplexityWitness) -> Option<ComplexityBoundResult> {
    let upper = analytic_upper_bound(&witness.dominant_term, witness.n, witness.m)?;
    // Allow a 2x multiplier for constant factors
    let adjusted_upper = upper.saturating_mul(2);
    Some(ComplexityBoundResult {
        within_bounds: witness.observed_count <= adjusted_upper,
        observed_count: witness.observed_count,
        upper_bound: adjusted_upper,
        dominant_term: witness.dominant_term.clone(),
        formula: format!("2 * f({}, {})", witness.n, witness.m),
    })
}

/// Complexity oracle assertion: panic if witness exceeds expected bounds.
pub fn assert_complexity_within_bounds(witness: &ComplexityWitness) {
    if let Some(result) = verify_complexity_bound(witness) {
        assert!(
            result.within_bounds,
            "Complexity bound violation: observed {} operations, expected at most {} for {} complexity (n={}, m={})",
            result.observed_count, result.upper_bound, result.dominant_term, witness.n, witness.m
        );
    }
}

// ---------------------------------------------------------------------------
// Counter-Example Mining — G3
// ---------------------------------------------------------------------------

/// A counter-example candidate found during witness-hash mining.
///
/// When two executions of the same algorithm on the same graph produce
/// different witness hashes, we have found a potential non-determinism bug.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CounterExample {
    /// The algorithm that exhibited non-determinism.
    pub algorithm: ReferenceAlgorithm,
    /// The graph that triggered the issue (serialized as edge list).
    pub graph_edges: Vec<(String, String)>,
    /// Number of nodes in the graph.
    pub node_count: usize,
    /// Whether the graph is directed.
    pub directed: bool,
    /// Witness from the first run.
    pub witness_a: ComplexityWitness,
    /// Witness from the second run.
    pub witness_b: ComplexityWitness,
    /// Description of the discrepancy.
    pub discrepancy: String,
}

/// Result of a counter-example mining session.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MiningResult {
    /// Counter-examples found during mining.
    pub counter_examples: Vec<CounterExample>,
    /// Number of graphs tested.
    pub graphs_tested: u64,
    /// Number of algorithm executions.
    pub executions: u64,
    /// Algorithms that passed all tests.
    pub passing_algorithms: Vec<ReferenceAlgorithm>,
}

impl MiningResult {
    /// Returns true if no counter-examples were found.
    #[must_use]
    pub fn is_clean(&self) -> bool {
        self.counter_examples.is_empty()
    }
}

/// Configuration for counter-example mining.
#[derive(Debug, Clone)]
pub struct MiningConfig {
    /// Number of random graphs to generate per algorithm.
    pub graphs_per_algorithm: usize,
    /// Number of repeated executions per graph (to detect non-determinism).
    pub executions_per_graph: usize,
    /// Maximum number of nodes in generated graphs.
    pub max_nodes: usize,
    /// Maximum edge density (0.0 to 1.0).
    pub max_density: f64,
    /// Seed for reproducible random generation.
    pub seed: u64,
}

impl Default for MiningConfig {
    fn default() -> Self {
        Self {
            graphs_per_algorithm: 100,
            executions_per_graph: 3,
            max_nodes: 20,
            max_density: 0.5,
            seed: 0,
        }
    }
}

/// Compares two witnesses for consistency.
///
/// Returns a description of the discrepancy if the witnesses differ in
/// decision path (the main indicator of non-determinism).
#[must_use]
pub fn compare_witnesses(a: &ComplexityWitness, b: &ComplexityWitness) -> Option<String> {
    if a.decision_path_blake3 != b.decision_path_blake3 {
        let hash_a = hex::encode(&a.decision_path_blake3[..8]);
        let hash_b = hex::encode(&b.decision_path_blake3[..8]);
        return Some(format!(
            "Decision path hash mismatch: {}... vs {}... (counts: {} vs {})",
            hash_a, hash_b, a.observed_count, b.observed_count
        ));
    }

    if a.observed_count != b.observed_count {
        return Some(format!(
            "Operation count mismatch: {} vs {} (hashes match)",
            a.observed_count, b.observed_count
        ));
    }

    None
}

/// Verifies witness determinism by running the same algorithm multiple times
/// and checking for hash consistency.
///
/// Returns `None` if all runs produce identical witnesses, or a `CounterExample`
/// if non-determinism is detected.
pub fn verify_witness_determinism<F>(
    algorithm: ReferenceAlgorithm,
    graph_edges: Vec<(String, String)>,
    node_count: usize,
    directed: bool,
    iterations: usize,
    mut run_algorithm: F,
) -> Option<CounterExample>
where
    F: FnMut() -> Vec<ComplexityWitness>,
{
    if iterations < 2 {
        return None;
    }

    let first_witnesses = run_algorithm();
    let first_witness = first_witnesses.into_iter().next()?;

    for _ in 1..iterations {
        let witnesses = run_algorithm();
        if let Some(witness) = witnesses.into_iter().next()
            && let Some(discrepancy) = compare_witnesses(&first_witness, &witness)
        {
            return Some(CounterExample {
                algorithm,
                graph_edges,
                node_count,
                directed,
                witness_a: first_witness,
                witness_b: witness,
                discrepancy,
            });
        }
    }

    None
}

/// Generates a deterministic pseudo-random value from a seed and index.
#[must_use]
fn seeded_random(seed: u64, index: u64) -> u64 {
    // Simple LCG for reproducibility
    let mut state = seed.wrapping_add(index);
    state = state.wrapping_mul(6364136223846793005).wrapping_add(1);
    state
}

/// Generates random graph edges for testing.
#[must_use]
pub fn generate_random_edges(
    node_count: usize,
    density: f64,
    directed: bool,
    seed: u64,
) -> Vec<(String, String)> {
    let mut edges = Vec::new();
    let mut idx = 0u64;

    for i in 0..node_count {
        let j_start = if directed { 0 } else { i + 1 };
        for j in j_start..node_count {
            if i == j {
                continue;
            }
            let rand = (seeded_random(seed, idx) % 1000) as f64 / 1000.0;
            idx += 1;
            if rand < density {
                edges.push((i.to_string(), j.to_string()));
            }
        }
    }

    edges
}

/// Serializes a mining result to JSONL format.
#[must_use]
pub fn mining_result_to_jsonl(result: &MiningResult) -> String {
    let mut lines = Vec::new();

    // Header line
    lines.push(
        serde_json::json!({
            "type": "mining_summary",
            "graphs_tested": result.graphs_tested,
            "executions": result.executions,
            "counter_examples_found": result.counter_examples.len(),
            "passing_algorithms": result.passing_algorithms.iter()
                .map(|a| a.algorithm())
                .collect::<Vec<_>>(),
        })
        .to_string(),
    );

    // Counter-example lines
    for ce in &result.counter_examples {
        lines.push(serde_json::to_string(ce).unwrap_or_default());
    }

    lines.join("\n")
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_policy_id_stable() {
        assert_eq!(TieBreakPolicy::LexMin.id(), "lex_min");
        assert_eq!(TieBreakPolicy::WeightThenLex.id(), "weight_then_lex");
        assert_eq!(
            TieBreakPolicy::DeterministicHash { seed: 42 }.id(),
            "deterministic_hash"
        );
    }

    #[test]
    fn test_policy_roundtrip_serde() {
        for policy in [
            TieBreakPolicy::LexMin,
            TieBreakPolicy::LexMax,
            TieBreakPolicy::InsertionOrder,
            TieBreakPolicy::ReverseInsertionOrder,
            TieBreakPolicy::WeightThenLex,
            TieBreakPolicy::LexThenWeight,
            TieBreakPolicy::DeterministicHash { seed: 42 },
            TieBreakPolicy::DegreeMinThenLex,
            TieBreakPolicy::DegreeMaxThenLex,
            TieBreakPolicy::DfsPreorder,
            TieBreakPolicy::BfsLevelLex,
            TieBreakPolicy::EdgeKeyLex,
        ] {
            let json = serde_json::to_string(&policy).unwrap();
            let back: TieBreakPolicy = serde_json::from_str(&json).unwrap();
            assert_eq!(policy, back);
        }
    }

    #[test]
    fn test_witness_sink_deterministic_hash() {
        let mut sink1 = WitnessSink::new(TieBreakPolicy::LexMin);
        sink1.record_decision("a", "b");
        sink1.record_decision("c", "d");
        let w1 = sink1.finalize(4, 3, "n_plus_m", None);

        let mut sink2 = WitnessSink::new(TieBreakPolicy::LexMin);
        sink2.record_decision("a", "b");
        sink2.record_decision("c", "d");
        let w2 = sink2.finalize(4, 3, "n_plus_m", None);

        // Same decisions → same hash.
        assert_eq!(w1.decision_path_blake3, w2.decision_path_blake3);
        assert_eq!(w1.observed_count, 2);
    }

    #[test]
    fn test_witness_sink_different_decisions_different_hash() {
        let mut sink1 = WitnessSink::new(TieBreakPolicy::LexMin);
        sink1.record_decision("a", "b");
        let w1 = sink1.finalize(2, 1, "n", None);

        let mut sink2 = WitnessSink::new(TieBreakPolicy::LexMin);
        sink2.record_decision("b", "a"); // reversed
        let w2 = sink2.finalize(2, 1, "n", None);

        // Different decisions → different hash.
        assert_ne!(w1.decision_path_blake3, w2.decision_path_blake3);
    }

    #[test]
    fn test_witness_ledger_jsonl() {
        let mut ledger = WitnessLedger::new();
        let mut sink = WitnessSink::new(TieBreakPolicy::InsertionOrder);
        sink.record_decision("x", "y");
        ledger.append(sink.finalize(3, 2, "n_plus_m", None));

        let jsonl = ledger.to_jsonl();
        assert!(!jsonl.is_empty());
        let _: ComplexityWitness = serde_json::from_str(&jsonl).unwrap();
    }

    #[test]
    fn test_thread_local_ledger() {
        with_ledger(|l| l.clear());

        let mut sink = WitnessSink::new(TieBreakPolicy::BfsLevelLex);
        sink.record_decision("1", "2");
        let w = sink.finalize(5, 4, "n_plus_m", None);
        with_ledger(|l| l.append(w));

        let drained = drain_witnesses();
        assert_eq!(drained.len(), 1);
        assert_eq!(drained[0].policy, TieBreakPolicy::BfsLevelLex);
    }

    #[test]
    fn test_v1_registry_has_12_entries() {
        let reg = v1_policy_registry();
        assert_eq!(reg.len(), 12);
    }

    #[test]
    fn test_v1_registry_unique_algorithms() {
        let reg = v1_policy_registry();
        let mut algos: Vec<&str> = reg.iter().map(|r| r.algorithm.as_str()).collect();
        algos.sort();
        algos.dedup();
        assert_eq!(algos.len(), 12, "All 12 algorithms should be unique");
    }

    #[test]
    fn test_analytic_upper_bound_n_plus_m() {
        assert_eq!(analytic_upper_bound("n_plus_m", 100, 200), Some(300));
    }

    #[test]
    fn test_analytic_upper_bound_n_log_n() {
        let bound = analytic_upper_bound("n_log_n", 1024, 0).unwrap();
        // 1024 * ceil(log2(1024)) = 1024 * 10 = 10240
        assert_eq!(bound, 10240);
    }

    #[test]
    fn test_analytic_upper_bound_m_log_m() {
        let bound = analytic_upper_bound("m_log_m", 0, 256).unwrap();
        // 256 * ceil(log2(256)) = 256 * 8 = 2048
        assert_eq!(bound, 2048);
    }

    #[test]
    fn test_verify_complexity_bound_within() {
        let witness = ComplexityWitness {
            n: 100,
            m: 200,
            dominant_term: "n_plus_m".to_owned(),
            observed_count: 500, // Well within 2 * 300 = 600
            policy: TieBreakPolicy::LexMin,
            seed: None,
            decision_path_blake3: [0u8; 32],
        };
        let result = verify_complexity_bound(&witness).unwrap();
        assert!(result.within_bounds);
        assert_eq!(result.upper_bound, 600);
    }

    #[test]
    fn test_verify_complexity_bound_exceeded() {
        let witness = ComplexityWitness {
            n: 100,
            m: 200,
            dominant_term: "n_plus_m".to_owned(),
            observed_count: 1000, // Exceeds 2 * 300 = 600
            policy: TieBreakPolicy::LexMin,
            seed: None,
            decision_path_blake3: [0u8; 32],
        };
        let result = verify_complexity_bound(&witness).unwrap();
        assert!(!result.within_bounds);
    }

    #[test]
    fn test_analytic_upper_bound_unknown_term() {
        assert_eq!(analytic_upper_bound("unknown", 100, 200), None);
    }

    #[test]
    fn test_collect_witnesses_panic_safety() {
        let result = std::panic::catch_unwind(|| {
            collect_witnesses(|| {
                std::panic::resume_unwind(Box::new("intentional panic"));
            });
        });
        assert!(result.is_err());
        // Verify that the thread-local state was reset correctly despite the panic.
        assert!(!witness_collection_enabled());
    }

    // -------------------------------------------------------------------------
    // Counter-Example Mining Tests
    // -------------------------------------------------------------------------

    #[test]
    fn test_compare_witnesses_identical() {
        let w1 = ComplexityWitness {
            n: 10,
            m: 15,
            dominant_term: "n_plus_m".to_owned(),
            observed_count: 25,
            policy: TieBreakPolicy::LexMin,
            seed: None,
            decision_path_blake3: [42u8; 32],
        };
        let w2 = w1.clone();
        assert!(compare_witnesses(&w1, &w2).is_none());
    }

    #[test]
    fn test_compare_witnesses_hash_mismatch() {
        let w1 = ComplexityWitness {
            n: 10,
            m: 15,
            dominant_term: "n_plus_m".to_owned(),
            observed_count: 25,
            policy: TieBreakPolicy::LexMin,
            seed: None,
            decision_path_blake3: [42u8; 32],
        };
        let w2 = ComplexityWitness {
            decision_path_blake3: [99u8; 32],
            ..w1.clone()
        };
        let result = compare_witnesses(&w1, &w2);
        assert!(result.is_some());
        assert!(result.unwrap().contains("hash mismatch"));
    }

    #[test]
    fn test_compare_witnesses_count_mismatch() {
        let w1 = ComplexityWitness {
            n: 10,
            m: 15,
            dominant_term: "n_plus_m".to_owned(),
            observed_count: 25,
            policy: TieBreakPolicy::LexMin,
            seed: None,
            decision_path_blake3: [42u8; 32],
        };
        let w2 = ComplexityWitness {
            observed_count: 30,
            ..w1.clone()
        };
        let result = compare_witnesses(&w1, &w2);
        assert!(result.is_some());
        assert!(result.unwrap().contains("count mismatch"));
    }

    #[test]
    fn test_generate_random_edges_deterministic() {
        let edges1 = generate_random_edges(5, 0.5, false, 12345);
        let edges2 = generate_random_edges(5, 0.5, false, 12345);
        assert_eq!(edges1, edges2);
    }

    #[test]
    fn test_generate_random_edges_different_seeds() {
        let edges1 = generate_random_edges(5, 0.5, false, 12345);
        let edges2 = generate_random_edges(5, 0.5, false, 54321);
        assert_ne!(edges1, edges2);
    }

    #[test]
    fn test_generate_random_edges_directed() {
        let edges = generate_random_edges(3, 1.0, true, 0);
        // Directed graph with n=3 can have up to 6 edges (3*2)
        // but some may be filtered by the random process
        assert!(!edges.is_empty());
    }

    #[test]
    fn test_mining_result_clean() {
        let result = MiningResult {
            counter_examples: vec![],
            graphs_tested: 100,
            executions: 300,
            passing_algorithms: ReferenceAlgorithm::ALL.to_vec(),
        };
        assert!(result.is_clean());
    }

    #[test]
    fn test_mining_result_to_jsonl_format() {
        let result = MiningResult {
            counter_examples: vec![],
            graphs_tested: 10,
            executions: 30,
            passing_algorithms: vec![ReferenceAlgorithm::Bfs, ReferenceAlgorithm::Dfs],
        };
        let jsonl = mining_result_to_jsonl(&result);
        assert!(jsonl.contains("mining_summary"));
        assert!(jsonl.contains("graphs_tested"));
        assert!(jsonl.contains("10"));
    }

    #[test]
    fn test_verify_witness_determinism_consistent() {
        let edges = vec![("0".to_string(), "1".to_string())];
        let mut call_count = 0;

        let result =
            verify_witness_determinism(ReferenceAlgorithm::Bfs, edges, 2, false, 3, || {
                call_count += 1;
                vec![ComplexityWitness {
                    n: 2,
                    m: 1,
                    dominant_term: "n_plus_m".to_owned(),
                    observed_count: 3,
                    policy: TieBreakPolicy::InsertionOrder,
                    seed: None,
                    decision_path_blake3: [1u8; 32],
                }]
            });

        assert!(
            result.is_none(),
            "Consistent witnesses should not produce counter-example"
        );
        assert_eq!(call_count, 3);
    }

    #[test]
    fn test_verify_witness_determinism_inconsistent() {
        let edges = vec![("0".to_string(), "1".to_string())];
        let mut call_count = 0;

        let result =
            verify_witness_determinism(ReferenceAlgorithm::Bfs, edges, 2, false, 3, || {
                call_count += 1;
                vec![ComplexityWitness {
                    n: 2,
                    m: 1,
                    dominant_term: "n_plus_m".to_owned(),
                    observed_count: 3,
                    policy: TieBreakPolicy::InsertionOrder,
                    seed: None,
                    // Different hash each call to simulate non-determinism
                    decision_path_blake3: [call_count as u8; 32],
                }]
            });

        assert!(
            result.is_some(),
            "Inconsistent witnesses should produce counter-example"
        );
        let ce = result.unwrap();
        assert_eq!(ce.algorithm, ReferenceAlgorithm::Bfs);
        assert!(ce.discrepancy.contains("hash mismatch"));
    }

    #[test]
    fn test_mining_config_default() {
        let config = MiningConfig::default();
        assert_eq!(config.graphs_per_algorithm, 100);
        assert_eq!(config.executions_per_graph, 3);
        assert_eq!(config.max_nodes, 20);
        assert!(config.max_density > 0.0);
    }
}
