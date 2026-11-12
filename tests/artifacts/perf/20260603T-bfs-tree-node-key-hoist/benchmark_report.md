# Benchmark Report: BFS tree node-key lookup hoist

## Baseline
- Direct FNX repeat=80 mean: `0.007188971197319915s`
- Direct NX repeat=80 mean: `0.004845346014553798s`
- Baseline residual ratio: `1.4837x`
- Hyperfine baseline mean: `603.5 ms +/- 21.4 ms`

## Candidate After
- Direct FNX repeat=80 mean: `0.007496119475399609s`
- Direct delta: regression, `0.958x` versus baseline
- Hyperfine after mean: `607.0 ms +/- 35.5 ms`
- Hyperfine delta: no improvement

## Restored
- Restored FNX repeat=80 mean: `0.00697327811139985s`
- Restored SHA matched baseline.

## Decision
Reject. Impact became `0`, so the final score is `0 * 4 / 1 = 0.0`, below the required `2.0` keep threshold.
