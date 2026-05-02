//! Structure-aware fuzzer for graph generator parameter surfaces.
//!
//! Exercises strict and hardened generator modes over bounded random
//! parameters. Invalid parameters may fail closed; successful reports must
//! contain structurally valid graphs.

#![no_main]

use arbitrary::Arbitrary;
use fnx_classes::Graph;
use fnx_classes::digraph::{DiGraph, MultiDiGraph};
use fnx_generators::{
    DiGenerationReport, GenerationReport, GraphGenerator, MultiDiGenerationReport,
};
use libfuzzer_sys::fuzz_target;

#[derive(Debug, Clone, Copy, Arbitrary)]
enum FuzzProbability {
    Unit(u8),
    Wide(i16),
    Nan,
    PosInf,
    NegInf,
}

impl FuzzProbability {
    fn to_f64(self) -> f64 {
        match self {
            Self::Unit(raw) => f64::from(raw) / f64::from(u8::MAX),
            Self::Wide(raw) => f64::from(raw) / 100.0,
            Self::Nan => f64::NAN,
            Self::PosInf => f64::INFINITY,
            Self::NegInf => f64::NEG_INFINITY,
        }
    }
}

#[derive(Debug, Arbitrary)]
enum GeneratorInput {
    Empty {
        n: u16,
    },
    Path {
        n: u16,
    },
    Star {
        spokes: u16,
    },
    Cycle {
        n: u16,
    },
    Complete {
        n: u8,
    },
    Gnp {
        n: u8,
        p: FuzzProbability,
        seed: u64,
    },
    FastGnp {
        n: u8,
        p: FuzzProbability,
        seed: u64,
    },
    WattsStrogatz {
        n: u8,
        k: u8,
        p: FuzzProbability,
        seed: u64,
    },
    NewmanWattsStrogatz {
        n: u8,
        k: u8,
        p: FuzzProbability,
        seed: u64,
    },
    ConnectedWattsStrogatz {
        n: u8,
        k: u8,
        p: FuzzProbability,
        tries: u8,
        seed: u64,
    },
    BarabasiAlbert {
        n: u8,
        m: u8,
        seed: u64,
    },
    RandomRegular {
        n: u8,
        d: u8,
        seed: u64,
    },
    PowerlawCluster {
        n: u8,
        m: u8,
        p: FuzzProbability,
        seed: u64,
    },
    Gn {
        n: u8,
        seed: u64,
    },
    Gnr {
        n: u8,
        p: FuzzProbability,
        seed: u64,
    },
    Gnc {
        n: u8,
        seed: u64,
    },
    ScaleFree {
        n: u8,
        alpha: FuzzProbability,
        beta: FuzzProbability,
        gamma: FuzzProbability,
        delta_in: u8,
        delta_out: u8,
        seed: u64,
    },
}

fn assert_valid_graph(graph: &Graph) {
    let nodes = graph.nodes_ordered();
    assert_eq!(nodes.len(), graph.node_count());
    for edge in graph.edges_ordered() {
        assert!(graph.has_node(&edge.left));
        assert!(graph.has_node(&edge.right));
        assert!(graph.has_edge(&edge.left, &edge.right));
    }
}

fn assert_valid_digraph(graph: &DiGraph) {
    let nodes = graph.nodes_ordered();
    assert_eq!(nodes.len(), graph.node_count());
    for edge in graph.edges_ordered() {
        assert!(graph.has_node(&edge.left));
        assert!(graph.has_node(&edge.right));
        assert!(graph.has_edge(&edge.left, &edge.right));
    }
}

fn assert_valid_multidigraph(graph: &MultiDiGraph) {
    let nodes = graph.nodes_ordered();
    assert_eq!(nodes.len(), graph.node_count());
    for edge in graph.edges_ordered() {
        assert!(graph.has_node(&edge.source));
        assert!(graph.has_node(&edge.target));
        assert!(graph.has_edge(&edge.source, &edge.target));
    }
}

fn check_graph_report(result: Result<GenerationReport, fnx_generators::GenerationError>) {
    if let Ok(report) = result {
        assert_valid_graph(&report.graph);
    }
}

fn check_digraph_report(result: Result<DiGenerationReport, fnx_generators::GenerationError>) {
    if let Ok(report) = result {
        assert_valid_digraph(&report.graph);
    }
}

fn check_multidigraph_report(
    result: Result<MultiDiGenerationReport, fnx_generators::GenerationError>,
) {
    if let Ok(report) = result {
        assert_valid_multidigraph(&report.graph);
    }
}

