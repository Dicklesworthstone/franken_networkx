# Perf WIN (code-only) — bipartite preferential_attachment_graph de-delegation (br-r37-c1-bprandgen)

- Agent: `BlackThrush` · 2026-06-20 · File: `python/franken_networkx/bipartite.py`
- DISK-LOW turn: code-only, NO cargo. Parity + conformance via existing install.

Fourth/last RNG bipartite generator (default MultiGraph) — the most intricate: it reads
GRAPH STATE (len(G), G.degree(b)) as it builds. Tracked the node count (ng) + per-
bottom-node degree (bdeg) so no live graph is needed during the draw loop. nx evaluates
``seed.random() < p or len(G) == naseq`` (random() ALWAYS drawn even on the len==naseq
branch), creating a fresh bottom id=len(G) on the if-branch or preferentially choosing
an existing bottom (degree-weighted reduce()-flattened stub list) on the else-branch.
Reproduced verbatim with create_py_random_state; collect edges + bottom-node creation
order, then bulk add.

## Parity (existing install, no build)
- 5000 random (aseq, p) incl p in {0,...,1}: byte-exact node order (top then bottom in
  creation order), edge order WITH multigraph keys, bipartite attrs, graph name,
  MultiGraph type. 0 mismatches, 0 error-contract mismatches.
- p>1 -> NetworkXError matches; pytest -k 'preferential or bipartite': 1337 passed, 78 skipped.

## Perf
BENCH DEFERRED (disk-low). Win = skip nx MultiGraph build + _from_nx_graph. Measure when disk recovers.

## Bipartite generator surface COMPLETE (create_using=None / default)
Deterministic: complete_bipartite_graph, havel_hakimi_graph, alternating_/reverse_
havel_hakimi_graph. RNG (create_py_random_state lever): random_graph, gnmk_random_graph,
configuration_model, preferential_attachment_graph. Only non-None create_using delegates.
