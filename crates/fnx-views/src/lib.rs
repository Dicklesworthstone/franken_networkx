#![forbid(unsafe_code)]

use fnx_classes::digraph::{DiGraph, DiGraphSnapshot};
use fnx_classes::{EdgeSnapshot, Graph, GraphSnapshot};
use std::sync::Arc;

#[derive(Debug, Clone, Copy)]
pub struct GraphView<'a> {
    graph: &'a Graph,
}

impl<'a> GraphView<'a> {
    #[must_use]
    pub fn new(graph: &'a Graph) -> Self {
        Self { graph }
    }

    #[must_use]
    pub fn revision(&self) -> u64 {
        self.graph.revision()
    }

    #[must_use]
    pub fn nodes(&self) -> Vec<&str> {
        self.graph.nodes_ordered()
    }

    #[must_use]
    pub fn edges(&self) -> Vec<EdgeSnapshot> {
        self.graph.edges_ordered()
    }

    #[must_use]
    pub fn neighbors(&self, node: &str) -> Option<Vec<&str>> {
        self.graph.neighbors(node)
    }

    #[must_use]
    pub fn snapshot(&self) -> GraphSnapshot {
        self.graph.snapshot()
    }
}

#[derive(Debug, Clone, Copy)]
pub struct DiGraphView<'a> {
    graph: &'a DiGraph,
}

impl<'a> DiGraphView<'a> {
    #[must_use]
    pub fn new(graph: &'a DiGraph) -> Self {
        Self { graph }
    }

    #[must_use]
    pub fn revision(&self) -> u64 {
        self.graph.revision()
    }

    #[must_use]
    pub fn nodes(&self) -> Vec<&str> {
        self.graph.nodes_ordered()
    }

    #[must_use]
    pub fn edges(&self) -> Vec<EdgeSnapshot> {
        self.graph.edges_ordered()
    }

    #[must_use]
    pub fn successors(&self, node: &str) -> Option<Vec<&str>> {
        self.graph.successors(node)
    }

    #[must_use]
    pub fn predecessors(&self, node: &str) -> Option<Vec<&str>> {
        self.graph.predecessors(node)
    }

    #[must_use]
    pub fn snapshot(&self) -> DiGraphSnapshot {
        self.graph.snapshot()
    }
}

#[derive(Debug, Clone)]
pub struct CachedSnapshotView {
    cached_revision: u64,
    snapshot: Arc<GraphSnapshot>,
}

impl CachedSnapshotView {
    #[must_use]
    pub fn new(graph: &Graph) -> Self {
        Self {
            cached_revision: graph.revision(),
            snapshot: Arc::new(graph.snapshot()),
        }
    }

    #[must_use]
    pub fn cached_revision(&self) -> u64 {
        self.cached_revision
    }

    #[must_use]
    pub fn snapshot(&self) -> &GraphSnapshot {
        &self.snapshot
    }

    #[must_use]
    pub fn is_stale(&self, graph: &Graph) -> bool {
        self.cached_revision != graph.revision()
    }

    /// Returns true when a refresh occurred.
    pub fn refresh_if_stale(&mut self, graph: &Graph) -> bool {
        if !self.is_stale(graph) {
            return false;
        }
        self.cached_revision = graph.revision();
        self.snapshot = Arc::new(graph.snapshot());
        true
    }
}

#[derive(Debug, Clone)]
pub struct CachedDiGraphSnapshotView {
    cached_revision: u64,
    snapshot: DiGraphSnapshot,
}

impl CachedDiGraphSnapshotView {
    #[must_use]
    pub fn new(graph: &DiGraph) -> Self {
        Self {
            cached_revision: graph.revision(),
            snapshot: graph.snapshot(),
        }
    }

    #[must_use]
    pub fn cached_revision(&self) -> u64 {
        self.cached_revision
    }

    #[must_use]
    pub fn snapshot(&self) -> &DiGraphSnapshot {
        &self.snapshot
    }

    #[must_use]
    pub fn is_stale(&self, graph: &DiGraph) -> bool {
        self.cached_revision != graph.revision()
    }

