# Perf WIN (code-only) — random_k_out_graph numpy de-delegation (br-r37-c1-koutnative)

- Agent: `BlackThrush` · 2026-06-20 · File: `python/franken_networkx/__init__.py`
- DISK-LOW turn: code-only, NO cargo. Parity verified with existing install.

Extends the RNG-reproduction lever to NUMPY generators. nx's default
_random_k_out_graph_numpy is @np_random_state-seeded, so
networkx.utils.create_random_state(seed) reproduces its EXACT numpy draw sequence
(uniform seed.choice over remaining sources + weighted seed.choice(p=weights/total)
preferential targets, with in-place weight / out-strength / remaining-mask updates).
Run verbatim to collect edges in nx's exact order and build the fnx MultiDiGraph
directly, skipping nx's per-edge add_edge + the nx->fnx conversion. numpy-unavailable
-> delegate (nx's pure-Python variant).

## Parity (existing install, no build)
- 3000 random (n,k,alpha,self_loops): byte-exact node/edge order WITH multidigraph
  keys, graph attrs, MultiDiGraph type. alpha<0 -> ValueError matches.
- No dedicated conformance test exists; broader generator sweep shows 0 generator/k_out
  failures (the 39 unrelated failures are pre-existing flow/dijkstra/connectivity from
  the stale .so vs peers' Rust — confirmed by stashing this change).

## Perf
BENCH DEFERRED (disk-low). Win = skip nx MultiDiGraph build + _from_nx_graph. Measure when disk recovers.

## Lever generalization
create_py_random_state (Python RNG) + create_random_state (numpy RNG) together cover
nx generators seeded by either RNG -> reproduce the exact draw sequence in-process,
build fnx directly. Next numpy-RNG candidates: scale_free_graph, other directed gens.
