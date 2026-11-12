//! Structure-aware fuzzer for shortest path algorithms.
//!
//! Tests dijkstra, bellman-ford, and unweighted shortest paths on
//! valid-but-pathological graph structures.

#![no_main]

mod arbitrary_graph;

use arbitrary::Arbitrary;
use arbitrary_graph::{
    ArbitraryDiGraph, ArbitraryGraph, ArbitraryWeightedDiGraph, ArbitraryWeightedGraph,
};
use fnx_classes::Graph;
use fnx_classes::digraph::DiGraph;
use libfuzzer_sys::fuzz_target;
use std::collections::{HashMap, VecDeque};

const EPSILON: f64 = 1.0e-7;

#[derive(Debug, Arbitrary)]
enum ShortestPathInput {
    /// Unweighted shortest path on undirected graph.
    UnweightedUndirected(ArbitraryGraph),
    /// Unweighted shortest path on directed graph.
    UnweightedDirected(ArbitraryDiGraph),
    /// Weighted (Dijkstra) shortest path on undirected graph.
    WeightedUndirected(ArbitraryWeightedGraph),
    /// Weighted (Dijkstra) shortest path on directed graph.
    WeightedDirected(ArbitraryWeightedDiGraph),
    /// Single-source shortest path (all destinations).
    SingleSource(ArbitraryGraph),
    /// Multi-source dijkstra.
    MultiSource(ArbitraryWeightedGraph),
    /// All shortest paths via Bellman-Ford on undirected graph.
    AllShortestPathsBellmanFordUndirected(ArbitraryWeightedGraph),
    /// All shortest paths via Bellman-Ford on directed graph.
    AllShortestPathsBellmanFordDirected(ArbitraryWeightedDiGraph),
}

fn bfs_distance_graph(graph: &Graph, source: &str, target: &str) -> Option<usize> {
    if !graph.has_node(source) || !graph.has_node(target) {
        return None;
    }
    let mut distances = HashMap::new();
    let mut queue = VecDeque::new();
    distances.insert(source.to_owned(), 0usize);
    queue.push_back(source.to_owned());

    while let Some(node) = queue.pop_front() {
        let distance = distances[&node];
        if node == target {
            return Some(distance);
        }
        if let Some(neighbors) = graph.neighbors_iter(&node) {
            for neighbor in neighbors {
                if !distances.contains_key(neighbor) {
                    distances.insert(neighbor.to_owned(), distance + 1);
                    queue.push_back(neighbor.to_owned());
                }
            }
        }
    }
    None
}

fn bfs_distance_digraph(digraph: &DiGraph, source: &str, target: &str) -> Option<usize> {
    if !digraph.has_node(source) || !digraph.has_node(target) {
        return None;
    }
    let mut distances = HashMap::new();
    let mut queue = VecDeque::new();
    distances.insert(source.to_owned(), 0usize);
    queue.push_back(source.to_owned());

    while let Some(node) = queue.pop_front() {
        let distance = distances[&node];
        if node == target {
            return Some(distance);
        }
        if let Some(successors) = digraph.neighbors_iter(&node) {
            for successor in successors {
                if !distances.contains_key(successor) {
                    distances.insert(successor.to_owned(), distance + 1);
                    queue.push_back(successor.to_owned());
                }
            }
        }
    }
    None
}

fn assert_unweighted_graph_path(
    graph: &Graph,
    source: &str,
    target: &str,
    path: Option<&[String]>,
) {
    match (path, bfs_distance_graph(graph, source, target)) {
        (None, None) => {}
        (Some(path), Some(distance)) => {
            assert_eq!(path.first().map(String::as_str), Some(source));
            assert_eq!(path.last().map(String::as_str), Some(target));
            assert_eq!(path.len().saturating_sub(1), distance);
            for edge in path.windows(2) {
                assert!(graph.has_edge(&edge[0], &edge[1]));
            }
        }
        (actual, expected) => panic!(
            "unweighted graph path mismatch: actual={actual:?} expected_distance={expected:?}"
        ),
    }
}

fn assert_unweighted_digraph_path(
    digraph: &DiGraph,
    source: &str,
    target: &str,
    path: Option<&[String]>,
) {
    match (path, bfs_distance_digraph(digraph, source, target)) {
        (None, None) => {}
        (Some(path), Some(distance)) => {
            assert_eq!(path.first().map(String::as_str), Some(source));
            assert_eq!(path.last().map(String::as_str), Some(target));
            assert_eq!(path.len().saturating_sub(1), distance);
            for edge in path.windows(2) {
                assert!(digraph.has_edge(&edge[0], &edge[1]));
            }
        }
        (actual, expected) => panic!(
            "unweighted digraph path mismatch: actual={actual:?} expected_distance={expected:?}"
        ),
    }
}

