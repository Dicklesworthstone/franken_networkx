# Benchmark Report

## Target
`dag_longest_path(DiGraph)` on a deterministic 400-node DAG (`p=0.02`, seed `20260603`, repeat `500` for direct samples).

## Baseline
- FNX direct: `0.001064320371951908s` per call.
- NetworkX direct: `0.0009785389300086536s` per call.
- Hyperfine process envelope, 160 calls/run: `462.95975636ms +/- 25.03546602ms`.
- cProfile, 160 calls: `0.2588407860021107s`; visible residuals included Python `topological_sort` and `_native_in_edges_data_key`.

## After
- FNX direct: `0.0007000821719993837s` per call.
- NetworkX direct check: `0.0012248068380285985s` per call.
- Hyperfine process envelope, 160 calls/run: `430.37989512ms +/- 36.15129399ms`.
- cProfile, 160 calls: `0.1426455159962643s`; the separate Python `topological_sort` and `_native_in_edges_data_key` calls are gone from the hot path.

## Delta
- Direct FNX: `1.52x` faster.
- cProfile timed section: `1.81x` faster.
- Hyperfine process envelope: `1.08x` faster.
- Output payload SHA: unchanged at `76214d0b33d25b721eb1437d081b03fcf320e749ed72ceb521a87215d5ebbb7f`.

## Score
Impact 3 * Confidence 5 / Effort 2 = `7.5`; keep.
