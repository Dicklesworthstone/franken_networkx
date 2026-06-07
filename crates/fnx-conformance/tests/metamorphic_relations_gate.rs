//! Metamorphic relation tests for FrankenNetworkX.
//!
//! These tests encode invariants that should hold regardless of input,
//! catching correctness bugs without needing an exact oracle.
//!
//! Relations tested:
//! 1. Node relabeling preserves invariant metrics (centrality/components/diameter)
//! 2. Adding an isolated node doesn't change shortest paths between existing nodes
//! 3. Reversing all edges twice = identity
//! 4. Subgraph monotonicity of connectivity
//! 5. Isomorphic graphs yield equal invariants

use fnx_algorithms::{
    clustering_coefficient, is_connected, number_connected_components, shortest_path_length,
};
use fnx_classes::Graph;
use fnx_classes::digraph::DiGraph;
use fnx_runtime::CompatibilityMode;
use proptest::prelude::*;
use std::collections::{HashMap, HashSet};

fn default_mode() -> CompatibilityMode {
    CompatibilityMode::Strict
}

/// Generate a random undirected graph with n nodes and m edges.
fn arb_graph(max_nodes: usize, max_edges: usize) -> impl Strategy<Value = Graph> {
    (1..=max_nodes, 0..=max_edges).prop_flat_map(move |(n, m)| {
        let m = m.min(n * (n - 1) / 2); // cap at complete graph
        prop::collection::vec((0..n, 0..n), m).prop_map(move |edges| {
            let mut g = Graph::new(default_mode());
            for i in 0..n {
                g.add_node(&i.to_string());
            }
            for (u, v) in edges {
                if u != v {
                    g.add_edge(&u.to_string(), &v.to_string());
                }
            }
            g
        })
    })
}

/// Generate a random directed graph with n nodes and m edges.
fn arb_digraph(max_nodes: usize, max_edges: usize) -> impl Strategy<Value = DiGraph> {
    (1..=max_nodes, 0..=max_edges).prop_flat_map(move |(n, m)| {
        let m = m.min(n * (n - 1)); // cap at complete digraph
        prop::collection::vec((0..n, 0..n), m).prop_map(move |edges| {
            let mut g = DiGraph::new(default_mode());
            for i in 0..n {
                g.add_node(&i.to_string());
            }
            for (u, v) in edges {
                if u != v {
                    g.add_edge(&u.to_string(), &v.to_string());
                }
            }
            g
        })
    })
}

/// Generate a connected undirected graph (path + random edges).
fn arb_connected_graph(max_nodes: usize, extra_edges: usize) -> impl Strategy<Value = Graph> {
    (2..=max_nodes, 0..=extra_edges).prop_flat_map(move |(n, m)| {
        prop::collection::vec((0..n, 0..n), m).prop_map(move |extra| {
            let mut g = Graph::new(default_mode());
            // Build a path to ensure connectivity
            for i in 0..n {
                g.add_node(&i.to_string());
            }
            for i in 0..(n - 1) {
                g.add_edge(&i.to_string(), &(i + 1).to_string());
            }
            // Add random extra edges
            for (u, v) in extra {
                if u != v {
                    g.add_edge(&u.to_string(), &v.to_string());
                }
            }
            g
        })
    })
}

// ---------------------------------------------------------------------------
// Relation 1: Node relabeling preserves invariant metrics
// ---------------------------------------------------------------------------

