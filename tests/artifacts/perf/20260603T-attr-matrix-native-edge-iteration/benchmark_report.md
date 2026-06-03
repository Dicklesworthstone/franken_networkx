# br-r37-c1-hz27w Benchmark Report

## Target

- Kernel: `fnx.attr_matrix(G, rc_order=list(range(800)))`.
- Fixture: deterministic simple undirected graph from `networkx.gnm_random_graph(800, 6000, seed=8675309)`.
- Profile-backed hotspot: baseline cProfile over 50 calls spent `0.8175s` total, dominated by `attr_matrix`, adjacency wrapper `__getitem__`, `_atlas`, and per-edge node/edge value calls.

## Lever

For exact simple `Graph` / `DiGraph` inputs with `node_attr is None`, source edges from native `_fnx.to_edgelist_simple(G)` instead of walking `G._adj` and re-entering `G[u][v]` wrappers for every edge. Multigraphs, subclasses, node-attribute grouping, and existing fallback paths are unchanged.

## Baseline

- Direct FNX 10-sample mean: `0.008925872700638137s`; digest `171f29578e3a9a9691d28ad6271bd2de365720f8a52e15fd072f7bde07b461fa`.
- Direct NetworkX 10-sample mean: `0.003237433300819248s`; same digest.
- Hyperfine process mean: `307.8 ms +/- 15.4 ms`.
- cProfile 50 calls: `0.8175071350124199s`.

## After

- Direct FNX 10-sample mean: `0.006842623394913971s`; digest `171f29578e3a9a9691d28ad6271bd2de365720f8a52e15fd072f7bde07b461fa`.
- Direct NetworkX 10-sample mean: `0.003199023904744536s`; same digest.
- Hyperfine process mean: `307.7 ms +/- 21.0 ms` (process/import/graph construction dominates).
- cProfile 50 calls: `0.6553985179925803s`.

## Delta

- Direct FNX mean: `0.008925872700638137s -> 0.006842623394913971s` (`1.30x` faster).
- cProfile target workload: `0.8175071350124199s -> 0.6553985179925803s` (`1.25x` faster).
- Hyperfine process-level: effectively unchanged because it includes Python startup, NetworkX graph generation, and graph population.

## Score Gate

- Impact: 2
- Confidence: 4
- Effort: 1
- Score: `2 * 4 / 1 = 8.0`

Decision: keep and commit.
