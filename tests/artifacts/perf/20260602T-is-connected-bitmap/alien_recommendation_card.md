## Alien Recommendation Card: `is_connected` Bitmap BFS

- Profile symptom: `tests/artifacts/perf/20260602T-is-connected-bitmap/profile_is_connected_fnx.txt` showed 96 public `is_connected` calls spending 0.740 s in native `_fnx.is_connected`; wrapper overhead was negligible.
- Baseline gap: `baseline_is_connected.jsonl` measured fnx 0.001861601718 s vs nx 0.001383933312 s on BA(5000, 4, seed=42), 1.3452x slower, with matching digest.
- Graveyard primitive: §7.1 Succinct Data Structures plus §7.2 cache-local data structures. Replace hash-probed visited state and string neighbor iteration with dense `Vec<bool>`/integer queue traversal over the existing `adj_indices` mirror.
- Expected value: Impact 4 x Confidence 5 / Effort 1 = 20.0.
- Fallback: keep the previous string-iterator BFS if `neighbors_indices` is unavailable; no fallback was needed for undirected `Graph`, which exposes the integer adjacency mirror.