    /// Returns true when a refresh occurred.
    pub fn refresh_if_stale(&mut self, graph: &DiGraph) -> bool {
        if !self.is_stale(graph) {
            return false;
        }
        self.cached_revision = graph.revision();
        self.snapshot = graph.snapshot();
        true
    }
}

#[cfg(test)]
mod tests {
    use super::{CachedDiGraphSnapshotView, CachedSnapshotView, DiGraphView, GraphView};
    use fnx_classes::digraph::DiGraph;
    use fnx_classes::{Graph, GraphSnapshot};
    use std::hint::black_box;
    use std::sync::Arc;
    use std::time::Instant;

    #[derive(Clone)]
    struct OwnedCachedSnapshotView {
        cached_revision: u64,
        snapshot: GraphSnapshot,
    }

    impl OwnedCachedSnapshotView {
        fn new(graph: &Graph) -> Self {
            Self {
                cached_revision: graph.revision(),
                snapshot: graph.snapshot(),
            }
        }

        fn is_stale(&self, graph: &Graph) -> bool {
            self.cached_revision != graph.revision()
        }

        fn refresh_if_stale(&mut self, graph: &Graph) -> bool {
            if !self.is_stale(graph) {
                return false;
            }
            self.cached_revision = graph.revision();
            self.snapshot = graph.snapshot();
            true
        }
    }

    fn cached_clone_fixture(nodes: usize, edges_per_node: usize) -> Graph {
        let mut graph = Graph::strict();
        for node in 0..nodes {
            graph.add_node(format!("node_{node:04}"));
        }
        for left in 0..nodes {
            for offset in 1..=edges_per_node {
                let right = (left + offset) % nodes;
                graph
                    .add_edge(format!("node_{left:04}"), format!("node_{right:04}"))
                    .expect("fixture edge should be unique");
            }
        }
        graph
    }

    fn time_owned_clones(view: &OwnedCachedSnapshotView, clones: usize) -> u128 {
        let started = Instant::now();
        for _ in 0..clones {
            drop(black_box(view.clone()));
        }
        started.elapsed().as_nanos()
    }

    fn time_shared_clones(view: &CachedSnapshotView, clones: usize) -> u128 {
        let started = Instant::now();
        for _ in 0..clones {
            drop(black_box(view.clone()));
        }
        started.elapsed().as_nanos()
    }

    fn median_ns(samples: &mut [u128]) -> u128 {
        samples.sort_unstable();
        samples[samples.len() / 2]
    }

    #[test]
    fn live_view_observes_graph_mutations() {
        let mut graph = Graph::strict();
        graph.add_edge("a", "b").expect("edge add should succeed");

        let before = {
            let view = GraphView::new(&graph);
            view.neighbors("a")
                .expect("neighbors should exist")
                .iter()
                .map(|n| (*n).to_owned())
                .collect::<Vec<String>>()
        };
        assert_eq!(before, vec!["b".to_owned()]);

        graph.add_edge("a", "c").expect("edge add should succeed");
        let after = {
            let view = GraphView::new(&graph);
            view.neighbors("a")
                .expect("neighbors should exist")
                .iter()
                .map(|n| (*n).to_owned())
                .collect::<Vec<String>>()
        };
        assert_eq!(after, vec!["b".to_owned(), "c".to_owned()]);
    }

    #[test]
    fn cached_snapshot_refreshes_on_revision_change() {
        let mut graph = Graph::strict();
        graph.add_edge("a", "b").expect("edge add should succeed");
        let mut cached = CachedSnapshotView::new(&graph);
        let old_rev = cached.cached_revision();
        assert_eq!(cached.snapshot().nodes, vec!["a", "b"]);

        graph.add_edge("b", "c").expect("edge add should succeed");
        assert!(cached.is_stale(&graph));
        let refreshed = cached.refresh_if_stale(&graph);
        assert!(refreshed);
        assert!(cached.cached_revision() > old_rev);
        assert_eq!(cached.snapshot().nodes, vec!["a", "b", "c"]);
    }

