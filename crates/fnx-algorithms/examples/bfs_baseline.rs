use fnx_algorithms::shortest_path_unweighted;
use fnx_classes::Graph;

fn main() {
    let mut graph = Graph::strict();
    let width = 80usize;
    let height = 80usize;

    for y in 0..height {
        for x in 0..width {
            let node = format!("{x}:{y}");
            if x + 1 < width {
                let right = format!("{}:{y}", x + 1);
                graph
                    .add_edge(node.clone(), right)
                    .expect("grid edge add should succeed");
            }
            if y + 1 < height {
                let down = format!("{x}:{}", y + 1);
                graph
                    .add_edge(node, down)
                    .expect("grid edge add should succeed");
            }
        }
    }

    let result = shortest_path_unweighted(&graph, "0:0", "79:79");
    println!(
        "path_len={} nodes_touched={} edges_scanned={}",
        result.path.as_ref().map_or(0, Vec::len),
        result.witness.nodes_touched,
        result.witness.edges_scanned
    );
}
