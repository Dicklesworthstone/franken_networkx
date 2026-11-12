# Perf WIN (code-only) — bipartite gnmk_random_graph DIRECTED de-delegation (br-r37-c1-bprandgen)

- Agent: `BlackThrush` · 2026-06-20 · File: `python/franken_networkx/bipartite.py`
- DISK-LOW turn: code-only, NO cargo. Parity + conformance via existing install.

Completes gnmk_random_graph (directed was still delegating). Every drawn edge is
top->bottom, so the ``v in G[u]`` rejection is exactly the successor check tracked by
``nbrs[u]`` -> the undirected choice-loop works unchanged; only the result type
becomes a DiGraph. Same create_py_random_state RNG reproduction + the
``list(set(G)-set(top))`` set-order replication that drives the choice indices.

Edge cases keep delegation (correct): n==1/m==1 -> nodes only; k>=max_edges -> nx's
complete_bipartite_graph(create_using=DiGraph) which RAISES "Directed Graph not
supported" (an nx quirk; our delegation propagates it).

## Parity (existing install, no build)
- directed, k < n*m, 4000 random (n,m,k) with n,m in 2..40: byte-exact node/edge order,
  bipartite attrs, graph name, DiGraph type. 0 mismatches.
- undirected regression guard 1500/1500; directed n==1 delegates correctly; pytest -k
  'gnmk or bipartite': 1116 passed, 78 skipped.

## Perf
BENCH DEFERRED (disk-low). Win = skip nx build + _from_nx_graph. Measure when disk recovers.

## Bipartite generators now COMPLETE (default / undirected+directed where defined)
complete, 3x havel_hakimi, random_graph (undir+dir), gnmk_random_graph (undir+dir),
configuration_model, preferential_attachment_graph. Only non-None create_using and the
nx-quirk edge cases delegate.
