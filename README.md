# FrankenNetworkX

<div align="center">
  <img src="franken_networkx_illustration.webp" alt="FrankenNetworkX — Rust-backed drop-in replacement for NetworkX">
</div>

<div align="center">

[![CI](https://github.com/Dicklesworthstone/franken_networkx/actions/workflows/ci.yml/badge.svg)](https://github.com/Dicklesworthstone/franken_networkx/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/franken-networkx.svg)](https://pypi.org/project/franken-networkx/)
[![Python](https://img.shields.io/pypi/pyversions/franken-networkx.svg)](https://pypi.org/project/franken-networkx/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Rust 2024](https://img.shields.io/badge/rust-2024_edition-orange.svg)](rust-toolchain.toml)

</div>

**FrankenNetworkX is a Rust-backed, byte-for-byte–compatible drop-in for [NetworkX](https://networkx.org/).** Use it as a standalone library with the familiar NetworkX API, or wire it in as a `networkx>=3.0` backend so existing code dispatches into Rust with zero call-site changes.

```bash
pip install franken-networkx
```

No Rust toolchain required. Pre-built wheels are provided for Linux, macOS, and Windows (Python 3.10+, ABI3).

---

## TL;DR

### The Problem

NetworkX is the canonical Python graph library: rich, correct, comprehensive, and slow on anything that isn't toy-sized. Its pure-Python adjacency, Python-level inner loops, and per-call dict bookkeeping turn graph analytics over even modest graphs (10⁵–10⁶ nodes) into multi-minute affairs. Most "alternatives" pay for speed in compatibility: they expose a different API, change tie-break behavior, lose attribute fidelity, or drop entire algorithm families.

### The Solution

FrankenNetworkX is a Rust port of NetworkX that treats **observable behavior** as a hard constraint. Graph mutation semantics, iteration order, tie-break choices, exception classes, error message wording, and serialization round-trip behavior are all part of the contract. Where pure-Python NetworkX would call `dict[unhashable]`, FrankenNetworkX raises the same `TypeError`. Where NetworkX iterates a `dict_keys` in insertion order, FrankenNetworkX does too. Where NetworkX returns a generator, FrankenNetworkX returns a generator, not a list with a different repr.

That contract is enforced by a 377-file Python parity test suite, by a curated Rust differential conformance harness, and by five auto-generated audit ledgers (coverage matrix, raw-vs-public, delegation, upstream divergence, API ergonomics) that fail CI if any public symbol drifts.

### Why FrankenNetworkX?

| Feature | NetworkX 3.x | FrankenNetworkX |
|---|---|---|
| Backing language | Pure Python | Rust 2024 (`#![forbid(unsafe_code)]`) |
| Graph types | `Graph`, `DiGraph`, `MultiGraph`, `MultiDiGraph` | Same four, same method surface |
| Adjacency storage | nested `dict` | deterministic `IndexMap`-based, insertion-order preserving |
| GIL release on heavy work | n/a (pure Python) | yes; hundreds of `py.allow_threads(...)` sites |
| Public API exports | ~730 | **763** classified in `docs/coverage.md` |
| Backend-dispatch surface | n/a | **316** algorithms registered in `backend.py` |
| Tie-break determinism | implicit | explicit **CGSE** (12-variant `TieBreakPolicy`) |
| Complexity audit | none | `ComplexityWitness` per call, length-prefixed Blake3 decision-path ledger |
| Strict vs hardened parsing | n/a | mode-aware `CgsePolicyEngine` with fail-closed defaults |
| Durable conformance artifacts | n/a | RaptorQ erasure-coded sidecars with decode-proof receipts |
| Fuzz harness | none | **33** cargo-fuzz binaries across parsers + algorithm families |
| CI gates | tests | **G0–G8**: docs freshness → fmt → clippy → rust tests → python parity → e2e → docs → examples → conformance → performance SLO → UBS → fuzz smoke → RaptorQ scrub |

---

## Why a Port, Not a Wrapper?

There are several existing approaches to "faster NetworkX." Each has tradeoffs the FrankenNetworkX design rejects.

| Approach | What it does | Why we didn't choose it |
|---|---|---|
| **Subclassing or monkey-patching nx graphs with C/Cython adjacency** | Replace specific hot loops with native code, leave the rest in Python. | Doesn't move the cost: nested Python dicts still dominate memory and cache behavior. Algorithm-level work happens in pure Python. GIL stays held. |
| **Wrapping a separate Rust/C++ graph engine and copying data in/out** | Convert nx graphs into a foreign representation, run algorithms there, convert results back. | The conversion is the entire workload for short-running algorithms. Attribute fidelity gets lost. Tie-break behavior diverges. Algorithm coverage is sparse. |
| **Rewriting in Rust with a "Rust-idiomatic" API** | Build a clean-slate Rust graph library with its own type system. | Users have to rewrite. The behavioral oracle (NetworkX) becomes invisible. Iteration order drift makes results non-portable. |
| **FrankenNetworkX** | Port the algorithms into native Rust, expose the *same* Python API NetworkX exposes (same names, same signatures, same iteration order, same exception classes, same tie-break behavior), and stand up an audit harness that fails CI if any public symbol drifts. | This is the design. The cost is high one-time engineering. The benefit is real drop-in compatibility without behavioral surprises. |

The discipline difference is enforced by tooling, not goodwill:

- The Python parity gate (`pytest tests/python/`, 377 files) compares fnx-vs-nx call by call across thousands of fixtures, including iteration order, exception class, and error wording.
- The auto-generated audit ledgers under `docs/` fail CI if `__all__` drifts or if a wrapper acquires a NetworkX delegation route that isn't documented.
- The CGSE complexity-witness ledger gives every algorithm execution a reproducible length-prefixed Blake3 receipt, so behavioral parity can be regression-locked, not just spot-checked.

### Comparison with other "faster graphs"

| Library | API style | Drop-in for nx? | Tie-break parity? | Coverage | Notes |
|---|---|---|---|---|---|
| **NetworkX** | nx.* | n/a | n/a (reference) | comprehensive | Pure Python; the behavioral oracle for everything below. |
| **igraph** (`python-igraph`) | `Graph` class with its own methods | no; different method names, different return types | no; internal node IDs are integer indices, often re-numbered | strong for the algorithms it supports | Mature, fast, C core. Different conceptual model: vertices are dense integer indices, not arbitrary labels. |
| **graph-tool** | `Graph` with vertex/edge property maps | no; C++/Python hybrid API | no | strong for analytics + statistics | Boost-backed, very fast, but requires a custom build pipeline (no PyPI wheel). |
| **rustworkx** | `PyGraph`/`PyDiGraph` with integer node IDs | partial; explicit conversion API | no; integer-index based | growing | High-quality Rust core; intentionally not a drop-in replacement. |
| **graspologic** / **networkx-cuda** / **cugraph** | various, often GPU-backed | partial; mostly nx-shaped but algorithm coverage varies widely | varies | varies | Often optimize the inner loop of specific algorithms (PageRank, BFS, connected components) but require additional toolchains (CUDA, conda channels). |
| **FrankenNetworkX** | `fnx.*` mirroring `nx.*` exactly + backend dispatch | **yes**; same API surface, same iteration order, same exceptions, fallback to nx for unsupported | **yes**; explicit CGSE `TieBreakPolicy` per algorithm | 763 public exports, 316 backend-dispatchable, 25+ algorithm families | Pre-built ABI3 wheels. No GPU or extra toolchain. CGSE complexity-witness ledger. Audit ledgers for every public symbol. |

The honest summary: if the only thing you need is "PageRank on a huge graph as fast as possible" and you don't care about API shape or tie-break semantics, igraph or graph-tool or a GPU library may beat fnx on raw throughput for that single call. If you have an existing NetworkX codebase and you want it to *just work* without rewriting and without subtle behavior changes, fnx is built for that case.

---

## Design Principles

Five durable principles govern every commit:

1. **Observable behavior is the contract.** "Faster" is never a license to change a return value, a return type, an iteration order, an exception class, or an error message. Anything visible to the caller is part of the API. If a refactor would shift observable behavior, the refactor doesn't ship until the deviation is either reverted or moved into the upstream-divergence ledger as a documented, owner-acknowledged limitation.
2. **Tie-breaks are first-class.** Equivalent answers chosen by hash-order are bugs in waiting. CGSE pins the tie-break for every algorithm at the type level, records it in the `ComplexityWitness`, and Merkle-hashes the decision path so non-determinism is detectable, not "usually fine."
3. **Failure modes are explicit, not emergent.** Strict mode fails closed on malformed input. Hardened mode applies *bounded* recovery and writes a `DecisionRecord` for every recovery. There is no third mode where a parser silently fixes up bad input without telling anyone.
4. **Profile, prove, repeat.** Every performance optimization comes with a witness: a `cargo flamegraph` artifact, a behavior-isomorphism proof from the conformance corpus, a baseline-vs-after percentile table, and a delta artifact. "It's faster" without a proof artifact is not accepted.
5. **Long-lived artifacts are self-healing.** Conformance reports, performance baselines, and reproducibility ledgers ship with RaptorQ erasure-coded sidecars and decode-drill receipts. Bit-rot doesn't break replay.

None of these are aspirational. They are load-bearing in the CI gate topology, and skipping any one of them breaks the build.

---

## Two Ways to Use It

### 1. Standalone

Replace `networkx` with `franken_networkx` at the import line:

```python
import franken_networkx as fnx

G = fnx.Graph()
G.add_edge("a", "b", weight=3.0)
G.add_edge("b", "c", weight=1.5)
G.add_edge("a", "c", weight=10.0)

# Everything below returns the exact same thing as NetworkX would.
path        = fnx.shortest_path(G, "a", "c", weight="weight")  # ['a', 'b', 'c']
length      = fnx.shortest_path_length(G, "a", "c", weight="weight")  # 4.5
pr          = fnx.pagerank(G, alpha=0.85)
components  = list(fnx.connected_components(G))
btw         = fnx.betweenness_centrality(G)
mst         = fnx.minimum_spanning_tree(G)
```

### 2. NetworkX backend (zero call-site changes)

If you already have a NetworkX codebase, set the backend priority once and supported algorithms dispatch into Rust transparently. Unsupported algorithms fall back to NetworkX so nothing breaks.

```python
import networkx as nx
nx.config.backend_priority = ["franken_networkx"]

# Everything below now runs through FrankenNetworkX for supported algos.
G = nx.path_graph(10_000)
path = nx.shortest_path(G, 0, 9999)
pr   = nx.pagerank(G)
cc   = nx.connected_components(G)

# Or be explicit on a per-call basis:
path = nx.shortest_path(G, 0, 9999, backend="franken_networkx")
```

The backend is registered via Python entry points (`pyproject.toml`) so NetworkX picks it up automatically once `franken-networkx` is installed.

---

## Graph Types

| Type | Direction | Parallel edges | Notes |
|---|---|---|---|
| `fnx.Graph` | undirected | no | The default; `G[u][v]` returns the edge attribute mapping |
| `fnx.DiGraph` | directed | no | `successors` / `predecessors` / `in_degree` / `out_degree` |
| `fnx.MultiGraph` | undirected | yes (keyed by int) | `G[u][v][k]` returns the per-key attribute mapping |
| `fnx.MultiDiGraph` | directed | yes (keyed by int) | Combined directedness + parallel edges |

All four share the same method surface (`add_node`, `add_edge`, `remove_node`, `subgraph`, `copy`, `to_directed`, `to_undirected`, `edges`, `nodes`, `degree`, `adj`, `__getitem__`, etc.) and the same algorithm dispatch. MultiGraph variants collapse parallel edges transparently when a simple-graph algorithm is invoked.

```python
import franken_networkx as fnx

D = fnx.DiGraph()
D.add_edges_from([(1, 2, {"w": 3}), (2, 3, {"w": 1}), (1, 3, {"w": 5})])

assert list(D.successors(1)) == [2, 3]
assert D.in_degree(3) == 2
assert fnx.is_directed_acyclic_graph(D)
assert list(fnx.topological_sort(D)) == [1, 2, 3]
```

---

## Algorithm Catalog

FrankenNetworkX implements 25+ algorithm families. The table below is a high-level inventory. The canonical, machine-checked list lives in [`docs/coverage.md`](docs/coverage.md) (763 entries, auto-generated from `franken_networkx.__all__`) and [`python/franken_networkx/backend.py`](python/franken_networkx/backend.py) (the 316 algorithms wired into the NetworkX dispatcher).

| Family | Selected Functions |
|--------|--------------------|
| **Shortest path** | `shortest_path`, `all_shortest_paths`, `dijkstra_path`, `bellman_ford_path`, `multi_source_dijkstra`, `bidirectional_dijkstra`, `has_path`, `shortest_path_length`, `average_shortest_path_length`, `single_source_*`, `all_pairs_*`, `astar_path`, `astar_path_length`, `shortest_simple_paths`, `johnson`, `floyd_warshall*`, `find_negative_cycle` |
| **Connectivity** | `is_connected`, `connected_components`, `node_connectivity`, `edge_connectivity`, `minimum_node_cut`, `minimum_edge_cut`, `bridges`, `articulation_points`, `biconnected_components`, `strongly_connected_components`, `kosaraju_strongly_connected_components`, `condensation`, `weakly_connected_components`, `k_edge_components`, `k_edge_subgraphs`, `k_edge_augmentation`, `all_node_cuts`, `local_node_connectivity`, `local_edge_connectivity` |
| **Centrality** | `pagerank`, `betweenness_centrality`, `edge_betweenness_centrality`, `closeness_centrality`, `harmonic_centrality`, `eigenvector_centrality` (+ `_numpy`), `katz_centrality` (+ `_numpy`), `degree_centrality`, `hits`, `voterank`, `load_centrality`, `subgraph_centrality`, `information_centrality`, `second_order_centrality`, `group_betweenness_centrality`, `current_flow_betweenness`, `communicability`, `communicability_betweenness_centrality`, `communicability_exp` |
| **Clustering** | `clustering`, `triangles`, `transitivity`, `average_clustering`, `square_clustering`, `generalized_degree` |
| **Matching** | `max_weight_matching`, `min_weight_matching`, `maximal_matching`, `hopcroft_karp_matching`, `min_edge_cover`, `is_matching`, `is_maximal_matching`, `is_perfect_matching`, `is_edge_cover` |
| **Flow** | `maximum_flow`, `maximum_flow_value`, `minimum_cut`, `minimum_cut_value`, `min_cost_flow*`, `network_simplex`, `stoer_wagner`, `gomory_hu_tree`, `edmonds_karp` |
| **Trees & forests** | `minimum_spanning_tree`, `maximum_spanning_tree`, `partition_spanning_tree`, `random_spanning_tree`, `number_of_spanning_trees`, `is_tree`, `is_forest`, `is_arborescence`, `is_branching`, `maximum_branching`, `minimum_branching`, `greedy_branching`, `SpanningTreeIterator`, `ArborescenceIterator`, `tree_data`, `from_prufer_sequence`, `to_prufer_sequence` |
| **Euler** | `eulerian_circuit`, `eulerian_path`, `is_eulerian`, `has_eulerian_path`, `is_semieulerian`, `eulerize` |
| **Paths & cycles** | `all_simple_paths`, `all_simple_edge_paths`, `cycle_basis`, `simple_cycles`, `find_cycle`, `is_simple_path`, `has_cycle` |
| **Operators** | `complement`, `union`, `intersection`, `compose`, `difference`, `symmetric_difference`, `disjoint_union`, `cartesian_product`, `tensor_product`, `lexicographic_product`, `strong_product`, `power` |
| **Bipartite** | `is_bipartite`, `bipartite.sets`, `bipartite.color`, `bipartite.density`, `bipartite.biadjacency_matrix`, `bipartite.from_biadjacency_matrix`, `bipartite.projected_graph`, `bipartite.weighted_projected_graph` |
| **Coloring** | `greedy_color`, `strategy_*` strategies under `nx.coloring` |
| **Distance** | `diameter`, `radius`, `center`, `periphery`, `eccentricity`, `density`, `barycenter`, `resistance_distance` |
| **Efficiency** | `global_efficiency`, `local_efficiency`, `efficiency` |
| **Traversal** | `bfs_edges`, `bfs_tree`, `bfs_predecessors`, `bfs_successors`, `bfs_layers`, `descendants_at_distance`, `dfs_edges`, `dfs_tree`, `dfs_predecessors`, `dfs_successors`, `dfs_preorder_nodes`, `dfs_postorder_nodes`, `edge_bfs`, `edge_dfs`, `generic_bfs_edges` |
| **DAG** | `topological_sort`, `topological_generations`, `lexicographical_topological_sort`, `dag_longest_path`, `dag_longest_path_length`, `is_directed_acyclic_graph`, `ancestors`, `descendants`, `transitive_closure`, `transitive_reduction`, `immediate_dominators`, `dominance_frontiers`, `antichains`, `is_aperiodic`, `dag_to_branching` |
| **Link prediction** | `common_neighbors`, `jaccard_coefficient`, `adamic_adar_index`, `preferential_attachment`, `resource_allocation_index`, `cn_soundarajan_hopcroft`, `within_inter_cluster` |
| **Reciprocity** | `reciprocity`, `overall_reciprocity` |
| **Graph metrics** | `average_degree_connectivity`, `rich_club_coefficient`, `s_metric`, `wiener_index`, `hyper_wiener_index`, `degree_assortativity_coefficient`, `average_neighbor_degree`, `attribute_assortativity_coefficient`, `attribute_mixing_dict`, `attribute_mixing_matrix`, `degree_mixing_matrix`, `triadic_census`, `all_triads` |
| **Community** | `louvain_communities`, `greedy_modularity_communities`, `label_propagation_communities`, `asyn_fluidc`, `girvan_newman`, `k_clique_communities`, `kernighan_lin_bisection`, `community.modularity` |
| **Isomorphism** | `is_isomorphic`, `could_be_isomorphic`, `fast_could_be_isomorphic`, `faster_could_be_isomorphic`, `GraphMatcher`, `MultiGraphMatcher`, VF2++, tree isomorphism, ISMAGS |
| **Planarity** | `is_planar`, `check_planarity`, `check_planarity_recursive` |
| **Approximation** | `min_weighted_vertex_cover`, `maximum_independent_set`, `max_clique`, `clique_removal`, `large_clique_size`, `treewidth_min_degree`, `treewidth_min_fill_in`, `min_edge_dominating_set`, `traveling_salesman_problem`, `christofides`, `randomized_partitioning`, `one_exchange` |
| **Dominating** | `dominating_set`, `is_dominating_set`, `connected_dominating_set` |
| **Isolates** | `isolates`, `is_isolate`, `number_of_isolates` |
| **Boundary** | `edge_boundary`, `node_boundary` |
| **k-core / k-truss** | `core_number`, `k_core`, `k_shell`, `k_corona`, `k_crust`, `onion_layers`, `k_truss` |
| **Polynomial / spectral** | `tutte_polynomial`, `chromatic_polynomial`, `laplacian_spectrum`, `adjacency_spectrum`, `modularity_spectrum`, `fiedler_vector`, `algebraic_connectivity`, `simrank_similarity`, `google_matrix` |
| **Generators** | `path_graph`, `cycle_graph`, `star_graph`, `wheel_graph`, `complete_graph`, `complete_bipartite_graph`, `complete_multipartite_graph`, `empty_graph`, `petersen_graph`, `tutte_graph`, `random_geometric_graph`, `gnp_random_graph`, `gnm_random_graph`, `fast_gnp_random_graph`, `watts_strogatz_graph`, `barabasi_albert_graph`, `dual_barabasi_albert_graph`, `stochastic_block_model`, `random_regular_graph`, `random_tree` (Prüfer), `navigable_small_world_graph` (Kleinberg), `relaxed_caveman_graph`, `partial_duplication_graph`, `LFR_benchmark_graph`, `LCF_graph`, lattices (grid, hexagonal, triangular, hypercube), social datasets (`karate_club_graph`, `davis_southern_women_graph`, `florentine_families_graph`) |
| **I/O** | `read_edgelist` / `write_edgelist`, `read_weighted_edgelist` / `write_weighted_edgelist`, `read_adjlist` / `write_adjlist`, `read_multiline_adjlist` / `write_multiline_adjlist`, `read_graphml` / `write_graphml`, `read_gml` / `write_gml`, `read_pajek` / `write_pajek`, `read_leda`, `read_gexf` / `write_gexf`, `read_graph6` / `write_graph6`, `read_sparse6` / `write_sparse6`, `node_link_data` / `node_link_graph`, `cytoscape_data` / `cytoscape_graph`, `tree_data` / `tree_graph` |
| **NumPy / SciPy / pandas** | `to_numpy_array`, `from_numpy_array`, `to_scipy_sparse_array`, `from_scipy_sparse_array`, `to_pandas_edgelist`, `from_pandas_edgelist`, `to_pandas_adjacency`, `from_pandas_adjacency`, `attr_matrix`, `incidence_matrix`, `laplacian_matrix`, `adjacency_matrix` |
| **Conversion** | `from_dict_of_dicts`, `to_dict_of_dicts`, `from_dict_of_lists`, `to_dict_of_lists`, `from_edgelist`, `to_edgelist`, `convert_node_labels_to_integers`, `relabel_nodes`, `contracted_nodes`, `contracted_edge`, `identified_nodes`, `quotient_graph`, `line_graph`, `reverse` |
| **Drawing & layout** | `draw`, `draw_spring`, `draw_circular`, `draw_kamada_kawai`, `draw_planar`, `draw_random`, `draw_shell`, `draw_spectral`, `draw_bipartite`, `spring_layout`, `circular_layout`, `kamada_kawai_layout`, `planar_layout`, `random_layout`, `shell_layout`, `spectral_layout`, `bipartite_layout` (delegates to NetworkX + matplotlib) |

The full export list is in [`docs/coverage.md`](docs/coverage.md). To use a specific algorithm: `from franken_networkx import <name>`. If it's a `RUST_NATIVE`, `PY_WRAPPER`, or `CLASS` row in the coverage matrix, it works.

---

## Architecture

```
                ┌──────────────────────────────────────────────────────────┐
                │                Python package: franken_networkx          │
                │   __init__.py  •  backend.py  •  backend_info.py         │
                │   _fnx.pyi (stubs)  •  316 algorithms in backend dispatch│
                └────────────────────────────┬─────────────────────────────┘
                                             │  PyO3 / ABI3-py310
                                             ▼
   ┌──────────────────────────────────────────────────────────────────────────┐
   │                              fnx-python  (cdylib)                        │
   │   lib.rs  •  algorithms.rs  •  digraph.rs  •  generators.rs              │
   │   readwrite.rs  •  views.rs  •  cgse.rs   (releases GIL at hot paths)    │
   └────────┬───────────────────┬────────────────┬───────────────┬────────────┘
            │                   │                │               │
            ▼                   ▼                ▼               ▼
   ┌────────────────┐  ┌─────────────────┐  ┌──────────┐  ┌──────────────┐
   │  fnx-classes   │  │ fnx-algorithms  │  │ fnx-cgse │  │ fnx-readwrite│
   │  Graph,DiGraph │  │ 550+ pub fns:   │  │ TieBreak │  │ edgelist,GML │
   │  Multi*Graph   │  │ shortest path,  │  │ Policy   │  │ GraphML,JSON │
   │  IndexMap adj  │  │ centrality, etc │  │ Witness  │  │ Pajek,GEXF,..│
   └───────┬────────┘  └────────┬────────┘  │ Ledger   │  └──────────────┘
           │                    │           └────┬─────┘
           ▼                    ▼                ▼
   ┌────────────────┐  ┌──────────────────┐  ┌─────────────────────────────┐
   │   fnx-views    │  │  fnx-generators  │  │       fnx-runtime           │
   │  GraphView     │  │ classic, random, │  │  CompatibilityMode          │
   │  DiGraphView   │  │ scale-free,      │  │  (Strict | Hardened)        │
   │  CachedSnap-   │  │ lattice, social  │  │  CgsePolicyEngine           │
   │  cached        │  │ SBM, WS, BA, GNP │  │  DecisionRecord / evidence  │
   └────────────────┘  └──────────────────┘  └─────────────────────────────┘
                                             ┌─────────────────────────────┐
                                             │ fnx-dispatch  fnx-convert   │
                                             │ fnx-conformance fnx-durability│
                                             │ RaptorQ sidecars + scrub    │
                                             └─────────────────────────────┘
```

### The 12 Rust Crates

| Crate | Purpose |
|---|---|
| `fnx-classes` | Core graph types and deterministic adjacency storage (`IndexMap<Node, IndexMap<Neighbor, AttrMap>>`). Attribute storage via `BTreeMap`. Node and edge insertion order is preserved, which matters for tie-break parity. |
| `fnx-views` | Borrowed snapshot wrappers (`GraphView<'a>`, `DiGraphView<'a>`) plus revision-tracking `CachedSnapshotView` / `CachedDiGraphSnapshotView`. Used by the conformance harness and snapshot round-trip layer. The Python-facing live views (`NodeView`, `EdgeView`, `DegreeView`, `AdjacencyView`, `SubgraphView`) are defined in `crates/fnx-python/src/views.rs` as PyO3 classes on top of these primitives. |
| `fnx-dispatch` | Backend registry, dispatch routing, fail-closed decision plumbing for the NetworkX backend protocol. |
| `fnx-convert` | Conversions between graph types, NumPy / SciPy / pandas interop, dict-of-dicts and dict-of-lists round-trips, node-label remapping. |
| `fnx-algorithms` | ~47 KLOC across 550+ public functions covering shortest path, centrality, connectivity, clustering, matching, flow, trees, community, isomorphism, planarity, polynomials, spectral, traversal, and DAG families. |
| `fnx-generators` | Classic, random, scale-free, lattice, and social graph generators. Deterministic seeded RNG with NetworkX-byte-compatible edge enumeration order where contracted. |
| `fnx-readwrite` | Native Rust parsers and writers for **7 formats**: edgelist, adjlist, GraphML, GML, JSON (node-link), Pajek, GEXF. Cargo-fuzz hardened with 8 dedicated parser fuzzers. Format variants exposed at the Python layer (`read_weighted_edgelist`, `read_multiline_adjlist`, `read_leda`, `read_graph6`, `read_sparse6`) compose the native primitives or delegate to NetworkX for niche formats. |
| `fnx-cgse` | **Canonical Graph Semantics Engine.** 12-variant `TieBreakPolicy` sum type. `ComplexityWitness { n, m, dominant_term, observed_count, policy, seed, decision_path_blake3 }` with length-prefixed Blake3 hashing. `WitnessSink`, `WitnessLedger`, and a V1 policy registry mapping reference algorithms to canonical policies. |
| `fnx-runtime` | `CompatibilityMode::{Strict, Hardened}`, `CgsePolicyEngine`, structured `DecisionRecord`s with evidence terms, fail-closed defaults. |
| `fnx-conformance` | Curated parity harness; fixture replay; differential report generation; structured logs and replay commands; artifact emitters writing to `artifacts/conformance/latest/`. |
| `fnx-durability` | RaptorQ sidecar generation, integrity scrub, decode-proof artifacts for conformance fixture bundles, benchmark baselines, migration manifests, reproducibility ledgers, and long-lived state snapshots. |
| `fnx-python` | PyO3/maturin bindings; the `franken_networkx._fnx` cdylib; ABI3-py310 (one wheel works on Python 3.10+). Releases the GIL via `py.allow_threads(...)` at hundreds of call sites. |

---

## Canonical Graph Semantics Engine (CGSE)

CGSE is the project's core correctness mechanism. It treats algorithmic *tie-breaking* as part of the API contract rather than incidental behavior.

### The 12 Tie-Break Policies

Every algorithm declares, at the type level, which policy governs its choices when multiple equally-correct answers exist:

```rust
pub enum TieBreakPolicy {
    LexMin,                              // lex-min node/edge label
    LexMax,                              // lex-max node/edge label
    InsertionOrder,                      // adjacency-list order
    ReverseInsertionOrder,               // reverse adjacency-list order
    WeightThenLex,                       // weight ↑ then lex-min label
    LexThenWeight,                       // lex-min label then weight ↑
    DeterministicHash { seed: u64 },     // reproducible but order-agnostic
    DegreeMinThenLex,                    // min-degree node, ties lex-min
    DegreeMaxThenLex,                    // max-degree node, ties lex-min
    DfsPreorder,                         // DFS pre-order
    BfsLevelLex,                         // BFS level, within-level lex-min
    EdgeKeyLex,                          // multigraph edge key lex-min
}
```

Defined in [`crates/fnx-cgse/src/lib.rs:37`](crates/fnx-cgse/src/lib.rs). Each policy has a short stable identifier used in ledger entries and serialized artifacts.

### Complexity-class reference

The 10 dominant-term strings recognized by `fnx_cgse::analytic_upper_bound(term, n, m)`. Use them to interpret the `dominant_term` field of a `ComplexityWitness`:

| Term | Closed form | Typical algorithms |
|---|---|---|
| `n` | `n` | `degree_centrality`, `is_isolate`, single-node lookups |
| `m` | `m` | `eulerian_circuit`, edge-only scans |
| `n_plus_m` | `n + m` | BFS, DFS, `connected_components`, `topological_sort`, articulation points |
| `n_log_n` | `n · ⌈log₂ n⌉` | sorting-based reductions, lex-min element selection |
| `n_plus_m_log_n` | `(n + m) · ⌈log₂ n⌉` | Dijkstra with binary heap |
| `n_m` | `n · m` | Bellman-Ford, Brandes betweenness |
| `n_squared` | `n²` | dense-matrix shortest-paths, dense centrality |
| `n_m_alpha` | `n · m · α(n,m)` | Edmonds' max-weight matching, union-find-amortized algorithms |
| `m_log_m` | `m · ⌈log₂ m⌉` | Kruskal's MST (edge sort dominates) |
| `m_log_n` | `m · ⌈log₂ n⌉` | Prim's MST with binary heap |

If you build your own algorithm on top of fnx and want to participate in the witness ledger, pick the term that bounds your worst-case observed-op count, return it in the witness, and the runtime's complexity-bound verifier will catch any regression.

### The V1 policy registry

The `v1_policy_registry()` table pins a canonical tie-break policy and dominant complexity term for each of the 12 *reference* algorithms, the V1 set whose tie-break behavior is contractually frozen. Source: `ReferenceAlgorithm::policy` and `::dominant_complexity` in [`crates/fnx-cgse/src/lib.rs`](crates/fnx-cgse/src/lib.rs).

| Family | Reference algorithm | Tie-break policy | Dominant complexity |
|---|---|---|---|
| shortest_path | `dijkstra` | `WeightThenLex` | `n_plus_m_log_n` |
| shortest_path | `bellman_ford` | `InsertionOrder` | `n_m` |
| traversal | `bfs` | `InsertionOrder` | `n_plus_m` |
| traversal | `dfs` | `InsertionOrder` | `n_plus_m` |
| matching | `max_weight_matching` | `WeightThenLex` | `n_m_alpha` |
| matching | `min_weight_matching` | `WeightThenLex` | `n_m_alpha` |
| connectivity | `connected_components` | `LexMin` | `n_plus_m` |
| connectivity | `strongly_connected_components` | `InsertionOrder` | `n_plus_m` |
| trees | `kruskal` | `WeightThenLex` | `m_log_m` |
| trees | `prim` | `WeightThenLex` | `m_log_n` |
| euler | `eulerian_circuit` | `InsertionOrder` | `m` |
| dag | `topological_sort` | `InsertionOrder` | `n_plus_m` |

The choice of `InsertionOrder` for `bfs`/`dfs`/`bellman_ford`/`topological_sort` is exactly the NetworkX behavior: those algorithms iterate adjacency in the order the user inserted edges, and `IndexMap` preserves that. The choice of `WeightThenLex` for weighted algorithms reflects NetworkX's `heapq` semantics, where equal-weight heap entries are broken by Python's tuple comparison on subsequent fields (which lex-compares the node labels).

These assignments encode the same tie-break choices a careful reading of the NetworkX source would extract, except now they are machine-readable, versioned in source, and enforceable via the witness ledger. The broader algorithm surface (~550 functions) inherits the appropriate policy via the family the algorithm belongs to.

### Complexity Witnesses

Every algorithm call emits a structured `ComplexityWitness` capturing `n`, `m`, observed operation count, the policy identifier, and a length-prefixed Blake3 hash over the decision path. Witnesses can be drained from a `WitnessLedger` for offline audit, regression-locking, or reproducibility checks.

### Strict vs Hardened Modes

Two compatibility doctrines, both available at runtime:

- **Strict**: maximize observable compatibility for V1 scoped APIs. No behavior-altering repairs. Malformed input fails closed with structured error context.
- **Hardened**: preserve the API contract while applying bounded defensive recovery for malformed inputs and hostile edge cases. Useful when ingesting graphs from adversarial sources.

The choice is made through `CgsePolicyEngine` in `fnx-runtime`, which records every action selection as a `DecisionRecord` with evidence terms.

### Why determinism matters

Most NetworkX algorithms have multiple equally-correct answers. Consider `connected_components(G)` on a graph with two components. There is no inherent ordering between the components, and NetworkX's actual answer depends on Python's `dict` iteration order, which depends on insertion order, which depends on whatever sequence of `add_edge` calls produced the graph. Code that does `next(iter(connected_components(G)))` is implicitly depending on this chain.

A "faster" library that returns the same set of components but in a different order silently breaks every caller that depended on the original order. The crash, if any, surfaces far from the swap, usually as a downstream comparison or hash that produces a different result.

CGSE addresses this by making the tie-break *visible*:

```python
import franken_networkx as fnx
from franken_networkx._fnx import cgse  # bound Rust submodule

# Inspect the policy registry: which policy governs which algorithm.
# policy_registry() returns: { "<algorithm>": {"family": ..., "policy": ..., "dominant_complexity": ...} }
registry = cgse.policy_registry()
for algorithm, info in registry.items():
    print(f"{algorithm:30s} → policy={info['policy']:20s} bound={info['dominant_complexity']}")
# dijkstra                       → policy=weight_then_lex      bound=n_plus_m_log_n
# bellman_ford                   → policy=insertion_order      bound=n_m
# bfs                            → policy=insertion_order      bound=n_plus_m
# connected_components           → policy=lex_min              bound=n_plus_m
# max_weight_matching            → policy=weight_then_lex      bound=n_m_alpha
# topological_sort               → policy=insertion_order      bound=n_plus_m
# ...

# You can also query an algorithm's canonical policy directly:
print(cgse.algorithm_policy("dijkstra"))      # → TieBreakPolicy.weight_then_lex
print(cgse.algorithm_policy("unknown_algo"))  # → None
print(cgse.reference_algorithms()[:5])        # → ['dijkstra', 'bellman_ford', 'bfs', 'dfs', 'max_weight_matching']
```

### The complexity witness contract

Every algorithm execution emits a `ComplexityWitness`. The actual Rust struct is:

```rust
pub struct ComplexityWitness {
    pub n: usize,                       // node count
    pub m: usize,                       // edge count
    pub dominant_term: String,          // "n_log_n", "n_plus_m_log_n", "n_m", ...
    pub observed_count: u64,            // tie-break decisions + main-loop iterations
    pub policy: TieBreakPolicy,         // which policy governed tie-breaks
    pub seed: Option<u64>,              // RNG seed for randomized algorithms
    pub decision_path_blake3: [u8; 32], // length-prefixed Blake3 over the decision path
}
```

The 10 supported complexity-class terms in `fnx_cgse::analytic_upper_bound` are: `n`, `m`, `n_plus_m`, `n_log_n`, `n_plus_m_log_n`, `n_m`, `n_squared`, `n_m_alpha`, `m_log_m`, `m_log_n`. The analytic upper bound is computed against the term rather than stored in the witness, so the witness stays small and the bound is looked up on demand:

```rust
use fnx_cgse::{collect_witnesses, analytic_upper_bound, ComplexityWitness};

let (result, witnesses): (_, Vec<ComplexityWitness>) = collect_witnesses(|| {
    // any block of fnx algorithm calls
    fnx_algorithms::pagerank(&graph, 0.85, 100, 1e-6)
});

for w in &witnesses {
    if let Some(bound) = analytic_upper_bound(&w.dominant_term, w.n, w.m) {
        assert!(w.observed_count <= bound, "complexity regression!");
    }
}
```

Or use the `verify_complexity_bound(&witness)` and `assert_complexity_within_bounds(&witness)` helpers shipped from `fnx_cgse`. Two runs on the same graph with the same policy produce identical `decision_path_blake3` hashes; any ordering drift manifests as a hash mismatch, making non-determinism a regression-locked property.

This makes complexity regressions a CI gate, not a folklore expectation.

### Tie-break policies in action

Different policies on the same algorithm give different, but reproducible, answers:

```python
# Conceptually, fnx ships these per-algorithm. Most users never have to think about it;
# the policy that matches NetworkX's behavior is the default. The visibility matters
# when you're auditing for reproducibility.

# Dijkstra under WeightThenLex (the default, matching NetworkX): equal-weight
# alternatives broken by lex-min node label.
fnx.shortest_path(G, "a", "z", weight="w")

# The same algorithm under DfsPreorder would tie-break by DFS visit order;
# a different but equally-correct shortest path may emerge in the equal-weight case.
```

You should almost never override the default. The defaults are chosen to match NetworkX. The point is that *which* tie-break is in effect is now a contract, not an emergent property of Python dict layout.

---

## Quick Start

### Install

```bash
# from PyPI (pre-built wheels, no Rust toolchain required)
pip install franken-networkx

# with NumPy / SciPy extras
pip install 'franken-networkx[all]'

# from source (requires Rust nightly + maturin)
git clone https://github.com/Dicklesworthstone/franken_networkx
cd franken_networkx
pip install maturin
maturin develop --release --features pyo3/abi3-py310
```

### Run an algorithm

```python
import franken_networkx as fnx

# Build a small weighted graph
G = fnx.Graph()
G.add_weighted_edges_from([
    ("a", "b", 1.0),
    ("b", "c", 2.0),
    ("a", "c", 5.0),
    ("c", "d", 1.0),
    ("b", "d", 4.0),
])

print(fnx.shortest_path(G, "a", "d", weight="weight"))         # ['a', 'b', 'c', 'd']
print(fnx.shortest_path_length(G, "a", "d", weight="weight"))  # 4.0

print(sorted(fnx.pagerank(G).items()))
# [('a', 0.229...), ('b', 0.270...), ('c', 0.299...), ('d', 0.200...)]
# (b and c are the degree-3 hubs; a and d are degree-2 leaves of the cluster.)

print(list(fnx.connected_components(G)))
# [{'a', 'b', 'c', 'd'}]
```

### Drop in as a backend

```python
import networkx as nx

# Enable the backend once, application-wide.
nx.config.backend_priority = ["franken_networkx"]

G = nx.erdos_renyi_graph(1_000, 0.01, seed=42)
cc = nx.connected_components(G)              # routes to FrankenNetworkX
pr = nx.pagerank(G)                          # routes to FrankenNetworkX
diam = nx.diameter(G)                        # routes to FrankenNetworkX
```

### Round-trip I/O

```python
import franken_networkx as fnx

G = fnx.path_graph(5)
fnx.write_graphml(G, "graph.xml")
H = fnx.read_graphml("graph.xml")
assert sorted(H.edges()) == sorted(G.edges())
```

---

## Tutorial: A Complete Graph Analysis

A walkthrough that goes from raw data to insight using only fnx, demonstrating the end-to-end loop a real user would follow.

### 1. Build or load the graph

```python
import franken_networkx as fnx

# Option A: load Zachary's karate club (a classic ~34-node fixture).
G = fnx.karate_club_graph()

# Option B: load from an edgelist file. Whitespace-separated, with optional
# {"weight": value} attribute literals; exact format match with nx.
# G = fnx.read_edgelist("input.edgelist", create_using=fnx.Graph)

# Option C: build from scratch.
# G = fnx.Graph()
# G.add_edges_from([(0, 1), (1, 2), (2, 0), (3, 4), (4, 5)])

print(G.number_of_nodes(), "nodes,", G.number_of_edges(), "edges")
# 34 nodes, 78 edges
```

### 2. Inspect structural properties

```python
print("density:",  fnx.density(G))         # → 0.139...
print("diameter:", fnx.diameter(G))        # → 5
print("radius:",   fnx.radius(G))          # → 3
print("center:",   sorted(fnx.center(G)))  # → nodes at min eccentricity
print("is_connected:", fnx.is_connected(G))# → True

# Degree distribution.
hist = fnx.degree_histogram(G)
for d, count in enumerate(hist):
    if count:
        print(f"degree {d:2d}: {count}")
```

### 3. Rank nodes by centrality

```python
pr  = fnx.pagerank(G)
btw = fnx.betweenness_centrality(G)
clo = fnx.closeness_centrality(G)

# Top 5 by each measure:
def top5(d, label):
    rows = sorted(d.items(), key=lambda kv: kv[1], reverse=True)[:5]
    print(f"\nTop 5 by {label}:")
    for node, score in rows:
        print(f"  {node!s:>5} → {score:.4f}")

top5(pr,  "PageRank")
top5(btw, "betweenness")
top5(clo, "closeness")
```

For the karate club graph, both centralities surface nodes 0 ("Mr. Hi") and 33 ("Officer"), the two factional leaders. Cross-method agreement is a useful sanity check.

### 4. Detect community structure

```python
# Louvain (modularity-maximizing community detection).
comms = list(fnx.community.louvain_communities(G, seed=7))
print(f"\n{len(comms)} communities (modularity = "
      f"{fnx.community.modularity(G, comms):.4f}):")
for i, c in enumerate(comms):
    print(f"  community {i}: {sorted(c)}")
```

Louvain on the karate club typically finds 3–4 communities with modularity ≈ 0.42, splitting the graph along the actual social-faction lines documented by Zachary in 1977.

### 5. Compute shortest paths between every pair

```python
# all-pairs shortest path lengths (BFS for unweighted graphs).
ap = dict(fnx.all_pairs_shortest_path_length(G))

# Find the two most-distant nodes.
import heapq
furthest = max(
    ((u, v, ap[u][v]) for u in ap for v in ap[u] if u < v),
    key=lambda triple: triple[2],
)
print(f"\nfurthest pair: {furthest[0]} → {furthest[1]}, distance {furthest[2]}")
```

### 6. Export the analysis

```python
# Annotate nodes with PageRank before saving so downstream readers see it.
for node, score in pr.items():
    G.nodes[node]["pagerank"] = score

fnx.write_graphml(G, "karate_annotated.graphml")
print("\n→ wrote karate_annotated.graphml")
```

That entire pipeline is byte-for-byte identical to the corresponding NetworkX code; flip `fnx.` → `nx.` and run it again to verify.

### 7. Verify against the NetworkX oracle

```python
import networkx as nx

# Convert via node-link JSON so attributes are preserved exactly.
data  = fnx.node_link_data(G)
G_nx  = nx.node_link_graph(data)

# Re-run a load-bearing computation on each side and assert agreement.
assert fnx.diameter(G) == nx.diameter(G_nx)
assert {tuple(sorted(c)) for c in fnx.community.louvain_communities(G, seed=7)} == \
       {tuple(sorted(c)) for c in  nx.community.louvain_communities(G_nx, seed=7)}
print("→ fnx ↔ nx agreement verified on diameter + communities")
```

If that assertion fires, please file an issue. That is the contract.

---

## How a Call Flows Through the System

Tracing `fnx.pagerank(G, alpha=0.85)` from the Python call site down to native code and back:

```
 ┌────────────────────────────────────────────────────────────────────┐
 │  1. User: fnx.pagerank(G, alpha=0.85)                              │
 └─────────────────────┬──────────────────────────────────────────────┘
                       │  Python attribute lookup on the franken_networkx
                       │  package surface (__all__ entry).
                       ▼
 ┌────────────────────────────────────────────────────────────────────┐
 │  2. python/franken_networkx/__init__.py — public Python wrapper    │
 │     • Validates types, coerces nx graphs at the boundary if any.   │
 │     • For ~143 functions, checks an "argument shape" — if the      │
 │       caller passed a non-supported flavor (e.g. callable          │
 │       weight, exotic kwarg), routes via                            │
 │       _call_networkx_for_parity(...) and returns nx's answer.      │
 │     • Otherwise calls the bound Rust kernel:                       │
 │       franken_networkx._fnx.pagerank(G, alpha, ...)                │
 └─────────────────────┬──────────────────────────────────────────────┘
                       │  PyO3 type marshaling.
                       ▼
 ┌────────────────────────────────────────────────────────────────────┐
 │  3. crates/fnx-python/src/algorithms.rs — PyO3 binding             │
 │     • Borrows the underlying fnx_classes::Graph by reference.      │
 │     • py.allow_threads(|| { ... })  ← GIL released here.           │
 │     • Calls into fnx_algorithms::pagerank(...) with a CGSE         │
 │       PolicyContext that pins the tie-break policy.                │
 └─────────────────────┬──────────────────────────────────────────────┘
                       │  Native Rust call.
                       ▼
 ┌────────────────────────────────────────────────────────────────────┐
 │  4. crates/fnx-algorithms/src/...  — native algorithm              │
 │     • Iterates adjacency via IndexMap → deterministic order.       │
 │     • Records observed-op count + tie-break decisions in the       │
 │       CGSE WitnessLedger.                                          │
 │     • Returns Vec<f64> / HashMap<NodeId, f64>.                     │
 └─────────────────────┬──────────────────────────────────────────────┘
                       │  Result hand-off.
                       ▼
 ┌────────────────────────────────────────────────────────────────────┐
 │  5. PyO3 conversion — Rust types → PyDict / PyList / PyFloat       │
 │     • GIL is reacquired here.                                      │
 │     • dict iteration order is the order Rust emitted, matching     │
 │       the policy-defined enumeration order.                        │
 └─────────────────────┬──────────────────────────────────────────────┘
                       │  Return path back to Python.
                       ▼
 ┌────────────────────────────────────────────────────────────────────┐
 │  6. Python wrapper post-processing (if needed)                     │
 │     • For ~25 "wrapper-patched" functions, post-processes the      │
 │       raw output to match nx iteration order or coerce return      │
 │       types (cataloged in docs/raw_vs_public_audit.md).            │
 │     • Returns the user-visible result.                             │
 └────────────────────────────────────────────────────────────────────┘
```

In NetworkX backend mode (`nx.config.backend_priority = ["franken_networkx"]`), step 1 is preceded by an extra layer: NetworkX's dispatcher checks the supported-algorithm registry (`BackendInterface.can_run` against `_SUPPORTED_ALGORITHMS`), converts the nx graph to an fnx graph via `convert_from_nx`, dispatches to the fnx wrapper, and converts the result back via `convert_to_nx` (which recursively unwraps fnx graphs nested in dicts/lists/tuples/sets).

---

## Compatibility Doctrine

FrankenNetworkX's compatibility contract is not "best-effort similarity." It is a machine-checked guarantee policed by five auto-generated audit ledgers under [`docs/`](docs/):

| Ledger | Purpose |
|---|---|
| [`coverage.md`](docs/coverage.md) | Every `franken_networkx.__all__` export classified as `RUST_NATIVE`, `PY_WRAPPER`, `CLASS`, or `CONSTANT`. 763 entries. Drift fails CI. |
| [`raw_vs_public_audit.md`](docs/raw_vs_public_audit.md) | Every `_raw_X` Rust kernel cross-checked against its public wrapper. Documents the 25 wrapper-patched parity repairs where the public wrapper post-processes raw output to match NetworkX. |
| [`delegation_ledger.md`](docs/delegation_ledger.md) | Every `_call_networkx_*_for_parity(...)` call site enumerated: 143 public exports, 167 routes. Tracks which algorithms intentionally delegate edge cases to upstream NetworkX. |
| [`upstream_divergence_ledger.md`](docs/upstream_divergence_ledger.md) | Unified ledger of `native-parity`, `wrapper-patched`, `intentionally-delegated`, `raw-known-gap`, and `owner-acknowledged-limitation` rows. |
| [`api_ergonomics_audit.md`](docs/api_ergonomics_audit.md) | Signature-level drift detection: parameter names, defaults, and keyword-only contracts compared against NetworkX. |

If you find a behavior that doesn't match NetworkX and isn't listed in `upstream_divergence_ledger.md`, that's a bug, not a feature.

### Exception class hierarchy

FrankenNetworkX re-exports NetworkX's exception classes verbatim so `except nx.NetworkXError:` and `except fnx.NetworkXError:` catch the same instances. 14 of these classes are explicitly listed in `fnx.__all__` and show up as public `CLASS` exports in `docs/coverage.md`. The remaining two (`AmbiguousSolution`, `ExceededMaxIterations`) are not in `__all__` but are still reachable as `fnx.AmbiguousSolution` / `fnx.ExceededMaxIterations` via the package's `__getattr__` fallback to `networkx` (the identity is preserved: `fnx.AmbiguousSolution is nx.AmbiguousSolution`). The actual hierarchy (matches `networkx.exception`):

```
Exception
└── NetworkXException                       (base for everything below)
    ├── NetworkXError                       (general "wrong shape of input")
    ├── NetworkXPointlessConcept            (e.g. centrality on the empty graph)
    ├── NetworkXAlgorithmError              (algorithm-specific precondition violated)
    │   ├── NetworkXUnfeasible              (no feasible solution exists)
    │   │   ├── NetworkXNoPath              (no path between s and t)
    │   │   └── NetworkXNoCycle             (cycle expected but none found)
    │   └── NetworkXUnbounded               (objective unbounded)
    ├── HasACycle                           (cycle present where one is forbidden)
    ├── NetworkXNotImplemented              (also inherits NotImplementedError)
    ├── NodeNotFound                        (node missing from graph)
    ├── AmbiguousSolution                   (multiple valid answers)
    ├── ExceededMaxIterations               (loop hit its iteration cap)
    │   └── PowerIterationFailedConvergence (specifically eigenvector/PageRank failed)
    ├── NetworkXTreewidthBoundExceeded      (chordal — treewidth above the requested bound)
    └── NotATree                            (tree-only algorithm given a non-tree)
```

Important nuances to know about:

- **`NetworkXAlgorithmError` is *not* under `NetworkXError`.** Both are direct children of `NetworkXException`. If you write `except nx.NetworkXError:`, you will not catch `NetworkXNoPath`. Use `NetworkXException` (the broadest catch) or `NetworkXAlgorithmError` (the broadest algorithm catch).
- **`NetworkXNoPath` and `NetworkXNoCycle` are siblings under `NetworkXUnfeasible`**, not direct children of `NetworkXAlgorithmError`. `except nx.NetworkXUnfeasible:` catches both.
- **`NodeNotFound` is under `NetworkXException` directly.** It is *not* a subclass of `NetworkXError`.

The exception-class and error-message parity is a CI gate (`test_error_messages.py`). If `nx.shortest_path(G, "a", "z")` raises `NetworkXNoPath` with message `"No path between a and z."`, `fnx.shortest_path(G, "a", "z")` must raise the same class with the same wording. Bead cycles like `br-r37-c1-hpeix` and `br-r37-c1-jxvsu` were dedicated to locking missing-source/target wording across 30+ functions.

Why the strict parity: existing NetworkX code routinely does `except nx.NetworkXNoPath:` and inspects `str(e)`. Drifting an exception class or wording subtly breaks downstream pipelines that depend on it.

### Parity coverage today

- **731** Python-wrapper exports with no visible NetworkX route at runtime.
- **143** exports retain a parity-helper branch that delegates specific argument shapes or edge cases to NetworkX (typically: complex callable arguments, drawing/matplotlib, exotic format variants).
- **25** exports are "wrapper-patched": the Rust kernel runs the algorithm but the Python wrapper post-processes output ordering to match NetworkX's iteration semantics.
- **2** known native gaps: `_raw_is_planar` is still a necessary-only test (the public `is_planar` wrapper short-circuits with bipartite + girth bounds and then delegates the residual to NetworkX so K3,3, Petersen, and K5 all return correct answers).
- **0** "DIRECT_NETWORKX" public exports at the Python wrapper layer. Dispatch is always through the `_call_networkx_*_for_parity` helper layer tracked in the delegation ledger.

---

## Security Doctrine

The project defends against:

- **Malformed graph ingestion.** Every parser (`fnx-readwrite`) is cargo-fuzz hardened with 33 corpus-seeded targets covering edgelist, adjlist, GraphML, GML, JSON, Pajek, GEXF, node-link, attribute-value, and multigraph variants.
- **Attribute confusion.** `CgseValue` is a typed serde-compatible value with a controlled set of variants. GraphML/GML parsers validate keys, scope attributes, reject empty keys, escape `#` in edgelist attrs, and enforce typed parsing (so `bool=0/1` doesn't become an integer downstream).
- **Algorithmic denial vectors.** Strict mode fails closed on adversarial inputs (NaN edge weights, ±∞ weights on algorithms that can't handle them, malformed directed flags, namespace-prefix abuse). Hardened mode applies bounded defensive recovery.
- **Stack-safety on deep graphs.** Traversal-heavy algorithms (DFS, planarity, transitive closure) avoid unbounded recursion.

The minimum security bar (per [AGENTS.md](AGENTS.md)):

1. Threat-model notes for each major subsystem.
2. Fail-closed behavior for unknown incompatible features.
3. Adversarial fixture coverage and fuzz/property tests for high-risk parsers and state transitions.
4. Deterministic audit logs for recoveries and policy overrides.

---

## Durability: RaptorQ Everywhere

Long-lived artifacts emit RaptorQ erasure-coded sidecars and decode-proof receipts. This applies to:

- Conformance fixture bundles
- Benchmark baseline bundles
- Migration manifests
- Reproducibility ledgers
- Long-lived state snapshots

The `fnx-durability` crate produces three artifacts per recovery event: a repair-symbol generation manifest, an integrity scrub report, and a decode-proof receipt. The G8 CI gate runs the full scrub + decode-drill against the latest conformance bundle on every push.

---

## NetworkX Backend Protocol Primer

NetworkX 3.0+ ships a backend protocol that lets third-party libraries accelerate or replace algorithm implementations. FrankenNetworkX implements it through two Python entry points wired up in `pyproject.toml`:

```toml
[project.entry-points."networkx.backends"]
franken_networkx = "franken_networkx.backend:backend_interface"

[project.entry-points."networkx.backend_info"]
franken_networkx = "franken_networkx.backend_info:get_backend_info"
```

Once the package is installed, NetworkX picks up these entry points automatically. There is nothing to import on the user's side beyond `networkx`.

### What the dispatcher does on each call

For each `nx.<algorithm>(...)` call when `franken_networkx` is in the priority list (or supplied as `backend="franken_networkx"`):

1. NetworkX asks `backend_info.get_backend_info()` for the list of supported algorithms (parsed from `_SUPPORTED_ALGORITHMS` via AST so the metadata side is safe to import while NetworkX itself is still initializing).
2. NetworkX asks `BackendInterface.can_run(name, args, kwargs)` whether fnx will accept the call shape. `can_run` returns `False` for:
   - unsupported algorithm names,
   - argument shapes that fail `inspect.signature(...).bind(...)`,
   - `average_shortest_path_length` with a non-default `method=...`,
   - `node_connectivity` / `edge_connectivity` / `minimum_node_cut` / `minimum_edge_cut` when a custom `flow_func=...` is supplied (fnx's native flow implementation can't honor arbitrary user callables).
3. If `can_run` returns `True`, NetworkX calls `BackendInterface.convert_from_nx(G)` to materialize an fnx graph. The conversion preserves node insertion order via the `_topo_emit_edges_by_adj` helper so adjacency order matches what nx would have iterated.
4. The bound fnx function runs.
5. NetworkX calls `BackendInterface.convert_to_nx(result)`. This recursively unwraps fnx graphs hiding inside dicts, lists, tuples, and sets, so an algorithm that returns `dict[str, fnx.Graph]` (e.g. `gomory_hu_tree` subgraphs) returns `dict[str, nx.Graph]` to the caller.
6. Mutation-preserving dispatchables (`relabel_nodes`, `contracted_nodes`, `set_node_attributes`, `double_edge_swap`, ...) write the mutation back to the original graph rather than a throwaway copy.

### Per-call vs application-wide

```python
import networkx as nx

# Application-wide:
nx.config.backend_priority = ["franken_networkx"]

# Per-call:
nx.shortest_path(G, s, t, backend="franken_networkx")
```

The application-wide form still falls back to NetworkX for any algorithm fnx doesn't claim. The per-call form raises `NotImplementedError` if fnx doesn't claim the algorithm (you can wrap it yourself if you want a softer fallback).

### Fallback semantics

When `can_run` returns `False`, NetworkX uses the next backend in `backend_priority`, or pure-Python NetworkX itself. This is why FrankenNetworkX is safe to install in an existing nx codebase: in the worst case, you're back to vanilla nx.

---

## The Audit-Ledger System

The five ledgers under `docs/` are not documentation. They are *machine-checked invariants*. Each is generated by a script under `scripts/`, run on every CI push, and a drift between the generated file and what's checked in fails the build.

### How a public symbol gets classified

When a name appears in `franken_networkx.__all__`, `scripts/generate_coverage_matrix.py` does the following:

1. Look up the source location.
2. Classify the surface: is it a `_fnx`-bound Rust function (`RUST_NATIVE`)? A Python def (`PY_WRAPPER`)? A class (`CLASS`)? Something else (`CONSTANT`)?
3. Inspect the function body for `_call_networkx_*_for_parity(...)` call sites. If any are present, mark the runtime route as `NETWORKX_HELPER`; otherwise `PY_WRAPPER`.
4. Cross-reference `raw_vs_public_audit.json` to detect wrapper-patched exports (the ones where a `_raw_X` Rust kernel is post-processed by the public wrapper to match NetworkX's iteration order).
5. Cross-reference closed beads with bead-tagged comments (e.g. `# br-r37-c1-...`) to surface owner-acknowledged limitations.

The output is `docs/coverage.md`. If a developer adds a public symbol without classifying it, or sneaks in a NetworkX delegation that isn't covered by `delegation_ledger.md`, the regenerated file diverges from the committed file and CI breaks.

### The five ledgers and what they catch

- `coverage.md`: *Did anyone add a public symbol without thinking about classification?*
- `raw_vs_public_audit.md`: *Did anyone introduce a parity wrapper without documenting the underlying gap?*
- `delegation_ledger.md`: *Did anyone start delegating to NetworkX without noting it?*
- `upstream_divergence_ledger.md`: *Are intentional divergences from NetworkX still owned?*
- `api_ergonomics_audit.md`: *Did a signature drift in parameter names, defaults, or keyword-only contracts?*

Combined, these turn "byte-for-byte compatibility" from an aspiration into a property the CI enforces on every commit.

---

## Quality Gates (CI)

CI is structured as a strict, sequential gate topology in [`.github/workflows/ci.yml`](.github/workflows/ci.yml). A break at gate N short-circuits everything after it.

| Gate | Job | Purpose |
|---|---|---|
| **G0** | docs freshness | `README.md`, `FEATURE_PARITY.md`, `CHANGELOG.md` may not lag HEAD by more than 50 commits. |
| **G1** | fmt | `cargo fmt --all -- --check` on nightly. |
| **G2** | clippy | `cargo clippy --workspace --all-targets -- -D warnings` on Ubuntu + macOS + Windows. |
| **G3** | rust tests | `cargo test --workspace` on Ubuntu + macOS + Windows. |
| **G4** | python parity | `pytest tests/python/`, the canonical conformance gate (377 test files). |
| **G4b** | e2e | `scripts/e2e_integration_test.py` with NumPy + SciPy. |
| **G4c** | docs verifier | `scripts/verify_docs.py`; every code example in `docs/*.md` is import-checked and executed. |
| **G4d** | examples | All four `examples/*.py` scripts must run cleanly. |
| **G5** | conformance | `fnx-conformance` harness replay + dashboard generation into `artifacts/conformance/latest/`. |
| **G6** | performance SLO | `scripts/run_perf_slo_gate.py`; p50/p95/p99 thresholds per algorithm family. |
| **G7** | UBS | Ultimate Bug Scanner static analysis on the workspace. |
| **G7b** | fuzz smoke | 15 cargo-fuzz targets: 8 parser harnesses × 60 s + 7 algorithm harnesses × 30 s. |
| **G8** | RaptorQ | Generate / scrub / decode-drill RaptorQ sidecars for conformance + perf bundles. |

---

## Testing

The Python parity suite (`pytest tests/python/`) is the canonical truth. It is organized by parity flavor:

- **`test_*_parity.py`**: direct NetworkX-vs-FrankenNetworkX comparisons on fixed inputs.
- **`test_*_conformance.py`**: broad fixture-matrix parity sweeps.
- **`test_*_metamorphic.py`**: algebraic invariants (e.g., shortest-path triangle inequality, max-flow/min-cut duality, degree-sum identity, König's theorem, MST cycle property).
- **`test_*_hypothesis.py`**: property-based testing with `hypothesis` over randomized graphs.
- **`test_*_golden.py`**: frozen output snapshots that lock in current behavior against regression.
- **`test_thread_safety.py`**: concurrent dispatch under GIL release.
- **`test_error_messages.py`**: exception class + wording parity.

To run the suite:

```bash
maturin develop --release --features pyo3/abi3-py310
pytest tests/python/ -v --tb=long
```

Skip slow tests for a fast loop:

```bash
pytest tests/python/ -v -m "not slow"
```

Cross-validate a specific algorithm family against NetworkX:

```bash
pytest tests/python/ -v -k "shortest_path or dijkstra"
```

### Conformance Testing Methodology

The 377 Python test files implement five complementary testing strategies, each catching a different class of bug:

**1. Direct parity (`test_*_parity.py`).** Fix an input graph, call both `fnx.<func>(G)` and `nx.<func>(G_nx)`, assert equality. Catches "I got the wrong answer." The most basic and most numerous family.

```python
def test_dijkstra_path_parity():
    G_fnx = fnx.path_graph(20)
    G_nx  = nx.path_graph(20)
    assert fnx.dijkstra_path(G_fnx, 0, 19) == nx.dijkstra_path(G_nx, 0, 19)
```

**2. Conformance matrix (`test_*_conformance.py`).** Sweep over a fixture matrix: {path, cycle, complete, star, BA, ER, WS, bipartite} × {small, medium} × {weighted, unweighted}. Catches "I got the wrong answer on a *kind* of graph I didn't think to test individually." The conformance harness inside `fnx-conformance` writes structured logs and replay commands so a mismatch ships with a one-line reproducer.

**3. Metamorphic invariants (`test_*_metamorphic.py`).** These tests don't compare to a reference at all; they assert mathematical identities the algorithm must obey on *any* input. Catches "I got an answer that looks plausible but violates a structural law." Examples shipping today:

- **Shortest path triangle inequality.** `d(a,c) ≤ d(a,b) + d(b,c)` for all triples.
- **Max-flow / min-cut duality.** `max_flow(s,t).value == min_cut(s,t).value` on every directed graph.
- **Degree sum identity.** `sum(degree.values()) == 2 * G.number_of_edges()` on undirected.
- **König's theorem.** `len(max_matching) == len(min_vertex_cover)` on bipartite graphs.
- **MST cycle property.** Removing any MST edge and re-adding the cheapest edge in the resulting cut yields a graph of equal or greater weight.
- **PageRank stochastic invariant.** `sum(pagerank.values()) ≈ 1.0` to numerical tolerance.

**4. Property-based (`test_*_hypothesis.py`).** Use `hypothesis` to synthesize randomized graphs over arbitrary topologies and assert the same parity/metamorphic checks. Catches "I got the right answer on every hand-crafted fixture but miss a weird shape." Hypothesis shrinks failing inputs to minimal counterexamples automatically.

**5. Golden snapshots (`test_*_golden.py`).** Freeze the current output of a sensitive function on a fixed input. Any future change to the algorithm output for that fixed input fails CI loudly. Catches "I refactored the kernel and accidentally changed observable behavior." Used for tie-break-sensitive algorithms (`is_planar` on K3,3 / Petersen / K5, `dag_longest_path` tie-break, directed-distance metrics).

The five flavors run together as a single `pytest tests/python/` invocation: Gate G4 in CI.

Beyond Python: the `fnx-conformance` Rust crate runs a curated *differential* harness comparing fnx outputs against the legacy NetworkX oracle (the pure-Python `legacy_networkx_code/` reference copy) over a hardened fixture matrix. It emits structured JSON logs into `artifacts/conformance/latest/` that the CI dashboard generator turns into per-family parity reports, and those reports are RaptorQ-encoded by Gate G8 for self-healing replay.

---

## Performance

The performance doctrine in `AGENTS.md` is profile-first:

1. Baseline: record p50/p95/p99 and memory.
2. Profile: identify real hotspots.
3. Implement one optimization lever.
4. Prove behavior unchanged via conformance + invariant checks.
5. Re-baseline and emit delta artifact.

Hot paths that have already landed through this loop:

- Native-Rust nonfinite-weight scan for the Dijkstra / A* / PageRank +∞ gate.
- Index-based BFS + direct `PySet` emission for `connected_components`.
- Adjacency built from `G.neighbors` rather than `G[u]` for `find_cliques`.
- `square_clustering` bypasses `AtlasView` via `CachedNeighborSets`.
- `core_number` uses an O(|V|) self-loop guard rather than walking O(|E|) edges.
- `greedy_color` default routes through Rust matching NetworkX's `largest_first` tie-breaking.
- `complement` single-pass edge insertion via `extend_edges_unrecorded` / `complement_edges`.
- GIL released at hundreds of `py.allow_threads(...)` sites in `crates/fnx-python/src/algorithms.rs`.
- Sparse `HashMap` / `HashSet` adjacency replacing former O(n²) dense matrices in algorithm internals.

See [`docs/performance.md`](docs/performance.md) for guidance on benchmarking, and `examples/benchmark_comparison.py` for a runnable local A/B against NetworkX.

### Running your own benchmark

```python
import time, statistics, networkx as nx, franken_networkx as fnx

G_nx  = nx.barabasi_albert_graph(50_000, 5, seed=7)
G_fnx = fnx.barabasi_albert_graph(50_000, 5, seed=7)

def time_it(fn, *a, **kw):
    samples = []
    for _ in range(5):
        t0 = time.perf_counter()
        fn(*a, **kw)
        samples.append(time.perf_counter() - t0)
    return statistics.median(samples)

print("nx  pagerank:", time_it(nx.pagerank, G_nx))
print("fnx pagerank:", time_it(fnx.pagerank, G_fnx))

print("nx  cc:",       time_it(lambda g: list(nx.connected_components(g)),  G_nx))
print("fnx cc:",       time_it(lambda g: list(fnx.connected_components(g)), G_fnx))
```

The same script works in backend mode: leave `nx.config.backend_priority = ["franken_networkx"]` set and call only `nx.*`.

### Hot-path design notes

- **Index-based working sets.** Algorithm interiors operate on dense `Vec<usize>` node indices rather than chasing `IndexMap` lookups in tight loops. The index↔label map is built once at the start of a call via `graph.nodes_ordered()` + `graph.get_node_index(name)`.
- **Byte-array visited tracking.** BFS / DFS / SCC / matching kernels use a `vec![false; n]` byte array (≈45 sites), not `HashSet<NodeId>`, for visited tracking. One contiguous allocation per call, cache-friendly inner loops.
- **Min-heap without `Reverse` allocation.** Dijkstra-family algorithms use a custom `DijkstraState { dist: f64, seq: u64, node }` struct whose `Ord` impl reverses the dist comparison; the standard `BinaryHeap` acts as a min-heap with no per-push `Reverse(_)` wrapper.
- **FIFO tie-break in the comparator.** The `seq` insertion counter is the secondary key in `DijkstraState`'s `Ord` impl, so equal-distance entries pop in the order they were pushed (matching NetworkX's `heapq`-with-counter behavior bit-exactly). No post-pass needed.
- **Borrowed PyO3 returns.** `connected_components` emits a `PySet` per component directly from Rust instead of building a Vec first and converting in a second pass, which saves one full pass over the result.

### Cost model: when fnx wins, by how much, and why

The cost of a `fnx.algorithm(G)` call decomposes into four chunks:

| Chunk | Typical scale | Notes |
|---|---|---|
| Python → Rust marshaling | ~5–50 μs base + O(n + m) for graph conversion when a *new* graph is constructed | Reusing an existing fnx graph: ~5 μs total per call (attribute lookup only). Constructing a fresh fnx graph from an nx graph at call time: O(n + m) plus a constant ~5 μs/node, ~3 μs/edge for dict→IndexMap conversion. |
| Native algorithm execution | algorithm-dependent | Where fnx wins: tight Rust loops over `Vec<u32>` indices with packed visited bitsets. For algorithms that are linear in `(n + m)`, the GIL-released native loop is typically 10–100× faster than the equivalent NetworkX Python loop. |
| Rust → Python return marshaling | O(output size) | For algorithms returning a `dict[node, float]` of size `n`, this is the dominant tail. A `PyDict::set_item` per entry plus an arc-bumped node label string. ~0.5–1 μs per entry. |
| Wrapper-side post-processing (if any) | O(output size) | The 25 wrapper-patched functions add a single pass over the output for iteration-order normalization. Skipped for the 731 - 25 = 706 functions that don't need it. |

The performance break-even versus pure-Python NetworkX is roughly:

- **Below ~100 nodes**: marshaling cost dominates; NetworkX usually wins or ties.
- **100–10,000 nodes**: fnx wins for most algorithms by 5–50×. Cubic algorithms (e.g. Floyd-Warshall, exact betweenness on dense graphs) win more.
- **Above ~10,000 nodes**: fnx wins by 10–100× on most algorithms. Some (like `find_cliques` and `transitive_closure` on dense graphs) can be 1000× or more thanks to native bitset enumeration.

If you can keep the graph on the fnx side (don't reconstruct per call), the marshaling chunk vanishes. The backend-dispatch path automatically caches the converted graph for repeat calls.

---

## Algorithm Implementation Notes

The native algorithm implementations in `fnx-algorithms` favor textbook complexity bounds with one consistent twist: **every tie-break is pinned by a CGSE policy and recorded in the witness ledger**. The notes below cover the most-used families.

### Shortest path

- **Dijkstra.** Standard binary-heap Dijkstra. Internally uses a `DijkstraState { dist: f64, seq: u64, node }` struct whose `Ord` impl reverses the dist comparison (so a max-heap acts as a min-heap, with no per-push `Reverse(_)` wrapper) and tie-breaks equal-distance entries by insertion-counter `seq` to match NetworkX's `heapq`-with-counter behavior exactly. Single-source / multi-source / bidirectional all share the same kernel. The `+∞` and negative-weight gates are short-circuit native scans before the algorithm enters its main loop; invalid input fails fast or delegates to `nx` per the documented contract.
- **Bellman-Ford.** O(VE) relaxation with predecessor reconstruction. Negative-cycle detection scans the last-pass relaxation; the canonical error wording matches NetworkX's exact string (regression-locked in `test_bellman_ford_negative_cycle_message_parity.py`).
- **A*.** Standard heuristic-guided Dijkstra. The heuristic callable contract was tightened in commit [`b7d9e785`](https://github.com/Dicklesworthstone/franken_networkx/commit/b7d9e785) (`franken_networkx-74xw`) to honor NetworkX's exact signature.
- **Johnson all-pairs.** Edge re-weighting via Bellman-Ford + Dijkstra from every source. The inner-dict ordering of `johnson` was specifically locked to NetworkX's order in `br-r37-c1-9l73c`.

### Connectivity

- **Connected components.** Index-based BFS with a packed visited bitset. Emits `PySet` per component directly through PyO3, skipping a Vec → set conversion pass.
- **Strongly connected components.** Tarjan's iterative variant (avoids Rust stack overflow on deep DAGs). Kosaraju is available as `kosaraju_strongly_connected_components` for parity tests where NetworkX uses it specifically.
- **Articulation points / bridges.** Single DFS, parent-tracking, low-link propagation. The DFS visit order is the documented `BfsLevelLex` / `DfsPreorder` variant from CGSE.
- **Node / edge connectivity, min cuts.** Built on max-flow over a residual graph; custom `flow_func` callables are explicitly rejected by `can_run` so nx's slower-but-flexible path takes over when needed.

### Centrality

- **PageRank.** Power iteration with damping, native Rust nonfinite-weight scan, native dangling-node handling. Single iteration is one sparse matvec across the IndexMap-keyed adjacency. GIL released around the inner loop.
- **Betweenness.** Brandes' algorithm. Subset variants (`betweenness_centrality_subset`, `edge_betweenness_subset`) share the same accumulator infrastructure.
- **HITS.** Power iteration on the adjacency operator and its transpose. `numpy` variants offload eigensolvers to SciPy with sign/basis tolerance baked into the test layer.
- **Katz / eigenvector / closeness / harmonic.** Standard formulas. `harmonic_centrality` specifically matches NetworkX's set-based dict iteration order (locked in `br-r37-c1-rsom6`).
- **Voterank.** Iterative selection with explicit `LexMin` tie-break.

### Matching

- **Maximum-weight matching.** Edmonds' blossom-shrinking algorithm, native Rust port. `max_weight_matching` and `min_weight_matching` share the same kernel parameterized by sign and the `maxcardinality` flag.
- **Maximal matching.** Greedy with canonical edge enumeration; suitable as a lower-bound approximation.
- **Bipartite matching helpers (`hopcroft_karp_matching`, `eppstein_matching`, `minimum_weight_full_matching`).** Live under `fnx.bipartite.*` and currently delegate to the upstream `networkx.algorithms.bipartite` reference. Tracked in `docs/delegation_ledger.md`.

### Flow

- **Maximum flow.** Edmonds-Karp on the residual graph; the BFS traverses *only* residual neighbors (not the full node set; that bug-fix landed early in the project and is locked by tests).
- **Stoer-Wagner.** Native O(V·E + V²·log V) global min-cut.
- **Gomory-Hu tree.** Native; rejects MultiGraph input with a typed `NetworkXError` matching nx.
- **Min-cost flow.** Successive-shortest-path + Bellman-Ford for negative-edge support; delegates to nx for undirected input (`NetworkXNotImplemented`).

### Trees and arborescences

- **MST.** Kruskal's with union-find; `partition_spanning_tree` / `random_spanning_tree` / `number_of_spanning_trees` are exposed.
- **Edmonds' branching.** Native rewrite (commit [`9edb5819`](https://github.com/Dicklesworthstone/franken_networkx/commit/9edb5819)) using explicit `EdmondsMultiDiGraph` + `UnionFind` structures; deterministic edge sort.
- **SpanningTreeIterator / ArborescenceIterator.** Janssens-Sörensen partition scheme for lazy enumeration of all minimum spanning trees / arborescences; the partition logic is module-level and reusable.

### Community

The `fnx.community` submodule mirrors `nx.algorithms.community`. Most algorithms currently route through nx after parity-converting the graph (the `_networkx_graph_for_parity` adapter); the native rewrites are landing one by one.

- **Louvain (`louvain_communities`).** Currently routes through `nx.algorithms.community.louvain_communities` against a converted graph. Bead `br-r37-c1-louvainsubmod` documents the conversion path; nx's multi-level Louvain produces wrong partitions against a raw fnx graph. Native Rust port is planned.
- **Label propagation (`label_propagation_communities`).** Same routing today (bead `br-r37-c1-cy2me`). Earlier had a native fast path that was retired pending a parity fix.
- **Greedy modularity, k-clique communities, Girvan-Newman, asyn_fluidc, Kernighan-Lin bisection.** Mixed: some native, some delegated. Check `docs/delegation_ledger.md` for the canonical state of each.
- **`community.modularity`.** Computed natively against fnx adjacency.

### Isomorphism

- **VF2 / VF2++.** Native no-label VF2++ implementation. With node/edge label callbacks, the algorithm falls back to NetworkX's reference matcher to honor the user-provided callable contract.
- **`could_be_isomorphic` / `fast_could_be_isomorphic` / `faster_could_be_isomorphic`.** Quick degree/clustering invariant checks before invoking the full matcher.

### Planarity

- **`is_planar` / `check_planarity`.** Wrapper-patched today: a necessary-only Kuratowski-bound check in Rust (degree + edge-count + bipartite + girth bounds) short-circuits the easy YES/NO answers, then delegates the residual to NetworkX for the full Boyer-Myrvold check. A native Hopcroft-Tarjan port is on the roadmap.

### DAG

- **Topological sort.** Kahn's algorithm with `LexMin` tie-break for the no-predecessor frontier; matches nx's `_topological_sort` exactly including order ties.
- **Transitive closure.** O(V·(V+E)) DFS-based, preserves node + edge attributes on the DAG fast path (regression `br-r37-c1-gtkxs`).
- **Dominators.** Cooper-Harvey-Kennedy iterative algorithm: reverse-postorder DFS followed by intersect-by-walking-up until fixpoint. `immediate_dominators` + `dominance_frontiers`.

### Polynomial / spectral

- **Tutte polynomial / chromatic polynomial.** Native straight-line deletion-contraction recursion (exponential time, no memoization; intentional, matching NetworkX's reference behavior on small graphs).
- **Spectral helpers.** `laplacian_spectrum`, `adjacency_spectrum`, `modularity_spectrum`, `fiedler_vector`, `algebraic_connectivity`; built on `scipy.linalg.eigh` / `scipy.sparse.linalg.eigsh`. Solver-method validation (`fiedler_method`) is enforced (`br-r37-c1-pvge4`).

### Generators

- **Random generators (BA, WS, GNP, GNM, fast_GNP).** Deterministic seeded RNG; edge enumeration order matches NetworkX byte-for-byte where contracted (`waxman_graph` is locked byte-for-byte; `erdos_renyi_graph` seed parity is locked).
- **Stochastic block model.** Native; preserves user-supplied `nodelist` order.
- **Random tree (Prüfer).** Native O(n) Prüfer-sequence sampling.
- **Navigable small world.** Native Kleinberg implementation.
- **Lattice generators.** Native Rust `hypercube_graph`; pure-Python `grid_graph`, `hexagonal_lattice_graph`, `triangular_lattice_graph` (compose into native primitives but stay at the Python layer since the cost is dominated by the construction loop, not by per-edge insertion).

---

## Internals Walkthrough

A guided tour of the moving parts in a single algorithm execution. Useful for new contributors and for anyone debugging an edge case.

### Step 1: Python wrapper entry

Every public algorithm name in `franken_networkx.*` resolves through the package's `__getattr__` or its 1.4 MB `__init__.py`. A typical wrapper does these things in order:

1. **Argument validation.** Check that the graph is a supported type, that node arguments exist, that weight strings are hashable. Errors raised here use the same class and message as `nx`.
2. **Boundary coercion.** If the user passed an `nx.Graph`, convert it via `_networkx_graph_for_parity` (which uses `_topo_emit_edges_by_adj` to preserve adjacency order).
3. **Argument-shape dispatch.** For ~143 functions, check whether the call shape is one the native fast path handles. If not, route through `_call_networkx_for_parity` or `_call_networkx_submodule_for_parity` and return nx's answer.
4. **GIL-releasing call into the Rust kernel** via `franken_networkx._fnx.<bound_name>`.
5. **Post-processing**, if the function is one of the 25 wrapper-patched ones.

### Step 2: PyO3 binding (`crates/fnx-python/src/algorithms.rs`)

The cdylib re-exports algorithm functions as `#[pyfunction]`s. The actual `pagerank` binding (simplified; the real one also accepts `personalization`, `nstart`, `dangling` and forwards them to the native kernel):

```rust
#[pyfunction]
#[pyo3(signature = (g, alpha=0.85, max_iter=100, tol=1.0e-6, weight="weight"))]
pub fn pagerank(
    py: Python<'_>,
    g: &Bound<'_, PyAny>,            // accepts a fnx graph or an nx graph
    alpha: f64,
    max_iter: isize,
    tol: f64,
    weight: Option<&str>,
) -> PyResult<Py<PyDict>> {
    let graph: PyRef<'_, PyGraph> = g.downcast::<PyGraph>()?.borrow();
    let result: HashMap<String, f64> = py.allow_threads(|| {     // ← GIL released
        fnx_algorithms::pagerank(&graph.inner, alpha, max_iter as usize, tol, weight)
    });
    let dict = PyDict::new(py);                                  // ← GIL reacquired
    for (node, score) in result {
        dict.set_item(node, score)?;
    }
    Ok(dict.into())
}
```

GIL release is critical: without it, concurrent Python threads calling fnx algorithms would serialize on the interpreter lock. With it, each call holds only its own Rust adjacency borrow for the duration.

### Step 3: Native algorithm (`crates/fnx-algorithms/src/lib.rs`)

The Rust kernel:

1. Calls `cgse_begin(CgseReferenceAlgorithm::PageRank)` to create a `WitnessSink`.
2. Builds dense `Vec<u32>` node-index working data from the `IndexMap`-keyed adjacency.
3. Runs the algorithm body using indices for inner loops.
4. Calls `cgse_record_decision(...)` at every tie-break point.
5. Calls `cgse_publish(...)` at the end to finalize the witness and push it into the thread-local `WitnessLedger`.
6. Returns the result as `HashMap<String, f64>` (or whatever the algorithm's natural return type is).

### Step 4: Result marshaling

PyO3 walks the returned Rust collection and constructs the corresponding Python container. For a `HashMap<String, f64>` returning a `PyDict`, this is N hash insertions; for a `Vec<HashSet<String>>` returning a list of `PySet`, this is one nested walk.

### Step 5: Witness ledger drain (optional)

If the conformance harness or a Rust integration test wrapped the call in `collect_witnesses(...)`, the `WitnessLedger` is drained at scope exit and the per-call `ComplexityWitness`es are returned to the caller. From normal Python use, the witnesses are emitted into the thread-local ledger but typically not collected: they're available if you want them and don't cost anything if you don't.

### Anatomy of `PyGraph`

The Python-visible `franken_networkx.Graph` is implemented as a PyO3 `#[pyclass]` named `PyGraph` whose state has *two* tiers:

```rust
#[pyclass(module = "franken_networkx", name = "Graph", dict, weakref, subclass)]
pub(crate) struct PyGraph {
    pub(crate) inner: Graph,                                  // the Rust adjacency map
    pub(crate) node_key_map: HashMap<String, PyObject>,        // canonical key → original Py object
    pub(crate) node_py_attrs: HashMap<String, Py<PyDict>>,     // per-node Python attr dict
    pub(crate) edge_py_attrs: HashMap<(String, String), Py<PyDict>>,  // per-edge Python attr dict
    pub(crate) graph_attrs: Py<PyDict>,                        // graph-level attr dict
}
```

The two-tier design is deliberate:

- **`inner: Graph`**: the canonical adjacency the Rust algorithm kernels iterate. Attribute values inside `inner` use `CgseValue` (serde-typed), which is the form algorithms want and which serializers can round-trip without information loss.
- **`node_py_attrs` / `edge_py_attrs` / `graph_attrs`**: *real* Python `PyDict`s that the Python-visible `G.nodes[u]`, `G.edges[u, v]`, and `G.graph` views point to. Mutations like `G[u][v]["weight"] = 2.0` land here first because the user expects standard dict semantics (live views, identity, subclass support).
- **`node_key_map`**: preserves the original Python object that became the canonical string key, so iteration returns the same Python object the user passed in (`G.add_node(("a", "b"))` then `list(G.nodes())[0]` returns the *same tuple instance*, not a re-constructed one).

The `_sync_rust_edge_attrs(G)` helper bridges the two: when an algorithm needs current edge attributes, it copies the Python-side dict into `inner` in `CgseValue` form first. This is why a `G[u][v]["weight"] = 2.0` mutation is immediately visible to downstream weighted algorithms, at the cost of a sync pass scoped to the algorithm call.

---

## Working With Attributes

NetworkX's killer feature is arbitrary edge / node / graph attributes. fnx preserves that contract exactly. A few patterns worth knowing.

### Setting attributes at construction time

```python
import franken_networkx as fnx

G = fnx.Graph()
G.add_node("alice", role="engineer", since=2020)
G.add_node("bob",   role="manager",  since=2018)
G.add_edge("alice", "bob", weight=3.0, since=2022, project="franken_networkx")

print(G.nodes["alice"])
# {'role': 'engineer', 'since': 2020}
print(G.edges["alice", "bob"])
# {'weight': 3.0, 'since': 2022, 'project': 'franken_networkx'}
```

### Bulk attribute updates

```python
# Bulk-set node attributes from a dict.
fnx.set_node_attributes(G, {"alice": "Engineering", "bob": "Management"}, "team")

# Bulk-set edge attributes.
fnx.set_edge_attributes(G, {("alice", "bob"): {"status": "active"}})

print(G.nodes["alice"]["team"])     # → "Engineering"
print(G.edges["alice", "bob"])
# {'weight': 3.0, 'since': 2022, 'project': 'franken_networkx', 'status': 'active'}
```

`set_node_attributes` and `set_edge_attributes` are mutation-preserving dispatchables: when called via the NetworkX backend they route into fnx and the mutation lands on the *original* graph.

### Reading edge attributes in algorithms

The `weight=` kwarg on weighted algorithms is the attribute name to read:

```python
fnx.shortest_path(G, "a", "z", weight="cost")     # use the "cost" attribute
fnx.shortest_path(G, "a", "z", weight="weight")   # default
fnx.shortest_path(G, "a", "z", weight=None)       # ignore weights → BFS
fnx.shortest_path(G, "a", "z", weight=lambda u,v,d: d.get("cost", 1) + d.get("toll", 0))
# ↑ callable form: fnx accepts it but may delegate to nx depending on the algorithm
#   (see docs/delegation_ledger.md for the per-algorithm contract)
```

### Reading attributes from algorithm output

Many algorithms return the original graph's attributes as part of their output. The `SubgraphView` returned by `G.subgraph([...])` shares the underlying attribute store, so mutations propagate. Use `G.subgraph([...]).copy()` to take a snapshot.

### Attribute mutation outside an algorithm call

```python
G.edges["alice", "bob"]["weight"] = 5.0  # direct mutation
# ↑ updates the Python-side attribute dict. The next *weighted* algorithm
#   call (one that reads "weight" or another attribute) invokes
#   _sync_rust_edge_attrs(G) under the hood to push the new value down
#   into the Rust adjacency before running.
```

The sync helper only runs ahead of algorithms that *read* edge attributes (`dijkstra`, `bellman_ford`, weighted matching, and so on), not before every dispatch. If you're profiling an attribute-heavy hot loop and want to amortize the sync cost, the canonical pattern is to batch mutations through `set_edge_attributes(G, {...})` (one sync at the end of the batch) rather than per-mutation `G[u][v][k] = v`.

### Attribute serialization

Attributes survive a round-trip through every native I/O format:

```python
fnx.write_graphml(G, "g.xml")     # types preserved via <data attr.type=...>
fnx.write_gml(G,     "g.gml")     # typed scalars
fnx.write_gexf(G,    "g.gexf")    # typed attributes
data = fnx.node_link_data(G)      # JSON with type tags
```

The GraphML / GML / GEXF writers all emit typed attribute markers (`long`, `double`, `string`, `boolean`) so type identity survives. JSON node-link uses Python's standard `json` library type mapping.

---

## Cookbook

### Large-graph PageRank

```python
import franken_networkx as fnx

# Build (or load) a 1M-node BA graph.
G = fnx.barabasi_albert_graph(1_000_000, 4, seed=42)

# fnx.pagerank releases the GIL, so this is fine to run from a thread pool.
pr = fnx.pagerank(G, alpha=0.85, max_iter=100, tol=1e-6)

top10 = sorted(pr.items(), key=lambda kv: kv[1], reverse=True)[:10]
```

### Community detection

```python
import franken_networkx as fnx

G = fnx.karate_club_graph()
comms = list(fnx.community.louvain_communities(G, seed=42))
print("#communities:", len(comms))
print("modularity:", fnx.community.modularity(G, comms))
```

### Mixing fnx + nx graph types at the boundary

Every fnx function accepts an `nx.Graph` (or fnx graph) interchangeably; the boundary coerces:

```python
import networkx as nx, franken_networkx as fnx

G_nx  = nx.path_graph(10)
G_fnx = fnx.path_graph(10)

# all four combinations work and return the same answer
fnx.shortest_path(G_nx,  0, 9)
fnx.shortest_path(G_fnx, 0, 9)
nx.shortest_path(G_nx,  0, 9, backend="franken_networkx")
nx.shortest_path(G_fnx, 0, 9, backend="franken_networkx")
```

### Format conversion in one line

```python
import franken_networkx as fnx

G = fnx.read_gml("input.gml")
fnx.write_graphml(G, "output.xml")
fnx.write_edgelist(G, "output.edgelist")
fnx.write_gexf(G, "output.gexf")
```

### Drawing (delegated to matplotlib via NetworkX)

```python
import franken_networkx as fnx
import matplotlib.pyplot as plt

G = fnx.karate_club_graph()
pos = fnx.spring_layout(G, seed=7)
fnx.draw(G, pos, with_labels=True, node_size=200)
plt.savefig("karate.png", dpi=160)
```

### Inspecting CGSE policy + witness types from Python

```python
import franken_networkx as fnx
from franken_networkx._fnx import cgse

# The 12 tie-break policies are reachable as named constructors:
p = cgse.TieBreakPolicy.weight_then_lex()
print(p.id())                       # "weight_then_lex"

# Per-algorithm canonical policy. Only the 12 reference algorithms have
# entries; unknown algorithms return None.
print(cgse.algorithm_policy("dijkstra"))             # → TieBreakPolicy.weight_then_lex
print(cgse.algorithm_policy("max_weight_matching")) # → TieBreakPolicy.weight_then_lex
print(cgse.algorithm_policy("pagerank"))             # → None (not in the V1 reference set)

# Full V1 registry: { "<algorithm>": {"family": ..., "policy": ..., "dominant_complexity": ...} }
registry = cgse.policy_registry()
print(len(registry), "registered algorithms")        # → 12
print(sorted(registry.keys())[:5])                   # → ['bellman_ford', 'bfs', 'connected_components', 'dfs', 'dijkstra']

# All reference-algorithm identifiers:
print(cgse.reference_algorithms())
# → ['dijkstra', 'bellman_ford', 'bfs', 'dfs', 'max_weight_matching', 'min_weight_matching',
#    'connected_components', 'strongly_connected_components', 'kruskal', 'prim',
#    'eulerian_circuit', 'topological_sort']
```

Programmatic CGSE-witness collection is exposed at the Rust level via `fnx_cgse::collect_witnesses` and the `WitnessLedger` JSONL serializer; the Python surface today is read-only (policy inspection). To collect witnesses end-to-end, drive an algorithm from a Rust integration test or read the JSONL artifacts emitted by the conformance harness under `artifacts/conformance/latest/`.

---

## When to Use FrankenNetworkX (and When Not To)

**Use it when:**

- You have an existing NetworkX codebase and the per-call cost dominates wall-clock time. Set `nx.config.backend_priority = ["franken_networkx"]` and you're done.
- You want determinism *and* speed. The CGSE tie-break contract means rerunning the same analysis on the same graph gives byte-identical output across runs and across machines.
- You're shipping graph analytics as part of a long-lived pipeline where iteration-order drift would be a quiet correctness bug downstream.
- You're doing research on graph algorithms and want a reproducibility audit trail per algorithm execution (the `ComplexityWitness` ledger).
- You're parsing graphs from untrusted sources and want strict-vs-hardened ingestion semantics, not "best-effort don't crash."

**Don't use it when:**

- You're working with graphs that fit comfortably in pure-Python NetworkX (< 10⁴ nodes, single-shot analysis) and you'd rather not add a Rust dependency. NetworkX is excellent at that scale.
- You need GPU acceleration. Look at cugraph / pylibraft.
- You need a different API entirely (igraph's vertex-index model, graph-tool's property-map model) and aren't tied to NetworkX semantics.
- You're targeting a Python runtime older than 3.10. ABI3-py310 means 3.10 is the floor.
- You need exotic backends (Neo4j, distributed graphs across machines). This is an in-memory graph algorithms library.

---

## Advanced Topics

### Backend dispatch from an `nx.Graph` you can't easily convert

If you're working in a third-party library that hands you `nx.Graph` instances, the easiest path is:

```python
import networkx as nx

# Either: globally
nx.config.backend_priority = ["franken_networkx"]

# Or: with a context manager (NetworkX ≥ 3.4)
with nx.config(backend_priority=["franken_networkx"]):
    pr = nx.pagerank(third_party_graph)
```

The backend dispatcher converts the nx graph at the dispatch boundary; the original graph is unchanged.

### Converting an fnx graph to an nx graph

Three options, in increasing fidelity:

```python
import franken_networkx as fnx
import networkx as nx

G = fnx.path_graph(5)

# Quickest: identity-of-shape via edgelist.
nx_view  = nx.Graph(list(G.edges()))

# Full attribute round-trip via node-link JSON.
data     = fnx.node_link_data(G)
nx_full  = nx.node_link_graph(data)

# Topology-preserving via adjacency walk (used internally by the backend
# convert_to_nx path; respects insertion order).
from franken_networkx.readwrite import _from_nx_graph  # private helper for parity
```

For most users, the second option is what you want: it preserves graph-level, node-level, and edge-level attributes.

### Witness ledger artifacts

The conformance harness writes one `*.report.json` per fixture family into `artifacts/conformance/latest/`. Each report carries `{schema_version, fixture_id, fnx_commit, nx_version, status, mismatches[], duration_ms, witness_hash}` and a RaptorQ sidecar (`*.raptorq.json`) plus a decode-proof receipt (`*.recovered.json`). The witness ledger itself is in `structured_logs.jsonl`, one line per algorithm call, drainable as JSON.

### RuntimePolicy at the Rust layer

`RuntimePolicy` lives in `fnx-runtime` and bundles the compatibility mode, an allowlist of safe operations, a Bayesian admission posterior, a loss-matrix for decision-theoretic action selection, and an append-only `EvidenceLedger`. It is *not* a global; it is constructed per call so behavior is reproducible from the decision log alone:

```rust
use fnx_runtime::{RuntimePolicy, CompatibilityMode, DecisionAction, EvidenceTerm};

let mut policy = RuntimePolicy::hardened();
assert_eq!(policy.mode(), CompatibilityMode::Hardened);
assert!(policy.allows("bounded_diagnostic_enrichment"));

// Algorithms / parsers can record decisions into the policy's evidence ledger:
policy.record(
    "read_graphml",                       // operation
    DecisionAction::FullValidate,         // action selected
    0.7,                                  // incompatibility probability
    "parser warning observed",            // rationale
    vec![                                 // evidence terms (signal/value/llr)
        EvidenceTerm {
            signal: "warning_count".into(),
            observed_value: "1".into(),
            log_likelihood_ratio: 0.3,
        },
    ],
);

for record in policy.decision_log().records() {
    println!("{:?}", record);
}
```

The threading of `RuntimePolicy` through parser and high-risk algorithm entry points is in progress (roadmap beads D2–D4). At the Python layer today, the default `Strict` mode is in effect; an explicit Python toggle is part of the same D2–D4 milestone.

### Thread safety

Algorithm calls release the GIL during their inner loops, with the following consequences:

- Concurrent reads of the same graph from multiple Python threads are safe (each one borrows the underlying Rust adjacency by reference).
- Concurrent writes are *not* safe. `Graph` mutation is `&mut self` in Rust; Python-side, the mutation paths take a write borrow internally, and `_sync_rust_edge_attrs` tolerates concurrent borrow with bounded retry, but neither is a substitute for application-level synchronization on a shared graph.
- The `tests/python/test_thread_safety.py` suite exercises the concurrent-read contract specifically; concurrent Dijkstra calls from a thread pool over a shared graph is the canonical pattern.

---

## Examples

| File | What it shows |
|---|---|
| [`examples/basic_usage.py`](examples/basic_usage.py) | Standalone graph construction, algorithms, and round-trips. |
| [`examples/backend_mode.py`](examples/backend_mode.py) | NetworkX backend dispatch with zero call-site changes. |
| [`examples/social_network.py`](examples/social_network.py) | Community detection and centrality on a small social graph. |
| [`examples/benchmark_comparison.py`](examples/benchmark_comparison.py) | Lightweight local comparison vs NetworkX. |

---

## Documentation

| Page | Audience |
|---|---|
| [docs/quickstart.md](docs/quickstart.md) | First-time users; standalone usage |
| [docs/backend.md](docs/backend.md) | Existing NetworkX users; backend dispatch |
| [docs/migration.md](docs/migration.md) | Side-by-side NetworkX → FrankenNetworkX patterns |
| [docs/algorithms.md](docs/algorithms.md) | Algorithm reference summary |
| [docs/performance.md](docs/performance.md) | Performance notes and benchmarking |
| [docs/coverage.md](docs/coverage.md) | Auto-generated public-API inventory (763 entries) |
| [docs/raw_vs_public_audit.md](docs/raw_vs_public_audit.md) | Wrapper-patched parity repairs |
| [docs/delegation_ledger.md](docs/delegation_ledger.md) | All parity-helper delegation routes |
| [docs/upstream_divergence_ledger.md](docs/upstream_divergence_ledger.md) | Native-parity / wrapper-patched / delegated / gap rows |
| [docs/api_ergonomics_audit.md](docs/api_ergonomics_audit.md) | Signature-drift report |
| [docs/contributing.md](docs/contributing.md) | Development setup |
| [AGENTS.md](AGENTS.md) | Guide for AI coding agents working in this repo |
| [COMPREHENSIVE_SPEC_FOR_FRANKENNETWORKX_V1.md](COMPREHENSIVE_SPEC_FOR_FRANKENNETWORKX_V1.md) | V1 specification |
| [FEATURE_PARITY.md](FEATURE_PARITY.md) | Family-by-family parity inventory |

---

## Development

```bash
# clone
git clone https://github.com/Dicklesworthstone/franken_networkx
cd franken_networkx

# install build deps
pip install maturin pytest hypothesis networkx numpy scipy

# dev loop: debug build, edit, repeat
maturin develop --features pyo3/abi3-py310

# release build (recommended for benchmarks)
maturin develop --release --features pyo3/abi3-py310

# run tests
pytest tests/python/ -v --tb=long

# verify docs
python3 scripts/verify_docs.py

# build a wheel
maturin build --release

# Rust-side checks
cargo fmt --check
cargo clippy --workspace --all-targets -- -D warnings
cargo test --workspace
```

ABI3 builds a single wheel that works on Python 3.10, 3.11, 3.12, and 3.13; no per-version matrix is needed.

### Building from source on a fresh machine

```bash
# Rust toolchain (nightly, pinned by rust-toolchain.toml)
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
. "$HOME/.cargo/env"
rustup component add rustfmt clippy

# Python build deps
python3 -m venv .venv && source .venv/bin/activate
pip install --upgrade pip
pip install maturin pytest hypothesis networkx numpy scipy

# Clone + build
git clone https://github.com/Dicklesworthstone/franken_networkx
cd franken_networkx
maturin develop --release --features pyo3/abi3-py310

# Smoke test
python -c "import franken_networkx as fnx; G = fnx.path_graph(5); print(fnx.shortest_path(G, 0, 4))"
```

Cold build time on a modern laptop (16-core, 32 GB): about 4 minutes for a release build. Incremental builds run in seconds for most edits.

### Cross-compilation notes

ABI3 wheels published to PyPI are built in CI on three runners (Ubuntu, macOS, Windows). For local cross-compilation, `maturin build --release --target=...` works if you have the corresponding Rust target installed (`rustup target add ...`). The cdylib doesn't have any platform-specific code paths today.

### Editor / IDE setup

The project ships a `rust-toolchain.toml` so `rust-analyzer` and `rustfmt` honor the pinned nightly. For VS Code, install:

- `rust-lang.rust-analyzer`
- `tamasfe.even-better-toml`
- `vadimcn.vscode-lldb` for debugging

For Python, `pylance` or `pyright` will pick up the type stubs from `python/franken_networkx/_fnx.pyi` automatically.

---

## Troubleshooting

Top issues and their fixes.

### `ImportError: cannot import name '_fnx' from 'franken_networkx'`

The cdylib didn't build or didn't get installed. Cause and fix:

- **You installed from source but the build silently failed.** Re-run `maturin develop --release --features pyo3/abi3-py310` and read the full output.
- **A stale wheel from a previous build is shadowing the new one.** `pip uninstall franken-networkx && pip install franken-networkx`.
- **You're on Python < 3.10.** ABI3-py310 means 3.10 is the floor; upgrade Python.

### Backend isn't dispatching: `nx.shortest_path` still slow

```python
import networkx as nx
nx.config.backend_priority = ["franken_networkx"]
# Now call nx.shortest_path(G, ...)
```

If still slow, check:

```python
import franken_networkx
print(franken_networkx.__version__)        # should print "0.1.0" or later

import networkx as nx
print(nx.config.backend_priority)          # should contain "franken_networkx"

# Did NetworkX actually pick up the entry point?
import importlib.metadata as im
print([e.name for e in im.entry_points(group="networkx.backends")])
# → should include "franken_networkx"
```

If the entry point isn't visible, your install is broken. Reinstall.

### `NotImplementedError: BackendInterface has no attribute '<name>'`

The algorithm isn't in `_SUPPORTED_ALGORITHMS` and you passed `backend="franken_networkx"` explicitly (the per-call form raises rather than falling back). Fix: drop the explicit kwarg and rely on `backend_priority`-based fallback, or call `fnx.<name>` directly.

### A result that doesn't match NetworkX

Reproduce both sides:

```python
import networkx as nx, franken_networkx as fnx
G_nx  = nx.path_graph(10)
G_fnx = fnx.path_graph(10)
print(nx.shortest_path(G_nx, 0, 9))
print(fnx.shortest_path(G_fnx, 0, 9))
```

If they differ and the difference isn't in `docs/upstream_divergence_ledger.md`, it's a bug. Please open an issue with `franken_networkx.__version__` and `networkx.__version__`.

### `RuntimeError: dictionary changed size during iteration`

You mutated a graph while iterating it. `fnx` matches NetworkX's behavior exactly here: iteration views are live, and mutating during iteration raises. Use `list(G.nodes())` to snapshot.

### "Stale wheel" detected during pytest

The conformance test layer detects a previously-installed fnx wheel with a mismatched API surface and skips backend-dispatch tests rather than report spurious failures (`br-r37-c1-...` cycle, see `tests/python/test_backend_dispatch_recursion_parity.py`). Fix: rebuild with `maturin develop --release`.

### Performance is worse than NetworkX for tiny graphs (< 50 nodes)

Expected. The dispatch + PyO3 marshaling cost dominates for graphs that small. Use NetworkX directly, or just accept the constant overhead. fnx wins at scale, not on micro-benchmarks.

### Multiprocessing crashes with `_fnx` segfaults

PyO3 extension modules need to be re-imported in each spawned process. Use `multiprocessing.set_start_method("spawn")` (not `fork`) on macOS and most modern Linux setups.

---

## Environment Variables

Standard Rust / Python build-time and runtime variables that are useful when working with FrankenNetworkX:

| Variable | Effect |
|---|---|
| `RUST_LOG=fnx=info` | Enables `tracing` output from the workspace. `debug` for verbose; `trace` for everything including per-call diagnostics. Applied at process start; honored by anyone subscribing via `tracing-subscriber`. |
| `CARGO_TARGET_DIR=...` | Standard cargo override; useful for sharing the target directory between local and CI builds. Speeds up incremental rebuilds dramatically when building from source repeatedly. |
| `RUSTFLAGS="-C target-cpu=native"` | Build a wheel tuned for the current CPU. Meaningful for the `numpy`/`scipy`-adjacent paths and any SIMD-friendly inner loop. Don't use for distributable wheels. |
| `PYO3_PYTHON=/path/to/python` | Build against a specific Python interpreter. Useful for multi-venv setups. |
| `MATURIN_PEP517_ARGS=--release --features pyo3/abi3-py310` | Force a release build when `pip install` from source. |

FrankenNetworkX itself does not introduce custom `FNX_*` environment variables today. Runtime behavior is configured per call (via the `RuntimePolicy` builder shown earlier) rather than via process-wide flags. This is intentional: per-call construction means behavior is reproducible from the decision log alone.

---

## Reproducibility Recipe

Bit-for-bit reproducible graph analytics with fnx. The recipe below is usable as the spine of a regression-locked pipeline.

### 1. Pin the inputs

```python
import os, hashlib, franken_networkx as fnx

GRAPH_INPUT = "datasets/snapshot_2026Q2.edgelist"

# Compute and log the SHA-256 of the input. Any drift here is the first
# place to look if reproducibility breaks downstream.
with open(GRAPH_INPUT, "rb") as f:
    digest = hashlib.sha256(f.read()).hexdigest()
print(f"input sha256: {digest}")
```

### 2. Pin the build

```python
import franken_networkx, networkx, sys
print("fnx:    ", franken_networkx.__version__)
print("nx:     ", networkx.__version__)
print("python: ", sys.version.split()[0])

# Optionally also pin the Rust commit the wheel was built from. If
# you're using a release wheel, the version is the contract; if you're
# building from source, capture `git rev-parse HEAD` in CI.
```

### 3. Pin the runtime mode

```python
# Default is Strict. For ingest of trusted data this is what you want.
# For ingest from a hostile source you may want Hardened; but pick
# one mode per pipeline run and log it.
print("compat mode: Strict (default)")
```

### 4. Run the analysis

```python
G = fnx.read_edgelist(GRAPH_INPUT, create_using=fnx.Graph)
pr = fnx.pagerank(G, alpha=0.85, max_iter=100, tol=1e-6)
```

The default CGSE `WeightThenLex` tie-break + `IndexMap` adjacency means: on the same input + same fnx version + same seed for any randomized stage, you get byte-identical PageRank values across machines. There is no "but on my Mac it returns 0.299 instead of 0.300"; that doesn't happen in CGSE-pinned algorithms.

### 5. Hash the output

```python
import json
canonical = json.dumps(sorted(pr.items()), sort_keys=True)
out_digest = hashlib.sha256(canonical.encode()).hexdigest()
print(f"output sha256: {out_digest}")

# Lock this digest in a regression test. If it ever changes without a
# version bump, that's a bug in fnx or in your input pipeline.
```

### 6. Optional: harvest the CGSE witness

For Rust-side audit, drain `WitnessLedger` and serialize as JSONL. The hash of the witness JSONL bundle is a stronger reproducibility receipt than the algorithm output alone: two runs that produce the same algorithm output but different witness hashes are *suspicious* (it usually means the algorithm took a different path through equally-correct choices, indicating a non-determinism leak).

This recipe is what powers the project's own conformance gate (G5) and performance SLO gate (G6).

---

## Migration From NetworkX: Patterns

A reference catalog of common NetworkX patterns and their fnx equivalents. The migration is almost always trivial; the patterns below cover the edge cases that aren't.

### Pattern: `import networkx as nx` → no change (backend mode)

```python
# Before
import networkx as nx
G = nx.karate_club_graph()
print(nx.shortest_path(G, 0, 33))

# After (just enable the backend at startup)
import networkx as nx
nx.config.backend_priority = ["franken_networkx"]   # ← one line
G = nx.karate_club_graph()
print(nx.shortest_path(G, 0, 33))
```

### Pattern: `import networkx as nx` → `import franken_networkx as nx` (standalone mode)

```python
# Before
import networkx as nx

# After: drop-in alias, NetworkX still importable for exception classes
import franken_networkx as nx
```

This works for the algorithm surface fnx natively implements; for the rest, the fnx wrapper delegates to NetworkX internally so behavior is identical.

### Pattern: type checks on `nx.Graph`

```python
# Before
if isinstance(g, nx.Graph): ...

# After: fnx graphs are NOT subclasses of nx.Graph; use duck typing or
# the __networkx_backend__ attribute fnx graphs carry.
if hasattr(g, "__networkx_backend__") or isinstance(g, nx.Graph):
    ...
# Or convert at the boundary:
if not isinstance(g, nx.Graph):
    g = nx.Graph(g.edges(data=True))   # or use fnx.node_link helpers
```

### Pattern: pickling

```python
# Before
import pickle
pickle.dumps(nx.path_graph(5))   # works

# After
import pickle, franken_networkx as fnx
pickle.dumps(fnx.path_graph(5))  # also works; fnx graphs are pickleable
```

### Pattern: subclassing `nx.Graph`

```python
# Before
class MyGraph(nx.Graph):
    def my_method(self): ...

# After: fnx.Graph is a PyO3 #[pyclass(subclass)] so Python subclassing
# works, but you can't override Rust-side methods. Override at the
# Python wrapper layer (the public algorithm surface).
class MyGraph(fnx.Graph):
    def my_method(self): ...
```

### Pattern: NetworkX-only algorithms via fallback

```python
# Before: calling an algorithm fnx doesn't natively support
import networkx as nx
nx.config.backend_priority = ["franken_networkx"]
# nx will fall through to its own implementation for unsupported algorithms
result = nx.some_obscure_algorithm(G)   # → pure-Python nx
```

If you want to *force* the nx implementation for a single call (e.g., for an A/B comparison), drop the `backend=` kwarg or override `backend_priority` temporarily with `nx.config(backend_priority=[]):` context manager.

### Pattern: existing test suites

Run your existing nx-based test suite against fnx by setting the backend priority in `conftest.py`:

```python
# tests/conftest.py
import networkx as nx
import franken_networkx  # ensure the entry point registers
nx.config.backend_priority = ["franken_networkx"]
```

If any test fails after the change, you've found either a fnx bug worth reporting or an instance of `docs/upstream_divergence_ledger.md` your code was relying on.

---

## Production Deployment Notes

A practical checklist for shipping fnx in production.

### Dependency pinning

```toml
# requirements.txt or pyproject.toml [tool.poetry.dependencies]
franken-networkx = "==0.1.0"
networkx = ">=3.0,<4.0"
```

Pin fnx exactly during early development (0.1.x). The fnx parity guarantee includes "we won't change observable behavior of a supported algorithm without a version bump", and pinning gives you that guarantee in your dependency graph.

### Wheel selection

PyPI ships pre-built ABI3 wheels for:

- Linux x86_64 (manylinux_2_28)
- Linux aarch64
- macOS x86_64 (10.12+)
- macOS arm64 (11.0+)
- Windows x86_64

If you're on a non-standard platform (musl libc, FreeBSD, embedded Linux variants), you'll need to build from source. The build is cargo-driven so it works anywhere Rust nightly works.

### Memory considerations

The IndexMap-backed adjacency is denser than NetworkX's `dict-of-dicts` per node (typical ratio: 60–70% of nx's memory for the same graph). The `node_key_map` + `node_py_attrs` + `edge_py_attrs` caches add overhead proportional to the number of Python-side attribute accesses you make. For pipelines that never touch attributes, those caches stay nearly empty.

Rough rules of thumb for a graph with `n` nodes + `m` edges + average `a` attributes per node/edge:

- Pure adjacency (no attributes): ~80 bytes per node + ~24 bytes per edge.
- With attributes: + ~120 bytes per attribute (CgseValue tagged union + Python dict bridge).

A 1M-node graph with 4M edges and 2 attributes per edge is roughly 80MB pure adjacency + ~1GB with attribute storage on both sides.

### Multiprocessing

The `_fnx` cdylib is safe to import from multiple Python processes. Standard caveats apply:

- Use `multiprocessing.set_start_method("spawn")` on macOS (default since 3.8) and modern Linux.
- Graphs do not share memory across processes; serialize via `pickle`, JSON node-link, or write to a file.
- Each process initializes its own thread-local CGSE witness ledger.

### Async / threading

- fnx algorithm calls release the GIL during native execution. Using a `ThreadPoolExecutor` to run algorithms concurrently on independent graphs is the correct pattern.
- Calls that mutate a *shared* graph from multiple threads are not safe; serialize the mutator from a single thread.
- `asyncio` works trivially; algorithm calls are blocking, so wrap them with `loop.run_in_executor(None, fn, args)`.

### Logging and tracing

```python
import logging
logging.basicConfig(level=logging.INFO)
# The Python wrapper layer logs at INFO when an algorithm is dispatched via the backend.
logging.getLogger("franken_networkx.backend").setLevel(logging.INFO)
```

For Rust-side `tracing` output, set `RUST_LOG=fnx=info` in the process environment before importing fnx.

### Container image notes

If you're shipping fnx inside a Docker image, a minimal layer set:

```dockerfile
FROM python:3.12-slim
RUN pip install --no-cache-dir franken-networkx
# Optional NumPy / SciPy extras
RUN pip install --no-cache-dir 'franken-networkx[all]'
```

The wheels are self-contained; no apt packages needed. Final image cost is ~80 MB beyond the base Python image.

---

## Style Guide for Code That Uses fnx

How to write code that flips cleanly between fnx and nx without surprises.

### Prefer `fnx.X(G)` to `G.X()` where both exist

```python
# Both work, but the module-level form is the documented contract.
fnx.shortest_path(G, "a", "z")        # preferred
G.shortest_path("a", "z")              # not all graph types expose this
```

### Don't rely on private internals

The audit ledgers track the *public* surface. Anything starting with `_` (e.g. `fnx._fnx`, `fnx._sync_rust_edge_attrs`, `fnx.backend._SUPPORTED_ALGORITHMS`) is not part of the contract and may move between releases.

### Catch the broadest reasonable exception

```python
# Brittle (won't catch NetworkXNoPath, since it's under NetworkXUnfeasible)
try:
    path = fnx.shortest_path(G, s, t)
except fnx.NetworkXError:   # ← does NOT catch NetworkXNoPath!
    ...

# Correct
try:
    path = fnx.shortest_path(G, s, t)
except fnx.NetworkXNoPath:
    ...
# Or, if you want a catch-all
except fnx.NetworkXException:
    ...
```

### Use named kwargs for keyword-only parameters

```python
# Good
fnx.shortest_path(G, "a", "z", weight="weight")
fnx.pagerank(G, alpha=0.85, max_iter=100, tol=1e-6)

# Bad: positional args past 2 are fragile, fnx mirrors nx's keyword-only contract
fnx.pagerank(G, 0.85, 100, 1e-6)   # works today, may not tomorrow
```

### Don't iterate views during mutation

Same rule as NetworkX:

```python
# Bad
for u in G.nodes():
    if G.degree(u) == 0:
        G.remove_node(u)        # raises RuntimeError mid-iteration

# Good
isolates = list(fnx.isolates(G))
for u in isolates:
    G.remove_node(u)
```

### Snapshot views before subprocess transfer

`G.subgraph([...])` returns a view, not a fresh graph. If you want to pickle it or pass it across an async boundary, call `.copy()`:

```python
sub = G.subgraph(important_nodes)         # view; aliases G
sub_copy = G.subgraph(important_nodes).copy()  # standalone graph
pickle.dumps(sub_copy)                    # ← this is what you want for IPC
```

---

## Real-World Use Cases

A non-exhaustive list of problems fnx fits well, drawn from the project's design rationale.

### Network security analytics

- **Attack-graph centrality:** PageRank or betweenness over a graph of network hosts + attacker pivots, to identify chokepoints whose hardening cuts the most attack paths.
- **Reachability queries:** `has_path` / `bidirectional_shortest_path` over a permission graph.
- **Anomaly detection:** community-detection drift between two time-windowed snapshots of the same logical graph.

CGSE matters here because the analytics output drives alerting; an iteration-order drift becomes a false-positive flood.

### Knowledge graph and RAG retrieval

- **Entity-relationship traversal:** `bfs_layers` / `descendants_at_distance` over an entity-relation graph for K-hop neighborhood expansion.
- **Salience ranking:** PageRank-style scoring of entities to prioritize what to feed an LLM context window.
- **Schema-aware similarity:** Jaccard / Adamic-Adar over the relation graph for entity linking.

fnx's GIL-released algorithm calls let a server handle multiple concurrent retrieval queries against a shared in-memory graph.

### Bioinformatics and molecular graphs

- **Cycle and clique analysis:** `find_cliques` (Bron-Kerbosch with the native bitset fast path), `k_truss`, `core_number` over protein-interaction networks.
- **Shortest-pathway analysis:** Dijkstra over metabolic networks weighted by reaction enthalpy.
- **Isomorphism:** VF2 / VF2++ for subgraph matching in chemical structure search.

The conformance gate guarantees that an analysis published last year and rerun today produces byte-identical results.

### Recommendation systems and social analytics

- **Link prediction:** `adamic_adar_index`, `preferential_attachment`, `resource_allocation_index` over user-item bipartite graphs.
- **Community detection at scale:** Louvain / greedy modularity over follower graphs (with the caveat that Louvain currently routes through nx).
- **Pagerank-style ranking:** personalized PageRank for content recommendation.

### Compiler and program analysis

- **Dominator computation** (`immediate_dominators`, `dominance_frontiers`) for SSA construction.
- **Loop and natural-region detection** via `simple_cycles` and `strongly_connected_components`.
- **Reachability and constant-propagation** via `transitive_closure` and `topological_sort`.

The CHK iterative dominator algorithm is exactly what production compilers use.

### Workflow and dependency analysis

- **Topological scheduling:** `topological_sort` / `lexicographical_topological_sort` over a DAG of build steps.
- **Critical-path identification:** `dag_longest_path` for project-planning longest-duration chains.
- **Cycle detection in declared dependencies:** `simple_cycles` over a config dependency graph.

### Geographic and routing systems

- **Shortest-path queries** with custom cost functions: `astar_path` with a Haversine heuristic over a road-network graph.
- **Network resilience:** `articulation_points` / `bridges` to identify single-points-of-failure in transit networks.
- **Catchment analysis:** `single_source_shortest_path_length` to compute drive-time isochrones.

### Adversarial graph ingestion

Parsing untrusted graphs (e.g. social-network exports from third-party tools) benefits from the strict-vs-hardened mode toggle and the fuzz-hardened parsers. The 33 cargo-fuzz binaries have collectively run for thousands of CPU-hours in CI without finding a panic. That's the security contract you want before feeding `nx.read_graphml(untrusted_path)` to a public-facing service.

---

## Observability

For long-running pipelines, the witness ledger and decision log are the canonical observability surface:

- **`artifacts/conformance/latest/structured_logs.jsonl`**: one JSON line per algorithm call. Fields include `{algorithm, fixture, n, m, observed_count, duration_ms, witness_hash, mismatch_reason?}`. Drainable by `jq`.
- **`artifacts/perf/latest/perf_baseline_matrix_v1.json`**: p50/p95/p99 + memory for every algorithm family in the SLO matrix.
- **`artifacts/perf/latest/slo_gate_report_v1.json`**: pass/fail status for each SLO row plus the delta from baseline.
- **RaptorQ sidecars (`*.raptorq.json`) and decode receipts (`*.recovered.json`)**: paired with each of the above so artifacts survive partial-corruption events.

For Python-side observability:

```python
import logging
logging.basicConfig(level=logging.INFO)
logging.getLogger("franken_networkx.backend").setLevel(logging.DEBUG)

# Now every backend dispatch decision is logged at DEBUG.
```

For Rust-side `tracing` output, point `RUST_LOG=fnx=info` at any process that loads the cdylib; the spans annotate algorithm entry/exit, GIL-release boundaries, and witness-ledger drains.

---

## Limitations

FrankenNetworkX is honest about what it does not do today:

- **Drawing is delegated.** `draw`, `draw_*`, and the matplotlib-backed layout functions delegate to NetworkX/matplotlib. Layout *math* (`spring_layout`, `kamada_kawai_layout`, etc.) is also delegated. We do not own matplotlib rendering.
- **`is_planar` is wrapper-patched.** The raw Rust kernel is still a necessary-condition test (degree + edge-count bounds, bipartite + girth). The public wrapper short-circuits K3,3 / Petersen / K5 and delegates the residual to NetworkX so the answer is always correct. A native Boyer-Myrvold / Hopcroft-Tarjan port is on the roadmap.
- **143 exports retain a parity-helper branch.** These are not bugs; they are the documented set in `delegation_ledger.md` where unusual argument shapes (callable arguments, exotic format variants, deprecated API forms) defer to NetworkX. The native fast path runs for the common case.
- **No formal releases yet.** Workspace version is `0.1.0`. PyPI status is **Beta**. There are no git tags or GitHub Releases at the time of writing.
- **No Windows/macOS performance SLO yet.** The performance gate (G6) currently runs only on Linux. Correctness gates (G1–G3) cover all three platforms.
- **No 3rd-party graph DB integration.** This is a graph *algorithms* library; it does not connect to Neo4j, JanusGraph, etc. Use it on in-memory graphs.

---

## FAQ

**Is it really a drop-in replacement?**
For the 316 algorithms in `backend.py`'s `_SUPPORTED_ALGORITHMS` registry, yes: output is byte-compatible with NetworkX including iteration order. For the rest, NetworkX itself runs the algorithm (via the standard backend fallback) so nothing breaks. The 377-file parity suite is the canonical truth.

**Why are iteration orders such a big deal?**
NetworkX users often write code that implicitly depends on `dict` insertion order or BFS visit order or `connected_components` set ordering. If a "faster NetworkX" returns the same set of correct answers but in a different order, downstream code breaks subtly. CGSE + the parity tests + the iteration-order audit ledger collectively make iteration order a first-class API contract.

**Do I need a Rust toolchain?**
No. Pre-built wheels are published for Linux, macOS, and Windows. Only contributors building from source need `rustup` and the nightly toolchain pinned in `rust-toolchain.toml`.

**What's the ABI3 story?**
The native extension uses `pyo3/abi3-py310`. One wheel works for Python 3.10, 3.11, 3.12, and 3.13. No per-Python-version build matrix is needed.

**Is it thread-safe?**
Algorithm calls release the GIL at hundreds of call sites and operate on borrowed adjacency. Concurrent reads are safe. Concurrent writes are not. `Graph` mutation is `&mut self` in Rust, and `_sync_rust_edge_attrs` tolerates concurrent borrow with bounded retry but is not a substitute for application-level synchronization on shared graphs. The `tests/python/test_thread_safety.py` suite exercises the concurrent-read contract.

**What's "Strict" vs "Hardened"?**
A runtime mode in `fnx-runtime::CompatibilityMode`. Strict maximizes byte-for-byte NetworkX compatibility on V1-scoped APIs and fails closed on malformed input. Hardened preserves the API contract while applying bounded defensive recovery; useful when ingesting adversarial graphs from untrusted sources. Both modes record every action selection as a `DecisionRecord` in an evidence ledger.

**What's CGSE?**
The **Canonical Graph Semantics Engine**: a Rust crate (`fnx-cgse`) that makes tie-breaking, complexity witnesses, and policy registries first-class. Every algorithm declares (at the type level) which of the 12 `TieBreakPolicy` variants governs its choices; every call emits a length-prefixed-Blake3 `ComplexityWitness` that can be drained from a `WitnessLedger` for offline reproducibility audits.

**Why not just use `networkx[backend=cugraph]` / igraph / graph-tool?**
Use them if they fit. cugraph requires CUDA; igraph and graph-tool have different APIs and don't preserve nx tie-break behavior. The niche FrankenNetworkX fills is "I have an nx codebase, I want it faster, I do not want to think about tie-breaks or rewrite anything."

**Does the backend mode work with `nx.config.backend_priority` *and* explicit `backend="..."` kwargs?**
Yes. The list-form controls the default; the per-call kwarg overrides it. fnx's `BackendInterface.can_run` honors both paths the same way; for unsupported algorithms or unsupported argument shapes, the call falls through.

**What happens to graph mutations made through the backend?**
Mutation-preserving dispatchables (`relabel_nodes`, `contracted_nodes`, `contracted_edge`, `identified_nodes`, `set_node_attributes`, `set_edge_attributes`, `double_edge_swap`, `connected_double_edge_swap`) write the mutation back to the original graph rather than a throwaway copy. This was a coordinated late-cycle effort tracked under beads `br-r37-c1-{pq52x, frbgb, tq78w, l2j31}`.

**How are NaN edge weights handled?**
The Dijkstra / A* / PageRank +∞ gate uses a native Rust nonfinite-weight scan as a fast pre-check. Strict mode fails closed on `NaN` weights with a typed error. Hardened mode applies the documented recovery (e.g. coerce `NaN → +∞` for the affected algorithm only) and records the recovery in the decision log.

**Why do some functions return an iterator and others a list?**
Because NetworkX does. The contract is that `fnx.<func>` returns the exact same Python type as `nx.<func>`: generators stay generators, dict_values stays dict_values, list stays list. This was specifically locked for `all_shortest_paths` (`br-r37-c1-6atv8`).

**Can I run an algorithm under a non-default tie-break policy?**
The Rust-level API in `fnx-algorithms` is parameterized by `TieBreakPolicy`, so yes, but the Python wrappers fix the canonical policy that matches NetworkX. Switching policies at the Python layer is not exposed today; the use case (reproducibility audits on the same algorithm under different policies) is a Rust-level integration test pattern, not a user-facing API.

**Does `pip install franken-networkx` install NetworkX too?**
Yes. `networkx>=3.0` is a hard dependency. fnx's wrapper layer imports nx for exception classes, the dispatch protocol, and the fallback path on unsupported argument shapes.

**Is there a no-NetworkX build?**
Not currently. The dependency on `networkx>=3.0` is part of the parity-helper architecture (the `_call_networkx_*_for_parity` routes need nx available). A "pure fnx" mode would require porting another 143 routes to native Rust.

---

## Common Pitfalls

Pitfalls real users have hit, in roughly descending order of frequency.

### "Why is `nx.shortest_path` not faster after I installed franken-networkx?"

You probably forgot to enable the backend:

```python
import networkx as nx
nx.config.backend_priority = ["franken_networkx"]   # ← required
```

Installing the wheel doesn't automatically rewire `nx.*`; the user is in charge of enabling the backend. This is intentional (otherwise installing the wheel would silently change behavior of every NetworkX program on the machine).

### "My algorithm result has the same set of items but in a different order between runs"

`fnx` shouldn't be the cause; CGSE pins iteration order. If you see drift, the cause is almost always a Python-side issue:

- You're iterating a `dict` constructed from a `set` (sets have hash-randomized iteration order in CPython unless `PYTHONHASHSEED` is fixed).
- You're collecting `connected_components` into a `set` of `frozenset`s and printing them; the print order depends on `frozenset.__hash__`, not on fnx.

Use `list(...)` end-to-end and the order will be deterministic.

### "My benchmark shows fnx is *slower* than networkx"

For very small graphs (< 100 nodes / single-shot analysis), the PyO3 marshaling cost can exceed the algorithm cost. Three suggestions:

- **Use a release build.** `maturin develop --release --features pyo3/abi3-py310`. Debug builds are 5–20× slower.
- **Amortize the marshaling.** A single `fnx.pagerank(G)` call pays the marshaling once; calling it 1000 times in a loop pays it 1000 times. Reuse the result.
- **Use the standalone API, not backend dispatch, when you know the algorithm is supported.** Direct `fnx.pagerank(G)` skips the dispatcher overhead.

### "I called `G.add_edge(0, 1)` and then `G[0][1]['weight'] = 5` but `nx.shortest_path(G, 0, 1, weight='weight', backend='franken_networkx')` returned the wrong path"

This is a known sync subtlety. `_sync_rust_edge_attrs(G)` runs transparently before weighted-algorithm dispatch, but if you're doing direct `G[u][v][k] = v` mutation outside of any algorithm call and then querying `G.adj[u][v][k]`, you may see stale Python-side state. The fix landed in beads `br-r37-c1-sjf4t` and `br-r37-c1-0x9pd`; if you see this on the latest version, please file an issue.

### "MultiGraph edge keys of `0`, `0.0`, and `False` are colliding"

This is intentional. fnx matches Python's `hash(0) == hash(0.0) == hash(False)` dict-key semantics. If you want distinct edges, use distinct keys (e.g. `0`, `1`, `2`).

### "I'm getting `NetworkXNotImplemented` on a function I thought was supported"

A few functions accept the *graph type* but not the *argument shape* you provided. Examples:

- `min_cost_flow` rejects undirected input (matches nx).
- `gomory_hu_tree` rejects MultiGraph input.
- `node_connectivity(G, flow_func=my_callable)` rejects the custom callable; drop the `flow_func` kwarg or call the nx version directly.

Check `docs/upstream_divergence_ledger.md` for the canonical list.

### "My CI is failing G0 (docs freshness)"

This gate fires if `README.md`, `FEATURE_PARITY.md`, or `CHANGELOG.md` hasn't been touched in 50+ commits. Touch the file in the same PR that introduces a substantive change, or batch a `chore(docs):` commit before merging.

---

## Citations and Algorithm References

The algorithm implementations and design decisions trace to a specific body of literature. Treat this as a reading list more than a complete bibliography.

### Graph algorithms

- **Dijkstra, E. W. (1959).** *A note on two problems in connexion with graphs.* Numerische Mathematik 1.
- **Bellman, R. (1958).** *On a routing problem.* Quarterly of Applied Mathematics 16.
- **Floyd, R. W. (1962).** *Algorithm 97: Shortest path.* Comm. ACM 5(6).
- **Johnson, D. B. (1977).** *Efficient algorithms for shortest paths in sparse networks.* JACM 24(1).
- **Hart, Nilsson, Raphael (1968).** *A formal basis for the heuristic determination of minimum cost paths.* IEEE TSCC.
- **Brandes, U. (2001).** *A faster algorithm for betweenness centrality.* Journal of Mathematical Sociology 25(2).
- **Tarjan, R. E. (1972).** *Depth-first search and linear graph algorithms.* SIAM J. Computing 1(2).
- **Tarjan, R. E. (1974).** *A note on finding the bridges of a graph.* Inf. Proc. Letters 2.
- **Kosaraju, S. R. (1978).** Unpublished; canonical statement in Aho, Hopcroft, Ullman.
- **Boyer, J., & Myrvold, W. (2004).** *On the cutting edge: Simplified O(n) planarity by edge addition.* JGAA 8(3). The target of the planned native planarity port.
- **Cooper, K. D., Harvey, T. J., & Kennedy, K. (2001).** *A simple, fast dominance algorithm.* Rice University TR. The algorithm `immediate_dominators` actually uses.
- **Stoer, M., & Wagner, F. (1997).** *A simple min-cut algorithm.* JACM 44(4).
- **Edmonds, J. (1967).** *Optimum branchings.* J. Res. Nat. Bur. Stand.
- **Edmonds, J. (1965).** *Paths, trees, and flowers.* Canad. J. Math 17. (Blossom algorithm for maximum-weight matching.)
- **Edmonds, J., & Karp, R. M. (1972).** *Theoretical improvements in algorithmic efficiency for network flow problems.* JACM 19(2).
- **Goldberg, A. V., & Radzik, T. (1993).** *A heuristic improvement of the Bellman-Ford algorithm.* AML 6.
- **Hopcroft, J. E., & Karp, R. M. (1973).** *An n^{5/2} algorithm for maximum matchings in bipartite graphs.* SIAM J. Computing 2(4).
- **Cordella, Foggia, Sansone, Vento (2004).** *A (sub)graph isomorphism algorithm for matching large graphs.* IEEE TPAMI 26(10). (VF2.)
- **Jüttner, A., & Madarasi, P. (2018).** *VF2++: An improved subgraph isomorphism algorithm.* Discrete Applied Mathematics 242.
- **Newman, M. E. J. (2006).** *Modularity and community structure in networks.* PNAS 103(23). (Greedy modularity.)
- **Blondel et al. (2008).** *Fast unfolding of communities in large networks.* J. Stat. Mech. (Louvain.)
- **Maslov, S., & Sneppen, K. (2002).** *Specificity and stability in topology of protein networks.* Science 296(5569). (`random_reference`.)
- **Janssens, G., & Sörensen, K. (2005).** A partition scheme used by the spanning-tree / arborescence iterators.

### Generators

- **Erdős, P., & Rényi, A. (1959).** *On random graphs I.* Publ. Math. Debrecen 6.
- **Watts, D. J., & Strogatz, S. H. (1998).** *Collective dynamics of "small-world" networks.* Nature 393.
- **Barabási, A.-L., & Albert, R. (1999).** *Emergence of scaling in random networks.* Science 286.
- **Kleinberg, J. (2000).** *The small-world phenomenon: an algorithmic perspective.* (`navigable_small_world_graph`.)
- **Holland, P. W., Laskey, K. B., & Leinhardt, S. (1983).** *Stochastic blockmodels.* Social Networks 5.
- **Lancichinetti, A., Fortunato, S., & Radicchi, F. (2008).** *Benchmark graphs for testing community detection.* PRE 78. (LFR benchmark.)
- **Frucht, R. (1949).** Construction underlying the named small graphs (Frucht, Tutte, Petersen) shipped as fixed generators.

### Systems infrastructure

- **Birch, J. (2013).** *RaptorQ codes: A practical look.* IETF RFC 6330 codifying the erasure code used in `fnx-durability`.
- **O'Hearn, P. W. (2018).** *Continuous reasoning: Scaling the impact of formal methods.* LICS. The doctrinal background for the "fail closed under uncertainty" stance encoded in `RuntimePolicy`.
- **`indexmap` crate** by bluss et al. The ordered hash-map underlying every fnx adjacency structure.
- **`blake3` crate** by Connor / O'Connor / Aumasson / Neves. The hash function backing the decision-path fingerprint in `WitnessSink`.
- **PyO3 / Maturin.** The Python ↔ Rust binding and packaging stack (Konstin / messense et al.).

Most of these papers are open-access; search by author + year. The NetworkX project's algorithm docstrings (in `legacy_networkx_code/` in this repo) cite the same primary sources and are a good cross-reference.

**Can I contribute an algorithm?**
See *About Contributions* below. The short version: bug reports are welcome, PRs that demonstrate a fix are welcome as illustrations, but I won't merge community PRs directly.

**Where do I file a bug?**
[GitHub Issues](https://github.com/Dicklesworthstone/franken_networkx/issues). Please include a minimal reproducer that calls both `nx.<func>` and `fnx.<func>` (or `nx.<func>(..., backend="franken_networkx")`), the exact mismatch, your NetworkX version, and the FrankenNetworkX version (`franken_networkx.__version__`).

---

## Memory Model and Data Layout

Understanding the internals helps when you want to reason about cost or attribute semantics.

### Adjacency

The actual storage layout for each graph type splits adjacency from attribute storage. This differs from NetworkX's nested-dict layout and is more cache-friendly:

```rust
// crates/fnx-classes/src/lib.rs
pub struct Graph {
    nodes:     IndexMap<String, AttrMap>,             // node → its attrs
    adjacency: IndexMap<String, IndexSet<String>>,    // node → neighbor labels
    edges:     IndexMap<EdgeKey, AttrMap>,            // canonical (u,v) → edge attrs
    revision:  u64,                                   // bumped on every mutation
    mode:      CompatibilityMode,                     // Strict | Hardened
    runtime_policy: RuntimePolicy,
}

pub struct DiGraph {
    nodes:        IndexMap<String, AttrMap>,
    successors:   IndexMap<String, IndexSet<String>>,
    predecessors: IndexMap<String, IndexSet<String>>,
    edges:        IndexMap<DirectedEdgeKey, AttrMap>,
    ...
}

pub struct MultiGraph {
    nodes:     IndexMap<String, AttrMap>,
    adjacency: IndexMap<String, IndexMap<String, IndexSet<usize>>>, // node → neighbor → {edge keys}
    edges:     IndexMap<EdgeKey, IndexMap<usize, AttrMap>>,         // (u,v) → {key → attrs}
    edge_count: usize,
    ...
}
```

Three design choices fall out of this layout:

- **`IndexMap` everywhere.** All node, neighbor, and edge containers preserve insertion order on iteration. This is the structural guarantee that lets fnx match NetworkX's iteration order without sorting.
- **Adjacency and edge attributes live in separate maps.** Adjacency lookups (`G[u]`, `G.neighbors(u)`) don't have to walk attribute payloads. Edge-attribute mutations (`G[u][v]["weight"] = 2`) are constant-time on the canonical `EdgeKey` and don't disturb the neighbor iteration order.
- **`DiGraph` keeps `successors` and `predecessors` as separate adjacency maps.** `in_degree(v)` and `out_degree(v)` are O(1) lookups, not full edge walks.

The `revision` counter is incremented on every mutation; the cached snapshot views in `fnx-views` and the Python view classes carry the revision they last saw, so view invalidation is a single integer compare.

### Node identity

Python node labels are canonicalized to a Rust `String` by `node_key_to_string` in `crates/fnx-python/src/lib.rs`. The canonicalization:

- Passes through Python strings unchanged.
- Stringifies integers and booleans to mirror Python's `hash(True) == hash(1)`, `hash(False) == hash(0)` collisions, so an edge added with `key=0` and one added with `key=False` resolve to the same edge (matching NetworkX's dict-based key semantics).
- Collapses floats with integer value into their integer canonical so that `hash(1) == hash(1.0)` parity holds for dict-keyed paths (matching NetworkX).
- Falls back to `repr()` for other hashable Python values (tuples, frozensets, custom objects), preserving distinctness across IEEE-754 special floats (`NaN`, `±Inf`, `1.5`, `1e20`).

This canonicalization is the entire reason MultiGraph edge keys with `key=0`, `key=0.0`, and `key=False` collide into a single edge (tracked in commit history as `br-r37-c1-edgekeyint`). The known limitation: distinct Python types whose `repr()` collides (e.g. user-defined classes returning the same string from `__repr__`) will collide as nodes in fnx. See `docs/upstream_divergence_ledger.md` for the full set of int/str/float canonicalization caveats.

### Attribute storage

Edge and node attributes live in `BTreeMap<String, CgseValue>`. `CgseValue` is a tagged union covering:

- `None` / `Bool` / `Int` (i64) / `Float` (f64) / `String`
- Homogeneous and heterogeneous sequences
- Nested dicts (recursive `CgseValue` map)

Reading and writing attributes uses `serde` end to end. Format writers (`write_gml`, `write_graphml`, `write_gexf`) emit the correct typed values (`bool=0/1`, `long`, `double`) based on the `CgseValue` variant. Read-side, parsers validate type tags and reject malformed inputs in strict mode.

### Node order preservation

Node insertion order is preserved across the entire graph lifecycle, with two important caveats:

- **`G.copy()` is shallow per the NetworkX contract.** Node insertion order is preserved on the copy, but node attribute dicts are aliased, not deep-cloned.
- **`G.copy()` does not preserve node insertion order in some legacy code paths.** This is a known quirk recorded in the project memory; rely on the explicit `add_node` / `add_edge` order if order matters for a tie-break-sensitive downstream call.

### Views

The Python view classes (`NodeView`, `EdgeView`, `DegreeView`, `AdjacencyView`, `SubgraphView`) are defined in `crates/fnx-python/src/views.rs` on top of the borrowed snapshot primitives in `fnx-views`. Views are *live*: mutations to the underlying graph are visible through them. They carry a revision counter so they can invalidate themselves cheaply when the graph changes underneath them. `SubgraphView` is the structure operators (`union`, `intersection`, `difference`, `compose`) accept transparently; they don't materialize a fresh graph unless asked to.

### Edge attribute semantics

Edge attributes pass through `CgseValue`, a tagged-union representation that round-trips between Python objects and Rust's `serde`-serializable values. The supported types and how they survive a round-trip:

| Python type | CgseValue variant | Round-trips through GraphML / GML / JSON? | Notes |
|---|---|---|---|
| `None` | `Null` | yes | GraphML `<data>` element with empty body |
| `bool` | `Bool` | yes | `bool=true/false` for GraphML, `0/1` for GML, JSON boolean |
| `int` (i64 range) | `Int` | yes | GraphML `long`, GML integer, JSON number |
| `float` (finite) | `Float` | yes | GraphML `double`, GML real, JSON number |
| `float` (`NaN`/`±Inf`) | `Float` | partial | GML/GraphML lose precision; JSON preserves via `null` per RFC 7159 |
| `str` | `String` | yes | XML-escaped for GraphML/GEXF, escaped for GML, JSON-escaped |
| `list[T]` (homogeneous) | `Sequence` | yes | type-tagged in GraphML, lossy in GML |
| `dict[str, T]` | `Mapping` | partial | preserved in JSON node-link; GraphML/GML flatten or skip |
| arbitrary Python object | `Repr(String)` | no | falls back to `repr()`, type identity not preserved |

The contract is *NetworkX parity*: anywhere NetworkX accepts an arbitrary Python value as an edge attribute, fnx accepts it too. The difference is that fnx's serialization preserves type tags where the underlying format supports it (GraphML's typed `<data>` elements, GML's typed scalars) so a round-trip `G → write_graphml → read_graphml → G'` preserves the type, not just the string representation.

The `_sync_rust_edge_attrs(G)` helper is the wraparound that pushes Python-side attribute mutations like `G[u][v]["weight"] = 2.0` down into the Rust adjacency map. This is invoked transparently from algorithm wrappers; you only need to know about it if you're profiling the cost of an attribute-heavy hot loop.

### EdgeKey canonicalization

For undirected graphs, edges are canonicalized to `(u, v)` with `u <= v` lex-order so `G[u][v]` and `G[v][u]` find the same entry. For directed graphs, the source/target order is preserved. For MultiGraph variants, the inner edge key (`0, 1, 2, …` or user-supplied) is canonicalized through `edge_key_lookup_string`, collapsing `0`, `0.0`, and `False` to a single canonical (mirroring Python's dict-key hash collisions on those values).

---

## Threat Model

The security doctrine in `AGENTS.md` covers four threat surfaces:

| Surface | Threat | Mitigation |
|---|---|---|
| **Parser input** | Malformed GraphML / GML / GEXF / JSON / edgelist / Pajek crashes the process or escalates to memory corruption. | `#![forbid(unsafe_code)]` workspace-wide. 8 cargo-fuzz parser targets run on every CI push for 60 s each, with persisted corpora. Strict mode rejects malformed input; hardened mode applies bounded recovery (e.g., default attribute, skip malformed node) and logs the recovery as a `DecisionRecord`. |
| **Attribute confusion** | Attacker-supplied attribute tricks downstream code into treating a string as a number, or smuggling a callable through a deserialized graph. | `CgseValue` is a closed-variant sum type. Parsers reject mixed-type lists where the format spec forbids them. Boolean parsing accepts only the spec's literal forms (`0/1/"true"/"false"` per format). |
| **Algorithmic denial** | Adversarial graphs trigger pathological behavior (Dijkstra-with-`-∞`, A*-with-`NaN`-heuristic, planarity bombs, super-linear matching). | Algorithms that can't handle non-finite or negative weights either reject the input fast-closed or delegate to a slower-but-correct nx path. The complexity-witness ledger turns observed-vs-bound mismatches into a CI signal. Stack-safety for deep DFS / planarity / transitive-closure paths. |
| **Reproducibility loss** | A future release silently changes algorithm output and breaks downstream pipelines. | RaptorQ-encoded conformance + perf artifact bundles. Decode-drill proofs. Golden snapshots locked in `tests/python/test_*_golden.py`. CGSE policy registry pinned in source. Audit ledgers fail CI on drift. |

---

## Roadmap

In rough priority order (`bv --robot-triage` shows the current bead backlog):

1. **Wire strict/hardened modes into all parser entry points** (D2–D4 beads). Connect `RuntimePolicy` to `fnx-readwrite` entry points and prove behavior with ≥24 strict + ≥24 hardened fixtures.
2. **Refresh `artifacts/conformance/latest/` reports and add a CI freshness gate** (beads B2–B4).
3. **Native Boyer-Myrvold / Hopcroft-Tarjan planarity** so `_raw_is_planar` is exact, eliminating the nx delegation.
4. **Performance proof artifacts per SLO row (E3)** so every algorithm family in `docs/performance.md` has a profile-and-prove witness on file.
5. **Tail closure on the remaining 143 delegated exports.** Move as many as possible to native fast paths while preserving the parity contract.
6. **First tagged release.** Workspace version moves from `0.1.0` to `0.2.0` once the SLO gate has run green for a sustained window.

---

## Glossary

- **CGSE (Canonical Graph Semantics Engine).** The Rust crate (`fnx-cgse`) and runtime policy machinery (`fnx-runtime`) that pin tie-break policy and emit complexity witnesses.
- **Complexity witness.** A `ComplexityWitness { n, m, dominant_term, observed_count, policy, seed, decision_path_blake3 }` receipt emitted per algorithm execution, drainable from a `WitnessLedger` for audit.
- **Compatibility mode (Strict vs Hardened).** Two-mode runtime contract: Strict fails closed on malformed input; Hardened applies bounded recovery and records every recovery as a `DecisionRecord`.
- **Conformance harness.** The `fnx-conformance` crate; replays curated graph fixtures through fnx and the legacy NetworkX oracle, emitting a structured report under `artifacts/conformance/latest/`.
- **Coverage matrix.** The `docs/coverage.md` ledger, auto-generated from `franken_networkx.__all__` by `scripts/generate_coverage_matrix.py`. Classifies every export and fails CI on drift.
- **Decision-path hash (`decision_path_blake3`).** A length-prefixed Blake3 hash of the sequence of tie-break decisions an algorithm made. Used to detect non-determinism.
- **Delegation ledger.** `docs/delegation_ledger.md`; enumerates every `_call_networkx_*_for_parity` route (public exports that intentionally fall back to NetworkX for specific argument shapes).
- **Fail-closed.** A policy choice in `fnx-runtime`: on uncertain input, raise rather than guess. The default in Strict mode.
- **PY_WRAPPER / RUST_NATIVE / NETWORKX_HELPER.** The three runtime-route categories in the coverage matrix's runtime ledger.
- **RaptorQ sidecar.** An RFC 6330 erasure-coded shadow file written alongside a long-lived artifact (conformance bundle, perf baseline, migration manifest). Combined with a scrub report and a decode-proof receipt to make the artifact self-healing.
- **TieBreakPolicy.** The 12-variant Rust enum in `fnx-cgse` that pins how an algorithm resolves equally-correct choices.
- **Upstream divergence ledger.** `docs/upstream_divergence_ledger.md`; unified record of `native-parity`, `wrapper-patched`, `intentionally-delegated`, `raw-known-gap`, and `owner-acknowledged-limitation` rows.
- **Witness ledger.** A scoped collector inside `fnx-cgse`; you push an algorithm execution into it and drain `ComplexityWitness` receipts at the end of a scope.

---

## References and Inspiration

- **NetworkX.** Hagberg, A., Schult, D., & Swart, P. (2008). *Exploring network structure, dynamics, and function using NetworkX*. SciPy 2008. <https://networkx.org/>. The behavioral oracle for every algorithm in this project; a reference copy ships in `legacy_networkx_code/`.
- **PyO3 + Maturin.** <https://pyo3.rs/> and <https://www.maturin.rs/>. The Python ↔ Rust binding layer and build tool.
- **`indexmap`.** <https://docs.rs/indexmap/>. The deterministic ordered-map that makes node and edge iteration order reproducible.
- **RaptorQ (RFC 6330).** <https://www.rfc-editor.org/rfc/rfc6330>. The erasure code used in `fnx-durability` for self-healing artifact sidecars.
- **VF2++.** Jüttner, A., & Madarasi, P. (2018). *VF2++: An improved subgraph isomorphism algorithm*. Discrete Applied Mathematics, 242. The basis of the native isomorphism path.
- **Edmonds' algorithm.** Edmonds, J. (1967). *Optimum branchings*. Used in the maximum branching / arborescence path.
- **Stoer-Wagner minimum cut.** Stoer, M., & Wagner, F. (1997). *A simple min-cut algorithm*. JACM 44(4). Used by `stoer_wagner`.
- **Boyer-Myrvold planarity.** Boyer, J., & Myrvold, W. (2004). *On the cutting edge: Simplified O(n) planarity by edge addition*. JGAA 8(3). The target of the planned native planarity port.
- **Janssens-Sörensen spanning-tree enumeration.** Used in the `SpanningTreeIterator` and `ArborescenceIterator` rewrite.
- **Kleinberg navigable small world.** Kleinberg, J. (2000). *The small-world phenomenon: an algorithmic perspective*. Backing the `navigable_small_world_graph` generator.

---

## Project Layout

```
franken_networkx/
├── Cargo.toml                 # workspace root (12 crates)
├── pyproject.toml             # maturin + NetworkX backend entry points
├── rust-toolchain.toml        # pinned Rust nightly
├── crates/                    # the 12 Rust crates
│   ├── fnx-classes/           # Graph, DiGraph, MultiGraph, MultiDiGraph
│   ├── fnx-views/             # live and cached views
│   ├── fnx-dispatch/          # backend dispatch routing
│   ├── fnx-convert/           # type conversions + NumPy/SciPy/pandas
│   ├── fnx-algorithms/        # algorithm implementations
│   ├── fnx-generators/        # graph generators
│   ├── fnx-readwrite/         # I/O for 12+ formats
│   ├── fnx-cgse/              # Canonical Graph Semantics Engine
│   ├── fnx-runtime/           # Strict/Hardened modes + policy engine
│   ├── fnx-conformance/       # differential conformance harness
│   ├── fnx-durability/        # RaptorQ sidecars + scrub
│   └── fnx-python/            # PyO3 bindings (cdylib)
├── python/franken_networkx/   # Python package surface
│   ├── __init__.py            # 763 public exports
│   ├── backend.py             # 316 algorithms wired into nx dispatch
│   ├── backend_info.py        # backend metadata for nx registration
│   └── _fnx.pyi               # type stubs
├── tests/python/              # 377 parity / conformance / metamorphic / fuzz / hypothesis / golden tests
├── fuzz/fuzz_targets/         # 33 cargo-fuzz binaries (parsers + algorithm harnesses)
├── examples/                  # 4 runnable examples
├── docs/                      # docs + 5 auto-generated audit ledgers
├── artifacts/                 # CI-generated conformance / perf / RaptorQ artifacts
├── legacy_networkx_code/      # NetworkX Python reference (behavioral oracle)
├── reference_specs/           # reference specifications
├── scripts/                   # audit generators + CI helpers
└── .github/workflows/ci.yml   # G0–G8 gate topology
```

---

## About Contributions

> *Please don't take this the wrong way, but I do not accept outside contributions for any of my projects. I simply don't have the mental bandwidth to review anything, and it's my name on the thing, so I'm responsible for any problems it causes; thus, the risk-reward is highly asymmetric from my perspective. I'd also have to worry about other "stakeholders," which seems unwise for tools I mostly make for myself for free. Feel free to submit issues, and even PRs if you want to illustrate a proposed fix, but know I won't merge them directly. Instead, I'll have Claude or Codex review submissions via `gh` and independently decide whether and how to address them. Bug reports in particular are welcome. Sorry if this offends, but I want to avoid wasted time and hurt feelings. I understand this isn't in sync with the prevailing open-source ethos that seeks community contributions, but it's the only way I can move at this velocity and keep my sanity.*

---

## License

MIT. See [`LICENSE`](LICENSE).

The upstream NetworkX project is BSD-3-Clause licensed. A reference copy of the NetworkX source ships in [`legacy_networkx_code/`](legacy_networkx_code/) as a behavioral oracle for the conformance harness.
