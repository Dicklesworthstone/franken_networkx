//! Memory profiling baseline using dhat.
//!
//! Run with:
//! ```bash
//! cargo run --release --features dhat-heap --example memory_baseline -- --topology grid --width 80 --height 80
//! ```
//!
//! Outputs JSON stats to stdout for machine parsing.

#![forbid(unsafe_code)]

#[cfg(feature = "dhat-heap")]
#[global_allocator]
static ALLOC: dhat::Alloc = dhat::Alloc;

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
    output_json: bool,
}

fn parse_config() -> Result<Config, String> {
    let mut config = Config {
        topology: Topology::Grid,
        width: 80,
        height: 80,
        nodes: 6_400,
        edge_prob: 0.01,
        seed: 0xD1CE_BEEF,
        output_json: true,
    };

    let mut args = env::args().skip(1);
    while let Some(arg) = args.next() {
        match arg.as_str() {
            "--topology" => {
                let value = args.next().ok_or("missing value for --topology")?;
                config.topology = match value.as_str() {
                    "grid" => Topology::Grid,
                    "line" => Topology::Line,
                    "star" => Topology::Star,
                    "complete" => Topology::Complete,
                    "erdos_renyi" => Topology::ErdosRenyi,
                    _ => return Err(format!("unsupported --topology value: {value}")),
                };
            }
            "--width" => {
                let value = args.next().ok_or("missing value for --width")?;
                config.width = value.parse::<usize>().map_err(|_| "invalid --width")?;
            }
            "--height" => {
                let value = args.next().ok_or("missing value for --height")?;
                config.height = value.parse::<usize>().map_err(|_| "invalid --height")?;
            }
            "--nodes" => {
                let value = args.next().ok_or("missing value for --nodes")?;
                config.nodes = value.parse::<usize>().map_err(|_| "invalid --nodes")?;
            }
            "--edge-prob" => {
                let value = args.next().ok_or("missing value for --edge-prob")?;
                config.edge_prob = value.parse::<f64>().map_err(|_| "invalid --edge-prob")?;
            }
            "--seed" => {
                let value = args.next().ok_or("missing value for --seed")?;
                config.seed = value.parse::<u64>().map_err(|_| "invalid --seed")?;
            }
            "--no-json" => {
                config.output_json = false;
            }
            _ => return Err(format!("unsupported argument: {arg}")),
        }
    }

    if !(0.0..=1.0).contains(&config.edge_prob) {
        return Err("--edge-prob must be in [0.0, 1.0]".to_string());
    }
    Ok(config)
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

fn topology_label(topology: Topology) -> &'static str {
    match topology {
        Topology::Grid => "grid",
        Topology::Line => "line",
        Topology::Star => "star",
        Topology::Complete => "complete",
        Topology::ErdosRenyi => "erdos_renyi",
    }
}

fn build_graph(config: &Config) -> Result<(Graph, String, String), String> {
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
                            .map_err(|_| "grid edge add should succeed")?;
                    }
                    if y + 1 < height {
                        let down = format!("{x}:{}", y + 1);
                        graph
                            .add_edge(node, down)
                            .map_err(|_| "grid edge add should succeed")?;
                    }
                }
            }
            let source = "0:0".to_string();
            let target = format!("{}:{}", width - 1, height - 1);
            Ok((graph, source, target))
        }
        Topology::Line => {
            let nodes = config.nodes.max(2);
            for idx in 0..nodes - 1 {
                graph
                    .add_edge(idx.to_string(), (idx + 1).to_string())
                    .map_err(|_| "line edge add should succeed")?;
            }
            let source = "0".to_string();
            let target = (nodes - 1).to_string();
            Ok((graph, source, target))
        }
        Topology::Star => {
            let nodes = config.nodes.max(2);
            for idx in 1..nodes {
                graph
                    .add_edge("0".to_string(), idx.to_string())
                    .map_err(|_| "star edge add should succeed")?;
            }
            let source = "1".to_string();
            let target = (nodes - 1).to_string();
            Ok((graph, source, target))
        }
        Topology::Complete => {
            let nodes = config.nodes.max(2);
            for left in 0..nodes {
                for right in left + 1..nodes {
                    graph
                        .add_edge(left.to_string(), right.to_string())
                        .map_err(|_| "complete edge add should succeed")?;
                }
            }
            let source = "0".to_string();
            let target = (nodes - 1).to_string();
            Ok((graph, source, target))
        }
        Topology::ErdosRenyi => {
            let nodes = config.nodes.max(2);
            let mut state = config.seed;
            for idx in 0..nodes - 1 {
                graph
                    .add_edge(idx.to_string(), (idx + 1).to_string())
                    .map_err(|_| "erdos_renyi backbone edge add should succeed")?;
            }
            for left in 0..nodes {
                for right in left + 1..nodes {
                    if random_unit_f64(&mut state) < config.edge_prob {
                        graph
                            .add_edge(left.to_string(), right.to_string())
                            .map_err(|_| "erdos_renyi edge add should succeed")?;
                    }
                }
            }
            let source = "0".to_string();
            let target = (nodes - 1).to_string();
            Ok((graph, source, target))
        }
    }
}

fn main() -> Result<(), String> {
    let config = parse_config()?;

    #[cfg(feature = "dhat-heap")]
    let profiler = dhat::Profiler::builder().testing().build();

    let (graph, source, target) = build_graph(&config)?;
    let result = shortest_path_unweighted(&graph, &source, &target);

    #[cfg(feature = "dhat-heap")]
    let stats = dhat::HeapStats::get();

    let node_count = graph.node_count();
    let edge_count = graph.edge_count();
    let path_len = result.path.as_ref().map_or(0, Vec::len);

    if config.output_json {
        #[cfg(feature = "dhat-heap")]
        {
            println!(
                r#"{{"topology":"{}","node_count":{},"edge_count":{},"path_len":{},"total_bytes":{},"total_blocks":{},"max_bytes":{},"max_blocks":{},"curr_bytes":{},"curr_blocks":{}}}"#,
                topology_label(config.topology),
                node_count,
                edge_count,
                path_len,
                stats.total_bytes,
                stats.total_blocks,
                stats.max_bytes,
                stats.max_blocks,
                stats.curr_bytes,
                stats.curr_blocks,
            );
        }
        #[cfg(not(feature = "dhat-heap"))]
        {
            println!(
                r#"{{"topology":"{}","node_count":{},"edge_count":{},"path_len":{},"dhat_enabled":false}}"#,
                topology_label(config.topology),
                node_count,
                edge_count,
                path_len,
            );
        }
    } else {
        println!(
            "topology={} nodes={} edges={} path_len={}",
            topology_label(config.topology),
            node_count,
            edge_count,
            path_len
        );
        #[cfg(feature = "dhat-heap")]
        {
            println!(
                "  total_bytes={} total_blocks={} max_bytes={} max_blocks={} curr_bytes={} curr_blocks={}",
                stats.total_bytes,
                stats.total_blocks,
                stats.max_bytes,
                stats.max_blocks,
                stats.curr_bytes,
                stats.curr_blocks,
            );
        }
    }

    #[cfg(feature = "dhat-heap")]
    drop(profiler);

    Ok(())
}
