# Alien Recommendation Card

Symptom: sparse NetworkX-compatible generators spend their time in construction, repeatedly applying single-edge mutations even when the caller has already materialized a batch of plain two-tuples.

Matched primitive:
- `alien_cs_graveyard.md` section 14.2, flat combining / sequential batching: convert many small operations on a hot data structure into one ordered batch.
- High-level summary section 8.2, vectorized execution / morsel batching: process cache-sized batches while preserving the outer interface.

Chosen lever: batch only the simple `Graph.add_edges_from` plain two-tuple/no-attr path after Python-level validation has already materialized input order. Preserve external graph semantics while reducing repeated Python map and edge metadata work.

Fallback: if golden output or mutation counters diverge, reject the lever and instead pursue a narrower direct-call refactor that still calls the existing per-edge `add_edge` helper.

EV score: Impact 4 x Confidence 4 / Effort 3 = 5.3.
