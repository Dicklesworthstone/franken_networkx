# br-r37-c1-04z53.58 Attr Descriptor Flag Rejection

## Target

- Surface: attributed `DiGraph.add_edges_from` batch construction.
- Profile-backed residual: restored row-staged source still spends nearly all
  cProfile time in native `_try_add_edges_from_batch`.
- Candidate lever: carry the `__fnx_incompatible` sentinel flag out of
  `py_dict_to_attr_map_with_mirror` so the attr descriptor does not scan the
  converted `AttrMap` keys a second time.

## Baseline

- Direct timing, `n=1500`, `edges=5217`, `loops=80`:
  - FNX median: `0.00863380846567452s`
  - NetworkX median: `0.0032541039981879294s`
  - Ratio: `2.653206065473727x`
- Hyperfine mean: `0.4241101131000001s`
- Hyperfine median: `0.42624116440000004s`
- cProfile, 200 FNX builds:
  - native `_try_add_edges_from_batch`: `1.697s`

## Candidate Result

- Direct timing repeat:
  - FNX median: `0.012568845006171614s`
  - NetworkX median: `0.004415657982463017s`
  - Ratio: `2.8464262984337427x`
- Hyperfine mean: `0.62525667418s`
- Hyperfine median: `0.6375743217800001s`
- cProfile, 200 FNX builds:
  - native `_try_add_edges_from_batch`: `2.212s`

## Proof

- Golden proof command: `.venv/bin/python tests/artifacts/perf/20260606T-digraph-add-edges-batch-cod/digraph_add_edges_batch_harness.py proof --cases 8`
- Golden SHA unchanged:
  `c6f6227073dc924849e81ae552df913fcfaf278a522aae3abccdca2605eb6f48`
- `sha256sum -c golden_add_edges_batch.sha256`: passed.

## Isomorphism Notes

- Ordering: candidate did not change edge stream order, node order, successor
  row order, predecessor row order, or duplicate merge order.
- Tie-breaking: no algorithm tie policy changed.
- Floating-point: no arithmetic was introduced.
- RNG: unchanged; harness seed remains `20260606`.
- Error semantics: incompatible attr detection remained fail-closed, only the
  detection site moved into the conversion pass.

## Verdict

- Rejected.
- Direct FNX median regressed `0.00863380846567452s -> 0.012568845006171614s`.
- Hyperfine mean regressed `0.4241101131000001s -> 0.62525667418s`.
- cProfile native time regressed `1.697s -> 2.212s`.
- Score: Impact `0` x Confidence `5` / Effort `1` = `0.0`.
- Source change was removed; only this rejection artifact remains.

## Next Primitive

Do not continue one-scan attr descriptor micro-tuning. The next pass should
replace the representation, not the current loop: build a typed batched
edge-attribute substrate for the dominant scalar schema (`weight`, `label`,
`flag`, optional duplicate marker) with a generic fallback. The proof target is
the same NetworkX-visible final dict order, duplicate merge order, live dict
identity after first access, source-dict non-aliasing, and golden SHA. Target
ratio remains `<=2.0x` vs NetworkX on this fixture.
