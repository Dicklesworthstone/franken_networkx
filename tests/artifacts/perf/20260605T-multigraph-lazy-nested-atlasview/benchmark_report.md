# br-r37-c1-f0zo8 Baseline Report

## Target

Current-head, release-built Python extension baseline for public
`MultiGraph` / `MultiDiGraph` nested adjacency access:

- `G[u]`
- `G[u][v]`

The workload is deterministic: source node `0`, `720` outgoing/incident
neighbors, and `16` parallel keyed edges per neighbor (`11,520` edges touching
the source). This pass records current behavior only; no source code was
changed.

## Commands

Release extension build:

```bash
rch exec -- maturin develop --release --features pyo3/abi3-py310 > tests/artifacts/perf/20260605T-multigraph-lazy-nested-atlasview/maturin_baseline_f0zo8.rch.log 2>&1
```

Direct in-process baselines:

```bash
python3 tests/artifacts/perf/20260605T-multigraph-lazy-nested-atlasview/multigraph_nested_atlasview_baseline.py benchmark --library fnx --graph multigraph --operation gu --loops 20 --samples 9 --output tests/artifacts/perf/20260605T-multigraph-lazy-nested-atlasview/baseline_fnx_multigraph_gu.json
python3 tests/artifacts/perf/20260605T-multigraph-lazy-nested-atlasview/multigraph_nested_atlasview_baseline.py benchmark --library fnx --graph multigraph --operation guv --loops 20 --samples 9 --output tests/artifacts/perf/20260605T-multigraph-lazy-nested-atlasview/baseline_fnx_multigraph_guv.json
python3 tests/artifacts/perf/20260605T-multigraph-lazy-nested-atlasview/multigraph_nested_atlasview_baseline.py benchmark --library fnx --graph multidigraph --operation gu --loops 20 --samples 9 --output tests/artifacts/perf/20260605T-multigraph-lazy-nested-atlasview/baseline_fnx_multidigraph_gu.json
python3 tests/artifacts/perf/20260605T-multigraph-lazy-nested-atlasview/multigraph_nested_atlasview_baseline.py benchmark --library fnx --graph multidigraph --operation guv --loops 20 --samples 9 --output tests/artifacts/perf/20260605T-multigraph-lazy-nested-atlasview/baseline_fnx_multidigraph_guv.json
python3 tests/artifacts/perf/20260605T-multigraph-lazy-nested-atlasview/multigraph_nested_atlasview_baseline.py benchmark --library nx --graph multigraph --operation gu --loops 200000 --samples 9 --output tests/artifacts/perf/20260605T-multigraph-lazy-nested-atlasview/baseline_nx_multigraph_gu.json
python3 tests/artifacts/perf/20260605T-multigraph-lazy-nested-atlasview/multigraph_nested_atlasview_baseline.py benchmark --library nx --graph multigraph --operation guv --loops 200000 --samples 9 --output tests/artifacts/perf/20260605T-multigraph-lazy-nested-atlasview/baseline_nx_multigraph_guv.json
python3 tests/artifacts/perf/20260605T-multigraph-lazy-nested-atlasview/multigraph_nested_atlasview_baseline.py benchmark --library nx --graph multidigraph --operation gu --loops 200000 --samples 9 --output tests/artifacts/perf/20260605T-multigraph-lazy-nested-atlasview/baseline_nx_multidigraph_gu.json
python3 tests/artifacts/perf/20260605T-multigraph-lazy-nested-atlasview/multigraph_nested_atlasview_baseline.py benchmark --library nx --graph multidigraph --operation guv --loops 200000 --samples 9 --output tests/artifacts/perf/20260605T-multigraph-lazy-nested-atlasview/baseline_nx_multidigraph_guv.json
```

cProfile baselines:

