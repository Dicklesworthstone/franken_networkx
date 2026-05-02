#![no_main]

use libfuzzer_sys::fuzz_target;

fuzz_target!(|data: &[u8]| {
    let Ok(input) = std::str::from_utf8(data) else {
        return;
    };

    // Strict mode: must return Err or Ok, never panic. For successful
    // parses, assert the fundamental I/O-parser invariant: every
    // emitted edge's endpoints are members of the parsed graph's
    // node set.
    let mut strict = fnx_readwrite::EdgeListEngine::strict();
    if let Ok(report) = strict.read_adjlist(input) {
        for edge in report.graph.edges_ordered() {
            assert!(
                report.graph.has_node(&edge.left),
                "adjlist (strict): edge endpoint {} not in node set",
                edge.left
            );
            assert!(
                report.graph.has_node(&edge.right),
                "adjlist (strict): edge endpoint {} not in node set",
                edge.right
            );
        }
    }

    // Hardened mode: must return Ok with warnings or Ok empty, never panic.
    let mut hardened = fnx_readwrite::EdgeListEngine::hardened();
    if let Ok(report) = hardened.read_adjlist(input) {
        for edge in report.graph.edges_ordered() {
            assert!(
                report.graph.has_node(&edge.left),
                "adjlist (hardened): edge endpoint {} not in node set",
                edge.left
            );
            assert!(
                report.graph.has_node(&edge.right),
                "adjlist (hardened): edge endpoint {} not in node set",
                edge.right
            );
        }
    }

    // DiGraph variants.
    let mut strict_di = fnx_readwrite::EdgeListEngine::strict();
    if let Ok(report) = strict_di.read_digraph_adjlist(input) {
        for edge in report.graph.edges_ordered() {
            assert!(
                report.graph.has_node(&edge.left),
                "adjlist digraph (strict): edge endpoint {} not in node set",
                edge.left
            );
            assert!(
                report.graph.has_node(&edge.right),
                "adjlist digraph (strict): edge endpoint {} not in node set",
                edge.right
            );
        }
    }

    let mut hardened_di = fnx_readwrite::EdgeListEngine::hardened();
    if let Ok(report) = hardened_di.read_digraph_adjlist(input) {
        for edge in report.graph.edges_ordered() {
            assert!(
                report.graph.has_node(&edge.left),
                "adjlist digraph (hardened): edge endpoint {} not in node set",
                edge.left
            );
            assert!(
                report.graph.has_node(&edge.right),
                "adjlist digraph (hardened): edge endpoint {} not in node set",
                edge.right
            );
        }
    }
});