fn graph_edge_weight(graph: &Graph, left: &str, right: &str, weight_attr: &str) -> f64 {
    graph
        .edge_attrs(left, right)
        .and_then(|attrs| attrs.get(weight_attr))
        .and_then(fnx_runtime::CgseValue::as_f64)
        .unwrap_or(1.0)
}

fn digraph_edge_weight(digraph: &DiGraph, source: &str, target: &str, weight_attr: &str) -> f64 {
    digraph
        .edge_attrs(source, target)
        .and_then(|attrs| attrs.get(weight_attr))
        .and_then(fnx_runtime::CgseValue::as_f64)
        .unwrap_or(1.0)
}

fn graph_has_only_nonnegative_weights(graph: &Graph, weight_attr: &str) -> bool {
    graph.edges_ordered().into_iter().all(|edge| {
        let weight = graph_edge_weight(graph, &edge.left, &edge.right, weight_attr);
        weight.is_finite() && weight >= 0.0
    })
}

fn digraph_has_only_nonnegative_weights(digraph: &DiGraph, weight_attr: &str) -> bool {
    digraph.edges_ordered().into_iter().all(|edge| {
        let weight = digraph_edge_weight(digraph, &edge.left, &edge.right, weight_attr);
        weight.is_finite() && weight >= 0.0
    })
}

fn brute_weighted_distance_graph(
    graph: &Graph,
    source: &str,
    target: &str,
    weight_attr: &str,
) -> Option<f64> {
    if !graph.has_node(source) || !graph.has_node(target) {
        return None;
    }
    let nodes = graph.nodes_ordered();
    let mut distances: HashMap<String, f64> = nodes
        .iter()
        .map(|node| ((*node).to_owned(), f64::INFINITY))
        .collect();
    distances.insert(source.to_owned(), 0.0);

    for _ in 0..nodes.len().saturating_sub(1) {
        let mut changed = false;
        for edge in graph.edges_ordered() {
            let weight = graph_edge_weight(graph, &edge.left, &edge.right, weight_attr);
            let left_distance = distances[&edge.left];
            let right_distance = distances[&edge.right];
            if left_distance + weight < right_distance - EPSILON {
                distances.insert(edge.right.clone(), left_distance + weight);
                changed = true;
            }
            if right_distance + weight < left_distance - EPSILON {
                distances.insert(edge.left.clone(), right_distance + weight);
                changed = true;
            }
        }
        if !changed {
            break;
        }
    }

    distances
        .get(target)
        .copied()
        .filter(|distance| distance.is_finite())
}

fn brute_weighted_distance_digraph(
    digraph: &DiGraph,
    source: &str,
    target: &str,
    weight_attr: &str,
) -> Option<f64> {
    if !digraph.has_node(source) || !digraph.has_node(target) {
        return None;
    }
    let nodes = digraph.nodes_ordered();
    let mut distances: HashMap<String, f64> = nodes
        .iter()
        .map(|node| ((*node).to_owned(), f64::INFINITY))
        .collect();
    distances.insert(source.to_owned(), 0.0);

    for _ in 0..nodes.len().saturating_sub(1) {
        let mut changed = false;
        for edge in digraph.edges_ordered() {
            let weight = digraph_edge_weight(digraph, &edge.left, &edge.right, weight_attr);
            let left_distance = distances[&edge.left];
            let right_distance = distances[&edge.right];
            if left_distance + weight < right_distance - EPSILON {
                distances.insert(edge.right.clone(), left_distance + weight);
                changed = true;
            }
        }
        if !changed {
            break;
        }
    }

    distances
        .get(target)
        .copied()
        .filter(|distance| distance.is_finite())
}

fn graph_path_weight(graph: &Graph, path: &[String], weight_attr: &str) -> f64 {
    path.windows(2)
        .map(|edge| {
            assert!(graph.has_edge(&edge[0], &edge[1]));
            graph_edge_weight(graph, &edge[0], &edge[1], weight_attr)
        })
        .sum()
}

fn digraph_path_weight(digraph: &DiGraph, path: &[String], weight_attr: &str) -> f64 {
    path.windows(2)
        .map(|edge| {
            assert!(digraph.has_edge(&edge[0], &edge[1]));
            digraph_edge_weight(digraph, &edge[0], &edge[1], weight_attr)
        })
        .sum()
}

