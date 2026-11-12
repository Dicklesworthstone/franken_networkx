# br-r37-c1-1pvsc: check_planarity Euler early return

## Target

Profile-backed target from `br-r37-c1-2mfuj`: `check_planarity(G, counterexample=False)` on a dense nonplanar native `Graph` spent most time converting to a temporary NetworkX graph and then calling NetworkX planarity, even though the observable result is only `(False, None)`.

## Lever

One lever kept: for exact simple `Graph`, `counterexample=False`, non-recursive calls, check Euler's loopless simple-graph bound before building a certificate graph. If `m > 3n - 6` and there are no self-loops, return `(False, None)` directly. All planar-under-bound graphs, self-loop graphs, recursive calls, non-`Graph` inputs, and `counterexample=True` calls still delegate to the previous NetworkX certificate path.

## rch Benchmark

Harness: `planarity_harness.py`, release `fnx-python` extension, `loops=20`.

| case | baseline mean | candidate mean | speedup | output sha256 |
| --- | ---: | ---: | ---: | --- |
| grid planar | 0.017576314998586896s | 0.016705767400708282s | 1.052x | `003cc7efd008f28e3445319bfe2dd971559df667ed9db28aa5355d5ceece3451` |
| random nonplanar | 0.007649017748917686s | 0.0005816945515107364s | 13.149x | `cf10a0acfc8dfa1af67c2f9f165ae9df9f141b97c63a597397504871cbe6d06e` |

Golden SHA unchanged:

`9777eb824e38b6e96da70eb7811aeca410ca45219857d55a04604ca68331e4b0`

Direct proof SHA:

`bdf21b4d645fe362b5e3b1fcc209808a03a82fa49fb0318b6392fca6ef723f84`

Score: `Impact 13.149 x Confidence 0.90 / Effort 2 = 5.92`.

## Isomorphism Proof

- Ordering and tie-breaking: unchanged on delegated paths; planar grid still produces byte-identical `PlanarEmbedding` serialization.
- Floating point and RNG: no floating-point math or RNG introduced; random graph fixture is built by the harness before the operation and its output SHA is unchanged.
- Counterexample semantics: `counterexample=True` is not fast-pathed and still returns a non-`None` certificate for K5.
- Self-loop semantics: self-loop graphs are not fast-pathed because the native helper rejects the Euler shortcut when self-loops exist.
- Golden output: `baseline_golden.json` and `candidate_golden.json` have identical SHA-256.

## Profile Shift

Baseline random profile: 36,034 calls, dominated by `_planarity_graph_for_certificate`, `_fnx_to_nx`, and NetworkX `check_planarity`.

Candidate random profile: 16 calls, dominated by the native `franken_networkx._fnx.planarity_euler_reject` helper.
