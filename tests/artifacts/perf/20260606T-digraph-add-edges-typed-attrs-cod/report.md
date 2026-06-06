# br-r37-c1-04z53.59 Typed Scalar Attr Substrate Rejection

## Target

- Surface: attributed `DiGraph.add_edges_from` batch construction.
- Profile-backed residual: `_try_add_edges_from_batch` remains the dominant
  cProfile frame after the row-staged commit and descriptor-flag rejection.
- Candidate lever: strict fast path for the fixture's homogeneous scalar schema
  (`weight: float`, `label: str`, `flag: bool`, optional `dupe: int`) with
  generic fallback for every other dict shape/type.

## Baseline

- Direct timing, `n=1500`, `edges=5217`, `loops=80`:
  - FNX median: `0.010978006001096219s`
  - NetworkX median: `0.003995156032033265s`
  - Ratio: `2.7478290993078325x`
- Hyperfine mean: `0.74380139496s`
- Hyperfine median: `0.76182712806s`
- cProfile, 200 FNX builds:
  - native `_try_add_edges_from_batch`: `1.806s`

## Candidate Result

- Direct timing:
  - FNX median: `0.015887815010501072s`
  - NetworkX median: `0.005590957996901125s`
  - Ratio: `2.8416981525003657x`
- Direct timing repeat:
  - FNX median: `0.01972709849360399s`
  - NetworkX median: `0.006547252007294446s`
  - Ratio: `3.0130348536493736x`
- Hyperfine mean: `0.8834167414400002s`
- Hyperfine median: `0.8801228916400001s`
- cProfile, 200 FNX builds:
  - native `_try_add_edges_from_batch`: `3.718s`

## Proof

- Focused parity: `pytest tests/python/test_add_edges_attr_batch_parity.py -q`
  reported `15 passed`.
- Golden SHA unchanged:
  `c6f6227073dc924849e81ae552df913fcfaf278a522aae3abccdca2605eb6f48`
- `sha256sum -c golden_add_edges_batch.sha256`: passed.

## Isomorphism Notes

- Ordering: candidate only changed the attr conversion/mirror construction
  branch for exact schema dicts; edge stream, node order, successor order,
  predecessor order, and duplicate merge order were unchanged.
- Tie-breaking: no algorithm tie policy changed.
- Floating-point: float values were extracted from exact `PyFloat` into the
  same `CgseValue::Float` representation.
- RNG: unchanged; harness seed remains `20260606`.
- Fallback: every non-exact schema/type path stayed on the old generic
  converter and fail-closed incompatible-key check.

## Verdict

- Rejected.
- Direct FNX median regressed `0.010978006001096219s -> 0.01972709849360399s`.
- Hyperfine mean regressed `0.74380139496s -> 0.8834167414400002s`.
- cProfile native time regressed `1.806s -> 3.718s`.
- Score: Impact `0` x Confidence `5` / Effort `2` = `0.0`.
- Source change was removed; only this rejection artifact remains.

## Next Primitive

Stop tuning the attr converter. The next pass should replace eager Python mirror
materialization with a lazy ordered mirror-log substrate: store Rust `AttrMap`
plus a compact ordered Python key/value log during batch insertion, materialize
the graph-owned `PyDict` only on first edge-data observation or duplicate update,
and keep a generic fallback for non-scalar or incompatible attrs. Proof target:
final dict insertion order, duplicate merge order, key/value identity for visible
dicts, source-dict non-aliasing, live `get_edge_data` identity after first
observation, node/succ/pred ordering, FP/RNG invariants, and unchanged golden
SHA. Target ratio remains `<=2.0x` vs NetworkX on this fixture.
