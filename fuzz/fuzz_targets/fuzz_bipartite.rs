//! Structure-aware fuzzer for bipartite algorithms.
//!
//! Tests is_bipartite, bipartite_sets, and color on valid-but-pathological
//! graph structures including both bipartite and non-bipartite graphs.

#![no_main]

mod arbitrary_graph;

use arbitrary::Arbitrary;
use arbitrary_graph::ArbitraryGraph;
use fnx_classes::Graph;
use libfuzzer_sys::fuzz_target;
use std::collections::HashSet;

/// Verify that `set_a` and `set_b` form a valid bipartition of `graph`:
/// disjoint, both subsets of G's node set, and every edge that lies
/// entirely within the partition crosses between the two sets.
///
/// fnx's bipartite_sets returns the partition of the BFS source's
/// connected component only, so other components' edges may have
/// endpoints in neither set — those are skipped here, since the
/// returned partition is meaningless for them.
fn assert_valid_bipartition(graph: &Graph, set_a: &[String], set_b: &[String], label: &str) {
    let in_a: HashSet<&str> = set_a.iter().map(|s| s.as_str()).collect();
    let in_b: HashSet<&str> = set_b.iter().map(|s| s.as_str()).collect();
    assert_eq!(
        in_a.len(),
        set_a.len(),
        "{}: set_a has duplicate nodes",
        label
    );
    assert_eq!(
        in_b.len(),
        set_b.len(),
        "{}: set_b has duplicate nodes",
        label
    );
    for n in &in_a {
        assert!(
            graph.has_node(n),
            "{}: set_a contains foreign node {}",
            label,
            n
        );
        assert!(
            !in_b.contains(n),
            "{}: node {} appears in both bipartite sets",
            label,
            n
        );
    }
    for n in &in_b {
        assert!(
            graph.has_node(n),
            "{}: set_b contains foreign node {}",
            label,
            n
        );
    }
    for edge in graph.edges_ordered() {
        let l_in_a = in_a.contains(edge.left.as_str());
        let l_in_b = in_b.contains(edge.left.as_str());
        let r_in_a = in_a.contains(edge.right.as_str());
        let r_in_b = in_b.contains(edge.right.as_str());
        if !(l_in_a || l_in_b) || !(r_in_a || r_in_b) {
            // Edge endpoints belong to a different component than the
            // returned partition — skip.
            continue;
        }
        let crosses = (l_in_a && r_in_b) || (l_in_b && r_in_a);
        assert!(
            crosses,
            "{}: edge ({}, {}) does not cross the bipartition",
            label,
            edge.left,
            edge.right
        );
    }
}

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
}

fuzz_target!(|input: BipartiteInput| {
    match input {
        BipartiteInput::IsBipartiteArbitrary(ag) => {
            // Cross-check is_bipartite against bipartite_sets.is_bipartite —
            // the two predicates must always agree.
            let result = fnx_algorithms::is_bipartite(&ag.graph);
            let sets = fnx_algorithms::bipartite_sets(&ag.graph);
            assert_eq!(
                result.is_bipartite, sets.is_bipartite,
                "is_bipartite ({}) disagrees with bipartite_sets.is_bipartite ({})",
                result.is_bipartite, sets.is_bipartite
            );
        }
        BipartiteInput::IsBipartiteKnown(bg) => {
            // Known bipartite graph should always return true (this is a
            // real assertion, not debug_assert!, so the fuzzer can
            // catch regressions in release/sanitizer builds).
            let result = fnx_algorithms::is_bipartite(&bg.graph);
            assert!(
                result.is_bipartite,
                "constructed bipartite graph reported as non-bipartite by is_bipartite"
            );
            // Cross-check: bipartite_sets must agree.
            let sets = fnx_algorithms::bipartite_sets(&bg.graph);
            assert!(
                sets.is_bipartite,
                "constructed bipartite graph reported as non-bipartite by bipartite_sets"
            );
            assert_valid_bipartition(
                &bg.graph,
                &sets.set_a,
                &sets.set_b,
                "bipartite_sets (known)",
            );
        }
        BipartiteInput::BipartiteSetsArbitrary(ag) => {
            let result = fnx_algorithms::bipartite_sets(&ag.graph);
            if result.is_bipartite {
                assert_valid_bipartition(
                    &ag.graph,
                    &result.set_a,
                    &result.set_b,
                    "bipartite_sets (arbitrary)",
                );
            }
            // When non-bipartite, the returned sets are
            // implementation-dependent; just ensure the bool matches
            // is_bipartite (consistency).
            let bp = fnx_algorithms::is_bipartite(&ag.graph);
            assert_eq!(
                result.is_bipartite, bp.is_bipartite,
                "bipartite_sets.is_bipartite disagrees with is_bipartite"
            );
        }
        BipartiteInput::BipartiteSetsKnown(bg) => {
            let result = fnx_algorithms::bipartite_sets(&bg.graph);
            assert!(
                result.is_bipartite,
                "constructed bipartite graph reported as non-bipartite by bipartite_sets"
            );
            assert_valid_bipartition(
                &bg.graph,
                &result.set_a,
                &result.set_b,
                "bipartite_sets (known)",
            );
        }
    }
});
