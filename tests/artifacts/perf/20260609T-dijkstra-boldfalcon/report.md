# br-r37-c1-04z53 Dijkstra all-pairs length pass

## Target

- Profile-backed hotspot: `all_pairs_dijkstra_path_length` raw binding.
- Baseline cProfile: `_fnx.all_pairs_dijkstra_path_length` consumed 0.063s of 0.104s total on the 96-node harness.
- Primitive: build the Dijkstra CSR/weight/intness arrays once per all-pairs call and return predecessor metadata instead of full path vectors for the length-only binding.

## Change

- Added `all_pairs_dijkstra_path_length_with_pred` and directed twin in `fnx-algorithms`.
- Switched the PyO3 all-pairs length binding to the predecessor-distance rows.
- Kept public ordering/tie behavior by using the existing finalized-order typed CSR kernel.
- Fixed a same-surface raw single-source integer emission bug: all-int finite integral distances now emit Python `int` through `i128`, avoiding `i64::MAX` saturation at `2^63`.
- Fixed one pre-existing `fnx-algorithms` clippy `collapsible_if` lint in the touched crate.

## Proof

- `after_proof.json`
  - graph SHA: `03a4a893de6779b33ebb361ccc63784fbfef0a3014bea7d5347fc677876996d1`
  - digraph SHA: `20c07f990cd4ce29b6a450fefbbf4e7c36a39016e5e43b8047075882376dba02`
  - both match NetworkX.
- Ordering: outer node insertion order, inner Dijkstra finalize order.
- Tie-breaking: existing typed CSR heap push sequence preserved.
- Floating point/RNG: deterministic arithmetic fixture; missing weights are integer default `1`; no RNG.

## Benchmarks

- 96-node in-process public FNX mean: `0.017156543s` -> `0.005505829s` = `3.12x`.
- 96-node raw binding mean: `0.012230628s` -> `0.004735373s` = `2.58x`.
- 384-node hyperfine command window:
  - parent FNX: `1.233196803s`
  - candidate FNX: `0.880473870s`
  - command-window speedup: `1.40x`
  - parent was `1.26x` slower than NetworkX; candidate is `1.19x` faster than NetworkX.
- cProfile raw binding share: `0.063s` -> `0.023s`; residual is now Python-side int coercion/reordering.

## Gates

- `rustfmt --edition 2024 --check crates/fnx-algorithms/src/lib.rs crates/fnx-python/src/algorithms.rs`: pass.
- `rch exec -- cargo check -p fnx-algorithms --all-targets`: pass.
- `rch exec -- cargo check -p fnx-python --all-targets --features pyo3/abi3-py310`: pass.
- `rch exec -- cargo clippy -p fnx-algorithms --all-targets -- -D warnings`: pass.
- `python -m pytest tests/python/test_shortest_path.py tests/python/test_all_pairs_dijkstra_inner_order_parity.py tests/python/test_all_pairs_dijkstra_outer_order_parity.py tests/python/test_more_all_pairs_outer_order_parity.py tests/python/test_dijkstra_finalize_order_parity.py tests/python/test_dijkstra_length_typed_cutoff.py -q`: `244 passed`.
- `ubs crates/fnx-algorithms/src/lib.rs crates/fnx-python/src/algorithms.rs tests/artifacts/perf/20260609T-dijkstra-boldfalcon/harness_all_pairs_length.py`: nonzero aggregate (`critical=1`, `warning=6745`, `info=2129`) from file-wide Rust inventory; Python harness had `critical=0`, `warning=0`. JSON artifacts: `ubs_report.json`, `ubs_output.json`.
- `cargo fmt --check`: blocked by pre-existing untouched formatting drift in `fnx-generators/src/lib.rs`, `fnx-python/src/digraph.rs`, `fnx-python/src/lib.rs`, and `fnx-python/src/readwrite.rs`.
- `cargo clippy -p fnx-python --all-targets --features pyo3/abi3-py310 -- -D warnings`: blocked by pre-existing `collapsible_if` warnings in `fnx-python/src/digraph.rs` and `fnx-python/src/lib.rs`, both exclusively reserved by TealSpring until `2026-06-09T06:04:09Z`.

## Score

- Impact: 3.0
- Confidence: 0.9
- Effort: 1.0
- Score: 2.7

## Next Residual

Profile now points at Python wrapper overhead, especially `_sp_coerce_dist_to_int` and `_reorder_by_distance`. The next disjoint pass should move all-int row emission/coercion into the raw all-pairs binding or eliminate the wrapper pass once `python/franken_networkx/__init__.py` is no longer reserved.
