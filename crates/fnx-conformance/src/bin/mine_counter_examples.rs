//! Counter-example mining loop for CGSE determinism verification.
//!
//! This binary generates random graphs and runs reference algorithms
//! multiple times to detect non-deterministic behavior. Any discrepancies
//! in witness hashes are recorded as counter-examples.
//!
//! Usage:
//!   cargo run -p fnx-conformance --bin mine_counter_examples [OPTIONS]
//!
//! Options:
//!   --graphs N       Number of random graphs per algorithm (default: 100)
//!   --iterations N   Executions per graph to check determinism (default: 3)
//!   --max-nodes N    Maximum nodes in generated graphs (default: 20)
//!   --density F      Edge density 0.0-1.0 (default: 0.5)
//!   --seed N         Random seed for reproducibility (default: 0)
//!   --algorithm ALG  Mine only this algorithm (default: all)
//!   --output PATH    Output file for results (default: stdout)

use fnx_cgse::{
    MiningConfig, MiningResult, ReferenceAlgorithm, collect_witnesses, generate_random_edges,
    mining_result_to_jsonl, verify_witness_determinism,
};
use fnx_classes::{Graph, digraph::DiGraph};
use fnx_runtime::CompatibilityMode;
use std::fs::File;
use std::io::Write;

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let config = parse_args()?;
    let algorithms = select_algorithms(&config)?;

    eprintln!(
        "Mining counter-examples: {} algorithms, {} graphs each, {} iterations per graph",
        algorithms.len(),
        config.base.graphs_per_algorithm,
        config.base.executions_per_graph
    );

    let result = run_mining(&config, &algorithms);

    let jsonl = mining_result_to_jsonl(&result);

    if let Some(output_path) = &config.output_path {
        let mut file = File::create(output_path)?;
        writeln!(file, "{jsonl}")?;
        eprintln!("Results written to {output_path}");
    } else {
        println!("{jsonl}");
    }

    if result.is_clean() {
        eprintln!(
            "Mining complete: {} graphs tested, {} executions, no counter-examples found",
            result.graphs_tested, result.executions
        );
        Ok(())
    } else {
        eprintln!(
            "Mining complete: {} counter-examples found!",
            result.counter_examples.len()
        );
        std::process::exit(1);
    }
}

struct ExtendedConfig {
    base: MiningConfig,
    algorithm_filter: Option<String>,
    output_path: Option<String>,
}

fn parse_args() -> Result<ExtendedConfig, Box<dyn std::error::Error>> {
    let mut config = MiningConfig::default();
    let mut algorithm_filter = None;
    let mut output_path = None;

    let mut args = std::env::args().skip(1);
    while let Some(arg) = args.next() {
        match arg.as_str() {
            "--graphs" => {
                config.graphs_per_algorithm =
                    args.next().ok_or("--graphs requires a value")?.parse()?;
            }
            "--iterations" => {
                config.executions_per_graph = args
                    .next()
                    .ok_or("--iterations requires a value")?
                    .parse()?;
            }
            "--max-nodes" => {
                config.max_nodes = args.next().ok_or("--max-nodes requires a value")?.parse()?;
            }
            "--density" => {
                config.max_density = args.next().ok_or("--density requires a value")?.parse()?;
            }
            "--seed" => {
                config.seed = args.next().ok_or("--seed requires a value")?.parse()?;
            }
            "--algorithm" => {
                algorithm_filter = Some(args.next().ok_or("--algorithm requires a value")?);
            }
            "--output" => {
                output_path = Some(args.next().ok_or("--output requires a value")?);
            }
            "--help" | "-h" => {
                print_help();
                std::process::exit(0);
            }
            unknown => {
                return Err(format!("unknown argument: {unknown}").into());
            }
        }
    }

    Ok(ExtendedConfig {
        base: config,
        algorithm_filter,
        output_path,
    })
}

