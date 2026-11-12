# Benchmark Report

Bead: `br-r37-c1-acuub`

Target: `DiGraph.edges()` no-data materialization on a deterministic graph with `1800` nodes and `9000` directed edges.

## Profile

`cProfile` on the baseline benchmark showed the active hot path in Python:

```text
61 calls to __init__.py:1320(__iter__)
61 calls to __init__.py:1313(_materialize), 1.078s cumulative
549061 calls to _FailFastEdgeIterator.__next__
109800 calls through AtlasView adjacency access
```

The bead's prior profile had already identified the same materialization-bound `edges()` gap after the staleness fix.

## Direct rch Benchmark

Command:

```text
RCH_ENV_ALLOWLIST=PYTHONPATH,VIRTUAL_ENV,PATH rch exec -- .venv/bin/python tests/artifacts/perf/20260603T-digraph-edges-native-order/bench_digraph_edges.py --mode bench --nodes 1800 --edges 9000 --seed 23 --samples 7 --iters 20 --warmup 3
```

Before:

```json
{"mean_s": 0.01650334310002758, "median_s": 0.01688883394963341, "min_s": 0.015020065600401722}
```

After:

```json
{"mean_s": 0.00968236315737678, "median_s": 0.009398456951021216, "min_s": 0.008843379600148183}
```

Direct mean speedup: `1.70x`.

## Hyperfine via rch

Command:

```text
RCH_ENV_ALLOWLIST=PYTHONPATH,VIRTUAL_ENV,PATH rch exec -- hyperfine --warmup 1 --runs 3 ".venv/bin/python tests/artifacts/perf/20260603T-digraph-edges-native-order/bench_digraph_edges.py --mode bench --nodes 1800 --edges 9000 --seed 23 --samples 1 --iters 20 --warmup 1"
```

Before:

```text
651.1 ms +/- 3.3 ms
```

After:

```text
504.8 ms +/- 26.2 ms
```

Process-level speedup: `1.29x`.

## Score

Impact `3.5` x confidence `4.0` / effort `2.0` = `7.0`.

Verdict: keep.
