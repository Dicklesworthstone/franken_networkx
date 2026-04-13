//! Python bindings for the Canonical Graph Semantics Engine (CGSE).
//!
//! Exposes:
//! - `TieBreakPolicy`: The 12 canonical tie-break orderings
//! - `ComplexityWitness`: Per-execution proof of tie-break decisions
//! - `collect_witnesses()`: Wrapper for running algorithms with witness collection

use fnx_cgse::{ComplexityWitness, ReferenceAlgorithm, TieBreakPolicy, v1_policy_registry};
use pyo3::prelude::*;
use pyo3::types::PyDict;

/// The 12 canonical tie-break orderings that NetworkX algorithms exhibit.
#[pyclass(name = "TieBreakPolicy")]
#[derive(Debug, Clone)]
pub struct PyTieBreakPolicy(pub TieBreakPolicy);

#[pymethods]
impl PyTieBreakPolicy {
    /// Lexicographically smallest node/edge label wins.
    #[staticmethod]
    fn lex_min() -> Self {
        Self(TieBreakPolicy::LexMin)
    }

    /// Lexicographically largest node/edge label wins.
    #[staticmethod]
    fn lex_max() -> Self {
        Self(TieBreakPolicy::LexMax)
    }

    /// First-inserted candidate wins (adjacency-list order).
    #[staticmethod]
    fn insertion_order() -> Self {
        Self(TieBreakPolicy::InsertionOrder)
    }

    /// Last-inserted candidate wins (reverse adjacency-list order).
    #[staticmethod]
    fn reverse_insertion_order() -> Self {
        Self(TieBreakPolicy::ReverseInsertionOrder)
    }

    /// Primary: weight ascending; secondary: lex-min label.
    #[staticmethod]
    fn weight_then_lex() -> Self {
        Self(TieBreakPolicy::WeightThenLex)
    }

    /// Primary: lex-min label; secondary: weight ascending.
    #[staticmethod]
    fn lex_then_weight() -> Self {
        Self(TieBreakPolicy::LexThenWeight)
    }

    /// Deterministic hash of (seed, label).
    #[staticmethod]
    fn deterministic_hash(seed: u64) -> Self {
        Self(TieBreakPolicy::DeterministicHash { seed })
    }

    /// Minimum-degree node wins; ties broken by lex-min label.
    #[staticmethod]
    fn degree_min_then_lex() -> Self {
        Self(TieBreakPolicy::DegreeMinThenLex)
    }

    /// Maximum-degree node wins; ties broken by lex-min label.
    #[staticmethod]
    fn degree_max_then_lex() -> Self {
        Self(TieBreakPolicy::DegreeMaxThenLex)
    }

    /// DFS pre-order traversal order.
    #[staticmethod]
    fn dfs_preorder() -> Self {
        Self(TieBreakPolicy::DfsPreorder)
    }

    /// BFS level order, within-level lex-min.
    #[staticmethod]
    fn bfs_level_lex() -> Self {
        Self(TieBreakPolicy::BfsLevelLex)
    }

    /// Edge key lex-min (for multigraph algorithms).
    #[staticmethod]
    fn edge_key_lex() -> Self {
        Self(TieBreakPolicy::EdgeKeyLex)
    }

    /// Short stable identifier string.
    fn id(&self) -> &'static str {
        self.0.id()
    }

    fn __repr__(&self) -> String {
        format!("TieBreakPolicy.{}", self.0.id())
    }

    fn __eq__(&self, other: &Self) -> bool {
        self.0 == other.0
    }

    fn __hash__(&self) -> u64 {
        use std::hash::{Hash, Hasher};
        let mut hasher = std::collections::hash_map::DefaultHasher::new();
        self.0.hash(&mut hasher);
        hasher.finish()
    }
}

/// A per-execution record emitted by CGSE-instrumented algorithms.
#[pyclass(name = "ComplexityWitness")]
#[derive(Debug, Clone)]
pub struct PyComplexityWitness(pub ComplexityWitness);

#[pymethods]
impl PyComplexityWitness {
    /// Number of nodes in the input graph.
    #[getter]
    fn n(&self) -> usize {
        self.0.n
    }

    /// Number of edges in the input graph.
    #[getter]
    fn m(&self) -> usize {
        self.0.m
    }

    /// Dominant complexity term symbol (e.g., "n_log_n", "n_m").
    #[getter]
    fn dominant_term(&self) -> &str {
        &self.0.dominant_term
    }

    /// Observed operation count (tie-break decisions).
    #[getter]
    fn observed_count(&self) -> u64 {
        self.0.observed_count
    }

    /// Which tie-break policy governed this execution.
    #[getter]
    fn policy(&self) -> PyTieBreakPolicy {
        PyTieBreakPolicy(self.0.policy)
    }

    /// Optional RNG seed (for randomized algorithms).
    #[getter]
    fn seed(&self) -> Option<u64> {
        self.0.seed
    }

    /// Blake3 hash over the ordered sequence of tie-break decisions, as hex.
    #[getter]
    fn decision_path_hash(&self) -> String {
        hex::encode(self.0.decision_path_blake3)
    }

    fn __repr__(&self) -> String {
        format!(
            "ComplexityWitness(n={}, m={}, policy={}, observed_count={}, hash={}...)",
            self.0.n,
            self.0.m,
            self.0.policy.id(),
            self.0.observed_count,
            &hex::encode(&self.0.decision_path_blake3[..4])
        )
    }
}

/// Get the canonical policy for a reference algorithm.
#[pyfunction]
pub fn algorithm_policy(algorithm: &str) -> PyResult<Option<PyTieBreakPolicy>> {
    Ok(ReferenceAlgorithm::from_algorithm_id(algorithm).map(|alg| PyTieBreakPolicy(alg.policy())))
}

/// Get the full V1 policy registry as a dict.
#[pyfunction]
pub fn policy_registry(py: Python<'_>) -> PyResult<Py<PyDict>> {
    let registry = v1_policy_registry();
    let dict = PyDict::new(py);
    for entry in registry {
        let inner = PyDict::new(py);
        inner.set_item("family", entry.family)?;
        inner.set_item("policy", entry.policy.id())?;
        inner.set_item("dominant_complexity", entry.dominant_complexity)?;
        dict.set_item(entry.algorithm, inner)?;
    }
    Ok(dict.into())
}

/// List all reference algorithm IDs.
#[pyfunction]
pub fn reference_algorithms() -> Vec<&'static str> {
    ReferenceAlgorithm::ALL
        .into_iter()
        .map(|alg| alg.algorithm())
        .collect()
}

pub fn register_module(parent: &Bound<'_, PyModule>) -> PyResult<()> {
    let m = PyModule::new(parent.py(), "cgse")?;
    m.add_class::<PyTieBreakPolicy>()?;
    m.add_class::<PyComplexityWitness>()?;
    m.add_function(wrap_pyfunction!(algorithm_policy, &m)?)?;
    m.add_function(wrap_pyfunction!(policy_registry, &m)?)?;
    m.add_function(wrap_pyfunction!(reference_algorithms, &m)?)?;
    parent.add_submodule(&m)?;
    Ok(())
}
