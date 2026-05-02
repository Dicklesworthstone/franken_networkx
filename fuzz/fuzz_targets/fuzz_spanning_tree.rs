//! Structure-aware fuzzer for spanning tree algorithms.
//!
//! Tests minimum spanning tree (Kruskal, Prim), maximum spanning tree,
//! and tree validation on valid-but-pathological graph structures.

#![no_main]

mod arbitrary_graph;

use arbitrary::Arbitrary;
use arbitrary_graph::{ArbitraryGraph, ArbitraryWeightedGraph};
use fnx_algorithms::MinimumSpanningTreeResult;
use fnx_classes::Graph;
use libfuzzer_sys::fuzz_target;
use std::collections::{HashMap, HashSet};

const MST_EPS: f64 = 1.0e-6;

/// Verify the structural MST/MaxST contract for a single connected
/// component: every reported edge is in G, total_weight is the actual
/// edge-weight sum, and the edge set is acyclic (|E| = |V_covered| - 1
/// per component).
fn assert_valid_spanning_forest(
    graph: &Graph,
    result: &MinimumSpanningTreeResult,
    label: &str,
) {
    let mut covered: HashSet<&str> = HashSet::new();
    let mut weight_sum = 0.0_f64;
    for edge in &result.edges {
        assert!(
            graph.has_edge(&edge.left, &edge.right),
            "{}: emitted edge ({}, {}) not in graph",
            label,
            edge.left,
            edge.right
        );
        assert!(
            edge.weight.is_finite(),
            "{}: edge weight ({} → {}) is not finite ({})",
            label,
            edge.left,
            edge.right,
            edge.weight
        );
        covered.insert(edge.left.as_str());
        covered.insert(edge.right.as_str());
        weight_sum += edge.weight;
    }
    // total_weight matches sum of per-edge weights.
    assert!(
        (weight_sum - result.total_weight).abs() < MST_EPS,
        "{}: total_weight {} != sum of per-edge weights {}",
        label,
        result.total_weight,
        weight_sum
    );
    // Acyclic: |E| ≤ |V_covered| - 1 (with equality on connected
    // components). We can't easily compute the exact number of
    // components here, but |E| < |V| of the full graph is a useful
    // ceiling — a spanning forest has at most n-1 edges total.
    assert!(
        result.edges.len() < graph.node_count().max(1),
        "{}: spanning forest has {} edges, ≥ |V|={}",
        label,
        result.edges.len(),
        graph.node_count()
    );
    // No duplicate edges (canonicalize undirected pairs).
    let mut seen: HashSet<(&str, &str)> = HashSet::new();
    for edge in &result.edges {
        let (a, b) = if edge.left <= edge.right {
            (edge.left.as_str(), edge.right.as_str())
        } else {
            (edge.right.as_str(), edge.left.as_str())
        };
        assert!(
            seen.insert((a, b)),
            "{}: duplicate edge ({}, {}) in result",
            label,
            edge.left,
            edge.right
        );
    }
    // Acyclicity check via union-find: every accepted edge must merge
    // two distinct components.
    let nodes: Vec<&str> = covered.iter().copied().collect();
    let mut idx: HashMap<&str, usize> = HashMap::with_capacity(nodes.len());
    for (i, n) in nodes.iter().enumerate() {
        idx.insert(*n, i);
    }
    let mut parent: Vec<usize> = (0..nodes.len()).collect();
    fn find(parent: &mut [usize], i: usize) -> usize {
        let mut root = i;
        while parent[root] != root {
            root = parent[root];
        }
        let mut cur = i;
        while parent[cur] != root {
            let next = parent[cur];
            parent[cur] = root;
            cur = next;
        }
        root
    }
    for edge in &result.edges {
        let u = idx[edge.left.as_str()];
        let v = idx[edge.right.as_str()];
        let ru = find(&mut parent, u);
        let rv = find(&mut parent, v);
        assert!(
            ru != rv,
            "{}: edge ({}, {}) creates a cycle in the result",
            label,
            edge.left,
            edge.right
        );
        parent[ru] = rv;
    }
}

