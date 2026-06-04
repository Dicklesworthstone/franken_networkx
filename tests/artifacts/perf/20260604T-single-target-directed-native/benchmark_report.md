# Directed single-target shortest-path length native pass

Bead: br-r37-c1-cnndw

Target: `single_target_shortest_path_length(DiGraph, target)` on a deterministic
2500-node directed fanout graph. The old Python wrapper did reverse BFS in
Python; the lever routes directed calls to the native Rust predecessor BFS and
returns an ordered vector for Python dict insertion.

## Baseline

Command:

```text
RCH_ENV_ALLOWLIST=PYTHONPATH rch exec -- hyperfine --warmup 2 --runs 10 --export-json tests/artifacts/perf/20260604T-single-target-directed-native/baseline_old_hyperfine.json 'env PYTHONPATH=python .venv/bin/python tests/artifacts/perf/20260604T-single-target-directed-native/bench_single_target_directed.py --mode old --repeats 100 --n 2500 --fanout 4'
```

Result: 1.9715228509s mean, 0.1523342258s stddev per 100 calls.

Profile baseline: 2.3943154180s elapsed, 0.02394315418s per call.

## After

Command:

```text
RCH_ENV_ALLOWLIST=PYTHONPATH rch exec -- hyperfine --warmup 2 --runs 10 --export-json tests/artifacts/perf/20260604T-single-target-directed-native/after_fnx_hyperfine.json 'env PYTHONPATH=python .venv/bin/python tests/artifacts/perf/20260604T-single-target-directed-native/bench_single_target_directed.py --mode fnx --repeats 100 --n 2500 --fanout 4'
```

Result: 0.43296587184s mean, 0.04027169320s stddev per 100 calls.

Profile after: 0.08125397802s elapsed, 0.00081253978s per call.

NetworkX comparison: 0.43014455380s mean per 100 calls.

## Score

Hyperfine speedup: 4.55x. Profile per-call speedup: 29.47x.

Score: 25.0 = Impact 5 x Confidence 5 / Effort 1.

## Validation

- Golden output SHA: `6cf211ed2d04f16a43d51b6c6c909ead3ada96143f4b502ea42d78169b2872a8`
- Rust focused test: `cargo test -p fnx-algorithms single_target_shortest_path_length_directed -- --nocapture`
- Python focused parity: 13 tests passed in `pytest_single_target_expanded.rch.log`
- rch gates: fmt, check, clippy for `fnx-algorithms` and `fnx-python`
