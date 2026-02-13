#![forbid(unsafe_code)]

use fnx_classes::{EdgeSnapshot, Graph, GraphSnapshot};

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

#[derive(Debug, Clone)]
pub struct CachedSnapshotView {
    cached_revision: u64,
    snapshot: GraphSnapshot,
}

impl CachedSnapshotView {
    #[must_use]
    pub fn new(graph: &Graph) -> Self {
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
        self.snapshot = graph.snapshot();
        true
    }
}

#[cfg(test)]
mod tests {
    use super::{CachedSnapshotView, GraphView};
    use fnx_classes::Graph;

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
    fn view_preserves_deterministic_ordering() {
        let mut graph = Graph::strict();
        graph.add_edge("n1", "n2").expect("edge add should succeed");
        graph.add_edge("n1", "n3").expect("edge add should succeed");
        let view = GraphView::new(&graph);
        assert_eq!(view.nodes(), vec!["n1", "n2", "n3"]);
        let edges = view.edges();
        assert_eq!(edges[0].left, "n1");
        assert_eq!(edges[0].right, "n2");
        assert_eq!(edges[1].left, "n1");
        assert_eq!(edges[1].right, "n3");
    }
}