fn assert_weighted_graph_path(
    graph: &Graph,
    source: &str,
    target: &str,
    weight_attr: &str,
    path: Option<&[String]>,
) {
    if !graph_has_only_nonnegative_weights(graph, weight_attr) {
        return;
    }
    match (
        path,
        brute_weighted_distance_graph(graph, source, target, weight_attr),
    ) {
        (None, None) => {}
        (Some(path), Some(distance)) => {
            assert_eq!(path.first().map(String::as_str), Some(source));
            assert_eq!(path.last().map(String::as_str), Some(target));
            assert!((graph_path_weight(graph, path, weight_attr) - distance).abs() <= EPSILON);
        }
        (actual, expected) => {
            panic!("weighted graph path mismatch: actual={actual:?} expected_distance={expected:?}")
        }
    }
}

fn assert_weighted_digraph_path(
    digraph: &DiGraph,
    source: &str,
    target: &str,
    weight_attr: &str,
    path: Option<&[String]>,
) {
    if !digraph_has_only_nonnegative_weights(digraph, weight_attr) {
        return;
    }
    match (
        path,
        brute_weighted_distance_digraph(digraph, source, target, weight_attr),
    ) {
        (None, None) => {}
        (Some(path), Some(distance)) => {
            assert_eq!(path.first().map(String::as_str), Some(source));
            assert_eq!(path.last().map(String::as_str), Some(target));
            assert!((digraph_path_weight(digraph, path, weight_attr) - distance).abs() <= EPSILON);
        }
        (actual, expected) => panic!(
            "weighted digraph path mismatch: actual={actual:?} expected_distance={expected:?}"
        ),
    }
}

fuzz_target!(|input: ShortestPathInput| {
    match input {
        ShortestPathInput::UnweightedUndirected(ag) => {
            if ag.nodes.len() >= 2 {
                let src = &ag.nodes[0];
                let dst = &ag.nodes[ag.nodes.len() - 1];
                let result = fnx_algorithms::shortest_path_unweighted(&ag.graph, src, dst);
                assert_unweighted_graph_path(&ag.graph, src, dst, result.path.as_deref());
            }
        }
        ShortestPathInput::UnweightedDirected(ag) => {
            if ag.nodes.len() >= 2 {
                let src = &ag.nodes[0];
                let dst = &ag.nodes[ag.nodes.len() - 1];
                let result = fnx_algorithms::shortest_path_unweighted_directed(&ag.graph, src, dst);
                assert_unweighted_digraph_path(&ag.graph, src, dst, result.path.as_deref());
            }
        }
        ShortestPathInput::WeightedUndirected(ag) => {
            if ag.nodes.len() >= 2 {
                let src = &ag.nodes[0];
                let dst = &ag.nodes[ag.nodes.len() - 1];
                let result =
                    fnx_algorithms::shortest_path_weighted(&ag.graph, src, dst, &ag.weight_attr);
                assert_weighted_graph_path(
                    &ag.graph,
                    src,
                    dst,
                    &ag.weight_attr,
                    result.path.as_deref(),
                );
            }
        }
        ShortestPathInput::WeightedDirected(ag) => {
            if ag.nodes.len() >= 2 {
                let src = &ag.nodes[0];
                let dst = &ag.nodes[ag.nodes.len() - 1];
                let result = fnx_algorithms::shortest_path_weighted_directed(
                    &ag.graph,
                    src,
                    dst,
                    &ag.weight_attr,
                );
                assert_weighted_digraph_path(
                    &ag.graph,
                    src,
                    dst,
                    &ag.weight_attr,
                    result.path.as_deref(),
                );
            }
        }
        ShortestPathInput::SingleSource(ag) => {
            if !ag.nodes.is_empty() {
                let src = &ag.nodes[0];
                let _ = fnx_algorithms::single_source_shortest_path(&ag.graph, src, None);
            }
        }
        ShortestPathInput::MultiSource(ag) => {
            if !ag.nodes.is_empty() {
                // Use first 1-3 nodes as sources
                let num_sources = 3.min(ag.nodes.len());
                let sources: Vec<&str> = ag
                    .nodes
                    .iter()
                    .take(num_sources)
                    .map(|s| s.as_str())
                    .collect();
                let _ = fnx_algorithms::multi_source_dijkstra(&ag.graph, &sources, &ag.weight_attr);
            }
        }
        ShortestPathInput::AllShortestPathsBellmanFordUndirected(ag) => {
            if ag.nodes.len() >= 2 {
                let src = &ag.nodes[0];
                let dst = &ag.nodes[ag.nodes.len() - 1];
                let result = fnx_algorithms::all_shortest_paths_weighted_bellman_ford(
                    &ag.graph,
                    src,
                    dst,
                    &ag.weight_attr,
                );
                assert_all_shortest_paths_bellman_ford_graph(
                    &ag.graph,
                    src,
                    dst,
                    &ag.weight_attr,
                    &result,
                );
            }
        }
        ShortestPathInput::AllShortestPathsBellmanFordDirected(ag) => {
            if ag.nodes.len() >= 2 {
                let src = &ag.nodes[0];
                let dst = &ag.nodes[ag.nodes.len() - 1];
                let result = fnx_algorithms::all_shortest_paths_weighted_directed_bellman_ford(
                    &ag.graph,
                    src,
                    dst,
                    &ag.weight_attr,
                );
                assert_all_shortest_paths_bellman_ford_digraph(
                    &ag.graph,
                    src,
                    dst,
                    &ag.weight_attr,
                    &result,
                );
            }
        }
    }
});