```bash
python3 tests/artifacts/perf/20260605T-multigraph-lazy-nested-atlasview/multigraph_nested_atlasview_baseline.py profile --library fnx --graph multigraph --operation gu --loops 20 --limit 40 > tests/artifacts/perf/20260605T-multigraph-lazy-nested-atlasview/profile_fnx_multigraph_gu.txt
python3 tests/artifacts/perf/20260605T-multigraph-lazy-nested-atlasview/multigraph_nested_atlasview_baseline.py profile --library fnx --graph multigraph --operation guv --loops 20 --limit 40 > tests/artifacts/perf/20260605T-multigraph-lazy-nested-atlasview/profile_fnx_multigraph_guv.txt
python3 tests/artifacts/perf/20260605T-multigraph-lazy-nested-atlasview/multigraph_nested_atlasview_baseline.py profile --library fnx --graph multidigraph --operation gu --loops 20 --limit 40 > tests/artifacts/perf/20260605T-multigraph-lazy-nested-atlasview/profile_fnx_multidigraph_gu.txt
python3 tests/artifacts/perf/20260605T-multigraph-lazy-nested-atlasview/multigraph_nested_atlasview_baseline.py profile --library fnx --graph multidigraph --operation guv --loops 20 --limit 40 > tests/artifacts/perf/20260605T-multigraph-lazy-nested-atlasview/profile_fnx_multidigraph_guv.txt
```

Hyperfine process envelope:

```bash
hyperfine --warmup 2 --runs 7 --export-json tests/artifacts/perf/20260605T-multigraph-lazy-nested-atlasview/baseline_hyperfine_f0zo8_valid.json 'python3 tests/artifacts/perf/20260605T-multigraph-lazy-nested-atlasview/multigraph_nested_atlasview_baseline.py benchmark --library fnx --graph multigraph --operation gu --loops 10 --samples 3 > /dev/null' 'python3 tests/artifacts/perf/20260605T-multigraph-lazy-nested-atlasview/multigraph_nested_atlasview_baseline.py benchmark --library fnx --graph multigraph --operation guv --loops 10 --samples 3 > /dev/null' 'python3 tests/artifacts/perf/20260605T-multigraph-lazy-nested-atlasview/multigraph_nested_atlasview_baseline.py benchmark --library fnx --graph multidigraph --operation gu --loops 10 --samples 3 > /dev/null' 'python3 tests/artifacts/perf/20260605T-multigraph-lazy-nested-atlasview/multigraph_nested_atlasview_baseline.py benchmark --library fnx --graph multidigraph --operation guv --loops 10 --samples 3 > /dev/null' 'python3 tests/artifacts/perf/20260605T-multigraph-lazy-nested-atlasview/multigraph_nested_atlasview_baseline.py benchmark --library nx --graph multigraph --operation gu --loops 10 --samples 3 > /dev/null' 'python3 tests/artifacts/perf/20260605T-multigraph-lazy-nested-atlasview/multigraph_nested_atlasview_baseline.py benchmark --library nx --graph multigraph --operation guv --loops 10 --samples 3 > /dev/null' 'python3 tests/artifacts/perf/20260605T-multigraph-lazy-nested-atlasview/multigraph_nested_atlasview_baseline.py benchmark --library nx --graph multidigraph --operation gu --loops 10 --samples 3 > /dev/null' 'python3 tests/artifacts/perf/20260605T-multigraph-lazy-nested-atlasview/multigraph_nested_atlasview_baseline.py benchmark --library nx --graph multidigraph --operation guv --loops 10 --samples 3 > /dev/null' > tests/artifacts/perf/20260605T-multigraph-lazy-nested-atlasview/baseline_hyperfine_f0zo8_valid.stdout 2> tests/artifacts/perf/20260605T-multigraph-lazy-nested-atlasview/baseline_hyperfine_f0zo8_valid.stderr
```

Golden capture:

```bash
python3 tests/artifacts/perf/20260605T-multigraph-lazy-nested-atlasview/multigraph_nested_atlasview_baseline.py golden --output tests/artifacts/perf/20260605T-multigraph-lazy-nested-atlasview/golden_multigraph_nested_atlasview_f0zo8.json
```

## Direct Baseline

Mean milliseconds per public operation:

