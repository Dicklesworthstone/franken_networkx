//! Structure-aware fuzzer for clique algorithms.
//!
//! Tests max_clique, enumerate_all_cliques, graph_clique_number, and related
//! algorithms on valid-but-pathological graph structures.

#![no_main]

mod arbitrary_graph;

use arbitrary::Arbitrary;
use arbitrary_graph::ArbitraryGraph;
use libfuzzer_sys::fuzz_target;

/// A small graph for clique enumeration (exponential in worst case).
/// Limited to 16 nodes to avoid combinatorial explosion.
#[derive(Debug, Clone)]
pub struct ArbitrarySmallGraph {
    pub graph: fnx_classes::Graph,
    pub nodes: Vec<String>,
}

impl<'a> Arbitrary<'a> for ArbitrarySmallGraph {
    fn arbitrary(u: &mut arbitrary::Unstructured<'a>) -> arbitrary::Result<Self> {
        use fnx_runtime::CompatibilityMode;

        let mode = if u.arbitrary()? {
            CompatibilityMode::Strict
        } else {
            CompatibilityMode::Hardened
        };

        let mut graph = fnx_classes::Graph::new(mode);
        let node_count: usize = u.int_in_range(0..=16)?;
        let mut nodes = Vec::with_capacity(node_count);

        for i in 0..node_count {
            let name = format!("n{i}");
            graph.add_node(&name);
            nodes.push(name);
        }

        // Generate edges
        if node_count > 1 {
            let edge_density: u8 = u.arbitrary()?;
            let target_edges = (node_count * (edge_density as usize % 6)) / 2;

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

#[derive(Debug, Arbitrary)]
enum CliqueInput {
    /// Enumerate all cliques (small graph to avoid exponential blowup).
    EnumerateAllCliques(ArbitrarySmallGraph),
    /// Find maximum clique approximation.
    MaxClique(ArbitraryGraph),
    /// Find max weight clique.
    MaxWeightClique(ArbitraryGraph),
    /// Get graph clique number.
    GraphCliqueNumber(ArbitraryGraph),
    /// Get large clique size approximation.
    LargeCliqueSize(ArbitraryGraph),
    /// Clique removal.
    CliqueRemoval(ArbitraryGraph),
}

fuzz_target!(|input: CliqueInput| {
    match input {
        CliqueInput::EnumerateAllCliques(ag) => {
            // Limit iteration to avoid combinatorial explosion
            let cliques = fnx_algorithms::enumerate_all_cliques(&ag.graph);
            for (i, _clique) in cliques.into_iter().enumerate() {
                if i >= 1000 {
                    break;
                }
            }
        }
        CliqueInput::MaxClique(ag) => {
            let _ = fnx_algorithms::max_clique_approx(&ag.graph);
        }
        CliqueInput::MaxWeightClique(ag) => {
            let _ = fnx_algorithms::max_weight_clique(&ag.graph, "weight");
        }
        CliqueInput::GraphCliqueNumber(ag) => {
            let _ = fnx_algorithms::graph_clique_number(&ag.graph);
        }
        CliqueInput::LargeCliqueSize(ag) => {
            let _ = fnx_algorithms::max_clique_approx(&ag.graph).len();
        }
        CliqueInput::CliqueRemoval(ag) => {
            let _ = fnx_algorithms::clique_removal(&ag.graph);
        }
    }
});