fn exercise(mut generator: GraphGenerator, input: &GeneratorInput) {
    match *input {
        GeneratorInput::Empty { n } => {
            let n = usize::from(n);
            if let Ok(report) = generator.empty_graph(n) {
                assert_valid_graph(&report.graph);
                // empty_graph(n) has exactly n nodes and 0 edges.
                assert_eq!(
                    report.graph.node_count(), n,
                    "empty_graph({}) reports {} nodes, expected {}",
                    n, report.graph.node_count(), n
                );
                assert_eq!(
                    report.graph.edge_count(), 0,
                    "empty_graph({}) has {} edges, expected 0",
                    n, report.graph.edge_count()
                );
            }
        }
        GeneratorInput::Path { n } => {
            let n = usize::from(n);
            if let Ok(report) = generator.path_graph(n) {
                assert_valid_graph(&report.graph);
                // path_graph(n) has n nodes and max(0, n-1) edges.
                assert_eq!(
                    report.graph.node_count(), n,
                    "path_graph({}) reports {} nodes, expected {}",
                    n, report.graph.node_count(), n
                );
                let expected_edges = n.saturating_sub(1);
                assert_eq!(
                    report.graph.edge_count(), expected_edges,
                    "path_graph({}) has {} edges, expected {}",
                    n, report.graph.edge_count(), expected_edges
                );
            }
        }
        GeneratorInput::Star { spokes } => {
            let spokes = usize::from(spokes);
            if let Ok(report) = generator.star_graph(spokes) {
                assert_valid_graph(&report.graph);
                // star_graph(spokes) has spokes+1 nodes and spokes
                // edges (one center + ``spokes`` rim nodes connected
                // to the center).
                let expected_nodes = spokes.saturating_add(1);
                assert_eq!(
                    report.graph.node_count(), expected_nodes,
                    "star_graph({}) reports {} nodes, expected {}",
                    spokes, report.graph.node_count(), expected_nodes
                );
                assert_eq!(
                    report.graph.edge_count(), spokes,
                    "star_graph({}) has {} edges, expected {}",
                    spokes, report.graph.edge_count(), spokes
                );
            }
        }
        GeneratorInput::Cycle { n } => {
            let n = usize::from(n);
            if let Ok(report) = generator.cycle_graph(n) {
                assert_valid_graph(&report.graph);
                // cycle_graph(n): n nodes; n edges for n ≥ 3, n-1 for
                // n=2 (single edge), 0 for n ≤ 1.
                assert_eq!(
                    report.graph.node_count(), n,
                    "cycle_graph({}) reports {} nodes, expected {}",
                    n, report.graph.node_count(), n
                );
                let expected_edges = if n >= 3 { n } else { n.saturating_sub(1) };
                assert_eq!(
                    report.graph.edge_count(), expected_edges,
                    "cycle_graph({}) has {} edges, expected {}",
                    n, report.graph.edge_count(), expected_edges
                );
            }
        }
        GeneratorInput::Complete { n } => {
            let n = usize::from(n);
            if let Ok(report) = generator.complete_graph(n) {
                assert_valid_graph(&report.graph);
                // complete_graph(n) has n nodes and n*(n-1)/2 edges.
                assert_eq!(
                    report.graph.node_count(), n,
                    "complete_graph({}) reports {} nodes, expected {}",
                    n, report.graph.node_count(), n
                );
                let expected_edges = n.saturating_mul(n.saturating_sub(1)) / 2;
                assert_eq!(
                    report.graph.edge_count(), expected_edges,
                    "complete_graph({}) has {} edges, expected {}",
                    n, report.graph.edge_count(), expected_edges
                );
            }
        }
        GeneratorInput::Gnp { n, p, seed } => {
            check_graph_report(generator.gnp_random_graph(usize::from(n), p.to_f64(), seed));
        }
        GeneratorInput::FastGnp { n, p, seed } => {
            check_graph_report(generator.fast_gnp_random_graph(
                usize::from(n),
                p.to_f64(),
                seed,
                false,
            ));
        }
        GeneratorInput::WattsStrogatz { n, k, p, seed } => {
            check_graph_report(generator.watts_strogatz_graph(
                usize::from(n),
                usize::from(k),
                p.to_f64(),
                seed,
            ));
        }
        GeneratorInput::NewmanWattsStrogatz { n, k, p, seed } => {
            check_graph_report(generator.newman_watts_strogatz_graph(
                usize::from(n),
                usize::from(k),
                p.to_f64(),
                seed,
            ));
        }
        GeneratorInput::ConnectedWattsStrogatz {
            n,
            k,
            p,
            tries,
            seed,
        } => {
            check_graph_report(generator.connected_watts_strogatz_graph(
                usize::from(n),
                usize::from(k),
                p.to_f64(),
                usize::from(tries % 8),
                seed,
            ));
        }
        GeneratorInput::BarabasiAlbert { n, m, seed } => {
            check_graph_report(generator.barabasi_albert_graph(
                usize::from(n),
                usize::from(m),
                seed,
            ));
        }
        GeneratorInput::RandomRegular { n, d, seed } => {
            check_graph_report(generator.random_regular_graph(
                usize::from(n),
                usize::from(d),
                seed,
            ));
        }
        GeneratorInput::PowerlawCluster { n, m, p, seed } => {
            check_graph_report(generator.powerlaw_cluster_graph(
                usize::from(n),
                usize::from(m),
                p.to_f64(),
                seed,
            ));
        }
        GeneratorInput::Gn { n, seed } => {
            check_digraph_report(generator.gn_graph(usize::from(n), seed));
        }
        GeneratorInput::Gnr { n, p, seed } => {
            check_digraph_report(generator.gnr_graph(usize::from(n), p.to_f64(), seed));
        }
        GeneratorInput::Gnc { n, seed } => {
            check_digraph_report(generator.gnc_graph(usize::from(n), seed));
        }
        GeneratorInput::ScaleFree {
            n,
            alpha,
            beta,
            gamma,
            delta_in,
            delta_out,
            seed,
        } => {
            check_multidigraph_report(generator.scale_free_graph(
                usize::from(n),
                alpha.to_f64(),
                beta.to_f64(),
                gamma.to_f64(),
                f64::from(delta_in % 4),
                f64::from(delta_out % 4),
                None,
                seed,
            ));
        }
    }
}

fuzz_target!(|input: GeneratorInput| {
    exercise(GraphGenerator::strict(), &input);
    exercise(GraphGenerator::hardened(), &input);
});