| Graph | Operation | FNX ms/op | NetworkX ms/op | FNX / NetworkX |
|---|---:|---:|---:|---:|
| MultiGraph | `G[u]` | 22.375645 | 0.000291 | 76793.90x |
| MultiGraph | `G[u][v]` | 42.194599 | 0.000419 | 100666.58x |
| MultiDiGraph | `G[u]` | 8.833513 | 0.000300 | 29482.38x |
| MultiDiGraph | `G[u][v]` | 19.306632 | 0.000441 | 43757.48x |

## Hyperfine Baseline

Process envelope for the same harness (`10` loops x `3` samples inside each
process):

| Graph | Operation | Library | Mean |
|---|---:|---|---:|
| MultiGraph | `G[u]` | FNX | 959.3 ms +/- 73.0 ms |
| MultiGraph | `G[u][v]` | FNX | 1.432 s +/- 0.168 s |
| MultiDiGraph | `G[u]` | FNX | 624.5 ms +/- 50.1 ms |
| MultiDiGraph | `G[u][v]` | FNX | 776.2 ms +/- 105.4 ms |
| MultiGraph | `G[u]` | NetworkX | 385.5 ms +/- 79.2 ms |
| MultiGraph | `G[u][v]` | NetworkX | 374.9 ms +/- 53.8 ms |
| MultiDiGraph | `G[u]` | NetworkX | 364.5 ms +/- 65.4 ms |
| MultiDiGraph | `G[u][v]` | NetworkX | 393.4 ms +/- 32.6 ms |

## Profile Findings

The FNX public view path is dominated by the eager saved adjacency descriptor
behind `_atlas`:

- MultiGraph `G[u]`: `0.590 s` over `20` accesses; `_multigraph_adj_view`
  descriptor lambda at `python/franken_networkx/__init__.py:1279` accounts for
  `0.585 s`.
- MultiGraph `G[u][v]`: `0.615 s` over `20` accesses; the same eager descriptor
  accounts for `0.606 s`, with additional inner `AtlasView` materialization.
- MultiDiGraph `G[u]`: `0.214 s` over `20` accesses; `_multidigraph_adj_view`
  descriptor lambda at `python/franken_networkx/__init__.py:1298` accounts for
  `0.211 s`.
- MultiDiGraph `G[u][v]`: `0.644 s` over `20` accesses; the directed eager
  descriptor accounts for `0.633 s`, again with additional inner lookup work.

## Notes

- The baseline release build log contains the old `private_interfaces` warning
  for `DiAtlasView::new` / `AdjKind`. The after lever tightens that constructor
  visibility, so the `fnx-python` check no longer reports it.
- The first hyperfine export path, `baseline_hyperfine_f0zo8.json`, is a
  superseded malformed export because an existing longer file left stale trailing
  JSON. It is retained only for audit. Use `baseline_hyperfine_f0zo8_valid.json`.

## After Lever

Implemented one structural lever: exact `MultiGraph` and `MultiDiGraph`
`G[u]` now return the existing Python `AdjacencyView` wrapper backed by a native
lazy row object. `G[u][v]` returns the existing Python `AtlasView` wrapper backed
by a native lazy edge-key mapping. The full `{neighbor: {key: attrs}}` dict is
materialized only for Mapping operations that require materialization.

Release extension build:

```bash
rch exec -- maturin develop --release --features pyo3/abi3-py310 > tests/artifacts/perf/20260605T-multigraph-lazy-nested-atlasview/maturin_after_tealspring.rch.log 2>&1
```

Direct after measurements used the same workload shape as baseline: source node
`0`, `720` neighbors, and `16` parallel edges per neighbor.

| Graph | Operation | Before FNX ms/op | After FNX ms/op | Speedup |
|---|---:|---:|---:|---:|
| MultiGraph | `G[u]` | 22.375645 | 0.001518 | 14738.01x |
| MultiGraph | `G[u][v]` | 42.194599 | 0.001746 | 24164.75x |
| MultiDiGraph | `G[u]` | 8.833513 | 0.001504 | 5872.02x |
| MultiDiGraph | `G[u][v]` | 19.306632 | 0.001807 | 10681.46x |

