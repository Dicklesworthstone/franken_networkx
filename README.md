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
| Other | `core_number`, `voterank`, `find_cliques`, `number_of_cliques`, `degree_assortativity_coefficient`, `average_neighbor_degree`, `wiener_index`, `non_neighbors`, `is_empty`, `relabel_nodes`, `degree_histogram` |
| Generators | `path_graph`, `cycle_graph`, `star_graph`, `complete_graph`, `empty_graph`, `gnp_random_graph`, `watts_strogatz_graph`, `barabasi_albert_graph` |
| I/O | `read_edgelist`, `write_edgelist`, `read_adjlist`, `write_adjlist`, `read_graphml`, `write_graphml`, `node_link_data`, `node_link_graph` |
| NumPy/SciPy | `to_numpy_array`, `from_numpy_array`, `to_scipy_sparse_array`, `from_scipy_sparse_array` |
| Conversion | `from_dict_of_dicts`, `to_dict_of_dicts`, `from_dict_of_lists`, `to_dict_of_lists`, `from_edgelist`, `to_edgelist`, `convert_node_labels_to_integers`, `from_pandas_edgelist`, `to_pandas_edgelist` |
| Drawing | `draw`, `draw_spring`, `draw_circular`, `draw_kamada_kawai`, `draw_planar`, `draw_random`, `draw_shell`, `draw_spectral`, `spring_layout`, `circular_layout`, `kamada_kawai_layout`, `planar_layout`, `random_layout`, `shell_layout`, `spectral_layout` (delegates to NetworkX/matplotlib) |

## Graph Types

- `Graph` -- undirected graph
- `DiGraph` -- directed graph
- `MultiGraph` -- undirected multigraph (parallel edges keyed by integer)
- `MultiDiGraph` -- directed multigraph

All four types share the same method surface (add/remove/subgraph/copy/to_directed/to_undirected) and the same algorithm dispatch; multigraph variants collapse parallel edges when a simple-graph algorithm is invoked.

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

## Conformance Policy

`pytest tests/python/` is the canonical conformance and parity gate for
FrankenNetworkX's public, NetworkX-compatible behavior. It exercises the
installed Python package surface that users actually call, so behavior decisions
are made there first.

`fnx-conformance` remains the curated Rust-side evidence harness. It replays
selected oracle fixtures, emits structured logs and replay commands, and
produces durable artifacts under `artifacts/conformance/latest/`. When pytest
expectations and harness fixtures drift, the harness is updated to match the
canonical Python parity contract rather than treated as a competing source of
truth.

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

The canonical, machine-checked counts for the public surface and parity test suite live outside this README so they don't rot:

- **Public API inventory:** see [`docs/coverage.md`](docs/coverage.md), generated from `franken_networkx.__all__` by `scripts/generate_coverage_matrix.py`. It reports per-export classification as `RUST_NATIVE` / `PY_WRAPPER` / `NX_DELEGATED` / `CLASS` / `CONSTANT`.
- **Parity suite:** `pytest tests/python/` is the canonical source of truth; run it and read the summary line.
- **Bead backlog:** `bv --robot-triage` for the current open/in-progress count.

Structural headlines that change less often:

- **Rust core:** 12 workspace crates including `fnx-cgse` (CGSE engine). `fnx-algorithms` covers 280+ algorithms across shortest path, connectivity, centrality, clustering, matching, flow, trees, Euler, DAG, traversal, community, isomorphism, and more.
- **Python bindings:** `crates/fnx-python/src/algorithms.rs` releases the GIL via `py.allow_threads(...)` at hundreds of call sites and avoids callbacks into upstream NetworkX.
- **NetworkX backend mode:** entry points registered in the package metadata; a curated set of algorithms in `backend.py:_SUPPORTED_ALGORITHMS` dispatch into Rust when `backend="franken_networkx"` is selected.
- **CI:** G1-G8 fail-closed gate topology in `.github/workflows/ci.yml` (fmt → clippy → rust tests → python tests → e2e → docs → conformance → performance → UBS → fuzz smoke → RaptorQ scrub).
- **CGSE (Canonical Graph Semantics Engine):** `fnx-cgse` crate ships a 12-variant `TieBreakPolicy` sum type, `ComplexityWitness` with length-prefixed Merkle decision-path hash, `WitnessSink`, `WitnessLedger`, and a V1 policy registry mapping reference algorithms to their canonical policies; wired into `fnx-algorithms` at hundreds of call sites.
- **Strict/Hardened modes:** `CgsePolicyEngine` in `fnx-runtime` implements mode-aware decision-theoretic action selection with evidence terms, structured `DecisionRecord`s, and fail-closed defaults.
- **Durability:** `fnx-durability` generates RaptorQ sidecars, runs scrub verification, and emits decode proofs. Used in CI G8 gate.

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

See [`REALITY_CHECK_BRIDGE_PLAN_2026-04-08.md`](REALITY_CHECK_BRIDGE_PLAN_2026-04-08.md) for the full bridge-plan bead set, and `bv --robot-triage` for the current top-of-backlog. Durable priorities:

1. **Wire strict/hardened modes into parsers (D2-D4):** the D1 decision is resolved in favor of implementation; remaining work is connecting runtime policy state to `fnx-readwrite` entry points and proving strict/hardened behavior with ≥24 strict and ≥24 hardened fixtures.
2. **Conformance regeneration (B2-B4):** refresh `artifacts/conformance/latest/` reports and add a CI freshness gate.
3. **Performance proof artifacts (E3):** run the profile-and-prove optimization loop for each SLO row to earn the SPEC §17 budgets.
4. **Algorithm surface quality:** track remaining nx-parity gaps (e.g. multigraph serialization, backend dispatch tail) via beads; see `bv --robot-triage` for the current set.

## Porting Artifact Set

- PLAN_TO_PORT_NETWORKX_TO_RUST.md
- EXISTING_NETWORKX_STRUCTURE.md
- PROPOSED_ARCHITECTURE.md
- FEATURE_PARITY.md

These four docs are now the canonical porting-to-rust workflow for this repo.