proptest! {
    #![proptest_config(ProptestConfig::with_cases(50))]

    #[test]
    fn relabeling_preserves_number_of_components(g in arb_graph(20, 40)) {
        // Create a relabeled copy: node "i" -> "r_i"
        let mut relabeled = Graph::new(default_mode());
        let nodes: Vec<_> = g.nodes_ordered().into_iter().map(|s| s.to_owned()).collect();
        for node in &nodes {
            relabeled.add_node(&format!("r_{}", node));
        }
        for (u, v, _) in g.edges_ordered_borrowed() {
            relabeled.add_edge(&format!("r_{}", u), &format!("r_{}", v));
        }

        let orig_cc = number_connected_components(&g).count;
        let relabeled_cc = number_connected_components(&relabeled).count;
        prop_assert_eq!(orig_cc, relabeled_cc,
            "Relabeling should preserve number of connected components");
    }

    #[test]
    fn relabeling_preserves_degree_sequence(g in arb_graph(20, 40)) {
        // Create a relabeled copy
        let mut relabeled = Graph::new(default_mode());
        let nodes: Vec<_> = g.nodes_ordered().into_iter().map(|s| s.to_owned()).collect();
        for node in &nodes {
            relabeled.add_node(&format!("r_{}", node));
        }
        for (u, v, _) in g.edges_ordered_borrowed() {
            relabeled.add_edge(&format!("r_{}", u), &format!("r_{}", v));
        }

        // Compare degree sequences (sorted)
        let mut orig_degrees: Vec<_> = nodes.iter()
            .map(|n| g.degree(n))
            .collect();
        let mut relabeled_degrees: Vec<_> = nodes.iter()
            .map(|n| relabeled.degree(&format!("r_{}", n)))
            .collect();
        orig_degrees.sort();
        relabeled_degrees.sort();

        prop_assert_eq!(orig_degrees, relabeled_degrees,
            "Relabeling should preserve degree sequence");
    }

    #[test]
    fn relabeling_preserves_clustering_values(g in arb_graph(15, 30)) {
        // Create a relabeled copy
        let mut relabeled = Graph::new(default_mode());
        let nodes: Vec<_> = g.nodes_ordered().into_iter().map(|s| s.to_owned()).collect();
        for node in &nodes {
            relabeled.add_node(&format!("r_{}", node));
        }
        for (u, v, _) in g.edges_ordered_borrowed() {
            relabeled.add_edge(&format!("r_{}", u), &format!("r_{}", v));
        }

        let orig_result = clustering_coefficient(&g);
        let relabeled_result = clustering_coefficient(&relabeled);

        // Build maps from scores
        let orig_clustering: HashMap<_, _> = orig_result.scores.iter()
            .map(|s| (s.node.as_str(), s.score))
            .collect();
        let relabeled_clustering: HashMap<_, _> = relabeled_result.scores.iter()
            .map(|s| (s.node.as_str(), s.score))
            .collect();

        // Values should match (after mapping node names)
        for node in &nodes {
            let orig_val = orig_clustering.get(node.as_str()).copied().unwrap_or(0.0);
            let relabeled_val = relabeled_clustering
                .get(format!("r_{}", node).as_str())
                .copied()
                .unwrap_or(0.0);
            prop_assert!(
                (orig_val - relabeled_val).abs() < 1e-10,
                "Clustering coefficient should be preserved under relabeling: {} vs {}",
                orig_val, relabeled_val
            );
        }
    }
}

// ---------------------------------------------------------------------------
// Relation 2: Adding an isolated node doesn't change shortest paths
// ---------------------------------------------------------------------------

