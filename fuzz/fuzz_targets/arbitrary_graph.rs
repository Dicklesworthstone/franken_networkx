//! Structure-aware graph generation for fuzzing algorithms.
//!
//! Provides `Arbitrary` implementations that generate valid-but-pathological
//! graph structures to exercise algorithm code paths that parser fuzzers
//! cannot reach.

use arbitrary::{Arbitrary, Unstructured};
use fnx_classes::digraph::{DiGraph, MultiDiGraph};
use fnx_classes::{Graph, MultiGraph};
use fnx_runtime::CompatibilityMode;
use std::collections::BTreeMap;

/// Maximum nodes to generate (controls fuzzer memory usage).
const MAX_NODES: usize = 64;

/// Maximum edges per node (controls graph density).
const MAX_EDGES_PER_NODE: usize = 8;

/// An undirected graph generated via `Arbitrary`.
#[derive(Debug, Clone)]
pub struct ArbitraryGraph {
    pub graph: Graph,
    /// Node names for algorithm source/target selection.
    pub nodes: Vec<String>,
}

/// A directed graph generated via `Arbitrary`.
#[derive(Debug, Clone)]
pub struct ArbitraryDiGraph {
    pub graph: DiGraph,
    /// Node names for algorithm source/target selection.
    pub nodes: Vec<String>,
}

/// Parameters for weighted graph generation.
#[derive(Debug, Clone, Arbitrary)]
pub struct WeightParams {
    /// Whether to include edge weights.
    pub weighted: bool,
    /// Whether to include negative weights (for Bellman-Ford testing).
    pub allow_negative: bool,
}

/// A weighted undirected graph with configurable weight distribution.
#[derive(Debug, Clone)]
pub struct ArbitraryWeightedGraph {
    pub graph: Graph,
    pub nodes: Vec<String>,
    pub weight_attr: String,
}

/// A weighted directed graph for flow/shortest-path testing.
#[derive(Debug, Clone)]
pub struct ArbitraryWeightedDiGraph {
    pub graph: DiGraph,
    pub nodes: Vec<String>,
    pub weight_attr: String,
}

/// A flow network (directed graph with capacity attributes).
#[derive(Debug, Clone)]
pub struct ArbitraryFlowNetwork {
    pub graph: DiGraph,
    pub nodes: Vec<String>,
    pub source: String,
    pub sink: String,
    pub capacity_attr: String,
}

/// An undirected multigraph generated via `Arbitrary`.
///
/// Unlike `ArbitraryGraph`, edges may be added multiple times between
/// the same endpoints. Keys are assigned by the underlying `MultiGraph`
/// via the fnx auto-key policy (matches networkx semantics).
#[derive(Debug, Clone)]
pub struct ArbitraryMultiGraph {
    pub graph: MultiGraph,
    /// Node names for algorithm source/target selection.
    pub nodes: Vec<String>,
}

/// A directed multigraph generated via `Arbitrary`.
///
/// Edges may be added multiple times between the same endpoints in a
/// given direction; the underlying `MultiDiGraph` assigns keys.
#[derive(Debug, Clone)]
pub struct ArbitraryMultiDiGraph {
    pub graph: MultiDiGraph,
    /// Node names for algorithm source/target selection.
    pub nodes: Vec<String>,
}

impl<'a> Arbitrary<'a> for ArbitraryGraph {
    fn arbitrary(u: &mut Unstructured<'a>) -> arbitrary::Result<Self> {
        let mode = if u.arbitrary()? {
            CompatibilityMode::Strict
        } else {
            CompatibilityMode::Hardened
        };

        let mut graph = Graph::new(mode);
        let node_count: usize = u.int_in_range(0..=MAX_NODES)?;
        let mut nodes = Vec::with_capacity(node_count);

        // Generate nodes
        for i in 0..node_count {
            let name = format!("n{i}");
            graph.add_node(&name);
            nodes.push(name);
        }

        // Generate edges (sparse to dense based on fuzzer input)
        if node_count > 0 {
            let edge_density: u8 = u.arbitrary()?;
            let target_edges = (node_count * (edge_density as usize % MAX_EDGES_PER_NODE)) / 2;

            for _ in 0..target_edges {
                if u.is_empty() {
                    break;
                }
                let src_idx: usize = u.int_in_range(0..=node_count - 1)?;
                let dst_idx: usize = u.int_in_range(0..=node_count - 1)?;
                if src_idx != dst_idx {
                    let _ = graph.add_edge(&nodes[src_idx], &nodes[dst_idx]);
                }
            }
        }

        Ok(Self { graph, nodes })
    }
}

