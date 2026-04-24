//! Structure-aware fuzzer for DAG algorithms.
//!
//! Tests topological sort, ancestors, descendants, antichains, and longest path
//! on valid-but-pathological DAG structures.

#![no_main]

mod arbitrary_graph;

use arbitrary::Arbitrary;
use libfuzzer_sys::fuzz_target;
use std::collections::{HashMap, HashSet};

/// A directed acyclic graph generated via `Arbitrary`.
///
/// We generate a DiGraph and then remove back-edges to ensure acyclicity.
#[derive(Debug, Clone)]
pub struct ArbitraryDag {
    pub graph: fnx_classes::digraph::DiGraph,
    pub nodes: Vec<String>,
}

/// A small DAG for combinatorial algorithms (all_topological_sorts, antichains).
/// Limited to 8 nodes to avoid factorial explosion.
#[derive(Debug, Clone)]
pub struct ArbitrarySmallDag {
    pub graph: fnx_classes::digraph::DiGraph,
    pub nodes: Vec<String>,
}

fn build_dag(
    u: &mut arbitrary::Unstructured<'_>,
    max_nodes: usize,
) -> arbitrary::Result<(fnx_classes::digraph::DiGraph, Vec<String>)> {
    use fnx_runtime::CompatibilityMode;

    let mode = if u.arbitrary()? {
        CompatibilityMode::Strict
    } else {
        CompatibilityMode::Hardened
    };

    let mut graph = fnx_classes::digraph::DiGraph::new(mode);
    let node_count: usize = u.int_in_range(0..=max_nodes)?;
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

    Ok((graph, nodes))
}

impl<'a> Arbitrary<'a> for ArbitraryDag {
    fn arbitrary(u: &mut arbitrary::Unstructured<'a>) -> arbitrary::Result<Self> {
        let (graph, nodes) = build_dag(u, 32)?;
        Ok(Self { graph, nodes })
    }
}

impl<'a> Arbitrary<'a> for ArbitrarySmallDag {
    fn arbitrary(u: &mut arbitrary::Unstructured<'a>) -> arbitrary::Result<Self> {
        let (graph, nodes) = build_dag(u, 8)?;
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
    /// All topological sorts (small DAG to avoid factorial explosion).
    AllTopologicalSorts(ArbitrarySmallDag),
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
    /// Antichains (small DAG to avoid exponential explosion).
    Antichains(ArbitrarySmallDag),
    /// Transitive closure.
    TransitiveClosure(ArbitraryDag),
    /// Transitive reduction.
    TransitiveReduction(ArbitraryDag),
}

fn assert_valid_topological_order(
    graph: &fnx_classes::digraph::DiGraph,
    order: Option<Vec<String>>,
) {
    let order = order.expect("generated DAG must have a topological order");
    assert_eq!(order.len(), graph.node_count());

    let mut seen = HashSet::new();
    let mut positions = HashMap::new();
    for (index, node) in order.iter().enumerate() {
        assert!(graph.has_node(node));
        assert!(seen.insert(node.as_str()));
        positions.insert(node.as_str(), index);
    }

    for edge in graph.edges_ordered() {
        let source_position = positions[edge.left.as_str()];
        let target_position = positions[edge.right.as_str()];
        assert!(
            source_position < target_position,
            "topological order violates edge {} -> {}",
            edge.left,
            edge.right
        );
    }
}

fn assert_valid_topological_generations(
    graph: &fnx_classes::digraph::DiGraph,
    generations: Option<Vec<Vec<String>>>,
) {
    let generations = generations.expect("generated DAG must have topological generations");
    let mut positions = HashMap::new();
    let mut seen = HashSet::new();

    for (generation_index, generation) in generations.iter().enumerate() {
        for node in generation {
            assert!(graph.has_node(node));
            assert!(seen.insert(node.as_str()));
            positions.insert(node.as_str(), generation_index);
        }
    }

    assert_eq!(seen.len(), graph.node_count());
    for edge in graph.edges_ordered() {
        let source_generation = positions[edge.left.as_str()];
        let target_generation = positions[edge.right.as_str()];
        assert!(
            source_generation < target_generation,
            "generation order violates edge {} -> {}",
            edge.left,
            edge.right
        );
    }
}

fuzz_target!(|input: DagInput| {
    match input {
        DagInput::TopologicalSort(dag) => {
            assert_valid_topological_order(
                &dag.graph,
                fnx_algorithms::topological_sort(&dag.graph).map(|result| result.order),
            );
        }
        DagInput::LexicographicTopologicalSort(dag) => {
            assert_valid_topological_order(
                &dag.graph,
                fnx_algorithms::lexicographic_topological_sort(&dag.graph),
            );
        }
        DagInput::TopologicalGenerations(dag) => {
            assert_valid_topological_generations(
                &dag.graph,
                fnx_algorithms::topological_generations(&dag.graph)
                    .map(|result| result.generations),
            );
        }
        DagInput::AllTopologicalSorts(dag) => {
            // Limit iteration to avoid combinatorial explosion
            let sorts = fnx_algorithms::all_topological_sorts(&dag.graph);
            for (i, sort) in sorts.into_iter().enumerate() {
                assert_valid_topological_order(&dag.graph, Some(sort));
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
                let _ =
                    fnx_algorithms::descendants_at_distance_directed(&dag.graph, node.as_str(), 2);
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
