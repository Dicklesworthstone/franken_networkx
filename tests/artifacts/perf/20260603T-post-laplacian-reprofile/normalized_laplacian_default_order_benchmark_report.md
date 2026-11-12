# br-r37-c1-u1de5 Benchmark Report

## Target

- Kernel: `franken_networkx.normalized_laplacian_matrix(G)` on exact `Graph` with `nodelist=None`.
- Fixture: deterministic `networkx.barabasi_albert_graph(8000, 4, seed=12345)` mirrored into `fnx.Graph`.
- Profile-backed hotspot: focused cProfile over 8 calls spent `0.549s` in `_fnx.adjacency_index_arrays`.

## Lever

For exact undirected `Graph` with default nodelist, route `normalized_laplacian_matrix` through the existing `_native_adjacency_default_order_index_arrays` helper instead of the generic nodelist-index helper.

## Baseline

- Sweep: FNX `0.04245995860255789s`; NetworkX `0.04090225760592148s`; ratio `1.038x`; digest matched.
- Focused direct FNX repeat-12 mean: `0.05293597716566486s`; median `0.04379087999404874s`.
- Focused cProfile: `normalized_laplacian_matrix` `1.103s / 8`; `_fnx.adjacency_index_arrays` `0.549s / 8`.
- Hyperfine process envelope: `1.061s +/- 0.069s`.

## After

- Direct FNX repeat-12 mean: `0.04371122541488148s`; median `0.02097199100535363s`.
- Direct FNX repeat-30 confirm mean: `0.01930127266581015s`; median `0.015994246496120468s`.
- Focused cProfile: `normalized_laplacian_matrix` `0.286s / 8`; `_fnx.adjacency_default_order_index_arrays` `0.060s / 8`.
- Hyperfine process envelope: `970.2 ms +/- 133.8 ms`.
- Golden digest stayed `aa810df87c3bc48287dcee99741e5a144bb8a4155d83a6d079520488b39769b8`.

## Delta

- Direct FNX median: `0.04379087999404874s -> 0.015994246496120468s` (`2.74x`).
- Direct FNX mean: `0.05293597716566486s -> 0.01930127266581015s` (`2.74x`).
- Native index helper profile: `0.549s -> 0.060s` over 8 calls (`9.15x`).
- Process hyperfine: `1.061s -> 970.2 ms` (`1.09x`); this command is still dominated by Python process startup, graph construction, SciPy import, and rch dispatch overhead.

## Score Gate

- Impact: 4
- Confidence: 4
- Effort: 1
- Score: `4 * 4 / 1 = 16.0`

Decision: keep and commit.
