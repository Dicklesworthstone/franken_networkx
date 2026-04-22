//! Structure-aware fuzzer for DAG algorithms.
//!
//! Tests topological sort, ancestors, descendants, antichains, and longest path
//! on valid-but-pathological DAG structures.

#![no_main]

mod arbitrary_graph;

use arbitrary::Arbitrary;
use arbitrary_graph::ArbitraryDiGraph;
use libfuzzer_sys::fuzz_target;

/// A directed acyclic graph generated via `Arbitrary`.
///
/// We generate a DiGraph and then remove back-edges to ensure acyclicity.
#[derive(Debug, Clone)]
pub struct ArbitraryDag {
    pub graph: fnx_classes::digraph::DiGraph,
    pub nodes: Vec<String>,
}

impl<'a> Arbitrary<'a> for ArbitraryDag {
    fn arbitrary(u: &mut arbitrary::Unstructured<'a>) -> arbitrary::Result<Self> {
        use fnx_runtime::CompatibilityMode;

        let mode = if u.arbitrary()? {
            CompatibilityMode::Strict
        } else {
            CompatibilityMode::Hardened
        };

        let mut graph = fnx_classes::digraph::DiGraph::new(mode);
        let node_count: usize = u.int_in_range(0..=32)?;
        let mut nodes = Vec::with_capacity(node_count);

        // Generate nodes with numeric names for topological ordering
        for i in 0..node_count {
            let name = format!("n{i}");
            graph.add_node(&name);
            nodes.push(name);
        }

        // Generate edges only from lower to higher index (ensures DAG)
        if node_count > 1 {
            let edge_density: u8 = u.arbitrary()?;
            let target_edges = (node_count * (edge_density as usize % 4)) / 2;

            for _ in 0..target_edges {
                if u.is_empty() {
                    break;
                }
                let src_idx: usize = u.int_in_range(0..=node_count - 2)?;
                let dst_idx: usize = u.int_in_range(src_idx + 1..=node_count - 1)?;
                let _ = graph.add_edge(&nodes[src_idx], &nodes[dst_idx]);
            }
        }

        Ok(Self { graph, nodes })
    }
}

#[derive(Debug, Arbitrary)]
enum DagInput {
    /// Topological sort.
    TopologicalSort(ArbitraryDag),
    /// Lexicographic topological sort.
    LexicographicTopologicalSort(ArbitraryDag),
    /// Topological generations.
    TopologicalGenerations(ArbitraryDag),
    /// All topological sorts.
    AllTopologicalSorts(ArbitraryDag),
    /// Ancestors of a node.
    Ancestors(ArbitraryDag),
    /// Descendants of a node.
    Descendants(ArbitraryDag),
    /// Descendants at distance.
    DescendantsAtDistance(ArbitraryDag),
    /// DAG longest path.
    DagLongestPath(ArbitraryDag),
    /// DAG longest path length.
    DagLongestPathLength(ArbitraryDag),
    /// Antichains.
    Antichains(ArbitraryDag),
    /// Transitive closure.
    TransitiveClosure(ArbitraryDag),
    /// Transitive reduction.
    TransitiveReduction(ArbitraryDag),
}

fuzz_target!(|input: DagInput| {
    match input {
        DagInput::TopologicalSort(dag) => {
            let _ = fnx_algorithms::topological_sort(&dag.graph);
        }
        DagInput::LexicographicTopologicalSort(dag) => {
            let _ = fnx_algorithms::lexicographic_topological_sort(&dag.graph);
        }
        DagInput::TopologicalGenerations(dag) => {
            let _ = fnx_algorithms::topological_generations(&dag.graph);
        }
        DagInput::AllTopologicalSorts(dag) => {
            // Limit iteration to avoid combinatorial explosion
            let sorts = fnx_algorithms::all_topological_sorts(&dag.graph);
            for (i, _sort) in sorts.into_iter().enumerate() {
                if i >= 100 {
                    break;
                }
            }
        }
        DagInput::Ancestors(dag) => {
            if !dag.nodes.is_empty() {
                let node = &dag.nodes[dag.nodes.len() / 2];
                let _ = fnx_algorithms::ancestors(&dag.graph, node);
            }
        }
        DagInput::Descendants(dag) => {
            if !dag.nodes.is_empty() {
                let node = &dag.nodes[0];
                let _ = fnx_algorithms::descendants(&dag.graph, node);
            }
        }
        DagInput::DescendantsAtDistance(dag) => {
            if !dag.nodes.is_empty() {
                let node = &dag.nodes[0];
                let _ = fnx_algorithms::descendants_at_distance_directed(&dag.graph, node.as_str(), 2);
            }
        }
        DagInput::DagLongestPath(dag) => {
            let _ = fnx_algorithms::dag_longest_path(&dag.graph);
        }
        DagInput::DagLongestPathLength(dag) => {
            let _ = fnx_algorithms::dag_longest_path_length(&dag.graph);
        }
        DagInput::Antichains(dag) => {
            // Limit iteration to avoid combinatorial explosion
            let antichains = fnx_algorithms::antichains(&dag.graph);
            for (i, _antichain) in antichains.into_iter().enumerate() {
                if i >= 100 {
                    break;
                }
            }
        }
        DagInput::TransitiveClosure(dag) => {
            let _ = fnx_algorithms::transitive_closure(&dag.graph, None);
        }
        DagInput::TransitiveReduction(dag) => {
            let _ = fnx_algorithms::transitive_reduction(&dag.graph);
        }
    }
});
