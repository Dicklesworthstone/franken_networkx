//! Structure-aware fuzzer for community-detection algorithms.
//!
//! Exercises louvain_communities, label_propagation_communities, and
//! modularity on valid-but-pathological graph structures. Each call is
//! wrapped so that panics (which libfuzzer turns into crashes) are the
//! only failure signal — algorithmic results are discarded because the
//! target is to drive the implementations through diverse inputs, not
//! check parity here.

#![no_main]

mod arbitrary_graph;

use arbitrary::Arbitrary;
use arbitrary_graph::ArbitraryGraph;
use libfuzzer_sys::fuzz_target;

/// Small graph (<= 16 nodes) — some community algorithms are superlinear,
/// so limit size to keep fuzzer throughput high.
#[derive(Debug, Clone)]
pub struct ArbitrarySmallGraph {
    pub graph: fnx_classes::Graph,
    pub nodes: Vec<String>,
}

impl<'a> Arbitrary<'a> for ArbitrarySmallGraph {
    fn arbitrary(u: &mut arbitrary::Unstructured<'a>) -> arbitrary::Result<Self> {
        use fnx_runtime::CompatibilityMode;

        let mode = if u.arbitrary()? {
            CompatibilityMode::Strict
        } else {
            CompatibilityMode::Hardened
        };

        let mut graph = fnx_classes::Graph::new(mode);
        let node_count: usize = u.int_in_range(0..=16)?;
        let mut nodes = Vec::with_capacity(node_count);

        for i in 0..node_count {
            let name = format!("n{i}");
            graph.add_node(&name);
            nodes.push(name);
        }

        if node_count > 1 {
            let edge_density: u8 = u.arbitrary()?;
            let target_edges = (node_count * (edge_density as usize % 6)) / 2;

            for _ in 0..target_edges {
                if u.is_empty() {
                    break;
                }
                let src_idx: usize = u.int_in_range(0..=node_count - 1)?;
                let dst_idx: usize = u.int_in_range(0..=node_count - 1)?;
                if src_idx != dst_idx {
                    let _ = graph.add_edge(&nodes[src_idx], &nodes[dst_idx]);
                }
            }
        }

        Ok(Self { graph, nodes })
    }
}

/// Partition selector — avoids expensive probing by packing 4 bits per
/// node into the seed. Each bit-pair sequence assigns one of up to 16
/// community IDs, capped at the node count so every community is at
/// least singleton-valid.
fn arbitrary_partition_ids(node_count: usize, seed: u64) -> Vec<Vec<String>> {
    if node_count == 0 {
        return Vec::new();
    }
    let k = (node_count.min(4)).max(1);
    let mut buckets: Vec<Vec<String>> = (0..k).map(|_| Vec::new()).collect();
    for i in 0..node_count {
        let bucket_id = ((seed >> (i * 2)) as usize) % k;
        buckets[bucket_id].push(format!("n{i}"));
    }
    buckets.into_iter().filter(|b| !b.is_empty()).collect()
}

#[derive(Debug, Arbitrary)]
enum CommunityInput {
    /// Louvain with a deterministic seed.
    Louvain {
        graph: ArbitrarySmallGraph,
        resolution: f32,
        threshold: f32,
        seed: Option<u64>,
    },
    /// Label propagation (no tuning knobs).
    LabelPropagation(ArbitrarySmallGraph),
    /// Modularity of an arbitrary partition of the node set.
    Modularity {
        graph: ArbitrarySmallGraph,
        partition_seed: u64,
        resolution: f32,
    },
    /// Larger arbitrary graph through louvain — exercise edge cases
    /// driven by the richer ArbitraryGraph fixture.
    LouvainLarge(ArbitraryGraph),
}

fuzz_target!(|input: CommunityInput| {
    match input {
        CommunityInput::Louvain {
            graph: ag,
            resolution,
            threshold,
            seed,
        } => {
            // Clamp resolution/threshold into sane ranges so the fuzzer
            // doesn't drive louvain into NaN territory.
            let resolution = (resolution as f64).clamp(1e-3, 8.0);
            let threshold = (threshold as f64).clamp(1e-9, 1.0);
            let _ = fnx_algorithms::louvain_communities(
                &ag.graph,
                resolution,
                "weight",
                threshold,
                None,
                seed,
            );
        }
        CommunityInput::LabelPropagation(ag) => {
            let _ = fnx_algorithms::label_propagation_communities(&ag.graph);
        }
        CommunityInput::Modularity {
            graph: ag,
            partition_seed,
            resolution,
        } => {
            let resolution = (resolution as f64).clamp(1e-3, 8.0);
            let node_count = ag.nodes.len();
            let partition = arbitrary_partition_ids(node_count, partition_seed);
            // modularity may return Err on an invalid partition; we only
            // care that it doesn't panic.
            let _ = fnx_algorithms::modularity(&ag.graph, &partition, resolution, "weight");
        }
        CommunityInput::LouvainLarge(ag) => {
            let _ = fnx_algorithms::louvain_communities(
                &ag.graph, 1.0, "weight", 1e-7, None, Some(42),
            );
        }
    }
});
