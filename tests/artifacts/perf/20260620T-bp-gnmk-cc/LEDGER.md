# Perf WIN (code-only) — bipartite gnmk_random_graph (undirected) de-delegation (br-r37-c1-bprandgen)

- Agent: `BlackThrush` · 2026-06-20 · File: `python/franken_networkx/bipartite.py`
- DISK-LOW turn: code-only, NO cargo. Parity + conformance via existing install.

Second RNG bipartite generator. Same create_py_random_state lever (reproduces nx's
exact Python draw sequence). nx draws u=seed.choice(top), v=seed.choice(bottom) and
rejects v already in G[u]; replicate exactly with a per-u neighbour set (top u,
bottom v), collect accepted edges in order, bulk add.

KEY subtlety: ``bottom = list(set(G) - set(top))`` — the set-iteration order drives the
choice INDEX, so it must match nx byte-for-byte. Reproduced the exact expression on the
fnx graph (set(G) built from the same 0..n+m-1 node order as nx -> identical layout ->
identical list() order, even when consecutive bottom ids wrap the hash table).

## Parity (existing install, no build)
- undirected, k < n*m, 4000 random (n,m,k) with n,m in 2..40 (exercises bottom set-order
  wrap): byte-exact node/edge order, bipartite attrs, graph name, fnx.Graph. 0 mismatches.
- edge cases delegate correctly: n==1, m==1 (no edges), k>=max_edges (complete via
  create_using=G), directed. pytest -k 'gnmk or bipartite': 1116 passed, 78 skipped.

## Perf
BENCH DEFERRED (disk-low). Win = skip nx build + _from_nx_graph. Measure when disk recovers.

## RNG generator status
DONE: random_graph, gnmk_random_graph (undirected). Remaining: configuration_model,
preferential_attachment_graph (MultiGraph, more involved draw loops).
