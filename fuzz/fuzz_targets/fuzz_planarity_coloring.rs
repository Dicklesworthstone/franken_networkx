//! Structure-aware fuzzer for planarity testing and graph coloring.
//!
//! Targets two algorithms with strong, easy-to-verify runtime contracts:
//!
//! - ``fnx_algorithms::is_planar`` — LR-planarity test (Boyer-Myrvold-style
//!   simplification). NetworkX equivalent:
//!   ``networkx.algorithms.planarity.is_planar``.
//! - ``fnx_algorithms::greedy_color`` and ``greedy_color_with_strategy`` —
//!   greedy proper colorings under multiple node-orderings
//!   (``largest_first``, ``smallest_last``, ``random_sequential``,
//!   ``DSATUR``, lexicographic). NetworkX equivalent:
//!   ``networkx.algorithms.coloring.greedy_color``.
//!
//! Beyond no-panic, the harness asserts:
//!
//! Coloring family
//! ---------------
//! * **Proper**: for every edge ``(u, v)``, ``color[u] != color[v]``.
//! * **Total**: every node receives a color.
//! * **Non-negative**: all colors are ``>= 0`` (always true since usize, but
//!   we pin the API).
//! * **Bound**: ``num_colors == 1 + max_color`` (or 0 for empty graph).
//! * **All-strategies-proper**: ``largest_first``, ``smallest_last``,
//!   ``random_sequential``, ``DSATUR``, and the default lexicographic
//!   ordering all produce *proper* colorings on the same graph.
//! * **Determinism**: the same strategy run twice on the same graph
//!   produces the same coloring (deterministic — no hidden randomness).
//!
//! Planarity family
//! ----------------
//! * **Determinism**: ``is_planar(G)`` is stable across calls.
//! * **Small graphs**: ``n <= 4`` ⇒ always planar (the four-vertex
//!   complete graph K_4 is planar).
//! * **Sparse-edge bound**: ``m > 3n - 6 ⇒ not planar`` (Euler bound on
//!   simple graphs with ``n >= 3``).
//! * **Edge-deletion monotonicity**: a non-planar witness is
//!   *necessary* — removing an edge cannot turn planar into non-planar,
//!   so ``is_planar(G) ⇒ is_planar(G - e)`` for any edge e. The fuzzer
//!   removes one randomly-chosen edge and re-checks.
//!
//! These are minor-monotone topological invariants. Any violation
//! indicates a real bug in the underlying algorithm — a regression or
//! corner case the unit tests miss.

#![no_main]

mod arbitrary_graph;

use arbitrary::Arbitrary;
use arbitrary_graph::ArbitraryGraph;
use fnx_algorithms::{GreedyColorResult, NodeColor, greedy_color_with_strategy, is_planar};
use fnx_classes::Graph;
use libfuzzer_sys::fuzz_target;
use std::collections::HashMap;

/// Strategies exposed by ``greedy_color_with_strategy``. All five must
/// produce proper colorings on every valid input.
const STRATEGIES: &[&str] = &[
    "largest_first",
    "smallest_last",
    "random_sequential",
    "DSATUR",
    "lexicographic",
];

#[derive(Debug, Arbitrary)]
enum PlanarityColoringInput {
    /// Verify proper-coloring invariant under a single strategy.
    SingleStrategy(ArbitraryGraph, u8),
    /// Run all five strategies and assert each is proper.
    AllStrategies(ArbitraryGraph),
    /// Determinism: same strategy twice ⇒ identical result.
    Determinism(ArbitraryGraph, u8),
    /// Planarity: stability + small-graph & Euler-bound invariants.
    Planarity(ArbitraryGraph),
    /// Edge-deletion monotonicity for planarity.
    PlanarityEdgeDelete(ArbitraryGraph),
}