fn print_help() {
    eprintln!(
        r#"mine_counter_examples - CGSE determinism mining loop

Usage: mine_counter_examples [OPTIONS]

Options:
  --graphs N       Number of random graphs per algorithm (default: 100)
  --iterations N   Executions per graph to check determinism (default: 3)
  --max-nodes N    Maximum nodes in generated graphs (default: 20)
  --density F      Edge density 0.0-1.0 (default: 0.5)
  --seed N         Random seed for reproducibility (default: 0)
  --algorithm ALG  Mine only this algorithm (default: all)
  --output PATH    Output file for results (default: stdout)
  --help, -h       Show this help

Algorithms: dijkstra, bellman_ford, bfs, dfs, max_weight_matching,
            min_weight_matching, connected_components,
            strongly_connected_components, kruskal, prim,
            eulerian_circuit, topological_sort
"#
    );
}

fn select_algorithms(
    config: &ExtendedConfig,
) -> Result<Vec<ReferenceAlgorithm>, Box<dyn std::error::Error>> {
    if let Some(filter) = &config.algorithm_filter {
        let alg = ReferenceAlgorithm::from_algorithm_id(filter)
            .ok_or_else(|| format!("unknown algorithm: {filter}"))?;
        Ok(vec![alg])
    } else {
        Ok(ReferenceAlgorithm::ALL.to_vec())
    }
}

fn run_mining(config: &ExtendedConfig, algorithms: &[ReferenceAlgorithm]) -> MiningResult {
    let mut result = MiningResult {
        counter_examples: Vec::new(),
        graphs_tested: 0,
        executions: 0,
        passing_algorithms: Vec::new(),
    };

    for &algorithm in algorithms {
        let mut algorithm_clean = true;
        let requires_directed = matches!(
            algorithm,
            ReferenceAlgorithm::StronglyConnectedComponents | ReferenceAlgorithm::TopologicalSort
        );

        for graph_idx in 0..config.base.graphs_per_algorithm {
            let seed = config.base.seed.wrapping_add(graph_idx as u64);
            let node_count = ((seed % (config.base.max_nodes as u64 - 2)) + 3) as usize;
            let density = (seed % 100) as f64 / 100.0 * config.base.max_density;

            let edges = generate_random_edges(node_count, density, requires_directed, seed);
            result.graphs_tested += 1;

            let counter_example = if requires_directed {
                mine_directed_algorithm(
                    algorithm,
                    &edges,
                    node_count,
                    config.base.executions_per_graph,
                    &mut result.executions,
                )
            } else {
                mine_undirected_algorithm(
                    algorithm,
                    &edges,
                    node_count,
                    config.base.executions_per_graph,
                    &mut result.executions,
                )
            };

            if let Some(ce) = counter_example {
                result.counter_examples.push(ce);
                algorithm_clean = false;
            }
        }

        if algorithm_clean {
            result.passing_algorithms.push(algorithm);
        }
    }

    result
}

fn mine_undirected_algorithm(
    algorithm: ReferenceAlgorithm,
    edges: &[(String, String)],
    node_count: usize,
    iterations: usize,
    execution_count: &mut u64,
) -> Option<fnx_cgse::CounterExample> {
    let run_algorithm = || {
        *execution_count += 1;
        let mut graph = Graph::new(CompatibilityMode::Strict);
        for i in 0..node_count {
            graph.add_node(i.to_string());
        }
        for (u, v) in edges {
            let _ = graph.add_edge(u.clone(), v.clone());
        }

        let (_, witnesses) = collect_witnesses(|| {
            run_undirected_algorithm(algorithm, &graph);
        });
        witnesses
    };

    verify_witness_determinism(
        algorithm,
        edges.to_vec(),
        node_count,
        false,
        iterations,
        run_algorithm,
    )
}

