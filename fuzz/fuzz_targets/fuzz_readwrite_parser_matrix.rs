//! Combined parser fuzzing for readwrite formats and compatibility modes.
#![no_main]

use fnx_classes::Graph;
use fnx_classes::digraph::DiGraph;
use fnx_readwrite::{DiReadWriteReport, EdgeListEngine, ReadWriteError, ReadWriteReport};
use libfuzzer_sys::fuzz_target;

const MAX_INPUT_BYTES: usize = 16 * 1024;

fn assert_graph_endpoints(graph: &Graph, context: &str) {
    for edge in graph.edges_ordered() {
        assert!(
            graph.has_node(&edge.left),
            "{context}: edge endpoint {} not in node set",
            edge.left
        );
        assert!(
            graph.has_node(&edge.right),
            "{context}: edge endpoint {} not in node set",
            edge.right
        );
    }
}

fn assert_digraph_endpoints(graph: &DiGraph, context: &str) {
    for edge in graph.edges_ordered() {
        assert!(
            graph.has_node(&edge.left),
            "{context}: edge endpoint {} not in node set",
            edge.left
        );
        assert!(
            graph.has_node(&edge.right),
            "{context}: edge endpoint {} not in node set",
            edge.right
        );
    }
}

fn check_graph(result: Result<ReadWriteReport, ReadWriteError>, context: &str) {
    if let Ok(report) = result {
        assert_graph_endpoints(&report.graph, context);
    }
}

fn check_digraph(result: Result<DiReadWriteReport, ReadWriteError>, context: &str) {
    if let Ok(report) = result {
        assert_digraph_endpoints(&report.graph, context);
    }
}

fuzz_target!(|data: &[u8]| {
    if data.len() < 2 || data.len() > MAX_INPUT_BYTES {
        return;
    }
    let selector = data[0];
    let Ok(input) = std::str::from_utf8(&data[1..]) else {
        return;
    };

    match selector % 16 {
        0 => {
            let mut engine = EdgeListEngine::strict();
            check_graph(engine.read_edgelist(input), "edgelist graph strict");
        }
        1 => {
            let mut engine = EdgeListEngine::hardened();
            check_graph(engine.read_edgelist(input), "edgelist graph hardened");
        }
        2 => {
            let mut engine = EdgeListEngine::strict();
            check_digraph(
                engine.read_digraph_edgelist(input),
                "edgelist digraph strict",
            );
        }
        3 => {
            let mut engine = EdgeListEngine::hardened();
            check_digraph(
                engine.read_digraph_edgelist(input),
                "edgelist digraph hardened",
            );
        }
        4 => {
            let mut engine = EdgeListEngine::strict();
            check_graph(engine.read_graphml(input), "graphml graph strict");
        }
        5 => {
            let mut engine = EdgeListEngine::hardened();
            check_graph(engine.read_graphml(input), "graphml graph hardened");
        }
        6 => {
            let mut engine = EdgeListEngine::strict();
            check_digraph(engine.read_digraph_graphml(input), "graphml digraph strict");
        }
        7 => {
            let mut engine = EdgeListEngine::hardened();
            check_digraph(
                engine.read_digraph_graphml(input),
                "graphml digraph hardened",
            );
        }
        8 => {
            let mut engine = EdgeListEngine::strict();
            let _ = engine.graphml_declares_directed(input);
        }
        9 => {
            let mut engine = EdgeListEngine::hardened();
            let _ = engine.graphml_declares_directed(input);
        }
        10 => {
            let mut engine = EdgeListEngine::strict();
            check_graph(engine.read_gexf(input), "gexf graph strict");
        }
        11 => {
            let mut engine = EdgeListEngine::hardened();
            check_graph(engine.read_gexf(input), "gexf graph hardened");
        }
        12 => {
            let mut engine = EdgeListEngine::strict();
            check_digraph(engine.read_digraph_gexf(input), "gexf digraph strict");
        }
        13 => {
            let mut engine = EdgeListEngine::hardened();
            check_digraph(engine.read_digraph_gexf(input), "gexf digraph hardened");
        }
        14 => {
            let mut engine = EdgeListEngine::strict();
            let _ = engine.gexf_declares_directed(input);
        }
        _ => {
            let mut engine = EdgeListEngine::hardened();
            let _ = engine.gexf_declares_directed(input);
        }
    }
});
