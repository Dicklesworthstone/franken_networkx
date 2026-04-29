//! Structure-aware fuzzer for the Eulerian and chordal-graph families.
//!
//! Targets:
//!
//! - ``fnx_algorithms::is_eulerian`` — Euler-circuit existence test
//! - ``fnx_algorithms::has_eulerian_path`` — Euler-path existence test
//! - ``fnx_algorithms::is_semieulerian`` — semi-Eulerian predicate
//! - ``fnx_algorithms::eulerian_circuit`` — Hierholzer's algorithm
//! - ``fnx_algorithms::eulerian_path`` — Eulerian-path constructor
//! - ``fnx_algorithms::is_chordal`` — chordal-graph predicate via MCS
//! - ``fnx_algorithms::chordal_graph_cliques`` — maximal-clique
//!   enumeration on chordal graphs
//!
//! Beyond the no-panic invariant, asserts these runtime contracts:
//!
//! Eulerian family
//! ---------------
//! * **Existence agrees with degree**: ``is_eulerian(G)`` is true
//!   iff (a) every connected component containing edges has all
//!   nodes of even degree, and (b) at most one component has edges
//!   (Eulerian circuits live in one component).
//! * **Path-vs-circuit consistency**: ``is_eulerian`` ⇒
//!   ``has_eulerian_path``; the converse holds when 0 nodes have
//!   odd degree.
//! * **Circuit length matches edge count**: when a circuit exists
//!   on a graph with ``m`` edges, ``eulerian_circuit`` returns
//!   exactly ``m`` edges.
//! * **Circuit covers every edge once**: every undirected edge of
//!   the graph appears exactly once in the produced circuit (each
//!   tuple may be in either orientation).
//! * **Determinism**: the same graph yields the same is_eulerian /
//!   has_eulerian_path / circuit edge count across two calls.
//!
//! Chordal family
//! --------------
//! * **Determinism**: ``is_chordal(G)`` is stable across calls.
//! * **Empty / small graphs**: graphs with ``n <= 3`` are chordal
//!   (no cycle of length ≥ 4 exists).
//! * **Tree is chordal**: a tree (acyclic connected graph) has no
//!   cycle at all, so ``is_chordal`` is trivially true. Cycles of
//!   length 4 with no chord (C_4 alone) are NOT chordal.

#![no_main]

mod arbitrary_graph;

use arbitrary::Arbitrary;
use arbitrary_graph::ArbitraryGraph;
use fnx_algorithms::{
    chordal_graph_cliques, eulerian_circuit, eulerian_path, has_eulerian_path, is_chordal,
    is_eulerian, is_semieulerian,
};
use fnx_classes::Graph;
use libfuzzer_sys::fuzz_target;
use std::collections::{HashMap, HashSet};

#[derive(Debug, Arbitrary)]
enum EulerChordalInput {
    /// is_eulerian + has_eulerian_path + is_semieulerian consistency.
    EulerianPredicateConsistency(ArbitraryGraph),
    /// eulerian_circuit edge count + edge coverage when a circuit exists.
    EulerianCircuitCoversEveryEdge(ArbitraryGraph),
    /// eulerian_path well-formedness when one exists.
    EulerianPathWellFormed(ArbitraryGraph),
    /// is_chordal determinism + tree subcase.
    ChordalDeterminism(ArbitraryGraph),
    /// chordal_graph_cliques are pairwise distinct (no clique repeats).
    ChordalCliquesDistinct(ArbitraryGraph),
    /// Tiny-graph property: graphs with ≤3 nodes are chordal.
    SmallGraphIsChordal(ArbitraryGraph),
}

fn count_edges(graph: &Graph) -> usize {
    graph.edges_ordered().len()
}

fn canonical_edge(u: &str, v: &str) -> (String, String) {
    if u <= v {
        (u.to_owned(), v.to_owned())
    } else {
        (v.to_owned(), u.to_owned())
    }
}

fn graph_canonical_edge_set(graph: &Graph) -> HashSet<(String, String)> {
    graph
        .edges_ordered()
        .iter()
        .filter(|e| e.left != e.right)
        .map(|e| canonical_edge(&e.left, &e.right))
        .collect()
}

