# Benchmark report: quotient edge insertion

Bead: `br-r37-c1-04z53.40`

## Baseline

- Direct FNX mean, 3 samples: `0.0861229623357455s`
- NetworkX mean, 3 samples: `2.3246433133414635s`
- Hyperfine process mean: `0.48731108788000005s +/- 0.011577545167698782s`
- cProfile `quotient_graph`: `0.118s`
- cProfile `_add_default_undirected_bucketed_edges`: `0.074s`

## After

- Direct FNX mean, 3 samples: `0.08898841333575547s` (one outlier at `0.10636499201063998s`)
- Direct FNX confirm mean, 10 samples: `0.08136882939434145s`
- Hyperfine process mean, 5 runs: `0.4587408062800001s +/- 0.029629160443276355s`
- Hyperfine confirm mean, 15 runs: `0.47474024608000004s`; median `0.45820293988s`
- cProfile `quotient_graph`: `0.105s`
- cProfile `_add_default_undirected_bucketed_edges`: `0.067s`

## Decision

Kept. The direct confirm and cProfile both show a small but real improvement while preserving the golden digest. The hyperfine confirm is noisy, but its median remains aligned with the 5-run after mean and below the captured baseline median.

