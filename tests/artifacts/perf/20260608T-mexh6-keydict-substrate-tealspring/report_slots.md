# br-r37-c1-mexh6: MultiGraph live keydict slotting

## Target

`to_dict_of_dicts` on `MultiGraph` / `MultiDiGraph` spends most of its time materializing transient `_LiveMultiEdgeDataView` dict-subclass wrappers for each observed `(u, v)` pair.

## Baseline

- Harness: `tests/artifacts/perf/20260608T-mexh6-keydict-substrate-tealspring/multigraph_keydict_harness.py`
- `MultiGraph` direct: `0.85062263708096s`, FNX/NX ratio `73.09803796281726`
- `MultiDiGraph` direct: `0.3846034350572154s`, FNX/NX ratio `33.19983614725262`
- Hyperfine `MultiGraph` mean: `1.7076729814s`
- Hyperfine `MultiDiGraph` mean: `1.04461565256s`
- Profile `MultiGraph`: `_LiveMultiEdgeDataView.__init__` `0.540s` cumulative
- Profile `MultiDiGraph`: `_LiveMultiEdgeDataView.__init__` `0.263s` cumulative

## Rejected Candidate

Per-graph caching of `_LiveMultiEdgeDataView` objects fixed the existing undirected keydict alias identity divergence (`MultiGraph` FNX SHA moved to NetworkX SHA `5a55bbcd4cb59516aeba251c246aff4bb85b1e13903cfd7c4f3648635b1e23ba`), but it regressed runtime:

- `MultiGraph` direct: `0.85062263708096s -> 1.1704032060224563s`
- `MultiDiGraph` direct: `0.3846034350572154s -> 0.5061054230900481s`

This branch was not kept.

## Kept Lever

Add `__slots__ = ("_graph", "_u", "_v")` to `_LiveMultiEdgeDataView`.

This removes the per-instance `__dict__` allocation while leaving all lookup, iteration, write rejection, row order, key order, and golden digest surfaces unchanged.

## After

- `MultiGraph` direct: `0.85062263708096s -> 0.4741967360023409s` (`1.794x`)
- `MultiDiGraph` direct: `0.3846034350572154s -> 0.2627881009830162s` (`1.464x`)
- Hyperfine `MultiGraph` mean: `1.7076729814s -> 1.3771469167s` (`1.240x`)
- Hyperfine `MultiDiGraph` mean: `1.04461565256s -> 0.8652263126000002s` (`1.207x`)
- Profile `MultiGraph`: `_LiveMultiEdgeDataView.__init__` `0.540s -> 0.308s`
- Profile `MultiDiGraph`: `_LiveMultiEdgeDataView.__init__` `0.263s -> 0.152s`

## Proof

- Slot proof SHA: `1cef3a7ef93d10e2a178b103bf5a0f26108a7f345d5c6a8b5f7bdaaba3dfd505`
- `MultiGraph` FNX SHA unchanged: `231583cedff594f62d823fb4b31b13b96ed668cfb49879e4509e99bd1aa417a5`
- `MultiDiGraph` FNX SHA unchanged and matches NetworkX: `f390ad0dd5b62afcea49a121448d11f13954103ea0bb8bc164092a25e38ae759`
- Ordering/tie-breaking surface: no algorithmic tie-break path; serialization order/digest unchanged for FNX.
- Floating point: N/A, attributes are serialized only.
- RNG: deterministic synthetic graph.

The known `MultiGraph` keydict alias identity gap remains unchanged (`alias_pairs=0` vs NetworkX `11970`), and is routed to child bead `br-r37-c1-rup1h`.

## Gates

- Focused pytest: `33 passed, 75 deselected`
- `python3 -m py_compile python/franken_networkx/__init__.py tests/artifacts/perf/20260608T-mexh6-keydict-substrate-tealspring/multigraph_keydict_harness.py` passed
- Current checkout proof replay: `current_proof.json`
  - `MultiGraph` FNX SHA unchanged: `231583cedff594f62d823fb4b31b13b96ed668cfb49879e4509e99bd1aa417a5`
  - `MultiDiGraph` FNX SHA still matches NetworkX: `f390ad0dd5b62afcea49a121448d11f13954103ea0bb8bc164092a25e38ae759`
  - Known undirected alias gap unchanged: `alias_pairs=0` vs NetworkX `11970`
- Current checkout timing replay: `current_timing.json`, `MultiGraph` ratio `31.657x` vs NetworkX over 20 repeats
- Focused conversion parity: `python3 -m pytest tests/python/test_conversion.py -q -k 'to_dict_of_dicts or multigraph_view or LiveMultiEdgeDataView'` passed, `10 passed, 98 deselected`
- Broad selector smoke: `python3 -m pytest tests/python -q -k 'to_dict_of_dicts'` passed, `1 passed, 22195 deselected`
- `cargo fmt -p fnx-python --check` passed
- `rch exec -- cargo check -p fnx-python --all-targets --features pyo3/abi3-py310` passed on worker `vmi1227854`
- `rch exec -- cargo clippy -p fnx-python --all-targets --features pyo3/abi3-py310 -- -D warnings` passed on worker `vmi1152480`
- `git diff --check` passed
- UBS on `multigraph_keydict_harness.py` and `report_slots.md` exited `0` with no critical/warning findings
- UBS including `python/franken_networkx/__init__.py` was interrupted after more than six minutes without emitting findings; this large-file timeout is covered by py_compile, focused pytest, proof SHA, RCH check/clippy, and diff-check

Score: `3.0` (`Impact 3 * Confidence 4 / Effort 4`). Keep.
