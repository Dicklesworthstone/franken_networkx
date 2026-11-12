# br-r37-c1-2zudj: EdgeDataView length hint

## Target

Profile-backed target: `list(G.edges(data=True))` on a simple `Graph`.
Baseline cProfile showed `EdgeDataView._materialize()` called twice per
`list()` conversion because `list()` asks `__len__` for a length hint before
iterating.

## One Lever

For no-`nbunch` native graph edge views, `EdgeDataView.__len__` now returns the
current `graph.number_of_edges()` instead of materializing the edge list.
Iteration, containment, repr, string conversion, nbunch handling, and data
projection still resnapshot through `_materialize()`.

## Benchmark

Command:

```bash
rch exec -- hyperfine --warmup 2 --min-runs 20 \
  'python3 tests/artifacts/perf/20260605T-edgeview-materialize-2zudj/bench.py --module fnx --data true 4000 16000 30' \
  'python3 tests/artifacts/perf/20260605T-edgeview-materialize-2zudj/bench.py --module nx --data true 4000 16000 30'
```

Before:

- FNX: 4.058 s mean, 3.797 s median
- NetworkX: 1.229 s mean, 1.223 s median
- Gap: NetworkX 3.30x faster

After:

- FNX: 2.272 s mean, 2.293 s median
- NetworkX: 1.220 s mean, 1.218 s median
- Gap: NetworkX 1.86x faster
- FNX speedup: 1.79x by mean

## Profile Delta

- Before: `_materialize()` 546 calls, 3.258 s cumulative
- After: `_materialize()` 273 calls, 1.997 s cumulative

## Behavior Proof

- Focused pytest: `13 passed, 249 deselected`
- Golden proof: 6 cases, 0 mismatches
- Golden sha256: `ff7d8a98d99113812cd06202ae4d75aff092cdd491a2b6a664aff72a41ea539f`
- Ordering/tie-breaking: compared exact `list(G.edges(...))` order against NetworkX
- Floating point/RNG: not applicable; deterministic structural graph view path
- Attribute identity: verified `attrs is G[u][v]` parity for `data=True`
- Live view semantics: captured view before mutation, then checked length and iteration after mutation

## Gates

- `python3 -m py_compile ...`: pass
- `pytest tests/python/test_view_pickle_parity.py -q -k edge_data_view`: pass
- `rch exec -- cargo fmt -p fnx-python --check`: pass
- `rch exec -- cargo check -p fnx-python --all-targets`: pass
- `rch exec -- cargo clippy -p fnx-python --all-targets -- -D warnings`: pass
- `ubs <touched files>`: interrupted after setup-only output and no findings; monolithic Python scan hung

## Score

Impact 3.0 x Confidence 0.95 / Effort 1.0 = 2.85. Keep.
