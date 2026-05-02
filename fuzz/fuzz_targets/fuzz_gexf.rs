//! Fuzz target for the GEXF parser boundary.
#![no_main]

use libfuzzer_sys::fuzz_target;

fuzz_target!(|data: &[u8]| {
    let Ok(input) = std::str::from_utf8(data) else {
        return;
    };

    // For each successful parse, assert the fundamental I/O-parser
    // invariant: every emitted edge's endpoints are members of the
    // parsed graph's node set.
    let mut strict = fnx_readwrite::EdgeListEngine::strict();
    if let Ok(report) = strict.read_gexf(input) {
        for edge in report.graph.edges_ordered() {
            assert!(
                report.graph.has_node(&edge.left),
                "gexf (strict): edge endpoint {} not in node set",
                edge.left
            );
            assert!(
                report.graph.has_node(&edge.right),
                "gexf (strict): edge endpoint {} not in node set",
                edge.right
            );
        }
    }

    let mut hardened = fnx_readwrite::EdgeListEngine::hardened();
    if let Ok(report) = hardened.read_gexf(input) {
        for edge in report.graph.edges_ordered() {
            assert!(
                report.graph.has_node(&edge.left),
                "gexf (hardened): edge endpoint {} not in node set",
                edge.left
            );
            assert!(
                report.graph.has_node(&edge.right),
                "gexf (hardened): edge endpoint {} not in node set",
                edge.right
            );
        }
    }

    let mut strict_di = fnx_readwrite::EdgeListEngine::strict();
    if let Ok(report) = strict_di.read_digraph_gexf(input) {
        for edge in report.graph.edges_ordered() {
            assert!(
                report.graph.has_node(&edge.left),
                "gexf digraph (strict): edge endpoint {} not in node set",
                edge.left
            );
            assert!(
                report.graph.has_node(&edge.right),
                "gexf digraph (strict): edge endpoint {} not in node set",
                edge.right
            );
        }
    }

    let mut hardened_di = fnx_readwrite::EdgeListEngine::hardened();
    if let Ok(report) = hardened_di.read_digraph_gexf(input) {
        for edge in report.graph.edges_ordered() {
            assert!(
                report.graph.has_node(&edge.left),
                "gexf digraph (hardened): edge endpoint {} not in node set",
                edge.left
            );
            assert!(
                report.graph.has_node(&edge.right),
                "gexf digraph (hardened): edge endpoint {} not in node set",
                edge.right
            );
        }
    }

    // Directed detection helper — keep panic-only since the boolean
    // result is well-defined for malformed input.
    let mut directed_detector = fnx_readwrite::EdgeListEngine::strict();
    let _ = directed_detector.gexf_declares_directed(input);
});
