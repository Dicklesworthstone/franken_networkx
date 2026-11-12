# br-r37-c1-tlfqe Benchmark Report

Target: profile-backed `Graph.add_edges_from` residual on `plain_edges_int`
construction.

Lever kept: `fnx-classes::Graph::extend_edges_unrecorded` now reserves batch
capacity from the iterator lower bound and inserts endpoint nodes in one pass.
This removes the previous `contains_key` plus `get_index_of` double probe while
preserving the existing edge order, duplicate suppression, and self-loop
behavior.

The originally suggested Python validation-fusion path was rejected before this
commit because direct timing showed validation was not the real bottleneck.

## Baseline

- Release rebuild: `maturin_baseline.rch.log`
- Direct benchmark: `baseline_plain_edges_int.jsonl`
- FNX mean: `0.07464806899840298s`
- NetworkX mean: `0.028649601471932747s`
- FNX / NX: `2.6055534863734042`
- Construction digest: `74d9d20a476a21a81c3d7643eda931baea4788d9968cc125f6e30425842e990c`
- cProfile mean: `0.10609737071873886s`
- Native `Graph.add_edges_from`: `0.364s / 7 calls`
- Hyperfine: `442.2 ms +/- 38.2 ms`

## After

- Release rebuild: `maturin_after.rch.log`
- Direct benchmark: `after_plain_edges_int.jsonl`
- FNX mean: `0.05117460855175383s`
- NetworkX mean: `0.02109624938412498s`
- FNX / NX: `2.4257680889126645`
- Construction digest: `74d9d20a476a21a81c3d7643eda931baea4788d9968cc125f6e30425842e990c`
- cProfile mean: `0.0752418508719919s`
- Native `Graph.add_edges_from`: `0.226s / 7 calls`
- Hyperfine: `372.7 ms +/- 19.6 ms`

## Delta

- Direct benchmark speedup: `1.459x`
- cProfile mean speedup: `1.410x`
- Native frame speedup: `1.611x`
- Hyperfine speedup: `1.186x`
- Score: Impact `3` x Confidence `4` / Effort `2` = `6.0`

## Validation

- `rch exec -- cargo check -p fnx-classes --all-targets`
- `rch exec -- cargo fmt --package fnx-classes -- --check`
- `rch exec -- cargo clippy -p fnx-classes --all-targets -- -D warnings`
- `rch exec -- cargo test -p fnx-classes extend_edges`
- `rch exec -- cargo check -p fnx-python --features pyo3/abi3-py310 --all-targets`
- `ubs crates/fnx-classes/src/lib.rs`: 0 critical findings; broad warning
  categories remain in the file scan.

