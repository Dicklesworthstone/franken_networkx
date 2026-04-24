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
            check_graph_report(generator.empty_graph(usize::from(n)));
        }
        GeneratorInput::Path { n } => {
            check_graph_report(generator.path_graph(usize::from(n)));
        }
        GeneratorInput::Star { spokes } => {
            check_graph_report(generator.star_graph(usize::from(spokes)));
        }
        GeneratorInput::Cycle { n } => {
            check_graph_report(generator.cycle_graph(usize::from(n)));
        }
        GeneratorInput::Complete { n } => {
            check_graph_report(generator.complete_graph(usize::from(n)));
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
