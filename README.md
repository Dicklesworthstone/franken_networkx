# FrankenNetworkX

<div align="center">
  <img src="franken_networkx_illustration.webp" alt="FrankenNetworkX - clean-room memory-safe NetworkX reimplementation">
</div>

FrankenNetworkX is a high-performance, Rust-backed drop-in replacement for [NetworkX](https://networkx.org/). Use it as a standalone library or as a NetworkX backend with zero code changes.

Documentation:

- [Quickstart](docs/quickstart.md)
- [Backend integration](docs/backend.md)
- [Migration guide](docs/migration.md)
- [Algorithm reference](docs/algorithms.md)
- [Performance notes](docs/performance.md)
- [Contributing](docs/contributing.md)

## Quick Start

```bash
pip install franken-networkx
```

### Standalone usage

```python
import franken_networkx as fnx

G = fnx.Graph()
G.add_edge("a", "b", weight=3.0)
G.add_edge("b", "c", weight=1.5)

path = fnx.shortest_path(G, "a", "c", weight="weight")
pr = fnx.pagerank(G)
components = fnx.connected_components(G)
```

### NetworkX backend (zero code changes)

```python
import networkx as nx
nx.config.backend_priority = ["franken_networkx"]

# All supported algorithms now dispatch to Rust automatically
G = nx.path_graph(100)
nx.shortest_path(G, 0, 99)
```

## Supported Algorithms

| Family | Functions |
|--------|-----------|
| Shortest path | `shortest_path`, `all_shortest_paths`, `dijkstra_path`, `bellman_ford_path`, `multi_source_dijkstra`, `has_path`, `shortest_path_length`, `average_shortest_path_length`, `single_source_shortest_path`, `single_source_shortest_path_length`, `all_pairs_shortest_path`, `all_pairs_shortest_path_length`, `astar_path`, `astar_path_length`, `shortest_simple_paths` |
| Connectivity | `is_connected`, `connected_components`, `number_connected_components`, `node_connectivity`, `edge_connectivity`, `minimum_node_cut`, `bridges`, `articulation_points`, `strongly_connected_components`, `number_strongly_connected_components`, `is_strongly_connected`, `condensation`, `weakly_connected_components`, `number_weakly_connected_components`, `is_weakly_connected` |
| Centrality | `pagerank`, `betweenness_centrality`, `edge_betweenness_centrality`, `closeness_centrality`, `harmonic_centrality`, `eigenvector_centrality`, `degree_centrality`, `katz_centrality`, `hits` |
| Clustering | `clustering`, `triangles`, `transitivity`, `average_clustering`, `square_clustering` |
| Matching | `max_weight_matching`, `min_weight_matching`, `maximal_matching`, `min_edge_cover`, `is_matching`, `is_maximal_matching`, `is_perfect_matching` |
| Flow | `maximum_flow`, `maximum_flow_value`, `minimum_cut`, `minimum_cut_value` |
| Trees | `minimum_spanning_tree`, `maximum_spanning_tree`, `partition_spanning_tree`, `random_spanning_tree`, `number_of_spanning_trees`, `is_tree`, `is_forest`, `is_arborescence`, `is_branching` |
| Euler | `eulerian_circuit`, `eulerian_path`, `is_eulerian`, `has_eulerian_path`, `is_semieulerian` |
| Paths & Cycles | `all_simple_paths`, `cycle_basis`, `simple_cycles`, `find_cycle`, `is_simple_path` |
| Operators | `complement`, `union`, `intersection`, `compose`, `difference`, `symmetric_difference` |
| Bipartite | `is_bipartite`, `bipartite_sets` |
| Coloring | `greedy_color` |
| Distance | `diameter`, `radius`, `center`, `periphery`, `eccentricity`, `density`, `barycenter` |
| Efficiency | `global_efficiency`, `local_efficiency` |
| Traversal | `bfs_edges`, `bfs_tree`, `bfs_predecessors`, `bfs_successors`, `bfs_layers`, `descendants_at_distance`, `dfs_edges`, `dfs_tree`, `dfs_predecessors`, `dfs_successors`, `dfs_preorder_nodes`, `dfs_postorder_nodes` |
| DAG | `topological_sort`, `topological_generations`, `dag_longest_path`, `dag_longest_path_length`, `lexicographic_topological_sort`, `is_directed_acyclic_graph`, `ancestors`, `descendants`, `transitive_closure`, `transitive_reduction` |
| Link prediction | `common_neighbors`, `jaccard_coefficient`, `adamic_adar_index`, `preferential_attachment`, `resource_allocation_index` |
| Reciprocity | `reciprocity`, `overall_reciprocity` |
| Graph metrics | `average_degree_connectivity`, `rich_club_coefficient`, `s_metric` |
| Community | `louvain_communities`, `greedy_modularity_communities`, `label_propagation_communities`, `modularity` |
| Isomorphism | `is_isomorphic`, `could_be_isomorphic`, `fast_could_be_isomorphic`, `faster_could_be_isomorphic` |
| Planarity | `is_planar` |
| Approximation | `min_weighted_vertex_cover`, `maximum_independent_set`, `max_clique`, `clique_removal`, `large_clique_size` |
| Dominating | `dominating_set`, `is_dominating_set` |
| Isolates | `isolates`, `is_isolate`, `number_of_isolates` |
| Boundary | `edge_boundary`, `node_boundary` |
| Other | `core_number`, `voterank`, `find_cliques`, `graph_clique_number`, `number_of_cliques`, `degree_assortativity_coefficient`, `average_neighbor_degree`, `wiener_index`, `non_neighbors`, `is_empty`, `relabel_nodes`, `degree_histogram` |
| Generators | `path_graph`, `cycle_graph`, `star_graph`, `complete_graph`, `empty_graph`, `gnp_random_graph`, `watts_strogatz_graph`, `barabasi_albert_graph` |
| I/O | `read_edgelist`, `write_edgelist`, `read_adjlist`, `write_adjlist`, `read_graphml`, `write_graphml`, `node_link_data`, `node_link_graph` |
| NumPy/SciPy | `to_numpy_array`, `from_numpy_array`, `to_scipy_sparse_array`, `from_scipy_sparse_array` |
| Conversion | `from_dict_of_dicts`, `to_dict_of_dicts`, `from_dict_of_lists`, `to_dict_of_lists`, `from_edgelist`, `to_edgelist`, `convert_node_labels_to_integers`, `from_pandas_edgelist`, `to_pandas_edgelist` |
| Drawing | `draw`, `draw_spring`, `draw_circular`, `draw_kamada_kawai`, `draw_planar`, `draw_random`, `draw_shell`, `draw_spectral`, `spring_layout`, `circular_layout`, `kamada_kawai_layout`, `planar_layout`, `random_layout`, `shell_layout`, `spectral_layout` (delegates to NetworkX/matplotlib) |

## Graph Types

- `Graph` -- undirected graph
- `DiGraph` -- directed graph (algorithms automatically convert to undirected where needed)

## Examples

- [examples/basic_usage.py](examples/basic_usage.py) -- standalone graph construction, algorithms, and round-trips
- [examples/backend_mode.py](examples/backend_mode.py) -- NetworkX backend dispatch with zero call-site changes
- [examples/social_network.py](examples/social_network.py) -- community and centrality analysis on a real graph
- [examples/benchmark_comparison.py](examples/benchmark_comparison.py) -- lightweight local comparison against NetworkX

## Requirements

- Python 3.10+
- No Rust toolchain needed for `pip install` (pre-built wheels provided)

## Development

```bash
pip install maturin
maturin develop --features pyo3/abi3-py310
pytest tests/python/ -v
python3 scripts/verify_docs.py
```

## What Makes This Project Special

Canonical Graph Semantics Engine (CGSE): deterministic tie-break policies with complexity witness artifacts per algorithm family.

This is treated as a core identity constraint, not a best-effort nice-to-have.

## Methodological DNA

This project uses four pervasive disciplines:

1. alien-artifact-coding for decision theory, confidence calibration, and explainability.
2. extreme-software-optimization for profile-first, proof-backed performance work.
3. RaptorQ-everywhere for self-healing durability of long-lived artifacts and state.
4. frankenlibc/frankenfs compatibility-security thinking: strict vs hardened mode separation, fail-closed compatibility gates, and explicit drift ledgers.

## Current State

- project charter docs established.
- legacy oracle cloned:
  - `/dp/franken_networkx/legacy_networkx_code/networkx`
- FrankenSQLite exemplar spec copied locally:
  - `reference_specs/COMPREHENSIVE_SPEC_FOR_FRANKENSQLITE_V1.md`
- first executable vertical slice landed:
  - deterministic graph core (`fnx-classes`),
  - strict/hardened runtime + evidence ledger (`fnx-runtime`),
  - unweighted shortest path + complexity witness (`fnx-algorithms`),
  - fixture-driven conformance harness (`fnx-conformance`).
- second vertical slice landed:
  - deterministic dispatch routing (`fnx-dispatch`),
  - conversion routes (`fnx-convert`),
  - edgelist parser/writer (`fnx-readwrite`),
  - RaptorQ sidecar + scrub/decode drill pipeline (`fnx-durability`).
- third vertical slice landed:
  - live/cached view semantics with revision invalidation (`fnx-views`),
  - JSON graph read/write path (`fnx-readwrite`),
  - oracle-generated view/JSON fixtures (`fnx-conformance`),
  - percentile benchmark gate with durability sidecars (`scripts/run_benchmark_gate.sh`).
- fourth vertical slice landed:
  - deterministic connected-components and component-count witnesses (`fnx-algorithms`),
  - deterministic (`empty/path/star/cycle/complete`) + seeded graph generators with strict/hardened guards (`fnx-generators`),
  - oracle-generated components/generators fixtures (`fnx-conformance`),
  - expanded drift-free conformance corpus (12 fixtures) with durability artifacts.
- fifth vertical slice landed:
  - deterministic degree-centrality with complexity witness (`fnx-algorithms`),
  - cycle-graph edge-order parity tightening for larger `n` (`fnx-generators`),
  - oracle-generated degree-centrality fixture + stronger cycle fixture (`fnx-conformance`),
  - expanded drift-free conformance corpus (13 fixtures) with durability artifacts.
- sixth vertical slice landed:
  - deterministic closeness-centrality with WF-improved semantics (`fnx-algorithms`),
  - conformance operation/schema support for closeness centrality (`fnx-conformance`),
  - oracle-generated closeness-centrality fixture (`fnx-conformance`),
  - expanded drift-free conformance corpus (14 fixtures) with durability artifacts.
- seventh vertical slice landed:
  - deterministic minimum-cut surface paired with the existing Edmonds-Karp max-flow path (`fnx-algorithms`),
  - conformance operation/schema support for `minimum_cut_query` (`fnx-conformance`),
  - oracle-anchored minimum-cut strict fixture (`fnx-conformance`),
  - expanded drift-free conformance corpus (16 fixtures) with durability artifacts.

## V1 Scope

- Graph, DiGraph, MultiGraph core semantics; - shortest path/components/centrality/flow scoped sets; - serialization core formats.

## Architecture Direction

graph API -> graph storage -> algorithm modules -> analysis and serialization

## Compatibility and Security Stance

Preserve NetworkX-observable algorithm outputs, tie-break behavior, and graph mutation semantics for scoped APIs.

Defend against malformed graph ingestion, attribute confusion, and algorithmic denial vectors on adversarial graphs.

## Performance and Correctness Bar

Track algorithm runtime tails and memory by graph size/density; gate complexity regressions for adversarial classes.

Maintain deterministic graph semantics, tie-break policies, and serialization round-trip invariants.

## Key Documents

- AGENTS.md
- COMPREHENSIVE_SPEC_FOR_FRANKENNETWORKX_V1.md

## Next Steps

1. Expand fixture corpus to larger legacy families for matching and additional centrality variants.
2. Expand flow-family coverage beyond max-flow + min-cut (directed semantics hardening, larger adversarial flow fixtures, and stress fixtures).
3. Add format breadth beyond edgelist/json (adjlist/graphml scoped paths).
4. Add benchmark families and p50/p95/p99 regression gates across centrality and flow workloads.
5. Tighten strict/hardened drift budgets with per-family parity thresholds.

## Porting Artifact Set

- PLAN_TO_PORT_NETWORKX_TO_RUST.md
- EXISTING_NETWORKX_STRUCTURE.md
- PROPOSED_ARCHITECTURE.md
- FEATURE_PARITY.md

These four docs are now the canonical porting-to-rust workflow for this repo.
