# br-r37-c1-qtb9w DiGraph Add-Edges Descriptor Report

## Target

- Bead: `br-r37-c1-qtb9w`
- Surface: Python `DiGraph.add_edges_from` compatibility wrapper after the
  native directed batch-ingest lever from `br-r37-c1-35cg6`.
- Profile-backed hotspot: cProfile showed `4,175,001` Python calls over 200
  builds, including `2,086,800` `hash` calls, `1,043,600` `len` calls, and
  `1,043,800` `isinstance` calls inside the wrapper before the Rust batch path.
- One lever: expose a DiGraph-only no-fallback native batch probe and let the
  Python wrapper return immediately only when that probe accepts and mutates the
  whole list/tuple batch. Unsupported batches still fall through to the existing
  Python parity scanner.

## Alien Primitive

- Graveyard mapping: vectorized execution / morsel batching
  (`alien_cs_graveyard.md` 8.2) plus region-style batch descriptors
  (`alien_cs_graveyard.md` 5.10). The change treats the edge list as a typed
  batch descriptor validated by Rust once, rather than as Python tuple-at-a-time
  control flow.
- Safety boundary: safe Rust only; no external native graph or BLAS backend.

## Baseline

- Build: `rch exec -- env CARGO_TARGET_DIR=/data/projects/rch_target_franken_networkx_cod .venv/bin/maturin develop --release --features pyo3/abi3-py310`
- Proof: `8` directed attributed-batch cases, `0` mismatches.
- Golden SHA: `c6f6227073dc924849e81ae552df913fcfaf278a522aae3abccdca2605eb6f48`
- Direct timing, `n=1500`, `edges=5217`, `loops=80`:
  - FNX median: `0.0125015620s`
  - NetworkX median: `0.0042252025s`
  - Ratio: `2.9588x`
- Hyperfine process timing:
  - Mean: `0.5155636768s`
  - Median: `0.5224527236s`
- cProfile, 200 FNX builds:
  - total: `2.700s`
  - Python calls: `4,175,001`
  - wrapper self time: `0.492s`
  - native `DiGraph.add_edges_from`: `1.928s`

## After

- Proof: `8` directed attributed-batch cases, `0` mismatches.
- Golden SHA: `c6f6227073dc924849e81ae552df913fcfaf278a522aae3abccdca2605eb6f48`
- Direct timing repeat, same fixture:
  - FNX median: `0.0118062505s`
  - NetworkX median: `0.0040573530s`
  - Ratio: `2.9098x`
- Hyperfine process timing:
  - Mean: `0.4894449076s`
  - Median: `0.4729535763s`
- cProfile, 200 FNX builds:
  - total: `2.314s`
  - Python calls: `1,401`
  - wrapper self time: `0.025s`
  - native `_try_add_edges_from_batch`: `2.284s`

## Delta

- Direct FNX median: `0.0125015620s -> 0.0118062505s`, `1.06x` faster.
- Hyperfine mean: `0.5155636768s -> 0.4894449076s`, `1.05x` faster.
- cProfile total: `2.700s -> 2.314s`, `1.17x` faster.
- Python call count: `4,175,001 -> 1,401`, removing the wrapper
  `hash`/`len`/`isinstance` loop from the accepted DiGraph batch path.
- Score: Impact `2` x Confidence `4` / Effort `2` = `4.0`; keep.

## Isomorphism Proof

- Ordering preserved: the accepted fast path uses the same Rust
  `collect_*_edge_batch` and `add_*_edge_batch` order as the prior native batch
  path; unsupported batches take the unchanged Python scanner.
- Tie-breaking unchanged: no graph algorithm tie policy changes; duplicate
  edge attribute merges still occur in input order with last write winning.
- Floating-point: unchanged; attrs are copied through the same `AttrMap`
  conversion as before.
- RNG seeds: unchanged; harness seed remains `20260606`.
- Golden outputs: `sha256sum -c golden_add_edges_batch.sha256` passed.

## Validation

- `cargo fmt -p fnx-python --check`: passed.
- `rch exec -- .venv/bin/python -m pytest tests/python/test_add_edges_attr_batch_parity.py -q`: `15 passed`.
- `rch exec -- env CARGO_TARGET_DIR=/data/projects/rch_target_franken_networkx_cod cargo check -p fnx-python --features pyo3/abi3-py310 --all-targets`: passed.
- `rch exec -- env CARGO_TARGET_DIR=/data/projects/rch_target_franken_networkx_cod cargo clippy -p fnx-python --features pyo3/abi3-py310 --all-targets -- -D warnings`: passed.
- `sha256sum -c golden_add_edges_batch.sha256`: passed.
- `ubs crates/fnx-python/src/digraph.rs tests/python/test_add_edges_attr_batch_parity.py tests/artifacts/perf/20260606T-digraph-add-edges-descriptor-cod/report.md`: exit `0`; no critical findings.
- `timeout 120s ubs python/franken_networkx/__init__.py`: timed out in the Python analyzer on this large wrapper file; the changed wrapper path was still exercised by import, golden proof, focused pytest, cProfile, and hyperfine.

## Reprofile Note

The residual shifted from Python wrapper validation to the native batch
collector and live PyDict mirror creation. The next primitive to attack is a
deeper directed construction substrate: collect endpoint descriptors and edge
attribute mirrors in an arena-backed batch, then commit both inner adjacency and
Python mirror cells with fewer per-edge map probes while preserving
`get_edge_data`, successor/predecessor display keys, duplicate merge order, and
fallback-on-error semantics.
