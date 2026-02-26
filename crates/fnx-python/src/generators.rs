//! Python bindings for graph generator functions.
//!
//! Wraps `fnx_generators::GraphGenerator` methods as module-level functions.
//! Node labels are Python integers (0, 1, 2, ...) matching NetworkX convention.

use crate::PyGraph;
use fnx_generators::GraphGenerator;
use pyo3::prelude::*;
use pyo3::types::PyDict;
use std::collections::HashMap;

/// Build a PyGraph from a Rust Graph returned by a generator.
///
/// Converts string node keys ("0", "1", ...) to Python int keys so that
/// `G.nodes()` yields `[0, 1, 2, ...]` matching NetworkX.
fn report_to_pygraph(py: Python<'_>, graph: fnx_classes::Graph) -> PyResult<PyGraph> {
    let mut pg = PyGraph {
        inner: graph,
        node_key_map: HashMap::new(),
        node_py_attrs: HashMap::new(),
        edge_py_attrs: HashMap::new(),
        graph_attrs: PyDict::new(py).unbind(),
    };

    // Map string keys to Python int keys.
    for canonical in pg.inner.nodes_ordered() {
        if let Ok(i) = canonical.parse::<i64>() {
            pg.node_key_map.insert(
                canonical.to_owned(),
                i.into_pyobject(py).unwrap().into_any().unbind(),
            );
        }
        pg.node_py_attrs
            .insert(canonical.to_owned(), PyDict::new(py).unbind());
    }

    // Create edge attr dicts for all edges.
    for edge in pg.inner.edges_ordered() {
        let ek = PyGraph::edge_key(&edge.left, &edge.right);
        pg.edge_py_attrs
            .entry(ek)
            .or_insert_with(|| PyDict::new(py).unbind());
    }

    Ok(pg)
}

// ---------------------------------------------------------------------------
// Generator functions
// ---------------------------------------------------------------------------

/// Return the empty graph with ``n`` nodes and zero edges.
///
/// Parameters
/// ----------
/// n : int, optional
///     Number of nodes (default 0).
#[pyfunction]
#[pyo3(signature = (n=0))]
pub fn empty_graph(py: Python<'_>, n: usize) -> PyResult<PyGraph> {
    let mut gg = GraphGenerator::strict();
    let report = gg
        .empty_graph(n)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(format!("{e:?}")))?;
    report_to_pygraph(py, report.graph)
}

/// Return a path graph with ``n`` nodes: 0-1-2-...(n-1).
#[pyfunction]
pub fn path_graph(py: Python<'_>, n: usize) -> PyResult<PyGraph> {
    let mut gg = GraphGenerator::strict();
    let report = gg
        .path_graph(n)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(format!("{e:?}")))?;
    report_to_pygraph(py, report.graph)
}

/// Return a cycle graph with ``n`` nodes: 0-1-2-...(n-1)-0.
#[pyfunction]
pub fn cycle_graph(py: Python<'_>, n: usize) -> PyResult<PyGraph> {
    let mut gg = GraphGenerator::strict();
    let report = gg
        .cycle_graph(n)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(format!("{e:?}")))?;
    report_to_pygraph(py, report.graph)
}

/// Return a star graph with ``n`` outer nodes (n+1 nodes total).
///
/// Hub is node 0, spokes are 1..n.
#[pyfunction]
pub fn star_graph(py: Python<'_>, n: usize) -> PyResult<PyGraph> {
    let mut gg = GraphGenerator::strict();
    let report = gg
        .star_graph(n)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(format!("{e:?}")))?;
    report_to_pygraph(py, report.graph)
}

/// Return the complete graph K_n with ``n`` nodes.
#[pyfunction]
pub fn complete_graph(py: Python<'_>, n: usize) -> PyResult<PyGraph> {
    let mut gg = GraphGenerator::strict();
    let report = gg
        .complete_graph(n)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(format!("{e:?}")))?;
    report_to_pygraph(py, report.graph)
}

/// Return a random graph using the Erdős-Rényi G(n,p) model.
///
/// Each possible edge is included independently with probability ``p``.
///
/// Parameters
/// ----------
/// n : int
///     Number of nodes.
/// p : float
///     Probability of edge creation.
/// seed : int
///     Seed for the random number generator (deterministic output).
///
/// Notes
/// -----
/// The RNG differs from NetworkX, so graphs with the same seed will
/// differ between FrankenNetworkX and NetworkX.
#[pyfunction]
pub fn gnp_random_graph(py: Python<'_>, n: usize, p: f64, seed: u64) -> PyResult<PyGraph> {
    let mut gg = GraphGenerator::strict();
    let report = gg
        .gnp_random_graph(n, p, seed)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(format!("{e:?}")))?;
    report_to_pygraph(py, report.graph)
}

/// Return a Watts-Strogatz small-world graph.
///
/// Parameters
/// ----------
/// n : int
///     Number of nodes.
/// k : int
///     Each node is joined with its ``k`` nearest neighbors in a ring
///     topology.  Must be even.
/// p : float
///     Probability of rewiring each edge.
/// seed : int
///     Seed for the random number generator.
#[pyfunction]
pub fn watts_strogatz_graph(py: Python<'_>, n: usize, k: usize, p: f64, seed: u64) -> PyResult<PyGraph> {
    let mut gg = GraphGenerator::strict();
    let report = gg
        .watts_strogatz_graph(n, k, p, seed)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(format!("{e:?}")))?;
    report_to_pygraph(py, report.graph)
}

/// Return a random graph using Barabasi-Albert preferential attachment.
///
/// Parameters
/// ----------
/// n : int
///     Number of nodes.
/// m : int
///     Number of edges to attach from a new node to existing nodes.
/// seed : int
///     Seed for the random number generator.
#[pyfunction]
pub fn barabasi_albert_graph(py: Python<'_>, n: usize, m: usize, seed: u64) -> PyResult<PyGraph> {
    let mut gg = GraphGenerator::strict();
    let report = gg
        .barabasi_albert_graph(n, m, seed)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(format!("{e:?}")))?;
    report_to_pygraph(py, report.graph)
}

// ---------------------------------------------------------------------------
// Registration
// ---------------------------------------------------------------------------

pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(empty_graph, m)?)?;
    m.add_function(wrap_pyfunction!(path_graph, m)?)?;
    m.add_function(wrap_pyfunction!(cycle_graph, m)?)?;
    m.add_function(wrap_pyfunction!(star_graph, m)?)?;
    m.add_function(wrap_pyfunction!(complete_graph, m)?)?;
    m.add_function(wrap_pyfunction!(gnp_random_graph, m)?)?;
    m.add_function(wrap_pyfunction!(watts_strogatz_graph, m)?)?;
    m.add_function(wrap_pyfunction!(barabasi_albert_graph, m)?)?;
    Ok(())
}