    #[test]
    #[ignore = "release same-binary A/B benchmark; run explicitly"]
    fn cached_snapshot_shared_clone_ab() {
        const NODES: usize = 2_048;
        const EDGES_PER_NODE: usize = 4;
        const CLONES_PER_SAMPLE: usize = 32;
        const NULL_CLONES_PER_SAMPLE: usize = 65_536;
        const ROUNDS: usize = 15;

        let mut parity_graph = cached_clone_fixture(16, 2);
        let owned = OwnedCachedSnapshotView::new(&parity_graph);
        let shared = CachedSnapshotView::new(&parity_graph);
        assert_eq!(&owned.snapshot, shared.snapshot());

        let owned_clone = owned.clone();
        let mut shared_clone = shared.clone();
        assert_eq!(owned.cached_revision, shared.cached_revision());
        assert_eq!(&owned_clone.snapshot, shared_clone.snapshot());
        assert!(Arc::ptr_eq(&shared.snapshot, &shared_clone.snapshot));

        parity_graph
            .add_edge("node_0000", "new_node")
            .expect("parity mutation should succeed");
        assert!(owned_clone.is_stale(&parity_graph));
        assert!(shared.is_stale(&parity_graph));
        assert!(shared_clone.refresh_if_stale(&parity_graph));
        assert!(shared.is_stale(&parity_graph));
        assert!(!Arc::ptr_eq(&shared.snapshot, &shared_clone.snapshot));

        let mut refreshed_owned = owned_clone;
        assert!(refreshed_owned.refresh_if_stale(&parity_graph));
        assert_eq!(&refreshed_owned.snapshot, shared_clone.snapshot());
        assert_eq!(
            refreshed_owned.cached_revision,
            shared_clone.cached_revision()
        );

        let graph = cached_clone_fixture(NODES, EDGES_PER_NODE);
        let owned = OwnedCachedSnapshotView::new(&graph);
        let shared = CachedSnapshotView::new(&graph);
        assert_eq!(&owned.snapshot, shared.snapshot());

        for round in 0..3 {
            if round % 2 == 0 {
                black_box(time_owned_clones(&owned, CLONES_PER_SAMPLE));
                black_box(time_shared_clones(&shared, CLONES_PER_SAMPLE));
            } else {
                black_box(time_shared_clones(&shared, CLONES_PER_SAMPLE));
                black_box(time_owned_clones(&owned, CLONES_PER_SAMPLE));
            }
        }

        let mut baseline_ns = Vec::with_capacity(ROUNDS);
        let mut candidate_ns = Vec::with_capacity(ROUNDS);
        for round in 0..ROUNDS {
            if round % 2 == 0 {
                baseline_ns.push(time_owned_clones(&owned, CLONES_PER_SAMPLE));
                candidate_ns.push(time_shared_clones(&shared, CLONES_PER_SAMPLE));
            } else {
                candidate_ns.push(time_shared_clones(&shared, CLONES_PER_SAMPLE));
                baseline_ns.push(time_owned_clones(&owned, CLONES_PER_SAMPLE));
            }
        }

        let mut null_left_ns = Vec::with_capacity(ROUNDS);
        let mut null_right_ns = Vec::with_capacity(ROUNDS);
        for round in 0..ROUNDS {
            if round % 2 == 0 {
                null_left_ns.push(time_shared_clones(&shared, NULL_CLONES_PER_SAMPLE));
                null_right_ns.push(time_shared_clones(&shared, NULL_CLONES_PER_SAMPLE));
            } else {
                null_right_ns.push(time_shared_clones(&shared, NULL_CLONES_PER_SAMPLE));
                null_left_ns.push(time_shared_clones(&shared, NULL_CLONES_PER_SAMPLE));
            }
        }

        let wins = baseline_ns
            .iter()
            .zip(&candidate_ns)
            .filter(|(baseline, candidate)| baseline > candidate)
            .count();
        let null_wins = null_left_ns
            .iter()
            .zip(&null_right_ns)
            .filter(|(left, right)| left > right)
            .count();
        let baseline_median = median_ns(&mut baseline_ns);
        let candidate_median = median_ns(&mut candidate_ns);
        let null_left_median = median_ns(&mut null_left_ns);
        let null_right_median = median_ns(&mut null_right_ns);
        let ratio = baseline_median as f64 / candidate_median as f64;
        let null_ratio = null_left_median as f64 / null_right_median as f64;

        assert!(baseline_median > candidate_median);
        println!(
            "CACHED_SNAPSHOT_SHARED_CLONE_AB nodes={NODES} edges={} clones_per_sample={CLONES_PER_SAMPLE} \
             rounds={ROUNDS} baseline_median_ns={baseline_median} \
             candidate_median_ns={candidate_median} ratio={ratio:.4} wins={wins}/{ROUNDS} \
             null_clones_per_sample={NULL_CLONES_PER_SAMPLE} null_left_median_ns={null_left_median} \
             null_right_median_ns={null_right_median} null_ratio={null_ratio:.4} \
             null_wins={null_wins}/{ROUNDS}",
            shared.snapshot().edges.len()
        );
    }

