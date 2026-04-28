//! Structure-aware fuzzer for cycle-related algorithms.
//!
//! Tests simple_cycles, find_cycle, cycle_basis, and Eulerian path algorithms
//! on valid-but-pathological graph structures.

#![no_main]

mod arbitrary_graph;

use arbitrary::Arbitrary;
use arbitrary_graph::{ArbitraryDiGraph, ArbitraryGraph};
use libfuzzer_sys::fuzz_target;

/// A small directed graph for cycle enumeration (can be exponential).
/// Limited to 12 nodes to avoid combinatorial explosion.
#[derive(Debug, Clone)]
pub struct ArbitrarySmallDiGraph {
    pub graph: fnx_classes::digraph::DiGraph,
    pub nodes: Vec<String>,
}

impl<'a> Arbitrary<'a> for ArbitrarySmallDiGraph {
    fn arbitrary(u: &mut arbitrary::Unstructured<'a>) -> arbitrary::Result<Self> {
        use fnx_runtime::CompatibilityMode;

        let mode = if u.arbitrary()? {
            CompatibilityMode::Strict
        } else {
            CompatibilityMode::Hardened
        };

        let mut graph = fnx_classes::digraph::DiGraph::new(mode);
        let node_count: usize = u.int_in_range(0..=12)?;
        let mut nodes = Vec::with_capacity(node_count);

        for i in 0..node_count {
            let name = format!("n{i}");
            graph.add_node(&name);
            nodes.push(name);
        }

        // Generate edges - allow self-loops for cycle detection
        if node_count > 0 {
            let edge_density: u8 = u.arbitrary()?;
            let target_edges = (node_count * (edge_density as usize % 8)) / 2;

            for _ in 0..target_edges {
                if u.is_empty() {
                    break;
                }
                let src_idx: usize = u.int_in_range(0..=node_count - 1)?;
                let dst_idx: usize = u.int_in_range(0..=node_count - 1)?;
                let _ = graph.add_edge(&nodes[src_idx], &nodes[dst_idx]);
            }
        }

        Ok(Self { graph, nodes })
    }
}

#[derive(Debug, Arbitrary)]
enum CycleInput {
    /// Enumerate all simple cycles (small digraph to avoid exponential blowup).
    SimpleCycles(ArbitrarySmallDiGraph),
    /// Find a single cycle in a directed graph.
    FindCycleDirected(ArbitraryDiGraph),
    /// Find a single cycle in an undirected graph.
    FindCycleUndirected(ArbitraryGraph),
    /// Compute cycle basis of undirected graph.
    CycleBasis(ArbitraryGraph),
    /// Check if graph has Eulerian path.
    HasEulerianPath(ArbitraryGraph),
    /// Check if graph is Eulerian.
    IsEulerian(ArbitraryGraph),
    /// Check if graph is semi-Eulerian.
    IsSemiEulerian(ArbitraryGraph),
}

fuzz_target!(|input: CycleInput| {
    match input {
        CycleInput::SimpleCycles(ag) => {
            // Limit iteration to avoid combinatorial explosion
            let cycles = fnx_algorithms::simple_cycles(&ag.graph);
            for (i, _cycle) in cycles.into_iter().enumerate() {
                if i >= 1000 {
                    break;
                }
            }
        }
        CycleInput::FindCycleDirected(ag) => {
            let _ = fnx_algorithms::find_cycle_directed(&ag.graph);
        }
        CycleInput::FindCycleUndirected(ag) => {
            let _ = fnx_algorithms::find_cycle_undirected(&ag.graph);
        }
        CycleInput::CycleBasis(ag) => {
            let _ = fnx_algorithms::cycle_basis(&ag.graph, None);
        }
        CycleInput::HasEulerianPath(ag) => {
            let _ = fnx_algorithms::has_eulerian_path(&ag.graph);
        }
        CycleInput::IsEulerian(ag) => {
            let _ = fnx_algorithms::is_eulerian(&ag.graph);
        }
        CycleInput::IsSemiEulerian(ag) => {
            let _ = fnx_algorithms::is_semieulerian(&ag.graph);
        }
    }
});
