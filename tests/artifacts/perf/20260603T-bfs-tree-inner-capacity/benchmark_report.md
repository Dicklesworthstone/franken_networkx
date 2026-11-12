# bfs_tree inner DiGraph capacity benchmark

Bead: `br-r37-c1-04z53.35`

## Baseline

- fnx direct repeat-50 mean: `0.006522759519284591s`.
- NetworkX direct repeat-50 mean: `0.004460272279102355s`.
- Baseline fnx/NetworkX ratio: `1.4624x`.
- Baseline golden SHA256: `5a16c0c6b529b4abf6a1e8e95a7b383d81f8b9f586357b010ec92697613cdc64`.
- Baseline hyperfine mean: `0.38590132196666665s`.
- Baseline hyperfine stddev: `0.020717349199476178s`.

## Candidate

- Candidate fnx direct repeat-50 mean: `0.006293302656849846s`.
- Candidate direct speedup: `1.0365x`.
- Candidate golden SHA256: `5a16c0c6b529b4abf6a1e8e95a7b383d81f8b9f586357b010ec92697613cdc64`.
- Candidate hyperfine mean: `0.3823539619866667s`.
- Candidate hyperfine stddev: `0.024161033926073466s`.
- Candidate hyperfine speedup: `1.0093x`.

## Score

- Impact: 1. Direct sample moved slightly, but hyperfine means differed by only
  `0.00354735998s` with overlapping variance.
- Confidence: 1. The process-level benchmark did not confirm a real win.
- Effort: 1. The code change was small.
- Opportunity score: `1 * 1 / 1 = 1.0`.

## Decision

Rejected. No source change was kept.