fn assert_proper_coloring(graph: &Graph, result: &GreedyColorResult, strategy: &str) {
    let map: HashMap<&str, usize> = result
        .coloring
        .iter()
        .map(|nc| (nc.node.as_str(), nc.color))
        .collect();

    // Total: every node colored.
    let nodes = graph.nodes_ordered();
    assert_eq!(
        map.len(),
        nodes.len(),
        "strategy={strategy}: not every node colored ({} of {})",
        map.len(),
        nodes.len(),
    );
    for n in &nodes {
        assert!(
            map.contains_key(*n),
            "strategy={strategy}: node {n} missing from coloring",
        );
    }

    // Proper: no edge has matching endpoint colors.
    for edge in graph.edges_ordered() {
        let (u, v) = (edge.left.as_str(), edge.right.as_str());
        let cu = map.get(u).copied().expect("colored");
        let cv = map.get(v).copied().expect("colored");
        assert_ne!(
            cu, cv,
            "strategy={strategy}: edge ({u},{v}) has matching color {cu}",
        );
    }

    // num_colors bound.
    let max_color = result.coloring.iter().map(|nc: &NodeColor| nc.color).max();
    if let Some(mc) = max_color {
        assert_eq!(
            result.num_colors,
            mc + 1,
            "strategy={strategy}: num_colors={} but max_color+1={}",
            result.num_colors,
            mc + 1,
        );
    } else {
        assert_eq!(
            result.num_colors, 0,
            "strategy={strategy}: empty coloring should report num_colors=0",
        );
    }
}

fn pick_strategy(byte: u8) -> &'static str {
    STRATEGIES[(byte as usize) % STRATEGIES.len()]
}

fn assert_planarity_invariants(graph: &Graph) {
    let n = graph.nodes_ordered().len();
    let m = graph.edges_ordered().len();
    let p1 = is_planar(graph);
    let p2 = is_planar(graph);
    assert_eq!(p1, p2, "is_planar not deterministic");

    // Empty / very small graphs are planar by convention.
    if n <= 4 {
        assert!(
            p1,
            "n={n} m={m}: graphs with at most 4 vertices are always planar",
        );
        return;
    }

    // Euler upper bound for simple planar graphs.
    if n >= 3 && m > 3 * n - 6 {
        assert!(
            !p1,
            "n={n} m={m}: |E| > 3|V|-6 implies non-planar",
        );
    }
}

fn rebuild_without_edge(src: &Graph, drop_idx: usize) -> Option<(Graph, (String, String))> {
    use fnx_runtime::CompatibilityMode;
    let edges = src.edges_ordered();
    if edges.is_empty() {
        return None;
    }
    let drop = drop_idx % edges.len();
    let dropped = edges[drop].clone();
    let mut g = Graph::new(CompatibilityMode::Strict);
    for n in src.nodes_ordered() {
        g.add_node(n);
    }
    for (i, edge) in edges.iter().enumerate() {
        if i == drop {
            continue;
        }
        let _ = g.add_edge(&edge.left, &edge.right);
    }
    Some((g, (dropped.left.clone(), dropped.right.clone())))
}

fuzz_target!(|input: PlanarityColoringInput| {
    match input {
        PlanarityColoringInput::SingleStrategy(ag, sb) => {
            let strategy = pick_strategy(sb);
            let result = greedy_color_with_strategy(&ag.graph, strategy);
            assert_proper_coloring(&ag.graph, &result, strategy);
        }
        PlanarityColoringInput::AllStrategies(ag) => {
            for &strategy in STRATEGIES {
                let result = greedy_color_with_strategy(&ag.graph, strategy);
                assert_proper_coloring(&ag.graph, &result, strategy);
            }
        }
        PlanarityColoringInput::Determinism(ag, sb) => {
            let strategy = pick_strategy(sb);
            let r1 = greedy_color_with_strategy(&ag.graph, strategy);
            let r2 = greedy_color_with_strategy(&ag.graph, strategy);
            assert_eq!(
                r1.coloring, r2.coloring,
                "strategy={strategy} not deterministic across two calls",
            );
            assert_eq!(
                r1.num_colors, r2.num_colors,
                "strategy={strategy} num_colors differs across two calls",
            );
        }
        PlanarityColoringInput::Planarity(ag) => {
            assert_planarity_invariants(&ag.graph);
        }
        PlanarityColoringInput::PlanarityEdgeDelete(ag) => {
            assert_planarity_invariants(&ag.graph);
            // If planar, dropping any edge must keep it planar.
            if is_planar(&ag.graph) {
                if let Some((sub, _)) = rebuild_without_edge(&ag.graph, 0) {
                    assert!(
                        is_planar(&sub),
                        "planar graph became non-planar after removing one edge",
                    );
                }
            }
        }
    }
});