#[derive(Debug, Arbitrary)]
enum SpanningTreeInput {
    /// Minimum spanning tree (Kruskal).
    MstKruskal(ArbitraryWeightedGraph),
    /// Minimum spanning tree (Prim).
    MstPrim(ArbitraryWeightedGraph),
    /// Maximum spanning tree.
    MaxSt(ArbitraryWeightedGraph),
    /// Is tree check.
    IsTree(ArbitraryGraph),
    /// Is forest check.
    IsForest(ArbitraryGraph),
    /// Number of spanning trees.
    NumberSpanningTrees(ArbitraryWeightedGraph),
}

fuzz_target!(|input: SpanningTreeInput| {
    match input {
        SpanningTreeInput::MstKruskal(ag) => {
            let result = fnx_algorithms::minimum_spanning_tree(&ag.graph, &ag.weight_attr);
            assert_valid_spanning_forest(&ag.graph, &result, "minimum_spanning_tree (Kruskal)");
            // Cross-check: Prim must produce the same total weight on
            // the same graph (MST total weight is algorithm-invariant).
            let prim = fnx_algorithms::minimum_spanning_tree_prim(&ag.graph, &ag.weight_attr);
            assert!(
                (result.total_weight - prim.total_weight).abs() < MST_EPS,
                "MST total weight diverges across algorithms: kruskal={} prim={}",
                result.total_weight,
                prim.total_weight
            );
        }
        SpanningTreeInput::MstPrim(ag) => {
            let result = fnx_algorithms::minimum_spanning_tree_prim(&ag.graph, &ag.weight_attr);
            assert_valid_spanning_forest(&ag.graph, &result, "minimum_spanning_tree (Prim)");
        }
        SpanningTreeInput::MaxSt(ag) => {
            let result = fnx_algorithms::maximum_spanning_tree(&ag.graph, &ag.weight_attr);
            assert_valid_spanning_forest(&ag.graph, &result, "maximum_spanning_tree");
            // Cross-check: max spanning tree weight ≥ min spanning tree
            // weight (always — equal only when all edge weights equal).
            let mst = fnx_algorithms::minimum_spanning_tree(&ag.graph, &ag.weight_attr);
            assert!(
                result.total_weight + MST_EPS >= mst.total_weight,
                "max spanning tree weight {} < min spanning tree weight {}",
                result.total_weight,
                mst.total_weight
            );
        }
        SpanningTreeInput::IsTree(ag) => {
            let result = fnx_algorithms::is_tree(&ag.graph);
            // A tree has exactly n-1 edges. For non-empty graph,
            // is_tree → |E| == |V| - 1. The converse isn't true in
            // general (could be a disconnected forest with the same
            // edge count) but the forward direction is a real check.
            if result.is_tree && ag.graph.node_count() > 0 {
                assert_eq!(
                    ag.graph.edge_count(),
                    ag.graph.node_count() - 1,
                    "is_tree=true but |E|={} != |V|-1={}",
                    ag.graph.edge_count(),
                    ag.graph.node_count() - 1
                );
            }
        }
        SpanningTreeInput::IsForest(ag) => {
            let result = fnx_algorithms::is_forest(&ag.graph);
            // A forest has |E| ≤ |V| - components. Without computing
            // components here, the weaker bound |E| ≤ |V| - 1 is wrong
            // (forests with multiple components have |E| < |V|-1). The
            // tightest fast check: forest implies |E| ≤ |V| (always
            // true since forests are acyclic, so |E| < |V|).
            if result.is_forest && ag.graph.node_count() > 0 {
                assert!(
                    ag.graph.edge_count() < ag.graph.node_count(),
                    "is_forest=true but |E|={} >= |V|={}",
                    ag.graph.edge_count(),
                    ag.graph.node_count()
                );
            }
            // Cross-check: tree → forest (every tree is a forest).
            let tree = fnx_algorithms::is_tree(&ag.graph);
            if tree.is_tree {
                assert!(
                    result.is_forest,
                    "is_tree=true implies is_forest=true (failed cross-check)"
                );
            }
        }
        SpanningTreeInput::NumberSpanningTrees(ag) => {
            // Only compute for small graphs (determinant is O(n^3)).
            if ag.nodes.len() <= 16 {
                let count =
                    fnx_algorithms::number_of_spanning_trees(&ag.graph, Some(&ag.weight_attr));
                // Count is non-negative finite (or 0 for disconnected
                // graphs).
                assert!(
                    count.is_finite() && count >= -MST_EPS,
                    "number_of_spanning_trees {} is not non-negative finite",
                    count
                );
            }
        }
    }
});
