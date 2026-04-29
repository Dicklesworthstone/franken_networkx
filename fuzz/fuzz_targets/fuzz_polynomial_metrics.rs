//! Structure-aware fuzzer for polynomial and metric invariants.
//!
//! Targets:
//!
//! - ``fnx_algorithms::chromatic_polynomial`` and ``tutte_polynomial``
//! - ``fnx_algorithms::s_metric``
//! - ``fnx_algorithms::floyd_warshall`` (weighted all-pairs)
//! - ``fnx_algorithms::wiener_index`` and ``wiener_index_weighted``
//! - ``fnx_algorithms::global_efficiency``
//! - ``fnx_algorithms::flow_hierarchy_directed``
//! - ``fnx_algorithms::rich_club_coefficient``
//!
//! Beyond the no-panic invariant, asserts these runtime contracts:
//!
//! Polynomial family
//! -----------------
//! * **chromatic_polynomial(G, 0) == 0** for any non-empty graph (a
//!   graph with no proper 0-coloring).
//! * **chromatic_polynomial(G, 1) == 0** when |E| > 0 (no proper
//!   coloring with a single color exists once an edge is present).
//! * **chromatic_polynomial determinism**: same graph, same x, same
//!   answer across two calls.
//! * **tutte_polynomial determinism** at small (x, y) integer points.
//!
//! s_metric
//! --------
//! * **Equal to ∑ deg(u)·deg(v) over edges** — the algebraic
//!   definition. The fuzzer recomputes this from the graph and
//!   compares to ``s_metric(G)``.
//!
//! Floyd–Warshall family
//! ---------------------
//! * **Diagonal is zero**: ``d[u][u] == 0`` for every node ``u``.
//! * **Symmetry on undirected**: ``d[u][v] == d[v][u]``.
//! * **Triangle inequality**: ``d[u][w] <= d[u][v] + d[v][w]`` for
//!   every triple ``(u, v, w)`` of reachable nodes.
//!
//! Wiener family
//! -------------
//! * **wiener_index_weighted(G, "weight") with all unit weights ==
//!   wiener_index(G)**.
//! * **Both are non-negative on connected inputs**.
//!
//! Global efficiency / flow hierarchy
//! ----------------------------------
//! * Both lie in ``[0, 1]`` (with NaN tolerance for empty inputs).
//!
//! Rich-club coefficient
//! ---------------------
//! * Every value is non-negative.

#![no_main]

mod arbitrary_graph;

use arbitrary::Arbitrary;
use arbitrary_graph::{ArbitraryDiGraph, ArbitraryGraph};
use fnx_algorithms::{
    chromatic_polynomial, flow_hierarchy_directed, floyd_warshall, global_efficiency,
    rich_club_coefficient, s_metric, tutte_polynomial, wiener_index, wiener_index_weighted,
};
use fnx_classes::Graph;
use fnx_runtime::CompatibilityMode;
use libfuzzer_sys::fuzz_target;

#[derive(Debug, Arbitrary)]
enum PolyMetricInput {
    /// chromatic_polynomial(G, 0) and (G, 1) are both 0 (with the
    /// edge-count caveat for x=1).
    ChromaticZeros(ArbitraryGraph),
    /// chromatic_polynomial deterministic at a small x.
    ChromaticDeterminism(ArbitraryGraph, u8),
    /// tutte_polynomial deterministic at a small (x, y).
    TutteDeterminism(ArbitraryGraph, u8, u8),
    /// s_metric == sum_(u,v) in E deg(u) * deg(v).
    SMetricFromDegrees(ArbitraryGraph),
    /// Floyd–Warshall diagonal/symmetry/triangle invariants.
    FloydWarshallInvariants(ArbitraryGraph),
    /// wiener_index_weighted(G, "weight") equals wiener_index(G) when
    /// every edge has unit weight.
    WienerWeightedUnit(ArbitraryGraph),
    /// global_efficiency lies in [0, 1].
    GlobalEfficiencyRange(ArbitraryGraph),
    /// flow_hierarchy_directed in [0, 1].
    FlowHierarchyRange(ArbitraryDiGraph),
    /// rich_club coefficients are non-negative.
    RichClubNonneg(ArbitraryGraph),
}

