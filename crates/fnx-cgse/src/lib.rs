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
use std::cell::RefCell;

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
    DeterministicHash {
        seed: u64,
    },
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
        self.hasher.update(chosen.as_bytes());
        self.hasher.update(b"|");
        self.hasher.update(rejected.as_bytes());
        self.hasher.update(b"\n");
        self.count += 1;
    }

    /// Record an arbitrary decision byte slice (for numeric node labels).
    pub fn record_decision_bytes(&mut self, chosen: &[u8], rejected: &[u8]) {
        self.hasher.update(chosen);
        self.hasher.update(b"|");
        self.hasher.update(rejected);
        self.hasher.update(b"\n");
        self.count += 1;
    }

    /// Finalize the sink into a [`ComplexityWitness`].
    #[must_use]
    pub fn finalize(self, n: usize, m: usize, dominant_term: &str, seed: Option<u64>) -> ComplexityWitness {
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
        Self { entries: Vec::new() }
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
pub fn with_ledger<F, R>(f: F) -> R
where
    F: FnOnce(&mut WitnessLedger) -> R,
{
    THREAD_LEDGER.with(|cell| f(&mut cell.borrow_mut()))
}

/// Drain and return all witnesses from the thread-local ledger.
pub fn drain_witnesses() -> Vec<ComplexityWitness> {
    THREAD_LEDGER.with(|cell| {
        let mut ledger = cell.borrow_mut();
        std::mem::take(&mut ledger.entries)
    })
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

/// The canonical policy registry for V1 algorithms.
///
/// Each entry maps an algorithm to its declared tie-break policy and
/// dominant complexity term.
#[must_use]
pub fn v1_policy_registry() -> Vec<AlgorithmFamilyPolicy> {
    vec![
        AlgorithmFamilyPolicy {
            family: "shortest_path".into(),
            algorithm: "dijkstra".into(),
            policy: TieBreakPolicy::WeightThenLex,
            dominant_complexity: "n_plus_m_log_n".into(),
        },
        AlgorithmFamilyPolicy {
            family: "shortest_path".into(),
            algorithm: "bellman_ford".into(),
            policy: TieBreakPolicy::InsertionOrder,
            dominant_complexity: "n_m".into(),
        },
        AlgorithmFamilyPolicy {
            family: "traversal".into(),
            algorithm: "bfs".into(),
            policy: TieBreakPolicy::InsertionOrder,
            dominant_complexity: "n_plus_m".into(),
        },
        AlgorithmFamilyPolicy {
            family: "traversal".into(),
            algorithm: "dfs".into(),
            policy: TieBreakPolicy::InsertionOrder,
            dominant_complexity: "n_plus_m".into(),
        },
        AlgorithmFamilyPolicy {
            family: "matching".into(),
            algorithm: "max_weight_matching".into(),
            policy: TieBreakPolicy::WeightThenLex,
            dominant_complexity: "n_m_alpha".into(),
        },
        AlgorithmFamilyPolicy {
            family: "matching".into(),
            algorithm: "min_weight_matching".into(),
            policy: TieBreakPolicy::WeightThenLex,
            dominant_complexity: "n_m_alpha".into(),
        },
        AlgorithmFamilyPolicy {
            family: "connectivity".into(),
            algorithm: "connected_components".into(),
            policy: TieBreakPolicy::LexMin,
            dominant_complexity: "n_plus_m".into(),
        },
        AlgorithmFamilyPolicy {
            family: "connectivity".into(),
            algorithm: "strongly_connected_components".into(),
            policy: TieBreakPolicy::InsertionOrder,
            dominant_complexity: "n_plus_m".into(),
        },
        AlgorithmFamilyPolicy {
            family: "trees".into(),
            algorithm: "kruskal".into(),
            policy: TieBreakPolicy::WeightThenLex,
            dominant_complexity: "m_log_m".into(),
        },
        AlgorithmFamilyPolicy {
            family: "trees".into(),
            algorithm: "prim".into(),
            policy: TieBreakPolicy::WeightThenLex,
            dominant_complexity: "m_log_n".into(),
        },
        AlgorithmFamilyPolicy {
            family: "euler".into(),
            algorithm: "eulerian_circuit".into(),
            policy: TieBreakPolicy::InsertionOrder,
            dominant_complexity: "m".into(),
        },
        AlgorithmFamilyPolicy {
            family: "dag".into(),
            algorithm: "topological_sort".into(),
            policy: TieBreakPolicy::InsertionOrder,
            dominant_complexity: "n_plus_m".into(),
        },
    ]
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
}
