# perf(approx.average_clustering): lazy sampled adjacency cache

br-r37-c1-t105o

## Profile Target

The prior `20260609T-approx-avgclustering-native-cc` report left a residual:
large-N / small-trials calls were still slower than NetworkX because the FNX
route snapshotted the whole adjacency (`O(V+E)`) before sampling. Fresh baseline
confirmed the same shape at `n=2000, m=4, trials=1000, repeats=30`:

- FNX cProfile: 430,101 calls in 0.281s; 0.116s cumulative in
  `_native_adjacency_dict`.
- Hyperfine baseline: FNX `485.118548ms +/- 21.966842ms`; NetworkX
  `371.353906ms +/- 18.634131ms`.

## Lever

One lever: for plain safe-to-bypass FNX graphs when `trials <= len(G)`, keep
NetworkX's Schank-Wagner RNG order but cache only sampled neighbor rows:

1. Draw all `int(rng.random() * n)` trial indices before any `sample()` call,
   matching the previous implementation and NetworkX.
2. Use `_raw_neighbors_dispatch(G)` to materialize only rows touched by sampled
   centers or membership checks.
3. Cache row sets for the sampled membership check instead of calling the
   `has_edge` wrapper per trial.
4. Keep the previous full-adjacency snapshot path for compatibility views,
   directed rejection, multigraphs, and dense-trials cases.

## Isomorphism Proof

- RNG order is unchanged: all `random()` index draws occur before per-trial
  `sample()` calls.
- Neighbor order is unchanged: sampled rows come from the same raw graph
  neighbor order used by existing fast paths.
- Tie-breaking is unchanged: the sampled node list remains `list(G)`.
- Floating point is unchanged: the function still returns `triangles / trials`
  with the same integer numerator and denominator.
- Golden proof payload is byte-identical before and after:
  `42cab3f8d9d37a071d57646e94382e237d7372aab501a4a19e529c8f6a1a800c`.

## Timing

Same command, same worktree, same local package:

| case | mean | stddev |
| --- | ---: | ---: |
| FNX baseline | `485.118548ms` | `21.966842ms` |
| FNX after | `387.650354ms` | `16.400693ms` |
| NetworkX baseline run | `371.353906ms` | `18.634131ms` |
| NetworkX after run | `385.572868ms` | `24.975996ms` |

Self-speedup: `1.25x`. FNX moves from `1.31x` slower than NetworkX in the
baseline run to parity (`1.01x` slower, within noise) in the after run.

After cProfile: 545,915 calls in 0.211s. The full-adjacency snapshot vanished
from the hot list; remaining time is dominated by Python RNG sampling.

## Validation

- `rch exec -- python3 -m py_compile ...`: pass.
- `rch exec -- cargo check -p fnx-python --lib`: pass; emitted pre-existing
  `fnx-generators` unused-must-use warnings outside this change.
- Rebuilt extension via `rch exec -- maturin build --release --features pyo3/abi3-py310`
  and refreshed `python/franken_networkx/_fnx.abi3.so`.
- `rch exec -- env PYTHONPATH=python python3 -m pytest tests/python/test_approximation_signature_parity.py tests/python/test_approx_bipartite_parity.py -q`:
  36 passed.
- `git diff --check`: pass.
- `timeout 240 ubs <touched files>`: timed out with exit 124 while scanning the
  large top-level Python module; log contains only UBS startup text and no
  emitted findings.

## Score

Impact `2.5` (1.25x self-speedup and closes the vs-NetworkX residual to parity)
* Confidence `4.5` (golden SHA unchanged, focused parity tests, profile
matches target) / Effort `1.5` = `7.5`. Keep.
