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
                let result = fnx_algorithms::ancestors(&dag.graph, node);
                // Every ancestor must be in G and must NOT be the node
                // itself (nx contract: ancestors(v) excludes v).
                for a in &result {
                    assert!(
                        dag.graph.has_node(a),
                        "ancestors result contains foreign node {}",
                        a
                    );
                    assert_ne!(
                        a.as_str(),
                        node.as_str(),
                        "ancestors of {} should exclude self",
                        node
                    );
                }
            }
        }
        DagInput::Descendants(dag) => {
            if !dag.nodes.is_empty() {
                let node = &dag.nodes[0];
                let result = fnx_algorithms::descendants(&dag.graph, node);
                for d in &result {
                    assert!(
                        dag.graph.has_node(d),
                        "descendants result contains foreign node {}",
                        d
                    );
                    assert_ne!(
                        d.as_str(),
                        node.as_str(),
                        "descendants of {} should exclude self",
                        node
                    );
                }
                // Symmetric invariant: u ∈ descendants(v) iff v ∈
                // ancestors(u). Cross-check on a sample (cap iterations
                // so the fuzzer stays fast on dense DAGs).
                for (i, d) in result.iter().enumerate() {
                    if i >= 8 {
                        break;
                    }
                    let anc = fnx_algorithms::ancestors(&dag.graph, d);
                    assert!(
                        anc.contains(node.as_str()),
                        "asymmetry: {} in descendants({}) but {} not in ancestors({})",
                        d, node, node, d
                    );
                }
            }
        }
        DagInput::DescendantsAtDistance(dag) => {
            if !dag.nodes.is_empty() {
                let node = &dag.nodes[0];
                let result = fnx_algorithms::descendants_at_distance_directed(
                    &dag.graph,
                    node.as_str(),
                    2,
                );
                for d in &result {
                    assert!(
                        dag.graph.has_node(d),
                        "descendants_at_distance result contains foreign node {}",
                        d
                    );
                }
                // Subset relation: descendants_at_distance(v, k) ⊆
                // descendants(v) ∪ {v}.
                let all_desc = fnx_algorithms::descendants(&dag.graph, node);
                for d in &result {
                    assert!(
                        all_desc.contains(d) || d.as_str() == node.as_str(),
                        "node {} at distance 2 from {} is not in descendants set",
                        d, node
                    );
                }
            }
        }
        DagInput::DagLongestPath(dag) => {
            if let Some(path) = fnx_algorithms::dag_longest_path(&dag.graph) {
                // Each consecutive pair must be an edge of G.
                for window in path.windows(2) {
                    assert!(
                        dag.graph.has_edge(&window[0], &window[1]),
                        "dag_longest_path emitted edge {} -> {} not in graph",
                        window[0], window[1]
                    );
                }
                // No node appears twice (DAG path is simple by
                // construction).
                let mut seen: HashSet<&str> = HashSet::new();
                for n in &path {
                    assert!(
                        seen.insert(n.as_str()),
                        "dag_longest_path repeated node {}",
                        n
                    );
                }
                // Cross-check: dag_longest_path_length must equal
                // |path| - 1.
                let length = fnx_algorithms::dag_longest_path_length(&dag.graph);
                let expected = path.len().saturating_sub(1);
                assert_eq!(
                    length,
                    Some(expected),
                    "dag_longest_path_length ({:?}) != |dag_longest_path|-1 ({})",
                    length,
                    expected
                );
            }
        }
        DagInput::DagLongestPathLength(dag) => {
            let length = fnx_algorithms::dag_longest_path_length(&dag.graph);
            // Length is bounded: |path| ≤ n, so length ≤ n - 1.
            if let Some(len) = length {
                let upper = dag.graph.node_count().saturating_sub(1);
                assert!(
                    len <= upper,
                    "dag_longest_path_length {} exceeds n-1 = {}",
                    len,
                    upper
                );
            }
        }
        DagInput::Antichains(dag) => {
            // Sample the first few antichains and verify nodes are in
            // G. Pairwise-incomparability is more expensive to check
            // (would need a full reachability oracle), so we settle for
            // node-set membership here.
            let antichains = fnx_algorithms::antichains(&dag.graph);
            for (i, antichain) in antichains.into_iter().enumerate() {
                if i >= 100 {
                    break;
                }
                for n in &antichain {
                    assert!(
                        dag.graph.has_node(n),
                        "antichain contains foreign node {}",
                        n
                    );
                }
            }
        }
        DagInput::TransitiveClosure(dag) => {
            let tc = fnx_algorithms::transitive_closure(&dag.graph, None);
            // Closure has the same node set.
            assert_eq!(
                tc.node_count(),
                dag.graph.node_count(),
                "transitive_closure node count diverged from input"
            );
            for n in dag.graph.nodes_ordered() {
                assert!(
                    tc.has_node(n),
                    "transitive_closure missing node {}",
                    n
                );
            }
            // Closure is a superset of G's edges.
            for edge in dag.graph.edges_ordered() {
                assert!(
                    tc.has_edge(&edge.left, &edge.right),
                    "transitive_closure missing original edge {} -> {}",
                    edge.left,
                    edge.right
                );
            }
        }
        DagInput::TransitiveReduction(dag) => {
            if let Some(tr) = fnx_algorithms::transitive_reduction(&dag.graph) {
                assert_eq!(
                    tr.node_count(),
                    dag.graph.node_count(),
                    "transitive_reduction node count diverged from input"
                );
                // Every reduction edge must be an actual edge of G
                // (the reduction is a subgraph of G when G is a DAG).
                for edge in tr.edges_ordered() {
                    assert!(
                        dag.graph.has_edge(&edge.left, &edge.right),
                        "transitive_reduction emitted edge {} -> {} not in original DAG",
                        edge.left,
                        edge.right
                    );
                }
            }
        }
    }
});
