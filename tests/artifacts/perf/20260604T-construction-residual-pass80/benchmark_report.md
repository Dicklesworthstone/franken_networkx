# br-r37-c1-fhdxg Benchmark Report

## Target

Profile-backed residual: `MultiGraph.add_edge(i, i + 1, key=str(i))` construction.

The fresh post-build rch sweep selected `multigraph_str_keys` as the top remaining construction gap with matching golden digest.

## Baseline

- Command: `rch exec -- env PYTHONPATH=python .venv/bin/python tests/artifacts/perf/20260603T-construction-string-key-current/bench_construction.py bench --case all --impl both --repeats 9`
- `multigraph_str_keys` FNX mean: `0.3918365926688744s`
- `multigraph_str_keys` NetworkX mean: `0.09069006932744135s`
- FNX / NetworkX ratio: `4.320611899127868x`
- Golden digest: `a316d777cf3e4070855b2fca932a4f8f993dee8bbacf6d430f95624dd04d41bf`
- Baseline cProfile mean: `0.5318472604267299s`
- Baseline hyperfine mean: `1.132s`

The first sweep in `current_construction_sweep.jsonl` was discarded as stale-extension evidence because the installed PyO3 module predated the relanded pass79 commit. `maturin_develop_current.rch.log` rebuilds the current extension; `current_construction_sweep_after_build.jsonl` is the valid baseline.

## After

- Command: `rch exec -- env PYTHONPATH=python .venv/bin/python tests/artifacts/perf/20260603T-construction-string-key-current/bench_construction.py bench --case multigraph_str_keys --impl both --repeats 15`
- `multigraph_str_keys` FNX mean: `0.29623204059898856s`
- `multigraph_str_keys` NetworkX mean: `0.09677888020329799s`
- FNX / NetworkX ratio: `3.06091618312498x`
- Golden digest: `a316d777cf3e4070855b2fca932a4f8f993dee8bbacf6d430f95624dd04d41bf`
- After cProfile mean: `0.3106229281402193s`
- After hyperfine mean: `0.8083s`

## Delta

- Direct construction mean: `0.3918365926688744s -> 0.29623204059898856s` (`1.32x`)
- cProfile construction mean: `0.5318472604267299s -> 0.3106229281402193s` (`1.71x`)
- Hyperfine process envelope: `1.132s -> 0.8083s` (`1.40x`)
- Golden digest: unchanged.

## Keep Score

- Impact: `3`
- Confidence: `5`
- Effort: `1`
- Score: `15.0`
- Verdict: keep.
