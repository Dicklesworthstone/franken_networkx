use fnx_algorithms::multi_source_dijkstra_directed;
use fnx_classes::AttrMap;
use fnx_classes::digraph::DiGraph;
use fnx_runtime::CompatibilityMode;

fn main() {
    let mut dg = DiGraph::new(CompatibilityMode::Strict);
    let mut attrs1 = AttrMap::new();
    attrs1.insert("weight".to_owned(), fnx_runtime::CgseValue::Float(1.0));
    let _ = dg.add_edge_with_attrs("a", "b", attrs1);

    let mut attrs2 = AttrMap::new();
    attrs2.insert("weight".to_owned(), fnx_runtime::CgseValue::Float(2.0));
    let _ = dg.add_edge_with_attrs("b", "c", attrs2);

    println!("Successors of b: {:?}", dg.successors("b"));

    let res = multi_source_dijkstra_directed(&dg, &["b"], "weight");
    for entry in res.distances {
        println!("{}: {}", entry.node, entry.distance);
    }
}
