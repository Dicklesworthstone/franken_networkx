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
use fnx_classes::Graph;
use libfuzzer_sys::fuzz_target;
use std::collections::HashSet;

/// A community detection result must be a valid partition of G:
/// every node in G appears in exactly one community, and every
/// reported node belongs to G.
fn assert_valid_community_partition(
    graph: &Graph,
    communities: &[Vec<String>],
    label: &str,
) {
    let expected: HashSet<&str> =
        graph.nodes_ordered().into_iter().collect();
    let mut seen: HashSet<&str> = HashSet::new();
    for comm in communities {
        for node in comm {
            assert!(
                graph.has_node(node),
                "{}: community contains foreign node {}",
                label,
                node
            );
            assert!(
                seen.insert(node.as_str()),
                "{}: node {} appears in two communities",
                label,
                node
            );
        }
    }
    assert_eq!(
        seen, expected,
        "{}: community partition does not cover the graph's node set",
        label
    );
}

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
    let k = node_count.clamp(1, 4);
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
            let communities = fnx_algorithms::louvain_communities(
                &ag.graph,
                resolution,
                "weight",
                threshold,
                None,
                seed,
            );
            assert_valid_community_partition(
                &ag.graph,
                &communities,
                "louvain_communities",
            );
            // Cross-check: the fnx public ``community_partition_is_valid``
            // predicate must accept the constructor's own output.
            assert!(
                fnx_algorithms::community_partition_is_valid(&ag.graph, &communities),
                "louvain output failed community_partition_is_valid"
            );
        }
        CommunityInput::LabelPropagation(ag) => {
            let communities = fnx_algorithms::label_propagation_communities(&ag.graph);
            assert_valid_community_partition(
                &ag.graph,
                &communities,
                "label_propagation_communities",
            );
            assert!(
                fnx_algorithms::community_partition_is_valid(&ag.graph, &communities),
                "label_propagation output failed community_partition_is_valid"
            );
        }
        CommunityInput::Modularity {
            graph: ag,
            partition_seed,
            resolution,
        } => {
            let resolution = (resolution as f64).clamp(1e-3, 8.0);
            let node_count = ag.nodes.len();
            let partition = arbitrary_partition_ids(node_count, partition_seed);
            // modularity may return Err on an invalid partition or a
            // disconnected graph; if it returns Ok, the value must be
            // finite.
            if let Ok(q) = fnx_algorithms::modularity(&ag.graph, &partition, resolution, "weight")
            {
                assert!(
                    q.is_finite(),
                    "modularity returned non-finite value {}",
                    q
                );
            }
        }
        CommunityInput::LouvainLarge(ag) => {
            let communities = fnx_algorithms::louvain_communities(
                &ag.graph, 1.0, "weight", 1e-7, None, Some(42),
            );
            assert_valid_community_partition(
                &ag.graph,
                &communities,
                "louvain_communities (large)",
            );
        }
    }
});