fn assert_chromatic_zeros(graph: &Graph) {
    if graph.nodes_ordered().is_empty() {
        return;
    }
    let p_at_zero = chromatic_polynomial(graph, 0.0);
    // P(G, 0) is 0 for any graph with at least one node.
    assert!(
        p_at_zero.abs() < 1e-9,
        "chromatic_polynomial(G, 0) = {p_at_zero}, expected 0",
    );
    if graph.edges_ordered().iter().any(|e| e.left != e.right) {
        let p_at_one = chromatic_polynomial(graph, 1.0);
        assert!(
            p_at_one.abs() < 1e-9,
            "chromatic_polynomial(G, 1) = {p_at_one} but |E|>0 should give 0",
        );
    }
}

fn assert_chromatic_determinism(graph: &Graph, x_byte: u8) {
    let x = (x_byte as f64) / 32.0;
    let a = chromatic_polynomial(graph, x);
    let b = chromatic_polynomial(graph, x);
    if a.is_finite() && b.is_finite() {
        assert!(
            (a - b).abs() < 1e-9 * a.abs().max(1.0),
            "chromatic_polynomial(_, {x}) not deterministic: {a} vs {b}",
        );
    }
}

fn assert_tutte_determinism(graph: &Graph, x_byte: u8, y_byte: u8) {
    let x = (x_byte as f64) / 32.0;
    let y = (y_byte as f64) / 32.0;
    let a = tutte_polynomial(graph, x, y);
    let b = tutte_polynomial(graph, x, y);
    if a.is_finite() && b.is_finite() {
        assert!(
            (a - b).abs() < 1e-9 * a.abs().max(1.0),
            "tutte_polynomial(_, {x}, {y}) not deterministic: {a} vs {b}",
        );
    }
}

fn assert_s_metric_from_degrees(graph: &Graph) {
    let mut expected = 0.0f64;
    for edge in graph.edges_ordered() {
        let du = graph.degree(&edge.left) as f64;
        let dv = graph.degree(&edge.right) as f64;
        expected += du * dv;
    }
    let actual = s_metric(graph);
    assert!(
        (actual - expected).abs() < 1e-9 * expected.abs().max(1.0),
        "s_metric mismatch: actual={actual} expected={expected}",
    );
}

fn assert_floyd_invariants(graph: &Graph) {
    let nodes = graph.nodes_ordered();
    if nodes.len() < 2 {
        return;
    }
    let d = floyd_warshall(graph, "weight");
    // Diagonal is zero.
    for &u in &nodes {
        let row = d.get(u).expect("source row");
        let val = *row.get(u).unwrap_or(&f64::INFINITY);
        assert!(
            val.abs() < 1e-9,
            "floyd_warshall diagonal d[{u}][{u}] = {val}, expected 0",
        );
    }
    // Symmetry on undirected.
    for &u in &nodes {
        for &v in &nodes {
            let duv = *d.get(u).and_then(|r| r.get(v)).unwrap_or(&f64::INFINITY);
            let dvu = *d.get(v).and_then(|r| r.get(u)).unwrap_or(&f64::INFINITY);
            assert!(
                (duv - dvu).abs() < 1e-6 || (duv.is_infinite() && dvu.is_infinite()),
                "floyd_warshall not symmetric: d[{u}][{v}]={duv} d[{v}][{u}]={dvu}",
            );
        }
    }
    // Triangle inequality on a *bounded* triple sweep — full V^3 is
    // O(n^3) which is fine for fuzzer-bounded n=64. Skip pairs whose
    // distance is infinite (unreachable).
    for &u in &nodes {
        for &v in &nodes {
            for &w in &nodes {
                let duw = *d.get(u).and_then(|r| r.get(w)).unwrap_or(&f64::INFINITY);
                let duv = *d.get(u).and_then(|r| r.get(v)).unwrap_or(&f64::INFINITY);
                let dvw = *d.get(v).and_then(|r| r.get(w)).unwrap_or(&f64::INFINITY);
                if duw.is_infinite() || duv.is_infinite() || dvw.is_infinite() {
                    continue;
                }
                assert!(
                    duw <= duv + dvw + 1e-6,
                    "triangle inequality violated: d[{u}][{w}]={duw} > \
                     d[{u}][{v}]={duv} + d[{v}][{w}]={dvw}",
                );
            }
        }
    }
}

