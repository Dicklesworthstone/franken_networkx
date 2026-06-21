# WIN — all_node_cuts 0.24x -> 1.52x (6x self-speedup), byte-identical cuts

- Agent: `BlackThrush` · 2026-06-21 · MEASURED · SUPERSEDES 20260621T-all-node-cuts-substrate-noship

## What
`residual_after_flow` (nested in all_node_cuts) rebuilt a residual DiGraph PER FLOW via an
O(E) `add_edge(left,right,**dict(attrs))` loop, COPYING the capacity edge attr. Those residual
edge attrs are NEVER read downstream — transitive_closure / condensation / antichains + the cut
logic use STRUCTURE plus the *auxiliary* node "id" only. Fix: drop the per-edge attr copy and
batch via `add_edges_from((left,right) for ... if cap != flow and cap != 0)`.

## Why it was much bigger than the premise
A microbench said no-attr `_native_adjacency_dict` is only ~1.26x. But the residual feeds the
WHOLE pipeline: a no-attr residual -> no-attr transitive_closure -> no-attr condensation, so
EVERY per-flow `_native_adjacency_dict` materialization downstream (the 0.89s / 68% hotspot)
got lighter, PLUS the per-edge add_edge loop became one bulk build. Compounded: 6x self-speedup.

## Measured (warm, taskset -c 2, PYTHONHASHSEED=0)
  n=40: 0.51x -> 1.27x        n=80: 0.24x -> 1.52x  (fnx 1083ms -> 178ms)

## Correctness
- conformance node_cut/kcutset/all_node/cut: 1692 passed, 0 failed
- 25/25 random connected_watts_strogatz match nx; C10/K6 match; directed -> NetworkXNotImplemented

## Lesson (corrects my own prior call)
I had filed all_node_cuts as "substrate-bound, no clean lever" (20260621T-all-node-cuts-substrate-
noship). WRONG — the profile's _native_adjacency_dict hotspot was AMPLIFIED by a dead-attr +
per-edge-construction Python-layer waste, not pure PyO3 substrate. LEVER: when a profiled
"substrate" hotspot sits behind a Python helper that copies UNUSED attrs / builds per-edge, kill
the dead attr + batch FIRST — the substrate cost often collapses with the payload.
