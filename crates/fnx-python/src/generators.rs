//! Python bindings for graph generator functions.
//!
//! Wraps `fnx_generators::GraphGenerator` methods as module-level functions.
//! Node labels are Python integers (0, 1, 2, ...) matching NetworkX convention.

use crate::digraph::{PyDiGraph, PyMultiDiGraph};
use crate::{PyGraph, unwrap_infallible};
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
                unwrap_infallible(i.into_pyobject(py)).into_any().unbind(),
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

fn report_to_pydigraph(
    py: Python<'_>,
    graph: fnx_classes::digraph::DiGraph,
) -> PyResult<PyDiGraph> {
    let mut pg = PyDiGraph {
        inner: graph,
        node_key_map: HashMap::new(),
        node_py_attrs: HashMap::new(),
        edge_py_attrs: HashMap::new(),
        graph_attrs: PyDict::new(py).unbind(),
    };

    for canonical in pg.inner.nodes_ordered() {
        if let Ok(i) = canonical.parse::<i64>() {
            pg.node_key_map.insert(
                canonical.to_owned(),
                unwrap_infallible(i.into_pyobject(py)).into_any().unbind(),
            );
        }
        pg.node_py_attrs
            .insert(canonical.to_owned(), PyDict::new(py).unbind());
    }

    for source in pg.inner.nodes_ordered() {
        for target in pg.inner.successors(source).unwrap_or_default() {
            pg.edge_py_attrs
                .entry((source.to_owned(), target.to_owned()))
                .or_insert_with(|| PyDict::new(py).unbind());
        }
    }

    Ok(pg)
}

fn report_to_pymultidigraph(
    py: Python<'_>,
    graph: fnx_classes::digraph::MultiDiGraph,
) -> PyResult<PyMultiDiGraph> {
    let mut pg = PyMultiDiGraph {
        inner: graph,
        node_key_map: HashMap::new(),
        node_py_attrs: HashMap::new(),
        edge_py_attrs: HashMap::new(),
        graph_attrs: PyDict::new(py).unbind(),
    };

    for canonical in pg.inner.nodes_ordered() {
        if let Ok(i) = canonical.parse::<i64>() {
            pg.node_key_map.insert(
                canonical.to_owned(),
                unwrap_infallible(i.into_pyobject(py)).into_any().unbind(),
            );
        }
        pg.node_py_attrs
            .insert(canonical.to_owned(), PyDict::new(py).unbind());
    }

    for source in pg.inner.nodes_ordered() {
        for target in pg.inner.successors(source).unwrap_or_default() {
            for key in pg.inner.edge_keys(source, target).unwrap_or_default() {
                pg.edge_py_attrs
                    .entry((source.to_owned(), target.to_owned(), key))
                    .or_insert_with(|| PyDict::new(py).unbind());
            }
        }
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
///     topology. If ``k`` is odd, this matches NetworkX by using ``k - 1``
///     nearest neighbors.
/// p : float
///     Probability of rewiring each edge.
/// seed : int
///     Seed for the random number generator.
#[pyfunction]
pub fn watts_strogatz_graph(
    py: Python<'_>,
    n: usize,
    k: usize,
    p: f64,
    seed: u64,
) -> PyResult<PyGraph> {
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

/// Return an Erdős–Rényi random graph (alias for ``gnp_random_graph``).
#[pyfunction]
pub fn erdos_renyi_graph(py: Python<'_>, n: usize, p: f64, seed: u64) -> PyResult<PyGraph> {
    gnp_random_graph(py, n, p, seed)
}

/// Return a Newman-Watts-Strogatz small-world graph.
///
/// Unlike ``watts_strogatz_graph``, shortcut edges are added without removing
/// the original ring edges, guaranteeing the graph stays connected.
#[pyfunction]
pub fn newman_watts_strogatz_graph(
    py: Python<'_>,
    n: usize,
    k: usize,
    p: f64,
    seed: u64,
) -> PyResult<PyGraph> {
    let mut gg = GraphGenerator::strict();
    let report = gg
        .newman_watts_strogatz_graph(n, k, p, seed)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(format!("{e:?}")))?;
    report_to_pygraph(py, report.graph)
}

/// Return a connected Watts-Strogatz small-world graph.
///
/// Repeatedly generates Watts-Strogatz graphs until a connected one is found.
#[pyfunction(signature = (n, k, p, tries=100, seed=0))]
pub fn connected_watts_strogatz_graph(
    py: Python<'_>,
    n: usize,
    k: usize,
    p: f64,
    tries: usize,
    seed: u64,
) -> PyResult<PyGraph> {
    let mut gg = GraphGenerator::strict();
    let report = gg
        .connected_watts_strogatz_graph(n, k, p, tries, seed)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(format!("{e:?}")))?;
    report_to_pygraph(py, report.graph)
}

/// Return a random d-regular graph on n nodes.
///
/// The resulting graph has exactly ``n`` nodes, each with degree ``d``.
/// Requires ``n * d`` to be even and ``d < n``.
#[pyfunction]
pub fn random_regular_graph(py: Python<'_>, d: usize, n: usize, seed: u64) -> PyResult<PyGraph> {
    let mut gg = GraphGenerator::strict();
    let report = gg
        .random_regular_graph(n, d, seed)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(format!("{e:?}")))?;
    report_to_pygraph(py, report.graph)
}

