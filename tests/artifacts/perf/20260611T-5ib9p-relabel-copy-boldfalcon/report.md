# br-r37-c1-5ib9p relabel_nodes(copy=True) empty-attr fast path

## Target

Residual sweep on current `main` found `relabel_nodes(G, {i: i + 1 for i in range(0, n, 5)}, copy=True)` on a sparse `Graph(n=1800)` slower than NetworkX while preserving the same output signature.

## Lever

Add a native simple-graph predicate, `graph_has_any_attrs`, and route exact `Graph` + empty node/edge attr copy relabels through bulk `add_nodes_from` and plain edge tuples. Attribute-bearing, multigraph, directed, callable mapping, and in-place relabel paths keep the existing implementation.

## Baseline

- Direct FNX best: `0.007247911999s`
- Direct FNX median: `0.008923494956s`
- Direct NetworkX best: `0.005068867002s`
- FNX vs NetworkX best ratio: `1.4299x` slower
- cProfile target loop: `1.281s` over 80 calls
- RCH-wrapped hyperfine mean: `0.3174593696s`

## Candidate

- Direct FNX best: `0.002658274025s`
- Direct FNX median: `0.002707347041s`
- Direct NetworkX best: `0.003187525901s`
- FNX vs NetworkX best ratio: `0.8340x`
- Direct FNX best speedup: `2.73x`
- Direct FNX median speedup: `3.30x`
- cProfile target loop: `0.350s` over 80 calls, `3.66x` faster
- RCH-wrapped hyperfine mean: `0.28743911072s`, `1.10x` faster

## Proof

- Target empty graph SHA unchanged and matches NetworkX: `fe7753d2efe9455d57f6f91f3845fc6b43d8a1b395b6e87a6aaa2d41170390b4`
- Small empty graph SHA unchanged and matches NetworkX: `ff5d8b4e1bee5eff868ef887b559020f6bbc726d4ff2296861a3743f1f77a185`
- Small attr no-collision graph SHA unchanged and matches NetworkX: `b95636f888a0fe34b7f0f3dca9b16efd3b6782ca1a0f85b5568b2098310e475b`
- Existing attr-collision FNX behavior SHA unchanged: `9e83de01bf6e4e4673aaa6976d0ef2c4d78df92b80d3e492214a80c98e2da00f`

Ordering is preserved by insertion-order node relabeling followed by graph edge-order replay. Tie-breaking is only collision insertion order. There is no floating-point or RNG surface in the optimized path.

## Gates

- `python3 -m py_compile python/franken_networkx/__init__.py tests/python/test_conversion.py tests/artifacts/perf/20260611T-5ib9p-relabel-copy-boldfalcon/harness_relabel_copy.py`
- `pytest tests/python/test_conversion.py -q`: `103 passed, 6 skipped`
- `cargo check -p fnx-python --all-targets --features pyo3/abi3-py310`: passed through `rch exec`
- `cargo clippy -p fnx-python --all-targets --features pyo3/abi3-py310 -- -D warnings -A clippy::needless-range-loop -A unused-must-use -A clippy::collapsible-if`: passed through `rch exec`
- `git diff --check`: passed
- `ubs` on the smaller touched files completed with pre-existing `test_conversion.py` security-test heuristics and broad `algorithms.rs` warning inventory; no lever-specific critical was identified.
- Bounded `timeout 180 ubs python/franken_networkx/__init__.py` timed out without emitted findings.

`cargo fmt -p fnx-python --check` remains blocked by pre-existing formatting drift in unrelated sections of `fnx-python`.

## Verdict

PRODUCTIVE / kept. Score `10.0` (`Impact 4 * Confidence 4 / Effort 1.6`).
