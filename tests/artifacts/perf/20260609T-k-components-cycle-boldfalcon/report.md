# br-r37-c1-14zul - k_components simple-cycle lattice

## Target

After `br-r37-c1-lnrxj`, `k_components` still delegated simple cycle families to
NetworkX Moody-White cut enumeration. `cycle_graph(10)` showed a profile-backed
residual through `_call_networkx_for_parity`:

- Baseline profile: 1,056,370 calls in 0.338 s for one `cycle_graph(10)` call.
- Top cumulative path: `k_components` -> `_call_networkx_for_parity` ->
  NetworkX `k_components` -> `all_node_cuts` -> DAG antichains / flow calls.

## Lever

Add one exact fast path for strict `fnx.Graph` values where:

- node count is at least 3,
- edge count equals node count,
- self-loop count is zero,
- every node has degree 2.

That predicate certifies each connected component is a simple cycle. The
k-component lattice is therefore closed form: each connected component appears
once at `k=2` and once at `k=1`, preserving connected-component order.

## Proof

Harness: `harness_cycle_k_components.py proof`

- Baseline proof SHA256: `04a2d22b2338706fa5a32defcc511e2c960a53727b6982991dbe95f5b38e0392`
- After proof SHA256: `04a2d22b2338706fa5a32defcc511e2c960a53727b6982991dbe95f5b38e0392`
- Cases: `cycle4`, `cycle10`, disconnected `cycle4 + cycle5`, and a
  density-one all-degree-2 self-loop fixture that must delegate.
- Ordering/tie-breaking: dict keys remain `[2, 1]`; components retain
  connected-component order; output list/set shapes match NetworkX.
- Floating point: N/A.
- RNG: N/A.

## Benchmarks

All timings were run through `rch exec -- hyperfine`.

| Case | Before | After | Delta |
| --- | ---: | ---: | ---: |
| one `cycle_graph(10)` process | 410.7 ms +/- 35.0 ms | 285.0 ms +/- 26.8 ms | 1.44x faster |
| 20 calls/process, mean | 4.334 s +/- 3.791 s | 298.4 ms +/- 33.5 ms | 14.5x faster |
| 20 calls/process, median | 2.617 s | 287.9 ms | 9.1x faster |
| 20 calls/process, conservative min/max | 2.545 s min | 337.8 ms max | 7.5x faster |
| NetworkX comparator, 20 calls/process | 2.632 s +/- 0.027 s | 298.4 ms +/- 33.5 ms | 8.8x faster than upstream |

The pre-change repeated-call run had one noisy outlier, so the median and
min/max ratios are recorded alongside the mean. Even the conservative min/max
ratio clears the keep threshold.

## Gates

- `pytest tests/python/test_tree_kcomponents_assortativity_conformance.py tests/python/test_collection_container_type_parity.py -q`
  - `86 passed, 3 warnings`
  - warnings are existing assortativity NaN parity warnings in fnx/NetworkX.
- `python -m py_compile python/franken_networkx/__init__.py tests/python/test_tree_kcomponents_assortativity_conformance.py tests/artifacts/perf/20260609T-k-components-cycle-boldfalcon/harness_cycle_k_components.py`
  - pass
- `ubs tests/python/test_tree_kcomponents_assortativity_conformance.py tests/artifacts/perf/20260609T-k-components-cycle-boldfalcon/harness_cycle_k_components.py`
  - pass, no critical/warning findings
- `timeout 180s ubs python/franken_networkx/__init__.py`
  - timed out with no emitted findings; known scanner/runtime limitation on this large wrapper file
- `rch exec -- cargo check -p fnx-python --all-targets`
  - pass; existing `fnx-generators` unused-must-use warnings remain
- `cargo fmt -p fnx-python --check`
  - fails on pre-existing untouched Rust formatting drift in `crates/fnx-python/src/{algorithms.rs,digraph.rs,lib.rs,readwrite.rs}`
- `rch exec -- cargo clippy -p fnx-python --all-targets --no-deps -- -D warnings`
  - fails on pre-existing untouched `collapsible_if` lints in `digraph.rs` and `lib.rs`, plus existing `fnx-generators` warnings

## Score

Impact 5 x confidence 4 / effort 1 = 20. Keep.