Hyperfine process-envelope after measurements include interpreter startup and
graph construction, so they show the whole harness effect rather than only the
hot access loop:

| Graph | Operation | Before mean | After mean | Speedup |
|---|---:|---:|---:|---:|
| MultiGraph | `G[u]` | 959.3 ms | 446.6 ms | 2.15x |
| MultiGraph | `G[u][v]` | 1.432 s | 414.2 ms | 3.46x |
| MultiDiGraph | `G[u]` | 624.5 ms | 406.7 ms | 1.54x |
| MultiDiGraph | `G[u][v]` | 776.2 ms | 418.6 ms | 1.85x |

After re-profile (`200000` point lookups) shows the eager full-adjacency
descriptor path is gone. The residual is now Python wrapper/lambda overhead plus
native row calls:

- MultiGraph `G[u][v]`: `1.023 s`; hottest public wrapper is
  `AdjacencyView.__getitem__` / `_multigraph_getitem_from_native_row`;
  `_native_adjacency_row` accounts for `0.124 s` over `600000` calls.
- MultiDiGraph `G[u][v]`: `1.019 s`; hottest public wrapper is
  `AdjacencyView.__getitem__` / `_multidigraph_getitem_from_native_row`;
  `_native_successor_row` accounts for `0.124 s` over `600000` calls.

Score: Impact `5` x Confidence `5` / Effort `2` = `12.5`, keep.

## After Validation

- `rch exec -- cargo check -p fnx-python --features pyo3/abi3-py310 --all-targets`
  passed.
- `rch exec -- cargo clippy -p fnx-python --features pyo3/abi3-py310 --all-targets --no-deps -- -D warnings`
  passed. The dependency-inclusive clippy invocation is blocked by pre-existing
  `fnx-classes` dead-code warnings in `rebuild_adj_indices` and
  `rebuild_edge_index_endpoints`.
- `cargo fmt -p fnx-python --check` passed.
- `python3 -m pytest tests/python/test_attribute_access_parity.py -q` passed
  (`143 passed`).
- Golden parity harness passed; `after_golden_f0zo8.jsonl` SHA-256:
  `e2e47e39c2f5b5656a6a6aa171e9666d63cd3f46911cc7318164e15b0516f06f`.
- UBS split scans: Rust binding files exited `0` with no critical findings
  (`ubs_rust_after_tealspring.log`); artifact Python scripts exited `0` with no
  warning findings (`ubs_artifact_python_after_tealspring.log`). The isolated
  monolithic `python/franken_networkx/__init__.py` UBS scan hung past 90 seconds
  and was terminated with its partial log preserved.

## Final TealSpring Verification

After removing the unused eager helper methods and rebuilding the release
extension, direct final means on the same `720` neighbor / `16` key workload:

| Graph | Operation | Before FNX ms/op | Final FNX ms/op | Speedup |
|---|---:|---:|---:|---:|
| MultiGraph | `G[u]` | 22.375645 | 0.001849 | 12102.98x |
| MultiGraph | `G[u][v]` | 42.194599 | 0.002160 | 19537.30x |
| MultiDiGraph | `G[u]` | 8.833513 | 0.002223 | 3973.21x |
| MultiDiGraph | `G[u][v]` | 19.306632 | 0.002208 | 8742.36x |

Final validation:

- `cargo fmt -p fnx-python --check` passed.
- `rch exec -- cargo check -p fnx-python --features pyo3/abi3-py310 --all-targets`
  passed.
- `rch exec -- cargo clippy -p fnx-python --features pyo3/abi3-py310 --all-targets --no-deps -- -D warnings`
  passed.
- `rch exec -- maturin develop --release --features pyo3/abi3-py310` passed.
- `python3 -m pytest tests/python/test_attribute_access_parity.py -q` passed
  (`143 passed`).
- `sha256sum -c final_artifact_sha256_tealspring.txt` passed.