fn assert_all_shortest_paths_bellman_ford_graph(
    graph: &Graph,
    source: &str,
    target: &str,
    weight_attr: &str,
    result: &Result<Vec<Vec<String>>, ()>,
) {
    let paths = match result {
        // Negative cycle detected — caller wraps as NetworkXUnbounded.
        // Implementation invariant: only reachable when at least one
        // edge has a finite negative weight (or weights make 0-cost
        // unbounded loops).
        Err(()) => return,
        Ok(paths) => paths,
    };
    if !graph.has_node(source) || !graph.has_node(target) {
        assert!(paths.is_empty());
        return;
    }
    if source == target {
        assert_eq!(paths, &vec![vec![source.to_owned()]]);
        return;
    }
    let brute = brute_weighted_distance_graph(graph, source, target, weight_attr);
    if paths.is_empty() {
        // Either target unreachable, or all paths have non-finite cost.
        assert!(brute.is_none() || !brute.unwrap().is_finite());
        return;
    }
    if !graph_has_only_nonnegative_weights(graph, weight_attr) {
        // brute_weighted_distance_graph relaxes both directions and
        // would diverge on negative-weight undirected edges; skip the
        // distance comparison but still validate path structure.
        validate_paths_structure_graph(graph, source, target, paths);
        return;
    }
    let expected = brute.expect("path exists, so brute should produce a finite distance");
    for path in paths {
        assert_eq!(path.first().map(String::as_str), Some(source));
        assert_eq!(path.last().map(String::as_str), Some(target));
        let actual = graph_path_weight(graph, path, weight_attr);
        assert!(
            (actual - expected).abs() <= EPSILON,
            "all_shortest_paths_bellman_ford undirected weight mismatch: \
             actual={actual} expected={expected} path={path:?}"
        );
    }
    validate_paths_structure_graph(graph, source, target, paths);
}

fn assert_all_shortest_paths_bellman_ford_digraph(
    digraph: &DiGraph,
    source: &str,
    target: &str,
    weight_attr: &str,
    result: &Result<Vec<Vec<String>>, ()>,
) {
    let paths = match result {
        Err(()) => return,
        Ok(paths) => paths,
    };
    if !digraph.has_node(source) || !digraph.has_node(target) {
        assert!(paths.is_empty());
        return;
    }
    if source == target {
        assert_eq!(paths, &vec![vec![source.to_owned()]]);
        return;
    }
    let brute = brute_weighted_distance_digraph(digraph, source, target, weight_attr);
    if paths.is_empty() {
        assert!(brute.is_none() || !brute.unwrap().is_finite());
        return;
    }
    if !digraph_has_only_nonnegative_weights(digraph, weight_attr) {
        validate_paths_structure_digraph(digraph, source, target, paths);
        return;
    }
    let expected = brute.expect("path exists, so brute should produce a finite distance");
    for path in paths {
        assert_eq!(path.first().map(String::as_str), Some(source));
        assert_eq!(path.last().map(String::as_str), Some(target));
        let actual = digraph_path_weight(digraph, path, weight_attr);
        assert!(
            (actual - expected).abs() <= EPSILON,
            "all_shortest_paths_bellman_ford directed weight mismatch: \
             actual={actual} expected={expected} path={path:?}"
        );
    }
    validate_paths_structure_digraph(digraph, source, target, paths);
}

fn validate_paths_structure_graph(
    graph: &Graph,
    source: &str,
    target: &str,
    paths: &[Vec<String>],
) {
    for path in paths {
        assert_eq!(path.first().map(String::as_str), Some(source));
        assert_eq!(path.last().map(String::as_str), Some(target));
        for edge in path.windows(2) {
            assert!(graph.has_edge(&edge[0], &edge[1]));
        }
    }
}

fn validate_paths_structure_digraph(
    digraph: &DiGraph,
    source: &str,
    target: &str,
    paths: &[Vec<String>],
) {
    for path in paths {
        assert_eq!(path.first().map(String::as_str), Some(source));
        assert_eq!(path.last().map(String::as_str), Some(target));
        for edge in path.windows(2) {
            assert!(digraph.has_edge(&edge[0], &edge[1]));
        }
    }
}
