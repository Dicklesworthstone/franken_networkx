# Perf WIN (code-only) — bipartite configuration_model de-delegation (br-r37-c1-bprandgen)

- Agent: `BlackThrush` · 2026-06-20 · File: `python/franken_networkx/bipartite.py`
- DISK-LOW turn: code-only, NO cargo. Parity + conformance via existing install.

Third RNG bipartite generator (default MultiGraph). create_py_random_state lever:
nx builds degree-repeated stub lists (a-vertex v repeated aseq[v] times; same for b),
seed.shuffles BOTH, and pairs astubs[i] <-> bstubs[i]. Reproduce the exact initial
stub order + rng so both shuffles match nx byte-for-byte, then bulk add the paired
multi-edges. @py_random_state(3) is reproduced via networkx.utils.create_py_random_state.

## Parity (existing install, no build)
- 4000 random valid degree-seq pairs: byte-exact node/edge order WITH multigraph keys,
  bipartite attrs, graph name, MultiGraph type. 0 mismatches, 0 error-contract mismatches.
- invalid (sum mismatch) -> NetworkXError matches; pytest -k 'configuration or
  bipartite': 1149 passed, 78 skipped.

## Perf
BENCH DEFERRED (disk-low). Win = skip nx MultiGraph build + _from_nx_graph. Measure when disk recovers.

## RNG generator status
DONE: random_graph, gnmk_random_graph, configuration_model. Remaining:
preferential_attachment_graph (MultiGraph, preferential-attachment draw loop).