fn mine_directed_algorithm(
    algorithm: ReferenceAlgorithm,
    edges: &[(String, String)],
    node_count: usize,
    iterations: usize,
    execution_count: &mut u64,
) -> Option<fnx_cgse::CounterExample> {
    let run_algorithm = || {
        *execution_count += 1;
        let mut graph = DiGraph::new(CompatibilityMode::Strict);
        for i in 0..node_count {
            graph.add_node(i.to_string());
        }
        for (u, v) in edges {
            let _ = graph.add_edge(u.clone(), v.clone());
        }

        let (_, witnesses) = collect_witnesses(|| {
            run_directed_algorithm(algorithm, &graph);
        });
        witnesses
    };

    verify_witness_determinism(
        algorithm,
        edges.to_vec(),
        node_count,
        true,
        iterations,
        run_algorithm,
    )
}

fn run_undirected_algorithm(algorithm: ReferenceAlgorithm, graph: &Graph) {
    use fnx_algorithms::*;

    match algorithm {
        ReferenceAlgorithm::Dijkstra => {
            if let Some(source) = graph.nodes_ordered().first() {
                let _ = multi_source_dijkstra(graph, &[source], "weight");
            }
        }
        ReferenceAlgorithm::BellmanFord => {
            if let Some(source) = graph.nodes_ordered().first() {
                let _ = bellman_ford_shortest_paths(graph, source, "weight");
            }
        }
        ReferenceAlgorithm::Bfs => {
            if let Some(source) = graph.nodes_ordered().first() {
                let _ = bfs_edges(graph, source, None);
            }
        }
        ReferenceAlgorithm::Dfs => {
            if let Some(source) = graph.nodes_ordered().first() {
                let _ = dfs_edges(graph, source, None);
            }
        }
        ReferenceAlgorithm::MaxWeightMatching => {
            let _ = max_weight_matching(graph, false, "weight");
        }
        ReferenceAlgorithm::MinWeightMatching => {
            let _ = min_weight_matching(graph, "weight");
        }
        ReferenceAlgorithm::ConnectedComponents => {
            let _ = connected_components(graph);
        }
        ReferenceAlgorithm::Kruskal | ReferenceAlgorithm::Prim => {
            // MST algorithms not yet implemented - skip
        }
        ReferenceAlgorithm::EulerianCircuit => {
            let _ = is_eulerian(graph);
        }
        // Directed-only algorithms - no-op for undirected
        ReferenceAlgorithm::StronglyConnectedComponents | ReferenceAlgorithm::TopologicalSort => {}
    }
}

fn run_directed_algorithm(algorithm: ReferenceAlgorithm, graph: &DiGraph) {
    use fnx_algorithms::*;

    match algorithm {
        ReferenceAlgorithm::Dijkstra => {
            if let Some(source) = graph.nodes_ordered().first() {
                let _ = multi_source_dijkstra_directed(graph, &[source], "weight");
            }
        }
        ReferenceAlgorithm::BellmanFord => {
            if let Some(source) = graph.nodes_ordered().first() {
                let _ = bellman_ford_shortest_paths_directed(graph, source, "weight");
            }
        }
        ReferenceAlgorithm::Bfs => {
            if let Some(source) = graph.nodes_ordered().first() {
                let _ = bfs_edges_directed(graph, source, None);
            }
        }
        ReferenceAlgorithm::Dfs => {
            if let Some(source) = graph.nodes_ordered().first() {
                let _ = dfs_edges_directed(graph, source, None);
            }
        }
        ReferenceAlgorithm::StronglyConnectedComponents => {
            // SCC algorithm not yet CGSE-instrumented - skip
        }
        ReferenceAlgorithm::TopologicalSort => {
            let _ = topological_sort(graph);
        }
        // Undirected-only algorithms - no-op for directed
        ReferenceAlgorithm::MaxWeightMatching
        | ReferenceAlgorithm::MinWeightMatching
        | ReferenceAlgorithm::ConnectedComponents
        | ReferenceAlgorithm::Kruskal
        | ReferenceAlgorithm::Prim
        | ReferenceAlgorithm::EulerianCircuit => {}
    }
}