impl<'a> Arbitrary<'a> for ArbitraryDiGraph {
    fn arbitrary(u: &mut Unstructured<'a>) -> arbitrary::Result<Self> {
        let mode = if u.arbitrary()? {
            CompatibilityMode::Strict
        } else {
            CompatibilityMode::Hardened
        };

        let mut graph = DiGraph::new(mode);
        let node_count: usize = u.int_in_range(0..=MAX_NODES)?;
        let mut nodes = Vec::with_capacity(node_count);

        // Generate nodes
        for i in 0..node_count {
            let name = format!("n{i}");
            graph.add_node(&name);
            nodes.push(name);
        }

        // Generate directed edges
        if node_count > 0 {
            let edge_density: u8 = u.arbitrary()?;
            let target_edges = (node_count * (edge_density as usize % MAX_EDGES_PER_NODE)) / 2;

            for _ in 0..target_edges {
                if u.is_empty() {
                    break;
                }
                let src_idx: usize = u.int_in_range(0..=node_count - 1)?;
                let dst_idx: usize = u.int_in_range(0..=node_count - 1)?;
                if src_idx != dst_idx {
                    let _ = graph.add_edge(&nodes[src_idx], &nodes[dst_idx]);
                }
            }
        }

        Ok(Self { graph, nodes })
    }
}

impl<'a> Arbitrary<'a> for ArbitraryWeightedGraph {
    fn arbitrary(u: &mut Unstructured<'a>) -> arbitrary::Result<Self> {
        let mode = if u.arbitrary()? {
            CompatibilityMode::Strict
        } else {
            CompatibilityMode::Hardened
        };

        let mut graph = Graph::new(mode);
        let node_count: usize = u.int_in_range(0..=MAX_NODES)?;
        let mut nodes = Vec::with_capacity(node_count);
        let weight_attr = "weight".to_string();

        // Generate nodes
        for i in 0..node_count {
            let name = format!("n{i}");
            graph.add_node(&name);
            nodes.push(name);
        }

        // Generate weighted edges
        if node_count > 0 {
            let edge_density: u8 = u.arbitrary()?;
            let target_edges = (node_count * (edge_density as usize % MAX_EDGES_PER_NODE)) / 2;
            let allow_negative: bool = u.arbitrary()?;

            for _ in 0..target_edges {
                if u.is_empty() {
                    break;
                }
                let src_idx: usize = u.int_in_range(0..=node_count - 1)?;
                let dst_idx: usize = u.int_in_range(0..=node_count - 1)?;
                if src_idx != dst_idx {
                    // Generate weight: mostly positive, occasionally negative or zero
                    let raw_weight: i16 = u.arbitrary()?;
                    let weight = if allow_negative {
                        f64::from(raw_weight) / 100.0
                    } else {
                        f64::from(raw_weight.unsigned_abs()) / 100.0 + 0.01
                    };

                    let mut attrs = BTreeMap::new();
                    attrs.insert(
                        weight_attr.clone(),
                        fnx_runtime::CgseValue::Float(weight),
                    );
                    let _ = graph.add_edge_with_attrs(&nodes[src_idx], &nodes[dst_idx], attrs);
                }
            }
        }

        Ok(Self {
            graph,
            nodes,
            weight_attr,
        })
    }
}

impl<'a> Arbitrary<'a> for ArbitraryWeightedDiGraph {
    fn arbitrary(u: &mut Unstructured<'a>) -> arbitrary::Result<Self> {
        let mode = if u.arbitrary()? {
            CompatibilityMode::Strict
        } else {
            CompatibilityMode::Hardened
        };

        let mut graph = DiGraph::new(mode);
        let node_count: usize = u.int_in_range(0..=MAX_NODES)?;
        let mut nodes = Vec::with_capacity(node_count);
        let weight_attr = "weight".to_string();

        // Generate nodes
        for i in 0..node_count {
            let name = format!("n{i}");
            graph.add_node(&name);
            nodes.push(name);
        }

        // Generate weighted directed edges
        if node_count > 0 {
            let edge_density: u8 = u.arbitrary()?;
            let target_edges = (node_count * (edge_density as usize % MAX_EDGES_PER_NODE)) / 2;
            let allow_negative: bool = u.arbitrary()?;

            for _ in 0..target_edges {
                if u.is_empty() {
                    break;
                }
                let src_idx: usize = u.int_in_range(0..=node_count - 1)?;
                let dst_idx: usize = u.int_in_range(0..=node_count - 1)?;
                if src_idx != dst_idx {
                    let raw_weight: i16 = u.arbitrary()?;
                    let weight = if allow_negative {
                        f64::from(raw_weight) / 100.0
                    } else {
                        f64::from(raw_weight.unsigned_abs()) / 100.0 + 0.01
                    };

                    let mut attrs = BTreeMap::new();
                    attrs.insert(
                        weight_attr.clone(),
                        fnx_runtime::CgseValue::Float(weight),
                    );
                    let _ = graph.add_edge_with_attrs(&nodes[src_idx], &nodes[dst_idx], attrs);
                }
            }
        }

        Ok(Self {
            graph,
            nodes,
            weight_attr,
        })
    }
}

