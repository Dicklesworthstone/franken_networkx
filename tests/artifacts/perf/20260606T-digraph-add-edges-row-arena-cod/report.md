# br-r37-c1-04z53.56 DiGraph Row-Staged Add Edges Report

## Target

- Bead: `br-r37-c1-04z53.56`
- Surface: attributed `DiGraph.add_edges_from` batch construction.
- Profile-backed hotspot after `br-r37-c1-blgry`: cProfile still showed native
  `_try_add_edges_from_batch` dominating at `2.284s` over 200 FNX builds in the
  prior closeout. Fresh baseline for this bead measured `2.957s` native time
  and hyperfine mean `0.5849869173s`.
- Lever: row-local directed staging arena. The Python batch path now sends the
  already-known new-node list and inner edge records to a prepared inner
  `DiGraph` commit method. The inner method inserts new nodes once, keeps edge
  map insertion and duplicate attr merges in global input order, then commits
  successor and predecessor row updates by touched row.

## Baseline

- Golden SHA:
  `c6f6227073dc924849e81ae552df913fcfaf278a522aae3abccdca2605eb6f48`
- Direct timing, `n=1500`, `edges=5217`, `loops=80`:
  - Baseline sample FNX median: `0.0229522670s`
  - Baseline repeat FNX median: `0.0132303665s`
  - Baseline repeat NetworkX median: `0.0046363725s`
  - Baseline repeat ratio: `2.8536x`
- Hyperfine:
  - Mean: `0.5849869173s`
  - Median: `0.5768756928s`
- cProfile, 200 FNX builds:
  - total: `2.981s`
  - native `_try_add_edges_from_batch`: `2.957s`

## Candidate Result

- Direct timing:
  - FNX median: `0.0121729030s`
  - NetworkX median: `0.0041926420s`
  - Ratio: `2.9034x`
- Hyperfine:
  - Mean: `0.5174077912s`
  - Median: `0.5237871634s`
- cProfile, 200 FNX builds:
  - total: `2.088s`
  - native `_try_add_edges_from_batch`: `2.069s`

## Proof

- `cargo fmt --check`: passed
- `cargo check -p fnx-python --all-targets --features pyo3/abi3-py310`: passed
  via rch
- `cargo test -p fnx-classes row_staged_attr_edges_preserve_orders_and_duplicate_merges`: passed via rch
- `cargo clippy -p fnx-python --all-targets --features pyo3/abi3-py310 -- -D warnings`: passed via rch
- Focused add_edges parity: `19 passed`
- `sha256sum -c golden_add_edges_batch.sha256`: passed
- Golden SHA unchanged:
  `c6f6227073dc924849e81ae552df913fcfaf278a522aae3abccdca2605eb6f48`

## Verdict

- Kept.
- Hyperfine mean improved `11.6%`.
- cProfile native `_try_add_edges_from_batch` improved `30.0%`.
- Direct FNX median improved `8.0%` against the repeat direct baseline.
- Score: Impact `3` x Confidence `5` / Effort `2` = `7.5`.

## Isomorphism Notes

- Ordering: edge map insertion and duplicate attr merges still process the input
  edge stream in order. Successor rows and predecessor rows are committed from
  row-local vectors that preserve the global filtered order within each row.
- Tie-breaking: no algorithmic tie policy changed.
- Floating-point: attr conversion remains the same `CgseValue` path; no FP math
  was introduced.
- RNG: harness seed remains `20260606`.
- Python mirrors: graph-owned mirror dicts remain separate from caller input
  dicts; duplicate edges update existing live mirrors in NetworkX order.

## Next Primitive

The residual direct ratio remains near `2.9x` on noisy direct samples even
though native cProfile improved materially. The next profile-backed primitive
should attack endpoint canonicalization and batch-local node identity caching:
deduplicate repeated plain int/float/string endpoint canonical strings within
the batch, carry canonical handles through edge collection, and preserve the
existing display-conflict fallback for int/float/string collisions. Target
ratio: `<=2.0x` vs NetworkX on this fixture.