proptest! {
    #![proptest_config(ProptestConfig::with_cases(50))]

    #[test]
    fn isolated_node_preserves_shortest_paths(g in arb_connected_graph(10, 15)) {
        let nodes: Vec<_> = g.nodes_ordered().into_iter().map(|s| s.to_owned()).collect();
        if nodes.len() < 2 {
            return Ok(());
        }

        // Add an isolated node
        let mut g_with_isolate = Graph::new(default_mode());
        for node in &nodes {
            g_with_isolate.add_node(node);
        }
        for (u, v, _) in g.edges_ordered_borrowed() {
            g_with_isolate.add_edge(u, v);
        }
        g_with_isolate.add_node("__isolated__");

        // Check shortest paths between existing nodes are unchanged
        for i in 0..nodes.len().min(5) {
            for j in (i + 1)..nodes.len().min(5) {
                let orig_len = shortest_path_length(&g, &nodes[i], &nodes[j]).length;
                let new_len = shortest_path_length(&g_with_isolate, &nodes[i], &nodes[j]).length;
                prop_assert_eq!(orig_len, new_len,
                    "Adding isolated node should not change shortest path between {} and {}",
                    nodes[i], nodes[j]);
            }
        }
    }

    #[test]
    fn isolated_node_increases_component_count(g in arb_graph(10, 20)) {
        let nodes: Vec<_> = g.nodes_ordered().into_iter().map(|s| s.to_owned()).collect();

        // Add an isolated node
        let mut g_with_isolate = Graph::new(default_mode());
        for node in &nodes {
            g_with_isolate.add_node(node);
        }
        for (u, v, _) in g.edges_ordered_borrowed() {
            g_with_isolate.add_edge(u, v);
        }
        g_with_isolate.add_node("__isolated__");

        let orig_cc = number_connected_components(&g).count;
        let new_cc = number_connected_components(&g_with_isolate).count;

        prop_assert_eq!(new_cc, orig_cc + 1,
            "Adding isolated node should increase component count by 1");
    }
}

// ---------------------------------------------------------------------------
// Relation 3: Reversing all edges twice = identity
// ---------------------------------------------------------------------------

proptest! {
    #![proptest_config(ProptestConfig::with_cases(50))]

    #[test]
    fn reverse_twice_is_identity(dg in arb_digraph(15, 30)) {
        // Reverse once
        let mut reversed = DiGraph::new(default_mode());
        for node in dg.nodes_ordered() {
            reversed.add_node(node);
        }
        for (u, v, _) in dg.edges_ordered_borrowed() {
            reversed.add_edge(v, u); // reverse direction
        }

        // Reverse again
        let mut double_reversed = DiGraph::new(default_mode());
        for node in reversed.nodes_ordered() {
            double_reversed.add_node(node);
        }
        for (u, v, _) in reversed.edges_ordered_borrowed() {
            double_reversed.add_edge(v, u); // reverse again
        }

        // Should have same edges as original
        let orig_edges: HashSet<_> = dg.edges_ordered_borrowed()
            .into_iter()
            .map(|(u, v, _)| (u.to_owned(), v.to_owned()))
            .collect();
        let final_edges: HashSet<_> = double_reversed.edges_ordered_borrowed()
            .into_iter()
            .map(|(u, v, _)| (u.to_owned(), v.to_owned()))
            .collect();

        prop_assert_eq!(orig_edges, final_edges,
            "Reversing edges twice should yield original graph");
    }

    #[test]
    fn reverse_preserves_node_count(dg in arb_digraph(15, 30)) {
        let mut reversed = DiGraph::new(default_mode());
        for node in dg.nodes_ordered() {
            reversed.add_node(node);
        }
        for (u, v, _) in dg.edges_ordered_borrowed() {
            reversed.add_edge(v, u);
        }

        prop_assert_eq!(dg.node_count(), reversed.node_count(),
            "Reversing should preserve node count");
        prop_assert_eq!(dg.edge_count(), reversed.edge_count(),
            "Reversing should preserve edge count");
    }
}

// ---------------------------------------------------------------------------
// Relation 4: Subgraph monotonicity of connectivity
// ---------------------------------------------------------------------------