    #[test]
    fn digraph_live_view_observes_mutations() {
        let mut digraph = DiGraph::strict();
        digraph.add_edge("a", "b").expect("edge add");

        {
            let view = DiGraphView::new(&digraph);
            assert_eq!(view.successors("a").unwrap(), vec!["b"]);
            assert_eq!(view.predecessors("b").unwrap(), vec!["a"]);
        }

        digraph.add_edge("c", "a").expect("edge add");
        {
            let view = DiGraphView::new(&digraph);
            assert_eq!(view.predecessors("a").unwrap(), vec!["c"]);
        }
    }

    #[test]
    fn cached_digraph_snapshot_refreshes() {
        let mut digraph = DiGraph::strict();
        digraph.add_node("n1");
        let mut cached = CachedDiGraphSnapshotView::new(&digraph);
        assert_eq!(cached.snapshot().nodes, vec!["n1"]);

        digraph.add_node("n2");
        assert!(cached.is_stale(&digraph));
        assert!(cached.refresh_if_stale(&digraph));
        assert_eq!(cached.snapshot().nodes, vec!["n1", "n2"]);
    }

    // B10: Additional view-coherence tests

    #[test]
    fn cached_snapshot_not_stale_without_mutation() {
        let mut graph = Graph::strict();
        graph.add_edge("a", "b").expect("edge add");
        let cached = CachedSnapshotView::new(&graph);

        // No mutations - should not be stale
        assert!(!cached.is_stale(&graph));
    }

    #[test]
    fn cached_snapshot_stale_after_remove_node() {
        let mut graph = Graph::strict();
        graph.add_edge("a", "b").expect("edge add");
        graph.add_edge("b", "c").expect("edge add");
        let mut cached = CachedSnapshotView::new(&graph);
        assert_eq!(cached.snapshot().nodes.len(), 3);

        graph.remove_node("c");
        assert!(cached.is_stale(&graph));
        cached.refresh_if_stale(&graph);
        assert_eq!(cached.snapshot().nodes.len(), 2);
    }

    #[test]
    fn refresh_if_stale_returns_false_when_not_stale() {
        let mut graph = Graph::strict();
        graph.add_edge("a", "b").expect("edge add");
        let mut cached = CachedSnapshotView::new(&graph);

        // First call when not stale should return false
        assert!(!cached.refresh_if_stale(&graph));

        // After mutation
        graph.add_edge("b", "c").expect("edge add");
        assert!(cached.refresh_if_stale(&graph)); // true - refresh occurred
        assert!(!cached.refresh_if_stale(&graph)); // false - already fresh
    }

    #[test]
    fn revision_increments_with_each_mutation() {
        let mut graph = Graph::strict();
        let r0 = graph.revision();

        graph.add_edge("a", "b").expect("edge add");
        let r1 = graph.revision();
        assert!(r1 > r0, "revision should increase after add_edge");

        graph.add_edge("b", "c").expect("edge add");
        let r2 = graph.revision();
        assert!(r2 > r1, "revision should increase after second add_edge");

        graph.remove_node("c");
        let r3 = graph.revision();
        assert!(r3 > r2, "revision should increase after remove_node");
    }

    #[test]
    fn digraph_revision_tracks_mutations() {
        let mut digraph = DiGraph::strict();
        let r0 = digraph.revision();

        digraph.add_edge("a", "b").expect("edge add");
        let r1 = digraph.revision();
        assert!(r1 > r0);

        digraph.remove_edge("a", "b");
        let r2 = digraph.revision();
        assert!(r2 > r1);
    }
}
