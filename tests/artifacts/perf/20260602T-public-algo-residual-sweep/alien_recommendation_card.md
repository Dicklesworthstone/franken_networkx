## Recommendation: PageRank Absent-Weight Early Exit

- Bead: `br-r37-c1-syvnz`
- Profile target: `fnx.pagerank` on deterministic `gnp_random_graph(1000, 0.05, seed=42)`, default `weight="weight"`, no edge carries that attr.
- Baseline evidence: `baseline_sweep.jsonl`, `profile_pagerank_fnx_steady.txt`.
- Hotspot table:
  - `_fnx.graph_has_nonfinite_edge_weight`: 0.010 s cumulative, value scan that cannot find a value when the attr is absent.
  - `_fnx.adjacency_arrays`: 0.012 s cumulative, sparse COO build using the string weight key.
- Graveyard primitive: staged early-exit validation. The canonical high-level summary describes early-exit validation pipelines as a way to pay only for the first necessary proof stage; the graveyard catalog warns that constants and extra scans matter at practical graph sizes.
- One lever: if `_fnx.graph_has_edge_attr(G, weight)` proves the requested string attr is absent on a simple `Graph`/`DiGraph`, treat the PageRank call as `weight=None` for the native sparse helper and skip nonfinite weight scanning.
- EV score: Impact 3 x Confidence 5 x Reuse 3 / (Effort 1 x AdoptionFriction 1) = 45.0.
- Keep score: Impact 3 x Confidence 5 / Effort 1 = 15.0 (threshold >= 2.0).
- Fallback: helper unavailable, multigraph, attr present, non-string weight key, personalization, nstart, dangling, or any exception keeps the existing route.
- Risk gate: constants risk only; benchmark old/new route directly and keep only if digest is unchanged and sampled calls improve.