/// Return a Holme-Kim powerlaw cluster graph.
///
/// Like Barabási-Albert with an additional triangle-closing step.
#[pyfunction]
pub fn powerlaw_cluster_graph(
    py: Python<'_>,
    n: usize,
    m: usize,
    p: f64,
    seed: u64,
) -> PyResult<PyGraph> {
    let mut gg = GraphGenerator::strict();
    let report = gg
        .powerlaw_cluster_graph(n, m, p, seed)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(format!("{e:?}")))?;
    report_to_pygraph(py, report.graph)
}

/// Return a fast G(n,p) random graph (Batagelj-Brandes O(n+m) algorithm).
#[pyfunction]
#[pyo3(signature = (n, p, seed=None, directed=false, create_using=None))]
pub fn fast_gnp_random_graph(
    py: Python<'_>,
    n: usize,
    p: f64,
    seed: Option<u64>,
    directed: bool,
    create_using: Option<&Bound<'_, PyAny>>,
) -> PyResult<PyGraph> {
    let _ = create_using; // accepted for API compat, ignored
    let actual_seed = seed.unwrap_or(0);
    let mut gg = GraphGenerator::strict();
    let report = gg
        .fast_gnp_random_graph(n, p, actual_seed, directed)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(format!("{e:?}")))?;
    report_to_pygraph(py, report.graph)
}

/// Return a growing network digraph (GN model).
#[pyfunction]
#[pyo3(signature = (n, seed=None, create_using=None))]
pub fn gn_graph(
    py: Python<'_>,
    n: usize,
    seed: Option<u64>,
    create_using: Option<&Bound<'_, PyAny>>,
) -> PyResult<Py<PyDiGraph>> {
    let _ = create_using;
    let actual_seed = seed.unwrap_or(0);
    let mut gg = GraphGenerator::strict();
    let report = gg
        .gn_graph(n, actual_seed)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(format!("{e:?}")))?;
    Py::new(py, report_to_pydigraph(py, report.graph)?)
}

/// Return a growing network with redirection digraph (GNR model).
#[pyfunction]
#[pyo3(signature = (n, p, seed=None, create_using=None))]
pub fn gnr_graph(
    py: Python<'_>,
    n: usize,
    p: f64,
    seed: Option<u64>,
    create_using: Option<&Bound<'_, PyAny>>,
) -> PyResult<Py<PyDiGraph>> {
    let _ = create_using;
    let actual_seed = seed.unwrap_or(0);
    let mut gg = GraphGenerator::strict();
    let report = gg
        .gnr_graph(n, p, actual_seed)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(format!("{e:?}")))?;
    Py::new(py, report_to_pydigraph(py, report.graph)?)
}

/// Return a growing network with copying digraph (GNC model).
#[pyfunction]
#[pyo3(signature = (n, seed=None, create_using=None))]
pub fn gnc_graph(
    py: Python<'_>,
    n: usize,
    seed: Option<u64>,
    create_using: Option<&Bound<'_, PyAny>>,
) -> PyResult<Py<PyDiGraph>> {
    let _ = create_using;
    let actual_seed = seed.unwrap_or(0);
    let mut gg = GraphGenerator::strict();
    let report = gg
        .gnc_graph(n, actual_seed)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(format!("{e:?}")))?;
    Py::new(py, report_to_pydigraph(py, report.graph)?)
}

/// Return a scale-free directed graph.
#[pyfunction]
#[pyo3(signature = (n, alpha=0.41, beta=0.54, gamma=0.05, delta_in=0.2, delta_out=0.0, seed=None, initial_graph=None))]
pub fn scale_free_graph(
    py: Python<'_>,
    n: usize,
    alpha: f64,
    beta: f64,
    gamma: f64,
    delta_in: f64,
    delta_out: f64,
    seed: Option<u64>,
    initial_graph: Option<&Bound<'_, PyAny>>,
) -> PyResult<Py<PyMultiDiGraph>> {
    let initial = match initial_graph {
        None => None,
        Some(graph) => Some(graph.extract::<PyRef<'_, PyMultiDiGraph>>()?.inner.clone()),
    };
    let actual_seed = seed.unwrap_or(0);
    let mut gg = GraphGenerator::strict();
    let report = gg
        .scale_free_graph(
            n,
            alpha,
            beta,
            gamma,
            delta_in,
            delta_out,
            initial,
            actual_seed,
        )
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(format!("{e:?}")))?;
    Py::new(py, report_to_pymultidigraph(py, report.graph)?)
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
    m.add_function(wrap_pyfunction!(erdos_renyi_graph, m)?)?;
    m.add_function(wrap_pyfunction!(newman_watts_strogatz_graph, m)?)?;
    m.add_function(wrap_pyfunction!(connected_watts_strogatz_graph, m)?)?;
    m.add_function(wrap_pyfunction!(random_regular_graph, m)?)?;
    m.add_function(wrap_pyfunction!(powerlaw_cluster_graph, m)?)?;
    m.add_function(wrap_pyfunction!(fast_gnp_random_graph, m)?)?;
    m.add_function(wrap_pyfunction!(gn_graph, m)?)?;
    m.add_function(wrap_pyfunction!(gnr_graph, m)?)?;
    m.add_function(wrap_pyfunction!(gnc_graph, m)?)?;
    m.add_function(wrap_pyfunction!(scale_free_graph, m)?)?;
    Ok(())
}
