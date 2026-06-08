# find_cliques_recursive: native Python in-process + eager-ValueError fix (br-r37-c1-fcrnative)

## Problems
1. PERF: delegated the nodes=None case to nx (full fnx->nx conversion per call).
2. PARITY BUG: bad `nodes` (not a clique) raised LAZILY (generator-wrapped) /
   not at all, while nx raises ValueError EAGERLY on call.
3. The nodes!=None path borrowed the ITERATIVE find_cliques order (different
   traversal than nx's recursive).

## Lever (ONE)
Port nx's exact recursive Bron-Kerbosch in PYTHON in-process. Building `adj` from
`G[u]` the same way nx does makes the CPython set-iteration tie-breaks (pivot
`max(subg,...)` and `cand - adj[u]`) identical to nx, so the clique SEQUENCE
byte-matches. The eager part (node validation) runs on call like nx's function
body; only the recursion is the returned generator.

## Proof (correctness — no timing; host load avg ~12 this window)
- 300 ORDER-sensitive calls (Graph/MultiGraph x nodes=None / [edge] / [single]):
  0 mismatches on the full ordered clique list.
- Eager ValueError with nx's exact message; directed -> NetworkXNotImplemented;
  empty -> iter([]); iterator contract `iter(it) is it`. All match nx.
- `pytest -k clique`: 359 passed.

Fixes the eager/lazy ValueError divergence AND drops the per-call conversion.
