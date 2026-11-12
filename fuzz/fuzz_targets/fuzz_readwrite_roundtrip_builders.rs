//! Structure-aware read/write fuzzing for graph-builder output.
#![no_main]

mod arbitrary_graph;

use arbitrary::{Arbitrary, Unstructured};
use arbitrary_graph::{ArbitraryDiGraph, ArbitraryGraph};
use fnx_classes::Graph;
use fnx_classes::digraph::DiGraph;
use fnx_readwrite::EdgeListEngine;
use libfuzzer_sys::fuzz_target;

#[derive(Debug, Arbitrary)]
struct ReadWriteRoundTripCase {
    graph: ArbitraryGraph,
    digraph: ArbitraryDiGraph,
    format_mask: u8,
}

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

fn assert_graph_edge_count(expected: &Graph, actual: &Graph, context: &str) {
    assert_eq!(
        actual.edges_ordered().len(),
        expected.edges_ordered().len(),
        "{context}: edge count changed across round trip"
    );
    assert_graph_endpoints(actual, context);
}

fn assert_digraph_edge_count(expected: &DiGraph, actual: &DiGraph, context: &str) {
    assert_eq!(
        actual.edges_ordered().len(),
        expected.edges_ordered().len(),
        "{context}: edge count changed across round trip"
    );
    assert_digraph_endpoints(actual, context);
}

fn assert_graph_full_counts(expected: &Graph, actual: &Graph, context: &str) {
    assert_eq!(
        actual.nodes_ordered().len(),
        expected.nodes_ordered().len(),
        "{context}: node count changed across round trip"
    );
    assert_graph_edge_count(expected, actual, context);
}

fn assert_digraph_full_counts(expected: &DiGraph, actual: &DiGraph, context: &str) {
    assert_eq!(
        actual.nodes_ordered().len(),
        expected.nodes_ordered().len(),
        "{context}: node count changed across round trip"
    );
    assert_digraph_edge_count(expected, actual, context);
}

fn roundtrip_edgelist(graph: &Graph, digraph: &DiGraph) {
    let mut writer = EdgeListEngine::hardened();
    let encoded = writer
        .write_edgelist(graph)
        .expect("builder graph edgelist serialization should succeed");
    let mut reader = EdgeListEngine::strict();
    let parsed = reader
        .read_edgelist(&encoded)
        .expect("builder graph edgelist should parse strictly");
    assert_graph_edge_count(graph, &parsed.graph, "edgelist graph");

    let mut di_writer = EdgeListEngine::hardened();
    let di_encoded = di_writer
        .write_digraph_edgelist(digraph)
        .expect("builder digraph edgelist serialization should succeed");
    let mut di_reader = EdgeListEngine::strict();
    let di_parsed = di_reader
        .read_digraph_edgelist(&di_encoded)
        .expect("builder digraph edgelist should parse strictly");
    assert_digraph_edge_count(digraph, &di_parsed.graph, "edgelist digraph");
}

fn roundtrip_graphml(graph: &Graph, digraph: &DiGraph) {
    let mut writer = EdgeListEngine::hardened();
    let encoded = writer
        .write_graphml(graph)
        .expect("builder graph GraphML serialization should succeed");
    let mut detector = EdgeListEngine::strict();
    assert!(
        !detector
            .graphml_declares_directed(&encoded)
            .expect("builder graph GraphML directed flag should parse strictly"),
        "graphml graph: undirected writer emitted directed metadata"
    );
    let mut reader = EdgeListEngine::strict();
    let parsed = reader
        .read_graphml(&encoded)
        .expect("builder graph GraphML should parse strictly");
    assert_graph_full_counts(graph, &parsed.graph, "graphml graph");

    let mut di_writer = EdgeListEngine::hardened();
    let di_encoded = di_writer
        .write_digraph_graphml(digraph)
        .expect("builder digraph GraphML serialization should succeed");
    let mut di_detector = EdgeListEngine::strict();
    assert!(
        di_detector
            .graphml_declares_directed(&di_encoded)
            .expect("builder digraph GraphML directed flag should parse strictly"),
        "graphml digraph: directed writer emitted undirected metadata"
    );
    let mut di_reader = EdgeListEngine::strict();
    let di_parsed = di_reader
        .read_digraph_graphml(&di_encoded)
        .expect("builder digraph GraphML should parse strictly");
    assert_digraph_full_counts(digraph, &di_parsed.graph, "graphml digraph");
}

fn roundtrip_gexf(graph: &Graph, digraph: &DiGraph) {
    let mut writer = EdgeListEngine::hardened();
    let encoded = writer
        .write_gexf(graph)
        .expect("builder graph GEXF serialization should succeed");
    let mut detector = EdgeListEngine::strict();
    assert!(
        !detector
            .gexf_declares_directed(&encoded)
            .expect("builder graph GEXF directed flag should parse strictly"),
        "gexf graph: undirected writer emitted directed metadata"
    );
    let mut reader = EdgeListEngine::strict();
    let parsed = reader
        .read_gexf(&encoded)
        .expect("builder graph GEXF should parse strictly");
    assert_graph_full_counts(graph, &parsed.graph, "gexf graph");

    let mut di_writer = EdgeListEngine::hardened();
    let di_encoded = di_writer
        .write_digraph_gexf(digraph)
        .expect("builder digraph GEXF serialization should succeed");
    let mut di_detector = EdgeListEngine::strict();
    assert!(
        di_detector
            .gexf_declares_directed(&di_encoded)
            .expect("builder digraph GEXF directed flag should parse strictly"),
        "gexf digraph: directed writer emitted undirected metadata"
    );
    let mut di_reader = EdgeListEngine::strict();
    let di_parsed = di_reader
        .read_digraph_gexf(&di_encoded)
        .expect("builder digraph GEXF should parse strictly");
    assert_digraph_full_counts(digraph, &di_parsed.graph, "gexf digraph");
}

fuzz_target!(|data: &[u8]| {
    let mut input = Unstructured::new(data);
    let Ok(case) = ReadWriteRoundTripCase::arbitrary(&mut input) else {
        return;
    };

    let format_mask = case.format_mask | 0b001;
    if format_mask & 0b001 != 0 {
        roundtrip_edgelist(&case.graph.graph, &case.digraph.graph);
    }
    if format_mask & 0b010 != 0 {
        roundtrip_graphml(&case.graph.graph, &case.digraph.graph);
    }
    if format_mask & 0b100 != 0 {
        roundtrip_gexf(&case.graph.graph, &case.digraph.graph);
    }
});