impl<'a> Arbitrary<'a> for ArbitraryFlowNetwork {
    fn arbitrary(u: &mut Unstructured<'a>) -> arbitrary::Result<Self> {
        let mode = if u.arbitrary()? {
            CompatibilityMode::Strict
        } else {
            CompatibilityMode::Hardened
        };

        let mut graph = DiGraph::new(mode);
        // Flow networks need at least 2 nodes for source/sink
        let node_count: usize = u.int_in_range(2..=MAX_NODES)?;
        let mut nodes = Vec::with_capacity(node_count);
        let capacity_attr = "capacity".to_string();

        // Generate nodes
        for i in 0..node_count {
            let name = format!("n{i}");
            graph.add_node(&name);
            nodes.push(name);
        }

        // Source is first node, sink is last node
        let source = nodes[0].clone();
        let sink = nodes[node_count - 1].clone();

        // Generate edges with capacity
        let edge_density: u8 = u.arbitrary()?;
        let target_edges = (node_count * (edge_density as usize % MAX_EDGES_PER_NODE)) / 2;

        for _ in 0..target_edges {
            if u.is_empty() {
                break;
            }
            let src_idx: usize = u.int_in_range(0..=node_count - 1)?;
            let dst_idx: usize = u.int_in_range(0..=node_count - 1)?;
            if src_idx != dst_idx {
                // Capacity must be positive
                let capacity: u16 = u.arbitrary()?;
                let capacity = f64::from(capacity.max(1));

                let mut attrs = BTreeMap::new();
                attrs.insert(
                    capacity_attr.clone(),
                    fnx_runtime::CgseValue::Float(capacity),
                );
                let _ = graph.add_edge_with_attrs(&nodes[src_idx], &nodes[dst_idx], attrs);
            }
        }

        Ok(Self {
            graph,
            nodes,
            source,
            sink,
            capacity_attr,
        })
    }
}

/// An undirected flow network (undirected graph with capacity attributes).
#[derive(Debug, Clone)]
pub struct ArbitraryFlowNetworkUndirected {
    pub graph: Graph,
    pub nodes: Vec<String>,
    pub source: String,
    pub sink: String,
    pub capacity_attr: String,
}

impl<'a> Arbitrary<'a> for ArbitraryFlowNetworkUndirected {
    fn arbitrary(u: &mut Unstructured<'a>) -> arbitrary::Result<Self> {
        let mode = if u.arbitrary()? {
            CompatibilityMode::Strict
        } else {
            CompatibilityMode::Hardened
        };

        let mut graph = Graph::new(mode);
        // Flow networks need at least 2 nodes for source/sink
        let node_count: usize = u.int_in_range(2..=MAX_NODES)?;
        let mut nodes = Vec::with_capacity(node_count);
        let capacity_attr = "capacity".to_string();

        // Generate nodes
        for i in 0..node_count {
            let name = format!("n{i}");
            graph.add_node(&name);
            nodes.push(name);
        }

        // Source is first node, sink is last node
        let source = nodes[0].clone();
        let sink = nodes[node_count - 1].clone();

        // Generate edges with capacity
        let edge_density: u8 = u.arbitrary()?;
        let target_edges = (node_count * (edge_density as usize % MAX_EDGES_PER_NODE)) / 2;

        for _ in 0..target_edges {
            if u.is_empty() {
                break;
            }
            let src_idx: usize = u.int_in_range(0..=node_count - 1)?;
            let dst_idx: usize = u.int_in_range(0..=node_count - 1)?;
            if src_idx != dst_idx {
                // Capacity must be positive
                let capacity: u16 = u.arbitrary()?;
                let capacity = f64::from(capacity.max(1));

                let mut attrs = BTreeMap::new();
                attrs.insert(
                    capacity_attr.clone(),
                    fnx_runtime::CgseValue::Float(capacity),
                );
                let _ = graph.add_edge_with_attrs(&nodes[src_idx], &nodes[dst_idx], attrs);
            }
        }

        Ok(Self {
            graph,
            nodes,
            source,
            sink,
            capacity_attr,
        })
    }
}

