# br-r37-c1-04z53.29 Benchmark Report

## Target

- Profile-backed bead: `br-r37-c1-04z53.29`
- Hot path: `ego_graph(Graph, 0, radius=2)` on BA(3000, 4, seed=42)
- Baseline profile: 9 `ego_graph` calls took 0.399s cumulative; wrapper `Graph.add_edges_from` took 0.215s cumulative and raw `Graph.add_edges_from` took 0.152s.
- Lever: for copied simple-Graph edges with empty edge data, append `(u, v)` instead of `(u, v, {})`, so the existing plain-edge `Graph.add_edges_from` path is used.

## Baseline

- Direct rch sample: `baseline_fnx.jsonl`
  - mean: `0.0394445046025794s`
  - median: `0.03812749098869972s`
  - golden digest: `a66fe1d2d36fe1f69a5966fab6d739d8b5b34ed0aae622b17565fbba8ce603d6`
- Hyperfine via rch: `hyperfine_baseline.json`
  - command: `env PYTHONPATH=python .venv/bin/python tests/artifacts/perf/20260603T-ego-graph-r2-current/bench_ego_graph_r2.py sample --impl fnx --n 3000 --m 4 --seed 42 --repeats 9`
  - mean: `0.760665895474286s`
  - median: `0.7610308347600001s`
  - stddev: `0.025115516030771206s`
- Profile via rch: `profile_baseline_fnx.txt`
  - total: `0.461s`
  - `ego_graph`: `0.399s` cumulative
  - wrapper `Graph.add_edges_from`: `0.215s` cumulative
  - raw `Graph.add_edges_from`: `0.152s` cumulative

## After

- Direct rch sample: `after_fnx.jsonl`
  - mean: `0.030322225463654224s`
  - median: `0.029418423015158623s`
  - golden digest: `a66fe1d2d36fe1f69a5966fab6d739d8b5b34ed0aae622b17565fbba8ce603d6`
- Hyperfine via rch: `hyperfine_after.json`
  - command: `env PYTHONPATH=python .venv/bin/python tests/artifacts/perf/20260603T-ego-graph-r2-current/bench_ego_graph_r2.py sample --impl fnx --n 3000 --m 4 --seed 42 --repeats 9`
  - mean: `0.6022390344942857s`
  - median: `0.59954171378s`
  - stddev: `0.02004953393447412s`
- Profile via rch: `profile_after_fnx.txt`
  - total: `0.369s`
  - `ego_graph`: `0.342s` cumulative
  - wrapper `Graph.add_edges_from`: `0.152s` cumulative
  - raw `Graph.add_edges_from`: `0.086s` cumulative

## Delta

- Hyperfine process mean: `0.760665895474286s -> 0.6022390344942857s`
  - speedup: `1.263x`
  - reduction: `20.83%`
- Direct sample mean: `0.0394445046025794s -> 0.030322225463654224s`
  - speedup: `1.301x`
  - reduction: `23.13%`
- Profile sample mean: `0.05125428688350237s -> 0.04096514966739859s`
  - speedup: `1.251x`
  - reduction: `20.07%`
- Raw `Graph.add_edges_from` profile line: `0.152s -> 0.086s`
  - speedup: `1.767x`
  - reduction: `43.42%`

## Score

- Impact: `2.5`
- Confidence: `4.0`
- Effort: `1.0`
- Score: `10.0`
- Verdict: keep. This exceeds the required `>= 2.0` threshold.
