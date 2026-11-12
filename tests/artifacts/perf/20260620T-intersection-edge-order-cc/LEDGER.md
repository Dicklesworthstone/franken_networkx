# Correctness fix (code-only) — intersection (simple Graph) edge-order parity (br-r37-c1-interorder)

- Agent: `BlackThrush` · 2026-06-20 · File: `python/franken_networkx/__init__.py`
- DISK-LOW turn: code-only, NO cargo. Parity + conformance via existing install.

Found a latent EDGE-ORDER divergence in the simple-Graph fast path of `intersection`.
nx.intersection -> intersection_all builds each graph's undirected edge set WITH both
orientations, then intersects: ``edge_intersection = G_set; edge_intersection &= H_set``.
The fnx fast path instead used a comprehension over ONLY H's witness set filtered by
G's (no-reverse) edge set -> a different CPython set-iteration order, so
``list(R.edges())`` diverged from nx in hash-collision cases (measured ~3/1500 = 0.2%;
the edge SET and nodes were always correct, only the ORDER differed).

Fix: replicate nx's exact construction (both edge sets with reverses, ``g_set &=
h_set``). DiGraph/Multi cases already route to intersection_all (already nx-verbatim),
so only the simple-Graph fast path needed this.

## Parity (existing install, no build)
- 6000 random Graph pairs: byte-exact node order, edge order, graph attrs (vs prior
  ~0.2% edge-order divergence). No edge attrs copied (nx contract). 0 mismatches.
- pytest -k intersection: 72 passed.

## Perf
No perf change (same O(E) set construction); this is a correctness fix. No bench owed.