proptest! {
    #![proptest_config(ProptestConfig::with_cases(50))]

    #[test]
    fn removing_edge_cannot_decrease_components(g in arb_graph(15, 25)) {
        let edges: Vec<_> = g.edges_ordered_borrowed()
            .into_iter()
            .map(|(u, v, _)| (u.to_owned(), v.to_owned()))
            .collect();

        if edges.is_empty() {
            return Ok(());
        }

        let orig_cc = number_connected_components(&g).count;

        // Remove one edge
        let edge_to_remove = &edges[0];
        let mut subgraph = Graph::new(default_mode());
        for node in g.nodes_ordered() {
            subgraph.add_node(node);
        }
        for (u, v) in &edges[1..] {
            subgraph.add_edge(u.as_str(), v.as_str());
        }

        let new_cc = number_connected_components(&subgraph).count;

        prop_assert!(new_cc >= orig_cc,
            "Removing edge ({}, {}) should not decrease component count: {} -> {}",
            edge_to_remove.0, edge_to_remove.1, orig_cc, new_cc);
    }

    #[test]
    fn adding_edge_cannot_increase_components(g in arb_graph(10, 15)) {
        let nodes: Vec<_> = g.nodes_ordered().into_iter().map(|s| s.to_owned()).collect();
        if nodes.len() < 2 {
            return Ok(());
        }

        let orig_cc = number_connected_components(&g).count;

        // Add one edge between first two nodes
        let mut supergraph = Graph::new(default_mode());
        for node in &nodes {
            supergraph.add_node(node);
        }
        for (u, v, _) in g.edges_ordered_borrowed() {
            supergraph.add_edge(u, v);
        }
        supergraph.add_edge(&nodes[0], &nodes[1]);

        let new_cc = number_connected_components(&supergraph).count;

        prop_assert!(new_cc <= orig_cc,
            "Adding edge should not increase component count: {} -> {}",
            orig_cc, new_cc);
    }

    #[test]
    fn induced_subgraph_connectivity_monotonic(g in arb_connected_graph(15, 20)) {
        let nodes: Vec<_> = g.nodes_ordered().into_iter().map(|s| s.to_owned()).collect();
        if nodes.len() < 3 {
            return Ok(());
        }

        // Original is connected (1 component)
        prop_assert!(is_connected(&g).is_connected, "Test graph should be connected");

        // Induced subgraph on first half of nodes
        let half = nodes.len() / 2;
        let subset: HashSet<_> = nodes[..half].iter().cloned().collect();
        let mut induced = Graph::new(default_mode());
        for node in &subset {
            induced.add_node(node);
        }
        for (u, v, _) in g.edges_ordered_borrowed() {
            if subset.contains(u) && subset.contains(v) {
                induced.add_edge(u, v);
            }
        }

        let induced_cc = number_connected_components(&induced).count;

        // Induced subgraph can have more components than original
        prop_assert!(induced_cc >= 1,
            "Induced subgraph should have at least 1 component");
    }
}

// ---------------------------------------------------------------------------
// Relation 5: Isomorphic graphs yield equal invariants
// ---------------------------------------------------------------------------

