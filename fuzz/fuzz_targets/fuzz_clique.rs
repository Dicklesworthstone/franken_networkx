//! Structure-aware fuzzer for clique algorithms.
//!
//! Tests max_clique, enumerate_all_cliques, graph_clique_number, and related
//! algorithms on valid-but-pathological graph structures.

#![no_main]

mod arbitrary_graph;

use arbitrary::Arbitrary;
use arbitrary_graph::ArbitraryGraph;
use fnx_classes::Graph;
use libfuzzer_sys::fuzz_target;
use std::collections::HashSet;

/// Verify that `clique` is a valid clique in `graph`: every node is in
/// G, no duplicates, and every pair of distinct nodes shares an edge.
fn assert_is_clique(graph: &Graph, clique: &[String], label: &str) {
    let mut seen: HashSet<&str> = HashSet::new();
    for n in clique {
        assert!(
            graph.has_node(n),
            "{}: clique contains foreign node {}",
            label,
            n
        );
        assert!(
            seen.insert(n.as_str()),
            "{}: clique has duplicate node {}",
            label,
            n
        );
    }
    // Pairwise adjacency. O(k^2) but k is small in practice.
    for (i, u) in clique.iter().enumerate() {
        for v in &clique[i + 1..] {
            assert!(
                graph.has_edge(u, v),
                "{}: clique members {} and {} are not adjacent",
                label,
                u,
                v
            );
        }
    }
}

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
            // Limit iteration to avoid combinatorial explosion. For each
            // sampled clique, verify it really is a clique.
            let cliques = fnx_algorithms::enumerate_all_cliques(&ag.graph);
            for (i, clique) in cliques.into_iter().enumerate() {
                if i >= 1000 {
                    break;
                }
                assert_is_clique(&ag.graph, &clique, "enumerate_all_cliques");
            }
        }
        CliqueInput::MaxClique(ag) => {
            let clique = fnx_algorithms::max_clique_approx(&ag.graph);
            assert_is_clique(&ag.graph, &clique, "max_clique_approx");
        }
        CliqueInput::MaxWeightClique(ag) => {
            let (clique, total_weight) =
                fnx_algorithms::max_weight_clique(&ag.graph, "weight");
            assert_is_clique(&ag.graph, &clique, "max_weight_clique");
            assert!(
                total_weight.is_finite(),
                "max_weight_clique total_weight {} is not finite",
                total_weight
            );
        }
        CliqueInput::GraphCliqueNumber(ag) => {
            let result = fnx_algorithms::graph_clique_number(&ag.graph);
            // The clique number is bounded by the graph's node count.
            assert!(
                result.clique_number <= ag.graph.node_count(),
                "clique_number {} exceeds node count {}",
                result.clique_number,
                ag.graph.node_count()
            );
            // Cross-check with max_clique_approx: approximation is a
            // lower bound on the true clique number, and the result of
            // max_clique_approx must itself be a valid clique whose
            // size is ≤ clique_number.
            let approx = fnx_algorithms::max_clique_approx(&ag.graph);
            assert!(
                approx.len() <= result.clique_number,
                "max_clique_approx size {} exceeds graph_clique_number {}",
                approx.len(),
                result.clique_number
            );
        }
        CliqueInput::LargeCliqueSize(ag) => {
            // Just calling max_clique_approx().len() — the underlying
            // call is already covered structurally by the MaxClique arm,
            // so this arm's only invariant is non-panic. Keep it minimal.
            let clique = fnx_algorithms::max_clique_approx(&ag.graph);
            assert!(
                clique.len() <= ag.graph.node_count(),
                "approx clique size {} exceeds node count {}",
                clique.len(),
                ag.graph.node_count()
            );
        }
        CliqueInput::CliqueRemoval(ag) => {
            let (independent_set, cliques) =
                fnx_algorithms::clique_removal(&ag.graph);
            // Every node in the result is from G's node set.
            for n in &independent_set {
                assert!(
                    ag.graph.has_node(n),
                    "clique_removal independent set contains foreign node {}",
                    n
                );
            }
            // Each returned clique is a real clique in G.
            for (i, clique) in cliques.iter().enumerate() {
                assert_is_clique(
                    &ag.graph,
                    clique,
                    &format!("clique_removal cover[{}]", i),
                );
            }
        }
    }
});