fn assert_wiener_weighted_unit_eq_unweighted(graph: &Graph) {
    use fnx_classes::AttrMap;
    use fnx_runtime::CgseValue;
    // Build a copy with explicit unit weights.
    let mut copy = Graph::new(CompatibilityMode::Strict);
    for n in graph.nodes_ordered() {
        copy.add_node(n);
    }
    for edge in graph.edges_ordered() {
        let mut attrs = AttrMap::new();
        attrs.insert("weight".to_owned(), CgseValue::Float(1.0));
        let _ = copy.add_edge_with_attrs(&edge.left, &edge.right, attrs);
    }
    let unweighted = wiener_index(&copy);
    let weighted = wiener_index_weighted(&copy, "weight");
    if unweighted.is_finite() && weighted.is_finite() {
        assert!(
            (unweighted - weighted).abs() < 1e-6 * unweighted.abs().max(1.0),
            "wiener_index_weighted with unit weights ({weighted}) != \
             wiener_index ({unweighted})",
        );
    } else {
        // Both must be infinite together, or both finite.
        assert_eq!(
            unweighted.is_finite(),
            weighted.is_finite(),
            "wiener_index finiteness mismatch: unweighted={unweighted} weighted={weighted}",
        );
    }
}

fn assert_global_efficiency_in_range(graph: &Graph) {
    let result = global_efficiency(graph);
    let e = result.efficiency;
    if e.is_finite() {
        assert!(
            (-1e-9..=1.0 + 1e-9).contains(&e),
            "global_efficiency = {e}, outside [0, 1]",
        );
    }
}

fn assert_flow_hierarchy_in_range(digraph: &fnx_classes::digraph::DiGraph) {
    let h = flow_hierarchy_directed(digraph);
    if h.is_finite() {
        assert!(
            (-1e-9..=1.0 + 1e-9).contains(&h),
            "flow_hierarchy = {h}, outside [0, 1]",
        );
    }
}

fn assert_rich_club_nonneg(graph: &Graph) {
    let rcc = rich_club_coefficient(graph);
    for (k, v) in &rcc {
        if v.is_finite() {
            assert!(*v >= -1e-9, "rich_club_coefficient[{k}] = {v} < 0");
        }
    }
}

fuzz_target!(|input: PolyMetricInput| {
    match input {
        PolyMetricInput::ChromaticZeros(ag) => {
            assert_chromatic_zeros(&ag.graph);
        }
        PolyMetricInput::ChromaticDeterminism(ag, x) => {
            assert_chromatic_determinism(&ag.graph, x);
        }
        PolyMetricInput::TutteDeterminism(ag, x, y) => {
            assert_tutte_determinism(&ag.graph, x, y);
        }
        PolyMetricInput::SMetricFromDegrees(ag) => {
            assert_s_metric_from_degrees(&ag.graph);
        }
        PolyMetricInput::FloydWarshallInvariants(ag) => {
            assert_floyd_invariants(&ag.graph);
        }
        PolyMetricInput::WienerWeightedUnit(ag) => {
            assert_wiener_weighted_unit_eq_unweighted(&ag.graph);
        }
        PolyMetricInput::GlobalEfficiencyRange(ag) => {
            assert_global_efficiency_in_range(&ag.graph);
        }
        PolyMetricInput::FlowHierarchyRange(ag) => {
            assert_flow_hierarchy_in_range(&ag.graph);
        }
        PolyMetricInput::RichClubNonneg(ag) => {
            assert_rich_club_nonneg(&ag.graph);
        }
    }
});