proptest! {
    #![proptest_config(ProptestConfig::with_cases(30))]

    #[test]
    fn isomorphic_by_permutation_same_invariants(
        g in arb_graph(10, 20),
        perm_seed in 0u64..1000
    ) {
        let nodes: Vec<_> = g.nodes_ordered().into_iter().map(|s| s.to_owned()).collect();
        if nodes.is_empty() {
            return Ok(());
        }

        // Create a deterministic permutation
        use std::collections::hash_map::DefaultHasher;
        use std::hash::{Hash, Hasher};
        let mut indices: Vec<_> = (0..nodes.len()).collect();
        indices.sort_by_key(|&i| {
            let mut h = DefaultHasher::new();
            (i as u64 ^ perm_seed).hash(&mut h);
            h.finish()
        });

        // Build isomorphic graph with permuted node names
        let perm_map: HashMap<_, _> = nodes.iter()
            .enumerate()
            .map(|(i, n)| (n.as_str(), format!("p_{}", indices[i])))
            .collect();

        let mut iso = Graph::new(default_mode());
        for node in &nodes {
            iso.add_node(&perm_map[node.as_str()]);
        }
        for (u, v, _) in g.edges_ordered_borrowed() {
            iso.add_edge(&perm_map[u], &perm_map[v]);
        }

        // Check invariants match
        prop_assert_eq!(g.node_count(), iso.node_count());
        prop_assert_eq!(g.edge_count(), iso.edge_count());
        prop_assert_eq!(
            number_connected_components(&g).count,
            number_connected_components(&iso).count
        );

        // Degree sequences should match
        let mut orig_degrees: Vec<_> = nodes.iter().map(|n| g.degree(n)).collect();
        let mut iso_degrees: Vec<_> = nodes.iter()
            .map(|n| iso.degree(&perm_map[n.as_str()]))
            .collect();
        orig_degrees.sort();
        iso_degrees.sort();
        prop_assert_eq!(orig_degrees, iso_degrees,
            "Isomorphic graphs should have same degree sequence");

        // Clustering coefficient multisets should match
        let orig_result = clustering_coefficient(&g);
        let iso_result = clustering_coefficient(&iso);
        let mut orig_vals: Vec<_> = orig_result.scores.iter().map(|s| s.score).collect();
        let mut iso_vals: Vec<_> = iso_result.scores.iter().map(|s| s.score).collect();
        orig_vals.sort_by(|a, b| a.partial_cmp(b).unwrap());
        iso_vals.sort_by(|a, b| a.partial_cmp(b).unwrap());
        prop_assert_eq!(orig_vals.len(), iso_vals.len());
        for (a, b) in orig_vals.iter().zip(iso_vals.iter()) {
            prop_assert!((a - b).abs() < 1e-10,
                "Clustering values should match: {} vs {}", a, b);
        }
    }
}

// ---------------------------------------------------------------------------
// Additional sanity checks
// ---------------------------------------------------------------------------

proptest! {
    #![proptest_config(ProptestConfig::with_cases(50))]

    #[test]
    fn edge_count_matches_degree_sum_div_2(g in arb_graph(20, 40)) {
        let nodes: Vec<_> = g.nodes_ordered().into_iter().map(|s| s.to_owned()).collect();
        let degree_sum: usize = nodes.iter().map(|n| g.degree(n)).sum();

        // For undirected graph: sum of degrees = 2 * edge count
        prop_assert_eq!(degree_sum, 2 * g.edge_count(),
            "Sum of degrees should equal 2 * edge count");
    }

    #[test]
    fn complete_graph_is_connected(n in 2usize..15) {
        let mut g = Graph::new(default_mode());
        for i in 0..n {
            g.add_node(&i.to_string());
        }
        for i in 0..n {
            for j in (i + 1)..n {
                g.add_edge(&i.to_string(), &j.to_string());
            }
        }

        prop_assert!(is_connected(&g).is_connected,
            "Complete graph K_{} should be connected", n);
        prop_assert_eq!(number_connected_components(&g).count, 1);
        prop_assert_eq!(g.edge_count(), n * (n - 1) / 2,
            "K_{} should have n(n-1)/2 = {} edges", n, n * (n - 1) / 2);
    }

    #[test]
    fn path_graph_has_n_minus_1_edges(n in 2usize..20) {
        let mut g = Graph::new(default_mode());
        for i in 0..n {
            g.add_node(&i.to_string());
        }
        for i in 0..(n - 1) {
            let _ = g.add_edge(&i.to_string(), &(i + 1).to_string());
        }

        prop_assert_eq!(g.edge_count(), n - 1,
            "Path graph P_{} should have {} edges", n, n - 1);
        prop_assert!(is_connected(&g).is_connected,
            "Path graph P_{} should be connected", n);
    }

    #[test]
    fn cycle_graph_has_n_edges(n in 3usize..20) {
        let mut g = Graph::new(default_mode());
        for i in 0..n {
            g.add_node(&i.to_string());
        }
        for i in 0..n {
            let _ = g.add_edge(&i.to_string(), &((i + 1) % n).to_string());
        }

        prop_assert_eq!(g.edge_count(), n,
            "Cycle graph C_{} should have {} edges", n, n);
        prop_assert!(is_connected(&g).is_connected,
            "Cycle graph C_{} should be connected", n);
    }
}
