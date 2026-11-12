# Native intersection-graph projection — k_random 3.0x→0.18x, uniform 2.0x→0.55x (both beat nx)

Bead: br-r37-c1-kriproj / br-r37-c1-uriproj
Agent: cc / 2026-06-14

## Problem

- `k_random_intersection_graph` was already native but projected with an O(n²)
  all-pairs `attrs[i] & attrs[j]` scan — 3.0x slower than nx (21.9ms vs 7.3ms).
- `uniform_random_intersection_graph` delegated to nx (`bipartite.random_graph`
  + `projected_graph`) then converted nx→fnx — 2.0x slower (310ms vs 152ms).

## Fix (attribute-clique projection; native byte-exact uniform)

Both project a bipartite (node↔attribute) graph onto the nodes: two nodes are
adjacent iff they share an attribute. Replace the per-pair / nx projection with
an **attribute→holders bucket map** — each attribute's holders form a clique:

- `k_random_intersection_graph`: keep the exact per-node `rng.sample(range(m),
  min(k,m))` draw sequence; bucket nodes by attribute; `add_edges_from` the
  per-attribute cliques (dedups parallel edges). Edge SET identical, ~15x faster.
- `uniform_random_intersection_graph`: for `0 < p < 1`, int/None seed, generate
  natively — reproduce nx's `bipartite.random_graph` geometric-skip sampling
  (`w += 1 + int(log(1-rng.random())/log(1-p))` over the row-major (node,attr)
  enumeration), bucket by attribute, clique-project. Set
  `graph["name"]="fast_gnp_random_graph(n,m,p)"` (carried by nx's
  projected_graph) and `bipartite=0` node attrs. p≤0 / p≥1 / Random|numpy seed
  delegate to nx (nx's name differs at the corners).

## Proof

- 142-case parity sweep (k_random: 20 seeds × 4 configs; uniform: 20 seeds × 3
  configs + 2 delegated corners) comparing full signature (class, graph attrs,
  sorted nodes w/ attrs, sorted edges) vs nx — **0 mismatches**.
- Golden sha256 uniform edges (500,300,0.1,seed=7):
  `94a7ab5988148f0c677f9ac77b6c0b85b188e35d8f817cd5a2d59066423481f1`.
- Targeted (test_intersection_generators_conformance, generator_delegations):
  174 passed. Full suite: only known pre-existing failures.

## Timing (min-of-4)

| op                                     | before | after  | nx     | now vs nx |
|----------------------------------------|--------|--------|--------|-----------|
| k_random_intersection_graph(500,300,3) | 21.9ms | 1.41ms | 7.77ms | 0.18x (beats 5.5x) |
| uniform_random_intersection(500,300,.1)| 310ms  | 93.5ms | 170ms  | 0.55x (beats 1.8x) |

Pure-Python.
