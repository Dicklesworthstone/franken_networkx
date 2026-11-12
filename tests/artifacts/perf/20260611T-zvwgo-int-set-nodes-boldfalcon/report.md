# br-r37-c1-zvwgo exact int-set add_nodes_from fast path

## Target

Post-`br-r37-c1-5ib9p` residual profiling found `intersection(G, H)` still paying per-node Python insertion for `node_intersection`, a CPython `set` of integer nodes. The existing native `Graph.add_nodes_from` int bulk path handled `range`, `list`, and `tuple`, but exact `set` fell through to per-node `add_node`.

## Lever

Allow exact `set` inputs to use the existing atomic `_fast_add_int_nodes` path for exact integer elements. The native validator still rejects `bool`, non-int elements, and overflowing integers before mutating, so fallback behavior is unchanged. Set iteration order is preserved by iterating the same CPython set object once in the native path.

## Baseline

- `add_int_set` FNX best: `0.001810979098s`
- `add_int_set` FNX median: `0.001828012057s`
- `add_int_set` FNX vs NetworkX best ratio: `4.0622x` slower
- `intersection` FNX best: `0.010588353965s`
- `intersection` FNX median: `0.014264215948s`
- `intersection` FNX vs NetworkX best ratio: `1.3884x` slower
- cProfile combined loop: `1.266s`; `add_nodes_from` cumulative `0.660s`
- RCH-wrapped hyperfine mean: `0.30320092738s`

## Candidate

- `add_int_set` FNX best: `0.000408434076s`, `4.43x` faster
- `add_int_set` FNX median: `0.000418342068s`, `4.37x` faster
- `add_int_set` FNX vs NetworkX best ratio: `0.9039x`
- `intersection` FNX best: `0.008056979976s`, `1.31x` faster
- `intersection` FNX median: `0.008179111057s`, `1.74x` faster
- cProfile combined loop: `0.621s`, `2.04x` faster; `add_nodes_from` cumulative `0.078s`
- RCH-wrapped hyperfine mean: `0.28025249108s`, `1.08x` faster

## Proof

- `intersection` SHA unchanged and matches NetworkX: `a8ad08618e39d836fcdff54f962a7b4bfb8fe7c4b5942247ea9a0dbb0aaea13a`
- `add_int_set` SHA unchanged and matches NetworkX: `52ef146bc091b3df9713017f0f1193ee824105c83db64841bda43bdecbefb6d9`
- `add_bool_set_existing_behavior` SHA unchanged and matches NetworkX: `a11ce739b9a23ba4af38da1654957aba7c15d023e19dfde5003a0fb2f2dc430e`

Ordering is CPython set iteration order for both FNX and NetworkX. Tie behavior is first insertion for equal nodes. There is no floating-point or RNG surface.

## Gates

- `python3 -m py_compile python/franken_networkx/__init__.py tests/python/test_graph_utilities.py tests/artifacts/perf/20260611T-zvwgo-int-set-nodes-boldfalcon/harness_int_set_nodes.py`
- `pytest tests/python/test_graph_utilities.py -q`: `612 passed`
- Candidate proof replay against baseline SHA: passed
- `git diff --check`: passed
- `cargo check -p fnx-python --all-targets --features pyo3/abi3-py310`: passed via `rch` on `vmi1227854` with pre-existing `fnx-generators` warnings
- `cargo clippy -p fnx-python --all-targets --features pyo3/abi3-py310 -- -D warnings -A clippy::needless-range-loop -A unused-must-use -A clippy::collapsible-if`: passed via `rch` local fallback
- Artifact UBS on `harness_int_set_nodes.py` and `report.md`: `0` critical, `0` warnings
- Broad UBS on `tests/python/test_graph_utilities.py` reported pre-existing test-suite assert heuristics; no lever-specific finding was identified
- Bounded `timeout 180 ubs python/franken_networkx/__init__.py` timed out without emitted findings

## Verdict

PRODUCTIVE / kept. Score `8.0` (`Impact 3.2 * Confidence 4 / Effort 1.6`).
