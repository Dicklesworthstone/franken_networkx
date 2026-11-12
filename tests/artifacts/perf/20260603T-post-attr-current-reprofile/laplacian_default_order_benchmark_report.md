# br-r37-c1-7svor Benchmark Report

## Target

- Kernel: `franken_networkx.laplacian_matrix(G)` on exact `Graph` with `nodelist=None`.
- Fixture: deterministic `networkx.barabasi_albert_graph(8000, 4, seed=12345)` mirrored into `fnx.Graph`.
- Profile-backed hotspot: focused cProfile over 8 calls spent `0.223s` in `_fnx.adjacency_index_arrays`.

## Lever

For exact undirected `Graph` with default nodelist, route `laplacian_matrix` through the existing `_native_adjacency_default_order_index_arrays` helper instead of the generic nodelist-index helper.

## Baseline

- Sweep: FNX `0.03878668759716675s`; NetworkX `0.030633811402367428s`; ratio `1.266x`; digest matched.
- Focused direct FNX repeat-12 mean: `0.04114515699620824s`; median `0.035806276500807144s`.
- Focused cProfile: `laplacian_matrix` `0.413s / 8`; `_fnx.adjacency_index_arrays` `0.223s / 8`.
- Hyperfine process envelope: `831.4 ms +/- 32.7 ms`.

## After

- Direct FNX repeat-12 mean: `0.020119644422569156s`; median `0.013879560006898828s`.
- Focused cProfile: `laplacian_matrix` `0.229s / 8`; `_fnx.adjacency_default_order_index_arrays` `0.045s / 8`.
- Hyperfine process envelope: `884.4 ms +/- 121.4 ms`; confirm with 20 internal repeats `878.1 ms +/- 40.7 ms`.
- Golden digest stayed `bca361dbcc78a18bc70f73d2dec30cc09d245e30218842df631d2bd79c1a2306`.

## Delta

- Direct FNX mean: `0.04114515699620824s -> 0.020119644422569156s` (`2.05x`).
- Direct FNX median: `0.035806276500807144s -> 0.013879560006898828s` (`2.58x`).
- Native index helper profile: `0.223s -> 0.045s` over 8 calls (`4.96x`).
- Process hyperfine remains dominated by Python startup, graph construction, SciPy import, and host noise; it is recorded but not used as the isolated target-section signal.

## Score Gate

- Impact: 4
- Confidence: 4
- Effort: 1
- Score: `4 * 4 / 1 = 16.0`

Decision: keep and commit.
