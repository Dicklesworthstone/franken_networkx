# FrankenNetworkX Fuzzing Audit

*Generated 2026-04-22 via /testing-fuzzing*

## Fuzzing Infrastructure Status: COMPREHENSIVE

The `fuzz/fuzz_targets/` directory contains 16 structure-aware fuzz targets using
libFuzzer and the `arbitrary` crate for grammar-based graph generation.

## Existing Fuzz Targets

### Algorithm Fuzzers (User-Requested)

| Target | Coverage | Graph Types | Variants |
|--------|----------|-------------|----------|
| `fuzz_flow.rs` | max_flow, min_cut | Directed/Undirected | 4 variants |
| `fuzz_shortest_path.rs` | dijkstra, bellman-ford, unweighted | Weighted/Unweighted × Dir/Undir | 6 variants |
| `fuzz_centrality.rs` | pagerank, betweenness, closeness, degree, eigenvector, katz, HITS, harmonic | Dir/Undir | 16 variants |

### Additional Algorithm Fuzzers

| Target | Coverage |
|--------|----------|
| `fuzz_connectivity.rs` | Connected components, articulation points |
| `fuzz_matching.rs` | Maximal/max-weight matching |
| `fuzz_clustering.rs` | Clustering coefficients |
| `fuzz_spanning_tree.rs` | MST/maximum spanning tree |

### Parser Fuzzers

| Target | Format |
|--------|--------|
| `fuzz_edgelist.rs` | Edge list format |
| `fuzz_adjlist.rs` | Adjacency list format |
| `fuzz_gml.rs` | GML format |
| `fuzz_graphml.rs` | GraphML format |
| `fuzz_json.rs` | JSON graph format |
| `fuzz_node_link.rs` | Node-link JSON |
| `fuzz_pajek.rs` | Pajek format |
| `fuzz_attribute_value.rs` | Attribute value parsing |

## Arbitrary Graph Generators (`arbitrary_graph.rs`)

Structure-aware generators producing valid-but-pathological graphs:

- `ArbitraryGraph` / `ArbitraryDiGraph` - Basic unweighted
- `ArbitraryWeightedGraph` / `ArbitraryWeightedDiGraph` - With weight attrs
- `ArbitraryFlowNetwork` / `ArbitraryFlowNetworkUndirected` - With capacity attrs

Features:
- MAX_NODES=64 (controls memory)
- MAX_EDGES_PER_NODE=8 (controls density)
- Negative weight support for Bellman-Ford edge cases
- Both Strict and Hardened compatibility modes

## Running Fuzz Tests

```bash
# Install cargo-fuzz
cargo install cargo-fuzz

# Run specific target
cargo +nightly fuzz run fuzz_flow -- -max_total_time=300
cargo +nightly fuzz run fuzz_shortest_path -- -max_total_time=300
cargo +nightly fuzz run fuzz_centrality -- -max_total_time=300

# Run all targets
for target in fuzz/fuzz_targets/fuzz_*.rs; do
  name=$(basename "$target" .rs)
  cargo +nightly fuzz run "$name" -- -max_total_time=60
done
```

## Coverage Gaps (Potential Beads)

### P1: Missing algorithm fuzz targets

| Algorithm Family | Status | Suggested Bead |
|-----------------|--------|----------------|
| Community detection | NOT FUZZED | `fuzz_community.rs` for louvain, label_prop |
| DAG algorithms | NOT FUZZED | `fuzz_dag.rs` for topo_sort, ancestors, descendants |
| Clique enumeration | NOT FUZZED | `fuzz_clique.rs` for max_clique, enumerate_cliques |
| Bipartite | NOT FUZZED | `fuzz_bipartite.rs` for is_bipartite, bipartite_sets |

### P2: Edge case generators

| Generator Type | Status | Suggested Bead |
|---------------|--------|----------------|
| Disconnected graphs | PARTIAL | Add multi-component graphs |
| Self-loops | NOT COVERED | Add self-loop support to generators |
| Multigraphs | NOT COVERED | ArbitraryMultiGraph/ArbitraryMultiDiGraph |

## Recommended Fuzz Beads

1. **[FUZZ] fuzz_community.rs** - Community detection (louvain, label_prop, modularity)
2. **[FUZZ] fuzz_dag.rs** - DAG algorithms (topo_sort, ancestors, descendants, antichains)
3. **[FUZZ] fuzz_clique.rs** - Clique enumeration (max_clique, enumerate_all_cliques)
4. **[FUZZ] fuzz_bipartite.rs** - Bipartite algorithms (is_bipartite, bipartite_sets, color)
5. **[FUZZ] ArbitraryMultiGraph** - Multigraph generator for algorithm testing

## Bead Commands (for manual filing)

```bash
# P1: Missing algorithm fuzz targets
br create "[FUZZ] fuzz_community.rs - community detection (louvain, label_prop, modularity)"
br create "[FUZZ] fuzz_dag.rs - DAG algorithms (topo_sort, ancestors, descendants, antichains)"
br create "[FUZZ] fuzz_clique.rs - clique enumeration (max_clique, enumerate_all_cliques)"
br create "[FUZZ] fuzz_bipartite.rs - bipartite algorithms (is_bipartite, bipartite_sets)"

# P2: Edge case generators
br create "[FUZZ] ArbitraryMultiGraph/ArbitraryMultiDiGraph - multigraph fuzzing support"
```

## Conclusion

Core algorithm families (flow, shortest_path, centrality) have comprehensive fuzz
coverage. Gaps exist in community detection, DAG, clique, and bipartite families.
The arbitrary graph generators are well-designed but lack multigraph support.
