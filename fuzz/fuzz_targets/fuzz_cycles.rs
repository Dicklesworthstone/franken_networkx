//! Structure-aware fuzzer for cycle-related algorithms.
//!
//! Tests simple_cycles, find_cycle, cycle_basis, and Eulerian path algorithms
//! on valid-but-pathological graph structures.

#![no_main]

mod arbitrary_graph;

use arbitrary::Arbitrary;
use arbitrary_graph::{ArbitraryDiGraph, ArbitraryGraph};
use libfuzzer_sys::fuzz_target;
use std::collections::HashSet;

/// A small directed graph for eager cycle enumeration.
///
/// `simple_cycles` returns a fully materialized `Vec`, so the fuzzer must bound
/// the generated graph before calling it rather than trying to stop iteration
/// after the call has already enumerated every cycle.
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
        let node_count: usize = u.int_in_range(0..=8)?;
        let mut nodes = Vec::with_capacity(node_count);

        for i in 0..node_count {
            let name = format!("n{i}");
            graph.add_node(&name);
            nodes.push(name);
        }

        // Generate edges - allow self-loops for cycle detection
        if node_count > 0 {
            let edge_density: u8 = u.arbitrary()?;
            let target_edges = ((node_count * (edge_density as usize % 5)) / 2).min(16);

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
            let cycles = fnx_algorithms::simple_cycles(&ag.graph);
            for cycle in &cycles {
                // Empty cycle is meaningless.
                assert!(
                    !cycle.is_empty(),
                    "simple_cycles emitted empty cycle"
                );
                // Every consecutive pair must be a directed edge of G.
                // simple_cycles convention: cycle is given as a list
                // [v_0, v_1, ..., v_{k-1}] where (v_i, v_{i+1}) and
                // (v_{k-1}, v_0) are edges of G.
                for i in 0..cycle.len() {
                    let u = &cycle[i];
                    let v = &cycle[(i + 1) % cycle.len()];
                    assert!(
                        ag.graph.has_edge(u, v),
                        "simple_cycles emitted non-edge {} -> {}",
                        u, v
                    );
                }
                // No node repeats within the cycle (simple cycles are
                // simple by definition — no repeated vertices except
                // implicit wrap-around).
                let mut seen: HashSet<&str> = HashSet::new();
                for n in cycle {
                    assert!(
                        ag.graph.has_node(n),
                        "simple_cycles emitted foreign node {}",
                        n
                    );
                    assert!(
                        seen.insert(n.as_str()),
                        "simple_cycles emitted non-simple cycle (repeated node {})",
                        n
                    );
                }
            }
        }
        CycleInput::FindCycleDirected(ag) => {
            if let Some(cycle) = fnx_algorithms::find_cycle_directed(&ag.graph) {
                assert!(
                    !cycle.is_empty(),
                    "find_cycle_directed returned empty cycle"
                );
                // br-r37-c1-4q1rb: find_cycle_directed returns a NODE
                // list that closes the cycle by DUPLICATING the start
                // node at the end (e.g. triangle 0->1->2->0 yields
                // ["0","1","2","0"]).  Iterate consecutive pairs
                // without wrap; wrapping checks has_edge(start, start)
                // and triggers false-positive selfloop assertions on
                // graphs that arbitrary_graph.rs is documented to
                // skip selfloops in.
                for i in 0..cycle.len().saturating_sub(1) {
                    let u = &cycle[i];
                    let v = &cycle[i + 1];
                    assert!(
                        ag.graph.has_edge(u, v),
                        "find_cycle_directed emitted non-edge {} -> {}",
                        u, v
                    );
                }
                for n in &cycle {
                    assert!(
                        ag.graph.has_node(n),
                        "find_cycle_directed emitted foreign node {}",
                        n
                    );
                }
            }
        }
        CycleInput::FindCycleUndirected(ag) => {
            if let Some(cycle) = fnx_algorithms::find_cycle_undirected(&ag.graph) {
                assert!(
                    !cycle.is_empty(),
                    "find_cycle_undirected returned empty cycle"
                );
                // br-r37-c1-4q1rb: see find_cycle_directed above —
                // cycle list closes via duplicated start node.
                for i in 0..cycle.len().saturating_sub(1) {
                    let u = &cycle[i];
                    let v = &cycle[i + 1];
                    assert!(
                        ag.graph.has_edge(u, v),
                        "find_cycle_undirected emitted non-edge {} -- {}",
                        u, v
                    );
                }
            }
        }
        CycleInput::CycleBasis(ag) => {
            let result = fnx_algorithms::cycle_basis(&ag.graph, None);
            for cycle in &result.cycles {
                // Each cycle in the basis is a simple cycle of G; node
                // membership and adjacency between consecutive members
                // must hold.
                if cycle.is_empty() {
                    continue;
                }
                for n in cycle {
                    assert!(
                        ag.graph.has_node(n),
                        "cycle_basis emitted foreign node {}",
                        n
                    );
                }
                for i in 0..cycle.len() {
                    let u = &cycle[i];
                    let v = &cycle[(i + 1) % cycle.len()];
                    assert!(
                        ag.graph.has_edge(u, v),
                        "cycle_basis emitted non-edge {} -- {}",
                        u, v
                    );
                }
            }
        }
        CycleInput::HasEulerianPath(ag) => {
            // br-r37-c1-eol4n: is_semieulerian is NOT an alias of
            // has_eulerian_path — it specifically excludes Eulerian
            // circuits.  The mathematical invariant matching nx and
            // the fnx docstring is
            //     is_semieulerian == has_eulerian_path AND NOT is_eulerian
            // (semi-Eulerian = has Eulerian path but not Eulerian
            // circuit, i.e. exactly two odd-degree nodes).
            let has = fnx_algorithms::has_eulerian_path(&ag.graph).has_eulerian_path;
            let semi = fnx_algorithms::is_semieulerian(&ag.graph).is_semieulerian;
            let is_e = fnx_algorithms::is_eulerian(&ag.graph).is_eulerian;
            assert_eq!(
                semi,
                has && !is_e,
                "is_semieulerian ({}) != has_eulerian_path ({}) && !is_eulerian ({}) — \
                 the documented semi-Eulerian invariant",
                semi,
                has,
                is_e
            );
        }
        CycleInput::IsEulerian(ag) => {
            // Eulerian circuit implies an Eulerian path (the circuit IS
            // such a path) AND implies NOT semi-Eulerian (semi requires
            // exactly two odd-degree nodes; Eulerian needs zero).
            let is_e = fnx_algorithms::is_eulerian(&ag.graph).is_eulerian;
            if is_e {
                let has = fnx_algorithms::has_eulerian_path(&ag.graph).has_eulerian_path;
                let semi = fnx_algorithms::is_semieulerian(&ag.graph).is_semieulerian;
                assert!(
                    has,
                    "is_eulerian=true but has_eulerian_path=false (circuit implies path)"
                );
                assert!(
                    !semi,
                    "is_eulerian=true but is_semieulerian=true (Eulerian circuit is *not* semi-Eulerian)"
                );
            }
        }
        CycleInput::IsSemiEulerian(ag) => {
            // br-r37-c1-eol4n: same invariant as HasEulerianPath above.
            let semi = fnx_algorithms::is_semieulerian(&ag.graph).is_semieulerian;
            let has = fnx_algorithms::has_eulerian_path(&ag.graph).has_eulerian_path;
            let is_e = fnx_algorithms::is_eulerian(&ag.graph).is_eulerian;
            assert_eq!(
                semi,
                has && !is_e,
                "is_semieulerian ({}) != has_eulerian_path ({}) && !is_eulerian ({})",
                semi,
                has,
                is_e
            );
        }
    }
});
