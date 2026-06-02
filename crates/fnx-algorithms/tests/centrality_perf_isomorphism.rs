#![forbid(unsafe_code)]

//! Metamorphic isomorphism guard for the cached-adjacency centrality
//! optimizations (commits 9937e9e17 betweenness, 42b08d416 closeness, and the
//! harmonic migration).
//!
//! The optimization replaced per-edge string→index resolution with an integer
//! adjacency built once per call. Its correctness rests on the cached adjacency
//! being iterated in the *same order* the old string path used, so per-node
//! scores must be **independent of node-insertion order** (betweenness,
//! closeness, and harmonic centrality are structural invariants). These tests
//! build the same graph two ways — canonical and permuted insertion order — and
//! assert the per-node scores agree. A regression in the adjacency caching that
//! reorders traversal would diverge here.

use std::collections::HashMap;

use fnx_algorithms::{betweenness_centrality, closeness_centrality, harmonic_centrality};
use fnx_classes::Graph;

/// Build a graph inserting nodes in `order`, then adding `edges`.
fn build(order: &[usize], edges: &[(usize, usize)]) -> Graph {
    let mut g = Graph::strict();
    for &node in order {
        let _ = g.add_node(node.to_string());
    }
    for &(u, v) in edges {
        let _ = g.add_edge(u.to_string(), v.to_string());
    }
    g
}

fn betweenness_map(g: &Graph) -> HashMap<String, f64> {
    betweenness_centrality(g)
        .scores
        .into_iter()
        .map(|s| (s.node, s.score))
        .collect()
}
fn closeness_map(g: &Graph) -> HashMap<String, f64> {
    closeness_centrality(g)
        .scores
        .into_iter()
        .map(|s| (s.node, s.score))
        .collect()
}
fn harmonic_map(g: &Graph) -> HashMap<String, f64> {
    harmonic_centrality(g)
        .scores
        .into_iter()
        .map(|s| (s.node, s.score))
        .collect()
}

/// Deterministic SplitMix64 — reproducible graph shapes without an rng dep.
struct Rng(u64);
impl Rng {
    fn next(&mut self) -> u64 {
        self.0 = self.0.wrapping_add(0x9E37_79B9_7F4A_7C15);
        let mut z = self.0;
        z = (z ^ (z >> 30)).wrapping_mul(0xBF58_476D_1CE4_E5B9);
        z = (z ^ (z >> 27)).wrapping_mul(0x94D0_49BB_1331_11EB);
        z ^ (z >> 31)
    }
    fn below(&mut self, b: usize) -> usize {
        (self.next() % b as u64) as usize
    }
}

/// Connected sparse graph (spanning path + random extra edges), fixed seed.
fn sparse_edges(n: usize, avg_deg: usize, seed: u64) -> Vec<(usize, usize)> {
    let mut edges: Vec<(usize, usize)> = (0..n.saturating_sub(1)).map(|i| (i, i + 1)).collect();
    let target = n.saturating_mul(avg_deg) / 2;
    let mut rng = Rng(seed);
    let mut seen: std::collections::HashSet<(usize, usize)> = edges
        .iter()
        .map(|&(a, b)| if a < b { (a, b) } else { (b, a) })
        .collect();
    let mut guard = 0;
    while edges.len() < target && guard < target * 8 + 16 {
        guard += 1;
        let (u, v) = (rng.below(n), rng.below(n));
        if u == v {
            continue;
        }
        let key = if u < v { (u, v) } else { (v, u) };
        if seen.insert(key) {
            edges.push((u, v));
        }
    }
    edges
}

fn assert_maps_close(a: &HashMap<String, f64>, b: &HashMap<String, f64>, label: &str) {
    assert_eq!(a.len(), b.len(), "{label}: node count differs");
    for (k, va) in a {
        let vb = b
            .get(k)
            .unwrap_or_else(|| panic!("{label}: node {k} missing in permuted graph"));
        let diff = (va - vb).abs();
        let tol = 1e-9 * va.abs().max(1.0);
        assert!(
            diff <= tol,
            "{label}: node {k} score diverges across insertion order: {va} vs {vb} (diff {diff})"
        );
    }
}

/// Permutation must not change per-node centrality scores.
#[test]
fn centrality_is_insertion_order_invariant() {
    for &(n, deg, seed) in &[(60usize, 6usize, 1u64), (120, 8, 7), (200, 4, 42), (90, 10, 99)] {
        let edges = sparse_edges(n, deg, seed);
        let canonical: Vec<usize> = (0..n).collect();
        // Reverse insertion order — a maximally different ordering.
        let reversed: Vec<usize> = (0..n).rev().collect();
        // A shuffled order, deterministic.
        let mut shuffled = canonical.clone();
        let mut rng = Rng(seed ^ 0xDEAD_BEEF);
        for i in (1..n).rev() {
            shuffled.swap(i, rng.below(i + 1));
        }

        let g0 = build(&canonical, &edges);
        for order in [&reversed, &shuffled] {
            let g1 = build(order, &edges);
            assert_maps_close(&betweenness_map(&g0), &betweenness_map(&g1), "betweenness");
            assert_maps_close(&closeness_map(&g0), &closeness_map(&g1), "closeness");
            assert_maps_close(&harmonic_map(&g0), &harmonic_map(&g1), "harmonic");
        }
    }
}

/// Absolute structural anchors (independent of any oracle) that the optimized
/// implementations must still satisfy.
#[test]
fn centrality_structural_anchors() {
    // Path 0-1-2-3-4: endpoints have zero betweenness; the middle node is highest.
    let path: Vec<(usize, usize)> = vec![(0, 1), (1, 2), (2, 3), (3, 4)];
    let g = build(&(0..5).collect::<Vec<_>>(), &path);
    let bc = betweenness_map(&g);
    assert!(bc["0"].abs() < 1e-12, "path endpoint betweenness must be 0");
    assert!(bc["4"].abs() < 1e-12, "path endpoint betweenness must be 0");
    assert!(
        bc["2"] > bc["1"] && bc["2"] > bc["0"],
        "path center must have the highest betweenness"
    );

    // Star: center reaches everyone in 1 hop → strictly highest closeness.
    let star: Vec<(usize, usize)> = (1..=6).map(|i| (0, i)).collect();
    let g = build(&(0..7).collect::<Vec<_>>(), &star);
    let cc = closeness_map(&g);
    for leaf in 1..=6 {
        assert!(
            cc["0"] > cc[&leaf.to_string()],
            "star center closeness must exceed every leaf"
        );
    }
}
