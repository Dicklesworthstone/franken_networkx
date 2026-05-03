// br-r37-c1-btmc5: was a debug-print scratchpad with assert!(false).
// Converted to a real regression test that pins the multi-source
// Dijkstra distances on a 3-node directed chain.

use fnx_classes::digraph::DiGraph;

#[test]
fn multi_source_dijkstra_directed_returns_zero_for_source_and_one_for_successor() {
    let mut g = DiGraph::strict();
    g.add_edge("a", "b").unwrap();
    g.add_edge("b", "c").unwrap();

    let res = crate::multi_source_dijkstra_directed(&g, &["b"], "weight");

    // From source "b", distances are: b=0 (self), c=1 (via b->c).
    // "a" is unreachable from "b" in the directed graph, so it should
    // not appear in the distances map.
    let by_node: std::collections::HashMap<&str, f64> = res
        .distances
        .iter()
        .map(|e| (e.node.as_str(), e.distance))
        .collect();

    assert_eq!(by_node.get("b").copied(), Some(0.0));
    assert_eq!(by_node.get("c").copied(), Some(1.0));
    assert!(
        by_node.get("a").is_none(),
        "node 'a' should not be reachable from 'b' in the directed chain a->b->c, \
         got distance {:?}",
        by_node.get("a"),
    );
}
