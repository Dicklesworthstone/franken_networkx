//! Structure-aware fuzzer for graph isomorphism algorithms.
//!
//! Drives the VF2 isomorphism check (`is_isomorphic`,
//! `is_isomorphic_directed`) and the cheaper invariant-based necessary
//! conditions (`could_be_isomorphic`, `faster_could_be_isomorphic`,
//! `faster_could_be_isomorphic_directed`, `fast_could_be_isomorphic`).
//!
//! In addition to checking that no input panics, asserts the implication
//! ``is_isomorphic(g1, g2) ==> could_be_isomorphic(g1, g2)``: the
//! cheaper invariant filter is a necessary condition. A failure here
//! means either VF2 returned a false positive or one of the invariant
//! checks rejected a genuine isomorph.

#![no_main]

mod arbitrary_graph;

use arbitrary::Arbitrary;
use arbitrary_graph::{ArbitraryDiGraph, ArbitraryGraph};
use libfuzzer_sys::fuzz_target;

#[derive(Debug, Arbitrary)]
enum IsomorphismInput {
    /// VF2 on a pair of undirected graphs.
    IsIsomorphic(ArbitraryGraph, ArbitraryGraph),
    /// VF2 on a pair of directed graphs.
    IsIsomorphicDirected(ArbitraryDiGraph, ArbitraryDiGraph),
    /// Necessary-condition checks on a pair of undirected graphs.
    CouldBeIsomorphic(ArbitraryGraph, ArbitraryGraph),
    /// Necessary-condition checks on a pair of directed graphs.
    FasterCouldBeIsomorphicDirected(ArbitraryDiGraph, ArbitraryDiGraph),
    /// VF2 against a graph compared with itself (must always be true).
    SelfIsomorphism(ArbitraryGraph),
    /// VF2 directed against itself (must always be true).
    SelfIsomorphismDirected(ArbitraryDiGraph),
}

fuzz_target!(|input: IsomorphismInput| {
    match input {
        IsomorphismInput::IsIsomorphic(a, b) => {
            let iso = fnx_algorithms::is_isomorphic(&a.graph, &b.graph);
            let could = fnx_algorithms::could_be_isomorphic(&a.graph, &b.graph);
            let faster = fnx_algorithms::faster_could_be_isomorphic(&a.graph, &b.graph);
            let fast = fnx_algorithms::fast_could_be_isomorphic(&a.graph, &b.graph);
            // Necessary-condition implications: a true VF2 result must
            // pass the cheaper filters.
            if iso {
                assert!(
                    could,
                    "is_isomorphic=true but could_be_isomorphic=false"
                );
                assert!(
                    faster,
                    "is_isomorphic=true but faster_could_be_isomorphic=false"
                );
                assert!(
                    fast,
                    "is_isomorphic=true but fast_could_be_isomorphic=false"
                );
            }
        }
        IsomorphismInput::IsIsomorphicDirected(a, b) => {
            let iso = fnx_algorithms::is_isomorphic_directed(&a.graph, &b.graph);
            let faster =
                fnx_algorithms::faster_could_be_isomorphic_directed(&a.graph, &b.graph);
            if iso {
                assert!(
                    faster,
                    "is_isomorphic_directed=true but \
                     faster_could_be_isomorphic_directed=false"
                );
            }
        }
        IsomorphismInput::CouldBeIsomorphic(a, b) => {
            let _ = fnx_algorithms::could_be_isomorphic(&a.graph, &b.graph);
            let _ = fnx_algorithms::faster_could_be_isomorphic(&a.graph, &b.graph);
            let _ = fnx_algorithms::fast_could_be_isomorphic(&a.graph, &b.graph);
        }
        IsomorphismInput::FasterCouldBeIsomorphicDirected(a, b) => {
            let _ =
                fnx_algorithms::faster_could_be_isomorphic_directed(&a.graph, &b.graph);
        }
        IsomorphismInput::SelfIsomorphism(g) => {
            assert!(
                fnx_algorithms::is_isomorphic(&g.graph, &g.graph),
                "graph not isomorphic to itself"
            );
        }
        IsomorphismInput::SelfIsomorphismDirected(g) => {
            assert!(
                fnx_algorithms::is_isomorphic_directed(&g.graph, &g.graph),
                "directed graph not isomorphic to itself"
            );
        }
    }
});
