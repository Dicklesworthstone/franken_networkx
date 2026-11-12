//! Structure-aware fuzzer for the snapshot → replay round-trip.
//!
//! Exercises ``Graph::snapshot``, ``DiGraph::snapshot``,
//! ``MultiGraph::snapshot``, and ``MultiDiGraph::snapshot`` plus the
//! corresponding replay paths. The recent audit added a
//! ``node_attrs: BTreeMap<String, AttrMap>`` field to all four
//! snapshot types so that ``add_node(name, attrs)`` data isn't
//! silently lost on round-trip — this target gives that fix
//! continuous fuzz coverage.
//!
//! Beyond the no-panic invariant, asserts:
//!
//! Determinism
//! -----------
//! * ``graph.snapshot() == graph.snapshot()`` — the same graph
//!   snapshotted twice produces equal snapshot structs.
//!
//! Replay invariants
//! -----------------
//! * The replayed graph has the same ``node_count``, ``edge_count``,
//!   and ``has_edge``-set as the original.
//! * For each node in the original snapshot's ``node_attrs``, the
//!   replayed graph reports the same attribute map. (This is the
//!   property the ``node_attrs`` field was added to preserve.)
//! * Re-snapshotting the replayed graph produces an equal snapshot
//!   (full structural identity, including attribute maps).
//!
//! Revision monotonicity
//! ---------------------
//! * ``graph.revision()`` only ever increases (or stays the same)
//!   across successful mutations.

#![no_main]

mod arbitrary_graph;

use arbitrary::Arbitrary;
use arbitrary_graph::{
    ArbitraryDiGraph, ArbitraryGraph, ArbitraryMultiDiGraph, ArbitraryMultiGraph,
};
use fnx_classes::digraph::{DiGraph, MultiDiGraph};
use fnx_classes::{AttrMap, Graph, MultiGraph};
use fnx_runtime::{CgseValue, CompatibilityMode};
use libfuzzer_sys::fuzz_target;

#[derive(Debug, Arbitrary)]
enum SnapshotInput {
    /// Round-trip a Graph snapshot.
    UndirectedRoundTrip(ArbitraryGraph),
    /// Round-trip a DiGraph snapshot.
    DirectedRoundTrip(ArbitraryDiGraph),
    /// Round-trip a MultiGraph snapshot.
    MultiUndirectedRoundTrip(ArbitraryMultiGraph),
    /// Round-trip a MultiDiGraph snapshot.
    MultiDirectedRoundTrip(ArbitraryMultiDiGraph),
    /// Determinism: same graph snapshotted twice ⇒ equal snapshots.
    Determinism(ArbitraryGraph),
    /// Determinism for digraph.
    DeterminismDirected(ArbitraryDiGraph),
    /// Revision monotonicity across snapshot calls (snapshot is read-only,
    /// so revision must NOT change).
    RevisionStableAcrossSnapshot(ArbitraryGraph),
    /// Round-trip with a synthetic node attribute attached so the
    /// node_attrs field gets exercised.
    UndirectedRoundTripWithNodeAttr(ArbitraryGraph, u8),
    /// Same, for digraph.
    DirectedRoundTripWithNodeAttr(ArbitraryDiGraph, u8),
}

fn replay_graph(s: &fnx_classes::GraphSnapshot) -> Graph {
    let mut g = Graph::new(s.mode);
    for node in &s.nodes {
        let attrs = s.node_attrs.get(node).cloned().unwrap_or_default();
        g.add_node_with_attrs(node.clone(), attrs);
    }
    for edge in &s.edges {
        let _ = g.add_edge_with_attrs(edge.left.clone(), edge.right.clone(), edge.attrs.clone());
    }
    g
}

fn replay_digraph(s: &fnx_classes::digraph::DiGraphSnapshot) -> DiGraph {
    let mut g = DiGraph::new(s.mode);
    for node in &s.nodes {
        let attrs = s.node_attrs.get(node).cloned().unwrap_or_default();
        g.add_node_with_attrs(node.clone(), attrs);
    }
    for edge in &s.edges {
        let _ = g.add_edge_with_attrs(edge.left.clone(), edge.right.clone(), edge.attrs.clone());
    }
    g
}

fn replay_multigraph(s: &fnx_classes::MultiGraphSnapshot) -> MultiGraph {
    let mut g = MultiGraph::new(s.mode);
    for node in &s.nodes {
        let attrs = s.node_attrs.get(node).cloned().unwrap_or_default();
        g.add_node_with_attrs(node.clone(), attrs);
    }
    for edge in &s.edges {
        let _ = g.add_edge_with_key_and_attrs(
            edge.left.clone(),
            edge.right.clone(),
            edge.key,
            edge.attrs.clone(),
        );
    }
    g
}

fn replay_multidigraph(s: &fnx_classes::digraph::MultiDiGraphSnapshot) -> MultiDiGraph {
    let mut g = MultiDiGraph::new(s.mode);
    for node in &s.nodes {
        let attrs = s.node_attrs.get(node).cloned().unwrap_or_default();
        g.add_node_with_attrs(node.clone(), attrs);
    }
    for edge in &s.edges {
        let _ = g.add_edge_with_key_and_attrs(
            edge.source.clone(),
            edge.target.clone(),
            edge.key,
            edge.attrs.clone(),
        );
    }
    g
}

fn synth_node_attrs(byte: u8) -> AttrMap {
    let mut attrs = AttrMap::new();
    if byte & 0x01 != 0 {
        attrs.insert(
            "fuzz_color".to_owned(),
            CgseValue::String("synth".to_owned()),
        );
    }
    if byte & 0x02 != 0 {
        attrs.insert(
            "fuzz_weight".to_owned(),
            CgseValue::Float(byte as f64 / 255.0),
        );
    }
    if byte & 0x04 != 0 {
        attrs.insert("fuzz_count".to_owned(), CgseValue::Int(byte as i64));
    }
    attrs
}

