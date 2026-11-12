# degree_assortativity / degree_pearson on self-loop graphs — 2.7x slower → 0.3x (beats nx ~3x)

Bead: br-r37-c1-degxyloop
Agent: cc
Date: 2026-06-13

## Problem

`degree_assortativity_coefficient` and `degree_pearson_correlation_coefficient`
were fast on self-loop-FREE graphs but ~2.5-2.7x slower than nx whenever the
graph had ANY self-loop:

| op (600 nodes / 2400 edges, 3 self-loops) | before vs nx |
|-------------------------------------------|--------------|
| degree_assortativity_coefficient          | 2.68x slower (10.2ms) |
| degree_pearson_correlation_coefficient    | 2.52x slower (11.3ms) |

`_degree_xy_pairs_fast` (the vectorized scipy-COO degree-pair extractor that
backs `degree_pearson`) bailed on `number_of_selfloops(G) != 0`, falling back to
the slow `node_degree_xy` DegreeView/EdgeView walk. And
`degree_assortativity_coefficient` gated its native kernel on
`number_of_selfloops == 0`, delegating self-loop graphs to nx (full fnx→nx
conversion).

## Fix (ONE lever: handle self-loops in the vectorized path)

- `_degree_xy_pairs_fast`: drop the self-loop bail. nx's `node_degree_xy` walks
  `G.edges(u)`, so an undirected self-loop `(u,u)` yields the `(deg_u, deg_u)`
  pair exactly ONCE — matching the single `(u,u)` diagonal entry the symmetric
  COO carries. The only correction needed (undirected) is the degree: to_scipy
  writes `A[u,u]=1` per self-loop but nx counts an undirected loop as +2, so
  `deg = A.sum(axis=1) + A.diagonal()`. The directed case needs nothing (out/in
  already count a loop once each; one diagonal entry = one directed (u,u) edge).
- `degree_pearson` automatically benefits (it calls `_degree_xy_pairs_fast`).
- `degree_assortativity_coefficient` (undirected, unweighted, nodes=None): route
  self-loop graphs to the vectorized `degree_pearson` (nx's assortativity equals
  the degree-degree Pearson r — verified) instead of nx delegation. Degenerate
  inputs (<2 degree pairs) make `pearsonr` raise where nx's mixing-matrix path
  returns nan — those rare cases are caught and delegated to nx for exact parity.

## Proof

- 40-seed × {Graph, DiGraph} parity sweep (random sizes/densities, self-loops,
  empty/degenerate) for BOTH functions, comparing value AND exception type vs nx
  — **0 mismatches** over 160 checks.
- Golden sha256 of all results:
  `dfa02d3506efcc0c46694b4855e75de3d99ea7d388f37244bad31ae1fed603b4`.
- Targeted suite (`assortativ`/`pearson`/`degree_mixing`/`node_degree_xy`/
  `degenerate`): 811 passed.
- Full python suite: only the known pre-existing failures remain.

## Timing (600 nodes / 2400 edges, 3 self-loops, min-of-8×3)

| op                                      | before  | after  | nx     | after vs nx | self-speedup |
|-----------------------------------------|---------|--------|--------|-------------|--------------|
| degree_assortativity_coefficient        | 10206µs | 1209µs | 3860µs | 0.31x | ~8.4x |
| degree_pearson_correlation_coefficient  | 11263µs | 1166µs | 3888µs | 0.30x | ~9.7x |

Both now beat nx ~3x on self-loop graphs (the self-loop-free path was already
fast). Pure-Python change — no Rust rebuild.
