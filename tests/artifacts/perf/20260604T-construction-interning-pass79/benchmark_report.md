# br-r37-c1-nxgph Benchmark Report

## Target

Profile-backed residual: `MultiGraph.add_edge(i, i + 1, key=i)` construction.

Alien primitive applied: cache-friendly fresh-pair insertion that bypasses generic edge-key resolution and repeated policy bookkeeping for the exact fresh explicit integer-key path. This is the bounded first slice of the integer-interned construction substrate requested by the bead.

## Baseline

- Command: `rch exec -- env PYTHONPATH=python .venv/bin/python tests/artifacts/perf/20260603T-construction-string-key-current/bench_construction.py bench --case all --impl both --repeats 7`
- `multigraph_int_keys` FNX mean: `0.3907069749963869s`
- `multigraph_int_keys` NetworkX mean: `0.0819025522838014s`
- FNX / NetworkX ratio: `4.77038827364676x`
- Golden digest: `6041eefb1e549a77af5c18a4e08ab1dc24e9df42e2e9ef094e810d35bedf58dc`
- Hyperfine mean: `0.86265378126s`
- Hyperfine median: `0.87149436366s`
- cProfile construction mean: `0.45804864820092916s`

## After

- Command: `rch exec -- env PYTHONPATH=python .venv/bin/python tests/artifacts/perf/20260603T-construction-string-key-current/bench_construction.py bench --case multigraph_int_keys --impl both --repeats 15`
- `multigraph_int_keys` FNX mean: `0.22853927953013528s`
- `multigraph_int_keys` NetworkX mean: `0.08501921366356933s`
- FNX / NetworkX ratio: `2.6880897820872716x`
- Golden digest: `6041eefb1e549a77af5c18a4e08ab1dc24e9df42e2e9ef094e810d35bedf58dc`
- Hyperfine mean: `0.6941681100399999s`
- Hyperfine median: `0.6970228740400001s`
- cProfile construction mean: `0.2935939242015593s`

## Delta

- Direct construction mean: `0.3907069749963869s -> 0.22853927953013528s` (`1.71x`)
- cProfile construction mean: `0.45804864820092916s -> 0.2935939242015593s` (`1.56x`)
- Hyperfine process envelope: `0.86265378126s -> 0.6941681100399999s` (`1.24x`)
- Golden digest: unchanged.

## Keep Score

- Impact: `4`
- Confidence: `5`
- Effort: `2`
- Score: `10.0`
- Verdict: keep.
