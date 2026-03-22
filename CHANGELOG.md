# Changelog

All notable changes to FrankenNetworkX are documented in this file.

This project has no formal releases, git tags, or GitHub Releases yet. The
timeline below is reconstructed exhaustively from the commit history on `main`
(246 commits, 2026-02-13 through 2026-03-21). Sections are organized by
capability area rather than raw diff order. Every link points to the actual
commit on GitHub.

Repository: <https://github.com/Dicklesworthstone/franken_networkx>

---

## Unreleased (HEAD -- 01aef85)

Workspace version: **0.1.0** (`Cargo.toml`).
PyPI package name: `franken-networkx` (Alpha, `pip install franken-networkx`).
No GitHub Releases or git tags exist as of 2026-03-21.

---

## 2026-03-21 -- NetworkX Parity Push (428+ Python-exposed functions)

The single largest day of commits (39 commits). The primary goals were closing
parity gaps with NetworkX's public API and completing the CgseValue type
migration across the entire codebase.

### New algorithms

- **Graph coloring** -- multi-strategy greedy coloring (`greedy_color`).
  [7c1d06a](https://github.com/Dicklesworthstone/franken_networkx/commit/7c1d06a5fa9a97972fbdff6ac97427b1b588c3ba)
- **Chordal graphs** -- `is_chordal` via Maximum Cardinality Search.
  [76939c3](https://github.com/Dicklesworthstone/franken_networkx/commit/76939c3366af5c67f5e39cce0397c7cc45b47d8a)
- **Community detection** -- `girvan_newman`, `k_clique_communities`.
  [a5cae89](https://github.com/Dicklesworthstone/franken_networkx/commit/a5cae89aa565d040eb72a0f24fed052234e89acf)
- **Bipartite** -- 4 bipartite algorithm functions for NetworkX parity.
  [a6901e2](https://github.com/Dicklesworthstone/franken_networkx/commit/a6901e24c8f4d50f731a25dbf66bf1d4e27a6373)
- **DAG & ancestors** -- `dag_longest_path`, `ancestors`, `descendants`, and more.
  [a23d295](https://github.com/Dicklesworthstone/franken_networkx/commit/a23d295f3162b63fc7cc3432dbd6ad9e361b768e)
- **Spectral/matrix** -- 7 spectral/matrix functions (Laplacian, adjacency spectrum, etc.).
  [01aef85](https://github.com/Dicklesworthstone/franken_networkx/commit/01aef85905cca7cdc513c607f6003384820d87ed)
- **6 spectral graph theory functions** added to Python bindings.
  [b0403ae](https://github.com/Dicklesworthstone/franken_networkx/commit/b0403aee0bf0d7398a235ace9f58d738daf7f9c4)

### Python binding expansion

- 13 DAG + shortest-path functions exposed.
  [5d2990a](https://github.com/Dicklesworthstone/franken_networkx/commit/5d2990a157eb76c546fc3d5bbd7883a4c79f1361)
- `ego_graph`, k-core family, `line_graph`, `power`, graph operators.
  [3a9a20e](https://github.com/Dicklesworthstone/franken_networkx/commit/3a9a20e28584f58541f9ce770c512f8cba06f295)
- `adjacency_matrix`, `has_bridges`, `stochastic_graph`, and more.
  [045297a](https://github.com/Dicklesworthstone/franken_networkx/commit/045297ae02ee2b7f3e05eccc7dd3e0979a590d57)
- `communicability`, `subgraph_centrality`, mixing matrices.
  [520c894](https://github.com/Dicklesworthstone/franken_networkx/commit/520c89425f1d45ccaf1461978eb20ce331e97cc4)
- `incidence_matrix`, social graph generators, caveman, `random_tree`.
  [058cd6d](https://github.com/Dicklesworthstone/franken_networkx/commit/058cd6d61fee6cc27e9d71a3715d474ad087be6a)
- `structural_holes`, spectral ordering, and more utilities.
  [ab4335d](https://github.com/Dicklesworthstone/franken_networkx/commit/ab4335d5a000bcecccc13a145de053fe947bae61)
- `contracted_nodes`, `contracted_edges`, `configuration_model`, and more.
  [52bbbe7](https://github.com/Dicklesworthstone/franken_networkx/commit/52bbbe7792a2bdcd8e2d0856dd0b3a0e5966ac27)
- `freeze`, `info`, `gnm_random_graph`, `chain_decomposition`, and more.
  [4cd767e](https://github.com/Dicklesworthstone/franken_networkx/commit/4cd767eb95ae46439b203ba8a6bc19b129df0e32)
- 11 more parity functions bringing Python-exposed total to 428.
  [e86fa43](https://github.com/Dicklesworthstone/franken_networkx/commit/e86fa43e6ff962b17ed9ffd3c4b3603aff72798c)
- Additional graph algorithm bindings expansion.
  [f629916](https://github.com/Dicklesworthstone/franken_networkx/commit/f6299161fbbe324182502ec4b691153b71ebd59e)

### Generators

- 5 new random graph generators matching NetworkX API.
  [8ce8c83](https://github.com/Dicklesworthstone/franken_networkx/commit/8ce8c83e3fc938c9c8e4b898747b1d86cb2a2d7a),
  [d312da0](https://github.com/Dicklesworthstone/franken_networkx/commit/d312da066ad8687c304d80fdcb865b21384f866e)
- Watts-Strogatz and graph coloring API parity improvements.
  [4fa5e42](https://github.com/Dicklesworthstone/franken_networkx/commit/4fa5e428fee05e90d5e83d26353c770b84bec653)

### I/O

- **GML format** -- graph reader and writer for NetworkX parity.
  [d9def20](https://github.com/Dicklesworthstone/franken_networkx/commit/d9def203cba8d3bb8091d04908ab21a5d0e1acad)

### Refactoring

- **CgseValue migration** -- unified type across `fnx-classes`, `fnx-algorithms`,
  and `fnx-readwrite`.
  [a6b7e35](https://github.com/Dicklesworthstone/franken_networkx/commit/a6b7e35948b69cb2da418be839fffe0918b55f9e)
- MultiGraph/MultiDiGraph conversion with CgseValue type and edge key support
  in `fnx-convert`, `fnx-runtime`, `fnx-classes`.
  [c6ca066](https://github.com/Dicklesworthstone/franken_networkx/commit/c6ca066ecabf6d4ddbb9b52bbb9400509b7b78a8)
- Algorithm and DiGraph improvements, Python binding refactoring.
  [5c3fb58](https://github.com/Dicklesworthstone/franken_networkx/commit/5c3fb58a5e8d4795b3c793e493383a8763327104),
  [baa2aaa](https://github.com/Dicklesworthstone/franken_networkx/commit/baa2aaa3b5476e12254e26e27879a0d54f5a2932),
  [82421ce](https://github.com/Dicklesworthstone/franken_networkx/commit/82421cef042ea6d8e732d06e3107f5ad56a37072)

### Bug fixes

- `max_flow` functions now return `Result` instead of silently returning zero.
  [66f5b79](https://github.com/Dicklesworthstone/franken_networkx/commit/66f5b79aec72bc7153db03b7bb1414a8c00bacbc)
- Node removal edge cleanup and `flow_terminals` helper extraction.
  [a227f29](https://github.com/Dicklesworthstone/franken_networkx/commit/a227f293bf26fa349b8297c4e104c12cc02dd343)
- Dijkstra test correctness fix, `Box` large enum variants for performance.
  [5cbaa85](https://github.com/Dicklesworthstone/franken_networkx/commit/5cbaa8515716afdcd2551d7371aec5a4c9b0b4a6)

### Testing

- 22 tests for new parity functions.
  [f2eb428](https://github.com/Dicklesworthstone/franken_networkx/commit/f2eb428101d7dbe5b4d2639a1cdf1acf3547c1e9)
- `is_chordal` tests with NetworkX cross-validation.
  [3c51918](https://github.com/Dicklesworthstone/franken_networkx/commit/3c5191823b689bf1d8e1388f8d40604608624752)

---

## 2026-03-19 -- 2026-03-20 -- MultiGraph Support & Performance Overhaul

Two days (36 commits) focused on adding full MultiGraph/MultiDiGraph support,
major performance work, and correctness hardening.

### MultiGraph / MultiDiGraph

- 14 missing `MultiGraph` methods + view types.
  [1c2efdb](https://github.com/Dicklesworthstone/franken_networkx/commit/1c2efdb3ee587e3698bad4a3c8ccf0531f34983a)
- 20 missing `MultiDiGraph` methods + view types.
  [ea21fd4](https://github.com/Dicklesworthstone/franken_networkx/commit/ea21fd448a060b87ed554a9a792b09b18fea00de)
- MultiGraph/MultiDiGraph backend conversion support.
  [c6a3714](https://github.com/Dicklesworthstone/franken_networkx/commit/c6a3714ae80a1a91851ff6bb4d8d5231265c56be)
- Algorithm dispatch enabled for multi-graph types.
  [9e32952](https://github.com/Dicklesworthstone/franken_networkx/commit/9e32952a52b1e5cda3e0d100428fd9f3c0afb1af)
- Weighted graph/digraph projection helpers for multigraph algorithm dispatch.
  [490885f](https://github.com/Dicklesworthstone/franken_networkx/commit/490885f642651fecc27b79ed46120f647bc3491a)
- Expanded weighted multigraph projection and dispatch coverage.
  [307a898](https://github.com/Dicklesworthstone/franken_networkx/commit/307a89884ac052e0f92c2e4c671a6030ecd86142)
- Simplified bindings, conversion, and dispatch logic refactor.
  [309704b](https://github.com/Dicklesworthstone/franken_networkx/commit/309704bf3b6a2da2d12023eb51da1ecd76df9de8)

### Performance

- **Core algorithms rewritten from `HashMap` to index-based `Vec`** with
  heap-based Dijkstra -- significant speedup for shortest-path family.
  [94f6c44](https://github.com/Dicklesworthstone/franken_networkx/commit/94f6c44066d04a55fa1d04fb8215c1f062506932)

### Connectivity

- Directed node connectivity and expanded Python bindings.
  [15bee9e](https://github.com/Dicklesworthstone/franken_networkx/commit/15bee9e522a2e133a99964885b0a441b5a19d380)
- Same-node connectivity/cut variants and improved directed global connectivity.
  [685b2d8](https://github.com/Dicklesworthstone/franken_networkx/commit/685b2d8fcaf1929ea809525f219e644b2080f292)

### Shortest paths

- Directed graph support for all shortest-path Python bindings.
  [6a27ab6](https://github.com/Dicklesworthstone/franken_networkx/commit/6a27ab6e9f968d9cb2d255d2c73373fe561b6f44)
- 12 new algorithm bindings + test/clippy fixes.
  [9e13469](https://github.com/Dicklesworthstone/franken_networkx/commit/9e13469382441fc64adf82473822d28974803b80)

### Bug fixes

- Self-loop degree counting now matches NetworkX convention.
  [05d4556](https://github.com/Dicklesworthstone/franken_networkx/commit/05d45566310894ead69152f70e53ab08f87492b7)
- `max_weight_matching` was incorrectly calling `min_weight_matching`.
  [580b845](https://github.com/Dicklesworthstone/franken_networkx/commit/580b84577fc7b289c79b9072c50151220a701146)
- Directed `minimum_node_cut` tie-break parity.
  [ec2e902](https://github.com/Dicklesworthstone/franken_networkx/commit/ec2e9027339900b09005851d98a38c2999e99eec)
- `is_tree` self-loop detection and `betweenness_centrality` normalization.
  [abc23f9](https://github.com/Dicklesworthstone/franken_networkx/commit/abc23f9e3032557e201c0cdc8863cb2591d979e1)
- Duplicate entries for self-loops in `to_scipy_sparse_array`.
  [e43779d](https://github.com/Dicklesworthstone/franken_networkx/commit/e43779d1deceef86aec3a081df8de89c6a6842ce)
- Preserve node/edge attributes in graph operations.
  [953b64a](https://github.com/Dicklesworthstone/franken_networkx/commit/953b64a064d199331062b3cfdd08de7ab4ed2f3a)
- `edge_attr` type check fix and type stub cleanup.
  [064a0dd](https://github.com/Dicklesworthstone/franken_networkx/commit/064a0dd83767cdd1eeec05f5a8e2ecee3113721c)
- `from_*` methods renamed in `fnx-convert` to fix `wrong_self_convention`
  clippy lint.
  [c536bda](https://github.com/Dicklesworthstone/franken_networkx/commit/c536bda9e741abe17218a8498922b2d24cabff5f)

### Testing

- 33 tests for MultiGraph/MultiDiGraph algorithm dispatch.
  [7a48de2](https://github.com/Dicklesworthstone/franken_networkx/commit/7a48de210005385039e11c55288b735ef4a82fda)
- 32 tests covering 31 previously untested functions.
  [9449578](https://github.com/Dicklesworthstone/franken_networkx/commit/94495784561245afcd9df55500db62c497b45efe)
- 11 hypothesis property tests for expansion metrics.
  [f268fc2](https://github.com/Dicklesworthstone/franken_networkx/commit/f268fc2707bbbb3cbd68ef1d5c17f754f9df2976)
- I/O test coverage expanded for DiGraph and GraphML.
  [4dd784c](https://github.com/Dicklesworthstone/franken_networkx/commit/4dd784c97df61daf8d08d67e21b22178f4733bed),
  [27e8662](https://github.com/Dicklesworthstone/franken_networkx/commit/27e8662df599cdbbec351bd092623a05e8ad4be0)
- Conformance fixture inventory updated to include 20 new fixtures.
  [67890ec](https://github.com/Dicklesworthstone/franken_networkx/commit/67890ec6699f43feb113a7e9dbe71d5502c2be43)

---

## 2026-03-18 -- GraphView Trait & Directed Algorithm Variants

- **GraphView trait** -- unified abstraction for algorithm dispatch across
  `Graph` and `DiGraph`, enabling directed algorithm variants.
  [26c63b0](https://github.com/Dicklesworthstone/franken_networkx/commit/26c63b0a35222fcfabbb837dc4d55dbda8f62f50)
- Strict centrality and matching golden conformance fixtures added.
  [ad89054](https://github.com/Dicklesworthstone/franken_networkx/commit/ad89054b0a694b9357afcd34c9312d1d8e5fb6ac)
- HITS fixture consolidation and algorithm expansion.
  [53c5624](https://github.com/Dicklesworthstone/franken_networkx/commit/53c5624f7bde6b05a5ceb5df85a46d6477bb02b6)
- Python bindings, type stubs, and hardened conformance fixtures expanded.
  [53635da](https://github.com/Dicklesworthstone/franken_networkx/commit/53635daa1449c180404423b8ae08e14a06fcca0c)

---

## 2026-03-12 -- 2026-03-13 -- Algorithm & Binding Explosion

Massive expansion across two days (29 commits). The codebase went from a
handful of algorithm families to near-complete coverage of NetworkX's core API,
with full Python bindings and comprehensive test suites.

### Shortest paths (20 functions, 52 tests)

- `shortest_path`, `all_shortest_paths`, `dijkstra_path`, `bellman_ford_path`,
  `multi_source_dijkstra`, `has_path`, `astar_path`, `shortest_simple_paths`,
  `shortest_path_length`, `average_shortest_path_length`,
  `single_source_shortest_path`, `single_source_shortest_path_length`,
  `all_pairs_shortest_path`, `all_pairs_shortest_path_length`,
  `astar_path_length`, and more.
  [60bfb9b](https://github.com/Dicklesworthstone/franken_networkx/commit/60bfb9b4f5dbeca5041c0c9cdf38b466427c9a64)

### Components (9 functions, 32 tests)

- `strongly_connected_components`, `number_strongly_connected_components`,
  `is_strongly_connected`, `condensation`, `weakly_connected_components`,
  `number_weakly_connected_components`, `is_weakly_connected`, and more.
  [c0b9454](https://github.com/Dicklesworthstone/franken_networkx/commit/c0b945471d1cc8d006e7c0451ce346ca1c481ab1)
- SCC/WCC algorithms for DiGraph.
  [e9f080a](https://github.com/Dicklesworthstone/franken_networkx/commit/e9f080abdc8ee6cf06e2b044c7d8920a613a2ac3)

### Centrality (7 functions, 17 tests)

- `eigenvector_centrality`, `katz_centrality`, `hits`, and more.
  [68e3af7](https://github.com/Dicklesworthstone/franken_networkx/commit/68e3af744a3b8915b937f91fbbd1ee1285c41eba)

### Clustering & cliques (8 functions, 39 tests)

- `clustering`, `triangles`, `transitivity`, `average_clustering`,
  `square_clustering`, `find_cliques`, `graph_clique_number`,
  `number_of_cliques`.
  [acb48e5](https://github.com/Dicklesworthstone/franken_networkx/commit/acb48e519e7339416c7a9db8bb17c12f0fc842e2)

### Traversal

- `bfs_edges`, `bfs_tree`, `bfs_predecessors`, `bfs_successors`, `bfs_layers`,
  `descendants_at_distance`, `dfs_edges`, `dfs_tree`, `dfs_predecessors`,
  `dfs_successors`, `dfs_preorder_nodes`, `dfs_postorder_nodes`,
  `all_shortest_paths`, graph complement.
  [668c67e](https://github.com/Dicklesworthstone/franken_networkx/commit/668c67ee37d17054f9ae89277f923e18e349d873)
- `edge_bfs` and `edge_dfs` traversal algorithms.
  [3128b27](https://github.com/Dicklesworthstone/franken_networkx/commit/3128b273e3b12dcace7cb26e0163a6e2f983fde1)

### DAG algorithms

- `topological_sort`, `topological_generations`, `is_directed_acyclic_graph`,
  `transitive_closure`, `transitive_reduction`, `ancestors`, `descendants`.
  [7df9c76](https://github.com/Dicklesworthstone/franken_networkx/commit/7df9c7617faa23487d4b451410145e3ca1d7d343)
- `is_aperiodic`, `antichains`, `immediate_dominators`, `dominance_frontiers`.
  [8a0de97](https://github.com/Dicklesworthstone/franken_networkx/commit/8a0de97e0f186a94b678c07b62544a663c1709b0)

### Graph predicates (11 functions, 34 tests)

- `is_bipartite`, `is_tree`, `is_forest`, `is_arborescence`, `is_branching`,
  `is_empty`, `is_simple_path`, and more.
  [06d8cb7](https://github.com/Dicklesworthstone/franken_networkx/commit/06d8cb74be4e66af1653ae0ca0372b3cc914bcb6)

### Isomorphism, planarity, approximation

- `is_isomorphic`, `could_be_isomorphic`, `fast_could_be_isomorphic`,
  `faster_could_be_isomorphic`, `is_planar`, `astar_path`, `astar_path_length`,
  `min_weighted_vertex_cover`, `maximum_independent_set`, `max_clique`,
  `clique_removal`, `large_clique_size`, `barycenter`.
  [170e16d](https://github.com/Dicklesworthstone/franken_networkx/commit/170e16dc3525d3b7ebb961ba6c2332c83e131a8c)

### Community detection & graph operators

- `louvain_communities`, `greedy_modularity_communities`,
  `label_propagation_communities`, `modularity`, `dominating_set`,
  `is_dominating_set`, all-pairs shortest paths, graph operators
  (`complement`, `union`, `intersection`, `compose`, `difference`,
  `symmetric_difference`).
  [7df9c76](https://github.com/Dicklesworthstone/franken_networkx/commit/7df9c7617faa23487d4b451410145e3ca1d7d343)

### Link prediction & graph metrics

- `common_neighbors`, `jaccard_coefficient`, `adamic_adar_index`,
  `preferential_attachment`, `resource_allocation_index`, `reciprocity`,
  `overall_reciprocity`, `wiener_index`.
  [2602f25](https://github.com/Dicklesworthstone/franken_networkx/commit/2602f25d8f9eb566800d9bbb5ae449d09002daad),
  [88276f2](https://github.com/Dicklesworthstone/franken_networkx/commit/88276f28f5918a2d2436e26fe4ece9d45c4dc081)
- `average_degree_connectivity`, `rich_club_coefficient`, `s_metric`.
  [83a5b03](https://github.com/Dicklesworthstone/franken_networkx/commit/83a5b037e337d1d8c62c526103a875400500fcdf)

### Connectivity & expansion metrics (8 functions)

- Node/edge expansion, vertex/edge connectivity cuts, mixing expansion,
  Cheeger constant, and more.
  [e2e5982](https://github.com/Dicklesworthstone/franken_networkx/commit/e2e5982c1d071daa2eea4d4dc0c6de8f8d71d522),
  [587c8ff](https://github.com/Dicklesworthstone/franken_networkx/commit/587c8ff60820ba4c6da13ae21ea985da6f99043e),
  [0f651f0](https://github.com/Dicklesworthstone/franken_networkx/commit/0f651f01c21b9a924292be111c1c3d97d3b19238)

### Matching & covers

- `is_edge_cover`, `max_weight_clique` (9 tests).
  [760851a](https://github.com/Dicklesworthstone/franken_networkx/commit/760851aad1d2e75ca8bcc6150257fcbccac70bdf)
- Tree recognition, isolates, boundary, path validation, matching, cycles
  (13 new bindings).
  [ff2980a](https://github.com/Dicklesworthstone/franken_networkx/commit/ff2980af5c71002f6e073b2d03d256471f7780e9)

### Generators (44 new generators, 82 tests)

- **40 classic graph generators**: Petersen, complete bipartite, grid, hypercube,
  ladder, wheel, tutte, and many more.
  [b55ffda](https://github.com/Dicklesworthstone/franken_networkx/commit/b55ffda1be8830b731d5b525eb4d9524bdddf0e8)
- Circulant, Kneser, Paley, chordal cycle generators.
  [f3b06a8](https://github.com/Dicklesworthstone/franken_networkx/commit/f3b06a874639cac2e02fc65ca2a887b3f0743ea1)

### Flow & trees

- `minimum_cut` algorithm with undirected-only enforcement.
  [371f37a](https://github.com/Dicklesworthstone/franken_networkx/commit/371f37a72532ba54160f0f3719cafa0a0604ea27)
- **FlowGraphView trait** generalizing flow algorithms to directed graphs.
  [dcc2107](https://github.com/Dicklesworthstone/franken_networkx/commit/dcc2107d9f7752a0c7820235862dce0702abc52c)
- Optimum branching (Edmonds' algorithm), bipartite matching, tree algorithms.
  [9449abf](https://github.com/Dicklesworthstone/franken_networkx/commit/9449abfa5508025f98e64fec86dd28da55c42867)
- `maximum_flow` edge values, partition/random spanning trees, spanning tree
  counting (`number_of_spanning_trees`).
  [ef7fd78](https://github.com/Dicklesworthstone/franken_networkx/commit/ef7fd78fc287cc955f81f9b08451094a1460728b)
- Spanning edge APIs exposed.
  [66187f1](https://github.com/Dicklesworthstone/franken_networkx/commit/66187f1278d55abba875680c8e9277ec94b4dbd3)

### Miscellaneous algorithms

- `girth` and `find_negative_cycle` (10 tests).
  [cf16738](https://github.com/Dicklesworthstone/franken_networkx/commit/cf1673822fd614a8290a72843c5e448b2e0a3d7a)
- `global_efficiency`, `local_efficiency`, tree broadcasting,
  `maximal_independent_set`, `chordal_graph_treewidth`, `spanner`.
  [4d02565](https://github.com/Dicklesworthstone/franken_networkx/commit/4d0256585ce0a3c4b9b023891a2f55ca9549519f)

### Bug fix

- Compile errors in new bindings fixed, `nbunch2` added to `node_boundary`,
  47 tests added.
  [4ffd29f](https://github.com/Dicklesworthstone/franken_networkx/commit/4ffd29fec0096312645404bfb0bb2e8c24af4349)

---

## 2026-02-26 -- Python Package & NetworkX Backend

The project became pip-installable with full PyO3 bindings and a NetworkX
backend entry point (`nx.config.backend_priority = ["franken_networkx"]`).

### DiGraph & backend (major commit)

- **DiGraph support** with directed edge semantics (successors/predecessors,
  in_degree/out_degree). New PyDiGraph wrapper mirroring PyGraph's API.
  GraphRef enum enabling all 50+ algorithm bindings to accept both Graph and
  DiGraph transparently.
- **NetworkX backend** -- full `BackendInterface` class with `convert_from_nx`,
  `convert_to_nx`, `can_run`, `should_run` methods.
- **Graph generators** in Python -- `path_graph`, `cycle_graph`, `star_graph`,
  `complete_graph`, `empty_graph`, `gnp_random_graph`.
- **Graph I/O** -- `read_edgelist`/`write_edgelist`, `read_adjlist`/`write_adjlist`,
  `read_graphml`/`write_graphml`, `node_link_data`/`node_link_graph`.
- **Drawing module** -- layout algorithms (spring, circular, kamada_kawai,
  planar, random, shell, spectral) and draw functions delegating to
  NetworkX/matplotlib.
- **Conversion utilities** -- `relabel_nodes`, `convert_node_labels_to_integers`,
  `to/from_numpy_array`, `to/from_scipy_sparse_array`, `to/from_dict_of_dicts`,
  `to/from_dict_of_lists`, `to/from_edgelist`, `to/from_pandas_edgelist`.
- **CI/CD** -- GitHub Actions workflow and `pyproject.toml` added.
  [cef86c5](https://github.com/Dicklesworthstone/franken_networkx/commit/cef86c5b1025a4a98486f24459e187d61628efc9)

### Algorithm bindings

- GIL released in all algorithm bindings; 12 conformance test suites added.
  [a4b6518](https://github.com/Dicklesworthstone/franken_networkx/commit/a4b65182591a7c7305df556cae001b3dae386971)
- Euler path/circuit algorithms (`eulerian_circuit`, `eulerian_path`,
  `is_eulerian`, `has_eulerian_path`, `is_semieulerian`) and PyO3 bindings.
  [e912899](https://github.com/Dicklesworthstone/franken_networkx/commit/e9128995369fb7a218a2d608bc3eda2801ec401a)

### Generators

- Watts-Strogatz and Barabasi-Albert generators with Python exposure and
  weighted `size()`.
  [3107428](https://github.com/Dicklesworthstone/franken_networkx/commit/3107428d6253b9a3f7ab230511dd4767837f82f4),
  [6a8ca21](https://github.com/Dicklesworthstone/franken_networkx/commit/6a8ca21ea5efa42187e847b80d1f172229f436b6),
  [c767d30](https://github.com/Dicklesworthstone/franken_networkx/commit/c767d308ebba304ee87e80754f0e733a46116562)

### Bug fixes

- `from_numpy_array` and `from_scipy_sparse_array` to iterate full matrix.
  [94f9b4a](https://github.com/Dicklesworthstone/franken_networkx/commit/94f9b4ace74a8d4cbcf8d4ee7ac89aa208273859)
- Prevent panic in Barabasi-Albert with `m=1` and harden test infrastructure.
  [12d8e37](https://github.com/Dicklesworthstone/franken_networkx/commit/12d8e37549482b12d510f6fe88d14e6776633d35)

---

## 2026-02-25 -- Algorithm Family Expansion & Conformance Hardening

10 new algorithm families landed with oracle fixtures and conformance harness
coverage.

### Algorithms

- **10 algorithm families** with oracle fixtures: `core_number`,
  `average_neighbor_degree`, `degree_assortativity_coefficient`, `voterank`,
  `find_cliques`, `graph_clique_number`, `number_of_cliques`,
  `non_neighbors`, `is_empty`, `degree_histogram`.
  [74e0ebd](https://github.com/Dicklesworthstone/franken_networkx/commit/74e0ebde5c076013840bdc1fe7c5fb359b905ead),
  [639600c](https://github.com/Dicklesworthstone/franken_networkx/commit/639600ca7fc7e66ddbcd38ced88b3ce0175338e1)
- Edge connectivity and global minimum edge cut operations.
  [9d8c3da](https://github.com/Dicklesworthstone/franken_networkx/commit/9d8c3da2ae54c9bba0ec25aa70e7885b0e9385eb)
- Matching algorithm verification logic and max-weight strict fixture.
  [07fc7e0](https://github.com/Dicklesworthstone/franken_networkx/commit/07fc7e0c0d94631f48ffaaab8dd1648d60f22805),
  [d19360d](https://github.com/Dicklesworthstone/franken_networkx/commit/d19360da0ec5ed9779a262514a2868d683dc32ef)
- Continued algorithm implementation from concurrent development.
  [775191a](https://github.com/Dicklesworthstone/franken_networkx/commit/775191ab6b2ffc2d47f0007b8af61eef62180cdf)

### Bug fixes

- Stabilize edge ordering and relax HITS centrality tolerance.
  [d9f2beb](https://github.com/Dicklesworthstone/franken_networkx/commit/d9f2bebc40cdbb904a956893caf8ad3174686983)
- Correct edge cases in algorithm implementations.
  [9a20f1c](https://github.com/Dicklesworthstone/franken_networkx/commit/9a20f1c9d9bec0a1a0b608b9ef737ec1ae9454dd)

---

## 2026-02-21 -- Correctness Fixes & GraphML I/O

### I/O

- **GraphML reader and writer** with conformance test support.
  [cd24316](https://github.com/Dicklesworthstone/franken_networkx/commit/cd24316f7906d05c8f8f1a926eb3d631f0832b79)

### Bug fixes

- Edmonds-Karp BFS fixed to traverse residual neighbors instead of all nodes.
  [6762c17](https://github.com/Dicklesworthstone/franken_networkx/commit/6762c170e0413eefa46acd114f8e9918354360ad)
- HITS normalization, shortest path epsilon, min-cut filtering, retry
  off-by-one, NaN probability handling, decode proof hashes -- multi-area
  correctness sweep.
  [ef8cce7](https://github.com/Dicklesworthstone/franken_networkx/commit/ef8cce7c09b634206382c574fc41162ec5f58d64)
- Stack-safety, scrub timestamp, attribute encoding, and runtime correctness
  fixes.
  [ca3db35](https://github.com/Dicklesworthstone/franken_networkx/commit/ca3db35b2eccc1446c6fb4516e22d200a7fe4b2a)
- Harden NaN handling in risk probability decision path to fail-closed.
  [54f9491](https://github.com/Dicklesworthstone/franken_networkx/commit/54f949199a78cc23fd513364d17d1eaa42c3922b)

### Dependencies

- Switch `asupersync` and `ftui` from local paths to crates.io.
  [d34ef40](https://github.com/Dicklesworthstone/franken_networkx/commit/d34ef40e2b232ad5a503663647d1bf1d06fed7fb)

---

## 2026-02-20 -- Centrality & Structural Algorithm Expansion

### Algorithms

- **Six new centrality algorithms** (eigenvector, Katz, HITS, PageRank variants)
  and blossom-optimal weighted matching.
  [d4c83bb](https://github.com/Dicklesworthstone/franken_networkx/commit/d4c83bbc5af6335e5abdc3e1af9f68412e4b9b68)
- **Articulation points, bridges**, and extended edge connectivity algorithms.
  [fdde1f4](https://github.com/Dicklesworthstone/franken_networkx/commit/fdde1f4e2c30402d36d5322ab9b211d5adad332f)
- K-core decomposition, clustering coefficients, and DAG algorithms.
  [09ce092](https://github.com/Dicklesworthstone/franken_networkx/commit/09ce092368be5eba08d7f000221bf341c6f77ac8)

### Conformance

- Oracle-validated centrality fixtures: eigenvector, harmonic, Katz, PageRank,
  HITS, edge betweenness.
  [3141edd](https://github.com/Dicklesworthstone/franken_networkx/commit/3141edd8514bf1fc965b4ce42a2a352e2658cf87),
  [fc864b6](https://github.com/Dicklesworthstone/franken_networkx/commit/fc864b66859fcf48a5ccf634ed9b5f5cc897e96d),
  [d20cf7f](https://github.com/Dicklesworthstone/franken_networkx/commit/d20cf7fe571bf1d3301ca0b346ac3e8bbb010fc7),
  [76bbdd2](https://github.com/Dicklesworthstone/franken_networkx/commit/76bbdd21ff49ba1b2b195db8ced0750e1767a99f),
  [63c55fc](https://github.com/Dicklesworthstone/franken_networkx/commit/63c55fc522b4ee5dc01dd568606f291cd9b22ae2)
- Articulation points and bridges conformance test fixtures.
  [51c2ed2](https://github.com/Dicklesworthstone/franken_networkx/commit/51c2ed2e1f24f40bf31f6f3bea81738857b61d74),
  [c4f144c](https://github.com/Dicklesworthstone/franken_networkx/commit/c4f144cd432bac8805e6ac3d563e207ca546487f)
- NetworkX oracle-validated centrality tests for path graphs.
  [e9ceafd](https://github.com/Dicklesworthstone/franken_networkx/commit/e9ceafd39a4f7b884e4a8cf984da868e1ffccea5)

### Dependencies

- Upgrade workspace dependencies to latest compatible versions.
  [a34b40a](https://github.com/Dicklesworthstone/franken_networkx/commit/a34b40aec78e99898207c89e3c5594a39e91666c)

---

## 2026-02-19 -- Vertical Slices 5-7 (Centrality, Generators, Min-Cut)

### Algorithms

- **Deterministic minimum-cut surface** with Edmonds-Karp residual reachability
  (vertical slice 7).
  [b122d13](https://github.com/Dicklesworthstone/franken_networkx/commit/b122d13881c1dbdeb9cc529e032084b6d40a2006)
- **Betweenness centrality**, maximal matching, and weighted matching algorithms.
  [fc02725](https://github.com/Dicklesworthstone/franken_networkx/commit/fc0272503856bac4d31bd3d3347063224c8e251c)
- **Harmonic centrality** algorithm and adjacency-list read/write support.
  [d373239](https://github.com/Dicklesworthstone/franken_networkx/commit/d373239106bf0eff4ef31373905c0eb1e62c64a6)

### Generators

- Deterministic `star_graph` generator with full conformance integration
  (vertical slice 5 extension).
  [28a1e50](https://github.com/Dicklesworthstone/franken_networkx/commit/28a1e504a5a0b830ad4bdf41f0277f7c429f654b)

### Conformance

- Betweenness centrality wired into fixture runner with oracle-backed fixture.
  [b6c008d](https://github.com/Dicklesworthstone/franken_networkx/commit/b6c008d3c983e60410d56fb4a402cca97713df6a)
- `generators_star_strict.json` oracle-backed fixture.
  [10a8b19](https://github.com/Dicklesworthstone/franken_networkx/commit/10a8b19c988a256b9127fec4bf1c509dd4e41c01)

### CGSE (Canonical Graph Semantics Engine)

- CGSE v1 evidence packs, policy spec, threat model, and legacy tiebreak
  ledger.
  [4608950](https://github.com/Dicklesworthstone/franken_networkx/commit/46089503fc0c0eb870b8a1452168aa6b309c9410)

---

## 2026-02-18 -- Vertical Slices 2-4 (Readwrite, Weighted Paths, Max-Flow)

### Vertical slice 2: Readwrite

- Edgelist and JSON graph I/O with full conformance test coverage.
  [df1a9f0](https://github.com/Dicklesworthstone/franken_networkx/commit/df1a9f0ac04ddd9f16b34259bc31da4c81d8bb83)

### Vertical slice 3: Weighted shortest paths

- Deterministic weighted shortest-path parity slice.
  [100a7af](https://github.com/Dicklesworthstone/franken_networkx/commit/100a7af1dd963e44a6dcfc12640d5af4e0466900)

### Vertical slice 4: Max-flow

- First deterministic max-flow parity slice (Edmonds-Karp).
  [ced4595](https://github.com/Dicklesworthstone/franken_networkx/commit/ced4595ec39e986c944727dd4086e67e8cf4d0b1)

### CGSE & generators

- CGSE deterministic policy spec and semantics threat model; expanded generator
  coverage with cycle/path hardening.
  [2ea8486](https://github.com/Dicklesworthstone/franken_networkx/commit/2ea84864382bb4fae971fb914a3a43bba946401f)

### Licensing

- Adopt MIT + OpenAI/Anthropic rider across workspace.
  [442a3c6](https://github.com/Dicklesworthstone/franken_networkx/commit/442a3c662c729c24c53a7f406c73ca8cc81124a9)

---

## 2026-02-17 -- Conformance Contracts & E2E Infrastructure

### Conformance hardening

- Phase2c extraction packets with threat matrix, compatibility boundaries, and
  hardened deviation guardrails.
  [334e177](https://github.com/Dicklesworthstone/franken_networkx/commit/334e1778589b1994ca47b4826559eb27ad1b87ea)
- Dispatch route scenarios added; dispatch and runtime crates hardened;
  phase2c security contracts updated.
  [8eb9529](https://github.com/Dicklesworthstone/franken_networkx/commit/8eb9529b8e550a32063dcfed71067363d40c3550)
- Hardened graph invariant tests, mismatch taxonomy and drift report schemas,
  proptest-driven adversarial fixtures.
  [f8490b8](https://github.com/Dicklesworthstone/franken_networkx/commit/f8490b80a73fcc2d610f43fdb0bd7b452c18eb84)
- Readwrite packet with full contract tables, module boundaries, and artifact
  generator.
  [ad6edfc](https://github.com/Dicklesworthstone/franken_networkx/commit/ad6edfce3d7e21c6afade9d6dd4e0541cf326806)
- Packet-004 and packet-005 conformance contracts with property-based testing
  and structured telemetry.
  [1fbd16a](https://github.com/Dicklesworthstone/franken_networkx/commit/1fbd16ab7a2764bee4eaac509c58b28a16fd79fb)

### Documentation

- Pass-B behavioral contracts expanded, legacy analysis corrected,
  Phase 2C fixture manifest and risk documentation refreshed.
  [cebdcba](https://github.com/Dicklesworthstone/franken_networkx/commit/cebdcbad122807f71a591f616213f6b4d050a95d)

---

## 2026-02-16 -- Conformance Gates & Safety Infrastructure

### Safety & reliability

- **Fail-closed policy**, operator playbook, and dashboard gate contracts.
  [635f819](https://github.com/Dicklesworthstone/franken_networkx/commit/635f8193bc88da1128705b1223fa98ecf82a59ec)
- Machine-checkable CI gate topology contract (G1..G8).
  [cb44743](https://github.com/Dicklesworthstone/franken_networkx/commit/cb447433af1d267640fb594f2b84d70576ebddf1)
- Reliability budget gate with flake quarantine.
  [1953b88](https://github.com/Dicklesworthstone/franken_networkx/commit/1953b88ad3bac51eefb3c858f569fa538bd363d5)
- AsuperSync adapter recovery and fault-injection E2E scenarios with forensics
  integration.
  [1897199](https://github.com/Dicklesworthstone/franken_networkx/commit/18971990a620842d7abda4617c25398bf08cd4e2)
- AsuperSync performance gate with pre-allocated transition vec and RaptorQ
  encoding.
  [c036652](https://github.com/Dicklesworthstone/franken_networkx/commit/c0366528ead2fd43ed254fa974462720b06c2883)

### Documentation passes

- DOC-PASS-07: error taxonomy, failure modes, and recovery semantics.
  [285548e](https://github.com/Dicklesworthstone/franken_networkx/commit/285548eb9b88e36598a4c636108ee3ccf04228c7)
- DOC-PASS-05: complexity, performance, and memory analysis.
  [a9596a5](https://github.com/Dicklesworthstone/franken_networkx/commit/a9596a515509a5fe7140d1874ae19651a27b661e)
- DOC-PASS-04: execution path tracing infrastructure and gate test.
  [1cd4d11](https://github.com/Dicklesworthstone/franken_networkx/commit/1cd4d111127161690ff1899f386cd3a69296f389),
  [02b14d5](https://github.com/Dicklesworthstone/franken_networkx/commit/02b14d5a8c333fde792ddeae7d58843a9fc82a7b)
- DOC-PASS-02: symbol API census gate test.
  [dbdf375](https://github.com/Dicklesworthstone/franken_networkx/commit/dbdf375e5c0b89fd99f68beaa417f2ac1805a266)

---

## 2026-02-15 -- AsuperSync Integration & Safety Gates

### AsuperSync integration

- AsuperSync adapter state machine, fault injection suite, and FTUI
  telemetry/workflow artifacts with full conformance gates.
  [9566152](https://github.com/Dicklesworthstone/franken_networkx/commit/9566152399491efed01e2ced959ed403785e88dc)
- AsuperSync capability matrix artifact and schema.
  [f0b48d7](https://github.com/Dicklesworthstone/franken_networkx/commit/f0b48d746d1b25c1ea5f9fafbcdce04bc0bc1739)
- Align `asupersync` and franken ecosystem crates to v0.2.0.
  [057759c](https://github.com/Dicklesworthstone/franken_networkx/commit/057759caf79f7aa0f1b00b276950c04d8828e446)

### Safety & conformance

- Safety gate pipeline and unsafe exception registry with validation
  infrastructure.
  [36fc492](https://github.com/Dicklesworthstone/franken_networkx/commit/36fc492eb691a024b7ba4c094d47a96bdd547f35)
- CGSE legacy tiebreak ordering ledger and validation infrastructure.
  [37c2047](https://github.com/Dicklesworthstone/franken_networkx/commit/37c204750ee1a0afd591b65f897b4c345ed3aca0)
- E2E script-pack replay infrastructure and gate orchestrator.
  [c400e57](https://github.com/Dicklesworthstone/franken_networkx/commit/c400e571e3566ebc692e2eccd272ec10e96b71b6)
- Clean final compliance attestation suite.
  [b8580c4](https://github.com/Dicklesworthstone/franken_networkx/commit/b8580c4b5138ac114b3e8beff47f39be5071e924)
- Adversarial soak scenario and expanded E2E script-pack infrastructure.
  [c9d308a](https://github.com/Dicklesworthstone/franken_networkx/commit/c9d308aeb86360254011767b990df4bce65fb7f2)
- Provenance spoofing, policy bypass, and source contamination ambiguity
  threat classes.
  [9f9cc44](https://github.com/Dicklesworthstone/franken_networkx/commit/9f9cc44a0e13868264c7b9bbd2880b6e9c2ef003)

### Testing

- Property and snapshot tests for `FtuiTelemetryAdapter` determinism.
  [e1f0fc0](https://github.com/Dicklesworthstone/franken_networkx/commit/e1f0fc00e9c9d538cb3d990e08a55084b6914c6c)
- Journey/evidence pack gates, adversarial regression bundle expanded to 53
  fixtures.
  [03aab2b](https://github.com/Dicklesworthstone/franken_networkx/commit/03aab2b3501b3f3b99bbcee9a862586ade78f7b2)

---

## 2026-02-14 -- Conformance Framework & Adversarial Testing

### Conformance infrastructure

- DOC-PASS-01 module cartography gate and artifacts.
  [857249d](https://github.com/Dicklesworthstone/franken_networkx/commit/857249df0ce131e14182f9625a67ffa147ab0f02)
- DOC-PASS-03 data model layer, structured log schema, and forensics emitter.
  [598dc18](https://github.com/Dicklesworthstone/franken_networkx/commit/598dc18d35d20ac286d73bcf9f16d02dc65a9e94)
- E2E scenario matrix gate with generation and validation scripts.
  [53e9d2d](https://github.com/Dicklesworthstone/franken_networkx/commit/53e9d2ddfc83a5979c2c54a8ff8b67382675a938)
- E2E script pack testing infrastructure with schema validation.
  [e5a976b](https://github.com/Dicklesworthstone/franken_networkx/commit/e5a976bfde59953f34aa05b7ec8801e9b0997804)
- Phase2c packet readiness gate and security contract validation.
  [0660b3e](https://github.com/Dicklesworthstone/franken_networkx/commit/0660b3ec1fe02cbb6feeff483497d20d30c7f11f)

### Adversarial testing

- Adversarial testing expanded with crash triage and regression bundle.
  [14407e9](https://github.com/Dicklesworthstone/franken_networkx/commit/14407e9e19b0b1940eda1cec4d05080d577f4e1d),
  [ccc2690](https://github.com/Dicklesworthstone/franken_networkx/commit/ccc2690e2f773949ad3f994f12acdca98780e3c3),
  [61630a8](https://github.com/Dicklesworthstone/franken_networkx/commit/61630a850b74cc79a7b7939a1941de3f4ac3f122)

### Performance

- Phase2c performance baseline matrix and regression gate infrastructure.
  [367fe07](https://github.com/Dicklesworthstone/franken_networkx/commit/367fe078f22e0028b2e15e177351f841dbfc2155)

### Documentation

- P2C-001 through P2C-009 extraction packets, isomorphism proofs, and essence
  ledger.
  [f49a482](https://github.com/Dicklesworthstone/franken_networkx/commit/f49a48232f601e37d4ffa6842331ee77e875c941)

---

## 2026-02-13 -- Initial Public Import (Vertical Slice 1)

First commit: 1,047 files, 330,958 insertions. The initial import established
the full workspace architecture and the first executable vertical slice.

### Architecture

- **Workspace crates**: `fnx-classes`, `fnx-views`, `fnx-dispatch`,
  `fnx-convert`, `fnx-algorithms`, `fnx-generators`, `fnx-readwrite`,
  `fnx-durability`, `fnx-conformance`, `fnx-runtime`, `fnx-python`.
- Deterministic graph core (`fnx-classes`), strict/hardened runtime + evidence
  ledger (`fnx-runtime`), unweighted shortest path + complexity witness
  (`fnx-algorithms`), fixture-driven conformance harness (`fnx-conformance`).

### Vertical slice 1

- `Graph` type with deterministic graph semantics and CGSE tie-break policies.
- Unweighted shortest-path algorithm with complexity witness.
- Connected-components algorithm.
- `empty_graph`, `path_graph`, `complete_graph` generators.
- Conformance harness with oracle-backed fixtures.
- RaptorQ sidecar + scrub/decode drill pipeline (`fnx-durability`).
- Benchmark gate with percentile regression tracking
  (`scripts/run_benchmark_gate.sh`).

### Performance

- Neighbor iterator optimization in Phase2c packet validation framework.
  [e535089](https://github.com/Dicklesworthstone/franken_networkx/commit/e535089e758b70698a16c65fbfa1c5fe0e62b09c)
- Elide clone churn in BFS-family traversals and `add_edge` hot path.
  [2ef18ac](https://github.com/Dicklesworthstone/franken_networkx/commit/2ef18ac4e74582f7ec25e5d471f4cf6cd7b056ee)

### Artifacts

- Structured conformance logs, durability reports, and WebP README banner.
  [da02943](https://github.com/Dicklesworthstone/franken_networkx/commit/da029439fc475ad33d0ac7c31e05f63937a08f98)

### Representative commit

- [125113a](https://github.com/Dicklesworthstone/franken_networkx/commit/125113a6fd15250c4faa60b791a29ef1485b6514)
  -- Initial public import of franken_networkx

---

## Summary Statistics

| Metric | Value |
|--------|-------|
| Total commits | 246 |
| Date range | 2026-02-13 to 2026-03-21 |
| Git tags | 0 |
| GitHub Releases | 0 |
| Workspace version | 0.1.0 |
| Workspace crates | 11 |
| Python-exposed functions | 428+ |
| Graph types | Graph, DiGraph, MultiGraph, MultiDiGraph |
| Algorithm families | 25+ (shortest path, connectivity, centrality, clustering, matching, flow, trees, Euler, DAG, traversal, community, isomorphism, planarity, approximation, coloring, link prediction, and more) |
| I/O formats | edgelist, adjlist, GraphML, GML, JSON (node-link) |
| Conformance fixtures | 20+ oracle-backed golden fixtures |
| License | MIT |

---

## Crate Map

| Crate | Role |
|-------|------|
| `fnx-classes` | Graph, DiGraph, MultiGraph, MultiDiGraph core types |
| `fnx-algorithms` | All algorithm implementations |
| `fnx-generators` | Deterministic and seeded graph generators |
| `fnx-readwrite` | I/O: edgelist, adjlist, GraphML, GML, JSON |
| `fnx-views` | Live/cached view semantics with revision invalidation |
| `fnx-dispatch` | Deterministic dispatch routing |
| `fnx-convert` | Conversion routes between graph types and external formats |
| `fnx-durability` | RaptorQ sidecar, scrub/decode drill pipeline |
| `fnx-conformance` | Fixture-driven conformance harness with oracle validation |
| `fnx-runtime` | Strict/hardened runtime, evidence ledger, CGSE policy engine |
| `fnx-python` | PyO3/maturin Python bindings (ABI3, Python 3.10+) |
