# Perf WIN (code-only) — bipartite random_graph (undirected) de-delegation (br-r37-c1-bprandgen)

- Agent: `BlackThrush` · 2026-06-20 · File: `python/franken_networkx/bipartite.py`
- DISK-LOW turn: code-only, NO cargo. Parity + conformance via existing install.

First RNG bipartite generator de-delegated. KEY: nx's random_graph is RNG-driven but
uses PYTHON's random (the @py_random_state-converted ``seed``), so
``networkx.utils.create_py_random_state(seed)`` reproduces nx's EXACT draw sequence
IN PYTHON (no Rust RNG kernel needed -> stays code-only). The fast-gnp geometric loop
has no graph-state dependency, so running it verbatim with the reproduced rng yields
nx's exact edges; collect + bulk add instead of nx build + _from_nx_graph.

Edge cases match nx: p<=0 -> nodes only; p>=1 -> complete_bipartite_graph (native,
byte-exact, its name overrides the fast_gnp name exactly as nx). Directed keeps the
delegation path (DiGraph + second loop).

## Parity (existing install, no build)
- undirected, 3000 random (n,m,p) incl p in {<=0, in (0,1), >=1}: byte-exact node
  order, edge order, bipartite attrs, graph name, fnx.Graph type. 0 mismatches.
- directed still delegates correctly; seed=None produces a valid bipartite Graph;
  pytest -k 'random_graph or bipartite': 1267 passed, 78 skipped.

## Perf
BENCH DEFERRED (disk-low). Win = skip nx build + _from_nx_graph. Measure when disk recovers.

## Follow-up (RNG generators, same create_py_random_state lever)
gnmk_random_graph (choice loop w/ v-in-G[u] rejection -> track an edge set),
configuration_model + preferential_attachment_graph (MultiGraph, more involved).
