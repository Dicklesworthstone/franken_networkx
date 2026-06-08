# br-r37-c1-57dlh Report

## Target

Profile-backed bead: `fnx.find_cycle(DiGraph 1500n/9000e)` delegated to
NetworkX, paying full graph conversion before an early-exit cycle search.

## Lever

One lever: mirror NetworkX `edge_dfs` plus `find_cycle` backtracking in
`python/franken_networkx/__init__.py` and call it directly from `find_cycle`.
The native `_raw_find_cycle` remains unused because its DFS discipline returns a
different valid cycle than NetworkX on documented directed cases.

## Benchmark

Same fixture for all rows: deterministic `DiGraph` with 1500 nodes, 9000 edges,
and an early 3-cycle. `fnx-old` reconstructs the previous fallback by calling
`_call_networkx_for_parity("find_cycle", graph)`.

| Command | Mean |
| --- | ---: |
| `bench_find_cycle.py fnx-old 30` | 1.6160159463 s |
| `bench_find_cycle.py fnx 30` | 0.3259452679 s |
| `bench_find_cycle.py nx 30` | 0.3280854181 s |

End-to-end speedup over the previous fallback: `4.96x`.

Single-call internal timer on the same fixture:

| Mode | Elapsed |
| --- | ---: |
| `fnx-old 1` | 43.452898 ms |
| `fnx 1` | 0.447548 ms |
| `nx 1` | 0.500017 ms |

Hot-loop profile after the lever: 1000 calls in 0.308 s. The dominant residual
is Python view/key iteration (`dict.fromkeys`, adjacency accessors, and
`_fnx_edge_dfs`), not fnx-to-nx graph conversion.

## Score

Impact 5 x Confidence 5 / Effort 2 = 12.5. Keep threshold is 2.0.

## RCH Note

Commands were invoked through `rch exec`, but RCH logged
`exec called with non-compilation command` for Python `hyperfine`, `pytest`,
and profile commands. No worker pin was available for these Python-only runs.

## Next Route

`br ready --json` now points at `br-r37-c1-1kor1`: weighted Dijkstra
length-only raw kernel with int-preserving emission and cutoff-aware API.
