# bidirectional_dijkstra — in-process nx algorithm, drop double fnx->nx delegation (br-r37-c1-bdjkstra)

## Problem (correctness + perf)
`bidirectional_dijkstra`'s local path called `dijkstra_path(G,s,t,weight)` AND
`dijkstra_path_length(G,s,t,weight)`. For weighted graphs each of those delegates to nx, so
every call paid TWO full fnx->nx O(V+E) conversions — for a single-pair query that is the
whole cost: ~107ms on n=3000 (~100x SLOWER than nx, 0.01x). Worse, it returned the *plain*
Dijkstra path, which DIVERGES from nx's *bidirectional* path on ~2% of pairs (current wrapper
measured 441/450 vs nx).

## Lever (ONE)
Run networkx's exact bidirectional-Dijkstra in-process on the fnx graph (`G.adj` / `G.succ` /
`G.pred`, string weight `d.get(weight,1)`, shared counter tie-break, meeting-node path
reconstruction) — no conversion. Multigraph (per-key min weight), callable / non-string
weight, and negative / non-finite weights still delegate to nx.

## Behavior parity (isomorphism proof)
- 600 cases (200 random graphs: weighted/unweighted x directed/undirected x 25% string-keyed,
  3 random (s,t) each, plus src==tgt, missing-node NodeNotFound, no-path NetworkXNoPath,
  multigraph delegation) -> **600/600 byte-exact** with `nx.bidirectional_dijkstra` (the
  current wrapper was 441/450 — this also FIXES a path-tie-break correctness bug).
- Golden sha256: `d5590b0f011af23742ef22531ccb35f3f0292079ea3ca574633055db0bb9a141`.
- `pytest -k "bidirectional or dijkstra or shortest_path"` -> 825 passed.

## Benchmark (warm min, ms, weighted gnp single-pair)
| n    | networkx | fnx before (delegation) | fnx after | self-speedup |
|------|----------|-------------------------|-----------|--------------|
| 500  | 0.224    | 5.31                    | 1.65      | 3.2x         |
| 1500 | 0.272    | 40.3                    | 1.76      | 23x          |
| 3000 | 1.03     | 107.6                   | 7.5       | 14x          |

Removes a pathological ~100x-slower-than-nx delegation (now ~0.14x = ~7x slower). The
residual gap is the fnx Python adjacency-view access in the heap loop; a NATIVE Rust
bidirectional-Dijkstra kernel (integer adjacency) is the follow-up to beat nx (filed).

## Score
Impact: high (fixes a correctness bug AND a ~100x perf regression; large self-speedup).
Confidence: high (600-case byte-exact golden + 825 tests). Effort: low (one Python helper).
