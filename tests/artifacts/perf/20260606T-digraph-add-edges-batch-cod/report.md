# br-r37-c1-35cg6 DiGraph Add-Edges Batch Report

## Target

- Bead: `br-r37-c1-35cg6`
- Surface: Python `DiGraph.add_edges_from`
- Profile-backed residual: after `remove_nodes_from` compaction, broad profiles
  were dominated by directed graph construction. The current baseline cProfile
  put 200 attributed-batch builds at `6.059s`, with `5.078s` inside native
  `DiGraph.add_edges_from`.
- One lever: route list/tuple batches of `(u, v)` and `(u, v, dict)` through a
  no-mutation collector and one Rust bulk edge insertion, preserving the
  existing per-edge loop for global attrs, bad tuples, non-dict thirds,
  unsupported endpoints, incompatible attrs, and mixed display-key conflicts.

## Alien Primitive

- Graveyard mapping: vectorized execution / morsel-style batching
  (`alien_cs_graveyard.md` §8.2) plus GraphBLAS-style sparse graph construction
  thinking (`alien_cs_graveyard.md` §10.5): batch endpoints and attributes into
  contiguous Rust vectors, then update adjacency storage once instead of taking
  the tuple-at-a-time mutation path.
- Safety boundary: safe Rust only; no external BLAS/LAPACK/C backends.

## Baseline

- Build: `rch exec -- env CARGO_TARGET_DIR=/data/projects/rch_target_franken_networkx_cod maturin develop --release --features pyo3/abi3-py310`
- Proof: `8` directed attributed-batch cases, `0` mismatches.
- Golden SHA: `c6f6227073dc924849e81ae552df913fcfaf278a522aae3abccdca2605eb6f48`
- Direct timing, `n=1500`, `edges=5217`, `loops=80`:
  - FNX median: `0.0231968855s`
  - NetworkX median: `0.0040279935s`
  - Ratio: `5.7589x`
- Hyperfine process timing:
  - FNX mean: `0.3851223819s`
  - NetworkX mean: `0.3483306259s`
- cProfile, 200 FNX builds:
  - total: `6.059s`
  - native `DiGraph.add_edges_from`: `5.078s`

## After

- Proof: `8` directed attributed-batch cases, `0` mismatches.
- Golden SHA: `c6f6227073dc924849e81ae552df913fcfaf278a522aae3abccdca2605eb6f48`
- Direct timing, same fixture:
  - FNX median: `0.0139258410s`
  - NetworkX median: `0.0044143360s`
  - Ratio: `3.1547x`
- Hyperfine process timing:
  - FNX mean: `0.3663212992s`
  - NetworkX mean: `0.3570627677s`
- cProfile, 200 FNX builds:
  - total: `2.664s`
  - native `DiGraph.add_edges_from`: `1.898s`

## Delta

- Direct FNX median: `0.0231968855s -> 0.0139258410s`, `1.67x` faster.
- cProfile total: `6.059s -> 2.664s`, `2.27x` faster.
- Native `DiGraph.add_edges_from`: `5.078s -> 1.898s`, `2.68x` faster.
- Hyperfine process mean: `0.3851223819s -> 0.3663212992s`, `1.05x` faster;
  this is Python startup dominated and not the primary scorer.
- Score: Impact `3` x Confidence `5` / Effort `2` = `7.5`; keep.

## Validation

- `cargo fmt -p fnx-python --check`: passed.
- `rch exec -- env CARGO_TARGET_DIR=/data/projects/rch_target_franken_networkx_cod cargo check -p fnx-python --features pyo3/abi3-py310 --all-targets`: passed.
- `rch exec -- env CARGO_TARGET_DIR=/data/projects/rch_target_franken_networkx_cod cargo clippy -p fnx-python --features pyo3/abi3-py310 --all-targets -- -D warnings`: passed.
- `rch exec -- .venv/bin/python -m pytest tests/python/test_add_edges_attr_batch_parity.py -q`: `13 passed`.
- `sha256sum -c golden_add_edges_batch.sha256`: passed.
- `ubs crates/fnx-python/src/digraph.rs tests/python/test_add_edges_attr_batch_parity.py tests/artifacts/perf/20260606T-digraph-add-edges-batch-cod/digraph_add_edges_batch_harness.py`: exit `0`; no critical issues.

## Reprofile Note

The residual is not a ceiling. The next deeper primitive is a directed
construction substrate that removes the remaining Python wrapper hash/len/
isinstance churn and PyDict mirror allocation cost: collect endpoint objects and
attrs into an arena-style batch descriptor, canonicalize once, and expose lazy
directed edge-attribute mirrors with `get_edge_data` parity preserved. Target:
drive the 5217-edge attributed DiGraph batch from `3.15x` vs NetworkX to
`<=1.5x` without altering order, duplicate merge semantics, or mixed-key
display behavior.
