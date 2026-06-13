# br-r37-c1-pyp75 - MultiDiGraph non_neighbors node-set cache

## Target

- Profile-backed residual: prior `20260608T-cijlm-nodekeys-tealspring` report identified directed `non_neighbors` as a remaining direct gap and recommended native set/list emission.
- Fresh baseline reproduced the `MultiDiGraph` gap on the rch path:
  - FNX direct median: `0.00003262016997905448s`
  - NetworkX direct median: `0.000022384956013411282s`
  - Ratio: `1.46x` slower than NetworkX.

## Lever

Cache a `PySet` of `MultiDiGraph` node display objects alongside the existing
`nodes_seq`-keyed tuple cache. `_native_node_key_set()` returns a copy of that
cached set, so `non_neighbors()` can keep Python's C-level set difference while
avoiding a tuple-to-set rebuild on every call.

Scope is exact `MultiDiGraph` with no private NetworkX storage. `DiGraph`,
`Graph`, `MultiGraph`, subclasses, views, and private-storage overrides retain
their existing paths.

## Behavior Proof

- Golden SHA before: `41779f04b5b574369e60d6a56b2258e53868bb2051aca1816a05aed5101a7315`
- Golden SHA after: `41779f04b5b574369e60d6a56b2258e53868bb2051aca1816a05aed5101a7315`
- `diff -u baseline_golden.json candidate_golden.json`: empty.
- Result digest unchanged:
  `0e51c9988dedcfd8140bb6489bf627e1481da73cf5241ee8b6efcff7dff2032b`
- Ordering/tie-breaking: public output is a Python `set`; harness sorts only for hashing.
- Floating point: none.
- RNG: none.
- Directed semantics: unchanged; `non_neighbors` still subtracts successors and the queried node.
- Missing-node behavior: unchanged `KeyError(node)` pre-check before the native cache route.
- Cache invalidation: cache key is the existing `nodes_seq`; node mutations bump `nodes_seq`.

## Benchmark

All direct-loop runs used `rch exec`, `n=1500`, `degree=3`, `node=0`,
`loops=500`, `repeats=15`.

| Case | Median | Mean | Stdev |
| --- | ---: | ---: | ---: |
| baseline FNX MultiDiGraph | `32.620 us` | `36.206 us` | `8.534 us` |
| candidate FNX MultiDiGraph | `22.777 us` | `23.461 us` | `1.574 us` |
| NetworkX MultiDiGraph | `22.385 us` | `24.346 us` | `7.220 us` |

Self-speedup: `1.43x` by median. Candidate is `1.02x` NetworkX median.

Profile check for 1000 calls:

- Baseline `non_neighbors`: `0.047s` cumulative.
- Candidate `non_neighbors`: `0.029s` cumulative.
- Hot-body profile speedup: `1.62x`.

Process-level hyperfine is recorded but startup/import dominated:

- Baseline FNX command mean: `281.6 ms +/- 6.6 ms`
- Candidate FNX command mean: `456.7 ms +/- 17.0 ms`

The keep/reject gate uses the direct-loop and profile artifacts because they
measure the profiled hot path rather than Python process startup.

## Validation

- `rch exec -- cargo check -p fnx-python --lib`: passed.
- `maturin develop --release --features pyo3/abi3-py310` via `rch exec`: passed.
- Focused pytest:
  `46 passed, 596 deselected`.
- `python -m py_compile python/franken_networkx/__init__.py .../non_neighbors_harness.py`: passed.
- `git diff --check`: passed.
- `cargo clippy -p fnx-python --lib -- -D warnings`: blocked by pre-existing
  `fnx-generators` unused-must-use warnings at lines `538`, `621`, `666`,
  `6218`, and `6758`.
- `rustfmt --edition 2024 --check crates/fnx-python/src/digraph.rs`: blocked by
  pre-existing formatting drift outside this lever around lines `4668`-`5780`.
- `ubs ...`: Rust scan completed; Python scanner hung and was terminated.

## Score

Impact `1.43` x Confidence `3` / Effort `1` = `4.29`. Kept.
