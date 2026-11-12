# Perf WIN (code-only) — bipartite random_graph DIRECTED de-delegation (br-r37-c1-bprandgen)

- Agent: `BlackThrush` · 2026-06-20 · File: `python/franken_networkx/bipartite.py`
- DISK-LOW turn: code-only, NO cargo. Parity + conformance via existing install.

Completes random_graph (the directed case was still delegating). nx runs the geometric
fast-gnp loop a SECOND time for directed B to add the reverse (m->n) edges, continuing
the same rng sequence. Reproduce both loops in order via create_py_random_state, build
a DiGraph, bulk add. Replicated nx quirks: p<=0 -> nodes only; p>=1 -> UNDIRECTED
complete_bipartite_graph even for directed=True (verified type Graph == nx).

## Parity (existing install, no build)
- directed, 4000 random (n,m,p) incl p edge cases: byte-exact node order, edge order
  (both directions), bipartite attrs, graph name, DiGraph type. 0 mismatches.
- undirected regression guard 1000/1000; pytest -k 'random_graph or bipartite': 1267
  passed, 78 skipped.

## Perf
BENCH DEFERRED (disk-low). Win = skip nx build + _from_nx_graph. Measure when disk recovers.

## Remaining bipartite RNG directed case
gnmk_random_graph directed (choice loop + v-in-G[u] rejection over a DiGraph) — follow-up.
