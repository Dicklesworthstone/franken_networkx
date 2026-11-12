# ego_graph batch empty node copy benchmark

Bead: `br-r37-c1-04z53.36`

## Baseline

- fnx direct repeat-50 mean: `0.03508577799831983s`.
- NetworkX direct repeat-50 mean: `0.03066611245914828s`.
- Baseline fnx/NetworkX ratio: `1.1441x`.
- Baseline golden SHA256: `8195242bb15c80fa50c2ad2d1daf43699828f5dadf578d8ac6c22754dddc7849`.
- Baseline hyperfine mean: `0.4819253350133334s`.
- Baseline hyperfine stddev: `0.026764217864175186s`.

## Candidate

- Candidate fnx direct repeat-50 mean: `0.02620539966097567s`.
- Candidate direct speedup: `1.3389x`.
- Candidate golden SHA256: `8195242bb15c80fa50c2ad2d1daf43699828f5dadf578d8ac6c22754dddc7849`.
- Candidate hyperfine mean: `0.5640134540599999s`.
- Candidate hyperfine stddev: `0.1439717996405627s`.
- Candidate hyperfine confirm mean: `0.7067660573000001s`.
- Candidate hyperfine confirm stddev: `0.16108399585371455s`.

## Score

- Impact: 1. The operation sample was faster, but process-level runs regressed.
- Confidence: 1. Two hyperfine runs failed to confirm the win.
- Effort: 1. The code change was a small guarded branch.
- Opportunity score: `1 * 1 / 1 = 1.0`.

## Decision

Rejected. No source change was kept.
