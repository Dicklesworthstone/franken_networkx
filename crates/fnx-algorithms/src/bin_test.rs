use fnx_classes::digraph::DiGraph;
use fnx_algorithms::multi_source_dijkstra_directed;

fn main() {
    let mut g = DiGraph::strict();
    g.add_edge("a", "b").unwrap();
    g.add_edge("b", "c").unwrap();
    let res = multi_source_dijkstra_directed(&g, &["b"], "weight");
    println!("Dists: {:?}", res.distances);
}
