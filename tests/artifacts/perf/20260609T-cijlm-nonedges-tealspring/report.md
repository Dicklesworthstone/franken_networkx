# br-r37-c1-cijlm residual closeout

## Target

Remaining `_native_node_keys` caller adoption after the landed directed
node-key binding and tuple cache.

## Baseline

- Harness: `harness_cijlm_nonedges.py`
- Proof command: `PYTHONHASHSEED=0 .venv/bin/python harness_cijlm_nonedges.py --mode proof --n 36`
- Timing command: `PYTHONHASHSEED=0 .venv/bin/python harness_cijlm_nonedges.py --mode time --n 420 --loops 5`
- Hyperfine: `PYTHONHASHSEED=0 hyperfine --warmup 2 --runs 7 ... --mode time --n 420 --loops 3`

## Evidence

- Directed `non_edges` proof SHA: `935328dffd63483f4639e097d4381b039767d50a009bd8892fb0fb1abb750a72`
- Proof matched NetworkX for `Graph`, `DiGraph`, `MultiGraph`, and `MultiDiGraph`.
- Timing SHA: `ca5d284200f3a75e3ef664d9c97f7974995ab3092c158cedf279f9e04247a204`
- Baseline directed medians:
  - `DiGraph`: FNX `0.0117996860s`, NetworkX `0.0083252540s`
  - `MultiDiGraph`: FNX `0.0112794110s`, NetworkX `0.0094486220s`
- Baseline hyperfine mean: `413.0 ms +/- 28.9 ms`
- Profile: `non_edges` generator/output dominated; `_native_node_keys` was already tuple-cached and below visible profile resolution.

## Candidate Gate

Best remaining one-lever candidate was replacing validation-only `set(G)`
checks with a native node-key helper in set-operation preconditions. Isolated
set equality improved, but public wrappers remained dominated by native result
construction, node insertion loops, or output generation.

Score: `Impact 1.0 * Confidence 3.0 / Effort 2.0 = 1.5`

## Verdict

Rejected/no-ship for remaining cijlm caller shims. The landed cijlm lever
(`3d55e5664`) already removed the high-value directed `non_neighbors` /
`selfloop_edges` adjacency materialization trap. The next correct primitive is
the deeper iterator substrate bead `br-r37-c1-29f85`, not more call-site shims.