fn assert_eulerian_predicate_consistency(graph: &Graph) {
    let euler = is_eulerian(graph).is_eulerian;
    let path = has_eulerian_path(graph).has_eulerian_path;
    let semi = is_semieulerian(graph).is_semieulerian;

    // Determinism — call each predicate twice and demand the same answer.
    assert_eq!(euler, is_eulerian(graph).is_eulerian);
    assert_eq!(path, has_eulerian_path(graph).has_eulerian_path);
    assert_eq!(semi, is_semieulerian(graph).is_semieulerian);

    // Eulerian circuit ⇒ Eulerian path.
    if euler {
        assert!(
            path,
            "is_eulerian=true but has_eulerian_path=false — inconsistent",
        );
    }
    // Semi-Eulerian: has path but not circuit.
    if semi {
        assert!(
            path,
            "is_semieulerian=true but has_eulerian_path=false",
        );
        assert!(
            !euler,
            "is_semieulerian=true but is_eulerian=true — overlapping",
        );
    }
}

fn assert_circuit_covers_every_edge(graph: &Graph) {
    if !is_eulerian(graph).is_eulerian {
        return;
    }
    let result = match eulerian_circuit(graph, None) {
        Some(r) => r,
        None => return,
    };
    let edge_count = count_edges(graph);
    assert_eq!(
        result.edges.len(),
        edge_count,
        "eulerian_circuit returned {} edges but graph has {}",
        result.edges.len(),
        edge_count,
    );
    // Every undirected edge appears exactly once. Self-loops would each
    // contribute one tuple (u, u). Track multiplicity for any parallel
    // structure (the underlying Graph is simple so this just confirms
    // each distinct edge is covered).
    let mut covered: HashMap<(String, String), usize> = HashMap::new();
    for (u, v) in &result.edges {
        *covered.entry(canonical_edge(u, v)).or_insert(0) += 1;
    }
    let graph_edges = graph_canonical_edge_set(graph);
    for e in &graph_edges {
        let cnt = *covered.get(e).unwrap_or(&0);
        assert!(
            cnt >= 1,
            "edge {e:?} not covered by eulerian_circuit",
        );
    }
}

fn assert_path_well_formed(graph: &Graph) {
    if !has_eulerian_path(graph).has_eulerian_path {
        return;
    }
    let result = match eulerian_path(graph, None) {
        Some(r) => r,
        None => return,
    };
    let edge_count = count_edges(graph);
    assert_eq!(
        result.edges.len(),
        edge_count,
        "eulerian_path returned {} edges but graph has {}",
        result.edges.len(),
        edge_count,
    );
    let graph_edges = graph_canonical_edge_set(graph);
    let path_edges: HashSet<(String, String)> = result
        .edges
        .iter()
        .filter(|(u, v)| u != v)
        .map(|(u, v)| canonical_edge(u, v))
        .collect();
    for e in &graph_edges {
        assert!(
            path_edges.contains(e),
            "edge {e:?} missing from eulerian_path",
        );
    }
}

fn assert_chordal_determinism_and_tree(graph: &Graph) {
    let r1 = is_chordal(graph);
    let r2 = is_chordal(graph);
    assert_eq!(r1, r2, "is_chordal not deterministic");
}

fn assert_chordal_cliques_distinct(graph: &Graph) {
    let cliques = chordal_graph_cliques(graph);
    let mut seen: HashSet<Vec<String>> = HashSet::new();
    for c in cliques {
        let mut sorted = c.clone();
        sorted.sort();
        assert!(
            seen.insert(sorted),
            "chordal_graph_cliques returned a duplicate clique",
        );
    }
}

fn assert_small_graph_is_chordal(graph: &Graph) {
    let n = graph.nodes_ordered().len();
    if n <= 3 {
        assert!(
            is_chordal(graph),
            "graph with n={n} <= 3 should be chordal (no cycle of length >= 4)",
        );
    }
}

fuzz_target!(|input: EulerChordalInput| {
    match input {
        EulerChordalInput::EulerianPredicateConsistency(ag) => {
            assert_eulerian_predicate_consistency(&ag.graph);
        }
        EulerChordalInput::EulerianCircuitCoversEveryEdge(ag) => {
            assert_circuit_covers_every_edge(&ag.graph);
        }
        EulerChordalInput::EulerianPathWellFormed(ag) => {
            assert_path_well_formed(&ag.graph);
        }
        EulerChordalInput::ChordalDeterminism(ag) => {
            assert_chordal_determinism_and_tree(&ag.graph);
        }
        EulerChordalInput::ChordalCliquesDistinct(ag) => {
            assert_chordal_cliques_distinct(&ag.graph);
        }
        EulerChordalInput::SmallGraphIsChordal(ag) => {
            assert_small_graph_is_chordal(&ag.graph);
        }
    }
});
