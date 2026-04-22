//! Structure-aware fuzzer for bipartite algorithms.
//!
//! Tests is_bipartite, bipartite_sets, and color on valid-but-pathological
//! graph structures including both bipartite and non-bipartite graphs.

#![no_main]

mod arbitrary_graph;

use arbitrary::Arbitrary;
use arbitrary_graph::ArbitraryGraph;
use libfuzzer_sys::fuzz_target;

/// A bipartite graph generated via `Arbitrary`.
///
/// Nodes are split into two sets (even/odd indices) with edges only between sets.
#[derive(Debug, Clone)]
pub struct ArbitraryBipartiteGraph {
    pub graph: fnx_classes::Graph,
    pub nodes: Vec<String>,
    pub top_nodes: Vec<String>,
    pub bottom_nodes: Vec<String>,
}

impl<'a> Arbitrary<'a> for ArbitraryBipartiteGraph {
    fn arbitrary(u: &mut arbitrary::Unstructured<'a>) -> arbitrary::Result<Self> {
        use fnx_runtime::CompatibilityMode;

        let mode = if u.arbitrary()? {
            CompatibilityMode::Strict
        } else {
            CompatibilityMode::Hardened
        };

        let mut graph = fnx_classes::Graph::new(mode);
        let node_count: usize = u.int_in_range(0..=32)?;
        let mut nodes = Vec::with_capacity(node_count);
        let mut top_nodes = Vec::new();
        let mut bottom_nodes = Vec::new();

        // Generate nodes, splitting into two partitions
        for i in 0..node_count {
            let name = format!("n{i}");
            graph.add_node(&name);
            nodes.push(name.clone());
            if i % 2 == 0 {
                top_nodes.push(name);
            } else {
                bottom_nodes.push(name);
            }
        }

        // Generate edges only between partitions (ensures bipartite)
        if !top_nodes.is_empty() && !bottom_nodes.is_empty() {
            let edge_density: u8 = u.arbitrary()?;
            let target_edges = (node_count * (edge_density as usize % 4)) / 2;

            for _ in 0..target_edges {
                if u.is_empty() {
                    break;
                }
                let top_idx: usize = u.int_in_range(0..=top_nodes.len() - 1)?;
                let bottom_idx: usize = u.int_in_range(0..=bottom_nodes.len() - 1)?;
                let _ = graph.add_edge(&top_nodes[top_idx], &bottom_nodes[bottom_idx]);
            }
        }

        Ok(Self {
            graph,
            nodes,
            top_nodes,
            bottom_nodes,
        })
    }
}

#[derive(Debug, Arbitrary)]
enum BipartiteInput {
    /// Check if arbitrary graph is bipartite.
    IsBipartiteArbitrary(ArbitraryGraph),
    /// Check if known-bipartite graph is bipartite.
    IsBipartiteKnown(ArbitraryBipartiteGraph),
    /// Get bipartite sets from arbitrary graph.
    BipartiteSetsArbitrary(ArbitraryGraph),
    /// Get bipartite sets from known-bipartite graph.
    BipartiteSetsKnown(ArbitraryBipartiteGraph),
    /// Color arbitrary graph (may fail for non-bipartite).
    ColorArbitrary(ArbitraryGraph),
    /// Color known-bipartite graph.
    ColorKnown(ArbitraryBipartiteGraph),
}

fuzz_target!(|input: BipartiteInput| {
    match input {
        BipartiteInput::IsBipartiteArbitrary(ag) => {
            let _ = fnx_algorithms::is_bipartite(&ag.graph);
        }
        BipartiteInput::IsBipartiteKnown(bg) => {
            // Known bipartite graph should always return true
            let result = fnx_algorithms::is_bipartite(&bg.graph);
            debug_assert!(result, "Known bipartite graph should be bipartite");
        }
        BipartiteInput::BipartiteSetsArbitrary(ag) => {
            let _ = fnx_algorithms::bipartite_sets(&ag.graph);
        }
        BipartiteInput::BipartiteSetsKnown(bg) => {
            // Known bipartite graph should successfully return sets
            let _ = fnx_algorithms::bipartite_sets(&bg.graph);
        }
        BipartiteInput::ColorArbitrary(ag) => {
            // May return error for non-bipartite graphs
            let _ = fnx_algorithms::bipartite_color(&ag.graph);
        }
        BipartiteInput::ColorKnown(bg) => {
            // Known bipartite graph should successfully color
            let _ = fnx_algorithms::bipartite_color(&bg.graph);
        }
    }
});
