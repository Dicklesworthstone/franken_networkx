# Alien Recommendation Card: ego_graph Return Path

## Target

- Workload: `fnx.ego_graph(G, 0, radius=2)` on `barabasi_albert_graph(3000, 4, seed=42)`.
- Baseline: fnx mean `0.17297742869704963s`; NetworkX mean `0.02183564264778397s`.
- Baseline hyperfine repeat-10 process mean: `2.1717935009s`.
- Golden normalized-output sha256: `4db403d99bf3742c4261ba39968be657e7dbf94788fabbf69fc9f3e9532e0eed`.
- Profile: `profile_baseline_fnx.txt` shows the wrapper spends `2.028s` of repeat-10 in `_from_nx_graph` after it already built a concrete fnx graph.

## Primitive Match

- Symptom: redundant materialization across a representation boundary.
- Alien Graveyard match: narrow-interface drop-in replacement plus "constants kill you" discipline. The asymptotic algorithm is unchanged; the win comes from removing the practical constant factor of copying through NetworkX-style adjacency views.
- Alien artifact family: certified rewrite at a stable API boundary. The compiled artifact is a one-line return-path rewrite with an isomorphism proof and golden-output digest check.

## Candidate

Return the already-built concrete fnx graph directly from `ego_graph` instead of converting that graph through `_from_nx_graph(graph)`.

## Score

- Impact: 5
- Confidence: 4
- Reuse: 3
- Effort: 1
- Adoption friction: 1
- EV: `(5 * 4 * 3) / (1 * 1) = 60.0`

## Fallback

Revert the return-path line if any of these trip:

- Golden normalized-output sha changes.
- Node order, edge order, center removal, directed/undirected behavior, weighted distance, or attribute parity tests fail.
- Hyperfine speedup is below `2.0x`.