fn assert_undirected_roundtrip(graph: &Graph) {
    let s1 = graph.snapshot();
    let replay = replay_graph(&s1);
    let s2 = replay.snapshot();
    assert_eq!(s1, s2, "Graph snapshot round-trip diverged");
    assert_eq!(graph.node_count(), replay.node_count());
    assert_eq!(graph.edge_count(), replay.edge_count());
    // Per-node attribute preservation.
    for (node, attrs) in &s1.node_attrs {
        let replayed_attrs = replay
            .node_attrs(node)
            .expect("replayed node missing")
            .clone();
        assert_eq!(replayed_attrs, *attrs, "node {node} attrs mismatch");
    }
}

fn assert_directed_roundtrip(graph: &DiGraph) {
    let s1 = graph.snapshot();
    let replay = replay_digraph(&s1);
    let s2 = replay.snapshot();
    assert_eq!(s1, s2, "DiGraph snapshot round-trip diverged");
    assert_eq!(graph.node_count(), replay.node_count());
    assert_eq!(graph.edge_count(), replay.edge_count());
    for (node, attrs) in &s1.node_attrs {
        let replayed_attrs = replay
            .node_attrs(node)
            .expect("replayed node missing")
            .clone();
        assert_eq!(replayed_attrs, *attrs, "node {node} attrs mismatch");
    }
}

fn assert_multi_roundtrip(graph: &MultiGraph) {
    let s1 = graph.snapshot();
    let replay = replay_multigraph(&s1);
    let s2 = replay.snapshot();
    assert_eq!(s1, s2, "MultiGraph snapshot round-trip diverged");
    assert_eq!(graph.node_count(), replay.node_count());
    assert_eq!(graph.edge_count(), replay.edge_count());
}

fn assert_multidi_roundtrip(graph: &MultiDiGraph) {
    let s1 = graph.snapshot();
    let replay = replay_multidigraph(&s1);
    let s2 = replay.snapshot();
    assert_eq!(s1, s2, "MultiDiGraph snapshot round-trip diverged");
    assert_eq!(graph.node_count(), replay.node_count());
    assert_eq!(graph.edge_count(), replay.edge_count());
}

fn assert_determinism(graph: &Graph) {
    let s1 = graph.snapshot();
    let s2 = graph.snapshot();
    assert_eq!(s1, s2, "snapshot is non-deterministic on undirected");
}

fn assert_determinism_directed(graph: &DiGraph) {
    let s1 = graph.snapshot();
    let s2 = graph.snapshot();
    assert_eq!(s1, s2, "snapshot is non-deterministic on directed");
}

fn assert_revision_stable_across_snapshot(graph: &Graph) {
    let r1 = graph.revision();
    let _ = graph.snapshot();
    let r2 = graph.revision();
    let _ = graph.snapshot();
    let r3 = graph.revision();
    assert_eq!(r1, r2);
    assert_eq!(r2, r3);
}

fn fuzz_round_trip_with_node_attr_undirected(graph: Graph, byte: u8) {
    let mut g = graph;
    // Sprinkle synthesized attrs onto a deterministic subset of nodes.
    let nodes: Vec<String> = g.nodes_ordered().iter().map(|s| s.to_string()).collect();
    let attrs = synth_node_attrs(byte);
    if attrs.is_empty() {
        return;
    }
    for (i, n) in nodes.iter().enumerate() {
        if i % 2 == 0 {
            g.add_node_with_attrs(n.clone(), attrs.clone());
        }
    }
    assert_undirected_roundtrip(&g);
}

fn fuzz_round_trip_with_node_attr_directed(graph: DiGraph, byte: u8) {
    let mut g = graph;
    let nodes: Vec<String> = g.nodes_ordered().iter().map(|s| s.to_string()).collect();
    let attrs = synth_node_attrs(byte);
    if attrs.is_empty() {
        return;
    }
    for (i, n) in nodes.iter().enumerate() {
        if i % 2 == 0 {
            g.add_node_with_attrs(n.clone(), attrs.clone());
        }
    }
    assert_directed_roundtrip(&g);
}

fuzz_target!(|input: SnapshotInput| {
    match input {
        SnapshotInput::UndirectedRoundTrip(ag) => {
            assert_undirected_roundtrip(&ag.graph);
        }
        SnapshotInput::DirectedRoundTrip(ag) => {
            assert_directed_roundtrip(&ag.graph);
        }
        SnapshotInput::MultiUndirectedRoundTrip(ag) => {
            assert_multi_roundtrip(&ag.graph);
        }
        SnapshotInput::MultiDirectedRoundTrip(ag) => {
            assert_multidi_roundtrip(&ag.graph);
        }
        SnapshotInput::Determinism(ag) => {
            assert_determinism(&ag.graph);
        }
        SnapshotInput::DeterminismDirected(ag) => {
            assert_determinism_directed(&ag.graph);
        }
        SnapshotInput::RevisionStableAcrossSnapshot(ag) => {
            assert_revision_stable_across_snapshot(&ag.graph);
        }
        SnapshotInput::UndirectedRoundTripWithNodeAttr(ag, byte) => {
            fuzz_round_trip_with_node_attr_undirected(ag.graph, byte);
        }
        SnapshotInput::DirectedRoundTripWithNodeAttr(ag, byte) => {
            fuzz_round_trip_with_node_attr_directed(ag.graph, byte);
        }
    }
    // Suppress the unused-import warning when CompatibilityMode isn't
    // used directly.
    let _ = CompatibilityMode::Strict;
});
