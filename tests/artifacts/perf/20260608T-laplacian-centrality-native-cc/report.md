# laplacian_centrality (undirected): native in-process, drop fnx->nx delegation (br-r37-c1-lapcentnative)

## Problem
laplacian_centrality delegated to nx (full fnx->nx conversion + nx compute) on
every call.

## Lever (ONE)
The UNDIRECTED case is `laplacian_matrix` (D - A) + a deterministic numpy energy
loop (no eigenvalues). Compute in-process from the NATIVE laplacian_matrix
(byte-identical to nx's) + the same numpy, dropping the per-call conversion.
DIRECTED (Perron-vector / PageRank via directed_laplacian_matrix) and callable
weight keep delegating.

## Proof (correctness — no timing; host load avg ~17 this window)
- 240 calls (weighted/unweighted x self-loops x normalized T/F x nodelist subset
  x weight=None): 0 mismatches (value + key order).
- Edge cases: null -> NetworkXPointlessConcept; no-edges+normalized ->
  ZeroDivisionError; no-edges+unnormalized -> {n:0}; single edge; directed ->
  delegate; duplicate nodelist -> NetworkXError. All match nx.
- Golden fnx == nx.
- `pytest -k laplacian`: 90 passed.

Structural delegation-elimination (load-independent); the O(n^3) energy loop is
identical numpy, so the win is the removed conversion + native matrix build.