impl<'a> Arbitrary<'a> for ArbitraryMultiGraph {
    fn arbitrary(u: &mut Unstructured<'a>) -> arbitrary::Result<Self> {
        let mode = if u.arbitrary()? {
            CompatibilityMode::Strict
        } else {
            CompatibilityMode::Hardened
        };

        let mut graph = MultiGraph::new(mode);
        let node_count: usize = u.int_in_range(0..=MAX_NODES)?;
        let mut nodes = Vec::with_capacity(node_count);

        for i in 0..node_count {
            let name = format!("n{i}");
            graph.add_node(&name);
            nodes.push(name);
        }

        if node_count > 0 {
            // Density and parallel-edge frequency are driven independently,
            // so single-edge, sparse-multi, and dense-multi topologies are
            // all reachable.
            let edge_density: u8 = u.arbitrary()?;
            let parallel_bias: u8 = u.arbitrary()?;
            let target_edges = (node_count * (edge_density as usize % MAX_EDGES_PER_NODE)) / 2;

            for _ in 0..target_edges {
                if u.is_empty() {
                    break;
                }
                let src_idx: usize = u.int_in_range(0..=node_count - 1)?;
                let dst_idx: usize = u.int_in_range(0..=node_count - 1)?;
                if src_idx == dst_idx {
                    continue;
                }
                // Add the edge once; with `parallel_bias` probability add
                // one or two additional parallel edges to exercise the
                // keyed-multiplicity code paths.
                let _ = graph.add_edge(&nodes[src_idx], &nodes[dst_idx]);
                if parallel_bias % 4 != 0 {
                    let _ = graph.add_edge(&nodes[src_idx], &nodes[dst_idx]);
                }
                if parallel_bias % 8 == 0 {
                    let _ = graph.add_edge(&nodes[src_idx], &nodes[dst_idx]);
                }
            }
        }

        Ok(Self { graph, nodes })
    }
}

impl<'a> Arbitrary<'a> for ArbitraryMultiDiGraph {
    fn arbitrary(u: &mut Unstructured<'a>) -> arbitrary::Result<Self> {
        let mode = if u.arbitrary()? {
            CompatibilityMode::Strict
        } else {
            CompatibilityMode::Hardened
        };

        let mut graph = MultiDiGraph::new(mode);
        let node_count: usize = u.int_in_range(0..=MAX_NODES)?;
        let mut nodes = Vec::with_capacity(node_count);

        for i in 0..node_count {
            let name = format!("n{i}");
            graph.add_node(&name);
            nodes.push(name);
        }

        if node_count > 0 {
            let edge_density: u8 = u.arbitrary()?;
            let parallel_bias: u8 = u.arbitrary()?;
            let target_edges = (node_count * (edge_density as usize % MAX_EDGES_PER_NODE)) / 2;

            for _ in 0..target_edges {
                if u.is_empty() {
                    break;
                }
                let src_idx: usize = u.int_in_range(0..=node_count - 1)?;
                let dst_idx: usize = u.int_in_range(0..=node_count - 1)?;
                if src_idx == dst_idx {
                    continue;
                }
                let _ = graph.add_edge(&nodes[src_idx], &nodes[dst_idx]);
                // Occasionally add the reverse direction to get (u, v) *and*
                // (v, u) pairs — the directed-multi code paths handle these
                // distinctly from parallel same-direction edges.
                if parallel_bias % 3 == 0 {
                    let _ = graph.add_edge(&nodes[dst_idx], &nodes[src_idx]);
                }
                if parallel_bias % 4 != 0 {
                    let _ = graph.add_edge(&nodes[src_idx], &nodes[dst_idx]);
                }
                if parallel_bias % 8 == 0 {
                    let _ = graph.add_edge(&nodes[src_idx], &nodes[dst_idx]);
                }
            }
        }

        Ok(Self { graph, nodes })
    }
}

/// Select a random node from a non-empty node list.
pub fn pick_node<'a>(nodes: &'a [String], u: &mut Unstructured<'_>) -> arbitrary::Result<&'a str> {
    if nodes.is_empty() {
        return Err(arbitrary::Error::NotEnoughData);
    }
    let idx: usize = u.int_in_range(0..=nodes.len() - 1)?;
    Ok(&nodes[idx])
}

/// Select two distinct random nodes from a node list.
pub fn pick_two_nodes<'a>(
    nodes: &'a [String],
    u: &mut Unstructured<'_>,
) -> arbitrary::Result<(&'a str, &'a str)> {
    if nodes.len() < 2 {
        return Err(arbitrary::Error::NotEnoughData);
    }
    let src_idx: usize = u.int_in_range(0..=nodes.len() - 1)?;
    let mut dst_idx: usize = u.int_in_range(0..=nodes.len() - 2)?;
    if dst_idx >= src_idx {
        dst_idx += 1;
    }
    Ok((&nodes[src_idx], &nodes[dst_idx]))
}
