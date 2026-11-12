# Correctness fix (code-only) — bipartite weighted-projection edge order (br-r37-c1-bpprojorder)

- Agent: `BlackThrush` · 2026-06-20 · File: `python/franken_networkx/bipartite.py`
- DISK-CRITICAL turn: code-only, NO cargo. Parity + conformance via existing install.

While extending bipartite projections I found a LATENT edge-order bug in the shipped
`_weighted_projection_inprocess` fast path (used by weighted / overlap / generic /
collaboration projected graphs). Two root causes, both set-iteration-order:

1. networkx builds the candidate set `nbrs2` TWO different ways: weighted/overlap/
   generic use `{...} - {u}`, collaboration uses `{... if n != u}`. These produce
   DIFFERENT CPython set layouts -> different edge iteration order. The shared helper
   used the `if n != u` form for ALL callers, so weighted/overlap/generic diverged.
2. The helper snapshotted adjacency rows as SETS, but iterated them while building
   nbrs2 — nx iterates `B[nbr]` (AtlasView = insertion order). In hash-collision
   cases the set inner-row order diverged.

Measured BEFORE: undirected weighted_projected_graph matched nx exact edge order only
2994/3000 (~0.2%); overlap/generic same class. (Edge SET and weights were always
correct — only list(edges()) ORDER diverged.)

Fix: snapshot an ORDER-PRESERVING adjacency list (native key order == AtlasView order,
verified 0/500 mismatch) for nbrs2 construction (keep sets for the weight `&`/`|`/`min`/
`len` ops), and add a `nbrs2_form` param so each caller requests its nx form
('minus' default; collaboration passes 'filter').

## Parity (existing install, no build) — EXACT edge order + weights vs nx-on-nx
weighted 3000/3000, weighted(ratio) 3000/3000, overlap(jaccard) 3000/3000,
overlap(overlap) 3000/3000, generic 3000/3000, collaboration 3000/3000.
pytest -k 'projected or projection or bipartite': 1124 passed, 78 skipped.

## Follow-up (verified, not yet shipped)
Directed weighted/overlap/generic projections can also be de-delegated byte-exactly
(integer/ratio weight, no float order): directed weighted proto = 4000/4000 with the
'minus' form + successor-list + predecessor-set snapshot. Ship next turn.
