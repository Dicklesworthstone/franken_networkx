use fnx_algorithms::shortest_path_unweighted;
use fnx_classes::Graph;
use std::env;

#[derive(Clone, Copy)]
enum Topology {
    Grid,
    Line,
    Star,
    Complete,
    ErdosRenyi,
}

struct Config {
    topology: Topology,
    width: usize,
    height: usize,
    nodes: usize,
    edge_prob: f64,
    seed: u64,
}

fn parse_config() -> Config {
    let mut config = Config {
        topology: Topology::Grid,
        width: 80,
        height: 80,
        nodes: 6_400,
        edge_prob: 0.01,
        seed: 0xD1CE_BEEF,
    };

    let mut args = env::args().skip(1);
    while let Some(arg) = args.next() {
        match arg.as_str() {
            "--topology" => {
                let value = args.next().expect("missing value for --topology");
                config.topology = match value.as_str() {
                    "grid" => Topology::Grid,
                    "line" => Topology::Line,
                    "star" => Topology::Star,
                    "complete" => Topology::Complete,
                    "erdos_renyi" => Topology::ErdosRenyi,
                    _ => panic!("unsupported --topology value: {value}"),
                };
            }
            "--width" => {
                let value = args.next().expect("missing value for --width");
                config.width = value.parse::<usize>().expect("invalid --width");
            }
            "--height" => {
                let value = args.next().expect("missing value for --height");
                config.height = value.parse::<usize>().expect("invalid --height");
            }
            "--nodes" => {
                let value = args.next().expect("missing value for --nodes");
                config.nodes = value.parse::<usize>().expect("invalid --nodes");
            }
            "--edge-prob" => {
                let value = args.next().expect("missing value for --edge-prob");
                config.edge_prob = value.parse::<f64>().expect("invalid --edge-prob");
            }
            "--seed" => {
                let value = args.next().expect("missing value for --seed");
                config.seed = value.parse::<u64>().expect("invalid --seed");
            }
            _ => panic!("unsupported argument: {arg}"),
        }
    }

    assert!(
        (0.0..=1.0).contains(&config.edge_prob),
        "--edge-prob must be in [0.0, 1.0]"
    );
    config
}

fn lcg_next(state: &mut u64) -> u64 {
    *state = state
        .wrapping_mul(6_364_136_223_846_793_005)
        .wrapping_add(1_442_695_040_888_963_407);
    *state
}

fn random_unit_f64(state: &mut u64) -> f64 {
    let sample = lcg_next(state) >> 11;
    sample as f64 / ((1u64 << 53) as f64)
}

fn build_graph(config: &Config) -> (Graph, String, String, &'static str) {
    let mut graph = Graph::strict();

    match config.topology {
        Topology::Grid => {
            let width = config.width.max(2);
            let height = config.height.max(2);
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
            let source = "0:0".to_string();
            let target = format!("{}:{}", width - 1, height - 1);
            (graph, source, target, "grid")
        }
        Topology::Line => {
            let nodes = config.nodes.max(2);
            for idx in 0..nodes - 1 {
                graph
                    .add_edge(idx.to_string(), (idx + 1).to_string())
                    .expect("line edge add should succeed");
            }
            let source = "0".to_string();
            let target = (nodes - 1).to_string();
            (graph, source, target, "line")
        }
        Topology::Star => {
            let nodes = config.nodes.max(2);
            for idx in 1..nodes {
                graph
                    .add_edge("0".to_string(), idx.to_string())
                    .expect("star edge add should succeed");
            }
            let source = "1".to_string();
            let target = (nodes - 1).to_string();
            (graph, source, target, "star")
        }
        Topology::Complete => {
            let nodes = config.nodes.max(2);
            for left in 0..nodes {
                for right in left + 1..nodes {
                    graph
                        .add_edge(left.to_string(), right.to_string())
                        .expect("complete edge add should succeed");
                }
            }
            let source = "0".to_string();
            let target = (nodes - 1).to_string();
            (graph, source, target, "complete")
        }
        Topology::ErdosRenyi => {
            let nodes = config.nodes.max(2);
            let mut state = config.seed;
            // Ensure stable connectivity baseline, then add deterministic random edges.
            for idx in 0..nodes - 1 {
                graph
                    .add_edge(idx.to_string(), (idx + 1).to_string())
                    .expect("erdos_renyi backbone edge add should succeed");
            }
            for left in 0..nodes {
                for right in left + 1..nodes {
                    if random_unit_f64(&mut state) < config.edge_prob {
                        graph
                            .add_edge(left.to_string(), right.to_string())
                            .expect("erdos_renyi edge add should succeed");
                    }
                }
            }
            let source = "0".to_string();
            let target = (nodes - 1).to_string();
            (graph, source, target, "erdos_renyi")
        }
    }
}

fn main() {
    let config = parse_config();
    let (graph, source, target, topology_label) = build_graph(&config);
    let result = shortest_path_unweighted(&graph, &source, &target);
    println!(
        "topology={topology_label} path_len={} nodes_touched={} edges_scanned={}",
        result.path.as_ref().map_or(0, Vec::len),
        result.witness.nodes_touched,
        result.witness.edges_scanned
    );
}
